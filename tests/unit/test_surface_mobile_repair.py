"""Complete mobile-channel/calcium/injury composition with distinct material owners."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.errors import NumericalError
from cells.core.runner import run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_mobile_repair_spec import prior_spec
from cells.ensemble import ionic
from cells.io import load_snapshot
from cells.models import surface_mobile_repair as model
from cells.models import surface_repair as prior
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step, rk4_step
from tests.unit.test_surface_mobile_channel import error_budget, exact
from validation.tissue import surface_mobile_repair_fixtures as fixtures
from validation.tissue import surface_mobile_repair_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
PUBLISHED_EVIDENCE = os.environ.get("CELLS_COMPONENT_PUBLISHED_EVIDENCE")


def evidence(name, value, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def initial(raw=None):
    spec = parse_spec(fixtures.definition(backend=BACKEND) if raw is None else raw)
    state, p = model.initial_values(spec)
    c = control_values(spec, [0.0])
    return spec, state, p, type(c)(*(v[0] for v in c))


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registration_roundtrip_and_ensemble(backend):
    raw = fixtures.definition(backend=backend)
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec and get_model(spec.model) is model
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    assert len(model.STATE_TYPE._fields) == 47


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_complete_stage_and_ownership(arm, padded):
    raw = fixtures.definition(arm, backend=BACKEND, padded=padded)
    spec, state, p, control = initial(raw)
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(raw)
    expected, phi, proof = reference.evaluate(c, reference.initial(c), 0.0)
    ratio = error_budget(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    np.testing.assert_allclose(
        np.r_[
            actual.field.potential_V[: p.active.size][p.active],
            actual.field.potential_V[p.active.size :][p.outside_active],
        ],
        phi,
        rtol=3e-10,
        atol=3e-13,
    )
    assert actual.valid and abs(actual.field.energy_balance_pJ_s) < 1e-10
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    assert not np.any(
        actual.derivative.channel_state_amount_increment[p.channel_state_reference == 0]
    )
    model.check_values(state, spec)
    evidence(
        f"mobile-repair-stage-{arm}-{'padded' if padded else 'compact'}",
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


def test_single_free_ion_owner_controls_and_ionic_energy():
    _, state, p, control = initial()
    w = model.readouts(state, control, p, xp=np)
    blocked = model.readouts(
        state, control._replace(mobile_channel=np.zeros_like(control.mobile_channel)), p, xp=np
    )
    diff = w.derivative.amount_increment - blocked.derivative.amount_increment
    chemical = w.derivative.chemical_amount_increment - blocked.derivative.chemical_amount_increment
    assert np.max(np.abs(diff)) > 1e-5
    for i in range(p.er_initial_amount.shape[0]):
        np.testing.assert_allclose(
            chemical[i],
            (p.free_ion_selector @ diff[:, i])[:, None] * p.cytosol_selector[i],
            atol=3e-12,
            rtol=3e-10,
        )
    assert not np.any(diff[np.arange(len(p.valence)) != p.mobile_potassium])
    exact(
        (w.derivative.damage, w.gating.amount_rate, w.motion.flux_fmol_s),
        (blocked.derivative.damage, blocked.gating.amount_rate, blocked.motion.flux_fmol_s),
    )
    off = model.readouts(state, control._replace(injury=np.ones_like(control.injury)), p, xp=np)
    np.testing.assert_array_equal(
        off.derivative.mobile_channel_transferred, w.derivative.mobile_channel_transferred
    )
    assert np.any(off.derivative.damage != w.derivative.damage)
    assert np.min(w.derivative.mobile_channel_dissipated_energy_pJ, initial=0) >= 0
    evidence(
        "mobile-repair-ownership",
        dict(
            status="passed",
            free_cytosol_updated_once=True,
            independent_injury_controls=True,
            blocking_preserves_proteins_and_gates=True,
        ),
    )


@pytest.mark.parametrize("arm", ["blocked", "empty"])
def test_reduction_to_existing_repair(arm):
    spec, state, p, control = initial(fixtures.definition(arm))
    actual = model.readouts(state, control, p, xp=np)
    expected = prior.readouts(
        model.prior_state(state), model.prior_control(control), model.prior_layout(p), xp=np
    )
    exact(model.prior_state(actual.derivative), expected.derivative)
    exact(jax.tree.leaves(actual.field), jax.tree.leaves(expected.field))
    assert prior_spec(spec).to_dict()["model"]["id"] == "resolved_repair@1"


def test_independent_clocks_and_zero_surface_edges():
    raw = fixtures.definition("release")
    raw["model"]["surface_edges"] = []
    raw["execution"]["surface_edge_capacity"] = 0
    spec, state, p, control = initial(raw)
    grid = timeline(spec)
    assert all(t in grid for t in (5.3e-6, 15.3e-6, 19.1e-6, 29.1e-6))
    assert model.readouts(state, control, p, xp=np).valid
    assert state.channel_state_transferred.shape[-1] == 0
    evidence("mobile-repair-clocks", dict(status="passed", inputs=raw, steps=len(grid) - 1))


@pytest.mark.parametrize("name", tuple(model.EXTRA_AXES))
def test_corrupt_mobile_material_and_ion_ledgers_rejected(name):
    spec, state, _, _ = initial()
    value = getattr(state, name).copy()
    value.flat[0] = 1e-4
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: value}), spec)


@pytest.mark.parametrize(
    "fault",
    [
        "cross_cell",
        "duplicate_edge",
        "edge_width",
        "missing_patch",
        "zero_state",
        "negative_amount",
        "law",
        "species",
        "temperature",
        "duplicate_owner",
        "missing_control",
        "control_value",
        "control_clock",
        "channel_capacity",
        "edge_capacity",
        "surface_step",
    ],
)
def test_invalid_definitions(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    pop = m["mobile_channels"][0]
    if fault == "cross_cell":
        m["surface_edges"][0]["receiver"] = "membrane_2"
    elif fault == "duplicate_edge":
        m["surface_edges"].append(copy.deepcopy(m["surface_edges"][0]))
        x["surface_edge_capacity"] += 1
    elif fault == "edge_width":
        m["surface_edges"][0]["width_um"] = 0
    elif fault == "missing_patch":
        pop["initial_state_amount_fmol"]["m0h0"].pop("membrane_0")
    elif fault == "zero_state":
        pop["initial_state_amount_fmol"]["m0h0"]["membrane_0"] = 0
    elif fault == "negative_amount":
        pop["initial_state_amount_fmol"]["m0h0"]["membrane_0"] = -1
    elif fault == "law":
        pop["kinetic_law"] = "unknown"
    elif fault == "species":
        pop["species_id"] = "Ca"
    elif fault == "temperature":
        m["ionic"]["temperature_K"] = 300
    elif fault == "duplicate_owner":
        pop["id"] = m["ionic"]["channels"][0]["id"]
    elif fault == "missing_control":
        e["mobile_channel_controls"].pop()
    elif fault == "control_value":
        e["mobile_channel_controls"][0]["schedule"][0]["availability"] = 1.01
    elif fault == "control_clock":
        e["mobile_channel_controls"][0]["schedule"][0]["time"] = 1e-6
    elif fault == "channel_capacity":
        x["channel_population_capacity"] = 1
    elif fault == "edge_capacity":
        x["surface_edge_capacity"] = 0
    else:
        pop["diffusivity_um2_per_s"] *= 100000
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_compiled_stage_and_invalid_trial_guard():
    _, state, p, control = initial()
    expected = model.rhs(state, control, p, p.active, xp=np)
    state, p, control = jax.device_put((state, p, control), jax.devices(BACKEND)[0])
    actual = jax.jit(model.rhs)(state, control, p, p.active)
    for name, a, b in zip(model.STATE_TYPE._fields, actual, expected, strict=True):
        assert a.device.platform == BACKEND
        np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-23 if name.endswith("_C") else 3e-12)
    step = jax.jit(
        lambda y, c: rk4_checked_step(model.rhs, model.domain_valid, y, 0.625e-6, c, p, p.active)
    )
    bad = control._replace(mobile_channel=control.mobile_channel.at[0, 0].set(-1.0))
    kept, valid = step(state, bad)
    assert not valid
    exact(kept, state)
    bad_state = state._replace(
        channel_state_amount_increment=state.channel_state_amount_increment.at[0, 0, 0].set(-1.0)
    )
    kept, valid = step(bad_state, control)
    assert not valid
    exact(kept, bad_state)
    evidence(
        "mobile-repair-compiled-guard",
        dict(status="passed", backend=BACKEND, complete_state_rejection=True),
    )


ARMS = ("mobile", "immobile", "sham", "held", "release")


def arrays(value):
    return {
        "accepted_times": value.times,
        **value.history._asdict(),
        **{"observed_" + k: v for k, v in vars(value.observations).items()},
    }


def normalized(raw):
    value = copy.deepcopy(raw)
    value["execution"]["backend"] = "cpu"
    return value


def independent(raw, arm, *, refinement=1):
    name = f"mobile-repair-reference-{arm}-{refinement}"
    if BACKEND == "gpu" and EVIDENCE:
        root = Path(EVIDENCE) / "cpu"
        report = json.loads((root / (name + ".json")).read_text())
        assert report["status"] == "passed" and report["inputs"] == normalized(raw)
        assert report["refinement"] == refinement
        with np.load(root / (name + ".npz"), allow_pickle=False) as saved:
            result = {k: v.copy() for k, v in saved.items()}
        evidence(name, report | dict(reused_cpu_reference=True), result)
        return result
    result = reference.integrate(raw, refinement=refinement)
    saved = {k: np.asarray(result[k]) for k in ("times", "state", "potential_V")}
    evidence(
        name,
        dict(
            status="passed",
            inputs=normalized(raw),
            refinement=refinement,
            evaluations=result["evaluations"],
            method=result["method"],
        ),
        saved,
    )
    return saved


@pytest.fixture(scope="module")
def trajectories():
    values = {}

    def get(arm):
        if arm not in values:
            v = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
            assert all(y.device.platform == BACKEND for y in v.final.state)
            values[arm] = v
            evidence(
                "mobile-repair-history-" + arm,
                dict(status="captured", inputs=v.spec.to_dict(), diagnostics=v.diagnostics),
                arrays(v),
            )
        return values[arm]

    return get


def recorded_history(arm, trajectories, *, backend=BACKEND):
    """Read earlier workers' immutable arrays without retaining their compiled graphs."""
    if PUBLISHED_EVIDENCE:
        root = Path(PUBLISHED_EVIDENCE) / backend
    elif backend != BACKEND:
        assert EVIDENCE
        root = Path(EVIDENCE) / backend
    else:
        return arrays(trajectories(arm)), dict(source="current_process")
    name = "mobile-repair-history-" + arm
    report_path = root / (name + ".json")
    arrays_path = root / (name + ".npz")
    report = json.loads(report_path.read_text())
    assert report["status"] == "captured"
    assert report["inputs"] == parse_spec(fixtures.definition(arm, backend=backend)).to_dict()
    with np.load(arrays_path, allow_pickle=False) as saved:
        values = {key: value.copy() for key, value in saved.items()}
    assert set(model.STATE_TYPE._fields) <= set(values)
    return values, {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (report_path, arrays_path)
    }


