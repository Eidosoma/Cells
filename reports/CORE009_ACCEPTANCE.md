# CORE-009 finite extracellular production acceptance

2026-09-10 UTC. **Complete — bounded CPU/JAX production acceptance.**
All **150 targeted and 3616 regression tests pass**, with no failures, errors or
skips in the final five-context matrix. The final capture exactly reproduces the
first run's numerical arrays. The first matrix's two missing-interpreter failures
remain retained in the [correction record](core-009-regression-correction.json);
no physics, reference input or tolerance changed to resolve them.

The new family is `finite_extracellular@1`, Cells 0.14.0. Cells now change a
shared, finite outside ion inventory, which feeds back into their transport.
The [production contract](../docs/FINITE_EXTRACELLULAR.md) specifies the limited
physics, ten state fields, independent capacities and prospective acceptance.
The [one-cell example](../configs/finite_extracellular_cell.json) starts small;
the implementation also handles data-defined multiple cells and sparse junctions.

## Preservation and numerical authority

[Pre-edit preservation](core-009-preservation.json) authenticated accepted 0.13.0
and saved 356 source/configuration/documentation files, including all 46 old
production modules. Archive SHA-256:
`73b152cfbeb016c9d842753fda21620f53fe8449a5fceb01f6cd6bac30dd9a15`.
Reference scripts, scientific inputs and saved evidence remain unchanged.
Original packaging/source guards execute under that preserved source context,
not under a silently relaxed validator.

The unchanged [NUM-009 v2 reference](NUM009_REFERENCE_V2.md) supplies fourteen
synthetic 0.05–0.3 s cases and saved refined trajectories. It selected 1 ms
RK4/cubic with passing 0.5 ms refinement; this is not a timestep guarantee for
arbitrary new parameters, large tissues or long runs. Its preserved-source
audit rechecks 242 payloads/43 sources and exactly replays 251400 sampled rows.
No reference ODE was rerun.

The [post-edit historical audit](core-009-preserved-evidence-audit.json) also
passes for accepted CORE-008 and the original stopped NUM-009 v1 attempt.
V1 remains stopped/not qualified. Its thirteen prospective complete-session
tests remain explicitly unexecuted; the maintained v2 counterparts do run.

## Engineering evidence

The [final targeted receipt](core-009-targeted-03.xml) records **150 passing
tests**, zero failures/errors/skips, in 109.444 s of JUnit context time. Tests cover independent
complete-state derivatives and frozen trajectories; outside feedback and
conservation; every padded state leaf; real-stage and unsampled cubic refusals;
hidden cycle history, restart, branch and independent worlds; species/ID
renaming and permutation; and one-/five-cell extensive scaling.
The saved-data auditor independently checks all **42 derived readouts**, not
just voltage, and refuses all 33 rehashed state/readout corruptions.

Two earlier test-fixture failures are retained in the
[preflight record](core-009-preflight-closeout.json): an accidentally duplicated
edge in the cycle witness, and an incorrect expected readout count. Neither
required changing physical laws, numerical settings or tolerances. The cycle
witness is an algebraic checkpoint test, not an independently qualified cycle
trajectory. Derived extreme-float arithmetic is explicitly refused.

## Formal session

The final captured session,
[`acceptance-02`](../runs/core-009-2026-09-10/acceptance-02/verification.json),
passes with **631.733625 s recorded verification time and 446951333 bytes**
(426.246 MiB) of evidence. The prospective limits were 3600 s and 2 GiB,
four pinned eager CPU lanes and single-thread numerical libraries.
The terminal read-only audit follows the recorded verification interval.
These are acceptance-workload costs, not a simulator speed benchmark.
No numerical formal attempt failed or required a budget/scientific amendment.
The [first successful numerical session](../runs/core-009-2026-09-10/acceptance-01/verification.json)
remains retained but is excluded from final release acceptance because its
implementation capsule predates the test-launcher correction. It recorded
686.208126 s and 446950703 bytes; those records were not rewritten.
The [read-only repeat audit](core-009-repeat-audit.json) authenticates all 830 old
payloads and finds **25,654 arrays exactly equal across all 408 numerical files**.
All 48 production modules are identical; only the launcher and its test module
differ between the two captured implementations.

The verification SHA-256 is
`247e2bd8f00cb58736e2b6e7ef2bf0c0855742fa8e929e6067ef861bc2ad3b92`.
The [standalone audit](core-009-production-audit-02.json) verifies 830 payloads and
256 captured implementation files, including 48 production modules.
[Checkpoint loading](core-009-checkpoint-load-02.json) passes for all 235 scalar
and 21 cohort snapshots with complete state, layout and source identity.

All fourteen cases pass eager/JIT reference comparison and exact fresh-process
restart. A future-only branch retains the complete preparation: **43 scalar
outputs** in total. Two full scalar-window runs and four original/resumed
cohorts replay exactly. The monovalent cohort contains eleven independent worlds;
the calcium-containing cohort contains three. Each world owns its outside,
including when it finishes before other worlds.

