"""Finite ER chemistry, source contact, independent trajectories and CPU/L4 replay."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import parse_batch, run_batch
from cells.core.batch_windows import run_batch_windowed
from cells.core.devices import execution_device
from cells.core.er_spec import chemistry_spec
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, run_windowed
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import er_calcium as model
from cells.processes import er_calcium as process
from tests.batch_fixtures import definition
from tests.reference_er_calcium import NATIVE_HASHES, F, R, System, native_functions, reference

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_ER_TEST_BACKEND", "cpu")


def data():
    raw = json.loads((ROOT / "configs/er_calcium_buffered.json").read_text())
    raw["execution"]["backend"] = BACKEND
    return raw


def evidence(name, record=None, arrays=None):
    target = os.environ.get("CELLS_ER_EVIDENCE")
    if target:
        path = Path(target) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if record is not None:
            (path / (name + ".json")).write_text(
                json.dumps(record, indent=2, allow_nan=False) + "\n"
            )
        if arrays is not None:
            np.savez(path / (name + ".npz"), **arrays)


def equal(a, b):
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


def compare_reference(observations, expected):
    errors = {}
    for field in model.State._fields:
        actual = getattr(observations, field)
        if field == "amount_increment":
            actual = actual[..., :2]
        elif field in ("reaction_extent", "dissipated_energy_pJ"):
            actual = actual[..., :4]
        np.testing.assert_allclose(actual, expected[field], rtol=3e-9, atol=3e-12)
        errors[field] = float(np.max(np.abs(actual - expected[field]), initial=0))
    return errors


@pytest.fixture(scope="module")
def baseline():
    result = run(parse_spec(data()))
    assert all(v.device.platform == BACKEND for v in result.final.state)
    evidence(
        "baseline",
        {"status": "passed", "diagnostics": result.diagnostics},
        dict(zip(result.history._fields, result.history, strict=True)),
    )
    return result


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "membrane", "cytosol"), "er"),
        (("model", "membrane", "er"), "absent"),
        (("model", "membrane", "calcium_species"), "K"),
        (("model", "membrane", "area_m2"), 0),
        (("model", "membrane", "specific_capacitance_F_per_m2"), 0),
        (("model", "membrane", "initial_voltage_V"), 0.2),
        (("model", "membrane", "permeability_m_per_s", "Ca"), -1),
        (("model", "membrane", "pump", "law"), "serca_two_ca"),
        (("model", "membrane", "pump", "metabolism"), "finite_atp"),
        (("model", "membrane", "pump", "atp_mM"), 0),
        (("model", "membrane", "pump", "km_ca_mM"), 0),
        (("model", "membrane", "release", "activation_n"), 1.5),
        (("model", "membrane", "release", "inhibition_mM"), 0),
        (("experiment", "controls", 0, "pump"), 1.1),
        (("experiment", "controls", 0, "release"), True),
        (("experiment", "controls", 0, "passive", "Ca"), -1),
    ],
)
def test_invalid_physical_definitions(path, value):
    raw = data()
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_canonical_schema_padding_and_public_artifacts(baseline, tmp_path):
    raw = data()
    for field in ("species", "moieties", "reactions", "compartments"):
        raw["model"][field].reverse()
    assert parse_spec(raw) == baseline.spec == parse_spec(baseline.spec.to_dict())
    assert np.all(baseline.observations.amount[:, :, 2] == 0)
    assert np.all(baseline.history.reaction_extent[:, 4:] == 0)
    assert baseline.history.pump_transferred.shape == (801, 1)
    summary = write_run(tmp_path / "public", baseline)
    assert summary["pump_transferred_fmol"] > 0 and summary["release_transferred_fmol"] < 0
    loaded = load_snapshot(tmp_path / "public/checkpoint_final")
    equal(loaded.checkpoint.state, baseline.final.state)
    equal(loaded.checkpoint.layout, baseline.final.layout)


def test_stage_ownership_charge_and_resolved_energy():
    raw = data()
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    schedule = control_values(spec, [0])
    control = type(schedule)(*(v[0] for v in schedule))
    actual = model.rhs(state, control, p, p.active, xp=np)
    system = System(raw)
    expected = system.unpack(system.rhs(np.zeros(system.size), raw["experiment"]["controls"][0]))
    for field, a, b in zip(model.State._fields, actual, expected, strict=True):
        if field == "amount_increment":
            a = a[:, :2]
        if field in ("reaction_extent", "dissipated_energy_pJ"):
            a = a[:4]
        np.testing.assert_allclose(a, b, rtol=2e-12, atol=1e-14)
    mu = p.standard_mu_RT[:, None] + np.log(
        p.initial_amount / (p.volume * p.standard_concentration)
    )
    chemical_power = 1e-3 * R * p.temperature * np.sum(mu * actual.amount_increment)
    dv = F * 1e-15 / p.capacitance * np.dot(p.valence, actual.amount_increment[:, p.er])
    electric_power = 1e12 * p.capacitance * p.initial_voltage * dv
    work = (
        -1e-3
        * process.chemical_drive(model.pump_parameters(p), p.temperature, xp=np)
        * actual.pump_transferred[0]
    )
    assert (
        abs(
            chemical_power
            + electric_power
            + np.sum(actual.dissipated_energy_pJ)
            + np.sum(actual.transport_dissipated_energy_pJ)
            - work
        )
        < 2e-14
    )
    np.testing.assert_allclose(p.moieties @ np.sum(actual.amount_increment, axis=-1), 0, atol=1e-16)
    np.testing.assert_allclose(
        p.fixed_charge_C + F * 1e-15 * (p.valence @ (p.initial_amount * p.active)),
        p.capacitance * p.initial_voltage * p.incidence,
        atol=1e-24,
    )
    with pytest.raises(ConfigError, match="50 us"):
        timeline(replace(spec, execution=replace(spec.execution, dt=0.001)))


def test_native_pump_and_calcium_release_functions():
    native = native_functions()
    p = process.PumpParameters(0.003, 0.001, 0.5, 1.5, 0.1, 0.1, -10000.0)
    cy = np.array([1e-6, 0.0001, 0.002, 0.002, 0.02, 0.002])
    er = np.array([0.2, 0.1, 0.2, 0.2, 0.01, 0.2])
    v = np.array([-0.12, -0.04, 0.0, 0.12, 0.04, 0.05])
    params = SimpleNamespace(
        deltaGATP=p.delta_g0_J_per_mol,
        cATP=p.atp_mM,
        cADP=p.adp_mM,
        cPi=p.pi_mM,
        R=R,
        F=F,
        KmCa_Ca=p.km_ca_mM,
        KmCa_ATP=p.km_atp_mM,
        serca_max=p.capacity_fmol_per_s * 1e-15 / 1e-9,
    )
    expected = native["pumpCaER"](er, cy, v, 298.15, params) * 1e-9 / 1e-15
    actual, affinity, _ = process.pump_rates(cy, er, v, 298.15, p, 1.0, xp=np)
    np.testing.assert_allclose(actual, expected, rtol=3e-12, atol=3e-14)
    assert np.any(actual > 0) and np.any(actual < 0) and np.all(-actual * affinity >= 0)
    with jax.default_device(execution_device(BACKEND)):
        compiled = jax.jit(process.pump_rates)(cy, er, v, 298.15, p, 1.0)
        assert compiled[0].device.platform == BACKEND
        np.testing.assert_allclose(compiled[0], expected, rtol=3e-12, atol=3e-14)
    ca = np.geomspace(1e-6, 1.0, 25)
    params = SimpleNamespace(act_Km_Ca=0.001, act_n_Ca=2, inh_Km_Ca=0.02, inh_n_Ca=2, max_er=1.0)
    sim = SimpleNamespace(cc_cells=[ca], iCa=0, molecules=None, metabo=None, grn=None)
    er_object = SimpleNamespace(
        Dm_channels=np.zeros((1, len(ca))), Dm_er_base=np.zeros((1, len(ca)))
    )
    native["channels"](er_object, sim, None, params)
    opening = process.release_open(ca, 0.001, 2, 0.02, 2, xp=np)
    np.testing.assert_allclose(opening, er_object.Dm_channels[0], rtol=3e-14, atol=2e-16)
    with jax.default_device(execution_device(BACKEND)):
        compiled_opening = jax.jit(process.release_open)(ca, 0.001, 2, 0.02, 2)
        assert compiled_opening.device.platform == BACKEND
        np.testing.assert_allclose(compiled_opening, opening, rtol=3e-14, atol=2e-16)
    assert opening.max() > opening[0] and opening.max() > opening[-1]
    evidence(
        "native-laws",
        {
            "status": "passed",
            "pump_points": len(cy),
            "release_points": len(ca),
            "native_files_sha256": NATIVE_HASHES,
            "scope": (
                "Pinned functions with harmonized physical constants; "
                "no native lifecycle/trajectory claim"
            ),
        },
        {
            "pump_native": expected,
            "pump_cells": actual,
            "release_native": er_object.Dm_channels[0],
            "release_cells": opening,
        },
    )


def test_stall_and_no_reaction_electrochemical_equilibrium():
    p = process.PumpParameters(1, 1, 1, 1, 1, 1, 0)
    rate, energy, _ = process.pump_rates(1.0, 1.0, 0.0, 298.15, p, 1.0, xp=np)
    assert rate == energy == 0
    rate, energy, _ = process.pump_rates(1.0, 1.0 + 1e-12, 0.0, 298.15, p, 1.0, xp=np)
    assert rate < 0 and energy > 0
    raw = data()
    raw["model"]["reactions"] = []
    raw["model"]["membrane"].update(pump=None, release=None)
    for c in raw["model"]["compartments"]:
        c["initial_amount_fmol"] = {s["id"]: c["volume_pL"] for s in raw["model"]["species"]}
    raw["experiment"]["controls"][0]["reactions"] = {}
    raw["experiment"].update(end_time=0.0001, observation_times=[0, 0.000037, 0.0001])
    raw["execution"]["reaction_capacity"] = 0
    result = run(parse_spec(raw))
    assert all(np.all(v == 0) for v in result.history)


def test_independent_full_state_references_and_refinement(baseline):
    raw = data()
    references = [
        reference(raw, baseline.observations.times, method=m) for m in ("DOP853", "Radau")
    ]
    errors = {}
    for name, expected in zip(("DOP853", "Radau"), references, strict=True):
        errors[name] = compare_reference(baseline.observations, expected)
        evidence(
            "reference-" + name,
            {"rhs_calls": expected["rhs_calls"]},
            {k: v for k, v in expected.items() if k != "rhs_calls"},
        )
    for field in model.State._fields:
        np.testing.assert_allclose(
            references[0][field], references[1][field], rtol=2e-10, atol=5e-14
        )
    convergence = []
    for dt in (0.00005, 0.000025, 0.0000125):
        raw["execution"]["dt"] = dt
        result = baseline if dt == 0.000025 else run(parse_spec(raw))
        convergence.append(
            float(
                np.max(
                    np.abs(
                        result.observations.amount_increment[:, :, :2]
                        - references[0]["amount_increment"]
                    )
                )
            )
        )
    assert convergence[1] < convergence[0] / 6 and convergence[2] < convergence[1] / 6
    evidence(
        "independent-reference",
        {
            "status": "passed",
            "max_errors": errors,
            "steps_s": [0.00005, 0.000025, 0.0000125],
            "refinement_errors_fmol": convergence,
        },
    )


@pytest.mark.parametrize(
    "variant", ["pump_off", "release_off", "reaction_only", "passive_only", "release_event"]
)
def test_route_interventions_and_chemistry_reduction(baseline, variant):
    raw = data()
    c = raw["experiment"]["controls"][0]
    if variant in ("pump_off", "passive_only"):
        c["pump"] = 0
    if variant in ("release_off", "passive_only"):
        c["release"] = 0
    if variant == "passive_only":
        c["reactions"] = {key: 0 for key in c["reactions"]}
    if variant == "reaction_only":
        raw["model"]["membrane"]["pump"] = None
        raw["model"]["membrane"]["release"] = None
        raw["model"]["membrane"]["permeability_m_per_s"] = {key: 0 for key in c["passive"]}
    if variant == "release_event":
        c["release"] = 0
        raw["experiment"]["controls"].append(copy.deepcopy(c) | {"time": 0.00613, "release": 1})
        raw["experiment"]["observation_times"] = [0, 0.00613, 0.0062, 0.01237, 0.02]
    spec = parse_spec(raw)
    result = run(spec)
    if variant == "reaction_only":
        original = run(chemistry_spec(spec))
        for field in original.history._fields:
            np.testing.assert_allclose(
                getattr(result.history, field),
                getattr(original.history, field),
                rtol=3e-10,
                atol=3e-13,
            )
        assert np.all(result.history.passive_transferred == 0)
        assert np.all(result.history.pump_transferred == 0)
        assert np.all(result.history.release_transferred == 0)
    else:
        compare_reference(result.observations, reference(raw, result.observations.times))
    if variant == "pump_off":
        assert np.all(result.history.pump_transferred == 0)
        assert (
            result.observations.concentration_mM[-1, 1, 0]
            > baseline.observations.concentration_mM[-1, 1, 0]
        )
    if variant == "release_off":
        assert np.all(result.history.release_transferred == 0)
        assert (
            result.observations.concentration_mM[-1, 1, 0]
            < baseline.observations.concentration_mM[-1, 1, 0]
        )
    if variant == "release_event":
        assert np.all(result.observations.release_transferred[:2] == 0)
        evidence("controls", {"status": "passed", "release_at_s": 0.00613})


def test_complete_restart_windows_partitions_and_future_branch(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    specs = []
    for scale in (0.8, 1, 1.2):
        variant = copy.deepcopy(raw)
        variant["model"]["membrane"]["pump"]["capacity_fmol_per_s"] *= scale
        specs.append(parse_spec(variant))
    cohort = parse_batch(definition(specs, ids=[17, 31, 90]).to_dict())
    full = run_batch(cohort)
    starts = full.checkpoint_at({17: 0.00025, 31: 0.0005, 90: 0.001})
    write_batch_snapshot(tmp_path / "restart", cohort, starts)
    saved = load_batch_snapshot(tmp_path / "restart")
    for world in cohort.worlds:
        equal(run(world.simulation).final.state, full.worlds[world.world_id].final.state)
        equal(
            run_windowed(world.simulation, WindowPolicy(7)).final.state,
            full.worlds[world.world_id].final.state,
        )
    endpoints = {}
    for width in (1, 2, 3):
        for start in range(0, 3, width):
            part = replace(saved.spec, worlds=saved.spec.worlds[start : start + width])
            result = run_batch_windowed(
                part,
                WindowPolicy(9),
                {w.world_id: saved.checkpoints[w.world_id] for w in part.worlds},
            )
            for identity, checkpoint in result.checkpoints.items():
                equal(checkpoint.state, full.worlds[identity].final.state)
                for field, value in zip(checkpoint.state._fields, checkpoint.state, strict=True):
                    endpoints[f"width_{width}_world_{identity}_{field}"] = np.asarray(value)
    changed = specs[0].to_dict()
    c = changed["experiment"]["controls"][0]
    changed["experiment"]["controls"].append(
        {
            "time": starts[17].time,
            "pump": 0,
            "release": 0,
            "passive": {k: 0 for k in c["passive"]},
            "reactions": {k: 0 for k in c["reactions"]},
        }
    )
    changed = parse_spec(changed)
    branched = run(changed, branch_checkpoint(specs[0], starts[17], changed))
    equal(branched.final.state, starts[17].state)
    terminal = run(specs[2], full.worlds[90].final)
    equal(terminal.final.state, full.worlds[90].final.state)
    evidence(
        "replay", {"status": "passed", "widths": [1, 2, 3], "world_ids": [17, 31, 90]}, endpoints
    )


def test_domain_ledgers_and_checkpoint_corruption(baseline, tmp_path):
    state = model.State(*(np.array(v) for v in baseline.final.state))
    state.amount_increment[1, 1] += 0.1
    assert not bool(model.domain_valid(state, baseline.final.layout, baseline.final.layout.active))
    with pytest.raises(NumericalError, match="domain"):
        validate_checkpoint(baseline.spec, replace(baseline.final, state=state))
    state = model.State(*(np.array(v) for v in baseline.final.state))
    state.transport_dissipated_energy_pJ[1] += 1e-5
    with pytest.raises(NumericalError, match="energy balance"):
        validate_checkpoint(baseline.spec, replace(baseline.final, state=state))
    write_snapshot(tmp_path / "corrupt", baseline.spec, baseline.final)
    with (tmp_path / "corrupt/state.npz").open("ab") as handle:
        handle.write(b"corrupted")
    with pytest.raises(ConfigError, match="checksum"):
        load_snapshot(tmp_path / "corrupt")


def test_public_cli_and_selected_backend(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.0001, observation_times=[0, 0.000037, 0.0001])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw))
    child = subprocess.run(
        [sys.executable, "-B", "-m", "cells", "run", str(path), "--output", str(tmp_path / "run")],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert not child.stderr
    saved = load_snapshot(tmp_path / "run/checkpoint_final")
    assert saved.spec.execution.backend == BACKEND and saved.checkpoint.time == 0.0001
    evidence("public-cli", {"status": "passed", "backend": BACKEND})


def test_cpu_gpu_agreement(baseline):
    if BACKEND != "gpu":
        pytest.skip("CPU baseline retained for the subsequent GPU comparison")
    target = os.environ.get("CELLS_ER_EVIDENCE")
    if target:
        with np.load(Path(target) / "cpu/baseline.npz") as archive:
            expected = dict(archive)
    else:
        raw = data()
        raw["execution"]["backend"] = "cpu"
        result = run(parse_spec(raw))
        expected = dict(zip(result.history._fields, result.history, strict=True))
    count, error = 0, 0.0
    for field, values in zip(baseline.history._fields, baseline.history, strict=True):
        np.testing.assert_allclose(values, expected[field], rtol=3e-10, atol=3e-13)
        count += values.size
        error = max(error, float(np.max(np.abs(values - expected[field]))))
    evidence(
        "cpu-gpu",
        {
            "status": "passed",
            "scalar_values_compared": count,
            "max_absolute_error": error,
            "rtol": 3e-10,
            "atol": 3e-13,
        },
    )
