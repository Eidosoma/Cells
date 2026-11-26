"""cells.model.resolved_pump_tissue@3's own run-view declarations (docs/RUN_VIEW_DESIGN.md §3; D154).

The module declares UNITS, OBSERVATION_AXES, RECORD_KINDS, ORIENTATION, RECORD_LAYERS and
VIEW_LAYERS (with RECORD_NOTES), which replace the run-view writer's interim table:
- every state field and observation column has a unit, a record kind and a layer of its own
  layers, every readout its axes, and nothing else is declared;
- each orientation is a flow (from, to) or a difference (plus, minus), naming roles of its
  record's entity set, with what it says;
- the implementation object, and the composite's inner adapter, give the module's declarations;
- on data: a membrane's voltage is its cell's potential less its outside node's, a junction's its
  sender's less its receiver's (a sheet with nonzero junction voltages), and a positive membrane or
  junction flux leaves the patch's cell or the junction's sender (the amounts' rates);
- the passive route laws declare their provenance;
- RECORD_DIAGNOSTICS names records that are the step's own residuals, and RECORD_REFERENCES maps
  each increment record to its reference layout field (the run view's loop closure measure, FR-11):
  every named field is a record and every reference a layout field, @3's and a kind world's, with
  a kind's entries folded in where its structure has the fields.
"""

import numpy as np

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import passive_routes
from cells.models import inner_laws
from cells.models import surface_pump_v3 as v3
from cells.numerics.extracellular_field import scatter
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures

RECORD_KINDS = ("level", "amount", "cumulative", "rate")
REPRESENTATIONS = ("simulated", "modelled", "prescribed")
# The run view's set roles (cells/records/run_view.py, SET_ROLES), by the record's entity axis.
ROLES = {
    "membrane_slot": {"inside", "outside"},
    "channel_slot": {"inside", "outside"},
    "edge_slot": {"sender", "receiver"},
    "face_slot": {"sender", "receiver"},
    "extracellular_slot": {"exterior", "node"},
}


def fields():
    readouts = [f for f in v3.OBSERVATION_FIELDS if f not in v3.STATE_AXES and f != "times"]
    return [*v3.STATE_AXES, *readouts], readouts


def test_every_state_field_and_column_is_declared_and_nothing_else():
    names, readouts = fields()
    layers = {layer["id"] for layer in v3.VIEW_LAYERS}
    for layer in v3.VIEW_LAYERS:
        assert set(layer) == {"id", "label", "representation"}
        assert layer["representation"] in REPRESENTATIONS
    for name in names:
        assert v3.UNITS[name], name
        assert v3.RECORD_KINDS[name] in RECORD_KINDS, name
        assert v3.RECORD_LAYERS[name] in layers, name
    assert set(v3.UNITS) == set(v3.RECORD_KINDS) == set(v3.RECORD_LAYERS) == set(names)
    assert set(v3.OBSERVATION_AXES) == set(readouts)
    assert set(v3.RECORD_NOTES) <= set(names)


def test_orientations_are_flows_or_differences_of_their_sets_roles():
    assert {"membrane_voltage_V", "junction_voltage_V"} <= set(v3.ORIENTATION)
    for name, sign in v3.ORIENTATION.items():
        axes = v3.STATE_AXES.get(name) or v3.OBSERVATION_AXES[name]
        roles = ROLES[axes[-1]]
        ends = ("plus", "minus") if "plus" in sign else ("from", "to")
        assert set(sign) <= {*ends, "says", "confirmed", "source"}, name
        assert sign[ends[0]] in roles and sign[ends[1]] in roles, name
        assert sign[ends[0]] != sign[ends[1]] and sign["says"], name
    membrane, junction = v3.ORIENTATION["membrane_voltage_V"], v3.ORIENTATION["junction_voltage_V"]
    assert (membrane["plus"], membrane["minus"]) == ("inside", "outside")
    assert (junction["plus"], junction["minus"]) == ("sender", "receiver")


def test_the_implementation_object_and_the_composite_adapter_give_them():
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    impl = get_model(parse_spec(raw).model)
    composite = get_model(parse_spec(cs.frozen_definition(raw)).model).inner
    names = ("UNITS", "OBSERVATION_AXES", "RECORD_KINDS", "ORIENTATION", "RECORD_LAYERS")
    for name in (*names, "VIEW_LAYERS", "RECORD_NOTES", "RECORD_DIAGNOSTICS", "RECORD_REFERENCES"):
        assert getattr(impl, name) is getattr(v3, name), name
        assert getattr(composite, name) is getattr(v3, name), name


def sheet():
    """A gated sheet's initial row: its spec, implementation, state, layout and control."""
    spec = parse_spec(water_fixtures.gated_sheet(end_time=0.01))
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return spec, impl, state, p, control


