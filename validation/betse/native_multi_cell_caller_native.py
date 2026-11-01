"""Independent original-source multi-cell caller through cell_index.

The external runner must own release, immutable inputs and resource limits.
This module imports no Cells model. It constructs a fresh normalized parameter
and phase boundary; it does not claim full Parameters/YAML/SimPhase authority.
Only final parameters/caller/mesh and the two MT states are comparison targets.
Original helper modules, numerical libraries and the wire encoder are disclosed.
"""

import copy
import hashlib
import json
import math
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

from validation.betse import native_multi_cell_caller_native_source as source
from validation.betse import native_multi_cell_caller_runtime as runtime
from validation.betse.native_multi_cell_caller_compare import NATIVE_FIELDS

KIND = "cells.independent_multi_cell_caller@1"
CONTROL_FIELDS = (
    "single_cell",
    "svg_override",
    "alpha_shape",
    "use_centroids",
    "refine_mesh",
    "maximum_voronoi_steps",
    "voronoi_convergence",
)
CONTROLS = dict(
    kind="cells.betse_make_voronoi_controls@1",
    single_cell=False,
    svg_override=False,
    alpha_shape=0.05,
    use_centroids=True,
    refine_mesh=False,
    maximum_voronoi_steps=2,
    voronoi_convergence=1e-30,
)


def _same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(
        b, sort_keys=True, allow_nan=False
    )


def inputs(raw, configuration):
    """Validate only the two existing non-SVG, non-refining diagnostic recipes."""
    value = source.shared.scalars(raw)
    if type(value) is not dict or set(value) != {
        "seed_recipe",
        "seed_stream_before",
        "controls",
        "image_recipe",
    }:
        raise ValueError("Require the complete independent four-field source recipe")
    recipe = value["seed_recipe"]
    if (
        type(recipe) is not dict
        or set(recipe)
        != {
            "kind",
            "provenance",
            "lattice_type",
            "world_len_m",
            "cell_radius_m",
            "lattice_disorder",
        }
        or recipe.get("kind") != "cells.betse_lattice_seed_recipe@1"
        or recipe.get("lattice_type") not in ("SQUARE", "HEX")
    ):
        raise ValueError("Unknown native lattice recipe")
    if type(recipe["provenance"]) is not str or not recipe["provenance"]:
        raise ValueError("Require explicit recipe provenance")
    for name in ("world_len_m", "cell_radius_m", "lattice_disorder"):
        if type(recipe[name]) not in (int, float) or not math.isfinite(recipe[name]):
            raise ValueError("Finite scalar required: " + name)
    if (
        recipe["world_len_m"] <= 0
        or recipe["cell_radius_m"] <= 0
        or not 0 <= recipe["lattice_disorder"] <= 1
    ):
        raise ValueError("Outside declared lattice domain")
    if not 1 <= int(recipe["world_len_m"] / (2 * recipe["cell_radius_m"])) <= 8:
        raise ValueError("Outside bounded diagnostic lattice size")
    if not _same(value["controls"], CONTROLS):
        raise ValueError("Only declared non-SVG multi-cell core controls are supported")
    conf = source.shared.scalars(configuration)
    if type(conf) is not dict or set(conf) != {"world options"}:
        raise ValueError("Require the normalized caller configuration only")
    world = conf["world options"]
    if type(world) is not dict or set(world) != {
        "cell height",
        "cell spacing",
        "simulate single cell",
        "import from svg",
        "alpha shape",
        "use centers",
        "mesh refinement",
    }:
        raise ValueError("Incomplete or extended world configuration")
    for name in ("cell height", "cell spacing"):
        if (
            type(world[name]) not in (int, float)
            or not math.isfinite(world[name])
            or world[name] <= 0
        ):
            raise ValueError("Finite positive geometry scalar required")
    fixed = dict(world)
    fixed.pop("cell height")
    fixed.pop("cell spacing")
    if not _same(
        fixed,
        {
            "simulate single cell": False,
            "import from svg": None,
            "alpha shape": 0.05,
            "use centers": True,
            "mesh refinement": {
                "refine mesh": False,
                "maximum steps": 2,
                "convergence threshold": 1e-30,
            },
        },
    ):
        raise ValueError("Configuration does not produce the declared source controls")
    image = value["image_recipe"]
    if (
        type(image) is not dict
        or set(image) != {"kind", "filename", "conf_dirname", "image_sha256"}
        or image.get("kind") != "cells.betse_image_mask_source@1"
    ):
        raise ValueError("Unknown image recipe")
    if any(type(image[name]) is not str for name in ("filename", "conf_dirname", "image_sha256")):
        raise ValueError("Image paths/hash must be strings")
    path = Path(image["filename"])
    if not path.is_absolute():
        path = Path(image["conf_dirname"]) / path
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2**20
        or source.shared.digest(path) != image["image_sha256"]
    ):
        raise ValueError("Changed, missing, linked or oversized declared image")
    state = value["seed_stream_before"]
    if (
        type(state) is not list
        or len(state) != 5
        or state[0] != "MT19937"
        or type(state[1]) is not list
        or len(state[1]) != 624
        or any(type(word) is not int or not 0 <= word < 2**32 for word in state[1])
        or type(state[2]) is not int
        or not 0 <= state[2] <= 624
        or type(state[3]) is not int
        or state[3] not in (0, 1)
        or type(state[4]) not in (int, float)
        or not math.isfinite(state[4])
    ):
        raise ValueError("Invalid complete MT stream")
    return value, conf, path


