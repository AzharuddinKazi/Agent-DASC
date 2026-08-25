"""Converts a finished DS-STAR+ report (the JSON writer.py produces — see that module's
_PROMPT_TAIL for the schema, and ReportView.jsx for the frontend's own reading of the same
shape) into a real downloadable .docx file. Exists because the app's only prior "export"
for report mode was a client-side `window.print()` (ReportView.jsx) — not a generated file
at all, just the browser's own print dialog, unusable from a script/API caller and
dependent on the browser's print-to-PDF renderer for formatting.

python-docx is already a dependency (knowledge.py reads uploaded .docx files with it) —
this is the same library used the other direction, generating rather than parsing.
"""

import io
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

# Splits on **bold** and `code` spans, keeping the delimiters so the loop below can tell
# a formatted span from plain text by which capture group matched. Matches writer.py's
# own documented markdown subset (WRITER prompt: "Use markdown for emphasis: **bold** for
# key entities, `code` for metric names") — deliberately not a general markdown parser,
# since that's the entire vocabulary the writer prompt asks the model to use.
_MARKDOWN_SPAN = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def _add_markdown_runs(paragraph, text: str) -> None:
    """Appends `text` to `paragraph` as one or more runs, translating **bold** and
    `code` spans into real run formatting instead of leaving the markdown punctuation
    in the visible text."""
    for chunk in _MARKDOWN_SPAN.split(text):
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**") and len(chunk) > 4:
            paragraph.add_run(chunk[2:-2]).bold = True
        elif chunk.startswith("`") and chunk.endswith("`") and len(chunk) > 2:
            run = paragraph.add_run(chunk[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(10)
        else:
            paragraph.add_run(chunk)


def _add_body_paragraphs(doc: Document, body: str) -> None:
    """Section bodies are the writer's own free-text, blank-line-separated paragraphs
    (see writer.py's _PROMPT_TAIL) — split on those rather than treating the whole body
    as one paragraph, so a multi-paragraph section actually renders as one."""
    for para_text in re.split(r"\n\s*\n", body.strip()):
        para_text = para_text.strip()
        if not para_text:
            continue
        p = doc.add_paragraph()
        _add_markdown_runs(p, para_text)


def build_report_docx(report: dict, query: str) -> bytes:
    """Builds a .docx from a parsed report dict (already `json.loads`-ed by the caller —
    this function assumes a valid dict, doesn't itself handle a malformed/unparseable
    report; the caller decides what to do with those, same as ReportView.jsx's own
    "Report could not be parsed" fallback)."""
    doc = Document()

    title = report.get("title") or query
    doc.add_heading(title, level=0)

    if report.get("classification"):
        p = doc.add_paragraph()
        run = p.add_run(report["classification"].upper())
        run.bold = True
        run.font.color.rgb = RGBColor(0xB0, 0x00, 0x00)
        run.font.size = Pt(10)

    if report.get("reporting_period"):
        p = doc.add_paragraph()
        p.add_run(report["reporting_period"]).italic = True

    coverage = report.get("data_coverage") or {}
    if coverage:
        parts = []
        if coverage.get("sub_questions_answered") is not None:
            parts.append(f"{coverage['sub_questions_answered']} sub-questions answered")
        if coverage.get("total_records_analysed") is not None:
            parts.append(f"{coverage['total_records_analysed']:,} records analysed")
        if coverage.get("datasets_used"):
            parts.append(f"Datasets: {', '.join(coverage['datasets_used'])}")
        if parts:
            p = doc.add_paragraph(" · ".join(parts))
            p.runs[0].font.size = Pt(9)
            p.runs[0].font.color.rgb = RGBColor(0x60, 0x60, 0x60)

    if report.get("executive_summary"):
        doc.add_heading("Executive Summary", level=1)
        p = doc.add_paragraph()
        _add_markdown_runs(p, report["executive_summary"])

    for section in report.get("sections") or []:
        doc.add_heading(section.get("heading") or "", level=1)
        _add_body_paragraphs(doc, section.get("body") or "")
        if section.get("key_stat"):
            p = doc.add_paragraph()
            run = p.add_run(f"Key stat: {section['key_stat']}")
            run.italic = True
            run.font.size = Pt(9.5)

    risk_matrix = report.get("risk_matrix") or []
    if risk_matrix:
        doc.add_heading("Risk Matrix", level=1)
        # Dimension names are the writer's own choice per report (see writer.py's
        # _PROMPT_TAIL point 6 — "identify 2-4 evaluative dimensions most relevant to
        # this query"), not a fixed schema — read them from the data itself rather than
        # hardcoding column names, same as ReportView.jsx's own rendering does.
        dimension_names = list(risk_matrix[0].get("dimensions", {}).keys())
        headers = ["Entity", *dimension_names, "Overall", "Priority Action"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Light Grid Accent 1"
        for cell, header in zip(table.rows[0].cells, headers):
            cell.paragraphs[0].add_run(header).bold = True
        for row in risk_matrix:
            cells = table.add_row().cells
            cells[0].text = str(row.get("entity", ""))
            dims = row.get("dimensions", {})
            for i, name in enumerate(dimension_names):
                cells[1 + i].text = str(dims.get(name, ""))
            cells[1 + len(dimension_names)].text = str(row.get("overall", ""))
            cells[2 + len(dimension_names)].text = str(row.get("priority_action", ""))

    if report.get("conclusions"):
        doc.add_heading("Conclusions", level=1)
        p = doc.add_paragraph()
        _add_markdown_runs(p, report["conclusions"])

    recommendations = report.get("recommendations") or []
    if recommendations:
        doc.add_heading("Recommendations", level=1)
        for rec in recommendations:
            p = doc.add_paragraph(style="List Bullet")
            _add_markdown_runs(p, rec)

    sources = report.get("sources") or []
    if sources:
        doc.add_heading("Sources", level=1)
        for src in sources:
            p = doc.add_paragraph()
            p.add_run(f"[{src.get('id', '?')}] ").bold = True
            p.add_run(src.get("question", ""))
            if src.get("summary"):
                sp = doc.add_paragraph()
                sp.paragraph_format.left_indent = Pt(18)
                run = sp.add_run(src["summary"])
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0x50, 0x50, 0x50)

    footer = doc.sections[0].footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer_p.add_run("Generated by DS-STAR — AI-powered data analysis")
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = RGBColor(0x90, 0x90, 0x90)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
