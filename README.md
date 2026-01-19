# 📄 pdf-a11y-crawler

`pdf-a11y-crawler` is a lightweight command-line tool for discovering PDF files on a website and identifying **potential accessibility issues**, with a focus on detecting **image-only PDFs** and other high-risk cases.

This tool is intended as an **early-stage accessibility screening utility**, not a compliance certification tool.

---

## 🎯 Purpose

This project helps answer a common question:

> **“Which PDFs on this site are most likely inaccessible?”**

It does this by:
- Crawling a web page (optionally recursively)
- Discovering linked PDF files
- Detecting whether PDFs contain extractable text
- Optionally running PDF/UA checks using veraPDF
- Producing machine-readable reports (CSV / JSON)

---

## ✅ What This Tool Does

✔ Finds PDF files linked from a webpage
✔ Detects image-only (scanned) PDFs
✔ Identifies whether text is present
✔ Optionally runs veraPDF for PDF/UA checks
✔ Generates CSV and JSON reports
✔ Supports dry-run and recursive scanning

---

## ❌ What This Tool Does NOT Do

❌ It does **not** certify WCAG or ADA compliance
❌ It does **not** guarantee PDF accessibility
❌ It does **not** fix PDFs
❌ It does **not** replace manual accessibility review

This tool provides **signal**, not legal or accessibility certification.

---

## 🧠 Important Context

- WCAG 2.1 does **not** require PDF/UA compliance.
- A PDF can fail PDF/UA and still be readable.
- An image-only PDF is almost always inaccessible.
- This tool focuses on identifying **high-risk cases quickly**.

---

## 🛠 Setup (Debian Trixie)

This section describes how to install and run **pdf-a11y-crawler** on **Debian Trixie** using a Python virtual environment.

---

### 1️⃣ Install System Dependencies

Update package lists:

```bash
sudo apt update
```

Install required packages:

```bash
sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    poppler-utils \
    curl
```

> `poppler-utils` provides `pdffonts`, which is required for detecting text in PDFs.

---

### 2️⃣ Clone the Repository

```bash
git clone https://github.com/unixabg/pdf-a11y-crawler.git
cd pdf-a11y-crawler
```

---

### 3️⃣ Create and Activate a Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

You should now see:

```text
(venv) user@host:~/pdf-a11y-crawler$
```

---

### 4️⃣ Install Python Dependencies

```bash
pip install requests beautifulsoup4 tqdm
```

---

### 5️⃣ Make the Script Executable

```bash
chmod +x pdf-a11y-crawl.py
```

---

### 6️⃣ Verify Installation

```bash
./pdf-a11y-crawl.py --version
```

Expected output:

```text
pdf-a11y-crawler 0.1.0
```

---

### 7️⃣ Optional: Install veraPDF (for PDF/UA checks)

veraPDF is optional and only required if you use `--verapdf`.

Download from:

```
https://verapdf.org/software/
```

Once installed verify veraPDF installation:

```bash
verapdf --version
```

---

###  8️⃣ Deactivate Environment (optional)

```bash
deactivate
```

---

## ▶️ Usage

### Basic scan (single page)
```bash
./pdf-a11y-crawl.py https://example.com/page
```

### Recursive scan
```bash
./pdf-a11y-crawl.py --recursive https://example.com
```

### Dry run (no downloads)
```bash
./pdf-a11y-crawl.py --dry-run https://example.com
```

### Enable PDF/UA checks
```bash
./pdf-a11y-crawl.py --verapdf https://example.com
```

### See help for more usage options
```bash
./pdf-a11y-crawl.py --help
usage: pdf-a11y-crawl [-h] [--dry-run] [--include-external-pdfs] [--max-bytes MAX_BYTES] [--max-pages MAX_PAGES] [--out OUT] [--pdftotext]
                       [--recursive] [--timeout TIMEOUT] [--verapdf] [--version]
                      url

Crawl a web page and identify PDF files, then analyze them for basic accessibility characteristics such as text presence (image-only detection) and optional PDF/UA checks.

positional arguments:
  url                   Starting URL to scan for PDF links

options:
  -h, --help            show this help message and exit
  --dry-run             Discover PDFs but do not download or analyze them
  --include-external-pdfs
                        Also scan PDFs hosted on external domains
  --max-bytes MAX_BYTES
                        Maximum size of a PDF in bytes (default: 50MB)
  --max-pages MAX_PAGES
                        Maximum number of pages to crawl when using --recursive (default: 200)
  --out OUT             Output directory (default: ./out)
  --pdftotext           Dump extracted text for review when text layer is detected
  --recursive           Follow links on the same site (default: off)
  --timeout TIMEOUT     HTTP timeout in seconds (default: 20)
  --verapdf             Run veraPDF to check PDF/UA compliance (slower)
  --version             show program's version number and exit

Examples:
  pdf-a11y-crawl https://example.com/page
  pdf-a11y-crawl --recursive https://example.com
  pdf-a11y-crawl --verapdf https://example.com/docs

Notes:
  - By default, only the given page is scanned.
  - --recursive enables crawling of linked pages.
  - --verapdf enables PDF/UA checks (optional, slower).
```

---

## 📊 Output

Results are written to:

```
out/
 ├──/date-time/report.csv
 └──/date-time/report.json
```

Each PDF entry includes:
- Source page
- PDF URL
- Text detection result
- Font count
- Optional veraPDF result
- Notes and warnings

---

## 🧪 Accessibility Detection Logic

### Primary check
- Uses `pdffonts` to determine whether text exists
- PDFs with no fonts are flagged as likely inaccessible

### Optional check
- Uses `veraPDF` to evaluate PDF/UA conformance
- Results are informational only

---

## ⚠️ Compliance Notice

This tool:

- ❌ Does not certify WCAG or ADA compliance
- ❌ Does not replace manual accessibility testing
- ✔ Helps identify likely accessibility risks
- ✔ Supports accessibility remediation workflows

Use this tool as part of a broader accessibility review process.

---

## 🔐 Responsible Use

Only scan websites and documents you own or are authorized to test.

Do not use this tool to scan:
- third-party sites without permission
- internal systems you do not control

---

## 📦 Version

Current version:

```
0.1.0
```

---

## 🙌 Contributions

Suggestions, improvements, and issues are welcome.

This project is intentionally kept simple and focused.
