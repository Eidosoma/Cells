# Independent physical-pair numerics

NUM-003 / D022, 2026-09-08. This reference qualifies the numerical model specified
by [SPEC-002](SELECTIVE_CONTACT_SPEC.md), not a production or source-compatible
simulator. [Qualification evidence](../reports/NUM003_REFERENCE.md) records the
actual outcomes and preserved artifacts. The subsequent
[MODEL-004 production acceptance](../reports/MODEL004_ACCEPTANCE.md) adds the JAX
pair in 0.6.0. This document retains the independent reference-stage contract;
the numerical equations, panel, trajectories and targets are unchanged.

## Reference boundary

[reference_bioelectric_pair.py](../tests/reference_bioelectric_pair.py) uses the
already independent [one-cell reference](../tests/reference_bioelectric.py) for
each membrane/pump. It imports neither Cells mechanisms nor the earlier
instantaneous contact calculator. The junction flux uses the alternative
symmetric hyperbolic expression, checked against the Bernoulli design formula:

```text
x_s = z_s F (V_from - V_to)/(R temperature)
H(x) = x/[2 tanh(x/2)], H(0) = 1
J_s = (area P_s/a) u [r_s+(1-r_s)g]
      * [(c_from_s-c_to_s)H(x_s)+(c_from_s+c_to_s)x_s/2]
```

The reference is a bounded two-cell numerical tool, not another production
backend or a general plugin system. It has two physical cells and one edge;
capacity padding, compiled execution, persistent identities and production
checkpoints are MODEL-004 responsibilities. Physics, units and omitted gate
energetics remain exactly those of SPEC-002.

| Reference coordinates | Count | Role |
| --- | --- | --- |
| Na/K/Cl amounts in A/B, species-major | 6 | Primary material state, fmol |
| Na/K/Cl membrane-leak ledgers in A/B | 6 | Signed external exchange history, fmol |
| A/B pump-cycle ledgers | 2 | Signed fmol cycles |
| Na/K/Cl oriented junction-transfer ledgers | 3 | Signed fmol from the stored source endpoint to destination |
| Junction gate | 1 | Primary evolving fraction, not recomputed from voltage |
| Leak, pump and junction dissipation quadratures | 3 | Separate reference diagnostics, pJ; not additional biological state |

The 21-column order is explicit in the run receipt. No independent voltage
coordinate is integrated. SciPy evolves six amount increments relative to the
immutable initial anchors; RK4 evolves absolute amounts, as planned for Cells.
This is an algebraic coordinate change, not a change of physics. Carry all
coordinates across event boundaries without resetting increments or ledgers.
Comparison arrays contain absolute amounts; the explicitly named native
`increment_state` arrays retain amount increments in their first six columns.

## Frozen panel and reference methods

[bioelectric_pair_panel_v1.json](../configs/reference/bioelectric_pair_panel_v1.json)
was frozen before integration, SHA-256
`642c92c6dba5f1f06c1639fbe37c0f69ef962e7018f2003d88c1c34d5ae14d46`.
It contains SPEC-002's 20 cases Q00-Q19, exact parameters and controls, accuracy
targets, and the predeclared timestep-study list. All unspecified case parameters
inherit the explicit base fixture. Each control record resolves to a complete
held-control state; omitted fields use the documented open defaults, not hidden
inheritance from the previous record. Q18 explicitly retains earlier inhibitions.

Resolved complete definitions are saved before the first integration, alongside
a code/input archive. Reference methods are Radau and BDF at `rtol=1e-11`,
`atol=1e-13`, compared with Radau refined to `rtol=1e-12`, `atol=1e-14`.
All use maximum internal step 0.25 s and start a new solve at each control
boundary. These are different numerical methods applied to the same independently
implemented equations, not independent biological models.

The numerical Jacobian uses only the seven kinetic coordinates: six amount
increments and the gate. Ledger columns are zero. A central second-order stencil
is used when both probes are valid; otherwise a valid one-sided second-order
stencil is used. This prevents the default forward perturbation of a gate at
one from leaving `[0,1]`. Every evaluated Jacobian probe passes the same physical
domain checks as an ordinary RHS trial; no clipping or altered gate equation.
If a valid stencil cannot be found, the reference fails explicitly.

RHS accounting includes those Jacobian probes. Each reference solve is limited
to 100000 calls and 60 wall-clock seconds; each RK4 probe to 100000 steps and
60 seconds. Case horizons are bounded to 10 s. These limits keep this development
tool bounded; they are not limits on a future organ model or promises of solver
convergence for arbitrary inputs.

## Selected candidate and what the study rejected

The predeclared study evaluates gate-only Q03, fast-gate Q09 and strong-junction
Q11 at 20, 10, 5, 2.5 and 1 ms. Retain every trajectory, including inaccurate
ones. Fourth-order gate refinement is checked on Q03/Q09 as steps are halved.

For the frozen panel the selected candidate is **CPU float64 RK4 with nominal
maximum step 0.001 s**, on a zero-anchored grid split at all control boundaries,
with **interval-held-control cubic Hermite observations**. The full-panel receipt,
not a claim about all parameters between its extremes, determines qualification.
Floating-point differences of stored grid times can exceed the nominal step by
roundoff; maximum actual steps are recorded explicitly.

