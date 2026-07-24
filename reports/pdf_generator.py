import os
import uuid

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_reports")
os.makedirs(_OUTPUT_DIR, exist_ok=True)


def _safe_text(value):
    if not value:
        return "Not generated for this session."
    return str(value)


def generate_pdf(
    filename,
    explanation,
    risk_data,
    clause_data,
    comparison_report,
    qa_history,
):
    """
    filename: the source contract's filename (for the report title)
    explanation: plain text
    risk_data: dict returned by risk_analyzer.analyze_risk (or None)
    clause_data: dict returned by missing_clause_detector.detect_missing_clauses (or None)
    comparison_report: plain text (or None)
    qa_history: list of {"question", "answer", "sources": [{"filename","page","paragraph"}]}
    """
    output_path = os.path.join(_OUTPUT_DIR, f"JurisAI_Report_{uuid.uuid4().hex[:8]}.pdf")

    doc = SimpleDocTemplate(output_path)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Legal Document Intelligence Report", styles["Title"]))
    if filename:
        story.append(Paragraph(f"Source document: {filename}", styles["Normal"]))
    story.append(Spacer(1, 20))

    # ---------------- Contract Summary ----------------
    story.append(Paragraph("Contract Summary", styles["Heading2"]))
    story.append(Paragraph(_safe_text(explanation), styles["BodyText"]))
    story.append(Spacer(1, 20))

    # ---------------- Risk Analysis ----------------
    story.append(Paragraph("Risk Analysis", styles["Heading2"]))

    if risk_data and not risk_data.get("error"):
        summary_table_data = [
            ["Risk Score", f"{risk_data.get('risk_score', 'N/A')}/100"],
            ["Risk Level", risk_data.get("risk_level", "N/A")],
            ["Confidence", f"{risk_data.get('confidence', 'N/A')}%"],
        ]
        table = Table(summary_table_data, colWidths=[150, 300])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ]))
        story.append(table)
        story.append(Spacer(1, 10))

        breakdown = risk_data.get("breakdown", {})
        if breakdown:
            story.append(Paragraph("Risk Breakdown", styles["Heading3"]))
            breakdown_rows = [["Dimension", "Score"]]
            for key, value in breakdown.items():
                if value is None:
                    continue
                breakdown_rows.append([key.replace("_", " ").title(), f"{value}/100"])
            breakdown_table = Table(breakdown_rows, colWidths=[250, 100])
            breakdown_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]))
            story.append(breakdown_table)
            story.append(Spacer(1, 10))

        if risk_data.get("major_risks"):
            story.append(Paragraph("Major Risks", styles["Heading3"]))
            for risk in risk_data["major_risks"]:
                story.append(Paragraph(f"• {risk}", styles["BodyText"]))
            story.append(Spacer(1, 10))

        if risk_data.get("recommendations"):
            story.append(Paragraph("Recommendations", styles["Heading3"]))
            for rec in risk_data["recommendations"]:
                story.append(Paragraph(f"• {rec}", styles["BodyText"]))
            story.append(Spacer(1, 10))

        if risk_data.get("narrative"):
            story.append(Paragraph("Narrative Summary", styles["Heading3"]))
            story.append(Paragraph(_safe_text(risk_data["narrative"]), styles["BodyText"]))
    else:
        story.append(Paragraph("Not generated for this session.", styles["BodyText"]))

    story.append(Spacer(1, 20))

    # ---------------- Missing Clause Detection ----------------
    story.append(Paragraph("Missing Clause Detection", styles["Heading2"]))

    if clause_data and clause_data.get("clauses"):
        rows = [["Clause", "Status", "Risk If Missing"]]
        for item in clause_data["clauses"]:
            status = "Present" if item["present"] else "Missing"
            rows.append([item["clause"], status, item.get("risk_if_missing", "") or "-"])
        clause_table = Table(rows, colWidths=[150, 80, 220])
        clause_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ]))
        story.append(clause_table)
    else:
        story.append(Paragraph("Not generated for this session.", styles["BodyText"]))

    story.append(Spacer(1, 20))

    # ---------------- Contract Comparison ----------------
    story.append(Paragraph("Contract Comparison", styles["Heading2"]))
    story.append(Paragraph(_safe_text(comparison_report), styles["BodyText"]))
    story.append(Spacer(1, 20))

    # ---------------- Chat / Q&A History (with citations) ----------------
    story.append(Paragraph("Question & Answer History", styles["Heading2"]))

    if qa_history:
        for entry in qa_history:
            story.append(Paragraph(f"Q: {entry['question']}", styles["Heading3"]))
            story.append(Paragraph(entry["answer"], styles["BodyText"]))

            sources = entry.get("sources", [])
            if sources:
                source_lines = [
                    f"{s['filename']} — Page {s['page']}, Paragraph {s['paragraph']}"
                    for s in sources
                ]
                story.append(Paragraph("Sources: " + "; ".join(source_lines), styles["Italic"]))
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("Not generated for this session.", styles["BodyText"]))

    doc.build(story)

    return output_path
