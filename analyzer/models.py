"""Data models for the apartment review analyzer."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlaceResult:
    """A search result from Google Maps search."""
    title: str
    data_id: str
    rating: Optional[float]
    review_count: Optional[int]
    address: Optional[str]


@dataclass
class PlaceInfo:
    """Metadata from the reviews response."""
    title: str
    data_id: str
    rating: Optional[float]
    review_count: Optional[int]
    address: Optional[str]
    phone: Optional[str] = None
    website: Optional[str] = None


@dataclass
class Review:
    """A single user review."""
    author: str
    rating: int
    snippet: str
    iso_date: Optional[str] = None
    response: Optional[str] = None  # management response text


@dataclass
class Topic:
    """A Google Maps extracted keyword/topic."""
    keyword: str
    mentions: int
    topic_id: Optional[str] = None


@dataclass
class KeywordStat:
    """Stat for a specific keyword within a theme."""
    keyword: str
    positive_mentions: int
    negative_mentions: int
    example_quotes: list[str] = field(default_factory=list)


@dataclass
class Theme:
    """An LLM-identified theme from the reviews."""
    name: str
    sentiment: str  # "positive" | "negative" | "mixed" | "neutral"
    summary: str
    mentions: int
    keywords: list[KeywordStat] = field(default_factory=list)
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    quotes: list[str] = field(default_factory=list)


@dataclass
class RatingDistribution:
    """Distribution of star ratings."""
    five: int = 0
    four: int = 0
    three: int = 0
    two: int = 0
    one: int = 0

    def total(self) -> int:
        return self.five + self.four + self.three + self.two + self.one

    def as_dict(self) -> dict:
        return {5: self.five, 4: self.four, 3: self.three, 2: self.two, 1: self.one}


@dataclass
class Segment:
    """A sentence/phrase extracted from a review, tagged with keyword and sentiment."""
    text: str
    keyword: str
    sentiment: str      # "positive" | "negative"
    review_rating: int
    author: str


@dataclass
class KeywordGroup:
    """All segments for a single keyword, split by sentiment."""
    keyword: str
    positive_segments: list[Segment]
    negative_segments: list[Segment]

    @property
    def total(self) -> int:
        return len(self.positive_segments) + len(self.negative_segments)


@dataclass
class AnalysisResult:
    """Full assembled analysis output."""
    place_info: PlaceInfo
    total_reviews: int
    fetched_reviews: int
    rating_distribution: RatingDistribution
    api_topics: list[Topic]
    themes: list[Theme]
    overall_pros: list[str]
    overall_cons: list[str]
    verdict: str
    management_response_rate: float
    recent_positives: list[Review]
    recent_negatives: list[Review]
    keyword_groups: list[KeywordGroup] = field(default_factory=list)
