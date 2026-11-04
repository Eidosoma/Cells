"""Source/metadata contracts only; no successful synthetic phase or core owner."""

import ast
import builtins
import copy
import importlib.abc
import os
import sys
from collections import OrderedDict
from contextlib import contextmanager
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_init_profiles as stage
from validation.betse import betse_native_seed_init_profiles_software as software

_ORIGINAL_SHUFFLE = np.random.shuffle


def _original_profile_function(monkeypatch, filename, cls, name):
    path = stage.NATIVE / filename
    module_code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    parent = module_code
    if cls is not None:
        parent = next(c for c in module_code.co_consts if type(c) is CodeType and c.co_name == cls)
    code = next(c for c in parent.co_consts if type(c) is CodeType and c.co_name == name)
    module = ModuleType(filename[:-3].replace("/", "."))
    module.__dict__["__builtins__"] = vars(builtins)
    module.__file__ = str(path)
    function = FunctionType(code, vars(module), name)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return function


@pytest.mark.parametrize(
    "filename,cls,name",
    [("betse/science/tissue/tishandler.py", "TissueHandler", "init_profiles"), *stage.HELPERS],
)
def test_contextual_metadata_original_profile_helpers_are_authenticated_without_execution(
    monkeypatch, filename, cls, name
):
    function = _original_profile_function(monkeypatch, filename, cls, name)
    core, chain = stage._native(function, filename, cls, name)
    assert core is function and chain == (function,)
    assert core.__code__.co_qualname == ((cls + ".") if cls else "") + name


@pytest.mark.parametrize(
    "change", ["isolated", "constants", "flags", "filename", "qualname", "line", "globals"]
)
def test_contextual_metadata_profile_helper_drift_refuses_before_any_call(monkeypatch, change):
    filename, cls, name = stage.IMAGE_FILE, "TissuePickerImageMask", "__init__"
    function = _original_profile_function(monkeypatch, filename, cls, name)
    code, globals_ = function.__code__, function.__globals__
    if change == "isolated":
        code = stage._compile(
            stage._node(stage._trees()[filename], cls, name), str(stage.NATIVE / filename)
        )
    elif change == "constants":
        code = code.replace(co_consts=(*code.co_consts, "foreign"))
    elif change == "flags":
        code = code.replace(co_flags=code.co_flags ^ 64)
    elif change == "filename":
        code = code.replace(co_filename="<foreign>")
    elif change == "qualname":
        code = code.replace(co_qualname="Other.__init__")
    elif change == "line":
        code = code.replace(co_firstlineno=code.co_firstlineno + 1)
    elif change == "globals":
        globals_ = dict(globals_)
    replacement = FunctionType(code, globals_, name)
    replacement.__qualname__ = cls + "." + name
    with pytest.raises(ValueError, match="Original helper code/global/builtins"):
        stage._native(replacement, filename, cls, name)


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit blocked-software release required")
    attempts = []
    initial = (sys.getprofile(), sys.gettrace())
    write = software.snapshot.write_json

    def forbid(*args, **kwargs):
        attempts.append("native_or_RNG_or_solver")
        raise AssertionError("Actual native/source/solver/RNG entry forbidden")

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                attempts.append(fullname)
                raise AssertionError("Native import forbidden in blocked software")

    def trace(frame, event, arg):
        if event == "call" and software.is_forbidden_frame(frame):
            attempts.append((frame.f_code.co_filename, frame.f_code.co_name))
            raise AssertionError("Native/source/model/RNG body forbidden")
        if initial[1] is not None:
            initial[1](frame, event, arg)
        return trace

    finder = Block()
    sys.meta_path.insert(0, finder)
    for name in (
        "shuffle",
        "permutation",
        "rand",
        "randn",
        "random",
        "random_sample",
        "seed",
        "default_rng",
        "RandomState",
        "uniform",
        "normal",
        "choice",
    ):
        monkeypatch.setattr(np.random, name, forbid)
    for name in ("inv", "pinv", "solve", "lstsq", "svd"):
        monkeypatch.setattr(np.linalg, name, forbid)
    saved_active, saved_failed = tuple(stage._ACTIVE), len(stage._FAILED)
    sys.settrace(trace)
    try:
        yield
    finally:
        active_ok = tuple(stage._ACTIVE) == saved_active
        stage._ACTIVE[:] = saved_active
        del stage._FAILED[saved_failed:]
        intact = sys.gettrace() is trace and sys.getprofile() is initial[0]
        sys.setprofile(initial[0])
        sys.settrace(initial[1])
        sys.meta_path.remove(finder)
        write(
            tmp_path / "native-blocked.json",
            dict(
                nodeid=request.node.nodeid,
                attempts=attempts,
                active_restored=active_ok,
                trace_restored=sys.gettrace() is initial[1],
                profile_restored=sys.getprofile() is initial[0],
                hooks_intact=intact,
                original_source_native_reference_or_scientific_entries=0,
                scope=(
                    "Metadata guards/AST/local synthetic functions only; no issued core/phase owner"
                ),
            ),
        )
        assert attempts == [] and active_ok and intact
        assert sys.gettrace() is initial[1] and sys.getprofile() is initial[0]


