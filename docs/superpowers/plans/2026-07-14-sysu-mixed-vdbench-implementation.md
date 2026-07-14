# SYSU Mixed-Size Vdbench Workloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a separate `/home/chris/ceph-test/SYSU_workload` suite containing five 750 GiB Vdbench workloads with 4/8/16/32/64 MiB files, source-preserving heat distributions, and 4 MiB Direct I/O.

**Architecture:** A shared Python module owns the 320 MiB capacity unit, exact size-bucket expansion, Zipf aggregation, Vdbench text helpers, and structural validation. Each workload has a small Python renderer that declares its logical pools/ranks and stages, plus three shell entry points matching the existing render/prepare/run workflow. Rendered configs omit `hd=` until a later multi-client task.

**Tech Stack:** Python 3 standard library, Bash, Oracle Vdbench 5.04.07 parameter files, `unittest`.

## Global Constraints

- Do not modify `/home/chris/ceph-test/new_workload`; it remains the single-node suite.
- Create the new source suite at `/home/chris/ceph-test/SYSU_workload`.
- Require `ANCHOR_ROOT`; data anchors are `${ANCHOR_ROOT}/<workload-name>`.
- Generate no `hd=` lines and hard-code no client host names.
- Each workload is exactly 750 GiB and 74,400 files.
- File sizes are exactly 4, 8, 16, 32, and 64 MiB; each contributes 150 GiB per workload.
- Every formal I/O uses `xfersize=4m` and `openflags=o_direct`.
- Prepare configs contain clean/create runs; run configs contain no `format=`.
- Do not create CephFS data or execute a formal workload.
- Do not modify the HPC IOR workload in this implementation.

---

### Task 1: Shared mixed-layout and Vdbench generation library

**Files:**
- Create: `SYSU_workload/common/__init__.py`
- Create: `SYSU_workload/common/layout.py`
- Create: `SYSU_workload/common/vdbench.py`
- Create: `SYSU_workload/tests/test_common.py`

**Interfaces:**
- Produces: `bucket_counts(units: int) -> dict[int, int]`
- Produces: `aggregate_zipf_percentages(object_count: int, rank_count: int, alpha: float) -> list[int]`
- Produces: `split_skew(weight: int | float, buckets: int = 5) -> list[str]`
- Produces: `Bucket`, `make_buckets()`, `render_fsd_lines()`, `render_prepare_config()` and `write_config()`.

- [ ] **Step 0: Record the untouched single-node tree**

```bash
find new_workload -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/sysu-new-workload-before.sha256
find new_workload -type f -printf '%P\n' | sort > /tmp/sysu-new-workload-before.files
```

- [ ] **Step 1: Write the failing common tests**

```python
def test_one_unit_has_equal_capacity_per_size():
    assert bucket_counts(1) == {4: 16, 8: 8, 16: 4, 32: 2, 64: 1}

def test_750_gib_layout():
    counts = bucket_counts(2400)
    assert sum(size * files for size, files in counts.items()) == 750 * 1024
    assert sum(counts.values()) == 74400

def test_scaled_zipf_profiles():
    assert aggregate_zipf_percentages(64000, 20, 0.99) == [73, 6, 3, 2] + [1] * 16
    assert aggregate_zipf_percentages(166400, 20, 0.99) == [74, 5, 3, 2] + [1] * 16

def test_fractional_bucket_skew():
    assert split_skew(13) == ["2.6"] * 5
    assert split_skew(1) == ["0.2"] * 5
```

- [ ] **Step 2: Run the common tests and confirm failure**

Run: `python3 -m unittest SYSU_workload.tests.test_common -v`

Expected: FAIL because `SYSU_workload.common` does not exist.

- [ ] **Step 3: Implement the common library**

Use these constants and formulas:

```python
SIZE_MIB = (4, 8, 16, 32, 64)
FILES_PER_UNIT = (16, 8, 4, 2, 1)
UNIT_MIB = 320

def bucket_counts(units: int) -> dict[int, int]:
    if units <= 0:
        raise ValueError("units must be positive")
    return {size: count * units for size, count in zip(SIZE_MIB, FILES_PER_UNIT)}
```

