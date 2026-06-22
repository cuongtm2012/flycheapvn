"""Tests for search response with calendar fallback."""

import pytest

from response_builder import ResponseBuilder


@pytest.fixture
def builder():
    b = ResponseBuilder()
    b.client = None
    return b


@pytest.mark.asyncio
async def test_month_query_shows_calendar_with_note(builder):
    parsed = {
        "origin": "HAN",
        "destination": "DAD",
        "date_from": "2026-07-01",
        "date_to": "2026-07-31",
        "month_label": "tháng 7/2026",
    }
    data = {
        "use_calendar_only": True,
        "calendar_note": "⚠️ Chưa có lịch giá cho tháng 7/2026.",
        "price_calendar": [
            {"day": "2026-06-28", "price_str": "1.1tr", "airline": "VietJet Air"},
            {"day": "2026-06-30", "price_str": "1.2tr", "airline": "VJ"},
        ],
        "flights": [],
    }
    reply = await builder.build("search_flight", data, parsed)
    assert "tháng 7/2026" in reply
    assert "2026-06-28" in reply
    assert "Chưa có lịch giá" in reply


@pytest.mark.asyncio
async def test_promo_snippet_includes_route(builder):
    snippet = builder.promo_snippet({"origin": "HAN", "destination": "DAD"})
    assert "HAN→DAD" in snippet
    assert "VietJet" in snippet
