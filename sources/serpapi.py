"""SerpAPI Google Flights source (fallback)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from utils import vnd_to_usd

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"


class SerpAPISource:
    name = "serpapi"
    max_per_hour = 10

    def __init__(self):
        self.api_key = os.getenv("SERPAPI_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.api_key)

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
        if not self.is_configured():
            return {"success": False, "source": self.name, "flights": [], "error": "not_configured"}

        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": dest,
            "outbound_date": date_from,
            "currency": "VND" if currency == "VND" else currency,
            "hl": "vi",
            "api_key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.get(SERPAPI_BASE, params=params)

        if resp.status_code == 429:
            return {"success": False, "rate_limited": True, "source": self.name, "flights": []}
        if resp.status_code != 200:
            logger.warning("SerpAPI error %s", resp.status_code)
            return {"success": False, "source": self.name, "flights": []}

        flights = []
        best = resp.json().get("best_flights", [])
        for item in best[:limit]:
            price = int(item.get("price", 0))
            if max_price and price > max_price:
                continue
            legs = item.get("flights", [])
            if not legs:
                continue
            first = legs[0]
            last = legs[-1]
            airline = first.get("airline", "")
            dep = f"{first.get('departure_airport', {}).get('time', '')}"
            arr = f"{last.get('arrival_airport', {}).get('time', '')}"

            flights.append({
                "airline": airline[:2].upper() if airline else "??",
                "airline_name": airline,
                "flight_number": first.get("flight_number", ""),
                "price": price,
                "currency": currency,
                "price_usd": vnd_to_usd(price),
                "departure": f"{date_from}T{dep}" if dep else date_from,
                "arrival": f"{date_from}T{arr}" if arr else date_from,
                "origin": origin,
                "dest": dest,
                "stops": max(0, len(legs) - 1),
                "duration_minutes": item.get("total_duration", 90),
                "booking_url": "",
            })

        return {"success": bool(flights), "source": self.name, "flights": flights, "cached": False}
