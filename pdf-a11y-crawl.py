#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

__version__ = "0.1.2"

PDF_RE = re.compile(r"\.pdf(\?|#|$)", re.IGNORECASE)


@dataclass
class PdfResult:
    pdf_url: str
    source_page: str
    http_status: int | None
    content_type: str | None
    bytes_downloaded: int | None
    sha256: str | None
    has_text_layer: bool | None          # True if fonts found via pdffonts
    fonts_count: int | None
    pdftotext_ran: bool
    pdftotext_ok: bool | None
    pdftotext_output: str | None
    pdftotext_bytes: int | None
    pdftotext_chars: int | None
    text_density: float | None
    verapdf_ran: bool
    verapdf_passed: bool | None
    notes: str | None


def same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


def normalize_url(base: str, href: str) -> str | None:
    if not href:
        return None
    u = urljoin(base, href)
    u, _frag = urldefrag(u)
    return u


def is_probably_pdf(url: str) -> bool:
    return bool(PDF_RE.search(url))


def safe_filename_from_url(url: str) -> str:
    # Stable, non-guessable-ish but deterministic name from URL
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"{h}.pdf"


def run_pdffonts(pdf_path: Path) -> tuple[bool, int, str | None]:
    """
    Returns: (has_text_layer, fonts_count, error_note)
    If fonts_count > 0 => there are font objects => likely text layer.
    """
    if shutil.which("pdffonts") is None:
        return (None, None, "pdffonts not installed (poppler-utils missing)")  # type: ignore

    try:
        p = subprocess.run(
            ["pdffonts", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if p.returncode != 0:
            return (None, None, f"pdffonts failed: {p.stderr.strip()[:200]}")  # type: ignore

        lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
        # Typical output includes two header lines, then rows. If no fonts, only headers or nothing.
        # Heuristic: count rows after a separator line of dashes, or simply count non-header rows.
        # We'll treat any line that doesn't start with 'name' or '---' as a font row.
        font_rows = [
            ln for ln in lines
            if not ln.lower().startswith("name")
            and not ln.startswith("---")
        ]
        fonts_count = len(font_rows)
        return (fonts_count > 0, fonts_count, None)

    except subprocess.TimeoutExpired:
        return (None, None, "pdffonts timed out")  # type: ignore
    except Exception as e:
        return (None, None, f"pdffonts exception: {e}")  # type: ignore


def run_pdftotext(pdf_path: Path, out_txt: Path, timeout: int = 120):
    if shutil.which("pdftotext") is None:
        return False, "pdftotext not installed"

    try:
        p = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), str(out_txt)],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if p.returncode != 0:
            return False, p.stderr.strip()
        return True, None
    except Exception as e:
        return False, str(e)


