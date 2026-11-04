"""Immutable blocked software; ordinary480 or one explicit value-only1800 pilot."""

import argparse
import importlib
import json
import os
import resource
import signal
import sys
import time
import traceback
from pathlib import Path
from types import CodeType, FrameType, FunctionType, ModuleType, SimpleNamespace

from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_native_init_first_step_software as reused

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_short_history.py"
DIAGNOSTICS = "src/cells/processes/betse_native_init_short_history_diagnostics.py"
ELECTRICAL = "src/cells/processes/betse_native_init_electrical.py"
STORAGE = "src/cells/processes/betse_native_init_storage.py"
LITERAL = reused.LITERAL
TEST = "tests/unit/test_betse_native_init_short_history.py"
DIAGNOSTICS_TEST = "tests/unit/test_betse_native_init_short_history_diagnostics.py"
FILE = "validation/betse/betse_native_init_short_history_software.py"
MODULE = "validation.betse.betse_native_init_short_history_software"
SOFTWARE_RELEASE = "BETSE_NATIVE_INIT_SHORT_HISTORY_SOFTWARE_RELEASED"
ISSUED_RELEASE = "BETSE_NATIVE_INIT_SHORT_HISTORY_ISSUED_SOFTWARE_RELEASED"
ISSUED_CASES = (
    "test_short_history_issued_value_only",
    "test_short_history_issued_retained_flux",
    "test_short_history_failed_mid_history_value_only",
    "test_short_history_failed_mid_history_retained_flux",
)
OWNED = (SOURCE, DIAGNOSTICS, TEST, DIAGNOSTICS_TEST, FILE, ELECTRICAL, STORAGE)
DEPENDENCIES = (
    "src/cells/processes/betse_native_init_first_step.py",
    "src/cells/processes/betse_native_init_molecule_short_runtime.py",
    "src/cells/processes/betse_native_init_dynamics_completion.py",
    "src/cells/processes/betse_native_init_retained_world.py",
    "src/cells/processes/betse_native_init_molecule_network.py",
    "src/cells/processes/betse_native_init_molecule_wrapper_authority.py",
    "src/cells/processes/betse_native_init_molecule_channels.py",
    "tests/unit/test_betse_native_init_dynamics_completion.py",
)
snapshot, base = reused.snapshot, reused.base
NATIVE_ROOT = reused.NATIVE_ROOT
FORBIDDEN_MODULES = reused.FORBIDDEN_MODULES
_RAW_FAILURES = ()
_DIAGNOSTIC = None


def compact_error(error):
    """Primitive exception metadata only; never render owner/local graphs."""
    if error is None:
        return None

    def one(value):
        if type(value) in (str, int, float, bool) or value is None:
            return value[:240] if type(value) is str else value
        return dict(opaque_type=type(value).__module__ + "." + type(value).__qualname__)

    rows, seen, current = [], set(), error
    while current is not None and id(current) not in seen and len(rows) < 4:
        seen.add(id(current))
        rows.append(
            dict(
                type=type(current).__module__ + "." + type(current).__qualname__,
                args=[one(v) for v in BaseException.args.__get__(current)[:6]],
            )
        )
        current = BaseException.__cause__.__get__(current)
    return rows


