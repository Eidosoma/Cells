# Electrical return currents between cell regions

The existing spatial cluster assigns junction-connected cells to one local
extracellular compartment. Extending that geometry requires a different field
closure: a charged junction transfer changes the capacitor charge at both ends,
so extracellular current must close the circuit. Setting extracellular current
divergence to zero independently would violate local capacitor countercharge.

The `cells.numerics.tissue_field` component supplies this instantaneous
calculation. The registered `spatial_extracellular@3` model composes it with finite
inventories, kinetic Na/K pumps, Kv1.5 channels and evolving junction conductance.
Qualification status is in `PROGRESS.md`. The `spatial_calcium@5` composition
adds the existing owned calcium/IP3 chemistry and assembly connection.

For cell i, let r(i) be its outside owner, V_i its membrane voltage and phi_r the
outside potential. Its absolute intracellular potential is V_i + phi_r(i).
The existing constant-field junction law uses the difference of those absolute
potentials. Existing logmean electrodiffusion determines each outside-face flux.
For every capacitor component, solve

    B_face I_face(phi) + B_junction I_junction(V + phi) = 0.

An incidence column is +1 at the sender and -1 at the receiver. Junction
incidence here maps to the two extracellular owners. A same-region junction
has a zero component-incidence column. Membrane transfer stays within a
capacitor component and therefore cancels from this component equation.

There is one declared potential gauge. Every active outside owner must be
connected by conductive outside faces even when all junctions are closed.
One membrane capacitor per cell and fixed geometry are required. This is a
bounded dense closure, not a general Poisson solver or multiple-surface model.

The capacitor/return-current constraint follows the charge antisymmetry argument
in the [ion-conserving electrodiffusive model of Sætra et al.](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007661),
particularly its four potential constraints. Our GHK junctions, logmean faces
and synthetic fixtures are explicit Cells choices; that paper does not validate
this implementation or supply these fixture parameters.

The algorithm starts from the outside-only solution, then uses damped Newton
iterations with the analytic GHK current derivative. One gauge row and column
are removed through masked unit rows; inactive padding does not ground a
physical compartment. The residual is checked at all nodes, including the
gauge, against `1e-23 A + 2e-12 * current_scale`. Newton targets 1% of that
bound to leave margin for independent local charge summation. Exhausted
iterations, failed line search or invalid domains return `converged=False`. No pseudoinverse,
concentration clipping, charge repair, or carried-over field is used.

The [component protocol](../validation/tissue/protocol.json) compares independent
scalar/bracketed or reduced roots, an analytic two-region resistor limit,
blocking, reversal, gauge changes, padding and return-path connectivity.
It checks species balance, local capacitor-current balance and the instantaneous
identity `d(chemical + capacitor energy)/dt + dissipation = 0` with separate
ownership arithmetic. An outside-only negative control must fail current balance.
Fresh CPU and L4 physical fields are compared with units-specific tolerances;
solver residual noise and iteration counts are not physical observables.

Run with the existing qualification launcher:

```sh
PYTHONPATH=src:. /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  validation/assembly/qualify_cell.py launch /mnt/workspaces/Cells/FRESH_RUN \
  --component-protocol validation/tissue/protocol.json
```

The launcher freezes sources and tests, runs CPU then L4, and retains result or
failure artifacts. Existing samplers record GPU busy time and SM activity with
coverage. A warm interval is explicitly unavailable for this correctness suite,
which compiles different kernels throughout; it is not guessed from the first
completed call. Utilization is descriptive and cannot fail a physics check.

For the evolving model, junction conductance uses the difference of absolute
intracellular potentials, including when availability blocks transport. Every
RK4 stage and combined endpoint uses its held controls for the field/domain
check through the optional `domain_valid.with_control` integration hook.
An unconverged root also yields rejected nonfinite RHS values. State-only
checks retain inventory, ledger and capacitor constraints. Existing Vm-based
definition/domain bounds remain additional conservative restrictions.

All twelve inventory, gate, transfer and dissipated-energy fields are ordinary
checkpoint state. The field is recomputed, never checkpointed as an independent
voltage. Existing complete snapshots, world IDs, windows and independent-world
batching therefore carry the whole simulation state.

