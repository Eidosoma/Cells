# REF-005c matched pump–leak pilot handoff

2026-09-16, D117. **Prepared for one detached attempt; no trajectory pass claimed.**
See the [registered contract](../docs/BETSE_MATCHED_PUMP_PILOT.md) and
[native prerequisite closeout](REF005B_PUMP_LOOP_CLOSEOUT.md).

The new adapter maps measured native geometry/chemistry into the unchanged
public `finite_extracellular@2` model. Boundary masks reduce transport area,
not full membrane capacitance. Actual immutable-ion charge and effective bath
volume are preserved; neither simulator is fitted to the other's outputs.

**37 software checks pass in 24.07 s** in
[`ref-005c-pilot-checks-01.xml`](ref-005c-pilot-checks-01.xml). These cover:

- Prerequisite identity and registered scope; public-schema round trips for
  all six preparations and rejection of nonuniform membrane aggregation.
- NumPy/eager/compiled held-state mapping for all six initial conditions and
  a later masked state; saved-native update reconstruction for all six cases.
- Short DOP853 base/tight and Radau reference smoke, refinement floor/rejection
  rules, off-grid observation rejection and incomplete-phase refusal.
- A real two-step compiled production run with a complete saved-checkpoint
  load and bitwise-equal full-state restart suffix.

These checks are not the full matched trajectory campaign. No production,
upstream or historical captured source is edited for this adapter.

```text
.venv/bin/python -B validation/betse/pump_matched_pilot/pilot_job.py launch runs/ref-005c-matched-pump-2026-09-16/pilot-01 --tests reports/ref-005c-pilot-checks-01.xml
```

The fresh attempt registers **629 source/configuration/contract inputs** and
binds the passing software receipt, D116 independent closeout and original
native capture. Its launch acknowledgement records PID, UTC time and registration
SHA-256 in `launch.json`; living progress indexes record the returned receipt.
Do not edit this handoff or any registered source after launch.

The gated campaign checks 48 saved states on three backends, then 18 independent
reference solves, 36 native runs / 18 exact observer pairs, 24 production Cells
trajectories and six exact checkpoint restarts. Six control cases run for 1 ms,
with registered native/Cells refinement ladders and five common elapsed-time
observations. Full native/reference/Cells evidence is retained separately from
the producer's comparison summaries.

Limits: CPUs 0–3, one BLAS thread, 120 s mapping / 120 s reference / 300 s native /
420 s Cells / 1,080 s total; 64 MiB/file and 512 MiB disk artifacts, not RAM.
Logs, partial outputs and terminal failure are durable. Do not overwrite or
automatically retry an attempt; a failure requires interpretation before any
explicit amendment. A successful launch is not a successful calculation.

Success status is `matched_pump_pilot_pass_pending_independent_review`.
Independent review waits for the user's next instruction. No polling, automatic
follow-up audit/regression, relaxation/equilibrium claim, experimental validation,
GPU test or release promotion is part of this attempt.
