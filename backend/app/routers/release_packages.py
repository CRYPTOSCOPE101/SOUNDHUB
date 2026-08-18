"""Release packages router — lock, deliver, invoice."""
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import not_found, session_or_404
from ..database import get_db
from ..models import DeliveryEvent, Deliverable, ReleasePackage, ReviewSession, ReviewVersion, User, utcnow
from ..schemas import DeliverableOut, ReleasePackageCreate, ReleasePackageOut
from ..security import get_current_user
from ..services import ledger, storage

router = APIRouter(prefix="/api/release-packages", tags=["release packages"])


def _package_by_token(db: Session, delivery_token: str) -> ReleasePackage:
    package = db.scalar(
        select(ReleasePackage).where(ReleasePackage.delivery_token == delivery_token)
    )
    if package is None:
        raise not_found("Delivery")
    return package


@router.get("", response_model=list[ReleasePackageOut])
def list_packages(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session_or_404(db, session_id, user)
    packages = db.scalars(
        select(ReleasePackage).where(ReleasePackage.session_id == session_id).order_by(ReleasePackage.created_at.desc())
    ).all()
    return [ReleasePackageOut.model_validate(p, from_attributes=True) for p in packages]


@router.post("", response_model=ReleasePackageOut, status_code=status.HTTP_201_CREATED)
def create_package(session_id: int, payload: ReleasePackageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session_or_404(db, session_id, user)
    version = db.get(ReviewVersion, payload.approved_version_id)
    if version is None or version.session_id != session_id:
        raise not_found("Version")
    if version.status != "approved":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Version must be approved before packaging")

    package = ReleasePackage(
        session_id=session_id,
        approved_version_id=payload.approved_version_id,
        name=payload.name,
        template=payload.template,
    )
    db.add(package)
    db.flush()

    # Auto-add the approved version as a deliverable
    deliverable = Deliverable(
        package_id=package.id,
        type="master",
        filename=version.filename,
        blob_sha=version.blob_sha,
        size=version.size,
        source_version_id=version.id,
    )
    db.add(deliverable)

    ledger.append(db, "package.created", session_id=session_id, actor=user.username, entity_type="package", entity_id=package.id, payload={"name": package.name})
    db.commit()
    db.refresh(package)
    return ReleasePackageOut.model_validate(package, from_attributes=True)


@router.patch("/{package_id}/lock", response_model=ReleasePackageOut)
def lock_package(package_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise not_found("Package")
    session = db.get(ReviewSession, package.session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    # Compute manifest hash
    deliverables = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package_id)
    ).all()
    manifest = "\n".join(f"{d.blob_sha}  {d.filename}" for d in sorted(deliverables, key=lambda x: x.filename))
    manifest_hash = hashlib.sha256(manifest.encode()).hexdigest()

    package.status = "delivered"
    package.immutable_at = utcnow()
    package.manifest_hash = manifest_hash
    package.locked_by = user.username
    package.delivery_token = secrets.token_urlsafe(32)

    db.add(DeliveryEvent(package_id=package_id, event="package.locked", actor=user.username))
    ledger.append(db, "package.locked", session_id=session.id, actor=user.username, entity_type="package", entity_id=package_id, payload={"manifest_hash": manifest_hash})
    db.commit()
    return ReleasePackageOut.model_validate(package, from_attributes=True)


@router.get("/{package_id}/deliverables", response_model=list[DeliverableOut])
def list_deliverables(package_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    deliverables = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package_id)
    ).all()
    return [DeliverableOut.model_validate(d, from_attributes=True) for d in deliverables]


@router.get("/public/{delivery_token}")
def public_delivery(delivery_token: str, db: Session = Depends(get_db)):
    package = _package_by_token(db, delivery_token)
    deliverables = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package.id)
    ).all()
    return {
        "package": ReleasePackageOut.model_validate(package, from_attributes=True),
        "deliverables": [DeliverableOut.model_validate(d, from_attributes=True) for d in deliverables],
    }


@router.get("/public/{delivery_token}/download/{deliverable_id}")
def public_download(delivery_token: str, deliverable_id: int, db: Session = Depends(get_db)):
    package = _package_by_token(db, delivery_token)
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None or deliverable.package_id != package.id:
        raise not_found("Deliverable")
    data = storage.read_blob(deliverable.blob_sha)
    db.add(DeliveryEvent(package_id=package.id, event="delivery.downloaded", detail=deliverable.filename))
    db.commit()
    return Response(
        content=data,
        media_type=f"audio/{deliverable.format}",
        headers={"Content-Disposition": f'attachment; filename="{deliverable.filename}"'},
    )