def stream_record(rng, numpy_version):
    row = rng.get_state()
    state = [row[0], row[1].tolist(), int(row[2]), int(row[3]), float(row[4])]
    identity = dict(
        rng_id="numpy_mt19937_legacy_state_with_gaussian_cache@1",
        numpy_version=numpy_version,
        state=state,
    )
    return dict(
        state_json=json.dumps(state, separators=(",", ":"), allow_nan=False),
        numpy_version=numpy_version,
        identity=hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest(),
    )


class CaptureFailure(Exception):
    """A metadata failure, distinguished from the original source exception."""


def _fallback_error(error):
    """Retain a bounded cause/context graph if the primary recorder itself fails."""
    nodes, seen = [], {}

    def visit(item):
        if item is None:
            return None
        if id(item) in seen:
            return seen[id(item)]
        if len(nodes) == 64:
            return "truncated_after_64_errors"
        index = seen[id(item)] = len(nodes)
        try:
            message = str(item)
        except Exception:
            message = "<exception message unavailable>"
        row = dict(type=type(item).__name__, module=type(item).__module__, message=message)
        nodes.append(row)
        row.update(
            cause=visit(item.__cause__),
            context=visit(item.__context__),
            suppress_context=bool(item.__suppress_context__),
        )
        return index

    visit(error)
    return dict(
        type=nodes[0]["type"], message=nodes[0]["message"], chain=nodes, recorder_failed=True
    )


def _source_unchanged(root, pins):
    return all(
        not (Path(root) / relative).is_symlink()
        and source.shared.digest(Path(root) / relative) == expected
        for relative, expected in pins.items()
    )


def comparison_record(result):
    """Select the strict comparison wire; retain the full forensic result separately.

    This projection is not an input/source authentication substitute. The
    execution runner must bind both this view and the complete saved result.
    """
    if result["status"] == "source_completed" and (
        result["source_body_completed"] is not True
        or result["original_source_unchanged"] is not True
        or result["capture_errors"]
        or result["source_error"] is not None
        or result["capture_error"] is not None
        or result["image_unchanged"] is not True
        or result["global_random_stream_unchanged"] is not True
        or any(value is not True for value in result["aliases"].values())
    ):
        raise ValueError("Completed comparison view contradicts full source evidence")
    return {name: result[name] for name in NATIVE_FIELDS}


