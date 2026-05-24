from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.review import Review, Category, Tag, ReviewTag
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewOut, ReviewListOut, CategoryOut
from app.core.deps import require_admin
from datetime import datetime, timezone
import uuid
import re

router = APIRouter(prefix="/api/admin", tags=["admin"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def _sync_tags(review: Review, tag_slugs: list[str], db: Session):
    # Remove existing
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
    # ensure unique slug
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
    # unpin all first
    db.query(Review).update({Review.is_pinned: False})
    review = db.query(Review).filter(Review.slug == slug).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.is_pinned = True
    db.commit()
    return {"pinned": True}


@router.get("/reviews", response_model=list[ReviewListOut])
def admin_list_reviews(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from sqlalchemy.orm import joinedload
    reviews = db.query(Review).options(
        joinedload(Review.category), joinedload(Review.review_tags).joinedload(ReviewTag.tag)
    ).order_by(Review.created_at.desc()).all()
    return [
        ReviewListOut(
            **{c.name: getattr(r, c.name) for c in r.__table__.columns},
            category=r.category,
            tags=[rt.tag for rt in r.review_tags],
        )
        for r in reviews
    ]


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    name: str, icon: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    slug = slugify(name)
    if db.query(Category).filter(Category.slug == slug).first():
        raise HTTPException(status_code=400, detail="Category already exists")
    cat = Category(id=str(uuid.uuid4()), name=name, slug=slug, icon=icon)
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
