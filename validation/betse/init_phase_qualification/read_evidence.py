"""Complete INIT archives and actual runtimes, read without science imports."""

import argparse
import hashlib
import json
import struct
import sys
import traceback
from pathlib import Path

from common import (
    RAW_LIMIT,
    exact_ids,
    finite_budget,
    read,
    require,
    sha,
    verify_runtime,
    write,
)
from contracts import RAW_CALLBACKS, RAW_EXPECTATIONS, declaration, verify_roster


def tree_sha(value):
    digest = hashlib.sha256()
    for chunk in json.JSONEncoder(
        sort_keys=True, separators=(",", ":"), allow_nan=False
    ).iterencode(value):
        digest.update(chunk.encode())
    return digest.hexdigest()


def field(tree, key):
    require(type(tree) is dict and set(tree) == {"mapping"}, "Typed mapping root required")
    found = [value for name, value in tree["mapping"] if name == key]
    require(len(found) == 1, "Missing/duplicate typed field: " + key)
    return found[0]


def metadata(tree):
    if type(tree) is dict:
        if set(tree) == {"mapping"}:
            result = {}
            for key, value in tree["mapping"]:
                require(key not in result, "Duplicate typed metadata key")
                result[key] = metadata(value)
            return result
        if set(tree) == {"sequence"}:
            return [metadata(v) for v in tree["sequence"]]
        if set(tree) == {"float64_bits"}:
            return struct.unpack("<d", bytes.fromhex(tree["float64_bits"]))[0]
        raise ValueError("Unexpected array in scalar runtime/refusal metadata")
    require(tree is None or type(tree) in (str, int, bool), "Unsupported typed metadata")
    return tree


def runtime(row, out, plan, inputs, role):
    sources = (
        plan["reference_runtime_source_sha256"] if role == "reference" else inputs["source_sha256"]
    )
    return verify_runtime(
        row,
        source_root=out / "source",
        source_hashes=sources,
        runner_root=Path(__file__).resolve().parent,
        runner_hashes=plan["runner_sha256"],
        executable=plan["python"],
        executable_sha256=plan["python_sha256"],
        cpu=plan["cpu"],
        role=role,
        external_roots=plan["external_runtime_roots"],
        extra_file_pins={
            **plan["extra_runtime_file_pins"],
            **{str(out / name): digest for name, digest in inputs["tool_sha256"].items()},
        },
    )


def reference(folder, mode, out, plan, inputs):
    incoming = read(folder / "inputs.json", RAW_LIMIT)
    expected_mode = (
        "cold_initialization" if mode == "cold" else "field" if mode == "bootstrap" else mode
    )
    require(incoming.get("mode") == expected_mode, "Exact reference input mode")
    comparison = read(folder / "comparison.json", RAW_LIMIT)
    require(
        comparison.get("fresh_conditional_reference") is True
        and comparison.get("carried_reference_forms") == 0,
        "Conditional reference scope",
    )
    maxima = {}
    for section, limit in (("fields", 1.0), ("resolutions", 0.1)):
        values = comparison.get(section)
        require(type(values) is dict and values, "Empty reference comparison section")
        scores = [row["normalized_max_error"] for row in values.values()]
        require(
            all(finite_budget(v, limit) for v in scores),
            "Unchanged reference budget failed",
        )
        maxima[section] = max(scores)
    children = []
    for level, precision in ((1, 100), (2, 160)):
        path = folder / f"reference-{level}.json"
        answer = read(path, RAW_LIMIT)
        require(
            answer.get("mode") == expected_mode
            and answer.get("production_imports_denied") is True
            and answer.get("loaded_production_modules") == []
            and answer.get("carried_reference_forms") == 0
            and answer.get("decimal_precision") == precision
            and answer.get("source_phase") == "INIT"
            and answer.get("legacy_run_sim") is False
            and answer.get("independent_trajectory") is False
            and answer.get("physical_global_conservation_credit") is False,
            "Exact independent reference identity/scope",
        )
        bound = runtime(answer["runtime"], out, plan, inputs, "reference")
        children.append(
            dict(
                path=str(path.relative_to(out)),
                sha256=sha(path),
                input_sha256=sha(folder / "inputs.json"),
                refinement=level,
                decimal_precision=precision,
                runtime=bound,
            )
        )
    return dict(
        mode=mode,
        input_sha256=sha(folder / "inputs.json"),
        comparison_sha256=sha(folder / "comparison.json"),
        max_budget_fraction=maxima["fields"],
        max_self_resolution_fraction=maxima["resolutions"],
        children=children,
    )


