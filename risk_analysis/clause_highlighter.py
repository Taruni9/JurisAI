"""
Clause highlighting: given the extracted contract text and the clause
checklist from missing_clause_detector, locate the paragraph(s) most likely
to correspond to each *present* clause and produce an HTML preview with
those paragraphs highlighted, plus a simple checklist.
"""

import html
import re

# Keyword hints used to locate a clause's likely paragraph inside the text.
CLAUSE_KEYWORDS = {
    "Confidentiality Clause": ["confidential", "non-disclosure", "nda"],
    "Termination Clause": ["terminat", "notice period", "cancellation"],
    "Liability Clause": ["liability", "liable", "limitation of liability"],
    "Indemnity Clause": ["indemnif", "indemnity", "hold harmless"],
    "Arbitration Clause": ["arbitration", "dispute resolution", "arbitrator"],
    "Force Majeure Clause": ["force majeure", "act of god", "unforeseeable"],
}


def build_checklist(clause_results):
    """
    Simple ✔ / ✘ checklist for display, e.g.:
        Confidentiality ✔
        Termination ✔
        Governing Law ✘
    """
    checklist = []
    for item in clause_results:
        short_name = item["clause"].replace(" Clause", "")
        mark = "✔" if item["present"] else "✘"
        checklist.append(f"{short_name} {mark}")
    return checklist


def highlight_clauses_in_text(full_text, clause_results):
    """
    Returns HTML-safe text with paragraphs matching a *present* clause
    wrapped in a highlighted <mark> span labeled with the clause name.
    Paragraphs are split on blank lines to roughly match how clauses are
    extracted elsewhere in the app.
    """
    present_clauses = [c["clause"] for c in clause_results if c["present"]]

    paragraphs = [p for p in re.split(r"\n\s*\n", full_text) if p.strip()]
    if not paragraphs:
        paragraphs = [full_text]

    rendered = []
    for paragraph in paragraphs:
        escaped = html.escape(paragraph).replace("\n", "<br>")
        matched_clause = None

        lower_para = paragraph.lower()
        for clause in present_clauses:
            keywords = CLAUSE_KEYWORDS.get(clause, [])
            if any(kw in lower_para for kw in keywords):
                matched_clause = clause
                break

        if matched_clause:
            label = matched_clause.replace(" Clause", "")
            rendered.append(
                f'<div style="background:#FEF3C7;border-left:4px solid #D97706;'
                f'padding:8px 12px;margin-bottom:10px;border-radius:4px;">'
                f'<span style="font-size:12px;font-weight:600;color:#92400E;">'
                f'{html.escape(label)}</span><br>{escaped}</div>'
            )
        else:
            rendered.append(f'<p style="margin-bottom:10px;">{escaped}</p>')

    return "".join(rendered)
