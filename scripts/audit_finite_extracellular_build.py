"""Read-only CORE-009 audit: independent equations, dense replay and full state.

Production metadata/layout loading is inspected but never used as a dynamics or
observer oracle. No ODE solver is imported or invoked by this auditor.
"""

import argparse
import hashlib
import json
import math
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core.specs import load_spec  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes  # noqa: E402
from cells.models import finite_extracellular as model  # noqa: E402
from scripts.audit_finite_extracellular_reference_v2 import replay  # noqa: E402
from scripts.verify_batch_windows_build import audit_cohort, suffix  # noqa: E402
from scripts.verify_windows_build import audit_windows, payloads  # noqa: E402
from tests import finite_extracellular_numerical_checks as checks  # noqa: E402
from tests import finite_extracellular_numerical_data as data  # noqa: E402
from tests.finite_extracellular_fixtures import REFERENCE, REFERENCE_SHA, canonical  # noqa: E402


def held(raw, times):
    """Resolve IDs independently of production's schedule composer."""
    root, controls = raw["model"], raw["experiment"]
    ids = [p["id"] for p in root["species"]]
    n, s, k, e = (
        len(root["cells"]),
        len(ids),
        len(controls["channel_controls"]),
        len(root["junctions"]),
    )
    leak, pump = np.zeros((len(times), n, s)), np.zeros((len(times), n))
    channel, junction = np.zeros((len(times), k)), np.zeros((len(times), e))

    def values(group, key):
        at = np.searchsorted([p["time"] for p in group], times, side="right") - 1
        assert np.all(at >= 0)
        rows = (
            [[p[key][s] for s in ids] for p in group]
            if key == "multipliers"
            else [p[key] for p in group]
        )
        return np.asarray(rows)[at]

    membranes = {p["membrane_id"]: p for p in controls["membrane_controls"]}
    channels = {p["channel_id"]: p for p in controls["channel_controls"]}
    edges = {p["junction_id"]: p for p in controls["junction_controls"]}
    at = 0
    for i, entry in enumerate(root["cells"]):
        g = membranes[entry["membrane"]["id"]]
        leak[:, i], pump[:, i] = values(g["leak"], "multipliers"), values(g["pump"], "multiplier")
        if entry["channel"] is not None:
            channel[:, at] = values(channels[entry["channel"]["id"]]["schedule"], "availability")
            at += 1
    for i, edge in enumerate(root["junctions"]):
        junction[:, i] = values(edges[edge["id"]]["schedule"], "open_fraction")
    return leak, pump, channel, junction


def hyperbolic(x):
    regular = np.where(np.abs(x) < 1e-5, 1.0, x)
    return np.where(
        np.abs(x) < 1e-5, 1 + x * x / 12 - x**4 / 720, regular / (2 * np.tanh(regular / 2))
    )


