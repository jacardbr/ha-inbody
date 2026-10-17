"""Pure helpers for turning scans into hourly statistics (no HA imports)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any


def hourly_points(
    scans: Iterable[Any], value_fn: Callable[[Any], float | None]
) -> list[tuple[datetime, float]]:
    """Bucket scans into UTC hours, oldest first.

    Scans without a timestamp or without a value are skipped. When several
    scans fall in the same hour the latest one wins.
    """
    buckets: dict[datetime, float] = {}
    dated = sorted(
        (s for s in scans if getattr(s, "taken_at", None) is not None),
        key=lambda s: s.taken_at,
    )
    for scan in dated:
        value = value_fn(scan)
        if value is None:
            continue
        start = scan.taken_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        buckets[start] = value
    return sorted(buckets.items())
