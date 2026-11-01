"""Independent original-BETSE AST execution through a closed source prefix.

No Cells model, source kernel, fixture or cache implementation is imported.
The native source is compiled afresh. A normalized parameter/phase boundary
supplies scalar configuration and records callbacks; it is not the full native
Parameters/YAML/SimPhase/package lifecycle. Numerical library implementations
and the independent wire encoder are shared and must be recorded by the runner.
The opt-in ECM endpoint also shares the pinned original metadata descriptor
factory and its genuine package initialization; no native science is imported.
"""

import __future__

import ast
import builtins
import copy
import hashlib
import importlib
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
ENVIRONMENT_STAGES = ("environment", "assign_grid_len", "make_maskM")
POISSON_STAGES = ("environment_voltage", "environment_current")
POISSON_ASSIGNMENTS = ("lapENVinv", "lapENV_P_inv")
# Independent observation schema only; no Cells runtime/tree adapter is used.
TREE_FIELDS = ("data", "indices", "mins", "maxes", "n", "m", "leafsize", "boxsize")
ECM_PINS = {
    "betse/__init__.py": "a3dce54aab848c36dfc4738f5dba889505adefad819d63d4c61a4310655cf200",
    "betse/metadata.py": "6a09cc83d58ec6c1ea4b5a4c11fa0eb46d3b84518309a0495ddc7d61610ce8a1",
    "betse/lib/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "betse/lib/yaml/__init__.py": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "betse/lib/yaml/yamlalias.py": (
        "cc87d9403c088a936a00187e33417b05ae2d26f64ee02b37d7857504cf3f0e37"
    ),
    "betse/util/__init__.py": "27ba859ab475847ac208aa581afc5c24053ae1b487e1cd3a73ab750a0c245d11",
    "betse/util/type/__init__.py": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "betse/util/type/descriptor/__init__.py": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "betse/util/type/descriptor/expralias.py": (
        "96f5095f544894dd880a63cbdcb6333dbd178e0d64ed173b6afec384878a1986"
    ),
    "betse/util/type/cls/__init__.py": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ),
    "betse/util/type/cls/classes.py": (
        "518cf58a45b621fae925595c3e3ed48dcba8c1f71df6718b10ffbe253710aab4"
    ),
    "betse/science/math/finitediff.py": (
        "8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350"
    ),
}
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


def methods_for(stop_after="near_neigh"):
    if type(stop_after) is not str or stop_after not in (
        "near_neigh",
        "makeECM",
        "make_maskM",
        "lapENV_P_inv",
    ):
        raise ValueError("Unknown independent native endpoint")
    if stop_after == "near_neigh":
        return METHODS
    if stop_after == "makeECM":
        return (*METHODS, "makeECM")
    return (*METHODS, "makeECM", "environment", "make_maskM")


def pins_for(stop_after="near_neigh"):
    methods_for(stop_after)
    return dict(NATIVE_PINS) if stop_after == "near_neigh" else NATIVE_PINS | ECM_PINS


def metadata_imports_for(stop_after="near_neigh"):
    """Exact shared metadata imports; never a prefix-wide BETSE allowance."""
    methods_for(stop_after)
    if stop_after == "near_neigh":
        return ()
    paths = (ECM_PINS.keys() - {"betse/science/math/finitediff.py"}) | {
        "betse/exceptions.py",
        "betse/util/type/types.py",
    }
    return tuple(
        sorted(p.removesuffix("/__init__.py").removesuffix(".py").replace("/", ".") for p in paths)
    )


def metadata_records(native_root):
    """Check actual shared metadata producers without importing anything."""
    root = Path(native_root).resolve()
    allowed = set(metadata_imports_for("makeECM"))
    pins = pins_for("makeECM")
    records = {}
    for name, module in tuple(sys.modules.items()):
        if name != "betse" and not name.startswith("betse."):
            continue
        if name not in allowed:
            raise ImportError("Undeclared native metadata module: " + name)
        relative = name.replace(".", "/") + ".py"
        if relative not in pins:
            relative = name.replace(".", "/") + "/__init__.py"
        expected = root / relative
        path = Path(getattr(module, "__file__", ""))
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if (
            path != expected
            or origin != str(expected)
            or path.is_symlink()
            or digest(path) != pins[relative]
        ):
            raise ValueError("Changed native metadata import producer: " + name)
        records[name] = dict(path=str(path), sha256=pins[relative])
    return records


