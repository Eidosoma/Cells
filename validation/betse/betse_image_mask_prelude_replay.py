"""Prepared fresh saved-image replay with production/native packages denied."""

import argparse
import builtins
import hashlib
import importlib.abc
import json
import os
import sys
from importlib import metadata
from pathlib import Path

BLOCKED = {"cells", "betse", "jax", "jaxlib"}
original_import = builtins.__import__


def guarded(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise ImportError("Production/native package import denied: " + name)
    return original_import(name, *args, **kwargs)


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError("Production/native package import denied: " + fullname)


builtins.__import__ = guarded
sys.meta_path.insert(0, Guard())

import numpy as np  # noqa: E402


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def canonical(value):
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def coordinate_fraction(actual, expected):
    a, b = np.asarray(actual), np.asarray(expected)
    assert a.shape == b.shape
    value = float(np.max(abs(a - b) / (1e-27 + 6e-12 * abs(b)), initial=0))
    assert value <= 1
    return value


def canonical_cycle(points):
    values = np.asarray(points)
    first = min(range(len(values)), key=lambda index: tuple(values[index]))
    return np.concatenate((values[first:], values[:first]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "reference"), required=True)
    args = parser.parse_args()
    if args.mode == "native":
        from validation.betse import betse_image_mask_prelude_native as provider
    else:
        from validation.betse import betse_image_mask_prelude_reference as provider
    evidence = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    root = evidence / "image-mask-prelude"
    complete, failures, rows = 0, 0, []
    for path in sorted(root.glob("*.json")):
        record = json.loads(path.read_text())
        mode = record.get("mode")
        if mode not in ("complete_image_prelude", "retained_raw_native_mask_failure"):
            continue
        input_path = root / record.get("input_record", path.stem + "-input.json")
        inputs = json.loads(input_path.read_text())
        data = (root / record.get("image_bytes_record", path.stem + "-input.pgm")).read_bytes()
        assert hashlib.sha256(data).hexdigest() == inputs["recipe"]["image_sha256"]
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as columns:
            if mode == "complete_image_prelude":
                qx, qy = record["points_x"], record["points_y"]
                maximum = resolution = 0.0
                if args.mode == "native":
                    proof = provider.evaluate(
                        inputs["recipe"],
                        inputs["geometry"],
                        inputs["controls"],
                        points_x=qx,
                        points_y=qy,
                    )
                    assert (
                        proof["status"] == "mesh_method_argument_boundary"
                        and proof["failure"] is None
                    )
                    assert proof["source_sites"] == record["native"]["source_sites"]
                    assert proof["source_layouts"] == record["native"]["source_layouts"]
                    assert proof["native_source_sha256"] == record["native"]["native_source_sha256"]
                    assert (
                        proof["original_global_rng_unchanged"]
                        and not proof["mesh_constructor_executed"]
                    )
                    for key in record["fields"]:
                        actual, expected = columns["actual__" + key], proof["values"][key]
                        assert actual.dtype == expected.dtype and actual.shape == expected.shape
                        np.testing.assert_array_equal(actual, expected)
                        np.testing.assert_array_equal(columns["native__" + key], expected)
                    for key in ("selected_indices", "paired_linear_values"):
                        np.testing.assert_array_equal(columns["actual__" + key], proof[key])
                        np.testing.assert_array_equal(columns["native__" + key], proof[key])
                    assert canonical(proof["calls"]) == canonical(record["native"]["calls"])
                    actual = json.loads((root / (path.stem + "-actual.json")).read_text())["state"]
                    assert canonical(actual["constructor_kwargs"]) == canonical(
                        proof["calls"][0]["kwargs"]
                    )
                    assert actual["next_method"] == proof["calls"][1]["name"]
                    assert canonical(actual["next_kwargs"]) == canonical(
                        proof["calls"][1]["kwargs"]
                    )
                else:
                    proof = provider.evaluate(data, inputs["geometry"]["bounds_m"], qx, qy)
                    refined = provider.evaluate(
                        data, inputs["geometry"]["bounds_m"], qx, qy, refinement=2
                    )
                    assert canonical(proof) == canonical(record["reference"])
                    assert canonical(refined) == canonical(record["refined_reference"])
                    for prefix, reference in (("reference", proof), ("refined", refined)):
                        for name in columns.files:
                            if name.startswith(prefix + "__"):
                                np.testing.assert_array_equal(
                                    columns[name], reference[name[len(prefix) + 2 :]]
                                )
                    for key in ("bitmap", "clipping_matrix", "active_grid_indices"):
                        np.testing.assert_array_equal(columns["actual__" + key], proof[key])
                    for key in ("xpts_m", "ypts_m", "active_points_m"):
                        maximum = max(
                            maximum, coordinate_fraction(columns["actual__" + key], proof[key])
                        )
                        resolution = max(resolution, coordinate_fraction(proof[key], refined[key]))
                    maximum = max(
                        maximum,
                        coordinate_fraction(
                            canonical_cycle(columns["actual__clipcurve_m"]),
                            proof["canonical_clipcurve_m"],
                        ),
                    )
                    resolution = max(
                        resolution,
                        coordinate_fraction(
                            proof["canonical_clipcurve_m"], refined["canonical_clipcurve_m"]
                        ),
                    )
                    target = np.asarray(proof["paired_linear_values"])
                    budget = 2e-14 + 6e-12 * abs(target)
                    assert (
                        np.max(
                            abs(columns["actual__paired_linear_values"] - target) / budget,
                            initial=0,
                        )
                        <= 1
                    )
                    assert (
                        np.max(
                            abs(target - np.asarray(refined["paired_linear_values"])) / budget,
                            initial=0,
                        )
                        <= 0.1
                    )
                    np.testing.assert_array_equal(
                        columns["actual__selected_indices"],
                        np.asarray(proof["selected_indices"], dtype=int),
                    )
                    assert proof["selected_indices"] == refined["selected_indices"]
                    assert resolution <= 0.1
                assert (
                    record["full_refined_buffers_retained"]
                    and not record["mesh_constructor_executed"]
                )
                rows.append(
                    dict(
                        case=path.stem,
                        maximum_coordinate_fraction=maximum,
                        reference_resolution_fraction=resolution,
                    )
                )
                complete += 1
            else:
                if args.mode == "native":
                    proof = provider.evaluate(
                        inputs["recipe"], inputs["geometry"], inputs["controls"]
                    )
                    assert proof["status"] == "source_failed" and not proof["calls"]
                    assert proof["failure"]["type"] == record["native"]["failure"]["type"]
                    assert proof["original_global_rng_unchanged"]
                    for function, fields in proof["raw_locals"].items():
                        for key, array in fields.items():
                            np.testing.assert_array_equal(columns[function + "__" + key], array)
                else:
                    try:
                        provider.evaluate(data, inputs["geometry"]["bounds_m"])
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Expected independent raw input/hull refusal")
                assert record["no_partial_commit"]
                failures += 1
    assert (complete, failures) == (16, 4)
    loaded = sorted(name for name in sys.modules if name.split(".")[0] in BLOCKED)
    assert not loaded
    files = {}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name and Path(name).is_file():
            p = Path(name).resolve()
            files[str(p)] = sha(p)
    executable = Path(sys.executable).resolve()
    files[str(executable)] = sha(executable)
    result = dict(
        mode=args.mode,
        complete_cases=complete,
        raw_failures=failures,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        cases=rows,
        fast_cubic_independent_claim=False,
        mesh_constructor_executed=False,
        topology_generated=False,
        biological_geometry=False,
        runtime=dict(
            files=files,
            affinity=sorted(os.sched_getaffinity(0)),
            python=sys.version,
            packages={"numpy": metadata.version("numpy")},
        ),
    )
    with (evidence / (args.mode + "-replay.json")).open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(
        json.dumps(dict(mode=args.mode, complete_cases=complete, raw_failures=failures)), flush=True
    )


if __name__ == "__main__":
    main()
