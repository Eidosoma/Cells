"""CORE-010 saved scalar arrays: independent equations, not a production oracle.

Production spec/layout/checkpoint loaders provide structural identity only.
The physical oracle is NUM-010's separately written instantaneous field evaluator
and saved refined polynomial. No trajectory integrator is invoked here.
"""

import math
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np

from cells.core.specs import load_spec, read_json
from cells.io import _sha256 as sha
from cells.io import load_snapshot, runtime_identity, source_hashes
from cells.models import spatial_extracellular as model
from tests import spatial_extracellular_fields as fields
from tests import spatial_extracellular_numerical_checks as checks
from tests import spatial_extracellular_numerical_data as data
from tests.spatial_extracellular_fixtures import canonical, load_reference, spec_for

require = checks.require
STATE_FIELDS = model.STATE_TYPE._fields
LAYOUT_FIELDS = tuple("cell_ids" if k == "ids" else k for k in model.LAYOUT_TYPE._fields)
OBS_FIELDS = tuple("observed_" + k for k in model.Observations.__dataclass_fields__ if k != "times")
ARRAY_FIELDS = {"accepted_times", "observation_times", *STATE_FIELDS, *LAYOUT_FIELDS, *OBS_FIELDS}
MANIFEST_FIELDS = {
    "schema_version",
    "status",
    "created_utc",
    "definition_sha256",
    "runtime",
    "source_hashes",
    "device",
    "cpu_affinity",
    "observer",
    "numerics",
    "random_state",
    "timings",
    "timing_scope",
    "provenance",
    "snapshots",
    "files_sha256",
}


def evidence_path(root, name):
    root, relative = Path(root).absolute(), Path(name)
    require(
        isinstance(name, str)
        and name == relative.as_posix()
        and not relative.is_absolute()
        and bool(relative.parts)
        and not {"..", "."}.intersection(relative.parts),
        "Invalid evidence path",
    )
    target = root
    require(not root.is_symlink(), "Linked evidence root")
    for part in relative.parts:
        target = target / part
        require(not target.is_symlink(), "Linked evidence path")
    require(target.resolve().is_relative_to(root.resolve()), "Escaping evidence path")
    require(target.is_file() and target.stat().st_nlink == 1, "Missing or multiply-linked evidence")
    return target


def authenticate(root, identity, *, extra=()):
    root = Path(root)
    require(isinstance(identity, dict) and bool(identity), "Missing evidence inventory")
    for p in root.rglob("*"):
        require(not p.is_symlink(), "Linked evidence tree")
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    require(actual == set(identity) | set(extra), "Evidence file coverage changed")
    for name, value in identity.items():
        require(sha(evidence_path(root, name)) == value, f"Evidence hash differs: {name}")
    for name in extra:
        evidence_path(root, name)


def numeric_archive(path, expected):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Duplicate numeric archive members")
        require(set(names) == {k + ".npy" for k in expected}, "Numeric fields changed")
        require(sum(p.file_size for p in archive.infolist()) <= 2**30, "Numeric archive budget")
        require(all(not p.is_dir() for p in archive.infolist()), "Numeric archive directory")
    with np.load(path, allow_pickle=False) as saved:
        result = dict(saved)
    require(all(np.isfinite(v).all() for v in result.values()), "Nonfinite numeric payload")
    return result


def state_values(case, arrays, prefix=""):
    return canonical(case, {k: arrays[prefix + k] for k in STATE_FIELDS})


