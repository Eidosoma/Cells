"""Execute pinned sodium-class/update ASTs and retain external source evidence."""

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
from abc import ABCMeta, abstractmethod
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.channels import sodium_catalog_reference as reference

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads((ROOT / "validation/channels/sodium_catalog_protocol.json").read_text())


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def gates(obj, shape):
    return np.stack((np.broadcast_to(obj.m, shape), np.broadcast_to(obj.h, shape)), axis=-2)


def kinetics(obj, shape):
    return (
        np.stack((np.broadcast_to(obj._mInf, shape), np.broadcast_to(obj._hInf, shape)), axis=-2),
        np.stack((np.broadcast_to(obj._mTau, shape), np.broadcast_to(obj._hTau, shape)), axis=-2)
        / obj.time_unit,
    )


def compare(actual, expected, *, tau=False):
    tol = PROTOCOL["tolerances"]
    np.testing.assert_allclose(
        actual,
        expected,
        rtol=tol["native_ordinary_relative"],
        atol=tol["native_tau_atol_s"] if tau else tol["native_gate_atol"],
    )


def native_clamp(namespace, name, output):
    captures, errors = {}, []
    settings = PROTOCOL["clamp_protocol"]
    holding, depolarized = settings["holding_voltage_V"], settings["depolarized_voltage_V"]
    cells, p = SimpleNamespace(mem_i=np.arange(1)), SimpleNamespace(dt=0.0)
    for refinement in settings["native_clock_refinement"]:
        obj = namespace[name]()
        obj.init(np.array([holding]), cells, p)
        exact_initial = reference.kinetics(holding, name)["target"]
        time_offset = 0.0
        initial = gates(obj, (1,))[:, 0]
        saved = [initial.copy()]
        opening = [reference.opening(initial.tolist(), name)]
        expected, expected_opening = (
            [np.asarray(exact_initial)],
            [reference.opening(exact_initial, name)],
        )
        times, phases = [0.0], ["initial"]
        for phase, voltage in (("depolarize", depolarized), ("recover", holding)):
            clock = reference.clamp_clock(voltage, name)
            for left, right in zip(clock, clock[1:], strict=False):
                p.dt = (right - left) / refinement
                for _ in range(refinement):
                    obj.run(np.array([voltage]), p)
                saved.append(gates(obj, (1,))[:, 0].copy())
                opening.append(float(np.asarray(obj.P)[0]))
                exact = reference.relaxation(exact_initial, voltage, name, right)
                expected.append(np.asarray(exact))
                expected_opening.append(reference.opening(exact, name))
                times.append(time_offset + right)
                phases.append(phase)
            exact_initial = reference.relaxation(exact_initial, voltage, name, clock[-1])
            time_offset += clock[-1]
        actual, expected = np.stack(saved), np.stack(expected)
        actual_opening, expected_opening = np.asarray(opening), np.asarray(expected_opening)
        stem = f"native-clamp-{name}-{refinement}"
        np.savez_compressed(
            output / (stem + ".npz"),
            times_s=times,
            gates=actual,
            expected_continuous_gates=expected,
            opening=actual_opening,
            expected_continuous_opening=expected_opening,
        )
        error = float(
            max(
                np.max(np.abs(actual - expected)), np.max(np.abs(actual_opening - expected_opening))
            )
        )
        errors.append(error)
        record = dict(
            status="captured",
            kind="native-backward-Euler-clamp-refinement",
            name=name,
            refinement=refinement,
            voltage_V=[depolarized, holding],
            duration_s=time_offset,
            samples=len(times),
            phases=phases,
            maximum_continuous_error=error,
            segment_duration_rule="12*max(tau_m,tau_h)",
            arrays=stem + ".npz",
        )
        write(output / (stem + ".json"), record)
        assert np.isfinite(actual).all() and np.all((actual >= 0) & (actual <= 1))
        if name == "NaLeak":
            np.testing.assert_array_equal(actual, 1)
            np.testing.assert_array_equal(actual_opening, 1)
        record["status"] = "passed"
        write(output / (stem + ".json"), record)
        captures[str(refinement)] = record
    summary = dict(status="captured", name=name, errors=errors, traces=captures)
    write(output / ("native-clamp-" + name + ".json"), summary)
    if name != "NaLeak":
        assert errors[2] < errors[1] < errors[0]
        assert 0.40 < errors[2] / errors[1] < 0.65
    summary["status"] = "passed"
    write(output / ("native-clamp-" + name + ".json"), summary)


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    source = PROTOCOL["native_probe"]
    installed, checkout = Path(source["installed"]), Path(source["checkout"])
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    manifest = dict(status="capturing", revision=revision, files={})
    write(output / "source-manifest.json", manifest)
    assert revision == PROTOCOL["source_revision"]
    for relative, expected in PROTOCOL["source_files"].items():
        data = (installed / relative).read_bytes()
        target = output / "upstream" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, target)
        manifest["files"][relative] = dict(
            sha256=hashlib.sha256(data).hexdigest(),
            checkout_match=data == (checkout / relative).read_bytes(),
        )
        write(output / "source-manifest.json", manifest)
        assert (
            manifest["files"][relative]["sha256"] == expected
            and manifest["files"][relative]["checkout_match"]
        )
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    version = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert version == PROTOCOL["source_version"]
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        logs=SimpleNamespace(log_info=lambda *_: None),
        __name__="pinned_sodium_probe",
    )
    inherited = ast.parse((installed / "betse/science/channels/channelsabc.py").read_text())
    base = next(
        n for n in inherited.body if isinstance(n, ast.ClassDef) and n.name == "ChannelsABC"
    )
    module = ast.parse((installed / "betse/science/channels/vg_na.py").read_text())
    classes = [n for n in module.body if isinstance(n, ast.ClassDef)]
    assert [n.name for n in classes if n.name != "VgNaABC"] == PROTOCOL["classes"]
    exec(
        compile(
            ast.Module(body=[base], type_ignores=[]),
            str(installed / "betse/science/channels/channelsabc.py"),
            "exec",
        ),
        namespace,
    )
    exec(
        compile(
            ast.Module(body=classes, type_ignores=[]),
            str(installed / "betse/science/channels/vg_na.py"),
            "exec",
        ),
        namespace,
    )
    manifest.update(
        version=version, classes=[n.name for n in classes], native_tissue_simulation=False
    )
    write(output / "source-manifest.json", manifest)
    p = SimpleNamespace(dt=source["update_dt_s"])
    voltage = np.asarray(source["ordinary_voltage_V"])
    cells = SimpleNamespace(mem_i=np.arange(voltage.size))
    for name in PROTOCOL["classes"]:
        obj = namespace[name]()
        record = dict(
            kind="native-sodium-initialization-and-discrete-update",
            status="prepared",
            name=name,
            voltage_V=voltage,
            native_dt_s=p.dt,
            configured_gates=source["initial_gates_for_update_probe"],
        )
        path = output / ("native-ordinary-" + name + ".json")
        write(path, record)
        obj.init(voltage, cells, p)
        initialized = gates(obj, voltage.shape)
        record.update(
            initial_gates=initialized,
            native_P_set_by_init=hasattr(obj, "P"),
            time_unit=float(obj.time_unit),
            gate_powers=[float(obj._mpower), float(obj._hpower)],
            v_corr_mV=float(obj.v_corr),
            nominal_vrev_mV=float(obj.vrev),
        )
        obj._calculate_state(1000 * voltage + obj.v_corr)
        target, tau = kinetics(obj, voltage.shape)
        obj.m, obj.h = (
            np.full_like(voltage, value) for value in source["initial_gates_for_update_probe"]
        )
        obj.run(voltage, p)
        actual = gates(obj, voltage.shape)
        record.update(
            status="actual_captured",
            target=target,
            tau_s=tau,
            after_update=actual,
            native_opening=obj.P,
        )
        write(path, record)
        expected = [reference.kinetics(float(v), name) for v in voltage]
        expected_target = np.asarray([v["target"] for v in expected]).T
        expected_tau = np.asarray([v["tau_s"] for v in expected]).T
        expected_step = np.asarray(
            [
                reference.backward_euler(
                    source["initial_gates_for_update_probe"], float(v), name, p.dt
                )
                for v in voltage
            ]
        ).T
        compare(initialized, expected_target)
        compare(target, expected_target)
        compare(tau, expected_tau, tau=True)
        compare(actual, expected_step)
        compare(obj.P, [reference.opening(g, name) for g in actual.T.tolist()])
        record["status"] = "passed"
        write(path, record)
        # Inherited correction is a source voltage offset, separate from Nav1p2's internal shifts.
        shifted_v = np.array([-0.08, -0.02, 0.0])
        obj = namespace[name]()
        obj.init(shifted_v, cells, p)
        obj.v_corr = 2.0
        obj.run(shifted_v, SimpleNamespace(dt=0.0))
        target, tau = kinetics(obj, shifted_v.shape)
        shifted = dict(
            status="actual_captured",
            kind="native-voltage-correction",
            name=name,
            input_voltage_V=shifted_v,
            v_corr_mV=2.0,
            target=target,
            tau_s=tau,
        )
        shift_path = output / ("native-correction-" + name + ".json")
        write(shift_path, shifted)
        expected = [reference.kinetics(float(v + 0.002), name) for v in shifted_v]
        compare(target, np.asarray([v["target"] for v in expected]).T)
        compare(tau, np.asarray([v["tau_s"] for v in expected]).T, tau=True)
        shifted["status"] = "passed"
        write(shift_path, shifted)
    singular_results = []
    for name, points in reference.SINGULAR_V.items():
        for i, value in enumerate(points):
            record = dict(
                kind="native-singular-source-evidence",
                name=name,
                voltage_V=value,
                millivolt_argument=value * 1000,
                status="prepared",
            )
            path = output / f"native-singular-{name}-{i}.json"
            write(path, record)
            obj = namespace[name]()
            try:
                with np.errstate(all="raise"):
                    obj.init(np.array([value]), cells, p)
                    obj._calculate_state(np.array([value * 1000]))
                    target, tau = kinetics(obj, (1,))
                record.update(native_outcome="finite_at_binary_argument", target=target, tau_s=tau)
            except FloatingPointError as exc:
                record.update(
                    native_outcome="source_singular_failure",
                    error=dict(type=type(exc).__name__, message=str(exc)),
                )
            record.update(
                status="retained", separate_regularized_limit=reference.kinetics(value, name)
            )
            write(path, record)
            singular_results.append(record)
    manifest["singular_cases"] = len(singular_results)
    manifest["native_singular_failures"] = sum(
        v["native_outcome"] == "source_singular_failure" for v in singular_results
    )
    write(output / "source-manifest.json", manifest)
    for name in PROTOCOL["classes"]:
        native_clamp(namespace, name, output)
    manifest.update(
        status="passed",
        ordinary_cases=7,
        correction_cases=7,
        clamp_cases=7,
        clamp_refinements=PROTOCOL["clamp_protocol"]["native_clock_refinement"],
    )
    write(output / "source-manifest.json", manifest)
    print(json.dumps(manifest | dict(files="captured separately")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        capture(args.output)
    except Exception as error:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
