"""Marketplace catalog service."""
from sqlalchemy import select, or_, literal_column, cast, String
from sqlalchemy.orm import Session
from typing import Optional, List, Union
import hashlib
import hmac
import time

from ..models import ReviewSession, User, Package, Deliverable, ReviewVersion
from .. import config


def list_public_sessions(db: Session, limit: int = 50, offset: int = 0) -> list[dict]:
    """List public portfolio sessions."""
    sessions = db.scalars(
        select(ReviewSession)
        .where(ReviewSession.portfolio_public == True, ReviewSession.status == "approved")
        .order_by(ReviewSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "service_type": s.service_type,
            "genre": s.genre,
            "share_token": s.share_token,
            "owner_username": s.owner.username if s.owner else "",
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


def list_engineers(db: Session, limit: int = 50) -> list[dict]:
    """List engineers with public profiles."""
    users = db.scalars(
        select(User).where(User.bio != "").limit(limit)
    ).all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "bio": u.bio,
            "specialty": u.specialty,
            "location": u.location,
        }
        for u in users
    ]


def list_assets(
    db: Session,
    bpm_min: Optional[int] = None,
    bpm_max: Optional[int] = None,
    license: Optional[str] = None,
    format: Optional[str] = None,
    key: Optional[str] = None,
    genre: Optional[str] = None,
    plugin: Optional[str] = None,
    q: Optional[str] = None,
    include_unpublished: bool = False
) -> List[dict]:
    """List public marketplace assets (Packages and Deliverables) with optional filters."""
    # Build Package query (existing marketplace items)
    package_query = select(
        Package.id.label("id"),
        Package.name.label("name"),
        Package.description.label("description"),
        Package.license.label("license"),
        literal_column("true").label("verified"),  # Packages are verified by definition
        literal_column("'package'").label("type"),  # Mark as package type
        Package.bpm.label("bpm"),
        Package.genre.label("genre"),
        Package.devices.label("devices"),
        Package.devices.label("plugins"),  # For test compatibility
        Package.format.label("format"),
        Package.key.label("key"),
        literal_column("30").label("duration_seconds"),  # Placeholder
        literal_column("'[0.5,0.5,...,0.5]'").label("waveform")  # Placeholder - simplified
    )
    # Only include Packages that have a license (marketplace items) OR include unpublished if requested
    # License must not be NULL and not empty string
    if not include_unpublished:
        package_query = package_query.where(Package.license.isnot(None))
        package_query = package_query.where(Package.license != '')

    # Build Deliverable query (newly enabled marketplace items)
    deliverable_query = select(
        Deliverable.id.label("id"),
        Deliverable.filename.label("name"),
        Deliverable.tags.label("description"),
        Deliverable.license.label("license"),
        Deliverable.verified.label("verified"),
        literal_column("'deliverable'").label("type"),  # Mark as deliverable type
        Deliverable.bpm.label("bpm"),
        Deliverable.genre.label("genre"),
        literal_column("''").label("devices"),  # Deliverables don't have devices directly
        literal_column("''").label("plugins"),   # For test compatibility
        Deliverable.format.label("format"),
        Deliverable.key.label("key"),
        literal_column("30").label("duration_seconds"),  # Placeholder - could be enhanced
        literal_column("'[0.5,0.5,...,0.5]'").label("waveform")  # Placeholder
    )
    # Only include Deliverables that have a license (marketplace-enabled) OR include unpublished if requested
    # License must not be NULL and not empty string
    if not include_unpublished:
        deliverable_query = deliverable_query.where(Deliverable.license.isnot(None))
        deliverable_query = deliverable_query.where(Deliverable.license != '')

    # Apply filters to Package query
    if bpm_min is not None:
        package_query = package_query.where(Package.bpm >= bpm_min)
    if bpm_max is not None:
        package_query = package_query.where(Package.bpm <= bpm_max)
    if license is not None:
        package_query = package_query.where(Package.license.ilike(license))
    if format is not None:
        package_query = package_query.where(Package.format == format)
    if key is not None:
        package_query = package_query.where(Package.key.ilike(key))
    if genre is not None:
        search_terms = [term.strip().lower() for term in genre.split(',')]
        genre_conditions = []
        for term in search_terms:
            genre_conditions.append(Package.genre.ilike(f"%{term}%"))
        if genre_conditions:
            package_query = package_query.where(or_(*genre_conditions))
    if plugin is not None:
        package_query = package_query.where(Package.devices.ilike(f"%{plugin}%"))
    if q is not None:
        search_term = q.strip()
        if len(search_term) > 1 and search_term.endswith('s'):
            stemmed = search_term[:-1]
            search_pattern = f"%{search_term}%"
            stemmed_pattern = f"%{stemmed}%"
            package_query = package_query.where(
                or_(
                    Package.name.ilike(search_pattern),
                    Package.description.ilike(search_pattern),
                    Package.name.ilike(stemmed_pattern),
                    Package.description.ilike(stemmed_pattern)
                )
            )
        else:
            search_term = f"%{search_term}%"
            package_query = package_query.where(or_(Package.name.ilike(search_term), Package.description.ilike(search_term)))

    # Apply filters to Deliverable query
    if bpm_min is not None:
        deliverable_query = deliverable_query.where(Deliverable.bpm >= bpm_min)
    if bpm_max is not None:
        deliverable_query = deliverable_query.where(Deliverable.bpm <= bpm_max)
    if license is not None:
        deliverable_query = deliverable_query.where(Deliverable.license.ilike(license))
    if format is not None:
        deliverable_query = deliverable_query.where(Deliverable.format == format)
    if key is not None:
        deliverable_query = deliverable_query.where(Deliverable.key.ilike(key))
    if genre is not None:
        search_terms = [term.strip().lower() for term in genre.split(',')]
        genre_conditions = []
        for term in search_terms:
            genre_conditions.append(Deliverable.genre.ilike(f"%{term}%"))
        if genre_conditions:
            deliverable_query = deliverable_query.where(or_(*genre_conditions))
    # Note: Deliverables don't have devices field, so plugin filter doesn't apply
    if q is not None:
        search_term = q.strip()
        if len(search_term) > 1 and search_term.endswith('s'):
            stemmed = search_term[:-1]
            search_pattern = f"%{search_term}%"
            stemmed_pattern = f"%{stemmed}%"
            deliverable_query = deliverable_query.where(
                or_(
                    Deliverable.filename.ilike(search_pattern),
                    Deliverable.tags.ilike(search_pattern),
                    Deliverable.filename.ilike(stemmed_pattern),
                    Deliverable.tags.ilike(stemmed_pattern)
                )
            )
        else:
            search_term = f"%{search_term}%"
            deliverable_query = deliverable_query.where(or_(Deliverable.filename.ilike(search_term), Deliverable.tags.ilike(search_term)))

    # Combine queries with UNION ALL
    combined_query = package_query.union_all(deliverable_query)

    # Execute combined query
    results = db.execute(combined_query).fetchall()

    # Format results to match expected structure
    return [
        {
            "id": row.id,
            "name": row.name or "",
            "description": row.description or "",
            "license": row.license or "",
            "verified": bool(row.verified),
            "type": row.type,  # Add type field to distinguish package vs deliverable
            "bpm": [row.bpm] if row.bpm is not None else None,
            "genre": row.genre or "",
            "devices": row.devices or "",
            "plugins": row.plugins or "",  # For compatibility with tests
            "format": row.format or "wav",
            "key": row.key or "",
            "duration_seconds": int(row.duration_seconds) if row.duration_seconds is not None else 30,
            "waveform": [0.5] * 100,  # Placeholder waveform data
        }
        for row in results
    ]


