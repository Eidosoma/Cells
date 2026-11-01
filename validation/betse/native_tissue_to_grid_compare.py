"""Strict saved mapping/source comparison, independent of domain diagnostics.

Only original references execute under an explicit reviewed release. Saved
records are authenticated bytes, never inputs for executable owner hydration.
"""

import argparse
import hashlib
import json
import resource
import struct
from pathlib import Path
from types import SimpleNamespace

from validation.betse import native_multi_cell_environment_compare as prefix
from validation.betse import native_tissue_to_grid_native as native
from validation.betse import native_tissue_to_grid_qualification as diagnostic

shared, wire, payload = diagnostic.shared, prefix.wire, diagnostic.payload
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_tissue_to_grid_compare.py"
MODULE = "validation.betse.native_tissue_to_grid_compare"
ENDPOINT = native.ENDPOINT
KINDS = ("cells.tissue_to_grid_comparison_plan@2", "cells.tissue_to_grid_reference_release@2")
PURPOSE = "independent_original_tissue_to_grid_comparison"
NO_CREDIT = shared.NO_CREDIT
TRIAL_FIELDS = (
    "request_identity",
    "parent_identity",
    "before",
    "after",
    "results",
    "events",
    "work",
    "warnings",
    "source_completed",
    "failure_stage",
    "identity",
)
CAPTURE_FIELDS = (
    "kind",
    "probe_policy",
    "request",
    "trial",
    "inputs",
    "environment_cache",
    "stream_before",
    "stream_after",
    "work_is_not_independent_cases",
)
REQUEST_FIELDS = (
    "law",
    "parent",
    "probes",
    "native_source_lines",
    "boundary",
    "metadata_verification",
    "invalidated_owners",
)
REFERENCE_FIELDS = (
    "kind",
    "stop_after",
    "status",
    "source_body_completed",
    "source_error",
    "capture_error",
    "capture_errors",
    "failed_stage",
    "environment",
    "before",
    "after",
    "results",
    "inputs",
    "stream_before",
    "stream_after",
    "aliases",
    "work",
    "warnings",
    "original_source_pins",
    "source_sites",
    "probe_policy",
    "reference_inputs",
)
LAW = "betse_actual_multi_caller_declared_mapping_probes@1"
POISSON_SHAPE = [625, 625]
ALIASES = (
    "caller",
    "grid",
    "mesh",
    "parameter",
    "mask",
    # Positive witnesses describe two DISTINCT objects after the literal tail:
    # the original Python list and the exact unchanged np.asarray return.
    # all_points_cell_i is intentionally not the current caller.cell_i.
    "all_points_cell_i_is_original",
    "cell_i_is_tail_asarray_return",
)


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _complete(trial, label):
    if type(trial) is not dict or trial.get("source_completed") is not True:
        raise ValueError("Incomplete actual source trial: " + label)
    for key in ("identity", "parent_identity", "request_identity"):
        wire._digest(trial[key], label + "." + key)
    if any(trial.get(k) is not None for k in ("failure_stage", "failure_type", "failure_message")):
        raise ValueError("Failed/partial source trial: " + label)


def capture_lineage(values, configuration, case):
    if type(values) is not list or len(values) != len(diagnostic.STAGES):
        raise ValueError("Require all fresh caller/environment/operator/tail/mapping captures")
    raw = prefix.capture_lineage(values[:9], configuration, case)
    environment, world_data, capture = values[8:]
    wire._keys(world_data, ("poisson", "tail"), "world_data capture")
    poisson, tail = world_data["poisson"], world_data["tail"]
    for label, trial, parent in (("poisson", poisson, environment), ("tail", tail, poisson)):
        _complete(trial, label)
        if trial["parent_identity"] != parent["identity"]:
            raise ValueError("Changed actual owner lineage: " + label)
        before = wire._stream(trial["stream_before"], label + ".stream_before")
        after = wire._stream(trial["stream_after"], label + ".stream_after")
        prior = wire._stream(parent["stream_after"], label + ".parent_stream")
        if before != prior or before != after:
            raise ValueError("Changed same-caller continuing RNG lineage: " + label)
    validate_capture(capture)
    if capture["trial"]["parent_identity"] != tail["identity"]:
        raise ValueError("Mapping is not associated with this freshly issued world")
    if wire._stream(capture["stream_before"], "mapping.stream_before") != wire._stream(
        tail["stream_after"], "tail.stream_after"
    ):
        raise ValueError("Changed mapping continuing RNG handoff")
    if capture["environment_cache"] != environment["cache"]:
        raise ValueError("Changed retained pre-Poisson diagnostic cache")
    return raw