def clone(fn, **overrides):
    result = FunctionType(
        fn.__code__, dict(fn.__globals__, **overrides), fn.__name__, fn.__defaults__, fn.__closure__
    )
    result.__kwdefaults__ = fn.__kwdefaults__
    return result


def context():
    return NS(
        active=True,
        invalid=False,
        thread=stage.get_ident(),
        observing=False,
        request=None,
        trial=None,
        stage="synthetic_metadata",
        primary=None,
        entry_error=None,
        observation_error=None,
        capture_errors=(),
        cleanup_errors=(),
        raw_returns=[],
        last_raw=None,
        last_raw_history=None,
        events=[],
        work=[],
        locals={},
        picks=[],
        pick_code=None,
        percent_code=None,
        percent_active=False,
        shuffle=None,
        rng_events=[],
        source_exceptions=[],
        pending_errors={},
        helper_frames=[],
        required_hooks=(sys.getprofile(), sys.gettrace()),
        restore_setters=(sys.setprofile, sys.settrace),
        restore_getters=(sys.getprofile, sys.gettrace),
    )


@contextmanager
def active(value):
    stage._ACTIVE.append(value)
    try:
        yield value
    finally:
        assert stage._ACTIVE.pop() is value


def test_complete_original_profile_body_callsite_and_boundaries(tmp_path):
    plan = stage.source_plan()
    software.snapshot.write_json(tmp_path / "source-plan.json", plan)
    assert plan["method_lines"] == (363, 443)
    assert plan["caller_lines"] == (143, 145)
    assert plan["maps"] == ("cell_target_inds", "env_target_inds", "tissue_target_inds")
    assert plan["ion_statement_order"] == ("Na", "K", "Cl", "Ca", "M", "P")
    assert len(plan["helpers"]) == 11
    assert "redo_gj" in plan["stopped_before"]
    assert plan["source_native_or_scientific_release"] is False
    assert all(
        plan[k] is None
        for k in (
            "parent_source_pin",
            "parent_review_pin",
            "coordinator_source_pin",
            "coordinator_review_pin",
            "dyna_source_pin",
            "dyna_review_pin",
        )
    )


@pytest.mark.parametrize("name", ["init_profiles", "continue_seed"])
def test_whole_original_code_compiles_without_execution(name, tmp_path):
    code = stage._codes()[name]
    assert type(code) is CodeType and code.co_filename.startswith(str(stage.NATIVE))
    assert "redo_gj" not in code.co_names and "init_events" not in code.co_names
    if name == "continue_seed":
        assert code.co_names == ("_callbacks", "progressed_next", "dyna", "init_profiles")
        assert stage.CALLBACK_STATUS in code.co_consts
    software.snapshot.write_json(
        tmp_path / "unexecuted-code.json",
        dict(
            name=name,
            filename=code.co_filename,
            names=code.co_names,
            evaluated=False,
        ),
    )


@pytest.mark.parametrize("row", stage.HELPERS, ids=lambda row: (row[1] or "module") + "." + row[2])
def test_complete_picker_and_mapping_helper_code_is_original_not_evaluated(row):
    filename, cls, name = row
    node = stage._node(stage._trees()[filename], cls, name)
    code = stage._compile(node, str(stage.NATIVE / filename))
    assert code.co_name == name and code.co_filename == str(stage.NATIVE / filename)
    assert isinstance(node, ast.FunctionDef)
    if cls == "TissuePickerPercent":
        assert "np.random.shuffle(cell_i_copy)" in ast.unparse(node)
    if name == "pick_cells_and_mems":
        text = ast.unparse(node)
        assert text.index("self.pick_cells(cells, p)") < text.index("toolbox.flatten(mems_index)")
        assert text.index("toolbox.flatten(mems_index)") < text.index("nparray.from_iterable")


