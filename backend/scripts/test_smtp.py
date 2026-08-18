"""Verify the SMTP transport end to end (Resend or any SMTP relay).

Sends one plain-text email through the exact code path the reminder
notifications use (app.services.reminders._deliver), so a green run here
means the reminders module will deliver for real.

Usage (from backend/):

    SMTP_HOST=smtp.resend.com SMTP_PORT=465 SMTP_USER=resend \
    SMTP_PASSWORD=re_<api-key> SMTP_FROM='SoundHub <soundhub@soundhub.com>' \
    .venv/bin/python -m scripts.test_smtp you@example.com [--subject "hi"]

Exit code 0 = delivered; anything else prints the SMTP error.
"""
import argparse
import os
import sys
from email.message import EmailMessage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from app import config
    from app.services.reminders import _deliver

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipient", help="where to send the test email")
    parser.add_argument("--subject", default="SoundHub SMTP test", help="subject line")
    args = parser.parse_args()

    if not config.SMTP_HOST:
        print("SMTP_HOST is not set — the reminders module is in log-only mode.", file=sys.stderr)
        return 2

    msg = EmailMessage()
    msg["Subject"] = args.subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = args.recipient
    msg.set_content(
        "This is a test email from SoundHub.\n\n"
        "If you received this, the SMTP transport is working and reminder\n"
        "notifications will be delivered for real.\n"
    )

    try:
        _deliver(msg)
    except Exception as exc:  # transport failure — surface the SMTP detail
        print(f"✗ delivery failed: {exc}", file=sys.stderr)
        return 1

    print(f"✓ sent via {config.SMTP_HOST}:{config.SMTP_PORT} → {args.recipient} (from {config.SMTP_FROM})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
