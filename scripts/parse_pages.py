"""
parse_pages.py — Turn scraped NCS HTML into clean per-occupation Markdown.

Iterates the entry-level slice (SOC 6–9). For each occupation:
  - if data/raw/{soc}.html exists → extract the named sections
  - else → write a compact stub from the SOC title + major group + LMI context
    (so every slice occupation still gets scored)

Writes data/pages/{soc}.md and flags thin pages to data/parse_warnings.log.

Usage:
    uv run python scripts/parse_pages.py            # slice (SOC 6-9)
    uv run python scripts/parse_pages.py --all      # every row with a raw page
"""
from __future__ import annotations

import re
import sys

from bs4 import BeautifulSoup

from common import (
    PAGES,
    RAW,
    console,
    filter_slice,
    load_occupations,
    soc_major_label,
    wants_all,
    write_log,
)

WARN_LOG = RAW.parent / "parse_warnings.log"

# NCS heading id suffix → Markdown section title (in output order)
SECTIONS = [
    ("what-youll-do", "What you'll do"),
    ("what-it-takes", "Skills required"),
    ("how-to-become", "How to become"),
    ("career-path-and-progression", "Career path and progression"),
]
NO_QUAL_PHRASES = (
    "no qualifications", "no formal qualifications", "without qualifications",
    "school leaver", "no experience", "entry level", "entry-level",
    "apprenticeship", "no set requirements", "no specific requirements",
)


def _clean(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _section_text(soup: BeautifulSoup, suffix: str) -> str:
    h = soup.find("h2", id=lambda x: bool(x) and x.endswith(f"heading-{suffix}"))
    if not h:
        return ""
    parts: list[str] = []
    for sib in h.find_next_siblings():
        if sib.name == "h2":
            break
        # convert list items to bullets, keep paragraph text
        for li in sib.find_all("li"):
            li.insert_before("\n- ")
        parts.append(sib.get_text(" ", strip=True))
    return _clean("\n".join(p for p in parts if p))


def _salary_text(soup: BeautifulSoup) -> str:
    h = next(
        (h for h in soup.find_all("h2")
         if "average salary" in h.get_text(strip=True).lower()),
        None,
    )
    if not h:
        return ""
    bits = []
    for sib in h.find_next_siblings():
        if sib.name == "h2":
            break
        t = sib.get_text(" ", strip=True)
        if "£" in t:
            bits.append(t)
    return _clean(" ".join(bits))[:200]


def _lmi_line(row: dict) -> str:
    emp = f"{int(row['employment_uk']):,}" if row["employment_uk"] else "n/a"
    pay = f"£{int(row['median_annual_pay']):,}" if row["median_annual_pay"] else "n/a"
    growth = f"{row['growth_pct_5yr']}%" if row["growth_pct_5yr"] else "n/a"
    return (
        f"UK employment: {emp}. Median annual pay: {pay}. "
        f"Recent employment change: {growth}."
    )


def parse_html(row: dict, html: str) -> tuple[str, bool]:
    """Return (markdown, thin?) for a scraped NCS page."""
    soup = BeautifulSoup(html, "lxml")
    title = row["title"]
    lines = [f"# {title}", "", f"_SOC {row['soc_code']} · {row['soc_major_label']}_",
             "", f"## UK labour market", _lmi_line(row)]
    found_core = False
    full_text = ""
    for suffix, heading in SECTIONS:
        body = _section_text(soup, suffix)
        if body:
            lines += ["", f"## {heading}", body]
            full_text += " " + body.lower()
            if suffix in ("what-youll-do", "how-to-become"):
                found_core = True
    salary = _salary_text(soup)
    if salary:
        lines += ["", "## Pay", salary]

    # entry-level signal from "How to become" content
    no_qual = any(p in full_text for p in NO_QUAL_PHRASES)
    row["_no_qual"] = no_qual
    thin = not found_core or len(full_text) < 200
    return "\n".join(lines) + "\n", thin


def stub_markdown(row: dict) -> str:
    _, label = soc_major_label(row["soc_code"])
    return (
        f"# {row['title']}\n\n"
        f"_SOC {row['soc_code']} · {label}_\n\n"
        f"## UK labour market\n{_lmi_line(row)}\n\n"
        f"## About this occupation\n"
        f"This is SOC 2020 unit group {row['soc_code']} in the '{label}' major group. "
        f"No detailed National Careers Service profile was matched for this unit group; "
        f"score from the occupation title and category, treating it as a typical "
        f"'{label.lower()}' role.\n"
    )


def main() -> int:
    include_all = wants_all()
    rows = load_occupations()
    targets = filter_slice(rows, include_all=include_all)
    warnings: list[str] = []
    from_html = stubbed = 0

    for row in targets:
        soc = row["soc_code"]
        raw = RAW / f"{soc}.html"
        if raw.exists():
            md, thin = parse_html(row, raw.read_text(encoding="utf-8"))
            from_html += 1
            if thin:
                warnings.append(f"{soc}\t{row['title']}\tthin/missing core sections")
        else:
            md = stub_markdown(row)
            stubbed += 1
            warnings.append(f"{soc}\t{row['title']}\tno NCS page (stub)")
        (PAGES / f"{soc}.md").write_text(md, encoding="utf-8")

    write_log(WARN_LOG, warnings)
    console.print(
        f"[bold green]Wrote {len(targets)} markdown pages[/] → {PAGES}\n"
        f"  from NCS HTML: {from_html}\n"
        f"  stubbed:       {stubbed}\n"
        f"  warnings:      {len(warnings)}"
        + (f" → {WARN_LOG}" if warnings else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