def test_original_profile_order_empty_branch_and_ion_presence_are_not_normalized():
    text = ast.unparse(stage._source_nodes()["init_profiles"])
    assert "for tissue_name, tissue_profile in self.tissue_name_to_profile.items():" in text
    assert "if len(self.cell_target_inds[tissue_name]):" in text
    assert "if p.is_ecm:" in text
    positions = [text.index("if p.ions_dict['" + name + "'] == 1:") for name in stage.IONS]
    assert positions == sorted(positions)
    assert "sorted(" not in text and "set(" not in text and "unique(" not in text
    assert "sim.Dm_cells[sim.iNa][tissue_mems_index] = tissue_profile.Dm_Na" in text


@pytest.mark.parametrize("entry", ["request", "prepare"])
def test_unbound_prerequisite_refuses_before_foreign_parent_access(entry):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("Foreign parent must not be inspected")

    with pytest.raises(stage.ProfilesRejected) as caught:
        if entry == "request":
            stage.from_core(Foreign(), law_id=stage.LAW_ID)
        else:
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "unbound_contract"


def test_direct_or_reconstructed_owner_cannot_supply_phase_authority():
    with pytest.raises(TypeError):
        stage.ProfilesOwner()
    forged = object.__new__(stage.ProfilesOwner)
    with pytest.raises(stage.ProfilesRejected, match="issued"):
        stage._authority(forged)
    with pytest.raises(TypeError):
        forged.__reduce_ex__(5)
    assert not stage._ISSUED


@pytest.mark.parametrize(
    "drift", ["none", "inactive", "invalid", "thread", "stack", "entry", "capture", "hooks"]
)
def test_local_epoch_guard_is_sticky_and_never_issues_an_owner(drift):
    value = context()
    entry = RuntimeError("first refusal")
    capture = OSError("capture failure")
    with active(value):
        stage._guard(value)
        if drift == "inactive":
            value.active = False
        elif drift == "invalid":
            value.invalid = True
        elif drift == "thread":
            value.thread = -1
        elif drift == "stack":
            stage._ACTIVE.append(context())
        elif drift == "entry":
            value.entry_error = entry
        elif drift == "capture":
            value.observation_error = capture
        elif drift == "hooks":
            value.observing = True
            value.observer_hooks = (object(), object())
        try:
            if drift == "none":
                stage._guard(value)
            elif drift == "entry":
                with pytest.raises(RuntimeError) as caught:
                    stage._guard(value)
                assert caught.value is entry
            else:
                with pytest.raises(stage.ProfilesRejected) as caught:
                    stage._guard(value)
                if drift == "capture":
                    assert caught.value.__cause__ is capture
                if drift in ("invalid", "thread", "hooks"):
                    with pytest.raises(stage.ProfilesRejected) as again:
                        stage._guard(value)
                    assert again.value is value.entry_error
        finally:
            if drift == "stack":
                stage._ACTIVE.pop()
    assert not stage._ISSUED


def test_raw_return_is_retained_before_fallible_observation_and_not_double_counted():
    value, frame, returned = context(), object(), object()
    stage._raw(value, "synthetic-return", frame, returned)
    stage._raw(value, "synthetic-return", frame, returned)
    assert len(value.raw_returns) == 1
    assert value.last_raw == ("synthetic-return", frame, returned)


@pytest.mark.parametrize("unwind", [False, True])
def test_actual_profile_distinguishes_normal_none_and_exception_unwind(unwind):
    primary, cause = RuntimeError("original synthetic failure"), LookupError("cause")
    primary.__cause__ = cause

    def probe():
        if unwind:
            raise primary
        return None

    rows = []
    old = sys.getprofile()

    def profile(frame, event, arg):
        if frame.f_code is probe.__code__ and event == "return":
            rows.append((arg, stage._normal_return(frame)))

    sys.setprofile(profile)
    try:
        if unwind:
            with pytest.raises(RuntimeError) as caught:
                probe()
            assert caught.value is primary and caught.value.__cause__ is cause
        else:
            assert probe() is None
    finally:
        sys.setprofile(old)
    assert rows == [(None, not unwind)]


