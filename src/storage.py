"""
storage.py
==========
SQLite persistence layer for the Contract & Legal Document Risk Analyzer.

Tables:
    users        -> authentication + role (user/admin)
    documents    -> uploaded document metadata + extracted text
    analyses     -> AI analysis results (JSON blobs) tied to a document
    audit_log    -> every significant action, for the admin panel

Design notes:
    - Single-file SQLite DB (data/app.db) -> no server needed, works on
      Streamlit Community Cloud's ephemeral filesystem.
    - All functions open a short-lived connection and close it -> safe for
      Streamlit's rerun model (no dangling connections across reruns).
    - JSON columns are stored as TEXT and (de)serialized by the caller layer
      (ai_analyzer.py / app.py) to keep this module free of AI-specific logic.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "app.db")


def _ensure_data_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_conn():
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables if they do not already exist. Safe to call every app start."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)


# ---------------------------------------------------------------- users ----
def create_user(username, email, password_hash, role="user"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?,?,?,?,?)",
            (username, email, password_hash, role, datetime.utcnow().isoformat()),
        )


def get_user_by_username(username):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_last_login(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.utcnow().isoformat(), user_id))


def update_password(user_id, new_password_hash):
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))


def update_email(user_id, new_email):
    with get_conn() as conn:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user_id))


def list_all_users():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, username, email, role, created_at, last_login FROM users ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def set_user_role(user_id, role):
    with get_conn() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def delete_user(user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ------------------------------------------------------------ documents ----
def save_document(user_id, filename, file_type, raw_text):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents (user_id, filename, file_type, raw_text, uploaded_at) VALUES (?,?,?,?,?)",
            (user_id, filename, file_type, raw_text, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_document(document_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return dict(row) if row else None


def list_documents_for_user(user_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, file_type, uploaded_at FROM documents WHERE user_id = ? ORDER BY uploaded_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_all_documents():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT documents.id, documents.filename, documents.file_type, documents.uploaded_at,
                   users.username
            FROM documents JOIN users ON documents.user_id = users.id
            ORDER BY documents.uploaded_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def delete_document(document_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


# ------------------------------------------------------------- analyses ----
def save_analysis(document_id, analysis_type, result_json):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO analyses (document_id, analysis_type, result_json, created_at) VALUES (?,?,?,?)",
            (document_id, analysis_type, result_json, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_latest_analysis(document_id, analysis_type):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE document_id = ? AND analysis_type = ? ORDER BY created_at DESC LIMIT 1",
            (document_id, analysis_type),
        ).fetchone()
        return dict(row) if row else None


def list_analyses_for_document(document_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM analyses WHERE document_id = ? ORDER BY created_at DESC", (document_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------ audit log ----
def log_action(user_id, username, action, details=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, username, action, details, timestamp) VALUES (?,?,?,?,?)",
            (user_id, username, action, details, datetime.utcnow().isoformat()),
        )


def get_audit_log(limit=200):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------------------------------- stats -----
def get_dashboard_stats():
    with get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        total_docs = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"]
        total_analyses = conn.execute("SELECT COUNT(*) c FROM analyses").fetchone()["c"]
        by_type = conn.execute(
            "SELECT file_type, COUNT(*) c FROM documents GROUP BY file_type"
        ).fetchall()
        return {
            "total_users": total_users,
            "total_documents": total_docs,
            "total_analyses": total_analyses,
            "documents_by_type": {r["file_type"]: r["c"] for r in by_type},
        }


def get_user_risk_insights(user_id):
    """
    Aggregate risk/compliance data across a single user's documents for the
    'AI Insights Dashboard': average risk score, high-risk document count,
    most frequently detected risk clauses, and a processing history timeline.
    """
    import json as _json

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT analyses.result_json, analyses.analysis_type, analyses.created_at,
                   documents.filename, documents.id as document_id
            FROM analyses
            JOIN documents ON analyses.document_id = documents.id
            WHERE documents.user_id = ?
            ORDER BY analyses.created_at DESC
        """, (user_id,)).fetchall()

    compliance_scores = []
    risk_levels = []
    clause_counter = {}
    processing_history = []
    seen_history_keys = set()

    for row in rows:
        try:
            data = _json.loads(row["result_json"])
        except (ValueError, TypeError):
            continue

        history_key = (row["document_id"], row["created_at"])
        if history_key not in seen_history_keys:
            seen_history_keys.add(history_key)
            processing_history.append({
                "filename": row["filename"],
                "analysis_type": row["analysis_type"],
                "processed_at": row["created_at"],
            })

        if row["analysis_type"] == "compliance" and isinstance(data.get("score"), (int, float)):
            compliance_scores.append(data["score"])

        if row["analysis_type"] == "risks":
            level = data.get("overall_risk_level")
            if level:
                risk_levels.append(level)
            for risk in data.get("risks", []):
                clause = risk.get("clause", "Unknown")
                clause_counter[clause] = clause_counter.get(clause, 0) + 1

    avg_risk_score = round(sum(compliance_scores) / len(compliance_scores), 1) if compliance_scores else None
    high_risk_doc_count = sum(1 for lvl in risk_levels if lvl == "high")
    frequent_risks = sorted(clause_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    processing_history.sort(key=lambda x: x["processed_at"], reverse=True)

    return {
        "average_compliance_score": avg_risk_score,
        "high_risk_document_count": high_risk_doc_count,
        "total_documents_analyzed": len(risk_levels),
        "frequently_detected_risks": [{"clause": c, "count": n} for c, n in frequent_risks],
        "processing_history": processing_history[:20],
    }


def get_ai_usage_stats():
    """
    Admin-facing: how many analyses were produced by live Gemini calls vs the
    rule-based fallback, across ALL users. Used for the 'Monitor AI Usage'
    admin panel requirement.
    """
    import json as _json

    with get_conn() as conn:
        rows = conn.execute("SELECT result_json, analysis_type FROM analyses").fetchall()

    ai_count = 0
    fallback_count = 0
    by_type = {}
    for row in rows:
        try:
            data = _json.loads(row["result_json"])
        except (ValueError, TypeError):
            continue
        source = data.get("source", "unknown")
        by_type.setdefault(row["analysis_type"], {"ai": 0, "fallback": 0})
        if source == "ai":
            ai_count += 1
            by_type[row["analysis_type"]]["ai"] += 1
        else:
            fallback_count += 1
            by_type[row["analysis_type"]]["fallback"] += 1

    total = ai_count + fallback_count
    return {
        "total_analyses": total,
        "ai_powered_count": ai_count,
        "fallback_count": fallback_count,
        "ai_usage_percent": round(100 * ai_count / total, 1) if total else 0,
        "by_analysis_type": by_type,
    }
