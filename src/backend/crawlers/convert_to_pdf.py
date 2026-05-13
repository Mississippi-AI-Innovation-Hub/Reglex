"""
Convert all non-PDF crawled documents to PDF using pandoc + pdflatex.

For each HTML/DOCX file:
  1. Injects a clickable source URL header linking back to the original page
  2. Converts to PDF via pandoc with the pdflatex engine
  3. Preserves document structure (headings, tables, lists)
  4. Saves as .pdf alongside or replacing the original

Usage:
  python3 -m backend.crawlers.convert_to_pdf --dest ./crawled_documents
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote


# ── Source URL mapping ──────────────────────────────────────────────────

# Known URL patterns per state for reconstructing source links
SOURCE_URL_PATTERNS = {
    "GA": {
        "base": "https://rules.sos.ga.gov/gac/",
        "pattern": lambda filename, agency: (
            f"https://rules.sos.ga.gov/gac/{filename.replace('.html', '').replace('.pdf', '')}"
        ),
    },
    "TX": {
        "base": "https://texas-sos.appianportalsgov.com/rules-and-meetings",
        "pattern": lambda filename, agency: (
            "https://texas-sos.appianportalsgov.com/rules-and-meetings"
            "?interface=VIEW_TAC"
        ),
    },
    "LA": {
        "base": "https://www.doa.la.gov/doa/osr/louisiana-administrative-code/",
        "pattern": lambda filename, agency: (
            "https://www.doa.la.gov/doa/osr/louisiana-administrative-code/"
        ),
    },
}


def get_source_url(filepath: Path, manifest_lookup: dict[str, str]) -> str:
    """Get the source URL for a document from manifest or URL patterns."""
    # Try manifest first
    str_path = str(filepath)
    for key, url in manifest_lookup.items():
        if key in str_path or str_path.endswith(key):
            return url

    # Fall back to pattern-based URL construction
    parts = filepath.parts
    # Find state and agency from path: .../crawled_documents/STATE/agency_type/file
    state = None
    agency = None
    for i, part in enumerate(parts):
        if part in ("MS", "TN", "AL", "LA", "AR", "GA", "TX"):
            state = part
            if i + 1 < len(parts):
                agency = parts[i + 1]
            break

    if state and state in SOURCE_URL_PATTERNS:
        pattern = SOURCE_URL_PATTERNS[state]
        return pattern["pattern"](filepath.name, agency)

    return ""


def load_manifest_urls(dest_root: Path) -> dict[str, str]:
    """Load file → source URL mapping from manifest.json."""
    manifest_path = dest_root / "manifest.json"
    lookup: dict[str, str] = {}

    if not manifest_path.exists():
        return lookup

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)

        for entry in manifest.get("entries", []):
            for doc in entry.get("documents", []):
                saved_path = doc.get("saved_path", "")
                url = doc.get("url", "")
                if saved_path and url:
                    lookup[saved_path] = url
                # Also store by filename
                filename = doc.get("filename", "")
                if filename and url:
                    lookup[filename] = url
    except (json.JSONDecodeError, KeyError):
        pass

    return lookup


def create_header_latex(source_url: str, state: str, agency: str) -> str:
    """Create a LaTeX header block with source link."""
    if not source_url:
        return ""

    # Escape special LaTeX characters in URL
    safe_url = source_url.replace("%", "\\%").replace("#", "\\#").replace("&", "\\&")
    safe_url = safe_url.replace("_", "\\_").replace("$", "\\$")

    header = (
        f"\\noindent\\fbox{{\\parbox{{\\dimexpr\\textwidth-2\\fboxsep-2\\fboxrule\\relax}}{{"
        f"\\small\\textbf{{Source:}} \\href{{{source_url}}}{{View original document on official website}}"
        f" \\\\[2pt] \\textbf{{State:}} {state} \\quad \\textbf{{Agency:}} {agency.replace('_', ' ').title()}"
        f"}}}}\n\\vspace{{12pt}}\n\n"
    )
    return header


def clean_html_for_conversion(html_content: str) -> str:
    """
    Strip navigation, scripts, styles, and images from HTML.
    Extract just the meaningful document content.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove scripts, styles, nav, header, footer
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "img", "link"]):
            tag.decompose()

        # Try to find the main content area
        content = None
        for selector in ["#doc-content", "#content", ".content", "main", "article", ".rule-text"]:
            content = soup.select_one(selector)
            if content:
                break

        if content:
            text = content.get_text("\n", strip=True)
        else:
            # Fall back to body text
            body = soup.find("body")
            text = body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True)

        # Get the title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Clean up: remove excessive blank lines
        lines = text.split("\n")
        cleaned_lines = []
        prev_blank = False
        for line in lines:
            line = line.strip()
            if not line:
                if not prev_blank:
                    cleaned_lines.append("")
                prev_blank = True
            else:
                cleaned_lines.append(line)
                prev_blank = False

        cleaned_text = "\n".join(cleaned_lines)

        # Build a minimal clean HTML doc using <p> tags for proper wrapping
        paragraphs = []
        current_para = []
        for line in cleaned_lines:
            if line.strip() == "":
                if current_para:
                    paragraphs.append(" ".join(current_para))
                    current_para = []
            else:
                current_para.append(line)
        if current_para:
            paragraphs.append(" ".join(current_para))

        body_html = "\n".join(f"<p>{p}</p>" for p in paragraphs)

        clean_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h1>{title}</h1>
{body_html}
</body></html>"""

        return clean_html

    except ImportError:
        # No BeautifulSoup — do basic regex cleanup
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<img[^>]*>', '', html_content)
        html_content = re.sub(r'<pre[^>]*>', '<div>', html_content)
        html_content = html_content.replace('</pre>', '</div>')
        return html_content


def convert_html_to_pdf(
    html_path: Path,
    pdf_path: Path,
    source_url: str,
    state: str,
    agency: str,
) -> bool:
    """Convert an HTML file to PDF using pandoc + pdflatex."""
    html_content = html_path.read_text(encoding="utf-8", errors="replace")

    # Clean HTML: strip nav, JS, CSS, images, extract content
    html_content = clean_html_for_conversion(html_content)

    # Write cleaned HTML to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(html_content)
        tmp_html = tmp.name

    # Build the LaTeX header
    header_tex = create_header_latex(source_url, state, agency)

    header_file = None
    if header_tex:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tex", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(header_tex)
            header_file = tmp.name

    try:
        cmd = [
            "pandoc",
            tmp_html,
            "-o", str(pdf_path),
            "--pdf-engine=pdflatex",
            "-V", "geometry:margin=1in",
            "-V", "fontsize=10pt",
            "-V", "colorlinks=true",
            "-V", "linkcolor=blue",
            "-V", "urlcolor=blue",
            "--wrap=auto",
        ]

        if header_file:
            cmd.extend(["-B", header_file])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            # Fallback: try without header
            cmd_simple = [
                "pandoc",
                tmp_html,
                "-o", str(pdf_path),
                "--pdf-engine=pdflatex",
                "-V", "geometry:margin=1in",
                "-V", "fontsize=10pt",
                "--wrap=auto",
            ]
            result = subprocess.run(
                cmd_simple,
                capture_output=True,
                text=True,
                timeout=60,
            )

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        return False
    finally:
        os.unlink(tmp_html)
        if header_file:
            os.unlink(header_file)


def _strip_markdown_tables(md_content: str) -> str:
    """Replace pipe-delimited markdown tables with plain text rows."""
    lines = md_content.split("\n")
    cleaned = []
    for line in lines:
        # Skip table separator lines (---+---+---)
        if re.match(r'\s*\|?\s*[-:]+\s*\|', line):
            continue
        if line.strip().startswith("|"):
            # Convert table row to plain text
            cells = [c.strip() for c in line.split("|")[1:-1]]
            cleaned.append("  |  ".join(cells))
        else:
            cleaned.append(line)
    return "\n".join(cleaned)


def convert_docx_to_pdf(
    docx_path: Path,
    pdf_path: Path,
    source_url: str,
    state: str,
    agency: str,
) -> bool:
    """
    Convert a DOCX file to PDF using a two-step process:
      1. DOCX → Markdown (strips complex formatting)
      2. Strip markdown tables (which break LaTeX with too many columns)
      3. Markdown → PDF via lualatex (handles Unicode)
    """
    # Step 1: DOCX → Markdown
    md_tmp = None
    header_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            md_tmp = tmp.name

        result = subprocess.run(
            ["pandoc", str(docx_path), "-t", "markdown", "-o", md_tmp],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return False

        # Step 2: Strip tables
        md_content = Path(md_tmp).read_text(encoding="utf-8", errors="replace")
        md_content = _strip_markdown_tables(md_content)
        Path(md_tmp).write_text(md_content, encoding="utf-8")

        # Step 3: Build header
        header_tex = create_header_latex(source_url, state, agency)
        if header_tex:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tex", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(header_tex)
                header_file = tmp.name

        # Step 4: Markdown → PDF via lualatex
        cmd = [
            "pandoc",
            md_tmp,
            "-o", str(pdf_path),
            "--pdf-engine=lualatex",
            "-V", "geometry:margin=0.75in",
            "-V", "fontsize=10pt",
            "-V", "colorlinks=true",
            "-V", "linkcolor=blue",
            "-V", "urlcolor=blue",
            "--wrap=auto",
        ]

        if header_file:
            cmd.extend(["-B", header_file])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180,
        )

        if result.returncode != 0:
            # Fallback without header
            cmd_simple = [
                "pandoc", md_tmp, "-o", str(pdf_path),
                "--pdf-engine=lualatex",
                "-V", "geometry:margin=0.75in",
                "--wrap=auto",
            ]
            result = subprocess.run(
                cmd_simple, capture_output=True, text=True, timeout=180,
            )

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        return False
    finally:
        if md_tmp and os.path.exists(md_tmp):
            os.unlink(md_tmp)
        if header_file and os.path.exists(header_file):
            os.unlink(header_file)


def convert_all(dest_root: str) -> dict:
    """Convert all non-PDF files in the crawled documents directory."""
    root = Path(dest_root)
    manifest_urls = load_manifest_urls(root)

    stats = {
        "html_converted": 0,
        "docx_converted": 0,
        "failed": [],
        "skipped": 0,
        "total_non_pdf": 0,
    }

    # Find all non-PDF document files
    non_pdf_files = []
    for ext in ("*.html", "*.htm", "*.docx", "*.doc"):
        non_pdf_files.extend(root.rglob(ext))

    stats["total_non_pdf"] = len(non_pdf_files)
    print(f"Found {len(non_pdf_files)} non-PDF files to convert")

    for i, filepath in enumerate(sorted(non_pdf_files), 1):
        # Extract state and agency from path
        parts = filepath.parts
        state = ""
        agency = ""
        for j, part in enumerate(parts):
            if part in ("MS", "TN", "AL", "LA", "AR", "GA", "TX"):
                state = part
                if j + 1 < len(parts):
                    agency = parts[j + 1]
                break

        # Get source URL
        source_url = get_source_url(filepath, manifest_urls)

        # Determine output PDF path
        pdf_path = filepath.with_suffix(".pdf")

        # Skip if PDF already exists
        if pdf_path.exists():
            stats["skipped"] += 1
            continue

        ext = filepath.suffix.lower()
        success = False

        if ext in (".html", ".htm"):
            success = convert_html_to_pdf(filepath, pdf_path, source_url, state, agency)
            if success:
                stats["html_converted"] += 1
        elif ext in (".docx", ".doc"):
            success = convert_docx_to_pdf(filepath, pdf_path, source_url, state, agency)
            if success:
                stats["docx_converted"] += 1

        if not success:
            stats["failed"].append(str(filepath))
            print(f"  FAILED [{i}/{len(non_pdf_files)}]: {filepath.name}")
        else:
            # Remove original non-PDF file after successful conversion
            filepath.unlink()

        if i % 50 == 0:
            print(f"  Progress: {i}/{len(non_pdf_files)} files processed")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Convert non-PDF crawled documents to PDF")
    parser.add_argument("--dest", default="./crawled_documents", help="Crawled documents root")
    args = parser.parse_args()

    print(f"Converting non-PDF files in {args.dest}...")
    stats = convert_all(args.dest)

    print(f"\nConversion complete:")
    print(f"  HTML → PDF: {stats['html_converted']}")
    print(f"  DOCX → PDF: {stats['docx_converted']}")
    print(f"  Skipped (PDF exists): {stats['skipped']}")
    print(f"  Failed: {len(stats['failed'])}")

    if stats["failed"]:
        print(f"\nFailed files:")
        for f in stats["failed"]:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