@pytest.mark.parametrize("returned", [None, (1, 2)])
def test_direct_return_witness_precedes_observer_locals_failure(returned):
    def probe():
        return None

    def other():
        return None

    value = context()
    value.methods = dict(init_profiles=probe, continue_seed=other)
    value.callback_chain = (other,)
    value.pick_code = other.__code__
    frame = NS(f_code=probe.__code__, f_locals={})
    secondary = OSError("synthetic locals capture")

    def fail_copy(*args, **kwargs):
        raise secondary

    observe = clone(stage._observe, dict=fail_copy)
    with pytest.raises(OSError) as caught:
        observe(value, frame, "return", returned)
    assert caught.value is secondary
    assert value.last_raw[1] is frame and value.last_raw[2] is returned
    assert value.raw_returns == [value.last_raw]


@pytest.mark.parametrize("route", ["valid", "foreign_forwarder", "direct_body"])
def test_real_local_dispatch_chain_authenticates_forwarder_and_immediate_body_caller(
    route, tmp_path
):
    value, owner, phase, returned = context(), object(), object(), object()
    entered = []

    def body(actual, actual_phase):
        entered.append((actual, actual_phase))
        return returned

    def other():
        return None

    def metadata_check(context):
        # Only frame admission is selected; this supplies no phase authority.
        return None

    def metadata_bindings(context):
        return ()

    observe = clone(stage._observe, _check=metadata_check, _bindings=metadata_bindings)
    dispatch = clone(stage._dispatch, _check=metadata_check)
    account = contextmanager(clone(stage._account.__wrapped__, _observe=observe))
    value.methods = dict(init_profiles=body, continue_seed=other)
    value.callback_chain = (other,)
    value.source_codes = frozenset((body.__code__,))
    value.allowed_codes = frozenset()
    value.bindings = ()
    value.dyna_origin, value.dyna, value.phase = owner, owner, phase
    value.delegate = body
    value.forwarding_frame = value.dispatch_frame = value.body_frame = None
    value.environment_store_line = -1
    value.body_returned = False

    def forward():
        frame = sys._getframe()
        if route == "foreign_forwarder":
            frame = NS(f_back=value.wrapper_frame)
        return dispatch(value, owner, "init_profiles", body, owner, (phase,), {}, frame)

    def wrapper():
        value.wrapper_frame = sys._getframe()
        if route == "direct_body":
            return body(owner, phase)
        return forward()

    with active(value):
        if route == "valid":
            with account(value):
                assert wrapper() is returned
        else:
            with pytest.raises(stage.ProfilesRejected) as caught:
                with account(value):
                    wrapper()
            assert caught.value is value.entry_error
    if route == "valid":
        assert entered == [(owner, phase)] and value.body_returned
        assert value.body_frame.f_back is value.dispatch_frame
        assert value.dispatch_frame.f_back is value.forwarding_frame
        assert value.forwarding_frame.f_code is forward.__code__
        assert value.forwarding_frame.f_back is value.wrapper_frame
        assert value.body_return is returned
    else:
        assert entered == [] and value.invalid
    assert value.hooks_safe and not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "dispatch-chain.json",
        dict(
            route=route,
            delegate_entries=len(entered),
            exact_local_chain=route == "valid",
            issued_phase_or_profile_owner=False,
        ),
    )


@pytest.mark.parametrize("unwind", [False, True])
@pytest.mark.parametrize("returned", [None, (1, 2)])
def test_installed_helper_unwind_keeps_primary_and_raw_before_history_append_failure(
    unwind, returned, tmp_path
):
    value = context()
    primary, cause = RuntimeError("original helper failure"), LookupError("helper cause")
    primary.__cause__ = cause
    secondary = OSError("return history append failed")

    class FailedHistory(list):
        def append(self, row):
            raise secondary

    def helper():
        if unwind:
            raise primary
        return returned

    def metadata_observer(context, frame, event, arg):
        return None

    value.raw_returns = FailedHistory()
    value.source_codes = frozenset()
    value.allowed_codes = frozenset((helper.__code__,))
    account = contextmanager(clone(stage._account.__wrapped__, _observe=metadata_observer))
    with pytest.raises(RuntimeError if unwind else OSError) as caught:
        with account(value):
            helper()
    assert caught.value is (primary if unwind else secondary)
    assert value.primary is (primary if unwind else None)
    if unwind:
        assert caught.value.__cause__ is cause
    assert value.last_raw[1].f_code is helper.__code__
    assert value.last_raw[2] is (None if unwind else returned)
    assert value.last_raw_history[1] is value.last_raw[1]
    assert value.raw_returns == []
    assert value.observation_error is secondary
    assert any(
        row[0] == "raw_return_history" and row[1] is secondary for row in value.capture_errors
    )
    assert value.hooks_safe and not stage._ISSUED
    software.snapshot.write_json(
        tmp_path / "raw-unwind.json",
        dict(
            unwind=unwind,
            primary_identity_preserved=caught.value is primary if unwind else None,
            cause_identity_preserved=caught.value.__cause__ is cause if unwind else None,
            direct_return_witness=True,
            history_complete=False,
            original_return_kind="none" if returned is None else "tuple",
            cleanup_safe=value.hooks_safe,
        ),
    )


