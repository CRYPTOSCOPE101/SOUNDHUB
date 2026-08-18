"""Pytest bootstrap: keep the test suite hermetic.

A local `backend/.env` (dev SMTP credentials) must never make the test suite
send real email. We pre-set SMTP_HOST to an empty string BEFORE `app.config`
is imported: `load_dotenv` does not override variables already present in
the environment, so config.SMTP_HOST stays "" and the reminders module runs
in its log-only transport during tests.
"""
import os

os.environ.setdefault("SMTP_HOST", "")
