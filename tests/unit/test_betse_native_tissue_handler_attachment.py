"""Same-p handler controls on issued synthetic seven-load API parents."""

import sys
from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_tissue_handler_attachment as stage
from tests.unit import test_betse_native_parameter_subconfigurations as parents
from validation.betse.betse_native_single_cell_core_synthetic import save

plan = parents.plan
controlled = parents.controlled
blocked = parents.blocked


@pytest.fixture
def evidence(request, tmp_path):
    return tmp_path


@pytest.fixture
def rejected(evidence):
    count = 0

    @contextmanager
    def check(error_type=stage.AttachmentRejected):
        nonlocal count
        with pytest.raises(error_type) as caught:
            yield caught
        error = caught.value
        partial = getattr(error, "partial", None)
        partial = partial if type(partial) is dict else {}
        save(
            evidence,
            "refusal-" + str(count),
            dict(
                stage=getattr(error, "stage", None),
                exception_type=type(error).__name__,
                primary=getattr(error, "source_error", None),
                capture=getattr(error, "capture_error", None),
                cause=error.__cause__,
                trial=getattr(error, "trial", None),
                request_identity=getattr(getattr(error, "request", None), "identity", None),
                partial={
                    key: partial.get(key)
                    for key in (
                        "parameters",
                        "handler",
                        "parent_trial",
                        "last_completed",
                        "objects",
                        "events",
                        "work",
                        "stages",
                        "observation_errors",
                        "request_consumed",
                    )
                },
            ),
        )
        count += 1

    return check


@pytest.fixture
def attached(monkeypatch, controlled):
    h = controlled
    calls, hooks = [], {}

    class Factory:
        def __init__(self, *args, **kwargs):
            calls.append("factory")
            if "factory" in hooks:
                hooks["factory"]()
            self.arguments = args
            self.fields = kwargs

    def acquire(context):
        context.factories = {name: Factory for name in stage.literal._FACTORY_MODULES}
        context.symbols = {}

    namespace = {}
    exec(
        compile(
            """
def __init__(self,p):
    point('__init__',self,p)
    self.event_cut=None
    self._event_voltage=None
    self._init_tissues(p)
    self._init_cuts(p)
    self._init_events(p)
def _init_tissues(self,p):
    point('_init_tissues',self,p)
    self.tissue_default=TissueProfile(name=p.tissue_default._conf['name'])
    self.raw_default=p.tissue_default._conf
def _init_cuts(self,p):
    point('_init_cuts',self,p)
    if missing_cut_store:p.event_cut_profile_names
    self.cut_name_to_profile={}
def _init_events(self,p):
    point('_init_events',self,p)
    self._init_events_global(p)
def _init_events_global(self,p):
    point('_init_events_global',self,p)
""",
            "<synthetic-selected-handler>",
            "exec",
        ),
        namespace,
    )

    def point(name, actual, p):
        assert p is h.p
        calls.append(name)
        if name in hooks:
            hooks[name]()

    namespace.update(point=point, missing_cut_store=False)
    monkeypatch.setattr(stage, "_NATIVE", {n: namespace[n] for n in stage.METHODS})
    monkeypatch.setattr(stage, "_acquire", acquire)
    monkeypatch.setenv(stage.claims.RELEASE, "1")
    parent = parents.run(h)
    request = stage.from_subconfigurations(parent, law_id=stage.LAW_ID)
    monkeypatch.setenv(stage.RELEASE, "1")
    return NS(
        parent=parent,
        p=h.p,
        request=request,
        calls=calls,
        hooks=hooks,
        source=namespace,
        parent_context=stage.previous._ISSUED[parent],
    )


def test_original_selected_handler_scope_has_no_parameter_reconstruction(plan):
    value = stage.source_plan()
    assert value["handler_methods"] == stage.literal.METHODS
    assert value["actual_same_parameter"] and not value["parameter_or_wrapper_reconstruction"]
    assert not value["phase_dyna_assignment"]


@pytest.mark.parametrize("enabled,flag", [(False, "1"), (True, "0"), (1, "1")])
def test_release_refuses_before_upstream_or_native(monkeypatch, enabled, flag, rejected):
    monkeypatch.setenv(stage.RELEASE, flag)
    with rejected() as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


