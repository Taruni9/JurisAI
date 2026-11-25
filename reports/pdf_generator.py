import html
import os
import re
import uuid

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_reports")
os.makedirs(_OUTPUT_DIR, exist_ok=True)


def _sanitize_for_reportlab(text):
    """Clean and convert markdown/HTML formatting into ReportLab-compliant XML."""
    if not text:
        return ""
    text = str(text)

    # 1. Standardize <br> and <br/> to self-closing <br/>
    text = re.sub(r"<br\s*/?>", "<br/>", text, flags=re.IGNORECASE)

    # 2. Convert markdown bold **text** to <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # 3. Convert markdown italic *text* or _text_ to <i>text</i>
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", text)

    # 4. Escape standalone & characters (not part of valid entity like &amp; &lt; etc.)
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;)", "&amp;", text)

    # 5. Sanitize any tags not supported by ReportLab Paragraph (only <b>, <i>, <u>, <br/>, <font> allowed)
    allowed_tags = {"<b>", "</b>", "<i>", "</i>", "<u>", "</u>", "<br/>"}

    def _tag_repl(match):
        raw_tag = match.group(0)
        lower_tag = raw_tag.lower()
        if lower_tag in allowed_tags:
            return lower_tag
        return html.escape(raw_tag)

    text = re.sub(r"<[^>]+>", _tag_repl, text)
    return text


def _make_safe_paragraph(text, style):
    """Creates a Paragraph safely; if ReportLab parser fails, falls back to stripped plain text."""
    try:
        sanitized = _sanitize_for_reportlab(text)
        return Paragraph(sanitized, style)
    except Exception:
        # Ultimate fallback: strip all HTML/XML tags and safely escape
        clean = re.sub(r"<[^>]+>", "", str(text or ""))
        return Paragraph(html.escape(clean), style)


def _markdown_to_flowables(md_text, styles, cell_style=None, header_style=None):
    """Converts a multi-line markdown or plain text string into ReportLab flowables,
    supporting headers, bullet lists, body text, and markdown tables.
    """
    if not md_text:
        return [_make_safe_paragraph("Not generated for this session.", styles["BodyText"])]

    if cell_style is None:
        cell_style = ParagraphStyle(
            "TableCellFlowable",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1E293B"),
        )
    if header_style is None:
        header_style = ParagraphStyle(
            "TableHeaderFlowable",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.whitesmoke,
            fontName="Helvetica-Bold",
        )

    flowables = []
    lines = str(md_text).strip().split("\n")
    table_lines = []

    def _flush_table(tbl_lines):
        if not tbl_lines:
            return
        parsed_rows = []
        for raw_line in tbl_lines:
            trimmed = raw_line.strip()
            if trimmed.startswith("|"):
                trimmed = trimmed[1:]
            if trimmed.endswith("|"):
                trimmed = trimmed[:-1]
            cells = [c.strip() for c in trimmed.split("|")]
            # Skip divider rows like |---|---|
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                continue
            parsed_rows.append(cells)

        if not parsed_rows:
            return

        num_cols = max(len(r) for r in parsed_rows)
        # Printable width with 36pt margins on A4/Letter is ~520-540pt
        total_width = 520.0
        if num_cols == 2:
            col_widths = [160, 360]
        elif num_cols == 3:
            col_widths = [130, 195, 195]
        elif num_cols == 4:
            col_widths = [100, 140, 140, 140]
        else:
            col_widths = [total_width / num_cols] * num_cols

        table_data = []
        for row_idx, row in enumerate(parsed_rows):
            while len(row) < num_cols:
                row.append("")
            row_cells = []
            for col_idx, cell in enumerate(row):
                st = header_style if row_idx == 0 else cell_style
                row_cells.append(_make_safe_paragraph(cell, st))
            table_data.append(row_cells)

        table = Table(table_data, colWidths=col_widths)
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        flowables.append(table)
        flowables.append(Spacer(1, 10))

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if table_lines:
                _flush_table(table_lines)
                table_lines = []
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            table_lines.append(stripped)
            continue
        elif table_lines:
            _flush_table(table_lines)
            table_lines = []

        if stripped.startswith("### "):
            flowables.append(_make_safe_paragraph(stripped[4:], styles["Heading3"]))
            flowables.append(Spacer(1, 4))
        elif stripped.startswith("## "):
            flowables.append(_make_safe_paragraph(stripped[3:], styles["Heading2"]))
            flowables.append(Spacer(1, 6))
        elif stripped.startswith("# "):
            flowables.append(_make_safe_paragraph(stripped[2:], styles["Heading1"]))
            flowables.append(Spacer(1, 8))
        elif re.match(r"^(\*|-|•|\d+\.)\s+", stripped):
            flowables.append(_make_safe_paragraph(stripped, styles["BodyText"]))
            flowables.append(Spacer(1, 3))
        else:
            flowables.append(_make_safe_paragraph(stripped, styles["BodyText"]))
            flowables.append(Spacer(1, 6))

    if table_lines:
        _flush_table(table_lines)

    return flowables