@pytest.mark.parametrize("layer", ["profile", "trace"])
@pytest.mark.parametrize("unwind", [False, True])
def test_restore_helper_entry_rejection_keeps_primary_and_independently_recovers_both_hooks(
    layer, unwind, tmp_path
):
    before = (sys.getprofile(), sys.gettrace())
    primary, cause = RuntimeError("source before cleanup"), LookupError("source cause")
    primary.__cause__ = cause
    secondary = OSError("inherited rejection of restore entry")
    rejections, attempts = [], []

    def helper():
        if unwind:
            raise primary
        return None

    def prior_profile(frame, event, arg):
        if frame.f_code is stage._restore.__code__ and event == "call":
            rejections.append((layer, frame))
            raise secondary
        if before[0] is not None:
            before[0](frame, event, arg)

    def prior_trace(frame, event, arg):
        if frame.f_code is stage._restore.__code__ and event == "call":
            rejections.append((layer, frame))
            raise secondary
        if before[1] is not None:
            before[1](frame, event, arg)
        return prior_trace

    def metadata_observer(context, frame, event, arg):
        return None

    if layer == "profile":
        sys.setprofile(prior_profile)
    else:
        sys.settrace(prior_trace)
    value = context()
    value.source_codes = frozenset((helper.__code__,))
    value.allowed_codes = frozenset()

    def set_profile(hook):
        attempts.append((0, hook))
        sys.setprofile(hook)

    def set_trace(hook):
        attempts.append((1, hook))
        sys.settrace(hook)

    value.restore_setters = (set_profile, set_trace)
    account = contextmanager(clone(stage._account.__wrapped__, _observe=metadata_observer))
    try:
        if unwind:
            with pytest.raises(RuntimeError) as caught:
                with account(value):
                    helper()
            assert caught.value is primary and caught.value.__cause__ is cause
            assert value.primary is primary
        else:
            with account(value):
                helper()
        assert len(rejections) == 1
        assert any(
            row[0] == "restore_entry_or_return" and row[1] is secondary
            for row in value.cleanup_errors
        )
        assert value.observation_error is secondary
        assert any(index == 0 and hook is value.required_hooks[0] for index, hook in attempts)
        assert any(index == 1 and hook is value.required_hooks[1] for index, hook in attempts)
        assert value.final_hook_samples == (value.required_hooks, value.required_hooks)
        assert value.hooks_safe and not stage._ISSUED
        assert sys.getprofile() is value.required_hooks[0]
        assert sys.gettrace() is value.required_hooks[1]
        software.snapshot.write_json(
            tmp_path / "helper-entry-cleanup.json",
            dict(
                layer=layer,
                unwind=unwind,
                actual_entry_rejections=len(rejections),
                original_primary_and_cause_preserved=unwind,
                independent_profile_attempt=True,
                independent_trace_attempt=True,
                both_final_samples_match=True,
                child_admitted=False,
            ),
        )
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("unwind", [False, True])
def test_installed_observer_keeps_source_cause_and_recovers_both_hooks(hook, unwind):
    primary, cause = RuntimeError("synthetic source failure"), LookupError("original cause")
    primary.__cause__ = cause
    secondary = OSError("secondary return capture")

    def probe():
        if unwind:
            raise primary
        return None

    before = (sys.getprofile(), sys.gettrace())

    def prior_profile(frame, event, arg):
        if frame.f_code is probe.__code__ and event == "return":
            raise secondary
        if before[0] is not None:
            before[0](frame, event, arg)

    def prior_trace(frame, event, arg):
        if frame.f_code is probe.__code__ and event == "return":
            raise secondary
        if before[1] is not None:
            before[1](frame, event, arg)
        return prior_trace

    if hook == "profile":
        sys.setprofile(prior_profile)
    else:
        sys.settrace(prior_trace)
    value = context()
    value.source_codes = value.allowed_codes = frozenset((probe.__code__,))

    def metadata_observer(context, frame, event, arg):
        # The installed production observer's failure/lifetime contract is
        # tested on local functions; there is no actual phase/body dispatch.
        return None

    account = contextmanager(clone(stage._account.__wrapped__, _observe=metadata_observer))
    try:
        if unwind:
            with pytest.raises(RuntimeError) as caught:
                with account(value):
                    probe()
            assert caught.value is primary and caught.value.__cause__ is cause
            assert value.primary is primary
        elif hook == "trace":
            with pytest.raises(OSError) as caught:
                with account(value):
                    probe()
            assert caught.value is secondary
        else:
            with account(value):
                probe()
        assert value.observation_error is secondary
        assert value.raw_returns and value.raw_returns[0][2] is None
        assert sys.getprofile() is value.required_hooks[0]
        assert sys.gettrace() is value.required_hooks[1]
        assert len(value.final_hook_samples) == 2
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])