@pytest.mark.parametrize(
    "value", [None, {}, NS(), object.__new__(stage.previous.SubconfigurationsOwner)]
)
def test_supplied_or_unissued_parent_never_gains_handler_authority(value, rejected):
    with rejected(stage.previous.SubconfigurationsRejected):
        stage.from_subconfigurations(value, law_id=stage.LAW_ID)


def test_same_actual_parameter_original_wrappers_and_new_handler(attached, evidence):
    h = attached
    pfields = tuple(vars(h.p).items())
    owner = stage.prepare(h.request, enabled=True)
    assert owner.parameters is h.p and tuple(vars(h.p).items()) == pfields
    assert owner.handler.raw_default is h.p.tissue_default._conf
    assert h.calls == [
        "__init__",
        "_init_tissues",
        "factory",
        "_init_cuts",
        "_init_events",
        "_init_events_global",
    ]
    assert stage.previous._validate(h.parent) is h.parent_context
    assert owner.trial.source_completed
    assert owner.trial.parameter_claim.succeeded
    assert owner.trial.parameter_claim.purpose == "construction"
    assert any(row["layer"] == "factory_import_acquisition" for row in owner.trial.work)
    save(evidence, "trial", owner.trial)


def test_unavailable_numeric_store_keeps_original_failure_and_partial_handler(
    attached, evidence, rejected
):
    h = attached
    h.source["missing_cut_store"] = True
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    error = caught.value
    assert isinstance(error.source_error, AttributeError) and "event_cut_profile_names" in str(
        error.source_error
    )
    assert error.__cause__ is error.source_error and error.partial["parameters"] is h.p
    assert error.partial["handler"].raw_default is h.p.tissue_default._conf
    assert error.partial["usable_child_available"] is False
    assert not any(v.request is h.request for v in stage._ISSUED.values())
    save(evidence, "failure", dict(source_error=error.source_error, trial=error.trial))


def test_raw_handler_entry_blocked_after_success(attached, rejected):
    owner = stage.prepare(attached.request, enabled=True)
    with rejected():
        owner.handler._init_tissues(attached.p)


def test_repeated_attempt_irreversible(attached, rejected):
    h = attached
    stage.prepare(h.request, enabled=True)
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.stage == "consumed"


def test_parent_change_after_issuance_invalidates_child(attached, rejected):
    h = attached
    owner = stage.prepare(h.request, enabled=True)
    h.parent_context.invalid = True
    with rejected() as caught:
        _ = owner.handler
    assert caught.value.stage == "owner_drift"


def test_reentrant_parameter_transition_poisoned_before_delegate(attached, rejected):
    h = attached
    entered = []

    def attempt():
        assert stage.previous._ACTIVE
        stage.previous._ACTIVE[-1].invalid = True
        raise ValueError("same-thread numeric transition refused before delegate")

    h.hooks["factory"] = attempt
    with rejected():
        stage.prepare(h.request, enabled=True)
    assert entered == [] and not any(c.request is h.request for c in stage._ISSUED.values())


@pytest.mark.parametrize("falsey", [False, True])
def test_primary_cause_kept_on_native_synthetic_failure(attached, falsey, rejected):
    h = attached

    class Primary(ValueError):
        def __bool__(self):
            return not falsey

    primary, cause = Primary("original body"), RuntimeError("original cause")

    def fail():
        raise primary from cause

    h.hooks["_init_cuts"] = fail
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.source_error is primary and caught.value.__cause__ is primary
    assert primary.__cause__ is cause


def test_phase_and_profile_mapping_remain_unavailable(attached, rejected):
    owner = stage.prepare(attached.request, enabled=True)
    with rejected() as caught:
        stage.require_phase(owner)
    assert caught.value.stage == "phase_prerequisites"


def test_late_capture_error_restores_prior_profile_and_trace(attached, monkeypatch, rejected):
    h = attached
    profile, trace = sys.getprofile(), sys.gettrace()
    primary = OSError("snapshot unavailable")

    def failed(context):
        raise primary

    monkeypatch.setattr(stage, "_snapshot", failed)
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.capture_error is primary
    assert sys.getprofile() is profile and sys.gettrace() is trace
    assert not any(v.request is h.request for v in stage._ISSUED.values())


