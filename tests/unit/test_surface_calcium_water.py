"""Owned molecular particles, shared volumes and joint chemical/water energy."""

import json
from copy import deepcopy
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import RunResult, timeline
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_calcium_water_spec import OSMOTIC_COUPLING_ID, prior_spec
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run
from cells.models import surface_calcium_morris_lecar as prior
from cells.models import surface_calcium_water as model
from cells.models.registry import get_model
from cells.numerics import osmotic_water as water
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import calcium_water_fixtures as fixtures
from validation.tissue import calcium_water_reference as reference
from validation.tissue import water_volume_reference as water_reference

ROOT = Path(__file__).resolve().parents[2]


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    table = control_values(spec, [time])
    return spec, state, p, type(table)(*(v[0] for v in table))


def moved(state):
    state = type(state)(*(v.copy() for v in state))
    state.volume_increment_pL[0] += 0.08
    state.extracellular_volume_increment_pL[0] -= 0.08
    state.water_transferred_pL[0] -= 0.08
    return state


def compare(spec, state, derivative, time=0.0, levels=None):
    c = reference.bind(spec.to_dict())
    target, phi, proof = reference.evaluate(
        c, reference.flatten(c, state._asdict()), time, channel_levels=levels
    )
    ratio = assert_states(
        c,
        reference.flatten(c, derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    return c, phi, dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_identity_and_versioned_whole_chemical_volume_owner(backend):
    raw = fixtures.definition(backend=backend)
    if backend == "cpu":
        assert json.loads((ROOT / "configs/resolved_calcium_water.json").read_text()) == raw
    spec, state, p, _ = initial(raw)
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert len(state) == 38 and len(spec.model.channels) == 60
    assert set(p.channel_laws[p.channel_active]) == set(range(53))
    assert spec.model.chemical_osmotic_coupling == OSMOTIC_COUPLING_ID
    assert spec == parse_spec(spec.to_dict())
    assert prior_spec(spec).to_dict()["model"]["id"] == "resolved_calcium@10"
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    timeline(spec)
    model.check_values(state, spec)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("nonzero", [False, True])
def test_full_38field_current_volume_independent_stage(arm, padded, nonzero):
    spec, state, p, control = initial(fixtures.definition(arm, padded=padded))
    if nonzero:
        state = moved(state)
    before = tuple(v.copy() for v in state)
    if arm == "sealed" and nonzero:
        assert not model.control_domain_valid(state, control, p, p.active, xp=np)
        c = reference.bind(spec.to_dict())
        with pytest.raises(ValueError, match="sealed"):
            reference.evaluate(c, reference.flatten(c, state._asdict()), 0.0)
        return
    actual = model.readouts(state, control, p, xp=np)
    assert actual.valid
    _, phi, checked = compare(spec, state, actual.derivative)
    np.testing.assert_allclose(
        np.r_[
            actual.field.potential_V[:2],
            actual.field.potential_V[p.active.size : p.active.size + 5],
        ],
        phi,
        atol=3e-13,
        rtol=3e-10,
    )
    assert abs(actual.field.energy_balance_pJ_s) < 1e-9
    exact(state, before)
    effective = model.effective_layout(state, p)
    np.testing.assert_array_equal(
        effective.er_volume[np.arange(2), p.er_er], p.er_volume[np.arange(2), p.er_er]
    )
    np.testing.assert_array_equal(
        effective.er_volume[np.arange(2), p.er_cytosol], effective.volume[:2]
    )
    evidence(
        f"calcium-water-stage-{arm}-{padded}-{nonzero}",
        dict(status="passed", inputs=spec.to_dict(), **checked),
    )


def test_each_molecular_particle_once_and_binding_changes_particle_count():
    spec, state, p, control = initial()
    particles = model.osmolyte_amounts(state, p)
    names = [s.id for s in spec.model.stores[0].species]
    for i, store in enumerate(spec.model.stores):
        cy = next(row for row in store.compartments if row.id == store.membrane.cytosol)
        np.testing.assert_array_equal(particles[:, i], cy.initial_amount_fmol)
    ca, buffer, bound = [names.index(k) for k in ("Ca", "B", "CaB")]
    changed = type(state)(*(v.copy() for v in state))
    # Unbinding raises particle count by one per converted complex; ionic
    # moieties and charge stay fixed. The stage need not represent elapsed time.
    changed.chemical_amount_increment[0, [ca, buffer, bound], int(p.er_cytosol[0])] += (
        np.array([1, 1, -1]) * 1e-4
    )
    q = model.osmolyte_amounts(changed, p)
    np.testing.assert_allclose(q[:, 0].sum() - particles[:, 0].sum(), 1e-4, atol=1e-13, rtol=0)
    assert model.maximum_osmolytes(p)[0] >= np.sum(q)
    assert model.readouts(changed, control, p, xp=np).valid
    _, _, checked = compare(spec, changed, model.readouts(changed, control, p, xp=np).derivative)
    evidence(
        "calcium-water-particles",
        dict(status="passed", chemical_species=names, particle_change_fmol=1e-4, **checked),
    )


def ip3_conversion(arm):
    raw = fixtures.definition()
    for store in raw["model"]["stores"]:
        chemical = store["model"]
        source = deepcopy(next(s for s in chemical["species"] if s["id"] == "IP3"))
        source.update(id="IP3_precursor", standard_mu_RT=0.0)
        chemical["species"].append(source)
        for row in chemical["compartments"]:
            row["initial_amount_fmol"]["IP3_precursor"] = row["initial_amount_fmol"]["IP3"] * (
                5 if arm == "source" else 0.2
            )
        chemical["membrane"]["permeability_m_per_s"]["IP3_precursor"] = 0.0
        chemical["reactions"].append(
            dict(
                id="ip3_conversion",
                compartment="cytosol",
                reactants={"IP3_precursor": 1},
                products={"IP3": 1},
                forward_rate_per_s=50.0,
            )
        )
    for row in raw["experiment"]["store_controls"]:
        for change in row["controls"]:
            change["reactions"]["ip3_conversion"] = 1.0
            change["passive"]["IP3_precursor"] = 0.0
    raw["execution"]["reaction_capacity"] += 1
    return raw


@pytest.mark.parametrize("arm", ["binding", "source", "sink"])
def test_endpoint_G_and_directional_derivative_including_ip3_and_water(arm):
    spec, state, p, control = initial(
        fixtures.definition() if arm == "binding" else ip3_conversion(arm)
    )
    state = moved(state)
    value = model.readouts(state, control, p, xp=np)
    assert value.valid
    c, _, checked = compare(spec, state, value.derivative)
    target = reference.free_energy_change(c, reference.flatten(c, state._asdict()))
    np.testing.assert_allclose(model.free_energy_change(state, p), target, atol=2e-11, rtol=2e-12)
    if arm != "binding":
        j = [r.id for r in spec.model.stores[0].reactions].index("ip3_conversion")
        assert np.sign(value.derivative.reaction_extent[0, j]) == (1 if arm == "source" else -1)
    power = (
        value.field.chemical_energy_rate_pJ_s
        + value.field.capacitor_energy_rate_pJ_s
        + value.water.elastic_energy_rate_pJ_s
    )
    errors = []
    for step in (2e-8, 1e-8):
        plus = model.STATE_TYPE(
            *(a + step * b for a, b in zip(state, value.derivative, strict=True))
        )
        minus = model.STATE_TYPE(
            *(a - step * b for a, b in zip(state, value.derivative, strict=True))
        )
        directional = (model.free_energy_change(plus, p) - model.free_energy_change(minus, p)) / (
            2 * step
        )
        # Resolve the small binding-dependent Ndot*log(V/V0) term even when
        # the mechanical/dilution power is much larger in absolute magnitude.
        np.testing.assert_allclose(directional, power, atol=2e-5, rtol=2e-10)
        errors.append(float(abs(directional - power)))
    evidence(
        "calcium-water-energy-" + arm,
        dict(
            status="passed",
            endpoint_G_pJ=target,
            directional_power_pJ_s=float(power),
            directional_errors=errors,
            **checked,
        ),
    )


def test_sealed_water_reduces_bitwise_to_parent_without_volume_resets():
    spec, state, p, control = initial(fixtures.definition("sealed"))
    old, q = prior.initial_values(prior_spec(spec))
    expected = prior.readouts(old, model.base_control(control), q, xp=np)
    actual = model.readouts(state, control, p, xp=np)
    exact(model.prior_state(state), old)
    exact(model.prior_state(actual.derivative), expected.derivative)
    exact(jax.tree.leaves(actual.field), jax.tree.leaves(expected.field))
    assert all(not np.any(getattr(actual.derivative, k)) for k in model.EXTRA_AXES)


def test_batched_ip3_and_observations_use_current_cytosol_outside_volumes():
    spec, state, p, control = initial()
    state = moved(state)
    other = type(state)(*(v.copy() for v in state))
    other.volume_increment_pL[0] *= -1
    other.extracellular_volume_increment_pL[0] *= -1
    other.water_transferred_pL[0] *= -1
    batch = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, other, strict=True)))
    concentration, fraction = model.ip3_readouts(batch, p, xp=np)
    for i, row in enumerate((state, other)):
        value = model.readouts(row, control, p, xp=np)
        np.testing.assert_allclose(
            concentration[i], value.calcium.ip3_cytosol_mM, atol=1e-19, rtol=3e-15
        )
        np.testing.assert_allclose(
            fraction[i], value.calcium.ip3_release_fraction, atol=1e-19, rtol=3e-15
        )
        np.testing.assert_allclose(
            model.ensemble_voltage(row, p, spec, 0.0),
            value.field.rates.membrane_voltage_V[: len(spec.model.membranes)],
            atol=3e-14,
            rtol=3e-10,
        )
    obs = model.observe_history(
        np.array([0.0]), model.STATE_TYPE(*(v[None] for v in state)), p, np.array([0.0]), spec
    )
    inside, outside = model.physical_amounts(state, p)
    np.testing.assert_array_equal(
        obs.cell_concentration_mM[0], inside / (p.volume + state.volume_increment_pL)
    )
    np.testing.assert_array_equal(
        obs.extracellular_concentration_mM[0],
        outside / (p.extracellular_volume + state.extracellular_volume_increment_pL),
    )
    np.testing.assert_array_equal(
        obs.membrane_voltage_V[0],
        model.readouts(state, control, p, xp=np).field.rates.membrane_voltage_V,
    )


