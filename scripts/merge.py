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

import json
import sys

from common import (
    ROOT,
    SCORES_JSON,
    SITE_DATA_JSON,
    console,
    load_occupations_map,
    parse_bool,
    parse_num,
)

# Numeric CSV fields → typed JSON (blank → None).
INT_FIELDS = ("employment_uk", "median_annual_pay")
FLOAT_FIELDS = ("median_hourly_pay", "growth_pct_5yr")
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



def main() -> int:
    occ = load_occupations_map()
    scores = {s["soc_code"]: s for s in json.loads(SCORES_JSON.read_text())}

    data = []
    for soc, score in scores.items():
        row = occ.get(soc, {})
        ai = float(score["ai_score"])
        # entry_level: trust the CSV flag, OR the model's judgement
        entry_level = parse_bool(row.get("entry_level")) or bool(score.get("entry_level"))
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
            "entry_level_risk": entry_level and ai >= 7,
            "no_qualification_required": parse_bool(row.get("no_qualification_required")),
            "apprenticeship_available": parse_bool(row.get("apprenticeship_available")),
            "public_sector": parse_bool(row.get("public_sector")),
            "regulated_profession": parse_bool(row.get("regulated_profession")),
            "ncs_url": row.get("ncs_url", ""),
        }
        for fld in INT_FIELDS:
            rec[fld] = parse_num(row.get(fld), int)
        for fld in FLOAT_FIELDS:
            rec[fld] = parse_num(row.get(fld), float)
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
