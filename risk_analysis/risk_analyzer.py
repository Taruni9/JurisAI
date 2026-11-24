import json
import re

from backend.gemini_helper import invoke_llm
from risk_analysis.missing_clause_detector import detect_missing_clauses, CLAUSES

WEIGHTS = {
    "missing_clauses": 0.30,
    "ambiguous_wording": 0.25,
    "liability_terms": 0.25,
    "payment_terms": 0.20,
}


def _extract_json(raw_text):
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return json.loads(match.group(0))


def _missing_clause_score(clause_results):
    """Rule-based component: what fraction of expected clauses are missing."""
    if not clause_results:
        return None
    total = len(clause_results)
    missing = sum(1 for c in clause_results if not c["present"])
    return round((missing / total) * 100)


def _risk_level(score):
    if score < 40:
        return "Low"
    if score < 70:
        return "Medium"
    return "High"


def analyze_risk(text, clause_results=None):
    """
    Structured risk scoring combining:
      - Missing clauses (rule-based, from the clause checklist)
      - Ambiguous wording (LLM-assessed)
      - Liability terms (LLM-assessed)
      - Payment terms (LLM-assessed)
      - Overall LLM reasoning

    Returns a dict:
        {
            "risk_score": int (0-100),
            "risk_level": "Low"/"Medium"/"High",
            "confidence": int (0-100),
            "breakdown": {
                "missing_clauses": int or None,
                "ambiguous_wording": int,
                "liability_terms": int,
                "payment_terms": int,
            },
            "major_risks": [str, ...],
            "recommendations": [str, ...],
            "narrative": str,
            "error": bool
        }
    """
    if clause_results is None:
        clause_data = detect_missing_clauses(text)
        clause_results = clause_data.get("clauses", [])

    missing_score = _missing_clause_score(clause_results)

    prompt = f"""
You are a legal risk analyst. Analyze the contract below and score these
four risk dimensions from 0 (no risk) to 100 (severe risk):

1. ambiguous_wording — vague, unclear, or open-to-interpretation language
2. liability_terms — how one-sided or unfavorable liability terms are
3. payment_terms — how risky or unclear payment obligations/terms are

Also give an overall confidence (0-100) in your own assessment based on how
complete and unambiguous the contract text is, a list of major_risks
(short strings), a list of recommendations (short strings), and a short
narrative summary.

Respond with ONLY a JSON object (no markdown fences, no commentary) in
exactly this shape:

{{
  "ambiguous_wording": <int>,
  "liability_terms": <int>,
  "payment_terms": <int>,
  "confidence": <int>,
  "major_risks": ["...", "..."],
  "recommendations": ["...", "..."],
  "narrative": "..."
}}

Contract:

{text}
"""

    try:
        raw = invoke_llm(prompt)
        parsed = _extract_json(raw)
    except Exception as e:
        return {
            "risk_score": "N/A",
            "risk_level": "N/A",
            "confidence": "N/A",
            "breakdown": {},
            "major_risks": [],
            "recommendations": [],
            "narrative": f"""
❌ Unable to perform risk analysis.

Reason:

{str(e)}

Please wait for a minute and try again.
""",
            "error": True,
        }

    ambiguous = int(parsed.get("ambiguous_wording", 50))
    liability = int(parsed.get("liability_terms", 50))
    payment = int(parsed.get("payment_terms", 50))
    confidence = int(parsed.get("confidence", 75))

    # If we have no rule-based missing-clause data, redistribute its weight
    # across the LLM-scored dimensions instead of assuming zero risk.
    if missing_score is None:
        remaining_weight = (
            WEIGHTS["ambiguous_wording"]
            + WEIGHTS["liability_terms"]
            + WEIGHTS["payment_terms"]
        )
        overall = (
            WEIGHTS["ambiguous_wording"] / remaining_weight * ambiguous
            + WEIGHTS["liability_terms"] / remaining_weight * liability
            + WEIGHTS["payment_terms"] / remaining_weight * payment
        )
    else:
        overall = (
            WEIGHTS["missing_clauses"] * missing_score
            + WEIGHTS["ambiguous_wording"] * ambiguous
            + WEIGHTS["liability_terms"] * liability
            + WEIGHTS["payment_terms"] * payment
        )

    overall_score = round(overall)

    return {
        "risk_score": overall_score,
        "risk_level": _risk_level(overall_score),
        "confidence": confidence,
        "breakdown": {
            "missing_clauses": missing_score,
            "ambiguous_wording": ambiguous,
            "liability_terms": liability,
            "payment_terms": payment,
        },
        "major_risks": parsed.get("major_risks", []),
        "recommendations": parsed.get("recommendations", []),
        "narrative": parsed.get("narrative", ""),
        "error": False,
    }
