"""Original same-parameter seven subconfiguration loads; numeric stores closed.

The eight top-level objects must already belong to the original constructor.
Only native YamlList.load may create fresh per-row wrappers in this epoch.
"""

import ast
import hashlib
import io
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_paths as paths

LAW_ID = paths.SUBCONFIGURATION_LAW
PATHS_SHA256 = "4c3fc0f0c195440fe0e200975b3093b605ad06094b94e582c0bba7374e549d79"
RELEASE = "CELLS_NATIVE_PARAMETER_SUBCONFIGURATIONS_RELEASED"
MAX_NEW_WRAPPERS = 4096
ORDER = ("cut_profiles", "tissue_default", "tissue_profiles", "anim", "csv", "plot", "visual")
ROOT_TYPES = {
    "cut_profiles": ("YamlList", "SimConfCutListItem"),
    "tissue_default": ("SimConfTissueDefault", None),
    "tissue_profiles": ("YamlList", "SimConfTissueListItem"),
    "anim": ("SimConfExportAnims", None),
    "csv": ("SimConfExportCSVs", None),
    "plot": ("SimConfExportPlots", None),
    "visual": ("SimConfExportVisual", None),
    "grn": ("SimConfGrnFile", None),
    "anim.anim_while_sim": ("SimConfExportAnimCellsEmbedded", None),
    "anim.anims_after_sim": ("YamlList", "SimConfExportAnimCells"),
    "csv.csvs_after_sim": ("YamlList", "SimConfExportCSV"),
    "plot.plots_cell_after_sim": ("YamlList", "SimConfExportPlotCell"),
    "plot.plots_cells_after_sim": ("YamlList", "SimConfExportPlotCells"),
}
MODULES = {
    "YamlList": "betse.lib.yaml.abc.yamllistabc",
    "SimConfCutListItem": "betse.science.config.model.conftis",
    "SimConfTissueDefault": "betse.science.config.model.conftis",
    "SimConfTissueListItem": "betse.science.config.model.conftis",
    "SimConfExportAnims": "betse.science.config.export.visual.confexpvisanim",
    "SimConfExportAnimCells": "betse.science.config.export.visual.confexpvisanim",
    "SimConfExportAnimCellsEmbedded": "betse.science.config.export.visual.confexpvisanim",
    "SimConfExportCSVs": "betse.science.config.export.confexpcsv",
    "SimConfExportCSV": "betse.science.config.export.confexpcsv",
    "SimConfExportPlots": "betse.science.config.export.visual.confexpvisplot",
    "SimConfExportPlotCell": "betse.science.config.export.visual.confexpvisplot",
    "SimConfExportPlotCells": "betse.science.config.export.visual.confexpvisplot",
    "SimConfExportVisual": "betse.science.config.export.visual.confexpvisual",
    "SimConfGrnFile": "betse.science.config.grn.confgrn",
}
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_LOCK, _ACTIVE = RLock(), []


class SubconfigurationsRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        partial=None,
        trial=None,
        source_error=None,
        capture_errors=(),
    ):
        super().__init__(reason)
        self.stage, self.request, self.partial, self.trial = stage, request, partial, trial
        self.source_error, self.capture_errors = source_error, tuple(capture_errors)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parent: paths.PathsOwner
    before_trial_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live subconfiguration requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    before_trial_identity: str
    cache: object
    work: tuple
    attempted: tuple
    completed: tuple
    constructions: tuple
    identity: str


def _digest(value):
    return paths._digest(value)


