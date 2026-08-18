import io
import struct
import sys
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config
    from app import database

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    config.ensure_dirs()

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", test_db_url)
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=test_engine, autoflush=False, autocommit=False),
    )
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c


def make_wav(seconds: float = 1.0, sample_rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    n = int(seconds * sample_rate)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = b"".join(
            struct.pack("<h", int(8000 * (0.5 + 0.5 * ((i // 400) % 2)))) for i in range(n)
        )
        w.writeframes(frames)
    return buf.getvalue()


def _register(client, username="producer") -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client, token, name="Neon Warehouse"):
    r = client.post("/api/sessions", json={"name": name}, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, token, sid, wav, message="v1"):
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=_auth(token),
        data={"message": message},
        files=[("file", ("track.wav", wav, "audio/wav"))],
    )
    assert r.status_code == 201, r.text
    return r.json()


def _set_client_email(client, token, sid, email="aisha@example.com"):
    r = client.patch(
        f"/api/sessions/{sid}/reminders",
        headers=_auth(token),
        json={"client_email": email, "reminders_enabled": True},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _evaluate(client, token):
    r = client.post("/api/reminders/evaluate", headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _notifs(client, token, sid):
    r = client.get(f"/api/sessions/{sid}/reminders", headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()["notifications"]


def _kinds(notifs):
    return {n["kind"] for n in notifs}


def _db_session():
    from app.database import SessionLocal

    return SessionLocal()


def _backdate_version(sid, number, days):
    from sqlalchemy import select

    from app.models import ReviewVersion

    with _db_session() as db:
        v = db.scalar(
            select(ReviewVersion).where(
                ReviewVersion.session_id == sid, ReviewVersion.number == number
            )
        )
        v.created_at = datetime.now(timezone.utc) - timedelta(days=days)
        db.commit()


def _insert_invoice_package(sid, version_id, due_hours, delivery_token="dl-test123"):
    from app.models import ReleasePackage

    with _db_session() as db:
        db.add(
            ReleasePackage(
                session_id=sid,
                approved_version_id=version_id,
                name="Final delivery",
                status="ready",
                invoice_status="balance_due",
                amount_due_cents=5000,
                invoice_due_at=datetime.now(timezone.utc) + timedelta(hours=due_hours),
                delivery_token=delivery_token,
            )
        )
        db.commit()


def _set_quote_expiry(sid, co_id, hours):
    from app.models import ChangeOrder

    with _db_session() as db:
        co = db.get(ChangeOrder, co_id)
        co.quote_expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
        db.commit()


# ---------- events ----------


def test_review_opened_queued_on_upload_and_deduped(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    _upload(client, token, s["id"], make_wav())

    notifs = _notifs(client, token, s["id"])
    assert "review.opened" in _kinds(notifs)

    # evaluate again — dedup: nothing new, but queued ones get sent
    r = _evaluate(client, token)
    assert r["created"] == 0
    notifs2 = _notifs(client, token, s["id"])
    assert len(notifs2) == len(notifs)
    assert all(n["status"] == "sent" for n in notifs2)


def test_no_reminders_without_client_email(client):
    token = _register(client)
    s = _create_session(client, token)
    _upload(client, token, s["id"], make_wav())
    assert _evaluate(client, token)["created"] == 0


def test_disabled_reminders_suppressed(client):
    token = _register(client)
    s = _create_session(client, token)
    client.patch(
        f"/api/sessions/{s['id']}/reminders",
        headers=_auth(token),
        json={"reminders_enabled": False, "client_email": "c@x.io"},
    )
    _upload(client, token, s["id"], make_wav())
    assert _evaluate(client, token)["created"] == 0


def test_category_filter_invoice_only(client):
    token = _register(client)
    s = _create_session(client, token)
    client.patch(
        f"/api/sessions/{s['id']}/reminders",
        headers=_auth(token),
        json={"client_email": "c@x.io", "reminder_categories": "invoice"},
    )
    v = _upload(client, token, s["id"], make_wav())
    _insert_invoice_package(s["id"], v["id"], due_hours=12)
    _evaluate(client, token)
    kinds = _kinds(_notifs(client, token, s["id"]))
    assert "invoice.due_1d" in kinds
    assert "review.opened" not in kinds


def test_approval_requested_after_round2_upload(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    v1 = _upload(client, token, s["id"], make_wav())
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/versions/{v1['id']}/comments",
        json={"time_s": 1.0, "body": "bass masks the vocal", "author_name": "aisha@example.com"},
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/submit-feedback",
        params={"actor": "aisha@example.com"},
        json={"note": "round 1"},
    )
    assert r.status_code == 200, r.text
    _upload(client, token, s["id"], make_wav(), message="v2 fixes")
    kinds = _kinds(_notifs(client, token, s["id"]))
    assert "approval.requested" in kinds


def test_feedback_deadline_48h_and_overdue(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    _upload(client, token, s["id"], make_wav())

    due = (datetime.now(timezone.utc) + timedelta(hours=36)).isoformat()
    client.patch(f"/api/sessions/{s['id']}/share", headers=_auth(token), json={"feedback_due_at": due})
    _evaluate(client, token)
    assert "feedback.deadline_48h" in _kinds(_notifs(client, token, s["id"]))

    due = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    client.patch(f"/api/sessions/{s['id']}/share", headers=_auth(token), json={"feedback_due_at": due})
    _evaluate(client, token)
    assert "feedback.overdue" in _kinds(_notifs(client, token, s["id"]))


def test_draft_notes_idle_after_3_days(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    v = _upload(client, token, s["id"], make_wav())
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/versions/{v['id']}/comments",
        json={"time_s": 2.0, "body": "hats are great", "author_name": "aisha@example.com"},
    )
    assert r.status_code == 201, r.text
    _backdate_version(s["id"], v["number"], days=4)
    _evaluate(client, token)
    assert "draft_notes.idle" in _kinds(_notifs(client, token, s["id"]))


def test_invoice_due_1d(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    v = _upload(client, token, s["id"], make_wav())
    _insert_invoice_package(s["id"], v["id"], due_hours=12)
    _evaluate(client, token)
    assert "invoice.due_1d" in _kinds(_notifs(client, token, s["id"]))


def test_change_order_quote_expiring(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    v = _upload(client, token, s["id"], make_wav())
    # change orders only exist for approved projects
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/versions/{v['id']}/approvals",
        json={"scope": "master", "approved": True, "approver_name": "aisha@example.com"},
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"/api/sessions/public/{s['share_token']}/change-orders",
        json={"reason": "mix_revision", "description": "tweak the bass"},
    )
    assert r.status_code == 201, r.text
    co = r.json()
    r = client.patch(
        f"/api/sessions/{s['id']}/change-orders/{co['id']}",
        headers=_auth(token),
        json={"decision": "paid_round", "price_cents": 5000},
    )
    assert r.status_code == 200, r.text
    _set_quote_expiry(s["id"], co["id"], hours=12)
    _evaluate(client, token)
    assert "change_order.quote_expiring" in _kinds(_notifs(client, token, s["id"]))


# ---------- send + ledger ----------


def test_send_writes_notification_sent_ledger(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    _upload(client, token, s["id"], make_wav())
    _evaluate(client, token)
    notifs = _notifs(client, token, s["id"])
    assert notifs and all(n["status"] == "sent" for n in notifs)
    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    events = [e["event"] for e in r.json()["events"]]
    assert "notification.sent" in events


def test_client_opt_out_dismisses_noncritical_only(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    v = _upload(client, token, s["id"], make_wav())  # trigger queues review.opened (not sent)
    _insert_invoice_package(s["id"], v["id"], due_hours=12)
    # queue the invoice reminder without sending (run_all would send everything)
    from app.services import reminders as svc

    with _db_session() as db:
        svc.evaluate(db)
        db.commit()

    r = client.post(f"/api/sessions/public/{s['share_token']}/reminders/opt-out")
    assert r.status_code == 200, r.text
    assert r.json()["opted_out"] is True

    by_kind = {n["kind"]: n for n in _notifs(client, token, s["id"])}
    # non-critical cancelled, transactional invoice mail survives
    assert by_kind["review.opened"]["status"] == "dismissed"
    assert by_kind["invoice.due_1d"]["status"] == "queued"

    # dismissed events land in the ledger
    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    events = [e["event"] for e in r.json()["events"]]
    assert "notification.dismissed" in events


def test_opt_out_blocks_future_noncritical(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_client_email(client, token, s["id"])
    client.post(f"/api/sessions/public/{s['share_token']}/reminders/opt-out")
    _upload(client, token, s["id"], make_wav())
    _evaluate(client, token)
    assert "review.opened" not in _kinds(_notifs(client, token, s["id"]))


# ---------- SMTP transport (port 465 = implicit TLS, 587 = STARTTLS) ----------


class _FakeSmtp:
    """Records login/send; used to unit-test the transport without a server."""

    used_ssl = False
    started_tls = False
    logged_in = None
    sent = None

    @classmethod
    def reset(cls):
        cls.used_ssl = False
        cls.started_tls = False
        cls.logged_in = None
        cls.sent = None

    def __init__(self, host="", port=0, timeout=0):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, user, password):
        type(self).logged_in = (user, password)

    def send_message(self, msg):
        type(self).sent = msg

    def starttls(self):
        type(self).started_tls = True


class _FakeSmtpSsl(_FakeSmtp):
    used_ssl = True


def _notif():
    from types import SimpleNamespace

    return SimpleNamespace(
        subject="Neon Warehouse — your mix is ready",
        recipient="aisha@example.com",
        body="v1 is ready for review.",
        cta_label="Listen & leave notes",
        cta_url="http://front.local/r/tok123",
    )


def test_smtp_deliver_uses_implicit_tls_on_465(monkeypatch):
    """Port 465 (Resend) → SMTP_SSL + login + send."""
    import smtplib

    from app import config
    from app.services.reminders import _smtp_send

    _FakeSmtp.reset()
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.resend.com")
    monkeypatch.setattr(config, "SMTP_PORT", 465)
    monkeypatch.setattr(config, "SMTP_USER", "resend")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "re_secret")
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSmtpSsl)
    monkeypatch.setattr(smtplib, "SMTP", _FakeSmtp)

    _smtp_send(_notif())
    assert _FakeSmtpSsl.used_ssl is True
    assert _FakeSmtpSsl.logged_in == ("resend", "re_secret")
    assert _FakeSmtpSsl.sent["To"] == "aisha@example.com"
    assert _FakeSmtpSsl.sent["From"] == config.SMTP_FROM
    assert "http://front.local/r/tok123" in _FakeSmtpSsl.sent.get_content()


def test_smtp_deliver_uses_starttls_on_587(monkeypatch):
    """Port 587 (Mailgun/SendGrid) → SMTP + starttls + login + send."""
    import smtplib

    from app import config
    from app.services.reminders import _smtp_send

    _FakeSmtp.reset()
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.mailgun.org")
    monkeypatch.setattr(config, "SMTP_PORT", 587)
    monkeypatch.setattr(config, "SMTP_USER", "postmaster@mg.soundhub.com")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "pw")
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSmtpSsl)
    monkeypatch.setattr(smtplib, "SMTP", _FakeSmtp)

    _smtp_send(_notif())
    assert _FakeSmtp.used_ssl is False  # plain SMTP, not SSL
    assert _FakeSmtp.started_tls is True
    assert _FakeSmtp.logged_in == ("postmaster@mg.soundhub.com", "pw")
    assert _FakeSmtp.sent is not None


def test_smtp_deliver_no_auth_when_user_unset(monkeypatch):
    """SMTP_USER empty (open relay/dev) → send without login."""
    import smtplib

    from app import config
    from app.services.reminders import _smtp_send

    _FakeSmtp.reset()
    monkeypatch.setattr(config, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "SMTP_PORT", 25)
    monkeypatch.setattr(config, "SMTP_USER", "")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "")
    monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSmtpSsl)
    monkeypatch.setattr(smtplib, "SMTP", _FakeSmtp)

    _smtp_send(_notif())
    assert _FakeSmtp.logged_in is None
    assert _FakeSmtp.sent is not None
