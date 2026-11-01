"""Issued synthetic world chains; original bodies/helpers/operators stay blocked."""

import ast
import hashlib
import os
import pickle
import runpy
from dataclasses import replace
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_multi_cell_post_world_operators as stage
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

world = stage.world
HELPER = Path(__file__).with_name("test_betse_native_multi_cell_world_finalization.py")
helpers = SimpleNamespace(**runpy.run_path(str(HELPER)))


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_POST_WORLD_EVIDENCE", str(tmp_path)))
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(parents=True, exist_ok=False)
    save(
        path,
        "case",
        dict(
            nodeid=request.node.nodeid,
            synthetic_only=True,
            native_execution=False,
            parent_helper_sha256=hashlib.sha256(HELPER.read_bytes()).hexdigest(),
        ),
    )
    return path


def fixture(monkeypatch, *, failure=None, issued_chain=False):
    if issued_chain:
        h = helpers.issued_multi_chain(monkeypatch)
    else:
        h = helpers.fixture(monkeypatch)
    parent = world.prepare_continuation(world.from_poisson(h.owner, law_id=world.LAW_ID))
    context = world._authority(parent)
    prefix = world._prefix(context)
    events, hooks, errors = [], {}, {}
    arrays = {
        "nn_mids": np.asarray([[0.0, 0.0], [1.0, 1.0]]),
        "nn_tx": np.asarray([0.0, 1.0]),
        "nn_ty": np.asarray([0.0, 0.0]),
        "nn_len": np.asarray([-1.0, 2.0]),
        "nn_edges": np.asarray([[[0.0, 0.0], [0.0, 0.0]], [[0.0, 0.0], [1.0, 1.0]]]),
        "cell_nn_tx": np.asarray([0.0, 1.0]),
        "cell_nn_ty": np.asarray([0.0, 0.0]),
        "cell_to_nn_full": np.asarray([[], []], dtype=object),
        "lapGJinv": np.asarray([[2.0, 0.0], [0.0, 2.0]]),
        "lapGJ": np.asarray([[1.0, 0.0], [0.0, 1.0]]),
        "geom_weight": np.asarray([3.0, 4.0]),
    }

    def fail(where):
        if where == failure:
            cause = SyntheticSourceCause("post-world original cause")
            error = SyntheticSourceFailure("post-world source failure at " + where)
            errors.update(source=error, cause=cause)
            raise error from cause

    def probe(where, actual, p):
        assert actual is prefix.caller and p is prefix.p
        events.append(where)
        if where in hooks:
            hooks[where]()
        fail(where)

    namespace = dict(stage.source.__dict__, probe=probe, arrays=arrays)
    exec(
        compile(
            "def calc_gj_vects(self,p):\n"
            "    probe('vectors_before',self,p)\n"
            "    self.nn_mids=np.asarray(arrays['nn_mids'])\n"
            "    for name in ('nn_tx','nn_ty','nn_len','nn_edges',"
            "'cell_nn_tx','cell_nn_ty','cell_to_nn_full'):\n"
            "        setattr(self,name,arrays[name])\n"
            "    probe('vectors_after',self,p)\n"
            "def graphLaplacian(self,p):\n"
            "    probe('graph_before',self,p)\n"
            "    logs.log_debug('synthetic graph marker')\n"
            "    self.lapGJinv=arrays['lapGJinv']\n"
            "    self.lapGJ=arrays['lapGJ']\n"
            "    self.geom_weight=arrays['geom_weight']\n"
            "    probe('graph_after',self,p)\n",
            "<synthetic-post-world>",
            "exec",
        ),
        namespace,
    )
    monkeypatch.setattr(stage, "_NATIVE", {name: namespace[name] for name in stage.METHODS})

    def asarray(value, *a, **k):
        events.append("asarray_delegate")
        fail("asarray")
        return value

    def forbidden(*a, **k):
        raise AssertionError("No real numerical operator in a synthetic control")

    monkeypatch.setattr(
        stage, "_HELPERS", dict(asarray=asarray, sqrt=forbidden, diag=forbidden, dot=forbidden)
    )
    monkeypatch.setattr(stage, "_LOG", lambda *a: None)
    return SimpleNamespace(
        parent=parent,
        parent_context=context,
        prefix=prefix,
        caller=prefix.caller,
        p=prefix.p,
        rng=prefix.rng,
        events=events,
        hooks=hooks,
        errors=errors,
        arrays=arrays,
    )


