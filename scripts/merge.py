"""
merge.py — Join occupations.csv + scores.json into the frontend payload.

Adds derived fields:
  - risk_category:     0-3 Lower / 4-6 Moderate / 7-8 High / 9-10 Very high risk
  - entry_level_risk:  entry_level AND ai_score >= 7

Writes data/site/data.json (one record per scored occupation).

Usage:
    uv run python scripts/merge.py
"""
from __future__ import annotations

import csv
import json
import sys

from rich.console import Console

from common import OCCUPATIONS_CSV, ROOT, SCORES_JSON, SITE_DATA_JSON

console = Console()

# Numeric CSV fields → typed JSON (blank → None).
INT_FIELDS = ("employment_uk", "median_annual_pay")
FLOAT_FIELDS = ("median_hourly_pay", "growth_pct")
BOOL_FIELDS = (
    "entry_level", "no_qualification_required", "apprenticeship_available",
    "public_sector", "regulated_profession",
)


def risk_category(score: float) -> str:
    if score <= 3:
        return "Lower risk"
    if score <= 6:
        return "Moderate risk"
    if score <= 8:
        return "High risk"
    return "Very high risk"


def _num(val, cast):
    if val in ("", None):
        return None
    try:
        return cast(val)
    except (TypeError, ValueError):
        return None


def _bool(val) -> bool:
    return str(val).strip().lower() in ("true", "1", "yes")


def main() -> int:
    with OCCUPATIONS_CSV.open() as f:
        occ = {r["soc_code"]: r for r in csv.DictReader(f)}
    scores = {s["soc_code"]: s for s in json.loads(SCORES_JSON.read_text())}

    data = []
    for soc, score in scores.items():
        row = occ.get(soc, {})
        ai = float(score["ai_score"])
        # entry_level: trust the CSV flag (SOC 6-9 heuristic) AND the model's
        # judgement — the CSV flag provides the target-audience filter, the model
        # provides a reality check from role content.
        csv_entry = _bool(row.get("entry_level"))
        model_entry = bool(score.get("entry_level"))
        entry_level = csv_entry or model_entry
        rec = {
            "soc_code": soc,
            "title": row.get("title") or score.get("title", ""),
            "soc_major_group": row.get("soc_major_group", soc[:1]),
            "soc_major_label": row.get("soc_major_label", ""),
            "ai_score": round(ai, 1),
            "rationale": score.get("rationale", ""),
            "key_factors": score.get("key_factors", []),
            "automation_timeline": score.get("automation_timeline", ""),
            "safer_pivot": score.get("safer_pivot"),
            "risk_category": risk_category(ai),
            "entry_level": entry_level,
            "entry_level_csv": csv_entry,
            "entry_level_model": model_entry,
            "entry_level_risk": entry_level and ai >= 7,
            "no_qualification_required": _bool(row.get("no_qualification_required")),
            "apprenticeship_available": _bool(row.get("apprenticeship_available")),
            "public_sector": _bool(row.get("public_sector")),
            "regulated_profession": _bool(row.get("regulated_profession")),
            "ncs_url": row.get("ncs_url", ""),
        }
        for fld in INT_FIELDS:
            rec[fld] = _num(row.get(fld), int)
        for fld in FLOAT_FIELDS:
            rec[fld] = _num(row.get(fld), float)
        data.append(rec)

    data.sort(key=lambda d: d["soc_code"])
    payload = json.dumps(data, indent=2)
    SITE_DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    SITE_DATA_JSON.write_text(payload, encoding="utf-8")
    # Serving copy next to site/index.html (so `cd site && http.server` can fetch it).
    serve_copy = ROOT / "site" / "data.json"
    serve_copy.write_text(payload, encoding="utf-8")

    elr = sum(1 for d in data if d["entry_level_risk"])
    console.print(
        f"[bold green]Wrote {len(data)} records[/] → {SITE_DATA_JSON}\n"
        f"  serving copy:                 {serve_copy}\n"
        f"  entry-level-risk occupations: {elr}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
