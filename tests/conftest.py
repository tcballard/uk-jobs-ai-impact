"""Shared fixtures for uk-jobs-neet tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/ importable.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def sample_csv_row():
    return {
        "soc_code": "6145",
        "title": "Care workers and home carers",
        "soc_major_group": "6",
        "soc_major_label": "Caring, Leisure & Other Services",
        "employment_uk": "750000",
        "median_hourly_pay": "11.5",
        "median_annual_pay": "22000",
        "growth_pct_5yr": "3.2",
        "entry_level": "True",
        "no_qualification_required": "",
        "apprenticeship_available": "False",
        "public_sector": "True",
        "regulated_profession": "False",
        "ncs_url": "https://nationalcareers.service.gov.uk/job-profiles/care-worker",
    }
