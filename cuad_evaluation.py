r"""
==========================================================

WHAT THIS DOES
---------------
Runs JurisAI's REAL missing-clause detector (the actual Gemini-backed
function in risk_analysis/missing_clause_detector.py — not a simulation)
against a sample of real contracts from the CUAD dataset, compares its
output to CUAD's expert-annotated ground truth, and computes Precision,
Recall, F1, and Accuracy per clause category, plus overall.

This must run on YOUR machine, in YOUR JurisAI project folder, with YOUR
.env file present — it needs your real Gemini API key to call the real
detector. Nobody else can run this for you and have it mean anything.

SETUP (do this once)
---------------------
1. Download CUAD v1. The most reliable verified source is Hugging Face
   (the official atticusprojectai.org page links here too). Easiest method
   — run this once in your terminal (installs a small helper library and
   downloads the whole dataset, ~180MB, in one go):

       pip install huggingface_hub
       python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='theatticusproject/cuad', repo_type='dataset', local_dir='CUAD_v1_download')"

   (Alternative, no coding: search "Contract Understanding Atticus Dataset
   CUAD" on Kaggle and use the Download button there instead — needs a
   free Kaggle account.)

   Note: CUAD's real folder structure is NESTED, e.g.
   CUAD_v1/full_contract_pdf/Part_I/Co_Branding/SomeContract.pdf — you do
   NOT need to flatten it or reorganize anything; this script searches
   recursively through whatever folder you point it at.

2. Copy this script into your JurisAI project root (same folder as app.py),
   so it can import your real modules.

3. FIRST, run this to see CUAD's actual column names — do not skip this:

       python cuad_evaluation.py --show-columns "C:\path\to\CUAD_v1_download\master_clauses.csv"

   (the exact path depends on where snapshot_download or Kaggle placed it —
   look for a file literally named master_clauses.csv)

4. Open the CATEGORY_COLUMN_MAP dictionary below and edit it to match the
   REAL column names you just saw printed. Leave a category's list EMPTY if
   CUAD has no matching column for it (this is expected for at least
   Arbitration and Force Majeure — CUAD's 41 categories do not include an
   exact match for either, based on available documentation; if you find
   otherwise when you look at the real file, map it in).

5. THEN run the real evaluation:

       python cuad_evaluation.py --run --cuad-dir "C:\path\to\CUAD_v1_download" --n 10

   This will take a few minutes (10 contracts x 2 real Gemini calls each,
   with a short pause between calls to be polite to the API).

OUTPUT
------
Two CSV files are written next to this script:
  - cuad_eval_detailed_log.csv   (every single prediction vs. ground truth)
  - cuad_eval_summary_metrics.csv (Precision/Recall/F1/Accuracy per category)

And a summary table is printed to the console. Paste both the console
summary and the CSVs back to me and I'll write the real Results section
from your real numbers.
"""

import argparse
import csv
import os
import sys
import time

# ---------------------------------------------------------------------
# STEP 4 (see docstring above): EDIT THIS MAPPING AFTER YOU HAVE LOOKED
# AT THE REAL master_clauses.csv HEADER. Do not trust these as correct —
# they are unverified best-guesses and MUST be checked against the real
# file before you run --run.
# ---------------------------------------------------------------------
CATEGORY_COLUMN_MAP = {
    "Confidentiality Clause": ["Confidentiality"],          # VERIFY
    "Termination Clause": ["Termination For Convenience"],  # VERIFY
    "Liability Clause": ["Uncapped Liability", "Cap On Liability"],  # VERIFY — Present if EITHER has content
    "Indemnity Clause": ["Indemnification"],                # VERIFY — may not exist, check header
    "Arbitration Clause": [],                                # Likely no CUAD match — leave empty if confirmed absent
    "Force Majeure Clause": [],                              # Likely no CUAD match — leave empty if confirmed absent
}

FILENAME_COLUMN_CANDIDATES = ["Filename", "Document Name", "File Name", "filename"]


