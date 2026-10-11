# SPEC-009: spatial extracellular design and arithmetic reference

2026-09-11, D059 / R011. **Complete — design and instantaneous reference only.**
The production simulator remains Cells 0.14.0. No production module, dependency,
solver, model registry, timestep, checkpoint schema or old evidence is changed.

The [new contract](../docs/SPATIAL_EXTRACELLULAR_SPEC.md) starts with one cell,
one membrane and two finite outside volumes. Bulk ions move by diffusion and
electric drift; current continuity determines the relative outside potentials.
Membrane-associated charge is retained, while a bulk volume with no membrane
needs no invented capacitor. The topology is data, not a cell-count or organ branch.

## Executed checks

The [saved arithmetic receipt](spec-009-design-check.json) passes all **1,016
scalar comparisons** against an independently assembled 70-digit Decimal path:
eight synthetic definitions, 44 initial/shifted-state and availability evaluations.
The maximum normalized discrepancy is **0.162823**, below the boundary of 1;
the largest discrepancy is a near-zero charge-rate comparison, about
`1.63e-24 A`, not a biological uncertainty estimate. No tolerance was relaxed.

The NumPy reference solves capacitance components and their relative offsets.
The Decimal oracle instead assembles the outside-node Kirchhoff equations,
uses its own row elimination, and evaluates direct membrane GHK exponentials.
It does not call the reference's face flux, incidence or potential functions.
The oracle separately forms chemical power and membrane capacitive power.
Neither calculation imports production dynamics or an ODE solver.

| Synthetic definition | Question checked |
| --- | --- |
| Single outside | Reduction to the existing membrane charge anchor and independent passive law |
| Binary salt, unequal diffusivities | Analytic diffusion potential and ambipolar salt flux, despite zero net current |
| Binary salt, equal diffusivities | Zero diffusion potential with nonzero salt transport |
| Uniform outside | Exactly zero initial bulk flux; membrane transfer may still occur |
| Ternary outside loop | Node current balance with nonzero circulating face currents |
| Two-cell outside chain | Different membrane owners coupled to a shared outside graph |
| Divalent salt | Valence-weighted charge/current and energy, not hard-coded monovalent indices |
| Pure bulk | Electrical closure without any membrane or capacitance |

In the unequal-diffusivity example, the near region is at **+6.17218 mV** relative
to the far region and both ions transfer at **8 fmol/s**. Setting both outside
potentials to zero would instead produce an unbalanced diffusion current.
The cell's initial membrane voltage remains **−65 mV**: its absolute potential
shifts with its facing outside. This is not an observed biological voltage or
a simulated time-dependent depolarization.

The prescribed shifted states explicitly change both owners of a membrane
transfer and both outside owners of a neutral salt transfer. They are algebraic
probes, not accepted solver steps. Availability values 0, 0.35 and 1 are evaluated
for membrane-bearing cases; the pure-bulk case has no membrane control to vary.

## Tests, replay and preservation

All **85 new unit tests** pass in the [initial preflight](spec-009-preflight-01.xml).
The [final targeted run](spec-009-targeted-01.xml) passes **229 tests** with no
failures, errors or skips: those 85 plus 144 existing finite-outside production,
saved-output audit and historical-launcher tests. Its reported wall duration is
105.16 s; this is a test run, not a simulator speed benchmark. Formatting/lint
checks on the three new Python files pass.

Additional unit coverage includes gauge, label, species-order and face-orientation
invariance; stable near-equal log means; amount/volume separation; exact membrane
blocking; material and power identities; and refusal of incompatible component
charge despite global neutrality. Invalid geometry, disconnected/duplicate
interfaces, zero conductivity, unknown fields and invalid inventories are refused.
There is no charge repair, artificial grounding, concentration floor or clipping.

[Exact saved-receipt recomputation](spec-009-reference-replay.json) reproduces
all 44 evaluations, metadata and captured source identities except the capture
timestamp. The [unchanged production audit](spec-009-core009-audit.json) authenticates
830 accepted payloads, 256 captured implementation files and all 48 production
modules; it rechecks the earlier fourteen-case execution evidence without an ODE
rerun. The [per-turn closeout](spec-009-closeout.json) compares against the actual
dirty-worktree baseline, not Git HEAD, and records preserved old files and the
ten expected documentation-only changes.

The full five-context regression matrix was **not rerun in this slice**. Its
previous 3,616-test passing result belongs to CORE-009 and is preserved, not
counted as newly executed coverage. This bounded slice adds no production code
and relies on the targeted run, independent arithmetic, saved-output audit and
byte preservation. The original NUM-009 v1 stopped evidence and unexecuted
prospective tests retain their original status.

To reproduce the arithmetic and unit checks from the Cells directory:

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/check_spatial_extracellular.py --verify reports/spec-009-design-check.json
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest tests/unit/test_spatial_extracellular_reference.py -q
```

## What remains

This checks a discrete passive electrical/environment contract. It does not
qualify a time integrator, positivity over a trajectory, arbitrary meshes,
spatial convergence, multiple membrane patches, electrodes, cross-region gap
junction return currents, biological plausibility, BETSE parity or GPU execution.
The minimal single-patch cell cannot establish general spatial polarization or
ephaptic physiology. Existing production mechanisms keep their separate meaning.

Next is **NUM-010**: freeze a short coupled spatial-trajectory panel, independent
reference methods, charge/current/energy and positivity budgets, temporal and
spatial refinement, observation reconstruction and restart requirements. The
old 1 ms well-mixed timestep does not apply automatically. Only after numerical
qualification should **CORE-010** add a versioned CPU/JAX family. The future GPU
design reserves a real sparse field-solve/communication block; it makes no speed
claim and does not add a mandatory solver dependency now.
