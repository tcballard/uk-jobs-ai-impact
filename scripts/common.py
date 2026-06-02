"""Shared constants and helpers for the uk-jobs-neet pipeline."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from rich.console import Console

# ── Paths ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PAGES = DATA / "pages"
SITE = DATA / "site"
OCCUPATIONS_CSV = DATA / "occupations.csv"
SCORES_JSON = DATA / "scores.json"
SITE_DATA_JSON = SITE / "data.json"

for _d in (RAW, PAGES, SITE):
    _d.mkdir(parents=True, exist_ok=True)

# ── SOC 2020 major groups ─────────────────────────────────────────────
SOC_MAJOR_LABELS = {
    "1": "Managers, Directors & Senior Officials",
    "2": "Professional Occupations",
    "3": "Associate Professional & Technical",
    "4": "Administrative & Secretarial",
    "5": "Skilled Trades",
    "6": "Caring, Leisure & Other Services",
    "7": "Sales & Customer Service",
    "8": "Process, Plant & Machine Operatives",
    "9": "Elementary Occupations",
}

# Major groups with the highest density of entry-level roles (spec focus).
ENTRY_LEVEL_MAJOR_GROUPS = {"6", "7", "8", "9"}

# ── NOMIS ─────────────────────────────────────────────────────────────
NOMIS_BASE = "https://www.nomisweb.co.uk/api/v01"
NOMIS_UK_GEOGRAPHY = "2092957697"  # United Kingdom
NOMIS_APS_OCC = "NM_218_1"  # APS: occupation (SOC2020) by sex by employment type
# Earliest SOC2020 APS period and "latest" sentinel, for short-run growth.
NOMIS_BASE_DATE = "2021-12"

# ── National Careers Service ──────────────────────────────────────────
NCS_SITEMAP = "https://nationalcareers.service.gov.uk/explore-careers/sitemap.xml"
NCS_JOB_PROFILE_PREFIX = "https://nationalcareers.service.gov.uk/job-profiles/"

# ── ONS ASHE Table 14 (SOC2020, 2021 provisional — latest SOC2020 release) ─
ASHE_ZIP_URL = (
    "https://www.ons.gov.uk/file?uri=/employmentandlabourmarket/peopleinwork/"
    "earningsandworkinghours/datasets/earningsandhoursworkedallemployeesashetable14/"
    "2021/ashetable142021provisionalsoc20.zip"
)
ASHE_ANNUAL_MEMBER = "PROV - Occupation SOC20 (4) Table 14.7a   Annual pay - Gross 2021.xls"
ASHE_HOURLY_MEMBER = "PROV - Occupation SOC20 (4) Table 14.5a   Hourly pay - Gross 2021.xls"
ASHE_ZIP_CACHE = RAW / "ashe_table14_soc2020.zip"

# Heuristics for sector / regulation flags (refined later from NCS content).
PUBLIC_SECTOR_HINTS = (
    "nurse", "nursing", "teacher", "teaching assistant", "police", "paramedic",
    "firefighter", "social worker", "care worker", "nhs", "midwife", "armed forces",
    "prison officer", "civil service", "local government", "ambulance",
)
REGULATED_HINTS = (
    "solicitor", "barrister", "accountant", "surveyor", "architect", "pharmacist",
    "doctor", "dentist", "optometrist", "veterinary", "actuary", "electrician",
    "gas engineer", "social worker", "nurse", "paramedic",
)
APPRENTICESHIP_HINTS = (
    "electrician", "plumber", "carpenter", "bricklayer", "mechanic", "engineer",
    "welder", "joiner", "technician", "fitter", "installer", "chef", "hairdresser",
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Stopwords dropped before token-matching SOC titles to NCS slugs.
TITLE_STOPWORDS = {
    "and", "or", "the", "of", "a", "an", "to", "in", "for", "with", "other",
    "others", "related", "occupations", "occupation", "nec", "n", "e", "c",
    "including", "excluding", "etc",
}


def slugify(text: str) -> str:
    """Lowercase, hyphenate — matches NCS job-profile slug style."""
    return _NON_ALNUM.sub("-", text.lower()).strip("-")


def title_tokens(text: str) -> set[str]:
    """Singularised, stopword-filtered token set for fuzzy occupation matching."""
    return {
        w.rstrip("s")
        for w in _NON_ALNUM.split(text.lower())
        if w and w not in TITLE_STOPWORDS and len(w) > 1
    }


def dice(a: set[str], b: set[str]) -> float:
    """Sørensen–Dice coefficient over two token sets."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return 2 * inter / (len(a) + len(b)) if inter else 0.0


def soc_major_label(soc_code: str) -> tuple[str, str]:
    major = soc_code[0]
    return major, SOC_MAJOR_LABELS.get(major, "Unknown")


def is_unit_group(code: str) -> bool:
    """True for a 4-digit SOC 2020 unit group code."""
    return bool(re.fullmatch(r"\d{4}", code))


def any_hint(text: str, hints) -> bool:
    t = text.lower()
    return any(h in t for h in hints)


# ── Shared Rich console ───────────────────────────────────────────────
console = Console()

# ── HTTP ──────────────────────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (uk-jobs-neet research pipeline)"
HTTP_HEADERS = {"User-Agent": USER_AGENT}


# ── CSV / data loading ────────────────────────────────────────────────
def load_occupations() -> list[dict[str, str]]:
    """Load data/occupations.csv as a list of row dicts."""
    with OCCUPATIONS_CSV.open() as f:
        return list(csv.DictReader(f))


def load_occupations_map() -> dict[str, dict[str, str]]:
    """Load data/occupations.csv keyed by soc_code."""
    return {r["soc_code"]: r for r in load_occupations()}


def filter_slice(rows: list[dict], *, include_all: bool) -> list[dict]:
    """Filter rows to the entry-level slice (SOC 6-9) unless include_all is True."""
    if include_all:
        return rows
    return [r for r in rows if r["soc_major_group"] in ENTRY_LEVEL_MAJOR_GROUPS]


def wants_all() -> bool:
    """Return True if --all was passed on the command line."""
    import sys
    return "--all" in sys.argv


# ── Type coercion from CSV strings ────────────────────────────────────
def parse_num(val, cast=float):
    """Convert a CSV value to a number (int or float), returning None for blanks."""
    if val in ("", None):
        return None
    try:
        return cast(val)
    except (TypeError, ValueError):
        return None


def parse_bool(val) -> bool:
    """Convert a CSV string to a boolean (True for 'true', '1', 'yes')."""
    return str(val).strip().lower() in ("true", "1", "yes")


# ── Logging ───────────────────────────────────────────────────────────
def write_log(path: Path, lines: list[str]) -> None:
    """Write a newline-separated log file if lines is non-empty."""
    if lines:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
