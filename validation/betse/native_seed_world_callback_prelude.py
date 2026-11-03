"""Held genuine callback ancestry before the first native BETSE import.

The auxiliary selected configuration/Simulator belong ONLY to the callback
prelude. They never supply the fresh Key parameters or the world's phase.sim.
No application singleton, testing cache, callback or owner is hydrated/reset.
"""

import ast
import builtins
import importlib
import json
import os
import resource
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from threading import get_ident
from types import CodeType, FunctionType
from weakref import WeakKeyDictionary

from validation import source_snapshot as snapshot

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/native_seed_world_callback_prelude.py"
RELEASE = "CELLS_NATIVE_SEED_WORLD_CALLBACK_PRELUDE_RELEASED"
KIND = "cells.native_seed_world_callback_bootstrap@1"
RUNTIME_MODULE = "validation.betse.betse_native_parameter_world_ready_qualification"
RUNTIME_SOURCE_SHA256 = RUNTIME_REVIEW_SHA256 = None
MODULES = {
    "tissue": "cells.processes.betse_native_tissue_configuration",
    "simulator": "cells.processes.betse_native_simulator_construction",
    "callbacks": "cells.processes.betse_native_phase_callbacks",
}
SOURCE_PINS = dict(
    tissue="0dd4e51887e5975e5356e5efe946a3c19a2c969c54049955c6886bc199f98bb5",
    simulator="8f68eaa22a6225b044e0dbd87475ace0439443aa490369fb42612b54f3ae12ce",
    callbacks="4fa19547caac95257162e6678092c3e55ce4fe43b05b2d16f7908f9196740f2d",
)
POLICY = dict(cpu=0, threads=1, bytes=2**30, wall_seconds=480, reserve_bytes=8 * 2**30)
_RETAINED = WeakKeyDictionary()
_ACTIVE = []


class PreludeRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None, source_error=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.partial = stage, partial
        self.source_error, self.capture_errors = source_error, tuple(capture_errors)


@dataclass(slots=True)
class Execution:
    stage: str = "preflight"
    thread: int = field(default_factory=get_ident)
    requests: list = field(default_factory=list)
    parents: list = field(default_factory=list)
    trials: list = field(default_factory=list)
    operations: list = field(default_factory=list)
    capture_errors: list = field(default_factory=list)
    last_return: object = None
    source_error: object = None
    primary: object = None
    callback: object = None
    completed: bool = False
    observed_application: object = None
    observed_testing_cache: object = None
    runtime_before: object = None
    entry_error: object = None
    path_links: tuple = ()

    def __reduce_ex__(self, protocol):
        raise TypeError("Prelude live ancestry is not checkpoint/hydration authority")


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def source_plan():
    return dict(
        boundary="genuine selected tissue -> Simulator -> native callback, before world birth",
        source_pins=dict(SOURCE_PINS),
        runtime_source=RUNTIME_SOURCE_SHA256,
        runtime_review=RUNTIME_REVIEW_SHA256,
        before_first_betse_import=True,
        native_order=(
            "tissue.from_configuration",
            "tissue.prepare",
            "simulator.from_tissue",
            "simulator.prepare(enabled=True)",
            "callbacks.from_simulator",
            "callbacks.prepare(enabled=True)",
        ),
        actual_application_observation_required=True,
        auxiliary_objects_are_world_parameter_or_phase_sim_authority=False,
        supplied_singleton_callback_testing_cache_or_serialized_owner=False,
        preserve_existing_native_testing_branch=True,
        progress_ranged_or_default_phase_caller_order_admitted=False,
        runtime=dict(POLICY),
        filesystem_conflicts=dict(
            native_dot_directory=str(Path.home() / ".betse"),
            native_default_logfile=str(Path.home() / ".betse/betse.log"),
            native_HOME_unchanged=True,
            existing_native_dot_link=(
                _link_record(Path.home() / ".betse")
                if (Path.home() / ".betse").is_symlink()
                else None
            ),
            matplotlib_cache=(
                "exact caller-declared MPLCONFIGDIR or native default; no silent rewrite"
            ),
            strict_mnt_output_policy_conflicts_with_default_native_dot_directory=True,
            explicit_Root_bootstrap_exception_and_enclosing_audit_required=True,
        ),
        native_or_scientific_release=False,
        invalidated_owners=11,
        held_postcut_cases=12,
    )


