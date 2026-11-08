"""Real phase-state metadata functions with synthetic objects, never native owners.

The cache encoder, reference projector and labeled graph walker are compiled
unchanged. Numerical type sentinels are deliberately unreachable; no NumPy,
native constructor, parameter owner or scientific body is imported or executed.
"""

import ast
import hashlib
import json
import math
import struct
import sys
import weakref
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORLD = "src/cells/processes/betse_native_world_phase_construction.py"
CACHE = "src/cells/processes/betse_initial_mesh_preparation_cache.py"
PROJECT = "src/cells/processes/betse_native_tissue_configuration.py"
GRAPH = "src/cells/processes/betse_native_single_cell_caller_lattice.py"


class Holder:
    pass


class NumericTypeSentinel:
    """Only isinstance branches are reached; numerical values are unavailable."""


def definitions(path, names, namespace):
    nodes = [
        node
        for node in ast.parse((ROOT / path).read_bytes()).body
        if getattr(node, "name", None) in names
    ]
    assert {node.name for node in nodes} == set(names)
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "phase_state_metadata:" + path, "exec"),
        namespace,
    )


@pytest.fixture
def model(monkeypatch):
    module = ModuleType("isolated_phase_state_cache")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    vars(module).update(
        hashlib=hashlib,
        json=json,
        math=math,
        struct=struct,
        dataclass=dataclass,
        np=NS(ndarray=NumericTypeSentinel, generic=NumericTypeSentinel),
        MAX_TREE_DEPTH=32,
        MAX_TREE_NODES=262144,
        MAX_ARRAY_ELEMENTS=262144,
    )
    definitions(CACHE, ("Cache", "CacheColumn", "snapshot"), vars(module))
    graph_space = dict(np=module.np, struct=struct, core=NS(caches=module))
    definitions(GRAPH, ("_graph",), graph_space)
    project_space = dict(Enum=Enum)
    definitions(PROJECT, ("_project",), project_space)

    class Rejected(ValueError):
        def __init__(self, reason, *, stage, partial):
            super().__init__(reason)
            self.stage, self.partial = stage, partial

    def same(left, right):
        if len(left) != len(right) or any(a is not b for a, b in zip(left, right, strict=True)):
            raise ValueError("Original object-reference roster changed")

    namespace = dict(
        SimpleNamespace=NS,
        WorldPhaseRejected=Rejected,
        _world_forwarded=lambda transition: None,
        _world_stage_links=lambda context, transition: None,
        _world_parameter_authority=lambda transition: None,
    )
    definitions(
        WORLD,
        (
            "_world_objects",
            "_world_projector",
            "_world_state",
            "_world_stage_runtime",
            "_world_stage_runtime_pass",
            "_world_reject",
        ),
        namespace,
    )
    p, callback, phase, cells, sim = (Holder() for _ in range(5))
    request = Holder()
    request.parameter_identity, request.callback_identity = "parameters", "callback"
    phase.callbacks, phase.cells, phase.kind, phase.p, phase.sim = callback, cells, "SEED", p, sim
    transition = NS(
        p=p, parents=(None, None, None, callback), request=request, invalid=False, entry_error=None
    )
    transition.world_roots = [("parameters", p), ("callback", callback)]
    transition.world_root_tokens = (transition.world_roots, tuple(transition.world_roots))
    contexts, modules = [], []
    for index in range(4):
        context = NS(
            world_transition=transition,
            world_index=index,
            phase=phase,
            objects=[],
            proxy_returns=[],
            world_proxy_roots={},
            world_views={},
            world_stable_tape=NS(rng=None, events=(), draws=(), locals=()),
            parent=None,
            evidence=None,
            active=True,
            invalid=False,
            entry_error=None,
        )
        contexts.append(context)
        modules.append(NS(_WORLD={request: context}))
    contexts[0].objects[:] = [("SimPhase", phase), ("Cells", cells), ("Simulator", sim)]
    transition.api = NS(
        stages=modules,
        helpers=NS(
            core=NS(caches=module),
            literal=NS(
                _project=project_space["_project"],
                callers=NS(_graph=graph_space["_graph"]),
                _same=same,
            ),
        ),
    )
    cache_objects = []
    for name in ("SimPhaseCaches", "upscaled", "vector", "layer", "vector_field"):
        value = Holder()
        cache_objects.append((name, value))
    phase.cache = cache_objects[0][1]
    phase.cache.upscaled, phase.cache.vector, phase.cache.vector_field = (
        cache_objects[1][1],
        cache_objects[2][1],
        cache_objects[4][1],
    )
    phase.cache.vector.layer = cache_objects[3][1]
    contexts[1].objects[:] = cache_objects
    # CPython's original weak-proxy idempotence retains the same proxy here.
    for _, value in cache_objects[1:]:
        proxy = weakref.proxy(phase)
        value._phase = proxy
        contexts[1].proxy_returns.append((phase, proxy))
    for context in contexts:
        context.world_base_objects = namespace["_world_objects"](
            transition, context.world_index - 1
        )
        context.world_before, context.world_before_graph = namespace["_world_state"](
            context, baseline=True
        )
    return NS(
        namespace=namespace,
        transition=transition,
        contexts=contexts,
        phase=phase,
        p=p,
        sim=sim,
        cells=cells,
        cache_objects=cache_objects,
        Rejected=Rejected,
    )


