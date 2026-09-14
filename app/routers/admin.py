import unicodedata
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.review import Review, Category, Tag, ReviewTag
from app.models.user import User
from app.models.blog import BlogQA
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewOut, ReviewListOut, CategoryOut, CategoryCreate, PaginatedReviews
from app.schemas.blog import BlogQACreate, BlogQAUpdate, BlogQAOut
from app.core.deps import require_admin
from datetime import datetime, timezone
import math

router = APIRouter(prefix="/api/admin", tags=["admin"])


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = re.sub(r"[^\w\s.-]", "", text)
    text = re.sub(r"[.\s_-]+", "-", text)
    return text.strip("-")


def _sync_tags(review: Review, tag_slugs: list[str], db: Session):
    db.query(ReviewTag).filter(ReviewTag.review_id == review.id).delete()
    for slug in tag_slugs:
        tag = db.query(Tag).filter(Tag.slug == slug).first()
        if not tag:
            tag = Tag(id=str(uuid.uuid4()), name=slug.replace("-", " ").title(), slug=slug)
            db.add(tag)
            db.flush()
        db.add(ReviewTag(review_id=review.id, tag_id=tag.id))


@router.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    slug = payload.slug or slugify(payload.title)
    base, counter = slug, 1
    while db.query(Review).filter(Review.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1

    review = Review(
        id=str(uuid.uuid4()),
        product_slug=payload.product_slug or slugify(payload.title.rsplit(" ", 1)[0]),
        title=payload.title,
        slug=slug,
        tagline=payload.tagline,
        body=payload.body,
        hero_image_url=payload.hero_image_url,
        verdict=payload.verdict,
        category_id=payload.category_id,
        release_date=payload.release_date,
        platforms=payload.platforms,
        external_url=payload.external_url,
        status=payload.status,
    )
    if payload.status == "published":
        review.published_at = datetime.now(timezone.utc)

    db.add(review)
    db.flush()
    _sync_tags(review, payload.tags, db)
    db.commit()
    db.refresh(review)
    from sqlalchemy.orm import joinedload
    review = db.query(Review).options(
        joinedload(Review.category), joinedload(Review.review_tags).joinedload(ReviewTag.tag)
    ).filter(Review.id == review.id).first()
    return ReviewOut(
        **{c.name: getattr(review, c.name) for c in review.__table__.columns},
        category=review.category,
        tags=[rt.tag for rt in review.review_tags],
    )


@router.patch("/reviews/{slug}", response_model=ReviewOut)
def update_review(
    slug: str,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from sqlalchemy.orm import joinedload
    review = db.query(Review).filter(Review.slug == slug).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    for field, value in payload.model_dump(exclude_none=True, exclude={"tags"}).items():
        setattr(review, field, value)

    if payload.status == "published" and not review.published_at:
        review.published_at = datetime.now(timezone.utc)

    if payload.tags is not None:
        _sync_tags(review, payload.tags, db)

    review.updated_at = datetime.now(timezone.utc)
    db.commit()
    review = db.query(Review).options(
        joinedload(Review.category), joinedload(Review.review_tags).joinedload(ReviewTag.tag)
    ).filter(Review.id == review.id).first()
    return ReviewOut(
        **{c.name: getattr(review, c.name) for c in review.__table__.columns},
        category=review.category,
        tags=[rt.tag for rt in review.review_tags],
    )


@router.delete("/reviews/{slug}", status_code=204)
def delete_review(slug: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    review = db.query(Review).filter(Review.slug == slug).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()


@router.post("/reviews/{slug}/pin")
def pin_review(slug: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    review = db.query(Review).filter(Review.slug == slug).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.is_pinned:
        review.is_pinned = False
        db.commit()
        return {"pinned": False}
    # Unpin all first, then pin the target
    for r in db.query(Review).filter(Review.is_pinned == True).all():
        r.is_pinned = False
    review.is_pinned = True
    db.commit()
    return {"pinned": True}


@router.get("/reviews", response_model=PaginatedReviews)
def admin_list_reviews(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from sqlalchemy.orm import joinedload
    query = db.query(Review).options(
        joinedload(Review.category), joinedload(Review.review_tags).joinedload(ReviewTag.tag)
    ).order_by(Review.created_at.desc())

    total = query.count()
    reviews = query.offset((page - 1) * per_page).limit(per_page).all()
    items = [
        ReviewListOut(
            **{c.name: getattr(r, c.name) for c in r.__table__.columns},
            category=r.category,
            tags=[rt.tag for rt in r.review_tags],
        )
        for r in reviews
    ]
    return PaginatedReviews(items=items, total=total, page=page, per_page=per_page, pages=max(1, math.ceil(total / per_page)))


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    slug = slugify(payload.name)
    if db.query(Category).filter(Category.slug == slug).first():
        raise HTTPException(status_code=400, detail="Category already exists")
    cat = Category(id=str(uuid.uuid4()), name=payload.name, slug=slug, icon=payload.icon)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.post("/users/{user_id}/ban", status_code=204)
def ban_user(user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = True
    db.commit()


@router.delete("/users/{user_id}/ban", status_code=204)
def unban_user(user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_banned = False
    db.commit()


# ── Blog Q&A (admin-only prep material, never exposed to guests) ────────────

@router.get("/blog", response_model=list[BlogQAOut])
def list_blog_qa(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(BlogQA).order_by(BlogQA.created_at.desc()).all()


@router.post("/blog", response_model=BlogQAOut, status_code=201)
def create_blog_qa(payload: BlogQACreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    entry = BlogQA(id=str(uuid.uuid4()), question=payload.question.strip(), answer="")
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/blog/{entry_id}", response_model=BlogQAOut)
def update_blog_qa(entry_id: str, payload: BlogQAUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    entry = db.query(BlogQA).filter(BlogQA.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if payload.question is not None:
        if not payload.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        entry.question = payload.question.strip()
    if payload.answer is not None:
        entry.answer = payload.answer
    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/blog/{entry_id}", status_code=204)
def delete_blog_qa(entry_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    entry = db.query(BlogQA).filter(BlogQA.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
