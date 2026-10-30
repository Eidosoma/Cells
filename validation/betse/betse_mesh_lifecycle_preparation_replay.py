"""One guarded fresh lifecycle replay; production imports are denied first."""

import argparse
import json
import math
import os
import struct
import traceback
from decimal import Decimal, localcontext
from pathlib import Path

from validation.betse import betse_initial_mesh_preparation_replay as transport
from validation.betse import betse_mesh_clip_preparation_replay as clipping_transport

np, wire = transport.np, transport.wire


def read(path):
    with Path(path).open() as handle:
        return json.load(handle)


def restore(cache):
    """Restore bounded typed inputs; object pointers never use byte buffers."""
    wire.validate(cache)

    def decode(node):
        kind = node["type"]
        if kind in ("array", "object_array"):
            layout = node["layout"]
            shape, strides = tuple(layout["shape"]), tuple(layout["strides_bytes"])
            if len(shape) > 4 or any(type(n) is not int or n < 0 for n in shape):
                raise ValueError("Invalid bounded replay shape")
            if math.prod(shape) > 262144:
                raise ValueError("Replay input exceeds declared element bound")
            if kind == "object_array":
                if not (layout["C_contiguous"] or layout["F_contiguous"]):
                    raise ValueError("Undeclared noncontiguous object input")
                order = "C" if layout["C_contiguous"] else "F"
                value = np.empty(shape, dtype=object, order=order)
                assert value.size == len(node["values"])
                for index, item in enumerate(node["values"]):
                    value.flat[index] = decode(item)
            else:
                values = cache["columns"][node["column"]]
                if values.dtype.hasobject:
                    raise ValueError("Object pointers are not numeric replay storage")
                empty = any(n == 0 for n in shape)
                offset = (
                    0
                    if empty
                    else sum((n - 1) * (-s) for n, s in zip(shape, strides, strict=True) if s < 0)
                )
                size = (
                    0
                    if empty
                    else values.dtype.itemsize
                    + sum((n - 1) * abs(s) for n, s in zip(shape, strides, strict=True))
                )
                if size > 8 * 2**20:
                    raise ValueError("Replay storage exceeds the declared bound")
                value = np.ndarray(
                    shape,
                    dtype=values.dtype,
                    buffer=np.empty(size, dtype=np.uint8),
                    offset=offset,
                    strides=strides,
                )
                value[...] = values
            assert wire.signature(wire.capture(value)["tree"]) == wire.signature(node)
            return value
        if kind == "numpy_scalar":
            return np.frombuffer(bytes.fromhex(node["bits"]), dtype=np.dtype(node["dtype"]))[0]
        if kind == "float":
            return struct.unpack("<d", bytes.fromhex(node["bits"]))[0]
        if kind == "dict":
            return {decode(k): decode(v) for k, v in node["values"]}
        if kind in ("list", "tuple", "set", "frozenset"):
            cls = {"list": list, "tuple": tuple, "set": set, "frozenset": frozenset}[kind]
            return cls(decode(v) for v in node["values"])
        return node["value"]

    return decode(cache["tree"])


def member(cache, name):
    assert cache["tree"]["type"] == "dict"
    matches = [v for k, v in cache["tree"]["values"] if k == dict(type="str", value=name)]
    assert len(matches) == 1
    columns = {}

    def visit(node):
        if node["type"] == "array":
            columns[node["column"]] = cache["columns"][node["column"]]
        elif node["type"] == "dict":
            for key, value in node["values"]:
                visit(key)
                visit(value)
        elif "values" in node:
            for value in node["values"]:
                visit(value)

    visit(matches[0])
    return restore(dict(tree=matches[0], columns=columns))


def retain_native(path, proof):
    columns = {}

    def record(prefix, cache):
        columns.update({prefix + "__" + k: v for k, v in cache["columns"].items()})
        return dict(column_prefix=prefix, tree=cache["tree"])

    names = ("initial_cache", "before_lifecycle_cache", "cache", "events", "helper_result")
    value = {k: v for k, v in proof.items() if k not in names}
    for key in ("initial_cache", "before_lifecycle_cache", "cache"):
        value[key] = record(key, proof[key])
    value["helper_result"] = (
        None if proof["helper_result"] is None else record("helper_result", proof["helper_result"])
    )
    value["events"] = [
        {
            **{k: v for k, v in e.items() if k != "payload"},
            "payload": record(f"event{e['sequence']}", e["payload"]),
        }
        for e in proof["events"]
    ]
    transport.write(path, value, columns)