This first evolving version requires observations at exact accepted integration
boundaries. No continuous interpolation enclosure is claimed for the nonlinear
field; off-grid requests are rejected. The
[trajectory protocol](../validation/tissue/dynamics_protocol.json) checks the
synthetic two-cell, three-region, 2-ms regime against independent scalar laws,
nonlinear roots and adaptive integration, then timestep refinement, full replay
and CPU/L4 agreement. Use the same launcher with this protocol path.

Native BETSE correspondence remains a separate comparison of shared physics.
Neither numerical gate establishes biological validation, general tissue
equivalence or multi-GPU scaling. Current status is in `PROGRESS.md`.

The calcium composition supplies **free cytosolic ionic amounts** to the tissue
field, membrane pumps/channels and junction transport at every stage. The
whole-cell exchange ledger still determines plasma voltage: binding and ER
exchange redistribute intracellular material without charging that capacitor.
Owned ER capacitors, reaction extents and dissipated-energy ledgers retain their
existing meanings. The new identity is explicit; old calcium definitions keep
the previous same-region electrical law.

Assembly uses the existing union of cell-owned event clocks. Each event segment
holds its actual channel availability and runs the same guarded coupled calcium
RHS. Protein pools remain separate and neutral; this is the existing one-way
channel-regulation hypothesis, without protein energy accounting or feedback
from calcium to assembly. Complete snapshots retain chemical inventories and
pending random events along with the ordinary transport ledgers.

The [calcium protocol](../validation/tissue/calcium_protocol.json) addresses the
specific risk of double-counting calcium or using total calcium as free calcium
when the electrical closure changes. It composes independently implemented
scalar chemical/process laws with independent field roots, checks adaptive
trajectories and event histories, and exercises full CPU/L4 replay. It also
checks the unchanged task identities in the eventual 16-GPU plan; that is an
architecture check, not a scaling measurement.

The [native spatial contact protocol](../validation/betse/tissue_contact/protocol.json)
addresses a separate comparison risk: the earlier native BETSE trajectories
used a shared outside bath, while the spatial FULL driver uses fixed boundary
reservoirs, a grid, and several membrane faces per cell. Its new capture enables
the native extracellular mode in the existing pinned preparation. It records
the actual seven cells, 30 membrane faces and 10-by-10 grid, then runs four
synthetic 8-microsecond cases at two timesteps, each with an observed/bare pair.
Those timesteps exercise source semantics; they do not establish trajectory
convergence. Pumps, dynamic channels and auxiliary chemistry are disabled.

The observer copies per-ion junction and extracellular calls, ordinary inventory
updates, and voltage updates. Separate checks reconstruct the reservoir resets,
membrane/edge transfers, and screened exterior voltage, including the source's
Gaussian smoothing. The recorded native boundary-operator inverse is an input
to that reconstruction, not an independently qualified Poisson solve. The
checker explicitly retains the pinned finite-difference routine's reversed
boundary derivatives and the native extracellular drift's `q/kb` constant ratio,
which differs from the matched `F/R` used in its GHK law. These are validation
adapter semantics; they do not change the Cells physical model. Reservoir
resets and net discrete-stencil exchange are reported separately from conserved
membrane/junction exchange, without asserting closed-system conservation for an
open native grid.

Native membrane voltage in this declared nonpolarizable mode subtracts the
boundary potential `Phi_b`, while extracellular transport uses the screened
charge-derived field. Cells' qualified tissue model instead solves a same-stage
return-current constraint and currently has one membrane/outside owner per
cell. The contact panel measures face ownership and within-cell voltage spread
so those differences cannot be hidden by averaging. Actual captured membrane
and junction GHK inputs are compared with the existing independent Decimal
reference and production Cells laws on CPU/L4. Passing these checks qualifies
shared transport laws and native update accounting, not equivalence of the
complete tissue trajectories. The existing component runner records both GPU
metrics; use it with the native contact protocol above. Current results and
preserved development failures are recorded in `PROGRESS.md`.

The next reusable component, `cells.numerics.surface_transport`, removes the
one-surface restriction from transport ownership. A cell has one absolute
interior potential, while each physical membrane patch has its own outside
owner, area, capacitance, permeability and voltage. With cell capacitor charge
`Q_i`, patch capacitances `C_m` and supplied outside potentials `phi_o`, it uses

    psi_i = (Q_i + sum_m C_m phi_out(m)) / sum_m C_m
    Vm_m = psi_owner(m) - phi_out(m).

