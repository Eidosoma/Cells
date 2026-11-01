"""Issued synthetic parents; every actual native constructor/import is held."""

import builtins
import json
import sys
from contextlib import contextmanager
from enum import Enum
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_phase_assembly as stage
from tests.unit import test_betse_native_parameter_subconfigurations as parameters
from tests.unit import test_betse_native_phase_callbacks as callback_inputs
from validation.betse.betse_native_single_cell_core_synthetic import save


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    old, trace, imp = sys.getprofile(), sys.gettrace(), builtins.__import__
    attempts = []
    codes = {
        stage._acquire.__code__,
        stage._PREFIX.__code__,
        stage._import_native.__code__,
        stage.previous._load.__code__,
        stage.previous.paths._upgrade.__code__,
        stage.previous.paths._reload.__code__,
        stage.callbacks._acquire.__code__,
        stage.previous.paths.prefix.parameters._acquire.__code__,
        stage.previous.paths.prefix.parameters._invoke.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native/source constructor work forbidden")
        if old is not None:
            old(frame, event, arg)

    def imported(name, *a, **k):
        if name == "betse" or name.startswith(("betse.", "ruamel")):
            attempts.append(name)
            raise AssertionError("Actual native import forbidden")
        return imp(name, *a, **k)

    def rng(*a, **k):
        attempts.append("RNG")
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imported)
    for name in ("RandomState", "default_rng", "seed", "random", "normal", "uniform", "choice"):
        monkeypatch.setattr(stage.literal.callers.np.random, name, rng)
    sys.setprofile(profile)
    try:
        yield
        assert attempts == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempts,
                    actual_source_or_scientific_credit=0,
                )
            )
        )


@pytest.fixture(scope="module")
def plans():
    return stage.previous.source_plan(), stage.callbacks.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plans):
    p = parameters.controlled.__wrapped__(monkeypatch, tmp_path, plans[0])
    cb = callback_inputs.controlled.__wrapped__(monkeypatch, plans[1])
    parent = parameters.run(p)
    callback = callback_inputs.prepare(cb)
    log, hooks = [], {}

    class Kind(Enum):
        SEED = 1

    class Phase:
        def __init__(self, *a, **k):
            raise AssertionError("Full phase constructor forbidden")

        def _init_kludge(self):
            raise AssertionError("Native kludge forbidden")

        @property
        def is_sim(self):
            raise AssertionError("Native phase getter forbidden")

    class Cells:
        def __init__(self, *, p):
            log.append(("Cells", self, p))
            self.actual_argument = p
            if "Cells" in hooks:
                hooks["Cells"]()

        def make_world(self, *a):
            raise AssertionError("Native world forbidden")

    class Simulator:
        def __init__(self):
            log.append(("Simulator", self))
            if "Simulator" in hooks:
                hooks["Simulator"]()

        def init_core(self, *a):
            raise AssertionError("Native core forbidden")

    modules = {name: NS() for name in stage.IMPORTS}

    def acquire(context):
        context.factories = dict(SimPhase=Phase, Cells=Cells, Simulator=Simulator)
        context.kind = Kind.SEED
        context.modules = {}
        context.import_modules = modules

    def imported(name, *a):
        return modules[name]

    space = {}
    exec(
        compile(
            """
def construct(self,kind,p,cells=None,sim=None,callbacks=None):
    from betse.science.cells import Cells
    from betse.science.math.cache.cacheabc import SimPhaseCaches
    from betse.science.sim import Simulator
    from betse.science.tissue.tishandler import TissueHandler
    if callbacks is None:raise AssertionError('No supplied callback authority')
    if cells is None:cells=Cells(p=p)
    if sim is None:sim=Simulator()
    self.callbacks=callbacks
    self.cells=cells
    self.kind=kind
    self.p=p
    self.sim=sim
""",
            "<synthetic-phase-prefix>",
            "exec",
        ),
        space,
    )
    monkeypatch.setattr(stage, "_PREFIX", space["construct"])
    monkeypatch.setattr(stage, "_acquire", acquire)
    monkeypatch.setattr(stage, "_import_native", imported)
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setenv(stage.claims.RELEASE, "1")
    req = stage.from_owners(parent, callback, law_id=stage.LAW_ID, mode=stage.MODE)
    return NS(
        parameter=p,
        callback=cb,
        parameter_owner=parent,
        callback_owner=callback,
        request=req,
        log=log,
        hooks=hooks,
        classes=dict(phase=Phase, cells=Cells, sim=Simulator),
        kind=Kind.SEED,
    )