The inherited one-cell 5 ms candidate is insufficient: Q09's gate error is about
8.45e-6 against the unchanged 1e-7 target, despite a small voltage error. Q11 also
misses the gate target. At 2.5 ms Q09 still fails. At 1 ms all three study cases
meet the full-state targets. Stability, plausible voltages, and a single endpoint
label would not have exposed these accuracy failures.

| Quantity | RK4 accepted/observed target | Reference-method agreement target |
| --- | --- | --- |
| Every amount, leak ledger and transfer ledger | 1e-7 fmol | 1e-8 fmol |
| Each pump-cycle ledger | 1e-7 fmol cycles | 1e-8 fmol cycles |
| Gate fraction | 1e-7 | 1e-8 |
| Each derived cell voltage | 1e-6 V | 1e-7 V |
| Each diagnostic dissipation quadrature | 1e-6 pJ | 1e-7 pJ |

Per-cell material accounting additionally requires residual <=1e-8 fmol,
charge residual expressed as voltage <=1e-8 V, and resolved energy residual
<=1e-6 pJ. All targets remain those frozen before the study. Fine reference
agreement does not by itself prove correct physics; the independent equation,
limiting-case and accounting checks are separate evidence.

## Observations and numerical-domain checks

Compare at every RK4 endpoint plus the quarter, half and three-quarter positions
of every interval, including intervals split by sub-step events. These sampled
error maxima are not rigorous continuous-time error bounds. Store accepted-state,
observed-state and reference-method errors separately.

Linear observations fail the gate target even at 1 ms: Q09's largest sampled
linear gate error is about 1.70e-4. Cubic Hermite interpolation uses the
increment expression established by NUM-002, with both endpoint slopes evaluated
under the control held over that interval. An event's left interval uses the
old control at its right endpoint, and its right interval uses the new control.
Stored endpoints are returned exactly; observation schedules never alter the
integration grid or accepted state.

Positive amounts and gates within `[0,1]` at accepted endpoints do not guarantee
valid cubic interiors. The reference also solves each cubic's derivative for
interior extrema and checks amount positivity, gate bounds, and the derived
membrane/junction voltage domain over each entire interpolant. This is a
floating-point polynomial-extrema check, not interval-arithmetic certification
or a bound on interpolation error against the exact ODE solution. A test with
valid endpoints but a gate overshoot verifies that it is not an endpoint-only check.

All RHS trials, including RK4 stages and Jacobian evaluations, require finite
positive ion amounts, valid gates and `abs(z F deltaV/(R temperature)) <= 50`
for both membranes and the junction. Numerical failures are not repaired or
interpreted as cellular death. A rejected RK4 trial retains its stage, attempted
state and accepted prefix. Domain/accuracy failures of a candidate remain
separate from physical model parameters and scientific outcomes.

## Accounting and cross-checks

All observed and accepted states are checked against SPEC-002's signed material,
charge and resolved energy identities. Three quadratures distinguish membrane
leak, pump-cycle and junction dissipation; their sum enters the energy identity.
Gate-protein energy/current/cost remains excluded. Assigned experimental costs
must not be substituted for these physical diagnostics.

Additional cross-checks include two separately integrated one-cell references
for Q01's blocked pair; Q03's exact gate-only solution and constant other state;
Q02's isolated species totals; Q04's symmetric zero-transfer limit; Q06's reversed
orientation; Q14's impermeant K route; and exact ledger constancy throughout
prescribed inhibitions. Q17's 0.7 ms block is retained despite a 1 ms base grid:
transport pauses, while the gate continues evolving.
The blocked one-cell comparison independently supplies only its common amounts,
leak/pump ledgers, voltages and summed dissipation; it does not supply a gate or
independent per-process dissipation columns.

A separate [artifact auditor](../scripts/audit_bioelectric_pair_reference.py)
checks native implicit accepted states and exact event carryover directly from
saved increments, using literal accounting identities rather than the reference
RHS. Its energy-change calculation uses `log1p` to avoid subtracting large
absolute potentials. See the qualification report for coverage and hash counts.

The complete sample arrays are used for domain, accounting and dissipation
monotonicity checks. Instantaneous dissipation rates additionally use a declared
subset of at most 257 samples per case. Receipts distinguish these coverage
levels rather than calling a sparse diagnostic an all-stage audit.

## Computational multiscale consequence and MODEL-004

Seven-coordinate local Jacobian spectra are diagnostics at the specified initial
states, not global stability bounds. Electrical relaxation, gate relaxation and
ionic concentration change have different timescales. The 1 ms candidate is a
bounded correctness baseline, not an organ-scale performance recommendation.

Later subcycling, implicit blocks or quasi-steady reductions must compare the
full state and intervention responses, including gate history. A GPU does not
remove an accuracy restriction. Precision, physical fidelity, numerical method,
world batching and graph/device partitioning remain separate decisions. No GPU,
multirate, field, organ or inter-organ implementation is added here.

The MODEL-004 handoff required preserving verified 0.5.0 source before production
edits, then adding
the physical pair through reusable mechanisms, explicit gate/transfer state,
independent controls, padding/identity checks, matching observations and complete
restart/branch acceptance. Compare JAX against the frozen numerical arrays and
regress all five existing models. This is now implemented; see the
[production guide](BIOELECTRIC_PAIR.md). Source-compatible contact remains a distinct
CONTACT-003 task; this physical reference is not BITSEY/BETSE or Levin-assay parity.
