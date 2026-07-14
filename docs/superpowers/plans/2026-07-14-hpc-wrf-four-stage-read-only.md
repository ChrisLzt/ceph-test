# HPC WRF Four-Stage Read-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `hpc_wrf_ior_v1` into a four-stage, read-only, Direct-I/O workload whose normal I/O runtime is approximately 600 seconds.

**Architecture:** Prepare three equal 36 GiB semantic pools once, then run four independent IOR read phases. The checkpoint pool is read in phases 2 and 4 so that the final phase is a measurable reheat; IOR combines a 150-second minimum runtime with a 150-second stonewall deadline to keep normal stage time close to 150 seconds.

**Tech Stack:** Bash, IOR POSIX backend, OpenMPI, Python validation scripts, Markdown.

## Global Constraints

- Formal test stages must contain reads only; prepare remains write-only.
- Use `NP=4`, file-per-process, POSIX Direct I/O, 1 MiB transfers, and three 36 GiB pools totaling 108 GiB.
- Run exactly four phases: `startup_read`, `checkpoint_read`, `history_read`, `checkpoint_reheat`.
- Each phase must use `-i 1 -D 150 -O minTimeDuration=150 -O stoneWallingWearOut=0`.
- Do not execute actual prepare or formal I/O against CephFS during implementation.
- Preserve unrelated dirty-worktree changes.

---

### Task 1: Express the four-stage model in validation

**Files:**
- Modify: `new_workload/hpc_wrf_ior_v1/tests/validate_hpc_workload.py`
- Test: `new_workload/hpc_wrf_ior_v1/tests/validate_hpc_workload.py`

**Interfaces:**
- Consumes: rendered Bash variables and literal IOR arguments.
- Produces: validation requirements used by the templates and renderer in Task 2.

- [ ] **Step 1: Replace eight-stage assertions with four-stage read-only assertions**

Require these exact phase calls:

```python
expected_calls = [
    'run_ior_read startup_read "$ANCHOR/startup/wrf_state"',
    'run_ior_read checkpoint_read "$ANCHOR/checkpoint/wrfrst_current"',
    'run_ior_read history_read "$ANCHOR/history/wrfout_current"',
    'run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"',
]
for call in expected_calls:
    if call not in run:
        fail(f"run script missing phase call: {call}")
if run.count("run_ior_read ") != 4:
    fail("rendered run should contain exactly four read phases")
if "run_ior_write" in run or re.search(r"(?:^|\s)-w(?:\s|$)", run):
    fail("formal run must be read-only")
```

Require the timing and Direct-I/O markers:

```python
for marker in [
    'PHASE_SECONDS="150"',
    '--posix.odirect',
    '-i 1',
    '-D "$PHASE_SECONDS"',
    '-O "minTimeDuration=$PHASE_SECONDS"',
    '-O stoneWallingWearOut=0',
]:
    if marker not in run:
        fail(f"rendered run missing timing/direct-I/O marker: {marker}")
```

Change prepare validation to require exactly three bases and no stale paths:

```python
if prepare.count("run_ior_write prepare_") != 3:
    fail("prepare script should create three WRF semantic file bases")
for stale in ["wrfinput_d01", "wrfbdy_d01", "wrfrst_initial", "wrfrst_old", "wrfout_old"]:
    if stale in prepare or stale in run:
        fail(f"scripts contain stale dataset: {stale}")
```

Update capacity calculation:

```python
file_bases = 3
total_gib = np * block_gib * segments * file_bases
if total_gib != 108:
    fail(f"total prepared capacity should be exactly 108 GiB, got {total_gib:.2f}")
```

- [ ] **Step 2: Run validation to verify RED**

Run:

```bash
cd /home/chris/ceph-test/new_workload/hpc_wrf_ior_v1
python3 tests/validate_hpc_workload.py
```

Expected: FAIL because the rendered scripts still contain seven prepared bases and eight formal phases.

---

### Task 2: Implement and render the read-only IOR workload

**Files:**
- Modify: `new_workload/hpc_wrf_ior_v1/configs/prepare_data.sh.in`
- Modify: `new_workload/hpc_wrf_ior_v1/configs/run_test.sh.in`
- Modify: `new_workload/hpc_wrf_ior_v1/render_config.sh`
- Generate: `new_workload/hpc_wrf_ior_v1/rendered/prepare_data.sh`
- Generate: `new_workload/hpc_wrf_ior_v1/rendered/run_test.sh`

**Interfaces:**
- Consumes: `ANCHOR`, `IOR_BIN`, `MPI_RUN`, `NP`, `API`, `BLOCK_SIZE`, `TRANSFER_SIZE`, `SEGMENT_COUNT`, `PHASE_SECONDS`.
- Produces: three prepared file bases and four read-only formal phases validated by Task 1.

- [ ] **Step 1: Reduce prepare to three semantic pools**

Keep the existing `run_ior_write()` helper with Direct I/O and replace its calls with:

```bash
run_ior_write prepare_startup_state "$ANCHOR/startup/wrf_state"
run_ior_write prepare_checkpoint_current "$ANCHOR/checkpoint/wrfrst_current"
run_ior_write prepare_history_current "$ANCHOR/history/wrfout_current"
```

