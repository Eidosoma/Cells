"""Immutable CPU6 blocked software controls; no original first-step execution."""

import argparse
import importlib
import json
import os
import resource
import sys
from pathlib import Path
from types import CodeType, FrameType, FunctionType, ModuleType, SimpleNamespace

from validation.betse import betse_native_init_storage_software as inherited
from validation.betse import betse_native_world_phase_construction_software as reporting

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_first_step.py"
LITERAL = "src/cells/processes/betse_native_init_first_step_source.py"
TEST = "tests/unit/test_betse_native_init_first_step.py"
FILE = "validation/betse/betse_native_init_first_step_software.py"
MODULE = "validation.betse.betse_native_init_first_step_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_FIRST_STEP_SOFTWARE_RELEASED"
ISSUED_CHAIN_TEST = "test_first_step_issued_enabled_network_full_handoff"
ISSUED_CHAIN_SECONDS = 7200
ISSUED_CHAIN_RELEASE = "BETSE_NATIVE_INIT_FIRST_STEP_ISSUED_CHAIN_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, base = inherited.snapshot, inherited.base
NATIVE_ROOT = inherited.NATIVE_ROOT
FORBIDDEN_MODULES = inherited.FORBIDDEN_MODULES | frozenset(
    ("cells.processes.betse_native_init_first_step_source",)
)
_RAW_FAILURES = ()
_MODEL_RUN_BINDINGS = None
_REPORTS_BASE = reporting.Reports
_SELECT_BASE = reporting.reuse.select_items


def _select_items(items, select):
    if select != ISSUED_CHAIN_TEST:
        return _SELECT_BASE(items, select)
    selected, removed = [], []
    for item in items:
        if item.name == ISSUED_CHAIN_TEST and item.originalname == ISSUED_CHAIN_TEST:
            selected.append(item)
        else:
            removed.append(item)
    if len(selected) != 1:
        raise ValueError("Exactly one unparametrized issued-chain item is required")
    return selected, removed


class Reports(_REPORTS_BASE):
    def pytest_collection_modifyitems(self, config, items):
        selected, removed = _select_items(items, self.select)
        snapshot.write_json(
            self.output / "selection.json",
            dict(
                matching=(
                    "exact item.name and originalname, one item only"
                    if self.select == ISSUED_CHAIN_TEST
                    else "literal item.name only"
                ),
                selector=self.select,
                selected=[item.name for item in selected],
                deselected=[item.name for item in removed],
            ),
        )
        items[:] = selected
        if removed:
            config.hook.pytest_deselected(items=removed)


def _issued_model_driver(frame):
    """Only exact frozen drivers with real public pending owner/lease chains."""
    if (
        os.environ.get(ISSUED_CHAIN_RELEASE) != "1"
        or type(frame) is not FrameType
        or _MODEL_RUN_BINDINGS is None
    ):
        return False
    selected = next((row for row in _MODEL_RUN_BINDINGS if frame.f_code is row[2]), None)
    if selected is None:
        return False
    name, function, code, namespace = selected
    module = sys.modules.get(name)
    if (
        type(module) is not ModuleType
        or vars(module) is not namespace
        or vars(module).get("_run") is not function
        or function.__code__ is not code
        or frame.f_globals is not namespace
    ):
        return False
    context = frame.f_locals.get("context")
    if (
        type(context) is not SimpleNamespace
        or not module._ACTIVE
        or module._ACTIVE[-1] is not context
        or frame.f_back is None
        or frame.f_back.f_code is not module.prepare.__code__
        or frame.f_back.f_globals is not namespace
        or frame.f_back.f_locals.get("context") is not context
    ):
        return False
    request = context.request
    if (
        type(request) is not module.Request
        or module._REQUESTS.get(request) is not context.refs
        or module._CONSUMED.get(request) is not context
    ):
        return False
    if name.endswith("_storage"):
        owner, parent = request.dynamics_owner, context.parent
        actual = module.previous
        forwarded = actual._STORAGE_FORWARDED
        owner_type = actual.DynamicsOwner
        methods = (context.method, context.original)
    elif name.endswith("_electrical"):
        owner, parent = request.storage_owner, context.parent
        actual = module.storage
        forwarded = actual._ELECTRICAL_FORWARDED
        owner_type = actual.StorageOwner
        methods = (*context.methods.values(), *context.originals.values())
    else:
        owner, parent = request.electrical_owner, context.electrical_parent
        actual = module.previous
        forwarded = actual._FORWARDED
        owner_type = actual.ElectricalOwner
        methods = (*context.methods.values(), *context.originals.values())
    if (
        type(owner) is not owner_type
        or module._RETIRED.get(owner) is not context
        or forwarded.get(owner) is not context
        or actual._ISSUED.get(owner, (None,))[0] is not parent
    ):
        return False
    fixture_modules = frozenset(
        (
            "tests.unit.test_betse_native_init_first_step",
            "tests.unit.test_betse_native_init_storage",
            "tests.unit.test_betse_native_init_dynamics_completion",
            "tests.unit.test_betse_native_init_retained_world",
        )
    )
    return bool(methods) and all(
        type(fn) is FunctionType
        and fn.__globals__.get("__name__") in fixture_modules
        and not fn.__code__.co_filename.startswith(str(NATIVE_ROOT) + os.sep)
        for fn in methods
    )