Earlier-model results remain exact: 78 scalar cases / 3511 arrays, 1777 windows,
ten batches / 44 worlds / 2042 arrays, and 2868 further arrays across forty
multispecies/channel/physical-graph cases. All ten earlier families are covered;
the driver's inherited progress label saying “nine” is cosmetic.
All 162 old scalar and 16 old cohort checkpoints load under preserved 0.13.0,
with exact old physical-graph replay and strict current-source migration refusal.

The [trajectory review](core-009-trajectory-review-02.json) records the measured
maxima across accepted and observed states:

| Quantity | Maximum error/residual |
| --- | --- |
| Cell voltage | 1.910208e-8 V |
| Membrane m/h gate | 1.201560e-7 |
| Junction gate | 1.682845e-9 |
| Outside concentration | 5.939372e-5 mM |
| Local charge accounting | 1.161330e-16 V |
| Global increment-charge accounting | 6.328881e-28 C |
| Resolved energy accounting | 6.498741e-9 pJ |

Worst observed normalized trajectory error is 0.593937 (59.4% of its declared
budget), in the tiny-outside depletion stress. No dissipation decrease is
detected. Outside potassium drops by 80.80565756% in that synthetic test.
Junction-only exchange leaves accepted and sampled outside increments exactly
zero. None of these numbers is a biological calibration or universal bound.

## Regression and release closeout

The [first matrix](core-009-regression-01/verification.json) ran all 3614 tests:
3612 passed and two failed, with no errors or skips. Current production passed
1969 tests; preserved 0.10/0.11/0.12 passed 971/205/213. The final preserved
0.13 context passed 254 and failed two subprocess import-isolation tests because
its local `.venv/bin/python` path was absent. That matrix remains failed.

The correction links only the isolated workspace's environment directory to the
already pinned interpreter. No scientific file or source is linked, no original
test is edited, and no evidence/source guard is relaxed. Its full
[256-test recheck](core-009-finite-context-correction-01/verification.json) and
[eight launcher tests](core-009-context-correction-01.xml) pass. Final acceptance
has been recaptured successfully. The
[complete corrected matrix](core-009-regression-02/verification.json) passes:

| Source context | Tests | JUnit context time (s) |
| --- | ---: | ---: |
| Current 0.14.0 production | 1971 | 914.936 |
| Preserved 0.10.0 reference | 971 | 159.089 |
| Preserved 0.11.0 channel reference | 205 | 19.016 |
| Preserved 0.12.0 physical-graph reference | 213 | 15.594 |
| Preserved 0.13.0 finite-outside reference | 256 | 59.405 |
| Total | 3616 | 1168.040 |

These are summed test-context times, excluding temporary-copy/driver overhead,
not a simulator performance benchmark. The thirteen prospective v1
complete-session tests remain explicitly unexecuted, not counted as passes;
their maintained v2 replacements and original stopped-evidence checks run.
Matrix SHA-256:
`e64950a3e14518562404bf72a7ddefa043992b1b2a8a51a751346636a91d2916`.

The [release audit](../runs/core-009-2026-09-10/release-audit.json) authenticates
all 830 accepted payloads, 256 current/captured files, 356 archived members,
242 reference payloads and thirteen final matrix receipt/XML/log payloads.
It also binds the unchanged first formal session, failed first matrix and
passing correction checks. Only `acceptance-02` is included in final acceptance.
The [workspace closeout](core-009-closeout.json) checks all 559 pre-existing
files: **545 unchanged, fourteen expected documentation/API/version edits,
none missing**. Shared solver/scheduler/I/O and all earlier model equations are
unchanged. All 251 Python files pass lint/format; dependency, whitespace and
eleven-document link/structure checks pass.

## Reproduce and inspect

From the Cells workspace, with the pinned environment and retained earlier
evidence present, re-audit the accepted session without an ODE solve:

```bash
env PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 4 .venv/bin/python scripts/audit_finite_extracellular_build.py runs/core-009-2026-09-10/acceptance-02
```

Fresh verification and regression outputs must use previously unused paths:

```bash
env PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/verify_finite_extracellular_build.py --output runs/core-009-local-check
env PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/test_finite_extracellular_production_build.py --output reports/core-009-local-regression
```

The regression driver creates isolated temporary copies and authenticates the
preserved archives; never extract an old source archive over the working tree.
Old checkpoints require their archived source and compatible numerical runtime.
See the [production guide](../docs/FINITE_EXTRACELLULAR.md) for the small example
and the [README](../README.md#verify) for test-context and storage requirements.

## Limits and next architecture step

No GPU execution, optimization, spatial field, tissue barrier, electrode model,
BETSE parity, organ simulation, multirate method or biological validation is
claimed. The descriptive pilot remains closed and the long E02 campaign deferred.
The common runner, numerical method, scheduler and I/O are unchanged; new schema,
state/layout types and registry dispatch give this family its own identity.

The proposed next slice is SPEC-009: a minimal spatial extracellular
transport/electrical-closure contract. Multiple spatial outside compartments
must not simply become independent zero-potential baths. Define inventories,
flux ownership, potential constraints and limiting-case references before
implementing a mesh or distributed GPU communication.
