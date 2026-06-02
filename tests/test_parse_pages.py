"""Tests for scripts/parse_pages.py — HTML parsing and Markdown generation."""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from parse_pages import _clean, _lmi_line, _salary_text, _section_text, parse_html, stub_markdown

# ── HTML fixtures (inline to avoid conftest import issues) ────────────

SAMPLE_NCS_HTML = """\
<html>
<body>
<h1>Care worker</h1>
<h2 id="heading-what-youll-do">What you'll do</h2>
<div>
  <p>As a care worker, you could:</p>
  <ul>
    <li>help with washing, dressing and feeding</li>
    <li>support people with daily activities</li>
    <li>monitor health and wellbeing</li>
  </ul>
</div>
<h2 id="heading-what-it-takes">What it takes</h2>
<div>
  <p>You'll need patience, empathy and communication skills.</p>
</div>
<h2 id="heading-how-to-become">How to become</h2>
<div>
  <p>There are no set requirements. Some employers need no qualifications.</p>
  <p>An apprenticeship is also available.</p>
</div>
<h2 id="heading-career-path-and-progression">Career path and progression</h2>
<div>
  <p>You could progress to senior care worker or care manager.</p>
</div>
<h2>Average salary (Median)</h2>
<div>
  <p>Starter: \u00a318,000 Experienced: \u00a324,000</p>
</div>
</body>
</html>
"""

SAMPLE_NCS_HTML_THIN = """\
<html>
<body>
<h1>Mystery role</h1>
<h2 id="heading-career-path-and-progression">Career path</h2>
<div><p>Short.</p></div>
</body>
</html>
"""


# ── _clean ────────────────────────────────────────────────────────────

class TestClean:
    def test_collapses_spaces(self):
        assert _clean("hello   world") == "hello world"

    def test_collapses_newlines(self):
        assert _clean("a\n\n\n\nb") == "a\n\nb"

    def test_strips_whitespace(self):
        assert _clean("  hello  ") == "hello"

    def test_tabs_to_spaces(self):
        assert _clean("hello\t\tworld") == "hello world"

    def test_empty(self):
        assert _clean("") == ""


# ── _section_text ─────────────────────────────────────────────────────

class TestSectionText:
    def test_extracts_what_youll_do(self):
        soup = BeautifulSoup(SAMPLE_NCS_HTML, "lxml")
        text = _section_text(soup, "what-youll-do")
        assert "washing" in text
        assert "daily activities" in text

    def test_extracts_how_to_become(self):
        soup = BeautifulSoup(SAMPLE_NCS_HTML, "lxml")
        text = _section_text(soup, "how-to-become")
        assert "no set requirements" in text

    def test_missing_section_returns_empty(self):
        soup = BeautifulSoup(SAMPLE_NCS_HTML, "lxml")
        text = _section_text(soup, "nonexistent-section")
        assert text == ""

    def test_stops_at_next_h2(self):
        soup = BeautifulSoup(SAMPLE_NCS_HTML, "lxml")
        text = _section_text(soup, "what-youll-do")
        # Should not include content from "Skills required" section
        assert "patience" not in text


# ── _salary_text ──────────────────────────────────────────────────────

class TestSalaryText:
    def test_extracts_salary(self):
        soup = BeautifulSoup(SAMPLE_NCS_HTML, "lxml")
        text = _salary_text(soup)
        assert "\u00a3" in text  # £ sign

    def test_no_salary_section(self):
        html = "<html><body><h2>Something else</h2><p>No pay info</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert _salary_text(soup) == ""

    def test_truncated_to_200_chars(self):
        long_salary_html = (
            '<html><body>'
            '<h2>Average salary (Median)</h2>'
            f'<div><p>\u00a3{"1" * 300}</p></div>'
            '</body></html>'
        )
        soup = BeautifulSoup(long_salary_html, "lxml")
        text = _salary_text(soup)
        assert len(text) <= 200


# ── _lmi_line ─────────────────────────────────────────────────────────

class TestLmiLine:
    def test_full_data(self):
        row = {
            "employment_uk": "750000",
            "median_annual_pay": "22000",
            "growth_pct_5yr": "3.2",
        }
        line = _lmi_line(row)
        assert "750,000" in line
        assert "\u00a322,000" in line
        assert "3.2%" in line

    def test_missing_data(self):
        row = {
            "employment_uk": "",
            "median_annual_pay": "",
            "growth_pct_5yr": "",
        }
        line = _lmi_line(row)
        assert "n/a" in line


# ── parse_html ────────────────────────────────────────────────────────

class TestParseHtml:
    def test_produces_markdown(self, sample_csv_row):
        md, thin = parse_html(sample_csv_row, SAMPLE_NCS_HTML)
        assert md.startswith("# Care workers and home carers")
        assert "## What you'll do" in md
        assert "## How to become" in md
        assert "## Pay" in md
        assert not thin  # should have core sections

    def test_detects_no_qual_phrases(self, sample_csv_row):
        md, thin = parse_html(sample_csv_row, SAMPLE_NCS_HTML)
        assert sample_csv_row["_no_qual"] is True

    def test_thin_page_flagged(self, sample_csv_row):
        md, thin = parse_html(sample_csv_row, SAMPLE_NCS_HTML_THIN)
        assert thin

    def test_includes_lmi_section(self, sample_csv_row):
        md, thin = parse_html(sample_csv_row, SAMPLE_NCS_HTML)
        assert "## UK labour market" in md
        assert "750,000" in md


# ── stub_markdown ─────────────────────────────────────────────────────

class TestStubMarkdown:
    def test_produces_stub(self, sample_csv_row):
        md = stub_markdown(sample_csv_row)
        assert md.startswith("# Care workers and home carers")
        assert "SOC 6145" in md
        assert "## About this occupation" in md
        assert "No detailed National Careers Service profile" in md

    def test_includes_lmi_data(self, sample_csv_row):
        md = stub_markdown(sample_csv_row)
        assert "750,000" in md
        assert "\u00a322,000" in md
