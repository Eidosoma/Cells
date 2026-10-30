"""Prepared authenticated image/prelude capture; no mesh constructor executes."""

import __future__

import ast
import builtins
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import traceback
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
from scipy.interpolate import RectBivariateSpline
from scipy.spatial import ConvexHull

PROTOCOL = Path(__file__).with_name("betse_image_mask_prelude_protocol.json")
FUNCTIONS = {
    "betse/util/type/types.py": ("type_check",),
    "betse/util/path/pathnames.py": (
        "is_absolute",
        "is_relative",
        "die_if_absolute",
        "join",
        "get_basename",
    ),
    "betse/util/path/files.py": ("is_file", "die_unless_file"),
    "betse/lib/numpy/nparray.py": ("to_signed",),
    "betse/lib/pil/pilnumpy.py": ("load_image",),
    "betse/util/math/mathinterp.py": ("interp2d_linear",),
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _site(source, node):
    return dict(
        source=source,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def capture():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    root = Path(pins["checkout"])
    installed = Path(pins["installed_package"]).parent
    frozen = Path(os.environ.get("CELLS_BETSE_SOURCE", str(root)))
    trees = {}
    for name, expected in pins["source_sha256"].items():
        for base in (root, installed, frozen):
            if _sha(base / name) != expected:
                raise ValueError("Pinned image prelude source changed: " + str(base / name))
        trees[name] = ast.parse((frozen / name).read_text())
    assert (
        subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        == pins["revision"]
    )
    nodes, sites = [], {}
    for source, names in FUNCTIONS.items():
        for name in names:
            node = next(
                n for n in trees[source].body if isinstance(n, ast.FunctionDef) and n.name == name
            )
            nodes.append(copy.deepcopy(node))
            sites[name] = _site(source, node)
    source = "betse/lib/numpy/nparray.py"
    assignment = next(
        n
        for n in trees[source].body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "DTYPE_UNSIGNED_TO_SIGNED" for t in n.targets)
    )
    nodes.append(copy.deepcopy(assignment))
    sites["DTYPE_UNSIGNED_TO_SIGNED"] = _site(source, assignment)
    source = "betse/lib/pil/pilnumpy.py"
    enum = next(
        n for n in trees[source].body if isinstance(n, ast.ClassDef) and n.name == "ImageModeType"
    )
    nodes.append(copy.deepcopy(enum))
    sites["ImageModeType"] = _site(source, enum)
    source = "betse/science/tissue/picker/tispickimage.py"
    for name in ("TissuePickerImageMask", "TissuePickerImage"):
        original = next(
            n for n in trees[source].body if isinstance(n, ast.ClassDef) and n.name == name
        )
        node = copy.deepcopy(original)
        if name == "TissuePickerImage":
            # The constructor never calls its nominal abstract base. Its exact
            # original body/methods remain; no class inheritance parity claim.
            node.bases = [ast.Name(id="object", ctx=ast.Load())]
        assert ast.dump(
            ast.Module(body=node.body, type_ignores=[]), include_attributes=False
        ) == ast.dump(ast.Module(body=original.body, type_ignores=[]), include_attributes=False)
        nodes.append(node)
        sites[name] = _site(source, original)
    source = "betse/science/cells.py"
    cls = next(n for n in trees[source].body if isinstance(n, ast.ClassDef) and n.name == "Cells")
    method = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "make_voronoi"
    )
    nodes.append(copy.deepcopy(method))
    sites["make_voronoi"] = _site(source, method)
    expected = json.loads(
        PROTOCOL.with_name("betse_image_mask_prelude_source_map.json").read_text()
    )
    assert sites == expected["captured_sites"]
    return ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), sites, pins


def _state():
    saved = np.random.get_state()
    return [saved[0], saved[1].tolist(), int(saved[2]), int(saved[3]), float(saved[4])]


def _layout(value):
    return dict(
        shape=list(value.shape),
        dtype=value.dtype.str,
        strides_bytes=list(value.strides),
        C_contiguous=bool(value.flags.c_contiguous),
        F_contiguous=bool(value.flags.f_contiguous),
    )


