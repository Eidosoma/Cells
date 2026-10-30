"""Fresh saved-column native/reference replay with production imports denied."""

import argparse
import builtins
import hashlib
import importlib.abc
import json
import math
import os
import sys
from importlib import metadata
from pathlib import Path

BLOCKED = {"cells", "jax", "jaxlib", "betse"}
original_import = builtins.__import__


def guarded(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise ImportError("Production import denied: " + name)
    return original_import(name, *args, **kwargs)


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError("Production import denied: " + fullname)


builtins.__import__ = guarded
sys.meta_path.insert(0, Guard())

import numpy as np  # noqa: E402


def flat(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result.update(flat(item, prefix + ("." if prefix else "") + key))
        return result
    return {} if value is None else {prefix: np.asarray(value, dtype=np.float64)}


def budget(key, target):
    absolute = (
        3e-12
        if key.endswith("temperature_K")
        else 3e-14
        if key.endswith(("_V", ".hh_m", ".hh_h", ".ml_m")) or "ion_reversal_V." in key
        else 3e-13
    )
    return absolute + 6e-12 * abs(target)


def maximum(first, last):
    assert first.keys() == last.keys()
    result = 0.0
    for key, target in last.items():
        value = first[key]
        assert value.shape == target.shape, key
        np.testing.assert_array_equal(np.isfinite(value), np.isfinite(target))
        np.testing.assert_array_equal(np.isnan(value), np.isnan(target))
        np.testing.assert_array_equal(np.isposinf(value), np.isposinf(target))
        np.testing.assert_array_equal(np.isneginf(value), np.isneginf(target))
        finite = np.isfinite(target)
        scaled = abs(value[finite] - target[finite]) / budget(key, target[finite])
        result = max(result, float(np.max(scaled, initial=0)))
    assert result <= 1, result
    return result


def wire(values):
    if values is None:
        return None
    return {
        key: np.frombuffer(bytes.fromhex(row["hex"]), dtype="<f8").reshape(row["shape"])
        for key, row in values.items()
    }


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "reference"), required=True)
    args = parser.parse_args()
    if args.mode == "native":
        from validation.betse import betse_temperature_calendar_native as provider
    else:
        from validation.betse import betse_temperature_calendar_reference as provider
    directory = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    results, full, rows_count, refused = [], 0, 0, 0
    for path in sorted((directory / "temperature-calendar").glob("*.json")):
        record = json.loads(path.read_text())
        if record["mode"] == "complete_source_stream":
            original = record["inputs"]
            proof = provider.evaluate(original)
            columns = np.load(path.with_suffix(".npz"), allow_pickle=False)
            actual_cache = {
                key: columns["cache__" + key.replace(".", "__")] for key in record["cache_fields"]
            }
            error = maximum(actual_cache, flat(proof["cache"]))
            resolved = None
            if args.mode == "native":
                assert proof["native_source_sha256"] == record["native_source_sha256"]
                assert proof["source_sites"] == record["native_source_sites"]
                second_guard = provider.evaluate(original, solver="fast")
                error = max(error, maximum(actual_cache, flat(second_guard["cache"])))
            else:
                assert canonical(proof) == canonical(record["reference"])
                resolved = provider.evaluate(original, precision=170)
                assert maximum(flat(proof["cache"]), flat(resolved["cache"])) <= 0.1
            assert len(proof["frames"]) == len(record["rows"])
            for i, row in enumerate(record["rows"]):
                expected = proof["frames"][i]
                names = row["fields"]
                actual = {
                    key: columns[f"actual__row_{i}__" + key.replace(".", "__")] for key in names
                }
                wanted = flat(
                    {key: expected[key] for key in ("values", "probes", "gate_arithmetic")}
                )
                error = max(error, maximum(actual, wanted))
                assert all(row["diagnostics"].values())
                assert row["duration_s"] == original["calendar"]["dt_s"]
                for key in (
                    "call_index",
                    "elapsed_start_s",
                    "elapsed_end_s",
                    "duration_s",
                    "sampled",
                    "events_enabled",
                ):
                    assert row[key] == expected[key], key
                if args.mode == "native":
                    assert row["event_label_s"] == expected["event_label_s"]
                    assert row["source_order"] == expected["source_order"]
                    saved_native = {
                        key: columns[f"native_normal__row_{i}__" + key.replace(".", "__")]
                        for key in names
                    }
                    assert maximum(saved_native, wanted) <= 1
                    alternate = second_guard["frames"][i]
                    alternative_values = flat(
                        {key: alternate[key] for key in ("values", "probes", "gate_arithmetic")}
                    )
                    saved_alternate = {
                        key: columns[f"native_fast__row_{i}__" + key.replace(".", "__")]
                        for key in names
                    }
                    error = max(
                        error,
                        maximum(saved_alternate, alternative_values),
                        maximum(actual, alternative_values),
                    )
                    assert alternate["source_order"] == row["source_order"]
                    assert alternate["event_label_s"] == row["event_label_s"]
                else:
                    assert abs(row["event_label_s"] - expected["event_label_s"]) <= (
                        4 * math.ulp(expected["event_label_s"])
                    )
                    target = flat(
                        {
                            key: resolved["frames"][i][key]
                            for key in ("values", "probes", "gate_arithmetic")
                        }
                    )
                    assert maximum(wanted, target) <= 0.1
                checkpoint = dict(row["checkpoint"])
                identity = checkpoint.pop("identity")
                assert hashlib.sha256(canonical(checkpoint).encode()).hexdigest() == identity
                exact_values = wire(checkpoint["values"])
                for key, value in exact_values.items():
                    np.testing.assert_array_equal(actual["values." + key], value)
                assert checkpoint["binding_identity"] == record["original_binding_identity"]
                assert checkpoint["cache_identity"] == record["cache_identity"]
            columns.close()
            full += 1
            rows_count += len(record["rows"])
            results.append(
                dict(case=path.name, stream_rows=len(record["rows"]), maximum_error_fraction=error)
            )
        elif record["mode"] in ("raw_temperature_refusal", "raw_gate_overflow_refusal"):
            proof = provider.evaluate(record["inputs"])
            trial = record["raw_trial"]
            i = trial["call_index"]
            if args.mode == "native":
                actual = flat(
                    {key: wire(trial[key]) for key in ("values", "probes", "gate_arithmetic")}
                )
                wanted = flat(
                    {
                        key: proof["frames"][i][key]
                        for key in ("values", "probes", "gate_arithmetic")
                    }
                )
                maximum(actual, wanted)
            else:
                assert proof["first_refused_call_index"] == i
                assert not proof["frames"][-1]["admissible"]
            assert record["no_partial_commit"]
            refused += 1
    assert (full, rows_count, refused) == (34, 192, 3), (full, rows_count, refused)
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
        full_streams=full,
        source_call_rows=rows_count,
        raw_refusal_cases=refused,
        cases=results,
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=dict(
            files=files,
            affinity=sorted(os.sched_getaffinity(0)),
            python=sys.version,
            packages={"numpy": metadata.version("numpy")},
        ),
        numerical_scope="Native source-discrete temperature/cache/explicit clock probes only",
        accepted_tissue_steps=False,
        heat_law=False,
        compiled_JAX=False,
    )
    with (directory / (args.mode + "-replay.json")).open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                mode=args.mode,
                full_streams=full,
                source_call_rows=rows_count,
                raw_refusal_cases=refused,
                production_imports_denied=True,
            )
        )
    )


if __name__ == "__main__":
    main()
