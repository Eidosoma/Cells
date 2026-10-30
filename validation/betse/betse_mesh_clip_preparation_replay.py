"""Prepared fresh clipping replay with production imports denied by transport."""

import argparse
import json
import os
import struct
import traceback
from pathlib import Path

# The transport installs both import guards before importing NumPy/wire.
from validation.betse import betse_initial_mesh_preparation_replay as transport
from validation.betse import betse_mesh_clip_preparation_report as branches

np = transport.np
wire = transport.wire
PLAN = (
    Path(__file__).resolve().parents[2]
    / "agent-work/cells-specialist/betse_mesh_clip_preparation_plan.json"
)


def restore(cache):
    """Restore typed declared helper inputs, with bounded original strides."""
    wire.validate(cache)

    def decode(node):
        kind = node["type"]
        if kind == "array":
            values = cache["columns"][node["column"]]
            layout = node["layout"]
            shape, strides = tuple(layout["shape"]), tuple(layout["strides_bytes"])
            if values.size > 262144 or len(shape) > 4 or values.dtype.hasobject:
                raise ValueError("Helper input exceeds bounded numeric wire domain")
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
                raise ValueError("Restored helper layout exceeds bounded storage")
            buffer = np.empty(size, dtype=np.uint8)
            result = np.ndarray(
                shape, dtype=values.dtype, buffer=buffer, offset=offset, strides=strides
            )
            result[...] = values
            assert wire.signature(wire.capture(result)["tree"]) == wire.signature(node)
            return result
        if kind == "numpy_scalar":
            return np.frombuffer(bytes.fromhex(node["bits"]), dtype=np.dtype(node["dtype"]))[0]
        if kind == "float":
            return struct.unpack("<d", bytes.fromhex(node["bits"]))[0]
        if kind == "dict":
            return {decode(k): decode(v) for k, v in node["values"]}
        if kind in ("list", "tuple", "set", "frozenset"):
            cls = {"list": list, "tuple": tuple, "set": set, "frozenset": frozenset}[kind]
            return cls(decode(v) for v in node["values"])
        if kind == "object_array":
            raise ValueError("No object-array helper input is declared")
        return node["value"]

    return decode(cache["tree"])


def retain_native(path, proof):
    columns = {}

    def record(prefix, cache):
        columns.update({prefix + "__" + name: value for name, value in cache["columns"].items()})
        return dict(column_prefix=prefix, tree=cache["tree"])

    value = {
        k: v
        for k, v in proof.items()
        if k not in ("initial_cache", "cache", "events", "helper_result")
    }
    value.update(
        initial_cache=record("initial", proof["initial_cache"]),
        cache=record("final", proof["cache"]),
        helper_result=None
        if proof["helper_result"] is None
        else record("result", proof["helper_result"]),
        events=[
            {
                **{k: v for k, v in e.items() if k != "payload"},
                "payload": record(f"event{e['sequence']}", e["payload"]),
            }
            for e in proof["events"]
        ],
    )
    transport.write(path, value, columns)


def compare_events(actual, archive, saved, saved_archive, proof, *, failed):
    assert len(actual["events"]) == len(saved["events"]) == len(proof["events"])
    for a, b, c in zip(actual["events"], saved["events"], proof["events"], strict=True):
        for key in ("sequence", "kind", "method", "depth"):
            assert a[key] == b[key] == c[key]
        is_failure = failed and a["kind"].endswith("failure")
        transport.compare_cache(
            transport.load_cache(a["payload"], archive, owned=True),
            c["payload"],
            failure=is_failure,
        )
        transport.compare_cache(
            transport.load_cache(b["payload"], saved_archive, owned=False),
            c["payload"],
            failure=is_failure,
        )