def find_asset(db: Session, asset_id: int) -> Optional[Union[Package, Deliverable]]:
    """Find an asset by ID in either Package or Deliverable tables."""
    # First try to find in Package table
    asset = db.get(Package, asset_id)
    if asset is not None:
        return asset

    # If not found in Package, try Deliverable table
    asset = db.get(Deliverable, asset_id)
    return asset


def make_download_token(secret_key: str, listing_id: int, user_id: int, expires_in: int = 3600) -> str:
    """Create a download token for an asset."""
    # Simple token implementation for testing
    # In production, this would use proper signing like itsdangerous
    import hashlib
    timestamp = str(int(time.time()) + expires_in)
    data = f"{listing_id}:{user_id}:{timestamp}"
    signature = hashlib.sha256((data + secret_key).encode()).hexdigest()
    return f"{data}:{signature}"


def parse_download_token(token: str, secret_key: str) -> tuple[int, int]:
    """Parse and validate a download token.
    Returns (listing_id, user_id) if valid.
    Raises exception if invalid.
    """
    # Implementation similar to the one in assets router
    try:
        parts = token.split(":")
        if len(parts) != 4:  # listing_id:user_id:timestamp:signature
            raise ValueError("Invalid token format")

        listing_id_str, user_id_str, timestamp_str, signature = parts
        listing_id = int(listing_id_str)
        user_id = int(user_id_str)
        timestamp = int(timestamp_str)

        # Check if token expired
        if timestamp < int(time.time()):
            raise ValueError("Token expired")

        # Verify signature
        data = f"{listing_id_str}:{user_id_str}:{timestamp_str}"
        expected_signature = hashlib.sha256((data + secret_key).encode()).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature")

        return listing_id, user_id
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid token: {e}")