def independent_readouts(case, times, values):
    """All physical outputs in real-owner order, without production field/observer calls."""
    g, p, rt = case.g, case.layout.split(values), data.R * case.g.temperature
    n = g.initial + p["amount"]
    c = n / g.volume[:, None]
    rows = [
        fields.independent(case, case.control_at(float(t)), y)
        for t, y in zip(times, values, strict=True)
    ]
    phi = np.asarray([m["potential_V"] for _, m in rows]).reshape(len(times), len(g.ids))
    rates = case.layout.split(np.asarray([r for r, _ in rows]).reshape(len(times), case.size))
    inside = [
        i
        for i, entry in enumerate(case.raw["world"]["compartments"])
        if entry["kind"] == "intracellular"
    ]
    outside = list(case.outside)
    vm, vf = phi @ g.bm, phi @ g.bf
    membrane_mu = np.empty((len(times), len(g.membrane_pairs), len(g.z)))
    face_mu, weight, logs = (np.empty((len(times), len(g.face_pairs), len(g.z))) for _ in range(3))
    for e, (u, v) in enumerate(g.membrane_pairs):
        membrane_mu[:, e] = rt * (np.log(c[:, u]) - np.log(c[:, v])) + data.F * g.z * vm[:, e, None]
    for e, (u, v) in enumerate(g.face_pairs):
        a, b = c[:, u], c[:, v]
        ratio = (a - b) / (a + b)
        near = np.abs(ratio) < 0.5
        log = np.where(near, 2 * np.arctanh(np.where(near, ratio, 0.0)), np.log(a) - np.log(b))
        mean = np.where(a == b, a, (a - b) / np.where(a == b, 1.0, log))
        weight[:, e], logs[:, e] = g.face_factor[e] * mean, log
        face_mu[:, e] = rt * log + data.F * g.z * vf[:, e, None]
    conductance = data.F**2 / rt * np.sum(weight * g.z**2, axis=-1)
    diffusion = data.F * np.sum(weight * logs * g.z, axis=-1)
    drift = conductance * vf
    membrane_flux, face_flux = rates["membrane_transfer"], rates["face_transfer"]
    current = data.QF * np.sum(face_flux * g.z, axis=-1)
    # Reference capacitance components have their own ordering. Public current
    # and charge arrays are indexed by outside owner, not by component column.
    residual = current @ g.bf[outside].T
    current_scale = np.maximum(
        np.max(np.abs(diffusion), axis=-1, initial=0), np.max(np.abs(drift), axis=-1, initial=0)
    )
    material = (
        p["amount"]
        + np.einsum("nm,tms->tns", g.bm, p["membrane_transfer"])
        + np.einsum("ne,tes->tns", g.bf, p["face_transfer"])
    )
    node_charge = g.initial_charge + data.QF * (p["amount"] @ g.z)
    charge = node_charge[:, outside].copy()
    for u, v in g.membrane_pairs:
        charge[:, outside.index(v)] += node_charge[:, u]
    return {
        "amount": n[:, inside].swapaxes(-1, -2),
        "extracellular_amount": n[:, outside].swapaxes(-1, -2),
        "concentration_mM": c[:, inside].swapaxes(-1, -2),
        "extracellular_concentration_mM": c[:, outside].swapaxes(-1, -2),
        "cell_potential_V": phi[:, inside],
        "extracellular_potential_V": phi[:, outside],
        "membrane_voltage_V": vm,
        "membrane_availability": np.asarray(
            [case.control_at(float(t)).availability for t in times]
        ).reshape(len(times), len(g.membrane_pairs)),
        "membrane_flux_fmol_per_s": membrane_flux.swapaxes(-1, -2),
        "membrane_current_A": data.QF * np.sum(membrane_flux * g.z, axis=-1),
        "membrane_delta_mu_J_per_mol": membrane_mu.swapaxes(-1, -2),
        "membrane_dissipation_rate_pJ_per_s": rates["membrane_dissipation"],
        "face_flux_fmol_per_s": face_flux.swapaxes(-1, -2),
        "face_delta_mu_J_per_mol": face_mu.swapaxes(-1, -2),
        "face_conductance_S": conductance,
        "face_diffusion_current_A": diffusion,
        "face_drift_current_A": drift,
        "face_current_A": current,
        "current_residual_A": residual,
        "current_normalized": np.max(np.abs(residual), axis=-1, initial=0)
        / (1e-23 + 2e-12 * current_scale),
        "face_dissipation_rate_pJ_per_s": rates["face_dissipation"],
        "species_balance_fmol": material[:, inside].swapaxes(-1, -2),
        "extracellular_species_balance_fmol": material[:, outside].swapaxes(-1, -2),
        "global_species_balance_fmol": np.sum(p["amount"], axis=1),
        "component_charge_C": charge,
        "energy_balance_pJ": checks.energy_change(case, values)
        + np.sum(p["membrane_dissipation"], axis=-1)
        + np.sum(p["face_dissipation"], axis=-1),
    }


