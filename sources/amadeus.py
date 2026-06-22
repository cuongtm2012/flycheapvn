"""Amadeus Self-Service API source."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from utils import vnd_to_usd

logger = logging.getLogger(__name__)

AMADEUS_AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
AMADEUS_BASE = "https://test.api.amadeus.com"

AIRLINE_MAP = {
    "VJ": "VietJet Air",
    "VN": "Vietnam Airlines",
    "QH": "Bamboo Airways",
}


class AmadeusSource:
    name = "amadeus"
    max_per_hour = 100

    def __init__(self):
        self.client_id = os.getenv("AMADEUS_CLIENT_ID", "")
        self.client_secret = os.getenv("AMADEUS_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_token(self) -> Optional[str]:
        if self._token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._token
        if not self.is_configured():
            return None

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                AMADEUS_AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
        if resp.status_code != 200:
            logger.warning("Amadeus auth failed: %s", resp.status_code)
            return None
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 1800) - 60)
        return self._token

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
        token = await self._get_token()
        if not token:
            return {"success": False, "source": self.name, "flights": [], "error": "not_configured"}

        params = {
            "originLocationCode": origin,
            "destinationLocationCode": dest,
            "departureDate": date_from,
            "adults": 1,
            "max": limit,
            "currencyCode": currency,
        }
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{AMADEUS_BASE}/v2/shopping/flight-offers",
                params=params,
                headers=headers,
            )

        if resp.status_code == 429:
            return {"success": False, "rate_limited": True, "source": self.name, "flights": []}
        if resp.status_code != 200:
            logger.warning("Amadeus API error %s", resp.status_code)
            return {"success": False, "source": self.name, "flights": []}

        flights = []
        for offer in resp.json().get("data", [])[:limit]:
            price_info = offer.get("price", {})
            price = int(float(price_info.get("grandTotal", 0)))
            if max_price and price > max_price:
                continue
            itineraries = offer.get("itineraries", [])
            if not itineraries:
                continue
            segments = itineraries[0].get("segments", [])
            if not segments:
                continue
            first = segments[0]
            last = segments[-1]
            carrier = first.get("carrierCode", "")
            duration_str = itineraries[0].get("duration", "PT0H0M")
            duration = _parse_iso_duration(duration_str)

            flights.append({
                "airline": carrier,
                "airline_name": AIRLINE_MAP.get(carrier, carrier),
                "flight_number": f"{carrier}{first.get('number', '')}",
                "price": price,
                "currency": currency,
                "price_usd": vnd_to_usd(price) if currency == "VND" else round(price, 2),
                "departure": first.get("departure", {}).get("at", ""),
                "arrival": last.get("arrival", {}).get("at", ""),
                "origin": first.get("departure", {}).get("iataCode", origin),
                "dest": last.get("arrival", {}).get("iataCode", dest),
                "stops": max(0, len(segments) - 1),
                "duration_minutes": duration,
                "booking_url": "",
            })

        return {"success": bool(flights), "source": self.name, "flights": flights, "cached": False}


def _parse_iso_duration(duration: str) -> int:
    import re
    hours = int(re.search(r"(\d+)H", duration).group(1)) if re.search(r"(\d+)H", duration) else 0
    minutes = int(re.search(r"(\d+)M", duration).group(1)) if re.search(r"(\d+)M", duration) else 0
    return hours * 60 + minutes
