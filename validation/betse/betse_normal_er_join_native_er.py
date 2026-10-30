"""Authenticated original EndoRetic methods with observational hooks only."""

import ast
import copy
import hashlib
import json
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

PROTOCOL = Path(__file__).with_name("betse_normal_er_join_protocol.json")
FIELDS = (
    "cc_er",
    "er_vol",
    "er_sa",
    "Ver",
    "Q",
    "cm_er",
    "Dm_er",
    "Dm_er_base",
    "Dm_channels",
    "zer",
)


def call(expression):
    return ast.parse(expression).body[0]


def literal_nodes(original):
    toolbox = ast.parse((original / "sim_toolbox.py").read_text())
    pump = copy.deepcopy(
        next((n for n in toolbox.body if isinstance(n, ast.FunctionDef) and n.name == "pumpCaER"))
    )
    pump.name = "_pumpCaER"
    labels = {
        "Qnumo": "quotient_numerator",
        "Qdenomo": "quotient_denominator_raw",
        "Q": "quotient",
        "Keq": "equilibrium",
        "frwd": "forward",
        "bkwrd": "backward_unused",
        "f_Ca": "serca_flux_mol_m2_s",
    }
    body = []
    for node in pump.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        body.append(node)
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and (node.targets[0].id in labels)
        ):
            name = node.targets[0].id
            body.append(call("p._observe(" + repr(labels[name]) + "," + name + ")"))
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript):
            body.append(call("p._observe('quotient_denominator_used',Qdenomo)"))
    pump.body = body
    flux = copy.deepcopy(
        next(
            (n for n in toolbox.body if isinstance(n, ast.FunctionDef) and n.name == "electroflux")
        )
    )
    flux.name = "_electroflux"
    flux.body = [
        n
        for n in flux.body
        if not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        )
    ]
    original = ast.parse((original / "organelles/endo_retic.py").read_text())
    er = copy.deepcopy(
        next((n for n in original.body if isinstance(n, ast.ClassDef) and n.name == "EndoRetic"))
    )
    er.name = "_LiteralEndoRetic"
    er.body = [
        n
        for n in er.body
        if isinstance(n, ast.FunctionDef) and n.name in ("__init__", "get_v", "channels", "update")
    ]
    for method in er.body:
        method.body = [
            n
            for n in method.body
            if not (
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str)
            )
        ]
        if method.name == "update":
            body = []
            for node in method.body:
                body.append(node)
                if (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Call)
                    and (ast.unparse(node.value.func) == "self.channels")
                ):
                    body.append(call("self._observe('channels',sim,None,None)"))
                if (
                    isinstance(node, ast.Assign)
                    and ast.unparse(node.targets[0]) == "sim.cc_er[sim.iCa]"
                ):
                    body.append(call("self._observe('serca_commit',sim,sim.iCa,f_CaATP)"))
                if isinstance(node, ast.For):
                    node.body.append(call("self._observe('er_electroflux_commit',sim,i,f_ED)"))
                if (
                    isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Call)
                    and (ast.unparse(node.value.func) == "self.get_v")
                ):
                    body.append(call("self._observe('charge_voltage',sim,None,None)"))
            method.body = body
    return [pump, flux, er]


def authenticated():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    for name in ("betse/science/organelles/endo_retic.py", "betse/science/sim_toolbox.py"):
        data = (Path(pins["checkout"]) / name).read_bytes()
        if (
            hashlib.sha256(data).hexdigest() != pins["source_sha256"][name]
            or data != (Path(pins["installed_package"]).parent / name).read_bytes()
        ):
            raise ValueError("Original ER source changed: " + name)
    nodes = literal_nodes(Path(pins["checkout"]) / "betse/science")
    ns = dict(np=np, copy=copy, SimpleNamespace=SimpleNamespace)
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            "<authenticated original ER>",
            "exec",
        ),
        ns,
    )
    ns["stb"] = SimpleNamespace(pumpCaER=ns["_pumpCaER"], electroflux=ns["_electroflux"])
    return ns


