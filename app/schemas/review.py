from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional


class CategoryOut(BaseModel):
    id: str
    name: str
    slug: str
    icon: str | None

    model_config = {"from_attributes": True}


class TagOut(BaseModel):
    id: str
    name: str
    slug: str

    model_config = {"from_attributes": True}


class ReviewBase(BaseModel):
    title: str
    tagline: str
    body: str
    verdict: str
    product_slug: str
    category_id: Optional[str] = None
    release_date: Optional[date] = None
    platforms: Optional[str] = None
    external_url: Optional[str] = None
    hero_image_url: Optional[str] = None
    status: str = "draft"
    tags: list[str] = []  # list of tag slugs


class ReviewCreate(ReviewBase):
    slug: Optional[str] = None


class ReviewUpdate(BaseModel):
    title: Optional[str] = None
    tagline: Optional[str] = None
    body: Optional[str] = None
    verdict: Optional[str] = None
    category_id: Optional[str] = None
    release_date: Optional[date] = None
    platforms: Optional[str] = None
    external_url: Optional[str] = None
    hero_image_url: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None


class ReviewOut(BaseModel):
    id: str
    product_slug: str
    title: str
    slug: str
    tagline: str
    body: str
    hero_image_url: str | None
    verdict: str
    category: CategoryOut | None
    release_date: date | None
    platforms: str | None
    external_url: str | None
    status: str
    is_pinned: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    upvote_count: int
    comment_count: int
    tags: list[TagOut] = []
    user_has_upvoted: bool = False
    user_has_bookmarked: bool = False

    model_config = {"from_attributes": True}


class ReviewListOut(BaseModel):
    id: str
    product_slug: str
    title: str
    slug: str
    tagline: str
    hero_image_url: str | None
    verdict: str
    category: CategoryOut | None
    release_date: date | None
    platforms: str | None
    status: str
    is_pinned: bool
    published_at: datetime | None
    upvote_count: int
    comment_count: int
    tags: list[TagOut] = []
    user_has_upvoted: bool = False
    user_has_bookmarked: bool = False

    model_config = {"from_attributes": True}


class PaginatedReviews(BaseModel):
    items: list[ReviewListOut]
    total: int
    page: int
    per_page: int
    pages: int


class CommentAuthor(BaseModel):
    id: str
    display_name: str
    avatar_url: str | None

    model_config = {"from_attributes": True}


class CommentOut(BaseModel):
    id: str
    review_id: str
    user: CommentAuthor
    body: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    body: str


class CommentUpdate(BaseModel):
    body: str