def _fresh_native():
    existing = tuple(name for name in sys.modules if name == "betse" or name.startswith("betse."))
    if existing:
        raise PreludeRejected(
            "Preinitialized/unobserved native modules cannot supply callback ancestry",
            stage="native_before",
            partial=existing,
        )


def _path(name):
    return ROOT / (
        ("" if name.startswith("validation.") else "src/") + name.replace(".", "/") + ".py"
    )


def _import_bound(name, pin):
    path = _path(name)
    if not _pin(pin) or path.is_symlink() or snapshot.digest(path) != pin:
        raise PreludeRejected("Exact reviewed prelude producer required", stage="producer")
    module = importlib.import_module(name)
    if Path(module.__file__).resolve() != path or sys.modules.get(name) is not module:
        raise PreludeRejected("Actual current immutable module required", stage="producer")
    return module


def _function(module, name):
    """Authenticate direct public code without entering or importing native bodies."""
    function = vars(module).get(name)
    if (
        type(function) is not FunctionType
        or function.__globals__ is not vars(module)
        or function.__builtins__ is not vars(builtins)
        or function.__closure__ is not None
    ):
        raise PreludeRejected("Original public prelude function required", stage="function")
    filename = str(Path(module.__file__).resolve())
    tree = ast.parse(Path(filename).read_bytes())
    definition = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    defaults = tuple(ast.literal_eval(node) for node in definition.args.defaults) or None
    keywords = {
        argument.arg: ast.literal_eval(value)
        for argument, value in zip(
            definition.args.kwonlyargs, definition.args.kw_defaults, strict=True
        )
        if value is not None
    } or None
    if (
        _code(function.__defaults__) != _code(defaults)
        or (function.__kwdefaults__ is None) != (keywords is None)
        or (
            keywords is not None
            and (
                type(function.__kwdefaults__) is not dict
                or tuple(function.__kwdefaults__) != tuple(keywords)
                or any(
                    _code(function.__kwdefaults__[key]) != _code(value)
                    for key, value in keywords.items()
                )
            )
        )
    ):
        raise PreludeRejected("Public prelude default/delegate changed", stage="function")
    compiled = compile(tree, filename, "exec", dont_inherit=True)
    code = next(
        code for code in compiled.co_consts if type(code) is CodeType and code.co_name == name
    )
    if _code(function.__code__) != _code(code) or function.__code__.co_filename != filename:
        raise PreludeRejected("Public prelude callable/code changed", stage="function")
    return function


def _code(value):
    """Typed metadata only: CodeType equality alone merges signed-zero constants."""
    kind = type(value)
    if kind is CodeType:
        return (
            kind,
            value.co_argcount,
            value.co_posonlyargcount,
            value.co_kwonlyargcount,
            value.co_flags,
            value.co_code,
            tuple(_code(item) for item in value.co_consts),
            value.co_names,
            value.co_varnames,
            value.co_freevars,
            value.co_cellvars,
            value.co_exceptiontable,
        )
    if kind is float:
        return kind, struct.pack(">d", value)
    if kind is complex:
        return kind, struct.pack(">dd", value.real, value.imag)
    if kind in (tuple, frozenset):
        items = tuple(_code(item) for item in value)
        return kind, frozenset(items) if kind is frozenset else items
    if value is None or kind in (str, bytes, int, bool):
        return kind, value
    raise PreludeRejected("Unknown public callable constant", stage="function")