class SetupDiagnostic:
    """Bounded same-thread SIGALRM stacks and local API monitoring only."""

    def __init__(self, output, methods):
        self.output, self.methods = output, methods
        self.started, self.cpu_started = time.monotonic(), time.process_time()
        self.events, self.samples, self.skipped, self.errors = 0, 0, 0, []
        self.writing, self.tool, self.local_codes = False, None, ()
        self.reserved = False
        self.handler = self._sample

    def record(self, name, error=None):
        if self.writing or self.events >= 128:
            self.skipped += 1
            return
        self.writing = True
        self.events += 1
        try:
            snapshot.write_json(
                self.output / f"stage-{self.events:03d}.json",
                dict(
                    stage=name,
                    elapsed_seconds=time.monotonic() - self.started,
                    cpu_seconds=time.process_time() - self.cpu_started,
                    error=compact_error(error),
                    owner_or_local_graph_rendered=False,
                ),
            )
        except BaseException as capture:
            self.last_error = capture
            self._keep_error(capture)
        finally:
            self.writing = False

    def _keep_error(self, error):
        self.last_error = error
        try:
            self.errors.append(compact_error(error))
        except BaseException as secondary:
            self.journal_error = secondary

    def _sample(self, number, frame):
        if self.writing or self.samples >= 16:
            self.skipped += 1
            return
        self.writing = True
        self.samples += 1
        try:
            hooks = sys.getprofile(), sys.gettrace()
            stack, current = [], frame
            while current is not None and len(stack) < 32:
                stack.append(
                    dict(
                        filename=current.f_code.co_filename,
                        function=current.f_code.co_name,
                        line=current.f_lineno,
                    )
                )
                current = current.f_back
            snapshot.write_json(
                self.output / f"stack-{self.samples:03d}.json",
                dict(
                    elapsed_seconds=time.monotonic() - self.started,
                    cpu_seconds=time.process_time() - self.cpu_started,
                    stack=stack,
                    observer_identities_unchanged=(
                        sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
                    ),
                    locals_or_owner_graphs_saved=False,
                ),
            )
        except BaseException as capture:
            self.last_error = capture
            self._keep_error(capture)
        finally:
            self.writing = False

    def __enter__(self):
        self.output.mkdir()
        self.previous_handler = signal.getsignal(signal.SIGALRM)
        self.previous_timer = signal.getitimer(signal.ITIMER_REAL)
        if self.previous_handler != signal.SIG_DFL or any(self.previous_timer):
            raise ValueError("An independent idle SIGALRM/ITIMER_REAL slot is required")
        self.previous_hooks = sys.getprofile(), sys.gettrace()
        monitor = sys.monitoring
        free = [i for i in range(6) if monitor.get_tool(i) is None]
        if not free:
            raise ValueError("An independent local monitoring slot is required")
        self.tool = free[-1]
        self.local_codes = tuple(self.methods)

        def begin(code, offset):
            self.record(self.methods[code] + ":enter")

        def returned(code, offset, value):
            self.record(self.methods[code] + ":return")

        def unwind(code, offset, error):
            if code in self.methods:
                self.record(self.methods[code] + ":unwind", error)

        try:
            monitor.use_tool_id(self.tool, "Cells bounded owner setup diagnostic")
            self.reserved = True
            for event, callback in (
                (monitor.events.PY_START, begin),
                (monitor.events.PY_RETURN, returned),
                (monitor.events.PY_UNWIND, unwind),
            ):
                monitor.register_callback(self.tool, event, callback)
            # PY_UNWIND is a global event in CPython; it cannot be enabled in
            # a local event set. Filter only the declared methods there.
            monitor.set_events(self.tool, monitor.events.PY_UNWIND)
            events = monitor.events.PY_START | monitor.events.PY_RETURN
            for code in self.local_codes:
                monitor.set_local_events(self.tool, code, events)
            signal.signal(signal.SIGALRM, self.handler)
            signal.setitimer(signal.ITIMER_REAL, 30.0, 30.0)
            self.record("diagnostic:installed")
            return self
        except BaseException as primary:
            self._close(primary)
            raise

    def _close(self, primary):
        actions = (
            lambda: signal.setitimer(signal.ITIMER_REAL, 0.0, 0.0),
            lambda: signal.signal(signal.SIGALRM, self.previous_handler),
        )
        for action in actions:
            try:
                action()
            except BaseException as capture:
                self._keep_error(capture)
        if self.reserved:
            monitor = sys.monitoring
            try:
                monitor.set_events(self.tool, 0)
            except BaseException as capture:
                self._keep_error(capture)
            for code in self.local_codes:
                try:
                    monitor.set_local_events(self.tool, code, 0)
                except BaseException as capture:
                    self._keep_error(capture)
            for event in (
                monitor.events.PY_START,
                monitor.events.PY_RETURN,
                monitor.events.PY_UNWIND,
            ):
                try:
                    monitor.register_callback(self.tool, event, None)
                except BaseException as capture:
                    self._keep_error(capture)
            try:
                monitor.free_tool_id(self.tool)
            except BaseException as capture:
                self._keep_error(capture)
        self.record("diagnostic:closed", primary)
        try:
            snapshot.write_json(
                self.output / "terminal.json",
                dict(
                    primary=compact_error(primary),
                    capture_errors=self.errors,
                    events=self.events,
                    stacks=self.samples,
                    skipped=self.skipped,
                    both_observers_unchanged=(
                        sys.getprofile() is self.previous_hooks[0]
                        and sys.gettrace() is self.previous_hooks[1]
                    ),
                    alarm_restored=signal.getsignal(signal.SIGALRM) is self.previous_handler,
                    one_thread_signal_sampling=True,
                    source_or_scientific_credit=0,
                ),
            )
        except BaseException as capture:
            self.last_error = capture

    def __exit__(self, kind, primary, tb):
        self._close(primary)
        return False