It returns each patch charge and the corresponding outside countercharge. That
countercharge is an explicit constraint for the future coupled field solver;
this component does not assert it equals the supplied extracellular ionic
charge. It also accepts supplied absolute cell potentials for comparisons with
a separately declared field law. GHK membrane and junction transport and
conservative logmean outside faces accumulate through their actual owners.
Patch subdivision preserves total capacitance, material transfers and energy.

Reservoir owners have zero concentration-change rate and a separate signed
material-supply ledger. Positive supply enters the finite system. An explicit
boundary reset returns both the prescribed inventory and every injected or
removed fmol; it rejects invalid input rather than using the reset to repair
negative amounts. Finite-system species rates sum to reservoir supply. The
instantaneous electrochemical port-power identity includes that supply at its
boundary potential. A concentration reservoir alone does not specify the
electrical boundary or electrode work needed by a complete evolving model.

The [surface protocol](../validation/tissue/surface_protocol.json) addresses the
concrete risks of collapsing distinct patch voltages, double-counting membrane
owners and silently losing material at open boundaries. Independent scalar
capacitor sums, Decimal GHK laws and ownership accounting check the CPU/L4
component, including subdivision, reversal, padding, neutral species, controls,
world batching and partition replay. It reuses an authenticated completed native
capture and retains its inputs with the new evidence. The native grid is also
represented as 180 conservative faces and 36 reservoir nodes; those graph
coefficients are synthetic, not an implementation of BETSE's finite differences.

For the same declared ionic charge, BETSE's captured `Q_i / C_i - Phi_b`
membrane voltage differs from the resolved capacitor formula by the
capacitance-weighted mean boundary potential at that cell. The protocol measures
this correction and checks native membrane/junction fluxes using their actual
native voltage inputs. It does not absorb the mismatch into fixed charge,
change the already-qualified tissue law, or claim full trajectory equivalence.
The next integration needs a coupled field satisfying patch countercharge and
return-current constraints, with explicit electrical reservoir conditions.
Use the existing component launcher with the surface protocol; current status
and any failures remain in `PROGRESS.md`.

`cells.numerics.surface_field` now composes the resolved transport with those
charge/current constraints. Let `B_m` be the cell-to-outside membrane incidence
and `L_C = B_m diag(C_m) B_m^T`. At every finite node the field satisfies
`L_C phi = Q`, where `Q` includes ionic charge and fixed backgrounds. Outside
reservoirs impose held concentrations and absolute voltages. A closed geometry
instead declares one outside gauge, without adding an electrode at that gauge.

The capacitance graph can have several connected components. In each floating
component, the charge equations determine voltage differences but leave one
common offset. A reduced damped Newton solve determines those offsets by setting
the sum of outside-face and junction currents at each component to zero.
Membrane currents remain within their capacitance component and cancel from
this sum. Every finite-node charge equation is checked, including the rows
temporarily pinned in the linear solve, and every floating-component current
balance is checked, including the closed gauge component. Incompatible charge,
failed roots and invalid transport domains are rejected without charge repair.

The voltage-clamp electrode charge is `L_C phi - Q` at reservoir nodes. With
held boundary voltages, differentiating the capacitor equations gives patch
voltage rates and electrode current. The returned source terms obey

    d(chemical + capacitor energy)/dt + dissipation
        = reservoir electrochemical power + electrode power.

Reservoir material supply is still separate from electrode charge. Both sources
are needed when a voltage clamp touches a membrane capacitor. Changing a common
voltage reference can shift their individual electrical power terms; their sum
and the physical energy balance remain unchanged. Moving voltage clamps and
boundary interventions need an explicit later time-integration contract.

The [field protocol](../validation/tissue/surface_field_protocol.json) addresses
the concrete risk of satisfying current balance while violating membrane charge
or omitting external work. Its independent reference solves full-node equations
with scalar current laws and independently discovered topology. Checks include
the previous one-owner field law, clamped capacitor limits, gauge changes,
independent energy derivatives, source-ledger corruption, inactive padding and
world batching. Actual native geometry is exercised with declared manufactured
compatible charges and conservative graph coefficients; native screened-field
equivalence is not assumed. The field is a bounded numerical component,
limited to 256 total cell/outside nodes. Its evolving-model contract is described
below. Existing model identities and qualified laws remain unchanged. Use the
existing launcher with this field protocol; `PROGRESS.md` records qualification
status.

