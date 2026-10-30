# Physiological perturbations, random streams and checkpoints

Cells provides explicit random-stream ownership in
[`physiology_random_streams.py`](../src/cells/core/physiology_random_streams.py)
and a checked component update in
[`physiology_perturbation_step.py`](../src/cells/core/physiology_perturbation_step.py),
with a paired checkpoint format in
[`physiology_checkpoint.py`](../src/cells/physiology_checkpoint.py). These reuse
the [qualified BETSE perturbation samplers](../agent-work/cells-worker-01/workfiles/BETSE_PERTURBATIONS_HANDOFF.md).
They support explicit component/tissue updates and exact restart. The
whole-loop operation below preserves physiological update frequency across
finer numerical steps. Charged-protein coupling, joint tissue/component cuts,
partitioned GPU execution and biological validation remain separate work.
[Progress](../PROGRESS.md) records the actual checks.

## Draw ownership

`new_stream(binding, rng, stream_id=..., world_id=..., next_tick=...)` returns
an immutable stream. `draw(stream, binding, site=..., enabled=...)` returns a
sample packet and the next stream. One logical tick advances per enabled call,
regardless of the number of owners sampled. Disabled calls return the original
stream without consuming anything. An enabled perturbation with zero physical
amplitude still consumes its draw. The uint64 counter refuses overflow before
sampling; it is never derived from floating time, an observation index or GPU
batch position. Retaining an earlier stream explicitly permits replay or a
branch with the same future draws.

The sampling laws remain distinct. Native MT19937 preserves all words, its
position, the cached Gaussian and its NumPy version. Native `world_id` and
`stream_id` label ownership; they do not create independent random states.
Callers must supply independent states when that is intended. Stable sampling
uses the existing seed/world/tick/site/owner coordinates and requires its
declared world to match the stream. `stream_id` is a bookkeeping identifier,
not an additional random key. Reordering or partitioning stable owners retains
their coordinate samples at a fixed tick; changing the sequence of enabled
calls changes subsequent ticks. No cross-device or cross-version bitwise
normal-sample guarantee is added.

`stream_record` and `restore_stream` validate the complete stream, sampling law
and bound owner layout. `rebind_stream` explicitly transfers unchanged stream
coordinates to surviving owner IDs. Surviving membranes must keep their cell
and environment owners. No owner is invented or silently renamed. The caller
still owns geometry, amount/state remapping and conservation. Changed native
owner counts/order or categorical boundary weights can change future native
draws; the stream API does not assert native subset invariance. Old packets
remain bound to their original layout and cannot be reused as new-layout draws.

## Native tissue-target selection

[`physiology_target_selection`](../src/cells/core/physiology_target_selection.py)
owns the two separate random tapes used by native target preparation. PERCENT
pickers shuffle the current logical cell order with NumPy's legacy MT19937;
global gap-junction setup shuffles a copied membrane array with Python's random
generator. BETSE discards that second permutation and selects the original
membrane prefix. Cells retains both the source selection and the consumed
Python state, including when the selected prefix is empty.

`new_stream` binds complete NumPy and Python states to explicit layout, stream
and world IDs. Both Gaussian caches and runtime versions survive serialization;
world labels do not reseed native tapes. `resolve` runs declared percentage
pickers in order and then optional global GJ setup. Every active shuffle advances
one logical call counter, including 0%/100% selections and empty/singleton axes.
Disabled profiles consume no NumPy draws. Global GJ setup has its own enable
flag, independent of profile and ion flags or INIT/SIM phase.

Repeated setup retains the preceding logical cell order. The authoritative
geometry stays fixed. Native ALL cell targets follow the final shuffled order,
while their membrane/environment targets retain pick-time order; earlier
percentage selections remain fixed. The returned binding reuses the existing
profile masks and physical owner mappings with these ordered selections.
Declaration preflight is stricter than partial invalid native setup: malformed
inputs refuse before sampling. A later counter refusal retains completed
speculative selections and both proposed tapes without changing the parent.

`stream_record` and `restore_stream` save and restore both tapes, original layout
identity, carried order and uint64 counter against explicitly requested stream
and world owners. Restore draws nothing. When subsequent component initialization
shares the native NumPy tape, its caller passes the returned NumPy state forward;
the selection and component streams are not implicitly joined. Tissue checkpoint
and post-cut reselection integration remain separate. Returned source targets
also require downstream physical admission, including reciprocal junction checks.

The [native capture](../validation/perturbations/target_selection_native.py)
executes pinned ALL/PERCENT/INDICES and global-finalizer bodies with private
instances of the actual samplers. The
[independent reference](../validation/perturbations/target_selection_reference.py)
checks owner expansion and target order from captured permutations; it is not
an independent RNG implementation. [Progress](../PROGRESS.md) records exact
source/restart evidence separately from tissue evolution or GPU qualification.

### Preparing physical tissue profiles

[`random_tissue_profile_preparation`](../src/cells/core/random_tissue_profile_preparation.py)
connects these native selections to the existing static physical preparation.
Its exact admitted models are `resolved_tissue@1`, `resolved_tissue@12`,
`resolved_calcium@11` and `resolved_calcium_energy@5`. It creates a new initial
definition with selected membrane permeability and insular junction coefficients;
full inventories, gates, owners and control histories are retained. It does not
reinterpret an evolved checkpoint or rescale stored charge/energy anchors.

A request uses the existing static preparation fields (`definition`, complete
SI `geometry`, `default`, ordered `profiles`, `ion_enabled`, `enabled`, `is_ecm`)
with `schema_version: 1`, kind
`cells.random_tissue_profile_preparation_request@1`, complete `selection_stream`,
explicit `stream_id`/`world_id` and `global_gj_percent`. Percentage selectors have
no pre-resolved permutation. The owned sampler supplies those permutations to
the qualified static bridge and verifies the complete numerical binding. Native
ALL occurrence order and the static coefficient recipe are both retained; their
membership agrees even when re-entry starts from a carried logical cell order.

`global_gj_percent: null` disables global selection. A numeric value prepares its
targets and consumes the native Python shuffle only; it fires no blocker and
changes no physical coefficient by itself. Disabled profiles consume no NumPy
draws, independently of whether global GJ selection is enabled. A physical
admission failure retains the original tapes, completed selection and proposed
successor for diagnosis. The caller replaces its source only after success.

The public module provides a complete durable bundle:

```sh
python -m cells.random_tissue_profiles prepare request.json --output prepared
python -m cells.random_tissue_profiles replay prepared/provenance.json --output replayed
python -m cells.random_tissue_profiles validate replayed
```

The manifest binds the definition, complete recipe, successor stream and exact
source/runtime identities. It is written last; existing destinations are refused
and incomplete publication remains failed. Replay starts from the saved source
tapes to reproduce the same definition and successor. It is not continuation
from the successor. For another preparation, explicitly pass that successor in
a new request with its matching geometry and owners. Shared evolved checkpoints,
post-cut reselection and device execution remain separate. Qualification and its
limits are recorded in [Progress](../PROGRESS.md).

### Initializing physiology after random preparation

[`physiology_initial_preparation`](../src/cells/core/physiology_initial_preparation.py)
continues the exact selected NumPy tape into the qualified static-potassium
initializer. It creates a full initial numeric checkpoint, physical owner
binding and component state for the same four ordinary families. Component axes
come from the unchanged geometry, not the picker's carried logical cell order.
Callers explicitly declare ion order, boundary-cell occurrences, protein
concentrations by owner in mol/m3, component controls, stream ID and starting tick.
The native world ID is retained without deriving a seed from it.

The component base is computed from the prepared physical permeability times
declared membrane thickness. This retains the qualified binary64 conversion;
it does not promise exact recovery of an earlier D before D-to-P conversion.
One static draw occurs even in INIT/fast mode, with disabled dynamic guards or
zero static amplitude. Current D receives the noise, base D stays unchanged and
scheduled D is zero. Numeric/component elapsed time and loop counts stay zero.
The noisy permeability must pass the complete initial rate view and original
timestep/turnover limits before the pair is returned. First SIM finalization
still uses base + scheduled according to the existing component law.
Initial admission does not certify time-integration accuracy: fast extracellular
electrical relaxation can require a finer declared grid even when instantaneous
rates and membrane turnover pass. Trajectory qualification retains the original
physical horizon and checks both full state and voltage against independently
integrated references; no timestep retry or tolerance relaxation is implicit.

After initialization, the component owns the NumPy successor. The full selection
source/successor and Python successor remain history; the earlier selection
snapshot must not be treated as the current NumPy tape for another setup call.
Selection calls, component ticks and elapsed physical time remain separate.
This initial bundle does not project protein charge or initialize a complete
charged loop. Failed static/physical admission retains the selection prefix and
any proposed component buffers/tape; no source is partially committed.

The [public bundle interface](../src/cells/physiology_initial_preparation_io.py)
wraps the existing complete bound physiology checkpoint:

```sh
python -m cells.physiology_initial_preparation_io prepare request.json --output initialized
python -m cells.physiology_initial_preparation_io validate initialized
python -m cells.physiology_initial_preparation_io replay initialized/initialization.json --output replayed
```

The request uses `schema_version: 1`, kind
`cells.physiology_initial_preparation_request@1`, the complete random-profile
request under `preparation`, and explicit component inputs under `component`.
Source/runtime identities and nested manifests are bound before the outer
manifest commits. Publication privately recomputes the recipe for admission;
it publishes the same single committed successor. Loading restores the saved
pair without initialization or RNG sampling, checks every initial numeric
state/layout array, and validates its history associations. Deterministic static
coefficient reconstruction is allowed; its percentage permutations are already
recorded. Hash-consistent records are integrity checks, not proof of historical
RNG execution; explicit replay supplies that stronger comparison. Actual
qualification status and scope are recorded in [Progress](../PROGRESS.md).

### Starting complete loops from reproducible initialization

[`physiology_initial_loop_io`](../src/cells/physiology_initial_loop_io.py)
retains the full initial bundle under `origin/` and a corresponding managed
checkpoint under `loop/`. The handoff adds an explicit zero-loop cursor while
preserving both random histories, all numeric state/layout bytes, component
buffers and clocks. Preparing or loading this association draws nothing.
Publication uses the existing private origin-replay audit; it commits the same
single static successor. Source/runtime identities and nested payload hashes
are checked before the final outer manifest is published.

```sh
python -m cells.physiology_initial_loop_io prepare initialized --output loop-start
python -m cells.physiology_initial_loop_io validate loop-start
```

