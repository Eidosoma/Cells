"""Read-only CORE-006 audit: authenticated arrays, independent laws and accounting.

No solver is invoked. Refined implicit trajectories are reconstructed from the
frozen NUM-006 dense basis. Production kernels are not the readout oracle.
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
from cells.models import multispecies_membrane as model  # noqa: E402
from scripts.audit_multispecies_reference import replay  # noqa: E402
from scripts.verify_batch_windows_build import audit_cohort, suffix  # noqa: E402
from scripts.verify_windows_build import payloads  # noqa: E402
from tests import multispecies_numerical_checks as checks  # noqa: E402

REFERENCE = ROOT / "runs/num-006-2026-09-09/reference-01"
REFERENCE_SHA = "331f3dde9ec6093ad1ccd18f27044bc8c30f573c3a596f07642e5c34a2edd41a"


def canonical(data, case, prefix=""):
    initial = np.asarray(case["parameters"]["initial_amount_fmol"])
    return np.concatenate(
        (
            data[prefix + "amount"][:, :, 0] - initial,
            data[prefix + "leak_transferred"][:, :, 0],
            data[prefix + "pump_cycles"][:, :1],
            data[prefix + "dissipated_energy_pJ"][:, :1],
        ),
        axis=-1,
    )


def held_controls(raw, times, ids):
    controls = raw["experiment"]["membrane_controls"]
    groups = []
    for name in ("leak", "pump"):
        group = controls[name]
        positions = np.searchsorted([p["time"] for p in group], times, side="right") - 1
        assert np.all(positions >= 0)
        values = (
            [[p["multipliers"][s] for s in ids] for p in group]
            if name == "leak"
            else [p["multiplier"] for p in group]
        )
        groups.append(np.asarray(values)[positions])
    return groups


def inspect_readouts(data, raw, case):
    """Separate vectorized hyperbolic GHK and literal thermodynamic identities."""
    p, z, initial, nu = checks.parameters(case)
    times = data["observation_times"]
    n = data["observed_amount"][:, :, 0]
    delta = n - initial
    voltage = checks.voltage(case, delta)
    ci, co = n / p["volume_pL"], np.asarray(p["bath_mM"])
    leak_control, pump_control = held_controls(raw, times, p["species_ids"])
    x = z * checks.F * voltage[:, None] / (checks.R * p["temperature_K"])
    regular = np.where(np.abs(x) < 1e-5, 1.0, x)
    h = np.where(
        np.abs(x) < 1e-5, 1 + x * x / 12 - x**4 / 720, regular / (2 * np.tanh(regular / 2))
    )
    leak = (
        p["area_m2"]
        * np.asarray(p["permeability_m_per_s"])
        / 1e-15
        * leak_control
        * ((co - ci) * h - (co + ci) * x / 2)
    )
    mu = checks.R * p["temperature_K"] * (np.log(ci) - np.log(co)) + z * checks.F * voltage[:, None]
    energy = p["drive_J_per_mol"] + np.sum(nu * mu, axis=1)
    cycles = (
        p["capacity_fmol_per_s"]
        * pump_control
        * np.tanh(-energy / (2 * checks.R * p["temperature_K"]))
    )
    expected = {
        "voltage_V": (voltage, 1e-13),
        "concentration_mM": (ci, 1e-14),
        "leak_flux_fmol_per_s": (leak, 1e-14),
        "pump_rate_fmol_per_s": (cycles, 1e-14),
        "pump_flux_fmol_per_s": (nu * cycles[:, None], 1e-14),
        "delta_mu_J_per_mol": (mu, 1e-9),
        "cycle_energy_J_per_mol": (energy, 1e-8),
        "inward_current_A": (checks.QF * np.sum(z * (leak + nu * cycles[:, None]), axis=1), 1e-23),
        "chemical_power_W": (-1e-15 * p["drive_J_per_mol"] * cycles, 1e-23),
        "chemical_work_J": (
            -1e-15 * p["drive_J_per_mol"] * data["observed_pump_cycles"][:, 0],
            1e-23,
        ),
        "dissipation_rate_pJ_per_s": (-1e-3 * (np.sum(leak * mu, axis=1) + cycles * energy), 1e-11),
        "bath_exchange_fmol": (
            -(
                data["observed_leak_transferred"][:, :, 0]
                + nu * data["observed_pump_cycles"][:, :1]
            ),
            1e-14,
        ),
    }
    for field, (value, atol) in expected.items():
        np.testing.assert_allclose(
            data["observed_" + field][..., 0], value, rtol=3e-12, atol=atol, err_msg=field
        )
    residual = (
        delta
        - data["observed_leak_transferred"][:, :, 0]
        - nu * data["observed_pump_cycles"][:, :1]
    )
    capacitance = p["area_m2"] * p["specific_capacitance_F_per_m2"]
    dv = checks.QF / capacitance * np.sum(z * delta, axis=1)
    chemical = (
        1e-3
        * checks.R
        * p["temperature_K"]
        * np.sum(
            delta * (np.log(initial / p["volume_pL"] / co) - 1) + n * np.log1p(delta / initial),
            axis=1,
        )
    )
    energy_balance = (
        chemical
        + 0.5e12 * capacitance * dv * (2 * p["initial_voltage_V"] + dv)
        + data["observed_dissipated_energy_pJ"][:, 0]
        + 1e-3 * p["drive_J_per_mol"] * data["observed_pump_cycles"][:, 0]
    )
    for field, value, atol in (
        ("species_balance_fmol", residual, 1e-14),
        ("charge_balance_V", checks.QF / capacitance * np.sum(z * residual, axis=1), 1e-13),
        ("resolved_energy_balance_pJ", energy_balance, 1e-10),
    ):
        np.testing.assert_allclose(data["observed_" + field], value, atol=atol, rtol=3e-12)
    np.testing.assert_array_equal(data["observed_leak_multiplier"][:, :, 0], leak_control)
    np.testing.assert_array_equal(data["observed_pump_multiplier"][:, 0], pump_control)
    assert np.min(-leak * mu, initial=0) >= -1e-9
    assert np.min(-cycles * energy, initial=0) >= -1e-9
    return len(expected) + 5


def audit_run(path, case, plan, reference_path, *, branch=False):
    path = Path(path)
    manifest = payloads(path, current=True)
    spec = load_spec(path / "resolved_config.json")
    raw = spec.to_dict()
    assert json.loads(json.dumps(asdict(spec.model))) == json.loads(json.dumps(case["parameters"]))
    assert raw["model"]["id"] == "multispecies_membrane@1"
    assert spec.execution.dt == 0.01
    assert spec.fingerprint == manifest["definition_sha256"]
    assert manifest["observer"] == {"id": model.OBSERVER_ID, "sampling": model.OBSERVATION_SAMPLING}
    assert manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID
    expected_limits = tuple(
        plan["accounting_limits"]["species_material_overrides_fmol"].get(
            s, plan["accounting_limits"]["material_fmol"]
        )
        for s in spec.model.species_ids
    )
    assert spec.execution.material_balance_atol_fmol == expected_limits
    if not branch:
        assert spec.experiment.end_time == case["horizon_s"]
        actual_changes = [
            {"time_s": p.time, "leak": list(p.leak), "pump": p.pump}
            for p in spec.experiment.changes
        ]
        assert actual_changes == json.loads(json.dumps(case["controls"]))
    else:
        assert case["id"] == "divalent_passive_10s" and spec.experiment.end_time == 1.0
        assert all(p.pump == 0 and all(u == 1 for u in p.leak) for p in spec.experiment.changes)
    with np.load(path / "trajectory.npz", allow_pickle=False) as saved:
        data = dict(saved)
    times = data["accepted_times"]
    count = math.ceil(spec.experiment.end_time / spec.execution.dt)
    grid = np.unique(
        np.r_[
            np.arange(count) * spec.execution.dt,
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
        assert len(mesh) >= 2
        queried = oracle | {"sample_times_s": mesh, "sample_state": np.empty_like(values)}
        expected = replay(case, queried, "Radau")
        error = checks.errors(case, values, expected, plan["trajectory_limits"])
        accounting = checks.inspect_samples(case, mesh, values, plan["accounting_limits"])
        assert error["pass"] and accounting["pass"], (group, error, accounting)
        # Account for a restarted suffix without pretending earlier intervals were
        # inspected here. Bounds/anchors remain those of the complete original run.
        event_times = [p.time for p in spec.experiment.changes if mesh[0] < p.time <= mesh[-1]]
        boundaries = [float(mesh[0]), *event_times]
        leak, pump = held_controls(raw, boundaries, spec.model.species_ids)
        clipped = case | {
            "horizon_s": float(mesh[-1]),
            "controls": [
                {"time_s": t, "leak": list(a), "pump": float(b)}
                for t, a, b in zip(boundaries, leak, pump, strict=True)
            ],
        }
        controls = checks.control_checks(clipped, mesh, values)
        assert controls["pass"]
        results[group] = {
            "errors": error,
            "accounting": accounting,
            "controls": controls,
            "rows": len(mesh),
        }
    readouts = inspect_readouts(data, raw, case)
    for relative in manifest["snapshots"]:
        saved = load_snapshot(path / relative)
        row = np.flatnonzero(times == saved.checkpoint.time)
        assert len(row) == 1 and saved.spec == spec
        for field, value in zip(
            saved.checkpoint.state._fields, saved.checkpoint.state, strict=True
        ):
            np.testing.assert_array_equal(value, data[field][row[0]])
        for field, value in zip(
            saved.checkpoint.layout._fields, saved.checkpoint.layout, strict=True
        ):
            np.testing.assert_array_equal(value, data["cell_ids" if field == "ids" else field])
    return data, {
        "reference_case": case["id"],
        "branch": branch,
        "manifest_sha256": sha(path / "manifest.json"),
        "payload_hashes": len(manifest["files_sha256"]),
        "snapshots": len(manifest["snapshots"]),
        "independent_readout_fields": readouts,
        **results,
    }


def audit(path):
    path = Path(path)
    receipt = json.loads((path / "verification.json").read_text())
    assert receipt["status"] == "pass" and not (path / "failure.json").exists()
    assert receipt["source_hashes"] == source_hashes() and receipt["runtime"] == runtime_identity()
    assert {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()} == set(
        receipt["files_sha256"]
    ) | {"verification.json"}
    for name, digest in receipt["files_sha256"].items():
        target = (path / name).resolve()
        assert target.is_relative_to(path.resolve()) and sha(target) == digest
    with zipfile.ZipFile(path / "implementation_sources.zip") as capsule:
        assert set(capsule.namelist()) == set(receipt["implementation_files_sha256"])
        for name, digest in receipt["implementation_files_sha256"].items():
            assert hashlib.sha256(capsule.read(name)).hexdigest() == digest == sha(ROOT / name)
    assert sha(REFERENCE / "verification.json") == REFERENCE_SHA
    reference = json.loads((REFERENCE / "verification.json").read_text())
    for name, digest in reference["files_sha256"].items():
        assert sha(REFERENCE / name) == digest
    plan = json.loads((REFERENCE / "protocol.json").read_text())
    cases = {c["id"]: c for c in json.loads((REFERENCE / "cases.json").read_text())}
    assert set(receipt["runs"]) == {
        f"{mode}/{c}" for mode in ("jit", "eager", "resumed") for c in cases
    } | {"branch/divalent_pulse_omitted"}
    assert receipt["jit_eager_comparison_factor"] == 0.001
    runs, data = {}, {}
    for name, record in receipt["runs"].items():
        case = cases[record["reference_case"]]
        data[name], runs[name] = audit_run(
            path / name, case, plan, REFERENCE / case["id"], branch=record["branch"]
        )
        assert runs[name] == record
    for identity in cases:
        original, resumed = data[f"jit/{identity}"], data[f"resumed/{identity}"]
        start = np.searchsorted(original["accepted_times"], resumed["accepted_times"][0])
        observed = np.searchsorted(original["observation_times"], resumed["accepted_times"][0])
        for key in original:
            expected = (
                original[key][start:]
                if key in model.STATE_TYPE._fields or key == "accepted_times"
                else original[key][observed:]
                if key.startswith("observed_") or key == "observation_times"
                else original[key]
            )
            np.testing.assert_array_equal(resumed[key], expected)
        for prefix in ("", "observed_"):
            assert checks.errors(
                cases[identity],
                canonical(original, cases[identity], prefix),
                canonical(data[f"eager/{identity}"], cases[identity], prefix),
                plan["trajectory_limits"],
                factor=receipt["jit_eager_comparison_factor"],
            )["pass"]
    parent = load_snapshot(path / "branch-parent")
    assert parent.checkpoint.time == 0.203
    branch = data["branch/divalent_pulse_omitted"]
    assert branch["accepted_times"][0] == parent.checkpoint.time
    original = data["jit/divalent_short_pulse"]
    row = np.flatnonzero(original["accepted_times"] == parent.checkpoint.time)[0]
    for field, value in zip(parent.checkpoint.state._fields, parent.checkpoint.state, strict=True):
        np.testing.assert_array_equal(value, original[field][row])
        np.testing.assert_array_equal(value, branch[field][0])
    for field, value in zip(
        parent.checkpoint.layout._fields, parent.checkpoint.layout, strict=True
    ):
        np.testing.assert_array_equal(value, branch["cell_ids" if field == "ids" else field])
    cohorts = {}
    for prefix in ("mono", "divalent"):
        selected = [c for c in cases if c.startswith(prefix)]
        expected = {i + 1: data[f"jit/{c}"] for i, c in enumerate(selected)}
        cohorts[prefix] = audit_cohort(path / "cohorts" / prefix, expected)
        from cells.batch_io import load_batch_snapshot

        saved = load_batch_snapshot(path / "cohorts" / prefix / "snapshots/round-0000000001")
        wanted = {i: suffix(v, saved.checkpoints[i], model) for i, v in expected.items()}
        cohorts[f"resumed/{prefix}"] = audit_cohort(path / "cohort-resumed" / prefix, wanted)
    assert cohorts == receipt["cohorts"]
    return {
        "status": "pass",
        "runs": len(runs),
        "reference_cases": len(cases),
        "fresh_process_restarts": len(cases),
        "cohort_runs": len(cohorts),
        "scalar_snapshots": sum(r["snapshots"] for r in runs.values()),
        "payload_hashes": len(receipt["files_sha256"]),
        "production_sources": len(source_hashes()),
        "maximum_observed_normalized_error": max(
            r["observed"]["errors"]["max_normalized_error"] for r in runs.values()
        ),
        "maximum_voltage_error_V": max(
            r["observed"]["errors"]["errors"]["voltage_V"] for r in runs.values()
        ),
        "verification_sha256": sha(path / "verification.json"),
        "solver_rerun": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