def compare_events(events, archive, proof, *, owned, failed):
    assert len(events) == len(proof["events"])
    for actual, expected in zip(events, proof["events"], strict=True):
        for key in ("sequence", "kind", "method", "depth"):
            assert actual[key] == expected[key]
        transport.compare_cache(
            transport.load_cache(actual["payload"], archive, owned=owned),
            expected["payload"],
            failure=failed and actual["kind"].endswith("failure"),
        )


def native_case(provider, path, output):
    """Release the actual record before loading the saved native record."""
    case = path.stem.removesuffix("-actual")
    actual = read(path)
    helper = actual.get("classification") == "isolated_manufactured_lifecycle_helper"
    expected_failure = actual.get("failure_type") if helper else actual["state"]["failure_type"]
    constructor = None
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        if helper:
            prototype = restore(
                transport.load_cache(actual["caches"]["prototype"], archive, owned=True)
            )
            params = restore(transport.load_cache(actual["caches"]["params"], archive, owned=True))
            n = prototype.get("n_tverts", len(prototype["tri_verts"]))
            ids = tuple("manufactured-lifecycle-point-" + str(i) for i in range(n))
            before = actual["stream_before"]["state"]
            proof = provider.evaluate(
                {}, ids, before, None, helper=(actual["method"], prototype, params)
            )
        else:
            from validation.betse import betse_initial_mesh_preparation_native as caller_native

            inputs = actual["inputs"]
            caller = caller_native.caller_kwargs(
                inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
            )
            caller_cache = wire.capture(caller["kwargs"])
            transport.write(
                output / (case + "-caller"),
                dict(
                    kwargs=caller_cache["tree"],
                    caller={k: v for k, v in caller.items() if k != "kwargs"},
                ),
                caller_cache["columns"],
            )
            input_record = read(path.with_name(case + "-input.json"))
            with np.load(path.with_name(case + "-input.npz"), allow_pickle=False) as inputs_archive:
                constructor = transport.load_cache(
                    input_record["caches"]["constructor"], inputs_archive, owned=True
                )
            before = caller["rng_before_constructor"]
            ids = input_record["initial_request"]["constructor_point_ids"]
            mask = member(
                transport.load_cache(actual["caches"]["before"], archive, owned=True), "image_mask"
            )
            options = actual["request"]["options"]
            controls = (
                options["parameters"]
                if actual["request"]["origin"] == "manufactured_native_api_options"
                else options
            )
            proof = provider.evaluate(
                caller["kwargs"],
                ids,
                before,
                mask,
                controls=controls,
                origin=actual["request"]["origin"],
            )
        retain_native(output / (case + "-native"), proof)
        if constructor is not None:
            clipping_transport.compare_constructor_arguments(constructor, caller_cache)
            assert exact(before) == exact(input_record["initial_request"]["stream_before"]["state"])
        failed = expected_failure is not None
        assert proof["status"] == ("source_failed" if failed else "source_completed")
        if failed:
            assert proof["failure"]["type"] == expected_failure
        else:
            assert proof["failure"] is None
        if helper:
            transport.compare_cache(
                transport.load_cache(actual["caches"]["final"], archive, owned=True), proof["cache"]
            )
            if not failed:
                transport.compare_cache(
                    transport.load_cache(actual["caches"]["result"], archive, owned=True),
                    proof["helper_result"],
                )
            assert actual["original_global_rng_unchanged"]
            assert (
                exact(actual["stream_before"]["state"])
                == exact(actual["stream_after"]["state"])
                == exact(proof["rng_after"])
            )
        else:
            for key, target in (("before", "before_lifecycle_cache"), ("final", "cache")):
                transport.compare_cache(
                    transport.load_cache(actual["caches"][key], archive, owned=True), proof[target]
                )
            state = actual["state"]
            assert state["status"] == "source_lifecycle_completed_unqualified"
            assert state["point_ids_before"] == list(proof["point_ids_before_lifecycle"])
            assert state["point_ids_after"] == list(proof["point_ids_after_lifecycle"])
            assert (
                exact(state["stream_before"]["state"])
                == exact(state["stream_after"]["state"])
                == exact(proof["rng_after"])
            )
            for key, value in proof["lifecycle_termination"].items():
                assert state["termination"][key] == value
        compare_events(actual["events"], archive, proof, owned=True, failed=failed)
    del actual
    saved = read(path.with_name(case + "-native.json"))
    with np.load(path.with_name(case + "-native.npz"), allow_pickle=False) as archive:
        for key in ("initial_cache", "before_lifecycle_cache", "cache"):
            transport.compare_cache(
                transport.load_cache(saved[key], archive, owned=False), proof[key]
            )
        if not failed and helper:
            transport.compare_cache(
                transport.load_cache(saved["helper_result"], archive, owned=False),
                proof["helper_result"],
            )
        compare_events(saved["events"], archive, proof, owned=False, failed=failed)
    for key in (
        "status",
        "stage",
        "failure_origin",
        "lifecycle_termination",
        "point_ids_before_lifecycle",
        "point_ids_after_lifecycle",
        "rng_after_initial",
        "rng_after",
    ):
        if key.startswith("rng_"):
            assert exact(saved[key]) == exact(proof[key])
        else:
            assert saved[key] == (list(proof[key]) if key.startswith("point_ids_") else proof[key])
    assert proof["original_global_rng_unchanged"] and not proof["topology_qualified"]
    return dict(
        case=case,
        role="raw_helper" if failed else "helper" if helper else "mesh",
        full_native_typed_trace_exact=True,
        topology_qualified=False,
    )