Advance its managed child through the existing complete-loop operation:

```python
from cells.physiology_initial_loop_io import load_handoff
from cells.physiology_checkpoint import advance_loop_checkpoint

start = load_handoff("loop-start")
binding = start.initialization.binding.component
first = advance_loop_checkpoint("loop-start/loop", "loop-01", binding)
second = advance_loop_checkpoint("loop-01", "loop-02", binding)
```

Keep `loop-start` with the resulting paired checkpoints: it retains the earlier
selection recipe and parked Python history, while the paired checkpoints own
the evolving numeric state, component and current NumPy stream. Restore rejects
a different valid managed child even if its outer byte hash is resealed.
Saved bundles must contain their own child directories and payloads; symbolic
links inside the bundle are refused, including hash-valid links to external files.

The ordinary loop contract remains unchanged. INIT retains initialized noisy
permeability and suppresses dynamic protein draws; SIM finalizes base plus
scheduled permeability and follows the original protein draw guard once per
complete physiological call. Tissue refinement does not add component draws.
This bridge covers the four ordinary families without charged-protein feedback
or native calendar labels. [Progress](../PROGRESS.md) records the physical
durations, numerical comparisons and qualification status.

## Explicit component updates

`initialise(binding, controls, protein, diffusion_m2_s, stream)` constructs an
immutable `PhysiologyPerturbationState`. It owns three protein concentration
buffers (cell, membrane view and environment) and three permeability buffers
(current, pre-noise base and scheduled modifier), plus controls, stream,
accumulated `time_s` and `loop_calls`. Initialization consumes the native
`static_K` draw even in INIT/fast modes or at zero amplitude. It keeps the base
permeability from before static noise; no physical loop has elapsed yet.

`advance(state, binding)` attempts one full `controls.dt_s` component call and
returns a `PerturbationTransition` containing the accepted state, optional draw
packet and diagnostics. SIM first finalizes current permeability from
`base + scheduled`; thus its first finalization removes the initialization
noise. The protein perturbation draws only under the source guard: normal SIM
with both dynamic noise and protein enabled. Zero amplitude still draws under
that guard. Inactive calls preserve every protein buffer, including a stale
membrane view. Every successful call advances elapsed time and loop count,
whether or not a draw occurs. The first call carries source label zero but
applies a full dt; there is no RK-stage resampling or square-root-dt scaling.

This composes only the already qualified static and protein components. It
does not execute the rest of BETSE's physiological loop, including downstream
bulk membrane refresh or clipping. Scheduled modifiers must be staged by the
caller. Accepted protein and physical permeability buffers must be finite and
nonnegative; signed scheduled modifiers are allowed, with the finalized result
checked before the protein draw. The original protein transfer conservation
bound remains `3e-13` times the sum of absolute transferred amounts.

`PerturbationRejected` retains the attempted state, packet, proposed stream,
diagnostics and failing stage. The caller's accepted state stays unchanged. A
trial that already consumed a draw retains that proposed RNG/cache for
inspection; it is not an accepted checkpoint. Clock overflow, a floating time
addition that cannot advance and invalid finalized permeability refuse before
sampling. The component neither retries nor repairs rejected values.

## Explicit tissue owners and units

[`physiology_tissue_binding.py`](../src/cells/core/physiology_tissue_binding.py)
binds the component to the exact ordinary passive, 56-law ionic, calcium and
finite-fuel model classes. `bind_tissue` requires complete explicit cell,
membrane, environment and ion ID permutations, a positive thickness in metres
for every membrane, an ordered boundary-cell occurrence list and caller
provenance. It uses actual membrane areas and cell/exterior volumes. Boundary
duplicates retain their source sampling weights; axis order never implies
ownership.

The initial adapter supports the native matrix mode, which has one exterior
volume parameter. Every actual exterior volume must therefore be identical;
heterogeneous volumes are refused, without averaging or replacing the declared
geometry. The adapter requires float64 and retains the complete specification
hash, including execution and experimental settings.

Cells stores passive membrane permeability `P` in m/s. The component uses
diffusivity `D` in m²/s; the explicit bridge is `D = P × thickness`.
`initial_diffusion(binding)` gathers the actual initial values into component
order. `component_permeability(state, binding)` maps current, base and signed
scheduled buffers back to physical tissue order with zero inactive padding.
It validates all six material buffers and refuses nonrepresentable conversions.
It does not draw, finalize a schedule, advance either clock, apply protein charge
or replace the solver's passive permeability. Charged-protein coupling and the
point at which physical controls reach the solver require separate integration.

Bindings and their geometry arrays are immutable. `binding_record` exports
provenance; `restore_binding(record, spec)` reconstructs the mapping from the
exact model definition and requires complete agreement with the saved record.
Changing geometry, thickness, owners or provenance does not become acceptable
merely by recalculating a record hash.

## Applying permeability to a complete tissue readout

[`physiology_permeability_view.evaluate`](../src/cells/models/physiology_permeability_view.py)
takes the exact ordinary `spec`, accepted `state`, original `layout`, explicit
held `control`, tissue `binding`, component state and a positive `step_s`.
It maps the component's current `D` to physical `P`, replaces only passive
membrane permeability in a temporary layout, and evaluates the original full
field and rate equations. Inventories, geometry, physical anchors, gates and
active channel/pump parameters remain unchanged. The returned layout, complete
readouts, derivatives, permeability buffers and admission arrays are immutable.

Admission replays the binding against the complete source definition and checks
the exact original layout, state and control types, shapes and precision. The
original physical-domain, balance and method/loss limits remain in force.
Additional limits bound actual absolute passive transfer against each finite
free-ion inventory and all-consumer gross fuel turnover to **0.05 per proposed
step**. Opposing routes cannot hide turnover by netting. The proposed step must
fit the source nominal timestep, allowing only the stated clock-representation
roundoff. Changing `P` to zero while its route has nonzero historical transfer
still refuses under the original structural-support rule; history is not reset.

The result records the actual held controls, proposed step, balance diagnostics
and unchanged component clock/draw count. This is a readout at an accepted state;
it does not advance either clock, draw noise, finalize scheduled modifiers,
apply protein charge or prove synchronization with a schedule. The temporary
layout must not replace the original layout in a numeric checkpoint. The
explicit tissue-step and restart operations below apply that temporary view
through an accepted interval. Automatic component scheduling remains separate.
[Progress](../PROGRESS.md) records the scoped comparisons and their limits.

## Advancing a bound tissue checkpoint

[`physiology_tissue_step.advance`](../src/cells/core/physiology_tissue_step.py)
accepts the original `spec`, numeric `checkpoint`, tissue `binding` and component
state. It attempts exactly the next interval on the original `EventGrid`.
An optional `end_time_s` must equal that next point; the helper cannot skip a
control event or take an extra step after the terminal checkpoint. Original
schedules select the held control at the start and the right-continuous control
at the endpoint. The component's current permeability stays fixed through RK4.

The original zero/nonzero passive-route support must remain identical in both
directions. Input and output pass ordinary checkpoint validation. RK trial
states receive domain, field, finite-rate and gross-turnover checks; accumulated
energy/conservation and monotonic history checks apply to accepted endpoints,
using both original and temporary permeability declarations. The result retains
the original layout, binding and component. Its immutable trial includes the
raw stage states, derivatives and statuses. `TissueStepRejected` preserves the
uncommitted trial and source objects without clipping, repair or retry.

[`advance_tissue_checkpoint`](../src/cells/physiology_checkpoint.py) connects
that step to complete bound checkpoint files:

```python
from cells.physiology_checkpoint import advance_tissue_checkpoint

result = advance_tissue_checkpoint(
    "before-step", "after-step", tissue_binding.component,
    expected_stream_id="physiology", expected_world_id=world_id,
    tissue_binding=tissue_binding,
)
```

The operation loads and validates the source pair, attempts one interval, then
publishes the accepted endpoint in a new directory using the existing bound
format. It returns the `TissueStepResult` after publication. Installation source
hashes remain pinned across restoration, stepping and publication. An existing
destination or an older unbound checkpoint refuses before numerical work.
Numerical refusal leaves no destination; a failed publication retains a failure
artifact and cannot be loaded as an accepted pair. The source directory remains
unchanged.

All six component buffers, pending modifiers, controls, component time, loop
count and complete random stream remain unchanged during this operation. It
does not finalize permeability or infer a component update from tissue time.
Continue through the bound operation to retain this association: the inner
ordinary numeric snapshot alone stores the original layout and does not restore
the physiological permeability component. This host operation covers the four
ordinary model families. The whole-loop operation below additionally updates
the component; charged-protein physics and GPU execution require separate
integration and qualification. A checkpoint with a loop cursor refuses this
single-step operation, preventing silent loss of its scheduling association.

## Advancing a complete physiological loop

[`physiology_tissue_loop.advance`](../src/cells/core/physiology_tissue_loop.py)
combines one component update with every original tissue/control interval up
to the next declared physiological boundary. Its fixed physiological duration
is `component.controls.dt_s`; the finer tissue timestep is `spec.execution.dt`.
Refining tissue steps or splitting them at control events does not add random
draws or rescale the component's uniform protein flux. The proposed component's
finalized permeability stays fixed across all those tissue steps.

The cursor explicitly declares a Cells loop index. Its left and right times
are `index * physiological_dt` and `(index + 1) * physiological_dt`; both must
be exact points on the original event grid. The full interval must fit inside
the original experiment. There is no inferred index, partial final update or
checkpoint cursor partway through a loop. Component elapsed time and prior
call count can have independent offsets, for example from INIT calls. The
cursor records these coordinates and preserves `component_call_origin =
component.loop_calls - loop_index`.

The public operation starts from an explicitly bound checkpoint:

```python
from cells.physiology_checkpoint import (
    initialise_loop_checkpoint,
    advance_loop_checkpoint,
    load_physiology_checkpoint,
)

# Declare the association at an exact nominal boundary; no draw or step occurs.
cursor = initialise_loop_checkpoint(
    "before-loop", "managed-loop", tissue_binding.component, loop_index=0,
)
result = advance_loop_checkpoint(
    "managed-loop", "after-loop", tissue_binding.component, loop_cursor=cursor,
)
saved = load_physiology_checkpoint(
    "after-loop", tissue_binding.component, require_loop_cursor=True,
)
```