def inspect_readouts(case, arrays):
    expected = independent_readouts(
        case, arrays["observation_times"], state_values(case, arrays, "observed_")
    )
    require(
        set(expected) == set(model.Observations.__dataclass_fields__) - {"times", *STATE_FIELDS},
        "Incomplete independent readout coverage",
    )
    unpadded = {"global_species_balance_fmol", "energy_balance_pJ", "current_normalized"}
    for name, wanted in expected.items():
        actual = arrays["observed_" + name]
        require(actual.dtype == np.float64, f"Readout dtype: {name}")
        if name not in unpadded:
            require(
                actual.ndim == wanted.ndim
                and actual.shape[:-1] == wanted.shape[:-1]
                and actual.shape[-1] >= wanted.shape[-1],
                f"Readout shape: {name}",
            )
            require(np.all(actual[..., wanted.shape[-1] :] == 0), f"Readout padding: {name}")
            actual = actual[..., : wanted.shape[-1]]
        require(actual.shape == wanted.shape, f"Readout extent: {name}")
        if name == "current_normalized":
            # Independent solves have different last-bit cancellation in an almost-zero current.
            require(np.all((actual >= 0) & (actual <= 1)), "Invalid current normalization")
            continue
        atol = (
            1e-23
            if name.endswith(("_A", "_C", "_S"))
            else 1e-8
            if name.endswith("_J_per_mol")
            else 1e-11
            if name.endswith(("_per_s", "_pJ"))
            else 3e-13
        )
        if name == "membrane_availability":
            np.testing.assert_array_equal(actual, wanted)
        if name in {"face_current_A", "current_residual_A"}:
            # A cancellation-dominated current inherits the already checked
            # species-flux error, not a relative tolerance on its near-zero sum.
            flux = expected["face_flux_fmol_per_s"]
            bound = data.QF * np.sum(
                np.abs(case.g.z)[None, :, None] * (1e-11 + 3e-12 * np.abs(flux)), axis=1
            )
            if name == "current_residual_A":
                bound = bound @ np.abs(case.g.bf[list(case.outside)]).T
            require(
                np.all(np.abs(actual - wanted) <= atol + bound), f"Current forward error: {name}"
            )
        else:
            np.testing.assert_allclose(actual, wanted, atol=atol, rtol=3e-12, err_msg=name)
    face_current = arrays["observed_face_current_A"][:, : len(case.g.face_pairs)]
    flux = arrays["observed_face_flux_fmol_per_s"][:, :, : len(case.g.face_pairs)]
    expected_current = data.QF * np.sum(case.g.z[None, :, None] * flux, axis=1)
    np.testing.assert_allclose(face_current, expected_current, atol=1e-30, rtol=3e-12)
    residual = face_current @ case.g.bf[list(case.outside)].T
    actual_residual = arrays["observed_current_residual_A"][:, : len(case.outside)]
    np.testing.assert_allclose(actual_residual, residual, atol=1e-30, rtol=3e-12)
    scale = np.maximum(
        *[
            np.max(np.abs(arrays["observed_face_" + k + "_current_A"]), axis=-1, initial=0)
            for k in ("diffusion", "drift")
        ]
    )
    wanted_normalized = np.max(np.abs(residual), axis=-1, initial=0) / (1e-23 + 2e-12 * scale)
    np.testing.assert_allclose(
        arrays["observed_current_normalized"], wanted_normalized, atol=1e-12, rtol=3e-12
    )
    return len(expected)


