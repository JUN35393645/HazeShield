from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

import requests

import app as domain


FEED_URL = os.environ.get("HAZESHIELD_FEED_URL", "").strip()
FEED_SOURCE = os.environ.get("HAZESHIELD_FEED_SOURCE", "UNVERIFIED_EXTERNAL").strip()
FEED_TOKEN = os.environ.get("HAZESHIELD_FEED_TOKEN", "").strip()
FEED_POLL_SECONDS = max(60, int(os.environ.get("HAZESHIELD_FEED_POLL_SECONDS", "300")))
_STATUS: dict[str, Any] = {"last_success_utc": None, "last_error": None, "imported": 0}


def status() -> dict[str, Any]:
    return {
        "configured": bool(FEED_URL),
        "source": FEED_SOURCE if FEED_URL else "not_configured",
        **_STATUS,
    }


def record_failure(error: Exception) -> None:
    _STATUS["last_error"] = str(error)


def poll_once() -> int:
    if not FEED_URL:
        return 0

    headers = {"Authorization": f"Bearer {FEED_TOKEN}"} if FEED_TOKEN else {}
    response = requests.get(FEED_URL, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("readings") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("Feed response must be a list or an object with a readings list")

    imported = 0
    with domain.connect() as db:
        zone_ids = {row["name"]: row["id"] for row in db.execute("SELECT id, name FROM zones")}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Each feed reading must be an object")
            zone_name = record.get("zone")
            zone_id = zone_ids.get(zone_name)
            if zone_id is None:
                raise ValueError(f"Feed reading refers to an unknown zone: {zone_name!r}")
            reading_date = date.fromisoformat(str(record.get("reading_date", "")))
            api_value = int(record["api_value"])
            if not 0 <= api_value <= 1000:
                raise ValueError("Feed api_value must be between 0 and 1000")
            cursor = db.execute(
                "INSERT INTO readings(zone_id, reading_date, api_value, source) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(zone_id, reading_date) DO UPDATE SET api_value=excluded.api_value, source=excluded.source",
                (zone_id, reading_date.isoformat(), api_value, FEED_SOURCE),
            )
            imported += cursor.rowcount

    _STATUS.update(
        last_success_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        last_error=None,
        imported=imported,
    )
    return imported
