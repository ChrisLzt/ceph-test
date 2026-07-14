# SYSU HPC WRF IOR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a host-agnostic 750 GiB WRF-lifecycle IOR workload with four MPI ranks, file-per-process `-F`, 4 MiB Direct I/O, and four read-only 150-second phases.

**Architecture:** A shell renderer substitutes an explicitly supplied CephFS root and optional MPI hostfile into separate prepare/run templates. The prepare path creates three 250 GiB file-per-process groups; the run path reads startup, checkpoint, history, and the same checkpoint again. Python validation parses generated scripts and enforces capacity, lifecycle, read-only behavior, timing, and client neutrality.

**Tech Stack:** Bash, POSIX IOR, OpenMPI-compatible `mpirun`, Python 3 `unittest`, Git.

## Global Constraints

- Work in `/home/chris/ceph-test` on the user-authorized local `main` branch.
- Create `/home/chris/ceph-test/SYSU_workload/hpc_wrf_ior_v1`; do not change `new_workload/hpc_wrf_ior_v1`.
- Require an absolute `ANCHOR_ROOT`; append `/hpc_wrf_ior_v1` for the data path.
- Fix capacity at three groups × 250 GiB = 750 GiB logical.
- Fix `NP=4`, `BLOCK_SIZE=64000m`, `SEGMENT_COUNT=1`, and `TRANSFER_SIZE=4m`.
- Use `-F` and `--posix.odirect` for both prepare and formal run.
- Formal run is sequential read-only with four 150-second phases and checkpoint reheat.
- Do not hardcode a client hostname or hostfile; accept an optional runtime `MPI_HOSTFILE`.
- Do not create CephFS data or execute IOR during implementation and validation.

---

### Task 1: Add failing contract tests

**Files:**
- Create: `SYSU_workload/tests/test_hpc_ior.py`
- Modify: `SYSU_workload/tests/test_suite.py`

**Interfaces:**
- Consumes: `SYSU_workload/hpc_wrf_ior_v1/render_config.sh` as a subprocess interface.
- Produces: executable behavior contracts for rendered `prepare_data.sh` and `run_test.sh`.

- [ ] **Step 1: Write the failing renderer tests**

Create `SYSU_workload/tests/test_hpc_ior.py` with tests that:

```python
class HpcIorRendererTests(unittest.TestCase):
    def test_requires_anchor_root(self):
        result = subprocess.run(
            [str(RENDERER)],
            env={"PATH": "/usr/bin:/bin"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ANCHOR_ROOT", result.stderr)

    def test_renders_750_gib_file_per_process_lifecycle(self):
        env = os.environ.copy()
        env.update({
            "ANCHOR_ROOT": "/__SYSU_CEPHFS__",
            "RENDERED_DIR": str(output),
            "IOR_BIN": "/opt/ior/bin/ior",
            "MPI_RUN": "/opt/mpi/bin/mpirun",
        })
        subprocess.run(
            [str(RENDERER)],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        prepare = (output / "prepare_data.sh").read_text()
        run = (output / "run_test.sh").read_text()
        self.assertIn('NP="4"', prepare)
        self.assertIn('BLOCK_SIZE="64000m"', prepare)
        self.assertIn('TRANSFER_SIZE="4m"', run)
        self.assertIn("-F", prepare)
        self.assertIn("-F", run)
        self.assertIn("--posix.odirect", prepare)
        self.assertIn("--posix.odirect", run)
        self.assertEqual(4 * 64000 * 3 // 1024, 750)
        self.assertEqual(run.count("run_ior_read "), 4)
        self.assertNotRegex(run, r"(?:^|\\s)-w(?:\\s|$)")
```

Also assert the exact four calls, including the same checkpoint base in phases two and four, `PHASE_SECONDS="150"`, `-D`, `minTimeDuration`, and `stoneWallingWearOut=0`. Assert that the default rendered hostfile is empty and contains no hostname.

- [ ] **Step 2: Extend the suite contract**

