"""Tests for scripts/validate.py — coverage/sanity report."""
from __future__ import annotations

import csv
import json
from unittest.mock import patch

import pytest

from validate import main


class TestValidateMain:
    @pytest.fixture()
    def data_files(self, tmp_path):
        """Create minimal occupations.csv + data/site/data.json for validation."""
        csv_path = tmp_path / "occupations.csv"
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
            for code, mg in [("6145", "6"), ("7111", "7"), ("9111", "9"), ("1111", "1")]:
                w.writerow({
                    "soc_code": code, "title": f"Test {code}",
                    "soc_major_group": mg, "soc_major_label": "",
                    "employment_uk": "1000", "median_hourly_pay": "10",
                    "median_annual_pay": "20000", "growth_pct_5yr": "1.0",
                    "entry_level": mg in ("6", "7", "9"), "no_qualification_required": "",
                    "apprenticeship_available": "", "public_sector": "",
                    "regulated_profession": "", "ncs_url": "",
                })

        site_dir = tmp_path / "data" / "site"
        site_dir.mkdir(parents=True)
        site_json = site_dir / "data.json"
        data = [
            {
                "soc_code": "6145",
                "title": "Care workers",
                "ai_score": 3.0,
                "risk_category": "Lower risk",
                "entry_level": True,
                "entry_level_risk": False,
                "rationale": "Physical caring role with strong human-contact buffer.",
                "median_annual_pay": 22000,
            },
            {
                "soc_code": "7111",
                "title": "Sales assistants",
                "ai_score": 7.5,
                "risk_category": "High risk",
                "entry_level": True,
                "entry_level_risk": True,
                "rationale": "High automation exposure from self-checkout and online retail displacement.",
                "median_annual_pay": None,
            },
        ]
        site_json.write_text(json.dumps(data))
        return csv_path, site_json

    def test_returns_zero(self, data_files):
        csv_path, site_json = data_files
        with patch("validate.OCCUPATIONS_CSV", csv_path), \
             patch("validate.SITE_DATA_JSON", site_json):
            rc = main()
        assert rc == 0

    def test_returns_one_if_no_data_json(self, tmp_path):
        missing = tmp_path / "data" / "site" / "data.json"
        with patch("validate.SITE_DATA_JSON", missing):
            rc = main()
        assert rc == 1
