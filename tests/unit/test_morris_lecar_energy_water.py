"""Full-catalog finite fuel, live dilution, conservative ledgers and CPU execution."""

from copy import deepcopy

import jax
import numpy as np
import pytest

from cells.core.runner import run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_energy_spec import initial_ionic_spec
from cells.core.surface_energy_water_spec import energy_spec
from cells.ensemble import ionic
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_energy as old_energy
from cells.models import surface_energy_morris_lecar as energy
from cells.models import surface_energy_water as old_water
from cells.models import surface_energy_water_morris_lecar as water
from cells.models.registry import get_model
from cells.processes import morris_lecar_catalog as catalog
from cells.processes.electrochemistry import R
from tests.unit.test_surface_energy_water import evidence
from tests.unit.test_surface_kinetic import exact
from tests.unit.test_surface_water_kinetic import error_budget
from validation.chemistry import finite_energy_reference as pool_reference
from validation.tissue import morris_lecar_energy_water_fixtures as fixtures
from validation.tissue import surface_energy_fixtures as old_energy_fixtures
from validation.tissue import surface_energy_reference as energy_reference
from validation.tissue import surface_energy_water_fixtures as old_water_fixtures
from validation.tissue import surface_energy_water_reference as water_reference

MODELS = dict(energy=energy, water=water)
REFERENCES = dict(energy=energy_reference, water=water_reference)


def initial(kind="water", raw=None, time=0.0):
    spec = parse_spec(fixtures.definition(kind) if raw is None else raw)
    state, p = MODELS[kind].initial_values(spec)
    controls = control_values(spec, [time])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def changed_state(kind, state, p, *, move_water=True):
    y = type(state)(*(v.copy() for v in state))
    delta = 0.1 * p.energy_initial_amount_fmol[0, 0]
    y.energy_amount_increment_fmol[:, 0] = [-delta, delta, delta]
    if kind == "water" and move_water:
        patch = int(np.flatnonzero(p.membrane_active)[0])
        a, b = int(p.membrane_cell[patch]), int(p.membrane_outside[patch])
        y.volume_increment_pL[a] += 0.08
        y.extracellular_volume_increment_pL[b] -= 0.08
        y.water_transferred_pL[patch] -= 0.08
    return y


