"""Prospective schema/arithmetic checks; synthetic records are not native evidence."""

import copy
import math

import alignment as a
import cluster_alignment as cluster
import contact as c
import numpy as np
import pytest
import trajectory as driver
import trajectory_context as ctx
from trajectory_check import Checks, cells_record, difference, native_record, rate_by_cell, unpack


def registered():
    saved = c.read(ctx.evidence.SESSION / "betse.json")
    return {
        "protocol": c.read(ctx.PROTOCOL),
        "base_protocol": c.read(a.PROTOCOL),
        "geometry": saved["geometry"],
        "settings": saved["settings"],
    }


def synthetic_native(case_id):
    r = registered()
    p, b, g = r["protocol"], r["base_protocol"], r["geometry"]
    case = next(row for row in p["cases"] if row["id"] == case_id)
    dt, count, constants = 0.0001, 10, b["profiles"]["matched_constants"]
    vi = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    owners, areas, zs = g["membrane_owners"], g["membrane_areas_m2"], b["expected_valence"]
    ci, co, zero = (
        [[v] * 7 for v in b["inside_mM"]],
        [[v] * 30 for v in b["outside_mM"]],
        [[0.0] * 30 for _ in range(6)],
    )

    def snapshot(ci, co, density):
        rho = [constants["F"] * math.fsum(z * ci[s][i] for s, z in enumerate(zs)) for i in range(7)]
        voltage = [
            rho[i] * g["cell_volumes_m3"][i] / (0.01 * g["cell_areas_m2"][i]) for i in range(7)
        ]
        return {
            "inside_mM": copy.deepcopy(ci),
            "outside_mM": copy.deepcopy(co),
            "rho_C_per_m3": rho,
            "voltage_V": [voltage[i] for i in owners],
            "inward_current_A": [
                constants["F"] * areas[j] * math.fsum(z * density[s][j] for s, z in enumerate(zs))
                for j in range(30)
            ],
            "boundary_voltage_V": [0.0] * 100,
        }

    labels = [i * count * dt / (count - 1) for i in range(count)]
    initial = snapshot(ci, co, zero)
    before, rows = initial, []
    for k in range(count):
        density = [
            [
                c.oracle(
                    {
                        "inside_mM": ci[s][owner],
                        "outside_mM": co[s][j],
                        "valence": z,
                        "voltage_V": before["voltage_V"][j],
                        "temperature_K": 310.15,
                        "area_m2": areas[j],
                        "permeability_m_per_s": b["permeability_m_per_s"][s] * case["availability"],
                    },
                    constants,
                )
                * 1e-15
                / areas[j]
                for j, owner in enumerate(owners)
            ]
            for s, z in enumerate(zs)
        ]
        rates = rate_by_cell(density, g)
        ci = [[v + dt * rates[s][i] / vi[i] for i, v in enumerate(row)] for s, row in enumerate(ci)]
        co = [[v - dt * math.fsum(rates[s]) / vo for v in row] for s, row in enumerate(co)]
        after = snapshot(ci, co, density)
        rows.append(
            {
                "index": k,
                "raw_label_s": labels[k],
                "before_elapsed_s": k * dt,
                "after_elapsed_s": (k + 1) * dt,
                "before": before,
                "after": after,
                "density_mol_per_m2_s": density,
                "junction_density_mol_per_m2_s": copy.deepcopy(zero),
            }
        )
        before = after
    record = {
        "id": ctx.key(case_id, "matched_constants", dt),
        "dt_s": dt,
        "constants": constants,
        "configured_steps": count,
        "geometry": {key: g[key] for key in cluster.GEOMETRY_FIELDS},
        "settings": r["settings"],
        "rho_channel": 1,
        "species": b["expected_species"],
        "valence": zs,
        "native_pickle_present": True,
        "permeability_m_per_s": [
            [v * case["availability"]] * 30 for v in b["permeability_m_per_s"]
        ],
        "trace": {
            "initial": initial,
            "steps": rows,
            "labels_s": labels,
            "sampled_indices": list(range(1, count)),
            "storage": [{"index": k, "raw_label_s": labels[k]} for k in range(1, count)],
            "loop_calls": 1,
            "loop_returns": 1,
            "concentration_updates": count,
            "hook_restored": True,
        },
        "ordinary": {"time": driver.array_record(np.asarray(labels[1:]))},
        "final": {},
    }
    for field, ordinary, final in (
        ("inside_mM", "cc_time", "cc_cells"),
        ("outside_mM", "cc_env_time", "cc_env"),
        ("voltage_V", "vm_time", "vm"),
        ("inward_current_A", "I_mem_time", "I_mem"),
        ("rho_C_per_m3", "rho_cells_time", "rho_cells"),
    ):
        record["ordinary"][ordinary] = driver.array_record(
            np.asarray([row["after"][field] for row in rows[1:]])
        )
        record["final"][final] = driver.array_record(np.asarray(rows[-1]["after"][field]))
    # Extra exported columns are synthetic field-coverage fixtures, not native evidence.
    for name, shape in (
        ("rate_NaKATP_time", (count - 1, 30)),
        ("gjopen_time", (count - 1, 30)),
        ("dd_time", (count - 1, 6, 30)),
    ):
        record["ordinary"][name] = driver.array_record(np.zeros(shape))
    record["final"] |= {
        "cc_at_mem": driver.array_record(np.asarray([[row[i] for i in owners] for row in ci])),
        "fluxes_mem": driver.array_record(np.asarray(rows[-1]["density_mol_per_m2_s"])),
        "fluxes_gj": driver.array_record(np.asarray(zero)),
        "Dm_cells": driver.array_record(np.zeros((6, 30))),
        "Phi_b": driver.array_record(np.zeros(100)),
    }
    return r, record, case


