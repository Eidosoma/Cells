"""Door S, scoped composition: the declarations, admission per slot and the merge (no long runs).

docs/SCOPED_COMPOSITION_DESIGN.md (D176), the tests that land with door S:
* T1, the merge: two changers on disjoint slots merge to the same bits in either order, in NumPy
  and under jit;
* T2, overlaps: overlaps on every slot are refused at the structure check ("two providers" for
  replacements, as before door S) unless both changes commute; scoped overlaps are refused at the
  definition, naming the slots; a commuting chain applies in declared order and is recorded in
  the field map;
* T3, readers: a fixed reader is refused where a changer meets its slots and admitted where they
  are disjoint; a reference read has no constraint; a current reader must follow the changers of
  its slots at its own stage, sees an earlier stage's change whatever the declared order, and
  reads the declared value where nothing changes the field (docs/OPERATOR_COMPOSITION_DESIGN.md
  §4.1, C1 and C2; tests/unit/test_composition_order.py has the rest); a part with a current read
  at stage split receives the merged view;
* T7, planted controls: a changer's values off its slots change nothing there; a slot mask that
  differs from the declared slots is refused at binding;
* the contract's checks of the new declarations, and the real pair the round admits: the bath
  schedule beside D152's reactions, in either order, while the other pairs keep their refusals.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS
from cells.operators.contract import Change, Operator, Read, check_declarations
from cells.registry.models import get_model
from validation.tissue import delivery_fixtures as dfx
from validation.tissue import secreted_species_fixtures as fx

jax.config.update("jax_enable_x64", True)

FIELD = "extracellular_volume"  # [outside]: the bath, ecs_0 and comp_0 in the delivery world.
BATH, D152 = (
    "cells.operator.scheduled_bath_composition@1",
    "cells.operator.local_species_reactions@1",
)
INSERTION_1, STATE = (
    "cells.operator.scheduled_membrane_insertion@1",
    "cells.operator.membrane_entity_state@1",
)
SITES = "cells.operator.site_occupancy@1"


def changer(law, slots, value, *, contribution="replace", scoped=True, stage="event"):
    """A test-double changer of FIELD at `stage` (its event map, or its split part): `value` on
    every slot (off its slots too: T7), taken on `slots` when scoped."""

    class Changer(Operator):
        LAW_ID = law
        EVENT = stage == "event"
        SPLIT = stage == "split"
        RK4 = "split" if stage == "split" else None
        VIEW_FIELDS = (FIELD,)
        VIEW_CHANGES = {FIELD: Change(contribution, stage, scoped=scoped)}

        def changed_slots(self, spec, declaration):
            return {FIELD: tuple(slots)}

        def view(self, state, p, q, *, xp):
            return {FIELD: xp.full_like(p.extracellular_volume, value)}

        def view_slots(self, p, *, xp):
            mask = np.zeros(p.extracellular_volume.shape[0], dtype=bool)
            mask[list(slots)] = True
            return {FIELD: xp.asarray(mask)}

    return check_declarations(Changer)()


def reader(law, slots, mode, *, scoped=True, stage="split"):
    """A test-double reader of FIELD with a split part that records the view it receives."""

    class Reader(Operator):
        LAW_ID = law
        SPLIT = True
        RK4 = "split"
        CONFLICTS_VIEW = (FIELD,) if mode == "fixed" else ()
        VIEW_READS = (FIELD,) if mode == "current" else ()
        SCOPED_READS = {FIELD: Read(mode, stage, scoped=scoped)}
        received = []

        def read_slots(self, spec, declaration):
            return {FIELD: tuple(slots)}

        def half_step(self, state, h, control, p, *, xp, view=None):
            self.received.append(view)
            return state, None

    return check_declarations(Reader)()


@pytest.fixture(scope="module")
def world():
    spec = parse_spec(dfx.delivery_world(end=0.02))
    return (spec, *get_model(spec.model).initial_values(spec))


def merged(operators, p, state, *, xp=np):
    return np.asarray(getattr(adapter.view(p, state, operators, xp=xp), FIELD))


# ------------------------------------------------------------------ T1, the merge


def test_disjoint_changers_merge_to_the_same_bits_in_either_order(world):
    _, state, p = world
    a, b = (
        changer("cells.operator.test_a@1", [0], 2.0),
        changer("cells.operator.test_b@1", [2], 3.0),
    )
    forward, backward = merged((a, b), p, state), merged((b, a), p, state)
    assert forward.tobytes() == backward.tobytes()
    declared = np.asarray(p.extracellular_volume)
    assert forward[0] == 2.0 and forward[2] == 3.0 and forward[1] == declared[1]
    jp, js = jax.tree.map(jnp.asarray, (p, state))
    for order in ((a, b), (b, a)):
        traced = jax.jit(lambda q, s, o=order: getattr(adapter.view(q, s, o), FIELD))(jp, js)
        assert np.asarray(traced).tobytes() == forward.tobytes()


def test_an_unscoped_replacement_is_the_value_itself(world):
    _, state, p = world
    whole = changer("cells.operator.test_whole@1", [0, 1, 2], 4.0, scoped=False)
    assert merged((whole,), p, state).tobytes() == np.full(3, 4.0).tobytes()


# ------------------------------------------------------------------ T2, overlaps


def structure(*operators):
    return pump_composite.structure_errors(adapter, operators)


def scope(world, *operators):
    spec = world[0]
    return pump_composite.scope_errors(adapter, [(op, None) for op in operators], spec)


def test_overlaps_on_every_slot_are_refused_at_the_structure_check_unless_they_commute():
    replace = [
        changer(law, [0], 1.0, scoped=False)
        for law in ("cells.operator.test_r0@1", "cells.operator.test_r1@1")
    ]
    assert structure(*replace) == [f"two providers of the view field {FIELD}"]
    for kind, pair_ids in (
        ("add", ("cells.operator.test_add0@1", "cells.operator.test_add1@1")),
        ("multiply", ("cells.operator.test_multiply0@1", "cells.operator.test_multiply1@1")),
    ):
        pair = [changer(law, [0], 1.0, contribution=kind, scoped=False) for law in pair_ids]
        assert structure(*pair) == []
    mixed = (
        changer("cells.operator.test_add@1", [0], 1.0, contribution="add", scoped=False),
        changer("cells.operator.test_mul@1", [0], 1.0, contribution="multiply", scoped=False),
    )
    assert "both change the view field" in structure(*mixed)[0]
    # A scoped replacement beside an unscoped one meets it on every slot: refused as before.
    assert structure(changer("cells.operator.test_s@1", [0], 1.0), replace[0]) == [
        f"two providers of the view field {FIELD}"
    ]


def test_scoped_overlaps_are_refused_at_the_definition_naming_the_slots(world):
    a, b = (
        changer("cells.operator.test_a@1", [0, 1], 2.0),
        changer("cells.operator.test_b@1", [1, 2], 3.0),
    )
    assert structure(a, b) == []
    (error,) = scope(world, a, b)
    assert (
        "cells.operator.test_a@1 and cells.operator.test_b@1 both change extracellular_volume"
        in error
        and error.endswith("at ecs_0")
    )
    assert (
        scope(
            world,
            changer("cells.operator.test_a@1", [0], 2.0),
            changer("cells.operator.test_b@1", [1, 2], 3.0),
        )
        == []
    )


def test_a_commuting_chain_applies_in_declared_order_and_is_recorded(world):
    _, state, p = world
    a = changer("cells.operator.test_a@1", [1], 2.0, contribution="multiply")
    b = changer("cells.operator.test_b@1", [1], 3.0, contribution="add")
    c = changer("cells.operator.test_c@1", [1], 5.0, contribution="add")
    assert scope(world, b, c) == []
    declared = np.asarray(p.extracellular_volume)[1]
    assert merged((b, c), p, state)[1] == (declared + 3.0) + 5.0
    (error,) = scope(world, a, b)
    assert "(multiply and add) at ecs_0" in error
    views = pump_composite.field_map(adapter, (b, c))["views"]
    assert views[FIELD]["changes"] == [
        ["cells.operator.test_b@1", "add", True],
        ["cells.operator.test_c@1", "add", True],
    ]
    assert "changes" not in pump_composite.field_map(adapter, (b,))["views"][FIELD]


# ------------------------------------------------------------------ T3, readers


def test_a_fixed_reader_is_refused_where_a_changer_meets_its_slots(world):
    dose = changer("cells.operator.test_dose@1", [0], 2.0)
    assert structure(dose, reader("cells.operator.test_fixed@1", [1, 2], "fixed")) == []
    assert scope(world, dose, reader("cells.operator.test_fixed@1", [1, 2], "fixed")) == []
    (error,) = scope(world, dose, reader("cells.operator.test_fixed@1", [0, 1], "fixed"))
    assert (
        error
        == "cells.operator.test_fixed@1 reads extracellular_volume as declared at bath, which cells.operator.test_dose@1 changes"
    )
    # Unscoped on either side: refused at the structure check, as before door S.
    assert structure(dose, reader("cells.operator.test_fixed@1", [1], "fixed", scoped=False)) == [
        "cells.operator.test_fixed@1 reads extracellular_volume as declared, but "
        "cells.operator.test_dose@1 provides it"
    ]


def test_a_reference_read_has_no_constraint(world):
    dose = changer("cells.operator.test_dose@1", [0], 2.0)
    ref = reader("cells.operator.test_ref@1", [0], "reference")
    assert structure(dose, ref) == [] and scope(world, dose, ref) == []


def test_a_current_reader_follows_the_changers_of_its_slots(world):
    """Door S's rule 3, stage-aware (docs/OPERATOR_COMPOSITION_DESIGN.md §5, C2): a split reader
    sees an event's change whatever the declared order, since the events run first; a split
    change of its slot must precede it, else it is refused naming the slot. A reader of a field
    nothing changes reads the declared value (C1)."""
    dose = changer("cells.operator.test_dose@1", [0], 2.0)
    late = reader("cells.operator.test_current@1", [0], "current")
    assert scope(world, dose, late) == []
    early = (changer("cells.operator.test_first@1", [2], 1.0), late, dose)
    assert structure(*early) == [] and scope(world, *early) == []  # The event runs first.
    split_dose = changer(
        "cells.operator.test_split_dose@1", [0], 2.0, stage="split"
    )  # The same-stage twin.
    assert scope(world, split_dose, late) == []
    before = (changer("cells.operator.test_first@1", [2], 1.0), late, split_dose)
    assert structure(*before) == []
    (error,) = scope(world, *before)
    assert error == (
        "cells.operator.test_current@1 reads the view extracellular_volume at bath at stage split "
        "before "
        "cells.operator.test_split_dose@1 changes it there"
    )
    assert (
        structure(reader("cells.operator.test_alone@1", [0], "current")) == []
    )  # Nothing changes it.


def test_a_current_split_reader_receives_the_merged_view(world):
    _, state, p = world
    dose = changer("cells.operator.test_dose@1", [0], 2.0)
    current = reader("cells.operator.test_current@1", [0], "current")
    fixed = reader("cells.operator.test_fixed@1", [1], "fixed")
    composition = pump_composite.Composition(adapter, (dose, current, fixed))
    assert composition._passes_view(current) and not composition._passes_view(fixed)
    composition._half_step(current, state, 0.5e-3, None, p, xp=np)
    composition._half_step(fixed, state, 0.5e-3, None, p, xp=np)
    view, nothing = current.received[-1], fixed.received[-1]
    assert np.asarray(getattr(view, FIELD))[0] == 2.0 and nothing is None


# ------------------------------------------------------------------ T7, planted controls


def test_a_changer_off_its_slots_changes_nothing_there(world):
    _, state, p = world
    planted = changer("cells.operator.test_planted@1", [0], 7.0)  # Its values are 7 on every slot.
    out, declared = merged((planted,), p, state), np.asarray(p.extracellular_volume)
    assert out[0] == 7.0 and out[1:].tobytes() == declared[1:].tobytes()


def test_a_slot_mask_that_differs_from_the_declared_slots_is_refused(world):
    spec, _, p = world
    honest, wrong = (
        changer("cells.operator.test_h@1", [0], 1.0),
        changer("cells.operator.test_w@1", [0], 1.0),
    )
    wrong.changed_slots = lambda spec, declaration: {FIELD: (1,)}
    assert pump_composite.slot_mask_errors([(honest, None)], spec, p) == []
    assert pump_composite.slot_mask_errors([(wrong, None)], spec, p) == [
        f"cells.operator.test_w@1's slot mask for {FIELD} differs from its slots"
    ]


def test_the_definition_check_runs_the_scope_check(monkeypatch):
    """The wiring: a planted per-slot refusal refuses a real definition at parse."""
    monkeypatch.setattr(pump_composite, "scope_errors", lambda *a: ["planted overlap"])
    with pytest.raises(ConfigError, match="planted overlap"):
        parse_spec(dfx.delivery_world(end=0.02))


def test_binding_refuses_a_bath_mask_that_differs_from_its_baths(monkeypatch):
    """The wiring: the bath schedule's bound mask is checked against its declared baths."""
    wrong = lambda self, p, *, xp: {"extracellular_amount_reference": ~p.bath_scheduled}  # noqa: E731
    monkeypatch.setattr(type(OPERATORS[BATH]), "view_slots", wrong)
    with pytest.raises(ConfigError, match="slot mask for extracellular_amount_reference differs"):
        parse_spec(dfx.delivery_world(end=0.02))


