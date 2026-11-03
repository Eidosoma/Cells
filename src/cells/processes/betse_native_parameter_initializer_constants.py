"""Original same-p plotting/internal stores before geometric and ion loading.

Only the literal Parameters.load[139:203] source may populate this successor.
Metadata inspection is not permission to execute the source or to issue INIT.
"""

import ast
import copy
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_colormap_load as previous

LAW_ID = "betse_native_parameter_plotting_initializer_constants@1"
PREVIOUS_SHA256 = "cfe5d3baf710f5a7f1b1e53b5f10716c133e3c59c91db8e003a3bd10e3a14004"
RELEASE = "CELLS_NATIVE_PARAMETER_INITIALIZER_CONSTANTS_RELEASED"
START, STOP, MAX_WORK = 139, 203, 20000
_FLOAT = float
prefix, claims = previous.prefix, previous.claims
_LOCK, _ACTIVE = Lock(), []
_ISSUED, _CONSUMED, _CLAIMED = (WeakKeyDictionary() for _ in range(3))
CM_STORES = tuple(row[0] for row in previous.boundary.ROLES)
REMAINDER_HANDOFF_LAW = "betse_native_parameter_original_load_remainder_handoff@1"
_REMAINDER_LOCK, _REMAINDER_ACTIVE = Lock(), []
_REMAINDER_ISSUED, _REMAINDER_CONSUMED, _REMAINDER_CLOSED, _REMAINDER_SEALS = (
    WeakKeyDictionary() for _ in range(4)
)
_REMAINDER_TOKEN = object()


class ConstantsRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None, source_error=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.partial, self.source_error = stage, partial, source_error
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class Trial:
    parent_identity: str
    before_identity: str
    after_identity: str
    source_identity: str
    stores: tuple
    work: tuple
    metadata_work: tuple
    source_completed: bool
    identity: str


class ConstantsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use released prepare from the actual colormap successor")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live original parameter owners cannot be pickled")

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


@dataclass(frozen=True, slots=True)
class RemainderRecord:
    parent_identity: str
    source_identity: str
    scope_identity: str
    before_identity: str
    after_identity: str
    before_names: tuple
    after_names: tuple
    work: tuple
    succeeded: bool
    failure_stage: str
    failure_type: str
    capture_stages: tuple
    identity: str
    parent_verified: bool = False


class RemainderGrant:
    """Opaque one-shot mutation scope, never a complete-load or phase owner."""

    __slots__ = ("__weakref__",)

    def __init__(self, token):
        if token is not _REMAINDER_TOKEN:
            raise TypeError("Use remainder_handoff with the actual ConstantsOwner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live parameter mutation grants cannot be serialized")

    def __enter__(self):
        return _remainder_enter(self)

    def __exit__(self, kind, error, traceback):
        try:
            _remainder_close(self, error)
        except BaseException as secondary:
            if error is None:
                raise
            entry = _REMAINDER_ISSUED.get(self)
            if entry is not None:
                entry[0].invalid = True
                entry[0].capture_errors += (("close_primary_recovery", secondary),)
        return False

    @property
    def parameters(self):
        return self.check()

    def check(self):
        return _remainder_check(self)

    @property
    def record(self):
        context = _remainder_context(self)
        closed = _REMAINDER_CLOSED.get(self)
        if context.active or closed is None or closed[0] is not context:
            raise ConstantsRejected("Remainder grant has no closed record", stage="grant_record")
        return closed[1]  # Failed records are forensic data, never successful authority.

    @property
    def metadata_work(self):
        context = _remainder_context(self)
        return (*context.work, *context.validation_work)


def _digest(value):
    return previous._digest(value)


def _ast():
    path, cls, load, _ = previous.boundary._ast()
    selected = load.body[START:STOP]
    if (
        len(selected) != 64
        or ast.unparse(selected[0]) != "ro = self._conf['results options']"
        or ast.unparse(selected[-1]) != "self.merge_cut_off = 1 / 50"
        or ast.unparse(load.body[STOP]) != "self.d_cell = self.cell_radius * 2"
    ):
        raise ValueError("Original plotting/constants/geometry boundary changed")
    return path, cls, load, selected


