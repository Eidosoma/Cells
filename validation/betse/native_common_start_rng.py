"""Opt-in common-start input program on the actual two global MT generators.

This is a fresh-process operation after parameters and before world creation,
not an ambient-state witness, saved-state loader, or model/phase admission.
Consumers must adopt this producer and declare both new caller source hashes.
All execution stays behind the explicit release gate. Importing reads no RNG.
"""

import builtins
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, active_count, get_ident, main_thread
from types import (
    BuiltinFunctionType,
    CodeType,
    FrameType,
    FunctionType,
    GeneratorType,
    MethodType,
    ModuleType,
)

from cells.processes import betse_native_numpy_copy_origin as executable
from validation import source_snapshot as snapshot
from validation.betse import native_rng_runtime as provenance

FILE = "validation/betse/native_common_start_rng.py"
KIND = "cells.explicit_fresh_common_start_rng_program@1"
RELEASE = "CELLS_COMMON_START_RNG_RELEASED"
EPOCH = "after_parameters_before_world_construction"
PROVENANCE_SHA256 = "6ddb846ef3a20e9ff95fb2e546a39329e8d305b821bfedadf344fce9fe548315"
CONSUMERS = {
    "cells": ("validation.betse.native_seed_demo", "_execute", "_call"),
    "original": ("validation.betse.native_init_terminal_reference", "_workflow", "_attempt"),
}
STEPS = (
    ("python_before", "python_get", None),
    ("numpy_before", "numpy_get", None),
    ("python_seed", "python_seed", "python_seed"),
    ("python_after", "python_get", None),
    ("numpy_seed", "numpy_seed", "numpy_seed"),
    ("numpy_after", "numpy_get", None),
    ("python_readback", "python_get", None),
    ("numpy_readback", "numpy_get", None),
)
_LOCK, _ATTEMPT = RLock(), None
_SAMPLING, _AUDIT_READY, _AUDIT_PROBE = [], False, None
_AUDIT_EVENT = "cells.common_start_rng.sampling_audit_ack"


def _sampling_audit(event, args):
    if event == _AUDIT_EVENT and _AUDIT_PROBE is not None:
        if len(args) == 1 and args[0] is _AUDIT_PROBE:
            _AUDIT_PROBE["acknowledged"] = True
    if event in ("sys.setprofile", "sys.settrace"):
        for sample in _SAMPLING:
            sample["changed"] = True
            sample["last_mutation"] = (event, args)


def _install_sampling_audit():
    global _AUDIT_READY, _AUDIT_PROBE
    installed = _AUDIT_READY
    _AUDIT_READY = False
    probe = {"acknowledged": False}
    _AUDIT_PROBE = probe
    try:
        if not installed:
            # CPython may silently suppress a RuntimeError raised by an
            # earlier hook, returning without installing this callback.
            sys.addaudithook(_sampling_audit)
        sys.audit(_AUDIT_EVENT, probe)
        _require(probe["acknowledged"], "Sampling audit hook acknowledgement missing")
        _AUDIT_READY = True
    finally:
        _AUDIT_PROBE = None


class CommonStartRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


@dataclass(frozen=True, slots=True)
class Program:
    python_seed: int
    numpy_seed: int
    input_identity: str
    consumer_sources: tuple
    identity: str


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def program_document(program):
    _require(type(program) is Program, "Exact explicit Program required")
    _require(
        type(program.python_seed) is int
        and 0 <= program.python_seed < 2**256
        and type(program.numpy_seed) is int
        and 0 <= program.numpy_seed < 2**32
        and _pin(program.input_identity)
        and type(program.consumer_sources) is tuple
        and len(program.consumer_sources) == 2,
        "Bounded integer seeds, input identity and both caller sources required",
    )
    _require(
        all(
            type(row) is tuple and len(row) == 2 and type(row[0]) is str and _pin(row[1])
            for row in program.consumer_sources
        )
        and tuple(role for role, _ in program.consumer_sources) == tuple(CONSUMERS)
        and all(_pin(pin) for _, pin in program.consumer_sources),
        "Exact declared Cells/original source identities required",
    )
    return dict(
        kind=KIND,
        epoch=EPOCH,
        python_seed=program.python_seed,
        python_seed_version=2,
        numpy_seed=program.numpy_seed,
        numpy_api="legacy global RandomState.seed",
        input_identity=program.input_identity,
        consumer_sources=dict(program.consumer_sources),
        operations=[list(row) for row in STEPS],
        draws=0,
        setstate_or_generator_replacement=False,
    )


def declare(*, python_seed, numpy_seed, input_identity, consumer_sources):
    """Declare inputs only. No generator, parameter or state is constructed."""
    _require(
        type(consumer_sources) is dict and set(consumer_sources) == set(CONSUMERS),
        "Both explicit caller hashes required",
    )
    value = Program(
        python_seed,
        numpy_seed,
        input_identity,
        tuple((role, consumer_sources[role]) for role in CONSUMERS),
        "",
    )
    return Program(
        value.python_seed,
        value.numpy_seed,
        value.input_identity,
        value.consumer_sources,
        _digest(program_document(value)),
    )


