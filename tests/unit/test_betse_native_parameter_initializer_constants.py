"""Conditional same-p dataflow; original constants/getters/float remain held."""

import builtins
import json
import sys
from dataclasses import replace
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_initializer_constants as stage
from tests.unit import test_betse_native_parameter_colormap_load as earlier
from tests.unit import test_betse_native_parameter_subconfigurations as roots
from validation.betse import betse_native_parameter_initializer_constants_software as runner
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

blocked = earlier.blocked
prevent_reference_execution = earlier.prevent_reference_execution
ORIGINAL_PLOT, ORIGINAL_COMPILE = stage._plot, stage._compile


class ConditionalAlias:
    def __init__(self, key):
        self.key = key

    def __get__(self_descriptor, self, cls):
        if self is None:
            return self_descriptor
        return self._conf["results options"]["after solving"]["plots"][self_descriptor.key]


def plot_model(context):
    value = vars(context.p)["plot"]
    cls = type(value)
    rows, refs = [], [value, cls]
    for name in ("is_after_sim_show", "is_after_sim_save"):
        descriptor = vars(cls)[name]
        function = vars(type(descriptor))["__get__"]
        rows.append((name, descriptor, function))
        refs.extend(
            (descriptor, *stage.prefix.parameters.inherited.tissue._surface(type(descriptor)))
        )
        refs.extend(stage.prefix._function_bindings(function)[1])
    return SimpleNamespace(plot=value, cls=cls, rows=tuple(rows), bindings=((), tuple(refs)))


@pytest.fixture
def controlled(monkeypatch, tmp_path):
    initial = roots.controlled.__wrapped__

    def configured(*args, **kwargs):
        h = initial(*args, **kwargs)
        h.cfg["results options"].update(
            {
                "plot cutlines": False,
                "plot networks": False,
                "vector and stream color": "black",
                "plot networks single cell": False,
                "show cells": True,
                "streamline density": 1.0,
                "plot total current": False,
                "plot masked geometry": False,
            }
        )
        h.cfg["results options"]["after solving"]["plots"].update(show=False, save=True)
        h.cfg["internal parameters"] = {"declared-only": "not numerically evaluated"}
        cls = type(h.p.plot)
        cls.is_after_sim_show = ConditionalAlias("show")
        cls.is_after_sim_save = ConditionalAlias("save")
        return h

    monkeypatch.setattr(roots.controlled, "__wrapped__", configured)
    prior = earlier.controlled.__wrapped__(monkeypatch, tmp_path, SimpleNamespace())
    parent = prior.run()
    owner_context = stage.previous._ISSUED[parent]
    plan = stage.source_plan()
    hooks, flags = {}, {}
    primary, cause = (
        SyntheticSourceFailure("conditional constants source"),
        SyntheticSourceCause("cause"),
    )
    values = {name: 1.0 for name in plan["stores"]}
    values.update(turn_all_plots_off=True, autosave=True)

    def driver(self):
        if "before" in hooks:
            hooks["before"]()
        ro = self._conf["results options"]
        iu = self._conf["internal parameters"]
        self.turn_all_plots_off = not self.plot.is_after_sim_show
        self.autosave = self.plot.is_after_sim_save
        for name in plan["stores"][2:]:
            if name == flags.get("fail_at"):
                raise primary from cause
            if name == flags.get("skip"):
                continue
            setattr(self, name, values[name])
        if flags.get("wrong_ro"):
            ro = dict(ro)
        if flags.get("wrong_iu"):
            iu = dict(iu)
        if "after" in hooks:
            hooks["after"]()
        assert ro is not None and iu is not None

    monkeypatch.setattr(stage, "_compile", lambda context: driver)
    monkeypatch.setattr(stage, "_plot", plot_model)
    monkeypatch.setenv(stage.RELEASE, "1")
    return SimpleNamespace(
        prior=prior,
        parent=parent,
        parent_context=owner_context,
        p=prior.p,
        plan=plan,
        hooks=hooks,
        flags=flags,
        primary=primary,
        cause=cause,
        driver=driver,
        run=lambda: stage.prepare(parent, law_id=stage.LAW_ID, enabled=True),
    )


def empty():
    assert not stage._ACTIVE
    assert stage._LOCK.acquire(blocking=False)
    stage._LOCK.release()
    earlier.empty()


