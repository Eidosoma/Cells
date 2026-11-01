"""Native arithmetic is held; use explicit literal-output orchestration models."""

import builtins
import json
import os
import sys
from pathlib import Path
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_numeric_prefix as stage
from tests.unit import test_betse_native_parameter_subconfigurations as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ORIGINAL_COMPILE = stage._compile


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    attempts = []
    old, trace, imp = sys.getprofile(), sys.gettrace(), builtins.__import__
    codes = {
        stage._invoke.__code__,
        stage.previous._load.__code__,
        stage.previous.paths._upgrade.__code__,
        stage.previous.paths._reload.__code__,
        stage.previous.paths.prefix._invoke.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(
                str(stage.previous.paths.prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"
            )
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native/numeric/parser work forbidden")
        if old is not None:
            old(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith(("betse.", "ruamel")):
            attempts.append(name)
            raise AssertionError("Actual native import forbidden")
        return imp(name, *args, **kwargs)

    def rng(*args, **kwargs):
        attempts.append("RNG")
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imports)
    for name in ("RandomState", "default_rng", "seed", "random", "normal", "uniform", "choice"):
        monkeypatch.setattr(
            stage.previous.paths.prefix.parameters.inherited.tissue.callers.np.random, name, rng
        )
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
                    actual_native_numeric_parser_RNG_path_writes=0,
                )
            )
        )


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan):
    # Reuse the sealed earlier orchestration fixture, not a production authority.
    parent_plan = stage.previous.source_plan()
    h = earlier.controlled.__wrapped__(monkeypatch, tmp_path, parent_plan)
    parent_owner = stage.previous.prepare(h.request(), enabled=True)
    parent = stage.previous._ISSUED[parent_owner]
    setup_work = tuple(parent.trial.work)
    hooks, errors, calls = {}, {}, []
    # Literal software observations only; no original int/division/volume law.
    values = {name: 1.0 for name in plan["stores"]}
    values.update(
        autoInit=False,
        plot_grid_size=50,
        init_tsteps=2,
        sim_tsteps=3,
        refine_mesh=False,
        maximum_voronoi_steps=10,
        svg_override=False,
        svg_cells_fname=None,
        svg_size=None,
        single_cell=False,
        use_centroids=False,
    )

    def synthetic(p):
        calls.append("synthetic_numeric")
        if "before" in hooks:
            hooks["before"]()
        p.autoInit = values["autoInit"]
        if "source" in errors:
            raise errors["source"] from errors.get("cause")
        for name, value in values.items():
            setattr(p, name, value)
        if "after" in hooks:
            hooks["after"]()

    def compile_control(context):
        return synthetic, synthetic

    def invoke(context):
        context.work.append(
            dict(layer="synthetic_numeric_observation", status="entered_not_native_or_case_credit")
        )
        return context.function(context.p)

    monkeypatch.setattr(stage, "_compile", compile_control)
    monkeypatch.setattr(stage, "_invoke", invoke)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, synthetic_only=True))
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setenv(stage.previous.RELEASE, "1")
    return SimpleNamespace(
        p=h.p,
        cfg=h.cfg,
        parent=parent,
        parent_owner=parent_owner,
        base=h,
        values=values,
        hooks=hooks,
        errors=errors,
        calls=calls,
        setup_work=setup_work,
        request=lambda: stage.from_subconfigurations(parent_owner, law_id=stage.LAW_ID),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def test_exact_original_contiguous_boundary_and_no_ion_skip(plan):
    assert plan["statement_slice"] == (12, 29) and plan["source_lines"] == (520, 582)
    assert plan["next_source_line"] == 602 and len(plan["stores"]) == 18
    assert (
        len(plan["native_pins"]) == 272
        and not plan["full_Parameters_ions_geometry_tissue_handler_phase_INIT_admitted"]
    )


@pytest.mark.parametrize(
    "enabled,local,parent", [(False, "1", "1"), (True, "0", "1"), (True, "1", "0"), (1, "1", "1")]
)
def test_both_release_gates_before_handoff_or_source(monkeypatch, enabled, local, parent):
    monkeypatch.setenv(stage.RELEASE, local)
    monkeypatch.setenv(stage.previous.RELEASE, parent)
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.previous.SubconfigurationsOwner)]
)
def test_real_unissued_subconfiguration_owner_and_supplied_config_refuse(value, plan):
    with pytest.raises(
        stage.previous.SubconfigurationsRejected,
        match="Issued same-parameter subconfiguration owner",
    ):
        stage.from_subconfigurations(value, law_id=stage.LAW_ID)


