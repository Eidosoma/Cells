"""Bounded Poisson-only observations using the unchanged typed cache/graph code.

Private function namespaces alter observation admission for explicitly issued
operator arrays only. They never alter a module global, native numerical body,
live caller/mesh/phase, or the ordinary cache/graph defaults. Cache columns stay
complete shaped arrays; this module adds no hydration or checkpoint interface.
"""

from types import FunctionType, SimpleNamespace

import numpy as np

from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_native_single_cell_caller_lattice as callers

MAX_MATRIX_SIDE = 625
MAX_OPERATOR_ELEMENTS = 390625
MAX_OPERATOR_ARRAYS = 6
ROLE_NAMES = tuple(
    stage + "." + role
    for stage in ("environment_voltage", "environment_current")
    for role in ("Z", "A", "P")
)
_ORDINARY_ARRAY_ELEMENTS = 262144
_ORDINARY_TREE_NODES = 262144
_ORDINARY_TREE_DEPTH = 32


def specification():
    return dict(
        kind="cells.single_cell_Poisson_observation_capacity@1",
        max_matrix_side=MAX_MATRIX_SIDE,
        max_operator_array_elements=MAX_OPERATOR_ELEMENTS,
        max_issued_operator_arrays=MAX_OPERATOR_ARRAYS,
        numeric_operator_roots_and_actual_bases_only=True,
        ordinary_array_elements=_ORDINARY_ARRAY_ELEMENTS,
        ordinary_tree_nodes=_ORDINARY_TREE_NODES,
        ordinary_tree_depth=_ORDINARY_TREE_DEPTH,
        typed_cache_format="unchanged complete numeric_array columns",
    )


def _defaults():
    if (
        caches.MAX_ARRAY_ELEMENTS != _ORDINARY_ARRAY_ELEMENTS
        or caches.MAX_TREE_NODES != _ORDINARY_TREE_NODES
        or caches.MAX_TREE_DEPTH != _ORDINARY_TREE_DEPTH
        or callers.core.caches is not caches
    ):
        raise ValueError("Ordinary observation defaults/producer changed")


def _clone(function, **globals):
    return FunctionType(
        function.__code__,
        dict(function.__globals__, **globals),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )


def _namespace(module, **overrides):
    # Metadata lookup facade only; never supplied to any scientific method.
    return SimpleNamespace(**dict(vars(module), **overrides))


class Scope:
    """Retain Z=zeros allocation, A=scaled operator, P=pinv for both calls.

    Z is the actual zeros-helper object, later filled by the native stencil.
    A is a separate division result and the pinv input/returned operator. P is
    shared by the pinv helper result and returned inverse. No root is dropped.
    """

    def __init__(self, arrays=(), *, roles=None):
        _defaults()
        if roles is not None:
            if arrays or type(roles) is not dict or any(name not in ROLE_NAMES for name in roles):
                raise ValueError("Unknown or mixed Poisson observation roles")
            self.roles = dict(roles)
            arrays = self.roles.values()
        else:
            self.roles = {}
        roots = {}
        for value in arrays:
            if isinstance(value, np.ndarray):
                roots.setdefault(id(value), value)
        if len(roots) > MAX_OPERATOR_ARRAYS:
            raise ValueError("Poisson observation exceeds six issued Z/A/P operator arrays")
        self.roots = tuple(roots.values())
        self.allowed = dict(roots)
        for value in self.roots:
            if value.size > _ORDINARY_ARRAY_ELEMENTS:
                if (
                    value.dtype.hasobject
                    or value.dtype.kind not in "biufc"
                    or value.ndim != 2
                    or value.shape[0] != value.shape[1]
                    or value.shape[0] > MAX_MATRIX_SIDE
                ):
                    raise ValueError("Poisson observation exceeds bounded numeric matrix capacity")
            base = value.base
            while isinstance(base, np.ndarray) and id(base) not in self.allowed:
                self.allowed[id(base)] = base
                base = base.base

    def layout(self, value):
        if value.size > _ORDINARY_ARRAY_ELEMENTS:
            if (
                self.allowed.get(id(value)) is not value
                or value.size > MAX_OPERATOR_ELEMENTS
                or value.dtype.hasobject
                or value.dtype.kind not in "biufc"
            ):
                raise ValueError("Large observation lacks issued Poisson array/base authority")
        return caches.layout(value)

    def snapshot(self, value):
        _defaults()
        # The existing producer/type/descriptor/columns are unchanged. Only
        # this function invocation sees the explicit array-admission policy.
        function = _clone(
            caches.snapshot, MAX_ARRAY_ELEMENTS=MAX_OPERATOR_ELEMENTS, layout=self.layout
        )
        return function(value)

    def graph(self, caller, parameters, tape):
        _defaults()
        cache_namespace = _namespace(
            caches, MAX_ARRAY_ELEMENTS=MAX_OPERATOR_ELEMENTS, layout=self.layout
        )
        core_namespace = _namespace(callers.core, caches=cache_namespace)
        return _clone(callers._graph, core=core_namespace)(caller, parameters, tape)

    def environment_snapshot(self, parent, environment):
        core_namespace = _namespace(
            environment.core, caches=_namespace(caches, snapshot=self.snapshot)
        )
        return _clone(environment._snapshot, core=core_namespace)(parent)

    def environment_graphs(self, parent, environment):
        """Reuse all original roots/edges, including the genuine tree views."""
        geometry, ecm = environment.geometry, environment.ecm
        callers_namespace = _namespace(geometry.callers, _graph=self.graph)
        meshes = geometry.meshes
        mesh_graphs = _clone(meshes._graphs, callers=callers_namespace)
        geometry_namespace = _namespace(
            geometry, callers=callers_namespace, meshes=_namespace(meshes, _graphs=mesh_graphs)
        )
        ecm_graphs = _clone(ecm._graphs, geometry=geometry_namespace)
        return _clone(
            environment._graphs,
            geometry=geometry_namespace,
            ecm=_namespace(ecm, _graphs=ecm_graphs),
        )(parent)


def bindings(environment):
    """Exact reused producer/code and scoped-policy atoms for live guards."""
    functions = (
        specification,
        _defaults,
        _clone,
        _namespace,
        Scope.__init__,
        Scope.layout,
        Scope.snapshot,
        Scope.graph,
        Scope.environment_snapshot,
        Scope.environment_graphs,
        caches.snapshot,
        caches.validate,
        caches.layout,
        callers._graph,
        environment._snapshot,
        environment._graphs,
        environment.ecm._graphs,
        environment.geometry.meshes._graphs,
    )
    atoms = environment.ecm.aliases._atoms
    return (
        Scope,
        *environment.ecm.aliases._dispatch_bindings(Scope),
        MAX_MATRIX_SIDE,
        MAX_OPERATOR_ELEMENTS,
        MAX_OPERATOR_ARRAYS,
        ROLE_NAMES,
        caches.MAX_ARRAY_ELEMENTS,
        caches.MAX_TREE_NODES,
        caches.MAX_TREE_DEPTH,
        *(atom for function in functions for atom in atoms(function)),
    )
