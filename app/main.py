import os, sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.limiter import limiter
from app.database import Base, engine
from app.routers import auth, reviews, categories, admin

# On Railway, refuse to start with SQLite — ephemeral filesystem loses all data on redeploy
if os.getenv("RAILWAY_ENVIRONMENT") and settings.DATABASE_URL.startswith("sqlite"):
    print(
        "FATAL: Running on Railway but DATABASE_URL is not set — would use SQLite "
        "on an ephemeral filesystem. Set DATABASE_URL in Railway service variables.",
        file=sys.stderr,
    )
    sys.exit(1)

app = FastAPI(title="Rollout Report API", version="1.0.0")

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    _warn_insecure_defaults()
    Base.metadata.create_all(bind=engine)
    _seed_initial_data()


def _warn_insecure_defaults():
    if settings.SECRET_KEY == "dev-secret-key-change-in-production":
        print(
            "⚠️  WARNING: SECRET_KEY is using the insecure default. "
            "Set SECRET_KEY in your environment before deploying to production.",
            file=sys.stderr,
        )
    if settings.ADMIN_PASSWORD == "admin123":
        print(
            "⚠️  WARNING: ADMIN_PASSWORD is using the default 'admin123'. "
            "Set ADMIN_PASSWORD in your environment before deploying to production.",
            file=sys.stderr,
        )


def _seed_initial_data():
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.review import Category
    from app.core.security import hash_password
    import uuid

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.ADMIN_EMAIL).first():
            db.add(User(
                id=str(uuid.uuid4()),
                email=settings.ADMIN_EMAIL,
                display_name="Admin",
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                is_admin=True,
                email_verified=True,
            ))

        default_categories = [
            ("Dev Tools",    "dev-tools",    "🛠️"),
            ("Productivity", "productivity", "⚡"),
            ("Design",       "design",       "🎨"),
            ("AI Tools",     "ai-tools",     "🤖"),
            ("Security",     "security",     "🔒"),
            ("DevOps",       "devops",       "📡"),
            ("Mobile",       "mobile",       "📱"),
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