Exact world-partition and ordering replay uses `jax.lax.map`, the same mapping
primitive as `core.batch._batch_rollout`. The first field qualification used
direct `vmap` for this exact check and failed on L4 when changing cohort width;
its first differing voltage field changed by at most `4.34e-19 V`. The solver
and numerical tolerances remain unchanged. The corrected check retains exact
replay through the production mapping method, and separately compares direct
`vmap` cohorts against each other and the mapped results using the original
physical tolerances. Both execution methods receive independent charge/current,
material and energy checks, and their outputs and differences are retained.
Arbitrary direct-`vmap` cohort widths do not carry a bitwise-replay claim.

`resolved_tissue@1` registers the field as an evolving, passive resolved-surface
model through the ordinary runner, guarded RK4, snapshots and batch windows.
Its [trajectory protocol](../validation/tissue/surface_dynamics_protocol.json)
addresses the new risk that an instantaneous electrical identity can pass while
an evolving open system loses material, electrode charge or source work. The
initial ionic charge includes an explicit immutable fixed background and a
compatible charge anchor; subsequent charge comes only from inventory changes.
Every trial stage and combined endpoint uses its actual held membrane/junction
availability. Failed algebraic roots cannot advance a state.

The twelve state arrays retain inside/outside inventory changes, three route
transfer histories, reservoir material supply, three dissipation integrals,
electrode charge transfer, reservoir electrochemical work and electrode work.
All outside reservoir amounts remain at their declared initial values. Their
opposing route exchange is integrated into signed supply. Held boundary
voltages give electrode work `sum(phi_boundary * transferred_charge)`, and
held reservoir electrochemical potentials independently determine their work
from the supplied material. Owner balances, both work identities, capacitor
charges and `delta(chemical + capacitor energy) + dissipation - total work`
are checked with unit-specific tolerances. Total supplied ionic charge plus
electrode charge transfer must vanish. The closed-gauge case adds no source.

An independent DOP853 reference integrates the same serialized inputs with
full-node roots, scalar/Decimal transport and a separately pinned derivative
solve. It does not call the production parser, binder, RHS or RK4. The protocol
compares open, closed, clamped and scheduled-release trajectories, three time
steps, every stored state field and physical CPU/L4 observations. Restart and
partition tests exercise the actual registered model and complete checkpoints.
Independent-world batches require matching capacitor topology because the
reduced floating-component axis is part of their array layout. Ordinary ionic
ensemble reports identify the endpoint voltage axis as membrane patches.

This family currently holds boundary concentrations and voltages constant and
uses scheduled passive route openings. Existing kinetic, calcium and assembly
models are not silently replaced or projected into this electrical law. Their
composition, changing boundaries, native full-tissue comparison and larger
sparse/distributed solves remain subsequent work. The bounded dense limit is
still 256 total cell/outside nodes. The example
[configuration](../configs/resolved_tissue.json) is synthetic; qualification
status and run receipts belong in `PROGRESS.md`.

`resolved_tissue@2` composes the same resolved field with the existing named
Kv1.5 m/h channel, physical-time junction gate and maintained-pool Na/K ATPase
laws. Each channel uses its own patch voltage; junction kinetics use the
cell-to-cell potential difference. Availability multiplies transport without
resetting intrinsic gates. Multiple channel populations can occupy one patch.
The Kv1.5 composition is restricted to 298.15 K, with the existing declared
voltage domains and bounded RK4 steps.

Membrane processes join nodes within a capacitor-connected component and cancel
from its floating return-current equation. Junction opening changes that equation
and is supplied to the same-stage nonlinear solve. Pump and channel transport
still change ionic inventories, capacitor derivatives, reservoir exchange and
electrode current. All those rates are recomputed after composing the processes;
the passive electrode/work values cannot be reused.

Nineteen complete state arrays include the original twelve plus channel gates,
channel transfer/dissipation, junction gates, pump cycles/dissipation and signed
metabolic work. The membrane-transfer and membrane-dissipation state arrays
retain **baseline passive** transport only. Physical membrane-flux observations
report the total of passive, channel and pump transport. Pump stoichiometry is
inward-positive (`Na: -3, K: +2`); route transfer is outward-positive. Energy
accounting adds nonnegative pump/channel dissipation and subtracts metabolic
input, alongside reservoir and electrode work. Reversal can make pump cycles
and metabolic work negative without making dissipation negative.

