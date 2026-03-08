# ApartmentLens

AI-powered Google Maps review analyzer for apartment hunters. Fetch hundreds of reviews, surface what renters actually complain about, and get a keyword-by-keyword breakdown — in seconds.

```
python main.py "Avalon Mission Bay San Francisco" --save pdf
```

---

## What it does

Most apartments have a 4.x rating and glowing recent reviews. ApartmentLens digs deeper:

- Fetches up to all available Google Maps reviews (paginated)
- Runs two AI passes: **theme analysis** (terminal) + **keyword segmentation** (report)
- Shows you the most-complained-about topics first — noise, management, maintenance, etc.
- Exports clean **PDF**, **Markdown**, or **JSON** reports

```
## noise  ✗ 15 negative · ✓ 3 positive

Negative mentions (all 15):
- ★☆☆☆☆  "Walls are paper thin, you can hear everything"
- ★☆☆☆☆  "Street noise from construction starts at 7am"
  ...

## maintenance team  ✓ 38 positive · ✗ 2 negative

Negative mentions (all 2):
- ★★☆☆☆  "Took 3 weeks to fix the broken heat"

Positive mentions (showing 3 of 38):
- ★★★★★  "Miguel fixed my issue within the hour"
```

---

## Quick start

**1. Install**

```bash
pip install -r requirements.txt
```

**2. Add API keys**

```bash
cp .env.example .env
# edit .env and add your keys
```

You need two free accounts:
- [SerpAPI](https://serpapi.com) — fetches Google Maps reviews (100 free searches/month)
- [OpenRouter](https://openrouter.ai) — runs the AI analysis via Gemini 2.5 Flash (<$0.01 per run)

**3. Run**

```bash
python main.py "NEMA San Francisco" --save pdf
```

---

## CLI reference

```
python main.py <query> [options]

Options:
  --limit N           Max reviews to fetch (default: 200, 0 = all)
  --save FORMAT       markdown, json, pdf, all — or multiple: --save pdf markdown
  --output-dir DIR    Where to save reports (default: ./reports)
  --no-cache          Force fresh API + LLM calls
  --top-n N           Search results to show (default: 5)
  --model MODEL_ID    OpenRouter model (default: google/gemini-2.5-flash)
```

**Examples:**

```bash
# Save in all formats
python main.py "The Avery SF" --save all

# Fetch every available review
python main.py "One Mission Bay" --limit 0 --save pdf

# Force a fresh run (bypass cache)
python main.py "NEMA SF" --no-cache --save pdf markdown
```

---

## How it works

```
Search query → SerpAPI Google Maps → paginated review fetch
    → LLM 1: theme analysis       (terminal display)
    → LLM 2: keyword segmentation (saved report)
    → PDF / Markdown / JSON export
```

All API responses and LLM outputs are **cached locally** in `./cache/`. Re-running the same query is instant and costs nothing.

---

## Output formats

| Format | Contents |
|--------|----------|
| **Terminal** | Themes, sentiment, keyword bars, quotes, verdict |
| **PDF / Markdown** | Keyword-centric report sorted by most-negative topic first |
| **JSON** | Full structured data — themes, keyword groups, rating distribution, raw stats |

---

## Requirements

- Python 3.10+
- SerpAPI key
- OpenRouter key

See [USER_MANUAL.md](USER_MANUAL.md) for full documentation including caching behavior, troubleshooting, and report format details.

---

## License

MIT