def run_verapdf(pdf_path: Path) -> tuple[bool, bool | None, str | None]:
    """
    Returns: (ran, passed?, note)
    veraPDF output/return codes can vary by package; we use a simple heuristic:
    - If it runs and output contains 'PASS' (case-insensitive) and not 'FAIL', treat as pass.
    """
    if shutil.which("verapdf") is None:
        return (False, None, None)

    try:
        p = subprocess.run(
            ["verapdf", "--flavour", "ua1", "--format", "text", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        out = (p.stdout + "\n" + p.stderr).lower()
        # Heuristic: look for pass/fail tokens.
        passed = None
        if "pass" in out and "fail" not in out:
            passed = True
        if "fail" in out:
            passed = False
        note = None
        if p.returncode != 0 and passed is None:
            note = f"verapdf return code {p.returncode}"
        return (True, passed, note)

    except subprocess.TimeoutExpired:
        return (True, None, "verapdf timed out")
    except Exception as e:
        return (True, None, f"verapdf exception: {e}")


def fetch_html(session: requests.Session, url: str, timeout: int) -> tuple[int | None, str | None, str | None]:
    try:
        r = session.get(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "pdf-a11y-crawler/0.1"})
        ct = r.headers.get("Content-Type", "")
        if r.status_code >= 400:
            return (r.status_code, ct, None)
        if "text/html" not in ct and "application/xhtml+xml" not in ct:
            return (r.status_code, ct, None)
        r.encoding = r.apparent_encoding
        return (r.status_code, ct, r.text)
    except Exception:
        return (None, None, None)


def download_pdf(session: requests.Session, url: str, out_path: Path, timeout: int, max_bytes: int) -> tuple[int | None, str | None, int | None, str | None]:
    """
    Returns: (status, content_type, bytes_downloaded, note)
    """
    try:
        with session.get(url, timeout=timeout, stream=True, allow_redirects=True, headers={"User-Agent": "pdf-a11y-crawler/0.1"}) as r:
            ct = r.headers.get("Content-Type", "")
            status = r.status_code
            if status >= 400:
                return (status, ct, None, f"HTTP {status}")

            # Some servers mislabel; accept if URL ends with .pdf OR content-type suggests PDF.
            if ("application/pdf" not in ct.lower()) and (not is_probably_pdf(url)):
                # still download a small chunk to decide? We'll just note it.
                pass

            out_path.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            h = hashlib.sha256()

            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        return (status, ct, total, f"exceeded max_bytes={max_bytes}")
                    f.write(chunk)
                    h.update(chunk)

            return (status, ct, total, h.hexdigest())

    except Exception as e:
        return (None, None, None, f"download exception: {e}")


def extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    hrefs = []
    for a in soup.find_all("a"):
        href = a.get("href")
        u = normalize_url(base_url, href)
        if u:
            hrefs.append(u)
    return hrefs


def crawl(
    start_url: str,
    recursive: bool,
    max_pages: int,
    timeout: int,
    max_bytes: int,
    out_dir: Path,
    include_external_pdfs: bool,
    run_vera: bool,
    pdftotext: bool,
    dry_run=False,
) -> list[PdfResult]:
    session = requests.Session()

    seen_pages: set[str] = set()
    seen_pdfs: set[str] = set()
    queue: list[str] = [start_url]

    results: list[PdfResult] = []

    with tqdm(total=max_pages if recursive else 1, desc="Crawling pages", unit="page") as bar:
        while queue and (len(seen_pages) < max_pages):
            page_url = queue.pop(0)
            if page_url in seen_pages:
                continue
            seen_pages.add(page_url)
            bar.update(1)

            status, ct, html = fetch_html(session, page_url, timeout)
            if not html:
                continue

            links = extract_links(html, page_url)

            for link in links:
                # Collect PDFs
                if is_probably_pdf(link):
                    # Always define these so they exist
                    dl_status = None
                    dl_ct = None
                    dl_bytes = None
                    sha256 = None
                    note = None

                    if dry_run:
                        results.append(
                            PdfResult(
                                pdf_url=link,
                                source_page=page_url,
                                http_status=None,
                                content_type=None,
                                bytes_downloaded=None,
                                sha256=None,
                                has_text_layer=None,
                                fonts_count=None,
                                pdftotext_ran=False,
                                pdftotext_ok=None,
                                pdftotext_output=None,
                                pdftotext_bytes=None,
                                pdftotext_chars=None,
                                text_density=None,
                                verapdf_ran=False,
                                verapdf_passed=None,
                                notes="dry-run (not downloaded)"
                            )
                        )
                        continue

                    # ---- Normal (non-dry-run) processing ----
                    pdf_path = out_dir / "pdfs" / safe_filename_from_url(link)

                    dl_status, dl_ct, dl_bytes, dl_note_or_sha = download_pdf(
                        session, link, pdf_path,
                        timeout=timeout,
                        max_bytes=max_bytes
                    )

                    if dl_status is None:
                        note = dl_note_or_sha
                    else:
                        if dl_note_or_sha and re.fullmatch(r"[0-9a-f]{64}", dl_note_or_sha):
                            sha256 = dl_note_or_sha
                        else:
                            note = dl_note_or_sha

                    has_text_layer, fonts_count, pdffonts_note = run_pdffonts(pdf_path)
                    if pdffonts_note:
                        note = (note + "; " if note else "") + pdffonts_note

                    pdftotext_ran = False
                    pdftotext_ok = None
                    pdftotext_output = None
                    
                    # Optional: extract text for review
                    if pdftotext and has_text_layer and pdf_path.exists():
                        pdftotext_ran = True
                        txt_path = pdf_path.with_suffix(".pdftotext.txt")
                        ok, err = run_pdftotext(pdf_path, txt_path)
                        pdftotext_ok = ok
                        pdftotext_output = str(txt_path) if ok else None
                        if not ok:
                            note = (note + "; " if note else "") + f"pdftotext failed: {err}"

                    pdftotext_bytes = None
                    pdftotext_chars = None
                    text_density = None

                    if pdftotext_ok and pdftotext_output and dl_bytes:
                        txt_p = Path(pdftotext_output)
                        try:
                            data = txt_p.read_text(encoding="utf-8", errors="replace")
                            pdftotext_chars = len(data)
                            pdftotext_bytes = len(data.encode("utf-8", errors="replace"))
                            text_density = pdftotext_bytes / dl_bytes if dl_bytes else None
                        except Exception as e:
                            note = (note + "; " if note else "") + f"pdftotext read failed: {e}"

                    ver_ran = False
                    ver_passed = None
                    if run_vera:
                        ver_ran, ver_passed, ver_note = run_verapdf(pdf_path)
                        if ver_note:
                            note = (note + "; " if note else "") + ver_note

                    results.append(
                        PdfResult(
                            pdf_url=link,
                            source_page=page_url,
                            http_status=dl_status,
                            content_type=dl_ct,
                            bytes_downloaded=dl_bytes,
                            sha256=sha256,
                            has_text_layer=has_text_layer,
                            fonts_count=fonts_count,
                            pdftotext_ran=pdftotext_ran,
                            pdftotext_ok=pdftotext_ok,
                            pdftotext_output=pdftotext_output,
                            pdftotext_bytes=pdftotext_bytes,
                            pdftotext_chars=pdftotext_chars,
                            text_density=text_density,
                            verapdf_ran=ver_ran,
                            verapdf_passed=ver_passed,
                            notes=note
                        )
                    )

                # Recurse to other pages
                if recursive:
                    if same_origin(start_url, link) and (link not in seen_pages):
                        # Avoid crawling PDFs as pages
                        if not is_probably_pdf(link):
                            queue.append(link)

            if not recursive:
                break

    return results


def write_reports(results: list[PdfResult], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "report.json"
    csv_path = out_dir / "report.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()) if results else [
            "pdf_url","source_page","http_status","content_type","bytes_downloaded","sha256",
            "has_text_layer","fonts_count","verapdf_ran","verapdf_passed","notes"
        ])
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))

    return (csv_path, json_path)


