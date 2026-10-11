# Source-compatible pair: numerical contract

NUM-004 / D025, 2026-09-08. Independent CPU qualification is complete for the
frozen 14-case panel. The candidate is **RK4 with a maximum step of 0.01 source
nominal-time units and checked cubic observations**. This is not 10 ms and is
not itself a production implementation. At this stage Cells remained 0.6.0;
subsequent [MODEL-005](SOURCE_EMT_PAIR.md) implements and verifies the profile
through the shared JAX architecture in 0.7.0. This document retains the original
numerical qualification and handoff; its inputs and targets are unchanged.

The [model specification](SOURCE_EMT_PAIR_SPEC.md) owns the equations, units,
prepared inputs and mechanism boundaries. The [qualification report](../reports/NUM004_REFERENCE.md)
records measurements, failures, provenance and reproduction commands.

## Frozen scope and independent state

The original [14-case panel](../configs/reference/source_emt_pair_panel_v1.json)
and its predeclared accuracy targets are unchanged. The supplementary
[numerical protocol](../configs/reference/source_emt_pair_numerics_v1.json)
defines the study cases, diagnostic tolerances, native refinement levels and
resource limits. Prepared cases run for 10 nominal units; constructed and event
cases for one. No long-time attractor, memory assay, physical clock calibration
or arbitrary-parameter stability is established by these short trajectories.

The standalone [NumPy/SciPy reference](../tests/reference_source_pair_numerics.py)
imports neither Cells nor the upstream simulator. It reuses the independently
written and previously frozen instantaneous equations, not a production kernel.
Its 30-coordinate packet is a reference interchange format, not a requirement
to mix dimensional types in a production state array.

| Coordinates | Shape | Role |
| --- | --- | --- |
| Primary Na/K/Cl and u/m/z | 6 × 2 | Six evolving coordinates per cell, with ionic and regulatory units kept distinct |
| Inward membrane leak history | 3 × 2 | Ionic concentration-equivalent contribution |
| Pump-cycle history | 2 | Signed cycles in concentration-equivalent units; stoichiometry (-3,+2,0) |
| Oriented ionic transfer | 3 | One signed history per species on the edge |
| Local regulatory history | 3 × 2 | Source-scaled regulatory contribution |
| Oriented miRNA transfer | 1 | Source-scaled regulatory contribution, not ionic charge inventory |

All 18 history coordinates are diagnostic and never feed back. Each initial
primary coordinate plus the relevant local and exchange contributions must
reconstruct its trajectory within 2e-9 in its own coordinate units. Opposite
edge contributions cancel for these equal-volume cells. There is no assertion
of physical miRNA conservation through the approximate binding caches, nor an
energy inequality for the source upwind transport law.

P/Snail/ST remain fixed context. Free/bound caches, voltage and algebraic gate
scales are reconstructed from current primary state. They are not evolving
memory. Pump eligibility is determined by base membrane permeabilities, before
prescribed IC leak inhibition, exactly as in the source-compatible contract.

## Reference solvers and method selection

Integrate independently with Radau and BDF at `rtol=1e-10`, `atol=1e-11`, and
repeat Radau with both tolerances ten times tighter. Implicit methods evolve
primary increments from the fixed initial anchor, together with the histories;
this reduces cancellation when resolving tiny ionic changes. Their maximum
step is 0.1 nominal units. A bounded second-order finite-difference Jacobian
perturbs only the 12 feedback coordinates; the history columns are zero.

Reference methods must agree within one tenth of the candidate error budget.
Accepted increments, complete dense-polynomial coefficients and solver statistics
are retained. The coefficient adapters are checked against SciPy's own dense
output; domain checks include each polynomial's interior extrema, not just the
solver's accepted states.

The independent RK4 probe evolves absolute primary coordinates and all histories
at shared stages. The frozen study uses S01, S05 and S13 at 0.01, 0.005, 0.0025
and 0.001. Select the largest candidate passing all three, then qualify all 14
cases at that step and its half. All 12 study trials and 28 qualification trials
pass. This accepts 0.01 within the tested regime; larger steps were not tested
and are not authorized by this result.

| Quantity | Absolute target | Relative target |
| --- | --- | --- |
| Ionic concentration and ionic histories | 5e-8 | 5e-10 |
| Regulatory coordinate and regulatory histories | 5e-6 | 5e-8 |
| Cell voltage | 5e-7 V | 0 |
| Junction scale | 5e-6 | 5e-8 |
| Each membrane/junction flux | 1e-13 in its source numerical flux units | 1e-5 |

For each scalar, error is divided by `atol + rtol * abs(reference)`; a maximum
normalized score of one passes. Flux entries retain ionic versus nominal
regulatory semantics despite sharing numerical comparison targets. Gates can
exceed one under the source amplitude convention and are not probability states.

## Events, observations and refusal policy

