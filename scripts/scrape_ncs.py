"""
scrape_ncs.py — Fetch National Careers Service job-profile pages.

NCS pages are server-rendered, so a plain HTTP GET works (no Playwright needed).
Scoped tonight to the entry-level slice: SOC major groups 6–9 with an ncs_url.

  - Rate limit: ~2s ± 0.5s between requests
  - Cache HTML to data/raw/{soc_code}.html (skip if present)
  - Retry once after 10s on failure, then log and continue

Usage:
    uv run python scripts/scrape_ncs.py            # slice only (SOC 6-9)
    uv run python scripts/scrape_ncs.py --all      # every row with an ncs_url
"""
from __future__ import annotations

import csv
import random
import sys
import time

import httpx
from rich.console import Console

from common import ENTRY_LEVEL_MAJOR_GROUPS, OCCUPATIONS_CSV, RAW

console = Console()
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) uk-jobs-neet"}
ERR_LOG = RAW.parent / "scrape_errors.log"


def load_targets(all_rows: bool) -> list[tuple[str, str]]:
    with OCCUPATIONS_CSV.open() as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if not r["ncs_url"]:
            continue
        if not all_rows and r["soc_major_group"] not in ENTRY_LEVEL_MAJOR_GROUPS:
            continue
        out.append((r["soc_code"], r["ncs_url"]))
    return out


def fetch(client: httpx.Client, url: str) -> str | None:
    for attempt in (1, 2):
        try:
            r = client.get(url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            return r.text
        except Exception as exc:  # noqa: BLE001
            if attempt == 1:
                time.sleep(10)
            else:
                return f"__ERROR__{exc}"
    return None


def main() -> int:
    all_rows = "--all" in sys.argv
    targets = load_targets(all_rows)
    console.print(
        f"[cyan]Scraping {len(targets)} NCS pages "
        f"({'all groups' if all_rows else 'SOC 6-9 slice'})[/]"
    )
    errors: list[str] = []
    fetched = skipped = 0

    with httpx.Client(headers=UA) as client:
        for i, (soc_code, url) in enumerate(targets, 1):
            dest = RAW / f"{soc_code}.html"
            if dest.exists():
                skipped += 1
                continue
            html = fetch(client, url)
            if html is None or html.startswith("__ERROR__"):
                msg = f"{soc_code}\t{url}\t{(html or 'no response').removeprefix('__ERROR__')}"
                errors.append(msg)
                console.print(f"  [red]✗[/] {soc_code} {url}")
            else:
                dest.write_text(html, encoding="utf-8")
                fetched += 1
                console.print(f"  [green]✓[/] [{i}/{len(targets)}] {soc_code}")
                time.sleep(2 + random.uniform(-0.5, 0.5))

    if errors:
        ERR_LOG.write_text("\n".join(errors) + "\n", encoding="utf-8")
    console.print(
        f"\n[bold]Done.[/] fetched={fetched} cached={skipped} "
        f"errors={len(errors)}" + (f" → {ERR_LOG}" if errors else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