@pytest.fixture
def refused(tmp_path):
    @contextmanager
    def check():
        with pytest.raises(stage.AssemblyRejected) as caught:
            yield caught
        e = caught.value
        part = e.partial if type(e.partial) is dict else {}
        save(
            tmp_path,
            "refusal",
            dict(
                stage=e.stage,
                source=e.source_error,
                capture=e.capture_error,
                cause=e.__cause__,
                trial=e.trial,
                objects=part.get("objects"),
                imports=part.get("imports"),
                attempts=part.get("attempts"),
                returns=part.get("returns"),
            ),
        )

    return check


def test_literal_source_prefix_stops_before_cache_dyna_and_kludge():
    plan = stage.source_plan()
    assert plan["fields"] == stage.FIELDS and plan["source_lines"] == [142, 160]
    assert plan["constructor_order"] == ("Cells(p)", "Simulator()")
    assert plan["stopped_before"] == ("SimPhaseCaches", "TissueHandler", "_init_kludge")
    assert not plan["complete_phase_or_world_or_physical_or_checkpoint_admitted"]


def test_genuine_api_parents_new_objects_same_parameter_and_source_order(controlled, tmp_path):
    h = controlled
    p = h.parameter.p
    before = tuple(vars(p).items())
    owner = stage.prepare(h.request, enabled=True)
    phase = owner.partial_phase
    assert isinstance(phase, h.classes["phase"])
    assert phase.p is p and phase.callbacks is h.callback_owner.callback
    assert isinstance(phase.cells, h.classes["cells"]) and phase.cells.actual_argument is p
    assert (
        isinstance(phase.sim, h.classes["sim"])
        and phase.sim is not h.callback.source_parent.instance
    )
    assert h.log[0][0] == "Cells" and h.log[0][2] is p and h.log[1][0] == "Simulator"
    assert tuple(vars(phase)) == stage.FIELDS and tuple(vars(p).items()) == before
    assert owner.trial.prefix_completed and owner.trial.constructor_returns == (
        "Cells",
        "Simulator",
    )
    save(tmp_path, "trial", owner.trial)


@pytest.mark.parametrize("enabled,flag", [(False, "1"), (True, "0"), (1, "1")])
def test_release_precedes_parent_or_native_entry(monkeypatch, refused, enabled, flag):
    monkeypatch.setenv(stage.RELEASE, flag)
    with refused() as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


@pytest.mark.parametrize("role", ["Cells", "Simulator"])
def test_original_constructor_failure_keeps_partial_actual_objects(controlled, refused, role):
    h = controlled
    primary, cause = ValueError("original constructor"), KeyError("source cause")

    def fail():
        raise primary from cause

    h.hooks[role] = fail
    with refused() as caught:
        stage.prepare(h.request, enabled=True)
    e = caught.value
    assert e.source_error is primary and e.__cause__ is primary and primary.__cause__ is cause
    assert e.partial["parameters"] is h.parameter.p and not e.partial["usable_child_available"]
    assert [r[0] for r in h.log] == (["Cells"] if role == "Cells" else ["Cells", "Simulator"])


@pytest.mark.parametrize(
    "role,method",
    [
        ("phase", "_init_kludge"),
        ("cells", "make_world"),
        ("sim", "init_core"),
        ("phase", "__init__"),
    ],
)
def test_raw_unfinished_native_surface_refuses_before_body(controlled, refused, role, method):
    phase = stage.prepare(controlled.request, enabled=True).partial_phase
    obj = {"phase": phase, "cells": phase.cells, "sim": phase.sim}[role]
    with refused():
        getattr(obj, method)()


@pytest.mark.parametrize("field", ["p", "cells", "sim", "callbacks"])
def test_equal_looking_object_retarget_refuses_completed_prefix(controlled, refused, field):
    owner = stage.prepare(controlled.request, enabled=True)
    phase = owner.partial_phase
    old = getattr(phase, field)
    setattr(phase, field, NS(**vars(old)))
    with refused() as caught:
        _ = owner.partial_phase
    assert caught.value.stage == "owner_drift"


def test_shared_numeric_advance_conflict_poisoned_before_delegate(controlled, refused):
    h = controlled
    called = []

    def advance():
        with stage.claims._advance(h.parameter_owner):
            called.append(True)

    h.hooks["Cells"] = advance
    with refused():
        stage.prepare(h.request, enabled=True)
    assert called == [] and len(h.log) == 1


