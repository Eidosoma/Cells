"""Conditional native-blocked contiguous modulator ownership and failure controls."""

import builtins
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import CodeType, GeneratorType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_modulators as stage
from tests.unit import test_betse_native_parameter_grn_variables as earlier
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ORIGINAL_COMPILE = stage._compile
GUARD_PINS = dict(
    zip(
        (
            "test_betse_native_parameter_grn_variables.py",
            "test_betse_native_parameter_network_load.py",
            "test_betse_native_parameter_event_declarations.py",
            "test_betse_native_parameter_numeric_prefix.py",
        ),
        (
            "325cff1d0f45f1b31c373ea8e26120e99f513bdf15f25dd051c49b7840f73eeb",
            "8b822ff0f4789b44791860dfbd463089918124a1fbecf5bc1ca9e45011996e68",
            "2bc57049a2f84de04ac553521dec1c656fdc108e2b8268d468c4936dc3c07b65",
            "35c584c35f6b710944c3dddbc182f43fab514a23f3f617a3f1ce80bf3af9fd93",
        ),
        strict=True,
    )
)


def _guard_union(function, base):
    """Collapse only the exact four pinned fixtures' known profile predicates."""
    codes, producers = set(), {}

    def visit(fn):
        if fn is base:
            return
        path = Path(fn.__code__.co_filename)
        assert fn.__code__.co_qualname == "blocked.<locals>.profile"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == GUARD_PINS[path.name]
        producers[path.name] = GUARD_PINS[path.name]
        for name, cell in zip(fn.__code__.co_freevars, fn.__closure__ or (), strict=True):
            value = cell.cell_contents
            if name in ("old", "prior"):
                visit(value)
            elif type(value) is CodeType:
                codes.add(value)
            elif type(value) is set and all(type(item) is CodeType for item in value):
                codes.update(value)

    visit(function)
    assert producers == GUARD_PINS
    return codes, producers


