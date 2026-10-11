# Native BETSE initialization and the corresponding Cells model

REF-003b1 / D066, 2026-09-12. **Status: native preparation rejected; numerical
alignment is not qualified.** Scope: initialization, charge closure and
prescribed one-update bookkeeping, before a full trajectory comparison.
The prospective [protocol](../validation/betse/alignment_protocol.json) fixes
inputs, checks and limits before execution. The [executed preparation result](../reports/REF003B1_PREPARATION.md)
contains seven actual cells despite the native single-cell flag. Configuration
loading and seeding ran; the later voltage/RHS/update checks described below did
not. Protocol revision 2 explicitly disables the native default general network;
all prior registrations and numerical criteria remain preserved.

**D067 follow-up:** the literal one-centre SVG route also fails native
triangulation. REF-003b1 remains rejected and the one-cell specification below
is retained as historical/prospective design. The separately named
[REF-003c seven-cell capture](../reports/REF003C_CLUSTER_ALIGNMENT.md) now executes
the corresponding charge/RHS/prescribed-update checks for all seven cells,
including the finite-bath normalization. D068's
[separate audit and closeout](../reports/REF003C_CLOSEOUT.md) now pass, including
the strict negative-evidence check for the one-centre SVG rejection.
References below to unexecuted checks describe the original one-cell protocol,
not the status of the new seven-cell adapter.

## The common physical setup

One fixed-volume, well-mixed cell exchanges Na/K/Cl with one finite,
well-mixed outside compartment. Geometry and temperature are fixed; there are
no pumps, active channels, gap-junction exchange, water, mechanics, regulation,
noise or imposed boundary voltage. Use BETSE's FULL solver configuration with
`cell polarizability: 0.0`, not its FAST equivalent-circuit solver.

This amends the initial maintained-bath proposal in [REF-003](BETSE_REFERENCE_PLAN.md).
Disabling BETSE's spatial extracellular simulation does **not** freeze outside
concentrations. Cells already has the corresponding finite-inventory family,
`finite_extracellular@1`; no new production physics or compatibility branch is
needed. The environment-volume normalization below is specific to this pinned
native pathway, not a change to Cells' general definition of a physical volume.

## Charge and preparation

The upstream [custom ion loader](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/parameters.py)
adds a charge-balancing anion M. It initializes neutral intracellular and outside
compositions; it does not accept our previous synthetic -40 mV state as an
independent voltage setting. Start at neutral charge / approximately 0 V, with
no claim of resting physiological equilibrium or completed equilibration.

The native custom profile includes Ca, protein P and M as well as Na/K/Cl.
Set all three auxiliary permeabilities to zero and disable Ca pumps and ER
dynamics. Their fixed net charges can then be represented by Cells' explicit
fixed-charge fields. This reduction is only for charge and passive transport:
it does not preserve auxiliary osmolarity, chemistry, ionic-strength-dependent
effects, or a resolved electrostatic field. Neither engine should be silently
neutralized after preparation or during a run.

BETSE computes charge density from the current ion concentrations, and in the
zero-polarizability mode computes membrane voltage from that density times
`cell_vol / cell_sa`, divided by specific capacitance, less the boundary
potential. See [get_current](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/ion_current.py),
[update_V](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim.py)
and [native geometry](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/cells.py).
With zero boundary potential this reduces algebraically to:

```text
C = total membrane area * specific capacitance
Q_inside = F * sum(z * intracellular amount in mol), including immobile ions
V_membrane = Q_inside / C
Cells: V = V_initial + (F * 1e-15 / C) * sum(z * amount_increment_fmol)
```

The anchored Cells expression avoids repeatedly subtracting large mobile and
fixed charges. BETSE's direct concentration sum can have a small floating-point
charge residual. Record and bound that residual rather than shifting either
voltage curve after the fact. A nonzero-polarizability BETSE simulation follows
a different, history-dependent voltage update and is outside this reduction.

## A non-obvious bath-volume convention

The pinned [update_Co](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/sim_toolbox.py)
nonspatial branch applies a face-wise concentration update using `p.vol_env`,
then takes the arithmetic mean over membrane faces. For M faces and a uniform
outside concentration before the update:

```text
delta_amount_inside = dt * sum(face_flux_density * face_area)
delta_c_outside = -delta_amount_inside / (M * p.vol_env)
```

