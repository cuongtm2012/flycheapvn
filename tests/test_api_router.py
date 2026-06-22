"""Tests for API router cache logic."""

import json
import tempfile
from pathlib import Path

import pytest

from database import get_cache, init_db, set_cache
from utils import make_cache_key


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def test_cache_roundtrip(temp_db):
    params = {"origin": "HAN", "dest": "SGN", "date_from": "2026-06-27"}
    key = make_cache_key(params)
    payload = {"success": True, "source": "kiwi", "flights": [{"price": 599000}]}
    set_cache(key, payload, "kiwi", db_path=temp_db)
    cached = get_cache(key, db_path=temp_db)
    assert cached is not None
    assert cached["flights"][0]["price"] == 599000
    assert cached["cached"] is True
