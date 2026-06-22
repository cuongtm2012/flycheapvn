"""Aviasales/Travelpayouts cached prices source."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from utils import vnd_to_usd

logger = logging.getLogger(__name__)

AVIASALES_BASE = "https://api.travelpayouts.com/aviasales/v3"


class AviasalesSource:
    name = "aviasales"
    max_per_hour = 200

    def __init__(self):
        self.token = os.getenv("TRAVELPAYOUTS_TOKEN", "")

    def is_configured(self) -> bool:
        return bool(self.token)

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
            "origin": origin,
            "destination": dest,
            "departure_at": date_from,
            "currency": "rub" if currency == "VND" else currency.lower(),
            "limit": limit,
            "sorting": "price",
        }
        headers = {"X-Access-Token": self.token}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{AVIASALES_BASE}/prices_for_dates", params=params, headers=headers)

        if resp.status_code == 429:
            return {"success": False, "rate_limited": True, "source": self.name, "flights": []}
        if resp.status_code != 200:
            logger.warning("Aviasales API error %s", resp.status_code)
            return {"success": False, "source": self.name, "flights": []}

        flights = []
        for item in resp.json().get("data", [])[:limit]:
            price_rub = int(item.get("price", 0))
            price = int(price_rub * 280) if currency == "VND" else price_rub
            if max_price and price > max_price:
                continue
            airline = item.get("airline", "")
            dep_at = item.get("departure_at", f"{date_from}T06:00:00")

            flights.append({
                "airline": airline,
                "airline_name": airline,
                "flight_number": airline,
                "price": price,
                "currency": currency,
                "price_usd": vnd_to_usd(price),
                "departure": dep_at,
                "arrival": dep_at,
                "origin": origin,
                "dest": dest,
                "stops": item.get("transfers", 0),
                "duration_minutes": item.get("duration", 90),
                "booking_url": item.get("link", ""),
            })

        return {"success": bool(flights), "source": self.name, "flights": flights, "cached": False}

    async def quick_price(self, origin: str, dest: str, date_from: Optional[str] = None) -> Optional[int]:
        if not date_from:
            date_from = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
        result = await self.search(origin, dest, date_from, limit=1)
        flights = result.get("flights", [])
        return flights[0]["price"] if flights else None
