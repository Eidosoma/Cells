"""Fresh imported beartype provenance for original molecule/channel methods.

The observer runs around the EXISTING native import operation. It never calls
a decorator, code generator, wrapper, constructor or native method itself.
Already imported native targets cannot acquire retrospective issuance.
"""

import builtins
import hashlib
import importlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_dynamics_prelude as typed
from cells.processes import betse_native_init_molecule_channels_source as channels
from cells.processes import betse_native_init_molecule_network_source as network

RELEASE = "CELLS_NATIVE_INIT_MOLECULE_WRAPPER_RELEASED"
LAW = "fresh_original_molecule_channel_imported_beartype_factory@1"
ROOTS = (
    Path("/mnt/workspaces/Cells/beartype-overlay-0.22.9-20261031-01"),
    Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages"),
)
LIBRARIES = {
    # Source paths and exact library bytes are intentionally kept together.
    # ruff: noqa: E501
    "beartype._decor._nontype.decornontype": "7dcb3fa458601f813aded9551c86f6db5d45aa5c5181a6925d2f2a343d7ff3c9",
    "beartype._decor._nontype._wrap.wrapmain": "3fc2f8162accefcbb75192503450c0d8120719a1bf653215ee6ee86540b82a6f",
    "beartype._util.func.utilfuncmake": "9190bbf6126b820b4e4259bd130dc5406c2b5ee0e17942ad7ac359822e6f776f",
    "beartype._check.metadata.metacheck": "029a5dab742c77b1a3cc44fd75751a35cb5664913bc5499374de6abc1e74e558",
    "beartype._conf.confmain": "4fbe9f5482c9f82b98737e91c3b4b6d3e338342906863d4bfcad8d98eb0ddf22",
    "beartype.claw._importlib._clawimpload": "6279c7a280ce26e884d0c5db3e965380048ad21fd2dcc9b9ca6e871dd9fa2cae",
}
MAX_FACTORIES = 512
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
_ISSUED = WeakKeyDictionary()


class WrapperAuthorityRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


@dataclass(frozen=True, slots=True)
class ImportEvidence:
    law: str
    source_completed: bool
    factories: int
    generated: int
    raw_returns: tuple
    source_errors: tuple


def source_plan():
    return dict(
        law=LAW,
        release=RELEASE,
        libraries=LIBRARIES,
        native_sources={**network.PINS, **channels.PINS},
        observe_existing_import_order_not_preload_or_redecorate=True,
        required_window=(
            "Before first native target module import, through successful import completion"
        ),
        original_factory_generator_or_wrapper_invoked_by_observer=False,
        retrospective_or_decoded_or_supplied_wrapper_authority=False,
        no_Parameters_phase_material_or_scientific_admission=True,
    )


def _items(value):
    if value is None:
        return None
    if type(value) is not dict:
        raise ValueError("Actual function dictionary required")
    return tuple(value.items())


def _function_state(function):
    if type(function) is not FunctionType:
        raise ValueError("Actual Python source function required")
    namespace, cached = function.__globals__, function.__builtins__
    provider = namespace.get("__builtins__")
    resolved = vars(provider) if type(provider) is ModuleType else provider
    if cached is not vars(builtins) or resolved is not cached:
        raise ValueError("Actual cached builtin/namespace dictionary required")
    values = [
        function,
        function.__code__,
        namespace,
        cached,
        function.__defaults__,
        function.__kwdefaults__,
    ]
    values.extend(function.__defaults__ or ())
    for key, value in _items(function.__kwdefaults__) or ():
        values.extend((key, value))
    for cell in function.__closure__ or ():
        values.extend((cell, cell.cell_contents))
    for name in function.__code__.co_names:
        if name in namespace:
            value = namespace[name]
            if (
                name in cached
                and value is not cached[name]
                and name not in ("__name__", "__doc__", "__package__", "__loader__", "__spec__")
            ):
                raise ValueError("Source builtin lookup shadowed: " + name)
            values.extend((name, value))
        elif name in cached:
            values.extend((name, cached[name]))
    return tuple(values)


