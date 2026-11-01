"""Source declarations and typed continuation; real native work is blocked."""

import builtins
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_event_declarations as stage
from tests.unit import test_betse_native_parameter_numeric_prefix as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ORIGINAL_COMPILE = stage._compile


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    inherited = earlier.blocked.__wrapped__(monkeypatch, request, tmp_path)
    next(inherited)
    prior, trace = sys.getprofile(), sys.gettrace()
    code, attempted = stage._invoke.__code__, []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code is code:
            attempted.append("actual_event_declaration_slice")
            raise AssertionError("Actual source declarations forbidden")
        if prior is not None:
            prior(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
        assert attempted == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(prior)
        try:
            next(inherited)
        except StopIteration:
            pass
        path = tmp_path / "native-blocked.json"
        value = json.loads(path.read_text())
        value["attempted"].extend(attempted)
        value["actual_event_source_numeric_parser_RNG_file_entries"] = (
            0 if not value["attempted"] else None
        )
        path.write_text(json.dumps(value))


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan, request):
    scenario = getattr(request, "param", "zero")
    raw_targets = ["source-profile", "source-profile"]
    raw_cut = ["cut-source", "cut-source"]
    selected = {
        "Na_mem": "change Na mem",
        "K_mem": "change K mem",
        "Cl_mem": "change Cl mem",
        "Ca_mem": "change Ca mem",
        "pressure": "apply pressure",
        "ecmJ": "break ecm junctions",
    }
    enabled = scenario in {"all", "real-runtime"}
    cfg = {
        name: {
            "event happens": enabled,
            "change start": 1.0,
            "change finish": 2.0,
            "change rate": 0.25,
            "multiplier": 0.5,
            "apply to": raw_targets,
            "modulator function": "None",
        }
        for name in selected.values()
    }
    global_names = (
        "change K env",
        "change Cl env",
        "change Na env",
        "block gap junctions",
        "change temperature",
        "block NaKATP pump",
    )
    cfg.update(
        {
            name: {
                "event happens": enabled,
                "change start": 1.0,
                "change finish": 2.0,
                "change rate": 0.25,
                "multiplier": 0.5,
                "random fraction": 20.0,
            }
            for name in global_names
        }
    )
    cfg["cutting event"] = {"event happens": enabled, "apply to": raw_cut}
    if scenario == "network":
        cfg["general network"] = {
            "implement network": True,
            "expression data file": "missing-source.yaml",
        }
    elif scenario == "mixed":
        cfg[selected["Na_mem"]]["event happens"] = True
        cfg["change temperature"]["event happens"] = True
    original_base = earlier.earlier.controlled.__wrapped__

    def configured(*args, **kwargs):
        h = original_base(*args, **kwargs)
        # Configure the synthetic parsed source before issuing any seven-load
        # owner. Never alter an already sealed parameter/configuration.
        h.cfg.update(cfg)
        if scenario == "real-runtime":
            module = ModuleType("betse.synthetic_event_declaration_runtime")
            module.__file__ = __file__
            vars(module).update(h.classes, Yaml=h.birth.source.yaml, Parameters=type(h.p))
            monkeypatch.setitem(sys.modules, module.__name__, module)
            monkeypatch.setattr(
                stage.prefix, "_runtime_types", earlier.earlier.ORIGINAL_RUNTIME_TYPES
            )
        return h

    monkeypatch.setattr(earlier.earlier.controlled, "__wrapped__", configured)
    prior = earlier.controlled.__wrapped__(monkeypatch, tmp_path, stage.previous.source_plan())
    numeric_request = prior.request()
    numeric_owner = stage.previous.prepare(numeric_request, enabled=True)
    parent = stage.previous._ISSUED[numeric_owner]
    values = {
        "scheduled_options": dict.fromkeys(stage.SCHEDULED, 0),
        "break_TJ": True,
        "wound_TJ": 0.1,
        "event_cut_time": 0.0,
        "event_cut_profile_names": raw_cut,
        "global_options": dict.fromkeys(stage.GLOBAL, 0),
        "Ca_dyn": False,
        "network_config": prior.cfg.get("general network", None),
    }
    for key, source in selected.items():
        if cfg[source]["event happens"]:
            if key == "ecmJ":
                values["scheduled_options"][key] = [1.0, 2.0, 0.25, raw_targets, 0.5]
            else:
                values["scheduled_options"][key] = [1.0, 2.0, 0.25, 0.5, raw_targets, "None"]
    for key, name in zip(stage.GLOBAL, global_names, strict=True):
        if cfg[name]["event happens"]:
            values["global_options"][key] = (
                [1.0, 2.0, 0.25]
                if key == "NaKATP_block"
                else [1.0, 2.0, 0.25, 20.0 if key == "gj_block" else 0.5]
            )
    hooks, errors, calls = {}, {}, []

    def synthetic(p):
        calls.append("synthetic_declarations")
        if "before" in hooks:
            hooks["before"]()
        for name, value in values.items():
            if errors.get("point") == name:
                raise errors["source"] from errors.get("cause")
            setattr(p, name, value)
        if "after" in hooks:
            hooks["after"]()

    def compile_control(context):
        return synthetic, synthetic

    def invoke(context):
        context.source_work.append(
            dict(
                operation="synthetic_declaration_observation",
                status="entered_not_native_or_case_credit",
            )
        )
        return context.function(context.p)

    monkeypatch.setattr(stage, "_compile", compile_control)
    monkeypatch.setattr(stage, "_invoke", invoke)
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setenv(stage.claims.RELEASE, "1")
    return SimpleNamespace(
        p=prior.p,
        cfg=prior.cfg,
        parent=parent,
        parent_owner=numeric_owner,
        numeric_request=numeric_request,
        prior=prior,
        values=values,
        hooks=hooks,
        errors=errors,
        calls=calls,
        request=lambda: stage.from_numeric(numeric_owner, law_id=stage.LAW_ID),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def empty():
    assert not stage._ACTIVE and not stage.previous._ACTIVE and not stage.claims._ACTIVE
    assert not stage.previous.previous._ACTIVE and not stage.previous.previous.paths._ACTIVE


def test_exact_contiguous_original_boundary_stops_before_network_file_branch(plan):
    assert plan["statement_slice"] == (29, 61) and plan["source_lines"] == (602, 777)
    assert plan["next_source_line"] == 779 and len(plan["native_pins"]) == 272
    assert plan["stores"] == (
        "scheduled_options",
        "break_TJ",
        "wound_TJ",
        "event_cut_time",
        "event_cut_profile_names",
        "global_options",
        "Ca_dyn",
        "network_config",
    )
    assert not plan["events_callbacks_files_full_Parameters_phase_INIT_admitted"]


@pytest.mark.parametrize(
    "enabled,local,parent,sub",
    [
        (False, "1", "1", "1"),
        (True, "0", "1", "1"),
        (True, "1", "0", "1"),
        (True, "1", "1", "0"),
        (1, "1", "1", "1"),
    ],
)
def test_all_release_gates_precede_parent_read_or_source(monkeypatch, enabled, local, parent, sub):
    monkeypatch.setenv(stage.RELEASE, local)
    monkeypatch.setenv(stage.previous.RELEASE, parent)
    monkeypatch.setenv(stage.previous.previous.RELEASE, sub)
    with pytest.raises(stage.DeclarationsRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"
    empty()


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.previous.NumericPrefixOwner)]
)
def test_only_actual_issued_numeric_owner_can_continue(value, plan):
    with pytest.raises(stage.previous.NumericPrefixRejected, match="Issued numeric prefix owner"):
        stage.from_numeric(value, law_id=stage.LAW_ID)
    empty()