def test_the_voltage_differences_on_data():
    spec, impl, state, p, _ = sheet()
    history = impl.STATE_TYPE(*(np.asarray(v)[None] for v in state))
    observed = impl.observe_history(np.zeros(1), history, p, [0.0], spec)
    cell, outside = observed.cell_potential_V[0], observed.extracellular_potential_V[0]
    membranes, junctions = np.asarray(p.membrane_active), np.asarray(p.junction_active)
    assert junctions.any()
    membrane = cell[p.membrane_cell] - outside[p.membrane_outside]
    junction = cell[p.junction_sender] - cell[p.junction_receiver]
    np.testing.assert_array_equal(observed.membrane_voltage_V[0][membranes], membrane[membranes])
    np.testing.assert_array_equal(observed.junction_voltage_V[0][junctions], junction[junctions])
    assert np.max(np.abs(junction[junctions])) > 1e-6  # A sign is checked, not 0 = 0.


def test_a_positive_flux_leaves_the_patchs_cell_or_the_junctions_sender():
    _, impl, state, p, control = sheet()
    w = impl.readouts(state, control, p, xp=np)
    rates, derivative = w.field.rates, w.derivative
    membrane = np.asarray(rates.membrane_flux_fmol_s)  # Every patch's total, outward.
    junction = np.asarray(rates.junction_flux_fmol_s)
    cells = np.zeros_like(np.asarray(derivative.amount_increment))
    expected = (
        -scatter(membrane, cells, (p.membrane_cell,), xp=np)
        - scatter(junction, cells, (p.junction_sender,), xp=np)
        + scatter(junction, cells, (p.junction_receiver,), xp=np)
    )
    active = np.asarray(p.active)
    got = np.asarray(derivative.amount_increment)[:, active]
    scale = np.max(np.abs(membrane)) + np.max(np.abs(junction))
    np.testing.assert_allclose(got, expected[:, active], rtol=0, atol=1e-12 * scale)
    assert np.max(np.abs(junction)) > 0  # The junction term is exercised.


INNER_AXES = {  # The run view's inner axis sets (cells/records/run_view.py, AXIS_SETS).
    "species",
    "cell_slot",
    "extracellular_slot",
    "membrane_slot",
    "edge_slot",
    "face_slot",
    "channel_slot",
    "gate",
    "field_node",
    "world",
    "floating_component",
}


def test_a_kind_worlds_declarations_cover_its_kinds_fields():
    """FR-4's development world with the passive routes, B4's closure and the transporter (its
    declarations landed with the FR lane's): the implementation object folds the kinds'
    declarations into @3's, every field and column of the structure is declared, and every axis
    has a view set (an inner one, a kind's axis set or a kind's own view set)."""
    from validation.compartment_ph_engine import definitions as defs

    raw = defs.development_world(defs.fr4_world())
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    assert [k for k, _ in impl.structure.kinds] == [
        "cells.kind.passive_routes@1",
        "cells.kind.rapid_proton_buffer@1",
        "cells.kind.transporter@1",
    ]
    cycles = impl.ORIENTATION["transporter_cycles"]  # Outward-positive: the role leaves the cell.
    assert (cycles["from"], cycles["to"]) == ("inside", "outside")
    assert "transporter_fuel_supplied_fmol" not in impl.ORIENTATION
    names = [*impl.STATE_TYPE._fields, *(f for f in impl.OBSERVATION_FIELDS if f != "times")]
    layers = {layer["id"] for layer in impl.VIEW_LAYERS}
    for name in names:
        assert impl.UNITS[name] and impl.RECORD_KINDS[name] in RECORD_KINDS, name
        assert impl.RECORD_LAYERS[name] in layers, name
    readouts = [f for f in names if f not in impl.STATE_TYPE._fields]
    assert set(readouts) <= set(impl.OBSERVATION_AXES)
    sets = impl.view_sets(spec)
    routes = sets["passive_route"]
    assert routes["ids"] == [r["id"] for r in raw["model"]["passive_routes"]]
    assert set(routes["roles"]) == {"inside", "outside"}
    laws = [r["law"] for r in raw["model"]["passive_routes"]]
    assert [law["law_id"] for law in routes["laws"]] == laws  # Each route's law, under laws.
    assert routes["kinds"] == [passive_routes.KIND_WORDS[law] for law in laws]  # Words.
    # A word for every law (main's Seam F step 1, 2e6fa1bf, renamed LAWS to VERSION_1_LAWS).
    assert set(passive_routes.KIND_WORDS) == set(passive_routes.VERSION_1_LAWS)
    assert not any("@" in word for word in passive_routes.KIND_WORDS.values())
    assert impl.ORIENTATION["passive_transferred"]["from"] == "outside"  # Inward-positive.
    axes = {a for name in names for a in (impl.STATE_AXES.get(name) or impl.OBSERVATION_AXES[name])}
    assert axes <= INNER_AXES | set(impl.VIEW_AXIS_SETS) | set(sets), axes - INNER_AXES
    assert impl.VIEW_AXIS_SETS == {"node": "node"}
    for name in v3.UNITS:  # @3's own entries are unchanged in a kind world.
        assert impl.UNITS[name] == v3.UNITS[name]