# ------------------------------------------------------------------ the contract's checks


@pytest.mark.parametrize(
    "attributes, message",
    [
        (dict(VIEW_CHANGES={FIELD: ("replace", "event")}), "maps extracellular_volume to a Change"),
        (dict(VIEW_CHANGES={"volume": Change()}), "refines a field it provides or closes"),
        (dict(VIEW_CHANGES={FIELD: Change("and")}), "is one of"),
        (dict(VIEW_CHANGES={FIELD: Change("replace", "inner")}), "at a stage of"),
        (dict(SCOPED_READS={FIELD: Read("current", "split")}), "needs it in VIEW_READS"),
        (dict(SCOPED_READS={"volume": Read("fixed", "split")}), "needs it in CONFLICTS_VIEW"),
        (dict(SCOPED_READS={FIELD: Read("reference", "split")}), "is not also read"),
        (dict(SCOPED_READS={"volume": Read("guess", "split")}), "has a mode of"),
    ],
)
def test_the_contract_refuses_malformed_scopes(attributes, message):
    base = dict(LAW_ID="cells.operator.test_bad@1", EVENT=True, VIEW_FIELDS=(FIELD,))
    with pytest.raises(ValueError, match=message):
        check_declarations(type("Bad", (Operator,), base | attributes))


def test_closers_change_whole_masks_in_r():
    base = dict(LAW_ID="cells.operator.test_closer@1", EVENT=True, CLOSES=("active",))
    check_declarations(
        type("Closer", (Operator,), base | dict(VIEW_CHANGES={"active": Change("and")}))
    )
    with pytest.raises(ValueError, match="closers change whole masks"):
        check_declarations(
            type(
                "Scoped",
                (Operator,),
                base | dict(VIEW_CHANGES={"active": Change("and", scoped=True)}),
            )
        )


