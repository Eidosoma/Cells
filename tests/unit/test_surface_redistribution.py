"""Ordinary mobile-surface integration, independent reference and replay contracts."""

import copy
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
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_redistribution_spec import base_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble import ionic
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_redistribution as model
from cells.models import surface_tissue as base
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from validation.tissue import surface_dynamics_fixtures
from validation.tissue import surface_redistribution_fixtures as fixtures
from validation.tissue import surface_redistribution_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, value):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def initial(raw=None):
    spec = parse_spec(fixtures.definition(backend=BACKEND) if raw is None else raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def exact(a, b):
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


def error_budget(c, actual, expected, *, atol=2e-11, charge_atol=3e-25, rtol=3e-9):
    absolute = reference.flatten(
        c,
        {
            k: np.full(shape, charge_atol if k.endswith("_C") else atol)
            for k, shape in c["shapes"].items()
        },
    )
    ratio = np.abs(actual - expected) / (absolute + rtol * np.abs(expected))
    assert np.max(ratio, initial=0) <= 1
    return float(np.max(ratio, initial=0))


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registered_roundtrip_and_ensemble(backend):
    raw = fixtures.definition(backend=backend)
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_stage_and_separate_energy(arm, padded):
    raw = fixtures.definition(arm, padded=padded)
    spec, state, p, control = initial(raw)
    actual = model.rhs(state, control, p, p.active, xp=np)
    c = reference.bind(raw)
    expected, phi, proof = reference.evaluate(c, reference.initial(c), 0.0)
    ratio = error_budget(
        c,
        reference.flatten(c, actual._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    values = model.field_values(state, control, p, xp=np)
    np.testing.assert_allclose(
        np.r_[values.potential_V[:1], values.potential_V[p.active.size : p.active.size + 2]],
        phi,
        atol=3e-13,
        rtol=3e-10,
    )
    r = model.surface_rates(state, p, xp=np)
    log_density = np.log(
        np.where(
            p.surface_amount_reference > 0, r.density_fmol_um2 / p.reference_density[:, None], 1.0
        )
    )
    chemical_rate = (
        1e-3
        * model.R
        * p.temperature
        * np.sum(log_density * actual.surface_amount_increment, axis=1)
    )
    np.testing.assert_allclose(
        chemical_rate + actual.surface_dissipated_energy_pJ.sum(axis=1), 0, atol=3e-15, rtol=0
    )
    assert values.converged and abs(values.energy_balance_pJ_s) < 1e-10
    assert model.check_values(state, spec)["max_surface_energy_balance_error_pJ"] == 0
    if arm in ("uniform", "empty", "immobile"):
        np.testing.assert_allclose(actual.surface_amount_increment, 0, atol=2e-15, rtol=0)
    if arm == "blocked":
        assert not np.any(actual.membrane_transferred)
        assert np.max(np.abs(actual.surface_amount_increment)) > 1
    evidence(
        f"mobile-stage-{arm}-{'padded' if padded else 'compact'}",
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


def test_stage_uses_current_density_and_preserves_background():
    spec, state, p, control = initial()
    delta = state.surface_amount_increment.copy()
    delta[0, :2] = [-0.002, 0.002]
    changed = state._replace(surface_amount_increment=delta)
    actual = model.rhs(changed, control, p, p.active, xp=np)
    c = reference.bind(spec.to_dict())
    expected, _, _ = reference.evaluate(c, reference.flatten(c, changed._asdict()), 0.0)
    error_budget(
        c,
        reference.flatten(c, actual._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    original = model.rhs(state, control, p, p.active, xp=np)
    assert np.max(np.abs(actual.membrane_transferred - original.membrane_transferred)) > 1e-3
    np.testing.assert_array_equal(
        model.effective_layout(changed, p, xp=np).membrane_permeability[2],
        p.membrane_permeability[2],
    )


@pytest.mark.parametrize("boundary", ["open", "closed"])
def test_multicell_resolved_field_stage(boundary):
    raw = surface_dynamics_fixtures.definition(boundary)
    source = fixtures.definition()["model"]
    m = raw["model"]
    m["id"] = model.MODEL_ID
    m["mobile_populations"] = copy.deepcopy(source["mobile_populations"])
    for k, pop in enumerate(m["mobile_populations"]):
        pop["initial_amount_fmol"] = {
            p["id"]: p["area_m2"] * 1e12 * 1e-4 * (1 + 0.2 * j + 0.05 * k)
            for j, p in enumerate(m["membranes"])
        }
    m["surface_edges"] = []
    for cell in m["cells"]:
        patches = [p["id"] for p in m["membranes"] if p["inside"] == cell["id"]]
        m["surface_edges"].append(
            dict(
                id="along_" + cell["id"],
                sender=patches[0],
                receiver=patches[1],
                width_um=1.0,
                distance_um=2.0,
            )
        )
    raw["execution"].update(population_capacity=3, surface_edge_capacity=3)
    _, state, p, control = initial(raw)
    actual = model.rhs(state, control, p, p.active, xp=np)
    c = reference.bind(raw)
    expected, _, proof = reference.evaluate(c, reference.initial(c), 0)
    ratio = error_budget(
        c,
        reference.flatten(c, actual._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    np.testing.assert_allclose(
        model.surface_rates(state, p, xp=np).cell_rate_residual_fmol_s, 0, atol=2e-15, rtol=0
    )
    evidence(
        "mobile-multicell-" + boundary,
        dict(status="passed", inputs=raw, max_error_over_budget=ratio, independent_root=proof),
    )


@pytest.mark.parametrize(
    "fault",
    [
        "charge",
        "owner",
        "duplicate_edge",
        "duplicate_id",
        "density",
        "negative",
        "partial_empty",
        "missing_patch",
        "missing_ion",
        "diffusion",
        "width",
        "capacity",
        "step",
    ],
)
def test_invalid_definitions_are_rejected(fault):
    raw = fixtures.definition()
    m, x = raw["model"], raw["execution"]
    p, edge = m["mobile_populations"][0], m["surface_edges"][0]
    if fault == "charge":
        p["effective_charge_e"] = 1
    elif fault == "owner":
        edge["receiver"] = "cell"
    elif fault == "duplicate_edge":
        m["surface_edges"].append(
            dict(edge, id="other_edge", sender=edge["receiver"], receiver=edge["sender"])
        )
    elif fault == "duplicate_id":
        p["id"] = "cell"
    elif fault == "density":
        p["reference_density_fmol_per_um2"] = 0
    elif fault == "negative":
        p["initial_amount_fmol"]["patch_0"] = -0.01
    elif fault == "partial_empty":
        p["initial_amount_fmol"]["patch_0"] = 0
    elif fault == "missing_patch":
        del p["initial_amount_fmol"]["patch_1"]
    elif fault == "missing_ion":
        del p["permeability_at_reference_density_m_per_s"]["Cl"]
    elif fault == "diffusion":
        p["diffusivity_um2_per_s"] = -1
    elif fault == "width":
        edge["width_um"] = 0
    elif fault == "capacity":
        x["population_capacity"] = 1
    else:
        p["diffusivity_um2_per_s"] *= 100
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("name", tuple(model.EXTRA_AXES))
def test_corrupt_surface_ledgers_are_rejected(name):
    spec, state, _, _ = initial()
    value = getattr(state, name).copy()
    value[0, 0] = 1e-4
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{name: value}), spec)


def test_negative_absent_padding_and_disabled_routes_rejected():
    for arm, name, index, value in (
        ("mobile", "surface_amount_increment", (0, 0), -0.03),
        ("empty", "surface_amount_increment", (0, 0), 0.01),
        ("mobile", "surface_amount_increment", (2, 0), 0.01),
        ("mobile", "surface_transferred", (0, 1), 0.01),
        ("immobile", "surface_transferred", (0, 0), 0.01),
    ):
        _, state, p, _ = initial(fixtures.definition(arm))
        v = getattr(state, name).copy()
        v[index] = value
        assert not model.domain_valid(state._replace(**{name: v}), p, p.active, xp=np)


def test_empty_and_static_populations_reduce_to_passive_model():
    for arm in ("empty", "immobile"):
        spec, state, p, control = initial(fixtures.definition(arm))
        effective = model.effective_layout(state, p, xp=np)
        exact(
            model.base_state(model.rhs(state, control, p, p.active, xp=np)),
            base.rhs(model.base_state(state), control, effective, p.active, xp=np),
        )
        if arm == "empty":
            exact(effective, model.base_layout(p))
        assert base_spec(spec).to_dict()["model"]["id"] == base.MODEL_ID


def test_compiled_stage_matches_numpy():
    _, state, p, control = initial()
    expected = model.rhs(state, control, p, p.active, xp=np)
    state, p, control = jax.device_put((state, p, control), jax.devices(BACKEND)[0])
    actual = jax.jit(model.rhs)(state, control, p, p.active)
    for name, a, b in zip(model.STATE_TYPE._fields, actual, expected, strict=True):
        assert a.device.platform == BACKEND
        np.testing.assert_allclose(a, b, atol=3e-23 if name.endswith("_C") else 3e-12, rtol=3e-10)


@pytest.fixture(scope="module")
def trajectories():
    values = {}
    for arm in ("mobile", "immobile", "blocked"):
        value = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        assert all(v.device.platform == BACKEND for v in value.final.state)
        values[arm] = value
        if EVIDENCE:
            path = Path(EVIDENCE) / BACKEND
            path.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                path / ("mobile-trajectory-" + arm + ".npz"),
                **{k: np.asarray(v) for k, v in value.history._asdict().items()},
                **{"observed_" + k: v for k, v in vars(value.observations).items()},
            )
    return values


@pytest.mark.parametrize("arm", ["mobile", "immobile", "blocked"])
def test_independent_ordinary_trajectory(arm, trajectories):
    result = trajectories[arm]
    expected = reference.integrate(result.spec.to_dict())
    c = reference.bind(result.spec.to_dict())
    evidence(
        "mobile-reference-" + arm,
        dict(status="evaluated", inputs=result.spec.to_dict(), reference=expected),
    )
    ratio = error_budget(
        c, reference.flatten(c, vars(result.observations)), np.asarray(expected["state"])
    )
    np.testing.assert_allclose(
        np.c_[
            result.observations.cell_potential_V[:, :1],
            result.observations.extracellular_potential_V[:, :2],
        ],
        expected["potential_V"],
        atol=2e-8,
        rtol=3e-9,
    )
    evidence(
        "mobile-trajectory-" + arm,
        dict(
            status="passed",
            inputs=result.spec.to_dict(),
            reference=expected,
            max_error_over_budget=ratio,
            diagnostics=result.diagnostics,
        ),
    )


def test_analytic_diffusion_and_effect_on_ionic_dynamics(trajectories):
    mobile, fixed, blocked = (trajectories[k] for k in ("mobile", "immobile", "blocked"))
    p = mobile.final.layout
    for k, pop in enumerate(mobile.spec.model.mobile_populations):
        a, b = p.mobile_patch_area_um2[:2]
        initial_amount = p.surface_amount_reference[k, :2]
        equilibrium = np.sum(initial_amount) * np.asarray([a, b]) / (a + b)
        decay = pop.diffusivity_um2_per_s * 2 * (1 / a + 1 / b)
        expected = equilibrium[None] + (initial_amount - equilibrium)[None] * np.exp(
            -decay * mobile.observations.times[:, None]
        )
        np.testing.assert_allclose(
            mobile.observations.surface_amount_fmol[:, k, :2], expected, atol=3e-12, rtol=0
        )
    np.testing.assert_array_equal(
        mobile.history.surface_amount_increment, blocked.history.surface_amount_increment
    )
    assert not np.any(fixed.history.surface_amount_increment)
    assert not np.any(blocked.history.membrane_transferred)
    current_effect = float(
        np.max(
            np.abs(
                mobile.observations.membrane_flux_fmol_s[-1]
                - fixed.observations.membrane_flux_fmol_s[-1]
            )
        )
    )
    voltage_effect = float(
        np.max(
            np.abs(
                mobile.observations.membrane_voltage_V[-1]
                - fixed.observations.membrane_voltage_V[-1]
            )
        )
    )
    assert current_effect > 1e-3 and voltage_effect > 1e-8
    evidence(
        "mobile-coupling-controls",
        dict(
            status="passed",
            current_difference_fmol_s=current_effect,
            voltage_difference_V=voltage_effect,
            scope="synthetic accelerated diffusion, not biological validation",
        ),
    )


def test_numpy_timestep_refinement_and_reference_accuracy():
    raw = fixtures.definition()
    c = reference.bind(raw)
    target = np.asarray(reference.integrate(raw)["state"])[-1]
    tighter = np.asarray(reference.integrate(raw, refinement=2)["state"])[-1]
    reference_ratio = error_budget(c, target, tighter, atol=2e-13, charge_atol=3e-27, rtol=0)
    errors, charges = [], []
    steps = [5e-5, 2.5e-5, 1.25e-5]
    for dt in steps:
        spec, state, p, control = initial(raw)
        for _ in range(round(spec.experiment.end_time / dt)):
            state = rk4_step(
                lambda y, held=control, layout=p: model.rhs(y, held, layout, layout.active, xp=np),
                state,
                dt,
            )
            assert model.control_domain_valid(state, control, p, p.active, xp=np)
        delta = reference.unpack(c, reference.flatten(c, state._asdict()) - tighter)
        errors.append(
            max(
                float(np.max(np.abs(v), initial=0))
                for k, v in delta.items()
                if not k.endswith("_C")
            )
        )
        charges.append(float(np.max(np.abs(delta["electrode_charge_transferred_C"]), initial=0)))
    assert errors[-1] <= max(errors[0] / 100, 3e-13)
    assert charges[-1] <= max(charges[0] / 100, 3e-27)
    evidence(
        "mobile-refinement",
        dict(
            status="passed",
            implementation="NumPy production RK4/RHS",
            steps_s=steps,
            amount_energy_max_errors=errors,
            electrode_charge_max_errors_C=charges,
            reference_tightening_error_over_budget=reference_ratio,
        ),
    )


def test_checkpoint_branch_and_window_replay(trajectories, tmp_path):
    value = trajectories["mobile"]
    checkpoint = value.checkpoint_at(0.0002)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    exact(loaded.checkpoint.state, checkpoint.state)
    resumed = run(loaded.spec, loaded.checkpoint)
    exact(resumed.history, tuple(v[checkpoint.step_index :] for v in value.history))
    exact(tuple(v[0] for v in run(value.spec, value.final).history), value.final.state)
    raw = value.spec.to_dict()
    for control in raw["experiment"]["membrane_controls"]:
        control["schedule"].append(dict(time=0.0002, availability=0.0))
    spec = parse_spec(raw)
    branch = run(spec, branch_checkpoint(value.spec, checkpoint, spec))
    exact(tuple(v[0] for v in branch.history), checkpoint.state)
    np.testing.assert_array_equal(
        branch.final.state.membrane_transferred, checkpoint.state.membrane_transferred
    )
    np.testing.assert_array_equal(
        branch.final.state.surface_amount_increment, value.final.state.surface_amount_increment
    )
    parts = list(iter_windows(value.spec, WindowPolicy(4, "full")))
    merged = tuple(
        np.concatenate([getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    exact(merged, value.history)
    fresh = subprocess.run(
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
        capture_output=True,
        text=True,
        timeout=180,
    )
    (tmp_path / "fresh.stdout.log").write_text(fresh.stdout)
    (tmp_path / "fresh.stderr.log").write_text(fresh.stderr)
    fresh.check_returncode()
    exact(load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint.state, resumed.final.state)
    evidence(
        "mobile-replay",
        dict(
            status="passed",
            comparison="bitwise",
            state_fields=list(model.STATE_TYPE._fields),
            disk=True,
            terminal=True,
            branch=True,
            windows=True,
            fresh_process=True,
        ),
    )


def test_independent_world_batch_and_order(trajectories):
    worlds = tuple(
        WorldSpec(i + 1, trajectories[a].spec) for i, a in enumerate(("mobile", "immobile"))
    )
    # The refined grid needs 32 steps plus conservative event headroom per world.
    spec = BatchSpec(worlds, 2, 128, 2**28)
    result = run_batch(spec)
    reversed_result = run_batch(BatchSpec(tuple(reversed(worlds)), 2, 128, 2**28))
    # The ordinary batch result owns individual complete trajectories by world ID.
    for identity, world in result.worlds.items():
        other = reversed_result.worlds[identity]
        exact(world.history, other.history)
        original = trajectories["mobile" if identity == 1 else "immobile"]
        for name, a, b in zip(
            model.STATE_TYPE._fields, world.history, original.history, strict=True
        ):
            np.testing.assert_allclose(
                a, b, atol=3e-25 if name.endswith("_C") else 3e-12, rtol=3e-10
            )
    raw = copy.deepcopy(spec.to_dict())
    raw["worlds"][1]["simulation"]["execution"]["population_capacity"] += 1
    with pytest.raises(ConfigError):
        parse_batch(raw)
    evidence("mobile-independent-worlds", dict(status="passed", worlds=2, reordered="bitwise"))


def test_cpu_gpu_complete_saved_states_and_observations(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    count = 0
    for arm, value in trajectories.items():
        actual = {
            **value.history._asdict(),
            **{"observed_" + k: v for k, v in vars(value.observations).items()},
        }
        with np.load(
            Path(EVIDENCE) / "cpu" / ("mobile-trajectory-" + arm + ".npz"), allow_pickle=False
        ) as saved:
            assert set(actual) == set(saved.files)
            for name, values in actual.items():
                atol = (
                    3e-25
                    if name.endswith("_C")
                    else (
                        3e-23 if name.endswith("_A") else (3e-11 if name.endswith("_V") else 3e-13)
                    )
                )
                np.testing.assert_allclose(values, saved[name], rtol=3e-10, atol=atol)
                count += values.size
    evidence(
        "mobile-cpu-gpu",
        dict(
            status="passed",
            physical_scalars=count,
            rtol=3e-10,
            amount_energy_atol=3e-13,
            charge_atol_C=3e-25,
            current_atol_A=3e-23,
            voltage_atol_V=3e-11,
        ),
    )
