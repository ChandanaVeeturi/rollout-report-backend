from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database import Base, engine
from app.routers import auth, reviews, categories, admin

import os, sys

# Railway sets RAILWAY_ENVIRONMENT automatically. Bail out early if DATABASE_URL
# wasn't configured — silently falling back to SQLite on an ephemeral filesystem
# means all data is wiped on every deploy.
if os.getenv("RAILWAY_ENVIRONMENT") and settings.DATABASE_URL.startswith("sqlite"):
    print("FATAL: Running on Railway but DATABASE_URL is not set — would use SQLite "
          "on an ephemeral filesystem. Set DATABASE_URL in Railway service variables.", file=sys.stderr)
    sys.exit(1)

app = FastAPI(title="Rollout Report API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(reviews.router)
app.include_router(categories.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    _seed_initial_data()


def _seed_initial_data():
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.review import Category
    from app.core.security import hash_password
    import uuid

    db = SessionLocal()
    try:
        # Create admin user if not exists
        if not db.query(User).filter(User.email == settings.ADMIN_EMAIL).first():
            db.add(User(
                id=str(uuid.uuid4()),
                email=settings.ADMIN_EMAIL,
                display_name="Admin",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                is_admin=True,
                email_verified=True,
            ))

        # Seed categories
        default_categories = [
            ("Dev Tools", "dev-tools", "🛠️"),
            ("Productivity", "productivity", "⚡"),
            ("Design", "design", "🎨"),
            ("AI Tools", "ai-tools", "🤖"),
            ("Security", "security", "🔒"),
            ("DevOps", "devops", "📡"),
            ("Mobile", "mobile", "📱"),
        ]
        for name, slug, icon in default_categories:
            if not db.query(Category).filter(Category.slug == slug).first():
                db.add(Category(id=str(uuid.uuid4()), name=name, slug=slug, icon=icon))

        db.commit()
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}
