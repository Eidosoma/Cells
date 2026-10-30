"""Fresh saved-field replay with production/native package imports denied."""

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


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("native", "reference"))
    args = parser.parse_args()
    if args.mode == "native":
        from validation.betse import betse_environment_field_native as provider
    else:
        from validation.betse import betse_environment_field_reference as provider
    directory = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    results, complete, rows, refused = [], 0, 0, 0
    for path in sorted((directory / "environment-field").glob("*.json")):
        record = json.loads(path.read_text())
        inputs = record["inputs"]
        if record["mode"] == "narrower_nearest_tie_refusal" and args.mode == "reference":
            try:
                provider.evaluate(inputs)
            except ValueError as error:
                assert "ambiguous" in str(error)
            else:
                raise AssertionError("Independent nearest tie was not refused")
            refused += 1
            continue
        if record["mode"] == "raw_current_overflow_refusal" and args.mode == "reference":
            # Binary64 overflow is checked against actual native arrays. A
            # high-precision finite equation is a different arithmetic claim.
            values = np.asarray(inputs["frames"][0]["environment"]["extra_environment_current_xy"])
            assert np.isfinite(values).all() and np.max(abs(values)) >= 1e308
            assert record["no_partial_commit"]
            refused += 1
            continue
        proof = provider.evaluate(inputs)
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as columns:
            if args.mode == "native":
                assert proof["native_source_sha256"] == record["native_source_sha256"]
                assert proof["RNG_unchanged"]
                saved_native = checks.saved_columns(columns, "native", checks.source_arrays(proof))
                checks.compare(saved_native, checks.source_arrays(proof), exact=True)
            if record["mode"] == "complete_instantaneous_fields":
                if args.mode == "native":
                    assert proof["source_sites"] == record["native_source_sites"]
                    assert not proof["warnings"]
                    checks.compare(
                        checks.saved_columns(columns, "actual", record["fields"]),
                        checks.source_arrays(proof),
                        exact=True,
                    )
                    maximum, resolution = 0.0, 0.0
                else:
                    assert canonical(proof) == canonical(record["reference"])
                    refined = provider.evaluate(inputs, refinement=2)
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
                    actual_head = checks.saved_columns(columns, "actual", head)
                    maximum = checks.compare(actual_head, head)
                    resolution = checks.compare(
                        head,
                        checks.flat(dict(geometry=refined["geometry"], cache=refined["cache"])),
                    )
                    factor = checks.prefix_factor(inputs["definition"])
                    for i, row in enumerate(proof["frames"]):
                        wanted = checks.flat(checks.data_frame(row))
                        names = ["frame_" + str(i) + "." + key for key in wanted]
                        saved = checks.saved_columns(columns, "actual", names)
                        actual = {key.split(".", 1)[1]: value for key, value in saved.items()}
                        maximum = max(
                            maximum,
                            checks.compare(
                                actual, wanted, gross=row["current"]["gross"], factor=factor
                            ),
                        )
                        next_row = refined["frames"][i]
                        resolution = max(
                            resolution,
                            checks.compare(
                                wanted,
                                checks.flat(checks.data_frame(next_row)),
                                gross=next_row["current"]["gross"],
                                factor=factor,
                            ),
                        )
                    assert resolution <= 0.1
                complete += 1
                rows += len(proof["frames"])
                results.append(
                    dict(
                        case=path.name,
                        maximum_error_fraction=maximum,
                        maximum_reference_resolution_fraction=resolution,
                    )
                )
            elif record["mode"] in ("raw_zero_screening_refusal", "raw_current_overflow_refusal"):
                assert record["no_partial_commit"]
                if args.mode == "native":
                    target = checks.flat(
                        {key: proof["frames"][0][key] for key in ("values", "current_hodge")}
                    )
                    checks.compare(
                        checks.saved_columns(columns, "trial", record["fields"]), target, exact=True
                    )
                else:
                    assert proof["frames"][0]["values"]["refused_zero_screening"]
                refused += 1
            else:
                assert record["mode"] == "narrower_nearest_tie_refusal"
                assert record["no_partial_commit"] and not record["native_tie_equivalence"]
                chosen = columns["trial__native_single_nearest"]
                np.testing.assert_array_equal(chosen, proof["geometry"]["membrane_to_grid"])
                refused += 1
    assert (complete, rows, refused) == (24, 72, 4), (complete, rows, refused)
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
    report = dict(
        mode=args.mode,
        complete_cases=complete,
        instantaneous_rows=rows,
        raw_refusals=refused,
        cases=results,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        full_refined_buffers_retained=True,
        physical_field_energy_parity=False,
        binary64_overflow_reference_parity=False,
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
                complete_cases=complete,
                instantaneous_rows=rows,
                raw_refusals=refused,
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
