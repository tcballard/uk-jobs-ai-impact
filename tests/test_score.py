"""Tests for scripts/score.py — request building and constants."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from score import OUTPUT_SCHEMA, SYSTEM_PROMPT, build_requests, load_titles


# ── OUTPUT_SCHEMA ─────────────────────────────────────────────────────

class TestOutputSchema:
    def test_required_fields_present(self):
        required = OUTPUT_SCHEMA["required"]
        assert "ai_score" in required
        assert "rationale" in required
        assert "key_factors" in required
        assert "entry_level" in required
        assert "automation_timeline" in required
        assert "safer_pivot" in required

    def test_ai_score_is_number(self):
        assert OUTPUT_SCHEMA["properties"]["ai_score"]["type"] == "number"

    def test_entry_level_is_boolean(self):
        assert OUTPUT_SCHEMA["properties"]["entry_level"]["type"] == "boolean"

    def test_automation_timeline_enum(self):
        enum = OUTPUT_SCHEMA["properties"]["automation_timeline"]["enum"]
        assert set(enum) == {"near-term", "medium-term", "long-term", "resistant"}

    def test_safer_pivot_nullable(self):
        sp = OUTPUT_SCHEMA["properties"]["safer_pivot"]["type"]
        assert "null" in sp
        assert "string" in sp

    def test_no_additional_properties(self):
        assert OUTPUT_SCHEMA["additionalProperties"] is False


# ── SYSTEM_PROMPT ─────────────────────────────────────────────────────

class TestSystemPrompt:
    def test_contains_scoring_instructions(self):
        assert "Score each occupation from 0 to 10" in SYSTEM_PROMPT

    def test_contains_uk_factors(self):
        assert "NHS" in SYSTEM_PROMPT
        assert "Regulated professions" in SYSTEM_PROMPT

    def test_contains_calibration_examples(self):
        assert "Roofer" in SYSTEM_PROMPT
        assert "Medical transcriptionist" in SYSTEM_PROMPT


# ── build_requests ────────────────────────────────────────────────────

class TestBuildRequests:
    def test_builds_from_pages(self, tmp_path):
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "6145.md").write_text("# Care workers\nContent here.")
        (pages_dir / "7111.md").write_text("# Sales assistants\nMore content.")

        with patch("score.PAGES", pages_dir):
            reqs = build_requests(limit=None)

        assert len(reqs) == 2
        ids = {r["custom_id"] for r in reqs}
        assert ids == {"6145", "7111"}

    def test_limit_parameter(self, tmp_path):
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        for i in range(5):
            (pages_dir / f"900{i}.md").write_text(f"# Occupation {i}")

        with patch("score.PAGES", pages_dir):
            reqs = build_requests(limit=2)

        assert len(reqs) == 2

    def test_empty_pages_dir(self, tmp_path):
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()

        with patch("score.PAGES", pages_dir):
            reqs = build_requests(limit=None)

        assert reqs == []

    def test_request_structure(self, tmp_path):
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "6145.md").write_text("# Care workers\nTest content.")

        with patch("score.PAGES", pages_dir):
            reqs = build_requests(limit=None)

        req = reqs[0]
        assert req["custom_id"] == "6145"
        params = req["params"]
        assert params["model"] == "claude-sonnet-4-6"
        assert params["max_tokens"] == 600
        assert len(params["system"]) == 1
        assert params["system"][0]["cache_control"] == {"type": "ephemeral"}


# ── load_titles ───────────────────────────────────────────────────────

class TestLoadTitles:
    def test_loads_from_csv(self, tmp_path):
        import csv as csv_mod
        csv_path = tmp_path / "occupations.csv"
        with csv_path.open("w", newline="") as f:
            w = csv_mod.DictWriter(f, fieldnames=["soc_code", "title"])
            w.writeheader()
            w.writerow({"soc_code": "6145", "title": "Care workers"})
            w.writerow({"soc_code": "7111", "title": "Sales assistants"})

        with patch("score.OCCUPATIONS_CSV", csv_path):
            titles = load_titles()

        assert titles == {"6145": "Care workers", "7111": "Sales assistants"}
