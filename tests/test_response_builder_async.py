"""Tests for ResponseBuilder async methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from response_builder import ResponseBuilder


@pytest.fixture
def builder_no_llm():
    """ResponseBuilder without LLM (falls back to templates)."""
    rb = ResponseBuilder()
    rb.client = None
    return rb


@pytest.mark.asyncio
async def test_build_search_flight_no_results(builder_no_llm):
    result = await builder_no_llm.build(
        "search_flight",
        {"success": False, "flights": [], "message": "Không tìm thấy"},
        {"origin": "HAN", "destination": "SGN"},
    )
    assert "Không tìm thấy" in result


@pytest.mark.asyncio
async def test_build_search_flight_with_results(builder_no_llm):
    flights = [{
        "airline": "VJ", "airline_name": "VietJet Air",
        "flight_number": "VJ123", "price": 599_000,
        "currency": "VND", "price_usd": 25.82,
        "departure": "2026-06-27T06:00:00",
        "arrival": "2026-06-27T07:30:00",
        "origin": "HAN", "dest": "SGN",
        "stops": 0, "duration_minutes": 90,
        "booking_url": "",
    }]
    result = await builder_no_llm.build(
        "search_flight",
        {"success": True, "flights": flights, "source": "kiwi"},
        {"origin": "HAN", "destination": "SGN", "date_from": "2026-06-27"},
    )
    assert "VietJet Air" in result
    assert "599k" in result


@pytest.mark.asyncio
async def test_build_compare_with_data(builder_no_llm):
    flights = [
        {"airline": "VJ", "airline_name": "VietJet Air", "price": 599_000,
         "stops": 0, "currency": "VND", "price_usd": 25.82},
        {"airline": "VN", "airline_name": "Vietnam Airlines", "price": 899_000,
         "stops": 0, "currency": "VND", "price_usd": 38.75},
    ]
    result = await builder_no_llm.build(
        "compare",
        {"success": True, "flights": flights, "source": "kiwi"},
        {"origin": "HAN", "destination": "SGN"},
    )
    assert "So sánh" in result
    assert "VietJet Air" in result
    assert "599k" in result


@pytest.mark.asyncio
async def test_build_unknown_intent(builder_no_llm):
    result = await builder_no_llm.build("nonexistent_intent", {}, {})
    assert "chưa hiểu" in result
