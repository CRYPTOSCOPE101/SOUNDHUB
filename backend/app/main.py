"""SoundHub API — GitHub for music production projects."""
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .routers import (
    activity,
    analytics,
    assets,
    auth,
    change_orders,
    comparisons,
    diffs,
    files,
    groups,
    pins,
    portfolio,
    projects,
    references,
    release_packages,
    reminders,
    roles,
    search,
    sessions,
    tags,
    templates,
    webhooks,
)

app = FastAPI(
    title="SoundHub API",
    description="Version control and collaboration for music production projects.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(activity.router)
app.include_router(analytics.router)
app.include_router(templates.router)
app.include_router(tags.router)
app.include_router(groups.router)
app.include_router(pins.router)
app.include_router(webhooks.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "soundhub-api"}
