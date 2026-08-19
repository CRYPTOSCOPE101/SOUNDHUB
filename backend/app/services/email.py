"""Email sending service.

Supports two backends:
  1. Resend API (recommended — simple, free tier, no SMTP setup)
  2. SMTP fallback (already built into reminders.py)

Usage:
  from app.services.email import send_email

  send_email(
      to="client@example.com",
      subject="Your mix is ready for review",
      html="<h1>Review ready</h1><p>Click here to listen...</p>",
  )
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.error
import smtplib
from email.message import EmailMessage
from typing import Optional


# ── Configuration ────────────────────────────────────────────────────────────

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "SoundHub <onboarding@resend.dev>")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "SoundHub <no-reply@soundhub.local>")


# ── Resend API ───────────────────────────────────────────────────────────────

def _send_via_resend(to: str, subject: str, html: str) -> dict | None:
    """Send email via Resend API (https://resend.com)."""
    if not RESEND_API_KEY:
        return None

    payload = json.dumps({
        "from": RESEND_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {RESEND_API_KEY}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"error": f"Resend API error {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}


# ── SMTP fallback ────────────────────────────────────────────────────────────

def _send_via_smtp(to: str, subject: str, html: str) -> dict | None:
    """Send email via SMTP (fallback when Resend is not configured)."""
    if not SMTP_HOST:
        return None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.set_content(html, subtype="html")

    try:
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
                if SMTP_USER:
                    smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
                smtp.starttls()
                if SMTP_USER:
                    smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(msg)
        return {"ok": True, "backend": "smtp"}
    except Exception as e:
        return {"error": f"SMTP error: {e}"}


# ── Public API ───────────────────────────────────────────────────────────────

def send_email(
    to: str,
    subject: str,
    html: str,
    *,
    fallback: bool = True,
) -> dict:
    """Send a transactional email.

    Tries Resend first, falls back to SMTP if not configured.

    Args:
        to: Recipient email address
        subject: Email subject line
        html: HTML body content
        fallback: If True, try SMTP when Resend fails

    Returns:
        dict with "ok": true on success, or "error" on failure.
    """
    # Try Resend first
    result = _send_via_resend(to, subject, html)
    if result and "error" not in result:
        return {"ok": True, "backend": "resend", "id": result.get("id")}

    # Fallback to SMTP
    if fallback:
        smtp_result = _send_via_smtp(to, subject, html)
        if smtp_result and "error" not in smtp_result:
            return {"ok": True, "backend": "smtp"}

    # Both failed
    errors = []
    if result and "error" in result:
        errors.append(f"Resend: {result['error']}")
    if fallback:
        smtp_result = _send_via_smtp(to, subject, html)
        if smtp_result and "error" in smtp_result:
            errors.append(f"SMTP: {smtp_result['error']}")

    return {"ok": False, "error": "; ".join(errors) or "No email backend configured"}


# ── Template helpers ──────────────────────────────────────────────────────────

def review_ready_email(
    session_name: str,
    reviewer_name: str,
    review_url: str,
    version_label: str = "",
) -> dict:
    """Generate email content for a review-ready notification."""
    subject = f"Review ready: {session_name}"
    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1f1f1f;">🎧 Review ready</h2>
        <p><strong>{reviewer_name}</strong> uploaded a new version for <strong>{session_name}</strong>.</p>
        {"<p>Version: <strong>" + version_label + "</strong></p>" if version_label else ""}
        <a href="{review_url}"
           style="display: inline-block; background: #ff5e1a; color: white;
                  padding: 12px 24px; border-radius: 6px; text-decoration: none;
                  font-weight: 600; margin: 16px 0;">
            Open review →
        </a>
        <p style="color: #666; font-size: 13px; margin-top: 24px;">
            You're receiving this because you're a reviewer on this project.
        </p>
    </div>
    """
    return {"subject": subject, "html": html}


def approval_email(
    session_name: str,
    approved: bool,
    approver_name: str,
    note: str = "",
) -> dict:
    """Generate email content for an approval notification."""
    if approved:
        subject = f"✅ Approved: {session_name}"
        icon = "✅"
        text = "has been approved"
    else:
        subject = f"🔄 Changes requested: {session_name}"
        icon = "🔄"
        text = "needs changes"

    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #1f1f1f;">{icon} {subject}</h2>
        <p><strong>{approver_name}</strong> {text} on <strong>{session_name}</strong>.</p>
        {"<p>Note: " + note + "</p>" if note else ""}
    </div>
    """
    return {"subject": subject, "html": html}
