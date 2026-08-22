from pathlib import Path
import math
import struct
import sys
import wave
from io import BytesIO

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base  # noqa: E402
from app.models import AudioAnalysis, ReviewSession, ReviewVersion, User  # noqa: E402
from app.services import analysis  # noqa: E402
from app.services import storage  # noqa: E402


def _wav(
    values: list[int],
    *,
    sample_rate: int = 8000,
    channels: int = 1,
    width: int = 2,
) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(sample_rate)
        if width == 2:
            output.writeframes(b"".join(struct.pack("<h", value) for value in values))
        else:
            output.writeframes(bytes(values))
    return buf.getvalue()


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _version(db, audio_format="wav", blob_sha="blob"):
    user = User(username=f"user-{id(db)}", password_hash="hash")
    db.add(user)
    db.flush()
    review = ReviewSession(owner_id=user.id, name="Mix", share_token=f"token-{id(db)}")
    db.add(review)
    db.flush()
    version = ReviewVersion(
        session_id=review.id,
        label="v1",
        filename="mix.wav",
        blob_sha=blob_sha,
        audio_format=audio_format,
    )
    db.add(version)
    db.commit()
    return version


def test_measure_audio_reports_peak_duration_and_channels():
    data = _wav([16384, -16384] * 400, sample_rate=16000, channels=2)

    result = analysis._measure_audio(data, "wav")

    assert result["duration_ms"] == 25
    assert result["sample_rate"] == 16000
    assert result["channels"] == 2
    assert result["true_peak_dbtp"] == round(20 * math.log10(0.5), 2)
    assert result["integrated_lufs"] == round(20 * math.log10(0.5) - 3, 2)


def test_measure_audio_defaults_for_non_wav_corrupt_and_silence():
    expected = {
        "duration_ms": 0,
        "sample_rate": None,
        "channels": None,
        "integrated_lufs": None,
        "true_peak_dbtp": None,
    }

    assert analysis._measure_audio(b"audio", "mp3") == expected
    assert analysis._measure_audio(b"not wav", "wav") == expected
    assert analysis._measure_audio(_wav([0] * 10), "wav") == {
        **expected,
        "duration_ms": 1,
        "sample_rate": 8000,
        "channels": 1,
    }


def test_measure_audio_non_16_bit_still_reports_metadata():
    result = analysis._measure_audio(_wav([128] * 80, width=1), "wav")

    assert result["duration_ms"] == 10
    assert result["sample_rate"] == 8000
    assert result["channels"] == 1
    assert result["true_peak_dbtp"] is None
    assert result["integrated_lufs"] is None


def test_analyse_version_creates_done_row_and_is_idempotent(monkeypatch):
    db = _session()
    version = _version(db)
    data = _wav([16384] * 800)
    calls = []

    def read_blob(sha):
        calls.append(sha)
        return data

    monkeypatch.setattr(storage, "read_blob", read_blob)
    analysis.analyse_version(db, version)

    row = db.query(AudioAnalysis).filter_by(version_id=version.id).one()
    assert row.analysis_status == "done"
    assert row.duration_ms == 100
    assert row.sample_rate == 8000
    assert row.channels == 1
    assert row.true_peak_dbtp is not None
    assert row.integrated_lufs is not None
    assert row.analysed_at is not None
    assert calls == ["blob"]

    analysis.analyse_version(db, version)
    assert db.query(AudioAnalysis).filter_by(version_id=version.id).count() == 1
    assert calls == ["blob"]


def test_analyse_version_commits_unavailable_on_blob_error(monkeypatch):
    db = _session()
    version = _version(db, blob_sha="missing")

    def read_blob(_sha):
        raise FileNotFoundError("missing blob")

    monkeypatch.setattr(storage, "read_blob", read_blob)
    analysis.analyse_version(db, version)

    row = db.query(AudioAnalysis).filter_by(version_id=version.id).one()
    assert row.analysis_status == "unavailable"


def test_analyse_version_done_row_skips_blob_read(monkeypatch):
    db = _session()
    version = _version(db)
    existing = AudioAnalysis(version_id=version.id, analysis_status="done")
    db.add(existing)
    db.commit()

    def fail_read(_sha):
        raise AssertionError("read_blob should not be called")

    monkeypatch.setattr(storage, "read_blob", fail_read)
    analysis.analyse_version(db, version)

    assert db.query(AudioAnalysis).filter_by(version_id=version.id).count() == 1
