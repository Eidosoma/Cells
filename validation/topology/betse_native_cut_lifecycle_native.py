"""Independent original pre-mesh cut fragment; no production imports or geometry calls."""

import argparse
import ast
import copy
import hashlib
import json
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.topology import betse_native_cut_lifecycle_records as records

PROTOCOL = Path(__file__).with_name("betse_native_cut_lifecycle_protocol.json")


def literal_nodes(root):
    tree = ast.parse((root / "betse/science/tissue/tishandler.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler")
    fn = copy.deepcopy(
        next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_cut_cells")
    )
    stop = next(
        i
        for i, n in enumerate(fn.body)
        if isinstance(n, ast.Assign) and "cells.mesh.cut_mesh" in ast.unparse(n)
    )
    fn.body = fn.body[:stop] + ast.parse("return locals()").body
    fn.name = "deletion_prefix"
    tb = ast.parse((root / "betse/science/math/toolbox.py").read_text())
    flat = copy.deepcopy(
        next(n for n in tb.body if isinstance(n, ast.FunctionDef) and n.name == "flatten")
    )

    class Clean(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return None
            return self.generic_visit(node)

        def visit_FunctionDef(self, node):
            node.decorator_list = []
            node.returns = None
            for arg in node.args.args + node.args.kwonlyargs:
                arg.annotation = None
            return self.generic_visit(node)

    return [Clean().visit(flat), Clean().visit(fn)]


def evaluate(inputs):
    protocol = json.loads(PROTOCOL.read_text())
    native = protocol["native_source"]
    for relative, expected in native["source_sha256"].items():
        a = (Path(native["checkout"]) / relative).read_bytes()
        b = (Path(native["installed_package"]).parent / relative).read_bytes()
        if a != b or hashlib.sha256(a).hexdigest() != expected:
            raise ValueError("Native cut source pin changed: " + relative)
    api = dict(np=np, copy=copy, logs=SimpleNamespace(log_info=lambda *_: None))
    nodes = literal_nodes(Path(native["checkout"]))
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            "<original native pre-mesh cut prefix>",
            "exec",
        ),
        api,
    )
    api["tb"] = SimpleNamespace(flatten=api["flatten"])
    supplied = dict(
        sim=inputs["simulator_fields"],
        cells=inputs["cell_fields"],
        selection=inputs["selection"],
        p=inputs["parameters"],
        handler=inputs["handler_fields"],
    )
    before = records.snapshot(supplied)
    work = copy.deepcopy(supplied)

    def owner(value):
        result = records._DataOwner()
        result.__dict__ = value
        return result

    phase = SimpleNamespace(sim=owner(work["sim"]), cells=owner(work["cells"]), p=owner(work["p"]))
    handler = owner(work["handler"])
    targets = work["selection"]
    picker = SimpleNamespace(
        pick_cells_and_mems=lambda cells, p: (targets["cells"], targets["membranes"])
    )
    local_values = {}
    source_frames = []
    excluded = {"self", "phase", "cells", "p", "sim", "tissue_picker"}
    failure = None
    try:
        local_values = api["deletion_prefix"](handler, phase, picker)
    except Exception as error:
        frame = error.__traceback__
        while frame is not None:
            name = frame.tb_frame.f_code.co_name
            if name in ("deletion_prefix", "flatten"):
                available = {
                    key: value
                    for key, value in frame.tb_frame.f_locals.items()
                    if key not in excluded
                }
                source_frames.append(dict(function=name, available=available))
                if name == "deletion_prefix":
                    local_values = dict(frame.tb_frame.f_locals)
            frame = frame.tb_next
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
    after = records.snapshot(
        dict(
            sim=vars(phase.sim),
            cells=vars(phase.cells),
            selection=targets,
            p=vars(phase.p),
            handler=vars(handler),
            available_source_locals={k: v for k, v in local_values.items() if k not in excluded},
            available_source_frames=source_frames,
        )
    )
    assert records.snapshot(supplied) == before
    return dict(
        before_json=before,
        after_json=after,
        source_prefix_completed=failure is None,
        failure=failure,
        complete_native_cut=False,
        geometry_calls_executed=0,
        native_source_sha256=native["source_sha256"],
        physical_mesh_qualified=False,
    )


def main():
    import builtins
    import importlib.abc
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    denied = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in denied:
            raise ImportError("Native source import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in denied:
                raise ImportError("Native source import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(records.restore(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in denied]
    assert not loaded
    result.update(production_imports_denied=True, loaded_production_modules=loaded)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