def is_forbidden_frame(frame):
    name = frame.f_globals.get("__name__")
    drivers = frozenset(
        (
            "cells.processes.betse_native_init_storage",
            "cells.processes.betse_native_init_electrical",
            "cells.processes.betse_native_init_first_step",
        )
    )
    if name in drivers and frame.f_code.co_name == "_run":
        return not _issued_model_driver(frame)
    return (
        frame.f_globals.get("__name__") in FORBIDDEN_MODULES
        or frame.f_globals.get("__name__") == "cells.processes.betse_native_init_first_step"
        and frame.f_code.co_name in ("_namespace", "_run")
        or inherited.is_forbidden_frame(frame)
    )


def _scope():
    result = dict(
        inherited._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        OWNED=OWNED,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
        is_forbidden_frame=is_forbidden_frame,
        Reports=Reports,
        __file__=__file__,
    )
    # The reused core child creates another namespace from base.reuse. Carry
    # the reporter through that actual seam instead of changing the shared
    # module or merely replacing an unused outer Reports name.
    original = result["base"]
    if original.reuse is not reporting:
        raise ValueError("Exact existing core/reporter namespace relationship required")
    result["base"] = SimpleNamespace(
        **dict(vars(original), reuse=SimpleNamespace(**dict(vars(reporting), Reports=Reports)))
    )
    return result


def _integration_policy(select, seconds):
    if (
        type(select) is not str
        or not select
        or type(seconds) is not int
        or seconds not in (480, ISSUED_CHAIN_SECONDS)
    ):
        raise ValueError(
            "Explicit ordinary480 or single named issued-chain7200 software mode required"
        )
    if (seconds == ISSUED_CHAIN_SECONDS) != (select == ISSUED_CHAIN_TEST):
        raise ValueError("Only the exact issued-chain item can use the long software envelope")
    return seconds


def prepare(output, select, *, issued_chain_seconds=480):
    namespace = dict(vars(inherited))
    namespace.update(_scope())
    namespace.update(
        inherited=inherited.inherited,
        _scope=_scope,
        _integration_policy=_integration_policy,
        ISSUED_CHAIN_TEST=ISSUED_CHAIN_TEST,
        ISSUED_CHAIN_SECONDS=ISSUED_CHAIN_SECONDS,
    )
    return FunctionType(inherited.prepare.__code__, namespace)(
        output, select, issued_chain_seconds=issued_chain_seconds
    )


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    seconds = _integration_policy(select, inputs.get("wall_seconds"))
    if inputs.get("software_release_requested") is not True or inputs.get("selection") != select:
        raise ValueError("Exact prepared blocked-software selector required")
    if seconds != 480:
        policy = inputs.get("software_integration_envelope", {})
        if (
            policy.get("seconds") != seconds
            or policy.get("single_named_pilot") != ISSUED_CHAIN_TEST
            or policy.get("native_bodies_operators_RNG_reference_and_science_held") is not True
            or inputs.get("cpu") != 6
            or inputs.get("threads") != 1
            or inputs.get("software_bytes") != 2**30
            or inputs.get("reserve_bytes") != 8 * 2**30
        ):
            raise ValueError("Exact issued-chain software policy/resource inputs required")
        os.environ[ISSUED_CHAIN_RELEASE] = "1"
    else:
        os.environ.pop(ISSUED_CHAIN_RELEASE, None)
    inherited.inherited._external_producers(inputs, loaded=False)
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if (
            snapshot.digest(ROOT / name) != inputs["owned_files"][name]
            or manifest["files"][name]["sha256"] != inputs["owned_files"][name]
        ):
            raise ValueError("Exact immutable first-step source required")
    stage = importlib.import_module("cells.processes.betse_native_init_first_step")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen first-step definitions required")
    if seconds != 480:
        bindings = []
        for module in (stage.previous.storage, stage.previous, stage):
            path = Path(module.__file__)
            relative = str(path.relative_to(ROOT))
            if snapshot.digest(path) != manifest["files"][relative]["sha256"]:
                raise ValueError("Exact frozen public driver producer required")
            compiled = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
            expected = next(
                value
                for value in compiled.co_consts
                if type(value) is CodeType and value.co_name == "_run"
            )
            if module._run.__code__ != expected or module._run.__globals__ is not vars(module):
                raise ValueError("Original nonnumerical driver code/namespace required")
            bindings.append((module.__name__, module._run, module._run.__code__, vars(module)))
        global _MODEL_RUN_BINDINGS
        _MODEL_RUN_BINDINGS = tuple(bindings)
    snapshot.write_json(output / "first-step-source-plan.json", stage.source_plan())
    original = inherited.inherited.inherited
    namespace = dict(
        vars(original), **_scope(), _scope=_scope, _integration_policy=_integration_policy
    )
    try:
        result = FunctionType(original.child.__code__, namespace)(output, select)
        snapshot.write_json(
            output / "first-step-external-producers.json",
            inherited.inherited._external_producers(inputs, loaded=True),
        )
        return result
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--child", type=Path)
    parser.add_argument("--select", required=True)
    parser.add_argument("--issued-chain-seconds", type=int, default=480)
    args = parser.parse_args()
    output = args.child if args.child is not None else args.prepare
    try:
        if args.child is not None:
            inputs = json.loads((output / "inputs.json").read_text())
            if inputs.get("wall_seconds") != args.issued_chain_seconds:
                raise ValueError("Child mode must equal immutable preparation inputs")
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(output, args.select)
        if os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit blocked-software release required")
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return prepare(output, args.select, issued_chain_seconds=args.issued_chain_seconds)
    except BaseException as primary:
        try:
            inherited.inherited.inherited.base.reuse.reuse._main_failure(output, primary)
        except BaseException as capture:
            global _RAW_FAILURES
            _RAW_FAILURES += ((primary, capture, output),)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
