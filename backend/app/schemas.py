"""Pydantic schemas for the SoundHub API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: int
    username: str
    wallet_address: str | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Projects ----------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)


class ProjectOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str
    release_token_id: int | None = None
    release_contract: str | None = None
    release_name: str | None = None
    created_at: datetime
    updated_at: datetime
    owner: UserOut


# ---------- Web3 ----------
class WalletNonceOut(BaseModel):
    nonce: str
    message: str


class WalletLogin(BaseModel):
    address: str
    message: str
    signature: str


class ReleaseIn(BaseModel):
    token_id: int = Field(gt=0)
    contract_address: str = Field(min_length=40, max_length=42)
    name: str = Field(min_length=1, max_length=256)


# ---------- Files / commits ----------
class FileOut(BaseModel):
    path: str
    size: int
    blob_sha: str
    kind: str  # "dir" | "file"
    daw_format: str | None = None
    daw_info: dict | None = None


class TreeOut(BaseModel):
    commit_id: int
    commit_message: str
    files: list[FileOut]


class CommitCreate(BaseModel):
    message: str = Field(default="", max_length=2000)


class CommitOut(ORMModel):
    id: int
    message: str
    created_at: datetime
    parent_id: int | None
    author: UserOut
    file_count: int = 0
    total_size: int = 0


class CommitDetailOut(CommitOut):
    files: list[FileOut]


# ---------- Diff ----------
class DiffChange(BaseModel):
    kind: str  # "bpm" | "tempo" | "track_added" | "track_removed" | "device_added" | "device_removed" | "info"
    label: str
    old: str | None = None
    new: str | None = None


class DiffOut(BaseModel):
    path: str
    format: str | None = None
    summary: list[DiffChange] = []
    raw: str = ""
    binary: bool = False
    truncated: bool = False