def test_complete_phase_admission_remains_explicitly_unavailable(controlled, refused):
    owner = stage.prepare(controlled.request, enabled=True)
    with refused() as caught:
        stage.require_phase(owner)
    assert caught.value.stage == "phase_incomplete"


def test_source_observation_capture_failure_has_no_child(controlled, monkeypatch, refused):
    h = controlled
    original = stage._namespace
    error = OSError("raw constructor return capture")

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, value):
                if value[0] == "Cells.__init___return":
                    raise error
                super().append(value)

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    old, trace = sys.getprofile(), sys.gettrace()
    with refused() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.capture_error is error and caught.value.source_error is None
    assert [r[0] for r in h.log] == ["Cells"]
    assert sys.getprofile() is old and sys.gettrace() is trace


@pytest.mark.parametrize("parent", ["parameters", "callback"])
def test_receipts_or_unissued_objects_never_supply_live_parents(controlled, parent):
    h = controlled
    params = h.parameter_owner if parent != "parameters" else NS()
    callback = h.callback_owner if parent != "callback" else NS()
    with pytest.raises(
        (stage.previous.SubconfigurationsRejected, stage.callbacks.CallbackRejected)
    ):
        stage.from_owners(params, callback, law_id=stage.LAW_ID, mode=stage.MODE)


def test_default_callback_or_relabelled_mode_is_not_this_source_route(controlled, refused):
    h = controlled
    with refused() as caught:
        stage.from_owners(
            h.parameter_owner, h.callback_owner, law_id=stage.LAW_ID, mode="default_callbacks"
        )
    assert caught.value.stage == "law" and h.log == []


@pytest.mark.parametrize(
    "link", ["parameter_issuance", "callback_issuance", "construction", "raw_object"]
)
def test_inherited_and_new_issuance_links_remain_required(controlled, refused, link):
    h = controlled
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner]
    before = stage._snapshot(context).identity
    if link == "parameter_issuance":
        stage.previous._ISSUED.pop(h.parameter_owner)
    elif link == "callback_issuance":
        stage.callbacks._ISSUED.pop(h.callback_owner)
    elif link == "construction":
        stage.claims._CONSTRUCTED.pop(h.parameter_owner)
    else:
        stage._OBJECTS.pop(context.constructed["Cells"])
    assert stage._snapshot(context).identity == before
    with refused() as caught:
        _ = owner.partial_phase
    assert caught.value.stage == "owner_drift"


def test_direct_native_property_also_refuses_outside_source_entry(controlled, refused):
    phase = stage.prepare(controlled.request, enabled=True).partial_phase
    with refused():
        _ = phase.is_sim


def test_attempt_is_not_rearmed_after_success(controlled, refused):
    h = controlled
    stage.prepare(h.request, enabled=True)
    with refused() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.stage == "consumed"


def test_reentrant_attempt_cannot_be_swallowed_into_success(controlled, refused):
    h = controlled
    errors = []

    def again():
        try:
            stage.prepare(h.request, enabled=True)
        except stage.AssemblyRejected as e:
            errors.append(e)

    h.hooks["Cells"] = again
    with refused():
        stage.prepare(h.request, enabled=True)
    assert errors[0].stage == "reentrant" and [r[0] for r in h.log] == ["Cells"]


def test_secondary_sealing_error_keeps_original_constructor_cause(controlled, monkeypatch, refused):
    h = controlled
    primary, cause, capture = RuntimeError("constructor"), LookupError("cause"), OSError("cache")

    def failed():
        raise primary from cause

    def snapshot(context):
        raise capture

    h.hooks["Simulator"] = failed
    monkeypatch.setattr(stage, "_snapshot", snapshot)
    with refused() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.source_error is primary and caught.value.capture_error is capture
    assert caught.value.__cause__ is primary and primary.__cause__ is cause
    assert len(caught.value.partial["objects"]) == 3


def test_source_capture_stop_class_is_not_misclassified_as_observation(controlled, refused):
    primary = stage.literal._CaptureStop("actual synthetic source exception")

    def failed():
        raise primary

    controlled.hooks["Cells"] = failed
    with refused() as caught:
        stage.prepare(controlled.request, enabled=True)
    assert caught.value.source_error is primary and caught.value.capture_error is None