def _wrapper_state(function, backend):
    values = list(_function_state(function))
    values.append(function.__annotations__)
    for key, value in _items(function.__annotations__):
        values.extend((key, value))
    for key, value in vars(function).items():
        values.extend((key, value))
    defaults = function.__kwdefaults__ or {}
    for value in defaults.values():
        if type(value) is FunctionType and value is not defaults.get("__beartype_func"):
            values.extend(_function_state(value))
    for name, cls in (
        ("__beartype_check_meta", backend.metadata),
        ("__beartype_conf", backend.configuration),
    ):
        value = defaults.get(name)
        if value is None:
            continue
        if type(value) is not cls:
            raise ValueError("Original wrapper metadata/configuration type changed")
        values.append(value)
        for slot in cls.__slots__:
            if slot == "__weakref__":
                continue
            item = object.__getattribute__(value, slot)
            values.extend((slot, item))
            if type(item) is dict:
                for key, member in item.items():
                    values.extend((key, member))
            if type(item) is backend.configuration:
                for conf_slot in backend.configuration.__slots__:
                    if conf_slot != "__weakref__":
                        values.extend((conf_slot, object.__getattribute__(item, conf_slot)))
    return tuple(values)


def _original_header(function):
    """A module may gain later globals while importing; its method may not change."""
    provider = function.__globals__.get("__builtins__")
    resolved = vars(provider) if type(provider) is ModuleType else provider
    if resolved is not function.__builtins__ or resolved is not vars(builtins):
        raise ValueError("Original cached builtin/namespace dictionary changed")
    result = [
        function,
        function.__code__,
        function.__globals__,
        function.__builtins__,
        function.__defaults__,
        function.__kwdefaults__,
    ]
    result.extend(function.__defaults__ or ())
    for key, value in _items(function.__kwdefaults__) or ():
        result.extend((key, value))
    for cell in function.__closure__ or ():
        result.extend((cell, cell.cell_contents))
    return tuple(result)


def _same(current, original):
    if len(current) != len(original) or any(
        a is not b for a, b in zip(current, original, strict=True)
    ):
        raise ValueError("Actual source/closure/default/builtin binding changed")


def _library_code(path, role, name):
    full = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    if role is not None:
        full = next(
            item for item in full.co_consts if type(item) is CodeType and item.co_name == role
        )
    return next(item for item in full.co_consts if type(item) is CodeType and item.co_name == name)


def _backend():
    """Lazy genuine imports; only the explicitly released observer enters here."""
    modules = {}
    for name, pin in LIBRARIES.items():
        module = importlib.import_module(name)
        path = Path(module.__file__)
        relative = Path(name.replace(".", "/") + ".py")
        if path.is_symlink() or not any(path.resolve() == root / relative for root in ROOTS):
            raise ValueError("Original retained beartype source origin required")
        if hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Pinned original beartype library required")
        modules[name] = module
    decorator = modules["beartype._decor._nontype.decornontype"]
    maker = modules["beartype._util.func.utilfuncmake"]
    generator = modules["beartype._decor._nontype._wrap.wrapmain"]
    functions = dict(
        decorator=decorator.beartype_func,
        generate=generator.generate_code,
        make=maker.make_func,
        loader=modules["beartype.claw._importlib._clawimpload"].BeartypeSourceFileLoader.get_code,
    )
    if (
        decorator.generate_code is not functions["generate"]
        or decorator.make_func is not functions["make"]
    ):
        raise ValueError("Actual imported decorator/generator/maker aliases required")
    for role, fn in functions.items():
        module = sys.modules[fn.__module__]
        path = Path(module.__file__)
        if fn.__globals__ is not vars(module) or typed._constant(fn.__code__) != typed._constant(
            _library_code(
                path, "BeartypeSourceFileLoader" if role == "loader" else None, fn.__name__
            )
        ):
            raise ValueError("Exact original beartype function body required: " + role)
        _function_state(fn)
    return SimpleNamespace(
        modules=modules,
        functions=functions,
        states=tuple((fn, _function_state(fn)) for fn in functions.values()),
        metadata=modules["beartype._check.metadata.metacheck"].BeartypeCheckMeta,
        configuration=modules["beartype._conf.confmain"].BeartypeConf,
        loader_type=modules["beartype.claw._importlib._clawimpload"].BeartypeSourceFileLoader,
    )


def _target(function, frame):
    if type(function) is not FunctionType:
        return None
    pieces = function.__qualname__.split(".")
    key = (None, pieces[0]) if len(pieces) == 1 else tuple(pieces)
    sites = {**network.SITES, **channels.SITES}
    if key not in sites:
        return None
    relative = sites[key]
    module_name = relative[:-3].replace("/", ".")
    module = sys.modules.get(module_name)
    path = network.NATIVE / relative
    if (
        type(module) is not ModuleType
        or function.__globals__ is not vars(module)
        or function.__code__.co_filename != str(path)
    ):
        return None
    compiler = channels if key in channels.SITES else network
    if typed._constant(function.__code__) != typed._constant(compiler.code(*key)):
        raise ValueError("Actual original native method code required")
    spec = vars(module).get("__spec__")
    if spec is None or spec.name != module_name or spec._initializing is not True:
        raise ValueError("Fresh original import frame required; retrospective decoration refused")
    ancestor = frame.f_back
    while ancestor is not None and not (
        ancestor.f_code.co_name == "<module>"
        and ancestor.f_globals is vars(module)
        and ancestor.f_code.co_filename == str(path)
    ):
        ancestor = ancestor.f_back
    if ancestor is None:
        raise ValueError("Actual native module-execution ancestry required")
    return key, module, ancestor