def source_plan():
    if hashlib.sha256(Path(paths.__file__).read_bytes()).hexdigest() != PATHS_SHA256:
        raise ValueError("Explicit retained path producer required")
    parent = paths.source_plan()
    native = paths.prefix.parameters.inherited.tissue.aliases.NATIVE
    cls = paths.prefix.parameters.inherited._class(
        ast.parse((native / paths.prefix.parameters.PARAMETERS).read_bytes()), "Parameters"
    )
    load = paths.prefix.parameters.inherited._method(cls, "load")
    selected = load.body[5:12]
    if tuple(node.value.func.value.attr for node in selected) != ORDER:
        raise ValueError("Original subconfiguration load order changed")
    # Reuse the Specialist literal source correspondence, never its supplied p.
    specialist = paths.prefix.parameters.inherited.tissue
    specialist._verify_sources()
    tree = ast.parse(Path(specialist.source.__file__).read_bytes())
    node = paths.prefix.parameters.inherited._class(tree, "ParameterSubconfigurations")
    own = paths.prefix.parameters.inherited._method(node, "load")
    if ast.dump(ast.Module(body=selected[:3], type_ignores=[])) != ast.dump(
        ast.Module(body=own.body, type_ignores=[])
    ):
        raise ValueError("Existing Specialist first-three load correspondence changed")
    return dict(
        law=LAW_ID,
        native_pins=parent["native_pins"],
        paths_producer=PATHS_SHA256,
        load_order=ORDER,
        load_lines=(selected[0].lineno, selected[-1].end_lineno),
        next_source_line=load.body[12].lineno,
        original_roster=tuple(ROOT_TYPES),
        max_new_wrappers=MAX_NEW_WRAPPERS,
        specialist_source=hashlib.sha256(Path(specialist.source.__file__).read_bytes()).hexdigest(),
        actual_numeric_Parameters_tissue_handler_phase_INIT_admitted=False,
    )


def _member(p, name):
    value = p
    for part in name.split("."):
        value = vars(value)[part]
    return value


def _canonical(parent):
    birth = parent.parent
    native = paths.prefix.parameters.inherited.tissue.aliases.NATIVE
    frame = birth.locals.get(
        (str(native / paths.prefix.parameters.PARAMETERS), "Parameters.__init__")
    )
    if (
        type(frame) is not dict
        or frame.get("self") is not parent.p
        or frame.get("__class__") is not birth.source.cls
        or type(frame.get("args")) is not tuple
        or frame["args"]
        or type(frame.get("kwargs")) is not dict
        or frame["kwargs"]
        or not birth.source_completed
        or not birth.trial.source_completed
    ):
        raise SubconfigurationsRejected(
            "Actual original same-p constructor authority absent", stage="constructor_authority"
        )
    paths.prefix.parameters.inherited.tissue.aliases._check_modules()
    classes = {}
    for name, module_name in MODULES.items():
        module = sys.modules.get(module_name)
        if module is None:
            raise ValueError("Original subconfiguration class module absent")
        classes[name] = getattr(module, name)
        if name.startswith("SimConfExport") and name in frame and frame[name] is not classes[name]:
            raise ValueError("Retained actual export constructor import changed")
    for name in (
        "SimConfExportAnims",
        "SimConfExportCSVs",
        "SimConfExportPlots",
        "SimConfExportVisual",
        "SimConfGrnFile",
    ):
        if frame.get(name) is not classes[name]:
            raise ValueError("Retained actual constructor imports incomplete")
    objects = {}
    for name, (class_name, item_name) in ROOT_TYPES.items():
        value = _member(parent.p, name)
        expected = classes[class_name]
        if type(value) is not expected or vars(value).get("_conf", "missing") is not None:
            raise ValueError("Original unloaded wrapper type/config changed: " + name)
        if item_name is not None and (
            vars(value).get("_item_type") is not classes[item_name]
            or vars(value).get("_confs_wrap", "missing") is not None
        ):
            raise ValueError("Original unloaded list item factory/storage changed: " + name)
        candidates = {
            id(obj): obj
            for obj in birth.graph[0]
            if type(obj) is expected
            and (item_name is None or vars(obj).get("_item_type") is classes[item_name])
        }
        if len(candidates) != 1 or candidates.get(id(value)) is not value:
            raise ValueError(
                "Wrapper does not have unique retained native birth association: " + name
            )
        objects[name] = value
    return SimpleNamespace(classes=classes, objects=objects)


