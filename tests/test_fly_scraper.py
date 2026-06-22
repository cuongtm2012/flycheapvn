"""Tests for Fly Scraper source."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from sources.fly_scraper import FlyScraperSource, _milli_to_vnd


def test_milli_to_vnd():
    assert _milli_to_vnd(142080, "USD") == int(142.08 * 23_200)


@pytest.mark.asyncio
async def test_parse_search_response():
    source = FlyScraperSource()
    sample = {
        "itineraries": [{
            "pricingOptions": [{
                "price": {"amount": "142080"},
                "items": [{"deepLink": "https://example.com/book"}],
            }],
            "legs": [{
                "stopCount": 0,
                "durationInMinutes": 130,
                "departureDateTime": {"year": 2026, "month": 6, "day": 27, "hour": 15, "minute": 0, "second": 0},
                "arrivalDateTime": {"year": 2026, "month": 6, "day": 27, "hour": 17, "minute": 10, "second": 0},
                "carriers": {"marketing": [{"displayCode": "VN", "name": "Vietnam Airlines"}]},
                "segments": [{"marketingFlightNumber": "215"}],
            }],
        }]
    }
    flights = source._parse_itineraries(sample, "HAN", "SGN", "VND", None, 5)
    assert len(flights) == 1
    assert flights[0]["airline"] == "VN"
    assert flights[0]["origin"] == "HAN"


@pytest.mark.asyncio
async def test_price_calendar_live():
    if not os.getenv("RAPIDAPI_KEY"):
        pytest.skip("RAPIDAPI_KEY not set")
    source = FlyScraperSource()
    calendar = await source.price_calendar("HAN", "SGN")
    assert len(calendar) > 0
    assert calendar[0]["price_vnd"] > 0