def source_plan():
    return dict(
        kind=KIND,
        epoch=EPOCH,
        consumers=CONSUMERS,
        operations=STEPS,
        runtime_provenance=(provenance.FILE, PROVENANCE_SHA256),
        default="ambient mode untouched; no operation unless explicitly selected",
        boundary="actual consumer frame and same retained parameters before any world",
        one_attempt_per_process_including_failures=True,
        readbacks="bit-exact states after actual seed calls, never draws or replay",
        qualification=False,
    )


def _function(function):
    _require(type(function) is FunctionType, "Actual Python function required")
    provider = function.__globals__.get("__builtins__")
    cached = vars(provider) if type(provider) is ModuleType else provider
    _require(
        cached is function.__builtins__ is vars(builtins), "Exact cached builtin namespace required"
    )
    names = []
    for name in function.__code__.co_names:
        if name in function.__globals__:
            value = function.__globals__[name]
            _require(
                name not in cached or value is cached[name], "RNG source builtin shadowed: " + name
            )
            names.append((name, value))
        elif name in cached:
            names.append((name, cached[name]))
    return (
        function,
        function.__code__,
        function.__globals__,
        function.__builtins__,
        function.__defaults__,
        tuple((function.__kwdefaults__ or {}).items()),
        tuple((cell, cell.cell_contents) for cell in function.__closure__ or ()),
        tuple(names),
    )


def _same_function(binding):
    function, code, namespace, cached, defaults, keywords, cells, names = binding
    current = _function(function)
    _require(
        all(a is b for a, b in zip(current[:5], binding[:5], strict=True)),
        "Original function/code/globals changed",
    )
    _require(
        len(current[5]) == len(keywords)
        and all(a == b and x is y for (a, x), (b, y) in zip(current[5], keywords, strict=True)),
        "Original keyword defaults changed",
    )
    _require(
        len(current[6]) == len(cells)
        and all(a is b and x is y for (a, x), (b, y) in zip(current[6], cells, strict=True)),
        "Original closure association changed",
    )
    _require(
        len(current[7]) == len(names)
        and all(a == b and x is y for (a, x), (b, y) in zip(current[7], names, strict=True)),
        "Original RNG global lookup changed",
    )


def _source_code(function, path, qualified):
    """Compare actual executable metadata with pinned bytes; execute neither."""
    raw = Path(path).read_bytes()
    pending = [compile(raw, str(path), "exec", dont_inherit=True, optimize=0)]
    expected = None
    while pending:
        code = pending.pop()
        if code.co_qualname == qualified:
            _require(expected is None, "Unique original executable required")
            expected = code
        pending.extend(item for item in code.co_consts if type(item) is CodeType)
    _require(
        type(function) is FunctionType
        and expected is not None
        and executable._code(function.__code__) == executable._code(expected),
        "Actual full source code/constants required: " + qualified,
    )


def _boundary(program, state, role, frame):
    """No state/receipt/dictionary can substitute for the reached caller frame."""
    module_name, entry, wrapper = CONSUMERS[role]
    module = sys.modules.get(module_name)
    _require(type(module) is ModuleType, "Actual loaded consumer required")
    path = Path(module.__file__).resolve()
    root = Path(__file__).resolve().parents[2]
    relative = module_name.replace(".", "/") + ".py"
    _require(
        path == root / relative
        and not Path(module.__file__).is_symlink()
        and snapshot.digest(path) == dict(program.consumer_sources)[role],
        "Declared immutable consumer producer changed",
    )
    manifest = json.loads(snapshot.regular_file(root, "SNAPSHOT.json").read_text())
    _require(
        manifest["files"][relative]["sha256"] == dict(program.consumer_sources)[role]
        and manifest["files"][FILE]["sha256"] == snapshot.digest(Path(__file__)),
        "Actual frozen caller/helper source binding required",
    )
    state_name = "Execution" if role == "cells" else "State"
    _require(
        type(state) is vars(module).get(state_name),
        "Actual consumer " + state_name + " type required",
    )
    # The real caller may use its existing operation recorder. Skip only that
    # exact function, never arbitrary supplied frames or another wrapper.
    if type(frame) is FrameType and frame.f_code is vars(module)[wrapper].__code__:
        _require(
            frame.f_globals is vars(module) and frame.f_locals.get("state") is state,
            "Actual original operation recorder/state required",
        )
        frame = frame.f_back
    function = vars(module)[entry]
    _source_code(function, path, entry)
    _require(
        type(frame) is FrameType
        and frame.f_code is function.__code__
        and frame.f_globals is vars(module)
        and frame.f_locals.get("state") is state,
        "Actual after-parameters caller frame required",
    )
    _same_function(_function(function))
    plan = frame.f_locals.get("plan")
    _require(type(plan) is dict, "Actual caller input plan required")
    if role == "cells":
        owner, p = state.world_ready, state.parameters
        api = sys.modules.get("cells.processes.betse_native_parameter_load_remainder")
        _require(
            api is not None
            and type(owner) is api.WorldReadyParametersOwner
            and owner.parameters is p
            and state.callback is not None
            and state.phase is state.seed_phase is state.init_phase is None
            and not state.owners
            and not state.trials
            and not state.requests,
            "Fresh actual WorldReady/p before phase/geometry required",
        )
        order = [(row["name"], row["status"]) for row in state.operations]
        _require(
            order[-2:] == [("parameters", "returned"), ("common_start_rng", "attempted")],
            "One explicit common_start_rng immediately after parameters required",
        )
        from validation.betse import native_seed_initial_rng as ambient

        common = ambient.input_binding(plan, state)
        _require(
            common["input_inventory_sha256"] == program.input_identity,
            "Declared RNG program and actual Cells input inventory differ",
        )
        return (state, owner, p, frame, function, _function(function))
    p, runner = state.raw.get("parameters"), state.raw.get("runner")
    _require(
        state.stage == "original_runner"
        and p is not None
        and runner is not None
        and vars(runner).get("_p") is p
        and frame.f_locals.get("p") is p
        and frame.f_locals.get("runner") is runner
        and "seed_phase" not in state.raw
        and "init_phase" not in state.raw
        and not any(
            row[2:4] in (("betse.science.simrunner", "seed"), ("betse.science.simrunner", "init"))
            for row in state.work
        ),
        "Original same-p runner after Parameters.make and before seed required",
    )
    _require(
        _digest(plan["inputs"]["inventory"]) == program.input_identity,
        "Declared RNG program and actual original input inventory differ",
    )
    from validation.betse import native_seed_demo_inputs as inputs

    actual = inputs.inventory(Path(plan["inputs"]["root"]))
    _require(
        actual["files"] == plan["inputs"]["inventory"]["files"],
        "Actual original pre-world input files changed",
    )
    return (state, runner, p, frame, function, _function(function))