@pytest.mark.parametrize("link", ["parent_issuance", "attachment_claim", "factory_issuance"])
def test_exact_registry_links_remain_required_after_attachment(attached, rejected, link):
    h = attached
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner]
    before = stage._snapshot(context).identity
    if link == "parent_issuance":
        stage.previous._ISSUED.pop(h.parent)
    elif link == "attachment_claim":
        stage._CLAIMED.pop(h.parent)
    else:
        obj = next(obj for name, obj in context.objects if name != "handler")
        stage._FACTORY_OBJECTS.pop(obj)
    assert stage._snapshot(context).identity == before
    with rejected() as caught:
        _ = owner.handler
    assert caught.value.stage == "owner_drift"


@pytest.mark.parametrize("when", ["before_helper", "completed_child"])
@pytest.mark.parametrize(
    "kind", ["factory_code", "handler_code", "parameter_dispatch", "log_owner"]
)
def test_exact_callable_and_parameter_surface_retained(attached, monkeypatch, rejected, kind, when):
    h = attached

    def mutate():
        context = stage._CONSUMED[h.request]
        if kind == "factory_code":
            cls = context.factories["TissueProfile"]
            monkeypatch.setattr(
                cls.__init__,
                "__code__",
                cls.__init__.__code__.replace(
                    co_consts=(*cls.__init__.__code__.co_consts, "retarget witness")
                ),
            )
        elif kind == "handler_code":
            monkeypatch.setattr(
                context.methods["_init_cuts"], "__code__", (lambda self, p: None).__code__
            )
        elif kind == "parameter_dispatch":
            monkeypatch.setattr(
                type(h.p), "__getattribute__", lambda self, key: object.__getattribute__(self, key)
            )
        else:
            fn = context.methods["_init_cuts"]
            monkeypatch.setitem(
                fn.__globals__, "logs", NS(log_warning=fn.__globals__["logs"].log_warning)
            )

    if when == "before_helper":
        h.hooks["_init_tissues"] = mutate
        with rejected():
            stage.prepare(h.request, enabled=True)
        assert h.calls == ["__init__", "_init_tissues"]
    else:
        owner = stage.prepare(h.request, enabled=True)
        mutate()
        with rejected():
            _ = owner.handler


def test_equal_already_retained_array_retarget_refuses_without_value_change(attached, rejected):
    h = attached

    def fields():
        actual = stage._CONSUMED[h.request].handler
        np = stage.literal.callers.np
        actual.left = np.array([1.0, -0.0])
        actual.right = actual.left.copy()
        actual.selected = actual.left

    h.hooks["_init_events_global"] = fields
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner]
    actual = owner.handler
    cache = stage._snapshot(context).identity
    actual.selected = actual.right
    assert stage._snapshot(context).identity == cache
    with rejected() as caught:
        _ = owner.handler
    assert "alias edges" in str(caught.value.source_error)


@pytest.mark.parametrize(
    "boundary", ["__init___enter", "_init_tissues_return", "_init_cuts_unwind"]
)
def test_event_capture_stops_next_body_and_preserves_primary(
    attached, monkeypatch, rejected, boundary
):
    h = attached
    capture, primary, cause = (
        OSError("event capture"),
        ValueError("original body"),
        LookupError("original cause"),
    )

    class Events(list):
        def append(self, item):
            if item[0] == boundary:
                raise capture
            super().append(item)

    original = stage._namespace

    def namespace(context):
        original(context)
        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    if boundary.endswith("unwind"):

        def fail():
            raise primary from cause

        h.hooks["_init_cuts"] = fail
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    error = caught.value
    assert error.capture_error is capture and error.partial["usable_child_available"] is False
    assert "_init_events" not in h.calls
    if boundary == "__init___enter":
        assert h.calls == []
    elif boundary == "_init_tissues_return":
        assert "_init_cuts" not in h.calls and error.partial["handler"].tissue_default
    else:
        assert error.source_error is primary and error.__cause__ is primary
        assert primary.__cause__ is cause


