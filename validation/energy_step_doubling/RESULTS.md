# The step-doubled energy check (FR-18's criterion X): harness and results

This folder holds the harness that registered and judged FR-18's criterion X
(`docs/FR18_CRITERION_X_2026-11-18.md`). It is the independent reference for the engine's opt-in
check `step_doubled_energy@1`, X2 as adopted under D224. The files are byte-identical to the runs of
record. Their digests are in `tools.sha256`, and the runs' own digests are in each run folder's.

| File | Role |
| --- | --- |
| `harness.py` | The FR-18 probe's worlds, ledger paths and plants (the probe's run, unchanged) |
| `recorder_x.py` | Replays each world's accepted steps whole and as two half steps; records R, F, T, O, d, d'' and the plants' contributions |
| `evaluate_x.py` | Applies the registration: X1 and X2, then decisions (a), (b) and (c) |
| `recorder_fr8.py` | Amendment 1's wrapper for FR-8's worlds, built by FR-8's stage-0 builders |
| `evaluate_x_running.py` | Amendment 2's test: the run-level conditions re-evaluated at every row |

## Results

The runs and their machine-readable results are in the workspace,
`/mnt/workspaces/Cells/core-pass-at3-20261118/fr18-x/`:
- **The full set** (`results.json`): 128 worlds, 122 evaluated. Five RK4 worlds are excluded,
  since their energy bound is absolute. cleft_egg was refused at admission; it is run in `cleft/`.
  - X1 does not work: four mixed G1 worlds fail at row 1.
  - X2 works: (a) the refused arms are admitted, with largest ratios 0.49, 0.30 and 0.13; (b) every
    honest world is admitted; (c) FR-3's registered plant is caught.
- **FR-8's worlds** (`fr8/results.json`, amendment 1): H2 at 1 ms over 3600 s, and W0 at 1, 2 and
  5 ms with both bookings. X2 admits all seven. The 10 ms arms are refused at definition time, as
  M5 registered. Nothing past 5 ms was measured.
- **cleft_egg** (`cleft/results.json`): 200 steps, admitted by X2 (largest ratio 0.17), its trace
  limit raised for admission only.
- **Amendment 2** (`amendment2/results.json`): the running form of the order condition and the cap
  refuses 47 admitted worlds, so X2's run-level conditions stay whole-run.
- **The plants:** X2 misses 15 of 378 planted cases. Each lies inside the allowance, which κΣ|a|
  dominates, so X2's sensitivity falls as the steps grow.
- **The cost:** two extra half steps per checked step. The runs' memory figures (13.8 GB and
  52.1 GB) were raised admission limits on whole-horizon trace estimates, not the check's cost.