def generate_pdf(
    filename,
    explanation,
    risk_data,
    clause_data,
    comparison_report,
    qa_history,
):
    """
    Generates a professional legal intelligence PDF report with full support
    for markdown formatting, tables, risk scores, and Q&A citations.
    """
    output_path = os.path.join(_OUTPUT_DIR, f"JurisAI_Report_{uuid.uuid4().hex[:8]}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B"),
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.whitesmoke,
        fontName="Helvetica-Bold",
    )

    story = []

    # Title & Metadata
    story.append(_make_safe_paragraph("Legal Document Intelligence Report", styles["Title"]))
    if filename:
        story.append(_make_safe_paragraph(f"Source document: <b>{filename}</b>", styles["Normal"]))
    story.append(Spacer(1, 15))

    # ---------------- 1. Contract Summary ----------------
    story.append(_make_safe_paragraph("1. Contract Summary", styles["Heading2"]))
    story.append(Spacer(1, 4))
    if explanation:
        story.extend(_markdown_to_flowables(explanation, styles))
    else:
        story.append(_make_safe_paragraph("Not generated for this session.", styles["BodyText"]))
    story.append(Spacer(1, 15))

    # ---------------- 2. Risk Analysis ----------------
    story.append(_make_safe_paragraph("2. Risk Analysis", styles["Heading2"]))
    story.append(Spacer(1, 4))

    if risk_data and not risk_data.get("error"):
        summary_table_data = [
            [_make_safe_paragraph("<b>Risk Score</b>", styles["Normal"]), _make_safe_paragraph(f"<b>{risk_data.get('risk_score', 'N/A')}/100</b>", styles["Normal"])],
            [_make_safe_paragraph("<b>Risk Level</b>", styles["Normal"]), _make_safe_paragraph(str(risk_data.get("risk_level", "N/A")), styles["Normal"])],
            [_make_safe_paragraph("<b>Confidence</b>", styles["Normal"]), _make_safe_paragraph(f"{risk_data.get('confidence', 'N/A')}%", styles["Normal"])],
        ]
        table = Table(summary_table_data, colWidths=[160, 360])
        table.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(table)
        story.append(Spacer(1, 10))

        breakdown = risk_data.get("breakdown", {})
        if breakdown:
            story.append(_make_safe_paragraph("Risk Breakdown by Dimension", styles["Heading3"]))
            story.append(Spacer(1, 4))
            breakdown_rows = [
                [_make_safe_paragraph("Dimension", table_header_style), _make_safe_paragraph("Score", table_header_style)]
            ]
            for key, value in breakdown.items():
                if value is None:
                    continue
                breakdown_rows.append([
                    _make_safe_paragraph(key.replace("_", " ").title(), table_cell_style),
                    _make_safe_paragraph(f"{value}/100", table_cell_style),
                ])
            breakdown_table = Table(breakdown_rows, colWidths=[360, 160])
            breakdown_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(breakdown_table)
            story.append(Spacer(1, 10))

        if risk_data.get("major_risks"):
            story.append(_make_safe_paragraph("Major Risks", styles["Heading3"]))
            story.append(Spacer(1, 4))
            for risk in risk_data["major_risks"]:
                story.append(_make_safe_paragraph(f"• {risk}", styles["BodyText"]))
                story.append(Spacer(1, 2))
            story.append(Spacer(1, 8))

        if risk_data.get("recommendations"):
            story.append(_make_safe_paragraph("Recommendations", styles["Heading3"]))
            story.append(Spacer(1, 4))
            for rec in risk_data["recommendations"]:
                story.append(_make_safe_paragraph(f"• {rec}", styles["BodyText"]))
                story.append(Spacer(1, 2))
            story.append(Spacer(1, 8))

        if risk_data.get("narrative"):
            story.append(_make_safe_paragraph("Narrative Summary", styles["Heading3"]))
            story.append(Spacer(1, 4))
            story.extend(_markdown_to_flowables(risk_data["narrative"], styles))
    else:
        story.append(_make_safe_paragraph("Not generated for this session.", styles["BodyText"]))

    story.append(Spacer(1, 15))

    # ---------------- 3. Missing Clause Detection ----------------
    story.append(_make_safe_paragraph("3. Missing Clause Detection", styles["Heading2"]))
    story.append(Spacer(1, 4))

    if clause_data and clause_data.get("clauses"):
        rows = [
            [
                _make_safe_paragraph("Clause", table_header_style),
                _make_safe_paragraph("Status", table_header_style),
                _make_safe_paragraph("Risk If Missing", table_header_style),
            ]
        ]
        for item in clause_data["clauses"]:
            status_text = "Present" if item.get("present") else "Missing"
            status_color = "#16A34A" if item.get("present") else "#DC2626"
            rows.append([
                _make_safe_paragraph(item.get("clause", ""), table_cell_style),
                _make_safe_paragraph(f"<font color='{status_color}'><b>{status_text}</b></font>", table_cell_style),
                _make_safe_paragraph(item.get("risk_if_missing", "") or "-", table_cell_style),
            ])
        clause_table = Table(rows, colWidths=[150, 70, 300])
        clause_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(clause_table)
    else:
        story.append(_make_safe_paragraph("Not generated for this session.", styles["BodyText"]))

    story.append(Spacer(1, 15))

    # ---------------- 4. Contract Comparison ----------------
    story.append(_make_safe_paragraph("4. Contract Comparison", styles["Heading2"]))
    story.append(Spacer(1, 4))
    if comparison_report:
        story.extend(_markdown_to_flowables(comparison_report, styles))
    else:
        story.append(_make_safe_paragraph("Not generated for this session.", styles["BodyText"]))

    story.append(Spacer(1, 15))

    # ---------------- 5. Question & Answer History ----------------
    story.append(_make_safe_paragraph("5. Question & Answer History", styles["Heading2"]))
    story.append(Spacer(1, 4))

    if qa_history:
        for idx, entry in enumerate(qa_history, 1):
            story.append(_make_safe_paragraph(f"<b>Q{idx}: {entry.get('question', '')}</b>", styles["Heading3"]))
            story.append(Spacer(1, 3))
            ans_flowables = _markdown_to_flowables(entry.get("answer", ""), styles)
            story.extend(ans_flowables)

            sources = entry.get("sources", [])
            if sources:
                source_lines = [
                    f"{s.get('filename', 'doc')} — Page {s.get('page', 1)}, Paragraph {s.get('paragraph', 1)}"
                    for s in sources
                ]
                story.append(
                    _make_safe_paragraph(f"<i>Sources: {'; '.join(source_lines)}</i>", styles["Italic"])
                )
            story.append(Spacer(1, 8))
    else:
        story.append(_make_safe_paragraph("Not generated for this session.", styles["BodyText"]))

    doc.build(story)
    return output_path
