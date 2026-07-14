"""Capacity and Zipf calculations shared by all SYSU workloads."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal


SIZE_MIB = (4, 8, 16, 32, 64)
FILES_PER_UNIT = (16, 8, 4, 2, 1)
UNIT_MIB = 320


@dataclass(frozen=True)
class Bucket:
    """One exact-size Vdbench FSD bucket."""

    name: str
    anchor: str
    files: int
    size_mib: int
    group: str

    @property
    def capacity_mib(self) -> int:
        return self.files * self.size_mib


def bucket_counts(units: int) -> dict[int, int]:
    """Return exact file counts for an integer number of 320 MiB units."""
    if units <= 0:
        raise ValueError("units must be positive")
    return {
        size: count * units
        for size, count in zip(SIZE_MIB, FILES_PER_UNIT)
    }


def make_buckets(*, prefix: str, anchor: str, units: int, group: str) -> list[Bucket]:
    """Expand a logical pool/rank into five equal-capacity size buckets."""
    counts = bucket_counts(units)
    return [
        Bucket(
            name=f"fsd_{prefix}_s{size}",
            anchor=f"{anchor}/size_{size}m",
            files=counts[size],
            size_mib=size,
            group=group,
        )
        for size in SIZE_MIB
    ]


def _normalize_nonzero_percentages(raw: list[float]) -> list[int]:
    if not raw or len(raw) > 100:
        raise ValueError("raw percentages must contain between 1 and 100 entries")

    result = [max(1, math.floor(value + 0.5)) for value in raw]
    while sum(result) > 100:
        candidates = [index for index, value in enumerate(result) if value > 1]
        if not candidates:
            raise ValueError("cannot normalize percentages without producing a zero")
        index = max(candidates, key=lambda item: result[item] - raw[item])
        result[index] -= 1
    while sum(result) < 100:
        index = max(range(len(result)), key=lambda item: raw[item] - result[item])
        result[index] += 1
    return result


def aggregate_zipf_percentages(
    object_count: int,
    rank_count: int,
    alpha: float,
) -> list[int]:
    """Aggregate an object-level Zipf distribution into equal-capacity ranks."""
    if object_count <= 0 or rank_count <= 0 or object_count % rank_count:
        raise ValueError("object_count must be positive and divisible by rank_count")
    if not math.isfinite(alpha) or alpha <= 0:
        raise ValueError("alpha must be a positive finite number")

    weights = [index ** (-alpha) for index in range(1, object_count + 1)]
    total = sum(weights)
    objects_per_rank = object_count // rank_count
    raw = [
        100.0
        * sum(weights[index * objects_per_rank : (index + 1) * objects_per_rank])
        / total
        for index in range(rank_count)
    ]
    return _normalize_nonzero_percentages(raw)


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def split_skew(weight: int | float, buckets: int = 5) -> list[str]:
    """Split one logical percentage equally without losing fractional skews."""
    if buckets <= 0:
        raise ValueError("buckets must be positive")
    value = Decimal(str(weight))
    if value <= 0:
        raise ValueError("weight must be positive")
    part = value / Decimal(buckets)
    return [_decimal_text(part)] * buckets
