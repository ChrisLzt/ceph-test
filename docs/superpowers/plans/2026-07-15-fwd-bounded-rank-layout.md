# FWD-Bounded Rank Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce every formal RD to at most 512 matched FWDs and replace GraphChi windows with shard-local Zipf ranks.

**Architecture:** Change the shared rank constants so both physical layouts retain one logical model. Replace GraphChi's 16-window map with four 600-unit shard groups and preserve the existing four-stage crossfade machinery. Enforce the bound in the shared structural validator and regenerate both suites.

**Tech Stack:** Python 3, `unittest`, Bash, Vdbench 5.04.07.

## Global Constraints

- Keep all five Vdbench workloads at their existing total capacities and exactly 600 seconds.
- Preserve Zipf(0.99), physical file-size classes, Direct I/O, read-only execution, and `fwdrate=max`.
- Keep prefix-wildcard RD selectors and require every RD to match no more than 512 FWDs.
- Do not modify either IOR workload.

---

### Task 1: Encode the new rank and GraphChi contracts in tests

**Files:**
- Modify: `workload_common/tests/test_mapreduce.py`
- Modify: `workload_common/tests/test_graphchi.py`
- Modify: `workload_common/tests/test_hpc.py`
- Modify: `workload_common/tests/test_ai_training.py`
- Modify: `workload_common/tests/test_ai_inference.py`
- Modify: `SYSU_workload/tests/test_bigdata.py`
- Modify: `SYSU_workload/tests/test_graph.py`
- Modify: `SYSU_workload/tests/test_hpc.py`
- Modify: `SYSU_workload/tests/test_ai_training.py`
- Modify: `SYSU_workload/tests/test_ai_inference.py`
- Modify: `workload_common/tests/test_validation.py`

- [ ] Change expected constants, paths, stable counts, and transition counts.
- [ ] Add a failing validator test for a wildcard that matches 513 FWDs.
- [ ] Run focused tests and confirm they fail against the old models.

### Task 2: Implement the bounded shared models

**Files:**
- Modify: `workload_common/models/mapreduce.py`
- Modify: `workload_common/models/graphchi.py`
- Modify: `workload_common/models/hpc.py`
- Modify: `workload_common/models/ai_training.py`
- Modify: `workload_common/models/ai_inference.py`
- Modify: `workload_common/validate_vdbench.py`

- [ ] Set rank constants to 24/40/40/40/40.
- [ ] Replace GraphChi window construction with four shard groups of 600 units and 40 ranks.
- [ ] Reject run RDs whose expanded wildcard matches more than 512 FWDs.
- [ ] Run all shared and SYSU tests and confirm they pass.

### Task 3: Update migration behavior and documentation

**Files:**
- Modify: `SINGLE_workload/graph_graphchi_vdbench_v1/prepare_data.sh`
- Modify: `SYSU_workload/graph_graphchi_vdbench_v1/prepare_data.sh`
- Modify: `SINGLE_workload/graph_graphchi_vdbench_v1/README.md`
- Modify: `SINGLE_workload/graph_graphchi_vdbench_v1/SOURCES.md`
- Modify: `SYSU_workload/graph_graphchi_vdbench_v1/README.md`
- Modify: remaining workload READMEs and suite summaries containing old rank counts.

- [ ] Add scoped removal of legacy `window_src*` directories to GraphChi prepare.
- [ ] Remove PSW/window claims and document shard-local Zipf as an experimental mapping.
- [ ] Update every old 32/80/window rank statement.

### Task 4: Regenerate and verify both suites

**Files:**
- Regenerate: `SINGLE_workload/*_vdbench_v1/rendered/*.vdb`
- Regenerate: `SYSU_workload/*_vdbench_v1/rendered/*.vdb`

- [ ] Render all five formal workloads in both suites.
- [ ] Run both suite-level validation entry points.
- [ ] Verify 45+ unit/deployment tests, two IOR checks, 20 Vdbench simulations, shell syntax, Python compilation, and `git diff --check`.
- [ ] Confirm both IOR directories and unrelated user files remain unchanged.
