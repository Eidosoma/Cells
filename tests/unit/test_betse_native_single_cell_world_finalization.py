"""Issued single-cell data-tail controls; real numerical/source entry is forbidden."""

import ast
import hashlib
import os
import pickle
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_world_finalization as tail
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

core, poisson, env = tail.core, tail.poisson, tail.environment


@pytest.fixture
def evidence(request, tmp_path):
    root = Path(os.environ.get("CELLS_WORLD_DATA_EVIDENCE", str(tmp_path)))
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def issued_chain(monkeypatch, tmp_path, *, failure=None, full=False):
    upstream = runpy.run_path(
        str(Path(__file__).with_name("test_betse_native_single_cell_environment.py"))
    )
    h = upstream["harness"](monkeypatch, tmp_path)
    mesh_factory = tail.completion._mesh

    def mesh(image_owner):
        owner = mesh_factory(image_owner)
        context = tail.meshes._authority(owner)
        # The existing counterfactual upstream factory issues a real typed
        # MeshOwner. Retain its actual image-owner request too; no native body,
        # parameter retrofit, scientific state hydration or multi owner is used.
        context.request = tail.meshes.Request(image_owner, context.request.identity)
        context.caller_owner = context.parent_image["request"].caller
        return owner

    monkeypatch.setattr(tail.completion, "_mesh", mesh)
    env_owner = env.prepare(h.request)
    environment = env._authority(env_owner)
    prefix = environment.parent.parent.parent
    original_cell_i = prefix.caller.cell_i
    steps, delegates, hooks, errors = [], [], {}, {}

    def fail(stage):
        if failure == stage:
            try:
                raise SyntheticSourceCause("original synthetic single-cell cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic source failure at " + stage)
                errors.update(source=error, cause=cause)
                raise error from cause

    def matrix(role):
        words = np.asarray(
            [
                role,
                0x8000000000000000,
                0x7FF8000000000042,
                0x7FF0000000000000,
                0x3FF0000000000000 + role,
            ],
            dtype="<u8",
        )
        raw = (words.tobytes() * ((625 * 625 + 4) // 5))[: 625 * 625 * 8]
        return np.frombuffer(raw, dtype="<f8").reshape(625, 625)

    counts = {"zeros": 0, "pinv": 0}

    def zeros(shape):
        counts["zeros"] += 1
        return matrix(10 * counts["zeros"]) if full else np.asarray([[1.0, -0.0], [0.0, 1.0]])

    def pinv(value):
        counts["pinv"] += 1
        return matrix(10 * counts["pinv"] + 2) if full else np.asarray([[2.0, 0.0], [0.0, 2.0]])

    monkeypatch.setattr(poisson, "_ZEROS", zeros)
    monkeypatch.setattr(poisson, "_PINV", pinv)
    values = dict(poisson.source.__dict__)
    exec(
        compile(
            "def environment_voltage(self):\n"
            "    discarded,self.lapENVinv=self.grid_obj.makeLaplacian("
            "bound={'N':'value','S':'value','E':'value','W':'value'})\n"
            "def environment_current(self):\n"
            "    discarded,self.lapENV_P_inv=self.grid_obj.makeLaplacian("
            "bound={'N':'flux','S':'flux','E':'flux','W':'flux'})\n"
            "def operator(self,bound={'N':'value','S':'value','E':'value','W':'value'}):\n"
            "    Z=np.zeros((2,2))\n    A=Z.copy()\n    P=np.linalg.pinv(A)\n    return A,P\n",
            "<synthetic-single-Poisson>",
            "exec",
        ),
        values,
    )
    monkeypatch.setattr(poisson, "_CALLER", {name: values[name] for name in poisson.METHODS})
    monkeypatch.setattr(poisson, "_LAPLACIAN", values["operator"])
    poisson_owner = poisson.prepare_continuation(
        poisson.from_environment(env_owner, law_id=poisson.LAW_ID)
    )

    def image_state(caller):
        tape = caller.mesh_context.parent_image["tape"]
        return core.caches.snapshot(
            dict(mask=vars(tape.mask), hull=vars(tape.hull), locals=tape.locals, events=tape.events)
        )

    monkeypatch.setattr(tail, "_image_state", image_state)

    def asarray(value):
        assert value is original_cell_i
        delegates.append("asarray")
        fail("asarray")
        return np.asarray(value)

    def ones(size):
        assert size == len(prefix.caller.mem_i)
        delegates.append("ones")
        fail("ones")
        return np.asarray([1.0] * size)

    monkeypatch.setattr(tail, "_ASARRAY", asarray)
    monkeypatch.setattr(tail, "_ONES", ones)
    values = dict(tail.source.__dict__)
    statements = (
        "self.lapGJinv=None",
        "self.lapGJ=None",
        "self.M_sum_mem_to_ecm=None",
        "self.gradMem=None",
        "self.cell_i=np.asarray(self.cell_i)",
        "self.gj_default_weights=np.ones(len(self.mem_i))",
    )
    program = "\n".join(
        f"def {name}(self):\n    step('{name}_before',self)\n    {statement}\n"
        f"    step('{name}_after',self)\n"
        for name, statement in zip(tail.METHODS, statements, strict=True)
    )
    exec(compile(program, "<synthetic-single-world-tail>", "exec"), values)
    monkeypatch.setattr(tail, "_NATIVE", {name: values[name] for name in tail.METHODS})
    namespace = tail._namespace

    def methods(context):
        result = namespace(context)

        def step(name, actual):
            assert actual is prefix.caller
            steps.append(name)
            if name in hooks:
                hooks[name](context)
            fail(name)

        for function in result.values():
            function.__globals__["step"] = step
        return result

    monkeypatch.setattr(tail, "_namespace", methods)
    return SimpleNamespace(
        h=h,
        owner=poisson_owner,
        parent=poisson._authority(poisson_owner),
        prefix=prefix,
        original_cell_i=original_cell_i,
        steps=steps,
        delegates=delegates,
        hooks=hooks,
        errors=errors,
    )


def request(h):
    return tail.from_poisson(h.owner, law_id=tail.LAW_ID)


def test_software_literal_six_stores_and_single_cell_authority_roster(evidence):
    save(evidence, "pins", tail._verify_sources())
    assert tail.STORES == (
        "lapGJinv",
        "lapGJ",
        "M_sum_mem_to_ecm",
        "gradMem",
        "cell_i",
        "gj_default_weights",
    )
    assert tail.source.STORE_LINES == (517, 518, 521, 522, 525, 526)
    tree = ast.parse(Path(tail.__file__).read_text())
    assert not any(
        isinstance(node, ast.ImportFrom) and "multi_cell" in str(node.module)
        for node in ast.walk(tree)
    )
    assert len(tail.INVALIDATED_OWNERS) == 11


def test_software_same_caller_six_stores_aliases_operators_and_claim(
    monkeypatch, tmp_path, evidence
):
    h = issued_chain(monkeypatch, tmp_path)
    prior = dict(vars(h.prefix.caller))
    child = tail.prepare_continuation(request(h))
    context = tail._authority(child)
    assert child.cells is h.prefix.caller
    assert all(
        getattr(child.cells, name) is value
        for name, value in prior.items()
        if name not in tail.STORES
    )
    assert child.cells.all_points_cell_i is h.original_cell_i
    assert child.cells.cell_i is not h.original_cell_i
    assert child.cells.cell_i.tolist() == h.original_cell_i
    assert child.cells.gj_default_weights.tolist() == [1.0] * len(child.cells.mem_i)
    assert all(getattr(child.cells, name) is None for name in tail.STORES[:4])
    assert context.applied == list(tail.STORES) and h.delegates == ["asarray", "ones"]
    assert len(tail._scope(context).roots) == 6
    assert child.trial.stream_before.identity == child.trial.stream_after.identity
    for method in tail.METHODS:
        assert sum(row["entry_method"] == method for row in child.trial.work) == 1
    with pytest.raises(poisson.PoissonRejected, match="consumed"):
        _ = h.owner.cells
    with pytest.raises(TypeError):
        pickle.dumps(child)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.require_full_make_world(child, phase=SimpleNamespace())
    assert caught.value.stage == "full_make_world_held"
    save(evidence, "trial", child.trial)
    save(
        evidence,
        "aliases",
        dict(
            old=h.original_cell_i,
            new=child.cells.cell_i,
            all_points_cell_i=child.cells.all_points_cell_i,
            helpers=context.helpers,
            refusal=caught.value,
        ),
    )


def test_software_multi_owner_cannot_supply_single_cell_authority(evidence):
    from cells.processes import betse_native_multi_cell_poisson as other

    with pytest.raises(poisson.PoissonRejected):
        tail.from_poisson(object.__new__(other.PoissonOwner), law_id=tail.LAW_ID)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(dict(parent="cache"))
    save(evidence, "refusal", caught.value)


@pytest.mark.parametrize(
    "where", ["clear_gradMem_before", "coerce_cell_i_after", "asarray", "ones"]
)
def test_software_retention_source_failures_original_parent_and_partial_stores(
    where, monkeypatch, tmp_path, evidence
):
    h = issued_chain(monkeypatch, tmp_path, failure=where)
    supplied = request(h)
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(supplied)
    error = caught.value
    assert (
        error.source_error is h.errors["source"]
        and error.source_error.__cause__ is h.errors["cause"]
    )
    assert error.partial["parent"] is h.parent and error.partial["parent_trial"] is h.parent.trial
    assert error.partial["poisson_consumed"] and not error.trial.source_completed
    assert h.prefix.caller.lapENVinv is h.parent.results[0][1][1]
    assert h.prefix.caller.lapENV_P_inv is h.parent.results[1][1][1]
    assert not any(context.request is supplied for context in tail._ISSUED.values())
    save(evidence, "failure", error)


@pytest.mark.parametrize(
    "kind",
    [
        "cell_i_alias",
        "old_list",
        "operator",
        "RNG",
        "observer",
        "helper",
        "namespace",
        "descriptor",
    ],
)
def test_software_ownership_buffers_bindings_and_epoch(kind, monkeypatch, tmp_path, evidence):
    h = issued_chain(monkeypatch, tmp_path)
    child = tail.prepare_continuation(request(h))
    context = tail._authority(child)
    if kind == "cell_i_alias":
        h.prefix.caller.cell_i = h.prefix.caller.cell_i.copy()
    elif kind == "old_list":
        h.original_cell_i[0] = 99
    elif kind == "operator":
        h.prefix.caller.lapENVinv[0, 0] += 1
    elif kind == "RNG":
        h.prefix.rng.epoch = "changed"
    elif kind == "observer":
        h.prefix.mesh_context.kernel._cells_rng.observer = object()
    elif kind == "helper":
        monkeypatch.setattr(tail, "_ONES", lambda *args: None)
    elif kind == "namespace":
        context.methods[tail.METHODS[0]].__globals__["np"].ones = lambda *args: None
    else:

        def dispatch(self, name):
            if name == "grid_size":
                return 4
            return object.__getattribute__(self, name)

        monkeypatch.setattr(type(h.prefix.p), "__getattribute__", dispatch)
    with pytest.raises(tail.FinalizationRejected) as caught:
        _ = child.cells
    assert context.invalid
    save(evidence, "refusal", caught.value)


def links(h):
    p, e, c, g, f, m, t = tail._parts(SimpleNamespace(parent=h.parent))
    return dict(
        environment=(env._ISSUED, p.request.environment_owner),
        environment_claim=(env._FORWARDED, p.request.environment_owner),
        ecm=(tail.ecm._ISSUED, e.request.ecm_owner),
        ecm_claim=(tail.ecm._FORWARDED, e.request.ecm_owner),
        geometry=(tail.geometry._ISSUED, c.request.geometry_owner),
        geometry_claim=(tail.geometry._FORWARDED, c.request.geometry_owner),
        completion=(tail.completion._ISSUED, g.request.caller_owner),
        completion_claim=(tail.completion._FORWARDED, g.request.caller_owner),
        mesh=(tail.meshes._ISSUED, f.request.mesh_owner),
        mesh_claim=(tail.meshes._FORWARDED, f.request.mesh_owner),
        image=(tail.images._ISSUED, m.request.image_owner),
        caller=(tail.callers._ISSUED, m.parent_image["request"].caller),
        caller_claim=(tail.callers._CONSUMED, m.parent_image["request"].caller),
        parameter=(tail.parameters._ISSUED, f.parameter_owner),
        parameter_claim=(tail.parameters._CLAIMED, f.parameter_owner),
    )


@pytest.mark.parametrize(
    "name",
    [
        "environment",
        "ecm",
        "geometry",
        "completion",
        "mesh",
        "image",
        "caller",
        "parameter",
        "environment_claim",
        "ecm_claim",
        "geometry_claim",
        "completion_claim",
        "mesh_claim",
        "caller_claim",
        "parameter_claim",
    ],
)
def test_software_registry_every_inherited_link_missing_or_replaced(
    name, monkeypatch, tmp_path, evidence
):
    h = issued_chain(monkeypatch, tmp_path)
    child = tail.prepare_continuation(request(h))
    context = tail._authority(child)
    mapping, key = links(h)[name]
    before = tail._snapshot(context).identity
    # Check both faults on the unchanged completed context without re-arming
    # its handle: direct checks do not invalidate; final public use does.
    errors = []
    for mutation in ("remove", "replace"):
        with monkeypatch.context() as change:
            if mutation == "remove":
                change.delitem(mapping, key)
            else:
                change.setitem(mapping, key, object())
            assert tail._snapshot(context).identity == before
            with pytest.raises(Exception) as caught:
                tail._check(context)
            errors.append(caught.value)
    assert child.cells is h.prefix.caller
    monkeypatch.delitem(mapping, key)
    previous = list(h.delegates)
    with pytest.raises(tail.FinalizationRejected) as caught:
        _ = child.cells
    assert context.invalid and h.delegates == previous
    save(
        evidence, "registry", dict(checks=errors, public_refusal=caught.value, cache_before=before)
    )


@pytest.mark.parametrize("name", ["caller", "completion_claim", "ecm_claim", "parameter_claim"])
def test_software_registry_before_next_helper_stops_without_source_delegate(
    name, monkeypatch, tmp_path, evidence
):
    h = issued_chain(monkeypatch, tmp_path)
    mapping, key = links(h)[name]
    proof = {}

    def corrupt(context):
        before = tail._snapshot(context).identity
        monkeypatch.delitem(mapping, key)
        assert tail._snapshot(context).identity == before
        proof["unchanged_cache"] = before

    h.hooks["coerce_cell_i_before"] = corrupt
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(request(h))
    assert proof and h.delegates == []
    assert (
        caught.value.partial["applied"] == list(tail.STORES[:4])
        and caught.value.partial["poisson_consumed"]
    )
    assert caught.value.partial["parent_trial"] is h.parent.trial
    save(evidence, "refusal", caught.value)
    save(evidence, "proof", proof)


@pytest.mark.parametrize("where", ["enter", "return", "unwind", "locals", "seal"])
def test_software_retention_capture_failures_keep_primary_and_no_child(
    where, monkeypatch, tmp_path, evidence
):
    h = issued_chain(monkeypatch, tmp_path, failure="ones" if where == "unwind" else None)
    supplied = request(h)
    capture = SyntheticCaptureFailure("synthetic capture " + where)
    if where in ("enter", "return", "unwind"):
        observe = tail.ecm._observe

        def observer(context, kind, raw):
            if kind == "ones_" + where:
                tail.geometry._remember_observation_error(context, capture, origin=kind, raw=raw)
            else:
                observe(context, kind, raw)

        monkeypatch.setattr(tail.ecm, "_observe", observer)
    elif where == "locals":
        original = tail.geometry._capture_locals

        def local(context, name, frame):
            if name == "clear_lapGJ":
                raise capture
            return original(context, name, frame)

        monkeypatch.setattr(tail.geometry, "_capture_locals", local)
    else:
        record = tail.trial_record

        def fail(trial):
            record(trial)
            raise capture

        monkeypatch.setattr(tail, "trial_record", fail)
    previous = sys.getprofile()
    with pytest.raises(tail.FinalizationRejected) as caught:
        tail.prepare_continuation(supplied)
    error = caught.value
    assert sys.getprofile() is previous and error.capture_error is capture
    assert error.source_error is (h.errors["source"] if where == "unwind" else None)
    assert error.partial["parent_trial"] is h.parent.trial and error.partial["poisson_consumed"]
    assert not any(ctx.request is supplied for ctx in tail._ISSUED.values())
    save(evidence, "failure", error)


@pytest.mark.parametrize("failed_weights", [False, True])
def test_software_full_default_625_operators_and_partial_tail_survive(
    failed_weights, monkeypatch, tmp_path, evidence
):
    h = issued_chain(monkeypatch, tmp_path, full=True, failure="ones" if failed_weights else None)
    if failed_weights:
        with pytest.raises(tail.FinalizationRejected) as caught:
            tail.prepare_continuation(request(h))
        context, trial = caught.value.partial["context"], caught.value.trial
        assert caught.value.source_error is h.errors["source"] and context.applied == list(
            tail.STORES[:5]
        )
    else:
        child = tail.prepare_continuation(request(h))
        context, trial = tail._authority(child), child.trial
        assert child.cells is h.prefix.caller
    scope = tail._scope(context)
    assert len(scope.roots) == 6
    archives = []
    for name, value in scope.roles.items():
        path = evidence / (name + ".npy")
        with path.open("xb") as stream:
            np.save(stream, value, allow_pickle=False)
        archives.append(
            dict(
                name=name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                raw_C_sha256=hashlib.sha256(value.tobytes()).hexdigest(),
                layout=core.caches.layout(value),
            )
        )
    save(
        evidence,
        "capacity",
        dict(
            archives=archives,
            descriptor=trial.cache.descriptor,
            source_completed=trial.source_completed,
            applied=context.applied,
        ),
    )
    assert (
        core.caches.MAX_ARRAY_ELEMENTS,
        core.caches.MAX_TREE_NODES,
        core.caches.MAX_TREE_DEPTH,
    ) == (262144, 262144, 32)
