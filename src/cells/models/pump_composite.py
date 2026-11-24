"""resolved_pump_composite@1: resolved_pump_tissue@3's own step plus declared operators.

Design: docs/CELL_DIVISION_DESIGN.md §3 (D142, D143). Definition:
definitions/pump_composite_spec.py. The inner model's names live only in the entity
adapter (models/pump_composite_adapter.py); operators implement the contract of
operators/contract.py. implementation(inner, laws) builds one object per
inner identity and ordered operator list (cached, so its state, layout and
control types and its step functions are stable jit inputs); registry.get_model
returns it for a composite definition. Object structure lives in that object and
the operators; every step function is pure JAX over arrays.

The step (§3.4), for an IMEX inner step:

    Phi_dt = P1(dt/2) o ... o Pm(dt/2) o I_dt[view] o Pm(dt/2) o ... o P1(dt/2) o E

* E: the operators' event maps at the step start, in declared order;
* P: their split parts on their own variables (the first half in declared order,
  the second in reverse);
* I: the inner model's own checked step at the view of its layout (the
  providers' fields) and control (availabilities times the declared factors),
  behind jax.lax.optimization_barrier on its inputs and outputs, so XLA compiles
  it as one unit; with an active in-step process, the inner IMEX step with that
  process through @3's hook, whose applied transfer and heat the operator books.
  Geometry and every view are frozen inside I.
* Any refused piece refuses the whole step: the start state is returned. Idle
  parts select the inner value and never add a computed zero; branches are static
  (by the operator list and layout shapes), never by value. The empty composition
  is the inner step itself.

RK4 inner steps (reference runs; a contract addition, §3.4 covers the split
form): when an operator's split part is declared "coupled" (water) or an
in-step process is present, RK4 integrates the coupled right-hand side (the inner
readouts at the view, with the process, plus the operators' rates) unsplit, as
resolved_pump_water@1 does; such compositions refuse event maps, split parts kept
"split" and integer state. Otherwise the events and exact half-steps stay around
the inner RK4 step, as resolved_pump_replacement@1 does.

Checks: host and device use the inner model's own row checks
(surface_pump.checked_rows, surface_pump_checks.row_checks, surface_pump.
ledger_limits) on the declared layout, with the inner balances plus the
operators' terms (in declared order), the operators' own ledgers after the inner
ones, the rounding magnitudes with the operators' terms, and the dissipation
fields with the operators' heat. Without operators every check is the inner
model's exactly.
"""

from collections.abc import Mapping
from dataclasses import make_dataclass, replace
from functools import cache, partial
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.pump_composite_spec import MODEL_ID, entries, identity, projection
from cells.definitions.specs import ChannelChange, ConfigError
from cells.execution.errors import NumericalError
from cells.models import pump_composite_adapter as pump3
from cells.models.surface_pump import DOMAIN_MESSAGE
from cells.models.surface_pump_checks import row_checks
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.fixed_step import rk4_checked_step
from cells.operators.contract import (
    COMMUTING,
    HEAT_SUFFIX,
    READ_STAGES,
    WORK_SUFFIX,
    factor_reads,
    monotone_heat,
    part_stages,
    reads_of,
    reports_labels,
    takes_labels,
)
from cells.registry import kind_registry, species_registry

OBSERVER_ID = "resolved_pump_composite_accepted_grid_readouts@1"
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_operator_domains@1"
SPLITTING_ID = "events_then_symmetric_operator_halves@1"
INNERS = {pump3.MODEL_ID: pump3}
# Inner control fields and the experiment schedules that hold them for observation.
HELD_SCHEDULES = dict(
    membrane="membranes",
    junction="junctions",
    channel="channels",
    pump="pumps",
    calcium_pump="calcium_pumps",
)


def _and(a, b):
    """Conjunction of validity flags, where None means nothing to check."""
    if a is None:
        return b
    if b is None:
        return a
    return a & b


def _merged(old, new, *, xp):
    """Two (values, mask) records of one FACTOR_RECORD field, the later taking its own routes
    (B1′); None is no record."""
    if old is None:
        return new
    values, mask = new
    return xp.where(mask, values, old[0]), mask | old[1]


def _recorded(state, records, *, xp):
    """state with each FACTOR_RECORD field set to its routes' applied factors, elsewhere kept
    (B1′'s exact record); unchanged without a record (static)."""
    if not records:
        return state
    return state._replace(
        **{
            field: xp.where(mask, values, getattr(state, field))
            for field, (values, mask) in records.items()
        }
    )


def _checked_above(row, p, active, *, xp):
    """The domain of a row whose actual state was checked beforehand (retirement, S5 §3.5)."""
    return xp.asarray(True)


def implementation(inner_model, laws, structure=None, *, midpoint=frozenset()):
    """The composite for one inner identity, ordered operator law tuple and, from a definition,
    the inner model's declared structure (I2: the composite then takes the inner protocol from
    that structure's implementation object; None keeps the module's own, the full catalogue), and
    the definition's self-moved rate-route targets (self_moved_targets; empty: none).

    Cached: equal arguments share one composition. A structure that declares kinds is also keyed
    on the active kind registry, whose kinds its types are built from (schema A, §7.4 (j)), as
    the inner implementation object is; one that declares none shares its composition across
    registries, so a registered but undeclared kind changes nothing. A definition without a
    self-moved route shares the composition it had before the midpoint existed."""
    kinds = structure is not None and bool(structure.kinds)
    registry = kind_registry.active() if kinds else None
    return _implementation(inner_model, laws, structure, registry, frozenset(midpoint))


@cache
def _implementation(inner_model, laws, structure, registry, midpoint):
    from cells.operators import OPERATORS

    if inner_model not in INNERS:
        raise ConfigError("Composite inner model must be one of " + ", ".join(INNERS))
    unknown = [law for law in laws if law not in OPERATORS]
    if unknown:
        raise ConfigError("Unregistered operator laws: " + ", ".join(unknown))
    inner = INNERS[inner_model]
    if structure is not None:
        inner = inner.for_structure(structure)
    return Composition(inner, tuple(OPERATORS[law] for law in laws), midpoint=midpoint)


def model_for(spec_model):
    inner = INNERS[spec_model.inner_model] if spec_model.inner_model in INNERS else None
    structure = None if inner is None else inner.inner_structure(spec_model)
    return implementation(
        spec_model.inner_model,
        composite_spec.operator_laws(spec_model),
        structure,
        midpoint=self_moved_targets(spec_model),
    )


def self_moved_targets(spec_model):
    """The law IDs of the definition's rate-route targets whose own half-steps move a species
    source of one of their routes, in the cell the route reads it (B1′; the independent Lean
    project's finding, lean/PROGRESS.md "regulated-turnover-routing", 20 November 2026).

    A factor read at the start of a half-step is exact while nothing in that half-step moves its
    source: another split operator's halves and @3's step stand symmetric about it (Strang). When
    the target moves the source itself (a turnover producing the regulator of its own route),
    the frozen factor is a left-endpoint rule, first order: those targets' half-steps evaluate
    the factor at the half-step's midpoint (Composition._half_step). Read from the declarations
    alone (each source's rate_route_sources, each target's routable_elements and half_step_rows),
    so a definition without such a route is the composition it was. A route the definition's
    checks would refuse (to a law not composed, or a control not routable) is passed over here."""
    from cells.operators import OPERATORS

    declared = [
        (OPERATORS[d.law], d) for d in getattr(spec_model, "operators", ()) if d.law in OPERATORS
    ]
    by_law = {op.LAW_ID: (op, d) for op, d in declared}
    out = set()
    for op, declaration in declared:
        for law, control, ids, species in op.rate_route_sources(declaration):
            if law not in by_law:
                continue
            target, target_declaration = by_law[law]
            if target.ROUTABLE_CONTROLS.get(control) != "rate":
                continue
            moved = set(target.half_step_rows(target_declaration))
            elements = target.routable_elements(target_declaration, control)
            if any(e in ids and (species, cell) in moved for e, cell in elements):
                out.add(law)
    return frozenset(out)


# The laws whose events change which occupant a slot holds (D150's occupant tables switch at
# their times): observe_history's event rows report the departing occupant.
OCCUPANT_EVENTS = ("scheduled_cell_replacement@1",)


def occupant_event_times(spec):
    """The times OCCUPANT_EVENTS' events land on in this definition (a set of floats)."""
    return {
        float(event.time)
        for op, _, schedule in entries(spec)
        if op.LAW_ID in OCCUPANT_EVENTS
        for event in schedule
    }


def check_definition(spec):
    model_for(spec.model).check_definition(spec)


class FamilyModel:
    """A model family that runs as one composition (water@1 and @2, cell replacement@1), for one
    declared inner structure (I2; docs/INNER_MODEL_V4_DESIGN.md §7.4 (c)).

    Each such module binds its names to one full-catalogue composition (its `_model`) and rewrites
    its definitions as that composition's (its `composite(spec)`). This object is the module with
    the composition of one structure instead: the names the module takes from its `_model`, and
    the functions that pass `composite(spec)` to it, come from that composition; every other name
    is the module's own.
    """

    BOUND = (
        "STATE_AXES",
        "STATE_TYPE",
        "LAYOUT_TYPE",
        "FLOOR_LAYOUT_TYPE",
        "SPARSE_LAYOUT_TYPE",
        "checked_step",
        "readouts",
        "field_values",
        "rhs",
        "domain_valid",
        "control_domain_valid",
        "balances",
        "device_balances",
        "magnitudes",
        "ledger_limits",
        "DISSIPATION_FIELDS",
        "DEVICE_CHECKS",
        "DEVICE_DIAGNOSTICS",
        "device_check_constants",
        "device_failure_message",
        "device_checks",
        "OBSERVATION_FIELDS",
        "Observations",
        "structure_key",
    )
    ALIASES = dict(
        Values="VALUES_TYPE",
        ionic_balances="inner_balances",
        ionic_magnitudes="inner_magnitudes",
        imex_step="split_step",
    )

    def __init__(self, module, composition):
        self.module, self.composition = module, composition
        for name in self.BOUND:
            setattr(self, name, getattr(composition, name))
        for name, source in self.ALIASES.items():
            if hasattr(module, name):  # Only the names the module itself exports.
                setattr(self, name, getattr(composition, source))

    def __getattr__(self, name):
        # Only reached for names not set above: the module's own.
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.module, name)

    def __repr__(self):
        return f"<{self.module.MODEL_ID} for {self.composition!r}>"

    def initial_values(self, spec):
        return self.composition.initial_values(self.module.composite(spec))

    def check_definition(self, spec):
        self.composition.check_definition(self.module.composite(spec))

    def check_steps(self, spec, steps, controls):
        self.composition.check_steps(self.module.composite(spec), steps, controls)

    def bind_step_checks(self, spec):
        return self.composition.bind_step_checks(self.module.composite(spec))

    def check_values(self, state, spec, steps=None):
        return self.composition.check_values(state, self.module.composite(spec), steps=steps)

    def observe_history(self, times, history, layout, requested, spec):
        return self.composition.observe_history(
            times, history, layout, requested, self.module.composite(spec)
        )

    def ensemble_voltage(self, state, layout, spec, time):
        return self.composition.ensemble_voltage(state, layout, self.module.composite(spec), time)

    def field_owners(self, spec):
        return self.composition.field_owners(self.module.composite(spec))


@cache
def family_model(module, laws, structure):
    """A family's model for one declared inner structure (cached: equal structures share it). A
    structure that declares kinds is refused at binding (refuse_kinds)."""
    refuse_kinds(module.MODEL_ID, structure)
    return FamilyModel(module, implementation(module.ionic.MODEL_ID, laws, structure))


def refuse_kinds(model_id, declared):
    """The families' refusal of declared kinds (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), the lead's
    ruling 2). Water@1, water@2 and replacement@1 bind @3's full-catalogue types and build its
    states, layouts and controls with today's fields (the replacement operator's arrival field
    solve among them), so a definition that declares a kind is refused, at its definition check
    and at binding, until each family has per-structure internals. declared: a parsed model block
    or an InnerStructure; each carries `kinds`, ((kind ID, ...), ...)."""
    kinds = [kind_id for kind_id, _ in getattr(declared, "kinds", ())]
    if kinds:
        raise ConfigError(
            f"{model_id} does not run declared kinds ({', '.join(kinds)}): it builds the inner "
            "model's states, layouts and controls with today's fixed fields"
        )


def compact(spec):
    m = spec.model
    return replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            channel_capacity=len(m.channels),
        ),
    )


def held_schedules(base, control, names):
    """The inner definition with each named availability held at the given values.

    The inner observer reads its controls from its definition, so a row observed
    at an effective (factored) availability observes this definition.
    """
    e = base.experiment
    held = {}
    for name in names:
        attribute = HELD_SCHEDULES[name]
        count = len(getattr(e, attribute))
        values = np.asarray(getattr(control, name))[:count]
        held[attribute] = tuple((ChannelChange(0.0, float(v)),) for v in values)
    return replace(base, experiment=replace(e, **held))


def _both_scoped(changer, other, name, read=None):
    """Door S: whether a change of `name` by `changer` and other's change or read of it (`read`,
    else its one read of it) are both scoped, so they meet only on the slots both name (decided
    at the definition, scope_errors). Only a provider's own change can be scoped: a closer's,
    and a writer's of a provider's state, cover every slot."""
    if name not in changer.VIEW_FIELDS or not changer.view_change(name).scoped:
        return False
    if name in other.VIEW_FIELDS and other is not changer:
        return other.view_change(name).scoped
    if read is None:
        read = other.scoped_read(name)
    return read is not None and read.scoped


def _whole_field_overlap(earlier, later, name):
    """The refusal of two changes of `name` that meet on every slot (None: admitted or decided per
    slot at the definition): commuting contributions apply in declared order, others overlap."""
    if _both_scoped(earlier, later, name):
        return None
    a, b = earlier.view_change(name).contribution, later.view_change(name).contribution
    if a == b and a in COMMUTING:
        return None
    if a == b == "replace":
        return f"two providers of the view field {name}"
    return (
        f"{earlier.LAW_ID} and {later.LAW_ID} both change the view field {name} ({a} and {b}), "
        "which only commuting changes in declared order may"
    )


