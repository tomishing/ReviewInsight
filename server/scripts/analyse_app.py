"""Phase 1 MVP: fetch Google Play reviews -> extract -> cluster -> Markdown report.

Usage:
    python scripts/analyse_app.py com.monarchmoney.mobile [--count 200] > report.md

Progress goes to stderr; the Markdown report goes to stdout.
"""

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

import anthropic  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from google_play_scraper import app as play_app  # noqa: E402

from app.analysis.cluster import Theme, cluster_all  # noqa: E402
from app.analysis.extract import (  # noqa: E402
    ReviewExtraction,
    ReviewInput,
    Usage,
    extract_reviews,
)
from app.fetchers.play import FetchedReview, fetch_play_reviews  # noqa: E402

load_dotenv(SERVER_DIR.parent / ".env")
load_dotenv(SERVER_DIR / ".env")

DEFAULT_MODEL = "claude-haiku-4-5"
SECTIONS = [("pain", "Pain points"), ("positive", "Positive points"), ("request", "Feature requests")]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def render_report(
    app_name: str,
    play_id: str,
    reviews: list[FetchedReview],
    extractions: list[ReviewExtraction],
    themes: dict[str, list[Theme]],
    usage: Usage,
    model: str,
    top: int,
) -> str:
    by_id = {r.store_review_id: r for r in reviews}
    analysed = [e for e in extractions if e.review_id in by_id]
    n = len(analysed)
    sentiments = Counter(e.sentiment for e in analysed)
    ratings = [r.rating for r in reviews if r.rating]
    dates = [r.review_date for r in reviews if r.review_date]

    lines = [
        f"# {app_name} — review insights",
        "",
        f"- **Source:** Google Play `{play_id}` ({reviews[0].country if reviews else '-'})",
        f"- **Reviews analysed:** {n} of {len(reviews)} fetched",
    ]
    if dates:
        lines.append(f"- **Date range:** {min(dates):%Y-%m-%d} → {max(dates):%Y-%m-%d}")
    if ratings:
        lines.append(f"- **Average rating:** {sum(ratings) / len(ratings):.2f} ★")
    lines.append(f"- **Generated:** {date.today():%Y-%m-%d}")

    lines += ["", "## Sentiment", "", "| Sentiment | Reviews | Share |", "| --- | ---: | ---: |"]
    for s in ("positive", "neutral", "negative"):
        c = sentiments.get(s, 0)
        lines.append(f"| {s} | {c} | {c / n:.0%} |" if n else f"| {s} | 0 | - |")

    # Monthly trend
    monthly: dict[str, list[ReviewExtraction]] = defaultdict(list)
    for e in analysed:
        d = by_id[e.review_id].review_date
        if d:
            monthly[f"{d:%Y-%m}"].append(e)
    if monthly:
        lines += [
            "",
            "## Trend by month",
            "",
            "| Month | Reviews | Avg ★ | Positive | Neutral | Negative |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for m in sorted(monthly):
            es = monthly[m]
            rs = [by_id[e.review_id].rating for e in es if by_id[e.review_id].rating]
            c = Counter(e.sentiment for e in es)
            avg = f"{sum(rs) / len(rs):.2f}" if rs else "-"
            lines.append(
                f"| {m} | {len(es)} | {avg} | "
                + " | ".join(f"{c.get(s, 0) / len(es):.0%}" for s in ("positive", "neutral", "negative"))
                + " |"
            )

    for key, title in SECTIONS:
        lines += ["", f"## {title}", ""]
        ts = [t for t in themes.get(key, []) if not t.generic][:top]
        generic = sum(t.review_count for t in themes.get(key, []) if t.generic)
        if not ts:
            lines.append("_None found._")
            continue
        lines += ["| # | Theme | Reviews | Share | Example phrases |", "| ---: | --- | ---: | ---: | --- |"]
        for i, t in enumerate(ts, 1):
            share = f"{t.review_count / n:.0%}" if n else "-"
            ex = "; ".join(t.example_phrases).replace("|", "/")
            lines.append(f"| {i} | **{t.label}** — {t.description} | {t.review_count} | {share} | {ex} |")
        if generic:
            lines += ["", f"_Not ranked: {generic} reviews with generic remarks (e.g. \"great app\")._"]

    lines += [
        "",
        "---",
        f"_Model: `{model}` · tokens in/out: {usage.input_tokens:,} / {usage.output_tokens:,}_",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Analyse Google Play reviews of one app.")
    p.add_argument("play_id", help="Google Play package id, e.g. com.monarchmoney.mobile")
    p.add_argument("--count", type=int, default=200, help="number of newest reviews (default 200)")
    p.add_argument("--lang", default=os.getenv("DEFAULT_LANG", "en"))
    p.add_argument("--country", default=os.getenv("DEFAULT_COUNTRY", "ca"))
    p.add_argument("--model", default=os.getenv("EXTRACT_MODEL", DEFAULT_MODEL), help="extraction model")
    p.add_argument("--cluster-model", default=os.getenv("CLUSTER_MODEL"), help="defaults to --model")
    p.add_argument("--top", type=int, default=10, help="themes per section (default 10)")
    p.add_argument("-o", "--output", type=Path, help="write report to file instead of stdout")
    args = p.parse_args()
    cluster_model = args.cluster_model or args.model

    try:
        app_name = play_app(args.play_id, lang=args.lang, country=args.country)["title"]
    except Exception as e:  # noqa: BLE001 — name lookup is optional
        log(f"! could not fetch app details ({e}); using package id as name")
        app_name = args.play_id

    log(f"Fetching up to {args.count} reviews for {app_name} ({args.play_id})...")
    reviews = fetch_play_reviews(args.play_id, args.count, args.lang, args.country)
    log(f"  fetched {len(reviews)} reviews")
    if not reviews:
        log("No reviews found.")
        return 1

    client = anthropic.Anthropic()
    usage = Usage()
    inputs = [
        ReviewInput(review_id=r.store_review_id, rating=r.rating, title=r.title, body=r.body)
        for r in reviews
    ]
    log(f"Extracting with {args.model}...")
    extractions = extract_reviews(
        client, args.model, app_name, inputs, usage,
        on_progress=lambda done, total: log(f"  {done}/{total}"),
    )
    log(f"Clustering with {cluster_model}...")
    themes = cluster_all(client, cluster_model, extractions, usage)
    log(f"Done. Tokens in/out: {usage.input_tokens:,} / {usage.output_tokens:,}")

    report = render_report(
        app_name, args.play_id, reviews, extractions, themes, usage, args.model, args.top
    )
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        log(f"Report written to {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
