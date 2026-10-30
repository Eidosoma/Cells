"""Pinned native picker and global-GJ sites with private, fully saved RNGs.

Execute actual ALL/PERCENT/INDICES picker bodies and the global-finalizer body.
Geometry construction, membrane expansion and the full solver are not run.
The namespace gives those bodies private NumPy/Python RNG instances, preserving
their actual shuffle implementations without touching process-global states.
"""

import ast
import copy
import hashlib
import os
import platform
import random
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PINNED = {
    "betse/science/tissue/picker/tispickcls.py": (
        "c1c592ddc600479806da73c37ade7aecf19df0f49cd46706a74ad6bb9f1bc773"
    ),
    "betse/science/tissue/tishandler.py": (
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54"
    ),
}


@lru_cache(maxsize=1)
def capture():
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    functions, sites = [], {}
    for relative, names in (
        (
            "betse/science/tissue/picker/tispickcls.py",
            {
                "TissuePickerAll": ("pick_cells", "all"),
                "TissuePickerPercent": ("pick_cells", "percent"),
                "TissuePickerIndices": ("pick_cells", "indices"),
            },
        ),
        (
            "betse/science/tissue/tishandler.py",
            {
                "TissueHandler": ("_finalize_events_global", "global_gj"),
            },
        ),
    ):
        data = (root / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != PINNED[relative]:
            raise ValueError("Pinned target-selection source changed: " + relative)
        tree = ast.parse(data)
        for cls in (
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in names
        ):
            method, name = names[cls.name]
            body = next(
                node
                for node in cls.body
                if isinstance(node, ast.FunctionDef) and node.name == method
            )
            node = copy.deepcopy(body)
            node.name, node.decorator_list, node.returns = name, [], None
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                argument.annotation = None
            functions.append(node)
            sites[name] = dict(source=relative, first_line=body.lineno, last_line=body.end_lineno)
    assert set(sites) == {"all", "percent", "indices", "global_gj"}
    code = compile(
        ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
        "<pinned target selection>",
        "exec",
    )
    return code, sites


def numpy_state(rng):
    state = rng.get_state()
    return [state[0], state[1].tolist(), int(state[2]), int(state[3]), float(state[4])]


def python_state(rng):
    state = rng.getstate()
    return [state[0], list(state[1]), state[2]]


def evaluate(raw, stream):
    if stream["numpy"]["numpy_version"] != np.__version__ or (
        stream["python"]["python_version"] != platform.python_version()
        or stream["python"]["implementation"] != platform.python_implementation()
    ):
        raise ValueError("Native target replay requires the original RNG runtimes")
    a, b = stream["numpy"]["state"], stream["python"]["state"]
    nrng, prng = np.random.RandomState(0), random.Random(0)
    nrng.set_state((a[0], np.asarray(a[1], dtype=np.uint32), a[2], a[3], a[4]))
    prng.setstate((b[0], tuple(b[1]), b[2]))
    ignored_orders = []

    def py_shuffle(values):
        prng.shuffle(values)
        ignored_orders.append(values.tolist())

    code, sites = capture()
    namespace = dict(
        np=SimpleNamespace(random=SimpleNamespace(shuffle=nrng.shuffle), copy=np.copy),
        shuffle=py_shuffle,
    )
    exec(code, namespace)
    ids, membrane_ids = raw["layout"]["cell_ids"], raw["layout"]["membrane_ids"]
    positions = {name: i for i, name in enumerate(ids)}
    cells = SimpleNamespace(
        cell_i=np.asarray([positions[name] for name in stream["cell_order"]], dtype=np.int64),
        mem_i=np.arange(len(membrane_ids), dtype=np.int64),
    )
    selected, picked, operations = {}, {}, []
    for index, row in enumerate([raw["default"], *raw["profiles"]] if raw["enabled"] else []):
        kind = "all" if index == 0 else row["picker"]
        if kind not in ("all", "percent", "indices"):
            raise ValueError("This native capture covers ALL/PERCENT/INDICES only")
        picker = SimpleNamespace(cells_percent=row["percent"], cells_index=row["indices"])
        values = namespace[kind](picker, cells, None)
        selected[row["name"]] = values
        picked[row["name"]] = [ids[int(i)] for i in values]
        if kind == "percent":
            operations.append(
                dict(
                    kind="percent",
                    name=row["name"],
                    permutation=[ids[int(i)] for i in cells.cell_i],
                    selected=picked[row["name"]],
                    numpy_state=numpy_state(nrng),
                    python_state=python_state(prng),
                    shuffled_copy_ignored=False,
                )
            )
    options = {
        name: 0 for name in ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block")
    }
    percent = raw.get("global_gj_percent")
    if percent is not None:
        options["gj_block"] = [0.0, 1.0, 0.1, percent]
    handler = SimpleNamespace()
    namespace["global_gj"](
        handler, SimpleNamespace(cells=cells, p=SimpleNamespace(global_options=options))
    )
    global_ids = None
    if percent is not None:
        assert len(ignored_orders) == 1
        global_ids = [membrane_ids[int(i)] for i in handler.targets_gj_block]
        operations.append(
            dict(
                kind="global_gj",
                name="global_gj",
                permutation=[membrane_ids[int(i)] for i in ignored_orders[0]],
                selected=global_ids,
                numpy_state=numpy_state(nrng),
                python_state=python_state(prng),
                shuffled_copy_ignored=True,
            )
        )
    result = dict(
        selected_cells={name: [ids[int(i)] for i in values] for name, values in selected.items()},
        picked_cells=picked,
        final_cell_order=[ids[int(i)] for i in cells.cell_i],
        global_gj_targets=global_ids,
        operations=operations,
        numpy_state=numpy_state(nrng),
        python_state=python_state(prng),
        next_call=stream["next_call"] + len(operations),
        native_source_sha256=PINNED,
        source_sites=sites,
        scope="Native picker/finalizer sites; no full solver or geometry calls",
    )
    result["future_probe"] = dict(
        numpy_normals=nrng.normal(size=3).tolist(),
        python_gaussians=[prng.gauss(0, 1) for _ in range(3)],
        numpy_state=numpy_state(nrng),
        python_state=python_state(prng),
    )
    return result
