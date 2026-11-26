"""Tier-1 smoke test of cells.operator.membrane_entity_state@1 (docs/PUMP_COMPOSITE_V2_DESIGN.md §3).

On the bound heredity cell, in NumPy (no compile): zero increments give @3's declared layout
bit for bit (R8, with the field arrays selected as bound); increments reach the view as area,
capacitance and abundance (a fixed number of units keeps its conductance); the entity ledgers
and domain; catalogue references never reach bindings or the batch signature, only the
summary and the definition; definition refusals; an empty population's abundance and flux exactly
zero at a moved area (one row, with its plant; the independent Lean project's findings of 20
November 2026). The compiled guards are test_membrane_insertion_runs.py.
"""

import copy

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS, membrane_state
from cells.operators.contract import check_declarations
from cells.operators.membrane_state import MembraneEntityState
from cells.registry.models import get_model
from tests import membrane_insertion_fixtures as fx
from validation.fr7 import unit_turnover_fixtures as ufx

CATALOGUE = {
    "kir_0": {"catalogue": "test_catalogue", "entry": "kir2.1"},
    "nav_0": {"catalogue": "test_catalogue", "entry": "nav1.2"},
}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(fx.with_operators(fx.one_patch()))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, model.operators[0], state, p


def test_zero_increments_give_the_declared_layout_bitwise(bound):
    _, model, _, state, p = bound
    assert model.field_inputs  # Capacitance is a field input: the view refreshes the field.
    view, declared = model.view(p, state, xp=np), adapter.inner_layout(p)
    for name in declared._fields:
        a, b = np.asarray(getattr(view, name)), np.asarray(getattr(declared, name))
        assert a.dtype == b.dtype and a.tobytes() == b.tobytes(), name


def test_increments_reach_the_view(bound):
    _, model, op, state, p = bound
    a0, c0 = float(p.membrane_area[0]), float(p.membrane_capacitance[0])
    abundance0 = np.asarray(p.channel_abundance)
    grown = state._replace(
        membrane_area_increment_m2=np.array([0.5 * a0]),
        membrane_capacitance_increment_F=np.array([0.25 * c0]),
    )
    view = model.view(p, grown, xp=np)
    assert view.membrane_area[0] == 1.5 * a0 and view.membrane_capacitance[0] == 1.25 * c0
    # A fixed number of units keeps its conductance: abundance x area is unchanged.
    np.testing.assert_allclose(view.channel_abundance * 1.5 * a0, abundance0 * a0, rtol=1e-15)
    np.testing.assert_allclose(view.field_capacitor_matrix[0, 0], 1.25 * c0, rtol=1e-15)
    added = grown._replace(population_abundance_increment=np.array([2.0e3, 0.0]))
    view = model.view(p, added, xp=np)
    expected = abundance0[0] / 1.5 + 2.0e3 / (1.5 * a0 * fx.DENSITY)
    assert view.channel_abundance[0] == pytest.approx(expected, rel=1e-15)
    units = op.observe({}, added, None, p, view, model, None)["population_units"]
    assert units[0] == pytest.approx(abundance0[0] * a0 * fx.DENSITY + 2.0e3, rel=1e-15)


def test_entity_ledgers_and_domain(bound):
    _, model, op, state, p = bound
    assert all(not np.any(v) for v in op.own_ledgers(state, p, xp=np).values())
    moved = state._replace(membrane_area_increment_m2=np.array([1e-14]))
    ledgers = model.balances(moved, p)  # No writer: the increment itself is the residual.
    assert ledgers["membrane_area_entity"][0] == 1e-14
    assert op.domain_valid(state, p, None, xp=np)
    for bad in (
        state._replace(membrane_area_increment_m2=-np.asarray(p.membrane_area)),
        state._replace(membrane_capacitance_increment_F=np.array([np.nan])),
        state._replace(population_abundance_increment=np.array([-1e12, 0.0])),
    ):
        assert not op.domain_valid(bad, p, None, xp=np)