Consequently the conservative lumped counterpart has **effective outside volume
M * p.vol_env**, not `p.vol_env`. This is an inference from the executed code
path's normalization, not an assertion that BETSE's configured physical box has
that geometric volume. Mapping directly to `p.vol_env` leaves a measurable
inventory residual. Uniform, one-face, balanced-face and blocked transfer probes
distinguish this convention from an area-weighted mean or a maintained bath.

Do not generalize this mapping to other versions, a spatial ECM, membrane-mesh
refinement, arbitrary initial outside heterogeneity or untested cell layouts
without rederiving and testing it. REF-003c now tests the particular seven-cell /
30-face case separately. Cells continues to own an explicit volume and one
equal-and-opposite amount transfer; it does not inherit this face-count rule.

## What the executable check is intended to do

Load a generated YAML with BETSE's actual `Parameters.load`, run its native
`SimRunner.seed`, then initialize actual `SimPhase`/`Simulator` objects using
`init_core` and `init_dynamics`. No patched functions, stubbed simulation objects,
or manually fabricated geometry are used. Source identity and all installed
BETSE Python files remain checked against v1.5.0, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`.

Six independently prescribed, conservative Na/K/Cl transfer states cover neutral
initial charge, inward sodium, outward potassium, inward chloride, neutral salt
and mixed transfer. Invoke actual `update_V`, `electroflux`, and
`update_all_concs` methods. The latter is a prescribed single update, **not** a
call to the whole simulator's time-integration loop. Four additional prescribed
flux footprints test outside normalization and conservation. Auxiliary species
must have zero transport.

Build an explicit Cells definition from the exported native area and volume,
resolve it through the unchanged production parser, and evaluate its actual
finite-compartment voltage and RHS using NumPy, eager JAX and compiled JAX on
CPU/float64. **These downstream numerical paths are implemented but not yet
executed against BETSE: the native cell-count guard stops first.** Native rounded
F/R and explicitly matched F/R are separate prospective profiles;
only the latter is a same-parameter cross-program comparison.

Absolute limits are 2e-10 V, 2e-12 mM, 2e-12 fmol, 2e-8 C/m³,
2e-10 fmol/s and 2e-20 A, plus relative 2e-11. Rate/current limits allow the
small direct-charge cancellation error to propagate through GHK; the earlier
[REF-003a](../reports/REF003A_PASSIVE_CONTACT.md) isolated-law comparison has
tighter flux limits. The checker replays saved quantities with independent
decimal GHK arithmetic and compartment accounting. Time is bounded to 25 seconds
per worker, 60 seconds overall, and 32 MiB of retained artifacts.

## Before running the first full trajectory

First resolve native geometry. The v1.5.0 `single_cell` mesh path creates a
central seed point and six surrounding points, and the actual seeded simulation
contains all seven as cell compartments with 30 membrane faces. Do not select
one trace and call the whole fixture a one-cell simulation. The next bounded
step should test whether an unmodified native geometry/configuration route can
produce exactly one cell with all unwanted mechanisms disabled. If that is not
available, explicitly register a seven-cell reference using Cells' existing
finite-compartment family; do not patch upstream or quietly relax the cell-count
requirement in this protocol. D067 has now tested the one-centre SVG alternative
and executed the explicitly seven-cell fallback; see the follow-up above.

Source inspection shows BETSE's `_plot_loop` uses N labels spanning 0 to N*dt, while its FULL loop
updates state before writing each sampled label. Thus the state after loop
index k belongs to elapsed update time (k+1)*dt, not automatically to its stored
label. The original one-cell schedule probe did not run because preparation failed;
REF-003c has since executed schedule construction only for seven cells. The later
adapter must retain raw labels, indices and an explicitly derived elapsed-time
column, including a separately captured initial state. Never relabel a native
post-update sample as an initial state.

Next register a short native FULL initialization-phase trajectory (a physical
transient, not a claim of equilibrium), with independent step refinement in
BETSE and Cells, then a declared permeability perturbation. Capture actual
native step counts and the timing of flux/current versus state observations.
Compare native-constant results separately from matched-constant results.
Keep conservation and analytic checks alongside curve comparisons. Follow the
[detached/no-poll policy](../AGENTS.md) for any long campaign.

This stage is not time-integration qualification, BETSE feature parity,
experimental biological validation, stable release promotion or GPU testing.
