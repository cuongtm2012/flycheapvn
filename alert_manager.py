"""Trigger-based alert manager."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from api_router import APIRouter
from database import create_alert, get_active_alerts, update_alert_check

logger = logging.getLogger(__name__)

CHECK_COOLDOWN = timedelta(hours=1)
MAX_INCIDENTAL_CHECKS = 3


class AlertManager:
    def __init__(self, api_router: Optional[APIRouter] = None):
        self.api_router = api_router or APIRouter()

    def set_alert(
        self,
        user_id: int,
        origin: str,
        dest: str,
        max_price: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict[str, Any]:
        if not origin or not dest:
            return {"error": "Thiếu tuyến bay. VD: /theodoi HAN-SGN duoi 800k"}
        if not max_price or max_price <= 0:
            return {"error": "Thiếu mức giá. VD: /theodoi HAN-SGN duoi 800k"}

        alert_id = create_alert(
            user_id=user_id,
            origin=origin.upper(),
            dest=dest.upper(),
            max_price=max_price,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            "alert_id": alert_id,
            "origin": origin.upper(),
            "dest": dest.upper(),
            "max_price": max_price,
        }

    async def check_alerts(
        self,
        user_id: int,
        force: bool = False,
        route_filter: Optional[tuple[str, str]] = None,
    ) -> dict[str, Any]:
        alerts = get_active_alerts(user_id)
        if route_filter:
            o, d = route_filter
            alerts = [a for a in alerts if a["origin"] == o.upper() and a["dest"] == d.upper()]

        notifications = []
        now = datetime.utcnow()

        for alert in alerts:
            should_check = force
            if not should_check and alert.get("last_checked"):
                last = datetime.fromisoformat(alert["last_checked"])
                should_check = now - last >= CHECK_COOLDOWN
            elif not alert.get("last_checked"):
                should_check = True

            if not should_check:
                continue

            try:
                price = await self.api_router.quick_price(
                    alert["origin"],
                    alert["dest"],
                    alert.get("date_from"),
                )
            except Exception as exc:
                logger.exception("Alert check failed for #%s: %s", alert["id"], exc)
                continue

            update_alert_check(alert["id"], price)

            if price and price <= alert["max_price"]:
                last_notified = alert.get("last_notified_price")
                if not last_notified or price < last_notified:
                    notifications.append({
                        "alert_id": alert["id"],
                        "origin": alert["origin"],
                        "dest": alert["dest"],
                        "price": price,
                        "max_price": alert["max_price"],
                    })
                    update_alert_check(alert["id"], price, last_notified_price=price)

        refreshed = get_active_alerts(user_id)
        return {"alerts": refreshed, "notifications": notifications}

    async def incidental_check(self, user_id: int) -> list[dict[str, Any]]:
        """Check up to 3 active alerts when user sends any message."""
        alerts = get_active_alerts(user_id)[:MAX_INCIDENTAL_CHECKS]
        if not alerts:
            return []

        result = await self.check_alerts(user_id, force=False)
        return result.get("notifications", [])