def diagnostic_stage(name, error=None):
    if _DIAGNOSTIC is not None:
        _DIAGNOSTIC.record(name, error)


def _cpu(value):
    if type(value) is not int or value not in (4, 6):
        raise ValueError("Explicit released software CPU4 or default CPU6 required")
    return value


def is_forbidden_frame(frame):
    name = frame.f_globals.get("__name__")
    drivers = {
        "cells.processes.betse_native_init_short_history",
        "cells.processes.betse_native_init_storage",
        "cells.processes.betse_native_init_electrical",
    }
    if name in drivers and frame.f_code.co_name == "_run":
        return not _issued_driver(frame)
    if name == "cells.processes.betse_native_init_short_history":
        if frame.f_code.co_name in ("_run", "_namespace", "_dispatch_impl"):
            return True
    return reused.is_forbidden_frame(frame)


def _issued_driver(frame):
    """Nonnumerical original driver, actual active public issuer, toy bodies."""
    if os.environ.get(ISSUED_RELEASE) != "1" or type(frame) is not FrameType:
        return False
    name = frame.f_globals.get("__name__")
    if name not in (
        "cells.processes.betse_native_init_short_history",
        "cells.processes.betse_native_init_storage",
        "cells.processes.betse_native_init_electrical",
    ):
        return False
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
    if name.endswith("_short_history"):
        original = module.base
        function = context.runtime.get("_run")
        if (
            context.runtime is not context.runtime_record
            or frame.f_globals is not context.runtime
            or type(function) is not FunctionType
            or function.__globals__ is not context.runtime
            or function.__code__ is not original._run.__code__
        ):
            return False
        owner, parent = context.request.electrical_owner, context.electrical_parent
        producer, owner_type = original.previous, original.previous.ElectricalOwner
        forwarded = producer._FORWARDED
    else:
        function, original = vars(module).get("_run"), module
        if frame.f_globals is not vars(module):
            return False
        if name.endswith("_storage"):
            owner, parent = context.request.dynamics_owner, context.parent
            producer, owner_type = module.previous, module.previous.DynamicsOwner
            forwarded = producer._STORAGE_FORWARDED
        elif name.endswith("_electrical"):
            owner, parent = context.request.storage_owner, context.storage_parent
            producer, owner_type = module.storage, module.storage.StorageOwner
            forwarded = producer._ELECTRICAL_FORWARDED
        else:
            return False
    path = Path(original.__file__)
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        return False
    code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    expected = next(v for v in code.co_consts if type(v) is CodeType and v.co_name == "_run")
    if (
        type(function) is not FunctionType
        or function.__code__ != expected
        or frame.f_code is not function.__code__
        or type(owner) is not owner_type
        or module._RETIRED.get(owner) is not context
        or forwarded.get(owner) is not context
        or producer._ISSUED.get(owner, (None,))[0] is not parent
    ):
        return False
    methods = (
        (context.method, context.original)
        if name.endswith("_storage")
        else (*context.methods.values(), *context.originals.values())
    )
    fixtures = frozenset(
        (
            "tests.unit.test_betse_native_init_short_history",
            "tests.unit.test_betse_native_init_first_step",
            "tests.unit.test_betse_native_init_storage",
            "tests.unit.test_betse_native_init_dynamics_completion",
            "tests.unit.test_betse_native_init_retained_world",
        )
    )
    return bool(methods) and all(
        type(fn) is FunctionType
        and fn.__globals__.get("__name__") in fixtures
        and not fn.__code__.co_filename.startswith(str(NATIVE_ROOT) + os.sep)
        for fn in methods
    )


def _policy(select, seconds):
    if (
        type(select) is not str
        or not select
        or type(seconds) is not int
        or seconds not in (480, 1800)
    ):
        raise ValueError("Only explicit ordinary480 or named value-only1800 software modes")
    if any(name in select for name in ISSUED_CASES) and select not in ISSUED_CASES:
        raise ValueError("One exact fresh issued-chain item per guarded group required")
    if seconds == 1800 and select != ISSUED_CASES[0]:
        raise ValueError("Only the exact value-only item may use the1800 software envelope")
    return seconds


