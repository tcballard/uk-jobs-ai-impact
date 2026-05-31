# uk-jobs-neet

A data pipeline and interactive visualisation analysing AI and automation exposure across UK occupations — scoped specifically to **entry-level roles accessible to under-25s**, with direct relevance to the NEET (Not in Education, Employment or Training) population.

This is a fork/adaptation of [karpathy/jobs](https://github.com/karpathy/jobs), rebuilt for UK data sources, UK occupational classifications, and a youth employment policy lens.

---

## Project purpose

The US version scores all 342 BLS occupations for AI exposure. This project does the same for the UK, but narrows the frame: **which entry-level jobs are most and least at risk, and what does that mean for young people entering the labour market right now?**

The NEET population (approximately 900,000 under-25s in the UK as of 2024) disproportionately flows into the roles most exposed to near-term automation: retail, admin, basic logistics, call centres, data entry. This project makes that risk visible and points toward the roles with durability.

Secondary audience: careers advisers, DWP/Jobcentre Plus staff, youth employment charities (e.g. Youth Employment UK, Prince's Trust, Catch22), and policymakers looking at skills and labour market strategy.

---

## Repo structure

```
uk-jobs-neet/
├── CLAUDE.md                        # This file
├── README.md
├── pyproject.toml
├── .env.example
├── data/
│   ├── raw/                         # Scraped HTML from National Careers Service
│   ├── pages/                       # Cleaned Markdown per occupation
│   ├── occupations.csv              # SOC codes, pay, employment, growth
│   ├── scores.json                  # LLM AI exposure scores + entry-level flags
│   └── site/data.json               # Merged frontend payload
├── scripts/
│   ├── 01_fetch_soc.py              # Pull SOC 2020 unit groups + LMI for All data
│   ├── 02_scrape_ncs.py             # Scrape National Careers Service pages
│   ├── 03_parse.py                  # HTML → clean Markdown
│   ├── 04_score.py                  # LLM scoring via Anthropic Batch API
│   ├── 05_merge.py                  # Combine CSV + scores → site/data.json
│   └── 06_validate.py               # Sanity checks, coverage report
└── site/
    └── index.html                   # D3 treemap visualisation
```

---

## Data sources

### Primary: LMI for All API
- Base URL: `https://api.lmiformall.org.uk/api/v1/`
- Provides SOC 2020 unit group data: employment counts, median pay, growth projections
- No API key required. Returns JSON.
- Key endpoints:
  - `/soc/list` — all SOC 2020 unit groups with codes and titles
  - `/occupation/[soc_code]` — detail per occupation
- **Coverage:** ~369 SOC 2020 unit groups at 4-digit level

### Secondary: National Careers Service (NCS)
- Base URL: `https://nationalcareers.service.gov.uk/job-profiles/`
- Individual occupation pages with sections: *What you'll do*, *Skills required*, *How to become*, *What you'll earn*, *Career path*
- Must be scraped with Playwright (site blocks automated requests)
- ~800 occupation profiles — filter to those mappable to SOC 2020 unit groups

### Tertiary: NOMIS API (fallback for employment/pay gaps)
- Base URL: `https://www.nomisweb.co.uk/api/v01/`
- ONS official labour market statistics
- Use if LMI for All data is stale or missing for a given SOC code

### Entry-level classification source
- **Youth Employment UK occupational data** and **DWP/Jobcentre Plus Job Family frameworks** for entry-level flags
- Alternatively: derive from NCS page content — the "How to become" section specifies whether a role typically requires no prior qualifications/experience
- SOC major groups 6 (Caring/Leisure), 7 (Sales/Customer Service), 8 (Process/Plant), and 9 (Elementary) have the highest density of entry-level roles and are the primary focus

---

## Key data schema

### occupations.csv
```
soc_code, title, soc_major_group, soc_major_label, employment_uk,
median_hourly_pay, median_annual_pay, growth_pct_5yr,
entry_level, no_qualification_required, apprenticeship_available,
public_sector, regulated_profession, ncs_url
```

### scores.json (per occupation)
```json
{
  "soc_code": "7111",
  "title": "Sales and retail assistants",
  "ai_score": 7.8,
  "rationale": "High exposure due to self-checkout expansion, AI inventory management, and online retail displacement. Core customer interaction tasks provide partial buffer but volume roles are structurally at risk.",
  "key_factors": [
    "Routine transaction processing fully automatable",
    "Physical presence requirement provides short-term buffer",
    "Online retail continues to erode in-store headcount"
  ],
  "entry_level": true,
  "automation_timeline": "near-term",
  "safer_pivot": "Visual merchandiser, warehouse team leader, customer experience specialist"
}
```

### site/data.json
Merged payload combining all CSV fields + score fields. One record per occupation.

---

## LLM scoring prompt

Use this system prompt for `04_score.py`. Send each occupation's Markdown page content as user message.

```
You are analysing UK occupations for AI and automation exposure, with a specific 
focus on entry-level roles accessible to young people (under 25) with no or 
minimal qualifications.

Score each occupation from 0 to 10 on AI Exposure:
- How much will AI and automation reshape or displace this role by 2030?
- Consider: direct automation (AI doing the work) AND indirect displacement 
  (AI making workers so productive that fewer are needed)
- Digital, screen-based output = inherently higher exposure
- Physical presence, manual dexterity, unpredictable environments = natural barrier

UK-specific factors to weight:
- NHS and public sector roles: institutional procurement inertia slows deployment 
  even where technically feasible; weight down by ~1 point
- Regulated professions (solicitors, accountants, surveyors): compliance frameworks 
  create deployment lag
- Trades with chronic UK skills shortages (electricians, plumbers, heating engineers): 
  market pressure and physical complexity delay displacement
- Retail, admin, basic logistics: accelerating automation, weight up

Also assess:
- entry_level: true/false — is this role typically accessible with no prior 
  qualifications or less than 1 year experience?
- automation_timeline: "near-term" (0-5 years), "medium-term" (5-10 years), 
  "long-term" (10+ years), or "resistant"
- safer_pivot: if this is a high-exposure entry-level role, suggest 1-2 adjacent 
  roles with lower exposure that require similar or achievable skills

Calibration examples:
  0-1: Roofer, refuse collector, groundskeeper (physical, variable)
  2-3: Care worker, plumber, electrician (physical + human judgment)
  4-5: Registered nurse, primary school teacher (mixed)
  6-7: Accountant, HR manager, marketing executive (largely digital)
  8-9: Paralegal, data analyst, software developer (fully digital)
  10: Medical transcriptionist, copy editor, data entry clerk

Return JSON only — no preamble, no markdown fences:
{
  "ai_score": <float 0-10>,
  "rationale": "<2-3 sentences explaining the score>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "entry_level": <true|false>,
  "automation_timeline": "<near-term|medium-term|long-term|resistant>",
  "safer_pivot": "<suggestion or null if not entry-level or score < 6>"
}
```

---

## Script instructions

### 01_fetch_soc.py
1. Call LMI for All `/soc/list` to get all SOC 2020 unit groups
2. For each SOC code, call `/occupation/{soc_code}` to get pay, employment, growth
3. Assign `soc_major_group` (1–9) from first digit of SOC code
4. Build NCS URL slug mapping: pull `https://nationalcareers.service.gov.uk/sitemap.xml` 
   to get all job-profile URLs, then fuzzy-match titles to SOC entries
5. Write `data/occupations.csv`

**Entry-level flag logic:** Set `entry_level = true` if:
- SOC major group is 6, 7, 8, or 9, OR
- NCS "How to become" section contains phrases like "no qualifications needed", 
  "school leaver", "no experience required", "entry level", "apprenticeship"

### 02_scrape_ncs.py
1. Use Playwright in non-headless mode
2. Load URLs from `occupations.csv` `ncs_url` column
3. Rate limit: 2 second delay between requests, randomised ±0.5s
4. Cache HTML to `data/raw/{soc_code}.html` — skip if file exists
5. On failure: retry once after 10s, then log to `data/scrape_errors.log` and continue
6. Target sections to preserve: `div.job-profile-content`, skip nav/footer/related

### 03_parse.py
1. BeautifulSoup parse each `data/raw/{soc_code}.html`
2. Extract named sections into structured Markdown:
   ```
   # {title}
   ## What you'll do
   ## Skills required
   ## How to become
   ## Pay
   ## Career path and progression
   ```
3. Strip: cookie banners, nav elements, "You might also like" sections, 
   breadcrumbs, share buttons
4. Write to `data/pages/{soc_code}.md`
5. Flag any file missing Pay or "What you'll do" sections to `data/parse_warnings.log`

### 04_score.py
1. Use Anthropic Batch API (`POST /v1/messages/batches`) — do NOT use serial calls
2. Load all `.md` files from `data/pages/`
3. Build batch request list: one request per occupation with the system prompt above
4. Submit batch, poll every 60s until complete
5. Parse responses, extract JSON from each (strip any accidental markdown fences)
6. Write `data/scores.json` as array of objects keyed by `soc_code`
7. Log any failed/malformed responses to `data/score_errors.log` for manual review

**Model:** `claude-sonnet-4-5`  
**max_tokens:** 400 (the response schema is compact)  
**Expected cost:** ~400 occupations × ~2,000 tokens input + 300 output ≈ $8–10 total

### 05_merge.py
1. Load `data/occupations.csv` and `data/scores.json`
2. Join on `soc_code`
3. Add derived field: `risk_category`
   - score 0–3: "Lower risk"
   - score 4–6: "Moderate risk"  
   - score 7–8: "High risk"
   - score 9–10: "Very high risk"
4. Add derived field: `entry_level_risk` = `entry_level == true AND ai_score >= 7`
5. Write `data/site/data.json`

### 06_validate.py
Run these checks and print a summary report:
- Coverage: what % of SOC unit groups have scores
- Score distribution: print histogram (should be roughly normal, mean ~5)
- Entry-level coverage: how many entry-level roles scored
- High-risk entry-level count: how many `entry_level_risk == true`
- Missing pay data: flag any occupations with null `median_annual_pay`
- Suspiciously short rationales: flag any rationale under 50 characters

---

## Visualisation (site/index.html)

Adapt the D3 treemap from karpathy/jobs with these UK-specific changes:

### Layout
- Group by SOC 2020 major group (9 groups, not BLS categories)
- SOC major group labels:
  1. Managers, Directors & Senior Officials
  2. Professional Occupations
  3. Associate Professional & Technical
  4. Administrative & Secretarial
  5. Skilled Trades
  6. Caring, Leisure & Other Services
  7. Sales & Customer Service
  8. Process, Plant & Machine Operatives
  9. Elementary Occupations

### Colour scale
- Same green (safe) → red (exposed) scale as karpathy/jobs
- Area proportional to UK employment count

### Filter toggles (add these — not in the original)
- **Entry-level only** — filter to `entry_level == true`
- **High risk entry-level** — filter to `entry_level_risk == true`
- **Public sector** — filter to `public_sector == true`
- **Apprenticeship available** — filter to `apprenticeship_available == true`

### Tooltip (hover state)
Show:
- Occupation title
- SOC code
- AI Exposure score (e.g. "7.8 / 10")
- Risk category
- Median annual pay (£)
- UK employment count
- 5-year growth projection
- LLM rationale
- Safer pivot (if populated)
- Entry-level badge (if applicable)

### Colour mode toggle
Switch between:
1. AI Exposure (default)
2. Employment growth (green = growing, red = declining)

### Formatting
- Salary: `£XX,XXX` not `$`
- Employment: formatted with commas (e.g. `1,240,000`)
- Growth: `+3.2%` / `-1.4%`

---

## Environment setup

```bash
uv sync
uv run playwright install chromium
```

`.env` file:
```
ANTHROPIC_API_KEY=your_key_here
```

---

## Run order

```bash
uv run python scripts/01_fetch_soc.py
uv run python scripts/02_scrape_ncs.py
uv run python scripts/03_parse.py
uv run python scripts/04_score.py
uv run python scripts/05_merge.py
uv run python scripts/06_validate.py
cd site && python -m http.server 8000
```

---

## Key analytical questions the output should answer

These should drive the README narrative and any posts published about this project:

1. Which entry-level roles have the lowest AI exposure right now — i.e., where should a school leaver or NEET young person focus?
2. Which entry-level roles are already high-risk and likely to see headcount decline in the next 5 years?
3. What are the best "pivot" paths — low-barrier moves from a high-risk entry role to an adjacent lower-risk one?
4. Does the public sector provide a meaningful buffer for entry-level workers, or is that a false sense of security?
5. Which SOC major groups have the healthiest mix of low exposure + growing employment + accessible entry?

---

## Notes and constraints

- Do not score management consulting, law, finance, or medicine as primary focus — these are not realistic entry points for the NEET population
- Where NCS page content is missing or sparse, fall back to the SOC unit group description from the ONS SOC 2020 Volume 2 (task descriptions) — available at `https://www.ons.gov.uk/methodology/classificationsandstandards/standardoccupationalclassificationsoc/soc2020`
- The scoring is directional, not empirical — make this limitation explicit in the README and any published posts
- Do not conflate "AI exposure" with "job loss" in copy — the framing should be "likelihood of significant role change or headcount reduction" not "this job will disappear"

---

## Build note — data source change (2026)

**LMI for All was decommissioned at the end of October 2025** (`api.lmiforall.org.uk` no longer resolves; no official successor as of 2026). `scripts/fetch_soc.py` therefore does NOT use LMI for All. It sources data from:

- **SOC 2020 structure** (codes, titles, major groups): ONS SOC 2020 structure spreadsheet.
- **Employment + growth**: NOMIS API dataset `NM_218_1` (Annual Population Survey — occupation SOC2020 by sex by employment type), UK geography `2092957697`, `SOC2020_FULL` dimension. Growth is short-run year-over-year from the APS time dimension (labelled honestly; not a true 5-year projection).
- **Median pay**: ONS ASHE Table 14 (median gross annual + hourly pay by 4-digit SOC 2020), with NOMIS `NM_30_1` as backstop.
- **Scoring content**: National Careers Service scrape, with ONS SOC 2020 Volume 2 task descriptions as fallback where NCS pages are thin/missing.

Scripts use descriptive names (no numeric prefixes): `fetch_soc.py`, `scrape_ncs.py`, `parse_pages.py`, `score.py`, `merge.py`, `validate.py`.

**Tonight's scope:** entry-level slice = SOC major groups 6–9 scraped + scored. CSV/structure covers all ~370 unit groups; scrape/score target is the slice. Model: `claude-sonnet-4-6`.