class SavedEvents:
    """Reiterable typed event stream; only one decoded payload is materialized."""

    def __init__(self, events, archive):
        self.events, self.archive = events, archive

    def __iter__(self):
        for event in self.events:
            cache = transport.load_cache(event["payload"], self.archive, owned=True)
            yield dict(
                sequence=event["sequence"],
                kind=event["kind"],
                method=event["method"],
                payload=wire.plain(cache["tree"], cache["columns"]),
            )


def exact(value):
    return wire.signature(wire.capture(value)["tree"])


def fraction(actual, expected, atol):
    a, b = (np.asarray(actual, dtype=float), np.asarray(expected, dtype=float))
    assert a.shape == b.shape
    value = float(np.max(abs(a - b) / (np.asarray(atol) + 6e-12 * abs(b)), initial=0))
    assert value <= 1, value
    return value


def check_reports(first, second):
    maximum = resolution = 0.0
    for a, b in zip(first["pinv"], second["pinv"], strict=True):
        assert (a["sequence"], a["label"]) == (b["sequence"], b["label"])
        assert a["target"]["supported"] and a["target"]["rank_gap_resolved"]
        assert b["target"]["supported"] and b["target"]["rank_gap_resolved"]
        maximum = max(maximum, fraction(a["actual"], a["target"]["expected"], 2e-14))
        resolution = max(
            resolution, fraction(a["target"]["expected"], b["target"]["expected"], 2e-14)
        )
        for key, identity in a["identities"].items():
            maximum = max(maximum, fraction(identity["actual"], identity["expected"], 2e-14))
            resolution = max(
                resolution, fraction(identity["actual"], b["identities"][key]["actual"], 2e-14)
            )
    for a, b in zip(first["dots"], second["dots"], strict=True):
        assert (a["sequence"], a["label"]) == (b["sequence"], b["label"])
        if a["independent_accuracy_claim"]:
            floor = 1e-27 if a["units"] == "m" else 2e-14
            maximum = max(maximum, fraction(a["actual"], a["expected"], floor))
            resolution = max(resolution, fraction(a["expected"], b["expected"], floor))
    for a, b in zip(first["operators"], second["operators"], strict=True):
        assert a["exact_topological_entries"] and b["exact_topological_entries"]
        np.testing.assert_array_equal(a["actual"], a["expected"])
        assert a["expected"] == b["expected"]
    for name, floor in (("quality", 1e-26), ("energy", 2e-14)):
        for a, b in zip(first[name], second[name], strict=True):
            assert a["sequence"] == b["sequence"]
            maximum = max(maximum, fraction(a["actual"], a["expected"], floor))
            resolution = max(resolution, fraction(a["expected"], b["expected"], floor))
    for a, b in zip(first["smoothing"], second["smoothing"], strict=True):
        assert a["sequence"] == b["sequence"]
        maximum = max(maximum, fraction(a["source_MM"], a["expected_MM"], 2e-14))
        resolution = max(resolution, fraction(a["expected_MM"], b["expected_MM"], 2e-14))
        assert a["semantic_inverse"]["supported"] and a["semantic_inverse"]["rank_gap_resolved"]
        assert b["semantic_inverse"]["supported"] and b["semantic_inverse"]["rank_gap_resolved"]
        maximum = max(
            maximum, fraction(a["source_points_after_m"], a["expected_full_step_points_m"], 1e-27)
        )
        resolution = max(
            resolution,
            fraction(a["expected_full_step_points_m"], b["expected_full_step_points_m"], 1e-27),
        )
    for a, b in zip(first["moves"], second["moves"], strict=True):
        assert a["sequence"] == b["sequence"] and a["point_ids_before"] == a["point_ids_after"]
        assert exact(a["actual"]) == exact(a["expected"])
        assert a == b
    assert resolution <= 0.1
    return (maximum, resolution)


