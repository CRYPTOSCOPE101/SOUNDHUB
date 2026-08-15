"""Team roles & approval chains.

Presets (from the product spec — the default keeps the solo engineer happy):

    solo_client        Engineer, client            client approves
    artist_team        Engineer, artist, feedback owner   artist / feedback owner approves
    label_workflow     Engineer, artist, A&R, label admin Artist: mix · A&R: master · label: release
    post_production    Engineer, producer, director       producer / director approves

Permission model (minimum):
    engineer        upload versions, resolve requests, create packages, quote change orders
    reviewer        draft notes, voice notes, view approved versions
    feedback_owner  submit consolidated notes
    approver        approve the scope(s) their role covers (mix / master / release)
    label_admin     invite users, configure policy, approve release, see invoices & delivery

Approval policy per enforced preset — a scope is only "signed off" when the
required roles have an approved approval for that scope on the SAME version:

    mix:     Artist
    master:  Artist + A&R
    release: Label admin (prerequisite: master approved)

Permissive presets (solo_client, artist_team) keep the original behaviour:
any reviewer with comment access can approve — no role gymnastics for the
freelance client.

Enforcement is deliberately scoped: a new version (v14) never inherits the
approvals of v13 (approvals are bound to version_id), and a release package
can only lock the version whose approvals satisfy the policy.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ReviewApproval, SessionMember

# role id -> human label
ROLE_LABELS: dict[str, str] = {
    "engineer": "Engineer",
    "artist": "Artist",
    "feedback_owner": "Feedback owner",
    "a_r": "A&R",
    "label_admin": "Label admin",
    "producer": "Producer",
    "director": "Director",
    "viewer": "Viewer",
    "client": "Client",
}

# scope -> required roles (order matters for display; release implies master)
_POLICY = {
    "label_workflow": {"mix": ["artist"], "master": ["artist", "a_r"], "release": ["label_admin"]},
    "post_production": {"mix": ["producer"], "master": ["producer", "director"], "release": ["director"]},
}

PRESETS: dict[str, dict] = {
    "solo_client": {
        "label": "Solo client",
        "roles": ["engineer", "client"],
        "policy": {"mix": ["client"], "master": ["client"], "release": ["client"]},
        "enforced": False,
    },
    "artist_team": {
        "label": "Artist team",
        "roles": ["engineer", "artist", "feedback_owner"],
        "policy": {"mix": ["artist"], "master": ["artist"], "release": ["artist"]},
        "enforced": False,
    },
    "label_workflow": {
        "label": "Label workflow",
        "roles": ["engineer", "artist", "a_r", "label_admin"],
        "policy": _POLICY["label_workflow"],
        "enforced": True,
    },
    "post_production": {
        "label": "Post-production",
        "roles": ["engineer", "producer", "director"],
        "policy": _POLICY["post_production"],
        "enforced": True,
    },
}


def preset_info(preset: str) -> dict:
    return PRESETS.get(preset, PRESETS["solo_client"])


def member_role(db: Session, session, name: str) -> str | None:
    """Resolve an approver's role by email (case-insensitive). None = not invited."""
    if not name or not name.strip():
        return None
    row = db.scalar(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            func.lower(SessionMember.email) == name.strip().lower(),
        )
    )
    return row.role if row else None


def role_can_approve(session, role: str | None, scope: str) -> bool:
    """May this role sign off the given scope in this session's preset?"""
    preset = preset_info(session.approval_preset)
    if not preset["enforced"]:
        return True  # permissive: any reviewer with comment access approves
    if not role:
        return False
    allowed = preset["policy"].get(scope, [])
    return role in allowed


def policy_status(db: Session, session, version, scope: str) -> dict:
    """Is the approval policy satisfied for `scope` on THIS version?

    Permissive presets: always ok (any approved approval of the scope counts
    in practice — the UI keeps showing the policy, but nothing is gated).
    Enforced presets: every required role must have an approved approval of
    the scope on this version; `release` also requires master to be signed.
    """
    preset = preset_info(session.approval_preset)
    if not preset["enforced"]:
        return {"ok": True, "missing": [], "required": [], "enforced": False}
    rows = db.scalars(
        select(ReviewApproval).where(
            ReviewApproval.session_id == session.id,
            ReviewApproval.version_id == version.id,
        )
    ).all()
    required = list(preset["policy"].get(scope, []))
    approved_roles = {a.role for a in rows if a.approved and a.scope == scope}
    if scope == "release":
        # prerequisite: master approved (Artist + A&R in label workflow)
        required = list(dict.fromkeys(required + preset["policy"].get("master", [])))
        master_roles = {a.role for a in rows if a.approved and a.scope == "master"}
        approved_roles = approved_roles | master_roles
    missing = [r for r in required if r not in approved_roles]
    return {"ok": not missing, "missing": missing, "required": required, "enforced": True}


def policy_for_session(session) -> dict:
    """Full policy object for the session's preset (frontend panel)."""
    preset = preset_info(session.approval_preset)
    return {
        "preset": session.approval_preset,
        "preset_label": preset["label"],
        "enforced": preset["enforced"],
        "policy": preset["policy"],
        "roles": preset["roles"],
    }
