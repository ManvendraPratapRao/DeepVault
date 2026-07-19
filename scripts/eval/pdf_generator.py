import logging
from pathlib import Path

import markdown
from xhtml2pdf import pisa

from scripts.eval.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

DOCS_BENCHMARKS_DIR = PROJECT_ROOT / "docs" / "benchmarks"

DARK_MODE_CSS = """
@page {
    size: a4 portrait;
    margin: 2cm;
    @frame header_frame {
        -pdf-frame-content: header_content;
        left: 50pt; width: 512pt; top: 50pt; height: 40pt;
    }
    @frame footer_frame {
        -pdf-frame-content: footer_content;
        left: 50pt; width: 512pt; top: 772pt; height: 20pt;
    }
}

body {
    background-color: #161b22;
    color: #e6edf3;
    font-family: Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
}

h1, h2, h3, h4, h5, h6 {
    color: #58a6ff;
    margin-top: 24px;
    margin-bottom: 16px;
    font-weight: 600;
}

h1 {
    font-size: 2em;
    border-bottom: 1px solid #30363d;
    padding-bottom: 0.3em;
}

h2 {
    font-size: 1.5em;
    border-bottom: 1px solid #30363d;
    padding-bottom: 0.3em;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 1em;
}

th, td {
    padding: 8px 13px;
    border: 1px solid #30363d;
}

th {
    background-color: #21262d;
    font-weight: bold;
    color: #e6edf3;
}

tr:nth-child(even) {
    background-color: #1c2128;
}

code {
    background-color: rgba(110, 118, 129, 0.4);
    padding: 0.2em 0.4em;
    border-radius: 6px;
    font-family: monospace;
    font-size: 85%;
}

a {
    color: #58a6ff;
    text-decoration: none;
}
"""


def generate_pdf_from_markdown(run_id: str) -> Path:
    """Reads the generated Markdown report and converts it into a styled dark-mode PDF."""
    md_path = DOCS_BENCHMARKS_DIR / f"{run_id}.md"
    pdf_path = DOCS_BENCHMARKS_DIR / f"{run_id}.pdf"

    if not md_path.exists():
        raise FileNotFoundError(f"Markdown report not found for run_id: {run_id}")

    with open(md_path, encoding="utf-8") as f:
        md_content = f.read()

    # Convert MD to HTML (with tables support)
    html_body = markdown.markdown(md_content, extensions=["tables"])

    # Wrap in HTML structure
    html_content = f"""
    <html>
    <head>
        <style>
            {DARK_MODE_CSS}
        </style>
    </head>
    <body>
        <div id="header_content">DeepVault Evaluation Engine</div>
        <div id="footer_content">Generated automatically <pdf:pagenumber></div>
        
        {html_body}
    </body>
    </html>
    """

    # Render PDF
    with open(pdf_path, "wb") as f:
        pisa_status = pisa.CreatePDF(html_content, dest=f)

    if pisa_status.err:
        logger.error(f"Failed to generate PDF for {run_id}: {pisa_status.err}")
        raise RuntimeError("PDF generation failed.")

    logger.info(f"Generated PDF report at {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_id = sys.argv[1]
        try:
            pdf_path = generate_pdf_from_markdown(run_id)
            print(f"Success: {pdf_path}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python -m scripts.eval.pdf_generator <run_id>")
