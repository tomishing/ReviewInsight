"""Group per-app themes of one type into cross-app topics."""

from collections.abc import Sequence
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

from app.analysis.extract import Usage
from app.analysis.prompts import COMPARE_SYSTEM, COMPARE_USER

ThemeType = Literal["pain", "positive", "request"]
_KIND = {"pain": "Pain point", "positive": "Positive", "request": "Feature request"}


class ThemeRef(BaseModel):
    theme_id: int
    app_name: str
    label: str
    description: str | None


class CompareGroupOut(BaseModel):
    label: str
    description: str
    theme_ids: list[int]


class CompareResult(BaseModel):
    groups: list[CompareGroupOut]


class CompareGroup(BaseModel):
    label: str
    description: str | None
    theme_ids: list[int]  # database theme ids


def group_themes(
    client: anthropic.Anthropic,
    model: str,
    theme_type: ThemeType,
    themes: Sequence[ThemeRef],
    usage: Usage,
) -> list[CompareGroup]:
    if not themes:
        return []
    kind = _KIND[theme_type]
    listing = "\n".join(
        f"{i}. [{t.app_name}] {t.label}" + (f" — {t.description}" if t.description else "")
        for i, t in enumerate(themes, 1)
    )
    last_err: Exception | None = None
    for _ in range(2):
        try:
            resp = client.messages.parse(
                model=model,
                max_tokens=16000,
                system=COMPARE_SYSTEM.format(kind=kind.lower()),
                messages=[
                    {"role": "user", "content": COMPARE_USER.format(kind=kind, themes=listing)}
                ],
                output_format=CompareResult,
            )
            usage.add(resp.usage)
            if resp.stop_reason != "end_turn" or resp.parsed_output is None:
                raise ValueError(f"unusable response (stop_reason={resp.stop_reason})")
            break
        except (ValidationError, ValueError) as e:
            last_err = e
    else:
        raise RuntimeError(f"comparing {theme_type} themes failed after retry: {last_err}")

    groups: list[CompareGroup] = []
    assigned: set[int] = set()  # a repeated id counts for the first group only
    for g in resp.parsed_output.groups:
        idx = [i - 1 for i in dict.fromkeys(g.theme_ids) if 1 <= i <= len(themes)]
        idx = [i for i in idx if i not in assigned]
        assigned.update(idx)
        if idx:
            groups.append(
                CompareGroup(
                    label=g.label,
                    description=g.description,
                    theme_ids=[themes[i].theme_id for i in idx],
                )
            )
    # Nothing silently disappears: a theme the model left out becomes its own group.
    for i, t in enumerate(themes):
        if i not in assigned:
            groups.append(
                CompareGroup(label=t.label, description=t.description, theme_ids=[t.theme_id])
            )
    return groups