def grid_parameter_type(factory, native_root):
    """Use the genuine lazy factory/hook before any parameter instance exists."""
    metadata_records(native_root)
    old_path = list(sys.path)
    sys.path.insert(0, str(Path(native_root).resolve()))
    try:
        yaml = importlib.import_module("betse.lib.yaml.yamlalias")
        importlib.import_module("betse.util.type.descriptor.expralias")
        importlib.import_module("betse.util.type.cls.classes")
        before = metadata_records(native_root)
        runtime = factory(yaml.yaml_alias)
        after = metadata_records(native_root)
        if before != after:
            raise ValueError("Native descriptor producers changed during construction")
        return runtime, after
    finally:
        sys.path[:] = old_path


def source_nodes(root, *, stop_after="near_neigh"):
    """Read/verify/assemble AST only; no numerical imports or execution."""
    root = Path(root)
    trees = {}
    methods = methods_for(stop_after)
    for name, expected in pins_for(stop_after).items():
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
    if stop_after != "near_neigh":
        file = "betse/science/math/finitediff.py"
        grid = copy.deepcopy(cls(file, "FiniteDiffSolver"))
        grid.body = [
            n
            for n in grid.body
            if isinstance(n, ast.FunctionDef)
            and n.name
            in (
                ("__init__", "cell_grid", "makeLaplacian")
                if stop_after == "lapENV_P_inv"
                else ("__init__", "cell_grid")
            )
        ]
        add(file, (grid,))
        if stop_after == "lapENV_P_inv":
            method = next(n for n in grid.body if n.name == "makeLaplacian")
            sites[file + ":FiniteDiffSolver.makeLaplacian"] = dict(
                first_line=method.lineno,
                last_line=method.end_lineno,
                ast_sha256=hashlib.sha256(
                    ast.dump(method, include_attributes=False).encode()
                ).hexdigest(),
            )
    original = cls("betse/science/cells.py", "Cells")
    selected = (
        "__init__",
        "make_world",
        "_make_cell_lattice",
        "make_voronoi",
        "cell_index",
        *methods,
    )
    cells = copy.deepcopy(original)
    cells.body = [n for n in cells.body if isinstance(n, ast.FunctionDef) and n.name in selected]
    make_world = next(n for n in cells.body if n.name == "make_world")
    if stop_after == "lapENV_P_inv":
        stop = next(
            i
            for i, n in enumerate(make_world.body)
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Attribute) and t.attr == stop_after
                for target in n.targets
                for t in ast.walk(target)
            )
        )
    else:
        stop = next(
            i
            for i, n in enumerate(make_world.body)
            if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Attribute)
            and n.value.func.attr == stop_after
        )
    make_world.body = make_world.body[: stop + 1]
    add("betse/science/cells.py", (cells,))
    if stop_after in ("make_maskM", "lapENV_P_inv"):
        assignment = next(
            n
            for n in make_world.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "grid_len" for t in n.targets)
        )
        sites["betse/science/cells.py:make_world.grid_len"] = dict(
            first_line=assignment.lineno,
            last_line=assignment.end_lineno,
            ast_sha256=hashlib.sha256(
                ast.dump(assignment, include_attributes=False).encode()
            ).hexdigest(),
        )
    if stop_after == "lapENV_P_inv":
        for line in (503, 504, 511, 512):
            statement = next(n for n in make_world.body if n.lineno == line)
            sites["betse/science/cells.py:make_world.assignment_" + str(line)] = dict(
                first_line=statement.lineno,
                last_line=statement.end_lineno,
                ast_sha256=hashlib.sha256(
                    ast.dump(statement, include_attributes=False).encode()
                ).hexdigest(),
            )
    parameters = cls("betse/science/parameters.py", "Parameters")
    stores = {n.lineno: n for n in ast.walk(parameters) if isinstance(n, ast.Assign)}
    wrapper = ast.parse("def store_parameters(self):\n    pass\n").body[0]
    store_lines = (
        (521, *STORE_LINES) if stop_after in ("make_maskM", "lapENV_P_inv") else STORE_LINES
    )
    wrapper.body = [copy.deepcopy(stores[line]) for line in store_lines]
    ast.fix_missing_locations(wrapper)
    add("betse/science/parameters.py", (wrapper,))
    if stop_after != "near_neigh":
        descriptor = next(
            n
            for n in parameters.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "grid_size" for t in n.targets)
        )
        expected = ast.parse(
            "grid_size = yaml_alias(\"['general options']['comp grid size']\", int)"
        ).body[0]
        if ast.dump(descriptor) != ast.dump(expected):
            raise ValueError("Original grid_size descriptor declaration changed")
        factory = ast.parse(
            "def parameter_type(yaml_alias):\n"
            "    pass\n"
            "    return type('NativeGridParameters', (SimpleNamespace,), "
            "{'grid_size': grid_size})\n"
        ).body[0]
        factory.body[0] = copy.deepcopy(descriptor)
        add("betse/science/parameters.py", (factory,))
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