def continuation(h):
    return stage.from_world(h.parent, law_id=stage.LAW_ID)


def test_software_ast_real_source_leaf_bodies_roster_and_no_new_solver(evidence):
    save(evidence, "source-pins", stage._verify_sources())
    assert stage._NATIVE["calc_gj_vects"] is stage.vectors.CellKernel.calc_gj_vects
    assert stage.METHODS == ("calc_gj_vects", "graphLaplacian")
    tree = ast.parse(Path(stage.source.__file__).read_text())
    calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not any("pinv" in name or "solve" in name for name in calls)
    assert {"np.diag", "np.dot"} <= calls
    assert len(stage.STORES) == 11 and len(stage.INVALIDATED_OWNERS) == 11


def test_software_smoke_same_actual_world_two_methods_partial_defaults_and_no_admission(
    monkeypatch, evidence
):
    h = fixture(monkeypatch)
    original = dict(vars(h.caller))
    owner = stage.prepare_continuation(continuation(h))
    c = stage._authority(owner)
    assert owner.cells is h.caller and c.parent is h.parent_context
    assert c.prior_trial is h.parent.trial
    assert h.events == [
        "vectors_before",
        "asarray_delegate",
        "vectors_after",
        "graph_before",
        "graph_after",
    ]
    assert c.applied == list(stage.METHODS) and set(c.output_values) == set(stage.STORES)
    for name, value in original.items():
        if name not in stage.STORES:
            assert getattr(h.caller, name) is value
    assert (
        h.caller.nn_len[0] == -1 and h.caller.M_sum_mem_to_ecm is None and h.caller.gradMem is None
    )
    assert owner.trial.stream_before.identity == owner.trial.stream_after.identity
    with pytest.raises(world.FinalizationRejected, match="consumed"):
        _ = h.parent.cells
    with pytest.raises(stage.PostWorldRejected, match="unavailable"):
        c.methods[stage.METHODS[0]](h.caller, h.p)
    with pytest.raises(stage.PostWorldRejected) as incomplete:
        stage.require_normal_ecm_field(owner)
    assert incomplete.value.stage == "normal_ecm_prerequisites"
    with pytest.raises(TypeError):
        pickle.dumps(owner)
    save(evidence, "trial", owner.trial)
    save(evidence, "remaining-dependencies", incomplete.value)


def test_software_smoke_real_issued_multi_API_chain_keeps_original_descriptor_and_caller(
    monkeypatch, evidence
):
    h = fixture(monkeypatch, issued_chain=True)
    p, mesh, grid, mask, rng = h.p, h.caller.mesh, h.caller.grid_obj, h.prefix.mask, h.rng
    owner = stage.prepare_continuation(continuation(h))
    assert owner.cells is h.caller and h.prefix.p is p and h.prefix.rng is rng
    assert h.caller.mesh is mesh and h.caller.grid_obj is grid and mesh.image_mask is mask
    stage.aliases.validate(h.prefix.parameter_info)
    assert stage._env(stage._authority(owner)).descriptor_read_completed
    save(evidence, "issued-chain-trial", owner.trial)


@pytest.mark.parametrize("kind", ["mapping", "unissued", "law", "identity"])
def test_software_request_refusal_has_no_consumption_or_delegate(monkeypatch, evidence, kind):
    h = fixture(monkeypatch)
    with pytest.raises(world.FinalizationRejected) as caught:
        if kind == "mapping":
            stage.prepare_continuation(dict(world_owner=h.parent))
        elif kind == "unissued":
            stage.from_world(object.__new__(world.WorldDataOwner), law_id=stage.LAW_ID)
        elif kind == "law":
            stage.from_world(h.parent, law_id="ordinary_field_bridge")
        else:
            stage.prepare_continuation(replace(continuation(h), identity="changed"))
    assert h.parent not in world._FORWARDED and h.events == []
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize(
    "where", ["vectors_before", "vectors_after", "graph_before", "graph_after", "asarray"]
)
def test_software_source_failure_keeps_actual_partials_cause_and_irreversible_world(
    monkeypatch, evidence, where
):
    h = fixture(monkeypatch, failure=where)
    request = continuation(h)
    with pytest.raises(stage.PostWorldRejected) as caught:
        stage.prepare_continuation(request)
    error = caught.value
    assert error.source_error is h.errors["source"] and error.__cause__ is h.errors["source"]
    assert error.source_error.__cause__ is h.errors["cause"]
    assert error.partial["caller"] is h.caller and error.partial["parent_trial"] is h.parent.trial
    assert error.partial["world_consumed"] and not error.trial.source_completed
    if where.startswith("graph"):
        assert "calc_gj_vects" in error.partial["completed_methods"]
    with pytest.raises(world.FinalizationRejected):
        stage.prepare_continuation(request)
    with pytest.raises(stage.PostWorldRejected, match="unavailable"):
        error.partial["context"].methods[stage.METHODS[0]](h.caller, h.p)
    save(evidence, "failure", error)