@pytest.mark.parametrize(
    "fault",
    [
        "coupling",
        "er_owner",
        "cytosol_volume",
        "missing_owner",
        "bad_level",
        "nonfinite",
        "open_source",
    ],
)
def test_explicit_schema_rejects_incompatible_ownership(fault):
    raw = fixtures.definition()
    if fault == "coupling":
        raw["model"]["chemical_osmotic_coupling"] = "ionic_only@1"
    elif fault == "er_owner":
        raw["model"]["water_compartments"][0]["compartment_id"] = "er"
    elif fault == "cytosol_volume":
        raw["model"]["stores"][0]["model"]["compartments"][0]["volume_pL"] *= 1.1
    elif fault == "missing_owner":
        raw["model"]["water_compartments"].pop()
    elif fault == "bad_level":
        raw["experiment"]["water_controls"][0]["schedule"][0]["availability"] = 1.1
    elif fault == "nonfinite":
        raw["model"]["water_compartments"][0]["impermeant_amount_fmol"] = np.nan
    else:
        raw["model"]["ip3_source_fmol_per_s"] = 1.0
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize(
    "fault",
    [
        "minimum",
        "maximum",
        "pad_volume",
        "pad_flow",
        "negative_heat",
        "nan_control",
        "pad_control",
        "absent_gate",
    ],
)
def test_invalid_trial_volume_padding_and_controls_reject(fault):
    spec, state, p, control = initial()
    if fault in ("minimum", "maximum"):
        target = (
            p.water_minimum_volume_pL[0] if fault == "minimum" else p.water_maximum_volume_pL[0]
        )
        state.volume_increment_pL[0] = target - p.volume[0]
    elif fault == "pad_volume":
        state.volume_increment_pL[-1] = 0.1
    elif fault == "pad_flow":
        state.water_transferred_pL[-1] = 0.1
    elif fault == "negative_heat":
        state.water_dissipated_energy_pJ[0] = -1.0
    elif fault == "absent_gate":
        state.channel_gate[1, np.flatnonzero(p.channel_laws == 40)[0]] = 1e-8
    else:
        control.water[-1 if fault == "pad_control" else 0] = (
            np.nan if fault == "nan_control" else 0.1
        )
    assert not model.control_domain_valid(state, control, p, p.active, xp=np)
    if fault not in ("nan_control", "pad_control"):
        with pytest.raises(NumericalError):
            model.check_values(state, spec)


