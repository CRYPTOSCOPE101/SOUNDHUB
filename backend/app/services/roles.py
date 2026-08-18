"""Team roles and approval gate enforcement.

Approval presets control who can sign off on what scope:
- solo_client / artist_team: permissive (any reviewer may approve)
- label_workflow / post_production: enforced (role must match scope)
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ReviewSession, SessionMember

ROLE_LABELS = {
    "engineer": "Engineer",
    "artist": "Artist",
    "a_r": "A&R",
    "label_admin": "Label Admin",
    "producer": "Producer",
    "director": "Director",
    "feedback_owner": "Feedback Owner",
    "viewer": "Viewer",
}

PRESETS = {
    "solo_client": {
        "label": "Solo Client",
        "enforced": False,
        "policy": {"mix": ["*"], "master": ["*"], "arrangement": ["*"], "release": ["*"]},
    },
    "artist_team": {
        "label": "Artist Team",
        "enforced": False,
        "policy": {"mix": ["*"], "master": ["*"], "arrangement": ["*"], "release": ["*"]},
    },
    "label_workflow": {
        "label": "Label Workflow",
        "enforced": True,
        "policy": {
            "mix": ["artist", "a_r"],
            "master": ["a_r", "label_admin"],
            "arrangement": ["producer", "director"],
            "release": ["label_admin"],
        },
    },
    "post_production": {
        "label": "Post-Production",
        "enforced": True,
        "policy": {
            "mix": ["engineer", "director"],
            "master": ["director"],
            "arrangement": ["director"],
            "release": ["director"],
        },
    },
}


def member_role(db: Session, session: ReviewSession, email: str) -> str | None:
    """Look up the role of a session member by email."""
    if not email:
        return None
    member = db.scalar(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            SessionMember.email == email.lower().strip(),
        )
    )
    return member.role if member else None


def role_can_approve(session: ReviewSession, role: str | None, scope: str) -> bool:
    """Check whether the given role is allowed to approve the scope."""
    preset = PRESETS.get(session.approval_preset, PRESETS["solo_client"])
    if not preset["enforced"]:
        return True  # permissive presets: anyone may approve
    if role is None:
        return False
    allowed = preset["policy"].get(scope, [])
    return "*" in allowed or role in allowed


def preset_info(session: ReviewSession) -> dict:
    return PRESETS.get(session.approval_preset, PRESETS["solo_client"])


def list_presets() -> list[dict]:
    return [{"key": k, **v} for k, v in PRESETS.items()]
