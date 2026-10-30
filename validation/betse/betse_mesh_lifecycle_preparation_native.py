"""Original-source post-clipping lifecycle oracle; supplied topology is not geometry admission."""

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
from validation.betse import betse_mesh_clip_preparation_native as clipping

MAP = Path(__file__).with_name("betse_mesh_lifecycle_preparation_source_map.json")
TOOLS = {"clip_counterclockwise", "orient_counterclockwise", "is_left_of_vector", "intersect_lines"}


def capture():
    base = clipping.capture()
    source_map = json.loads(MAP.read_text())
    assert source_map["native_source_sha256"] == base["source_map"]["native_source_sha256"]
    numeric_pin = source_map["numpy_pinv_default"]
    numeric_file = Path(np.__file__).parent / numeric_pin["module_relative_path"]
    assert np.__version__ == numeric_pin["numpy_version"]
    assert hashlib.sha256(numeric_file.read_bytes()).hexdigest() == numeric_pin["sha256"]
    frozen = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    file = "betse/science/math/mesh.py"
    tree = ast.parse((frozen / file).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DECMesh")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    added = []
    for name, site in source_map["methods"].items():
        if name == "after_clip_lifecycle":
            node = copy.deepcopy(methods["clip_and_refine"])
            assert [ast.unparse(n) for n in node.body[:2]] == source_map["lifecycle_suffix"][
                "omitted_prefix"
            ]
            node.name = name
            node.args.args = [node.args.args[0]] + node.args.args[2:]
            node.body = node.body[2:]
        else:
            node = copy.deepcopy(methods[name])
        assert (
            hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
            == site["ast_sha256"]
        )
        added.append(node)
    base["cls"].body.extend(added)
    base["lifecycle_map"] = source_map
    base["lifecycle_methods"] = tuple(source_map["methods"])
    return base


def _locals(frame):
    return {
        k: v
        for k, v in frame.items()
        if k not in ("self", "imagemask", "nparray") and not k.startswith("_cells_")
    }


def evaluate(
    kwargs,
    point_ids,
    before,
    mask_values,
    *,
    controls=None,
    origin="owned_make_voronoi_lifecycle",
    helper=None,
):
    captured = capture()
    if helper is None and (kwargs.get("image_mask") is not None or kwargs["seed_points"] is None):
        raise ValueError("Require the original unmasked multi-cell constructor")
    if helper is None and (not 1 <= len(point_ids) <= 132 or len(set(point_ids)) != len(point_ids)):
        raise ValueError("Require bounded distinct source occurrences")
    if helper is not None and helper[0] not in {
        "create_core_operators",
        "create_aux_operators",
        "laplacian_smoothing",
        "mesh_quality_calc",
        "refine_mesh",
    }:
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
        lifecycle_active=False,
        pending_move=None,
        first_failure=None,
        rebuild_count=0,
        rebuild_epochs={},
        iterations_started=0,
        iterations_completed=0,
        converged=False,
        iteration_active=False,
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

    def lifecycle_locals(frame):
        result = _locals(frame)
        for key in ("tedge_tree", "vedge_tree"):
            if key in result:
                result[key] = dict(kind="native_kd_tree_input_token", data=result[key].data)
        return result

    def lifecycle_snapshot(kind, frame):
        add(kind, dict(locals=lifecycle_locals(frame), cache=public(), point_ids=state["ids"]))

    def move_before(site):
        indices = mesh.inner_tvert_i if site["policy"] == "inner" else None
        state["pending_move"] = dict(policy=site["policy"], axis=site["axis"], indices=indices)
        add(
            "coordinate_update_before",
            dict(
                **state["pending_move"],
                points=mesh.tri_verts,
                vor_cents=mesh.vor_cents if hasattr(mesh, "vor_cents") else None,
                point_ids=state["ids"],
            ),
        )

    def move_after():
        if state["pending_move"] is not None:
            add(
                "coordinate_update_after",
                dict(
                    **state["pending_move"],
                    points=mesh.tri_verts,
                    point_ids=state["ids"],
                    point_count_preserved=len(mesh.tri_verts) == len(state["ids"]),
                ),
            )
            state["pending_move"] = None

    def iteration_start(frame):
        state["iterations_started"] += 1
        state["iteration_active"] = True
        lifecycle_snapshot("refinement_iteration_start", frame)

    def iteration_end(frame, termination):
        state["iterations_completed"] += 1
        state["iteration_active"] = False
        state["converged"] = termination == "converged"
        add(
            "refinement_iteration_end",
            dict(
                termination=termination,
                locals=lifecycle_locals(frame),
                cache=public(),
                point_ids=state["ids"],
            ),
        )

    class Linalg:
        def __getattr__(self, name):
            return getattr(np.linalg, name)

        def pinv(self, matrix, *args, **kw):
            if not state["lifecycle_active"]:
                return np.linalg.pinv(matrix, *args, **kw)
            label = captured["lifecycle_map"]["pinv_call_labels"][str(sys._getframe(1).f_lineno)]
            add("pinv_input", dict(label=label, matrix=matrix, args=args, kwargs=kw))
            try:
                result = np.linalg.pinv(matrix, *args, **kw)
            except Exception as error:
                state["first_failure"] = state["first_failure"] or "pinv:" + label
                add(
                    "pinv_failure",
                    dict(label=label, failure_type=type(error).__name__, reason=str(error)),
                )
                raise
            add("pinv_output", dict(label=label, matrix=matrix, result=result))
            return result

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
        linalg = Linalg()

        def dot(self, left, right, *args, **kw):
            if not state["lifecycle_active"]:
                return np.dot(left, right, *args, **kw)
            label = captured["lifecycle_map"]["dot_call_labels"][str(sys._getframe(1).f_lineno)]
            add("dot_input", dict(label=label, left=left, right=right, args=args, kwargs=kw))
            try:
                result = np.dot(left, right, *args, **kw)
            except Exception as error:
                state["first_failure"] = state["first_failure"] or "dot:" + label
                add(
                    "dot_failure",
                    dict(label=label, failure_type=type(error).__name__, reason=str(error)),
                )
                raise
            add("dot_output", dict(label=label, left=left, right=right, result=result))
            return result

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
        for name in (
            *captured["initial_sites"],
            "clip_to_curve",
            "search_point_cloud",
            *captured["lifecycle_methods"],
        )
    }
    codes.update({functions[name].__code__: name for name in TOOLS})
    callables = {
        **{
            name: getattr(cls, name)
            for name in (
                *captured["initial_sites"],
                "clip_to_curve",
                "search_point_cloud",
                *captured["lifecycle_methods"],
            )
        },
        **{name: functions[name] for name in TOOLS},
    }
    simple = prior.PRIMITIVES | TOOLS | {"clip_to_curve", "search_point_cloud"}
    failed_frames = set()

    def trace(frame, event, arg):
        if frame.f_code not in codes:
            return None
        name = codes[frame.f_code]
        lifecycle = name in captured["lifecycle_methods"]
        if event == "call":
            if name == "pre_mesh" and state["lifecycle_active"]:
                move_after()
                state["rebuild_count"] += 1
                epoch = state["rebuild_count"]
                state["rebuild_epochs"][id(frame)] = epoch
                add(
                    "lifecycle_rebuild_enter",
                    dict(epoch=epoch, cache=public(), point_ids=state["ids"]),
                )
            state["stack"].append(name)
            params = {
                k: frame.f_locals[k]
                for k in inspect.signature(callables[name]).parameters
                if k != "self"
            }
            add(
                "method_enter",
                dict(call_parameters=params)
                if name in simple
                else dict(call_parameters=params, cache=public(), point_ids=state["ids"])
                if lifecycle
                else dict(cache=public(), point_ids=state["ids"], call_parameters=params),
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
            elif lifecycle:
                mapping = captured["lifecycle_map"]
                if name == "refine_mesh":
                    if frame.f_lineno == mapping["refine_loop_line"] and state["iteration_active"]:
                        iteration_end(frame.f_locals, "step_completed")
                    elif frame.f_lineno == mapping["refine_iteration_first_line"]:
                        iteration_start(frame.f_locals)
                    elif frame.f_lineno == mapping["refine_break_line"]:
                        iteration_end(frame.f_locals, "converged")
                for site in mapping["coordinate_update_sites"]:
                    if site["method"] == name and site["line"] == frame.f_lineno:
                        move_after()
                        move_before(site)
        elif event == "exception":
            failed_frames.add(id(frame))
            if lifecycle:
                lifecycle_snapshot("lifecycle_partial_locals", frame.f_locals)
                state["first_failure"] = state["first_failure"] or name
            elif name in ("clip_to_curve", "clip_counterclockwise", "search_point_cloud"):
                add("clip_partial_locals", dict(locals=_locals(frame.f_locals)))
            payload = dict(failure_type=type(arg[1]).__name__, reason=str(arg[1]))
            if name in TOOLS | {"clip_to_curve", "search_point_cloud"}:
                payload["call_parameters"] = {
                    k: frame.f_locals[k]
                    for k in inspect.signature(callables[name]).parameters
                    if k != "self"
                }
            else:
                payload.update(cache=public(), point_ids=state["ids"])
            add("method_failure", payload)
        elif event == "return":
            failed = id(frame) in failed_frames
            if failed:
                failed_frames.remove(id(frame))
            else:
                if lifecycle:
                    move_after()
                    lifecycle_snapshot("lifecycle_return_locals", frame.f_locals)
                elif name in (
                    "clip_counterclockwise",
                    "orient_counterclockwise",
                    "intersect_lines",
                    "search_point_cloud",
                ):
                    add("geometry_return_locals", dict(locals=_locals(frame.f_locals)))
                add(
                    "method_return",
                    dict(result=arg, cache=public(), point_ids=state["ids"])
                    if lifecycle
                    else dict(result=arg)
                    if name in simple
                    else dict(cache=public(), point_ids=state["ids"]),
                )
            assert state["stack"].pop() == name
            if name == "pre_mesh" and state["lifecycle_active"]:
                epoch = state["rebuild_epochs"].pop(id(frame))
                if failed:
                    state["first_failure"] = state["first_failure"] or "pre_mesh"
                    add(
                        "lifecycle_rebuild_failure",
                        dict(
                            epoch=epoch,
                            cache=public(),
                            point_ids=state["ids"],
                            failure_type=state["pending_pre_mesh_failure"][0],
                            reason=state["pending_pre_mesh_failure"][1],
                        ),
                    )
                else:
                    add(
                        "lifecycle_rebuild_return",
                        dict(epoch=epoch, cache=public(), point_ids=state["ids"]),
                    )
        if event == "exception" and name == "pre_mesh" and state["lifecycle_active"]:
            state["pending_pre_mesh_failure"] = (type(arg[1]).__name__, str(arg[1]))
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
    before_lifecycle = wire.capture({})
    ids_before_lifecycle = ()
    global_before, previous = prior._state(np.random), sys.gettrace()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sys.settrace(trace)
            if helper is not None:
                name, prototype, params = helper
                for key, value in prototype.items():
                    setattr(
                        mesh,
                        key,
                        np.array(value, copy=True, order="K")
                        if isinstance(value, np.ndarray)
                        else value,
                    )
                state["lifecycle_active"] = True
                state["stage"] = "manufactured_helper:" + name
                before_lifecycle = wire.capture(public())
                ids_before_lifecycle = state["ids"]
                helper_result = wire.capture(getattr(mesh, name)(**params))
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
                before_lifecycle = wire.capture(public())
                ids_before_lifecycle = state["ids"]
                state["lifecycle_active"] = True
                state["stage"] = "after_clip_lifecycle"
                add(
                    "lifecycle_continuation_start",
                    dict(
                        cache=public(), point_ids=state["ids"], parameters=controls, origin=origin
                    ),
                )
                mesh.after_clip_lifecycle(**controls)
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
        before_lifecycle_cache=before_lifecycle,
        point_ids_before_lifecycle=ids_before_lifecycle,
        point_ids_after_lifecycle=state["ids"],
        failure_origin=state["first_failure"],
        lifecycle_termination=dict(
            iterations_started=state["iterations_started"],
            iterations_completed=state["iterations_completed"],
            source_converged=state["converged"],
            rebuilds=state["rebuild_count"],
            mesh_qual_present=hasattr(mesh, "mesh_qual"),
        ),
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
        operator_fields_present=[key for key in vars(mesh) if key.startswith("delta_")],
        refinement_executed=any(
            e["kind"] == "method_enter" and e["method"] == "refine_mesh" for e in state["events"]
        ),
        smoothing_executed=any(
            e["kind"] == "method_enter" and e["method"] == "laplacian_smoothing"
            for e in state["events"]
        ),
        upstream_initial_qualification="19/22 accuracy qualification open",
    )
