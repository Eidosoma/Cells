"""Composition's M1: the composite's rules for current reads (no long runs).

docs/OPERATOR_COMPOSITION_DESIGN.md §4.1 (C1–C4), §5 and §12 (E1, E2), D191. Every planted operator
is a test double and none is registered. Each admission is checked beside a refused twin.
* C1, the fallback: a current read of a field no operator changes is admitted, reads the declared
  value and receives no view; a read of a name that is no view field is refused;
* C2, the stage-aware order: a change at another stage is seen whatever the declared order (the
  events run before the split parts' first halves, and an event reads the previous step's end); a
  later change at the reader's own stage is refused, at the structure check, or per slot where both
  are scoped;
* the table of changes (pump_composite.view_changes): a closer changes every mask and padded field,
  since close() propagates and pads; a writer of a provider's accepted state changes what it
  provides, at each stage it runs at; a provider also changes at the stages of what it reads;
* C3, per-stage read modes: one field read current at one stage and as a reference at another; the
  contract's refusals of malformed reads and of a stage none of an operator's parts runs at;
* C4, the reader view: a door S reader's part receives its read fields only, bitwise the full
  view's, formed without the field refresh; an operator that books at the view keeps the full view;
* E1: a volume reader joins water with no edit to water and sees its merged volume bitwise; alone it
  reads the declared volume and receives no view. Joining the full cycle waits for M2–M4;
* E2: a closer of one cell by an event, with a reader of the masks placed before it, which C2 admits
  and which sees the cell and its patches closed. Water and turnover idling on that slot waits for
  M2 and M3. E3, a scoped second volume changer beside water, waits for M2: water's change of the
  volume is a replacement on every slot until then.
"""

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS
from cells.operators.contract import Change, Operator, Read, check_declarations, reads_of
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import secreted_species_fixtures as fx

jax.config.update("jax_enable_x64", True)

WATER = "cells.operator.ideal_osmosis_linear_compliance_water@1"
STATE = "cells.operator.membrane_entity_state@1"
INSERTION = "cells.operator.scheduled_membrane_insertion@2"
VOLUME = "extracellular_volume"


def reader(law, field, *declared, parts=("split",), slots=None, **attributes):
    """A planted reader of `field`: its SCOPED_READS entry is `declared` (one Read, or several at
    distinct stages), it runs `parts`, and it records the view each part receives."""
    modes = {r.mode for r in declared}
    body = dict(
        LAW_ID=law,
        EVENT="event" in parts,
        SPLIT="split" in parts,
        RK4="split" if "split" in parts else None,
        VIEW_READS=(field,) if "current" in modes else (),
        CONFLICTS_VIEW=(field,) if "fixed" in modes else (),
        SCOPED_READS={field: declared[0] if len(declared) == 1 else tuple(declared)},
        received=[],
        **attributes,
    )

    def half_step(self, state, h, control, p, *, xp, view=None):
        self.received.append(view)
        return state, None

    def event(self, state, control, p, *, xp, view=None):
        self.received.append(None if view is None else view(state))
        return state, None

    def read_slots(self, spec, declaration):
        return {field: tuple(slots or ())}

    body.update(half_step=half_step, event=event, read_slots=read_slots)
    return check_declarations(type("Reader", (Operator,), body))()


def provider(
    law,
    field,
    value,
    *,
    stage="event",
    contribution="replace",
    scoped=False,
    slots=(),
    **attributes,
):
    """A planted changer of `field` at `stage`: `value` on every slot, taken on `slots` when
    scoped."""

    def view(self, state, p, q, *, xp):
        return {field: xp.full_like(getattr(p, field), value)}

    def changed_slots(self, spec, declaration):
        return {field: tuple(slots)}

    def view_slots(self, p, *, xp):
        mask = np.zeros(np.shape(getattr(p, field))[-1], dtype=bool)
        mask[list(slots)] = True
        return {field: xp.asarray(mask)}

    body = dict(
        LAW_ID=law,
        EVENT=stage == "event",
        SPLIT=stage == "split",
        RK4="split" if stage == "split" else None,
        VIEW_FIELDS=(field,),
        VIEW_CHANGES={field: Change(contribution, stage, scoped=scoped)},
        view=view,
        changed_slots=changed_slots,
        view_slots=view_slots,
        **attributes,
    )
    return check_declarations(type("Provider", (Operator,), body))()


