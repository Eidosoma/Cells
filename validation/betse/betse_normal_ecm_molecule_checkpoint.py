"""Short conditional preparation for the Cells-owned molecule checkpoint boundary.

Actual setup and ownership checks are numerical executions, never metadata
qualification. The supplied INIT/SIM fixtures and their upstream holds remain
unchanged. All requests, returned/failure prefixes and attempts are retained.
"""

import argparse
import json
import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path

import numpy as np

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_lifecycle as leaf
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from cells.processes import betse_normal_ion_join as ions
from validation.betse import betse_normal_current_native as archives
from validation.betse import betse_normal_ecm_molecule_failure_checks as failures
from validation.betse import betse_normal_ecm_molecule_run_lifecycle_fixtures as fixtures


def _retainer(directory, attempts):
    def retain(name, operation, **readers):
        event = dict(operation=name, numerical_work_possible=True, status="attempted")
        attempts.append(event)

        def counted():
            event["operation_status"] = "attempted"
            if name.startswith("actual-call-"):
                event["source_timestep_attempts"] = 1
            try:
                value = operation()
            except BaseException:
                event["operation_status"] = "refused"
                raise
            event["operation_status"] = "returned"
            if name.startswith("actual-call-"):
                event["accepted_timestep_executions"] = 1
            return value

        try:
            result = failures.retained_call(
                counted,
                stage=name,
                readers={k: lambda value=value: value for k, value in readers.items()},
                retain=lambda value: archives.write_archive(directory / name, ions.data(value)),
            )
        except BaseException:
            event["status"] = "refused"
            raise
        event["status"] = "returned"
        return result

    return retain


def prepare_INIT(directory, case, attempts, *, call_limit=None):
    """Produce an actual source-owned entry; never synthesize its receipt."""
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    retain = _retainer(directory, attempts)

    raw = retain("fixture", lambda: fixtures.init_inputs(case))
    if call_limit is not None:
        raw["stop_after_calls"] = call_limit
    declaration = retain("declaration", lambda: leaf.init.bind(raw), raw=raw)
    binding, entry = retain(
        "actual-setup", lambda: leaf.init.initialize(declaration), declaration=declaration
    )
    declared = retain("run-inputs", lambda: fixtures.declaration(case, binding))
    outer = retain("run-binding", lambda: run.bind(declared, binding), declared=declared)
    receipt = retain(
        "actual-entry-receipt",
        lambda: run.entry_receipt(
            outer,
            entry,
            provenance="Actual checkpoint conditional setup return; no receipt as admission",
        ),
        entry=entry,
    )
    parent = retain(
        "run-begin", lambda: run.begin(outer, entry, receipt), entry=entry, receipt=receipt
    )
    return outer, parent


def prepare_SIM(directory, init_binding, init_parent, attempts):
    """Use the existing complete-INIT admission and actual warm transition."""
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    retain = _retainer(directory, attempts)
    complete = retain(
        "actual-complete-INIT",
        lambda: run.complete_INIT(init_binding, init_parent),
        init_binding=init_binding,
        init_parent=init_parent,
    )
    raw = retain(
        "SIM-fixture",
        lambda: fixtures.sim_inputs("zero_INIT_calls", complete.complete_init),
        complete=complete,
    )
    component = retain("SIM-component-binding", lambda: leaf.bind(raw), raw=raw)
    declared = retain("SIM-run-inputs", lambda: fixtures.declaration("zero_INIT_calls", component))
    return retain(
        "actual-INIT-to-SIM",
        lambda: run.transition(
            init_binding,
            init_parent,
            component,
            declared,
            provenance=(
                "Actual existing transition for checkpoint conditional; no synthetic admission"
            ),
        ),
        component=component,
        declared=declared,
        init_parent=init_parent,
    )


def accepted_prefix(directory, binding, parent, attempts, *, calls):
    """A bounded conditional request, not a qualification or source comparison."""
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    retain = _retainer(directory, attempts)
    for index in range(calls):
        prior = parent
        parent, _ = retain(
            "actual-call-" + str(index),
            lambda prior=prior: run.advance(binding, prior),
            parent=prior,
        )
    return parent


def inventory(value):
    types, arrays, unknown = Counter(), Counter(), Counter()
    active = set()

    def visit(obj):
        key = id(obj)
        if key in active:
            raise ValueError("Cyclic runtime state")
        if isinstance(obj, np.ndarray):
            arrays[(obj.dtype.str, obj.ndim, obj.flags.writeable)] += 1
        elif isinstance(obj, np.generic):
            types["numpy.scalar:" + obj.dtype.str] += 1
        elif is_dataclass(obj) or isinstance(obj, tuple) and hasattr(type(obj), "_fields"):
            types[type(obj).__module__ + "." + type(obj).__qualname__] += 1
            active.add(key)
            values = (getattr(obj, f.name) for f in fields(obj)) if is_dataclass(obj) else iter(obj)
            for item in values:
                visit(item)
            active.remove(key)
        elif isinstance(obj, Mapping):
            active.add(key)
            for name, item in obj.items():
                visit(name)
                visit(item)
            active.remove(key)
        elif type(obj) in (tuple, list):
            active.add(key)
            for item in obj:
                visit(item)
            active.remove(key)
        elif type(obj) not in (type(None), str, bool, int, float):
            unknown[type(obj).__module__ + "." + type(obj).__qualname__] += 1

    visit(value)
    return dict(
        records=dict(types), arrays={str(k): v for k, v in arrays.items()}, unknown=dict(unknown)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--save-load", action="store_true")
    parser.add_argument(
        "--case",
        choices=("zero_INIT_calls", "one_INIT_call", "both_disabled"),
        default="zero_INIT_calls",
    )
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    attempts = []
    stage = "upstream_preparation"
    try:
        binding, parent = prepare_INIT(args.output / "preparation", args.case, attempts)
        result = dict(
            status="returned",
            inventory=inventory((binding, parent)),
            phase=run.composition.kind(binding.composition),
            status_owned=parent.status,
            parent_identity=parent.identity,
            accepted_timestep_executions=0,
            upstream_full_qualification="pending",
            scientific_credit=0,
        )
        if args.save_load:
            stage = "checkpoint"
            saved = checkpoint.save_checkpoint(
                args.output / "checkpoint",
                binding,
                parent,
                expected_phase="INIT",
                expected_parent_identity=parent.identity,
            )
            loaded = checkpoint.load_checkpoint(
                args.output / "checkpoint",
                binding=binding,
                expected_phase="INIT",
                expected_parent_identity=parent.identity,
                expected_checkpoint_identity=saved.identity,
                evidence_directory=args.output / "load-evidence",
            )
            result["checkpoint"] = dict(
                identity=saved.identity,
                parent_identity=loaded.parent.identity,
                save_ownership_attempts=saved.verification_attempts,
                load_ownership_attempts=loaded.receipt.verification_attempts,
                exact_graph=checkpoint.codec.fingerprint((binding, parent))
                == checkpoint.codec.fingerprint((loaded.binding, loaded.parent)),
            )
    except BaseException as error:
        result = dict(
            status=stage + "_refusal",
            type=type(error).__name__,
            message=str(error),
            scientific_credit=0,
        )
        raise
    finally:
        result.update(
            attempts=attempts,
            CPU_affinity=sorted(os.sched_getaffinity(0)),
            no_native_checkpoint_parity_claim=True,
        )
        with (args.output / "result.json").open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")


if __name__ == "__main__":
    main()