def inspect_dense(case, arrays):
    times, values = arrays["accepted_times"], state_values(case, arrays)
    if len(times) == 1:
        expected = np.broadcast_to(values[0], (len(arrays["observation_times"]), case.size))
        np.testing.assert_array_equal(state_values(case, arrays, "observed_"), expected)
        return {"pass": True, "intervals": 0}
    f0, f1 = (
        np.asarray(
            [
                fields.independent(case, case.control_at(float(t)), y)[0]
                for t, y in zip(times[:-1], values[part], strict=True)
            ]
        )
        for part in (slice(None, -1), slice(1, None))
    )
    h, delta = np.diff(times)[:, None], values[1:] - values[:-1]
    coefficients = np.stack(
        (values[:-1], h * f0, 3 * delta - h * (2 * f0 + f1), -2 * delta + h * (f0 + f1)), axis=-1
    )
    domain = checks.cubic_domain(case, {"coefficients": coefficients, "native_times_s": times})
    require(domain["pass"], "Independent full cubic domain failed")
    sample = arrays["observation_times"]
    at = np.clip(np.searchsorted(times, sample, side="right") - 1, 0, len(times) - 2)
    theta = (sample - times[at]) / (times[at + 1] - times[at])
    c = coefficients[at]
    expected = c[:, :, 0] + theta[:, None] * (
        c[:, :, 1] + theta[:, None] * (c[:, :, 2] + theta[:, None] * c[:, :, 3])
    )
    indices = np.searchsorted(times, sample)
    exact = times[indices] == sample
    expected[exact] = values[indices[exact]]
    np.testing.assert_allclose(
        state_values(case, arrays, "observed_"), expected, atol=3e-13, rtol=3e-12
    )
    return domain | {"intervals": len(times) - 1}


def inspect_arrays(case, spec, arrays, plan):
    require(set(arrays) == ARRAY_FIELDS, "Incomplete scalar arrays")
    require(all(np.isfinite(a).all() for a in arrays.values()), "Nonfinite scalar arrays")
    require(spec.model == spec_for(case).model, "Physical definition differs from reference")
    require(spec.experiment.end_time == case.horizon_s, "Physical horizon differs")
    require(
        spec.experiment.membranes == spec_for(case).experiment.membranes, "Physical controls differ"
    )
    require(spec.execution.dt in (0.000125, 0.0000625), "Unqualified acceptance step")
    require(
        spec.execution.material_balance_atol_fmol == (1e-10,) * len(case.g.z),
        "Accounting tolerance changed",
    )
    state, layout = model.initial_values(spec)
    for key, target in zip(LAYOUT_FIELDS, layout, strict=True):
        require(
            arrays[key].shape == target.shape and arrays[key].dtype == target.dtype,
            f"Geometry shape/dtype: {key}",
        )
        np.testing.assert_array_equal(arrays[key], target, err_msg=key)
    times, sample = arrays["accepted_times"], arrays["observation_times"]
    require(
        times.ndim == sample.ndim == 1
        and times.dtype == sample.dtype == np.float64
        and len(times) > 0,
        "Invalid numeric clocks",
    )
    grid = data.candidate_grid(case, spec.execution.dt)
    require(times[0] in grid, "Non-native start time")
    np.testing.assert_array_equal(times, grid[grid >= times[0]])
    np.testing.assert_array_equal(
        sample, [t for t in spec.experiment.observation_times if t >= times[0]]
    )
    counts = (
        len(spec.model.cells),
        len(case.outside),
        len(case.g.membrane_pairs),
        len(case.g.face_pairs),
        len(case.g.membrane_pairs),
        len(case.g.face_pairs),
    )
    oracle = load_reference(case)
    records = {}
    for group, mesh, prefix in (("native", times, ""), ("observed", sample, "observed_")):
        for key, target, count in zip(STATE_FIELDS, state, counts, strict=True):
            actual = arrays[prefix + key]
            require(
                actual.shape == (len(mesh), *target.shape) and actual.dtype == np.float64,
                f"State shape/dtype: {key}",
            )
            require(np.all(actual[..., count:] == 0), f"Nonzero state padding: {key}")
        values = state_values(case, arrays, prefix)
        if len(mesh) and mesh[0] == 0:
            np.testing.assert_array_equal(values[0], np.zeros(case.size))
        accounting, phi = checks.inspect(case, mesh, values, plan["accounting_limits"])
        wanted = checks.replay(case, oracle, "Radau", mesh)
        wanted_phi = checks.potential_values(case, mesh, wanted)[0]
        errors = checks.errors(case, values, wanted, phi, wanted_phi, plan["trajectory_limits"])
        require(
            accounting["pass"] and errors["pass"],
            f"Independent {group} check failed: {accounting}, {errors}",
        )
        if len(mesh) > 1:
            # Only the recorded suffix is available; keep its actual held initial control.
            controls = (replace(case.control_at(float(mesh[0])), time_s=float(mesh[0])),) + tuple(
                c for c in case.controls if mesh[0] < c.time_s <= mesh[-1]
            )
            clipped = replace(case, controls=controls, horizon_s=float(mesh[-1]))
            blocked = checks.blocked_checks(clipped, mesh, values)
            require(blocked["pass"], "Blocked history changed")
        else:
            blocked = {"pass": True, "intervals": []}
        records[group] = {
            "rows": len(mesh),
            "accounting": accounting,
            "errors": errors,
            "blocked": blocked,
        }
    return records | {
        "independent_readout_fields": inspect_readouts(case, arrays),
        "dense_domain": inspect_dense(case, arrays),
    }