@pytest.mark.parametrize("case_id", ["passive", "blocked"])
def test_synthetic_native_accounting_and_raw_clock(case_id):
    r, record, case = synthetic_native(case_id)
    checks = Checks()
    result = native_record(r, record, case, "matched_constants", 0.0001, checks)
    assert checks.failed_count == 0 and checks.count > 1000
    assert len(result) == 11 and len(result[-1]["flux_fmol_per_s"]) == 0
    assert record["trace"]["storage"][0]["raw_label_s"] != 0.0002


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_first",
        "raw_label",
        "storage_index",
        "blocked_leak",
        "junction",
        "rho_channel",
        "native_flags",
        "precision",
        "elapsed_time",
        "missing_ordinary",
        "missing_final",
        "extra_final",
    ],
)
def test_synthetic_bad_native_record_rejected(corruption):
    r, record, case = synthetic_native("blocked")
    if corruption == "missing_first":
        record["trace"]["steps"].pop(0)
    elif corruption == "raw_label":
        record["trace"]["labels_s"][1] = 0.0002
    elif corruption == "storage_index":
        record["trace"]["storage"][0]["index"] = 0
    elif corruption == "blocked_leak":
        record["trace"]["steps"][0]["density_mol_per_m2_s"][0][0] = 1e-30
    elif corruption == "junction":
        record["trace"]["steps"][0]["junction_density_mol_per_m2_s"][0][0] = 1e-30
    elif corruption == "rho_channel":
        record["rho_channel"] = 2
    elif corruption == "native_flags":
        record["settings"] = record["settings"] | {"Ca_dyn": True}
    elif corruption == "elapsed_time":
        record["trace"]["steps"][0]["after_elapsed_s"] = 0.0
    elif corruption == "missing_ordinary":
        record["ordinary"].pop("dd_time")
    elif corruption == "missing_final":
        record["final"].pop("cc_at_mem")
    elif corruption == "extra_final":
        record["final"]["undeclared"] = driver.array_record(np.zeros(1))
    else:
        record["ordinary"]["time"]["dtype"] = "<f4"
    with pytest.raises(ValueError):
        native_record(r, record, case, "matched_constants", 0.0001, Checks())