@pytest.mark.parametrize("unwind", [False, True])
def test_local_capture_preserves_source_and_outer_observers(
    attached, monkeypatch, rejected, unwind
):
    h = attached
    capture, primary, cause = OSError("local capture"), ValueError("body failed"), KeyError("cause")

    class Locals(dict):
        def __setitem__(self, key, value):
            if key[1] in stage.METHODS:
                raise capture
            super().__setitem__(key, value)

    original = stage._namespace

    def namespace(context):
        original(context)
        context.locals = Locals()
        context.tape.locals = context.locals

    monkeypatch.setattr(stage, "_namespace", namespace)
    if unwind:

        def fail():
            raise primary from cause

        h.hooks["__init__"] = fail
    profile, trace = sys.getprofile(), sys.gettrace()
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.capture_error is capture
    assert sys.getprofile() is profile and sys.gettrace() is trace
    if unwind:
        assert caught.value.source_error is primary and primary.__cause__ is cause


def test_early_parent_failure_has_no_fabricated_trial_or_native_entry(attached, rejected):
    h = attached
    h.parent_context.invalid = True
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    assert caught.value.trial is None and caught.value.partial["parameters"] is None
    assert h.calls == [] and h.request in stage._CONSUMED


def test_primary_and_cause_survive_final_cache_failure(attached, monkeypatch, rejected):
    h = attached
    primary, cause, capture = RuntimeError("source"), LookupError("cause"), OSError("final cache")

    def body():
        raise primary from cause

    def snapshot(context):
        raise capture

    h.hooks["_init_cuts"] = body
    monkeypatch.setattr(stage, "_snapshot", snapshot)
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    error = caught.value
    assert error.source_error is primary and error.capture_error is capture
    assert error.__cause__ is primary and primary.__cause__ is cause
    assert error.partial["handler"].tissue_default
    assert error.partial["parent_trial"] is h.parent_context.trial


def test_caught_reentrant_attachment_cannot_rearm_outer_attempt(attached, rejected):
    h = attached
    inner = []

    def retry():
        try:
            stage.prepare(h.request, enabled=True)
        except stage.AttachmentRejected as error:
            inner.append(error)

    h.hooks["_init_tissues"] = retry
    with rejected():
        stage.prepare(h.request, enabled=True)
    assert inner[0].stage == "reentrant"
    assert h.request in stage._CONSUMED
    assert not any(c.request is h.request for c in stage._ISSUED.values())


@pytest.mark.parametrize("drift", [False, True])
def test_lazily_acquired_factory_retains_its_module_identity(
    attached, monkeypatch, rejected, drift
):
    h = attached
    acquire = stage._acquire
    records = {}
    module = NS()

    def setup(context):
        acquire(context)
        module.TissueProfile = context.factories.pop("TissueProfile")

    @contextmanager
    def held_imports(pins):
        # No native import: only a declared stand-in module record is issued.
        records["synthetic.factory"] = (module, "synthetic-path", "synthetic-sha")
        yield

    def imported(name):
        assert name == stage.literal._FACTORY_MODULES["TissueProfile"]
        return module

    monkeypatch.setattr(stage, "_acquire", setup)
    monkeypatch.setattr(stage.aliases, "issuing_native_imports", held_imports)
    monkeypatch.setattr(stage.aliases, "_module_records", lambda: dict(records))
    monkeypatch.setattr(stage.aliases, "_check_modules", lambda: None)
    monkeypatch.setattr(stage, "importlib", NS(import_module=imported))
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner]
    assert context.modules["synthetic.factory"][0] is module
    if drift:
        cache = stage._snapshot(context).identity
        records["synthetic.factory"] = (
            NS(TissueProfile=module.TissueProfile),
            "synthetic-path",
            "synthetic-sha",
        )
        assert stage._snapshot(context).identity == cache
        with rejected() as caught:
            _ = owner.handler
        assert "import changed" in str(caught.value.source_error)
    else:
        assert owner.handler.tissue_default


