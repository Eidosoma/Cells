"""Authenticated isolated native Mito execution and source-limit captures."""

import argparse
import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.organelles.betse_mitochondria_fixtures import base, cases, neutral_relaxation
from validation.organelles.betse_mitochondria_reference import evaluate, neutral_profile

PROTOCOL = Path(__file__).with_name("betse_mitochondria_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def write(path, data):
    path.write_text(json.dumps(serial(data), indent=2, allow_nan=False) + "\n")


def state(native, sim):
    return dict(
        cytosol_mM=sim.cc_cells.copy(),
        mitochondria_mM=sim.cc_mit.copy(),
        charge_C=native.Q.copy(),
        voltage_V=native.Vmit.copy(),
    )


def prepared(cls, raw, *, dtype=np.float64, extra=True):
    sim = SimpleNamespace(
        cc_cells=np.asarray(raw["cytosol_mM"], dtype=dtype),
        zs=np.asarray(raw["species_valence"]),
        movingIons=list(raw["moving_species"]),
        cdl=len(raw["cell_volume_m3"]),
        T=raw["temperature_K"],
    )
    cells = SimpleNamespace(
        cell_vol=np.asarray(raw["cell_volume_m3"], float),
        cell_sa=np.asarray(raw["cell_area_m2"], float),
    )
    p = SimpleNamespace(
        cm=raw["specific_capacitance_F_m2"],
        tm=raw["membrane_thickness_m"],
        F=raw["faraday_C_mol"],
        R=raw["gas_constant_J_mol_K"],
        dt=raw["dt_s"],
    )
    native = cls(sim, cells, p)
    initial = dict(
        state(native, sim),
        mit_volume_m3=native.mit_vol.copy(),
        mit_area_m2=native.mit_sa.copy(),
        capacitance_F=native.cm_mit.copy(),
        diffusivity_m2_s=native.Dm_mit.copy(),
        base_diffusivity_m2_s=native.Dm_mit_base.copy(),
        channel_diffusivity_m2_s=native.Dm_channels.copy(),
        charge_valence=native.zmit.copy(),
        extra_charge_exists=hasattr(native, "extra_rho"),
    )
    sim.cc_mit = np.asarray(raw["mitochondria_mM"], dtype=dtype)
    native.Q, native.Vmit = np.asarray(raw["charge_C"], float), np.asarray(raw["voltage_V"], float)
    if extra:
        native.extra_rho = np.asarray(raw["extra_charge_density_C_m3"], float)
    for key, field in (
        ("diffusivity_m2_s", "Dm_mit"),
        ("base_diffusivity_m2_s", "Dm_mit_base"),
        ("channel_diffusivity_m2_s", "Dm_channels"),
    ):
        if key in raw:
            setattr(native, field, np.asarray(raw[key], dtype=dtype))
    if "live_cytosol_volume_m3" in raw:
        cells.cell_vol = np.asarray(raw["live_cytosol_volume_m3"], float)
    if raw.get("refresh_before"):
        native.get_v(sim, p)
    return native, sim, cells, p, initial


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    contract = json.loads(PROTOCOL.read_text())
    source = contract["native_source"]
    checkout, installed = Path(source["checkout"]), Path(source["installed_package"]).parent
    manifest = dict(
        status="capturing",
        source_files={},
        methods={},
        cases=[],
        native_limits=[],
        native_simulation=False,
    )
    write(output / "source-manifest.json", manifest)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest["revision"] = revision
    for relative, expected in source["source_sha256"].items():
        data = (installed / relative).read_bytes()
        copied = output / "upstream" / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, copied)
        observed = hashlib.sha256(data).hexdigest()
        manifest["source_files"][relative] = dict(
            sha256=observed, checkout_match=data == (checkout / relative).read_bytes()
        )
        write(output / "source-manifest.json", manifest)
        assert observed == expected and manifest["source_files"][relative]["checkout_match"]
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    manifest["version"] = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert manifest["version"] == source["version"]
    params = ast.parse((installed / "betse/science/parameters.py").read_text())
    constants = {}
    for node in ast.walk(params):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr in ("F", "R", "tm")
                ):
                    constants[target.attr] = ast.literal_eval(node.value)
    assert constants == dict(F=96485, R=8.314, tm=7.5e-9)
    manifest["native_parameter_constants"] = constants
    toolbox_tree = ast.parse((installed / "betse/science/sim_toolbox.py").read_text())
    functions = [
        n
        for n in toolbox_tree.body
        if isinstance(n, ast.FunctionDef) and n.name in source["executed_toolbox_functions"]
    ]
    ns = dict(np=np)
    exec(
        compile(
            ast.Module(body=functions, type_ignores=[]),
            str(installed / "betse/science/sim_toolbox.py"),
            "exec",
        ),
        ns,
    )
    toolbox = SimpleNamespace(**{n.name: ns[n.name] for n in functions})
    native_tree = ast.parse((installed / "betse/science/organelles/mitochondria.py").read_text())
    cls = next(n for n in native_tree.body if isinstance(n, ast.ClassDef) and n.name == "Mito")
    namespace = dict(np=np, copy=copy, stb=toolbox)
    exec(
        compile(
            ast.Module(body=[cls], type_ignores=[]),
            str(installed / "betse/science/organelles/mitochondria.py"),
            "exec",
        ),
        namespace,
    )
    for node in [*functions, *[n for n in cls.body if isinstance(n, ast.FunctionDef)]]:
        manifest["methods"][node.name] = dict(first_line=node.lineno, last_line=node.end_lineno)
    original_flux = toolbox.electroflux
    for raw in cases():
        native, sim, cells, p, initial = prepared(namespace["Mito"], raw)
        before, calls = state(native, sim), []

        def traced(
            ca, cb, dc, distance, z, voltage, temperature, parameters, rho=1, *, _calls=calls
        ):
            incoming = voltage.copy()
            value = original_flux(ca, cb, dc, distance, z, voltage, temperature, parameters, rho)
            _calls.append(
                dict(voltage_before=incoming, voltage_used=voltage.copy(), flux=value.copy())
            )
            return value

        toolbox.electroflux = traced
        physical_before = (
            toolbox.get_charge(sim.cc_mit, native.zmit, native.mit_vol, p)
            + native.extra_rho * native.mit_vol
        )
        record = dict(
            status="prepared",
            input=raw,
            native_initial=initial,
            before=before,
            physical_charge_before_C=physical_before,
        )
        path = output / (raw["name"] + ".json")
        write(path, record)
        native.update(sim, cells, p)
        fluxes = np.zeros_like(sim.cc_cells)
        for ion, call in zip(sim.movingIons, calls, strict=True):
            fluxes[ion] = call["flux"]
        record.update(
            status="captured",
            after=state(native, sim),
            flux_calls=calls,
            flux_density_mol_m2_s=fluxes,
            transferred_fmol=fluxes * native.mit_sa * p.dt / 1e-15,
            voltage_used_V=np.stack([c["voltage_used"] for c in calls])
            if calls
            else np.empty((0, sim.cdl)),
            cache_charge_adjustment_C=physical_before - before["charge_C"],
        )
        write(path, record)
        expected = evaluate(raw)
        record["reference"] = expected
        write(path, record)
        for key in ("cytosol_mM", "mitochondria_mM", "voltage_V", "charge_C"):
            atol = 3e-22 if key == "charge_C" else 3e-10 if key == "voltage_V" else 3e-12
            np.testing.assert_allclose(record["after"][key], expected[key], rtol=5e-12, atol=atol)
        np.testing.assert_allclose(
            fluxes, expected["flux_density_mol_m2_s"], rtol=5e-12, atol=1e-18
        )
        record["status"] = "passed"
        write(path, record)
        manifest["cases"].append(dict(name=raw["name"], path=str(path), status="passed"))
    toolbox.electroflux = original_flux
    raw = base()
    native, sim, cells, p, _ = prepared(namespace["Mito"], raw)
    history = [state(native, sim)]
    extra_controls, diffusion_controls = [], []
    for index in range(12):
        extra = [0.0] * 3 if index < 4 else [-7500.0, -3500.0, 2000.0]
        multiplier = 1.0 if index < 8 else 0.0
        native.extra_rho = np.asarray(extra)
        native.Dm_mit = np.full_like(native.Dm_mit, 1e-19 * multiplier)
        native.update(sim, cells, p)
        history.append(state(native, sim))
        extra_controls.append(extra)
        diffusion_controls.append(multiplier)
    write(
        output / "short-ordered-trajectory.json",
        dict(
            status="passed",
            input=raw,
            history=history,
            extra_charge_density_C_m3=extra_controls,
            diffusivity_multiplier=diffusion_controls,
            physical_horizon_s=12 * p.dt,
            scope=(
                "Twelve actual native updates with external charge pulse and D block; "
                "no settling claim"
            ),
        ),
    )
    # Source-side failures/limitations, including partially mutated update state.
    for name, operation in (("missing-extra-get-v", "get_v"), ("missing-extra-update", "update")):
        raw = base()
        native, sim, cells, p, _ = prepared(namespace["Mito"], raw, extra=False)
        before = state(native, sim)
        try:
            native.get_v(sim, p) if operation == "get_v" else native.update(sim, cells, p)
        except AttributeError as error:
            record = dict(
                status="observed_native_limit",
                before=before,
                after=state(native, sim),
                exception_type=type(error).__name__,
                message=str(error),
            )
        else:
            raise AssertionError("Raw native missing-extra branch unexpectedly succeeded")
        write(output / (name + ".json"), record)
        manifest["native_limits"].append(name)
    raw = neutral_relaxation()
    raw.update(species_valence=[1], voltage_V=[-1e-25])
    native, sim, cells, p, _ = prepared(namespace["Mito"], raw)
    with np.errstate(all="ignore"):
        native.update(sim, cells, p)
    assert not np.isfinite(sim.cc_mit).all()
    write(
        output / "nonce-singularity.json",
        dict(status="observed_native_limit", input=raw, after=state(native, sim)),
    )
    manifest["native_limits"].append("nonce-singularity")
    raw = base()
    native, sim, cells, p, _ = prepared(namespace["Mito"], raw)
    native.remove_mits(sim, [1])
    sim.cc_cells, sim.cdl = np.delete(sim.cc_cells, [1], axis=1), 2
    cells.cell_vol, cells.cell_sa = np.delete(cells.cell_vol, [1]), np.delete(cells.cell_sa, [1])
    try:
        native.update(sim, cells, p)
    except ValueError as error:
        record = dict(
            status="observed_native_limit",
            after=state(native, sim),
            extra_rho=native.extra_rho,
            remaining_mito_volume=native.mit_vol,
            exception_type=type(error).__name__,
            message=str(error),
        )
    else:
        raise AssertionError("Native deletion unexpectedly resized extra_rho")
    write(output / "untrimmed-extra-after-removal.json", record)
    manifest["native_limits"].append("untrimmed-extra-after-removal")
    for label, dtype in (("integer-initialization", np.int64), ("float32-precision", np.float32)):
        raw = neutral_relaxation()
        raw["dt_s"] = 0.001
        native, sim, cells, p, initial = prepared(namespace["Mito"], raw, dtype=dtype)
        before = state(native, sim)
        native.update(sim, cells, p)
        if label == "integer-initialization":
            assert np.all(native.Dm_mit == 0)
        else:
            assert float(native.Dm_mit[0, 0]) != 1e-19
        write(
            output / (label + ".json"),
            dict(
                status="observed_native_limit",
                before=before,
                after=state(native, sim),
                native_initial=initial,
                dtype=str(np.dtype(dtype)),
            ),
        )
        manifest["native_limits"].append(label)
    raw = neutral_relaxation()
    raw["dt_s"] = 1e6
    native, sim, cells, p, _ = prepared(namespace["Mito"], raw)
    native.update(sim, cells, p)
    assert np.any(sim.cc_mit < 0)
    write(
        output / "unguarded-negative-euler.json",
        dict(status="observed_native_limit", input=raw, after=state(native, sim)),
    )
    manifest["native_limits"].append("unguarded-negative-euler")
    # Actual native reduced physical trajectories, three explicit-Euler steps.
    raw = neutral_relaxation()
    plan = neutral_profile(raw, [0.0])
    profiles = []
    write(
        output / "neutral-physical-plan.json",
        dict(
            input=raw, **plan, counts=[32, 64, 128], horizon_tau_multiples=12, native_default_D=True
        ),
    )
    for count in (32, 64, 128):
        row = copy.deepcopy(raw)
        row["dt_s"] = plan["tau_s"] / count
        native, sim, cells, p, _ = prepared(namespace["Mito"], row)
        times, values = [0.0], [[float(sim.cc_cells[0, 0]), float(sim.cc_mit[0, 0])]]
        for index in range(1, 12 * count + 1):
            native.update(sim, cells, p)
            times.append(index * p.dt)
            values.append([float(sim.cc_cells[0, 0]), float(sim.cc_mit[0, 0])])
        expected = neutral_profile(row, times)
        errors = np.abs(np.asarray(values) - np.asarray(expected["concentration_mM"]))
        profile = dict(
            status="passed",
            input=row,
            times_s=times,
            concentration_mM=values,
            analytic=expected,
            max_error_mM=float(errors.max()),
            tau_s=plan["tau_s"],
            horizon_s=times[-1],
            scope="Neutral fixed native geometry only; no full mitochondrial settling",
        )
        write(output / ("neutral-physical-" + str(count) + ".json"), profile)
        profiles.append(profile["max_error_mM"])
    assert profiles[1] < profiles[0] / 1.9 and profiles[2] < profiles[1] / 1.9
    manifest["neutral_physical"] = dict(
        tau_s=plan["tau_s"], horizon_s=plan["horizon_s"], max_errors_mM=profiles
    )
    assert not any(
        n == "cells" or n.startswith("cells.") or n == "jax" or n.startswith("jax.")
        for n in sys.modules
    )
    manifest.update(
        status="passed",
        no_production_or_jax_imports=True,
        successful_cases=len(manifest["cases"]),
        observed_native_limits=len(manifest["native_limits"]),
    )
    write(output / "source-manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="passed",
                cases=manifest["successful_cases"],
                source_limits=manifest["observed_native_limits"],
                physical=manifest["neutral_physical"],
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        capture(args.output)
    except Exception as error:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