def _historical():
    """Keep original parent metadata/returns, replacing only old store extents."""
    path = Path(previous.__file__)
    if hashlib.sha256(path.read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Explicit original four-colormap producer required")
    tree = ast.parse(path.read_bytes())
    functions, descriptions = {}, []
    for name, trim in (("_history", "tail"), ("_outputs", "head")):
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        selected = copy.deepcopy(node)
        if trim == "tail":
            removed = [ast.unparse(n) for n in selected.body[-5:]]
            if (
                removed[:3]
                != [
                    "fields = vars(context.p)",
                    "appended = tuple(fields)[len(context.before_names):]",
                    "expected = tuple((row[0] for row in boundary.ROLES))",
                ]
                or "Old parameter layout or original four-store prefix changed" not in removed[3]
                or "Unowned later parameter stores" not in removed[4]
            ):
                raise ValueError("Original historical field-boundary checks changed")
            selected.body = selected.body[:-5]
        else:
            removed = [ast.unparse(n) for n in selected.body[:2]]
            if (
                removed[0] != "expected = tuple((row[0] for row in boundary.ROLES))"
                or "All four original stores in literal order required" not in removed[1]
            ):
                raise ValueError("Original four-store completion check changed")
            selected.body = selected.body[2:]
        original = vars(previous)[name]
        prefix._function_bindings(original)
        code = previous.boundary._code(selected, str(path), name)
        function = FunctionType(code, original.__globals__, name)
        if function.__builtins__ is not original.__builtins__:
            raise ValueError("Historical function cached builtins changed")
        functions[name] = function
        descriptions.append((name, _digest(ast.dump(selected)), tuple(removed)))
    return functions, tuple(descriptions)


def source_plan():
    _, historical = _historical()
    path, _, load, selected = _ast()
    stores = tuple(n.targets[0].attr for n in selected if isinstance(n.targets[0], ast.Attribute))
    casts = tuple(
        n.lineno
        for statement in selected
        for n in ast.walk(statement)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "float"
    )
    if len(stores) != 62 or len(set(stores)) != 62 or len(casts) != 10:
        raise ValueError("Original constants store/conversion roster changed")
    return dict(
        law=LAW_ID,
        previous_producer=PREVIOUS_SHA256,
        previous=previous.source_plan(),
        source=str(path),
        statement_slice=(START, STOP),
        source_lines=(1017, 1125),
        source_body_ast=_digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
        stores=stores,
        native_float_sites=casts,
        native_float_site_count=10,
        float_work_scope=(
            "Inside the exact source attempt; no independently completed-scalar claim."
        ),
        historical_functions=historical,
        replacement_extent="Entire old p/data/colormap graph plus exact new-store prefix.",
        next_source_line=load.body[STOP].lineno,
        actual_owner_required=True,
        same_parameter=True,
        supplied_configuration=False,
        geometry_ion_profile_phase_Simulator_INIT_admitted=False,
        predecessor_source_acceptance_inferred=False,
    )


def _fields(context, *, complete=False):
    names = tuple(vars(context.p)) if complete else context.before_names
    return prefix.graphs.capture(
        {name: vars(context.p)[name] for name in names if name not in CM_STORES},
        yaml_base=context.parent.parent.birth.source.yaml,
        runtime_types=context.parent.parent.runtime.runtime_types,
    )


def _cm_graph(parent):
    # A capture view carries actual references, never a replacement p/owner.
    view = SimpleNamespace(p=parent.p, bound=parent.bound, kinds=parent.kinds)
    return previous._graph(view)


def _same_cm(actual, saved):
    if (
        actual.identity != saved.identity
        or len(actual.objects) != len(saved.objects)
        or any(a is not b for a, b in zip(actual.objects, saved.objects, strict=True))
        or saved.encoder.arrays is not saved.arrays
        or saved.encoder.nodes is not saved.tree["nodes"]
        or saved.encoder.seal(saved.tree) != saved.identity
    ):
        raise ValueError("Original returned colormap graph/data/aliases changed")


def _plot(context):
    # This actual loaded object is retained by the original GRN ancestry.
    loaded = context.parent.parent.parent.authority.loaded
    subconfigs = previous.mod.subconfigs
    owner = loaded.owner
    if subconfigs._ISSUED.get(owner) is not loaded or loaded.p is not context.p:
        raise ValueError("Original loaded subconfiguration association absent")
    cls = loaded.authority.classes["SimConfExportPlots"]
    plot = loaded.authority.objects["plot"]
    module = sys.modules.get(subconfigs.MODULES["SimConfExportPlots"])
    native = prefix.parameters.inherited.tissue.aliases.NATIVE
    expected_file = native / "betse/science/config/export/visual/confexpvisplot.py"
    birth = loaded.parent.parent
    frame = birth.locals.get((str(native / prefix.parameters.PARAMETERS), "Parameters.__init__"))
    if (
        vars(context.p).get("plot") is not plot
        or type(plot) is not cls
        or vars(plot).get("_conf") is not vars(context.p)["_conf"]
        or module is None
        or vars(module).get("SimConfExportPlots") is not cls
        or Path(vars(module)["__file__"]).resolve() != expected_file
        or type(frame) is not dict
        or frame.get("self") is not context.p
        or frame.get("SimConfExportPlots") is not cls
        or frame.get("__class__") is not birth.source.cls
        or birth.source_completed is not True
        or birth.trial.source_completed is not True
        or not any(value is plot for value in birth.graph[0])
        or not any(value is plot for value in loaded.before_objects)
    ):
        raise ValueError("Actual same-p loaded plotting wrapper required")
    prefix.parameters.inherited._same(subconfigs._native_bindings(loaded), loaded.native_bindings)
    rows, refs = [], [loaded, owner, plot, cls, module, vars(module)]
    for name in ("is_after_sim_show", "is_after_sim_save"):
        descriptor = vars(cls).get(name)
        if name in vars(plot) or descriptor is None:
            raise ValueError("Original plot descriptor may not be supplied/shadowed")
        function = vars(type(descriptor)).get("__get__")
        if type(function) is not FunctionType:
            raise ValueError("Actual source-backed plot descriptor getter required")
        rows.append((name, descriptor, function))
        refs.extend((descriptor, *prefix.parameters.inherited.tissue._surface(type(descriptor))))
        refs.extend(prefix._function_bindings(function)[1])
    return SimpleNamespace(plot=plot, cls=cls, rows=tuple(rows), bindings=((), tuple(refs)))


def _compile(context):
    original = context.parent.bound.original
    prefix._function_bindings(original)
    if "float" in original.__globals__ or original.__builtins__.get("float") is not _FLOAT:
        raise ValueError("Original float lookup authority changed")
    path, cls, _, selected = _ast()
    cls = copy.deepcopy(cls)
    prefix.parameters.inherited._method(cls, "load").body = copy.deepcopy(selected)
    code = prefix.parameters._method_code(cls, "load", str(path))
    if code.co_freevars:
        raise ValueError("Unexpected closure in original plotting/constants slice")
    function = FunctionType(code, original.__globals__, original.__name__, None, None)
    if function.__builtins__ is not original.__builtins__:
        raise ValueError("Original constants cached builtins changed")
    return function


def _stacks(context):
    return ((_ACTIVE, context), *previous._stacks(context))


def _parent_refs(parent):
    return tuple((name, value) for name, value in vars(parent).items() if name != "invalid")


def _parent(context):
    parent = context.parent
    if (
        previous._ISSUED.get(context.parent_owner) is not parent
        or parent.owner is not context.parent_owner
        or parent.p is not context.p
        or parent.invalid is not context.retired
        or parent.active
        or parent.validating
        or parent.thread != get_ident()
        or parent.guard.active
        or parent.guard.invalid
        or parent.source_completed is not True
        or parent.source_error is not None
        or parent.capture_errors
        or parent.observation_errors
        or previous._CONSUMED.get(parent.source_owner) is not parent
        or previous._PARENTS.get(parent.parent_owner) is not parent
        or parent.trial is not context.parent_trial
        or parent.trial is not parent.original_trial
        or _digest(previous.trial_record(parent.trial)) != parent.trial.identity
        or parent.trial.work != tuple(parent.work)
        or parent.trial.calls != tuple(parent.calls.items())
    ):
        raise ValueError("Original successful colormap owner/retirement/work association changed")
    current = _parent_refs(parent)
    if len(current) != len(context.parent_refs) or any(
        a[0] != b[0] or a[1] is not b[1] for a, b in zip(current, context.parent_refs, strict=True)
    ):
        raise ValueError("Original parent context references changed")
    prefix.parameters.inherited._same(previous._bindings(), parent.bindings)
    prefix.parameters.inherited._same(
        previous.runtime.bindings(previous.runtime.bind(parent.bound, parent.kinds)),
        parent.runtime_bindings,
    )
    before = len(parent.observations)
    context.historical["_history"](parent)
    context.historical["_outputs"](parent)
    observed = _cm_graph(parent)
    _same_cm(observed, parent.after)
    context.metadata_work.append(
        (
            "actual_historical_metadata_and_colormap_capture",
            len(parent.observations) - before,
            observed.array_copies,
            observed.callbacks,
        )
    )
    prefix.parameters.inherited._same(_plot(context).bindings, context.plot.bindings)
    prefix.parameters.inherited._same_graph(_fields(context), context.before_graph)
    fields = vars(context.p)
    appended = tuple(fields)[len(context.before_names) :]
    if (
        tuple(fields)[: len(context.before_names)] != context.before_names
        or appended != context.plan["stores"][: len(appended)]
    ):
        raise ValueError("Original field layout/new constants prefix changed")
    if len(appended) > len(context.plan["stores"]):
        raise ValueError("Unowned geometry/ion/later stores appeared")


def _check(context):
    if (
        context.invalid
        or context.guard.invalid
        or context.thread != get_ident()
        or not context.guard.audit_ready
        or _CONSUMED.get(context.parent_owner) is not context
        or _CLAIMED.get(context.parent.source_owner) is not context
    ):
        raise ValueError("Poisoned/foreign initializer-constants epoch")
    if context.active and any(
        not stack or stack[-1] is not value for stack, value in _stacks(context)
    ):
        raise ValueError("Shared constants exclusion changed")
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("Issued constants source plan changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(
        prefix._function_bindings(context.function), context.function_bindings
    )
    for name, function in context.historical.items():
        prefix.parameters.inherited._same(
            prefix._function_bindings(function), context.historical_bindings[name]
        )
    _parent(context)


def _reserve(owner):
    if type(owner) is not previous.ColormapsOwner or owner not in previous._ISSUED:
        raise ConstantsRejected("Actual issued colormap successor required", stage="owner")
    if not _LOCK.acquire(blocking=False):
        raise ConstantsRejected("Constants reservation busy", stage="reservation")
    try:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise ConstantsRejected("Reentrant constants attempt", stage="reentrant")
        parent = previous._ISSUED[owner]
        if owner in _CONSUMED or parent.source_owner in _CLAIMED:
            raise ConstantsRejected("Original constants attempt consumed", stage="consumed")
        context = SimpleNamespace(
            parent_owner=owner,
            parent=parent,
            p=parent.p,
            thread=get_ident(),
            active=True,
            invalid=False,
            retired=False,
            registered=False,
            stage="admission",
            source_completed=False,
            source_error=None,
            capture_errors=(),
            observation_errors=(),
            entries=0,
            returns=0,
            plot_entries=0,
            plot_returns=[],
            raw_returns=[],
            raw_return=None,
            locals={},
            events=[],
            work=[],
            metadata_work=[],
            validations=[],
            validating=False,
            source_return_graph=None,
            failure_capture=None,
            guard=SimpleNamespace(
                thread=get_ident(),
                active=True,
                invalid=False,
                audit_ready=False,
                directory_depth=0,
                directory_calls=0,
                directory_targets=(),
                filesystem=[],
            ),
        )
        _CONSUMED[owner] = _CLAIMED[parent.source_owner] = context
        _ACTIVE.append(context)
        return context
    finally:
        _LOCK.release()


@contextmanager
def _claim(context):
    primary = None
    try:
        if previous._validate(context.parent_owner) is not context.parent:
            raise ValueError("Foreign initial colormap verification result")
        context.plan = source_plan()
        context.source_identity = _digest(context.plan)
        context.parent_trial = context.parent.trial
        context.before_names = tuple(vars(context.p))
        if any(name in vars(context.p) for name in context.plan["stores"]):
            raise ValueError("Existing plotting/constants stores cannot be retrofitted")
        context.before_graph = _fields(context)
        context.parent_refs = _parent_refs(context.parent)
        context.historical, _ = _historical()
        context.historical_bindings = {
            name: prefix._function_bindings(function)
            for name, function in context.historical.items()
        }
        context.plot = _plot(context)
        context.function = _compile(context)
        context.function_bindings = prefix._function_bindings(context.function)
        context.bindings = _bindings()
        with claims._registry(context.parent.parent_owner):
            if any(stack for stack, _ in _stacks(context)[1:]):
                claims._busy(context.parent.parent_owner, "constants_conflict")
            for stack, value in _stacks(context)[1:]:
                stack.append(value)
            context.registered = True
            previous.mod.subconfigs.paths._install_audit(context.guard)
            _check(context)
            context.parent.invalid = context.retired = True
        context.stage = "original_plotting_constants"
        _check(context)
        yield
    except BaseException as error:
        primary = error
        context.claim_error = error
        raise
    finally:
        if context.registered:
            try:
                with claims._registry(context.parent.parent_owner):
                    for stack, value in reversed(_stacks(context)[1:]):
                        if not stack or stack[-1] is not value:
                            raise ValueError("Constants registry changed at closure")
                        stack.pop()
            except BaseException as error:
                context.capture_errors += (("claim_release", error),)
        context.active = context.guard.active = False
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()
        else:
            context.capture_errors += (
                ("reservation_release", ValueError("Constants reservation changed")),
            )
        if primary is not None:
            try:
                primary.initializer_constants = context
            except BaseException as error:
                context.capture_errors += (("exception_attachment", error),)
        elif context.capture_errors:
            context.invalid = True
            raise ConstantsRejected(
                "Constants closure incomplete",
                stage="closure",
                partial=context,
                capture_errors=context.capture_errors,
            )


def _copy_locals(frame):
    return dict(frame.f_locals)


def _returned(context, role, frame, value):
    context.raw_return = (role, frame, value)
    context.raw_returns.append(context.raw_return)
    if role == "source":
        context.returns += 1
        context.locals = _copy_locals(frame)
        context.source_return_graph = _fields(context, complete=True)
    else:
        context.plot_returns.append(value)
    context.events.append((role, "return_or_unwind", _copy_locals(frame)))


@contextmanager
def _observe(context):
    prior, trace = sys.getprofile(), sys.gettrace()
    descriptor_codes = {row[2].__code__ for row in context.plot.rows}
    native = str(prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"

    def profile(frame, event, arg):
        source = frame.f_code is context.function.__code__
        descriptor = frame.f_code in descriptor_codes
        role = "source" if source else "plot_alias" if descriptor else None
        if event == "call" and role is not None:
            if context.invalid or context.guard.invalid or not context.active:
                raise ValueError("Poisoned constants source entry")
            if source:
                context.entries += 1
                if context.entries != 1 or frame.f_locals.get("self") is not context.p:
                    raise ValueError("Duplicate/foreign constants source attempt")
            else:
                context.plot_entries += 1
                index = context.plot_entries - 1
                if index >= 2:
                    raise ValueError("Duplicate plotting alias read")
                row = context.plot.rows[index]
                if (
                    frame.f_code is not row[2].__code__
                    or frame.f_locals.get("self_descriptor") is not row[1]
                    or frame.f_locals.get("self") is not context.plot.plot
                    or frame.f_locals.get("cls") is not context.plot.cls
                ):
                    raise ValueError("Original plotting descriptor/receiver/order changed")
        if event == "call" and (role is not None or frame.f_code.co_filename.startswith(native)):
            if len(context.work) >= MAX_WORK:
                raise ValueError("Constants actual source work bound exceeded")
            context.work.append(
                (
                    len(context.work),
                    role or "nested_native",
                    frame.f_code.co_filename,
                    frame.f_code.co_qualname,
                    "entered_not_case_credit",
                )
            )
        if event == "return" and role is not None:
            try:
                _returned(context, role, frame, arg)
            except BaseException as error:
                context.observation_errors += ((role + "_return_capture", error),)
        if prior is not None:
            if event == "return":
                try:
                    prior(frame, event, arg)
                except BaseException as error:
                    context.observation_errors += (("inherited_return", error),)
            else:
                prior(frame, event, arg)

    try:
        sys.setprofile(profile)
        yield
    finally:
        for name, setter, value in (
            ("profile_restore", sys.setprofile, prior),
            ("trace_restore", sys.settrace, trace),
        ):
            try:
                setter(value)
            except BaseException as error:
                context.observation_errors += ((name, error),)


def _invoke(context):
    return context.function(context.p)


def _outputs(context):
    if tuple(vars(context.p))[len(context.before_names) :] != context.plan["stores"]:
        raise ValueError("Complete original plotting/constants store order required")
    if (
        context.entries != 1
        or context.returns != 1
        or context.raw_return is None
        or context.raw_return[0] != "source"
        or context.raw_return[2] is not None
        or context.plot_entries != 2
        or len(context.plot_returns) != 2
        or context.source_return_graph is None
        or context.locals.get("self") is not context.p
        or context.locals.get("ro") is not vars(context.p)["_conf"]["results options"]
        or context.locals.get("iu") is not vars(context.p)["_conf"]["internal parameters"]
    ):
        raise ValueError("Complete source/plot-alias return/config associations required")
    if (
        vars(context.p)["turn_all_plots_off"] is not (not context.plot_returns[0])
        or vars(context.p)["autosave"] is not context.plot_returns[1]
    ):
        raise ValueError("Actual plot-alias returns lost their original stores")
    prefix.parameters.inherited._same_graph(
        _fields(context, complete=True), context.source_return_graph
    )


def trial_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_identity,
        before=value.before_identity,
        after=value.after_identity,
        source=value.source_identity,
        stores=value.stores,
        work=value.work,
        metadata_work=value.metadata_work,
        source_completed=value.source_completed,
        source_lines=(1017, 1125),
        next_line=1127,
        biological_cases=0,
        full_Parameters_ions_phase_INIT=False,
    )


def prepare(owner, *, law_id, enabled=False):
    if enabled is not True or any(
        os.environ.get(gate) != "1" for gate in (RELEASE, previous.RELEASE, previous.mod.RELEASE)
    ):
        raise ConstantsRejected("Original initializer constants remain held", stage="release")
    if type(law_id) is not str or law_id != LAW_ID:
        raise ConstantsRejected("Explicit original plotting/constants law required", stage="law")
    context = _reserve(owner)
    with _claim(context):
        primary = None
        try:
            with _observe(context):
                try:
                    _invoke(context)
                except BaseException as error:
                    context.source_error = error
                    raise
            context.source_completed = True
            if context.observation_errors:
                raise ValueError("Original constants reached-output capture incomplete")
            _check(context)
            _outputs(context)
            context.after_graph = _fields(context, complete=True)
            value = Trial(
                context.parent_trial.identity,
                _digest(context.before_graph[1]),
                _digest(context.after_graph[1]),
                context.source_identity,
                context.plan["stores"],
                tuple(context.work),
                tuple(context.metadata_work),
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
            context.original_trial = context.trial
            owner = object.__new__(ConstantsOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            primary = context.operation_error = error
        try:
            context.failure_capture = _fields(context, complete=True)
        except BaseException as error:
            context.capture_errors += (("failure_capture", error),)
        context.invalid = True
        raise ConstantsRejected(
            "Original constants attempt issued no successor",
            stage=context.stage,
            partial=context,
            source_error=context.source_error,
            capture_errors=(*context.observation_errors, *context.capture_errors),
        ) from primary


def _validate(owner):
    if type(owner) is ConstantsOwner and owner in _REMAINDER_CONSUMED:
        raise ConstantsRejected(
            "Constants owner irreversibly reserved for load remainder", stage="remainder_retired"
        )
    return _validate_state(owner)


def _validate_state(owner):
    if type(owner) is not ConstantsOwner or owner not in _ISSUED:
        raise ConstantsRejected("Actual issued initializer-constants owner required", stage="owner")
    context = _ISSUED[owner]
    if context.active or context.validating or _ACTIVE:
        raise ConstantsRejected("Active/overlapping constants successor", stage="state")
    context.validating = True
    validation = SimpleNamespace(
        invalid=False,
        guard=SimpleNamespace(
            thread=get_ident(),
            active=True,
            invalid=False,
            audit_ready=False,
            directory_depth=0,
            directory_calls=0,
            directory_targets=(),
            filesystem=[],
        ),
    )
    registered = False
    primary = release_error = None
    context.validations.append(("successor_validation", "attempted"))
    try:
        with claims._registry(context.parent.parent_owner):
            if any(stack for stack, _ in _stacks(context)):
                claims._busy(context.parent.parent_owner, "constants_validation_conflict")
            for stack, _ in _stacks(context):
                stack.append(
                    validation.guard
                    if stack is previous.mod.subconfigs.paths._ACTIVE
                    else validation
                )
            registered = True
            previous.mod.subconfigs.paths._install_audit(validation.guard)
        if (
            context.owner is not owner
            or context.source_completed is not True
            or context.source_error is not None
            or context.capture_errors
            or context.observation_errors
            or context.trial is not context.original_trial
            or context.trial.work != tuple(context.work)
            or _digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Original successful constants owner/completion/work changed")
        _check(context)
        _outputs(context)
        prefix.parameters.inherited._same_graph(
            _fields(context, complete=True), context.after_graph
        )
        if validation.invalid or validation.guard.invalid:
            raise ValueError("Read-only constants validation poisoned")
        context.validations.append(("successor_validation", "completed"))
        return context
    except BaseException as error:
        primary = error
        context.invalid = True
        raise ConstantsRejected(
            "Stale original initializer constants",
            stage="drift",
            partial=context,
            source_error=error,
        ) from error
    finally:
        if registered:
            try:
                with claims._registry(context.parent.parent_owner):
                    for stack, _ in reversed(_stacks(context)):
                        expected = (
                            validation.guard
                            if stack is previous.mod.subconfigs.paths._ACTIVE
                            else validation
                        )
                        if not stack or stack[-1] is not expected:
                            raise ValueError("Constants validation registry changed")
                        stack.pop()
            except BaseException as error:
                release_error = error
                context.invalid = True
                context.capture_errors += (("validation_release", error),)
        validation.guard.active = False
        context.validating = False
        if primary is None and release_error is not None:
            raise ConstantsRejected(
                "Constants validation closure incomplete",
                stage="closure",
                partial=context,
                source_error=release_error,
            ) from release_error


def require_continuation(owner):
    context = _validate(owner)
    raise ConstantsRejected(
        "Original geometry-derived settings/ion-profile prerequisite required",
        stage="next_prerequisite",
        partial=dict(next_line=1127, parent=context.trial.identity),
    )


def _remainder_scope():
    """Derive mutation names/order from the pinned original source, without running it."""
    path, cls, load, _ = _ast()
    tail = load.body[203:218]
    if len(load.body) != 218 or ast.unparse(tail[-1]) != "self._load_ion_profile()":
        raise ValueError("Original complete-load tail extent changed")
    ion = prefix.parameters.inherited._method(cls, "_load_ion_profile")
    balance = next(
        n
        for n in ast.parse(path.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_balance_charge"
    )

    def stores(nodes):
        names = []
        for statement in nodes:
            for node in ast.walk(statement):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        for item in ast.walk(target):
                            if (
                                isinstance(item, ast.Attribute)
                                and isinstance(item.value, ast.Name)
                                and item.value.id == "self"
                                and item.attr not in names
                            ):
                                names.append(item.attr)
        return tuple(names)

    names = ("BASIC", "BASIC_CA", "MAMMAL", "AMPHIBIAN", "CUSTOM")
    node = next(n for n in ion.body if isinstance(n, ast.If))
    rows = []
    for name in names:
        if ast.unparse(node.test) != "self.ion_profile is IonProfileType." + name:
            raise ValueError("Original ion profile dispatch changed")
        rows.append((name, stores(node.body)))
        if name != names[-1]:
            if len(node.orelse) != 1 or not isinstance(node.orelse[0], ast.If):
                raise ValueError("Original ion profile elif order changed")
            node = node.orelse[0]
    if len(node.orelse) != 1 or not isinstance(node.orelse[0], ast.Raise):
        raise ValueError("Original unknown ion-profile refusal changed")
    tail_stores = stores(tail)
    replaced = ("wsx", "wsy")
    return dict(
        law=REMAINDER_HANDOFF_LAW,
        source=str(path),
        statement_slice=(203, 218),
        parameters_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        tail_ast=_digest(ast.dump(ast.Module(body=tail, type_ignores=[]))),
        ion_ast=_digest(ast.dump(ion)),
        balance_ast=_digest(ast.dump(balance)),
        replaced=replaced,
        profiles=tuple(rows),
        append_orders=tuple(
            tuple(n for n in tail_stores if n not in replaced) + fields for _, fields in rows
        ),
        permits_source_execution=False,
        permits_phase_or_INIT=False,
    )


def remainder_record_document(value):
    return dict(
        law=REMAINDER_HANDOFF_LAW,
        parent=value.parent_identity,
        source=value.source_identity,
        scope=value.scope_identity,
        before=value.before_identity,
        after=value.after_identity,
        before_names=value.before_names,
        after_names=value.after_names,
        work=value.work,
        succeeded=value.succeeded,
        failure_stage=value.failure_stage,
        failure_type=value.failure_type,
        capture_stages=value.capture_stages,
        complete_load_or_phase_admission=False,
        live_state_validation=False,
        parent_verified=value.parent_verified,
    )


def _remainder_context(grant):
    if type(grant) is not RemainderGrant or grant not in _REMAINDER_ISSUED:
        raise ConstantsRejected("Actual issued remainder grant required", stage="grant")
    context, owner, base, guard = _REMAINDER_ISSUED[grant]
    if (
        context.claim is not grant
        or context.owner is not owner
        or context.base is not base
        or context.guard is not guard
        or context.thread != get_ident()
        or guard.thread != context.thread
        or _REMAINDER_CONSUMED.get(owner) is not context
    ):
        raise ConstantsRejected("Remainder issuance/consumption association changed", stage="grant")
    sealed = _REMAINDER_SEALS.get(grant)
    if sealed is not None and any(vars(context).get(name) is not value for name, value in sealed):
        raise ConstantsRejected(
            "Original remainder source/context references changed", stage="grant"
        )
    return context


def remainder_handoff(owner, *, law_id, enabled=False):
    if enabled is not True or any(
        os.environ.get(gate) != "1" for gate in (RELEASE, previous.RELEASE, previous.mod.RELEASE)
    ):
        raise ConstantsRejected("Original remainder handoff stays held", stage="release")
    if type(law_id) is not str or law_id != REMAINDER_HANDOFF_LAW:
        raise ConstantsRejected("Explicit original remainder handoff law required", stage="law")
    if type(owner) is not ConstantsOwner or owner not in _ISSUED:
        raise ConstantsRejected("Actual completed constants owner required", stage="owner")
    if not _REMAINDER_LOCK.acquire(blocking=False):
        raise ConstantsRejected("Remainder reservation busy", stage="reservation")
    try:
        if _REMAINDER_ACTIVE:
            _REMAINDER_ACTIVE[-1].invalid = True
            raise ConstantsRejected("Reentrant remainder handoff", stage="reentrant")
        if owner in _REMAINDER_CONSUMED:
            raise ConstantsRejected("Constants remainder handoff consumed", stage="consumed")
        claim = object.__new__(RemainderGrant)
        guard = SimpleNamespace(
            thread=get_ident(),
            active=False,
            invalid=False,
            audit_ready=False,
            directory_depth=0,
            directory_calls=0,
            directory_targets=(),
            filesystem=[],
        )
        context = SimpleNamespace(
            claim=claim,
            owner=owner,
            base=_ISSUED[owner],
            guard=guard,
            thread=get_ident(),
            entered=False,
            active=False,
            invalid=False,
            checking=False,
            registered=False,
            rows=(),
            p=None,
            record=None,
            work=[],
            validation_work=[],
            source_error=None,
            capture_errors=(),
            stage="reservation",
            before_values=None,
            after_values=None,
            before_graph=None,
            after_graph=None,
            before_names=(),
            after_names=(),
            parent_identity="",
            source_identity="",
            scope_identity="",
            parent_verified=False,
            first_refusal=None,
            refusal_stage="",
            refusals=[],
        )
        # Reserve before validation, capture, caller callbacks or any p work. Never rearm.
        _REMAINDER_CONSUMED[owner] = context
        _REMAINDER_ISSUED[claim] = (context, owner, context.base, guard)
        return claim
    finally:
        _REMAINDER_LOCK.release()


def _remainder_poison(context, stage, error):
    context.invalid = True
    entry = _REMAINDER_ISSUED.get(context.claim)
    if entry is not None and entry[0] is context:
        entry[3].invalid = True
    if context.first_refusal is None:
        context.first_refusal, context.refusal_stage = error, stage
    context.refusals.append((stage, error))


def _remainder_checked_context(grant, stage):
    try:
        return _remainder_context(grant)
    except BaseException as error:
        entry = _REMAINDER_ISSUED.get(grant) if type(grant) is RemainderGrant else None
        if entry is not None:
            _remainder_poison(entry[0], stage, error)
        raise


def _remainder_work(context, validation, role, detail):
    if len(context.work) + len(context.validation_work) >= MAX_WORK:
        error = ConstantsRejected(
            "Remainder metadata work bound exceeded", stage="grant_work", partial=context
        )
        _remainder_poison(context, "grant_work", error)
        raise error
    target = context.validation_work if validation else context.work
    target.append((len(target), role, detail))


def _remainder_capture(context, values, phase):
    _remainder_work(context, False, phase, "graph_capture_attempt")
    return prefix.graphs.capture(
        values,
        yaml_base=context.base.parent.parent.birth.source.yaml,
        runtime_types=context.base.parent.parent.runtime.runtime_types,
    )


def _remainder_ancestry(base):
    cm, mod = base.parent, base.parent.parent
    grn, seven = mod.parent, previous.mod.subconfigs
    loaded = grn.authority.loaded
    if (
        previous._ISSUED.get(cm.owner) is not cm
        or previous.mod._ISSUED.get(mod.owner) is not mod
        or previous.mod.previous._ISSUED.get(grn.owner) is not grn
        or seven._ISSUED.get(loaded.owner) is not loaded
        or any(item.p is not base.p for item in (cm, mod, grn, loaded))
        or loaded.owner in claims._CONSTRUCTED
    ):
        raise ValueError("Actual same-p unconstructed constants/GRN/seven lineage required")
    return loaded


def _remainder_history(context):
    """Authenticate historical metadata only: never run a stale full-p validator."""
    base = context.base
    _remainder_work(
        context, not context.active, "source_binding_and_history_check", "attempted_metadata"
    )
    if any(vars(base).get(name) is not value for name, value in context.source_edges):
        raise ValueError("Original constants before/work/bindings/guard references changed")
    if (
        context.thread != get_ident()
        or _ISSUED.get(context.owner) is not base
        or base.owner is not context.owner
        or base.p is not context.p
        or base.active
        or base.validating
        or base.invalid
        or base.guard is not context.base_guard
        or base.guard.active
        or base.guard.invalid
        or not base.guard.audit_ready
        or base.thread != get_ident()
        or base.guard.thread != base.thread
        or base.retired is not context.base_retired
        or base.source_completed is not True
        or base.source_error is not None
        or base.capture_errors
        or base.observation_errors
        or base.trial is not context.trial
        or base.original_trial is not context.trial
        or base.work is not context.source_work
        or base.bindings is not context.source_bindings
        or base.trial.work != tuple(base.work)
        or base.trial.source_completed is not True
        or _digest(base.before_graph[1]) != base.trial.before_identity
        or _digest(base.after_graph[1]) != base.trial.after_identity
        or _digest(context.before_graph[1]) != base.trial.after_identity
        or _digest(trial_record(base.trial)) != context.parent_identity
        or _CONSUMED.get(base.parent_owner) is not base
        or _CLAIMED.get(base.parent.source_owner) is not base
        or _remainder_ancestry(base) is not context.loaded
        or vars(context.p).get("_conf") is not context.config
        or context.config.get("internal parameters") is not context.internal
        or base.locals.get("iu") is not context.internal
        or vars(context.p).get("vol_env") is not context.volume
    ):
        raise ValueError("Original constants/grant ancestry, trial or retained inputs changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(_bindings(), base.bindings)
    prefix.parameters.inherited._same(
        prefix._function_bindings(base.function), base.function_bindings
    )
    if (
        _digest(_remainder_scope()) != context.scope_identity
        or base.source_identity != context.source_identity
        or _digest(source_plan()) != context.source_identity
    ):
        raise ValueError("Original constants/remainder source identities changed")


def _remainder_check(grant):
    context = _remainder_checked_context(grant, "grant_check_context")
    if not context.active:
        raise ConstantsRejected(
            "Closed/unentered remainder grant grants no p access",
            stage="grant_state",
            partial=context,
        )
    if (
        context.invalid
        or context.checking
        or context.guard.invalid
        or not context.guard.active
        or not context.guard.audit_ready
        or context.guard.directory_depth != 0
        or context.guard.directory_calls != 0
        or context.guard.filesystem
        or not _REMAINDER_ACTIVE
        or _REMAINDER_ACTIVE[-1] is not context
    ):
        error = ConstantsRejected(
            "Inactive/poisoned remainder grant", stage="grant_state", partial=context
        )
        _remainder_poison(context, "grant_check_admission", error)
        raise error from context.first_refusal if error is not context.first_refusal else None
    context.checking = True
    try:
        if any(not stack or stack[-1] is not value for stack, value in context.rows):
            raise ValueError("Shared remainder exclusion changed")
        _remainder_history(context)
        fields = vars(context.p)
        if tuple(fields)[: len(context.before_names)] != context.before_names:
            raise ValueError("Original pre-tail parameter order changed")
        appended = tuple(fields)[len(context.before_names) :]
        if not any(appended == order[: len(appended)] for order in context.scope["append_orders"]):
            raise ValueError("Only the literal ordered load-tail/profile prefix may be added")
        for name, value in context.before_values.items():
            if name not in context.scope["replaced"] and fields.get(name) is not value:
                raise ValueError("Unowned original parameter field replacement")
        prefix.parameters.inherited._same_graph(
            _remainder_capture(context, context.before_values, "active_old_values"),
            context.before_graph,
        )
        _same_cm(_cm_graph(context.base.parent), context.colormaps)
        if context.invalid or context.guard.invalid:
            raise ValueError("Read-only capture/reentrant remainder check poisoned")
        return context.p
    except BaseException as error:
        _remainder_poison(context, "grant_check", error)
        raise
    finally:
        context.checking = False


def _remainder_enter(grant):
    context = _remainder_context(grant)
    if context.entered:
        context.invalid = True
        raise ConstantsRejected(
            "Remainder entry already attempted", stage="grant_entry", partial=context
        )
    context.entered = True
    if not _REMAINDER_LOCK.acquire(blocking=False):
        context.invalid = True
        raise ConstantsRejected(
            "Remainder entry reservation busy", stage="grant_entry", partial=context
        )
    try:
        if _REMAINDER_ACTIVE:
            context.invalid = True
            _REMAINDER_ACTIVE[-1].invalid = True
            raise ConstantsRejected(
                "Remainder entry already attempted/busy", stage="grant_entry", partial=context
            )
        context.active = True
        _REMAINDER_ACTIVE.append(context)
    finally:
        _REMAINDER_LOCK.release()
    try:
        context.stage = "constants_admission"
        # Retain available original input identity even when validation itself refuses.
        input_trial = vars(context.base).get("original_trial")
        if type(input_trial) is Trial:
            context.parent_identity = input_trial.identity
            context.source_identity = input_trial.source_identity
        _remainder_work(context, False, "actual_constants_validation", "attempted")
        metadata_start = len(context.base.metadata_work)
        validation_error = None
        try:
            base = _validate_state(context.owner)
        except BaseException as error:
            validation_error = error
            raise
        finally:
            try:
                _remainder_work(
                    context,
                    False,
                    "parent_validation_metadata_delta",
                    tuple(context.base.metadata_work[metadata_start:]),
                )
            except BaseException as secondary:
                context.capture_errors += (("parent_validation_accounting", secondary),)
                if validation_error is None:
                    raise
        if base is not context.base:
            raise ValueError("Constants validator replaced actual source context")
        context.parent_verified = True
        context.p, context.trial = base.p, base.trial
        context.parent_identity = context.trial.identity
        context.source_identity = base.source_identity
        context.source_work, context.source_bindings = base.work, base.bindings
        context.base_guard, context.base_retired = base.guard, base.retired
        context.source_edges = tuple(
            (name, vars(base)[name])
            for name in (
                "p",
                "trial",
                "original_trial",
                "source_identity",
                "owner",
                "parent_owner",
                "parent",
                "parent_trial",
                "before_graph",
                "after_graph",
                "guard",
                "plot",
                "function",
                "function_bindings",
                "historical",
                "historical_bindings",
                "parent_refs",
                "plan",
                "source_return_graph",
                "work",
                "metadata_work",
                "validations",
            )
        )
        context.config = vars(context.p)["_conf"]
        context.internal = base.locals["iu"]
        context.volume = vars(context.p)["vol_env"]
        context.loaded = _remainder_ancestry(base)
        context.scope = _remainder_scope()
        context.scope_identity = _digest(context.scope)
        context.bindings = _bindings()
        context.before_names = tuple(vars(context.p))
        if (
            "_run_sim" in context.before_names
            or context.internal is not context.config["internal parameters"]
        ):
            raise ValueError("Original iu/fresh pre-phase p required")
        context.before_values = {
            n: vars(context.p)[n] for n in context.before_names if n not in CM_STORES
        }
        context.before_graph = _remainder_capture(
            context, context.before_values, "initial_old_values"
        )
        prefix.parameters.inherited._same_graph(context.before_graph, base.after_graph)
        context.colormaps = _cm_graph(base.parent)
        with claims._registry(context.loaded.owner):
            stacks = _stacks(base)
            if any(stack for stack, _ in stacks):
                claims._busy(context.loaded.owner, "remainder_conflict")
            context.rows = tuple(
                (
                    stack,
                    context.guard if stack is previous.mod.subconfigs.paths._ACTIVE else context,
                )
                for stack, _ in stacks
            )
            for stack, value in context.rows:
                stack.append(value)
            context.registered = True
            context.guard.active = True
            previous.mod.subconfigs.paths._install_audit(context.guard)
        context.stage = "original_tail_scope"
        _REMAINDER_SEALS[grant] = tuple(
            (name, vars(context)[name])
            for name in (
                "claim",
                "owner",
                "base",
                "guard",
                "p",
                "trial",
                "source_identity",
                "source_edges",
                "source_work",
                "source_bindings",
                "base_guard",
                "base_retired",
                "config",
                "internal",
                "volume",
                "loaded",
                "scope",
                "scope_identity",
                "bindings",
                "before_names",
                "before_values",
                "before_graph",
                "colormaps",
                "rows",
            )
        )
        grant.check()
        return grant
    except BaseException as error:
        try:
            _remainder_close(grant, error)
        except BaseException as secondary:
            context.invalid = True
            context.capture_errors += (("enter_primary_recovery", secondary),)
        raise


def _remainder_close(grant, primary):
    entry = _REMAINDER_ISSUED.get(grant) if type(grant) is RemainderGrant else None
    if entry is None:
        raise ConstantsRejected("Actual issued remainder closure required", stage="grant_closure")
    context = entry[0]
    if grant in _REMAINDER_CLOSED or not context.entered:
        context.invalid = True
        raise ConstantsRejected(
            "Remainder closure unavailable or already consumed",
            stage="grant_closure",
            partial=context,
        )
    if primary is not None:
        context.source_error = primary
        _remainder_poison(context, "body_failure", primary)
    closure_error = context.first_refusal
    try:
        _remainder_context(grant)
    except BaseException as error:
        _remainder_poison(context, "closure_association", error)
        if closure_error is None:
            closure_error = error
        context.capture_errors += (("closure_association", error),)
    sealed = dict(_REMAINDER_SEALS.get(grant, ()))
    original_rows = sealed.get("rows", context.rows)
    original_guard = entry[3]
    try:
        if primary is None and closure_error is None:
            grant.check()
            context.after_names = tuple(vars(context.p))
            appended = context.after_names[len(context.before_names) :]
            if appended not in context.scope["append_orders"]:
                raise ValueError("Complete original tail/profile store extent required at closure")
            context.after_values = {
                n: vars(context.p)[n] for n in context.after_names if n not in CM_STORES
            }
            context.after_graph = _remainder_capture(
                context, context.after_values, "closed_new_values"
            )
            grant.check()
    except BaseException as error:
        _remainder_poison(context, "scope_closure", error)
        if closure_error is None:
            closure_error = error
        context.capture_errors += (("scope_closure", error),)
    finally:
        if context.registered or original_rows:
            try:
                with claims._registry(sealed.get("loaded", context.loaded).owner):
                    for stack, value in reversed(original_rows):
                        if not stack or stack[-1] is not value:
                            error = ValueError("Remainder shared registry changed at closure")
                            _remainder_poison(context, "registry_release", error)
                            context.capture_errors += (("registry_release", error),)
                            if closure_error is None:
                                closure_error = error
                        else:
                            stack.pop()
            except BaseException as error:
                _remainder_poison(context, "registry_release", error)
                context.capture_errors += (("registry_release", error),)
                if closure_error is None:
                    closure_error = error
        context.active = original_guard.active = False
        if _REMAINDER_ACTIVE and _REMAINDER_ACTIVE[-1] is context:
            _REMAINDER_ACTIVE.pop()
        else:
            error = ValueError("Remainder reservation changed")
            _remainder_poison(context, "reservation_release", error)
            context.capture_errors += (("reservation_release", error),)
            if closure_error is None:
                closure_error = error
    error = primary if primary is not None else closure_error
    context.closure_error = closure_error
    context.effective_primary = error
    try:
        record = RemainderRecord(
            context.parent_identity,
            context.source_identity,
            context.scope_identity,
            _digest(context.before_graph[1]) if context.before_graph is not None else "",
            _digest(context.after_graph[1]) if context.after_graph is not None else "",
            context.before_names,
            context.after_names,
            tuple(context.work),
            error is None and not context.invalid and not context.capture_errors,
            context.stage if error is not None or context.capture_errors else "",
            type.__getattribute__(type(error), "__qualname__") if error is not None else "",
            tuple(stage for stage, _ in context.capture_errors),
            "",
            parent_verified=context.parent_verified,
        )
        context.record = replace(record, identity=_digest(remainder_record_document(record)))
        _REMAINDER_CLOSED[grant] = (context, context.record)
    except BaseException as secondary:
        _remainder_poison(context, "record_capture", secondary)
        context.capture_errors += (("record_capture", secondary),)
        if error is None:
            error = secondary
            context.effective_primary = secondary
    if error is not None:
        try:
            error.remainder_grant = grant
        except BaseException as secondary:
            context.capture_errors += (("exception_attachment", secondary),)
    if primary is None and (context.record is None or not context.record.succeeded):
        raise ConstantsRejected(
            "Remainder scope closure refused",
            stage="grant_closure",
            partial=context,
            source_error=error,
            capture_errors=context.capture_errors,
        ) from error


def validate_remainder_history(grant, *, original_owner):
    """Closed historical record only; no p access permission or old full-p replay.

    The complete-load/WorldReady owner separately validates live post-tail state.
    Later SEED-only additions therefore do not become a false stale-parent failure.
    """
    context = _remainder_checked_context(grant, "grant_history_context")
    closed = _REMAINDER_CLOSED.get(grant)
    if (
        original_owner is not context.owner
        or context.active
        or context.checking
        or context.invalid
        or context.guard.active
        or context.guard.invalid
        or not context.guard.audit_ready
        or context.guard.directory_depth != 0
        or context.guard.directory_calls != 0
        or context.guard.filesystem
        or context.source_error is not None
        or context.capture_errors
        or closed is None
        or closed[0] is not context
        or closed[1] is not context.record
        or context.record.succeeded is not True
        or context.record.parent_verified is not True
        or context.parent_verified is not True
    ):
        error = ConstantsRejected(
            "Actual successful closed remainder grant required",
            stage="grant_history",
            partial=context,
        )
        _remainder_poison(context, "grant_history_admission", error)
        raise error from context.first_refusal if error is not context.first_refusal else None
    context.checking = True
    try:
        _remainder_work(context, True, "closed_history_validation", "attempted")
        _remainder_history(context)
        record = context.record
        if (
            record.work != tuple(context.work)
            or record.parent_identity != context.trial.identity
            or record.before_identity != _digest(context.before_graph[1])
            or record.after_identity != _digest(context.after_graph[1])
            or _digest(remainder_record_document(record)) != record.identity
        ):
            raise ValueError("Original immutable remainder record/capture changed")
        if context.invalid or context.guard.invalid:
            raise ValueError("Closed history validation became poisoned") from context.first_refusal
        _remainder_work(context, True, "closed_history_validation", "completed")
        _remainder_checked_context(grant, "grant_history_commit")
        return record
    except BaseException as error:
        _remainder_poison(context, "grant_history", error)
        raise
    finally:
        context.checking = False


def _bindings():
    functions = (
        _digest,
        _ast,
        _historical,
        source_plan,
        _fields,
        _cm_graph,
        _same_cm,
        _plot,
        _compile,
        _stacks,
        _parent_refs,
        _parent,
        _check,
        _reserve,
        _claim,
        _claim.__wrapped__,
        _copy_locals,
        _returned,
        _observe,
        _observe.__wrapped__,
        _invoke,
        _outputs,
        trial_record,
        prepare,
        _validate,
        _validate_state,
        require_continuation,
        _remainder_scope,
        remainder_record_document,
        _remainder_context,
        _remainder_poison,
        _remainder_checked_context,
        _remainder_work,
        remainder_handoff,
        _remainder_capture,
        _remainder_ancestry,
        _remainder_history,
        _remainder_check,
        _remainder_enter,
        _remainder_close,
        validate_remainder_history,
        RemainderGrant.__init__,
        RemainderGrant.__reduce_ex__,
        RemainderGrant.__enter__,
        RemainderGrant.__exit__,
        RemainderGrant.parameters.fget,
        RemainderGrant.check,
        RemainderGrant.record.fget,
        RemainderGrant.metadata_work.fget,
        _bindings,
        ConstantsOwner.__init__,
        ConstantsOwner.__reduce_ex__,
        ConstantsOwner.parameters.fget,
        ConstantsOwner.trial.fget,
    )
    return (), (
        LAW_ID,
        PREVIOUS_SHA256,
        RELEASE,
        START,
        STOP,
        MAX_WORK,
        _FLOAT,
        CM_STORES,
        _LOCK,
        _ACTIVE,
        _ISSUED,
        _CONSUMED,
        _CLAIMED,
        ConstantsOwner,
        ConstantsRejected,
        Trial,
        REMAINDER_HANDOFF_LAW,
        _REMAINDER_LOCK,
        _REMAINDER_ACTIVE,
        _REMAINDER_ISSUED,
        _REMAINDER_CONSUMED,
        _REMAINDER_CLOSED,
        _REMAINDER_SEALS,
        _REMAINDER_TOKEN,
        RemainderGrant,
        RemainderRecord,
        get_ident,
        *previous._bindings()[1],
        *(
            atom
            for function in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(function)
        ),
    )
