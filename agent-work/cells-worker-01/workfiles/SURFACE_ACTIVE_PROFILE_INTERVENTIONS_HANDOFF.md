# Scheduled regional background membranes on complete active tissue

The standalone model is `resolved_active_membrane_profiles@1`, with
`SurfaceActiveProfileInterventionModel` in
`cells.core.surface_active_profile_interventions_spec` and runtime hooks in
`cells.models.surface_active_profile_interventions`. The Chief owns shared
parse/serialization/registry/ensemble integration and shared status. This worker
changes only new owned files; the passive scheduled model, phase-handoff model,
active parent and numerical engines remain frozen.

## Physical and source contract

The physical owner is exactly `resolved_tissue@12`: the complete 56-law shared
Na/K/Cl/Ca catalog, its actual zero/one/two-state gate slots and channel owners,
intrinsic junction gates, maintained ATP/ADP/Pi pumps, finite exterior/reservoir
owners and all nineteen state fields. A new one-entry phase clock makes twenty
state fields. Background permeability changes do not scale channel conductance,
reset intrinsic gates or reset pump/transfer/work/dissipation history.

The source is a complete qualified direct static profile
`{definition, provenance}` artifact for @12, including explicit SI thickness,
native layout order, stable owners and the full preparation recipe. Replaying
that artifact must reproduce the entire physical model, including every gate,
pump and channel declaration. Other families, cuts, remaps and changed physical
owners are refused. The actual parent layout is reconstructed as its exact
HCN_EXTRA type before every parent call; layout type selects the complete law
catalog and its instantaneous calcium and Morris–Lecar state contracts.

Native regional events modify only the background membrane diffusion buffer.
The frozen compiler and signal operator retain one event per Na/K/Cl/Ca kind,
native family order, ordered target profiles, duplicate-last assignment,
default-Dm multipliers and explicit constant sampled spatial/dynamic factors.
Na/K remain unguarded by native ion flags; Cl/Ca retain their native guards.
Those flags govern the scheduled background component, while actual physical
channel and pump owners continue to follow the @12 definition. Total background
diffusion converts through each explicit thickness to permeability. Signed
factors require the unchanged conservative all-time nonnegative-D bound and
actual-stage finite/nonnegative P. Invalid physical coefficients are refused
without clipping or accepting a corrupted trial state.

All four membrane/junction/channel/pump control families retain their complete
clock union and held-input semantics. The phase clock advances at RK stages and
samples the qualified smooth native pulse, including tails. INIT suppresses
only scheduled background effects: full parent gates/pumps continue to evolve.
SIM enables those effects. Fresh phase/reset policies are explicit; ordinary
resume retains phase clock and history and ordinary branch cannot change phase.
This feature does not introduce an INIT-to-SIM physical-state operation.

## Closed-route history and call-graph proof

The unchanged active parent was designed for fixed background routes. Its
`readouts` calls `domain_valid`, which rejects background transfer history on a
route whose current P is zero. A scheduled route can have valid earlier
transfers and later close. The wrapper therefore gives actual history the union
of possible background routes for accounting support only. Actual instantaneous
P always drives physical fields, fluxes and derivatives.

The parent's physical evaluator sees a temporary view that masks only the
closed-route `membrane_transferred` diagnostic integral. No stored state changes.
Pinned function ASTs prove the parent readout accesses physical state only via
`channel_gate`, `junction_gate`, physical amounts and charge increments. Its
field call reaches only amounts and charge increments. The projected integral
reaches only the fixed-route validity check and cannot enter potentials,
physical fluxes, any state/ledger derivative or numerical field diagnostics.

Dynamic closure/reopening tests compare every nonboolean parent readout leaf
between untouched history and the temporary view, bit for bit. The old
fixed-route validity flag intentionally changes; the wrapper's validity uses
the actual complete state with historical route support. Independent full-field
and twenty-field RHS comparisons use evolved actual states through closure and
reopening. Every observed parent state field is restored exactly. Observations
first validate the untouched full history. Material, charge, chemical/capacitor
energy, channel/pump heat, reservoir/electrode work and maintained-fuel work
diagnostics always use actual arrays. A deliberately corrupted closed-route
transfer is refused by both accounting and observation, so a projection cannot
hide an actual material-balance failure. No scientific tolerance is relaxed.

## API and artifacts

The spec module provides `parse`, `to_dict`, `active_spec`, `bindings`, `artifact`
and `replay`. Execution retains the parent channel capacity and adds
`intervention_capacity` and `intervention_target_capacity`. All physical
definitions and both native/physical owner orders remain in the portable
record, with compiled binding and event identities.

```python
import json
from pathlib import Path
from cells.core import surface_active_profile_interventions_spec as scheduled

record = json.loads(Path("examples/SIM/artifact.json").read_text())
spec = scheduled.replay(record)
assert scheduled.parse(scheduled.to_dict(spec)) == spec
```

Exported model definitions retain the complete static recipe and can also be
parsed directly. Shared public loaders and ionic cohorts require the Chief's
proposed integration patch. That patch routes this subtype before the existing
HCN_EXTRA parent dispatch, preserving its own model and checkpoint identity.
The separate test patch applies only to an isolated frozen engine copy.

## Evidence and limits

Independent NumPy/Decimal references accumulate ordered native assignments,
all 56 scalar channel laws, full-node electrical roots, pump kinetics, all
nineteen active derivatives and the stage clock. Additional independent owner
loops reconstruct total channel/pump/background currents and complete physical
power terms. Full-history conservation includes actual channels, pumps and
maintained-fuel work. Cases cover INIT, SIM, disabled native flags, safe signed
events, closure/reopening, empty events and independently reordered owner axes.
Short SIM and closure trajectories receive explicit refinement against segmented
DOP853 with all four held-control families and unchanged active-parent budgets.

CPU JAX coverage is eager complete-catalog RHS parity, abstract tracing of the
twenty-field state and native pulse differentiation. A separate eager public
run checks all laws, actual gate/pump/work history, complete observations and
exact snapshot resume. This component does not qualify a compiled active RHS
or compiled trajectory. CPU7, one thread, at most 1 GiB live process-tree RSS and
at least 8 GiB host reserve apply to every guarded phase; no GPU or long run.

Native correspondence covers pulse/default-Dm/target/buffer arithmetic and
explicit D/thickness. The pinned native `makeAllChanges` adds Dm_scheduled and
Dm_base. Active channel laws and maintained-fuel accounting retain their
separately qualified parent equations. New coupling is checked independently;
no native full-solver, physiological fit or slow-gate settling claim follows.

Calcium-store owners need their full free/bound inventories and owner-specific
energy coupling. Finite-fuel models need actual ATP/ADP/Pi conservation and
reaction work rather than maintained pools. Water/moving geometry needs a
qualified changing-volume/area/thickness and material-history contract. These
families are explicit future boundaries, not passive or @12 projections.