def independent(case, values, controls):
    """Cell-major hyperbolic flux, native mV/ms kinetics and literal accounting."""
    layout, g = data.layout(case), checks.geometry(case)
    p = layout.split(values)
    count = len(values)
    cells = []
    for c, m in zip(case["world"]["cells"], case["world"]["membranes"], strict=True):
        pump = m["pump"]
        cells.append(
            c
            | m
            | {
                "species_ids": case["world"]["species_ids"],
                "stoichiometry": [0] * layout.s if pump is None else pump["stoichiometry"],
                "drive_J_per_mol": 0 if pump is None else pump["drive_J_per_mol"],
                "capacity_fmol_per_s": 0 if pump is None else pump["capacity_fmol_per_s"],
            }
        )
    leak_control, pump_control, availability, edge_control = controls
    n, delta, z, rt = g["initial"] + p["amount"], p["amount"], g["z"], g["rt"]
    v = checks.voltage(case, delta)
    outside = g["outside_initial"] + p["extracellular_amount"]
    ci = n / g["volume"][None, :, None]
    co = outside[:, None, :] / g["outside_volume"]
    x = v[..., None] * z * data.F / rt
    unit = (
        np.asarray([c["area_m2"] for c in cells])[None, :, None]
        / 1e-15
        * ((co - ci) * hyperbolic(x) - (co + ci) * x / 2)
    )
    leak = np.asarray([c["permeability_m_per_s"] for c in cells]) * leak_control * unit
    mu = rt * (np.log(ci) - np.log(co)) + z * data.F * v[..., None]
    nu = np.asarray([c["stoichiometry"] for c in cells])
    drive = np.asarray([c["drive_J_per_mol"] for c in cells])
    cycle_energy = drive + np.sum(nu * mu, axis=-1)
    cycles = (
        np.asarray([c["capacity_fmol_per_s"] for c in cells])
        * pump_control
        * np.tanh(-cycle_energy / (2 * rt))
    )
    pump_flux = nu * cycles[..., None]
    local_rate, exchange = (
        leak + pump_flux,
        p["leak_transferred"] + nu * p["pump_cycles"][..., None],
    )
    dissipation = -1e-3 * (np.sum(leak * mu, axis=-1) + cycles * cycle_energy)
    targets, taus, gate_rates = (np.zeros((count, layout.k, 2)) for _ in range(3))
    opened, permeability, channel_flux, channel_mu, channel_d = (
        np.zeros((count, layout.k)) for _ in range(5)
    )
    for k, c in enumerate(case["world"]["channels"]):
        i = g["channel_cells"][k]
        s = cells[i]["species_ids"].index(c["species_id"])
        mv = v[:, i] * 1000
        targets[:, k] = np.stack(
            (1 / (1 + np.exp(-(mv + 6) / 6.4)), 1 / (1 + np.exp((mv + 25.3) / 3.5))), axis=1
        )
        taus[:, k] = np.stack(((8.33 - 0.1163 * mv) / 1000, (1620 - 15.5 * mv) / 1000), axis=1)
        gate_rates[:, k] = (targets[:, k] - p["membrane_gate"][:, k]) / taus[:, k]
        opened[:, k] = np.prod(p["membrane_gate"][:, k], axis=1)
        permeability[:, k] = (
            c["max_permeability_m_per_s"] * c["abundance"] * availability[:, k] * opened[:, k]
        )
        channel_flux[:, k] = unit[:, i, s] * permeability[:, k]
        channel_mu[:, k] = mu[:, i, s]
        channel_d[:, k] = -1e-3 * channel_flux[:, k] * channel_mu[:, k]
        local_rate[:, i, s] += channel_flux[:, k]
        exchange[:, i, s] += p["channel_transferred"][:, k]
        dissipation[:, i] += channel_d[:, k]
    edge_flux, edge_mu, edge_open, edge_p = (
        np.zeros((count, layout.e, layout.s)) for _ in range(4)
    )
    edge_v, edge_target, edge_rate, edge_d = (np.zeros((count, layout.e)) for _ in range(4))
    amount_rate, internal = local_rate.copy(), np.zeros_like(n)
    for e, (a, b) in enumerate(g["endpoints"]):
        edge = case["world"]["junctions"][e]
        dv = v[:, a] - v[:, b]
        edge_v[:, e] = dv
        scaled = edge["sensitivity_per_V"] * dv
        logcosh = np.logaddexp(scaled, -scaled) - np.log(2.0)
        edge_target[:, e] = np.exp(
            -np.logaddexp(
                0.0, np.log(2.0) - edge["sensitivity_per_V"] * edge["half_voltage_V"] + logcosh
            )
        )
        edge_rate[:, e] = (edge_target[:, e] - p["junction_gate"][:, e]) / edge["tau_s"]
        residual = np.asarray(edge["residual_fraction"])
        edge_open[:, e] = residual + (1 - residual) * p["junction_gate"][:, e, None]
        edge_p[:, e] = (
            np.asarray(edge["permeability_m_per_s"]) * edge_control[:, e, None] * edge_open[:, e]
        )
        ex = z * data.F * dv[:, None] / rt
        edge_flux[:, e] = (
            edge["area_m2"]
            / 1e-15
            * edge_p[:, e]
            * ((ci[:, a] - ci[:, b]) * hyperbolic(ex) + (ci[:, a] + ci[:, b]) * ex / 2)
        )
        edge_mu[:, e] = rt * (np.log(ci[:, b]) - np.log(ci[:, a])) - z * data.F * dv[:, None]
        edge_d[:, e] = -1e-3 * np.sum(edge_flux[:, e] * edge_mu[:, e], axis=1)
        amount_rate[:, a] -= edge_flux[:, e]
        amount_rate[:, b] += edge_flux[:, e]
        internal[:, a] -= p["junction_transferred"][:, e]
        internal[:, b] += p["junction_transferred"][:, e]
    material = delta - exchange - internal
    global_material = np.sum(delta, axis=1) + p["extracellular_amount"]
    dv = data.QF / g["cap"] * np.sum(z * delta, axis=-1)
    chemical = (
        1e-3
        * rt
        * np.sum(
            delta * (np.log(g["initial"] / g["volume"][:, None]) - 1)
            + n * np.log1p(delta / g["initial"]),
            axis=(1, 2),
        )
    )
    od = p["extracellular_amount"]
    chemical += (
        1e-3
        * rt
        * np.sum(
            od * (np.log(g["outside_initial"] / g["outside_volume"]) - 1)
            + outside * np.log1p(od / g["outside_initial"]),
            axis=1,
        )
    )
    outside0 = case["world"]["extracellular"]
    q0 = math.fsum(
        (
            data.QF
            * math.fsum((outside0["fixed_charge_equivalent_fmol"], *(z * g["outside_initial"]))),
            *(g["cap"] * g["v0"]),
        )
    )
    electric = 0.5e12 * np.sum(g["cap"] * dv * (2 * g["v0"] + dv), axis=1)
    balance = (
        chemical
        + electric
        + np.sum(p["membrane_dissipated_energy_pJ"], axis=1)
        + np.sum(p["junction_dissipated_energy_pJ"], axis=1)
        + 1e-3 * np.sum(drive * p["pump_cycles"], axis=1)
    )
    result = {
        "amount": n.swapaxes(-1, -2),
        "extracellular_amount": outside[..., None],
        "extracellular_concentration_mM": outside[..., None] / g["outside_volume"],
        "extracellular_rate_fmol_per_s": -np.sum(local_rate, axis=1)[..., None],
        "extracellular_species_balance_fmol": (
            p["extracellular_amount"] + np.sum(exchange, axis=1)
        )[..., None],
        "concentration_mM": ci.swapaxes(-1, -2),
        "voltage_V": v,
        "leak_multiplier": leak_control.swapaxes(-1, -2),
        "pump_multiplier": pump_control,
        "leak_flux_fmol_per_s": leak.swapaxes(-1, -2),
        "pump_cycles_per_s": cycles,
        "pump_flux_fmol_per_s": pump_flux.swapaxes(-1, -2),
        "delta_mu_J_per_mol": mu.swapaxes(-1, -2),
        "pump_affinity_J_per_mol": cycle_energy,
        "membrane_current_A": data.QF * np.sum(z * local_rate, axis=-1),
        "pump_power_W": -1e-15 * drive * cycles,
        "pump_work_J": -1e-15 * drive * p["pump_cycles"],
        "dissipation_rate_pJ_per_s": dissipation,
        "species_balance_fmol": material.swapaxes(-1, -2),
        "charge_balance_V": data.QF / g["cap"] * np.sum(z * material, axis=-1),
        "energy_balance_pJ": balance,
        "channel_availability": availability,
        "channel_open_probability": opened,
        "channel_gate_inf": targets.swapaxes(-1, -2),
        "channel_gate_tau_s": taus.swapaxes(-1, -2),
        "channel_gate_rate_per_s": gate_rates.swapaxes(-1, -2),
        "channel_effective_permeability_m_per_s": permeability,
        "channel_flux_fmol_per_s": channel_flux,
        "channel_delta_mu_J_per_mol": channel_mu,
        "channel_dissipation_rate_pJ_per_s": channel_d,
        "junction_availability": edge_control,
        "junction_delta_voltage_V": edge_v,
        "junction_gate_inf": edge_target,
        "junction_gate_rate_per_s": edge_rate,
        "junction_open_fraction": edge_open.swapaxes(-1, -2),
        "junction_effective_permeability_m_per_s": edge_p.swapaxes(-1, -2),
        "junction_flux_fmol_per_s": edge_flux.swapaxes(-1, -2),
        "junction_delta_mu_J_per_mol": edge_mu.swapaxes(-1, -2),
        "junction_current_A": data.QF * np.sum(z * edge_flux, axis=-1),
        "junction_dissipation_rate_pJ_per_s": edge_d,
        "global_species_balance_fmol": global_material,
        "countercharge_C": q0 + data.QF * np.sum(z * global_material, axis=1),
    }
    slopes = (
        amount_rate,
        leak,
        cycles,
        dissipation,
        gate_rates,
        channel_flux,
        edge_rate,
        edge_flux,
        edge_d,
        -np.sum(local_rate, axis=1),
    )
    return result, np.concatenate(
        [a.reshape(count, math.prod(a.shape[1:])) for a in slopes], axis=1
    )


