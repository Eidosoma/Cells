"""Actual pinned remaining-K classes, inherited clock and long-horizon captures."""

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

from validation.channels import potassium_catalog_reference as reference

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads((ROOT / "validation/channels/potassium_catalog_protocol.json").read_text())


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
    t = PROTOCOL["tolerances"]
    np.testing.assert_allclose(
        actual,
        expected,
        rtol=t["native_ordinary_relative"],
        atol=t["native_tau_atol_s"] if tau else t["native_gate_atol"],
    )


def clamp(namespace, name, output):
    summaries, errors = {}, []
    settings = PROTOCOL["clamp_protocol"]
    holding, depolarized = settings["holding_voltage_V"], settings["depolarized_voltage_V"]
    p, cells = SimpleNamespace(dt=0.0), SimpleNamespace(mem_i=np.arange(1))
    for refinement in settings["native_clock_refinement"]:
        obj = namespace[name]()
        obj.init(np.array([holding]), cells, p)
        expected_initial = reference.kinetics(holding, name)["target"]
        offset, times, phases = 0.0, [0.0], ["initial"]
        actual, expected = [gates(obj, (1,))[:, 0].copy()], [np.asarray(expected_initial)]
        opened, expected_opened = (
            [reference.opening(actual[0].tolist(), name)],
            [reference.opening(expected_initial, name)],
        )
        durations = {}
        for phase, voltage in (("depolarize", depolarized), ("recover", holding)):
            clock = reference.clamp_clock(voltage, name)
            durations[phase] = clock[-1]
            for left, right in zip(clock, clock[1:], strict=False):
                p.dt = (right - left) / refinement
                for _ in range(refinement):
                    obj.run(np.array([voltage]), p)
                actual.append(gates(obj, (1,))[:, 0].copy())
                opened.append(float(np.asarray(obj.P)[0]))
                exact = reference.relaxation(expected_initial, voltage, name, right)
                expected.append(np.asarray(exact))
                expected_opened.append(reference.opening(exact, name))
                times.append(offset + right)
                phases.append(phase)
            expected_initial = reference.relaxation(expected_initial, voltage, name, clock[-1])
            offset += clock[-1]
        actual, expected = np.stack(actual), np.stack(expected)
        opened, expected_opened = np.asarray(opened), np.asarray(expected_opened)
        error = float(
            max(np.max(np.abs(actual - expected)), np.max(np.abs(opened - expected_opened)))
        )
        errors.append(error)
        stem = f"native-clamp-{name}-{refinement}"
        np.savez_compressed(
            output / (stem + ".npz"),
            times_s=times,
            gates=actual,
            expected_continuous_gates=expected,
            opening=opened,
            expected_continuous_opening=expected_opened,
        )
        record = dict(
            status="captured",
            kind="native-backward-Euler-clamp-refinement",
            name=name,
            refinement=refinement,
            duration_s=offset,
            segment_duration_s=durations,
            samples=len(times),
            phases=phases,
            maximum_continuous_error=error,
            arrays=stem + ".npz",
        )
        write(output / (stem + ".json"), record)
        assert np.isfinite(actual).all() and np.all((actual >= 0) & (actual <= 1))
        if name == "KLeak":
            np.testing.assert_array_equal(actual, 1)
            np.testing.assert_array_equal(opened, 1)
        if name == "Kv3p3":
            np.testing.assert_allclose(
                durations["recover"],
                86400 * PROTOCOL["source_quirks"]["Kv3p3_12tau_at_minus80mV_days"],
                rtol=PROTOCOL["tolerances"]["horizon_relative"],
                atol=PROTOCOL["tolerances"]["horizon_atol_s"],
            )
        record["status"] = "passed"
        write(output / (stem + ".json"), record)
        summaries[str(refinement)] = record
    summary = dict(status="captured", name=name, errors=errors, traces=summaries)
    write(output / ("native-clamp-" + name + ".json"), summary)
    if name != "KLeak":
        assert errors[2] < errors[1] < errors[0]
        assert 0.40 < errors[2] / errors[1] < 0.65
    summary["status"] = "passed"
    write(output / ("native-clamp-" + name + ".json"), summary)


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    installed, checkout = (Path(PROTOCOL["native_probe"][k]) for k in ("installed", "checkout"))
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
    inherited = ast.parse((installed / "betse/science/channels/channelsabc.py").read_text())
    base = next(
        n for n in inherited.body if isinstance(n, ast.ClassDef) and n.name == "ChannelsABC"
    )
    module = ast.parse((installed / "betse/science/channels/vg_k.py").read_text())
    classes = [n for n in module.body if isinstance(n, ast.ClassDef)]
    remaining = [n.name for n in classes if n.name != "VgKABC" and not n.name.startswith("Kv1")]
    assert set(remaining) == set(PROTOCOL["classes"])
    selected = [n for n in classes if n.name == "VgKABC" or n.name in remaining]
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        logs=SimpleNamespace(log_info=lambda *_: None),
        __name__="pinned_potassium_probe",
    )
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
            ast.Module(body=selected, type_ignores=[]),
            str(installed / "betse/science/channels/vg_k.py"),
            "exec",
        ),
        namespace,
    )
    manifest.update(
        version=version, remaining_concrete_classes=remaining, native_tissue_simulation=False
    )
    write(output / "source-manifest.json", manifest)
    source = PROTOCOL["native_probe"]
    voltage, p = np.asarray(source["ordinary_voltage_V"]), SimpleNamespace(dt=source["update_dt_s"])
    cells = SimpleNamespace(mem_i=np.arange(voltage.size))
    for name in PROTOCOL["classes"]:
        obj = namespace[name]()
        path = output / ("native-ordinary-" + name + ".json")
        record = dict(
            status="prepared",
            name=name,
            kind="native-initialization-and-discrete-update",
            voltage_V=voltage,
            configured_gates=source["initial_gates_for_update_probe"],
            dt_s=p.dt,
        )
        write(path, record)
        with np.errstate(all="raise"):
            obj.init(voltage, cells, p)
            initialized = gates(obj, voltage.shape)
            record.update(
                initial_gates=initialized,
                native_P_set_by_init=hasattr(obj, "P"),
                time_unit=float(obj.time_unit),
                gate_powers=[float(obj._mpower), float(obj._hpower)],
                v_corr_mV=float(obj.v_corr),
                nominal_vrev_mV=float(obj.vrev),
                ions=obj.ions,
                relative_permeability=obj.rel_perm,
            )
            obj._calculate_state(1000 * voltage)
            target, tau = kinetics(obj, voltage.shape)
            obj.m, obj.h = (
                np.full_like(voltage, v) for v in source["initial_gates_for_update_probe"]
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
        compare(initialized, np.asarray([v["target"] for v in expected]).T)
        compare(target, np.asarray([v["target"] for v in expected]).T)
        compare(tau, np.asarray([v["tau_s"] for v in expected]).T, tau=True)
        compare(
            actual,
            np.asarray(
                [
                    reference.backward_euler(
                        source["initial_gates_for_update_probe"], float(v), name, p.dt
                    )
                    for v in voltage
                ]
            ).T,
        )
        compare(obj.P, [reference.opening(g, name) for g in actual.T.tolist()])
        assert obj.ions == ["K"] and obj.rel_perm == [1.0]
        if name == "Kv3p3":
            assert obj.vrev == 82.0
            compare(tau[1, 1], PROTOCOL["source_quirks"]["Kv3p3_tau_h_at_minus80mV_s"], tau=True)
        record["status"] = "passed"
        write(path, record)
        shifted_v = np.array([-0.080, -0.020, 0.0])
        obj = namespace[name]()
        obj.init(shifted_v, cells, p)
        obj.v_corr = 2.0
        obj.run(shifted_v, SimpleNamespace(dt=0.0))
        target, tau = kinetics(obj, shifted_v.shape)
        shifted = dict(
            status="actual_captured",
            name=name,
            kind="native-voltage-correction",
            input_voltage_V=shifted_v,
            v_corr_mV=2.0,
            target=target,
            tau_s=tau,
        )
        path = output / ("native-correction-" + name + ".json")
        write(path, shifted)
        expected = [reference.kinetics(float(v + 0.002), name) for v in shifted_v]
        compare(target, np.asarray([v["target"] for v in expected]).T)
        compare(tau, np.asarray([v["tau_s"] for v in expected]).T, tau=True)
        shifted["status"] = "passed"
        write(path, shifted)
    transition_count = 0
    for name, points in reference.TRANSITIONS_V.items():
        for index, voltage in enumerate(points):
            path = output / f"native-transition-{name}-{index}.json"
            record = dict(
                status="prepared", name=name, kind="smooth-native-transition", voltage_V=voltage
            )
            write(path, record)
            obj = namespace[name]()
            with np.errstate(all="raise"):
                obj.init(np.array([voltage]), cells, p)
                obj._calculate_state(np.array([1000 * voltage]))
            target, tau = kinetics(obj, (1,))
            record.update(status="actual_captured", target=target, tau_s=tau)
            write(path, record)
            expected = reference.kinetics(voltage, name)
            compare(target[:, 0], expected["target"])
            compare(tau[:, 0], expected["tau_s"], tau=True)
            record["status"] = "passed"
            write(path, record)
            transition_count += 1
    for name in PROTOCOL["classes"]:
        clamp(namespace, name, output)
    manifest.update(
        status="passed",
        ordinary_cases=9,
        correction_cases=9,
        clamp_cases=9,
        transition_cases=transition_count,
        native_singular_failures=0,
        source_quirks=PROTOCOL["source_quirks"],
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
    except Exception as exc:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(exc).__name__, message=str(exc)))
        raise