def refusal(base, spec):
    case, category = spec["case"], spec["category"]
    if category == "raw":
        tree = read(base / (case + "-raw-failure-before-assertions/data.json"), RAW_LIMIT)
        stage, cause = RAW_EXPECTATIONS[case]
        require(
            metadata(field(field(tree, "partial"), "stage")) == stage
            and cause in metadata(field(tree, "error"))
            and metadata(field(tree, "traceback")),
            "Exact raw failure stage/cause/traceback",
        )
        observed = field(tree, "observed")
        require(
            [name for name, _ in observed["mapping"]] == list(RAW_CALLBACKS[case]),
            "Raw reached-buffer order/count",
        )
        return dict(
            category=category,
            stage=stage,
            cause=cause,
            completed_call_credit=0,
            raw_trial_retained=True,
        )
    if category == "dependency":
        incoming = read(base / (case + "-rejected-inputs-before-check/data.json"), RAW_LIMIT)
        failed = read(base / (case + "-exact-refusal/data.json"), RAW_LIMIT)
        expected = metadata(field(incoming, "expected"))
        require(
            type(expected) is str
            and expected
            and expected in metadata(field(failed, "cause"))
            and metadata(field(failed, "traceback"))
            and metadata(field(failed, "type")) in ("ValueError", "InitRejected"),
            "Exact dependency failure cause/type/traceback",
        )
        return dict(
            category=category,
            stage=metadata(field(incoming, "stage")),
            cause=expected,
            completed_call_credit=0,
        )
    if category == "observer":
        tree = read(base / (case + "-call-0-retained-exception/data.json"), RAW_LIMIT)
        partial = field(tree, "partial")
        require(
            metadata(field(partial, "stage")) == case + "_observer"
            and metadata(field(partial, "root_cause"))
            == dict(type="RuntimeError", message="INIT observer exact cause at " + case)
            and metadata(field(tree, "traceback")),
            "Exact observer failure cause/stage/traceback",
        )
        return dict(
            category=category,
            stage=case + "_observer",
            completed_call_credit=0,
            accepted_after_call_trial_not_extra_history=True,
        )
    return None


