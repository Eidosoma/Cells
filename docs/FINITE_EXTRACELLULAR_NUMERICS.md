# Finite extracellular-compartment numerical qualification

NUM-009 / D056, 2026-09-10. This protocol and its
[panel](../configs/reference/finite_extracellular_trajectories_v1.json) are declared
before trajectory evaluation. [SPEC-008](FINITE_EXTRACELLULAR_SPEC.md) owns the
unchanged physical equations. Production remains Cells 0.13.0; CORE-009 is a
separate implementation gate. Results belong in a separate report.

## Scope and declared cases

Fourteen synthetic cases, 0.05–0.3 seconds: single-cell outside volumes 0.1,
1, 10 and 1000 pL; a divalent single cell; disconnected cells sharing one outside;
a pair; mono/divalent stars; a junction-only star; independently blocked/released
routes; a 0.1 ms junction pulse; and two 0.0001 pL outside stress cases.
One stress case enables only the original single-cell pump; the other retains
the divalent cell's original routes. Explicit tiny-outside inventories and fixed
charges are declared once, using 70-digit arithmetic for their initial anchors.
No resolver recalculates them to repair an input. All other physical parameters
and preparations are inherited unchanged from the passing SPEC-008 receipt.

Tiny compartments are synthetic stiffness/depletion probes, not a claim that
this well-mixed, fixed-volume, lumped-charge approximation is physiological at
that size. No calcium-buffering, osmosis, metabolism, mesh, organ, GPU or biological
acceptance follows. Sharing an outside couples disconnected cells: there is no
independent-cell trajectory decomposition in this finite model.

The pump-only stress case must show at least a 5% reduction of outside potassium
at a sampled time while remaining positive, as a predeclared depletion witness.
Otherwise report the unfulfilled witness without changing the case. Volume
variants are reported, but no uniform long-time maintained-bath limit is claimed.

## Coordinates and two equation paths

All saved native states, dense bases and observations retain all ten SPEC-008
fields, in their declared cell-/edge-major order. Both amount fields are stored
as increments from immutable original amounts; gates and signed histories retain
their meanings. Physical amount is initial amount plus increment. This avoids
accumulating the rounding of tiny transfers into a large reservoir inventory.
It is not a concentration floor, material projection, history-derived amount or
reanchoring. A future production adapter must preserve these anchors explicitly.

The Radau/BDF references evolve the nine old fields: inside amount increments,
all leak/pump/channel/junction and dissipation histories, and every gate.
The outside increment is the linear coordinate map

```text
delta_n_out[s] = -sum_i delta_n_inside[i,s]
```

This eliminates only the redundant species-total coordinates. Every reference
RHS/Jacobian perturbation reconstructs the same conserved total; arbitrary
independent outside perturbations would violate the physical charge constraint.
The map also expands every coefficient of each retained dense basis. All ten
fields remain available for audit. It never replaces a supplied full state's
outside amounts with a repaired value.

The separate RK4 candidate evolves all ten fields, including an independent
outside increment and its equal/opposite membrane derivative. Thus its material,
countercharge and outside-history residuals are not imposed by the reference
coordinate reduction. At every stage it uses the unchanged SPEC-008 scalar
Bernoulli transport evaluator on reconstructed physical amounts.

The reference expresses membrane/edge transport independently in hyperbolic
form, pump flux through its affinity, and channel gates in their native mV/ms
formula. It uses current outside concentrations, not a substituted maintained
bath parameter record. Local membrane exchange is accumulated once into the
outside derivative; internal junction exchange is excluded. Independent
instantaneous agreement is tested before integration. Neither path imports
production Cells/JAX or uses production derivatives as an oracle.

## Numerical ladder and event handling

Radau/BDF: rtol 1e-11, atol 1e-13, maximum step 0.005 s. Refined Radau:
1e-12, 1e-14 and 0.0025 s. Local mixed-coordinate tolerances are not global error
bounds. Candidate RK4 ladder: 0.004, 0.002, 0.001, 0.0005, 0.00025 s, tested anew.
A coarse domain or accuracy failure is retained and does not authorize extension
of the ladder. Select the coarsest all-case pass whose next-finer candidate also
passes and improves the specified observables; the finest candidate alone cannot
qualify.

