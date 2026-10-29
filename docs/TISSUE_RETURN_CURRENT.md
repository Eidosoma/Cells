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

If an original component run completes CPU qualification and then stops at a
GPU resource guard, the same launcher can recover into a fresh output with
`--component-parent /mnt/workspaces/Cells/FAILED_RUN` and
`--component-protocol /mnt/workspaces/Cells/FAILED_RUN/component-protocol.json`.
It checks the parent's frozen source, test collection, complete group results,
saved evidence and runtime identities before reusing completed groups. Only
the interrupted and unstarted GPU groups execute. Numerical code, references,
tests, parameters and resource limits stay identical; only the qualification
controller is updated. The failed parent remains intact. The completion record
identifies reused versus executed groups, and new GPU measurements describe
only the recovery interval. Scientific failures and incomplete CPU phases are
ineligible for this recovery path.

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

The experimental [dynamic junction component](../src/cells/numerics/betse_junction.py)
composes evolving junction openings with the same spatial pump/channel kernel.
It keeps fourteen state arrays and an explicit moving-ion order. In pinned BETSE,
each moving ion advances the stored opening by one full outer timestep before
using it for transport. Blocking then multiplies that stored opening. These
source-compatibility rules differ from the separate physical-time junction law,
where availability controls transport without overwriting the intrinsic gate.
No existing model or numerical kernel is changed by this composition.

The [junction protocol](../validation/betse/spatial_active/junction_protocol.json)
checks six cases through 64 us at 1 and 0.5 us steps: coupled transport, reversed
ion order, half blocking, block/release, disconnection and one connected pair.
Independent scalar gate/flux checks accompany complete native trajectories,
material accounting, CPU/L4 comparison, disk state restoration and independent
world replay. Geometry, metabolic pools and the Kv1p5 population retain the
previous scope. This component currently exposes the array API; integration
into the ordinary configuration and snapshot registry is a subsequent task.
Current qualification results belong in `PROGRESS.md`.

## Mixed potassium channels in resolved tissue

`resolved_tissue@3` extends the physical-time resolved model with independently
declared Kv1.5 and Kir2.1 populations. Each population names its membrane patch,
K species, maximum permeability, abundance, initial m/h gates and availability
schedule. Two populations may share a patch; their signed ionic transfers and
dissipated energy add through that patch's actual cell/outside owners. Intrinsic
gates continue evolving while availability blocks transport. All nineteen state
arrays, including each population's gates and ledgers, remain ordinary snapshot
state. The numeric layout carries the per-population law codes for GPU execution.

[The GPU example](../configs/resolved_channels_cluster.json) declares five
populations in a synthetic two-cell tissue. It uses the ordinary runner:

```sh
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -m cells run \
  configs/resolved_channels_cluster.json \
  --output /mnt/workspaces/Cells/resolved-channels-example-01
```

