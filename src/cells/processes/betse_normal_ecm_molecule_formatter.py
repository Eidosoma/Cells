"""Checked private formatter bindings, without mutating any live owner/global.

Preparing functions does not install them, execute a warm method or admit an
INIT/phase owner. The declared source aliases resolve the literal formatter.
These objects contain live functions and are not checkpoint/decoder vocabulary.
"""

import builtins
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from types import FunctionType, MappingProxyType

import numpy as np

from cells.processes import betse_ecm_grn_source as environment
from cells.processes import betse_normal_ecm_molecule_formatter_source as source
from cells.processes import betse_normal_ecm_molecule_lifecycle_source as lifecycle
from cells.processes import betse_normal_network_join_source as network

PINS = {
    network.__name__: "9f2308e26cee06ad8cfb324791f8a4ce05e304c9a05ef532bdf12e5bab1e774d",
    environment.__name__: "944d497b0416c3cb98167589d4f2d1e664e39ff29ed80d59eb1c264aad2d312f",
    lifecycle.__name__: "33c63bd05aa258b0dae4782d3e543e5269b58a1b6be4a30d1bb7aa6c1e8e1341",
}
SPECS = (
    (network, network._LiteralNetwork, "write_growth_and_decay"),
    (network, network._LiteralNetwork, "write_reactions"),
    (network, network._LiteralNetwork, "get_influencers"),
    (environment, environment.MasterOfNetworks, "write_reactions_env"),
    (lifecycle, lifecycle.MasterOfNetworks, "write_transporters"),
)
_ORIGINALS = tuple(vars(cls)[name] for _, cls, name in SPECS)
_CODES = tuple(f.__code__ for f in _ORIGINALS)
_FUNCTION_BUILTINS = tuple(f.__builtins__ for f in _ORIGINALS)
_DEFAULTS = tuple(f.__defaults__ for f in _ORIGINALS)
_KWDEFAULTS = tuple(f.__kwdefaults__ for f in _ORIGINALS)
_ANNOTATIONS = tuple(f.__annotations__ for f in _ORIGINALS)
_METADATA = tuple((f.__name__, f.__qualname__, f.__module__, f.__doc__) for f in _ORIGINALS)
_FILES = {m.__name__: Path(m.__file__).resolve() for m, _, _ in SPECS}
_FORMATTER, _FORMATTER_CODE = source.tex_val, source.tex_val.__code__
_FORMATTER_BUILTINS = source.tex_val.__builtins__
_FORMATTER_FILE = Path(source.__file__).resolve()
_FORMATTER_PIN = hashlib.sha256(_FORMATTER_FILE.read_bytes()).hexdigest()
_MEAN, _LOG10 = np.mean, math.log10
_CONSUMER_FORMATTER = _FORMATTER
_BUILTINS = {name: getattr(builtins, name) for name in ("type", "float", "int", "abs", "str")}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _builtin_dictionary(namespace):
    """Resolve the construction slot without using FunctionType's fallback."""
    require("__builtins__" in namespace, "Missing explicit consumer builtins namespace")
    value = namespace["__builtins__"]
    if value is builtins:
        value = vars(builtins)
    require(type(value) is dict, "Unowned consumer builtins namespace")
    return value


def check_helper():
    """Inspect the real code/globals/builtins; never evaluate the helper."""
    require(
        source.tex_val is _FORMATTER
        and type(source.tex_val) is FunctionType
        and source.tex_val.__code__ is _FORMATTER_CODE
        and source.tex_val.__globals__ is vars(source)
        and source.tex_val.__builtins__ is _FORMATTER_BUILTINS
        and _builtin_dictionary(vars(source)) is _FORMATTER_BUILTINS
        and source.tex_val.__closure__ is None
        and source.tex_val.__defaults__ is None
        and source.tex_val.__kwdefaults__ is None
        and source.tex_val.__annotations__ == {},
        "Changed formatter function/code/closure association",
    )
    require(
        source.math is math and source.np is np and math.log10 is _LOG10 and np.mean is _MEAN,
        "Changed formatter math/NumPy callable binding",
    )
    require(
        all(
            getattr(builtins, name) is value
            and source.tex_val.__builtins__.get(name) is value
            and vars(source).get(name, value) is value
            for name, value in _BUILTINS.items()
        ),
        "Changed formatter builtin binding",
    )
    require(
        Path(source.__file__).resolve() == _FORMATTER_FILE
        and Path(source.tex_val.__code__.co_filename).resolve() == _FORMATTER_FILE
        and hashlib.sha256(_FORMATTER_FILE.read_bytes()).hexdigest() == _FORMATTER_PIN,
        "Changed formatter source bytes after import",
    )
    return _FORMATTER


