# File-Level Zipf Workloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved file-level Zipf(0.99), mixed-file-size layouts for the five Vdbench workloads in both `new_workload/` and `SYSU_workload/`, without changing HPC IOR or the two fixed-hot experiments.

**Architecture:** A new repository-level `workload_common` package owns capacity units, exact decimal Zipf aggregation, Vdbench emission, and five workload models. Thin single-node and SYSU wrappers select the physical layout and host policy, so both environments share one logical design and cannot drift. Generated parameter files stay committed, while tests render into temporary directories and validate capacities, phases, skews, Direct I/O, and batched preparation.

**Tech Stack:** Python 3 standard library (`dataclasses`, `decimal`, `math`, `unittest`), Bash, Vdbench 5.04.07 parameter files.

## Global Constraints

- Single-node file sizes are exactly 4, 8, and 16 MiB; one unit is 48 MiB.
- SYSU file sizes are exactly 4, 8, 16, 32, and 64 MiB; one unit is 320 MiB.
- Every formal Vdbench workload contains exactly 2,400 units: 112.5 GiB single-node and 750 GiB SYSU.
- File popularity is Zipf(0.99) independently within each fixed-size class, aggregated into equal-capacity ranks with decimal skews and no minimum 1% normalization.
- Formal runs use read-only operations, `xfersize=4m`, `fwdrate=max`, `openflags=o_direct`, and `fileselect=random`.
- Prepare and run remain separate; prepare processes no more than 20 logical ranks per clean/create batch.
- SYSU parameter files contain no `hd=` definition; single-node files retain configurable `HOST1` and `REMOTE_USER`.
- Leave `new_workload/hpc_wrf_ior_v1`, `SYSU_workload/hpc_wrf_ior_v1`, `bigdata_fixed_hot_vdbench_v1`, and `graph_graphchi_fixed_hot_vdbench_v1` unchanged.

---

### Task 1: Shared layout and Vdbench emitter

**Files:**
- Create: `workload_common/__init__.py`
- Create: `workload_common/layout.py`
- Create: `workload_common/vdbench.py`
- Create: `workload_common/tests/__init__.py`
- Create: `workload_common/tests/test_layout.py`
- Create: `workload_common/tests/test_vdbench.py`
- Modify: `SYSU_workload/common/layout.py`
- Modify: `SYSU_workload/common/vdbench.py`

**Interfaces:**
- Produces: `Layout`, `SINGLE_LAYOUT`, `SYSU_LAYOUT`, `Bucket`, `make_rank_buckets()`, `rank_bucket_skews()`, `render_prepare_config()`, `fwd_line()`, `rd_line()`, and `write_config()`.
- `rank_bucket_skews(layout, group_units, rank_count, group_weight, hot_rank=1)` returns `{rank: {size_mib: decimal_text}}` whose values sum to `group_weight`.

- [ ] **Step 1: Write failing shared-layout tests**

```python
def test_physical_layouts_share_2400_logical_units():
    assert SINGLE_LAYOUT.capacity_mib(2400) == 112_500 + 2_700
    assert SYSU_LAYOUT.capacity_mib(2400) == 750 * 1024

def test_zipf_skews_are_positive_decimal_and_exact():
    skews = rank_bucket_skews(SINGLE_LAYOUT, 800, 80, Decimal("100"))
    values = [Decimal(value) for rank in skews.values() for value in rank.values()]
    assert all(value > 0 for value in values)
    assert sum(values) == Decimal("100")
    assert any(value != value.to_integral() for value in values)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest workload_common.tests.test_layout workload_common.tests.test_vdbench -v`

Expected: import failure because `workload_common` does not exist.

- [ ] **Step 3: Implement layouts, decimal Zipf aggregation, and batched prepare**

Implement immutable layouts with `(4,8,16)/(4,2,1)` and `(4,8,16,32,64)/(16,8,4,2,1)`. Compute each size class independently, partition its ordered file weights across equal file-count ranks, rotate the Zipf head with `hot_rank`, quantize to 12 decimal places, and apply the rounding correction to the final FWD. Give every `Bucket` a `rank_key`; group at most 20 distinct keys in each prepare clean/create pair.

