"""SoundHub API — GitHub for music production projects."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers import assets, auth, diffs, files, projects, release_packages, sessions

app = FastAPI(
    title="SoundHub API",
    description="Version control and collaboration for music production projects "
    "(Ableton Live, Cubase, REAPER, FL Studio).",
    version="0.1.0",
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
app.include_router(release_packages.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "soundhub-api"}