def test_secondary_attachment_failure_does_not_replace_original_primary():
    class NoAttachment(RuntimeError):
        def __setattr__(self, name, value):
            if name == "seed_init_profiles_partial":
                raise OSError("secondary attachment error")
            return super().__setattr__(name, value)

    primary, cause = NoAttachment("original"), LookupError("cause")
    primary.__cause__ = cause
    value = context()
    value.primary = primary
    value.phase = value.dyna = value.sim = value.p = value.cells = object()
    with pytest.raises(NoAttachment) as caught:
        stage._failure(value, OSError("secondary interruption"))
    assert caught.value is primary and caught.value.__cause__ is cause
    assert value.partial["primary"] is primary and value in stage._FAILED
    assert any(row[0] == "exception_attachment" for row in value.capture_errors)


def _synthetic_registry():
    """Metadata association probe only; it is never an issued parent/phase."""

    class Item:
        pass

    class Profile:
        pass

    class Picker:
        pass

    handler, p, phase = Item(), Item(), Item()
    picker1, picker2 = Picker(), Picker()
    profile1, profile2 = Profile(), Profile()
    profile1.picker, profile2.picker = picker1, picker2
    table = OrderedDict((("first", profile1), ("second", profile2)))
    handler.tissue_name_to_profile = table
    origin = NS(
        handler=handler,
        phase=phase,
        p=p,
        constructor_completed=True,
        objects=[("TissuePickerIndices", picker1), ("TissuePickerIndices", picker2)],
        runtime_types=dict(TissueProfile=Profile, TissuePickerIndices=Picker),
        factories=dict(TissueProfile=object(), TissuePickerIndices=object()),
    )
    module = NS(
        _OBJECTS={x: origin for x in (handler, profile1, profile2, picker1, picker2)},
        _surface=stage.previous._LITERAL._surface,
    )
    return NS(
        dyna=handler,
        phase=phase,
        p=p,
        dyna_origin=origin,
        dyna_module=module,
        profiles=tuple(table.items()),
    )


@pytest.mark.parametrize(
    "drift", ["none", "reorder", "table-copy", "origin", "class", "picker-registry"]
)
def test_registry_metadata_retains_exact_original_context_class_and_profile_order(drift):
    value = _synthetic_registry()
    original = stage._profile_bindings(value)
    profile = value.profiles[0][1]
    if drift == "reorder":
        value.dyna.tissue_name_to_profile = OrderedDict(reversed(value.profiles))
    elif drift == "table-copy":
        value.dyna.tissue_name_to_profile = OrderedDict(value.profiles)
    elif drift == "origin":
        value.dyna_module._OBJECTS[profile] = copy.copy(value.dyna_origin)
    elif drift == "class":
        old = type(profile)
        replacement = type(old.__name__, old.__bases__, {})
        replacement.__module__ = old.__module__
        profile.__class__ = replacement
    elif drift == "picker-registry":
        value.dyna_module._OBJECTS.pop(profile.picker)
    if drift == "none":
        stage._same_bindings(stage._profile_bindings(value), original)
    else:
        with pytest.raises(ValueError):
            stage._same_bindings(stage._profile_bindings(value), original)
    assert not stage._ISSUED


@pytest.mark.parametrize("value", [None, 0, False, "foreign", {}])
def test_unknown_authority_is_refused_without_native_dispatch(value):
    with pytest.raises(stage.ProfilesRejected) as caught:
        stage._authority(value)
    assert caught.value.stage == "owner" and not stage._ISSUED