def _import_ancestry(context, target):
    _, module, ancestor = target
    origin = context.loaded_codes.get(module.__name__)
    if (
        origin is None
        or origin.output is not ancestor.f_code
        or vars(module)["__spec__"].loader is not origin.loader
        or not origin.returned
        or origin.primary is not None
    ):
        raise ValueError("Actual observed native loader/code/module ancestry required")


def _record_function(row, backend):
    function, original = row.output, row.original
    _same(_original_header(original), row.original_header)
    if function is original:
        if row.generated != "" or row.make is not None:
            raise ValueError("Only actual observed no-code decoration may return original function")
        return _wrapper_state(function, backend)
    if type(function) is not FunctionType or row.make is None:
        raise ValueError("Actual observed make_func return required")
    made = row.make
    if (
        made.output is not function
        or made.primary is not None
        or made.original is not original
        or made.text is not row.generated
        or vars(function).get("__wrapped__") is not original
        or vars(function).get("__beartype_wrapper") is not True
        or function.__globals__ is not made.globals
        or function.__code__
        is not next(
            code
            for code in made.compiled.co_consts
            if type(code) is CodeType and code.co_name == made.name
        )
        or type(function.__kwdefaults__) is not dict
        or any(function.__kwdefaults__.get(name) is not value for name, value in made.scope)
        or function.__kwdefaults__.get("__beartype_func") is not original
        or function.__annotations__ is not original.__annotations__
    ):
        raise ValueError("Original wrapper/code/scope/delegate return association changed")
    probe = compile(row.generated.strip(), made.filename, "exec", dont_inherit=True)
    if typed._constant(probe) != typed._constant(made.compiled):
        raise ValueError("Actual generated executable constants differ from observed source")
    meta = function.__kwdefaults__.get("__beartype_check_meta")
    if (
        type(meta) is not backend.metadata
        or object.__getattribute__(meta, "func") is not original
        or object.__getattribute__(meta, "conf") is not row.conf
        or object.__getattribute__(meta, "cls_stack") is not row.stack
        or object.__getattribute__(meta, "func_annotations") is not original.__annotations__
    ):
        raise ValueError(
            "Original check-time function/configuration/class/annotation edges changed"
        )
    return _wrapper_state(function, backend)


