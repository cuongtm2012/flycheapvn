"""Tests for regex fallback parser."""

import pytest

from utils import format_price_vnd, parse_price_vnd, regex_parse_intent, resolve_airport


def test_resolve_airport():
    assert resolve_airport("hà nội") == "HAN"
    assert resolve_airport("sg") == "SGN"
    assert resolve_airport("HAN") == "HAN"


def test_parse_price_vnd():
    assert parse_price_vnd("1tr") == 1_000_000
    assert parse_price_vnd("800k") == 800_000
    assert parse_price_vnd("1.2 triệu") == 1_200_000


def test_format_price_vnd():
    assert format_price_vnd(1_000_000) == "1tr"
    assert format_price_vnd(800_000) == "800k"


def test_regex_search_flight():
    result = regex_parse_intent("tìm vé HN-SG cuối tuần này dưới 1tr")
    assert result["intent"] == "search_flight"
    assert result["origin"] == "HAN"
    assert result["destination"] == "SGN"
    assert result["max_price"] == 1_000_000


def test_regex_set_alert():
    result = regex_parse_intent("/theodoi HAN-SGN duoi 800k")
    assert result["intent"] == "set_alert"
    assert result["origin"] == "HAN"
    assert result["destination"] == "SGN"
    assert result["max_price"] == 800_000


def test_regex_general_chat():
    result = regex_parse_intent("/start")
    assert result["intent"] == "general_chat"
    assert result["sub_intent"] == "start"
