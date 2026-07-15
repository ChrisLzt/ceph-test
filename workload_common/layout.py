"""Physical capacity layouts and file-level Zipf aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from functools import lru_cache
import math


getcontext().prec = 40
ZIPF_ALPHA = 0.99
SKEW_QUANTUM = Decimal("0.000000000001")


@dataclass(frozen=True)
class Layout:
    """One physical representation of a shared logical capacity unit."""

    name: str
    sizes_mib: tuple[int, ...]
    files_per_unit: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.sizes_mib or len(self.sizes_mib) != len(self.files_per_unit):
            raise ValueError("sizes_mib and files_per_unit must be non-empty and aligned")
        if any(value <= 0 for value in self.sizes_mib + self.files_per_unit):
            raise ValueError("layout values must be positive")
        capacities = {
            size * files
            for size, files in zip(self.sizes_mib, self.files_per_unit)
        }
        if len(capacities) != 1:
            raise ValueError("each fixed-size class must contribute equal capacity")

    @property
    def unit_mib(self) -> int:
        return sum(
            size * files
            for size, files in zip(self.sizes_mib, self.files_per_unit)
        )

    def capacity_mib(self, units: int) -> int:
        if units <= 0:
            raise ValueError("units must be positive")
        return units * self.unit_mib

    def files_for_units(self, units: int) -> dict[int, int]:
        if units <= 0:
            raise ValueError("units must be positive")
        return {
            size: units * files
            for size, files in zip(self.sizes_mib, self.files_per_unit)
        }


SINGLE_LAYOUT = Layout(
    name="single",
    sizes_mib=(4, 8, 16),
    files_per_unit=(4, 2, 1),
)
SYSU_LAYOUT = Layout(
    name="sysu",
    sizes_mib=(4, 8, 16, 32, 64),
    files_per_unit=(16, 8, 4, 2, 1),
)


@dataclass(frozen=True)
class Bucket:
    """One exact-size Vdbench FSD belonging to one logical heat rank."""

    name: str
    anchor: str
    files: int
    size_mib: int
    group: str
    rank: int
    rank_key: str

    @property
    def capacity_mib(self) -> int:
        return self.files * self.size_mib


def make_rank_buckets(
    *,
    layout: Layout,
    prefix: str,
    anchor: str,
    group: str,
    total_units: int,
    rank_count: int,
) -> list[Bucket]:
    """Split a logical group into equal-capacity ranks and size buckets."""
    if total_units <= 0 or rank_count <= 0 or total_units % rank_count:
        raise ValueError("total_units must be positive and divisible by rank_count")
    units_per_rank = total_units // rank_count
    counts = layout.files_for_units(units_per_rank)
    buckets: list[Bucket] = []
    for rank in range(1, rank_count + 1):
        rank_key = f"{group}:{rank:03d}"
        for size in layout.sizes_mib:
            buckets.append(
                Bucket(
                    name=f"fsd_{prefix}_r{rank:03d}_s{size}",
                    anchor=f"{anchor.rstrip('/')}/rank_{rank:03d}/size_{size}m",
                    files=counts[size],
                    size_mib=size,
                    group=group,
                    rank=rank,
                    rank_key=rank_key,
                )
            )
    return buckets


@lru_cache(maxsize=None)
def _zipf_rank_profile(
    file_count: int,
    rank_count: int,
    alpha: float,
) -> tuple[float, ...]:
    if file_count <= 0 or rank_count <= 0 or file_count % rank_count:
        raise ValueError("file_count must be positive and divisible by rank_count")
    if not math.isfinite(alpha) or alpha <= 0:
        raise ValueError("alpha must be a positive finite number")
    per_rank = file_count // rank_count
    weights = [index ** (-alpha) for index in range(1, file_count + 1)]
    total = math.fsum(weights)
    return tuple(
        math.fsum(weights[start : start + per_rank]) / total
        for start in range(0, file_count, per_rank)
    )


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def rank_bucket_skews(
    layout: Layout,
    group_units: int,
    rank_count: int,
    group_weight: Decimal | int | float | str,
    *,
    hot_rank: int = 1,
    alpha: float = ZIPF_ALPHA,
) -> dict[int, dict[int, str]]:
    """Return exact decimal FWD skews for one ranked logical group.

    Every fixed-size class receives an equal share of ``group_weight`` and
    independently follows Zipf(alpha). Popularity rank one is mapped to
    ``hot_rank`` and the remaining popularity ranks wrap around physically.
    """
    if group_units <= 0 or rank_count <= 0 or group_units % rank_count:
        raise ValueError("group_units must be positive and divisible by rank_count")
    if not 1 <= hot_rank <= rank_count:
        raise ValueError("hot_rank must be within rank_count")
    target = Decimal(str(group_weight))
    if target <= 0:
        raise ValueError("group_weight must be positive")

    result: dict[int, dict[int, Decimal]] = {
        rank: {} for rank in range(1, rank_count + 1)
    }
    size_share = target / Decimal(len(layout.sizes_mib))
    ordered: list[tuple[int, int]] = []
    for size, files_per_unit in zip(layout.sizes_mib, layout.files_per_unit):
        profile = _zipf_rank_profile(group_units * files_per_unit, rank_count, alpha)
        for popularity_index, probability in enumerate(profile):
            physical_rank = ((hot_rank - 1 + popularity_index) % rank_count) + 1
            value = (size_share * Decimal(str(probability))).quantize(
                SKEW_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
            result[physical_rank][size] = value
            ordered.append((physical_rank, size))

    current = sum(value for ranks in result.values() for value in ranks.values())
    correction_rank, correction_size = ordered[-1]
    result[correction_rank][correction_size] += target - current
    if result[correction_rank][correction_size] <= 0:
        raise ArithmeticError("rounding correction produced a non-positive skew")
    return {
        rank: {size: _decimal_text(value) for size, value in by_size.items()}
        for rank, by_size in result.items()
    }


def equal_decimal_shares(
    total: Decimal | int | float | str,
    count: int,
) -> tuple[Decimal, ...]:
    """Split a total into positive 12-decimal shares with an exact sum."""
    target = Decimal(str(total))
    if target <= 0 or count <= 0:
        raise ValueError("total and count must be positive")
    part = (target / Decimal(count)).quantize(SKEW_QUANTUM, rounding=ROUND_HALF_UP)
    shares = [part] * count
    shares[-1] += target - sum(shares)
    if shares[-1] <= 0:
        raise ArithmeticError("rounding correction produced a non-positive share")
    return tuple(shares)


def buckets_by_rank(buckets: list[Bucket]) -> dict[int, list[Bucket]]:
    """Index buckets by their physical rank while preserving size order."""
    grouped: dict[int, list[Bucket]] = {}
    for bucket in buckets:
        grouped.setdefault(bucket.rank, []).append(bucket)
    return grouped