- [ ] **Step 4: Run shared tests and verify GREEN**

Run: `python3 -m unittest workload_common.tests.test_layout workload_common.tests.test_vdbench -v`

Expected: all tests pass.

- [ ] **Step 5: Preserve compatibility imports**

Make `SYSU_workload.common.layout` and `SYSU_workload.common.vdbench` re-export the shared implementation so existing external imports do not silently get the obsolete integer-skew behavior.

### Task 2: MapReduce model and both environment wrappers

**Files:**
- Create: `workload_common/models/__init__.py`
- Create: `workload_common/models/mapreduce.py`
- Create: `workload_common/tests/test_mapreduce.py`
- Create: `new_workload/__init__.py`
- Create: `new_workload/bigdata_mapreduce_vdbench_v1/__init__.py`
- Create: `new_workload/bigdata_mapreduce_vdbench_v1/scripts/__init__.py`
- Create: `new_workload/bigdata_mapreduce_vdbench_v1/scripts/render.py`
- Modify: `SYSU_workload/bigdata_mapreduce_vdbench_v1/scripts/render.py`
- Modify: both `bigdata_mapreduce_vdbench_v1/render_config.sh`
- Modify: both MapReduce `README.md` files and `SOURCES.md` as needed.

**Interfaces:**
- Consumes: shared layouts and Vdbench emitter from Task 1.
- Produces: `workload_common.models.mapreduce.render(...)` with 96/96/96/2112 units, 32 ranks per pool, and four 150-second stages.

- [ ] **Step 1: Write failing model tests**

Render both layouts into temporary directories and assert: 2,400 units; 32 ranks per pool; units/rank `3,3,3,66`; stage pool weights `85/1/1/13`; four `elapsed=150` RDs; 384/640 FWDs per stage; all skews positive and summing to 100.

- [ ] **Step 2: Run MapReduce tests and verify RED**

Run: `python3 -m unittest workload_common.tests.test_mapreduce -v`

Expected: failure because the shared MapReduce model is missing.

- [ ] **Step 3: Implement and wire the model**

Generate anchors `<root>/<workload>/<pool>/rank_NNN/size_Xm`; call `rank_bucket_skews()` separately for each pool and each stage. Keep sequential file I/O and rotate only the pool-level 85% hotspot, not rank identities.

- [ ] **Step 4: Run tests and render committed configs**

Run: `python3 -m unittest workload_common.tests.test_mapreduce -v`

Run: `./new_workload/bigdata_mapreduce_vdbench_v1/render_config.sh all`

Run: `ANCHOR_ROOT=/ceph-test/SYSU_workload ./SYSU_workload/bigdata_mapreduce_vdbench_v1/render_config.sh`

Expected: tests pass and both `rendered/` pairs update.

### Task 3: GraphChi 4-shard × 4-window model

**Files:**
- Create: `workload_common/models/graphchi.py`
- Create: `workload_common/tests/test_graphchi.py`
- Create: `new_workload/graph_graphchi_vdbench_v1/__init__.py`
- Create: `new_workload/graph_graphchi_vdbench_v1/scripts/__init__.py`
- Create/Replace: `new_workload/graph_graphchi_vdbench_v1/scripts/render.py`
- Modify: `SYSU_workload/graph_graphchi_vdbench_v1/scripts/render.py`
- Modify: both GraphChi `render_config.sh`, `README.md`, and validation entry points.

**Interfaces:**
- Produces: 16 windows named by source and destination interval, 15 ranks/window, 10 units/rank, and four PSW stages.

- [ ] **Step 1: Write failing PSW tests**

Assert four equal 600-unit shards; four 150-unit windows per shard; 15 ranks/window; every phase activates the destination shard's four windows plus three source-matched windows; exactly seven windows, 105 ranks, and 315/525 FWDs are active; each phase runs 150 seconds and sums to 100% skew.

- [ ] **Step 2: Run GraphChi tests and verify RED**

Run: `python3 -m unittest workload_common.tests.test_graphchi -v`

- [ ] **Step 3: Implement the PSW access model**

