"""Authenticated native control compilation, target writes and channel dispatch.

Prescribed core P and zero-current transport hooks isolate modulation call order;
neither channel kinetics nor physical transport/tissue parity is claimed.
"""

import argparse
import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.regulation.betse_network_modulation_fixtures import cases, limitations
from validation.regulation.betse_network_modulation_reference import evaluate

PROTOCOL = Path(__file__).with_name("betse_network_modulation_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def write(path, data):
    path.write_text(json.dumps(serial(data), indent=2, allow_nan=False) + "\n")


def executable(node):
    result = copy.deepcopy(node)
    if isinstance(result, ast.FunctionDef):
        result.decorator_list, result.returns = [], None
        for arg in (*result.args.posonlyargs, *result.args.args, *result.args.kwonlyargs):
            arg.annotation = None
    return result


def captured_class(original, name, methods):
    selected = [n for n in original.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    assert {n.name for n in selected} == set(methods)
    return ast.ClassDef(
        name=name, bases=[], keywords=[], body=[executable(n) for n in selected], decorator_list=[]
    ), selected


class PhaseKind(Enum):
    INIT = 1
    SIM = 2


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(PROTOCOL.read_text())
    source = protocol["native_source"]
    checkout, installed = Path(source["checkout"]), Path(source["installed_package"]).parent
    manifest = dict(
        status="capturing",
        files={},
        executed_methods={},
        hooks=source["hooks"],
        full_simulator=False,
    )
    write(output / "source-manifest.json", manifest)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest["revision"] = revision
    for relative, expected in source["source_sha256"].items():
        content = (installed / relative).read_bytes()
        dest = output / "upstream" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, dest)
        manifest["files"][relative] = dict(
            sha256=hashlib.sha256(content).hexdigest(),
            checkout_match=content == (checkout / relative).read_bytes(),
        )
        write(output / "source-manifest.json", manifest)
        assert (
            manifest["files"][relative]["sha256"] == expected
            and manifest["files"][relative]["checkout_match"]
        )
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    manifest["version"] = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert manifest["version"] == source["version"]
    tree = ast.parse((installed / "betse/science/chemistry/networks.py").read_text())
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    body, all_methods = [], []
    for original, name, methods in (
        ("MasterOfNetworks", "CapturedNetwork", source["executed_methods"]),
        ("Modulator", "Modulator", ("__init__", "init_modulator")),
        ("Channel", "Channel", ("__init__", "init_channel")),
    ):
        cls, selected = captured_class(classes[original], name, methods)
        body.append(cls)
        for method in selected:
            manifest["executed_methods"][original + "." + method.name] = dict(
                first_line=method.lineno, last_line=method.end_lineno
            )
        all_methods.extend(selected)
    assert not any(
        method.name == "write_modulators"
        for method in classes["MasterOfNetworks"].body
        if isinstance(method, ast.FunctionDef)
    )
    sim_tree = ast.parse((installed / "betse/science/sim.py").read_text())
    dispatch = {}
    for fast in (False, True):
        channel_call = "run_fast_loop_channels" if fast else "run_loop_channels"
        nodes = [
            n
            for n in ast.walk(sim_tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) in ("p.molecules_enabled", "p.grn_enabled")
            and channel_call + "(" in ast.unparse(n)
            and "run_loop_modulators(" in ast.unparse(n)
        ]
        assert len(nodes) == 2
        nodes.sort(key=lambda n: n.lineno)
        function = ast.parse("def dispatch(self, phase, cells, p, t):\n    pass\n").body[0]
        function.name = "dispatch_fast" if fast else "dispatch_normal"
        function.body = copy.deepcopy(nodes)
        body.append(function)
        dispatch[function.name] = [dict(first_line=n.lineno, last_line=n.end_lineno) for n in nodes]
    manifest["simulator_dispatch_fragments"] = dispatch
    namespace = dict(
        np=np,
        OrderedDict=OrderedDict,
        logs=SimpleNamespace(log_info=lambda *_: None),
        BetseSimConfException=ValueError,
        tex_val=str,
        SimPhaseKind=PhaseKind,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
            str(installed / "betse/science/chemistry/networks.py"),
            "exec",
        ),
        namespace,
    )
    # Execute exact simulator network-dispatch blocks with recording handlers.
    dispatch_records = {}
    for label in ("normal", "fast"):
        calls = []

        def handler(group, calls=calls):
            def record(name):
                def call(*_args, **_kwargs):
                    calls.append(group + "." + name)

                return call

            core = SimpleNamespace(
                **{
                    name: record(name)
                    for name in (
                        "clear_run_loop",
                        "run_loop_transporters",
                        "run_loop_channels",
                        "run_fast_loop_channels",
                        "run_loop_modulators",
                        "run_loop",
                    )
                }
            )
            return SimpleNamespace(core=core, transporters=True, channels=True, modulators=True)

        sim = SimpleNamespace(molecules=handler("molecules"), grn=handler("grn"))
        namespace["dispatch_" + label](
            sim,
            SimpleNamespace(),
            SimpleNamespace(),
            SimpleNamespace(molecules_enabled=True, grn_enabled=True),
            0.0,
        )
        dispatch_records[label] = calls
    write(output / "dispatch-order.json", dispatch_records)
    records = []
    for raw, limitation in [(r, False) for r in cases()] + [(r, True) for r in limitations()]:
        path = output / (raw["name"] + ".json")
        record = dict(
            status="prepared",
            input=raw,
            limitation=limitation,
            stage="prepare",
            hooks=source["hooks"],
        )
        write(path, record)
        trace, core_instances = [], []
        m, e, ions = len(raw["membrane_to_environment"]), raw["environment_count"], raw["ion_ids"]

        class Core:
            def __init__(self, raw=raw, core_instances=core_instances, ions=ions):
                self.index = len(core_instances)
                self.modulator = np.asarray(raw["initial_channel_modulator"], float)
                self.ions, self.rel_perm = ions, raw["relative_permeability"]
                core_instances.append(self)

            def init(self, vm, cells, p, targets, raw=raw, m=m, trace=trace):
                self.targets = targets
                self.P = np.zeros(m)
                self.P[targets] = np.asarray(raw["core_P"])[targets]
                trace.append(dict(event="core.init", index=self.index, targets=targets))

            def run(self, vm, p, trace=trace):
                trace.append(
                    dict(
                        event="core.run",
                        index=self.index,
                        modulator=self.modulator.copy(),
                        P=self.P.copy(),
                    )
                )

        catalog_names = ("vgna", "vgk", "vgcl", "vgca", "vgfun", "vgcat", "vgml")
        for catalog in catalog_names:
            namespace[catalog] = SimpleNamespace(Probe=Core)

        def electroflux(cenv, cmem, D, thickness, z, voltage, temperature, p, rho, trace=trace):
            trace.append(dict(event="electroflux", diffusivity_m2_s=np.asarray(D).copy(), charge=z))
            return np.zeros_like(D)

        def update_co(sim, ccell, cmem, cenv, flux, cells, p, ignoreECM):
            return ccell, cmem, cenv

        def conductivity(D, z, cbar, thickness, p, trace=trace):
            trace.append(
                dict(event="conductivity", diffusivity_m2_s=np.asarray(D).copy(), charge=z)
            )
            return np.zeros_like(D)

        namespace["stb"] = SimpleNamespace(
            electroflux=electroflux, update_Co=update_co, get_conductivity=conductivity
        )
        native = namespace["CapturedNetwork"]()
        native.zmol = dict(zip(raw["species_ids"], raw["species_valence"], strict=True))
        for label, indices in (
            ("mem", list(range(m))),
            ("cell", list(range(m))),
            ("env", list(range(m, m + e))),
        ):
            setattr(
                native,
                label + "_concs",
                {
                    s: np.asarray(raw["sample_mM"][i], float)[indices]
                    for i, s in enumerate(raw["species_ids"])
                },
            )
        dyna = SimpleNamespace(tissue_target_inds={})
        for row in raw["channels"]:
            profile = row["apply to"]
            if isinstance(profile, list):
                for target in profile:
                    dyna.tissue_target_inds[target] = np.flatnonzero(
                        raw["channel_targets"].get(row["name"], [True] * m)
                    )
            if profile == "express":
                dyna.tissue_target_inds["left"] = np.array([0])
        sim = SimpleNamespace(
            mdl=m,
            cdl=m,
            edl=e,
            get_ion=ions.index,
            vm=np.asarray(raw["voltage_V"], float),
            T=raw["sim_temperature_K"],
            gj_block=np.asarray(raw["initial_gj"], float),
            NaKATP_block=np.asarray(raw["initial_nak"], float),
            TJ_modulator=None
            if raw.get("uninitialized_TJ")
            else np.asarray(raw["initial_tj"], float),
            TJ_targets=np.flatnonzero(raw["tj_targets"]),
            dyna=dyna,
            rho_channel=1.0,
            geo_conv=1.0,
            cbar_dic=dict.fromkeys(ions, 1.0),
            rev_E_dic=dict.fromkeys(ions, 0.0),
        )
        if raw.get("missing_sim_dyna"):
            del sim.dyna
        p = SimpleNamespace(
            F=raw["faraday_C_mol"],
            R=raw["gas_constant_J_mol_K"],
            T=raw["temperature_K"],
            is_ecm=True,
            tm=7.5e-9,
            expression_data={row["name"]: {"left": 0.2} for row in raw["channels"]},
        )
        cells = SimpleNamespace(
            mem_i=np.arange(m),
            mem_to_cells=np.arange(m),
            map_mem2ecm=np.asarray(raw["membrane_to_environment"]),
        )
        phase = SimpleNamespace(
            sim=sim,
            cells=cells,
            p=p,
            dyna=dyna,
            kind=PhaseKind.INIT if raw["initialization"] else PhaseKind.SIM,
        )
        native.extra_J_mem = np.zeros(m)
        try:
            record["stage"] = "read_modulators"
            native.read_modulators(raw["modulators"], sim, cells, p)
            record["live_after_modulator_init"] = dict(
                gj=sim.gj_block.copy(),
                nak=sim.NaKATP_block.copy(),
                tj=copy.deepcopy(sim.TJ_modulator),
            )
            record["initialized_original_arrays"] = {
                name: getattr(sim, name)
                for name in ("gj_block_o", "NaKATP_block_o")
                if hasattr(sim, name)
            }
            record["stage"] = "read_channels"
            native.read_channels(raw["channels"], phase)
            record["expressions"] = dict(
                modulators={name: obj.alpha_eval_string for name, obj in native.modulators.items()},
                channels={name: obj.alpha_eval_string for name, obj in native.channels.items()},
            )
            record["channel_init"] = {
                name: dict(
                    maxDm=obj.maxDm,
                    channelMax=obj.channelMax,
                    targets=obj.channel_core.targets,
                    class_name=obj.channel_class,
                    type_name=obj.channel_type,
                )
                for name, obj in native.channels.items()
            }
            write(path, record)
            factor_rows = []
            context = dict(self=native, sim=sim, cells=cells, p=p)
            record["stage"] = "evaluate"
            for channel, objects in ((False, native.modulators), (True, native.channels)):
                for name, obj in objects.items():
                    with np.errstate(all="ignore"):
                        alpha = np.asarray(eval(obj.alpha_eval_string, {"np": np}, context), float)
                    factor_rows.append(
                        dict(
                            name=name,
                            channel=channel,
                            alpha=alpha,
                            factor=alpha if channel else alpha * obj.max_val,
                        )
                    )
            record["factors"] = factor_rows
            write(path, record)
            record["variants"] = {}
            for variant in ("normal", "fast"):
                trace.clear()
                sim.gj_block = np.asarray(raw["initial_gj"], float)
                sim.NaKATP_block = np.asarray(raw["initial_nak"], float)
                sim.TJ_modulator = (
                    None if raw.get("uninitialized_TJ") else np.asarray(raw["initial_tj"], float)
                )
                for obj in native.channels.values():
                    obj.channel_core.modulator = np.asarray(raw["initial_channel_modulator"], float)
                record["stage"] = variant + "_channel_dispatch"
                (native.run_fast_loop_channels if variant == "fast" else native.run_loop_channels)(
                    phase
                )
                record["stage"] = variant + "_target_application"
                native.run_loop_modulators(sim, cells, p)
                channel_values = [[0.0] * m for _ in native.modulators]
                channel_values.extend(
                    obj.channel_core.modulator.copy() for obj in native.channels.values()
                )
                record["variants"][variant] = dict(
                    controls=dict(
                        gj=sim.gj_block.copy(),
                        nak=sim.NaKATP_block.copy(),
                        tj=copy.deepcopy(sim.TJ_modulator),
                        channel_modulator=channel_values,
                    ),
                    trace=copy.deepcopy(trace),
                )
            record["status"] = "captured_limitation" if limitation else "passed"
            if limitation:
                assert not raw["expected_failure"]
            else:
                expected = evaluate(raw)
                record["independent_reference"] = expected
                for i, row in enumerate(factor_rows):
                    count = len(row["factor"])
                    np.testing.assert_allclose(
                        row["factor"], expected["factors"][i][:count], rtol=5e-12, atol=3e-14
                    )
                    np.testing.assert_allclose(
                        row["alpha"], expected["regulation"][i][:count], rtol=5e-12, atol=3e-14
                    )
                for variant in record["variants"].values():
                    for field, actual in variant["controls"].items():
                        np.testing.assert_allclose(
                            actual, expected["controls"][field], rtol=5e-12, atol=3e-14
                        )
                    values = [
                        event["diffusivity_m2_s"]
                        for event in variant["trace"]
                        if event["event"] in ("electroflux", "conductivity")
                    ]
                    exp_values = [
                        expected["diffusivity_m2_s"][ion][rule]
                        for rule in range(len(raw["modulators"]), len(factor_rows))
                        if expected["channel_run"][rule]
                        for ion in range(len(ions))
                    ]
                    np.testing.assert_allclose(values, exp_values, rtol=5e-12, atol=1e-30)
        except (
            TypeError,
            ValueError,
            SyntaxError,
            KeyError,
            IndexError,
            AttributeError,
            UnboundLocalError,
        ) as error:
            record.update(
                status="captured_failure",
                failure_type=type(error).__name__,
                message=str(error),
                partial_controls=dict(gj=sim.gj_block, nak=sim.NaKATP_block, tj=sim.TJ_modulator),
                partial_trace=trace,
            )
            write(path, record)
            assert limitation and raw["expected_failure"], record
        write(path, record)
        records.append(dict(name=raw["name"], status=record["status"], path=str(path)))
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
    manifest.update(
        status="passed",
        records=records,
        component_cases=len(cases()),
        limitations=len(limitations()),
        production_cells_imported=False,
        jax_imported=False,
    )
    write(output / "source-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture(args.output)
    print(json.dumps({key: result[key] for key in ("status", "component_cases", "limitations")}))