def _integration_envelope(select, seconds):
    _policy(select, seconds)
    if seconds == 480:
        return None
    return dict(
        seconds=1800,
        default_seconds=480,
        single_named_pilot=ISSUED_CASES[0],
        native_bodies_operators_RNG_reference_and_science_held=True,
        calls_and_attempts_are_not_independent_cases=True,
        detached=True,
        automatic_retry=False,
    )


def _prepared_policy(inputs, select, *, cpu, seconds):
    _policy(select, seconds)
    if (
        inputs.get("wall_seconds") != seconds
        or type(inputs.get("wall_seconds")) is not int
        or inputs.get("selection") != select
        or inputs.get("software_release_requested") is not True
        or inputs.get("software_integration_envelope") != _integration_envelope(select, seconds)
        or inputs.get("cpu") != _cpu(cpu)
        or type(inputs.get("cpu")) is not int
        or any(
            type(inputs.get(name)) is not int or inputs[name] != expected
            for name, expected in (
                ("threads", 1),
                ("software_bytes", 2**30),
                ("reserve_bytes", 8 * 2**30),
            )
        )
        or (select in ISSUED_CASES and cpu != 6)
    ):
        raise ValueError("Exact prepared software selection, envelope and resource limits required")
    return seconds


def _scope():
    return dict(
        reused._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        OWNED=OWNED,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=6,
        FORBIDDEN_MODULES=FORBIDDEN_MODULES,
        is_forbidden_frame=is_forbidden_frame,
        _scope=_scope,
        _integration_policy=_policy,
        __file__=__file__,
    )