class Observation:
    def __init__(self, capture, record_exception):
        self.capture = capture
        self.record_exception = record_exception
        self.caller = self.mesh = self.mask = self.parameter = None
        self.mask_locals = {}
        self.events, self.stages, self.capture_errors = [], [], []
        self.capture_error = None
        self.stage = "parameter_constructor"

    def remember(self, error, where):
        try:
            saved = self.record_exception(error)
        except Exception as secondary:
            saved = _fallback_error(error)
            saved["recorder_error"] = _fallback_error(secondary)
        self.capture_errors.append(dict(stage=where, error=saved))
        if self.capture_error is None:
            self.capture_error = saved

    def stop(self):
        if self.capture_error is not None:
            raise CaptureFailure("Original-source observation failed")

    def event(self, **row):
        try:
            if len(self.events) >= 100000:
                raise ValueError("Bounded original-source entry ledger exhausted")
            self.events.append(dict(sequence=len(self.events), **row))
        except Exception as error:
            self.remember(error, "events")

    def token(self):
        if self.mask is None or not {"xpts", "ypts"} <= self.mask_locals.keys():
            raise ValueError("Original mask constructor observation unavailable")
        return dict(
            kind="independent_image_mask_token",
            identity=None,
            image_identity=None,
            xpts_m=self.mask_locals["xpts"],
            ypts_m=self.mask_locals["ypts"],
            clipping_matrix=self.mask.clipping_matrix,
            clipcurve_m=self.mask.clipcurve,
        )

    def project(self, value, memo=None):
        if value is self.mask and self.mask is not None:
            return self.token()
        memo = {} if memo is None else memo
        if type(value) in (dict, list, tuple):
            if id(value) in memo:
                return memo[id(value)]
            if type(value) is dict:
                result = {}
                memo[id(value)] = result
                result.update((key, self.project(item, memo)) for key, item in value.items())
            else:
                result = [self.project(item, memo) for item in value]
                result = tuple(result) if type(value) is tuple else result
                memo[id(value)] = result
            return result
        return value

    def public(self, value, *, caller=False):
        return self.project(
            {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_cells_") and not (caller and key == "mesh")
            }
        )

    def snapshot(self, value, where):
        try:
            return self.capture(value)
        except Exception as error:
            self.remember(error, where)
            raise CaptureFailure("Snapshot failed: " + where) from error

    def wrap(self, cls, name, *, role=None, stage=None):
        original = getattr(cls, name)

        def observed(obj, *args, **kwargs):
            self.stop()
            if role is not None:
                setattr(self, role, obj)
            self.stage = stage or name
            self.event(
                kind="source_wrapper_entry",
                function=cls.__name__ + "." + name,
                entry_is_success_or_case=False,
            )
            self.stop()
            # Deferred trace/log observation errors never replace a source
            # error unwinding this original call. A successful call must stop
            # at its boundary before the next source stage if observation failed.
            result = original(obj, *args, **kwargs)
            self.stop()
            if cls.__name__ == "Cells" and name != "make_world":
                cache = self.snapshot(self.public(obj, caller=True), name)
                self.stages.append((name, cache))
            return result

        setattr(cls, name, observed)
        return original