def native_case(provider, path, actual, archive, replay_root):
    case = path.stem.removesuffix("-actual")
    saved = json.loads(path.with_name(case + "-native.json").read_text())
    helper = actual.get("classification") == "isolated_manufactured_helper_only"
    constructor_check = None
    if helper:
        parameters = restore(
            transport.load_cache(actual["caches"]["parameters"], archive, owned=True)
        )
        # Isolated helpers have no constructor/RNG draws; the captured full
        # state is an input, without new random-stream qualification credit.
        proof = provider.evaluate(
            {}, (), saved["rng_after_initial"], None, helper=(actual["method"], parameters)
        )
        failed = actual["failure_type"] is not None
    else:
        from validation.betse import betse_initial_mesh_preparation_native as caller_native

        inputs = actual["inputs"]
        caller = caller_native.caller_kwargs(
            inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
        )
        caller_cache = wire.capture(caller["kwargs"])
        transport.write(
            replay_root / (case + "-caller"),
            dict(
                kwargs=caller_cache["tree"],
                caller={k: v for k, v in caller.items() if k != "kwargs"},
            ),
            caller_cache["columns"],
        )
        input_record = json.loads(path.with_name(case + "-input.json").read_text())
        with np.load(path.with_name(case + "-input.npz"), allow_pickle=False) as input_archive:
            constructor_check = transport.load_cache(
                input_record["caches"]["constructor"], input_archive, owned=True
            )
        mask = restore(transport.load_cache(actual["caches"]["mask"], archive, owned=True))
        ids = input_record["initial_request"]["constructor_point_ids"]
        proof = provider.evaluate(caller["kwargs"], ids, caller["rng_before_constructor"], mask)
        failed = actual["state"]["status"] == "retained_source_failure"
    retain_native(replay_root / case, proof)
    if constructor_check is not None:
        transport.compare_cache(constructor_check, caller_cache)
    assert proof["status"] == ("source_failed" if failed else "source_completed")
    if failed:
        expected = actual["failure_type"] if helper else actual["state"]["failure_type"]
        assert proof["failure"]["type"] == saved["failure"]["type"] == expected
    else:
        assert proof["failure"] is None
    with np.load(path.with_name(case + "-native.npz"), allow_pickle=False) as saved_archive:
        compare_events(actual, archive, saved, saved_archive, proof, failed=failed)
        for name in ("initial_cache", "cache"):
            transport.compare_cache(
                transport.load_cache(saved[name], saved_archive, owned=False), proof[name]
            )
        if helper:
            if not failed:
                transport.compare_cache(
                    transport.load_cache(actual["caches"]["result"], archive, owned=True),
                    proof["helper_result"],
                )
                transport.compare_cache(
                    transport.load_cache(saved["helper_result"], saved_archive, owned=False),
                    proof["helper_result"],
                )
        else:
            for actual_name, native_name in (("initial", "initial_cache"), ("final", "cache")):
                transport.compare_cache(
                    transport.load_cache(actual["caches"][actual_name], archive, owned=True),
                    proof[native_name],
                )
            for key in (
                "parent_point_ids",
                "derived_point_ids_before_rebuild",
                "retained_point_ids",
            ):
                assert actual["state"][key] == list(proof[key]) == saved[key]
            assert actual["state"]["stream_after_initial"]["state"] == proof["rng_after_initial"]
            assert actual["state"]["stream_after"]["state"] == proof["rng_after"]
    assert proof["rng_after_initial"] == proof["rng_after"] == saved["rng_after"]
    assert proof["original_global_rng_unchanged"] and not proof["topology_qualified"]
    return dict(
        case=case,
        role="raw_helper" if failed and helper else "helper" if helper else "mesh",
        full_native_typed_trace_exact=True,
        observed_branches=None if helper else branches.branch_counts(path),
        topology_qualified=False,
    )


def fraction(actual, expected, atol):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    assert a.shape == b.shape
    value = float(np.max(abs(a - b) / (np.asarray(atol) + 6e-12 * abs(b)), initial=0))
    assert value <= 1, value
    return value


def geometry_budgets(events, first, second):
    start = next(e["sequence"] for e in events if e["kind"] == "clip_continuation_start")
    by_sequence = {e["sequence"]: e["payload"] for e in events}
    maximum = resolution = 0.0
    for a, b in zip(
        first["source_geometry"]["primitives"], second["source_geometry"]["primitives"], strict=True
    ):
        assert (a["sequence"], a["method"]) == (b["sequence"], b["method"])
        if a["sequence"] <= start:
            continue
        atol = (
            1e-26
            if a["method"] == "area"
            else [1e-27, 1e-26, 1e-27, 1e-27]
            if a["method"] == "quad_circumc"
            else 1e-27
        )
        maximum = max(
            maximum, fraction(by_sequence[a["sequence"]]["result"], a["expected_result"], atol)
        )
        resolution = max(resolution, fraction(a["expected_result"], b["expected_result"], atol))
    for a, b in zip(
        first["source_geometry"]["nearest"], second["source_geometry"]["nearest"], strict=True
    ):
        assert a["sequence"] == b["sequence"]
        if a["sequence"] <= start:
            continue
        payload = by_sequence[a["sequence"]]
        values = np.asarray(payload["result"][0]).ravel().tolist()
        expected = [v for row in a["expected"] for v in row["ranked_distances"]]
        refined = [v for row in b["expected"] for v in row["ranked_distances"]]
        assert [r["exact_tie_candidate_indices"] for r in a["expected"]] == [
            r["exact_tie_candidate_indices"] for r in b["expected"]
        ]
        floor = 2e-14 if np.asarray(payload["data"]).dtype.kind in "iu" else 1e-27
        for value, target, refined_value in zip(values, expected, refined, strict=True):
            if target == "infinity":
                assert np.isinf(value) and refined_value == "infinity"
            else:
                maximum = max(maximum, fraction(value, target, floor))
                resolution = max(resolution, fraction(target, refined_value, floor))
    for a, b in zip(first["mask_queries"], second["mask_queries"], strict=True):
        assert a["sequence"] == b["sequence"]
        if a["within_closed_window"]:
            maximum = max(maximum, fraction(a["observed_value"], a["independent_value"], 2e-14))
            resolution = max(
                resolution, fraction(a["independent_value"], b["independent_value"], 2e-14)
            )
    for a, b in zip(first["helper_diagnostics"], second["helper_diagnostics"], strict=True):
        assert (a["sequence"], a["method"]) == (b["sequence"], b["method"])
        x, y = a["diagnostic"], b["diagnostic"]
        if a["method"] == "intersect_lines" and x["exact_unique"]:
            maximum = max(
                maximum,
                fraction(by_sequence[a["sequence"]]["result"], x["expected_point_m"], 1e-27),
            )
            resolution = max(
                resolution, fraction(x["expected_point_m"], y["expected_point_m"], 1e-27)
            )
        elif a["method"] == "clip_counterclockwise" and x["supported"]:
            maximum = max(
                maximum, fraction(x["source_result_signed_area_m2"], x["signed_area_m2"], 1e-26)
            )
            resolution = max(resolution, fraction(x["signed_area_m2"], y["signed_area_m2"], 1e-26))
    assert resolution <= 0.1
    return maximum, resolution