`advance_loop_checkpoint` publishes only a complete accepted loop, returning
`TissueLoopResult` after the numeric endpoint, component and next cursor are
saved together. Source/runtime checks and original numerical acceptance remain
in force. A `TissueLoopRejected` exception retains the original pair, proposed
component/random stream/packet, completed local tissue steps and failed raw
trial when available. No partial loop is committed. Explicit replay from the
unchanged source uses the same random tape. Publication errors retain a failure
artifact and cannot load as accepted checkpoints. Existing output directories
and attempts to reinitialize a managed checkpoint refuse.

The [pinned BETSE source audit](../agent-work/cells-worker-01/workfiles/physiology_loop_bridge_source_audit.json)
finds permeability finalization before ionic work, then guarded protein noise
before bulk/voltage refresh. This bridge stages the complete component first.
The accepted transformations commute only within its four ordinary model
families: tissue equations do not read component protein, protein updates do
not read tissue ions, and tissue stepping has no other random sites. Protein
charge, native failure-prefix behavior and complete native-loop equivalence
remain outside this identity. Native `linspace` labels also differ from the
Cells nominal boundaries; the clocks are not treated as interchangeable.
Automatic scheduled-buffer staging, geometry/cuts, the fast equivalent-circuit
solver and GPU execution require their own extensions and qualification.

## Separate pre-ion and post-ion component phases

[`physiology_perturbation_phases`](../src/cells/core/physiology_perturbation_phases.py)
exposes the component ordering needed for a future charged physiological loop.
`prepare(component, tissue_binding.component)` returns a sealed proposal whose
`held_state` contains finalized SIM permeability. Protein, random state, controls
and component time/count stay unchanged; INIT retains current permeability.
The tissue unit adapter converts this held diffusion coefficient to physical
permeability. Preparation draws no protein noise and publishes no accepted state.

After caller-owned ionic work, `finish(original_component, binding.component,
preparation)` validates the complete source/binding/held-buffer association and
calls the existing guarded full-duration component transition exactly once.
Pass the original component, not its held proposal. An advanced source cannot
reuse a stale preparation. Repeating an unchanged source can replay an
uncommitted proposal; the outer transaction remains responsible for committing
once. Recomputed permeability finalization validates the proposal and is not a
second physical event.

Rejected preparations/finishes retain available held proposals, trial material,
random packets and stream states. This module performs no ionic integration or
checkpoint publication and establishes neither full native-loop equivalence nor
native failure-prefix behavior. The original qualified loop remains unchanged.
Qualification status is recorded in [Progress](../PROGRESS.md).

## Protein amounts and electrostatic response

[`physiology_protein_projection`](../src/cells/core/physiology_protein_projection.py)
projects protein concentration into amount and charge using actual cell and
exterior volumes. Callers declare both valence and Faraday constant. Results
use physical tissue-owner order without inactive padding. Membrane protein
concentrations are views of material owners and add no separate inventory.
`project(protein, binding, valence=..., faraday_C_mol=...)` reports absolute
stocks; `delta(reference_protein, current_protein, binding, ...)` reports
concentration differences multiplied by those same volumes. It never subtracts
large absolute charges to construct a small change or adjusts a balance
residual to make it vanish.

The native [protein source audit](../agent-work/cells-worker-01/workfiles/physiology_protein_projection_source_audit.json)
finds protein valence `-1` and Faraday constant `96485 C/mol`. The Cells field
uses `6.02214076e23 * 1.602176634e-19 C/mol`. Native reproduction and Cells field
conversion therefore require their respective explicit constants. A declared
protein valence is a model input, not a claim that all biological proteins
have the same charge.

The delta reports the raw material/charge residual and strict conservation
test separately from input-stock floating-point resolution and conversion
roundoff. `storage_resolution_used` identifies reliance on the latter bound.
This diagnostic never relaxes the electrical field's charge/current tolerances.

[`physiology_protein_charge_view.evaluate`](../src/cells/models/physiology_protein_charge_view.py)
compares electrostatic fields at one accepted numeric checkpoint. It uses the
checkpoint's original scheduled controls, geometry and mobile-ion inventories,
holding current component permeability fixed in both solves. The caller
explicitly supplies the reference protein state represented by the unchanged
electrical baseline and the current protein state. Only their projected charge
increment enters the second solve through the field solver's charge inputs.
Stored initial-charge anchors are never rewritten; nonzero reference stock
alone produces no added charge.

```python
from cells.models.physiology_protein_charge_view import evaluate

response = evaluate(
    spec, checkpoint, tissue_binding, reference_component, current_component,
    protein_species_id="separate_protein", valence=-1,
)
voltage_change = response.potential_change_V
```

The named protein must be absent from existing ionic, chemical and finite-fuel
inventories. This guards declared duplicate ownership; the caller still owns
the physical interpretation of its reference state. Missing or incompatible
owners, nonconservative material changes and failed field closure refuse.
`ProteinChargeViewRejected` retains the attempted charge inputs, projection
and raw field trial when available. Accepted response arrays are immutable.

This is a read-only field diagnostic: potential, capacitor/electrode charge,
capacitor energy and closure at a fixed state. It neither draws noise nor
advances material, gates, component clocks or tissue time. Its capacitor energy
change does not account for protein transport work or chemical free energy.
The conditional endpoint diagnostic below adds explicit chemical and clamp
terms, and the held-protein RHS below evaluates complete ionic/chemical rates.
Trajectory work/heat ledgers and integration into the physiological loop
require a new qualified composition.
Existing loop checkpoints retain their uncoupled-protein contract.
[Progress](../PROGRESS.md) records the actual qualifications and their limits.

## Conditional protein endpoint work

[`physiology_protein_thermodynamics`](../src/cells/core/physiology_protein_thermodynamics.py)
defines an optional ideal-solution chemical energy at fixed owner volumes:
`G = R T sum(n * (log(c / c0) - 1))`. Temperature, standard concentration `c0`
and gas constant are declared inputs. Each actual cell/exterior stock counts
once, including finite protein stocks at owners that are ionic reservoirs.
Membrane views add no inventory. Zero stock has zero energy by continuity and
explicitly minus-infinite ideal chemical potential; there is no concentration
floor. Endpoint differences preserve small changes without subtracting rounded
total energies. This is an explicit Cells assumption, not a native BETSE
protein energy law or a measured biological free energy.

[`physiology_protein_work_view.evaluate`](../src/cells/models/physiology_protein_work_view.py)
combines that chemical difference with two qualified field views at one accepted
tissue checkpoint. Supply a common `charge_reference` component, `before` and
`after` components, a distinct `protein_species_id`, valence and positive
`standard_concentration_mol_m3`. Both endpoints must use identical current
permeability and strictly conserve protein amount. Stock-resolution-only
admission is insufficient. The checkpoint's original anchors, ionic state,
scheduled controls, geometry and temperature remain fixed.

The signed conditional reversible requirement is
`W = delta G_protein + delta U_capacitor - W_clamp`, in pJ. Positive clamp work
means energy entering the held system. It is calculated from each fixed
reservoir potential times its electrode-charge change, using the stored
capacitor matrix and represented material-charge change. The result keeps
per-owner chemical terms, per-membrane capacitor terms and per-electrode work.
Reversals and split transfers must retain the same electrical reference.

Requested versus represented charge, edge versus matrix assembly, and direct
endpoint versus stable electrode differences are separate diagnostics. The
electrical identity retains its raw residual and a bound propagated from the
unchanged field tolerances and floating-point arithmetic. Original field
closure remains mandatory. A common clamp-potential shift `delta V` predicts
`delta W [pJ] = 1e12 * delta V * gauge_work_coefficient_C`; conservation is not
used to erase a small residual or assert exact gauge independence.

This is a read-only endpoint requirement under fixed-ion constraints. Holding
ions fixed can require additional work even at a current-balanced field. The
diagnostic does not include that holding process, ongoing ionic dissipation,
heat, stochastic driving work or a realizable transfer protocol; it establishes
neither total protocol work nor an attainable minimum. It advances no state or
random stream. A `ProteinWorkViewRejected` retains available endpoint trials
and the underlying field rejection. Live protein feedback and complete
trajectory energy accounting remain separate work.

## Complete rates with held protein charge

[`physiology_protein_charge_rhs.evaluate`](../src/cells/models/physiology_protein_charge_rhs.py)
routes the separately owned protein charge through the complete passive,
channel/pump, calcium/ER and finite-fuel rate calculations. Supply the original
checkpoint, tissue binding, explicit reference/current components, distinct
protein species identity, valence and `step_s`. It uses actual scheduled
controls and current component permeability. `step_s` checks current passive
and fuel turnover against the existing ceilings; the call advances no time.

The adapter returns both the original complete readout and charged rates.
Permeability and protein are held fixed, so protein contributes no material or
charge-rate term during this call. The shifted field can change channel gates,
plasma transport, cytosolic influx and ATP demand. Intrinsic ER rates, ER voltage,
pool thermodynamics and regeneration retain their original inputs at this same
state. Their later evolution requires an integrated trajectory.

The original checkpoint is checked against its own anchors and histories.
An ephemeral argument view then supplies the protein increment to the frozen
kernels' plasma charge inputs. It changes neither the saved layout nor chemical
fixed charges, ER parameters, initial membrane-voltage baselines or fuel stocks.
This argument view is not an accepted checkpoint or a new energy baseline.
The result retains actual field charge and the roundoff between the two charge
addition orders, `(anchor + ionic) + protein` and `(anchor + protein) + ionic`.

The shifted complete model must pass its own field, channel-voltage,
pump-affinity, rate-domain and turnover checks. Passing the earlier passive
electrostatic diagnostic alone is insufficient. `ProteinChargeRHSRejected`
retains available original/charged trials and diagnostics. The array-only
`array_readouts` entry point accepts pre-admitted state, controls, layout and
explicit padded protein-charge inputs; its validity flag does not establish
source provenance or trajectory acceptance.

This supports the next joint physiological loop, but does not publish one.
Protein-transition work and native update order need their own composition.
The held-protein trajectory below adds interval accounting and restart.
Qualification details,
including CPU array execution and independent references, live in
[Progress](../PROGRESS.md).

[`physiology_protein_charge_step.array_rk4_step`](../src/cells/core/physiology_protein_charge_step.py)
uses these complete rates at every RK4 stage with one held protein charge,
permeability and control packet. Ionic, gating, ER and fuel states evolve in
the trial. Stage domains, field validity and gross turnover remain mandatory;
the result retains all stage states, derivatives, diagnostics and the first
invalid stage. Its validity flag establishes local numerical admission only.
It publishes no checkpoint and does not validate a coupled trajectory's
integrated energy histories, protocol work, clock ordering or restart.

