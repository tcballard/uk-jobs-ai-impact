"""Tests for scripts/common.py — pure utility functions."""
from __future__ import annotations

import pytest

from common import (
    ENTRY_LEVEL_MAJOR_GROUPS,
    SOC_MAJOR_LABELS,
    any_hint,
    dice,
    is_unit_group,
    slugify,
    soc_major_label,
    title_tokens,
)


# ── slugify ───────────────────────────────────────────────────────────

class TestSlugify:
    def test_basic(self):
        assert slugify("Care Worker") == "care-worker"

    def test_strips_leading_trailing_hyphens(self):
        assert slugify("  Hello World  ") == "hello-world"

    def test_collapses_multiple_non_alnum(self):
        assert slugify("foo---bar   baz") == "foo-bar-baz"

    def test_special_characters(self):
        assert slugify("Nurse (Adult)") == "nurse-adult"

    def test_already_slug(self):
        assert slugify("care-worker") == "care-worker"

    def test_empty(self):
        assert slugify("") == ""

    def test_numbers_preserved(self):
        assert slugify("SOC 6145") == "soc-6145"


# ── title_tokens ──────────────────────────────────────────────────────

class TestTitleTokens:
    def test_basic(self):
        tokens = title_tokens("Sales and retail assistants")
        assert "sale" in tokens
        assert "retail" in tokens
        assert "assistant" in tokens
        # stopwords removed
        assert "and" not in tokens

    def test_stopwords_removed(self):
        tokens = title_tokens("Other occupations n.e.c.")
        assert "other" not in tokens
        assert "occupations" not in tokens
        assert "nec" not in tokens

    def test_singularisation(self):
        tokens = title_tokens("Electricians")
        assert "electrician" in tokens

    def test_short_words_dropped(self):
        tokens = title_tokens("a b cd ef")
        # single-char tokens filtered (after stopword check)
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" in tokens
        assert "ef" in tokens

    def test_empty(self):
        assert title_tokens("") == set()


# ── dice ──────────────────────────────────────────────────────────────

class TestDice:
    def test_identical(self):
        s = {"a", "b", "c"}
        assert dice(s, s) == 1.0

    def test_disjoint(self):
        assert dice({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # intersection=1, len(a)=2, len(b)=2 → 2*1/(2+2) = 0.5
        assert dice({"a", "b"}, {"b", "c"}) == 0.5

    def test_empty_a(self):
        assert dice(set(), {"a"}) == 0.0

    def test_empty_b(self):
        assert dice({"a"}, set()) == 0.0

    def test_both_empty(self):
        assert dice(set(), set()) == 0.0


# ── soc_major_label ───────────────────────────────────────────────────

class TestSocMajorLabel:
    def test_known_code(self):
        major, label = soc_major_label("6145")
        assert major == "6"
        assert label == "Caring, Leisure & Other Services"

    def test_all_labels_covered(self):
        for digit in "123456789":
            major, label = soc_major_label(f"{digit}000")
            assert major == digit
            assert label == SOC_MAJOR_LABELS[digit]

    def test_unknown_first_digit(self):
        major, label = soc_major_label("0999")
        assert major == "0"
        assert label == "Unknown"


# ── is_unit_group ─────────────────────────────────────────────────────

class TestIsUnitGroup:
    @pytest.mark.parametrize("code", ["1111", "6145", "9999", "0001"])
    def test_valid(self, code):
        assert is_unit_group(code)

    @pytest.mark.parametrize("code", ["111", "11111", "61A5", "", "abc", "12 34"])
    def test_invalid(self, code):
        assert not is_unit_group(code)


# ── any_hint ──────────────────────────────────────────────────────────

class TestAnyHint:
    def test_match(self):
        assert any_hint("Registered nurse", ("nurse", "doctor"))

    def test_no_match(self):
        assert not any_hint("Software developer", ("nurse", "doctor"))

    def test_case_insensitive(self):
        assert any_hint("POLICE Officer", ("police",))

    def test_substring_match(self):
        assert any_hint("registered nurse practitioner", ("nurse",))

    def test_no_partial_word_match(self):
        # "nurse" is not a substring of "nursing" — the function checks substring of full text
        assert any_hint("nursing assistant", ("nursing",))
        assert not any_hint("nursing assistant", ("nurse ",))

    def test_empty_hints(self):
        assert not any_hint("anything", ())

    def test_empty_text(self):
        assert not any_hint("", ("nurse",))


# ── ENTRY_LEVEL_MAJOR_GROUPS constant ─────────────────────────────────

class TestConstants:
    def test_entry_level_major_groups(self):
        assert ENTRY_LEVEL_MAJOR_GROUPS == {"6", "7", "8", "9"}

    def test_soc_major_labels_has_nine_entries(self):
        assert len(SOC_MAJOR_LABELS) == 9
        for k in "123456789":
            assert k in SOC_MAJOR_LABELS
