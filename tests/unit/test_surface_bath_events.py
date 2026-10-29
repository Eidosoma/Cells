"""Scientific admission, literal setters, external controllers and exact owner retention."""

from copy import deepcopy
from functools import lru_cache
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import surface_active_bath_events_spec as active_schema
from cells.core import surface_bath_events_binding as binding
from cells.core import surface_passive_bath_events_spec as passive_schema
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import surface_active_bath_events as active
from cells.models import surface_passive_bath_events as passive
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_environment_transport as literal
from cells.processes.electrochemistry import F, R
from validation.transport import surface_bath_events_fixtures as fixtures
from validation.transport import surface_bath_events_reference as reference

OWNERS = {"passive": (passive_schema, passive, 14), "active": (active_schema, active, 21)}


@lru_cache
def setup(family, case="overlap"):
    schema, model, count = OWNERS[family]
    raw = fixtures.definition(family, case)
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    return schema, model, count, raw, spec, state, p


def control(schema, spec, time):
    table = control_values(schema.owner_spec(spec), [time])
    return type(table)(*(v[0] for v in table))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", fixtures.CASES)
def test_literal_native_bath_setters_and_explicit_controllers(family, case):
    _, model, _, _, spec, state, p = setup(family, case)
    grid = SimpleNamespace(
        identity="literal_bath_owner",
        species_ids=spec.model.species_ids,
        site_ids=("declared_reservoir",),
        kernel=SimpleNamespace(valence=np.asarray(spec.model.valence)),
    )
    for time in (0.0, 0.25e-6, 2.5e-6, 4e-6, 6e-6, fixtures.END):
        trial = state._replace(phase_clock_s=np.asarray([time]))
        s = model.signal_values(trial, p, xp=np)
        original = model.base.physical_amounts(model.parent_state(trial), model.parent_layout(p))
        actual = model.physical_amounts(trial, p)[1]
        for j, owner in enumerate(spec.model.extracellular):
            baseline = np.asarray(owner.initial_amount_fmol) / owner.volume_pL
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
            if spec.model.phase == "INIT" or owner.id not in spec.model.bath_site_ids:
                expected = baseline
            np.testing.assert_allclose(
                actual[:, j], owner.volume_pL * expected, rtol=5e-15, atol=2e-13
            )
        physical = model.physical_state(trial, p, xp=np)
        np.testing.assert_array_equal(physical.reservoir_supplied, s.dose_fmol)
        np.testing.assert_array_equal(physical.electrode_charge_transferred_C, -s.charge_C)
        np.testing.assert_array_equal(physical.reservoir_work_pJ, s.electrochemical_work_pJ)
        np.testing.assert_array_equal(physical.electrode_work_pJ, s.electrode_work_pJ)
        np.testing.assert_array_equal(model.physical_amounts(trial, p)[0], original[0])
        np.testing.assert_allclose(model.balances(trial, p)["energy"], 0.0, rtol=0, atol=1e-10)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_initial_logistic_tails_are_explicit_original_anchor_operation(family):
    schema, model, count, raw, spec, state, p = setup(family)
    original = {k: np.array(v, copy=True) for k, v in p._asdict().items()}
    s = model.signal_values(state, p, xp=np)
    operation = model.initial_operation(spec)
    assert len(state) == count
    assert np.any(s.dose_fmol != 0)
    assert np.any(s.charge_C != 0)
    np.testing.assert_array_equal(operation["dose_fmol"], s.dose_fmol)
    np.testing.assert_array_equal(operation["electrode_charge_C"], -s.charge_C)
    assert operation["time_s"] == 0.0
    assert operation["kind"] == binding.PREPARATION_KIND
    for key in (
        "amount_increment",
        "extracellular_amount_increment",
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
    ):
        np.testing.assert_array_equal(getattr(state, key), 0)
    artifact = schema.artifact(spec)
    assert schema.to_dict(schema.replay(artifact)) == raw
    assert schema.to_dict(spec) == raw
    model.check_values(state, spec)
    model.readouts(state, control(schema, spec, 0.0), p, xp=np)
    for key, value in p._asdict().items():
        np.testing.assert_array_equal(value, original[key], err_msg=key)
    corrupt = deepcopy(artifact)
    corrupt["initial_operation"]["dose_fmol"][0][0] += 0.1
    with pytest.raises(ConfigError, match="replay"):
        schema.replay(corrupt)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("empty", "disabled", "init"))
