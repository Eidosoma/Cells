# SPEC-010 kinetic finite-bath development handoff

2026-09-16, D113. **Implemented development extension; full acceptance pending.**
See the [contract and example](../docs/KINETIC_FINITE_BATH_MODEL.md) and the
[reviewed process prerequisite](SPEC010_PROCESS_CLOSEOUT.md).

## Implemented

`finite_extracellular@2` is selectable through ordinary schema-1 configuration,
with separate immutable pump/metabolism/membrane/model types and a distinct
flat numeric layout. This working tree is **0.16.0.dev0**, not the accepted
0.15.0.dev0 or stable 0.14.0 source context; 55 production modules are captured.

Pump capacity is extensive, with explicit Na/K roles, fixed -3/+2 stoichiometry,
positive metabolic pools and saturation parameters. The chemical drive derives
from the declared maintained ATP/ADP/Pi inputs; no prescribed-drive alias or
time-varying metabolism controls. Absent and padded routes are neutral; blocked
present pumps still undergo physical-domain checks.

Reuse narrowly extracted geometry, passive readouts, conservative scatter,
accounting and observation helpers. No new integrator, synthetic-pump subtraction
or runtime monkeypatch. Local and shared-outside inventories own one opposite
membrane transfer; junctions never enter the outside ledger. The ten evolving
state/history fields are unchanged. Strict snapshot source identity remains.

The kinetic model has stage-domain checks and conservative whole-cubic pump
enclosures, with explicit rounding assumptions and conservative-refusal
diagnostics. The initial step ceiling is 100 µs, not v1's 1 ms; this is a guard,
not a general accuracy claim. Data, not organism names, selects species/owners.

## Bounded checks completed before launch

- [Schema/layout](spec-010-family-schema-01.xml): **43 pass / 1.61 s**.
- [Stage equations and interpolation](spec-010-family-dynamics-02.xml):
  **13 pass / 12.90 s**, including six independent complete RHS comparisons,
  role permutations, absence/blocking, unsafe interiors, conservative refusal,
  and 80-digit polynomial/affinity checks. Receipt 01 also passed in 13.13 s;
  receipt 02 additionally checks quiet rejection of invalid physical inventory
  with absent/zero-capacity/blocked pumps. No state is floored or repaired.
- [Preserved old-family equivalence](spec-010-family-legacy-01.xml):
  **1 pass / 3.61 s**, comparing all fourteen v1 preparations against the
  pre-edit 52-module archive in a separate process: exact fingerprints,
  serialization, state/layout arrays and complete initial NumPy RHS values.
- [Compiled ordinary-runner smoke](spec-010-family-smoke-01.xml):
  **1 pass / 10.36 s**, off-grid observations, energy ledger, artifacts/snapshot.
- [Channel/junction and split-event smoke](spec-010-family-composition-01.xml):
  **2 pass / 18.28 s**. This is software composition evidence, not biological
  calibration or a new BETSE-coupled channel/junction qualification.
- [Controller checks](spec-010-family-controller-02.xml): **8 pass / 0.34 s**
  (receipt 01: 8 pass / 0.21 s).
  Read-only collection confirms **422 tests** across the two registered scopes.

No physical comparison budget or law was tuned to achieve these checks.

## One detached attempt

The new matrix has **74 tests**, including 12 ordinary 10 ms trajectories
(six NUM-011 cases × 100/50 µs), compared against both saved DOP853 and Radau
references with their original state/voltage/accounting budgets. Save full
ordinary-runner outputs, complete 6 ms checkpoints, all twelve bitwise restart
suffixes and per-run comparisons. No native or independent reference solver is
rerun. Also cover fresh-process checkpoint loading, branches, eager/compiled
agreement, off-grid events, scalar windows, heterogeneous independent batches
and independent-clock cohorts. Independent worlds are not interacting organs.

The same detached job then runs the existing **348-test** targeted regression
again on the new source context. Historical source-identity suites are not
silently rerouted or weakened. This is **422 tests, not a full release matrix**.
The separately preserved old-context equivalence check remains part of the new
matrix and its original source bytes are authenticated.

`validation/betse/kinetic_family/family_job.py` freezes **601 inputs**: all
production/test/validation/script Python sources, JSON configurations, the
current bytes of every known accepted implementation input (including lock
files/non-Python fixtures), and this contract/handoff.
It binds pre-integration and independent coupled evidence, runtime packages,
software receipts, source archive and exact test coverage before execution,
then authenticates again before success. CPU 0–3, CPU float64, JIT enabled,
one BLAS thread; **1,200 s new-family / 600 s regression / 1,860 s total**;
**64 MiB/file / 256 MiB disk artifacts**, not a RAM cap. Test artifacts are
retained under the job directory; no overwrite or automatic retry.

```text
.venv/bin/python -B validation/betse/kinetic_family/family_job.py launch runs/spec-010-family-2026-09-16/acceptance-01
```

Return after launch, without polling or automatic follow-up review. A success
is `family_checks_pass_pending_review`; a failure is durable and stays rejected.
The launched job's inputs must not be edited until its terminal result has
been inspected on user request.

After review: close the bounded development scope and route broader historical
regressions appropriately, then prepare a matched coupled BETSE pump–leak
comparison. Long relaxation, experimental data, spatial pump composition,
additional transporters, GPU and organ-scale/multirate work remain separate.
