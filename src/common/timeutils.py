"""Fechas en ISO 8601 UTC (formato 2026-11-12T15:30:00Z)."""

from datetime import datetime, timezone


def ahora_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
