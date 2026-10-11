# D128: disjoint output ownership and shared-worker integration gate

Correct the D125 campaign harness's output-path collision without modifying
executed code or production Cells. D127's continuation stopped after 79.799 s:
one Cells case completed all three windows, then a checkpoint-enabled case
tried to write its full recording into the existing ordinary-baseline `full/`
directory. The production writer correctly refused to overwrite it. Preserve
both earlier failed attempts; no numerical mismatch was reported.

## Output layout

Each new case has separately owned leaves:

```text
cells/<case>/<step>/<execution>/
  baseline/                 ordinary full-run evidence
  recordings/full/          windowed full-history evidence
  recordings/observations/  windowed observations-only evidence
  recordings/checkpoints/   windowed checkpoints-only evidence
  resumed/                  full run from a loaded checkpoint
  comparison.json
```

`output_context.case_paths` rejects existing, linked, escaping or overlapping
output paths before simulation. All selected case paths are checked before the
first case. `output_worker.worker` owns both ordinary and windowed writes, uses
the declared recording path to load its restart, and rechecks that baseline
bytes remain unchanged after every other operation in the case. Comparison
reports record the layout version, paths and baseline file hashes. Existing
non-overwrite protections remain in force.

The numerical checkers (`Arrays`, `WindowCheck`, `baseline`, `disk_check`) are
imported unchanged from the frozen D125 adapter. The worker retains its exact
specification, integration, window, disk, restart, zero-length and sparse-readout
checks. A source-level regression checks the three numerical branches against
the old worker, allowing only the output-path differences. No production module,
upstream source, physical law, timestep, duration or tolerance changes.

## One detached qualification, two gated phases

1. `probe`: **one actual pump+leak / 25 µs compiled / 1 ms case**, through the
   exact same `output_worker.worker` used for the matrix. It writes an ordinary
   baseline, compares all three window widths, writes all three disk policies,
   loads the complete 0.5 ms checkpoint, checks full/windowed restarts and a
   zero-length continuation. Its result, all files and empty stderr must pass
   before the controller seals `probe-complete.json`.
2. `matrix`: the original **24 Cells cases / 72 window comparisons / eighteen
   disk recordings / six full and six windowed restart suffixes / six zero-length
   / two sparse controls**. Both controller and worker authenticate the completed
   probe before this phase can start. Probe output is separate and never counted
   as a matrix case. The matrix still computes all 24 cases afresh.

The short pre-launch software suite exercises the real worker's filesystem and
dispatch sequence with **explicitly stubbed physics**, plus path overlap,
baseline mutation, scope/count refusal, source binding and failed/tampered probe
gates. Those fast tests are not numerical evidence. The actual-model probe runs
detached as the first phase of this one preregistered job, not a separate
automatically launched follow-up campaign.

Reuse the already compared 36 native rows/eighteen pairs using the frozen D127
hash-chain checker. Bind all 964 native packet files and all 24 files of the
stopped Cells continuation; neither is edited. No partial Cells result is
promoted or reused. Independent native/live review remains separate.

Limits remain CPUs 0–3, one BLAS thread, **1,800 s overall / 750 s matrix /
16 GiB Cells address space / 32 MiB per file / 512 MiB aggregate / 1 GiB disk
reserve**. The added actual-worker probe has **120 s**. Apply disk quotas to
the whole job, not each phase independently. Failed/timed-out probes do not
dispatch a matrix; deadlines terminate/reap the whole child process group.
No polling, automatic retry, audit, further regression or longer-horizon run
follows this job. Success is producer qualification pending independent review,
not biological, GPU, constant-native-memory or whole-BETSE parity.

[Handoff](../../../reports/REF005D_OUTPUT_LAYOUT_HANDOFF.md).