@pytest.mark.parametrize("case_id", ["passive", "blocked"])
@pytest.mark.parametrize("backend", ["jax_eager", "jax_jit"])
@pytest.mark.parametrize("dt", [0.0001, 0.00005])
def test_real_cells_definitions_and_initial_domains(case_id, backend, dt):
    from cells.core.runner import timeline
    from cells.core.specs import parse_spec
    from cells.models import finite_extracellular as model

    case = next(row for row in c.read(ctx.PROTOCOL)["cases"] if row["id"] == case_id)
    spec = parse_spec(ctx.definition(case, dt, backend))
    state, _ = model.initial_values(spec)
    model.check_values(state, spec)
    assert len(timeline(spec)) == round(0.001 / dt) + 1
    assert spec.execution.jit is (backend == "jax_jit")
    assert len(spec.model.cells) == 7
    assert all(not np.any(v) for v in state)


@pytest.mark.parametrize("case_id", ["passive", "blocked"])
@pytest.mark.parametrize("dt", [0.0001, 0.00005, 0.000025])
def test_native_input_changes_are_only_declared_timing_and_permeability(case_id, dt):
    case = next(row for row in c.read(ctx.PROTOCOL)["cases"] if row["id"] == case_id)
    original = c.read(a.PROTOCOL)
    changed = ctx.native_protocol(case, dt)
    allowed = {
        ("init time settings", "time step"),
        ("init time settings", "sampling rate"),
        ("init time settings", "total time"),
    }
    for (path, value), (other, old) in zip(
        changed["yaml_overrides"], original["yaml_overrides"], strict=True
    ):
        assert path == other
        if tuple(path) in allowed:
            assert value == (0.001 if path[-1] == "total time" else dt)
        elif path[:4] == ["tissue profile definition", "tissue", "default", "diffusion constants"]:
            assert value == old * case["availability"]
        else:
            assert value == old


@pytest.mark.parametrize("values", [[0.0, -0.0, 1.0], [[1.0], [2.0]], []])
def test_float64_export_roundtrip(values):
    array = np.asarray(values, dtype=np.float64)
    assert unpack(driver.array_record(array)) == values


@pytest.mark.parametrize("change", ["values", "dtype", "shape", "nonfinite"])
def test_export_corruption_rejected(change):
    record = driver.array_record(np.asarray([1.0]))
    record[change if change != "nonfinite" else "values"] = {
        "values": [2.0],
        "dtype": "<f4",
        "shape": [2],
        "nonfinite": [float("inf")],
    }[change]
    with pytest.raises(ValueError):
        unpack(record)


def test_comparison_counts_failures_and_does_not_hide_small_inventory_changes():
    row = {
        key: [0.0]
        for key in ("voltage_V", "amount_fmol", "transfer_fmol", "flux_fmol_per_s", "current_A")
    }
    other = copy.deepcopy(row)
    other["amount_fmol"][0] = 1e-4
    checks = Checks()
    difference("synthetic", [row], [other], c.read(ctx.PROTOCOL)["trajectory_tolerances"], checks)
    assert checks.count == 5 and checks.failed_count == 1


def test_panel_is_frozen_before_native_execution_and_uses_real_runner_backends():
    p = c.read(ctx.PROTOCOL)
    assert p["cases"] == [
        {"id": "passive", "availability": 1.0},
        {"id": "blocked", "availability": 0.0},
    ]
    assert p["cells_backends"] == ["jax_eager", "jax_jit"]
    assert p["common_times_s"] == [i * 0.0001 for i in range(11)]
    assert p["native_steps_s"] == [0.0001, 0.00005, 0.000025]
    assert p["instantaneous_tolerances"] == c.read(a.PROTOCOL)["tolerances"]
    assert p["total_timeout_seconds"] == 180 and p["max_artifact_bytes"] == 64 * 1024**2


