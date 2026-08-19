"""SoundHub API — GitHub for music production projects."""
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .config import CORS_ORIGINS
from .database import get_db, init_db
from .routers import (
    activity,
    ai_mix,
    analytics,
    assets,
    audio_checks,
    auth,
    change_orders,
    codeowners_milestones,
    comparisons,
    dashboard,
    discussions,
    diffs,
    files,
    groups,
    integrations,
    kanban,
    metadata,
    notifications_social,
    packages_gist_sponsors,
    pins,
    portfolio,
    projects,
    pull_requests,
    references,
    release_packages,
    reminders,
    roles,
    search,
    secrets_envs,
    sessions,
    tags,
    tags_releases,
    tasks,
    templates,
    two_factor,
    webhooks,
    workflows_security,
    wiki_time_epics,
    gitlab_features,
    code_search_and_insights,
    pipelines_ci,
    test_plans,
    deployments_artifacts,
    agile_delivery,
    search_engine as search_engine_router,
)

app = FastAPI(
    title="SoundHub API",
    description="Version control and collaboration for music production projects.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
app.include_router(metadata.router)
app.include_router(pull_requests.router)
app.include_router(tasks.router)
app.include_router(tags_releases.router)
app.include_router(audio_checks.router)
app.include_router(discussions.router)
app.include_router(kanban.router)
app.include_router(ai_mix.router)
app.include_router(dashboard.router)
app.include_router(integrations.router)
app.include_router(two_factor.router)
app.include_router(codeowners_milestones.router)
app.include_router(notifications_social.router)
app.include_router(secrets_envs.router)
app.include_router(packages_gist_sponsors.router)
app.include_router(workflows_security.router)
app.include_router(wiki_time_epics.router)
app.include_router(gitlab_features.router)
app.include_router(code_search_and_insights.router)
app.include_router(pipelines_ci.router)
app.include_router(test_plans.router)
app.include_router(deployments_artifacts.router)
app.include_router(agile_delivery.router)
app.include_router(search_engine_router.router)

# GraphQL endpoint
from strawberry.fastapi import GraphQLRouter
from .graphql.schema import schema as graphql_schema

graphql_app = GraphQLRouter(graphql_schema)
app.include_router(graphql_app, prefix="/graphql")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    # Initialize FTS5 search index and reindex all entities
    from .services.search_engine import init_search_index, reindex_all
    init_search_index()
    try:
        result = reindex_all()
        print(f"🔍 Search index: {result['indexed']} entities indexed")
    except Exception as e:
        print(f"⚠️  Search reindex skipped: {e}")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "soundhub-api"}


_STATIC = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
def docs_home():
    """Serve the API documentation landing page."""
    return (_STATIC / "docs.html").read_text(encoding="utf-8")
