# Remove Vdbench Crossfade States Design

## Goal

Remove the generated `transition_*_25`, `transition_*_50`, and
`transition_*_75` run definitions from all five formal Vdbench workloads.
Keep only workload lifecycle stages with direct hotspot changes at stage
boundaries.

## Scope

The five workload models under `workload_common/models/` are shared by the
single-node `SINGLE_workload` suite and the 12-node `SYSU_workload` suite. The
change therefore applies to both suites and their rendered configurations.

The following properties remain unchanged:

- total physical capacities and file-size layouts;
- Zipf alpha of 0.99;
- read modes and stage ordering;
- `fwdrate=max` and 4 MiB transfers;
- total run time of 600 seconds.

Rank resolution changes to 100 ranks per GraphChi shard, 80 ranks per HPC
group, 100 ranks per AI-training group, and 80 ranks per AI-inference group.
MapReduce remains at 24 ranks per pool. AI-training units change from
`2080/160/160` to `2000/200/200`, preserving the total while making all three
groups divisible by 100. Dataset epochs retain hot ranks 1, 2, and 3.

## Stage Durations

- MapReduce: four stages of 150 seconds.
- GraphChi: four stages of 150 seconds.
- HPC/WRF: four stages of 150 seconds.
- AI training: three dataset stages of 160 seconds followed by current and old
  checkpoint stages of 60 seconds.
- AI inference: six stages of 100 seconds.

AI inference retains separate prefill and decode stages even when their hot
data is identical, because their sequential and random read modes differ.

## Implementation

Each model emits one RD per formal stage. Crossfade profile construction and
the 30-second deductions from stable stages are removed from the five model
emitters. Shared helpers may remain available if other, non-formal workloads
still depend on them; unused helpers should only be removed when repository
search confirms that no caller remains.

Existing unrelated worktree changes, including Vdbench skew-checking changes,
must be preserved.

## Documentation and Validation

Update the single-node and SYSU summaries/readmes to describe direct hotspot
switches instead of 25/50/75 crossfades. Tests must verify:

- no formal run configuration contains an RD named `transition_*`;
- each suite still totals exactly 600 seconds per workload;
- the expected formal stage names and durations are present;
- all generated Vdbench configurations parse with Vdbench 5.04.07;
- existing capacity, rank-count, FWD-bound, and IOR validations continue to
  pass.
