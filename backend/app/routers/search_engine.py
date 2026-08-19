"""Unified Search Engine — full-text search across all 235 endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services import search_engine

router = APIRouter(prefix="/api/unified-search", tags=["search engine"])


# ── Unified Search ──────────────────────────────────────────────────────────

@router.get("")
def unified_search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str | None = Query(None, alias="type", description="Filter by entity type"),
    project: int | None = Query(None, description="Filter by project ID"),
    tags: str | None = Query(None, description="Filter by tags"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
):
    """Search across ALL entities in SoundHub.

    Examples:
        - `?q=remix` — find everything mentioning "remix"
        - `?q=vocal+chop&type=pull_request` — search PRs only
        - `?q=urgent&project=5` — search within project 5
    """
    results = search_engine.search(
        query=q, entity_type=type, project_id=project, tags=tags,
        limit=limit, offset=offset, user_id=user.id,
    )
    return results


# ── Quick Search (type-ahead) ───────────────────────────────────────────────

@router.get("/quick")
def quick_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
):
    """Fast type-ahead search for autocomplete."""
    results = search_engine.search(query=q, limit=limit)
    return {
        "suggestions": [
            {"type": r["type"], "id": r["id"], "title": r["title"], "snippet": r.get("snippet", "")[:100]}
            for r in results["results"]
        ],
        "total": results["total"],
    }


# ── Index Management ────────────────────────────────────────────────────────

class IndexEntity(BaseModel):
    entity_type: str
    entity_id: int
    title: str
    body: str = ""
    tags: str = ""
    project_id: int | None = None
    metadata: dict | None = None


@router.post("/index")
def index_entity(payload: IndexEntity, user: User = Depends(get_current_user)):
    """Manually index an entity."""
    search_engine.index_entity(
        entity_type=payload.entity_type, entity_id=payload.entity_id,
        title=payload.title, body=payload.body, tags=payload.tags,
        project_id=payload.project_id, metadata=payload.metadata,
    )
    return {"ok": True}


@router.delete("/index/{entity_type}/{entity_id}")
def remove_from_index(entity_type: str, entity_id: int, user: User = Depends(get_current_user)):
    """Remove an entity from the search index."""
    search_engine.remove_entity(entity_type, entity_id)
    return {"ok": True}


@router.post("/reindex")
def reindex_all(project: int | None = None, user: User = Depends(get_current_user)):
    """Re-index all entities."""
    result = search_engine.reindex_all(project_id=project)
    return {"ok": True, **result}


# ── Index Statistics ────────────────────────────────────────────────────────

@router.get("/stats")
def search_stats(user: User = Depends(get_current_user)):
    """Get statistics about the search index."""
    return search_engine.get_index_stats()


@router.get("/popular")
def popular_queries(limit: int = Query(10, ge=1, le=50)):
    """Get most popular search queries."""
    return search_engine.get_popular_queries(limit)


# ── Saved Searches ──────────────────────────────────────────────────────────

class SavedSearchCreate(BaseModel):
    name: str
    query: str
    filters: dict = {}


@router.get("/saved")
def list_saved_searches(user: User = Depends(get_current_user)):
    """List user's saved searches."""
    from ..services.search_engine import _get_conn
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_searches WHERE user_id = ? ORDER BY created_at DESC",
            (user.id,),
        ).fetchall()
        return [{"id": r["id"], "name": r["name"], "query": r["query"],
                 "filters": r["filters"], "created_at": r["created_at"]} for r in rows]


@router.post("/saved", status_code=201)
def save_search(payload: SavedSearchCreate, user: User = Depends(get_current_user)):
    """Save a search for later reuse."""
    import json
    from ..services.search_engine import _get_conn
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO saved_searches (user_id, name, query, filters) VALUES (?, ?, ?, ?)",
            (user.id, payload.name, payload.query, json.dumps(payload.filters)),
        )
        return {"id": cur.lastrowid, "name": payload.name}


@router.delete("/saved/{sid}", status_code=204)
def delete_saved_search(sid: int, user: User = Depends(get_current_user)):
    """Delete a saved search."""
    from ..services.search_engine import _get_conn
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM saved_searches WHERE id = ? AND user_id = ?",
            (sid, user.id),
        )


# ── Search Suggestions ──────────────────────────────────────────────────────

@router.get("/suggest")
def suggest(q: str = Query(..., min_length=1)):
    """Get search suggestions based on entity types and aliases."""
    from ..services.search_engine import _get_conn
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT alias, entity_type FROM search_aliases WHERE alias LIKE ? LIMIT 10",
            (f"%{q.lower()}%",),
        ).fetchall()
        suggestions = [{"text": r["alias"], "type": r["entity_type"]} for r in rows]

        title_rows = conn.execute(
            "SELECT entity_type, entity_id, title FROM entity_registry WHERE title LIKE ? LIMIT 10",
            (f"%{q}%",),
        ).fetchall()
        for r in title_rows:
            suggestions.append({
                "text": r["title"], "type": r["entity_type"], "id": r["entity_id"],
            })

        return {"suggestions": suggestions[:10]}


# ── Search by Entity Type (MUST be last — catch-all) ───────────────────────

@router.get("/{entity_type}")
def search_by_type(
    entity_type: str,
    q: str = Query(..., min_length=1),
    project: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Search within a specific entity type."""
    results = search_engine.search(
        query=q, entity_type=entity_type, project_id=project, limit=limit, offset=offset,
    )
    return results
