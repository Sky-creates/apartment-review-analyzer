"""Orchestrates the full analysis pipeline."""

from typing import List, Tuple

from . import llm as llm_module
from .cache import Cache
from .models import (
    AnalysisResult,
    KeywordGroup,
    KeywordStat,
    PlaceInfo,
    RatingDistribution,
    Review,
    Segment,
    Theme,
    Topic,
)


def compute_rating_distribution(reviews: List[Review]) -> RatingDistribution:
    dist = RatingDistribution()
    for r in reviews:
        if r.rating == 5:
            dist.five += 1
        elif r.rating == 4:
            dist.four += 1
        elif r.rating == 3:
            dist.three += 1
        elif r.rating == 2:
            dist.two += 1
        elif r.rating == 1:
            dist.one += 1
    return dist


def compute_management_response_rate(reviews: List[Review]) -> float:
    if not reviews:
        return 0.0
    responded = sum(1 for r in reviews if r.response)
    return responded / len(reviews)


def select_representative_reviews(
    reviews: List[Review],
    n: int = 3,
) -> Tuple[List[Review], List[Review]]:
    """Select top positive and top negative reviews by recency."""
    # Sort: positives = rating >= 4, negatives = rating <= 2, ordered by recency (keep original order = newest first)
    positives = [r for r in reviews if r.rating >= 4][:n]
    negatives = [r for r in reviews if r.rating <= 2][:n]
    return positives, negatives


def group_segments_by_keyword(
    raw_segments: list[dict],
    reviews: List[Review],
) -> list[KeywordGroup]:
    """
    Aggregate raw segment dicts (from LLM) into KeywordGroup objects.

    Steps:
    1. Build Segment objects, looking up author/rating from reviews by review_index.
    2. Group by keyword (case-insensitive, normalized to lowercase).
    3. Filter: drop keywords with total < 2 (noise).
    4. Sort: by negative_count desc, then total desc.
    """
    groups: dict[str, KeywordGroup] = {}

    for seg in raw_segments:
        idx = seg.get("review_index")
        keyword = seg.get("keyword", "").strip().lower()
        sentiment = seg.get("sentiment", "").lower()
        text = seg.get("text", "").strip()

        if not keyword or sentiment not in ("positive", "negative") or not text:
            continue

        if idx is None or idx < 0 or idx >= len(reviews):
            continue

        review = reviews[idx]
        segment = Segment(
            text=text,
            keyword=keyword,
            sentiment=sentiment,
            review_rating=review.rating,
            author=review.author,
        )

        if keyword not in groups:
            groups[keyword] = KeywordGroup(
                keyword=keyword,
                positive_segments=[],
                negative_segments=[],
            )

        if sentiment == "positive":
            groups[keyword].positive_segments.append(segment)
        else:
            groups[keyword].negative_segments.append(segment)

    # Keep any keyword with ≥1 negative segment (always worth surfacing),
    # or ≥2 total segments (suppresses one-off positive noise).
    filtered = [
        g for g in groups.values()
        if len(g.negative_segments) >= 1 or g.total >= 2
    ]

    # Sort: negative count desc, then total desc
    filtered.sort(key=lambda g: (-len(g.negative_segments), -g.total))

    return filtered


def _parse_keyword_stat(kw_data: dict) -> KeywordStat:
    return KeywordStat(
        keyword=kw_data.get("keyword", ""),
        positive_mentions=int(kw_data.get("positive_mentions", 0)),
        negative_mentions=int(kw_data.get("negative_mentions", 0)),
        example_quotes=kw_data.get("example_quotes", []),
    )


def _parse_theme(theme_data: dict) -> Theme:
    keywords = [_parse_keyword_stat(kw) for kw in theme_data.get("keywords", [])]
    return Theme(
        name=theme_data.get("name", ""),
        sentiment=theme_data.get("sentiment", "neutral"),
        summary=theme_data.get("summary", ""),
        mentions=int(theme_data.get("mentions", 0)),
        keywords=keywords,
        pros=theme_data.get("pros", []),
        cons=theme_data.get("cons", []),
        quotes=theme_data.get("quotes", []),
    )


def analyze(
    reviews: List[Review],
    api_topics: List[Topic],
    place_info: PlaceInfo,
    openrouter_key: str,
    cache: Cache,
    model: str = llm_module.DEFAULT_MODEL,
) -> AnalysisResult:
    """
    Orchestrate the full analysis pipeline:
    1. Compute rating distribution
    2. Compute management response rate
    3. Select representative reviews
    4. Call LLM for thematic analysis
    5. Parse LLM output into dataclasses
    6. Assemble and return AnalysisResult
    """
    rating_dist = compute_rating_distribution(reviews)
    mgmt_response_rate = compute_management_response_rate(reviews)
    recent_positives, recent_negatives = select_representative_reviews(reviews)

    # LLM analysis
    raw = llm_module.analyze_reviews(
        reviews=reviews,
        api_topics=api_topics,
        place_name=place_info.title,
        openrouter_key=openrouter_key,
        cache=cache,
        model=model,
    )

    # Parse themes
    themes = [_parse_theme(t) for t in raw.get("themes", [])]
    # Sort by mentions descending (LLM should already do this, but enforce it)
    themes.sort(key=lambda t: -t.mentions)

    overall_pros = raw.get("overall_pros", [])
    overall_cons = raw.get("overall_cons", [])
    verdict = raw.get("verdict", "")

    # Keyword segmentation (separate LLM call, independently cached)
    raw_segments = llm_module.segment_reviews(
        reviews=reviews,
        place_name=place_info.title,
        openrouter_key=openrouter_key,
        cache=cache,
        model=model,
    )
    keyword_groups = group_segments_by_keyword(raw_segments, reviews)

    total_reviews = place_info.review_count or len(reviews)

    return AnalysisResult(
        place_info=place_info,
        total_reviews=total_reviews,
        fetched_reviews=len(reviews),
        rating_distribution=rating_dist,
        api_topics=api_topics,
        themes=themes,
        overall_pros=overall_pros,
        overall_cons=overall_cons,
        verdict=verdict,
        management_response_rate=mgmt_response_rate,
        recent_positives=recent_positives,
        recent_negatives=recent_negatives,
        keyword_groups=keyword_groups,
    )
