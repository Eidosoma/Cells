"""Explicit bath ownership, exact static reductions and hard physical domains."""

from copy import deepcopy
from functools import lru_cache
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import surface_open_calcium_bath_events_spec as calcium_schema
from cells.core import surface_open_calcium_energy_bath_events_spec as fuel_schema
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import surface_open_calcium_bath_events as calcium
from cells.models import surface_open_calcium_energy_bath_events as fuel
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_environment_transport as literal
from cells.processes.electrochemistry import F
from validation.tissue import open_calcium_bath_fixtures as fixtures
from validation.tissue import open_calcium_bath_reference as reference
from validation.tissue import open_calcium_fixtures as static_fixtures

OWNERS = dict(calcium=(calcium_schema, calcium, 36), energy=(fuel_schema, fuel, 40))


@lru_cache
def setup(family, case="overlap", padded=True):
    schema, model, count = OWNERS[family]
    raw = fixtures.definition(family, case, padded=padded)
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    return schema, model, count, raw, spec, state, p


def control(schema, spec, time):
    table = control_values(schema.owner_spec(spec), [time])
    return type(table)(*(value[0] for value in table))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_new_five_ion_counterion_has_real_chemical_routes_and_unchanged_background(family):
    _, model, _, raw, spec, _, p = setup(family)
    original = static_fixtures.definition(family, "mixed")
    ion, before = raw["model"]["ionic"], original["model"]["ionic"]
    assert {row["id"]: row["valence"] for row in ion["species"]}["M"] == -1
    for group in ("cells", "extracellular"):
        for row, old in zip(ion[group], before[group], strict=True):
            assert row["fixed_charge_equivalent_fmol"] == old["fixed_charge_equivalent_fmol"]
            assert (
                row["initial_amount_fmol"]["Cl"] + row["initial_amount_fmol"]["M"]
                == old["initial_amount_fmol"]["Cl"]
            )
    for row in raw["model"]["stores"]:
        store = row["model"]
        species = next(value for value in store["species"] if value["id"] == "M")
        assert species["valence"] == -1 and species["moieties"]["M"] == 1
        assert all(value["moieties"]["M"] == 0 for value in store["species"] if value["id"] != "M")
        assert all(owner["initial_amount_fmol"]["M"] > 0 for owner in store["compartments"])
        assert "M" in store["membrane"]["permeability_m_per_s"]
    stores = {row["cell_id"]: row["model"] for row in raw["model"]["stores"]}
    for group in raw["experiment"]["store_controls"]:
        species = {row["id"] for row in stores[group["cell_id"]]["species"]}
        for row in group["controls"]:
            assert set(row["passive"]) == species
            assert row["passive"]["M"] == row["passive"]["Cl"]
    for kind, field in (
        ("membranes", "permeability_m_per_s"),
        ("junctions", "permeability_m_per_s"),
        ("faces", "diffusivity_m2_per_s"),
    ):
        assert all("M" in row[field] for row in ion[kind])
    static = OWNERS[family][0].parent.parse(fixtures.static_definition(raw))
    _, original_layout = model.base.initial_values(static)
    for key, value in model.parent_layout(p)._asdict().items():
        np.testing.assert_array_equal(value, getattr(original_layout, key), err_msg=key)
    assert len(static.model.channels) == len(spec.model.channels)
    assert len({row.kinetic_law for row in spec.model.channels}) == 56


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("empty", "disabled", "init"))
@pytest.mark.parametrize("padded", (False, True))
def test_exact_reduction_to_corresponding_static_five_ion_owner(family, case, padded):
    schema, model, count, _, spec, state, p = setup(family, case, padded)
    ordinary = schema.owner_spec(spec)
    old, q = model.base.initial_values(ordinary)
    assert len(state) == count == len(old) + 2
    np.testing.assert_array_equal(model.signal_values(state, p, xp=np).dose_fmol, 0)
    for key in q._fields:
        np.testing.assert_array_equal(getattr(p, key), getattr(q, key), err_msg=key)
    u = control(schema, spec, 0.0)
    history, static_history = [state], [old]
    for _ in range(2):
        a = model.rhs(state, u, p, p.active, xp=np)
        b = model.base.rhs(old, u, q, q.active, xp=np)
        for key in old._fields:
            np.testing.assert_array_equal(getattr(a, key), getattr(b, key), err_msg=key)
        state = rk4_step(
            lambda y, *args: model.rhs(y, *args, xp=np), state, fixtures.DT, u, p, p.active
        )
        old = rk4_step(
            lambda y, *args: model.base.rhs(y, *args, xp=np), old, fixtures.DT, u, q, q.active
        )
        model.check_values(state, spec)
        model.base.check_values(old, ordinary)
        for key in old._fields:
            np.testing.assert_array_equal(getattr(state, key), getattr(old, key), err_msg=key)
        history.append(state)
        static_history.append(old)
    times = np.asarray([0.0, fixtures.DT, 2 * fixtures.DT])
    observed = model.observe_history(
        times,
        model.STATE_TYPE(
            *(np.stack([getattr(row, key) for row in history]) for key in state._fields)
        ),
        p,
        times,
        spec,
    )
    expected = model.base.observe_history(
        times,
        model.base.STATE_TYPE(
            *(np.stack([getattr(row, key) for row in static_history]) for key in old._fields)
        ),
        q,
        times,
        ordinary,
    )
    for key in model.base.OBSERVATION_FIELDS:
        np.testing.assert_array_equal(getattr(observed, key), getattr(expected, key), err_msg=key)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_literal_setters_and_initial_operation_preserve_full_anchors(family, case):
    schema, model, count, raw, spec, state, p = setup(family, case)
    original = {key: np.array(value, copy=True) for key, value in p._asdict().items()}
    grid = SimpleNamespace(
        identity="explicit_owned_calcium_bath",
        species_ids=spec.model.species_ids,
        site_ids=("one_declared_reservoir",),
        kernel=SimpleNamespace(valence=np.asarray(spec.model.valence)),
    )
    for time in (0.0, 0.25e-6, 2e-6, 4e-6, 6e-6, fixtures.END):
        stage = state._replace(phase_clock_s=np.asarray([time]))
        outside = model.physical_amounts(stage, p)[1]
        for j, row in enumerate(spec.model.extracellular):
            baseline = np.asarray(row.initial_amount_fmol) / row.volume_pL
            bound = literal.compile_baths(
                grid,
                spec.model.bath_events,
                baseline,
                is_ecm=True,
                enabled_Cl=spec.model.enabled_Cl,
            )
            expected = literal.apply_baths(
                time,
                baseline,
                baseline[:, None],
                bound,
                grid,
                SimpleNamespace(faraday_C_mol=F),
                xp=np,
            ).boundary_mol_m3
            if spec.model.phase == "INIT" or row.id not in spec.model.bath_site_ids:
                expected = baseline
            np.testing.assert_allclose(
                outside[:, j], row.volume_pL * expected, rtol=5e-15, atol=2e-13
            )
    # Reaction declarations have a canonical species/moiety order. Retain
    # every declared value while comparing only that documented reordering.
    canonical = deepcopy(raw)
    for row in canonical["model"]["stores"]:
        row["model"]["species"].sort(key=lambda species: species["id"])
        row["model"]["moieties"].sort()
    if family == "energy":
        # Pools follow their declared cell owners; control groups follow ports.
        # The permutation fixture deliberately starts with different list order.
        owners = [row["id"] for row in canonical["model"]["ionic"]["cells"]]
        ports = [row["id"] for row in canonical["model"]["regeneration_ports"]]
        canonical["model"]["energy_pools"].sort(key=lambda row: owners.index(row["cell_id"]))
        canonical["experiment"]["regeneration_controls"].sort(
            key=lambda row: ports.index(row["regeneration_id"])
        )
    assert len(state) == count and schema.to_dict(spec) == canonical
    assert schema.parse(canonical) == spec
    operation = model.initial_operation(spec)
    signal = model.signal_values(state, p, xp=np)
    np.testing.assert_array_equal(operation["dose_fmol"], signal.dose_fmol)
    np.testing.assert_array_equal(operation["electrode_charge_C"], -signal.charge_C)
    if case == "overlap":
        assert np.any(signal.dose_fmol != 0) and np.any(signal.charge_C != 0)
    for key, value in p._asdict().items():
        np.testing.assert_array_equal(value, original[key], err_msg=key)
    record = schema.artifact(spec)
    assert schema.to_dict(schema.replay(record)) == canonical
    bad = deepcopy(record)
    bad["initial_operation"]["dose_fmol"][0][0] += 0.1
    with pytest.raises(ConfigError, match="replay"):
        schema.replay(bad)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "bad",
    (
        "finite_target",
        "duplicate_target",
        "missing_M",
        "wrong_M",
        "reordered",
        "negative_domain",
        "outside_window",
        "zero_change",
        "nan_amplitude",
        "bool_guard",
        "static_policy",
        "clock_policy",
        "pulse_ceiling",
    ),
)
def test_explicit_counterion_clock_controller_and_ceiling_admission(family, bad):
    raw = fixtures.definition(family)
    m = raw["model"]
    if bad == "finite_target":
        m["bath_site_ids"] = [
            next(row["id"] for row in m["ionic"]["extracellular"] if not row["reservoir"])
        ]
    elif bad == "duplicate_target":
        m["bath_site_ids"] *= 2
    elif bad in ("missing_M", "wrong_M"):
        if bad == "missing_M":
            # The real four-ion owner is otherwise valid; only the requested
            # K/Na setters lack their required explicit counterion.
            raw = fixtures.definition(family, "cl_only")
            raw["model"]["bath_events"][0]["kind"] = "K_env"
        else:
            next(row for row in m["ionic"]["species"] if row["id"] == "M")["valence"] = 1
    elif bad == "reordered":
        m["bath_events"].reverse()
    elif bad == "negative_domain":
        m["bath_events"][0]["amplitude"] = -1.1
    elif bad == "outside_window":
        m["bath_events"][0]["off_s"] = 2 * fixtures.END
    elif bad == "zero_change":
        m["bath_events"][0]["change_s"] = 0.0
    elif bad == "nan_amplitude":
        m["bath_events"][0]["amplitude"] = float("nan")
    elif bad == "bool_guard":
        m["enabled_Cl"] = 1
    elif bad == "static_policy":
        m["exterior_policy"] = "static_declared_ideal_chemical_and_voltage_reservoirs@1"
    elif bad == "clock_policy":
        m["timing_policy"] = "host_step_only"
    elif bad == "pulse_ceiling":
        total = static_fixtures.ionic_totals(m)["K"]
        dose = m["bath_events"][0]["amplitude"] * sum(
            row["initial_amount_fmol"]["K"]
            for row in m["ionic"]["extracellular"]
            if row["id"] in m["bath_site_ids"]
        )
        m["ionic_moiety_ceiling_fmol"]["K"] = total + 0.5 * dose
    with pytest.raises(ConfigError):
        OWNERS[family][0].parse(raw)
    with pytest.raises(ValueError):
        reference.bind(raw)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_ramp_original_step_guards_and_actual_dose_ceiling(family):
    schema, model, _, raw, spec, state, p = setup(family)
    u = control_values(schema.owner_spec(spec), [0.0])
    model.check_steps(spec, np.asarray([fixtures.DT]), u)
    ceiling = min(event.change_s / 8 for event in spec.model.bath_events)
    with pytest.raises(ConfigError, match="transition"):
        model.check_steps(spec, np.asarray([ceiling * (1 + 1e-7)]), u)
    for value in (float("nan"), -1e-9, 1e-2):
        with pytest.raises(ConfigError):
            model.check_steps(spec, np.asarray([value]), u)
    peak = state._replace(phase_clock_s=np.asarray([2.125e-6]))
    signal = model.signal_values(peak, p, xp=np)
    limits = p.open_ionic_moiety_ceiling_fmol.copy()
    k = spec.model.species_ids.index("K")
    limits[k] = static_fixtures.ionic_totals(raw["model"])["K"] + signal.dose_fmol[k].sum() / 2
    restricted = p._replace(open_ionic_moiety_ceiling_fmol=limits)
    assert not model.domain_valid(peak, restricted, p.active, xp=np)
    assert all(
        np.isnan(value).all()
        for value in model.rhs(peak, control(schema, spec, 0), restricted, p.active, xp=np)
    )
    bad = state._replace(reservoir_chemical_work_pJ=np.where(~p.reservoir, 1.0, 0.0))
    assert not model.domain_valid(bad, p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(bad, spec)