def _execute(
    namespace,
    declared,
    configuration,
    *,
    capture,
    record_exception,
    stream,
    image_unchanged,
    global_unchanged,
    source_unchanged,
    native_root,
    sites,
    pins,
    log_events,
    observation=None,
):
    """Run fresh original objects; injection seams exist only for blocked controls."""
    obs = observation if observation is not None else Observation(capture, record_exception)
    obs.events = log_events
    caller_type, mesh_type, mask_type = (
        namespace[key] for key in ("Cells", "DECMesh", "TissuePickerImageMask")
    )
    mask_original = obs.wrap(mask_type, "__init__", role="mask", stage="image_mask")
    obs.wrap(mesh_type, "__init__", role="mesh", stage="mesh_constructor")
    obs.wrap(mesh_type, "clip_and_refine", stage="clip_and_refine")
    obs.wrap(caller_type, "__init__", role="caller", stage="Cells_constructor")
    obs.wrap(caller_type, "_make_cell_lattice", stage="Cells_lattice")
    obs.wrap(caller_type, "make_voronoi", stage="Voronoi_tail")
    obs.wrap(caller_type, "cell_index", stage="cell_index")
    previous_trace, previous_profile = sys.gettrace(), sys.getprofile()
    trace_handlers = {}

    def trace(frame, event, arg):
        # Preserve an outer trace's per-frame handler rather than silently
        # replacing it with the global function on each line.
        if previous_trace is not None:
            handler = previous_trace if event == "call" else trace_handlers.get(id(frame))
            if handler is not None:
                trace_handlers[id(frame)] = handler(frame, event, arg)
            if event == "return":
                trace_handlers.pop(id(frame), None)
        if frame.f_code is mask_original.__code__ and event == "return":
            try:
                obs.mask_locals = dict(frame.f_locals)
            except Exception as error:
                obs.remember(error, "mask_constructor_locals")
        return trace

    prefix = str(Path(native_root)) + "/"

    def profile(frame, event, arg):
        if previous_profile is not None:
            previous_profile(frame, event, arg)
        if event == "call" and frame.f_code.co_filename.startswith(prefix):
            obs.event(
                kind="original_source_entry",
                function=frame.f_code.co_qualname,
                file=frame.f_code.co_filename[len(prefix) :],
                line=frame.f_code.co_firstlineno,
                entry_is_success_or_case=False,
            )

    def callback(*args, **kwargs):
        obs.stop()
        obs.event(kind="normalized_phase_callback", args=args, kwargs=kwargs)
        obs.stop()

    error, completed = None, False
    parameter_cache = before = None
    warnings_rows = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sys.settrace(trace)
            sys.setprofile(profile)
            recipe = declared["seed_recipe"]
            p = obs.parameter = SimpleNamespace(
                _conf=copy.deepcopy(configuration),
                world_len=float(recipe["world_len_m"]),
                cell_radius=float(recipe["cell_radius_m"]),
                cell_lattice_disorder=float(recipe["lattice_disorder"]),
                cell_lattice_type=getattr(namespace["CellLatticeType"], recipe["lattice_type"]),
            )
            obs.stage = "parameter_stores"
            namespace["store_parameters"](p)
            obs.stop()
            if not _same(
                {name: getattr(p, name) for name in CONTROL_FIELDS},
                {name: declared["controls"][name] for name in CONTROL_FIELDS},
            ):
                raise ValueError("Original parameter stores disagree with declared controls")
            parameter_cache = obs.snapshot(
                {
                    key: value.name if key == "cell_lattice_type" else value
                    for key, value in vars(p).items()
                },
                "parameters",
            )
            image = declared["image_recipe"]
            p.tissue_default = SimpleNamespace(picker_image_filename=image["filename"])
            p.conf_dirname = image["conf_dirname"]
            phase = SimpleNamespace(
                p=p,
                callbacks=SimpleNamespace(progress_stated=callback, progressed_next=callback),
                die_unless_kind_seed=lambda: callback("normalized_seed_phase_assertion"),
            )
            before = stream()
            obs.stage = "Cells_constructor"
            caller = caller_type(p)
            obs.stop()
            obs.stage = "make_world_prefix"
            caller.make_world(phase)
            obs.stop()
            completed = True
        except Exception as failure:
            if not isinstance(failure, CaptureFailure):
                try:
                    error = record_exception(failure)
                except Exception as secondary:
                    error = _fallback_error(failure)
                    obs.remember(secondary, "primary_exception_record")
        finally:
            sys.setprofile(previous_profile)
            sys.settrace(previous_trace)
            warnings_rows = [str(w.message) for w in caught]

    def aliases():
        caller, mesh, mask = obs.caller, obs.mesh, obs.mask
        return dict(
            ecm_verts_is_vcell_verts=caller.ecm_verts is mesh.vcell_verts,
            ecm_verts_unique_is_vor_verts=caller.ecm_verts_unique is mesh.vor_verts,
            cluster_mask_is_clipping_matrix=caller.cluster_mask is mask.clipping_matrix,
            cell_centres_is_vor_cents=caller.cell_centres is mesh.vor_cents,
            mesh_image_mask_is_actual_mask=caller.mesh is mesh and mesh.image_mask is mask,
        )

    result = dict(
        kind=KIND,
        stop_after="cell_index",
        source_body_completed=completed,
        status="source_failed",
        source_error=error,
        capture_error=obs.capture_error,
        failed_stage=None if completed else obs.stage,
        parameter_cache=parameter_cache,
        caller_cache=None,
        mesh_cache=None,
        stream_before=before,
        source_sites=sites,
        original_source_pins=pins,
        events=obs.events,
        stages=obs.stages,
        warnings=warnings_rows,
        aliases=None,
        actual_source_executions=1,
        normalized_parameters_phase_callbacks_only=True,
        full_package_or_physical_admission=False,
        image_file_sha256=declared["image_recipe"]["image_sha256"],
        runtime_metadata=namespace.get("metadata", {}),
        capture_errors=obs.capture_errors,
    )
    probes = dict(
        caller_cache=lambda: (
            None if obs.caller is None else capture(obs.public(obs.caller, caller=True))
        ),
        mesh_cache=lambda: None if obs.mesh is None else capture(obs.public(obs.mesh)),
        aliases=aliases,
        stream_after=stream,
        image_unchanged=image_unchanged,
        global_random_stream_unchanged=global_unchanged,
        original_source_unchanged=source_unchanged,
    )
    # Retain the primary source result even when partial objects cannot yet be
    # represented by a complete cache. Every secondary failure stays explicit.
    for name, action in probes.items():
        try:
            result[name] = action()
        except Exception as failure:
            obs.remember(failure, name)
            result[name] = None
        finally:
            # CPython clears a profiler/trace when that hook raises. A late
            # metadata refusal must not leave later probes or our caller
            # without the original guard, even though source work has ended.
            sys.setprofile(previous_profile)
            sys.settrace(previous_trace)
    result["capture_error"] = obs.capture_error
    good = (
        completed
        and error is None
        and obs.capture_error is None
        and all(
            result.get(name) is True
            for name in (
                "image_unchanged",
                "global_random_stream_unchanged",
                "original_source_unchanged",
            )
        )
        and result["aliases"] is not None
        and all(value is True for value in result["aliases"].values())
    )
    result["status"] = "source_completed" if good else "source_failed"
    if not good and result["failed_stage"] is None:
        result["failed_stage"] = "final_metadata"
    return result


