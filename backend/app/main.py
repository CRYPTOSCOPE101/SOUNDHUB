"""SoundHub API — GitHub for music production projects."""
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .routers import (
    assets,
    auth,
    change_orders,
    comparisons,
    diffs,
    files,
    portfolio,
    projects,
    references,
    release_packages,
    reminders,
    roles,
    search,
    sessions,
)

app = FastAPI(
    title="SoundHub API",
    description="Version control and collaboration for music production projects "
    "(Ableton Live, Cubase, REAPER, FL Studio).",
    version="0.1.0",
    docs_url=None,  # custom /docs below (larger fonts for readability)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only — tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(diffs.router)
app.include_router(assets.router)
app.include_router(sessions.router)
app.include_router(change_orders.router)
app.include_router(release_packages.router)
app.include_router(comparisons.router)
app.include_router(portfolio.router)
app.include_router(references.router)
app.include_router(reminders.router)
app.include_router(roles.router)
app.include_router(search.router)

# The landing page CTA "Open a sample review" points here directly — a fixed,
# human-readable token so the demo review is always reachable at /r/demo-review-token
# (no account, no /login redirect, no fetch-then-redirect on the landing page).
DEMO_REVIEW_TOKEN = "demo-review-token"


def _seed_sample_review() -> None:
    """Idempotent demo seed: a public sample review the landing page links to.

    Lets the "Open a sample review" CTA show the value without an account.
    """
    import io
    import math
    import struct
    import wave

    from .database import SessionLocal
    from .models import ReviewComment, ReviewSession, ReviewVersion, User
    from .security import hash_password
    from .services import storage, waveform

    with SessionLocal() as db:
        demo = db.scalar(select(User).where(User.username == "demo"))
        if demo is None:
            demo = User(username="demo", password_hash=hash_password("demo123"))
            db.add(demo)
            db.flush()
        if not demo.bio:
            # demo engineer profile — reputation is computed from real data,
            # bio/specialty/location are the only self-edited fields
            demo.bio = (
                "Demo engineer: bass-heavy garage and neon warehouse mixes. "
                "Working in Ableton Live 12, REAPER, Cubase and FL Studio."
            )
            demo.specialty = "mix_master"
            demo.location = "Berlin"
        if not demo.wallet_address:
            # wallet-linked identity → ✓ Verified badge (signature-checked path)
            demo.wallet_address = "0x" + "ab" * 20
            db.add(demo)
        db.commit()  # persist the profile even when the review already exists
        existing = db.scalar(
            select(ReviewSession).where(ReviewSession.share_token == DEMO_REVIEW_TOKEN)
        )
        if existing is not None:
            return
        sr = 22050
        n = sr * 16  # 16 seconds
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            frames = b"".join(
                struct.pack(
                    "<h",
                    int(
                        6500
                        * (0.55 + 0.45 * math.sin(2 * math.pi * 110 * i / sr))
                        * (0.6 + 0.4 * ((i // (sr // 2)) % 2))
                    ),
                )
                for i in range(n)
            )
            w.writeframes(frames)
        data = buf.getvalue()
        blob_sha = storage.put_blob(data)
        wf = waveform.generate(blob_sha, data, "neon-warehouse-v12.wav", "wav")
        session = ReviewSession(
            owner_id=demo.id,
            name="Neon Warehouse — sample review",
            share_token=DEMO_REVIEW_TOKEN,
            status="in_review",
            share_permission="download",
            portfolio_public=True,  # visible in header search + demo portfolio
            service_type="mix_master",
            genre="Neon warehouse / garage",
            goal="label",
            do_not_change="Keep the vocal balance as-is; don't touch the arrangement",
            required_deliverables="master, instrumental, clean edit",
            reference_links="https://soundcloud.com/example/neon-warehouse-ref",
            included_rounds=1,
            round_number=1,
            # so the reminder engine has a real recipient for the demo session
            client_email="aisha@example.com",
        )
        db.add(session)
        db.flush()
        version = ReviewVersion(
            session_id=session.id,
            number=1,
            label="v12",
            message="Bass revised after round 1 — vocal left untouched",
            filename="neon-warehouse-v12.wav",
            blob_sha=blob_sha,
            size=len(data),
            duration_s=wf["duration_s"],
            audio_format="wav",
            round_number=1,
            status="in_review",
        )
        db.add(version)
        db.flush()
        db.add(
            ReviewComment(
                version_id=version.id,
                author_name="Aisha (A&R)",
                time_s=1.5,
                body="Kick and bass clash at the drop — let the vocal breathe.",
            )
        )
        db.add(
            ReviewComment(
                version_id=version.id,
                author_name="Artist",
                time_s=9.0,
                body="Hats are great after 0:45. Keep them.",
            )
        )
        db.commit()


demo = APIRouter(prefix="/api", tags=["demo"])


@demo.get("/demo/review")
def demo_review(db: Session = Depends(get_db)):
    """The seeded sample review — used by the landing CTA "Open a sample review"."""
    from .models import ReviewSession, User

    demo = db.scalar(select(User).where(User.username == "demo"))
    if demo is None:
        return {"share_token": "", "name": "", "url": "", "version_count": 0}
    s = db.scalar(
        select(ReviewSession)
        .where(ReviewSession.owner_id == demo.id)
        .order_by(ReviewSession.created_at.desc())
        .limit(1)
    )
    if s is None:
        return {"share_token": "", "name": "", "url": "", "version_count": 0}
    from .models import ReviewVersion

    vcount = db.scalar(
        select(ReviewVersion).where(ReviewVersion.session_id == s.id).order_by(ReviewVersion.number.desc()).limit(1)
    )
    return {
        "share_token": s.share_token,
        "name": s.name,
        "url": f"/r/{s.share_token}",
        "version_count": vcount.number if vcount else 0,
    }


app.include_router(demo)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    _seed_sample_review()
    # queue + deliver reminders for the seeded demo session (review.opened,
    # invoice due, …) so the notification log is non-empty on first boot
    try:
        from .database import SessionLocal
        from .services import reminders as reminders_svc

        with SessionLocal() as db:
            reminders_svc.run_all(db)
            db.commit()
    except Exception:
        pass  # reminders are best-effort at startup


# ── Custom documentation pages ──────────────────────────────────────────
# /docs      → styled landing page (docs.html)
# /docs/raw  → Swagger UI with enlarged fonts
# /redoc     → ReDoc (built-in FastAPI)

import pathlib as _pathlib

_DOCS_HTML = (_pathlib.Path(__file__).parent / "static" / "docs.html").read_text()

_SWAGGER_FONT_CSS = """
<style>
  .swagger-ui { font-size: 16px; }
  .swagger-ui .info .title { font-size: 2.8em; }
  .swagger-ui .info .description, .swagger-ui .info .base-url { font-size: 1.4em; }
  .swagger-ui .info li, .swagger-ui .info p, .swagger-ui .info table { font-size: 1.25em; }
  .swagger-ui .opblock-tag { font-size: 1.9em; }
  .swagger-ui .opblock-summary-path a { font-size: 1.4em; }
  .swagger-ui .opblock-summary-description { font-size: 1.25em; }
  .swagger-ui .opblock .opblock-summary { font-size: 1.15em; }
  .swagger-ui .opblock-description-wrapper p { font-size: 1.25em; }
  .swagger-ui .parameter__name, .swagger-ui .parameter__type { font-size: 1.2em; }
  .swagger-ui .parameters-col_description { font-size: 1.2em; }
  .swagger-ui .model-title { font-size: 1.5em; }
  .swagger-ui .model { font-size: 1.15em; }
  .swagger-ui .btn { font-size: 1.2em; }
  .swagger-ui .response-col_status, .swagger-ui .response-col_description { font-size: 1.15em; }
  .swagger-ui label, .swagger-ui .servers-title { font-size: 1.2em; }
  .swagger-ui table { font-size: 1.15em; }
  .swagger-ui input[type=text], .swagger-ui textarea { font-size: 1.2em; }
  .swagger-ui .markdown p, .swagger-ui .renderedMarkdown p { font-size: 1.2em; }
</style>
"""


@app.get("/docs", include_in_schema=False)
def docs_landing():
    from fastapi.responses import HTMLResponse

    return HTMLResponse(_DOCS_HTML)


@app.get("/docs/raw", include_in_schema=False)
def swagger_ui():
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.responses import HTMLResponse

    html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_ui_parameters={"displayRequestDuration": True},
    )
    body = html.body.decode() if isinstance(html.body, bytes) else html.body
    body = body.replace("</head>", _SWAGGER_FONT_CSS + "</head>", 1)
    return HTMLResponse(body)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "soundhub-api"}
