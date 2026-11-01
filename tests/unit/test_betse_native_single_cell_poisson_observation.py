"""Full default-grid observations; no native operators or reference executions."""

import ast
import hashlib
import importlib.util
import os
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_native_single_cell_poisson as poisson
from cells.processes import betse_native_single_cell_poisson_observation as observation
from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticSourceCause,
    SyntheticSourceFailure,
    save,
)

ROOT = Path(__file__).resolve().parents[2]
HARNESS_MODULE = "_poisson_observation_harness"
spec = importlib.util.spec_from_file_location(
    HARNESS_MODULE, ROOT / "tests/unit/test_betse_native_single_cell_poisson.py"
)
helper = importlib.util.module_from_spec(spec)
sys.modules[HARNESS_MODULE] = helper
spec.loader.exec_module(helper)


@pytest.fixture
def evidence(request, tmp_path):
    path = (
        Path(os.environ.get("CELLS_POISSON_EVIDENCE", str(tmp_path)))
        / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    )
    path.mkdir(parents=True, exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, native_execution=False)
    )
    return path


def matrix(side=625, *, endian="<", role=0):
    # Repeated exact bits, including negative zero, payload NaN and infinities.
    # No random draw, solve, matrix product or native stencil executes.
    words = np.asarray(
        [
            role,
            0x8000000000000000,
            0x7FF8000000000042,
            0x7FF0000000000000,
            0x3FF0000000000000 + role,
        ],
        dtype=endian + "u8",
    )
    raw = (words.tobytes() * ((side * side + 4) // 5))[: side * side * 8]
    return np.frombuffer(raw, dtype=endian + "f8").reshape(side, side)


def archive(path, label, array):
    target = path / (label + ".npy")
    with target.open("xb") as file:
        np.save(file, array, allow_pickle=False)
    save(
        path,
        label + "-layout",
        dict(
            layout=poisson.core.caches.layout(array),
            raw_C_sha256=hashlib.sha256(array.tobytes(order="C")).hexdigest(),
            file_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        ),
    )


@pytest.mark.parametrize("layout", ["C", "F", "negative", "big_endian"])
def test_software_full_625_matrix_dtype_layout_bits_and_ordinary_defaults(layout, evidence):
    array = matrix(endian=">" if layout == "big_endian" else "<")
    if layout == "F":
        array = array.T
    elif layout == "negative":
        array = array[::-1, ::-1]
    ordinary = poisson.core.caches
    before = (ordinary.MAX_ARRAY_ELEMENTS, ordinary.MAX_TREE_NODES, ordinary.MAX_TREE_DEPTH)
    with pytest.raises(ValueError, match="bounded array"):
        ordinary.snapshot(array)
    cache = observation.Scope((array,)).snapshot(dict(matrix=array))
    ordinary.validate(cache)
    column = cache.columns[0].values
    assert column.shape == (625, 625) and column.dtype.str == array.dtype.str
    assert column.tobytes(order="C") == array.tobytes(order="C")
    assert not column.flags.writeable and not cache.all_finite
    descriptor = next(n for n in cache.descriptor["items"] if n[0]["value"] == "matrix")[1]
    assert descriptor["source_layout"] == ordinary.layout(array)
    assert descriptor["sha256"] == hashlib.sha256(array.tobytes(order="C")).hexdigest()
    assert before == (262144, 262144, 32)
    assert before == (ordinary.MAX_ARRAY_ELEMENTS, ordinary.MAX_TREE_NODES, ordinary.MAX_TREE_DEPTH)
    with pytest.raises(ValueError, match="bounded array"):
        ordinary.snapshot(array)
    archive(evidence, "complete-column", column)
    save(evidence, "cache-descriptor", cache.descriptor)


def test_software_full_graph_preserves_equal_retained_alias_edges_and_bases(evidence):
    a, b = matrix(), matrix()
    caller = SimpleNamespace(first=a, second=b, selected=a)
    p, tape = SimpleNamespace(), SimpleNamespace(rng=None, events=[], draws=[], locals={})
    with pytest.raises(ValueError, match="array exhausted"):
        poisson.geometry.callers._graph(caller, p, tape)
    scope = observation.Scope((a, b))
    before = scope.graph(caller, p, tape)
    unchanged = scope.graph(caller, p, tape)
    poisson.geometry.meshes._same_graphs((unchanged,), (before,))
    values = scope.snapshot(vars(caller)).identity
    caller.selected = b
    assert scope.snapshot(vars(caller)).identity == values
    after = scope.graph(caller, p, tape)
    assert len(before[0]) == len(after[0])
    assert all(x is y for x, y in zip(before[0], after[0], strict=True))
    with pytest.raises(ValueError):
        poisson.geometry.meshes._same_graphs((after,), (before,))
    assert a.base is not None and any(value is a.base for value in before[0])
    archive(evidence, "complete-aliased-matrix", a)


@pytest.mark.parametrize("kind", ["unissued", "oversize", "seventh", "object"])
def test_software_scoped_capacity_has_explicit_refusals_and_preserves_default(kind, evidence):
    array = matrix(626 if kind == "oversize" else 625)
    if kind == "object":
        array = np.empty((625, 625), dtype=object)
        array.fill(None)
    with pytest.raises(ValueError) as caught:
        if kind == "unissued":
            observation.Scope().snapshot(array)
        elif kind == "seventh":
            observation.Scope(tuple(matrix() for _ in range(7)))
        else:
            observation.Scope((array,)).snapshot(array)
    assert poisson.core.caches.MAX_ARRAY_ELEMENTS == 262144
    save(evidence, "refusal", caught.value)


def parent(h):
    h.grid.cents_shape = (25, 25)
    cache = poisson.environment._snapshot(h.parent)
    trial = replace(h.parent.trial, before=cache, cache=cache, identity="")
    h.parent.trial = replace(
        trial, identity=poisson.core.records._digest(poisson.environment.trial_record(trial))
    )
    h.parent.graphs = poisson.environment._graphs(h.parent)


def six_root_harness(monkeypatch, failure):
    h = helper.harness(monkeypatch, failure=None if failure == "pinv_flux" else failure)
    parent(h)
    matrices = [np.array(matrix(role=index + 1), copy=True) for index in range(6)]
    zero_iter = iter(matrices[::3])
    pinv_iter = iter(matrices[2::3])
    pinv_calls = []

    def zeros(*args, **kwargs):
        return next(zero_iter)

    def scaled(z, boundary):
        index = 0 if boundary == "value" else 3
        assert z is matrices[index]
        # Model the native mutation of the retained allocation without
        # executing the stencil/division. A is a separate typed buffer.
        z.view(np.uint64)[0, 0] = 0x4000000000000000 + index
        return matrices[index + 1]

    def pinv(a):
        index = 1 if not pinv_calls else 4
        assert a is matrices[index] and a is not matrices[index - 1]
        pinv_calls.append(a)
        if failure == "pinv_flux" and index == 4:
            try:
                raise SyntheticSourceCause("synthetic second pinv original cause")
            except SyntheticSourceCause as cause:
                error = SyntheticSourceFailure("synthetic second pinv failed")
                h.errors.update(source=error, cause=cause)
                raise error from cause
        return next(pinv_iter)

    monkeypatch.setattr(poisson, "_ZEROS", zeros)
    monkeypatch.setattr(poisson, "_PINV", pinv)
    values = {}
    exec(
        compile(
            "def operator(self,bound):\n"
            "    step('operator_'+bound['N'],self)\n"
            "    Z=np.zeros((625,625))\n"
            "    A=scaled_operator(Z,bound['N'])\n"
            "    Ainv=np.linalg.pinv(A)\n"
            "    return A,Ainv\n",
            "<synthetic-six-root-poisson>",
            "exec",
        ),
        values,
    )
    monkeypatch.setattr(poisson, "_LAPLACIAN", values["operator"])
    original_namespace = poisson._namespace

    def namespace(context):
        methods, operator = original_namespace(context)
        operator.__globals__["scaled_operator"] = scaled
        return methods, operator

    monkeypatch.setattr(poisson, "_namespace", namespace)
    return h, matrices


@pytest.mark.parametrize("failure", [None, "operator_flux", "pinv_flux", "after_flux"])
def test_software_default_grid_passes_value_snapshot_then_flux_or_retains_source_failure(
    failure, monkeypatch, evidence
):
    h, matrices = six_root_harness(monkeypatch, failure)
    request = poisson.from_environment(h.owner, law_id=poisson.LAW_ID)
    if failure is None:
        owner = poisson.prepare_continuation(request)
        context = poisson._authority(owner)
        assert owner.cells.lapENVinv is matrices[2] and owner.cells.lapENV_P_inv is matrices[5]
        assert [name for name, _ in owner.trial.stages] == list(poisson.METHODS)
        assert context.attempted == list(poisson.METHODS)
        cache = owner.trial.cache
        assert len(poisson._observation(context).roots) == 6
        assert tuple(poisson._observation(context).roles) == observation.ROLE_NAMES
        assert [(stage, name) for stage, name, _ in context.helper_results] == [
            (stage, name) for stage in poisson.METHODS for name in ("zeros", "pinv")
        ]
        assert (
            context.results[0][1][0] is matrices[1] and context.helper_results[0][2] is matrices[0]
        )
        assert (
            context.results[1][1][0] is matrices[4] and context.helper_results[2][2] is matrices[3]
        )
        # Exact wire traversal remains returns first, then zeros/pinv helpers.
        expected = [matrices[index] for index in (1, 2, 4, 5, 0, 2, 3, 5)]
        assert len(cache.columns) == len(expected)
        for column, source in zip(cache.columns, expected, strict=True):
            assert column.values.dtype.str == source.dtype.str
            assert column.values.tobytes(order="C") == source.tobytes(order="C")
        assert {
            row["helper_operation"] for row in owner.trial.work if row.get("helper_operation")
        } == {"zeros", "pinv"}
    else:
        with pytest.raises(poisson.PoissonRejected) as caught:
            poisson.prepare_continuation(request)
        error = caught.value
        assert (
            error.source_error is h.errors["source"]
            and error.source_error.__cause__ is h.errors["cause"]
        )
        context = error.partial["context"]
        assert h.caller.lapENVinv is matrices[2]
        if failure == "after_flux":
            assert h.caller.lapENV_P_inv is matrices[5]
        else:
            assert not hasattr(h.caller, "lapENV_P_inv")
        assert [name for name, _ in error.partial["stages"]] == [poisson.METHODS[0]]
        assert (
            error.partial["parent_trial"] is h.parent.trial
            and error.partial["environment_consumed"]
        )
        cache = error.trial.cache
        save(evidence, "source-error", error.source_error)
        if failure == "pinv_flux":
            assert error.partial["helper_inputs"][-1][2] is matrices[4]
            assert error.partial["raw_locals"]["makeLaplacian"]["A"] is matrices[4]
    graph = poisson._graphs(context)
    assert graph and any(value is matrices[0] for value in graph[-1][0])
    assert any(column.values.shape == (625, 625) for column in cache.columns)
    poisson.core.caches.validate(cache)
    scope = poisson._observation(context)
    for name, value in scope.roles.items():
        archive(evidence, name, value)
    save(evidence, "named-roles", dict(names=list(scope.roles), distinct_arrays=len(scope.roots)))
    save(evidence, "complete-cache-descriptor", cache.descriptor)
    assert poisson.core.caches.MAX_ARRAY_ELEMENTS == 262144


def test_software_graph_scope_cannot_change_global_defaults(evidence):
    save(evidence, "policy", observation.specification())
    assert observation.MAX_OPERATOR_ELEMENTS == 625 * 625
    assert observation.MAX_OPERATOR_ARRAYS == 6
    assert poisson.geometry.callers.core.caches.MAX_ARRAY_ELEMENTS == 262144
    assert poisson.core.caches.MAX_TREE_NODES == 262144
    assert poisson.core.caches.MAX_TREE_DEPTH == 32


def test_software_capacity_refusal_retains_completed_raw_returns_and_stops_flux(
    monkeypatch, evidence
):
    h = helper.harness(monkeypatch)
    parent(h)
    a, inverse = matrix(626), matrix(626)
    # Keep the closure independent of the delegate's argument tuple.
    monkeypatch.setattr(poisson, "_ZEROS", lambda *args, **kwargs: a)
    monkeypatch.setattr(poisson, "_PINV", lambda *args, **kwargs: inverse)
    request = poisson.from_environment(h.owner, law_id=poisson.LAW_ID)
    with pytest.raises(poisson.PoissonRejected) as caught:
        poisson.prepare_continuation(request)
    error = caught.value
    assert error.source_error is None and isinstance(error.capture_error, ValueError)
    assert error.partial["results"][0][1][0] is a
    assert error.partial["results"][0][1][1] is inverse
    assert h.caller.lapENVinv is inverse and not hasattr(h.caller, "lapENV_P_inv")
    assert "before_flux" not in h.events and error.partial["environment_consumed"]
    assert not any(c.request is request for c in poisson._ISSUED.values())
    archive(evidence, "oversize-raw-matrix", a)
    archive(evidence, "oversize-raw-inverse", inverse)
    save(evidence, "capture", error.capture_error)


def test_software_scoped_policy_class_dispatch_change_is_refused(monkeypatch, evidence):
    h = helper.harness(monkeypatch)
    owner = poisson.prepare_continuation(poisson.from_environment(h.owner, law_id=poisson.LAW_ID))
    monkeypatch.setattr(
        observation.Scope,
        "__getattribute__",
        lambda self, name: object.__getattribute__(self, name),
    )
    with pytest.raises(poisson.PoissonRejected) as caught:
        _ = owner.cells
    assert caught.value.stage == "poisson_drift"
    save(evidence, "refusal", caught.value)


def test_software_native_assignment_requires_distinct_allocation_and_scaled_return(evidence):
    tree = ast.parse(Path(poisson.source.__file__).read_text())
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FiniteDiffPoisson"
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "makeLaplacian"
    )
    assignments = [
        node
        for node in method.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "A" for target in node.targets)
    ]
    assert isinstance(assignments[0].value, ast.Call)
    assert ast.unparse(assignments[0].value.func) == "np.zeros"
    assert isinstance(assignments[1].value, ast.BinOp) and isinstance(
        assignments[1].value.op, ast.Div
    )
    assert ast.unparse(assignments[1].value) == "A / self.delta ** 2"
    assert ast.unparse(method.body[-1].value) == "(A, Ainv)"
    save(
        evidence,
        "predicted-defect",
        dict(
            classification="predicted observation capacity defect, no observed scientific failure",
            roles=list(observation.ROLE_NAMES),
            maximum_distinct_roots=6,
            wire_results="(stage,(A,P))",
            wire_helpers="(stage,zeros,Z), (stage,pinv,P)",
            unchanged_default_array_elements=262144,
        ),
    )
