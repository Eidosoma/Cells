"""Actual wired Morris–Lecar classes, native clocks and instantaneous steps."""

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

from validation.channels import morris_lecar_channels_reference as reference

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads(
    (ROOT / "validation/channels/morris_lecar_channels_protocol.json").read_text()
)


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def compare(actual, expected):
    t = PROTOCOL["tolerances"]
    np.testing.assert_allclose(actual, expected, rtol=t["native_relative"], atol=t["native_atol"])


def clamp(namespace, name, output):
    settings = PROTOCOL["clamp_protocol"]
    holding = settings["holding_voltage_V"]
    cells, p = SimpleNamespace(mem_i=np.arange(1)), SimpleNamespace(dt=0.0)
    errors, traces = [], {}
    for refinement in settings["native_refinements"]:
        obj = namespace[name]()
        obj.init(np.array([holding]), cells, p)
        start = reference.kinetics(holding, name)["target"]
        actual, exact = [float(obj.m[0])], [start]
        offset, times, durations = 0.0, [0.0], {}
        for phase, voltage in (
            ("depolarize", settings["depolarized_voltage_V"]),
            ("recover", holding),
        ):
            clock = reference.clamp_clock(voltage, name)
            durations[phase] = clock[-1]
            for left, right in zip(clock, clock[1:], strict=False):
                p.dt = (right - left) / refinement
                for _ in range(refinement):
                    obj.run(np.array([voltage]), p)
                actual.append(float(obj.P[0]))
                exact.append(reference.relaxation(start, voltage, name, right))
                times.append(offset + right)
            start = reference.relaxation(start, voltage, name, clock[-1])
            offset += clock[-1]
        actual, exact = np.asarray(actual), np.asarray(exact)
        error = float(np.max(np.abs(actual - exact)))
        errors.append(error)
        stem = f"native-clamp-{name}-{refinement}"
        np.savez_compressed(
            output / (stem + ".npz"), times_s=times, opening=actual, continuous_opening=exact
        )
        record = dict(
            status="captured",
            name=name,
            refinement=refinement,
            duration_s=offset,
            segment_duration_s=durations,
            maximum_continuous_error=error,
            arrays=stem + ".npz",
        )
        write(output / (stem + ".json"), record)
        assert np.all(np.isfinite(actual) & (actual >= 0) & (actual <= 1))
        record["status"] = "passed"
        write(output / (stem + ".json"), record)
        traces[str(refinement)] = record
    assert errors[2] < errors[1] < errors[0] and 0.4 < errors[2] / errors[1] < 0.65
    write(
        output / ("native-clamp-" + name + ".json"),
        dict(status="passed", name=name, errors=errors, traces=traces),
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
    module = ast.parse((installed / "betse/science/channels/vg_morrislecar.py").read_text())
    classes = [n for n in module.body if isinstance(n, ast.ClassDef)]
    assert {n.name for n in classes} == {"VgKABC", *PROTOCOL["classes"]}
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        logs=SimpleNamespace(log_info=lambda *_: None),
        __name__="pinned_morris_lecar_probe",
    )
    for nodes, path in (([base], "channelsabc.py"), (classes, "vg_morrislecar.py")):
        exec(
            compile(
                ast.Module(body=nodes, type_ignores=[]),
                str(installed / "betse/science/channels" / path),
                "exec",
            ),
            namespace,
        )
    network = (installed / "betse/science/chemistry/networks.py").read_text()
    assert "from betse.science.channels import vg_morrislecar as vgml" in network
    assert "class_string = vgml" in network and "getattr(class_string,type_string)()" in network
    assert (
        "channel_core.init(sim.vm, cells, p" in network and "channel_core.run(sim.vm, p)" in network
    )
    write(
        output / "active-call-sites.json",
        dict(
            status="inspected",
            source="betse/science/chemistry/networks.py",
            factory_selection=True,
            channel_init=True,
            channel_run=True,
            whole_network_simulation=False,
        ),
    )
    settings = PROTOCOL["native_probe"]
    voltage = np.asarray(settings["ordinary_voltage_V"])
    cells, p = (
        SimpleNamespace(mem_i=np.arange(len(voltage))),
        SimpleNamespace(dt=settings["update_dt_s"]),
    )
    for name in PROTOCOL["classes"]:
        obj = namespace[name]()
        obj.init(voltage, cells, p)
        initialized = np.asarray(obj.m).copy()
        obj._calculate_state(voltage * 1000)
        target = np.broadcast_to(obj._mInf, voltage.shape)
        raw_tau = np.broadcast_to(obj._mTau, voltage.shape)
        obj.m = np.full_like(voltage, settings["initial_m_for_update"])
        obj.run(voltage, p)
        record = dict(
            status="captured",
            name=name,
            voltage_V=voltage,
            initial_m=initialized,
            target=target,
            raw_tau=raw_tau,
            phi=obj.Phi,
            time_unit=obj.time_unit,
            kinetic_gate=obj.kinetic_gate,
            ions=obj.ions,
            relative_permeability=obj.rel_perm,
            vrev_mV=obj.vrev,
            dt_s=p.dt,
            updated_m=obj.m,
            native_P=obj.P,
        )
        path = output / ("native-ordinary-" + name + ".json")
        write(path, record)
        expected = [reference.kinetics(float(v), name) for v in voltage]
        compare(initialized, [v["target"] for v in expected])
        compare(target, [v["target"] for v in expected])
        compare(raw_tau, [v["raw_tau"] for v in expected])
        compare(obj.Phi, expected[0]["phi"])
        assert obj.time_unit == 1000 and obj.kinetic_gate == (name in reference.KINETIC)
        assert tuple(zip(obj.ions, obj.rel_perm, strict=True)) == reference.PERMEABILITIES[name]
        compare(
            obj.P,
            [
                reference.native_update(settings["initial_m_for_update"], float(v), name, p.dt)
                for v in voltage
            ],
        )
        record["status"] = "passed"
        write(path, record)
        for label, indices in (("reordered", [4, 1]), ("duplicates", [4, 1, 4]), ("empty", [])):
            targets = np.asarray(indices, dtype=int)
            obj = namespace[name]()
            obj.init(voltage, cells, p, targets=targets)
            obj.m = np.full(len(targets), 0.2)
            obj.run(voltage, p)
            expected = np.zeros(len(voltage))
            for index in targets:
                expected[index] = reference.native_update(0.2, float(voltage[index]), name, p.dt)
            compare(obj.P, expected)
            write(
                output / ("native-target-" + name + "-" + label + ".json"),
                dict(
                    status="passed",
                    name=name,
                    targets=targets,
                    opening=obj.P,
                    assignment_scatter=True,
                ),
            )
        if name in reference.KINETIC:
            clamp(namespace, name, output)
        else:
            rows = []
            for dt in PROTOCOL["clamp_protocol"]["instantaneous_dt_s"]:
                obj = namespace[name]()
                obj.init(np.array([-0.080]), cells, p)
                for value in PROTOCOL["clamp_protocol"]["instantaneous_steps"]:
                    obj.m = np.array([0.123])
                    obj.run(np.array([value]), SimpleNamespace(dt=dt))
                    compare(obj.P, reference.kinetics(value, name)["target"])
                    rows.append(dict(dt_s=dt, voltage_V=value, opening=float(obj.P[0])))
            write(
                output / ("native-instantaneous-" + name + ".json"),
                dict(
                    status="passed",
                    name=name,
                    rows=rows,
                    no_channel_clock=True,
                    includes_dt_zero=True,
                ),
            )
    missing_name = "Kv_ML2"
    try:
        getattr(SimpleNamespace(**namespace), missing_name)
    except AttributeError as exc:
        write(
            output / "missing-comment-class.json",
            dict(
                status="captured-source-lookup-failure",
                name="Kv_ML2",
                exception=dict(type=type(exc).__name__, message=str(exc)),
                scope="Stale configuration comment, not one of thirteen selected classes",
            ),
        )
    else:
        raise AssertionError("Unexpected source alias Kv_ML2")
    manifest.update(
        status="passed",
        version=version,
        ordinary_cases=13,
        target_cases=39,
        kinetic_clamp_cases=5,
        instantaneous_step_groups=8,
        source_class_failures=0,
        missing_comment_alias_failures=1,
        active_factory_call_sites=True,
        source_state_counts={name: int(name in reference.KINETIC) for name in reference.CLASSES},
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
