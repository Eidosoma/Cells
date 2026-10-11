# Next: a small channel–voltage feedback pilot

D092, 2026-09-14. **Conditional outline, not a registered experiment or launch.**
First require the [single-transfer independent closeout](BETSE_CHANNEL_TRANSPORT_CLOSEOUT.md)
to pass. Earlier isolated gating and passive comparisons remain qualified only
in their stated scopes; prior failures and input-sampling limitations remain.

## One scientific question

Do two independently implemented simulators converge on the same short feedback
response when a potassium channel changes cell/bath inventories and voltage,
and that changing voltage feeds back into its own m/h gates?

Use the existing Cells finite-bath family and shared, checked RK4. Keep the
native FULL solver and its own gate-before-transfer ordering. Do not prescribe
native post-gates into Cells during a trajectory: each engine must evolve its
own complete state. Agreement of one matched transfer does not establish this.

## Small scope before extra physiology

Retain the explicit seven-cell / thirty-face fixture, fixed geometry, uniform
Kv1p5 face targets, 298.15 K, matched F/R, one well-mixed finite bath and no
background leak, pumps, junction transport, auxiliary chemistry, mechanics,
flow or stochasticity. This is an engineering regime, not a physiological
resting-state preparation. Organ choice and tissue size remain data choices.

Keep four controls: network off, empty network, zero-permeability Kv1p5 and
active Kv1p5. For the first opening response, consider the already explicit
non-equilibrium pair m=0.2, h=0.6. Blocked channels must still evolve their gates;
only transport is blocked. The equal-product second pair can follow as a
separate history challenge once the simplest dynamic comparison closes.

Use a millisecond-scale candidate horizon that resolves measurable gate and
voltage change without approaching concentration or kinetic-domain boundaries.
**2 ms is a candidate to assess, not a selected timestep, accuracy claim or
registered horizon.** Set final duration and sample points from preparation,
signal-size, independent numerical and resource checks. Do not extrapolate the
21-second capture cost linearly: it includes setup and JAX compilation.

## Next implementation steps

1. Review and expose the actual native FULL-loop channel boundary. Carry the
   minimal configuration and explicit initial m/h through real initialization,
   without reinitializing them on the first recorded step. Prefer a fixed-control
   INIT opening experiment first; SIM events and suppression/recovery are later.
2. Run a separately registered, short full-loop preparation/observer check.
   Record observer-on/off counterparts and ensure observing changes neither
   state nor loop ordering. Initial P may still be absent; do not invent an
   initial update just to obtain a readout.
3. Define an independent coupled numerical reference and choose a bounded
   refinement panel. Candidate native steps are 25, 12.5 and 6.25 microseconds;
   choose Cells steps by its own refinement and validity checks. Do not inherit
   accepted step sizes from another model regime or match discrete methods.
4. Register the short comparison, precision, tolerances, observation semantics
   and complete compute/output caps before numerical capture. First compare
   constant controls; do not conflate input sampling with integration error.
5. Independently audit a passing result before longer recovery, interventions,
   more channel types, gap-junction transport or larger tissues.

Required observations: both gates; voltage; every modeled cell/bath inventory;
channel permeability and flux; outward native versus inward Cells current;
interval and accumulated transfer; and complete restart state. Distinguish fresh
constitutive rates from interval-averaged currents. Retain exact blocking,
species conservation, explicit auxiliary fixed charge and one-owned transfers.

## Implications for multiscale and GPU work

This is a useful small test of coupling interfaces, not a GPU optimization task.
Gates are local state; membrane transfers have explicit owners; a shared bath
requires a same-stage reduction across all contributing cells. Independent
experiments can be batched, but cells sharing a bath are not independent worlds.
Future partitioning, subcycling or tissue reduction must account for interface
errors and retain or explicitly approximate slow h history. Hardware placement
must not silently change the physics, precision or temporal coupling.

No full dynamic pilot is launched by this outline or by the preceding audit.
