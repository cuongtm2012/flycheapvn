"""Kiwi/Tequila API source."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from utils import vnd_to_usd

logger = logging.getLogger(__name__)

KIWI_BASE = "https://api.tequila.kiwi.com"
AIRLINE_MAP = {
    "VJ": "VietJet Air",
    "VN": "Vietnam Airlines",
    "QH": "Bamboo Airways",
    "VU": "Vietravel Airlines",
    "BL": "Pacific Airlines",
}


class KiwiSource:
    name = "kiwi"
    max_per_hour = 500

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KIWI_API_KEY", "picky")

    async def search(
        self,
        origin: str,
        dest: str,
        date_from: str,
        date_to: Optional[str] = None,
        max_price: Optional[int] = None,
        currency: str = "VND",
        limit: int = 5,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "fly_from": origin,
            "fly_to": dest,
            "date_from": date_from,
            "date_to": date_to or date_from,
            "curr": currency,
            "limit": limit,
            "sort": "price",
            "one_for_city": 0,
            "max_stopovers": 2,
        }
        if max_price:
            params["price_to"] = max_price

        headers = {"apikey": self.api_key, "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{KIWI_BASE}/v2/search", params=params, headers=headers)

        if resp.status_code == 429:
            return {"success": False, "rate_limited": True, "source": self.name, "flights": []}

        if resp.status_code != 200:
            logger.warning("Kiwi API error %s: %s", resp.status_code, resp.text[:200])
            return {"success": False, "source": self.name, "flights": [], "error": resp.text[:200]}

        data = resp.json()
        flights = []
        for item in data.get("data", [])[:limit]:
            route = item.get("route", [])
            if not route:
                continue
            first = route[0]
            last = route[-1]
            airline_code = first.get("airline", "")
            price = int(float(item.get("price", 0)))
            dep_ts = first.get("local_departure", "")
            arr_ts = last.get("local_arrival", "")
            duration = item.get("duration", {}).get("total", 0) // 60 if item.get("duration") else 0
            if not duration and dep_ts and arr_ts:
                try:
                    dep = datetime.fromisoformat(dep_ts.replace("Z", ""))
                    arr = datetime.fromisoformat(arr_ts.replace("Z", ""))
                    duration = int((arr - dep).total_seconds() // 60)
                except ValueError:
                    duration = 0

            flights.append({
                "airline": airline_code,
                "airline_name": AIRLINE_MAP.get(airline_code, airline_code),
                "flight_number": f"{airline_code}{first.get('flight_no', '')}",
                "price": price,
                "currency": currency,
                "price_usd": vnd_to_usd(price) if currency == "VND" else round(price, 2),
                "departure": dep_ts,
                "arrival": arr_ts,
                "origin": first.get("flyFrom", origin),
                "dest": last.get("flyTo", dest),
                "stops": max(0, len(route) - 1),
                "duration_minutes": duration,
                "booking_url": item.get("deep_link", ""),
            })

        return {"success": bool(flights), "source": self.name, "flights": flights, "cached": False}

    async def quick_price(self, origin: str, dest: str, date_from: Optional[str] = None) -> Optional[int]:
        if not date_from:
            date_from = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
        result = await self.search(origin, dest, date_from, limit=1)
        flights = result.get("flights", [])
        return flights[0]["price"] if flights else None
