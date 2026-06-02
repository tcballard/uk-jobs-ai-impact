"""Tests for scripts/scrape_ncs.py — target loading and fetch retry logic."""
from __future__ import annotations

import csv
from unittest.mock import MagicMock, patch

import httpx
import pytest

from scrape_ncs import fetch, load_targets


# ── load_targets ──────────────────────────────────────────────────────

class TestLoadTargets:
    @pytest.fixture()
    def csv_file(self, tmp_path):
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
            # SOC 6 with URL (entry-level slice)
            w.writerow({
                "soc_code": "6145", "title": "Care workers", "soc_major_group": "6",
                "soc_major_label": "Caring", "employment_uk": "750000",
                "median_hourly_pay": "", "median_annual_pay": "",
                "growth_pct_5yr": "", "entry_level": "True",
                "no_qualification_required": "", "apprenticeship_available": "",
                "public_sector": "", "regulated_profession": "",
                "ncs_url": "https://nationalcareers.service.gov.uk/job-profiles/care-worker",
            })
            # SOC 2 with URL (not in entry-level slice)
            w.writerow({
                "soc_code": "2111", "title": "Chemical scientists", "soc_major_group": "2",
                "soc_major_label": "Professional", "employment_uk": "50000",
                "median_hourly_pay": "", "median_annual_pay": "",
                "growth_pct_5yr": "", "entry_level": "False",
                "no_qualification_required": "", "apprenticeship_available": "",
                "public_sector": "", "regulated_profession": "",
                "ncs_url": "https://nationalcareers.service.gov.uk/job-profiles/chemical-scientist",
            })
            # SOC 9 without URL
            w.writerow({
                "soc_code": "9111", "title": "Farm workers", "soc_major_group": "9",
                "soc_major_label": "Elementary", "employment_uk": "30000",
                "median_hourly_pay": "", "median_annual_pay": "",
                "growth_pct_5yr": "", "entry_level": "True",
                "no_qualification_required": "", "apprenticeship_available": "",
                "public_sector": "", "regulated_profession": "",
                "ncs_url": "",
            })
        return csv_path

    def test_slice_only(self, csv_file):
        with patch("scrape_ncs.OCCUPATIONS_CSV", csv_file):
            targets = load_targets(all_rows=False)
        # Only SOC 6 row qualifies (SOC 6-9 with URL)
        assert len(targets) == 1
        assert targets[0] == (
            "6145",
            "https://nationalcareers.service.gov.uk/job-profiles/care-worker",
        )

    def test_all_rows(self, csv_file):
        with patch("scrape_ncs.OCCUPATIONS_CSV", csv_file):
            targets = load_targets(all_rows=True)
        # SOC 6 + SOC 2 have URLs (SOC 9 has no URL)
        assert len(targets) == 2
        codes = {t[0] for t in targets}
        assert codes == {"6145", "2111"}

    def test_empty_urls_excluded(self, csv_file):
        with patch("scrape_ncs.OCCUPATIONS_CSV", csv_file):
            targets = load_targets(all_rows=True)
        codes = {t[0] for t in targets}
        assert "9111" not in codes


# ── fetch (retry logic) ──────────────────────────────────────────────

class TestFetch:
    def test_success_first_try(self):
        mock_response = MagicMock()
        mock_response.text = "<html>page content</html>"
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.get.return_value = mock_response

        result = fetch(client, "https://example.com/page")
        assert result == "<html>page content</html>"
        assert client.get.call_count == 1

    def test_retry_on_first_failure(self):
        mock_response = MagicMock()
        mock_response.text = "<html>ok</html>"
        mock_response.raise_for_status = MagicMock()

        client = MagicMock()
        client.get.side_effect = [
            httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()),
            mock_response,
        ]

        with patch("scrape_ncs.time.sleep"):
            result = fetch(client, "https://example.com/page")
        assert result == "<html>ok</html>"
        assert client.get.call_count == 2

    def test_returns_error_after_two_failures(self):
        client = MagicMock()
        err = httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())
        client.get.side_effect = [err, err]

        with patch("scrape_ncs.time.sleep"):
            result = fetch(client, "https://example.com/page")
        assert result is not None
        assert result.startswith("__ERROR__")
