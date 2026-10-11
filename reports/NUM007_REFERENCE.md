# NUM-007: coupled cell/channel trajectories

2026-09-09, D050. **Independent CPU numerical qualification and artifact audit
pass.** The predeclared rule selects **0.0005 s (0.5 ms) coupled RK4 with
interval-control cubic Hermite observations**, on all fourteen frozen cases;
the next-finer 0.00025 s trial also passes every case. Production remains Cells
0.11.0. This is not a production channel or a change to any old timestep bound.
All 2770 regression tests pass across current and preserved-reference contexts.

The [prospective protocol](../docs/VOLTAGE_GATED_NUMERICS.md) and
[frozen panel](../configs/reference/voltage_gated_trajectories_v1.json) precede
trajectory evaluation. There are fourteen cases and 98 declared attempts:
three implicit reference settings and four candidate RK4 steps per case.
Horizon, work and artifact limits are fixed; no fit or biological comparison runs.

## What this tests

Both existing species assemblies retain their transport laws, geometry, bath,
channel permeability and abundance. Explicit nonequilibrium gate/charge
preparations exercise feedback, channel-only flow, independently blocked
mechanisms, a 0.1 ms availability pulse and different hidden states with equal
initial open fraction. In the gates-only reduction, ionic routes are off and
voltage remains constant through its owned charge, without an electrode model.

The [independent reference](../tests/reference_voltage_gated_dynamics.py)
evolves ionic increments and native-unit gate equations with hyperbolic transport.
The scalar RK4 candidate evolves absolute amounts through the SPEC-006 Bernoulli
evaluator. Every stage uses one coupled voltage for both amount and gate rates.
Both paths carry baseline leak, pump, ionic dissipation and separate channel
transfer histories. Neither imports the production engine or JAX.

[Data-only checks](../tests/voltage_gated_numerical_checks.py) inspect material,
charge, ionic energy and disabled-route histories, and compare both gates and
open fraction. Candidate cubic extrema cover complete intervals, not only
observation times. The [read-only auditor](../scripts/audit_voltage_gated_reference.py)
checks source/preparation/settings identities and reconstructs observations
from the saved dense basis; it does not rerun an ODE solver.

## Results and retained failures

The [qualification receipt](../runs/num-007-2026-09-09/reference-01/verification.json)
contains all 98 attempts. All 42 implicit attempts pass and independently agree.
Of 56 candidate attempts, 49 pass, six complete but miss frozen accuracy limits,
and one is rejected at a real stage outside the gate domain. No input, tolerance
or ladder was changed after evaluation; no attempt was silently replaced.

| Candidate nominal step | Cases passing | Worst observed voltage error in completed paths | Worst gate error in completed paths |
| --- | --- | --- | --- |
| 2 ms | 10/14; one rejected path | 1.1804e-5 V | 5.0347e-4 |
| 1 ms | 11/14 | 5.9209e-7 V | 1.6594e-3 |
| 0.5 ms | 14/14, selected | 5.1577e-8 V | 7.7717e-5 |
| 0.25 ms | 14/14, qualifying refinement | 3.5566e-9 V | 4.1700e-6 |

The 2 ms row does not include a fabricated gates-only suffix. Its first k4
stage at 2 ms produces m=1.1943829789, outside [0,1]; the initial prefix and
exact rejected trial/control are retained. The ordinary failures are both
depolarized cases at 2/1 ms, equal-open-A at 2 ms, and gates-only at 1 ms.
In particular, the 1 ms depolarized voltage errors are below their 1e-6 V limit,
but dissipation errors are approximately 1.97e-6 pJ, above the 1e-6 pJ limit.
Voltage agreement alone would therefore select a method that fails this contract.

| Selected-method or reference check | Worst observed value | Frozen limit |
| --- | --- | --- |
| Reference/reference normalized error | 0.00049668 | 1, using reference budgets ten times tighter |
| Selected accepted/observed normalized error | 0.777162 | 1 |
| Selected voltage error | 5.1577e-8 V | 1e-6 V |
| Selected gate error | 7.7717e-5 | 1e-4 |
| Selected open-fraction error | 7.7548e-5 | 1e-4 |
| Selected channel-ledger error | 4.2836e-9 fmol | 1e-7 fmol |
| Selected synthetic Ca amount error | 3.6804e-12 fmol | 1e-9 fmol |
| Selected material residual | 3.3546e-13 fmol | 1e-10 fmol; 1e-12 for Ca |
| Selected charge residual as voltage | 3.5410e-12 V | 1e-8 V |
| Selected ionic-energy residual | 9.5572e-8 pJ | 1e-6 pJ |

These are maxima over declared native/comparison points, not a continuous-time
error proof or uncertainty interval. All selected stage, observation and full
cubic gate/amount/voltage domain checks pass. Disabled ledgers and all-off ionic
substates remain exact while gates evolve. The 0.1 ms pulse retains nonzero
channel transfer (about -3.09e-6 fmol in either assembly), with no final-time
transfer added by the final availability change.

