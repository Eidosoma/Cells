"""Closed chemistry: independent physics, ownership, strict replay and real CPU/GPU runs."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import parse_batch, run_batch
from cells.core.batch_windows import run_batch_windowed
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, run_windowed
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import compartment_reactions as model
from cells.processes.mass_action import reversible_flux
from tests.batch_fixtures import definition
from tests.reference_compartment_reactions import binding_equilibrium, reference

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_CHEMISTRY_TEST_BACKEND", "cpu")


def data():
    raw = json.loads((ROOT / "configs/calcium_buffer_compartments.json").read_text())
    raw["execution"]["backend"] = BACKEND
    return raw


def evidence(name, record=None, arrays=None):
    target = os.environ.get("CELLS_CHEMISTRY_EVIDENCE")
    if target is None:
        return
    path = Path(target) / BACKEND
    path.mkdir(parents=True, exist_ok=True)
    if record is not None:
        (path / (name + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    if arrays is not None:
        np.savez(path / (name + ".npz"), **arrays)


def state_equal(a, b):
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


def controls(raw, values, time=0):
    return {"time": time, "multipliers": {r["id"]: values for r in raw["model"]["reactions"]}}


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


def test_roundtrip_canonical_order_layout_and_public_artifacts(baseline, tmp_path):
    raw = data()
    for name in ("species", "moieties", "compartments", "reactions"):
        raw["model"][name].reverse()
    assert parse_spec(raw) == baseline.spec == parse_spec(baseline.spec.to_dict())
    assert parse_spec(raw).fingerprint == baseline.spec.fingerprint
    layout = baseline.final.layout
    np.testing.assert_array_equal(layout.ids, [0, 1, -1])
    assert baseline.history.amount_increment.shape == (401, 4, 3)
    assert baseline.history.reaction_extent.shape == (401, 6)
    assert np.all(baseline.observations.amount[:, :, 2] == 0)
    assert np.all(baseline.history.reaction_extent[:, 4:] == 0)
    summary = write_run(tmp_path / "public", baseline)
    assert summary["active_compartments"] == 2
    restored = load_snapshot(tmp_path / "public/checkpoint_final")
    state_equal(restored.checkpoint.state, baseline.final.state)
    manifest = json.loads((tmp_path / "public/manifest.json").read_text())
    assert manifest["observer"]["id"] == model.OBSERVER_ID
    assert manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "law"), "irreversible"),
        (("model", "species", 0, "valence"), True),
        (("model", "species", 0, "valence"), 1),
        (("model", "species", 0, "moieties", "calcium"), 2),
        (("model", "species", 0, "standard_mu_RT"), float("nan")),
        (("model", "compartments", 0, "volume_pL"), 0),
        (("model", "compartments", 0, "initial_amount_fmol", "Ca"), 0),
        (("model", "compartments", 0, "initial_amount_fmol", "Ca"), -1),
        (("model", "reactions", 0, "compartment"), "absent"),
        (("model", "reactions", 0, "compartment"), []),
        (("model", "reactions", 0, "products"), {"CaB": 2}),
        (("model", "reactions", 0, "reactants"), {"Ca": True, "B": 1}),
        (("model", "reactions", 0, "forward_rate_per_s"), -1),
        (("experiment", "reaction_controls", 0, "time"), 0.01),
        (("experiment", "observation_times"), [0, 0.2]),
        (("execution", "reaction_capacity"), 3),
        (("execution", "capacity"), 1),
        (("execution", "solver"), "euler"),
        (("execution", "precision"), "float32"),
    ],
)
def test_invalid_chemical_definitions(path, value):
    raw = data()
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_controls_and_unknown_fields_are_strict():
    raw = data()
    raw["model"]["reactions"][0]["reverse_rate_per_s"] = 2
    with pytest.raises(ConfigError):
        parse_spec(raw)
    raw = data()
    raw["experiment"]["reaction_controls"] = [controls(raw, 1.1)]
    with pytest.raises(ConfigError):
        parse_spec(raw)
    raw["experiment"]["reaction_controls"] = [controls(raw, 1), controls(raw, 0)]
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_readonly_observations_and_named_padding_preserve_dynamics(baseline):
    raw = data()
    raw["experiment"]["observation_times"] = [0, 0.000001, 0.00337, 0.08137, 0.1]
    sampled = run(parse_spec(raw))
    state_equal(sampled.history, baseline.history)
    raw["execution"].update(capacity=2, reaction_capacity=4)
    # Change sorting order as well as physical labels, retaining the named graph.
    species = {s["id"]: "s" + str(9 - i) for i, s in enumerate(raw["model"]["species"])}
    for s in raw["model"]["species"]:
        s["id"] = species[s["id"]]
    for c in raw["model"]["compartments"]:
        c["initial_amount_fmol"] = {species[s]: n for s, n in c["initial_amount_fmol"].items()}
    for r in raw["model"]["reactions"]:
        for side in ("reactants", "products"):
            r[side] = {species[s]: n for s, n in r[side].items()}
    changed = run(parse_spec(raw))
    indices = [sorted(species.values()).index(species[s.id]) for s in baseline.spec.model.species]
    np.testing.assert_allclose(
        changed.history.amount_increment[:, indices],
        baseline.history.amount_increment[:, :, :2],
        rtol=3e-10,
        atol=3e-13,
    )


def test_stage_polynomial_rates_local_ownership_and_chemical_work():
    spec = parse_spec(data())
    state, layout = model.initial_values(spec)
    slope = model.rhs(state, control_values(spec, [0])[0], layout, layout.active, xp=np)
    # First binding in cytosol_0: V*kf*(Ca/V)*(B/V) - kr*CaB.
    slot = [r.id for r in spec.model.reactions].index("bind_0_first")
    assert slope.reaction_extent[slot] == pytest.approx(0.045, abs=1e-15)
    chemical_potential = layout.standard_mu_RT[:, None] + np.log(
        layout.initial_amount / layout.volume / layout.standard_concentration
    )
    dg = (
        8.31446261815324
        * spec.model.temperature_K
        * 1e-3
        * np.sum(chemical_potential * slope.amount_increment, axis=0)
    )
    np.testing.assert_allclose(
        dg + slope.dissipated_energy_pJ @ layout.owner_matrix, 0, rtol=0, atol=1e-15
    )
    np.testing.assert_allclose(layout.moieties @ slope.amount_increment, 0, atol=1e-17)
    assert np.all(slope.dissipated_energy_pJ >= 0)
    assert model.loss_bound(spec) * spec.execution.dt < 0.25
    with pytest.raises(ConfigError, match="bounded loss rate"):
        timeline(replace(spec, execution=replace(spec.execution, dt=0.01)))


def test_near_equilibrium_flux_sign_and_closed_form():
    activity = np.array([[1.0], [1.0 + 1e-12]])
    flux, affinity = reversible_flux(
        activity, np.array([[1], [0]]), np.array([[0], [1]]), np.zeros(1), np.ones(1), xp=np
    )
    assert flux[0] < 0 and affinity[0] < 0
    np.testing.assert_allclose(flux, 1.0 - activity[1], rtol=2e-15, atol=0)
    free_ca, free_b, bound = binding_equilibrium(0.013, 0.06, 0.001)
    assert free_ca * free_b / bound == pytest.approx(0.001, rel=2e-14)
    raw = data()
    raw["model"]["species"] = [s for s in raw["model"]["species"] if s["id"] != "Ca2B"]
    raw["model"]["compartments"] = [
        {
            "id": "cytosol_0",
            "volume_pL": 0.5,
            "initial_amount_fmol": {"Ca": 0.5 * free_ca, "B": 0.5 * free_b, "CaB": 0.5 * bound},
        }
    ]
    raw["model"]["reactions"] = [raw["model"]["reactions"][0]]
    raw["experiment"]["reaction_controls"] = [controls(raw, 1)]
    result = run(parse_spec(raw))
    assert np.max(np.abs(result.history.amount_increment)) < 1e-16
    assert np.max(result.history.dissipated_energy_pJ) < 1e-28


def test_independent_references_and_refinement(baseline):
    raw = data()
    refs = [reference(raw, baseline.observations.times, method=m) for m in ("DOP853", "Radau")]
    errors = []
    for method, ref in zip(("DOP853", "Radau"), refs, strict=True):
        for name, actual in (
            ("amount", baseline.observations.amount[:, :, :2]),
            ("reaction_extent", baseline.observations.reaction_extent[:, :4]),
            ("dissipated_energy_pJ", baseline.observations.dissipated_energy_pJ[:, :4]),
        ):
            np.testing.assert_allclose(actual, ref[name], rtol=3e-9, atol=3e-12)
        evidence(
            "reference-" + method,
            {"rhs_calls": ref["rhs_calls"]},
            {k: v for k, v in ref.items() if k != "rhs_calls"},
        )
    np.testing.assert_allclose(refs[0]["amount"], refs[1]["amount"], rtol=2e-11, atol=3e-14)
    for dt in (0.0005, 0.00025, 0.000125):
        raw["execution"]["dt"] = dt
        result = baseline if dt == 0.00025 else run(parse_spec(raw))
        errors.append(
            float(np.max(np.abs(result.observations.amount[:, :, :2] - refs[0]["amount"])))
        )
        assert result.diagnostics["max_energy_balance_error_pJ"] < model.ENERGY_ATOL_PJ
    assert errors[1] < errors[0] / 8
    assert errors[2] < errors[1] / 8
    evidence(
        "independent-reference",
        {
            "status": "passed",
            "refinement_amount_errors_fmol": errors,
            "steps_s": [0.0005, 0.00025, 0.000125],
        },
    )


@pytest.mark.parametrize(
    "variant", ["blocked", "zero_rate", "no_reactions", "isolation", "release"]
)
def test_controls_reductions_and_compartment_isolation(baseline, variant):
    raw = data()
    if variant == "no_reactions":
        raw["model"]["reactions"] = []
        raw["execution"]["reaction_capacity"] = 0
    if variant == "zero_rate":
        for reaction in raw["model"]["reactions"]:
            reaction["forward_rate_per_s"] = 0
    raw["experiment"]["reaction_controls"] = [controls(raw, 0 if variant == "blocked" else 1)]
    if variant == "isolation":
        raw["model"]["compartments"][0]["initial_amount_fmol"]["Ca"] *= 1.5
    if variant == "release":
        raw["experiment"]["reaction_controls"] = [
            controls(raw, 0),
            controls(raw, 0.5, 0.03113),
            controls(raw, 1, 0.05317),
        ]
        raw["experiment"]["observation_times"] = [0, 0.02037, 0.03113, 0.0312, 0.05317, 0.1]
    result = run(parse_spec(raw))
    if variant in ("blocked", "zero_rate", "no_reactions"):
        assert all(np.all(v == 0) for v in result.history)
    elif variant == "isolation":
        np.testing.assert_array_equal(
            result.history.amount_increment[:, :, 1], baseline.history.amount_increment[:, :, 1]
        )
        assert not np.array_equal(
            result.history.amount_increment[:, :, 0], baseline.history.amount_increment[:, :, 0]
        )
    else:
        assert np.all(result.observations.amount_increment[:3] == 0)
        expected = reference(raw, result.observations.times)
        np.testing.assert_allclose(
            result.observations.amount[:, :, :2], expected["amount"], rtol=3e-9, atol=3e-12
        )
        evidence(
            "controls",
            {"status": "passed", "blocked_until_s": 0.03113, "restarted_at_full_rate_s": 0.05317},
        )


def test_finite_multimerization_and_catalyst():
    raw = data()
    raw["model"]["moieties"] = ["material", "catalyst"]
    raw["model"]["species"] = [
        {
            "id": s,
            "valence": 0,
            "moieties": {"material": material, "catalyst": catalyst},
            "standard_mu_RT": mu,
        }
        for s, material, catalyst, mu in (("A", 1, 0, 0), ("A2", 2, 0, -2), ("E", 0, 1, 0))
    ]
    raw["model"]["compartments"] = [
        {
            "id": "vessel",
            "volume_pL": 0.5,
            "initial_amount_fmol": {"A": 0.01, "A2": 0.003, "E": 0.01},
        }
    ]
    raw["model"]["reactions"] = [
        {
            "id": "dimer",
            "compartment": "vessel",
            "reactants": {"A": 2, "E": 1},
            "products": {"A2": 1, "E": 1},
            "forward_rate_per_s": 100,
        }
    ]
    raw["experiment"]["reaction_controls"] = [controls(raw, 1)]
    result = run(parse_spec(raw))
    expected = reference(raw, result.observations.times)
    np.testing.assert_allclose(
        result.observations.amount[:, :, :1], expected["amount"], atol=3e-12, rtol=3e-9
    )
    assert np.all(result.history.amount_increment[:, 2] == 0)


def test_domain_conservation_and_corrupt_checkpoint_refusal(baseline, tmp_path):
    initial = initialise(baseline.spec)
    bad = model.State(*(np.array(v) for v in initial.state))
    bad.amount_increment[0, 0] = -float(initial.layout.initial_amount[0, 0])
    assert not bool(model.domain_valid(bad, initial.layout, initial.layout.active))
    with pytest.raises(NumericalError, match="Nonpositive"):
        model.check_values(bad, baseline.spec)
    bad = model.State(*(np.array(v) for v in baseline.final.state))
    bad.reaction_extent[0] += 1e-6
    with pytest.raises(NumericalError, match="reaction ledger"):
        validate_checkpoint(baseline.spec, replace(baseline.final, state=bad))
    write_snapshot(tmp_path / "corrupt", baseline.spec, baseline.final)
    with (tmp_path / "corrupt/state.npz").open("ab") as handle:
        handle.write(b"corrupted")
    with pytest.raises(ConfigError, match="checksum"):
        load_snapshot(tmp_path / "corrupt")


def test_complete_restart_branch_windows_partitions_and_world_isolation(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.01, observation_times=[0, 0.00437, 0.01])
    specs = []
    for i in range(3):
        variant = copy.deepcopy(raw)
        variant["model"]["compartments"][0]["initial_amount_fmol"]["Ca"] *= 1 + 0.1 * i
        specs.append(parse_spec(variant))
    cohort = parse_batch(definition(specs, ids=[17, 31, 90]).to_dict())
    full = run_batch(cohort)
    for world in cohort.worlds:
        scalar = run(world.simulation)
        state_equal(full.worlds[world.world_id].final.state, scalar.final.state)
        windowed = run_windowed(world.simulation, WindowPolicy(7))
        state_equal(windowed.final.state, scalar.final.state)
    starts = full.checkpoint_at({17: 0.003, 31: 0.005, 90: 0.01})
    write_batch_snapshot(tmp_path / "restart", cohort, starts)
    saved = load_batch_snapshot(tmp_path / "restart")
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
                state_equal(checkpoint.state, full.worlds[identity].final.state)
                for name, value in zip(checkpoint.state._fields, checkpoint.state, strict=True):
                    endpoints[f"width_{width}_world_{identity}_{name}"] = np.asarray(value)
    checkpoint = starts[17]
    changed = specs[0].to_dict()
    changed["experiment"]["reaction_controls"].append(controls(changed, 0, checkpoint.time))
    changed = parse_spec(changed)
    branch = branch_checkpoint(specs[0], checkpoint, changed)
    halted = run(changed, branch)
    state_equal(halted.final.state, checkpoint.state)
    terminal = run(specs[2], full.worlds[90].final)
    state_equal(terminal.final.state, full.worlds[90].final.state)
    evidence(
        "replay", {"status": "passed", "widths": [1, 2, 3], "world_ids": [17, 31, 90]}, endpoints
    )


def test_public_cli_executes_selected_backend_and_complete_checkpoint(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    config = tmp_path / "config.json"
    config.write_text(json.dumps(raw))
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "cells",
            "run",
            str(config),
            "--output",
            str(tmp_path / "run"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert not result.stderr
    final = load_snapshot(tmp_path / "run/checkpoint_final")
    assert final.spec.execution.backend == BACKEND and final.checkpoint.time == 0.001
    evidence("public-cli", {"status": "passed", "backend": BACKEND})


def test_cpu_gpu_agreement(baseline):
    if BACKEND != "gpu":
        pytest.skip("CPU baseline retained; comparison requires the subsequent real GPU phase")
    target = os.environ.get("CELLS_CHEMISTRY_EVIDENCE")
    if target:
        with np.load(Path(target) / "cpu/baseline.npz") as archive:
            expected = dict(archive)
    else:
        raw = data()
        raw["execution"]["backend"] = "cpu"
        cpu = run(parse_spec(raw))
        expected = dict(zip(cpu.history._fields, cpu.history, strict=True))
    compared, max_error = 0, 0.0
    for name, values in zip(baseline.history._fields, baseline.history, strict=True):
        np.testing.assert_allclose(values, expected[name], rtol=3e-10, atol=3e-13)
        compared += values.size
        max_error = max(max_error, float(np.max(np.abs(values - expected[name]))))
    evidence(
        "cpu-gpu",
        {
            "status": "passed",
            "scalar_values_compared": compared,
            "max_absolute_error": max_error,
            "rtol": 3e-10,
            "atol": 3e-13,
        },
    )
