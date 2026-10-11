# NUM-009 v2: explicit inventories and conservation-tangent linearization

2026-09-10, D057. Prospective amendment after the
[v1 stopped attempt](../reports/NUM009_REFERENCE.md), not a reinterpretation of it.
The [v2 panel](../configs/reference/finite_extracellular_trajectories_v2.json)
keeps all fourteen inputs, horizons, equation paths, candidate steps,
reference tolerances, comparison grids, error/accounting/domain gates,
depletion witness and resource caps from the [v1 protocol](FINITE_EXTRACELLULAR_NUMERICS.md).
Only the implicit reference coordinates and Jacobian construction change.
Production 0.13.0, SPEC-008 and every v1 captured file remain unchanged.

## General representation

Radau and BDF now evolve all ten fields, including both inventory increments,
using their actual physical derivatives. No compartment is dependent on the
floating-point sum of other inventories. All saved native/dense coefficients
are the solver's full coordinates, without expansion, projection or repair.
Initial amount anchors are immutable and histories are not used as inventories.
The independent hyperbolic equations and Bernoulli RK4 path are the unchanged
v1 implementations.

Let A sum the N+1 compartment increments separately for each species. Its
constraint is A y = 0. On amount coordinates use the symmetric projector
P = I - A^T (A A^T)^(-1) A: for each species the block is
I - 11^T/(N+1). P is identity on other fields. It treats all owners equally,
does not depend on topology or controls, and never selects a convenient cell
to absorb conservation error.

The supplied Newton linearization approximates Df P by probing f(y+h P e_j).
It is **not** claimed to be the unconstrained ambient Jacobian. For any physical
correction v with A v = 0, P v = v, so Df P v = Df v. In exact arithmetic A f = 0
and A Df P = 0. Thus the conservation-tangent Newton system maps tangent residuals
to tangent corrections; its normal extension has zero derivative. Floating-point
drift is still possible and must pass the unchanged actual-state charge and
material checks. No solver state, residual, derivative or dense output is
projected onto a constraint.

A blocked inventory has identically zero RHS for all admissible states. Its
Jacobian row is therefore exactly zero; its constant value is integrated directly,
even while other compartments exchange material. This applies equally to outside,
arbitrarily isolated cells and nonzero inventories after blocking events.
The complete-state exact-constancy tests are retained unchanged.

## Bounded numerical differentiation

Active amount columns use P e_j; gate columns use e_j. History columns are exactly
zero because the physical RHS never consumes histories. The nominal displacement
is cbrt(float64 epsilon) times max(abs(coordinate), scale), with scale 0.001 fmol
for amount increments and 1 for gates.

Compute the directional distances to every affine physical-domain boundary:
positive inside/outside amounts, gates in [0,1], all membrane/junction
dimensionless voltages, and channel voltage bounds. Prefer a central difference
with at most one quarter of either distance. If its step is less than one tenth
of nominal, use a second-order one-sided difference into the admissible interval,
with h at most one quarter of the available distance (the second probe is 2h).
No failed RHS probe is clipped or retried. Unrepresentable steps or failed actual
domain checks stop the attempt. Each Jacobian uses one base and two RHS evaluations
per active column; all count against the same 100000-call budget.

This is a reference-only dense CPU construction, not a proposed GPU kernel.
The physical inventories/ownership and production JAX design remain suitable for
later separate array, sparse or matrix-free implementation and qualification.
SciPy supports callable Jacobians in
[Radau](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.Radau.html)
and [BDF](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.BDF.html).
Those APIs do not establish our constrained-linearization argument or accuracy;
the independent trajectory/refinement and invariant tests must do that.

## Preflight, provenance and stopping

Before the new formal session, test projector identities and directional
derivatives, every initial panel state without integrating the panel, gate
boundaries, exact inactive rows/history columns, event-held nonzero blocking,
arbitrary isolated cell owners, and complete short synthetic trajectories.
Test actual probe/resource accounting and reject invalid supplied outside state.
Do not infer qualification from preflight.

Use a new destination, reference-02, with a pre-run registration and complete
source capsule. All v1 scientific code, tests and failed artifacts stay executable
and byte-identical. The v1 stopped-attempt audit still runs against its original
31 current source identities. Its prospective complete-session corruption suite
has no complete v1 evidence to exercise: retain it as historical, unexecuted
coverage, not passing or skipped acceptance. The maintained v2 complete-session
suite reproduces all those checks and adds Jacobian accounting. A new explicit
test-context driver records this version routing; the accepted production driver
is not edited. Both v1 preflight and stopped-evidence suites still run.

The v2 auditor reads arrays and metadata only, independently replays dense
observations, recomputes unchanged acceptance checks, and verifies actual
Jacobian work totals. A failed reference or exhausted resource stops this run
without an automatic retry, weaker checks, larger budget or production promotion.
No GPU, long-time, organ or biological validation is claimed.
