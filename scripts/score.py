"""
score.py — Score occupations for AI/automation exposure via the Anthropic Batch API.

One batch request per occupation (custom_id = soc_code). The shared system prompt is
sent with a cache_control breakpoint; responses are constrained to a strict JSON schema
via output_config so no fence-stripping is needed. Model: claude-sonnet-4-6.

Usage:
    uv run python scripts/score.py            # score everything in data/pages/
    uv run python scripts/score.py --limit 5  # tiny smoke test
"""
from __future__ import annotations

import csv
import json
import sys
import time

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv
from rich.console import Console

from common import OCCUPATIONS_CSV, PAGES, SCORES_JSON

load_dotenv(dotenv_path=PAGES.parent.parent / ".env", override=True)
console = Console()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 600
ERR_LOG = PAGES.parent / "score_errors.log"

SYSTEM_PROMPT = """You are analysing UK occupations for AI and automation exposure, with a specific \
focus on entry-level roles accessible to young people (under 25) with no or \
minimal qualifications.

Score each occupation from 0 to 10 on AI Exposure:
- How much will AI and automation reshape or displace this role by 2030?
- Consider: direct automation (AI doing the work) AND indirect displacement \
  (AI making workers so productive that fewer are needed)
- Digital, screen-based output = inherently higher exposure
- Physical presence, manual dexterity, unpredictable environments = natural barrier

UK-specific factors to weight:
- NHS and public sector roles: institutional procurement inertia slows deployment \
  even where technically feasible; weight down by ~1 point
- Regulated professions (solicitors, accountants, surveyors): compliance frameworks \
  create deployment lag
- Trades with chronic UK skills shortages (electricians, plumbers, heating engineers): \
  market pressure and physical complexity delay displacement
- Retail, admin, basic logistics: accelerating automation, weight up

Also assess:
- entry_level: true/false — is this role typically accessible with no prior \
  qualifications or less than 1 year experience?
- automation_timeline: "near-term" (0-5 years), "medium-term" (5-10 years), \
  "long-term" (10+ years), or "resistant"
- safer_pivot: if this is a high-exposure entry-level role, suggest 1-2 adjacent \
  roles with lower exposure that require similar or achievable skills

Calibration examples:
  0-1: Roofer, refuse collector, groundskeeper (physical, variable)
  2-3: Care worker, plumber, electrician (physical + human judgment)
  4-5: Registered nurse, primary school teacher (mixed)
  6-7: Accountant, HR manager, marketing executive (largely digital)
  8-9: Paralegal, data analyst, software developer (fully digital)
  10: Medical transcriptionist, copy editor, data entry clerk

Return JSON only. safer_pivot must be null if the role is not entry-level or scores below 6."""

# Strict JSON schema — guarantees parseable output (no markdown fences to strip).
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ai_score": {"type": "number"},
        "rationale": {"type": "string"},
        "key_factors": {"type": "array", "items": {"type": "string"}},
        "entry_level": {"type": "boolean"},
        "automation_timeline": {
            "type": "string",
            "enum": ["near-term", "medium-term", "long-term", "resistant"],
        },
        "safer_pivot": {"type": ["string", "null"]},
    },
    "required": [
        "ai_score", "rationale", "key_factors",
        "entry_level", "automation_timeline", "safer_pivot",
    ],
    "additionalProperties": False,
}


def load_titles() -> dict[str, str]:
    with OCCUPATIONS_CSV.open() as f:
        return {r["soc_code"]: r["title"] for r in csv.DictReader(f)}


def build_requests(limit: int | None) -> list[Request]:
    pages = sorted(PAGES.glob("*.md"))
    if limit:
        pages = pages[:limit]
    requests = []
    for path in pages:
        content = path.read_text(encoding="utf-8")
        requests.append(
            Request(
                custom_id=path.stem,  # soc_code
                params=MessageCreateParamsNonStreaming(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=[{
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{"role": "user", "content": content}],
                    output_config={
                        "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}
                    },
                ),
            )
        )
    return requests


def main() -> int:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    titles = load_titles()
    requests = build_requests(limit)
    if not requests:
        console.print("[red]No markdown pages found in data/pages/. Run parse_pages.py first.[/]")
        return 1

    client = anthropic.Anthropic()
    console.print(f"[cyan]Submitting batch of {len(requests)} occupations ({MODEL}) …[/]")
    batch = client.messages.batches.create(requests=requests)
    console.print(f"  batch id: {batch.id}")

    # Poll until the batch ends.
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        c = batch.request_counts
        console.print(
            f"  status={batch.processing_status} "
            f"processing={c.processing} succeeded={c.succeeded} errored={c.errored}"
        )
        time.sleep(60)

    # Collect results.
    scores, errors = [], []
    for result in client.messages.batches.results(batch.id):
        soc = result.custom_id
        if result.result.type != "succeeded":
            errors.append(f"{soc}\t{result.result.type}")
            continue
        msg = result.result.message
        text = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            data = json.loads(text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        except json.JSONDecodeError as exc:
            errors.append(f"{soc}\tjson_error: {exc} :: {text[:120]}")
            continue
        data["soc_code"] = soc
        data["title"] = titles.get(soc, "")
        scores.append(data)

    scores.sort(key=lambda d: d["soc_code"])
    SCORES_JSON.write_text(json.dumps(scores, indent=2), encoding="utf-8")
    if errors:
        ERR_LOG.write_text("\n".join(errors) + "\n", encoding="utf-8")

    console.print(
        f"\n[bold green]Wrote {len(scores)} scores[/] → {SCORES_JSON}\n"
        f"  errors: {len(errors)}" + (f" → {ERR_LOG}" if errors else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