def numpy_trajectory(raw):
    spec, state, p, _ = initial(raw)
    grid = timeline(spec)
    controls = control_values(spec, grid[:-1])
    history = [state]
    for i, h in enumerate(np.diff(grid)):
        control = type(controls)(*(v[i] for v in controls))
        state = rk4_step(lambda y, c=control: model.rhs(y, c, p, p.active, xp=np), state, h)
        assert model.control_domain_valid(state, control, p, p.active, xp=np)
        history.append(state)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*history, strict=True)))
    diagnostics = model.check_values(history, spec)
    observations = model.observe_history(grid, history, p, spec.experiment.observation_times, spec)
    return spec, grid, history, observations, diagnostics


@pytest.mark.parametrize("arm", ARMS)
def test_complete_trajectory_reference_and_analytic_material(arm, trajectories):
    v = trajectories(arm)
    raw = v.spec.to_dict()
    target = independent(raw, arm)
    c = reference.bind(raw)
    ratio = error_budget(c, reference.flatten(c, vars(v.observations)), target["state"])
    p = v.final.layout
    np.testing.assert_allclose(
        np.c_[
            v.observations.cell_potential_V[:, p.active],
            v.observations.extracellular_potential_V[:, p.outside_active],
        ],
        target["potential_V"],
        atol=2e-8,
        rtol=3e-9,
    )
    # Total channels follow neutral diffusion independently of internal gates.
    t = v.observations.times
    for k, pop in enumerate(v.spec.model.mobile_channels):
        for edge in v.spec.model.surface_edges:
            ids = [m.id for m in v.spec.model.membranes]
            i, j = ids.index(edge.sender), ids.index(edge.receiver)
            area = np.asarray(p.mobile_patch_area_um2)[[i, j]]
            start = np.asarray(p.channel_state_reference)[k, :][:, [i, j]].sum(axis=0)
            eq = start.sum() * area / area.sum()
            rate = pop.diffusivity_um2_per_s * edge.width_um / edge.distance_um * np.sum(1 / area)
            wanted = eq[None] + (start - eq)[None] * np.exp(-rate * t[:, None])
            actual = v.observations.mobile_channel_amount_fmol[:, k].sum(axis=1)[:, [i, j]]
            np.testing.assert_allclose(actual, wanted, atol=3e-13, rtol=0)
    # Prescribed damage retains the existing exact piecewise scalar solution.
    from validation.tissue.surface_repair_reference import analytic_damage

    for j, patch in enumerate(v.spec.model.injury_patches):
        schedule = raw["experiment"]["injury_controls"][j]["schedule"]
        for index, time in enumerate(t):
            damage = patch.initial_damage
            for a, b in zip(schedule, [*schedule[1:], dict(time=time)], strict=True):
                elapsed = min(time, b["time"]) - a["time"]
                if elapsed > 0:
                    damage = analytic_damage(
                        damage,
                        patch.injury_rate_per_s * a["injury"],
                        patch.resealing_rate_per_s * a["resealing"],
                        elapsed,
                    )
            np.testing.assert_allclose(v.observations.damage[index, j], damage, atol=2e-9, rtol=0)
    evidence(
        "mobile-repair-trajectory-" + arm,
        dict(
            status="passed",
            inputs=raw,
            max_error_over_budget=ratio,
            diagnostics=v.diagnostics,
            total_channel_diffusion_analytic=True,
            damage_analytic=True,
        ),
    )


