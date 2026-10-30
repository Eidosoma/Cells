"""Fresh replay of saved initialization/field columns with production denied."""

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

from validation.betse import betse_environment_field_checks as checks  # noqa: E402
from validation.betse import betse_geometry_initialization_fixtures as fixtures  # noqa: E402


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "reference"), required=True)
    args = parser.parse_args()
    if args.mode == "native":
        from validation.betse import betse_environment_field_native as field_provider
        from validation.betse import betse_geometry_initialization_native as seed_provider
    else:
        from validation.betse import betse_environment_field_reference as field_provider
        from validation.betse import betse_geometry_initialization_reference as seed_provider
    directory = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    seeds = accepted = refused = 0
    accepted_classes, results = set(), []
    for path in sorted((directory / "geometry-initialization").glob("*.json")):
        record = json.loads(path.read_text())
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as columns:
            if record["mode"] == "complete_seed_provenance":
                recipe = record["inputs"]["recipe"]
                before = record["seed_state"]["stream_before"]["state"]
                proof = (
                    seed_provider.evaluate(recipe, before)
                    if args.mode == "native"
                    else seed_provider.evaluate_seed(recipe, before)
                )
                if args.mode == "reference":
                    assert canonical(proof) == canonical(record["reference"])
                    refined = seed_provider.evaluate_seed(recipe, before, refinement=2)
                    assert canonical(refined) == canonical(record["refined_reference"])
                for name in ("points_m", "x_uniforms", "y_uniforms"):
                    wanted, actual = np.asarray(proof[name]), columns["actual__" + name]
                    if args.mode == "native" or name != "points_m":
                        np.testing.assert_array_equal(actual, wanted)
                    else:
                        assert (
                            np.max(abs(actual - wanted) / (1e-27 + 6e-12 * abs(wanted)), initial=0)
                            <= 1
                        )
                    if args.mode == "reference":
                        np.testing.assert_array_equal(columns["reference__" + name], wanted)
                        np.testing.assert_array_equal(
                            columns["refined__" + name], np.asarray(refined[name])
                        )
                assert canonical(proof["rng_after"]) == canonical(
                    record["seed_state"]["stream_after"]["state"]
                )
                if args.mode == "native":
                    assert proof["source_sites"] == record["native_source_sites"]
                    assert proof["native_source_sha256"] == record["native_source_sha256"]
                    assert proof["original_global_rng_unchanged"]
                seeds += 1
            elif record["mode"] == "complete_generated_environment_bridge":
                inputs = record["field_inputs"]
                proof = field_provider.evaluate(inputs)
                if args.mode == "native":
                    assert (
                        proof["native_source_sha256"] == record["native_source_sha256"]
                        and proof["RNG_unchanged"]
                    )
                    assert not proof["warnings"]
                    checks.compare(
                        checks.saved_columns(columns, "actual", record["fields"]),
                        checks.source_arrays(proof),
                        exact=True,
                    )
                    checks.compare(
                        checks.saved_columns(columns, "native", record["fields"]),
                        checks.source_arrays(proof),
                        exact=True,
                    )
                    maximum = resolution = 0.0
                else:
                    assert canonical(proof) == canonical(record["reference"])
                    refined = field_provider.evaluate(inputs, refinement=2)
                    assert canonical(refined) == canonical(record["refined_reference"])
                    checks.compare(
                        checks.saved_columns(columns, "reference", record["fields"]),
                        checks.source_arrays(proof),
                        exact=True,
                    )
                    checks.compare(
                        checks.saved_columns(columns, "refined", record["fields"]),
                        checks.source_arrays(refined),
                        exact=True,
                    )
                    head = checks.flat(dict(geometry=proof["geometry"], cache=proof["cache"]))
                    maximum = checks.compare(checks.saved_columns(columns, "actual", head), head)
                    resolution = checks.compare(
                        head,
                        checks.flat(dict(geometry=refined["geometry"], cache=refined["cache"])),
                    )
                    wanted = checks.flat(checks.data_frame(proof["frames"][0]))
                    names = ["frame_0." + key for key in wanted]
                    actual = {
                        key.split(".", 1)[1]: value
                        for key, value in checks.saved_columns(columns, "actual", names).items()
                    }
                    maximum = max(
                        maximum,
                        checks.compare(
                            actual,
                            wanted,
                            gross=proof["frames"][0]["current"]["gross"],
                            factor=checks.prefix_factor(inputs["definition"]),
                        ),
                    )
                    resolution = max(
                        resolution,
                        checks.compare(
                            wanted,
                            checks.flat(checks.data_frame(refined["frames"][0])),
                            gross=refined["frames"][0]["current"]["gross"],
                            factor=checks.prefix_factor(inputs["definition"]),
                        ),
                    )
                    assert resolution <= 0.1
                assert not record["new_B09_generation_coverage"] and record["no_metric_override"]
                accepted_classes.add(record["classification"])
                accepted += 1
                results.append(
                    dict(
                        case=path.name,
                        maximum_error_fraction=maximum,
                        maximum_reference_resolution_fraction=resolution,
                    )
                )
            else:
                assert record["mode"] == "inherited_nearest_mapping_refusal"
                if args.mode == "native":
                    proof = field_provider.evaluate(
                        fixtures.readout(record["generated_field_definition"])
                    )
                    key = (
                        "membrane_to_grid"
                        if record["mapping_source"] == "membrane_midpoints"
                        else "cell_to_grid"
                    )
                    np.testing.assert_array_equal(
                        columns["trial__native_single_nearest"], proof["geometry"][key]
                    )
                else:
                    try:
                        field_provider.geometry(record["generated_field_definition"], precision=100)
                    except ValueError as error:
                        assert "ambiguous" in str(error)
                    else:
                        raise AssertionError("Inherited nearest tie not independently confirmed")
                refused += 1
    assert seeds == 5 and accepted + refused == 5 and accepted >= 2
    assert accepted_classes == {"manufactured_seed_cloud", "native_generated_ring_and_centre"}
    loaded = [name for name in sys.modules if name.split(".")[0] in BLOCKED]
    assert not loaded
    files = {}
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_file():
            absolute = Path(path).resolve()
            files[str(absolute)] = sha(absolute)
    executable = Path(sys.executable).resolve()
    files[str(executable)] = sha(executable)
    report = dict(
        mode=args.mode,
        seed_cases=seeds,
        accepted_bridges=accepted,
        nearest_refusals=refused,
        accepted_classes=sorted(accepted_classes),
        cases=results,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        B09_coverage_reused=True,
        new_B09_generation_coverage=False,
        biological_geometry=False,
        full_make_world=False,
        runtime=dict(
            files=files,
            affinity=sorted(os.sched_getaffinity(0)),
            python=sys.version,
            packages={name: metadata.version(name) for name in ("numpy", "scipy")},
        ),
    )
    with (directory / (args.mode + "-replay.json")).open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                mode=args.mode,
                seed_cases=seeds,
                accepted_bridges=accepted,
                nearest_refusals=refused,
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