Add an assertion to `test_suite.py` that `hpc_wrf_ior_v1` contains `README.md`, `render_config.sh`, `prepare_data.sh`, `run_test.sh`, and `validate_model.sh`. Keep the existing assertion of exactly five directories ending in `_vdbench_v1`.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
python3 -m unittest SYSU_workload.tests.test_hpc_ior SYSU_workload.tests.test_suite -v
```

Expected: FAIL because `SYSU_workload/hpc_wrf_ior_v1/render_config.sh` and the workload directory do not exist.

- [ ] **Step 4: Commit the failing tests**

```bash
git add SYSU_workload/tests/test_hpc_ior.py SYSU_workload/tests/test_suite.py
git commit -m "test: define SYSU WRF IOR contract"
```

---

### Task 2: Implement rendering and workload scripts

**Files:**
- Create: `SYSU_workload/hpc_wrf_ior_v1/configs/prepare_data.sh.in`
- Create: `SYSU_workload/hpc_wrf_ior_v1/configs/run_test.sh.in`
- Create: `SYSU_workload/hpc_wrf_ior_v1/render_config.sh`
- Create: `SYSU_workload/hpc_wrf_ior_v1/prepare_data.sh`
- Create: `SYSU_workload/hpc_wrf_ior_v1/run_test.sh`
- Create: `SYSU_workload/hpc_wrf_ior_v1/validate_model.sh`
- Create: `SYSU_workload/hpc_wrf_ior_v1/tests/validate_hpc_ior.py`
- Create: `SYSU_workload/hpc_wrf_ior_v1/__init__.py`
- Create: `SYSU_workload/hpc_wrf_ior_v1/tests/__init__.py`

**Interfaces:**
- Consumes: `ANCHOR_ROOT`, `IOR_BIN`, `MPI_RUN`, optional `MPI_HOSTFILE`, optional `PHASE_SECONDS`, and optional `RENDERED_DIR`.
- Produces: `rendered/prepare_data.sh`, `rendered/run_test.sh`, prepare/run wrappers, and a static model validator.

- [ ] **Step 1: Implement the prepare template**

The rendered template must define fixed capacity variables and build MPI arguments as an array:

```bash
ANCHOR="@ANCHOR@"
IOR_BIN="@IOR_BIN@"
MPI_RUN="@MPI_RUN@"
MPI_HOSTFILE="@MPI_HOSTFILE@"
NP="4"
API="POSIX"
BLOCK_SIZE="64000m"
TRANSFER_SIZE="4m"
SEGMENT_COUNT="1"

mpi_args=(-np "$NP")
[[ -n "$MPI_HOSTFILE" ]] && mpi_args+=(--hostfile "$MPI_HOSTFILE")

"$MPI_RUN" "${mpi_args[@]}" "$IOR_BIN" \
    -a "$API" --posix.odirect -F -w -k -e \
    -o "$target" -b "$BLOCK_SIZE" -t "$TRANSFER_SIZE" \
    -s "$SEGMENT_COUNT" -i 1
```

Limit deletion to `$ANCHOR`, recreate startup/checkpoint/history, and call the helper exactly three times for `wrf_state`, `wrfrst_current`, and `wrfout_current`.

- [ ] **Step 2: Implement the run template**

Use the same MPI, capacity, `-F`, and Direct I/O options, but run only reads:

```bash
"$MPI_RUN" "${mpi_args[@]}" "$IOR_BIN" \
    -a "$API" --posix.odirect -F -r -k \
    -o "$target" -b "$BLOCK_SIZE" -t "$TRANSFER_SIZE" \
    -s "$SEGMENT_COUNT" -i 1 \
    -D "$PHASE_SECONDS" \
    -O "minTimeDuration=$PHASE_SECONDS" \
    -O stoneWallingWearOut=0
