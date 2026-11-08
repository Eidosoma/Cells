"""CPU5 frozen native-blocked wrapper-authority metadata controls only."""

import argparse
import ast
import contextlib
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import os
import resource
import sys
from collections import Counter
from pathlib import Path
from threading import RLock
from types import CodeType, FunctionType, GenericAlias, SimpleNamespace
from weakref import WeakKeyDictionary

from validation.betse import betse_native_init_molecule_network_software as previous

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_init_molecule_wrapper_authority.py"
LITERAL = "src/cells/processes/betse_native_init_molecule_channels_source.py"
TEST = "tests/unit/test_betse_native_init_molecule_wrapper_authority.py"
FILE = "validation/betse/betse_native_init_molecule_wrapper_authority_software.py"
MODULE = "validation.betse.betse_native_init_molecule_wrapper_authority_software"
SOFTWARE_RELEASE = "CELLS_NATIVE_INIT_MOLECULE_WRAPPER_SOFTWARE_RELEASED"
LIBRARY_RELEASE = "CELLS_WRAPPER_SYNTHETIC_LIBRARY_METADATA_RELEASED"
COUNTER_RELEASE = "CELLS_WRAPPER_PINNED_COUNTER_METADATA_RELEASED"
BOOTSTRAP_RELEASE = "CELLS_WRAPPER_SIX_API_METADATA_RELEASED"
OWNED = SOURCE, LITERAL, TEST, FILE
snapshot, runtime, ref = previous.snapshot, previous.runtime, previous.ref


def is_forbidden_frame(frame):
    module = frame.f_globals.get("__name__", "")
    return (
        module == "beartype" or module.startswith("beartype.") or previous.is_forbidden_frame(frame)
    )


def _scope():
    return dict(
        previous._scope(),
        ROOT=ROOT,
        SOURCE=SOURCE,
        LITERAL=LITERAL,
        TEST=TEST,
        FILE=FILE,
        MODULE=MODULE,
        SOFTWARE_RELEASE=SOFTWARE_RELEASE,
        SOFTWARE_CPU=5,
        OWNED=OWNED,
        __file__=__file__,
    )


def prepare(directory, select=""):
    function = previous.previous.previous.previous.reused.prepare
    return FunctionType(function.__code__, _scope(), argdefs=function.__defaults__)(
        directory, select
    )


def child(directory):
    # Match the existing declared 1GiB software policy before definition imports.
    # A metadata controller may itself have an inherited 512MiB address-space cap.
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    # The established child owns snapshot, guard, result and runtime checks.
    # Only its hard-coded DEFINITION import is redirected to this exact family.
    target = SOURCE.removeprefix("src/").removesuffix(".py").replace("/", ".")

    def own_import(name):
        if name != "cells.processes.betse_native_init_molecule_network":
            raise ValueError("Only the exact existing software definition import is selected")
        return importlib.import_module(target)

    namespace = dict(vars(previous), **_scope())
    namespace["importlib"] = SimpleNamespace(import_module=own_import)
    return FunctionType(previous.child.__code__, namespace)(directory)


LIBRARY_SOURCE = """from beartype import beartype
@beartype
class Early:
    def plain(self):
        return Later, late_helper
    def typed(self, value: int) -> int:
        return value
@beartype
class Later:
    def __init__(self, value):
        self.value = value
@beartype
def late_helper(value):
    return value
"""


def _atom(value):
    """Forensic labels only: no repr, getters, callable or owner reconstruction."""
    kind = type(value)
    result = dict(
        identity=id(value),
        type_module=type.__getattribute__(kind, "__module__"),
        type_name=type.__getattribute__(kind, "__qualname__"),
    )
    if kind is str:
        result["text"] = value[:256]
    elif value is None or kind in (bool, int):
        result["scalar"] = value
    elif kind is FunctionType:
        result["function"] = (value.__module__, value.__qualname__)
    elif kind is CodeType:
        result["code"] = (value.co_filename, value.co_firstlineno, value.co_qualname)
    elif kind in (tuple, dict, list, set):
        result["length"] = len(value)
    return result


LIBRARY_VARIANTS = (
    "none",
    "self_reference",
    "postpublish_equal_helper",
    "postpublish_equal_method",
    "existing_global",
    "undeclared",
    "foreign_later",
    "foreign_helper",
    "prepublish_annotation",
    "conf_cache",
    "module_unwind",
    "module_reentry",
    "unselected_class",
    "unselected_helper",
    "unselected_class_foreign",
    "unselected_helper_foreign",
    "unselected_helper_default",
    "unselected_helper_equal_copy",
    "unselected_class_label",
    "unselected_helper_label",
    "class_method_positive",
    "class_method_default_before",
    "class_method_kwdefault_before",
    "class_method_default_type_before",
    "class_method_default_signed_before",
    "class_method_annotations_before",
    "class_method_closure_before",
    "class_method_mutable_default",
    "class_method_default_after",
    "class_method_kwdefault_after",
    "class_method_annotations_after",
    "class_method_closure_after",
    "class_method_equal_copy_after",
    "class_method_metaclass_default_before",
    "class_method_metaclass_nested_before",
    "class_method_metaclass_keyword_before",
    "class_method_foreign_key_before",
)