def _runtime():
    path = Path(provenance.__file__)
    _require(
        not path.is_symlink() and snapshot.digest(path) == PROVENANCE_SHA256,
        "Exact reviewed RNG provenance helper required",
    )
    for name, function in vars(provenance).items():
        if type(function) is FunctionType and function.__globals__ is vars(provenance):
            _source_code(function, path, name)
    py, np, mtrand = (sys.modules.get(name) for name in ("random", "numpy", "numpy.random.mtrand"))
    _require(
        all(type(value) is ModuleType for value in (py, np, mtrand)),
        "Already imported actual Python/NumPy runtime required; no lazy generator construction",
    )
    nr = vars(np).get("random")
    _require(
        type(nr) is ModuleType and sys.modules.get("numpy.random") is nr,
        "Actual NumPy random module association required",
    )
    python, numpy = vars(py)["_inst"], vars(mtrand)["_rand"]
    _require(
        type(python) is vars(py)["Random"]
        and type(numpy) is vars(mtrand)["RandomState"]
        and vars(nr)["RandomState"] is type(numpy),
        "Original global generator instances required",
    )
    delegates = dict(
        python_seed=vars(py)["seed"],
        python_get=vars(py)["getstate"],
        numpy_seed=vars(nr)["seed"],
        numpy_get=vars(nr)["get_state"],
    )
    for name in ("python_seed", "python_get"):
        fn = delegates[name]
        method = "seed" if name == "python_seed" else "getstate"
        _require(
            type(fn) is MethodType
            and fn.__self__ is python
            and fn.__func__ is vars(type(python))[method],
            "Original Python global bound method required",
        )
        _source_code(fn.__func__, Path(py.__file__).resolve(), "Random." + method)
    for name in ("numpy_seed", "numpy_get"):
        fn = delegates[name]
        method = "seed" if name == "numpy_seed" else "get_state"
        cytype = type(vars(type(numpy))["seed"])
        cython = (
            cytype.__name__ == "cython_function_or_method"
            and cytype.__module__.startswith("_cython_")
            and (
                name == "numpy_seed"
                and type(fn) is cytype
                and getattr(fn, "__self__", None) is None
                and fn.__globals__ is vars(mtrand)
                or name == "numpy_get"
                and type(fn) is MethodType
                and fn.__self__ is numpy
                and fn.__func__ is vars(type(numpy))[method]
                and type(fn.__func__) is cytype
                and fn.__func__.__globals__ is vars(mtrand)
            )
        )
        _require(
            fn.__name__ == method
            and fn is vars(mtrand)[method]
            and (
                cython
                or type(fn) is BuiltinFunctionType
                and (fn.__self__ is numpy or name == "numpy_seed" and fn.__self__ is mtrand)
            ),
            "Original NumPy global method/seed dispatch required",
        )
    bindings = dict(
        modules=(py, np, nr, mtrand),
        python=python,
        numpy=numpy,
        delegates=delegates,
        functions=tuple(
            _function(delegates[name].__func__) for name in ("python_seed", "python_get")
        ),
        python_type=type(python),
        numpy_type=type(numpy),
        python_members=tuple(vars(type(python)).items()),
        numpy_members=tuple(vars(type(numpy)).items()),
        opaque=tuple(
            (
                value,
                type(value),
                getattr(value, "__globals__", None),
                getattr(value, "__defaults__", None),
                getattr(value, "__kwdefaults__", None),
            )
            for name in ("numpy_seed", "numpy_get")
            for value in (getattr(delegates[name], "__func__", delegates[name]),)
        ),
    )
    return bindings