def _dependencies():
    if not _pin(RUNTIME_SOURCE_SHA256) or not _pin(RUNTIME_REVIEW_SHA256):
        raise PreludeRejected("Corrected Key runtime producer remains unadopted", stage="unbound")
    runtime = _import_bound(RUNTIME_MODULE, RUNTIME_SOURCE_SHA256)
    _function(runtime, "_runtime_entry")
    return runtime


def _bootstrap_input(path, sha256, directory):
    path, directory = Path(path), Path(directory)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise PreludeRejected("Original unlinked bootstrap declaration required", stage="bootstrap")
    if snapshot.digest(path) != sha256 or path.stat().st_size > 2**20:
        raise PreludeRejected("Exact bounded bootstrap declaration required", stage="bootstrap")
    declaration = json.loads(path.read_text())
    if set(declaration) != {
        "kind",
        "runtime",
        "environment",
        "native_write_roots",
        "native_links",
        "Root_review",
    }:
        raise PreludeRejected(
            "Exact bootstrap/runtime/write declaration required", stage="bootstrap"
        )
    if declaration["kind"] != KIND or not _pin(declaration["Root_review"]):
        raise PreludeRejected("Root-reviewed bootstrap policy required", stage="bootstrap")
    if not directory.is_absolute() or not directory.is_relative_to("/mnt/workspaces/Cells"):
        raise PreludeRejected(
            "Evidence outputs must be under /mnt/workspaces/Cells", stage="output"
        )
    if directory.exists() or any(p.is_symlink() for p in (directory, *directory.parents)):
        raise PreludeRejected("Fresh unlinked output required", stage="output")
    # The native constructor writes its actual .betse/log path. This is a
    # declared bootstrap exception, not relocation of HOME or numeric output.
    native_home = str(Path.home() / ".betse")
    roots = declaration["native_write_roots"]
    if type(roots) is not list or native_home not in roots:
        raise PreludeRejected(
            "Native home/log writes conflict with strict output policy", stage="native_writes"
        )
    links = declaration["native_links"]
    if type(links) is not dict or set(links) - {native_home}:
        raise PreludeRejected(
            "Only the declared existing native home link is supported", stage="native_writes"
        )
    if Path(native_home).is_symlink():
        actual = _link_record(Path(native_home))
        target = Path(actual["resolved"])
        if (
            links.get(native_home) != actual
            or actual["resolved"] not in roots
            or not target.is_relative_to("/mnt/workspaces/Cells")
            or any(p.is_symlink() for p in (target, *target.parents))
        ):
            raise PreludeRejected(
                "Exact existing native-home link/target binding required", stage="native_writes"
            )
    elif links:
        raise PreludeRejected(
            "Declared native link is not the actual live path", stage="native_writes"
        )
    for raw in roots:
        root = Path(raw)
        if str(root) == native_home and root.is_symlink():
            if any(p.is_symlink() for p in root.parents):
                raise PreludeRejected("Native-home parent links refused", stage="native_writes")
            continue
        if (
            not root.is_absolute()
            or root in (Path("/"), Path.home(), Path("/home"))
            or ".." in root.parts
            or str(root) != str(root.resolve(strict=False))
        ):
            raise PreludeRejected(
                "Narrow actual native cache/log roots required", stage="native_writes"
            )
        if any(p.is_symlink() for p in (root, *root.parents)):
            raise PreludeRejected("Linked native write root refused", stage="native_writes")
    environment = declaration["environment"]
    required = {"HOME", "MPLCONFIGDIR", "PYTHONDONTWRITEBYTECODE"}
    if type(environment) is not dict or set(environment) != required:
        raise PreludeRejected("Declare actual unchanged bootstrap environment", stage="environment")
    if any(os.environ.get(name) != value for name, value in environment.items()):
        raise PreludeRejected(
            "Bootstrap environment changed; no automatic rewrite", stage="environment"
        )
    if environment["PYTHONDONTWRITEBYTECODE"] != "1":
        raise PreludeRejected("Undeclared library bytecode writes refused", stage="environment")
    mpl = environment["MPLCONFIGDIR"]
    if type(mpl) is not str or not Path(mpl).is_absolute() or mpl not in roots:
        raise PreludeRejected("Exact Matplotlib cache root must be declared", stage="native_writes")
    return declaration