Create only these directories:

```bash
mkdir -p "$ANCHOR/startup" "$ANCHOR/checkpoint" "$ANCHOR/history" "$OUTPUT_DIR"
```

- [ ] **Step 2: Replace run template with a single read helper and four calls**

The helper command must be:

```bash
"$MPI_RUN" -np "$NP" "$IOR_BIN" \
    -a "$API" --posix.odirect -F -r -k -C \
    -o "$target" \
    -b "$BLOCK_SIZE" \
    -t "$TRANSFER_SIZE" \
    -s "$SEGMENT_COUNT" \
    -i 1 \
    -D "$PHASE_SECONDS" \
    -O "minTimeDuration=$PHASE_SECONDS" \
    -O stoneWallingWearOut=0 \
    2>&1 | tee "$log"
```

The formal calls must be:

```bash
run_ior_read startup_read "$ANCHOR/startup/wrf_state"
run_ior_read checkpoint_read "$ANCHOR/checkpoint/wrfrst_current"
run_ior_read history_read "$ANCHOR/history/wrfout_current"
run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"
```

- [ ] **Step 3: Update renderer defaults and substitutions**

Use:

```bash
block_size=${BLOCK_SIZE:-9g}
phase_seconds=${PHASE_SECONDS:-150}
```

Remove `IOR_ITERATIONS`, validate `phase_seconds` as a positive integer, render `@PHASE_SECONDS@`, and report `phase=${phase_seconds}s` in the final profile line.

- [ ] **Step 4: Render both scripts**

Run:

```bash
cd /home/chris/ceph-test/new_workload/hpc_wrf_ior_v1
./render_config.sh all
```

Expected: both rendered scripts are regenerated with `BLOCK_SIZE="9g"` and the run script contains four 150-second read phases.

- [ ] **Step 5: Run validation to verify GREEN**

Run:

```bash
python3 tests/validate_hpc_workload.py
```

Expected:

```text
Total prepared capacity: 108.00 GiB
PASS: HPC WRF IOR workload is split into prepare-only and run-only scripts.
```

---

### Task 3: Synchronize workload documentation and verify the result

**Files:**
- Modify: `new_workload/hpc_wrf_ior_v1/README.md`
- Modify: `new_workload/hpc_wrf_ior_v1/SOURCES.md`
- Modify: `new_workload/WORKLOAD_SUMMARY.md`
- Modify: `new_workload/hpc_wrf_ior_v1/validate_model.sh` only if its existing commands do not cover all changed scripts.

**Interfaces:**
- Consumes: the final rendered parameters and phase names from Task 2.
- Produces: user-facing documentation that distinguishes official WRF file semantics from the engineering timing/capacity model.

- [ ] **Step 1: Update README and source boundaries**

Document exactly:

```text
3 pools × 36 GiB = 108 GiB
startup_read -> checkpoint_read -> history_read -> checkpoint_reheat
4 phases × about 150 seconds = slightly more than 10 minutes wall-clock
formal run is read-only; prepare writes data once
capacity equality and 150-second timing are engineering parameters, not WRF trace values
```

Remove references to write-hot stages, eight phases, 512 GiB fixed logical I/O, seven bases, `IOR_ITERATIONS=4`, and all deleted paths.

- [ ] **Step 2: Update the summary section**

Replace the HPC capacity and stage tables with the three pools and four read phases. State that checkpoint is first read in phase 2 and reheated in phase 4 after the 150-second history phase.

- [ ] **Step 3: Run all static verification**

Run:

```bash
cd /home/chris/ceph-test/new_workload/hpc_wrf_ior_v1
./validate_model.sh
bash -n render_config.sh prepare_data.sh run_test.sh validate_model.sh configs/prepare_data.sh.in configs/run_test.sh.in rendered/prepare_data.sh rendered/run_test.sh
python3 -m py_compile tests/validate_hpc_workload.py
cd /home/chris/ceph-test
git diff --check
```

Expected: all commands exit 0, validation reports 108.00 GiB and PASS, and `git diff --check` prints nothing.

- [ ] **Step 4: Confirm no stale workload markers remain**

Run:

```bash
rg -n "wrfinput_d01|wrfbdy_d01|wrfrst_initial|wrfrst_old|wrfout_old|IOR_ITERATIONS|checkpoint_write|history_write|8 次 IOR|512 GiB" \
  new_workload/hpc_wrf_ior_v1 \
  new_workload/WORKLOAD_SUMMARY.md
```

Expected: no matches outside historical design/plan documents.

- [ ] **Step 5: Review scope without running CephFS I/O**

Run:

```bash
git status --short -- new_workload/hpc_wrf_ior_v1 new_workload/WORKLOAD_SUMMARY.md
git diff --stat -- new_workload/hpc_wrf_ior_v1 new_workload/WORKLOAD_SUMMARY.md
```

Expected: only the intended HPC workload and the HPC portion of the summary are changed; no prepare or formal workload process has been started.