def inputs(raw, configuration, *, stop_after="near_neigh"):
    methods_for(stop_after)
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
        or set(configuration)
        != (
            {"world options"}
            if stop_after == "near_neigh"
            else {"world options", "general options"}
        )
        or type(configuration["world options"]) is not dict
        or set(configuration["world options"]) != {"cell height", "cell spacing"}
    ):
        raise ValueError("Require explicit geometry configuration")
    if stop_after != "near_neigh" and (
        type(configuration["general options"]) is not dict
        or set(configuration["general options"]) != {"comp grid size"}
        or type(configuration["general options"]["comp grid size"]) is not int
        or configuration["general options"]["comp grid size"] != 25
    ):
        raise ValueError("Require declared original integer computational grid size 25")
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


def snapshot_state(caller, parameter, parameter_names, *, ecm=False, grid=None):
    """Original public owner axes; ECM keeps its grid separate from the caller."""
    excluded = {"mesh", "grid_obj"} if ecm else {"mesh"}
    result = dict(
        caller={k: v for k, v in vars(caller).items() if k not in excluded},
        mesh=dict(vars(caller.mesh)),
        parameters={
            k: getattr(parameter, k).name if k == "cell_lattice_type" else getattr(parameter, k)
            for k in parameter_names
        },
    )
    if ecm:
        result["grid"] = None if grid is None else dict(vars(grid))
    return result


def tree_state(tree):
    values = {}
    for name in TREE_FIELDS:
        try:
            values[name] = getattr(tree, name)
        except AttributeError:
            values[name] = ("unavailable", name)
    return values


def environment_snapshot(caller, parameter, parameter_names, grid, trees):
    """Five ordered observation owners; native tree objects are never hydrated."""
    base = snapshot_state(caller, parameter, parameter_names, ecm=True, grid=grid)
    base["caller"].pop("points_tree", None)
    return dict(
        caller=base["caller"],
        grid=base["grid"],
        mesh=base["mesh"],
        parameters=base["parameters"],
        trees=[tree_state(tree) for tree in trees],
    )


def observe_tree(constructor, args, kwargs, trees, events, capture, record_exception):
    """Observe the original type call; keep its returned object unchanged.

    A failed C constructor does not return its allocation. Preserve its inputs,
    original exception and previously returned trees without claiming that self.
    """
    row = dict(
        kind="environment_tree_constructor",
        prior_successful_trees=len(trees),
        request=capture(dict(args=args, kwargs=kwargs)),
        outcome="entered",
    )
    events.append(row)
    try:
        tree = constructor(*args, **kwargs)
    except Exception as error:
        row.update(outcome="raised", unreturned_c_allocation_available=False)
        try:
            row["error"] = record_exception(error)
        except Exception as capture_error:
            row["error_capture_failure"] = dict(
                type=type(capture_error).__name__, message=str(capture_error)
            )
        raise
    trees.append(tree)
    row.update(outcome="returned", tree_index=len(trees) - 1)
    return tree


