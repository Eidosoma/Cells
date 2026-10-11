# Bioelectric CPU reference and numerical contract

NUM-002, 2026-09-08. This supplies independent integrated trajectories and an
execution candidate for [SPEC-001](BIOELECTRIC_CELL_SPEC.md). NUM-002 itself added
no registered model to 0.4.0. The subsequent [MODEL-003 implementation](BIOELECTRIC_CELL.md)
and [acceptance](../reports/MODEL003_ACCEPTANCE.md) now verify production JAX,
controls, observations and complete checkpoints in 0.5.0. The independent
[qualification report](../reports/NUM002_REFERENCE.md)
records results, retained failures, runtime, and reproduction commands.

## Independent reference, not a second production backend

[reference_bioelectric.py](../tests/reference_bioelectric.py) imports NumPy and
SciPy, not Cells or the earlier instantaneous design calculator. Its constant-field
flux uses the symmetric hyperbolic form:

```text
x_s = z_s F V_m / (R T)
H(x) = x / [2 tanh(x/2)], H(0) = 1
J_s = A P_s u_s / a * [(c_o,s - c_i,s) H(x_s) - (c_o,s + c_i,s) x_s/2]
```

This is algebraically equivalent to SPEC-001's Bernoulli-function expression.
Tests compare the alternative expressions, earlier design values, Nernst and
diffusion limits, orientation, pump stall/reversal, and charge/energy signs.
Sharing the specified physical equations is intentional; importing the future
production mechanism implementations into the reference is not allowed.

SciPy evolves amount increments relative to the immutable initial anchor,
plus leak/cycle ledgers. Its voltage uses those increments directly. The
independent RK4 method probe evolves absolute ion amounts as planned for Cells,
then derives voltage from their difference from the initial anchor. The coordinate
change is algebraic, not new physics; it helps expose cancellation and tolerance
scaling problems. No independent voltage ODE is introduced.

Each constant-control interval is integrated separately, carrying all state and
ledgers into the next interval. Reference dense output is evaluated only after
integration. The [SciPy documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)
describes Radau, BDF, their tolerances, and continuous-output interfaces. Exact
versions used in qualification are recorded in the receipt, not inferred from
the latest online documentation.

## Panel and reference tolerances

The 18 short cases are data definitions in the reference, not production engine
branches: baseline at 1 and 10 s; leak-only, pump-only, all-off; independent and
simultaneous controls; a 4 ms pump pulse; half/double area, volume, permeability,
or pump capacity; heterogeneous leaks; and a reversed pump under zero maintained
ATP free-energy change. Volume variants preserve initial concentrations, so their
initial amounts scale with volume. Area variants change capacitance with area
but retain the explicitly aggregate pump capacity.

For each case, compare Radau and BDF at `rtol=1e-11`, `atol=1e-13` against Radau
refined to `rtol=1e-12`, `atol=1e-14`. All use `max_step=0.25 s` within each
constant-control interval. These scalar local tolerances apply to the reference's
mixed, explicitly scaled increment/ledger coordinates; they are not global
trajectory error guarantees.

The comparison grid contains every candidate RK4 endpoint and the quarter,
half, and three-quarter points of every interval, including event splits.
The maximum errors reported are over these samples, not rigorous continuous-time
supremum bounds. Record accepted-step errors and observed/interpolated errors
separately; accurate endpoints alone are insufficient.

| Quantity | Candidate trajectory limit | Reference-reference limit |
| --- | --- | --- |
| Each ion amount and leak ledger | 1e-7 fmol | 1e-8 fmol |
| Pump cycle ledger | 1e-7 fmol cycles | 1e-8 fmol cycles |
| Voltage | 1e-6 V | 1e-7 V |
| Independent dissipation quadrature | 1e-6 pJ | 1e-7 pJ |

The first three rows retain SPEC-001's targets. The last is an additional
reference diagnostic, not a requirement to add another production state field.
Per-species balance must be within 1e-10 fmol, charge balance expressed as voltage
within 1e-8 V, and the diagnostic energy identity within 1e-6 pJ.

## Candidate for MODEL-003

Use CPU float64 RK4 with largest actual step at most **0.005 s** for the initial
panel, on a zero-anchored grid split at every control boundary. Use read-only
**cubic Hermite observations** with interval-held controls. This is qualified
here as an independent NumPy method experiment; production JAX qualification
is recorded separately in MODEL-003, using the same physical targets.