def _check_runtime(binding):
    py, np, nr, mtrand = binding["modules"]
    _require(
        all(
            actual is expected
            for actual, expected in zip(
                (
                    sys.modules.get(name)
                    for name in ("random", "numpy", "numpy.random", "numpy.random.mtrand")
                ),
                binding["modules"],
                strict=True,
            )
        )
        and vars(py)["_inst"] is binding["python"]
        and vars(mtrand)["_rand"] is binding["numpy"]
        and vars(np)["random"] is nr,
        "Original global RNG module/receiver identity changed",
    )
    for key, module, name in (
        ("python_seed", py, "seed"),
        ("python_get", py, "getstate"),
        ("numpy_seed", nr, "seed"),
        ("numpy_get", nr, "get_state"),
    ):
        _require(vars(module)[name] is binding["delegates"][key], "Original RNG export changed")
    for fn in binding["functions"]:
        _same_function(fn)
    for value, cls, namespace, defaults, keywords in binding["opaque"]:
        _require(
            type(value) is cls
            and getattr(value, "__globals__", None) is namespace
            and getattr(value, "__defaults__", None) is defaults
            and getattr(value, "__kwdefaults__", None) is keywords,
            "Original compiled NumPy callable/defaults changed",
        )
    for cls, key in (
        (binding["python_type"], "python_members"),
        (binding["numpy_type"], "numpy_members"),
    ):
        current, old = tuple(vars(cls).items()), binding[key]
        _require(
            len(current) == len(old)
            and all(
                key == name and actual is expected
                for (key, actual), (name, expected) in zip(current, old, strict=True)
            ),
            "Original RNG class dispatch changed",
        )


def _state(value, kind):
    """Exact supported state schema plus existing lossless typed sidecar codec."""
    if kind == "python":
        _require(
            type(value) is tuple
            and len(value) == 3
            and type(value[0]) is int
            and value[0] == 3
            and type(value[1]) is tuple
            and len(value[1]) == 625
            and all(type(word) is int and 0 <= word < 2**32 for word in value[1][:-1])
            and type(value[1][-1]) is int
            and 0 <= value[1][-1] <= 624
            and (value[2] is None or type(value[2]) is float),
            "Exact Python MT words/index/cache required",
        )
    else:
        np = sys.modules["numpy"]
        _require(
            type(value) is tuple
            and len(value) == 5
            and value[0] == "MT19937"
            and type(value[1]) is vars(np)["ndarray"]
            and value[1].dtype.str in ("<u4", ">u4")
            and value[1].shape == (624,)
            and value[1].strides == (4,)
            and type(value[2]) is int
            and 0 <= value[2] <= 624
            and type(value[3]) is int
            and value[3] in (0, 1)
            and type(value[4]) is float,
            "Exact NumPy MT words/index/Gaussian cache required",
        )
    from validation.betse import betse_native_membrane_initialization_archive as archive

    return archive.snapshot(value)


def _save(attempt, name, value):
    """Exclusive durable JSON; pending bytes survive any publication failure."""
    output = attempt["output"]
    pending, target = output / (name + ".pending"), output / name
    row = dict(name=name, pending=str(pending), target=str(target), stage="write", visible=False)
    attempt["writes"].append(row)
    snapshot.write_json(pending, value)
    row["stage"] = "link"
    os.link(pending, target)
    row.update(stage="directory_fsync", visible=True, durability="unconfirmed")
    descriptor = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    row.update(stage="durable", durability="confirmed")
    return dict(path=str(target), sha256=snapshot.digest(target))


def _secondary(attempt, label, error):
    attempt["last_secondary"] = label, error
    try:
        attempt["secondary"].append((label, error))
    except BaseException as recording:
        attempt["last_secondary_recording_error"] = recording