def test_bidirectional_voltage_calcium_coupling(trajectories):
    values, sources = {}, {}
    for arm in ("mobile", "immobile", "sham", "held"):
        values[arm], sources[arm] = recorded_history(arm, trajectories)
    a, b = values["mobile"], values["immobile"]
    voltage = float(
        np.max(np.abs(a["observed_membrane_voltage_V"][-1] - b["observed_membrane_voltage_V"][-1]))
    )
    calcium = float(np.max(np.abs(a["observed_calcium_gate"][-1] - b["observed_calcium_gate"][-1])))
    assert voltage > 1e-10 and calcium > 1e-9
    sham = values["sham"]
    injury_gate = float(
        np.max(
            np.abs(
                a["observed_mobile_channel_open_fraction"][-1]
                - sham["observed_mobile_channel_open_fraction"][-1]
            )
        )
    )
    assert injury_gate > 1e-10
    assert values["held"]["observed_damage"][-1, 0] > a["observed_damage"][-1, 0] > 0
    # Injury changes gating through voltage, while neutral total-protein transport is independent.
    np.testing.assert_allclose(
        a["observed_mobile_channel_amount_fmol"].sum(axis=2),
        sham["observed_mobile_channel_amount_fmol"].sum(axis=2),
        atol=3e-13,
        rtol=0,
    )
    evidence(
        "mobile-repair-coupling",
        dict(
            status="passed",
            voltage_difference_V=voltage,
            calcium_gate_difference=calcium,
            injury_gate_difference=injury_gate,
            history_sources=sources,
            scope=(
                "synthetic interaction controls, not biological recovery or calibrated effect sizes"
            ),
        ),
    )


