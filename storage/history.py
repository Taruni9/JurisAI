"""
Document + report history, and simple admin-facing aggregate stats.
"""

from storage.database import get_connection


def save_document(doc_id, user_id, filename, used_ocr=False):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO documents (id, user_id, filename, used_ocr) VALUES (?, ?, ?, ?)",
        (doc_id, user_id, filename, int(used_ocr)),
    )
    conn.commit()
    conn.close()


def save_report(user_id, document_id, report_type, pdf_path=None, summary=None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO reports (user_id, document_id, report_type, pdf_path, summary)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, document_id, report_type, pdf_path, summary),
    )
    conn.commit()
    conn.close()


def get_user_documents(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_reports(user_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT reports.*, documents.filename AS document_filename
           FROM reports
           LEFT JOIN documents ON reports.document_id = documents.id
           WHERE reports.user_id = ?
           ORDER BY reports.created_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_documents():
    conn = get_connection()
    rows = conn.execute(
        """SELECT documents.*, users.username
           FROM documents
           JOIN users ON documents.user_id = users.id
           ORDER BY documents.created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_reports():
    conn = get_connection()
    rows = conn.execute(
        """SELECT reports.*, users.username
           FROM reports
           JOIN users ON reports.user_id = users.id
           ORDER BY reports.created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_risk_analysis(user_id, document_id, risk_score, risk_level):
    conn = get_connection()
    conn.execute(
        "INSERT INTO analysis_log (user_id, document_id, risk_score, risk_level) VALUES (?, ?, ?, ?)",
        (user_id, document_id, risk_score, risk_level),
    )
    conn.commit()
    conn.close()


def get_risk_history(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM analysis_log WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_admin_stats():
    conn = get_connection()
    user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    doc_count = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
    report_count = conn.execute("SELECT COUNT(*) AS c FROM reports").fetchone()["c"]
    conn.close()
    return {"users": user_count, "documents": doc_count, "reports": report_count}
