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

## 📥 Download

### 🔹 Clone from GitHub

```bash
git clone https://github.com/unixabg/pdf-a11y-crawler.git
cd pdf-a11y-crawler
```

---

## 🧰 Requirements

- Python 3.9+
- `poppler-utils` (for `pdffonts`)
- Optional: `veraPDF` (for PDF/UA checks)

### Debian / Ubuntu
```bash
sudo apt install poppler-utils
```

### veraPDF (optional)
Download from:
https://verapdf.org/software/

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
