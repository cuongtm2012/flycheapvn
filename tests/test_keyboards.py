"""Tests for Telegram keyboards."""

from keyboards import (
    INLINE_CALLBACKS,
    MENU_PROMPTS,
    resolve_menu_text,
    BTN_SEARCH,
    BTN_HELP,
)


def test_resolve_menu_search():
    assert resolve_menu_text(BTN_SEARCH) == MENU_PROMPTS[BTN_SEARCH]
    assert "tìm vé" in resolve_menu_text(BTN_SEARCH)


def test_resolve_menu_help():
    assert resolve_menu_text(BTN_HELP) == "/help"


def test_resolve_menu_unknown():
    assert resolve_menu_text("hello world") is None


def test_inline_callbacks_cover_samples():
    assert "s_hn_sg" in INLINE_CALLBACKS
    assert "alert_hn_sg" in INLINE_CALLBACKS
    assert INLINE_CALLBACKS["s_hn_sg"].startswith("tìm vé")