@pytest.mark.parametrize("fault", ["chemical", "water"])
def test_minimum_volume_and_water_rate_guards(fault):
    raw = fixtures.definition()
    if fault == "chemical":
        for row in raw["model"]["water_compartments"]:
            row["minimum_volume_pL"] = 1e-8
    else:
        for row in raw["model"]["water_membranes"]:
            row["hydraulic_permeability_m_per_Pa_s"] *= 1e8
    with pytest.raises(ConfigError, match="minimum-volume|relaxation"):
        timeline(parse_spec(raw))


def test_initial_ordinary_complete_artifacts(tmp_path):
    spec, state, p, _ = initial()
    history = model.STATE_TYPE(*(v[None] for v in state))
    point = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    times = np.array([0.0])
    result = RunResult(
        spec,
        point,
        0,
        times,
        history,
        model.observe_history(times, history, p, times, spec),
        {},
        model.check_values(history, spec),
    )
    summary = write_run(tmp_path / "initial", result)
    restored = load_snapshot(tmp_path / "initial/checkpoint_final")
    assert restored.spec == spec and summary["model"] == fixtures.MODEL_ID
    exact(restored.checkpoint.state, state)
    exact(restored.checkpoint.layout, p)
    raw = json.loads((ROOT / "configs/assembly_calcium_water.json").read_text())
    assert raw == fixtures.assembly_definition()
    evidence(
        "calcium-water-initial-artifacts",
        dict(
            status="passed",
            summary=summary,
            scope="Initial ordinary artifacts; Chief owns assembly checkpoint/report validation",
        ),
    )


