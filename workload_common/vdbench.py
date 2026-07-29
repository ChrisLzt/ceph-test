"""Deterministic Vdbench parameter-file emission."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Iterable

from .layout import Bucket


def config_header(
    title: str,
    *,
    hd_line: str | None = None,
    check_skew: bool = False,
) -> list[str]:
    lines = [
        f"* {title}",
        "* Generated from the shared file-level Zipf workload model.",
        "",
        "data_errors=1",
        "create_anchors=yes",
        "messagescan=no",
    ]
    if check_skew:
        lines.append("abort_failed_skew=2")
    if hd_line:
        lines.extend(["", hd_line])
    lines.append("")
    return lines


def render_fsd_lines(buckets: Iterable[Bucket]) -> list[str]:
    lines = ["fsd=default,depth=1,width=1,shared=yes,openflags=o_direct"]
    lines.extend(
        f"fsd={bucket.name},anchor={bucket.anchor},files={bucket.files},size={bucket.size_mib}m"
        for bucket in buckets
    )
    lines.append("")
    return lines


def render_prepare_config(
    title: str,
    buckets: list[Bucket],
    threads: int,
    *,
    hd_line: str | None = None,
    batch_rank_limit: int = 20,
) -> str:
    if threads <= 0 or batch_rank_limit <= 0:
        raise ValueError("threads and batch_rank_limit must be positive")
    lines = config_header(f"{title} - prepare only", hd_line=hd_line)
    lines.extend(render_fsd_lines(buckets))
    by_rank: OrderedDict[str, list[Bucket]] = OrderedDict()
    for bucket in buckets:
        by_rank.setdefault(bucket.rank_key, []).append(bucket)
    rank_keys = list(by_rank)
    fwd_lines = [
        "* Explicit format settings avoid version-dependent Vdbench defaults.",
        "fwd=format,threads=1,xfersize=4m",
    ]
    rd_lines: list[str] = []
    for batch_number, start in enumerate(range(0, len(rank_keys), batch_rank_limit), 1):
        names: list[str] = []
        for rank_key in rank_keys[start : start + batch_rank_limit]:
            for bucket in by_rank[rank_key]:
                name = f"prep_{bucket.name.removeprefix('fsd_')}"
                names.append(name)
                fwd_lines.append(
                    f"fwd={name},fsd={bucket.name},operation=read,threads={threads}"
                )
        joined = ",".join(names)
        rd_lines.extend(
            [
                f"rd=prepare_b{batch_number:03d}_clean,fwd=({joined}),format=(clean,only),fwdrate=max",
                f"rd=prepare_b{batch_number:03d}_create,fwd=({joined}),format=(restart,only),fwdrate=max",
            ]
        )
    lines.extend(fwd_lines)
    lines.append("")
    lines.extend(rd_lines)
    lines.append("")
    return "\n".join(lines)


def fwd_line(
    *,
    name: str,
    bucket: Bucket,
    operation: str,
    fileio: str,
    threads: int,
    skew: str,
    xfersize: str = "4m",
) -> str:
    return (
        f"fwd={name},fsd={bucket.name},operation={operation},fileio={fileio},"
        f"fileselect=random,xfersize={xfersize},threads={threads},skew={skew}"
    )


def rd_line(
    *,
    name: str,
    fwds: list[str],
    rate: str,
    elapsed: int,
    fwd_set_name: str | None = None,
) -> str:
    if not fwds:
        raise ValueError(f"RD {name} must select at least one FWD")
    selector = fwd_set_name or name
    prefix = f"{selector}_"
    mismatched = [fwd for fwd in fwds if not fwd.startswith(prefix)]
    if mismatched:
        raise ValueError(
            f"all FWD names for RD {name} must start with {prefix}: {mismatched[0]}"
        )
    return (
        f"rd={name},fwd={selector}*,fwdrate={rate},"
        f"elapsed={elapsed},interval=1"
    )


def write_config(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
