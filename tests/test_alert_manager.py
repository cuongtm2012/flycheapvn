"""Tests for alert manager."""

import tempfile

import pytest

from alert_manager import AlertManager
from database import get_active_alerts, init_db, upsert_user


@pytest.fixture
def alert_setup(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    import database
    original = database.DB_PATH
    database.DB_PATH = db_path
    user_id = upsert_user(telegram_id=123, chat_id=456, db_path=db_path)
    yield user_id, db_path
    database.DB_PATH = original


def test_set_alert(alert_setup):
    user_id, _ = alert_setup
    manager = AlertManager()
    result = manager.set_alert(user_id, "HAN", "SGN", 800_000)
    assert "alert_id" in result
    assert result["origin"] == "HAN"
    alerts = get_active_alerts(user_id)
    assert len(alerts) == 1


def test_set_alert_missing_route(alert_setup):
    user_id, _ = alert_setup
    manager = AlertManager()
    result = manager.set_alert(user_id, "", "SGN", 800_000)
    assert "error" in result
