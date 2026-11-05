"""Held completed-SIM evidence transport; no owner construction or comparison.

The provider receives the actual returned Key owner. Its already typed payloads
are written directly, and its exact record is published separately. An execution
result still needs the independent saved-artifact finalization in the SIM report.
"""

import ast
import builtins
import importlib
import os
import re
import sys
from pathlib import Path
from types import CodeType, FunctionType, ModuleType, SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_single_cell_prefix_payload as payload

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/native_sim_demo_observation.py"
MODULE = "validation.betse.native_sim_result_observation"
OBSERVER = "validation/betse/native_sim_result_observation.py"
WRITER = "validation/betse/native_seed_demo_evidence.py"
KEY = "src/cells/processes/betse_native_sim_run.py"
KEY_MODULE = "cells.processes.betse_native_sim_run"
SIM = "validation/betse/native_sim_demo.py"
HISTORY = "src/cells/processes/betse_native_sim_history_observation.py"
HISTORY_MODULE = "cells.processes.betse_native_sim_history_observation"
HISTORY_RELEASE = "CELLS_NATIVE_SIM_HISTORY_OBSERVATION_RELEASED"
RELEASE = "CELLS_COMPLETED_SIM_OBSERVATION_RELEASED"
OBSERVER_SHA256 = OBSERVER_REVIEW = None
WRITER_SHA256 = "e3b5228e3622b6baeaa27fd322008ec61c251f477f406dfe38f26f1f875ab4b6"
KIND = "cells.completed_SIM_observation@1"
BINDING_KIND = "cells.completed_SIM_observation_saved_binding@1"
EPOCH = "original_full_SIM_body_end_before_next_FOR_ITER"
OPERATOR_MODES = {
    "original": "original_value_and_flux",
    "disabled": "original_value_only_flux_omitted",
}
_FAILED = []
DECLARATIONS = (
    "KEY_SHA256",
    "KEY_REVIEW",
    "WRITER_SHA256",
    "HISTORY_FILE",
    "HISTORY_MODULE",
    "HISTORY_SHA256",
    "HISTORY_REVIEW",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def _hash(value):
    return type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None


def pin(path):
    path = payload._regular(path)
    require(path.is_file(), "Regular observation file required")
    return dict(path=str(path), sha256=snapshot.digest(path))


def bound(row):
    require(type(row) is dict and set(row) == {"path", "sha256"}, "Exact observation pin required")
    require(_hash(row["sha256"]), "Observation digest required")
    path = payload._regular(row["path"])
    require(path.is_file() and snapshot.digest(path) == row["sha256"], "Observation file changed")
    return path


def constants(path, names):
    values = {}
    for node in ast.parse(Path(path).read_bytes()).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in names:
                require(target.id not in values, "Duplicate observation declaration")
                values[target.id] = ast.literal_eval(node.value)
    require(set(values) == set(names), "Complete observation declarations required")
    return values


def declaration():
    return dict(
        helper=FILE,
        observer=OBSERVER,
        observer_sha256=OBSERVER_SHA256,
        observer_review=OBSERVER_REVIEW,
        writer=WRITER,
        writer_sha256=WRITER_SHA256,
        release=RELEASE,
        history=HISTORY,
        history_module=HISTORY_MODULE,
        history_release=HISTORY_RELEASE,
        enabled=True,
        already_typed_transport=True,
        record_separate=True,
        saved_binding_after_guarded_completion=True,
        comparison_or_physical_credit=False,
    )


def contract(root, policy, files, run_sha):
    """Authenticate a declared source policy without importing any producer."""
    root = Path(root)
    require(
        type(policy) is dict and set(policy) == set(declaration()), "Exact observer policy required"
    )
    require(
        policy["helper"] == FILE
        and policy["observer"] == OBSERVER
        and policy["writer"] == WRITER
        and policy["release"] == RELEASE
        and policy["history"] == HISTORY
        and policy["history_module"] == HISTORY_MODULE
        and policy["history_release"] == HISTORY_RELEASE
        and policy["writer_sha256"] == WRITER_SHA256
        and all(
            policy[name] is True
            for name in (
                "enabled",
                "already_typed_transport",
                "record_separate",
                "saved_binding_after_guarded_completion",
            )
        )
        and policy["comparison_or_physical_credit"] is False,
        "Explicit typed observation-only policy required",
    )
    require(_hash(policy["observer_sha256"]), "Completed SIM observer remains unadopted")
    bound(policy["observer_review"])
    for name, expected in ((OBSERVER, policy["observer_sha256"]), (WRITER, WRITER_SHA256)):
        require(
            files.get(name) == expected and snapshot.digest(root / name) == expected,
            "Observation producer differs from immutable source",
        )
    require(
        _hash(files.get(FILE)) and snapshot.digest(root / FILE) == files[FILE],
        "Observation helper missing from immutable source",
    )
    adopted = constants(root / FILE, ("OBSERVER_SHA256", "OBSERVER_REVIEW"))
    require(
        adopted
        == {
            name: policy[key]
            for name, key in (
                ("OBSERVER_SHA256", "observer_sha256"),
                ("OBSERVER_REVIEW", "observer_review"),
            )
        },
        "Frozen observer adoption and plan differ",
    )
    provider = constants(root / OBSERVER, DECLARATIONS)
    require(
        _hash(run_sha) and provider["KEY_SHA256"] == files.get(KEY) == run_sha,
        "Observer and SIM issuer source differ",
    )
    require(provider["WRITER_SHA256"] == WRITER_SHA256, "Observer transport differs")
    bound(provider["KEY_REVIEW"])
    require(
        _hash(files.get(SIM)) and snapshot.digest(root / SIM) == files[SIM],
        "Frozen SIM issuer declaration missing",
    )
    issuer = constants(root / SIM, ("SOURCE_PINS", "REVIEW_PINS"))
    require(
        type(issuer["SOURCE_PINS"]) is dict
        and type(issuer["REVIEW_PINS"]) is dict
        and issuer["SOURCE_PINS"].get("run") == run_sha
        and issuer["REVIEW_PINS"].get("run") == provider["KEY_REVIEW"]["sha256"],
        "Observation and selected SIM issuer review differ",
    )
    require(
        provider["HISTORY_FILE"] == HISTORY
        and provider["HISTORY_MODULE"] == HISTORY_MODULE
        and _hash(provider["HISTORY_SHA256"])
        and files.get(HISTORY) == provider["HISTORY_SHA256"],
        "Exact completed-history source/module declaration required",
    )
    history_path = bound(dict(path=str(root / HISTORY), sha256=provider["HISTORY_SHA256"]))
    bound(provider["HISTORY_REVIEW"])
    history = constants(history_path, ("PARENT_SHA256", "PARENT_REVIEW_SHA256", "RELEASE"))
    require(
        history
        == dict(
            PARENT_SHA256=run_sha,
            PARENT_REVIEW_SHA256=provider["KEY_REVIEW"]["sha256"],
            RELEASE=HISTORY_RELEASE,
        ),
        "History interval and SIM issuer/review/release differ",
    )
    return provider


def preflight(run_sha):
    require(_hash(OBSERVER_SHA256), "Completed SIM observer remains unadopted")
    files = {
        name: snapshot.digest(ROOT / name) for name in (FILE, OBSERVER, WRITER, KEY, HISTORY, SIM)
    }
    contract(ROOT, declaration(), files, run_sha)
    return {name: files[name] for name in (FILE, OBSERVER, WRITER, HISTORY)}


def _history_state(module, history, parent):
    """Read retained declarations and actual module ancestry, never a history owner."""
    require(
        type(history) is ModuleType
        and sys.modules.get(HISTORY_MODULE) is history
        and Path(history.__file__).resolve() == ROOT / HISTORY
        and type(parent) is ModuleType
        and sys.modules.get(KEY_MODULE) is parent
        and Path(parent.__file__).resolve() == ROOT / KEY
        and vars(history).get("parent") is parent,
        "Actual frozen history/SIM module association changed",
    )
    declared = {
        key: vars(history).get(key) for key in ("PARENT_SHA256", "PARENT_REVIEW_SHA256", "RELEASE")
    }
    require(
        vars(module).get("HISTORY_FILE") == HISTORY
        and vars(module).get("HISTORY_MODULE") == HISTORY_MODULE
        and declared
        == dict(
            PARENT_SHA256=module.KEY_SHA256,
            PARENT_REVIEW_SHA256=module.KEY_REVIEW["sha256"],
            RELEASE=HISTORY_RELEASE,
        ),
        "History live parent/review/release declaration changed",
    )
    return evidence._seal(declared)


def _history_module(module):
    history = importlib.import_module(HISTORY_MODULE)
    parent = importlib.import_module(KEY_MODULE)
    _history_state(module, history, parent)
    return history, parent


def _atoms(module, names):
    rows = []
    for name in names:
        function = vars(module).get(name)
        require(
            type(function) is FunctionType and function.__globals__ is vars(module),
            "Original observation function namespace required",
        )
        rows.extend(
            (
                function,
                function.__code__,
                function.__globals__,
                function.__defaults__,
                function.__kwdefaults__,
                function.__closure__,
            )
        )
        if function.__kwdefaults__ is not None:
            rows.extend(function.__kwdefaults__)
            rows.extend(function.__kwdefaults__.values())
        if function.__closure__ is not None:
            rows.extend(function.__closure__)
            rows.extend(cell.cell_contents for cell in function.__closure__)
    return tuple(rows)


def _callable(module, name):
    parts = name.split(".")
    selected = vars(module).get(parts[0])
    for part in parts[1:]:
        require(type(selected) is type, "Original observer class required")
        selected = vars(selected).get(part)
    require(type(selected) is FunctionType, "Original observation helper required")
    return selected


def _codes(code):
    return (code,) + tuple(
        nested for value in code.co_consts if type(value) is CodeType for nested in _codes(value)
    )


def _binding_atom(value, depth=0):
    require(depth <= 12, "Bounded observer executable binding required")
    kind = type(value)
    if value is None or kind in (str, int, bool, bytes):
        return (kind, value)
    if kind is FunctionType:
        return (
            kind,
            id(value),
            id(value.__code__),
            id(value.__globals__),
            _binding_atom(value.__defaults__, depth + 1),
            _binding_atom(value.__kwdefaults__, depth + 1),
            tuple(
                (id(cell), _binding_atom(cell.cell_contents, depth + 1))
                for cell in (value.__closure__ or ())
            ),
            _binding_atom(vars(value), depth + 1),
        )
    if kind is dict:
        return (
            kind,
            id(value),
            tuple(
                (_binding_atom(key, depth + 1), _binding_atom(item, depth + 1))
                for key, item in value.items()
            ),
        )
    if kind in (tuple, list):
        return (kind, id(value), tuple(_binding_atom(item, depth + 1) for item in value))
    return (kind, id(value))


def _provider_atoms(module, codes):
    """Bind the pinned module's helpers and resolved names without calling them."""
    namespace = vars(module)
    rows = []
    names = set()
    for name in codes:
        function = _callable(module, name)
        require(function.__globals__ is namespace, "Original observer helper namespace required")
        rows.append((name, _binding_atom(function)))
        for code in _codes(function.__code__):
            names.update(code.co_names)
        if "." in name:
            cls = namespace[name.split(".")[0]]
            rows.append(
                (
                    "class",
                    id(cls),
                    tuple(id(base) for base in type.__getattribute__(cls, "__mro__")),
                    tuple((key, _binding_atom(value)) for key, value in vars(cls).items()),
                )
            )
    actual_builtins = namespace.get("__builtins__")
    require(
        actual_builtins is builtins or actual_builtins is vars(builtins),
        "Original observer builtins required",
    )
    for name in sorted(names):
        if name in namespace:
            value = namespace[name]
            # These are the provider's live append-only forensic/active journals.
            atom = (
                (type(value), id(value)) if name in ("_ACTIVE", "_FAILED") else _binding_atom(value)
            )
            rows.append(("global", name, atom))
        elif name in vars(builtins):
            rows.append(("builtin", name, _binding_atom(vars(builtins)[name])))
    return tuple(rows)


def _original(module):
    path = ROOT / OBSERVER
    require(
        type(module) is ModuleType
        and sys.modules.get(MODULE) is module
        and Path(module.__file__).resolve() == path,
        "Actual frozen observer module required",
    )
    raw = path.read_bytes()
    top_codes = {
        code.co_name: code
        for code in compile(raw, str(path), "exec", dont_inherit=True).co_consts
        if type(code) is CodeType
    }
    definitions = []
    for node in ast.parse(raw).body:
        if isinstance(node, ast.FunctionDef):
            definitions.append((node.name, node, top_codes[node.name]))
        elif isinstance(node, ast.ClassDef):
            cls = vars(module).get(node.name)
            require(
                type(cls) is type
                and all(isinstance(base, ast.Name) for base in node.bases)
                and cls.__bases__
                == tuple(
                    vars(module).get(base.id, vars(builtins).get(base.id)) for base in node.bases
                ),
                "Original observation class ancestry required",
            )
            class_codes = {code.co_name: code for code in _codes(top_codes[node.name])[1:]}
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    definitions.append(
                        (node.name + "." + member.name, member, class_codes[member.name])
                    )
    codes = {}
    for name, node, code in definitions:
        function = _callable(module, name)
        defaults = tuple(ast.literal_eval(value) for value in node.args.defaults) or None
        keywords = {
            arg.arg: ast.literal_eval(value)
            for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
            if value is not None
        } or None
        closure = function.__closure__
        class_closure = (
            "." in name
            and function.__code__.co_freevars == ("__class__",)
            and type(closure) is tuple
            and len(closure) == 1
            and closure[0].cell_contents is vars(module)[name.split(".")[0]]
        )
        require(
            function.__globals__ is vars(module)
            and function.__code__ == code
            and function.__defaults__ == defaults
            and function.__kwdefaults__ == keywords
            and (closure is None or class_closure)
            and not vars(function),
            "Original observation helper executable/defaults required",
        )
        require(
            all(
                type(a) is type(b)
                for a, b in zip(function.__defaults__ or (), defaults or (), strict=True)
            )
            and all(
                type(function.__kwdefaults__[key]) is type(value)
                for key, value in (keywords or {}).items()
            ),
            "Exact observer helper default types required",
        )
        codes[name] = code
    require(
        module.observe_completed.__kwdefaults__ == {"enabled": False}
        and module.saved_view.__kwdefaults__ == {"accepted_observer_sha256": None},
        "Original observer keyword defaults required",
    )
    declared = constants(path, DECLARATIONS)
    require(
        all(getattr(module, key, None) == value for key, value in declared.items()),
        "Observer live producer/review declarations changed",
    )
    return _provider_atoms(module, codes), codes


def bind(state, run_sha):
    require(getattr(state, "sim_observation", None) is None, "Observation binding is one-shot")
    preflight(run_sha)
    require(os.environ.get(RELEASE) == "1", "Explicit completed-SIM observation release required")
    require(os.environ.get(HISTORY_RELEASE) == "1", "Explicit completed-history release required")
    module = importlib.import_module(MODULE)
    atoms, expected_codes = _original(module)
    history, parent = _history_module(module)
    # Import observers may mutate already loaded declarations while the new
    # module is acquired. Recheck the full frozen contracts before binding.
    preflight(run_sha)
    require(_original(module)[0] == atoms, "Observer changed during history import")
    require(
        Path(evidence.__file__).resolve() == ROOT / WRITER, "Frozen typed writer origin required"
    )
    state.sim_observation = SimpleNamespace(
        module=module,
        atoms=atoms,
        expected_codes=expected_codes,
        frame_codes=tuple(
            code for name in expected_codes for code in _codes(_callable(module, name).__code__)
        ),
        writer_atoms=_atoms(evidence, ("write", "read", "files", "_seal")),
        run_sha=run_sha,
        observer_sha=OBSERVER_SHA256,
        key_review=getattr(module, "KEY_REVIEW", None),
        history=history,
        parent=parent,
        history_sha=module.HISTORY_SHA256,
        history_review=module.HISTORY_REVIEW,
        history_declarations=_history_state(module, history, parent),
        declarations=evidence._seal({key: getattr(module, key, None) for key in DECLARATIONS}),
        started=False,
        completed=False,
        raw_return=None,
        partial=None,
        owner=None,
        record=None,
        record_pin=None,
        rows=[],
        primary=None,
        secondary=[],
        source_exception=None,
        observer_error=None,
        raw_exception=None,
        cleanup_complete=True,
        hooks=None,
        callable=None,
        provider_error=None,
        raw_wire=None,
        raw_capture_return=None,
        directory=None,
        record_seal=None,
    )
    _check(state.sim_observation)


def _check(context, *, hooks=True, source=True):
    require(context.primary is None and not context.secondary, "Observation has a retained failure")
    require(
        os.environ.get(RELEASE) == os.environ.get(HISTORY_RELEASE) == "1",
        "Explicit observation and history releases must remain enabled",
    )
    if source:
        preflight(context.run_sha)
    require(
        type(context.module) is ModuleType and sys.modules.get(MODULE) is context.module,
        "Observer module registry/dispatch changed",
    )
    require(
        evidence._seal({key: getattr(context.module, key, None) for key in DECLARATIONS})
        == context.declarations,
        "Observer live source/review declaration changed",
    )
    require(
        _history_state(context.module, context.history, context.parent)
        == context.history_declarations,
        "Retained history declarations changed",
    )
    require(
        all(
            _callable(context.module, name).__code__ == code
            for name, code in context.expected_codes.items()
        ),
        "Original observation executable changed",
    )
    current = _provider_atoms(context.module, context.expected_codes)
    require(
        current == context.atoms,
        "Observation callable changed",
    )
    current = _atoms(evidence, ("write", "read", "files", "_seal"))
    require(
        len(current) == len(context.writer_atoms)
        and all(a is b for a, b in zip(current, context.writer_atoms, strict=True)),
        "Typed observation writer changed",
    )
    if hooks and context.hooks is not None:
        require(
            sys.getprofile() is context.hooks[0] and sys.gettrace() is context.hooks[1],
            "Observation inherited hooks changed",
        )


def _invoke(context, capture):
    """Retain actual return/unwind before forwarding inherited observer callbacks."""
    function = context.module.observe_completed
    context.callable = function
    prior_p, prior_t = sys.getprofile(), sys.gettrace()
    set_p, set_t, get_p, get_t = sys.setprofile, sys.settrace, sys.getprofile, sys.gettrace
    context.hooks = (prior_p, prior_t)
    frame_ref, pending = None, None
    prior_locals = {}
    primary, traceback = None, None

    def forward(frame, event, arg, previous):
        nonlocal frame_ref, pending
        tracked = frame.f_code is function.__code__ and frame.f_globals is function.__globals__
        if tracked:
            if event == "call":
                if frame_ref is None:
                    frame_ref = frame
                if frame is not frame_ref:
                    error = ValueError("Completed observation cannot reenter")
                    if context.observer_error is None:
                        context.observer_error = error
                    context.secondary.append(("reentry", error))
                    raise error
            elif frame is frame_ref and event == "exception":
                pending = arg[1]
                context.raw_exception = arg
            elif frame is frame_ref and event == "return":
                if arg is not None or context.raw_return is None:
                    context.raw_return = arg
                if arg is not None:
                    pending = None
        next_trace = None
        provider_frame = frame.f_globals is vars(context.module)
        provider_caller = frame.f_back is not None and frame.f_back.f_globals is vars(
            context.module
        )
        entered = (
            event == "call"
            and (provider_frame or provider_caller)
            or (event == "c_call" and provider_frame)
        )
        if entered:
            _check(context, source=tracked)
            require(
                not provider_frame or any(frame.f_code is code for code in context.frame_codes),
                "Unbound observer helper frame refused",
            )
        if previous is not None:
            try:
                next_trace = previous(frame, event, arg)
            except BaseException as error:
                if context.observer_error is None:
                    context.observer_error = error
                context.secondary.append(("inherited_" + event, error))
                if tracked and pending is not None and event in ("exception", "return"):
                    context.source_exception = pending
                    return
                raise
        if entered:
            _check(context, source=tracked)
        return next_trace

    def profile(frame, event, arg):
        forward(frame, event, arg, prior_p)

    def trace(frame, event, arg):
        previous = prior_t if event == "call" else prior_locals.get(id(frame))
        next_trace = forward(frame, event, arg, previous)
        if next_trace is None or event == "return":
            prior_locals.pop(id(frame), None)
        else:
            prior_locals[id(frame)] = next_trace
        return trace

    try:
        set_p(profile)
        set_t(trace)
        context.hooks = (profile, trace)
        _check(context)
        result = function(context.owner, enabled=True, capture=capture)
        context.raw_return = result
        _check(context)
    except BaseException as error:
        primary = (
            context.primary
            if context.primary is not None
            else error
            if context.raw_exception is not None and error is context.raw_exception[1]
            else context.observer_error
            if context.observer_error is not None
            else error
        )
        traceback = primary.__traceback__
        context.primary = primary
        context.provider_error = error
        # The actual provider's context is forensic only, never parent authority.
        try:
            context.partial = vars(error).get("partial")
        except BaseException as secondary:
            context.secondary.append(("partial_attribute", secondary))
    finally:
        # No cleanup helper entry can prevent both independently protected setters.
        for setter, target in (
            (set_p, prior_p),
            (set_t, prior_t),
            (set_t, prior_t),
            (set_p, prior_p),
        ):
            try:
                setter(target)
            except BaseException as error:
                context.secondary.append(("hook_restore", error))
        try:
            first = (get_p(), get_t())
            second = (get_t(), get_p())
            context.cleanup_complete = (
                first[0] is prior_p
                and first[1] is prior_t
                and second[0] is prior_t
                and second[1] is prior_p
            )
        except BaseException as error:
            context.secondary.append(("hook_probe", error))
            context.cleanup_complete = False
        context.hooks = (prior_p, prior_t)
    if primary is not None:
        raise primary.with_traceback(traceback)
    require(context.cleanup_complete, "Observation hooks could not be recovered")
    if context.secondary:
        raise context.secondary[0][1]
    return context.raw_return


def _record(context, record, trial, mode):
    require(
        type(record) is dict
        and record.get("kind") == KIND
        and record.get("status") == "completed_observation"
        and record.get("epoch") == EPOCH
        and record.get("operator_mode") == mode
        and record.get("source_operator_mode") == OPERATOR_MODES.get(mode) == trial.operator_mode
        and record.get("trial_identity") == trial.identity
        and type(record.get("configured_iterations")) is int
        and record["configured_iterations"] == len(trial.iterations)
        and record.get("numerical_parity_available") is False
        and record.get("common_starting_authority_established") is False
        and type(record.get("physical_checkpoint_credit")) is int
        and record["physical_checkpoint_credit"] == 0,
        "Exact completed unqualified observation record required",
    )
    producer = record.get("producer", {})
    require(
        producer.get("observer") == dict(path=OBSERVER, sha256=context.observer_sha)
        and producer.get("sha256") == context.run_sha
        and producer.get("module") == "cells.processes.betse_native_sim_run"
        and producer.get("review") == context.key_review,
        "Observation record producer differs from accepted sources",
    )
    require(
        producer.get("history")
        == dict(path=HISTORY, sha256=context.history_sha, review=context.history_review),
        "Observation history producer differs from accepted sources",
    )
    rows = record.get("iterations")
    count = len(trial.iterations)
    require(
        type(rows) is list and len(rows) == count and 1 <= count <= 512,
        "Complete observation iteration roster required",
    )
    closed = record.get("work", {}).get("history_interval")
    require(
        type(closed) is dict
        and closed.get("law") == "actual_completed_SIM_read_only_complete_history_interval@1"
        and closed.get("status") == "completed_observation"
        and closed.get("trial_identity") == trial.identity
        and type(closed.get("configured_rows")) is int
        and closed["configured_rows"] == count
        and type(closed.get("checked_rows")) in (list, tuple)
        and all(type(i) is int for i in closed["checked_rows"])
        and tuple(closed["checked_rows"]) == tuple(range(count))
        and all(
            type(closed.get(name)) is int and closed[name] == 2
            for name in ("full_authority_attempts", "full_authority_returns")
        )
        and type(closed.get("retained_payload_attempts")) is int
        and type(closed.get("retained_payload_returns")) is int
        and closed["retained_payload_attempts"] == closed["retained_payload_returns"] >= 0
        and type(closed.get("native_or_scientific_credit")) is int
        and closed["native_or_scientific_credit"] == 0,
        "Completed history interval/exit evidence required",
    )
    expected = []
    for i, row in enumerate(rows, 1):
        require(
            type(row) is dict
            and set(row) == {"ordinal", "epoch", "files"}
            and type(row["ordinal"]) is int
            and row["ordinal"] == i - 1
            and row["epoch"] == EPOCH,
            "Ordered completed observation rows required",
        )
        expected.append((f"SIM.iteration_{i:04d}", row["files"]))
    captures = record.get("captures")
    require(
        type(captures) is dict
        and set(captures) == {"before", "ready", "final", "rng_before", "rng_after"},
        "Complete observation boundary roster required",
    )
    for key, label in (
        ("before", "before_state"),
        ("ready", "ready_state"),
        ("final", "final_state"),
        ("rng_before", "rng_before"),
        ("rng_after", "rng_after"),
    ):
        expected.append(("SIM." + label, captures[key]))
    require(len(context.rows) == len(expected), "Observation has missing or extra writes")
    for actual, (label, selected) in zip(context.rows, expected, strict=True):
        require(
            actual["label"] == label and actual["pin"] == selected and actual["status"] == "saved",
            "Observation record substituted capture",
        )
        path = bound(selected)
        require(
            evidence._seal(evidence.read(path, expected_sha256=selected["sha256"]))
            == actual["seal"],
            "Observation capture changed after return",
        )


def observe(state, owner, directory, trial, mode):
    context = state.sim_observation
    require(context is not None and not context.started, "One prebound observation required")
    context.started, context.owner = True, owner
    directory = Path(directory)
    context.directory = directory
    baseline = (sys.getprofile(), sys.gettrace())
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    try:
        _check(context)
        directory.mkdir(exist_ok=False)

        def capture(label, raw):
            context.raw_wire = raw
            _check(context)
            require(
                type(label) is str
                and re.fullmatch(
                    r"SIM\.(?:iteration_[0-9]{4}|before_state|ready_state|final_state|rng_before|rng_after)",
                    label,
                )
                is not None
                and not any(row["label"] == label for row in context.rows),
                "Exact unique observation capture label required",
            )
            require(
                type(raw) is dict
                and set(raw) == {"tree", "columns"}
                and type(raw["tree"]) is dict
                and type(raw["columns"]) is dict,
                "Observer capture requires already typed wire",
            )
            row = dict(
                label=label,
                raw=raw,
                status="attempted",
                pin=None,
                seal=evidence._seal(raw),
                attempted_path=str(directory / f"capture-{len(context.rows):04d}.json"),
            )
            context.rows.append(row)
            try:
                path = Path(row["attempted_path"])
                context.raw_capture_return = evidence.write(path, raw, label=label)
                row["pin"] = pin(path)
                require(evidence._seal(raw) == row["seal"], "Typed input changed during write")
                require(
                    evidence._seal(evidence.read(path, expected_sha256=row["pin"]["sha256"]))
                    == row["seal"],
                    "Typed roundtrip changed",
                )
                row["status"] = "saved"
                _check(context)
                return dict(row["pin"])
            except BaseException as error:
                row["error"] = error
                context.primary = error
                raise

        record = _invoke(context, capture)
        context.record = record
        _check(context)
        _record(context, record, trial, mode)
        context.record_seal = evidence._seal(record)
        snapshot.write_json(directory / "record.json", record)
        context.record_pin = pin(directory / "record.json")
        finish(state, trial, mode)
        context.completed = True
        return record
    except BaseException as error:
        # CPython may clear a still-unwinding hook after _invoke sampled it.
        # This caller boundary owns the same captured epoch, including failure
        # before _invoke's body. Recover independently before any reporting.
        for index in (0, 1, 1, 0):
            try:
                setters[index](baseline[index])
            except BaseException as secondary:
                try:
                    context.secondary.append(("outer_hook_restore", secondary))
                except BaseException:
                    pass
        try:
            first, second = (getters[0](), getters[1]()), (getters[1](), getters[0]())
            context.cleanup_complete = (
                first[0] is baseline[0]
                and first[1] is baseline[1]
                and second[0] is baseline[1]
                and second[1] is baseline[0]
            )
        except BaseException:
            context.cleanup_complete = False
        if not context.cleanup_complete:
            state.sim_metadata_stopped = True
            state.sim_cleanup_complete = False
        if context.primary is None:
            context.primary = error
        try:
            _FAILED.append(context)
        except BaseException:
            pass
        if error is not context.primary:
            try:
                context.secondary.append(("observer_escape", error))
            except BaseException:
                pass
        raise context.primary  # noqa: B904 -- Keep the actual primary and its original cause.


def finish(state, trial, mode, *, inherited_hooks=True):
    context = state.sim_observation
    _check(context, hooks=inherited_hooks)
    require(
        context.cleanup_complete and context.record_pin is not None,
        "Observation did not close and publish",
    )
    _record(context, context.record, trial, mode)
    require(
        evidence._seal(context.record) == context.record_seal,
        "Observation record mutated after publication",
    )
    saved = payload._metadata(
        bound(context.record_pin), payload.MAX_METADATA, context.record_pin["sha256"]
    )[0]
    require(evidence._seal(saved) == context.record_seal, "Saved observation record changed")
    _check(context, hooks=inherited_hooks)


def summary(state):
    context = state.sim_observation
    if context is None:
        return None
    return dict(
        started=context.started,
        completed=context.completed,
        record=context.record_pin,
        cleanup_complete=context.cleanup_complete,
        primary_present=context.primary is not None,
        capture_errors=len(context.secondary),
        captures=[
            {k: row[k] for k in ("label", "status", "pin", "attempted_path")}
            for row in context.rows
        ],
        raw_return_retained=context.raw_return is not None,
        raw_partial_retained=context.partial is not None,
        comparison_or_physical_credit=False,
    )


def original_sources(root):
    """Bounded streaming inventory with the reference's package-relative grammar."""
    root = payload._regular(root)
    files, total = {}, 0
    for path in sorted((root / "betse").rglob("*")):
        if "__pycache__" in path.parts:
            continue
        require(not path.is_symlink(), "Linked original package member")
        if path.is_dir():
            continue
        path = payload._regular(path)
        size = path.stat().st_size
        require(path.is_file() and size <= 8 * 2**20, "Bounded original package file required")
        total += size
        require(len(files) < 4096 and total <= 128 * 2**20, "Original package inventory bound")
        files[str(path.relative_to(root))] = dict(sha256=snapshot.digest(path), size_bytes=size)
    require(bool(files), "Original package inventory missing")
    return dict(root=str(root), files=files, sha256=evidence._seal(files))


def check_original_sources(value):
    require(
        type(value) is dict and set(value) == {"root", "files", "sha256"},
        "Exact original package declaration required",
    )
    require(value == original_sources(value["root"]), "Original package inventory changed")
    return value


def runtime_sources(runtime, declared):
    """Tie actual imported original files to the inventory declared before execution."""
    root = Path(declared["root"])
    for name, row in runtime["loaded_files"].items():
        path = Path(row["path"])
        if name == "betse" or name.startswith("betse.") or path.is_relative_to(root):
            require(path.is_relative_to(root), "Original runtime escaped declared source inventory")
            relative = str(path.relative_to(root))
            require(
                declared["files"].get(relative, {}).get("sha256") == row["sha256"],
                "Actual original runtime differs from declared source inventory",
            )
