from datetime import datetime

from pydantic import BaseModel, field_validator


class FetchedReview(BaseModel):
    store: str
    store_review_id: str
    rating: int | None
    title: str | None
    body: str
    app_version: str | None
    country: str
    review_date: datetime | None

    @field_validator("rating")
    @classmethod
    def rating_in_range(cls, v: int | None) -> int | None:
        return v if v is not None and 1 <= v <= 5 else None  # DB CHECK allows only 1-5
