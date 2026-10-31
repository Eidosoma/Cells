"""Fresh original native cut/contact source worker; no production kernel import."""

import ast
import copy
import hashlib
import json
import math
import os
import sys
import traceback
import warnings
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
from numpy import array
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from cells.processes import betse_post_cut_mesh_contact_records as wire  # noqa: E402

PROTOCOL = Path(__file__).with_name("betse_native_cut_lifecycle_protocol.json")
LAW_ID = "betse_post_cut_DEC_and_contact_source_boundary@1"
MAX_CELLS, MAX_MEMBRANES, MAX_EDGES, MAX_FACES = 16, 96, 128, 64
MAX_EVENTS = 256
MAX_EVIDENCE_BYTES = 128 * 2**20


def source_texts(paths):
    """Read the pinned originals without running native source or a simulation."""
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    native = Path(os.environ.get("CELLS_BETSE_SOURCE", pins["checkout"]))
    texts = {}
    for key, relative in paths.items():
        payload = (native / relative).read_bytes()
        if hashlib.sha256(payload).hexdigest() != pins["source_sha256"][relative]:
            raise ValueError("Native post-cut source pin changed: " + relative)
        texts[key] = payload.decode("utf-8")
    return native, texts


def original_module():
    paths = {
        "mesh": "betse/science/math/mesh.py",
        "cells": "betse/science/cells.py",
        "handler": "betse/science/tissue/tishandler.py",
        "toolbox": "betse/science/math/toolbox.py",
    }
    native, texts = source_texts(paths)
    trees = {key: ast.parse(text) for key, text in texts.items()}
    wanted = {
        "mesh": (
            "DECMesh",
            ["cut_mesh", "create_tri_map", "create_mappings", "create_core_operators"],
        ),
        "cells": (
            "Cells",
            [
                "cellVerts",
                "cellMatrices",
                "intra_updater",
                "cell_vols",
                "mem_processing",
                "near_neigh",
                "calc_gj_vects",
            ],
        ),
    }
    classes = []
    for key, (name, methods) in wanted.items():
        cls = next(
            node for node in trees[key].body if isinstance(node, ast.ClassDef) and node.name == name
        )
        selected = [
            copy.deepcopy(node)
            for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name in methods
        ]
        assert len(selected) == len(methods)
        for node in selected:
            node.decorator_list = []
        classes.append(
            ast.ClassDef(
                name="MeshKernel" if key == "mesh" else "CellKernel",
                bases=[],
                keywords=[],
                body=selected,
                decorator_list=[],
                type_params=[],
            )
        )
    handler = next(
        node
        for node in trees["handler"].body
        if isinstance(node, ast.ClassDef) and node.name == "TissueHandler"
    )
    cut = copy.deepcopy(
        next(
            node
            for node in handler.body
            if isinstance(node, ast.FunctionDef) and node.name == "_cut_cells"
        )
    )
    stop = next(
        index
        for index, node in enumerate(cut.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "cells.environment"
    )
    assert stop == 41
    cut.name = "cut_through_contacts"
    cut.decorator_list = []
    cut.body = cut.body[:stop]
    cut.body.append(
        ast.Return(value=ast.Call(func=ast.Name(id="locals", ctx=ast.Load()), args=[], keywords=[]))
    )
    flatten = copy.deepcopy(
        next(
            node
            for node in trees["toolbox"].body
            if isinstance(node, ast.FunctionDef) and node.name == "flatten"
        )
    )
    flatten.decorator_list = []
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module_ast = ast.fix_missing_locations(
        ast.Module(body=[future, flatten, *classes, cut], type_ignores=[])
    )
    module = ModuleType("independent_original_post_cut_source")
    module.__file__ = str(native / paths["mesh"])
    module.__dict__.update(
        np=np,
        array=array,
        math=math,
        copy=copy,
        cKDTree=cKDTree,
        logs=SimpleNamespace(log_info=lambda *_: None),
    )
    exec(compile(module_ast, str(native / paths["mesh"]), "exec"), module.__dict__)
    module.tb = SimpleNamespace(flatten=module.flatten)
    return module


def modules():
    return np, cKDTree, wire, original_module()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Trial:
    law_id: str
    mode: str
    before_json: str
    after_json: str
    events_json: str
    failure_json: object
    source_completed: bool
    first_failure_stage: object
    source_pin: str
    identity: str


class BoundaryRejected(RuntimeError):
    def __init__(self, reason, *, trial=None, partial=None):
        super().__init__(reason)
        self.trial, self.partial = (trial, partial)


def trial_record(value):
    return {
        key: getattr(value, key)
        for key in (
            "law_id",
            "mode",
            "before_json",
            "after_json",
            "events_json",
            "failure_json",
            "source_completed",
            "first_failure_stage",
            "source_pin",
        )
    }


def _validate_request(raw, np):
    expected = {
        "kind",
        "mode",
        "classification",
        "provenance",
        "sim",
        "cells",
        "mesh",
        "selection",
        "parameters",
        "handler",
        "owners",
    }
    if (
        type(raw) is not dict
        or set(raw) != expected
        or raw["kind"] != "cells.supplied_post_cut_source_request@1"
    ):
        raise ValueError("Complete explicit supplied native state required")
    if raw["mode"] not in ("cut_through_contacts", "mesh_only", "contact_only"):
        raise ValueError("Unknown separately named source component boundary")
    if (
        raw["classification"] != "manufactured_supplied_source_state"
        or type(raw["provenance"]) is not str
        or (not raw["provenance"])
    ):
        raise ValueError("Caller-supplied state is not cold native geometry provenance")
    if not all(
        (
            type(raw[key]) is dict
            for key in ("sim", "cells", "mesh", "selection", "parameters", "handler", "owners")
        )
    ):
        raise ValueError("Explicit source owner dictionaries required")
    p = raw["parameters"]
    if p.get("is_ecm") is not True or p.get("Ca_dyn") is not False:
        raise ValueError("Actual ordinary ECM/Ca_dynFalse source conditions required")
    owners = raw["owners"]
    if set(owners) != {
        "cell_ids",
        "membrane_ids",
        "mesh_edge_ids",
        "mesh_face_ids",
        "cell_membrane_ids",
    }:
        raise ValueError("Original named owner axes required")
    for key in ("cell_ids", "membrane_ids", "mesh_edge_ids", "mesh_face_ids"):
        values = owners[key]
        if (
            type(values) is not list
            or any((type(value) is not str or not 0 < len(value) <= 96 for value in values))
            or len(set(values)) != len(values)
        ):
            raise ValueError("Unique ordered stable names required: " + key)
    n = len(owners["cell_ids"])
    m = len(owners["membrane_ids"])
    if (
        not 1 <= n <= MAX_CELLS
        or not 1 <= m <= MAX_MEMBRANES
        or len(owners["mesh_edge_ids"]) > MAX_EDGES
        or (len(owners["mesh_face_ids"]) > MAX_FACES)
    ):
        raise ValueError("Source state exceeds the bounded owner/working-array panel")
    groups = owners["cell_membrane_ids"]
    if len(groups) != n or [value for row in groups for value in row] != owners["membrane_ids"]:
        raise ValueError("Cell membrane occurrences must partition the original ordered axis")
    selected = raw["selection"]
    if set(selected) != {"cells", "membranes", "provenance"} or not selected["provenance"]:
        raise ValueError("Actual supplied picker result includes both typed occurrence axes")
    for key, limit in (("cells", n), ("membranes", m)):
        values = np.asarray(selected[key])
        if (
            values.ndim != 1
            or values.dtype.kind not in "iu"
            or np.any(values < 0)
            or np.any(values >= limit)
        ):
            raise ValueError("Explicit in-range integer picker occurrence array required")
    expected_membranes = [
        owners["membrane_ids"].index(value)
        for index in selected["cells"]
        for value in groups[int(index)]
    ]
    if np.asarray(selected["membranes"]).tolist() != expected_membranes:
        raise ValueError("Picker membrane occurrences differ from selected original owners")
    if raw["mode"] != "contact_only":
        mesh = raw["mesh"]
        if np.shape(mesh.get("tri_verts")) != (n, 2) or np.shape(mesh.get("tri_edges")) != (
            len(owners["mesh_edge_ids"]),
            2,
        ):
            raise ValueError("Supplied DEC vertex/edge axes differ from original cell owners")
        if len(mesh.get("tri_cells", ())) != len(owners["mesh_face_ids"]):
            raise ValueError("Supplied DEC face owner axis differs")
    return raw


def _available(value, np, tree_type, seen=None):
    if isinstance(value, tree_type):
        return dict(kind="native_KDTree_input_token", data=np.asarray(value.data))
    if isinstance(value, (np.ndarray, np.generic, str, bool, int, float, type(None))):
        return value
    if isinstance(value, (list, tuple, set, dict, SimpleNamespace)):
        return value
    return dict(
        kind="unserializable_source_local_token",
        python_type=type(value).__module__ + "." + type(value).__qualname__,
    )


def _execute(raw, *, native=None, observer=None):
    np, tree_type, wire, default_source = modules()
    source = default_source if native is None else native
    before = wire.snapshot(raw)
    _validate_request(raw, np)
    work = copy.deepcopy(raw)

    class Mesh(source.MeshKernel, SimpleNamespace):
        pass

    class Cells(source.CellKernel, SimpleNamespace):
        pass

    mesh = Mesh()
    mesh.__dict__ = work["mesh"]
    cells = Cells()
    cells.__dict__ = work["cells"]
    cells.mesh = mesh
    p = SimpleNamespace()
    p.__dict__ = work["parameters"]
    sim = SimpleNamespace()
    sim.__dict__ = work["sim"]
    handler = SimpleNamespace()
    handler.__dict__ = work["handler"]
    phase = SimpleNamespace(cells=cells, p=p, sim=sim)

    class Picker:
        def pick_cells_and_mems(self, *, cells, p):
            return (work["selection"]["cells"], work["selection"]["membranes"])

    picker = Picker()
    events = []
    event_bytes = 0
    stack = []
    first_failure = None

    def world():
        return dict(
            sim=sim,
            cells=cells,
            parameters=p,
            handler=handler,
            selection=work["selection"],
            owners=work["owners"],
        )

    codes = {
        source.cut_through_contacts.__code__: "cut_through_contacts",
        source.flatten.__code__: "flatten",
    }
    for cls in (source.MeshKernel, source.CellKernel):
        for name, value in vars(cls).items():
            if callable(value) and hasattr(value, "__code__"):
                codes[value.__code__] = name

    def add(kind, name, payload):
        nonlocal event_bytes
        encoded = wire.snapshot(payload)
        row = dict(sequence=len(events), kind=kind, method=name, depth=len(stack), payload=encoded)
        if observer is not None:
            observer(row)
        event_bytes += len(encoded.encode())
        events.append(row)
        if len(events) > MAX_EVENTS or event_bytes > MAX_EVIDENCE_BYTES:
            raise BoundaryRejected(
                "Declared complete source evidence budget exhausted", partial=dict(last_event=row)
            )

    excluded = {"self", "phase", "cells", "p", "sim", "tissue_picker"}

    def trace(frame, event, arg):
        nonlocal first_failure
        name = codes.get(frame.f_code)
        if name is None:
            return trace
        if event == "call":
            stack.append(name)
            add(
                "enter",
                name,
                dict(
                    world=world(),
                    arguments={
                        key: _available(value, np, tree_type)
                        for key, value in frame.f_locals.items()
                        if key not in excluded
                    },
                ),
            )
        elif event in ("return", "exception"):
            available = {
                key: _available(value, np, tree_type)
                for key, value in frame.f_locals.items()
                if key not in excluded
            }
            payload = dict(world=world(), available_source_locals=available)
            if event == "exception":
                first_failure = first_failure or name
                payload["exception"] = dict(type=arg[0].__name__, message=str(arg[1]))
            add(event, name, payload)
            if event == "return" and stack:
                stack.pop()
        return trace

    failure = None
    returned = None
    previous = sys.gettrace()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            sys.settrace(trace)
            try:
                if raw["mode"] == "cut_through_contacts":
                    returned = source.cut_through_contacts(handler, phase, picker)
                elif raw["mode"] == "mesh_only":
                    returned = mesh.cut_mesh(work["selection"]["cells"])
                else:
                    cells.mem_processing(p)
                    cells.near_neigh(p)
                    cells.calc_gj_vects(p)
            finally:
                sys.settrace(previous)
        warning_records = [
            dict(
                type=type(item.message).__name__,
                message=str(item.message),
                filename=item.filename,
                lineno=item.lineno,
            )
            for item in caught
        ]
    except Exception as error:
        sys.settrace(previous)
        failure = dict(
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
            available_partial=getattr(error, "partial", None),
        )
        warning_records = (
            [
                dict(
                    type=type(item.message).__name__,
                    message=str(item.message),
                    filename=item.filename,
                    lineno=item.lineno,
                )
                for item in caught
            ]
            if "caught" in locals()
            else []
        )
    returned_locals = None
    if isinstance(returned, dict):
        returned_locals = {
            key: _available(value, np, tree_type)
            for key, value in returned.items()
            if key not in excluded
        }
    else:
        returned_locals = returned
    after = wire.snapshot(
        dict(world=world(), return_value=returned_locals, warnings=warning_records)
    )
    if wire.snapshot(raw) != before:
        raise BoundaryRejected(
            "Source capture mutated its actual supplied parent",
            partial=dict(before=before, after=after, events=events),
        )
    from pathlib import Path

    source_path = Path(default_source.__file__)
    pin = hashlib.sha256(source_path.read_bytes()).hexdigest()
    record = dict(
        law_id=LAW_ID,
        mode=raw["mode"],
        before_json=before,
        after_json=after,
        events_json=json.dumps(events, sort_keys=True, separators=(",", ":")),
        failure_json=None if failure is None else json.dumps(failure, sort_keys=True),
        source_completed=failure is None,
        first_failure_stage=first_failure,
        source_pin=pin,
    )
    return Trial(**record, identity=digest(record))


def main():
    text = sys.stdin.read(16 * 2**20 + 1)
    if len(text.encode()) > 16 * 2**20:
        raise ValueError("Bounded source input exceeded")
    request = json.loads(text)
    raw = wire.restore(request["input_graph"])
    trial = _execute(raw)
    response = trial_record(trial)
    response["runtime"] = dict(
        pid=os.getpid(),
        ppid=os.getppid(),
        executable=sys.executable,
        source_compiled_from="original native AST",
        production_kernel_imported=any(
            name.endswith("betse_post_cut_mesh_contact_source") for name in sys.modules
        ),
    )
    json.dump(response, sys.stdout, sort_keys=True, allow_nan=False)


if __name__ == "__main__":
    main()
