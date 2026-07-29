# Vdbench Wildcard, Validation, and IOR Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate Vdbench's 512-FWD RD parser failure, validate every generated configuration with Vdbench 5.04.07, and align the single-node IOR workload with the SYSU workload shape at single-node capacity.

**Architecture:** Run RDs select their phase FWDs through a deterministic `<rd_name>*` prefix wildcard, while prepare RDs retain bounded explicit lists. A shared Python validator performs structural checks and real `vdbench -s -e 2` parser simulations for both workload suites. The single-node IOR workload keeps the SYSU four-phase, four-rank, file-per-process design but scales each of its three pools to 37.5 GiB.

**Tech Stack:** Python 3 standard library, Bash, Vdbench 5.04.07, IOR, Open MPI, `unittest`.

## Global Constraints

- Preserve all existing workload semantics, Zipf weights, phase order, and 600-second formal run duration.
- Formal Vdbench run RDs must use an RD-name prefix wildcard; prepare RDs may use explicit lists of at most 512 FWDs.
- Validate all five single-node and all five SYSU Vdbench prepare/run configurations with `/home/chris/PDSL/vdbench/vdbench -s -e 2`.
- Single-node IOR must use `NP=4`, `-F`, `BLOCK_SIZE=9600m`, `TRANSFER_SIZE=4m`, three equal pools, four 150-second read phases, and Direct I/O.
- Preserve the existing SYSU IOR capacity and all unrelated user files, including `资料/`.

---

### Task 1: Replace explicit run FWD lists with prefix wildcards

**Files:**
- Modify: `workload_common/vdbench.py`
- Modify: `workload_common/tests/helpers.py`
- Modify: `workload_common/tests/test_vdbench.py`
- Modify: `workload_common/tests/test_mapreduce.py`

**Interfaces:**
- Consumes: `rd_line(name: str, fwds: list[str], rate: str, elapsed: int) -> str`.
- Produces: run RD lines with `fwd=<name>*`, after verifying every supplied FWD begins with `<name>_`.

- [ ] **Step 1: Write failing tests for wildcard emission and selector expansion**

Add tests that pass 600 phase FWD names to `rd_line`, require `fwd=phase*`, and reject a name outside the RD prefix. Update the shared contract helper to require and expand wildcard selectors against declared FWDs.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest workload_common.tests.test_vdbench -v`

Expected: failure because `rd_line` still emits an explicit parenthesized list.

- [ ] **Step 3: Implement prefix wildcard emission**

Validate that `fwds` is non-empty and each entry starts with `name + "_"`, then emit `rd=<name>,fwd=<name>*,...`. Leave prepare RD generation unchanged.

- [ ] **Step 4: Run shared model tests and verify GREEN**

Run: `python3 -m unittest discover -s workload_common/tests -v`

Expected: all shared model tests pass and every formal run RD expands to the same FWD set and skew sum as before.

### Task 2: Add real-tool validation for both suites

**Files:**
- Create: `workload_common/validate_vdbench.py`
- Create: `workload_common/tests/test_validation.py`
- Create: `SINGLE_workload/validate_all.sh`
- Modify: `SYSU_workload/validate_all.sh`
- Modify: `SYSU_workload/tests/test_suite.py`

**Interfaces:**
- Produces: `validate_run_text(text: str) -> None`, `validate_prepare_text(text: str) -> None`, and CLI `python3 -m workload_common.validate_vdbench <suite-root> --vdbench <executable>`.
- Consumes: five `rendered/prepare_data.vdb` and five `rendered/run_test.vdb` files under either suite root.

- [ ] **Step 1: Write failing structural-validator and suite-entry tests**

Require wildcard-only run RDs, a 600-second elapsed sum, 100-percent skew sums, bounded prepare FWD lists, and both top-level validation scripts invoking the shared validator.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest workload_common.tests.test_validation SYSU_workload.tests.test_suite -v`

Expected: failure because the shared module and single-node validation entry point do not exist.

- [ ] **Step 3: Implement structural and Vdbench simulation validation**

Parse FWD/RD declarations, expand prefix selectors, and report actionable errors. Simulate all ten configs per suite using isolated output directories and `vdbench -f <config> -o <dir> -s -e 2`.

- [ ] **Step 4: Integrate suite-level validation scripts**

Render the five formal workloads, run Python and shell checks, validate IOR, then invoke the shared real-tool validator.

- [ ] **Step 5: Verify both suites**

Run: `SINGLE_workload/validate_all.sh`

Run: `SYSU_workload/validate_all.sh`

Expected: model tests, shell syntax, IOR validation, structural checks, and all twenty Vdbench simulations pass.

### Task 3: Align the single-node IOR workload with SYSU semantics

**Files:**
- Modify: `SINGLE_workload/hpc_wrf_ior_v1/render_config.sh`
- Modify: `SINGLE_workload/hpc_wrf_ior_v1/tests/validate_hpc_workload.py`
- Modify: `SINGLE_workload/hpc_wrf_ior_v1/README.md`
- Regenerate: `SINGLE_workload/hpc_wrf_ior_v1/rendered/prepare_data.sh`
- Regenerate: `SINGLE_workload/hpc_wrf_ior_v1/rendered/run_test.sh`

**Interfaces:**
- Produces: three 37.5-GiB IOR pools and four 150-second Direct-I/O read phases.

- [ ] **Step 1: Change validator expectations and verify RED**

Require `BLOCK_SIZE="9600m"`, `TRANSFER_SIZE="4m"`, and exact total prepared capacity `112.5 GiB`.

- [ ] **Step 2: Update renderer defaults and regenerate scripts**

Set the defaults in `render_config.sh`, then run `SINGLE_workload/hpc_wrf_ior_v1/render_config.sh all`.

- [ ] **Step 3: Revise workload documentation**

Explain the 37.5-GiB pool calculation, 4-MiB transfer size, and that IOR and Vdbench are alternative HPC representations rather than additive datasets.

- [ ] **Step 4: Verify the IOR model**

Run: `SINGLE_workload/hpc_wrf_ior_v1/validate_model.sh`

Expected: exact 112.50-GiB capacity and all phase/direct-I/O checks pass.

### Task 4: Regenerate, document, and perform final regression

**Files:**
- Regenerate: `SINGLE_workload/*_vdbench_v1/rendered/*.vdb`
- Regenerate: `SYSU_workload/*_vdbench_v1/rendered/*.vdb`
- Modify: `SINGLE_workload/README.md`
- Modify: `SYSU_workload/README.md`

- [ ] **Step 1: Render all five workloads in both suites**

Use the existing workload renderers; for SYSU use `ANCHOR_ROOT=/__SYSU_CEPHFS__` so validation never touches production data.

- [ ] **Step 2: Verify every run RD and duration**

Run a repository scan requiring wildcard selectors and exactly 600 seconds per formal run config.

- [ ] **Step 3: Run complete validation**

Run both `validate_all.sh` scripts, `git diff --check`, and Bash syntax validation over both suite trees.

- [ ] **Step 4: Review the final diff**

Confirm the SYSU IOR workload and unrelated user files are unchanged, while generated configs and documentation match their source models.
