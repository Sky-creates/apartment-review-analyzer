# Apartment Review Analyzer — User Manual

A CLI tool that fetches Google Maps reviews for any apartment and runs AI-powered analysis to surface themes, sentiment, pros/cons, and a verdict — so you can evaluate a place before signing a lease.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [API Keys](#api-keys)
4. [Quick Start](#quick-start)
5. [CLI Reference](#cli-reference)
6. [How It Works](#how-it-works)
7. [Understanding the Terminal Output](#understanding-the-terminal-output)
8. [Saving Reports](#saving-reports)
9. [Caching](#caching)
10. [Troubleshooting](#troubleshooting)

---

## Requirements

- Python 3.10 or higher
- A [SerpAPI](https://serpapi.com) account (for Google Maps review fetching)
- An [OpenRouter](https://openrouter.ai) account (for AI analysis via Gemini 2.5 Flash)

For PDF export, `weasyprint` requires no additional system libraries on most platforms (bundled since v60). If you encounter font issues on Linux, install `libpango-1.0`.

---

## Installation

```bash
# Clone or download the project
cd google-review

# Install dependencies
pip install -r requirements.txt
```

---

## API Keys

Both keys are required. Copy the template and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
SERPAPI_KEY=your_serpapi_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**Where to get them:**

| Key | Where |
|-----|-------|
| `SERPAPI_KEY` | [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key) |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |

SerpAPI offers 100 free searches/month. OpenRouter charges per token — Gemini 2.5 Flash is very cheap (typically <$0.01 per analysis run).

---

## Quick Start

```bash
python main.py "Avalon Mission Bay San Francisco"
```

If multiple results are found, you'll see a numbered table and be prompted to select one:

```
┌───┬──────────────────────────────────┬────────┬─────────┬─────────────────────────────┐
│ # │ Name                             │ Rating │ Reviews │ Address                     │
├───┼──────────────────────────────────┼────────┼─────────┼─────────────────────────────┤
│ 1 │ Avalon Mission Bay               │ 3.9    │ 312     │ 438 Mission Bay Blvd N, SF  │
│ 2 │ Avalon at Mission Bay            │ 4.1    │ 87      │ 1200 4th St, San Francisco  │
└───┴──────────────────────────────────┴────────┴─────────┴─────────────────────────────┘

Select apartment [1-2]:
```

The tool fetches reviews and displays the full analysis in your terminal.

---

## CLI Reference

```
python main.py <query> [options]
```

### Positional Argument

| Argument | Description |
|----------|-------------|
| `query` | Apartment name or search phrase (use quotes for multi-word queries) |

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--limit N` | `200` | Max reviews to fetch. `0` = fetch all available. |
| `--model MODEL_ID` | `google/gemini-2.5-flash` | OpenRouter model ID for analysis. |
| `--save FORMAT [FORMAT ...]` | _(none)_ | Save report in one or more formats: `markdown`, `json`, `pdf`, `all`. |
| `--output-dir DIR` | `./reports` | Directory where saved reports are written. |
| `--no-cache` | _(cache on)_ | Bypass the local cache and make fresh API and LLM calls. |
| `--top-n N` | `5` | Number of search results to show when selecting an apartment. |
| `-h, --help` | | Show help and exit. |

### Examples

```bash
# Basic run — fetch 200 reviews, display in terminal
python main.py "Avalon Mission Bay San Francisco"

# Save as PDF
python main.py "NEMA San Francisco" --save pdf

# Save in multiple formats at once
python main.py "NEMA San Francisco" --save pdf markdown

# Save in all formats (markdown + json + pdf)
python main.py "NEMA San Francisco" --save all

# Fetch more reviews and save as JSON
python main.py "One Mission Bay" --limit 300 --save json

# Fetch all available reviews
python main.py "One Mission Bay" --limit 0 --save pdf

# Skip cache for a completely fresh run
python main.py "The Avery San Francisco" --no-cache

# Use a different AI model
python main.py "Strata SF" --model google/gemini-2.5-pro

# Show up to 10 search results when picking
python main.py "luxury apartments San Francisco" --top-n 10

# Save to a custom directory
python main.py "NEMA SF" --save pdf --output-dir ~/Desktop/reports
```

---

## How It Works

```
Your query
    │
    ▼
SerpAPI Google Maps Search
    │   Returns up to --top-n results
    ▼
You select an apartment
    │
    ▼
SerpAPI Reviews Fetch (paginated)
    │   Up to --limit reviews, newest first
    │   0.5s delay between pages
    ▼
Local stats computed
    │   Rating distribution, management response rate,
    │   representative positive/negative reviews
    ▼
LLM call 1 — Theme analysis (Gemini 2.5 Flash)
    │   All reviews sent in one prompt (≤500 reviews)
    │   Batched + synthesized for larger sets (>500)
    │   → Themes, pros/cons, verdict (terminal display + saved report)
    ▼
LLM call 2 — Keyword segmentation (Gemini 2.5 Flash)
    │   Each review split into keyword-tagged segments
    │   → Powers the saved report (markdown / pdf)
    ▼
Terminal display + optional report save
```

Both LLM calls are cached independently. A warm-cache run makes zero API calls and completes in under a second.

---

## Understanding the Terminal Output

### Header

Displays the apartment name, address, overall star rating, and total review count from Google Maps.

### Fetch Summary

```
Fetched 200 of 412 reviews  ·  Management replies to 23% of reviews
```

- **Fetched / Total**: How many reviews were analyzed vs. how many exist on Google Maps.
- **Management response rate**: Percentage of reviews that received an owner reply. Higher is generally better — it signals an engaged management team.

### Rating Distribution

A visual histogram of star ratings across all fetched reviews:

```
5 ★  ██████████████████░░  182  (44%)
4 ★  ██████░░░░░░░░░░░░░░   61  (15%)
3 ★  ████░░░░░░░░░░░░░░░░   33  ( 8%)
2 ★  ███░░░░░░░░░░░░░░░░░   29  ( 7%)
1 ★  ██████████░░░░░░░░░░  107  (26%)
```

A bimodal distribution (many 5-stars and many 1-stars) often signals polarizing management or inconsistent unit quality.

### Google-Extracted Topics

Keywords that Google Maps automatically extracted from all reviews, with a mention count. These drive the AI theme analysis categories.

### AI Theme Analysis

One panel per theme. Each panel contains:

| Field | Description |
|-------|-------------|
| **Theme name** | e.g., "Noise", "Management", "Parking" |
| **Sentiment badge** | `POSITIVE` / `NEGATIVE` / `MIXED` / `NEUTRAL` |
| **Mention count** | Approximate number of reviews touching this theme |
| **Summary** | 1-2 sentence AI-written description |
| **Keyword breakdown** | Specific phrases with positive vs. negative mention counts and a proportional bar |
| **Quotes** | 1-2 direct excerpts from actual reviews |

**Reading the keyword bar:**

```
thin walls    ████████████████████░░░░  23 bad  ·  2 good
quiet         ████░░░░░░░░░░░░░░░░░░░░   3 bad  ·  8 good
```

Longer bar = more total mentions. The `bad` / `good` counts show directionality.

### Overall

- **Pros**: Top positive points across all themes.
- **Cons**: Top negative points across all themes.
- **Verdict**: A 2-3 sentence AI-written summary paragraph.

### Recent Reviews

Side-by-side display of the most recent positive (4-5★) and negative (1-2★) reviews in their original words.

---

## Saving Reports

Use `--save` to write the analysis to disk. You can specify one or more formats in a single run.

```bash
# Single format
python main.py "NEMA SF" --save pdf
python main.py "NEMA SF" --save markdown
python main.py "NEMA SF" --save json

# Multiple formats at once
python main.py "NEMA SF" --save pdf markdown
python main.py "NEMA SF" --save pdf markdown json

# All formats
python main.py "NEMA SF" --save all
```

Files are saved to `./reports/` by default, named `<apartment-slug>_<date>.<ext>`:

```
reports/
├── nema-san-francisco_2026-03-08.pdf
├── nema-san-francisco_2026-03-08.md
└── nema-san-francisco_2026-03-08.json
```

Use `--output-dir` to change the save location:

```bash
python main.py "NEMA SF" --save pdf --output-dir ~/Desktop/apartment-research
```

### Report format (markdown and PDF)

The saved report has three sections:

**1. Keyword segments** — every review split into short phrases, tagged with a keyword and sentiment, grouped by keyword and sorted with the most-complained-about topics first.

**2. AI theme analysis** — the same themes shown in the terminal (sentiment, summary, pros, cons, quotes), appended after the keyword section.

**3. Overall verdict** — consolidated pros, cons, and a 2-3 sentence summary paragraph.

```
# NEMA San Francisco — Review Report
2026-03-08 · 8 10th St, San Francisco · ★ 4.1 · 200 of 412 reviews analyzed

---

## Rating Distribution
...

## noise  ✗ 15 negative · ✓ 3 positive

Negative mentions (all 15):
- ★☆☆☆☆  "Walls are paper thin, you can hear everything"
...

## maintenance team  ✓ 38 positive · ✗ 2 negative
...

---

## AI Theme Analysis

### ✗ Noise (~18 mentions)
Significant noise issues reported by multiple residents...
**Cons:** thin walls · street noise · construction

### ✓ Maintenance Team (~40 mentions)
...

---

## Overall

**Pros:** great location · responsive maintenance ...
**Cons:** noise issues · parking limited ...

Overall verdict paragraph...
```

**Key behaviors of the keyword section:**
- Ordered by **negative count descending** — worst issues appear first.
- **All** negative segments are shown.
- For positives, the **top 3 by star rating** are shown, with a count of additional mentions.
- Any keyword with at least 1 negative segment is always included, regardless of total mentions.

The JSON format saves the complete structured data (all themes, keyword groups, raw stats) and is suitable for further processing.

---

## Caching

All SerpAPI responses and LLM outputs are cached in `./cache/` as SHA256-keyed JSON files.

| What is cached | Cache key ingredients |
|----------------|-----------------------|
| Place search results | query + top_n |
| Reviews + topics | place data_id + limit |
| LLM theme analysis | model + place name + all review text |
| LLM keyword segmentation | model + place name + all review text |

**Implications:**
- Re-running the same query is **instant and free** — no API calls.
- Changing `--limit` creates a new review cache entry (different review set).
- Changing `--model` creates new LLM cache entries.
- The theme and segmentation caches are **independent** — one can be stale while the other is fresh.
- There is **no expiry**. Delete `./cache/` to clear everything.

```bash
# Use cached data (default)
python main.py "NEMA SF"

# Force fresh data — ignores and overwrites all cache entries
python main.py "NEMA SF" --no-cache
```

Use `--no-cache` when:
- You want the latest reviews from Google Maps.
- You suspect a cached LLM response missed something.
- You've changed `--model` and want a fresh analysis with the new model.

---

## Troubleshooting

### "No results found"

The search query didn't match any Google Maps listings. Try:
- Adding the city name: `"NEMA San Francisco"` instead of `"NEMA"`
- Using the full address or neighborhood
- Checking spelling

### "No review text found"

Reviews were fetched but all had empty text. This is rare — try `--no-cache` to re-fetch.

### SerpAPI errors / rate limits

SerpAPI returns a 429 if you exceed your plan's request rate. The tool automatically retries once after a 2-second pause. If errors persist, wait a minute and re-run (the cache will pick up where it left off).

### LLM returns malformed JSON

Gemini 2.5 Flash reliably returns valid JSON, but if it doesn't, the tool raises a `ValueError` with the raw response. Run with `--no-cache` to retry the LLM call.

### Missing API key errors

```
Error: SERPAPI_KEY not set.
Error: OPENROUTER_API_KEY not set.
```

Ensure your `.env` file exists in the project root and contains both keys. The file must be named exactly `.env` (not `.env.txt`).

### Report shows no negative keywords

If the saved report only shows positive keywords, the segmentation LLM call may have missed negatives on a previous run. Re-run with `--no-cache` to force a fresh segmentation:

```bash
python main.py "Harper Apartments Boston" --no-cache --save pdf
```

### Slow first run

Fetching 200+ reviews requires multiple paginated SerpAPI calls (0.5s delay each). Expect 10-30 seconds for the fetch phase. Subsequent runs use the cache and are near-instant.

### PDF generation warnings

GLib warnings like `g_object_unref: assertion 'G_IS_OBJECT (object)' failed` may appear during PDF generation on some systems. These are harmless internal messages from the rendering library and do not affect the output.