def scope_errors(inner, entries, spec):
    """Door S's admission per slot (docs/SCOPED_COMPOSITION_DESIGN.md §3), for the pairs whose
    changes and reads are both scoped (the structure check decides every other pair).

    entries: (operator, its declaration) in declared order. Every refusal names the field, both
    laws and the slots they share, by entity ID."""
    errors = []
    ids = {}

    def entity(name):
        kind = inner.VIEW_FIELD_ENTITIES[name]
        if kind not in ids:
            ids[kind] = [e.id for e in getattr(spec.model, kind)]
        return ids[kind]

    def declared(op, declaration, name, slots_of):
        given = slots_of(spec, declaration)
        if name not in given:
            errors.append(f"{op.LAW_ID} scopes {name} but names no slots for it")
            return frozenset()
        n = len(entity(name))
        slots = frozenset(int(k) for k in given[name])
        if any(not 0 <= k < n for k in slots):
            errors.append(f"{op.LAW_ID} names a slot of {name} outside its {n} entities")
        return slots

    def shared(a, b, name):
        return ", ".join(entity(name)[k] for k in sorted(a & b))

    changes, reads = {}, {}
    for i, (op, declaration) in enumerate(entries):
        for name in op.VIEW_FIELDS:
            if op.view_change(name).scoped:
                slots = declared(op, declaration, name, op.changed_slots)
                changes.setdefault(name, []).append((i, op, slots))
        for name in dict.fromkeys((*op.VIEW_READS, *op.CONFLICTS_VIEW, *op.SCOPED_READS)):
            scoped = [r for r in reads_of(op, name) if r.scoped and r.mode != "reference"]
            if scoped:  # Its slots once per field, whatever the number of stages it reads at.
                slots = declared(op, declaration, name, op.read_slots)
                for read in scoped:
                    reads.setdefault(name, []).append((i, op, read, slots))
    for name, listed in changes.items():
        for k, (_, a, slots_a) in enumerate(listed):
            for _, b, slots_b in listed[k + 1 :]:
                both = (a.view_change(name).contribution, b.view_change(name).contribution)
                if slots_a & slots_b and not (both[0] == both[1] and both[0] in COMMUTING):
                    errors.append(
                        f"{a.LAW_ID} and {b.LAW_ID} both change {name} ({both[0]} and {both[1]}) "
                        f"at {shared(slots_a, slots_b, name)}"
                    )
        for j, reader, read, slots_r in reads.get(name, ()):
            for i, changer, slots_c in listed:
                if changer is reader or not slots_r & slots_c:
                    continue
                if read.mode == "fixed":
                    errors.append(
                        f"{reader.LAW_ID} reads {name} as declared at "
                        f"{shared(slots_r, slots_c, name)}, which {changer.LAW_ID} changes"
                    )
                elif i > j and changer.view_change(name).stage == read.stage:  # C2: one stage.
                    errors.append(
                        f"{reader.LAW_ID} reads the view {name} at "
                        f"{shared(slots_r, slots_c, name)} at stage {read.stage} before "
                        f"{changer.LAW_ID} changes it there"
                    )
    return errors


def slot_mask_errors(entries, spec, p):
    """Door S: each scoped change's device mask (view_slots, from the bound layout) marks exactly
    the slots its changed_slots names (empty: consistent)."""
    errors = []
    for op, declaration in entries:
        scoped = [k for k in op.VIEW_FIELDS if op.view_change(k).scoped]
        if not scoped:
            continue
        given, masks = op.changed_slots(spec, declaration), op.view_slots(p, xp=np)
        for name in scoped:
            mask = np.asarray(masks.get(name, ()))
            if mask.dtype != bool or mask.ndim != 1:
                errors.append(f"{op.LAW_ID} gives no bool slot mask for {name}")
                continue
            if set(np.flatnonzero(mask).tolist()) != {int(k) for k in given.get(name, ())}:
                errors.append(f"{op.LAW_ID}'s slot mask for {name} differs from its slots")
    return errors


# The operators' in-step writers beside declared kinds (docs/INNER_MODEL_V4_DESIGN.md §7.4 (k)
# gap 8, §7.5 version 1): the core's binding refuses inner movers by node (moved_nodes) and
# leaves the operators' writers to the composite's admission. An operator's in-step process
# (PROCESS) declares its writers by node kind (the contract's moves_in_step: (species, "cell" |
# "outside")), so it is taken to move its species at every node of that kind. The species
# registry's moved_in_step is not read here: it joins the inner movers by node kind, and an inner
# route at another node would be a false refusal.
PASSIVE_ROUTES_ID = "cells.passive_routes@1"


def operator_writers(entries, spec):
    """{(species, node ID): (law ID, ...)}: every row a PROCESS operator's in-step process moves
    (entries: (operator, its declaration) pairs), each node kind expanded to the definition's
    nodes of that kind; {} without a PROCESS operator."""
    m = spec.model
    nodes = dict(cell=[c.id for c in m.cells], outside=[o.id for o in m.extracellular])
    out = {}
    for op, declaration in entries:
        if not op.PROCESS:
            continue
        for species, kind in op.moves_in_step(spec, declaration):
            if kind not in nodes:
                raise ConfigError(f"{op.LAW_ID}: moves_in_step gives node kinds cell or outside")
            for node in nodes[kind]:
                laws = out.setdefault((species, node), [])
                if op.LAW_ID not in laws:
                    laws.append(op.LAW_ID)
    return {row: tuple(laws) for row, laws in out.items()}


def _node_kind(spec, node):
    return "cell" if node in {c.id for c in spec.model.cells} else "outside"


def held_row_errors(entries, spec):
    """Gap 8, the composite's part: a row a declared kind holds (held_rows: read at every stage,
    never moved, such as held fuel) is moved by no operator's in-step process (one writer)."""
    declared = tuple(getattr(spec.model, "kinds", ()))
    writers = operator_writers(entries, spec) if declared else {}
    if not writers:
        return []
    errors, registry = [], kind_registry.active()
    for kind_id, declaration in declared:
        # The kind bound to its entry, whose hooks the step runs (never the static kind's).
        kind = pump3.bound_kind(registry.lookup(kind_id), declaration)
        if kind.held_rows is None:
            continue
        for species, node in kind.held_rows(declaration):
            for law in writers.get((species, node), ()):
                errors.append(
                    f"Kind {kind_id} holds {species} at {node}, which {law} moves in the step (its "
                    f"in-step process moves {species} at every {_node_kind(spec, node)} node); a "
                    "held row is moved by nothing in the step (one writer)"
                )
    return errors


def exact_row_errors(entries, spec, p):
    """§7.5 version 1, the operators' half: a row that an exact-booked passive route moves (its
    bound passive_exact, the kind's fixpoint over shared rows, and a nonzero permeability, as the
    booking's own mask) is written by no operator's in-step process. Version 1 refuses such a
    composition: the route's exact share would average over a change it did not make, and the
    operators' writers cannot yet join the kind's scope to downgrade it to tableau booking (a
    seam queued after the landing). A tableau-booked route's rows are not refused."""
    routes = dict(getattr(spec.model, "kinds", ())).get(PASSIVE_ROUTES_ID)
    writers = operator_writers(entries, spec) if routes else {}
    if not writers:
        return []
    errors, exact = [], np.asarray(p.passive_exact)
    for k, route in enumerate(routes):
        if not (exact[k] and route.permeability > 0):
            continue
        for node in (route.inside, route.outside):
            for law in writers.get((route.species, node), ()):
                errors.append(
                    f"{law} moves {route.species} at every {_node_kind(spec, node)} node in the "
                    f"step (its in-step process), and the passive route {route.id} books "
                    f"{route.species} at {node} exactly (§7.5); version 1 refuses this because it "
                    "cannot yet downgrade the route to tableau booking where an operator writes "
                    "its row"
                )
    return errors


def exact_face_row_errors(entries, spec, structure):
    """D280, the operators' half for @3's faces: where the inner structure picks
    exact_free_energy_heat@1 for faces (surface_pump_v3.exact_faces), no operator's in-step
    process writes a row a face carries (a species with a positive diffusivity, at either end
    node), as exact_row_errors holds for exact passive routes: the face's exact share would
    average over a change it did not make."""
    writers = operator_writers(entries, spec) if pump3.ionic.exact_faces(structure) else {}
    if not writers:
        return []
    errors, m = [], spec.model
    for face in m.faces:
        for species, diffusivity in zip(m.species_ids, face.diffusivity_m2_per_s, strict=True):
            if not diffusivity:
                continue
            for node in (face.sender, face.receiver):
                for law in writers.get((species, node), ()):
                    errors.append(
                        f"{law} moves {species} at every {_node_kind(spec, node)} node in the "
                        f"step (its in-step process), and face {face.id} books {species} at "
                        f"{node} exactly ({pump3.ionic.EXACT_FREE_ENERGY_HEAT}, D280); version 1 "
                        "refuses this"
                    )
    return errors


class ViewChange(NamedTuple):
    """One change of a view field in a composition (view_changes): the changer's position in the
    declared order, the changer, the stage, and whether that stage is the changer's own declared
    change of the field (door S's per-slot check covers that one where both sides are scoped)."""

    position: int
    operator: object
    stage: str
    own: bool


def _change_stages(op, names):
    """The stages at which op's own change of `names` is made: those its VIEW_CHANGES declares;
    for an undeclared change, every stage its parts run at (an event map and a split part may both
    change it), or split for a part-less state owner, Operator.view_change's default."""
    declared = {op.VIEW_CHANGES[k].stage for k in names if k in op.VIEW_CHANGES}
    if any(k not in op.VIEW_CHANGES for k in names):
        declared |= set(part_stages(op)) or {op.view_change(names[0]).stage}
    return declared


def closure_reach(inner, op):
    """The view fields op's closures change (close()): for each mask it closes, the inner model's
    CLOSURE_REACH, in its order; a mask the inner model gives no reach changes only itself."""
    reach = getattr(inner, "CLOSURE_REACH", {})
    return tuple(dict.fromkeys(k for name in op.CLOSES for k in reach.get(name, (name,))))


def view_changes(inner, operators):
    """{view field: (ViewChange, ...)}: every change of a view field in an ordered operator list,
    in declared order, once per stage it is made at (docs/OPERATOR_COMPOSITION_DESIGN.md §4.1 and
    §5, C2). The order rule of current reads (structure_errors), its fallback (C1) and the
    composite's view readers read it.

    * A provider changes each field it provides at its change's stages (_change_stages: an
      undeclared change counts at every stage its parts run at), and also at the stages of the
      earlier changes of what it reads current, since its view takes the view the providers before
      it accumulated. Only the declared stage is its own (ViewChange.own).
    * A closer changes, at the stages of its closures, what close() changes for the masks it
      closes (the inner model's CLOSURE_REACH): the masks below them in the entity hierarchy (a
      closed cell closes its patches) and the padded fields of the slots closed.
    * A writer of an earlier owner's accepted state (ACCEPTS_WRITES) changes every field that owner
      provides, at each stage its own parts run at (contract.part_stages).
    """
    out, owners = {}, {}
    for i, op in enumerate(operators):
        found = {}  # {field: {stage: own}}
        for name in op.VIEW_FIELDS:
            stages = dict.fromkeys(_change_stages(op, (name,)), True)
            for read in op.VIEW_READS:
                for change in out.get(read, ()):
                    if change.operator is not op:
                        stages.setdefault(change.stage, False)
            found[name] = stages
        if op.CLOSES:
            closures = _change_stages(op, op.CLOSES)
            for name in closure_reach(inner, op):
                stages = found.setdefault(name, {})
                for stage in closures:
                    stages.setdefault(stage, False)
        for owner in dict.fromkeys(owners[k] for k in op.ENTITY_WRITES if k in owners):
            for name in owner.VIEW_FIELDS:
                stages = found.setdefault(name, {})
                for stage in part_stages(op):
                    stages.setdefault(stage, False)
        for name, stages in found.items():
            for stage in sorted(stages, key=READ_STAGES.index):
                out.setdefault(name, []).append(ViewChange(i, op, stage, stages[stage]))
        owners.update(dict.fromkeys(op.ACCEPTS_WRITES, op))
    return {name: tuple(changes) for name, changes in out.items()}


def _part_reads(op):
    """The fields op's event map or half-step reads current, in declared order: door S's
    SCOPED_READS, its opt-in to receive the merged view (a VIEW_READS default does not opt in)."""
    return tuple(
        k
        for k in op.SCOPED_READS
        if any(r.mode == "current" and r.stage in ("event", "split") for r in reads_of(op, k))
    )


@cache
def reader_view_type(fields):
    """The view a door S current reader's part receives: its read fields only (C4)."""
    return NamedTuple("ReaderView", [(k, object) for k in fields])