def _link_record(path):
    """Filesystem provenance only, never a native object or source-code alias."""
    stat = path.lstat()
    return dict(
        text=os.readlink(path),
        resolved=str(path.resolve(strict=True)),
        device=stat.st_dev,
        inode=stat.st_ino,
        mode=stat.st_mode,
        mtime_ns=stat.st_mtime_ns,
        ctime_ns=stat.st_ctime_ns,
    )


def _check_links(state):
    for path, record in state.path_links:
        if json.dumps(_link_record(Path(path)), sort_keys=True, allow_nan=False) != record:
            raise PreludeRejected("Native cache/log path link changed", stage="native_writes")


def _resources():
    limits = resource.getrlimit(resource.RLIMIT_AS)
    if os.sched_getaffinity(0) != {0} or any(n <= 0 or n > POLICY["bytes"] for n in limits):
        raise PreludeRejected("Native CPU0/1GiB resource envelope required", stage="resources")
    if (
        any(
            os.environ.get(n) != "1"
            for n in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        )
        or os.environ.get("CUDA_VISIBLE_DEVICES") != ""
    ):
        raise PreludeRejected(
            "One native CPU thread without GPU visibility required", stage="resources"
        )


def _operation(state, name, function, *args, **kwargs):
    if state.entry_error is not None:
        raise state.entry_error
    _check_links(state)
    state.stage = name
    row = dict(sequence=len(state.operations), stage=name, status="attempted")
    state.operations.append(row)
    try:
        returned = function(*args, **kwargs)
    except BaseException as primary:
        row["status"], row["primary"] = "source_failed", primary
        state.source_error = primary
        try:
            _check_links(state)
        except BaseException as capture:
            state.capture_errors.append(("failed_source_path_check", capture, primary))
        raise
    state.last_return = returned
    row["status"], row["returned"] = "returned", returned
    _check_links(state)
    if state.entry_error is not None:
        raise state.entry_error
    return returned


def _capture(state, evidence, label, value):
    try:
        if not evidence.save(label, value):
            raise RuntimeError("Prelude typed observation refused: " + label)
    except BaseException as capture:
        state.capture_errors.append((label, capture, value))
        raise


def _execute(state, modules, configuration, evidence):
    parent = configuration
    for label, factory in (
        ("tissue", "from_configuration"),
        ("simulator", "from_tissue"),
        ("callbacks", "from_simulator"),
    ):
        module = modules[label]
        request = _operation(
            state, label + "_request", getattr(module, factory), parent, law_id=module.LAW_ID
        )
        state.requests.append((label, request))
        keywords = {} if label == "tissue" else dict(enabled=True)
        if label == "tissue":
            _fresh_native()  # Metadata/request observation cannot preinitialize the application.
        parent = _operation(state, label, module.prepare, request, **keywords)
        state.parents.append((label, parent))
        trial = parent.trial
        state.trials.append((label, trial))
        _capture(state, evidence, label + ".trial", module.trial_record(trial))
        _capture(state, evidence, label + ".cache", trial.cache)
    actual = modules["callbacks"]._validate(parent)
    _check_links(state)
    if actual.owner is not parent or not actual.trial.factory_completed:
        raise PreludeRejected("Actual completed callback factory required", stage="callback")
    state.observed_application = actual.source.app
    state.observed_testing_cache = actual.after.cache
    state.callback, state.completed = parent, True
    return parent


