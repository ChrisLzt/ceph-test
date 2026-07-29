# Smooth Hotspot Transitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace instantaneous hotspot changes in all five Vdbench workloads with 30-second, three-step crossfades while preserving each workload's 600-second total duration.

**Architecture:** The shared workload layer will represent every stable hotspot as a complete bucket-to-skew profile and blend adjacent profiles at 25%, 50%, and 75% progress. Each transition uses three 10-second Vdbench RDs; stable time is shortened inside the existing logical phase budget, so capacity, source-derived lifecycle, data layout, operations, and the 600-second total remain unchanged. Both `SINGLE_workload/` and `SYSU_workload/` continue to render from the same five models.

**Tech Stack:** Python 3 standard library (`decimal`, `unittest`), Bash, Vdbench 5.04.07 parameter files, Markdown.

## Global Constraints

- Apply only to the five Vdbench workloads; leave both HPC IOR workloads and fixed-hot experiments unchanged.
- Every crossfade is exactly `old/new = 75/25, 50/50, 25/75`, with each step lasting 10 seconds.
- Every formal workload remains exactly 600 seconds in total.
- Do not add a transition when only `fileio` changes and the data hotspot is unchanged.
- Preserve the existing capacities, ranks, file sizes, Zipf(0.99), read-only operations, 4 MiB transfers, Direct I/O, and `fwdrate=max`.
- Preserve the untracked `资料/` directory.

---

### Task 1: Shared profile and crossfade primitives

**Files:**
- Modify: `workload_common/models/common.py`
- Modify: `workload_common/tests/test_layout.py`

**Interfaces:**
- Produces: `ranked_profile(...) -> dict[Bucket, Decimal]`, `combine_profiles(...) -> dict[Bucket, Decimal]`, and `blend_profiles(old, new, new_share) -> dict[Bucket, Decimal]`.
- Guarantees: every returned full profile has positive skews whose exact decimal sum is its requested total; every blended 100% profile sums to exactly 100.

- [ ] **Step 1: Add tests for exact 75/25, 50/50, and 25/75 profile blends.**
- [ ] **Step 2: Run the focused test and verify it fails because the helpers do not exist.**
- [ ] **Step 3: Implement minimal decimal profile construction and blending with 12-decimal correction.**
- [ ] **Step 4: Run the focused test and verify it passes.**

### Task 2: MapReduce, GraphChi, and HPC crossfades

**Files:**
- Modify: `workload_common/models/mapreduce.py`
- Modify: `workload_common/models/graphchi.py`
- Modify: `workload_common/models/hpc.py`
- Modify: `workload_common/tests/test_mapreduce.py`
- Modify: `workload_common/tests/test_graphchi.py`
- Modify: `workload_common/tests/test_hpc.py`

**Interfaces:**
- Produces: three 10-second transition RDs after each of the first three 120-second stable RDs, followed by a final 150-second stable RD.
- MapReduce blends complete `85/1/1/13%` pool profiles, retaining the background share at 13%.
- GraphChi blends complete seven-window PSW profiles, automatically retaining weights for windows shared by adjacent stages.
- HPC blends startup/checkpoint/history group profiles while retaining sequential reads.

- [ ] **Step 1: Change model tests to require 13 RDs, durations `120,(10×3),120,(10×3),120,(10×3),150`, exact skew sums, and 600 seconds.**
- [ ] **Step 2: Run the three focused tests and verify they fail against the four-RD implementation.**
- [ ] **Step 3: Refactor the three models to emit stable profiles and transition blends.**
- [ ] **Step 4: Run the focused tests and verify they pass for both physical layouts.**

### Task 3: AI training and inference crossfades

**Files:**
- Modify: `workload_common/models/ai_training.py`
- Modify: `workload_common/models/ai_inference.py`
- Modify: `workload_common/tests/test_ai_training.py`
- Modify: `workload_common/tests/test_ai_inference.py`

**Interfaces:**
- Training keeps logical budgets `160×3 + 40×3`: each dataset epoch uses 130 stable seconds plus a 30-second crossfade to the next hotspot; the second current-checkpoint period uses 10 stable seconds plus a 30-second crossfade to old-checkpoint recovery.
- Inference keeps six 100-second logical budgets: unchanged-hotspot prefill/decode boundaries remain direct; the final 30 seconds before active→next, next→prefix, and prefix rank1→rank2 are three-step crossfades.

- [ ] **Step 1: Add failing tests for the exact AI RD timelines, only the true hotspot boundaries, exact 100% skew sums, and 600 seconds.**
- [ ] **Step 2: Run both focused tests and verify RED.**
- [ ] **Step 3: Implement the two schedules using shared profiles and transition blends.**
- [ ] **Step 4: Run both focused tests and verify GREEN for single-node and SYSU layouts.**

### Task 4: Rendered configs, documentation, and regression

**Files:**
- Modify: ten tracked `rendered/run_test.vdb` files through the existing renderers.
- Modify: ten workload `README.md` files.
- Modify: `SINGLE_workload/WORKLOAD_SUMMARY.md`
- Modify: `SYSU_workload/README.md`
- Modify: tests/helpers only if needed to validate variable FWD counts safely.

**Interfaces:**
- Produces: user-visible timelines that distinguish logical phases from Vdbench transition sub-RDs and state that crossfade ratios are controlled experimental parameters rather than paper measurements.

- [ ] **Step 1: Render all five workloads in both environments.**
- [ ] **Step 2: Update documentation with stable intervals, transition intervals, and the 600-second accounting.**
- [ ] **Step 3: Run both full unittest suites and every workload validation script.**
- [ ] **Step 4: Confirm IOR/fixed-hot paths and `资料/` are unchanged, then review the final diff.**
