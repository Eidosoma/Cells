"""Execute actual pinned calcium-extra classes and retain native clock/defect evidence."""

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

from validation.channels import calcium_catalog_extra_reference as reference

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads(
    (ROOT / "validation/channels/calcium_catalog_extra_protocol.json").read_text()
)


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def gates(obj, shape):
    return np.stack([np.broadcast_to(v, shape) for v in (obj.m, obj.h)], axis=-2)


def kinetics(obj, shape):
    return (
        np.stack([np.broadcast_to(v, shape) for v in (obj._mInf, obj._hInf)], axis=-2),
        np.stack([np.broadcast_to(v, shape) for v in (obj._mTau, obj._hTau)], axis=-2)
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


def native_clamp(namespace, name, output):
    settings = PROTOCOL["clamp_protocol"]
    holding, depolarized = settings["holding_voltage_V"], settings["depolarized_voltage_V"]
    p, cells = SimpleNamespace(dt=0.0), SimpleNamespace(mem_i=np.arange(1))
    traces, errors = {}, []
    for refinement in settings["native_clock_refinement"]:
        obj = namespace[name]()
        obj.init(np.array([holding]), cells, p)
        expected_initial = reference.kinetics(holding, name)["target"]
        if name == "CaLeak":
            expected_initial = settings["CaLeak_initial_auxiliary_gates"]
            obj.m, obj.h = (np.array([v]) for v in expected_initial)
        actual, expected = [gates(obj, (1,))[:, 0].copy()], [np.asarray(expected_initial)]
        opened, expected_opened = (
            [reference.opening(actual[0].tolist(), name)],
            [reference.opening(expected_initial, name)],
        )
        offset, times, phases, durations = 0.0, [0.0], ["initial"], {}
        for phase, voltage in (("depolarize", depolarized), ("recover", holding)):
            clock = reference.clamp_clock(voltage, name)
            durations[phase] = clock[-1]
            for left, right in zip(clock, clock[1:], strict=False):
                p.dt = (right - left) / refinement
                for _ in range(refinement):
                    obj.run(np.array([voltage]), p)
                exact = reference.relaxation(expected_initial, voltage, name, right)
                actual.append(gates(obj, (1,))[:, 0].copy())
                expected.append(np.asarray(exact))
                opened.append(float(np.asarray(obj.P)[0]))
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
            name=name,
            kind="native-backward-Euler-refinement",
            refinement=refinement,
            segment_duration_s=durations,
            duration_s=offset,
            maximum_continuous_error=error,
            phases=phases,
            arrays=stem + ".npz",
        )
        write(output / (stem + ".json"), record)
        assert np.isfinite(actual).all() and np.all((actual >= 0) & (actual <= 1))
        if name == "CaLeak":
            np.testing.assert_array_equal(opened, 1)
            assert durations == {"depolarize": 12.0, "recover": 12.0}
        record["status"] = "passed"
        write(output / (stem + ".json"), record)
        traces[str(refinement)] = record
    summary = dict(status="captured", name=name, errors=errors, traces=traces)
    write(output / ("native-clamp-" + name + ".json"), summary)
    assert errors[2] < errors[1] < errors[0] and 0.4 < errors[2] / errors[1] < 0.65
    summary["status"] = "passed"
    write(output / ("native-clamp-" + name + ".json"), summary)


