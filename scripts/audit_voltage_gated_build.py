"""Read-only CORE-007 evidence audit with independent equations and dense replay.

No ODE solver, production RHS or production observer is used as an oracle.
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
from cells.models import voltage_gated_membrane as model  # noqa: E402
from scripts.audit_multispecies_build import canonical as ionic_canonical  # noqa: E402
from scripts.audit_multispecies_build import held_controls  # noqa: E402
from scripts.audit_voltage_gated_reference import replay  # noqa: E402
from scripts.verify_batch_windows_build import audit_cohort, suffix  # noqa: E402
from scripts.verify_windows_build import audit_windows, payloads  # noqa: E402
from tests import voltage_gated_numerical_checks as checks  # noqa: E402

REFERENCE = ROOT / "runs/num-007-2026-09-09/reference-01"
REFERENCE_SHA = "422720bd0de6ef3259bb32604399f91502112cefa2a318720b28e2fb25c05e75"


def canonical(data, case, prefix=""):
    return np.concatenate(
        (
            ionic_canonical(data, case, prefix),
            data[prefix + "gate"][:, :, 0],
            data[prefix + "channel_transferred"][:, :1],
        ),
        axis=1,
    )


def held(raw, times, ids):
    leak, pump = held_controls(raw, times, ids)
    group = raw["experiment"]["channel_controls"]["schedule"]
    indices = np.searchsorted([p["time"] for p in group], times, side="right") - 1
    assert np.all(indices >= 0)
    return leak, pump, np.asarray([p["availability"] for p in group])[indices]


def independent(case, values, controls):
    """Native mV/ms gates, hyperbolic GHK and literal balance identities.

    Inputs are canonical amount increments and complete ledgers/gates. Results
    have physical axes only; stored padding is inspected separately.
    """
    p, z, n0, nu = checks.parameters(case)
    size, g = len(n0), 2 * len(n0) + 2
    n, leak_control, pump_control, availability = n0 + values[:, :size], *controls
    voltage = checks.voltage(case, values[:, :size])
    ci, co = n / p["volume_pL"], np.asarray(p["bath_mM"])
    x = z * checks.old.F * voltage[:, None] / (checks.old.R * p["temperature_K"])
    regular = np.where(np.abs(x) < 1e-5, 1.0, x)
    h = np.where(
        np.abs(x) < 1e-5, 1 + x * x / 12 - x**4 / 720, regular / (2 * np.tanh(regular / 2))
    )
    unit_flux = p["area_m2"] / 1e-15 * ((co - ci) * h - (co + ci) * x / 2)
    leak = np.asarray(p["permeability_m_per_s"]) * leak_control * unit_flux
    mu = (
        checks.old.R * p["temperature_K"] * (np.log(ci) - np.log(co))
        + z * checks.old.F * voltage[:, None]
    )
    energy = p["drive_J_per_mol"] + np.sum(nu * mu, axis=1)
    cycles = (
        p["capacity_fmol_per_s"]
        * pump_control
        * np.tanh(-energy / (2 * checks.old.R * p["temperature_K"]))
    )
    c = case["channel"]
    index = p["species_ids"].index(c["species_id"])
    gate = values[:, g : g + 2]
    mv = voltage * 1000
    targets = np.stack(
        (1 / (1 + np.exp(-(mv + 6) / 6.4)), 1 / (1 + np.exp((mv + 25.3) / 3.5))), axis=1
    )
    tau = np.stack(((-0.1163 * mv + 8.33) * 0.001, (-15.5 * mv + 1620) * 0.001), axis=1)
    rates = (targets - gate) / tau
    opened = gate[:, 0] * gate[:, 1]
    permeability = c["max_permeability_m_per_s"] * c["abundance"] * availability * opened
    channel_flux = unit_flux[:, index] * permeability
    flux = leak + nu * cycles[:, None]
    flux[:, index] += channel_flux
    channel_d = -1e-3 * channel_flux * mu[:, index]
    dissipated = -1e-3 * (np.sum(leak * mu, axis=1) + cycles * energy) + channel_d
    exchange = values[:, size : 2 * size] + nu * values[:, 2 * size, None]
    exchange[:, index] += values[:, -1]
    material = values[:, :size] - exchange
    cap = p["area_m2"] * p["specific_capacitance_F_per_m2"]
    dv = checks.old.QF / cap * np.sum(z * values[:, :size], axis=1)
    chemical = (
        1e-3
        * checks.old.R
        * p["temperature_K"]
        * np.sum(
            values[:, :size] * (np.log(n0 / p["volume_pL"]) - np.log(co) - 1)
            + n * np.log1p(values[:, :size] / n0),
            axis=1,
        )
    )
    balance = (
        chemical
        + 0.5e12 * cap * dv * (2 * p["initial_voltage_V"] + dv)
        + values[:, 2 * size + 1]
        + 1e-3 * p["drive_J_per_mol"] * values[:, 2 * size]
    )
    readouts = {
        "concentration_mM": ci,
        "voltage_V": voltage,
        "leak_multiplier": leak_control,
        "pump_multiplier": pump_control,
        "leak_flux_fmol_per_s": leak,
        "pump_rate_fmol_per_s": cycles,
        "pump_flux_fmol_per_s": nu * cycles[:, None],
        "delta_mu_J_per_mol": mu,
        "cycle_energy_J_per_mol": energy,
        "inward_current_A": checks.old.QF * np.sum(z * flux, axis=1),
        "chemical_power_W": -1e-15 * p["drive_J_per_mol"] * cycles,
        "chemical_work_J": -1e-15 * p["drive_J_per_mol"] * values[:, 2 * size],
        "dissipation_rate_pJ_per_s": dissipated,
        "bath_exchange_fmol": -exchange,
        "species_balance_fmol": material,
        "charge_balance_V": checks.old.QF / cap * np.sum(z * material, axis=1),
        "resolved_energy_balance_pJ": balance,
        "channel_availability": availability,
        "channel_open_probability": opened,
        "gate_inf": targets,
        "gate_tau_s": tau,
        "gate_rate_per_s": rates,
        "channel_effective_permeability_m_per_s": permeability,
        "channel_flux_fmol_per_s": channel_flux,
        "channel_delta_mu_J_per_mol": mu[:, index],
        "channel_dissipation_rate_pJ_per_s": channel_d,
    }
    derivative = np.concatenate(
        (flux, leak, cycles[:, None], dissipated[:, None], rates, channel_flux[:, None]), axis=1
    )
    return readouts, derivative


def inspect_readouts(data, raw, case):
    values = canonical(data, case, "observed_")
    expected, _ = independent(
        case, values, held(raw, data["observation_times"], case["parameters"]["species_ids"])
    )
    unpadded = {"species_balance_fmol", "charge_balance_V", "resolved_energy_balance_pJ"}
    for name, wanted in expected.items():
        actual = data["observed_" + name]
        if name not in unpadded:
            assert np.all(actual[..., 1:] == 0), name
            actual = actual[..., 0]
        atol = {
            "inward_current_A": 1e-23,
            "chemical_power_W": 1e-23,
            "chemical_work_J": 1e-23,
            "channel_effective_permeability_m_per_s": 1e-24,
            "delta_mu_J_per_mol": 1e-9,
            "channel_delta_mu_J_per_mol": 1e-9,
            "cycle_energy_J_per_mol": 1e-8,
            "gate_rate_per_s": 1e-11,
            "dissipation_rate_pJ_per_s": 1e-11,
            "channel_dissipation_rate_pJ_per_s": 1e-11,
        }.get(name, 1e-13)
        if name in ("leak_multiplier", "pump_multiplier", "channel_availability"):
            np.testing.assert_array_equal(actual, wanted)
        np.testing.assert_allclose(actual, wanted, atol=atol, rtol=2e-12, err_msg=name)
    assert set(data) >= {"observed_" + k for k in expected}
    return len(expected)


def inspect_dense(data, raw, case):
    """Independently reconstruct interval-held cubic observations and their domain."""
    times, values = data["accepted_times"], canonical(data, case)
    control = held(raw, times[:-1], case["parameters"]["species_ids"])
    _, f0 = independent(case, values[:-1], control)
    _, f1 = independent(case, values[1:], control)
    h = np.diff(times)[:, None]
    delta = values[1:] - values[:-1]
    coeff = np.stack(
        (values[:-1], h * f0, 3 * delta - h * (2 * f0 + f1), -2 * delta + h * (f0 + f1)), axis=-1
    )
    # Polynomial checker expects absolute amount coordinates, not increments.
    absolute = coeff.copy()
    n0 = np.asarray(case["parameters"]["initial_amount_fmol"])
    absolute[:, : len(n0), 0] += n0
    domain = checks.candidate_polynomial_domain(case, {"coefficients": absolute})
    assert domain["pass"]
    requested = data["observation_times"]
    index = np.clip(np.searchsorted(times, requested, side="right") - 1, 0, len(times) - 2)
    theta = (requested - times[index]) / (times[index + 1] - times[index])
    c = coeff[index]
    wanted = c[:, :, 0] + theta[:, None] * (
        c[:, :, 1] + theta[:, None] * (c[:, :, 2] + theta[:, None] * c[:, :, 3])
    )
    # Exact endpoints bypass cubic arithmetic in the production observation contract.
    exact = np.searchsorted(times, requested)
    at = times[np.minimum(exact, len(times) - 1)] == requested
    wanted[at] = values[exact[at]]
    np.testing.assert_allclose(canonical(data, case, "observed_"), wanted, atol=3e-13, rtol=2e-12)
    return domain


def audit_run(path, case, plan, reference_path, *, branch=False):
    path = Path(path)
    manifest = payloads(path, current=True)
    spec = load_spec(path / "resolved_config.json")
    raw = spec.to_dict()
    resolved = asdict(spec.model)
    channel = resolved.pop("channel")
    channel["initial_gate"] = dict(zip(("m", "h"), channel["initial_gate"], strict=True))
    assert json.loads(json.dumps(resolved)) == case["parameters"]
    assert json.loads(json.dumps(channel)) == case["channel"]
    assert spec.execution.dt == 0.0005
    assert spec.fingerprint == manifest["definition_sha256"]
    assert manifest["observer"] == {"id": model.OBSERVER_ID, "sampling": model.OBSERVATION_SAMPLING}
    assert manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID
    assert spec.execution.material_balance_atol_fmol == tuple(
        plan["accounting_limits"]["species_material_overrides_fmol"].get(
            s, plan["accounting_limits"]["material_fmol"]
        )
        for s in spec.model.species_ids
    )
    if not branch:
        assert spec.experiment.end_time == case["horizon_s"]
        assert [
            {"time_s": p.time, "leak": list(p.leak), "pump": p.pump, "availability": p.availability}
            for p in spec.experiment.changes
        ] == case["controls"]
    with np.load(path / "trajectory.npz", allow_pickle=False) as saved:
        data = dict(saved)
    expected_fields = {
        "accepted_times",
        *model.STATE_TYPE._fields,
        *("observed_" + k for k in model.Observations.__dataclass_fields__ if k != "times"),
        "observation_times",
        *("cell_ids" if k == "ids" else k for k in model.LAYOUT_TYPE._fields),
    }
    assert set(data) == expected_fields
    state, layout = model.initial_values(spec)
    for field, value in zip(layout._fields, layout, strict=True):
        np.testing.assert_array_equal(data["cell_ids" if field == "ids" else field], value)
    times = data["accepted_times"]
    grid = np.unique(
        np.r_[
            np.arange(math.ceil(spec.experiment.end_time / spec.execution.dt)) * spec.execution.dt,
            [p.time for p in spec.experiment.changes],
            spec.experiment.end_time,
        ]
    )
    np.testing.assert_array_equal(times, grid[grid >= times[0]])
    np.testing.assert_array_equal(
        data["observation_times"], [t for t in spec.experiment.observation_times if t >= times[0]]
    )
    with np.load(reference_path / "refined.npz", allow_pickle=False) as saved:
        oracle = dict(saved)
    results = {}
    for group, key, prefix in (
        ("accepted", "accepted_times", ""),
        ("observed", "observation_times", "observed_"),
    ):
        mesh, values = data[key], canonical(data, case, prefix)
        for field, target in zip(state._fields, state, strict=True):
            actual = data[prefix + field]
            assert actual.shape == (len(mesh), *target.shape) and actual.dtype == np.float64
            assert np.all(actual[..., 1:] == 0)
        expected = replay(
            case, oracle | {"sample_times_s": mesh, "sample_state": np.empty_like(values)}, "Radau"
        )
        error = checks.errors(case, values, expected, plan["trajectory_limits"])
        accounting = checks.inspect_samples(case, mesh, values, plan["accounting_limits"])
        assert error["pass"] and accounting["pass"], (group, error, accounting)
        boundaries = sorted(
            {
                float(mesh[0]),
                *(p.time for p in spec.experiment.changes if mesh[0] < p.time <= mesh[-1]),
            }
        )
        leak, pump, availability = held(raw, boundaries, spec.model.species_ids)
        clipped = case | {
            "horizon_s": float(mesh[-1]),
            "controls": [
                {"time_s": t, "leak": list(a), "pump": float(b), "availability": float(c)}
                for t, a, b, c in zip(boundaries, leak, pump, availability, strict=True)
            ],
        }
        controls = checks.control_checks(clipped, mesh, values, plan["trajectory_limits"]["gate"])
        assert controls["pass"]
        results[group] = {
            "errors": error,
            "accounting": accounting,
            "controls": controls,
            "rows": len(mesh),
        }
    readouts = inspect_readouts(data, raw, case)
    dense = inspect_dense(data, raw, case)
    for relative in manifest["snapshots"]:
        saved = load_snapshot(path / relative)
        row = np.flatnonzero(times == saved.checkpoint.time)
        assert len(row) == 1 and saved.spec == spec
        for field, value in zip(
            saved.checkpoint.state._fields, saved.checkpoint.state, strict=True
        ):
            np.testing.assert_array_equal(value, data[field][row[0]])
    return data, {
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
    assert receipt["source_hashes"] == source_hashes() and receipt["runtime"] == runtime_identity()
    assert {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()} == set(
        receipt["files_sha256"]
    ) | {"verification.json"}
    for name, value in receipt["files_sha256"].items():
        target = (path / name).resolve()
        assert target.is_relative_to(path) and sha(target) == value
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
    assert set(receipt["runs"]) == {
        f"{m}/{c}" for m in ("jit", "eager", "resumed") for c in cases
    } | {"branch/mono_pulse_omitted"}
    data = {}
    for name, record in receipt["runs"].items():
        case = cases[record["reference_case"]]
        data[name], actual = audit_run(
            path / name, case, plan, REFERENCE / case["id"], branch=record["branch"]
        )
        assert actual == record
    for name, case in cases.items():
        original, resumed = data[f"jit/{name}"], data[f"resumed/{name}"]
        start, obs = (
            np.searchsorted(original[k], resumed["accepted_times"][0])
            for k in ("accepted_times", "observation_times")
        )
        for key, value in original.items():
            expected = (
                value[start:]
                if key in model.STATE_TYPE._fields or key == "accepted_times"
                else value[obs:]
                if key.startswith("observed_") or key == "observation_times"
                else value
            )
            np.testing.assert_array_equal(resumed[key], expected)
        for prefix in ("", "observed_"):
            assert checks.errors(
                case,
                canonical(original, case, prefix),
                canonical(data[f"eager/{name}"], case, prefix),
                plan["trajectory_limits"],
                factor=0.001,
            )["pass"]
    parent = load_snapshot(path / "branch-parent")
    branch = data["branch/mono_pulse_omitted"]
    assert parent.checkpoint.time == branch["accepted_times"][0] == 0.0203
    for field, value in zip(parent.checkpoint.state._fields, parent.checkpoint.state, strict=True):
        np.testing.assert_array_equal(branch[field][0], value)
    windows, cohorts = {}, {}
    for prefix in ("mono", "divalent"):
        name = prefix + "_short_pulse"
        windows[prefix] = audit_windows(path / "windows" / prefix, data[f"jit/{name}"])
        selected = [c for c in cases if c.startswith(prefix)]
        wanted = {i + 1: data[f"jit/{c}"] for i, c in enumerate(selected)}
        cohorts[prefix] = audit_cohort(path / "cohorts" / prefix, wanted)
        from cells.batch_io import load_batch_snapshot

        saved = load_batch_snapshot(path / "cohorts" / prefix / "snapshots/round-0000000001")
        cohorts[f"resumed/{prefix}"] = audit_cohort(
            path / "cohort-resumed" / prefix,
            {i: suffix(v, saved.checkpoints[i], model) for i, v in wanted.items()},
        )
    assert windows == receipt["windows"] and cohorts == receipt["cohorts"]
    return {
        "status": "pass",
        "scalar_runs": len(receipt["runs"]),
        "reference_cases": len(cases),
        "fresh_process_restarts": len(cases),
        "window_runs": len(windows),
        "cohort_runs": len(cohorts),
        "payload_hashes": len(receipt["files_sha256"]),
        "production_sources": len(source_hashes()),
        "maximum_observed_normalized_error": max(
            r["observed"]["errors"]["max_normalized_error"] for r in receipt["runs"].values()
        ),
        "maximum_gate_error": max(
            max(r["observed"]["errors"]["errors"][g] for g in ("m", "h"))
            for r in receipt["runs"].values()
        ),
        "verification_sha256": sha(path / "verification.json"),
        "solver_rerun": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
