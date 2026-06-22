"""Tests for Google Flights scraper helpers."""

import pytest

from sources.google_flights_scraper import GoogleFlightsScraper


def test_parse_price_vnd():
    scraper = GoogleFlightsScraper()
    assert scraper._parse_price("1.200.000 ₫") == 1200000
    assert scraper._parse_price("599,000 VND") == 599000


def test_parse_time_am_pm():
    scraper = GoogleFlightsScraper()
    assert scraper._parse_time("6:35 AM", "2026-07-15") == "2026-07-15T06:35:00"
    assert scraper._parse_time("6:35 PM", "2026-07-15") == "2026-07-15T18:35:00"
    assert scraper._parse_time("14:20", "2026-07-15") == "2026-07-15T14:20:00"


def test_resolve_airline():
    scraper = GoogleFlightsScraper()
    assert scraper._resolve_airline("VietJet Air") == "VJ"
    assert scraper._resolve_airline("Bamboo Airways") == "QH"
    assert scraper._resolve_airline("Unknown Air") == "??"


def test_parallel_and_quick_price_flags():
    scraper = GoogleFlightsScraper()
    assert scraper.parallel_eligible is False
    assert scraper.quick_price_eligible is False


@pytest.mark.asyncio
async def test_search_live():
    """Live scrape — skip if Playwright/Chromium missing or Google blocks headless."""
    import os

    scraper = GoogleFlightsScraper()
    if not scraper.is_configured():
        pytest.skip("Playwright not installed")
    if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.expanduser("~/.cache/ms-playwright"))

    from datetime import datetime, timedelta

    date = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")
    result = await scraper.search("HAN", "SGN", date, limit=3)
    if result.get("error") in ("google_blocked", "playwright_not_installed", "no_results"):
        pytest.skip(f"Google Flights live scrape unavailable: {result.get('error')}")
    assert result.get("success") is True
    assert len(result.get("flights", [])) > 0
    assert result["flights"][0]["price"] > 0