@contextmanager
def _observing(attempt):
    """Visible nested calls counted; C implementation internals stay opaque.

    Call admission runs after each inherited hook and examines the executing
    frame/delegate, not just the mutable function about to be called. Original
    unwind errors retain precedence over secondary observer/cleanup errors.
    """
    prior, local = (sys.getprofile(), sys.gettrace()), {}
    binding, primary = attempt["binding"], None

    def admit(frame, event, arg):
        current = attempt.get("current")
        if (
            current is not None
            and frame is current[1]
            and event in ("line", "opcode")
            and attempt.get("pending_primary") is None
        ):
            _, _, delegate, args, keywords = current
            _require(not attempt["invalid"], "Incomplete common-start RNG observation")
            _check_runtime(binding)
            _require(
                frame.f_locals.get("delegate") is delegate
                and frame.f_locals.get("args") is args
                and frame.f_locals.get("keywords") is keywords
                and not attempt["invalid"],
                "Original RNG call-instruction dispatch changed",
            )
        direct = current is not None and (
            event == "call"
            and frame.f_back is current[1]
            or event == "c_call"
            and frame is current[1]
        )
        if direct:
            _, _, delegate, args, keywords = current
            _check_runtime(binding)
            _require(
                not attempt["invalid"] and sys.getprofile() is profile and sys.gettrace() is trace,
                "Both original inherited/RNG observers required",
            )
            caller = frame.f_back if event == "call" else frame
            _require(
                caller.f_locals.get("args") is args
                and caller.f_locals.get("keywords") is keywords
                and caller.f_locals.get("delegate") is delegate,
                "Original RNG operation argument/dispatch locals changed",
            )
            if event == "call":
                function = getattr(delegate, "__func__", delegate)
                _require(
                    frame.f_code is getattr(function, "__code__", None)
                    and frame.f_globals is getattr(function, "__globals__", None)
                    and frame.f_builtins is vars(builtins)
                    and (
                        current[0]["delegate"].startswith("numpy_")
                        or type(delegate) is MethodType
                        and frame.f_locals.get("self") is binding["python"]
                    ),
                    "Exact actual RNG callable entry frame required",
                )
                if args and current[0]["delegate"] == "python_seed":
                    _require(
                        type(frame.f_locals.get("a")) is int
                        and frame.f_locals["a"] == args[0]
                        and type(frame.f_locals.get("version")) is int
                        and frame.f_locals["version"] == 2,
                        "Actual Python seed/version arguments changed",
                    )
            else:
                _require(arg is delegate, "Exact original NumPy RNG C entry required")
        receiver = (
            getattr(arg, "__self__", None) if event.startswith("c_") else frame.f_locals.get("self")
        )
        rng = receiver is binding["python"] or receiver is binding["numpy"]
        if direct or rng:
            raw = (frame, event, arg)
            attempt["last_observer_raw"] = raw
            attempt["observed_calls"].append(raw)
            _require(
                len(attempt["observed_calls"]) <= 256, "Bounded common-start RNG observer work"
            )
            if event in ("call", "c_call"):
                _require(current is not None, "No RNG call outside the declared program operation")
        if (
            current is not None
            and event == "c_call"
            and receiver is binding["python"]
            and current[0]["delegate"] == "python_seed"
            and getattr(arg, "__name__", None) == "seed"
        ):
            _require(
                type(frame.f_locals.get("a")) is int
                and frame.f_locals["a"] == current[3][0]
                and type(frame.f_locals.get("version")) is int
                and frame.f_locals["version"] == 2,
                "Declared Python seed argument changed at its C delegate",
            )

    def inherited(fn, frame, event, arg):
        if fn is None:
            return None
        try:
            return fn(frame, event, arg)
        except BaseException as error:
            attempt["invalid"] = True
            if attempt.get("pending_primary") is None:
                attempt["pending_primary"] = error
                attempt["pending_traceback"] = error.__traceback__
                attempt["pending_origin"] = ("inherited", frame, event)
            _secondary(attempt, "inherited_" + event, error)
            if event not in ("return", "exception", "c_return", "c_exception"):
                raise
            return None

    def profile(frame, event, arg):
        inherited(prior[0], frame, event, arg)
        try:
            admit(frame, event, arg)
        except BaseException as error:
            attempt["invalid"] = True
            _secondary(attempt, "profile_" + event, error)
            if event not in ("return", "c_return", "c_exception"):
                raise

    def trace(frame, event, arg):
        current = attempt.get("current")
        if (
            event == "exception"
            and current is not None
            and (frame is current[1] or frame.f_back is current[1])
            and attempt.get("pending_primary") is None
        ):
            # Retain the actual source exception before a return observer can
            # reject. Let its original handler/unwind execute, without a later
            # caller opcode guard substituting a secondary coverage error.
            attempt["pending_primary"] = arg[1]
            attempt["pending_traceback"] = arg[2]
            attempt["pending_origin"] = ("source", frame, event)
        fn = prior[1] if event == "call" else local.get(id(frame))
        result = inherited(fn, frame, event, arg)
        if event == "return":
            local.pop(id(frame), None)
        elif result is not None:
            local[id(frame)] = result
        try:
            admit(frame, event, arg)
        except BaseException as error:
            attempt["invalid"] = True
            _secondary(attempt, "trace_" + event, error)
            if event not in ("return", "exception"):
                raise
        return trace

    try:
        expected_prior = attempt.get("observer_prior", prior)
        _require(
            prior[0] is expected_prior[0] and prior[1] is expected_prior[1],
            "Original caller observer hooks required before RNG entry",
        )
        sys.setprofile(profile)
        sys.settrace(trace)
        attempt["observer_yielded"] = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        attempt["current"] = None
        for name, getter, setter, original in (
            ("trace", sys.gettrace, sys.settrace, prior[1]),
            ("profile", sys.getprofile, sys.setprofile, prior[0]),
        ):
            for _index in range(3):
                try:
                    setter(original)
                    if getter() is original:
                        break
                except BaseException as error:
                    attempt["invalid"] = True
                    _secondary(attempt, name + "_recovery", error)
        final = []
        for name, getter in (("profile", sys.getprofile), ("trace", sys.gettrace)):
            try:
                final.append(getter())
            except BaseException as error:
                _secondary(attempt, name + "_final", error)
                final.append(None)
        attempt["hooks_restored"] = final[0] is prior[0] and final[1] is prior[1]
        if not attempt["hooks_restored"]:
            attempt["invalid"] = True
            if primary is None:
                raise ValueError("Both inherited RNG observers must be restored")


def _execute_program(program, attempt):
    binding = attempt["binding"]
    for label, name, argument in STEPS:
        _require(not attempt["invalid"], "Incomplete/reentrant common-start program")
        _require(
            program.identity == _digest(program_document(program)), "Declared RNG program changed"
        )
        _check_runtime(binding)
        row = dict(
            label=label, delegate=name, arguments=None, status="entered", raw=None, bits=None
        )
        attempt["operations"].append(row)
        delegate = binding["delegates"][name]
        args = () if argument is None else (getattr(program, argument),)
        keywords = {"version": 2} if name == "python_seed" else {}
        row["arguments"] = args, keywords
        try:
            attempt["current"] = row, sys._getframe(), delegate, args, keywords
            attempt["current"][1].f_trace_opcodes = True
            row["raw"] = delegate(*args, **keywords)
            attempt["current"] = None
            row["status"] = "returned"
            _require(not attempt["invalid"], "Incomplete common-start RNG observation")
            _check_runtime(binding)
            if argument is None:
                row["bits"] = _state(row["raw"], "python" if name == "python_get" else "numpy")
                attempt["states"][label] = row["bits"]
                _save(attempt, label + ".json", row["bits"])
            else:
                _require(row["raw"] is None, "Original seed returns None")
        except BaseException as error:
            attempt["current"] = None
            row["error"], row["status"] = error, "failed"
            raise
    for kind in ("python", "numpy"):
        _require(
            attempt["states"][kind + "_after"] == attempt["states"][kind + "_readback"],
            "RNG state changed between seed observation and independent readback",
        )