The equal-open preparations start with m h=0.16 and identical ionic conditions.
After 100 ms the independent reference gives approximately -58.538 and -56.744
mV, a 1.794 mV separation. This is a state-sufficiency witness: storing only
open fraction loses relevant history. It is not a biological-memory or Plastic
Heredity validation result.

## Evidence, resources and verification

The scientific session completed in **196.401 s**, below its 900 s cap, retaining
**80,191,978 bytes (76.48 MiB)** below 128 MiB. One CPU process was pinned to CPU 4
with BLAS/OpenMP thread limits of one. There are 110,631 retained native rows
(including the rejected initial prefix) and 140,502 common sample points summed
across cases. These are qualification costs, not production throughput or a GPU
speedup measurement. A 0.5 ms nominal grid has twenty times as many steps as
10 ms over the same horizon; that arithmetic is not a measured runtime ratio.

The [read-only audit passes](num-007-audit.json): **214 payloads, 19 archived
source files, 97 replayed complete arrays / 947,939 reproduced sampled rows**,
and the independently confirmed rejected stage. It reconstructs observations,
case verdicts and the full selection from saved data without rerunning an ODE
solver. Successful adaptive/candidate trial ranges are instrumented summaries,
not saved transcripts of every RHS evaluation; the rejected trial is retained.
The [source capsule](../runs/num-007-2026-09-09/reference-01/sources.zip),
[resolved cases](../runs/num-007-2026-09-09/reference-01/cases.json) and
[session metadata](../runs/num-007-2026-09-09/reference-01/session.json) are immutable.

All **198 preflight tests pass in 14.24 s**, including 93 new numerical/evidence
tests and all 105 SPEC-006 tests. [Receipt](num-007-preflight-04.xml).
Shortened, explicitly synthetic unit fixtures exercise full recording/audit,
candidate rejection and injected budget-stop receipts. They are not undisclosed
evaluations of the scientific panel. Earlier passing preflight receipts remain
retained: 87, 92 and 93 tests as coverage was added.

All **205 targeted tests pass in 19.29 s**, including the **100 new tests**
(93 numerical/preflight and seven saved-artifact corruption/provenance tests)
and the 105 unchanged SPEC-006 tests. [Receipt](num-007-targeted-01.xml).
The [full regression matrix passes](num-007-regression-01/verification.json),
with **2770 tests, zero failures, errors or skips**:

| Context | Passed | Test-context time |
| --- | --- | --- |
| Current production and new references | 1799 | 566.839 s |
| Preserved historical reference | 971 | 155.340 s |
| Total | 2770 | 722.179 s |

These are summed test-suite times, not simulator performance measurements.

No numerical unit test failed or tolerance/input/ladder was tuned during preflight.
Lint corrections and additional coverage preceded the scientific session.
Lint and formatting pass across 189 Python files. The existing CORE-006
773-payload [acceptance audit passes again](num-007-core006-audit.json) without
rerunning its solver. All 41 production modules, packaging/locks, old reference
code and pilot data remain unchanged; the new work adds reference tools/tests
and updates current architecture/status documents only. The
[final preservation receipt](num-007-closeout.json) records 382 pre-existing
files: 372 remain byte-identical and ten have intentional documentation changes.

This qualifies only the frozen short engineering panel, not a parameter box,
physiological calibration, whole-cell voltage clamp, GPU execution or organ simulation.

## Frozen identities

| Object | SHA-256 |
| --- | --- |
| NUM-007 panel | `aa07cd7c200a2a93c9484d7b45d5a47a28a766e3958db1511bd230af4a5bd9e0` |
| Prospective protocol | `1e3aa65487b8a95c6f7e5bf1100c45e840456e7a6a1c96a97b0b973e932020c6` |
| Unchanged SPEC-006 panel | `16b6e245ba2cef921fc48e1a4c7f8ebd03481724e7de5d1062fcf0d8fdeed09c` |
| Scientific verification receipt | `422720bd0de6ef3259bb32604399f91502112cefa2a318720b28e2fb25c05e75` |
| Read-only audit receipt | `5e9433d2f2b3f17b8066eb729a4f636e4168da59d50d68f0ae9de19649166c5f` |

## Reproduction and next gate

Use a new directory for a deliberate reproduction; the qualifier refuses
existing destinations. The independent matrix needs the unchanged, pinned local
SciPy/NumPy environment and original source/reference artifacts.

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 4 .venv/bin/python scripts/qualify_voltage_gated_reference.py --output runs/my-num007-reference
.venv/bin/python scripts/audit_voltage_gated_reference.py runs/my-num007-reference
.venv/bin/python scripts/test_cells_build.py --output reports/my-num007-regression
```

CORE-007 follows only a qualified reference: implement a new model identity,
numeric gate/channel axes and shared-stage CPU/JAX dynamics; verify eager/JIT,
observations, full snapshots, independent branches and scalar/cohort execution.
Keep earlier sources/checkpoints and timestep bounds unchanged. Multirate,
reduction and parallel GPU execution still need independent evidence. The
descriptive pilot and deferred E02 campaign are not reopened.
