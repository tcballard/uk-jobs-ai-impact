# uk-jobs-neet

**Which entry-level jobs are most and least exposed to AI/automation — and what does that mean for young people entering the UK labour market right now?**

An interactive treemap and data pipeline scoring UK occupations (SOC 2020) for AI and automation
exposure, scoped to **entry-level roles accessible to under-25s** and the ~900,000-strong NEET
(Not in Education, Employment or Training) population. A UK adaptation of
[karpathy/jobs](https://github.com/karpathy/jobs).

> ⚠️ **The scoring is directional, not empirical.** Read a score as *“likelihood of significant
> role change or headcount reduction by 2030”* — **not** “this job will disappear”. It is an
> LLM’s structured judgement, useful for comparison and conversation, not a forecast.

---

## What it shows

A treemap of UK occupations grouped by SOC 2020 major group, tile area proportional to UK
employment, coloured green (lower exposure) → red (higher exposure). Toggles:

- **Colour by**: AI exposure, or employment growth (green = growing, red = declining)
- **Filters**: entry-level only · high-risk entry-level · public sector · apprenticeship available
- **Hover**: score, risk band, median pay (£), employment, recent growth, the model’s rationale,
  and — for high-risk entry-level roles — a suggested **safer pivot**.

Tonight’s build scores the **entry-level slice: SOC major groups 6–9** (~120 unit groups —
caring/leisure, sales/customer service, process/plant operatives, elementary occupations), where
the NEET population disproportionately enters work. The structure/CSV covers all ~370 unit groups,
so the scored set can be expanded by widening the scrape/score step.

---

## Data sources

LMI for All (the spec’s original source) was **decommissioned at the end of October 2025**, so the
pipeline sources data from:

| Field | Source |
|---|---|
| SOC 2020 codes, titles, major groups | NOMIS `NM_218_1` codelist (APS occupation SOC2020) |
| UK employment + recent growth | NOMIS `NM_218_1` (Annual Population Survey), UK, 2021→latest |
| Median annual / hourly pay | ONS **ASHE Table 14** (4-digit SOC 2020, latest SOC2020 release) |
| Role content for scoring | **National Careers Service** job profiles (httpx scrape) |

Growth is a recent **year-over-year** APS change, **not** a 5-year projection, and is noisy for
small occupations — labelled honestly in the tooltip and capped in the colour scale.

---

## Pipeline

```bash
uv sync
uv run playwright install chromium          # optional; the scraper uses plain HTTP
cp .env.example .env                          # add ANTHROPIC_API_KEY for the scoring step

uv run python scripts/fetch_soc.py            # → data/occupations.csv  (all ~370 unit groups)
uv run python scripts/scrape_ncs.py           # → data/raw/*.html       (SOC 6–9 slice)
uv run python scripts/parse_pages.py          # → data/pages/*.md       (NCS content or SOC stub)
uv run python scripts/score.py                # → data/scores.json      (Anthropic Batch API)
uv run python scripts/merge.py                # → data/site/data.json + site/data.json
uv run python scripts/validate.py             # coverage / sanity report

cd site && python -m http.server 8000         # open http://localhost:8000
```

- **Scoring** uses the Anthropic **Message Batches API** (`claude-sonnet-4-6`, `max_tokens=400`),
  one request per occupation with a shared, prompt-cached system prompt and a strict JSON-schema
  output. ~120 occupations costs roughly **$2–3**. Requires `ANTHROPIC_API_KEY` in `.env`.
- Where no NCS profile matches a SOC unit group, `parse_pages.py` writes a compact title + major-group
  stub so every occupation in the slice is still scored.

---

## The questions this is meant to answer

1. Which entry-level roles have the **lowest** AI exposure right now — where should a school leaver
   or NEET young person focus?
2. Which entry-level roles are already **high-risk** and likely to see headcount decline?
3. What are the best **pivot paths** — low-barrier moves from a high-risk entry role to an adjacent
   lower-risk one?
4. Does the **public sector** provide a meaningful buffer for entry-level workers, or a false sense
   of security?
5. Which SOC major groups have the healthiest mix of **low exposure + growing employment +
   accessible entry**?

Use the filters and the two colour modes to read these off the treemap directly.

---

## Caveats

- Directional, not empirical — see the note at the top.
- “AI exposure” ≠ “job loss”. The framing is *role change / headcount reduction*, not disappearance.
- Pay is from the latest SOC2020 ASHE release and may lag the current year; some 4-digit cells are
  suppressed (shown as n/a).
- The focus is realistic entry points for under-25s — law, finance, medicine and management
  consulting are deliberately **not** the centre of attention.

---

## Layout

```
scripts/  fetch_soc · scrape_ncs · parse_pages · score · merge · validate  (+ common.py)
data/     occupations.csv · scores.json · site/data.json · raw/ · pages/
site/     index.html (D3 treemap)
```