def initialize(program, state, *, role, output, enabled=False):
    """One genuine call before world. Failed calls consume this process too.

    Cells uses its real _call(state,'common_start_rng',initialize,program,state,
    role='cells',output=...,enabled=True) immediately after parameters. Original
    calls directly in _workflow at original_runner before _capture_initial_rng.
    Neither a record nor a supplied state tuple is an accepted input.
    """
    global _ATTEMPT
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise CommonStartRejected("Explicit common-start RNG execution held", stage="release")
    with _LOCK:
        if _ATTEMPT is not None:
            _ATTEMPT["invalid"] = True
            raise CommonStartRejected(
                "Common-start attempt is irreversible", stage="once", partial=_ATTEMPT
            )
        attempt = dict(
            stage="declaration",
            primary=None,
            secondary=[],
            states={},
            operations=[],
            writes=[],
            output=None,
            binding=None,
            boundary=None,
            runtime_before=None,
            runtime_after=None,
            record=None,
            invalid=False,
            thread=get_ident(),
            observed_calls=[],
            current=None,
            last_observer_raw=None,
            hooks_restored=None,
            pending_primary=None,
            pending_traceback=None,
            pending_origin=None,
            body_primary=None,
            observer_prior=None,
            observer_hook_api=None,
            observer_manager=None,
            observer_generator=None,
            observer_yielded=False,
            observer_entered=False,
            observer_cleanup_errors=[],
            observer_cleanup_complete=False,
            reporting_held=False,
            sampling_audit_acknowledged=False,
        )
        _ATTEMPT = attempt
    manager, generator, prior, hook_api = None, None, None, None
    try:
        # Retain actual APIs/hooks before any fallible observer entry. Recovery
        # below is in this caller, independent of contextlib.__exit__ admission.
        hook_api = (
            ("trace", sys.gettrace, sys.settrace, 1),
            ("profile", sys.getprofile, sys.setprofile, 0),
        )
        prior = (hook_api[1][1](), hook_api[0][1]())
        attempt["observer_prior"], attempt["observer_hook_api"] = prior, hook_api
        try:
            _install_sampling_audit()
            attempt["sampling_audit_acknowledged"] = True
            document = program_document(program)
            _require(
                program.identity == _digest(document) and role in CONSUMERS,
                "Sealed program and exact consumer role required",
            )
            _require(
                active_count() == 1 and get_ident() == main_thread().ident,
                "Single Python thread required for global RNG initialization",
            )
            attempt["stage"] = "boundary"
            attempt["boundary"] = _boundary(program, state, role, sys._getframe(1))
            path = Path(output).resolve()
            _require(
                not path.exists()
                and path.is_relative_to(Path("/mnt/workspaces/Cells"))
                and not path.is_relative_to(Path(__file__).resolve().parents[2]),
                "Fresh contained non-source RNG evidence directory required",
            )
            path.mkdir(parents=True)
            attempt["output"] = path
            attempt["stage"] = "runtime"
            attempt["binding"] = _runtime()
            attempt["runtime_before"] = provenance.binding()
            _save(attempt, "program.json", dict(document, identity=program.identity))
            attempt["stage"] = "program"
            manager = _observing(attempt)
            generator = vars(manager).get("gen")
            attempt["observer_manager"], attempt["observer_generator"] = manager, generator
            _require(
                type(generator) is GeneratorType
                and generator.gi_code is _observing.__wrapped__.__code__,
                "Actual original RNG observation generator required",
            )
            with manager:
                attempt["observer_entered"] = True
                try:
                    _execute_program(program, attempt)
                    _require(not attempt["invalid"], "Reentrant common-start attempt poisoned")
                    attempt["runtime_after"] = provenance.binding()
                    _require(
                        attempt["runtime_before"] == attempt["runtime_after"],
                        "Actual RNG runtime changed",
                    )
                    _check_runtime(attempt["binding"])
                    _same_function(attempt["boundary"][-1])
                except BaseException as error:
                    # Retain this before contextlib can be refused at CALL.
                    attempt["body_primary"] = (
                        error,
                        error.__cause__,
                        error.__context__,
                        error.__traceback__,
                    )
                    if attempt["pending_primary"] is None:
                        attempt["pending_primary"] = error
                        attempt["pending_traceback"] = error.__traceback__
                        attempt["pending_origin"] = ("body", None, "exception")
                    raise
        except BaseException as error:
            # This also covers declaration/runtime/program.json failures,
            # before the observation body exists. Cleanup is secondary.
            attempt["outer_body_primary"] = (
                error,
                error.__cause__,
                error.__context__,
                error.__traceback__,
            )
            if attempt["pending_primary"] is None:
                attempt["pending_primary"] = error
                attempt["pending_traceback"] = error.__traceback__
                attempt["pending_origin"] = ("outer_body", None, "exception")
            raise
        finally:
            attempt["outer_cleanup_started"] = True
            attempt["current"] = None
            if type(generator) is GeneratorType and generator.gi_frame is not None:
                try:
                    generator.close()
                except BaseException as error:
                    attempt["invalid"] = True
                    if attempt["pending_primary"] is None:
                        attempt["pending_primary"] = error
                        attempt["pending_traceback"] = error.__traceback__
                        attempt["pending_origin"] = ("cleanup", None, "generator_close")
                    attempt["last_cleanup_error"] = ("generator_close", error, generator)
                    try:
                        attempt["observer_cleanup_errors"].append(("generator_close", error))
                    except BaseException as recording:
                        attempt["last_cleanup_recording_error"] = recording
            # Inline and independent: a rejected helper entry or one failing
            # setter must not skip the other hook. No evidence callback yet.
            for name, getter, setter, index in hook_api:
                for ordinal in range(3):
                    try:
                        setter(prior[index])
                        if getter() is prior[index]:
                            break
                    except BaseException as error:
                        attempt["invalid"] = True
                        if attempt["pending_primary"] is None:
                            attempt["pending_primary"] = error
                            attempt["pending_traceback"] = error.__traceback__
                            attempt["pending_origin"] = ("cleanup", None, name)
                        attempt["last_cleanup_error"] = (name, error, ordinal)
                        try:
                            attempt["observer_cleanup_errors"].append((name, error))
                        except BaseException as recording:
                            attempt["last_cleanup_recording_error"] = recording
            final = [None, None]
            sample = dict(changed=False, last_mutation=None)
            _SAMPLING.append(sample)
            try:
                for name, getter, _setter, index in hook_api:
                    try:
                        final[index] = getter()
                    except BaseException as error:
                        attempt["invalid"] = True
                        if attempt["pending_primary"] is None:
                            attempt["pending_primary"] = error
                            attempt["pending_traceback"] = error.__traceback__
                            attempt["pending_origin"] = ("cleanup", None, name + "_final")
                        attempt["last_cleanup_error"] = (name + "_final", error, None)
            finally:
                # No helper entry/callback is needed to retire the window.
                for index in range(len(_SAMPLING) - 1, -1, -1):
                    if _SAMPLING[index] is sample:
                        del _SAMPLING[index]
            attempt["outer_hook_sample"] = sample
            attempt["outer_final_hooks"] = tuple(final)
            attempt["hooks_restored"] = (
                attempt["sampling_audit_acknowledged"]
                and not sample["changed"]
                and final[0] is prior[0]
                and final[1] is prior[1]
            )
            attempt["observer_closed"] = generator is None or (
                type(generator) is GeneratorType and generator.gi_frame is None
            )
            attempt["observer_cleanup_complete"] = (
                attempt["hooks_restored"] and attempt["observer_closed"]
            )
        _require(attempt["observer_cleanup_complete"], "RNG observer cleanup unresolved")
        _require(not attempt["invalid"], "Incomplete common-start publication")
        # Publication follows verified closure; a refused __exit__ cannot
        # publish a completed program marker before its cleanup runs.
        attempt["stage"] = "publication"
        binding = attempt["binding"]
        record = dict(
            kind=KIND,
            status="completed",
            program=document,
            program_identity=program.identity,
            role=role,
            pid=os.getpid(),
            epoch=EPOCH,
            source=dict(
                helper=FILE,
                helper_sha256=snapshot.digest(Path(__file__)),
                provenance=provenance.FILE,
                provenance_sha256=PROVENANCE_SHA256,
            ),
            runtime=attempt["runtime_after"],
            generator_identities=dict(python=id(binding["python"]), numpy=id(binding["numpy"])),
            state=attempt["states"],
            operations=[[r["label"], r["status"]] for r in attempt["operations"]],
            work=dict(
                program_API_calls=len(attempt["operations"]),
                visible_RNG_observer_events=len(attempt["observed_calls"]),
                opaque_C_internals_not_independent_cases=True,
                inherited_observer_RNG_effects_require_reviewed_caller_contract=True,
            ),
            states_loaded=False,
            generators_replaced=False,
            biological_or_phase_admission=False,
        )
        _save(attempt, "COMPLETED.json", record)
        attempt["record"] = record
        return record
    except BaseException as escaped:
        pending = attempt["pending_primary"]
        primary = escaped if pending is None else pending
        attempt["primary"] = primary
        attempt["invalid"] = True
        if escaped is not primary:
            attempt["escaped_error"] = (escaped, escaped.__cause__, escaped.__traceback__)
        if attempt["record"] is not None:
            attempt["unaccepted_record"], attempt["record"] = attempt["record"], None
        if not attempt["observer_cleanup_complete"]:
            # Raw _ATTEMPT remains available, including primary/partial bits;
            # unsafe exception attachment/reporters cannot run under lost hooks.
            attempt["reporting_held"] = True
            if primary is escaped:
                raise
            # Keep the actual cause; the escaped observer is retained separately.
            raise primary  # noqa: B904
        if escaped is not primary:
            try:
                _secondary(attempt, "scope_exit", escaped)
            except BaseException as recording:
                attempt["last_secondary_recording_error"] = recording
        for label, error in attempt["observer_cleanup_errors"]:
            try:
                _secondary(attempt, label, error)
            except BaseException as recording:
                attempt["last_secondary_recording_error"] = recording
        try:
            primary.common_start_attempt = attempt
        except BaseException as secondary:
            try:
                _secondary(attempt, "attachment", secondary)
            except BaseException as recording:
                attempt["last_secondary_recording_error"] = recording
        if attempt["output"] is not None:
            try:
                _save(
                    attempt,
                    "failure.json",
                    dict(
                        kind=KIND,
                        status="failed",
                        stage=attempt["stage"],
                        primary=dict(type=type(primary).__name__, message=str(primary)),
                        states=attempt["states"],
                        operations=[(r["label"], r["status"]) for r in attempt["operations"]],
                        writes=list(attempt["writes"]),
                        automatic_retry=False,
                        rng_restore_attempted=False,
                    ),
                )
            except BaseException as secondary:
                try:
                    _secondary(attempt, "failure_evidence", secondary)
                except BaseException as recording:
                    attempt["last_secondary_recording_error"] = recording
        if primary is escaped:
            raise
        raise primary  # noqa: B904 -- preserve its original cause rather than replace it.