def compare(kind, spec, state, derivative, time=0.0):
    reference = REFERENCES[kind]
    c = reference.bind(spec.to_dict())
    target, _, proof = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    ratio = error_budget(
        c,
        reference.flatten(c, derivative._asdict()),
        target,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    return dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("kind", fixtures.KINDS)
@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_registered_complete_state_and_lossless_projection(kind, backend, padded):
    spec, state, p, _ = initial(kind, fixtures.definition(kind, backend=backend, padded=padded))
    model = MODELS[kind]
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert len(state) == dict(energy=23, water=28)[kind] and len(spec.model.channels) == 60
    assert set(p.channel_laws[p.channel_active]) == set(range(53))
    assert spec == parse_spec(spec.to_dict())
    finite = energy_spec(spec) if kind == "water" else spec
    assert finite.to_dict()["model"]["id"] == fixtures.MODEL_IDS["energy"]
    assert initial_ionic_spec(finite).to_dict()["model"]["id"] == "resolved_tissue@11"
    assert (
        ionic.parse_spec(
            dict(model="ionic_worlds@1", simulation=spec.to_dict(), worlds=2)
        ).simulation
        == spec
    )
    timeline(spec)
    model.check_values(state, spec)


@pytest.mark.parametrize("kind", fixtures.KINDS)
@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_stages_with_changed_fuel_and_volume(kind, arm, padded):
    time = 36e-6 if arm == "release" else 0.0
    spec, state, p, control = initial(kind, fixtures.definition(kind, arm, padded=padded), time)
    state = changed_state(kind, state, p, move_water=arm != "sealed")
    before = tuple(v.copy() for v in state)
    value = MODELS[kind].readouts(state, control, p, xp=np)
    assert value.valid
    checked = compare(kind, spec, state, value.derivative, time)
    exact(state, before)
    absent = ~(catalog.gate_active(p.channel_laws, xp=np) & p.channel_active)
    assert np.all(value.derivative.channel_gate[absent] == 0)
    if arm in ("blocked", "empty"):
        assert not np.any(value.derivative.channel_transferred)
    if arm == "supply_off":
        assert not np.any(value.derivative.regeneration_cycles_fmol)
    if arm == "inhibited":
        assert not np.any(value.derivative.pump_cycles)
    if kind == "water":
        assert (
            abs(
                sum(value.derivative.volume_increment_pL)
                + sum(value.derivative.extracellular_volume_increment_pL)
            )
            < 3e-13
        )
        if arm == "sealed":
            assert not np.any(value.water.edge_flow_pL_s)
    if padded:
        assert not np.any(value.derivative.channel_transferred[:, -1])
        assert not np.any(value.derivative.energy_amount_increment_fmol[:, -1])
        assert value.derivative.regeneration_cycles_fmol[-1] == 0
    evidence(
        f"morris-lecar-stage-{kind}-{arm}-{padded}",
        dict(
            status="passed", inputs=spec.to_dict(), scope="complete instantaneous stage", **checked
        ),
    )


@pytest.mark.parametrize("kind", fixtures.KINDS)
@pytest.mark.parametrize("nonzero", [False, True])
def test_previous_versions_stay_bitwise_identical(kind, nonzero):
    source = dict(energy=old_energy_fixtures, water=old_water_fixtures)[kind]
    previous = dict(energy=old_energy, water=old_water)[kind]
    for arm in source.ARMS:
        raw = source.definition(arm)
        old, state, p, control = initial(kind, raw)
        raw["model"]["id"] = fixtures.MODEL_IDS[kind]
        spec, newer, q, other = initial(kind, raw)
        if nonzero:
            state = changed_state(kind, state, p)
            newer = changed_state(kind, newer, q)
        exact(state, newer)
        a = previous.readouts(state, control, p, xp=np)
        b = MODELS[kind].readouts(newer, other, q, xp=np)
        exact(jax.tree.leaves(a), jax.tree.leaves(b))
        assert old.to_dict()["model"]["id"].endswith("@1")
        assert spec.to_dict()["model"]["id"] == fixtures.MODEL_IDS[kind]


def test_sealed_water_reduces_exactly_to_full_catalog_finite_fuel():
    spec, state, p, u = initial("water", fixtures.definition("water", "sealed"))
    finite = energy_spec(spec)
    y, q = energy.initial_values(finite)
    controls = control_values(finite, [0.0])
    expected = energy.readouts(y, type(controls)(*(v[0] for v in controls)), q, xp=np)
    actual = water.readouts(state, u, p, xp=np)
    exact(water.energy_state(actual.derivative), expected.derivative)
    assert all(not np.any(getattr(actual.derivative, name)) for name in water.EXTRA_AXES)


def test_live_pool_particles_dilute_without_duplicate_energy_or_ionic_charge():
    spec, y, p, u = initial()
    changed = changed_state("water", y, p)
    value = water.readouts(changed, u, p, xp=np)
    np.testing.assert_allclose(
        value.energy.energy.concentration_mM[:, p.active],
        energy.energy_amounts(changed, p)[:, p.active]
        / (p.volume + changed.volume_increment_pL)[p.active],
        rtol=2e-15,
        atol=0,
    )
    fuel_only = changed_state("water", y, p, move_water=False)
    before = water.water_values(y, u, p, xp=np)
    after = water.water_values(fuel_only, u, p, xp=np)
    delta = 0.1 * p.energy_initial_amount_fmol[0, 0]
    np.testing.assert_allclose(
        after.osmotic_pressure_Pa[0] - before.osmotic_pressure_Pa[0],
        R * p.temperature * delta / p.volume[0],
        rtol=1e-8,
    )
    exact(water.physical_amounts(fuel_only, p), water.physical_amounts(y, p))
    target = pool_reference.free_energy_change(
        p.energy_initial_amount_fmol[:, 0],
        energy.energy_amounts(changed, p)[:, 0],
        float(p.volume[0]),
        float(p.volume[0] + changed.volume_increment_pL[0]),
        float(p.temperature),
        float(p.energy_delta_g0_J_mol[0]),
    )
    np.testing.assert_allclose(
        water.pool_free_energy_change_pJ(changed, p)[0], target, atol=3e-15, rtol=3e-10
    )
    original = water.balances(changed, p)
    changed.pool_volume_work_pJ[0] -= 0.001
    other = water.balances(changed, p)
    assert other["energy"] == original["energy"]
    np.testing.assert_allclose(other["pool_energy"][0] - original["pool_energy"][0], 0.001)
    assert value.valid and abs(value.field.energy_balance_pJ_s) < 1e-9


@pytest.mark.parametrize("kind", fixtures.KINDS)
@pytest.mark.parametrize(
    "fault", ["old_identity", "gate_count", "pool_owner", "temperature", "gate_step", "fuel_step"]
)
def test_strict_catalog_ownership_and_independent_step_guards(kind, fault):
    raw = fixtures.definition(kind)
    m = raw["model"]
    if fault == "old_identity":
        m["id"] = m["id"].replace("@2", "@1")
    elif fault == "gate_count":
        m["channels"][-1]["initial_gate"] = [0.0]
    elif fault == "pool_owner":
        m["membranes"][0]["pump"]["metabolism"]["pool_id"] = m["energy_pools"][1]["id"]
    elif fault == "temperature":
        m["temperature_K"] = 300.0
    elif fault == "gate_step":
        raw["execution"]["dt"] = 2.5e-6
    else:
        m["regeneration_ports"][0]["capacity_fmol_per_s"] = 1e6
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("kind", fixtures.KINDS)
@pytest.mark.parametrize("arm", ["instant_only", "dynamic_only"])
def test_only_real_gates_restrict_the_clock(kind, arm):
    raw = fixtures.definition(kind, arm)
    raw["execution"]["dt"] = 2.5e-6
    timeline(parse_spec(raw))
    if kind == "water":
        raw["execution"]["dt"] = 25e-6
        # This tiny-pool fixture reaches its fuel turnover ceiling first.
        # Isolate the hydraulic guard with explicitly zero fuel-route capacities.
        with pytest.raises(ConfigError, match="gross turnover"):
            timeline(parse_spec(raw))
        for patch in raw["model"]["membranes"]:
            if patch["pump"] is not None:
                patch["pump"]["capacity_fmol_per_s"] = 0.0
        for port in raw["model"]["regeneration_ports"]:
            port["capacity_fmol_per_s"] = 0.0
        spec = parse_spec(raw)
        timeline(energy_spec(spec))
        with pytest.raises(ConfigError, match="water relaxation"):
            timeline(spec)


@pytest.mark.parametrize("kind", fixtures.KINDS)
@pytest.mark.parametrize(
    "fault", ["instant_gate", "absent_h", "padded_gate", "depleted_atp", "padded_regeneration"]
)
def test_blocked_populations_cannot_hide_invalid_state(kind, fault):
    _, y, p, u = initial(kind, fixtures.definition(kind, "blocked"))
    if fault == "instant_gate":
        y.channel_gate[0, np.flatnonzero(p.channel_laws == 46)[0]] = 0.25
    elif fault == "absent_h":
        y.channel_gate[1, np.flatnonzero(p.channel_laws == 40)[0]] = 0.25
    elif fault == "padded_gate":
        y.channel_gate[0, -1] = 0.25
    elif fault == "depleted_atp":
        y.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    else:
        u.regeneration[-1] = 0.1
    assert not MODELS[kind].control_domain_valid(y, u, p, p.active, xp=np)


def test_permanently_absent_water_route_rejects_accumulated_history():
    _, y, p, u = initial("water", fixtures.definition("water", "sealed"))
    y = changed_state("water", y, p)
    assert not water.control_domain_valid(y, u, p, p.active, xp=np)


@pytest.mark.parametrize("kind", fixtures.KINDS)
def test_complete_initial_snapshot(kind, tmp_path):
    from cells.core.state import Checkpoint

    spec, y, p, _ = initial(kind, fixtures.compact_probe(kind))
    write_snapshot(tmp_path / "initial", spec, Checkpoint(y, p, 0.0, 0, 0))
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is MODELS[kind].LAYOUT_TYPE
    exact(saved.checkpoint.state, y)
    exact(saved.checkpoint.layout, p)


@pytest.mark.parametrize("kind", ["energy", "water", "maintained_water"])
def test_projection_retains_supply_and_water_only_off_grid_boundaries(kind):
    from validation.tissue import morris_lecar_water_fixtures

    raw = (
        morris_lecar_water_fixtures.compact_probe()
        if kind == "maintained_water"
        else fixtures.compact_probe(kind)
    )
    families = ("water",) if kind == "maintained_water" else ("regeneration",)
    if kind == "water":
        families += ("water",)
    events = []
    for i, family in enumerate(families):
        time = (10.3 + i) * raw["execution"]["dt"]
        group = raw["experiment"][family + "_controls"][0]
        group["schedule"].append(dict(time=time, availability=0.35 + 0.1 * i))
        group["schedule"].sort(key=lambda row: row["time"])
        events.append(time)
    raw["experiment"]["observation_times"] = sorted(
        set(raw["experiment"]["observation_times"]) | set(events)
    )
    spec = parse_spec(raw)
    times = timeline(spec)
    assert all(time in times for time in events)
    table = control_values(spec, events)
    for i, family in enumerate(families):
        assert getattr(table, family)[i, 0] == 0.35 + 0.1 * i
    evidence(
        "morris-lecar-off-grid-" + kind,
        dict(
            status="passed",
            inputs=raw,
            retained_events=events,
            scope="Projection retains the full experiment clock and right-continuous controls",
        ),
    )


@pytest.mark.parametrize("kind", fixtures.KINDS)
def test_compiled_two_world_stage_and_isolated_failure(kind):
    model = MODELS[kind]
    spec, y, p, u = initial(kind)
    changed = changed_state(kind, y, p)
    changed.channel_gate[0, p.channel_laws == 40] = 0.51
    states = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(y, changed, strict=True)))
    controls = type(u)(*(np.stack((v, v)) for v in u))
    evaluate = jax.jit(
        jax.vmap(
            lambda state, control, q: (
                model.rhs(state, control, q, q.active),
                model.control_domain_valid(state, control, q, q.active),
            ),
            in_axes=(0, 0, None),
        )
    )
    rates, valid = evaluate(states, controls, p)
    assert np.all(valid)
    checked = []
    for i in (0, 1):
        checked.append(
            compare(
                kind,
                spec,
                model.STATE_TYPE(*(v[i] for v in states)),
                model.STATE_TYPE(*(v[i] for v in rates)),
            )
        )
    bad = states._replace(channel_gate=states.channel_gate.copy())
    bad.channel_gate[1, 0, np.flatnonzero(p.channel_laws == 46)[0]] = 0.25
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in rates))
    evidence(
        f"morris-lecar-compiled-stage-{kind}",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            world_checks=checked,
            invalid_world_isolated=True,
        ),
    )


