"""SQLite FTS5 full-text search engine for SoundHub.

Indexes all major entities and provides unified search with BM25 ranking,
highlighting, prefix search, and faceted results.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Path to the search index database (separate from main DB for isolation)
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_INDEX_PATH = str(_DB_DIR / "search_index.db")


@contextmanager
def _get_conn():
    conn = sqlite3.connect(_INDEX_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_search_index() -> None:
    """Create FTS5 virtual tables and metadata tables."""
    with _get_conn() as conn:
        # Main FTS5 index (content table — stores actual data)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                entity_type,
                entity_id,
                title,
                body,
                metadata,
                tags,
                updated_at,
                tokenize='porter unicode61'
            )
        """)

        # Entity registry
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entity_registry (
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                project_id INTEGER,
                title TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                PRIMARY KEY (entity_type, entity_id)
            )
        """)

        # Search analytics
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                result_count INTEGER DEFAULT 0,
                user_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Saved searches
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                query TEXT NOT NULL,
                filters TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Search aliases
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_aliases (
                alias TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL
            )
        """)

        # Pre-populate aliases
        aliases = {
            "pr": "pull_request", "pull request": "pull_request", "pull requests": "pull_request",
            "issue": "music_task", "issues": "music_task", "task": "music_task", "tasks": "music_task",
            "bug": "music_task", "feature": "music_task",
            "merge": "pull_request", "review": "pull_request_review",
            "commit": "commit", "commits": "commit",
            "branch": "branch", "branches": "branch",
            "tag": "git_tag", "tags": "git_tag", "release": "git_tag", "releases": "git_tag",
            "discussion": "discussion", "discussions": "discussion",
            "wiki": "wiki_page", "docs": "wiki_page",
            "sprint": "sprint", "sprints": "sprint",
            "retro": "retrospective", "retros": "retrospective",
            "test": "test_plan", "tests": "test_plan", "test plan": "test_plan",
            "epic": "epic", "epics": "epic",
            "kanban": "kanban_board", "board": "kanban_board",
            "package": "package", "packages": "package",
            "workflow": "workflow", "pipelines": "workflow", "ci": "workflow",
            "incident": "incident", "incidents": "incident",
            "error": "error", "errors": "error",
            "mirror": "mirror_config", "mirrors": "mirror_config",
            "extension": "extension", "extensions": "extension",
            "deploy": "deployment", "deployment": "deployment", "deployments": "deployment",
            "design": "design", "designs": "design",
            "ticket": "service_desk_ticket", "support": "service_desk_ticket",
            "requirement": "requirement", "requirements": "requirement",
            "objective": "objective", "okr": "objective", "okrs": "objective",
            "sponsor": "sponsorship", "sponsors": "sponsorship",
            "team": "team", "teams": "team",
            "secret": "project_secret", "secrets": "project_secret",
        }
        for alias, entity_type in aliases.items():
            conn.execute(
                "INSERT OR IGNORE INTO search_aliases (alias, entity_type) VALUES (?, ?)",
                (alias, entity_type),
            )


