"""Independent original-BETSE AST execution through ordinary near_neigh.

No Cells model, source kernel, fixture or cache implementation is imported.
The native source is compiled afresh. A normalized parameter/phase boundary
supplies scalar configuration and records callbacks; it is not the full native
Parameters/YAML/SimPhase/package lifecycle. Numerical library implementations
and the independent wire encoder are shared and must be recorded by the runner.
"""

import __future__

import ast
import builtins
import copy
import hashlib
import json
import math
import os
import struct
import sys
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

NATIVE_PINS = {
    "betse/exceptions.py": ("c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971"),
    "betse/lib/numpy/nparray.py": (
        "f7c1362a5c6daf545b6a516e0ce06fe53242c13abd05a5f2520226b7dd222889"
    ),
    "betse/lib/numpy/npscalar.py": (
        "02080a869ae0cda8e84851c3d6e5f8d95b88a90ea3cd122c33a83c000da7af12"
    ),
    "betse/lib/pil/pilnumpy.py": (
        "0e0f9c7589c8ae0d41d59c0f8306db66f4d87086932e1c7d7bf9cbe340f631b4"
    ),
    "betse/science/cells.py": ("be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"),
    "betse/science/math/mesh.py": (
        "fd0dc21e1f82aa71e19a487f3b91c4b5258f02aec4c69f22c2bf3c419e425c38"
    ),
    "betse/science/math/toolbox.py": (
        "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3"
    ),
    "betse/science/parameters.py": (
        "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"
    ),
    "betse/science/tissue/picker/tispickcls.py": (
        "c1c592ddc600479806da73c37ade7aecf19df0f49cd46706a74ad6bb9f1bc773"
    ),
    "betse/science/tissue/picker/tispickimage.py": (
        "75c5252998e73cce4f94d8ee03de5c206a82fae6caa1f33d0ae53260cef4a1ac"
    ),
    "betse/util/math/geometry/geopoint.py": (
        "e768b5ebcffd95eea6ce0cc35a8d0f5b6e7ccda6299b77c9e0a80edf1b548a41"
    ),
    "betse/util/math/geometry/polygon/geopoly.py": (
        "8a031ba303e024f13964f8bd2f225b72128f27574c10ff84a21e100a67727f83"
    ),
    "betse/util/math/mathinterp.py": (
        "15f3f217e151fbd9e01dff55d771d600e895b9585afc123f1ee54af2a166f4de"
    ),
    "betse/util/math/mathoper.py": (
        "375d44263e2b8fbda7f99ee0b63c4f62e2090dc5e8089ece8447df6f8bac4854"
    ),
    "betse/util/path/dirs.py": ("c18337d0564727251cf5367cca094ad373148f159ca55317d3d64de8a2436d4a"),
    "betse/util/path/files.py": (
        "5bb48c45c609fe7f161cc5062d6a5ab7a543409333cd004d225bb4cb605a4a66"
    ),
    "betse/util/path/pathnames.py": (
        "7530fe8e0deeb0806787859c01a0d1d4448457af8126d859ceb82594ea69969b"
    ),
    "betse/util/path/paths.py": (
        "4dd3c7aa0a9e9e973d556ecaea6b9dcf63ac9e248e1011560516d7f901521b4f"
    ),
    "betse/util/type/iterable/sequences.py": (
        "fbd68c0d532ad56d81e8a90696d95465cd21c78b46db28f34f939f74f412abb1"
    ),
    "betse/util/type/types.py": (
        "9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089"
    ),
}
METHODS = ("cellVerts", "cellMatrices", "cell_vols", "mem_processing", "near_neigh")
STORE_LINES = (533, 534, 535, 536, 1118, 1119, 1122, 1127, 1128, 1129, 1130, 1131)
FUNCTIONS = {
    "betse/util/type/types.py": ("type_check",),
    "betse/util/type/iterable/sequences.py": ("is_sequence",),
    "betse/lib/numpy/nparray.py": ("from_iterable", "to_signed"),
    "betse/lib/numpy/npscalar.py": ("to_python",),
    "betse/util/math/geometry/geopoint.py": ("is_point",),
    "betse/util/math/geometry/polygon/geopoly.py": (
        "die_unless_polygon",
        "is_polygon",
        "is_convex",
        "is_cyclic_quad",
        "orient_counterclockwise",
    ),
    "betse/util/math/mathoper.py": ("det1d",),
    "betse/util/path/pathnames.py": (
        "is_absolute",
        "is_relative",
        "die_if_absolute",
        "join",
        "get_basename",
    ),
    "betse/util/path/files.py": ("is_file", "die_unless_file"),
    "betse/util/path/dirs.py": ("is_dir",),
    "betse/util/path/paths.py": ("is_path",),
    "betse/lib/pil/pilnumpy.py": ("load_image",),
    "betse/util/math/mathinterp.py": ("interp2d_linear",),
    "betse/science/math/toolbox.py": ("flatten",),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_nodes(root):
    """Read/verify/assemble AST only; no numerical imports or execution."""
    root = Path(root)
    trees = {}
    for name, expected in NATIVE_PINS.items():
        path = root / name
        if path.is_symlink() or digest(path) != expected:
            raise ValueError("Changed original source: " + name)
        trees[name] = ast.parse(path.read_bytes(), filename=str(path))
    if not trees:
        raise ValueError("An explicit pinned original-source closure is required")
    groups, sites = [], {}

    def add(file, nodes):
        nodes = copy.deepcopy(list(nodes))
        groups.append((file, nodes))
        for node in nodes:
            name = getattr(node, "name", "assignment_" + str(node.lineno))
            sites[file + ":" + name] = dict(
                first_line=node.lineno,
                last_line=node.end_lineno,
                ast_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
            )

    def cls(file, name):
        return next(n for n in trees[file].body if isinstance(n, ast.ClassDef) and n.name == name)

    add(
        "betse/exceptions.py",
        (n for n in trees["betse/exceptions.py"].body if isinstance(n, ast.ClassDef)),
    )
    for file, names in FUNCTIONS.items():
        add(
            file,
            (
                next(
                    n for n in trees[file].body if isinstance(n, ast.FunctionDef) and n.name == name
                )
                for name in names
            ),
        )
    file = "betse/lib/numpy/nparray.py"
    add(
        file,
        (
            next(
                n
                for n in trees[file].body
                if isinstance(n, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "DTYPE_UNSIGNED_TO_SIGNED"
                    for t in n.targets
                )
            ),
        ),
    )
    add("betse/lib/pil/pilnumpy.py", (cls("betse/lib/pil/pilnumpy.py", "ImageModeType"),))
    add(
        "betse/science/tissue/picker/tispickcls.py",
        (cls("betse/science/tissue/picker/tispickcls.py", "TissuePickerABC"),),
    )
    add(
        "betse/science/tissue/picker/tispickimage.py",
        (
            cls("betse/science/tissue/picker/tispickimage.py", "TissuePickerImageMask"),
            cls("betse/science/tissue/picker/tispickimage.py", "TissuePickerImage"),
        ),
    )
    add("betse/science/math/mesh.py", (cls("betse/science/math/mesh.py", "DECMesh"),))
    original = cls("betse/science/cells.py", "Cells")
    selected = (
        "__init__",
        "make_world",
        "_make_cell_lattice",
        "make_voronoi",
        "cell_index",
        *METHODS,
    )
    cells = copy.deepcopy(original)
    cells.body = [n for n in cells.body if isinstance(n, ast.FunctionDef) and n.name in selected]
    make_world = next(n for n in cells.body if n.name == "make_world")
    stop = next(
        i
        for i, n in enumerate(make_world.body)
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Attribute)
        and n.value.func.attr == "near_neigh"
    )
    make_world.body = make_world.body[: stop + 1]
    add("betse/science/cells.py", (cells,))
    parameters = cls("betse/science/parameters.py", "Parameters")
    stores = {n.lineno: n for n in ast.walk(parameters) if isinstance(n, ast.Assign)}
    wrapper = ast.parse("def store_parameters(self):\n    pass\n").body[0]
    wrapper.body = [copy.deepcopy(stores[line]) for line in STORE_LINES]
    ast.fix_missing_locations(wrapper)
    add("betse/science/parameters.py", (wrapper,))
    return groups, sites