def test_compiled_early_water_trajectory_and_complete_final_snapshot(tmp_path):
    raw = fixtures.compact_probe()
    result = run(parse_spec(raw))
    c = water_reference.bind(raw)
    expected = water_reference.integrate(raw)
    actual = water_reference.flatten(c, vars(result.observations))
    target = np.asarray(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        diagnostics=result.diagnostics,
        scope="50-us full28 coupling; channel/fuel/water/pump events; no full settling",
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
    )
    evidence(
        "morris-lecar-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    ratio = error_budget(c, actual, target)
    p = result.final.layout
    absent = ~(catalog.gate_active(p.channel_laws, xp=np) & p.channel_active)
    assert np.all(result.observations.channel_gate[:, absent] == 0)
    assert np.max(np.abs(result.observations.volume_increment_pL)) > 1e-4
    assert np.max(np.abs(result.observations.energy_amount_increment_fmol)) > 1e-7
    write_run(tmp_path / "coupled", result)
    saved = load_snapshot(tmp_path / "coupled/checkpoint_final")
    assert saved.spec == result.spec and type(saved.checkpoint.layout) is water.LAYOUT_TYPE
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    evidence(
        "morris-lecar-trajectory",
        report
        | dict(
            status="passed",
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
            absent_gate_slots_exact_zero=True,
        ),
    )


def test_offline_one_four_sixteen_gpu_planning_preserves_worlds():
    from cells.ensemble.families import parse_definition, population
    from tests.unit.test_integrated_ensemble import experiment
    from tests.unit.test_morris_lecar_catalog_planning import verify

    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    template = deepcopy(raw["arms"][0])
    raw["arms"] = []
    for kind in fixtures.KINDS:
        arm = deepcopy(template)
        arm.update(id=kind, seconds_per_world=None)
        arm["definition"]["simulation"] = fixtures.definition(kind, backend="gpu")
        arm["definition"]["window_steps"] = 256
        raw["arms"].append(arm)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    plans = verify(raw)
    ids, counts = [], dict(energy=0, water=0)
    for task in plans["local"]["tasks"]:
        spec = parse_definition(task["definition"])
        group = population(spec)
        assert spec.simulation.to_dict()["model"]["id"] == fixtures.MODEL_IDS[task["arm"]]
        assert group.seed == raw["seed"]
        counts[task["arm"]] += group.worlds
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(ids) == list(range(16)) and set(counts.values()) == {8}
    evidence(
        "morris-lecar-planning",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            world_ids=sorted(ids),
            arm_worlds=counts,
            scope="Offline 1/4/16-GPU placement; runtime balance and device execution unqualified",
        ),
    )