def inspect_readouts(arrays, raw, case):
    values = canonical(case, arrays, "observed_")
    expected, _ = independent(case, values, held(raw, arrays["observation_times"]))
    unpadded = {
        "energy_balance_pJ",
        "global_species_balance_fmol",
        "countercharge_C",
    }
    for name, wanted in expected.items():
        actual = arrays["observed_" + name]
        if name not in unpadded:
            assert actual.shape[:-1] == wanted.shape[:-1] and actual.shape[-1] >= wanted.shape[-1]
            assert np.all(actual[..., wanted.shape[-1] :] == 0), name
            actual = actual[..., : wanted.shape[-1]]
        atol = (
            1e-23
            if name.endswith(("_A", "_W", "_J", "_C"))
            else 1e-24
            if name.endswith("_m_per_s")
            else 1e-8
            if name.endswith("_J_per_mol")
            else 1e-11
            if name.endswith(("_per_s", "_pJ"))
            else 3e-13
        )
        if name.endswith(("_multiplier", "_availability")):
            np.testing.assert_array_equal(actual, wanted)
        np.testing.assert_allclose(actual, wanted, atol=atol, rtol=3e-12, err_msg=name)
    assert set(expected) == set(model.Observations.__dataclass_fields__) - {
        "times",
        *model.STATE_TYPE._fields,
    }
    return len(expected)


