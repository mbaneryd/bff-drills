# BFF Drills – Övningsbank för Bällsta FF

A browsable football exercise bank for youth coaching at Bällsta FF. Built with Hugo, hosted on GitHub Pages. Contains exercises from three sources plus training plans.

## Data scope

- **420 SvFF exercises** — from Svenska Fotbollförbundets Övningsbanken, filtered to 3v3, 5v5, and 7v7
- **71 JSK exercises** — extracted from Järna Sportklubb PDFs (7–9 år 5v5, 10–12 år 7v7)
- **61 SIK exercises** — extracted from Sundbybergs IK training session PDFs (5v5)
- **142 training sessions** — 92 SvFF + 38 JSK + 12 SIK
- **Reference pages** — SIK årsplan, JSK träningsplanering

## File structure

```
bff-drills/
  hugo.yaml                     # Hugo configuration
  .github/workflows/deploy.yml  # GitHub Actions → GitHub Pages

  content/                      # Hugo content (published as website)
    exercises/{svff,jsk,sik}/   # Exercise markdown files with YAML frontmatter
    sessions/{svff,jsk,sik}/    # Training session markdown files
    pages/                      # Reference pages (årsplan, träningsplanering)

  static/images/{svff,jsk,sik}/ # Exercise diagram images (PNG/JPG)
  layouts/                      # Hugo templates
  assets/css/                   # Stylesheet

  tools/                        # Extraction & data pipeline scripts
    common.py                   # Shared helpers: write_exercise_md(), write_session_md()
    extract_svff.py             # SvFF scraper (uses Playwright browser)
    extract_jsk.py              # JSK PDF exercise extraction (pdfplumber)
    extract_jsk_images.py       # JSK diagram image extraction from PDFs
    extract_jsk_sessions.py     # JSK training session extraction from PDFs
    extract_sik.py              # SIK PDF extraction (pdfplumber + pdftoppm)
    migrate_to_hugo.py          # Regenerate all markdown from JSON manifests in sources/
    fetch_batch.py              # SvFF batch processor (browser fetch results)
    process_batch.py            # SvFF batch result processor

  sources/                      # Source PDFs and raw extracted data
    svff/                       # SvFF listing, filters, session manifests
    jsk/                        # JSK PDFs + extracted manifests
    sik/                        # SIK PDFs (5v5/) + extracted manifests
    ballsta/                    # Bällsta FF policy document

  plans/                        # Training plans (not published on site)
    traningsplan.md             # Main season plan (7-year-olds, v4)
    ramverk.md                  # BFF training plan framework
    blocks/                     # Block-specific plans (block1-7)
    pdfs/                       # Block PDFs
    generated/                  # Generated documents (docx)
```

## Running locally

```bash
hugo server
# Opens at http://localhost:1313/bff-drills/
```

## Adding or editing exercises

Edit markdown files in `content/exercises/{source}/`. Each exercise has YAML frontmatter with structured data and a markdown body with sections (Vad?, Varför?, Organisation, Anvisningar, Progressioner).

## Extracting from new sources

All scripts are run from the project root:

```bash
# Extract exercises from PDFs (generates markdown + images)
python3 tools/extract_sik.py              # SIK PDFs → content/exercises/sik/ + static/images/sik/
python3 tools/extract_jsk.py              # JSK PDFs → content/exercises/jsk/ + static/images/jsk/
python3 tools/extract_jsk_images.py       # JSK diagram images → static/images/jsk/
python3 tools/extract_jsk_sessions.py     # JSK sessions → content/sessions/jsk/

# Regenerate all markdown from JSON manifests (no PDF re-extraction)
python3 tools/migrate_to_hugo.py
```

The extraction scripts output Hugo markdown (YAML frontmatter + markdown body) directly to `content/` and images to `static/images/`. JSON manifests are saved to `sources/` for reference.

Shared markdown generation logic lives in `tools/common.py` (`write_exercise_md()` and `write_session_md()`). When adding a new source, use these helpers to ensure consistent output format.

### SvFF scraping (special case)

SvFF exercises require an authenticated browser session (SvFF login). The scraping uses Playwright MCP to run `fetch()` inside an already-logged-in browser:

```bash
# 1. Log in to ovningsbanken.svenskfotboll.se in Playwright browser
# 2. Run batch fetch via browser_evaluate
# 3. Process results:
python3 tools/process_batch.py
```

## Exercise data format

All exercises share a common frontmatter structure:

```yaml
title: "Exercise name"
exerciseId: 48347           # or string like "jsk_7_9_1"
source: "svff_ovningsbanken" # or "jsk_ovningsbank" or "sik_traningsplanering"
levels:
  3v3: false
  5v5: true
  7v7: false
image: "svff/48347.png"     # relative to static/images/
```

Source-specific fields: SvFF has `category`, `topic`, `exerciseType`, `videoUrl`. JSK has `ageGroup`, `gameFormat`. SIK has `tema`, `duration`, `areaSize`, `playerSkills`.

## Navigation

- `/exercises/` — browse all 552 exercises with filtering
- `/sessions/` — browse all 142 training sessions
- `/sik-arsplan/` — SIK yearly training plan and principles
- `/jsk-traningsplanering/` — JSK training planning guide
