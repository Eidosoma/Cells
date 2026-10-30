"""Create a separate supplied-state capture; no scientific imports or execution."""

# ruff: noqa: E501 -- captured generator text is formatted in its output file.

import ast
from pathlib import Path

original = Path("validation/betse/betse_normal_er_join_native.py")
source = original.read_text()
tree = ast.parse(source)
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate")
body = ast.get_source_segment(source, function)
assert body.count("er_state_cache = None") == 1
body = body.replace("def evaluate(inputs):", "def _whole_join(inputs):", 1)
body = body.replace(
    "er_state_cache = None",
    'er_state_cache = restore_supplied_fields(inputs["prepared_er_input"]["fields"])',
    1,
)
body = body.replace(
    'kind="cells.native_normal_er_join_capture@1"',
    'kind="cells.native_prepared_er_join_capture@1"',
    1,
)
head = '''"""Original native updates consuming the same complete supplied ER packet.

No native constructor or restart equivalence follows from this capture.
"""

import argparse
import builtins
import copy
import importlib.abc
import json
import sys
import traceback
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_er_join_native_er as er_native
from validation.betse.betse_normal_er_join_native import (
    channel_helpers, gated_native, material_capture, runtime_inventory, voltage_native,
)

write_archive = voltage_native.write_archive


def restore_supplied_fields(raw):
    if set(raw) != set(er_native.FIELDS):
        raise ValueError("Require every supplied ER field")
    return {name: float(raw[name]) if name == "cm_er" else np.asarray(raw[name], dtype=np.float64).copy() for name in er_native.FIELDS}

'''
tail = """

def _er_only(inputs):
    rng_before = copy.deepcopy(np.random.get_state())
    before = inputs["pre_er"]
    names = before["er_state"]["ion_ids"]
    sim = SimpleNamespace(
        cc_cells=np.asarray(before["cytosol_mM"], np.float64).copy(),
        cdl=len(before["cell_volume_m3"]), iCa=names.index("Ca"),
        zs=np.asarray(before["valence"], np.float64).copy(),
        movingIons=list(before["moving_indices"]), T=before["runtime_temperature_K"],
        get_ion=lambda name: names.index(name),
    )
    cells = SimpleNamespace(cell_vol=np.asarray(before["cell_volume_m3"], np.float64).copy())
    parameters = SimpleNamespace(**copy.deepcopy(before["parameters"]))
    parameters.ions_dict = dict.fromkeys(names, True)
    keys = ("serca_max", "max_er", "act_Km_Ca", "act_n_Ca", "inh_Km_Ca", "inh_n_Ca", "act_Km_IP3", "act_n_IP3")
    trace = er_native.setup(sim, cells, parameters, dict(endoretic={k: before["parameters"][k] for k in keys}), before["owner_context"], restore_supplied_fields(before["er_state"]["fields"]))
    failure = None
    with np.errstate(all="ignore"):
        try:
            sim.endo_retic.update(sim, cells, parameters)
        except Exception as error:
            failure = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
    rng_after = np.random.get_state()
    finite = failure is None and np.isfinite(sim.cc_cells).all() and all(np.isfinite(value).all() for value in trace["after"].values()) and all(np.isfinite(value).all() for value in trace["arithmetic"].values())
    return dict(
        kind="cells.native_prepared_ER_only_capture@1", inputs=inputs,
        status="source_completed" if finite else "source_refused", source_completed=failure is None,
        finite=bool(finite), failure=failure, endoretic=trace, cytosol_after_mM=sim.cc_cells.copy(),
        RNG_before=rng_before, RNG_after=rng_after,
        RNG_unchanged=rng_before[0]==rng_after[0] and np.array_equal(rng_before[1],rng_after[1]) and rng_before[2:]==rng_after[2:],
        runtime=runtime_inventory() | dict(numpy=np.__version__),
    )


def evaluate(inputs):
    if inputs.get("kind") == "cells.prepared_owned_ER_only_probe@1":
        result = _er_only(inputs)
    else:
        supplied = inputs["prepared_er_input"]
        if supplied["mode"] != "prepared_owned_ER_before_outer_call_channels_primed_v1" or set(supplied["fields"]) != set(er_native.FIELDS):
            raise ValueError("Require the full explicitly supplied prepared state")
        result = _whole_join(inputs)
    result.update(supplied_prepared_state=True, native_initialization_executed=False, native_restart_parity=False)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Supplied-state native import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Supplied-state native import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Native capture loaded a production module")
    result.update(production_imports_denied=True, loaded_production_modules=loaded)
    write_archive(args.output, result)


if __name__ == "__main__":
    main()
"""
output = Path("validation/betse/betse_prepared_er_join_native.py")
with output.open("x") as stream:
    stream.write(head + body + "\n" + tail)