Represent a window as `(src, dst)`. During phase `p`, select all `(src,p)` and all `(p,dst)` with duplicates removed. Assign every selected window `100/7` of accesses and then apply 15-rank file-level Zipf inside it.

- [ ] **Step 4: Run tests and render committed configs**

Run the GraphChi unit test, then both environment renderers with default phase length 150 seconds.

Expected: four RDs, no obsolete fifth reheat RD, and all tests pass.

### Task 4: HPC Vdbench model

**Files:**
- Create: `workload_common/models/hpc.py`
- Create: `workload_common/tests/test_hpc.py`
- Create: `new_workload/hpc_wrf_vdbench_v1/__init__.py`
- Create/Replace: `new_workload/hpc_wrf_vdbench_v1/scripts/render.py`
- Modify: `SYSU_workload/hpc_wrf_vdbench_v1/scripts/render.py`
- Modify: both HPC Vdbench wrappers, READMEs, and validation entry points.

**Interfaces:**
- Produces: startup/checkpoint/history groups of 800 units each, 80 ranks/group, and phases startup/checkpoint/history/checkpoint-reheat.

- [ ] **Step 1: Write failing HPC tests**

Assert 80 ranks and 10 units/rank in each group, four 150-second pure sequential-read phases, the checkpoint group is selected twice, all phases have 240/400 FWDs, and the HPC IOR tree hash is unchanged.

- [ ] **Step 2: Run HPC tests and verify RED**

Run: `python3 -m unittest workload_common.tests.test_hpc -v`

- [ ] **Step 3: Implement, wire, and render HPC Vdbench**

Use one 100% group-level share per phase and independent Zipf per size class. Keep `fileio=sequential`, Direct I/O, and 4 MiB transfers.

- [ ] **Step 4: Run tests and compare IOR status**

Run the HPC unit test and `git diff -- new_workload/hpc_wrf_ior_v1 SYSU_workload/hpc_wrf_ior_v1`.

Expected: test passes and IOR diff is empty.

### Task 5: AI training model

**Files:**
- Create: `workload_common/models/ai_training.py`
- Create: `workload_common/tests/test_ai_training.py`
- Create: `new_workload/ai_training_checkpoint_vdbench_v1/__init__.py`
- Create: `new_workload/ai_training_checkpoint_vdbench_v1/scripts/__init__.py`
- Create: `new_workload/ai_training_checkpoint_vdbench_v1/scripts/render.py`
- Modify: `SYSU_workload/ai_training_checkpoint_vdbench_v1/scripts/render.py`
- Modify: both AI-training wrappers, READMEs, and validation entry points.

**Interfaces:**
- Produces: dataset/current/old groups of 2080/160/160 units, 80 ranks each, and six phases totaling 600 seconds.

- [ ] **Step 1: Write failing AI-training tests**

Assert `26/2/2` units per rank; dataset epochs are random reads of 160 seconds with Zipf heads at physical ranks 1, 2, and 3; two current and one old checkpoint stages are sequential 40-second reads; all stages have 240/400 FWDs and exact skew sums.

- [ ] **Step 2: Run test and verify RED**

Run: `python3 -m unittest workload_common.tests.test_ai_training -v`

- [ ] **Step 3: Implement rotating dataset heads and ranked checkpoints**

Use `rank_bucket_skews(..., hot_rank=1/2/3)` for epochs and `hot_rank=1` for checkpoint stages; unlike the old generator, both checkpoint groups must contain 80 ranked partitions.

- [ ] **Step 4: Run tests and render both environments**

Expected: `160 × 3 + 40 × 3 = 600` seconds and all tests pass.

### Task 6: AI inference model

**Files:**
- Create: `workload_common/models/ai_inference.py`
- Create: `workload_common/tests/test_ai_inference.py`
- Create: `new_workload/ai_inference_kvcache_vdbench_v1/__init__.py`
- Create: `new_workload/ai_inference_kvcache_vdbench_v1/scripts/__init__.py`
- Create: `new_workload/ai_inference_kvcache_vdbench_v1/scripts/render.py`
- Modify: `SYSU_workload/ai_inference_kvcache_vdbench_v1/scripts/render.py`
- Modify: both AI-inference wrappers, READMEs, and validation entry points.

