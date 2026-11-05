"""CPU7 closed synthetic issued-terminal controls; all native science stays blocked."""

import argparse
import hashlib
import importlib
import json
import os
import resource
import sys
from pathlib import Path
from types import FrameType, FunctionType, ModuleType, SimpleNamespace

from validation.betse import betse_native_init_short_history_software as prior
from validation.betse import betse_native_init_terminal_software as metadata

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_terminal.py"
TEST = "tests/unit/test_betse_native_init_terminal_issued.py"
FILE = "validation/betse/betse_native_init_terminal_issued_software.py"
MODULE = "validation.betse.betse_native_init_terminal_issued_software"
LITERAL = prior.LITERAL
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_TERMINAL_ISSUED_SOFTWARE_RELEASED"
ISSUED_RELEASE = "BETSE_NATIVE_INIT_TERMINAL_ISSUED_CASE_RELEASED"
REPORTER_PROBE_RELEASE = "BETSE_NATIVE_INIT_TERMINAL_REPORTER_PROBE_RELEASED"
REPORTER_PROBE = "test_terminal_issued_reporter_refusal_probe"
ISSUED_CASES = (
    "test_terminal_issued_value_only",
    "test_terminal_issued_retained_flux",
    "test_terminal_issued_mid_failure_value_only",
    "test_terminal_issued_mid_failure_retained_flux",
)
DEPENDENCIES = tuple(
    dict.fromkeys(
        (
            *prior.DEPENDENCIES,
            "src/cells/processes/betse_native_init_terminal_molecules.py",
            "src/cells/processes/betse_native_init_short_history.py",
            "tests/unit/test_betse_native_init_short_history.py",
        )
    )
)
OWNED = (SOURCE, LITERAL, TEST, FILE, *DEPENDENCIES)
snapshot, guard, compact_error = prior.snapshot, prior.guard, prior.compact_error
base = prior.base
FORBIDDEN_MODULES, NATIVE_ROOT = prior.FORBIDDEN_MODULES, prior.NATIVE_ROOT
_RAW_FAILURES = ()


def _cpu(value):
    if type(value) is not int or value != 7:
        raise ValueError("Exact released CPU7 required")
    return value


def _policy(select, seconds):
    if (
        type(select) is not str
        or not select
        or type(seconds) is not int
        or seconds not in (480, 1800)
    ):
        raise ValueError("Explicit bounded software policy required")
    if any(name in select for name in ISSUED_CASES) and select not in ISSUED_CASES:
        raise ValueError("One exact issued case only")
    if seconds == 1800 and select != ISSUED_CASES[0]:
        raise ValueError("Only the first value-only pilot has the1800 envelope")
    return seconds


def _integration_envelope(select, seconds):
    """Keep the exact reached inherited contract in the declared preparation."""
    _policy(select, seconds)
    if seconds == 480:
        return None
    return dict(
        seconds=1800,
        single_named_pilot=ISSUED_CASES[0],
        native_bodies_operators_RNG_reference_and_science_held=True,
        detached=True,
        automatic_retry=False,
    )


def _select_items(items, select):
    if select not in ISSUED_CASES:
        selected, removed = prior.reused._select_items(items, select)
        if any(item.originalname in ISSUED_CASES for item in selected):
            raise ValueError("Issued terminal selection must name exactly one released item")
        return selected, removed
    yes = [item for item in items if item.name == select and item.originalname == select]
    if len(yes) != 1:
        raise ValueError("Exactly one issued terminal item required")
    return yes, [item for item in items if item not in yes]


def _exit_status(value):
    """Do not turn a nonzero inherited pytest result into a successful process."""
    if type(value) is not int or value not in range(6):
        raise ValueError("Exact inherited pytest process status required")
    return value


