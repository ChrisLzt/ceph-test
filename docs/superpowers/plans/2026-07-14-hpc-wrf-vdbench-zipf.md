# WRF-derived Vdbench Zipf Workload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent `hpc_wrf_vdbench_v1` workload with three WRF data groups, object-derived Zipf(0.99) rank weights, four read-only phases, and checkpoint reheat while preserving `hpc_wrf_ior_v1`.

**Architecture:** A Python derivation script computes the 20-rank Zipf profile and generates complete prepare/run Vdbench templates. A shell renderer substitutes server and scale parameters, wrapper scripts separate data creation from testing, and an independent Python validator checks capacity, phase semantics, skew, read-only behavior, and IOR coexistence.

**Tech Stack:** Python 3 standard library, Bash, Vdbench 5.04.07 configuration files, Markdown.

## Global Constraints

- Create `new_workload/hpc_wrf_vdbench_v1`; do not modify or delete `new_workload/hpc_wrf_ior_v1`.
- Use the independent anchor `/mnt/cephfs/hpc_wrf_vdbench_v1`.
- Model exactly three groups: startup, checkpoint, history.
- Split each group into 20 equal ranks, each with 120 files of 16 MiB.
- Total capacity is 112.5 GiB.
- Derive rank weights from 9600 objects per group with Zipf alpha 0.99 and emit `68/7/4/3/2/2/1x14` with no zero-weight rank.
- Run four 150-second, read-only phases with 1 MiB sequential I/O, Direct I/O, and `fwdrate=max`.
- Reheat the same checkpoint ranks with the same weight order in phase four.
- Do not run prepare or formal tests against `/mnt/cephfs` during implementation.
- Preserve unrelated dirty-worktree changes.

---

### Task 1: Zipf Derivation and Template Generator

**Files:**
- Create: `new_workload/hpc_wrf_vdbench_v1/tests/test_derive_zipf_profile.py`
- Create: `new_workload/hpc_wrf_vdbench_v1/scripts/derive_zipf_profile.py`

**Interfaces:**
- Produces: `aggregate_zipf_percentages(object_count: int, rank_count: int, alpha: float) -> list[int]`.
- Produces CLI options `--prepare-template`, `--run-template`, `--rank-count`, `--objects-per-rank`, and `--alpha`.
- Generates complete templates consumed by `render_config.sh` in Task 2.

- [ ] **Step 1: Write failing unit tests for the profile**

```python
from scripts.derive_zipf_profile import aggregate_zipf_percentages


def test_default_profile_is_nonzero_and_sums_to_100():
    assert aggregate_zipf_percentages(9600, 20, 0.99) == [
        68, 7, 4, 3, 2, 2,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    ]
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run:

```bash
python3 -m unittest discover -s new_workload/hpc_wrf_vdbench_v1/tests -p 'test_*.py' -v
```

Expected: FAIL because `scripts.derive_zipf_profile` does not exist.

- [ ] **Step 3: Implement deterministic Zipf aggregation**

Implement these functions in `derive_zipf_profile.py`:

```python
def zipf_object_shares(object_count: int, alpha: float) -> list[float]:
    weights = [index ** (-alpha) for index in range(1, object_count + 1)]
    total = sum(weights)
    return [weight * 100.0 / total for weight in weights]


def normalize_nonzero_percentages(raw: list[float]) -> list[int]:
    result = [max(1, math.floor(value + 0.5)) for value in raw]
    while sum(result) > 100:
        candidates = [i for i, value in enumerate(result) if value > 1]
        index = max(candidates, key=lambda i: result[i] - raw[i])
        result[index] -= 1
    while sum(result) < 100:
        index = max(range(len(result)), key=lambda i: raw[i] - result[i])
        result[index] += 1
    return result


def aggregate_zipf_percentages(object_count: int, rank_count: int, alpha: float) -> list[int]:
    if object_count <= 0 or rank_count <= 0 or object_count % rank_count:
        raise ValueError("object_count must be positive and divisible by rank_count")
    shares = zipf_object_shares(object_count, alpha)
    objects_per_rank = object_count // rank_count
    raw = [
        sum(shares[index * objects_per_rank:(index + 1) * objects_per_rank])
        for index in range(rank_count)
    ]
    return normalize_nonzero_percentages(raw)