The [kinetic composition protocol](../validation/tissue/surface_kinetic_protocol.json)
addresses missing pump/electrode work, incorrect patch-voltage ownership, hidden
gate resets during blocking and omission of evolving junction conductance from
the field solve. It reuses independent Decimal process references and integrates
the complete system with full-node roots and segmented DOP853. It also compares
all nineteen fields across restart, world partitioning and CPU/L4 execution.
The [example](../configs/resolved_kinetic_tissue.json) remains synthetic.

`resolved_calcium@1` adds the finite cytosol/ER chemistry, IP3 release,
Cav1.2 channels, PMCA and synthetic reversible NCX to that electrical model.
Each cell owns one chemical store and can have several membrane patches.
Only free cytosolic ions drive plasma and junction transport. The separate
whole-cell exchange ledger charges the plasma capacitors; binding and ER
exchange do not. ER charge establishes its own capacitor voltage. Fixed
chemical backgrounds incorporate the declared initial plasma charge without
counting charged buffers a second time.

Thirty-four complete state arrays preserve the nineteen electrical/kinetic
fields, seven chemical/ER fields, three plasma transport fields, three Cav
fields and separate PMCA/ER ATP-work ledgers. The original metabolic-work
ledger remains Na/K ATPase work. All membrane transfer ledgers, including the
new Cav ledger, are **outward-positive** in this family. Total chemical energy
counts free and bound intracellular species once, plus extracellular ions.
Both plasma and ER capacitor energies, every dissipative process, and all
three maintained ATP sources enter the energy balance.

This first composition requires **closed finite exterior compartments**. Its
concentration bounds use conserved global ionic moieties; a held calcium bath
would invalidate that bound and is explicitly rejected. The synthetic example
uses exterior calcium of 0.02 mM to keep this conservative verification bound
practical. It is not a biological calibration. Chemistry-only control changes
are retained as accepted observation boundaries. Timesteps are at most 50 us
and must also satisfy the combined chemical/calcium-transport loss bound.

The existing assembly event runner can control every Kv1.5 population owned
by a cell. It uses the same guarded electrical/chemical stages between the
union of the cell-owned event clocks. Assembly remains a one-way neutral
protein/channel-availability hypothesis. Reports identify voltage by membrane
patch and retain IP3 and all calcium-channel owners when aggregating worlds.

The [resolved calcium protocol](../validation/tissue/surface_calcium_protocol.json)
targets double-counted calcium/charge, missing ATP work, incorrect patch
ownership and event/restart errors using independent full-node roots, scalar
chemistry and segmented DOP853. Examples are provided for
[ordinary execution](../configs/resolved_calcium_tissue.json) and
[assembly coupling](../configs/assembly_resolved_calcium_tissue.json).
Qualification status and receipts remain in `PROGRESS.md`. Held-bath calcium,
moving boundaries, native full-tissue comparison and larger sparse/distributed
solves remain open.

`betse_spatial_passive@1` is a separate compatibility component for pinned
BETSE 1.5.0 passive spatial updates. It rebuilds the exterior Dirichlet
operator from grid topology and implements BETSE's screened-charge Gaussian
field, edge-derivative signs and forward-Euler update order. Membrane
concentrations lag the junction update; they are independent checkpoint
fields. Membrane transfer is inward-positive in this component, and junction
transfer is outward-positive. The resolved field and energy models above
retain their existing laws.

The native exterior stencil can change total material independently of held
boundary resets. Separate per-species, per-grid-site ledgers record both
terms; cell/exterior accounting includes membrane and junction transfers.
This reproduces the native law without claiming a conservative finite-volume
scheme or thermodynamic energy balance. Invalid trials retain the complete
prior state, including clocks and ledgers.

The [native trajectory protocol](../validation/betse/spatial_trajectory/protocol.json)
targets field conventions, hidden forcing and update-order errors by comparing
every completed step of four freely evolving passive cases at two timesteps.
Only native initial concentrations and static geometry/parameters initialize
the component; subsequent native states are comparison targets. Independent
harmonic-field checks and native material accounting accompany full-state
restart, world partitioning and CPU/L4 comparisons. The initial panel covers
seven cells, thirty membrane patches and a 10 by 10 exterior grid over eight
microseconds. Longer trajectories, refinement, active biology, ordinary
model-registry integration and remote multi-GPU execution remain subsequent
work. The dense boundary solver is limited to 256 grid sites. Qualification
status and receipts belong in `PROGRESS.md`.