def _native_bindings(context):
    refs = []
    labels = []
    native = paths.prefix.parameters.inherited.tissue.aliases.NATIVE
    for name, cls in sorted(context.authority.classes.items()):
        refs.extend((cls, *paths.prefix.parameters.inherited.tissue._surface(cls)))
        for method in ("__init__", "load", "make_list"):
            fn = getattr(cls, method, None)
            if fn is None:
                continue
            if type(fn) is MethodType:
                fn = fn.__func__
            chain = paths.prefix.parameters.inherited._chain(fn)
            original = chain[-1]
            filename = Path(original.__code__.co_filename)
            if not filename.is_relative_to(native):
                raise ValueError("Foreign native wrapper executable")
            tree = ast.parse(filename.read_bytes())
            owner = original.__qualname__.split(".")[0]
            node = paths.prefix.parameters.inherited._class(tree, owner)
            expected = paths.prefix.parameters._method_code(node, original.__name__, str(filename))
            if paths.prefix.parameters.inherited._code(
                original.__code__
            ) != paths.prefix.parameters.inherited._code(expected):
                raise ValueError("Original native wrapper body/header changed")
            for part in chain:
                label, atoms = paths.prefix._function_bindings(part)
                labels.append((name, method, label))
                refs.extend(atoms)
    return tuple(labels), tuple(refs)


def request_record(value):
    return dict(
        law=LAW_ID,
        before=value.before_trial_identity,
        source=value.source_identity,
        same_parameter=True,
    )


