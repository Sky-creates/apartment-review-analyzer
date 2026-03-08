"""Rich terminal rendering for analysis results."""

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import AnalysisResult, Review, Theme

console = Console()

SENTIMENT_COLORS = {
    "positive": "green",
    "negative": "red",
    "mixed": "yellow",
    "neutral": "blue",
}

SENTIMENT_LABELS = {
    "positive": "POSITIVE",
    "negative": "NEGATIVE",
    "mixed": "MIXED",
    "neutral": "NEUTRAL",
}

BAR_FULL = "█"
BAR_EMPTY = "░"
BAR_WIDTH = 20


def _bar(value: int, max_value: int, width: int = BAR_WIDTH) -> str:
    if max_value == 0:
        return BAR_EMPTY * width
    filled = round((value / max_value) * width)
    return BAR_FULL * filled + BAR_EMPTY * (width - filled)


def _keyword_bar(positive: int, negative: int, max_total: int = 30, width: int = 24) -> str:
    total = positive + negative
    if max_total == 0 or total == 0:
        return BAR_EMPTY * width
    filled = round((total / max_total) * width)
    return BAR_FULL * filled + BAR_EMPTY * (width - filled)


def render_header(result: AnalysisResult) -> None:
    info = result.place_info
    rating_str = f"★ {info.rating}" if info.rating else "No rating"
    review_str = f"{result.total_reviews:,} reviews" if result.total_reviews else "reviews"
    subtitle = f"[dim]{info.address or 'Address unknown'}[/dim]  ·  [yellow]{rating_str}[/yellow]  ·  {review_str}"
    panel = Panel(
        subtitle,
        title=f"[bold cyan]{info.title}[/bold cyan]",
        box=box.ROUNDED,
        border_style="cyan",
    )
    console.print(panel)
    console.print()


def render_fetch_summary(result: AnalysisResult) -> None:
    mgmt_pct = int(result.management_response_rate * 100)
    console.print(
        f"[dim]Fetched[/dim] [bold]{result.fetched_reviews:,}[/bold] [dim]of[/dim] "
        f"[bold]{result.total_reviews:,}[/bold] [dim]reviews[/dim]  ·  "
        f"[dim]Management replies to[/dim] [bold]{mgmt_pct}%[/bold] [dim]of reviews[/dim]"
    )
    console.print()


def render_rating_distribution(result: AnalysisResult) -> None:
    dist = result.rating_distribution
    total = dist.total()
    mapping = [(5, dist.five), (4, dist.four), (3, dist.three), (2, dist.two), (1, dist.one)]
    max_count = max(c for _, c in mapping) if total > 0 else 1

    console.rule("[bold]Rating Distribution[/bold]")
    for stars, count in mapping:
        pct = int((count / total) * 100) if total > 0 else 0
        bar = _bar(count, max_count)
        console.print(
            f"  [yellow]{stars} ★[/yellow]  [green]{bar}[/green]  "
            f"[bold]{count:>4}[/bold]  [dim]({pct:>2}%)[/dim]"
        )
    console.print()


def render_api_topics(result: AnalysisResult) -> None:
    if not result.api_topics:
        return
    console.rule("[bold]Top Topics (Google-extracted)[/bold]")
    sorted_topics = sorted(result.api_topics, key=lambda t: -t.mentions)[:8]
    max_mentions = sorted_topics[0].mentions if sorted_topics else 1
    for t in sorted_topics:
        bar = _bar(t.mentions, max_mentions, width=12)
        console.print(f"  [cyan]{t.keyword:<20}[/cyan] [bold]{t.mentions:>4}[/bold]  [blue]{bar}[/blue]")
    console.print()


def _render_theme_panel(theme: Theme) -> Panel:
    sentiment_color = SENTIMENT_COLORS.get(theme.sentiment, "white")
    sentiment_label = SENTIMENT_LABELS.get(theme.sentiment, theme.sentiment.upper())

    lines = Text()

    # Summary
    lines.append(f"{theme.summary}\n\n", style="italic")

    # Keyword breakdown
    if theme.keywords:
        lines.append("Keyword Breakdown:\n", style="bold underline")
        max_total = max(k.positive_mentions + k.negative_mentions for k in theme.keywords) if theme.keywords else 1
        for kw in theme.keywords[:6]:
            total = kw.positive_mentions + kw.negative_mentions
            bar = _keyword_bar(kw.positive_mentions, kw.negative_mentions, max_total)
            kw_line = (
                f"  {kw.keyword:<22} {bar}  "
                f"{kw.negative_mentions} bad  ·  {kw.positive_mentions} good\n"
            )
            lines.append(kw_line)
        lines.append("\n")

    # Quotes
    for q in theme.quotes[:2]:
        lines.append(f'  "{q}"\n', style="dim italic")

    title = (
        f"[bold]{theme.name}[/bold]  "
        f"[{sentiment_color}][{sentiment_label}][/{sentiment_color}]  "
        f"[dim]~{theme.mentions} mentions[/dim]"
    )
    return Panel(lines, title=title, box=box.ROUNDED, border_style=sentiment_color)


def render_themes(result: AnalysisResult) -> None:
    if not result.themes:
        return
    console.rule("[bold]AI Theme Analysis[/bold]")
    console.print()
    for theme in result.themes:
        console.print(_render_theme_panel(theme))
        console.print()


def render_overall(result: AnalysisResult) -> None:
    console.rule("[bold]Overall[/bold]")
    if result.overall_pros:
        pros_str = "  ·  ".join(result.overall_pros)
        console.print(f"  [green]Pros:[/green]  {pros_str}")
    if result.overall_cons:
        cons_str = "  ·  ".join(result.overall_cons)
        console.print(f"  [red]Cons:[/red]  {cons_str}")
    console.print()
    if result.verdict:
        console.print(f"  [italic]{result.verdict}[/italic]")
    console.print()


def _review_snippet(review: Review, max_len: int = 80) -> str:
    text = review.snippet
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text


def render_recent_reviews(result: AnalysisResult) -> None:
    console.rule("[bold]Recent Reviews[/bold]")
    console.print()

    # Build two tables side by side
    pos_table = Table(
        title="[green]Recent Positives[/green]",
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
        width=50,
    )
    pos_table.add_column("stars", style="yellow", no_wrap=True)
    pos_table.add_column("text", overflow="fold")

    for r in result.recent_positives:
        rating = int(r.rating)
        stars = "★" * rating + "☆" * (5 - rating)
        pos_table.add_row(stars, _review_snippet(r))

    neg_table = Table(
        title="[red]Recent Concerns[/red]",
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
        width=50,
    )
    neg_table.add_column("stars", style="red", no_wrap=True)
    neg_table.add_column("text", overflow="fold")

    for r in result.recent_negatives:
        rating = int(r.rating)
        stars = "★" * rating + "☆" * (5 - rating)
        neg_table.add_row(stars, _review_snippet(r))

    console.print(Columns([pos_table, neg_table]))
    console.print()


def render_full(result: AnalysisResult) -> None:
    """Render the complete analysis to the terminal."""
    render_header(result)
    render_fetch_summary(result)
    render_rating_distribution(result)
    render_api_topics(result)
    render_themes(result)
    render_overall(result)
    render_recent_reviews(result)