def test_every_registered_operator_keeps_its_declarations():
    for law, op in OPERATORS.items():
        check_declarations(type(op))
        for name in op.VIEW_FIELDS:
            assert op.view_change(name).contribution == "replace", law


# ------------------------------------------------------------------ the round's real pair


def laws(*names):
    return pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in names))


def test_the_bath_schedule_and_d152_compose_in_either_order_and_the_other_pairs_stay_refused():
    assert laws(BATH, D152) == [] and laws(D152, BATH) == []
    assert laws(STATE, INSERTION_1, BATH) == [
        "two providers of the view field extracellular_amount_reference"
    ]
    assert (
        "cells.operator.local_species_reactions@1 reads extracellular_amount_reference as declared, but "
        in (" ".join(laws(STATE, INSERTION_1, D152)))
    )
    # FR-23 (D244): site occupancy's anchor reads are scoped to its facing finite nodes, so it
    # composes beside the bath schedule in either order; beside insertion@1, whose anchors are
    # unscoped, it stays refused.
    assert laws(BATH, SITES) == [] and laws(SITES, BATH) == []
    assert (
        "cells.operator.site_occupancy@1 reads extracellular_amount_reference as declared, but "
        in (" ".join(laws(STATE, INSERTION_1, SITES)))
    )


def test_the_delivery_world_binds_with_disjoint_slots(world):
    spec, _, p = world
    assert BATH in [op.LAW_ID for op, _, _ in cs.entries(spec)]
    outside = [c.id for c in spec.model.extracellular]
    assert np.flatnonzero(np.asarray(p.bath_scheduled)).tolist() == [outside.index("bath")]
    finite = [i for i, c in enumerate(spec.model.extracellular) if not c.reservoir]
    reactions = OPERATORS[D152].read_slots(spec, None)
    assert reactions["extracellular_amount_reference"] == tuple(finite)


def test_a_plain_world_without_door_s_declarations_is_unchanged():
    spec = parse_spec(fx.world())
    model = get_model(spec.model)
    assert not model.scoped_changers and not model.view_readers
