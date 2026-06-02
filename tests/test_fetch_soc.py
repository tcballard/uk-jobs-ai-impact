"""Tests for scripts/fetch_soc.py — NCS URL matching and ASHE parsing."""
from __future__ import annotations

import pytest

from common import title_tokens
from fetch_soc import match_ncs_url, NCS_MATCH_THRESHOLD


# ── match_ncs_url ─────────────────────────────────────────────────────

class TestMatchNcsUrl:
    @pytest.fixture()
    def slug_tokens(self):
        """Small slug corpus resembling real NCS job-profile slugs."""
        slugs = [
            "care-worker",
            "sales-assistant",
            "electrician",
            "plumber",
            "nurse",
            "software-developer",
            "teaching-assistant",
            "warehouse-worker",
            "bus-driver",
            "chef",
        ]
        return {s: title_tokens(s.replace("-", " ")) for s in slugs}

    def test_exact_match(self, slug_tokens):
        url = match_ncs_url("Care worker", slug_tokens)
        assert url is not None
        assert url.endswith("/care-worker")

    def test_close_match(self, slug_tokens):
        url = match_ncs_url("Sales assistants", slug_tokens)
        assert url is not None
        assert "sales-assistant" in url

    def test_no_match_below_threshold(self, slug_tokens):
        url = match_ncs_url("Quantum physicist", slug_tokens)
        assert url is None

    def test_empty_title_returns_none(self, slug_tokens):
        assert match_ncs_url("", slug_tokens) is None

    def test_threshold_constant(self):
        assert NCS_MATCH_THRESHOLD == 0.5

    def test_returns_full_ncs_url(self, slug_tokens):
        url = match_ncs_url("Electrician", slug_tokens)
        assert url is not None
        assert url.startswith("https://nationalcareers.service.gov.uk/job-profiles/")
