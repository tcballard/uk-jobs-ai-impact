"""
validate.py — Coverage and sanity report for the scored dataset.

Usage:
    uv run python scripts/validate.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter

from rich.console import Console
from rich.table import Table

from common import ENTRY_LEVEL_MAJOR_GROUPS, OCCUPATIONS_CSV, SITE_DATA_JSON

console = Console()


def main() -> int:
    if not SITE_DATA_JSON.exists():
        console.print("[red]data/site/data.json not found. Run merge.py first.[/]")
        return 1
    data = json.loads(SITE_DATA_JSON.read_text())
    with OCCUPATIONS_CSV.open() as f:
        all_rows = list(csv.DictReader(f))

    n = len(data)
    n_units = len(all_rows)
    slice_total = sum(1 for r in all_rows if r["soc_major_group"] in ENTRY_LEVEL_MAJOR_GROUPS)

    scores = [d["ai_score"] for d in data]
    mean = sum(scores) / n if n else 0
    entry = [d for d in data if d["entry_level"]]
    elr = [d for d in data if d["entry_level_risk"]]
    null_pay = [d for d in data if d.get("median_annual_pay") is None]
    short_rat = [d for d in data if len(d.get("rationale", "")) < 50]

    console.rule("[bold]uk-jobs-neet coverage report")
    console.print(f"Scored occupations:        {n} / {n_units} SOC unit groups "
                  f"({100 * n / n_units:.0f}%)")
    console.print(f"Entry-level slice (6-9):   {slice_total} unit groups; "
                  f"{len(entry)} scored as entry-level")
    console.print(f"Mean AI exposure:          {mean:.2f}  (expect ~5)")
    console.print(f"High-risk entry-level:     {len(elr)}")
    console.print(f"Null median pay:           {len(null_pay)}")
    console.print(f"Rationales under 50 chars: {len(short_rat)}")

    # Histogram (integer buckets 0-10).
    buckets = Counter(min(int(s), 10) for s in scores)
    table = Table(title="\nScore distribution", show_edge=False)
    table.add_column("bucket", justify="right")
    table.add_column("count")
    table.add_column("histogram")
    peak = max(buckets.values()) if buckets else 1
    for b in range(11):
        c = buckets.get(b, 0)
        bar = "█" * int(40 * c / peak) if c else ""
        table.add_row(f"{b}–{b+1}", str(c), bar)
    console.print(table)

    # Risk category breakdown (in severity order).
    cats = Counter(d["risk_category"] for d in data)
    severity_order = ["Lower risk", "Moderate risk", "High risk", "Very high risk"]
    console.print("\n[bold]Risk categories:[/] " +
                  "  ".join(f"{k}: {cats.get(k, 0)}" for k in severity_order))

    if null_pay:
        console.print("\n[yellow]Occupations missing pay:[/] " +
                      ", ".join(d["soc_code"] for d in null_pay[:15]) +
                      (" …" if len(null_pay) > 15 else ""))
    if short_rat:
        console.print("[yellow]Suspiciously short rationales:[/] " +
                      ", ".join(d["soc_code"] for d in short_rat))
    return 0


if __name__ == "__main__":
    sys.exit(main())
