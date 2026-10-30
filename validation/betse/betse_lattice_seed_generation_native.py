"""Unchanged Parameters stores and Cells lattice body with owned MT state."""

import __future__

import ast
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import traceback
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PROTOCOL = Path(__file__).with_name("betse_lattice_seed_generation_protocol.json")


def _state(rng):
    value = rng.get_state()
    return [value[0], value[1].tolist(), int(value[2]), int(value[3]), float(value[4])]


def _validated_inputs(recipe, before):
    """Validate the normalized call boundary, without native import-hook claims."""
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
        or recipe["kind"] != "cells.betse_lattice_seed_recipe@1"
        or recipe["lattice_type"] not in ("SQUARE", "HEX")
        or type(recipe["provenance"]) is not str
        or not recipe["provenance"].strip()
    ):
        raise ValueError("Require the declared normalized native scalar controls")
    for key in ("world_len_m", "cell_radius_m", "lattice_disorder"):
        value = recipe[key]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Require a finite native scalar: " + key)
    if recipe["world_len_m"] <= 0 or recipe["cell_radius_m"] <= 0:
        raise ValueError("Native length and radius must be positive")
    if not 0 <= recipe["lattice_disorder"] <= 1:
        raise ValueError("Require the declared bounded disorder")
    if (
        not isinstance(before, (list, tuple))
        or len(before) != 5
        or before[0] != "MT19937"
        or not isinstance(before[1], (list, tuple))
        or len(before[1]) != 624
        or any(type(word) is not int or not 0 <= word < 2**32 for word in before[1])
        or type(before[2]) is not int
        or not 0 <= before[2] <= 624
        or type(before[3]) is not int
        or before[3] not in (0, 1)
        or type(before[4]) not in (int, float)
        or not math.isfinite(before[4])
    ):
        raise ValueError("Require the complete normalized native MT stream")


def _layout(value):
    return dict(
        shape=list(value.shape),
        dtype=value.dtype.str,
        strides_bytes=list(value.strides),
        C_contiguous=bool(value.flags.c_contiguous),
        F_contiguous=bool(value.flags.f_contiguous),
    )


