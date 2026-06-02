"""
fetch_soc.py — Build data/occupations.csv for SOC 2020 unit groups.

Data sources (LMI for All was decommissioned Oct 2025; this replaces it):
  - NOMIS NM_218_1 (APS occupation SOC2020) → SOC structure + employment + growth
  - ONS ASHE Table 14 (2021 provisional SOC2020) → median annual/hourly pay
  - National Careers Service explore-careers sitemap → ncs_url (fuzzy matched)

Usage:
    uv run python scripts/fetch_soc.py
"""
from __future__ import annotations

import csv
import io
import re
import sys
import zipfile

import httpx
import xlrd

from common import (
    APPRENTICESHIP_HINTS,
    ASHE_ANNUAL_MEMBER,
    ASHE_HOURLY_MEMBER,
    ASHE_ZIP_CACHE,
    ASHE_ZIP_URL,
    ENTRY_LEVEL_MAJOR_GROUPS,
    HTTP_HEADERS,
    NCS_JOB_PROFILE_PREFIX,
    NCS_SITEMAP,
    NOMIS_APS_OCC,
    NOMIS_BASE,
    NOMIS_BASE_DATE,
    NOMIS_UK_GEOGRAPHY,
    OCCUPATIONS_CSV,
    PUBLIC_SECTOR_HINTS,
    REGULATED_HINTS,
    any_hint,
    console,
    dice,
    is_unit_group,
    soc_major_label,
    title_tokens,
)

NCS_MATCH_THRESHOLD = 0.5  # Dice; precision-oriented (misses fall back in parse step)

CSV_FIELDS = [
    "soc_code", "title", "soc_major_group", "soc_major_label", "employment_uk",
    "median_hourly_pay", "median_annual_pay", "growth_pct_5yr",
    "entry_level", "no_qualification_required", "apprenticeship_available",
    "public_sector", "regulated_profession", "ncs_url",
]


# ── NOMIS: employment + structure + growth ────────────────────────────
def fetch_employment() -> dict[str, dict]:
    """Return {soc_code: {title, employment_uk, growth_pct_5yr}} for unit groups."""
    url = (
        f"{NOMIS_BASE}/dataset/{NOMIS_APS_OCC}.data.json"
        f"?geography={NOMIS_UK_GEOGRAPHY}"
        f"&date={NOMIS_BASE_DATE},latest"
        "&jtype=0&ftpt=0&etype=0&c_sex=0&measure=1&measures=20100"
    )
    console.print("[cyan]NOMIS:[/] fetching APS employment by SOC2020 …")
    r = httpx.get(url, headers=HTTP_HEADERS, timeout=60)
    r.raise_for_status()
    obs = r.json()["obs"]

    # group observations by soc code, keep base + latest values
    by_code: dict[str, dict] = {}
    for o in obs:
        desc = o["soc2020_full"]["description"]  # e.g. "1111 : Chief executives …"
        m = re.match(r"(\d+)\s*:\s*(.+)", desc)
        if not m:
            continue
        code, title = m.group(1), m.group(2).strip()
        if not is_unit_group(code):
            continue
        val = o["obs_value"]["value"]
        period = o["time"]["value"]
        rec = by_code.setdefault(code, {"title": title, "base": None, "latest": None})
        # multiply APS counts (already absolute) — keep as int
        if period == NOMIS_BASE_DATE:
            rec["base"] = val
        else:
            rec["latest"] = val

    out: dict[str, dict] = {}
    for code, rec in by_code.items():
        latest = rec["latest"]
        base = rec["base"]
        growth = None
        if base and latest and base > 0:
            growth = round((latest - base) / base * 100, 1)
        out[code] = {
            "title": rec["title"],
            "employment_uk": int(latest) if latest else None,
            "growth_pct_5yr": growth,
        }
    console.print(f"[green]NOMIS:[/] {len(out)} unit groups with employment data")
    return out


# ── ONS ASHE Table 14: median pay ─────────────────────────────────────
def _download_ashe() -> bytes:
    if ASHE_ZIP_CACHE.exists():
        return ASHE_ZIP_CACHE.read_bytes()
    console.print("[cyan]ASHE:[/] downloading Table 14 zip (~7.5 MB) …")
    r = httpx.get(ASHE_ZIP_URL, headers=HTTP_HEADERS, timeout=180, follow_redirects=True)
    r.raise_for_status()
    ASHE_ZIP_CACHE.write_bytes(r.content)
    return r.content