def evaluate(raw, configuration, native_root, *, record_exception):
    """One actual reference call; never invoke outside the release/resource gate."""
    declared, conf, image_path = inputs(raw, configuration)
    groups, sites = source.source_nodes(native_root)
    import numpy as np
    from PIL import Image
    from scipy.interpolate import RectBivariateSpline
    from scipy.spatial import ConvexHull, Delaunay, cKDTree

    from validation.betse import betse_initial_mesh_preparation_wire as wire

    row = declared["seed_stream_before"]
    rng = np.random.RandomState(0)
    rng.set_state((row[0], np.asarray(row[1], np.uint32), row[2], row[3], row[4]))
    global_before = np.random.get_state()
    observation = Observation(wire.capture, record_exception)
    events = observation.events

    def log(*args, **kwargs):
        observation.event(kind="log", args=args, kwargs=kwargs)
        observation.stop()

    namespace = runtime.build(
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

    def global_unchanged():
        after = np.random.get_state()
        return (
            global_before[0] == after[0]
            and np.array_equal(global_before[1], after[1])
            and global_before[2:] == after[2:]
        )

    return _execute(
        namespace,
        declared,
        conf,
        capture=wire.capture,
        record_exception=record_exception,
        stream=lambda: stream_record(rng, np.__version__),
        image_unchanged=lambda: (
            source.shared.digest(image_path) == declared["image_recipe"]["image_sha256"]
        ),
        global_unchanged=global_unchanged,
        source_unchanged=lambda: _source_unchanged(native_root, source.pins_for()),
        native_root=native_root,
        sites=sites,
        pins=source.pins_for(),
        log_events=events,
        observation=observation,
    )