def test_short_numpy_coupled_trajectory_and_reference():
    raw = fixtures.compact_probe()
    dt = raw["execution"]["dt"]
    raw["experiment"].update(
        end_time=16 * dt, observation_times=[i * dt for i in (0, 4, 8, 10, 16)]
    )
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [c for c in row[key] if c["time"] <= raw["experiment"]["end_time"]]
    spec, state, p, _ = initial(raw)
    independent = reference.integrate(raw)
    c = reference.bind(raw)
    times, records = timeline(spec), [state]
    for left, right in zip(times[:-1], times[1:], strict=True):
        u = control_values(spec, [left])
        control = type(u)(*(v[0] for v in u))
        state = rk4_step(
            lambda y, held=control: model.rhs(y, held, p, p.active, xp=np), state, right - left
        )
        assert model.control_domain_valid(state, control, p, p.active, xp=np)
        records.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*records, strict=True)))
    diagnostics = model.check_values(history, spec)
    ratios = []
    for i, time in enumerate(independent["times"]):
        index = int(np.flatnonzero(times == time)[0])
        actual = model.STATE_TYPE(*(v[index] for v in history))
        ratios.append(
            assert_states(
                c,
                reference.flatten(c, actual._asdict()),
                independent["state"][i],
                atol=2e-11,
                charge_atol=3e-24,
                rtol=3e-8,
            )
        )
    evidence(
        "calcium-water-short-trajectory",
        dict(
            status="passed",
            inputs=raw,
            max_error_over_budget=max(ratios),
            diagnostics=diagnostics,
            reference_evaluations=independent["evaluations"],
            scope="20-us coupled development; physical water relaxation is separately checked",
        ),
    )


