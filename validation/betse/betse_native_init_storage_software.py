"""Immutable CPU6 native-blocked controls for the INIT storage boundary."""

import argparse
import importlib
import json
import os
import resource
import sys
from pathlib import Path
from types import CodeType, FrameType, FunctionType, ModuleType, SimpleNamespace

from validation.betse import betse_native_init_tissue_dynamics_software as inherited

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_storage.py"
LITERAL = "src/cells/processes/betse_native_init_storage_source.py"
TEST = "tests/unit/test_betse_native_init_storage.py"
FILE = "validation/betse/betse_native_init_storage_software.py"
MODULE = "validation.betse.betse_native_init_storage_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_STORAGE_SOFTWARE_RELEASED"
ISSUED_CHAIN_TEST = "test_issued_dynamics_to_storage_public_chain"
ISSUED_CHAIN_SECONDS = 7200
ISSUED_CHAIN_RELEASE = "BETSE_NATIVE_INIT_STORAGE_ISSUED_CHAIN_SOFTWARE_RELEASED"
OWNED = (SOURCE, LITERAL, TEST, FILE)
snapshot, base = inherited.snapshot, inherited.base
NATIVE_ROOT = inherited.NATIVE_ROOT
FORBIDDEN_MODULES = inherited.FORBIDDEN_MODULES | frozenset(
    ("cells.processes.betse_native_init_storage_source",)
)
_RAW_FAILURES = ()
_MODEL_RUN_BINDING = None


def _issued_model_driver(frame):
    """Only the original transport frame with a genuinely issued test parent.

    Numerical acquisition remains forbidden. The selected body is explicitly
    the frozen synthetic fixture's method, never an original BETSE body.
    """
    if (
        os.environ.get(ISSUED_CHAIN_RELEASE) != "1"
        or type(frame) is not FrameType
        or _MODEL_RUN_BINDING is None
    ):
        return False
    module = sys.modules.get("cells.processes.betse_native_init_storage")
    function, code, namespace = _MODEL_RUN_BINDING
    if (
        type(module) is not ModuleType
        or vars(module) is not namespace
        or module._run is not function
        or function.__code__ is not code
        or frame.f_code is not code
        or frame.f_globals is not namespace
    ):
        return False
    context = frame.f_locals.get("context")
    if (
        type(context) is not SimpleNamespace
        or not module._ACTIVE
        or module._ACTIVE[-1] is not context
    ):
        return False
    request = context.request
    if (
        type(request) is not module.Request
        or module._REQUESTS.get(request) is not context.refs
        or module._CONSUMED.get(request) is not context
        or module._RETIRED.get(request.dynamics_owner) is not context
        or type(request.dynamics_owner) is not module.previous.DynamicsOwner
        or module.previous._STORAGE_FORWARDED.get(request.dynamics_owner) is not context
        or frame.f_back is None
        or frame.f_back.f_code is not module.prepare.__code__
        or frame.f_back.f_globals is not namespace
        or frame.f_back.f_locals.get("context") is not context
    ):
        return False
    issued = module.previous._ISSUED.get(request.dynamics_owner)
    method, original = context.method, context.original
    return (
        issued is not None
        and issued[0] is context.parent
        and issued[1] is context.refs[1]
        and context.phase is context.parent.phase
        and context.sim is context.parent.sim
        and context.cells is context.parent.cells
        and context.p is context.parent.p
        and type(method) is FunctionType
        and type(original) is FunctionType
        and original is context.parent.init_parent.factories["Simulator"].clear_storage
        and method.__code__ is original.__code__
        and method.__globals__ is context.namespace
        and method.__code__.co_filename
        == str(ROOT / "tests/unit/test_betse_native_init_dynamics_completion.py")
        and method.__code__.co_qualname == "issued_synthetic_completion.<locals>.clear_storage"
    )


_MODEL_DRIVER_FUNCTION = _issued_model_driver
_MODEL_DRIVER_CODE = _issued_model_driver.__code__


def is_forbidden_frame(frame):
    name = frame.f_globals.get("__name__", "")
    if name == "cells.processes.betse_native_init_storage" and frame.f_code.co_name == "_run":
        return (
            _MODEL_RUN_BINDING is None
            or _issued_model_driver is not _MODEL_DRIVER_FUNCTION
            or _issued_model_driver.__code__ is not _MODEL_DRIVER_CODE
            or _issued_model_driver.__globals__ is not globals()
            or _issued_model_driver.__defaults__ is not None
            or _issued_model_driver.__kwdefaults__ is not None
            or _issued_model_driver.__closure__ is not None
            or not _issued_model_driver(frame)
        )
    return (
        name in FORBIDDEN_MODULES
        or (
            name == "cells.processes.betse_native_init_storage"
            and frame.f_code.co_name in ("_namespace", "_run")
        )
        or inherited.is_forbidden_frame(frame)
    )