def inspect_checkpoint(path, spec, arrays):
    numeric_archive(evidence_path(path, "state.npz"), {*STATE_FIELDS, *model.LAYOUT_TYPE._fields})
    saved = load_snapshot(path)
    require(saved.spec == spec, "Checkpoint definition differs from run")
    at = np.flatnonzero(arrays["accepted_times"] == saved.checkpoint.time)
    require(len(at) == 1, "Checkpoint not on recorded grid")
    for k, v in zip(STATE_FIELDS, saved.checkpoint.state, strict=True):
        np.testing.assert_array_equal(v, arrays[k][at[0]], err_msg=k)
    for k, v in zip(LAYOUT_FIELDS, saved.checkpoint.layout, strict=True):
        np.testing.assert_array_equal(v, arrays[k], err_msg=k)
    return saved


def audit_run(path, case, plan, *, expected_spec=None):
    path = Path(path)
    manifest = read_json(evidence_path(path, "manifest.json"))
    require(set(manifest) == MANIFEST_FIELDS, "Scalar manifest fields changed")
    require(
        type(manifest["schema_version"]) is int
        and manifest["schema_version"] == 1
        and manifest["status"] == "complete",
        "Incomplete scalar run",
    )
    require(
        manifest["source_hashes"] == source_hashes() and manifest["runtime"] == runtime_identity(),
        "Scalar source/runtime differs",
    )
    snapshots = manifest["snapshots"]
    require(
        isinstance(snapshots, list)
        and len(snapshots) == len(set(snapshots))
        and "checkpoint_final" in snapshots,
        "Incomplete checkpoint list",
    )
    require(
        set(manifest["files_sha256"])
        == {
            "trajectory.npz",
            "resolved_config.json",
            "summary.json",
            *(f"{p}/{f}" for p in snapshots for f in ("state.npz", "manifest.json")),
        },
        "Scalar payload schema differs",
    )
    authenticate(path, manifest["files_sha256"], extra=("manifest.json",))
    spec = load_spec(path / "resolved_config.json")
    if expected_spec is not None:
        require(spec == expected_spec, "Registered scalar definition differs")
    require(spec.fingerprint == manifest["definition_sha256"], "Scalar definition identity differs")
    require(
        manifest["observer"] == {"id": model.OBSERVER_ID, "sampling": model.OBSERVATION_SAMPLING},
        "Observer identity differs",
    )
    require(
        manifest["numerics"]
        == {
            "grid": "zero_anchored_event_split",
            "jit": spec.execution.jit,
            "stage_domain": model.STAGE_DOMAIN_ID,
        },
        "Numerical identity differs",
    )
    require(manifest["random_state"] == "unused: deterministic model", "Unexpected random state")
    require(
        all(math.isfinite(v) and v >= 0 for v in manifest["timings"].values()),
        "Invalid scalar timing",
    )
    arrays = numeric_archive(path / "trajectory.npz", ARRAY_FIELDS)
    records = inspect_arrays(case, spec, arrays, plan)
    for name in snapshots:
        inspect_checkpoint(path / name, spec, arrays)
    summary = read_json(path / "summary.json")
    require(
        summary["status"] == "complete"
        and summary["start_time"] == arrays["accepted_times"][0]
        and summary["end_time"] == case.horizon_s
        and summary["executed_steps"] == len(arrays["accepted_times"]) - 1,
        "Scalar summary clock differs",
    )
    return arrays, records | {
        "reference_case": case.id,
        "manifest_sha256": sha(path / "manifest.json"),
        "snapshots": len(snapshots),
    }