def test_source_scope_stops_before_geometry_and_ions():
    plan = stage.source_plan()
    assert plan["statement_slice"] == (139, 203) and plan["source_lines"] == (1017, 1125)
    assert plan["next_source_line"] == 1127 and len(plan["stores"]) == 62
    assert plan["native_float_site_count"] == 10 and not plan["supplied_configuration"]
    assert not plan["geometry_ion_profile_phase_Simulator_INIT_admitted"]
    assert not plan["predecessor_source_acceptance_inferred"]
    fns, descriptions = stage._historical()
    assert set(fns) == {"_history", "_outputs"} and len(descriptions) == 2
    for name, fn in fns.items():
        original = vars(stage.previous)[name]
        assert fn.__globals__ is original.__globals__ and fn.__builtins__ is original.__builtins__


@pytest.mark.parametrize("mode", ["default", "integer", "local", "colormap", "modulator", "law"])
def test_all_release_gates_precede_authority_or_work(monkeypatch, mode):
    for gate in (stage.RELEASE, stage.previous.RELEASE, stage.previous.mod.RELEASE):
        monkeypatch.setenv(gate, "1")
    if mode in ("local", "colormap", "modulator"):
        gate = {
            "local": stage.RELEASE,
            "colormap": stage.previous.RELEASE,
            "modulator": stage.previous.mod.RELEASE,
        }[mode]
        monkeypatch.setenv(gate, "0")
    enabled = False if mode == "default" else 1 if mode == "integer" else True
    with pytest.raises(stage.ConstantsRejected) as caught:
        stage.prepare(None, law_id="foreign" if mode == "law" else stage.LAW_ID, enabled=enabled)
    assert caught.value.stage == ("law" if mode == "law" else "release")
    empty()


def test_actual_source_compilation_is_metadata_only():
    module = ModuleType("conditional-original-constants-namespace")
    module.__dict__["__builtins__"] = vars(builtins)

    def forbidden(self):
        raise AssertionError("Original body cannot execute in metadata control")

    original = FunctionType(forbidden.__code__, vars(module), "load")
    context = SimpleNamespace(parent=SimpleNamespace(bound=SimpleNamespace(original=original)))
    fn = ORIGINAL_COMPILE(context)
    path, _, _, selected = stage._ast()
    # Compare extracted code with the pinned exact AST at its original locations.
    _, original_cls, _, _ = stage._ast()
    stage.prefix.parameters.inherited._method(original_cls, "load").body = selected
    expected = stage.prefix.parameters._method_code(original_cls, "load", str(path))
    assert stage.prefix.parameters.inherited._code(
        fn.__code__
    ) == stage.prefix.parameters.inherited._code(expected)
    assert fn.__globals__ is vars(module) and fn.__builtins__ is original.__builtins__
    assert "d_cell" not in fn.__code__.co_names and "_load_ion_profile" not in fn.__code__.co_names


@pytest.mark.parametrize(
    "mode", ["valid", "foreign-plot", "equal-config", "descriptor", "shadow", "birth-class"]
)
def test_plot_metadata_requires_original_birth_wrapper_config_and_dispatch(monkeypatch, mode):
    class Plot:
        is_after_sim_show = ConditionalAlias("show")
        is_after_sim_save = ConditionalAlias("save")

    plot = object.__new__(Plot)
    conf = {"results options": {"after solving": {"plots": dict(show=False, save=True)}}}
    plot._conf = conf
    p = SimpleNamespace(_conf=conf, plot=plot)
    native = stage.prefix.parameters.inherited.tissue.aliases.NATIVE
    frame = dict(self=p, SimConfExportPlots=Plot, __class__=type(p))
    birth = SimpleNamespace(
        source=SimpleNamespace(cls=type(p)),
        source_completed=True,
        trial=SimpleNamespace(source_completed=True),
        graph=((p, plot), {}),
        locals={(str(native / stage.prefix.parameters.PARAMETERS), "Parameters.__init__"): frame},
    )
    owner = object.__new__(stage.previous.mod.subconfigs.SubconfigurationsOwner)
    loaded = SimpleNamespace(
        owner=owner,
        p=p,
        parent=SimpleNamespace(parent=birth),
        authority=SimpleNamespace(classes={"SimConfExportPlots": Plot}, objects={"plot": plot}),
        before_objects=(p, plot),
    )
    subconfigs = stage.previous.mod.subconfigs
    monkeypatch.setitem(subconfigs._ISSUED, owner, loaded)

    def bindings(context):
        return (), stage.prefix.parameters.inherited.tissue._surface(Plot)

    monkeypatch.setattr(subconfigs, "_native_bindings", bindings)
    loaded.native_bindings = bindings(loaded)
    module = ModuleType(subconfigs.MODULES["SimConfExportPlots"])
    module.__file__ = str(native / "betse/science/config/export/visual/confexpvisplot.py")
    module.SimConfExportPlots = Plot
    monkeypatch.setitem(sys.modules, module.__name__, module)
    context = SimpleNamespace(
        p=p,
        parent=SimpleNamespace(
            parent=SimpleNamespace(parent=SimpleNamespace(authority=SimpleNamespace(loaded=loaded)))
        ),
    )
    if mode == "foreign-plot":
        foreign = object.__new__(Plot)
        foreign._conf = conf
        p.plot = loaded.authority.objects["plot"] = foreign
    elif mode == "equal-config":
        plot._conf = dict(conf)
    elif mode == "descriptor":
        Plot.is_after_sim_show = ConditionalAlias("show")
    elif mode == "shadow":
        plot.is_after_sim_show = False
    elif mode == "birth-class":
        frame["SimConfExportPlots"] = type(Plot.__name__, (), {})
    if mode == "valid":
        actual = ORIGINAL_PLOT(context)
        assert actual.plot is plot and actual.cls is Plot and len(actual.rows) == 2
    else:
        with pytest.raises(ValueError):
            ORIGINAL_PLOT(context)