def _scope():
    return dict(
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
        __file__=__file__,
    )


def _integration_policy(select, seconds):
    if type(select) is not str or not select:
        raise ValueError("Explicit literal software item selector required")
    if type(seconds) is not int or seconds not in (480, ISSUED_CHAIN_SECONDS):
        raise ValueError("Only ordinary480 or explicit issued-chain7200 software mode")
    if (seconds == ISSUED_CHAIN_SECONDS) != (select == ISSUED_CHAIN_TEST):
        raise ValueError("Long software mode permits exactly the one named issued-chain control")
    return seconds


def prepare(output, select, *, issued_chain_seconds=480):
    seconds = _integration_policy(select, issued_chain_seconds)
    value = FunctionType(inherited.inherited.reuse.prepare.__code__, _scope())(output, select)
    if seconds != 480:
        inputs = json.loads((output / "inputs.json").read_text())
        snapshot.write_json(output / "ordinary-software-inputs.json", inputs)
        inputs.update(
            wall_seconds=seconds,
            software_integration_envelope=dict(
                seconds=seconds,
                default_seconds=480,
                single_named_pilot=select,
                native_bodies_operators_RNG_reference_and_science_held=True,
                calls_and_attempts_are_not_independent_cases=True,
            ),
        )
        pending = output / "issued-chain-inputs.json.pending"
        snapshot.write_json(pending, inputs)
        os.replace(pending, output / "inputs.json")
    return value


def child(output, select):
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs.get("software_release_requested") is not True or inputs.get("selection") != select:
        raise ValueError("Exact prepared native-blocked software release/selector required")
    seconds = _integration_policy(select, inputs.get("wall_seconds"))
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
            raise ValueError("Exact issued-chain software preparation/resource limits required")
        os.environ[ISSUED_CHAIN_RELEASE] = "1"
    else:
        os.environ.pop(ISSUED_CHAIN_RELEASE, None)
    inherited._external_producers(inputs, loaded=False)
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for path in OWNED:
        if (
            snapshot.digest(ROOT / path) != inputs["owned_files"][path]
            or inputs["owned_files"][path] != manifest["files"][path]["sha256"]
        ):
            raise ValueError("Actual immutable storage producer required")
    stage = importlib.import_module("cells.processes.betse_native_init_storage")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual verified frozen storage definitions required")
    fixture_name = "tests.unit.test_betse_native_init_dynamics_completion"
    fixture = importlib.import_module(fixture_name)
    fixture_path = "tests/unit/test_betse_native_init_dynamics_completion.py"
    if (
        Path(fixture.__file__).resolve() != ROOT / fixture_path
        or snapshot.digest(ROOT / fixture_path) != manifest["files"][fixture_path]["sha256"]
    ):
        raise ValueError("Exact frozen readonly public-issuer fixture definitions required")
    if seconds != 480:
        compiled = compile(
            (ROOT / SOURCE).read_bytes(), str(ROOT / SOURCE), "exec", dont_inherit=True
        )
        expected = next(
            c for c in compiled.co_consts if type(c) is CodeType and c.co_name == "_run"
        )
        if stage._run.__code__ != expected or stage._run.__globals__ is not vars(stage):
            raise ValueError("Exact original nonnumerical storage transport required")
        global _MODEL_RUN_BINDING
        _MODEL_RUN_BINDING = (stage._run, stage._run.__code__, vars(stage))
    snapshot.write_json(output / "storage-source-plan.json", stage.source_plan())
    original = inherited.inherited
    namespace = dict(
        vars(original), **_scope(), _scope=_scope, _integration_policy=_integration_policy
    )
    required = sys.getprofile(), sys.gettrace()
    try:
        value = FunctionType(original.child.__code__, namespace)(output, select)
        if sys.getprofile() is not required[0] or sys.gettrace() is not required[1]:
            raise ValueError("Exact inherited hooks required before final producer audit")
        snapshot.write_json(
            output / "storage-external-producers.json",
            inherited._external_producers(inputs, loaded=True),
        )
        return value
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
        _integration_policy(args.select, args.issued_chain_seconds)
        if args.child is not None:
            inputs = json.loads((output / "inputs.json").read_text())
            if inputs.get("wall_seconds") != args.issued_chain_seconds:
                raise ValueError("Child wall mode must equal its exact prepared inputs")
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(output, args.select)
        if os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit blocked-software release required")
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return prepare(output, args.select, issued_chain_seconds=args.issued_chain_seconds)
    except BaseException as primary:
        try:
            inherited.inherited.base.reuse.reuse._main_failure(output, primary)
        except BaseException as capture:
            global _RAW_FAILURES
            _RAW_FAILURES += ((primary, capture, output),)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