def from_paths(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise SubconfigurationsRejected("Explicit subconfiguration law required", stage="law")
    plan = source_plan()
    parent = paths._validate(owner)
    authority = _canonical(parent)
    value = Request(owner, parent.trial.identity, _digest(plan), "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (parent, parent.p, parent.config, parent.trial, parent.graph, authority)
    return value


def _target(config, name):
    if name == "cut_profiles":
        return config["tissue profile definition"]["cut profiles"]
    if name == "tissue_default":
        return config["tissue profile definition"]["tissue"]["default"]
    if name == "tissue_profiles":
        return config["tissue profile definition"]["tissue"]["profiles"]
    return config


def _lists(context):
    cfg = context.config
    results = cfg["results options"]
    return (
        ("cut_profiles", cfg["tissue profile definition"]["cut profiles"]),
        ("tissue_profiles", cfg["tissue profile definition"]["tissue"]["profiles"]),
        ("anim.anims_after_sim", results["after solving"]["animations"]["pipeline"]),
        ("csv.csvs_after_sim", results["after solving"]["csvs"]["pipeline"]),
        ("plot.plots_cell_after_sim", results["after solving"]["plots"]["single cell pipeline"]),
        ("plot.plots_cells_after_sim", results["after solving"]["plots"]["cell cluster pipeline"]),
    )


def _stable(context):
    if tuple(vars(context.p)) != context.before_names:
        raise ValueError("Subconfiguration load changed parameter field layout")
    return paths.prefix.graphs.capture(
        {name: vars(context.p)[name] for name in context.stable_names},
        yaml_base=context.birth.source.yaml,
        runtime_types=context.parent.runtime_types,
    )


def _check(context):
    request = context.request
    old = _REQUESTS.get(request)
    if (
        context.invalid
        or context.thread != get_ident()
        or context.guard.invalid
        or context.guard.active is not context.active
        or _CONSUMED.get(request) is not context
        or _CLAIMED.get(request.parent) is not context
        or old is None
        or _digest(request_record(request)) != request.identity
    ):
        raise ValueError("Original one-shot subconfiguration epoch changed")
    if (
        context.parent is not old[0]
        or context.p is not old[1]
        or context.config is not old[2]
        or context.parent.trial is not old[3]
        or context.parent.graph is not old[4]
        or not context.parent.invalid
        or context.parent.active
        or context.p._conf is not context.config
        or vars(context.p).get("config") is not context.config
        or type(context.p) is not context.birth.source.cls
    ):
        raise ValueError("Original same-p/config/path epoch changed")
    for name, value in context.authority.objects.items():
        if _member(context.p, name) is not value:
            raise ValueError("Retained wrapper replaced: " + name)
        kind, item = ROOT_TYPES[name]
        if type(value) is not context.authority.classes[kind]:
            raise ValueError("Retained native wrapper class changed: " + name)
        if (
            item is not None
            and vars(value).get("_item_type") is not context.authority.classes[item]
        ):
            raise ValueError("Retained native item factory changed: " + name)
    paths.prefix.parameters.inherited._same(_bindings(), context.bindings)
    paths.prefix.parameters.inherited._same(paths._bindings(), context.parent.bindings)
    paths.prefix.parameters.inherited._same(_native_bindings(context), context.native_bindings)
    paths.prefix.parameters.inherited._same(
        paths.prefix.parameters._runtime(context.birth.source), context.birth.runtime
    )
    paths.prefix.parameters.inherited._same_graph(_stable(context), context.stable)
    paths._computed(context.parent)
    paths.prefix._verify_file(context.parent.yaml.request.file)
    if _digest(source_plan()) != request.source_identity:
        raise ValueError("Subconfiguration producer changed")


def _loaded(context):
    for name in ORDER:
        if vars(context.authority.objects[name]).get("_conf") is not _target(context.config, name):
            raise ValueError("Native wrapper/config target association changed: " + name)
    if (
        vars(context.authority.objects["anim.anim_while_sim"]).get("_conf")
        is not context.config["results options"]["while solving"]["animations"]
    ):
        raise ValueError("Native embedded animation association changed")
    fresh = []
    for name, conf in _lists(context):
        wrapper = context.authority.objects[name]
        rows = vars(wrapper).get("_confs_wrap")
        item = context.authority.classes[ROOT_TYPES[name][1]]
        if (
            vars(wrapper).get("_conf") is not conf
            or vars(wrapper).get("_item_type") is not item
            or type(rows) is not list
            or len(rows) != len(conf)
        ):
            raise ValueError("Native list config/factory/length changed: " + name)
        for row, raw in zip(rows, conf, strict=True):
            if (
                type(row) is not item
                or vars(row).get("_conf") is not raw
                or any(row is before for before in context.before_objects)
                or not any(row is obj for obj in context.constructed)
                or any(row is obj for obj in fresh)
            ):
                raise ValueError(
                    "Row wrapper is omitted/foreign/reused or not freshly constructed: " + name
                )
            fresh.append(row)
    if len(fresh) != len(context.constructed) or len(fresh) > MAX_NEW_WRAPPERS:
        raise ValueError("Unbound extra or excessive native row construction")
    if any(
        row is not constructed for row, constructed in zip(fresh, context.constructed, strict=True)
    ):
        raise ValueError("Native row wrapper construction order changed")
    return fresh


@contextmanager
def _observe(context):
    with paths.prefix.parameters._observe(context):
        previous, trace = sys.getprofile(), sys.gettrace()
        item_types = {
            context.authority.classes[item] for _, item in ROOT_TYPES.values() if item is not None
        }
        wrapper_types = set(context.authority.classes.values()) | {context.birth.source.yaml}
        native_root = str(paths.prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"

        def profile(frame, event, arg):
            if event == "c_call" and getattr(arg, "__name__", None) in {
                "write",
                "writelines",
                "truncate",
            }:
                stream = getattr(arg, "__self__", None)
                if (
                    isinstance(stream, io.IOBase)
                    and stream is not sys.stdout
                    and stream is not sys.stderr
                ):
                    raise ValueError("Subconfiguration file writer refused")
            if previous is not None:
                previous(frame, event, arg)
            obj = frame.f_locals.get("self")
            if event == "call" and frame.f_code.co_name == "__init__" and type(obj) in item_types:
                if not any(obj is value for value in context.constructed):
                    if len(context.constructed) >= MAX_NEW_WRAPPERS:
                        raise ValueError("Native row construction budget exceeded")
                    if any(obj is value for value in context.before_objects):
                        raise ValueError("Native row constructor reused prior owner")
                    context.constructed.append(obj)
            reached = frame.f_code.co_filename.startswith(native_root) or type(obj) in wrapper_types
            if event == "return" and reached and frame.f_code.co_name in {"__init__", "load"}:
                try:
                    context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(
                        frame.f_locals
                    )
                except BaseException as error:
                    paths.prefix.parameters.inherited.tissue.captures._remember_observation_error(
                        context, error, origin="subconfiguration_locals", raw=frame
                    )

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(previous)
            sys.settrace(trace)


def _load(context, name):
    # Receiver and conf evaluation follow the original call-site order.
    wrapper = getattr(context.p, name)
    conf = _target(context.config, name)
    with paths.prefix.parameters.inherited.tissue.aliases.issuing_native_imports(
        paths.prefix.parameters.inherited.tissue.source.SOURCE_PINS
    ):
        return wrapper.load(conf=conf)


def _bindings():
    funcs = (
        source_plan,
        _member,
        _canonical,
        _native_bindings,
        request_record,
        from_paths,
        _target,
        _lists,
        _stable,
        _check,
        _loaded,
        _observe,
        _observe.__wrapped__,
        _load,
        _bindings,
        trial_record,
        _validate,
        prepare,
        require_parameters,
        paths.handoff_subconfigurations,
        paths.handoff_subconfigurations.__wrapped__,
    )
    return (
        (tuple(ROOT_TYPES.items()), tuple(MODULES.items())),
        (
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _LOCK,
            _ACTIVE,
            LAW_ID,
            PATHS_SHA256,
            RELEASE,
            MAX_NEW_WRAPPERS,
            ORDER,
            ROOT_TYPES,
            MODULES,
            *(
                atom
                for fn in funcs
                for atom in paths.prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        before=value.before_trial_identity,
        cache=value.cache.identity,
        work=value.work,
        attempted=value.attempted,
        completed=value.completed,
        constructions=value.constructions,
        full_Parameters_admitted=False,
    )


class SubconfigurationsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use original same-parameter subconfiguration continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live subconfiguration owners cannot be serialized")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not SubconfigurationsOwner or owner not in _ISSUED:
        raise SubconfigurationsRejected(
            "Issued same-parameter subconfiguration owner required", stage="owner"
        )
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced subconfiguration owner")
        # The read-only handoff guard is closed after construction; validation
        # does no native work or writes and checks the retained disposition.
        if context.guard.invalid:
            raise ValueError("Poisoned source handoff")
        _check(context)
        _loaded(context)
        paths.prefix.parameters.inherited._same_graph(
            paths.prefix._capture(context.capture_view), context.graph
        )
        paths.prefix.parameters.inherited._same(
            paths.prefix._class_bindings(context.runtime_types), context.runtime_classes
        )
        kinds, files, namespaces = paths.prefix._runtime_types(context.capture_view)
        if kinds != context.runtime_types or files != context.runtime_files:
            raise ValueError("Subconfiguration runtime inventory changed")
        paths.prefix.parameters.inherited._same(namespaces, context.runtime_namespaces)
        caches = paths.prefix.parameters.inherited.tissue.core.caches
        caches.validate(context.trial.cache)
        if (
            caches.snapshot(context.graph[1]).identity != context.trial.cache.identity
            or _digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Subconfiguration graph/trial changed")
    except BaseException as error:
        context.invalid = True
        raise SubconfigurationsRejected(
            "Stale subconfiguration owner refused",
            stage="owner_drift",
            request=context.request,
            partial=context,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def prepare(request, *, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(paths.RELEASE) != "1"
    ):
        raise SubconfigurationsRejected(
            "Actual native subconfiguration continuation held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise SubconfigurationsRejected(
                "Reentrant subconfiguration load refused", stage="reentrant", request=request
            )
        if (
            type(request) is not Request
            or request not in _REQUESTS
            or _digest(request_record(request)) != request.identity
        ):
            raise SubconfigurationsRejected(
                "Issued exact path owner request required", stage="request", request=request
            )
        if request in _CONSUMED or request.parent in _CLAIMED:
            raise SubconfigurationsRejected(
                "Subconfiguration attempt consumed", stage="consumed", request=request
            )
        context = SimpleNamespace(
            request=request,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="subconfiguration_admission",
            work=[],
            locals={},
            attempted=[],
            completed=[],
            constructed=[],
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
        )
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        _ACTIVE.append(context)
        error = None
        try:
            context.bindings = _bindings()
            parent = paths._validate(request.parent)
            old = _REQUESTS[request]
            if parent is not old[0] or parent.trial is not old[3]:
                raise ValueError("Original path owner epoch changed")
            context.parent = parent
            context.p = parent.p
            context.config = parent.config
            context.birth = parent.parent
            context.authority = _canonical(parent)
            context.native_bindings = _native_bindings(context)
            context.before_objects = tuple(parent.graph[0])
            context.before_names = tuple(vars(context.p))
            context.stable_names = tuple(name for name in context.before_names if name not in ORDER)
            context.stable = _stable(context)
            with paths.handoff_subconfigurations(request.parent, law_id=LAW_ID) as (retired, guard):
                if retired is not parent:
                    raise ValueError("Foreign path handoff")
                context.guard = guard
                _check(context)
                for name in ORDER:
                    context.stage = "native_load_" + name
                    context.attempted.append(name)
                    with _observe(context):
                        _load(context, name)
                    context.completed.append(name)
                    if context.observation_error is not None:
                        break
                    _check(context)
                if context.observation_error is None:
                    _loaded(context)
                    context.stage = "subconfiguration_capture"
                    context.file_record = parent.file_record
                    # Runtime enumeration and graph capture both require the
                    # actual constructor birth, not the intervening path owner.
                    view = SimpleNamespace(
                        p=context.p,
                        parent=context.birth,
                        file_record=context.file_record,
                    )
                    context.capture_view = view
                    context.runtime_types, context.runtime_files, context.runtime_namespaces = (
                        paths.prefix._runtime_types(view)
                    )
                    view.runtime_types = context.runtime_types
                    context.runtime_classes = paths.prefix._class_bindings(context.runtime_types)
                    context.graph = paths.prefix._capture(view)
                    cache = paths.prefix.parameters.inherited.tissue.core.caches.snapshot(
                        context.graph[1]
                    )
                    receipts = tuple(
                        dict(
                            sequence=i,
                            type=type(obj).__module__ + "." + type(obj).__qualname__,
                            scope="fresh native row; not independent case",
                        )
                        for i, obj in enumerate(context.constructed)
                    )
                    trial = Trial(
                        request.identity,
                        parent.trial.identity,
                        cache,
                        tuple(context.work),
                        tuple(context.attempted),
                        tuple(context.completed),
                        receipts,
                        "",
                    )
                    context.trial = replace(trial, identity=_digest(trial_record(trial)))
                    _check(context)
                    paths.prefix.parameters.inherited._same_graph(
                        paths.prefix._capture(view), context.graph
                    )
                    owner = object.__new__(SubconfigurationsOwner)
                    _check(context)
                    context.owner = owner
                    _ISSUED[owner] = context
                    return owner
        except BaseException as primary:
            if context.stage == "subconfiguration_capture":
                paths.prefix.parameters.inherited.tissue.captures._remember_observation_error(
                    context, primary, origin=context.stage, raw=context
                )
            else:
                error = primary
        finally:
            context.active = False
            _ACTIVE.pop()
        context.invalid = True
        refusal = SubconfigurationsRejected(
            "Subconfiguration continuation issued no child",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.observation_errors,
        )
        raise refusal from (error if error is not None else context.observation_error)


def require_parameters(owner):
    context = _validate(owner)
    raise SubconfigurationsRejected(
        "Original general/world/time/ion/material stores and phase remain unavailable",
        stage="numeric_parameter_prerequisites",
        request=context.request,
        trial=context.trial,
        partial=dict(
            next_source_line=source_plan()["next_source_line"],
            full_Parameters_or_phase_or_INIT_admitted=False,
        ),
    )
