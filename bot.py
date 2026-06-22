"""FlyCheapVN Telegram Bot — main entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Optional

from dotenv import load_dotenv
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from ai_router import AIRouter
from alert_manager import AlertManager
from api_router import APIRouter
from database import check_user_rate_limit, init_db, upsert_user
from keyboards import (
    BOT_COMMANDS,
    INLINE_CALLBACKS,
    help_inline_keyboard,
    main_menu_keyboard,
    resolve_menu_text,
    start_inline_keyboard,
)
from response_builder import ResponseBuilder
from utils import (
    ensure_date_range,
    filter_calendar_by_range,
    filter_domestic_flights,
    flights_in_range,
    format_month_label,
    is_domestic_route,
    is_month_or_range_query,
    is_promo_related,
    parse_relative_date,
    resolve_airport,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

START_TIME = datetime.utcnow()

ai_router = AIRouter()
api_router = APIRouter()
alert_manager = AlertManager(api_router)
response_builder = ResponseBuilder()


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands menu registered")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name if update.effective_user else "bạn"
    splash = (
        f"✈️ *Chào {name}!* Em là *FlyCheapVN* — bot săn vé máy bay giá rẻ.\n\n"
        "👇 *Chọn gợi ý bên dưới* hoặc hỏi tự nhiên bằng tiếng Việt.\n"
        "Menu cố định ở dưới ô chat giúp anh/chị thao tác nhanh hơn.\n\n"
        "_VD: tìm vé HN-SG cuối tuần này dưới 1tr_"
    )
    if update.effective_user and update.message:
        upsert_user(
            telegram_id=update.effective_user.id,
            chat_id=update.effective_chat.id if update.effective_chat else update.message.chat_id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
        )

        try:
            await update.message.reply_text(
                splash,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=start_inline_keyboard(),
            )
        except BadRequest:
            await update.message.reply_text(splash, reply_markup=start_inline_keyboard())

        await update.message.reply_text(
            "⌨️ Dùng menu bên dưới hoặc gõ câu hỏi nhé!",
            reply_markup=main_menu_keyboard(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(
        update, context,
        forced_intent={"intent": "general_chat", "sub_intent": "help"},
        extra_markup=help_inline_keyboard(),
    )


async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(update, context, forced_intent={"intent": "general_chat", "sub_intent": "uptime"})


async def theodoi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message else ""
    await _handle_message(update, context, forced_text=text)


async def check_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(update, context, forced_intent={"intent": "check_alerts"})


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message else ""
    menu_prompt = resolve_menu_text(text)
    if menu_prompt:
        await _handle_message(update, context, forced_text=menu_prompt)
        return
    await _handle_message(update, context)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    text = INLINE_CALLBACKS.get(query.data or "")
    if not text:
        return

    if query.message:
        await _handle_message(update, context, forced_text=text, reply_to=query.message)


async def _handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    forced_intent: dict | None = None,
    forced_text: str | None = None,
    extra_markup: Any = None,
    reply_to: Optional[Message] = None,
) -> None:
    message = reply_to or update.message
    if not update.effective_user or not message:
        return

    telegram_id = update.effective_user.id
    chat_id = message.chat_id

    if not check_user_rate_limit(telegram_id):
        await _safe_reply(
            message,
            "⏳ Anh/chị gửi hơi nhanh! Chờ 1 phút rồi thử lại nhé.",
            reply_markup=main_menu_keyboard(),
        )
        return

    user_id = upsert_user(
        telegram_id=telegram_id,
        chat_id=chat_id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
    )

    text = forced_text or (update.message.text if update.message else "") or ""
    parsed = forced_intent or await ai_router.classify(text, user_id=telegram_id)
    if not forced_intent:
        parsed["raw_message"] = text
    if is_promo_related(text) and parsed.get("intent") == "search_flight":
        parsed["include_promo"] = True
    intent = parsed.get("intent", "general_chat")

    logger.info("User %s intent=%s parsed=%s", telegram_id, intent, parsed)

    response_data: dict = {}
    extra_notifications: list = []

    try:
        if intent == "search_flight":
            response_data = await _do_search(parsed)
        elif intent == "set_alert":
            response_data = await _do_set_alert(user_id, parsed)
        elif intent == "check_alerts":
            response_data = await alert_manager.check_alerts(user_id, force=True)
        elif intent in ("compare", "schedule", "price_predict"):
            response_data = await _do_search(parsed)
            if intent == "price_predict" and not response_data.get("flights"):
                parsed["_fallback_intent"] = "price_predict"
        elif intent in ("promo_check", "advice", "lucky_date", "group_lucky_date", "general_chat"):
            pass
        else:
            parsed["intent"] = "general_chat"

        if intent not in ("check_alerts", "set_alert"):
            extra_notifications = await alert_manager.incidental_check(user_id)

        reply = await response_builder.build(intent, response_data, parsed)

        if parsed.get("_fallback_intent") == "price_predict" and not response_data.get("flights"):
            reply = await response_builder.build("price_predict", response_data, parsed)

        if parsed.get("include_promo") and intent == "search_flight":
            reply += "\n\n" + response_builder.promo_snippet(parsed)

        if extra_notifications:
            notify_lines = ["\n\n🔔 *Deal mới từ alert:*"]
            for n in extra_notifications:
                from utils import format_price_vnd
                notify_lines.append(
                    f"• {n['origin']}→{n['dest']}: {format_price_vnd(n['price'])}"
                )
            reply += "\n".join(notify_lines)

        markup = extra_markup or main_menu_keyboard()
        await _safe_reply(message, reply, reply_markup=markup)

    except Exception as exc:
        logger.exception("Handler error: %s", exc)
        await _safe_reply(
            message,
            "😅 Em gặp lỗi rồi. Thử lại sau hoặc gõ /help nhé!",
            reply_markup=main_menu_keyboard(),
        )


async def _safe_reply(
    message: Message,
    text: str,
    reply_markup: Any = None,
) -> None:
    try:
        await message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    except BadRequest:
        await message.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)


async def _do_search(parsed: dict) -> dict:
    origin = parsed.get("origin")
    dest = parsed.get("destination")
    if origin:
        origin = resolve_airport(origin) or origin.upper()
    if dest:
        dest = resolve_airport(dest) or dest.upper()

    if not origin or not dest:
        return {
            "success": False,
            "flights": [],
            "message": "Em cần biết điểm đi và điểm đến. VD: tìm vé HN-SG ngày mai",
        }

    date_from = parsed.get("date_from") or parse_relative_date("tuần sau")
    date_to = parsed.get("date_to")
    if not date_from:
        date_from = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
    date_from, date_to = ensure_date_range(date_from, date_to)

    month_query = is_month_or_range_query(parsed)

    parsed["origin"] = origin
    parsed["destination"] = dest
    parsed["date_from"] = date_from
    parsed["date_to"] = date_to
    if month_query:
        parsed["month_label"] = format_month_label(date_from, date_to)

    search_task = api_router.search(
        origin=origin,
        dest=dest,
        date_from=date_from,
        date_to=date_to,
        max_price=parsed.get("max_price"),
    )
    calendar_task = api_router.get_price_calendar(origin, dest, limit=30)

    search_result, calendar_result = await asyncio.gather(
        search_task, calendar_task, return_exceptions=True,
    )

    if isinstance(search_result, Exception):
        logger.exception("Search failed: %s", search_result)
        search_result = {"success": False, "flights": [], "message": "Lỗi tìm kiếm"}

    if isinstance(calendar_result, Exception):
        logger.exception("Calendar failed: %s", calendar_result)
        calendar_result = []

    flights = search_result.get("flights", [])
    if flights and is_domestic_route(origin, dest):
        filtered = filter_domestic_flights(flights)
        if filtered:
            flights = filtered
            search_result["flights"] = filtered

    calendar_all = calendar_result if isinstance(calendar_result, list) else []
    calendar_in_range = filter_calendar_by_range(calendar_all, date_from, date_to) if month_query else calendar_all

    search_result["price_calendar"] = calendar_in_range[:10] if calendar_in_range else calendar_all[:10]

    if month_query:
        matching = flights_in_range(flights, date_from, date_to)
        if matching:
            search_result["flights"] = matching
        elif flights:
            search_result["flights"] = []
            search_result["date_mismatch"] = True
            search_result["sample_flights"] = flights[:2]

        if calendar_in_range:
            search_result["use_calendar_only"] = True
        elif calendar_all:
            search_result["use_calendar_only"] = True
            search_result["calendar_note"] = (
                f"⚠️ Chưa có lịch giá cho {parsed.get('month_label', 'khoảng thời gian bạn hỏi')}. "
                "Dưới đây là các ngày rẻ nhất hiện có từ API (tham khảo):"
            )
            search_result["price_calendar"] = calendar_all[:10]
        elif not matching:
            search_result["message"] = (
                f"Chưa có dữ liệu giá cho {parsed.get('month_label', 'thời gian này')}. "
                "Thử lại sau hoặc hỏi ngày cụ thể hơn."
            )

    elif search_result.get("date_mismatch"):
        search_result["calendar_note"] = (
            f"⚠️ API trả về chuyến không đúng ngày {date_from}. "
            "Kết quả dưới đây mang tính tham khảo."
        )

    return search_result


async def _do_set_alert(user_id: int, parsed: dict) -> dict:
    origin = parsed.get("origin")
    dest = parsed.get("destination")
    if origin:
        origin = resolve_airport(origin) or origin.upper()
    if dest:
        dest = resolve_airport(dest) or dest.upper()

    return alert_manager.set_alert(
        user_id=user_id,
        origin=origin or "",
        dest=dest or "",
        max_price=parsed.get("max_price") or 0,
        date_from=parsed.get("date_from"),
        date_to=parsed.get("date_to"),
    )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    init_db()
    logger.info("Database initialized")

    app = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("uptime", uptime_command))
    app.add_handler(CommandHandler("theodoi", theodoi_command))
    app.add_handler(CommandHandler("check_alerts", check_alerts_command))
    app.add_handler(MessageHandler(filters.Regex(r"^/check-alerts$"), check_alerts_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("FlyCheapVN bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