```

Call it in this exact order:

```bash
run_ior_read startup_read "$ANCHOR/startup/wrf_state"
run_ior_read checkpoint_read "$ANCHOR/checkpoint/wrfrst_current"
run_ior_read history_read "$ANCHOR/history/wrfout_current"
run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"
```

- [ ] **Step 3: Implement the renderer**

`render_config.sh` must reject a missing/non-absolute `ANCHOR_ROOT`, reject non-positive `PHASE_SECONDS`, append the workload name, escape sed replacement values, render both templates into `${RENDERED_DIR:-$root/rendered}`, reject unresolved `@[A-Z_]+@` tokens, and make outputs executable. Defaults:

```bash
IOR_BIN=/home/chris/PDSL/ior/src/ior
MPI_RUN=mpirun
MPI_HOSTFILE=
PHASE_SECONDS=150
```

- [ ] **Step 4: Implement wrappers and validator**

`prepare_data.sh` must create only `${ANCHOR_ROOT}/hpc_wrf_ior_v1`, render, and execute the rendered prepare script. `run_test.sh` must render and execute only the read script. Both inherit `MPI_HOSTFILE` without inventing a host.

`tests/validate_hpc_ior.py` must parse the generated scripts and fail unless capacity is exactly 750 GiB, `NP=4`, `BLOCK_SIZE=64000m`, transfer is 4 MiB, both scripts contain `-F`/Direct I/O, prepare contains three writes, run contains four reads and no write, phases are correct, and checkpoint reheat targets the same base.

`validate_model.sh` renders using `${ANCHOR_ROOT:-/__SYSU_CEPHFS__}` and runs the validator without invoking IOR.

- [ ] **Step 5: Run focused tests and verify GREEN**

```bash
python3 -m unittest SYSU_workload.tests.test_hpc_ior SYSU_workload.tests.test_suite -v
ANCHOR_ROOT=/__SYSU_CEPHFS__ SYSU_workload/hpc_wrf_ior_v1/validate_model.sh
```

Expected: all focused unit tests pass and the validator prints total capacity `750.00 GiB` plus a PASS line.

- [ ] **Step 6: Commit implementation**

```bash
git add SYSU_workload/hpc_wrf_ior_v1
git commit -m "feat: add SYSU WRF IOR workload"
```

---

### Task 3: Document and integrate the sixth workload

**Files:**
- Create: `SYSU_workload/hpc_wrf_ior_v1/README.md`
- Create: `SYSU_workload/hpc_wrf_ior_v1/SOURCES.md`
- Modify: `SYSU_workload/README.md`
- Modify: `SYSU_workload/validate_all.sh`

**Interfaces:**
- Consumes: behavior implemented in Task 2.
- Produces: user-facing workflow and top-level six-workload validation.

- [ ] **Step 1: Write workload documentation**

Document exact capacity, 4-rank file-per-process structure, 62.5 GiB rank files, 4 MiB requests, Direct I/O, four phases, optional hostfile, separate prepare/run workflow, destructive prepare boundary, and the fact that this model has group-level but not within-group Zipf heat.

`SOURCES.md` must cite the WRF model page, IOR official repository, and IOR official documentation, and explicitly separate source-supported lifecycle semantics from experimental capacity/timing choices.

- [ ] **Step 2: Update the top-level workflow**

Change the overview to “five Vdbench workloads plus one IOR workload,” add an IOR table row, document its optional `MPI_HOSTFILE`, and retain the warning that no Vdbench `hd=` definitions exist yet.

Keep `validate_all.sh` running Python discovery and Bash syntax checks, then call:

```bash
ANCHOR_ROOT=/__SYSU_CEPHFS__ \
    SYSU_workload/hpc_wrf_ior_v1/validate_model.sh
```

- [ ] **Step 3: Run full verification**

```bash
./SYSU_workload/validate_all.sh
git diff --check
git status --short
```

Expected: all Python tests pass, IOR validator reports 750 GiB, all shell scripts pass `bash -n`, and only intended files are modified.

- [ ] **Step 4: Commit documentation and integration**

```bash
git add SYSU_workload/README.md SYSU_workload/validate_all.sh \
    SYSU_workload/hpc_wrf_ior_v1/README.md \
    SYSU_workload/hpc_wrf_ior_v1/SOURCES.md
git commit -m "docs: integrate SYSU WRF IOR workflow"
```

---

### Task 4: Final requirements audit

**Files:**
- Verify: `docs/superpowers/specs/2026-07-14-sysu-hpc-wrf-ior-design.md`
- Verify: all files created or modified by Tasks 1–3.

**Interfaces:**
- Consumes: complete implementation and approved design.
- Produces: evidence that the implementation matches the design without running IOR or creating data.

- [ ] **Step 1: Verify requirements by inspection and generated artifacts**

```bash
tmp=$(mktemp -d)
ANCHOR_ROOT=/__SYSU_CEPHFS__ RENDERED_DIR="$tmp" \
    SYSU_workload/hpc_wrf_ior_v1/render_config.sh
rg -n -- "-F|--posix.odirect|NP=|BLOCK_SIZE=|TRANSFER_SIZE=|run_ior_(write|read)" "$tmp"
rm -rf "$tmp"
```

Confirm three prepare calls, four read calls, no formal write, no hardcoded client, and the same checkpoint path in phases two and four.

- [ ] **Step 2: Run fresh complete validation**

```bash
./SYSU_workload/validate_all.sh
git diff --check
git status --short --branch
```

Expected: zero failures, clean diff checks, and no unrelated changes.

- [ ] **Step 3: Commit any final corrections**

If the audit required corrections, repeat their focused red-green test and commit only those corrections. Otherwise do not create an empty commit.