def capture():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    root, installed = Path(pins["checkout"]), Path(pins["installed_package"]).parent
    frozen = Path(os.environ.get("CELLS_BETSE_SOURCE", str(root)))
    trees = {}
    for name, expected in pins["source_sha256"].items():
        raw = (frozen / name).read_bytes()
        for path in (frozen / name, root / name, installed / name):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Pinned native lattice source changed: " + str(path))
        trees[name] = ast.parse(raw, filename=str(frozen / name))
    if (
        subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        != pins["revision"]
    ):
        raise ValueError("Pinned native lattice revision changed")
    cls = next(
        n
        for n in trees["betse/science/parameters.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Parameters"
    )
    assignments = sorted(
        (
            n
            for n in ast.walk(cls)
            if isinstance(n, ast.Assign)
            and any(
                ast.unparse(t)
                in ("self.wsx", "self.wsy", "self.ac", "self.d_cell", "self.nx", "self.ny")
                for t in n.targets
            )
        ),
        key=lambda n: n.lineno,
    )
    assert len(assignments) == 8
    cls = next(
        n
        for n in trees["betse/science/cells.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    lattice = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_make_cell_lattice"
    )
    decorator = next(
        n
        for n in trees["betse/util/type/types.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "type_check"
    )
    wrapper = ast.parse("def parameters(self):\n pass\n").body[0]
    wrapper.body = copy.deepcopy(assignments)
    body = copy.deepcopy(lattice)
    sites = dict(
        parameters=dict(
            lines=[[n.lineno, n.end_lineno] for n in assignments],
            ast_sha256=hashlib.sha256(
                ast.dump(
                    ast.Module(body=assignments, type_ignores=[]), include_attributes=False
                ).encode()
            ).hexdigest(),
        ),
        lattice=dict(
            first_line=lattice.lineno,
            last_line=lattice.end_lineno,
            ast_sha256=hashlib.sha256(
                ast.dump(lattice, include_attributes=False).encode()
            ).hexdigest(),
        ),
        type_check=dict(
            first_line=decorator.lineno,
            last_line=decorator.end_lineno,
            ast_sha256=hashlib.sha256(
                ast.dump(decorator, include_attributes=False).encode()
            ).hexdigest(),
        ),
    )
    source_map = json.loads(
        PROTOCOL.with_name("betse_lattice_seed_generation_source_map.json").read_text()
    )
    for key in ("parameters", "lattice", "type_check"):
        assert sites[key]["ast_sha256"] == source_map[key]["ast_sha256"], key
    module = ast.fix_missing_locations(
        ast.Module(body=[copy.deepcopy(decorator), wrapper, body], type_ignores=[])
    )
    # Verify both source wrappers before compiling; neither body is rewritten.
    assert ast.dump(module.body[0], include_attributes=False) == ast.dump(
        decorator, include_attributes=False
    )
    assert ast.dump(
        ast.Module(body=module.body[1].body, type_ignores=[]), include_attributes=False
    ) == ast.dump(ast.Module(body=assignments, type_ignores=[]), include_attributes=False)
    assert ast.dump(module.body[2], include_attributes=False) == ast.dump(
        lattice, include_attributes=False
    )
    sites["wrapper_verification"] = dict(
        parameter_body_exact=True,
        loop_annotations_and_decorator_exact=True,
        pinned_type_check_exact=True,
        postponed_annotations=True,
        normalized_call_boundary_validated=True,
        native_package_import_hook_executed=False,
    )
    return module, sites, pins


def evaluate(recipe, before):
    _validated_inputs(recipe, before)
    module, sites, pins = capture()
    rng = np.random.RandomState(0)
    rng.set_state((before[0], np.asarray(before[1], np.uint32), before[2], before[3], before[4]))
    calls, bases, captured_locals, color_counts, source_layouts = [], {}, {}, {}, {}

    class Recorder:
        def rand(self, *shape):
            frame = sys._getframe(1)
            count = math_product(shape)
            if count > 128:
                raise ValueError("Native capture point-count bound exceeded before drawing")
            if not bases:
                bases.update(
                    {key: np.array(frame.f_locals[key], copy=True) for key in ("x_2d", "y_2d")}
                )
            value = rng.rand(*shape)
            calls.append(
                dict(
                    line=frame.f_lineno,
                    shape=list(shape),
                    count=count,
                    values=np.array(value, copy=True),
                    rng_after=_state(rng),
                )
            )
            return value

    class NumpyNamespace:
        random = Recorder()

        def __getattr__(self, name):
            return getattr(np, name)

    enums = SimpleNamespace(SQUARE=object(), HEX=object())
    ns = dict(
        np=NumpyNamespace(),
        CellLatticeType=enums,
        BetseSimConfException=ValueError,
        logs=SimpleNamespace(log_info=lambda *args: None),
    )
    exec(
        compile(
            module,
            "<pinned native lattice seed generation>",
            "exec",
            flags=__future__.annotations.compiler_flag,
            dont_inherit=True,
        ),
        ns,
    )
    p = SimpleNamespace(
        world_len=float(recipe["world_len_m"]),
        cell_radius=float(recipe["cell_radius_m"]),
        cell_lattice_disorder=float(recipe["lattice_disorder"]),
        cell_lattice_type=getattr(enums, recipe["lattice_type"], None),
    )
    cells = SimpleNamespace()
    code = ns["_make_cell_lattice"].__code__

    def trace(frame, event, arg):
        if frame.f_code is code:
            if event in ("return", "exception"):
                source_layouts.update(
                    {
                        key: _layout(value)
                        for key, value in frame.f_locals.items()
                        if isinstance(value, np.ndarray)
                    }
                )
                captured_locals.update(
                    {
                        key: np.array(value, copy=True, order="K")
                        for key, value in frame.f_locals.items()
                        if isinstance(value, np.ndarray)
                    }
                )
                color_counts.update(
                    {
                        key: int(value)
                        for key, value in frame.f_locals.items()
                        if key in ("blue_x_num", "blue_y_num", "red_x_num", "red_y_num")
                    }
                )
            return trace
        return None

    failure = None
    global_before = np.random.get_state()
    previous = sys.gettrace()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            ns["parameters"](p)
            if max(p.nx, p.ny) > 16:
                raise ValueError("Native capture raw axis-count safety bound exceeded")
            sys.settrace(trace)
            ns["_make_cell_lattice"](cells, p)
        except Exception as error:
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
        finally:
            sys.settrace(previous)
    after_global = np.random.get_state()
    unchanged = (
        global_before[0] == after_global[0]
        and np.array_equal(global_before[1], after_global[1])
        and global_before[2:] == after_global[2:]
    )
    values = None
    if failure is None:
        blue = red = None
        if recipe["lattice_type"] == "HEX":
            blue = np.column_stack(
                (captured_locals["x_2d_blue"].ravel(), captured_locals["y_2d_blue"].ravel())
            )
            red = np.column_stack(
                (captured_locals["x_2d_red"].ravel(), captured_locals["y_2d_red"].ravel())
            )
        values = dict(
            base_points_m=np.column_stack((bases["x_2d"].ravel(), bases["y_2d"].ravel())),
            blue_points_m=blue,
            red_points_m=red,
            x_uniforms=calls[0]["values"],
            y_uniforms=calls[1]["values"],
            x_displacement_m=captured_locals["x_rnd"],
            y_displacement_m=captured_locals["y_rnd"],
            lattice_points_m=captured_locals["xypts"],
            bbox_seed_points_m=captured_locals["bbox"],
            all_seed_points_m=np.array(cells.clust_xy, copy=True),
            expanded_bbox_m=np.array(cells.bbox, copy=True),
            centre_m=np.array(cells.centre, copy=True),
            axis_bounds_m=np.asarray(cells.xyaxis),
        )
    parameters = {
        key: getattr(p, key)
        for key in (
            "world_len",
            "cell_radius",
            "cell_lattice_disorder",
            "wsx",
            "wsy",
            "ac",
            "d_cell",
            "nx",
            "ny",
        )
        if hasattr(p, key)
    }
    return dict(
        status="source_failed" if failure else "source_completed",
        parameters=parameters,
        values=values,
        raw_locals=captured_locals,
        source_layouts=source_layouts,
        source_color_counts=color_counts,
        calls=calls,
        rng_before=before,
        rng_after=_state(rng),
        failure=failure,
        warnings=[str(w.message) for w in caught],
        native_source_sha256=pins["source_sha256"],
        source_sites=sites,
        original_global_rng_unchanged=bool(unchanged),
        downstream_mesh_or_image_executed=False,
    )


def math_product(shape):
    result = 1
    for value in shape:
        result *= value
    return result
