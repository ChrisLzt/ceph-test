# FWD-Bounded Rank Layout Design

## Goal

Keep every formal Vdbench RD at or below 512 matched FWDs while preserving each workload's total capacity, file-size layout, Zipf(0.99), read pattern, 600-second duration, and 30-second hotspot crossfade.

## Rank Layout

The single-node and SYSU layouts continue to share the same logical rank counts:

| Workload | New rank layout |
|---|---:|
| MapReduce | 24 ranks per pool |
| GraphChi | 4 shards, 40 ranks per shard |
| HPC Vdbench | 40 ranks per group |
| AI training | 40 ranks per group |
| AI inference | 40 ranks per group |

All logical capacities divide exactly: MapReduce pools contain 96/96/96/2112 units, each GraphChi shard contains 600 units, HPC and inference groups contain 800 units, and AI training groups contain 2080/160/160 units.

## GraphChi Simplification

Remove the `window_srcXX_dstYY` layer completely. The dataset contains four equal shards; each shard contains 40 equal-capacity ranks, and every fixed file-size class independently follows Zipf(0.99) across those ranks.

The four 150-second logical stages process shards 00, 01, 02, and 03 in order. A stable stage reads only its current shard. At each boundary, the existing three 10-second crossfade RDs blend the old and new shard profiles at 75/25, 50/50, and 25/75. Every shard is therefore accessed during the complete run, but inactive shards receive no accesses during another shard's stable interval.

This model keeps GraphChi's shard-oriented sequential processing as its application inspiration, but no longer claims to reproduce Parallel Sliding Windows. Shard equality and shard-internal Zipf are controlled experiment parameters, not measurements from the GraphChi paper.

Existing `window_src*` data directories are incompatible with the new layout. GraphChi prepare wrappers must remove those legacy directories before creating the shard/rank dataset.

## FWD Bounds

An RD's matched FWD count is the number of selected ranks multiplied by the physical layout's file-size classes. Crossfades select the union of the old and new profiles.

| Workload | Single-node maximum | SYSU maximum |
|---|---:|---:|
| MapReduce | `4 × 24 × 3 = 288` | `4 × 24 × 5 = 480` |
| GraphChi | `2 × 40 × 3 = 240` | `2 × 40 × 5 = 400` |
| HPC Vdbench | `2 × 40 × 3 = 240` | `2 × 40 × 5 = 400` |
| AI training | `2 × 40 × 3 = 240` | `2 × 40 × 5 = 400` |
| AI inference | `2 × 40 × 3 = 240` | `2 × 40 × 5 = 400` |

MapReduce always selects all four pools, so its maximum occurs in both stable and crossfade RDs. Every maximum is below 512. Prefix wildcards remain in generated RDs; the reduced counts are an additional model invariant rather than a return to explicit FWD lists.

## Validation

- Unit tests assert each constant, capacity division, data path, phase duration, and expected stable/crossfade FWD count.
- The shared validator rejects any formal run RD matching more than 512 FWDs, even when a wildcard is used.
- Both suites are regenerated and all 20 prepare/run configs must pass Vdbench 5.04.07 `-s -e 2` simulation.
- The two IOR workloads are unchanged.

## Migration Boundary

The new GraphChi dataset cannot reuse the previous window-based files. MapReduce, HPC, and both AI datasets also change rank directory boundaries, so their existing prepared data cannot be reused after regeneration. No prepare or formal workload is executed as part of the source change.