@pytest.mark.parametrize(
    "kind",
    [
        "world_registry",
        "world_claim",
        "caller_registry",
        "caller_claim",
        "observer",
        "rng_observer",
        "binding",
        "output_value",
        "output_identity",
    ],
)
def test_software_completed_authority_or_buffer_drift_refuses(monkeypatch, evidence, kind):
    h = fixture(monkeypatch)
    owner = stage.prepare_continuation(continuation(h))
    c = stage._authority(owner)
    env = stage._env(c)
    if kind == "world_registry":
        monkeypatch.delitem(world._ISSUED, h.parent)
    elif kind == "world_claim":
        monkeypatch.setitem(world._FORWARDED, h.parent, object())
    elif kind == "caller_registry":
        monkeypatch.delitem(stage.multi._ISSUED, env.request.caller_owner)
    elif kind == "caller_claim":
        monkeypatch.setitem(stage.multi._FORWARDED, env.request.caller_owner, object())
    elif kind == "observer":
        h.prefix.kernel._cells_observer = object()
    elif kind == "rng_observer":
        h.prefix.kernel._cells_rng.observer = object()
    elif kind == "binding":
        monkeypatch.setattr(world, "_check_inherited", lambda *a: None)
    elif kind == "output_value":
        h.caller.lapGJ[0, 0] += 1
    else:
        h.caller.lapGJ = h.caller.lapGJ.copy()
    with pytest.raises(world.FinalizationRejected) as caught:
        _ = owner.cells
    save(evidence, "drift-refusal", caught.value)


@pytest.mark.parametrize(
    "where", ["calc_gj_vects_enter", "asarray_enter", "asarray_return", "graphLaplacian_unwind"]
)
def test_software_observation_failure_blocks_later_work_and_keeps_primary(
    monkeypatch, evidence, where
):
    h = fixture(monkeypatch, failure="graph_after" if where.endswith("unwind") else None)
    original = stage.environment._observe
    capture = SyntheticCaptureFailure("post-world observation capture")

    def observe(context, kind, raw):
        if kind == where:
            stage.geometry._remember_observation_error(context, capture, origin=where, raw=raw)
        else:
            original(context, kind, raw)

    monkeypatch.setattr(stage.environment, "_observe", observe)
    with pytest.raises(stage.PostWorldRejected) as caught:
        stage.prepare_continuation(continuation(h))
    error = caught.value
    assert error.capture_error is capture and error.trial is None
    if where == "calc_gj_vects_enter":
        assert h.events == []
    if where == "asarray_enter":
        assert "asarray_delegate" not in h.events
    if where == "asarray_return":
        assert "vectors_after" not in h.events
        assert error.partial["last_completed_helper"][0] == "asarray"
    if where.endswith("unwind"):
        assert error.source_error is h.errors["source"]
    save(evidence, "capture-failure", error)