def _parse_ashe_sheet(zf: zipfile.ZipFile, member: str) -> dict[str, float]:
    """Read 'All' sheet; map 4-digit SOC code → median (col 3). 'x' = suppressed."""
    wb = xlrd.open_workbook(file_contents=zf.read(member))
    sh = wb.sheet_by_name("All")
    out: dict[str, float] = {}
    for row in range(5, sh.nrows):
        code = str(sh.cell_value(row, 1)).strip()
        if not is_unit_group(code):
            continue
        median = sh.cell_value(row, 3)
        if isinstance(median, (int, float)) and median:
            out[code] = float(median)
    return out


def fetch_pay() -> tuple[dict[str, float], dict[str, float]]:
    data = _download_ashe()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        annual = _parse_ashe_sheet(zf, ASHE_ANNUAL_MEMBER)
        hourly = _parse_ashe_sheet(zf, ASHE_HOURLY_MEMBER)
    console.print(
        f"[green]ASHE:[/] {len(annual)} annual + {len(hourly)} hourly pay rows"
    )
    return annual, hourly


# ── NCS sitemap: fuzzy match titles → job-profile URLs ────────────────
def fetch_ncs_slugs() -> dict[str, set[str]]:
    console.print("[cyan]NCS:[/] fetching job-profile sitemap …")
    r = httpx.get(NCS_SITEMAP, headers=HTTP_HEADERS, timeout=60)
    r.raise_for_status()
    slugs = sorted(set(re.findall(r"/job-profiles/([a-z0-9-]+)", r.text)))
    console.print(f"[green]NCS:[/] {len(slugs)} job profiles")
    return {s: title_tokens(s.replace("-", " ")) for s in slugs}


def match_ncs_url(title: str, slug_tokens: dict[str, set[str]]) -> str | None:
    """Best Dice token-overlap match over the threshold (precision-oriented)."""
    a = title_tokens(title)
    if not a:
        return None
    best, best_score = None, 0.0
    for slug, b in slug_tokens.items():
        score = dice(a, b)
        if score > best_score:
            best, best_score = slug, score
    if best and best_score >= NCS_MATCH_THRESHOLD:
        return NCS_JOB_PROFILE_PREFIX + best
    return None


# ── Build CSV ─────────────────────────────────────────────────────────
def main() -> int:
    employment = fetch_employment()
    annual_pay, hourly_pay = fetch_pay()
    slug_tokens = fetch_ncs_slugs()

    rows = []
    for code in sorted(employment):
        emp = employment[code]
        title = emp["title"]
        major, major_label = soc_major_label(code)
        text = title  # only have the title at this stage; refined in parse step
        entry_level = major in ENTRY_LEVEL_MAJOR_GROUPS
        rows.append({
            "soc_code": code,
            "title": title,
            "soc_major_group": major,
            "soc_major_label": major_label,
            "employment_uk": emp["employment_uk"] or "",
            "median_hourly_pay": hourly_pay.get(code, ""),
            "median_annual_pay": (
                int(annual_pay[code]) if code in annual_pay else ""
            ),
            "growth_pct_5yr": "" if emp["growth_pct_5yr"] is None else emp["growth_pct_5yr"],
            "entry_level": entry_level,
            "no_qualification_required": "",  # filled from NCS content in parse step
            "apprenticeship_available": any_hint(text, APPRENTICESHIP_HINTS),
            "public_sector": any_hint(text, PUBLIC_SECTOR_HINTS),
            "regulated_profession": any_hint(text, REGULATED_HINTS),
            "ncs_url": match_ncs_url(title, slug_tokens) or "",
        })

    OCCUPATIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OCCUPATIONS_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)

    matched = sum(1 for r in rows if r["ncs_url"])
    slice_rows = [r for r in rows if r["soc_major_group"] in ENTRY_LEVEL_MAJOR_GROUPS]
    slice_matched = sum(1 for r in slice_rows if r["ncs_url"])
    with_pay = sum(1 for r in rows if r["median_annual_pay"] != "")
    console.print(
        f"\n[bold green]Wrote {len(rows)} occupations[/] → {OCCUPATIONS_CSV}\n"
        f"  NCS URL matched:        {matched}/{len(rows)}\n"
        f"  with annual pay:        {with_pay}/{len(rows)}\n"
        f"  SOC 6-9 (slice):        {len(slice_rows)}  (NCS matched {slice_matched})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
