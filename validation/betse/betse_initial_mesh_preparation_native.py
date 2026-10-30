"""Prepared original constructor/pre_mesh oracle, with native bodies unchanged."""

import __future__

import ast
import builtins
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import traceback
import warnings
from collections.abc import Sequence
from numbers import Number
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial import Delaunay, cKDTree

from validation.betse import betse_initial_mesh_preparation_wire as wire

PROTOCOL = Path(__file__).with_name("betse_initial_mesh_preparation_protocol.json")
PRIMITIVES = {"area", "poly_centroid", "circumc", "quad_circumc", "cc_sort_inds"}
HELPERS = {
    "betse/util/type/types.py": ("type_check",),
    "betse/util/math/geometry/polygon/geopoly.py": (
        "die_unless_polygon",
        "is_polygon",
        "is_convex",
        "is_cyclic_quad",
    ),
    "betse/util/math/mathoper.py": ("det1d",),
    "betse/util/math/geometry/geopoint.py": ("is_point",),
    "betse/util/type/iterable/sequences.py": ("is_sequence",),
    "betse/lib/numpy/nparray.py": ("from_iterable",),
    "betse/lib/numpy/npscalar.py": ("to_python",),
}


def _site(file, node):
    return dict(
        source=file,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def capture():
    protocol = json.loads(PROTOCOL.read_text())
    pins = protocol["native_source"]
    root = Path(pins["checkout"])
    installed = Path(pins["installed_package"]).parent
    frozen = Path(os.environ.get("CELLS_BETSE_SOURCE", str(root)))
    trees = {}
    for file, expected in pins["source_sha256"].items():
        for base in (root, installed, frozen):
            assert hashlib.sha256((base / file).read_bytes()).hexdigest() == expected, str(
                base / file
            )
        trees[file] = ast.parse((frozen / file).read_text())
    assert (
        subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        == pins["revision"]
    )
    nodes, helpers = [], {}
    for file, names in HELPERS.items():
        for name in names:
            node = next(
                n for n in trees[file].body if isinstance(n, ast.FunctionDef) and n.name == name
            )
            nodes.append(copy.deepcopy(node))
            helpers[name] = _site(file, node)
    file = "betse/science/math/mesh.py"
    cls = next(n for n in trees[file].body if isinstance(n, ast.ClassDef) and n.name == "DECMesh")
    source_map = json.loads(
        PROTOCOL.with_name("betse_initial_mesh_preparation_source_map.json").read_text()
    )
    methods = [
        n
        for n in cls.body
        if isinstance(n, ast.FunctionDef) and n.name in source_map["closure_methods"]
    ]
    sites = {n.name: _site(file, n) for n in methods}
    assert sites == source_map["methods"]
    assert helpers == source_map["native_helper_sites"]
    class_node = ast.ClassDef(
        name="NativeMesh",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=copy.deepcopy(methods),
        decorator_list=[],
    )
    nodes.append(class_node)
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    return module, sites, helpers, pins


def _state(rng):
    value = rng.get_state()
    return [value[0], value[1].tolist(), int(value[2]), int(value[3]), float(value[4])]


def caller_kwargs(seed_recipe, before, controls):
    """Evaluate pinned caller keyword expressions using literal native seeds.

    The owned image prelude is an upstream admission requirement. This helper
    does not repeat image decoding or claim image/lattice generation coverage.
    """
    from validation.betse import betse_lattice_seed_generation_native as seed_native

    proof = seed_native.evaluate(seed_recipe, before)
    assert proof["status"] == "source_completed" and proof["failure"] is None
    _, sites, _, pins = capture()
    root = Path(pins["checkout"])
    tree = ast.parse((root / "betse/science/cells.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Cells")
    method = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "make_voronoi"
    )
    calls = sorted(
        (
            n
            for n in ast.walk(method)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "DECMesh"
        ),
        key=lambda n: n.lineno,
    )
    call = calls[0] if controls["single_cell"] else calls[2]
    enums = SimpleNamespace(HEX=object(), SQUARE=object())
    p = SimpleNamespace(
        cell_radius=seed_recipe["cell_radius_m"],
        cell_lattice_type=getattr(enums, seed_recipe["lattice_type"]),
        alpha_shape=controls["alpha_shape"],
        use_centroids=controls["use_centroids"],
    )
    context = dict(
        phase=SimpleNamespace(p=p),
        self=SimpleNamespace(
            clust_xy=proof["values"]["all_seed_points_m"], centre=proof["values"]["centre_m"]
        ),
        lattice_to_mesh_type={enums.HEX: "tri", enums.SQUARE: "rect"},
    )
    kwargs = {
        k.arg: eval(
            compile(
                ast.Expression(body=copy.deepcopy(k.value)), "<pinned make_voronoi keyword>", "eval"
            ),
            context,
        )
        for k in call.keywords
    }
    return dict(
        kwargs=kwargs,
        rng_before_constructor=proof["rng_after"],
        source_call=_site("betse/science/cells.py", call),
        reused_lattice_source_sites=proof["source_sites"],
        constructor_sites=sites,
        source_lattice_layouts=proof["source_layouts"],
    )


def evaluate(kwargs, point_ids, before):
    module, sites, helpers, pins = capture()
    if (
        kwargs.get("image_mask") is not None
        or not 1 <= len(point_ids) <= 132
        or len(set(point_ids)) != len(point_ids)
    ):
        raise ValueError("Require the initial unmasked constructor and distinct source occurrences")
    rng = np.random.RandomState(0)
    rng.set_state(
        (before[0], np.asarray(before[1], dtype=np.uint32), before[2], before[3], before[4])
    )
    state = dict(stack=[], events=[], ids=tuple(point_ids), mesh=None)

    def add(kind, payload):
        state["events"].append(
            dict(
                sequence=len(state["events"]),
                kind=kind,
                method=state["stack"][-1] if state["stack"] else "driver",
                depth=len(state["stack"]),
                payload=wire.capture(payload),
            )
        )

    def public():
        return dict(vars(state["mesh"]))

    class Random:
        def random(self, size):
            original = _state(rng)
            value = rng.random(size)
            add(
                "uniform_draw",
                dict(size=size, values=value, rng_before=original, rng_after=_state(rng)),
            )
            return value

    class Numpy:
        random = Random()

        def __getattr__(self, name):
            return getattr(np, name)

        def delete(self, array, indices, axis=None):
            value = np.delete(array, indices, axis=axis)
            if array is getattr(state["mesh"], "tri_verts", None) and axis == 0:
                old = state["ids"]
                retained = np.delete(np.arange(len(old)), indices, axis=0)
                new = tuple(old[int(i)] for i in retained)
                add(
                    "source_row_deletion",
                    dict(
                        cause=state["stack"][-1],
                        indices=indices,
                        input_points=array,
                        output_points=value,
                        point_ids_before=old,
                        point_ids_after=new,
                        removed_ids=tuple(name for i, name in enumerate(old) if i not in retained),
                    ),
                )
                state["ids"] = new
            return value

    class Tree:
        def __init__(self, data):
            self.data = data
            add("tree_input", dict(data=data))
            try:
                self.tree = cKDTree(data)
            except Exception as error:
                add("tree_failure", dict(failure_type=type(error).__name__, reason=str(error)))
                raise
            add("tree_created", dict(native_tree_data=self.tree.data))

        def query(self, points, *args, **kw):
            try:
                value = self.tree.query(points, *args, **kw)
            except Exception as error:
                add(
                    "nearest_failure",
                    dict(
                        data=self.data,
                        points=points,
                        args=args,
                        kwargs=kw,
                        failure_type=type(error).__name__,
                        reason=str(error),
                    ),
                )
                raise
            add(
                "nearest_query",
                dict(
                    data=self.data,
                    native_tree_data=self.tree.data,
                    points=points,
                    args=args,
                    kwargs=kw,
                    result=value,
                ),
            )
            return value

    def triangulate(points):
        add("delaunay_input", dict(points=points, point_ids=state["ids"]))
        try:
            result = Delaunay(points)
        except Exception as error:
            add("delaunay_failure", dict(failure_type=type(error).__name__, reason=str(error)))
            raise
        add(
            "delaunay_output",
            dict(
                points=result.points,
                simplices=result.simplices,
                neighbors=result.neighbors,
                coplanar=result.coplanar,
                convex_hull=result.convex_hull,
                point_ids=state["ids"],
            ),
        )
        return result

    namespace = {}

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "betse.util.type.numeric.floats":
            return SimpleNamespace(PI=math.pi, TWO_PI=2 * math.pi)
        if name == "betse.lib.numpy":
            return SimpleNamespace(
                nparray=SimpleNamespace(from_iterable=namespace["from_iterable"]),
                npscalar=SimpleNamespace(to_python=namespace["to_python"]),
            )
        if name == "betse.util.math.geometry":
            return SimpleNamespace(geopoint=SimpleNamespace(is_point=namespace["is_point"]))
        if name.split(".")[0] in {"cells", "betse", "jax", "jaxlib"}:
            raise ImportError("Package denied by initial-mesh native boundary: " + name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    namespace.update(
        __name__="cells_initial_native_capture",
        __builtins__=dict(vars(builtins), __import__=imports),
        np=Numpy(),
        array=np.array,
        cKDTree=Tree,
        Delaunay=triangulate,
        math=math,
        NumpyArrayType=np.ndarray,
        NumericTypes=(Number,),
        SequenceTypes=(Sequence, np.ndarray),
        BetseMathPolygonException=ValueError,
        logs=SimpleNamespace(
            log_info=lambda *args: add("native_log", dict(level="log_info", args=args)),
            log_warning=lambda *args: add("native_log", dict(level="log_warning", args=args)),
        ),
    )
    exec(
        compile(
            module,
            "<pinned native initial mesh>",
            "exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        ),
        namespace,
    )
    namespace["sequences"] = SimpleNamespace(is_sequence=namespace["is_sequence"])
    cls = namespace["NativeMesh"]
    mesh = object.__new__(cls)
    state["mesh"] = mesh
    codes = {getattr(cls, name).__code__: name for name in sites}
    failed_frames = set()

    def trace(frame, event, arg):
        if frame.f_code not in codes:
            return None
        name = codes[frame.f_code]
        primitive = name in PRIMITIVES
        if event == "call":
            state["stack"].append(name)
            parameters = {
                key: frame.f_locals[key]
                for key in frame.f_code.co_varnames[: frame.f_code.co_argcount]
                if key != "self"
            }
            add(
                "method_enter",
                dict(call_parameters=parameters)
                if primitive
                else dict(cache=public(), point_ids=state["ids"], call_parameters=parameters),
            )
        elif event == "exception":
            failed_frames.add(id(frame))
            add(
                "method_failure",
                dict(
                    failure_type=type(arg[1]).__name__,
                    reason=str(arg[1]),
                    cache=public(),
                    point_ids=state["ids"],
                ),
            )
        elif event == "return":
            if id(frame) in failed_frames:
                failed_frames.remove(id(frame))
            else:
                add(
                    "method_return",
                    dict(result=arg) if primitive else dict(cache=public(), point_ids=state["ids"]),
                )
            assert state["stack"].pop() == name
        return trace

    failure = None
    stage = "constructor"
    constructed = wire.capture({})
    after_constructor = before
    constructor_completed = pre_mesh_completed = False
    global_before = _state(np.random)
    previous = sys.gettrace()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sys.settrace(trace)
            cls.__init__(
                mesh,
                **{
                    key: np.array(v, copy=True, order="K") if isinstance(v, np.ndarray) else v
                    for key, v in kwargs.items()
                },
            )
            constructor_completed = True
            constructed = wire.capture(public())
            after_constructor = _state(rng)
            stage = "pre_mesh"
            mesh.pre_mesh()
            pre_mesh_completed = True
        except Exception as error:
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
            if not constructor_completed:
                constructed = wire.capture(public())
                after_constructor = _state(rng)
        finally:
            sys.settrace(previous)
    assert not state["stack"]
    global_after = _state(np.random)
    return dict(
        status="source_completed" if failure is None else "source_failed",
        stage=stage,
        failure=failure,
        constructed_cache=constructed,
        cache=wire.capture(public()),
        events=state["events"],
        retained_point_ids=state["ids"],
        rng_before=before,
        rng_after_constructor=after_constructor,
        rng_after=_state(rng),
        constructor_completed=constructor_completed,
        pre_mesh_completed=pre_mesh_completed,
        warnings=[str(w.message) for w in caught],
        original_global_rng_unchanged=global_before == global_after,
        native_source_sha256=pins["source_sha256"],
        source_sites=sites,
        helper_sites=helpers,
        operators_created=False,
        image_clip_executed=False,
        topology_qualified=False,
    )