def test_actual_shared_numeric_claim_conflict_stops_before_numeric_delegate(attached, rejected):
    h = attached
    entries = []

    def advance():
        with stage.claims._advance(h.parent):
            entries.append("numeric delegate")

    h.hooks["_init_tissues"] = advance
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    assert entries == [] and isinstance(
        caught.value.source_error, stage.claims.ConstructionRejected
    )
    assert h.parent_context.invalid
    assert caught.value.partial["parameter_claim_record"].succeeded is False
    assert h.calls == ["__init__", "_init_tissues"]


def test_closed_shared_construction_claim_link_required(attached, rejected):
    h = attached
    owner = stage.prepare(h.request, enabled=True)
    context = stage._ISSUED[owner]
    before = stage._snapshot(context).identity
    stage.claims._CONSTRUCTED.pop(h.parent)
    assert stage._snapshot(context).identity == before
    with rejected() as caught:
        _ = owner.handler
    assert "construction claim" in str(caught.value.source_error)


def test_public_lease_preserves_actual_parameter_and_closed_record(attached, monkeypatch, evidence):
    h = attached
    reads, checks, records = [], [], []
    parameters = stage.claims.Lease.parameters
    check = stage.claims.Lease.check
    record = stage.claims.Lease.record

    def get(lease):
        p = parameters.fget(lease)
        reads.append((lease, p))
        return p

    def verify(lease):
        checks.append(lease)
        return check(lease)

    def recorded(lease):
        assert not stage.claims._context(lease).active
        value = record.fget(lease)
        records.append((lease, value))
        return value

    monkeypatch.setattr(stage.claims.Lease, "parameters", property(get))
    monkeypatch.setattr(stage.claims.Lease, "check", verify)
    monkeypatch.setattr(stage.claims.Lease, "record", property(recorded))
    owner = stage.prepare(h.request, enabled=True)
    assert owner.parameters is h.p and owner.handler.raw_default is h.p.tissue_default._conf
    trial = owner.trial
    assert reads and checks and records
    assert all(p is h.p for _, p in reads)
    assert all(value is trial.parameter_claim for _, value in tuple(records))
    save(
        evidence,
        "public-lease",
        dict(
            reads=len(reads),
            checks=len(checks),
            closed_records=len(records),
            same_actual_parameter=True,
            record=trial.parameter_claim,
        ),
    )


@pytest.mark.parametrize(
    "failure", ["foreign_parameter", "property_error", "falsey_property_error", "check_error"]
)
def test_public_lease_refusal_retains_parent_and_primary_before_body(
    attached, monkeypatch, rejected, failure
):
    h = attached

    class Primary(RuntimeError):
        def __bool__(self):
            return failure != "falsey_property_error"

    primary, cause = Primary("public lease access failed"), LookupError("original cause")

    def failed(*args):
        raise primary from cause

    if failure == "foreign_parameter":
        monkeypatch.setattr(
            stage.claims.Lease, "parameters", property(lambda lease: NS(**vars(h.p)))
        )
    elif failure == "check_error":
        monkeypatch.setattr(stage.claims.Lease, "check", failed)
    else:
        monkeypatch.setattr(stage.claims.Lease, "parameters", property(failed))
    with rejected() as caught:
        stage.prepare(h.request, enabled=True)
    error = caught.value
    assert h.calls == [] and error.partial["parameters"] is h.p
    assert error.partial["parent_trial"] is h.parent_context.trial
    assert error.partial["usable_child_available"] is False
    assert not any(c.request is h.request for c in stage._ISSUED.values())
    if failure == "foreign_parameter":
        assert isinstance(error.source_error, ValueError)
    else:
        assert error.source_error is primary and error.__cause__ is primary
        assert primary.__cause__ is cause


def test_public_lease_record_retarget_refuses_completed_child(attached, monkeypatch, rejected):
    h = attached
    owner = stage.prepare(h.request, enabled=True)
    record = owner.trial.parameter_claim
    monkeypatch.setattr(stage.claims.Lease, "record", property(lambda lease: record))
    with rejected() as caught:
        _ = owner.handler
    assert caught.value.stage == "owner_drift"