`aggregate_zipf_percentages()` must use object weights `i ** -alpha`, aggregate contiguous equal-capacity ranks, round to positive integer percentages, and preserve a total of 100. `split_skew()` must use `Decimal` and remove trailing zeros without converting 0.2 to zero.

- [ ] **Step 4: Run the common tests**

Run: `python3 -m unittest SYSU_workload.tests.test_common -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit the common foundation**

```bash
git add SYSU_workload/common SYSU_workload/tests/test_common.py
git commit -m "feat: add SYSU mixed-size workload primitives"
```

### Task 2: MapReduce 750 GiB workload

**Files:**
- Create: `SYSU_workload/bigdata_mapreduce_vdbench_v1/scripts/render.py`
- Create: `SYSU_workload/bigdata_mapreduce_vdbench_v1/render_config.sh`
- Create: `SYSU_workload/bigdata_mapreduce_vdbench_v1/prepare_data.sh`
- Create: `SYSU_workload/bigdata_mapreduce_vdbench_v1/run_test.sh`
- Create: `SYSU_workload/bigdata_mapreduce_vdbench_v1/validate_model.sh`
- Create: `SYSU_workload/bigdata_mapreduce_vdbench_v1/README.md`
- Create: `SYSU_workload/tests/test_bigdata.py`

**Interfaces:**
- Consumes: common size buckets and Vdbench helpers from Task 1.
- Produces: `render(anchor_root: str, output_dir: Path, threads: int, phase_seconds: int, fwdrate: str)`.

- [ ] **Step 1: Write tests for exact pools and stage weights**

Assert pool unit counts `{pool_01: 96, pool_02: 96, pool_03: 96, pool_04: 2112}`, 20 FSDs, 74,400 files, 750 GiB, no `hd=`, run config without `format=`, and per-stage aggregate weights:

```python
EXPECTED = {
    "hot_a": {"pool_01": 85, "pool_02": 1, "pool_03": 1, "pool_04": 13},
    "hot_b": {"pool_01": 1, "pool_02": 85, "pool_03": 1, "pool_04": 13},
    "hot_c": {"pool_01": 1, "pool_02": 1, "pool_03": 85, "pool_04": 13},
    "reheat_a": {"pool_01": 85, "pool_02": 1, "pool_03": 1, "pool_04": 13},
}
```

- [ ] **Step 2: Run the MapReduce test and confirm failure**

Run: `python3 -m unittest SYSU_workload.tests.test_bigdata -v`

Expected: FAIL because the renderer is absent.

- [ ] **Step 3: Implement the renderer and entry points**

Generate five FSDs per pool under `pool_XX/size_Ym`. Split each pool weight equally across its five buckets, use sequential 4 MiB reads, four 150-second phases, and `fwdrate=max` by default. `render_config.sh` must reject a missing `ANCHOR_ROOT`.
Rendered files are runtime artifacts under the workload's `rendered/` directory and are not committed with a synthetic anchor.

- [ ] **Step 4: Render and validate MapReduce**

Run:

```bash
ANCHOR_ROOT=/tmp/sysu-cephfs SYSU_workload/bigdata_mapreduce_vdbench_v1/render_config.sh
SYSU_workload/bigdata_mapreduce_vdbench_v1/validate_model.sh
```

Expected: renderer reports 750 GiB and validation prints PASS.

- [ ] **Step 5: Commit MapReduce**

```bash
git add SYSU_workload/bigdata_mapreduce_vdbench_v1 SYSU_workload/tests/test_bigdata.py
git commit -m "feat: add SYSU MapReduce workload"
```

### Task 3: GraphChi 750 GiB workload

**Files:**
- Create: `SYSU_workload/graph_graphchi_vdbench_v1/scripts/render.py`
- Create: `SYSU_workload/graph_graphchi_vdbench_v1/render_config.sh`
- Create: `SYSU_workload/graph_graphchi_vdbench_v1/prepare_data.sh`
- Create: `SYSU_workload/graph_graphchi_vdbench_v1/run_test.sh`
- Create: `SYSU_workload/graph_graphchi_vdbench_v1/validate_model.sh`
- Create: `SYSU_workload/graph_graphchi_vdbench_v1/README.md`
- Create: `SYSU_workload/tests/test_graph.py`

**Interfaces:**
- Consumes: Task 1 helpers and the existing generated-graph stage ratios 75/13/6/6.
- Produces: four-shard, five-size rendering with five 120-second stages.

- [ ] **Step 1: Write graph tests**

Assert four shards, 600 units per shard, bucket counts `9600/4800/2400/1200/600`, 20 FSDs, and stages `iter1_i0` through `iter1_i3` plus `iter2_i0`. For every stage, aggregate the five size FWDs back to shard weights and compare with the rotated 75/13/6/6 profile.

- [ ] **Step 2: Run the graph test and confirm failure**

Run: `python3 -m unittest SYSU_workload.tests.test_graph -v`

Expected: FAIL because the renderer is absent.

- [ ] **Step 3: Implement GraphChi rendering**

Use `shard_00/size_4m` through `shard_03/size_64m`. Do not call the single-node renderer and do not apply Zipf. Use sequential 4 MiB reads and split each derived shard percentage equally across size buckets.

- [ ] **Step 4: Render and validate GraphChi**

Run:

```bash
ANCHOR_ROOT=/tmp/sysu-cephfs SYSU_workload/graph_graphchi_vdbench_v1/render_config.sh
SYSU_workload/graph_graphchi_vdbench_v1/validate_model.sh
```

Expected: PASS with 750 GiB, five stages, and no `hd=`.

- [ ] **Step 5: Commit GraphChi**

```bash
git add SYSU_workload/graph_graphchi_vdbench_v1 SYSU_workload/tests/test_graph.py
git commit -m "feat: add SYSU GraphChi workload"
```

### Task 4: HPC WRF Vdbench 750 GiB workload

**Files:**
- Create: `SYSU_workload/hpc_wrf_vdbench_v1/scripts/render.py`
- Create: `SYSU_workload/hpc_wrf_vdbench_v1/render_config.sh`
- Create: `SYSU_workload/hpc_wrf_vdbench_v1/prepare_data.sh`
- Create: `SYSU_workload/hpc_wrf_vdbench_v1/run_test.sh`
- Create: `SYSU_workload/hpc_wrf_vdbench_v1/validate_model.sh`
- Create: `SYSU_workload/hpc_wrf_vdbench_v1/README.md`
- Create: `SYSU_workload/tests/test_hpc.py`

**Interfaces:**
- Consumes: `aggregate_zipf_percentages(64000, 20, 0.99)` from Task 1.
- Produces: three 250 GiB groups, each with twenty 12.5 GiB ranks and five size buckets per rank.

- [ ] **Step 1: Write HPC tests**

Assert 300 FSDs, each rank bucket counts `640/320/160/80/40`, group capacity 250 GiB, and rank weights `[73, 6, 3, 2] + [1] * 16`. Assert stages startup, checkpoint, history, checkpoint reheat and that the two checkpoint stages reference identical bucket sets and weights.

- [ ] **Step 2: Run the HPC test and confirm failure**

Run: `python3 -m unittest SYSU_workload.tests.test_hpc -v`

Expected: FAIL because the renderer is absent.

- [ ] **Step 3: Implement HPC rendering**

Create paths such as `startup/rank_01/size_4m`. Split every rank percentage evenly across its five bucket FWDs. Use sequential, random-file-selection, read-only, 4 MiB Direct I/O and four 150-second phases.

- [ ] **Step 4: Render and validate HPC**

Run:

```bash
ANCHOR_ROOT=/tmp/sysu-cephfs SYSU_workload/hpc_wrf_vdbench_v1/render_config.sh
SYSU_workload/hpc_wrf_vdbench_v1/validate_model.sh
```

Expected: PASS with 750 GiB and rank_01 at 73% of each active group.

- [ ] **Step 5: Commit HPC**

```bash
git add SYSU_workload/hpc_wrf_vdbench_v1 SYSU_workload/tests/test_hpc.py
git commit -m "feat: add SYSU WRF Vdbench workload"
```

### Task 5: AI training 750 GiB workload

**Files:**
- Create: `SYSU_workload/ai_training_checkpoint_vdbench_v1/scripts/render.py`
- Create: `SYSU_workload/ai_training_checkpoint_vdbench_v1/render_config.sh`
- Create: `SYSU_workload/ai_training_checkpoint_vdbench_v1/prepare_data.sh`
- Create: `SYSU_workload/ai_training_checkpoint_vdbench_v1/run_test.sh`
- Create: `SYSU_workload/ai_training_checkpoint_vdbench_v1/validate_model.sh`
- Create: `SYSU_workload/ai_training_checkpoint_vdbench_v1/README.md`
- Create: `SYSU_workload/tests/test_ai_training.py`

**Interfaces:**
- Consumes: `aggregate_zipf_percentages(166400, 20, 0.99)` from Task 1.
- Produces: 650 GiB dataset plus 50 GiB current and 50 GiB old checkpoints.

- [ ] **Step 1: Write AI training tests**

Assert 20 dataset ranks with bucket counts `1664/832/416/208/104`, two checkpoint groups with counts `2560/1280/640/320/160`, total 750 GiB and 74,400 files. Assert Zipf weights `[74, 5, 3, 2] + [1] * 16`, rotated rank leaders 01/02/03, and 20% per checkpoint size bucket.

- [ ] **Step 2: Run the AI training test and confirm failure**

Run: `python3 -m unittest SYSU_workload.tests.test_ai_training -v`

Expected: FAIL because the renderer is absent.

- [ ] **Step 3: Implement AI training rendering**

Use three 160-second dataset epochs and three 40-second checkpoint/recovery stages. Dataset FWDs use random 4 MiB reads with rotated Zipf ranks; checkpoint FWDs use sequential 4 MiB reads and five equal 20% size shares.

- [ ] **Step 4: Render and validate AI training**

Run:

```bash
ANCHOR_ROOT=/tmp/sysu-cephfs SYSU_workload/ai_training_checkpoint_vdbench_v1/render_config.sh
SYSU_workload/ai_training_checkpoint_vdbench_v1/validate_model.sh
```

Expected: PASS with 600 seconds total and no zero-weight dataset rank.

- [ ] **Step 5: Commit AI training**

```bash
git add SYSU_workload/ai_training_checkpoint_vdbench_v1 SYSU_workload/tests/test_ai_training.py
git commit -m "feat: add SYSU AI training workload"
```

### Task 6: AI inference 750 GiB workload

**Files:**
- Create: `SYSU_workload/ai_inference_kvcache_vdbench_v1/scripts/render.py`
- Create: `SYSU_workload/ai_inference_kvcache_vdbench_v1/render_config.sh`
- Create: `SYSU_workload/ai_inference_kvcache_vdbench_v1/prepare_data.sh`
- Create: `SYSU_workload/ai_inference_kvcache_vdbench_v1/run_test.sh`
- Create: `SYSU_workload/ai_inference_kvcache_vdbench_v1/validate_model.sh`
- Create: `SYSU_workload/ai_inference_kvcache_vdbench_v1/README.md`
- Create: `SYSU_workload/tests/test_ai_inference.py`

**Interfaces:**
- Consumes: the same 64,000-object Zipf profile as HPC.
- Produces: three 250 GiB KV groups, each with twenty mixed-size ranks.

- [ ] **Step 1: Write AI inference tests**

Assert 300 FSDs, exact 12.5 GiB rank layout, Zipf weights `[73, 6, 3, 2] + [1] * 16`, active and next rank_01 leaders, and shifted prefix rank_02 leader. Assert prefill is sequential while decode and prefix are random.

- [ ] **Step 2: Run the AI inference test and confirm failure**

Run: `python3 -m unittest SYSU_workload.tests.test_ai_inference -v`

Expected: FAIL because the renderer is absent.

- [ ] **Step 3: Implement AI inference rendering**

Generate six 100-second phases using the existing active/next/prefix sequence. Apply rank Zipf first and split each rank weight equally across its five size buckets. Keep all operations read-only and 4 MiB Direct I/O.

- [ ] **Step 4: Render and validate AI inference**

Run:

```bash
ANCHOR_ROOT=/tmp/sysu-cephfs SYSU_workload/ai_inference_kvcache_vdbench_v1/render_config.sh
SYSU_workload/ai_inference_kvcache_vdbench_v1/validate_model.sh
```

Expected: PASS with 600 seconds total and all ranks nonzero.

- [ ] **Step 5: Commit AI inference**

```bash
git add SYSU_workload/ai_inference_kvcache_vdbench_v1 SYSU_workload/tests/test_ai_inference.py
git commit -m "feat: add SYSU AI inference workload"
```

### Task 7: Suite documentation and aggregate validation

**Files:**
- Create: `SYSU_workload/README.md`
- Create: `SYSU_workload/validate_all.sh`
- Create: `SYSU_workload/tests/test_suite.py`

**Interfaces:**
- Consumes: all five renderers and validators.
- Produces: one command that validates every 12-node model without contacting clients or CephFS.

- [ ] **Step 1: Write aggregate suite tests**

Assert exactly five workload directories, no `hd=` in any rendered Vdbench file, every run config has 4 MiB I/O and no `format=`, every prepare config has clean/create, and every renderer rejects an absent `ANCHOR_ROOT`.

- [ ] **Step 2: Run the suite test and confirm failure**

Run: `python3 -m unittest SYSU_workload.tests.test_suite -v`

Expected: FAIL until `validate_all.sh` and the top-level README exist.

- [ ] **Step 3: Add top-level documentation and validator**

Document that `SYSU_workload` is the 12-node, three-replica script suite; `new_workload` remains single-node; `hd=` is intentionally deferred; and `ANCHOR_ROOT` must resolve identically on every future client.

- [ ] **Step 4: Run all tests and shell syntax checks**

Run:

```bash
python3 -m unittest discover -s SYSU_workload/tests -v
SYSU_workload/validate_all.sh
find SYSU_workload -name '*.sh' -print0 | xargs -0 -n1 bash -n
git diff --check
```

Expected: all unit tests and validators PASS, all shell scripts parse, and `git diff --check` prints nothing.

- [ ] **Step 5: Commit suite integration**

```bash
git add SYSU_workload/README.md SYSU_workload/validate_all.sh SYSU_workload/tests/test_suite.py
git commit -m "docs: add SYSU workload suite workflow"
```

### Task 8: Final source-preservation and capacity audit

**Files:**
- Verify only; no expected new files.

**Interfaces:**
- Consumes: completed suite.
- Produces: evidence that the five new workloads meet the approved design without changing single-node files.

- [ ] **Step 1: Verify single-node files were not changed by this implementation**

Run:

```bash
sha256sum -c /tmp/sysu-new-workload-before.sha256
find new_workload -type f -printf '%P\n' | sort > /tmp/sysu-new-workload-after.files
cmp /tmp/sysu-new-workload-before.files /tmp/sysu-new-workload-after.files
```

Expected: every checksum reports OK and `cmp` exits zero.

- [ ] **Step 2: Verify all rendered capacities and stages**

Run: `SYSU_workload/validate_all.sh`

Expected: five PASS lines followed by `PASS: all SYSU workloads validated`.

- [ ] **Step 3: Review final status without staging unrelated work**

Run: `git status --short`

Expected: pre-existing unrelated modifications remain visible and uncommitted; SYSU implementation files are committed.