def structure_errors(inner, operators):
    """Contract violations of an ordered operator list on an inner model (empty: none)."""
    errors = []
    laws = [op.LAW_ID for op in operators]
    if len(set(laws)) != len(laws):
        errors.append("an operator law appears twice")
    for kind, inner_names, attribute in (
        ("state", inner.STATE_FIELDS, "STATE_AXES"),
        ("layout", inner.LAYOUT_TYPE._fields, "LAYOUT_FIELDS"),
        ("control", inner.CONTROL_FIELDS, "CONTROL_FIELDS"),
    ):
        names = list(inner_names)
        for op in operators:
            names += list(getattr(op, attribute))
        if len(set(names)) != len(names):
            errors.append(f"two owners of one {kind} field")
    # Door S (docs/SCOPED_COMPOSITION_DESIGN.md §3): two changes, or a change and a read, of one
    # field meet on every slot unless both are scoped; a pair of scoped ones is admitted per slot
    # at the definition (scope_errors).
    providers, changers = {}, {}
    for op in operators:
        for name in op.VIEW_FIELDS:
            if name not in inner.VIEW_FIELDS:
                errors.append(f"{op.LAW_ID} provides {name}, which is not an inner view field")
            for earlier in changers.get(name, ()):
                overlap = _whole_field_overlap(earlier, op, name)
                if overlap:
                    errors.append(overlap)
            changers.setdefault(name, []).append(op)
            providers[name] = op.LAW_ID
        for name in op.CONTROL_FACTORS:
            if name not in inner.CONTROL_FIELDS:
                errors.append(f"{op.LAW_ID} multiplies {name}, which is not an inner control")
        for name in op.STATE_RESETS:
            if name not in inner.STATE_FIELDS:
                errors.append(f"{op.LAW_ID} resets {name}, which is not inner state")
    errors.extend(rate_route_errors(operators))
    # Closers of activity masks (S5 design §2): masks combine by conjunction, a mask has
    # closers or a provider, never both, and a closer counts as the mask's provider for
    # CONFLICTS_VIEW (an operator reading the mask on the declared layout is refused).
    closed = {}
    for op in operators:
        for name in op.CLOSES:
            if name not in getattr(inner, "MASK_FIELDS", ()):
                errors.append(f"{op.LAW_ID} closes {name}, which is not an inner activity mask")
            closed.setdefault(name, op.LAW_ID)
    padded = (*getattr(inner, "MASK_FIELDS", ()), *getattr(inner, "PADDED_FIELDS", ()))
    if closed:  # Propagation rewrites every mask and pads closed slots: no provider of them.
        for name in set(providers) & set(padded):
            errors.append(
                f"{name} has closers or a provider, never both ({providers[name]} provides it)"
            )
    accepted, columns = {}, {k: ["inner"] for k in inner.OBSERVATION_FIELDS}
    for op in operators:
        # Writers follow owners: an entity write targets inner state or a field an
        # earlier operator accepts.
        for name in op.ENTITY_WRITES:
            if name not in inner.STATE_FIELDS and name not in accepted:
                errors.append(
                    f"{op.LAW_ID} writes {name}, which is neither inner state nor accepted "
                    "by an earlier operator"
                )
        accepted.update(dict.fromkeys(op.ACCEPTS_WRITES, op.LAW_ID))
        # One owner per observation column; replacement is a declared chain in order.
        for name in op.observed_columns():
            if name in columns:
                errors.append(f"{op.LAW_ID} adds the column {name}, which {columns[name][-1]} owns")
            else:
                columns[name] = [op.LAW_ID]
        for name in op.REPLACES:
            if name in columns:
                columns[name].append(op.LAW_ID)
            else:
                errors.append(f"{op.LAW_ID} replaces {name}, which no earlier owner observes")
    # A closer changes what close() changes for the masks it closes (closure_reach: the masks
    # below them in the entity hierarchy and the padded fields of the slots closed), so a fixed read
    # of any of those beside another operator's closer is refused, not only of the masks it names
    # (door S's rule 4; docs/OPERATOR_COMPOSITION_DESIGN.md §17). The closer named is the first that
    # closes the field itself, else the first whose closures reach it.
    reached = [(op, closure_reach(inner, op)) for op in operators if op.CLOSES]
    for op in operators:
        for name in op.CONFLICTS_VIEW:
            for changer in changers.get(name, ()):
                if changer is not op and not _both_scoped(changer, op, name):
                    errors.append(
                        f"{op.LAW_ID} reads {name} as declared, but {changer.LAW_ID} provides it"
                    )
            others = [c for c, reach in reached if c is not op and name in reach]
            if others:
                closer = next((c for c in others if name in c.CLOSES), others[0])
                errors.append(
                    f"{op.LAW_ID} reads {name} as declared, but {closer.LAW_ID} closes it"
                )
    # The order of a current read (docs/OPERATOR_COMPOSITION_DESIGN.md §4.1 and §5, C1 and C2),
    # against every change of its field (view_changes): a field no operator changes is read at
    # its declared value, the fallback; a change at another stage of the step is seen whatever
    # the declared order (the events run before the split parts' first halves, and an event reads
    # the previous step's end); a change at the reader's own stage precedes it, door S's rule 3,
    # else the reader is refused rather than given a lagged value. A pair of scoped ones meets
    # only on the slots both name, decided at the definition (scope_errors).
    changes, refused = view_changes(inner, operators), set()
    for i, op in enumerate(operators):
        for name in dict.fromkeys((*op.VIEW_READS, *op.SCOPED_READS)):
            current = [r for r in reads_of(op, name) if r.mode == "current"]
            if current and name not in inner.VIEW_FIELDS:
                errors.append(
                    f"{op.LAW_ID} reads the view {name}, which is not an inner view field"
                )
            for read in current:
                for change in changes.get(name, ()):
                    if change.position <= i or change.stage != read.stage:
                        continue
                    # Only a scoped provider's own declared stage is decided per slot.
                    if change.own and _both_scoped(change.operator, op, name, read):
                        continue
                    refused.add((i, name, read.stage, change.operator.LAW_ID))
    for i, name, stage, changer in sorted(refused):
        errors.append(
            f"{operators[i].LAW_ID} reads the view {name} at stage {stage} before {changer} "
            "changes it there"
        )
    for i, op in enumerate(operators):
        for law in op.REQUIRES:
            if law not in laws[:i]:
                errors.append(f"{op.LAW_ID} requires {law} before it")
    # R3: a reader may read only quantities its composed owners declare.
    for reader, owners in quantity_readers(operators).items():
        for owner in owners:
            unknown = [k for k in reader.QUANTITY_READS[owner.LAW_ID] if k not in owner.QUANTITIES]
            if unknown:
                errors.append(
                    f"{reader.LAW_ID} reads {owner.LAW_ID}'s {', '.join(unknown)}, which it does "
                    "not declare among its quantities"
                )
    # Schema A (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j)): an operator that reads or writes a kind's
    # fields declares the kind (REQUIRES_KINDS), refused where the definition does not declare it;
    # its declared writes and resets of a kind's fields name the kind too. A factor of a kind's
    # control is refused: observation holds only today's schedules (held_schedules). An operator
    # that builds the inner types with today's fields (FIXED_INNER_FIELDS) is refused beside any
    # declared kind, and so is one that opens, closes or retires slots (CLOSES, RETIRES, or an
    # activity mask it provides) beside a kind the lifecycle cannot act on by role
    # (docs/CORE_SEAMS_DESIGN.md §4.2; the inner's kind_lifecycle_errors): a kind that declares no
    # roles keeps the refusal's words, since no closer resets its per-slot fields (state on
    # cell_slot, membrane_slot, ...), which would be left stale where a slot closes, retires or
    # opens; one with roles is refused while a field lacks declared axes or an entity axis lacks
    # presence. The core's presence gate, which makes an entity on a closed host absent, acts only
    # where the composition declares a closer (CLOSES: @3's padding_fill), so beside a slot changer
    # with no closer declared (an activity-mask provider alone) a kind with entities stays refused.
    kinds = tuple(getattr(inner, "KINDS", ()))
    declared, owners = set(kinds), getattr(inner, "KIND_FIELDS", {})
    masks = set(getattr(inner, "MASK_FIELDS", ()))
    blocked = _kinds_lifecycle(inner, kinds)
    gated = any(op.CLOSES for op in operators)
    bound = dict(zip(kinds, getattr(inner, "BOUND_KINDS", ()), strict=False))
    for op in operators:
        if kinds and op.FIXED_INNER_FIELDS:
            errors.append(
                f"{op.LAW_ID} builds the inner model's state, layout or control with today's "
                f"fixed fields, so it does not run beside declared kinds ({', '.join(kinds)})"
            )
        if kinds and (op.CLOSES or op.RETIRES or masks & set(op.VIEW_FIELDS)):
            errors.extend(_kinds_beside_closer(op, kinds, blocked, bound=bound, gated=gated))
            errors.extend(
                f"{op.LAW_ID} opens, closes or retires slots, and the kind {kind_id} keeps one_way "
                "records, which version 1 refuses beside an operator that retires or closes slots "
                "until its lifecycle covers them (FR-50; fails closed)"
                for kind_id, kind in bound.items()
                if kind.one_way_records
            )
        required = {kind_registry.qualified(k) for k in op.REQUIRES_KINDS}
        for kind_id in sorted(required - declared):
            errors.append(
                f"{op.LAW_ID} requires the kind {kind_id}, which the definition does not declare"
            )
        for name in dict.fromkeys((*op.ENTITY_WRITES, *op.STATE_RESETS)):
            if owners.get(name, None) not in (None, *required):
                errors.append(
                    f"{op.LAW_ID} writes {name}, a field of the kind {owners[name]}, which it "
                    "does not require (REQUIRES_KINDS)"
                )
        for name in op.CONTROL_FACTORS:
            if name in owners:
                errors.append(
                    f"{op.LAW_ID} multiplies {name}, a control of the kind {owners[name]}; a "
                    "kind's control is not factored (observation holds only today's schedules)"
                )
    errors.extend(lifecycle_errors(inner, operators))
    if sum(op.PROCESS for op in operators) > 1:
        errors.append(
            "at most one in-step membrane process (the inner hook books one combined transfer)"
        )
    return errors


def kind_lifecycle_table(inner, operators):
    """{field: (PartitionRole, axes)}: the declared kinds' state fields that a retiring operator's
    lifecycle acts on (B1's last slice; pump_composite_adapter.lifecycle_split and
    lifecycle_retire): those on a slot axis the partition divides or retires (their entity axis,
    shared and internal axes aside), of every bound kind whose fields all declare roles and axes.
    Empty without a retiring operator or such a field, so no composition admitted before the lift
    of Q7 (a) (which refused every kind with entity fields beside a closer) gains a field."""
    if not any(op.RETIRES for op in operators):
        return {}
    out = {}
    for kind in getattr(inner, "BOUND_KINDS", ()):
        reason = pump3.kind_lifecycle_errors(kind)
        if reason and reason[0] in ("roles", "axes"):  # Refused by the structure check anyway.
            continue
        table = pump3.kind_role_table(kind)
        for name in kind.state_fields:
            role, axes = table[name]
            if pump3.lifecycle_axis(name, axes, kind.internal_axes) in pump3.LIFECYCLE_AXES:
                out[name] = (role, axes)
    return out


def kind_lifecycle_internal(inner, table):
    """{field: its kind's internal axes} for the fields of a lifecycle table (kind_lifecycle_table)
    whose kind declares any: axes its laws carry no entities on, which ride along at a split as
    shared axes do (kind_registry.entity_axes), for pump_composite_adapter.lifecycle_split and
    lifecycle_retire."""
    return {
        name: tuple(kind.internal_axes)
        for kind in getattr(inner, "BOUND_KINDS", ())
        if kind.internal_axes
        for name in kind.state_fields
        if name in table
    }


def lifecycle_field_name(name, what):
    """The composite's field for a kind field's record (what: "retired") or moved accumulator
    ("moved"): the energy suffix dropped, as the partition's records drop it (a heat's record
    ends in _heat_pJ, a work's in _work_energy_pJ), so no name-based sum counts it twice."""
    for suffix, word in ((HEAT_SUFFIX, "heat_pJ"), (WORK_SUFFIX, "work_energy_pJ")):
        if name.endswith(suffix):
            return f"{name[: -len(suffix)]}_{what}_{word}"
    return f"{name}_{what}"


def lifecycle_fields(table):
    """{kind field: the composite's field}: a record for each history field and a moved accumulator
    for each extensive one of a lifecycle table (kind_lifecycle_table)."""
    what = {"history": "retired", "extensive": "moved"}
    return {
        k: lifecycle_field_name(k, what[r.role]) for k, (r, _) in table.items() if r.role in what
    }


def own_axes(kind):
    """A bound kind's own entity axes whose entities a division moves: its entity axes
    (kind_registry.entity_axes) that are not @3's slot axes, unless hosted on outside nodes, which
    are never divided. An own axis that declares no host counts (fails closed)."""
    hosts = kind.axis_hosts if isinstance(kind.axis_hosts, Mapping) else {}
    return tuple(
        axis
        for axis in kind_registry.entity_axes(kind)
        if axis not in pump3.SLOT_AXES and getattr(hosts.get(axis), "kind", None) != "outside_node"
    )


def lifecycle_errors(inner, operators):
    """The refusals of a retiring operator beside the kinds' lifecycle fields (the lead's rulings
    1 and 7 of 19 November 2026 on design statement 1, CORE_SEAMS §18 at 02:25 UTC): one whose
    event map takes no lifecycle= (TAKES_LIFECYCLE) would lose the kinds' history; a per-cell
    extensive kind field, which a division would split by the volume fraction alone, waits for a
    charge rule; and an extensive kind field on edge slots has no contact fraction to split by
    (the partition binds none), so it is refused here rather than when the event is traced (fails
    closed). With the lift of Q7 (a), a kind's own entity axes (own_axes) are refused beside a
    retiring operator too: B1's division neither splits nor retires their entities, which waits
    for B2's own-axis maps."""
    if not any(op.RETIRES for op in operators):
        return []
    errors = []
    if any(op.DIVIDES_OWNED for op in operators):  # FR-43 part 3 (D315): owned state divides.
        for op in operators:
            if op.RETIRES and not op.TAKES_LIFECYCLE:
                errors.append(
                    f"{op.LAW_ID} retires slots beside operators whose owned state divides "
                    "(DIVIDES_OWNED), but its event map takes no lifecycle=, so their state "
                    "would not divide (fails closed)"
                )
    for kind in getattr(inner, "BOUND_KINDS", ()):
        reason = pump3.kind_lifecycle_errors(kind)
        if reason and reason[0] in ("roles", "axes"):  # Refused by the structure check anyway.
            continue
        own = own_axes(kind)
        if own:
            errors.append(
                f"The kind {kind.kind_id}'s own entity axes {list(own)} are refused beside a "
                "dividing closer until own-axis maps exist (B2): a division would neither split "
                "nor retire their entities (fails closed)"
            )
    table = kind_lifecycle_table(inner, operators)
    if not table:
        return errors
    for op in operators:
        if op.RETIRES and not op.TAKES_LIFECYCLE:
            errors.append(
                f"{op.LAW_ID} retires slots beside the kinds' fields {sorted(table)}, but its "
                "event map takes no lifecycle=, so their history would be lost (fails closed)"
            )
    cells = sorted(
        k
        for k, (role, axes) in table.items()
        if role.role == "extensive" and axes[-1] == "cell_slot"
    )
    if cells:
        errors.append(
            f"The kinds' per-cell extensive fields {cells} are refused beside a dividing closer "
            "until a charge rule exists: a division splits them by the volume fraction alone"
        )
    edges = sorted(
        k
        for k, (role, axes) in table.items()
        if role.role == "extensive" and axes[-1] == "edge_slot"
    )
    if edges:
        errors.append(
            f"The kinds' extensive fields on edge slots {edges} are refused beside a dividing "
            "closer: the partition binds no contact fraction to split them by"
        )
    return errors


