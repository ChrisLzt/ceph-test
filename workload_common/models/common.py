"""Internal helpers for the five workload models."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable

from workload_common.layout import (
    SKEW_QUANTUM,
    Bucket,
    Layout,
    RankSpans,
    buckets_by_rank,
    make_rank_buckets,
    rank_bucket_skews,
)
from workload_common.vdbench import fwd_line, rd_line


Profile = dict[Bucket, Decimal]
CROSSFADE_STEPS = (
    ("25", Decimal("0.25")),
    ("50", Decimal("0.50")),
    ("75", Decimal("0.75")),
)
CROSSFADE_STEP_SECONDS = 10
CROSSFADE_SECONDS = len(CROSSFADE_STEPS) * CROSSFADE_STEP_SECONDS


def ranked_profile(
    layout: Layout,
    grouped: dict[int, list[Bucket]],
    group_units: int,
    rank_count: int,
    group_weight: Decimal | int | float | str,
    *,
    hot_rank: int = 1,
    rank_spans: RankSpans | None = None,
) -> Profile:
    """Expand rank/size Zipf skews into a bucket-addressable profile."""
    skews = rank_bucket_skews(
        layout,
        group_units,
        rank_count,
        group_weight,
        hot_rank=hot_rank,
        rank_spans=rank_spans,
    )
    return {
        bucket: Decimal(skews[rank][bucket.size_mib])
        for rank in sorted(grouped)
        for bucket in grouped[rank]
    }


def combine_profiles(*profiles: Profile) -> Profile:
    """Add one or more partial profiles, merging any shared buckets."""
    combined: Profile = {}
    for profile in profiles:
        for bucket, skew in profile.items():
            combined[bucket] = combined.get(bucket, Decimal("0")) + skew
    if any(value <= 0 for value in combined.values()):
        raise ValueError("profile skews must be positive")
    return combined


def blend_profiles(old: Profile, new: Profile, new_share: Decimal | str) -> Profile:
    """Crossfade two equally weighted profiles and preserve their exact sum."""
    progress = Decimal(str(new_share))
    if not Decimal("0") < progress < Decimal("1"):
        raise ValueError("new_share must be between zero and one")
    old_total = sum(old.values(), Decimal("0"))
    new_total = sum(new.values(), Decimal("0"))
    if old_total != new_total:
        raise ValueError("profiles must have the same total skew")
    raw = {
        bucket: (
            old.get(bucket, Decimal("0")) * (Decimal("1") - progress)
            + new.get(bucket, Decimal("0")) * progress
        )
        for bucket in sorted(set(old) | set(new), key=lambda item: item.name)
    }
    result = {
        bucket: value.quantize(SKEW_QUANTUM, rounding=ROUND_HALF_UP)
        for bucket, value in raw.items()
    }
    groups = {bucket.group for bucket in result}
    for group in groups:
        group_buckets = [bucket for bucket in result if bucket.group == group]
        target = sum(
            (value for bucket, value in raw.items() if bucket.group == group),
            Decimal("0"),
        )
        current = sum((result[bucket] for bucket in group_buckets), Decimal("0"))
        result[group_buckets[-1]] += target - current
    if any(value <= 0 for value in result.values()):
        raise ArithmeticError("crossfade produced a non-positive skew")
    return result


def skew_text(value: Decimal) -> str:
    """Format a decimal skew without exponent notation or trailing zeroes."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def append_profile_rd(
    lines: list[str],
    rds: list[str],
    *,
    name: str,
    profile: Profile,
    fileio: str | Callable[[Bucket], str],
    threads: int,
    fwdrate: str,
    elapsed: int,
    fwd_set_name: str | None = None,
    define_fwd: bool = True,
) -> None:
    """Emit a profile RD, optionally reusing an earlier FWD set."""
    if elapsed <= 0:
        raise ValueError("profile RD elapsed time must be positive")
    set_name = fwd_set_name or name
    names: list[str] = []
    for bucket in sorted(profile, key=lambda item: item.name):
        fwd_name = f"{set_name}_{bucket.name.removeprefix('fsd_')}"
        names.append(fwd_name)
        if define_fwd:
            bucket_fileio = fileio(bucket) if callable(fileio) else fileio
            lines.append(
                fwd_line(
                    name=fwd_name,
                    bucket=bucket,
                    operation="read",
                    fileio=bucket_fileio,
                    threads=threads,
                    skew=skew_text(profile[bucket]),
                )
            )
    if define_fwd:
        lines.append("")
    rds.append(
        rd_line(
            name=name,
            fwds=names,
            rate=fwdrate,
            elapsed=elapsed,
            fwd_set_name=set_name,
        )
    )


def append_crossfade_rds(
    lines: list[str],
    rds: list[str],
    *,
    old_name: str,
    old_profile: Profile,
    new_name: str,
    new_profile: Profile,
    fileio: str | Callable[[Bucket], str],
    threads: int,
    fwdrate: str,
) -> None:
    """Emit the standard 25/50/75% three-step hotspot crossfade."""
    for label, progress in CROSSFADE_STEPS:
        append_profile_rd(
            lines,
            rds,
            name=f"transition_{old_name}_to_{new_name}_{label}",
            profile=blend_profiles(old_profile, new_profile, progress),
            fileio=fileio,
            threads=threads,
            fwdrate=fwdrate,
            elapsed=CROSSFADE_STEP_SECONDS,
        )


def validate_render_args(
    *,
    anchor_root: str,
    threads: int,
    fwdrate: str,
    durations: tuple[int, ...],
) -> None:
    if not anchor_root.startswith("/"):
        raise ValueError("anchor_root must be an absolute path")
    if threads <= 0 or any(duration <= 0 for duration in durations):
        raise ValueError("threads and phase durations must be positive")
    if fwdrate != "max" and (not fwdrate.isdigit() or int(fwdrate) <= 0):
        raise ValueError("fwdrate must be max or a positive integer")


def make_group(
    *,
    layout: Layout,
    anchor_root: str,
    workload: str,
    group: str,
    prefix: str,
    units: int,
    ranks: int,
    rank_spans: RankSpans | None = None,
    anchor_suffix: str | None = None,
) -> tuple[list[Bucket], dict[int, list[Bucket]]]:
    suffix = anchor_suffix or group
    buckets = make_rank_buckets(
        layout=layout,
        prefix=prefix,
        anchor=f"{anchor_root.rstrip('/')}/{workload}/{suffix}",
        group=group,
        total_units=units,
        rank_count=ranks,
        rank_spans=rank_spans,
    )
    return buckets, buckets_by_rank(buckets)


def ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