def observe_poisson_helper(
    original, name, stage, args, kwargs, helpers, events, capture, record_exception
):
    """Observe one unchanged helper call, retaining its immediate return bytes."""
    row = dict(
        kind="poisson_helper",
        stage=stage,
        name=name,
        request=capture(dict(args=args, kwargs=kwargs)),
    )
    events.append(row)
    try:
        value = original(*args, **kwargs)
    except Exception as error:
        row["outcome"] = "raised"
        try:
            row["source_error"] = record_exception(error)
        except Exception as secondary:
            row["error_capture_failure"] = dict(
                type=type(secondary).__name__, message=str(secondary)
            )
        raise
    # Keep the original object; zeros is subsequently mutated by the literal
    # method. Its immediate wire capture is distinct from later boundaries.
    helpers.append((stage, name, value))
    row["outcome"] = "returned"
    row["output"] = capture(value)
    return value


def poisson_assignment(caller, stage, returned):
    """Verify the actual native assignment, without copying or replacing it."""
    index = POISSON_STAGES.index(stage)
    if type(returned) is not tuple or len(returned) != 2:
        raise ValueError("Original makeLaplacian return pair is missing")
    if getattr(caller, POISSON_ASSIGNMENTS[index], None) is not returned[1]:
        raise ValueError("Original Poisson inverse assignment identity changed")