def test_catalogue_references_never_reach_the_arrays():
    plain = parse_spec(fx.with_operators(fx.one_patch()))
    named = parse_spec(fx.with_operators(fx.one_patch(), catalogue=CATALOGUE))
    model = get_model(plain.model)
    assert get_model(named.model) is model
    for x, y in zip(model.initial_values(plain), model.initial_values(named), strict=True):
        for a, b in zip(x, y, strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    assert model.batch_signature(plain.model) == model.batch_signature(named.model)
    op, declaration = model.operators[0], named.model.operators[0]
    carried = op.summary(named, declaration, (), None)["membrane_populations"]
    assert carried["kir_0"]["catalogue"] == CATALOGUE["kir_0"]
    assert (
        op.summary(plain, plain.model.operators[0], (), None)["membrane_populations"]["kir_0"][
            "catalogue"
        ]
        is None
    )
    assert parse_spec(named.to_dict()) == named  # The definition carries the references.
    assert plain.fingerprint != named.fingerprint


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda b: b["populations"].pop(), "every channel population exactly once"),
        (lambda b: b["populations"].append(copy.deepcopy(b["populations"][0])), "exactly once"),
        (lambda b: b["populations"][0].update(channel_id="nobody"), "exactly once"),
        (lambda b: b["populations"][0].update(catalogue={"catalogue": "x"}), "missing"),
        (lambda b: b["populations"][0].update(catalogue={"catalogue": "x", "entry": ""}), "entry"),
        (lambda b: b["populations"][0].update(reference_density_per_m2=0.0), "positive"),
    ],
)
def test_definition_refusals(change, message):
    raw = fx.with_operators(fx.one_patch())
    change(raw["model"]["operators"][0])
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


def test_a_state_owner_has_no_part_and_a_second_owner_is_refused():
    check_declarations(MembraneEntityState)
    assert OPERATORS[fx.STATE].LAW_ID == fx.STATE
    raw = fx.with_operators(fx.one_patch())
    raw["model"]["operators"].append(copy.deepcopy(raw["model"]["operators"][0]))
    with pytest.raises(ConfigError, match="appears twice"):
        parse_spec(raw)


def test_operators_that_read_the_declared_area_refuse_the_membrane_state():
    """Water binds its conductance from the declared areas and replacement scales template
    pumps by them: both hold membrane_area as declared (CONFLICTS_VIEW)."""
    from cells.models import pump_composite

    for law in ("cells.operator.ideal_osmosis_linear_compliance_water@1", "cells.operator.scheduled_cell_replacement@1"):
        errors = pump_composite.structure_errors(adapter, (OPERATORS[law], OPERATORS[fx.STATE]))
        assert any(f"{law} reads membrane_area as declared" in e for e in errors), law


def two_term(state, p, *, xp):  # Planted: the abundance as it landed, two rounded terms always.
    patch = p.channel_membranes
    a = membrane_state.area(state, p, xp=xp)[patch]
    value = p.channel_abundance * (p.membrane_area[patch] / a) + (
        state.population_abundance_increment / (a * p.population_reference_density_per_m2)
    )
    return xp.where(p.channel_active, value, p.channel_abundance)


def emptied(area_ratio):
    """(units, abundance, K flux) of FR-7's unit cell with every unit withdrawn and its patch at
    area_ratio of its declared area: the Lean project's states (lean/checks/population_units.py
    surface, 3072 and 1536 units; 0.7 is a retrieval's 30% removal, as in its trafficking case)."""
    raw = ufx.cell(dt=1 / 1024, end=8 / 1024)
    raw["model"]["membranes"][0]["area_m2"] = 2.0**-32
    for row in raw["model"]["operators"][0]["populations"]:
        row["reference_density_per_m2"] = 3.0 * 2**42
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [0.0])))
    counts = np.asarray(membrane_state.units(state, p, xp=np))
    state = state._replace(
        membrane_area_increment_m2=np.asarray(p.membrane_area) * (area_ratio - 1),
        population_abundance_increment=-counts,
    )
    k = list(spec.model.species_ids).index("K")
    flux = model.readouts(state, control, p, xp=np).ionic.channel_flux_fmol_s[k]
    q = model.view(p, state, xp=np)
    return np.asarray(membrane_state.units(state, p, xp=np)), np.asarray(q.channel_abundance), flux


@pytest.mark.parametrize("area_ratio", [1.4, 1.8, 0.7], ids=["producer", "grown", "retrieval"])
def test_an_empty_population_has_exactly_zero_abundance_and_flux_at_a_moved_area(area_ratio):
    """Zero units give exactly zero abundance and potassium flux, whatever the area. Planted: the
    two-term abundance, which leaves -1.1e-16, +1.1e-16 and -2.2e-16 here."""
    units, abundance, flux = emptied(area_ratio)
    assert np.all(units == 0) and np.all(abundance == 0) and np.all(np.asarray(flux) == 0)
    saved = membrane_state.abundance
    membrane_state.abundance = two_term
    try:
        _, abundance, flux = emptied(area_ratio)
    finally:
        membrane_state.abundance = saved
    assert np.any(abundance != 0) and np.any(np.asarray(flux) != 0)