The [extended protocol](../validation/betse/spatial_trajectory/refinement_protocol.json)
examines the same four cases through 256 microseconds at 1, 0.5 and 0.25
microsecond steps. It reuses the unmodified native recorder, checks observed/
bare neutrality, and compares the original eight-microsecond prefixes by
completed-step time. Native clock labels depend on total duration and are
not interchangeable with completed-update time. Both native and Cells
trajectories receive separate self-refinement checks at 64, 128 and 256
microseconds. Only differences above the comparison resolution can establish
first-order behavior; required changing fields prevent a constant trajectory
from satisfying that claim. This does not establish spatial convergence.

Physical concentration, voltage, flux and material tolerance floors remain
unchanged. Longer accumulated material balances additionally report an
inventory-scaled float64 rounding allowance, separately from the measured
residuals: `gamma_n = n*eps/(1-n*eps)`, with `n = 32*completed_steps`.
The conservative operation allowance covers reductions over the thirty
patches and the concentration/ledger updates; global allowances sum local
ones. This bounds bookkeeping resolution, not nonlinear integration error.
Native per-update accounting retains its original tolerances, and deliberately
corrupted ledgers must still fail. The 6e-17-second clock tolerance covers
sequential additions through 1,024 steps. Qualification outcomes remain in
`PROGRESS.md`.

`betse_spatial_nak_kv1p5@1` composes that spatial law with the existing
positive-domain Na/K ATPase and Kv1p5 m/h kinetics. It preserves the native
semi-implicit gate update and separate channel concentration update. Ordinary
leak and pump rates use the old lagged membrane concentrations; the channel
uses bulk cell concentrations and the exterior after its diffusion step.
Channel transfer precedes the ordinary membrane/junction concentration
updates. Native channel current is separate from `fluxes_mem`, so a dedicated
channel-transfer ledger prevents either omission or double counting. Pump
cycles also have their own diagnostic ledger; their -3 Na / +2 K transfer is
already included in the ordinary membrane ledger. All thirteen state arrays,
including m/h, transfer histories and clocks, belong in a restart.

The [active spatial protocol](../validation/betse/spatial_active/protocol.json)
compares six synthetic cases at 1 and 0.5 microsecond steps through 64
microseconds. Pump-only, channel-only, combined, blocked and partial controls
expose missing transport, gate feedback and incorrect exterior sampling.
The native loop and numerical methods stay unmodified; declared setup hooks
set initial gates and static controls before integration. Observed/bare pairs,
independent Decimal pump/flux calculations, per-update material accounting,
complete trajectory comparisons and replay checks address those risks.
Maintained ATP/ADP/Pi, one Kv1p5 population and fixed geometry limit this
component's scope. Finite ATP, a wider native channel catalog, registry
integration and remote multi-GPU execution remain open.

The [active refinement protocol](../validation/betse/spatial_active/refinement_protocol.json)
extends four active cases through 256 microseconds at 1, 0.5 and 0.25
microsecond steps, using the same laws and tolerances. Native and Cells
histories are independently checked at 64, 128 and 256 microseconds; gates,
pump/channel rates and their transfer ledgers have separate physical units
and comparison budgets. First-order behavior is required only where changes
are resolved above numerical comparison tolerances, with membrane voltage
and the activation gate required to resolve in every case. The original
64-microsecond native and Cells state/rate prefixes must match bitwise;
derived field readouts retain their registered numerical tolerances.
The protocol requires a completed passing CPU/L4 predecessor before capture,
then checks complete histories and thirteen-array restart/world replay.
This addresses temporal integration and accumulation errors; it does not
establish spatial convergence or long-term biological behavior. Qualification
status and receipts remain in `PROGRESS.md`.

The active compatibility component also has an ordinary Cells configuration
in [betse_spatial_active.json](../configs/betse_spatial_active.json). It uses
the explicit `betse_ordered_euler@1` solver, preserving the qualified native
update and the declared timestep exactly. Accepted clock labels are multiples
of that timestep; subtracting adjacent labels does not change the numerical
step. Complete snapshots retain thirteen state arrays, including the lagged
membrane concentrations, separate channel/pump ledgers and the accumulated
clock. The ordinary run, snapshot, window and independent-world paths share
this solver. Qualification status remains in `PROGRESS.md`.

