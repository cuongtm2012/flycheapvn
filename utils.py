"""Helpers: airport codes, currency, date parsing."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

# IATA codes for Vietnamese cities and common international destinations
AIRPORT_ALIASES: dict[str, str] = {
  # Vietnam
    "hà nội": "HAN", "ha noi": "HAN", "hanoi": "HAN", "hn": "HAN", "han": "HAN",
    "sài gòn": "SGN", "sai gon": "SGN", "hcm": "SGN", "sg": "SGN", "sgn": "SGN",
    "tp hcm": "SGN", "tp.hcm": "SGN", "hồ chí minh": "SGN", "ho chi minh": "SGN",
    "đà nẵng": "DAD", "da nang": "DAD", "dn": "DAD", "dad": "DAD",
    "đà lạt": "DLI", "da lat": "DLI", "dli": "DLI",
    "nha trang": "CXR", "cxr": "CXR",
    "phú quốc": "PQC", "phu quoc": "PQC", "pqc": "PQC",
    "hải phòng": "HPH", "hai phong": "HPH", "hph": "HPH",
    "huế": "HUI", "hue": "HUI", "hui": "HUI",
    "vinh": "VII", "vii": "VII",
    "quy nhơn": "UIH", "quy nhon": "UIH", "uih": "UIH",
    "cần thơ": "VCA", "can tho": "VCA", "vca": "VCA",
    "rạch giá": "VKG", "rach gia": "VKG", "vkg": "VKG",
    "buôn ma thuột": "BMV", "buon ma thuot": "BMV", "bmv": "BMV",
    "pleiku": "PXU", "pxu": "PXU",
    "tuy hòa": "TBB", "tuy hoa": "TBB", "tbb": "TBB",
    # International
    "bangkok": "BKK", "bkk": "BKK",
    "seoul": "ICN", "icn": "ICN",
    "singapore": "SIN", "sin": "SIN",
    "tokyo": "NRT", "nrt": "NRT",
    "taipei": "TPE", "tpe": "TPE",
}

# Set of Vietnamese domestic airport codes
VN_DOMESTIC_AIRPORTS = {"HAN", "SGN", "DAD", "DLI", "CXR", "PQC", "HPH", "HUI",
                         "VII", "UIH", "VCA", "VKG", "BMV", "PXU", "TBB"}

AIRLINE_NAMES: dict[str, str] = {
    "VJ": "VietJet Air",
    "VN": "Vietnam Airlines",
    "QH": "Bamboo Airways",
    "VU": "Vietravel Airlines",
    "BL": "Pacific Airlines",
}

USD_TO_VND = 23_200


def resolve_airport(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = text.strip().lower()
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    return AIRPORT_ALIASES.get(cleaned)


def parse_price_vnd(text: str) -> Optional[int]:
    """Parse '1tr', '800k', '1.2 triệu', '500000'."""
    if not text:
        return None
    t = text.lower().strip()

    m = re.search(r"([\d]+(?:[.,]\d+)?)\s*(tr|triệu|trieu|m)\b", t)
    if m:
        num = float(m.group(1).replace(",", "."))
        return int(num * 1_000_000)

    m = re.search(r"(\d+)\s*k\b", t)
    if m:
        return int(m.group(1)) * 1_000

    m = re.search(r"(\d{4,})", t.replace(" ", "").replace(".", "").replace(",", ""))
    if m:
        return int(m.group(1))
    return None


def format_price_vnd(amount: int) -> str:
    if amount >= 1_000_000:
        val = amount / 1_000_000
        if val == int(val):
            return f"{int(val)}tr"
        return f"{val:.1f}tr".replace(".0tr", "tr")
    if amount >= 1_000:
        val = amount / 1_000
        if val == int(val):
            return f"{int(val)}k"
        return f"{val:.0f}k"
    return f"{amount:,}đ".replace(",", ".")


def vnd_to_usd(vnd: int) -> float:
    return round(vnd / USD_TO_VND, 2)


def format_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h{m:02d}m"
    if h:
        return f"{h}h"
    return f"{m}p"


def format_datetime_vn(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except ValueError:
        return iso_str


def format_date_vn(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_str


def make_cache_key(params: dict[str, Any]) -> str:
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


PROMO_KEYWORDS = (
    "khuyến mãi", "khuyen mai", "khuyến mại", "khuyen mai",
    "giảm giá", "giam gia", "sale", "deal", "0 đồng", "flash sale",
)


def is_promo_related(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in PROMO_KEYWORDS)


def month_end(date_from: str) -> str:
    """Last day of month for YYYY-MM-DD (typically day 1 of month)."""
    d = date.fromisoformat(date_from[:10])
    if d.month == 12:
        return f"{d.year}-12-31"
    next_month = date(d.year, d.month + 1, 1)
    last = next_month - timedelta(days=1)
    return last.isoformat()


def ensure_date_range(date_from: Optional[str], date_to: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not date_from:
        return None, date_to
    if date_to:
        return date_from[:10], date_to[:10]
    d = date.fromisoformat(date_from[:10])
    if d.day == 1:
        return date_from[:10], month_end(date_from)
    return date_from[:10], date_to


def is_month_or_range_query(parsed: dict[str, Any]) -> bool:
    raw = (parsed.get("raw_message") or "").lower()
    if parsed.get("date_to"):
        return True
    return any(kw in raw for kw in ("tháng", "thang", "cuối năm", "cuoi nam", "từ bây giờ", "tu bay gio"))


def date_in_range(day: str, date_from: str, date_to: Optional[str]) -> bool:
    d = day[:10]
    if d < date_from[:10]:
        return False
    if date_to and d > date_to[:10]:
        return False
    return True


def filter_calendar_by_range(
    calendar: list[dict[str, Any]],
    date_from: Optional[str],
    date_to: Optional[str],
) -> list[dict[str, Any]]:
    if not date_from:
        return calendar
    return [d for d in calendar if date_in_range(d["day"], date_from, date_to)]


def flights_in_range(
    flights: list[dict[str, Any]],
    date_from: str,
    date_to: Optional[str],
) -> list[dict[str, Any]]:
    return [
        f for f in flights
        if date_in_range((f.get("departure") or "")[:10], date_from, date_to)
    ]


def format_month_label(date_from: str, date_to: Optional[str]) -> str:
    d = date.fromisoformat(date_from[:10])
    if date_to and date_to[:7] != date_from[:7]:
        return f"{date_from[:7]} → {date_to[:7]}"
    return f"tháng {d.month}/{d.year}"


def is_domestic_route(origin: str, dest: str) -> bool:
    """Check if both airports are Vietnamese domestic."""
    return origin in VN_DOMESTIC_AIRPORTS and dest in VN_DOMESTIC_AIRPORTS


def filter_domestic_flights(flights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter out flights with non-Vietnamese airlines on domestic routes.
    Airline codes starting with letters outside VN domestic airlines (VJ, VN, QH, VU, BL)
    are suspicious on domestic VN routes.
    """
    VN_AIRLINES = {"VJ", "VN", "QH", "VU", "BL"}
    return [
        f for f in flights
        if f.get("airline") in VN_AIRLINES or f.get("duration_minutes", 0) <= 180
    ]