class Reports(prior.Reports):
    def pytest_configure(self, config):
        # The real failed context retains frames, modules and owner graphs.
        # Rendering their repr during pytest formatting is neither evidence
        # capture nor safe within the resource cap. Raw failures stay in the
        # existing state/contexts; supported checkpoints remain separate.
        config.option.tbstyle = "short"
        config.option.showlocals = False
        config.option.fulltrace = False

    def pytest_runtest_makereport(self, item, call):
        super().pytest_runtest_makereport(item, call)
        if call.excinfo is None:
            return
        error = call.excinfo.value
        try:
            self.state.evidence_attempts += (("compact_case_failure", item.nodeid, call.when),)
            directory = self.output / "compact-failures"
            directory.mkdir(exist_ok=True)
            key = hashlib.sha256(item.nodeid.encode()).hexdigest() + "." + call.when + ".json"
            snapshot.write_json(
                directory / key,
                dict(
                    nodeid=item.nodeid,
                    when=call.when,
                    primary=compact_error(error),
                    raw_primary_retained_in_state=self.state.primary is error,
                    full_failed_owner_serialization_claimed=False,
                ),
            )
        except BaseException as capture:
            self.state.evidence_errors += (("compact_case_failure", capture, error),)

    def pytest_collection_modifyitems(self, config, items):
        selected, removed = _select_items(items, self.select)
        snapshot.write_json(
            self.output / "selection.json",
            dict(
                selection=self.select,
                selected=[item.name for item in selected],
                deselected=[item.name for item in removed],
            ),
        )
        config.hook.pytest_deselected(items=removed)
        items[:] = selected


def _issued_driver(frame):
    if os.environ.get(ISSUED_RELEASE) != "1" or type(frame) is not FrameType:
        return False
    name = frame.f_globals.get("__name__")
    if name != "cells.processes.betse_native_init_terminal":
        namespace = dict(vars(prior), ROOT=ROOT, ISSUED_RELEASE=ISSUED_RELEASE)
        return FunctionType(prior._issued_driver.__code__, namespace)(frame)
    module = sys.modules.get(name)
    if type(module) is not ModuleType:
        return False
    context = frame.f_locals.get("context")
    if (
        type(context) is not SimpleNamespace
        or not module._ACTIVE
        or module._ACTIVE[-1] is not context
        or not context.active
        or context.invalid
        or frame.f_back is None
        or frame.f_back.f_code is not module.prepare.__code__
        or frame.f_back.f_globals is not vars(module)
        or frame.f_back.f_locals.get("context") is not context
        or type(context.request) is not module.Request
        or module._REQUESTS.get(context.request) is not context.refs
        or module._CONSUMED.get(context.request) is not context
    ):
        return False
    original, function = module.base, context.runtime.get("_run")
    if (
        context.runtime is not context.runtime_record
        or frame.f_globals is not context.runtime
        or type(function) is not FunctionType
        or function.__globals__ is not context.runtime
        or function.__code__ is not original._run.__code__
    ):
        return False
    owner, parent = context.request.electrical_owner, context.electrical_parent
    producer = original.previous
    if (
        type(owner) is not producer.ElectricalOwner
        or module._RETIRED.get(owner) is not context
        or producer._FORWARDED.get(owner) is not context
        or producer._ISSUED.get(owner, (None,))[0] is not parent
    ):
        return False
    path = Path(original.__file__)
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        return False
    code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    expected = next(v for v in code.co_consts if hasattr(v, "co_name") and v.co_name == "_run")
    if function.__code__ != expected or frame.f_code is not function.__code__:
        return False
    fixtures = {
        "tests.unit.test_betse_native_init_terminal_issued",
        "tests.unit.test_betse_native_init_first_step",
    }
    methods = (*context.methods.values(), *context.originals.values())
    return bool(methods) and all(
        type(fn) is FunctionType
        and fn.__globals__.get("__name__") in fixtures
        and not fn.__code__.co_filename.startswith(str(NATIVE_ROOT) + os.sep)
        for fn in methods
    )


def is_forbidden_frame(frame):
    name = frame.f_globals.get("__name__")
    drivers = {
        "cells.processes.betse_native_init_terminal",
        "cells.processes.betse_native_init_storage",
        "cells.processes.betse_native_init_electrical",
    }
    if name in drivers and frame.f_code.co_name == "_run":
        return not _issued_driver(frame)
    if name == "cells.processes.betse_native_init_terminal" and frame.f_code.co_name in (
        "_namespace",
        "_dispatch_impl",
    ):
        return True
    return prior.reused.is_forbidden_frame(frame)


def _scope():
    values = dict(
        prior._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=7,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
        is_forbidden_frame=is_forbidden_frame,
        _scope=_scope,
        _integration_policy=_policy,
        Reports=Reports,
        __file__=__file__,
    )
    base = values["base"]
    values["base"] = SimpleNamespace(
        **dict(vars(base), reuse=SimpleNamespace(**dict(vars(base.reuse), Reports=Reports)))
    )
    return values