def test_empty_or_disabled_program_reduces_exactly_to_complete_parent(family, case):
    schema, model, _, _, spec, state, p = setup(family, case)
    ordinary = schema.owner_spec(spec)
    y, q = model.base.initial_values(ordinary)
    u = control(schema, spec, 0.0)
    target = model.base.rhs(y, u, q, q.active, xp=np)
    actual = model.rhs(state, u, p, p.active, xp=np)
    for key in model.base.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(actual, key), getattr(target, key), err_msg=key)
    stage = model.signal_values(state, p, xp=np)
    np.testing.assert_array_equal(stage.dose_fmol, 0.0)
    np.testing.assert_array_equal(stage.dose_rate_fmol_s, 0.0)
    np.testing.assert_array_equal(stage.pulse, 0.0)
    if family == "active":
        assert len({v.kinetic_law for v in spec.model.channels}) == 56
        assert len(spec.experiment.channels) == len(spec.model.channels)
        assert len(spec.experiment.pumps) == len(spec.model.membranes)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_variable_chemical_work_replaces_only_the_invalid_constant_mu_identity(family):
    schema, model, _, _, spec, state, p = setup(family)
    u = control(schema, spec, 0.0)
    evolved = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, 1e-9, u, p, p.active)
    model.check_values(evolved, spec)
    s = model.signal_values(evolved, p, xp=np)
    physical = model.physical_state(evolved, p, xp=np)
    initial_co = np.where(
        p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1
    )
    mu0 = R * p.temperature * np.log(initial_co) + p.valence * F * p.boundary_V
    stale = physical.reservoir_work_pJ - 1e-3 * np.sum(mu0 * physical.reservoir_supplied, axis=0)
    assert np.max(np.abs(stale)) > 1e-7
    np.testing.assert_allclose(model.balances(evolved, p)["reservoir_work"], 0, rtol=0, atol=3e-12)
    np.testing.assert_allclose(
        physical.reservoir_work_pJ + physical.electrode_work_pJ,
        evolved.reservoir_work_pJ + evolved.electrode_work_pJ + s.chemical_work_pJ,
        rtol=5e-15,
        atol=3e-12,
    )
    changed = evolved._replace(
        reservoir_chemical_work_pJ=evolved.reservoir_chemical_work_pJ
        + np.where(p.reservoir, 1e-5, 0)
    )
    assert model.domain_valid(changed, p, p.active, xp=np)
    with pytest.raises(NumericalError, match="reservoir_work"):
        model.check_values(changed, spec)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "bad",
    (
        "finite_target",
        "duplicate_target",
        "unknown_target",
        "missing_M",
        "wrong_M",
        "wrong_K",
        "reordered",
        "duplicate_kind",
        "unknown_kind",
        "negative_domain",
        "reversed_window",
        "outside_window",
        "zero_change",
        "nan_amplitude",
        "bool_amplitude",
        "bool_guard",
        "implicit_policy",
        "implicit_baseline",
        "implicit_clock",
    ),
)
def test_refuse_ambiguous_native_or_physical_bath_ownership(family, bad):
    schema = OWNERS[family][0]
    raw = fixtures.definition(family)
    m = raw["model"]
    if bad == "finite_target":
        m["extracellular"][0]["reservoir"] = False
        m["extracellular"][0]["boundary_potential_V"] = 0.0
    elif bad == "duplicate_target":
        m["bath_site_ids"] *= 2
    elif bad == "unknown_target":
        m["bath_site_ids"] = ["missing"]
    elif bad == "missing_M":
        m["species"] = [v for v in m["species"] if v["id"] != "M"]
    elif bad in ("wrong_M", "wrong_K"):
        next(v for v in m["species"] if v["id"] == bad.split("_")[1])["valence"] = 2
    elif bad == "reordered":
        m["bath_events"].reverse()
    elif bad == "duplicate_kind":
        m["bath_events"] = [m["bath_events"][0]] * 2
    elif bad == "unknown_kind":
        m["bath_events"][0]["kind"] = "Ca_env"
    elif bad == "negative_domain":
        m["bath_events"][0]["amplitude"] = -1.1
    elif bad == "reversed_window":
        m["bath_events"][0]["off_s"] = 0.0
    elif bad == "outside_window":
        m["bath_events"][0]["off_s"] = 2 * fixtures.END
    elif bad == "zero_change":
        m["bath_events"][0]["change_s"] = 0
    elif bad == "nan_amplitude":
        m["bath_events"][0]["amplitude"] = float("nan")
    elif bad == "bool_amplitude":
        m["bath_events"][0]["amplitude"] = True
    elif bad == "bool_guard":
        m["enabled_Cl"] = 1
    else:
        m[
            {
                "implicit_policy": "controller_policy",
                "implicit_baseline": "baseline_policy",
                "implicit_clock": "timing_policy",
            }[bad]
        ] = "implicit"
    with pytest.raises(ConfigError):
        schema.parse(raw)
    with pytest.raises(ValueError):
        reference.bind(raw)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_ramp_bound_and_all_inherited_parent_step_checks(family):
    schema, model, _, _, spec, _, _ = setup(family)
    u = control_values(schema.owner_spec(spec), [0.0])
    model.check_steps(spec, np.asarray([fixtures.DT]), u)
    ceiling = min(v.change_s / 8 for v in spec.model.bath_events)
    with pytest.raises(ConfigError, match="transition"):
        model.check_steps(spec, np.asarray([ceiling * (1 + 1e-7)]), u)
    for value in (float("nan"), -1e-9, float("inf")):
        with pytest.raises(ConfigError, match="finite nonnegative"):
            model.check_steps(spec, np.asarray([value]), u)
    # Disabled drivers still retain every inherited gate and junction bound.
    empty = setup(family, "empty")[4]
    with pytest.raises(ConfigError):
        model.check_steps(empty, np.asarray([1e-2]), u)


def test_disabled_native_Cl_guard_requires_neither_Cl_nor_its_counterion():
    raw = fixtures.definition("passive", "disabled")
    m = raw["model"]
    for ion in ("Cl", "M"):
        m["species"] = [v for v in m["species"] if v["id"] != ion]
        for row in (*m["cells"], *m["extracellular"]):
            row["fixed_charge_equivalent_fmol"] -= row["initial_amount_fmol"].pop(ion)
        for kind, key in (
            ("membranes", "permeability_m_per_s"),
            ("junctions", "permeability_m_per_s"),
            ("faces", "diffusivity_m2_per_s"),
        ):
            for row in m[kind]:
                row[key].pop(ion)
        raw["execution"]["material_balance_atol_fmol"].pop(ion)
    spec = passive_schema.parse(raw)
    state, p = passive.initial_values(spec)
    np.testing.assert_array_equal(passive.signal_values(state, p, xp=np).dose_fmol, 0)
    c = reference.bind(raw)
    np.testing.assert_array_equal(reference.program(c, 1e-6)["dose_fmol"], 0)