def originals():
    """Require the exact present upstream methods before private preparation."""
    check_helper()
    for module, _, _ in SPECS:
        require(
            module.__name__ in PINS
            and Path(module.__file__).resolve() == _FILES[module.__name__]
            and hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            == PINS[module.__name__],
            "Changed formatter consumer source; explicit successor required: " + module.__name__,
        )
    for i, ((module, cls, name), expected, code) in enumerate(
        zip(SPECS, _ORIGINALS, _CODES, strict=True)
    ):
        actual = vars(cls)[name]
        require(
            actual is expected
            and type(actual) is FunctionType
            and actual.__code__ is code
            and actual.__globals__ is vars(module)
            and actual.__globals__.get("tex_val") is _CONSUMER_FORMATTER
            and actual.__closure__ is None
            and actual.__defaults__ is _DEFAULTS[i]
            and actual.__kwdefaults__ is _KWDEFAULTS[i]
            and actual.__annotations__ is _ANNOTATIONS[i]
            and not actual.__annotations__
            and not actual.__dict__
            and (actual.__name__, actual.__qualname__, actual.__module__, actual.__doc__)
            == _METADATA[i]
            and "tex_val" in actual.__code__.co_names,
            "Foreign formatter consumer function/code/globals: " + name,
        )
        require(
            actual.__builtins__ is _FUNCTION_BUILTINS[i]
            and _builtin_dictionary(actual.__globals__) is _FUNCTION_BUILTINS[i],
            "Original formatter consumer cached builtins/namespace mismatch: " + name,
        )
    return _ORIGINALS


@dataclass(frozen=True)
class Prepared:
    """In-memory source plumbing only, never a saved owner/admission record."""

    methods: MappingProxyType


def prepare():
    """Copy each checked function namespace, replacing only tex_val.

    Complete code, defaults, closure, annotations and all other global object
    associations are retained. No class, live instance or module is patched.
    """
    methods = {}
    for (_, _, name), original in zip(SPECS, originals(), strict=True):
        namespace = dict(original.__globals__, tex_val=check_helper())
        require(
            _builtin_dictionary(namespace) is original.__builtins__,
            "Private construction namespace differs from original cached builtins: " + name,
        )
        method = FunctionType(
            original.__code__,
            namespace,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        require(
            method.__builtins__ is original.__builtins__,
            "Private construction cached builtins differ from original: " + name,
        )
        method.__kwdefaults__ = original.__kwdefaults__
        method.__annotations__ = original.__annotations__
        method.__qualname__, method.__doc__ = original.__qualname__, original.__doc__
        methods[name] = method
    result = Prepared(MappingProxyType(methods))
    check_prepared(result)
    return result


def check_prepared(value):
    originals()
    require(
        type(value) is Prepared
        and type(value.methods) is MappingProxyType
        and tuple(value.methods) == tuple(name for _, _, name in SPECS),
        "Exact private formatter method set required; supplied records are not authority",
    )
    for (_, _, name), original in zip(SPECS, _ORIGINALS, strict=True):
        method = value.methods[name]
        require(
            type(method) is FunctionType
            and method.__builtins__ is original.__builtins__
            and _builtin_dictionary(method.__globals__) is original.__builtins__,
            "Private formatter cached builtins/namespace mismatch: " + name,
        )
        require(
            type(method) is FunctionType
            and method is not original
            and method.__code__ is original.__code__
            and method.__defaults__ is original.__defaults__
            and method.__kwdefaults__ is original.__kwdefaults__
            and method.__closure__ is original.__closure__
            and method.__annotations__ is original.__annotations__
            and method.__dict__ == {}
            and method.__qualname__ == original.__qualname__
            and method.__module__ == original.__module__
            and method.__doc__ == original.__doc__,
            "Changed private formatter consumer code/signature: " + name,
        )
        require(
            method.__globals__ is not original.__globals__
            and set(method.__globals__) == set(original.__globals__)
            and all(
                child is (check_helper() if key == "tex_val" else original.__globals__[key])
                for key, child in method.__globals__.items()
            ),
            "Private formatter namespace changed beyond tex_val: " + name,
        )
    return value


def describe(value):
    """Closed provenance data; reading it cannot recreate or execute a method."""
    check_prepared(value)
    return dict(
        kind="cells.private_molecule_formatter_prerequisite@1",
        formatter_source_sha256=_FORMATTER_PIN,
        formatter_bytecode_sha256=hashlib.sha256(_FORMATTER_CODE.co_code).hexdigest(),
        consumer_source_sha256=PINS.copy(),
        methods=[
            dict(
                name=name,
                module=module.__name__,
                original_class=cls.__qualname__,
                line=original.__code__.co_firstlineno,
                code_sha256=hashlib.sha256(original.__code__.co_code).hexdigest(),
                complete_code_defaults_and_other_globals_retained=True,
                actual_cached_builtin_dictionary_bound=True,
                original_formatter=original.__globals__["tex_val"].__module__
                + "."
                + original.__globals__["tex_val"].__name__,
                private_formatter=source.tex_val.__module__ + ".tex_val",
            )
            for (module, cls, name), original in zip(SPECS, _ORIGINALS, strict=True)
        ],
        prepared_function_objects=len(value.methods),
        warm_calls=0,
        helper_evaluated_by_preparation=False,
        installed=False,
        actual_source_formatter_aliases_installed=True,
        native_owner_or_INIT_admission=False,
    )
