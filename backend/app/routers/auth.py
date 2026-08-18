"""Auth router — register, login, wallet auth, profile."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    ProfileUpdate,
    TokenOut,
    UserLogin,
    UserOut,
    UserRegister,
    WalletLogin,
    WalletNonceOut,
)
from ..security import create_access_token, get_current_user, hash_password, verify_password
from ..wallet_auth import issue_challenge, verify_challenge

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.username)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(user.id, user.username)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/wallet/nonce", response_model=WalletNonceOut)
def wallet_nonce(payload: dict):
    address = payload.get("address", "").strip()
    if len(address) != 42 or not address.startswith("0x"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid wallet address")
    nonce, message = issue_challenge(address)
    return WalletNonceOut(nonce=nonce, message=message)


@router.post("/wallet/login", response_model=TokenOut)
def wallet_login(payload: WalletLogin, db: Session = Depends(get_db)):
    if not verify_challenge(payload.address, payload.message, payload.signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signature verification failed")

    address = payload.address.lower()
    user = db.scalar(select(User).where(User.wallet_address == address))
    if user is None:
        base = address[:10]
        username = base
        n = 2
        while db.scalar(select(User).where(User.username == username)):
            username = f"{base}-{n}"
            n += 1
        user = User(username=username, wallet_address=address)
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token(user.id, user.username)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.bio is not None:
        user.bio = payload.bio.strip()
    if payload.specialty is not None:
        user.specialty = payload.specialty.strip()
    if payload.location is not None:
        user.location = payload.location.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