def test_the_passive_route_laws_declare_their_provenance():
    routes = inner_laws.ROUTE_LAWS
    assert set(routes) == {
        inner_laws.MEMBRANE_ROUTE_LAW_ID,
        inner_laws.FACE_ROUTE_LAW_ID,
        inner_laws.FORMS_FACE_ROUTE_LAW_ID,  # MT-1b's forms face (D288), parity with the face's.
    }
    for law_id, law in routes.items():
        assert law.law_id == law_id and law.provenance in ("parity", "cited", "calibrated")
        assert law.basis
    assert routes[inner_laws.MEMBRANE_ROUTE_LAW_ID].hosts == ("membrane", "junction")
    for face in (inner_laws.FACE_ROUTE_LAW_ID, inner_laws.FORMS_FACE_ROUTE_LAW_ID):
        assert "not a reproduction" in routes[face].basis
    assert routes[inner_laws.FORMS_FACE_ROUTE_LAW_ID].test  # Its degenerate-equivalence row.


def records_and_layout(impl):
    records = {*impl.STATE_TYPE._fields, *(f for f in impl.OBSERVATION_FIELDS if f != "times")}
    return records, {*impl.LAYOUT_TYPE._fields, *impl.FLOOR_LAYOUT_TYPE._fields}


def test_record_diagnostics_and_references_name_records_and_layout_fields():
    """@3's residual records and increment references: every named field is a record of the
    model and every reference a field of its layout (both layout types)."""
    assert v3.RECORD_DIAGNOSTICS == (
        "charge_residual_C",
        "component_current_residual_A",
        "energy_balance_pJ_s",
    )
    assert dict(v3.RECORD_REFERENCES) == {
        "amount_increment": "amount_reference",
        "extracellular_amount_increment": "extracellular_amount_reference",
    }
    records = {*v3.STATE_AXES, *(f for f in v3.OBSERVATION_FIELDS if f != "times")}
    assert set(v3.RECORD_DIAGNOSTICS) <= records
    assert set(v3.RECORD_REFERENCES) <= set(v3.STATE_AXES)
    for layout in (v3.LAYOUT_TYPE, v3.FLOOR_LAYOUT_TYPE):
        assert set(v3.RECORD_REFERENCES.values()) <= set(layout._fields), layout
    for name in v3.RECORD_DIAGNOSTICS:  # Readouts with an axis and a unit, like every record.
        assert v3.OBSERVATION_AXES[name] and v3.UNITS[name], name


def test_a_kind_world_folds_the_kinds_record_roles():
    """FR-4's development world (as above): today's kinds declare no residual record and no
    reference, so the object gives @3's; a kind's own entries are folded in where its structure has
    the fields (a test-local registry with the passive routes' view extended), and dropped where
    it has not."""
    import dataclasses

    from cells.kinds import passive_routes, proton_buffer
    from cells.registry import kind_registry
    from validation.compartment_ph_engine import definitions as defs

    raw = defs.development_world(defs.fr4_world())
    raw["model"].pop("transporters")
    impl = get_model(parse_spec(raw).model)
    records, layout = records_and_layout(impl)
    assert impl.RECORD_DIAGNOSTICS == v3.RECORD_DIAGNOSTICS
    assert dict(impl.RECORD_REFERENCES) == dict(v3.RECORD_REFERENCES)
    assert set(impl.RECORD_DIAGNOSTICS) <= records
    assert set(impl.RECORD_REFERENCES) <= records
    assert set(impl.RECORD_REFERENCES.values()) <= layout
    view = passive_routes.VIEW._replace(
        record_diagnostics=("passive_dissipated_energy_pJ", "no_such_record"),
        record_references={"passive_transferred": "passive_permeability", "no_such": "field"},
    )
    kinds = kind_registry.KindRegistry()
    kinds.register(dataclasses.replace(passive_routes.PASSIVE_ROUTES, view=view))
    kinds.register(proton_buffer.PROTON_BUFFER)
    with kind_registry.scope(kinds):
        planted = get_model(parse_spec(raw).model)
    assert planted.RECORD_DIAGNOSTICS == (*v3.RECORD_DIAGNOSTICS, "passive_dissipated_energy_pJ")
    assert dict(planted.RECORD_REFERENCES) == {
        **v3.RECORD_REFERENCES,
        "passive_transferred": "passive_permeability",
    }
