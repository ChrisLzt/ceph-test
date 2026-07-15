from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re


def read_configs(output_dir: Path) -> tuple[str, str]:
    return (
        (output_dir / "prepare_data.vdb").read_text(encoding="utf-8"),
        (output_dir / "run_test.vdb").read_text(encoding="utf-8"),
    )


def fwd_definitions(text: str) -> dict[str, str]:
    return {
        line.split(",", 1)[0].split("=", 1)[1]: line
        for line in text.splitlines()
        if line.startswith("fwd=")
    }


def rd_definitions(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("rd=")]


def rd_fwd_names(line: str, definitions: dict[str, str] | None = None) -> list[str]:
    match = re.search(r",fwd=\(([^)]*)\)", line)
    if match:
        return match.group(1).split(",")
    selector = re.search(r",fwd=([^,]+)", line)
    if not selector:
        raise AssertionError(f"RD has no FWD selector: {line}")
    value = selector.group(1)
    if not value.endswith("*"):
        raise AssertionError(f"RD FWD selector is not a prefix wildcard: {line}")
    if definitions is None:
        raise AssertionError("FWD definitions are required to expand a wildcard selector")
    names = sorted(name for name in definitions if name.startswith(value[:-1]))
    if not names:
        raise AssertionError(f"RD wildcard selects no FWDs: {line}")
    return names


def skew_sum(run_text: str, rd_line: str) -> Decimal:
    fwds = fwd_definitions(run_text)
    result = Decimal("0")
    for name in rd_fwd_names(rd_line, fwds):
        match = re.search(r",skew=([^,]+)$", fwds[name])
        if not match:
            raise AssertionError(f"FWD has no skew: {fwds[name]}")
        result += Decimal(match.group(1))
    return result


def fsd_capacity_mib(text: str) -> int:
    total = 0
    for line in text.splitlines():
        if not line.startswith("fsd=fsd_"):
            continue
        files = int(re.search(r",files=(\d+)", line).group(1))
        size = int(re.search(r",size=(\d+)m", line).group(1))
        total += files * size
    return total


def assert_run_contract(
    testcase,
    run_text: str,
    *,
    expected_fwd_count: int | tuple[int, ...],
) -> None:
    expected_counts = (
        (expected_fwd_count,)
        if isinstance(expected_fwd_count, int)
        else expected_fwd_count
    )
    for line in fwd_definitions(run_text).values():
        testcase.assertIn("operation=read", line)
        testcase.assertIn("fileselect=random", line)
        testcase.assertIn("xfersize=4m", line)
        testcase.assertIn("threads=1", line)
    testcase.assertNotIn("operation=write", run_text)
    testcase.assertNotIn("format=", run_text)
    fwds = fwd_definitions(run_text)
    for rd in rd_definitions(run_text):
        rd_name = rd.split(",", 1)[0].split("=", 1)[1]
        testcase.assertIn("fwdrate=max", rd)
        testcase.assertIn(f",fwd={rd_name}*,", rd)
        matched_count = len(rd_fwd_names(rd, fwds))
        testcase.assertLessEqual(matched_count, 512)
        testcase.assertIn(matched_count, expected_counts)
        testcase.assertEqual(skew_sum(run_text, rd), Decimal("100"))
