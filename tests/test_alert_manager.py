"""Tests for AlertManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alert_manager import AlertManager


@pytest.fixture
def mock_api_router():
    router = MagicMock()
    router.quick_price = AsyncMock(return_value=500_000)
    return router


def test_set_alert_success(mock_api_router):
    mgr = AlertManager(mock_api_router)
    with patch("alert_manager.create_alert", return_value=42):
        result = mgr.set_alert(
            user_id=1,
            origin="HAN",
            dest="SGN",
            max_price=800_000,
        )
    assert result["alert_id"] == 42
    assert result["origin"] == "HAN"
    assert result["dest"] == "SGN"
    assert result["max_price"] == 800_000


def test_set_alert_missing_origin(mock_api_router):
    mgr = AlertManager(mock_api_router)
    result = mgr.set_alert(user_id=1, origin="", dest="SGN", max_price=800_000)
    assert "error" in result
    assert "Thiếu" in result["error"]


def test_set_alert_zero_price(mock_api_router):
    mgr = AlertManager(mock_api_router)
    result = mgr.set_alert(user_id=1, origin="HAN", dest="SGN", max_price=0)
    assert "error" in result
    assert "Thiếu" in result["error"]


@pytest.mark.asyncio
async def test_incidental_check_no_alerts(mock_api_router):
    mgr = AlertManager(mock_api_router)
    with patch("alert_manager.get_active_alerts", return_value=[]):
        notifications = await mgr.incidental_check(user_id=1)
    assert notifications == []


@pytest.mark.asyncio
async def test_incidental_check_with_notification(mock_api_router):
    mock_alert = {
        "id": 1, "user_id": 1,
        "origin": "HAN", "dest": "SGN",
        "max_price": 800_000, "currency": "VND",
        "date_from": None, "date_to": None,
        "last_checked": None, "last_price": None,
        "last_notified_price": None, "active": 1,
    }
    mgr = AlertManager(mock_api_router)
    with (
        patch("alert_manager.get_active_alerts", return_value=[mock_alert]),
        patch("alert_manager.update_alert_check"),
    ):
        result = await mgr.check_alerts(user_id=1, force=True)

    assert len(result["alerts"]) == 1
    assert len(result["notifications"]) == 1
    assert result["notifications"][0]["price"] == 500_000
