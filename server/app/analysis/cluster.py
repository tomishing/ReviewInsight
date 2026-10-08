"""Cluster extracted phrases into themes per type (pain / positive / request).

Small phrase sets: one call returns themes with their phrase ids.
Large sets (where listing every phrase id would overflow the output): one call defines the
themes, then phrases are assigned to them in batches. In both cases phrases the model left
out are assigned in a follow-up batch, so nothing is silently dropped.
"""

from collections.abc import Sequence
from typing import Literal, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.analysis.extract import ReviewExtraction, Usage
from app.analysis.prompts import (
    CLUSTER_ASSIGN_SYSTEM,
    CLUSTER_ASSIGN_USER,
    CLUSTER_DEFINE_SYSTEM,
    CLUSTER_DEFINE_USER,
    CLUSTER_SYSTEM,
    CLUSTER_USER,
)

ThemeType = Literal["pain", "positive", "request"]

_FIELD: dict[str, str] = {"pain": "pain_points", "positive": "positives", "request": "requests"}
_KIND: dict[str, str] = {"pain": "Pain point", "positive": "Positive", "request": "Feature request"}

SINGLE_CALL_MAX = 250  # above this many distinct phrases, define-then-assign
ASSIGN_BATCH = 250

# (phrase text, review ids that used it)
Item = tuple[str, list[str]]
M = TypeVar("M", bound=BaseModel)


class ClusterTheme(BaseModel):
    label: str
    description: str
    generic: bool
    phrase_ids: list[int]


class ClusterResult(BaseModel):
    themes: list[ClusterTheme]


class ThemeDef(BaseModel):
    label: str
    description: str
    generic: bool


class ThemeDefs(BaseModel):
    themes: list[ThemeDef]


class Assignment(BaseModel):
    phrase_id: int
    theme_id: int


class Assignments(BaseModel):
    assignments: list[Assignment]


class Theme(BaseModel):
    type: ThemeType
    label: str
    description: str
    generic: bool
    review_count: int
    review_ids: list[str]
    example_phrases: list[str]


def _parse(
    client: anthropic.Anthropic, model: str, system: str, user: str, out: type[M], usage: Usage
) -> M:
    """One structured call, retried once on invalid or truncated output."""
    last_err: Exception | None = None
    for _ in range(2):
        try:
            resp = client.messages.parse(
                model=model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=out,
            )
            usage.add(resp.usage)
            if resp.stop_reason != "end_turn" or resp.parsed_output is None:
                raise ValueError(f"unusable response (stop_reason={resp.stop_reason})")
            return resp.parsed_output
        except (ValidationError, ValueError) as e:
            last_err = e
    raise RuntimeError(f"failed after retry: {last_err}")


def _single_call(
    client: anthropic.Anthropic, model: str, kind: str, items: list[Item], usage: Usage
) -> tuple[list[ThemeDef], dict[int, int]]:
    """Themes and their phrase ids in one call. Returns (themes, phrase index -> theme index)."""
    phrases = "\n".join(f"{i}. {p}" for i, (p, _) in enumerate(items, 1))
    result = _parse(
        client,
        model,
        CLUSTER_SYSTEM.format(kind=kind.lower()),
        CLUSTER_USER.format(kind=kind, phrases=phrases),
        ClusterResult,
        usage,
    )
    defs: list[ThemeDef] = []
    assignment: dict[int, int] = {}
    for t in result.themes:
        defs.append(ThemeDef(label=t.label, description=t.description, generic=t.generic))
        for pid in t.phrase_ids:
            if 1 <= pid <= len(items):
                assignment.setdefault(pid - 1, len(defs) - 1)  # a repeated id: first theme wins
    return defs, assignment


def _define(
    client: anthropic.Anthropic, model: str, kind: str, items: list[Item], usage: Usage
) -> list[ThemeDef]:
    """Themes only (small output), from every phrase and how often it was used."""
    phrases = "\n".join(
        f"{i}. {p}" + (f" ×{len(r)}" if len(r) > 1 else "") for i, (p, r) in enumerate(items, 1)
    )
    result = _parse(
        client,
        model,
        CLUSTER_DEFINE_SYSTEM.format(kind=kind.lower()),
        CLUSTER_DEFINE_USER.format(kind=kind, phrases=phrases),
        ThemeDefs,
        usage,
    )
    if not result.themes:
        raise RuntimeError("no themes defined")
    return result.themes


def _assign(
    client: anthropic.Anthropic,
    model: str,
    kind: str,
    defs: list[ThemeDef],
    items: list[Item],
    indices: list[int],
    usage: Usage,
) -> dict[int, int]:
    """Assign the given phrase indices to themes in batches; one retry for any left out."""
    themes = "\n".join(
        f"{t}. {d.label}" + (" [generic]" if d.generic else "") + f" — {d.description}"
        for t, d in enumerate(defs, 1)
    )
    assignment: dict[int, int] = {}

    def run(batch: list[int]) -> None:
        phrases = "\n".join(f"[{i + 1}] {items[i][0]}" for i in batch)
        result = _parse(
            client,
            model,
            CLUSTER_ASSIGN_SYSTEM,
            CLUSTER_ASSIGN_USER.format(themes=themes, kind=kind, phrases=phrases),
            Assignments,
            usage,
        )
        wanted = set(batch)
        for a in result.assignments:
            i, t = a.phrase_id - 1, a.theme_id - 1
            if i in wanted and 0 <= t < len(defs):
                assignment.setdefault(i, t)

    for start in range(0, len(indices), ASSIGN_BATCH):
        run(indices[start : start + ASSIGN_BATCH])
    missing = [i for i in indices if i not in assignment]
    if missing:
        run(missing)
    return assignment


def cluster_type(
    client: anthropic.Anthropic,
    model: str,
    theme_type: ThemeType,
    extractions: Sequence[ReviewExtraction],
    usage: Usage,
) -> list[Theme]:
    # Distinct phrases (case-insensitive), each with the reviews that used it.
    # Ids in prompts are 1-based positions in `items`.
    by_key: dict[str, Item] = {}
    for e in extractions:
        for p in getattr(e, _FIELD[theme_type]):
            text = " ".join(p.split())
            if text:
                by_key.setdefault(text.lower(), (text, []))[1].append(e.review_id)
    items = list(by_key.values())
    if not items:
        return []
    kind = _KIND[theme_type]

    try:
        if len(items) <= SINGLE_CALL_MAX:
            defs, assignment = _single_call(client, model, kind, items, usage)
        else:
            defs, assignment = _define(client, model, kind, items, usage), {}
        missing = [i for i in range(len(items)) if i not in assignment]
        if missing:
            assignment.update(_assign(client, model, kind, defs, items, missing, usage))
    except RuntimeError as e:
        raise RuntimeError(f"clustering {theme_type}: {e}") from None

    members: dict[int, list[int]] = {}
    for i, t in assignment.items():
        members.setdefault(t, []).append(i)
    themes: list[Theme] = []
    for t, idx in members.items():
        review_ids = list(dict.fromkeys(r for i in idx for r in items[i][1]))
        most_used = sorted(idx, key=lambda i: len(items[i][1]), reverse=True)
        d = defs[t]
        themes.append(
            Theme(
                type=theme_type,
                label=d.label,
                description=d.description,
                generic=d.generic,
                review_count=len(review_ids),
                review_ids=review_ids,
                example_phrases=[items[i][0] for i in most_used[:3]],
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
