"""Tests for date range and promo helpers."""

from utils import (
    ensure_date_range,
    filter_calendar_by_range,
    flights_in_range,
    format_month_label,
    is_month_or_range_query,
    is_promo_related,
    month_end,
)


def test_month_end():
    assert month_end("2026-07-01") == "2026-07-31"


def test_ensure_date_range_month():
    start, end = ensure_date_range("2026-07-01", None)
    assert start == "2026-07-01"
    assert end == "2026-07-31"


def test_is_promo_related():
    assert is_promo_related("vé rẻ khuyến mại từ HN đi DN")
    assert not is_promo_related("tìm vé HN-SG")


def test_is_month_query():
    parsed = {"raw_message": "trong tháng 7", "date_to": "2026-07-31"}
    assert is_month_or_range_query(parsed)


def test_filter_calendar_by_range():
    cal = [
        {"day": "2026-06-28", "price_vnd": 100},
        {"day": "2026-07-02", "price_vnd": 90},
    ]
    out = filter_calendar_by_range(cal, "2026-07-01", "2026-07-31")
    assert len(out) == 1
    assert out[0]["day"] == "2026-07-02"


def test_flights_in_range():
    flights = [
        {"departure": "2026-06-22T06:00:00", "price": 1},
        {"departure": "2026-07-05T08:00:00", "price": 2},
    ]
    out = flights_in_range(flights, "2026-07-01", "2026-07-31")
    assert len(out) == 1
    assert "07-05" in out[0]["departure"]


def test_format_month_label():
    assert "7/2026" in format_month_label("2026-07-01", "2026-07-31")
