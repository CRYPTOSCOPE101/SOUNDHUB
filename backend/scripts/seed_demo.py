"""Seed the database with demo data for local development."""
import sys, os, secrets
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import get_db, init_db
from app.models import User, Project, Branch, ReviewSession, ReviewVersion
from app.security import hash_password

def seed():
    init_db()
    db = next(get_db())

    # 1. Create demo user
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(
            username="demo",
            password_hash=hash_password("demo123"),
            bio="SoundHub demo engineer",
            specialty="Mixing & Mastering",
            location="Berlin, DE",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Created user: demo (password: demo123)")
    else:
        print(f"ℹ️  User 'demo' already exists")

    # 2. Create sample projects
    projects_data = [
        ("Neon Warehouse", "neon-warehouse", "Deep house EP — 4 tracks"),
        ("Acoustic Sessions", "acoustic-sessions", "Live recording — solo guitar"),
        ("Bass Culture", "bass-culture", "Drum & bass single"),
    ]
    for name, slug, desc in projects_data:
        if not db.query(Project).filter(Project.name == name).first():
            p = Project(name=name, slug=slug, description=desc, owner_id=user.id)
            db.add(p)
            db.commit()
            db.refresh(p)
            # Add main branch
            db.add(Branch(project_id=p.id, name="main"))
            db.commit()
            print(f"✅ Created project: {name}")

    # 3. Create sample review sessions
    projects = db.query(Project).filter(Project.owner_id == user.id).all()
    sessions_data = [
        ("Neon Warehouse — Mix v1", projects[0].id if len(projects) > 0 else None),
        ("Acoustic Sessions — Raw Take", projects[1].id if len(projects) > 1 else None),
        ("Bass Culture — Master Review", projects[2].id if len(projects) > 2 else None),
    ]
    for name, pid in sessions_data:
        if not db.query(ReviewSession).filter(ReviewSession.name == name).first():
            token = secrets.token_urlsafe(32)
            s = ReviewSession(name=name, owner_id=user.id, project_id=pid, share_token=token)
            db.add(s)
            db.commit()
            print(f"✅ Created session: {name} (token: {token[:12]}...)")

    db.close()
    print("\n🎉 Demo data seeded!")
    print("   Login: demo / demo123")

if __name__ == "__main__":
    seed()