def _acquire_callback(state, configuration, directory, *, bootstrap, bootstrap_sha256):
    runtime = _dependencies()
    _fresh_native()
    _resources()
    declaration = _bootstrap_input(bootstrap, bootstrap_sha256, directory)
    state.path_links = tuple(
        (path, json.dumps(record, sort_keys=True, allow_nan=False))
        for path, record in declaration["native_links"].items()
    )
    directory = Path(directory)
    directory.mkdir(parents=True)
    evidence = None
    try:
        state.stage = "declared_runtime_bootstrap"
        _function(runtime, "_runtime_entry")(declaration["runtime"])
        _fresh_native()
        modules = {
            name: _import_bound(module, SOURCE_PINS[name]) for name, module in MODULES.items()
        }
        for name, methods in (
            ("tissue", ("from_configuration", "prepare", "trial_record")),
            ("simulator", ("from_tissue", "prepare", "trial_record")),
            ("callbacks", ("from_simulator", "prepare", "trial_record", "_validate")),
        ):
            for method in methods:
                _function(modules[name], method)
        _fresh_native()  # All imports above are definitions; real native work starts below.
        from validation.betse.native_single_cell_prefix_qualification import Evidence

        evidence = Evidence(directory, sidecars=True)
        _execute(state, modules, configuration, evidence)
    except BaseException as primary:
        state.primary = primary
        if evidence is not None:
            try:
                evidence.failure(primary)
            except BaseException as capture:
                state.capture_errors.append(("failure_forensics", capture, primary))
    try:
        snapshot.write_json(
            directory / "outcome.json",
            dict(
                completed=state.completed,
                stage=state.stage,
                primary=None if state.primary is None else type(state.primary).__qualname__,
                capture_errors=[
                    dict(stage=label, type=type(error).__qualname__)
                    for label, error, _ in state.capture_errors
                ],
                captures=[] if evidence is None else evidence.rows,
                api_operations=len(state.operations),
                computational_calls_are_not_cases=True,
                raw_owner_state_serialization_claimed=False,
                native_or_scientific_credit=0,
                auxiliary_p_or_sim_not_world_authority=True,
            ),
        )
    except BaseException as capture:
        state.capture_errors.append(("final_outcome", capture, state))
    if state.primary is not None or state.capture_errors or not state.completed:
        cause = state.primary if state.primary is not None else state.capture_errors[0][1]
        raise PreludeRejected(
            "Genuine callback prelude failed",
            stage=state.stage,
            partial=state,
            source_error=state.source_error,
            capture_errors=state.capture_errors,
        ) from cause
    return state.callback


def acquire_callback(configuration, directory, *, bootstrap, bootstrap_sha256, enabled=False):
    """Return ONLY the existing native callback issuer's live, sealed child."""
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise PreludeRejected("Actual callback prelude remains held", stage="release")
    if _ACTIVE:
        error = PreludeRejected("Reentrant callback prelude attempt", stage="reentrant")
        _ACTIVE[-1].entry_error = error
        raise error
    state = Execution()
    _ACTIVE.append(state)
    returned = None
    try:
        returned = _acquire_callback(
            state,
            configuration,
            directory,
            bootstrap=bootstrap,
            bootstrap_sha256=bootstrap_sha256,
        )
    except BaseException as primary:
        if state.primary is None:
            state.primary = primary
    finally:
        try:
            if not _ACTIVE or _ACTIVE[-1] is not state:
                raise ValueError("Original callback prelude reservation changed")
            _ACTIVE.pop()
        except BaseException as capture:
            state.capture_errors.append(("reservation_release", capture, state))
    primary = state.entry_error if state.entry_error is not None else state.primary
    if primary is not None or state.capture_errors or returned is None:
        if primary is None:
            primary = (
                state.capture_errors[0][1]
                if state.capture_errors
                else ValueError("No callback issued")
            )
        raise PreludeRejected(
            "Actual callback prelude issued no usable child",
            stage=state.stage,
            partial=state,
            source_error=state.source_error,
            capture_errors=state.capture_errors,
        ) from primary
    try:
        _check_links(state)
        _RETAINED[returned] = state
    except BaseException as capture:
        state.capture_errors.append(("retained_ancestry", capture, returned))
        raise PreludeRejected(
            "Final callback ancestry retention failed",
            stage="retention",
            partial=state,
            source_error=state.source_error,
            capture_errors=state.capture_errors,
        ) from capture
    return returned
