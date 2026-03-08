"""Save analysis results to disk as markdown, JSON, or PDF."""

import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .models import AnalysisResult

_PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
    padding: 32px 48px;
}

h1 {
    font-size: 20pt;
    font-weight: 700;
    color: #111;
    margin-bottom: 4px;
}

.subtitle {
    font-size: 10pt;
    color: #555;
    margin-bottom: 20px;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 18px 0;
}

h2 {
    font-size: 13pt;
    font-weight: 600;
    color: #1a1a1a;
    margin-top: 24px;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 2px solid #e0e0e0;
}

p { margin-bottom: 8px; }

ul { margin: 6px 0 10px 20px; }
li { margin-bottom: 3px; }

strong { font-weight: 600; }

em { color: #666; font-style: italic; }

/* rating distribution bar */
li { font-variant-numeric: tabular-nums; }
"""


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:50]


def _to_dict(result: AnalysisResult) -> dict:
    return asdict(result)


def _stars(rating: int) -> str:
    """Return a star string like ★★★☆☆ for a given 1-5 rating."""
    filled = "★" * rating
    empty = "☆" * (5 - rating)
    return filled + empty


def _to_markdown(result: AnalysisResult) -> str:
    info = result.place_info
    lines = []

    # Header
    rating_str = f"★ {info.rating}" if info.rating else "★ N/A"
    address_str = info.address or "N/A"
    lines.append(f"# {info.title} — Review Report")
    lines.append(
        f"**{date.today().isoformat()}** · {address_str} · {rating_str} · "
        f"{result.fetched_reviews:,} of {result.total_reviews:,} reviews analyzed"
    )
    lines.append("\n---\n")

    # Rating distribution
    dist = result.rating_distribution
    total = dist.total()
    lines.append("## Rating Distribution\n")
    for stars, count in [(5, dist.five), (4, dist.four), (3, dist.three), (2, dist.two), (1, dist.one)]:
        pct = int((count / total) * 100) if total > 0 else 0
        bar = "█" * (pct // 5)
        lines.append(f"- {'★' * stars}{'☆' * (5 - stars)}  {bar}  {count} ({pct}%)")
    lines.append("\n---\n")

    # Keyword sections (only if segmentation data is available)
    if result.keyword_groups:
        for group in result.keyword_groups:
            neg_count = len(group.negative_segments)
            pos_count = len(group.positive_segments)

            # Section header
            neg_label = f"✗ {neg_count} negative" if neg_count else ""
            pos_label = f"✓ {pos_count} positive" if pos_count else ""
            counts = " · ".join(filter(None, [neg_label, pos_label]))
            lines.append(f"## {group.keyword}  {counts}\n")

            # Negative mentions (all shown)
            if group.negative_segments:
                lines.append(f"**Negative mentions** (all {neg_count}):")
                for seg in group.negative_segments:
                    lines.append(f'- {_stars(seg.review_rating)}  "{seg.text}"')
                lines.append("")

            # Positive mentions (top 3 by rating, with overflow note)
            if group.positive_segments:
                sorted_pos = sorted(
                    group.positive_segments, key=lambda s: -s.review_rating
                )
                shown = sorted_pos[:3]
                overflow = pos_count - len(shown)
                lines.append(f"**Positive mentions** (showing {len(shown)} of {pos_count}):")
                for seg in shown:
                    lines.append(f'- {_stars(seg.review_rating)}  "{seg.text}"')
                if overflow > 0:
                    lines.append(f"- *(+{overflow} more positive mentions)*")
                lines.append("")

            lines.append("---\n")
    else:
        # Fallback: no segmentation data
        lines.append("*No keyword segmentation data available.*\n")
        lines.append("---\n")

    return "\n".join(lines)


def _to_pdf_bytes(result: AnalysisResult) -> bytes:
    """Render the markdown report as PDF bytes via weasyprint."""
    import os
    from contextlib import contextmanager

    import markdown as md_lib
    from weasyprint import CSS, HTML

    @contextmanager
    def _suppress_c_stderr():
        """Redirect fd 2 to /dev/null to silence C-level GLib warnings."""
        devnull = os.open(os.devnull, os.O_WRONLY)
        saved = os.dup(2)
        os.dup2(devnull, 2)
        try:
            yield
        finally:
            os.dup2(saved, 2)
            os.close(saved)
            os.close(devnull)

    md_text = _to_markdown(result)
    body_html = md_lib.markdown(md_text, extensions=["tables", "nl2br"])
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{result.place_info.title} — Review Report</title></head>
<body>{body_html}</body>
</html>"""
    with _suppress_c_stderr():
        return HTML(string=full_html).write_pdf(stylesheets=[CSS(string=_PDF_CSS)])


def save_report(
    result: AnalysisResult,
    fmt: str = "markdown",
    output_dir: str = "./reports",
) -> str:
    """Save the analysis result to disk. Returns the file path."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    slug = _slugify(result.place_info.title)
    today = date.today().isoformat()

    if fmt == "json":
        filename = f"{slug}_{today}.json"
        filepath = output_path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(_to_dict(result), f, indent=2, ensure_ascii=False)
    elif fmt == "pdf":
        filename = f"{slug}_{today}.pdf"
        filepath = output_path / filename
        pdf_bytes = _to_pdf_bytes(result)
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)
    else:
        filename = f"{slug}_{today}.md"
        filepath = output_path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(_to_markdown(result))

    return str(filepath)
