"""Tests for ResponseBuilder."""

from __future__ import annotations

import pytest

from response_builder import ResponseBuilder, MEDALS


@pytest.fixture
def builder():
    return ResponseBuilder()


def test_general_chat_start(builder):
    result = builder._general_chat({"sub_intent": "start"})
    assert "FlyCheapVN" in result
    assert "/help" in result


def test_general_chat_help(builder):
    result = builder._general_chat({"sub_intent": "help"})
    assert "Hướng dẫn" in result
    assert "/check-alerts" in result


def test_general_chat_uptime(builder):
    result = builder._general_chat({"sub_intent": "uptime"})
    assert "🟢" in result
    assert "UTC" in result


def test_general_chat_default(builder):
    result = builder._general_chat({})
    assert "FlyCheapVN" in result


def test_set_alert_success(builder):
    result = builder._set_alert({
        "alert_id": 42,
        "origin": "HAN",
        "dest": "SGN",
        "max_price": 800_000,
    })
    assert "✅" in result
    assert "#42" in result
    assert "HAN → SGN" in result
    assert "800k" in result


def test_set_alert_error(builder):
    result = builder._set_alert({"error": "Thiếu tuyến bay"})
    assert "❌" in result


def test_check_alerts_empty(builder):
    result = builder._check_alerts({"alerts": [], "notifications": []})
    assert "Chưa có alert" in result


def test_check_alerts_with_data(builder):
    result = builder._check_alerts({
        "alerts": [{
            "id": 1, "origin": "HAN", "dest": "SGN",
            "max_price": 800_000, "last_price": 750_000,
        }],
        "notifications": [],
    })
    assert "#1" in result
    assert "HAN→SGN" in result
    assert "750k" in result


def test_check_alerts_with_notification(builder):
    result = builder._check_alerts({
        "alerts": [{
            "id": 1, "origin": "HAN", "dest": "SGN",
            "max_price": 800_000, "last_price": 600_000,
        }],
        "notifications": [{
            "origin": "HAN", "dest": "SGN",
            "price": 600_000, "max_price": 800_000,
        }],
    })
    assert "🔔" in result
    assert "600k" in result


def test_promo_check(builder):
    result = builder._promo_check({})
    assert "Khuyến mãi" in result
    assert "VietJet" in result
    assert "Bamboo" in result


def test_advice(builder):
    result = builder._advice({"destination": "Đà Nẵng"})
    assert "Đà Nẵng" in result
    assert "3-6 tuần" in result
    assert "/theodoi" in result


def test_lucky_date(builder):
    result = builder._lucky_date({"destination": "Phú Quốc"}, group=False)
    assert "Phú Quốc" in result
    assert "Hoàng Đạo" in result
    assert "khoa học" in result


def test_lucky_date_group(builder):
    result = builder._lucky_date({"destination": "Nha Trang"}, group=True)
    assert "nhóm" in result
    assert "Nha Trang" in result
    assert "khoa học" in result


def test_format_flights_template_empty():
    from response_builder import _format_flights_template
    result = _format_flights_template("HAN", "SGN", "2026-06-27", [], {})
    assert "HAN → SGN" in result
    assert "─────────────────────────" in result


def test_format_flights_template_with_data():
    from response_builder import _format_flights_template
    flights = [{
        "airline": "VJ", "airline_name": "VietJet Air",
        "flight_number": "VJ123",
        "price": 599_000, "currency": "VND",
        "price_usd": 25.82,
        "departure": "2026-06-27T06:00:00",
        "arrival": "2026-06-27T07:30:00",
        "origin": "HAN", "dest": "SGN",
        "stops": 0, "duration_minutes": 90,
        "booking_url": "https://example.com",
    }]
    result = _format_flights_template("HAN", "SGN", "2026-06-27", flights, {})
    assert "VietJet Air" in result
    assert "599k" in result
    assert "Bay thẳng" in result
    assert "06:00" in result
    assert '"Đặt ngay"' in result or "[Đặt ngay]" in result or "https://" in result
