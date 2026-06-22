"""API rotation engine with cache, health tracking, and merge."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from database import (
    get_cache,
    get_source_health_score,
    get_stale_cache,
    increment_source_rate,
    is_circuit_open,
    record_source_result,
    set_cache,
)
from sources import AmadeusSource, AviasalesSource, FlyScraperSource, GoogleFlightsScraper, KiwiSource, SerpAPISource, SkyscannerSource
from utils import format_price_vnd, make_cache_key

logger = logging.getLogger(__name__)

# Thứ tự ưu tiên mặc định (số nhỏ = ưu tiên cao)
SOURCE_PRIORITY: dict[str, int] = {
    "fly_scraper": 1,
    "kiwi": 2,
    "amadeus": 3,
    "skyscanner": 4,
    "aviasales": 5,
    "serpapi": 6,
    "google_flights": 7,  # Fallback cuối — Playwright scrape, chậm
}

MIN_FLIGHTS_BEFORE_STOP = 3
PARALLEL_TOP_N = 2


class APIRouter:
    def __init__(self):
        self.sources = [
            FlyScraperSource(),
            GoogleFlightsScraper(),
            KiwiSource(),
            AmadeusSource(),
            SkyscannerSource(),
            AviasalesSource(),
            SerpAPISource(),
        ]

    def _ordered_sources(self) -> list[Any]:
        active = []
        for source in self.sources:
            if hasattr(source, "is_configured") and not source.is_configured():
                continue
            if is_circuit_open(source.name):
                logger.info("Circuit open, skip %s", source.name)
                continue
            score = get_source_health_score(source.name)
            priority = SOURCE_PRIORITY.get(source.name, 99)
            active.append((priority, -score, source))
        active.sort(key=lambda x: (x[0], x[1]))
        return [s for _, _, s in active]

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
        origin = origin.upper()
        dest = dest.upper()
        cache_params = {
            "origin": origin,
            "dest": dest,
            "date_from": date_from,
            "date_to": date_to,
            "max_price": max_price,
            "currency": currency,
            "limit": limit,
        }
        query_hash = make_cache_key(cache_params)

        cached = get_cache(query_hash)
        if cached:
            logger.info("Cache hit for %s-%s %s", origin, dest, date_from)
            return cached

        sources = self._ordered_sources()
        if not sources:
            return self._empty_result()

        all_flights: list[dict[str, Any]] = []
        used_sources: list[str] = []

        # Phase 1: gọi song song top N nguồn nhanh (bỏ nguồn chậm như Playwright)
        parallel_sources = [
            s for s in sources if getattr(s, "parallel_eligible", True)
        ][:PARALLEL_TOP_N]
        if len(parallel_sources) > 1:
            tasks = [
                self._try_source(s, origin, dest, date_from, date_to, max_price, currency, limit)
                for s in parallel_sources
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for source, result in zip(parallel_sources, results):
                if isinstance(result, Exception):
                    logger.exception("Parallel source %s failed: %s", source.name, result)
                    record_source_result(source.name, False)
                    continue
                if result and result.get("flights"):
                    all_flights.extend(result["flights"])
                    used_sources.append(source.name)
                    record_source_result(source.name, True)
                else:
                    record_source_result(source.name, False)

        # Phase 2: tuần tự các nguồn còn lại nếu chưa đủ kết quả
        if len(_dedupe_flights(all_flights)) < MIN_FLIGHTS_BEFORE_STOP:
            remaining = [s for s in sources if s.name not in used_sources]
            for source in remaining:
                if len(_dedupe_flights(all_flights)) >= limit:
                    break
                if not increment_source_rate(source.name, source.max_per_hour):
                    logger.warning("Rate limit exceeded for %s", source.name)
                    continue
                result = await self._try_source(
                    source, origin, dest, date_from, date_to, max_price, currency, limit
                )
                if result and result.get("flights"):
                    all_flights.extend(result["flights"])
                    used_sources.append(source.name)
                    record_source_result(source.name, True)
                    if len(_dedupe_flights(all_flights)) >= MIN_FLIGHTS_BEFORE_STOP:
                        break
                else:
                    record_source_result(source.name, False)

        # Nếu parallel chỉ có 1 nguồn
        if not all_flights and len(parallel_sources) == 1:
            source = parallel_sources[0]
            if increment_source_rate(source.name, source.max_per_hour):
                result = await self._try_source(
                    source, origin, dest, date_from, date_to, max_price, currency, limit
                )
                if result and result.get("flights"):
                    all_flights = result["flights"]
                    used_sources = [source.name]
                    record_source_result(source.name, True)
                else:
                    record_source_result(source.name, False)

        merged = _dedupe_flights(all_flights, limit)
        if merged:
            payload = {
                "success": True,
                "source": "+".join(used_sources) if len(used_sources) > 1 else used_sources[0],
                "flights": merged,
                "cached": False,
            }
            set_cache(query_hash, payload, payload["source"])
            return payload

        stale = get_stale_cache(query_hash)
        if stale:
            logger.info("Returning stale cache for %s-%s", origin, dest)
            return stale

        return self._empty_result()

    async def _try_source(
        self,
        source: Any,
        origin: str,
        dest: str,
        date_from: str,
        date_to: Optional[str],
        max_price: Optional[int],
        currency: str,
        limit: int,
    ) -> Optional[dict[str, Any]]:
        if not increment_source_rate(source.name, source.max_per_hour):
            return None
        try:
            result = await source.search(
                origin=origin,
                dest=dest,
                date_from=date_from,
                date_to=date_to,
                max_price=max_price,
                currency=currency,
                limit=limit,
            )
            if result.get("rate_limited"):
                return None
            if result.get("success") and result.get("flights"):
                return result
        except Exception as exc:
            logger.exception("Source %s failed: %s", source.name, exc)
        return None

    async def quick_price(
        self, origin: str, dest: str, date_from: Optional[str] = None
    ) -> Optional[int]:
        """Lightweight price check — ưu tiên price-calendar, không gọi full search."""
        if not date_from:
            date_from = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")

        for source in self._ordered_sources():
            if not hasattr(source, "quick_price") or not getattr(source, "quick_price_eligible", True):
                continue
            if not increment_source_rate(source.name, source.max_per_hour):
                continue
            try:
                price = await source.quick_price(origin.upper(), dest.upper(), date_from)
                if price:
                    record_source_result(source.name, True)
                    return price
                record_source_result(source.name, False)
            except Exception as exc:
                logger.warning("quick_price %s failed: %s", source.name, exc)
                record_source_result(source.name, False)

        result = await self.search(origin, dest, date_from, limit=1)
        flights = result.get("flights", [])
        return flights[0]["price"] if flights else None

    async def get_price_calendar(
        self,
        origin: str,
        dest: str,
        limit: int = 5,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Lấy top N ngày rẻ nhất, có thể lọc theo khoảng ngày."""
        from utils import filter_calendar_by_range

        for source in self._ordered_sources():
            if not hasattr(source, "price_calendar"):
                continue
            if not increment_source_rate(source.name, source.max_per_hour):
                continue
            try:
                calendar = await source.price_calendar(origin.upper(), dest.upper())
                if calendar:
                    record_source_result(source.name, True)
                    if date_from:
                        calendar = filter_calendar_by_range(calendar, date_from, date_to)
                    sorted_days = sorted(calendar, key=lambda x: x["price_vnd"])[:limit]
                    return [
                        {
                            "day": d["day"],
                            "price": d["price_vnd"],
                            "price_str": format_price_vnd(d["price_vnd"]),
                            "airline": d.get("airline", ""),
                        }
                        for d in sorted_days
                    ]
                record_source_result(source.name, False)
            except Exception as exc:
                logger.warning("price_calendar %s failed: %s", source.name, exc)
                record_source_result(source.name, False)
        return []

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "success": False,
            "source": "none",
            "flights": [],
            "cached": False,
            "message": "Không tìm thấy chuyến bay. Thử lại sau hoặc đổi ngày/tuyến.",
        }


def _dedupe_flights(flights: list[dict[str, Any]], limit: Optional[int] = None) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for f in sorted(flights, key=lambda x: x.get("price", 999_999_999)):
        key = (
            f.get("airline"),
            f.get("price"),
            (f.get("departure") or "")[:10],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
        if limit and len(unique) >= limit:
            break
    return unique
