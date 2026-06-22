"""Telegram keyboards: reply menu + inline suggestions."""

from __future__ import annotations

from typing import Optional

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

# --- Reply keyboard (menu cố định dưới ô chat) ---
BTN_SEARCH = "🔍 Tìm vé"
BTN_ALERT = "🔔 Theo dõi giá"
BTN_PROMO = "🔥 Khuyến mãi"
BTN_COMPARE = "📊 So sánh hãng"
BTN_ADVICE = "💡 Mẹo săn vé"
BTN_HELP = "❓ Hướng dẫn"
BTN_ALERTS = "📋 Alert của tôi"

MENU_BUTTON_TEXTS = {
    BTN_SEARCH,
    BTN_ALERT,
    BTN_PROMO,
    BTN_COMPARE,
    BTN_ADVICE,
    BTN_HELP,
    BTN_ALERTS,
}

MENU_PROMPTS: dict[str, str] = {
    BTN_SEARCH: "tìm vé HN-SG cuối tuần này dưới 1tr",
    BTN_ALERT: "/theodoi HAN-SGN duoi 800k",
    BTN_PROMO: "hãng nào đang giảm giá?",
    BTN_COMPARE: "VietJet hay Vietnam Airlines rẻ hơn HN-SG?",
    BTN_ADVICE: "mách em mẹo săn vé rẻ",
    BTN_HELP: "/help",
    BTN_ALERTS: "/check_alerts",
}

# --- Inline keyboard (gợi ý nhanh trên tin /start) ---
INLINE_CALLBACKS: dict[str, str] = {
    "s_hn_sg": "tìm vé HN-SG cuối tuần này dưới 1tr",
    "s_hn_dn": "tìm vé HN-Đà Nẵng ngày mai",
    "s_sg_pq": "tìm vé SG-Phú Quốc giá rẻ",
    "cmp_vj_vn": "VietJet hay Vietnam Airlines rẻ hơn HN-SG?",
    "promo": "hãng nào đang giảm giá?",
    "alert_hn_sg": "/theodoi HAN-SGN duoi 800k",
    "advice": "nên đặt vé trước bao lâu để rẻ nhất?",
    "lucky": "xem ngày đẹp đi Đà Nẵng tháng 7",
}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_SEARCH), KeyboardButton(BTN_ALERT)],
            [KeyboardButton(BTN_PROMO), KeyboardButton(BTN_COMPARE)],
            [KeyboardButton(BTN_ADVICE), KeyboardButton(BTN_ALERTS)],
            [KeyboardButton(BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Hỏi em tìm vé, khuyến mãi, ngày tốt...",
    )


def start_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✈️ HN → SG cuối tuần", callback_data="s_hn_sg"),
            InlineKeyboardButton("🏖 SG → Phú Quốc", callback_data="s_sg_pq"),
        ],
        [
            InlineKeyboardButton("🔍 HN → Đà Nẵng", callback_data="s_hn_dn"),
            InlineKeyboardButton("📊 So sánh hãng", callback_data="cmp_vj_vn"),
        ],
        [
            InlineKeyboardButton("🔥 Khuyến mãi", callback_data="promo"),
            InlineKeyboardButton("🔔 Theo dõi HN-SG", callback_data="alert_hn_sg"),
        ],
        [
            InlineKeyboardButton("💡 Mẹo săn vé", callback_data="advice"),
            InlineKeyboardButton("🌟 Ngày tốt", callback_data="lucky"),
        ],
    ])


def help_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✈️ Tìm vé mẫu", callback_data="s_hn_sg"),
            InlineKeyboardButton("🔔 Tạo alert", callback_data="alert_hn_sg"),
        ],
    ])


BOT_COMMANDS = [
    BotCommand("start", "Bắt đầu + menu gợi ý"),
    BotCommand("help", "Hướng dẫn sử dụng"),
    BotCommand("theodoi", "Theo dõi giá — VD: HAN-SGN duoi 800k"),
    BotCommand("check_alerts", "Xem alert đang theo dõi"),
]


def resolve_menu_text(text: str) -> Optional[str]:
    """Map nút menu → câu hỏi mẫu. None nếu không phải nút menu."""
    return MENU_PROMPTS.get(text.strip())
