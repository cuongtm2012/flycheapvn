"""Google Flights scrape via Playwright — fallback when APIs are unavailable."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from utils import vnd_to_usd

logger = logging.getLogger(__name__)

AIRLINE_CODES: dict[str, str] = {
    "VietJet Air": "VJ",
    "VietJet": "VJ",
    "Vietnam Airlines": "VN",
    "Bamboo Airways": "QH",
    "Bamboo": "QH",
    "Vietravel Airlines": "VU",
    "Pacific Airlines": "BL",
    "Pacific": "BL",
}

_playwright_checked = False
_playwright_available = False


def _check_playwright() -> bool:
    global _playwright_checked, _playwright_available
    if _playwright_checked:
        return _playwright_available
    _playwright_checked = True
    try:
        import playwright  # noqa: F401
    except ImportError:
        _playwright_available = False
        return False
    _playwright_available = True
    return True


class GoogleFlightsScraper:
    name = "google_flights"
    max_per_hour = 10
    parallel_eligible = False
    quick_price_eligible = False

    def is_configured(self) -> bool:
        if os.getenv("GOOGLE_FLIGHTS_SCRAPER", "1").lower() in ("0", "false", "no"):
            return False
        return _check_playwright()

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
            return {
                "success": False,
                "source": self.name,
                "flights": [],
                "error": "playwright_not_installed",
            }
        try:
            return await self._do_scrape(origin, dest, date_from, max_price, currency, limit)
        except Exception as exc:
            logger.exception("Google Flights scrape failed: %s", exc)
            return {"success": False, "source": self.name, "flights": [], "error": str(exc)[:200]}

    async def _do_scrape(
        self, origin: str, dest: str, date_from: str,
        max_price: Optional[int], currency: str, limit: int,
    ) -> dict[str, Any]:
        from playwright.async_api import async_playwright

        url = (
            f"https://www.google.com/travel/flights?"
            f"q=Flights+to+{dest}+from+{origin}+on+{date_from}"
            f"&curr={currency}&hl=en"
        )

        logger.info("Scraping Google Flights: %s → %s on %s", origin, dest, date_from)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await page.wait_for_timeout(3000)

            body_text = await page.inner_text("body")
            if "something went wrong" in body_text.lower() or "oops" in body_text.lower():
                await browser.close()
                return {
                    "success": False,
                    "source": self.name,
                    "flights": [],
                    "error": "google_blocked",
                }

            flights = await self._extract_flights(page, origin, dest, date_from, max_price, limit)

            await browser.close()

        if flights:
            return {"success": True, "source": self.name, "flights": flights, "cached": False}
        return {"success": False, "source": self.name, "flights": [], "error": "no_results"}

    async def _extract_flights(
        self, page, origin: str, dest: str, date_from: str,
        max_price: Optional[int], limit: int,
    ) -> list[dict[str, Any]]:
        flights = []

        try:
            await page.wait_for_selector('[role="listitem"]', timeout=15000)
        except Exception:
            pass

        items = await page.query_selector_all('[role="listitem"]')
        logger.info("Found %d flight items on Google Flights", len(items))

        for item in items[: limit * 3]:
            try:
                flight = await self._parse_item(item, origin, dest, date_from)
                if not flight:
                    continue
                if max_price and flight["price"] > max_price:
                    continue
                flights.append(flight)
                if len(flights) >= limit:
                    break
            except Exception as exc:
                logger.warning("Parse item failed: %s", exc)

        return flights

    async def _parse_item(
        self, item, origin: str, dest: str, date_from: str,
    ) -> Optional[dict[str, Any]]:
        airline_el = await item.query_selector(".sSHqwe, [aria-label*='airline'], .Ir0Voe")
        airline_name = ""
        if airline_el:
            airline_name = await airline_el.inner_text()
        airline_name = airline_name.strip()

        price_el = await item.query_selector(".YMlIz, .FpEdX, [aria-label*='price'], span[aria-label*='₫']")
        price = 0
        if price_el:
            price_text = await price_el.get_attribute("aria-label") or await price_el.inner_text()
            price = self._parse_price(price_text)

        time_el = await item.query_selector(".mv1WYe, .Ak5kWe, [aria-label*='departure']")
        dep_time = f"{date_from}T00:00:00"
        arr_time = f"{date_from}T00:00:00"
        if time_el:
            times = await time_el.inner_text()
            parts = re.split(r"[–\-]", times, maxsplit=1)
            if len(parts) == 2:
                dep_time = self._parse_time(parts[0].strip(), date_from)
                arr_time = self._parse_time(parts[1].strip(), date_from)

        stops = 0
        stops_el = await item.query_selector(".EfTay, .BbR8Ec")
        if stops_el:
            stops_text = await stops_el.inner_text()
            if "nonstop" in stops_text.lower() or "thẳng" in stops_text.lower():
                stops = 0
            else:
                m = re.search(r"(\d+)\s*stop", stops_text.lower())
                if m:
                    stops = int(m.group(1))

        duration = 0
        dur_el = await item.query_selector(".AdWm1e, .gvkrdb")
        if dur_el:
            dur_text = await dur_el.inner_text()
            duration = self._parse_duration(dur_text)

        airline_code = self._resolve_airline(airline_name)

        if not price:
            return None

        return {
            "airline": airline_code,
            "airline_name": airline_name or airline_code,
            "flight_number": airline_code,
            "price": price,
            "currency": "VND",
            "price_usd": vnd_to_usd(price),
            "departure": dep_time,
            "arrival": arr_time,
            "origin": origin,
            "dest": dest,
            "stops": stops,
            "duration_minutes": duration,
            "booking_url": "",
        }

    def _parse_price(self, text: str) -> int:
        text = text.replace(",", "").replace(".", "").replace("₫", "").replace("VND", "").strip()
        m = re.search(r"(\d[\d]*)", text)
        if m:
            return int(m.group(1))
        return 0

    def _parse_time(self, raw: str, date_from: str) -> str:
        """Parse '6:35 AM' or '18:35' into ISO datetime."""
        raw = raw.strip()
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
            try:
                t = datetime.strptime(raw.upper().replace(" ", ""), fmt.replace(" ", ""))
                return f"{date_from}T{t.strftime('%H:%M:%S')}"
            except ValueError:
                continue
        cleaned = re.sub(r"[^\d:]", "", raw)
        if ":" in cleaned:
            return f"{date_from}T{cleaned}:00" if cleaned.count(":") == 1 else f"{date_from}T{cleaned}"
        return f"{date_from}T00:00:00"

    def _parse_duration(self, text: str) -> int:
        h = re.search(r"(\d+)\s*h", text)
        m = re.search(r"(\d+)\s*m", text)
        hours = int(h.group(1)) * 60 if h else 0
        mins = int(m.group(1)) if m else 0
        return hours + mins

    def _resolve_airline(self, name: str) -> str:
        for key, code in AIRLINE_CODES.items():
            if key.lower() in name.lower():
                return code
        return "??"

    async def quick_price(self, origin: str, dest: str, date_from: Optional[str] = None) -> Optional[int]:
        # Không dùng cho alert — quá chậm; api_router sẽ skip nguồn này trong quick_price
        return None