def test_full_conditional_continuation_and_retirement(controlled, tmp_path):
    h = controlled
    before = tuple(vars(h.p))
    result = h.run()
    context = stage._ISSUED[result]
    assert result.parameters is h.p and result.trial.source_completed
    assert context.parent.invalid and context.retired and context.entries == context.returns == 1
    assert context.plot_entries == 2 and context.plot_returns == [False, True]
    assert tuple(vars(h.p))[len(before) :] == h.plan["stores"]
    assert context.locals["ro"] is h.p._conf["results options"]
    assert context.locals["iu"] is h.p._conf["internal parameters"]
    assert not any(name in vars(h.p) for name in ("d_cell", "nx", "ny"))
    with pytest.raises(stage.ConstantsRejected) as repeated:
        h.run()
    assert repeated.value.stage == "consumed"
    with pytest.raises(stage.ConstantsRejected) as following:
        stage.require_continuation(result)
    assert following.value.partial["next_line"] == 1127
    empty()
    save(
        tmp_path,
        "conditional-constants-complete",
        dict(
            trial=stage.trial_record(context.trial),
            data=context.after_graph[1],
            metadata_work=context.metadata_work,
            validation_work=context.validations,
            p_identity_preserved=True,
            returned_colormap_graph_preserved=True,
            conditional_source_only=True,
            actual_native_float_alias_ion_entries=0,
            independent_biological_cases=0,
        ),
    )


@pytest.mark.parametrize(
    "mode", ["primary", "capture", "combined", "skipped-store", "foreign-locals"]
)
def test_conditional_primary_and_capture_failures_keep_prefix(
    controlled, monkeypatch, tmp_path, mode
):
    h = controlled
    if mode in ("primary", "combined"):
        h.flags["fail_at"] = "Do_Cl"
    if mode == "skipped-store":
        h.flags["skip"] = "Do_Cl"
    if mode == "foreign-locals":
        h.flags["wrong_ro"] = True
    if mode in ("capture", "combined"):

        def bad(frame):
            if frame.f_code is h.driver.__code__:
                raise SyntheticCaptureFailure("conditional locals capture")
            return dict(frame.f_locals)

        monkeypatch.setattr(stage, "_copy_locals", bad)
    with pytest.raises(stage.ConstantsRejected) as caught:
        h.run()
    context = caught.value.partial
    assert context is stage._CONSUMED[h.parent] and context.invalid and not context.active
    assert context.raw_return is not None and context.raw_return[0] == "source"
    assert context.raw_return[2] is None and not hasattr(context, "trial")
    if mode in ("primary", "combined"):
        assert caught.value.source_error is h.primary and h.primary.__cause__ is h.cause
        assert "Do_Na" in vars(h.p) and "Do_Cl" not in vars(h.p)
    else:
        assert context.source_completed and context.source_error is None
        if mode == "capture":
            assert context.observation_errors
        elif mode == "skipped-store":
            assert "store order" in str(context.operation_error)
        else:
            assert "config associations" in str(context.operation_error)
    empty()
    save(
        tmp_path,
        "conditional-constants-refusal",
        dict(
            mode=mode,
            source_error=context.source_error,
            operation_error=context.operation_error,
            observation_errors=context.observation_errors,
            capture_errors=context.capture_errors,
            partial_graph=None if context.failure_capture is None else context.failure_capture[1],
            stores=tuple(vars(h.p))[len(context.before_names) :],
            raw_source_unwind_retained=True,
            no_success=True,
            actual_native_entries=0,
        ),
    )