def prepare(output, select, *, seconds=480):
    _policy(select, seconds)
    origin = prior.reused.inherited.inherited.inherited.reuse
    function = FunctionType(origin.prepare.__code__, _scope(), argdefs=origin.prepare.__defaults__)
    function.__kwdefaults__ = origin.prepare.__kwdefaults__
    result = function(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.write_json(output / "default-lane-inputs.json", inputs)
    inputs.update(
        cpu=7,
        wall_seconds=seconds,
        terminal_issued_synthetic=True,
        issued_dependencies={
            name: snapshot.digest(output / "source" / name) for name in DEPENDENCIES
        },
        terminal_overlay_pins=metadata._overlay_inventory(),
        software_integration_envelope=_integration_envelope(select, seconds),
    )
    pending = output / "lane-inputs.json.pending"
    snapshot.write_json(pending, inputs)
    os.replace(pending, output / "inputs.json")
    return result


def _prepared(inputs, select, seconds):
    _policy(select, seconds)
    for key, value in dict(
        cpu=7,
        threads=1,
        metadata_bytes=512 * 2**20,
        software_bytes=2**30,
        reserve_bytes=8 * 2**30,
        wall_seconds=seconds,
        software_release_requested=True,
        selection=select,
        terminal_issued_synthetic=True,
    ).items():
        if type(inputs.get(key)) is not type(value) or inputs[key] != value:
            raise ValueError("Exact frozen terminal-issued policy required: " + key)
    expected = _integration_envelope(select, seconds)
    actual = inputs.get("software_integration_envelope")
    if (expected is None and actual is not None) or (
        expected is not None
        and (
            type(actual) is not dict
            or set(actual) != set(expected)
            or any(
                type(actual[key]) is not type(value) or actual[key] != value
                for key, value in expected.items()
            )
        )
    ):
        raise ValueError("Exact terminal issued envelope required")


def _producers(inputs):
    """Authenticate the complete declared image before definitions or a worker."""
    prior.reused.inherited.inherited._external_producers(inputs, loaded=False)
    overlays = metadata._verify_overlay_manifest(inputs)
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for key, names in (("owned_files", OWNED), ("issued_dependencies", DEPENDENCIES)):
        if type(inputs.get(key)) is not dict or set(inputs[key]) != set(names):
            raise ValueError("Exact terminal issued source/dependency roster required")
        for name, pin in inputs[key].items():
            if manifest["files"][name]["sha256"] != pin or snapshot.digest(ROOT / name) != pin:
                raise ValueError("Exact terminal issued producer required: " + name)
    return manifest, overlays


def _definitions(output, manifest):
    """Load pinned fixture definitions before the source-entry blockade.

    These existing modules declare literal classes/functions without invoking
    their bodies. The later blockade still rejects every such native body.
    No public issuer or declared toy constructor is invoked here.
    """
    module = importlib.import_module(TEST[:-3].replace("/", "."))
    if Path(module.__file__).resolve() != ROOT / TEST:
        raise ValueError("Actual frozen issued fixture definitions required")
    rows = []
    for name, value in tuple(sys.modules.items()):
        if type(value) is not ModuleType:
            continue
        filename = vars(value).get("__file__")
        if type(filename) is not str:
            continue
        path = Path(filename)
        if path.is_relative_to(Path(NATIVE_ROOT)):
            raise ValueError("Original native package imports remain held")
        if not name.startswith(("cells.", "tests.", "validation.")):
            continue
        if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
            raise ValueError("Canonical frozen definition origin required: " + name)
        relative = str(path.relative_to(ROOT))
        expected = manifest["files"][relative]["sha256"]
        if snapshot.digest(path) != expected:
            raise ValueError("Loaded definition differs from frozen producer: " + name)
        rows.append(dict(module=name, path=relative, sha256=expected))
    snapshot.write_json(
        output / "issued-definition-imports.json",
        dict(definitions=rows, actual_issuer_constructor_native_RNG_or_science_entries=0),
    )


def child(output, select, *, seconds=480):
    inputs = json.loads((output / "inputs.json").read_text())
    _prepared(inputs, select, seconds)
    if (
        os.environ.get(SOFTWARE_RELEASE) != "1"
        or os.sched_getaffinity(0) != {7}
        or not __debug__
        or ROOT != output / "source"
    ):
        raise ValueError("Explicit immutable assertion-enabled CPU7 required")
    manifest, overlays = _producers(inputs)
    _definitions(output, manifest)
    if select in ISSUED_CASES:
        os.environ[ISSUED_RELEASE] = "1"
    else:
        os.environ.pop(ISSUED_RELEASE, None)
    try:
        return _inherited_child(output, select)
    finally:
        global _RAW_FAILURES
        # On failure leave primary handling to the existing child, retain overlay
        # observations independently rather than replacing an active exception.
        primary = sys.exception()
        try:
            snapshot.write_json(
                output / "terminal-issued-overlays.json", metadata._loaded_overlays(overlays)
            )
        except BaseException as capture:
            _RAW_FAILURES += ((primary, capture, output),)
            if primary is None:
                raise


def _inherited_child(output, select):
    """The real inherited launch seam, also exercised before any owner setup.

    Reuse the unchanged child code and its complete preparation/producer checks.
    Tests may stop its actual downstream worker at call entry, never substitute
    a passing child or a prepared owner.
    """
    origin = prior.reused.inherited.inherited.inherited
    namespace = dict(vars(origin), **_scope())
    try:
        return _exit_status(FunctionType(origin.child.__code__, namespace)(output, select))
    finally:
        global _RAW_FAILURES
        _RAW_FAILURES += namespace.get("_RAW_FAILURES", ())


def run_prepared(output, select, *, inputs_sha256):
    primary = None
    try:
        if select != ISSUED_CASES[0] or snapshot.digest(output / "inputs.json") != inputs_sha256:
            raise ValueError("Exact single prepared pilot required")
        inputs = json.loads((output / "inputs.json").read_text())
        _prepared(inputs, select, 1800)
        if (
            ROOT != output / "source"
            or Path(__file__).resolve() != ROOT / FILE
            or os.sched_getaffinity(0) != {7}
            or os.environ.get(SOFTWARE_RELEASE) != "1"
        ):
            raise ValueError("Exact CPU7 controller release required")
        _producers(inputs)
        snapshot.write_json(
            output / "controller-start.json", dict(inputs_sha256=inputs_sha256, cpu=7, seconds=1800)
        )
        process = output / "process"
        process.mkdir()
        guard.run_bounded(
            [
                "taskset",
                "-c",
                "7",
                sys.executable,
                "-B",
                "-m",
                MODULE,
                "--child",
                str(output),
                "--select",
                select,
                "--seconds",
                "1800",
            ],
            directory=process,
            cwd=ROOT,
            env=dict(os.environ),
            timeout=1800,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
        )
        cleanup = json.loads((output / "child-cleanup.json").read_text())
        native = json.loads((output / "native-entry-guard.json").read_text())
        reports = [json.loads(p.read_text()) for p in (output / "reports").glob("*.json")]
        if (
            cleanup.get("status") != "completed"
            or native.get("attempted")
            or len(reports) != 3
            or any(r.get("outcome") != "passed" for r in reports)
        ):
            raise ValueError("Complete passing synthetic pilot evidence required")
        snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
        if snapshot.digest(output / "inputs.json") != inputs_sha256:
            raise ValueError("Prepared pilot inputs changed during execution")
    except BaseException as error:
        primary = error
    result = dict(
        status="completed" if primary is None else "failed",
        primary=compact_error(primary),
        inputs_sha256=inputs_sha256,
        cpu=7,
        seconds=1800,
        scientific_credit=0,
        automatic_retry=False,
    )
    try:
        snapshot.write_json(
            output / ("controller-result.json" if primary is None else "controller-failure.json"),
            result,
        )
    except BaseException as capture:
        global _RAW_FAILURES
        _RAW_FAILURES += ((primary, capture, output),)
        if primary is None:
            raise
    if primary is not None:
        raise primary from BaseException.__cause__.__get__(primary)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", type=Path)
    modes.add_argument("--child", type=Path)
    modes.add_argument("--run-prepared", type=Path)
    parser.add_argument("--select", required=True)
    parser.add_argument("--seconds", type=int, default=480)
    parser.add_argument("--inputs-sha256")
    args = parser.parse_args()
    output = args.prepare or args.child or args.run_prepared
    resource.setrlimit(resource.RLIMIT_AS, ((2**30 if args.child else 512 * 2**20), 2**30))
    try:
        if args.run_prepared:
            return run_prepared(output, args.select, inputs_sha256=args.inputs_sha256)
        if args.child:
            return child(output, args.select, seconds=args.seconds)
        if os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit metadata release required")
        prepare(output, args.select, seconds=args.seconds)
        return 0
    except BaseException as primary:
        try:
            prior.reused.inherited.inherited.inherited.base.reuse.reuse._main_failure(
                output, primary
            )
        except BaseException as capture:
            global _RAW_FAILURES
            _RAW_FAILURES += ((primary, capture, output),)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
