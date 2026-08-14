"""Seed a demo user + project so the UI has something to show.

Usage:
    cd backend && .venv/bin/python -m scripts.seed_demo
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Project, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.daw import fixtures as fx  # noqa: E402
from app.services import versioning  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "demo").first()
        if user is None:
            user = User(username="demo", password_hash=hash_password("demo123"))
            db.add(user)
            db.commit()
            db.refresh(user)

        project = db.query(Project).filter(Project.owner_id == user.id, Project.name == "Neon Dreams").first()
        if project is None:
            project = Project(
                owner_id=user.id,
                name="Neon Dreams",
                slug="neon-dreams",
                description="Demo project — synthwave track. Shows versioned Ableton, REAPER, Cubase and FL Studio files.",
            )
            db.add(project)
            db.commit()
            db.refresh(project)

        if project.commits:
            print(f"Demo project already seeded ({len(project.commits)} commits). Nothing to do.")
            return

        base = "Neon Dreams"
        # ---- Commit 1: initial arrangement ----
        versioning.create_commit(
            db,
            project,
            user,
            "Initial arrangement: beat + lead sketch (128 BPM)",
            {
                f"{base}/{base}.als": fx.make_als(bpm=128.0),
                f"{base}/{base}.cpr": fx.make_cpr(bpm=128.0),
                f"{base}/{base}.rpp": fx.make_rpp(bpm=128.0),
                f"{base}/{base}.flp": fx.make_flp(bpm=128.0),
                f"{base}/README.md": (
                    "# Neon Dreams\n\nDemo project for SoundHub.\n\n"
                    "## Track plan\n- Synth lead (Serum)\n- Drums (808 kit)\n\n"
                    "Open with Ableton Live 12, Cubase 13, REAPER 6 or FL Studio 20.\n"
                ).encode(),
                f"{base}/Samples/Kick.wav": fx.make_wav(200),
                f"{base}/Samples/Clap.wav": fx.make_wav(150),
            },
        )

        # ---- Commit 2: arrangement changes ----
        versioning.create_commit(
            db,
            project,
            user,
            "Push tempo to 132, add vocal chop track + new pad synth",
            {
                f"{base}/{base}.als": fx.make_als(
                    bpm=132.0,
                    tracks=[
                        ("MidiTrack", "Synth Lead", ["Plugin:Serum"]),
                        ("MidiTrack", "Pad", ["Plugin:Vital"]),
                        ("AudioTrack", "Drums", ["Compressor2"]),
                        ("AudioTrack", "Vocal Chops", ["Plugin:Little AlterBoy", "Eq8"]),
                        ("MasterTrack", "Master", ["Limiter"]),
                    ],
                    samples=["Kick.wav", "Clap.wav", "VocalChop_01.wav"],
                ),
                f"{base}/{base}.cpr": fx.make_cpr(
                    bpm=132.0,
                    tracks=[
                        ("MidiTrack", "Synth Lead"),
                        ("MidiTrack", "Pad"),
                        ("AudioTrack", "Drums"),
                        ("AudioTrack", "Vocal Chops"),
                    ],
                ),
                f"{base}/{base}.rpp": fx.make_rpp(
                    bpm=132.0,
                    tracks=[
                        ("Drums", "VST3:ReaComp (Cockos)"),
                        ("Synth Lead", "VST3:Serum (Xfer Records)"),
                        ("Pad", "VST3:Vital (Matt Tytel)"),
                    ],
                ),
                f"{base}/{base}.flp": fx.make_flp(bpm=132.0),
                f"{base}/README.md": (
                    "# Neon Dreams\n\nDemo project for SoundHub.\n\n"
                    "## Track plan\n- Synth lead (Serum)\n- Pad (Vital)\n"
                    "- Drums (808 kit)\n- Vocal chops\n\n"
                    "Arrangement v2: 132 BPM, added pad + vocal chops.\n"
                ).encode(),
            },
        )

        commits = sorted(project.commits, key=lambda c: c.id)
        print(f"Seeded demo project '{project.name}' for user 'demo' (password: demo123)")
        print(f"  commits: {len(commits)}")
        for c in commits:
            total = sum(f.size for f in c.files)
            print(f"  - #{c.id} {c.message}  ({len(c.files)} files, {total} bytes)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
