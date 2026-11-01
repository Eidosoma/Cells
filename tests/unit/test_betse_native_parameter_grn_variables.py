"""Conditional ownership/observation models; actual GRN/float/parser stays held."""

import hashlib
import json
import sys
from dataclasses import replace
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_grn_variables as stage
from tests.unit import test_betse_native_parameter_network_load as earlier
from tests.unit import test_betse_native_parameter_subconfigurations as original
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ORIGINAL_COMPILE, ORIGINAL_AUTHORITY = stage._compile, stage._authority


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    inherited = earlier.blocked.__wrapped__(monkeypatch, request, tmp_path)
    next(inherited)
    old, trace = sys.getprofile(), sys.gettrace()
    forbidden, attempted = stage._invoke.__code__, []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code is forbidden:
            attempted.append("actual_GRN_variables_source")
            raise AssertionError("Original GRN/parser/variable source work forbidden")
        if old is not None:
            old(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
        assert attempted == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(old)
        try:
            next(inherited)
        except StopIteration:
            pass
        p = tmp_path / "native-blocked.json"
        row = json.loads(p.read_text())
        row["attempted"].extend(attempted)
        p.write_text(json.dumps(row))


@pytest.fixture(scope="module")
def plan():
    return stage.source_plan()


@pytest.fixture
def controlled(monkeypatch, tmp_path, request):
    scenario = getattr(request, "param", "enabled")
    selected = scenario != "disabled"
    file_path = tmp_path / "selected-grn.yaml"
    data = b"declared-only: not-parsed-by-this-control\n"
    file_path.write_bytes(data)
    file_path.chmod(0o444)
    file = stage.prefix.input_file(
        file_path,
        sha256=hashlib.sha256(data).hexdigest(),
        origin="synthetic immutable bytes, not native GRN derivation",
    )
    calls, hooks, errors, state, box = [], {}, {}, {}, {}
    flag = "foreign" if scenario == "foreign-flag" else selected
    boundary_values = {"Na": 140.0, "K": 5.0, "Cl": 110.0, "Ca": 2.0, "M": 0.0, "P": 0.0}
    settings = {
        "gene regulatory network simulated": flag,
        "gene regulatory network config": "selected-grn.yaml",
        "sim-grn settings": {
            "time step": "0.01",
            "total time": "10.0",
            "sampling rate": "1.0",
            "run as sim": False,
        },
    }
    variables = {
        "temperature": "300.0",
        "use Goldman calculator": False,
        "deformation": {
            "turn on": False,
            "galvanotropism": "0.0",
            "fixed cluster boundary": False,
            "young modulus": "100.0",
            "viscous damping": "1.0",
        },
        "pressures": {"include osmotic pressure": False, "membrane water conductivity": "0.0"},
        "gap junctions": {
            "gap junction surface area": "1.0",
            "gj voltage threshold": "0.02",
            "gj voltage window": "0.01",
            "gj minimum": "0.0",
            "voltage sensitive gj": False,
        },
        "tight junction scaling": "1.0",
        "adherens junction scaling": "1.0",
        "tight junction relative diffusion": dict.fromkeys(
            ("Na", "K", "Cl", "Ca", "M", "P"), "1.0"
        ),
        "env boundary concentrations": boundary_values,
        "noise": {
            "static noise level": "0.0",
            "dynamic noise": False,
            "dynamic noise level": "0.0",
        },
    }

    def fail(point):
        if errors.get("point") == point:
            raise errors["primary"] from errors.get("cause")

    def attach(self, conf):
        calls.append("attach")
        fail("attach")
        self._conf = dict(conf) if state.get("copy-decoded") else conf

    def filename(self, conf_filename):
        calls.append("filename")
        fail("filename")
        self._conf_filename = conf_filename
        self._conf_basename = Path(conf_filename).name
        self._conf_dirname = str(Path(conf_filename).parent)

    def file_load(self, conf_filename, **kwargs):
        calls.append("file_load")
        fail("file_load")
        value = box["loader"](filename=conf_filename, **kwargs)
        attach(self, conf=value)
        if not state.get("skip-filename"):
            filename(self, conf_filename)

    def grn_load(self, *args, **kwargs):
        calls.append("grn_load")
        fail("grn_load")
        file_load(self, *args, **kwargs)

    if scenario == "wrapped":

        def wrap(raw):
            @wraps(raw)
            def wrapped(*args, **kwargs):
                return raw(*args, **kwargs)

            return wrapped

        grn_load, file_load, attach, filename = (
            wrap(fn) for fn in (grn_load, file_load, attach, filename)
        )
    base = original.controlled.__wrapped__

    def configured(*args, **kwargs):
        h = base(*args, **kwargs)
        # Declared conditional configuration before any seven-load/numeric/
        # event/network child is issued. This never grants native path authority.
        h.cfg.update({"gene regulatory network settings": settings, "variable settings": variables})
        h.p.grn_config_filename = file.filename
        policy = tuple(
            (name, file.filename if name == "grn_config_filename" else value)
            for name, value in h.parent.request.policy.paths
        )
        h.parent.request.policy = stage.subconfigs.paths.declare_paths(
            paths=policy, law_id=stage.subconfigs.paths.LAW_ID
        )
        path_trial = stage.subconfigs.paths.Trial(
            "conditional_path_request",
            "conditional_read_parent",
            h.parent.trial.cache,
            (),
            (),
            (),
            True,
            True,
            "",
        )
        h.parent.trial = replace(
            path_trial, identity=stage._digest(stage.subconfigs.paths.trial_record(path_trial))
        )
        h.classes["SimConfGrnFile"].load = grn_load
        return h

    monkeypatch.setattr(original.controlled, "__wrapped__", configured)
    network = earlier.controlled.__wrapped__(monkeypatch, tmp_path, SimpleNamespace(param="zero"))
    owner = stage.previous.prepare(network.request(), enabled=True)
    parent = stage.previous._ISSUED[owner]
    # Retain the exact called helper, without pulling its unrelated complete
    # runtime binding namespace into synthetic frame-local JSON evidence.
    box["loader"] = parent.api.roles["load"].function

    class File:
        pass

    class Base:
        pass

    File.load, File._set_conf_filename, Base.load = file_load, filename, attach
    cls = type(parent.p.grn)
    methods = {
        role: SimpleNamespace(
            function=fn,
            raw=stage.prefix.parameters.inherited._chain(fn)[-1],
            chain=stage.prefix.parameters.inherited._chain(fn),
            cls=kind,
            name=name,
        )
        for role, fn, kind, name in (
            ("grn_load", grn_load, cls, "load"),
            ("file_load", file_load, File, "load"),
            ("attach", attach, Base, "load"),
            ("filename", filename, File, "_set_conf_filename"),
        )
    }

    def authority(p):
        assert p is parent
        loaded = p.parent.parent.parent
        return SimpleNamespace(
            grn=p.p.grn, cls=type(p.p.grn), loaded=loaded, path=loaded.parent, birth=p.parent.birth
        )

    monkeypatch.setattr(stage, "_authority", authority)
    monkeypatch.setattr(stage, "_native", lambda context: methods)
    # Fully declared software values. No copied/native float or source law runs.
    values = dict(
        grn_enabled=flag,
        grn_dt=0.01,
        grn_total_time=10.0,
        grn_tsample=1.0,
        grn_runmodesim=False,
        T=300.0,
        GHK_calc=False,
        fluid_flow=False,
        mu_water=0.01,
        sim_eosmosis=False,
        deformation=False,
        galvanotropism=0.0,
        td_deform=False,
        fixed_cluster_bound=False,
        youngMod=100.0,
        mu_tissue=1.0,
        deform_osmo=False,
        aquaporins=0.0,
        poi=0.49,
        lame_mu=1.0,
        lame_lamb=2.0,
        mu_membrane=1.0,
        zeta=-0.07,
        gj_surface=1.0,
        gj_flux_sensitive=False,
        gj_vthresh=0.02,
        gj_vgrad=0.01,
        gj_min=0.0,
        gj_respond_flow=False,
        v_sensitive_gj=False,
        env_type=True,
        cluster_open=True,
        D_tj=1.0,
        D_adh=1.0,
        Dtj_rel=dict.fromkeys(("Na", "K", "Cl", "Ca", "M", "P"), 1.0),
        cbnd=boundary_values,
        channel_noise_level=0.0,
        dynamic_noise=False,
        dynamic_noise_level=0.0,
    )

    def branch(p, **kwargs):
        calls.append("branch")
        if "before" in hooks:
            hooks["before"]()
        p.grn_enabled = flag
        if selected:
            version = kwargs[stage.previous.previous.LOCAL_KEY]
            if state.get("foreign-version"):
                version = version.encode().decode()
            p.grn.load(conf_filename=p.grn_config_filename, yaml_version=version)
        for name, value in tuple(values.items())[1:]:
            fail(name)
            setattr(p, name, value)
        if "after" in hooks:
            hooks["after"]()

    monkeypatch.setattr(stage, "_compile", lambda context: branch)

    def invoke(context):
        context.work.append(
            dict(
                sequence=len(context.work),
                layer="synthetic_GRN_variables_model",
                status="entered_not_native_or_case_credit",
            )
        )
        return context.function(
            context.p, **{stage.previous.previous.LOCAL_KEY: context.parent.bound.version}
        )

    monkeypatch.setattr(stage, "_invoke", invoke)
    monkeypatch.setenv(stage.RELEASE, "1")
    return SimpleNamespace(
        network=network,
        owner=owner,
        parent=parent,
        p=parent.p,
        file=file,
        calls=calls,
        hooks=hooks,
        errors=errors,
        state=state,
        values=values,
        methods=methods,
        selected=selected,
        request=lambda: stage.from_network(
            owner, law_id=stage.LAW_ID, grn_file=file if selected else None
        ),
    )


def run(h):
    return stage.prepare(h.request(), enabled=True)


def empty():
    assert not stage._ACTIVE
    earlier.empty()


def test_exact_contiguous_native_GRN_variable_temperature_and_environment_source(plan):
    assert plan["statement_slice"] == (62, 109) and plan["source_lines"] == (802, 945)
    assert (
        plan["next_source_line"] == 948
        and not plan["constructor_handoff_full_Parameters_phase_INIT_admitted"]
    )
    stores = plan["stores"]
    assert (
        stores.index("grn_enabled")
        < stores.index("T")
        < stores.index("gj_surface")
        < stores.index("cbnd")
    )
    assert stores[-1] == "dynamic_noise_level" and len(stores) == 39


@pytest.mark.parametrize(
    "enabled,local,parent", [(False, "1", "1"), (True, "0", "1"), (True, "1", "0"), (1, "1", "1")]
)
def test_both_release_gates_precede_lookup_or_source(monkeypatch, enabled, local, parent):
    monkeypatch.setenv(stage.RELEASE, local)
    monkeypatch.setenv(stage.previous.RELEASE, parent)
    with pytest.raises(stage.GrnVariablesRejected) as e:
        stage.prepare(None, enabled=enabled)
    assert e.value.stage == "release"
    empty()


@pytest.mark.parametrize("value", [None, {}, object.__new__(stage.previous.NetworkLoadOwner)])
def test_no_supplied_parsed_dictionary_or_retired_seven_load_substitution(value):
    with pytest.raises(stage.previous.NetworkLoadRejected) as e:
        stage.from_network(value, law_id=stage.LAW_ID)
    assert e.value.stage == "owner"
    empty()


@pytest.mark.parametrize("controlled", ["enabled", "disabled", "wrapped"], indirect=True)
def test_conditional_source_owner_order_retirement_and_complete_same_p_graph(controlled, tmp_path):
    h = controlled
    old = dict(vars(h.p))
    grn = h.p.grn
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    context = stage._ISSUED[owner]
    assert owner.parameters is h.p and h.p.grn is grn and h.parent.invalid
    assert all(vars(h.p)[name] is value for name, value in old.items())
    assert tuple(vars(h.p))[len(old) :] == tuple(h.values)
    assert h.p.T == 300.0 and h.p.cbnd is h.values["cbnd"]
    assert tuple(h.p.Dtj_rel) == ("Na", "K", "Cl", "Ca", "M", "P")
    if h.selected:
        assert h.calls == ["branch", "grn_load", "file_load", "attach", "filename"]
        assert h.network.calls == ["branch", "load", "reader", "factory"]
        assert h.p.grn._conf is context.decoded is h.network.decoded
        assert h.p.grn._conf["a"] is h.p.grn._conf["b"]
        assert all(v == 1 for v in context.counts.values()) and context.stream.closed
        if len(h.methods["grn_load"].chain) > 1:
            assert sum(w.get("layer") == "GRN_wrapper_entry" for w in context.work) == 4
    else:
        assert (
            h.calls == ["branch"]
            and all(v == 0 for v in context.counts.values())
            and grn._conf is None
        )
    with pytest.raises(stage.GrnVariablesRejected) as e:
        stage.prepare(request, enabled=True)
    assert e.value.stage == "consumed"
    with pytest.raises(stage.previous.NetworkLoadRejected):
        _ = h.owner.parameters
    with pytest.raises(stage.GrnVariablesRejected) as e:
        stage.require_continuation(owner)
    assert e.value.stage == "next_prerequisite" and e.value.partial["next_source_line"] == 948
    assert not e.value.partial["constructor_handoff_phase_cache_dyna_INIT_admitted"]
    empty()
    save(
        tmp_path,
        "GRN-result",
        dict(
            trial=owner.trial,
            graph=context.graph[1],
            events=context.events,
            work=context.work,
            metadata=context.metadata_work,
            conditional_models_only=True,
            native_entries=0,
        ),
    )


@pytest.mark.parametrize("change", ["missing", "foreign", "unissued"])
def test_enabled_branch_missing_or_foreign_file_refuses_before_source(controlled, tmp_path, change):
    h = controlled
    file = None
    if change == "foreign":
        p = tmp_path / "foreign.yaml"
        data = b"foreign: not-parsed\n"
        p.write_bytes(data)
        p.chmod(0o444)
        file = stage.prefix.input_file(
            p, sha256=hashlib.sha256(data).hexdigest(), origin="foreign declared bytes"
        )
    elif change == "unissued":
        file = replace(h.file)
    expected = (
        stage.prefix.YamlPrefixRejected if change == "unissued" else stage.GrnVariablesRejected
    )
    with pytest.raises(expected) as e:
        stage.from_network(h.owner, law_id=stage.LAW_ID, grn_file=file)
    assert e.value.stage == ("file_association" if change == "foreign" else "file_authority")
    assert h.calls == [] and h.network.calls == ["branch"] and h.parent.invalid
    empty()


@pytest.mark.parametrize("controlled", ["disabled", "foreign-flag"], indirect=True)
def test_unreached_file_and_unsupported_truth_value_are_not_hydrated(controlled):
    h = controlled
    with pytest.raises(stage.GrnVariablesRejected) as e:
        stage.from_network(h.owner, law_id=stage.LAW_ID, grn_file=h.file)
    assert e.value.stage == ("file_route" if not h.selected else "flag_authority")
    assert h.calls == [] and h.network.calls == ["branch"]
    empty()


@pytest.mark.parametrize(
    "point", ["grn_load", "file_load", "load", "reader", "factory", "attach", "filename", "T"]
)
def test_source_failure_retains_original_cause_and_actual_prefix_without_retry(
    controlled, tmp_path, point
):
    h = controlled
    primary = SyntheticSourceFailure("conditional source failure at " + point)
    cause = SyntheticSourceCause("original cause")
    errors = h.network.errors if point in {"load", "reader", "factory"} else h.errors
    errors.update(point=point, primary=primary, cause=cause)
    with pytest.raises(stage.GrnVariablesRejected) as e:
        run(h)
    error = e.value
    assert error.stage == "native_GRN_variables" and error.source_error is primary
    assert error.__cause__ is primary and primary.__cause__ is cause
    assert error.partial.retired and h.parent.invalid and not error.partial.source_completed
    assert h.calls.count("branch") == 1
    if point == "T":
        assert h.p.grn._conf is error.partial.decoded and "T" not in vars(h.p)
    empty()
    save(
        tmp_path,
        "source-failure",
        dict(
            primary=primary,
            secondary=error.capture_errors,
            fields=vars(h.p),
            events=error.partial.events,
            counts=error.partial.counts,
            work=error.partial.work,
        ),
    )


@pytest.mark.parametrize("change", ["foreign-version", "copy-decoded", "skip-filename"])
def test_wrong_epoch_or_missing_actual_attach_publication_never_issues_owner(controlled, change):
    h = controlled
    h.state[change] = True
    with pytest.raises(stage.GrnVariablesRejected) as e:
        run(h)
    assert e.value.partial.retired and h.parent.invalid
    assert e.value.stage == "native_GRN_variables" and e.value.source_error is not None
    if change == "foreign-version":
        assert h.calls == ["branch"] and h.network.calls == ["branch"]
    empty()


@pytest.mark.parametrize("swallow", [False, True])
def test_reentry_poisoned_once_only_parent_no_delegate_replay(controlled, swallow):
    h = controlled
    request = h.request()
    seen = []

    def nested():
        try:
            stage.prepare(request, enabled=True)
        except stage.GrnVariablesRejected as e:
            seen.append(e)
            if not swallow:
                raise

    h.hooks["before"] = nested
    with pytest.raises(stage.GrnVariablesRejected) as e:
        stage.prepare(request, enabled=True)
    assert seen[0].stage == "reentrant" and e.value.partial.invalid
    assert h.calls == ["branch"] and h.parent.invalid
    empty()


@pytest.mark.parametrize("source_failure", [False, True])
def test_return_observer_failure_keeps_source_primary_identity_and_cause(
    controlled, tmp_path, source_failure
):
    h = controlled
    primary = SyntheticSourceFailure("GRN source unwind")
    cause = SyntheticSourceCause("primary cause")
    secondary = SyntheticCaptureFailure("return observer failed")
    if source_failure:
        h.errors.update(point="grn_load", primary=primary, cause=cause)
    prior = sys.getprofile()
    code = h.methods["grn_load"].raw.__code__
    reached = []

    def profile(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if frame.f_code is code and event == "return":
            reached.append(event)
            raise secondary

    sys.setprofile(profile)
    try:
        with pytest.raises(stage.GrnVariablesRejected) as e:
            run(h)
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(prior)
    error = e.value
    assert reached == ["return"] and error.source_error is (primary if source_failure else None)
    assert error.__cause__ is (primary if source_failure else secondary)
    assert any(value is secondary for _, value in error.capture_errors)
    if source_failure:
        assert primary.__cause__ is cause and "T" not in vars(h.p)
    empty()
    save(
        tmp_path,
        "capture-unwind",
        dict(
            primary=error.source_error,
            secondary=error.capture_errors,
            fields=vars(h.p),
            events=error.partial.events,
            work=error.partial.work,
        ),
    )


def test_completed_source_cache_failure_keeps_decoded_and_field_prefix(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    primary = SyntheticCaptureFailure("post-source cache capture")
    original_snapshot = stage.prefix.parameters.inherited.tissue.core.caches.snapshot

    def snapshot(value):
        if sys._getframe(1).f_code is stage.prepare.__code__:
            raise primary
        return original_snapshot(value)

    monkeypatch.setattr(stage.prefix.parameters.inherited.tissue.core.caches, "snapshot", snapshot)
    with pytest.raises(stage.GrnVariablesRejected) as e:
        run(h)
    assert (
        e.value.source_error is None
        and e.value.__cause__ is primary
        and e.value.partial.source_completed
    )
    assert h.p.grn._conf is e.value.partial.decoded and h.p.T == 300.0
    empty()
    save(
        tmp_path,
        "post-source-capture",
        dict(
            primary=e.value.source_error,
            secondary=e.value.capture_errors,
            decoded=e.value.partial.decoded,
            fields=vars(h.p),
            events=e.value.partial.events,
        ),
    )


@pytest.mark.parametrize(
    "change", ["temperature", "env-alias", "GRN-alias", "file", "read-version", "path-trial"]
)
def test_final_graph_owner_layout_environment_alias_and_file_drift_refuse(controlled, change):
    h = controlled
    owner = run(h)
    if change == "temperature":
        h.p.T = 299.0
    elif change == "env-alias":
        h.p.cbnd = dict(h.p.cbnd)
    elif change == "GRN-alias":
        h.p.grn._conf["b"] = list(h.p.grn._conf["a"])
    elif change == "file":
        Path(h.file.filename).chmod(0o644)
    elif change == "read-version":
        h.parent.bound.frame["YAML_VERSION"] = h.parent.bound.version.encode().decode()
    else:
        context = stage._ISSUED[owner]
        object.__setattr__(context.authority.path.trial, "paths_completed", False)
    with pytest.raises(stage.GrnVariablesRejected) as e:
        _ = owner.parameters
    assert e.value.stage == "owner_drift"
    empty()


def test_original_compiler_prepares_exact_slice_and_retained_local_without_invocation(
    controlled, monkeypatch, tmp_path
):
    h = controlled
    function = ORIGINAL_COMPILE(SimpleNamespace(parent=h.parent))
    import ast
    import dis

    _, cls, load, selected = stage._ast()
    assert len(selected) == 47 and selected[0].lineno == 802 and selected[-1].end_lineno == 945
    assert any(
        i.opname == "LOAD_FAST" and i.argval == "YAML_VERSION"
        for i in dis.get_instructions(function)
    )
    assert function.__globals__ is h.parent.bound.original.__globals__
    assert function.__builtins__ is h.parent.bound.original.__builtins__
    assert h.calls == [] and h.network.calls == ["branch"] and not h.parent.invalid
    save(
        tmp_path,
        "compiled-source",
        dict(
            ast=stage._digest(ast.dump(ast.Module(body=selected, type_ignores=[]))),
            native_source_evaluations=0,
            original_local_retained=True,
            source_globals_unchanged=True,
        ),
    )


def test_unavailable_actual_GRN_class_authority_refuses_without_import_or_source(controlled):
    h = controlled
    assert "betse.science.config.grn.confgrn" not in sys.modules
    with pytest.raises(ValueError, match="Actual same-p original GRN constructor/path/read"):
        ORIGINAL_AUTHORITY(h.parent)
    assert h.calls == [] and h.network.calls == ["branch"]


def test_live_requests_and_advanced_owner_never_supply_phase_or_pickle(controlled):
    import pickle

    h = controlled
    request = h.request()
    owner = stage.prepare(request, enabled=True)
    for value in (request, owner):
        with pytest.raises(TypeError, match="cannot be serialized"):
            pickle.dumps(value)
    with pytest.raises(stage.GrnVariablesRejected) as e:
        stage.require_continuation(owner)
    assert not e.value.partial["retired_seven_load_substitution"]
    empty()


def test_software_child_selection_and_environment_restoration(monkeypatch, tmp_path):
    import shlex

    from validation.betse import betse_native_parameter_grn_variables_software as runner

    seen = []
    secondary = SyntheticCaptureFailure("conditional pytest child failure")

    def delegate(function, **bindings):
        assert function is runner.inherited.child and bindings == dict(TEST=runner.TEST)

        def fake_child(output):
            group = runner.os.environ[runner.GROUP_VARIABLE]
            assert output is tmp_path
            assert shlex.split(runner.os.environ["PYTEST_ADDOPTS"]) == ["-k", runner.GROUPS[group]]
            seen.append(group)
            if group == "failures":
                raise secondary
            return 0

        return fake_child

    monkeypatch.setattr(runner.callbacks, "delegate", delegate)
    monkeypatch.setenv("PYTEST_ADDOPTS", "prior-unchanged")
    for group in runner.GROUPS:
        monkeypatch.setenv(runner.GROUP_VARIABLE, group)
        if group == "failures":
            with pytest.raises(SyntheticCaptureFailure) as caught:
                runner.child(tmp_path)
            assert caught.value is secondary
        else:
            assert runner.child(tmp_path) == 0
        assert runner.os.environ["PYTEST_ADDOPTS"] == "prior-unchanged"
    assert seen == ["admission", "failures"]


def test_unselected_software_child_refuses_before_pytest(monkeypatch, tmp_path):
    from validation.betse import betse_native_parameter_grn_variables_software as runner

    calls = []
    monkeypatch.setattr(runner.callbacks, "delegate", lambda *a, **k: calls.append(a))
    for value in (None, "all"):
        if value is None:
            monkeypatch.delenv(runner.GROUP_VARIABLE, raising=False)
        else:
            monkeypatch.setenv(runner.GROUP_VARIABLE, value)
        with pytest.raises(ValueError, match="explicit admission or failures"):
            runner.child(tmp_path)
    assert calls == []


def test_software_guard_forwarding_preserves_policy_and_group(monkeypatch, tmp_path):
    from validation.betse import betse_native_parameter_grn_variables_software as runner

    seen = []
    environment = {"KEEP": "original"}

    def backend(command, **kwargs):
        assert command == ["synthetic-software-only"]
        seen.append(kwargs)
        return dict(status="completed", returncode=0)

    def delegate(function, **bindings):
        assert function is runner.inherited.software and bindings["FILE"] == runner.FILE

        def software(packet, output):
            assert packet == "conditional-packet" and output is tmp_path
            return bindings["guard"].run_bounded(
                ["synthetic-software-only"],
                env=environment,
                directory=tmp_path,
                cwd=tmp_path,
                timeout=480,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
            )

        return software

    monkeypatch.setattr(runner.callbacks, "delegate", delegate)
    monkeypatch.setattr(runner.inherited.guard, "run_bounded", backend)
    for group in runner.GROUPS:
        assert runner.software("conditional-packet", tmp_path, group=group)["returncode"] == 0
    assert len(seen) == 2 and environment == {"KEEP": "original"}
    for row, group in zip(seen, runner.GROUPS, strict=True):
        assert row["env"] == dict(environment, **{runner.GROUP_VARIABLE: group})
        assert row["timeout"] == 480 and row["max_rss_bytes"] == 2**30
        assert row["min_available_bytes"] == 8 * 2**30 and row["cwd"] is tmp_path


def test_software_invalid_group_refuses_before_delegate(monkeypatch, tmp_path):
    from validation.betse import betse_native_parameter_grn_variables_software as runner

    calls = []
    monkeypatch.setattr(runner.callbacks, "delegate", lambda *a, **k: calls.append(a))
    for group in (None, "all"):
        with pytest.raises(ValueError, match="explicit admission or failures"):
            runner.software("nonexistent-packet", tmp_path, group=group)
    assert calls == []


@pytest.mark.parametrize("role", ["reader", "factory", "load"])
@pytest.mark.parametrize("outcome", ["value", "none", "unwind"])
@pytest.mark.parametrize("capture_at", ["locals", "event"])
def test_capture_raw_return_witness_before_observation(
    monkeypatch, tmp_path, role, outcome, capture_at
):
    """Actual profiled synthetic returns, including normal None and unwind."""
    primary = SyntheticSourceFailure("synthetic GRN helper unwind")
    cause = SyntheticSourceCause("original source cause")
    secondary = SyntheticCaptureFailure("fallible return observation")
    data = b"metadata-only: not-parsed\n"
    path = tmp_path / "raw-return.yaml"
    path.write_bytes(data)
    path.chmod(0o444)
    file = stage.prefix.input_file(
        path, sha256=hashlib.sha256(data).hexdigest(), origin="conditional raw stream metadata"
    )

    class Parser:
        def load(self, stream):
            raise AssertionError("No parser evaluation in raw-return controls")

    stream = path.open("rt", encoding="utf-8") if role == "reader" else None
    returned = stream if role == "reader" else Parser() if role == "factory" else {"a": [1, 2]}
    entries = []

    def observed():
        entries.append("entered")
        if outcome == "unwind":
            raise primary from cause
        return None if outcome == "none" else returned

    def unused_load():
        raise AssertionError("Unselected synthetic helper")

    def unused_reader():
        raise AssertionError("Unselected synthetic helper")

    def unused_factory():
        raise AssertionError("Unselected synthetic helper")

    roles = {
        name: SimpleNamespace(raw=fn, chain=(fn,))
        for name, fn in (
            ("load", unused_load),
            ("reader", unused_reader),
            ("factory", unused_factory),
        )
    }
    roles[role] = SimpleNamespace(raw=observed, chain=(observed,))

    class BadEvents(list):
        def append(self, value):
            raise secondary

    context = SimpleNamespace(
        stage="synthetic_GRN_return_control",
        work=[],
        events=BadEvents() if capture_at == "event" else [],
        raw_returns=[],
        raw_return=None,
        locals={},
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        completed=set(),
        decoded=None,
        decoded_observed=False,
        stream=None,
        parser=None,
        request=SimpleNamespace(grn_file=file),
        methods={},
        parent=SimpleNamespace(
            api=SimpleNamespace(roles=roles, parser_type=Parser, parser_method=Parser.load)
        ),
    )
    monkeypatch.setattr(stage, "_entry", lambda *args: None)
    if capture_at == "locals":
        actual_dict = dict

        def copy_locals(*args, **kwargs):
            if args:
                raise secondary
            return actual_dict(*args, **kwargs)

        monkeypatch.setattr(stage, "dict", copy_locals, raising=False)
    profile, trace = sys.getprofile(), sys.gettrace()
    try:
        with stage._observe(context):
            if outcome == "unwind":
                with pytest.raises(SyntheticSourceFailure) as caught:
                    observed()
                assert caught.value is primary and primary.__cause__ is cause
            else:
                assert observed() is (None if outcome == "none" else returned)
        assert sys.getprofile() is profile and sys.gettrace() is trace
        assert entries == ["entered"] and context.observation_error is secondary
        witness = context.raw_returns[0]
        assert len(context.raw_returns) == 1 and context.raw_return is witness
        assert witness[0] == role and witness[1].f_code is observed.__code__
        assert witness[2] is (returned if outcome == "value" else None)
        assert context.observation_raw[0] == role
        assert context.observation_raw[1] is witness[1] and context.observation_raw[2] is witness[2]
        assert context.completed == set() and context.events == []
        assert context.decoded is context.stream is context.parser is None
        assert context.decoded_observed is False
        save(
            tmp_path,
            "raw-GRN-return",
            dict(
                role=role,
                outcome=outcome,
                capture_at=capture_at,
                raw_argument=witness[2],
                frame_file=witness[1].f_code.co_filename,
                frame_function=witness[1].f_code.co_qualname,
                original_primary=primary if outcome == "unwind" else None,
                capture_errors=context.observation_errors,
                exact_raw_identity_checked=True,
                completed_or_verified_owner=False,
                synthetic_helper_entries=1,
                native_entries=0,
            ),
        )
    finally:
        if stream is not None:
            stream.close()


@pytest.mark.parametrize("role", ["reader", "factory", "load"])
@pytest.mark.parametrize("unwind", [False, True])
def test_capture_GRN_payload_failure_keeps_raw_and_original_primary(
    controlled, monkeypatch, tmp_path, role, unwind
):
    h = controlled
    primary = SyntheticSourceFailure("original model helper unwind")
    cause = SyntheticSourceCause("source cause")
    secondary = SyntheticCaptureFailure("GRN return event failure")
    if unwind:
        h.network.errors.update(point=role, primary=primary, cause=cause)
    original_returned = stage._returned

    class BadEvents(list):
        def append(self, value):
            raise secondary

    def returned(context, selected, frame, arg):
        if selected == role:
            context.events = BadEvents(context.events)
        return original_returned(context, selected, frame, arg)

    monkeypatch.setattr(stage, "_returned", returned)
    request = h.request()
    with pytest.raises(stage.GrnVariablesRejected) as caught:
        stage.prepare(request, enabled=True)
    error = caught.value
    assert error.request is request and error.source_error is (primary if unwind else None)
    assert error.__cause__ is (primary if unwind else secondary)
    if unwind:
        assert primary.__cause__ is cause
    context = error.partial
    witness = next(row for row in context.raw_returns if row[0] == role)
    assert witness[1].f_code is h.network.roles[role].raw.__code__
    expected = (
        None
        if unwind
        else h.network.decoded
        if role == "load"
        else h.network.state["stream" if role == "reader" else "parser"]
    )
    assert witness[2] is expected
    assert role not in context.completed and context.observation_error is secondary
    if role == "load":
        assert context.decoded is None and context.decoded_observed is False
    else:
        assert getattr(context, "stream" if role == "reader" else "parser") is None
    assert context.retired and h.parent.invalid and context.source_completed is False
    assert "T" not in vars(h.p) and all(value is not context for value in stage._ISSUED.values())
    empty()
    save(
        tmp_path,
        "raw-GRN-payload-failure",
        dict(
            role=role,
            unwind=unwind,
            request=stage.request_record(request),
            primary=error.source_error,
            secondary=error.capture_errors,
            raw_argument=witness[2],
            fields=vars(h.p),
            events=context.events,
            work=context.work,
            target_verified_owner=False,
            native_entries=0,
        ),
    )


def test_rebound_network_producer_is_exact_and_old_pin_refuses(monkeypatch):
    current = hashlib.sha256(Path(stage.previous.__file__).read_bytes()).hexdigest()
    assert current == stage.PREVIOUS_SHA256
    assert stage.source_plan()["predecessor"] == current
    monkeypatch.setattr(
        stage, "PREVIOUS_SHA256", "4a471d3d5b7e2e29127922fe96efa5789c7c71fe65832a8c170ddef1ebb2d820"
    )
    with pytest.raises(ValueError, match="Exact completed network-load producer"):
        stage.source_plan()


@pytest.mark.parametrize("change", ["class-method", "instance-shadow"])
def test_rebound_parser_binding_and_receiver_are_inherited(
    controlled, monkeypatch, tmp_path, change
):
    h = controlled
    owner = run(h)
    context = stage._ISSUED[owner]
    calls = []

    def foreign(self, stream):
        calls.append(stream)
        raise AssertionError("No parser calls in inherited binding controls")

    if change == "class-method":
        monkeypatch.setattr(type(context.parser), "load", foreign)
    else:
        context.parser.load = context.parser.load
    with pytest.raises(stage.GrnVariablesRejected) as caught:
        _ = owner.parameters
    assert caught.value.stage == "owner_drift" and caught.value.source_error is not None
    assert context.invalid and calls == []
    empty()
    save(
        tmp_path,
        "inherited-parser-binding",
        dict(
            change=change,
            parent_source=stage.PREVIOUS_SHA256,
            error=caught.value.source_error,
            same_p=True,
            native_parser_calls=0,
            owner_refused=True,
        ),
    )