def _observe(context, frame, event, value):
    """Only canonical monitored events arrive here; no factory/body is called."""
    role = context.codes.get(frame.f_code)
    if role is None:
        return
    if event == "start":
        if context.capture_error is not None:
            raise WrapperAuthorityRejected(
                "Incomplete factory capture prevents more work", stage="capture", partial=context
            )
        for function, expected in context.backend.states:
            _same(_function_state(function), expected)
        if role == "loader":
            name = frame.f_locals.get("fullname")
            relative = name.replace(".", "/") + ".py" if type(name) is str else None
            if relative not in {**network.PINS, **channels.PINS}:
                return
            loader = frame.f_locals.get("self")
            if (
                type(loader) is not context.backend.loader_type
                or loader.name != name
                or Path(loader.path).resolve() != network.NATIVE / relative
                or name in context.loaded_codes
            ):
                raise ValueError("Fresh actual native source loader required")
            row = SimpleNamespace(
                loader=loader, name=name, output=None, primary=None, returned=False
            )
            context.loaded_codes[name] = row
            context.frames[id(frame)] = (frame, role, row)
        elif role == "decorator":
            original = frame.f_locals["func"]
            target = _target(original, frame)
            if target is None:
                return
            _import_ancestry(context, target)
            if len(context.rows) >= MAX_FACTORIES:
                raise ValueError("Bounded native factory observation exhausted")
            key, module, ancestor = target
            kwargs = frame.f_locals["kwargs"]
            stack = kwargs.get("cls_stack")
            if key[0] is not None and (
                type(stack) is not tuple
                or len(stack) != 1
                or vars(stack[0]).get(key[1]) is not original
            ):
                raise ValueError("Actual original class/undecorated method association required")
            row = SimpleNamespace(
                frame=frame,
                original=original,
                target=target,
                stack=stack,
                conf=frame.f_locals["conf"],
                module=module,
                ancestor=ancestor,
                generated=None,
                generate_frame=None,
                make=None,
                output=None,
                returned=False,
                primary=None,
                bindings=None,
                original_header=_original_header(original),
                original_bindings=None,
            )
            context.rows.append(row)
            context.frames[id(frame)] = (frame, role, row)
        else:
            parent = context.frames.get(id(frame.f_back))
            if parent is None or parent[0] is not frame.f_back or parent[1] != "decorator":
                return
            row = parent[2]
            if role == "generate":
                if row.generate_frame is not None:
                    raise ValueError("Duplicate original generator entry")
                row.generate_frame = frame
            else:
                if row.make is not None or frame.f_locals["func_wrapped"] is not row.original:
                    raise ValueError("Original once-only wrapper maker/delegate required")
                scope = frame.f_locals["func_locals"]
                if type(scope) is not dict or frame.f_locals["func_code"] is not row.generated:
                    raise ValueError("Actual generated text and scope association required")
                row.make = SimpleNamespace(
                    frame=frame,
                    original=row.original,
                    text=row.generated,
                    name=frame.f_locals["func_name"],
                    scope=tuple(scope.items()),
                    output=None,
                    primary=None,
                    globals=None,
                    compiled=None,
                    filename=None,
                )
            context.frames[id(frame)] = (frame, role, row)
        return
    found = context.frames.get(id(frame))
    if found is None or found[0] is not frame:
        return
    row = found[2]
    context.last_raw = (frame, event, value)
    if event == "unwind":
        context.source_errors.append(context.last_raw)
        if role == "make":
            row.make.primary = value
        else:
            row.primary = value
        return
    context.raw_returns.append(context.last_raw)
    if role == "loader":
        row.output, row.returned = value, True
        if type(value) is not CodeType:
            raise ValueError("Actual native imported module code required")
    elif role == "generate":
        row.generated = value
    elif role == "make":
        made = row.make
        made.output = value
        made.globals = frame.f_locals.get("func_globals")
        made.compiled = frame.f_locals.get("func_code_compiled")
        made.filename = frame.f_locals.get("func_filename")
    else:
        row.output, row.returned = value, True
        # No pooled decor_meta fields survive as authority. Capture final
        # defaults/metadata now, before that pooled object can be reused.
        row.bindings = _record_function(row, context.backend)


def _binding(row, backend):
    _same(_record_function(row, backend), row.bindings)
    if type(row.original_bindings) is not tuple or not row.original_bindings:
        raise ValueError("Complete post-import native method binding required")
    _same(_wrapper_state(row.original, backend), row.original_bindings)
    role, name = row.target[0]
    owner = row.module if role is None else row.stack[0]
    if role is not None and vars(row.module).get(role) is not owner:
        raise ValueError("Actual native module/class publication changed")
    if vars(owner).get(name) is not row.output:
        raise ValueError("Actual imported owner/export method changed")
    return row.original