def _kinds_lifecycle(inner, kinds):
    """{kind ID: (reason, fields) or ()} of the declared kinds beside a closer (the inner's
    kind_lifecycle_errors on its BOUND_KINDS); every kind is refused for its roles, fail-closed,
    where the inner declares neither."""
    check = getattr(inner, "kind_lifecycle_errors", None)
    bound = tuple(getattr(inner, "BOUND_KINDS", ()))
    if check is None or len(bound) != len(kinds):
        return {k: ("roles", ()) for k in kinds}
    return {k: check(kind) for k, kind in zip(kinds, bound, strict=True)}


def rate_route_errors(operators):
    """B1′'s refusal of an ordered operator list (docs/INVENTORY_COUPLING_DESIGN.md §2.1): a
    source's static routes (RATE_ROUTES) go to routable controls of their targets
    (ROUTABLE_CONTROLS). A route to a law the composition does not hold is idle. The order of a
    declared route is the definition's (rate_route_definition_errors), so a composition whose
    source declares no route keeps any order."""
    position = {op.LAW_ID: k for k, op in enumerate(operators)}
    errors = []
    for op in operators:
        for law, name in op.RATE_ROUTES:
            if law in position and operators[position[law]].ROUTABLE_CONTROLS.get(name) != "rate":
                errors.append(
                    f"{op.LAW_ID} routes a rate factor to {law}'s {name}, which is not one of its "
                    "routable controls (ROUTABLE_CONTROLS)"
                )
    return errors


def rate_route_definition_errors(pairs):
    """B1′'s refusals of a definition's declared rate routes ((operator, declaration) in
    declared order; each source's declared_rate_routes): a route that is not one of its source's
    RATE_ROUTES, to a law the composition does not hold, or to a target declared before its
    source. The last keeps the split order (first halves in declared order, second halves
    reversed) symmetric about the target."""
    position = {op.LAW_ID: k for k, (op, _) in enumerate(pairs)}
    errors = []
    for k, (op, declaration) in enumerate(pairs):
        for law, name in op.declared_rate_routes(declaration):
            if (law, name) not in op.RATE_ROUTES:
                errors.append(f"{op.LAW_ID} declares a route to {law}'s {name}, not one it routes")
            elif law not in position:
                errors.append(
                    f"{op.LAW_ID} routes a rate factor to {law}, which the composition does not "
                    "hold"
                )
            elif position[law] < k:
                errors.append(
                    f"{op.LAW_ID} routes a rate factor to {law}, which precedes it: a route's "
                    "source runs before its target, so the split's halves are symmetric about it"
                )
    return errors


def rate_routes(operators):
    """{target: ((source, field), ...)} of an ordered operator list's split targets with a route
    source, the sources in declared order (static; empty without a route source)."""
    out = {}
    for target in operators:
        if not (target.SPLIT and target.ROUTABLE_CONTROLS):
            continue
        routes = tuple(
            (source, name)
            for source in operators
            for law, name in source.RATE_ROUTES
            if law == target.LAW_ID and name in target.ROUTABLE_CONTROLS
        )
        if routes:
            out[target] = routes
    return out


def _kinds_beside_closer(op, kinds, blocked, *, bound=None, gated=True):
    """The refusals of a closer `op` beside the declared kinds the lifecycle cannot act on, and,
    where no closer is declared (`gated` false: the core's presence gate is off), beside each
    admitted kind with entities (kind_registry.entity_axes of its `bound` kind)."""
    roleless = [k for k in kinds if blocked[k] and blocked[k][0] == "roles"]
    out = []
    if roleless:
        out.append(
            f"{op.LAW_ID} opens, closes or retires slots, and no closer resets a kind's "
            f"per-slot fields, so it does not run beside declared kinds ({', '.join(roleless)})"
        )
    for k in kinds:
        reason, fields = blocked[k] or (None, ())
        if reason == "axes":
            out.append(
                f"{op.LAW_ID} opens, closes or retires slots, and the kind {k} declares no axes "
                f"for {', '.join(fields)}, so the lifecycle cannot act on them by role"
            )
        elif reason == "presence":
            out.append(
                f"{op.LAW_ID} opens, closes or retires slots, and the kind {k} declares no "
                f"presence field on its entity axes ({', '.join(fields)}), so the core's presence "
                "gate cannot make its entities there absent where their host is closed"
            )
        elif reason == "hosts":
            out.append(
                f"{op.LAW_ID} opens, closes or retires slots, and the kind {k}'s entity axes "
                f"({', '.join(fields)}) have no host the core's presence gate reads (@3's slots "
                "of cells, outside nodes, patches, junctions, channel populations or faces, or an "
                "own axis's declared host), so it cannot close their entities"
            )
        elif reason is None and not gated:
            entities = kind_registry.entity_axes(bound[k]) if k in (bound or {}) else ("?",)
            if entities:
                out.append(
                    f"{op.LAW_ID} opens, closes or retires slots, but no closer is declared, so "
                    "the core's presence gate is off and the kind "
                    f"{k}'s entities on {', '.join(entities)} would keep running where the view "
                    "closes their host"
                )
    return out


def field_map(inner, operators):
    """The composition's field-to-owner map (written to the run manifest).

    State fields with their owner and writers (entity writes and resets), layout and
    control fields with their owner, view fields with their provider and readers, and
    each observation column's owner chain (its owner is the last). With factor operators,
    `factors` gives each factored inner control's chain of their laws in declared order.
    """
    state = {k: {"owner": "inner", "writers": []} for k in inner.STATE_FIELDS}
    layout = dict.fromkeys(inner.LAYOUT_TYPE._fields, "inner")
    control = dict.fromkeys(inner.CONTROL_FIELDS, "inner")
    columns = {k: ["inner"] for k in inner.OBSERVATION_FIELDS}
    for name in lifecycle_fields(kind_lifecycle_table(inner, operators)).values():
        state[name] = {"owner": "composite", "writers": []}  # Q6 (b)'s records and moves.
    for op in operators:
        state |= {k: {"owner": op.LAW_ID, "writers": []} for k in op.STATE_AXES}
        layout |= dict.fromkeys(op.LAYOUT_FIELDS, op.LAW_ID)
        control |= dict.fromkeys(op.CONTROL_FIELDS, op.LAW_ID)
        columns |= {k: [op.LAW_ID] for k in op.observed_columns()}
        for k in op.REPLACES:
            columns[k] = [*columns[k], op.LAW_ID]
    for op in operators:
        for k in dict.fromkeys((*op.ENTITY_WRITES, *op.STATE_RESETS)):
            state[k]["writers"].append(op.LAW_ID)
    views = {
        k: {"provider": op.LAW_ID, "readers": [r.LAW_ID for r in operators if k in r.VIEW_READS]}
        for op in operators
        for k in op.VIEW_FIELDS
    }
    # Door S: a field several operators change records each change in declared order, the order
    # it is merged in (docs/SCOPED_COMPOSITION_DESIGN.md §3). Only then, so every other map, and so
    # its manifests, are unchanged.
    for k, view in views.items():
        changers = [op for op in operators if k in op.VIEW_FIELDS]
        if len(changers) > 1:
            view["changes"] = [
                [op.LAW_ID, op.view_change(k).contribution, op.view_change(k).scoped]
                for op in changers
            ]
    for k in dict.fromkeys(k for op in operators for k in op.CLOSES):  # Only with closers.
        views[k] = {
            "closers": [op.LAW_ID for op in operators if k in op.CLOSES],
            "readers": [r.LAW_ID for r in operators if k in r.VIEW_READS],
        }
    out = dict(state=state, layout=layout, control=control, views=views, observations=columns)
    # Each factored inner control's chain of factor operators, in declared (multiplication) order
    # (docs/INVENTORY_COUPLING_DESIGN.md §1.7, ruling 6). Only with factor operators, so every
    # other composition's map, and so its manifests, are unchanged.
    factors = {}
    for op in operators:
        for k in op.CONTROL_FACTORS:
            factors.setdefault(k, []).append(op.LAW_ID)
    if factors:
        out["factors"] = factors
    # R3's readable quantities: each owner's quantities with their axis and unit, and the readers
    # that may read them. Only where a reader and its owner are both composed, so every other map,
    # and so its manifests, are unchanged.
    readers = quantity_readers(operators)
    if readers:
        quantities = {}
        for reader, owners in readers.items():
            for owner in owners:
                entry = quantities.setdefault(
                    owner.LAW_ID,
                    {
                        "quantities": {k: list(v) for k, v in owner.QUANTITIES.items()},
                        "readers": [],
                    },
                )
                entry["readers"].append(reader.LAW_ID)
        out["quantities"] = quantities
    return out


def quantity_readers(operators):
    """R3: {reader: (its owners in the composition, in declared order)} for each operator whose
    QUANTITY_READS names a composed owner (static; empty without one)."""
    by_law = {op.LAW_ID: op for op in operators}
    out = {}
    for op in operators:
        owners = tuple(by_law[law] for law in op.QUANTITY_READS if law in by_law)
        if owners:
            out[op] = owners
    return out


def quantity_read_definition_errors(pairs):
    """R3's refusals of a definition's declared quantity reads ((operator, declaration) in declared
    order; each reader's declared_quantity_reads): a read that is not one of its QUANTITY_READS, of
    an owner the composition does not hold, or, read in an operator target's half-steps, of an
    owner declared after that target. The owner then moves its quantity in its own half-steps
    before the target's first half, and after its second, so the split stays symmetric about the
    target."""
    position = {op.LAW_ID: k for k, (op, _) in enumerate(pairs)}
    errors = []
    for op, declaration in pairs:
        for owner, name, target in op.declared_quantity_reads(declaration):
            if name not in op.QUANTITY_READS.get(owner, ()):
                errors.append(f"{op.LAW_ID} declares a read of {owner}'s {name}, not one it reads")
            elif owner not in position:
                errors.append(
                    f"{op.LAW_ID} reads {owner}'s {name}, which the composition does not hold"
                )
            elif target is not None and target in position and position[owner] > position[target]:
                errors.append(
                    f"{op.LAW_ID} reads {owner}'s {name} in {target}'s half-steps, but {owner} "
                    f"follows {target}: an owner whose quantity a route reads precedes the route's "
                    "target, so both of its halves read the quantity after the owner's first half"
                )
    return errors


def accepted_writers(operators):
    """{owner law: ((writer, the owner's ledgers its writes reach), ...)} in declared order."""
    owners = {k: op for op in operators for k in op.ACCEPTS_WRITES}
    writers = {}
    for op in operators:
        for field in op.ENTITY_WRITES:
            if field in owners:
                owner = owners[field]
                reached = writers.setdefault(owner.LAW_ID, {}).setdefault(op.LAW_ID, [op, []])
                reached[1] += [k for k in owner.ACCEPTS_WRITES[field] if k not in reached[1]]
    return {law: tuple((w, tuple(k)) for w, k in byw.values()) for law, byw in writers.items()}


def _channel_targets(values):
    """A composite's values' channel-gate targets: the inner model's, computed at the composite's
    view and effective control (values.ionic), as surface_pump_projective.settling reads a model's
    values.channel_targets (FR-8's engine gap, validation/long_duration/RESULTS_20261118.md §7)."""
    return values.ionic.channel_targets


