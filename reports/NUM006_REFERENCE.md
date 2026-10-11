# NUM-006: bounded multispecies trajectories

2026-09-09, D047. **Complete as independent CPU numerical qualification.**
All 14 frozen cases and 84 numerical attempts pass. The predeclared rule selects
**RK4 at a nominal maximum step of 0.01 s with interval-held-control cubic
Hermite observations**, on these exact assemblies and schedules. The finer
0.005 and 0.0025 s trials also pass. This does not change existing production
timestep limits or qualify arbitrary multispecies parameters.

The [qualification receipt](../runs/num-006-2026-09-09/reference-01/verification.json)
and [strengthened read-only audit](num-006-audit-v2.json) retain the evidence.
All **446 targeted tests pass**, including 94 new tests. Production remains
0.10.0 with the same seven models and 39 source files. CORE-006 is next.

## What changed

The [prospective protocol](../docs/MULTISPECIES_NUMERICS.md) and
[frozen panel](../configs/reference/multispecies_trajectories_v1.json) extend
SPEC-005's two unchanged synthetic assemblies into short trajectories. Each
has baseline 1/10 s, passive-only 10 s, pump-only 1 s, all-off 1 s, block/release
2 s and a 1 ms pump pulse within 1 s. Control boundaries include off-grid
events and a final-time readout change. No experimental data were fitted.

[The independent numerical module](../tests/reference_multispecies_dynamics.py)
uses a separately expressed hyperbolic transport law with Radau, BDF and refined
Radau, evolving amount increments. The RK4 candidate instead evolves absolute
amounts using SPEC-005's independent Bernoulli evaluator. Thus agreement checks
both integration and alternative equation/coordinate implementations. Neither
path imports the production engine or JAX.

Native states, full interpolation coefficients, common comparison samples,
solver statistics and per-attempt verdicts are saved. The
[data-only checks](../tests/multispecies_numerical_checks.py) recompute material,
charge and ideal chemical/capacitor energy identities. The auditor independently
replays the saved dense basis; it shares the explicit analysis rules with the
qualifier, not stored comparison answers. No ODE solver is rerun during audit.

## Results

| Check | Worst result | Frozen limit |
| --- | --- | --- |
| Radau/BDF versus refined Radau | Normalized error 0.001779 | 1, using reference limits ten times tighter than candidate limits |
| Selected RK4 accepted-state error | Normalized error 0.05030 | 1 |
| Selected RK4 observed voltage error | 5.243e-8 V (0.05243 microvolts) | 1e-6 V |
| Selected synthetic Ca amount error | 2.523e-12 fmol | 1e-9 fmol |
| Selected material residual | 3.168e-13 fmol | 1e-10 fmol; 1e-12 fmol specifically for Ca |
| Selected charge residual, expressed as voltage | 3.383e-12 V | 1e-8 V |
| Selected energy residual | 4.881e-8 pJ | 1e-6 pJ |
| Minimum trial and selected-cubic amount | 0.001 fmol | Strictly positive |
| Maximum trial dimensionless voltage magnitude | 11.787 | 50 per species |

Trajectory maxima are over the predeclared sample grid, not rigorous global
error bounds. Normalized comparison error divides by the applicable frozen
absolute limit, with species-specific limits for the small Ca pool.

| Candidate nominal step | Maximum observed voltage error | All 14 cases pass |
| --- | --- | --- |
| 0.01 s | 5.243e-8 V | Yes |
| 0.005 s | 3.908e-9 V | Yes |
| 0.0025 s | 2.695e-10 V | Yes |

The declared per-case voltage refinement rule passes. No alternative candidate
failure, solver failure, budget overrun or after-the-fact tolerance/parameter
adjustment was needed. All-off states and disabled-route ledgers remain exact.
The short pulse survives event splitting; for example, the divalent case records
approximately 1.927e-5 fmol pump cycles. Its all-off and Ca-block intervals do
not erase intracellular charge or silently disable unrelated routes.

The reference runs are not equilibrated cells. After the divalent baseline's
10 s, voltage is approximately -62.956 mV and the synthetic Ca amount has grown
from 0.001 to 0.001988 fmol. That drift is retained, not relabelled homeostasis
or calcium physiology. No buffers, calcium signaling, finite bath or metabolic
pool was added.