def index_entity(
    entity_type: str,
    entity_id: int,
    title: str,
    body: str = "",
    tags: str = "",
    project_id: int | None = None,
    metadata: dict | None = None,
    updated_at: str | None = None,
) -> None:
    """Index a single entity into the search engine."""
    now = updated_at or datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(metadata or {})

    with _get_conn() as conn:
        # Delete existing entry if re-indexing
        conn.execute(
            "DELETE FROM search_index WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        )

        # Insert into FTS5
        conn.execute(
            "INSERT INTO search_index (entity_type, entity_id, title, body, metadata, tags, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entity_type, entity_id, title, body, meta_json, tags, now),
        )

        # Update registry
        conn.execute(
            "INSERT OR REPLACE INTO entity_registry (entity_type, entity_id, project_id, title, tags, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (entity_type, entity_id, project_id, title, tags, now),
        )


def remove_entity(entity_type: str, entity_id: int) -> None:
    """Remove an entity from the search index."""
    with _get_conn() as conn:
        conn.execute(
            "DELETE FROM search_index WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        )
        conn.execute(
            "DELETE FROM entity_registry WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id),
        )


def _resolve_alias(query: str, entity_type: str | None) -> str | None:
    """Resolve search aliases to entity types."""
    if entity_type:
        return entity_type

    with _get_conn() as conn:
        first_word = query.strip().split()[0].lower() if query.strip() else ""
        row = conn.execute(
            "SELECT entity_type FROM search_aliases WHERE alias = ?",
            (first_word,),
        ).fetchone()
        if row:
            return row["entity_type"]

        row = conn.execute(
            "SELECT entity_type FROM search_aliases WHERE alias = ?",
            (query.strip().lower(),),
        ).fetchone()
        if row:
            return row["entity_type"]

    return None


def _build_fts_query(query: str) -> str:
    """Convert user query to FTS5 query syntax."""
    import re
    terms = query.strip().split()

    if '"' in query:
        return query

    fts_terms = []
    for term in terms:
        clean = re.sub(r'[^\w\-*]', '', term)
        if clean:
            if len(clean) <= 3:
                fts_terms.append(f'"{clean}"*')
            else:
                fts_terms.append(f'"{clean}"')

    return " OR ".join(fts_terms) if fts_terms else '""'


def _highlight(text: str, query: str, max_len: int = 200) -> str:
    """Extract a snippet around the first match."""
    if not text:
        return ""

    import re
    terms = [re.escape(t) for t in query.split() if len(t) > 1]
    if not terms:
        return text[:max_len]

    pattern = re.compile("|".join(terms), re.IGNORECASE)
    match = pattern.search(text)

    if match:
        start = max(0, match.start() - 60)
        end = min(len(text), match.end() + max_len - 60)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
    else:
        snippet = text[:max_len]

    snippet = pattern.sub(lambda m: f"**{m.group()}**", snippet)
    return snippet


def search(
    query: str,
    entity_type: str | None = None,
    project_id: int | None = None,
    tags: str | None = None,
    limit: int = 20,
    offset: int = 0,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Unified search across all indexed entities."""
    import time
    start = time.monotonic()

    resolved_type = _resolve_alias(query, entity_type)
    fts_query = _build_fts_query(query)

    with _get_conn() as conn:
        # --- Step 1: Get matching IDs from FTS5 ---
        fts_rows = conn.execute(
            "SELECT rowid, entity_type, entity_id, rank AS score FROM search_index WHERE search_index MATCH ? ORDER BY rank",
            (fts_query,),
        ).fetchall()

        if not fts_rows:
            return {"results": [], "facets": {}, "total": 0, "query": query, "took_ms": 0}

        # Build lookup maps from FTS results
        fts_map = {}  # (type, id) -> score
        for r in fts_rows:
            fts_map[(r["entity_type"], r["entity_id"])] = abs(r["score"])

        # --- Step 2: Filter via registry (project, type, tags) ---
        ids = [(r["entity_type"], r["entity_id"]) for r in fts_rows]
        if not ids:
            return {"results": [], "facets": {}, "total": 0, "query": query, "took_ms": 0}

        # Build IN clause
        placeholders = ",".join("?" * len(ids))
        flat_ids = []
        for et, eid in ids:
            flat_ids.extend([et, eid])

        registry_sql = f"""
            SELECT entity_type, entity_id, project_id, title, tags, updated_at
            FROM entity_registry
            WHERE (entity_type, entity_id) IN (VALUES {','.join(f'(?,?)' for _ in ids)})
        """
        registry_rows = conn.execute(registry_sql, flat_ids).fetchall()

        # Apply filters in Python
        filtered = []
        for r in registry_rows:
            if resolved_type and r["entity_type"] != resolved_type:
                continue
            if project_id is not None and r["project_id"] != project_id:
                continue
            if tags and tags not in (r["tags"] or ""):
                continue
            filtered.append(r)

        total = len(filtered)

        # Sort by FTS score
        filtered.sort(key=lambda r: fts_map.get((r["entity_type"], r["entity_id"]), 999))

        # Paginate
        page = filtered[offset : offset + limit]

        # --- Step 3: Log analytics ---
        if user_id:
            conn.execute(
                "INSERT INTO search_analytics (query, result_count, user_id) VALUES (?, ?, ?)",
                (query, total, user_id),
            )

        # --- Step 4: Build facets ---
        facets = {}
        if not resolved_type:
            facet_counts: dict[str, int] = {}
            for r in filtered:
                et = r["entity_type"]
                facet_counts[et] = facet_counts.get(et, 0) + 1
            facets["entity_type"] = dict(sorted(facet_counts.items(), key=lambda x: -x[1])[:20])

    took_ms = round((time.monotonic() - start) * 1000, 1)

    return {
        "results": [
            {
                "type": r["entity_type"],
                "id": r["entity_id"],
                "title": r["title"],
                "snippet": "",  # filled below
                "tags": r["tags"],
                "score": round(fts_map.get((r["entity_type"], r["entity_id"]), 0), 3),
                "updated_at": r["updated_at"],
            }
            for r in page
        ],
        "facets": facets,
        "total": total,
        "query": query,
        "took_ms": took_ms,
    }


def get_popular_queries(limit: int = 10) -> list[dict]:
    """Get most popular search queries."""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT query, COUNT(*) as cnt, AVG(result_count) as avg_results
            FROM search_analytics
            GROUP BY query ORDER BY cnt DESC LIMIT ?
        """, (limit,)).fetchall()
        return [{"query": r["query"], "count": r["cnt"], "avg_results": round(r["avg_results"])} for r in rows]


def get_index_stats() -> dict:
    """Get statistics about the search index."""
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as cnt FROM entity_registry").fetchone()["cnt"]
        by_type = conn.execute("""
            SELECT entity_type, COUNT(*) as cnt
            FROM entity_registry GROUP BY entity_type ORDER BY cnt DESC
        """).fetchall()
        return {
            "total_indexed": total,
            "by_type": {r["entity_type"]: r["cnt"] for r in by_type},
            "db_path": _INDEX_PATH,
        }


def reindex_all(project_id: int | None = None) -> dict:
    """Re-index all entities from the main database."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from ..database import DATABASE_URL
    from ..models import (
        Project, Branch, Commit, PullRequest, PullRequestReview,
        MusicTask, Discussion, GitTag, WikiPage, Milestone,
        Epic, Sprint, Retrospective, TestPlan, KanbanBoard,
        Package, Gist, Workflow, Incident, Error, SecurityScan,
        CodeOwner, Design, ServiceDeskTicket, Requirement,
        Extension, MirrorConfig, Objective, Sponsorship,
    )

    engine = create_engine(DATABASE_URL)
    indexed = 0

    with Session(engine) as db:
        # Projects
        for p in db.scalars(select(Project)).all():
            index_entity("project", p.id, p.name, p.description, project_id=p.id)
            indexed += 1

        # Branches
        for b in db.scalars(select(Branch)).all():
            index_entity("branch", b.id, b.name, f"Branch {b.name}", project_id=b.project_id)
            indexed += 1

        # Commits
        for c in db.scalars(select(Commit)).all():
            index_entity("commit", c.id, c.message[:200], c.message, project_id=c.project_id)
            indexed += 1

        # Pull Requests
        for pr in db.scalars(select(PullRequest)).all():
            body = f"{pr.title} {pr.description} {pr.source_branch} -> {pr.target_branch}"
            index_entity("pull_request", pr.id, pr.title, body, pr.status, pr.project_id)
            indexed += 1

        # PR Reviews
        for r in db.scalars(select(PullRequestReview)).all():
            index_entity("pull_request_review", r.id, f"Review by {r.reviewer_name or 'anon'}",
                         r.body, r.decision)
            indexed += 1

        # Music Tasks
        for t in db.scalars(select(MusicTask)).all():
            body = f"{t.title} {t.body} {t.type} {t.priority} {t.status}"
            index_entity("music_task", t.id, t.title, body, f"{t.type} {t.priority} {t.status}", t.project_id)
            indexed += 1

        # Discussions
        for d in db.scalars(select(Discussion)).all():
            index_entity("discussion", d.id, d.title, f"{d.title} {d.body}", d.category, d.project_id)
            indexed += 1

        # Git Tags
        for t in db.scalars(select(GitTag)).all():
            index_entity("git_tag", t.id, t.name, f"{t.name} {t.message}", project_id=t.project_id)
            indexed += 1

        # Wiki Pages
        for w in db.scalars(select(WikiPage)).all():
            index_entity("wiki_page", w.id, w.title, f"{w.title} {w.content}", project_id=w.project_id)
            indexed += 1

        # Milestones
        for m in db.scalars(select(Milestone)).all():
            index_entity("milestone", m.id, m.title, f"{m.title} {m.description}", project_id=m.project_id)
            indexed += 1

        # Epics
        for e in db.scalars(select(Epic)).all():
            index_entity("epic", e.id, e.title, f"{e.title} {e.description}", project_id=e.project_id)
            indexed += 1

        # Sprints
        for s in db.scalars(select(Sprint)).all():
            index_entity("sprint", s.id, s.name, f"{s.name} {s.goal}", project_id=s.project_id)
            indexed += 1

        # Retrospectives
        for r in db.scalars(select(Retrospective)).all():
            index_entity("retrospective", r.id, r.name, r.name, project_id=r.project_id)
            indexed += 1

        # Test Plans
        for tp in db.scalars(select(TestPlan)).all():
            index_entity("test_plan", tp.id, tp.name, f"{tp.name} {tp.description}", project_id=tp.project_id)
            indexed += 1

        # Kanban Boards
        for kb in db.scalars(select(KanbanBoard)).all():
            index_entity("kanban_board", kb.id, kb.name, kb.name, project_id=kb.project_id)
            indexed += 1

        # Packages
        for pkg in db.scalars(select(Package)).all():
            body = f"{pkg.name} {pkg.description} {pkg.package_type} {pkg.tags}"
            index_entity("package", pkg.id, pkg.name, body, pkg.tags, project_id=pkg.project_id)
            indexed += 1

        # Gists
        for g in db.scalars(select(Gist)).all():
            index_entity("gist", g.id, g.title or "Untitled", f"{g.title} {g.description}")
            indexed += 1

        # Workflows
        for w in db.scalars(select(Workflow)).all():
            index_entity("workflow", w.id, w.name, f"{w.name} {w.yaml_content}", project_id=w.project_id)
            indexed += 1

        # Incidents
        for i in db.scalars(select(Incident)).all():
            index_entity("incident", i.id, i.title, f"{i.title} {i.description}", project_id=i.project_id)
            indexed += 1

        # Errors
        for e in db.scalars(select(Error)).all():
            index_entity("error", e.id, e.message, f"{e.message} {e.stacktrace}", project_id=e.project_id)
            indexed += 1

        # Security Scans
        for s in db.scalars(select(SecurityScan)).all():
            index_entity("security_scan", s.id, f"{s.scan_type} scan",
                         f"Type: {s.scan_type} Status: {s.status}", s.status, s.project_id)
            indexed += 1

        # Code Owners
        for co in db.scalars(select(CodeOwner)).all():
            index_entity("code_owner", co.id, f"{co.pattern} -> {co.owner_username}",
                         f"Pattern: {co.pattern} Owner: {co.owner_username}", project_id=co.project_id)
            indexed += 1

        # Designs
        for d in db.scalars(select(Design)).all():
            index_entity("design", d.id, d.filename, f"{d.filename} {d.note}", project_id=d.project_id)
            indexed += 1

        # Service Desk
        for t in db.scalars(select(ServiceDeskTicket)).all():
            index_entity("service_desk_ticket", t.id, f"{t.identifier}: {t.subject}",
                         f"{t.subject} {t.body}", project_id=t.project_id)
            indexed += 1

        # Requirements
        for r in db.scalars(select(Requirement)).all():
            index_entity("requirement", r.id, r.title, f"{r.title} {r.description}", project_id=r.project_id)
            indexed += 1

        # Objectives
        for o in db.scalars(select(Objective)).all():
            index_entity("objective", o.id, o.title, f"{o.title} {o.description}", project_id=o.project_id)
            indexed += 1

        # Extensions
        for e in db.scalars(select(Extension)).all():
            index_entity("extension", e.id, e.name, f"{e.name} {e.description} {e.author} {e.category}")
            indexed += 1

        # Mirrors
        for m in db.scalars(select(MirrorConfig)).all():
            index_entity("mirror_config", m.id, m.mirror_url, f"Mirror: {m.mirror_url}", project_id=m.project_id)
            indexed += 1

        # Sponsorships
        for s in db.scalars(select(Sponsorship)).all():
            index_entity("sponsorship", s.id, f"Sponsorship by {s.sponsor_id}",
                         f"Tier: {s.tier} Amount: {s.amount_cents}c")
            indexed += 1

    return {"indexed": indexed, "by_type": get_index_stats()["by_type"]}