**Interfaces:**
- Produces: active/next/prefix groups of 800 units, 80 ranks/group, and six 100-second phases.

- [ ] **Step 1: Write failing AI-inference tests**

Assert 80 ranks and 10 units/rank; active and next each have sequential prefill followed by random decode without changing the physical Zipf head; prefix has two random phases whose heads are ranks 1 then 2; every phase has 240/400 FWDs and exact skew sums.

- [ ] **Step 2: Run test and verify RED**

Run: `python3 -m unittest workload_common.tests.test_ai_inference -v`

- [ ] **Step 3: Implement, wire, and render both environments**

Expected: six `elapsed=100` RDs and all tests pass.

### Task 7: Wrappers, generated files, documentation, and full regression

**Files:**
- Modify: ten `render_config.sh` files and ten `validate_model.sh` files.
- Modify: `new_workload/README.md`, `new_workload/WORKLOAD_SUMMARY.md`, `SYSU_workload/README.md`.
- Modify: all ten formal Vdbench workload READMEs and tracked `rendered/*.vdb` files.
- Remove: obsolete single-node `.vdb.in` templates and superseded derivation scripts/tests only after their replacement tests pass.

**Interfaces:**
- Consumes: all five shared models.
- Produces: end-user render/validate workflows and synchronized documentation.

- [ ] **Step 1: Add failing cross-suite contract tests**

Check each formal workload for: expected size set; 2,400 logical units; exact capacity; `fwdrate=max`; Direct I/O; 4 MiB transfers; no writes; no `format=` in run configs; batched prepare RDs; correct stage count and total 600 seconds. Also assert SYSU contains no `hd=` and single-node contains exactly one configurable `hd=` line.

- [ ] **Step 2: Run full suite and verify RED for stale wrappers/docs**

Run: `python3 -m unittest discover -s workload_common/tests -v`

Run: `python3 -m unittest discover -s SYSU_workload/tests -v`

- [ ] **Step 3: Replace wrappers and remove superseded templates**

Single-node wrappers invoke their Python module from repository root, default to `/mnt/cephfs`, one thread, `FWD_RATE=max`, and retain `HOST1`/`REMOTE_USER`. SYSU wrappers continue requiring `ANCHOR_ROOT`, default to one thread and `max`, and emit no host line.

- [ ] **Step 4: Update user documentation**

Document the two physical capacity units, 80-rank precision for HPC/AI, 32-rank MapReduce pools, 15-rank GraphChi windows, exact stages, file-level Zipf approximation, 20-rank prepare batching, and the fact that IOR remains unchanged.

- [ ] **Step 5: Regenerate all ten configuration pairs**

Run every single-node renderer with defaults and every SYSU renderer with `ANCHOR_ROOT=/ceph-test/SYSU_workload`.

- [ ] **Step 6: Run final verification**

Run:

```bash
python3 -m unittest discover -s workload_common/tests -v
python3 -m unittest discover -s SYSU_workload/tests -v
for validator in new_workload/*_vdbench_v1/validate_model.sh; do "$validator"; done
SYSU_workload/validate_all.sh
git diff --check
git diff -- new_workload/hpc_wrf_ior_v1 SYSU_workload/hpc_wrf_ior_v1
```

Expected: all commands pass; IOR diff is empty; no whitespace errors.

- [ ] **Step 7: Review scope**

Run `git status --short` and confirm there are no changes under the two fixed-hot workloads, the IOR workloads, runtime `output/`, or `hp_runs/`.

## Self-Review

- Spec coverage: all five logical models, both physical layouts, file-level Zipf, decimal skews, prepare batching, phase timing, Direct I/O, host policy, and exclusions map to Tasks 1–7.
- Placeholder scan: no TBD/TODO/“similar to” placeholders remain; every task names exact behavior and commands.
- Type consistency: all models consume the same `Layout`, `Bucket`, `rank_bucket_skews()`, and Vdbench emitter interfaces established in Task 1.
- Risk check: generated parameter files may be large, so tests validate generated text in temporary directories before tracked files are replaced; IOR and fixed-hot trees have explicit no-diff checks.
