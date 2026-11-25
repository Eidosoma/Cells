"""Schema A through the composite (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j), (k); the lead's rulings).

The integration owner's part of schema A, with the planted kinds of tests/kind_fixtures.py:
- the adapter takes the structure's types, and the names derived from them, from the
  implementation object (its own names first), and builds the structure's own state, layout and
  control: today's structures keep this module's own objects, a declared kind's fields reach
  the composite, and the composite spec's controls follow the object's control type;
- an empty composition of a kind's world is that world's resolved_pump_tissue@3 run, bitwise,
  and an operator runs beside a kind with every check passing;
- REQUIRES_KINDS: an operator that needs a kind is refused where the definition does not declare
  it, naming the operator and the kind, and a declared write of a kind's field names the kind;
- the families (water@1, water@2, replacement@1) refuse a declared kind at their definition check
  and at binding, and an operator with fixed inner fields (FIXED_INNER_FIELDS: replacement@1's
  and @2's) is refused beside one, as is every operator that opens, closes or retires slots
  (division's partition, insertion@1 and @2), whose closures would leave a kind's per-slot fields
  (the carrier's, on membrane_slot) stale;
- kind order: two definitions that declare the same kinds in different orders share one
  composition, structure key, classes and snapshot layout; a registered but undeclared kind
  changes no composition, and a kind world's composition follows its kind registry.
"""

import re

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.execution.state import initialise
from cells.models import cell_replacement, pump_composite, surface_pump_water, surface_pump_water_v2
from cells.models import pump_composite_adapter as pump3
from cells.models import surface_pump_v3 as ionic
from cells.operators import OPERATORS, contract
from cells.records.io import write_snapshot
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from tests import partition_fixtures as pfx
from tests import replacement_water_fixtures as wrfx
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import composite_guard as guard
from validation.tissue import pump_water_fixtures as wfx