class Composition:
    """The model protocol of one composition (attributes as a model module's)."""

    def __init__(self, inner, operators, *, midpoint=frozenset()):
        errors = structure_errors(inner, operators)
        if errors:
            raise ConfigError("Invalid operator composition: " + "; ".join(errors))
        self.inner, self.operators = inner, operators
        self.FIELD_MAP = field_map(inner, operators)
        self.writers_of = accepted_writers(operators)
        self.observed_keys = {op.LAW_ID: {*op.observed_columns(), *op.REPLACES} for op in operators}
        self.laws = tuple(op.LAW_ID for op in operators)
        # The executable's structure (I2): the inner structure's key and the operator list, and
        # the self-moved rate-route targets where there are any (static, B1′: none keeps the key).
        self.structure_key = (MODEL_ID, getattr(inner, "structure_key", None), self.laws)
        self.midpoint = frozenset(midpoint)
        if self.midpoint:
            self.structure_key += (("midpoint", tuple(sorted(self.midpoint))),)
        # Declarations contribute nothing to the step (contract.DECLARATION_ONLY): a composition
        # of declarations alone steps as the empty composition does (FR-1 design §1.6, S5).
        self.stepping = tuple(op for op in operators if not op.DECLARATION_ONLY)
        self.MODEL_ID = MODEL_ID
        self.OBSERVER_ID = OBSERVER_ID
        self.OBSERVATION_SAMPLING = inner.OBSERVATION_SAMPLING
        self.STAGE_DOMAIN_ID = STAGE_DOMAIN_ID
        self.BATCH_CAPACITIES = inner.BATCH_CAPACITIES
        self.ENERGY_RTOL = inner.ENERGY_RTOL
        self.EXPLICIT_STEP_BOUND = inner.EXPLICIT_STEP_BOUND
        # Parts, in declared order.
        self.events = tuple(op for op in operators if op.EVENT)
        self.splits = tuple(op for op in operators if op.SPLIT)
        self.providers = tuple(op for op in operators if op.VIEW_FIELDS)
        self.factors = tuple(op for op in operators if op.CONTROL_FACTORS)
        self.factored = tuple(dict.fromkeys(k for op in self.factors for k in op.CONTROL_FACTORS))
        # R2: each factor operator's current reads at the control view (static: none declared,
        # no view is passed and every control-view call is as before).
        self.factor_fields = {op: factor_reads(op) for op in self.factors if factor_reads(op)}
        # B1′: each routed split target's (source, field) routes (static: none without a source).
        self.rate_routes = rate_routes(operators)
        # R3: each reader's composed owners (static: none declared, no call changes).
        self.quantity_readers = quantity_readers(operators)
        self.domain_views = tuple(op for op in operators if op.VIEW_FOLLOWS_SPLIT)
        self.process_operator = next((op for op in operators if op.PROCESS), None)
        # FR-42 (D289): the label owner and the split parts that report their one-way moves to it
        # (static: without an owner no half-step call changes).
        self.label_owner = next((op for op in operators if op.LABEL_OWNER), None)
        self.label_reporters_in_order = tuple(
            op for op in operators if self.label_owner is not None and reports_labels(op)
        )
        self.label_reporters = frozenset(self.label_reporters_in_order)
        # D296: each source reporter's and pool reporter's position among them (static), the
        # label owner's axes (species_labels.reporters).
        self.label_sources = {
            op: k
            for k, op in enumerate(o for o in self.label_reporters_in_order if o.LABEL_SOURCES)
        }
        self.label_pools = {
            op: k for k, op in enumerate(o for o in self.label_reporters_in_order if o.LABEL_POOLS)
        }
        # D296: the events that report what they replace, the slots or (a pool reporter's) the
        # pools they empty (erratum E; static: by their signature).
        self.label_events = frozenset(
            op for op in self.events if self.label_owner is not None and takes_labels(op.event)
        )
        # FR-42's stage 2: the inner step reports its one-way transfers where it takes labels=
        # (static: by the inner implementation's signature; none without an owner). Declared
        # kinds report theirs through their hook (D303 item 6), and the owner's definition check
        # refuses what a kind cannot carry (species_labels.in_step_errors).
        self.inner_reports_labels = self.label_owner is not None and takes_labels(
            self.inner.checked_step
        )
        self.coupled = any(op.SPLIT and op.RK4 == "coupled" for op in operators) or (
            self.process_operator is not None
        )
        self.field_inputs = any(
            set((*op.VIEW_FIELDS, *op.CLOSES)) & set(inner.FIELD_INPUTS) for op in operators
        )
        # Door S (docs/SCOPED_COMPOSITION_DESIGN.md §2, §4): operators with scoped changes (their
        # bound slot masks are checked at binding), and the parts that declare a current read at
        # stage event or split of a field some operator changes, which receive the merged view
        # (static: by declarations; BOOKS_AT_VIEW keeps its own condition).
        self.scoped_changers = tuple(
            op for op in operators if any(op.view_change(k).scoped for k in op.VIEW_FIELDS)
        )
        self.view_changes = view_changes(inner, operators)
        self.view_readers = tuple(
            op for op in operators if any(k in self.view_changes for k in _part_reads(op))
        )
        # C4 (docs/OPERATOR_COMPOSITION_DESIGN.md §4.1, §11): each view reader's part receives its
        # current-read fields only (reader_view), never the full view's field refresh.
        self.reader_fields = {op: _part_reads(op) for op in self.view_readers}
        # Topology (S5 design §2, §3.5). With a closer the composite owns the capacitor-energy
        # correction at the view, referenced to the view of the initial state through two
        # bound layout arrays (COMPOSITE_LAYOUT_FIELDS); with a retiring operator its row
        # checks read the adjusted row. Without either, nothing here changes a program.
        self.closers = tuple(op for op in operators if op.CLOSES)
        self.retiring = tuple(op for op in operators if op.RETIRES)
        # FR-43 part 3 (D315): operators whose owned state divides at a retiring operator's
        # division (contract.DIVIDES_OWNED), in declared order. None in a composition admitted
        # before, so the lifecycle's condition and callable stay as they were (static).
        self.owned_dividers = tuple(op for op in operators if op.DIVIDES_OWNED)
        self.owns_view_energy = bool(self.closers)
        self.COMPOSITE_LAYOUT_FIELDS = (
            ("view_energy_reference_pJ", "view_plate_reference_C") if self.owns_view_energy else ()
        )
        # Types: the inner model's fields, then each operator's, in declared order.
        self.STATE_AXES = dict(inner.STATE_AXES)
        for op in operators:
            self.STATE_AXES.update(op.STATE_AXES)
        # B1's last slice (Q6 (b), the lead's rulings on design statement 1): beside a retiring
        # operator, the composite owns a record for each kind history field and a moved
        # accumulator for each extensive one, on the slot axes; none in a composition admitted
        # today (kind_lifecycle_table).
        self.kind_lifecycle = kind_lifecycle_table(inner, operators)
        self.KIND_INTERNAL = kind_lifecycle_internal(inner, self.kind_lifecycle)
        names = lifecycle_fields(self.kind_lifecycle)
        self.KIND_RECORDS = {
            k: names[k] for k, (r, _) in self.kind_lifecycle.items() if r.role == "history"
        }
        self.KIND_MOVED = {
            k: names[k] for k, (r, _) in self.kind_lifecycle.items() if r.role == "extensive"
        }
        for field, name in (*self.KIND_RECORDS.items(), *self.KIND_MOVED.items()):
            self.STATE_AXES[name] = list(self.kind_lifecycle[field][1])  # Records, then moves.
        self.STATE_DTYPES = {k: v for op in operators for k, v in op.STATE_DTYPES.items()}
        self.STATE_TYPE = NamedTuple("CompositeState", [(k, object) for k in self.STATE_AXES])
        # The energy-role table (v2 design §1.1): every heat and work field by declaration
        # (@3's from the adapter, each operator's HEAT_FIELDS and WORK_FIELDS), in state
        # order; the energy ledger's flow bound reads these, not field-name suffixes.
        roles = {*inner.HEAT_FIELDS, *inner.WORK_FIELDS}
        for op in operators:
            roles |= {*op.HEAT_FIELDS, *op.WORK_FIELDS}
        self.ENERGY_FLOW_FIELDS = tuple(k for k in self.STATE_TYPE._fields if k in roles)
        extra = (
            *(k for op in operators for k in op.LAYOUT_FIELDS),
            *self.COMPOSITE_LAYOUT_FIELDS,
        )
        self.LAYOUT_TYPE = NamedTuple(
            "CompositeLayout", [(k, object) for k in (*inner.LAYOUT_TYPE._fields, *extra)]
        )
        self.FLOOR_LAYOUT_TYPE = NamedTuple(
            "CompositeFloorLayout",
            [(k, object) for k in (*inner.FLOOR_LAYOUT_TYPE._fields, *extra)],
        )
        self.SPARSE_LAYOUT_TYPE = NamedTuple(  # The sparse field (surface_field.SPARSE_SOLVER_ID).
            "CompositeSparseLayout",
            [(k, object) for k in (*inner.SPARSE_LAYOUT_TYPE._fields, *extra)],
        )
        self.CONTROL_FIELDS = (
            *inner.CONTROL_FIELDS,
            *(k for op in operators for k in op.CONTROL_FIELDS),
        )
        self.CONTROL_TYPE = composite_spec.control_type(self.CONTROL_FIELDS)
        self.READOUTS = tuple(op.READOUT for op in operators if op.READOUT)
        # FR-8's engine gap (validation/long_duration/RESULTS_20261118.md §7): a reader of a model's
        # values finds the channel gates' targets as values.channel_targets
        # (surface_pump_projective.settling). A composite's are the inner model's at its view,
        # nested under `ionic`, so a property forwards them: the values' fields, every record and
        # every traced program stay as they were.
        values = NamedTuple(
            "CompositeValues",
            [(k, object) for k in ("field", "derivative", "ionic", *self.READOUTS, "valid")],
        )
        self.VALUES_TYPE = type(
            "CompositeValues",
            (values,),
            {"__slots__": (), "channel_targets": property(_channel_targets)},
        )
        # The dissipation check's fields: each operator's heat fields whose declared energy role
        # is monotone (contract.monotone_heat; every heat field by default). A non-monotone heat
        # stays among the energy flows above.
        self.DISSIPATION_FIELDS = (
            *inner.DISSIPATION_FIELDS,
            *(k for op in operators for k in monotone_heat(op)),
        )
        self.own_ledger_operators = tuple(op for op in operators if op.LEDGERS)
        self.LEDGERS = (*inner.LEDGERS, *(k for op in operators for k in op.LEDGERS))
        self.LEDGER_DIAGNOSTICS = (
            *inner.LEDGER_DIAGNOSTICS,
            *(k for op in operators for k in op.LEDGER_DIAGNOSTICS),
        )
        self.DEVICE_CHECKS = ("domain", *self.LEDGERS, "dissipation")
        self.DEVICE_DIAGNOSTICS = (
            *("max_" + k for k in self.LEDGER_DIAGNOSTICS),
            "max_energy_balance_relative",
            "max_global_charge_bound_ratio",
        )
        self.OBSERVATION_FIELDS = (
            *inner.OBSERVATION_FIELDS,
            *(k for op in operators for k in (*op.STATE_AXES, *op.READOUT_COLUMNS)),
        )
        self.Observations = make_dataclass(
            "CompositeObservations",
            [(k, np.ndarray) for k in self.OBSERVATION_FIELDS],
            frozen=True,
        )

        # Plain functions where callers read attributes off them.
        def domain_valid(state, p, active, *, xp=jnp):
            return self._domain(state, p, active, xp=xp)

        domain_valid.with_control = self.control_domain_valid
        self.domain_valid = domain_valid

    def __repr__(self):
        return f"<{MODEL_ID} {self.inner.MODEL_ID} [{', '.join(self.laws)}]>"

    # ------------------------------------------------------------ binding

    parameters = staticmethod(pump3.parameters)
    physical_amounts = staticmethod(pump3.physical_amounts)
    rebind = staticmethod(pump3.rebind)
    device_check_constants = staticmethod(pump3.device_check_constants)

    def composition_identity(self, spec):
        return identity(spec.model)

    def field_owners(self, spec):
        """The field-to-owner map (field_map), written to run manifests."""
        return self.FIELD_MAP

    def batch_signature(self, model):
        """The run identity and array axes of `model` (any composition: batches compare
        every world's signature with the first world's)."""
        from cells.operators import OPERATORS

        laws = composite_spec.operator_laws(model)
        parts = tuple(part for d in model.operators for part in OPERATORS[d.law].batch_signature(d))
        return (MODEL_ID, model.inner_model, laws, *self.inner.batch_signature(model), *parts)

    def working_size(self, spec):
        return self.inner.working_size(projection(spec)) + sum(
            op.working_size(spec) for op in self.operators
        )

    def fixed_working_size(self, spec):
        """Values held once per resident copy, never per saved row (execution/resources.fixed_bytes;
        FR-43, D315): the operators' bound layouts, where an operator declares one."""
        return sum(
            op.fixed_working_size(spec)
            for op in self.operators
            if hasattr(op, "fixed_working_size")
        )

    def initial_values(self, spec):
        state, p = self.inner.initial_values(projection(spec))
        values, layout = state._asdict(), p._asdict()
        for op, declaration, schedule in entries(spec):
            owned, bound = op.initial_values(
                spec, declaration, schedule, state, p, **self._inner_keyword(op)
            )
            values.update(owned)
            layout.update(bound)
        for field, name in (*self.KIND_RECORDS.items(), *self.KIND_MOVED.items()):
            values[name] = np.zeros_like(np.asarray(values[field], dtype=float))
        kind = (
            self.FLOOR_LAYOUT_TYPE
            if type(p) is self.inner.FLOOR_LAYOUT_TYPE
            else self.SPARSE_LAYOUT_TYPE
            if type(p) is self.inner.SPARSE_LAYOUT_TYPE
            else self.LAYOUT_TYPE
        )
        if self.owns_view_energy:
            values = self._closed_initial_state(self.STATE_TYPE(**values), kind, layout)
            layout.update(self._view_references(self.STATE_TYPE(**values), kind, layout))
        p = kind(**layout)
        if self.scoped_changers:  # Door S: each bound slot mask marks its declared slots.
            masks = slot_mask_errors([(op, d) for op, d, _ in entries(spec)], spec, p)
            if masks:
                raise ConfigError("Invalid operator composition: " + "; ".join(masks))
        return self.STATE_TYPE(**values), p

    def _closed_initial_state(self, state, kind, layout):
        """The bound state with closed contacts' gates at @3's padded 0 (S5 design §2).

        @3 binds every declared gate; a contact closed at the initial view holds 0 instead,
        and the closer that opens it writes its gate at that event."""
        o = layout["boundary_V"].size
        zeros = dict(view_energy_reference_pJ=np.asarray(0.0), view_plate_reference_C=np.zeros(o))
        p = kind(**layout, **zeros)
        live = self._live_closers(p)
        if not live:
            return state._asdict()
        view = self.inner.view(p, state, self.providers, live, xp=np)
        return self.inner.close_state(state, view, xp=np)._asdict()

    def _view_references(self, state, kind, layout):
        """The energy rule's reference with a closer (S5 design §3.6 point 4), bound once (R1).

        adapter.view_capacitor_terms measures against the declared layout at t = 0, where
        pending slots are active. At the view of the initial state its two terms are the
        offsets that bring the reference to that view: E_ref = 1/2 sum C0 V0^2 (declared) -
        1/2 sum C V^2 (initial view) and q_ref = plates_declared(0) - plates_view(0) at the held
        nodes. Every ledger then starts at zero (to rounding: a host bind against a device solve).
        """
        o = layout["boundary_V"].size
        zeros = dict(view_energy_reference_pJ=np.asarray(0.0), view_plate_reference_C=np.zeros(o))
        p = kind(**layout, **zeros)
        live = self._live_closers(p)
        if not live:
            return zeros
        view = self.inner.view(p, state, self.providers, live, xp=np)
        energy, electrode, _, _ = self.inner.view_capacitor_terms(
            state, view, self.inner.inner_layout(p), xp=np
        )
        return dict(
            view_energy_reference_pJ=np.asarray(-energy, dtype=float),
            view_plate_reference_C=np.asarray(-electrode, dtype=float),
        )

    def _live_retiring(self, p):
        """The retiring operators not statically idle (static under jit)."""
        return tuple(op for op in self.retiring if not op.statically_idle(p))

    def _live_closers(self, p):
        """The closers not statically idle (by layout shape: static under jit)."""
        return tuple(op for op in self.closers if not op.statically_idle(p))

    def view(self, p, state, *, xp=jnp):
        if self.closers:
            return self.inner.view(p, state, self.providers, self._live_closers(p), xp=xp)
        return self.inner.view(p, state, self.providers, xp=xp)

    def reader_view(self, op, p, state, *, xp=jnp):
        """A door S current reader's view (C4, docs/OPERATOR_COMPOSITION_DESIGN.md §4.1, §11):
        the full view's merge of every provider and closer at `state`, bitwise its fields, but
        without the field refresh, which no read field holds; it carries op's read fields only,
        so a part reads nothing else from it."""
        return self._reader_view_of(self.reader_fields[op], p, state, xp=xp)

    def _reader_view_of(self, fields, p, state, *, xp):
        """C4's reader view of `fields` at `state` (reader_view; R2's control-view reads)."""
        closers = self._live_closers(p) if self.closers else ()
        q = self.inner.view(p, state, self.providers, closers, xp=xp, refresh=False)
        return reader_view_type(fields)(*(getattr(q, k) for k in fields))

    def _factor_views(self, p, *, xp):
        """R2: {factor operator: the function of state giving its reader view of factor_reads}
        for each one that declares such a read (static)."""
        return {
            op: (lambda s, fields=fields: self._reader_view_of(fields, p, s, xp=xp))
            for op, fields in self.factor_fields.items()
        }

    def _view_for(self, op, p, *, xp):
        """The view function op's part receives (static): the full view for one that books at
        the view when a field input is provided, as before; a door S reader's view otherwise."""
        if op.BOOKS_AT_VIEW and self.field_inputs:
            return lambda s: self.view(p, s, xp=xp)
        return lambda s: self.reader_view(op, p, s, xp=xp)

    def quantity_reader(self, op, p, *, xp):
        """R3: the function of state a reader receives as quantities=, giving {owner law: {name:
        values}} of its composed owners, each computed by the owner's own quantities; None for an
        operator that reads none (static). Nothing is traced unless the reader calls it."""
        owners = self.quantity_readers.get(op)
        if not owners:
            return None
        return lambda s: {owner.LAW_ID: owner.quantities(s, p, xp=xp) for owner in owners}

    def _quantity_keywords(self, op, p, *, xp):
        """R3: {"quantities": its function} for a reader with a composed owner, else {} (static)."""
        reader = self.quantity_reader(op, p, xp=xp)
        return {} if reader is None else {"quantities": reader}

    def control_view(self, control, state, p, *, xp=jnp):
        """The inner control with every factor applied at `state`; a factor operator that reads
        at the control view gets view= (R2), and a reader of quantities quantities= (R3) (static:
        otherwise the call is unchanged)."""
        readers = {
            op: self.quantity_reader(op, p, xp=xp)
            for op in self.factors
            if op in self.quantity_readers
        }
        if not self.factor_fields and not readers:
            return self.inner.control_view(control, state, p, self.factors, xp=xp)
        keywords = {}
        if self.factor_fields:
            keywords["views"] = self._factor_views(p, xp=xp)
        if readers:
            keywords["quantities"] = readers
        return self.inner.control_view(control, state, p, self.factors, xp=xp, **keywords)

    def inner_state(self, state):
        return self.inner.inner_state(state)

    # ------------------------------------------------------------ the step

    def checked_step(self, state, dt, control, p, active):
        """The composite step (module docstring); RK4 for an empty tableau."""
        if not self.stepping:  # The empty composition (or declarations only) is the inner step.
            moved, ok = self.inner.checked_step(
                self.inner.inner_state(state),
                dt,
                self.inner.inner_control(control),
                self.inner.inner_layout(p),
                active,
            )
            return state._replace(**moved._asdict()), ok
        if p.imex_explicit.shape[0] == 0 and self.coupled:
            return rk4_checked_step(self.rhs, self.domain_valid, state, dt, control, p, active)
        return self.split_step(state, dt, control, p)

    def split_step(self, state, dt, control, p, *, xp=jnp):
        """E, the first halves, the inner step at the view, the second halves.

        The inner step is @3's checked step (IMEX, or RK4 for an empty tableau
        without coupled operators), or @3's IMEX step with the in-step process.
        A refused piece refuses the step, which returns the start state.
        """
        idle = tuple(op for op in self.operators if op.statically_idle(p))
        active = tuple(op for op in self.operators if op not in idle)
        valid, current = None, state
        for op in self.events:
            if op in active:
                keywords = self._inner_keyword(op)  # Static: an operator that uses the inner.
                if self._passes_view(op):  # Static: S5's partition; door S's current readers.
                    keywords["view"] = self._view_for(op, p, xp=xp)
                lifecycle = op.RETIRES and (  # Static: Q6 (b), and FR-43's owned dividers.
                    bool(self.kind_lifecycle) or bool(self.owned_dividers)
                )
                if lifecycle:
                    owned = self.owned_dividers
                    keywords["lifecycle"] = (
                        partial(self._owned_lifecycle, p) if owned else self._lifecycle
                    )
                before = current
                if op in self.label_events:  # Static (D296; erratum E): what it replaced.
                    rows = self.label_owner.rows(p)
                    current, ok, report = op.event(
                        current, control, p, xp=xp, labels=rows, **keywords
                    )  # A pool reporter's event reports its emptied pools, any other its slots.
                    pool = self.label_pools.get(op)
                    current = self.label_owner.advance_event(
                        before, current, report, control, p, xp=xp, pool=pool
                    )
                else:
                    current, ok = op.event(current, control, p, xp=xp, **keywords)
                valid = _and(valid, ok)
                if lifecycle:
                    valid = _and(valid, self._history_kept(before, current, xp=xp))
        h = 0.5 * dt
        splits = tuple(op for op in self.splits if op in active)
        for op in splits:
            current, ok = self._half_step(op, current, h, control, p, xp=xp)
            valid = _and(valid, ok)
            valid = _and(valid, op.control_valid(control, p, xp=xp))
        process = self.process_operator
        if process is not None and process.idle_process(p):
            process = None  # Statically absent (no route declared): the inner step itself.
        inputs = (
            self.inner.inner_state(current),
            self.control_view(control, current, p, xp=xp),
            self.view(p, current, xp=xp),
        )
        if self.factors:  # Static (B1′): the factors' ranges and records at the control view.
            checked, current = self._control_factor_checks(current, p, xp=xp)
            valid = _and(valid, checked)
        inputs = self.inner.barrier(inputs, xp=xp)
        # FR-42's stage 2 (static): an IMEX inner step that reports gives the label owner its
        # transfers; RK4's (an empty tableau) is refused beside a labelled in-step mover.
        if self.inner_reports_labels and p.imex_explicit.shape[0]:
            current, ok, applied, heat = self._labelled_inner(
                current, inputs, dt, process, control, p, xp=xp
            )
        elif process is None:
            moved, ok = self.inner.checked_step(inputs[0], dt, inputs[1], inputs[2], p.active)
            moved, ok = self.inner.barrier((moved, ok), xp=xp)
            current = current._replace(**moved._asdict())
        else:
            moved, ok, (applied, heat) = self.inner.imex_step(
                inputs[0],
                dt,
                inputs[1],
                inputs[2],
                xp=xp,
                membrane_process=process.process(control, p),
            )
            moved, ok, applied, heat = self.inner.barrier((moved, ok, applied, heat), xp=xp)
            current = current._replace(**moved._asdict())
        last = None
        for op in reversed(splits):
            current, ok_half = self._half_step(op, current, h, control, p, xp=xp)
            last = _and(last, ok_half)
        if process is not None:
            current = process.book_process(current, state, applied, heat, p)
        valid = _and(_and(_and(valid, ok), last), self._end_domain(current, p, active, xp=xp))
        if not idle:
            return jax.tree.map(lambda old, new: xp.where(valid, new, old), state, current), valid
        # Statically idle operators' fields pass through; the rest is selected.
        passed = {k for op in idle for k in op.STATE_AXES}
        selected = {
            k: xp.where(valid, getattr(current, k), getattr(state, k))
            for k in self.STATE_TYPE._fields
            if k not in passed
        }
        return state._replace(**selected), valid

    imex_step = split_step

    def _labelled_inner(self, current, inputs, dt, process, control, p, *, xp):
        """(state, valid, applied, heat): the inner step with labels (FR-42's stage 2), its
        transfers advancing the label owner's shares; applied and heat as the process gives them
        (None without one)."""
        labels = self.label_owner.rows(p)
        applied = heat = None
        if process is None:
            moved, ok, transfers = self.inner.checked_step(
                inputs[0], dt, inputs[1], inputs[2], p.active, labels=labels
            )
            moved, ok, transfers = self.inner.barrier((moved, ok, transfers), xp=xp)
        else:
            moved, ok, (applied, heat), transfers = self.inner.imex_step(
                inputs[0],
                dt,
                inputs[1],
                inputs[2],
                xp=xp,
                membrane_process=process.process(control, p),
                labels=labels,
            )
            moved, ok, applied, heat, transfers = self.inner.barrier(
                (moved, ok, applied, heat, transfers), xp=xp
            )
        end = current._replace(**moved._asdict())
        return self.label_owner.advance_inner(current, end, transfers, p, xp=xp), ok, applied, heat

    def _inner_keyword(self, op):
        """{"inner": the inner implementation object} for an operator that declares USES_INNER,
        else {} (static: every other call is unchanged)."""
        return {"inner": self.inner} if op.USES_INNER else {}

    def _passes_view(self, op):
        """Whether op's event or half-step receives the merged view (static): one that books at
        the view when a field input is provided, or a door S current reader (view_readers)."""
        return (op.BOOKS_AT_VIEW and self.field_inputs) or op in self.view_readers

    def _half_step(self, op, state, h, control, p, *, xp):
        """op's half-step; one that books at the view gets the current view when a field
        input is provided, and a door S current reader gets its reader view (static: otherwise
        the call is unchanged)."""
        keywords = self._inner_keyword(op)
        if self._passes_view(op):
            keywords["view"] = self._view_for(op, p, xp=xp)(state)
        labelled = op in self.label_reporters  # Static (FR-42): its moves advance the shares.

        def applied(at, h, control):
            """op's half-step from `at` as applied, with the label owner's shares advanced by its
            moves where op reports to one (FR-42, D289; otherwise today's call)."""
            if not labelled:
                return op.half_step(at, h, control, p, xp=xp, **keywords)
            labels = self.label_owner.labels(control, p, self.label_sources.get(op))
            new, ok, moves = op.half_step(at, h, control, p, xp=xp, labels=labels, **keywords)
            pool = self.label_pools.get(op)
            return self.label_owner.advance(at, new, moves, p, xp=xp, pool=pool), ok

        routes = self.rate_routes.get(op)
        if routes and op.LAW_ID in self.midpoint:  # Static: a self-moved route's target.
            # The explicit midpoint (self_moved_targets): a predictor over h/2 with the factors
            # from the state this half-step receives, then the half-step over h with the factors
            # from the predictor's state, second order where the target moves a route's source.
            # Every validity counts; FACTOR_RECORD holds the factors applied, the midpoint's.
            start, routed0, _ = self._routed_control(op, routes, state, control, p, xp=xp)
            mid, ok0 = op.half_step(state, h / 2, start, p, xp=xp, **keywords)
            control, routed, records = self._routed_control(op, routes, mid, control, p, xp=xp)
            new, ok = applied(state, h, control)
            valid = _and(_and(routed0, ok0), _and(ok, routed))
            return _recorded(new, records, xp=xp), valid
        if routes:  # Static (B1′): its routed rates, from the state this half-step receives.
            control, routed, records = self._routed_control(op, routes, state, control, p, xp=xp)
            new, ok = applied(state, h, control)
            return _recorded(new, records, xp=xp), _and(ok, routed)
        return applied(state, h, control)

    def _routed_control(self, op, routes, state, control, p, *, xp):
        """(control with each of op's routed fields times its sources' factors, in declared
        order, from `state`; their validity; the sources' exact records of the factors applied,
        {FACTOR_RECORD field: (values, mask)}) for B1′'s rate routes. A source that declares no
        route on a field in this definition gives None and leaves it as scheduled (static)."""
        fields, valid, records = {}, None, {}
        for source, name in routes:
            keywords = self._quantity_keywords(source, p, xp=xp)  # R3 (static: {} for most).
            out = source.rate_factors(state, p, op.LAW_ID, name, xp=xp, **keywords)
            if out is None:
                continue
            factor, ok = out
            fields[name] = fields.get(name, getattr(control, name)) * factor
            valid = _and(valid, ok)
            if source.FACTOR_RECORD:
                record = source.factor_record(state, p, op.LAW_ID, name, xp=xp, **keywords)
                records[source.FACTOR_RECORD] = _merged(
                    records.get(source.FACTOR_RECORD), record, xp=xp
                )
        return (control._replace(**fields) if fields else control), valid, records

    def _control_factor_checks(self, current, p, *, xp):
        """(validity, current with its records) of the factor sources at the control view (B1′):
        each one's factor_valid, and each FACTOR_RECORD filled with the factors applied there
        (static: a source without either changes nothing). A factor operator that reads at the
        control view gets view= in both (R2), and a reader of quantities quantities= (R3)."""
        valid, records = None, {}
        views = self._factor_views(p, xp=xp) if self.factor_fields else {}
        for op in self.factors:
            keywords = {"view": views[op]} if op in views else {}
            keywords |= self._quantity_keywords(op, p, xp=xp)  # R3 (static: {} for most).
            valid = _and(valid, op.factor_valid(current, p, xp=xp, **keywords))
            if op.FACTOR_RECORD:
                record = op.factor_record(current, p, None, None, xp=xp, **keywords)
                records[op.FACTOR_RECORD] = _merged(records.get(op.FACTOR_RECORD), record, xp=xp)
        return valid, _recorded(current, records, xp=xp)

    def _end_domain(self, state, p, operators, *, xp):
        """Domain of the step's end state: the inner one at the view if a split moved it."""
        valid = None
        if self.domain_views:
            view = (
                self.view(p, state, xp=xp)  # Static: with S5's closers, the full view (§2).
                if self.closers and self._live_closers(p)
                else self.inner.view(p, state, self.domain_views, xp=xp)
            )
            valid = self.inner.domain_valid(self.inner.inner_state(state), view, p.active, xp=xp)
        for op in operators:
            valid = op.domain_valid(state, p, valid, xp=xp)
        return valid

    # ------------------------------------------------------------ readouts

    def readouts(self, state, control, p, *, xp=jnp):
        """The inner readouts at the view (with the in-step process) plus the operators' rates.

        Validity folds the operators' rate validity, then their state and control
        checks, then the finiteness of their rates; the energy-balance rate adds their
        terms last (the frozen models' order).
        """
        inner_control = self.control_view(control, state, p, xp=xp)
        view = self.view(p, state, xp=xp)
        hook = {}
        if self.process_operator is not None:
            hook = dict(membrane_process=self.process_operator.process(control, p))
        v = self.inner.readouts(self.inner.inner_state(state), inner_control, view, xp=xp, **hook)
        computed = [
            op.rates(state, control, p, view, xp=xp, **self._inner_keyword(op))
            for op in self.operators
        ]
        derivative = list(v.derivative)
        for op, (rates, _, _) in zip(self.operators, computed, strict=True):
            derivative.extend(rates[k] for k in op.STATE_AXES)
        # The composite's own fields (Q6 (b)'s records and moves) change only at retiring events.
        derivative.extend(
            xp.zeros_like(getattr(state, name))
            for name in (*self.KIND_RECORDS.values(), *self.KIND_MOVED.values())
        )
        valid = v.valid
        for _, ok, _ in computed:
            valid = _and(valid, ok)
        for op in self.operators:
            valid = op.rate_checks(state, control, p, valid, xp=xp)
        for op, (rates, _, _) in zip(self.operators, computed, strict=True):
            if op.FINITE_RATES:
                for k in op.STATE_AXES:
                    valid &= xp.all(xp.isfinite(rates[k]))
        energy = v.field.energy_balance_pJ_s
        for op, (_, _, readout) in zip(self.operators, computed, strict=True):
            term = op.energy_rate(readout, p, xp=xp)
            if term is not None:
                energy = energy + term
        field = v.field._replace(energy_balance_pJ_s=energy, converged=valid)
        blocks = [r for op, (_, _, r) in zip(self.operators, computed, strict=True) if op.READOUT]
        return self.VALUES_TYPE(field, self.STATE_TYPE(*derivative), v, *blocks, valid)

    def field_values(self, state, control, p, *, xp=jnp):
        return self.readouts(state, control, p, xp=xp).field

    # ------------------------------------------------------------ FR-34 in a composite (D265)

    def clamp_inputs(self, state, control, p, *, xp=np):
        """(inner state, control view, layout view): what the composite's own readouts hands @3,
        so a clamped evaluation runs at the controls and layout the step runs at. The control view
        is the stored control times the operators' CONTROL_FACTORS (species_regulated_availability
        @1's writes and @2's step-view routes among them, held as the step holds them); the layout
        view is its providers' (membrane state's areas, capacitances and abundances among them).
        The stored control and layout are not what the step runs at (D265 finding 1)."""
        return (
            self.inner.inner_state(state),
            self.control_view(control, state, p, xp=xp),
            self.view(p, state, xp=xp),
        )

    def clamped_channel_flux(self, state, control, p, voltages_V, *, xp=np, block=False):
        """FR-34 in a composite (D265 finding 1): @3's clamped_channel_flux, each channel
        population's outward flux [species, channel] (fmol/s) and current [channel] (A,
        outward-positive) at the patch voltages given [membrane] (V; a scalar applies to every
        patch), at the composite's clamp_inputs; @3 then applies its structure's stage read and
        routing door. Given the stored control and layout instead, @3's helper loses every
        operator factor: a population held at 0.5 by species_regulated_availability@1 read
        11.10328 pA at -50 mV, where the composite runs at 5.55164 pA. Pure: it records nothing.
        block (FR-51): also the blocked populations' terms at the same inputs, as @3 gives them."""
        inner_state, inner_control, view = self.clamp_inputs(state, control, p, xp=xp)
        clamp = (
            getattr(self.inner, "clamped_channel_flux", None) or pump3.ionic.clamped_channel_flux
        )
        return clamp(inner_state, inner_control, view, voltages_V, xp=xp, block=block)

    def clamped_kind(self, function, state, control, p, voltages_V, *, xp=np):
        """FR-34's kinds in a composite (D265 finding 1's check: the same gap): a kind's clamped
        evaluation, cells.passive_routes@1's clamped_flux or cells.transporter@1's clamped_rates,
        at the composite's clamp_inputs after @3's stage read and routing door of its structure,
        the path @3's readouts takes to the kinds' rates. The kinds' own controls take no operator
        factor today (CONTROL_FACTORS name junction and channel only), but their read, the door
        and the layout providers' views (a patch's area) are the step's only here."""
        ionic = pump3.ionic
        inner_state, inner_control, view = self.clamp_inputs(state, control, p, xp=xp)
        structure = getattr(self.inner, "structure", None)
        kinds = ionic._kinds(structure)
        read = ionic._stage_read(inner_state, view, kinds, xp=xp)[0] if kinds else inner_state
        if kinds and structure.routes:
            inner_control = ionic._route(structure, kinds, read, inner_control, view, xp=xp)[0]
        return function(read, inner_control, view, voltages_V, xp=xp)

    def rhs(self, state, control, p, active, *, xp=jnp):
        values = self.readouts(state, control, p, xp=xp)
        return self.STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))

    def _domain(self, state, p, active, *, xp=jnp):
        if self.closers and self._live_closers(p):
            # Static: S5's closers (§2). Closed slots hold @3's padding, which the declared
            # layout does not admit (a closed contact's gate 0 below its declared minimum).
            layout = self.view(p, state, xp=xp)
        elif self.domain_views:
            layout = self.inner.view(p, state, self.domain_views, xp=xp)
        else:
            layout = self.inner.inner_layout(p)
        valid = self.inner.domain_valid(self.inner.inner_state(state), layout, active, xp=xp)
        for op in self.operators:
            valid = op.domain_valid(state, p, valid, xp=xp)
        return valid

    def control_domain_valid(self, state, control, p, active, *, xp=jnp):
        valid = self.domain_valid(state, p, active, xp=xp)
        for op in self.operators:
            valid = _and(valid, op.control_valid(control, p, xp=xp))
        if xp is np:
            if not valid:
                return np.asarray(False)
            try:
                return np.asarray(self.readouts(state, control, p, xp=np).valid)
            except np.linalg.LinAlgError:
                return np.asarray(False)
        return jax.lax.cond(
            valid, lambda: self.readouts(state, control, p).valid, lambda: jnp.asarray(False)
        )

    # ------------------------------------------------------------ definition checks

    def check_definition(self, spec):
        """Contract refusals that need the definition, then every scheduled control.

        The inner definition was checked by its own parser. Each change of the
        schedule union is checked on the compact initial state (the domain and a
        valid field), then each operator's own checks run.

        The RK4 composition rule comes first: it reads only the solver, so it refuses from the
        declarations before the definition is read. Then the definition's declared kinds must be
        the inner structure's (schema A): a composition bound without the definition's structure
        (the full catalogue) would drop them.

        The species registry's checks run next, ahead of every other check of the definition: the
        inner parser's hook sees the inner definition only, so an operator's in-step mover of a
        two-form row, or an operator that names one, is refused here (registry/species_registry.py;
        D176).

        Beside declared kinds, an operator's in-step process (moves_in_step) that writes a row a
        kind holds is refused (held_row_errors, gap 8), and so is one that writes a row an
        exact-booked passive route moves, read from the bound layout (exact_row_errors, §7.5
        version 1).
        """
        solver = spec.execution.solver
        if solver == "rk4" and self.coupled:
            if (
                self.events
                or self.STATE_DTYPES
                or any(op.SPLIT and op.RK4 == "split" for op in self.operators)
            ):
                raise ConfigError(
                    "An RK4 composition with a coupled operator cannot hold event maps, "
                    "split-only parts or integer state"
                )
        kinds = tuple(kind_id for kind_id, _ in getattr(spec.model, "kinds", ()))
        if kinds != tuple(getattr(self.inner, "KINDS", ())):
            raise ConfigError(
                f"The definition declares the kinds {list(kinds)}, but the composition's inner "
                f"structure declares {list(getattr(self.inner, 'KINDS', ()))}"
            )
        species_registry.check_definition(spec)
        pairs = [(op, d) for op, d, _ in entries(spec)]
        scoped = (
            scope_errors(self.inner, pairs, spec)
            + rate_route_definition_errors(pairs)
            + quantity_read_definition_errors(pairs)
        )
        if scoped:
            raise ConfigError("Invalid operator composition: " + "; ".join(scoped))
        # The operators' in-step writers beside declared kinds (held_row_errors,
        # exact_row_errors): only with kinds and an in-step process, so no world without them
        # makes either call.
        writing = bool(kinds) and self.process_operator is not None
        held = held_row_errors(pairs, spec) if writing else []
        if held:
            raise ConfigError("Invalid operator composition: " + "; ".join(held))
        dt, end = spec.execution.dt, spec.experiment.end_time
        for op, _, schedule in entries(spec):
            if op.EVENT and any(
                not 0 < t < end or on_grid(t, dt) is None for t in op.schedule_times(schedule)
            ):
                raise ConfigError(
                    f"{op.LAW_ID} event times must lie inside the horizon and {ON_THE_GRID}"
                )
        small = compact(spec)
        state, p = self.initial_values(small)
        exact = exact_row_errors(pairs, spec, p) if writing else []
        if self.process_operator is not None:  # D280: the faces' exact booking (static).
            exact += exact_face_row_errors(pairs, spec, getattr(self.inner, "structure", None))
        if exact:
            raise ConfigError("Invalid operator composition: " + "; ".join(exact))
        if self.field_inputs:
            x = spec.execution
            self.inner.check_field_inputs(p, x.capacity + x.extracellular_capacity)
        controls = composite_spec.control_values(small, [c.time for c in small.experiment.changes])
        with np.errstate(all="ignore"):
            for i in range(len(controls.membrane)):
                control = self.CONTROL_TYPE(*(v[i] for v in controls))
                if not self.control_domain_valid(state, control, p, p.active, xp=np):
                    raise ConfigError("Initial composite domain invalid")
        for op, declaration, schedule in entries(spec):
            op.check_definition(spec, declaration, schedule, self)

    def check_steps(self, spec, steps, controls):
        """The inner step checks on the definition the operators declare, then theirs
        (bind_step_checks for one chunk; the checks read no controls)."""
        self.bind_step_checks(spec)(steps)

    def bind_step_checks(self, spec):
        """check_steps bound to one definition, for every chunk of its clock (core/grid).

        The inner model's bound checks on the operator-adjusted check spec (each operator's
        inner_check_spec: water's minimum volumes, replacement's worst case; v2 design R5),
        then each operator's bound checks, in declared order. What they read from the
        definition is evaluated once, at first use; each chunk passes its steps.
        """
        check_spec = spec
        for op, declaration, schedule in entries(spec):
            check_spec = op.inner_check_spec(check_spec, spec, declaration, schedule)
        inner = self.inner.bind_step_checks(check_spec)
        own = tuple(
            op.bind_check_steps(spec, declaration, schedule, self)
            for op, declaration, schedule in entries(spec)
        )

        def bound(steps):
            inner(steps)
            for check in own:
                check(steps)

        return bound

    # ------------------------------------------------------------ ledgers

    def _adjusted(self, row, p, *, xp):
        for op in self.operators:
            row = op.adjust_inner(row, p, xp=xp)
        if self.kind_lifecycle:  # Static (Q6 (b)): the records added back, the moves taken out.
            row = row._replace(
                **{k: getattr(row, k) + getattr(row, r) for k, r in self.KIND_RECORDS.items()},
                **{k: getattr(row, k) - getattr(row, m) for k, m in self.KIND_MOVED.items()},
            )
        return row

    def _lifecycle(self, state, maps, masks, *, xp):
        """(state, valid): the kinds' lifecycle fields after a retiring event's division and
        retirement (the closer's maps and masks), by role, through the single implementation
        (pump_composite_adapter.lifecycle_split, then lifecycle_retire), with the records and the
        moved accumulators written. The retiring operator calls it (TAKES_LIFECYCLE)."""
        table = self.kind_lifecycle
        values = {k: getattr(state, k) for k in table}
        internal = self.KIND_INTERNAL
        split, valid = pump3.lifecycle_split(values, table, maps, xp=xp, internal=internal)
        records = {k: (r, getattr(state, r)) for k, r in self.KIND_RECORDS.items()}
        retired, kept = pump3.lifecycle_retire(
            split, table, masks, records, xp=xp, internal=internal
        )
        moved = {
            m: getattr(state, m) + (retired[k] - values[k]) for k, m in self.KIND_MOVED.items()
        }
        return state._replace(**retired, **kept, **moved), valid

    def _owned_lifecycle(self, p, state, maps, masks, *, xp):
        """(state, valid): the kinds' lifecycle where their table is non-empty (_lifecycle), then
        each owned divider's divide_owned in declared order (FR-43 part 3, D315; static: passed in
        place of _lifecycle only where an owned divider is composed)."""
        valid = None
        if self.kind_lifecycle:
            state, valid = self._lifecycle(state, maps, masks, xp=xp)
        for op in self.owned_dividers:
            state, ok = op.divide_owned(state, maps, masks, p, xp=xp)
            valid = _and(valid, ok)
        return state, xp.asarray(True) if valid is None else valid

    def _history_kept(self, before, after, *, xp):
        """Whether every kind history field plus its record is unchanged across a retiring event,
        element by element and exactly (the lead's ruling 4 (b)): a history no ledger reads, such as
        a cycle count, is then still refused if a retirement loses it."""
        ok = xp.asarray(True)
        for field, record in self.KIND_RECORDS.items():
            was = getattr(before, field) + getattr(before, record)
            ok &= xp.all(getattr(after, field) + getattr(after, record) == was)
        return ok

    def _ledgers(self, state, p, *, xp, own, adjust=True):
        """The inner ledgers (declared layout) with the operators' terms, in declared
        order, then (own) the operators' own ledgers; one ledger call per operator.
        adjust=False: state is already the adjusted row (a retiring composition's checks)."""
        row = self._adjusted(state, p, xp=xp) if adjust else state
        inner = self.inner.balances if xp is np else self.inner.device_balances
        result = inner(self.inner.inner_state(row), self.inner.inner_layout(p))
        extra = {}
        for op in self.operators:
            result, ledgers = op.ledger_terms(result, row, p, xp=xp)
            extra |= ledgers
        if self.owns_view_energy and self._live_closers(p):
            energy, electrode = self._view_energy_terms(row, p, xp=xp)[:2]
            result["energy"] = result["energy"] + energy
            result["electrode"] = result["electrode"] - electrode
        for op in self.operators:
            if op.LAW_ID in self.writers_of:
                extra |= self._with_writers(op, {k: extra[k] for k in op.LEDGERS}, row, p, xp=xp)
        return result | extra if own else result

    def _view_energy_terms(self, row, p, *, xp):
        """The energy rule at the view with a closer (S5 design §3.6 point 4, §5.3).

        (energy pJ, electrode C [outside], energy magnitude pJ, electrode magnitude C [outside]):
        adapter.view_capacitor_terms brings @3's capacitor term on the declared layout to the
        physical 1/2 sum C V^2 at the view; the bound references then measure it, and the
        clamps' plate charges, from the view of the initial state, so the energy is
        1/2 sum C V^2(t) - 1/2 sum C V^2(0) and the electrode residual is transferred minus
        (plates_view(t) - plates_view(0)).
        """
        view = self.view(p, row, xp=xp)
        energy, electrode, e_mag, q_mag = self.inner.view_capacitor_terms(
            row, view, self.inner.inner_layout(p), xp=xp
        )
        e_ref, q_ref = p.view_energy_reference_pJ, p.view_plate_reference_C
        return (
            energy + e_ref,
            xp.where(p.reservoir, electrode + q_ref, 0.0),
            e_mag + xp.abs(e_ref),
            xp.where(p.reservoir, q_mag + xp.abs(q_ref), 0.0),
        )

    def _with_writers(self, owner, values, row, p, *, xp, magnitudes=False):
        """An owner's own ledgers (or their magnitudes), {name: value}, with the terms
        of the later operators that write its accepted fields (v2 design §1.4)."""
        for writer, ledgers in self.writers_of.get(owner.LAW_ID, ()):
            add = writer.external_magnitude_terms if magnitudes else writer.external_ledger_terms
            terms = add({k: values[k] for k in ledgers}, row, p, xp=xp)
            values = values | {k: terms[k] for k in ledgers}
        return values

    def _own_ledgers(self, op, row, p, *, xp):
        values = op.own_ledgers(row, p, xp=xp)
        return (
            self._with_writers(op, values, row, p, xp=xp)
            if op.LAW_ID in self.writers_of
            else values
        )

    def _own_magnitudes(self, op, row, p, *, xp):
        values = op.own_magnitudes(row, p, xp=xp)
        if op.LAW_ID not in self.writers_of:
            return values
        named = dict(zip(op.LEDGERS, values, strict=True))
        named = self._with_writers(op, named, row, p, xp=xp, magnitudes=True)
        return tuple(named[k] for k in op.LEDGERS)

    def inner_balances(self, state, p, *, adjust=True):
        """The inner ledgers with the operators' terms (host; the inner row checks)."""
        return self._ledgers(state, p, xp=np, own=False, adjust=adjust)

    def balances(self, state, p, *, adjust=True):
        return self._ledgers(state, p, xp=np, own=True, adjust=adjust)

    def device_balances(self, state, p, *, adjust=True):
        return self._ledgers(state, p, xp=jnp, own=True, adjust=adjust)

    def inner_magnitudes(self, row, p, *, xp=np, adjust=True):
        adjusted = self._adjusted(row, p, xp=xp) if adjust else row
        magnitudes = list(
            self.inner.magnitudes(
                self.inner.inner_state(adjusted), self.inner.inner_layout(p), xp=xp
            )
        )
        for op in self.operators:
            magnitudes = op.magnitude_terms(magnitudes, row, p, xp=xp)
        if self.owns_view_energy and self._live_closers(p):
            _, _, energy, electrode = self._view_energy_terms(row, p, xp=xp)
            magnitudes[4] = electrode if magnitudes[4] is None else magnitudes[4] + electrode
            magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return tuple(magnitudes)

    def magnitudes(self, row, p, *, xp=np, adjust=True):
        inner = self.inner_magnitudes(row, p, xp=xp, adjust=adjust)
        own = tuple(
            m for op in self.own_ledger_operators for m in self._own_magnitudes(op, row, p, xp=xp)
        )
        return (*inner, *own)

    def ledger_limits(self, row, p, tol, rtol, *, steps, magnitudes, xp=np):
        # magnitudes() holds the inner model's magnitudes, then one per own ledger of each
        # operator. The inner model's are what is left once the operators' are counted from the
        # end: they can be fewer than its ledgers, since a kind's own ledgers are bounded by its
        # ledger_bounds, without magnitudes (E, CORE_SEAMS §7.3; the fourth review's finding 1).
        count = len(magnitudes) - sum(len(op.LEDGERS) for op in self.own_ledger_operators)
        flows, bounds = self.inner.ledger_limits(
            row,
            p,
            tol,
            rtol,
            steps=steps,
            magnitudes=magnitudes[:count],
            xp=xp,
            flow_fields=self.ENERGY_FLOW_FIELDS,
        )
        if not self.own_ledger_operators:
            return flows, bounds
        extra, offset = [], count
        for op in self.own_ledger_operators:
            k = len(op.LEDGERS)
            extra.extend(op.own_bounds(magnitudes[offset : offset + k], steps))
            offset += k
        return flows, (*bounds, *extra)

    def check_values(self, state, spec, steps=None):
        """Host checks of every accepted row (one row or a [time, ...] history).

        The inner model's row checks with the operators' terms, then each
        operator's own ledgers against their bounds (in declared order).
        """
        _, p = self.initial_values(spec)
        domain = self.domain_valid
        if self._live_retiring(p):  # S5 design §3.5: every check reads the record added back.
            self._check_actual_domains(state, p)
            domain = _checked_above
            state = self._adjusted(state, p, xp=np)
            balances = lambda s, q: self.inner_balances(s, q, adjust=False)  # noqa: E731
            magnitudes = lambda r, q, *, xp=np: self.inner_magnitudes(r, q, xp=xp, adjust=False)  # noqa: E731
        else:
            balances, magnitudes = self.inner_balances, self.inner_magnitudes
        diagnostics = self.inner.checked_rows(
            state,
            spec,
            p,
            domain=domain,
            balances=balances,
            magnitudes=magnitudes,
            dissipation=self.DISSIPATION_FIELDS,
            steps=steps,
            ledgers=self.inner,  # The inner ledgers' lists, from its object (§7.4 (p)).
        )
        if not self.own_ledger_operators:
            return diagnostics
        rows = (
            [state]
            if state.amount_increment.ndim == 2
            else [
                self.STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))
            ]
        )
        counts = [0] * len(rows) if steps is None else list(steps)
        extra = {"max_" + k: 0.0 for op in self.own_ledger_operators for k in op.LEDGER_DIAGNOSTICS}
        with np.errstate(all="ignore"):
            for row, count in zip(rows, counts, strict=True):
                for op in self.own_ledger_operators:
                    values = self._own_ledgers(op, row, p, xp=np)
                    bounds = op.own_bounds(self._own_magnitudes(op, row, p, xp=np), count)
                    for (name, value), key, bound in zip(
                        values.items(), op.LEDGER_DIAGNOSTICS, bounds, strict=True
                    ):
                        if (
                            not np.isfinite(value).all()
                            or not np.isfinite(bound).all()  # The fourth review's finding 2.
                            or np.any(np.abs(value) > bound)
                        ):
                            raise NumericalError(op.LEDGER_MESSAGE + name)
                        key = "max_" + key
                        extra[key] = max(extra[key], float(np.max(np.abs(value), initial=0)))
        return diagnostics | extra

    def _check_actual_domains(self, state, p):
        """A retiring composition's domain, on each actual row at its view (S5 design §2): the
        adjusted rows hold the retired history on closed slots, where @3 admits only padding."""
        rows = (
            [state]
            if state.amount_increment.ndim == 2
            else [
                self.STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))
            ]
        )
        with np.errstate(all="ignore"):
            for row in rows:
                if not self.domain_valid(row, p, p.active, xp=np):
                    raise NumericalError(DOMAIN_MESSAGE)

    def device_failure_message(self, check):
        for op in self.own_ledger_operators:
            if check in op.LEDGERS:
                return op.LEDGER_MESSAGE + check
        return self.inner.device_failure_message(check)

    def device_checks(self, previous, row, p, constants, steps, *, margins=False):
        """check_values' tests for one accepted row on the device: (failed, diagnostics).

        With a retiring operator both rows are the adjusted ones (the record added back), so
        the domain, every ledger and each heat element's monotonicity read the history as if
        nothing moved; the balances and magnitudes then do not adjust again (S5 design §3.5).
        margins=True also returns each ledger's ratio to its bound (row_checks).
        """
        if self._live_retiring(p):
            domain = self.domain_valid(row, p, p.active, xp=jnp)  # The actual row, at its view.
            return row_checks(
                self._adjusted(previous, p, xp=jnp),
                self._adjusted(row, p, xp=jnp),
                p,
                constants,
                steps,
                domain_valid=lambda *_, **__: domain,
                balances=lambda r, q: self.device_balances(r, q, adjust=False),
                limits=self.ledger_limits,
                magnitudes=lambda r, q, *, xp: self.magnitudes(r, q, xp=xp, adjust=False),
                dissipation=self.DISSIPATION_FIELDS,
                ledgers=self,
                margins=margins,
            )
        return row_checks(
            previous,
            row,
            p,
            constants,
            steps,
            domain_valid=self.domain_valid,
            balances=self.device_balances,
            limits=self.ledger_limits,
            magnitudes=self.magnitudes,
            dissipation=self.DISSIPATION_FIELDS,
            ledgers=self,
            margins=margins,
        )

    # ------------------------------------------------------------ observations

    def observe_history(self, times, history, layout, requested, spec):
        """The inner observations of each row at its view, then each operator's columns.

        Each operator observes with the controls its step runs at (D264, a tester's findings):
        - **a routed target's** controls times its rate routes' factors at the row's state
          (_routed_control), so an exported rate is the one the step ran at, not the scheduled
          one (finding 1: a receptor-routed reaction exported its unrouted rate);
        - **at an occupant event's row** (a time replacement@1's events land on, OCCUPANT_EVENTS)
          the controls held over the step that ended there, at t - dt. The row's state is that
          step's end, before the event, the departing occupant's, so state and controls are one
          occupant's; the newcomer appears from the next row on (finding 2: the event row mixed
          the departing cell's substrate with the newcomer's multiplier).
        The inner observations keep the row's own controls."""
        p = type(layout)(*(np.asarray(v) for v in layout))
        requested = np.asarray(requested, dtype=float)
        if any(t not in times for t in requested):
            raise ConfigError("Composite observations require accepted times")
        controls = composite_spec.control_values(spec, requested)
        events = occupant_event_times(spec)
        departing = [j for j, t in enumerate(requested) if float(t) in events]
        held = (
            composite_spec.control_values(
                spec, [float(requested[j]) - spec.execution.dt for j in departing]
            )
            if departing
            else None
        )
        base, records = projection(spec), []
        for j, t in enumerate(requested):
            i = int(np.flatnonzero(times == t)[0])
            state = self.STATE_TYPE(*(np.asarray(v[i]) for v in history))
            control = self.CONTROL_TYPE(*(v[j] for v in controls))
            if j in departing:
                k = departing.index(j)
                operator_control = self.CONTROL_TYPE(*(v[k] for v in held))
            else:
                operator_control = control
            view = self.view(p, state, xp=np)
            inner_spec = base
            if self.factored:
                effective = self.control_view(control, state, p, xp=np)
                inner_spec = held_schedules(base, effective, self.factored)
            one = self.inner.STATE_TYPE(*(getattr(state, k)[None] for k in self.inner.STATE_FIELDS))
            observed = self.inner.observe_history(
                np.array([t]), one, view, np.array([t]), inner_spec
            )
            row = {k: v[0] for k, v in vars(observed).items()}
            for op in self.operators:
                keywords = self._quantity_keywords(op, p, xp=np)  # R3 (static: {} for most).
                observed_control = operator_control
                routes = self.rate_routes.get(op)
                if routes:  # B1': the routed rates the step runs at, at the row's state.
                    observed_control, _, _ = self._routed_control(
                        op, routes, state, operator_control, p, xp=np
                    )
                columns = op.observe(row, state, observed_control, p, view, self, spec, **keywords)
                if set(columns) != self.observed_keys[op.LAW_ID]:
                    undeclared = sorted(set(columns) ^ self.observed_keys[op.LAW_ID])
                    raise ConfigError(f"{op.LAW_ID} observes {undeclared} against its declaration")
                row.update(columns)
            records.append(row)
        if records:
            return self.Observations(
                *(np.stack([r[k] for r in records]) for k in self.OBSERVATION_FIELDS)
            )
        sample = self.observe_history(
            times[:1], self.STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec
        )
        return self.Observations(
            *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
        )

    def ensemble_voltage(self, state, layout, spec, time):
        controls = composite_spec.control_values(spec, [time])
        control = self.CONTROL_TYPE(*(v[0] for v in controls))
        p = type(layout)(*(np.asarray(v) for v in layout))
        v = self.field_values(self.STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
        if not v.converged:
            raise NumericalError("Composite ensemble endpoint invalid")
        return v.rates.membrane_voltage_V[p.membrane_active]

    def summarize(self, history, diagnostics, spec):
        solver = spec.execution.solver
        coupled = solver == "rk4" and self.coupled
        result = self.inner.summarize(history, diagnostics, projection(spec)) | {
            "model": MODEL_ID,
            "inner_model": spec.model.inner_model,
            "operators": list(self.laws),
            "composition": identity(spec.model),
            "composition_status": composite_spec.DEVELOPMENT_STATUS,
            "state_fields": list(self.STATE_TYPE._fields),
            "time_integrator": solver,
            "splitting": "coupled rhs (rk4)" if coupled else SPLITTING_ID,
            "operator_steps": {op.LAW_ID: op.STEP_ID for op in self.operators},
        }
        for op, declaration, schedule in entries(spec):
            result |= op.summary(spec, declaration, schedule, history)
        return result
