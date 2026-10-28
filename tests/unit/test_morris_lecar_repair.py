"""39-field repair contracts; coupled stages and separate long scalar clocks."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.controls import modulate
from cells.assembly_cluster.spec import channel_owners
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.runner import RunResult, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.surface_repair_spec import base_spec
from cells.ensemble import ionic
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_morris_lecar as prior
from cells.models import surface_kinetic
from cells.models import surface_repair as original
from cells.models import surface_repair_morris_lecar as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from cells.processes import membrane_injury
from cells.processes import morris_lecar_catalog as catalog
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import morris_lecar_repair_fixtures as fixtures
from validation.tissue import morris_lecar_repair_reference as reference
from validation.tissue import surface_mobile_pump_repair_fixtures as pump_fixtures
from validation.tissue import surface_mobile_pump_repair_reference as pump_reference
from validation.tissue import surface_mobile_repair_fixtures as mobile_fixtures
from validation.tissue import surface_mobile_repair_reference as mobile_reference
from validation.tissue import surface_repair_fixtures as old_fixtures
from validation.tissue import surface_repair_reference as old_reference


def initial(raw=None, time=0.0):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = get_model(spec.model).initial_values(spec)
    table = control_values(spec, [time])
    return spec, state, p, type(table)(*(v[0] for v in table))


def compare(spec, state, derivative, time=0.0, levels=None, ref=reference):
    c = ref.bind(spec.to_dict())
    target, phi, proof = ref.evaluate(
        c, ref.flatten(c, state._asdict()), time, channel_levels=levels
    )
    ratio = assert_states(
        c, ref.flatten(c, derivative._asdict()), target, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-9
    return phi, dict(max_error_over_budget=ratio, independent_stage=proof)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_registered_complete_state_projection_and_roundtrip(backend, padded):
    raw = fixtures.definition(backend=backend, padded=padded)
    if backend == "cpu" and padded:
        stored = json.loads(
            (Path(__file__).parents[2] / "configs/resolved_morris_lecar_repair.json").read_text()
        )
        assert stored == raw
        raw = stored
    spec, state, p, _ = initial(raw)
    assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
    assert len(state) == 39 and len(spec.model.channels) == 60
    assert set(p.channel_laws[p.channel_active]) == set(range(53))
    assert spec == parse_spec(spec.to_dict())
    parent = base_spec(spec)
    assert parent.to_dict()["model"]["id"] == "resolved_calcium@10"
    assert parent.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@11"
    assert type(model.base_layout(p)) is prior.LAYOUT_TYPE
    view = prior.ionic_layout(model.base_state(state), model.base_layout(p), xp=np)
    assert surface_kinetic.channel_process(view) is catalog
    assert (
        ionic.parse_spec(
            dict(model="ionic_worlds@1", simulation=spec.to_dict(), worlds=2)
        ).simulation
        == spec
    )
    batch = BatchSpec((WorldSpec(7, spec), WorldSpec(31, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    assert 5.3e-6 in timeline(spec) and 15.3e-6 in timeline(spec)
    model.check_values(state, spec)
    evidence(
        f"morris-lecar-repair-identity-{backend}-{padded}",
        dict(status="passed", inputs=spec.to_dict(), state_fields=list(state._fields)),
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_full_independent_stage_injury_conservation_and_field(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    if arm in ("held", "resealing"):
        raw["model"]["injury_patches"][0]["initial_damage"] = 0.3
    spec, state, p, control = initial(raw, time=5.3e-6)
    before = tuple(v.copy() for v in state)
    value = model.readouts(state, control, p, xp=np)
    phi, checked = compare(spec, state, value.derivative, 5.3e-6)
    assert value.valid and model.control_domain_valid(state, control, p, p.active, xp=np)
    exact(state, before)
    np.testing.assert_allclose(
        np.r_[
            value.field.potential_V[:2], value.field.potential_V[p.active.size : p.active.size + 5]
        ],
        phi,
        rtol=3e-10,
        atol=3e-13,
    )
    assert abs(value.field.energy_balance_pJ_s) < 1e-9
    parent = prior.readouts(
        model.base_state(state), model.base_control(control), model.base_layout(p), xp=np
    )
    d, old = value.derivative, parent.derivative
    flux = d.injury_transferred
    ids = spec.model.species_ids
    assert not np.any(flux[[ids.index("Ca"), ids.index("Cl")]])
    assert np.count_nonzero(flux) == (2 if arm in ("held", "resealing") else 0)
    assert np.all(d.injury_dissipated_energy_pJ >= 0)
    delta = d.chemical_amount_increment - old.chemical_amount_increment
    np.testing.assert_allclose(
        np.sum(delta, axis=(0, 2))[p.ionic_species], -np.sum(flux, axis=1), atol=1e-12
    )
    np.testing.assert_allclose(
        np.sum(d.amount_increment - old.amount_increment, axis=1)
        + np.sum(d.extracellular_amount_increment - old.extracellular_amount_increment, axis=1),
        0,
        atol=1e-12,
    )
    assert not np.any(delta[1])
    exact(d.channel_gate, old.channel_gate)
    exact(d.calcium_gate, old.calcium_gate)
    evidence(
        f"morris-lecar-repair-stage-{arm}-{padded}", dict(status="passed", inputs=raw, **checked)
    )


@pytest.mark.parametrize("channels", fixtures.CHANNEL_ARMS)
def test_zero_one_two_gate_populations_and_lesion_survive_channel_controls(channels):
    raw = fixtures.definition(channels=channels)
    raw["model"]["injury_patches"][0]["initial_damage"] = 0.3
    spec, state, p, control = initial(raw, time=5.3e-6)
    value = model.readouts(state, control, p, xp=np)
    assert value.valid
    _, checked = compare(spec, state, value.derivative, 5.3e-6)
    active = catalog.gate_active(p.channel_laws, xp=np) & p.channel_active[None, :]
    assert np.all(state.channel_gate[~active] == 0)
    assert np.all(value.derivative.channel_gate[~active] == 0)
    if channels == "instant_only":
        assert not np.any(active)
    if channels == "dynamic_only":
        assert np.count_nonzero(active) == 5
    if channels == "empty":
        assert len(spec.model.channels) == 0 and not np.any(value.derivative.channel_transferred)
    # Ordinary membrane/channel inhibition must not erase an already open lesion.
    blocked = model.readouts(
        state,
        control._replace(
            membrane=np.zeros_like(control.membrane), channel=np.zeros_like(control.channel)
        ),
        p,
        xp=np,
    )
    assert blocked.valid and np.count_nonzero(blocked.derivative.injury_transferred) == 2
    np.testing.assert_array_equal(
        blocked.derivative.injury_transferred, value.derivative.injury_transferred
    )
    evidence("morris-lecar-repair-channels-" + channels, dict(status="passed", **checked))


def test_sham_bitwise_parent_and_injury_onset_preserve_all_inventories():
    spec, state, p, control = initial(fixtures.definition("sham"), time=5.3e-6)
    old, q = prior.initial_values(base_spec(spec))
    before = prior.readouts(old, model.base_control(control), q, xp=np)
    after = model.readouts(state, control, p, xp=np)
    exact(model.base_state(state), old)
    exact(model.base_state(after.derivative), before.derivative)
    exact(jax.tree.leaves(after.field), jax.tree.leaves(before.field))
    assert all(not np.any(getattr(after.derivative, k)) for k in model.EXTRA_AXES)
    injury = np.zeros_like(control.injury)
    injury[0] = 1.0
    changed = model.readouts(state, control._replace(injury=injury), p, xp=np)
    exact(model.base_state(changed.derivative), before.derivative)
    assert changed.derivative.damage[0] == 20000 and not np.any(state.damage)
    evidence(
        "morris-lecar-repair-sham",
        dict(status="passed", parent_rates_and_field="bitwise", reset=False),
    )


def test_free_calcium_sensor_uses_owned_pool_in_repair_layout():
    raw = fixtures.definition()
    raw["model"]["injury_patches"][0]["initial_damage"] = 0.3
    spec, state, p, control = initial(raw)
    changed = type(state)(*(v.copy() for v in state))
    names = [s.id for s in spec.model.stores[0].species]
    ids = [names.index(k) for k in ("Ca", "B", "CaB")]
    changed.chemical_amount_increment[0, ids, int(p.er_cytosol[0])] += 1e-4 * np.array([-1, -1, 1])
    before = model.readouts(state, control, p, xp=np)
    after = model.readouts(changed, control, p, xp=np)
    assert after.valid
    _, checked = compare(spec, changed, after.derivative)
    sensor = np.isin(p.channel_laws, [35, 36, 37, 38, 39]) & p.channel_active
    assert np.any(
        before.derivative.channel_transferred[:, sensor]
        != after.derivative.channel_transferred[:, sensor]
    )
    evidence("morris-lecar-repair-free-calcium", dict(status="passed", **checked))


@pytest.mark.parametrize("damage", [0.0, 0.25, 1.0])
def test_separate_twelve_tau_injury_and_resealing_clocks(damage):
    a, b = 20000.0, 4000.0
    opening_time, closing_time = 12 / (a + b), 12 / b
    opened_exact = np.array(reference.clock(damage, a, b, opening_time))
    closed_exact = np.array(reference.clock(opened_exact[0], 0, b, closing_time))
    closed_exact[1:] += opened_exact[1:]
    errors, traces = [], {}
    for count in (32, 64, 128):
        state = np.array([damage, 0.0, 0.0])
        records, targets, times = [state.copy()], [state.copy()], [0.0]
        for phase, (hazard, duration) in enumerate(((a, opening_time), (0.0, closing_time))):
            initial_exact = np.array([damage, 0.0, 0.0]) if phase == 0 else opened_exact
            for index in range(1, count + 1):
                state = rk4_step(
                    lambda y, h=hazard: np.array(
                        membrane_injury.rates(y[0], h, b, 1.0, 1.0, xp=np)
                    ),
                    state,
                    duration / count,
                )
                target = np.array(
                    reference.clock(initial_exact[0], hazard, b, index * duration / count)
                )
                target[1:] += initial_exact[1:]
                records.append(state.copy())
                targets.append(target)
                times.append((opening_time if phase else 0.0) + index * duration / count)
        values, exact_values = np.array(records), np.array(targets)
        assert np.all((values[:, 0] >= 0) & (values[:, 0] <= 1))
        assert np.all(np.diff(values[:, 1:], axis=0) >= -1e-14)
        assert np.max(np.abs(values[:, 0] - damage - values[:, 1] + values[:, 2])) < 1e-13
        errors.append(float(np.max(np.abs(values - exact_values))))
        traces[str(count)] = dict(
            time_s=times, numerical=values.tolist(), exact=exact_values.tolist()
        )
    assert errors[0] < 1e-4 and errors[1] < errors[0] / 14 and errors[2] < errors[1] / 14
    assert closed_exact[0] < 1e-5 * opened_exact[0]
    assert reference.clock(damage, 0, 0, 1) == (damage, 0.0, 0.0)
    evidence(
        f"morris-lecar-repair-twelve-tau-{damage}",
        dict(
            status="passed",
            initial_damage=damage,
            hazard_per_s=a,
            closure_per_s=b,
            opening_time_s=opening_time,
            closing_time_s=closing_time,
            tau_multiples=[12, 12],
            max_trace_errors=errors,
            observed_orders=np.log2(np.array(errors[:-1]) / errors[1:]).tolist(),
            final_exact=closed_exact.tolist(),
            traces=traces,
            scope=(
                "Separate scalar damage/integral clocks; "
                "not a long coupled run, fit, or biological recovery"
            ),
            full_coupled_step_ceiling_s=0.625e-6,
        ),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "damage_low",
        "damage_high",
        "damage_nan",
        "pad_damage",
        "ledger",
        "negative_heat",
        "calcium_injury",
        "pad_channel",
        "absent_h",
        "instant_m",
        "injury_nan",
        "injury_high",
        "pad_injury",
    ],
)
def test_invalid_damage_gates_controls_and_ledgers_are_rejected(fault):
    spec, state, p, control = initial()
    if fault.startswith("damage_"):
        state.damage[0] = dict(damage_low=-0.1, damage_high=1.1, damage_nan=np.nan)[fault]
    elif fault == "pad_damage":
        state.damage[-1] = 0.1
    elif fault == "ledger":
        state.damage_opened[0] = 0.1
    elif fault == "negative_heat":
        state.injury_dissipated_energy_pJ[0, 0] = -1.0
    elif fault == "calcium_injury":
        state.injury_transferred[spec.model.species_ids.index("Ca"), 0] = 0.1
    elif fault == "pad_channel":
        control.channel[-1] = 0.1
    elif fault == "absent_h":
        state.channel_gate[1, np.flatnonzero(p.channel_laws == 40)[0]] = 1e-10
    elif fault == "instant_m":
        state.channel_gate[0, np.flatnonzero(p.channel_laws == 45)[0]] = 1e-10
    else:
        control.injury[-1 if fault == "pad_injury" else 0] = (
            np.nan if fault == "injury_nan" else 1.1
        )
    assert not model.control_domain_valid(state, control, p, p.active, xp=np)
    if fault in {
        "damage_low",
        "damage_high",
        "damage_nan",
        "pad_damage",
        "ledger",
        "negative_heat",
        "calcium_injury",
        "absent_h",
        "instant_m",
    }:
        with pytest.raises(NumericalError):
            model.check_values(state, spec)


@pytest.mark.parametrize(
    "fault",
    [
        "old_identity",
        "old_parent",
        "calcium_route",
        "boolean_rate",
        "unknown_law",
        "duplicate_patch",
        "duplicate_time",
        "missing_control",
    ],
)
def test_strict_versioned_injury_schema(fault):
    raw = fixtures.definition()
    p = raw["model"]["injury_patches"][0]
    c = raw["experiment"]["injury_controls"][0]
    if fault == "old_identity":
        raw["model"]["id"] = "resolved_repair@1"
    elif fault == "old_parent":
        raw["model"]["ionic"]["id"] = "resolved_tissue@7"
    elif fault == "calcium_route":
        p["permeability_m_per_s"]["Ca"] = 1e-9
    elif fault == "boolean_rate":
        p["injury_rate_per_s"] = True
    elif fault == "unknown_law":
        p["law"] = "biological_repair@1"
    elif fault == "duplicate_patch":
        raw["model"]["injury_patches"][1] = deepcopy(p)
    elif fault == "duplicate_time":
        c["schedule"][1]["time"] = 0.0
    else:
        raw["experiment"]["injury_controls"].pop()
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize("fault", ["step", "rate", "loss"])
def test_coupled_step_damage_and_transport_guards_remain(fault):
    raw = fixtures.definition()
    # Isolate the intended guard from exact accepted-observation membership.
    raw["experiment"]["observation_times"] = [0.0, raw["experiment"]["end_time"]]
    if fault == "step":
        raw["execution"]["dt"] = 1e-6
    else:
        for row in raw["model"]["injury_patches"]:
            if fault == "rate":
                row.update(injury_rate_per_s=1e5, resealing_rate_per_s=1e5)
            else:
                row["permeability_m_per_s"]["Na"] = 1e-5
        if fault == "loss":
            # The default finite volumes remain safe even at maximum injury
            # permeability. A larger explicit patch area crosses the loss bound.
            for patch in raw["model"]["ionic"]["membranes"]:
                patch["area_m2"] *= 1e5
            # Otherwise the dedicated high-permeability CaV route correctly
            # rejects this geometry before the injury-specific guard is reached.
            for channel in raw["model"]["calcium_channels"]:
                channel["max_permeability_m_per_s"] = 0.0
    spec = parse_spec(raw)
    if fault == "loss":
        # Establish the scientific premise using the physical ownership bound.
        assert spec.execution.dt * model.injury_loss_bound(spec) > 0.25
        parent = base_spec(spec)
        prior.check_steps(parent, np.array([spec.execution.dt]), control_values(parent, [0.0]))
    with pytest.raises(ConfigError, match="Injury requires"):
        timeline(spec)


@pytest.mark.parametrize(
    "version,fixture,ref",
    [
        (1, old_fixtures, old_reference),
        (2, mobile_fixtures, mobile_reference),
        (3, pump_fixtures, pump_reference),
    ],
)
def test_existing_repair_versions_keep_catalog_and_independent_stage(version, fixture, ref):
    raw = fixture.definition()
    raw["model"]["injury_patches"][0]["initial_damage"] = 0.3
    spec, state, p, control = initial(raw, time=5.3e-6)
    legacy = get_model(spec.model)
    assert legacy is not model and type(p) is legacy.LAYOUT_TYPE
    assert spec.to_dict()["model"]["id"] == f"resolved_repair@{version}"
    assert parse_spec(spec.to_dict()) == spec
    value = legacy.readouts(state, control, p, xp=np)
    assert value.valid
    _, checked = compare(spec, state, value.derivative, 5.3e-6, ref=ref)
    if version == 1:
        assert legacy is original and len(state) == 39
        assert type(original.base_layout(p)) is original.prior.LAYOUT_TYPE
    evidence(f"morris-lecar-repair-legacy-{version}", dict(status="passed", **checked))


def test_initial_ordinary_snapshot_observer_and_report_metadata(tmp_path):
    spec, state, p, _ = initial(fixtures.compact_probe())
    point = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    validate_checkpoint(spec, point)
    write_snapshot(tmp_path / "initial", spec, point)
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, state)
    exact(saved.checkpoint.layout, p)
    with pytest.raises(ConfigError, match="state/layout"):
        validate_checkpoint(
            spec,
            replace(
                point,
                layout=original.LAYOUT_TYPE(*(getattr(p, k) for k in original.LAYOUT_TYPE._fields)),
            ),
        )
    history = model.STATE_TYPE(*(v[None, ...] for v in state))
    times = np.array([0.0])
    diagnostics = model.check_values(history, spec)
    observations = model.observe_history(times, history, p, times, spec)
    empty = model.observe_history(times, history, p, np.array([]), spec)
    assert all(v.shape[0] == 0 for v in vars(empty).values())
    result = RunResult(spec, point, 0, times, history, observations, {}, diagnostics)
    summary = write_run(tmp_path / "report", result)
    manifest = json.loads((tmp_path / "report/manifest.json").read_text())
    assert summary["model"] == fixtures.MODEL_ID and len(summary["state_fields"]) == 39
    assert summary["structural_repair_energy"] == "not modelled"
    assert manifest["observer"]["id"] == model.OBSERVER_ID
    assert manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID
    evidence(
        "morris-lecar-repair-ordinary-initial-artifacts",
        dict(
            status="passed",
            summary=summary,
            manifest=manifest,
            scope="Initial state only; no trajectory or settling claim",
        ),
    )


def test_assembly_conduction_controls_report_and_complete_checkpoint(tmp_path):
    raw = json.loads(
        (Path(__file__).parents[2] / "configs/assembly_morris_lecar_repair.json").read_text()
    )
    assert raw == fixtures.assembly_definition()
    raw["ionic"]["model"]["injury_patches"][0]["initial_damage"] = 0.3
    spec = parse_assembly(raw)
    _, state, p, u = initial(spec.ionic.to_dict(), time=5.3e-6)
    levels = np.array([0.0, 1.0])
    held = modulate(u, levels, channel_owners(spec))
    exact(held.injury, u.injury)
    exact(held.resealing, u.resealing)
    actual = model.readouts(state, held, p, xp=np)
    original_value = model.readouts(state, u, p, xp=np)
    assert actual.valid
    np.testing.assert_array_equal(
        actual.derivative.injury_transferred, original_value.derivative.injury_transferred
    )
    _, checked = compare(spec.ionic, state, actual.derivative, 5.3e-6, levels=levels)
    initial_state = assembly.initial_state(spec)
    report = assembly.summary(spec, initial_state) | dict(
        arm="repair", wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert report["physical_model"] == fixtures.MODEL_ID
    assert report["injury"]["structural_repair_energy"] == "not modelled"
    assert report["injury"]["transfer_axes"] == ["world", "species", "membrane_patch"]
    assert aggregate([report, report])["repair"]["worlds"] == 2 * spec.pool.worlds
    for key in ("ip3", "calcium", "channel_transfer_axes", "channel_species_ids", "injury"):
        wrong = deepcopy(report)
        wrong.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    wrong = deepcopy(report)
    wrong["injury"]["transfer_direction"] = "inward positive"
    with pytest.raises(ValueError):
        aggregate([wrong])
    write_checkpoint(tmp_path / "assembly", spec, initial_state, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(flatten(newer).values(), flatten(initial_state).values())
    evidence(
        "morris-lecar-repair-assembly-initial",
        dict(
            status="passed",
            report=report,
            **checked,
            scope="Controlled stage and initial complete checkpoint/report; no stochastic history",
        ),
    )