@contextmanager
def observing_native_imports(*, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1" or not __debug__:
        raise WrapperAuthorityRejected("Actual wrapper/import work remains held", stage="release")
    with _LOCK:
        if _ACTIVE:
            raise WrapperAuthorityRejected(
                "Exclusive fresh import observer required", stage="reentry"
            )
        targets = {
            relative[:-3].replace("/", ".") for relative in {**network.PINS, **channels.PINS}
        }
        if any(name in sys.modules for name in targets):
            raise WrapperAuthorityRejected(
                "Native targets already imported; cannot issue retrospectively", stage="fresh"
            )
        backend = _backend()
        before = sys.getprofile(), sys.gettrace()
        monitor = sys.monitoring
        original = tuple((monitor.get_tool(i), monitor.get_events(i)) for i in range(6))
        slots = [i for i, (name, _) in enumerate(original) if name is None]
        if not slots:
            raise WrapperAuthorityRejected(
                "Independent monitoring slot unavailable", stage="monitor"
            )
        tool = slots[-1]
        context = SimpleNamespace(
            backend=backend,
            codes={fn.__code__: name for name, fn in backend.functions.items()},
            rows=[],
            loaded_codes={},
            frames={},
            raw_returns=[],
            source_errors=[],
            last_raw=None,
            capture_error=None,
            capture_errors=[],
            primary=None,
            record=None,
            published=False,
            hook_losses=[],
            thread=get_ident(),
            active=True,
            tool=tool,
            original_hooks=before,
        )
        _ACTIVE.append(context)

        def report(event, code, offset, value=None):
            if code not in context.codes:
                return
            frame = sys._getframe(2)
            try:
                if frame.f_code is not code:
                    raise ValueError("Actual monitored factory frame required")
                if sys.getprofile() is not before[0] or sys.gettrace() is not before[1]:
                    context.hook_losses.append((event, frame))
                    raise ValueError("Inherited import guards changed during factory work")
                _observe(context, frame, event, value)
            except BaseException as error:
                if event == "start":
                    raise
                if context.capture_error is None:
                    context.capture_error = error
                context.capture_errors.append((event, error, frame, value))

        def start(code, offset):
            report("start", code, offset)

        def returned(code, offset, value):
            report("return", code, offset, value)

        def unwound(code, offset, value):
            report("unwind", code, offset, value)

        reserved, primary, cleanup = False, None, []
        try:
            monitor.use_tool_id(tool, "Cells original molecule wrapper import")
            reserved = True
            for event, callback in (
                (monitor.events.PY_START, start),
                (monitor.events.PY_RETURN, returned),
                (monitor.events.PY_UNWIND, unwound),
            ):
                monitor.register_callback(tool, event, callback)
            monitor.set_events(
                tool, monitor.events.PY_START | monitor.events.PY_RETURN | monitor.events.PY_UNWIND
            )
            yield context
            if (
                not context.rows
                or context.capture_error is not None
                or context.hook_losses
                or any(not row.returned or row.primary is not None for row in context.rows)
            ):
                raise WrapperAuthorityRejected(
                    "Complete original import/factory capture required",
                    stage="capture",
                    partial=context,
                )
            for row in context.rows:
                # Later declarations in the actual native module are now
                # complete. Preserve their real resolutions, not an early
                # incomplete import snapshot or a supplied namespace.
                row.original_bindings = _wrapper_state(row.original, backend)
                _binding(row, backend)
            context.record = ImportEvidence(
                LAW,
                True,
                len(context.rows),
                sum(row.make is not None for row in context.rows),
                tuple(context.raw_returns),
                tuple(context.source_errors),
            )
        except BaseException as error:
            primary, context.primary = error, error
            try:
                _FAILED.append(context)
            except BaseException as secondary:
                context.retention_error = (secondary, error)
            raise
        finally:
            if reserved:
                for operation, args in (
                    (monitor.set_events, (tool, 0)),
                    (monitor.register_callback, (tool, monitor.events.PY_START, None)),
                    (monitor.register_callback, (tool, monitor.events.PY_RETURN, None)),
                    (monitor.register_callback, (tool, monitor.events.PY_UNWIND, None)),
                    (monitor.free_tool_id, (tool,)),
                ):
                    try:
                        operation(*args)
                    except BaseException as error:
                        cleanup.append((operation.__name__, error))
            for getter, setter, prior in (
                (sys.getprofile, sys.setprofile, before[0]),
                (sys.gettrace, sys.settrace, before[1]),
            ):
                if getter() is not prior:
                    context.hook_losses.append(("cleanup", getter.__name__))
                    try:
                        setter(prior)
                    except BaseException as error:
                        cleanup.append(("hook_restore", error))
            context.active = False
            _ACTIVE.pop()
            final = tuple((monitor.get_tool(i), monitor.get_events(i)) for i in range(6))
            context.cleanup = tuple(cleanup)
            context.hooks_restored = sys.getprofile() is before[0] and sys.gettrace() is before[1]
            context.monitor_restored = final == original
            if primary is None and (
                cleanup
                or context.hook_losses
                or not context.hooks_restored
                or not context.monitor_restored
            ):
                context.record = None
                error = WrapperAuthorityRejected(
                    "Import observer cleanup incomplete", stage="cleanup", partial=context
                )
                context.primary = error
                _FAILED.append(context)
                raise error
        try:
            for row in context.rows:
                _ISSUED[row.output] = (context, row)
            context.published = True
        except BaseException as error:
            context.record, context.primary = None, error
            _FAILED.append(context)
            raise


def validate(function, original, *, owner, attribute):
    issued = _ISSUED.get(function) if type(function) is FunctionType else None
    if issued is None:
        raise WrapperAuthorityRejected(
            "Actual observed imported wrapper required", stage="unissued"
        )
    context, row = issued
    expected_owner = row.module if row.target[0][0] is None else row.stack[0]
    if (
        context.active
        or not context.published
        or context.record is None
        or context.primary is not None
        or context.thread != get_ident()
        or row.original is not original
        or owner is not expected_owner
        or attribute != row.target[0][1]
        or not context.hooks_restored
        or not context.monitor_restored
    ):
        raise WrapperAuthorityRejected(
            "Original closed imported wrapper association changed", stage="association"
        )
    for fn, expected in context.backend.states:
        _same(_function_state(fn), expected)
    return _binding(row, context.backend)
