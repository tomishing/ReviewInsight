"""Per-review extraction: sentiment, pain points, positives, requests."""

from collections.abc import Sequence
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

from app.analysis.prompts import EXTRACT_SYSTEM, EXTRACT_USER

BATCH_SIZE = 50
MAX_BODY_CHARS = 2000


class ReviewInput(BaseModel):
    review_id: str
    rating: int | None
    title: str | None
    body: str


class ReviewExtraction(BaseModel):
    review_id: str
    sentiment: Literal["positive", "neutral", "negative"]
    pain_points: list[str]
    positives: list[str]
    requests: list[str]


class ExtractionBatch(BaseModel):
    results: list[ReviewExtraction]


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, u: anthropic.types.Usage) -> None:
        self.input_tokens += u.input_tokens
        self.output_tokens += u.output_tokens


def _format_reviews(batch: Sequence[ReviewInput]) -> str:
    parts = []
    for r in batch:
        stars = f"{r.rating}★" if r.rating else "no rating"
        title = f" | {r.title}" if r.title else ""
        parts.append(f"[{r.review_id}] ({stars}){title}\n{r.body[:MAX_BODY_CHARS]}")
    return "\n\n".join(parts)


def _extract_batch(
    client: anthropic.Anthropic,
    model: str,
    app_name: str,
    batch: Sequence[ReviewInput],
    usage: Usage,
) -> list[ReviewExtraction]:
    """One API call for a batch; retry once on invalid / incomplete output."""
    expected = {r.review_id for r in batch}
    last_err: Exception | None = None
    for _ in range(2):
        try:
            resp = client.messages.parse(
                model=model,
                max_tokens=16000,
                system=EXTRACT_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": EXTRACT_USER.format(
                            app_name=app_name, reviews=_format_reviews(batch)
                        ),
                    }
                ],
                output_format=ExtractionBatch,
            )
            usage.add(resp.usage)
            if resp.stop_reason != "end_turn" or resp.parsed_output is None:
                raise ValueError(f"unusable response (stop_reason={resp.stop_reason})")
            results = [r for r in resp.parsed_output.results if r.review_id in expected]
            if len(results) < len(expected) * 0.9:
                raise ValueError(f"only {len(results)}/{len(expected)} reviews returned")
            return results
        except (ValidationError, ValueError) as e:
            last_err = e
    raise RuntimeError(f"extraction failed after retry: {last_err}")


def extract_reviews(
    client: anthropic.Anthropic,
    model: str,
    app_name: str,
    reviews: Sequence[ReviewInput],
    usage: Usage,
    on_progress=None,
) -> list[ReviewExtraction]:
    out: list[ReviewExtraction] = []
    for i in range(0, len(reviews), BATCH_SIZE):
        batch = reviews[i : i + BATCH_SIZE]
        out.extend(_extract_batch(client, model, app_name, batch, usage))
        if on_progress:
            on_progress(min(i + BATCH_SIZE, len(reviews)), len(reviews))
    return out