The new law `betse_kir2p1_mh2@1` uses the coefficients and **m × h²** opening in
[pinned BETSE's Kir2p1](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_k.py#L730-L779).
Cells expresses those equations independently in volts and seconds and integrates
`dg/dt = (g_inf(V) - g)/tau(V)` with its existing guarded RK4 solver. The
coefficient provenance is BETSE's implementation; its cited Makary experiment
has not been independently refitted here. No upstream source is vendored and
normal simulation does not import BETSE. Its unmodified channel methods run
only in the separate validation environment, with pinned source hashes.

This identity requires 298.15 K, patch voltages within [-0.120, 0.060] V and
steps at most 25 us. These are declared implementation bounds, not a claim of
temperature calibration or accuracy in every allowed configuration. Gates are
explicit initial conditions; there is no implicit equilibration. Invalid state,
law code, field solve or trial is rejected without clipping or state repair.
`resolved_tissue@2` and `resolved_calcium@1` retain their Kv1.5-only
identities; changing a channel law cannot be disguised as a checkpoint restart.

The [qualification protocol](../validation/tissue/surface_channel_protocol.json)
separates native law/discrete-clock correspondence from the continuous coupled
model. It checks 37 clamp voltages against native and independent Decimal
equations, analytic relaxation, and four synthetic 2-ms tissue cases against
independent field roots and adaptive integration. It also checks timestep
refinement, conservation, control boundaries, disk/fresh-process restart,
branches, windows, independent worlds and CPU/L4 agreement. Refinements and
replay controls are not extra biological cases. Native full-tissue equivalence,
experimental validation and Jupiter scaling require separate evidence. The
calcium/assembly composition is described below. Current run status belongs in
[Progress](../PROGRESS.md), including both GPU utilization measurements.

## Mixed potassium channels with owned calcium chemistry

`resolved_calcium@2` composes `resolved_tissue@3` with the existing finite
cytosol/ER stores, buffered calcium and IP3, Cav1.2, PMCA and synthetic NCX.
Each potassium population retains its own Kv1.5 or Kir2.1 law, intrinsic gates,
availability and transfer/energy ledgers. The shared membrane voltage couples
potassium transport to calcium-channel kinetics. Only free cytosolic ions enter
transport laws; binding and ER exchange do not create a second plasma inventory
or charge the plasma capacitors. The 34 complete state arrays retain all
chemical, ionic and maintained-source work accounting.

The new model identity and checkpoint layout retain the numeric potassium law
codes through GPU execution, windows and independent-world batches. Ordinary
and assembly examples are provided in
[resolved_calcium_channels_tissue.json](../configs/resolved_calcium_channels_tissue.json)
and [assembly_resolved_calcium_channels_tissue.json](../configs/assembly_resolved_calcium_channels_tissue.json).
Cell-owned assembly pools control both potassium channel types, including
multiple populations on one patch. Assembly remains the existing one-way
neutral-protein availability hypothesis; this composition adds no biochemical
feedback to assembly and makes no experimental assembly/calcium claim.

The [composition protocol](../validation/tissue/surface_calcium_channel_protocol.json)
targets lost channel-law identity, duplicated ion ownership, missed ATP work
and event/restart errors. It reuses the independent full-node electrical roots,
Decimal potassium equations and scalar calcium chemistry, then compares all
four synthetic 2-ms histories with segmented adaptive integration. Assembly
events, timestep refinement, legacy reductions and replay are numerical
controls, not additional biological cases. CPU and L4 compare complete saved
states and readouts; GPU busy and SM-active are recorded separately.

The bounds remain a closed finite exterior, 298.15 K, patch voltages within
[-0.120, 0.060] V and guarded RK4 steps at most 25 us, also subject to the
chemical loss bound. This is a continuous-time composition, not native BETSE
coupled calcium/tissue equivalence or a parameter fit. Held baths, finite
metabolic supply and interacting tissue distributed across GPUs remain open.
Qualification results belong in [Progress](../PROGRESS.md).

## Sodium and potassium channels in resolved tissue

`resolved_tissue@4` adds independently owned NaV1.2 populations alongside Kv1.5
and Kir2.1. The channel declaration binds NaV to sodium and Kv/Kir to potassium.
Different species and channel types may share a membrane patch while retaining
separate gates, material transfers and dissipated-energy ledgers. The ordinary
runner, complete nineteen-array checkpoints, windows and independent-world GPU
batches use a distinct model/layout identity. The previous potassium and calcium
model identities keep their existing catalogs.

The law `betse_nav1p2_m3h_regularized@1` independently expresses the coefficients,
voltage shifts and **m³ × h** opening in
[pinned BETSE's Nav1p2](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_na.py).
Gate inputs use volts; time constants use seconds. The existing GHK law determines
ionic flux from concentrations and voltage; the source's nominal reversal-voltage
attribute does not replace that calculation. This is source-model correspondence,
not a new fit to the measurements cited by BETSE.

The native rate expressions have removable singularities at **−25, −40 and
−65.000123 mV**. Cells evaluates the continuous limits with its existing
mask-safe Bernoulli function. For the three vanishing rate numerators, the
limits are respectively 1.638/1.116, 0.12 and 0.0455 per millisecond. The
independent 80-digit Decimal reference uses the direct exponential expressions
and analytic limits. Native nonfinite probes are retained separately from finite
native comparisons; they are not silently treated as successful comparisons.
The finite −65-mV source sample also loses precision through `1-exp` subtraction.
It remains in the capture and native clock checks. A separate replay of native
float arithmetic explains that value; the stable implementation is checked
against Decimal at every finite sample. Direct native parameter agreement uses
the remaining sweep points, with the dimensionless rate argument at least
`1e-4` from a removable zero. Neither diagnostic changes coupled-trajectory
or CPU/GPU tolerances.

The unmodified native methods run only in the separate validation environment.
Their native semi-implicit gate clock is checked separately from Cells' continuous
RK4 integration. The inspected `vg_na.py` SHA-256 at BETSE commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2` is
`6faa67bdc4bfd0ee35dc1cc0fd8dcd73a703ff58120d1b1968da94dac1fe8831`;
`channelsabc.py` retains
`ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4`.
No upstream source is vendored or imported by ordinary simulation.

[The GPU example](../configs/resolved_sodium_cluster.json) declares seven
populations in a synthetic two-cell, four-patch tissue. It uses 298.15 K,
patch voltages within [−0.120, 0.060] V, explicit initial gates and RK4 steps
no larger than **2.5 us**. These declared bounds do not guarantee accuracy for
every possible configuration. Invalid state, fields and trials are rejected
without clipping. The ordinary runner accepts the example as follows:

```sh
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -m cells run \
  configs/resolved_sodium_cluster.json \
  --output /mnt/workspaces/Cells/resolved-sodium-example-01
```

The [qualification protocol](../validation/tissue/surface_sodium_protocol.json)
checks source equations, singular limits and analytic clamps, then four synthetic
2-ms open/closed/clamped/release histories against independent field roots and
adaptive integration. Sodium-only ablation exposes species/owner mistakes;
potassium-only reduction, complete replay, heterogeneous worlds and CPU/L4
comparison guard the shared execution paths. Existing physical tolerances remain
unchanged, with 2.5/1.25/0.625-us refinement of both clamped and release cases.
These controls do not establish measured excitability or native full-tissue
equivalence. Run results and both GPU utilization measurements belong in
[Progress](../PROGRESS.md).

## Sodium and potassium channels with owned calcium chemistry

`resolved_calcium@3` composes the sodium/potassium catalog from
`resolved_tissue@4` with the existing owned cytosol/ER, calcium buffers, IP3,
CaV1.2, PMCA and synthetic NCX. It adds no new fitted channel or transport law.
An explicit layout carries the catalog through the free-cytosol view:
NaV uses its owner's free sodium, including changes from internal chemistry.
The complete state retains the existing 34 arrays and per-population transfer
and energy ledgers. Earlier calcium versions keep their restricted catalogs.

The [ordinary example](../configs/resolved_calcium_sodium_tissue.json) and
[assembly example](../configs/assembly_resolved_calcium_sodium_tissue.json)
use the GPU backend. They retain the closed-exterior, temperature, voltage and
chemical-loss restrictions of the earlier calcium family, with sodium steps
at most 2.5 us. Assembly regulation remains one-way and cell-owned.

The initial [composition checks](../tests/unit/test_surface_calcium_sodium.py)
cover independent rates, sodium ownership and selective blocking, earlier-model
reduction, a 50-us compiled trajectory/checkpoint and initial assembly reporting
and planning. They are bundled with the sodium regression in the
[combined protocol](../validation/tissue/sodium_composition_protocol.json),
with separate evidence requirements.

The [full composition suite](../tests/unit/test_surface_calcium_sodium_full.py)
and [qualification protocol](../validation/tissue/surface_calcium_sodium_protocol.json)
extend these checks to four complete 2-ms trajectories, baseline and release
refinement at 2.5/1.25/0.625 us, conservation and energy accounting, complete
restart/world replay, assembly dynamics and CPU/L4 agreement. The suite reuses
the calcium family's physical tolerances. Host planning checks the finer grids
and aggregate batch work before integration; the two-world allowance is 2,048
padded steps, with 1,024 for a single world. Earlier models retain their
original test settings. This composition allows 2 GiB for a single trace
and 2 GiB for aggregate batch working arrays, covering the finer grids'
conservative storage estimates. These are resource bounds, not changes
to numerical tolerances.

Additional controls check that each cell's assembly pool regulates its own
sodium and potassium populations, that heterogeneous worlds keep distinct
law/species arrays, and that checkpoints reject a changed channel law or
transported species. These controls and refinements are numerical checks,
not independent biological cases. The full protocol requires independent
trajectory evidence and complete replay; initial rates and successful planning
alone cannot qualify the composition. Current results and pending runs are
recorded in [Progress](../PROGRESS.md). Local planning does not establish
multi-GPU or Jupiter execution.

Store, plasma-transport and calcium-channel changes share the complete accepted
event clock. A chemical-only event can therefore be an observation boundary
even when it falls between nominal electrical steps. Observations at other
off-grid times remain invalid, and the 2.5-us sodium step cap still applies.
Three 50-us execution controls apply these events at 37 us, compare all
observed state fields with segmented independent integration, check local
transfer stopping and continuing intrinsic gates, and resume complete state
from a disk checkpoint at the event. They supplement the longer qualification
cases; their results remain scoped to event handling and replay.

## Shared HCN gates and multi-ion transport

`resolved_tissue@5` adds HCN1, HCN2 and HCN4 alongside the existing NaV1.2,
Kv1.5 and Kir2.1 populations. One HCN population owns one intrinsic `m/h`
gate pair and one availability schedule. Its sodium, potassium and calcium
routes share that opening; they do not evolve as three separate channels.
Transfer and dissipated-energy records have explicit `[species, channel_slot]`
axes, while gates retain `[gate, channel_slot]`. Calcium contributes charge
with valence **+2**. The distinct layout and complete nineteen-array checkpoints
retain that ownership through ordinary runs, windows and independent worlds.
Older model versions retain their existing schemas and array shapes.

The implementation follows the isolated laws in
[pinned BETSE's HCN source](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_funny.py)
and its [gate update](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/channelsabc.py).
With membrane voltage `V` in volts, activation is
`m_inf = 1 / (1 + exp((V - midpoint) / slope))`:

| Source feature | Cells correspondence | Check or scope boundary |
| --- | --- | --- |
| HCN1 | `betse_hcn1_m@1`: midpoint −94 mV, slope 8.1 mV, activation time constant 30 ms | Native and independent Decimal gate parameters; no voltage shift |
| HCN2 | `betse_hcn2_m@1`: effective midpoint −89 mV, slope 6.2 mV, activation time constant 184 ms | Includes the source's −10-mV input shift |
| HCN4 | `betse_hcn4_m@1`: effective midpoint −90 mV, slope 9.6 mV, activation time constant 461 ms | Includes the source's −10-mV input shift |
| Shared opening | `m¹ h⁰ = m`; unused `h` relaxes to 1 with a 1-ms time constant | Blocking transport leaves both intrinsic gate states evolving |
| Relative permeability | Na:K:Ca = **0.2:1:0.05**, multiplied by the population's maximum permeability, abundance, opening and availability | Strict named species and valences; separate material/heat records; no extra chloride route |
| Native gate clock | Semi-implicit update with millisecond time units | Captured unchanged in the separate BETSE environment; distinct from Cells' continuous RK4 tissue solver |
| Ionic current | Concentration-dependent GHK for each ion, summed using its valence | The source's nominal −45-mV reversal attribute does not replace this calculation |
| cAMP and temperature dependence | Not included in this family | No ligand modulation, temperature fit or physiological pacemaking claim |

These coefficients and ratios are source-model correspondence, not new fits
to experimental measurements. At BETSE commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, the inspected `vg_funny.py`
SHA-256 is `254f2176e0b86906ae445fdd297750ad0b68cc9bd22da11d05437e6f9824cde7`;
`channelsabc.py` is
`ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4`.
Native code is invoked only by the validation capture; ordinary Cells runs
do not import BETSE.

The [GPU example](../configs/resolved_hcn_cluster.json) has ten populations
on two cells and four membrane patches. The calcium pools and compatible
fixed background charge are manufactured inputs. Calcium moves through the
HCN routes; its other passive routes are zero in this panel. This finite-ion
model does **not** compose HCN with owned ER/calcium/IP3 chemistry,
CaV, plasma calcium transport or assembly regulation. The separate
[`resolved_calcium@4` composition](#shared-hcn-populations-with-owned-calcium-and-assembly)
adds those owners and has its own qualification requirements.

```sh
PYTHONPATH=src /mnt/workspaces/Cells/venv-gpu/bin/python -m cells run \
  configs/resolved_hcn_cluster.json \
  --output /mnt/workspaces/Cells/resolved-hcn-example-01
```

The [qualification protocol](../validation/tissue/surface_hcn_protocol.json)
separates 61 native voltage samples per family and native gate-clock traces
from 200-ms analytic gate-only clamps and four coupled **2-ms** tissue cases.
The tissue comparisons use independent field roots, Decimal rates and adaptive
integration, with clamped/release refinement at 2.5/1.25/0.625 us. Per-species
conservation and heat checks detect errors that would cancel in total charge
or total energy. Complete restart, heterogeneous-world ownership and CPU/L4
comparisons cover execution and storage. The inherited temperature/voltage
bounds and 2.5-us step cap still apply; longer coupled trajectories need their
own checks. Numerical controls, refinements and repeated process-group fixtures
are not additional biological cases. Results and GPU busy/SM-active readings
belong in [Progress](../PROGRESS.md); this protocol makes no full native BETSE
tissue, experimental or Jupiter scaling claim.

HCN reference trajectories use adaptive relative tolerance **1e-13**,
amount/energy/gate absolute tolerance **1e-16**, and charge absolute tolerance
**5e-32 C**. Clamped and release references are checked against a further
fourfold tightening, with agreement required within **3e-14** for each
non-charge state and **3e-28 C** for charge. This resolves reference error
below the existing refinement floors; the simulator's physical equations,
timestep grids and acceptance thresholds are unchanged. Earlier reference
panels retain their original default settings. Per-timestep inputs, comparison
arrays and field errors are written before refinement assertions, so a failed
comparison retains the values needed to diagnose it.

## Shared HCN populations with owned calcium and assembly

`resolved_calcium@4` composes the `resolved_tissue@5` channel catalog with
the existing cell-owned free cytosol, ER stores, calcium buffers, IP3, CaV1.2,
PMCA and synthetic reversible NCX. HCN's sodium, potassium and calcium routes
all read that same free cytosol. Binding or ER exchange can change an HCN flux
without charging the plasma capacitor; external transport updates the chemical
owner and the matching transfer records together. One population still owns
one intrinsic gate pair and one availability schedule.

The distinct layout retains 34 state fields, with `[species, channel_slot]`
axes for population transfer and heat. Older calcium versions retain their
catalogs and single-ion array layouts. Shared-population blocking stops all
three HCN routes while intrinsic gates continue. Conservation checks retain
species identity, including errors that cancel in total charge or heat.

| Component | Correspondence and interpretation |
| --- | --- |
| HCN1/2/4, NaV1.2, Kv1.5 and Kir2.1 | Reuses the separately checked pinned BETSE laws and HCN permeability ratios in the table above; this composition requires its own trajectory checks |
| Calcium/ER, buffering and IP3 | Reuses independently checked owned-chemistry equations and free-ion accounting; these synthetic inputs are not a measured tissue fit |
| CaV1.2, PMCA and NCX | Retains the existing plasma-calcium equations and maintained energy sources; NCX remains a named synthetic reversible law |
| Assembly | Separate neutral protein pools regulate every channel population owned by their cell, including all HCN routes through one shared availability; this is a one-way coupling hypothesis |

The [ordinary GPU example](../configs/resolved_calcium_hcn_tissue.json) and
[assembly GPU example](../configs/assembly_resolved_calcium_hcn_tissue.json)
use ten populations, two owned cells and four membrane patches. Assembly
reports carry `[world, species, channel]` transfers, ordered species IDs and
relative permeability matrices. Aggregation preserves these axes and rejects
missing or inconsistent route metadata. Complete checkpoints retain every
chemical, electrical, gate and assembly state; independent-world planning
supports the existing one-to-sixteen-GPU execution design.

The [qualification protocol](../validation/tissue/surface_calcium_hcn_protocol.json)
requires four synthetic 2-ms cases, independent initial/evolved rates, baseline
and release timestep refinement, complete restart, heterogeneous worlds and
assembly event reconstruction. Baseline/release reference controls use the
tighter HCN settings above and another fourfold accuracy check. The physical
acceptance tolerances remain those of the earlier calcium composition.
Per-timestep inputs, arrays and field errors are preserved before assertions.
Old-model reductions, reference controls, replay and shared regressions remain
numerical checks rather than additional biological cases.

Results are recorded in [Progress](../PROGRESS.md). This composition retains
the finite closed exterior, 2.5-us step cap and maintained ATP/ADP/Pi sources.
It does not yet establish longer-time physiology, cAMP modulation, protein
energy feedback, experimental calcium/assembly causation, full native BETSE
equivalence or a distributed single tissue across GPUs.

## Complete Kv1 catalog with shared populations and owned calcium

`resolved_tissue@6` and `resolved_calcium@5` add the remaining five Kv1 laws
from the same pinned BETSE source to the existing Kv1.5/Kir2.1/NaV1.2/HCN
catalog. Gates, population availability, species transfer and dissipation
retain the shared-population ownership described above. The calcium model
uses the existing free cytosol/ER owner, and neutral assembly regulates every
population belonging to its cell. Earlier model identities keep their
restricted catalogs; a change of channel law cannot silently continue a
checkpoint.

The correspondence is to
[BETSE 1.5.0 `vg_k.py`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_k.py),
SHA-256 `89412aff6163dfe4ccf61afb82418a788ff8e10fbe2ec8cda24c498316b4842f`.
All six classes have two intrinsic gates, K-only relative permeability 1,
and source time constants in milliseconds. Cells evaluates the corresponding
continuous equations in volts and seconds, using concentration-dependent GHK
transport. The source's nominal reversal attribute is not a fixed reversal
voltage in this calculation.

| Pinned source class | Cells law | Opening and distinguishing kinetics |
| --- | --- | --- |
| `Kv1p1` | `betse_kv1p1_mh2@1` | `m h²`; voltage-dependent sigmoid activation and inactivation time constants |
| `Kv1p2` | `betse_kv1p2_mh@1` | `m h`; its own sigmoid targets and time constants |
| `Kv1p3` | `betse_kv1p3_mh@1` | `m h`; both time constants are affine functions of voltage |
| `Kv1p4` | `betse_kv1p4_mh@1` | `m h`; constant activation/inactivation time constants of 3/119 ms |
| `Kv1p5` | `betse_kv1p5_mh@1` | Existing law retained; independent source capture includes it as a continuity control |
| `Kv1p6` | `betse_kv1p6_mh@1` | `m h`; its own sigmoid targets and time constants |

The [protocol](../validation/tissue/surface_calcium_kv1_protocol.json) executes
the unchanged source classes in the separate BETSE environment. It compares
initialization, targets, time constants, powers and 32 updates at each of three
native clocks across 61 voltages per family. Independent 80-digit Decimal
equations and analytic continuous gate clamps provide separate numerical
checks. Source semi-implicit updates and Cells' coupled RK4 remain distinct.

The [ordinary GPU example](../configs/resolved_calcium_kv1_tissue.json) and
[assembly GPU example](../configs/assembly_resolved_calcium_kv1_tissue.json)
use fifteen populations across two cells and four patches. Full qualification
requires four synthetic 2-ms coupled cases, baseline/release refinement,
independent reference accuracy, complete replay, heterogeneous worlds and
CPU/L4 agreement. World-routing controls change a Kv1 gate power alongside
the existing HCN and species/law changes. Source samples, old-model reductions,
clamps and repeated fixtures are numerical controls, not biological cases.
Standalone tissue is checked at initial rates here; the full trajectory panel
exercises the owned-calcium composition. Results and pending checks live only
in [Progress](../PROGRESS.md).

The inherited **−120 to +60 mV**, **298.15 K** and **2.5-us maximum step**
bounds remain. This extends source-model coverage without fitting experimental
tissue measurements. Longer histories, other channel families, dynamic ligand
modulation, finite metabolism, mechanics and multi-GPU execution require their
own work; complete Kv1 source coverage is not full BETSE equivalence.

## Shared calcium-channel populations

`resolved_tissue@7` and `resolved_calcium@6` add CaV1.3, CaV2.1, CaV2.2,
CaV2.3, CaV3.1 and CaV3.3 to the shared population catalog, and make the
existing CaV1.2 law available through that same interface. Multiple calcium
populations can occupy one membrane patch. Each has its own `m/h` gates,
availability and Ca-only route with valence **+2**. The owned-calcium model
uses the same free cytosol as HCN, binding, ER exchange and plasma transport;
no additional calcium inventory is created.

The correspondence is to
[pinned BETSE `vg_ca.py`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_ca.py),
SHA-256 `843d83f969ec53ba9322504f6ef0f699171c3c7c6e2caf03784de5bb17171dd6`.
The native capture executes unchanged classes in the separate BETSE environment.
Cells uses their continuous gate equations with GHK transport, rather than
interpreting their nominal reversal attributes as fixed reversal voltages.
Source milliseconds are converted to seconds; no temperature refit is applied.

| Source class | Cells law | Opening and correspondence boundary |
| --- | --- | --- |
| `Cav1p2` | `betse_cav1p2_m2h@1` | `m² h`; retains the source's −10-mV input shift and the existing dedicated-route kinetics |
| `Cav1p3` | `betse_cav1p3_m2h@1` | `m² h`; unshifted L-type source equations |
| `Cav2p1` | `betse_cav2p1_m@1` | `m`; unused `h` still relaxes to 1 with a 1-ms time constant |
| `Cav2p2` | `betse_cav2p2_m2h_regularized@1` | `m² h`; analytic limit at +20 mV, where the unchanged source produces nonfinite activation values |
| `Cav2p3` | `betse_cav2p3_mh@1` | `m h`; source activation/inactivation rate equations |
| `Cav3p1` | `betse_cav3p1_mh_source_branch@1` | `m h`; retains the literal source branch at **−0.01 mV**, including its time-constant discontinuity |
| `Cav3p3` | `betse_cav3p3_mh@1` | `m h`; source sigmoid activation and exponential inactivation time constants |

Two source details have explicit tests. CaV2.2's activation rate has a removable
zero at +20 mV; its limit is **1 ms⁻¹**. Stable Bernoulli evaluation supplies
that limit and finite derivatives. The native nonfinite values and warnings
are retained separately, outside passing finite-source comparisons. CaV3.1
compares its millivolt argument with `-10e-3`, so its threshold is −0.01 mV.
The named source-branch law preserves this instead of silently changing it to
−10 mV. Neither choice is a new physiological calibration.

The [ordinary GPU example](../configs/resolved_calcium_cav_tissue.json) and
[assembly GPU example](../configs/assembly_resolved_calcium_cav_tissue.json)
have 22 shared populations. The legacy dedicated CaV1.2 patch routes remain
separate, explicitly configured populations. Adding a shared population never
implicitly copies a dedicated route. A replacement control disables one
dedicated route and represents it once through the shared interface, requiring
the same physical rates and distinct, correct transfer records.

Assembly regulates the new shared calcium populations through their owning
cell's availability, alongside its Na/K/HCN populations. It does not thereby
regulate the separate legacy dedicated CaV1.2 routes. Binding or ER exchange
changes free calcium without instantly charging the plasma capacitor; CaV
transport updates the chemical owner and its divalent charge accounting.
Reports and checkpoints preserve the existing world/species/population axes.

The [qualification protocol](../validation/tissue/surface_calcium_cav_protocol.json)
uses source captures, independent 80-digit Decimal equations, analytic clamps,
four synthetic 2-ms coupled histories, reference-accuracy checks, refinement,
complete restart and assembly reconstruction. Heterogeneous worlds vary CaV
gate power as well as HCN, Kv1 and transported-species identities. CPU/L4
agreement and GPU busy/SM-active measurements are required separately from
successful CPU development checks. [Progress](../PROGRESS.md) records those
results and whether the full qualification has started.

The gate-only refinement probe spans 100 us at 0.625/0.3125/0.15625-us steps,
resolving fast calcium relaxation before rounding in very slow source
inactivation gates dominates the endpoint error. The failed 2-ms development
probe and its Decimal rounding diagnosis remain preserved. Gate error and
refinement limits were not loosened. Full coupled histories use 2 ms and a
1.25/0.625/0.3125-us grid. Arrays and errors are saved before assertions.

These models retain the −120 to +60 mV domain at 298.15 K, with a **1.25-us
maximum ordinary step**. A retained 50-us development trajectory at 2.5 us
exceeded the existing accuracy budget in CaV2.1 activation. Halving the step
resolved that transient without relaxing the tolerance; earlier Kv1/HCN
identities keep their 2.5-us cap. The new two-world work allowance is 4,096
padded steps, and the 2-ms assembly example has 1,600 ticks. These are resource
and numerical choices, not physiological parameters.

They do not include `Ca_L2`, `Ca_L3`, `Cav_G`, `CaLeak`,
dynamic calcium-dependent inactivation, measured tissue fits or longer-time
validation. Static/native-clock CaV3.1 branch checks do not qualify adaptive
event localization in coupled threshold-crossing trajectories. Assembly remains
a one-way hypothesis, and multi-GPU execution requires its own qualification.

## Expanded sodium, potassium and leak catalog

`resolved_tissue@8` makes **35 named channel laws** available in ordinary
resolved tissue. It retains the previous 18 Kv1/Kir/NaV1.2/HCN/CaV laws and
adds the following source-derived populations:

| Component guide | Added laws |
| --- | --- |
| [Sodium catalog](SODIUM_CHANNEL_CATALOG.md) | NaV1.3, NavRat2, NavRat1, NavRat3, NaLeak and persistent NaV1.6 |
| [Potassium catalog](POTASSIUM_CHANNEL_CATALOG.md) | Kv2.1/2.2, Kv3.1/3.2/3.3/3.4, K_Fast and KLeak |
| [Chloride and mixed-cation leaks](LEAK_CHANNEL_CATALOG.md) | ClLeak, CatLeak with Na/K/Ca weights 1/1/0, and CatLeak2 with weights 1/1/1 |

The [CPU example](../configs/resolved_catalog_tissue.json) has 39 populations
on four membrane patches belonging to two cells. Each population has one
availability control, two retained intrinsic gates and an explicit ordered
species/permeability declaration. All its species routes use that shared gate
opening and control, with material, charge and dissipation accumulated once
at their existing owners. Blocking a population stops transport while its
intrinsic gates continue to evolve. Always-open leaks retain their source
auxiliary clocks, and CatLeak's declared calcium route remains exactly zero.

The complete state still has 19 fields; channel transfer and heat retain
species-by-population axes. A distinct model/layout identity protects existing
checkpoints and prevents changing channel law during a continuation. Older
models retain their original catalogs and equations. Shared code zero remains
Kv1.5; inactive padding has a separate mask and zero controls/state.

The domain remains **−120 to +60 mV at 298.15 K**, with the inherited **1.25-us
maximum step** whenever channel populations are present. Source singularities,
regularized limits and unusual constants are documented per component.
In particular, the literal Kv3.3 recovery law can require days of model time
for a twelve-time-constant clamp. Its preservation is source correspondence,
not evidence of realistic physiological recovery.

[Integration checks](../tests/unit/test_surface_catalog.py) compare full
tissue derivatives against an
[independent reference](../validation/tissue/surface_kinetic_reference.py),
including multiple owners, reordered species/populations, controls, padding,
old-model reductions and complete snapshots. An early 50-us trajectory checks
coupled numerical wiring only. Component clamp/recovery checks cover their
declared gate time scales separately. Current results and failed evidence live
in [Progress](../PROGRESS.md).

Longer coupled trajectories, timestep/reference refinement, complete resumed
histories and GPU execution require separate qualification. The owned
calcium/ER and assembly composition is described below; finite fuel, water,
repair and mobile-population models retain their existing catalogs.
GPU-ready array laws and offline world planning do not establish multi-GPU
execution or biological calibration.

### Expanded catalog with owned calcium and assembly

`resolved_calcium@7` composes the 35-law catalog with each cell's existing
chemical cytosol/ER, buffering, IP3-controlled release, PMCA and NCX. Its nested
ionic identity is `resolved_tissue@8`. The
[ordinary CPU example](../configs/resolved_calcium_catalog_tissue.json) and
[assembly example](../configs/assembly_resolved_calcium_catalog_tissue.json)
retain 39 shared populations across two cells and four patches, alongside
separately declared dedicated CaV1.2 routes. These are manufactured inputs;
they do not describe a fitted tissue.

Every shared route reads the current **free cytosolic ion amount** from its
chemical owner. Transport changes that same inventory and the whole-cell
exchange ledger once. Internal binding or ER exchange changes available free
calcium without charging the plasma capacitor. CatLeak2 can transport calcium;
CatLeak's explicit zero-calcium weight remains zero. The separately configured
dedicated CaV1.2 routes have their own controls and ledgers; the shared catalog
does not implicitly create another copy of them.

The state retains **34 fields**, including chemical inventories, reaction
extents, ER and plasma transfer, gates, heat and maintained-source work.
Complete snapshots preserve the new layout identity, and branches cannot
change a channel law or population definition. The prior `resolved_calcium@6`
model retains its restricted catalog. Species-route heat must remain monotone
individually, including when total heat across routes would hide a decrease.

Assembly's existing cell-owner mapping scales all shared populations belonging
to that cell, using one availability per population across its species routes.
Gate clocks continue while conductance is blocked. Dedicated calcium channels
keep their separately scheduled controls. This remains one-way coupling from
protein assembly to conductance; calcium and fuel do not yet change assembly
rates or protein pools. Reports retain world/species/population axes, calcium
and IP3 owners, and reject missing route metadata. Ordinary and assembly
checkpoints use their complete existing formats.

The [integration tests](../tests/unit/test_surface_calcium_catalog.py) check
full derivatives, binding/ER redistribution, owner-local assembly control,
conservation, strict domains and checkpoint restoration. The existing
[independent calcium reference](../validation/tissue/surface_calcium_reference.py)
already composes the expanded ionic equations; its new isolated checks consume
frozen JSON inputs without production imports. Initial stages and an early
50-us coupled trajectory establish scoped wiring and numerical consistency.
They do not establish slow-gate or ER relaxation, stochastic assembly histories,
long coupled stability, GPU agreement or measured biology. Those qualifications
remain separate, with results recorded in [Progress](../PROGRESS.md).

The inherited **298.15 K**, **−120 to +60 mV**, **1.25-us maximum step**,
finite exterior and **1e-9-pJ energy tolerance** remain unchanged. ATP/ADP/Pi
are maintained parameters in this model. The
[standalone finite-pool adapter](FINITE_CALCIUM_PUMPS.md) reconciles calcium-pump
and Na/K-pool standard states explicitly; its composition into this model
remains separate work.

## Fixed-geometry injury and prescribed resealing

`resolved_repair@1` composes the shared CaV/Na/K/HCN catalog and owned
cytosol/ER chemistry with a dimensionless damage fraction `D` on each membrane
patch. Stable membrane IDs bind the model parameters and intervention schedules.
For held injury and resealing controls `u` and `v` in `[0, 1]`, its named law
`prescribed_patch_injury_resealing@1` is

```text
dD/dt = a u (1 - D) - k v D
injury permeability[species, patch] = P_max[species, patch] D[patch]
```

`a` and `k` have units s⁻¹, `P_max` has units m/s, and `0 <= D <= 1`.
After the injury pulse, `u = 0` gives exponential resealing; setting `v = 0`
holds the existing damage open. Events change the held rates at exact accepted
boundaries. They never reset damage, ion amounts, voltage, stores or intrinsic
channel gates. An injury pulse has a finite duration; an instantaneous cut or
damage jump is outside this model.

The first injury route admits the explicitly identified monovalent Na/K pair.
It uses the same outward-positive GHK flux as the shared channel populations,
with separate `[species, membrane_slot]` transfer and heat ledgers. Transport
reads the owned free cytosol and finite exterior, updates the chemical owner,
and changes capacitor charge once. Ordinary channel or passive-membrane
availability controls do not silently close an injury route. Chloride, calcium
and other wound permeabilities are rejected in this version.

The complete state adds `damage`, cumulative `damage_opened` and `damage_closed`,
`injury_transferred`, and `injury_dissipated_energy_pJ`. The damage balance is
`D - D_initial = opened - closed`. Inactive patch padding remains zero;
invalid damage, route ledgers or trial states reject without clipping. Existing
material, charge, energy and chemical-ownership checks include injury transport.
This model does **not** assign energetic or material costs to structural
resealing. Its transport energy balance is not a metabolic repair model.

The [example](../configs/resolved_repair_tissue.json) selects the GPU backend
through the ordinary runner. Pure JAX state updates, checkpoint arrays and
independent-world planning use the existing execution stack; actual CPU/GPU
and multiple-GPU qualification status is recorded in [Progress](../PROGRESS.md).
Earlier model identities and their array layouts are preserved.

The [assembly-integrated example](../configs/assembly_resolved_repair_tissue.json)
combines this component with independent cell-owned protein pools. The cluster
clock splits ionic steps at the union of scheduled external interventions and
stochastic assembly events. An interval ending at a change uses the preceding
controls; the new controls and assembly state drive the following interval,
including when both change simultaneously. Channel, pump and calcium controls
use the same scheduling path. Constant-input definitions retain their original
execution path and clock identity.

Assembly still regulates only its declared channel availability. Injury and
closure remain externally prescribed; no assembly-driven membrane repair is
assumed. Complete checkpoints retain damage, ion transfer and assembly state;
cluster reports and ensemble reductions retain membrane/species ownership for
the injury ledgers. Coupled observations and checkpoints stay on nominal ionic
ticks, while off-grid interventions split internal steps exactly. The saved
physical time selects the resumed controls without a separate schedule cursor.
These changes use the existing JAX execution and independent-world planner;
their validation status is tracked separately from the ordinary injury runner.

The numerical panel uses uninjured, sham, held-injury and resealing controls
on the same event grid, analytic damage evolution, and an independently
assembled scalar-ion/full-node-field DOP853 reference. The new model limits
steps to **0.625 us**, `step * (a + k) <= 0.015`, and the declared combined
transport-loss bound. A retained development failure and refinement diagnosis
motivate this finer grid for the closure integral; previous model limits and
acceptance tolerances remain unchanged. The 20–50-us checks and their fast
injury/closure rates are manufactured numerical probes, not measured tissue
repair times or independent biological cases.
The integrated checks additionally reconstruct the assembly event history for
the independent ion/field reference at all five registered observation times
and compare complete restart, changed execution windows and partitioned-world
states.

The [CPU/L4 qualification protocol](../validation/tissue/surface_repair_protocol.json)
adds complete **39-field, 50-us** histories for all four controls, with physical
readouts and accepted times. Held and resealing controls refine at
**0.625 / 0.3125 / 0.15625 us**; their independent references must remain stable
under fourfold tighter ODE tolerances. Complete arrays and signed errors are
saved before comparisons. Disk/fresh-process restart, terminal continuation,
changed windows, heterogeneous injury controls, reversed world order and
independent checkpoint times exercise the ordinary execution paths. CPU/L4
checks retain distinct amount/energy, charge, current and voltage tolerances,
and exact external controls and discrete event state. The assembled model also
compares complete sampled states across backends. Current results belong in
[Progress](../PROGRESS.md).

Use the existing qualification launcher with
`--component-protocol validation/tissue/surface_repair_protocol.json`.
Related tests run in fresh, serial process groups with the established live
memory guards, frozen inputs, durable failures and GPU busy/SM-active samplers.
The completed CaV panel is a prerequisite; this composition receives fresh
CPU and L4 checks rather than inheriting a qualification from its components.

This is an independently specified phenomenological component, not a runnable
copy of BETSE's old wound-channel fragment. The
[source review and later cutting/regrowth work](ROADMAP.md#injury-and-repair)
remain distinct. Declining damage alone does not establish restoration of
physiological function, sustained recovery, regeneration or BETSE cutting parity.

The [longer ordinary-tissue panel](../validation/tissue/surface_repair_recovery_protocol.json)
extends the same four controls to **2 ms**, keeping the physical parameters and
state-error budgets unchanged. Its [GPU example](../configs/resolved_repair_recovery_tissue.json)
uses 83 observations, at most 25 us apart, including both injury boundaries.
Run it with the same launcher and
`--component-protocol validation/tissue/surface_repair_recovery_protocol.json`.
The finest grid and two-world batch declare 8 GiB of conservative array working
storage; the measured process-tree and host-memory guards remain separate.

The reusable [sampled recovery observer](../src/cells/assays/recovery.py) compares
every physical patch voltage and free cytosol/exterior ion concentration with
the independently integrated, time-matched uninjured trajectory. This panel
declares engineering bands of **10 uV** for voltage and **1e-6 mM** for free
concentrations, with numerical uncertainty margins of **0.1 uV / 1e-8 mM**.
They are deliberately explicit analysis settings, not fitted healthy-tissue
ranges. Independent readout errors must remain below **0.01 uV / 1e-9 mM**,
alongside the original complete-state and conservation checks.

A sampled return requires a resolved disturbance followed by a simultaneous
final **0.5-ms hold** inside all bands, after the injury pulse. Quiet controls,
brief reentry, threshold ambiguity and incomplete recovery remain separate
outcomes. The observer rejects excessive observation gaps and does not infer
what happens between samples. Baseline drift is reported. Decreasing damage
alone cannot satisfy the functional criterion, and numerical qualification
does not require any injured arm to recover. The `resolved-repair-recovery-functional.json`
report retains every arm and per-metric result, compared with the independent
reference classification. Longer assembly coupling, autonomous repair and
biological validation remain separate work; current results stay in
[Progress](../PROGRESS.md).

The [2-ms assembly-composition panel](../validation/tissue/assembly_repair_recovery_protocol.json)
and [GPU example](../configs/assembly_resolved_repair_recovery_tissue.json)
extend the same injury controls with the existing cell-owned protein pools.
Each control uses two keyed worlds. Its 85 complete coupled snapshots remain
on nominal ionic ticks, including **5 / 5.625 us** and **15 / 15.625 us** around
the physical injury boundaries at **5.3 / 15.3 us**. Internal integration still
splits at the exact interventions and protein events. The recovery observer
accepts events between observations but begins eligibility at the first sample
at or after the event; an unobserved interval after release earns no hold time.
Existing cases with events on the observation grid retain their interpretation.

Independent scalar reconstruction supplies each world's protein event history
to the electrical/chemical reference. Injury and resealing are compared with
the **matching uninjured world and assembly path**, using the same engineering
bands and hold duration as the ordinary panel. The controls must preserve the
one-way protein trajectories; they are numerical controls, not independent
biological replications. Reference checks cover every observed ionic state,
free concentration, membrane voltage and integrated channel availability in
both worlds, with tighter-reference and three-timestep checks for held injury
and resealing. CPU/L4 comparisons include the physical readouts and complete
protein, pending-event, ionic and clock state.

Complete 1-ms checkpoint continuation with changed execution windows and
separately executed worlds must reproduce every subsequent sampled state and
the final state byte-for-byte. Inputs and snapshots are retained before checks,
including partial observations and the last callback state if execution fails.
This panel saves complete state at declared observations, not every internal
substep. Launch through the existing runner with
`--component-protocol validation/tissue/assembly_repair_recovery_protocol.json`.
Assembly still controls only shared channel availability; structural repair
costs, autonomous closure, changing topology and experimental validation remain
outside this composition. Current status and results belong in
[Progress](../PROGRESS.md).

## Lateral membrane redistribution

The independent component
[`cells.numerics.membrane_redistribution`](../src/cells/numerics/membrane_redistribution.py)
implements `fixed_surface_conservative_drift_diffusion@1`: movement of
membrane-bound populations between patches of the **same cell**, on a fixed
surface graph. The ordinary `resolved_redistribution@1` composition now connects
neutral always-open channel populations to local ionic transport. The
[`resolved_redistribution@2` extension](../src/cells/models/surface_mobile_pump.py)
adds neutral mobile Na/K ATPase populations, as specified below. Voltage-gated
populations remain separate work. Scheduled availability and physical movement
remain distinct; current qualification evidence is recorded in
[Progress](../PROGRESS.md).

Each population owns a nonnegative amount `N[k, patch]` in fmol. Patch area is
in square micrometres, diffusivity `D` in square micrometres per second, edge
width and distance in micrometres, supplied tangential potential `phi` in volts,
and temperature in kelvin. Effective charge `z` controls drift. These are
continuous amounts of membrane-bound material, separate from free ions and the
assembly simulator's discrete pools; no conversion or exchange is implicit.

For an oriented edge from patch `i` to patch `j`, the flux is

```text
x = z F (phi[j] - phi[i]) / (R T)
g = D * edge_width / edge_distance
B(x) = x / expm1(x), with B(0) = 1
J = g * (B(x) * N[i]/area[i] - B(-x) * N[j]/area[j])
dN[i]/dt -= J; dN[j]/dt += J
```

The component uses the existing stable Bernoulli function and ordered edge
accumulation. The same flux leaves one patch and enters the other; population
totals remain separate for every cell. Neutral diffusion equilibrates **density**,
not amount on unequal patches. With a fixed imposed potential, detailed balance
gives density proportional to `exp(-z F phi/(R T))`. The bounded numerical domain
requires `abs(x) <= 50` on active edges. Zero diffusivity, isolated patches,
empty populations and zero inactive padding are supported; cross-cell edges,
duplicate edges, invalid geometry and negative material are rejected.

`rates` supplies instantaneous derivatives, oriented fluxes, outgoing rate
coefficients and per-cell conservation residuals. `explicit_step` is a small
first-order primitive that retains nonnegative material only when
`dt * total_outgoing_rate <= 1` at every patch and population. It counts all
outgoing edges at a branch. Oversized steps are rejected without clipping;
its transfer ledger uses the same flux as the update. This is not a replacement
for the tissue integrator or a promise that an unchanged timestep is accurate.

The [component checks](../tests/unit/test_membrane_redistribution.py) use
independent 80-digit scalar equations, exact two-patch relaxation, step refinement,
Boltzmann equilibrium, field/edge reversal, gauge shifts, patch subdivision,
branched-graph positivity, per-cell conservation and passive free-energy decay
under an imposed field. NumPy, CPU JIT and reordered independent-world batches
are compared. Split continuation tests only this isolated deterministic state;
it is not a complete tissue checkpoint test. GPU and coupled qualification
results must be recorded separately in [Progress](../PROGRESS.md).

**Source correspondence and integration boundary.** The pinned BETSE
[`MoveChannel`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/physics/move_channels.py)
updates dimensionless radial membrane weights relative to a centre value and
calls `sim_toolbox.single_cell_div_free`. That helper is absent from the pinned
module; the unmodified two-patch update probe fails with `AttributeError`.
The [retained source probe](/mnt/workspaces/Cells/membrane-redistribution-development-20261024-01/native-source-probe.json)
records inputs, loaded source and hashes. This conservative surface-edge law is
independently specified and has not established native BETSE trajectory parity.
No upstream code or missing helper was substituted into that probe.

The [ordinary composition](../src/cells/models/surface_redistribution.py) adds
three complete state fields to the resolved passive tissue model:
`surface_amount_increment[population, patch]`,
`surface_transferred[population, surface_edge]`, and
`surface_dissipated_energy_pJ[population, surface_edge]`. Initial amounts,
population IDs, reference densities/permeabilities and edge geometry are bound
in the serialized definition and checkpoint layout. Material never crosses
between cells or enters the free-ion inventory. At **every RK4 stage**, the
current local amount determines permeability:

```text
density[k, m] = N[k, m] / area_um2[m]
P_effective[s, m] = P_background[s, m]
                  + sum_k P_reference[s, k] * density[k, m] / density_reference[k]
```

The ordinary membrane control scales the combined permeability. Closing it
blocks ion flow without immobilizing or destroying the surface population.
Background permeability remains separate from population contributions, and the
same stage's permeability enters the resolved field/current calculation.
The ionic material, capacitor, reservoir, electrode and work ledgers are retained.
Neutral diffusion adds an independent ideal-mixing free-energy check, with
`mu[k,m] = RT log(density[k,m]/density_reference[k])` and edge dissipation
`1e-3 * J * (mu_sender - mu_receiver)` pJ/s. Fixed geometry and neutral cargo
make this separate from electrical charge/work; no hidden active-energy source
is introduced.

For finite chemical potentials, this composition requires a population to be
strictly positive on every patch of a cell where it is present, or wholly absent
on that cell. It rejects partially empty preparations; it does not floor the
logarithm. The standalone transport operator still supports partially empty
patches. The ordinary RK4 grid must satisfy both the existing ionic step bound
and `dt * max(total_outgoing_surface_rate) <= 0.05`. This conservative step
guard does not replace trajectory comparison and refinement. Material residuals
are checked per patch and per cell at `2e-12` fmol; the separate surface-energy
residual is bounded by `2e-10` pJ. Existing ionic tolerances are unchanged.

The [coupled checks](../tests/unit/test_surface_redistribution.py) compare
mobile, immobile, uniform-density, blocked-ion-flow and empty populations.
The [independent reference](../validation/tissue/surface_redistribution_reference.py)
uses separately written diffusion/abundance equations, the established full-node
and Decimal ionic reference, and adaptive DOP853 integration. Synthetic diffusion
rates are accelerated to make coupling visible in a short test; they are not
measurements or a fitted biological timescale. Ordinary saved state, observation,
window and independent-world paths use the registered model contract. See
[Progress](../PROGRESS.md) for the completed CPU/L4 qualification and its bounded scope.
The [GPU example](../configs/resolved_redistribution_tissue.json) and
[qualification protocol](../validation/tissue/surface_redistribution_protocol.json)
use the existing `validation/assembly/qualify_cell.py launch` runner with
`--component-protocol validation/tissue/surface_redistribution_protocol.json`.
That protocol captures both GPU-busy and SM-active counters; the small correctness
panel is not a warmed throughput benchmark.

### Mobile Na/K ATPase populations

`resolved_redistribution@2` retains the neutral leak populations and adds separately
owned pump populations on the same fixed surface graph. A pump-only definition
may omit leak populations. Each pump has an ID, positive reference density,
initial amount in fmol on each patch, diffusivity in um²/s, turnover in 1/s, named
sodium/potassium roles and explicit maintained ATP/ADP/phosphate reservoirs. The
existing `nak_atp_mass_action_positive@1` law transports **three Na outward and
two K inward per forward cycle**, with signed reverse cycles allowed inside its
declared thermodynamic domain. It is the existing reversible ATPase law, not a
new biological parameter fit.

At every RK4 stage,

```text
capacity[k, patch] = turnover_per_s[k] * current_pump_amount_fmol[k, patch]
cycles[k, patch] = capacity * availability * saturation * thermodynamic_factor
```

Capacity is in fmol cycles/s: patch area is **not multiplied again**. It enters
surface density and lateral diffusion. Reference density defines the mixing
chemical potential and does not set pump capacity. Pump turnover does not consume
pump protein. Per-population, per-patch availability schedules have their own
integration boundaries; inhibiting pumping leaves lateral motion intact. These
controls also remain independent of the passive membrane availability.

Six additional state fields bring the complete model to **21**: pump surface
amount increments, lateral transfer and mixing dissipation; signed pump cycles,
pump dissipation and metabolic work. The cycle ledger supplies stoichiometric
ion transfer to the existing cell/exterior/reservoir balances. Total ion movement
determines capacitor derivatives, electrode current and boundary work. Pump
material is neutral and does not enter the free-ion charge inventory. The
unchanged ionic/electric energy balance includes pump dissipation and subtracts
signed ATP-reservoir input; neutral pump diffusion has its own mixing-energy
balance. Forward and reverse pumping must dissipate nonnegative energy. ATP/ADP/Pi
are maintained chemical reservoirs, **not finite metabolic pools**; signed work
and cycles expose their use without claiming ATP synthesis machinery or whole-cell
energetic closure.

The positive-or-wholly-absent preparation rule and 0.05 outgoing-loss step bound
apply independently to both leak and pump populations. Existing material, charge,
field and energy tolerances are retained, with separate pump material/mixing
checks and a `3e-12`-pJ metabolic-work identity check. Observations include current
pump amount/density/capacity, cycle rate, thermodynamic driving energy, availability
and all six extra state fields. Saved state, branches, windows and independent
worlds use the ordinary registered model interfaces.

The [checks](../tests/unit/test_surface_mobile_pump.py) and
[independent reference](../validation/tissue/surface_mobile_pump_reference.py)
combine the established Decimal ATPase oracle with separately accumulated ion
owners, neutral diffusion, a full-node electrical solve and segmented DOP853.
Controls distinguish mobile, immobile, inhibited, empty, zero-turnover, reverse,
scheduled-release, pump-only and uniform-density preparations. Two-cell open/closed
stages exercise distinct capacitor components and a population absent from one
cell. Five complete trajectories, timestep/reference refinement, restart/window
replay and independent clocks test the synthetic composition. CPU/L4 results and
failed attempts belong in [Progress](../PROGRESS.md); the
[protocol](../validation/tissue/surface_mobile_pump_protocol.json) also records
GPU-busy and SM-active. The [GPU example](../configs/resolved_mobile_pump_tissue.json)
uses accelerated synthetic rates for qualification. This extension does not resolve
the missing native BETSE redistribution helper or establish biological diffusion
rates. Calcium, injury and assembly coupling are not yet included.

### Mobile channels carrying joint gating states

`resolved_redistribution@3` adds neutral mobile **Kv1.5** populations to the pump
and leak composition. Each population owns four conformation amounts on every
patch: `m0h0`, `m0h1`, `m1h0` and `m1h1`. Only the last conducts. Transporting
averaged activation and inactivation gates would lose correlations when channels
from different patches mix: two populations can have identical average gates but
different open fractions. The model therefore transports every conformation
separately, without resetting gates or refactorizing the arriving distribution.

The existing `betse_kv1p5_mh@1` law supplies `m_inf`, `h_inf` and their time
constants at the current stage's membrane voltage. Its domain remains **298.15 K**
and **−0.120 to +0.060 V**. Each gate's forward/reverse rates are
`alpha = target/tau` and `beta = (1-target)/tau`. Four transitions connect the
joint states: `m0h0 <-> m1h0`, `m0h1 <-> m1h1`, `m0h0 <-> m0h1` and
`m1h0 <-> m1h1`. Their signed flows are `alpha*N_source - beta*N_destination`.
The m/h marginals obey the existing gate law; the joint state also retains
correlations introduced by transport or the initial preparation.

At every RK4 stage, potassium permeability includes

```text
P_channel[K, patch] = sum_population (
    P_reference * N_m1h1 / area_um2 / density_reference * channel_availability
)
P_total = P_passive_and_leaks * membrane_availability + P_channel
```

Channel, passive-membrane and pump controls are independent. Blocking channel
conduction leaves gate transitions and lateral diffusion active. An explicitly
declared `gate_mode: frozen` disables transitions for diagnostic controls; it
does not immobilize the population. All conformations share the population's
neutral diffusivity. The actual combined, controlled permeability is exposed as
`effective_membrane_permeability_m_per_s`. Gate targets and time constants are
law values; amounts, fluxes and work identify physical support, and those material
quantities remain zero in absent populations and padding.

Six new fields bring the complete state to **27**: conformation amount increments,
lateral transfers and lateral dissipation; gate-transition transfers, gate
dissipation and signed gate-rate-bias work. The latter two provide an explicit
**phenomenological accounting identity**, not a calibration of physical gating
heat or gating-charge work. For each transition,

```text
D_gate = 1e-3 * R*T * J * log(alpha*N_source / (beta*N_destination))
W_bias = 1e-3 * R*T * J * log(alpha/beta)
delta F_ideal_mixture + D_lateral + D_gate - W_bias = 0
```

The dissipation and work above are integrated into separate pJ ledgers. The
ideal-mixture functional sums all four conformation densities. Rate bias is a
declared external source representing the phenomenological gate law; it is not
ATP consumption, experimentally measured heat or an autonomous molecular energy
model. Ionic/capacitor/electrode and ATP-reservoir balances remain separate.
Channel material is neutral and does not contribute bound gating charge.

Every conformation must be positive on every patch of a cell where its population
is present, or the entire population must be absent on that cell. There are no
logarithm floors or state clipping. The conservative RK4 step guard includes both
lateral outgoing rates and a bound on gate-transition exit rates, with the same
0.05 maximum loss coefficient. It does not guarantee trajectory accuracy: the
synthetic example uses **6.25 µs** after refinement showed that 12.5 µs exceeded
the unchanged mixing-dissipation comparison budget. Local conformation and
per-cell total-material checks retain `2e-12` fmol tolerance; the separate
mixture/rate-bias energy identity retains `2e-10` pJ.

The [checks](../tests/unit/test_surface_mobile_channel.py) use an independently
assembled four-state generator and matrix exponential, the existing 80-digit
Kv1.5 scalar reference, and an
[independent full-tissue reference](../validation/tissue/surface_mobile_channel_reference.py).
They distinguish correlated versus factorized populations, mobile versus fixed
proteins, blocked conduction, frozen-gate conformation counterflow and scheduled
release. Analytic diffusion, three-step refinement, saved/fresh-process replay,
branches, windows and independent worlds test the complete model. The
[GPU example](../configs/resolved_mobile_channel_tissue.json) and
[CPU/L4 protocol](../validation/tissue/surface_mobile_channel_protocol.json)
use accelerated synthetic diffusion over 0.4 ms. Qualification results and
retained failures belong in [Progress](../PROGRESS.md).

**Source correspondence:** the immobile factorized gate dynamics reduce to the
existing BETSE-derived Kv1.5 law. Joint-state transport and its rate-bias accounting
are separately specified Cells extensions. The missing pinned BETSE redistribution
helper remains unresolved, so no native moving-channel trajectory equivalence is
claimed. A calcium/injury composition is specified below. Other mobile channel
families, assembly composition, charged-cargo field work, synthesis/degradation,
active trafficking, membrane fluid flow, changing geometry and experimental rate
calibration remain open.

### Mobile Kv1.5 with owned calcium and prescribed repair

`resolved_repair@2` composes the four-state mobile Kv1.5 populations above with
the existing `resolved_repair@1` finite cytosol/ER and injury model. Its
[GPU example](../configs/resolved_mobile_repair_tissue.json) has two cells, four
membrane patches and five finite exterior regions. It retains buffering, ER/IP3
chemistry, PMCA/NCX transport, dedicated calcium-channel routes and representative
fixed HCN2/CaV2.1 populations. This composition moves **Kv1.5 only**; the separately
implemented mobile leak and ATPase models are not implicitly included.

At every RK4 stage, the resolved membrane voltage drives both mobile Kv1.5
transitions and the existing voltage-dependent calcium routes. Each patch's
current conducting `m1h1` amount sets an additional K permeability:

```text
P_mobile[population, patch] = P_reference * N_m1h1 / area_um2
                              / density_reference * mobile_channel_availability
```

The resulting GHK potassium flow updates the existing free-cytosol owner and
finite extracellular inventory exactly once. It contributes to the same
capacitor voltage, ionic current and physical energy balance as the other
transport routes. The next stage therefore sees their coupled response. Neutral
channel-protein movement remains separate from this transmembrane ion flow.

Eight additional fields bring the complete state from 39 to **47**: the six
joint-conformation transport/transition fields above, plus per-population
`mobile_channel_transferred` and `mobile_channel_dissipated_energy_pJ`. The last
two retain conducted potassium and its ionic dissipation separately from protein
motion. Conservation checks combine them with the existing membrane ledgers;
that accounting projection never supplies an extra flux to the equations.
Phenomenological gate-rate-bias work remains separate from physical ionic,
capacitor and ATP accounting.

`mobile_channel_controls` have their own population/patch schedules. Blocking
conduction leaves lateral motion and gate transitions active. Injury/resealing,
fixed-channel and mobile-channel controls all enter the exact shared event grid,
including boundaries occurring between regular steps. Injury changes the
voltage seen by channels; it does not directly prescribe their gate state. Damage
and resealing rates are still externally specified, with no autonomous damage
sensor, selected repair action, geometry change or resolved structural cost.

The definition retains the Kv1.5 temperature/voltage domain and strict positive
joint amounts on present cells, with whole-cell absence allowed. The step guard
includes the existing calcium/repair bounds, lateral/gate exit rates and an
additional ion-loss bound allowing all conserved channel protein on a cell to
accumulate on any one of its patches. The example uses **0.625 µs** over a
synthetic **50 µs** interval. Material checks retain `2e-12` fmol, the separate
surface/gate-mixing identity `2e-10` pJ, and the parent physical energy budget
`1e-9` pJ. Neither fast synthetic diffusion nor this short interval establishes a
physiological repair timescale.

The [independent reference](../validation/tissue/surface_mobile_repair_reference.py)
combines explicitly accumulated transport, Decimal GHK/Kv1.5 laws, scalar
calcium/ER/injury equations and a full-node field solve. The
[checks](../tests/unit/test_surface_mobile_repair.py) cover all 47 derivatives,
padding, absent populations, independent controls and invalid-state rejection;
five complete trajectories; analytic total-protein diffusion and prescribed
damage; three-grid refinement and a separately tightened adaptive reference;
complete restart/branch/windows; and reordered independent worlds. The
[CPU/L4 protocol](../validation/tissue/surface_mobile_repair_protocol.json) gives
each trajectory a fresh process. Comparison workers verify inputs and bind
saved-array hashes, avoiding simultaneous retention of compiled graphs. Each GPU
group receives a copied view of its corresponding CPU group's references, with
shared files supplying other inputs. This preserves the matching input report
and arrays when different groups reuse a filename. `cpu-inputs.json` records
the selected sources and hashes; the runner checks originals and copies before
and after use and retains the binding in its completion evidence. Exact input
comparisons remain in force. The
4-GiB allowance applies both to the process tree's charged resident memory and
to each process's observed RSS high-water mark; the 8-GiB host reserve and both
GPU-utilization measurements remain in force. This protocol explicitly sets
`resources.process_tree_memory_metric` to `pss`: shared resident pages are
apportioned among processes, avoiding double charging the inherited address
space of a CUDA compiler child. Raw summed RSS remains in every resource log.
The guard also charges explicit hugetlb pages, falls back to RSS when a live
process's PSS cannot be read, and records those fallbacks. These are sampled
limits, not kernel allocation caps or an atomic snapshot of the process tree.
[Linux process-memory accounting](https://docs.kernel.org/filesystems/proc.html)
Other protocols default to their existing summed-RSS guard. Recovery can retain
authenticated completed groups while changing only this registered accounting
method; its report distinguishes old RSS groups from new PSS groups. Numerical
allowances, scientific inputs, tests and tolerances must match the parent.

This protocol sets `resources.persistent_compilation_cache`
to `false` for its CPU/L4 qualification workers: they compile fresh instead of
loading serialized executables from disk. In-process JIT remains enabled, and
the runner checks and records the effective cache setting in each backend's
runtime report. Other protocols and production jobs retain their own cache
policies. This protocol also registers the exact XLA slow-compilation notice
format: the runner retains and counts those blocks in authenticated logs, while
other diagnostics and all failed checks still stop qualification. XLA deliberately
uses error-level logging for these timing notices to make them visible; they do
not themselves indicate a failed computation.
[XLA alarm implementation](https://github.com/openxla/xla/blob/main/xla/service/slow_operation_alarm.cc)

For exact GPU replay, the component runner accepts
`resources.gpu_execution_policy: "deterministic"`, registered by this protocol. This sets
`XLA_FLAGS="--xla_gpu_exclude_nondeterministic_ops=true --xla_gpu_autotune_level=0"`
in GPU workers and their child processes. It replaces ambient GPU flags,
initializes the requested GPU before testing, and records the flags and device
platform in the runtime report. CPU workers retain their existing environment.
XLA documents variability both in timed kernel selection during compilation and
in the execution order of some GPU operations. These flags request deterministic
lowering and disable live autotuning; they can affect compilation and throughput.
[OpenXLA GPU determinism](https://openxla.org/xla/determinism)

Replay qualification remains specific to the frozen source, software, device
and execution policy. Checkpoints already bind `XLA_FLAGS`; changing this policy
does not authorize cross-runtime checkpoint migration. Exact window/restart
checks and all physical tolerances remain unchanged. The window worker saves
all 47 actual histories before assertions and binds their archive hash in its
passing report. A policy change requires a fresh qualification: the existing
resource-stop recovery rule cannot relabel evidence from a different GPU policy.
Other protocols opt in separately. Larger-run throughput under this policy
remains to be measured.

Results and retained failures belong in [Progress](../PROGRESS.md).

**Source correspondence:** the constituent gate and transport laws reuse their
existing source comparisons. Joint-state motion, its bookkeeping and this
mobile-channel/calcium/injury composition are separately specified Cells work.
They do not establish native BETSE moving-protein trajectory equivalence,
autonomous anatomical repair, wetlab agreement or the Forms transmission assays.
Assembly integration is described below; other mobile channel families remain extensions.

### Mobile pumps with owned calcium and prescribed repair

`resolved_repair@3` adds neutral mobile Na/K ATPase populations to the complete
`resolved_repair@2` model. The [GPU example](../configs/resolved_mobile_pump_repair_tissue.json)
uses the ordinary configuration, runner, checkpoint and independent-world APIs.
Each population has an explicitly owned amount on every patch of its cell, a
turnover rate, maintained ATP/ADP/Pi concentrations and its own intervention
schedule. A population may be absent on an entire cell. The same conservative
surface diffusion law moves pump proteins; pump cycles do not consume them.

At each integration stage, local cycle capacity is the **current pump amount
times turnover per second**, without applying patch area a second time. The
existing signed `nak_atp_mass_action_positive@1` law reads free cytosolic sodium,
exterior potassium and the shared resolved voltage. Positive cycles move three
sodium ions out and two potassium ions in. Reverse cycles reverse those transfers
and may return work to the declared chemical reservoirs. The added ion flux
updates the existing chemical cytosol owner and capacitor charge once.

Six new checkpoint arrays bring the full state to **53 fields**: pump-protein
amount increments, surface transfer and mixing dissipation, plus pump cycles,
ionic dissipation and signed metabolic work. Pump populations retain separate
ledgers from immobile ATPases, channels and calcium transporters. Calcium balance
validation accepts the additional outward ion transfer, dissipation and reservoir
work explicitly; it does not encode pump work as negative passive dissipation.
Local material, per-cell protein totals, chemical ownership, charge, physical
energy and each population's metabolic-work identity remain checked.

Pump controls affect cycling while leaving neutral diffusion active. They have
independent exact event boundaries alongside channel controls and prescribed
injury/resealing. Observations expose current amount, density, surface flux,
cycle capacity, affinity, signed metabolic power and availability. Invalid
inventory, padding, control, ledger or ensemble-readout states reject without
clipping. The inherited **0.625-us step ceiling** and calcium/channel/injury
checks remain; the pump surface diffusion bound is checked separately.

The [qualification protocol](../validation/tissue/surface_mobile_pump_repair_protocol.json)
compares all 53 derivatives with independent Decimal ATPase/GHK/gate calculations
and scalar calcium/ER ownership, including reordered species and reverse pumping.
Four complete synthetic 50-us trajectories cover mobile, immobile, reversed and
independently scheduled pumps. Analytic protein diffusion, prescribed damage,
three-grid refinement, tightened adaptive references, complete fresh-process
restart, future pump reactivation, changed windows, reordered worlds and CPU/L4
agreement supply separate checks. [Progress](../PROGRESS.md) records their status.

This version retains finite closed extracellular compartments, fixed geometry,
neutral protein cargo and maintained chemical reservoirs. It does not add finite
ATP supply, structural repair costs, protein exchange or autonomous recovery.
The assembly-cluster integration below adds separate pump reports and its own
qualification. Native BETSE redistribution correspondence and remote Jupiter
execution remain separate work.

### Assembly with mobile channels and prescribed repair

The assembly-cluster runner accepts `resolved_repair@2` through the
[mobile-channel example](../configs/assembly_resolved_mobile_repair_tissue.json).
Each cell's existing `root_component_has_cycle@1` coupling supplies an availability
factor. A fixed channel uses its membrane's cell owner; each mobile population
uses the owner of its current membrane patch. Effective conduction availability
is the product of the external schedule and this cell-owned assembly factor.
Padded slots remain inactive. Assembly does not directly change gate states,
lateral protein motion, damage, pumps or the separately controlled dedicated
calcium routes; voltage and chemistry continue to couple these processes through
their existing equations.

Assembly trimers and membrane-channel proteins retain separate inventories.
There is no exchange between these pools. Reports preserve mobile population,
joint-gate, transition, surface-edge, patch and cell identities; they include
absolute channel amounts and all eight added mobile state arrays. Aggregation
checks shapes, ownership, finite values, dissipation and each cell's conserved
mobile inventory before summing independent worlds. All 47 ionic state arrays
and complete assembly, pending-event, exposure and clock state remain in snapshots.
External changes and stochastic assembly events split the inner integration
steps; requested observations stay on nominal ionic ticks.

The [qualification protocol](../validation/tissue/assembly_mobile_repair_protocol.json)
specifies 50-us coupled, scheduled-release and uncoupled controls, each with two
keyed worlds. Independently reconstructed assembly histories drive the scalar
calcium/mobile-channel reference. It checks complete trajectories, tightened
references, compiled timestep refinement, unchanged assembly/damage in the
uncoupled control, fresh-process/window replay, reversed one-world partitions and
CPU/L4 agreement. Current results and failures belong in [Progress](../PROGRESS.md).
Assembly checkpoints now record `XLA_FLAGS` and `JAX_DISABLE_JIT` as part of their
runtime identity, so an execution-policy change cannot silently cross a restart.
The GPU qualification uses the deterministic policy described above.

This remains a one-way assembly/conduction hypothesis with synthetic rates,
phenomenological gate work and prescribed resealing. Protein exchange, finite
metabolic support, autonomous repair and experimental validation require further
models and evidence. Independent-world planning supports up to sixteen GPUs;
remote execution and a tissue distributed across devices require separate checks.

### Assembly with mobile pumps, channels and prescribed repair

The assembly-cluster runner also accepts `resolved_repair@3`, illustrated by the
[GPU example](../configs/assembly_resolved_mobile_pump_repair_tissue.json). The
existing cell-owned assembly factor still controls fixed and mobile channel
conduction. Mobile Na/K pumps retain their own schedules and use the shared ion
concentrations and voltage. Assembly can therefore affect pump cycling through
these physical variables without directly changing pump availability or protein
amount. Assembly pools, membrane channels and membrane pumps remain separate
material inventories.

Snapshots retain all **53 ionic fields** alongside complete assembly, pending
events, availability exposure and clocks. Pump reports preserve population,
species, patch, cell and surface-edge identities, initial and current protein
amounts, signed cycle counts, 3Na/2K ion transfers, dissipation and maintained
reservoir work. Aggregation checks material and ion-transfer identities and the
signed work-per-cycle relation before summing independent worlds. Reverse cycles
and returned reservoir work retain their signs.

The [qualification protocol](../validation/tissue/assembly_mobile_pump_repair_protocol.json)
extends the coupled, scheduled-release and uncoupled controls to the complete
pump composition. Independent assembly histories drive a scalar reference with
Decimal ATPase/GHK/gate calculations. Checks cover forward and reverse pump
stages, unchanged direct pump controls, all-field trajectories, tightened
references, compiled timestep refinement, CPU/L4 agreement, fresh-process/window
replay and reversed one-world partitions. The uncoupled comparison checks that
assembly events, prescribed damage and neutral pump protein motion stay identical
while channel currents, voltage and pump cycling respond. Results and retained
failures are recorded in [Progress](../PROGRESS.md).

This remains a synthetic, fixed-geometry composition with maintained ATP/ADP/Pi
reservoirs and prescribed injury/resealing. Finite metabolism, protein exchange,
feedback into assembly and autonomous repair require further models and evidence.
One-to-sixteen-GPU planning is distinct from qualified remote execution.

### Osmotic water and compliant volumes

The [GPU example](../configs/resolved_water_tissue.json) selects
`resolved_water@1`, a closed finite-compartment extension of the passive
`resolved_tissue@1` model. Water crosses each declared cell/exterior membrane
according to its area, hydraulic permeability and independently scheduled
availability. Osmotic pressure uses the current mobile-ion amounts plus explicit
impermeant osmolyte amounts. Fixed-charge equivalents do not specify particle
counts. Each compartment has a reference volume, linear elastic modulus,
constant pressure offset and strict allowed volume bounds.

Water transfer changes the two owners' volumes equally and oppositely. It
transports no ions or charge directly. Every coupled ionic stage uses the current
concentration, `amount / volume`, so swelling or shrinkage feeds back into
electrodiffusion and voltage. Membrane areas, capacitances and topology remain
fixed: this is a compliant-compartment approximation. The
[reference note](WATER_VOLUME_REFERENCE.md) specifies units, signs, pressure,
free energy and the independently implemented equations.

The complete state has **16 fields**: the existing 12 ionic fields plus cell
volume change, exterior volume change, signed membrane water transfer and
water dissipation. Observations include current volumes/concentrations, osmotic
and hydrostatic pressures, water potentials, flows and energy residuals. Material,
charge, local/global volume and combined mixing/elastic/electrical energy checks
remain separate. Invalid intermediate or final trial volumes reject the step
without clipping or changing the previous state. The water-volume relaxation
bound supplements the existing step ceiling; independent coupled refinement is
still needed because it is not a bound on the full ionic/water Jacobian.

Ordinary execution supports snapshots, future control branches, bounded windows
and independent ionic ensembles. The
[qualification protocol](../validation/tissue/surface_water_protocol.json) covers
coupled swelling, sealed water, water-only dilution, shrinkage and independently
scheduled release; complete CPU/L4 comparisons; tightened adaptive references;
three compiled timestep grids; complete fresh-process replay; reordered worlds;
and offline planning for 1–16 GPUs. [Progress](../PROGRESS.md) owns results and
pending checks. Outputs belong under `/mnt/workspaces/Cells`.

Pinned BETSE computes osmotic pressure and a water-velocity quantity, but its
volume and dilution updates are commented out. Its separately checked pressure
and zero-hydrostatic-pressure flow snapshots provide source correspondence;
they do not provide an evolving-volume trajectory reference. Kinetic channels,
pumps, calcium/ER, injury and assembly are not yet composed with this model.
Shape mechanics, extracellular fluid fields, solvent drag and experimental
calibration also require further work.

### Active transport with compliant volumes

The [active-water example](../configs/resolved_water_kinetic_tissue.json) selects
`resolved_water@2`. It composes the existing `resolved_tissue@7` channel catalog,
maintained Na/K ATPases and kinetic junction gates with the same finite water
owners and compliant-volume law. Each stage supplies current concentrations to
the passive routes, channels and pumps. Water, baseline ionic, shared-channel,
pump-cycle and metabolic-work records remain separate. The complete state has
**23 fields**. Unscaled channel laws retain **298.15 K** and their existing
**1.25-us** maximum RK4 step; the water relaxation bound also applies.
The channel-family step ceiling applies whenever channel populations are
present, including blocked populations whose gates still evolve. An empty
channel list has no channel-gate ceiling; ionic, junction, pump, water and
other applicable bounds and strict stage-domain checks remain in force.

The example includes Kv1.5, HCN4 and CaV1.2 populations. Calcium is an ordinary
mobile ion here; this family does not provide owned ER stores, calcium buffers
or dedicated plasma/ER calcium transport. Membrane, junction, channel, pump and
water controls retain separate schedules on one accepted event grid. Sealing
water recovers the active ionic model; removing channels and pumps recovers the
passive-water model. Definitions, full snapshots, future branches, windows and
independent-world plans use the ordinary execution stack.

The [qualification protocol](../validation/tissue/surface_water_kinetic_protocol.json)
specifies six synthetic 50-us trajectories: coupled transport, sealed water,
passive-water reduction, inhibited pumps, reversed pumping and independent
release schedules. Multi-cell stages also include shared exterior owners,
junctions and extracellular faces. Independent equations, complete CPU/L4
histories, tightened adaptive references, three-grid refinement and exact replay
have separate checks; [Progress](../PROGRESS.md) owns their execution status.
Implementing the wider channel catalog does not qualify every catalog law in
this coupled regime.

ATP/ADP/Pi are maintained chemical support inputs, not finite volume-owned
metabolites. They supply the recorded ATP work and are not silently added to
the osmotic particle inventory. Only declared mobile ions and finite impermeant
osmolytes contribute to this water law. A finite-energy model must declare its
material, energy, charge and osmotic ownership before replacing these inputs.
Existing phenomenological channel gates also have no newly assigned energetic
store. Geometry, capacitance and topology remain fixed; autonomous adaptation,
assembly coupling and experimental calibration require further work.

### Finite cellular energy with compliant volumes

The [combined example](../configs/resolved_energy_water_tissue.json) selects
`resolved_energy_water@1`. It composes the finite ATP/ADP/phosphate model with
water exchange and the active ionic/channel layer. Every stage uses current
amounts and volumes for ion transport, Na/K pumping, regeneration and osmotic
pressure. Membrane, junction, channel, pump, regeneration and water schedules
remain independent. The complete state has **28 fields**.

The required declaration `energy_osmotic_coupling: neutral_ideal_atp_adp_pi@1`
makes the extra assumption explicit: each transformed ATP, ADP and phosphate
particle contributes ideal osmotic pressure, without adding ionic charge.
These particles are separate from the declared background impermeant inventory.
This is an approximation with buffered pH/Mg/solvent, not explicit metabolite
speciation or measured cell energetics. Hydrolysis increases their combined
particle count; regeneration decreases it. Water changes concentrations without
directly moving solute or charge. Areas and capacitances remain fixed.

The finite pool already owns its mixing free energy. Its signed volume-work
ledger integrates `-0.001 R T N_pool/V * dV/dt` in pJ/s. This is an internal
transfer between pool mixing and volume relaxation. The pool identity includes
this transfer; the combined ionic/capacitor/pool/elastic energy identity includes
water heat and external regeneration work, with no second volume-work input.
In particular, endpoint dilution energy cannot replace the integrated ledger
when reactions change the particle count. The
[reference note](WATER_VOLUME_REFERENCE.md) derives the accounting and the
conserved-inventory bound `N_pool < 2 ATP_initial + ADP_initial + Pi_initial`.

Closed ions, adenylate, phosphorus and water retain their separate conservation
checks and existing tolerances. Invalid volumes or exhausted substrates reject
every trial, including when pumps, supply or water controls are disabled. Sealed
water recovers the complete fixed-volume finite-energy model. Independent
equations exercise changing volumes and particles, shared owners, full
trajectories and refinement. Snapshot/replay, world placement and CPU/L4
qualification are separate execution checks; [Progress](../PROGRESS.md) records
what has actually passed. Neither this model nor its manufactured regeneration
port establishes whole-BETSE equivalence, respiration or biological calibration.

### Cotransport with finite energy and water

The [combined cotransport example](../configs/resolved_cotransport_water_tissue.json)
selects `resolved_cotransport_water@1`. Manufactured electroneutral KCC/NKCC
routes act on the same ionic amounts that determine osmotic pressure, channel
currents and Na/K pump demand. Current volumes enter every concentration
calculation. Cotransport has no direct ATP reaction or transported current;
its ionic redistribution can change subsequent pumping, voltage and water flow.
The [cotransport guide](TISSUE_COTRANSPORT.md) retains its kinetic assumptions
and distinguishes these laws from the pinned BETSE generic transporter.

The complete state has **31 fields**, adding signed cotransport cycles,
per-species transfers and heat to the 28-field water/finite-energy state. Each
stage uses one shared ionic/field/pool calculation. Incoming cotransport amounts
are scattered once to their membrane owners, and heat enters the combined
energy balance once. Finite pool volume work retains its internal-transfer
meaning. Seven independent control families share the full accepted event
grid; reducing a model for a numerical check must not discard another
component's event boundaries.

Blocking or omitting cotransport recovers the complete water/finite-energy
model; sealing water recovers fixed-volume cotransport. Compact/padded stages,
renamed roles, shared pump owners, complete snapshots, accounting corruption
and a short feedback trajectory have CPU checks. Their evidence and limits
belong in [Progress](../PROGRESS.md). These checks establish component and
initial integration behavior. Coupled settling, long-time stability, full
restart trajectories and GPU execution require appropriately long comparisons,
refinement and complete state evidence before those claims are made.

The [CPU response protocol](../validation/tissue/surface_cotransport_water_response_protocol.json)
extends this check to six matched, channel-free, half-second trajectories.
Fuel supply, cotransport and water availability vary one family at a time;
recovery/release occurs at 0.25 seconds. Rates and inventories are unchanged
from the manufactured fixture. Each interval spans about nine initial
enabled-water relaxation times. Actual late rates are recorded, because elapsed
time alone does not establish equilibrium. The independent reference segments
all seven clocks and keeps all 31 fields; refinement uses explicit physical
observables, alongside full-state accuracy and complete saved-history restart.
This panel does not qualify channel recovery, physiological parameter values
or GPU execution. Its result belongs in Progress.

### Shared finite energy with owned calcium and assembly

The [finite-calcium example](../configs/resolved_calcium_energy_tissue.json)
selects `resolved_calcium_energy@1`, combining the 35-law shared catalog and
owned calcium/ER chemistry with one ATP/ADP/Pi pool per cell. The
[assembly example](../configs/assembly_resolved_calcium_energy_tissue.json)
adds the existing one-way assembly/channel control. Protein pools remain
separate; this does not assign ATP costs to protein assembly.

All Na/K, PMCA and ER pump routes refer explicitly to their own cytosol's
`energy_pool`. Each stage gathers its current substrates, computes each pump
rate once, and scatters the signed Na/K + PMCA + ER cycles into that pool once.
Hydrolysis consumes ATP and makes ADP + Pi; reverse cycles synthesize ATP.
NCX exchanges ions without a direct ATP reaction. Multiple patches and supply
ports may share an owner, but different cells do not share fuel implicitly.
ATP/ADP/Pi cannot also be declared as chemical species in this composition.

The [finite calcium adapter](FINITE_CALCIUM_PUMPS.md) preserves the named
positive-domain source equations and explicitly converts the pool's canonical
1-M standard energy for the calcium laws' numeric-mM quotient:
`delta_g0_mM = delta_g0_M - R*T*ln(1000)`. A shared pool therefore supplies the
same hydrolysis free energy to all three pump families. This is a new model
identity, not an assertion that different old maintained-reservoir declarations
describe the same fuel. The ER law still moves **one Ca per formal ATP cycle**;
it is not a two-Ca SERCA/proton model.

The complete state has **38 fields**. The existing three pump-work histories
remain internal transfer diagnostics. The combined energy balance includes
ionic/chemical, plasma/ER capacitor and finite-pool free energy, all transport
and regeneration heat, and external regeneration supply once. The former
constant-drive-times-cycles checks are replaced by the integrated owner-local
identity `pool free-energy change + pump work + regeneration heat - supply = 0`.
The total energy tolerance remains **1e-9 pJ**; finite-pool material tolerance
is **2e-12 fmol**. Adenylate and phosphorus remain conserved independently in
every owner. Geometry/volumes are fixed and the pools are neutral transformed
species with buffered pH/Mg/solvent; no mitochondrial metabolism is implied.

The full control clock includes regeneration-only boundaries. Strict positive
pool, calcium, affinity and padding checks apply even to blocked pumps. To
retain a conservative calcium timestep bound as fuel changes, let `A` and `P`
be the owner's conserved adenylate and phosphorus concentrations. Forward ATP
saturation is bounded by `A/(Km_ATP + A)` and the reverse coefficient by
`ADP*Pi/(Km_ATP + ATP) <= A*P/Km_ATP`. An auxiliary maintained-law parameter
set attains these upper coefficients for the existing calcium/chemistry loss
bound; it is not a realizable pool state. The initial gross-turnover bound and
all existing gate ceilings also apply. Exhaustion rejects a trial; it is never
clipped or repaired into a passing trajectory.

Independent references check full stages, owner routing, reversal, work and
supply. CPU trajectory, checkpoint and offline world-routing evidence is in
[Progress](../PROGRESS.md). A 50-us coupled check establishes early interaction
and a supply-control boundary; it cannot establish depletion, recovery, slow
channel relaxation, native whole-BETSE correspondence or GPU qualification.
The component's longer clamped-fuel tests remain separate evidence. Coupling
this model to water, mobile repair routes and mitochondrial chemistry remains
future work.

### Extended 39-law channel catalog

Four further pinned calcium laws join the shared population catalog:
`Ca_L2`, `Ca_L3`, regularized `Cav_G` and `CaLeak`. The
[component guide](CALCIUM_CHANNEL_EXTRAS.md) records their equations, native
clocks, source failures and independent temporal checks. Each new population
transports only calcium with relative permeability one, through the same
electrochemical transport and owner ledgers as the existing catalog.

| Composition | New identity / example | Complete state fields |
| --- | --- | ---: |
| Ionic tissue | [`resolved_tissue@9`](../configs/resolved_catalog_v2_ionic.json) | 19 |
| Owned calcium, ER and IP3 | [`resolved_calcium@8`](../configs/resolved_catalog_v2_calcium.json) | 34 |
| Shared finite Na/K, PMCA and ER fuel | [`resolved_calcium_energy@2`](../configs/resolved_catalog_v2_energy.json) | 38 |

The preceding `@8`, `@7` and `@1` identities, respectively, retain their
35-law catalogs and reject these four added laws. Codes 0–34 retain their
meanings; codes 35–38 select the new calcium laws. Tissue padding still uses
an inactive slot with code zero. Distinct layouts preserve this choice through
compiled execution and snapshots; a model-version change is not a restart.

Ca_L3 retains its native −15-mV shift. Cav_G uses the analytic activation-rate
limit **0.209/ms** at −27 mV, without shifting the input voltage or claiming
the native singular calculation succeeds. CaLeak remains always open before
availability is applied, while its auxiliary gates relax on **one-second**
clocks. Blocking or zero permeability stops transfer and leaves those clocks
running. Invalid gates and absent species routes remain checked while blocked.

In the owned models, transport reads current **free cytosolic calcium** and
updates that chemical owner exactly once. Channel transport does not directly
consume ATP; its concentration changes can affect subsequent pump demand.
The existing dedicated CaV routes, ER and finite-fuel accounting keep their
meaning. No new calcium store, ligand law, gating energy or temperature fit
is introduced.

Both the [calcium assembly](../configs/assembly_catalog_v2_calcium.json) and
[finite-fuel assembly](../configs/assembly_catalog_v2_energy.json) examples
apply cell-owned assembly controls to the shared channels. Separate protein
pools and regeneration controls remain explicit. Reports and complete
checkpoints retain calcium, channel and fuel ownership.

[Progress](../PROGRESS.md) links the full-stage CPU/reference checks,
two-world compiled checks, short coupled trajectory and offline 1/4/16-GPU
plans. Gate-component clamps cover their own relaxation time scales; the
50-us coupled trajectory checks early feedback and separate channel/supply
boundaries. Longer coupled relaxation, stochastic assembly histories, GPU
performance and experimental calibration require separate evidence.

### Calcium-sensitive potassium with the shared catalog

The [legacy calcium-sensitive potassium component](CALCIUM_ACTIVATED_POTASSIUM.md)
now composes with the 39 shared channel laws. It evaluates the pinned
`cagPotassium` equation from each patch owner's **current free cytosolic Ca
concentration** and the same-stage membrane voltage. It transfers K+, with
relative permeability one. Calcium is sensed without being consumed; channel
transport has no direct ATP demand. Existing calcium pumps can respond to the
resulting electrical and concentration changes through their usual coupling.

| Composition | Identity / example | Complete state fields |
| --- | --- | ---: |
| Ionic tissue | [`resolved_tissue@10`](../configs/resolved_calcium_activated_ionic.json) | 19 |
| Owned calcium, ER and IP3 | [`resolved_calcium@9`](../configs/resolved_calcium_activated_calcium.json) | 34 |
| Owned calcium and shared finite fuel | [`resolved_calcium_energy@3`](../configs/resolved_calcium_activated_energy.json) | 38 |

The new law has **no gate state or relaxation clock**. Its declaration uses
`initial_gate: []`. The common packed arrays reserve two zero entries for this
population; both entries and their derivatives remain exactly zero. Nonzero
values are rejected even when the channel is blocked. Target/tau readouts use
zero to mark absent gates, never an instruction to integrate a zero-time
relaxation law. Instantaneous-only populations add no gate timestep ceiling;
the other physical transport and reaction step bounds still apply.

The law requires a declared Ca species with valence +2 and uses the owner's
free-ion amount divided by its volume. Bound calcium, ER calcium, total calcium
and outside calcium are not direct sensor inputs. The complete ionic model
still requires positive free-ion concentrations for its chemical potentials,
although the standalone scalar opening also defines a zero-calcium limit.
Mixed-catalog temperature remains 298.15 K; the native numeric-mM concentration
scale remains explicit in the law name. No additional calcium, gating-energy
or fuel inventory is introduced.

Code 39 identifies this law in the new models. The previous @9/@8/@2 models
retain their 39-law catalogs and reject it. These equations are a composition
of a **legacy source function**, for which no active pinned call site was
found, with Cells' conservative transport. They are not a fitted BK/SK channel
or proof of complete native BETSE tissue behavior.

The [calcium assembly](../configs/assembly_calcium_activated_calcium.json) and
[finite-fuel assembly](../configs/assembly_calcium_activated_energy.json)
examples retain cell-owned channel controls, separate protein pools, reports
and complete checkpoints. [Progress](../PROGRESS.md) records CPU comparisons
and offline independent-world planning through 16 GPUs. Short coupled checks
test wiring and control boundaries; longer recovery histories and GPU
qualification require separate evidence.

### Morris-Lecar channels with the shared catalog

The [thirteen pinned Morris–Lecar laws](MORRIS_LECAR_CHANNELS.md) extend the
catalog to **53 named laws**, with 60 populations in the examples. Five have
one evolving activation gate; eight calculate their opening directly from the
current membrane voltage. BETSE's chemistry network has an active call path
for this family. Component source correspondence remains distinct from a
complete native tissue comparison.

| Composition | Identity / example | Complete state fields |
| --- | --- | ---: |
| Ionic tissue | [`resolved_tissue@11`](../configs/resolved_morris_lecar_ionic.json) | 19 |
| Owned calcium, ER and IP3 | [`resolved_calcium@10`](../configs/resolved_morris_lecar_calcium.json) | 34 |
| Owned calcium and shared finite fuel | [`resolved_calcium_energy@4`](../configs/resolved_morris_lecar_energy.json) | 38 |

Codes 40–44 declare `initial_gate: [m]`; codes 45–52 declare
`initial_gate: []`. The shared two-row gate array keeps every absent entry
exactly zero, including h for the five dynamic laws and both entries for the
eight instantaneous laws. Complete checkpoints and trial-state validation
enforce this contract even when a population is blocked. The previous model
identities retain their 35-, 39- or 40-law catalogs and state declarations.

Each dynamic law uses its own physical clock, including the 50-fold slower
Kv1p5S rate. Availability and permeability affect transport without stopping
the intrinsic gate clock. Instantaneous opening reads the voltage at each
integration stage; no relaxation state or synthetic time constant is added.
The gate-step bound uses each dynamic ML law's minimum tau over its declared
voltage domain. Instantaneous-only catalogs add no gate-step bound. Older
two-gate populations retain their existing bounds, and all other physical
transport/reaction bounds still apply.

The four Ca laws transfer free calcium through the existing owner. Nav
transfers sodium; the K laws transfer potassium. Each HCN population uses a
single opening/control for its K/Na routes with relative permeabilities
1/.2 and **no calcium route**. Its source target increases with voltage; the
formula is preserved explicitly rather than refitted. These ML gates have no
direct calcium, temperature, ligand or ATP input. The earlier calcium-sensitive
potassium law still reads current owner-local free calcium, and existing
pumps still couple transport to finite fuel. No duplicate calcium or fuel
inventory is introduced.

The [calcium assembly](../configs/assembly_morris_lecar_calcium.json) and
[finite-fuel assembly](../configs/assembly_morris_lecar_energy.json) examples
retain owner-specific controls, reports and full checkpoints. Assembly
regulation remains one-way. [Progress](../PROGRESS.md) records the independent
reference, CPU integration and offline 1/4/16-GPU planning evidence.

Component clamps cover twelve effective time constants in each activation
and recovery phase; instantaneous laws receive direct voltage steps. The
separate 50-us coupled check exercises early electrical/calcium/fuel feedback,
dynamic and instantaneous channel controls, a supply-only boundary and exact
complete final-snapshot restoration. That short history does not establish
coupled settling or long-term recovery. Longer coupled histories, stochastic
assembly, GPU execution and experimental calibration remain separate
qualifications. The water and prescribed-repair extensions below each have
their own scope; the joint water/calcium/fuel/repair composition is described
[below](#prescribed-repair-with-owned-calcium-finite-fuel-and-water).

### HCN leak and fixed cAMP variants

The **56-law** catalog adds three pinned BETSE variants to the previous 53
laws. The compositions are `resolved_tissue@12` (19 fields),
`resolved_calcium@11` (34 fields), and `resolved_calcium_energy@5` (38 fields).
The latter two retain owned calcium/ER/IP3 and, for `@5`, shared finite ATP.
All previous identities, including the 53-law water and repair compositions,
retain their declared catalogs. Version-two joint water and water/repair
compositions below add these three variants while preserving their 43- and
48-field owner contracts. Qualification status and evidence belong in
[Progress](../PROGRESS.md).

Examples: [ionic tissue](../configs/resolved_hcn_extra_ionic.json),
[owned calcium](../configs/resolved_hcn_extra_calcium.json),
[shared finite fuel](../configs/resolved_hcn_extra_energy.json),
[calcium with assembly control](../configs/assembly_hcn_extra_calcium.json),
and [finite fuel with assembly control](../configs/assembly_hcn_extra_energy.json).
The full examples contain 63 channel populations across the 56 laws.
They specify 2-ms histories. The scoped coupled CPU qualification uses the
separate 50-us fixture below; the full example horizons need their own runs.

The correspondence is to
[BETSE 1.5.0 `vg_funny.py`](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/channels/vg_funny.py#L291).
Voltages below are effective midpoints after the source input shift; the
activation target is `1 / (1 + exp((V - midpoint) / slope))`.
The [source protocol](../validation/channels/hcn_extra_protocol.json),
[independent equations](../validation/channels/hcn_extra_reference.py) and
[native capture](../validation/betse/hcn_extra_native.py) preserve initialization,
native backward Euler and continuous relaxation as separate contracts.

| Native class / Cells law | Initialization / update midpoint | Slope / activation time constant | Relative Na/K/Ca permeability | Cells state |
| --- | --- | --- | --- | --- |
| `HCNLeak` / `betse_hcn_leak_open@1` | Opening always 1 | No physical gate clock | .33 / 1 / .05 | `initial_gate: []` |
| `HCN2_cAMP` / `betse_hcn2_camp_m@1` | −79 / −79 mV | 6.2 mV / 184 ms | .2 / 1 / .05 | `initial_gate: [m, h]` |
| `HCN4_cAMP` / `betse_hcn4_camp_m@1` | **−80 / −76 mV** | 9.6 mV / 461 ms | .2 / 1 / .05 | `initial_gate: [m, h]` |

The cAMP variants retain the source's unused h gate, with target 1 and a
1-ms relaxation time; opening depends only on m. HCNLeak's native m/h
bookkeeping has powers zero and does not affect transport. Cells represents
that leak without dynamic gate state and requires both packed slots to remain
exactly zero, including while blocked. This representational difference is
explicit in the comparison with native execution.

HCN4_cAMP initializes using a −20-mV input shift and updates using −24 mV.
The component's `initial_gates` helper preserves the source initialization;
model definitions still provide explicit initial gates. Initial gates must
not silently be replaced by the update target. These are **fixed cAMP-shift
variants**, not dynamic ligand concentrations or binding kinetics.

One opening and availability control drives all three ion routes. Calcium
uses the actual free-cytosol owner in the calcium models. Channel transport
has no direct ATP cost; its effects can change the demand of the existing
finite-fuel pumps. Intrinsic gate clocks continue when transport is blocked.
Component clamps cover twelve activation time constants per phase. Separate
short coupled histories test current-state feedback, controls, conservation
and complete checkpoint restoration; they do not establish slow HCN settling
in a tissue. Native update-clock comparisons, continuous integration, GPU
execution and experimental calibration retain separate evidence scopes.

### Shared channel catalog with compliant water

[`resolved_water@3`](../configs/resolved_morris_lecar_water.json) combines the
53-law channel catalog with conservative water flow and compliant compartment
volumes. Its **23 complete state fields** retain the ionic state and four water
fields: inside/outside volume increments, transferred water and dissipated
water energy. The earlier `resolved_water@1` and `@2` definitions retain their
catalogs and behavior.

Each stage divides current free-ion amounts by **current owner volume** before
evaluating passive transport, channels and the Na/K pump. The calcium-sensitive
potassium law therefore responds to dilution or concentration of its free
calcium sensor. Volume changes do not create an extra calcium inventory. The
Morris–Lecar gates retain their voltage-only input, including one-state and
instantaneous declarations; absent packed gates stay exactly zero.

Water movement conserves total compartment volume. Its osmotic and elastic
free-energy accounting remains separate from, and consistent with, ionic heat
and maintained pump work. ATP/ADP/Pi here are maintained chemical support,
not owned osmolytes. The existing finite-fuel/water model is a separate
composition, now [also available with all 53 laws](#shared-channel-catalog-with-finite-fuel-and-water);
this maintained-support version does not add owned ER, finite fuel or injury.

All actual clocks constrain the timestep. Removing fast two-gate populations
can relax the gate bound, but leaves water, transport and junction bounds in
force. Blocking a dynamic channel does not stop its gate clock. A permanently
zero hydraulic permeability permits no accumulated water transfer or heat on
that route; a time-controlled closure may retain its earlier history.

The [validation fixtures](../validation/tissue/morris_lecar_water_fixtures.py)
exercise multiple cells and outside owners, the full 60-population catalog,
changed volumes, sealed/blocked routes, empty and single-state catalogs,
reordered declarations and separate water/channel/pump control boundaries.
[Progress](../PROGRESS.md) records CPU comparisons, numerical checks and
offline GPU planning. A water-only relaxation over twelve conservative time
constants is separate from the short full-catalog coupling check; neither
establishes long coupled recovery or biological calibration. Interfaces,
capacitances and topology stay fixed. Evolving shape, solvent drag, general
fluid fields and native BETSE evolving-volume correspondence remain outside
this model.

### Shared channel catalog with prescribed repair

[`resolved_repair@4`](../configs/resolved_morris_lecar_repair.json) combines all
53 channel laws with owned free cytosolic calcium, ER/IP3 and the existing
prescribed patch injury/resealing law. Its **39 complete state fields** retain
the 34-field calcium composition plus damage, accumulated opening/closure,
injury ion transfer and injury heat. The earlier repair `@1` and mobile
channel/pump repair `@2`/`@3` definitions keep their previous behavior.

The additional lesion transfers only explicitly declared Na+ and K+ through
the existing cell/outside owners. It uses the same-stage voltage and current
free-ion amounts; calcium stays with its chemical owner. Damage changes the
lesion's permeability, while channel controls and their intrinsic clocks keep
their separate meanings. All zero-, one- and two-state channel declarations,
including exact absent gate entries, remain enforced during injury and closure.

The [assembly example](../configs/assembly_morris_lecar_repair.json) retains
owner-specific channel modulation, injury controls, chemical inventories,
reports and full checkpoints. Its assembly-to-channel regulation remains
one-way. [Progress](../PROGRESS.md) records the independent comparisons and
execution evidence. Separate scalar repair checks cover twelve time constants
of the declared law; short coupled histories check injury/resealing boundaries
and changing channel availability. They do not establish physiological repair
times or long-term restoration of tissue function.

This is fixed-geometry **prescribed resealing**, with maintained pump support.
The model adds no autonomous repair controller, structural repair energy,
shape change, topology change, moving channel populations or water dynamics.
The expanded water and repair models are separate compositions. Native wound
source limitations remain documented; this extension makes no claim to a
working native BETSE wound trajectory or measured biological recovery.

### Shared channel catalog with finite fuel and water

[`resolved_energy@2`](../configs/resolved_morris_lecar_finite_energy.json) adds
the 53-law catalog to the finite cellular ATP/ADP/phosphate model. Its **23
complete state fields** retain ionic amounts, gates, transport and energy
ledgers, finite pool increments, and regeneration cycles, heat and supplied
work. [`resolved_energy_water@2`](../configs/resolved_morris_lecar_finite_water.json)
adds compliant cell/outside volumes, water transfer and heat, and signed pool
volume work, giving **28 complete fields**. Both earlier `@1` identities retain
their previous channel catalog and equations.

Each Na/K pump consumes or regenerates fuel in its explicitly named inside
cell's pool. Distinct cells have distinct pools and supply ports; multiple
membrane patches may share a cell's pool. Channels consume no ATP directly.
Their ionic transport changes the load faced by pumps. Each stage evaluates
the pump, regeneration port and channels with current amounts and, in the
water composition, current volumes. The calcium-sensitive potassium sensor
therefore responds to free-calcium dilution at the same stage as fuel dilution.
This composition owns free ionic calcium but has no ER or bound-calcium store.

The explicit `neutral_ideal_atp_adp_pi@1` convention counts ATP, ADP and phosphate
as transformed neutral osmotic particles. Hydrolysis changes their particle
count while conserving adenylate and phosphorus. Water moves volume rather
than carrying these particles across the membrane. The pool's mixing energy
is counted once. Signed pool volume work is an internal diagnostic; only
declared regeneration supply is external fuel input. Buffered pH, magnesium
and solvent remain assumptions of this transformed model.

Zero-, one- and two-state channel contracts survive both compositions, including
exact absent gate entries. Numerical guards retain actual gate clocks, gross
fuel turnover and water relaxation limits independently. Removing a gate or
blocking a route does not remove the other limits. Full snapshots retain
every pool, water and channel field and the versioned layout.

The [fixtures](../validation/tissue/morris_lecar_energy_water_fixtures.py) cover
60 channel populations, multiple fuel owners, reordered and padded layouts,
blocked routes, inhibited pumps, absent supply, and separate control clocks.
[Progress](../PROGRESS.md) records current CPU and offline placement evidence.
Short coupled histories establish early coupling and accounting; independent
fuel and water relaxation checks are labelled separately. The
[owned-ER/fuel/water composition](#owned-calcium-finite-fuel-and-compliant-water)
is described below, followed by its prescribed-repair extension. Longer coupled
recovery, GPU execution, evolving interfaces and biological parameter calibration
remain separate work.

### Owned calcium and ER with compliant cytosol

[`resolved_calcium_water@1`](../configs/resolved_calcium_water.json) composes
the 53-law channel catalog and owned calcium/ER/IP3 model with conservative
plasma-membrane water movement. Its **38 complete fields** retain the parent
34-field state plus cell/outside volume increments, water transfer and water
heat. The required convention is
`chemical_osmotic_coupling: ideal_all_cytosol_species_fixed_er@1`.

The cell's water volume is its chemical **cytosol** volume. Every stage uses
that same volume for free-ion concentrations, chemical reactions, plasma and
ER transport, and IP3 activation. ER volume stays fixed; there is no ER water
port. Cell volume here therefore does not mean the sum of independently
changing cytosol and organelle volumes. Plasma/ER areas and capacitances,
interfaces and tissue topology stay fixed.

Each declared cytosolic chemical species contributes one ideal osmotic particle
per molecule. Free calcium and free buffer are separate particles; a bound
calcium-buffer complex counts once. The free-ion view used by the electrical
solver adds no duplicate inventory or osmotic particles. Outside compartments
count their owned free ions, and explicitly declared additional inert solutes
are separate. Fixed electrical charge is not itself an osmolyte. Maintained
ATP reservoirs are external chemical support, without an automatically owned
cytosolic ATP/ADP/phosphate pool in this model.

The joint energy balance owns chemical mixing, binding standard energies,
plasma/ER capacitor energy, inert-solute mixing and compliance energy once.
The parent balance at reference volumes receives the exact current-particle
dilution correction, compliance energy and accumulated water heat. Maintained
pump work remains explicit. Binding and IP3 conversions can change particle
counts, so hydraulic timestep bounds use conserved chemical moieties rather
than treating the initial number of particles as a permanent upper bound.
Chemical loss bounds also use the declared minimum volumes.

The [assembly example](../configs/assembly_calcium_water.json) preserves
owner-specific channel control and complete checkpoints. Reports include
current cytosol/outside volumes, fixed ER volume, current free-ion and IP3
concentrations, and chemical particle counts. Assembly regulation remains
one-way. [Progress](../PROGRESS.md) records the independent equations,
directional energy checks, execution evidence and remaining qualifications.
Isolated water relaxation with frozen chemical particles is distinct from
coupled calcium/water histories. Finite cellular fuel joins this model in the
composition below. Injury, organelle water exchange, evolving shape, fluid
mechanics and biological calibration remain further work; this model does not
establish native BETSE volume trajectory correspondence.

### Owned calcium, finite fuel and compliant water

[`resolved_calcium_energy_water@1`](../configs/resolved_calcium_energy_water.json)
combines owned calcium/ER/IP3 chemistry, all 53 channel laws, finite ATP/ADP/Pi
and conservative plasma-membrane water flow. Its **43 complete fields** are
the 38-field finite-calcium state plus cell/outside volume increments, water
transfer and heat, and signed pool-volume work. The earlier model identities
retain their definitions.

`resolved_calcium_energy_water@2` uses the full 56-law catalog, with
`resolved_tissue@12` as its inner ionic identity and the same physical
configuration keys and 43 state fields. Its finite-fuel projection retains the
exact HCN layout, so the three additional laws survive water, volume and fuel
evaluation. The shared CLI, schedules, snapshots, independent-world planning
and assembly interfaces accept this version. Qualification is tracked in
[Progress](../PROGRESS.md); the version-one example above keeps its original scope.

Each cell has one chemical cytosol and one finite fuel pool at the **same current
volume**. At every numerical stage, Na/K, plasma-calcium and ER pumps read that
pool's current concentrations; chemical reactions, channels, exchangers and
IP3 activation use the current cytosol volume. ER volume stays fixed. Interface
areas, capacitances and topology also stay fixed. ATP/ADP/Pi remain transformed
neutral species with buffered pH/Mg/solvent; they cannot also appear as chemical
store species.

Both osmotic choices are explicit in the configuration:
`ideal_all_cytosol_species_fixed_er@1` and `neutral_ideal_atp_adp_pi@1`.
Each distinct cytosolic chemical species counts once, including bound complexes
and IP3 precursor/sink species. Three additional rows count ATP, ADP and Pi.
Exterior free ions and explicitly declared inert solute complete the water law.
The ionic view of cytosolic calcium contributes no second particle inventory.

The joint energy balance owns chemical and fuel mixing, binding standard
energies, plasma/ER capacitor energy, inert-solute mixing and compliance energy
once. Its exact dilution correction uses **current amounts**, retaining the
cross term when chemistry, fuel and volume change together. Pump work is an
internal transfer between the fuel pool and transport; declared regeneration
supplies external energy. The signed `pool_volume_work_pJ` diagnostic records
the pool's volume derivative times water movement. It enters the internal pool
identity and adds no second energy term to the whole system.

Chemical loss bounds use the minimum permitted cytosol/outside volumes and
conserved fuel bounds. The water relaxation bound includes conserved chemical
moieties and each pool's phosphorus-minus-adenylate bound, since hydrolysis can
increase particle count. Every channel, reaction, supply and water event retains
its exact accepted boundary. Exhausted fuel, invalid calcium, absent gate states,
invalid padding and unsupported water/work histories remain rejected even when
routes are blocked.

The [assembly example](../configs/assembly_calcium_energy_water.json) preserves
complete checkpoints and owner-specific channel control. Reports retain current
volumes, chemical and fuel concentrations, total cytosolic solute particles,
fuel particles, pool-volume work and regeneration ledgers. Inert solute is
additional to the reported cytosolic particle count. Assembly regulation remains
one-way; no metabolic assembly cost or protein exchange is implied.

[Progress](../PROGRESS.md) records the independent equations, endpoint-energy
checks, CPU execution and offline placement evidence. Short complete trajectories
and reduced physical-time relaxation tests support different claims. Longer
coupled recovery, stochastic assembly histories,
GPU qualification and experimental calibration remain separate work. This
synthetic composition does not establish native whole-tissue BETSE equivalence.

### Prescribed repair with owned calcium, finite fuel and water

[`resolved_calcium_energy_water_repair@1`](../configs/resolved_calcium_energy_water_repair.json)
extends the joint model above with damage, cumulative opening and closure,
species-resolved lesion transfer and lesion heat: **48 complete state fields**.
Each membrane patch has an explicit `prescribed_patch_injury_resealing@1`
declaration and independent injury/resealing controls. Na/K permeability is
multiplied by its current damage fraction; other lesion species are rejected.

`resolved_calcium_energy_water_repair@2` adds the 56-law parent with the same
48 fields and prescribed damage law. Water, injury and resealing retain separate
control axes, complete snapshots and assembly ownership reports. The new
versions have their own serialized model/layout identities. Cell removal is
currently supported by the separately qualified version-one water-cut model;
the new version-two water and repair models explicitly refuse that operation.

Leak flux uses the current chemical cytosol and exterior concentrations and
the shared membrane voltage. It updates the existing free-ion/chemical owners
and capacitor charge, with a separate outward-positive transfer ledger and
nonnegative dissipated heat. Total material and energy checks fold those
ledgers into the parent accounting once. Observations retain the separate
lesion fields while reporting the total membrane flux and joint energy balance.
Swelling changes leakage concentrations, and changed ion inventories feed the
existing water and pump laws at subsequent stages.

Damage follows the declared opening/closure rates. Structural resealing has
no modelled ATP cost and is not controlled by calcium, ATP or assembly; the
finite fuel pools still supply the existing ion pumps. Closing a lesion does
not reset any ion, chemical, gate, fuel or water state. ER volume, membrane
areas, capacitances and topology remain fixed. This is a synthetic prescribed
injury model, not native BETSE cutting or autonomous biological repair.

The timestep checks retain all channel, chemical, fuel, water and injury
clocks. They also bound injury opening/closure and combined transport losses
at the minimum permitted volumes, with steps no larger than 0.625 us.
Invalid damage histories, negative heat, unsupported lesion routes, depleted
fuel and invalid volumes remain rejected under blocked controls.

The [assembly example](../configs/assembly_calcium_energy_water_repair.json)
keeps one-way channel availability control, full checkpoints, and separate
injury, calcium, fuel and water ownership reports. The
[independent reference](../validation/tissue/calcium_energy_water_repair_reference.py)
compares the complete coupled state; separate scalar damage clocks test actual
opening/resealing durations without claiming full-system recovery.
[Progress](../PROGRESS.md) records development results and outstanding
qualifications. Longer coupled recovery, stochastic assembly histories, GPU
execution, changing topology and experimental validation require further evidence.

### Configured transport with owned calcium and finite fuel

[`resolved_calcium_energy_transport@1`](../configs/resolved_calcium_energy_network_transport.json)
composes the pinned configurable BETSE transporter component with the 56-law
`resolved_calcium_energy@5` model. Its **42 complete fields** include four new
ledgers: signed reaction cycles, outward ion transfer by species and route,
dissipated energy, and signed supplied work. It uses actual free cytosolic ions,
finite extracellular owners and the solved membrane voltage at every stage.
Transported calcium updates the existing chemical owner and its ionic accounting
view once; it does not create a second calcium pool.

This first physically accounted subset requires reversible, species-preserving
transport. Reactant and product species/coefficient maps must match exactly;
conversion reactions and irreversible native configurations are excluded.
Each route binds an explicit membrane, and `ignore ECM` or profile-based targeting
cannot bypass that owner. Native regulator algebra is retained, including the
source's unused regulator-zone and voltage-star requests, but negative regulation
is outside this physical model's domain even when the route is blocked.

The configuration explicitly declares Cells' SI Faraday/gas constants. The frozen
native captures used those constants too; this is not a comparison using BETSE's
rounded factory constants. For this subset, matching substrate lists cancel the
native quotient's per-item standard-concentration factors. If the configured
standard energy is `G0`, supplied work per forward mole must be declared as
`W = -G0`. With outward stoichiometry `nu`, inside-minus-outside voltage `Vm`, and
current free concentrations, the physical transfer energy is
`sum(nu * (R*T*log(c_out/c_in) - z*F*Vm))`. The native reaction energy is that
transfer energy plus `G0`. For a signed cycle rate in fmol/s:

- dissipated power is `-1e-3 * cycle_rate * reaction_energy`, in pJ/s;
- supplied power is `1e-3 * cycle_rate * W`, in pJ/s;
- chemical plus capacitor energy change, heat and supplied work balance once.

The declared driving work represents a maintained external source. It does not
silently consume ATP. Existing Na/K, plasma-calcium and ER pumps retain their
shared finite fuel owner and live ATP feedback. A future ATP-driven configurable
reaction needs an explicit chemical/pool stoichiometry contract.

Route-only event boundaries join the existing channel, pump and fuel clocks.
Parent timestep ceilings and an initial gross-transport turnover check are
retained; every actual trial still checks positive inventories, rate finiteness,
nonnegative dissipation and ledger/padding validity. The initial turnover bound
is not a lifetime stability guarantee. Geometry and ER volume remain fixed.

The [assembly example](../configs/assembly_resolved_calcium_energy_network_transport.json)
retains channel-only assembly modulation and separate transporter metadata and
ledgers in aggregate reports. All 42 fields and flat topology arrays participate
in checkpointing. The [independent reference](../validation/tissue/calcium_energy_network_transport_reference.py)
checks full coupled rates and histories; reduced long-duration transport checks
remain distinct from short coupled trajectories. Current receipts and failures
are recorded only in [Progress](../PROGRESS.md). Offline multi-GPU planning,
compiled CPU evidence, native-source correspondence and experimental calibration
are separate claims; this version does not establish whole-tissue BETSE parity.

### Finite mitochondrial ion and voltage coupling

[`resolved_calcium_energy_mitochondria@1`](../configs/resolved_calcium_energy_mitochondria.json)
extends the configured-transport composition with an explicit mitochondrial
compartment in each cell. Its **45 complete fields** retain the 56-law channel
catalog, calcium/ER chemistry, finite fuel and configured plasma transport.
The three added fields record mitochondrial amount increments, signed internal
ion transfer and dissipated energy, each by species and cell.

This is a continuous passive ion/voltage model. Its source correspondence is the
[separate pinned BETSE component](../src/cells/processes/betse_mitochondria.py),
which retains native copied initialization, cached voltage and ordered Euler
updates. The coupled Cells law instead declares explicit disjoint initial
inventories, SI constants and charge-consistent voltage at each RK stage.
Matching instantaneous fluxes under matched inputs does not establish identity
with the native discrete trajectory. The exact neutral-ion and zero-voltage
limits are evaluated without a voltage perturbation.

The initial mitochondrial inventory is supplied independently; construction
does not copy it from the cytosol or silently withdraw it. The configured cell
volume means cytosolic solvent volume excluding both ER and mitochondria.
Volumes, areas and capacitances are fixed. Positive internal transfer adds to
the mitochondrial owner and subtracts from the actual free cytosolic chemical
owner. Whole-cell external transfer and plasma charge records stay unchanged.
Calcium movement can therefore affect existing PMCA/ER fuel demand, but the
mitochondrial route itself has no ATP reaction.

With mitochondrial-minus-cytosolic voltage `V`, the initial fixed background is
`Q_fixed = C*V0 - F*1e-15*sum(z*n0)`, accompanied by cytosolic countercharge
`-C*V0`. During evolution, `V = V0 + F*1e-15*sum(z*delta_n)/C`; its current
countercharge is equal and opposite. Initial fixed backgrounds and subsequent
charge increments are checked separately to avoid cancelling large ionic
charges when testing a small capacitor residual. The current supported voltage
domain is `abs(V) <= 0.2 V`.

For compatibility with the parent cytosol/ER owner checks, a temporary stage
view subtracts mitochondrial increments from the parent's inventory coordinate
and adds the same charge to its field offset. Their sum remains the actual
whole-cell charge. This view is never saved as a checkpoint or used as an
initial energy anchor; snapshots retain the authoritative state and static
initial layout.

Passive GHK flux uses the actual cytosolic and mitochondrial concentrations.
For positive cytosol-to-mitochondrion transfer, its chemical potential change is
`delta_mu = R*T*log(c_mito/c_cyto) + z*F*V` and heat production is
`-1e-3*flux_fmol_s*delta_mu` in pJ/s. The balance includes mitochondrial chemical
and capacitor energy once, alongside the parent's actual cytosolic energy.
Positive inventories, nonnegative heat, material ledgers and charge ownership
are checked at actual stages, including blocked routes. Conserved-pool step
bounds include the initial mitochondrial inventory.

The [assembly example](../configs/assembly_resolved_calcium_energy_mitochondria.json)
retains channel-only modulation and reports organelle ownership, amounts,
transfer, charge and heat separately. All 45 fields participate in ordinary and
assembly checkpoints. [Independent reference checks](../validation/tissue/calcium_energy_mitochondria_reference.py)
separate a complete 50-us coupled probe from a reduced charged-potassium
relaxation at unchanged diffusivity over twelve time constants. The latter
holds other routes off and does not establish whole-cell settling. These are
synthetic calibration fixtures, not measured mitochondrial parameters.

Current CPU receipts, preserved failures and offline placement checks are in
[Progress](../PROGRESS.md). Respiration, electron transport, ATP synthesis,
dynamic organelle volume, long coupled recovery, stochastic assembly histories,
GPU execution and wetlab calibration remain outside this version's claim.

### Cell removal and absolute-time continuation

`resolved_tissue_excision@1` connects the conservative
[cut/remap component](../agent-work/cells-worker-01/workfiles/BETSE_TISSUE_CUT_HANDOFF.md)
to the twelve-field passive `resolved_tissue@1` solver. The public operation
`cells.core.excision.excise(spec, checkpoint, removed_cell_ids)` removes
named cells, their membranes and incident junctions, then rebuilds the field
operators for the surviving tissue. It supports finite extracellular owners
and maintained baths under the existing field-solvability rules.

Surviving amounts, net charge, fixed background, volumes, membranes and
extracellular faces are retained. Removed material, cell volume, fixed/net
charge and capacitor energy have explicit records. Material is excised from
the system; it is not released into extracellular space. Junctions in this
model are abstract cell-to-cell edges without an explicit pair of contact
faces, so removing them does not create a physical wound surface.

After a cut, the actual surviving amounts and charges become the new reference
state. New local transfer, work and heat ledgers start at zero. The complete
original definition, all twelve state arrays, full static layout and exact
checkpoint clock remain in the source archive, including padding and every
previous cut. Previous transfers are preserved as history, not counted again
as current material. Empty removal is an unchanged checkpoint; removing all
cells produces a terminal archive without invoking a zero-cell field solver.
An incompatible post-cut field is rejected without altering the source state.

The new model starts at the **absolute cut time**, retaining the original
nominal grid and event boundaries. Controls are evaluated on their
right-continuous side before removal. Even a future event targeting only a
removed membrane remains as a no-op clock boundary. Ordinary runs, scalar
windows and independent-world batch windows all start at this declared epoch;
checkpoint step indices remain global. Up to sixteen successive cuts can
retain nested provenance. The serialized definition rejects changed physical
survivors, rewritten control history, missing original event clocks, a changed
nominal timestep or an incomplete source checkpoint.

The event report records the before/after stored energies, removed chemical
and capacitor energies, electrode-charge impulse and held-potential electrical
work. The retained capacitor-energy change uses a stable difference of
squares. The remaining energy jump is a diagnostic in the declared potential
reference. It is **not** assigned to a fitted cutting-work term or claimed to
close a mechanical energy law. Ordinary passive material, charge and energy
checks apply separately to each continuous segment.

Use the CLI with a complete passive snapshot:

```bash
python -m cells excise /mnt/workspaces/Cells/my-run/checkpoint_final \
  --remove cell_1 --output /mnt/workspaces/Cells/my-cut
python -m cells resume /mnt/workspaces/Cells/my-cut/after \
  --output /mnt/workspaces/Cells/my-cut-continuation
```

Repeat `--remove` for multiple cell IDs. The non-overwriting cut archive contains
complete `before/` and, when runnable, `after/` snapshots, `transition.json` and
a checksummed manifest. `load_excision(...)` verifies the inventory and hashes,
recomputes the remap from the saved source and checks the saved continuation.
A terminal cut has no `after/` snapshot.

The [three-cell source example](../configs/resolved_tissue_excision_source.json)
declares a 2.5-ms horizon. Save a checkpoint at 1 ms with `--checkpoint-at 0.001`
to reproduce the qualified nonterminal cut; the run manifest names its
snapshot path. Windowed execution with 4096 steps bounds the conservative
working estimate to about 580 MiB. The scalar example also permits a full
trace; that larger declared storage estimate is distinct from measured runtime
memory. Current independent-world cut cohorts require matching post-cut axes
and the same cut epoch. Offline placement is available for 1/4/16 GPUs; GPU
execution and utilization are not established by that plan.

The independent oracle rebuilds full-node charge/current equations and
integrates every field using event-segmented DOP853. Its manufactured cases
cover open and held boundaries, blocked transport, padding, no-op/full removal,
single survivors, sequential cuts and rejected closed/disconnected layouts.
The three-cell fixture's initial fast electrical mode is about 3 microseconds;
the general 100-microsecond passive timestep ceiling is not an accuracy or
stability guarantee for this geometry. Production qualification uses finer
RK4 steps, with unchanged physical rates, event times and the 2.5-ms horizon.
See [Progress](../PROGRESS.md) for results, exact inputs and retained failures.
These are synthetic numerical comparisons, not independent biological cases.

The original passive API remains available. The family dispatcher above also
accepts the active channel/pump, calcium/ER, finite-fuel, configured-transport and
mitochondrial and compliant-water models described below. Regulation and assembly
still need explicit remapping of their extra owners and clocks. Lysis, healing, growth,
physical contact evolution, mechanical
cutting work, full native BETSE cut trajectories and GPU execution remain
separate work.

### Cell removal with channels and maintained-fuel pumps

`resolved_tissue_active_excision@1` applies the same physical-removal rules to
the 56-law `resolved_tissue@12` family. The generic Python operation and
`cells excise` command accept a complete snapshot from each supported family and write
an explicit family identity in the cut manifest. Other physiological families
are rejected until their additional state owners have a cut adapter.

Surviving channels retain their actual gate values by population and membrane
owner. Surviving junctions retain their intrinsic gate values by edge ID. This
includes zero-, one- and two-state channels and the parent's declared packed
HCN convention. Gates are not reinitialized from the new voltage. The new epoch
uses the original catalog layout class, which selects the channel equations in
the compiled kernel. Removed populations and pumps are listed explicitly;
surviving pump parameters and maintained chemical reservoirs remain unchanged.

All **19 source state fields**, including gates, transport histories, pump
cycles, heat and metabolic work, remain in the complete source checkpoint.
The two gate fields carry forward; the other **17 local ledger fields** start
at zero against the surviving physical amounts and charges. Kept and removed
histories use their own cell, membrane, channel, edge, face and extracellular
axes. Pump chemical support in this family is maintained externally; it is
not a finite cellular ATP inventory.

The field calculation at removal uses both scheduled availability and actual
intrinsic junction gates. Membrane, junction, channel and pump controls retain
their original absolute event boundaries, including events owned only by
removed structures. No-op, terminal and sequential cuts preserve the same
archive rules as passive removal. Source validation rejects changed gates,
pump parameters, owners, past controls, layouts and incomplete histories.

The [active source example](../configs/resolved_active_excision_source.json)
uses the qualified 39.0625-ns timestep. Save a checkpoint at 50 us with
`--checkpoint-at 0.00005`, then use the same `cells excise` and `cells resume`
commands above. The horizon is 150 us; 512-step windows provide bounded
recording. Saved source/after-cut examples and exact validation inputs are
linked from [Progress](../PROGRESS.md).

The independent comparison exercises a 50-us active prefix and continuation
through 150 us, including evolving sodium activation/inactivation and junction
gates. Separate stage/ownership panels exercise all 56 laws. Timestep refinement,
compiled scalar and bounded-world execution, complete checkpoint restoration
and offline GPU placement have separate evidence in [Progress](../PROGRESS.md).
These manufactured histories test transient consistency and gate memory;
they do not establish slow-gate equilibrium, tissue healing, measured recovery
or full native BETSE tissue correspondence. Cut-energy reports retain the
chemical, capacitor and held-electrode diagnostic scope; no gate free-energy
or mechanical cutting-work law is supplied.

### Cell removal with owned calcium and ER stores

`resolved_calcium_excision@1` extends removal to the 34-field
`resolved_calcium@11` family. The same Python operation, CLI and checksummed
before/after archive apply. Current qualification evidence and limitations are
linked from [Progress](../PROGRESS.md).

The authoritative material inventory is the full chemical store in each cell:
free ions, bound complexes, buffers and IP3 in both cytosol and ER. Surviving
stores keep their actual amounts, compartment volumes, reaction parameters
and ER voltage. Removed stores and their chemical and capacitor energies are
recorded explicitly. Moiety totals are projections of those stores; free-ion
concentrations are readouts. Neither is added as a second material inventory.

The ionic solver's concentration anchor becomes the actual free cytosol after
removal. Its plasma-charge anchor retains the whole-cell charge determined by
external transfers. Binding and ER exchange can change free-ion charge without
changing whole-cell charge, so the effective free-ion background is re-expressed
at this boundary. Physical chemical fixed backgrounds are preserved within an
explicit floating-point representation bound; ordinary incremental charge,
ownership and energy tolerances are unchanged.

Three intrinsic gate fields survive exactly: shared channel gates, junction
gates and dedicated calcium-channel gates. The other 31 local state fields
restart at zero against the new physical reference. All 34 original fields,
including every ER, reaction, transfer, heat and work history, remain in the
complete source checkpoint. Histories are remapped using their declared cell,
membrane, channel, junction, extracellular and face owners.

All seven control families retain their absolute clocks: membrane, junction,
shared channel, Na/K pump, store, plasma calcium transport and dedicated calcium
channel controls. Removed-owner events remain clock boundaries. No-op,
terminal and sequential cuts use the same provenance rules as earlier families.

This parent model has finite extracellular owners. Removing a charged cell can
make the retained closed field unsolvable; such a cut is rejected. The adapter
does not neutralize survivors, invent a bath or release removed stores into the
environment. The manufactured qualification fixture removes a neutral cell
whose external transport is explicitly blocked while its internal ER chemistry
and gates remain active. Surviving cells continue their active transport.

The comparison covers a 50-us prefix and continuation through 150 us, with
separate full-catalog ownership/stage panels and timestep refinement. This
tests transient chemical ownership and gate memory, not slow relaxation or
biological repair. Na/K, PMCA and ER pump support remains externally maintained.
The finite-ATP, configured-transport and mitochondrial adapters are described
below, followed by compliant water and regulated finite fuel. Assembly still
needs its own cut adapter.
The event energy jump remains a diagnostic; mechanical cutting work, physical
wound surfaces, lysis, healing, full native tissue parity and GPU execution
are separate qualifications.

The [calcium cut source example](../configs/resolved_calcium_excision_source.json)
uses 39.0625-ns steps. Save the 50-us checkpoint with `--checkpoint-at 0.00005`,
then use the same `cells excise` / `cells resume` commands above. Scalar windows
of 512 steps and two-world windows of 256 steps keep their declared array
budgets bounded. The qualified prefix, scalar continuation and windowed restart
use separate processes with one frozen source tree and checksummed artifacts.

### Cell removal with finite ATP and regeneration

`resolved_calcium_energy_excision@1` extends the same operation to the 38-field
`resolved_calcium_energy@5` family. It preserves surviving cytosol/ER chemistry,
intrinsic gates and actual ATP/ADP/Pi amounts. Each fuel pool keeps its cell owner
and standard chemical energy; regeneration ports survive only with their pool.
The CLI and checksummed before/after archive use the same interface as above.
Qualification results and pending checks are recorded in [Progress](../PROGRESS.md).

These fuel species are neutral transformed pools, separate from the ionic charge
inventory. Adenylate and phosphorus totals are conserved projections of the fuel
amounts, not additional stores. Na/K, PMCA and ER pump work transfers energy
internally between the finite pool and transport processes. Regeneration supply
is external work. The cut report lists removed fuel, its conserved moieties,
free energy, pool identities and regeneration-port identities without counting
pump work a second time as external support.

All **38 source fields** and the complete layout remain archived. The three gate
fields survive; 35 local ledger fields restart against the actual surviving
chemical and fuel inventories. Regeneration adds an eighth absolute control
clock to the seven families above. Removed-port events remain clock boundaries,
and rewriting prior fuel amounts, pump parameters, owners or controls is rejected.
No-op, terminal and sequential cuts retain the same provenance rules.

There is an inherited constructor restriction: a surviving PMCA or ER pump can
only be re-anchored when its live ATP, ADP and Pi concentrations are within
**[1e-9, 1e3] mM**. A valid evolved source may lie outside that interval. Such a
cut is explicitly refused without clipping fuel or changing the source; no-op
and terminal archives remain available. Na/K-only owners do not acquire this
PMCA/ER restriction. Closed-field solvability requirements also remain in force.

The manufactured comparison uses actual pump rates and finite-pool feedback over
a 50-us prefix, neutral removal and continuation through 150 us, with timestep
refinement and separate full-catalog owner panels. These transients test material,
energy, clock and restart consistency; they do not establish physiological fuel
exhaustion or recovery. The cut-energy jump remains a diagnostic. Mechanical
cutting work, combined water/organelle/regulation/assembly cuts, full native tissue
correspondence and GPU execution require separate qualification.

### Cell removal with configured membrane transport

`resolved_calcium_energy_transport_excision@1` applies conservative removal to
`resolved_calcium_energy_transport@1`, including its reversible, species-preserving
configured transporters. A route survives exactly when its membrane survives.
Its kinetic configuration, density, regulator definitions and declared maintained
drive remain unchanged. The rebuilt layout resolves the surviving membrane IDs;
it does not retain stale numerical indices. Qualification status belongs in
[Progress](../PROGRESS.md).

The full **42-field** source checkpoint is archived. The three gate fields survive
and 39 local fields restart against the actual surviving chemical/fuel inventories.
The four configured-route histories—cycle extent, transferred ions, dissipated
energy and supplied work—are archived by route owner. These are histories of
transfers already included in the physical stores, not additional material or
energy inventories. Configured transport's declared maintained work stays external;
finite-ATP pump work remains internal to the cellular pool/transport composition.

Transporter schedules add a ninth absolute control family. Removed-route events
remain clock boundaries, while changed prior schedules, route parameters, owners,
missing histories and nonzero padded entries are rejected. The Python operation,
CLI, checksummed cut archive, scalar/window execution and ensemble registration
use the same contracts as the preceding cut families.

The comparison includes a manufactured electrically neutral KCl route on a
removed cell, so archived work and transferred material can be nonzero without
neutralizing the tissue artificially. The default panel blocks the removed cell's
external transport. Continuous segments retain separate conservation and numerical
checks. The inherited PMCA/ER fuel-anchor range and closed-field solvability limits
still apply. This adapter does not add ATP-driven or species-converting configured
routes, assembly remapping, physical wound surfaces or healing. The separate
mitochondrial and water adapters below retain their additional owners.

### Cell removal with mitochondrial owners

`resolved_calcium_energy_mitochondria_excision@1` extends removal to the complete
45-field calcium/ER/fuel/configured-transport/mitochondrial composition. Surviving
organelles retain their actual ion inventories, voltage, fixed charge, geometry
and diffusivity. All 45 source fields remain archived; three gate fields survive
and 42 local fields restart at the cut's absolute time. Mitochondrial controls add
a tenth control family, including retained clock boundaries from removed owners.
Current qualification and evidence are recorded in [Progress](../PROGRESS.md).

Internal ion movement requires paired charge accounting at a restart. If
`delta_Qm = F*1e-15*sum(z*delta_nm)`, the new chemical reference coordinate shifts
by `+delta_Qm` in cytosol and the mitochondrial initial countercharge shifts by
`-delta_Qm`. Their sum is the physical chemical fixed background and must remain
unchanged within the explicitly reported representation bound. The organelle's
own fixed background, `Cm*Vm - F*1e-15*sum(z*nm)`, is also preserved. Its charge
`Cm*Vm` and matching cytosolic countercharge are internal; neither becomes an
additional whole-cell plasma charge. Ordinary segment conservation and domain
tolerances remain unchanged.

Removed mitochondrial inventories, capacitor/chemical energies and all three
organelle histories are retained in the cut report and complete source archive.
The internal transfer history does not count as additional material. Actual
survivor concentrations and capacitor voltages become the next epoch's anchors;
missing histories, changed owners/parameters and discarded control clocks reject.
The inherited PMCA/ER fuel-anchor range and retained-field solvability limits
still apply. This passive organelle law adds no respiration or ATP synthesis;
combined organelle/regulation/assembly cut compositions, mechanical cutting work, healing and full
native tissue correspondence remain separate work. Water uses the distinct
43-field composition below; water and mitochondrial owners are not combined here.

### Cell removal with compliant water and finite fuel

`resolved_calcium_energy_water_excision@1` connects removal to the existing
43-field `resolved_calcium_energy_water@1` parent and its 53-law channel catalog.
It archives all source fields, preserves three gate fields and rebases 40 local
fields. Nine control families retain absolute event times, including removed
water-port clocks. Qualification and limitations are tracked in [Progress](../PROGRESS.md).

Surviving cytosol and finite exterior compartments keep their actual current
volumes. Those volumes become the next epoch's initial anchors, alongside the
actual ion, chemical and fuel inventories. This preserves concentrations at the
cut. ER volume remains fixed. Each water compartment retains its original
compliance reference volume, pressure offset, bulk modulus, volume bounds and
impermeant amount; surviving interfaces retain their hydraulic permeability.
Rebasing the compliance reference to the current volume would reset the pressure
law and stored elastic energy, so that alteration is rejected.

The report records removed cytosolic water and fixed ER volume separately, with
additional neutral impermeant material, impermeant mixing energy and elastic
energy. Chemical/fuel mixing energy is already evaluated at current volumes;
adding the water evaluator's all-solute mixing energy would count it twice.
Pool volume work remains an internal diagnostic ledger, not another stored-energy
inventory. Complete water-transfer, heat and pool-volume-work histories stay in
the source archive. Surviving PMCA/ER fuel anchors must satisfy their inherited
concentration range at the actual current volume.
ATP amount loss alone does not imply crossing the lower concentration bound:
shrinking cytosol can increase concentration. The bound applies to each retained
pool divided by its current owner's volume.

The cut does not create wound contacts, release removed material, or supply
mechanical cutting work. This uses Cells' compliant-volume extension; native
BETSE volume-trajectory correspondence, combined water/mitochondrial cuts,
combined water/regulation/assembly cuts and healing remain separate work.

### Live network regulation of pumps, channels and junctions

`resolved_calcium_energy_regulated@1` adds concentration-dependent Na/K pump
availability to the 38-field finite-calcium/fuel parent. Version `@2` also
regulates existing shared channels and gap junctions. Both use the normal
configuration, model, checkpoint and ensemble interfaces; execution qualification
is tracked separately in [Progress](../PROGRESS.md).

Rules sample actual free cytosolic/exterior ions and the explicitly owned finite
ATP/ADP/Pi pool. Junction rules name the sampled endpoint. Native factor equations
retain their declared order: the last rule for a target sets its factor, which
multiplies scheduled availability once. Intrinsic gates and all physical
inventories remain with the parent. Regulation adds no duplicate fuel demand.
Every active raw factor must remain finite and between zero and one, including
shadowed rules and rules whose consumer is scheduled off.

This is common-stage coupling, with native SIM lag and ordering still distinct.
Voltage-dependent charged regulation, exterior sampling for junction rules,
and dedicated calcium-channel targets remain unsupported. The exact `@2` parent
has the cut adapter below; combined water, mitochondrial and assembly regulation
still need their own cut contracts.
The [Na/K contract](../agent-work/cells-worker-01/workfiles/INTEGRATED_NETWORK_REGULATION_HANDOFF.md)
and [channel/junction contract](../agent-work/cells-worker-01/workfiles/INTEGRATED_NETWORK_REGULATION_V2_HANDOFF.md)
describe the source equations and explicit scope limits.

### Cell removal with live network regulation

`resolved_calcium_energy_regulated_excision@1` accepts exactly the regulated
`@2` parent and its own previous cut epochs. Its 38-field archive preserves three
gate fields and rebases the other 35 local fields at the original time. Eight
control families keep their absolute clocks, including removed-owner event times.
Qualification is tracked in [Progress](../PROGRESS.md).

Rules disappear only with their physical pump, shared-channel or junction target.
Survivors retain their order, complete configuration, sampled cell/exterior/fuel
owners and factor values at the cut. Shadowed rules remain declared. Source and
retained electrical fields use the actual regulated availability; projecting to
an unregulated parent would change the field even with identical inventories.
The binder then recomputes live factors from the retained physical state during
continuation.

Complete cut archives retain the source definition, all state/layout arrays and
owned regulation capacity. No-op cuts preserve the source checkpoint; terminal
cuts retain a complete archive. Finite-fuel constructor limits and inherited
charge/field solvability checks remain enforced. Regulation adds no ATP sink or
energy inventory. Mechanical cutting work, wound healing and combinations with
water, mitochondria or assembly remain separate work.

### Static tissue-profile preparation

The `tissue-profiles` commands prepare ordinary tissue definitions from a complete
JSON recipe. Supported models include all `resolved_tissue@1` through `@12`,
calcium/ER, finite fuel, configured transport, mitochondria, compliant water and
regulation. The [example request](../configs/tissue_profiles_active.json)
uses a manufactured three-cell geometry with overlapping regional profiles:

```bash
python -m cells tissue-profiles prepare configs/tissue_profiles_active.json --output /mnt/workspaces/Cells/profile-example
python -m cells tissue-profiles validate /mnt/workspaces/Cells/profile-example
python -m cells tissue-profiles replay /mnt/workspaces/Cells/profile-example/provenance.json --output /mnt/workspaces/Cells/profile-replayed
```

Each output directory must be new. `definition.json` is an ordinary Cells input;
`provenance.json` retains the original definition, profiles, geometry and exact
preparation identity. These commands prepare or verify inputs without advancing
the simulation. Check the resulting definition's numerical/resource bounds with
`python -m cells validate /mnt/workspaces/Cells/profile-example/definition.json`
before choosing a run and recording policy.

Requests declare schema version 1, kind `cells.tissue_profile_preparation_request@1`,
the source `definition`, complete `geometry`, `default`, ordered `profiles`,
six `ion_enabled` flags and the explicit `enabled`/`is_ecm` flags. Native ion order
is Na/K/Cl/Ca/M/P; only physically supported, present Na/K/Cl/Ca ions may be enabled.
Geometry names every owner and reciprocal contact, with thickness and coordinates
in metres. Profiles specify diffusivity in m²/s; the bridge derives permeability
as diffusivity divided by thickness. Native index selectors require their explicit
layout identity. Image selectors contain decoded `grayscale_F` pixels.

Unknown or duplicate fields, nonfinite JSON, ambiguous mappings and unsupported
units refuse before publication. Replaying a complete artifact must reproduce its
definition and provenance, including JSON value types. Selected transport
coefficients may change; initial
state, inventories, physical owners and all unselected properties stay exact.
The [direct component contract](../agent-work/cells-worker-01/workfiles/TISSUE_PROFILE_PREPARATION_HANDOFF.md)
defines the source correspondence. The
[composition contract](../agent-work/cells-worker-01/workfiles/TISSUE_PROFILE_COMPOSITION_HANDOFF.md)
and explicit `SCHEMAS` map in
[the adapter](../src/cells/core/tissue_profile_composition_preparation.py) cover
the intermediate `resolved_tissue@2` through `@11` models and 29 composed schemas.
Versions `@1` and `@12` use the direct bridge, giving 41 supported model schemas.
Their full initial physical state, organelle and
fuel inventories, water volumes, event clocks and regulation configuration remain
exact. The passive geometry/coefficient view used during preparation does not
stand in for a composed model's electrical field or flux. The resulting ordinary
definition still selects its original complete physical model.

For an initial passive tissue prepared from recorded native geometry, the
[geometry-to-profile workflow](TISSUE_GEOMETRY.md#apply-static-tissue-profiles)
derives the selector layout from the bound physical owners and polygon centroids.
Its separate `cells.initial_geometry_profile_request@1` recipe embeds the complete
geometry artifact and retains both source recipes in the output. The ordinary
41-model preparation above remains available when geometry is declared directly.

Preparation of existing cut epochs, assembly and repair models is refused.
The scheduled passive extension below adds membrane interventions. Pressure,
ECM transport and dynamic interventions in composed models have separate
integration requirements. Qualification and remaining limitations are recorded in
[Progress](../PROGRESS.md).

### Scheduled passive membrane profiles

`resolved_membrane_profiles@1` applies timed Na/K/Cl/Ca membrane interventions to
a statically prepared passive `resolved_tissue@1` tissue. Its complete definition
retains the direct profile preparation or joined geometry/profile preparation,
including owner IDs, ordered selectors, native diffusion defaults and explicit
membrane thickness. The [portable example](../examples/scheduled_membrane_profiles/README.md)
contains both an ordinary input and a replayable artifact. Ordinary validation,
serialization, checkpoints and ensemble admission use the same public routes
as other models.

The native logistic pulse is evaluated at every RK4 stage. A stored phase clock
advances with the physical state: INIT suppresses scheduled membrane effects,
while a fresh SIM phase starts at zero and applies its declared events.
Restart preserves this clock; changing phase or resetting it through an ordinary
branch is refused. The [explicit INIT-to-SIM preparation](TISSUE_PHASES.md)
carries evolved physical state and all original accounting history into a new
SIM clock through `resolved_membrane_profile_epoch@1`. This is RK-stage evaluation
of the supported native event
law, rather than a claim of native solver-loop trajectory equivalence.

Events preserve native family order, ordered assignment and duplicate-target
behavior. Na/K and Cl/Ca retain their respective native ion-flag rules. Diffusion
divided by the declared thickness gives the stage's actual permeability. All-time
bounds and actual-stage checks reject negative or nonfinite permeability without
clipping. SIM's nominal timestep must resolve the shortest transition with at
least eight steps; bounded clock-roundoff allowance does not relax that nominal
limit. All twelve parent material, charge and energy fields remain present, plus
the phase clock. Closing a route retains its earlier transfer ledger.

This model supports at most four membrane-event kinds. Pressure/ECM events,
arbitrary callbacks, moving geometry, cuts and combinations with active channels,
water or fuel are outside this version. Independent stage comparisons, short
trajectory refinement and public checkpoint checks have separate scopes from
compiled trajectory qualification; see [Progress](../PROGRESS.md) and the
[component contract](../agent-work/cells-worker-01/workfiles/SURFACE_PROFILE_INTERVENTIONS_HANDOFF.md).

### Scheduled active membrane profiles

`resolved_active_membrane_profiles@1` applies the same supported native membrane
pulse laws to a directly prepared `resolved_tissue@12` tissue, including its
complete 56-law channel catalog, intrinsic channel and junction gates, and
maintained-fuel pumps. The [portable example](../examples/scheduled_active_membrane_profiles/README.md)
includes an ordinary definition and sealed replay artifact. Public loading,
serialization, snapshots and ensemble admission preserve this distinct family.

Only background membrane diffusion changes. Each RK stage converts its actual
diffusion through explicit thickness and solves the full active physical field.
Channel conductance, gates and pump kinetics retain their own controls and
equations. All four control families retain their original clocks. INIT suppresses
scheduled background effects while channels and pumps continue evolving; SIM
applies the pulses. The nineteen parent state fields and one phase-clock field
are preserved. Ordinary restart keeps the clock and complete history. The
[explicit INIT-to-SIM workflow](TISSUE_PHASES.md) now has a distinct active
adapter that carries all nineteen parent arrays into a fresh SIM clock;
the passive adapter continues to refuse active states.

Earlier transfers remain part of conservation accounting after a route closes.
The fixed-route parent evaluator receives a temporary view of the closed-route
diagnostic integral solely for its route-validity check. Actual state is unchanged;
physical amounts, electrical fields, channel/pump fluxes and every derivative
use the actual instantaneous permeability. Conservation checks and returned
observations retain the full transfer and work history. The qualification binds
the parent's call graph and compares physical outputs through closure/reopening,
including refusal of corrupted closed-route history.

The direct static recipe must reproduce all physical owners, channel/gate and
pump declarations. Native Na/K flags remain unguarded and Cl/Ca flags retain
their source behavior; these flags concern the scheduled background component,
not the existence of physical channel or pump owners. Ordered targets, signed
event bounds, nonnegative permeability and phase timing follow the passive
contract above. Other parent families, cuts, moving geometry and pressure/ECM
events are refused.

Independent complete-field/RHS comparisons, short trajectory refinement, eager
CPU JAX parity and public checkpoint checks have distinct scopes. Compiled
active-profile trajectories, GPU execution, finite-fuel/calcium-store coupling
and native full-loop correspondence remain separate. See [Progress](../PROGRESS.md)
and the [component contract](../agent-work/cells-worker-01/workfiles/SURFACE_ACTIVE_PROFILE_INTERVENTIONS_HANDOFF.md).

### Scheduled membrane profiles with calcium stores and finite fuel

Two distinct models extend regional background-permeability pulses to complete
calcium and fuel owners:

| Scheduled model | Physical parent |
| --- | --- |
| `resolved_calcium_membrane_profiles@1` | `resolved_calcium@6`: calcium/ER stores, buffers, plasma transport and shared calcium-channel gates |
| `resolved_calcium_energy_membrane_profiles@1` | `resolved_calcium_energy@5`: the shared 56-law catalog with calcium/ER chemistry and finite ATP/ADP/phosphate pools |

Their static profile artifacts must reproduce the complete physical parent.
At each RK stage, the actual regional background permeability enters that
parent's electrical field and transport equations. The model retains all
chemical inventories, bound calcium, intrinsic gates, reaction extents, pump
histories and energy accounts, together with one phase-clock field. The finite
fuel model uses its existing pool ownership and pump demand; a membrane pulse
does not provide an extra ATP supply.

INIT suppresses the scheduled background contribution while the complete parent
continues evolving. SIM applies the declared native membrane pulses. Original
control families keep their schedules. Closing a background route preserves
earlier transfer history for conservation and observations. The timestep must
resolve the pulse transition and satisfy a conservative bound on the maximum
scheduled background permeability and chemical loss.

Public parsing, serialization, checkpoints, window planning and ensemble
admission retain these model identities. Ordinary restart preserves the clock
and complete state; it cannot perform INIT-to-SIM transfer. These families need
an [explicit phase-transition preparation](TISSUE_PHASES.md) to carry an accepted
INIT state into a new SIM clock. That preparation preserves every physical
array and original accounting reference; the finite-fuel transition starts
with the actual carried pools. Cut contracts remain separate. The full-catalog
water and prescribed-repair compositions are described below. Mitochondria,
live regulation, pressure/ECM events and moving geometry remain separate
compositions. Implementation and qualification results, including independent
reference checks and pending execution checks, are tracked in
[Progress](../PROGRESS.md); interface admission alone is not compiled or GPU
trajectory qualification.

### Scheduled membrane profiles with water and prescribed repair

Regional membrane-permeability pulses can also bind the full 56-law water and
repair models:

| Scheduled model | Complete physical parent | Saved fields |
| --- | --- | --- |
| `resolved_calcium_energy_water_membrane_profiles@1` | `resolved_calcium_energy_water@2` | 43 physical fields and a phase clock |
| `resolved_calcium_energy_water_repair_membrane_profiles@1` | `resolved_calcium_energy_water_repair@2` | 48 physical fields and a phase clock |

Both use a complete static profile preparation for their exact parent, followed
by the same explicit `interventions`, `phase`, `timing_policy` and `reset_policy`
declarations as the calcium/fuel profiles. Parent versions and their portable
preparation artifacts must agree; an older channel catalog cannot be substituted.

At each integration stage, the pulse changes background membrane permeability
while the coupled calculation uses actual calcium, fuel and water volumes.
Na/K, plasma-calcium and ER pumps share the declared finite fuel pools. Repair
retains its separate injury/resealing controls, damage, transfer and heat history.
Closing a background route preserves accumulated transfers and energy; reopening
continues from that history. Water, chemical and injury losses contribute to the
timestep bound alongside the native pulse-transition limit.

Public parsing, serialization, ordinary run/restart and independent-world
planning retain these complete owners. A restart preserves the saved phase
clock. An [explicit INIT-to-SIM preparation](TISSUE_PHASES.md) carries the full
accepted physical state into a new local clock; ordinary restart or branching
cannot perform that transition. Cutting and assembly coupling remain refused
for these scheduled models. The interface tests use
two nanoseconds to exercise real execution and fresh-process restart; those
checks do not establish a physical recovery timescale. Independent trajectory
qualification and current limitations are recorded in [Progress](../PROGRESS.md).

### Static ideal reservoirs with calcium and finite fuel

Two explicit full-catalog families retain owned cytosolic/ER chemistry and all
56 channel laws while allowing static ideal chemical and voltage reservoirs:

| Model | Energy owner | Saved physical fields |
| --- | --- | ---: |
| `resolved_open_calcium@1` | Maintained pump metabolism | 34 |
| `resolved_open_calcium_energy@1` | Actual cellular ATP/ADP/phosphate shared by Na/K, PMCA and ER pumps | 38 |

The complete ordinary calcium/fuel definition is extended with
`exterior_policy: static_declared_ideal_chemical_and_voltage_reservoirs@1`,
`ionic_moiety_domain_policy: hard_global_ionic_moiety_ceilings_fmol_every_stage@1`
and `ionic_moiety_ceiling_fmol`, a map from every ionic species ID to a positive
global upper amount in fmol. Each exterior owner's existing `reservoir` flag,
volume, original inventory and boundary potential remain explicit. Mixed finite
and ideal exteriors are allowed. With no ideal reservoirs, the ceiling must be
`null` and the original closed-family admission applies.

An ideal reservoir maintains its declared concentration while recording all
supplied or removed ions. Plasma calcium pumps, Na/Ca exchange and calcium
channels contribute to that supply alongside the original ionic routes.
Electrode charge and external chemical/electrical work remain in the complete
physical history. A bath does not replenish intracellular ATP: the finite-fuel
family still consumes actual cellular pools and uses explicit regeneration ports.

Ionic ceilings are hard domain limits checked at every stage. They bound the
open-system chemical losses used for timestep admission; they are not conserved
inventories and never clamp an invalid state. Nonionic chemical moieties and
neutral-fuel adenylate/phosphorus retain their conservation checks. Changing a
ceiling changes the model definition and cannot be hidden in a restart.

Public loading, complete snapshots and independent-world admission use these
distinct identities. Scheduled bath composition, INIT-to-SIM operations,
profiles, cutting and assembly require their own explicit compositions. See
[Progress](../PROGRESS.md) for measured qualification scope; input admission and
short checkpoint probes do not establish long trajectories or GPU execution.

### Scheduled baths with calcium and finite fuel

The scheduled counterparts are `resolved_open_calcium_bath_events@1` and
`resolved_open_calcium_energy_bath_events@1`. They retain the complete 34/38-field
static calcium/fuel owner and add a bath clock and a reservoir chemical-work
integral, giving **36 / 40 saved fields**. Current implementation and executed
qualification scope are recorded in [Progress](../PROGRESS.md).

Use the static owner's complete physical declaration with
`exterior_policy: scheduled_declared_ideal_chemical_and_fixed_voltage_reservoirs@1`
and the explicit bath-event, target-site, phase and controller declarations
described in [scheduled ideal baths](TISSUE_GEOMETRY.md#schedule-ideal-reservoir-bath-composition).
The native K, Cl and Na setter order is preserved. K/Na setters require an
explicit M− species with inventories, chemical ownership and transport/control
declarations; Cl-only schedules can use the four-ion owner. The five-ion test
fixtures are separate manufactured models, not equivalent trajectories of the
four-ion fixtures.

Each stage uses the current prescribed bath concentration, actual calcium/ER
state and actual ATP/ADP/phosphate pools. The controller's ion dose, compensating
electrode charge and external work remain explicit. Saved parent fields retain
transport history; `physical_*` observations add the analytic controller
operation. Variable chemical work has its own integral because a static-bath
constant-chemical-potential identity does not apply to a changing bath.

The initial operation includes any nonzero logistic tail at time zero. Original
background charges and chemical/fuel anchors remain unchanged. Hard ionic
ceilings include the prescribed dose at every stage, and timestep admission
checks the pulse envelope and finite-pool turnover. Empty, disabled and INIT
schedules reduce to the corresponding static owner. Ordinary restart retains
both physical histories and the bath clock; a new INIT-to-SIM handoff requires
its own explicit composition.
