# NUM-011 kinetic pump / finite-bath candidate handoff

2026-09-16, D109. The user authorized source review, realistic pump integration
and coupled validation. D108's [source-contact audit is closed](REF005A_PUMP_CONTACT_CLOSEOUT.md).
The next numerical prerequisite is implemented under the
[integration contract](../docs/KINETIC_PUMP_INTEGRATION.md). Production integration
is explicitly pending this coupled gate and its saved-evidence review.

## What is implemented

A pure array candidate combines the audited substrate-dependent pump with the
unchanged production GHK process and checked JAX RK4 primitive. It uses one
signed membrane transfer, stage-consistent cell/bath chemistry, charge-derived
voltage, cycle/leak histories and energy accounting. It does not call or subtract
the synthetic pump, patch a production model, or rerun a native BETSE cell world.

The independent scalar RHS uses direct mass action and symmetric exponential
leak arithmetic, with DOP853/Radau reference solves in a separate process. The
candidate evaluates NumPy and compiled CPU/float64 JAX, with complete endpoint
state, explicit event grids and full-state restart suffixes.

Six synthetic 10 ms cases: pump–leak, pump-only, leak-only, all-blocked,
4–6 ms pump suppression/release, and two heterogeneous cells sharing one finite
bath. The frozen candidate has **12 reference trajectories, 24 NumPy/JAX
trajectories and 12 restart suffixes**. Fixed candidate steps are 100/50 µs.
No step is yet accepted for the production model or arbitrary regimes.

## Bounded software results

Final [receipt 03](num-011-kinetic-pump-checks-03.xml): **37 passed in 5.92 s**,
with warnings treated as errors and no failures/errors/skips. Coverage includes
independent complete RHS, material/charge closure, dissipation, explicit species
mapping, invalid-trial refusal, no synthetic-pump substitution, control boundaries,
blocked transfer/history separation, actual four-step Radau/NumPy/compiled-JAX
smoke, eager/compiled instantaneous rates, complete restart, saved-state
corruption, and no-poll/durable-failure controller checks.

Final software receipt SHA-256:
`dc482407d7c2d32fb5c291887c7941eb204e89dd1458be4d72ea43cdff4dd3f0`.
Prelaunch repository lint, formatting (733 files) and whitespace checks pass;
all 1,442 local file links checked across the current indexes and new documents
resolve. The 14 candidate source inputs, source-contact closeout and all 352
preserved implementation files authenticate before registration.

The comparator's synthetic fixtures check **4,070 saved-state columns / 30 groups
and 12 refinement groups**. They are not full-panel simulation evidence.
Earlier receipts are retained:

- [01](num-011-kinetic-pump-checks-01.xml): 27 passed / one failure / two warnings,
  5.58 s. The reference smoke ran in a process already containing Cells, correctly
  tripping its isolation guard; deliberately nonfinite rejection inputs also
  exposed unsafe arithmetic in the candidate's rejection predicate.
- [02](num-011-kinetic-pump-checks-02.xml): 28 passed / 5.98 s. Run the reference
  smoke in its separate interpreter and make the predicate's voltage arithmetic
  neutral on already-invalid input. No physical state, rate law or tolerance is
  clipped, repaired or changed.
- Receipt 03 adds complete saved-comparison/restart corruption coverage.

The short source-contact audit has its own separate 17-test receipt and source
capsule; it is not re-executed by this candidate. Accepted implementation remains
352 unchanged files / 51 production modules; stable 0.14.0 and accepted
development 0.15.0.dev0 are not promoted or replaced.

## Capture boundary

Freeze 14 source/contract/report inputs and the final software XML before launch.
Authenticate the source-contact audit, original 15-file contact capture / 11
sources, accepted implementation and pinned worker package inventories. The full
panel has not run merely because these software fixtures pass.

One detached attempt: CPUs 0–3, **240 s per worker / 600 s controller**, **16
MiB/file / 64 MiB aggregate disk artifacts**. The artifact quota is not a RAM
limit. Record durable registration, sources, logs, full numeric payloads,
comparison rows and terminal completion/failure. A success remains
`coupled_candidate_pass_pending_audit`, not an accepted production pump.

Return after launch. No polling, automatic retry, post-capture audit or regression.
Inspect the saved outcome on user request; then review the numerical evidence
before production preservation, versioned configuration/kernel integration,
ordinary-runner acceptance and old-model regression. Native whole-cell pump
correspondence, longer relaxation, biological validation and GPU remain later
explicit steps toward the BETSE-level realism target.