def _saved_state(value, kind):
    def bits(row):
        _require(
            type(row) is dict
            and set(row) == {"float64_bits"}
            and type(row["float64_bits"]) is str
            and len(row["float64_bits"]) == 16,
            "Complete binary64 state cache required",
        )
        _require(len(bytes.fromhex(row["float64_bits"])) == 8, "Exact binary64 bits required")

    _require(type(value) is list, "Exact saved state container required")
    if kind == "python":
        _require(
            len(value) == 3
            and type(value[0]) is int
            and value[0] == 3
            and type(value[1]) is list
            and len(value[1]) == 625
            and all(type(word) is int and 0 <= word < 2**32 for word in value[1][:-1])
            and type(value[1][-1]) is int
            and 0 <= value[1][-1] <= 624,
            "Complete saved Python words and index required",
        )
        if value[2] is not None:
            bits(value[2])
    else:
        _require(
            len(value) == 5 and value[0] == "MT19937" and type(value[1]) is dict,
            "Complete saved NumPy state required",
        )
        words = value[1]
        _require(
            set(words) == {"__ndarray__", "dtype", "shape", "strides", "raw_bytes_hex"}
            and words["__ndarray__"] is True
            and words["dtype"] in ("<u4", ">u4")
            and words["shape"] == [624]
            and words["strides"] == [4]
            and type(words["raw_bytes_hex"]) is str
            and len(words["raw_bytes_hex"]) == 4992
            and len(bytes.fromhex(words["raw_bytes_hex"])) == 2496
            and type(value[2]) is int
            and 0 <= value[2] <= 624
            and type(value[3]) is int
            and value[3] in (0, 1),
            "Complete saved NumPy word bytes/layout/index required",
        )
        bits(value[4])