def reference_case(provider, path, actual, archive, replay_root):
    case = path.stem.removesuffix("-actual")
    helper = actual.get("classification") == "isolated_manufactured_helper_only"
    if helper:
        params_cache = transport.load_cache(actual["caches"]["parameters"], archive, owned=True)
        parameters = wire.plain(params_cache["tree"], params_cache["columns"])
        result_cache = transport.load_cache(actual["caches"]["result"], archive, owned=True)
        observed = wire.plain(result_cache["tree"], result_cache["columns"])
        if actual["failure_type"] is not None:
            if actual["method"] == "intersect_lines":
                diagnostic = provider.helper_report(actual["method"], parameters, None)
            else:
                diagnostic = provider.closed_convex_intersection(
                    parameters["subject_polygon"], parameters["clip_polygon"]
                )
            transport.write(
                replay_root / case,
                dict(
                    diagnostic=diagnostic,
                    source_failure_type=actual["failure_type"],
                    scope="Independent domain diagnostic on retained source failure input",
                    source_failure_relabelled=False,
                    independent_native_failure_generation=False,
                ),
            )
            if actual["method"] == "intersect_lines":
                assert not diagnostic["exact_unique"]
            else:
                assert not diagnostic["supported"]
            return dict(case=case, role="raw_helper", topology_qualified=False)
        reports = []
        for refinement in (1, 2):
            try:
                report = provider.evaluate_helper(
                    actual["method"], parameters, observed, refinement=refinement
                )
            except provider.ReferenceFailure as error:
                transport.write(replay_root / (case + f"-reference-{refinement}"), error.trial)
                raise
            transport.write(replay_root / (case + f"-reference-{refinement}"), report)
            reports.append(report)
        for refinement, report in enumerate(reports, 1):
            assert report == json.loads(
                path.with_name(case + f"-reference-{refinement}.json").read_text()
            )
        a, b = reports[0]["diagnostic"], reports[1]["diagnostic"]
        if actual["method"] == "is_left_of_vector":
            assert bool(observed) == a["exact_strict_side"]
        elif actual["method"] == "intersect_lines":
            fraction(observed, a["expected_point_m"], 1e-27)
            assert fraction(a["expected_point_m"], b["expected_point_m"], 1e-27) <= 0.1
        elif actual["method"] == "clip_counterclockwise":
            fraction(a["source_result_signed_area_m2"], a["signed_area_m2"], 1e-26)
            assert fraction(a["signed_area_m2"], b["signed_area_m2"], 1e-26) <= 0.1
        elif case == "keeper-complement":
            assert a["exact_matching_occurrence_pairs"] == [[0, 0], [2, 1]]
            assert observed[0] == [parameters["pts"][0], parameters["pts"][2]]
            assert observed[1] == [parameters["pts"][1]]
        return dict(case=case, role="helper", topology_qualified=False)
    events = []
    for event in actual["events"]:
        cache = transport.load_cache(event["payload"], archive, owned=True)
        events.append(
            {
                **{k: v for k, v in event.items() if k != "payload"},
                "payload": wire.plain(cache["tree"], cache["columns"]),
            }
        )
    mask_cache = transport.load_cache(actual["caches"]["mask"], archive, owned=True)
    mask = wire.plain(mask_cache["tree"], mask_cache["columns"])
    reports = []
    for refinement in (1, 2):
        try:
            report = provider.evaluate(events, mask, refinement=refinement)
        except provider.ReferenceFailure as error:
            transport.write(replay_root / (case + f"-reference-{refinement}"), error.trial)
            raise
        transport.write(replay_root / (case + f"-reference-{refinement}"), report)
        reports.append(report)
    for refinement, report in enumerate(reports, 1):
        assert report == json.loads(
            path.with_name(case + f"-reference-{refinement}.json").read_text()
        )
    maximum, resolution = geometry_budgets(events, *reports)
    saved = json.loads(path.with_name(case + ".json").read_text())
    assert (
        maximum == saved["maximum_error_fraction"]
        and resolution == saved["maximum_reference_resolution_fraction"]
    )
    return dict(
        case=case,
        role="mesh",
        observed_branches=branches.branch_counts(path),
        maximum_error_fraction=maximum,
        maximum_reference_resolution_fraction=resolution,
        topology_qualified=False,
        outside_window_native_only_queries=sum(
            not r["within_closed_window"] for r in reports[0]["mask_queries"]
        ),
    )