```

Generate 60 FSDs, 60 prepare FWDs, 80 run FWDs, and four RDs. Use groups `startup`, `checkpoint`, `history` and phase mapping:

```python
PHASES = (
    ("startup_read", "startup"),
    ("checkpoint_read", "checkpoint"),
    ("history_read", "history"),
    ("checkpoint_reheat", "checkpoint"),
)
```

- [ ] **Step 4: Run unit tests**

Expected: all Zipf derivation and generated-template tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add new_workload/hpc_wrf_vdbench_v1/scripts new_workload/hpc_wrf_vdbench_v1/tests/test_derive_zipf_profile.py
git commit -m "feat: derive WRF vdbench Zipf profile"
```

### Task 2: Rendering, Wrappers, and Model Validation

**Files:**
- Create: `new_workload/hpc_wrf_vdbench_v1/configs/prepare_data.vdb.in`
- Create: `new_workload/hpc_wrf_vdbench_v1/configs/run_test.vdb.in`
- Create: `new_workload/hpc_wrf_vdbench_v1/rendered/prepare_data.vdb`
- Create: `new_workload/hpc_wrf_vdbench_v1/rendered/run_test.vdb`
- Create: `new_workload/hpc_wrf_vdbench_v1/render_config.sh`
- Create: `new_workload/hpc_wrf_vdbench_v1/prepare_data.sh`
- Create: `new_workload/hpc_wrf_vdbench_v1/run_test.sh`
- Create: `new_workload/hpc_wrf_vdbench_v1/validate_model.sh`
- Create: `new_workload/hpc_wrf_vdbench_v1/tests/validate_hpc_vdbench_workload.py`

**Interfaces:**
- `render_config.sh [all|prepare|run]` renders generated templates.
- `prepare_data.sh` renders and executes only `rendered/prepare_data.vdb`.
- `run_test.sh` renders and executes only `rendered/run_test.vdb`.
- `validate_model.sh` renders both files and runs static validation.

- [ ] **Step 1: Write the failing integration validator**

The validator must require all listed files, parse all FSD/FWD/RD lines, and assert:

```python
EXPECTED_WEIGHTS = [68, 7, 4, 3, 2, 2] + [1] * 14
EXPECTED_PHASES = [
    "startup_read",
    "checkpoint_read",
    "history_read",
    "checkpoint_reheat",
]
```

It must calculate capacity as:

```python
total_gib = 3 * 20 * 120 * 16 / 1024
assert total_gib == 112.5
```

It must reject `operation=write`, `format=` in run configs, unresolved tokens, multi-host definitions, old anchors, zero skew, non-150-second phases, non-`max` rates, and mismatched checkpoint reheat weights.

- [ ] **Step 2: Run the validator and verify missing configuration failure**

Run:

```bash
python3 new_workload/hpc_wrf_vdbench_v1/tests/validate_hpc_vdbench_workload.py
```

Expected: FAIL with missing `configs/prepare_data.vdb.in`.

- [ ] **Step 3: Implement rendering and wrappers**

Use these defaults in `render_config.sh`:

```bash
anchor=${ANCHOR:-/mnt/cephfs/hpc_wrf_vdbench_v1}
vdbench_home=${VDBENCH_HOME:-/home/chris/PDSL/vdbench}
remote_user=${REMOTE_USER:-chris}
host1=${HOST1:-s52.servers.hustpdsl.cn}
phase_seconds=${PHASE_SECONDS:-150}
fwd_rate=${FWD_RATE:-max}
threads=${THREADS:-4}
format_threads=${FORMAT_THREADS:-8}
files_per_rank=${FILES_PER_RANK:-120}
file_size=${FILE_SIZE:-16m}
xfer_size=${XFER_SIZE:-1m}
rank_count=${RANK_COUNT:-20}
objects_per_rank=${OBJECTS_PER_RANK:-480}
zipf_alpha=${ZIPF_ALPHA:-0.99}
```

Run `derive_zipf_profile.py` before scalar token replacement. Reject invalid positive integers, invalid Vdbench sizes, a rank count other than 20, an object count that does not equal 9600, and unresolved `@[A-Z_]+@` tokens.

Use wrapper commands:

```bash
"$vdbench_home/vdbench" -f rendered/prepare_data.vdb -o "$output_dir"
"$vdbench_home/vdbench" -f rendered/run_test.vdb -o "$output_dir"
```

- [ ] **Step 4: Render and run static validation**

Run:

```bash
cd new_workload/hpc_wrf_vdbench_v1
./render_config.sh all
./validate_model.sh
```

Expected:

```text
Total files: 7200
Total capacity: 112.50 GiB
PASS: WRF-derived Vdbench Zipf workload is internally consistent.
```

- [ ] **Step 5: Commit Task 2**

```bash
git add new_workload/hpc_wrf_vdbench_v1/configs \
  new_workload/hpc_wrf_vdbench_v1/rendered \
  new_workload/hpc_wrf_vdbench_v1/render_config.sh \
  new_workload/hpc_wrf_vdbench_v1/prepare_data.sh \
  new_workload/hpc_wrf_vdbench_v1/run_test.sh \
  new_workload/hpc_wrf_vdbench_v1/validate_model.sh \
  new_workload/hpc_wrf_vdbench_v1/tests/validate_hpc_vdbench_workload.py
git commit -m "feat: add WRF vdbench Zipf workload"
```

### Task 3: Source Documentation and Workload Index

**Files:**
- Create: `new_workload/hpc_wrf_vdbench_v1/README.md`
- Create: `new_workload/hpc_wrf_vdbench_v1/SOURCES.md`
- Modify: `new_workload/README.md`
- Modify: `new_workload/WORKLOAD_SUMMARY.md`

**Interfaces:**
- Documents the exact source/engineering boundary consumed by workload users.
- Lists IOR and Vdbench as parallel HPC options without replacing the IOR directory.

- [ ] **Step 1: Extend validation with required documentation markers**

Require README markers:

```python
for marker in [
    "112.5 GiB", "Zipf(0.99)", "68 / 7 / 4 / 3 / 2 / 2",
    "startup_read", "checkpoint_reheat", "不是 WRF trace",
]:
    assert marker in readme
```

Require official source URLs for the WRF model/users guide, IOR-retention explanation, and Vdbench execution-tool documentation in `SOURCES.md`.

- [ ] **Step 2: Run validation and verify documentation failure**

Expected: FAIL because README and SOURCES are missing.

- [ ] **Step 3: Write documentation and update indexes**

README sections must cover purpose, source boundary, data layout, formula, four phases, workflow, defaults, acceptance, and limitations. `new_workload/README.md` must show both `hpc_wrf_ior_v1` and `hpc_wrf_vdbench_v1`; `WORKLOAD_SUMMARY.md` must describe the Vdbench version as the controllable-heat option and retain IOR as the MPI-oriented option.

- [ ] **Step 4: Run validation and Markdown consistency checks**

Run:

```bash
./new_workload/hpc_wrf_vdbench_v1/validate_model.sh
rg -n "hpc_wrf_(ior|vdbench)_v1" new_workload/README.md new_workload/WORKLOAD_SUMMARY.md
```

Expected: validator PASS and both directories listed.

- [ ] **Step 5: Commit files that do not include unrelated dirty hunks**

Stage the new workload documentation and clean index changes only. If `WORKLOAD_SUMMARY.md` contains pre-existing unrelated modifications, leave it uncommitted and report that fact rather than staging unrelated content.

### Task 4: Final Verification

**Files:**
- Verify all files under `new_workload/hpc_wrf_vdbench_v1/`.
- Verify preservation of `new_workload/hpc_wrf_ior_v1/`.

**Interfaces:**
- Produces evidence for final handoff; performs no CephFS I/O.

- [ ] **Step 1: Run shell and Python syntax checks**

```bash
bash -n new_workload/hpc_wrf_vdbench_v1/*.sh
python3 -m compileall -q new_workload/hpc_wrf_vdbench_v1/scripts new_workload/hpc_wrf_vdbench_v1/tests
```

- [ ] **Step 2: Run unit and integration validation**

```bash
python3 -m unittest discover -s new_workload/hpc_wrf_vdbench_v1/tests -p 'test_*.py' -v
new_workload/hpc_wrf_vdbench_v1/validate_model.sh
```

Expected: all unit tests PASS and model validator reports 7200 files, 112.50 GiB, and PASS.

- [ ] **Step 3: Inspect rendered invariants**

```bash
rg -n '^rd=' new_workload/hpc_wrf_vdbench_v1/rendered/run_test.vdb
rg -n 'operation=write|format=' new_workload/hpc_wrf_vdbench_v1/rendered/run_test.vdb
test -d new_workload/hpc_wrf_ior_v1
```

Expected: four RDs, no write/format match, and the IOR directory exists.

- [ ] **Step 4: Check patch hygiene**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; unrelated pre-existing changes remain untouched.
