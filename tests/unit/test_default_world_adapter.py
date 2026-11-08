"""Synthetic checks of the BETSE default-world adapter (no BETSE; tiny emulator runs)."""

import copy
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

from validation.betse import betse_reference_extract as ex
from validation.betse import cells_betse_compare as cmp
from validation.betse import default_world_adapter as adapter
from validation.betse.emulator import active, laws

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation/betse/protocols/emulator_default_world_dense.json"
SPECIES, VALENCE = ["Na", "K", "P", "M"], [1, 1, -1, -1]
CELL, ENV = [12.0, 139.0, 135.0, 16.0], [145.0, 5.0, 10.0, 140.0]
FREE = np.array([1.33e-9, 1.96e-9, 0.0, 1e-9])
DM = np.array([2e-18, 1e-18, 0.0, 1e-18])
ROWS = COLS = 4
OWNER, SITE = np.array([0, 0, 0, 1, 1, 1]), np.array([5, 6, 9, 6, 10, 9])
PARTNER = np.array([0, 4, 2, 3, 1, 5])  # membranes 1 and 4 form the only gap junction
AREA = np.array([1e-10, 2e-10, 1.5e-10, 1.2e-10, 2e-10, 1.1e-10])
STEPS, DT = {"init": 4, "sim": 3}, {"init": 1e-3, "sim": 1e-4}
PARAMS = {
    "F": 96485, "R": 8.314, "NAv": 6.022e23, "q": 1.602e-19, "kb": 1.3806e-23,
    "eo": 8.854e-12, "er": 80.0, "T": 310.0, "cm": 0.05, "tm": 7.5e-9, "gj_surface": 5e-8,
    "gj_vthresh": 15.0, "gj_min": 0.1, "alpha_NaK": 1e-7, "cATP": 1.5, "cADP": 0.1,
    "cPi": 0.1, "KmNK_Na": 12.0, "KmNK_K": 0.2, "KmNK_ATP": 0.5, "deltaGATP": -37000,
    "cell_height": 1e-5, "true_cell_size": 1e-5,
    "cell_concs": dict(zip(SPECIES, CELL, strict=True)),
    "env_concs": dict(zip(SPECIES, ENV, strict=True)),
    **adapter.REQUIRED_PARAMS,
}  # fmt: skip
KEYED = {"cell_radius": 5e-6, "is_ecm": True, "cell_polarizability": 0.0}