The tested physical variants span area 0.5e-9 to 2e-9 m2, volume 0.5 to 2 pL,
half/double baseline permeabilities or aggregate pump capacity, and the explicitly
listed controls/drive variant. This is not validation of their entire Cartesian
product, arbitrary initial chemistry, temperature changes, or every parameter
inside a bounding box. Never dispatch numerical behaviour by a fixture name.
New parameter regimes require their own reference/refinement checks and may need
a smaller step or a different identified numerical method.

Runtime domain checks require finite positive physical amounts and geometry,
finite ledgers/parameters, allowed controls, and `abs(z F V_m / R T) <= 50` at
every RK stage and accepted endpoint. This last bound keeps the reference in its
declared dimensionless evaluation domain; it is not proof of a universal accuracy
range. No concentration flooring, flux clipping, automatic re-equilibration,
or reuse of the linear reaction/transport step bound is permitted. Reject an
invalid trial explicitly; production resource/domain failure handling remains
verified separately in MODEL-003 acceptance.

The reference tools limit RK4 probes to 100000 steps and implicit integrations
to 100000 RHS calls including Jacobian probes. They reject invalid horizons,
schedules, sample times, states, and existing output paths. These are bounded
development tools, not a world scheduler or general model loader.

## Why the observation method changes

At 10 ms, the short-panel accepted RK4 states meet the physical targets, but
linear interpolation can exceed the voltage limit between steps. Refinement of
RK4 alone does not make its linear observations fourth-order accurate. Keeping
the physics and targets fixed, an interval-local cubic interpolant avoids forcing
all integration work onto an unnecessarily fine observation-driven grid.

For `theta = (t - t0)/h`, `delta = y1 - y0`, and endpoint derivatives `f0`, `f1`:

```text
y(t) = y0 + theta * [h f0 + theta * (3 delta - h (2 f0 + f1)
                               + theta * (-2 delta + h (f0 + f1)))]
```

Both derivatives use the control held over this interval. At a switching time,
the preceding interval needs the old-control endpoint derivative, and the
following interval needs the new-control initial derivative. Looking up the
new control for both sides of an event produces an incorrect interpolant even
when the accepted states are correct; a dedicated negative test covers this.

Return exact stored states at accepted times. Use the increment form above to
preserve exactly constant intervals. Compute concentrations, voltage, and other
nonlinear readouts from the sampled primary state with their definitions labelled.
Keep observations read-only and independent of the integration grid. Cubic
interpolation is not automatically positivity preserving; sampled physical state
must also be checked. No changes to the four existing models' linear-observation
contracts are authorized by this candidate decision.

## Energy diagnostic and slow passive limit

The reference adds a quadrature of passive plus pump dissipation, in pJ. It is
not a second store of matter or charge, and need not become biological state.
For the maintained bath and fixed volume, define the bath-relative potential:

```text
Omega(n) = a R T sum_s[n_s (log(c_i,s/c_o,s) - 1)] + C V_m(n)^2 / 2  [J]
dD/dt = -a [sum_s(J_leak,s delta_mu_s) + r G_cycle]                 [W]
W_ATP(t) = -a G_ATP P(t)                                         [J]
Omega(t) - Omega(0) + D(t) - W_ATP(t) = 0
```

Check this identity independently from integrated material ledgers. It accounts
for the declared ideal-solution/capacitor model relative to the chemical bath;
it is not the full energetic cost of maintaining that external support.

With all three leaks open and the pump disabled, an independent scalar root
solves `c_i,s = c_o,s exp[-z_s F V/(R T)]` together with finite-capacitance charge
closure. Check its stationary fluxes and compare a 100000 s passive relaxation
using Radau and BDF at `rtol=1e-13`, `atol=1e-15`, `max_step=1000 s`. The long
run is an additional stiff-reference check, not a long RK4 qualification.
Retain the actual distance to equilibrium; do not call the ending state prepared
merely because the requested horizon was reached.

## Multiscale consequence and next build

The baseline's initial three-ion Jacobian has a fast relaxation near 0.063 s
and a slow local mode near 3706 s. These are local linear diagnostics, not fixed
biological timescales or global stability bounds. The separation motivates later
implicit or validated multirate/reduced methods for long-time tissue work. A GPU
alone does not remove a timestep restriction, and changing physical fidelity
must remain distinct from changing solver or device.

MODEL-003 now implements the specified state/layout and pure membrane/pump
contributions, independent control groups, and identified observation method.
Its separate acceptance compares JAX against this pinned reference, verifies
eager/JIT and complete restart/branch behaviour, and regresses all four earlier
models. Verified 0.4.0 source was archived before changes. No claim of
BITSEY/BETSE parity, physical EMT calibration, whole-organ execution, or GPU
performance follows from this numerical reference.