def inspect_dense(arrays, raw, case):
    times, values = arrays["accepted_times"], canonical(case, arrays)
    if len(times) < 2:
        raise ValueError("Acceptance dense check needs at least one interval")
    controls = held(raw, times[:-1])
    _, f0 = independent(case, values[:-1], controls)
    _, f1 = independent(case, values[1:], controls)
    h, delta = np.diff(times)[:, None], values[1:] - values[:-1]
    coefficients = np.stack(
        (values[:-1], h * f0, 3 * delta - h * (2 * f0 + f1), -2 * delta + h * (f0 + f1)), axis=2
    )
    domain = checks.candidate_polynomial_domain(case, {"coefficients": coefficients})
    assert domain["pass"]
    ts = arrays["observation_times"]
    at = np.clip(np.searchsorted(times, ts, side="right") - 1, 0, len(times) - 2)
    theta = (ts - times[at]) / (times[at + 1] - times[at])
    c = coefficients[at]
    wanted = c[:, :, 0] + theta[:, None] * (
        c[:, :, 1] + theta[:, None] * (c[:, :, 2] + theta[:, None] * c[:, :, 3])
    )
    indices = np.searchsorted(times, ts)
    exact = times[np.minimum(indices, len(times) - 1)] == ts
    wanted[exact] = values[indices[exact]]
    np.testing.assert_allclose(canonical(case, arrays, "observed_"), wanted, atol=3e-13, rtol=3e-12)
    return domain


def resolved_world(spec):
    raw = spec.to_dict()["model"]
    world = data.spec.resolve(
        {k: v for k, v in raw.items() if k != "id"} | {"schema": data.spec.SCHEMA}
    )
    return json.loads(json.dumps(asdict(world)))