def write_case(directory, *, params=None, dm_history=None):
    """A complete synthetic extraction with BETSE's array names, axes and units."""
    directory.mkdir()
    s, m, o = len(SPECIES), AREA.size, ROWS * COLS
    geometry = {
        "cell_vol": (np.array([5e-16, 6e-16]), "m^3"),
        "mem_sa": (AREA, "m^2"),
        "mem_to_cells": (OWNER, "index"),
        "map_mem2ecm": (SITE, "index"),
        "nn_i": (PARTNER, "index"),
        "gj_default_weights": (np.ones(m), "1"),
        "X": (np.zeros((ROWS, COLS)), "m"),
        "delta": (np.asarray(1e-5), "m"),
        "gj_len": (np.asarray(2.6e-8), "m"),
    }
    files = {
        "geometry.npz": ex.write_npz(
            directory / "geometry.npz", {k: (v, {"units": u}) for k, (v, u) in geometry.items()}
        )
    }
    rng = np.random.default_rng(1)
    time, scalars, all_params = {}, {}, {}
    debye = (
        PARAMS["NAv"]
        * PARAMS["q"] ** 2
        * np.square(VALENCE)
        / (80.0 * 8.854e-12 * 1.3806e-23 * 310)
    )
    start_env = np.repeat(np.array(ENV)[:, None], o, axis=1)  # INIT starts from env_concs
    for phase in adapter.PHASES:
        n = STEPS[phase]
        env = np.repeat(np.array(ENV)[:, None], o, axis=1) * (1 + 1e-6 * rng.random((s, o)))
        cell = np.repeat(np.array(CELL)[:, None], 2, axis=1)
        final = {
            "Dm_cells": np.repeat(DM[:, None], m, axis=1),
            "D_env": np.repeat(FREE[:, None], o, axis=1),
            "D_gj": np.repeat(FREE[:, None], m, axis=1),
            "cc_cells": cell,
            "cc_at_mem": cell[:, OWNER],
            "cc_env": env,
            "gjopen": np.full(m, 0.97),
            "vm": np.full(m, -0.02),
            "vm_ave": np.full(2, -0.02),
            "v_env": np.zeros(o),
        }
        files[f"{phase}_final.npz"] = ex.write_npz(
            directory / f"{phase}_final.npz", {k: (v, {"units": "x"}) for k, v in final.items()}
        )
        dd = np.repeat(final["Dm_cells"][None], n, axis=0) if dm_history is None else dm_history
        history = {
            "dd_time": (dd, ["samples", "ions", "membranes"], "m^2/s"),
            "vm_time": (np.full((n, m), -0.02), ["samples", "membranes"], "V"),
            "vm_ave_time": (np.full((n, 2), -0.02), ["samples", "cells"], "V"),
            "cc_time": (np.repeat(cell[None], n, axis=0), ["samples", "ions", "cells"], "mol/m^3"),
            "cc_env_time": (np.repeat(env[None], n, axis=0), ["samples", "ions", "env"], "mol/m^3"),
            "venv_time": (np.zeros((n, o)), ["samples", "ECM grid points"], "V"),
        }
        files[f"{phase}_history.npz"] = ex.write_npz(
            directory / f"{phase}_history.npz",
            {k: (v, {"axes": a, "units": u}) for k, (v, a, u) in history.items()},
        )
        time[phase] = {
            "elapsed_after_update_s": [(k + 1) * DT[phase] for k in range(n)],
            "final_state_elapsed_s": n * DT[phase],
            "n_steps": n,
        }
        scalars[phase] = {
            "scalars": {
                "NaKATP_block": 1,
                "gj_block": 1,
                "bound_V": {"T": 0, "B": 0, "L": 0, "R": 0},
                "movingIons": [0, 1, 2, 3],
                "c_env_bound": ENV,
                "ko_env": float(np.sqrt(debye @ start_env).mean()),
            }
        }
        all_params[phase] = {**PARAMS, "dt": DT[phase], **(params or {})}
        start_env = env  # SIM starts from init_final
    manifest = {
        "kind": ex.KIND,
        "status": "complete",
        "files": files,
        "time": time,
        "ions": {"order": SPECIES, "valence": VALENCE},
        "final_state": scalars,
        "parameters": {
            "all_simple_attributes": all_params,
            "key": {p: {k: {"value": v} for k, v in KEYED.items()} for p in adapter.PHASES},
        },
        "source_run": {"case": "synthetic"},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory


@pytest.fixture(scope="module")
def case(tmp_path_factory):
    return write_case(tmp_path_factory.mktemp("adapter") / "betse")


def test_world_maps_betse_arrays_with_units(case):
    world = adapter.betse_world(case)
    assert world["species"] == SPECIES and world["grid_shape"] == (ROWS, COLS)
    np.testing.assert_array_equal(world["membrane_permeability_m_s"]["init"][:, 0], DM / 7.5e-9)
    np.testing.assert_allclose(world["junction_permeability_m_s"][:, 1], FREE * 5e-8 / 2.6e-8)
    np.testing.assert_allclose(world["pump_capacity_fmol_s"], 1e-7 * AREA * 1e15)
    assert world["gate_threshold_V"] == pytest.approx(0.015) and world["gate_minimum_open"] == 0.1
    assert world["cell_size_ratio"] == 0.5 and world["site_volume_m3"] == pytest.approx(1e-15)
    assert world["ring_sites"].tolist() == [0, 1, 2, 3, 4, 7, 8, 11, 12, 13, 14, 15]
    for phase in adapter.PHASES:
        start = adapter.phase_start(world, phase)
        assert adapter.screening_wavenumber(world, start["env_mM"]) == pytest.approx(
            world["betse_ko_env"][phase], rel=1e-14
        )
    assert set(adapter.WORLD_UNITS) <= set(world) | {"species"}


@pytest.mark.parametrize(
    "change",
    [
        {"params": {"fluid_flow": True}},
        {"params": {"cell_polarizability": 0.5}},
        {"dm_history": np.zeros((STEPS["init"], 4, AREA.size))},
    ],
)
def test_unmapped_betse_features_are_refused(tmp_path, change):
    if "params" in change and "cell_polarizability" in change["params"]:
        directory = write_case(tmp_path / "betse")
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["parameters"]["key"]["init"]["cell_polarizability"] = {"value": 0.5}
        (directory / "manifest.json").write_text(json.dumps(manifest))
    else:
        directory = write_case(tmp_path / "betse", **change)
    with pytest.raises(adapter.AdapterError):
        adapter.betse_world(directory)


def test_layout_phase_follows_betse_sampling_and_cell_means(case):
    world = adapter.betse_world(case)
    vm = np.arange(2 * AREA.size, dtype=float).reshape(2, AREA.size)
    cell, env = np.ones((2, 4, 2)), np.ones((2, 4, ROWS * COLS))
    phase = adapter.layout_phase(world, [0.01, 0.02], vm, cell, env, np.zeros((2, ROWS * COLS)))
    assert phase["elapsed_after_update_s"] == [0.01, 0.02] and phase["final_elapsed_s"] == 0.02
    np.testing.assert_array_equal(phase["history"]["vm_ave_time"][1], [7.0, 10.0])
    np.testing.assert_array_equal(phase["final"]["vm"], vm[-1])
    assert set(phase["final"]) == set(cmp.SUPPORTED.values())
    with pytest.raises(adapter.AdapterError):
        adapter.layout_phase(world, [0.01], vm, cell, env, np.zeros((2, ROWS * COLS)))


def test_resolved_observations_follow_the_physical_route_mapping(case):
    world = adapter.betse_world(case)
    raw = adapter.resolved_definition(world, "init", adapter.phase_start(world, "init"), dt=1e-3)
    cells_pL = np.array([c["volume_pL"] for c in raw["model"]["cells"]])
    padded, o, m = 3, ROWS * COLS, AREA.size  # observation slots may exceed the routes
    increment = np.zeros((3, 4, 2 + padded))
    increment[1:, 0, 0] = 1e-3  # +1 amol Na in cell 0 after the first sample
    observations = {
        "times": np.array([0.0, 2e-3, 4e-3]),
        "amount_increment": increment,
        "amount": np.full((3, 4, 2 + padded), 5.0) * np.append(cells_pL, np.ones(padded)),
        "extracellular_amount": np.full((3, 4, o), 2.0),
        "extracellular_amount_increment": np.zeros((3, 4, o)),
        "membrane_voltage_V": np.full((3, m + padded), -0.02),
        "cell_potential_V": np.zeros((3, 2 + padded)),
        "extracellular_potential_V": np.zeros((3, o)),
        "junction_gate": np.ones((3, 1 + padded)),
        "charge_residual_C": np.zeros((3, 2)),
        "component_current_residual_A": np.zeros((3, 2)),
    }
    phase = adapter.resolved_layout_phase(world, raw, observations)
    history = phase["history"]
    assert phase["elapsed_after_update_s"] == [2e-3, 4e-3] and phase["final_elapsed_s"] == 4e-3
    np.testing.assert_allclose(history["cc_time"], 5.0)
    np.testing.assert_allclose(history["cc_env_time"], 2.0)  # site volume 1 pL
    capacitance = 0.05 * AREA[OWNER == 0].sum()  # C_patch = cm * mem_sa
    expected = 96485.33212331001e-15 * 1e-3 / capacitance  # Q_cell / sum(C_patch)
    np.testing.assert_allclose(history["vm_ave_time"][:, 0], expected, rtol=1e-12)
    np.testing.assert_array_equal(history["vm_time"], history["vm_ave_time"][:, OWNER])
    assert "venv_time" not in history and history["diag_patch_voltage_time"].shape == (2, m)
    assert phase["final"]["diag_extracellular_potential"].shape == (o,)
    assert adapter._isolated_sites(raw).tolist() == []  # every interior site faces a membrane
    check = adapter.patch_exterior_check(world, phase)
    assert check["x_ext_V"] == pytest.approx(0.02 + expected) and check["at"]["cell"] == 0
    assert check["max_abs_exterior_potential_at_patches_V"] == 0.0 and check["samples"] == 2


def test_blind_world_reads_no_betse_history_or_end_state(case, tmp_path):
    blind = tmp_path / "blind"
    shutil.copytree(case, blind)
    for name in ("init_history.npz", "sim_history.npz", "sim_final.npz"):
        (blind / name).unlink()
    world = adapter.betse_world(blind, blind=True)
    assert world["init_final"] is None
    np.testing.assert_array_equal(
        world["membrane_permeability_m_s"]["sim"],
        adapter.betse_world(case)["membrane_permeability_m_s"]["sim"],
    )
    with pytest.raises(adapter.AdapterError):
        adapter.phase_start(world, "sim", "betse")


def test_channel_free_variant_replaces_the_kv1p5_temperature_guard(case):
    world = adapter.betse_world(case)
    start = adapter.phase_start(world, "init")
    variant = laws.default_world("betse")
    state, layout, _ = adapter.emulator_inputs(world, "init", start, variant)
    with pytest.raises(ValueError, match="298.15 K"):
        active.validate_layout(layout.active, variant=laws.QUALIFIED)
    with pytest.raises(ValueError, match="zero Kv1p5"):
        active.validate_layout(
            layout.active._replace(channel_permeability=np.full(AREA.size, 1e-9)), variant=variant
        )
    assert variant.max_grid_sites > laws.QUALIFIED.max_grid_sites
    assert (variant.faraday_C_mol, variant.gas_J_mol_K) == (96485.0, 8.314)


@pytest.fixture(scope="module")
def emulated(case, tmp_path_factory):
    root = tmp_path_factory.mktemp("emulated")
    protocol = root / "protocol.json"
    shutil.copyfile(PROTOCOL, protocol)
    record = adapter.run_emulator(
        case, protocol, root / "layout", constants="betse", device_kind="cpu", sim_start="betse"
    )
    return root, protocol, record


def test_emulator_run_writes_a_judgeable_layout(case, emulated):
    root, protocol, record = emulated
    assert record["valid"] and record["phases"]["sim"]["start"] == "betse"
    assert all(abs(r["ko_env_relative_difference"]) < 1e-14 for r in record["phases"].values())
    manifest = json.loads((root / "layout" / cmp.LAYOUT_MANIFEST).read_text())
    assert manifest["provenance"]["git_revision"] and "dirty" in manifest["provenance"]
    result = cmp.run_comparison(case, root / "layout", protocol)
    assert result["verdict"] in ("pass", "fail") and not result["refusals"]
    assert {p: r["common_samples"] for p, r in result["phases"].items()} == STEPS


def test_layout_pair_comparison_detects_a_difference(emulated, tmp_path):
    root, protocol, _ = emulated
    same = adapter.compare_layouts(root / "layout", root / "layout", protocol)
    assert same["verdict"] == "pass"
    assert all(r["max_abs"] == 0 for p in same["phases"].values() for r in p.values())
    other = tmp_path / "other"
    shutil.copytree(root / "layout", other)
    data = dict(np.load(other / "sim_history.npz"))
    data["vm_time"] = data["vm_time"].copy()
    data["vm_time"][1, 2] += 1e-8
    (other / "sim_history.npz").unlink()
    np.savez(other / "sim_history.npz", **data)
    changed = adapter.compare_layouts(root / "layout", other, protocol)
    assert changed["verdict"] == "fail"
    assert changed["phases"]["sim"]["history/vm_time"]["max_abs"] == pytest.approx(1e-8)


def test_dt_factor_keeps_betse_sampling_and_feeds_the_budget(case, emulated, tmp_path):
    root, protocol, _ = emulated
    record = adapter.run_emulator(
        case,
        protocol,
        tmp_path / "f2",
        constants="betse",
        device_kind="cpu",
        sim_start="chained",
        dt_factor=2,
    )
    assert record["valid"] and record["phases"]["init"]["updates"] == 2 * STEPS["init"]
    assert record["phases"]["sim"]["dt_s"] == pytest.approx(DT["sim"] / 2)
    world = adapter.betse_world(case)
    budget = adapter.layout_difference(world, root / "layout", tmp_path / "f2")
    for phase, row in budget["phases"].items():
        assert row["samples"] == STEPS[phase] and set(row["observables"]) == set(adapter.BUDGET)
        for obs in row["observables"].values():
            assert np.isfinite(obs["max"]) and np.isfinite(obs["final"]["max"])
            assert obs["elapsed_s"] in [(k + 1) * DT[phase] for k in range(STEPS[phase])]
    same = adapter.layout_difference(world, root / "layout", root / "layout")
    assert all(o["max"] == 0 for r in same["phases"].values() for o in r["observables"].values())


def test_chained_sim_starts_from_the_emulator_init_end(case, tmp_path):
    world = adapter.betse_world(case)
    end = {k: np.asarray(v) * 1.0 for k, v in world["init_final"].items()}
    end["gate_open"] = np.full(AREA.size, 0.5)
    start = adapter.phase_start(world, "sim", "chained", end)
    np.testing.assert_array_equal(start["gate_open"], 0.5)
    with pytest.raises(adapter.AdapterError):
        adapter.phase_start(world, "sim", "chained", None)


def test_resolved_definition_maps_nodes_patches_junctions_and_faces(case):
    world = adapter.betse_world(case)
    start = adapter.phase_start(world, "init")
    raw = adapter.resolved_definition(world, "init", start, dt=1e-3)
    model, execution = raw["model"], raw["execution"]
    assert model["id"] == adapter.RESOLVED_MODEL_ID
    assert model["closure"] == {"law": adapter.RESOLVED_CLOSURE, "gauge_reference": None}
    kinds = ("cells", "extracellular", "membranes", "junctions", "faces")
    assert [len(model[k]) for k in kinds] == [2, ROWS * COLS, AREA.size, 1, 12]
    assert sum(node["reservoir"] for node in model["extracellular"]) == 12
    junction = model["junctions"][0]
    assert (junction["sender"], junction["receiver"]) == ("cell-0", "cell-1")
    assert junction["permeability_m_per_s"]["K"] == pytest.approx(1.96e-9 * 5e-8 / 2.6e-8)
    assert junction["gate"]["threshold_voltage_V"] == pytest.approx(0.015)
    cell = model["cells"][1]
    assert cell["volume_pL"] == pytest.approx(0.6)
    assert cell["initial_amount_fmol"]["K"] == pytest.approx(139.0 * 0.6)
    for node in model["cells"] + model["extracellular"]:
        terms = [z * node["initial_amount_fmol"][s] for s, z in zip(SPECIES, VALENCE, strict=True)]
        fixed = node["fixed_charge_equivalent_fmol"]
        assert node["initial_charge_C"] == 96485.33212e-15 * math.fsum([fixed, *terms]) == 0.0
        assert abs(fixed) <= 1e-14 * math.fsum(abs(t) for t in terms)  # roundoff only
    charged = adapter.resolved_definition(world, "sim", adapter.phase_start(world, "sim"), dt=1e-4)
    node = charged["model"]["extracellular"][5]  # BETSE's init_final ECM keeps its net charge
    assert node["fixed_charge_equivalent_fmol"] == 0.0 and node["initial_charge_C"] != 0.0
    membrane = model["membranes"][1]
    assert membrane["outside"] == "ecm-6" and membrane["capacitance_F"] == pytest.approx(
        0.05 * 2e-10
    )
    assert membrane["pump"]["capacity_fmol_per_s"] == pytest.approx(1e-7 * 2e-10 * 1e15)
    face = model["faces"][0]
    assert face["area_m2"] == pytest.approx(1e-5 * 1e-5) and face["length_m"] == 1e-5
    assert execution["face_capacity"] == 12 and execution["edge_capacity"] == 1
    assert raw["experiment"]["end_time"] == pytest.approx(STEPS["init"] * DT["init"])
    assert adapter.junction_gate_dt_bound(world) == pytest.approx(
        0.125 / (1.3 * np.exp(77 * 0.015) + 20)
    )


def test_resolved_definition_refuses_a_dt_that_does_not_divide_the_phase(case):
    world = adapter.betse_world(case)
    start = adapter.phase_start(world, "init")
    with pytest.raises(adapter.AdapterError):
        adapter.resolved_definition(world, "init", start, dt=3e-3)
    world = copy.deepcopy(world)
    world["membrane_partner"] = np.array([1, 0, 2, 3, 4, 5])  # two membranes of one cell
    world["membrane_cell"] = np.array([0, 0, 0, 1, 1, 1])
    with pytest.raises(adapter.AdapterError):
        adapter.resolved_definition(world, "init", start, dt=1e-3)


def judged_protocol_file(directory, **cells_run):
    """Protocol D's judged layout for the synthetic case, with an editable cells_run block."""
    protocol = json.loads(
        (ROOT / "validation/betse/protocols/physical_default_world_dense.json").read_text()
    )
    protocol["betse_case"] = "synthetic"
    protocol["cells_run"] = {
        **protocol["cells_run"],
        "dt_init_s": DT["init"],
        "dt_sim_s": DT["sim"],
        "backends": ["cpu"],
        **cells_run,
    }
    path = directory / "protocol.json"
    path.write_text(json.dumps(protocol))
    return path


def test_judged_protocol_must_match_the_case_and_the_run(case, tmp_path):
    world = adapter.betse_world(case, blind=True)
    run = dict(
        device_kind="cpu", dt_init=DT["init"], dt_sim=DT["sim"], solver=adapter.RESOLVED_SOLVER
    )
    path = judged_protocol_file(tmp_path)
    protocol, sha = adapter.judged_protocol(path, world, **run)
    assert (
        sha == hashlib.sha256(path.read_bytes()).hexdigest()
        and protocol["betse_case"] == "synthetic"
    )
    for change, message in (
        ({**run, "dt_init": 2 * DT["init"]}, "dt_init_s"),
        ({**run, "device_kind": "gpu"}, "backends"),
        ({**run, "solver": "rk4"}, "solver"),
    ):
        with pytest.raises(adapter.AdapterError, match=message):
            adapter.judged_protocol(path, world, **change)
    (tmp_path / "other").mkdir()
    wrong_case = judged_protocol_file(tmp_path / "other")
    data = json.loads(wrong_case.read_text())
    wrong_case.write_text(json.dumps(data | {"betse_case": "default-world-dense"}))
    with pytest.raises(adapter.AdapterError, match="betse_case"):
        adapter.judged_protocol(wrong_case, world, **run)


def test_judged_run_names_its_protocol_and_is_judgeable(case, tmp_path):
    path = judged_protocol_file(tmp_path)
    run = adapter.run_resolved(
        case,
        tmp_path / "run",
        device_kind="cpu",
        window_steps=2,
        protocol_path=path,
        dt_init=DT["init"],
        dt_sim=DT["sim"],
    )
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = json.loads((tmp_path / "run" / "layout" / cmp.LAYOUT_MANIFEST).read_text())
    assert run["valid"] and run["protocol"]["sha256"] == sha == manifest["protocol_sha256"]
    result = cmp.run_comparison(case, tmp_path / "run" / "layout", path)
    assert not result["refusals"] and result["verdict"] in ("pass", "fail")
    with pytest.raises(adapter.AdapterError):
        adapter.run_resolved(
            case,
            tmp_path / "refused",
            device_kind="cpu",
            protocol_path=path,
            dt_init=2 * DT["init"],
        )
    assert not (tmp_path / "refused").exists()