END_S = 0.004
RATE = 1e-3  # fmol/s, as the core's seam test.
METHODS = ("inner_state", "layout_kind", "inner_layout", "inner_control", "view", "control_view")
FIXED_REFUSAL = (
    r"builds the inner model's state, layout or control with today's fixed fields, so it does not "
    rf"run beside declared kinds \({re.escape(kf.KIND_ID)}\)"
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def with_b(raw):
    """raw with the neutral inventory species B, which the exchange kind moves."""
    return add_inventory_species(
        raw, "B", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12
    )


def world(end_time=END_S):
    """The core's seam world: heredity cell D with B, before any kind is declared."""
    return with_b(wfx.heredity_cell("D", end_time=end_time))


def composite(raw):
    return parse_spec(cs.frozen_definition(raw))


def test_todays_adapter_keeps_the_modules_own_names():
    model = get_model(composite(world()).model)
    adapter = model.inner
    assert isinstance(adapter, pump3.InnerAdapter) and adapter.KINDS == ()
    for name in (*pump3.TYPE_NAMES, "KIND_FIELDS"):
        assert getattr(adapter, name) is getattr(pump3, name), name
    assert adapter.Control is pump3.Control is ionic.Control
    assert adapter.Observations is ionic.Observations
    # Every other name of this module resolves as before the object-first lookup: the module's.
    own = set(vars(adapter)) | set(pump3.FORWARDED) | set(METHODS)
    for name in (n for n in vars(pump3) if not n.startswith("_") and n not in own):
        assert getattr(adapter, name) is getattr(pump3, name), name
    spec = composite(world())
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    assert type(adapter.inner_state(state)) is pump3.STATE_TYPE
    assert type(adapter.inner_layout(p)) is type(pump3.inner_layout(p))
    assert adapter.inner_control(control) == pump3.inner_control(control)
    assert model.CONTROL_FIELDS == cs.control_fields(spec.model)


def test_a_declared_kinds_fields_reach_the_composite():
    with kind_registry.scope(kf.registry()):
        spec = composite(kf.declare(world(), rate=RATE))
        model = get_model(spec.model)
        adapter, impl = model.inner, model.inner.implementation
        assert adapter.KINDS == (kf.KIND_ID,) == tuple(k for k, _ in spec.model.kinds)
        for name in ("STATE_AXES", "STATE_TYPE", "LAYOUT_TYPE", "FLOOR_LAYOUT_TYPE"):
            assert getattr(adapter, name) is getattr(impl, name), name
        assert adapter.CONTROL_TYPE is impl.Control is adapter.Control
        assert adapter.OBSERVATION_FIELDS is impl.OBSERVATION_FIELDS
        assert adapter.STATE_FIELDS == (
            *pump3.STATE_FIELDS,
            "exchange_moved_fmol",
            "exchange_work_pJ",
        )
        assert adapter.CONTROL_FIELDS == (*pump3.CONTROL_FIELDS, "exchange_availability")
        assert adapter.WORK_FIELDS == (*pump3.WORK_FIELDS, "exchange_work_pJ")
        assert adapter.HEAT_FIELDS is pump3.HEAT_FIELDS
        assert set(adapter.KIND_FIELDS) == {
            "exchange_moved_fmol",
            "exchange_work_pJ",
            "exchange_rate_fmol_s",
            "exchange_node",
            "exchange_availability",
        }
        assert model.STATE_TYPE._fields == impl.STATE_TYPE._fields  # The empty composition.
        assert model.CONTROL_FIELDS == impl.Control._fields == cs.control_fields(spec.model)
        assert model.OBSERVATION_FIELDS == impl.OBSERVATION_FIELDS
        assert "exchange_work_pJ" in model.ENERGY_FLOW_FIELDS
        state, p = model.initial_values(spec)
        assert type(adapter.inner_layout(p)) in (impl.LAYOUT_TYPE, impl.FLOOR_LAYOUT_TYPE)
        assert type(adapter.inner_state(state)) is impl.STATE_TYPE
        control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
        assert type(adapter.inner_control(control)) is impl.Control
        values = model.readouts(state, control, p, xp=np)
        assert values.valid and values.derivative.exchange_moved_fmol[0] == RATE
        model.check_values(state, spec)  # The host checks of the initial row.
        assert get_model(spec.model) is model


def test_an_empty_composition_of_a_kinds_world_is_its_inner_run_bitwise():
    with kind_registry.scope(kf.registry()):
        raw = kf.declare(world(), rate=RATE)
        reference, result = run(parse_spec(raw)), run(composite(raw))
        report = guard.assert_same(reference, result)
        assert report["bitwise"]
        assert {"exchange_moved_fmol", "exchange_work_pJ"} <= set(result.history._fields)
        assert "exchange_rate_column" in vars(result.observations)
        moved = float(result.final.state.exchange_moved_fmol[0])
        assert moved == pytest.approx(RATE * END_S, rel=1e-9)


def test_an_operator_runs_beside_a_kind():
    """Water beside the planted kind: its fields follow the kind's, the views keep the kind's
    layout fields, the run's every check passes, and the kind moves B as it does alone."""
    with kind_registry.scope(kf.registry()):
        spec = composite(wfx.with_water(kf.declare(world(), rate=RATE)))
        model = get_model(spec.model)
        water = OPERATORS[cs.operator_laws(spec.model)[0]]
        inner = model.inner.STATE_TYPE._fields
        assert model.STATE_TYPE._fields == (*inner, *water.STATE_AXES)
        assert inner[-2:] == ("exchange_moved_fmol", "exchange_work_pJ")
        state, p = model.initial_values(spec)
        view = model.view(p, state, xp=np)
        assert view.exchange_rate_fmol_s is not None and type(view) is type(
            model.inner.inner_layout(p)
        )
        result = run(spec)
        moved = float(result.final.state.exchange_moved_fmol[0])
        assert moved == pytest.approx(RATE * END_S, rel=1e-9)
        row = list(spec.model.species_ids).index("B")
        assert float(result.final.state.amount_increment[row, 0]) == pytest.approx(-moved, rel=1e-9)


class KindReader(contract.Operator):
    LAW_ID = "tests.kind_reader@1"
    EVENT = True
    REQUIRES_KINDS = (kf.KIND_ID,)


class KindWriter(contract.Operator):
    LAW_ID = "tests.kind_writer@1"
    EVENT = True
    STATE_AXES = {"kind_writer_booked_fmol": ("cell_slot",)}
    ENTITY_WRITES = {"exchange_moved_fmol": ("kind_writer_booked_fmol",)}


class RequiringKindWriter(KindWriter):
    LAW_ID = "tests.requiring_kind_writer@1"
    REQUIRES_KINDS = ("tests.exchange@1",)


class KindFactor(contract.Operator):
    LAW_ID = "tests.kind_factor@1"
    EVENT = True
    CONTROL_FACTORS = ("exchange_availability",)
    REQUIRES_KINDS = (kf.KIND_ID,)


def adapters():
    """(today's adapter, the exchange world's adapter); call inside the planted registry."""
    today = get_model(composite(world()).model).inner
    declared = get_model(composite(kf.declare(world())).model).inner
    return today, declared


def test_requires_kinds_is_refused_without_its_kind():
    for operator in (KindReader, KindWriter, RequiringKindWriter, KindFactor):
        contract.check_declarations(operator)
    with kind_registry.scope(kf.registry()):
        today, declared = adapters()
        errors = pump_composite.structure_errors(today, (KindReader(),))
        assert errors == [
            f"tests.kind_reader@1 requires the kind {kf.KIND_ID}, which the definition does not "
            "declare"
        ]
        with pytest.raises(ConfigError, match="requires the kind tests.exchange@1"):
            pump_composite.Composition(today, (KindReader(),))
        assert pump_composite.structure_errors(declared, (KindReader(),)) == []
        # A declared write of a kind's field names the kind; without the kind it is no inner state.
        errors = pump_composite.structure_errors(declared, (KindWriter(),))
        assert errors == [
            "tests.kind_writer@1 writes exchange_moved_fmol, a field of the kind "
            f"{kf.KIND_ID}, which it does not require (REQUIRES_KINDS)"
        ]
        assert pump_composite.structure_errors(declared, (RequiringKindWriter(),)) == []
        errors = pump_composite.structure_errors(today, (RequiringKindWriter(),))
        assert any("neither inner state" in e for e in errors)
        assert any("requires the kind" in e for e in errors)
        errors = pump_composite.structure_errors(declared, (KindFactor(),))
        assert errors == [
            "tests.kind_factor@1 multiplies exchange_availability, a control of the kind "
            f"{kf.KIND_ID}; a kind's control is not factored (observation holds only today's "
            "schedules)"
        ]


@pytest.mark.parametrize(
    "kinds, message",
    [
        (["tests.exchange@1"], "a tuple of kind IDs"),
        (("",), "non-empty string"),
        (("exchange@1", "cells.exchange@1"), "names a kind twice"),
    ],
)
def test_requires_kinds_declarations_are_checked(kinds, message):
    operator = type("Bad", (KindReader,), {"REQUIRES_KINDS": kinds})
    with pytest.raises(ValueError, match=message):
        contract.check_declarations(operator)


def test_fixed_inner_fields_declarations_are_checked():
    fixed = type("Fixed", (KindReader,), {"FIXED_INNER_FIELDS": True})
    with pytest.raises(ValueError, match="cannot require kinds"):
        contract.check_declarations(fixed)
    loose = type("Loose", (contract.Operator,), {"LAW_ID": "tests.loose@1", "EVENT": True})
    with pytest.raises(ValueError, match="FIXED_INNER_FIELDS is a bool"):
        contract.check_declarations(type("Odd", (loose,), {"FIXED_INNER_FIELDS": 1}))
    assert OPERATORS["scheduled_cell_replacement@1"].FIXED_INNER_FIELDS
    assert OPERATORS["scheduled_cell_replacement@2"].FIXED_INNER_FIELDS
    assert not OPERATORS["ideal_osmosis_linear_compliance_water@1"].FIXED_INNER_FIELDS


@pytest.mark.parametrize(
    "family, build",
    [
        ("resolved_pump_water@1", lambda raw: wfx.with_water(raw)),
        # water@2's parser runs water@1's first, whose refusal names its water@1 base.
        ("resolved_pump_water@1", lambda raw: wfx.with_symport(wfx.with_water(raw))),
        ("resolved_pump_replacement@1", lambda raw: rfx.with_replacement(raw)),
    ],
)
def test_the_families_refuse_a_declared_kind_at_their_definition(family, build):
    with kind_registry.scope(kf.registry()):
        with pytest.raises(ConfigError, match=rf"{family} does not run declared kinds \(tests"):
            parse_spec(build(kf.declare(world())))


def test_the_families_refuse_a_declared_kind_at_binding():
    with kind_registry.scope(kf.registry()):
        structure = ionic.structure(parse_spec(kf.declare(world())).model)
        assert structure.kinds
        for module in (surface_pump_water, surface_pump_water_v2, cell_replacement):
            with pytest.raises(
                ConfigError, match=rf"{module.MODEL_ID} does not run declared kinds"
            ):
                pump_composite.family_model(module, module.LAWS, structure)
        # A full-catalogue composition cannot drop a definition's kinds either.
        spec = composite(kf.declare(world()))
        with pytest.raises(ConfigError, match="declares the kinds"):
            pump_composite.implementation(ionic.MODEL_ID, ()).check_definition(spec)


def test_replacement_at_1_is_refused_beside_a_kind_in_a_composition():
    with kind_registry.scope(kf.registry()):
        raw = cs.frozen_definition(rfx.with_replacement(kf.declare(world())))
        with pytest.raises(
            ConfigError,
            match=r"scheduled_cell_replacement@1 " + FIXED_REFUSAL,
        ):
            parse_spec(raw)


def test_replacement_at_2_is_refused_beside_a_kind_in_a_composition():
    with kind_registry.scope(kf.registry()):
        raw = wrfx.over_water(kf.declare(with_b(wrfx.sheet(end=0.02))))
        with pytest.raises(
            ConfigError,
            match=r"scheduled_cell_replacement@2 " + FIXED_REFUSAL,
        ):
            parse_spec(raw)


SLOT_CHANGERS = (
    "isopotential_partition@1",  # CLOSES cells, RETIRES their history.
    "scheduled_membrane_insertion@1",  # Provides activity masks.
    "scheduled_membrane_insertion@2",  # CLOSES patches and outside nodes until their onsets.
)


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_every_operator_that_opens_closes_or_retires_slots_is_refused_beside_a_kind(law):
    """The carrier keeps per-patch state (membrane_slot), which no closer resets."""
    assert dict(kf.carrier().state_axes)["carrier_work_pJ"] == ("membrane_slot",)
    with kind_registry.scope(kf.registry(kf.carrier())):
        today = get_model(composite(world()).model).inner
        declared = get_model(composite(kf.declare_carrier(world(), species="K")).model).inner
        refusal = (
            f"{law} opens, closes or retires slots, and no closer resets a kind's per-slot "
            f"fields, so it does not run beside declared kinds ({kf.CARRIER_ID})"
        )
        assert refusal in pump_composite.structure_errors(declared, (OPERATORS[law],))
        assert not any(
            "retires slots" in e for e in pump_composite.structure_errors(today, (OPERATORS[law],))
        )
    for other in set(OPERATORS) - set(SLOT_CHANGERS):  # Every other operator, by declaration.
        op = OPERATORS[other]
        assert not (op.CLOSES or op.RETIRES or set(op.VIEW_FIELDS) & set(pump3.MASK_FIELDS)), other


def test_a_division_is_refused_beside_a_kind_with_per_patch_state():
    with kind_registry.scope(kf.registry(kf.carrier())):
        raw = kf.declare_carrier(pfx.divided(), species="K")
        with pytest.raises(
            ConfigError, match=r"isopotential_partition@1 opens, closes or retires slots"
        ):
            parse_spec(raw)


def snapshot_keys(path, spec):
    with np.load(write_snapshot(path, spec, initialise(spec)) / "state.npz") as archive:
        return list(archive.files)


def test_kinds_in_any_declaration_order_share_one_composition(tmp_path):
    """The canonical kind order (sorted ID): the carrier (tests.carrier@1) before the exchange."""
    with kind_registry.scope(kf.registry(kf.carrier())):
        base = world()
        one = composite(kf.declare_carrier(kf.declare(base), species="K"))
        two = composite(kf.declare(kf.declare_carrier(base, species="K")))
        assert list(one.model.kinds) == list(two.model.kinds)
        assert [k for k, _ in one.model.kinds] == [kf.CARRIER_ID, kf.KIND_ID]
        a, b = get_model(one.model), get_model(two.model)
        assert a is b and a.structure_key == b.structure_key
        assert a.structure_key[1][1].kinds == ((kf.CARRIER_ID, ()), (kf.KIND_ID, ()))
        assert a.STATE_TYPE._fields[-4:] == (
            "carrier_transferred",
            "carrier_work_pJ",
            "exchange_moved_fmol",
            "exchange_work_pJ",
        )
        assert a.CONTROL_FIELDS[-2:] == ("carrier_availability", "exchange_availability")
        layout = snapshot_keys(tmp_path / "one", one)
        assert layout == snapshot_keys(tmp_path / "two", two)
        assert layout == [*a.STATE_TYPE._fields, *a.LAYOUT_TYPE._fields]


def test_a_registered_but_undeclared_kind_changes_no_composition():
    spec = composite(world())
    model = get_model(spec.model)
    with kind_registry.scope(kf.registry()):
        again = composite(world())
        assert again == spec
        assert get_model(again.model) is model
        assert cs.control_fields(again.model) == cs.control_fields(spec.model)


def test_a_kind_worlds_composition_follows_its_kind_registry():
    compositions = []
    for _ in range(2):
        with kind_registry.scope(kf.registry()):
            spec = composite(kf.declare(world()))
            model = get_model(spec.model)
            assert get_model(spec.model) is model
            assert model.inner.implementation is ionic.implementation(
                model.inner.implementation.structure
            )
            assert model.inner.STATE_TYPE is model.inner.implementation.STATE_TYPE
            compositions.append(model)
    first, second = compositions
    assert first is not second and first.inner.STATE_TYPE is not second.inner.STATE_TYPE
    assert first.structure_key == second.structure_key
