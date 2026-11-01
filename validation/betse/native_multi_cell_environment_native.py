"""Independent original-BETSE multi-cell ordinary prefix through make_maskM.

AST preparation is metadata only. Actual reference execution needs the separate
review/release/resource gate. Original methods and the grid descriptor are
compiled from pinned files, never imported from Cells production. The legacy
private compiler, normalized type/phase adapters and numerical libraries are
shared machinery and give no independent physical oracle or package authority.
"""

import ast
import copy
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, SimpleNamespace

from validation.betse import native_multi_cell_caller_native as legacy
from validation.betse import native_multi_cell_caller_native_source as legacy_source
from validation.betse import native_multi_cell_caller_runtime as legacy_runtime
from validation.betse import native_single_cell_prefix_native as shared

KIND = "cells.independent_multi_cell_environment@1"
ENDPOINT = "make_maskM"
METHODS = (*shared.METHODS, "makeECM", "environment", "assign_grid_len", "make_maskM")
BODY_METHODS = tuple(name for name in METHODS if name != "assign_grid_len")
STORE_LINES = legacy_source.STORE_LINES
DESCRIPTOR = "['general options']['comp grid size']"
GRID_SIZE = 25
PLOT_GRID_SIZE = 50
TREE_FIELDS = shared.TREE_FIELDS


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(
        b, sort_keys=True, allow_nan=False
    )


