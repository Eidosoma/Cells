"""Fresh saved-mesh replay; production packages are denied before providers load."""

import argparse
import builtins
import hashlib
import importlib.abc
import json
import os
import sys
import traceback
from importlib import metadata
from pathlib import Path

BLOCKED = {"cells", "betse", "jax", "jaxlib"}
_original_import = builtins.__import__


def guarded(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise ImportError("Initial mesh production package denied: " + name)
    return _original_import(name, *args, **kwargs)


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError("Initial mesh production package denied: " + fullname)


builtins.__import__ = guarded
sys.meta_path.insert(0, Guard())

import numpy as np  # noqa: E402

from validation.betse import betse_initial_mesh_preparation_wire as wire  # noqa: E402


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, record, columns=None):
    if columns is not None:
        with path.with_suffix(".npz").open("xb") as handle:
            np.savez_compressed(handle, **columns)
            handle.flush()
            os.fsync(handle.fileno())
    with path.with_suffix(".json").open("x") as handle:
        json.dump(record, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def owned_tree(node):
    kind = node["kind"]
    if kind == "numeric_array":
        return dict(
            type="array", layout=node["source_layout"], column=node["column"], sha256=node["sha256"]
        )
    if kind == "object_array":
        return dict(
            type=kind, layout=node["source_layout"], values=[owned_tree(v) for v in node["items"]]
        )
    if kind == "dict":
        return dict(type=kind, values=[[owned_tree(k), owned_tree(v)] for k, v in node["items"]])
    if "items" in node:
        return dict(type=kind, values=[owned_tree(v) for v in node["items"]])
    return {"type": kind, **{k: v for k, v in node.items() if k != "kind"}}


def load_cache(record, archive, *, owned):
    prefix = record["column_prefix"] + "__"
    columns = {
        name[len(prefix) :]: archive[name] for name in archive.files if name.startswith(prefix)
    }
    if owned:
        descriptor = json.dumps(record["descriptor"], sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(descriptor.encode()).hexdigest() == record["identity"]
        tree = owned_tree(record["descriptor"])
    else:
        tree = record["tree"]
    return wire.validate(dict(tree=tree, columns=columns))


def compare_cache(left, right, *, failure=False):
    wire.validate(left)
    wire.validate(right)
    if failure:
        # Keep full raw reasons in both archives. Qhull identifiers and trace
        # text vary between executions; compare every other typed member.
        def without_reason(tree):
            assert tree["type"] == "dict"
            return {
                **tree,
                "values": [
                    [k, v]
                    for k, v in tree["values"]
                    if not (k["type"] == "str" and k["value"] == "reason")
                ],
            }

        a, b = without_reason(left["tree"]), without_reason(right["tree"])
    else:
        a, b = left["tree"], right["tree"]
    assert wire.signature(a) == wire.signature(b)


def retain_native(path, proof):
    columns = {}

    def record(prefix, cache):
        columns.update({prefix + "__" + key: value for key, value in cache["columns"].items()})
        return dict(tree=cache["tree"], column_prefix=prefix)

    report = {k: v for k, v in proof.items() if k not in ("cache", "constructed_cache", "events")}
    report.update(
        constructed_cache=record("constructed", proof["constructed_cache"]),
        cache=record("final", proof["cache"]),
        events=[
            {
                **{k: v for k, v in event.items() if k != "payload"},
                "payload": record(f"event{event['sequence']}", event["payload"]),
            }
            for event in proof["events"]
        ],
    )
    write(path, report, columns)


def native_case(provider, path, actual, archive, replay_root):
    inputs, request = actual["inputs"], actual["request"]
    kwargs_cache = load_cache(actual["request_cache"], archive, owned=True)
    if request["origin"] == "owned_image_prelude":
        caller = provider.caller_kwargs(
            inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
        )
        kwargs, before = caller["kwargs"], caller["rng_before_constructor"]
        captured = wire.capture(kwargs)
        write(
            replay_root / (path.stem + "-caller"),
            dict(
                caller={k: v for k, v in caller.items() if k != "kwargs"}, kwargs=captured["tree"]
            ),
            captured["columns"],
        )
        compare_cache(kwargs_cache, captured)
    else:
        assert request["origin"] == "reused_fixed_B09"
        raw = inputs["input"]
        kwargs = dict(
            raw["mesh"],
            seed_points=None
            if raw["seed_points_m"] is None
            else np.asarray(raw["seed_points_m"], dtype=float),
        )
        before = inputs["rng_before"]
        compare_cache(kwargs_cache, wire.capture(kwargs))
    assert before == request["stream_before"]["state"]
    proof = provider.evaluate(kwargs, request["constructor_point_ids"], before)
    retain_native(replay_root / path.stem, proof)
    failed = actual["state"]["status"] == "retained_source_failure"
    assert proof["status"] == ("source_failed" if failed else "source_completed")
    if failed:
        assert proof["failure"]["type"] == actual["state"]["failure_type"]
        assert proof["stage"] == actual["state"]["failure_stage"]
    else:
        assert actual["state"]["status"] == "source_completed_unqualified"
        assert proof["failure"] is None
    compare_cache(
        load_cache(actual["constructed"], archive, owned=True), proof["constructed_cache"]
    )
    compare_cache(load_cache(actual["final"], archive, owned=True), proof["cache"])
    assert len(actual["events"]) == len(proof["events"])
    saved = json.loads(
        path.with_name(path.stem.removesuffix("-actual") + "-native.json").read_text()
    )
    with np.load(
        path.with_name(path.stem.removesuffix("-actual") + "-native.npz"), allow_pickle=False
    ) as saved_archive:
        compare_cache(
            load_cache(saved["constructed_cache"], saved_archive, owned=False),
            proof["constructed_cache"],
        )
        compare_cache(load_cache(saved["cache"], saved_archive, owned=False), proof["cache"])
        for event, expected, original in zip(
            actual["events"], proof["events"], saved["events"], strict=True
        ):
            for key in ("sequence", "kind", "method", "depth"):
                assert event[key] == expected[key] == original[key]
            is_failure = failed and event["kind"].endswith("failure")
            compare_cache(
                load_cache(event["payload"], archive, owned=True),
                expected["payload"],
                failure=is_failure,
            )
            compare_cache(
                load_cache(original["payload"], saved_archive, owned=False),
                expected["payload"],
                failure=is_failure,
            )
    for actual_key, native_key in (
        ("stream_before", "rng_before"),
        ("stream_after_constructor", "rng_after_constructor"),
        ("stream_after", "rng_after"),
    ):
        assert actual["state"][actual_key]["state"] == proof[native_key] == saved[native_key]
    assert actual["state"]["retained_point_ids"] == list(proof["retained_point_ids"])
    assert list(proof["retained_point_ids"]) == saved["retained_point_ids"]
    for key in ("constructor_completed", "pre_mesh_completed"):
        assert actual["state"][key] == proof[key] == saved[key]
    assert proof["original_global_rng_unchanged"] and not proof["topology_qualified"]
    assert not proof["operators_created"] and not proof["image_clip_executed"]
    return dict(
        case=path.stem.removesuffix("-actual"),
        origin=request["origin"],
        raw_source_failure=failed,
        full_typed_caches_and_trace_exact=True,
    )


def fraction(actual, expected, atol):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    assert a.shape == b.shape
    value = float(np.max(abs(a - b) / (np.asarray(atol) + 6e-12 * abs(b)), initial=0))
    assert value <= 1, value
    return value


def reference_case(provider, path, actual, archive, replay_root):
    events = []
    for event in actual["events"]:
        cache = load_cache(event["payload"], archive, owned=True)
        events.append(
            {
                **{k: v for k, v in event.items() if k != "payload"},
                "payload": wire.plain(cache["tree"], cache["columns"]),
            }
        )
    case = path.stem.removesuffix("-actual")
    reports = []
    for refinement in (1, 2):
        target = replay_root / (case + f"-reference-{refinement}")
        try:
            report = provider.evaluate(events, refinement=refinement)
        except provider.ReferenceFailure as error:
            write(target, error.trial)
            raise
        write(target, report)
        reports.append(report)
    failed = actual["state"]["status"] == "retained_source_failure"
    maximum = resolution = 0.0
    first, second = reports
    if not failed:
        assert actual["state"]["status"] == "source_completed_unqualified"
        for refinement, report in enumerate(reports, 1):
            saved = path.with_name(case + f"-reference-{refinement}.json")
            assert report == json.loads(saved.read_text())
        by_sequence = {e["sequence"]: e["payload"] for e in events}
        for a, b in zip(first["primitives"], second["primitives"], strict=True):
            assert (a["sequence"], a["method"]) == (b["sequence"], b["method"])
            method = a["method"]
            atol = (
                1e-26
                if method == "area"
                else [1e-27, 1e-26, 1e-27, 1e-27]
                if method == "quad_circumc"
                else 1e-27
            )
            maximum = max(
                maximum, fraction(by_sequence[a["sequence"]]["result"], a["expected_result"], atol)
            )
            resolution = max(resolution, fraction(a["expected_result"], b["expected_result"], atol))
        for a, b in zip(first["nearest"], second["nearest"], strict=True):
            assert a["sequence"] == b["sequence"]
            payload = by_sequence[a["sequence"]]
            actual_values = np.asarray(payload["result"][0]).ravel().tolist()
            expected = [v for row in a["expected"] for v in row["ranked_distances"]]
            refined = [v for row in b["expected"] for v in row["ranked_distances"]]
            assert [r["exact_tie_candidate_indices"] for r in a["expected"]] == [
                r["exact_tie_candidate_indices"] for r in b["expected"]
            ]
            floor = 2e-14 if np.asarray(payload["data"]).dtype.kind in "iu" else 1e-27
            for value, target, refined_value in zip(actual_values, expected, refined, strict=True):
                if target == "infinity":
                    assert np.isinf(value) and refined_value == "infinity"
                else:
                    maximum = max(maximum, fraction(value, target, floor))
                    resolution = max(resolution, fraction(target, refined_value, floor))
        assert resolution <= 0.1
    assert not first["topology_qualified"] and not second["topology_qualified"]
    return dict(
        case=case,
        origin=actual["request"]["origin"],
        raw_source_failure=failed,
        maximum_error_fraction=maximum,
        maximum_reference_resolution_fraction=resolution,
        raw_reference_scope="Diagnostics of retained source prefix only" if failed else None,
        independent_native_failure_generation=False,
        topology_qualified=False,
    )


def runtime():
    loaded = sorted(name for name in sys.modules if name.split(".")[0] in BLOCKED)
    files, file_errors = {}, {}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            try:
                if Path(name).is_file():
                    files[str(Path(name).resolve())] = sha(name)
            except Exception as error:
                file_errors[str(name)] = dict(type=type(error).__name__, message=str(error))
    executable = Path(sys.executable).resolve()
    files[str(executable)] = sha(executable)
    packages, package_errors = {}, {}
    for name in ("numpy", "scipy"):
        try:
            packages[name] = metadata.version(name)
        except Exception as error:
            packages[name] = None
            package_errors[name] = dict(type=type(error).__name__, message=str(error))
    return dict(
        files=files,
        file_errors=file_errors,
        affinity=sorted(os.sched_getaffinity(0)),
        python=sys.version,
        packages=packages,
        package_errors=package_errors,
        loaded_production_modules=loaded,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "reference"), required=True)
    args = parser.parse_args()
    evidence = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    root, replay_root = evidence / "initial-mesh", evidence / (args.mode + "-fresh")
    replay_root.mkdir(exist_ok=False)
    rows, failure = [], None
    try:
        assert not runtime()["loaded_production_modules"]
        if args.mode == "native":
            from validation.betse import betse_initial_mesh_preparation_native as provider

            evaluate = native_case
        else:
            from validation.betse import betse_initial_mesh_preparation_reference as provider

            evaluate = reference_case
        paths = sorted(root.glob("*-actual.json"))
        assert len(paths) == 12
        for path in paths:
            actual = json.loads(path.read_text())
            with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
                rows.append(evaluate(provider, path, actual, archive, replay_root))
        complete = [r for r in rows if not r["raw_source_failure"]]
        raw = [r for r in rows if r["raw_source_failure"]]
        assert len(complete) == 10 and len(raw) == 2
        assert sum(r["origin"] == "reused_fixed_B09" for r in complete) == 5
        assert sum(r["origin"] == "owned_image_prelude" for r in complete) == 5
        assert all(r["origin"] == "owned_image_prelude" for r in raw)
        assert not runtime()["loaded_production_modules"]
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        inventory = runtime()
        result = dict(
            mode=args.mode,
            status="failed" if failure else "passed",
            failure=failure,
            cases=rows,
            complete_cases=sum(not r["raw_source_failure"] for r in rows),
            raw_failures=sum(r["raw_source_failure"] for r in rows),
            reused_B09_cases=sum(r["origin"] == "reused_fixed_B09" for r in rows),
            production_imports_denied=True,
            loaded_production_modules=inventory.pop("loaded_production_modules"),
            runtime=inventory,
            topology_qualified=False,
            downstream_geometry_admitted=False,
            new_B09_or_MT_coverage=False,
            operators_created=False,
            image_clip_executed=False,
        )
        write(evidence / (args.mode + "-replay"), result)
    assert not result["loaded_production_modules"]
    print(json.dumps(dict(mode=args.mode, complete_cases=10, raw_failures=2)), flush=True)


if __name__ == "__main__":
    main()