def audit_run(path, case, plan, reference_path, *, branch=False):
    path = Path(path)
    manifest = payloads(path, current=True)
    spec = load_spec(path / "resolved_config.json")
    raw = spec.to_dict()
    assert resolved_world(spec) == case["world"]
    assert spec.execution.dt == 0.001 and spec.fingerprint == manifest["definition_sha256"]
    assert manifest["observer"] == {"id": model.OBSERVER_ID, "sampling": model.OBSERVATION_SAMPLING}
    assert manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID
    assert spec.execution.material_balance_atol_fmol == tuple(
        plan["accounting_limits"]["species_material_overrides_fmol"].get(
            s, plan["accounting_limits"]["material_fmol"]
        )
        for s in spec.model.species_ids
    )
    times_controls = [p.time for p in spec.experiment.changes]
    if not branch:
        assert spec.experiment.end_time == case["horizon_s"]
        leak, pump, channel, junction = held(raw, times_controls)
        assert [
            {
                "time_s": t,
                "value": {
                    "leak": a.tolist(),
                    "pump": b.tolist(),
                    "channel": c.tolist(),
                    "junction": d.tolist(),
                },
            }
            for t, a, b, c, d in zip(times_controls, leak, pump, channel, junction, strict=True)
        ] == case["controls"]
    with np.load(path / "trajectory.npz", allow_pickle=False) as saved:
        arrays = dict(saved)
    expected_fields = {
        "accepted_times",
        "observation_times",
        *model.STATE_TYPE._fields,
        *("observed_" + k for k in model.Observations.__dataclass_fields__ if k != "times"),
        *("cell_ids" if k == "ids" else k for k in model.LAYOUT_TYPE._fields),
    }
    assert set(arrays) == expected_fields
    state, layout = model.initial_values(spec)
    for key, value in zip(layout._fields, layout, strict=True):
        np.testing.assert_array_equal(arrays["cell_ids" if key == "ids" else key], value)
    times = arrays["accepted_times"]
    grid = np.unique(
        np.r_[
            np.arange(math.ceil(spec.experiment.end_time / spec.execution.dt)) * spec.execution.dt,
            times_controls,
            spec.experiment.end_time,
        ]
    )
    np.testing.assert_array_equal(times, grid[grid >= times[0]])
    np.testing.assert_array_equal(
        arrays["observation_times"], [t for t in spec.experiment.observation_times if t >= times[0]]
    )
    with np.load(reference_path / "refined.npz", allow_pickle=False) as saved:
        oracle = dict(saved)
    counts = dict(
        zip(
            model.STATE_TYPE._fields,
            (
                len(spec.model.cells),
                len(spec.model.cells),
                len(spec.model.cells),
                len(spec.model.cells),
                len(spec.model.channels),
                len(spec.model.channels),
                len(spec.model.junctions),
                len(spec.model.junctions),
                len(spec.model.junctions),
                1,
            ),
            strict=True,
        )
    )
    results = {}
    for group, key, prefix in (
        ("accepted", "accepted_times", ""),
        ("observed", "observation_times", "observed_"),
    ):
        mesh, values = arrays[key], canonical(case, arrays, prefix)
        for field, target in zip(state._fields, state, strict=True):
            actual = arrays[prefix + field]
            assert actual.shape == (len(mesh), *target.shape) and actual.dtype == np.float64
            assert np.all(actual[..., counts[field] :] == 0)
        expected = replay(
            case, oracle | {"sample_times_s": mesh, "sample_state": np.empty_like(values)}, "Radau"
        )
        errors = checks.errors(case, values, expected, plan["trajectory_limits"])
        accounting = checks.inspect_samples(case, mesh, values, plan["accounting_limits"])
        assert errors["pass"] and accounting["pass"], (group, errors, accounting)
        boundaries = sorted(
            {float(mesh[0]), *(t for t in times_controls if mesh[0] < t <= mesh[-1])}
        )
        u = held(raw, boundaries)
        clipped = case | {
            "horizon_s": float(mesh[-1]),
            "controls": [
                {
                    "time_s": t,
                    "value": {
                        "leak": a.tolist(),
                        "pump": b.tolist(),
                        "channel": c.tolist(),
                        "junction": d.tolist(),
                    },
                }
                for t, a, b, c, d in zip(boundaries, *u, strict=True)
            ],
        }
        controls = checks.control_checks(clipped, mesh, values, plan["trajectory_limits"])
        assert controls["pass"]
        results[group] = {
            "errors": errors,
            "accounting": accounting,
            "controls": controls,
            "rows": len(mesh),
        }
    readouts, dense = inspect_readouts(arrays, raw, case), inspect_dense(arrays, raw, case)
    for name in manifest["snapshots"]:
        saved = load_snapshot(path / name)
        row = np.flatnonzero(times == saved.checkpoint.time)
        assert len(row) == 1 and saved.spec == spec
        for field, value in zip(
            saved.checkpoint.state._fields, saved.checkpoint.state, strict=True
        ):
            np.testing.assert_array_equal(value, arrays[field][row[0]])
    return arrays, {
        "reference_case": case["id"],
        "branch": branch,
        "manifest_sha256": sha(path / "manifest.json"),
        "snapshots": len(manifest["snapshots"]),
        "independent_readout_fields": readouts,
        "dense_domain": dense,
        **results,
    }


