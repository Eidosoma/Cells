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
        events=[],
        work=[],
        locals={},
        picks=[],
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
