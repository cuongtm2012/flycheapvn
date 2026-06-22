"""FlyCheapVN Telegram Bot — main entry point."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ai_router import AIRouter
from alert_manager import AlertManager
from api_router import APIRouter
from database import check_user_rate_limit, init_db, upsert_user
from response_builder import ResponseBuilder
from utils import parse_relative_date, resolve_airport

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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(update, context, forced_intent={"intent": "general_chat", "sub_intent": "start"})


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(update, context, forced_intent={"intent": "general_chat", "sub_intent": "help"})


async def uptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(update, context, forced_intent={"intent": "general_chat", "sub_intent": "uptime"})


async def theodoi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text if update.message else ""
    await _handle_message(update, context, forced_text=text)


async def check_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(
        update, context, forced_intent={"intent": "check_alerts"}
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_message(update, context)


async def _handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    forced_intent: dict | None = None,
    forced_text: str | None = None,
) -> None:
    if not update.effective_user or not update.effective_chat or not update.message:
        return

    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not check_user_rate_limit(telegram_id):
        await update.message.reply_text(
            "⏳ Anh/chị gửi hơi nhanh! Chờ 1 phút rồi thử lại nhé.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user_id = upsert_user(
        telegram_id=telegram_id,
        chat_id=chat_id,
        username=update.effective_user.username,
        first_name=update.effective_user.first_name,
    )

    text = forced_text or update.message.text or ""
    parsed = forced_intent or await ai_router.classify(text, user_id=telegram_id)
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
        elif intent in ("promo_check", "advice", "lucky_date", "group_lucky_date", "general_chat"):
            pass
        else:
            parsed["intent"] = "general_chat"

        if intent not in ("check_alerts", "set_alert"):
            extra_notifications = await alert_manager.incidental_check(user_id)

        reply = await response_builder.build(intent, response_data, parsed)

        if extra_notifications:
            notify_lines = ["\n\n🔔 *Deal mới từ alert:*"]
            for n in extra_notifications:
                from utils import format_price_vnd
                notify_lines.append(
                    f"• {n['origin']}→{n['dest']}: {format_price_vnd(n['price'])}"
                )
            reply += "\n".join(notify_lines)

        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    except Exception as exc:
        logger.exception("Handler error: %s", exc)
        await update.message.reply_text(
            "😅 Em gặp lỗi rồi. Thử lại sau hoặc gõ /help nhé!"
        )


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
    if not date_from:
        date_from = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

    parsed["origin"] = origin
    parsed["destination"] = dest
    parsed["date_from"] = date_from

    return await api_router.search(
        origin=origin,
        dest=dest,
        date_from=date_from,
        date_to=parsed.get("date_to"),
        max_price=parsed.get("max_price"),
    )


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

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("uptime", uptime_command))
    app.add_handler(CommandHandler("theodoi", theodoi_command))
    app.add_handler(CommandHandler("check_alerts", check_alerts_command))
    app.add_handler(MessageHandler(filters.Regex(r"^/check-alerts$"), check_alerts_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("FlyCheapVN bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