Every complete ID-bound control snapshot starts at zero and is right-continuous.
Split both reference and candidate integration at every control event. All stages
and the endpoint slope use the incoming interval's held control. A final-time
event changes readouts only, not the arriving state. The inherited star schedule
has independently blocked groups, an all-off interval [0.0679, 0.113] s and final
shutoff. The junction pulse [0.0203, 0.0204] s is shorter than every candidate step.

Candidate meshes union the zero-anchored regular grid with all events. The common
comparison grid includes every candidate endpoint and each interval's quarter,
half and three-quarter points. Native queries return stored native states exactly.
Other queries replay interval-held cubic Hermite (RK4), normalized power (Radau)
or Newton (BDF) data. Observation times never choose solver steps.

## Frozen error, accounting and domain gates

| Quantity | Candidate absolute error | Reference-reference error |
| --- | --- | --- |
| Inside/outside amount, leak, channel/pump and junction history | 1e-7 fmol | 1e-8 fmol |
| Synthetic Ca inside/outside amount, leak and junction history | 1e-9 fmol | 1e-10 fmol |
| Outside concentration | 1e-4 mM | 1e-5 mM |
| Outside synthetic Ca concentration | 1e-6 mM | 1e-7 mM |
| Cell voltage | 1e-6 V | 1e-7 V |
| Each membrane/edge dissipation history | 1e-6 pJ | 1e-7 pJ |
| Each gate and membrane open fraction | 1e-4 | 1e-5 |

Compare endpoints and common observations separately. The outside concentration
budget matters even if a tiny reservoir's absolute amount error looks small.
For every case require finer/coarser observed voltage, maximum membrane-gate,
junction-gate and outside-concentration error ratio <= 0.8, except below
1e-10 V, 1e-8 gate and 1e-8 mM concentration floors.

Check independent inside, outside and global material identities against full
histories: <= 1e-10 fmol, or 1e-12 for Ca. Local material/charge residual is
<= 1e-8 V. Full ionic countercharge remains <= 1e-20 C, including the reconstructed
absolute SPEC-008 check at actual trials. Full inside/outside chemical plus each
membrane capacitor once, all membrane/edge dissipations and supplied pump work
must balance to <= 1e-6 pJ. Use anchored log1p energy differences.
Each dissipation history may decrease by at most 1e-10 pJ.

Disabled transfer histories are exactly constant, also at dense observations.
With all membrane routes off the outside is exactly constant even while junctions
exchange material. When all transport is off, amounts/histories are constant but
membrane/junction gates follow fixed-voltage analytic relaxation. Preserve
nonzero histories across all interventions.

Every actual RHS trial (including implicit Jacobian probes), native state and
observation must have finite positive inside/outside amounts, finite concentrations,
all declared membrane/edge |z F deltaV/(R T)| <= 50 even when inhibited, gates in
[0,1], and channel-owning voltages in [-0.120, 0.060] V. No clipping or refill.
Check whole candidate cubic extrema of both amount fields, gate values and all
membrane/edge voltages; also check its linear countercharge polynomial.
These floating-arithmetic domain checks are not rigorous continuous error bounds.
Implicit dense domains are checked at trial/native/common points, not globally
over every interpolation polynomial.

## Resources, artifacts and acceptance

One CPU worker and single-thread numeric libraries; pinned Python 3.13.5,
NumPy 2.5.3 and SciPy 1.18.1. At most 14 cases / 112 attempts, 100000 RHS calls
(including Jacobian probes), accepted steps per attempt and common samples per
case. Session wall cap 1800 s; artifact cap 512 MiB. These are work/output caps,
not OS memory guarantees. Qualification is not a performance benchmark.

Capture frozen numerical/checker/auditor/test dependencies before integration.
Use a new destination, refuse overwrites and retain native/dense/observation
arrays, bindings, settings, trial summaries, verdicts and failures.
A rejected candidate retains its completed prefix and exact offending
time/control/stage/state; no missing suffix is synthesized. Reference failure or
resource exhaustion stops with a failure receipt, without automatic retry or
larger limits. Unit preflights use shorter synthetic fixtures, not hidden full
panel attempts.

A read-only auditor verifies all payload/source identities and scope, replays
every observation from saved dense data, and recomputes accounting, control,
error, depletion and timestep-selection verdicts without rerunning an ODE.
Source hashes are provenance, not biological evidence. The accepted production
and all prior pilot/scientific artifacts remain unchanged.