def setup(sim, cells, p, policy, owner_context, incoming_state):
    ns = authenticated()
    for name, value in policy["endoretic"].items():
        setattr(p, name, value)
    for name, row in owner_context.items():
        concentrations = (
            {"IP3": np.asarray(row["IP3_mM"], np.float64).copy()} if row["contains_IP3"] else {}
        )
        owner = (
            None
            if not row["present"]
            else SimpleNamespace(
                molecules={"IP3": True} if row["contains_IP3"] else {}, cell_concs=concentrations
            )
            if name == "molecules"
            else SimpleNamespace(core=SimpleNamespace(cell_concs=concentrations))
        )
        setattr(sim, name, owner)
    cls = ns["_LiteralEndoRetic"]
    if incoming_state is None:
        er = cls(sim, cells, p)
    else:
        er = object.__new__(cls)
        for name in FIELDS:
            if name == "cc_er":
                sim.cc_er = np.array(incoming_state[name], copy=True)
            else:
                setattr(er, name, copy.deepcopy(incoming_state[name]))

    def fields():
        return {
            name: copy.deepcopy(sim.cc_er if name == "cc_er" else getattr(er, name))
            for name in FIELDS
        }

    trace = dict(
        initial_state=fields(),
        frames=[],
        arithmetic={},
        owner_context=copy.deepcopy(owner_context),
        after=None,
    )

    def observe(stage, actual, index, flux):
        trace["frames"].append(
            dict(
                stage=stage,
                ion_id=None
                if index is None
                else next(name for name in p.ions_dict if sim.get_ion(name) == index),
                cytosol_mM=actual.cc_cells.copy(),
                fields=fields(),
                flux_mol_m2_s=None if flux is None else flux.copy(),
            )
        )

    er._observe = observe
    original_update = cls.update

    def update(actual, live_sim, geometry, params):
        trace["frames"].clear()
        trace["arithmetic"].clear()
        observe("initial", live_sim, None, None)
        params._observe = lambda name, value: trace["arithmetic"].__setitem__(
            name, np.array(value, copy=True)
        )
        try:
            return original_update(actual, live_sim, geometry, params)
        finally:
            trace["after"] = fields()
            del params._observe

    er.update = MethodType(update, er)
    sim.endo_retic = er
    return trace


def raw_probe(inputs):
    ns = authenticated()
    arithmetic = {}
    parameters = SimpleNamespace(
        **inputs["parameters"],
        _observe=lambda name, value: arithmetic.__setitem__(name, np.array(value, copy=True)),
    )
    cc_er = np.array(inputs["cER_mM"], np.float64)
    cytosol = np.array(inputs["cytosol_mM"], np.float64)
    voltage = np.array(inputs["voltage_V"], np.float64)
    failure = flux = None
    with np.errstate(all="ignore"):
        try:
            flux = ns["_pumpCaER"](
                cc_er, cytosol, voltage, inputs["runtime_temperature_K"], parameters
            )
        except Exception as error:
            import traceback

            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
    return dict(
        inputs=inputs,
        arithmetic=arithmetic,
        flux_mol_m2_s=flux,
        cER_after_mM=cc_er,
        cytosol_after_mM=cytosol,
        voltage_after_V=voltage,
        source_completed=failure is None,
        failure=failure,
        finite=failure is None
        and np.isfinite(flux).all()
        and all(np.isfinite(value).all() for value in arithmetic.values()),
    )


def main():
    import argparse
    import builtins
    import sys

    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_voltage_native import write_archive

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] == "cells":
            raise ImportError("Native ER capture forbids production import")
        return original(name, *rest, **kwargs)

    builtins.__import__ = guarded
    before = copy.deepcopy(np.random.get_state())
    result = raw_probe(json.loads(args.inputs.read_text()))
    after = np.random.get_state()
    loaded = [name for name in sys.modules if name == "cells" or name.startswith("cells.")]
    assert not loaded
    result.update(
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=inventory(),
        RNG_unchanged=before[0] == after[0]
        and np.array_equal(before[1], after[1])
        and before[2:] == after[2:],
    )
    write_archive(args.output, result)


if __name__ == "__main__":
    main()
