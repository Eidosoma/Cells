"""Fresh independent conditionals; exact frozen event and molecule equations."""

import copy
from decimal import localcontext

from validation.betse import betse_normal_ecm_event_join_reference as event
from validation.betse import betse_normal_ecm_molecule_lifecycle_reference as molecule


def evaluate(inputs, *, refinement, retain):
    if refinement not in (1, 2):
        raise ValueError("Require predeclared Decimal100/160 form")
    mode = inputs.get("mode")
    if mode == "events":
        result = event.event_equations(inputs, refinement=refinement)
        retain("actual-SIM-event-conditional", result)
    elif mode == "entry_controls":
        with localcontext() as context:
            context.prec = 100 if refinement == 1 else 160
            result = dict(
                mode=mode,
                controls={
                    key: [1.0] * inputs["membranes"] if inputs["global_options"][key] != 0 else 1
                    for key in ("gj_block", "NaKATP_block")
                },
                decimal_precision=context.prec,
                carried_reference_forms=0,
                fresh_conditional_reference=True,
                physical_global_conservation_credit=False,
            )
            retain("actual-SIM-control-entry-conditional", copy.deepcopy(result))
    else:
        return molecule.evaluate(inputs, refinement=refinement, retain=retain)
    result.update(source_phase="SIM", legacy_run_sim=True, independently_carried_trajectory=False)
    return result


def main():
    import argparse
    import builtins
    import hashlib
    import importlib.abc
    import json
    import sys
    from pathlib import Path

    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_ecm_init_phase_capture import record_failure

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "scipy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent event/mechanics reference import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError(
                    "Independent event/mechanics reference import denied: " + fullname
                )

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    retained = args.output.parent / ("raw-reference-" + str(args.refinement))
    completed_retained = []

    def retain(name, value):
        retained.mkdir(parents=True, exist_ok=True)
        with (retained / (name + ".json")).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
        completed_retained.append(name)

    def file_record(path):
        if not path.exists():
            return dict(path=str(path), present=False)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Failure evidence must be a regular file: " + str(path))
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        return dict(path=str(path), present=True, bytes=path.stat().st_size, sha256=digest)

    def raw_records():
        return dict(
            completed_names=list(completed_retained),
            files=[file_record(path) for path in sorted(retained.iterdir())]
            if retained.exists()
            else [],
            incomplete_files_are_not_completed_forms=True,
        )

    def retain_failure(payload):
        payload.update(worker_kind="independent_INIT_reference", scientific_credit=0)
        failure_path = args.output.with_name(args.output.name + ".failure.json")
        with failure_path.open("x") as stream:
            json.dump(payload, stream, indent=2, allow_nan=False)
            stream.write("\n")

    stage = "input"
    try:
        incoming = json.loads(args.inputs.read_text())
        stage = "evaluate"
        result = evaluate(incoming, refinement=args.refinement, retain=retain)
        stage = "runtime"
        loaded = [n for n in sys.modules if n.split(".")[0] in blocked]
        assert not loaded
        result.update(
            production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
        )
        stage = "result_write"
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except Exception as error:
        record_failure(
            error,
            stage=stage,
            readers=dict(
                inputs=lambda: file_record(args.inputs),
                output=lambda: file_record(args.output),
                refinement=lambda: args.refinement,
                raw_reference_records=raw_records,
                runtime=inventory,
                loaded_production_modules=lambda: sorted(
                    n for n in sys.modules if n.split(".")[0] in blocked
                ),
            ),
            retain=retain_failure,
        )
        raise


if __name__ == "__main__":
    main()