@pytest.mark.parametrize(
    "drift",
    [
        "none",
        "copy-cells",
        "copy-mems",
        "omit-empty",
        "reorder",
        "wrong-profile",
        "environment-empty",
        "environment-copy",
        "duplicate-return",
    ],
)
def test_local_target_contract_preserves_duplicates_empty_profiles_and_exact_return_aliases(drift):
    # These are local metadata roots, never actual core, phase or profile owners.
    one, two = NS(picker=object()), NS(picker=object())
    cells1, mems1 = np.array([1, 1]), np.array([3, 3])
    cells2, mems2 = np.array([], dtype=int), np.array([], dtype=int)
    environment = [4, 4]
    handler = NS(tissue_name_to_profile=OrderedDict((("one", one), ("two", two))))
    handler.cell_target_inds = dict(one=cells1, two=cells2)
    handler.env_target_inds = dict(one=environment)
    handler.tissue_target_inds = dict(one=mems1, two=mems2)
    value = NS(
        dyna=handler,
        p=NS(is_ecm=True),
        profiles=(("one", one), ("two", two)),
        original_names=("tissue_name_to_profile",),
        picks=[("one", one, one.picker, cells1, mems1), ("two", two, two.picker, cells2, mems2)],
        environment_returns=[("one", one, environment)],
        callback_completed=True,
        body_returned=True,
        body_return=None,
        primary=None,
        invalid=False,
        observation_error=None,
        entry_error=None,
        cleanup_errors=(),
    )
    stage._complete(value)
    if drift == "copy-cells":
        handler.cell_target_inds["one"] = cells1.copy()
    elif drift == "copy-mems":
        handler.tissue_target_inds["one"] = mems1.copy()
    elif drift == "omit-empty":
        handler.cell_target_inds.pop("two")
    elif drift == "reorder":
        handler.cell_target_inds = dict(reversed(tuple(handler.cell_target_inds.items())))
    elif drift == "wrong-profile":
        value.picks[0] = ("one", two, one.picker, cells1, mems1)
    elif drift == "environment-empty":
        handler.env_target_inds["two"] = []
    elif drift == "environment-copy":
        handler.env_target_inds["one"] = list(environment)
    elif drift == "duplicate-return":
        value.picks.append(value.picks[0])
    if drift == "none":
        stage._complete(value)
        assert list(handler.cell_target_inds["one"]) == [1, 1]
        assert list(handler.tissue_target_inds["one"]) == [3, 3]
        assert handler.cell_target_inds["two"] is cells2 and len(cells2) == 0
    else:
        with pytest.raises(ValueError):
            stage._complete(value)
    assert not stage._ISSUED


@pytest.mark.parametrize(
    "drift",
    [
        "none",
        "shadow-builtin",
        "cached-builtins",
        "wrapped-outer",
        "foreign-globals",
        "typed-constant",
        "signature",
        "callable-object",
    ],
)
def test_no_call_helper_guard_binds_outer_code_reached_names_and_exact_cached_builtins(
    monkeypatch, drift
):
    # This module/compiled code is a metadata comparison input only. No function
    # body runs and no actual module/file/constructor authority is manufactured.
    filename = "closed_guard_probe.py"
    tree = ast.parse("def probe():\n    return len((3, 4))\n")
    module = ModuleType("closed_guard_probe")
    module.__file__ = str(stage.NATIVE / filename)
    module.__dict__["__builtins__"] = vars(builtins)
    code = stage._compile(tree.body[0], module.__file__)
    original = FunctionType(code, vars(module), "probe")
    function = original
    if drift == "shadow-builtin":
        module.len = lambda value: 0
    elif drift == "cached-builtins":
        module.__dict__["__builtins__"] = dict(vars(builtins))
        function = FunctionType(code, vars(module), "probe")
        module.__dict__["__builtins__"] = vars(builtins)
    elif drift == "wrapped-outer":
        other_code = compile("def probe():\n    return None\n", module.__file__, "exec")
        function = FunctionType(
            next(c for c in other_code.co_consts if type(c) is CodeType), vars(module)
        )
        function.__wrapped__ = original
    elif drift == "foreign-globals":
        function = FunctionType(code, dict(vars(module)), "probe")
    elif drift == "typed-constant":
        values = list(code.co_consts)
        index = next(i for i, v in enumerate(values) if type(v) is tuple)
        assert values[index] == (complex(3, 0), 4)  # Obsolete plain equality would merge these.
        values[index] = (complex(3, 0), 4)
        function = FunctionType(code.replace(co_consts=tuple(values)), vars(module), "probe")
    elif drift == "signature":
        function.__defaults__ = (None,)
    elif drift == "callable-object":

        class Uninspected:
            def __getattribute__(self, name):
                raise AssertionError("Foreign callable metadata must not be read")

        function = Uninspected()
    module.probe = function
    monkeypatch.setitem(sys.modules, module.__name__, module)
    native = clone(stage._native, _trees=lambda: {filename: tree})
    if drift == "none":
        assert native(function, filename, None, "probe") == (original, (original,))
    else:
        with pytest.raises(ValueError):
            native(function, filename, None, "probe")
    assert not stage._ISSUED