The first qualified configuration accepts static controls, fixed geometry,
steps of at most one microsecond and horizons through 256 microseconds.
Observations must land on accepted steps. A branch can extend the horizon or
change observations while retaining the original physical definition;
scheduled forcing is a separate qualification described below; geometry changes
remain outside this version. The example
retains native Na, K, Cl, Ca, P and M in their original array order. Only Na,
K and Cl move; the fixed species still contribute charge.

The `tissue` arrays use SI geometry: volume in m³, area in m², spacing/height
in m, permeabilities in m/s, diffusivity in m²/s, temperature in K, capacitance
density in F/m² and permittivity in F/m. Concentrations are mM (numerically
equal to mol/m³), boundary potentials are V, extra charge densities are C/m³,
and the screening wavenumber is m⁻¹. `cell_size_ratio` is dimensionless;
`native_q_over_kb` is K/V. Owner/partner arrays are zero-based indices and
`moving` is boolean. Pump capacity is fmol cycles/s, metabolic pools and Km
values are mM, and `delta_g0_J_mol` is J/mol. All arrays are explicit inputs;
the normal simulator has no dependency on native BETSE or saved run folders.

For example, from the Cells checkout with the GPU environment:

```sh
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -m cells windowed run \
  configs/betse_spatial_active.json --window-steps 257 --recording full \
  --output /mnt/workspaces/Cells/betse-active-example-01
```

The [runtime protocol](../validation/betse/spatial_active/runtime_protocol.json)
checks configuration export against all native initial/static arrays, complete
histories against the qualified CPU/L4 states, disk/window/batch replay,
independent clocks, refusal of invalid trials and existing shared-runner RK4
regressions. This specifically addresses integration and serialization risk;
it does not extend the biological or spatial-convergence claim of the kernel.

Scheduled pump/channel availability uses the optional `experiment.changes`
list. Each entry gives `time`, `pump` and `channel`, with one fraction in
`[0,1]` per membrane patch for both controls. A nonempty schedule starts at
zero and increases strictly at accepted fixed-step boundaries. Fractions
multiply the model's baseline pump availability and channel permeability;
they do not reset concentrations, gates or material ledgers. Intrinsic Kv1p5
gates keep evolving while channel transport is blocked. Definitions without
changes retain their existing serialized identity and implicit unit fractions.

A change at time `t` controls the step starting at `t`; the state recorded at
`t` contains the preceding completed updates. Checkpoints include the event
cursor, and branches may alter inputs at or after their checkpoint but cannot
rewrite earlier inputs. An event at the horizon does not take another step.
Static and scheduled worlds can share a batch while keeping independent clocks.

[betse_spatial_interventions.json](../configs/betse_spatial_interventions.json)
provides a GPU example through 64 us: both routes start available, are blocked
at 16 us and are restored at 40 us. The
[intervention protocol](../validation/betse/spatial_active/intervention_protocol.json)
tests six cases at 1 and 0.5 us steps, including separate routes, regional
targets, staggered changes and a neutral schedule. This targets event timing,
owner mapping, hidden gate resets and lost restart state. The native input
hook runs in both observed and bare captures; it prescribes availability
between completed FULL INIT updates without replacing native methods or using
native endpoint labels as physical time. This is a declared external input,
not a claim about native built-in SIM tissue events or inhibitor chemistry.
Independent per-step laws/accounting, unchanged native comparison tolerances,
CPU/L4 agreement and exact event/window/world replay are required. Qualification
status belongs in `PROGRESS.md`; this panel makes no longer-time, biological
recovery, finite-ATP, spatial-convergence or multi-GPU performance claim.

The [long intervention example](../configs/betse_spatial_interventions_long.json)
extends the same block/release schedule through 256 us at a 0.25 us step. The
[scheduled refinement protocol](../validation/betse/spatial_active/intervention_refinement_protocol.json)
addresses accumulated error and restart behavior beyond the original horizon:
all six schedules run at 1, 0.5 and 0.25 us, with native and Cells comparisons
at common completed times, including the intervention boundaries. Fluxes at a
boundary describe the interval ending there; the new input drives the next
interval. The checks retain the existing physical tolerances and first-order
resolution criteria, preserve the original 64-us state/rate prefixes, and
exercise finer-step disk/window/world replay and saved-horizon extension.
This panel authenticates the complete prior qualification and all its unchanged
source files before extending it. Resolved temporal refinement does not establish
continuum accuracy, spatial convergence or biological recovery; completion and
results remain recorded in `PROGRESS.md`.
