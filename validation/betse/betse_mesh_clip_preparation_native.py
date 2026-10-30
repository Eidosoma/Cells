"""Original-source clipping oracle with an explicit owned-mask input boundary."""

import __future__

import ast
import builtins
import copy
import hashlib
import inspect
import json
import math
import os
import sys
import traceback
import warnings
from collections.abc import Sequence
from numbers import Number
from pathlib import Path
from types import GeneratorType, SimpleNamespace

import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.spatial import Delaunay, cKDTree

from validation.betse import betse_initial_mesh_preparation_native as prior
from validation.betse import betse_initial_mesh_preparation_wire as wire

MAP = Path(__file__).with_name("betse_mesh_clip_preparation_source_map.json")
TOOLS = {"clip_counterclockwise", "orient_counterclockwise", "is_left_of_vector", "intersect_lines"}


def capture():
    source_map = json.loads(MAP.read_text())
    root = Path("/mnt/workspaces/Cells/betse-v1.5.0")
    installed = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
    frozen = Path(os.environ.get("CELLS_BETSE_SOURCE", str(root)))
    trees = {}
    for name, expected in source_map["native_source_sha256"].items():
        for base in (root, installed, frozen):
            assert hashlib.sha256((base / name).read_bytes()).hexdigest() == expected, name
        trees[name] = ast.parse((frozen / name).read_text())
    module, initial_sites, _, _ = prior.capture()
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef))
    original = next(
        n
        for n in trees["betse/science/math/mesh.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "DECMesh"
    )
    new_methods = [
        n
        for n in original.body
        if isinstance(n, ast.FunctionDef) and n.name in source_map["methods"]
    ]
    for node in new_methods:
        expected = source_map["methods"][node.name]
        assert prior._site("betse/science/math/mesh.py", node) == {
            k: v for k, v in expected.items() if k != "source_name"
        }
    cls.body.extend(copy.deepcopy(new_methods))
    helpers = {}
    for file, names in prior.HELPERS.items():
        for name in names:
            helpers[name] = next(
                n for n in trees[file].body if isinstance(n, ast.FunctionDef) and n.name == name
            )
    for name, site in source_map["helpers"].items():
        node = next(
            n
            for n in trees[site["source"]].body
            if isinstance(n, ast.FunctionDef) and n.name == site["source_name"]
        )
        assert prior._site(site["source"], node) == {
            k: v for k, v in site.items() if k != "source_name"
        }
        helpers[name] = node
    helpers["interp2d_linear"] = next(
        n
        for n in trees["betse/util/math/mathinterp.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "interp2d_linear"
    )
    clip = next(n for n in new_methods if n.name == "clip_to_curve")
    cell_loop = next(
        n for n in ast.walk(clip) if isinstance(n, ast.For) and isinstance(n.target, ast.Tuple)
    )
    query_line = cell_loop.body[0].lineno
    image_assign = next(
        n
        for n in clip.body
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "self.image_mask" for t in n.targets)
    )
    convex = helpers["clip_counterclockwise"]
    edge_loop = next(
        n
        for n in ast.walk(convex)
        if isinstance(n, ast.For) and ast.unparse(n.target) == "clip_vert_next"
    )
    return dict(
        cls=cls,
        helpers=helpers,
        source_map=source_map,
        initial_sites=initial_sites,
        cell_loop_line=cell_loop.lineno,
        cell_query_line=query_line,
        replacement_line=image_assign.lineno,
        edge_first_line=edge_loop.body[0].lineno,
    )


def _locals(frame):
    return {
        k: v
        for k, v in frame.items()
        if k not in ("self", "imagemask", "nparray") and not k.startswith("_cells_")
    }


def evaluate(kwargs, point_ids, before, mask_values, *, helper=None):
    captured = capture()
    if helper is None and (kwargs.get("image_mask") is not None or kwargs["seed_points"] is None):
        raise ValueError("Require the original unmasked multi-cell constructor")
    if helper is None and (not 1 <= len(point_ids) <= 132 or len(set(point_ids)) != len(point_ids)):
        raise ValueError("Require bounded distinct source occurrences")
    if helper is not None and helper[0] not in TOOLS | {"search_point_cloud"}:
        raise ValueError("Unknown isolated manufactured-helper boundary")
    rng = np.random.RandomState(0)
    rng.set_state(
        (before[0], np.asarray(before[1], dtype=np.uint32), before[2], before[3], before[4])
    )
    state = dict(
        mesh=None,
        mask=None,
        stack=[],
        events=[],
        ids=tuple(point_ids),
        parent_ids=(),
        derived_ids=(),
        selected=[],
        current_cell=None,
        query_count=0,
        stage="initial_source_replay",
    )

    def normalize(value):
        if value is state["mask"] and state["mask"] is not None:
            return mask_values
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return type(value)(normalize(v) for v in value)
        return value

    def add(kind, payload):
        state["events"].append(
            dict(
                sequence=len(state["events"]),
                kind=kind,
                method=state["stack"][-1] if state["stack"] else "driver",
                depth=len(state["stack"]),
                payload=wire.capture(normalize(payload)),
            )
        )

    def public():
        return normalize(dict(vars(state["mesh"])))

    def cell_enter(frame):
        ii = int(frame["ii"])
        state["current_cell"], state["query_count"] = ii, 0
        add(
            "clip_cell_enter",
            dict(
                source_cell_index=frame["ii"],
                parent_id=state["parent_ids"][ii],
                poly_ind=frame["poly_ind"],
                cell_poly=frame["cell_poly"],
                vor_cent=frame["vor_cent"],
            ),
        )

    def cell_exit(frame):
        ii, count = int(frame["ii"]), len(frame["clip_vor_cents"])
        if count != len(state["selected"]):
            assert count == len(state["selected"]) + 1
            parent = state["parent_ids"][ii]
            point_id = parent + "/native-clip-centroid"
            branch = (
                "all_vertices_nonzero"
                if frame["point_check"].sum() == len(frame["cell_poly"])
                else "partial_with_nonzero_centre"
            )
            state["selected"].append(point_id)
            add(
                "clip_centroid_emitted",
                dict(
                    source_cell_index=ii,
                    parent_id=parent,
                    point_id=point_id,
                    branch=branch,
                    centroid=frame["clip_vor_cents"][-1],
                    polygon=frame["clip_vor_verts"][-1],
                ),
            )
        add("clip_cell_exit", dict(source_cell_index=ii, locals=_locals(frame)))
        state["current_cell"] = None

    def replacement(frame):
        state["derived_ids"] = tuple(state["selected"])
        assert len(frame["clip_vor_cents"]) == len(state["derived_ids"])
        add(
            "clip_seed_replacement",
            dict(
                parent_point_ids=state["parent_ids"],
                derived_point_ids=state["derived_ids"],
                clipped_polygons=frame["clip_vor_verts"],
                centroid_seed_points=frame["clip_vor_cents"],
                note="Polygons are source locals; the following mesh is rebuilt from centroids",
            ),
        )
        state["ids"], state["current_cell"], state["query_count"] = state["derived_ids"], None, 0
        state["stage"] = "masked_pre_mesh_rebuild"

    class Random:
        def random(self, size):
            original = prior._state(rng)
            value = rng.random(size)
            add(
                "uniform_draw",
                dict(size=size, values=value, rng_before=original, rng_after=prior._state(rng)),
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
                result = self.tree.query(points, *args, **kw)
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
                    result=result,
                ),
            )
            return result

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

    namespace, functions = {}, {}

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "betse.lib.numpy":
            return SimpleNamespace(nparray=namespace["nparray"], npscalar=namespace["npscalar"])
        if name == "betse.util.math.geometry":
            return SimpleNamespace(geopoint=namespace["geopoint"])
        if name == "betse.util.type.cls":
            return SimpleNamespace(classes=namespace["classes"])
        if name == "betse.util.type.iterable":
            return SimpleNamespace(generators=namespace["generators"])
        if name == "betse.util.type.numeric.floats":
            return SimpleNamespace(PI=math.pi, TWO_PI=2 * math.pi)
        if name.split(".")[0] in {"cells", "betse", "jax", "jaxlib"}:
            raise ImportError("Native clipping package boundary denied: " + name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    namespace.update(
        __name__="cells_clip_native_capture",
        __builtins__=dict(vars(builtins), __import__=imports),
        np=Numpy(),
        array=np.array,
        ndarray=np.ndarray,
        cKDTree=Tree,
        Delaunay=triangulate,
        math=math,
        NumpyArrayType=np.ndarray,
        NumericTypes=(Number,),
        SequenceTypes=(Sequence, np.ndarray),
        GeneratorType=GeneratorType,
        RectBivariateSpline=RectBivariateSpline,
        classes=SimpleNamespace(get_name_unqualified=lambda value: value.__name__),
        logs=SimpleNamespace(
            log_info=lambda *a: add("native_log", dict(level="log_info", args=a)),
            log_warning=lambda *a: add("native_log", dict(level="log_warning", args=a)),
        ),
    )
    for name in (
        "BetseMathLineException",
        "BetseMathPointException",
        "BetseMathPolygonException",
        "BetseIterableException",
    ):
        namespace[name] = type(name, (ValueError,), {})
    for logical, node in captured["helpers"].items():
        module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]))
        exec(
            compile(
                module,
                "<pinned native clipping helper>",
                "exec",
                flags=__future__.annotations.compiler_flag,
                dont_inherit=True,
            ),
            namespace,
        )
        functions[logical] = namespace[node.name]
    namespace.update(
        nparray=SimpleNamespace(
            from_iterable=functions["array_from_iterable"],
            to_iterable=functions["array_to_iterable"],
        ),
        npscalar=SimpleNamespace(to_python=functions["to_python"]),
        iterables=SimpleNamespace(to_iterable=functions["iterable_to_iterable"]),
        geopoly=SimpleNamespace(die_unless_polygon=functions["die_unless_polygon"]),
        geopoint=SimpleNamespace(
            is_point=functions["is_point"],
            is_left_of_vector=functions["is_left_of_vector"],
            intersect_lines=functions["intersect_lines"],
        ),
        sequences=SimpleNamespace(is_sequence=functions["is_sequence"]),
        generators=SimpleNamespace(is_generator=functions["is_generator"]),
    )
    module = ast.fix_missing_locations(ast.Module(body=[captured["cls"]], type_ignores=[]))
    exec(
        compile(
            module,
            "<pinned native clip continuation>",
            "exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        ),
        namespace,
    )
    cls = namespace["NativeMesh"]
    mesh = object.__new__(cls)
    state["mesh"] = mesh
    codes = {
        getattr(cls, name).__code__: name
        for name in (*captured["initial_sites"], "clip_to_curve", "search_point_cloud")
    }
    codes.update({functions[name].__code__: name for name in TOOLS})
    callables = {
        **{
            name: getattr(cls, name)
            for name in (*captured["initial_sites"], "clip_to_curve", "search_point_cloud")
        },
        **{name: functions[name] for name in TOOLS},
    }
    simple = prior.PRIMITIVES | TOOLS | {"clip_to_curve", "search_point_cloud"}
    failed_frames = set()

    def trace(frame, event, arg):
        if frame.f_code not in codes:
            return None
        name = codes[frame.f_code]
        if event == "call":
            state["stack"].append(name)
            parameters = {
                key: frame.f_locals[key]
                for key in inspect.signature(callables[name]).parameters
                if key != "self"
            }
            add(
                "method_enter",
                dict(call_parameters=parameters)
                if name in simple
                else dict(cache=public(), point_ids=state["ids"], call_parameters=parameters),
            )
        elif event == "line":
            if name == "clip_to_curve":
                if (
                    frame.f_lineno == captured["cell_loop_line"]
                    and state["current_cell"] is not None
                ):
                    cell_exit(frame.f_locals)
                elif frame.f_lineno == captured["cell_query_line"]:
                    cell_enter(frame.f_locals)
                elif frame.f_lineno == captured["replacement_line"]:
                    replacement(frame.f_locals)
            elif name == "clip_counterclockwise" and frame.f_lineno == captured["edge_first_line"]:
                add("clip_half_plane", dict(locals=_locals(frame.f_locals)))
        elif event == "exception":
            failed_frames.add(id(frame))
            if name in ("clip_to_curve", "clip_counterclockwise", "search_point_cloud"):
                add("clip_partial_locals", dict(locals=_locals(frame.f_locals)))
            payload = dict(failure_type=type(arg[1]).__name__, reason=str(arg[1]))
            if name in TOOLS | {"clip_to_curve", "search_point_cloud"}:
                payload["call_parameters"] = {
                    key: frame.f_locals[key]
                    for key in inspect.signature(callables[name]).parameters
                    if key != "self"
                }
            else:
                payload.update(cache=public(), point_ids=state["ids"])
            add("method_failure", payload)
        elif event == "return":
            if id(frame) in failed_frames:
                failed_frames.remove(id(frame))
            else:
                if name in (
                    "clip_counterclockwise",
                    "orient_counterclockwise",
                    "intersect_lines",
                    "search_point_cloud",
                ):
                    add("geometry_return_locals", dict(locals=_locals(frame.f_locals)))
                add(
                    "method_return",
                    dict(result=arg)
                    if name in simple
                    else dict(cache=public(), point_ids=state["ids"]),
                )
            assert state["stack"].pop() == name
        return trace

    class Mask:
        def __init__(self):
            self.clipcurve = mask_values["clipcurve_m"]
            self.function = functions["interp2d_linear"](
                mask_values["xpts_m"], mask_values["ypts_m"], mask_values["clipping_matrix"]
            )

        def clipping_function(self, x, y):
            value = self.function(x, y)
            role = (
                ("centre" if state["query_count"] == 0 else "vertex")
                if state["current_cell"] is not None
                else "rebuild_circumcentre"
            )
            add(
                "mask_query",
                dict(
                    x=x,
                    y=y,
                    result=value,
                    role=role,
                    source_cell_index=state["current_cell"],
                    cell_query_index=state["query_count"],
                    within_closed_window=bool(
                        mask_values["xpts_m"][0] <= x <= mask_values["xpts_m"][-1]
                        and mask_values["ypts_m"][0] <= y <= mask_values["ypts_m"][-1]
                    ),
                ),
            )
            state["query_count"] += 1
            return value

    failure, helper_result = None, None
    initial_cache = wire.capture({})
    after_initial = before
    global_before, previous = prior._state(np.random), sys.gettrace()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sys.settrace(trace)
            if helper is not None:
                name, parameters = helper
                state["stage"] = "manufactured_helper:" + name
                function = getattr(mesh, name) if name == "search_point_cloud" else functions[name]
                helper_result = wire.capture(function(**parameters))
            else:
                cls.__init__(
                    mesh,
                    **{
                        k: np.array(v, copy=True, order="K") if isinstance(v, np.ndarray) else v
                        for k, v in kwargs.items()
                    },
                )
                mesh.pre_mesh()
                initial_cache, after_initial = wire.capture(public()), prior._state(rng)
                state["parent_ids"] = state["ids"]
                state["stage"] = "clip_to_curve"
                add(
                    "clip_continuation_start",
                    dict(initial_cache=public(), parent_point_ids=state["parent_ids"]),
                )
                state["mask"] = Mask()
                mesh.clip_to_curve(state["mask"])
        except Exception as error:
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
        finally:
            sys.settrace(previous)
    assert not state["stack"]
    return dict(
        status="source_failed" if failure else "source_completed",
        failure=failure,
        stage=state["stage"],
        initial_cache=initial_cache,
        cache=wire.capture(public()),
        events=state["events"],
        parent_point_ids=state["parent_ids"],
        derived_point_ids_before_rebuild=state["derived_ids"],
        retained_point_ids=state["ids"],
        rng_after_initial=after_initial,
        rng_after=prior._state(rng),
        warnings=[str(w.message) for w in caught],
        original_global_rng_unchanged=global_before == prior._state(np.random),
        native_source_sha256=captured["source_map"]["native_source_sha256"],
        image_decode_coverage_reused=True,
        source_topology_is_input_for_diagnostics=True,
        manufactured_helper_only=helper is not None,
        helper_result=helper_result,
        topology_qualified=False,
        downstream_geometry_admitted=False,
        operators_created=False,
        refinement_executed=False,
    )
