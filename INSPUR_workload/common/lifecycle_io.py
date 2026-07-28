"""INSPUR-only adapters that add application lifecycle writes to shared models."""

from __future__ import annotations

import re
from pathlib import Path


def rewrite_phase(
    text: str,
    *,
    source: str,
    target: str,
    operation: str,
) -> str:
    if operation not in {"read", "write"}:
        raise ValueError(f"unsupported operation: {operation}")

    lines = text.splitlines()
    fwd_count = 0
    rd_count = 0
    for index, line in enumerate(lines):
        if line.startswith(f"fwd={source}_"):
            line = f"fwd={target}_{line.removeprefix(f'fwd={source}_')}"
            line, replacements = re.subn(
                r",operation=(?:read|write),",
                f",operation={operation},",
                line,
                count=1,
            )
            if replacements != 1:
                raise ValueError(f"FWD has no operation: {line}")
            lines[index] = line
            fwd_count += 1
        elif line.startswith(f"rd={source},"):
            line = f"rd={target},{line.removeprefix(f'rd={source},')}"
            line = line.replace(f",fwd={source}*", f",fwd={target}*", 1)
            lines[index] = line
            rd_count += 1

    if fwd_count == 0:
        raise ValueError(f"phase has no FWD definitions: {source}")
    if rd_count != 1:
        raise ValueError(f"phase must have exactly one RD definition: {source}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def clone_fwd_set(
    text: str,
    *,
    source: str,
    target: str,
    operation: str,
) -> str:
    if operation not in {"read", "write"}:
        raise ValueError(f"unsupported operation: {operation}")

    lines = text.splitlines()
    clones: list[str] = []
    last_fwd_index = -1
    for index, line in enumerate(lines):
        if line.startswith("fwd="):
            last_fwd_index = index
        if line.startswith(f"fwd={source}_"):
            clone = f"fwd={target}_{line.removeprefix(f'fwd={source}_')}"
            clone, replacements = re.subn(
                r",operation=(?:read|write),",
                f",operation={operation},",
                clone,
                count=1,
            )
            if replacements != 1:
                raise ValueError(f"FWD has no operation: {line}")
            clones.append(clone)

    if not clones or last_fwd_index < 0:
        raise ValueError(f"FWD set does not exist: {source}")
    if any(line.startswith(f"fwd={target}_") for line in lines):
        raise ValueError(f"target FWD set already exists: {target}")

    lines[last_fwd_index + 1 : last_fwd_index + 1] = clones
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def set_rd_selector(text: str, *, rd_name: str, fwd_set: str) -> str:
    lines = text.splitlines()
    matched = 0
    for index, line in enumerate(lines):
        if not line.startswith(f"rd={rd_name},"):
            continue
        line, replacements = re.subn(
            r",fwd=[^,]+",
            f",fwd={fwd_set}*",
            line,
            count=1,
        )
        if replacements != 1:
            raise ValueError(f"RD has no FWD selector: {rd_name}")
        lines[index] = line
        matched += 1
    if matched != 1:
        raise ValueError(f"RD must exist exactly once: {rd_name}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def update_run_config(path: Path, transform) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(transform(text), encoding="utf-8")
