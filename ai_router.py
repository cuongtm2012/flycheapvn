"""AI classifier and entity parser using DeepSeek."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

from openai import AsyncOpenAI

from utils import regex_parse_intent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Bạn là trợ lý săn vé máy bay FlyCheapVN. Nhiệm vụ:
1. Phân loại ý định người dùng vào MỘT trong các intent:
   search_flight | promo_check | compare | advice | schedule | set_alert | check_alerts | lucky_date | group_lucky_date | price_predict | general_chat
2. Trích xuất thông tin cần thiết
3. Trả về JSON thuần, không markdown

Quy tắc mã sân bay:
- Hà Nội = HAN, Sài Gòn/HCM = SGN, Đà Nẵng = DAD
- Đà Lạt = DLI, Nha Trang = CXR, Phú Quốc = PQC
- Hải Phòng = HPH, Huế = HUI, Vinh = VII
- Quy Nhơn = UIH, Cần Thơ = VCA, Rạch Giá = VKG
- Buôn Ma Thuột = BMV, Pleiku = PXU, Tuy Hòa = TBB
- Bangkok = BKK, Seoul = ICN, Singapore = SIN

Schema JSON:
{
  "intent": "search_flight",
  "origin": "HAN",
  "destination": "SGN",
  "date_from": "2026-06-27",
  "date_to": null,
  "max_price": 1000000,
  "airline": null,
  "trip_type": "one_way",
  "birth_year": null,
  "group_birth_years": null,
  "confidence": 0.95
}

Ngày: dùng ISO YYYY-MM-DD. Nếu không rõ ngày, date_from = null.
Giá: VND integer (1tr = 1000000, 800k = 800000).
Chỉ trả JSON, không giải thích."""

VALID_INTENTS = {
    "search_flight", "promo_check", "compare", "advice", "schedule",
    "set_alert", "check_alerts", "lucky_date", "group_lucky_date",
    "price_predict", "general_chat",
}


class AIRouter:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url) if api_key else None
        self._sessions: dict[int, list[dict[str, str]]] = {}

    def is_configured(self) -> bool:
        return self.client is not None

    def get_session(self, user_id: int) -> list[dict[str, str]]:
        return self._sessions.setdefault(user_id, [])

    def add_to_session(self, user_id: int, role: str, content: str, max_turns: int = 10) -> None:
        session = self.get_session(user_id)
        session.append({"role": role, "content": content})
        if len(session) > max_turns * 2:
            self._sessions[user_id] = session[-(max_turns * 2):]

    def clear_session(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)

    async def classify(self, message: str, user_id: Optional[int] = None) -> dict[str, Any]:
        if not self.client:
            logger.info("DeepSeek not configured, using regex fallback")
            return regex_parse_intent(message)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if user_id is not None:
            messages.extend(self.get_session(user_id))
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=500,
            )
            raw = response.choices[0].message.content or ""
            parsed = _extract_json(raw)
            if parsed and parsed.get("intent") in VALID_INTENTS:
                parsed["raw_message"] = message
                if user_id is not None:
                    self.add_to_session(user_id, "user", message)
                    self.add_to_session(user_id, "assistant", raw)
                return parsed
            logger.warning("Invalid LLM response, falling back to regex: %s", raw[:200])
        except Exception as exc:
            logger.exception("DeepSeek classify failed: %s", exc)

        return regex_parse_intent(message)


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None