def test_separate_physical_water_relaxation_for_twelve_time_constants():
    spec, state, p, _ = initial(fixtures.definition(padded=False))
    c = reference.bind(spec.to_dict())
    nodes = [0, len(spec.model.cells)]
    case = deepcopy(c["water_case"])
    for key in (
        "initial_volume_pL",
        "reference_volume_pL",
        "impermeant_amount_fmol",
        "bulk_modulus_Pa",
        "pressure_offset_Pa",
    ):
        case[key] = np.asarray(case[key])[nodes]
    case["amount_fmol"] = reference.particles(c, reference.unpack(c, reference.initial(c)))[
        :, nodes
    ]
    case["edges"] = [dict(case["edges"][0], sender=0, receiver=1)]
    equilibrium = water_reference.two_compartment_equilibrium(case)
    n = case["amount_fmol"].sum(axis=0) + case["impermeant_amount_fmol"]
    stiffness = (
        case["bulk_modulus_Pa"] / case["reference_volume_pL"]
        + water.R * p.temperature * n / equilibrium**2
    )
    conductance = (
        1e15 * case["edges"][0]["area_m2"] * case["edges"][0]["hydraulic_permeability_m_per_Pa_s"]
    )
    tau = 1 / (conductance * stiffness.sum())
    times = np.linspace(0, 12 * tau, 65)
    independent = water_reference.integrate(case, times)
    np.testing.assert_allclose(independent["volume_pL"][-1], equilibrium, atol=5e-6, rtol=0)
    np.testing.assert_allclose(
        independent["volume_pL"].sum(axis=1), sum(case["initial_volume_pL"]), atol=2e-14, rtol=0
    )
    # Established production water kernel, with the actual chemical particles
    # frozen. This checks the physical solvent clock, not a full chemical run.
    q = water.Parameters(
        p.temperature,
        np.ones(2, bool),
        case["reference_volume_pL"],
        p.water_minimum_volume_pL[nodes],
        p.water_maximum_volume_pL[nodes],
        case["impermeant_amount_fmol"],
        case["bulk_modulus_Pa"],
        case["pressure_offset_Pa"],
        np.ones(1, bool),
        np.array([0]),
        np.array([1]),
        np.array([conductance]),
    )
    values = np.r_[case["initial_volume_pL"], 0.0, 0.0]
    records = [values.copy()]
    step = times[1] / 8
    for _ in range(64):
        for _ in range(8):

            def slope(y):
                w = water.evaluate(y[:2], case["amount_fmol"], np.ones(1), q, xp=np)
                return np.r_[w.volume_rate_pL_s, w.edge_flow_pL_s, w.edge_dissipation_pJ_s]

            values = rk4_step(slope, values, step)
        records.append(values.copy())
    actual = np.array(records)
    assert np.all(actual[:, :2] > q.minimum_volume_pL)
    assert np.all(actual[:, :2] < q.maximum_volume_pL)
    np.testing.assert_allclose(actual[:, :2], independent["volume_pL"], atol=3e-8, rtol=3e-8)
    np.testing.assert_allclose(
        actual[:, 3:], independent["edge_dissipated_energy_pJ"], atol=3e-6, rtol=3e-7
    )
    assert np.all(np.diff(actual[:, 3]) >= -1e-12)
    energy = np.array(
        [
            water.evaluate(row[:2], case["amount_fmol"], np.ones(1), q, xp=np).free_energy_pJ
            for row in actual
        ]
    )
    assert np.max(np.abs(energy - energy[0] + actual[:, 3])) < 3e-6
    evidence(
        "calcium-water-physical-relaxation",
        dict(
            status="passed",
            inputs={
                key: value.tolist() if isinstance(value, np.ndarray) else value
                for key, value in case.items()
            },
            tau_s=float(tau),
            horizon_s=float(times[-1]),
            tau_multiples=12,
            equilibrium_volume_pL=equilibrium.tolist(),
            times_s=times.tolist(),
            numerical=actual.tolist(),
            reference_volume_pL=independent["volume_pL"].tolist(),
            energy_residual_pJ=(energy - energy[0] + actual[:, 3]).tolist(),
            scope=(
                "Isolated actual chemical-particle water pair, fixed solutes/ER; "
                "no full-model equilibration claim"
            ),
        ),
    )