def compare(cells, original):
    """Compare saved data only; never apply it to a generator or issue an owner."""
    for row, role in ((cells, "cells"), (original, "original")):
        _require(
            type(row) is dict
            and row.get("kind") == KIND
            and row.get("status") == "completed"
            and row.get("role") == role
            and row.get("epoch") == EPOCH
            and row.get("states_loaded") is False
            and row.get("generators_replaced") is False,
            "Complete explicit program receipts required; ambient witnesses do not qualify",
        )
        _require(
            type(row.get("pid")) is int
            and row["pid"] > 0
            and row["program_identity"] == _digest(row["program"])
            and row["operations"] == [[label, "returned"] for label, _, _ in STEPS],
            "Exact complete input program and operations required",
        )
        doc = row["program"]
        reconstructed = declare(
            python_seed=doc["python_seed"],
            numpy_seed=doc["numpy_seed"],
            input_identity=doc["input_identity"],
            consumer_sources=doc["consumer_sources"],
        )
        _require(
            program_document(reconstructed) == doc, "Canonical explicit input program required"
        )
        _require(
            type(row["state"]) is dict
            and set(row["state"])
            == {
                kind + "_" + suffix
                for kind in ("python", "numpy")
                for suffix in ("before", "after", "readback")
            },
            "Complete before/after/readback state records required",
        )
    _require(
        cells["pid"] != original["pid"]
        and cells["program"] == original["program"]
        and cells["runtime"] == original["runtime"],
        "Distinct fresh processes and common program/runtime required",
    )
    _require(
        cells["source"] == original["source"]
        and _pin(cells["source"]["helper_sha256"])
        and cells["source"]["helper"] == FILE
        and cells["source"]["provenance_sha256"] == PROVENANCE_SHA256,
        "Exact common-start helper/provenance producer required",
    )
    for kind in ("python", "numpy"):
        for receipt in (cells, original):
            for suffix in ("before", "after", "readback"):
                _saved_state(receipt["state"][kind + "_" + suffix], kind)
        state = cells["state"][kind + "_after"]
        _require(
            state
            == cells["state"][kind + "_readback"]
            == original["state"][kind + "_after"]
            == original["state"][kind + "_readback"],
            "Common bit-exact starting state not established",
        )
    return dict(
        kind=KIND,
        shared_start_bits_match=True,
        program_identity=cells["program_identity"],
        solver_or_biological_or_checkpoint_credit=0,
        states_replayed=False,
    )