def clone(function, **globals):
    value = FunctionType(
        function.__code__,
        dict(function.__globals__, **globals),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    value.__kwdefaults__ = function.__kwdefaults__
    return value


def pins_for():
    result = dict(legacy_source.pins_for())
    for name, digest in shared.pins_for(ENDPOINT).items():
        if name in result and result[name] != digest:
            raise ValueError("Conflicting original ordinary-prefix authority")
        result[name] = digest
    return result


def source_nodes(root):
    """Select original ASTs only; do not execute definitions or source work."""
    root = Path(root)
    groups, original_sites = legacy_source.source_nodes(root)
    extended, _ = shared.source_nodes(root, stop_after=ENDPOINT)
    by_file = {}
    for file, nodes in groups:
        by_file.setdefault(file, []).extend(copy.deepcopy(nodes))
    extended = {file: nodes for file, nodes in extended}
    cells = next(
        node
        for node in by_file[legacy_source.CELLS_FILE]
        if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    full_cells = next(
        node
        for node in extended[legacy_source.CELLS_FILE]
        if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    selected = {node.name: node for node in full_cells.body if isinstance(node, ast.FunctionDef)}
    # Preserve the whole original ordinary make_world ordering, including its
    # inline self-only grid_len assignment. No post-cut method sequence enters.
    cells.body = [
        copy.deepcopy(selected[node.name]) if node.name == "make_world" else node
        for node in cells.body
    ]
    cells.body.extend(copy.deepcopy(selected[name]) for name in BODY_METHODS)
    by_file["betse/science/math/finitediff.py"] = copy.deepcopy(
        extended["betse/science/math/finitediff.py"]
    )
    factory = next(
        node
        for node in extended[legacy_source.PARAMETER_FILE]
        if isinstance(node, ast.FunctionDef) and node.name == "parameter_type"
    )
    by_file[legacy_source.PARAMETER_FILE].append(copy.deepcopy(factory))
    world = next(
        node
        for node in cells.body
        if isinstance(node, ast.FunctionDef) and node.name == "make_world"
    )
    calls = [
        node.value.func.attr
        for node in world.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "self"
    ]
    if tuple(calls[-len(BODY_METHODS) :]) != BODY_METHODS or calls[-1] != ENDPOINT:
        raise ValueError("Original nine-method ordinary ordering changed")
    if any(
        isinstance(node, ast.Attribute)
        and node.attr in {"makeLaplacian", "intra_updater", "calc_gj_vects"}
        for node in ast.walk(world)
    ):
        raise ValueError("Reference widened beyond ordinary make_maskM")
    sites = dict(original_sites)
    for file, nodes in by_file.items():
        for node in nodes:
            sites[file + ":" + getattr(node, "name", "assignment_" + str(node.lineno))] = (
                legacy_source._site(node)
            )
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        sites[file + ":" + node.name + "." + method.name] = legacy_source._site(
                            method
                        )
    assignment = next(
        node
        for node in world.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute) and target.attr == "grid_len"
            for target in node.targets
        )
    )
    sites[legacy_source.CELLS_FILE + ":make_world.grid_len"] = legacy_source._site(assignment)
    for relative, digest in pins_for().items():
        path = root / relative
        if path.is_symlink() or shared.digest(path) != digest:
            raise ValueError("Original source changed during AST preparation: " + relative)
    return list(by_file.items()), sites


def runtime_functions():
    """Extend only private metadata namespaces; legacy interfaces stay unchanged."""
    order = list(legacy_runtime.MODULE_ORDER)
    order.insert(order.index("betse.science.cells"), "betse.science.math.finitediff")
    direct = copy.deepcopy(legacy_runtime.DIRECT)
    direct["betse.science.cells"].update(
        tb="betse.science.math.toolbox", fd="betse.science.math.finitediff"
    )
    exports = dict(
        legacy_runtime.EXPORTS,
        parameter_type=("betse.science.parameters", "parameter_type"),
        FiniteDiffSolver=("betse.science.math.finitediff", "FiniteDiffSolver"),
    )
    namespace = dict(
        vars(legacy_runtime), MODULE_ORDER=tuple(order), DIRECT=direct, EXPORTS=exports
    )
    for name, function in vars(legacy_runtime).items():
        if isinstance(function, FunctionType) and function.__module__ == legacy_runtime.__name__:
            namespace[name] = FunctionType(
                function.__code__,
                namespace,
                function.__name__,
                function.__defaults__,
                function.__closure__,
            )
    return namespace


def inputs(raw, configuration):
    conf = shared.scalars(configuration)
    if type(conf) is not dict or set(conf) != {"world options", "general options"}:
        raise ValueError("Exact ordinary world/general configuration required")
    if not same(conf["general options"], {"comp grid size": GRID_SIZE}):
        raise ValueError("Bounded diagnostic uses unchanged native default grid25")
    declared, _, path = legacy.inputs(raw, {"world options": conf["world options"]})
    return declared, conf, path


def public_snapshot(obs):
    caller = obs.caller
    fields = {
        name: value
        for name, value in vars(caller).items()
        if not name.startswith("_cells_") and name not in {"mesh", "grid_obj", "points_tree"}
    }
    parameter = {
        name: obs.parameter.__dict__[name].name
        if name == "cell_lattice_type"
        else obs.parameter.__dict__[name]
        for name in obs.parameter_names
    }
    return dict(
        caller=obs.project(fields),
        mesh=obs.public(obs.mesh),
        parameters=parameter,
        grid=None if obs.grid is None else dict(vars(obs.grid)),
        trees=[shared.tree_state(tree) for tree in obs.trees],
    )


def diagnostics(caller):
    """Observe native outputs only; zero/invalid support never changes the input."""
    import numpy as np

    result = dict(population={}, support={}, geometry={}, gates={}, physical_admission=False)
    errors = []
    for name, field in (
        ("cells", "cell_i"),
        ("membranes", "mem_i"),
        ("vertices", "ecm_verts_unique"),
        ("ecm_nodes", "xypts"),
    ):
        try:
            result["population"][name] = len(getattr(caller, field))
        except Exception as error:
            errors.append(dict(field=field, error=legacy._fallback_error(error)))
    for name in ("maskM", "maskECM", "voronoi_mask"):
        try:
            value = getattr(caller, name)
            result["support"][name] = dict(
                shape=list(value.shape),
                nonzero=int(np.count_nonzero(value)),
                finite=bool(np.isfinite(value).all()),
                size=int(value.size),
            )
        except Exception as error:
            errors.append(dict(field=name, error=legacy._fallback_error(error)))
    for name in ("cell_vol", "mem_vol", "ecm_vol", "cell_centres", "ecm_verts_unique", "xypts"):
        try:
            value = np.asarray(getattr(caller, name))
            result["geometry"][name] = dict(
                size=int(value.size),
                finite=bool(np.isfinite(value).all()),
                positive=bool((value > 0).all()) if name.endswith("vol") else None,
            )
        except Exception as error:
            errors.append(dict(field=name, error=legacy._fallback_error(error)))
    try:
        x0, x1, y0, y1 = caller.xmin, caller.xmax, caller.ymin, caller.ymax
        for name in ("cell_centres", "ecm_verts_unique"):
            points = getattr(caller, name)
            result["geometry"][name]["inside_native_bounds"] = int(
                np.count_nonzero(
                    (points[:, 0] >= x0)
                    & (points[:, 0] <= x1)
                    & (points[:, 1] >= y0)
                    & (points[:, 1] <= y1)
                )
            )
    except Exception as error:
        errors.append(dict(field="bounds", error=legacy._fallback_error(error)))
    finite_masks = all(
        result["support"].get(name, {}).get("finite") is True
        for name in ("maskM", "maskECM", "voronoi_mask")
    )
    result["gates"] = dict(
        populated=result["population"].get("cells", 0) > 1,
        finite_geometry=bool(result["geometry"])
        and all(row["finite"] for row in result["geometry"].values()),
        positive_volumes=all(
            result["geometry"].get(name, {}).get("positive") is True
            for name in ("cell_vol", "mem_vol", "ecm_vol")
        ),
        finite_masks=finite_masks,
        mask_support=finite_masks
        and all(
            result["support"].get(name, {}).get("finite") is True
            and result["support"].get(name, {}).get("nonzero", 0) > 0
            for name in ("maskM", "maskECM")
        ),
    )
    result["observation_errors"] = errors
    result["domain_gate_passed"] = not errors and all(result["gates"].values())
    result["native_grid_constants_changed"] = False
    return result


class Observation(legacy.Observation):
    def __init__(self, capture, record_exception, stream):
        super().__init__(capture, record_exception)
        self.grid, self.trees, self.ordinary = None, [], []
        self.before = self.after = self.stream_before = self.stream_after = None
        self.parameter_names = ()
        self.stream = stream
        self.aliases = {}
        self.raw_locals = {}
        self.work = []

    def save(self, label):
        value = self.snapshot(public_snapshot(self), label)
        if label == "before":
            self.before = value
        else:
            self.ordinary.append((label, value))

    def wrap(self, cls, name, *, role=None, stage=None):
        if cls.__name__ != "Cells" or name != "cell_index":
            return super().wrap(cls, name, role=role, stage=stage)
        original = getattr(cls, name)

        def boundary(obj, *args, **kwargs):
            value = original(obj, *args, **kwargs)
            self.stop()
            # These two fields are only the normalized image/phase adapter,
            # added after the real selected parameter-store snapshot.
            self.parameter_names = tuple(
                name
                for name in vars(self.parameter)
                if name not in {"tissue_default", "conf_dirname"}
            )
            self.stream_before = self.stream()
            self.save("before")
            return value

        setattr(cls, name, boundary)
        return original

    def ordinary_wrap(self, cls, name):
        original = getattr(cls, name)

        def method(obj, *args, **kwargs):
            self.stop()
            if name == "make_maskM":
                self.save("assign_grid_len")
            self.stage = name
            self.event(
                kind="ordinary_body_entry", function="Cells." + name, entry_is_success_or_case=False
            )
            self.stop()
            value = original(obj, *args, **kwargs)
            self.stop()
            self.save(name)
            if name == "environment":
                self.stage = "assign_grid_len"
            return value

        setattr(cls, name, method)


def _guards():
    return sys.getprofile(), sys.gettrace()


def _restore_guards(guards):
    profile, trace = guards
    sys.setprofile(profile)
    sys.settrace(trace)


def _guarded_call(action, guards):
    """A rejected observation must not disable either guard for later probes."""
    try:
        return action()
    finally:
        _restore_guards(guards)


@contextmanager
def _source_attempt(obs, attempt):
    """Keep a failed reference record even before a parameter/caller exists."""
    guards = _guards()
    try:
        yield
    except Exception as failure:
        primary = None
        if isinstance(failure, legacy.CaptureFailure):
            if obs.capture_error is None:
                obs.remember(failure, "source_capture_abort")
        else:
            try:
                primary = obs.record_exception(failure)
            except Exception as secondary:
                primary = legacy._fallback_error(failure)
                obs.remember(secondary, "primary_exception_record")
        attempt.execution = dict(
            status="source_failed",
            source_body_completed=False,
            source_error=primary,
            capture_error=obs.capture_error,
            failed_stage=obs.stage,
            warnings=[],
        )
    finally:
        _restore_guards(guards)


@contextmanager
def source_observation(obs, native_root, phase):
    """Chain the prior guard, defer capture failures during source unwinding."""
    guards = _guards()
    previous = guards[0]
    prefix = str(Path(native_root)) + "/"

    def profile(frame, event, arg):
        if previous is not None:
            try:
                previous(frame, event, arg)
            except Exception as error:
                obs.remember(error, "prior_profiler")
                if event in ("call", "c_call"):
                    raise
        if not frame.f_code.co_filename.startswith(prefix):
            return
        if event == "call" and phase == "descriptor_construction":
            obs.event(
                kind="original_descriptor_metadata_entry",
                phase=phase,
                function=frame.f_code.co_qualname,
                file=frame.f_code.co_filename[len(prefix) :],
                entry_is_success_or_case=False,
            )
            obs.stop()
        if event == "return":
            try:
                obs.raw_locals[
                    frame.f_code.co_filename[len(prefix) :] + ":" + frame.f_code.co_qualname
                ] = dict(frame.f_locals)
            except Exception as error:
                obs.remember(error, "original_return_or_unwind_locals")

    try:
        sys.setprofile(profile)
        yield
    finally:
        _restore_guards(guards)


def descriptor_before_birth(obs, factory, native_root):
    if obs.parameter is not None or obs.caller is not None:
        raise ValueError("Descriptor cannot be retrofitted after parameter/caller birth")
    obs.work.append(dict(phase="descriptor_construction", event="attempt", is_case=False))
    try:
        with source_observation(obs, native_root, "descriptor_construction"):
            value = shared.grid_parameter_type(factory, native_root)
            obs.stop()
    except Exception:
        obs.work.append(dict(phase="descriptor_construction", event="failed", is_case=False))
        raise
    obs.work.append(dict(phase="descriptor_construction", event="returned", is_case=False))
    return value


def retain_raw(obs):
    """Preserve fields independently; opaque self/phase cannot hide arrays."""
    rows = []
    guards = _guards()

    def save(label, value):
        if len(rows) >= 16384:
            error = ValueError("Bounded raw field observation exhausted")
            error.partial = rows
            raise error
        try:
            value = _guarded_call(lambda: obs.capture(value), guards)
            rows.append(dict(label=label, status="saved", value=value))
        except Exception as error:
            rows.append(
                dict(label=label, status="capture_failed", error=legacy._fallback_error(error))
            )
        finally:
            _restore_guards(guards)

    for label, owner in (
        ("caller", obs.caller),
        ("mesh", obs.mesh),
        ("parameters", obs.parameter),
        ("grid", obs.grid),
    ):
        try:
            if owner is None:
                save(label, None)
            else:
                for name, value in vars(owner).items():
                    save(label + "." + name, value)
        except Exception as error:
            _restore_guards(guards)
            save(label + ".fields_error", legacy._fallback_error(error))
    for site, fields in obs.raw_locals.items():
        for name, value in fields.items():
            save("locals." + site + "." + name, value)
    for i, tree in enumerate(obs.trees):
        for name, value in shared.tree_state(tree).items():
            save("tree." + str(i) + "." + name, value)
    return rows


def _finalize_reference(
    obs, execution, descriptor_metadata, *, sites, image_sha256, source_attempted, probes=None
):
    # Keep the legacy adapter's full record at its exact interface, including
    # its historical cell_index label. It is not passed off as an old-endpoint
    # qualification: this new envelope exclusively owns the extended boundary.
    result = dict(
        kind=KIND,
        stop_after=ENDPOINT,
        status="source_failed",
        source_error=execution["source_error"],
        capture_error=execution["capture_error"],
        capture_errors=obs.capture_errors,
        failed_stage=execution["failed_stage"],
        before=obs.before,
        stages=obs.ordinary,
        cache=None,
        stream_before=obs.stream_before,
        stream_after=None,
        warnings=execution["warnings"],
        aliases={},
        descriptor_metadata=descriptor_metadata,
        source_sites=sites,
        original_source_pins=pins_for(),
        base_adapter_result=execution,
        image_file_sha256=image_sha256,
        actual_source_executions=int(source_attempted),
        source_body_completed=execution.get("source_body_completed", False),
        descriptor_constructions_attempted=sum(
            row["phase"] == "descriptor_construction" and row["event"] == "attempt"
            for row in obs.work
        ),
        private_rng_constructions_attempted=1,
        reference_inputs=1,
        work=obs.work,
        work_log_is_complete_native_operation_count=False,
        normalized_parameters_phase_callbacks_only=True,
        shared_machinery=[
            "legacy original-AST clipping/compiler/observer",
            "numpy/scipy/Pillow",
            "native grid descriptor metadata",
            "normalized phase/type aliases",
        ],
        diagnostics=None,
        raw_captures=[],
        physical_or_checkpoint_admission=False,
    )
    if probes is None:
        probes = dict(
            cache=lambda: obs.capture(public_snapshot(obs)),
            stream_after=obs.stream,
            diagnostics=lambda: diagnostics(obs.caller),
            aliases=lambda: dict(
                grid_is_actual=obs.caller.grid_obj is obs.grid,
                X_is_grid=obs.caller.X is obs.grid.cents_X,
                Y_is_grid=obs.caller.Y is obs.grid.cents_Y,
                xy_is_grid=obs.caller.xypts is obs.grid.xy_cents,
                map_is_grid=obs.caller.map_ij2k is obs.grid.map_ij2k_cents,
                all_points_cell_i_is_cell_i=obs.caller.all_points_cell_i is obs.caller.cell_i,
                points_tree_is_retained=any(obs.caller.points_tree is tree for tree in obs.trees),
                voronoi_centres_is_xypts=obs.caller.voronoi_centres is obs.caller.xypts,
            ),
        )
        if obs.caller is None:
            probes = dict(stream_after=obs.stream)
    guards = _guards()
    for name, action in probes.items():
        try:
            result[name] = _guarded_call(action, guards)
        except Exception as error:
            obs.remember(error, "final_" + name)
        finally:
            _restore_guards(guards)
    # Independent forensic probes retain available raw parents/partials even
    # when another field is opaque. Their gaps cannot be credited as captures.
    try:
        result["raw_captures"] = _guarded_call(lambda: retain_raw(obs), guards)
    except Exception as error:
        result["raw_captures"] = getattr(error, "partial", [])
        obs.remember(error, "raw_field_capture")
    result["raw_capture_gaps"] = [
        row["label"] for row in result["raw_captures"] if row["status"] != "saved"
    ]
    result["raw_captures_are_complete_live_object_archive"] = False
    result["capture_error"] = obs.capture_error
    if (
        execution["status"] == "source_completed"
        and execution.get("source_body_completed") is True
        and not obs.capture_errors
        and [name for name, _ in obs.ordinary] == list(METHODS)
        and result["cache"] is not None
        and all(result["aliases"].values())
    ):
        result["status"] = "source_completed"
        result["failed_stage"] = None
    elif result["failed_stage"] is None and obs.capture_error is not None:
        result["failed_stage"] = "final_metadata"
    return result


def evaluate(raw, configuration, native_root, *, record_exception):
    """One real reference prefix; callers must supply review/release/resource gates."""
    declared, conf, image_path = inputs(raw, configuration)
    groups, sites = source_nodes(native_root)
    import numpy as np
    from PIL import Image
    from scipy.interpolate import RectBivariateSpline, griddata
    from scipy.ndimage import gaussian_filter
    from scipy.spatial import ConvexHull, Delaunay, cKDTree

    from validation.betse import betse_initial_mesh_preparation_wire as wire

    row = declared["seed_stream_before"]
    rng = np.random.RandomState(0)
    rng.set_state((row[0], np.asarray(row[1], np.uint32), row[2], row[3], row[4]))
    global_before = legacy.stream_record(np.random, np.__version__)

    def stream():
        return legacy.stream_record(rng, np.__version__)

    obs = Observation(wire.capture, record_exception, stream)

    def log(*args, **kwargs):
        obs.event(kind="log", args=args, kwargs=kwargs)
        obs.stop()

    attempt = SimpleNamespace(execution=None, descriptor_metadata=None, source_body_attempted=False)
    with _source_attempt(obs, attempt):
        obs.stage = "namespace_assembly"
        builder = runtime_functions()
        namespace = builder["build"](
            groups,
            native_root=native_root,
            numpy=np,
            image=Image,
            spline=RectBivariateSpline,
            hull=ConvexHull,
            delaunay=Delaunay,
            tree=cKDTree,
            rng=rng,
            log=log,
        )
        parameters = namespace["modules"]["betse.science.parameters"]
        parameters["SimpleNamespace"] = SimpleNamespace
        obs.stage = "descriptor_construction"
        parameter_type, attempt.descriptor_metadata = descriptor_before_birth(
            obs, namespace["parameter_type"], native_root
        )
        cells = namespace["modules"]["betse.science.cells"]

        def tree(*args, **kwargs):
            obs.stop()
            value = cKDTree.__new__(cKDTree)
            obs.trees.append(value)
            value.__init__(*args, **kwargs)
            obs.stop()
            return value

        cells.update(
            cKDTree=tree, interp=SimpleNamespace(griddata=griddata), gaussian_filter=gaussian_filter
        )
        grid_type = namespace["FiniteDiffSolver"]
        obs.wrap(grid_type, "__init__", role="grid", stage="grid_constructor")
        obs.wrap(grid_type, "cell_grid", stage="cell_grid")
        for method in BODY_METHODS:
            obs.ordinary_wrap(namespace["Cells"], method)

        def containers(**kwargs):
            return parameter_type(**kwargs) if "_conf" in kwargs else SimpleNamespace(**kwargs)

        obs.stage = "make_world_prefix"
        attempt.source_body_attempted = True
        with source_observation(obs, native_root, "ordinary_reference"):
            attempt.execution = clone(legacy._execute, SimpleNamespace=containers)(
                namespace,
                declared,
                conf,
                capture=wire.capture,
                record_exception=record_exception,
                stream=stream,
                image_unchanged=lambda: (
                    shared.digest(image_path) == declared["image_recipe"]["image_sha256"]
                ),
                global_unchanged=lambda: same(
                    global_before, legacy.stream_record(np.random, np.__version__)
                ),
                source_unchanged=lambda: legacy._source_unchanged(native_root, pins_for()),
                native_root=native_root,
                sites=sites,
                pins=pins_for(),
                log_events=obs.events,
                observation=obs,
            )
    return _finalize_reference(
        obs,
        attempt.execution,
        attempt.descriptor_metadata,
        sites=sites,
        image_sha256=declared["image_recipe"]["image_sha256"],
        source_attempted=attempt.source_body_attempted,
    )
