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
    if not OCCUPATIONS_CSV.exists():
        console.print(f"[red]{OCCUPATIONS_CSV} not found. Run fetch_soc.py first.[/]")
        raise SystemExit(1)
    with OCCUPATIONS_CSV.open() as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if not r.get("ncs_url"):
            continue
        if not all_rows and r.get("soc_major_group") not in ENTRY_LEVEL_MAJOR_GROUPS:
            continue
        out.append((r["soc_code"], r["ncs_url"]))
    return out


def fetch(client: httpx.Client, url: str) -> tuple[str | None, str | None]:
    """Return (html, error_message). Exactly one is non-None."""
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            r = client.get(url, timeout=30, follow_redirects=True)
            r.raise_for_status()
            return r.text, None
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt == 1:
                console.print(f"  [yellow]retry[/] {url} ({exc})")
                time.sleep(10)
    return None, str(last_exc)


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
            html, err = fetch(client, url)
            if err is not None:
                errors.append(f"{soc_code}\t{url}\t{err}")
                console.print(f"  [red]✗[/] {soc_code} {url} — {err}")
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
