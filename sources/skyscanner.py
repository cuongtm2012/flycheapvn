"""Skyscanner RapidAPI source."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from utils import vnd_to_usd

logger = logging.getLogger(__name__)

SKYSCANNER_HOST = "skyscanner44.p.rapidapi.com"


class SkyscannerSource:
    name = "skyscanner"
    max_per_hour = 50

    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY", "")

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

        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": SKYSCANNER_HOST,
        }
        params = {
            "fromEntityId": origin,
            "toEntityId": dest,
            "departDate": date_from,
            "adults": "1",
            "currency": currency,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"https://{SKYSCANNER_HOST}/v1/flights/search-one-way",
                params=params,
                headers=headers,
            )

        if resp.status_code == 429:
            return {"success": False, "rate_limited": True, "source": self.name, "flights": []}
        if resp.status_code != 200:
            logger.warning("Skyscanner API error %s", resp.status_code)
            return {"success": False, "source": self.name, "flights": []}

        flights = []
        data = resp.json()
        items = data.get("data", data.get("itineraries", []))
        if isinstance(items, dict):
            items = list(items.values())

        for item in (items or [])[:limit]:
            price = int(float(item.get("price", {}).get("raw", item.get("price", 0))))
            if max_price and price > max_price:
                continue
            legs = item.get("legs", [item])
            leg = legs[0] if legs else item
            carrier = leg.get("carriers", {}).get("marketing", [{}])
            carrier_code = carrier[0].get("alternateId", "") if carrier else ""
            dep = leg.get("departure", "")
            arr = leg.get("arrival", "")
            duration = leg.get("durationInMinutes", 0)

            flights.append({
                "airline": carrier_code,
                "airline_name": carrier[0].get("name", carrier_code) if carrier else carrier_code,
                "flight_number": carrier_code,
                "price": price,
                "currency": currency,
                "price_usd": vnd_to_usd(price) if currency == "VND" else round(price, 2),
                "departure": dep,
                "arrival": arr,
                "origin": origin,
                "dest": dest,
                "stops": leg.get("stopCount", 0),
                "duration_minutes": duration,
                "booking_url": item.get("deeplink", ""),
            })

        return {"success": bool(flights), "source": self.name, "flights": flights, "cached": False}