def _validated_inputs(image_recipe, geometry, controls, points_x, points_y):
    """Explicit normalized boundary; package import-hook validation is excluded."""
    if (
        type(image_recipe) is not dict
        or set(image_recipe) != {"kind", "filename", "conf_dirname", "image_sha256"}
        or image_recipe["kind"] != "cells.betse_image_mask_source@1"
        or any(
            type(image_recipe[k]) is not str for k in ("filename", "conf_dirname", "image_sha256")
        )
        or not image_recipe["filename"]
        or len(image_recipe["image_sha256"]) != 64
    ):
        raise ValueError("Require normalized image path controls and digest")
    if set(geometry) != {
        "bounds_m",
        "all_seed_points_m",
        "centre_m",
        "cell_radius_m",
        "lattice_type",
    } or geometry["lattice_type"] not in ("SQUARE", "HEX"):
        raise ValueError("Require the seed-stage geometry diagnostic snapshot")
    bounds = np.asarray(geometry["bounds_m"], dtype=np.float64)
    points = np.asarray(geometry["all_seed_points_m"], dtype=np.float64)
    centre = np.asarray(geometry["centre_m"], dtype=np.float64)
    if (
        bounds.shape != (4,)
        or not np.isfinite(bounds).all()
        or not (bounds[0] < bounds[1] and bounds[2] < bounds[3])
        or points.ndim != 2
        or points.shape[1:] != (2,)
        or not 1 <= len(points) <= 132
        or not np.isfinite(points).all()
        or centre.shape != (2,)
        or not np.isfinite(centre).all()
        or type(geometry["cell_radius_m"]) not in (int, float)
        or not np.isfinite(geometry["cell_radius_m"])
        or geometry["cell_radius_m"] <= 0
    ):
        raise ValueError("Require bounded finite seed-stage coordinate arrays")
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
        or controls["kind"] != "cells.betse_make_voronoi_controls@1"
    ):
        raise ValueError("Require normalized native make_voronoi branch controls")
    if (
        any(
            type(controls[k]) is not bool
            for k in (
                "single_cell",
                "svg_override",
                "use_centroids",
                "refine_mesh",
            )
        )
        or controls["svg_override"]
    ):
        raise ValueError("Require the declared non-SVG branch booleans")
    for key in ("alpha_shape", "voronoi_convergence"):
        if (
            type(controls[key]) not in (int, float)
            or not np.isfinite(controls[key])
            or controls[key] <= 0
        ):
            raise ValueError("Require a finite positive native branch scalar")
    if (
        type(controls["maximum_voronoi_steps"]) is not int
        or not 0 <= controls["maximum_voronoi_steps"] <= 100
    ):
        raise ValueError("Require a bounded native refinement-step declaration")
    for values in (points_x, points_y):
        array = np.asarray(values, dtype=np.float64)
        if array.ndim != 1 or len(array) > 128 or not np.isfinite(array).all():
            raise ValueError("Require bounded finite paired query sequences")


