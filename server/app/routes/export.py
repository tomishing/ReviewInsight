"""Markdown reports for the Obsidian vault (themes and counts only — no raw review text)."""

import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response

from app.routes.compare import TYPES, build_matrix
from app.routes.summary import summary

router = APIRouter(prefix="/api/export", tags=["export"])

TITLES = {"pain": "Pain points", "positive": "Positive points", "request": "Feature requests"}
TOP = 15


def _cell(text: Any) -> str:
    """Make a value safe inside a Markdown table cell."""
    return str(text).replace("|", "/").replace("\n", " ").strip()


def _share(x: float) -> str:
    """0.004 -> "0.4%", 0.012 -> "1.2%", 0.25 -> "25%": small shares never round to "0%"."""
    return f"{x:.1%}" if 0 < x < 0.1 else f"{x:.0%}"


def _pct(n: int, total: int) -> str:
    return _share(n / total) if total else "-"


def _day(v: Any) -> str:
    if isinstance(v, str):
        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    return f"{v:%Y-%m-%d}" if v else "-"


def _frontmatter(tags: list[str]) -> list[str]:
    return ["---", f"created: {date.today():%Y-%m-%d}", f"tags: [{', '.join(tags)}]", "---", ""]


def app_report(app_id: int) -> tuple[str, str]:
    s = summary(app_id, None, None, None)["data"]
    app, totals, sent = s["app"], s["totals"], s["sentiment"]
    analysed = sum(sent.values())
    sources = [
        f"Google Play `{app['play_id']}`" if app["play_id"] else None,
        f"App Store `{app['appstore_id']}`" if app["appstore_id"] else None,
    ]
    lines = _frontmatter(["review-insight", "competitor"]) + [
        f"# {app['name']} — review insights",
        "",
        f"- **Sources:** {', '.join(x for x in sources if x)}",
        f"- **Reviews:** {totals['reviews']:,} ({_day(totals['first_review'])} → {_day(totals['last_review'])}), "
        f"{totals['analysed']:,} analysed",
        f"- **Average rating:** {totals['avg_rating']:.2f} ★"
        if totals["avg_rating"] is not None
        else "- **Average rating:** -",
        f"- **Themes updated:** {_day(s['themes_updated_at'])}",
        "",
        "## Sentiment",
        "",
        "| Sentiment | Reviews | Share |",
        "| --- | ---: | ---: |",
        *[
            f"| {k} | {sent[k]:,} | {_pct(sent[k], analysed)} |"
            for k in ("positive", "neutral", "negative")
        ],
    ]
    if s["monthly"]:
        lines += [
            "",
            "## By month",
            "",
            "| Month | Reviews | Avg ★ | Positive | Neutral | Negative |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for m in s["monthly"]:
            avg = f"{m['avg_rating']:.2f}" if m["avg_rating"] is not None else "-"
            shares = " | ".join(
                _pct(m[k], m["analysed"]) for k in ("positive", "neutral", "negative")
            )
            lines.append(f"| {m['month']} | {m['reviews']} | {avg} | {shares} |")
    for key in TYPES:
        themes, generic = s["themes"][key], s["generic"][key]
        lines += ["", f"## {TITLES[key]}", ""]
        if not themes:
            lines.append("_None._" if analysed else "_Not analysed yet._")
        else:
            lines += [
                "| # | Theme | Reviews | Share | Example phrases |",
                "| ---: | --- | ---: | ---: | --- |",
            ]
            for i, t in enumerate(themes[:TOP], 1):
                desc = f" — {_cell(t['description'])}" if t["description"] else ""
                ex = "; ".join(_cell(p) for p in t["example_phrases"])
                lines.append(
                    f"| {i} | **{_cell(t['label'])}**{desc} | {t['review_count']} | "
                    f"{_pct(t['review_count'], analysed)} | {ex} |"
                )
            if len(themes) > TOP:
                lines.append(f"\n_{len(themes) - TOP} smaller themes not shown._")
        if generic:
            lines.append(f"\n_Not ranked: {generic} reviews with only generic remarks._")
    slug = re.sub(r"[^a-z0-9]+", "-", app["name"].lower()).strip("-") or f"app-{app_id}"
    return "\n".join(lines) + "\n", f"review-insight-{slug}-{date.today():%Y-%m-%d}.md"


def compare_report() -> tuple[str, str]:
    lines = _frontmatter(["review-insight", "competitor", "comparison"]) + [
        "# Competitor comparison — review insights",
        "",
        "Share = reviews mentioning the topic ÷ that app's analysed reviews.",
    ]
    for key in TYPES:
        m = build_matrix(key)
        lines += ["", f"## {TITLES[key]}", ""]
        if m["stale"]:
            lines.append(
                f"> [!warning] {m['unmatched_themes']} theme(s) changed since this comparison "
                "was built — refresh it in ReviewInsight.\n"
            )
        if not m["groups"]:
            lines.append("_No comparison yet._")
            continue
        apps = m["apps"]
        shared = [g for g in m["groups"] if g["apps_count"] >= 2]
        if key == "pain" and shared:
            lines += [
                "**Opportunities for PopNickel** — pain points shared by two or more competitors:",
                "",
            ]
            lines += [
                f"- **{_cell(g['label'])}** ({g['apps_count']} apps) — {_cell(g['description'] or '')}"
                for g in shared
            ]
            lines.append("")
        lines += [
            "| Topic | " + " | ".join(_cell(a["name"]) for a in apps) + " |",
            "| --- |" + " ---: |" * len(apps),
        ]
        for g in m["groups"][: TOP * 2]:
            cells = []
            for a in apps:
                c = g["cells"].get(str(a["id"]))
                cells.append(f"{_share(c['share'])} ({c['review_count']})" if c else "")
            mark = " ⚑" if g["apps_count"] >= 2 else ""
            lines.append(f"| **{_cell(g['label'])}**{mark} | " + " | ".join(cells) + " |")
        if len(m["groups"]) > TOP * 2:
            lines.append(f"\n_{len(m['groups']) - TOP * 2} smaller topics not shown._")
        lines.append("\n⚑ = mentioned for two or more apps.")
    return "\n".join(lines) + "\n", f"review-insight-comparison-{date.today():%Y-%m-%d}.md"


@router.get("/markdown")
def export_markdown(app_id: int | None = None) -> Response:
    """With `app_id`: one app's report. Without: the cross-app comparison.

    Returns the Markdown file itself (not the JSON envelope); errors still use the envelope.
    """
    text, filename = app_report(app_id) if app_id is not None else compare_report()
    return Response(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
