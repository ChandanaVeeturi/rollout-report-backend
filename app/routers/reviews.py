from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from app.database import get_db
from app.models.review import Review, Upvote, Bookmark, Comment, Tag, ReviewTag
from app.models.user import User
from app.schemas.review import ReviewOut, ReviewListOut, PaginatedReviews, CommentOut, CommentCreate, CommentUpdate
from app.core.deps import get_current_user, get_current_user_optional
from datetime import datetime, timezone
import math

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _enrich(review: Review, user: User | None, db: Session) -> dict:
    d = {c.name: getattr(review, c.name) for c in review.__table__.columns}
    d["category"] = review.category
    d["tags"] = [rt.tag for rt in review.review_tags]
    d["user_has_upvoted"] = False
    d["user_has_bookmarked"] = False
    if user:
        d["user_has_upvoted"] = db.query(Upvote).filter_by(user_id=user.id, review_id=review.id).first() is not None
        d["user_has_bookmarked"] = db.query(Bookmark).filter_by(user_id=user.id, review_id=review.id).first() is not None
    return d


@router.get("", response_model=PaginatedReviews)
def list_reviews(
    sort: str = Query("recent", enum=["recent", "popular", "trending"]),
    category: str | None = None,
    verdict: str | None = None,
    platform: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    query = (
        db.query(Review)
        .options(joinedload(Review.category), joinedload(Review.review_tags).joinedload(ReviewTag.tag))
        .filter(Review.status == "published")
    )
    if category:
        from app.models.review import Category
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
            query = query.filter(Review.category_id == cat.id)
    if verdict:
        query = query.filter(Review.verdict == verdict)
    if platform:
        query = query.filter(Review.platforms.ilike(f"%{platform}%"))
    if q:
        query = query.filter(
            or_(Review.title.ilike(f"%{q}%"), Review.tagline.ilike(f"%{q}%"), Review.body.ilike(f"%{q}%"))
        )

    if sort == "popular":
        query = query.order_by(Review.upvote_count.desc(), Review.published_at.desc())
    elif sort == "trending":
        query = query.order_by(Review.upvote_count.desc(), Review.published_at.desc())
    else:
        query = query.order_by(Review.is_pinned.desc(), Review.published_at.desc())

    total = query.count()
    reviews = query.offset((page - 1) * per_page).limit(per_page).all()
    items = [ReviewListOut(**_enrich(r, current_user, db)) for r in reviews]
    return PaginatedReviews(items=items, total=total, page=page, per_page=per_page, pages=max(1, math.ceil(total / per_page)))


@router.get("/bookmarks", response_model=list[ReviewListOut])
def get_bookmarks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bookmarks = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == current_user.id)
        .order_by(Bookmark.created_at.desc())
        .all()
    )
    review_ids = [b.review_id for b in bookmarks]
    if not review_ids:
        return []
    reviews = (
        db.query(Review)
        .options(joinedload(Review.category), joinedload(Review.review_tags).joinedload(ReviewTag.tag))
        .filter(Review.id.in_(review_ids))
        .all()
    )
    order = {rid: i for i, rid in enumerate(review_ids)}
    reviews.sort(key=lambda r: order[r.id])
    return [
        ReviewListOut(
            **{c.name: getattr(r, c.name) for c in r.__table__.columns},
            category=r.category,
            tags=[rt.tag for rt in r.review_tags],
        )
        for r in reviews
    ]


@router.get("/{slug}", response_model=ReviewOut)
def get_review(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    review = (
        db.query(Review)
        .options(joinedload(Review.category), joinedload(Review.review_tags).joinedload(ReviewTag.tag))
        .filter(Review.slug == slug)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status != "published" and (not current_user or not current_user.is_admin):
        raise HTTPException(status_code=404, detail="Review not found")
    return ReviewOut(**_enrich(review, current_user, db))


@router.get("/{slug}/comments", response_model=list[CommentOut])
def get_comments(slug: str, db: Session = Depends(get_db)):
    review = db.query(Review).filter(Review.slug == slug).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    comments = (
        db.query(Comment)
        .options(joinedload(Comment.user))
        .filter(Comment.review_id == review.id)
        .order_by(Comment.created_at.desc())
        .all()
    )
    return comments


@router.post("/{slug}/comments", response_model=CommentOut, status_code=201)
def post_comment(
    slug: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = db.query(Review).filter(Review.slug == slug, Review.status == "published").first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if len(payload.body.strip()) == 0:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    if len(payload.body) > 2000:
        raise HTTPException(status_code=400, detail="Comment too long")

    import uuid
    comment = Comment(
        id=str(uuid.uuid4()),
        review_id=review.id,
        user_id=current_user.id,
        body=payload.body.strip(),
    )
    db.add(comment)
    review.comment_count += 1
    db.commit()
    db.refresh(comment)
    # reload with user
    comment = db.query(Comment).options(joinedload(Comment.user)).filter(Comment.id == comment.id).first()
    return comment


@router.patch("/{slug}/comments/{comment_id}", response_model=CommentOut)
def edit_comment(
    slug: str,
    comment_id: str,
    payload: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(Comment).options(joinedload(Comment.user)).filter(Comment.id == comment_id).first()
    if not comment or comment.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Comment not found")
    elapsed = (datetime.now(timezone.utc) - comment.created_at.replace(tzinfo=timezone.utc)).total_seconds()
    if elapsed > 900:
        raise HTTPException(status_code=403, detail="Edit window has passed (15 minutes)")
    comment.body = payload.body.strip()
    comment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/{slug}/comments/{comment_id}", status_code=204)
def delete_comment(
    slug: str,
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    review = db.query(Review).filter(Review.id == comment.review_id).first()
    comment.is_deleted = True
    comment.body = "[comment removed]"
    if review and review.comment_count > 0:
        review.comment_count -= 1
    db.commit()


@router.post("/{slug}/upvote")
def toggle_upvote(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = db.query(Review).filter(Review.slug == slug, Review.status == "published").first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    existing = db.query(Upvote).filter_by(user_id=current_user.id, review_id=review.id).first()
    if existing:
        db.delete(existing)
        review.upvote_count = max(0, review.upvote_count - 1)
        upvoted = False
    else:
        db.add(Upvote(user_id=current_user.id, review_id=review.id))
        review.upvote_count += 1
        upvoted = True
    db.commit()
    return {"upvoted": upvoted, "upvote_count": review.upvote_count}


@router.post("/{slug}/bookmark")
def toggle_bookmark(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = db.query(Review).filter(Review.slug == slug).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    existing = db.query(Bookmark).filter_by(user_id=current_user.id, review_id=review.id).first()
    if existing:
        db.delete(existing)
        bookmarked = False
    else:
        db.add(Bookmark(user_id=current_user.id, review_id=review.id))
        bookmarked = True
    db.commit()
    return {"bookmarked": bookmarked}
