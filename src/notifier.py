"""
notifier.py
===========
Optional "Email Report Delivery" bonus feature.

Sends the generated PDF/DOCX analysis report as an email attachment via
SMTP. Fully optional: if SMTP credentials aren't configured (in Streamlit
secrets or environment variables), `is_configured()` returns False and the
UI simply hides/disables the "Email Report" button rather than erroring.

Configuration (Streamlit secrets or env vars):
    SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL
"""

import os
import smtplib
from email.message import EmailMessage


def _get_config(secrets) -> dict:
    def _get(key, default=""):
        try:
            if secrets and key in secrets:
                return secrets[key]
        except Exception:
            pass
        return os.environ.get(key, default)

    return {
        "host": _get("SMTP_HOST"),
        "port": _get("SMTP_PORT", "587"),
        "username": _get("SMTP_USERNAME"),
        "password": _get("SMTP_PASSWORD"),
        "from_email": _get("SMTP_FROM_EMAIL"),
    }


def is_configured(secrets=None) -> bool:
    cfg = _get_config(secrets)
    return bool(cfg["host"] and cfg["username"] and cfg["password"] and cfg["from_email"])


def send_report_email(to_email: str, subject: str, body: str, attachment_bytes: bytes,
                       attachment_filename: str, secrets=None) -> dict:
    """
    Send an analysis report as an email attachment.
    Returns {"success": bool, "message": str}. Never raises -- always safe to call.
    """
    cfg = _get_config(secrets)
    if not is_configured(secrets):
        return {"success": False, "message": "Email delivery is not configured on this server (SMTP settings missing)."}

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg["from_email"]
        msg["To"] = to_email
        msg.set_content(body)

        maintype = "application"
        subtype = "pdf" if attachment_filename.lower().endswith(".pdf") else \
            "vnd.openxmlformats-officedocument.wordprocessingml.document"
        msg.add_attachment(attachment_bytes, maintype=maintype, subtype=subtype, filename=attachment_filename)

        with smtplib.SMTP(cfg["host"], int(cfg["port"]), timeout=15) as server:
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.send_message(msg)

        return {"success": True, "message": f"Report emailed to {to_email}."}
    except Exception as e:  # noqa: BLE001 -- user-facing graceful failure
        return {"success": False, "message": f"Failed to send email: {e}"}