@pytest.mark.parametrize("arm", ["mobile", "release"])
def test_numpy_trajectory_refinement_and_reference_accuracy(arm):
    raw = fixtures.definition(arm, backend=BACKEND)
    c = reference.bind(raw)
    target = independent(raw, arm)
    tighter = independent(raw, arm, refinement=4)
    stability = error_budget(
        c, target["state"], tighter["state"], atol=3e-14, charge_atol=3e-28, rtol=0
    )
    errors, charges = [], []
    steps = (0.625e-6, 0.3125e-6, 0.15625e-6)
    for dt in steps:
        candidate = copy.deepcopy(raw)
        candidate["execution"]["dt"] = dt
        spec, grid, history, observed, diagnostics = numpy_trajectory(candidate)
        actual = reference.flatten(c, vars(observed))
        ratio = error_budget(c, actual, tighter["state"])
        delta = reference.unpack(c, actual - tighter["state"])
        errors.append(
            max(
                float(np.max(np.abs(v), initial=0))
                for k, v in delta.items()
                if not k.endswith("_C")
            )
        )
        charges.append(
            max(float(np.max(np.abs(v), initial=0)) for k, v in delta.items() if k.endswith("_C"))
        )
        evidence(
            f"mobile-repair-grid-{arm}-{dt}",
            dict(
                status="passed",
                inputs=spec.to_dict(),
                max_error_over_budget=ratio,
                diagnostics=diagnostics,
            ),
            dict(accepted_times=grid, **history._asdict(), error=actual - tighter["state"]),
        )
    assert errors[-1] <= max(errors[0] * 0.2, 3e-13)
    assert charges[-1] <= max(charges[0] * 0.2, 3e-27)
    evidence(
        "mobile-repair-refinement-" + arm,
        dict(
            status="passed",
            steps_s=steps,
            amount_energy_gate_errors=errors,
            charge_errors_C=charges,
            reference_stability_error_over_budget=stability,
            implementation="NumPy production RK4/RHS; unchanged tolerances",
        ),
    )