def test_same_p_wrappers_configuration_and_literal_observation_outputs_retained(
    controlled, tmp_path
):
    h = controlled
    roots = dict(h.parent.authority.objects)
    before_cfg = h.cfg
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    assert (
        owner.parameters is h.p
        and h.parent.invalid
        and h.p._conf is before_cfg
        and h.p.config is before_cfg
    )
    assert all(stage.previous._member(h.p, n) is v for n, v in roots.items())
    assert tuple(owner.trial.stores) == tuple(h.values) and all(
        vars(h.p)[n] is v for n, v in h.values.items()
    )
    assert (
        len(owner.trial.work) == 1 and len(h.setup_work) == 7 and h.calls == ["synthetic_numeric"]
    )
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    save(
        tmp_path,
        "numeric-observations",
        dict(
            trial=owner.trial,
            graph=stage._ISSUED[owner].graph[1],
            setup_work=h.setup_work,
            synthetic_only=True,
            native_scalar_evaluations=0,
        ),
    )


@pytest.mark.parametrize("field", ["autoInit", "init_tsteps", "vol_env", "svg_override"])
def test_existing_numeric_store_invalidates_changed_parent_without_overwrite(
    controlled, tmp_path, field
):
    h = controlled
    setattr(h.p, field, "existing")
    with pytest.raises(stage.previous.SubconfigurationsRejected) as caught:
        h.request()
    error = caught.value
    assert error.stage == "owner_drift" and str(error) == "Stale subconfiguration owner refused"
    assert error.partial is h.parent and error.trial is h.parent.trial
    assert error.__cause__ is error.source_error and error.source_error is not None
    assert h.parent.invalid and h.calls == [] and vars(h.p)[field] == "existing"
    assert h.parent_owner not in stage._CLAIMED
    save(
        tmp_path,
        "changed-parent-refusal",
        dict(
            field=field,
            stage=error.stage,
            reason=str(error),
            source_error=error.source_error,
            parent_invalid=h.parent.invalid,
            numeric_attempts=h.calls,
            unchanged_value=vars(h.p)[field],
        ),
    )


@pytest.mark.parametrize("kind", ["source", "capture"])
def test_raw_partial_failure_source_cause_and_capture_are_separate(
    controlled, monkeypatch, tmp_path, kind
):
    h = controlled
    request = h.request()
    primary = SyntheticSourceFailure("source failed")
    cause = SyntheticSourceCause("source cause")
    capture = SyntheticCaptureFailure("capture failed")
    if kind == "source":
        h.errors.update(source=primary, cause=cause)
    else:
        original = stage.previous.paths.prefix.parameters.inherited.tissue.core.caches.snapshot

        def fail(value):
            if sys._getframe(1).f_code is stage._prepare.__code__:
                raise capture
            return original(value)

        monkeypatch.setattr(
            stage.previous.paths.prefix.parameters.inherited.tissue.core.caches, "snapshot", fail
        )
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    error = caught.value
    if kind == "source":
        assert (
            error.source_error is primary
            and error.__cause__ is primary
            and primary.__cause__ is cause
            and not error.partial.source_completed
        )
    else:
        assert (
            error.source_error is None
            and error.__cause__ is capture
            and error.partial.source_completed
        )
    assert (
        h.parent.invalid
        and error.partial.p is h.p
        and error.partial.invalid
        and not stage._ACTIVE
        and not stage.previous.paths._ACTIVE
    )
    save(
        tmp_path,
        "failed-prefix",
        dict(
            error=error,
            source=error.source_error,
            capture=error.capture_errors,
            raw=vars(h.p),
            setup_work=h.setup_work,
            native_scalar_evaluations=0,
        ),
    )


@pytest.mark.parametrize(
    "change", ["config", "wrapper", "path", "class", "new-store", "missing-output"]
)
def test_changed_parent_wrapper_path_or_unrelated_store_refuses(controlled, change):
    h = controlled

    def mutate():
        if change == "config":
            h.cfg["foreign"] = "mutated"
        elif change == "wrapper":
            h.p.visual.__class__ = h.base.classes["SimConfTissueDefault"]
        elif change == "path":
            h.p.init_pickle_filename = str(h.base.root / "foreign")
        elif change == "class":
            h.p.__class__ = type("Foreign", type(h.p).__bases__, {})
        elif change == "new-store":
            h.p.scheduled_options = {}
        else:
            del h.values["vol_env"]

    h.hooks["before"] = mutate
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        run(h)
    assert (
        caught.value.source_error is not None
        and h.parent.invalid
        and h.calls == ["synthetic_numeric"]
    )


@pytest.mark.parametrize("operation", ["mkdir", "write", "rename"])
def test_numeric_stage_filesystem_mutation_attempts_are_blocked(controlled, tmp_path, operation):
    h = controlled
    target = tmp_path / "forbidden"

    def attempt():
        if operation == "mkdir":
            os.mkdir(target)
        elif operation == "write":
            target.write_text("forbidden")
        else:
            os.rename(h.base.file.filename, target)

    h.hooks["before"] = attempt
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        run(h)
    assert (
        type(caught.value.source_error) is ValueError
        and not target.exists()
        and Path(h.base.file.filename).is_file()
    )


@pytest.mark.parametrize("swallow", [False, True])
def test_reentry_cannot_restart_numeric_prefix(controlled, swallow):
    h = controlled
    request = h.request()
    inner = []

    def nested():
        try:
            stage.prepare(request, enabled=True)
        except stage.NumericPrefixRejected as error:
            inner.append(error)
            if not swallow:
                raise

    h.hooks["before"] = nested
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        stage.prepare(request, enabled=True)
    assert inner[0].stage == "reentrant" and caught.value.partial.invalid and len(h.calls) == 1
    assert not stage._ACTIVE and not stage.previous.paths._ACTIVE