def validate_capture(capture):
    wire._keys(capture, CAPTURE_FIELDS, "mapping capture")
    if (
        capture["kind"] != diagnostic.RESULT_KIND
        or capture["probe_policy"] != native.PROBE_POLICY
        or capture["work_is_not_independent_cases"] is not True
    ):
        raise ValueError("Changed declared mapping policy")
    trial, request = capture["trial"], capture["request"]
    wire._keys(trial, TRIAL_FIELDS, "mapping Trial")
    wire._keys(request, REQUEST_FIELDS, "mapping request")
    _complete(trial, "mapping")
    if (
        request["law"] != LAW
        or request["parent"] != trial["parent_identity"]
        or _digest(request) != trial["request_identity"]
    ):
        raise ValueError("Changed declared mapping request/source owner")
    if (
        request["native_source_lines"] != native.SOURCE_LINES
        or type(request["invalidated_owners"]) is not list
        or len(request["invalidated_owners"]) != 11
        or len(set(request["invalidated_owners"])) != 11
    ):
        raise ValueError("Changed original source boundary or invalidated owners")
    rows = request["probes"]
    if type(rows) is not list or len(rows) != 4:
        raise ValueError("Exactly four declared 1D/2D mapping probes required")
    for row, name in zip(rows, native.PROBE_POLICY["names"], strict=True):
        wire._keys(row, ("name", "method", "inputs", "interp_method"), "probe")
        if (
            row["name"] != name
            or row["method"] != ("grids" if name.startswith("grid_") else "points")
            or row["interp_method"] != "linear"
        ):
            raise ValueError("Changed mapping order/method/interpolation")
        wire._digest(row["inputs"], "probe inputs")
    if trial["before"]["identity"] != trial["after"]["identity"]:
        raise ValueError("Read-only mapping changed its parent cache")
    if wire._stream(capture["stream_before"], "mapping.stream_before") != wire._stream(
        capture["stream_after"], "mapping.stream_after"
    ):
        raise ValueError("Read-only mapping advanced its continuing RNG")
    for key in ("before", "after"):
        wire._Cache(trial[key], "mapping." + key, True, poisson_shape=POISSON_SHAPE)
    wire._Cache(capture["inputs"], "mapping.inputs", True)
    results = trial["results"]
    if type(results) is not list or [row[0] for row in results] != native.PROBE_POLICY["names"]:
        raise ValueError("Incomplete or reordered mapping results")
    for name, value in results:
        wire._Cache(value, "mapping.result." + name, True)
    record = dict(
        law=LAW,
        request=trial["request_identity"],
        parent=trial["parent_identity"],
        before=trial["before"]["identity"],
        after=trial["after"]["identity"],
        results=[[name, v["identity"]] for name, v in results],
        events=trial["events"],
        work=trial["work"],
        warnings=trial["warnings"],
        source_completed=trial["source_completed"],
        failure_stage=trial["failure_stage"],
        invalidated_owners=request["invalidated_owners"],
        physical_field_phase_admitted=False,
    )
    if _digest(record) != trial["identity"]:
        raise ValueError("Changed mapping Trial identity")
    return capture


def _caller(cache, label):
    fields = wire._fields(cache.tree, label)
    if "caller" not in fields:
        raise ValueError("Missing retained actual caller")
    return fields["caller"]