def prepare(output, select, *, cpu=6, diagnostic=False, issued_chain_seconds=480):
    lane = _cpu(cpu)
    seconds = _policy(select, issued_chain_seconds)
    if select in ISSUED_CASES and lane != 6:
        raise ValueError("Fresh actual-issued chain uses its released CPU6 lane")
    if type(diagnostic) is not bool or diagnostic and select != ISSUED_CASES[0]:
        raise ValueError("Setup diagnostic is limited to the one named value-only pilot")
    origin = reused.inherited.inherited.inherited.reuse
    fn = FunctionType(origin.prepare.__code__, _scope(), "prepare", origin.prepare.__defaults__)
    fn.__kwdefaults__ = origin.prepare.__kwdefaults__
    result = fn(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    snapshot.write_json(output / "default-lane-inputs.json", inputs)
    inputs.update(
        cpu=lane,
        wall_seconds=seconds,
        software_integration_envelope=_integration_envelope(select, seconds),
        setup_diagnostic=(
            dict(
                interval_seconds=30,
                max_stacks=16,
                max_depth=32,
                max_stage_rows=128,
                observer_controls_unchanged=True,
            )
            if diagnostic
            else None
        ),
        short_history_dependencies={
            name: snapshot.digest(output / "source" / name) for name in DEPENDENCIES
        },
        short_history_software_lane=dict(
            selected=lane,
            default=6,
            source_native_and_resource_caps_unchanged=True,
        ),
        issued_chain_software=(
            dict(
                selection=select,
                contiguous_iterations=3,
                actual_public_issuers_with_declared_prebirth_toy_acquisition=True,
                source_native_operator_RNG_reference_and_science_held=True,
            )
            if select in ISSUED_CASES
            else None
        ),
    )
    pending = output / "lane-inputs.json.pending"
    snapshot.write_json(pending, inputs)
    os.replace(pending, output / "inputs.json")
    return result


def child(output, select, *, cpu=6, diagnostic=False, issued_chain_seconds=480):
    lane = _cpu(cpu)
    inputs = json.loads((output / "inputs.json").read_text())
    _prepared_policy(inputs, select, cpu=lane, seconds=issued_chain_seconds)
    if inputs.get("cpu") != lane or os.sched_getaffinity(0) != {lane}:
        raise ValueError("Exact prepared and measured software lane required")
    expected_diagnostic = dict(
        interval_seconds=30,
        max_stacks=16,
        max_depth=32,
        max_stage_rows=128,
        observer_controls_unchanged=True,
    )
    if (
        type(diagnostic) is not bool
        or (inputs.get("setup_diagnostic") != (expected_diagnostic if diagnostic else None))
        or diagnostic
        and select != ISSUED_CASES[0]
    ):
        raise ValueError("Exact prepared setup diagnostic envelope required")
    if select in ISSUED_CASES:
        policy = inputs.get("issued_chain_software")
        if (
            lane != 6
            or type(policy) is not dict
            or policy.get("selection") != select
            or policy.get("contiguous_iterations") != 3
            or policy.get("actual_public_issuers_with_declared_prebirth_toy_acquisition")
            is not True
            or policy.get("source_native_operator_RNG_reference_and_science_held") is not True
        ):
            raise ValueError("Exact issued-chain software envelope required")
        os.environ[ISSUED_RELEASE] = "1"
    else:
        os.environ.pop(ISSUED_RELEASE, None)
    reused.inherited.inherited._external_producers(inputs, loaded=False)
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if set(inputs.get("short_history_dependencies", ())) != set(DEPENDENCIES):
        raise ValueError("Exact declared short-history dependency roster required")
    for name in OWNED:
        if (
            snapshot.digest(ROOT / name) != inputs["owned_files"][name]
            or inputs["owned_files"][name] != manifest["files"][name]["sha256"]
        ):
            raise ValueError("Selected frozen short-history producer changed")
    for name in DEPENDENCIES:
        expected = inputs["short_history_dependencies"][name]
        if (
            snapshot.digest(ROOT / name) != expected
            or manifest["files"][name]["sha256"] != expected
        ):
            raise ValueError("Declared frozen short-history dependency changed")
    stage = importlib.import_module("cells.processes.betse_native_init_short_history")
    if Path(stage.__file__).resolve() != ROOT / SOURCE:
        raise ValueError("Actual frozen source module required")
    snapshot.write_json(output / "short-history-source-plan.json", stage.source_plan())
    origin = reused.inherited.inherited.inherited
    namespace = dict(vars(origin), **_scope())
    canonical = importlib.import_module(MODULE)
    global _DIAGNOSTIC
    if diagnostic:
        initial = stage.base.previous.storage.previous.previous.previous
        modules = (
            initial,
            stage.base.previous.storage.previous.previous,
            stage.base.previous.storage.previous,
            stage.base.previous.storage,
            stage.base.previous,
            stage,
        )
        methods = {
            vars(module)[name].__code__: module.__name__ + "." + name
            for module in modules
            for name in ("prepare", "_authority")
        }
        _DIAGNOSTIC = SetupDiagnostic(output / "setup-diagnostic", methods)
        canonical._DIAGNOSTIC = _DIAGNOSTIC
    try:
        if diagnostic:
            with _DIAGNOSTIC:
                return FunctionType(origin.child.__code__, namespace)(output, select)
        return FunctionType(origin.child.__code__, namespace)(output, select)
    finally:
        _DIAGNOSTIC = canonical._DIAGNOSTIC = None
        global _RAW_FAILURES
        _RAW_FAILURES = namespace.get("_RAW_FAILURES", ())


def _controller_inputs(output, select, *, cpu, seconds, inputs_sha256):
    """Authenticate the frozen controller and inputs before creating a worker."""
    inputs_path = output / "inputs.json"
    if snapshot.digest(inputs_path) != inputs_sha256:
        raise ValueError("Exact prepared input digest required")
    inputs = json.loads(inputs_path.read_text())
    _prepared_policy(inputs, select, cpu=cpu, seconds=seconds)
    if ROOT != output / "source" or Path(__file__).resolve() != ROOT / FILE:
        raise ValueError("Run the prepared controller from its immutable source snapshot")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for key, names in (("owned_files", OWNED), ("short_history_dependencies", DEPENDENCIES)):
        if set(inputs.get(key, ())) != set(names):
            raise ValueError("Exact prepared producer roster required")
        for name in names:
            if inputs[key][name] != manifest["files"][name]["sha256"]:
                raise ValueError("Prepared producer differs from verified immutable bytes")
    reused.inherited.inherited._external_producers(inputs, loaded=False)
    return inputs


def run_prepared(output, select, *, cpu, seconds, inputs_sha256):
    """One durable guarded execution; detachment is performed by the launcher."""
    inputs, primary, stage = None, None, "authenticate_prepared_controller"
    result = dict(status="failed", scientific_credit=0, automatic_retry=False)
    try:
        if select != ISSUED_CASES[0] or seconds != 1800 or cpu != 6:
            raise ValueError("Detached controller permits only the named value-only1800 pilot")
        if os.sched_getaffinity(0) != {6} or os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit CPU6 blocked-software controller required")
        inputs = _controller_inputs(
            output, select, cpu=cpu, seconds=seconds, inputs_sha256=inputs_sha256
        )
        snapshot.write_json(
            output / "controller-start.json",
            dict(inputs_sha256=inputs_sha256, cpu=cpu, wall_seconds=seconds, retry=False),
        )
        stage = "guarded_software_worker"
        directory = output / "process"
        directory.mkdir()
        command = [
            "taskset",
            "-c",
            str(cpu),
            sys.executable,
            "-B",
            "-m",
            MODULE,
            "--child",
            str(output),
            "--select",
            select,
            "--cpu",
            str(cpu),
            "--issued-chain-seconds",
            str(seconds),
        ]
        if inputs.get("setup_diagnostic") is not None:
            command.append("--setup-diagnostic")
        guard.run_bounded(
            command,
            directory=directory,
            cwd=ROOT,
            env=dict(os.environ),
            timeout=seconds,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
        )
        stage = "saved_worker_outcome"
        cleanup = json.loads((output / "child-cleanup.json").read_text())
        native = json.loads((output / "native-entry-guard.json").read_text())
        reports = [json.loads(path.read_text()) for path in (output / "reports").glob("*.json")]
        calls = [row for row in reports if row.get("when") == "call"]
        if (
            cleanup.get("status") != "completed"
            or native.get("attempted")
            or len(calls) != 1
            or calls[0].get("outcome") != "passed"
            or len(reports) != 3
            or any(row.get("outcome") != "passed" for row in reports)
        ):
            raise ValueError("Complete single-case reports, cleanup and empty guard required")
        stage = "frozen_execution_verification"
        snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
        if snapshot.digest(output / "inputs.json") != inputs_sha256:
            raise ValueError("Prepared input changed during execution")
        integration = None
        try:
            snapshot.assert_checkout_unchanged(ROOT)
        except BaseException as drift:
            integration = dict(error=compact_error(drift), integration_pending=True)
        result.update(status="completed", calls=1, checkout_integration=integration)
    except BaseException as error:
        primary = error
        result.update(stage=stage, primary=compact_error(error), traceback=traceback.format_exc())
    result.update(
        inputs_sha256=inputs_sha256,
        selection=select,
        cpu=cpu,
        wall_seconds=seconds,
        source_pins=None if inputs is None else inputs["owned_files"],
        dependency_pins=None if inputs is None else inputs["short_history_dependencies"],
        failed_or_incomplete_call_has_zero_completed_credit=True,
    )
    terminal = output / ("controller-result.json" if primary is None else "controller-failure.json")
    try:
        snapshot.write_json(terminal, result)
    except BaseException as capture:
        global _RAW_FAILURES
        _RAW_FAILURES += ((primary, capture, terminal),)
        if primary is not None:
            raise primary from BaseException.__cause__.__get__(primary)
        raise
    if primary is not None:
        raise primary
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--child", type=Path)
    mode.add_argument("--run-prepared", type=Path)
    parser.add_argument("--select", required=True)
    parser.add_argument("--cpu", type=int, default=6, choices=(4, 6))
    parser.add_argument("--setup-diagnostic", action="store_true")
    parser.add_argument("--issued-chain-seconds", type=int, default=480)
    parser.add_argument("--inputs-sha256")
    args = parser.parse_args()
    output = args.child or args.prepare or args.run_prepared
    try:
        if args.run_prepared is not None:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
            return run_prepared(
                output,
                args.select,
                cpu=args.cpu,
                seconds=args.issued_chain_seconds,
                inputs_sha256=args.inputs_sha256,
            )
        if args.child is not None:
            resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
            return child(
                output,
                args.select,
                cpu=args.cpu,
                diagnostic=args.setup_diagnostic,
                issued_chain_seconds=args.issued_chain_seconds,
            )
        if os.environ.get(SOFTWARE_RELEASE) != "1":
            raise ValueError("Explicit native-blocked software release required")
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return prepare(
            output,
            args.select,
            cpu=args.cpu,
            diagnostic=args.setup_diagnostic,
            issued_chain_seconds=args.issued_chain_seconds,
        )
    except BaseException as primary:
        try:
            snapshot.write_json(
                output / "short-history-runner-failure.json",
                dict(
                    status="failed",
                    type=type(primary).__name__,
                    message=str(primary),
                    traceback=traceback.format_exc(),
                    native_scientific_credit=0,
                    full_raw_failed_owner_serialization_claimed=False,
                ),
            )
        except BaseException:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(main())
