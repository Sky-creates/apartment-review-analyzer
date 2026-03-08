"""SerpAPI integration for fetching apartment search results and reviews."""

import time
from typing import List, Optional, Tuple

from serpapi import GoogleSearch

from .cache import Cache
from .models import PlaceInfo, PlaceResult, Review, Topic


def search_apartments(
    query: str,
    api_key: str,
    cache: Cache,
    top_n: int = 5,
) -> List[PlaceResult]:
    """Search for apartments by name via Google Maps. Returns top N results."""
    cache_key = f"search:{query}:top_n:{top_n}"
    cached = cache.get(cache_key)
    if cached is not None:
        return [PlaceResult(**item) for item in cached]

    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "api_key": api_key,
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    places = []

    # Exact-address queries return a single `place_results` dict instead of a list
    if "place_results" in results:
        r = results["place_results"]
        places.append(
            PlaceResult(
                title=r.get("title", ""),
                data_id=r.get("data_id", ""),
                rating=r.get("rating"),
                review_count=r.get("reviews"),
                address=r.get("address"),
            )
        )
    else:
        for r in results.get("local_results", [])[:top_n]:
            places.append(
                PlaceResult(
                    title=r.get("title", ""),
                    data_id=r.get("data_id", ""),
                    rating=r.get("rating"),
                    review_count=r.get("reviews"),
                    address=r.get("address"),
                )
            )

    if places:
        cache.set(cache_key, [vars(p) for p in places])
    return places


def fetch_all_reviews(
    data_id: str,
    api_key: str,
    cache: Cache,
    limit: int = 200,
) -> Tuple[PlaceInfo, List[Review], List[Topic]]:
    """
    Fetch all available reviews for a place via pagination.

    Args:
        data_id: Google Maps data_id for the place.
        api_key: SerpAPI key.
        cache: Cache instance.
        limit: Max reviews to fetch. 0 means fetch all.

    Returns:
        (PlaceInfo, list of Reviews, list of Topics)
    """
    cache_key = f"reviews:{data_id}:limit:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        place_info = PlaceInfo(**cached["place_info"])
        reviews = [Review(**{**r, "rating": int(r["rating"])}) for r in cached["reviews"]]
        topics = [Topic(**t) for t in cached["topics"]]
        return place_info, reviews, topics

    all_reviews: List[Review] = []
    all_topics: List[Topic] = []
    place_info: Optional[PlaceInfo] = None
    next_page_token: Optional[str] = None

    while True:
        params = {
            "engine": "google_maps_reviews",
            "data_id": data_id,
            "api_key": api_key,
            "sort_by": "newestFirst",
            "hl": "en",
        }
        if next_page_token:
            params["next_page_token"] = next_page_token

        # Retry once on 429
        for attempt in range(2):
            try:
                search = GoogleSearch(params)
                result = search.get_dict()
                break
            except Exception as e:
                if attempt == 0 and "429" in str(e):
                    time.sleep(2)
                    continue
                raise

        # Extract place info from first page
        if place_info is None:
            place_data = result.get("place_info", {})
            addr = place_data.get("address") or result.get("search_metadata", {}).get("query", "")
            # Try to get review count from place_info or from overall rating
            review_count = place_data.get("reviews") or place_data.get("total_reviews")
            place_info = PlaceInfo(
                title=place_data.get("title", ""),
                data_id=data_id,
                rating=place_data.get("rating"),
                review_count=review_count,
                address=addr,
                phone=place_data.get("phone"),
                website=place_data.get("website"),
            )

            # Extract topics from first page
            for t in result.get("topics", []):
                all_topics.append(
                    Topic(
                        keyword=t.get("keyword", t.get("topic", "")),
                        mentions=t.get("reviews", t.get("mentions", 0)),
                        topic_id=t.get("topic_id"),
                    )
                )

        # Extract reviews from this page
        for r in result.get("reviews", []):
            snippet = r.get("snippet", "") or r.get("text", "") or ""
            if not snippet:
                continue
            mgmt_response = None
            if r.get("response"):
                mgmt_response = r["response"].get("snippet", r["response"].get("text", ""))

            all_reviews.append(
                Review(
                    author=r.get("user", {}).get("name", "Anonymous"),
                    rating=int(r.get("rating", 3)),
                    snippet=snippet,
                    iso_date=r.get("iso_date") or r.get("date"),
                    response=mgmt_response,
                )
            )

        # Check limit
        if limit > 0 and len(all_reviews) >= limit:
            all_reviews = all_reviews[:limit]
            break

        # Paginate
        next_page_token = result.get("serpapi_pagination", {}).get("next_page_token")
        if not next_page_token:
            break

        # Polite delay
        time.sleep(0.5)

    # Cache the result
    cache.set(
        cache_key,
        {
            "place_info": vars(place_info),
            "reviews": [vars(r) for r in all_reviews],
            "topics": [vars(t) for t in all_topics],
        },
    )

    return place_info, all_reviews, all_topics
