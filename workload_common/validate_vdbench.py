"""Structural and real-parser validation for generated Vdbench workloads."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import subprocess
import tempfile


FORMAL_WORKLOADS = (
    "bigdata_mapreduce_vdbench_v1",
    "graph_graphchi_vdbench_v1",
    "hpc_wrf_vdbench_v1",
    "ai_training_checkpoint_vdbench_v1",
    "ai_inference_kvcache_vdbench_v1",
)
MAX_EXPLICIT_FWDS = 512
FORMAL_ELAPSED_SECONDS = 600


class ConfigValidationError(ValueError):
    """Raised when a generated Vdbench parameter file violates its contract."""


def _named_lines(text: str, prefix: str) -> dict[str, str]:
    definitions: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        name = line.split(",", 1)[0].split("=", 1)[1]
        if name in definitions:
            raise ConfigValidationError(f"duplicate {prefix[:-1].upper()} name: {name}")
        definitions[name] = line
    return definitions


def _parameter(line: str, name: str) -> str:
    match = re.search(rf"(?:^|,){re.escape(name)}=([^,]+)", line)
    if not match:
        raise ConfigValidationError(f"missing {name}= in line: {line}")
    return match.group(1)


def _explicit_fwd_names(line: str) -> list[str]:
    match = re.search(r",fwd=\(([^)]*)\)", line)
    if not match:
        raise ConfigValidationError(f"RD must use an explicit FWD list: {line}")
    names = [name for name in match.group(1).split(",") if name]
    if not names:
        raise ConfigValidationError(f"RD has an empty FWD list: {line}")
    return names


def validate_prepare_text(text: str) -> None:
    """Validate bounded explicit FWD lists used only for data creation."""
    fwds = _named_lines(text, "fwd=")
    rds = _named_lines(text, "rd=")
    if not fwds or not rds:
        raise ConfigValidationError("prepare config must declare FWDs and RDs")
    for rd_name, line in rds.items():
        names = _explicit_fwd_names(line)
        if len(names) > MAX_EXPLICIT_FWDS:
            raise ConfigValidationError(
                f"prepare RD {rd_name} has {len(names)} explicit FWDs; maximum is {MAX_EXPLICIT_FWDS}"
            )
        missing = [name for name in names if name not in fwds]
        if missing:
            raise ConfigValidationError(
                f"prepare RD {rd_name} references undefined FWD: {missing[0]}"
            )


def validate_run_text(text: str) -> None:
    """Validate wildcard selection, skew totals, and formal run duration."""
    fwds = _named_lines(text, "fwd=")
    rds = _named_lines(text, "rd=")
    if not fwds or not rds:
        raise ConfigValidationError("run config must declare FWDs and RDs")
    elapsed_total = 0
    selected: set[str] = set()
    for rd_name, line in rds.items():
        if ",fwd=(" in line:
            raise ConfigValidationError(
                f"run RD {rd_name} must use its prefix wildcard, not an explicit FWD list"
            )
        selector = _parameter(line, "fwd")
        if not selector.endswith("*") or selector.count("*") != 1:
            raise ConfigValidationError(
                f"run RD {rd_name} must use one trailing prefix wildcard, got {selector}"
            )
        # Match Vdbench's literal prefix wildcard semantics exactly.  Do not
        # assume an underscore boundary: ``phase*`` also selects ``phase2_*``.
        prefix = selector[:-1]
        names = sorted(name for name in fwds if name.startswith(prefix))
        if not names:
            raise ConfigValidationError(f"run RD {rd_name} wildcard selects no FWDs")
        if len(names) > MAX_EXPLICIT_FWDS:
            raise ConfigValidationError(
                f"run RD {rd_name} matches {len(names)} FWDs; maximum is {MAX_EXPLICIT_FWDS}"
            )
        selected.update(names)
        skew_total = Decimal("0")
        for name in names:
            try:
                skew_total += Decimal(_parameter(fwds[name], "skew"))
            except InvalidOperation as error:
                raise ConfigValidationError(f"invalid skew for FWD {name}") from error
        if skew_total != Decimal("100"):
            raise ConfigValidationError(
                f"run RD {rd_name} skew total is {skew_total}, expected 100"
            )
        try:
            elapsed = int(_parameter(line, "elapsed"))
        except ValueError as error:
            raise ConfigValidationError(f"invalid elapsed value in RD {rd_name}") from error
        if elapsed <= 0:
            raise ConfigValidationError(f"run RD {rd_name} elapsed must be positive")
        elapsed_total += elapsed
    unselected = sorted(set(fwds) - selected)
    if unselected:
        raise ConfigValidationError(f"run FWD is not selected by any RD: {unselected[0]}")
    if elapsed_total != FORMAL_ELAPSED_SECONDS:
        raise ConfigValidationError(
            f"formal run totals {elapsed_total}s, expected {FORMAL_ELAPSED_SECONDS}s"
        )


def _validate_config_files(suite_root: Path) -> list[Path]:
    configs: list[Path] = []
    for workload in FORMAL_WORKLOADS:
        prepare = suite_root / workload / "rendered" / "prepare_data.vdb"
        run = suite_root / workload / "rendered" / "run_test.vdb"
        for path in (prepare, run):
            if not path.is_file():
                raise ConfigValidationError(f"missing generated config: {path}")
        validate_prepare_text(prepare.read_text(encoding="utf-8"))
        validate_run_text(run.read_text(encoding="utf-8"))
        configs.extend((prepare, run))
    return configs


def _simulate(vdbench: Path, config: Path, output_dir: Path) -> tuple[Path, str]:
    result = subprocess.run(
        [str(vdbench), "-f", str(config), "-o", str(output_dir), "-s", "-e", "2"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=120,
    )
    if result.returncode:
        tail = "\n".join(result.stdout.splitlines()[-30:])
        raise ConfigValidationError(
            f"Vdbench simulation failed for {config} (exit {result.returncode}):\n{tail}"
        )
    return config, result.stdout


def validate_suite(suite_root: Path, vdbench: Path, jobs: int = 4) -> None:
    """Validate and simulate all five formal Vdbench workloads in a suite."""
    suite_root = suite_root.resolve()
    vdbench = vdbench.resolve()
    if not vdbench.is_file() or not os.access(vdbench, os.X_OK):
        raise ConfigValidationError(f"Vdbench executable is missing or not executable: {vdbench}")
    if jobs <= 0:
        raise ConfigValidationError("jobs must be positive")
    configs = _validate_config_files(suite_root)
    with tempfile.TemporaryDirectory(prefix="vdbench-validate-") as tmp:
        base = Path(tmp)
        with ThreadPoolExecutor(max_workers=min(jobs, len(configs))) as executor:
            futures = {
                executor.submit(_simulate, vdbench, config, base / f"job_{index:02d}"): config
                for index, config in enumerate(configs, 1)
            }
            for future in as_completed(futures):
                config, _ = future.result()
                print(f"PASS: Vdbench parsed {config.relative_to(suite_root)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate generated Vdbench workloads structurally and with vdbench -s."
    )
    parser.add_argument("suite_root", type=Path)
    parser.add_argument(
        "--vdbench",
        type=Path,
        default=Path(os.environ.get("VDBENCH_HOME", "/home/chris/PDSL/vdbench")) / "vdbench",
    )
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    try:
        validate_suite(args.suite_root, args.vdbench, args.jobs)
    except (ConfigValidationError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"FAIL: {error}\n")
    print(f"PASS: validated all formal Vdbench configs in {args.suite_root}")


if __name__ == "__main__":
    main()
