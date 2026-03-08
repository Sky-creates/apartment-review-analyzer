"""OpenRouter / Gemini 2.5 Flash integration for review analysis."""

import hashlib
import json
import re
from typing import List

from openai import OpenAI

from .cache import Cache
from .models import Review, Topic

SEG_BATCH_SIZE = 300  # reviews per batch for segmentation

DEFAULT_MODEL = "google/gemini-2.5-flash"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = """You are a real estate research assistant specializing in apartment reviews.
Your job is to analyze tenant reviews and extract structured insights to help prospective renters make informed decisions.

Be accurate, nuanced, and evidence-based. Count keyword mentions carefully across all reviews.
Quote directly from the reviews when providing examples. Do not fabricate quotes or statistics."""

BATCH_SIZE = 300  # reviews per batch for large sets


def _build_user_prompt(
    reviews: List[Review],
    api_topics: List[Topic],
    place_name: str,
) -> str:
    """Build the analysis prompt for a set of reviews."""
    n = len(reviews)
    topic_str = ", ".join(
        f"{t.keyword} ({t.mentions})" for t in sorted(api_topics, key=lambda x: -x.mentions)
    ) if api_topics else "not available"

    review_lines = []
    for r in reviews:
        stars = r.rating
        text = r.snippet.replace("\n", " ").strip()
        review_lines.append(f"[{stars}★] {text}")
    reviews_text = "\n".join(review_lines)

    return f"""Analyze the following {n} reviews for apartment "{place_name}".

Reviews (format: [RATING★] review text):
{reviews_text}

Google Maps has identified these top topics: {topic_str}

Your task has TWO parts:

PART 1 — For each topic/category identified above, extract specific keywords or phrases
that reviewers mention, and count how many times each keyword appears in a positive
vs. negative context across ALL {n} reviews.

PART 2 — Provide an overall summary.

Return ONLY valid JSON in this exact schema:
{{
  "themes": [
    {{
      "name": "Noise",
      "sentiment": "positive|negative|mixed|neutral",
      "summary": "1-2 sentence summary of this theme",
      "mentions": 71,
      "keywords": [
        {{
          "keyword": "thin walls",
          "positive_mentions": 2,
          "negative_mentions": 23,
          "example_quotes": ["You can hear everything through the walls"]
        }}
      ],
      "pros": ["Some units are quiet"],
      "cons": ["Paper thin walls", "Street noise"],
      "quotes": ["exact quote 1", "exact quote 2"]
    }}
  ],
  "overall_pros": ["Great location", "Modern amenities"],
  "overall_cons": ["Noise issues", "Maintenance delays"],
  "verdict": "2-3 sentence overall verdict paragraph"
}}

Use the Google topic list as your category guide. Identify 3-6 keywords per theme.
Sort themes by total mentions descending. Sort keywords within each theme by
(positive_mentions + negative_mentions) descending."""


def _build_synthesis_prompt(
    batch_results: List[dict],
    place_name: str,
) -> str:
    """Build a prompt to synthesize multiple batch analysis results."""
    batches_text = json.dumps(batch_results, indent=2)
    return f"""You analyzed {len(batch_results)} batches of reviews for apartment "{place_name}".
Here are the JSON outputs from each batch analysis:

{batches_text}

Synthesize these into a single unified analysis. Merge themes with the same name by:
- Summing up keyword positive_mentions and negative_mentions
- Combining and deduplicating pros, cons, and quotes
- Updating summaries to reflect the combined picture
- Recalculating overall sentiment based on combined data

Return ONLY valid JSON in the same schema as the input batches."""


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from LLM response:\n{text[:500]}")