def main():
    from datetime import datetime

    ap = argparse.ArgumentParser(
        prog="pdf-a11y-crawl",
        description=(
            "Crawl a web page and identify PDF files, then analyze them for "
            "basic accessibility characteristics such as text presence "
            "(image-only detection) and optional PDF/UA checks."
        ),
        epilog=(
            "Examples:\n"
            "  pdf-a11y-crawl https://example.com/page\n"
            "  pdf-a11y-crawl --recursive https://example.com\n"
            "  pdf-a11y-crawl --verapdf https://example.com/docs\n"
            "\n"
            "Notes:\n"
            "  - By default, only the given page is scanned.\n"
            "  - --recursive enables crawling of linked pages.\n"
            "  - --verapdf enables PDF/UA checks (optional, slower).\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

    ap.add_argument(
        "url",
        help="Starting URL to scan for PDF links"
    )

    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover PDFs but do not download or analyze them"
    )

    ap.add_argument(
        "--include-external-pdfs",
        action="store_true",
        help="Also scan PDFs hosted on external domains"
    )

    ap.add_argument(
        "--max-bytes",
        type=int,
        default=50_000_000,
        help="Maximum size of a PDF in bytes (default: 50MB)"
    )

    ap.add_argument(
        "--max-pages",
        type=int,
        default=200,
        help="Maximum number of pages to crawl when using --recursive (default: 200)"
    )

    ap.add_argument(
        "--out",
        default="out",
        help="Output directory (default: ./out)"
    )

    ap.add_argument(
        "--pdftotext",
        action="store_true",
        help="Dump extracted text for review when text layer is detected"
    )

    ap.add_argument(
        "--recursive",
        action="store_true",
        help="Follow links on the same site (default: off)"
    )

    ap.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds (default: 20)"
    )

    ap.add_argument(
        "--verapdf",
        action="store_true",
        help="Run veraPDF to check PDF/UA compliance (slower)"
    )

    ap.add_argument(
        "--version",
        action="version",
        version="pdf-a11y-crawler 0.1.0"
    )

    args = ap.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out) / timestamp

    results = crawl(
        start_url=args.url,
        recursive=args.recursive,
        max_pages=args.max_pages,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
        out_dir=out_dir,
        include_external_pdfs=args.include_external_pdfs,
        run_vera=args.verapdf,
        pdftotext=args.pdftotext,
        dry_run=args.dry_run,
    )

    csv_path, json_path = write_reports(results, out_dir)

    # quick summary
    total = len(results)
    image_only = sum(1 for r in results if r.has_text_layer is False)
    text_based = sum(1 for r in results if r.has_text_layer is True)
    unknown = total - image_only - text_based

    print("\nDone.")
    print(f"PDFs found: {total}")
    print(f"Text-based (fonts found): {text_based}")
    print(f"Image-only (no fonts): {image_only}")
    print(f"Unknown/failed: {unknown}")
    print(f"\nReports:\n  {csv_path}\n  {json_path}")
    if args.dry_run:
        print("\nDry-run complete (no PDFs downloaded).")


if __name__ == "__main__":
    main()