def audit(path):
    path = Path(path).resolve()
    receipt = json.loads((path / "verification.json").read_text())
    assert receipt["status"] == "pass" and not (path / "failure.json").exists()
    registration = json.loads((path / "registration.json").read_text())
    assert registration["max_seconds"] == 3600
    assert registration["max_artifact_bytes"] == 2 * 2**30
    assert 0 <= receipt["seconds"] <= registration["max_seconds"]
    assert (
        sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        <= registration["max_artifact_bytes"]
    )
    assert registration["cpu_affinity"] == [0, 1, 2, 3] and registration["eager_lanes"] == 4
    assert registration["thread_environment"] == dict.fromkeys(
        ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
    )
    assert registration["reference_solver_rerun"] is False
    assert registration["scientific_inputs_changed"] is False
    assert registration["source_hashes"] == receipt["source_hashes"]
    assert registration["runtime"] == receipt["runtime"]
    assert registration["files_sha256"] == receipt["implementation_files_sha256"]
    assert receipt["source_hashes"] == source_hashes() and receipt["runtime"] == runtime_identity()
    assert {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()} == set(
        receipt["files_sha256"]
    ) | {"verification.json"}
    for name, value in receipt["files_sha256"].items():
        target = (path / name).resolve()
        assert target.is_relative_to(path) and sha(target) == value
        assert not (path / name).is_symlink() and target.stat().st_nlink == 1
    with zipfile.ZipFile(path / "implementation_sources.zip") as capsule:
        assert len(capsule.namelist()) == len(set(capsule.namelist()))
        assert set(capsule.namelist()) == set(receipt["implementation_files_sha256"])
        for name, value in receipt["implementation_files_sha256"].items():
            assert hashlib.sha256(capsule.read(name)).hexdigest() == value == sha(ROOT / name)
    assert sha(REFERENCE / "verification.json") == REFERENCE_SHA
    reference = json.loads((REFERENCE / "verification.json").read_text())
    for name, value in reference["files_sha256"].items():
        assert sha(REFERENCE / name) == value
    plan = json.loads((REFERENCE / "protocol.json").read_text())
    cases = {c["id"]: c for c in json.loads((REFERENCE / "cases.json").read_text())}
    assert receipt["fresh_process_restart"] == {"status": "pass", "exact_restarts": len(cases)}
    assert receipt["jit_eager_comparison_factor"] == 0.001
    assert receipt["cohort_cases"] == {
        group: [name for name in cases if ("divalent" in name) == (group == "divalent")]
        for group in ("mono", "divalent")
    }
    assert set(receipt["eager_worker_schedule"]) <= {"0", "1", "2", "3"}
    assert sorted(
        c for names in receipt["eager_worker_schedule"].values() for c in names
    ) == sorted(cases)
    assert receipt["reference"] == json.loads((path / "reference-audit.json").read_text())
    assert receipt["reference"]["status"] == receipt["archive"]["status"] == "pass"
    assert receipt["archive"] == json.loads((path / "archived-013-audit.json").read_text())
    assert (
        receipt["archive"]["scalar_snapshots"] == 162
        and receipt["archive"]["cohort_snapshots"] == 16
    )
    assert receipt["old_model_regression"] == json.loads(
        (path / "old-model-regression.json").read_text()
    )
    assert receipt["old_model_regression"]["status"] == "pass"
    assert (
        receipt["ionic_channel_exact_arrays"]
        == json.loads((path / "ionic-channel-regression.json").read_text())["exact_arrays"]
    )
    assert len(receipt["ionic_channel_exact_arrays"]) == 40
    assert set(receipt["runs"]) == {
        f"{m}/{c}" for m in ("jit", "eager", "resumed") for c in cases
    } | {"branch/star_mono_continue"}
    arrays = {}
    for name, record in receipt["runs"].items():
        case = cases[record["reference_case"]]
        arrays[name], actual = audit_run(
            path / name, case, plan, REFERENCE / case["id"], branch=record["branch"]
        )
        assert actual == record
    for name, case in cases.items():
        original, resumed = arrays[f"jit/{name}"], arrays[f"resumed/{name}"]
        start, obs = (
            np.searchsorted(original[k], resumed["accepted_times"][0])
            for k in ("accepted_times", "observation_times")
        )
        for key, value in original.items():
            wanted = (
                value[start:]
                if key in model.STATE_TYPE._fields or key == "accepted_times"
                else value[obs:]
                if key.startswith("observed_") or key == "observation_times"
                else value
            )
            np.testing.assert_array_equal(resumed[key], wanted)
        for prefix in ("", "observed_"):
            assert checks.errors(
                case,
                canonical(case, original, prefix),
                canonical(case, arrays[f"eager/{name}"], prefix),
                plan["trajectory_limits"],
                factor=0.001,
            )["pass"]
    parent = load_snapshot(path / "branch-parent")
    branch = arrays["branch/star_mono_continue"]
    assert parent.checkpoint.time == branch["accepted_times"][0] == 0.02
    target = load_spec(path / "branch/star_mono_continue/resolved_config.json")
    assert parent.spec.model == target.model and parent.spec.execution == target.execution
    assert all(
        group[-1].time == 0.02 and group[-1].open_fraction == 0
        for group in parent.spec.experiment.junctions
    )
    assert all(group[-1].open_fraction == 1 for group in target.experiment.junctions)
    for field, value in zip(parent.checkpoint.state._fields, parent.checkpoint.state, strict=True):
        np.testing.assert_array_equal(branch[field][0], value)
    windows, cohorts = {}, {}
    for group, names in receipt["cohort_cases"].items():
        name = names[-1]
        windows[group] = audit_windows(path / "windows" / group, arrays[f"jit/{name}"])
        wanted = {i + 1: arrays[f"jit/{c}"] for i, c in enumerate(names)}
        cohorts[group] = audit_cohort(path / "cohorts" / group, wanted)
        from cells.batch_io import load_batch_snapshot

        saved = load_batch_snapshot(path / "cohorts" / group / "snapshots/round-0000000001")
        cohorts[f"resumed/{group}"] = audit_cohort(
            path / "cohort-resumed" / group,
            {i: suffix(v, saved.checkpoints[i], model) for i, v in wanted.items()},
        )
    assert windows == receipt["windows"] and cohorts == receipt["cohorts"]
    return {
        "status": "pass",
        "reference_cases": len(cases),
        "scalar_runs": len(receipt["runs"]),
        "window_runs": len(windows),
        "cohort_runs": len(cohorts),
        "payload_hashes": len(receipt["files_sha256"]),
        "production_sources": len(source_hashes()),
        "implementation_sources": len(receipt["implementation_files_sha256"]),
        "maximum_observed_normalized_error": max(
            r["observed"]["errors"]["max_normalized_error"] for r in receipt["runs"].values()
        ),
        "verification_sha256": sha(path / "verification.json"),
        "solver_rerun": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