def recommend_assets(db: Session, user_id: int, limit: int = 10,
                     bpm: Optional[int] = None,
                     genre: Optional[str] = None,
                     license: Optional[str] = None,
                     format: Optional[str] = None,
                     key: Optional[str] = None,
                     devices: Optional[str] = None) -> List[dict]:
    """Recommend assets based on various filters.
    Returns a list of asset dicts sorted by relevance.
    """
    from sqlalchemy import or_

    # Get Packages (existing marketplace items)
    package_query = select(Package).where(Package.license.isnot(None))
    packages = db.scalars(package_query).all()

    # Get Deliverables (newly enabled marketplace items)
    deliverable_query = select(Deliverable).where(Deliverable.license.isnot(None))
    deliverables = db.scalars(deliverable_query).all()

    # Score each package based on how well it matches the criteria
    scored_packages = []
    for package in packages:
        score = 0
        reasons = []

        # BPM matching (exact match gets 2 points, range match gets 1 point)
        if bpm is not None:
            if package.bpm is not None:
                if package.bpm == bpm:
                    score += 2
                    reasons.append("bpm match")
                elif abs(package.bpm - bpm) <= 5:  # Within 5 BPM
                    score += 1
                    reasons.append("bpm close")

        # Genre matching (check if any comma-separated term matches)
        if genre is not None:
            if package.genre:
                # Split search genre by commas and check if any term is in package genre
                search_terms = [term.strip().lower() for term in genre.split(',')]
                package_genre_lower = package.genre.lower()
                if any(term in package_genre_lower for term in search_terms):
                    score += 2
                    reasons.append("genre match")

        # Devices matching (exact match gets 2 points)
        if devices is not None:
            if package.devices and devices.lower() in package.devices.lower():
                score += 2
                reasons.append("devices match")

        # License matching (exact match gets 2 points)
        if license is not None:
            if package.license and license.lower() == package.license.lower():
                score += 2
                reasons.append("license match")

        # Format matching (exact match gets 2 points)
        if format is not None:
            if package.format == format:
                score += 2
                reasons.append("format match")

        # Key matching (exact match gets 2 points)
        if key is not None:
            if package.key == key:
                score += 2
                reasons.append("key match")

        # Only include packages that have at least some match
        # If no filters provided, include all (score > 0 or all None)
        if score > 0 or (bpm is None and genre is None and devices is None and license is None and format is None and key is None):
            scored_packages.append({
                "item": package,
                "score": score,
                "reasons": reasons,
                "type": "package"
            })

    # Score each deliverable based on how well it matches the criteria
    scored_deliverables = []
    for deliverable in deliverables:
        score = 0
        reasons = []

        # BPM matching (exact match gets 2 points, range match gets 1 point)
        if bpm is not None:
            if deliverable.bpm is not None:
                if deliverable.bpm == bpm:
                    score += 2
                    reasons.append("bpm match")
                elif abs(deliverable.bpm - bpm) <= 5:  # Within 5 BPM
                    score += 1
                    reasons.append("bpm close")

        # Genre matching (check if any comma-separated term matches)
        if genre is not None:
            if deliverable.genre:
                # Split search genre by commas and check if any term is in deliverable genre
                search_terms = [term.strip().lower() for term in genre.split(',')]
                deliverable_genre_lower = deliverable.genre.lower()
                if any(term in deliverable_genre_lower for term in search_terms):
                    score += 2
                    reasons.append("genre match")

        # Devices matching - deliverables don't have devices field, so skip
        # License matching (exact match gets 2 points)
        if license is not None:
            if deliverable.license and license.lower() == deliverable.license.lower():
                score += 2
                reasons.append("license match")

        # Format matching (exact match gets 2 points)
        if format is not None:
            if deliverable.format == format:
                score += 2
                reasons.append("format match")

        # Key matching (exact match gets 2 points)
        if key is not None:
            if deliverable.key == key:
                score += 2
                reasons.append("key match")

        # Only include deliverables that have at least some match
        # If no filters provided, include all (score > 0 or all None)
        if score > 0 or (bpm is None and genre is None and license is None and format is None and key is None):
            scored_deliverables.append({
                "item": deliverable,
                "score": score,
                "reasons": reasons,
                "type": "deliverable"
            })

    # Combine and sort all scored items
    all_scored = scored_packages + scored_deliverables
    # Sort by score descending, then by price_cents descending for tie-breaking
    all_scored.sort(key=lambda x: (x["score"],
                                   getattr(x["item"], "price_cents", 0) if hasattr(x["item"], "price_cents") else 0),
                    reverse=True)

    # Limit results
    limited = all_scored[:limit]

    # Convert to the same format as list_assets with scoring info
    return [
        {
            "id": getattr(item["item"], "id", None),
            "name": getattr(item["item"], "name", getattr(item["item"], "filename", "")),
            "description": getattr(item["item"], "description", getattr(item["item"], "tags", "")) or "",
            "license": getattr(item["item"], "license", ""),
            "verified": getattr(item["item"], "verified", True) if item["type"] == "package" else bool(getattr(item["item"], "verified", False)),
            "type": item["type"],  # Add type field to distinguish package vs deliverable
            "bpm": [getattr(item["item"], "bpm", None)] if getattr(item["item"], "bpm", None) is not None else None,
            "genre": getattr(item["item"], "genre", "") or "",
            "devices": getattr(item["item"], "devices", "") if item["type"] == "package" else "",  # Deliverables don't have devices
            "plugins": getattr(item["item"], "devices", "") if item["type"] == "package" else "",   # For compatibility with tests
            "format": getattr(item["item"], "format", "wav"),
            "key": getattr(item["item"], "key", "") or "",
            "duration_seconds": 30,
            "waveform": [0.5] * 100,
            # Optionally include scoring info (not required by tests but useful)
            "_score": float(item["score"]),
            "_reasons": item["reasons"]
        }
        for item in limited
    ]