## Accepted intervals with held protein charge

[`physiology_protein_charge_interval`](../src/cells/core/physiology_protein_charge_interval.py)
owns a separate `HeldProteinCheckpoint`. It retains an accepted ordinary seed,
the unchanged layout, explicit charge-reference and current components, and the
complete evolved numeric state. The current protein and permeability are fixed
throughout this trajectory; component time, loop count and RNG do not advance.
The initial charge redistribution is a declared starting condition. Its prior
preparation work is outside this trajectory and is not inferred from an energy
residual.

Each `advance` attempts exactly the next original integration/control boundary.
It holds left-end controls through RK4, checks every stage's complete domains,
field closure, gross turnover and energy-rate residual, and admits the
right-continuous endpoint before returning a new checkpoint. Failed attempts
retain the source, raw trial and available accounting report. They publish no
new state and do not retry automatically.

[`physiology_protein_interval_accounting`](../src/cells/core/physiology_protein_interval_accounting.py)
checks both the attempted interval and the unchanged seed-to-current history.
It retains ionic, chemical, ER, fuel, boundary/work and dissipation checks with
the original model's tolerances. Stable chemical and capacitor differences use
the original anchors and actual held charge; no rounded bulk energy is
subtracted, no anchor is reset, and tolerances do not accumulate per step.
Finite-fuel pump transfers remain internal, with pool free energy and external
regeneration supply accounted separately. Full accounting reports retain raw
balances, limits, energy terms and failed checks.

```python
from cells.core import physiology_protein_charge_interval as held
from cells.physiology_protein_checkpoint import (
    load_held_protein_checkpoint, write_held_protein_checkpoint,
)

point = held.initialise(
    spec, ordinary_seed, tissue_binding, charge_reference, component,
    protein_species_id="protein", valence=-1,
)
point = held.advance(spec, point).checkpoint
write_held_protein_checkpoint(path, spec, point)
saved = load_held_protein_checkpoint(path)
point = held.advance(saved.spec, saved.checkpoint).checkpoint
```

The separate `cells.held_protein_charge_restart@1` format keeps the ordinary
seed, complete reference/current protein components and random streams, binding,
numeric endpoint, source/runtime pins and exact grid position. It syncs payloads
before committing the final manifest and refuses partial or inconsistent
bundles. Loading rechecks the physical context and seed-to-current balances;
it does not replay every historical RK stage. Hashes establish association,
not authorship. The charged endpoint is never saved as an ordinary checkpoint.