def test_complete_saved_restart_branch_and_windows(tmp_path):
    commands = [
        (
            phase,
            [
                sys.executable,
                "-B",
                "-m",
                "validation.tissue.surface_mobile_repair_replay",
                str(tmp_path),
                "--backend",
                BACKEND,
                "--phase",
                phase,
            ],
            900,
        )
        for phase in ("prepare", "resume_branch", "windows")
    ]
    commands.append(
        (
            "fresh",
            [
                sys.executable,
                "-B",
                "-m",
                "cells",
                "resume",
                str(tmp_path / "checkpoint"),
                "--output",
                str(tmp_path / "fresh"),
            ],
            600,
        )
    )
    for name, command, timeout in commands:
        with (
            (tmp_path / (name + ".stdout.log")).open("x") as out,
            (tmp_path / (name + ".stderr.log")).open("x") as err,
        ):
            subprocess.run(command, stdout=out, stderr=err, timeout=timeout, check=True)
    reports = {
        phase: json.loads((tmp_path / (phase + ".json")).read_text())
        for phase in ("prepare", "resume_branch", "windows")
    }
    for phase, report in reports.items():
        assert report["status"] == ("prepared" if phase == "prepare" else "passed")
        assert report["backend"] == BACKEND
        assert report["state_fields"] == list(model.STATE_TYPE._fields)
    assert reports["prepare"]["disk"]
    assert reports["resume_branch"]["branch"] and reports["resume_branch"]["terminal"]
    assert reports["resume_branch"]["saved_complete_history"] and reports["windows"]["windows"]
    target = load_snapshot(tmp_path / "expected").checkpoint
    actual = load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint
    exact(actual.state, target.state)
    exact(actual.layout, target.layout)
    assert (actual.time, actual.step_index, actual.event_index) == (
        target.time,
        target.step_index,
        target.event_index,
    )
    with (
        np.load(tmp_path / "expected_history.npz", allow_pickle=False) as expected,
        np.load(tmp_path / "fresh/trajectory.npz", allow_pickle=False) as fresh,
    ):
        assert set(expected.files) == {"accepted_times", *model.STATE_TYPE._fields}
        for name in expected.files:
            np.testing.assert_array_equal(fresh[name], expected[name])
    evidence(
        "mobile-repair-replay",
        dict(
            status="passed",
            phases=reports,
            state_fields=list(model.STATE_TYPE._fields),
            fresh_process=True,
            fresh_complete_history=True,
            fresh_layout_and_clock=True,
            sequential_workers=True,
        ),
    )