def _blocked_code(code, codes, native):
    return code in codes or code.co_filename.startswith(native) or "/ruamel/" in code.co_filename


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    base, trace = sys.getprofile(), sys.gettrace()
    inherited, old, ready = None, base, False
    codes, producers, attempted, cleanup = set(), {}, [], []
    primary, setup, installed = None, "inherited_create", False
    native = str(stage.prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"

    def profile(frame, event, arg):
        if event == "call" and _blocked_code(frame.f_code, codes, native):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual modulator source/float work forbidden")
        if base is not None:
            base(frame, event, arg)

    try:
        inherited = earlier.blocked.__wrapped__(monkeypatch, request, tmp_path)
        setup = "inherited_start"
        next(inherited)
        ready, old = True, sys.getprofile()
        setup = "guard_union"
        codes, producers = _guard_union(old, base)
        codes.add(stage._invoke.__code__)
        setup = "profile_install"
        sys.setprofile(profile)
        installed, setup = True, "body"
        yield
        assert attempted == [] and sys.getprofile() is profile and sys.gettrace() is trace
    except BaseException as error:
        primary = error
        raise
    finally:
        pending = [] if inherited is None else [inherited]
        # A legacy fixture can refuse after starting its own child but before
        # reaching yield/finally. Close only the known blocked generators still
        # retained by that setup traceback, never arbitrary caller generators.
        tb = None if primary is None or ready else primary.__traceback__
        while tb is not None:
            child = tb.tb_frame.f_locals.get("inherited")
            if (
                type(child) is GeneratorType
                and child.gi_code.co_name == "blocked"
                and Path(child.gi_code.co_filename).name in GUARD_PINS
            ):
                pending.append(child)
            tb = tb.tb_next
        try:
            sys.setprofile(old if ready else base)
        except BaseException as error:
            cleanup.append(("inherited_profile_restore", error))
        if ready:
            try:
                next(inherited)
            except StopIteration:
                pass
            except BaseException as error:
                cleanup.append(("inherited_unwind", error))
            else:
                cleanup.append(("inherited_unwind", AssertionError("Extra inherited yield")))
        seen = set()
        for child in pending:
            if id(child) in seen:
                continue
            seen.add(id(child))
            try:
                child.close()
            except BaseException as error:
                cleanup.append(("inherited_close", error))
        for name, restore, value in (
            ("profile_restore", sys.setprofile, base),
            ("trace_restore", sys.settrace, trace),
        ):
            try:
                restore(value)
            except BaseException as error:
                cleanup.append((name, error))
        path = tmp_path / "native-blocked.json"
        row, inherited_complete = {}, False
        try:
            if path.exists():
                row = json.loads(path.read_text())
                assert type(row) is dict and type(row["attempted"]) is list
                inherited_complete = True
            elif ready:
                raise AssertionError("Inherited guard receipt missing")
            inherited_aggregates = {
                name: row.get(name)
                for name in (
                    "actual_event_source_numeric_parser_RNG_file_entries",
                    "actual_native_numeric_parser_RNG_path_writes",
                )
            }
            merged = list(row.get("attempted", ())) + attempted
            complete = installed and inherited_complete and not cleanup
            aggregate = 0 if complete and not merged else None
            row.update(
                nodeid=request.node.nodeid,
                attempted=merged,
                flattened_attempted=list(attempted),
                inherited_aggregates=inherited_aggregates,
                inherited_aggregate_scope="before flattened attempts were merged",
                final_blocked_attempt_count=len(merged),
                actual_event_source_numeric_parser_RNG_file_entries=aggregate,
                actual_native_numeric_parser_RNG_path_writes=aggregate,
                fixture_setup_completed=installed,
                setup_stage=setup,
                inherited_receipt_complete=inherited_complete,
                inherited_generator_closed=(inherited is None or inherited.gi_frame is None),
                profile_restored=sys.getprofile() is base,
                trace_restored=sys.gettrace() is trace,
                cleanup_error_stages=[name for name, _ in cleanup],
                equivalent_flattened_guard_producers=producers,
                forbidden_adapter_codes=sorted(
                    (code.co_filename, code.co_qualname) for code in codes
                ),
                native_prefix_and_ruamel_path_guards_preserved=installed,
            )
            path.write_text(json.dumps(row))
        except BaseException as error:
            cleanup.append(("guard_receipt", error))
        if primary is not None:
            try:
                primary.modulator_guard_cleanup = dict(
                    setup_stage=setup,
                    errors=tuple(cleanup),
                    receipt=row,
                    profile_restored=sys.getprofile() is base,
                    trace_restored=sys.gettrace() is trace,
                )
            except BaseException as error:
                cleanup.append(("primary_evidence", error))
        elif cleanup:
            raise cleanup[0][1]


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, request):
    scenario = getattr(request, "param", "none")
    config = {n: dict(slope="1.0") for n in ("gradient_x", "gradient_y", "gradient_r")}
    config.update(
        periodic=dict(frequency="1.0", phase="0.0"),
        f_sweep={"start frequency": "1.0", "end frequency": "2.0"},
    )
    if scenario in ("bitmap", "both", "bitmap-default"):
        config["gradient_bitmap"] = {
            "file": "declared-unopened-bitmap.png",
            "z-offset": "raw-offset",
        }
        if scenario == "bitmap-default":
            del config["gradient_bitmap"]["z-offset"]
    if scenario in ("single", "both"):
        config["single_cell"] = {"z-offset": "0.25"}
    base = earlier.original.controlled.__wrapped__

    def configured(*args, **kwargs):
        h = base(*args, **kwargs)
        h.cfg["modulator function properties"] = config
        if scenario == "existing-store":
            h.p.periodic_properties = {}
        return h

    monkeypatch.setattr(earlier.original.controlled, "__wrapped__", configured)
    before = earlier.controlled.__wrapped__(
        monkeypatch,
        tmp_path,
        SimpleNamespace(param="disabled" if scenario == "grn-disabled" else "enabled"),
    )
    parent_owner = stage.previous.prepare(before.request(), enabled=True)
    parent = stage.previous._ISSUED[parent_owner]
    hooks, errors, calls = {}, {}, []
    values = {
        n: {"slope": 1.0, "x-offset": 0.0, "z-offset": 0.0, "exponent": 1.0}
        for n in ("gradient_x_properties", "gradient_y_properties", "gradient_r_properties")
    }
    values.update(
        periodic_properties={"frequency": 1.0, "phase": 0.0},
        f_scan_properties={"f start": 1.0, "f stop": 2.0, "f slope": None},
    )

    def model(self):
        calls.append("conditional_modulators")
        if "before" in hooks:
            hooks["before"]()
        if errors.get("when") == "before":
            raise errors["primary"] from errors.get("cause")
        for name in values:
            setattr(self, name, {})
        for name, value in values.items():
            vars(self)[name].update(value)
            if errors.get("when") == name:
                raise errors["primary"] from errors.get("cause")
        chk = config.get("gradient_bitmap")
        self.grad_bm_fn = None if chk is None else chk["file"]
        self.grad_bm_offset = None if chk is None else chk.get("z-offset", 0.0)
        chk2 = config.get("single_cell")
        self.mod_single_cell_offset = None if chk2 is None else 0.25
        if "after" in hooks:
            hooks["after"]()

    def invoke(context):
        context.work.append(
            dict(layer="conditional_modulator_model", status="not_native_or_case_credit")
        )
        return context.function(context.p)

    monkeypatch.setattr(stage, "_compile", lambda context: model)
    monkeypatch.setattr(stage, "_invoke", invoke)
    monkeypatch.setenv(stage.RELEASE, "1")
    return SimpleNamespace(
        p=parent.p,
        cfg=config,
        parent=parent,
        parent_owner=parent_owner,
        before=before,
        values=values,
        hooks=hooks,
        errors=errors,
        calls=calls,
        model=model,
        request=lambda: stage.from_grn(parent_owner, law_id=stage.LAW_ID),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def empty():
    assert not stage._ACTIVE
    earlier.empty()


def test_exact_contiguous_modulator_source_before_required_colormap(plan):
    assert plan["statement_slice"] == (109, 135) and plan["source_lines"] == (948, 1000)
    assert plan["next_source_line"] == 1007 and len(plan["stores"]) == 8
    assert plan["native_float_call_sites"] == 17 and plan["optional_float_call_sites"] == 1
    assert not plan["projection"] and not plan["replacement_parameter"]
    assert not plan["full_Parameters_constants_ions_constructor_phase_INIT_admitted"]


def test_flat_guard_keeps_all_pinned_adapter_and_native_parser_predicates():
    profile = sys.getprofile()
    cells = dict(
        zip(
            profile.__code__.co_freevars,
            (cell.cell_contents for cell in profile.__closure__),
            strict=True,
        )
    )
    codes, native = cells["codes"], cells["native"]
    assert stage._invoke.__code__ in codes and stage.previous._invoke.__code__ in codes
    assert len(codes) >= 8
    assert all(_blocked_code(code, codes, native) for code in codes)
    native_code = compile("pass", native + "declared_probe_only.py", "exec")
    parser_code = compile("pass", "/declared/ruamel/probe_only.py", "exec")
    assert _blocked_code(native_code, codes, native) and _blocked_code(parser_code, codes, native)
    assert not _blocked_code(
        test_flat_guard_keeps_all_pinned_adapter_and_native_parser_predicates.__code__,
        codes,
        native,
    )


@pytest.mark.parametrize("mode", ["union", "hash", "advance", "union-and-cleanup"])
def test_guard_setup_refusal_unwinds_inherited_generators_and_preserves_primary(
    tmp_path, request, mode
):
    base, trace = sys.getprofile(), sys.gettrace()
    primary = SyntheticSourceFailure("synthetic union/setup refusal")
    cause = SyntheticSourceCause("original setup cause")
    secondary = SyntheticCaptureFailure("synthetic inherited cleanup failure")
    real_provider, real_union = earlier.blocked.__wrapped__, _guard_union
    seen, actual_generators = [], []
    directory = tmp_path / "isolated-setup-refusal"
    directory.mkdir()

    def bad_union(*args):
        if mode == "hash":
            try:
                return real_union(*args)
            except BaseException as error:
                seen.append(error)
                raise
        seen.append(primary)
        raise primary from cause

    def start_refusal(*args):
        inherited = real_provider(*args)
        next(inherited)
        actual_generators.append(inherited)
        raise primary from cause
        yield  # Keep the intentional pre-yield refusal a generator setup.

    def cleanup_refusal(*args):
        inherited = real_provider(*args)
        next(inherited)
        actual_generators.append(inherited)
        try:
            yield
        finally:
            try:
                next(inherited)
            except StopIteration:
                pass
            raise secondary

    nested_request = SimpleNamespace(
        node=SimpleNamespace(nodeid=request.node.nodeid + "::isolated")
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(globals(), "_guard_union", bad_union)
        if mode == "hash":
            patch.setitem(GUARD_PINS, "test_betse_native_parameter_grn_variables.py", "0" * 64)
        elif mode == "advance":
            patch.setattr(earlier.blocked, "__wrapped__", start_refusal)
        elif mode == "union-and-cleanup":
            patch.setattr(earlier.blocked, "__wrapped__", cleanup_refusal)
        nested = blocked.__wrapped__(patch, nested_request, directory)
        with pytest.raises((AssertionError, SyntheticSourceFailure)) as caught:
            next(nested)
        if mode == "hash":
            assert type(caught.value) is AssertionError and caught.value is seen[0]
        else:
            assert caught.value is primary and primary.__cause__ is cause
        evidence = caught.value.modulator_guard_cleanup
        assert evidence["profile_restored"] and evidence["trace_restored"]
        assert sys.getprofile() is base and sys.gettrace() is trace and nested.gi_frame is None
        assert all(value.gi_frame is None for value in actual_generators)
        if mode == "union-and-cleanup":
            assert evidence["errors"] == (("inherited_unwind", secondary),)
        else:
            assert evidence["errors"] == ()
        receipt = json.loads((directory / "native-blocked.json").read_text())
        assert not receipt["fixture_setup_completed"] and receipt["inherited_generator_closed"]
        assert receipt["attempted"] == [] and receipt["final_blocked_attempt_count"] == 0
        assert receipt["actual_event_source_numeric_parser_RNG_file_entries"] is None
        assert receipt["actual_native_numeric_parser_RNG_path_writes"] is None
        (directory / "native-blocked.json").rename(directory / "isolated-setup-guard.json")
    assert sys.getprofile() is base and sys.gettrace() is trace
    save(
        tmp_path,
        "setup-refusal-witness",
        dict(
            mode=mode,
            primary=caught.value,
            secondary=evidence["errors"],
            receipt=receipt,
            generators_closed=True,
            independent_control_count=1,
            actual_native_source_entries=0,
        ),
    )


@pytest.mark.parametrize("mode", ["throw", "catch"])
def test_isolated_blocked_attempt_updates_final_aggregate_without_entering_body(
    tmp_path, request, mode
):
    base, trace = sys.getprofile(), sys.gettrace()
    directory = tmp_path / "isolated-blocked-attempt"
    directory.mkdir()
    nested_request = SimpleNamespace(
        node=SimpleNamespace(nodeid=request.node.nodeid + "::isolated")
    )
    entered = []
    probe = SimpleNamespace(work=[], p=object(), function=lambda p: entered.append(p))
    with pytest.MonkeyPatch.context() as patch:
        nested = blocked.__wrapped__(patch, nested_request, directory)
        next(nested)
        inner_profile = sys.getprofile()
        try:
            with pytest.raises(AssertionError, match="source/float work forbidden") as denied:
                stage._invoke(probe)
        finally:
            sys.setprofile(inner_profile)
        assert probe.work == [] and entered == []
        with pytest.raises(AssertionError) as exit_error:
            if mode == "throw":
                nested.throw(denied.value)
            else:
                next(nested)
        if mode == "throw":
            assert exit_error.value is denied.value
        assert sys.getprofile() is base and sys.gettrace() is trace and nested.gi_frame is None
        receipt = json.loads((directory / "native-blocked.json").read_text())
        assert (
            receipt["inherited_aggregates"]["actual_event_source_numeric_parser_RNG_file_entries"]
            == 0
        )
        assert receipt["flattened_attempted"] == ["_invoke"] and receipt["attempted"] == ["_invoke"]
        assert receipt["final_blocked_attempt_count"] == 1
        assert receipt["actual_event_source_numeric_parser_RNG_file_entries"] is None
        assert receipt["actual_native_numeric_parser_RNG_path_writes"] is None
        assert receipt["profile_restored"] and receipt["trace_restored"]
        (directory / "native-blocked.json").rename(directory / "isolated-attempt-guard.json")
    assert sys.getprofile() is base and sys.gettrace() is trace
    save(
        tmp_path,
        "blocked-attempt-witness",
        dict(
            mode=mode,
            denied=denied.value,
            receipt=receipt,
            actual_adapter_body_entries=0,
            actual_native_source_entries=0,
            callback_entries=len(entered),
            work=probe.work,
            independent_control_count=1,
        ),
    )


@pytest.mark.parametrize(
    "enabled,local,parent", [(False, "1", "1"), (1, "1", "1"), (True, "0", "1"), (True, "1", "0")]
)
def test_both_gates_precede_parent_lookup_and_source(monkeypatch, enabled, local, parent):
    monkeypatch.setenv(stage.RELEASE, local)
    monkeypatch.setenv(stage.previous.RELEASE, parent)
    with pytest.raises(stage.ModulatorsRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"
    empty()


@pytest.mark.parametrize("value", [None, {}, object.__new__(stage.previous.GrnVariablesOwner)])
def test_supplied_or_unissued_owner_is_not_native_parent(value):
    with pytest.raises(stage.previous.GrnVariablesRejected) as caught:
        stage.from_grn(value, law_id=stage.LAW_ID)
    assert caught.value.stage == "owner"
    empty()


@pytest.mark.parametrize(
    "controlled",
    ["none", "bitmap", "bitmap-default", "single", "both", "grn-disabled"],
    indirect=True,
)
def test_same_actual_p_native_store_order_aliases_and_old_owner_retirement(controlled, tmp_path):
    h = controlled
    old_trial, old_graph = h.parent.trial, h.parent.graph
    owner = run(h)
    ctx = stage._ISSUED[owner]
    assert owner.parameters is h.p and h.parent.invalid and ctx.retired
    assert h.parent.trial is old_trial and h.parent.graph is old_graph
    assert (
        tuple(vars(h.p))[-8:] == ctx.plan["stores"]
        and h.p._conf["modulator function properties"] is h.cfg
    )
    assert h.p.f_scan_properties["f slope"] is None and h.calls == ["conditional_modulators"]
    assert len(ctx.trial.source_work) == 1 and ctx.trial.source_completed
    with pytest.raises(stage.previous.GrnVariablesRejected, match="Stale"):
        stage.previous._validate(h.parent_owner)
    with pytest.raises(stage.ModulatorsRejected) as future:
        stage.require_continuation(owner)
    assert (
        future.value.stage == "next_prerequisite"
        and future.value.partial["next_source_line"] == 1007
    )
    with pytest.raises(stage.ModulatorsRejected) as again:
        stage.prepare(ctx.request, enabled=True)
    assert again.value.stage == "consumed"
    empty()
    save(
        tmp_path,
        "same-parameter-modulators",
        dict(
            trial=owner.trial,
            graph=ctx.graph[1],
            parent_trial=old_trial,
            source_work=ctx.work,
            metadata_work=ctx.metadata_work,
            actual_native_source_float_entries=0,
            synthetic_only=True,
        ),
    )


def test_native_compile_metadata_keeps_exact_original_namespace_and_cached_builtins(controlled):
    h = controlled
    fn = ORIGINAL_COMPILE(SimpleNamespace(parent=h.parent))
    original = h.parent.parent.bound.original
    assert fn.__globals__ is original.__globals__ and fn.__builtins__ is original.__builtins__
    assert not fn.__code__.co_freevars
    path, cls, _, selected = stage._ast()
    import copy

    cls = copy.deepcopy(cls)
    stage.prefix.parameters.inherited._method(cls, "load").body = copy.deepcopy(selected)
    expected = stage.prefix.parameters._method_code(cls, "load", str(path))
    assert stage.prefix.parameters.inherited._code(
        fn.__code__
    ) == stage.prefix.parameters.inherited._code(expected)
    assert fn.__code__.co_filename == str(path)
    assert h.calls == [] and not h.parent.invalid


def test_native_compile_refuses_shadowed_float_without_evaluation(controlled, monkeypatch):
    h = controlled
    original = h.parent.parent.bound.original
    assert "float" not in original.__globals__ and original.__builtins__["float"] is builtins.float
    monkeypatch.setitem(original.__globals__, "float", lambda _: 1.0)
    with pytest.raises(ValueError, match="float resolution"):
        ORIGINAL_COMPILE(SimpleNamespace(parent=h.parent))
    assert h.calls == []


@pytest.mark.parametrize("controlled", ["existing-store"], indirect=True)
def test_existing_modulator_store_cannot_be_retrofitted(controlled):
    h = controlled
    with pytest.raises(ValueError, match="cannot retrofit"):
        h.request()
    assert h.calls == [] and h.parent_owner not in stage._CLAIMED
    empty()


def test_issued_source_plan_drift_refuses_before_retirement_and_source(controlled, monkeypatch):
    h = controlled
    req = h.request()
    plan = stage.source_plan()
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, changed_epoch=True))
    with pytest.raises(stage.ModulatorsRejected) as caught:
        stage.prepare(req, enabled=True)
    assert caught.value.stage == "admission" and "source/parent association" in str(
        caught.value.source_error
    )
    assert req in stage._CONSUMED and not caught.value.partial.retired and h.calls == []
    empty()


@pytest.mark.parametrize(
    "kind",
    ["old-config", "new-value", "dict-alias", "parent-trial", "parent-counts", "rearm", "receipt"],
)
def test_owner_lifetime_refuses_changed_graph_layout_or_parent_epoch(controlled, kind):
    h = controlled
    owner = run(h)
    ctx = stage._ISSUED[owner]
    if kind == "old-config":
        h.cfg["gradient_x"]["slope"] = "foreign"
    elif kind == "new-value":
        h.p.gradient_x_properties["slope"] = True
    elif kind == "dict-alias":
        h.p.gradient_y_properties = h.p.gradient_x_properties
    elif kind == "parent-trial":
        h.parent.trial = replace(h.parent.trial)
    elif kind == "parent-counts":
        h.parent.counts["factory"] = 2
    elif kind == "rearm":
        h.parent.invalid = False
    else:
        ctx.trial = replace(ctx.trial, identity="foreign")
    with pytest.raises(stage.ModulatorsRejected) as caught:
        stage._validate(owner)
    assert caught.value.stage == "owner_drift" and ctx.invalid
    assert h.calls == ["conditional_modulators"]
    empty()


@pytest.mark.parametrize("when", ["before", "gradient_y_properties"])
def test_source_failure_preserves_primary_cause_attempt_and_partial_prefix(
    controlled, tmp_path, when
):
    h = controlled
    primary, cause = (
        SyntheticSourceFailure("modulator source failed"),
        SyntheticSourceCause("original cause"),
    )
    h.errors.update(when=when, primary=primary, cause=cause)
    with pytest.raises(stage.ModulatorsRejected) as caught:
        run(h)
    error = caught.value
    ctx = error.partial
    assert (
        error.stage == "native_modulators"
        and error.source_error is primary
        and error.__cause__ is primary
    )
    assert (
        primary.__cause__ is cause and ctx.retired and h.parent.invalid and not ctx.source_completed
    )
    assert (
        ctx.failure_graph is not None
        and h.calls == ["conditional_modulators"]
        and len(ctx.work) == 1
    )
    if when != "before":
        assert "gradient_x_properties" in vars(h.p) and h.p.periodic_properties == {}
    empty()
    save(
        tmp_path,
        "modulator-failed-prefix",
        dict(
            primary=primary,
            secondary=ctx.capture_errors,
            partial=ctx.failure_graph[1],
            work=ctx.work,
            raw_return_present=ctx.raw_return is not None,
            actual_native_source_float_entries=0,
        ),
    )


@pytest.mark.parametrize("source_failure", [False, True])
def test_return_copy_failure_retains_direct_frame_arg_without_success_credit(
    controlled, monkeypatch, tmp_path, source_failure
):
    h = controlled
    secondary = SyntheticCaptureFailure("return locals unavailable")
    primary = SyntheticSourceFailure("source failed independently")

    def fail(frame):
        raise secondary

    monkeypatch.setattr(stage, "_copy_locals", fail)
    if source_failure:
        h.errors.update(when="gradient_y_properties", primary=primary)
    with pytest.raises(stage.ModulatorsRejected) as caught:
        run(h)
    error, ctx = caught.value, caught.value.partial
    assert ctx.raw_return is not None and ctx.raw_return[0].f_code is h.model.__code__
    assert ctx.raw_return[1] is None and ctx.observation_error is secondary
    assert error.source_error is (primary if source_failure else None)
    assert ctx.source_completed is (not source_failure) and ctx.invalid and h.parent.invalid
    empty()
    save(
        tmp_path,
        "return-capture-failure",
        dict(
            primary=error.source_error,
            secondary=ctx.observation_errors,
            actual_frame_identity_checked=True,
            raw_arg=None,
            source_completed=ctx.source_completed,
            child_issued=False,
            partial=ctx.failure_graph[1],
        ),
    )


@pytest.mark.parametrize("source_failure", [False, True])
def test_inherited_return_hook_is_secondary_to_actual_source_error(controlled, source_failure):
    h = controlled
    primary, cause = SyntheticSourceFailure("original"), SyntheticSourceCause("cause")
    secondary = SyntheticCaptureFailure("inherited return hook")
    if source_failure:
        h.errors.update(when="gradient_y_properties", primary=primary, cause=cause)
    inherited = sys.getprofile()
    seen = []

    def profile(frame, event, arg):
        if frame.f_code is h.model.__code__ and event == "return":
            seen.append(arg)
            raise secondary
        if inherited is not None:
            inherited(frame, event, arg)

    sys.setprofile(profile)
    try:
        with pytest.raises(stage.ModulatorsRejected) as caught:
            run(h)
    finally:
        sys.setprofile(inherited)
    ctx = caught.value.partial
    assert seen == [None] and ctx.observation_error is secondary
    assert caught.value.source_error is (primary if source_failure else None)
    if source_failure:
        assert primary.__cause__ is cause
    assert ctx.invalid and h.parent.invalid and h.calls == ["conditional_modulators"]
    empty()


@pytest.mark.parametrize("swallow", [False, True])
def test_reentry_cannot_dispatch_a_second_modulator_source(controlled, swallow):
    h = controlled
    req = h.request()
    nested = []

    def reenter():
        try:
            stage.prepare(req, enabled=True)
        except stage.ModulatorsRejected as error:
            nested.append(error)
            if not swallow:
                raise

    h.hooks["before"] = reenter
    with pytest.raises(stage.ModulatorsRejected) as caught:
        stage.prepare(req, enabled=True)
    assert nested[0].stage == "reentrant" and caught.value.partial.invalid
    assert h.calls == ["conditional_modulators"] and h.parent.invalid
    empty()


def test_nonthrowing_inherited_return_mutation_cannot_change_the_captured_source_result(controlled):
    h = controlled
    inherited = sys.getprofile()
    seen = []

    def profile(frame, event, arg):
        if frame.f_code is h.model.__code__ and event == "return":
            seen.append(arg)
            h.p.gradient_x_properties["slope"] = 17.0
        if inherited is not None:
            inherited(frame, event, arg)

    sys.setprofile(profile)
    try:
        with pytest.raises(stage.ModulatorsRejected) as caught:
            run(h)
    finally:
        sys.setprofile(inherited)
    ctx = caught.value.partial
    assert seen == [None] and ctx.source_completed and ctx.source_return_graph is not None
    assert ctx.invalid and h.parent.invalid and h.calls == ["conditional_modulators"]
    assert "alias graph changed" in str(caught.value.source_error)
    empty()