@pytest.mark.parametrize("source_failure", [False, True])
def test_actual_profiled_return_capture_does_not_mask_primary(controlled, tmp_path, source_failure):
    h = controlled
    request = h.request()
    primary = stage.previous.paths.prefix.parameters.inherited.tissue._CaptureStop("source stop")
    cause = SyntheticSourceCause("cause")
    capture = SyntheticCaptureFailure("return observer")
    if source_failure:
        h.errors.update(source=primary, cause=cause)
    selected = stage._compile(None)[0].__code__
    old, trace = sys.getprofile(), sys.gettrace()
    seen = []

    def prior(frame, event, arg):
        if old is not None:
            old(frame, event, arg)
        if frame.f_code is selected and event == "return":
            seen.append(event)
            raise capture

    sys.setprofile(prior)
    try:
        with pytest.raises(stage.NumericPrefixRejected) as caught:
            stage.prepare(request, enabled=True)
        assert sys.getprofile() is prior and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        sys.settrace(trace)
    error = caught.value
    assert seen == ["return"] and error.source_error is (primary if source_failure else None)
    assert error.__cause__ is (primary if source_failure else capture) and any(
        e is capture for _, e in error.capture_errors
    )
    if source_failure:
        assert primary.__cause__ is cause
    assert h.parent.invalid
    save(
        tmp_path,
        "source-and-observer",
        dict(
            primary=error.source_error,
            capture=error.capture_errors,
            partial=error.partial.locals,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize("change", ["value", "signed-zero", "cache", "file"])
def test_completed_numeric_prefix_owner_rejects_store_and_evidence_drift(controlled, change):
    h = controlled
    if change == "signed-zero":
        h.values["cell_height"] = 0.0
    owner = run(h)
    ctx = stage._ISSUED[owner]
    if change == "value":
        h.p.init_tsteps = 999
    elif change == "signed-zero":
        h.p.cell_height = -0.0
    elif change == "file":
        Path(h.base.file.filename).chmod(0o644)
    else:
        object.__setattr__(ctx.trial.cache, "descriptor_json", "{}")
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and ctx.invalid


def test_ions_full_parameters_tissue_handler_phase_and_pickle_remain_closed(controlled):
    import pickle

    h = controlled
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    with pytest.raises(stage.NumericPrefixRejected) as caught:
        stage.require_ions(owner)
    assert (
        caught.value.stage == "ion_profile_prerequisites"
        and not caught.value.partial["ions_full_Parameters_phase_INIT_admitted"]
    )
    for value in (owner, request):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)


@pytest.mark.parametrize(
    "change", ["unchanged", "cached-builtins", "class-cell", "wrapper", "constant-type"]
)
def test_original_scalar_slice_compilation_and_reached_bindings_without_calling_it(
    change, tmp_path
):
    path, cls, load, selected = stage._ast()
    code = stage.previous.paths.prefix.parameters._method_code(cls, "load", str(path))
    metadata_cls = type("MetadataOnlyParameters", (), {})
    module = ModuleType("metadata_only_parameters")
    namespace = vars(module)
    namespace["__builtins__"] = builtins.__dict__

    def cell(value):
        return (lambda: value).__closure__[0]

    closure = (cell(object() if change == "class-cell" else metadata_cls),)
    if change == "cached-builtins":
        namespace["__builtins__"] = dict(builtins.__dict__)
    original = FunctionType(code, namespace, "load", None, closure)
    if change == "cached-builtins":
        namespace["__builtins__"] = builtins.__dict__
    metadata_cls.load = original
    if change == "wrapper":

        def wrapper(*args, **kwargs):
            raise AssertionError("Never call metadata wrapper")

        wrapper.__wrapped__ = original
        metadata_cls.load = wrapper
    if change == "constant-type":
        consts = list(original.__code__.co_consts)
        i = next(i for i, v in enumerate(consts) if type(v) is int and v == 50)
        consts[i] = 50.0
        original.__code__ = original.__code__.replace(co_consts=tuple(consts))
    ctx = SimpleNamespace(
        birth=SimpleNamespace(
            source=SimpleNamespace(cls=metadata_cls, modules={"betse.science.parameters": module})
        )
    )
    if change == "unchanged":
        function, parent = ORIGINAL_COMPILE(ctx)
        assert (
            parent is original
            and function.__globals__ is namespace
            and function.__builtins__ is original.__builtins__
        )
        assert function.__code__.co_freevars == () and function.__closure__ is None
        assert not any(n == "scheduled_options" for n in function.__code__.co_names)
    else:
        with pytest.raises(ValueError):
            ORIGINAL_COMPILE(ctx)
    save(
        tmp_path,
        "compiled-original-slice",
        dict(change=change, original_numeric_evaluations=0, metadata_only_class=True),
    )