def reference_case(provider, path, output):
    case = path.stem.removesuffix("-actual")
    actual = read(path)
    helper = actual.get("classification") == "isolated_manufactured_lifecycle_helper"
    if helper and actual["failure_type"] is not None:
        assert actual["failure_type"] in ("IndexError", "LinAlgError")
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
            for event in actual["events"]:
                transport.load_cache(event["payload"], archive, owned=True)
        row = dict(
            case=case,
            role="raw_helper",
            source_failure_type=actual["failure_type"],
            independent_numerical_target_claim=False,
            topology_qualified=False,
        )
        transport.write(output / (case + "-raw-reference-scope"), row)
        return row
    reports = []
    with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
        events = SavedEvents(actual["events"], archive)
        for refinement in (1, 2):
            try:
                report = provider.evaluate(events, refinement=refinement)
            except provider.ReferenceFailure as error:
                transport.write(output / (case + f"-reference-{refinement}"), error.trial)
                raise
            transport.write(output / (case + f"-reference-{refinement}"), report)
            reports.append(report)
    del events
    del actual
    for refinement, report in enumerate(reports, 1):
        saved = read(path.with_name(case + f"-reference-{refinement}.json"))
        assert report == saved
        del saved
    maximum, resolution = check_reports(*reports)
    if not helper:
        saved = read(path.with_name(case + ".json"))
        assert maximum == saved["maximum_error_fraction"]
        assert resolution == saved["maximum_reference_resolution_fraction"]
    return dict(
        case=case,
        role="helper" if helper else "mesh",
        maximum_error_fraction=maximum,
        maximum_reference_resolution_fraction=resolution,
        source_geometry_and_topology_are_inputs=True,
        topology_qualified=False,
    )


def reference_domain(provider, case, source, output):
    reports = []
    if case == "unresolved-rank-domain":
        for precision in (100, 160):
            with localcontext() as context:
                context.prec = precision
                report = provider.serial(
                    provider.pinv_reference(
                        [[Decimal(1), Decimal(0)], [Decimal(0), Decimal("1e-18")]]
                    )
                )
            transport.write(output / (case + "-" + str(precision)), report)
            reports.append(report)
        saved = read(source / "mesh-lifecycle/unresolved-rank-domain.json")
        assert saved == dict(primary=reports[0], refined=reports[1])
        assert all(not r["rank_gap_resolved"] for r in reports)
    else:
        assert case == "empty-matrix-domain"
        failure = None
        try:
            provider.matrix([])
        except ValueError as error:
            failure = dict(type=type(error).__name__, message=str(error))
        transport.write(output / case, dict(failure=failure, expected="refused"))
        assert failure is not None
    return dict(
        case=case,
        role="reference_domain",
        outcome="refusal_domain_verified",
        topology_qualified=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "reference"), required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    args = parser.parse_args()
    output = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    row, failure = None, None
    try:
        assert not transport.runtime()["loaded_production_modules"]
        if args.mode == "native":
            from validation.betse import betse_mesh_lifecycle_preparation_native as provider

            row = native_case(
                provider,
                args.source_evidence / "mesh-lifecycle" / (args.case + "-actual.json"),
                output,
            )
        else:
            from validation.betse import betse_mesh_lifecycle_preparation_reference as provider

            if args.case in ("unresolved-rank-domain", "empty-matrix-domain"):
                row = reference_domain(provider, args.case, args.source_evidence, output)
            else:
                row = reference_case(
                    provider,
                    args.source_evidence / "mesh-lifecycle" / (args.case + "-actual.json"),
                    output,
                )
        assert not transport.runtime()["loaded_production_modules"]
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        runtime = transport.runtime()
        transport.write(
            output / "replay-result",
            dict(
                mode=args.mode,
                case=args.case,
                status="failed" if failure else "passed",
                failure=failure,
                row=row,
                production_imports_denied=True,
                loaded_production_modules=runtime.pop("loaded_production_modules"),
                runtime=runtime,
                topology_qualified=False,
                physical_geometry_admitted=False,
                upstream_initial_qualification="19/22 accuracy qualification open",
            ),
        )


if __name__ == "__main__":
    main()