def singular_evidence(namespace, output):
    """Retain the upstream failure; never replace it with a regularized pass."""
    cells, p = SimpleNamespace(mem_i=np.arange(1)), SimpleNamespace(dt=0.0002)
    center = np.array([-0.027])
    for phase in ("init", "calculate", "run"):
        obj = namespace["Cav_G"]()
        if phase != "init":
            obj.init(np.array([-0.080]), cells, p)

        def execute(obj, phase=phase):
            if phase == "init":
                obj.init(center, cells, p)
            elif phase == "calculate":
                obj._calculate_state(center * 1000)
            else:
                obj.run(center, p)

        error = None
        try:
            with np.errstate(all="raise"):
                execute(obj)
        except FloatingPointError as exc:
            error = dict(type=type(exc).__name__, message=str(exc))
        record = dict(
            status="captured-native-defect", phase=phase, voltage_V=-0.027, strict_exception=error
        )
        write(output / ("native-singular-" + phase + ".json"), record)
        assert error is not None
        raw = namespace["Cav_G"]()
        if phase != "init":
            raw.init(np.array([-0.080]), cells, p)
        with np.errstate(all="ignore"):
            execute(raw)
        arrays = dict(gates=gates(raw, (1,)))
        if phase != "init":
            arrays.update(zip(("target", "tau_s"), kinetics(raw, (1,)), strict=True))
        if hasattr(raw, "P"):
            arrays["opening"] = raw.P
        np.savez_compressed(output / ("native-singular-" + phase + ".npz"), **arrays)
        record.update(
            raw_array_finite={k: bool(np.isfinite(v).all()) for k, v in arrays.items()},
            regularized_reference=reference.kinetics(-0.027, "Cav_G"),
            arrays="native-singular-" + phase + ".npz",
        )
        assert not all(record["raw_array_finite"].values())
        write(output / ("native-singular-" + phase + ".json"), record)
    voltage = np.array(
        [
            -0.027,
            np.nextafter(-0.027, -np.inf),
            np.nextafter(-0.027, np.inf),
            -0.027 - 1e-15,
            -0.027 + 1e-15,
            -0.027 - 1e-10,
            -0.027 + 1e-10,
        ]
    )
    raw = namespace["Cav_G"]()
    raw.init(np.array([-0.080]), cells, p)
    with np.errstate(all="ignore"):
        raw._calculate_state(1000 * voltage)
    target, tau = kinetics(raw, voltage.shape)
    expected = [reference.kinetics(float(v), "Cav_G") for v in voltage]
    np.savez_compressed(
        output / "native-near-singular.npz",
        voltage_V=voltage,
        target=target,
        tau_s=tau,
        regularized_target=np.asarray([v["target"] for v in expected]).T,
        regularized_tau_s=np.asarray([v["tau_s"] for v in expected]).T,
    )
    write(
        output / "native-near-singular.json",
        dict(
            status="diagnostic-source-conditioning-only",
            voltage_V=voltage,
            all_fields_finite=np.all(np.isfinite(target) & np.isfinite(tau), axis=-2),
            arrays="native-near-singular.npz",
            native_match_claim=False,
        ),
    )


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
        entry = dict(
            sha256=hashlib.sha256(data).hexdigest(),
            checkout_match=data == (checkout / relative).read_bytes(),
        )
        manifest["files"][relative] = entry
        write(output / "source-manifest.json", manifest)
        assert entry["sha256"] == expected and entry["checkout_match"]
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
    module = ast.parse((installed / "betse/science/channels/vg_ca.py").read_text())
    classes = [n for n in module.body if isinstance(n, ast.ClassDef)]
    selected = [n for n in classes if n.name == "VgCaABC" or n.name in PROTOCOL["classes"]]
    assert len(selected) == 5
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        logs=SimpleNamespace(log_info=lambda *_: None),
        __name__="pinned_calcium_extras_probe",
    )
    for nodes, path in (([base], "channelsabc.py"), (selected, "vg_ca.py")):
        exec(
            compile(
                ast.Module(body=nodes, type_ignores=[]),
                str(installed / "betse/science/channels" / path),
                "exec",
            ),
            namespace,
        )
    manifest.update(
        version=version, selected_classes=PROTOCOL["classes"], native_tissue_simulation=False
    )
    source = PROTOCOL["native_probe"]
    voltage = np.asarray(source["ordinary_voltage_V"])
    p, cells = (
        SimpleNamespace(dt=source["update_dt_s"]),
        SimpleNamespace(mem_i=np.arange(voltage.size)),
    )
    metadata_records = {}
    for name in PROTOCOL["classes"]:
        obj = namespace[name]()
        obj.init(voltage, cells, p)
        initialized = gates(obj, voltage.shape)
        obj._calculate_state(1000 * voltage)
        target, tau = kinetics(obj, voltage.shape)
        obj.m, obj.h = (np.full_like(voltage, v) for v in source["initial_gates_for_update_probe"])
        obj.run(voltage, p)
        actual = gates(obj, voltage.shape)
        klass = next(n for n in selected if n.name == name)
        init = next(
            n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == "_init_state"
        )
        texpt = next(
            ast.literal_eval(n.value)
            for n in init.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "Texpt" for t in n.targets)
        )
        record = dict(
            status="captured",
            name=name,
            kind="native-init-and-backward-Euler-update",
            voltage_V=voltage,
            dt_s=p.dt,
            initial_gates=initialized,
            target=target,
            tau_s=tau,
            configured_gates=source["initial_gates_for_update_probe"],
            after_update=actual,
            native_opening=obj.P,
            time_unit=obj.time_unit,
            gate_powers=[obj._mpower, obj._hpower],
            Texpt_C=texpt,
            qt=obj.qt,
            nominal_vrev_mV=obj.vrev,
            ions=obj.ions,
            relative_permeability=obj.rel_perm,
        )
        path = output / ("native-ordinary-" + name + ".json")
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
        quirks = PROTOCOL["source_quirks"][name]
        assert (
            texpt == quirks["Texpt_C"] and obj.qt == quirks["qt"] and obj.vrev == quirks["vrev_mV"]
        )
        assert (
            obj.ions == ["Ca"]
            and obj.rel_perm == [1.0]
            and tuple(record["gate_powers"]) == reference.POWERS[name]
        )
        record["status"] = "passed"
        write(path, record)
        metadata_records[name] = {
            k: record[k] for k in ("Texpt_C", "qt", "nominal_vrev_mV", "time_unit", "gate_powers")
        }
        shifted = np.array([-0.080, -0.020, 0.0])
        obj = namespace[name]()
        obj.init(shifted, cells, p)
        obj.v_corr = source["voltage_correction_mV"]
        obj.run(shifted, SimpleNamespace(dt=0.0))
        target, tau = kinetics(obj, shifted.shape)
        expected = [reference.kinetics(float(v + 0.002), name) for v in shifted]
        compare(target, np.asarray([v["target"] for v in expected]).T)
        compare(tau, np.asarray([v["tau_s"] for v in expected]).T, tau=True)
        write(
            output / ("native-correction-" + name + ".json"),
            dict(
                status="passed",
                name=name,
                input_voltage_V=shifted,
                v_corr_mV=obj.v_corr,
                target=target,
                tau_s=tau,
            ),
        )
        for label, targets in (("reordered", [4, 1]), ("empty", []), ("duplicates", [4, 1, 4])):
            indices = np.asarray(targets, dtype=int)
            obj = namespace[name]()
            obj.init(voltage, cells, p, targets=indices)
            initial = gates(obj, (len(indices),))
            expected_init = (
                np.asarray([reference.kinetics(float(voltage[i]), name)["target"] for i in indices])
                .reshape(-1, 2)
                .T
            )
            compare(initial, expected_init)
            obj.m = np.linspace(0.2, 0.6, len(indices))
            obj.h = np.linspace(0.7, 0.3, len(indices))
            configured = gates(obj, (len(indices),)).copy()
            obj.run(voltage, p)
            after = gates(obj, (len(indices),))
            expected_p = np.zeros(len(voltage))
            for i, index in enumerate(indices):
                expected_gate = reference.backward_euler(
                    configured[:, i].tolist(), float(voltage[index]), name, p.dt
                )
                compare(after[:, i], expected_gate)
                expected_p[index] = reference.opening(expected_gate, name)
            compare(obj.P, expected_p)
            write(
                output / ("native-target-" + name + "-" + label + ".json"),
                dict(
                    status="passed",
                    name=name,
                    targets=indices,
                    initial_gates=initial,
                    after_update=after,
                    full_opening=obj.P,
                    scatter="assignment-last-duplicate-wins",
                ),
            )
        native_clamp(namespace, name, output)
    singular_evidence(namespace, output)
    manifest.update(
        status="passed",
        ordinary_cases=4,
        correction_cases=4,
        target_cases=12,
        clamp_cases=4,
        expected_native_singular_failures=3,
        near_singular_diagnostic_points=7,
        source_metadata=metadata_records,
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