def _call_llm(
    client: OpenAI,
    model: str,
    system: str,
    user: str,
) -> dict:
    """Make a single LLM call and return parsed JSON."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content or ""
    return _extract_json(content)


def analyze_reviews(
    reviews: List[Review],
    api_topics: List[Topic],
    place_name: str,
    openrouter_key: str,
    cache: Cache,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Send all review texts + ratings to Gemini 2.5 Flash via OpenRouter.
    Returns parsed JSON matching the LLMOutput schema.

    Uses batching for >500 reviews (batches of 300 + synthesis call).
    Cache key: sha256 of (place_name + all review snippets concatenated).
    """
    # Build cache key
    review_content = "".join(f"{r.rating}:{r.snippet}" for r in reviews)
    cache_key_raw = f"llm:{model}:{place_name}:{review_content}"
    cache_key = hashlib.sha256(cache_key_raw.encode()).hexdigest()

    cached = cache.get(f"llm_result:{cache_key}")
    if cached is not None:
        return cached

    client = OpenAI(
        api_key=openrouter_key,
        base_url=OPENROUTER_BASE_URL,
    )

    if len(reviews) <= 500:
        # Single call
        prompt = _build_user_prompt(reviews, api_topics, place_name)
        result = _call_llm(client, model, SYSTEM_PROMPT, prompt)
    else:
        # Batch mode: analyze in chunks of BATCH_SIZE, then synthesize
        batch_results = []
        for i in range(0, len(reviews), BATCH_SIZE):
            batch = reviews[i : i + BATCH_SIZE]
            prompt = _build_user_prompt(batch, api_topics, place_name)
            batch_result = _call_llm(client, model, SYSTEM_PROMPT, prompt)
            batch_results.append(batch_result)

        # Synthesize batch results
        synthesis_prompt = _build_synthesis_prompt(batch_results, place_name)
        result = _call_llm(client, model, SYSTEM_PROMPT, synthesis_prompt)

    cache.set(f"llm_result:{cache_key}", result)
    return result


def _build_segment_prompt(reviews: List[Review], place_name: str, index_offset: int = 0) -> str:
    """Build the segmentation prompt for a set of reviews."""
    n = len(reviews)
    review_lines = []
    for i, r in enumerate(reviews):
        text = r.snippet.replace("\n", " ").strip()
        review_lines.append(f"[{index_offset + i}] [{r.rating}★] {text}")
    reviews_text = "\n".join(review_lines)

    return f"""You are analyzing {n} reviews for apartment "{place_name}".

For each review below, split it into meaningful segments (one topic per sentence or short phrase).
For each segment, assign:
- keyword: 1-3 word topic label. NORMALIZE: use the same label for the same concept
  (e.g. always "maintenance team", never sometimes "maintenance" and sometimes "repair staff")
- sentiment: "positive" or "negative" (skip neutral/factual segments)

Reviews (format: [INDEX] [RATING★] text):
{reviews_text}

Return ONLY valid JSON:
{{
  "segments": [
    {{"review_index": 0, "keyword": "gym", "sentiment": "positive", "text": "Great gym"}},
    {{"review_index": 0, "keyword": "noise", "sentiment": "negative", "text": "walls are thin"}},
    {{"review_index": 1, "keyword": "management", "sentiment": "negative", "text": "Management never responds"}}
  ]
}}

Rules:
- Normalize keywords strictly: pick one canonical label per concept across ALL reviews
- Skip segments that are purely neutral/factual (no clear positive or negative valence)
- Each segment text should be a direct quote or close paraphrase from the review
- Aim for 2-5 segments per review"""


def segment_reviews(
    reviews: List[Review],
    place_name: str,
    openrouter_key: str,
    cache: Cache,
    model: str = DEFAULT_MODEL,
) -> list[dict]:
    """
    Split reviews into keyword-tagged segments via a separate LLM call.
    Returns a flat list of segment dicts: {review_index, keyword, sentiment, text}.

    Cache key: sha256("seg:" + model + ":" + place_name + all_snippets_concat).
    Uses batching for >500 reviews (batches of SEG_BATCH_SIZE, then flatten).
    """
    review_content = "".join(f"{r.rating}:{r.snippet}" for r in reviews)
    cache_key_raw = f"seg:{model}:{place_name}:{review_content}"
    cache_key = hashlib.sha256(cache_key_raw.encode()).hexdigest()

    cached = cache.get(f"seg_result:{cache_key}")
    if cached is not None:
        return cached

    client = OpenAI(
        api_key=openrouter_key,
        base_url=OPENROUTER_BASE_URL,
    )

    seg_system = "You are a review segmentation assistant. Return only valid JSON."

    if len(reviews) <= 500:
        prompt = _build_segment_prompt(reviews, place_name)
        raw = _call_llm(client, model, seg_system, prompt)
        all_segments = raw.get("segments", [])
    else:
        all_segments = []
        for i in range(0, len(reviews), SEG_BATCH_SIZE):
            batch = reviews[i : i + SEG_BATCH_SIZE]
            prompt = _build_segment_prompt(batch, place_name, index_offset=i)
            raw = _call_llm(client, model, seg_system, prompt)
            all_segments.extend(raw.get("segments", []))

    cache.set(f"seg_result:{cache_key}", all_segments)
    return all_segments
