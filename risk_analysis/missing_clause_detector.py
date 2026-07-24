import json
import re

from backend.gemini_helper import llm

CLAUSES = [
    "Confidentiality Clause",
    "Termination Clause",
    "Liability Clause",
    "Indemnity Clause",
    "Arbitration Clause",
    "Force Majeure Clause",
]


def _extract_json(raw_text):
    """Pull a JSON array out of a model response, tolerating stray text/fences."""
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in model response.")
    return json.loads(match.group(0))


def detect_missing_clauses(text):
    """
    Returns a dict:
        {
            "clauses": [
                {
                    "clause": "Confidentiality Clause",
                    "present": true/false,
                    "importance": "...",
                    "risk_if_missing": "...",
                    "recommendation": "..."
                },
                ...
            ],
            "raw_text": "<human readable fallback>"
        }
    """
    prompt = f"""
You are an expert legal analyst.

Analyze the following contract and determine whether each of these clauses is present:

{json.dumps(CLAUSES, indent=2)}

Respond with ONLY a JSON array (no markdown fences, no commentary), where each
element has this exact shape:

{{
  "clause": "<clause name>",
  "present": true or false,
  "importance": "<why this clause matters>",
  "risk_if_missing": "<risk if it is missing, empty string if present>",
  "recommendation": "<recommendation, empty string if present>"
}}

Contract:

{text}
"""

    try:
        response = llm.invoke(prompt)
        raw = response.content
    except Exception as e:
        return {
            "clauses": [],
            "raw_text": f"""
❌ Unable to detect missing clauses.

Reason:

{str(e)}

Please wait for a minute and try again.
""",
            "error": True,
        }

    try:
        parsed = _extract_json(raw)
        # Normalize to guarantee all expected keys exist
        clauses = []
        for item in parsed:
            clauses.append({
                "clause": item.get("clause", "Unknown Clause"),
                "present": bool(item.get("present", False)),
                "importance": item.get("importance", ""),
                "risk_if_missing": item.get("risk_if_missing", ""),
                "recommendation": item.get("recommendation", ""),
            })
        return {"clauses": clauses, "raw_text": raw, "error": False}
    except Exception:
        # Model didn't return clean JSON — fall back to showing raw text
        return {"clauses": [], "raw_text": raw, "error": False}
