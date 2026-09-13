# Rollout Report — Backend

FastAPI backend for [Rollout Report](https://github.com/ChandanaVeeturi/Rollout-report-frontend), an admin-curated software review publication. Provides a REST API consumed by the React frontend.

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT — python-jose + bcrypt |
| Rate limiting | slowapi |
| Deployment | Railway |

## Project structure

```
app/
├── core/
│   ├── config.py        # Pydantic Settings — all env vars
│   ├── deps.py          # FastAPI dependencies (get_current_user, etc.)
│   ├── limiter.py       # slowapi rate limiter instance
│   └── security.py      # password hashing, JWT creation/decoding
├── models/
│   ├── user.py          # User model
│   └── review.py        # Review, Category, Tag, Upvote, Bookmark, Comment
├── routers/
│   ├── auth.py          # /api/auth — register, login, refresh, me
│   ├── reviews.py       # /api/reviews — public feed + interactions
│   ├── categories.py    # /api/categories — list categories
│   └── admin.py         # /api/admin — admin-only CRUD
├── schemas/
│   ├── auth.py          # Pydantic schemas for auth endpoints
│   └── review.py        # Pydantic schemas for reviews
├── database.py          # SQLAlchemy engine + session + Base
└── main.py              # App factory, middleware, startup seed
```

## Local setup

**Requirements:** Python 3.12+

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env — change SECRET_KEY and ADMIN_PASSWORD at minimum

uvicorn app.main:app --reload
```

API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

On first startup the server auto-creates all tables and seeds:
- An admin user (`ADMIN_EMAIL` / `ADMIN_PASSWORD` from env)
- Default categories: Dev Tools, Productivity, Design, AI Tools, Security, DevOps, Mobile

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./rollout_report.db` | SQLite for dev, PostgreSQL URL for prod |
| `SECRET_KEY` | — | **Required in prod.** Random 32+ char string |
| `ADMIN_EMAIL` | `admin@rolloutreport.com` | Admin account email |
| `ADMIN_PASSWORD` | — | **Required in prod.** Admin account password |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | JWT refresh token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

The server prints a warning on startup if `SECRET_KEY` or `ADMIN_PASSWORD` are still set to insecure defaults.

## API reference

### Auth — `/api/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/register` | — | Register new user (rate limited: 5/min) |
| POST | `/login` | — | Login, returns access + refresh tokens (rate limited: 10/min) |
| POST | `/refresh` | — | Exchange refresh token for new token pair |
| GET | `/me` | Bearer | Get current user |

### Reviews — `/api/reviews`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | Optional | List reviews. Query params: `sort` (recent/popular/trending), `category`, `verdict`, `platform`, `tag`, `q`, `page`, `per_page` |
| GET | `/{slug}` | Optional | Get single review |
| POST | `/{slug}/upvote` | Required | Toggle upvote |
| POST | `/{slug}/bookmark` | Required | Toggle bookmark |
| GET | `/bookmarks` | Required | List current user's bookmarked reviews |
| GET | `/{slug}/comments` | — | List comments |
| POST | `/{slug}/comments` | Required | Post comment |
| PATCH | `/{slug}/comments/{id}` | Required | Edit comment (15-min window) |
| DELETE | `/{slug}/comments/{id}` | Required | Delete comment (own or admin) |

### Categories — `/api/categories`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | — | List all categories |

### Admin — `/api/admin`

All admin endpoints require a valid JWT from an `is_admin=true` user.

| Method | Path | Description |
|---|---|---|
| GET | `/reviews` | Paginated review list (all statuses) |
| POST | `/reviews` | Create review |
| PATCH | `/reviews/{slug}` | Update review |
| DELETE | `/reviews/{slug}` | Delete review |
| POST | `/reviews/{slug}/pin` | Toggle Review of the Day pin |
| POST | `/categories` | Create category |
| GET | `/users` | List all users |
| POST | `/users/{id}/ban` | Ban user |
| DELETE | `/users/{id}/ban` | Unban user |

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Returns `{"status": "ok"}` — used by Railway healthcheck |

## Trending algorithm

The trending sort uses an HN-style time-decay score computed in Python:

```
score = (upvote_count + 1) / (age_hours + 2) ^ 1.5
```

All matching reviews are fetched, scored, sorted, then paginated in memory.

## Deployment (Railway)

1. Create a new Railway project and add a PostgreSQL plugin.
2. Set environment variables in the Railway service:
   - `DATABASE_URL` — copy the PostgreSQL connection string from the plugin
   - `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD`
   - `CORS_ORIGINS` — your frontend's Vercel URL
3. Connect the GitHub repo. Railway uses `railway.toml` for the start command and healthcheck path.

The server refuses to start on Railway if `DATABASE_URL` is not set (SQLite on Railway's ephemeral filesystem would lose all data on every redeploy).

## Notes

- No Alembic migrations yet — the app uses `Base.metadata.create_all()`. Drop and recreate `rollout_report.db` locally after schema changes.
- Never commit `rollout_report.db` or `.env`.
- All queries go through SQLAlchemy ORM — no raw SQL.