def test_independent_worlds_order_and_identity(trajectories):
    originals, sources = {}, {}
    for arm in ("mobile", "release"):
        originals[arm], sources[arm] = recorded_history(arm, trajectories)
    worlds = tuple(
        WorldSpec(i + 1, parse_spec(fixtures.definition(arm, backend=BACKEND)))
        for i, arm in enumerate(originals)
    )
    spec = BatchSpec(worlds, 2, 256, 2**30)
    values = run_batch(spec)
    reordered = run_batch(BatchSpec(tuple(reversed(worlds)), 2, 256, 2**30))
    for identity, v in values.worlds.items():
        exact(v.history, reordered.worlds[identity].history)
        scalar = originals["mobile" if identity == 1 else "release"]
        np.testing.assert_array_equal(v.times, scalar["accepted_times"])
        for name, a in v.history._asdict().items():
            np.testing.assert_allclose(
                a, scalar[name], rtol=3e-10, atol=3e-25 if name.endswith("_C") else 3e-12
            )
    raw = spec.to_dict()
    raw["worlds"][1]["simulation"]["execution"]["channel_population_capacity"] += 1
    with pytest.raises(ConfigError):
        parse_batch(raw)
    evidence(
        "mobile-repair-worlds",
        dict(
            status="passed",
            worlds=2,
            reordered="bitwise",
            independent_clocks=True,
            scalar_history_sources=sources,
        ),
    )


def test_cpu_gpu_complete_histories_and_observations(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires L4 phase and saved CPU histories")
    assert EVIDENCE
    count, sources = 0, {}
    for arm in ARMS:
        actual, gpu_source = recorded_history(arm, trajectories)
        saved, cpu_source = recorded_history(arm, trajectories, backend="cpu")
        sources[arm] = dict(cpu=cpu_source, gpu=gpu_source)
        assert set(actual) == set(saved)
        for name, y in actual.items():
            if name in ("accepted_times", "observed_times") or name.endswith(
                ("_availability", "_control")
            ):
                np.testing.assert_array_equal(y, saved[name])
            else:
                atol = (
                    3e-25
                    if name.endswith("_C")
                    else 3e-23
                    if name.endswith("_A")
                    else 3e-11
                    if name.endswith("_V")
                    else 3e-13
                )
                np.testing.assert_allclose(y, saved[name], rtol=3e-10, atol=atol)
            count += y.size
    evidence(
        "mobile-repair-cpu-gpu",
        dict(
            status="passed",
            physical_scalars=count,
            history_sources=sources,
            rtol=3e-10,
            amount_energy_gate_atol=3e-13,
            charge_atol_C=3e-25,
            current_atol_A=3e-23,
            voltage_atol_V=3e-11,
        ),
    )
