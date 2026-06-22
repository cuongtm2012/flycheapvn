"""Fly Scraper RapidAPI source (Skyscanner-based)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from utils import USD_TO_VND, vnd_to_usd

logger = logging.getLogger(__name__)

FLY_SCRAPER_HOST = "fly-scraper.p.rapidapi.com"
BASE_URL = f"https://{FLY_SCRAPER_HOST}"


def _dt_to_iso(dt: dict[str, int]) -> str:
    return (
        f"{dt['year']:04d}-{dt['month']:02d}-{dt['day']:02d}"
        f"T{dt['hour']:02d}:{dt['minute']:02d}:{dt.get('second', 0):02d}"
    )


def _milli_to_vnd(amount: Any, currency: str) -> int:
    value = int(amount) / 1000
    if currency == "VND":
        return int(value)
    if currency == "USD":
        return int(value * USD_TO_VND)
    return int(value * USD_TO_VND)


class FlyScraperSource:
    name = "fly_scraper"
    max_per_hour = 50

    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY", "")
        self.host = os.getenv("FLY_SCRAPER_HOST", FLY_SCRAPER_HOST)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
            "Content-Type": "application/json",
        }

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
            "originSkyId": origin.upper(),
            "destinationSkyId": dest.upper(),
            "date": date_from,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(
                    f"https://{self.host}/v2/flights/search-one-way",
                    params=params,
                    headers=self._headers(),
                )
        except httpx.TimeoutException:
            logger.warning("Fly Scraper timeout for %s-%s", origin, dest)
            return await self._search_via_calendar(origin, dest, date_from, max_price, currency, limit)

        if resp.status_code == 429:
            return {"success": False, "rate_limited": True, "source": self.name, "flights": []}

        if resp.status_code != 200:
            logger.warning("Fly Scraper error %s: %s", resp.status_code, resp.text[:200])
            return await self._search_via_calendar(origin, dest, date_from, max_price, currency, limit)

        try:
            data = resp.json()
        except ValueError:
            return {"success": False, "source": self.name, "flights": []}

        if not data.get("status"):
            logger.warning("Fly Scraper API status false: %s", data.get("message", "")[:200])
            return await self._search_via_calendar(origin, dest, date_from, max_price, currency, limit)

        flights = self._parse_itineraries(
            data.get("data", {}),
            origin.upper(),
            dest.upper(),
            currency,
            max_price,
            limit,
        )
        if flights:
            return {"success": True, "source": self.name, "flights": flights, "cached": False}

        return await self._search_via_calendar(origin, dest, date_from, max_price, currency, limit)

    def _parse_itineraries(
        self,
        payload: dict[str, Any],
        origin: str,
        dest: str,
        currency: str,
        max_price: Optional[int],
        limit: int,
    ) -> list[dict[str, Any]]:
        flights: list[dict[str, Any]] = []
        for item in payload.get("itineraries", [])[: limit * 2]:
            options = item.get("pricingOptions") or []
            if not options:
                continue
            option = options[0]
            price_raw = option.get("price", {}).get("amount")
            if price_raw is None:
                continue

            price_vnd = _milli_to_vnd(price_raw, "USD")
            if max_price and price_vnd > max_price:
                continue

            legs = item.get("legs") or []
            if not legs:
                continue
            leg = legs[0]
            carriers = (leg.get("carriers") or {}).get("marketing") or []
            carrier = carriers[0] if carriers else {}
            airline_code = carrier.get("displayCode") or carrier.get("iata") or "??"
            airline_name = carrier.get("name") or airline_code

            segments = leg.get("segments") or []
            flight_no = ""
            if segments:
                flight_no = segments[0].get("marketingFlightNumber", "")

            dep_dt = leg.get("departureDateTime") or {}
            arr_dt = leg.get("arrivalDateTime") or {}
            booking_url = ""
            items = option.get("items") or []
            if items:
                booking_url = items[0].get("deepLink", "")

            flights.append({
                "airline": airline_code,
                "airline_name": airline_name,
                "flight_number": f"{airline_code}{flight_no}",
                "price": price_vnd,
                "currency": "VND",
                "price_usd": vnd_to_usd(price_vnd),
                "departure": _dt_to_iso(dep_dt) if dep_dt else date_now_str(),
                "arrival": _dt_to_iso(arr_dt) if arr_dt else date_now_str(),
                "origin": origin,
                "dest": dest,
                "stops": leg.get("stopCount", 0),
                "duration_minutes": leg.get("durationInMinutes", 0),
                "booking_url": booking_url,
            })
            if len(flights) >= limit:
                break

        flights.sort(key=lambda f: f["price"])
        return flights

    async def _search_via_calendar(
        self,
        origin: str,
        dest: str,
        date_from: str,
        max_price: Optional[int],
        currency: str,
        limit: int,
    ) -> dict[str, Any]:
        calendar = await self.price_calendar(origin, dest)
        if not calendar:
            return {"success": False, "source": self.name, "flights": []}

        matched = [d for d in calendar if d["day"] == date_from]
        pool = matched or sorted(calendar, key=lambda x: x["price_vnd"])[:limit]

        flights = []
        for day in pool[:limit]:
            if max_price and day["price_vnd"] > max_price:
                continue
            flights.append({
                "airline": day["airline_code"],
                "airline_name": day["airline"],
                "flight_number": day["airline_code"],
                "price": day["price_vnd"],
                "currency": "VND",
                "price_usd": vnd_to_usd(day["price_vnd"]),
                "departure": f"{day['day']}T06:00:00",
                "arrival": f"{day['day']}T08:00:00",
                "origin": origin.upper(),
                "dest": dest.upper(),
                "stops": 0,
                "duration_minutes": 120,
                "booking_url": "",
            })

        return {"success": bool(flights), "source": self.name, "flights": flights, "cached": False}

    async def price_calendar(self, origin: str, dest: str) -> list[dict[str, Any]]:
        params = {
            "originSkyId": origin.upper(),
            "destinationSkyId": dest.upper(),
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(
                    f"https://{self.host}/v2/flights/price-calendar",
                    params=params,
                    headers=self._headers(),
                )
        except httpx.TimeoutException:
            logger.warning("Fly Scraper price-calendar timeout")
            return []

        if resp.status_code != 200:
            return []

        try:
            data = resp.json()
        except ValueError:
            return []

        if not data.get("status"):
            return []

        results = []
        for item in data.get("data", []):
            price_usd = float(item.get("price", 0))
            results.append({
                "day": item["day"],
                "price_vnd": int(price_usd * USD_TO_VND),
                "airline": item.get("airline", ""),
                "airline_code": item.get("airlineCode", ""),
            })
        return results

    async def quick_price(self, origin: str, dest: str, date_from: Optional[str] = None) -> Optional[int]:
        if date_from:
            result = await self.search(origin, dest, date_from, limit=1)
            flights = result.get("flights", [])
            if flights:
                return flights[0]["price"]

        calendar = await self.price_calendar(origin, dest)
        if not calendar:
            return None
        if date_from:
            for day in calendar:
                if day["day"] == date_from:
                    return day["price_vnd"]
        return min(d["price_vnd"] for d in calendar)


def date_now_str() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%dT00:00:00")
