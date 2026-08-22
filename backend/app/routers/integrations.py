"""Webhook Integrations — connect SoundHub to Slack, Discord, Telegram.

Each integration stores a webhook URL and the events it subscribes to.
When an event occurs, SoundHub sends a POST to the webhook with a payload.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


# ── Models (lightweight, no DB table needed for MVP) ──────────────────────

@dataclass
class WebhookConfig:
    id: int
    user_id: int
    platform: str     # slack | discord | telegram | custom
    url: str
    events: list[str]
    is_active: bool = True
    created_at: str = ""

# In-memory store for MVP — move to DB for production
_webhooks: list[WebhookConfig] = []
_next_id = 1


# ── Schemas ───────────────────────────────────────────────────────────────

class IntegrationCreate(BaseModel):
    platform: str = Field(pattern=r"^(slack|discord|telegram|custom)$")
    url: str = Field(min_length=10, max_length=500)
    events: list[str] = Field(default=["*"], description="Events to subscribe to")

class IntegrationOut(BaseModel):
    id: int
    platform: str
    url: str
    events: list[str]
    is_active: bool
    created_at: str

class IntegrationUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None


# ── Event types ────────────────────────────────────────────────────────────

EVENT_TYPES = {
    "push": "New commit pushed",
    "pr.opened": "Pull request opened",
    "pr.merged": "Pull request merged",
    "pr.review": "Pull request reviewed",
    "review.comment": "Review comment added",
    "review.approved": "Review approved",
    "task.created": "Task created",
    "task.closed": "Task closed",
    "discussion.created": "Discussion created",
    "tag.created": "Tag created",
    "release.published": "Release published",
    # Storage & job lifecycle events
    "storage.object.uploaded": "Asset uploaded to object storage",
    "storage.object.ready": "Asset processed and ready",
    "job.queued": "Background job queued",
    "job.completed": "Background job completed",
    "job.failed": "Background job failed",
}


# ── Platform formatters ────────────────────────────────────────────────────

def _format_slack(event: str, data: dict) -> dict:
    """Format event as Slack message."""
    color = "#3b82f6"
    if "approved" in event or "merged" in event:
        color = "#22c55e"
    elif "closed" in event or "comment" in event:
        color = "#ef4444"

    title = EVENT_TYPES.get(event, event)
    fields = []
    for k, v in data.items():
        if k in ("project", "branch", "title", "message", "author"):
            fields.append({"title": k.title(), "value": str(v)[:100], "short": True})

    return {
        "attachments": [{
            "color": color,
            "title": f"SoundHub: {title}",
            "fields": fields,
            "footer": "SoundHub Webhook",
            "ts": int(time.time()),
        }]
    }


def _format_discord(event: str, data: dict) -> dict:
    """Format event as Discord embed."""
    color = 0x3b82f6
    if "approved" in event or "merged" in event:
        color = 0x22c55e
    elif "closed" in event:
        color = 0xef4444

    fields = []
    for k, v in data.items():
        if k in ("project", "branch", "title", "message", "author"):
            fields.append({"name": k.title(), "value": str(v)[:100], "inline": True})

    return {
        "embeds": [{
            "title": f"SoundHub: {EVENT_TYPES.get(event, event)}",
            "color": color,
            "fields": fields,
            "footer": {"text": "SoundHub Webhook"},
        }]
    }


def _format_telegram(event: str, data: dict) -> dict:
    """Format event as Telegram message."""
    title = EVENT_TYPES.get(event, event)
    lines = [f"*{title}*"]
    for k, v in data.items():
        if k in ("project", "branch", "title", "message", "author"):
            lines.append(f"_{k.title()}:_ {str(v)[:100]}")

    return {"text": "\n".join(lines), "parse_mode": "Markdown"}


def _format_custom(event: str, data: dict) -> dict:
    """Format as generic JSON payload."""
    return {"event": event, "data": data, "timestamp": int(time.time())}


FORMATTERS = {
    "slack": _format_slack,
    "discord": _format_discord,
    "telegram": _format_telegram,
    "custom": _format_custom,
}


# ── Webhook dispatcher ─────────────────────────────────────────────────────

def dispatch_event(event: str, data: dict, user_id: int | None = None) -> dict:
    """Send event to all matching webhooks.

    Returns summary of delivery attempts.
    """
    results = {"sent": 0, "failed": 0, "skipped": 0}

    for wh in _webhooks:
        if not wh.is_active:
            results["skipped"] += 1
            continue
        if user_id and wh.user_id != user_id:
            continue
        if "*" not in wh.events and event not in wh.events:
            results["skipped"] += 1
            continue

        formatter = FORMATTERS.get(wh.platform, _format_custom)
        payload = formatter(event, data)

        try:
            req = urllib.request.Request(
                wh.url,
                data=json.dumps(payload).encode(),
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "SoundHub-Webhook/1.0")
            req.add_header("X-SoundHub-Event", event)

            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status < 300:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
        except Exception:
            results["failed"] += 1

    return results


# ── API endpoints ──────────────────────────────────────────────────────────

@router.get("/events")
def list_event_types():
    """List all available webhook event types."""
    return {"events": [{"key": k, "description": v} for k, v in EVENT_TYPES.items()]}


@router.get("", response_model=list[IntegrationOut])
def list_integrations(user: User = Depends(get_current_user)):
    """List all webhook integrations for the current user."""
    return [
        IntegrationOut(
            id=wh.id, platform=wh.platform, url=wh.url,
            events=wh.events, is_active=wh.is_active, created_at=wh.created_at,
        )
        for wh in _webhooks if wh.user_id == user.id
    ]


@router.post("", response_model=IntegrationOut, status_code=status.HTTP_201_CREATED)
def create_integration(payload: IntegrationCreate, user: User = Depends(get_current_user)):
    """Create a new webhook integration."""
    global _next_id
    wh = WebhookConfig(
        id=_next_id, user_id=user.id,
        platform=payload.platform, url=payload.url,
        events=payload.events,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    _webhooks.append(wh)
    _next_id += 1
    return IntegrationOut(id=wh.id, platform=wh.platform, url=wh.url, events=wh.events, is_active=wh.is_active, created_at=wh.created_at)


@router.patch("/{integration_id}", response_model=IntegrationOut)
def update_integration(integration_id: int, payload: IntegrationUpdate, user: User = Depends(get_current_user)):
    """Update a webhook integration."""
    wh = next((w for w in _webhooks if w.id == integration_id and w.user_id == user.id), None)
    if wh is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration not found")
    if payload.url is not None: wh.url = payload.url
    if payload.events is not None: wh.events = payload.events
    if payload.is_active is not None: wh.is_active = payload.is_active
    return IntegrationOut(id=wh.id, platform=wh.platform, url=wh.url, events=wh.events, is_active=wh.is_active, created_at=wh.created_at)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_integration(integration_id: int, user: User = Depends(get_current_user)):
    """Delete a webhook integration."""
    global _webhooks
    before = len(_webhooks)
    _webhooks = [w for w in _webhooks if not (w.id == integration_id and w.user_id == user.id)]
    if len(_webhooks) == before:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration not found")


@router.post("/{integration_id}/test")
def test_integration(integration_id: int, user: User = Depends(get_current_user)):
    """Send a test event to a webhook."""
    wh = next((w for w in _webhooks if w.id == integration_id and w.user_id == user.id), None)
    if wh is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Integration not found")

    result = dispatch_event("test", {"message": "This is a test from SoundHub", "project": "Test Project"}, user.id)
    return {"ok": True, "result": result}