def _numbers(node):
    if node["type"] != "array":
        raise ValueError("Original mapping output must be a numeric array")
    kind, width, order = wire._dtype(node["layout"]["dtype"], "mapping dtype")
    raw = bytes.fromhex(node["raw"])
    if kind == "f":
        return [
            v[0]
            for v in struct.iter_unpack(
                ("<" if order == "little" else ">") + {2: "e", 4: "f", 8: "d"}[width], raw
            )
        ]
    if kind in "iu":
        return [
            int.from_bytes(raw[i : i + width], order, signed=kind == "i")
            for i in range(0, len(raw), width)
        ]
    raise ValueError("Unexpected declared mapping output dtype")


def diagnostics(capture):
    result = dict(
        environment=prefix.diagnostics_from_cache(capture["environment_cache"]),
        mapping_support={},
        physical_admission=False,
        input_or_mask_repaired=False,
    )
    for name, value in capture["trial"]["results"]:
        cache = wire._Cache(value, "mapping.diagnostics." + name, True)
        numbers = _numbers(cache.tree)
        result["mapping_support"][name] = dict(
            shape=cache.tree["layout"]["shape"],
            finite=cache.finite,
            nonzero=sum(v != 0 for v in numbers),
            elements=len(numbers),
        )
    result["finite_mapping_outputs"] = all(v["finite"] for v in result["mapping_support"].values())
    result["domain_mask_gate_passed"] = bool(
        result["environment"]["domain_gate_passed"] and result["finite_mapping_outputs"]
    )
    return result


def compare(owned, reference):
    validate_capture(owned)
    wire._keys(reference, REFERENCE_FIELDS, "native mapping")
    wire._keys(reference["aliases"], ALIASES, "native aliases")
    differences = []
    result = dict(
        exact_match=False,
        differences=differences,
        cache_pairs_compared=0,
        arrays_compared=0,
        source_comparison_separate_from_domain=True,
        **NO_CREDIT,
    )
    if (
        reference["kind"] != native.KIND
        or reference["stop_after"] != ENDPOINT
        or reference["status"] != "source_completed"
        or reference["source_body_completed"] is not True
        or any(reference[k] is not None for k in ("source_error", "capture_error", "failed_stage"))
        or reference["capture_errors"]
        or reference["probe_policy"] != native.PROBE_POLICY
        or type(reference["reference_inputs"]) is not int
        or reference["reference_inputs"] != 1
        or any(v is not True for v in reference["aliases"].values())
    ):
        differences.append(dict(path="source", reason="incomplete_original_source_or_capture"))
        return result
    trial = owned["trial"]
    for name in ("before", "after"):
        a = wire._Cache(trial[name], "owned." + name, True, poisson_shape=POISSON_SHAPE)
        b = wire._Cache(reference[name], "native." + name, False, poisson_shape=POISSON_SHAPE)
        wire._difference(_caller(a, name), b.tree, name + ".caller", differences)
        result["cache_pairs_compared"] += 1
        result["arrays_compared"] += a.arrays
    a, b = (
        wire._Cache(owned["inputs"], "owned.inputs", True),
        wire._Cache(reference["inputs"], "native.inputs", False),
    )
    wire._difference(a.tree, b.tree, "probe.inputs", differences)
    result["cache_pairs_compared"] += 1
    result["arrays_compared"] += a.arrays
    if [row[0] for row in reference["results"]] != native.PROBE_POLICY["names"]:
        raise ValueError("Incomplete/reordered original mapping results")
    for (name, a), (_, b) in zip(trial["results"], reference["results"], strict=True):
        left, right = wire._Cache(a, "owned." + name, True), wire._Cache(b, "native." + name, False)
        wire._difference(left.tree, right.tree, name, differences)
        result["cache_pairs_compared"] += 1
        result["arrays_compared"] += left.arrays
    for name in ("stream_before", "stream_after"):
        # Mapping itself must not consume the continuing MT state.
        wire._difference(
            wire._stream(owned[name], "owned." + name),
            wire._stream(reference[name], "native." + name),
            name,
            differences,
        )
    if reference["original_source_pins"] != native.pins_for():
        raise ValueError("Changed original mapping source authority")
    if owned["trial"]["warnings"] != reference["warnings"]:
        differences.append(dict(path="warnings", reason="different_mapping_warning_records"))
    result.update(
        exact_match=not differences,
        owned_diagnostics=diagnostics(owned),
        provenance_exclusions=[
            "world/Poisson identities and tail receipts excluded; full caller bytes compared"
        ],
        unrun_operators_or_physical_admission=False,
    )
    return result


