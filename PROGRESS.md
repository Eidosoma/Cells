# Progress

Last updated: 2026-11-08 UTC.

This is the source of current implementation status. Milestone definitions live
in [Roadmap](docs/ROADMAP.md), scientific updates in
[Scientific basis](docs/SCIENTIFIC_BASIS.md), and design choices in
[Decisions](docs/DECISIONS.md). The complete status history up to 8 November
2026, with every earlier run summary and its evidence links, is preserved in
[the archived progress file](docs/history/PROGRESS_BEFORE_2026-11-08.md).

## Current position

- **Reset on 8 November: BETSE is an external reference, not part of the engine.**
  From 30 October the work drifted into re-hosting and transcribing BETSE inside
  `src/cells` (`betse_native_*`, about 110K lines; `betse_normal_*`, about 50K
  lines). The resulting end-to-end demonstration compared BETSE with BETSE; no
  Cells engine model ran in it. That track is frozen at checkpoint `7e9873a` and
  superseded, and tagged `native-betse-frozen-2026-11-08`. Its code and evidence
  are preserved. The rule is now in `AGENTS.md`.
- **Native demonstration outcome:** 15 actual launches (6–8 November) never
  reached tissue geometry. Every failure was in the provenance, observer, memory
  or wall-time layer. [Actual16](/mnt/workspaces/Cells/native-basic-end-to-end-20261105-01/actual-original-16/failure.json)
  stopped at its 1,800-second limit at 16:06:11 UTC, 20.5 minutes into phase
  construction. This track produced no numerical BETSE or Cells result.
- **Single lead agent from 8 November**, with at most four subagents on disjoint
  files. Work continues on `main`; milestones are tagged.

## Plan: BETSE parity on CPU and L4, then JUPITER (from 8 November)

Target: BETSE parity of the Cells engine, compared against output from plain
BETSE and run on CPU and the local L4. The JUPITER allocation (10,000 GH200
GPU-hours over about three months) follows; this session moves there when it
starts, and production design is deferred until parity is established.

| Step | Work | Status |
| --- | --- | --- |
| 1 | Plain BETSE reference outputs (default world; seven-cell fixture) | Done |
| 2 | Coverage map of default-world mechanisms, and the parity ladder | In progress |
| 3 | Cells run of BETSE's default world, compared with step 1 | Next |
| 4 | The same comparison on the L4 GPU | L4 path checks in progress |
| 5 | Further mechanism families from the parity ladder, on CPU and L4 | Planned |
| 6 | JUPITER environment and one-node pilot | Recipe in preparation |

## Runs

Per-run summaries for this plan are added here, newest first, each linking its
machine-readable inputs, results, checks and failures.

- **Plain BETSE reference outputs (8 November).** Unmodified BETSE v1.5.0 CLI,
  isolated HOME, CPUs 1–2; tools `validation/betse/betse_reference_run.py` and
  `betse_reference_extract.py`. [Index](/mnt/workspaces/Cells/betse-reference-20261108-01/index.json)
  of four cases, each with its run result, extract manifest and checks:
  - default world (headless_core): 226 cells, 1,298 membranes, 24×25 ECM grid;
    seed 11.1 s, INIT 11.8 s, SIM 9.6 s, peak 239 MiB;
  - dense default world (sampling = dt; 499 INIT / 349 SIM samples): its own
    unseeded geometry (222 cells, 25×25 grid);
  - dense run on the standard seed: histories bit-identical at all common
    samples, so dense sampling does not change dynamics;
  - seven-cell REF-003c configuration (YAML hash reproduced; new geometry).

  Comparison notes: sample k is the state after k+1 updates, and the end state
  is only in `*_final.npz`; BETSE uses F = 96485 and R = 8.314; geometry differs
  per run (unseeded RNG), so each comparison uses its case's own
  `geometry.npz`; INIT `P_cells_time` is an aliased series. Default-world SIM
  Vmem moves only about 3 µV, so the dense INIT is the informative comparison.