def evaluate(image_recipe, geometry, controls, *, points_x=(), points_y=()):
    """Execute original image bodies and stop at the first mesh method boundary.

    Geometry is a supplied diagnostic snapshot of the seed stage; this helper
    does not claim to generate topology or independently qualify the lattice.
    """
    _validated_inputs(image_recipe, geometry, controls, points_x, points_y)
    module, sites, pins = capture()
    filename = image_recipe["filename"]
    if not os.path.isabs(filename):
        filename = os.path.join(image_recipe["conf_dirname"], filename)
    if not Path(filename).is_file():
        raise ValueError("Diagnostic image must be an existing regular file")
    file_before = Path(filename).read_bytes()
    if (
        len(file_before) > 2**20
        or hashlib.sha256(file_before).hexdigest() != image_recipe["image_sha256"]
    ):
        raise ValueError("Diagnostic image differs from its owned content digest")
    with Image.open(io.BytesIO(file_before)) as header:
        if max(header.size) > 32:
            raise ValueError("Diagnostic image exceeds the bounded pixel admission")
    enums = SimpleNamespace(SQUARE=object(), HEX=object())
    calls, locals_by_function, layouts, snapshots = [], {}, {}, {}
    namespace = {}

    class MeshMethodBoundary(Exception):
        pass

    class MeshArguments:
        def __init__(self, **kwargs):
            calls.append(dict(name="DECMesh", kwargs=kwargs))

        def init_mesh(self):
            calls.append(dict(name="init_mesh", kwargs={}, original_mask_argument=False))
            raise MeshMethodBoundary()

        def clip_and_refine(self, mask, **kwargs):
            calls.append(dict(name="clip_and_refine", kwargs=kwargs, original_mask_argument=True))
            snapshots["passed_mask"] = mask
            raise MeshMethodBoundary()

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "betse.science.tissue.picker.tispickimage":
            return SimpleNamespace(TissuePickerImage=namespace["TissuePickerImage"])
        if name == "betse.util.path":
            return SimpleNamespace(
                dirs=SimpleNamespace(is_dir=os.path.isdir),
                paths=SimpleNamespace(is_path=os.path.lexists),
            )
        if name.split(".")[0] in {"betse", "cells", "jax", "jaxlib"}:
            raise ImportError("Package import denied by isolated native image capture: " + name)
        return builtins.__import__(name, globals, locals, fromlist, level)

    namespace.update(
        __name__="cells_native_image_prelude_capture",
        __builtins__=dict(vars(builtins), __import__=imports),
        np=np,
        Enum=Enum,
        Image=Image,
        array=np.array,
        os_path=os.path,
        RectBivariateSpline=RectBivariateSpline,
        ConvexHull=ConvexHull,
        BetseImageException=ValueError,
        BetseFileException=ValueError,
        BetsePathnameException=ValueError,
        BetseMathInterpolationException=ValueError,
        CellLatticeType=enums,
        DECMesh=MeshArguments,
        logs=SimpleNamespace(log_info=lambda *args: None, log_debug=lambda *args: None),
    )
    exec(
        compile(
            module,
            "<pinned native image prelude>",
            "exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        ),
        namespace,
    )
    namespace["pathnames"] = SimpleNamespace(
        **{name: namespace[name] for name in FUNCTIONS["betse/util/path/pathnames.py"]}
    )
    namespace["files"] = SimpleNamespace(die_unless_file=namespace["die_unless_file"])
    namespace["nparray"] = SimpleNamespace(to_signed=namespace["to_signed"])
    namespace["pilnumpy"] = SimpleNamespace(load_image=namespace["load_image"])
    p = SimpleNamespace(
        tissue_default=SimpleNamespace(picker_image_filename=image_recipe["filename"]),
        conf_dirname=image_recipe["conf_dirname"],
        single_cell=controls["single_cell"],
        svg_override=controls["svg_override"],
        cell_radius=geometry["cell_radius_m"],
        cell_lattice_type=getattr(enums, geometry["lattice_type"]),
        alpha_shape=controls["alpha_shape"],
        use_centroids=controls["use_centroids"],
        refine_mesh=controls["refine_mesh"],
        maximum_voronoi_steps=controls["maximum_voronoi_steps"],
        voronoi_convergence=controls["voronoi_convergence"],
    )
    xmin, xmax, ymin, ymax = geometry["bounds_m"]
    cells = SimpleNamespace(
        xmin=xmin,
        xmax=xmax,
        ymin=ymin,
        ymax=ymax,
        clust_xy=np.asarray(geometry["all_seed_points_m"]),
        centre=np.asarray(geometry["centre_m"]),
    )
    codes = {
        namespace["make_voronoi"].__code__: "make_voronoi",
        namespace["TissuePickerImageMask"].__init__.__code__: "mask_init",
        namespace["load_image"].__code__: "load_image",
    }

    def trace(frame, event, arg):
        if frame.f_code in codes:
            if event in ("return", "exception"):
                name = codes[frame.f_code]
                locals_by_function[name] = {
                    key: np.array(value, copy=True, order="K")
                    for key, value in frame.f_locals.items()
                    if isinstance(value, np.ndarray)
                }
                layouts[name] = {
                    key: _layout(value)
                    for key, value in frame.f_locals.items()
                    if isinstance(value, np.ndarray)
                }
                if name == "make_voronoi" and "image_mask" in frame.f_locals:
                    snapshots["mask"] = frame.f_locals["image_mask"]
                    snapshots["native_filename"] = frame.f_locals["image_picker"].filename
            return trace
        return None

    failure, reached = None, False
    before = _state()
    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        namespace["make_voronoi"](cells, SimpleNamespace(p=p))
    except MeshMethodBoundary:
        reached = True
    except Exception as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
    finally:
        sys.settrace(previous)
    values, selected, linear_values = None, None, None
    if reached:
        mask = snapshots["mask"]
        if "passed_mask" in snapshots:
            assert snapshots["passed_mask"] is mask
        raw = locals_by_function["mask_init"]
        closure = mask.clipping_function.__closure__
        assert len(closure) == 1 and isinstance(closure[0].cell_contents, RectBivariateSpline)
        linear = closure[0].cell_contents
        fast = mask.clipping_function_fast
        values = dict(
            bitmap=raw["bitmap"],
            clipping_matrix=mask.clipping_matrix,
            xpts_m=raw["xpts"],
            ypts_m=raw["ypts"],
            active_grid_indices=np.column_stack(np.nonzero(mask.clipping_matrix == 1.0)),
            active_points_m=raw["ppts"],
            hull_indices=raw["bverts"],
            clipcurve_m=mask.clipcurve,
            linear_knots_x_m=linear.get_knots()[0],
            linear_knots_y_m=linear.get_knots()[1],
            linear_coefficients=linear.get_coeffs(),
            fast_knots_x_m=fast.get_knots()[0],
            fast_knots_y_m=fast.get_knots()[1],
            fast_coefficients=fast.get_coeffs(),
        )
        selected = mask.get_clipped_points_index(points_x, points_y)
        linear_values = np.asarray(
            [mask.clipping_function(x, y).item() for x, y in zip(points_x, points_y, strict=False)],
            dtype=np.float64,
        )
    after = _state()
    assert Path(filename).read_bytes() == file_before
    return dict(
        status="mesh_method_argument_boundary" if reached else "source_failed",
        values=values,
        selected_indices=selected,
        paired_linear_values=linear_values,
        calls=calls,
        failure=failure,
        raw_locals=locals_by_function,
        source_layouts=layouts,
        native_filename=snapshots.get("native_filename"),
        image_sha256=hashlib.sha256(file_before).hexdigest(),
        rng_before=before,
        rng_after=after,
        original_global_rng_unchanged=before == after,
        native_source_sha256=pins["source_sha256"],
        source_sites=sites,
        mesh_constructor_executed=False,
        topology_generated=False,
        native_package_import_hook_executed=False,
    )
