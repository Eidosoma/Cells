"""Fresh independent lanes; deny production before loading any provider."""

import argparse
import os
import traceback
from pathlib import Path

from validation.geometry import stable_initial_mesh_preparation_runtime as runtime


def conditional_lane(case, actual, archive, source, out):
    from validation.geometry import stable_initial_mesh_preparation_io as transport
    from validation.geometry import stable_initial_mesh_preparation_native as provider

    native_request, inputs = actual["request"]["native_request"], actual["inputs"]
    kwargs_cache = transport.load_cache(actual["request_cache"], archive)
    if native_request["origin"] == "owned_image_prelude":
        caller = provider.native.caller_kwargs(
            inputs["seed_recipe"], inputs["seed_stream_before"], inputs["controls"]
        )
        kwargs, before = caller["kwargs"], caller["rng_before_constructor"]
        captured = transport.wire.capture(kwargs)
        transport.write(
            out / (case + "-source-caller"),
            dict(
                caller={k: v for k, v in caller.items() if k != "kwargs"}, kwargs=captured["tree"]
            ),
            captured["columns"],
        )
    else:
        assert native_request["origin"] == "reused_fixed_B09"
        import numpy as np

        raw = inputs["input"]
        kwargs = dict(
            raw["mesh"],
            seed_points=None
            if raw["seed_points_m"] is None
            else np.asarray(raw["seed_points_m"], dtype=np.float64),
        )
        before = inputs["rng_before"]
        captured = transport.wire.capture(kwargs)
    transport.constructor_equal(kwargs_cache, captured)
    assert before == native_request["stream_before"]["state"]
    tape = provider.tape_from_events(transport.load_events(actual, archive))
    proof = provider.evaluate(kwargs, native_request["constructor_point_ids"], before, tape)
    transport.retain_native(out / (case + "-conditional-native"), proof)
    row = transport.compare_native(actual, archive, proof)
    import numpy as np

    saved = transport.read(source / (case + "-conditional-native.json"))
    with np.load(source / (case + "-conditional-native.npz"), allow_pickle=False) as saved_archive:
        for key in ("constructed_cache", "cache"):
            transport.equal(
                transport.load_cache(saved[key], saved_archive, owned=False), proof[key]
            )
        assert len(saved["events"]) == len(proof["events"])
        for a, b in zip(saved["events"], proof["events"], strict=True):
            for key in ("sequence", "kind", "method", "depth"):
                assert a[key] == b[key]
            transport.equal(
                transport.load_cache(a["payload"], saved_archive, owned=False),
                b["payload"],
                failure=a["kind"].endswith("failure"),
            )
    return dict(case=case, lane="conditional-source", **row)


def geometry_lane(case, actual, archive, source, out):
    from validation.geometry import stable_initial_mesh_preparation_io as transport
    from validation.geometry import stable_initial_mesh_preparation_reference as provider

    final = transport.load_cache(actual["final"], archive)
    final = transport.wire.plain(final["tree"], final["columns"])
    events = transport.plain_events(transport.load_events(actual, archive))
    reports = []
    for refinement in (1, 2):
        report = provider.evaluate(
            final, events, completed=actual["state"]["pre_mesh_completed"], refinement=refinement
        )
        transport.write(out / (case + f"-reference-{refinement}"), report)
        assert report == transport.read(source / (case + f"-reference-{refinement}.json"))
        reports.append(report)
    repairs = provider.compare_repairs(*reports)
    whole_mesh = provider.compare_whole_mesh(*reports)
    row = dict(
        case=case,
        lane="geometry",
        primitive_comparisons=repairs,
        whole_mesh=whole_mesh,
        physical_geometry_admitted=False,
        topology_qualified=False,
        exact_native_arithmetic_equivalence=False,
    )
    # Retain the complete independent verdict even when the unchanged native
    # mapping or quad arithmetic prevents whole-mesh acceptance.
    transport.write(out / (case + "-geometry-verdict"), row)
    if actual["state"]["pre_mesh_completed"]:
        assert whole_mesh["whole_mesh_passed"], whole_mesh
    else:
        assert whole_mesh["partial_failure_preserved"]
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--lane", required=True, choices=("conditional-source", "geometry"))
    parser.add_argument("--source-evidence", required=True, type=Path)
    args = parser.parse_args()
    runtime.deny_production(extra=("PIL", "scipy") if args.lane == "geometry" else ("PIL",))
    import numpy as np

    from validation.geometry import stable_initial_mesh_preparation_io as transport

    source = args.source_evidence / "stable-initial-mesh"
    output = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    failure, row = None, None
    try:
        actual = transport.read(source / (args.case + "-actual.json"))
        assert actual["case"] == args.case
        with np.load(source / (args.case + "-actual.npz"), allow_pickle=False) as archive:
            function = conditional_lane if args.lane == "conditional-source" else geometry_lane
            row = function(args.case, actual, archive, source, output)
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        captured = runtime.capture()
        assert not captured["denied_production_modules_loaded"]
        if args.lane == "geometry":
            assert not any(
                name.split(".")[0] in {"scipy", "PIL"}
                for name in captured["scientific_modules_loaded"]
            )
        transport.write(
            output / "replay-result",
            dict(
                status="failed" if failure else "passed",
                failure=failure,
                case=args.case,
                lane=args.lane,
                row=row,
                runtime=captured,
                production_imports_denied=True,
                exact_native_arithmetic_equivalence=False,
                physical_geometry_admitted=False,
                topology_qualified=False,
                source_actual_sha256=transport.sha(source / (args.case + "-actual.json")),
                source_arrays_sha256=transport.sha(source / (args.case + "-actual.npz")),
            ),
        )


if __name__ == "__main__":
    main()