def show_columns(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    print(f"\nFound {len(header)} columns in {csv_path}:\n")
    for i, col in enumerate(header):
        print(f"  [{i}] {col}")
    print(
        "\nNow edit CATEGORY_COLUMN_MAP at the top of this script to use the "
        "EXACT column names shown above, then re-run with --run.\n"
    )


def load_ground_truth(csv_path, n, seed):
    import random

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    filename_col = None
    for cand in FILENAME_COLUMN_CANDIDATES:
        if rows and cand in rows[0]:
            filename_col = cand
            break
    if filename_col is None:
        print("ERROR: could not find a filename column. Available columns:")
        print(list(rows[0].keys()) if rows else "(no rows found)")
        sys.exit(1)

    random.seed(seed)
    sample = random.sample(rows, n) if len(rows) >= n else rows
    return sample, filename_col


def find_csv(cuad_dir):
    """Recursively locate master_clauses.csv anywhere under cuad_dir."""
    for root, _dirs, files in os.walk(cuad_dir):
        for f in files:
            if f.lower() == "master_clauses.csv":
                return os.path.join(root, f)
    return None


def find_pdf(cuad_dir, filename_hint):
    """
    Recursively match a CUAD ground-truth filename to an actual PDF
    anywhere under cuad_dir. CUAD's real download nests PDFs several
    folders deep (e.g. CUAD_v1/full_contract_pdf/Part_I/Co_Branding/...),
    so this cannot assume a flat directory.
    """
    hint_lower = filename_hint.lower().replace(".pdf", "")
    best_match = None
    for root, _dirs, files in os.walk(cuad_dir):
        for f in files:
            if not f.lower().endswith(".pdf"):
                continue
            f_lower = f.lower().replace(".pdf", "")
            if f_lower == hint_lower:
                return os.path.join(root, f)
            if best_match is None and hint_lower in f_lower:
                best_match = os.path.join(root, f)
    return best_match


def ground_truth_present(row, mapped_columns):
    if not mapped_columns:
        return None  # no CUAD equivalent — excluded from evaluation
    for col in mapped_columns:
        value = row.get(col, "")
        if value and value.strip() and value.strip().lower() not in ("no", "none", "n/a"):
            return "Present"
    return "Missing"


def run_evaluation(cuad_dir, n, seed):
    # Import JurisAI's REAL modules — this is what makes the result genuine.
    sys.path.insert(0, os.getcwd())
    try:
        from document_processing.file_extractor import extract_structured
        from risk_analysis.missing_clause_detector import detect_missing_clauses
    except ImportError as e:
        print(
            "ERROR: could not import JurisAI modules. Make sure this script "
            "is placed in your JurisAI project root (same folder as app.py) "
            "and that you're running it with the venv active.\n"
            f"Import error: {e}"
        )
        sys.exit(1)

    csv_path = find_csv(cuad_dir)
    if not csv_path:
        print(f"ERROR: could not find master_clauses.csv anywhere under {cuad_dir}")
        sys.exit(1)
    print(f"Found ground-truth CSV: {csv_path}")

    active_categories = {k: v for k, v in CATEGORY_COLUMN_MAP.items() if v}
    skipped_categories = [k for k, v in CATEGORY_COLUMN_MAP.items() if not v]
    if skipped_categories:
        print(f"NOTE: excluding from evaluation (no CUAD column mapped): {skipped_categories}\n")

    sample, filename_col = load_ground_truth(csv_path, n, seed)

    detailed_rows = []  # contract, category, jurisai_pred, ground_truth, result, extraction_sec, detection_sec

    for idx, row in enumerate(sample, start=1):
        filename_hint = row[filename_col]
        pdf_path = find_pdf(cuad_dir, filename_hint)
        if pdf_path is None:
            print(f"[{idx}/{len(sample)}] SKIP — could not locate PDF for '{filename_hint}'")
            continue

        print(f"[{idx}/{len(sample)}] Processing: {os.path.basename(pdf_path)}")

        # --- Real extraction (JurisAI's actual code) ---
        t0 = time.perf_counter()
        with open(pdf_path, "rb") as fh:
            import io
            class _Upload(io.BytesIO):
                pass
            data = fh.read()
            upload = _Upload(data)
            upload.name = os.path.basename(pdf_path)
            structured = extract_structured(upload)
        t1 = time.perf_counter()
        extraction_sec = round(t1 - t0, 2)

        # --- Real clause detection (JurisAI's actual Gemini-backed code) ---
        # Retries once after a pause if the call fails (e.g. a transient
        # rate-limit hiccup) rather than silently losing that contract's data.
        t2 = time.perf_counter()
        result = detect_missing_clauses(structured["full_text"])
        if result.get("error"):
            print("    Transient error on first attempt, waiting 30s and retrying once...")
            time.sleep(30)
            result = detect_missing_clauses(structured["full_text"])
        t3 = time.perf_counter()
        detection_sec = round(t3 - t2, 2)

        clause_lookup = {c["clause"]: c["present"] for c in result.get("clauses", [])}

        for category, mapped_cols in active_categories.items():
            gt = ground_truth_present(row, mapped_cols)
            if gt is None:
                continue
            jurisai_present = clause_lookup.get(category)
            if jurisai_present is None:
                print(f"    WARNING: JurisAI did not return a verdict for '{category}'")
                continue
            jurisai_pred = "Present" if jurisai_present else "Missing"

            if gt == "Present" and jurisai_pred == "Present":
                outcome = "TP"
            elif gt == "Present" and jurisai_pred == "Missing":
                outcome = "FN"
            elif gt == "Missing" and jurisai_pred == "Present":
                outcome = "FP"
            else:
                outcome = "TN"

            detailed_rows.append({
                "contract": os.path.basename(pdf_path),
                "category": category,
                "jurisai_prediction": jurisai_pred,
                "cuad_ground_truth": gt,
                "result": outcome,
                "extraction_sec": extraction_sec,
                "detection_sec": detection_sec,
            })

        time.sleep(2)  # be polite to the Gemini API between contracts

    # --- Write detailed log ---
    with open("cuad_eval_detailed_log.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "contract", "category", "jurisai_prediction", "cuad_ground_truth",
            "result", "extraction_sec", "detection_sec"
        ])
        writer.writeheader()
        writer.writerows(detailed_rows)

    # --- Compute and write summary metrics ---
    categories = list(active_categories.keys())
    summary = []
    totals = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}

    for cat in categories:
        counts = {"TP": 0, "FP": 0, "TN": 0, "FN": 0}
        for r in detailed_rows:
            if r["category"] == cat:
                counts[r["result"]] += 1
        for k in totals:
            totals[k] += counts[k]

        tp, fp, tn, fn = counts["TP"], counts["FP"], counts["TN"], counts["FN"]
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall) > 0) else None
        accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) else None

        summary.append({
            "category": cat, "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "precision": round(precision, 3) if precision is not None else "N/A",
            "recall": round(recall, 3) if recall is not None else "N/A",
            "f1": round(f1, 3) if f1 is not None else "N/A",
            "accuracy": round(accuracy, 3) if accuracy is not None else "N/A",
        })

    tp, fp, tn, fn = totals["TP"], totals["FP"], totals["TN"], totals["FN"]
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall) > 0) else None
    accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) else None
    summary.append({
        "category": "OVERALL (micro-avg)", "TP": tp, "FP": fp, "TN": tn, "FN": fn,
        "precision": round(precision, 3) if precision is not None else "N/A",
        "recall": round(recall, 3) if recall is not None else "N/A",
        "f1": round(f1, 3) if f1 is not None else "N/A",
        "accuracy": round(accuracy, 3) if accuracy is not None else "N/A",
    })

    with open("cuad_eval_summary_metrics.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "TP", "FP", "TN", "FN", "precision", "recall", "f1", "accuracy"])
        writer.writeheader()
        writer.writerows(summary)

    print("\n" + "=" * 78)
    print("RESULTS")
    print("=" * 78)
    header = f"{'Category':<24}{'TP':>4}{'FP':>4}{'TN':>4}{'FN':>4}{'Prec':>8}{'Recall':>8}{'F1':>8}{'Acc':>8}"
    print(header)
    print("-" * len(header))
    for s in summary:
        print(f"{s['category']:<24}{s['TP']:>4}{s['FP']:>4}{s['TN']:>4}{s['FN']:>4}"
              f"{str(s['precision']):>8}{str(s['recall']):>8}{str(s['f1']):>8}{str(s['accuracy']):>8}")
    print("\nSaved: cuad_eval_detailed_log.csv, cuad_eval_summary_metrics.csv")
    print("Paste both files (or their contents) back to Claude to write the real Results section.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate JurisAI's real clause detector against CUAD ground truth.")
    parser.add_argument("--show-columns", metavar="CSV_PATH", help="Print master_clauses.csv column names and exit.")
    parser.add_argument("--run", action="store_true", help="Run the real evaluation.")
    parser.add_argument("--cuad-dir", help="Path to the unzipped CUAD_v1 folder (containing master_clauses.csv and full_contracts_pdf/).")
    parser.add_argument("--n", type=int, default=10, help="Number of contracts to sample (default 10).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default 42).")
    args = parser.parse_args()

    if args.show_columns:
        show_columns(args.show_columns)
    elif args.run:
        if not args.cuad_dir:
            print("ERROR: --run requires --cuad-dir \"C:\\path\\to\\CUAD_v1\"")
            sys.exit(1)
        run_evaluation(args.cuad_dir, args.n, args.seed)
    else:
        parser.print_help()