def static_cells_record():
    """A prepared blocked invariant, read out without running an integration loop."""
    from cells.core.specs import parse_spec
    from cells.models import finite_extracellular as model

    r = registered()
    case = r["protocol"]["cases"][1]
    dt, backend = 0.0001, "jax_eager"
    identifier = ctx.key(case["id"], backend, dt)
    definition = ctx.definition(case, dt, backend)
    spec = parse_spec(definition)
    initial, layout = model.initial_values(spec)
    times = np.asarray(r["protocol"]["common_times_s"])
    history = model.STATE_TYPE(*(np.repeat(v[None], len(times), axis=0) for v in initial))
    observations = model.observe_history(times, history, layout, times, spec)
    r["cells_definitions"] = {identifier: definition}
    return (
        r,
        {
            "id": identifier,
            "definition": definition,
            "times": driver.array_record(times),
            "final_step_index": len(times) - 1,
            "history": {k: driver.array_record(v) for k, v in history._asdict().items()},
            "observations": {k: driver.array_record(v) for k, v in vars(observations).items()},
        },
        case,
    )


def test_static_cells_readouts_match_independent_accounting_without_integrating():
    r, record, case = static_cells_record()
    checks = Checks()
    values = cells_record(r, record, case, "jax_eager", 0.0001, checks)
    assert checks.failed_count == 0 and len(values) == 11


@pytest.mark.parametrize(
    "field",
    [
        "amount",
        "concentration_mM",
        "extracellular_amount",
        "extracellular_concentration_mM",
        "leak_flux_fmol_per_s",
        "membrane_current_A",
    ],
)
def test_rehashed_cells_readout_corruptions_are_detected(field):
    r, record, case = static_cells_record()
    array = np.asarray(unpack(record["observations"][field]))
    array.flat[-1 if field == "membrane_current_A" else 0] += 1
    if field == "membrane_current_A":
        array.flat[-1] -= 1
        array.flat[0] += 1
    record["observations"][field] = driver.array_record(array)
    checks = Checks()
    try:
        cells_record(r, record, case, "jax_eager", 0.0001, checks)
    except ValueError:
        return
    assert checks.failed_count > 0


def test_registration_is_source_bound_and_does_not_launch_workers(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Registration must not launch workers")

    # Authentication's git calls remain available; only process launch is forbidden.
    monkeypatch.setattr(driver, "native_worker", refuse)
    monkeypatch.setattr(driver, "cells_worker", refuse)
    output = tmp_path / "registration"
    value = driver.register(output)
    assert len(value["cells_definitions"]) == 8
    assert value["sources"] == ctx.sources()
    assert not (output / "started.json").exists()
    with pytest.raises(FileExistsError):
        driver.register(output)


def test_detached_launch_is_registered_and_affinity_bound_without_spawning(tmp_path, monkeypatch):
    from types import SimpleNamespace

    output = tmp_path / "fake-launch"
    calls = []

    def fake_popen(command, **kwargs):
        value = c.read(output / "registration.json")
        assert (output / "sources.zip").is_file()
        assert value["sources"] == ctx.sources()
        assert command[:3] == ["taskset", "-c", value["protocol"]["cpu_affinity"]]
        assert command[-2:] == ["execute", str(output)]
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] == driver.subprocess.DEVNULL
        assert kwargs["cwd"] == c.ROOT
        assert kwargs["stdout"].name == str(output / "runner.stdout.log")
        assert kwargs["stderr"].name == str(output / "runner.stderr.log")
        calls.append(command)
        return SimpleNamespace(pid=123456)

    monkeypatch.setattr(driver.subprocess, "Popen", fake_popen)
    # Authentication calls subprocess.check_output, so complete registration first.
    monkeypatch.undo()
    value = driver.register(output)
    monkeypatch.setattr(driver, "register", lambda target: value)
    monkeypatch.setattr(driver.subprocess, "Popen", fake_popen)
    driver.launch(output)
    receipt = c.read(output / "launch.json")
    assert len(calls) == 1 and receipt["pid"] == 123456
    assert receipt["status"] == "launched_detached"
    assert receipt["registration_sha256"] == c.sha(output / "registration.json")
    assert not (output / "started.json").exists()
