"""Discover the extra metrics the InBody API returns (no Home Assistant imports).

The API answers every scan with two blocks of fields, `BCA` and `MFA`. The
sensors for the most useful ones are declared by hand in sensor.py; every other
numeric field found in those blocks becomes an extra sensor, created disabled
by default so the entity list is not flooded.
"""

from __future__ import annotations

import math
import re
from typing import Any, NamedTuple

# (block, key) pairs that already have a dedicated sensor in sensor.py.
HANDLED: frozenset[tuple[str, str]] = frozenset(
    {
        ("bca", "WT"),
        ("bca", "BFM"),
        ("bca", "TBW"),
        ("mfa", "BMI"),
        ("mfa", "PBF"),
        ("mfa", "SMM"),
    }
)

# Fields that are identifiers, timestamps or versions rather than measurements.
_SKIP = re.compile(r"(DATE|TIME|UID|SEQ|SERIAL|^ID$|_ID$|MAC|VERSION)", re.IGNORECASE)

# Well-known InBody abbreviations: key -> (name, unit). Anything not listed is
# still exposed, named after its raw key and without a unit.
KNOWN: dict[str, tuple[str, str | None]] = {
    "ICW": ("Intracellular water", "kg"),
    "ECW": ("Extracellular water", "kg"),
    "PROTEIN": ("Protein mass", "kg"),
    "MINERAL": ("Mineral mass", "kg"),
    "BMC": ("Bone mineral content", "kg"),
    "FFM": ("Fat-free mass", "kg"),
    "LBM": ("Lean body mass", "kg"),
    "SLM": ("Soft lean mass", "kg"),
    "DLM": ("Dry lean mass", "kg"),
    "BMR": ("Basal metabolic rate", "kcal"),
    "VFL": ("Visceral fat level", None),
    "VFA": ("Visceral fat area", "cm²"),
    "WHR": ("Waist-hip ratio", None),
    "ECWTBW": ("ECW/TBW ratio", None),
    "ECW/TBW": ("ECW/TBW ratio", None),
    "SCORE": ("InBody score", "points"),
}

# Other spellings seen for the same measurement (compared after removing
# everything that is not a letter or a digit).
_ALIASES: dict[str, str] = {
    "INBODYSCORE": "SCORE",
    "BODYSCORE": "SCORE",
    "INBODYPOINT": "SCORE",
    "INBODYPOINTS": "SCORE",
    "VFLEVEL": "VFL",
    "VISCERALFATLEVEL": "VFL",
    "VISCERALFAT": "VFL",
    "WAISTHIPRATIO": "WHR",
    "WHRATIO": "WHR",
    "BASALMETABOLICRATE": "BMR",
    "BMRKCAL": "BMR",
    "ECWTBW": "ECW/TBW",
}

# Extras that are enabled right away; all the others start disabled.
FEATURED: frozenset[str] = frozenset({"SCORE", "VFL", "WHR", "BMR"})


def canonical(key: str) -> str:
    """Canonical KNOWN key for a raw API key, or the upper-cased key itself."""
    upper = key.upper()
    if upper in KNOWN:
        return upper
    squashed = re.sub(r"[^A-Z0-9]", "", upper)
    return _ALIASES.get(squashed, upper)


class ExtraMetric(NamedTuple):
    """One extra numeric field of the BCA or MFA block."""

    block: str  # "bca" or "mfa"
    path: tuple[str, ...]  # key, or nested keys, inside the block
    slug: str  # stable id, e.g. "bca_icw"
    name: str
    unit: str | None
    featured: bool = False  # enabled by default


def _slug(block: str, path: tuple[str, ...]) -> str:
    raw = "_".join((block, *path)).lower()
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _walk(block: dict[str, Any], prefix: tuple[str, ...] = ()):
    """Yield (path, value) for every leaf of a block; lists are ignored."""
    for key, value in block.items():
        path = (*prefix, str(key))
        if isinstance(value, dict):
            if len(path) < 3:
                yield from _walk(value, path)
        elif not isinstance(value, list):
            yield path, value


def extra_metrics(bca: dict[str, Any], mfa: dict[str, Any]) -> list[ExtraMetric]:
    """Numeric fields of a scan that have no dedicated sensor, sorted by id."""
    found: dict[str, ExtraMetric] = {}
    for block, data in (("bca", bca or {}), ("mfa", mfa or {})):
        if not isinstance(data, dict):
            continue
        for path, value in _walk(data):
            if (block, path[0]) in HANDLED and len(path) == 1:
                continue
            if any(_SKIP.search(part) for part in path):
                continue
            if _number(value) is None:
                continue
            leaf = path[-1]
            key = canonical(leaf) if len(path) == 1 else leaf.upper()
            known = KNOWN.get(key) if len(path) == 1 else None
            name = known[0] if known else f"{block.upper()} {'.'.join(path)}"
            unit = known[1] if known else None
            slug = _slug(block, path)
            found.setdefault(slug, ExtraMetric(block, path, slug, name, unit, key in FEATURED))
    return [found[key] for key in sorted(found)]


def read_metric(bca: dict[str, Any], mfa: dict[str, Any], metric: ExtraMetric) -> float | None:
    """Current value of an extra metric in a scan, or None if it is not there."""
    node: Any = (bca if metric.block == "bca" else mfa) or {}
    for part in metric.path:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return _number(node)