Use a global fixed-step grid split at every prescribed control event. State and
histories carry over exactly; controls are right-continuous and independent.
The cubic for the preceding interval uses the old held controls at both endpoint
derivatives. An event cannot be smeared across an integration or interpolation
interval. Restart tests at ordinary and event boundaries retain all 30 coordinates
and reproduce the independent probe suffix exactly. This is not yet production
checkpoint acceptance.

Compare complete state, histories, voltage, gate scales and fluxes at every
accepted endpoint, every midpoint, frozen irregular observation times and events.
Return stored accepted states exactly when sampled at their own times. Other
observations use cubic Hermite interpolation. Observation requests do not set
the integration grid.

Require finite states and coefficients, ions in [1e-6,1000], regulation in
[0,1000], and both cell and transjunction voltage magnitudes at most 0.2 V.
Check RK4 stages, endpoints and all relevant cubic extrema. The implicit dense
polynomials receive corresponding whole-interval checks. Polynomial roots and
extrema use floating-point arithmetic, not rigorous interval certification;
sampled error comparisons are not formal continuous-time ODE error bounds.
Invalid trials are refused, not clipped or reinterpreted as biological events.

Prescribed blocked routes must leave their own accepted histories exactly
constant while other mechanisms continue. Edge reversal with a hemichannel swap
must preserve the physical primary path and negate oriented transfer histories;
reversal without the swap is a distinct model and a negative control.

## Native source clocks are a separate numerical contract

The native comparison executes only the pinned reusable source modules in the
separate reference environment. It does not import the cancer driver, rerun
preparation, invoke the continuing exploration, or patch upstream code.

The source uses adaptive Euler. Its `time_step` is a **minimum time quantum**,
not a maximum accepted step. The integrator can overshoot a requested phase end.
Subsequent phases in this capture request their original duration and start
from the full actual accepted packet and clock. This produces a realized event
schedule distinct from the intended one; neither clock is silently relabeled.

Record every accepted step's raw full packet, refreshed caches, primary slope
and integer step multiple, along with the native plotting samples and final
packet. Audit the exact source update order, fixed context and cache carryover.
The accepted raw caches belong to the preceding RHS evaluation, whereas a pure
endpoint readout reconstructs current caches. Comparing these as interchangeable
state would manufacture a discrepancy.

Compare every accepted primary state and its pure readouts with independently
refined Radau/BDF trajectories under the **realized** schedule, starting from
the original full input, never reanchoring at native phase boundaries. Separately
compare intended and realized trajectories at common times. The state-induced
readout comparison holds controls to the intended schedule; the actual flux
difference across shifted discontinuities is also recorded, not hidden in an
inappropriate uniform convergence claim.

Native first-order targets are deliberately separate: ionic 2e-5 + 1e-7 relative,
regulatory 0.005 + 1e-5 relative, voltage 5e-6 V, scales 0.0005 + 1e-5 relative,
and flux 1e-11 + 0.001 relative. Refinement must reduce the maximum normalized
score by at least half from coarse to finest unless already below the 0.01
noise floor. Finest event error must be at most 0.01 nominal units, and the
intended-versus-realized state/readout effect must also meet these native targets.
These looser targets do not replace production-candidate tolerances.

The original three-level study passes 13 cases completely. S12 passes its
realized-time state checks but fails the intended-schedule RNA target: the
0.137 release actually occurs at 0.1439. The original failure is retained.
The separately recorded [event-refinement extension](../configs/reference/source_emt_pair_event_refinement_v1.json)
halves and quarters all three fine native step controls for S12, without changing
equations, inputs or tolerances. Both extra trajectories pass; the finest is the
qualified S12 native witness. Its release occurs at 0.13755. Timing error is not
monotone on this integer adaptive grid: the intermediate release is 0.13725.

Source-compatible equations therefore do not imply bitwise reproduction of an
old solver's requested-time outputs. Production should retain exact event
splitting and record its own clocks. Do not copy native overshoot into the
generic scheduler to reproduce an endpoint.

## Production and computational-multiscale handoff

At NUM-004 completion, MODEL-005 was ready for the following bounded implementation
(now [accepted](../reports/MODEL005_ACCEPTANCE.md)). Preserve
accepted Cells 0.6.0 source before edits. Use typed ionic/regulatory arrays,
immutable layout/context, explicit history and control PyTrees, shared stage and
graph-scatter composition, pure readouts, and the checked event/observation engine.
Keep source-specific constitutive laws inside the named model. Verify JAX against
the frozen reference arrays, complete restart and future-control branches,
capacity/identity semantics, numerical refusal and all six earlier models.

The reference's one nominal clock is an explicit compatibility approximation,
not a multirate solution or an organ-wide timestep policy. Future large-GPU work
must measure representative coupled and independent-world workloads, distinguish
fast electrical from slower regulatory behavior, and independently qualify any
multirate or coarse-grained exchange interface. More throughput cannot establish
a physical time mapping, long-time accuracy or valid reduction. No GPU run,
organ preset, cancer-expression strategy or memory/relay assay is added here.