@pytest.mark.parametrize("field", ["context", "trial"])
def test_incomplete_numeric_prefix_is_not_promoted_to_declaration_authority(controlled, field):
    h = controlled
    if field == "context":
        h.parent.source_completed = False
    else:
        trial = replace(h.parent.trial, source_completed=False, identity="")
        h.parent.trial = replace(trial, identity=stage._digest(stage.previous.trial_record(trial)))
    with pytest.raises(stage.DeclarationsRejected) as caught:
        h.request()
    assert caught.value.stage == "numeric_parent"
    assert str(caught.value) == "Actual completed numeric prefix required"
    assert h.parent.invalid and not h.calls
    empty()


@pytest.mark.parametrize("controlled", ["zero", "all", "mixed", "network"], indirect=True)
def test_same_p_order_aliases_clocks_prior_stores_and_first_file_refusal(controlled, tmp_path):
    h = controlled
    p = h.p
    original = dict(vars(p))
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    ctx = stage._ISSUED[owner]
    assert owner.parameters is p and h.parent.invalid
    assert all(vars(p)[name] is value for name, value in original.items())
    assert ctx.parent is h.parent and ctx.birth is h.parent.birth
    assert tuple(p.scheduled_options) == stage.SCHEDULED and tuple(p.global_options) == stage.GLOBAL
    assert p.event_cut_profile_names is h.cfg["cutting event"]["apply to"]
    assert p.network_config is h.cfg.get("general network", None)
    assert len(owner.trial.source_work) == 1 and h.calls == ["synthetic_declarations"]
    assert len(h.prior.setup_work) == 7 and h.prior.calls == ["synthetic_numeric"]
    with pytest.raises(stage.DeclarationsRejected) as caught:
        stage.require_network(owner)
    assert (
        caught.value.stage == "network_file_authority"
        and caught.value.partial["next_source_line"] == 779
    )
    with pytest.raises(stage.previous.NumericPrefixRejected):
        _ = h.parent_owner.parameters
    with pytest.raises(stage.DeclarationsRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    empty()
    save(
        tmp_path,
        "declarations",
        dict(
            trial=owner.trial,
            graph=ctx.graph[1],
            source_work=ctx.source_work,
            metadata_work=ctx.work,
            prior_numeric_work=h.parent.trial.work,
            earlier_setup_work=h.prior.setup_work,
            actual_native_entries=0,
            independent_cases=0,
        ),
    )


@pytest.mark.parametrize(
    "point", ["scheduled_options", "break_TJ", "global_options", "network_config"]
)
def test_source_failure_keeps_primary_cause_and_raw_partial_declarations(
    controlled, tmp_path, point
):
    h = controlled
    primary = SyntheticSourceFailure("source declaration failed")
    cause = SyntheticSourceCause("original cause")
    h.errors.update(point=point, source=primary, cause=cause)
    with pytest.raises(stage.DeclarationsRejected) as caught:
        run(h)
    e = caught.value
    assert e.source_error is primary and e.__cause__ is primary and primary.__cause__ is cause
    assert not e.partial.source_completed and h.parent.invalid and e.partial.invalid
    assert h.calls == ["synthetic_declarations"] and len(e.partial.source_work) == 1
    empty()
    save(
        tmp_path,
        "source-failure",
        dict(
            primary=e.source_error,
            capture=e.capture_errors,
            raw=vars(h.p),
            metadata_work=e.partial.work,
            source_work=e.partial.source_work,
            claim_secondary=e.partial.capture_errors,
            actual_native_entries=0,
        ),
    )


@pytest.mark.parametrize(
    "change",
    ["target-copy", "scheduled-order", "global-order", "shape", "Ca-dyn", "cut-zero", "late-GRN"],
)
@pytest.mark.parametrize("controlled", ["all"], indirect=True)
def test_literal_output_shape_order_target_alias_and_boundary_contract_refuse(controlled, change):
    h = controlled

    def mutate():
        if change == "target-copy":
            h.p.scheduled_options["Na_mem"][4] = list(h.cfg["change Na mem"]["apply to"])
        elif change == "scheduled-order":
            h.p.scheduled_options = dict(reversed(tuple(h.p.scheduled_options.items())))
        elif change == "global-order":
            h.p.global_options = dict(reversed(tuple(h.p.global_options.items())))
        elif change == "shape":
            h.p.global_options["NaKATP_block"].append(1.0)
        elif change == "Ca-dyn":
            h.p.Ca_dyn = True
        elif change == "cut-zero":
            h.p.event_cut_time = -0.0
        else:
            h.p.grn_enabled = False

    h.hooks["after"] = mutate
    with pytest.raises(stage.DeclarationsRejected) as caught:
        run(h)
    assert caught.value.source_error is not None and h.parent.invalid
    empty()


@pytest.mark.parametrize("change", ["numeric-value", "configuration", "wrapper", "class"])
def test_earlier_numeric_configuration_wrapper_birth_stores_are_not_rebuilt(controlled, change):
    h = controlled

    def mutate():
        if change == "numeric-value":
            h.p.init_tsteps = 999
        elif change == "configuration":
            h.p._conf = dict(h.cfg)
        elif change == "wrapper":
            h.p.visual = h.prior.base.classes["SimConfExportVisual"]()
        else:
            h.p.__class__ = type("ForeignParams", type(h.p).__bases__, {})

    h.hooks["before"] = mutate
    with pytest.raises(stage.DeclarationsRejected) as caught:
        run(h)
    assert caught.value.source_error is not None and h.parent.invalid
    empty()


@pytest.mark.parametrize("swallow", [False, True])
def test_reentry_cannot_repeat_source_or_issue_a_completed_child(controlled, swallow):
    h = controlled
    request = h.request()
    seen = []

    def nested():
        try:
            stage.prepare(request, enabled=True)
        except stage.DeclarationsRejected as e:
            seen.append(e)
            if not swallow:
                raise

    h.hooks["before"] = nested
    with pytest.raises(stage.DeclarationsRejected) as caught:
        stage.prepare(request, enabled=True)
    assert seen[0].stage == "reentrant" and caught.value.partial.invalid
    assert h.calls == ["synthetic_declarations"] and h.parent.invalid
    empty()


@pytest.mark.parametrize("operation", ["numeric", "constructor", "numeric-request"])
def test_shared_claim_excludes_other_consumers_before_their_delegates(controlled, operation):
    h = controlled
    seen = []

    def nested():
        if operation == "numeric":
            stage.previous.prepare(h.numeric_request, enabled=True)
        elif operation == "numeric-request":
            h.prior.request()
        else:
            with stage.claims.construction(
                h.prior.parent_owner, law_id=stage.claims.LAW_ID, enabled=True
            ):
                seen.append("should not enter")

    h.hooks["before"] = nested
    with pytest.raises(stage.DeclarationsRejected) as caught:
        run(h)
    assert caught.value.source_error is not None and seen == [] and h.parent.invalid
    expected = "reentrant" if operation == "numeric" else "claim_conflict"
    assert caught.value.source_error.stage == expected
    assert h.prior.calls == ["synthetic_numeric"] and h.calls == ["synthetic_declarations"]
    empty()


def test_completed_source_capture_failure_remains_failed_and_preserves_all_stores(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    capture = SyntheticCaptureFailure("event snapshot failed")
    original = stage.prefix.parameters.inherited.tissue.core.caches.snapshot

    def snapshot(value):
        if sys._getframe(1).f_code is stage.prepare.__code__:
            raise capture
        return original(value)

    monkeypatch.setattr(stage.prefix.parameters.inherited.tissue.core.caches, "snapshot", snapshot)
    with pytest.raises(stage.DeclarationsRejected) as caught:
        run(h)
    e = caught.value
    assert e.source_error is None and e.__cause__ is capture and e.partial.source_completed
    assert h.parent.invalid and all(name in vars(h.p) for name in h.values)
    empty()
    save(
        tmp_path,
        "capture-failure",
        dict(
            primary=e.source_error,
            capture=e.capture_errors,
            raw=vars(h.p),
            source_work=e.partial.source_work,
            metadata_work=e.partial.work,
        ),
    )


@pytest.mark.parametrize("source_failure", [False, True])
def test_profiled_return_hook_preserves_source_exception_and_separate_capture(
    controlled, tmp_path, source_failure
):
    h = controlled
    primary = stage.prefix.parameters.inherited.tissue._CaptureStop("original source stop")
    cause = SyntheticSourceCause("original cause")
    capture = SyntheticCaptureFailure("return observer failed")
    if source_failure:
        h.errors.update(point="break_TJ", source=primary, cause=cause)
    selected = stage._compile(None)[0].__code__
    old = sys.getprofile()
    seen = []

    def profile(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if frame.f_code is selected and event == "return":
            seen.append(event)
            raise capture

    sys.setprofile(profile)
    try:
        with pytest.raises(stage.DeclarationsRejected) as caught:
            run(h)
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(old)
    e = caught.value
    assert seen == ["return"] and e.source_error is (primary if source_failure else None)
    assert e.__cause__ is (primary if source_failure else capture)
    assert any(err is capture for _, err in e.capture_errors)
    if source_failure:
        assert primary.__cause__ is cause
    empty()
    save(
        tmp_path,
        "profile-failure",
        dict(
            primary=e.source_error,
            capture=e.capture_errors,
            locals=e.partial.locals,
            source_completed=e.partial.source_completed,
            raw=vars(h.p),
        ),
    )


@pytest.mark.parametrize("controlled", ["real-runtime"], indirect=True)
def test_actual_runtime_enumerator_uses_original_birth_without_inventory_refresh(
    controlled, tmp_path
):
    h = controlled
    original = earlier.earlier.ORIGINAL_RUNTIME_TYPES.__code__
    old = sys.getprofile()
    seen = []

    def profile(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if frame.f_code is original and event == "call":
            seen.append(frame.f_locals["context"])

    sys.setprofile(profile)
    try:
        owner = run(h)
        assert owner.parameters is h.p
    finally:
        sys.setprofile(old)
    ctx = stage._ISSUED[owner]
    assert len(seen) >= 5 and all(v.parent is ctx.birth for v in seen)
    assert ctx.view.runtime_types is h.parent.runtime_types
    empty()
    save(
        tmp_path,
        "real-runtime",
        dict(
            metadata_runtime_enumerations=len(seen),
            runtime_files=h.parent.runtime_files,
            native_entries=0,
            inventory_refreshed=False,
        ),
    )


@pytest.mark.parametrize("change", ["value", "target", "file", "cache"])
def test_retained_child_detects_later_data_file_and_cache_drift(controlled, change):
    h = controlled
    owner = run(h)
    ctx = stage._ISSUED[owner]
    if change == "value":
        h.p.wound_TJ = -0.0
    elif change == "target":
        h.p.event_cut_profile_names = list(h.p.event_cut_profile_names)
    elif change == "file":
        Path(h.prior.base.file.filename).chmod(0o644)
    else:
        object.__setattr__(ctx.trial.cache, "descriptor_json", "{}")
    with pytest.raises(stage.DeclarationsRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and ctx.invalid


@pytest.mark.parametrize(
    "change", ["unchanged", "bool-shadow", "float-shadow", "cached-builtins", "wrong-constant"]
)
def test_original_source_compilation_and_builtin_correspondence_never_evaluates(change, tmp_path):
    path, cls, load, selected = stage._ast()
    code = stage.prefix.parameters._method_code(cls, "load", str(path))
    holder = type("MetadataOnlyParameters", (), {})
    module = ModuleType("metadata_only_original_parameters")
    namespace = vars(module)
    namespace["__builtins__"] = builtins.__dict__

    def cell(value):
        return (lambda: value).__closure__[0]

    if change == "cached-builtins":
        namespace["__builtins__"] = dict(builtins.__dict__)
    native = FunctionType(code, namespace, "load", None, (cell(holder),))
    holder.load = native
    if change == "cached-builtins":
        namespace["__builtins__"] = builtins.__dict__
    if change == "bool-shadow":
        namespace["bool"] = bool
    if change == "float-shadow":
        namespace["float"] = lambda x: x
    if change == "wrong-constant":
        constants = list(native.__code__.co_consts)
        index = next(i for i, v in enumerate(constants) if type(v) is int and v == 50)
        constants[index] = 50.0
        native.__code__ = native.__code__.replace(co_consts=tuple(constants))
    ctx = SimpleNamespace(
        birth=SimpleNamespace(
            source=SimpleNamespace(cls=holder, modules={"betse.science.parameters": module})
        )
    )
    if change == "unchanged":
        function, raw = ORIGINAL_COMPILE(ctx)
        assert raw is native and function.__globals__ is namespace
        assert function.__builtins__ is native.__builtins__ and function.__closure__ is None
        assert "scheduled_options" in function.__code__.co_names
        assert "network_config" in function.__code__.co_names
        assert (
            "expression_data" not in function.__code__.co_names
            and "grn_enabled" not in function.__code__.co_names
        )
    else:
        with pytest.raises(ValueError):
            ORIGINAL_COMPILE(ctx)
    save(tmp_path, "compiled-only", dict(change=change, actual_source_evaluations=0))


def test_live_request_and_owner_pickle_stay_closed(controlled):
    import pickle

    h = controlled
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    for value in (request, owner):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)
    empty()