def parse_relative_date(text: str, reference: Optional[date] = None) -> Optional[str]:
    """Parse Vietnamese relative dates to YYYY-MM-DD."""
    ref = reference or date.today()
    t = text.lower().strip()

    if re.match(r"\d{4}-\d{2}-\d{2}", t):
        return t[:10]

    if "hôm nay" in t or "hom nay" in t:
        return ref.isoformat()
    if "ngày mai" in t or "ngay mai" in t or "mai" == t:
        return (ref + timedelta(days=1)).isoformat()
    if "tuần sau" in t or "tuan sau" in t:
        return (ref + timedelta(days=7)).isoformat()
    if "cuối tuần" in t or "cuoi tuan" in t:
        days_until_saturday = (5 - ref.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        return (ref + timedelta(days=days_until_saturday)).isoformat()

    m = re.search(r"tháng\s*(\d{1,2})", t)
    if m:
        month = int(m.group(1))
        year = ref.year
        if month < ref.month:
            year += 1
        return date(year, month, 1).isoformat()

    return None


def regex_parse_intent(message: str) -> dict[str, Any]:
    """Fallback parser when LLM is unavailable."""
    msg = message.lower().strip()
    result: dict[str, Any] = {
        "intent": "general_chat",
        "origin": None,
        "destination": None,
        "date_from": None,
        "date_to": None,
        "max_price": None,
        "airline": None,
        "trip_type": "one_way",
        "raw_message": message,
    }

    if msg.startswith("/start"):
        result["intent"] = "general_chat"
        result["sub_intent"] = "start"
        return result
    if msg.startswith("/help"):
        result["intent"] = "general_chat"
        result["sub_intent"] = "help"
        return result
    if msg.startswith("/uptime"):
        result["intent"] = "general_chat"
        result["sub_intent"] = "uptime"
        return result
    if msg.startswith("/check-alerts") or "check-alerts" in msg:
        result["intent"] = "check_alerts"
        return result

    alert_cmd = re.match(
        r"/theodoi\s+(\w+)-(\w+)\s+(duoi|dưới|under)\s+(.+)",
        msg,
        re.IGNORECASE,
    )
    if alert_cmd:
        result["intent"] = "set_alert"
        result["origin"] = resolve_airport(alert_cmd.group(1)) or alert_cmd.group(1).upper()
        result["destination"] = resolve_airport(alert_cmd.group(2)) or alert_cmd.group(2).upper()
        result["max_price"] = parse_price_vnd(alert_cmd.group(4))
        return result

    if any(kw in msg for kw in ("theo dõi", "theodoi", "báo em khi", "bao em khi", "alert")):
        result["intent"] = "set_alert"
        route = re.search(r"(\w+)\s*[-→>]\s*(\w+)", msg)
        if route:
            result["origin"] = resolve_airport(route.group(1)) or route.group(1).upper()
            result["destination"] = resolve_airport(route.group(2)) or route.group(2).upper()
        price_match = re.search(r"(duoi|dưới|under)\s+(.+)", msg)
        if price_match:
            result["max_price"] = parse_price_vnd(price_match.group(2))
        return result

    if any(kw in msg for kw in ("tìm vé", "tim ve", "vé đi", "ve di", "có chuyến", "co chuyen", "bay từ", "bay tu")):
        result["intent"] = "search_flight"
    elif any(kw in msg for kw in ("khuyến mãi", "khuyen mai", "giảm giá", "giam gia", "sale", "deal", "0 đồng")):
        result["intent"] = "promo_check"
    elif any(kw in msg for kw in ("so sánh", "so sanh", "hay hơn", "rẻ hơn", "re hon")):
        result["intent"] = "compare"
    elif any(kw in msg for kw in ("lịch bay", "lich bay", "chuyến thẳng", "chuyen thang", "giờ bay", "gio bay")):
        result["intent"] = "schedule"
    elif any(kw in msg for kw in ("nên mua", "nen mua", "dự đoán", "du doan", "chờ thêm", "cho them")):
        result["intent"] = "price_predict"
    elif any(kw in msg for kw in ("mẹo", "meo", "tư vấn", "tu van", "nên đặt", "nen dat")):
        result["intent"] = "advice"
    elif any(kw in msg for kw in ("ngày tốt", "ngay tot", "hoàng đạo", "hoang dao", "can chi")):
        result["intent"] = "lucky_date"

    route = re.search(
        r"(?:từ|tu|from)\s+([\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+?)\s+"
        r"(?:đi|ra|to|→|->|-)\s*([\w\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)",
        message,
        re.IGNORECASE,
    )
    if not route:
        route = re.search(r"([\w]{2,10})\s*[-→>]\s*([\w]{2,10})", msg)
    if route:
        result["origin"] = resolve_airport(route.group(1)) or resolve_airport(route.group(2))
        result["destination"] = resolve_airport(route.group(2)) or resolve_airport(route.group(1))
        if route.group(1) and route.group(2):
            o = resolve_airport(route.group(1)) or (route.group(1).upper() if len(route.group(1)) == 3 else None)
            d = resolve_airport(route.group(2)) or (route.group(2).upper() if len(route.group(2)) == 3 else None)
            result["origin"] = o
            result["destination"] = d

    for phrase in ("cuối tuần này", "cuoi tuan nay", "tuần sau", "tuan sau", "ngày mai", "ngay mai", "hôm nay", "hom nay"):
        if phrase in msg:
            result["date_from"] = parse_relative_date(phrase)
            break

    price = parse_price_vnd(msg)
    if price and ("duoi" in msg or "dưới" in msg):
        result["max_price"] = price

    return result
