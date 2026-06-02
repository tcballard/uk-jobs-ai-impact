"""Tests for scripts/merge.py — risk categorisation and type coercion."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from merge import _bool, _num, risk_category


# ── risk_category ─────────────────────────────────────────────────────

class TestRiskCategory:
    @pytest.mark.parametrize("score,expected", [
        (0, "Lower risk"),
        (1.5, "Lower risk"),
        (3, "Lower risk"),
        (3.1, "Moderate risk"),
        (5, "Moderate risk"),
        (6, "Moderate risk"),
        (6.1, "High risk"),
        (7, "High risk"),
        (8, "High risk"),
        (8.1, "Very high risk"),
        (9, "Very high risk"),
        (10, "Very high risk"),
    ])
    def test_boundaries(self, score, expected):
        assert risk_category(score) == expected


# ── _num ──────────────────────────────────────────────────────────────

class TestNum:
    def test_int(self):
        assert _num("42", int) == 42

    def test_float(self):
        assert _num("3.14", float) == pytest.approx(3.14)

    def test_empty_string(self):
        assert _num("", int) is None

    def test_none(self):
        assert _num(None, int) is None

    def test_invalid(self):
        assert _num("abc", int) is None

    def test_float_string_to_int_returns_none(self):
        # int("3.9") raises ValueError, so _num returns None
        assert _num("3.9", int) is None


# ── _bool ─────────────────────────────────────────────────────────────

class TestBool:
    @pytest.mark.parametrize("val", ["True", "true", "TRUE", "1", "yes", "YES"])
    def test_truthy(self, val):
        assert _bool(val) is True

    @pytest.mark.parametrize("val", ["False", "false", "0", "no", "", "random"])
    def test_falsy(self, val):
        assert _bool(val) is False

    def test_none(self):
        assert _bool(None) is False

    def test_whitespace(self):
        assert _bool("  true  ") is True


# ── main merge integration ────────────────────────────────────────────

class TestMergeMain:
    def test_merge_produces_correct_output(self, tmp_path):
        """End-to-end: CSV + scores.json → data.json with derived fields."""
        csv_path = tmp_path / "occupations.csv"
        scores_path = tmp_path / "scores.json"
        site_dir = tmp_path / "data" / "site"
        site_dir.mkdir(parents=True)
        site_json = site_dir / "data.json"
        serve_copy = tmp_path / "site" / "data.json"
        serve_copy.parent.mkdir(parents=True)

        # Write sample CSV
        fieldnames = [
            "soc_code", "title", "soc_major_group", "soc_major_label",
            "employment_uk", "median_hourly_pay", "median_annual_pay",
            "growth_pct_5yr", "entry_level", "no_qualification_required",
            "apprenticeship_available", "public_sector", "regulated_profession",
            "ncs_url",
        ]
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerow({
                "soc_code": "9111",
                "title": "Farm workers",
                "soc_major_group": "9",
                "soc_major_label": "Elementary Occupations",
                "employment_uk": "50000",
                "median_hourly_pay": "10.5",
                "median_annual_pay": "20000",
                "growth_pct_5yr": "-2.1",
                "entry_level": "True",
                "no_qualification_required": "True",
                "apprenticeship_available": "False",
                "public_sector": "False",
                "regulated_profession": "False",
                "ncs_url": "",
            })

        # Write sample scores
        scores_path.write_text(json.dumps([{
            "soc_code": "9111",
            "title": "Farm workers",
            "ai_score": 2.5,
            "rationale": "Physical outdoor work with variable conditions provides strong buffer.",
            "key_factors": ["outdoor", "manual", "variable"],
            "entry_level": True,
            "automation_timeline": "long-term",
            "safer_pivot": None,
        }]))

        # Patch paths and run
        with patch("merge.OCCUPATIONS_CSV", csv_path), \
             patch("merge.SCORES_JSON", scores_path), \
             patch("merge.SITE_DATA_JSON", site_json), \
             patch("merge.ROOT", tmp_path):
            from merge import main
            rc = main()

        assert rc == 0
        assert site_json.exists()
        data = json.loads(site_json.read_text())
        assert len(data) == 1
        rec = data[0]
        assert rec["soc_code"] == "9111"
        assert rec["ai_score"] == 2.5
        assert rec["risk_category"] == "Lower risk"
        assert rec["entry_level"] is True
        assert rec["entry_level_risk"] is False  # score < 7
        assert rec["employment_uk"] == 50000
        assert rec["median_annual_pay"] == 20000
        assert rec["growth_pct_5yr"] == pytest.approx(-2.1)

    def test_entry_level_risk_true_when_high_score(self, tmp_path):
        """entry_level_risk should be True when entry_level=True and ai_score >= 7."""
        csv_path = tmp_path / "occupations.csv"
        scores_path = tmp_path / "scores.json"
        site_dir = tmp_path / "data" / "site"
        site_dir.mkdir(parents=True)
        site_json = site_dir / "data.json"
        serve_copy = tmp_path / "site" / "data.json"
        serve_copy.parent.mkdir(parents=True)

        fieldnames = [
            "soc_code", "title", "soc_major_group", "soc_major_label",
            "employment_uk", "median_hourly_pay", "median_annual_pay",
            "growth_pct_5yr", "entry_level", "no_qualification_required",
            "apprenticeship_available", "public_sector", "regulated_profession",
            "ncs_url",
        ]
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerow({
                "soc_code": "7111",
                "title": "Sales and retail assistants",
                "soc_major_group": "7",
                "soc_major_label": "Sales & Customer Service",
                "employment_uk": "1000000",
                "median_hourly_pay": "9.5",
                "median_annual_pay": "18000",
                "growth_pct_5yr": "-1.5",
                "entry_level": "True",
                "no_qualification_required": "True",
                "apprenticeship_available": "False",
                "public_sector": "False",
                "regulated_profession": "False",
                "ncs_url": "",
            })

        scores_path.write_text(json.dumps([{
            "soc_code": "7111",
            "ai_score": 7.8,
            "rationale": "High exposure due to self-checkout and online retail.",
            "key_factors": ["automation", "online"],
            "entry_level": True,
            "automation_timeline": "near-term",
            "safer_pivot": "Visual merchandiser",
        }]))

        with patch("merge.OCCUPATIONS_CSV", csv_path), \
             patch("merge.SCORES_JSON", scores_path), \
             patch("merge.SITE_DATA_JSON", site_json), \
             patch("merge.ROOT", tmp_path):
            from merge import main
            main()

        data = json.loads(site_json.read_text())
        rec = data[0]
        assert rec["entry_level_risk"] is True
        assert rec["risk_category"] == "High risk"