## Evidence and verification

The one-process scientific session completed in **69.882 s**, below its 600 s
cap, retaining **38,264,835 bytes** (approximately 36.5 MiB) below 128 MiB.
There are 42 implicit and 42 RK4 attempts, 55,676 native state rows and 91,262
comparison points summed across cases. The audit reproduces **547,572 sampled
rows across 84 arrays**, checks 186 payloads and 13 archived sources, and
recomputes all case verdicts and the selection. These are qualification costs,
not a simulator throughput benchmark or GPU speedup estimate.

The [source capsule](../runs/num-006-2026-09-09/reference-01/sources.zip),
[resolved cases](../runs/num-006-2026-09-09/reference-01/cases.json),
[session metadata](../runs/num-006-2026-09-09/reference-01/session.json) and
original verification receipt are immutable. The original
[revision-1 audit](num-006-audit.json) is retained as well.

After that audit passed, code review identified two missing provenance links:
a session's protocol should equal its archived frozen protocol, and claimed
solver settings should match that protocol rather than only agreeing between
two receipts. Auditor revision 2 adds both checks plus candidate mesh/call-count
checks. Four [saved-artifact tests](../tests/unit/test_multispecies_artifact_audit.py)
reject deliberately rehashed tolerance, solver-setting and candidate-step
changes, and ordinary payload corruption, using temporary copies only.

No trajectory was rerun or changed for this audit strengthening. The original
auditor remains in the source capsule. Revision 2 reports both its own identity
and that archived auditor's identity; this is the sole permitted current-source
difference. Numerical code, original tests, protocol and dependency identities
remain checked against the archived sources. This is integrity/provenance
checking, not cryptographic proof of who performed an experiment.

Commands from the Cells directory:

```bash
.venv/bin/python scripts/qualify_multispecies_reference.py --output runs/num-006-2026-09-09/reference-01
.venv/bin/python scripts/audit_multispecies_reference.py runs/num-006-2026-09-09/reference-01
.venv/bin/pytest -q tests/unit/test_multispecies_dynamics.py tests/unit/test_multispecies_artifact_audit.py tests/unit/test_multispecies_reference.py tests/unit/test_bioelectric_reference.py tests/unit/test_bioelectric_cell.py tests/unit/test_biological_benchmark.py tests/unit/test_conditioned_voltage.py
```

The first command refuses an existing output directory: choose a new path for
a deliberate reproduction. The second is read-only; `--output` may name a new
audit receipt outside the session. The final regression command passed **446
tests in 56.67 s**: 90 numerical preflight tests, four additional provenance
tests and 352 related existing checks. Lint/format checks pass. The optional
four artifact tests skip when their immutable local run fixture is absent;
none skipped here. The historical full 2,178-test suite was not rerun.

The numerical panel retains its pre-evaluation SHA-256
`24895a45a27067626e370543513a59d27e21f2afec7d3f09b5d4ceef2dddc84a`;
the protocol document retains
`601c334ece3d08391d2251036e90f20a4b93b5617b79c84503db37086f9349d2`.
The original SPEC-005 physical panel/specification remain unchanged. All **284
pre-existing files captured before this task**, including all 39 production
sources, dependencies, previous references/tests/reports and original BIO-002
data/results, retain their hashes.

## Next: CORE-006

Implement a newly identified multispecies membrane model through the shared
CPU/JAX engine. Archive accepted 0.10.0 sources before production edits;
existing checkpoints retain their original source/runtime provenance, without
silent migration. Resolve species and pump roles on the host into pure array
parameters; retain explicit compartment/membrane ownership, fixed charge and
versioned state. Verify eager/JIT trajectories and observations against this
frozen reference, including inactive species, controls and runtime failures.
Qualify complete restart/branch behavior and regress old model identities.

The 10 ms result is a candidate for that separate acceptance, not a license to
loosen the old `bioelectric_cell@1` bound or accept a parameter box. New kinetics,
areas/capacitances, species sets, temperatures, longer horizons and coupled
cells require further qualification. Multirate, fields, fine/coarse coupling and
GPU partitioning retain the [multiscale execution contracts](../docs/MULTISCALE_EXECUTION_ARCHITECTURE.md).
The pilot stays descriptive; unfinished E02 and organ/GPU gates stay visible.