This supports held-protein ionic evolution and restart. The
[post-ion operator below](#post-ion-protein-updates-with-a-declared-energy-budget)
accounts for protein movement with explicit work and dissipation declarations.
Complete stochastic loop composition and GPU qualification remain separate
work. Run evidence and current qualification status are recorded only in
[Progress](../PROGRESS.md).

### Array accounting for batched execution

[`physiology_protein_interval_arrays`](../src/cells/numerics/physiology_protein_interval_arrays.py)
provides NumPy/JAX interval balances with static model family and array inputs.
The caller supplies admitted complete states, original layout with held
permeability, padded protein-charge increments, actual endpoint controls and
material tolerances. Source/binding/projection admission remains outside this
array layer; the qualified host accounting remains the reference and admission
path for public held-protein checkpoints.

`endpoint_values` evaluates an actual charged endpoint and packages its source
state, controls, layout, charge, field and rate validity. `evaluate` can compute
both endpoints itself, or consume `before_endpoint` and `after_endpoint`
together. Supplied records must match every input exactly and satisfy current
domain and capacitor-closure checks. The retained actual potentials must also
reproduce every membrane voltage and the prescribed reservoir potentials;
nodal charge closure alone would miss inconsistent voltages around capacitor
cycles. This separates endpoint preparation from accounting without moving
numerical arrays through the host or replacing field checks with an anonymous
validity flag. Provider records establish an execution contract; callers must
obtain them from `endpoint_values`.

Stable chemical differences, scaled products and explicit precision/overflow/
underflow checks retain the original energy and material budgets. Unresolved
cancellation of nonzero chemical terms to zero has a separate refusal flag.
A float64 array calculation may refuse a case that the high-precision host can
resolve; the array path does not silently relax the budget or repair the result.

The supported compilation scope is recorded in [Progress](../PROGRESS.md).
Shared geometry with dynamic per-world state, permeability, charge and controls
is the intended batching route. Compiling both complete RHS endpoints and all
accounting together is a separate memory requirement from compiling the
accounting stage using associated endpoint records. CPU qualification does not
establish GPU performance, GPU parity or cross-runtime checkpoint migration.

### Protein chemical energy in arrays

[`physiology_protein_chemical_arrays.change`](../src/cells/core/physiology_protein_chemical_arrays.py)
evaluates the optional ideal-protein chemical functional using NumPy/JAX arrays.
It requires complete before/after `ProteinState` buffers, cell and environment
volumes in m3 on the matching component-owner axes, and explicit scalar float64
temperature, standard concentration and gas constant. Membrane concentration
views are validated but do not count as a separate material inventory.

Zero stocks use the continuous ideal free-energy limit and have chemical
potential `-inf`; empty owner vectors are supported. Scaled arithmetic retains
tiny material changes and the actual net amount in the common chemical term.
`.valid` reports a resolved chemical diagnostic. `.closed_valid` additionally
requires the original strict material tolerance, **3e-13 times gross transferred
amount**, with no stock-resolution allowance. Explicit precision/subnormal
refusals can be stricter than the high-precision host path. The calculation
contains no host transfers or Decimal operations; it provides neither a heat
or driving law nor checkpoint admission. CPU compilation evidence and GPU
qualification status are recorded in [Progress](../PROGRESS.md).

### Protein electrical endpoint work in arrays

[`physiology_protein_electrical_arrays.evaluate`](../src/cells/numerics/physiology_protein_electrical_arrays.py)
accepts actual before/after `ArrayEndpoint` provider records and an explicit
`requested_material_charge_change_C` vector on the padded physical-node axis.
The complete ionic state, permeability, geometry and controls must be fixed.
Endpoint association, domains, charge grouping, capacitor closure, membrane and
clamp potentials, and current closure from the supplied potentials are checked.
An anonymous rate-valid flag cannot replace those checks.

The directly requested charge, difference between stored reference increments,
and represented change in grouped field charge remain separate. Tiny transfers
can otherwise disappear when subtracting large reference values. Inactive
padding must be zero; physically owned reservoir protein increments are retained.
Outputs include stable capacitor-energy change, per-reservoir electrode charge
and work, total clamp work, field/arithmetic bounds and a gauge-work coefficient.

This is the electrical contribution only. The caller retains protein projection
and strict material admission; the result does not supply chemical energy, a
driving/heat law, accepted time evolution or checkpoint publication. The
[Progress](../PROGRESS.md) record distinguishes full NumPy endpoint comparisons
from the smaller compiled CPU JAX accounting batches using actual NumPy provider
records. Compiled endpoint field solves and GPU qualification remain separate.

### Combined protein endpoint work in arrays

[`physiology_protein_work_arrays.evaluate`](../src/cells/numerics/physiology_protein_work_arrays.py)
combines chemical and electrical work from a common input frame. It accepts
the original charge-reference protein, before/after protein states, their actual
field endpoint records and a complete numeric `WorkGeometry`. Explicit valence,
Faraday constant, gas constant, temperature and standard concentration retain
their units and association with the physical model.

The kernel reconstructs three projections: reference-to-before,
reference-to-after and directly requested before-to-after. It checks material
closure, actual field-charge association, owner coverage, membrane incidence and
SI volume/area conversion. It then combines chemical change, capacitor change
and per-reservoir clamp work, retaining each term and its numerical diagnostics.
Compensated arithmetic preserves small contributions; unresolved work or an
unrepresentable projection refuses rather than receiving an enlarged tolerance.

The returned conditional work is `ΔG_protein + ΔU_capacitor − W_clamp` at fixed
ionic state, permeability, geometry and controls. Named provenance and protein
species declarations remain host responsibilities. This result does not commit
a stochastic update, supply external work/dissipation, or establish a driving or
heat law. [Progress](../PROGRESS.md) records the qualified CPU batches and
memory limits separately from future GPU execution and transition admission.

### Declared protein energy budgets in arrays

[`physiology_protein_drive_arrays.evaluate`](../src/cells/numerics/physiology_protein_drive_arrays.py)
recomputes the complete associated endpoint work before checking explicit signed
external work and nonnegative dissipation, both scalar float64 values in pJ.
The required provenance describes the supplied budget; it is not evidence of a
physical driving law. Original source, geometry, material, field and precision
checks remain part of admission.

The balance is `ΔG_protein + ΔU_capacitor + D − W_clamp − W_external`.
Its absolute tolerance remains **2e-8 pJ** for passive/ionic and **1e-9 pJ** for
calcium/fuel. The separate numerical error bound never enlarges that tolerance.
An error-free expansion retains small residuals between large cancelling
declarations. Unresolved intermediate precision refuses explicitly instead of
turning a missing work term into zero.

This kernel consumes complete endpoint inputs and returns diagnostics. It draws
no randomness, solves no new field, publishes no state and accepts no loop.
[Progress](../PROGRESS.md) distinguishes the four-family NumPy checks, compiled
budget arithmetic and reduced passive full-wrapper check from future complete
transition and GPU qualifications.

### Supplied-packet protein transitions in arrays

[`physiology_protein_transition_arrays`](../src/cells/numerics/physiology_protein_transition_arrays.py)
proposes a complete post-ion component update from an explicitly supplied random
packet. Numeric records retain all protein/diffusion buffers, controls,
component time/call count and source/successor streams. Native records include
all 624 MT19937 words, position and Gaussian cache bits; stable records preserve
their original seed and owner coordinates. Supplied values and successor words
remain the packet provider's responsibility: association checks do not regenerate
or authenticate an RNG draw.

SIM performs the original permeability finalisation and guarded protein update.
INIT, fast mode and disabled dynamics/protein preserve their source semantics;
enabled zero-level calls still require a packet and advance its logical tick.
Every proposed call retains its full declared duration. Unresolved stock changes,
underflow or non-advancing clocks refuse without clipping or redistribution.

The public `evaluate` recomputes the proposal and full associated work/drive
admission, checking actual held permeability, geometry and field endpoints.
Raw proposals and failed diagnostics remain available. Trusted internal staging
can separate proposal and admission to bound compilation memory, while checking
the complete supplied source records at that boundary. This introduces no
sampler, field solve, accepted loop, physical driving law or publication path.
[Progress](../PROGRESS.md) distinguishes full NumPy evidence from the staged,
reduced-geometry compiled CPU qualification and future GPU work.

### Real protein packets for array transitions

[`physiology_protein_packet_provider`](../src/cells/core/physiology_protein_packet_provider.py)
connects actual owned random streams to the supplied-packet array contract.
`encode_source` checks complete host ownership and the original phase/clock
preflight without drawing. `provide` uses the qualified sampler and returns the
original source, real packet, full successor stream, encoded packet and proposed
component transition. Publication or a committed tissue loop remains the caller's
responsibility. A refusal retains every proposed object available at the failing
stage and leaves the source unchanged.

Native MT19937 sampling remains on the host, retaining all words, the Gaussian
cache and NumPy-version association. Stable sampling retains the existing
Threefry seed/world/tick/site/owner law. `stable_packet_arrays` supports compiled
array preparation without replacing that law or changing global JAX settings.
The installed runtime and Threefry partitionable setting remain part of the
reproducibility context; a cross-version bitwise promise is not added.

The original SIM/normal/dynamic/protein guard decides whether a packet exists.
Enabled zero amplitude consumes a draw; disabled paths retain their streams.
Batch masking may evaluate stateless counter arithmetic in disabled lanes, but
does not create logical packets or advance their coordinates. Counter and clock
failures retain their exact phase of refusal. Independent integer-arithmetic
sampler replay, CPU compilation and physical endpoint admission are separate
checks recorded in [Progress](../PROGRESS.md). Successful packet preparation
does not establish a committed charged loop, physical noise-driving law or GPU
qualification.

### Atomic component commits across independent worlds

[`physiology_protein_transition_commit`](../src/cells/core/physiology_protein_transition_commit.py)
checks actual provider packets, complete host bindings, field endpoints and the
original transition/declared-work admission before selecting each world's next
component state. Its
[array kernel](../src/cells/numerics/physiology_protein_transition_commit_arrays.py)
selects the complete accepted protein/diffusion/control/stream/time/call record.
A refused world retains every parent bit, including Gaussian cache bits, and
keeps its speculative packet, trial and diagnostics separately. No arithmetic
blend of accepted and refused buffers is used.

`commit_batch` requires homogeneous engine/version contracts and unique explicit
stream/world owners. It detects stale source, foreign binding, changed field,
packet or geometry associations. Native packets remain host-provided. Optional
compiled selections are decoded against complete host admission and the actual
provider/component law; disagreement refuses the affected world. A valid final
counter can be committed without trying its next, overflowing advance.

Ionic state, physical interval acceptance and cumulative decimal work/electrode
ledgers remain caller-owned. This operation commits component records only;
it is not a complete charged-tissue loop. Independent/source, CPU compilation
and failure-isolation results are recorded in [Progress](../PROGRESS.md).

## Post-ion protein updates with a declared energy budget

[`physiology_protein_transition`](../src/cells/core/physiology_protein_transition.py)
adds a post-ion split operator. Its input is an accepted held-protein endpoint
and the exact pre-ion preparation used by that interval. The numeric seed and
endpoint must span one full declared nominal component duration. The complete
held protein, permeability, controls, clocks and RNG must match before the
operator calls the qualified component transition once. Its proposed protein
then affects the full charged field, channels, pumps, ER and fuel rates at the
same ionic endpoint. Ionic stocks and histories remain unchanged by this
instantaneous operation.

`propose` retains the component packet/successor RNG, both full rate endpoints,
strict material balance, ideal protein free-energy change, capacitor change and
electrode work. Electrode work comes from the endpoint charge change, including
protein charge at clamped owners. Their protein remains a finite inventory even
when their ionic bath is maintained. Requested and represented charge changes,
field closure and rounding diagnostics remain explicit.

`accept` requires a `DrivingBudget` with signed external work (positive into the
system), nonnegative dissipated free energy, and a provenance statement. It
checks `ΔG_protein + ΔU_capacitor + D − W_clamp − W_external` against the original
family energy tolerance. It rechecks the packet transformation, stream
association and actual physical endpoints without drawing again. These inputs
are caller declarations: choosing values that balance the equation establishes
consistency, not a measured driving law or an attainable protocol. Nonnegative
`D` is this external-drive model's constraint, not a general theorem about
individual thermal fluctuations. It does not specify calorimetric heat.

```python
from cells.core import physiology_protein_transition as protein_update

# point already covers the complete nominal ionic interval for preparation.
proposal = protein_update.propose(
    spec, point, preparation, loop_index=0,
    standard_concentration_mol_m3=1.0,
)
receipt = protein_update.accept(
    spec, proposal,
    protein_update.DrivingBudget(external_work_pJ, dissipated_free_energy_pJ,
                                protocol_provenance),
)
```

[`physiology_protein_transition_io`](../src/cells/physiology_protein_transition_io.py)
stores the source held checkpoint, preparation and declared-drive receipt in a
new directory, committing its manifest last. Loading replays the saved proposal
from its original RNG and requires the exact packet/component/field/budget
identity; it advances no external state. Failed draws, endpoint checks, budgets
and partial publications retain their evidence. Repeating a pure proposal or
acceptance from the same source is permitted; the future outer state owner must
enforce commitment once.

The receipt is a checked split operator, not a subsequent ionic checkpoint.
The repeated-loop owner below composes the same physical kernels with its own
state and cumulative accounting. Native full-loop comparisons, physical drive
calibration and GPU qualification remain separate.
[Progress](../PROGRESS.md) records the current evidence.

## Repeated charged loops and restart

[`physiology_protein_loop`](../src/cells/core/physiology_protein_loop.py)
owns complete nominal loops with changing protein charge. It keeps the original
ordinary seed and explicitly conditioned starting field, plus the current full
ionic state, protein component, random stream, original-grid cursor and separate
protein driving/dissipation/electrode ledgers. It never turns an evolved charged
state into an ordinary checkpoint or applies the latest protein retrospectively
to the original ionic history. Prior conditioning work remains outside the
declared trajectory.

`propose(spec, point)` prepares permeability without drawing, completes every
original-grid ionic interval using the held charged RHS, and only then calls
the protein component once. Original scheduled controls, stage/turnover limits,
local material and energy checks, and right-continuous endpoints remain active.
`accept(spec, point, proposal, budget)` requires that exact current parent,
rechecks the deterministic ionic path and prescribed protein transformation
without another draw, and accepts the caller's explicit `DrivingBudget` only
when both local and cumulative conservation pass. Rejected attempts retain
completed ionic trials, available failed state, packet and successor RNG.

The cumulative check independently recomputes origin-to-current ionic, ER,
fuel, protein and capacitor energy changes. Numeric heat and work histories
remain in their original state arrays. Protein external work, declared
free-energy dissipation, clamp work and per-reservoir electrode charge use
Decimal sums of their recorded float inputs. This preserves small additions
to large totals; it does not make underlying measurements or float64 numeric
histories exact. The global energy limit is the original family limit, with
no multiplication by loop count. Per-reservoir charge and clamp work are also
checked, retaining fixed boundary voltages. Finite fuel uses its pool energy
and regeneration supply; internal pump work is not counted again as external
energy.

```python
from cells.core import physiology_protein_loop as loops
from cells.physiology_protein_loop_io import (
    load_protein_loop_checkpoint, write_protein_loop_checkpoint,
)

point = loops.initialise(
    spec, ordinary_seed, tissue_binding, charge_reference, component,
    protein_species_id="protein", valence=-1,
    standard_concentration_mol_m3=1.0,
)
proposal = loops.propose(spec, point)
receipt = loops.accept(spec, point, proposal, declared_budget)
point = receipt.checkpoint
write_protein_loop_checkpoint(path, spec, point)
saved = load_protein_loop_checkpoint(path)
next_proposal = loops.propose(saved.spec, saved.checkpoint)
```

The distinct `cells.charged_protein_loop_restart@1` format validates the origin,
current component/RNG, complete numeric state, cursor and aggregate conservation
on save/load. Payloads precede the final manifest; partial or inconsistent
bundles cannot load. Restart does not replay every previous RK stage or prove
the authorship of historical work declarations. Keep each returned proposal,
budget and receipt in the run journal: the compact checkpoint carries totals
and a rolling association hash, not an ever-growing archive of old states.
Passing a stale proposal against the new current point fails; pure replay from
an unchanged old immutable point remains possible.

This host owner fixes the original geometry, protein species/valence,
thermodynamic frame and component controls. Optional permeability programs are
described below. Component removal, native complete-loop parity, calibrated
protein driving laws and GPU execution remain separate work. These limits and
numerical qualification results are tracked in [Progress](../PROGRESS.md).

### Scheduled permeability in charged loops

[`physiology_permeability_schedule`](../src/cells/core/physiology_permeability_schedule.py)
binds an explicit intervention program to the original specification, tissue
owners, initial component and nominal loop clock. `BufferChange` replaces the
complete scheduled diffusion modifier in m2/s from its declared loop onward.
Indices must identify exact original-grid boundaries with a following complete
nominal interval; duplicate, reversed and unreachable rows refuse.

```python
from cells.core import physiology_permeability_schedule as schedules

program = schedules.bind(
    spec, tissue_binding, component,
    changes=(schedules.BufferChange(
        1, replacement_modifier_m2_s, "Declared intervention protocol",
    ),),
)
point = loops.initialise(
    spec, ordinary_seed, tissue_binding, charge_reference, component,
    protein_species_id="protein", valence=-1,
    standard_concentration_mol_m3=1.0, schedule=program,
)
```

`MembranePulse` supplies the pinned BETSE logistic pulse shape with explicit ion
and membrane IDs, onset/off/transition times, multiplier, spatial factors,
constant dynamic amplitude and tissue-default diffusion coefficient. An optional
`time_modulator` supplies a recorded periodic or sweep factor, described below.
Pulses
overwrite targeted modifier entries; untargeted entries retain the latest
complete buffer. Overlapping pulse writes refuse. Other native dynamic
modulators, configuration parsing, tissue selection and other event families
are not supplied by this adapter.

Each SIM proposal samples the program at the **Cells nominal loop start**,
updates only the scheduled buffer, then performs the existing `base + scheduled`
finalization before ionic work. It samples no random values and advances no
clock. Subdividing tissue steps does not resample component events. INIT retains
its original component buffers. The accepted endpoint retains the settings
used by its completed loop; the next proposal applies any change due there.
Native `linspace` labels are not treated as equivalent to this calendar.
An explicit native calendar can be bound instead, as described below; the
default program identity and nominal-clock record remain distinct.

The actual charged field is rechecked when permeability changes. A kinetic
parameter intervention must not introduce a stored capacitor-energy change or
an electrode impulse beyond existing numerical limits. This does not model the
physical energy cost of an actuator. Current permeability must preserve the
original route support and pass the original domain/turnover checks. Invalid
future modifiers leave the last accepted point and RNG intact when attempted;
no clipping or automatic repair is performed.

Scheduled checkpoints use `cells.charged_protein_loop_restart@2`, with the full
program in a hashed `schedule.json` payload. Source/component/clock association,
the last accepted modifier and future plan are checked on restart. Unscheduled
checkpoints retain their separate existing format. Seals establish association,
not authorship of a deliberately rewritten history. Pinned native arithmetic
comparisons and coupled-trajectory qualification are distinguished in
[Progress](../PROGRESS.md).

### Native phase labels and elapsed call boundaries

[`physiology_native_calendar`](../src/cells/core/physiology_native_calendar.py)
prepares the pinned BETSE phase calendar explicitly. For `N > 1`, its event
labels run from zero through `N*dt` in `N` calls, while every update still uses
`dt`. A one-call phase has label zero and advances a full `dt`. Sampled source
labels describe observations after a call; they are not generally the elapsed
endpoints of those observations. INIT disables event dispatch in both captured
normal and fast solver guards. This does not implement either solver.

```python
from cells.core import physiology_native_calendar as calendars

calendar = calendars.bind(
    phase="SIM", step_count=100, dt_s=0.001, sample_stride=10,
    provenance="Declared pinned-BETSE comparison phase",
)
prepared = calendars.window(calendar, start=40)  # retain the original 100 calls
# Separate columns: event_label_s, elapsed_start_s, elapsed_end_s, duration_s.
saved = calendars.record(calendar)
restored = calendars.restore(saved, expected_identity=calendar.identity)
```

`from_duration` preserves the native configuration's `int(total/dt)` conversion,
including binary64 rounding near integers: `0.3 / 0.1` produces two calls in
that conversion. The preparation bound is one million calls. Sampling retains
the source's repeated addition and integer truncation, including noninteger
strides; strides below one refuse because the source loop would not progress.
An empty phase is representable calendar data, not an evolved trajectory.

Saved records retain the complete original phase and its identity. A resumed
window slices that phase; constructing a new calendar from the remaining call
count would change event labels. Read-only host arrays are preparation inputs;
the caller must separately associate accepted tissue state and loop cursor.
The schedule adapter accepts this calendar explicitly:

```python
program = schedules.bind(
    spec, tissue_binding, component,
    changes=recorded_buffer_changes, pulses=membrane_pulses,
    native_calendar=calendar,
)
```

This option requires a nonempty native phase beginning at nominal loop zero,
with the component's exact phase and duration, and a final elapsed boundary
within the original numerical grid. Complete buffer changes still use explicit
call indices; membrane pulses use the source event labels. Only event sampling
changes: ionic substeps use elapsed time and the component advances its original
fixed duration once per call. The staging receipt records both clocks and the
calendar identity. INIT retains its event guard, and this option does not turn
the existing physical solver into BETSE's fast equivalent-circuit solver.

Native programs use the separate `cells.native_label_permeability_schedule@1`
identity inside the existing scheduled checkpoint's hashed `schedule.json`.
Restoring a mid-phase checkpoint retains the original full count, never a new
calendar made from the remaining calls. A terminal checkpoint remains valid and
loadable; another proposal refuses during preparation, before ionic work or
random draws. The small immutable host label cache holds no advancing state.
Native complete-solver evolution, general configuration import and GPU scheduling
remain outside this implementation. [Progress](../PROGRESS.md) distinguishes
standalone source-site checks from the separately recorded coupled qualification.

### Periodic and frequency-sweep time factors

[`betse_time_modulation`](../src/cells/processes/betse_time_modulation.py)
implements the pinned `periodic` and `f_sweep` component expressions:
`sin(pi*t*f + phase)^2` and `sin(pi*(slope*t + start)*t)^2`. The sweep retains
that source polynomial; it does not substitute an integrated-frequency chirp
with a different coefficient. Signed finite coefficients are preserved.

```python
import numpy as np
from cells.processes import betse_time_modulation as modulation

program = modulation.sweep_program(
    start_Hz=0.2, stop_Hz=0.8, original_duration_s=0.3,
    provenance="Declared native frequency-sweep intervention",
)
values = modulation.evaluate(program, np.asarray(event_labels_s, dtype=np.float64), xp=np)
```

Automatic slope preparation preserves `(stop - start) / original_duration`,
including source floating operation order. The unresolved native automatic
slope outside SIM is refused explicitly. An explicit slope is also supported.
The complete coefficients and original duration are recorded with the program;
restart checks its original identity and does not recompute from remaining time.
These records check association, not authorship of deliberately resealed inputs.

The `periodic` and `sweep` array kernels accept broadcast float64 time/coefficient
arrays using NumPy or JAX. They return the factor, computed phase and a per-sample
finite-arithmetic flag, including checks on source intermediates. That flag
does not certify phase accuracy for very large or cancelling arguments. Raw
values are not clipped or repaired. The caller chooses the clock and retains
intervention ownership, numerical tolerances and physical admission.

The schedule adapter accepts a prepared program in `MembranePulse.time_modulator`.
At each enabled event call, the pulse uses
`spatial_scalar * (dynamic_scale * factor(t)) * pulse(t)` in source order.
The existing nominal or native calendar chooses `t`; fixed ionic and component
update durations do not change. INIT does not evaluate disabled event factors.

For an automatic sweep, binding checks the original SIM duration. With a native
calendar this is its requested duration when recorded, otherwise its full
`N*dt`; with the nominal clock it is the original numerical horizon. A restart
never substitutes the remaining duration. Explicit slopes remain independently
declared coefficients. A nonfinite factor refuses during preparation, preserving
the last accepted checkpoint and RNG. Finite arithmetic alone does not establish
accuracy or biological meaning at extreme phases.

Schedules containing these programs use `cells.modulated_permeability_schedule@1`
inside the scheduled restart's existing hashed payload. Complete nested program
and calendar identities are retained. Constant-only schedules keep their prior
record formats. Scalar source comparisons and compiled CPU JAX component checks
are distinct from the coupled qualification in [Progress](../PROGRESS.md).
No GPU execution, new actuator-energy law or biological calibration is implied.

### Spatial intervention gradients

[`betse_spatial_modulation`](../src/cells/processes/betse_spatial_modulation.py)
provides the pinned `gradient_x`, `gradient_y` and `gradient_r` factors. A prepared
program records the complete ordered cell and membrane owners, their coordinates
in metres, the centre, targets, coefficients and provenance. Saving/restoring a
program checks all of these against its original identity. An identity checks
association; it does not authenticate deliberately rewritten inputs.

For x/y gradients, BETSE chooses the coordinate array by **target count**, then
normalizes the entire chosen geometry. It ignores the target index values when
computing that full output. Membrane count wins a tie. Binding refuses a declared
domain that this source rule would misinterpret, and refuses lengths that leave
the source coordinate array undefined. The normalized coordinate `u` gives
`a = (u / (0.5 + x_offset))**exponent`, followed by
`a / (1 + a) * slope + z_offset`. The parameter is called `x_offset` for both
axes and is dimensionless.

The radial law uses actual membrane targets and returns the complete membrane
axis. Its source `x_offset`, in metres, shifts **both x and y** relative to the
declared centre. Unselected membranes have zero radius before normalization and
therefore receive `z_offset` afterwards. The array kernel retains source square,
sum and square-root order, including overflow; it does not substitute `hypot`.

Pure `axis` and `radial` kernels accept float64 NumPy/JAX arrays with leading
world axes and return factors, normalization length and finite-arithmetic flags.
Signed and out-of-range factors are preserved. Degenerate geometry, undefined
powers and nonfinite arithmetic remain explicit; the consumer must enforce its
own physical domain. Finite flags do not certify arbitrary-exponent accuracy.
`MembranePulse.spatial_modulator` attaches a prepared program to a charged-loop
intervention. Set `spatial_scalar=None` when constructing the pulse: binding
computes the complete factor tuple and saves it beside the program. On restore,
the original owners, coefficients, coordinates and stored factors are rechecked.
The distinct `cells.spatial_permeability_schedule@1` identity lives inside the
existing hashed schedule payload. Schedules without a spatial program retain
their earlier record formats.

This adapter requires **all bound membranes in their original component order**,
including exact program target order and complete cell/membrane owner axes.
BETSE assigns the full output array positionally to its target list; a partial
radial selection can fail on shape, and reordered targets would reassign factors
to different owners. The adapter refuses these cases. All spatial programs in
one schedule must share a coordinate frame. The ordinary tissue graph supplies
volumes, areas and contacts, but no embedding: stimulation coordinates are
declared inputs, not a reconstructed physical mesh.

Staging uses the already checked factor tuple without evaluating geometry or
drawing randomness. SIM guards, both existing event clocks, fixed update
durations and physical domain/conservation checks remain unchanged. An optional
time modulator multiplies the spatial factor in the established pulse expression.
This is an explicit composition of source components; native configuration's
single callback slot does not establish native support for that combined setup.
Geometry association and numerical validation are distinct from arbitrary-phase
accuracy, intervention actuator work and biological calibration. Coupled results,
bitmap callbacks and GPU qualification are tracked separately in
[Progress](../PROGRESS.md).

### Global control setters

[`betse_global_controls`](../src/cells/processes/betse_global_controls.py) implements
the pinned temperature, gap-junction block, Na/K pump block and directed boundary
voltage setters. `bind` records explicit membrane owners and at most one `Event`
of each kind; `compile_program` produces immutable numeric parameters for the
float64 `apply` kernel. `State` contains temperature in kelvin, the native
membrane-indexed junction availability, scalar pump availability and boundary
voltages ordered top/bottom/left/right. The junction array does not identify
physical intercellular edges without a separate owner mapping.

```python
from cells.processes import betse_global_controls as global_controls

program = global_controls.bind(
    membrane_ids=("membrane_0", "membrane_1"),
    events=(global_controls.Event(
        "junction_block", on_s=0.2, off_s=1.2, change_s=0.3,
        target_ids=("membrane_1",),
    ),),
    provenance="Explicit intervention and target owners",
)
kernel = global_controls.compile_program(program)
# Supply a complete State, explicit event time, original temperature and enable flag.
result = global_controls.apply(state, kernel, time_s, original_temperature_K, enabled)
```

Temperature uses `multiplier * pulse(t) * original_temperature_K +
original_temperature_K`, so repeated calls do not accumulate a change on the
previous temperature. Both blockers assign `1 - pulse(t)` rather than multiply
the previous availability. Unselected junction entries remain unchanged. Voltage
assigns `peak * pulse(t)` to the positive side and `-peak * pulse(t)` to the
negative side; the second write wins when both names select the same boundary.
Untouched sides retain their existing values. Equal pulse onset/offset is allowed
and still performs the source's zero-valued writes.

The native logistic expression and operation ordering are retained. Exponential
overflow with a finite argument can produce a finite saturated sigmoid; this has
its own diagnostic. Nonfinite arguments, coefficients and setter results fail
the finite-arithmetic check. A separate control-domain check requires positive
kelvin values and availability fractions in `[0, 1]`; raw source results are
never clipped. Disabled calls preserve state even when unused numeric inputs
are invalid, while array shape and dtype requirements still apply. The kernel
supports CPU/JAX compilation and `vmap` over complete independent worlds.

The caller supplies the event clock and phase enable flag. Targets are explicit;
this component does not reproduce the global junction initializer's unused
shuffle or consume its RNG stream. The existing native-prefix selector remains
separate. Program records preserve owner/coefficient association across restore,
but do not authenticate deliberately rewritten inputs. Numerical setter checks
do not establish tissue evolution: coupling temperature or boundary voltage
changes requires explicit thermal/electrode work and updated physical owners.
[Progress](../PROGRESS.md) records source, independent and execution evidence.

### Applying boundary voltage to complete tissue rates

[`physiology_boundary_voltage`](../src/cells/core/physiology_boundary_voltage.py)
binds the native top/bottom/left/right sides to explicitly named physical
reservoirs. A side may have several owners; a corner shared by different sides
must receive consistent voltages. Empty sides cannot be driven. Unmapped
reservoirs retain their original potential, and a finite exterior compartment
or gauge is never silently converted into an electrode. The source's ordered
positive/negative writes on the same side remain distinct from corner conflicts.

The [complete rate view](../src/cells/models/physiology_boundary_voltage_view.py)
checks the original source history, then changes only the temporary clamp
voltage array. It retains full ionic/calcium/fuel rates, physical field closure,
controls, charge/capacitance anchors and unchanged numerical/turnover limits.
Changed clamps are admitted for `resolved_tissue@1`, `resolved_tissue@12`,
`resolved_open_calcium@1` and `resolved_open_calcium_energy@1`. The finite-only
`resolved_calcium@11` and `resolved_calcium_energy@5` retain their existing
reservoir prohibition and gauge semantics; their no-event/refusal checks do not
count as changed-clamp coverage.

Frozen-inventory endpoint diagnostics report capacitor energy and electrode
charge changes, plus conditional work for an ideal linear capacitive ramp.
That path is an explicit physical assumption, not a voltage transition supplied
by BETSE. The adapter accepts no voltage jump, advances no clock, updates no
ledger and publishes no ordinary checkpoint with changed anchors. Temperature
changes, accepted voltage trajectories and GPU execution remain separate.
Actual source, independent-field and software evidence is recorded in
[Progress](../PROGRESS.md).

### Applying held temperature to complete tissue rates

[`physiology_temperature`](../src/cells/core/physiology_temperature.py) binds
native temperature setters to the actual cell, environment, membrane, junction,
face, channel, store and fuel-pool owners. `bind` requires a temperature-only
program and complete ordered owners; `record`/`restore` preserve that association.
`prepare` retains the event clock separately from physical time and applies the
source multiplier to the original temperature in kelvin. Invalid native proposals
remain available on a refused trial.

The [complete temperature view](../src/cells/models/physiology_temperature_view.py)
checks the source state under its original definition, then evaluates the full
passive field, transport rates and reservoir powers at held temperature. It keeps
the original anchors, inventories, controls, histories and clocks; neither a new
accepted checkpoint nor elapsed changed-temperature evolution is produced.
Original domain, turnover, field and stage-energy bounds remain in force.

Changed temperature is supported for passive `resolved_tissue@1`. The five
reviewed active ionic/calcium/fuel identities retain their declared 298.15 K
restriction, including empty or blocked channel populations. Their identity
checks are separate from changed-temperature passive coverage. The
[`inventory` function](../src/cells/core/physiology_temperature.py) lists parameter
roles and missing thermal assumptions; it does not invent a common Q10 or
activation-energy law for the channel, pump, ER and fuel systems.

At fixed inventories, the passive view reports the algebraic change in the
ideal isothermal mixing Gibbs functional for actual cells and finite exterior
owners; ideal-reservoir reference inventories are excluded. This diagnostic is
not heat, caloric internal energy or an accepted thermal transition. Physical
thermal evolution needs separately declared thermodynamics. Numerical/source
comparisons and qualification limits are recorded in [Progress](../PROGRESS.md).

The [native active-temperature investigation](../agent-work/cells-specialist/ACTIVE_TEMPERATURE_POLICY.md)
and [executable source probes](../validation/temperature/protocol.json) distinguish
runtime temperature from configured constants. In the pinned source, isolated
channel class curves retain fixed empirical coefficients; legacy calcium-K
opening explicitly uses temperature. The actual gap-junction caller uses
configured `p.T` even when the global setter changes runtime `sim.T`. Reaction
equilibrium and the Na/K versus calcium-pump standard-state conventions also
need explicit treatment. These component probes do not establish uniform
temperature behavior of a complete native simulation.

### Explicit active-temperature rate contract

[`physiology_active_temperature`](../src/cells/core/physiology_active_temperature.py)
requires the explicit policy `active_uniform_isothermal_fixed_empirical_kinetics@1`
and complete ordered physical owners. Its
[rate view](../src/cells/models/physiology_active_temperature_view.py) accepts
source states belonging to the five reviewed active identities at their original
298.15 K. It checks the original history and layout first, then evaluates a
private coefficient projection under the held temperature. It returns complete
ionic, gate, ER, finite-pool and reservoir rates and physical field quantities;
the projection is never returned as a parsed ordinary specification or accepted
changed-temperature checkpoint.

The policy uses coherent SI constants and a uniform held temperature while
keeping empirical curves, rate coefficients, pump capacities and geometric
parameters fixed. Legacy calcium-K still reads temperature. ER reference
standard coefficients remain fixed in J/mol, so their dimensionless values
scale as `298.15/T`; reaction differences follow their declared stoichiometry.
Finite shared fuel applies the live `-R*T*ln(1000)` conversion to its calcium
pumps. Maintained pumps retain their distinct declared 1 M or numeric-mM
standards. Cached drives are recomputed consistently; original anchors and
accumulated histories remain unchanged.

This is an explicit computational convention, distinct from the native
configured/runtime temperature split. The existing 200–400 K process domain
and all physical, gate, loss, gross-turnover and stage-energy checks still
apply; that domain is not a claim of biological calibration or exhaustive
qualification. No Q10, reaction enthalpy, heat capacity or heat law is inferred.
The [contract note](../agent-work/cells-specialist/ACTIVE_TEMPERATURE_CONTRACT.md)
details these assumptions; [Progress](../PROGRESS.md) records tested regimes,
source comparisons and execution limits.

### Combining temperature, voltage and blocker readouts

[`physiology_global_control_view`](../src/cells/core/physiology_global_control_view.py)
binds one native setter program to complete physical owners, explicit boundary
reservoirs and exclusive junction membrane pairs. Its
[complete rate view](../src/cells/models/physiology_global_control_view.py)
requires the original complete checkpoint and the explicit held-temperature
policy above. It applies temperature, junction block, Na/K pump block and
voltage in source order, then evaluates the complete coupled rates and field.
Junction factors multiply the supplied baseline once. Na/K blocking does not
silently block plasma or ER calcium pumps.

The original history, charge anchors and accepted physical clock are checked
before projection. `event_time_s` remains an explicit setter label; it is not
inferred from physical time. Finite-exterior models retain their voltage
restrictions, and all original and projected domain/step checks apply.
Restored device arrays are normalized at the host boundary. This composes held
readouts across the six supported families; it does not accept a temperature
jump, evolve a changed-temperature trajectory or invent heat accounting.
[Progress](../PROGRESS.md) links the combined comparisons separately from each
standalone control's evidence.

### Applying blockers to ordinary tissue rates

[`physiology_block_control_view`](../src/cells/models/physiology_block_control_view.py)
connects junction and Na/K pump blockers to complete passive, ionic, calcium and
finite-fuel readouts. `bind` requires an explicit membrane pair for every actual
junction, with the first membrane owned by its sender cell and the second by
its receiver. Each membrane belongs to at most one pair. These declarations map
control owners; they do not reconstruct a geometric contact mesh.

`prepare` applies the source setters to a complete `BlockState`, then maps the
membrane factors to junction controls. Both sides must agree exactly. An
asymmetric source result remains available on the rejected trial; the adapter
does not average it into a physical edge. The pump factor requires actual Na/K
pump owners even when carried into a disabled event call. Calcium pumps, ER
controls, channels and fuel regeneration retain their original values.

Global factors multiply the caller's original held control packet once. Repeated
calls must keep supplying that original baseline, not a previously multiplied
packet. The caller supplies the explicit event label and enable flag; this API
does not select them from a simulation clock. `evaluate` then reuses the complete
permeability view with current component diffusion, original field/current and
domain checks, and unchanged step and turnover limits.

No component state, RNG or clock advances. Temperature/voltage programs refuse
pending their thermal/electrode accounting. [Progress](../PROGRESS.md) records
initial and evolved numerical readout comparisons separately from the accepted
interval qualification below and future actuator-work accounting.

### Blocker controls in arrays

[`physiology_block_control_arrays`](../src/cells/numerics/physiology_block_control_arrays.py)
maps the same complete blocker state onto ordinary control packets using NumPy
or JAX arrays. `compile_kernel(spec, tissue_binding, binding)` checks actual
contact owners and produces immutable numeric maps. Recompile from the saved
host binding after restore; numeric arrays do not authenticate a rewritten graph.

`apply(state, base_control, kernel, time_s, events_enabled)` returns the proposed
complete control packet, raw source-setter results and per-world diagnostics.
It checks original and effective control domains, explicit owner indices,
exclusive paired membranes, matching junction factors and actual Na/K owners.
The original model forbids contacts joining a cell to itself; host compilation
and the array checks both retain that rule. Empty junction sets and padded
control slots remain representable. Calcium pumps, ER controls, channel controls
and fuel regeneration pass through unchanged.

Use `jax.vmap` for independent worlds with matching model types and array shapes.
The map can be shared as a host-compiled constant or passed separately for each
world. Baseline controls, event times and enable flags may vary across the batch.
Safe speculative gathers return invalid diagnostics for bad indices without
changing the input map or contaminating another world. Contact exclusivity uses
counts over the membrane axis rather than a quadratic matrix of contact pairs.

Supply the original held baseline on every call and require `result.valid`
before considering a proposal. Physical field, material/energy, step acceptance,
RNG ownership and clock selection remain separate checks. This array kernel is
not yet wired into the accepted-step path below. [Progress](../PROGRESS.md)
records NumPy and compiled CPU JAX evidence separately from future GPU runs and
end-to-end performance measurements.

### Accepted intervals with held blockers

[`physiology_block_control_step`](../src/cells/core/physiology_block_control_step.py)
adds an explicit ordinary-grid policy to the rate view. `initialise` binds an
accepted ordinary checkpoint, complete component state, blocker binding and
carried blocker buffer. It performs no event call. `advance` applies the setters
once at the next interval's **left physical-time label**, then holds their
result through all RK stages. Original scheduled controls still change at their
original grid boundaries. The right endpoint uses those right-continuous
controls with the carried blocker factors; the next blocker call belongs to
the next interval. This policy is saved explicitly and is distinct from the
native physiological event calendar.

The step retains all ionic, calcium, ER, fuel, charge, transfer and work fields.
Original stage-domain, field, turnover, balance, energy and history checks run
before the new numeric endpoint and block buffer are accepted together.
Conductance/capacity changes do not reassign inventories, geometry, capacitance
or voltage boundaries. The model contains no drug-delivery or other blocker
actuator cost; accepting its internal energy accounting does not establish
that missing physical driving law.

[`physiology_block_checkpoint`](../src/cells/physiology_block_checkpoint.py)
saves the complete association around the existing tissue/component snapshot.
It preserves the program, contact owners, carried factors, enable flag, original
interval origin, complete RNG state and source/runtime pins. Publication commits
the outer manifest last. Failed numerical attempts preserve the prior checkpoint
and their raw trial without publishing a destination. Restoring a pre-event
checkpoint does not fire a future event that may refuse.

Protein, diffusion, component elapsed time and random draw counters remain held.
The caller supplies the expected tissue binding when loading or advancing a
saved checkpoint. This interval primitive does not implement charged-protein
loops or GPU execution. The controller below owns native clock integration.
[Progress](../PROGRESS.md) records
the current qualification and its numerical scope.

### Native-calendar blocker calls

[`physiology_block_calendar`](../src/cells/core/physiology_block_calendar.py)
associates the blocker checkpoint with a complete original
[`NativePhaseCalendar`](../src/cells/core/physiology_native_calendar.py).
For `N` calls, BETSE's event labels span `0` through `N * dt` in `N` samples;
the physical call still advances from `k * dt` to `(k + 1) * dt`. The controller
never substitutes the difference between event labels for elapsed duration.
Its receipt records the source label, declared duration and actual physical
endpoints separately. A one-call phase has label zero. Empty phases are calendar
inputs but cannot initialise physical blocker execution.

Only the outer controller enables global setters: once per SIM call, at its
native label. INIT preserves the carried blocker factors. Internal interval
calls disable setters, holding those factors while original physical controls
change at their own grid boundaries. Every original interval retains the
existing RK, field, domain, turnover, material and energy checks. The requested
call must end exactly on the original grid before any event fires. An accepted
endpoint remains valid if a later, unrequested call would be off-grid or its
event would fail.

[`physiology_block_calendar_io`](../src/cells/physiology_block_calendar_io.py)
saves the original calendar and accepted call cursor around the complete bound
blocker snapshot. It preserves the original phase length on restart; replacing
it with the remaining call count would change event labels. Publication writes
the outer manifest last, retains source/runtime pins and refuses existing
destinations. Failure retains the original parent, the raw failed setter or
interval and any completed speculative intervals. None of those partial results
is published as a completed call.

The component's declared phase and duration must agree with the calendar;
protein, diffusion, component elapsed time and RNG remain held. This is a
blocker controller for ordinary Cells integration, not a native ionic solver,
post-ion component loop, observation scheduler or GPU execution path. The
[independent reference](../validation/tissue/physiology_block_calendar_reference.py)
uses rational labels, independent scalar setters and complete DOP853 states
carried from the initial condition. [Progress](../PROGRESS.md) records numerical
qualification separately from biological-duration or source whole-loop claims.

## Cell removal and surviving owners

[`remap_component(state, old_binding, new_binding)`](../src/cells/core/physiology_perturbation_remap.py)
returns the surviving component state, an immutable removal archive and
diagnostics. It reuses the existing cell-cut ownership and quantity contract.
Every surviving cell keeps all its membranes; environment and ion owner sets
remain complete. All four owner axes may be reordered explicitly. Surviving
areas, cell volumes, environment effective volumes, numeric precision and
environment mode must match exactly. New wound membranes, geometry changes,
environment mixing/removal and a terminal empty component require separate
adapters. A mixed-bath cut that changes effective volume is refused.

All six survivor buffers are copied by owner ID, including the pre-noise base,
pending signed modifiers and existing membrane concentration views. Controls,
component time/count and random-stream coordinates/cache remain unchanged;
the stream binds explicitly to the new layout without drawing or initializing.
The next native draw follows the preserved sequential tape on the new axes.
Stable sampling retains its owner-coordinate law at the preserved tick.

The removal archive retains the old cell/membrane IDs, ion order, all removed
buffer values and their geometry measures. Removed protein amount is cell
concentration times cell volume. The unchanged environment inventory remains
with the survivor. Membrane views are archived without adding another material
inventory. Diagnostics report previous, retained and removed amounts, an exact
owner-partition residual and the explicit sink policy: removed cell protein
leaves this simulated subsystem. Physical release into an extracellular
compartment would need its own conservative operation.

The returned survivor can be saved with the complete paired checkpoint below,
using `new_binding`. Restore with that binding before advancing it. Keep the
removal archive and cut provenance separately: this checkpoint saves the
surviving state and stream, not earlier cut histories. Numerical tissue geometry,
field rebuilding and joint coupling to the physiological component remain
separate responsibilities.

## Paired checkpoint formats

The paired checkpoint saves a complete ordinary Cells numeric snapshot and a
stream record together. Passing `component_state` additionally saves all six
material buffers, controls and the component clock; its stream must agree
exactly with the supplied stream. The final manifest binds their identities,
specification, numeric clock, stream/world/layout, logical counter and every
payload hash. It uses a new output directory, syncs payloads before publishing
the final manifest, preserves failed publication evidence, and refuses
incomplete, mixed or modified payloads on restoration. Existing source/runtime
compatibility and physical checkpoint checks remain in force.

```python
from cells.physiology_checkpoint import (
    load_physiology_checkpoint,
    write_physiology_checkpoint,
)

# The caller defines the association between these accepted states.
write_physiology_checkpoint(
    path, spec, checkpoint, component.stream, binding, component_state=component,
)
saved = load_physiology_checkpoint(
    path, binding, expected_stream_id="physiology", expected_world_id=world_id,
    require_component=True,
)
checkpoint = saved.snapshot.checkpoint
stream = saved.stream
component = saved.component_state
```

Without `component_state`, the writer retains the RNG-only outer format
`cells.physiology_random_checkpoint@1`. Supplying it selects
`cells.physiology_perturbation_checkpoint@2`, including `component.json`.
The loader retains both formats; `require_component=True` refuses RNG-only
records rather than rebuilding absent material buffers or drawing again.

Passing `tissue_binding` also selects `cells.physiology_tissue_checkpoint@3`,
which requires complete component state and adds `binding.json`. The binding
must agree with both the component layout and the saved numeric specification.
The same final manifest binds its identity and payload hash. Restoration always
replays a saved tissue binding, even when the caller supplies no expected one:

```python
write_physiology_checkpoint(
    path, spec, checkpoint, component.stream, tissue_binding.component,
    component_state=component, tissue_binding=tissue_binding,
)
saved = load_physiology_checkpoint(
    path, tissue_binding.component, require_tissue_binding=True,
)
restored_binding = saved.tissue_binding
```

`require_tissue_binding=True` refuses either older unbound format. An optional
`tissue_binding=...` on loading additionally checks the caller's exact expected
binding. Mixed component/binding/specification records refuse even if outer
payload hashes are recomputed. These checks preserve pending signed modifiers
and existing static initialization values without redrawing or finalizing them.
The current tissue adapter covers ordinary owners; it does not yet bind the
specialized post-cut model families.

Passing `loop_cursor` additionally selects
`cells.physiology_tissue_loop_checkpoint@4`, requiring both complete component
state and tissue binding and adding `loop.json`. Its identity seals the full
numeric state/layout, component buffers/controls/random state, specification,
binding and independent clocks. The loader always validates the saved cursor
against the restored pair, even without a caller expectation.
`require_loop_cursor=True` refuses older unmanaged formats; `loop_cursor=...`
also checks an exact expected cursor. Rehashing a wrong association does not
make it valid. These hashes detect changes; they do not authenticate authors.

The numerical clock, accumulated component time, loop count and draw counter
are distinct. The component's time measures accumulated explicit calls and
need not equal the deterministic snapshot time. The older formats record their
association without imposing a loop schedule; version 4 enforces the explicit
whole-loop contract above. Restart checks establish exact continuation of
saved state and random draws. Trajectory accuracy and biological calibration
require separate evidence, recorded in [Progress](../PROGRESS.md).

Use the paired loader to restore every saved object. Loading the inner
deterministic snapshot alone restores only numeric state and does not recover
the material component or its random stream. The format is portable, but
source/runtime migration and a CPU-to-GPU restart require their own execution
qualification.