def inspect(out, target, group, plan):
    inputs = read(out / "inputs.json")
    spec = inputs["groups"][group]
    ids = exact_ids(target / "tests.xml", spec["node_ids"])
    require(
        read(target / "pytest-exit.json")["exitstatus"] == 0,
        "Actual pytest session did not pass",
    )
    parent_runtime = runtime(read(target / "pytest-runtime.json"), out, plan, inputs, "pytest")
    base = target / "evidence/normal-ecm-init-phase"
    roster = declaration(spec)
    counts = verify_roster(base, roster)
    detail = target / "reader-detail"
    detail.mkdir(exist_ok=False)
    sys.path.insert(0, str(out / "tools"))
    import capture_binding

    require(
        Path(capture_binding.__file__).resolve() == out / "tools/capture_binding.py",
        "Exact frozen capture tool origin",
    )
    archives = []
    for index, name in enumerate(roster["typed_archives"]):
        bound = capture_binding.bind(base / name, profile="ordinary_ecm_init_phase_01")
        path = detail / f"archive-{index:04d}.json"
        write(path, dict(path=name, binding=bound))
        headers_sha256 = tree_sha(bound["typed_headers"])
        archives.append(
            dict(
                path=name,
                manifest_sha256=bound["manifest_sha256"],
                detail_file=str(path.relative_to(target)),
                detail_sha256=sha(path),
                typed_headers_sha256=headers_sha256,
                arrays=bound["arrays"],
                numeric_scalars=bound["numeric_scalars"],
            )
        )
        del bound
    native = None
    if roster["native_case"] is not None:
        native_path = base / ("isolated-" + roster["native_case"])
        data = read(native_path / "native/data.json", RAW_LIMIT)
        require(
            metadata(field(data, "production_imports_denied")) is True
            and metadata(field(data, "loaded_production_modules")) == []
            and metadata(field(data, "RNG_unchanged")) is True
            and metadata(field(data, "Python_RNG_unchanged")) is True,
            "Native denial/RNG identities",
        )
        native = dict(
            path=str((native_path / "native").relative_to(out)),
            manifest_sha256=sha(native_path / "native/manifest.json"),
            input_sha256=sha(native_path / "inputs.json"),
            runtime=runtime(metadata(field(data, "runtime")), out, plan, inputs, "native"),
        )
        filtered = {
            "mapping": [
                [key, value]
                for key, value in data["mapping"]
                if key
                not in (
                    "runtime",
                    "production_imports_denied",
                    "loaded_production_modules",
                )
            ]
        }
        raw_digest, full_digest = tree_sha(filtered), tree_sha(data)
        del data, filtered
        require(
            tree_sha(
                read(
                    native_path / "native-source-return-before-runtime/data.json",
                    RAW_LIMIT,
                )
            )
            == raw_digest,
            "Native source return differs before/after runtime metadata",
        )
        require(
            tree_sha(
                read(
                    base / (roster["native_case"] + "-native-return-before-assertions/data.json"),
                    RAW_LIMIT,
                )
            )
            == full_digest,
            "Native complete return changed before assertions",
        )
        by_path = {a["path"]: a for a in archives}
        copies = (
            "isolated-" + roster["native_case"] + "/native",
            "isolated-" + roster["native_case"] + "/native-source-return-before-runtime",
            roster["native_case"] + "-native-return-before-assertions",
        )
        require(
            len({by_path[p]["typed_headers_sha256"] for p in copies}) == 1,
            "Native array payload/owner bytes changed between captures",
        )
    points = [
        reference(base / point["folder"], point["mode"], out, plan, inputs)
        for point in roster["reference_points"]
    ]
    if spec["category"] == "positive":
        report = read(base / ("isolated-" + spec["case"] + "/comparison.json"))
        require(
            report.get("completed") is True
            and report.get("source_phase") == "INIT"
            and report.get("complete_calls") == spec["accepted_calls"]
            and report.get("independent_reference_forms") == spec["independent_forms"]
            and report.get("carried_reference_forms") == 0
            and report.get("whole_physical_initializer_credit") is False
            and report.get("inherited_passes") == 0
            and report.get("native_storage_called") is False
            and report.get("display_completed") is False,
            "Complete positive history/report association",
        )
    require(
        2 * len(points) == spec["independent_forms"],
        "Exact 100/160 reference form credit",
    )
    full = dict(
        group=group,
        archives=archives,
        references=points,
        native=native,
        pytest_runtime=parent_runtime,
        refusal=refusal(base, spec),
    )
    write(target / "reader-detail.json", full)
    summary = dict(
        status="passed",
        group=group,
        category=spec["category"],
        exact_pytest_ids=ids,
        complete_calls=spec["accepted_calls"],
        independent_reference_forms=spec["independent_forms"],
        native_captures=int(native is not None),
        counts=counts,
        max_budget_fraction=max((p["max_budget_fraction"] for p in points), default=0.0),
        max_self_resolution_fraction=max(
            (p["max_self_resolution_fraction"] for p in points), default=0.0
        ),
        detail_sha256=sha(target / "reader-detail.json"),
        no_scientific_evaluation=True,
        independent_trajectory=False,
        whole_native_phase_completed=False,
        whole_physical_initializer_credit=False,
        inherited_checks=0,
    )
    from runtime_inventory import inventory

    reader_runtime = inventory()
    runtime(reader_runtime, out, plan, inputs, "reader")
    write(target / "reader-runtime.json", reader_runtime)
    summary["reader_runtime_sha256"] = sha(target / "reader-runtime.json")
    write(target / "evidence-binding.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    try:
        inspect(args.output.resolve(), args.target.resolve(), args.group, read(args.plan))
    except BaseException as error:
        write(
            args.target / "reader-failure.json",
            dict(
                status="failed",
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                failed_evidence_unchanged=True,
            ),
        )
        raise


if __name__ == "__main__":
    main()
