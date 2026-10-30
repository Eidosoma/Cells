"""Prepared fresh saved-seed native/reference replay with production denied."""

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

from validation.betse import betse_lattice_seed_generation_checks as checks  # noqa: E402


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("native", "reference"))
    args = parser.parse_args()
    if args.mode == "native":
        from validation.betse import betse_lattice_seed_generation_native as provider
    else:
        from validation.betse import betse_lattice_seed_generation_reference as provider
    directory = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    cases, complete, refused, nonfinite = [], 0, 0, 0
    for path in sorted((directory / "lattice-seeds").glob("*.json")):
        record = json.loads(path.read_text())
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as columns:
            if record["mode"] == "complete_native_lattice_seed_stage":
                recipe = record["inputs"]["recipe"]
                before = record["seed_stage"]["state"]["stream_before"]["state"]
                proof = provider.evaluate(recipe, before)
                actual = {key: columns["actual__" + key] for key in record["fields"]}
                if args.mode == "native":
                    assert proof["status"] == "source_completed" and proof["failure"] is None
                    assert proof["native_source_sha256"] == record["native_source_sha256"]
                    assert proof["source_sites"] == record["native_source_sites"]
                    assert proof["source_layouts"] == record["native_source_layouts"]
                    assert proof["original_global_rng_unchanged"]
                    checks.compare(actual, proof["values"], exact=True)
                    checks.compare(
                        {key: columns["native__" + key] for key in record["fields"]},
                        proof["values"],
                        exact=True,
                    )
                    assert canonical(proof["calls"][0]["rng_after"]) == canonical(
                        record["native_calls"][0]["rng_after"]
                    )
                    maximum = resolution = 0.0
                else:
                    assert canonical(proof) == canonical(record["reference"])
                    refined = provider.evaluate(recipe, before, refinement=2)
                    assert canonical(refined) == canonical(record["refined_reference"])
                    checks.compare(
                        {key: columns["reference__" + key] for key in record["fields"]},
                        proof["values"],
                        exact=True,
                    )
                    checks.compare(
                        {key: columns["refined__" + key] for key in record["fields"]},
                        refined["values"],
                        exact=True,
                    )
                    maximum = checks.compare(actual, proof["values"])
                    resolution = checks.compare(proof["values"], refined["values"])
                    assert resolution <= 0.1
                assert canonical(proof["parameters"]) == canonical(record["native_parameters"])
                assert canonical(proof["rng_after"]) == canonical(
                    record["seed_stage"]["state"]["stream_after"]["state"]
                )
                assert not record["topology_generated"] and not record["biological_geometry"]
                cases.append(
                    dict(
                        case=path.name,
                        maximum_error_fraction=maximum,
                        maximum_reference_resolution_fraction=resolution,
                    )
                )
                complete += 1
            elif record["mode"] == "retained_raw_nonfinite_centre_failure":
                before = record["stream_before"]["state"]
                proof = provider.evaluate(record["recipe"], before)
                if args.mode == "native":
                    assert proof["status"] == "source_completed" and proof["warnings"]
                    assert canonical(proof["rng_after"]) == canonical(record["native_rng_after"])
                    checks.compare(
                        {key: columns["trial__" + key] for key in record["fields"]},
                        proof["values"],
                        exact=True,
                    )
                    checks.compare(
                        {key: columns["native__" + key] for key in record["fields"]},
                        proof["values"],
                        exact=True,
                    )
                else:
                    assert canonical(proof) == canonical(record["reference"])
                    assert np.isfinite(np.asarray(proof["values"]["centre_m"])).all()
                    checks.compare(
                        {key: columns["reference__" + key] for key in record["fields"]},
                        proof["values"],
                        exact=True,
                    )
                assert record["no_partial_commit"] and not record["accepted_seed_stage"]
                assert not record["binary64_overflow_reference_parity"]
                nonfinite += 1
            else:
                assert record["mode"] == "retained_raw_empty_failure"
                before = record["stream_before"]["state"]
                proof = provider.evaluate(record["recipe"], before)
                assert canonical(proof["rng_after"]) == canonical(before)
                if args.mode == "native":
                    assert proof["status"] == "source_failed" and proof["failure"]
                    assert len(proof["calls"]) == 2 and all(
                        row["count"] == 0 for row in proof["calls"]
                    )
                    for key, value in proof["raw_locals"].items():
                        np.testing.assert_array_equal(columns["native_local__" + key], value)
                else:
                    assert proof["status"] == "empty_native_lattice"
                assert record["no_partial_commit"] and not record["accepted_seed_stage"]
                refused += 1
    assert (complete, refused, nonfinite) == (12, 2, 1), (complete, refused, nonfinite)
    loaded = [name for name in sys.modules if name.split(".")[0] in BLOCKED]
    assert not loaded
    files = {}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name and Path(name).is_file():
            path = Path(name).resolve()
            files[str(path)] = sha(path)
    executable = Path(sys.executable).resolve()
    files[str(executable)] = sha(executable)
    result = dict(
        mode=args.mode,
        complete_cases=complete,
        raw_empty_failures=refused,
        nonfinite_centre_failures=nonfinite,
        cases=cases,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        B09_and_MT_coverage_reused=True,
        topology_generated=False,
        biological_geometry=False,
        downstream_mesh_or_image_executed=False,
        runtime=dict(
            files=files,
            affinity=sorted(os.sched_getaffinity(0)),
            python=sys.version,
            packages={"numpy": metadata.version("numpy")},
        ),
    )
    with (directory / (args.mode + "-replay.json")).open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(dict(mode=args.mode, complete_cases=complete, raw_empty_failures=refused)),
        flush=True,
    )


if __name__ == "__main__":
    main()