def reference_domains(provider, root, replay_root, domains):
    rows = []
    for item in domains:
        reports = []
        for refinement in (1, 2) if item["expected"] == "complete" else (1,):
            failure = None
            try:
                report = provider.evaluate(item["events"], item["mask"], refinement=refinement)
            except provider.ReferenceFailure as error:
                failure, report = error, error.trial
            transport.write(replay_root / (item["case"] + f"-{refinement}"), report)
            assert (failure is None) == (item["expected"] == "complete")
            saved = (
                item["saved"]
                if item["expected"] == "refused"
                else item["saved"] + f"-reference-{refinement}"
            )
            assert report == json.loads((root / (saved + ".json")).read_text())
            reports.append(report)
        rows.append(
            dict(
                case=item["case"],
                expected=item["expected"],
                outcome="verified_saved_reference_domain",
            )
        )
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "reference"), required=True)
    args = parser.parse_args()
    evidence = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    root, replay_root = evidence / "mesh-clip", evidence / (args.mode + "-fresh")
    rows, domains, failure = [], [], None
    try:
        replay_root.mkdir(exist_ok=False)
        assert not transport.runtime()["loaded_production_modules"]
        plan = json.loads(PLAN.read_text())
        roster = plan["case_roster"]
        expected = set(roster["mesh"] + roster["helper"] + roster["raw_helper"])
        paths = {p.stem.removesuffix("-actual"): p for p in root.glob("*-actual.json")}
        assert set(paths) == expected and len(expected) == 21
        if args.mode == "native":
            from validation.betse import betse_mesh_clip_preparation_native as provider

            evaluate = native_case
        else:
            from validation.betse import betse_mesh_clip_preparation_reference as provider

            evaluate = reference_case
        for case in sorted(paths):
            path = paths[case]
            actual = json.loads(path.read_text())
            with np.load(path.with_suffix(".npz"), allow_pickle=False) as archive:
                rows.append(evaluate(provider, path, actual, archive, replay_root))
        for role in ("mesh", "helper", "raw_helper"):
            assert {r["case"] for r in rows if r["role"] == role} == set(roster[role])
        if args.mode == "reference":
            domains = reference_domains(
                provider, root, replay_root, plan["reference_domain_inputs"]
            )
            assert {r["case"] for r in domains} == {
                r["case"] for r in plan["reference_domain_inputs"]
            }
        witness = json.loads((root / "keeper-complement-witness.json").read_text())
        assert witness["source_result_order"] == ["matched_discarded", "unmatched_kept"]
        assert witness["keeper_indices"] == [1] and witness["matched_indices"] == [0, 2]
        assert not transport.runtime()["loaded_production_modules"]
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        inventory = transport.runtime()
        report = dict(
            mode=args.mode,
            status="failed" if failure else "passed",
            failure=failure,
            cases=rows,
            reference_domain_cases=domains,
            complete_mesh_cases=sum(r["role"] == "mesh" for r in rows),
            manufactured_helper_cases=sum(r["role"] == "helper" for r in rows),
            raw_helper_failures=sum(r["role"] == "raw_helper" for r in rows),
            production_imports_denied=True,
            loaded_production_modules=inventory.pop("loaded_production_modules"),
            runtime=inventory,
            topology_qualified=False,
            downstream_geometry_admitted=False,
            upstream_accuracy_qualification="open",
            initial_mesh_qualification_credit=False,
            source_predicates_unchanged=True,
            outside_window_independent_mask_claim=False,
        )
        transport.write(evidence / (args.mode + "-replay"), report)
    print(
        json.dumps(
            dict(mode=args.mode, status="passed", mesh_cases=12, helper_cases=7, raw_helpers=2)
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
