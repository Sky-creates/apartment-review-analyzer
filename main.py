"""CLI entry point for the Apartment Review Analyzer."""

import argparse
import os
import sys

from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.table import Table

from analyzer import analysis, api, display, report
from analyzer.cache import Cache
from analyzer.llm import DEFAULT_MODEL

load_dotenv()
console = Console()


def _select_place(places):
    """Print a numbered table of search results and prompt user to pick one."""
    table = Table(title="Search Results", box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Rating", style="yellow", width=7)
    table.add_column("Reviews", width=8)
    table.add_column("Address")

    for i, p in enumerate(places, 1):
        table.add_row(
            str(i),
            p.title,
            str(p.rating) if p.rating else "N/A",
            str(p.review_count) if p.review_count else "N/A",
            p.address or "N/A",
        )

    console.print(table)

    while True:
        try:
            choice = int(input(f"\nSelect apartment [1-{len(places)}]: ").strip())
            if 1 <= choice <= len(places):
                return places[choice - 1]
        except (ValueError, KeyboardInterrupt):
            pass
        console.print(f"[red]Please enter a number between 1 and {len(places)}.[/red]")


def main():
    parser = argparse.ArgumentParser(
        description="Apartment Review Analyzer — search, fetch reviews, and get AI analysis.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "Avalon Mission Bay San Francisco"
  python main.py "NEMA San Francisco" --limit 300 --save markdown
  python main.py "One Mission Bay" --no-cache --save json
  python main.py "Continuum Western Avenue, Boston, MA" --save pdf
        """,
    )
    parser.add_argument("query", help="Apartment name or search query")
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        metavar="N",
        help="Max reviews to fetch (0 = all, default: 200)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        metavar="MODEL_ID",
        help=f"OpenRouter model ID (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--save",
        nargs="+",
        choices=["markdown", "json", "pdf", "all"],
        metavar="FORMAT",
        help="Save report in one or more formats: markdown, json, pdf, all",
    )
    parser.add_argument(
        "--output-dir",
        default="./reports",
        metavar="DIR",
        help="Directory to save reports (default: ./reports)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache for fresh API and LLM calls",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        metavar="N",
        help="Number of search results to show (default: 5)",
    )

    args = parser.parse_args()

    # Load API keys
    serpapi_key = os.getenv("SERPAPI_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if not serpapi_key:
        console.print("[red]Error: SERPAPI_KEY not set. Add it to .env or set as environment variable.[/red]")
        sys.exit(1)
    if not openrouter_key:
        console.print("[red]Error: OPENROUTER_API_KEY not set. Add it to .env or set as environment variable.[/red]")
        sys.exit(1)

    cache = Cache(enabled=not args.no_cache)

    # Step 1: Search
    console.print(f"\n[bold]Searching for:[/bold] {args.query}\n")
    with console.status("[cyan]Searching Google Maps...[/cyan]"):
        places = api.search_apartments(
            query=args.query,
            api_key=serpapi_key,
            cache=cache,
            top_n=args.top_n,
        )

    if not places:
        console.print("[red]No results found. Try a different search query.[/red]")
        sys.exit(1)

    # Step 2: Select place
    if len(places) == 1:
        selected = places[0]
        console.print(f"[green]Found:[/green] {selected.title}")
    else:
        selected = _select_place(places)

    console.print(f"\n[bold cyan]Analyzing:[/bold cyan] {selected.title}")

    # Step 3: Fetch reviews
    limit = args.limit if args.limit > 0 else 0
    with console.status(f"[cyan]Fetching reviews (limit: {limit or 'all'})...[/cyan]"):
        place_info, reviews, topics = api.fetch_all_reviews(
            data_id=selected.data_id,
            api_key=serpapi_key,
            cache=cache,
            limit=limit,
        )

    # Use selected place title if place_info title is empty
    if not place_info.title:
        place_info.title = selected.title
    if not place_info.review_count and selected.review_count:
        place_info.review_count = selected.review_count
    if not place_info.rating and selected.rating:
        place_info.rating = selected.rating
    if not place_info.address and selected.address:
        place_info.address = selected.address

    console.print(f"[green]Fetched {len(reviews):,} reviews.[/green]")

    if not reviews:
        console.print("[yellow]No review text found. Cannot perform analysis.[/yellow]")
        sys.exit(1)

    # Step 4: LLM analysis
    with console.status(f"[cyan]Running AI analysis with {args.model}...[/cyan]"):
        result = analysis.analyze(
            reviews=reviews,
            api_topics=topics,
            place_info=place_info,
            openrouter_key=openrouter_key,
            cache=cache,
            model=args.model,
        )

    # Step 5: Display
    console.print()
    display.render_full(result)

    # Step 6: Save report
    _ALL_FORMATS = ["markdown", "json", "pdf"]
    formats = _ALL_FORMATS if args.save and "all" in args.save else (args.save or [])
    for fmt in formats:
        path = report.save_report(result, fmt=fmt, output_dir=args.output_dir)
        console.print(f"[green]Report saved to:[/green] {path}")


if __name__ == "__main__":
    main()
