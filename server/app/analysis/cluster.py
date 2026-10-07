"""Cluster extracted phrases into themes per type (pain / positive / request)."""

from collections.abc import Sequence
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

from app.analysis.extract import ReviewExtraction, Usage
from app.analysis.prompts import CLUSTER_SYSTEM, CLUSTER_USER

ThemeType = Literal["pain", "positive", "request"]

_FIELD: dict[str, str] = {"pain": "pain_points", "positive": "positives", "request": "requests"}
_KIND: dict[str, str] = {"pain": "Pain point", "positive": "Positive", "request": "Feature request"}


class ClusterTheme(BaseModel):
    label: str
    description: str
    generic: bool
    phrase_ids: list[int]


class ClusterResult(BaseModel):
    themes: list[ClusterTheme]


class Theme(BaseModel):
    type: ThemeType
    label: str
    description: str
    generic: bool
    review_count: int
    review_ids: list[str]
    example_phrases: list[str]


def cluster_type(
    client: anthropic.Anthropic,
    model: str,
    theme_type: ThemeType,
    extractions: Sequence[ReviewExtraction],
    usage: Usage,
) -> list[Theme]:
    # Flatten to (phrase, review_id); ids in the prompt are 1-based list positions.
    items: list[tuple[str, str]] = [
        (p, e.review_id) for e in extractions for p in getattr(e, _FIELD[theme_type])
    ]
    if not items:
        return []
    kind = _KIND[theme_type]
    phrases = "\n".join(f"{i}. {p}" for i, (p, _) in enumerate(items, 1))

    last_err: Exception | None = None
    for _ in range(2):
        try:
            resp = client.messages.parse(
                model=model,
                max_tokens=16000,
                system=CLUSTER_SYSTEM.format(kind=kind.lower()),
                messages=[
                    {"role": "user", "content": CLUSTER_USER.format(kind=kind, phrases=phrases)}
                ],
                output_format=ClusterResult,
            )
            usage.add(resp.usage)
            if resp.stop_reason != "end_turn" or resp.parsed_output is None:
                raise ValueError(f"unusable response (stop_reason={resp.stop_reason})")
            break
        except (ValidationError, ValueError) as e:
            last_err = e
    else:
        raise RuntimeError(f"clustering {theme_type} failed after retry: {last_err}")

    themes: list[Theme] = []
    assigned: set[int] = set()  # the model sometimes repeats a phrase id; first theme wins
    for t in resp.parsed_output.themes:
        idx = sorted({i - 1 for i in t.phrase_ids if 1 <= i <= len(items)} - assigned)
        assigned.update(idx)
        if not idx:
            continue
        review_ids = list(dict.fromkeys(items[i][1] for i in idx))
        themes.append(
            Theme(
                type=theme_type,
                label=t.label,
                description=t.description,
                generic=t.generic,
                review_count=len(review_ids),
                review_ids=review_ids,
                example_phrases=list(dict.fromkeys(items[i][0] for i in idx))[:3],
            )
        )
    themes.sort(key=lambda t: t.review_count, reverse=True)
    return themes


def cluster_all(
    client: anthropic.Anthropic,
    model: str,
    extractions: Sequence[ReviewExtraction],
    usage: Usage,
) -> dict[str, list[Theme]]:
    return {
        t: cluster_type(client, model, t, extractions, usage)
        for t in ("pain", "positive", "request")
    }