@pytest.mark.parametrize("where", ["baseline", "sealing", "native_sealing", "issuance"])
def test_software_capture_and_sealing_failure_never_issue_or_rearm(monkeypatch, evidence, where):
    h = fixture(monkeypatch, failure="graph_after" if where == "native_sealing" else None)
    request = continuation(h)
    capture = SyntheticCaptureFailure("post-world " + where)
    count = len(stage._ISSUED)
    snapshot = stage._snapshot

    def fail(context):
        if (
            where == "baseline"
            or context.finished
            or where == "native_sealing"
            and context.stage == "graphLaplacian"
        ):
            raise capture
        return snapshot(context)

    if where == "issuance":
        monkeypatch.setattr(stage, "_graphs", lambda *a: (_ for _ in ()).throw(capture))
    else:
        monkeypatch.setattr(stage, "_snapshot", fail)
    with pytest.raises(stage.PostWorldRejected) as caught:
        stage.prepare_continuation(request)
    error = caught.value
    assert error.capture_error is capture and len(stage._ISSUED) == count
    assert error.partial["caller"] is h.caller
    if where == "baseline":
        assert h.parent not in world._FORWARDED and error.trial is None
    elif where == "native_sealing":
        assert h.parent in world._FORWARDED and error.source_error is h.errors["source"]
        assert error.__cause__ is h.errors["source"]
        assert error.source_error.__cause__ is h.errors["cause"]
        assert set(error.partial["outputs"]) == set(stage.OUTPUTS["calc_gj_vects"])
        assert h.caller.lapGJ is h.arrays["lapGJ"]
    else:
        assert h.parent in world._FORWARDED and set(error.partial["outputs"]) == set(stage.STORES)
    save(evidence, "sealing-failure", error)


@pytest.mark.parametrize("kind", ["stale", "broken_link"])
def test_software_capture_and_sealing_early_refusal_keeps_primary_without_baseline(
    monkeypatch, evidence, kind
):
    h = fixture(monkeypatch)
    request = continuation(h)
    trial = h.parent.trial
    if kind == "stale":
        h.parent_context.invalid = True
    else:
        h.parent_context.parent = None
    with pytest.raises(stage.PostWorldRejected) as caught:
        stage.prepare_continuation(request)
    error = caught.value
    assert error.trial is None and error.source_error is not None
    assert error.__cause__ is error.source_error and error.capture_error is None
    assert error.partial["parent"] is h.parent_context
    assert error.partial["parent_trial"] is trial
    assert h.events == [] and h.parent not in world._FORWARDED
    save(evidence, "early-refusal", error)


def test_software_reentrant_attempt_cannot_rearm_parent_or_enter_second_body(monkeypatch, evidence):
    h = fixture(monkeypatch)
    request = continuation(h)
    nested = []

    def reenter():
        with pytest.raises(world.FinalizationRejected) as caught:
            stage.prepare_continuation(request)
        nested.append(caught.value)

    h.hooks["vectors_before"] = reenter
    owner = stage.prepare_continuation(request)
    assert len(nested) == 1 and owner.cells is h.caller and h.events.count("vectors_before") == 1
    save(evidence, "reentry-refusal", nested[0])
    save(evidence, "valid-trial", owner.trial)


def _helper_dispatcher_fixture(monkeypatch):
    h = fixture(monkeypatch)

    def implementation(value):
        h.events.append("diag_delegate")
        return value

    class Dispatcher:
        def __init__(self):
            self.__wrapped__ = implementation
            self._implementation = implementation

        def __call__(self, *a, **k):
            h.events.append("diag_dispatcher")
            return self._implementation(*a, **k)

    dispatcher = Dispatcher()
    monkeypatch.setitem(stage._HELPERS, "diag", dispatcher)
    namespace = dict(
        stage.source.__dict__,
        arrays=h.arrays,
        probe=lambda where, actual, p: (h.events.append(where), h.hooks.get(where, lambda: None)()),
    )
    exec(
        compile(
            """
def graphLaplacian(self,p):
    probe('graph_before',self,p)
    self.lapGJinv=np.diag(arrays['lapGJinv'])
    self.lapGJ=arrays['lapGJ']
    self.geom_weight=arrays['geom_weight']
    probe('graph_after',self,p)
""",
            "<synthetic-dispatcher-operator>",
            "exec",
        ),
        namespace,
    )
    monkeypatch.setitem(stage._NATIVE, "graphLaplacian", namespace["graphLaplacian"])
    return h, dispatcher