def comparison_record(reference):
    return {name: reference[name] for name in REFERENCE_FIELDS}


def _scope():
    metadata = SimpleNamespace(
        **dict(
            vars(native.prefix.shared),
            metadata_imports_for=lambda stop: native.prefix.shared.metadata_imports_for(
                "lapENV_P_inv"
            ),
        )
    )
    api = SimpleNamespace(**dict(vars(native), shared=metadata, inputs=native.prefix.inputs))
    scope = prefix._clone_namespace(
        prefix,
        native=api,
        diagnostic=diagnostic,
        ROOT=ROOT,
        OWN=OWN,
        ENDPOINT=ENDPOINT,
        KINDS=KINDS,
        PURPOSE=PURPOSE,
    )
    scope.update(
        capture_lineage=capture_lineage, compare=compare, comparison_record=comparison_record
    )
    return scope


def saved(path, parent):
    return _scope()["saved"](path, parent)


def prepare(destination, path, parent, *, cpu=6):
    return _scope()["prepare"](destination, path, parent, cpu=cpu)


def verify(prepared, digest, release=None):
    return _scope()["verify"](prepared, digest, release)


def worker(prepared, digest, release, output):
    return _scope()["worker"](prepared, digest, release, output)


def launch(prepared, digest, release, output):
    scope = _scope()
    plan = scope["verify"](prepared, digest, release)
    old = prefix.old_runner
    output = old.protected_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    process = error = None
    try:
        claim = old.claim(prepared, digest, release, output)
        (output / "process").mkdir()
        shared.write(
            output / "inputs.json",
            dict(plan_sha256=digest, release=shared.pin(release), claim=claim, **NO_CREDIT),
        )
        if shared.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Require 12GiB launch memory")
        process = shared.guard.run_bounded(
            [
                plan["interpreter"],
                "-B",
                "-m",
                MODULE,
                "worker",
                "--prepared",
                str(prepared),
                "--plan-sha256",
                digest,
                "--release",
                str(release),
                "--output",
                str(output),
            ],
            directory=output / "process",
            cwd=Path(prepared) / "source",
            env=shared.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        child = shared.read(output / "worker-result.json")
        if (
            child.get("status") != "exact_source_match"
            or child.get("reference_calls_attempted") != 1
            or child.get("accepted_source_comparisons") != 1
            or child.get("attempted_prohibited_imports") != []
        ):
            raise RuntimeError("Original reference/comparison failed")
    except Exception as failure:
        error = old._error(failure)
    record = dict(
        status="failed" if error else "exact_source_match_pending_review",
        process=process,
        error=error,
        worker_result=shared.pin(output / "worker-result.json")
        if (output / "worker-result.json").is_file()
        else None,
        process_receipts=[
            shared.pin(output / "process" / name)
            for name in ("result.json", "failure.json", "resource-stop.json")
            if (output / "process" / name).is_file()
        ],
        automatic_retry=False,
        **NO_CREDIT,
    )
    old._terminal(output / ("failure.json" if error else "result.json"), record)
    return int(error is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    item = sub.add_parser("prepare")
    for name in ("output", "diagnostic", "parent"):
        item.add_argument("--" + name, type=Path, required=True)
    item.add_argument("--cpu", type=int, default=6)
    for name in ("run", "worker"):
        item = sub.add_parser(name)
        for field in ("prepared", "release", "output"):
            item.add_argument("--" + field, type=Path, required=True)
        item.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        prepare(args.output, args.diagnostic, args.parent, cpu=args.cpu)
        return 0
    return (worker if args.command == "worker" else launch)(
        args.prepared, args.plan_sha256, args.release, args.output
    )


if __name__ == "__main__":
    raise SystemExit(main())