def closer(law, cells, *, stage="event"):
    """A planted closer of `active` at the cells `cells` (cells.operator.stub_closer@1 of §12's E2)."""

    def closures(self, state, p, q, *, xp):
        mask = np.ones(np.shape(q.active), dtype=bool)
        mask[list(cells)] = False
        return {"active": xp.asarray(mask)}

    body = dict(
        LAW_ID=law,
        EVENT=stage == "event",
        SPLIT=stage == "split",
        RK4="split" if stage == "split" else None,
        CLOSES=("active",),
        VIEW_CHANGES={"active": Change("and", stage)},
        closures=closures,
    )
    return check_declarations(type("Closer", (Operator,), body))()


def structure(*operators):
    return pump_composite.structure_errors(adapter, operators)


def late(reader_law, field, stage, changer_law):
    return (
        f"{reader_law} reads the view {field} at stage {stage} before {changer_law} changes it "
        "there"
    )


@pytest.fixture(scope="module")
def two_cells():
    """Two cells on one finite node and a held bath, each with a wall and a contact patch."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")),
        faces=(),
        end=0.004,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6),
    )
    spec = parse_spec(raw)
    return (spec, *get_model(spec.model).initial_values(spec))


@pytest.fixture(scope="module")
def water_cell():
    """The heredity cell with water (pump_water_fixtures' approved arm), as a composition."""
    raw = water_fixtures.heredity_cell("H", dt=1e-3, end_time=0.004)
    spec = parse_spec(cs.frozen_definition(water_fixtures.with_water(raw)))
    model = get_model(spec.model)
    return (model, *model.initial_values(spec))


# ------------------------------------------------------------------ C1, the fallback


def test_a_current_read_of_a_field_no_operator_changes_reads_the_declared_value(two_cells):
    _, state, p = two_cells
    alone = reader("cells.operator.test_alone@1", "volume", Read("current", "split"))
    assert structure(alone) == []
    composition = pump_composite.Composition(adapter, (alone,))
    assert alone not in composition.view_readers and not composition._passes_view(alone)
    composition._half_step(alone, state, 0.5e-3, None, p, xp=np)
    assert alone.received == [None]  # No view: its call is unchanged, and it reads p.
    # Its refused twin: the same reader before a changer at its own stage.
    split = provider("cells.operator.test_split@1", "volume", 2.0, stage="split")
    assert structure(alone, split) == [
        late("cells.operator.test_alone@1", "volume", "split", "cells.operator.test_split@1")
    ]
    typo = reader("cells.operator.test_typo@1", "volume_pl", Read("current", "split"))
    assert structure(typo) == [
        "cells.operator.test_typo@1 reads the view volume_pl, which is not an inner view field"
    ]


# ------------------------------------------------------------------ C2, the stage-aware order


@pytest.mark.parametrize(
    "read_stage, change_stage, refused",
    [
        ("split", "event", False),  # The events run before the first halves.
        ("event", "split", False),  # An event reads the previous step's end.
        ("split", "split", True),  # The later operator's first half has not run.
        ("event", "event", True),  # The later operator's event has not run.
    ],
)
def test_a_later_change_is_refused_only_at_the_readers_own_stage(read_stage, change_stage, refused):
    current = reader(
        "cells.operator.test_reader@1", VOLUME, Read("current", read_stage), parts=(read_stage,)
    )
    change = provider("cells.operator.test_change@1", VOLUME, 2.0, stage=change_stage)
    assert structure(change, current) == []  # An earlier change: admitted at every stage.
    expected = (
        [late("cells.operator.test_reader@1", VOLUME, read_stage, "cells.operator.test_change@1")]
        if refused
        else []
    )
    assert structure(current, change) == expected


def test_scoped_pairs_are_ordered_per_slot_and_per_stage(two_cells):
    spec, _, _ = two_cells

    def scope(*operators):
        return pump_composite.scope_errors(adapter, [(op, None) for op in operators], spec)

    current = reader(
        "cells.operator.test_reader@1", VOLUME, Read("current", "split", scoped=True), slots=[0]
    )
    event = provider("cells.operator.test_event@1", VOLUME, 2.0, scoped=True, slots=[0])
    split = provider(
        "cells.operator.test_split@1", VOLUME, 2.0, stage="split", scoped=True, slots=[0]
    )
    elsewhere = provider(
        "cells.operator.test_split@1", VOLUME, 2.0, stage="split", scoped=True, slots=[1]
    )
    for pair in ((current, event), (event, current), (split, current), (current, elsewhere)):
        assert structure(*pair) == [] and scope(*pair) == []
    assert structure(current, split) == []
    assert scope(current, split) == [
        "cells.operator.test_reader@1 reads the view extracellular_volume at bath at stage split "
        "before "
        "cells.operator.test_split@1 changes it there"
    ]


# ------------------------------------------------------------------ the table of changes


def listed(changes):
    return {
        name: [(c.position, c.operator.LAW_ID, c.stage, c.own) for c in found]
        for name, found in changes.items()
    }


def test_a_closer_changes_every_mask_and_padded_field_and_a_writer_what_its_owner_provides():
    state, insertion = OPERATORS[STATE], OPERATORS[INSERTION]
    stages = listed(pump_composite.view_changes(adapter, (state, insertion)))
    # Insertion@2 writes membrane state's increments in its event map and its split part.
    for name in state.VIEW_FIELDS:
        assert stages[name] == [
            (0, STATE, "split", True),
            (1, INSERTION, "event", False),
            (1, INSERTION, "split", False),
        ]
    # It closes two masks, undeclared, so at both of its parts' stages (its event map opens an
    # onset); close() changes what closing them reaches (CLOSURE_REACH), and nothing else.
    reach = {*adapter.CLOSURE_REACH["membrane_active"], *adapter.CLOSURE_REACH["outside_active"]}
    for name in (*adapter.MASK_FIELDS, *adapter.PADDED_FIELDS):
        expected = [(1, INSERTION, "event", False), (1, INSERTION, "split", False)]
        assert stages.get(name, []) == (expected if name in reach else []), name
    # A provider changes at the stages of the earlier changes of what it reads current; only its
    # own declared stage is its own.
    lumen = OPERATORS[
        "cells.operator.restricted_cleft_lumen@2"
    ]  # Reads membrane_area, provides VOLUME.
    stages = listed(pump_composite.view_changes(adapter, (state, insertion, lumen)))
    assert stages[VOLUME] == [(2, lumen.LAW_ID, "event", False), (2, lumen.LAW_ID, "split", True)]


def test_an_undeclared_change_of_a_two_part_operator_counts_at_its_event_too():
    """Operator.view_change defaults a two-part operator's change to split, but its event map may
    change the field too (insertion@2 opens an onset there): an event reader of a mask placed
    before insertion@2 is refused, not given the mask before this step's onset."""
    masks = reader(
        "cells.operator.test_event_masks@1",
        "membrane_active",
        Read("current", "event"),
        parts=("event",),
    )
    state, insertion = OPERATORS[STATE], OPERATORS[INSERTION]
    assert structure(state, insertion, masks) == []
    assert structure(state, masks, insertion) == [
        late("cells.operator.test_event_masks@1", "membrane_active", "event", INSERTION)
    ]


def test_a_scoped_providers_inherited_stage_is_ordered_at_the_structure_check():
    """Door S's per-slot check covers a scoped provider's own declared stage only. The stage it
    inherits from what it reads (membrane state's area, at split) is ordered at the structure check,
    so a scoped split reader before it is refused there; without the inherited read it is not."""
    split = Read("current", "split", scoped=True)
    current = reader("cells.operator.test_reader@1", VOLUME, split, slots=[0])
    kwargs = dict(stage="event", scoped=True, slots=[0])
    inherits = provider(
        "cells.operator.test_inherits@1", VOLUME, 2.0, VIEW_READS=("membrane_area",), **kwargs
    )
    plain = provider("cells.operator.test_plain@1", VOLUME, 2.0, **kwargs)
    state = OPERATORS[STATE]
    assert structure(state, current, plain) == []  # Its own stage is event: decided per slot.
    assert structure(state, current, inherits) == [
        late("cells.operator.test_reader@1", VOLUME, "split", "cells.operator.test_inherits@1")
    ]


def test_a_reader_of_membrane_state_follows_the_writers_of_its_state():
    area = reader("cells.operator.test_area_reader@1", "membrane_area", Read("current", "split"))
    state, insertion = OPERATORS[STATE], OPERATORS[INSERTION]
    assert structure(state, insertion, area) == []
    assert structure(state, area, insertion) == [
        late("cells.operator.test_area_reader@1", "membrane_area", "split", INSERTION)
    ]


def test_a_reader_of_a_patch_mask_sees_a_closed_cells_patches_closed(two_cells):
    """Gap 5's hazard, guarded: a reader of membrane_active beside a closer of active only is a
    view reader (close() propagates), so it receives the propagated mask, never the declared one;
    a split closer after the split reader is refused."""
    _, state, p = two_cells
    patches = reader(
        "cells.operator.test_patch_reader@1", "membrane_active", Read("current", "split")
    )
    cell_0 = closer("cells.operator.test_closer@1", [0])
    composition = pump_composite.Composition(adapter, (patches, cell_0))
    assert patches in composition.view_readers
    composition._half_step(patches, state, 0.5e-3, None, p, xp=np)
    seen = np.asarray(patches.received[-1].membrane_active)
    assert np.asarray(p.membrane_active).all()
    assert seen.tolist() == [not k == 0 for k in np.asarray(p.membrane_cell)]
    split_closer = closer("cells.operator.test_closer@1", [0], stage="split")
    assert structure(patches, split_closer) == [
        late(
            "cells.operator.test_patch_reader@1",
            "membrane_active",
            "split",
            "cells.operator.test_closer@1",
        )
    ]


@pytest.mark.parametrize("mask", adapter.MASK_FIELDS)
def test_the_closure_reach_covers_everything_close_changes(mask):
    """CLOSURE_REACH, which the table of changes and the fixed-read rule read, is exactly what
    close() changes when the slots of `mask` close one at a time, in a world with every entity kind
    (cells, outside nodes with a face, patches, a channel population, a contact) and every padded
    field nonzero, so that each field the map names, or leaves out, shows. It is read against
    close() itself; the planted case of the rules it feeds is the fixed-read and order tests'."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_0", "ecs_0", "ecs_1", 1e-10, 1e-5),),
        junctions=(("junction_0", "cell_0", "cell_1"),),
        end=0.004,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6, ecs_1=1e-6),
    )
    raw["model"]["channels"] = [
        dict(
            id="leak_0",
            membrane_id="contact_0",
            kinetic_law="cells.channel.kleak_always_open@1",
            max_permeability_m_per_s=1e-9,
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
    ]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id="leak_0", schedule=[dict(time=0.0, availability=1.0)])
    ]
    raw["execution"]["channel_capacity"] = 1
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    q = adapter.inner_layout(p)
    q = q._replace(  # Every padded field nonzero, so that padding a closed slot shows.
        initial_cell_charge_C=np.full(np.shape(q.initial_cell_charge_C), 1e-15),
        initial_outside_charge_C=np.full(np.shape(q.initial_outside_charge_C), -1e-15),
        junction_minimum=np.full(np.shape(q.junction_minimum), 0.25),
    )
    for name in adapter.PADDED_FIELDS:
        assert np.all(np.asarray(getattr(q, name)) != 0), name

    def closes(first):
        def closures(self, state, p, q, *, xp):
            closed = np.ones(np.shape(getattr(q, mask)), dtype=bool)
            closed[first] = False
            return {mask: xp.asarray(closed)}

        body = dict(
            LAW_ID="cells.operator.test_reach@1", EVENT=True, CLOSES=(mask,), closures=closures
        )
        return check_declarations(type("Reach", (Operator,), body))()

    fields = (*adapter.MASK_FIELDS, *adapter.PADDED_FIELDS)
    changed = set()
    for first in range(np.shape(getattr(q, mask))[-1]):
        closed = adapter.close(q, state, p, (closes(first),), xp=np)
        changed |= {
            k
            for k in fields
            if np.asarray(getattr(closed, k)).tobytes() != np.asarray(getattr(q, k)).tobytes()
        }
    assert changed == set(adapter.CLOSURE_REACH[mask]), (mask, changed)


def test_a_fixed_read_of_a_mask_a_closure_reaches_is_refused():
    """§4 of the M1 hand-back (the lead's ruling (a)): a fixed read of a mask that another closer's
    closure reaches through close()'s propagation is refused, not only of the masks it names; one
    the closure does not reach is admitted."""
    fixed = reader("cells.operator.test_fixed_patches@1", "membrane_active", Read("fixed", "split"))
    cell_closer = closer("cells.operator.test_closer@1", [0])  # Closes active; its patches follow.
    assert structure(cell_closer, fixed) == [
        "cells.operator.test_fixed_patches@1 reads membrane_active as declared, but "
        "cells.operator.test_closer@1 closes it"
    ]
    faces = reader("cells.operator.test_fixed_faces@1", "face_active", Read("fixed", "split"))
    assert structure(cell_closer, faces) == []  # Closing a cell closes no face.


# ------------------------------------------------------------------ C3, per-stage read modes

TWO_MODES = (Read("current", "split"), Read("reference", "end"))


def test_one_field_is_read_current_at_one_stage_and_as_a_reference_at_another(two_cells):
    _, state, p = two_cells
    both = reader("cells.operator.test_two_modes@1", VOLUME, *TWO_MODES)
    assert reads_of(both, VOLUME) == TWO_MODES
    with pytest.raises(ValueError, match="reads extracellular_volume at 2 stages"):
        type(both).scoped_read(VOLUME)
    single = reader("cells.operator.test_one@1", VOLUME, Read("current", "split"))
    assert reads_of(single, VOLUME) == (type(single).scoped_read(VOLUME),)
    change = provider("cells.operator.test_change@1", VOLUME, 2.0, stage="split")
    assert structure(change, both) == []
    assert structure(both, change) == [
        late("cells.operator.test_two_modes@1", VOLUME, "split", "cells.operator.test_change@1")
    ]
    composition = pump_composite.Composition(adapter, (change, both))
    composition._half_step(both, state, 0.5e-3, None, p, xp=np)
    assert np.asarray(both.received[-1].extracellular_volume).tolist() == [2.0, 2.0]


@pytest.mark.parametrize(
    "declared, attributes, message",
    [
        ((Read("current", "split"), Read("current", "split")), {}, "once per stage"),
        ((Read("reference", "end"),), dict(VIEW_READS=(VOLUME,)), "is not also read"),
        ((Read("current", "event"),), {}, "at stage event, which none of its parts runs at"),
        ((Read("reference", "split"), Read("reference", "end")), {}, None),
        (("current", "split"), {}, "a tuple of Reads"),
    ],
)
def test_the_contract_refuses_malformed_per_stage_reads(declared, attributes, message):
    def build():
        body = dict(
            LAW_ID="cells.operator.test_bad@1",
            SPLIT=True,
            RK4="split",
            SCOPED_READS={VOLUME: declared},
        )
        if any(isinstance(r, Read) and r.mode == "current" for r in declared):
            body["VIEW_READS"] = (VOLUME,)
        return check_declarations(type("Bad", (Operator,), body | attributes))

    if message is None:
        build()
    else:
        with pytest.raises(ValueError, match=message):
            build()


def test_a_change_at_a_stage_none_of_its_parts_runs_at_is_refused():
    body = dict(LAW_ID="cells.operator.test_bad@1", EVENT=True, VIEW_FIELDS=(VOLUME,))
    check_declarations(type("Event", (Operator,), body | dict(VIEW_CHANGES={VOLUME: Change()})))
    with pytest.raises(ValueError, match="at stage split, which none of its parts runs at"):
        check_declarations(
            type(
                "Split", (Operator,), body | dict(VIEW_CHANGES={VOLUME: Change("replace", "split")})
            )
        )
    for law, op in OPERATORS.items():  # Every registered declaration keeps its stages.
        check_declarations(type(op))
        for name in op.SCOPED_READS:
            assert reads_of(op, name) == (op.scoped_read(name),), law


# ------------------------------------------------------------------ C4, the reader view


def test_a_reader_receives_its_read_fields_bitwise_without_the_field_refresh(
    two_cells, monkeypatch
):
    _, state, p = two_cells
    masks = reader("cells.operator.test_masks@1", "active", Read("current", "split"))
    composition = pump_composite.Composition(
        adapter, (closer("cells.operator.test_closer@1", [1]), masks)
    )
    full = composition.view(p, state, xp=np)  # Masks are field inputs: the full view refreshes.
    view = composition.reader_view(masks, p, state, xp=np)
    assert type(view)._fields == ("active",)
    assert np.asarray(view.active).tobytes() == np.asarray(full.active).tobytes()
    assert np.asarray(view.active).tolist() == [True, False]
    monkeypatch.setattr(adapter, "refresh_field", lambda *a, **k: pytest.fail("refreshed"))
    composition.reader_view(masks, p, state, xp=np)  # Formed without the refresh.
    with pytest.raises(pytest.fail.Exception, match="refreshed"):
        composition.view(p, state, xp=np)


def test_an_operator_that_books_at_the_view_keeps_the_full_view(two_cells):
    _, state, p = two_cells
    books = reader(
        "cells.operator.test_books@1", "active", Read("current", "split"), BOOKS_AT_VIEW=True
    )
    composition = pump_composite.Composition(
        adapter, (closer("cells.operator.test_closer@1", [1]), books)
    )
    assert composition.field_inputs and composition._passes_view(books)
    composition._half_step(books, state, 0.5e-3, None, p, xp=np)
    assert type(books.received[-1]) is type(composition.view(p, state, xp=np))


# ------------------------------------------------------------------ E1 and E2 (§12)


def test_e1_a_volume_reader_joins_water_and_sees_its_merged_volume(water_cell):
    model, state, p = water_cell
    water = OPERATORS[WATER]
    stub = reader("cells.operator.stub_volume_reader@1", "volume", Read("current", "split"))
    assert structure(water, stub) == []
    assert structure(stub, water) == [
        late("cells.operator.stub_volume_reader@1", "volume", "split", WATER)
    ]
    composition = pump_composite.Composition(model.inner, (water, stub))
    moved = state._replace(volume_increment_pL=state.volume_increment_pL + 0.125)
    composition._half_step(stub, moved, 0.5e-3, None, p, xp=np)
    seen, merged = stub.received[-1].volume, composition.view(p, moved, xp=np).volume
    assert np.asarray(seen).tobytes() == np.asarray(merged).tobytes()
    assert np.asarray(seen).tobytes() != np.asarray(p.volume).tobytes()
    alone = pump_composite.Composition(model.inner, (stub,))  # Without water: the declared value.
    assert not alone._passes_view(stub)
    alone._half_step(stub, moved, 0.5e-3, None, p, xp=np)
    assert stub.received[-1] is None


def test_e2_a_reader_placed_before_an_event_closer_sees_the_closed_cell(two_cells):
    _, state, p = two_cells
    stub_closer = closer("cells.operator.stub_closer@1", [0])
    masks = reader("cells.operator.test_masks@1", "active", Read("current", "split"))
    assert structure(masks, stub_closer) == []  # The closer's event runs first (C2).
    composition = pump_composite.Composition(adapter, (masks, stub_closer))
    composition._half_step(masks, state, 0.5e-3, None, p, xp=np)
    assert np.asarray(masks.received[-1].active).tolist() == [False, True]
    assert structure(masks, closer("cells.operator.stub_closer@1", [0], stage="split")) == [
        late("cells.operator.test_masks@1", "active", "split", "cells.operator.stub_closer@1")
    ]
