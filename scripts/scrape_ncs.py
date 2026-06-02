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

import random
import sys
import time

import httpx

from common import (
    HTTP_HEADERS,
    RAW,
    console,
    filter_slice,
    load_occupations,
    wants_all,
    write_log,
)

ERR_LOG = RAW.parent / "scrape_errors.log"


def load_targets(all_rows: bool) -> list[tuple[str, str]]:
    rows = filter_slice(load_occupations(), include_all=all_rows)
    return [(r["soc_code"], r["ncs_url"]) for r in rows if r["ncs_url"]]


def fetch_with_retry(client: httpx.Client, url: str) -> str | None:
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
    include_all = wants_all()
    targets = load_targets(include_all)
    console.print(
        f"[cyan]Scraping {len(targets)} NCS pages "
        f"({'all groups' if include_all else 'SOC 6-9 slice'})[/]"
    )
    errors: list[str] = []
    fetched = skipped = 0

    with httpx.Client(headers=HTTP_HEADERS) as client:
        for i, (soc_code, url) in enumerate(targets, 1):
            dest = RAW / f"{soc_code}.html"
            if dest.exists():
                skipped += 1
                continue
            html = fetch_with_retry(client, url)
            if html is None or html.startswith("__ERROR__"):
                msg = f"{soc_code}\t{url}\t{(html or 'no response').removeprefix('__ERROR__')}"
                errors.append(msg)
                console.print(f"  [red]✗[/] {soc_code} {url}")
            else:
                dest.write_text(html, encoding="utf-8")
                fetched += 1
                console.print(f"  [green]✓[/] [{i}/{len(targets)}] {soc_code}")
                time.sleep(2 + random.uniform(-0.5, 0.5))

    write_log(ERR_LOG, errors)
    console.print(
        f"\n[bold]Done.[/] fetched={fetched} cached={skipped} "
        f"errors={len(errors)}" + (f" → {ERR_LOG}" if errors else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