@pytest.mark.parametrize("mode", ["old-data", "new-data", "record", "plot-descriptor"])
def test_retained_successor_refuses_drift(controlled, mode):
    h = controlled
    owner = h.run()
    context = stage._ISSUED[owner]
    assert owner.parameters is h.p
    if mode == "old-data":
        h.p.periodic_properties["frequency"] = 99.0
    elif mode == "new-data":
        h.p.Do_Na = 99.0
    elif mode == "record":
        context.trial = replace(context.trial)
    else:
        type(h.p.plot).is_after_sim_show = ConditionalAlias("show")
    with pytest.raises(stage.ConstantsRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "drift" and context.invalid
    empty()


def test_reentrant_attempt_cannot_issue_success(controlled):
    h = controlled
    observed = []

    def nested():
        try:
            h.run()
        except stage.ConstantsRejected as error:
            observed.append(error)

    h.hooks["before"] = nested
    with pytest.raises(stage.ConstantsRejected):
        h.run()
    context = stage._CONSUMED[h.parent]
    assert len(observed) == 1 and observed[0].stage == "reentrant"
    assert context.invalid and context.plot_entries == 0 and not hasattr(context, "trial")
    empty()


@pytest.mark.parametrize("target", [None, "", "foreign", 1])
def test_runner_target_validation_precedes_worker(monkeypatch, tmp_path, target):
    def forbidden(*args, **kwargs):
        raise AssertionError("No worker should be launched")

    monkeypatch.setattr(runner.callbacks, "delegate", forbidden)
    with pytest.raises(ValueError, match="declared bounded"):
        runner.software(tmp_path / "packet", tmp_path / "output", target=target)
    assert not (tmp_path / "output").exists()


def test_detached_batch_plan_is_finite_unique_single_case_only():
    assert len(runner.BATCH) == 10
    assert (
        len({label for label, _ in runner.BATCH}) == len({node for _, node in runner.BATCH}) == 10
    )
    for _, node in runner.BATCH:
        assert runner._target(node) == runner.TEST + "::" + node
        name, _, _ = node.partition("[")
        assert name in globals() and callable(globals()[name])
    assert sum(node.startswith("test_conditional_primary") for _, node in runner.BATCH) == 5
    assert sum(node.startswith("test_retained_successor") for _, node in runner.BATCH) == 4


@pytest.mark.parametrize("failed_first", [False, True])
def test_detached_batch_retains_each_terminal_without_retry(monkeypatch, tmp_path, failed_first):
    packet, output = tmp_path / "packet", tmp_path / "controller-model"
    packet.mkdir()
    (packet / "source").mkdir()
    (packet / "inputs.json").write_text(json.dumps(dict(snapshot=dict(sha256="conditional"))))
    monkeypatch.setattr(
        runner.snapshot, "verify", lambda *a, **k: dict(repository=str(tmp_path / "repo"))
    )
    selected = runner.BATCH[:2]
    monkeypatch.setattr(runner, "BATCH", selected)
    calls = []

    def model(packet_arg, directory, *, target):
        assert packet_arg == packet.resolve() and target == selected[len(calls)][1]
        calls.append(target)
        process = directory / "process"
        process.mkdir(parents=True)
        fail = failed_first and len(calls) == 1
        result = dict(
            status="failed" if fail else "completed",
            returncode=1 if fail else 0,
            conditional_controller_observation_only=True,
        )
        runner.snapshot.write_json(process / ("failure.json" if fail else "result.json"), result)
        return result

    monkeypatch.setattr(runner, "software", model)
    result = runner.batch(packet, output)
    assert calls == [node for _, node in selected] and len(result["rows"]) == 2
    assert result["status"] == ("failed" if failed_first else "completed")
    assert result["unrun"] == [] and result["saved_results_still_require_review"]
    assert result["native_or_science_release"] is False
    for label, _ in selected:
        assert (output / (label + "-terminal.json")).is_file()
    assert (output / ("failure.json" if failed_first else "result.json")).is_file()