def allocate(model, role="TissueHandler"):
    value = Holder()
    model.contexts[2].objects.append((role, value))
    return value


def save_comparison(tmp_path, before, after, graph_equal):
    (tmp_path / "state-comparison.json").write_text(
        json.dumps(
            dict(
                before_identity=before.identity,
                after_identity=after.identity,
                before_descriptor=before.descriptor,
                after_descriptor=after.descriptor,
                raw_graph_equal=graph_equal,
                actual_native_or_owner_calls=0,
            ),
            indent=2,
            sort_keys=True,
        )
    )


def test_handler_allocation_preserves_actual_weak_proxy_tokens(model, tmp_path):
    context = model.contexts[2]
    before, old = context.world_before, context.world_before_graph
    allocate(model)
    after, new = model.namespace["_world_state"](context, baseline=True)
    model.transition.api.helpers.literal._same(old[0], new[0])
    save_comparison(tmp_path, before, after, old[1] == new[1])
    assert old[1] == new[1]
    assert before.identity == after.identity
    model.namespace["_world_stage_runtime"](context)


@pytest.mark.parametrize("count", [1, 3, 9])
def test_handler_and_picker_allocations_keep_inherited_snapshot(model, count):
    context = model.contexts[2]
    before = model.namespace["_world_projector"](context).objects
    for index in range(count):
        allocate(model, "factory" + str(index))
        model.namespace["_world_stage_runtime"](context)
        current = model.namespace["_world_projector"](context).objects
        assert all(a[1] is b[1] for a, b in zip(before, current[: len(before)], strict=True))
    assert len(current) == len(before) + count


@pytest.mark.parametrize(
    "mutation", ["phase_alias", "cache_child", "proxy", "extra_field", "value", "equal_alias"]
)
def test_real_inherited_changes_still_refuse_after_allocation(model, mutation):
    allocate(model)
    if mutation == "phase_alias":
        model.phase.cells = Holder()
    elif mutation == "cache_child":
        model.phase.cache.vector = Holder()
    elif mutation == "proxy":
        # Keep the referent alive while replacing the inherited weak edge.
        model.foreign_phase = Holder()
        model.cache_objects[1][1]._phase = weakref.proxy(model.foreign_phase)
    elif mutation == "extra_field":
        model.cells.unrelated = None
    elif mutation == "value":
        model.phase.kind = "INIT"
    else:
        model.phase.cache.vector = model.phase.cache.upscaled
    with pytest.raises((ValueError, model.Rejected)):
        model.namespace["_world_stage_runtime"](model.contexts[2])


def test_original_proxy_idempotence_deduplicates_by_identity_only(model):
    values = model.namespace["_world_projector"](model.contexts[2]).objects
    proxies = [value for role, value in values if role == "weak_phase_proxy"]
    assert len(proxies) == 1
    assert all(proxy is proxies[0] for _, proxy in model.contexts[1].proxy_returns)
    assert len({id(value) for _, value in values}) == len(values)
    assert proxies[0] is not model.phase


def test_completed_parent_projection_does_not_acquire_child_objects(model):
    parent = model.contexts[1]
    before, graph = model.namespace["_world_state"](parent)
    parent.trial, parent.world_graph = NS(cache=before), graph
    parent.evidence, parent.active = object(), False
    allocate(model)
    model.namespace["_world_stage_runtime"](parent)
    model.namespace["_world_stage_runtime"](model.contexts[2])


def test_tail_baseline_after_handler_keeps_complete_inherited_state(model):
    model.phase.dyna = allocate(model)
    context = model.contexts[3]
    context.world_base_objects = model.namespace["_world_objects"](model.transition, 2)
    context.world_before, context.world_before_graph = model.namespace["_world_state"](
        context, baseline=True
    )
    model.sim.dyna = model.phase.dyna
    model.phase.export_dirname = "/declared/export"
    model.p._run_sim = False
    model.namespace["_world_stage_runtime"](context)
    # The baseline excludes only those tail stores, retaining all other data.
    model.phase.dyna.unrelated = True
    with pytest.raises(model.Rejected):
        model.namespace["_world_stage_runtime"](context)