@pytest.mark.parametrize(
    "drift", ["none", "empty", "copy", "offset", "stride", "self", "inactive", "undeclared"]
)
def test_percent_view_metadata_keeps_actual_storage_without_inserting_a_copy(drift):
    root = np.arange(0 if drift == "empty" else 6)
    view = root[:]
    value = NS(cell_i=root, percent_declared=True, percent_active=True, parent=NS(numpy=np))
    if drift == "copy":
        view = root.copy()
    elif drift == "offset":
        view = root[1:]
    elif drift == "stride":
        view = root[::-1]
    elif drift == "self":
        view = root
    elif drift == "inactive":
        value.percent_active = False
    elif drift == "undeclared":
        value.percent_declared = False
    if drift in ("none", "empty"):
        assert stage._accept_percent_view(value, view) is None
        assert view.base is root and value.cell_i is root
    else:
        with pytest.raises(ValueError):
            stage._accept_percent_view(value, view)
    assert not stage._ISSUED


def test_shuffle_export_owner_metadata_is_inspected_without_invocation():
    from types import MethodType

    assert type(_ORIGINAL_SHUFFLE) is MethodType
    assert _ORIGINAL_SHUFFLE.__self__ is np.random.mtrand._rand
    assert _ORIGINAL_SHUFFLE.__name__ == "shuffle"
    assert vars(np.random.mtrand)["shuffle"] is _ORIGINAL_SHUFFLE
    assert _ORIGINAL_SHUFFLE.__func__ is vars(type(np.random.mtrand._rand))["shuffle"]
    assert _ORIGINAL_SHUFFLE.__func__.__code__.co_filename == "numpy/random/mtrand.pyx"


@pytest.mark.parametrize("ignored", [0, 1])
def test_observer_setup_requires_both_installed_hooks_before_any_delegate(ignored):
    value = context()
    value.source_codes = value.allowed_codes = frozenset()
    setters = list(value.restore_setters)
    setters[ignored] = lambda hook: None
    value.restore_setters = tuple(setters)
    account = contextmanager(clone(stage._account.__wrapped__, _observe=lambda *args: None))
    entered = []
    with pytest.raises(stage.ProfilesRejected, match="Both original hooks"):
        with account(value):
            entered.append(True)
    assert entered == []
    assert sys.getprofile() is value.required_hooks[0]
    assert sys.gettrace() is value.required_hooks[1]


@pytest.mark.parametrize(
    "drift", ["none", "missing", "foreign", "dict", "duplicate", "mutated", "unissued"]
)
def test_image_byte_authority_requires_actual_issued_file_and_exact_selected_filename(
    tmp_path, drift
):
    path = tmp_path / "source-bytes.png"
    path.write_bytes(b"synthetic file metadata only; never parsed or decoded")
    path.chmod(0o444)
    source = stage.files.input_file(
        path,
        sha256=software.snapshot.digest(path),
        origin="Software byte-authority control, no image loaded",
    )
    inputs = (source,)
    selected = (("TissuePickerImage", NS(filename=str(path))),)
    if drift == "missing":
        inputs = ()
    elif drift == "foreign":
        selected = (("TissuePickerImage", NS(filename=str(path.with_name("elsewhere.png")))),)
    elif drift == "dict":
        inputs = (dict(filename=str(path)),)
    elif drift == "duplicate":
        inputs = (source, source)
    elif drift == "mutated":
        path.chmod(0o644)
        path.write_bytes(b"changed")
        path.chmod(0o444)
    elif drift == "unissued":
        inputs = (
            stage.files.FileInput(
                source.filename, source.sha256, source.origin, source.stat, source.identity
            ),
        )
    if drift == "none":
        assert stage._image_authority(inputs, selected) is None
    else:
        with pytest.raises(ValueError):
            stage._image_authority(inputs, selected)
    assert not stage._ISSUED
