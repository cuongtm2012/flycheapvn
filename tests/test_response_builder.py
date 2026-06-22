"""Tests for response builder templates."""

import pytest

from response_builder import ResponseBuilder, _format_flights_template


def test_format_flights_template():
    flights = [{
        "airline": "VJ",
        "airline_name": "VietJet Air",
        "price": 599000,
        "departure": "2026-06-27T06:00:00",
        "arrival": "2026-06-27T07:30:00",
        "stops": 0,
        "duration_minutes": 90,
        "booking_url": "https://example.com",
    }]
    text = _format_flights_template("HAN", "SGN", "2026-06-27", flights, {"source": "kiwi"})
    assert "HAN → SGN" in text
    assert "VietJet" in text
    assert "599k" in text or "599" in text


@pytest.mark.asyncio
async def test_general_chat_start():
    builder = ResponseBuilder()
    text = await builder.build("general_chat", {}, {"sub_intent": "start"})
    assert "FlyCheapVN" in text