def library_probe(directory, variant="none"):
    """Actual pinned beartype lifecycle over synthetic source, never BETSE."""
    if os.environ.get(LIBRARY_RELEASE) != "1" or os.sched_getaffinity(0) != {5} or not __debug__:
        raise ValueError("Explicit CPU5 synthetic-library metadata release required")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    if type(variant) is not str or variant not in LIBRARY_VARIANTS:
        raise ValueError("Declared synthetic publication control required")
    directory.mkdir()
    import numpy as np

    from cells.processes import betse_native_init_molecule_wrapper_authority as authority

    source = directory / "cells_synthetic_wrapper_publication.py"
    text = LIBRARY_SOURCE
    if variant == "self_reference":
        text = text.replace("return Later, late_helper", "return Early, Later, late_helper")
    elif variant == "existing_global":
        text = "stable = object()\n" + text.replace(
            "return Later, late_helper", "return Later, late_helper, stable"
        )
        text += "\nstable = object()\n"
    elif variant == "undeclared":
        text = text.replace("return Later, late_helper", "return Later, late_helper, late_value")
        text += "\nlate_value = object()\n"
    elif variant == "foreign_later":
        text += "\nLater = object()\n"
    elif variant == "foreign_helper":
        text += "\nlate_helper = lambda value: value\n"
    elif variant == "prepublish_annotation":
        text += "\nEarly.plain.__annotations__['unobserved'] = 'changed'\n"
    elif variant == "module_unwind":
        text += (
            "\nsource_cause = OSError('source cause')\n"
            "source_error = RuntimeError('synthetic module unwind')\n"
            "raise source_error from source_cause\n"
        )
    elif variant == "conf_cache":
        text = text.replace(
            "from beartype import beartype",
            "from beartype import beartype, BeartypeConf\n"
            "probe_conf = BeartypeConf(claw_skip_package_names=('cells.synthetic_held_metadata',))",
        )
        text = text.replace("@beartype\nclass Early", "@beartype(conf=probe_conf)\nclass Early")
    if variant.startswith("unselected_helper"):
        text = text.replace("@beartype\ndef late_helper", "def late_helper")
        if variant == "unselected_helper_foreign":
            text += "\nlate_helper = lambda value: value\n"
        elif variant == "unselected_helper_default":
            text = text.replace("def late_helper(value):", "def late_helper(value, flag=1):")
            text += "\nlate_helper.__defaults__ = (2,)\n"
        elif variant == "unselected_helper_equal_copy":
            text += (
                "\nfrom types import FunctionType\n"
                "late_helper = FunctionType(late_helper.__code__, globals(), 'late_helper')\n"
            )
    elif variant == "unselected_class_foreign":
        text += "\nLater = object()\n"
    if variant.endswith("_label"):
        text += (
            "\nclass Label(str):\n"
            " def __eq__(self, other):\n"
            "  raise AssertionError('Foreign label equality must not execute')\n"
        )
        target = "Later" if variant.startswith("unselected_class") else "late_helper"
        text += target + ".__module__ = Label(__name__)\n"
    if variant.startswith("class_method_"):
        text = text.replace(
            "def __init__(self, value):", "def __init__(self, value=1, *, enabled=False):"
        )
        text = text.replace(
            "        self.value = value\n",
            "        self.value = value\n    def remember(self):\n        return __class__\n",
        )
        if variant == "class_method_default_signed_before":
            text = text.replace("value=1,", "value=-0.0,")
        elif variant == "class_method_mutable_default":
            text = text.replace("value=1,", "value=[],")
        elif variant == "class_method_metaclass_nested_before":
            text = text.replace("value=1,", "value=(1,),")
        text += "\npublication_boundary = None\n"
    with source.open("x") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    module_name = source.stem
    before = sys.getprofile(), sys.gettrace()
    work, forbidden, rows, primary, context, backend = [], [], [], None, None, None
    validated, validation_attempts, cached_repr_before = 0, 0, None
    source_primary_identity = source_cause_identity = None
    observer_edits, equality_dispatch = [], []

    class ForeignDefaultType(type):
        def __eq__(cls, other):
            equality_dispatch.append("metaclass")
            return True

        __hash__ = type.__hash__

    class ForeignDefault(metaclass=ForeignDefaultType):
        def __eq__(self, other):
            equality_dispatch.append("value")
            return True

        __hash__ = object.__hash__

    foreign_default = ForeignDefault()
    source_code = compile(text, str(source), "exec", dont_inherit=True)
    class_names = {node.name for node in ast.parse(text).body if isinstance(node, ast.ClassDef)}
    class_codes = {
        code
        for code in source_code.co_consts
        if type(code) is CodeType and code.co_name in class_names
    }
    marker_line = text.count("\n") if variant.startswith("class_method_") else None

    def trace(frame, event, arg):
        if (
            event == "line"
            and frame.f_code.co_filename == str(source)
            and frame.f_code.co_name == "<module>"
            and frame.f_lineno == marker_line
            and variant.endswith("_before")
        ):
            later = frame.f_globals["Later"]
            if variant == "class_method_default_before":
                later.__init__.__defaults__ = (2,)
            elif variant == "class_method_default_type_before":
                later.__init__.__defaults__ = (True,)
            elif variant == "class_method_default_signed_before":
                later.__init__.__defaults__ = (0.0,)
            elif variant == "class_method_kwdefault_before":
                later.__init__.__kwdefaults__["enabled"] = True
            elif variant == "class_method_annotations_before":
                later.__init__.__annotations__["value"] = int
            elif variant == "class_method_closure_before":
                later.remember.__closure__[0].cell_contents = object()
            elif variant == "class_method_metaclass_default_before":
                later.__init__.__defaults__ = (foreign_default,)
            elif variant == "class_method_metaclass_nested_before":
                later.__init__.__defaults__ = ((foreign_default,),)
            elif variant == "class_method_metaclass_keyword_before":
                later.__init__.__kwdefaults__["enabled"] = foreign_default
            elif variant == "class_method_foreign_key_before":
                later.__init__.__kwdefaults__ = {foreign_default: False}
            observer_edits.append((variant, frame.f_lineno))
        if before[1] is not None:
            before[1](frame, event, arg)
        return trace if frame.f_code.co_filename == str(source) else None

    def profile(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if event != "call":
            return
        name, code = frame.f_globals.get("__name__", ""), frame.f_code
        allowed_synthetic = code.co_filename == str(source) and any(
            authority.typed._constant(code) == authority.typed._constant(expected)
            for expected in (source_code, *class_codes)
        )
        maker = frame.f_back
        generated = code.co_filename.startswith("<@beartype(" + module_name)
        definition_only = (
            generated
            and code.co_name == "<module>"
            and backend is not None
            and maker is not None
            and maker.f_code is backend.functions["make"].__code__
            and maker.f_globals is backend.functions["make"].__globals__
            and maker.f_locals.get("func_code_compiled") is code
        )
        held = (
            name == "betse"
            or name.startswith("betse.")
            or (generated and not definition_only)
            or (code.co_filename == str(source) and not allowed_synthetic)
            or name.startswith(("numpy.random", "numpy.linalg", "scipy."))
        )
        if held:
            forbidden.append((name, code.co_qualname))
            raise AssertionError("BETSE, synthetic method, RNG and operator work held")
        if name == "beartype" or name.startswith("beartype."):
            if len(work) >= 131072:
                raise ValueError("Bounded library metadata work exhausted")
            work.append((name, code.co_qualname))

    def operator_held(*args, **kwargs):
        forbidden.append("numeric_operator_or_RNG")
        raise AssertionError("Actual numerical operator/RNG held")

    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                forbidden.append(fullname)
                raise AssertionError("BETSE imports held")
            if fullname == module_name:
                loader = backend.loader_type(fullname, str(source))
                return importlib.util.spec_from_loader(fullname, loader)
            return None

    finder, restored = Finder(), []
    try:
        sys.meta_path.insert(0, finder)
        for group, names in (
            (
                np.random,
                (
                    "random",
                    "random_sample",
                    "rand",
                    "randn",
                    "seed",
                    "default_rng",
                    "RandomState",
                    "normal",
                    "uniform",
                ),
            ),
            (np.linalg, ("inv", "pinv", "solve", "lstsq", "svd")),
        ):
            for name in names:
                restored.append((group, name, getattr(group, name)))
                setattr(group, name, operator_held)
        # Source definitions use the focused runtime first; only the actual
        # retained beartype/dependencies are added lazily afterwards.
        sys.path.extend(str(path) for path in authority.ROOTS)
        sys.setprofile(profile)
        if variant.startswith("class_method_"):
            sys.settrace(trace)
        backend = authority._backend()
        sites = {
            ("Early", "plain"): source.name,
            ("Early", "typed"): source.name,
            ("Later", "__init__"): source.name,
            (None, "late_helper"): source.name,
        }
        if variant.startswith("unselected_helper"):
            del sites[(None, "late_helper")]
        if variant.startswith(("unselected_class", "class_method_")):
            del sites[("Later", "__init__")]
        namespace = dict(
            vars(authority),
            network=SimpleNamespace(
                NATIVE=directory,
                SITES=sites,
                PINS={source.name: hashlib.sha256(source.read_bytes()).hexdigest()},
                code=lambda role, name: authority._library_code(source, role, name),
            ),
            channels=SimpleNamespace(SITES={}, PINS={}),
            LAW="synthetic_pinned_beartype_publication_metadata_only@1",
            _ACTIVE=[],
            _FAILED=[],
            _ISSUED=WeakKeyDictionary(),
            _LOCK=RLock(),
            os=SimpleNamespace(environ={authority.RELEASE: "1"}),
        )
        for name, function in vars(authority).items():
            if type(function) is FunctionType and function.__globals__ is vars(authority):
                copied = FunctionType(
                    function.__code__, namespace, name, function.__defaults__, function.__closure__
                )
                copied.__kwdefaults__ = function.__kwdefaults__
                namespace[name] = copied
        namespace["_backend"] = lambda: backend
        original = authority.observing_native_imports.__wrapped__
        body = FunctionType(
            original.__code__,
            namespace,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        body.__kwdefaults__ = original.__kwdefaults__
        try:
            with contextlib.contextmanager(body)(enabled=True) as context:
                imported = importlib.import_module(module_name)
                assert imported.__file__ == str(source)
                if variant in ("postpublish_equal_helper", "postpublish_equal_method"):
                    old = (
                        imported.late_helper if variant.endswith("helper") else imported.Early.plain
                    )
                    copied = FunctionType(
                        old.__code__,
                        old.__globals__,
                        old.__name__,
                        old.__defaults__,
                        old.__closure__,
                    )
                    copied.__kwdefaults__ = old.__kwdefaults__
                    if variant.endswith("helper"):
                        imported.late_helper = copied
                    else:
                        imported.Early.plain = copied
                elif variant == "conf_cache":
                    conf = imported.Early.typed.__kwdefaults__["__beartype_conf"]
                    cached_repr_before = object.__getattribute__(conf, "_repr")
                    repr(conf)  # Actual pinned lazy library cache, explicitly counted work.
                elif variant == "module_reentry":
                    exec(context.loaded_codes[module_name].output, vars(imported))
            if variant == "class_method_default_after":
                imported.Later.__init__.__defaults__ = (2,)
            elif variant == "class_method_kwdefault_after":
                imported.Later.__init__.__kwdefaults__["enabled"] = True
            elif variant == "class_method_annotations_after":
                imported.Later.__init__.__annotations__["value"] = int
            elif variant == "class_method_closure_after":
                imported.Later.remember.__closure__[0].cell_contents = object()
            elif variant == "class_method_equal_copy_after":
                old = imported.Later.__init__
                copied = FunctionType(
                    old.__code__, old.__globals__, old.__name__, old.__defaults__, old.__closure__
                )
                copied.__kwdefaults__ = old.__kwdefaults__
                copied.__qualname__ = old.__qualname__
                imported.Later.__init__ = copied
            for row in context.rows:
                owner = row.module if row.stack is None else row.stack[0]
                validation_attempts += 1
                assert (
                    namespace["validate"](
                        row.output, row.original, owner=owner, attribute=row.target[0][1]
                    )
                    is row.original
                )
                validated += 1
        except BaseException as error:
            primary = error
            if variant == "module_unwind" and context is not None:
                fields = context.loaded_codes[module_name].module_frame.f_globals
                source_primary_identity = primary is fields["source_error"]
                source_cause_identity = primary.__cause__ is fields["source_cause"]
        if context is not None:
            for row in context.rows:
                current, error = None, None
                original_bindings = row.bindings
                try:
                    current = namespace["_record_function"](row, backend)
                except BaseException as capture:
                    error = dict(type=type(capture).__name__, message=str(capture))
                differences = []
                if current is not None and type(original_bindings) is tuple:
                    for index in range(max(len(current), len(original_bindings))):
                        left = current[index] if index < len(current) else None
                        right = original_bindings[index] if index < len(original_bindings) else None
                        if index >= min(len(current), len(original_bindings)) or left is not right:
                            differences.append(
                                dict(index=index, current=_atom(left), before=_atom(right))
                            )
                rows.append(
                    dict(
                        target=row.target[0],
                        no_code=row.output is row.original,
                        before_count=None if original_bindings is None else len(original_bindings),
                        current_count=None if current is None else len(current),
                        differences=differences[:16],
                        comparison_error=error,
                    )
                )
    finally:
        for group, name, function in restored:
            setattr(group, name, function)
        sys.meta_path.remove(finder)
        sys.settrace(before[1])
        sys.setprofile(before[0])
        snapshot.write_json(directory / "runtime.json", runtime.inventory())
        snapshot.write_json(
            directory / "library-probe.json",
            dict(
                status="publication_observed"
                if primary is None
                else "closed_validation_refused"
                if context is not None and context.published
                else "publication_refused",
                primary=None
                if primary is None
                else dict(
                    type=type(primary).__name__,
                    message=str(primary),
                    cause=None
                    if primary.__cause__ is None
                    else dict(
                        type=type(primary.__cause__).__name__, message=str(primary.__cause__)
                    ),
                ),
                rows=rows,
                work=work,
                library_calls=len(work),
                variant=variant,
                observer_edits=observer_edits,
                equality_dispatch=equality_dispatch,
                source_primary_identity=source_primary_identity,
                source_cause_identity=source_cause_identity,
                validated=validated,
                validation_attempts=validation_attempts,
                cached_repr_before=cached_repr_before,
                capture_errors=[]
                if context is None
                else [
                    (item[0], type(item[1]).__name__, str(item[1]))
                    for item in context.capture_errors
                ],
                module_events=0 if context is None else len(context.module_raw),
                private_published=False if context is None else context.published,
                forbidden=forbidden,
                hooks_restored=sys.getprofile() is before[0] and sys.gettrace() is before[1],
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                wrapper_sha256=hashlib.sha256(Path(authority.__file__).read_bytes()).hexdigest(),
                library_sources=authority.LIBRARIES,
                native_or_original_owner_issuance=False,
                scientific_credit=0,
            ),
        )
    if forbidden:
        raise AssertionError("Forbidden actual body attempted")


COUNTER_OBSERVERS = ("molecule", "runner", "phase", "runtime")
COUNTER_VARIANTS = (
    "none",
    "repeated",
    "counter_before",
    "counter_after",
    "original_defaults",
    "original_code",
    "foreign_export",
    "foreign_body",
    "global_str",
    "reentry",
    "source_unwind",
    "capture_return",
    "source_capture_unwind",
    "closed_call",
    "budget",
    "record_drop",
)
COUNTER_IMPORTS = {
    # Source paths and exact literal bytes are kept together.
    # ruff: noqa: E501
    "betse/__init__.py": "a3dce54aab848c36dfc4738f5dba889505adefad819d63d4c61a4310655cf200",
    "betse/metadata.py": "6a09cc83d58ec6c1ea4b5a4c11fa0eb46d3b84518309a0495ddc7d61610ce8a1",
    "betse/exceptions.py": "c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971",
    "betse/util/__init__.py": "27ba859ab475847ac208aa581afc5c24053ae1b487e1cd3a73ab750a0c245d11",
    "betse/util/type/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "betse/util/type/types.py": "9b8c83555b06a18bfb252d236c95c0d625699237e5c5cc671c085d282fc2c089",
    "betse/util/type/iterable/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "betse/util/type/iterable/mapping/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "betse/util/type/iterable/mapping/mapcls.py": "15a88829cbb5fc9fc9d60c0a8b4e7ea120f86d06ceb7e1876d55862ee060ad58",
}
CONTEXT_IMPORT = (
    "betse/util/type/contexts.py",
    "66fad70e4b3458f3d24e66c93c741628112be7ba591d745e034529caaa8da8ef",
)
CONTEXT_VARIANTS = (
    "nested_export",
    "nested_export_foreign",
    "nested_export_equal",
    "nested_export_retarget",
    "nested_export_code",
    "nested_export_input",
    "nested_export_record",
    "nested_export_factory",
    "nested_export_closed",
    "nested_export_dispatch",
    "nested_export_origin",
    "nested_export_input_equal",
    "nested_export_annotation_after",
    "nested_export_wraps",
)


LIFECYCLE_VARIANTS = (
    *CONTEXT_VARIANTS,
    "nested_counter",
    "nested_all_counters",
    "nested_no_effect",
    "nested_exception",
    "nested_prefix",
    "nested_guards",
    "own_events",
    "own_callback",
    "own_local",
    "foreign_tool",
    "own_tool",
    "profile_drop",
    "trace_change",
    "getter_failure",
    "setter_failure",
    "callback_restore_failure",
    "free_failure",
    "primary_cleanup_failure",
    "teardown_binding_drift",
    "bookkeeping_id",
    "bookkeeping_values",
    "bookkeeping_id_primary",
    "bookkeeping_values_falsey",
    "publication_profile",
    "publication_trace",
    "publication_issue",
    "publication_mask",
)


def _counter_scope(api, authority, backend, include_counter=True, context_export=False):
    root = authority.network.NATIVE
    sites = {(None, "type_check"): "betse/util/type/types.py"}
    sites[
        (None, authority.COUNTER_HELPER[2]) if include_counter else ("DynamicValue", "__init__")
    ] = authority.COUNTER_HELPER[0]
    pins = dict(COUNTER_IMPORTS)
    if context_export:
        sites[(None, "noop_context")] = CONTEXT_IMPORT[0]
        pins[CONTEXT_IMPORT[0]] = CONTEXT_IMPORT[1]
    namespace = dict(
        api,
        network=SimpleNamespace(
            NATIVE=root,
            SITES=sites,
            PINS={p: pins[p] for p in sites.values()},
            code=lambda role, name: authority._library_code(root / sites[(role, name)], role, name),
        ),
        channels=SimpleNamespace(SITES={}, PINS={}),
        _ACTIVE=[],
        _FAILED=[],
        _ISSUED=WeakKeyDictionary(),
        _LOCK=RLock(),
    )
    for name, function in api.items():
        if type(function) is FunctionType and function.__globals__ is api:
            copied = FunctionType(
                function.__code__, namespace, name, function.__defaults__, function.__closure__
            )
            copied.__kwdefaults__ = function.__kwdefaults__
            namespace[name] = copied
    namespace["_backend"] = lambda: backend
    body = api["observing_native_imports"].__wrapped__
    manager = contextlib.contextmanager(
        FunctionType(body.__code__, namespace, body.__name__, body.__defaults__, body.__closure__)
    )
    return namespace, manager


def counter_probe(directory, variant="none", observer="molecule", lifecycle=None):
    """One original metadata helper lifecycle; no model, geometry or RNG work."""
    if os.environ.get(COUNTER_RELEASE) != "1" or os.sched_getaffinity(0) != {5} or not __debug__:
        raise ValueError("Explicit CPU5 pinned-counter metadata release required")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    if (
        type(variant) is not str
        or type(observer) is not str
        or variant not in COUNTER_VARIANTS
        or observer not in COUNTER_OBSERVERS
        or (
            lifecycle is not None
            and (type(lifecycle) is not str or lifecycle not in LIFECYCLE_VARIANTS)
        )
    ):
        raise ValueError("Declared counter metadata control required")
    directory.mkdir()
    import numpy as np

    from cells.processes import betse_native_init_molecule_wrapper_authority as authority
    from cells.processes import betse_native_init_sim_assembly as assembly
    from cells.processes import betse_native_init_sim_preparation as preparation
    from cells.processes import betse_native_sim_run as sim_run

    root = authority.network.NATIVE
    native_pins = dict(COUNTER_IMPORTS)
    context_export_enabled = lifecycle in CONTEXT_VARIANTS
    if context_export_enabled:
        native_pins[CONTEXT_IMPORT[0]] = CONTEXT_IMPORT[1]
    for relative, expected in native_pins.items():
        path = root / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Exact original metadata-only import sources required")
    if any(name == "betse" or name.startswith("betse.") for name in sys.modules):
        raise ValueError("Fresh original metadata import required")
    # Exact candidate projection in this isolated software process only. It
    # grants no adoption to a retained or actual execution owner.
    pin = hashlib.sha256(Path(authority.__file__).read_bytes()).hexdigest()
    preparation.WRAPPER_OBSERVER_SHA256 = assembly.WRAPPER_SHA256 = pin
    apis = (
        vars(authority),
        preparation._wrapper_api(),
        assembly._phase_import_api(),
        sim_run._runtime_import_api(),
    )
    api = apis[COUNTER_OBSERVERS.index(observer)]
    before = sys.getprofile(), sys.gettrace()
    context = backend = namespace = imported = None
    library_work, metadata_work, forbidden, restored, callback_work = [], [], [], [], []
    primary = None
    results, strict_difference, validations = [], None, 0

    class FalseyLifecycleError(RuntimeError):
        def __bool__(self):
            return False

    original_error = (
        FalseyLifecycleError if lifecycle == "bookkeeping_values_falsey" else RuntimeError
    )("counter source unwind")
    cause = OSError("counter cause")
    boundary_error = ValueError("installed cleanup bookkeeping rejection")
    boundary_hits = []
    source_identity = cause_identity = None
    reentered = False
    scopes, cleanup_samples, fixture_recovery, export_observations, export_edits = (
        [],
        [],
        [],
        [],
        [],
    )
    foreign_wraps_calls = []
    guard_patch, guard_models = None, []
    foreign_slots, monitor_api_originals, fault_calls = [], [], []
    monitoring_before = tuple(
        (sys.monitoring.get_tool(i), sys.monitoring.get_events(i)) for i in range(6)
    )
    helper_name = authority.COUNTER_HELPER[2]
    counter_name = authority.COUNTER_HELPER[3]

    def profile(frame, event, arg):
        nonlocal reentered
        if before[0] is not None:
            before[0](frame, event, arg)
        if (
            lifecycle == "nested_export_input_equal"
            and not export_edits
            and backend is not None
            and event == "call"
            and frame.f_code is backend.context_dispatch.__code__
        ):
            actual = frame.f_locals.get("obj")
            delegate = vars(actual).get("__wrapped__") if type(actual) is FunctionType else None
            if type(delegate) is FunctionType and delegate.__code__.co_filename == str(
                root / CONTEXT_IMPORT[0]
            ):
                copied = FunctionType(
                    actual.__code__,
                    actual.__globals__,
                    actual.__name__,
                    actual.__defaults__,
                    actual.__closure__,
                )
                copied.__kwdefaults__, copied.__annotations__ = (
                    actual.__kwdefaults__,
                    actual.__annotations__,
                )
                copied.__qualname__, copied.__module__, copied.__doc__ = (
                    actual.__qualname__,
                    actual.__module__,
                    actual.__doc__,
                )
                vars(copied).update(vars(actual))
                frame.f_locals["obj"] = copied
                export_edits.append(lifecycle)
        if lifecycle is not None and scopes and "context" in scopes[-1] and not boundary_hits:
            inner = scopes[-1]
            proof = inner["context"]
            own_frame = frame.f_globals is inner["namespace"]
            if (
                lifecycle.startswith("bookkeeping_")
                and event == "c_call"
                and own_frame
                and frame.f_locals.get("context") is proof
            ):
                hit = (
                    arg is id
                    if "_id" in lifecycle
                    else getattr(arg, "__name__", None) == "values"
                    and getattr(arg, "__self__", None) is frame.f_locals.get("codes")
                )
                if hit:
                    boundary_hits.append(
                        dict(
                            boundary=lifecycle,
                            primary_is_original=frame.f_locals.get("primary") is original_error,
                        )
                    )
                    raise boundary_error
            elif (
                lifecycle in ("publication_profile", "publication_trace", "publication_mask")
                and event == "return"
                and own_frame
                and frame.f_code is inner["namespace"]["_binding"].__code__
                and not proof.active
                and frame.f_locals.get("row") is proof.rows[-1]
            ):
                boundary_hits.append(dict(boundary=lifecycle))
                if lifecycle == "publication_profile":
                    sys.setprofile(None)
                elif lifecycle == "publication_trace":
                    sys.settrace(lambda *args: None)
                else:
                    enclosing = scopes[-2]["context"]
                    prior_mask = sys.monitoring.get_events(enclosing.tool)
                    sys.monitoring.set_events(
                        enclosing.tool, prior_mask ^ sys.monitoring.events.CALL
                    )
                    boundary_hits[-1].update(
                        tool=enclosing.tool,
                        before=prior_mask,
                        after=sys.monitoring.get_events(enclosing.tool),
                        hooks_unchanged=sys.getprofile() is profile,
                    )
            elif (
                lifecycle == "publication_issue"
                and event == "return"
                and frame.f_code is WeakKeyDictionary.__setitem__.__code__
                and frame.f_back.f_globals is inner["namespace"]
                and not proof.active
                and frame.f_back.f_locals.get("row") is proof.rows[-1]
            ):
                boundary_hits.append(dict(boundary=lifecycle))
                sys.setprofile(None)
        if event == "return" and "final" in frame.f_locals:
            for scope in scopes:
                if frame.f_globals is scope["namespace"] and frame.f_locals.get(
                    "context"
                ) is scope.get("context"):
                    final_context = scope["context"]
                    cleanup_samples.append(
                        dict(
                            scope=scope["label"],
                            original=frame.f_locals["original"],
                            final=frame.f_locals["final"],
                            monitor_restored=final_context.monitor_restored,
                            hooks_restored=final_context.hooks_restored,
                            hook_losses=len(final_context.hook_losses),
                            cleanup=[
                                (label, type(error).__name__)
                                for label, error in final_context.cleanup
                            ],
                        )
                    )
        if (
            event == "return"
            and variant in ("source_unwind", "source_capture_unwind")
            and imported is not None
        ):
            original = namespace["_ISSUED"].get(getattr(imported, helper_name))
            # During an active observer no closed issuance exists yet.
            rows = [] if context is None else context.rows
            original = next(
                (r.original for r in rows if r.target[0] == (None, helper_name)), original
            )
            if type(original) is FunctionType and frame.f_code is original.__code__:
                raise original_error from cause
        if event != "call":
            return
        name, code = frame.f_globals.get("__name__", ""), frame.f_code
        if name == "beartype" or name.startswith("beartype."):
            if len(library_work) >= 131072:
                raise ValueError("Bounded metadata library work exhausted")
            library_work.append((name, code.co_qualname))
        elif name == "betse" or name.startswith("betse."):
            relative = str(Path(code.co_filename).relative_to(root))
            allowed = relative in native_pins and (
                code.co_name == "<module>"
                or not code.co_flags & 1
                or (
                    relative == "betse/metadata.py"
                    and code.co_qualname
                    in (
                        "_convert_version_str_to_tuple",
                        "_convert_version_str_to_tuple.<locals>.<genexpr>",
                    )
                )
                or (relative == "betse/util/type/types.py" and code.co_name == "type_check")
                or (relative == authority.COUNTER_HELPER[0] and code.co_name == helper_name)
            )
            if not allowed:
                forbidden.append((name, code.co_qualname))
                raise AssertionError("Native model/geometry work held")
            metadata_work.append((name, code.co_qualname))
            if variant == "reentry" and code.co_name == helper_name and not reentered:
                reentered = True
                callback_work.append(dict(helper=helper_name, completed=False, result=None))
                callback_result = getattr(imported, helper_name)()
                callback_work[-1].update(completed=True, result=callback_result)
        elif code.co_filename.startswith("<@beartype(betse."):
            maker = frame.f_back
            definition = (
                code.co_name == "<module>"
                and backend is not None
                and maker.f_code is backend.functions["make"].__code__
                and maker.f_locals.get("func_code_compiled") is code
            )
            known = any(
                row.output is not None and row.output.__code__ is code
                for scope in scopes
                for row in getattr(scope.get("context"), "rows", ())
            )
            metadata = sys.modules.get("betse.metadata")
            convert = (
                None if metadata is None else vars(metadata).get("_convert_version_str_to_tuple")
            )
            known = known or (type(convert) is FunctionType and convert.__code__ is code)
            if not definition and not known:
                forbidden.append(("unowned_generated_body", code.co_qualname))
                raise AssertionError("Unowned native wrapper invocation held")
        elif name.startswith(("numpy.random", "numpy.linalg", "scipy.", "random")):
            forbidden.append((name, code.co_qualname))
            raise AssertionError("Numerical/RNG work held")

    def held(*args, **kwargs):
        forbidden.append("numeric_operator_or_RNG")
        raise AssertionError("Numerical/RNG work held")

    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != "betse" and not fullname.startswith("betse."):
                return None
            relative = fullname.replace(".", "/") + ".py"
            if relative not in native_pins:
                relative = fullname.replace(".", "/") + "/__init__.py"
            if relative not in native_pins:
                forbidden.append(fullname)
                raise AssertionError("Only the closed pinned metadata import chain is released")
            return importlib.util.spec_from_loader(
                fullname, backend.loader_type(fullname, str(root / relative))
            )

    finder = Finder()
    try:
        sys.meta_path.insert(0, finder)
        for group, names in (
            (np.random, ("seed", "default_rng", "RandomState", "random", "normal", "uniform")),
            (np.linalg, ("inv", "pinv", "solve", "lstsq", "svd")),
        ):
            for name in names:
                restored.append((group, name, getattr(group, name)))
                setattr(group, name, held)
        sys.path.extend((str(root), *(str(p) for p in authority.ROOTS)))
        sys.setprofile(profile)
        backend = authority._backend()
        selected = (
            [(observer, api)]
            if lifecycle is None
            else [(COUNTER_OBSERVERS[i], apis[i]) for i in (1, 2, 3, 0)]
        )
        for label, chosen in selected:
            include = (
                lifecycle is None
                or lifecycle == "nested_all_counters"
                or (lifecycle != "nested_no_effect" and label == "runtime")
            )
            scope_namespace, scope_manager = _counter_scope(
                chosen,
                authority,
                backend,
                include,
                context_export=context_export_enabled and label == "runtime",
            )
            scopes.append(dict(label=label, namespace=scope_namespace, manager=scope_manager))
        namespace = scopes[0 if lifecycle is None else 2]["namespace"]
        if lifecycle in ("nested_prefix", "nested_guards"):
            import pytest

            from tests.unit import test_betse_native_init_molecule_wrapper_authority as controls

            guard_patch = pytest.MonkeyPatch()
            guard_models = controls.issued_guard_models.__wrapped__(guard_patch)

        @contextlib.contextmanager
        def guard_window():
            if lifecycle == "nested_prefix":
                for index in (0, 1, 1):
                    model = guard_models[index]
                    with model.manager(model.child):
                        for scope in scopes:
                            scope["namespace"]["validate_import_guards"](scope["context"])
                with guard_models[2].manager(guard_models[2].child):
                    yield
            elif lifecycle == "nested_guards":
                with contextlib.ExitStack() as guards:
                    for model in guard_models:
                        guards.enter_context(model.manager(model.child))
                    yield
            else:
                yield

        def teardown_fault():
            inner = scopes[-1]
            proof = inner["context"]
            monitor = sys.monitoring
            if lifecycle == "own_events":
                monitor.set_events(proof.tool, 0)
            elif lifecycle == "own_callback":
                callback = inner["manager_instance"].gen.gi_frame.f_locals["returned"]
                copied = FunctionType(
                    callback.__code__, callback.__globals__, closure=callback.__closure__
                )
                monitor.register_callback(proof.tool, monitor.events.PY_RETURN, copied)
            elif lifecycle == "own_local":
                monitor.set_local_events(
                    proof.tool, backend.functions["loader"].__code__, monitor.events.LINE
                )
            elif lifecycle in ("foreign_tool", "own_tool"):
                if lifecycle == "own_tool":
                    slot = proof.tool
                    monitor.free_tool_id(slot)
                else:
                    slot = next(i for i in range(6) if monitor.get_tool(i) is None)
                monitor.use_tool_id(slot, "Key isolated foreign-tool refusal fixture")
                monitor.set_events(slot, monitor.events.PY_START)
                foreign_slots.append(slot)
            elif lifecycle == "profile_drop":
                sys.setprofile(None)
            elif lifecycle == "trace_change":
                sys.settrace(lambda *args: None)
            elif lifecycle in (
                "getter_failure",
                "setter_failure",
                "callback_restore_failure",
                "free_failure",
                "primary_cleanup_failure",
            ):
                proxy = SimpleNamespace(**vars(sys))
                if lifecycle in ("getter_failure", "primary_cleanup_failure"):
                    reads = []

                    def bad_getter():
                        reads.append(1)
                        if len(reads) == 1:
                            raise OSError("isolated hook getter failure")
                        return sys.getprofile()

                    proxy.getprofile = bad_getter
                elif lifecycle == "setter_failure":
                    sys.setprofile(None)

                    def bad_setter(value):
                        raise OSError("isolated hook setter failure")

                    proxy.setprofile = bad_setter
                else:
                    if lifecycle == "free_failure":
                        original_free = monitor.free_tool_id
                        monitor_api_originals.append(("free_tool_id", original_free))

                        def bad_free(tool):
                            monitor.free_tool_id = original_free
                            fault_calls.append(("free_tool_id", tool))
                            raise OSError("isolated tool free failure")

                        monitor.free_tool_id = bad_free
                    else:
                        original_callback = monitor.register_callback
                        monitor_api_originals.append(("register_callback", original_callback))

                        def bad_callback(tool, event, function):
                            monitor.register_callback = original_callback
                            fault_calls.append(("register_callback", tool, event))
                            raise OSError("isolated callback restore failure")

                        monitor.register_callback = bad_callback
                inner["namespace"]["sys"] = proxy
            elif lifecycle == "teardown_binding_drift":
                original_free = monitor.free_tool_id
                monitor_api_originals.append(("free_tool_id", original_free))

                def changed_after_free(tool):
                    monitor.free_tool_id = original_free
                    original_free(tool)
                    fault_calls.append(("free_and_mutate", tool))
                    source_row = next(r for r in proof.rows if r.target[0] != (None, helper_name))
                    source_row.original.__defaults__ = (None,)

                monitor.free_tool_id = changed_after_free

        @contextlib.contextmanager
        def window():
            with contextlib.ExitStack() as stack:
                for scope in scopes:
                    os.environ[scope["namespace"]["RELEASE"]] = "1"
                    instance = scope["manager_instance"] = scope["manager"](enabled=True)
                    scope["context"] = stack.enter_context(instance)
                try:
                    yield scopes[0 if lifecycle is None else 2]["context"]
                finally:
                    teardown_fault()

        original_event = namespace["_counter_event"]
        if variant == "capture_return":

            def bad_commit(*args):
                raise ValueError("counter return capture failure")

            namespace["_counter_commit"] = bad_commit
        elif variant == "source_capture_unwind":

            def bad_unwind(*args):
                original_event(*args)
                if args[-2] == "unwind":
                    raise ValueError("counter unwind capture failure")

            namespace["_counter_event"] = bad_unwind
        # The original factory/row checks still run; only the isolated candidate
        # release key is declared, never a retained real input owner.
        os.environ[namespace["RELEASE"]] = "1"
        try:
            with window() as context, guard_window():
                imported = importlib.import_module("betse.util.type.iterable.mapping.mapcls")
                if context_export_enabled:
                    if lifecycle == "nested_export_factory":
                        original_factory = contextlib.contextmanager
                        restored.append((contextlib, "contextmanager", original_factory))
                        contextlib.contextmanager = FunctionType(
                            original_factory.__code__, original_factory.__globals__
                        )
                        export_edits.append(lifecycle)
                    elif lifecycle == "nested_export_wraps":
                        original_wraps = contextlib.wraps
                        restored.append((contextlib, "wraps", original_wraps))

                        def foreign_wraps(*args, **kwargs):
                            foreign_wraps_calls.append(1)
                            return original_wraps(*args, **kwargs)

                        contextlib.wraps = foreign_wraps
                        export_edits.append(lifecycle)
                    exported = importlib.import_module("betse.util.type.contexts")
                    if context.capture_error is not None:
                        raise context.capture_error
                    for scope in scopes:
                        for export_row in scope["context"].rows:
                            if export_row.target[0] == (None, "noop_context"):
                                export_observations.append(
                                    dict(
                                        scope=scope["label"],
                                        target=export_row.target[0],
                                        original=_atom(export_row.original),
                                        factory_output=_atom(export_row.output),
                                        published_export=_atom(exported.noop_context),
                                        actual_export_is_factory_output=(
                                            exported.noop_context is export_row.output
                                        ),
                                        export_wrapped_is_factory_output=(
                                            vars(exported.noop_context).get("__wrapped__")
                                            is export_row.output
                                        ),
                                        export_code=(
                                            exported.noop_context.__code__.co_filename,
                                            exported.noop_context.__code__.co_qualname,
                                        ),
                                        annotation_before=_atom(
                                            export_row.context_export.annotation_before[0][1]
                                        ),
                                        annotation_after=_atom(
                                            export_row.context_export.annotation_after[0][1]
                                        ),
                                    )
                                )
                    export_row = next(
                        r for r in context.rows if r.target[0] == (None, "noop_context")
                    )

                    def change_export():
                        current = exported.noop_context
                        if lifecycle in ("nested_export_equal", "nested_export_closed"):
                            copied = FunctionType(
                                current.__code__,
                                current.__globals__,
                                current.__name__,
                                current.__defaults__,
                                current.__closure__,
                            )
                            copied.__kwdefaults__, copied.__annotations__ = (
                                current.__kwdefaults__,
                                current.__annotations__,
                            )
                            copied.__qualname__, copied.__module__, copied.__doc__ = (
                                current.__qualname__,
                                current.__module__,
                                current.__doc__,
                            )
                            vars(copied).update(vars(current))
                            exported.noop_context = copied
                        elif lifecycle == "nested_export_foreign":
                            exported.noop_context = lambda: None
                        elif lifecycle == "nested_export_retarget":
                            current.__closure__[0].cell_contents = FunctionType(
                                export_row.original.__code__, export_row.original.__globals__
                            )
                        elif lifecycle == "nested_export_code":
                            current.__code__ = current.__code__.replace()
                        elif lifecycle == "nested_export_input":
                            export_row.context_export.input.__closure__[
                                0
                            ].cell_contents = FunctionType(
                                export_row.original.__code__, export_row.original.__globals__
                            )
                        elif lifecycle == "nested_export_record":
                            context.context_exports.clear()
                        elif lifecycle == "nested_export_dispatch":
                            function = context.backend.context_functions[1][0]
                            restored.append((function, "__code__", function.__code__))
                            function.__code__ = function.__code__.replace()
                        elif lifecycle == "nested_export_origin":
                            context.source_context_factories.clear()
                        elif lifecycle == "nested_export_annotation_after":
                            hint = export_row.original.__annotations__["return"]
                            if type(hint) is not GenericAlias:
                                raise ValueError("Exact declared original generic hint required")
                            export_row.original.__annotations__["return"] = GenericAlias(
                                hint.__origin__, hint.__args__
                            )
                        else:
                            return
                        export_edits.append(lifecycle)

                    if lifecycle != "nested_export_closed":
                        change_export()
                row = next((r for r in context.rows if r.target[0] == (None, helper_name)), None)
                if variant == "counter_before":
                    setattr(imported, counter_name, 1)
                elif variant == "original_defaults":
                    row.original.__defaults__ = (None,)
                elif variant == "original_code":
                    row.original.__code__ = row.original.__code__.replace()
                elif variant == "foreign_export":
                    old = row.output
                    copied = FunctionType(
                        old.__code__,
                        old.__globals__,
                        old.__name__,
                        old.__defaults__,
                        old.__closure__,
                    )
                    copied.__kwdefaults__, copied.__annotations__ = (
                        old.__kwdefaults__,
                        old.__annotations__,
                    )
                    vars(copied).update(vars(old))
                    setattr(imported, helper_name, copied)
                elif variant == "global_str":
                    vars(imported)["str"] = lambda value: str(value)
                calls = (
                    3
                    if variant == "repeated"
                    else namespace["MAX_COUNTER_CALLS"] + 1
                    if variant == "budget"
                    else 0
                    if lifecycle == "nested_no_effect"
                    else 1
                )
                for _ in range(calls):
                    function = getattr(imported, helper_name)
                    if variant == "foreign_body":
                        function = FunctionType(
                            row.original.__code__, row.original.__globals__, row.original.__name__
                        )
                    results.append(function())
                if variant == "counter_after":
                    setattr(imported, counter_name, getattr(imported, counter_name) + 1)
                elif variant == "record_drop":
                    context.counter_attempts.clear()
                if lifecycle in (
                    "nested_exception",
                    "primary_cleanup_failure",
                    "bookkeeping_id_primary",
                    "bookkeeping_values_falsey",
                ):
                    raise original_error from cause
            current = None if row is None else namespace["_wrapper_state"](row.original, backend)
            try:
                if row is not None:
                    namespace["_same"](current, row.original_bindings)
            except ValueError as error:
                differences = [
                    i
                    for i, (a, b) in enumerate(zip(current, row.original_bindings, strict=True))
                    if a is not b
                ]
                strict_difference = dict(
                    before_count=len(row.original_bindings),
                    current_count=len(current),
                    indices=differences,
                    reason=str(error),
                )
            if variant == "closed_call":
                results.append(getattr(imported, helper_name)())
            if lifecycle == "nested_export_closed":
                change_export()
            for scope in scopes:
                for row in scope["context"].rows:
                    scope["namespace"]["validate"](
                        row.output,
                        row.original,
                        owner=row.module if row.stack is None else row.stack[0],
                        attribute=row.target[0][1],
                    )
                    validations += 1
        except BaseException as error:
            primary = error
            source_identity, cause_identity = error is original_error, error.__cause__ is cause
    finally:
        for name, function in monitor_api_originals:
            setattr(sys.monitoring, name, function)
        if guard_patch is not None:
            guard_patch.undo()
        for scope in reversed(scopes):
            proof = scope.get("context")
            if proof is None:
                continue
            tool = proof.tool
            actual_label = sys.monitoring.get_tool(tool)
            if actual_label is getattr(proof, "tool_label", None) and actual_label is not None:
                sys.monitoring.set_events(tool, 0)
                for event, _, prior in getattr(proof, "monitor_callbacks", ()):
                    sys.monitoring.register_callback(tool, event, prior)
                sys.monitoring.free_tool_id(tool)
                fixture_recovery.append((scope["label"], "owned_tool_after_refusal"))
            elif actual_label is None and getattr(proof, "cleanup", ()):
                for event, _, prior in getattr(proof, "monitor_callbacks", ()):
                    sys.monitoring.register_callback(tool, event, prior)
                fixture_recovery.append((scope["label"], "callbacks_after_refusal"))
        for slot in foreign_slots:
            if sys.monitoring.get_tool(slot) is not None:
                sys.monitoring.set_events(slot, 0)
                sys.monitoring.free_tool_id(slot)
                fixture_recovery.append(("foreign_fixture", slot))
        for group, name, function in restored:
            setattr(group, name, function)
        sys.meta_path.remove(finder)
        sys.settrace(before[1])
        sys.setprofile(before[0])
        attempts = [] if context is None else getattr(context, "counter_attempts", [])
        effects = [] if context is None else context.counter_effects
        raw_counter = [] if context is None else context.counter_raw
        snapshot.write_json(directory / "runtime.json", runtime.inventory())
        snapshot.write_json(
            directory / "counter-probe.json",
            dict(
                variant=variant,
                observer=observer,
                lifecycle=lifecycle,
                boundary_hits=boundary_hits,
                export_observations=export_observations,
                export_edits=export_edits,
                foreign_wraps_calls=foreign_wraps_calls,
                bookkeeping_primary_retained=primary is original_error,
                boundary_error_retained=any(
                    any(
                        error is boundary_error for _, error in getattr(s["context"], "cleanup", ())
                    )
                    for s in scopes
                    if "context" in s
                ),
                cleanup_samples=cleanup_samples,
                fixture_recovery=fixture_recovery,
                fault_calls=fault_calls,
                all_tools_restored=tuple(
                    (sys.monitoring.get_tool(i), sys.monitoring.get_events(i)) for i in range(6)
                )
                == monitoring_before,
                conditional_guard_code_only_no_native_owner=True,
                guard_model_work=[len(m.child.work) for m in guard_models],
                observer_scopes=[
                    dict(
                        label=s["label"],
                        published=s["context"].published,
                        counter_effects=len(s["context"].counter_effects),
                        completed_counter_calls=sum(
                            len(e.history) for e in s["context"].counter_effects
                        ),
                        hooks_restored=getattr(s["context"], "hooks_restored", False),
                        monitor_restored=getattr(s["context"], "monitor_restored", False),
                        monitor_losses=len(getattr(s["context"], "monitor_losses", ())),
                        hook_losses=len(s["context"].hook_losses),
                        cleanup=[
                            (label, type(error).__name__)
                            for label, error in getattr(s["context"], "cleanup", ())
                        ],
                        monitor_original=getattr(s["context"], "monitor_original", None),
                        monitor_final=getattr(s["context"], "monitor_final", None),
                        guard_closed=len(s["context"].guard_closed),
                        active=s["context"].active,
                        active_registry_entries=len(s["namespace"]["_ACTIVE"]),
                        issued_entries=len(s["namespace"]["_ISSUED"]),
                        publication_monitor_final=getattr(
                            s["context"], "publication_monitor_final", None
                        ),
                        cleanup_monitor_final=getattr(s["context"], "cleanup_monitor_final", None),
                    )
                    for s in scopes
                    if "context" in s
                ],
                primary=None
                if primary is None
                else dict(type=type(primary).__name__, message=str(primary)),
                published=False if context is None else context.published,
                results=results,
                validations=validations,
                actual_counter=None if imported is None else getattr(imported, counter_name),
                strict_difference=strict_difference,
                source_primary_identity=source_identity,
                source_cause_identity=cause_identity,
                counter_attempts=[
                    dict(
                        ordinal=a.ordinal,
                        before=a.before,
                        after=a.after,
                        output=a.output,
                        completed=a.completed,
                        frame_identity=id(a.frame),
                        callee_identity=id(a.callee),
                        wrapper_identity=None if a.wrapper is None else id(a.wrapper),
                        primary=None if a.primary is None else type(a.primary).__name__,
                    )
                    for a in attempts
                ],
                counter_history=[]
                if context is None
                else [
                    dict(
                        ordinal=a.ordinal,
                        before=a.before,
                        after=a.after,
                        output=a.output,
                        completed=a.completed,
                    )
                    for effect in context.counter_effects
                    for a in effect.history
                ],
                counter_calls=dict(
                    body=sum(
                        event == "call" and any(value is e.row.original for e in effects)
                        for _, event, value in raw_counter
                    ),
                    wrapper=sum(
                        event == "call"
                        and any(
                            value is e.row.output and value is not e.row.original for e in effects
                        )
                        for _, event, value in raw_counter
                    ),
                    starts=sum(
                        event == "start" and any(frame.f_code is e.original_code for e in effects)
                        for frame, event, _ in raw_counter
                    ),
                    profiled_helper_entries=sum(
                        name == "betse.util.type.iterable.mapping.mapcls" and qual == helper_name
                        for name, qual in metadata_work
                    ),
                ),
                counter_raw=[
                    dict(
                        event=event,
                        frame_identity=id(frame),
                        namespace_identity=id(frame.f_globals),
                        frame_code=(
                            frame.f_code.co_filename,
                            frame.f_code.co_firstlineno,
                            frame.f_code.co_qualname,
                        ),
                        value_identity=id(value),
                        value_type=(
                            type.__getattribute__(type(value), "__module__"),
                            type.__getattribute__(type(value), "__qualname__"),
                        ),
                        text=value if type(value) is str else None,
                    )
                    for frame, event, value in raw_counter
                ],
                capture_errors=[]
                if context is None
                else [(x[0], type(x[1]).__name__, str(x[1])) for x in context.capture_errors],
                raw_counter_events=0
                if context is None
                else len(getattr(context, "counter_raw", [])),
                library_work=library_work,
                metadata_work=metadata_work,
                callback_work=callback_work,
                forbidden=forbidden,
                hooks_restored=sys.getprofile() is before[0] and sys.gettrace() is before[1],
                observer_restored=context is None
                or (
                    getattr(context, "hooks_restored", False)
                    and getattr(context, "monitor_restored", False)
                ),
                native_source_pins=native_pins,
                wrapper_sha256=pin,
                conditional_private_scope_projection=True,
                genuine_INIT_phase_geometry_or_scientific_credit=0,
            ),
        )
    if forbidden:
        raise AssertionError("Forbidden model/RNG/geometry work attempted")


BOOTSTRAP_PLAN = (
    "/mnt/workspaces/Cells/native-basic-end-to-end-20261105-01/prepared-original-05/demo-plan.json",
    "c8e797987b8fb9127b8d4f83c353a234d9ae0d38e43e24b9e76665696ade7b03",
)
BOOTSTRAP_ORDER = (
    "tissue.from_configuration",
    "tissue.prepare",
    "simulator.from_tissue",
    "simulator.prepare",
    "callbacks.from_simulator",
    "callbacks.prepare",
)
# Only import-time metadata builders; never requirement evaluation or export.
# ruff: noqa: E501
BOOTSTRAP_DECLARATIONS = {
    "betse/science/phase/require/phasereqsmake.py": (
        "cc30ccf9b5c8db3a25a0e7dfb53049d9a9ebfe73c389a54d47f683bf7f31a905",
        (
            "make_requirements",
            "make_requirements_funcs",
            "make_requirements_bool_expr",
            "make_requirements_enum_expr",
            "make_requirements_ion",
        ),
    ),
    "betse/science/phase/require/abc/phasereqabc.py": (
        "51ebf4dbd28de9961b3913fb1794295f17a64d338d61a26bebc82c5be265b5c6",
        (
            "SimPhaseRequirement.__init__",
            "SimPhaseRequirement.name",
            "SimPhaseRequirement.is_satisfied",
            "SimPhaseRequirement.set_satisfied",
            "SimPhaseRequirementEmbodied.__init__",
            "SimPhaseRequirementBoolExpr.__init__",
            "SimPhaseRequirementEnumExpr.__init__",
        ),
    ),
    "betse/science/phase/require/abc/phasereqset.py": (
        "718f4b1015af8427f86e6c3e43b1db8e14240746efa71b1fac40a966ca5e0490",
        (
            "SimPhaseRequirements.__new__",
            "SimPhaseRequirements.name",
            "SimPhaseRequirements.name.<locals>.<genexpr>",
            "SimPhaseRequirements.isintersection",
        ),
    ),
    "betse/science/pipe/piperun.py": (
        "04e82dcb038afabee1f7e9fc99936a3a5e1d18cd76328df4ec1ea12b0e76a1a9",
        (
            "SimPipeRunnerMetadata.__init__",
            "piperunner",
            "piperunner.<locals>._piperunner_method_factory",
        ),
    ),
    "betse/science/pipe/pipeabc.py": (
        "8608bac4e1a565dc859a9e7478032fad5a532cd3b8d22fe164c0d03e9a35b9f4",
        (
            "SimPipeABCMeta.__new__",
            "SimPipeABC.iter_runners_method",
            "SimPipeABC._RUNNER_METHOD_NAME_PREFIX",
        ),
    ),
    "betse/science/pipe/export/pipeexpabc.py": (
        "1ad253c6ddc5f6a56c0520fafba8e100b7b98cecf7bd514e8b066c4d07634b14",
        (
            "SimPipeExportABC._RUNNER_METHOD_NAME_PREFIX",
            "SimPipeExportABC._VERB_CONTINUOUS",
        ),
    ),
    "betse/science/pipe/export/pipeexpcsv.py": (
        "ddedc91955309f459cd161ae0191fcbd466e3cc6f44c608e7b76ac6f1f0d3e1c",
        ("SimPipeExportCSVs._NOUN_SINGULAR",),
    ),
    "betse/science/pipe/export/pipeexpanim.py": (
        "c2d7380c95c87c49cee6b2b60966835ea17b26ee2267318455edce34c6bd330c",
        ("SimPipeExportAnimCells._NOUN_SINGULAR",),
    ),
    "betse/science/pipe/export/plot/pipeexpplotcell.py": (
        "230602b5fbc0ca47db361c23a2de608a6b4f2c6169ab9a2a308f0c4b7fd85290",
        ("SimPipeExportPlotCell._NOUN_SINGULAR",),
    ),
    "betse/science/pipe/export/plot/pipeexpplotcells.py": (
        "4246e2a2a9edce94b1b59d73e747b8ba9ed10754bf78cd0c9d58963bbe9d5097",
        ("SimPipeExportPlotCells._NOUN_SINGULAR",),
    ),
}
BOOTSTRAP_DECLARATION_REVIEW = (
    "/mnt/workspaces/Cells/native-wrapper-simrunner-declaration-roster-preparation-20261107-01/root-declaration-scope-review.json",
    "acc5a57ef9c78f431a188c9268720fee8aff3b74ae831dec71106f24510eade3",
)


def bootstrap_probe(directory, *, runner_import=False):
    """Real six auxiliary APIs; no world, phase, INIT, model or trajectory."""
    if os.environ.get(BOOTSTRAP_RELEASE) != "1" or os.sched_getaffinity(0) != {5} or not __debug__:
        raise ValueError("Explicit CPU5 six-API metadata release required")
    if type(runner_import) is not bool:
        raise ValueError("Explicit metadata-only runner import condition required")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    directory = directory.absolute()
    if (
        not directory.is_relative_to("/mnt/workspaces/Cells")
        or directory != directory.resolve(strict=False)
        or any(path.is_symlink() for path in (directory, *directory.parents))
    ):
        raise ValueError("Fresh canonical metadata evidence path required")
    directory.mkdir()
    scratch = directory / "runtime-cache/tmp"
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = str(scratch)
    tempfile_module = sys.modules.get("tempfile")
    if tempfile_module is not None and vars(tempfile_module).get("tempdir") not in (
        None,
        str(scratch),
    ):
        raise ValueError("Foreign initialized temporary-directory cache refused")
    plan_path = Path(BOOTSTRAP_PLAN[0])
    if snapshot.digest(plan_path) != BOOTSTRAP_PLAN[1]:
        raise ValueError("Exact original05 auxiliary metadata inputs required")
    plan = json.loads(plan_path.read_text())
    bootstrap_path = Path(plan["callback_bootstrap"])
    if snapshot.digest(bootstrap_path) != plan["callback_bootstrap_sha256"]:
        raise ValueError("Exact original05 bootstrap runtime declaration required")
    declared = json.loads(bootstrap_path.read_text())
    if runner_import:
        scope_path = Path(BOOTSTRAP_DECLARATION_REVIEW[0])
        if snapshot.digest(scope_path) != BOOTSTRAP_DECLARATION_REVIEW[1]:
            raise ValueError("Exact declaration-only import scope review required")
        scope = json.loads(scope_path.read_text())
        if scope["native_sources"] != {
            path: dict(sha256=pin, qualnames=list(names))
            for path, (pin, names) in BOOTSTRAP_DECLARATIONS.items()
        }:
            raise ValueError("Reviewed declaration constructor/factory roster changed")
    from validation.betse import betse_native_parameter_world_ready_qualification as provider
    from validation.betse import native_seed_demo as demo
    from validation.betse import native_seed_demo_launch as launch
    from validation.betse import native_seed_world_callback_prelude as prelude

    # Same real retained library regime; no full prelude/resource override.
    # Only the metadata worker's fresh cache/output path is newly declared.
    provider._runtime_entry(declared["runtime"])
    os.environ["MPLCONFIGDIR"] = str(directory / "runtime-cache/matplotlib")
    if (
        os.environ.get("HOME") != declared["environment"]["HOME"]
        or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1"
        or any(
            os.environ.get(name) != "1"
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        )
        or os.environ.get("CUDA_VISIBLE_DEVICES") != ""
    ):
        raise ValueError("Unchanged HOME, one thread and no GPU required")
    import numpy as np

    from cells.processes import betse_native_init_molecule_wrapper_authority as authority
    from cells.processes import betse_native_init_sim_assembly as assembly
    from cells.processes import betse_native_init_sim_preparation as preparation
    from cells.processes import betse_native_sim_run as run
    from validation.betse.native_single_cell_prefix_qualification import Evidence

    pin = snapshot.digest(Path(authority.__file__))
    preparation.WRAPPER_OBSERVER_SHA256 = assembly.WRAPPER_SHA256 = pin
    # Fresh private import registries select the actual four source rosters.
    # This software projection adopts no retained INIT/current-p/SIM producer.
    apis = (
        ("runner", preparation._wrapper_api()),
        ("phase", assembly._phase_import_api()),
        ("runtime", run._runtime_import_api()),
        ("molecule", vars(authority)),
    )
    modules = {name: importlib.import_module(module) for name, module in prelude.MODULES.items()}
    for name, module in modules.items():
        if snapshot.digest(Path(module.__file__)) != prelude.SOURCE_PINS[name]:
            raise ValueError("Exact actual auxiliary API producer required: " + name)
    state = prelude.Execution()
    state.path_links = tuple(
        (path, json.dumps(record, sort_keys=True, allow_nan=False))
        for path, record in declared["native_links"].items()
    )
    prelude._check_links(state)
    prelude._fresh_native()
    capture_directory = directory / "captures"
    capture_directory.mkdir()
    evidence = Evidence(capture_directory, sidecars=True)
    before = sys.getprofile(), sys.gettrace()
    monitor_before = tuple(
        (sys.monitoring.get_tool(i), sys.monitoring.get_events(i)) for i in range(6)
    )
    primary, later, contexts, api_calls, forbidden = None, [], [], [], []
    capture_exceptions = []
    native_work, library_work, owned_work, stdlib_work = Counter(), Counter(), Counter(), Counter()
    work_entries = 0
    functions = {}
    for label, names in (
        ("tissue", ("from_configuration", "prepare")),
        ("simulator", ("from_tissue", "prepare")),
        ("callbacks", ("from_simulator", "prepare")),
    ):
        for name in names:
            function = vars(modules[label])[name]
            functions[function.__code__] = label + "." + name
    native_root = str(authority.network.NATIVE) + "/"
    restores = []
    native_home = Path.home() / ".betse"
    writable = (native_home.resolve(strict=True),)
    if (
        str(native_home) not in declared["native_write_roots"]
        or not native_home.is_symlink()
        or not writable[0].is_relative_to("/mnt/workspaces/Cells")
    ):
        raise ValueError("Original explicit native metadata home/log authority required")
    writer_review = Path(
        "/mnt/workspaces/Cells/native-seed-demo-20261103-01/actual-preparation-01/shared-writer-review.json"
    )
    if (
        snapshot.digest(writer_review)
        != "2f6b64bb8cfb7a7eb70f203e51f1444849d7c0ed19adc580b02d044b1c799af0"
    ):
        raise ValueError("Exact process-lifetime writer coordination required")
    policy = session = None
    setup_operations = []
    additional_imports = []
    declaration_sources = {}

    def declaration_body(frame, relative):
        if (
            not runner_import
            or not additional_imports
            or additional_imports[-1]["status"] != "attempted"
        ):
            return False
        specification = BOOTSTRAP_DECLARATIONS.get(relative)
        if specification is None or frame.f_code.co_qualname not in specification[1]:
            return False
        parent = frame.f_back
        runner_frame = None
        while parent is not None:
            if parent.f_code.co_name == "<module>" and parent.f_code.co_filename == str(
                authority.network.NATIVE / preparation.source.RUNNER
            ):
                runner_frame = parent
                break
            parent = parent.f_back
        module = sys.modules.get("betse.science.simrunner")
        if runner_frame is None or module is None or runner_frame.f_globals is not vars(module):
            return False
        if relative not in declaration_sources:
            path = authority.network.NATIVE / relative
            if path.is_symlink() or snapshot.digest(path) != specification[0]:
                raise ValueError("Exact original import-time metadata declarations required")
            declaration_sources[relative] = specification[0]
        return True

    def profile(frame, event, value):
        nonlocal work_entries
        if before[0] is not None:
            before[0](frame, event, value)
        if event != "call":
            return
        work_entries += 1
        # This is an observation envelope, not a native factory/owner budget.
        # Include verifier/stdlib calls too; the source/domain guards and
        # original per-owner/factory caps remain independent and unchanged.
        if work_entries > 16777216:
            raise ValueError("Bounded auxiliary metadata work exhausted")
        code, module = frame.f_code, frame.f_globals.get("__name__", "")
        if code.co_filename == "<string>" and code.co_name in ("is_satisfied", "set_satisfied"):
            forbidden.append("generated_requirement_predicate_invocation")
            raise AssertionError("Requirement evaluation/mutation remains held")
        if code in functions:
            api_calls.append(functions[code])
            for _, _, proof in contexts:
                if proof.capture_error is not None:
                    raise proof.capture_error
        if code.co_filename.startswith(native_root):
            relative = code.co_filename.removeprefix(native_root)
            declaration = code.co_name == "<module>" or not code.co_flags & 1
            selected = (
                not relative.startswith("betse/science/")
                or relative.startswith(("betse/science/config/", "betse/science/enum/"))
                or (relative == "betse/science/sim.py" and code.co_qualname == "Simulator.__init__")
                or (
                    relative == "betse/science/phase/phasecallbacks.py"
                    and code.co_qualname == "make_default"
                )
                or declaration_body(frame, relative)
            )
            if not declaration and not selected:
                forbidden.append((module, code.co_qualname))
                raise AssertionError("Native world/phase/model/source/solve held")
            native_work[(relative, code.co_qualname)] += 1
        elif module.startswith("beartype"):
            library_work[(module, code.co_qualname)] += 1
        elif module.startswith("cells.processes."):
            owned_work[(module, code.co_qualname)] += 1
        elif module in ("tempfile", "random", "contextlib", "functools"):
            stdlib_work[(module, code.co_qualname)] += 1

    def held(*args, **kwargs):
        forbidden.append("numerical_or_RNG_entry")
        raise AssertionError("Native numerical/trajectory RNG work held")

    def context_document(label, api, context):
        exported = []
        for row in context.rows:
            if row.target[0] == (None, "noop_context"):
                item = row.context_export
                if item is None or not item.returned or item.factory_frame is None:
                    exported.append(
                        dict(
                            target=row.target[0],
                            original=_atom(row.original),
                            inner=_atom(row.output),
                            incomplete_transform=True,
                        )
                    )
                    continue
                exported.append(
                    dict(
                        target=row.target[0],
                        original=_atom(row.original),
                        inner=_atom(row.output),
                        actual_export=_atom(vars(row.module)["noop_context"]),
                        observed_export=_atom(item.output),
                        exact_published_export=vars(row.module)["noop_context"] is item.output,
                        exact_wrapped_generator=vars(item.output).get("__wrapped__") is row.output,
                        helper_frame=(item.frame.f_code.co_filename, item.frame.f_code.co_qualname),
                        factory_frame=(
                            item.factory_frame.f_code.co_filename,
                            item.factory_frame.f_code.co_qualname,
                        ),
                        source_factory_frame=(
                            item.source_factory.frame.f_code.co_filename,
                            item.source_factory.frame.f_code.co_qualname,
                        ),
                        exact_source_factory_return=item.source_factory.output is item.input,
                        factory_annotation_before=_atom(item.annotation_before[0][1]),
                        factory_annotation_after=_atom(item.annotation_after[0][1]),
                        annotation_shared_dictionary_identity=id(item.annotation_dictionary),
                        exact_factory_annotation_return=(
                            row.factory_original_bindings[len(row.factory_original_function) + 2]
                            is item.annotation_after[0][1]
                        ),
                        transform_returned=item.returned,
                    )
                )
        details = []
        for event, error, observed, value in context.capture_errors:
            frames, trace = [], error.__traceback__
            while trace is not None and len(frames) < 32:
                frame = trace.tb_frame
                if frame.f_code.co_filename == authority.__file__:
                    local = frame.f_locals
                    entry = dict(function=frame.f_code.co_name, line=trace.tb_lineno)
                    row = local.get("row")
                    if any(row is old for old in context.rows):
                        entry.update(
                            target=row.target[0],
                            output=_atom(row.output),
                            original=_atom(row.original),
                        )
                    current, original = local.get("current"), local.get("original")
                    if type(current) is tuple and type(original) is tuple:
                        entry.update(
                            current_length=len(current),
                            original_length=len(original),
                            differences=[
                                dict(index=i, current=_atom(a), original=_atom(b))
                                for i, (a, b) in enumerate(zip(current, original, strict=False))
                                if a is not b
                            ][:64],
                        )
                    frames.append(entry)
                trace = trace.tb_next
            details.append(
                dict(
                    event=event,
                    error=type(error).__name__,
                    message=str(error),
                    observed_frame=(observed.f_code.co_filename, observed.f_code.co_qualname),
                    raw_value=_atom(value),
                    frames=frames,
                    forensic_labels_are_not_authority=True,
                )
            )
        return dict(
            label=label,
            rows=len(context.rows),
            published=context.published,
            source_errors=len(context.source_errors),
            raw_returns=len(context.raw_returns),
            capture_errors=[
                (event, type(error).__name__, str(error))
                for event, error, *_ in context.capture_errors
            ],
            capture_error_details=details,
            hooks_restored=context.hooks_restored,
            monitor_restored=context.monitor_restored,
            guard_closed=len(context.guard_closed),
            active=context.active,
            active_registry=len(api["_ACTIVE"]),
            issued=len(api["_ISSUED"]),
            exports=exported,
            counter_calls=sum(len(effect.history) for effect in context.counter_effects),
            original_monitor=context.monitor_original,
            final_monitor=context.monitor_final,
        )

    def retain(label, function, *args):
        try:
            return function(*args)
        except BaseException as capture:
            later.append((label, type(capture).__name__, str(capture)))
            capture_exceptions.append(capture)
            return None

    try:
        sys.setprofile(profile)
        setup_operations.append(dict(operation="canonical_filesystem_policy", status="attempted"))
        policy = launch.WritePolicy(
            directory,
            native_home=native_home,
            native_target=writable[0],
            native_link=declared["native_links"][str(native_home)],
            directories=(),
        )
        launch._WRITE_POLICIES.append(policy)
        sys.addaudithook(policy.audit)
        sys.audit("cells.seed_demo.filesystem_installed", policy)
        if policy.installed is not True:
            raise ValueError("Actual process-lifetime filesystem audit required")
        setup_operations[-1]["status"] = "returned"
        setup_operations.append(dict(operation="original_writer_lease", status="attempted"))
        session = demo._writer_session(prelude, writer_review)
        session.__enter__()
        setup_operations[-1]["status"] = "returned"
        setup_operations.append(dict(operation="canonical_temporary_directory", status="attempted"))
        launch._temporary_directory(directory, policy)
        setup_operations[-1]["status"] = "returned"
        for group, names in (
            (np.random, ("seed", "default_rng", "RandomState", "random", "normal", "uniform")),
            (np.linalg, ("inv", "pinv", "solve", "lstsq", "svd")),
        ):
            for name in names:
                restores.append((group, name, getattr(group, name)))
                setattr(group, name, held)
        os.environ[modules["simulator"].RELEASE] = "1"
        with contextlib.ExitStack() as stack:
            for label, api in apis[:3]:
                os.environ[api["RELEASE"]] = "1"
                context = stack.enter_context(api["observing_native_imports"](enabled=True))
                contexts.append((label, api, context))
            # Execute the existing prelude's exact source and six real APIs.
            # It issues only the same selected auxiliary owners as original05.
            label, api = apis[3]
            os.environ[api["RELEASE"]] = "1"
            with api["observing_native_imports"](enabled=True) as context:
                contexts.append((label, api, context))
                prelude._execute(state, modules, plan["auxiliary_configuration"], evidence)
            if runner_import:
                relative = preparation.source.RUNNER
                original = authority.network.NATIVE / relative
                expected = preparation.source.PINS[relative]
                if original.is_symlink() or snapshot.digest(original) != expected:
                    raise ValueError("Original declared runner metadata source required")
                declaration = dict(
                    module="betse.science.simrunner",
                    path=str(original),
                    sha256=expected,
                    status="attempted",
                    after_real_six_APIs=True,
                    constructor_or_method_invocation=False,
                    after_canonical_molecule_publication=contexts[3][2].published,
                )
                additional_imports.append(declaration)
                from validation.betse import native_sim_demo as sim_demo

                with sim_demo._runner_import_issuance(prelude):
                    imported_runner = importlib.import_module(declaration["module"])
                    if Path(vars(imported_runner)["__file__"]) != original:
                        raise ValueError("Actual original runner module origin required")
                declaration["native_module_issuance_completed"] = True
                declaration["status"] = "returned"
            session.check()
            policy.check()
        for _label, api, context in contexts:
            for row in context.rows:
                api["validate"](
                    row.output,
                    row.original,
                    owner=row.module if row.stack is None else row.stack[0],
                    attribute=row.target[0][1],
                )
        if runner_import:
            # This is the exact registry check at the next Parameters import
            # boundary, after all wrapper observers have published and closed.
            modules["tissue"].aliases._check_modules()
            additional_imports[-1]["parameter_import_registry_ready"] = True
    except BaseException as error:
        primary = error
    finally:
        retain("restore_trace", sys.settrace, before[1])
        retain("restore_profile", sys.setprofile, before[0])
        for group, name, function in restores:
            retain("restore_operator:" + name, setattr, group, name, function)
        if session is not None and session.fd is not None:
            retain(
                "writer_lease_exit_keeps_fd",
                session.__exit__,
                None if primary is None else type(primary),
                primary,
                None if primary is None else primary.__traceback__,
            )
        if policy is not None:
            retain("filesystem_check", policy.check)
        filesystem = None if policy is None else retain("filesystem_record", policy.record)
        if primary is not None:
            retain("source_partial_evidence", evidence.failure, primary)
        context_documents = [
            retain("context:" + row[0], context_document, *row) for row in contexts
        ]
        pins = retain(
            "producer_pins",
            lambda: {
                str(Path(m.__file__)): snapshot.digest(Path(m.__file__))
                for m in (
                    authority,
                    preparation,
                    assembly,
                    run,
                    provider,
                    demo,
                    launch,
                    prelude,
                    *modules.values(),
                )
            },
        )
        hooks_restored = retain(
            "hooks", lambda: sys.getprofile() is before[0] and sys.gettrace() is before[1]
        )
        tools_restored = retain(
            "tools",
            lambda: (
                tuple((sys.monitoring.get_tool(i), sys.monitoring.get_events(i)) for i in range(6))
                == monitor_before
            ),
        )
        document = dict(
            kind="actual_six_auxiliary_API_nested_import_metadata@1",
            parent_plan=dict(path=str(plan_path), sha256=BOOTSTRAP_PLAN[1]),
            original_bootstrap=dict(
                path=str(bootstrap_path), sha256=plan["callback_bootstrap_sha256"]
            ),
            metadata_environment=dict(
                HOME=os.environ["HOME"],
                MPLCONFIGDIR=os.environ["MPLCONFIGDIR"],
                TMPDIR=str(scratch),
                native_write_roots=[str(root) for root in writable],
                historical_Matplotlib_cache_is_not_a_write_root=True,
            ),
            shared_writer_review=dict(
                path=str(writer_review), sha256=snapshot.digest(writer_review)
            ),
            writer_lease=None
            if session is None
            else dict(
                path=str(session.path),
                descriptor=session.fd,
                identity=session.identity,
                retained_to_process_exit=session in demo._PROCESS_LEASES,
            ),
            filesystem=filesystem,
            metadata_setup_operations=setup_operations,
            additional_native_metadata_imports=additional_imports,
            import_time_declaration_sources=declaration_sources,
            declaration_scope_review=None
            if not runner_import
            else dict(path=BOOTSTRAP_DECLARATION_REVIEW[0], sha256=BOOTSTRAP_DECLARATION_REVIEW[1]),
            requirement_evaluation_or_export_invocation=False,
            proposed_corrected_bootstrap_sequence=runner_import,
            original_current_route_has_no_runner_import=not runner_import,
            profiled_python_call_observations=work_entries,
            profile_observation_budget=16777216,
            source_pins=pins,
            actual_api_order=api_calls,
            operations=[
                dict(sequence=row["sequence"], stage=row["stage"], status=row["status"])
                for row in state.operations
            ],
            actual_auxiliary_owners=[
                dict(label=label, owner=_atom(owner)) for label, owner in state.parents
            ],
            completed=state.completed,
            capture_rows=evidence.rows,
            primary=None
            if primary is None
            else dict(type=type(primary).__name__, message=str(primary)),
            later_errors=later,
            forbidden=forbidden,
            contexts=context_documents,
            native_work=[
                dict(file=key[0], qualified=key[1], entries=count)
                for key, count in sorted(native_work.items())
            ],
            library_work=[
                dict(module=key[0], qualified=key[1], entries=count)
                for key, count in sorted(library_work.items())
            ],
            owned_work=[
                dict(module=key[0], qualified=key[1], entries=count)
                for key, count in sorted(owned_work.items())
            ],
            stdlib_metadata_work=[
                dict(module=key[0], qualified=key[1], entries=count)
                for key, count in sorted(stdlib_work.items())
            ],
            temporary_name_library_entropy_is_not_trajectory_RNG=True,
            hooks_restored=hooks_restored,
            tools_restored=tools_restored,
            auxiliary_parameters_or_simulator_are_not_world_or_INIT_or_SIM_authority=True,
            numerical_RNG_solve_or_biological_credit=0,
            actual_source_or_factory_metadata_work_is_not_cases=True,
            private_candidate_projection_only=True,
        )
        try:
            snapshot.write_json(directory / "bootstrap-probe.json", document)
        except BaseException as capture:
            later.append(("write_probe", type(capture).__name__, str(capture)))
            capture_exceptions.append(capture)
            if primary is None:
                primary = capture
        try:
            snapshot.write_json(directory / "runtime.json", runtime.inventory())
        except BaseException as capture:
            later.append(("runtime", type(capture).__name__, str(capture)))
            capture_exceptions.append(capture)
            if primary is None:
                primary = capture
        if later:
            try:
                snapshot.write_json(directory / "capture-errors.json", dict(errors=later))
            except BaseException as capture:
                capture_exceptions.append(capture)
        if primary is None and capture_exceptions:
            primary = capture_exceptions[0]
    if primary is not None:
        raise primary
    if forbidden:
        raise AssertionError("Forbidden auxiliary metadata work attempted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--child", type=Path)
    mode.add_argument("--library-probe", type=Path)
    mode.add_argument("--counter-probe", type=Path)
    mode.add_argument("--lifecycle-probe", type=Path)
    mode.add_argument("--bootstrap-probe", type=Path)
    parser.add_argument("--select", default="")
    parser.add_argument("--library-variant", default="none", choices=LIBRARY_VARIANTS)
    parser.add_argument("--counter-variant", default="none", choices=COUNTER_VARIANTS)
    parser.add_argument("--counter-observer", default="molecule", choices=COUNTER_OBSERVERS)
    parser.add_argument("--lifecycle-variant", default="nested_counter", choices=LIFECYCLE_VARIANTS)
    parser.add_argument("--bootstrap-runner-import", action="store_true")
    args = parser.parse_args()
    if args.library_probe:
        return library_probe(args.library_probe, args.library_variant)
    if args.counter_probe:
        return counter_probe(args.counter_probe, args.counter_variant, args.counter_observer)
    if args.lifecycle_probe:
        return counter_probe(args.lifecycle_probe, lifecycle=args.lifecycle_variant)
    if args.bootstrap_probe:
        return bootstrap_probe(args.bootstrap_probe, runner_import=args.bootstrap_runner_import)
    return prepare(args.prepare, args.select) if args.prepare else child(args.child)


if __name__ == "__main__":
    main()
