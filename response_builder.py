"""Format bot responses with LLM or templates."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

from openai import AsyncOpenAI

from utils import format_date_vn, format_datetime_vn, format_duration, format_price_vnd

logger = logging.getLogger(__name__)

MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


class ResponseBuilder:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url) if api_key else None

    async def build(
        self,
        intent: str,
        data: dict[str, Any],
        parsed: Optional[dict[str, Any]] = None,
    ) -> str:
        if intent == "general_chat":
            return self._general_chat(parsed or {})
        if intent == "search_flight":
            return await self._search_flight(data, parsed or {})
        if intent == "set_alert":
            return self._set_alert(data)
        if intent == "check_alerts":
            return self._check_alerts(data)
        if intent == "promo_check":
            return self._promo_check(parsed or {})
        if intent == "compare":
            return self._compare(data, parsed or {})
        if intent == "schedule":
            return await self._search_flight(data, parsed or {}, title="Lịch bay")
        if intent == "advice":
            return self._advice(parsed or {})
        if intent == "price_predict":
            return self._price_predict(data, parsed or {})
        if intent in ("lucky_date", "group_lucky_date"):
            return self._lucky_date(parsed or {}, group=intent == "group_lucky_date")

        return "Em chưa hiểu câu hỏi. Gõ /help để xem hướng dẫn nhé!"

    def _general_chat(self, parsed: dict[str, Any]) -> str:
        sub = parsed.get("sub_intent")
        if sub == "start":
            return (
                "✈️ *FlyCheapVN* — Săn vé máy bay giá rẻ!\n\n"
                "Em có thể giúp anh/chị:\n"
                "• Tìm vé: _tìm vé HN-SG cuối tuần này dưới 1tr_\n"
                "• Theo dõi giá: _/theodoi HAN-SGN duoi 800k_\n"
                "• Khuyến mãi, so sánh hãng, tư vấn...\n\n"
                "Gõ /help để xem thêm!"
            )
        if sub == "help":
            return (
                "📖 *Hướng dẫn FlyCheapVN*\n\n"
                "*Tìm vé:* tìm vé HN-SG ngày mai\n"
                "*Theo dõi:* /theodoi HAN-DAD duoi 800k\n"
                "*Kiểm tra alert:* /check-alerts\n"
                "*Khuyến mãi:* hãng nào đang giảm giá?\n"
                "*So sánh:* VietJet hay Bamboo rẻ hơn HN-DN?\n"
                "*Tư vấn:* nên đặt vé trước bao lâu?\n"
                "*Ngày tốt:* xem ngày đẹp đi Đà Nẵng tháng 7\n\n"
                "Hỏi tự nhiên bằng tiếng Việt nhé!"
            )
        if sub == "uptime":
            return f"🟢 Bot đang hoạt động — {datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
        return (
            "Chào anh/chị! 👋 Em là bot săn vé FlyCheapVN.\n"
            "Hỏi em tìm vé, theo dõi giá, hoặc gõ /help nhé!"
        )

    async def _search_flight(
        self,
        data: dict[str, Any],
        parsed: dict[str, Any],
        title: str = "Kết quả tìm vé",
    ) -> str:
        flights = data.get("flights", [])
        origin = parsed.get("origin") or (flights[0]["origin"] if flights else "???")
        dest = parsed.get("destination") or (flights[0]["dest"] if flights else "???")
        date_from = parsed.get("date_from") or ""

        if not flights:
            msg = data.get("message", "Không tìm thấy chuyến bay phù hợp.")
            return f"😔 {msg}\n\n💡 Thử đổi ngày hoặc tăng budget nhé!"

        template = _format_flights_template(origin, dest, date_from, flights, data)
        if self.client:
            try:
                llm_text = await self._llm_format(template, "search_flight")
                if llm_text:
                    return llm_text
            except Exception as exc:
                logger.warning("LLM format failed: %s", exc)

        return template

    def _set_alert(self, data: dict[str, Any]) -> str:
        if data.get("error"):
            return f"❌ {data['error']}"
        return (
            f"✅ Đã tạo alert #{data['alert_id']}!\n"
            f"📍 {data['origin']} → {data['dest']}\n"
            f"💰 Báo khi giá ≤ {format_price_vnd(data['max_price'])}\n\n"
            "Em sẽ kiểm tra nhân tiện khi anh/chị chat. Gõ /check-alerts để xem ngay."
        )

    def _check_alerts(self, data: dict[str, Any]) -> str:
        alerts = data.get("alerts", [])
        notifications = data.get("notifications", [])
        if not alerts:
            return "📭 Chưa có alert nào. Dùng /theodoi HAN-SGN duoi 800k để tạo nhé!"

        lines = ["📋 *Alert đang theo dõi:*\n"]
        for a in alerts:
            price_str = format_price_vnd(a["last_price"]) if a.get("last_price") else "chưa check"
            lines.append(
                f"#{a['id']} {a['origin']}→{a['dest']} ≤{format_price_vnd(a['max_price'])} "
                f"(giá gần nhất: {price_str})"
            )

        if notifications:
            lines.append("\n🔔 *Có deal mới:*")
            for n in notifications:
                lines.append(
                    f"• {n['origin']}→{n['dest']}: {format_price_vnd(n['price'])} "
                    f"(mục tiêu ≤{format_price_vnd(n['max_price'])})"
                )
        return "\n".join(lines)

    def _promo_check(self, parsed: dict[str, Any]) -> str:
        return (
            "🔥 *Khuyến mãi đang hot:*\n\n"
            "• VietJet: Flash sale 0đ + phí (theo lịch hãng)\n"
            "• Bamboo: Giảm 15% tuyến nội địa (mùa thấp điểm)\n"
            "• Vietnam Airlines: Combo khứ hồi tiết kiệm\n\n"
            "💡 Mẹo: Theo dõi fanpage hãng + đặt alert: /theodoi HAN-SGN duoi 800k"
        )

    def _compare(self, data: dict[str, Any], parsed: dict[str, Any]) -> str:
        flights = data.get("flights", [])
        if not flights:
            return "Chưa có dữ liệu so sánh. Thử hỏi: _tìm vé HN-SG ngày mai_ trước nhé!"
        by_airline: dict[str, dict] = {}
        for f in flights:
            code = f["airline"]
            if code not in by_airline or f["price"] < by_airline[code]["price"]:
                by_airline[code] = f
        sorted_airlines = sorted(by_airline.values(), key=lambda x: x["price"])
        lines = [f"📊 *So sánh hãng {parsed.get('origin', '')}→{parsed.get('destination', '')}:*\n"]
        for i, f in enumerate(sorted_airlines[:5]):
            stops_text = "Bay thẳng" if f["stops"] == 0 else f"{f['stops']} stop"
            lines.append(
                f"{MEDALS[i] if i < len(MEDALS) else '•'} {f['airline_name']}: "
                f"{format_price_vnd(f['price'])} | {stops_text}"
            )
        cheapest = sorted_airlines[0]
        lines.append(f"\n💡 Rẻ nhất: *{cheapest['airline_name']}* — {format_price_vnd(cheapest['price'])}")
        return "\n".join(lines)

    def _advice(self, parsed: dict[str, Any]) -> str:
        dest = parsed.get("destination", "điểm đến")
        return (
            f"💡 *Mẹo săn vé rẻ đi {dest}:*\n\n"
            "• Đặt trước 3-6 tuần (nội địa), 2-3 tháng (quốc tế)\n"
            "• Thứ 3-4 thường rẻ hơn cuối tuần\n"
            "• Bay sáng sớm/tối muộn thường rẻ hơn\n"
            "• So sánh hãng: VietJet rẻ, VN Airlines ổn định, Bamboo cân bằng\n"
            "• Dùng /theodoi để em báo khi giá xuống!"
        )

    def _price_predict(self, data: dict[str, Any], parsed: dict[str, Any]) -> str:
        flights = data.get("flights", [])
        current = parsed.get("max_price") or (flights[0]["price"] if flights else None)
        origin = parsed.get("origin", "")
        dest = parsed.get("destination", "")

        if current and flights:
            market = flights[0]["price"]
            diff = current - market
            if diff > 200_000:
                return (
                    f"📉 Giá thị trường {origin}→{dest}: ~{format_price_vnd(market)}\n"
                    f"Giá anh/chị nói ({format_price_vnd(current)}) cao hơn ~{format_price_vnd(diff)}.\n\n"
                    "⏳ *Nên chờ thêm* — giá có thể giảm trong 1-2 tuần tới."
                )
            if diff < -100_000:
                return (
                    f"📈 Giá {format_price_vnd(current)} thấp hơn thị trường ({format_price_vnd(market)})!\n\n"
                    "✅ *Nên mua ngay* — đây là deal tốt!"
                )
        return (
            f"📊 *Dự đoán giá {origin}→{dest}:*\n\n"
            "• 2-3 tuần trước ngày bay: giá thường ổn định\n"
            "• 1 tuần trước: có thể tăng 10-20%\n"
            "• Nếu giá < 800k HN-SG: cân nhắc mua ngay\n\n"
            "Dùng /theodoi để em báo khi giá đẹp!"
        )

    def _lucky_date(self, parsed: dict[str, Any], group: bool = False) -> str:
        dest = parsed.get("destination", "điểm đến")
        disclaimer = (
            "\n\n⚠️ _Tham khảo phong thủy truyền thống, không có cơ sở khoa học._"
        )
        if group:
            return (
                f"🌟 *Ngày tốt cho nhóm đi {dest}:*\n\n"
                "• Ngày 3, 8, 13, 18, 23, 28 âm lịch thường an toàn\n"
                "• Tránh ngày xung tuổi của từng thành viên\n"
                "• Giờ Hoàng Đạo: 7-9h, 11-13h, 15-17h\n"
                + disclaimer
            )
        return (
            f"🌟 *Ngày đẹp xuất hành đi {dest}:*\n\n"
            "• Ngày chẵn âm lịch: 2, 6, 8, 12, 16, 18, 22, 26, 28\n"
            "• Giờ Hoàng Đạo sáng: 7h-9h, 11h-13h\n"
            "• Nên tránh ngày 3, 7, 13, 18, 22, 27 âm lịch\n"
            + disclaimer
        )

    async def _llm_format(self, template: str, intent: str) -> Optional[str]:
        prompt = (
            f"Format kết quả {intent} thành text Telegram đẹp, tiếng Việt, dùng emoji vừa phải. "
            "Giữ nguyên giá, giờ bay, link đặt vé. Không bịa thêm dữ liệu.\n\n"
            f"Dữ liệu:\n{template}"
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Bạn format kết quả bot Telegram. Chỉ dùng dữ liệu có sẵn."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return response.choices[0].message.content


def _format_flights_template(
    origin: str,
    dest: str,
    date_from: str,
    flights: list[dict[str, Any]],
    data: dict[str, Any],
) -> str:
    date_str = format_date_vn(flights[0]["departure"]) if flights else date_from
    lines = [
        f"✈️ {origin} → {dest} | {date_str}",
        "─────────────────────────",
    ]
    if data.get("cached"):
        lines.append(f"📦 Cache ({data.get('source', '?')})")

    for i, f in enumerate(flights[:5]):
        medal = MEDALS[i] if i < len(MEDALS) else "•"
        stops = "Bay thẳng" if f["stops"] == 0 else f"{f['stops']} điểm dừng"
        dep = format_datetime_vn(f["departure"])
        arr = format_datetime_vn(f["arrival"])
        dur = format_duration(f.get("duration_minutes", 0))
        lines.append(f"{medal} {f['airline_name']} {format_price_vnd(f['price'])}")
        lines.append(f"   🕐 {dep}→{arr} | {stops} {dur}")
        if f.get("booking_url"):
            lines.append(f"   🔗 Đặt ngay: {f['booking_url']}")

    lines.append("\n💡 Mẹo: Đặt trước 3 tuần để có giá tốt nhất!")
    return "\n".join(lines)