def scalars(value):
    """Decode only the input recipe's explicit Python float records."""
    if type(value) is dict:
        if set(value) == {"float64_bits"}:
            raw = bytes.fromhex(value["float64_bits"])
            if len(raw) != 8:
                raise ValueError("Malformed input float")
            return struct.unpack("<d", raw)[0]
        return {k: scalars(v) for k, v in value.items()}
    if type(value) is list:
        return [scalars(v) for v in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise ValueError("Unsupported declared input")


def inputs(raw, configuration):
    value = scalars(raw)
    if type(value) is not dict or set(value) != {
        "seed_recipe",
        "seed_stream_before",
        "controls",
        "image_recipe",
    }:
        raise ValueError("Require complete independent native input recipe")
    recipe, controls = value["seed_recipe"], value["controls"]
    if (
        set(recipe)
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
        raise ValueError("Unknown source lattice recipe")
    if (
        set(controls)
        != {
            "kind",
            "single_cell",
            "svg_override",
            "alpha_shape",
            "use_centroids",
            "refine_mesh",
            "maximum_voronoi_steps",
            "voronoi_convergence",
        }
        or controls.get("kind") != "cells.betse_make_voronoi_controls@1"
    ):
        raise ValueError("Unknown native caller control fields")
    if controls.get("single_cell") is not True or controls.get("svg_override") is not False:
        raise ValueError("Only the original single-cell non-SVG caller is released")
    for key in ("world_len_m", "cell_radius_m", "lattice_disorder"):
        if type(recipe.get(key)) not in (int, float) or not math.isfinite(recipe[key]):
            raise ValueError("Finite declared scalar required: " + key)
    if (
        recipe["world_len_m"] <= 0
        or recipe["cell_radius_m"] <= 0
        or not 0 <= recipe["lattice_disorder"] <= 1
    ):
        raise ValueError("Outside declared diagnostic scalar domain")
    if int(recipe["world_len_m"] / (2 * recipe["cell_radius_m"])) > 8:
        raise ValueError("Diagnostic lattice bound exceeded")
    if (
        type(configuration) is not dict
        or set(configuration) != {"world options"}
        or set(configuration["world options"]) != {"cell height", "cell spacing"}
    ):
        raise ValueError("Require explicit geometry configuration")
    for v in configuration["world options"].values():
        if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
            raise ValueError("Require declared finite positive geometry controls")
    image = value["image_recipe"]
    if (
        set(image) != {"kind", "filename", "conf_dirname", "image_sha256"}
        or image.get("kind") != "cells.betse_image_mask_source@1"
    ):
        raise ValueError("Unknown image recipe fields")
    path = Path(image["filename"])
    if not path.is_absolute():
        path = Path(image["conf_dirname"]) / path
    if path.is_symlink() or path.stat().st_size > 2**20 or digest(path) != image["image_sha256"]:
        raise ValueError("Changed/oversized original image")
    before = value["seed_stream_before"]
    if (
        type(before) is not list
        or len(before) != 5
        or before[0] != "MT19937"
        or type(before[1]) is not list
        or len(before[1]) != 624
        or any(type(w) is not int or not 0 <= w < 2**32 for w in before[1])
        or type(before[2]) is not int
        or not 0 <= before[2] <= 624
        or type(before[3]) is not int
        or before[3] not in (0, 1)
        or type(before[4]) not in (int, float)
        or not math.isfinite(before[4])
    ):
        raise ValueError("Invalid complete MT state")
    return value, path


def finalize(record, probes, record_exception):
    """Secondary metadata failures never replace the original source outcome."""
    result = dict(record)
    result["secondary_capture_errors"] = []
    for name, action in probes.items():
        try:
            result[name] = action()
        except Exception as error:
            saved = record_exception(error)
            result[name] = None
            result["secondary_capture_errors"].append(dict(stage=name, error=saved))
            if result["capture_error"] is None:
                result["capture_error"] = saved
    completed = (
        result["source_body_completed"]
        and result["capture_error"] is None
        and result["image_unchanged"] is True
        and result["global_random_stream_unchanged"] is True
    )
    result["status"] = "source_completed" if completed else "source_failed"
    if not completed and result["failed_stage"] is None:
        result["failed_stage"] = "final_metadata"
    return result


def evaluate(raw, configuration, native_root, *, record_exception):
    """One actual source execution; caller must own resource/release gates."""
    declared, image_path = inputs(raw, configuration)
    groups, sites = source_nodes(native_root)
    import numpy as np
    from PIL import Image
    from scipy.interpolate import RectBivariateSpline
    from scipy.spatial import ConvexHull, Delaunay, cKDTree

    from validation.betse import betse_initial_mesh_preparation_wire as wire

    before = declared["seed_stream_before"]
    rng = np.random.RandomState(0)
    rng.set_state((before[0], np.asarray(before[1], np.uint32), before[2], before[3], before[4]))
    original_global = np.random.get_state()
    events, stages, captures = [], [], []
    state = dict(
        caller=None,
        parameter=None,
        constructing_mesh=None,
        before_geometry=None,
        capture_error=None,
        stage="namespace",
    )

    def stream():
        row = rng.get_state()
        row = [row[0], row[1].tolist(), int(row[2]), int(row[3]), float(row[4])]
        identity = dict(
            rng_id="numpy_mt19937_legacy_state_with_gaussian_cache@1",
            numpy_version=np.__version__,
            state=row,
        )
        return dict(
            state_json=json.dumps(row, separators=(",", ":"), allow_nan=False),
            numpy_version=np.__version__,
            identity=hashlib.sha256(
                json.dumps(
                    identity, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest(),
        )

    class NumpyNamespace:
        random = rng

        def __getattr__(self, name):
            return getattr(np, name)

    namespace = {}

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "betse.science.tissue.picker.tispickimage":
            return SimpleNamespace(TissuePickerImage=namespace["TissuePickerImage"])
        if name == "betse.util.path":
            return SimpleNamespace(
                dirs=SimpleNamespace(is_dir=namespace["is_dir"]),
                paths=SimpleNamespace(is_path=namespace["is_path"]),
            )
        if name == "betse.lib.numpy":
            return SimpleNamespace(
                nparray=SimpleNamespace(from_iterable=namespace["from_iterable"]),
                npscalar=SimpleNamespace(to_python=namespace["to_python"]),
            )
        if name == "betse.util.math.geometry":
            return SimpleNamespace(geopoint=SimpleNamespace(is_point=namespace["is_point"]))
        if name.split(".")[0] in {"cells", "betse", "jax", "jaxlib"}:
            raise ImportError("Undeclared native helper import: " + name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    def log(*args, **kwargs):
        events.append(dict(kind="log", args=args, kwargs=kwargs))

    namespace.update(
        __name__="independent_native_single_cell_prefix",
        __builtins__=dict(vars(builtins), __import__=imports),
        ABCMeta=ABCMeta,
        abstractmethod=abstractmethod,
        Enum=Enum,
        np=NumpyNamespace(),
        array=np.array,
        ndarray=np.ndarray,
        math=math,
        copy=copy,
        SequenceTypes=(Sequence, np.ndarray),
        NumpyArrayType=np.ndarray,
        os_path=os.path,
        Image=Image,
        RectBivariateSpline=RectBivariateSpline,
        ConvexHull=ConvexHull,
        Delaunay=Delaunay,
        cKDTree=cKDTree,
        CellLatticeType=Enum("CellLatticeType", ("HEX", "SQUARE")),
        logs=SimpleNamespace(log_info=log, log_warning=log, log_debug=log),
    )
    for file, nodes in groups:
        module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
        exec(
            compile(
                module,
                str(Path(native_root) / file),
                "exec",
                flags=__future__.annotations.compiler_flag,
                dont_inherit=True,
            ),
            namespace,
        )
    namespace.update(
        sequences=SimpleNamespace(is_sequence=namespace["is_sequence"]),
        pathnames=SimpleNamespace(
            **{n: namespace[n] for n in FUNCTIONS["betse/util/path/pathnames.py"]}
        ),
        files=SimpleNamespace(die_unless_file=namespace["die_unless_file"]),
        nparray=SimpleNamespace(
            to_signed=namespace["to_signed"], from_iterable=namespace["from_iterable"]
        ),
        pilnumpy=SimpleNamespace(load_image=namespace["load_image"]),
        tb=SimpleNamespace(flatten=namespace["flatten"]),
    )
    recipe, controls, image = (declared[k] for k in ("seed_recipe", "controls", "image_recipe"))
    parameter = SimpleNamespace(
        _conf=copy.deepcopy(configuration),
        world_len=recipe["world_len_m"],
        cell_radius=recipe["cell_radius_m"],
        cell_lattice_disorder=recipe["lattice_disorder"],
        cell_lattice_type=getattr(namespace["CellLatticeType"], recipe["lattice_type"]),
    )
    state["parameter"] = parameter
    parameter_names = None

    def public():
        caller = state["caller"]
        return dict(
            caller={k: v for k, v in vars(caller).items() if k != "mesh"},
            mesh=dict(vars(caller.mesh)),
            parameters={
                k: (
                    getattr(parameter, k).name
                    if k == "cell_lattice_type"
                    else getattr(parameter, k)
                )
                for k in parameter_names
            },
        )

    class CaptureFailure(Exception):
        pass

    def save_stage(name):
        try:
            stages.append((name, wire.capture(public())))
        except Exception as error:
            state["capture_error"] = record_exception(error)
            raise CaptureFailure("Native stage capture failed") from error

    for name in METHODS:
        original = getattr(namespace["Cells"], name)

        def observed(self, *args, _name=name, _original=original, **kwargs):
            state["stage"] = _name
            if _name == METHODS[0]:
                state["before_geometry"] = stream()
                save_stage("before")
            value = _original(self, *args, **kwargs)
            save_stage(_name)
            return value

        setattr(namespace["Cells"], name, observed)

    def callback(*args, **kwargs):
        events.append(dict(kind="normalized_phase_callback", args=args, kwargs=kwargs))

    phase = SimpleNamespace(
        p=parameter,
        callbacks=SimpleNamespace(progress_stated=callback, progressed_next=callback),
        die_unless_kind_seed=lambda: events.append(dict(kind="normalized_seed_phase_assertion")),
    )
    error, aliases = None, None
    previous = sys.getprofile()
    native_prefix = str(Path(native_root)) + os.sep

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event == "call" and frame.f_code.co_filename.startswith(native_prefix):
            if frame.f_code is namespace["DECMesh"].__init__.__code__:
                # The native assignment occurs only after constructor return.
                # Retain a failed constructor's original object separately.
                state["constructing_mesh"] = frame.f_locals["self"]
            events.append(
                dict(
                    kind="source_entry",
                    function=frame.f_code.co_qualname,
                    line=frame.f_code.co_firstlineno,
                    file=str(Path(frame.f_code.co_filename).relative_to(native_root)),
                )
            )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sys.setprofile(profile)
            state["stage"] = "parameter_stores"
            namespace["store_parameters"](parameter)
            parameter_names = tuple(vars(parameter))
            # Explicit normalized caller controls; no full native Parameters claim.
            parameter.tissue_default = SimpleNamespace(picker_image_filename=image["filename"])
            parameter.conf_dirname = image["conf_dirname"]
            for k, v in controls.items():
                if k != "kind":
                    setattr(parameter, k, v)
            state["stage"] = "constructor"
            state["caller"] = namespace["Cells"](parameter)
            state["stage"] = "make_world_prefix"
            state["caller"].make_world(phase)
            caller = state["caller"]
            aliases = dict(
                ecm_verts_is_vcell_verts=caller.ecm_verts is caller.mesh.vcell_verts,
                ecm_verts_unique_is_vor_verts=caller.ecm_verts_unique is caller.mesh.vor_verts,
                cell_centres_is_vor_cents=caller.cell_centres is caller.mesh.vor_cents,
            )
        except Exception as exc:
            if not isinstance(exc, CaptureFailure):
                error = record_exception(exc)
            try:
                if state["caller"] is not None and hasattr(state["caller"], "mesh"):
                    captures.append(wire.capture(public()))
                else:
                    partial_parameter = {
                        k: (v.name if k == "cell_lattice_type" else v)
                        for k, v in vars(parameter).items()
                        if k != "tissue_default"
                    }
                    if hasattr(parameter, "tissue_default"):
                        partial_parameter["tissue_default"] = vars(parameter.tissue_default)
                    captures.append(
                        wire.capture(
                            dict(
                                parameters=partial_parameter,
                                caller=vars(state["caller"])
                                if state["caller"] is not None
                                else None,
                                constructing_mesh=vars(state["constructing_mesh"])
                                if state["constructing_mesh"] is not None
                                else None,
                            )
                        )
                    )
            except Exception as capture_error:
                state["capture_error"] = record_exception(capture_error)
        finally:
            sys.setprofile(previous)

    def unchanged_global():
        global_after = np.random.get_state()
        return (
            original_global[0] == global_after[0]
            and np.array_equal(original_global[1], global_after[1])
            and original_global[2:] == global_after[2:]
        )

    completed = (
        error is None
        and state["capture_error"] is None
        and [s[0] for s in stages] == ["before", *METHODS]
    )
    record = dict(
        source_body_completed=completed,
        source_error=error,
        capture_error=state["capture_error"],
        failed_stage=None if completed else state["stage"],
        stages=stages,
        cache=stages[-1][1] if completed else None,
        partial_captures=captures,
        stream_before=state["before_geometry"],
        source_sites=sites,
        original_source_pins=NATIVE_PINS,
        events=events,
        aliases=aliases,
        actual_source_executions=1,
        normalized_parameters_phase_callbacks_only=True,
        full_package_or_physical_admission=False,
    )
    return finalize(
        record,
        dict(
            image_unchanged=lambda: digest(image_path) == image["image_sha256"],
            global_random_stream_unchanged=unchanged_global,
            stream_after=stream,
            warnings=lambda: [str(w.message) for w in caught],
        ),
        record_exception,
    )