def evaluate(raw, configuration, native_root, *, record_exception, stop_after="near_neigh"):
    """One actual source execution; caller must own resource/release gates."""
    declared, image_path = inputs(raw, configuration, stop_after=stop_after)
    groups, sites = source_nodes(native_root, stop_after=stop_after)
    methods = methods_for(stop_after)
    import numpy as np
    from PIL import Image
    from scipy.interpolate import RectBivariateSpline
    from scipy.spatial import ConvexHull, Delaunay, cKDTree

    if stop_after in ("make_maskM", "lapENV_P_inv"):
        from scipy.interpolate import griddata
        from scipy.ndimage import gaussian_filter

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
        constructing_grid=None,
        before_geometry=None,
        after_geometry=None,
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
        SimpleNamespace=SimpleNamespace,
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
    if stop_after != "near_neigh":
        namespace["fd"] = SimpleNamespace(FiniteDiffSolver=namespace["FiniteDiffSolver"])
    if stop_after in ("make_maskM", "lapENV_P_inv"):
        namespace.update(interp=SimpleNamespace(griddata=griddata), gaussian_filter=gaussian_filter)
    recipe, controls, image = (declared[k] for k in ("seed_recipe", "controls", "image_recipe"))
    parameter_values = dict(
        _conf=copy.deepcopy(configuration),
        world_len=recipe["world_len_m"],
        cell_radius=recipe["cell_radius_m"],
        cell_lattice_disorder=recipe["lattice_disorder"],
        cell_lattice_type=getattr(namespace["CellLatticeType"], recipe["lattice_type"]),
    )
    parameter = None
    parameter_names = None
    metadata = {}
    ecm = dict(before=None, cache=None, stream_before=None, stream_after=None)
    environment = dict(before=None, stages=[], cache=None, stream_before=None, stream_after=None)
    environment_trees = []
    poisson = dict(before=None, stages=[], cache=None, stream_before=None, stream_after=None)
    poisson_results, poisson_helpers = [], []

    def public(*, ecm=False):
        caller = state["caller"]
        grid = getattr(caller, "grid_obj", state["constructing_grid"]) if ecm else None
        return snapshot_state(
            caller,
            parameter,
            parameter_names,
            ecm=ecm,
            grid=grid,
        )

    def public_environment():
        caller = state["caller"]
        return environment_snapshot(
            caller, parameter, parameter_names, caller.grid_obj, environment_trees
        )

    class CaptureFailure(Exception):
        pass

    def save_stage(name):
        try:
            stages.append((name, wire.capture(public())))
        except Exception as error:
            state["capture_error"] = record_exception(error)
            raise CaptureFailure("Native stage capture failed") from error

    def save_ecm(key):
        try:
            ecm[key] = wire.capture(public(ecm=True))
        except Exception as error:
            state["capture_error"] = record_exception(error)
            raise CaptureFailure("Native ECM capture failed") from error

    def capture_environment(value):
        try:
            return wire.capture(value)
        except Exception as error:
            state["capture_error"] = record_exception(error)
            raise CaptureFailure("Native environment capture failed") from error

    def save_environment(name):
        # Include snapshot extraction in capture-error attribution as well.
        try:
            snapshot = capture_environment(public_environment())
        except CaptureFailure:
            raise
        except Exception as error:
            state["capture_error"] = record_exception(error)
            raise CaptureFailure("Native environment snapshot failed") from error
        if name == "before":
            environment["before"] = snapshot
        else:
            environment["stages"].append((name, snapshot))

    def environment_tree(*args, **kwargs):
        if state["stage"] not in ("environment", "make_maskM"):
            raise ValueError("Environment tree observation outside original source stage")
        return observe_tree(
            cKDTree,
            args,
            kwargs,
            environment_trees,
            events,
            capture_environment,
            record_exception,
        )

    def poisson_snapshot():
        try:
            return dict(
                environment=wire.capture(public_environment()),
                outputs=wire.capture(dict(results=poisson_results, helpers=poisson_helpers)),
            )
        except Exception as error:
            state["capture_error"] = record_exception(error)
            raise CaptureFailure("Native Poisson boundary capture failed") from error

    def finish_poisson_assignment():
        if len(poisson_results) == len(poisson["stages"]):
            return
        try:
            if len(poisson_results) != len(poisson["stages"]) + 1:
                raise ValueError("A native Poisson assignment boundary was missed")
            stage, returned = poisson_results[-1]
            poisson_assignment(state["caller"], stage, returned)
            boundary = poisson_snapshot()
        except CaptureFailure:
            raise
        except Exception as error:
            state["capture_error"] = record_exception(error)
            raise CaptureFailure("Native Poisson assignment observation failed") from error
        poisson["stages"].append((stage, boundary))
        poisson["cache"] = boundary
        source_site = "betse/science/cells.py:make_world.assignment_" + (
            "504" if stage == POISSON_STAGES[0] else "512"
        )
        events.append(
            dict(
                kind="inline_assignment_observed",
                observed_at=(
                    "next_original_callback"
                    if stage == POISSON_STAGES[0]
                    else "truncated_make_world_return"
                ),
                source_site=source_site,
                site=sites[source_site],
                original_inverse_identity=True,
            )
        )

    if stop_after == "lapENV_P_inv":
        original_grid_method = namespace["FiniteDiffSolver"].makeLaplacian
        original_zeros, original_pinv = np.zeros, np.linalg.pinv

        def poisson_helper(name, original, args, kwargs):
            return observe_poisson_helper(
                original,
                name,
                state["stage"],
                args,
                kwargs,
                poisson_helpers,
                events,
                capture_environment,
                record_exception,
            )

        def poisson_zeros(*args, **kwargs):
            return poisson_helper("zeros", original_zeros, args, kwargs)

        def poisson_pinv(*args, **kwargs):
            return poisson_helper("pinv", original_pinv, args, kwargs)

        def observed_laplacian(self, *args, **kwargs):
            if len(poisson_results) >= len(POISSON_STAGES):
                raise ValueError("Undeclared native Poisson call")
            if self is not state["caller"].grid_obj:
                raise ValueError("Native Poisson grid owner changed")
            stage = POISSON_STAGES[len(poisson_results)]
            state["stage"] = stage
            if poisson["before"] is None:
                poisson["stream_before"] = stream()
                poisson["before"] = poisson_snapshot()
            # Only the independently compiled grid method sees this narrow
            # observer namespace. Each delegate is the original retained NumPy
            # callable, called once with the original arguments.
            prior_numpy = namespace["np"]
            namespace["np"] = SimpleNamespace(
                zeros=poisson_zeros, linalg=SimpleNamespace(pinv=poisson_pinv)
            )
            try:
                returned = original_grid_method(self, *args, **kwargs)
            finally:
                namespace["np"] = prior_numpy
            poisson_results.append((stage, returned))
            return returned

        namespace["FiniteDiffSolver"].makeLaplacian = observed_laplacian

    def geometry_aliases():
        caller = state["caller"]
        return dict(
            ecm_verts_is_vcell_verts=caller.ecm_verts is caller.mesh.vcell_verts,
            ecm_verts_unique_is_vor_verts=caller.ecm_verts_unique is caller.mesh.vor_verts,
            cell_centres_is_vor_cents=caller.cell_centres is caller.mesh.vor_cents,
        )

    for name in methods:
        original = getattr(namespace["Cells"], name)

        def observed(self, *args, _name=name, _original=original, **kwargs):
            nonlocal aliases
            state["stage"] = _name
            if _name == METHODS[0]:
                state["before_geometry"] = stream()
                save_stage("before")
            if _name == "makeECM":
                ecm["stream_before"] = stream()
                save_ecm("before")
            if _name == "environment":
                environment["stream_before"] = stream()
                save_environment("before")
            if _name == "make_maskM":
                state["stage"] = "assign_grid_len"
                save_environment("assign_grid_len")
                events.append(
                    dict(
                        kind="inline_assignment_observed",
                        observed_at="make_maskM_entry",
                        source_site="betse/science/cells.py:make_world.grid_len",
                        site=sites["betse/science/cells.py:make_world.grid_len"],
                    )
                )
                state["stage"] = _name
            if _name in ("environment", "make_maskM"):
                # Only source-created ENV trees enter this roster. Geometry and
                # ECM keep their existing ordinary constructor binding.
                prior_tree = namespace["cKDTree"]
                namespace["cKDTree"] = environment_tree
                try:
                    value = _original(self, *args, **kwargs)
                finally:
                    namespace["cKDTree"] = prior_tree
            else:
                value = _original(self, *args, **kwargs)
            if _name == "makeECM":
                ecm["stream_after"] = stream()
                save_ecm("cache")
            elif _name in ("environment", "make_maskM"):
                save_environment(_name)
                if _name == "make_maskM":
                    environment["cache"] = environment["stages"][-1][1]
                    environment["stream_after"] = stream()
            else:
                save_stage(_name)
                if _name == "near_neigh":
                    state["after_geometry"] = stream()
                    aliases = geometry_aliases()
            return value

        setattr(namespace["Cells"], name, observed)

    def callback(*args, **kwargs):
        if stop_after == "lapENV_P_inv":
            # Original line 507 follows the voltage assignment. Capturing here
            # does not replace any original caller statement or matrix call.
            finish_poisson_assignment()
        events.append(dict(kind="normalized_phase_callback", args=args, kwargs=kwargs))

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
            if (
                stop_after != "near_neigh"
                and frame.f_code is namespace["FiniteDiffSolver"].__init__.__code__
            ):
                state["constructing_grid"] = frame.f_locals["self"]
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
            if stop_after != "near_neigh":
                state["stage"] = "grid_descriptor"
                runtime, metadata = grid_parameter_type(namespace["parameter_type"], native_root)
            else:
                runtime = SimpleNamespace
            state["stage"] = "parameter_constructor"
            parameter = runtime(**parameter_values)
            state["parameter"] = parameter
            state["stage"] = "parameter_stores"
            namespace["store_parameters"](parameter)
            parameter_names = tuple(vars(parameter))
            # Explicit normalized caller controls; no full native Parameters claim.
            parameter.tissue_default = SimpleNamespace(picker_image_filename=image["filename"])
            parameter.conf_dirname = image["conf_dirname"]
            for k, v in controls.items():
                if k != "kind":
                    setattr(parameter, k, v)
            phase = SimpleNamespace(
                p=parameter,
                callbacks=SimpleNamespace(progress_stated=callback, progressed_next=callback),
                die_unless_kind_seed=lambda: events.append(
                    dict(kind="normalized_seed_phase_assertion")
                ),
            )
            state["stage"] = "constructor"
            state["caller"] = namespace["Cells"](parameter)
            state["stage"] = "make_world_prefix"
            state["caller"].make_world(phase)
            if stop_after == "lapENV_P_inv":
                finish_poisson_assignment()
                poisson["stream_after"] = stream()
            if stop_after != "near_neigh" and metadata_records(native_root) != metadata:
                raise ValueError("Native descriptor producers changed during source work")
        except Exception as exc:
            if not isinstance(exc, CaptureFailure):
                error = record_exception(exc)
            if (
                stop_after != "near_neigh"
                and ecm["stream_before"] is not None
                and ecm["stream_after"] is None
            ):
                try:
                    ecm["stream_after"] = stream()
                except Exception as capture_error:
                    state["capture_error"] = record_exception(capture_error)
            if environment["stream_before"] is not None and environment["stream_after"] is None:
                try:
                    environment["stream_after"] = stream()
                except Exception as capture_error:
                    state["capture_error"] = record_exception(capture_error)
            if poisson["stream_before"] is not None and poisson["stream_after"] is None:
                try:
                    poisson["stream_after"] = stream()
                except Exception as capture_error:
                    state["capture_error"] = record_exception(capture_error)
            try:
                if state["caller"] is not None and hasattr(state["caller"], "mesh"):
                    if poisson["stream_before"] is not None:
                        # ENV.cache is the retained pre-Poisson boundary. Do not
                        # overwrite it with a later partial Poisson owner.
                        poisson["cache"] = poisson_snapshot()
                        partial = poisson["cache"]["environment"]
                    elif (
                        stop_after in ("make_maskM", "lapENV_P_inv")
                        and environment["stream_before"] is not None
                    ):
                        partial = wire.capture(public_environment())
                        environment["cache"] = partial
                    else:
                        partial = wire.capture(public(ecm=stop_after != "near_neigh"))
                    captures.append(partial)
                else:
                    partial_parameter = {
                        k: (v.name if k == "cell_lattice_type" else v)
                        for k, v in (vars(parameter).items() if parameter is not None else ())
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
        and (stop_after == "near_neigh" or all(v is not None for v in ecm.values()))
        and (
            stop_after not in ("make_maskM", "lapENV_P_inv")
            or (
                [s[0] for s in environment["stages"]] == list(ENVIRONMENT_STAGES)
                and all(
                    environment[k] is not None
                    for k in ("before", "cache", "stream_before", "stream_after")
                )
                and len(environment_trees) == 3
            )
        )
        and (
            stop_after != "lapENV_P_inv"
            or (
                [s[0] for s in poisson["stages"]] == list(POISSON_STAGES)
                and [s[0] for s in poisson_results] == list(POISSON_STAGES)
                and [(s, n) for s, n, _ in poisson_helpers]
                == [(stage, name) for stage in POISSON_STAGES for name in ("zeros", "pinv")]
                and all(
                    poisson[k] is not None
                    for k in ("before", "cache", "stream_before", "stream_after")
                )
            )
        )
    )
    record = dict(
        source_body_completed=completed,
        source_error=error,
        capture_error=state["capture_error"],
        failed_stage=None if completed else state["stage"],
        stages=stages,
        cache=stages[-1][1]
        if (
            completed
            if stop_after == "near_neigh"
            else [s[0] for s in stages] == ["before", *METHODS]
        )
        else None,
        partial_captures=captures,
        stream_before=state["before_geometry"],
        source_sites=sites,
        original_source_pins=pins_for(stop_after),
        events=events,
        aliases=aliases,
        actual_source_executions=1,
        normalized_parameters_phase_callbacks_only=True,
        full_package_or_physical_admission=False,
    )
    if stop_after != "near_neigh":
        record.update(stop_after=stop_after, ecm=ecm, shared_native_metadata=metadata)
    if stop_after in ("make_maskM", "lapENV_P_inv"):
        record.update(
            environment=environment,
            environment_observation=dict(
                stages=ENVIRONMENT_STAGES,
                tree_fields=TREE_FIELDS,
                successful_tree_count=len(environment_trees),
                native_type_call_preserved=True,
                failed_unreturned_c_allocation_captured=False,
                shared_helpers=(
                    "scipy.spatial.cKDTree",
                    "scipy.interpolate.griddata",
                    "scipy.ndimage.gaussian_filter",
                    "copy.deepcopy",
                ),
            ),
        )
    if stop_after == "lapENV_P_inv":
        record.update(
            poisson=poisson,
            poisson_observation=dict(
                stages=POISSON_STAGES,
                helpers=("numpy.zeros", "numpy.linalg.pinv"),
                actual_return_objects_retained=True,
                immediate_helper_returns_in_events=True,
                extra_numerical_calls=0,
                normalized_observers_are_native_methods=False,
            ),
        )
    return finalize(
        record,
        dict(
            image_unchanged=lambda: digest(image_path) == image["image_sha256"],
            global_random_stream_unchanged=unchanged_global,
            stream_after=lambda: (
                state["after_geometry"]
                if stop_after != "near_neigh" and state["after_geometry"] is not None
                else stream()
            ),
            warnings=lambda: [str(w.message) for w in caught],
        ),
        record_exception,
    )
