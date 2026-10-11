# Physical gated pair: Cells 0.6.0

`bioelectric_pair@1` composes two well-mixed Na/K/Cl cells, each with one
bath-facing membrane, and one species-selective junction with an evolving gate.
It reuses the one-cell membrane laws, shared RK4 engine, conservative graph
scatter, observation interface and complete checkpoints. The three axes for
cells, membranes and contacts have independent capacities and stable identities.

This is a synthetic dimensional engineering model, not calibrated connexin or
pump kinetics, BITSEY/BETSE parity, a heredity result, tissue or an organ.
The [physical specification](SELECTIVE_CONTACT_SPEC.md) defines equations and
omissions. The [independent numerical reference](SELECTIVE_CONTACT_NUMERICS.md)
precedes the [production acceptance](../reports/MODEL004_ACCEPTANCE.md).

## Run, resume and intervene

From the Cells directory, every output path must be new:

```bash
taskset -c 0-3 .venv/bin/python -m cells validate configs/bioelectric_pair_baseline.json
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_pair_baseline.json --output runs/my-physical-pair --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-physical-pair/snapshots/step-006000 --output runs/my-pair-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-physical-pair/snapshots/step-006000 configs/bioelectric_pair_branch.json --output runs/my-pair-branch
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_pair_controls.json --output runs/my-pair-controls
```

The baseline runs ten seconds, not automatic equilibration. The branch starts
from the exact six-second state, independently inhibits/restores A's Na leak,
B's pump and the junction, and includes a 0.7 ms contact block. No gate, chemical
history, charge anchor or diagnostic integral is reset. The separate one-second
controls example implements the frozen Q18 sequence.

Model and execution settings cannot change in a branch. Only future controls,
horizon and observation times may change, preserving the checkpoint's integration
boundary and past schedule. Complete snapshots require the same package sources
and runtime. Earlier releases are preserved in source archives; they are not
silently migrated. See [version preservation](../reports/MODEL004_ACCEPTANCE.md#version-preservation).

## Definition and storage

All units are explicit: fmol, pL, mM, seconds, volts, square metres, metres/second,
F/m², kelvin and J/mol pump cycles. The diagnostic energy integral uses pJ.
Species order is Na/K/Cl. No source-coordinate or time conversion is implicit.

The model declares exactly two cells, two effective membranes, one oriented
contact and one shared clamped bath. Cell IDs resolve membrane ownership and
contact endpoints before device allocation. Membrane records and control groups
may be reordered: their IDs, not their JSON positions, select the membrane.
Leak controls name the ions and are normalized to model order. IDs must be unique
within each entity family; the cell, membrane, contact and bath namespaces are
distinct. Additional capacity slots are inactive, not extra biological entities.

| Evolving field | Axes | Meaning |
| --- | --- | --- |
| `amount` | species, cell slot | Sole mobile-ion inventory, fmol |
| `leak_transferred` | species, membrane slot | Signed inward bath exchange history, fmol |
| `pump_cycles` | membrane slot | Signed forward pump history, fmol cycles |
| `transferred` | species, edge slot | Signed from-endpoint to to-endpoint history, fmol |
| `gate` | edge slot | Endogenous evolving fraction in [0,1] |
| `dissipated_energy_pJ` | diagnostic process | Integrated leak, pump and junction dissipation, in that order; no feedback into dynamics |

Voltage is derived from amounts and immutable amount/voltage/capacitance anchors,
not integrated independently. The contact has no material inventory or additional
capacitance. Changing its transport area does not change either bath-facing
membrane capacitance. Unequal capacitances require capacitance-weighted electrical
accounting, not conservation of the unweighted voltage sum.

Three signed material ledgers are history, not additional matter. Energy integrals
are diagnostic history and are checkpointed so resolved energy accounting spans
restarts. Gate conformational energy, gating current and intervention costs are
explicitly excluded. Assigned assay scores/costs are not these physical integrals.

## Controls versus biological state

`experiment.membrane_controls` contains one independent leak/pump group for each
declared membrane. Each schedule begins explicitly at zero, is right-continuous,
and has strictly increasing times within the horizon. Contact control is a
separate `prescribed_contact_multiplier` schedule identifying the contact ID.
All multipliers lie in [0,1]. The host resolves their event union into a PyTree
with separate membrane and edge array capacities.

The contact multiplier scales both residual and gate-dependent permeability.
At multiplier zero all transport stops but the gate keeps evolving. At gate
zero a species with nonzero residual permeability may still pass. At species
permeability zero that species never passes. Inactive padding is distinct from
all of these cases. Every flux is computed once from the common RK stage and
scattered with opposite signs at its two endpoints.

## Numerics, observations and failure

CPU float64 RK4 uses a zero-anchored, event-split grid with maximum nominal step
**0.001 seconds**. Floating grid differences have a small explicit roundoff
allowance. The inherited one-cell 0.005 s setting is rejected for this model.
The independent panel qualifies its 20 declared parameter/control cases through
one or ten seconds, not an arbitrary parameter box or long-horizon physiology.
New regimes need their own refinement and independent comparison.

Every trial and accepted endpoint requires finite state, positive active ion
amounts, gates in [0,1], exact zero inactive state, and membrane/junction
`abs(z F deltaV / (R T)) <= 50`. Numerical failure is refused before publication;
no clipping, projection, concentration floor or interpretation as cell death.
Finite neutral padding is supplied before divisions, logarithms and gate laws.
Resource limits are checked before capacity-sized allocation.

Requested observations do not alter integration. Cubic Hermite sampling uses
both endpoint slopes under the interval's held control; at a discontinuity the
left interval's right slope still uses the old control. Exact stored endpoints
are returned unchanged. Instantaneous readouts at the event use the new control.
Every amount, gate and affine voltage interpolant is checked at its floating
polynomial extrema, including when no interior samples were requested. Nonfinite
slopes or coefficients are refused. This is not a rigorous continuous-time
accuracy bound or interval-arithmetic proof.

Saved trajectories include all accepted state, all immutable layout arrays,
observed concentrations/voltages, gate targets/rates, independent control values,
fluxes, currents, chemical work/power, dissipation and accounting residuals.
Material, charge-as-voltage and resolved-energy residual limits are respectively
1e-8 fmol, 1e-8 V and 1e-6 pJ. Manifest metadata identifies the stage-domain and
extrema-checked sampling policies. All five earlier models retain their existing
numerical and observation policies.

## Scope of the next step

This closure is not a general ionic graph solver, arbitrary model-composition
language, channel-gate model, finite bath, field, geometry or regulatory coupling.
The [source map](SOURCE_COUPLING_MAP.md) identifies a different source algebraic
gate, upwind transport and nominal regulatory clock. That source-compatible model
and its coupled reference trajectories remain a separate acceptance gate.

The explicit gate is useful for later multirate/reduced-model comparisons: a
reduction must preserve intervention response and memory, not merely final
voltage. Independent-world execution, representative work/memory profiles,
multirate solvers, device partitioning and GPU measurements remain future work.
More GPU throughput alone does not remove the measured gate timestep restriction.
