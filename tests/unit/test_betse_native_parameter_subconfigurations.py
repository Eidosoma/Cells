"""Native-blocked original subconfiguration authority and graph continuation."""

import builtins
import hashlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_subconfigurations as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ORIGINAL_CANONICAL = stage._canonical
ORIGINAL_RUNTIME_TYPES = stage.paths.prefix._runtime_types


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    attempts = []
    old, trace, imp = sys.getprofile(), sys.gettrace(), builtins.__import__
    codes = {
        stage._load.__code__,
        stage.paths._upgrade.__code__,
        stage.paths._reload.__code__,
        stage.paths.prefix._invoke.__code__,
        stage.paths.prefix.parameters._acquire.__code__,
        stage.paths.prefix.parameters._invoke.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(
                str(stage.paths.prefix.parameters.inherited.tissue.aliases.NATIVE) + "/"
            )
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native constructor/load/parser forbidden")
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
            stage.paths.prefix.parameters.inherited.tissue.callers.np.random, name, rng
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
                    actual_native_parser_RNG_path_writes=0,
                )
            )
        )


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, plan):
    monkeypatch.setattr(stage.paths, "BASE", tmp_path)
    monkeypatch.setattr(stage.paths.prefix, "BASE", tmp_path)
    file_path = tmp_path / "configuration.yaml"
    data = b"synthetic retained source file\n"
    file_path.write_bytes(data)
    file_path.chmod(0o444)
    file = stage.paths.prefix.input_file(
        file_path, sha256=hashlib.sha256(data).hexdigest(), origin="conditional software only"
    )
    calls, hooks, errors, native_errors = [], {}, {}, {}

    class Yaml:
        def __init__(self):
            self._conf = None

        def load(self, conf):
            self._conf = conf
            if id(self) in native_errors:
                raise native_errors[id(self)] from native_errors.get("cause")

    def scalar(name):
        return type(name, (Yaml,), {})

    classes = {name: scalar(name) for name in stage.MODULES if name != "YamlList"}

    class YamlList(Yaml):
        def __init__(self, item_type):
            super().__init__()
            self._item_type = item_type
            self._confs_wrap = None

        def load(self, conf):
            super().load(conf)
            self._confs_wrap = []
            for raw in conf:
                row = self._item_type()
                row.load(conf=raw)
                self._confs_wrap.append(row)

    classes["YamlList"] = YamlList

    class Anims(Yaml):
        def __init__(self):
            super().__init__()
            self.anim_while_sim = classes["SimConfExportAnimCellsEmbedded"]()
            self.anims_after_sim = YamlList(classes["SimConfExportAnimCells"])

        def load(self, conf):
            super().load(conf)
            self.anim_while_sim.load(conf=conf["results options"]["while solving"]["animations"])
            self.anims_after_sim.load(
                conf=conf["results options"]["after solving"]["animations"]["pipeline"]
            )

    class Csvs(Yaml):
        def __init__(self):
            super().__init__()
            self.csvs_after_sim = YamlList(classes["SimConfExportCSV"])

        def load(self, conf):
            super().load(conf)
            self.csvs_after_sim.load(
                conf=conf["results options"]["after solving"]["csvs"]["pipeline"]
            )

    class Plots(Yaml):
        def __init__(self):
            super().__init__()
            self.plots_cell_after_sim = YamlList(classes["SimConfExportPlotCell"])
            self.plots_cells_after_sim = YamlList(classes["SimConfExportPlotCells"])

        def load(self, conf):
            super().load(conf)
            cfg = conf["results options"]["after solving"]["plots"]
            self.plots_cell_after_sim.load(conf=cfg["single cell pipeline"])
            self.plots_cells_after_sim.load(conf=cfg["cell cluster pipeline"])

    classes.update(SimConfExportAnims=Anims, SimConfExportCSVs=Csvs, SimConfExportPlots=Plots)

    class Params(Yaml):
        pass

    p = Params()
    cfg = {
        "tissue profile definition": {
            "cut profiles": [],
            "tissue": {"default": {"name": "synthetic default"}, "profiles": []},
        },
        "results options": {
            "while solving": {"animations": {}},
            "after solving": {
                "animations": {"pipeline": []},
                "csvs": {"pipeline": []},
                "plots": {"single cell pipeline": [], "cell cluster pipeline": []},
            },
        },
    }
    p._conf = cfg
    p.config = cfg
    p._conf_filename = file.filename
    p._conf_dirname = str(file_path.parent)
    p._conf_basename = file_path.name
    for name, (kind, item) in stage.ROOT_TYPES.items():
        if "." in name:
            continue
        setattr(p, name, classes[kind](classes[item]) if item is not None else classes[kind]())
    objects = {name: stage._member(p, name) for name in stage.ROOT_TYPES}
    before_objects = (p, cfg, *objects.values())
    path_values = tuple(
        (name, None if name == "grn_unpickle_filename" else str(tmp_path / "original-paths" / name))
        for name in stage.paths.FIELDS
    )
    policy = stage.paths.declare_paths(paths=path_values, law_id=stage.paths.LAW_ID)
    for name, value in path_values:
        setattr(p, name, value)
    p.grn_config_filename_relative = "synthetic_relative"
    runtime = ((), (Params,))
    birth = SimpleNamespace(
        p=p,
        source=SimpleNamespace(cls=Params, yaml=Yaml),
        runtime=runtime,
        locals={},
        graph=(before_objects, {}),
        source_completed=True,
    )
    cache = stage.paths.prefix.parameters.inherited.tissue.core.caches.snapshot(
        {"synthetic_path_parent": True}
    )
    birth.trial = SimpleNamespace(source_completed=True, cache=cache)
    owner = object.__new__(stage.paths.PathsOwner)
    parent = SimpleNamespace(
        p=p,
        config=cfg,
        parent=birth,
        invalid=False,
        active=False,
        trial=SimpleNamespace(identity="synthetic_path_epoch", cache=cache),
        graph=(before_objects, {}),
        request=SimpleNamespace(policy=policy),
        yaml=SimpleNamespace(request=SimpleNamespace(file=file)),
        file_record=stage.paths.prefix.file_record(file),
        runtime_types=frozenset((Yaml, Params, *classes.values())),
        bindings=None,
    )
    authority = SimpleNamespace(classes=classes, objects=objects)

    def validate(value):
        if value is not owner or parent.invalid:
            raise stage.paths.PathsRejected("Unissued/retired synthetic path owner", stage="owner")
        return parent

    def canonical(value):
        if value is not parent:
            raise AssertionError("Foreign synthetic parent")
        return authority

    def native_bindings(context):
        return ((), tuple(classes.values()))

    def load(context, name):
        context.work.append(
            dict(layer="synthetic_source", root=name, status="entered_not_native_credit")
        )
        calls.append(name)
        if name in hooks:
            hooks[name]()
        if name in errors:
            raise errors[name] from errors.get("cause")
        wrapper = getattr(context.p, name)
        conf = stage._target(context.config, name)
        wrapper.load(conf=conf)
        if "after_" + name in hooks:
            hooks["after_" + name]()

    def registry(context):
        return parent.runtime_types, {}, ((), (Params,))

    monkeypatch.setattr(stage.paths, "_validate", validate)
    monkeypatch.setattr(stage, "_canonical", canonical)
    monkeypatch.setattr(stage, "_native_bindings", native_bindings)
    monkeypatch.setattr(stage, "_load", load)
    monkeypatch.setattr(stage.paths.prefix.parameters, "_runtime", lambda source: runtime)
    monkeypatch.setattr(stage.paths.prefix, "_runtime_types", registry)
    monkeypatch.setattr(stage, "source_plan", lambda: dict(plan, synthetic_only=True))
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setenv(stage.paths.RELEASE, "1")
    parent.bindings = stage.paths._bindings()
    return SimpleNamespace(
        p=p,
        cfg=cfg,
        parent=parent,
        birth=birth,
        owner=owner,
        authority=authority,
        classes=classes,
        objects=objects,
        calls=calls,
        hooks=hooks,
        errors=errors,
        native_errors=native_errors,
        file=file,
        root=tmp_path,
        request=lambda: stage.from_paths(owner, law_id=stage.LAW_ID),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def test_literal_order_matches_native_and_specialist_read_only_correspondence(plan):
    assert plan["load_order"] == stage.ORDER and len(plan["native_pins"]) == 272
    assert plan["next_source_line"] > plan["load_lines"][1]
    assert not plan["actual_numeric_Parameters_tissue_handler_phase_INIT_admitted"]


@pytest.mark.parametrize(
    "enabled,local,base", [(False, "1", "1"), (True, "0", "1"), (True, "1", "0"), (1, "1", "1")]
)
def test_release_gates_before_path_owner_or_native_load(monkeypatch, enabled, local, base):
    monkeypatch.setenv(stage.RELEASE, local)
    monkeypatch.setenv(stage.paths.RELEASE, base)
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


@pytest.mark.parametrize(
    "value", [None, {}, SimpleNamespace(), object.__new__(stage.paths.PathsOwner)]
)
def test_real_unissued_path_or_supplied_configuration_refuses(value, plan):
    with pytest.raises(stage.paths.PathsRejected, match="Issued compatibility/path owner"):
        stage.from_paths(value, law_id=stage.LAW_ID)


@pytest.mark.parametrize("shape", ["empty", "one-each", "duplicate-source-rows"])
def test_same_parameter_roots_native_order_fresh_rows_and_aliases(controlled, tmp_path, shape):
    h = controlled
    roots = dict(h.objects)
    before = tuple(h.parent.graph[0])
    row = {"name": "synthetic shared row"}
    lists = stage._lists(SimpleNamespace(config=h.cfg))
    if shape != "empty":
        for _, values in lists:
            values.append(row)
        if shape == "duplicate-source-rows":
            for _, values in lists:
                values.append(row)
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    assert (
        owner.parameters is h.p and h.parent.invalid and h.p._conf is h.cfg and h.p.config is h.cfg
    )
    assert tuple(h.calls) == stage.ORDER and all(
        stage._member(h.p, name) is obj for name, obj in roots.items()
    )
    assert h.p.grn._conf is None and len(owner.trial.work) == 7
    context = stage._ISSUED[owner]
    fresh = stage._loaded(context)
    assert len(fresh) == (0 if shape == "empty" else 6 if shape == "one-each" else 12)
    assert len({id(v) for v in fresh}) == len(fresh) and not any(
        v is x for v in fresh for x in before
    )
    assert all(v._conf is row for v in fresh)
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        stage.prepare(request, enabled=True)
    assert caught.value.stage == "consumed"
    save(
        tmp_path,
        "loaded-graph",
        dict(trial=owner.trial, graph=context.graph[1], synthetic_only=True),
    )


def test_real_runtime_enumeration_uses_retained_birth_capture_view(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    # An isolated metadata module supplies the real enumerator's class/file
    # surface. No native module import, class construction or load is released.
    module = ModuleType("betse.synthetic_subconfiguration_runtime")
    module.__file__ = __file__
    vars(module).update(h.classes, Yaml=h.birth.source.yaml, Parameters=type(h.p))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(stage.paths.prefix, "_runtime_types", ORIGINAL_RUNTIME_TYPES)
    assert not hasattr(h.parent, "source")
    with pytest.raises(AttributeError, match="source"):
        ORIGINAL_RUNTIME_TYPES(SimpleNamespace(parent=h.parent))
    seen = []
    prior = sys.getprofile()

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if frame.f_code is ORIGINAL_RUNTIME_TYPES.__code__ and event == "call":
            seen.append(frame.f_locals["context"])

    sys.setprofile(profile)
    try:
        owner = run(h)
        context = stage._ISSUED[owner]
        assert owner.parameters is h.p
        assert len(seen) == 2 and all(view is context.capture_view for view in seen)
        assert context.capture_view.parent is h.birth
        assert (
            context.capture_view.p is h.p
            and context.capture_view.file_record is h.parent.file_record
        )
        assert context.capture_view.runtime_types is context.runtime_types
        assert context.runtime_types == h.parent.runtime_types
        assert context.runtime_files == {
            str(Path(__file__).resolve()): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        }
        assert any(value is module for value in context.runtime_namespaces[1])
        assert tuple(context.completed) == stage.ORDER and h.parent.invalid
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(prior)
    save(
        tmp_path,
        "real-runtime-enumeration",
        dict(
            real_enumerations=1 + len(seen),
            invalid_path_view_enumerations=1,
            valid_capture_view_enumerations=len(seen),
            same_birth_parent=True,
            same_p=True,
            runtime_files=context.runtime_files,
            completed=context.completed,
            native_entries=0,
            synthetic_metadata_only=True,
        ),
    )


@pytest.mark.parametrize(
    "name",
    [
        "cut_profiles",
        "tissue_profiles",
        "anim.anims_after_sim",
        "csv.csvs_after_sim",
        "plot.plots_cell_after_sim",
        "plot.plots_cells_after_sim",
    ],
)
def test_fresh_construction_identity_order_rejects_swapped_aliased_rows(controlled, tmp_path, name):
    h = controlled
    raw = {"name": "same actual raw row alias"}
    lists = dict(stage._lists(SimpleNamespace(config=h.cfg)))
    lists[name].extend((raw, raw))
    before = []

    def swap():
        rows = stage._member(h.p, name)._confs_wrap
        assert len(rows) == 2 and rows[0] is not rows[1]
        assert rows[0]._conf is raw and rows[1]._conf is raw
        before.extend(rows)
        rows.reverse()
        assert rows[0] is before[1] and rows[1] is before[0]

    h.hooks["after_visual"] = swap
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    failure = caught.value
    context = failure.partial
    assert type(failure.source_error) is ValueError
    assert str(failure.source_error) == "Native row wrapper construction order changed"
    assert failure.__cause__ is failure.source_error and not failure.capture_errors
    assert len(context.constructed) == 2 and all(
        actual is original for actual, original in zip(context.constructed, before, strict=True)
    )
    assert context.invalid and h.parent.invalid and tuple(context.completed) == stage.ORDER
    assert len(context.work) == 7 and not stage._ACTIVE and not stage.paths._ACTIVE
    save(
        tmp_path,
        "aliased-row-order-refusal",
        dict(
            list_name=name,
            primary=failure.source_error,
            completed=context.completed,
            work=context.work,
            raw_alias_preserved=True,
            distinct_fresh_wrappers=True,
            constructor_identity_order_retained=True,
            reversed_rows_refused=True,
            native_entries=0,
        ),
    )


@pytest.mark.parametrize("point", stage.ORDER)
def test_each_failed_native_shaped_load_keeps_primary_cause_and_completed_prefix(
    controlled, tmp_path, point
):
    h = controlled
    error = SyntheticSourceFailure("load failed " + point)
    cause = SyntheticSourceCause("original cause")
    h.errors.update({point: error, "cause": cause})
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    failure = caught.value
    assert failure.source_error is error and failure.__cause__ is error and error.__cause__ is cause
    assert tuple(failure.partial.completed) == stage.ORDER[: stage.ORDER.index(point)]
    assert (
        h.parent.invalid
        and failure.partial.p is h.p
        and failure.partial.invalid
        and not stage._ACTIVE
        and not stage.paths._ACTIVE
    )
    save(
        tmp_path,
        "failed-load",
        dict(
            primary=error,
            partial=vars(h.p),
            work=failure.partial.work,
            attempted=failure.partial.attempted,
            completed=failure.partial.completed,
            synthetic_only=True,
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "root-replaced",
        "config-root",
        "new-store",
        "grn-loaded",
        "path-change",
        "wrong-config-target",
        "config-mutated",
    ],
)
def test_foreign_parent_wrapper_configuration_or_unrelated_store_refuses(controlled, mutation):
    h = controlled

    def mutate():
        if mutation == "root-replaced":
            h.p.tissue_default = h.classes["SimConfTissueDefault"]()
        elif mutation == "config-root":
            h.p._conf = dict(h.cfg)
        elif mutation == "new-store":
            h.p.autoInit = True
        elif mutation == "grn-loaded":
            h.p.grn._conf = h.cfg
        elif mutation == "path-change":
            h.p.init_pickle_filename = str(h.root / "changed")
        elif mutation == "wrong-config-target":
            h.p.tissue_default._conf = {}
        else:
            h.cfg["foreign"] = "mutated"

    h.hooks["after_tissue_default"] = mutate
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    assert (
        caught.value.source_error is not None
        and h.parent.invalid
        and not stage._ACTIVE
        and not stage.paths._ACTIVE
    )


@pytest.mark.parametrize(
    "mutation", ["omit", "extra", "reuse", "foreign-type", "wrong-raw", "swap-row-order"]
)
def test_list_rows_must_be_fresh_ordered_complete_actual_source_associations(controlled, mutation):
    h = controlled
    values = h.cfg["tissue profile definition"]["cut profiles"]
    a, b = {"name": "a"}, {"name": "b"}
    values.extend((a, b))
    prior = h.classes["SimConfCutListItem"]()
    if mutation == "reuse":
        h.parent.graph = (h.parent.graph[0] + (prior,), {})

    def mutate():
        rows = h.p.cut_profiles._confs_wrap
        if mutation == "omit":
            rows.pop()
        elif mutation == "extra":
            rows.append(h.classes["SimConfCutListItem"]())
        elif mutation == "reuse":
            prior._conf = a
            rows[0] = prior
        elif mutation == "foreign-type":
            rows[0].__class__ = h.classes["SimConfTissueListItem"]
        elif mutation == "wrong-raw":
            rows[0]._conf = dict(a)
        else:
            rows.reverse()

    h.hooks["after_cut_profiles"] = mutate
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    assert caught.value.source_error is not None and h.parent.invalid
    assert not stage._ACTIVE and not stage.paths._ACTIVE


@pytest.mark.parametrize("operation", ["mkdir", "file-write", "rename"])
def test_all_subconfiguration_filesystem_mutation_attempts_refuse(controlled, tmp_path, operation):
    h = controlled
    target = tmp_path / "forbidden"

    def write():
        if operation == "mkdir":
            os.mkdir(target)
        elif operation == "file-write":
            target.write_text("forbidden")
        else:
            os.rename(h.file.filename, target)

    h.hooks["cut_profiles"] = write
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    assert (
        type(caught.value.source_error) is ValueError
        and not target.exists()
        and Path(h.file.filename).is_file()
    )
    save(tmp_path, "blocked-write", dict(error=caught.value, path_writes=0, synthetic_only=True))


@pytest.mark.parametrize("swallow", [False, True])
def test_reentry_never_reloads_or_issues_child(controlled, swallow):
    h = controlled
    request = h.request()
    inner = []

    def nested():
        try:
            stage.prepare(request, enabled=True)
        except stage.SubconfigurationsRejected as error:
            inner.append(error)
            if not swallow:
                raise

    h.hooks["tissue_default"] = nested
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        stage.prepare(request, enabled=True)
    assert (
        inner[0].stage == "reentrant"
        and h.calls.count("cut_profiles") == 1
        and caught.value.partial.invalid
    )
    assert not stage._ACTIVE and not stage.paths._ACTIVE


def test_original_constructor_observation_is_required_before_handoff(controlled, monkeypatch):
    h = controlled
    monkeypatch.setattr(stage, "_canonical", ORIGINAL_CANONICAL)
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        h.request()
    assert caught.value.stage == "constructor_authority" and not h.parent.invalid and h.calls == []


def test_actual_row_constructor_budget_is_finite_and_not_case_credit(controlled, monkeypatch):
    h = controlled
    h.cfg["tissue profile definition"]["cut profiles"].extend(({}, {}))
    monkeypatch.setattr(stage, "MAX_NEW_WRAPPERS", 1)
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    assert (
        type(caught.value.source_error) is ValueError
        and len(caught.value.partial.constructed) == 1
        and h.parent.invalid
    )


def test_capture_failure_preserves_all_completed_loads_and_raw_state(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    error = SyntheticCaptureFailure("final snapshot failed")

    def snapshot(value):
        raise error

    monkeypatch.setattr(
        stage.paths.prefix.parameters.inherited.tissue.core.caches, "snapshot", snapshot
    )
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    failure = caught.value
    assert (
        failure.source_error is None
        and failure.__cause__ is error
        and any(e is error for _, e in failure.capture_errors)
    )
    assert (
        tuple(failure.partial.completed) == stage.ORDER
        and failure.partial.p is h.p
        and h.parent.invalid
    )
    save(
        tmp_path,
        "capture-failure",
        dict(
            error=failure, raw=vars(h.p), completed=failure.partial.completed, synthetic_only=True
        ),
    )


@pytest.mark.parametrize("mutation", ["alias", "row", "class", "file", "cache"])
def test_loaded_owner_rejects_later_graph_type_file_and_cache_drift(controlled, mutation):
    h = controlled
    h.cfg["tissue profile definition"]["cut profiles"].append({})
    owner = run(h)
    ctx = stage._ISSUED[owner]
    if mutation == "alias":
        h.p.config = dict(h.cfg)
    elif mutation == "row":
        h.p.cut_profiles._confs_wrap[0]._conf = {}
    elif mutation == "class":
        h.p.csv.__class__ = type("Foreign", type(h.p.csv).__bases__, {})
    elif mutation == "file":
        Path(h.file.filename).chmod(0o644)
    else:
        object.__setattr__(ctx.trial.cache, "descriptor_json", "{}")
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and ctx.invalid


def test_numeric_general_stores_tissue_handler_phase_and_pickle_remain_closed(controlled):
    import pickle

    h = controlled
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        stage.require_parameters(owner)
    assert (
        caught.value.stage == "numeric_parameter_prerequisites"
        and not caught.value.partial["full_Parameters_or_phase_or_INIT_admitted"]
    )
    for value in (owner, request):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)


@pytest.mark.parametrize("change", ["known-root-class", "item-factory"])
def test_exact_native_root_class_and_item_factory_are_retained(controlled, change):
    h = controlled

    def mutate():
        if change == "known-root-class":
            h.p.tissue_default.__class__ = h.classes["SimConfExportVisual"]
        else:
            h.p.cut_profiles._item_type = h.classes["SimConfTissueListItem"]

    point = "after_tissue_default" if change == "known-root-class" else "after_cut_profiles"
    h.hooks[point] = mutate
    with pytest.raises(stage.SubconfigurationsRejected) as caught:
        run(h)
    failure = caught.value
    assert type(failure.source_error) is ValueError and h.parent.invalid
    assert str(failure.source_error).startswith(
        "Retained native wrapper class changed"
        if change == "known-root-class"
        else "Retained native item factory changed"
    )
    assert not stage._ACTIVE and not stage.paths._ACTIVE


@pytest.mark.parametrize("source_failure", [False, True])
def test_profiled_return_error_never_masks_source_capture_stop(
    controlled, tmp_path, source_failure
):
    h = controlled
    primary = stage.paths.prefix.parameters.inherited.tissue._CaptureStop(
        "native-shaped source stop"
    )
    cause = SyntheticSourceCause("original load cause")
    secondary = SyntheticCaptureFailure("return observer failed")
    if source_failure:
        h.native_errors.update({id(h.p.tissue_default): primary, "cause": cause})
    previous, trace = sys.getprofile(), sys.gettrace()
    selected = h.p.tissue_default.load.__func__.__code__
    seen = []

    def prior(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if (
            frame.f_code is selected
            and frame.f_locals.get("self") is h.p.tissue_default
            and event == "return"
        ):
            seen.append(event)
            raise secondary

    sys.setprofile(prior)
    try:
        with pytest.raises(stage.SubconfigurationsRejected) as caught:
            run(h)
        assert sys.getprofile() is prior and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
    failure = caught.value
    assert seen == ["return"] and failure.source_error is (primary if source_failure else None)
    assert failure.__cause__ is (primary if source_failure else secondary)
    if source_failure:
        assert primary.__cause__ is cause
    assert any(error is secondary for _, error in failure.capture_errors)
    assert tuple(failure.partial.completed) == stage.ORDER[: 1 if source_failure else 2]
    assert h.parent.invalid and "tissue_profiles" not in h.calls
    save(
        tmp_path,
        "source-and-return-observer",
        dict(
            primary=failure.source_error,
            capture=failure.capture_errors,
            partial=failure.partial.locals,
            completed=failure.partial.completed,
            synthetic_only=True,
        ),
    )


def test_preopened_subconfiguration_file_writer_refuses_before_content_write(controlled, tmp_path):
    h = controlled
    target = tmp_path / "preopened"
    with target.open("w") as stream:
        h.hooks["cut_profiles"] = lambda: stream.write("forbidden")
        with pytest.raises(stage.SubconfigurationsRejected) as caught:
            run(h)
    assert type(caught.value.source_error) is ValueError
    assert str(caught.value.source_error) == "Subconfiguration file writer refused"
    assert target.read_bytes() == b"" and h.parent.invalid
