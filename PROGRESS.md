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
  superseded. Its code and evidence are preserved. The rule is now in `AGENTS.md`.
- **Native demonstration outcome:** 15 actual launches (6–8 November) never
  reached tissue geometry. Every failure was in the provenance, observer, memory
  or wall-time layer. [Actual16](/mnt/workspaces/Cells/native-basic-end-to-end-20261105-01/actual-original-16/failure.json)
  stopped at its 1,800-second limit at 16:06:11 UTC, 20.5 minutes into phase
  construction. This track produced no numerical BETSE or Cells result.
- **Single lead agent from 8 November**, with at most four subagents on disjoint
  files. Work continues on branch `takeover-jupiter`.

## JUPITER week plan (from 8 November)

Target: a Cells-engine run of BETSE's default world compared against plain BETSE
output; the same model qualified on the L4; then a JUPITER pilot and production
within the 10,000 GH200 GPU-hour budget.

| Step | Work | Status |
| --- | --- | --- |
| 1 | Plain BETSE reference outputs (default world; seven-cell fixture) | In progress |
| 2 | Coverage map: default-world mechanisms → Cells models and gaps | In progress |
| 3 | Cells run on BETSE's default world, compared with step 1 | Next |
| 4 | L4 GPU qualification of that model; production ensemble definition | Next |
| 5 | JUPITER environment and one-node pilot | Preparation in progress |
| 6 | JUPITER production as independent one-node jobs | Not started |

## Runs

Per-run summaries for this plan are added here, newest first, each linking its
machine-readable inputs, results, checks and failures.