@pytest.mark.parametrize("attribute", ["__wrapped__", "_implementation"])
@pytest.mark.parametrize("mutation", ["code", "identity"])
@pytest.mark.parametrize("when", ["before_helper", "completed"])
def test_software_completed_authority_helper_binding_dispatcher_layers(
    monkeypatch, evidence, attribute, mutation, when
):
    h, dispatcher = _helper_dispatcher_fixture(monkeypatch)
    unchanged = stage.aliases._atoms(dispatcher)
    outer_code = type(dispatcher).__call__.__code__
    delegates = tuple(stage._HELPERS.values()) + stage._HELPERS_current()
    source_pins = stage._verify_sources()

    def mutate():
        target = getattr(dispatcher, attribute)
        if mutation == "code":

            def forbidden(value):
                h.events.append("forbidden_replacement")
                raise AssertionError("Mutated implementation must not execute")

            assert target.__code__.co_freevars == forbidden.__code__.co_freevars
            monkeypatch.setattr(target, "__code__", forbidden.__code__)
        else:
            replacement = FunctionType(
                target.__code__,
                target.__globals__,
                target.__name__,
                target.__defaults__,
                target.__closure__,
            )
            assert replacement.__code__ is target.__code__ and replacement is not target
            monkeypatch.setattr(dispatcher, attribute, replacement)
        assert type(dispatcher).__call__.__code__ is outer_code
        actual = stage.aliases._atoms(dispatcher)
        assert len(actual) == len(unchanged) and all(
            a is b for a, b in zip(actual, unchanged, strict=True)
        )
        current = tuple(stage._HELPERS.values()) + stage._HELPERS_current()
        assert all(a is b for a, b in zip(current, delegates, strict=True))
        assert stage._verify_sources() == source_pins

    request = continuation(h)
    if when == "before_helper":
        h.hooks["graph_before"] = mutate
        with pytest.raises(stage.PostWorldRejected) as caught:
            stage.prepare_continuation(request)
        error = caught.value
        assert error.partial["world_consumed"]
        assert error.partial["completed_methods"] == ["calc_gj_vects"]
        assert h.events.count("diag_dispatcher") == h.events.count("diag_delegate") == 0
        assert "graph_after" not in h.events
        saved = dict(
            error=error,
            source_error=error.source_error,
            trial=error.trial,
            completed=error.partial["completed_methods"],
            events=h.events,
        )
    else:
        owner = stage.prepare_continuation(request)
        assert owner.cells is h.caller
        assert h.events.count("diag_delegate") == 1
        context = stage._authority(owner)
        before = stage._snapshot(context).identity
        mutate()
        assert stage._snapshot(context).identity == before
        with pytest.raises(stage.PostWorldRejected) as caught:
            _ = owner.cells
        assert h.events.count("diag_dispatcher") == h.events.count("diag_delegate") == 1
        saved = dict(
            error=caught.value,
            source_error=caught.value.source_error,
            trial=owner.trial,
            events=h.events,
            cache_before=before,
        )
    assert "forbidden_replacement" not in h.events
    assert getattr(dispatcher, attribute) is not None
    save(evidence, "helper-binding-refusal", saved)


def test_software_completed_authority_helper_binding_actual_numpy_diag_metadata_only(
    monkeypatch, evidence
):
    dispatcher = stage.source.np.diag
    implementation = dispatcher._implementation
    original_code = implementation.__code__
    baseline = stage._bindings()
    outer = stage.aliases._atoms(dispatcher)
    current_helpers = stage._HELPERS_current()

    def forbidden(*args, **kwargs):
        raise AssertionError("No actual or altered NumPy diag execution")

    assert original_code.co_freevars == forbidden.__code__.co_freevars == ()
    monkeypatch.setattr(implementation, "__code__", forbidden.__code__)
    assert stage.source.np.diag is dispatcher and dispatcher._implementation is implementation
    assert all(a is b for a, b in zip(stage.aliases._atoms(dispatcher), outer, strict=True))
    assert all(a is b for a, b in zip(stage._HELPERS_current(), current_helpers, strict=True))
    with pytest.raises(ValueError):
        stage.multi.accounting._check_binding_identity(stage._bindings(), baseline)
    save(
        evidence,
        "numpy-diag-code-binding",
        dict(
            outer_identity_unchanged=True,
            implementation_identity_unchanged=True,
            implementation_code_changed=True,
            native_helper_calls=0,
            binding_refusal=True,
        ),
    )
