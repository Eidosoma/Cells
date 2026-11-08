"""Held ordinary INIT dynamics tail on one actual retained prelude lineage.

The numerical body is the pinned original tail, including its unconditional
NumPy random call. Tissue participation is one live session, never another
phase/parameter owner. Actual source/runtime/ancestor adoption is still held.

Tissue contract: bind_completion(actual CompletionClaim, *, original_owner);
validate_active/closed(session, *, completion_claim) return the identical
session/evidence; source_members(session); state_roots(session);
wrapper_guard/dispatch(session, *, completion_claim, original, frame and actual
dispatch arguments); observe(session, *, completion_claim, frame, event, arg);
finish(session, *, completion_claim); validate_rng_call(...) -> RngWitness.
The active checker returns the identical claim and authenticates registry and
ancestor edges without recursively reading tissue state. claim.check() and
source dispatch perform the complete state/stream audit. record and failed
context are forensic data; none grants another construction or source epoch.
"""

import ast
import copy
import hashlib
import os
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, MappingProxyType, MethodType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_dynamics_completion_source as source
from cells.processes import betse_native_init_dynamics_prelude as previous
from cells.processes import betse_native_parameter_yaml_prefix as files

LAW_ID = "betse_same_actual_INIT_ordinary_dynamics_completion@1"
MOLECULE_LAW_ID = "betse_same_actual_INIT_native_molecules_dynamics_completion@1"
RELEASE = "CELLS_NATIVE_INIT_DYNAMICS_COMPLETION_RELEASED"
PARENT_SOURCE_SHA256 = 'ca543ad58b9a850e508fd67ffdc64938682fe68220c1cd4f7fe5ce48e353927f'
PARENT_REVIEW_SHA256 = '1550f3033aa2e56573135bff934a93795a3169e129b6c4a17e8a787447bfa710'
TISSUE_INTERFACE_SHA256 = '4be2dc21e7f53f36d574ff2557670eb98640718669bfe767982f6dc49e4a1ce6'
TISSUE_REVIEW_SHA256 = '0f2fc6b9ae3b27bf53d637e5fd02a245a55c3cce5b885df9c5b7f30abe2b14ca'
TISSUE_MODULE = "cells.processes.betse_native_init_tissue_dynamics"
TISSUE_BINDING_KIND = "exact_INIT_tissue_bytes_except_two_validated_completion_backrefs@1"
TISSUE_BACK_REFERENCE_SLOTS = ("COMPLETION_SOURCE_SHA256", "COMPLETION_REVIEW_SHA256")
MOLECULE_MODULE = "cells.processes.betse_native_init_molecule_network"
MOLECULE_INTERFACE_SHA256 = 'dd77276a16c4e3aeb118bf5bb84eecc6bf9ce748a3ed76d98ee5739c44d039c9'
MOLECULE_REVIEW_SHA256 = '060c601d58a511985dc87b9d68b1d88c5a8c8f2173c28140a9e0167e0a8bd5df'
MOLECULE_BINDING_KIND = "exact_INIT_molecule_bytes_except_two_validated_completion_backrefs@1"
MOLECULE_BACK_REFERENCE_SLOTS = ("COMPLETION_SOURCE_SHA256", "COMPLETION_REVIEW_SHA256")
STORAGE_MODULE = "cells.processes.betse_native_init_storage"
STORAGE_INTERFACE_SHA256 = 'e8c50e8059a322daa70326c1b8995b5e5021560f37054d9b829901635a99064d'
STORAGE_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
STORAGE_PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
STORAGE_BINDING_KIND = "exact_INIT_storage_bytes_except_two_validated_dynamics_backrefs@1"
STORAGE_BACK_REFERENCE_SLOTS = ("PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256")
STORAGE_ANCESTOR_CLAIM = "_claim_storage_ancestor"
ELECTRICAL_ANCESTOR_CLAIM = "_claim_electrical_ancestor"
PARENT_CLAIM = "_claim_for_init_dynamics_completion"
PARENT_CHECK = "_check_init_dynamics_completion_authority"
NATIVE = previous.NATIVE
SIM_FILE = previous.SIM_FILE
SIM_SHA256 = previous.NATIVE_PINS[SIM_FILE]
MAX_WORK = 100000
MAX_RNG_CALLS = 4096
NUMPY_HELPERS = ("asarray", "copy", "zeros", "ones", "sqrt", "dot")
SIM_STORES = (
    "D_env_base",
    "J_env_x",
    "J_env_y",
    "fluxes_env_x",
    "fluxes_env_y",
    "Dm_base",
    "Dm_scheduled",
    "P_mod",
    "P_base",
    "div_u_osmo",
    "channel_noise_factor",
    "Dm_cells",
    "gj_block",
    "NaKATP_block",
    "CaATP_block",
    "endo_retic",
    "cellso",
    "rho_pump",
    "rho_channel",
    "ko_env",
    "ko_cell",
    "cedl_env",
    "cedl_cell",
    "cedl",
    "sigma",
    "sigma_cell",
    "sigma_env",
    "rho_factor",
    "cgj",
)
TISSUE_API = (
    "bind_completion",
    "validate_active",
    "validate_closed",
    "source_members",
    "state_roots",
    "wrapper_guard",
    "dispatch",
    "finish",
    "validate_rng_call",
    "observe",
    "_context",
    "_registry",
)
MOLECULE_API = (
    "bind_completion",
    "validate_active",
    "validate_closed",
    "source_members",
    "state_roots",
    "graph_roots",
    "project_state",
    "construct",
    "wrapper_guard",
    "dispatch",
    "observe",
    "bind_storage",
    "bind_first_step",
    "runtime_members",
    "runtime_codes",
    "observes_runtime_frame",
    "runtime_wrapper_guard",
    "runtime_dispatch",
    "runtime_permissions",
    "observe_runtime",
    "finish_runtime",
    "validate_runtime",
    "validate_runtime_active",
    "runtime_failed_context",
    "_effect_fields",
    "_runtime_field_table",
    "_runtime_route",
    "_runtime_expressions",
    "_runtime_mappings",
    "_runtime_context",
    "_bind_runtime",
    "_runtime_error",
    "_runtime_observer",
    "_runtime_entry",
    "_runtime_resolution",
    "_runtime_record_data",
    "finish",
    "_context",
    "_registry",
    "_configuration",
    "_ready",
    "_pin",
    "_reject",
    "_check",
    "_bindings",
    "_function_bindings",
    "_callback_pair",
    "_dynamic_associations",
    "_argument_links",
    "_class_associations",
    "_class_header",
    "_source_entry",
    "_actual_functions",
    "_capture",
    "_observe_event",
    "_descended",
    "source_plan",
    "failed_context",
    "owns_source_frame",
    "observes_source_frame",
)
_REQUESTS, _CONSUMED, _RETIRED, _CLAIMS, _ISSUED = (WeakKeyDictionary() for _ in range(5))
_STORAGE_FORWARDED, _STORAGE_LEASES = WeakKeyDictionary(), WeakKeyDictionary()
_ELECTRICAL_DESCENDANTS = WeakKeyDictionary()
_FIRST_STEP_DESCENDANTS = WeakKeyDictionary()
_SHORT_INIT_DESCENDANTS = WeakKeyDictionary()
SHORT_RUNTIME_MODULE = "cells.processes.betse_native_init_molecule_short_runtime"
SHORT_RUNTIME_SHA256 = '597671ce890a609e3a1584362646c73370429be850c65c2cc091dcc3d4ca7476'
SHORT_RUNTIME_REVIEW_SHA256 = '060c601d58a511985dc87b9d68b1d88c5a8c8f2173c28140a9e0167e0a8bd5df'
_TERMINAL_INIT_DESCENDANTS = WeakKeyDictionary()
TERMINAL_RUNTIME_MODULE = "cells.processes.betse_native_init_terminal_molecules"
TERMINAL_RUNTIME_SHA256 = '6f0e0432a07076a02f88b997d89ab6fae2e9bc9588da36d3dbca8cf582532412'
TERMINAL_RUNTIME_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
_ACTIVE, _FAILED, _LOCK = [], [], RLock()


class CompletionRejected(ValueError):
    def __init__(self, reason, *, stage, request=None, trial=None, partial=None):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    prelude_owner: object
    parent_identity: str
    source_identity: str
    file_inputs: tuple
    identity: str
    native_molecules: bool = False

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual live prelude lineage cannot be decoded from data")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    stream_before: tuple
    stream_after: tuple
    rng_calls: tuple
    work: tuple
    c_calls: tuple
    raw_returns: tuple
    tissue_record: object
    source_completed: bool
    identity: str
    molecule_record: object = None


def _digest(value):
    return previous._digest(value)


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _native_tree():
    path = NATIVE / SIM_FILE
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != SIM_SHA256:
        raise ValueError("Pinned whole original Simulator module required")
    return ast.parse(path.read_bytes())


def _node():
    full = previous._method(_native_tree(), "Simulator", "init_dynamics")
    if (full.lineno, full.end_lineno, len(full.body)) != (758, 1012, 45):
        raise ValueError("Exact original dynamics source extent required")
    if tuple(ast.unparse(n) for n in full.body[2:4]) != ("cells = phase.cells", "p = phase.p"):
        raise ValueError("Original alias-read statements changed")
    if ast.unparse(full.body[10]) != "phase.dyna.init_profiles(phase)":
        raise ValueError("Original post-prelude boundary changed")
    selected = copy.deepcopy(full)
    selected.body = [*copy.deepcopy(full.body[2:4]), *copy.deepcopy(full.body[10:])]
    proof = previous._method(
        ast.parse(Path(source.__file__).read_bytes()), "InitDynamicsCompletion", "init_dynamics"
    )
    if (
        ast.dump(ast.Module(body=proof.body, type_ignores=[]))
        != ast.dump(ast.Module(body=selected.body, type_ignores=[]))
        or previous._header(proof) != previous._header(full)
        or proof.decorator_list
        or proof.returns is not None
        or proof.type_params
    ):
        raise ValueError("Exact literal tail, alias reads or header changed")
    return selected


def _class_code(module_code, cls, method):
    owner = next(c for c in module_code.co_consts if type(c) is CodeType and c.co_name == cls)
    return next(c for c in owner.co_consts if type(c) is CodeType and c.co_name == method)


def _code():
    # Python3.13 compilation context affects LOAD_ATTR call hints. Compile in
    # the genuine whole-module/class context without executing its module body.
    tree = _native_tree()
    cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == "Simulator")
    full = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "init_dynamics")
    cls.body[cls.body.index(full)] = _node()
    compiled = compile(
        ast.fix_missing_locations(tree), str(NATIVE / SIM_FILE), "exec", dont_inherit=True
    )
    return _class_code(compiled, "Simulator", "init_dynamics")


def source_plan():
    node = _node()
    return dict(
        law=LAW_ID,
        source={SIM_FILE: SIM_SHA256},
        extent=(809, 1012),
        original_tail_statements=35,
        original_alias_reads=(778, 779),
        full_module_compile_context=True,
        prefix_replayed=False,
        statement_lines=tuple((n.lineno, n.end_lineno) for n in node.body),
        actual_parent_required="Issued PreludeOwner; same actual INIT phase/p/Cells/sim/handler",
        one_active_claim_through_tissue_profiles_noise_events_and_sealing=True,
        mandatory_channel_rng_even_if_level_zero=True,
        source_order=(
            "init_profiles",
            "environment/material bases",
            "NumPy channel RNG",
            "blocking/disabled optional branches",
            "cellso alias",
            "init_events",
            "screening/conductivity/geometry factors",
            "FAST branch unavailable",
        ),
        simulated_parameter_or_phase_or_world_constructed=False,
        permitted_cell_change="Percent picker shuffles the original cell_i full slice view only",
        rng_owners=(
            "actual continuing NumPy mtrand._rand",
            "actual native shuffle.__self__ stdlib _inst",
        ),
        unavailable=(
            "calcium EndoRetic owner",
            "molecule/GRN fresh or reload owner",
            "pressure/flow/deformation helpers",
            "FAST solver",
        ),
        maximum_work=MAX_WORK,
        maximum_rng_source_calls=MAX_RNG_CALLS,
        parent_source=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        tissue_interface=TISSUE_INTERFACE_SHA256,
        tissue_review=TISSUE_REVIEW_SHA256,
        tissue_binding_kind=TISSUE_BINDING_KIND,
        tissue_backrefs=TISSUE_BACK_REFERENCE_SLOTS,
        storage_handoff=dict(
            module=STORAGE_MODULE,
            interface=STORAGE_INTERFACE_SHA256,
            review=STORAGE_REVIEW_SHA256,
            parent_review=STORAGE_PARENT_REVIEW_SHA256,
            claim="_claim_for_init_storage",
            check="_check_init_storage_authority",
            route="_storage_route",
            retained_INIT_claim=STORAGE_ANCESTOR_CLAIM,
            no_run_sim_core_or_voltage_time_loop_credit=True,
        ),
        parent_hooks=(PARENT_CLAIM, PARENT_CHECK),
        tissue_API=TISSUE_API,
        native_molecule_opt_in=dict(
            law=MOLECULE_LAW_ID,
            declaration=(
                "from_prelude_native_molecules(actual PreludeOwner, law_id=..., file_inputs=())"
            ),
            default_ordinary_route_still_refuses_enabled_network=True,
            original_tail_factory_and_branch_order_unchanged=True,
            interface=MOLECULE_INTERFACE_SHA256,
            review=MOLECULE_REVIEW_SHA256,
            binding=MOLECULE_BINDING_KIND,
            required_same_INIT_material_ancestor_before_constructor=True,
            native_storage_and_first_step_participant_API_implemented=True,
            native_outer_wrapper_authority_and_review_still_required=True,
            API=MOLECULE_API,
        ),
        electrical_grandchild=dict(
            claim="_claim_electrical_ancestor(completion, storage, electrical)",
            check="_check_electrical_ancestor(completion, storage, electrical)",
            original_retained_INIT_claim=ELECTRICAL_ANCESTOR_CLAIM,
            permitted_fields="exact source-derived27 update_V/get_current Simulator fields",
            no_old_numeric_epoch_reopened=True,
        ),
        actual_native_RNG_source_or_reference_release=False,
        time_vector_solver_storage_updateV_pickle_or_completed_INIT_admission=False,
    )


def _tissue_binding(payload):
    """Existing exact-byte recipe; only the two peer backrefs may vary."""
    parent = previous.previous
    namespace = dict(
        vars(parent),
        DYNAMICS_BACK_REFERENCE_SLOTS=TISSUE_BACK_REFERENCE_SLOTS,
        DYNAMICS_BINDING_KIND=TISSUE_BINDING_KIND,
    )
    return FunctionType(parent._dynamics_binding.__code__, namespace)(payload)


def _check_tissue_backrefs(backrefs):
    expected = (
        ("COMPLETION_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("COMPLETION_REVIEW_SHA256", previous.COMPLETION_REVIEW_SHA256),
    )
    if (
        type(backrefs) is not tuple
        or len(backrefs) != 2
        or any(type(row) is not tuple or len(row) != 2 for row in backrefs)
        or any(type(item) is not str for row in backrefs for item in row)
        or not _pin(previous.COMPLETION_REVIEW_SHA256)
        or backrefs != expected
    ):
        raise CompletionRejected(
            "Original tissue actual Completion source/review back-reference changed",
            stage="tissue_source",
        )


def _molecule_api():
    """Exact held participant bytes; do not recursively call its _ready here."""
    if not all(
        _pin(value)
        for value in (
            MOLECULE_INTERFACE_SHA256,
            MOLECULE_REVIEW_SHA256,
            previous.COMPLETION_REVIEW_SHA256,
        )
    ):
        raise CompletionRejected(
            "Reviewed molecular source transport remains held", stage="molecule_held"
        )
    path = Path(__file__).parents[3] / ("src/" + MOLECULE_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Actual original molecule participant source required")
    raw = path.read_bytes()
    identity, backrefs = FunctionType(
        previous.previous._dynamics_binding.__code__,
        dict(
            vars(previous.previous),
            DYNAMICS_BACK_REFERENCE_SLOTS=MOLECULE_BACK_REFERENCE_SLOTS,
            DYNAMICS_BINDING_KIND=MOLECULE_BINDING_KIND,
        ),
    )(raw)
    expected = (
        ("COMPLETION_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("COMPLETION_REVIEW_SHA256", previous.COMPLETION_REVIEW_SHA256),
    )
    module = sys.modules.get(MOLECULE_MODULE)
    if (
        identity != MOLECULE_INTERFACE_SHA256
        or backrefs != expected
        or type(module) is not ModuleType
        or Path(module.__file__).resolve() != path
        or module.COMPLETION_MODULE != __name__
        or module.CONTRACT != module.PROPOSED_CONTRACT
        or any(getattr(module, name) != value for name, value in backrefs)
    ):
        raise ValueError("Original molecule transport/source/back-reference changed")
    previous.previous.previous._ready()._source_interface(module, raw, path, MOLECULE_API)
    for name in MOLECULE_API:
        fn = vars(module).get(name)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(module):
            raise ValueError("Actual molecule participant function required: " + name)
    return module


def _ready():
    if not all(
        _pin(value)
        for value in (
            PARENT_SOURCE_SHA256,
            PARENT_REVIEW_SHA256,
            TISSUE_INTERFACE_SHA256,
            TISSUE_REVIEW_SHA256,
            previous.COMPLETION_REVIEW_SHA256,
        )
    ):
        raise CompletionRejected(
            "Reviewed parent/tissue source adoption remains held", stage="unbound"
        )
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PARENT_SOURCE_SHA256:
        raise CompletionRejected("Original prelude producer changed", stage="parent_source")
    for name in (PARENT_CLAIM, PARENT_CHECK):
        function = vars(previous).get(name)
        if type(function) is not FunctionType or function.__globals__ is not vars(previous):
            raise CompletionRejected(
                "Actual prelude retirement/advanced-stream authority unavailable", stage="handoff"
            )
    tissue = sys.modules.get(TISSUE_MODULE)
    if type(tissue) is not ModuleType:
        raise CompletionRejected(
            "Actual source-backed tissue participant must already be loaded", stage="tissue"
        )
    path = Path(__file__).parents[3] / ("src/" + TISSUE_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or Path(tissue.__file__).resolve() != path:
        raise CompletionRejected("Original tissue source path changed", stage="tissue_source")
    raw = path.read_bytes()
    identity, backrefs = _tissue_binding(raw)
    _check_tissue_backrefs(backrefs)
    if identity != TISSUE_INTERFACE_SHA256 or any(
        getattr(tissue, name) != value for name, value in backrefs
    ):
        raise CompletionRejected(
            "Original tissue bytes or actual Completion back-reference changed",
            stage="tissue_source",
        )
    api = previous.previous.previous._ready()
    api._source_interface(tissue, raw, path, TISSUE_API)
    for name in TISSUE_API:
        function = vars(tissue).get(name)
        if type(function) is not FunctionType or function.__globals__ is not vars(tissue):
            raise CompletionRejected(
                "Exact declared tissue API required: " + name, stage="tissue_API"
            )
    return tissue


def request_record(value):
    result = dict(
        law=LAW_ID,
        parent=value.parent_identity,
        source=value.source_identity,
        files=tuple(item.identity for item in value.file_inputs),
    )
    if value.native_molecules:
        result.update(law=MOLECULE_LAW_ID, native_molecules=True)
    return result


def _file_inputs(values):
    if type(values) is not tuple or len(values) > 64:
        raise CompletionRejected("Explicit bounded issued FileInput tuple required", stage="files")
    names = []
    for value in values:
        files._verify_file(value)
        if value.filename in names:
            raise CompletionRejected("Duplicate file authority", stage="files")
        names.append(value.filename)
    return values


def _domain(parent, *, native_molecules=False):
    if type(native_molecules) is not bool:
        raise CompletionRejected("Exact declared native molecule mode required", stage="domain")
    p, phase = parent.p, parent.phase
    if phase.kind.name != "INIT" or p._run_sim is not False or p.is_ecm is not True:
        raise CompletionRejected("Actual ordinary normal-ECM INIT phase required", stage="domain")
    requested = []
    if p.ions_dict["Ca"] == 1 and p.Ca_dyn:
        requested.append((857, "EndoRetic"))
    for name, line in (
        ("molecules_enabled", 866),
        ("grn_enabled", 884),
        ("deform_osmo", 902),
        ("fluid_flow", 907),
        ("deformation", 927),
    ):
        if getattr(p, name) and not (name == "molecules_enabled" and native_molecules):
            requested.append((line, name))
    namespace = parent.original_globals
    solver_type = namespace["SolverType"]
    if p.solver_type is not solver_type.FULL:
        requested.append((1011, "FAST or unknown solver"))
    if requested:
        raise CompletionRejected(
            "Genuine optional owners unavailable: " + repr(requested), stage="unavailable_branch"
        )
    if native_molecules:
        module = _molecule_api()
        module._ready()
        module._configuration(
            SimpleNamespace(
                p=p, phase=phase, sim=parent.sim, request=SimpleNamespace(native_molecules=True)
            )
        )


def from_prelude(owner, *, law_id, file_inputs=()):
    if type(law_id) is not str or law_id != LAW_ID:
        raise CompletionRejected("Exact completion law required", stage="law")
    return _declare(owner, file_inputs=file_inputs, native_molecules=False)


def from_prelude_native_molecules(owner, *, law_id, file_inputs=()):
    if type(law_id) is not str or law_id != MOLECULE_LAW_ID:
        raise CompletionRejected("Exact molecular completion law required", stage="law")
    # Both source gates and real ancestor prerequisites precede owner lookup.
    module = _molecule_api()
    module._ready()
    return _declare(owner, file_inputs=file_inputs, native_molecules=True)


def _declare(owner, *, file_inputs, native_molecules):
    _ready()
    _file_inputs(file_inputs)
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant completion declaration")
        if type(owner) is not previous.PreludeOwner or owner in _RETIRED:
            raise CompletionRejected("Actual unconsumed PreludeOwner required", stage="owner")
        parent = previous._authority(owner)
        _domain(parent, native_molecules=native_molecules)
        value = Request(
            owner,
            parent.trial.identity,
            _digest(source_plan()),
            file_inputs,
            "",
            native_molecules=native_molecules,
        )
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.trial,
            previous._snapshot(parent),
            previous._graph(parent),
        )
        return value


class CompletionClaim:
    """One actual active participation capability; data/records grant none."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only actual completion preparation issues a claim")

    def __reduce_ex__(self, protocol):
        raise TypeError("Actual active completion cannot be decoded or replayed")

    @property
    def parameters(self):
        context = _active(self)
        _check(context)
        return context.p

    @property
    def phase(self):
        context = _active(self)
        _check(context)
        return context.phase

    def check(self):
        _check(_active(self))

    @property
    def file_inputs(self):
        return _active(self).request.file_inputs

    @property
    def record(self):
        context = _CLAIMS.get(self)
        if context is None or context.active or context.invalid or context.trial is None:
            raise CompletionRejected("No successful closed completion record", stage="record")
        return context.trial


def validate_active(claim, *, original_owner):
    """Authenticate a live participation edge, without recursive tissue reads.

    Source dispatch and claim.check() perform the complete value/stream audit.
    This registry/ancestor surface is safe for a tissue validator called FROM
    that audit; it neither executes source work nor grants an extra epoch.
    """
    context = _active(claim)
    if context.request.prelude_owner is not original_owner:
        _reject(context, "Different original prelude owner")
    return claim


def _active(claim):
    if type(claim) is not CompletionClaim or claim not in _CLAIMS:
        raise CompletionRejected("Actual issued active CompletionClaim required", stage="claim")
    context = _CLAIMS[claim]
    _guard(context)
    _registry(context)
    return context


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = CompletionRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    raise context.entry_error


def _guard(context):
    return context.observer_namespace["_guard"](context)


def _scope(context):
    return previous._scope(context.parent)


def _objects(context):
    objects = list(context.init_parent.objects)
    if context.parent.gap is not None:
        objects.append(("gap_dynamics", context.parent.gap))
    if context.tissue_session is not None:
        for role, value in context.tissue.state_roots(context.tissue_session):
            if not any(value is actual for _, actual in objects):
                objects.append((role, value))
    if context.molecule_session is not None:
        for role, value in context.molecule.state_roots(context.molecule_session):
            if not any(value is actual for _, actual in objects):
                objects.append((role, value))
    return objects


def _values(context, *, stable=False):
    projector = previous.previous._projector(context.init_parent)
    projector.objects = [*projector.objects, *_objects(context)]
    project = previous.previous.core._LITERAL._project
    stores = SIM_STORES
    if context.request.native_molecules:
        stores = (*stores, *context.molecule.SIM_STORES)
    sim = {k: v for k, v in vars(context.sim).items() if not stable or k not in stores}
    cells = {k: v for k, v in vars(context.cells).items() if not stable or k != "cell_i"}

    def values(value):
        if context.molecule_session is not None:
            value = context.molecule.project_state(context.molecule_session, value)
        return project(projector, value)

    return dict(
        simulator=values(sim),
        cells=values(cells),
        parameters=values(vars(context.p)),
        objects=tuple(
            (role, values(vars(actual)))
            for role, actual in (context.original_objects if stable else _objects(context))
            if not stable
            or all(actual is not item for item in (context.sim, context.phase.dyna, context.cells))
        ),
        handler=None if stable else values(vars(context.phase.dyna)),
    )


def _snapshot(context, *, stable=False):
    return _scope(context).snapshot(_values(context, stable=stable))


def _graph(context):
    context.graph_fields[:] = [vars(value) for _, value in _objects(context)]
    if context.molecule_session is not None:
        context.graph_view.molecular = context.molecule.graph_roots(context.molecule_session)
    return _scope(context).graph(context.graph_view, context.graph_view, context.graph_tape)


def _streams(context):
    if (
        context.numpy.random.mtrand._rand is not context.np_rng
        or context.numpy.random.random.__self__ is not context.np_rng
        or context.stdlib._inst is not context.std_rng
        or context.shuffle.__self__ is not context.std_rng
    ):
        raise ValueError("Actual NumPy/stdlib RNG instance association changed")
    first = previous.previous._rng(context.init_parent)
    second = _scope(context).snapshot(context.std_getstate())
    return first, second


def _epoch(context):
    return (
        _snapshot(context).identity,
        _graph(context),
        tuple(v.identity for v in _streams(context)),
    )


def _cell_snapshot(context):
    if context.cells.cell_i is not context.cell_i:
        raise ValueError("Original cell_i array object replaced")
    return _scope(context).snapshot(context.cell_i)


def _same_refs(actual, expected):
    previous.previous.core.previous._same(actual, expected)


def _observer_bindings(context):
    namespace = context.observer_namespace
    if (
        tuple(namespace) != tuple(name for name, _ in context.observer_refs)
        or any(namespace[name] is not value for name, value in context.observer_refs)
        or context.account is not context.observer_account
    ):
        raise ValueError("Actual private observer namespace/entry changed")
    result = [context.observer_refs, context.observer_functions, context.observer_account]
    for function in context.observer_functions:
        result.extend(previous.previous._atoms(function))
    result.extend(previous.previous.core._resolved_bindings(context.observer_functions))
    return tuple(result)


def _binding(context):
    functions = (
        context.parent_claim,
        context.parent_check,
        *context.methods.values(),
        *context.source_functions,
        *context.helper_functions,
        context.np_random,
        context.shuffle,
        context.std_getstate,
    )
    values = [
        context.parent,
        context.parent_trial,
        context.phase,
        context.p,
        context.cells,
        context.sim,
        context.callback,
        context.claim,
        context.tissue,
        context.tissue_session,
        context.molecule,
        context.molecule_session,
        None if context.molecule is None else context.molecule.SIM_STORES,
        MOLECULE_INTERFACE_SHA256,
        MOLECULE_REVIEW_SHA256,
        context.np_rng,
        context.std_rng,
        context.np_random,
        context.shuffle,
        context.entries,
        context.namespace,
        context.observer_namespace,
        context.metadata,
        _STORAGE_FORWARDED,
        _STORAGE_LEASES,
        _ELECTRICAL_DESCENDANTS,
        _FIRST_STEP_DESCENDANTS,
        _SHORT_INIT_DESCENDANTS,
        _TERMINAL_INIT_DESCENDANTS,
        TERMINAL_RUNTIME_MODULE,
        TERMINAL_RUNTIME_SHA256,
        TERMINAL_RUNTIME_REVIEW_SHA256,
        STORAGE_INTERFACE_SHA256,
        STORAGE_REVIEW_SHA256,
        STORAGE_PARENT_REVIEW_SHA256,
        *_observer_bindings(context),
    ]
    for name, function in context.metadata:
        if globals().get(name) is not function:
            raise ValueError("Original completion checker replaced: " + name)
        values.extend(previous.previous._atoms(function))
    for function in functions:
        values.extend(previous.previous._atoms(function))
    tissue_functions = tuple(vars(context.tissue)[name] for name in TISSUE_API)
    molecule_functions = (
        ()
        if context.molecule is None
        else tuple(vars(context.molecule)[name] for name in MOLECULE_API)
    )
    for function in (*tissue_functions, *molecule_functions):
        values.extend(previous.previous._atoms(function))
    values.extend(
        previous.previous.core._resolved_bindings(
            tuple(
                f
                for f in (*functions, *tissue_functions, *molecule_functions)
                if type(f) is FunctionType
            )
        )
    )
    values.extend((context.numpy, *(getattr(context.numpy, n) for n in NUMPY_HELPERS)))
    return tuple(values)


def _registry(context):
    if (
        _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.prelude_owner) is not context
        or _CLAIMS.get(context.claim) is not context
        or _REQUESTS.get(context.request) is not context.refs
        or context.parent is not context.refs[0]
        or context.parent.trial is not context.refs[1]
        or context.parent_check(context) is not context.parent
        or context.phase is not context.parent.phase
        or context.phase.p is not context.p
        or context.phase.sim is not context.sim
        or context.phase.cells is not context.cells
        or context.phase.dyna is not context.handler
        or context.phase.callbacks is not context.callback
        or context.invalid
        or context.thread != get_ident()
        or context.request.identity != _digest(request_record(context.request))
        or type(context.request.native_molecules) is not bool
        or context.request.source_identity != _digest(source_plan())
    ):
        raise ValueError("Original one-shot completion/Prelude/phase/source association changed")


def _check(context, *, closed=False):
    if not closed:
        _guard(context)
    _registry(context)
    if context.bindings is not None:
        _same_refs(_binding(context), context.bindings)
    if (
        context.stable is not None
        and _snapshot(context, stable=True).identity != context.stable.identity
    ):
        raise ValueError("Unowned parameter/geometry/Simulator field changed")
    if context.draw_active is None and tuple(v.identity for v in _streams(context)) != tuple(
        v.identity for v in context.current_streams
    ):
        raise ValueError("Unobserved NumPy or stdlib RNG advancement")
    if _cell_snapshot(context).identity != context.current_cell_i.identity:
        raise ValueError("Unwitnessed cell_i buffer mutation")
    if not closed and context.tissue_session is not None:
        if (
            context.tissue.validate_active(context.tissue_session, completion_claim=context.claim)
            is not context.tissue_session
        ):
            raise ValueError("Different actual active tissue participation")
    if not closed and context.molecule_session is not None:
        if (
            context.molecule.validate_active(
                context.molecule_session, completion_claim=context.claim
            )
            is not context.molecule_session
        ):
            raise ValueError("Different actual active molecule participation")


def _capture(context, origin, error, raw):
    context.last_capture = (origin, error, raw)
    if context.capture_error is None:
        context.capture_error = error
    try:
        return context.observer_namespace["_record_capture"](context, origin, error, raw)
    except BaseException as secondary:
        context.reporting_failure = (secondary, context.last_capture)


def _helper(context, name, delegate, args, kwargs, frame):
    _check(context)
    if frame is not context.body_frame or frame.f_globals is not context.namespace:
        _reject(context, "Numerical/copy helper must be reached by the actual original tail")
    row = dict(
        name=name,
        delegate=delegate,
        args=args,
        kwargs=kwargs,
        frame=frame,
        returned=False,
        raw_return=None,
        error=None,
    )
    context.last_helper = row
    context.helper_calls.append(row)
    if len(context.work) + len(context.helper_calls) > MAX_WORK:
        _reject(context, "Bounded actual helper work exhausted")
    try:
        value = delegate(*args, **kwargs)
        row["raw_return"] = context.last_helper_return = value
        row["returned"] = True
        return value
    except BaseException as error:
        row["error"] = error
        if context.primary is None:
            context.primary = error
        raise


def rng_call(claim, *, participant, library, operation, delegate, args, kwargs, source_frame):
    """Invoke an actual original source-issued RNG delegate exactly once.

    Tissue calls need the actual typed participant and its original-frame
    witness. Tail random(mdl) has a distinct direct source-frame check. Neither
    an equal array nor a supplied RNG/state/receipt grants permission.
    """
    context = _active(claim)
    _check(context)
    if context.draw_active is not None or len(context.rng_calls) >= MAX_RNG_CALLS:
        _reject(context, "One active bounded original RNG source call required")
    if type(args) is not tuple or type(kwargs) is not dict:
        _reject(context, "Original actual RNG call argument containers required")
    view = None
    if participant is None:
        if (
            library != "numpy"
            or operation != "random"
            or delegate is not context.np_random
            or source_frame is not context.body_frame
            or source_frame.f_globals is not context.namespace
            or len(args) != 1
            or args[0] is not context.sim.mdl
            or kwargs
        ):
            _reject(context, "Exact unconditional native random(mdl) call required")
        context.channel_random_attempts += 1
        if context.channel_random_attempts != 1:
            _reject(context, "Duplicate native channel RNG call")
    else:
        if participant is not context.tissue_session:
            _reject(context, "Foreign tissue RNG participation")
        witness = context.tissue.validate_rng_call(
            participant,
            completion_claim=claim,
            library=library,
            operation=operation,
            delegate=delegate,
            args=args,
            kwargs=kwargs,
            source_frame=source_frame,
        )
        if (
            type(witness) is not context.tissue.RngWitness
            or witness.source_frame is not source_frame
        ):
            _reject(context, "Actual source-backed immutable tissue RNG witness required")
        if library == "numpy" and operation in ("shuffle", "choice"):
            if delegate.__self__ is not context.np_rng:
                _reject(context, "Original continuing NumPy shuffle owner required")
        elif library == "stdlib" and operation == "shuffle":
            if (
                delegate.__self__ is not context.std_rng
                or delegate.__func__ is not context.shuffle.__func__
            ):
                _reject(context, "Original native stdlib shuffle owner/function required")
        else:
            _reject(context, "Unowned RNG source operation")
        if witness.cell_i_view is not None:
            view = witness.cell_i_view
            if (
                library != "numpy"
                or operation != "shuffle"
                or len(args) != 1
                or args[0] is not view
                or source_frame.f_locals.get("cell_i_copy") is not view
                or type(view) is not context.numpy.ndarray
                or view.shape != context.cell_i.shape
                or view.dtype != context.cell_i.dtype
                or view.strides != context.cell_i.strides
                or view.ctypes.data != context.cell_i.ctypes.data
            ):
                _reject(context, "Actual original percent-picker full slice view required")
    row = SimpleNamespace(
        index=len(context.rng_calls),
        library=library,
        operation=operation,
        delegate=delegate,
        args=args,
        kwargs=kwargs,
        source_frame=source_frame,
        participant=participant,
        before=_streams(context),
        after=None,
        cell_before=_cell_snapshot(context),
        returned=False,
        raw_return=None,
        primary=None,
        capture_errors=(),
    )
    context.last_rng = context.draw_active = row
    context.rng_calls.append(row)
    before_items = (
        Counter(item.tobytes() for item in context.cell_i.flat) if view is not None else None
    )
    primary = None
    try:
        returned = delegate(*args, **kwargs)
        row.raw_return = context.last_rng_return = returned
        row.returned = True
    except BaseException as error:
        row.primary = primary = error
        if context.primary is None:
            context.primary = error
    finally:
        try:
            row.after = _streams(context)
            context.current_streams = row.after
        except BaseException as error:
            row.capture_errors += (("stream_after", error),)
            _capture(context, "rng_after", error, row)
        try:
            if view is not None:
                if Counter(item.tobytes() for item in context.cell_i.flat) != before_items:
                    raise ValueError("Original shuffle changed cell index membership/bits")
                context.current_cell_i = _cell_snapshot(context)
            elif _cell_snapshot(context).identity != row.cell_before.identity:
                raise ValueError("A non-percent RNG call changed cell_i")
        except BaseException as error:
            row.capture_errors += (("cell_i_after", error),)
            _capture(context, "rng_cell_i", error, row)
        context.draw_active = None
    if primary is not None:
        raise primary
    _check(context)
    return row.raw_return


def _wrapper_guard(context, original, frame):
    _check(context)
    if original is not context.init_parent:
        _reject(context, "Original retained INIT constructor context required")
    participant, session = context.tissue, context.tissue_session
    if context.molecule_session is not None and context.molecule.owns_source_frame(
        context.molecule_session, frame
    ):
        participant, session = context.molecule, context.molecule_session
    return participant.wrapper_guard(
        session, completion_claim=context.claim, original=original, frame=frame
    )


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    _check(context)
    if original is not context.init_parent:
        _reject(context, "Actual same-INIT source context required")
    participant, session = context.tissue, context.tissue_session
    if context.molecule_session is not None and context.molecule.owns_source_frame(
        context.molecule_session, frame
    ):
        participant, session = context.molecule, context.molecule_session
    return participant.dispatch(
        session,
        completion_claim=context.claim,
        original=original,
        label=label,
        delegate=delegate,
        actual=actual,
        args=args,
        kwargs=kwargs,
        frame=frame,
    )


def _namespace(context):
    native = context.init_parent.factories["Simulator"]
    callbacks = previous.previous.caches.previous.callbacks
    original = callbacks._source_function(
        native.init_dynamics, SIM_FILE, "init_dynamics", "Simulator"
    )
    globals_before = original.__globals__
    context.source_functions = (original,)
    context.numpy = globals_before["np"]
    context.np_rng = context.numpy.random.mtrand._rand
    if context.init_parent.parent.rng is not context.np_rng:
        raise ValueError("Actual source NumPy RNG does not continue the retained world")
    context.np_random = context.numpy.random.random
    tissue_module = sys.modules.get("betse.science.tissue.tishandler")
    if tissue_module is None:
        raise ValueError("Original actually loaded TissueHandler module required")
    context.shuffle = vars(tissue_module)["shuffle"]
    context.stdlib = sys.modules.get("random")
    if (
        context.stdlib is None
        or type(context.shuffle) is not MethodType
        or context.shuffle.__self__ is not context.stdlib._inst
    ):
        raise ValueError("Original native stdlib global shuffle instance required")
    context.std_rng = context.shuffle.__self__
    context.std_getstate = context.std_rng.getstate
    helpers = {name: getattr(context.numpy, name) for name in NUMPY_HELPERS}
    helpers.update(
        gaussian_filter=globals_before["gaussian_filter"], python_copy=globals_before["copy"].copy
    )
    context.original_helpers = MappingProxyType(helpers)
    wrappers = {}
    for name, delegate in helpers.items():

        def wrapped(*args, _name=name, _delegate=delegate, **kwargs):
            return _helper(context, _name, _delegate, args, kwargs, sys._getframe(1))

        wrappers[name] = wrapped

    def random(size):
        return rng_call(
            context.claim,
            participant=None,
            library="numpy",
            operation="random",
            delegate=context.np_random,
            args=(size,),
            kwargs={},
            source_frame=sys._getframe(1),
        )

    def unavailable(*args, **kwargs):
        _reject(context, "Unowned optional native factory/helper attempted entry")

    def native_molecules(p):
        return context.molecule.construct(
            context.molecule_session,
            p,
            completion_claim=context.claim,
            source_frame=sys._getframe(1),
        )

    namespace = dict(
        globals_before,
        np=SimpleNamespace(
            **{name: wrappers[name] for name in NUMPY_HELPERS},
            random=SimpleNamespace(random=random),
        ),
        copy=SimpleNamespace(copy=wrappers["python_copy"], deepcopy=unavailable),
        gaussian_filter=wrappers["gaussian_filter"],
        EndoRetic=unavailable,
        MasterOfMolecules=native_molecules if context.request.native_molecules else unavailable,
        MasterOfGenes=unavailable,
    )
    context.namespace = namespace
    context.methods = {"init_dynamics": FunctionType(_code(), namespace, "init_dynamics")}
    context.expected_body = context.methods["init_dynamics"].__code__
    context.helper_functions = previous.previous.core.previous.previous._native_helper_functions(
        tuple(helpers.values())
    )
    context.allowed_codes = frozenset(
        code
        for fn in (*context.methods.values(), *context.helper_functions)
        for code in previous.previous._code_tree(fn.__code__)
    )


def _observe(context, frame, event, arg):
    # A directly retained raw return/exception precedes the participant's
    # fallible locals copy. Its observer precedes every inherited callback.
    if event == "exception":
        context.last_source_error = (frame, arg[1])
        try:
            context.pending[id(frame)] = arg[1]
        except BaseException as capture:
            if context.primary is None:
                context.primary = arg[1]
            _capture(context, "source_exception_record", capture, (frame, event, arg))
    if event == "return" and any(frame.f_code is code for code in context.allowed_codes):
        context.observer_namespace["_witness"](context, frame, arg)
    if context.tissue_session is not None and any(
        frame.f_code is code for code in context.tissue_codes
    ):
        try:
            context.tissue.observe(
                context.tissue_session,
                completion_claim=context.claim,
                frame=frame,
                event=event,
                arg=arg,
            )
        except context.tissue.CaptureStop as signal:
            context.tissue_capture_signal = signal
            context.observation_error = signal.__cause__
            capture = signal if signal.__cause__ is None else signal.__cause__
            _capture(context, "tissue_observation", capture, (frame, event, arg, signal.partial))
            if context.primary is None:
                raise
    if (
        context.molecule_session is not None
        and any(frame.f_code is code for code in context.molecule_codes)
        and context.molecule.observes_source_frame(context.molecule_session, frame)
    ):
        try:
            context.molecule.observe(
                context.molecule_session,
                completion_claim=context.claim,
                frame=frame,
                event=event,
                arg=arg,
            )
        except context.molecule.CaptureStop as signal:
            context.molecule_capture_signal = signal
            context.observation_error = signal.__cause__
            capture = signal if signal.__cause__ is None else signal.__cause__
            _capture(context, "molecule_observation", capture, (frame, event, arg, signal.partial))
            if context.primary is None:
                raise
    if event == "call":
        selected = any(frame.f_code is code for code in context.allowed_codes)
        native = frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
        if not selected and not native:
            return
        attempt = dict(
            frame=frame,
            code=frame.f_code,
            globals=frame.f_globals,
            function=frame.f_code.co_qualname,
            returned=False,
            body_started=False,
        )
        context.last_attempt = attempt
        context.work.append(attempt)
        _check(context)
        if not selected or len(context.work) + len(context.helper_calls) > MAX_WORK:
            _reject(context, "Unknown/later source entry or work bound exhausted")
        if frame.f_code is context.expected_body:
            if (
                context.body_frame is not None
                or frame.f_back is not context.driver_frame
                or frame.f_globals is not context.namespace
                or frame.f_locals.get("self") is not context.sim
                or frame.f_locals.get("phase") is not context.phase
            ):
                _reject(context, "Actual original tail driver/receiver/phase required")
            context.body_frame = frame
        else:
            ancestor = frame.f_back
            while ancestor is not None and ancestor is not context.body_frame:
                ancestor = ancestor.f_back
            if ancestor is None or context.body_frame is None:
                _reject(context, "Actual selected helper is detached from original tail")
        context.frames[id(frame)] = attempt
        attempt["body_started"] = True
    row = context.frames.get(id(frame))
    if row is None:
        return
    if row["frame"] is not frame or row["globals"] is not frame.f_globals:
        _reject(context, "Original admitted source frame/namespace changed")
    if event == "line":
        _check(context)
    if event == "return":
        context.observer_namespace["_witness"](context, frame, arg)
        try:
            context.raw_returns.append(context.last_raw)
            context.locals[id(frame)] = dict(frame.f_locals)
        except BaseException as error:
            _capture(context, "source_return", error, context.last_raw)
        row["returned"] = True
        if frame is context.body_frame and previous.previous._normal_return(frame):
            context.body_returned, context.body_return = True, arg


def _observer_recipe(context):
    # Reuse exact prelude observation code in an owned private namespace. The
    # only declared substitutions are this tail's checker/snapshot/admission.
    namespace = dict(
        vars(previous),
        previous=previous.previous,
        DynamicsRejected=CompletionRejected,
        _check=_check,
        _reject=_reject,
        _observe=_observe,
        _epoch=_epoch,
        MAX_WORK=MAX_WORK,
        _ACTIVE=_ACTIVE,
    )
    for name in (
        "_record_capture",
        "_guard",
        "_witness",
        "_delegate",
        "_same_epoch",
        "_inherited",
        "_recover_hooks",
    ):
        fn = vars(previous)[name]
        namespace[name] = FunctionType(
            fn.__code__, namespace, name, fn.__defaults__, fn.__closure__
        )
    inherited = namespace["_inherited"]

    def inherited_with_rng_guard(current, observer, frame, event, arg):
        owner = getattr(arg, "__self__", None) if event == "c_call" else None
        sampling = event == "c_call" and getattr(arg, "__name__", None) in ("get_state", "getstate")
        if (owner is current.np_rng or owner is current.std_rng) and not sampling:
            if current.draw_active is None:
                _reject(current, "Unwitnessed call on an owned global RNG")
            row = current.draw_active
            expected_owner = current.np_rng if row.library == "numpy" else current.std_rng
            if owner is not expected_owner:
                _reject(current, "RNG call changed actual source stream")
        return inherited(current, observer, frame, event, arg)

    namespace["_inherited"] = inherited_with_rng_guard
    original = previous._account.__wrapped__
    account = FunctionType(
        original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__
    )
    context.observer_namespace = namespace
    context.account = contextmanager(account)
    context.observer_account = context.account
    context.observer_refs = tuple(namespace.items())
    context.observer_functions = tuple(
        namespace[name]
        for name in (
            "_record_capture",
            "_guard",
            "_check",
            "_reject",
            "_observe",
            "_witness",
            "_delegate",
            "_same_epoch",
            "_inherited",
            "_epoch",
            "_recover_hooks",
        )
    ) + (account, context.account)


def _context(request, refs, parent, tissue):
    init = parent.parent
    value = SimpleNamespace(
        request=request,
        refs=refs,
        parent=parent,
        parent_trial=refs[1],
        init_parent=init,
        phase=parent.phase,
        p=parent.p,
        cells=parent.cells,
        sim=parent.sim,
        handler=parent.phase.dyna,
        callback=parent.callback,
        tissue=tissue,
        tissue_session=None,
        tissue_record=None,
        tissue_functions=(),
        tissue_codes=frozenset(),
        molecule=None,
        molecule_session=None,
        molecule_record=None,
        molecule_functions=(),
        molecule_codes=frozenset(),
        claim=None,
        bindings=None,
        stable=None,
        stage="parent_retirement",
        thread=get_ident(),
        active=True,
        invalid=False,
        validating=False,
        primary=None,
        failure_error=None,
        observation_error=None,
        tissue_capture_signal=None,
        molecule_capture_signal=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        cleanup_errors=(),
        last_capture=None,
        reporting_failure=None,
        observing=False,
        inherited=False,
        work=[],
        frames={},
        pending={},
        raw_returns=[],
        locals={},
        c_calls=[],
        helper_calls=[],
        rng_calls=[],
        draw_active=None,
        last_rng=None,
        last_rng_return=None,
        channel_random_attempts=0,
        body_frame=None,
        body_returned=False,
        body_return=None,
        trial=None,
        before=None,
        after=None,
        after_graph=None,
        graph_fields=[],
        required_hooks=(sys.getprofile(), sys.gettrace()),
        setters=(sys.setprofile, sys.settrace),
        getters=(sys.getprofile, sys.gettrace),
        call_tracing=sys.call_tracing,
        hooks_safe=True,
        last_raw=None,
        cell_i=parent.cells.cell_i,
    )
    value.original_objects = tuple(_objects(value))
    value.metadata = tuple(
        (
            (name, globals()[name])
            for name in (
                "_ready",
                "_tissue_binding",
                "_check_tissue_backrefs",
                "_molecule_api",
                "source_plan",
                "_registry",
                "_check",
                "_binding",
                "_observer_bindings",
                "_scope",
                "_objects",
                "_values",
                "_snapshot",
                "_graph",
                "_streams",
                "_epoch",
                "_cell_snapshot",
                "_active",
                "_guard",
                "_reject",
                "_observe",
                "_namespace",
                "_helper",
                "rng_call",
                "_capture",
                "_run",
                "_finish",
                "_observer_recipe",
                "prepare",
                "_authority",
                "validate_active",
                "_file_inputs",
                "_domain",
                "_declare",
                "from_prelude_native_molecules",
                "_closed_epoch",
                "_storage_binding",
                "_storage_api",
                "_storage_route",
                "_storage_values",
                "_storage_graph",
                "_claim_for_init_storage",
                "_check_init_storage_authority",
                "_storage_metadata",
                "_electrical_route",
                "_electrical_values",
                "_electrical_graph",
                "_claim_electrical_ancestor",
                "_check_electrical_ancestor",
                "_first_step_route",
                "_first_step_values",
                "_first_step_graph",
                "_first_step_permissions",
                "_claim_first_step_ancestor",
                "_check_first_step_ancestor",
                "_first_step_runtime_permissions",
                "_advance_lease",
                "_check_advance_ancestor",
                "_molecule_short_api",
                "_short_init_route",
                "_claim_short_init_ancestor",
                "_check_short_init_ancestor",
                "_molecule_terminal_api",
                "_terminal_init_route",
                "_claim_terminal_init_ancestor",
                "_check_terminal_init_ancestor",
            )
        )
    )
    value.graph_view = SimpleNamespace(
        fields=value.graph_fields,
        parameters=vars(value.p),
        cells=vars(value.cells),
        source_work=value.work,
        rng_records=value.rng_calls,
    )
    value.graph_tape = SimpleNamespace(
        rng=init.graph_tape.rng, events=value.raw_returns, draws=value.c_calls, locals=value.locals
    )
    return value


def _run(context):
    context.driver_frame = sys._getframe()
    return context.methods["init_dynamics"](context.sim, context.phase)


def _finish(context):
    if (
        not context.body_returned
        or context.body_return is not None
        or context.primary is not None
        or context.capture_error is not None
        or context.cleanup_errors
        or context.draw_active is not None
        or context.channel_random_attempts != 1
        or any(not row["returned"] for row in context.work)
    ):
        raise ValueError("Complete original tail, mandatory RNG and observations required")
    context.tissue_record = context.tissue.finish(
        context.tissue_session, completion_claim=context.claim
    )
    if context.tissue_record is None:
        raise ValueError("Actual successful tissue participation record required")
    if context.molecule_session is not None:
        context.molecule_record = context.molecule.finish(
            context.molecule_session, completion_claim=context.claim
        )
        if context.molecule_record is None:
            raise ValueError("Actual successful molecular participation record required")
    _check(context)


def _rng_record(row):
    return dict(
        index=row.index,
        library=row.library,
        operation=row.operation,
        source_frame=id(row.source_frame),
        delegate=id(row.delegate),
        before=tuple(v.identity for v in row.before),
        after=None if row.after is None else tuple(v.identity for v in row.after),
        returned=row.returned,
        raw_return=id(row.raw_return),
        primary=None if row.primary is None else id(row.primary),
        metadata_capture_complete=not row.capture_errors,
        independent_case=False,
    )


def trial_record(value):
    result = dict(
        request=value.request_identity,
        parent=value.parent_identity,
        before=value.before.identity,
        after=value.after.identity,
        stream_before=tuple(v.identity for v in value.stream_before),
        stream_after=tuple(v.identity for v in value.stream_after),
        rng_calls=tuple(_rng_record(row) for row in value.rng_calls),
        work=tuple(
            (row["code"].co_filename, row["function"], id(row["frame"]), row["returned"])
            for row in value.work
        ),
        c_calls=tuple((id(frame), event, id(delegate)) for frame, event, delegate in value.c_calls),
        raw_returns=tuple((id(frame), id(raw)) for frame, raw in value.raw_returns),
        tissue_record=id(value.tissue_record),
        tail_source_completed=value.source_completed,
        whole_init_dynamics_source_equivalence="Same state; split original-body projections",
        timesteps_completed=0,
        completed_INIT_or_independent_case=False,
    )
    if value.molecule_record is not None:
        result["molecule_record"] = id(value.molecule_record)
    return result


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise CompletionRejected("Actual source/RNG completion remains held", stage="release")
    tissue = _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant completion preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise CompletionRejected(
                "Actual issued process-local Request required", stage="request"
            )
        if request in _CONSUMED or request.prelude_owner in _RETIRED:
            raise CompletionRejected("Original prelude epoch already attempted", stage="consumed")
        refs = _REQUESTS[request]
        parent = previous._authority(request.prelude_owner)
        _file_inputs(request.file_inputs)
        _domain(parent, native_molecules=request.native_molecules)
        graph = previous._graph(parent)
        _same_refs(graph[0], refs[3][0])
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or previous._snapshot(parent).identity != refs[2].identity
            or graph[1] != refs[3][1]
            or request.identity != _digest(request_record(request))
            or request.source_identity != _digest(source_plan())
        ):
            raise CompletionRejected("Original closed prelude source/state changed", stage="parent")
        context = _context(request, refs, parent, tissue)
        claim = object.__new__(CompletionClaim)
        context.claim = claim
        _CLAIMS[claim] = _CONSUMED[request] = _RETIRED[request.prelude_owner] = context
        _ACTIVE.append(context)
        primary = None
        try:
            context.parent_claim, context.parent_check = (
                getattr(previous, PARENT_CLAIM),
                getattr(previous, PARENT_CHECK),
            )
            context.entries = MappingProxyType(
                dict(
                    wrapper_guard=_wrapper_guard,
                    dispatch=_dispatch,
                    validate_active=validate_active,
                    rng_call=rng_call,
                )
            )
            context.parent_claim(
                request.prelude_owner, expected=refs[1], transition=context, entries=context.entries
            )
            _observer_recipe(context)
            if request.native_molecules:
                context.molecule = _molecule_api()
            _namespace(context)
            context.current_streams = context.stream_before = _streams(context)
            context.current_cell_i = _cell_snapshot(context)
            context.stage = "tissue_source_binding"
            context.tissue_session = tissue.bind_completion(
                claim, original_owner=request.prelude_owner
            )
            if context.tissue_session is None:
                raise ValueError("Actual typed source-backed tissue session required")
            context.tissue_functions = tissue.source_members(context.tissue_session)
            if type(context.tissue_functions) is not tuple or any(
                type(fn) is not FunctionType for fn in context.tissue_functions
            ):
                raise ValueError("Bound actual tissue original function roster required")
            context.allowed_codes = frozenset(
                (
                    *context.allowed_codes,
                    *(
                        code
                        for fn in context.tissue_functions
                        for code in previous.previous._code_tree(fn.__code__)
                    ),
                )
            )
            context.tissue_codes = frozenset(
                code
                for fn in context.tissue_functions
                for code in previous.previous._code_tree(fn.__code__)
            )
            if request.native_molecules:
                context.stage = "molecule_source_binding"
                session = context.molecule.bind_completion(
                    claim, original_owner=request.prelude_owner
                )
                if session is None or session is not context.molecule_session:
                    raise ValueError("Actual original molecule session/claim association required")
                context.molecule_functions = context.molecule.source_members(session)
                if type(context.molecule_functions) is not tuple or any(
                    type(fn) is not FunctionType for fn in context.molecule_functions
                ):
                    raise ValueError("Original molecule source function roster required")
                context.molecule_codes = frozenset(
                    code
                    for fn in context.molecule_functions
                    for code in previous.previous._code_tree(fn.__code__)
                )
                context.allowed_codes = frozenset((*context.allowed_codes, *context.molecule_codes))
            context.bindings = _binding(context)
            context.before = _snapshot(context)
            context.stable = _snapshot(context, stable=True)
            context.stage = "actual_original_INIT_dynamics_tail"
            with context.account(context):
                context.raw_tail_return = _run(context)
            _finish(context)
            context.after = _snapshot(context)
            context.after_graph = _graph(context)
            streams_after = _streams(context)
            record = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                context.stream_before,
                streams_after,
                tuple(context.rng_calls),
                tuple(context.work),
                tuple(context.c_calls),
                tuple(context.raw_returns),
                context.tissue_record,
                True,
                "",
                context.molecule_record,
            )
            context.trial = replace(record, identity=_digest(trial_record(record)))
        except BaseException as error:
            primary = context.primary if context.primary is not None else error
            context.failure_error, context.invalid = primary, True
            if (
                primary is context.tissue_capture_signal
                or primary is context.molecule_capture_signal
            ):
                context.primary = None
            else:
                context.primary = primary
            _FAILED.append(context)
            try:
                primary.init_dynamics_completion_partial = context
                primary.completion_claim = claim
            except BaseException as secondary:
                context.cleanup_errors += (("attachment", secondary, primary),)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
            # Independent trusted recovery after every fallible source/record
            # callback, preserving original primary/cause and all secondary rows.
            for index in (1, 0):
                try:
                    context.setters[index](context.required_hooks[index])
                except BaseException as error:
                    context.cleanup_errors += (("terminal_restore", error, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.getters[index]()
                    except BaseException as error:
                        context.cleanup_errors += (("terminal_sample", error, index),)
                samples.append(tuple(pair))
            context.final_hooks = tuple(samples)
            context.hooks_safe = all(
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if primary is not None:
            raise primary
        if context.invalid or context.cleanup_errors or not context.hooks_safe:
            context.invalid = True
            _FAILED.append(context)
            raise CompletionRejected(
                "Completion observation/publication refused", stage="closure", partial=context
            )
        owner = object.__new__(DynamicsOwner)
        context.owner = owner
        _ISSUED[owner] = (context, context.trial)
        return owner


class DynamicsOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only actual same-phase completion issues an owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("No native checkpoint or decoded owner authority")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not DynamicsOwner or owner not in _ISSUED:
        raise CompletionRejected("Actual issued DynamicsOwner required", stage="owner")
    context, issued = _ISSUED[owner]
    if owner in _STORAGE_FORWARDED or hasattr(context, "storage_transition"):
        raise CompletionRejected(
            "Dynamics epoch consumed by its actual storage successor",
            stage="storage_forwarded",
            trial=issued,
            partial=context,
        )
    if context.active or context.invalid or context.validating:
        raise CompletionRejected("Closed completion epoch unavailable", stage="owner")
    context.validating = True
    try:
        _closed_epoch(context, issued)
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False


def _closed_epoch(context, issued):
    """Original complete state proof, before any storage ownership transfer."""
    _ready()
    _file_inputs(context.request.file_inputs)
    _check(context, closed=True)
    if (
        context.tissue.validate_closed(context.tissue_session, completion_claim=context.claim)
        is not context.tissue_record
    ):
        raise ValueError("Original successful tissue participation record changed")
    if context.molecule_session is not None:
        if (
            context.molecule.validate_closed(
                context.molecule_session, completion_claim=context.claim
            )
            is not context.molecule_record
        ):
            raise ValueError("Original successful molecular participation record changed")
    graph = _graph(context)
    _same_refs(graph[0], context.after_graph[0])
    if (
        graph[1] != context.after_graph[1]
        or _snapshot(context).identity != context.after.identity
        or context.trial is not issued
        or issued.identity != _digest(trial_record(issued))
    ):
        raise ValueError("Closed original tail values/aliases/work/record changed")


def failed_context(claim):
    if type(claim) is not CompletionClaim or claim not in _CLAIMS:
        raise CompletionRejected("Actual issued completion claim required", stage="claim")
    context = _CLAIMS[claim]
    if context.active or not context.invalid:
        raise CompletionRejected("No closed failed completion attempt", stage="failure")
    return context


def _storage_binding(payload):
    return FunctionType(
        previous.previous._dynamics_binding.__code__,
        dict(
            vars(previous.previous),
            DYNAMICS_BACK_REFERENCE_SLOTS=STORAGE_BACK_REFERENCE_SLOTS,
            DYNAMICS_BINDING_KIND=STORAGE_BINDING_KIND,
        ),
    )(payload)


def _storage_api():
    if not all(
        (
            _pin(value)
            for value in (
                STORAGE_INTERFACE_SHA256,
                STORAGE_REVIEW_SHA256,
                STORAGE_PARENT_REVIEW_SHA256,
            )
        )
    ):
        raise CompletionRejected(
            "Reviewed actual storage successor remains held", stage="storage_held"
        )
    path = Path(__file__).parents[3] / ("src/" + STORAGE_MODULE.replace(".", "/") + ".py")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Actual original storage consumer source required")
    raw = path.read_bytes()
    identity, backrefs = _storage_binding(raw)
    if identity != STORAGE_INTERFACE_SHA256 or backrefs != (
        ("PARENT_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("PARENT_REVIEW_SHA256", STORAGE_PARENT_REVIEW_SHA256),
    ):
        raise ValueError(
            "Original storage bytes or Dynamics producer/review back-reference changed"
        )
    module = sys.modules.get(STORAGE_MODULE)
    if (
        type(module) is not ModuleType
        or Path(module.__file__).resolve() != path
        or module.previous is not sys.modules[__name__]
        or any((getattr(module, name) != value for name, value in backrefs))
        or (module.PARENT_CLAIM != "_claim_for_init_storage")
        or (module.PARENT_CHECK != "_check_init_storage_authority")
    ):
        raise ValueError("Actual original storage namespace/handoff changed")
    api = previous.previous.previous._ready()
    api._source_interface(
        module,
        raw,
        path,
        (
            "prepare",
            "_ready",
            "_wrapper_guard",
            "_dispatch",
            "_run",
            "_stores",
            "trial_record",
            "_check",
            "_binding",
            "_bootstrap",
            "_observer_bindings",
            "_observer_recipe",
            "_electrical_api",
            "_electrical_route",
            "_claim_for_electrical",
            "_check_electrical_authority",
            "_closed_storage_epoch",
            "_first_step_key_api",
            "_check_first_step_key_binding",
            "_claim_first_step_ancestor",
            "_check_first_step_ancestor",
            "_terminal_init_key_api",
            "_claim_terminal_init_ancestor",
            "_check_terminal_init_ancestor",
        ),
    )
    module._ready()
    return module


def _storage_route(context):
    """Original registry/frame permission; no stale before-storage data read."""
    module = _storage_api()
    owner = getattr(context, "owner", None)
    if type(owner) is not DynamicsOwner:
        raise ValueError("Original actual completed DynamicsOwner required")
    issued, lease = _ISSUED.get(owner), _STORAGE_LEASES.get(owner)
    child = getattr(context, "storage_transition", None)
    if (
        issued is None
        or issued[0] is not context
        or issued[1] is not context.trial
        or lease is None
        or context.storage_lease is not lease
        or lease.parent is not context
        or lease.owner is not owner
        or lease.child is not child
        or _STORAGE_FORWARDED.get(owner) is not child
        or context.active
        or context.invalid
        or context.thread != get_ident()
        or child.invalid
        or child.thread != context.thread
        or type(child.request) is not module.Request
        or child.request.dynamics_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.parent is not context
        or child.refs[0] is not context
        or child.refs[1] is not lease.trial
        or child.phase is not context.phase
        or child.p is not context.p
        or child.cells is not context.cells
        or child.sim is not context.sim
        or child.handler is not context.handler
        or child.cache is not lease.cache
        or context.phase.cache is not lease.cache
        or context.phase.callbacks is not context.callback
        or child.entries is not lease.entries
        or context.storage_entries is not lease.entries
        or tuple(lease.entries) != ("wrapper_guard", "dispatch")
        or lease.entries["wrapper_guard"] is not module._wrapper_guard
        or lease.entries["dispatch"] is not module._dispatch
    ):
        raise ValueError("Original one-shot Dynamics/storage/phase registry association changed")
    if child.active:
        if not module._ACTIVE or module._ACTIVE[-1] is not child:
            raise ValueError("Actual exclusive active storage attempt required")
    else:
        if type(getattr(child, "owner", None)) is not module.StorageOwner:
            raise ValueError("Actual successfully closed StorageOwner required")
        published = module._ISSUED.get(child.owner)
        if (
            published is None
            or published[0] is not child
            or published[1] is not child.trial
            or child.trial is None
            or child.trial.source_completed is not True
        ):
            raise ValueError("Original successful closed storage record changed")
    frame = child.body_frame
    if frame is None:
        if lease.body_frame is not None:
            raise ValueError("Observed original storage body frame disappeared")
    else:
        row = child.frames.get(id(frame))
        if (
            row is None
            or row["frame"] is not frame
            or row["body_started"] is not True
            or frame.f_code is not child.expected_body
            or frame.f_globals is not child.namespace
            or frame.f_locals.get("self") is not context.sim
            or frame.f_locals.get("cells") is not context.cells
            or frame.f_locals.get("p") is not context.p
            or frame.f_back is not child.body_driver
            or child.body_driver.f_code is not module._dispatch.__code__
            or child.body_driver.f_globals is not vars(module)
            or (lease.body_frame is not None and lease.body_frame is not frame)
        ):
            raise ValueError("Original once-dispatched storage source frame changed")
        lease.body_frame = frame
    return child, module


def _storage_values(context):
    lease = context.storage_lease
    project = previous.previous.core._LITERAL._project
    projector = previous.previous._projector(context.init_parent)
    projector.objects = [*projector.objects, *lease.objects]
    for (_, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, lease.fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original retained Dynamics holder changed during storage")
        ignored = lease.allowed if actual is context.sim else frozenset()
        ignored |= next(
            (
                fields
                for owner, fields in getattr(lease, "molecule_permissions", ())
                if owner is actual
            ),
            frozenset(),
        )
        if tuple(name for name in holder if name not in ignored) != tuple(
            name for name in names if name not in ignored
        ):
            raise ValueError("Storage changed an unowned original field roster")
        target.clear()
        target.update((name, holder[name]) for name in names if name not in ignored)
    values = tuple(lease.fields)
    if getattr(context, "molecule_session", None) is not None:
        values = context.molecule.project_state(context.molecule_session, values)
    return _scope(context).snapshot(project(projector, values))


def _storage_graph(context):
    _storage_values(context)
    lease = context.storage_lease
    return _scope(context).graph(lease.view, lease.view, lease.tape)


def _claim_for_init_storage(owner, *, expected, transition, entries):
    """Consume exactly one actual successful Dynamics epoch before source work."""
    module = _storage_api()
    frame = sys._getframe(1)
    with _LOCK:
        issued = _ISSUED.get(owner) if type(owner) is DynamicsOwner else None
        if (
            issued is None
            or issued[1] is not expected
            or frame.f_code is not module.prepare.__code__
            or frame.f_globals is not vars(module)
            or frame.f_locals.get("context") is not transition
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
        ):
            raise CompletionRejected("Actual active storage issuer required", stage="storage_entry")
        context = issued[0]
        if owner in _STORAGE_FORWARDED or hasattr(context, "storage_transition"):
            raise CompletionRejected(
                "Dynamics storage epoch already attempted", stage="storage_consumed"
            )
        if (
            context.active
            or context.invalid
            or context.validating
            or context.owner is not owner
            or transition.parent is not context
            or transition.refs[1] is not expected
            or transition.entries is not entries
            or transition.thread != context.thread
            or context.thread != get_ident()
        ):
            context.invalid = transition.invalid = True
            raise ValueError("Original closed Dynamics/storage association changed")
        _STORAGE_FORWARDED[owner] = transition
        context.storage_transition = transition
        try:
            _closed_epoch(context, expected)
            fields = tuple(name for _, name in module._stores())
            if len(fields) != 52 or len(set(fields)) != 51:
                raise ValueError("Exact original storage field declaration required")
            objects = tuple(_objects(context))
            ancestor = vars(previous.previous).get(STORAGE_ANCESTOR_CLAIM)
            lease = SimpleNamespace(
                parent=context,
                owner=owner,
                child=transition,
                trial=expected,
                entries=entries,
                cache=context.phase.cache,
                bindings=context.bindings,
                refs=context.refs,
                metadata=context.metadata,
                allowed=frozenset(fields),
                objects=objects,
                holders=tuple(vars(actual) for _, actual in objects),
                names=tuple(tuple(vars(actual)) for _, actual in objects),
                fields=[{} for _ in objects],
                body_frame=None,
                streams=tuple(value.identity for value in _streams(context)),
                cell_i=context.cell_i,
                cell_state=_cell_snapshot(context),
                tissue_context=context.tissue._context(context.tissue_session, context.claim),
                ancestor=ancestor,
            )
            lease.view = SimpleNamespace(objects=objects, fields=lease.fields)
            lease.tape = SimpleNamespace(rng=context.np_rng, events=(), draws=(), locals={})
            context.storage_lease = lease
            context.storage_entries = entries
            _STORAGE_LEASES[owner] = lease
            if (
                type(ancestor) is not FunctionType
                or ancestor.__globals__ is not vars(previous.previous)
                or ancestor(context.init_parent, context, transition) is not context.init_parent
            ):
                raise ValueError("Actual retained INIT storage ancestor claim is unavailable")
            if context.request.native_molecules:
                lease.molecule_claim = context.molecule.bind_storage(
                    context.molecule_session, completion=context, storage=transition
                )
                lease.molecule_permissions = context.molecule.runtime_permissions(
                    lease.molecule_claim
                )
            lease.values, lease.graph = _storage_values(context), _storage_graph(context)
            _check_init_storage_authority(transition)
            return context
        except BaseException as error:
            context.storage_error = error
            context.invalid = transition.invalid = True
            raise


def _check_init_storage_authority(transition):
    context = transition.parent
    if _storage_route(context)[0] is not transition:
        raise ValueError("Different original storage transition")
    successor = _ELECTRICAL_DESCENDANTS.get(context.owner)
    if successor is not None:
        return _check_electrical_ancestor(context, transition, successor.child)
    _storage_metadata(context)
    lease = context.storage_lease
    if _storage_values(context).identity != lease.values.identity:
        raise ValueError("Storage changed an unowned original Dynamics value")
    graph = _storage_graph(context)
    _same_refs(graph[0], lease.graph[0])
    if graph[1] != lease.graph[1]:
        raise ValueError("Storage changed an original unowned reference/alias edge")
    return context


def _storage_metadata(context):
    """Original closed metadata/streams only; no historical numeric snapshot."""
    lease = context.storage_lease
    _ready()
    _file_inputs(context.request.file_inputs)
    _registry(context)
    if (
        context.trial is not lease.trial
        or context.trial.source_completed is not True
        or context.trial.identity != _digest(trial_record(context.trial))
        or context.bindings is not lease.bindings
        or context.metadata is not lease.metadata
        or context.refs is not lease.refs
        or context.cell_i is not lease.cell_i
        or vars(previous.previous).get(STORAGE_ANCESTOR_CLAIM) is not lease.ancestor
        or context.tissue._context(context.tissue_session, context.claim)
        is not lease.tissue_context
        or _cell_snapshot(context).identity != lease.cell_state.identity
        or tuple(value.identity for value in _streams(context)) != lease.streams
    ):
        raise ValueError("Original closed Dynamics state/source/stream ancestry changed")
    # Metadata-only session/producer registry audit. Its old full-state reader
    # is intentionally not called after the separately owned storage mutation.
    context.tissue._registry(lease.tissue_context, closed=True)
    _same_refs(_binding(context), lease.bindings)
    return context


def _electrical_route(context, storage, electrical):
    """Authenticate the actual grandchild registries without stale value reads."""
    actual_storage, module = _storage_route(context)
    if actual_storage is not storage:
        raise ValueError("Different actual Storage context")
    child, producer = module._electrical_route(storage)
    lease = _ELECTRICAL_DESCENDANTS.get(context.owner)
    if (
        child is not electrical
        or lease is None
        or getattr(context, "electrical_descendant", None) is not lease
        or lease.parent is not context
        or lease.storage is not storage
        or lease.child is not electrical
        or lease.module is not module
        or lease.producer is not producer
        or lease.status != "ready"
        or electrical.parent is not context
        or electrical.storage_parent is not storage
        or electrical.phase is not context.phase
        or electrical.p is not context.p
        or electrical.sim is not context.sim
        or electrical.cells is not context.cells
        or electrical.handler is not context.handler
        or electrical.cache is not context.phase.cache
        or storage.electrical_lease is not lease.storage_lease
        or storage.trial is not lease.storage_trial
        or storage.trial.source_completed is not True
        or storage.trial.identity != module._digest(module.trial_record(storage.trial))
        or storage.refs is not lease.storage_refs
        or storage.bindings is not lease.storage_bindings
        or storage.metadata is not lease.storage_metadata
        or storage.electrical_lease.ancestor is not _claim_electrical_ancestor
        or module.ELECTRICAL_ANCESTOR_CLAIM != "_claim_electrical_ancestor"
        or vars(previous.previous).get(ELECTRICAL_ANCESTOR_CLAIM) is not lease.ancestor
    ):
        raise ValueError("Original Completion/storage/electrical ancestry changed")
    current = frozenset(name for _, _, name in producer._stores(producer._definitions()))
    if len(current) != 27 or current != lease.allowed:
        raise ValueError("Exact source-derived27 electrical fields changed")
    module._bootstrap(storage)
    _same_refs(module._binding(storage), lease.storage_bindings)
    return lease


def _electrical_values(context):
    """Factor only storage fields and the separately owned27 electrical fields."""
    lease = context.electrical_descendant
    project = previous.previous.core._LITERAL._project
    projector = previous.previous._projector(context.init_parent)
    projector.objects = [*projector.objects, *lease.objects]
    for (_, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, lease.fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original Completion holder replaced during electrical work")
        ignored = lease.allowed | lease.storage_allowed if actual is context.sim else frozenset()
        ignored |= next(
            (
                fields
                for owner, fields in getattr(
                    getattr(context, "storage_lease", None), "molecule_permissions", ()
                )
                if owner is actual
            ),
            frozenset(),
        )
        if tuple(name for name in holder if name not in ignored) != tuple(
            name for name in names if name not in ignored
        ):
            raise ValueError("Electrical work changed an unowned Completion field roster")
        target.clear()
        target.update((name, holder[name]) for name in names if name not in ignored)
    values = tuple(lease.fields)
    if getattr(context, "molecule_session", None) is not None:
        values = context.molecule.project_state(context.molecule_session, values)
    return _scope(context).snapshot(project(projector, values))


def _electrical_graph(context):
    _electrical_values(context)
    lease = context.electrical_descendant
    return _scope(context).graph(lease.view, lease.view, lease.tape)


def _claim_electrical_ancestor(context, storage, electrical):
    """One actual storage-issuer call, before any original electrical source."""
    module = _storage_api()
    frame = sys._getframe(1)
    with _LOCK:
        if (
            frame.f_code is not module._claim_for_electrical.__code__
            or frame.f_globals is not vars(module)
            or frame.f_locals.get("context") is not storage
            or frame.f_locals.get("transition") is not electrical
            or _storage_route(context)[0] is not storage
            or storage.parent is not context
            or storage.electrical_transition is not electrical
            or storage.electrical_lease.child is not electrical
            or storage.electrical_lease.ancestor is not _claim_electrical_ancestor
            or module._ELECTRICAL_FORWARDED.get(storage.owner) is not electrical
            or not electrical.active
            or electrical.invalid
            or electrical.body_frame is not None
            or electrical.thread != get_ident()
        ):
            raise CompletionRejected(
                "Actual once-only storage electrical ancestor issuer required",
                stage="electrical_entry",
            )
        if context.owner in _ELECTRICAL_DESCENDANTS or hasattr(context, "electrical_descendant"):
            context.invalid = storage.invalid = electrical.invalid = True
            raise CompletionRejected(
                "Completion electrical descendant already attempted", stage="electrical_consumed"
            )
        lease = SimpleNamespace(
            parent=context,
            storage=storage,
            child=electrical,
            module=module,
            storage_lease=storage.electrical_lease,
            storage_trial=storage.trial,
            storage_refs=storage.refs,
            storage_bindings=storage.bindings,
            storage_metadata=storage.metadata,
            status="authenticating_original",
            primary=None,
        )
        _ELECTRICAL_DESCENDANTS[context.owner] = context.electrical_descendant = lease
        try:
            # This proof runs once, before the grandchild can mutate anything.
            # Later checks authenticate only retained metadata and new factored
            # projections; neither closed old numeric reader is re-entered.
            _storage_metadata(context)
            old = context.storage_lease
            if _storage_values(context).identity != old.values.identity:
                raise ValueError(
                    "Original Completion/storage values changed before electrical claim"
                )
            graph = _storage_graph(context)
            _same_refs(graph[0], old.graph[0])
            if graph[1] != old.graph[1]:
                raise ValueError(
                    "Original Completion/storage aliases changed before electrical claim"
                )
            child, producer = module._electrical_route(storage)
            if child is not electrical:
                raise ValueError("Different original electrical child")
            lease.producer = producer
            lease.allowed = frozenset(
                name for _, _, name in producer._stores(producer._definitions())
            )
            if len(lease.allowed) != 27:
                raise ValueError("Exactly27 source-derived electrical Simulator fields required")
            lease.storage_allowed = old.allowed
            objects = list(old.objects)
            for role, actual in (("parameters", context.p), ("cells", context.cells)):
                if not any(value is actual for _, value in objects):
                    objects.append((role, actual))
            lease.objects = tuple(objects)
            lease.holders = tuple(vars(value) for _, value in lease.objects)
            lease.names = tuple(tuple(holder) for holder in lease.holders)
            lease.fields = [{} for _ in lease.objects]
            lease.view = SimpleNamespace(objects=lease.objects, fields=lease.fields)
            lease.tape = SimpleNamespace(rng=context.np_rng, events=(), draws=(), locals={})
            # The new owner has not run yet: freeze even its future fields
            # across fallible ancestor publication, rather than laundering an
            # inherited callback mutation into the new baseline.
            entry = {
                name: value for name, value in vars(context.sim).items() if name in lease.allowed
            }
            entry_view = SimpleNamespace(fields=entry)
            entry_value = _scope(context).snapshot(entry)
            entry_graph = _scope(context).graph(entry_view, entry_view, lease.tape)
            lease.ancestor = vars(previous.previous).get(ELECTRICAL_ANCESTOR_CLAIM)
            if type(lease.ancestor) is not FunctionType or lease.ancestor.__globals__ is not vars(
                previous.previous
            ):
                raise ValueError("Actual retained INIT electrical ancestor hooks unavailable")
            if (
                lease.ancestor(context.init_parent, context, storage, electrical)
                is not context.init_parent
            ):
                raise ValueError("Different actual retained INIT electrical ancestor")
            current_entry = {
                name: value for name, value in vars(context.sim).items() if name in lease.allowed
            }
            if (
                electrical.body_frame is not None
                or tuple(current_entry) != tuple(entry)
                or _scope(context).snapshot(current_entry).identity != entry_value.identity
            ):
                raise ValueError("Electrical fields changed before original source entry")
            entry.clear()
            entry.update(current_entry)
            current_graph = _scope(context).graph(entry_view, entry_view, lease.tape)
            _same_refs(current_graph[0], entry_graph[0])
            if current_graph[1] != entry_graph[1]:
                raise ValueError("Electrical field aliases changed before original source entry")
            lease.values, lease.graph = _electrical_values(context), _electrical_graph(context)
            lease.status = "ready"
            _check_electrical_ancestor(context, storage, electrical)
            return context
        except BaseException as error:
            lease.status, lease.primary = "failed", error
            context.invalid = storage.invalid = electrical.invalid = True
            raise


def _check_electrical_ancestor(context, storage, electrical):
    """Current metadata and factored graph; no stale Completion/Storage reader."""
    terminal = _TERMINAL_INIT_DESCENDANTS.get(getattr(context, "owner", None))
    if terminal is not None:
        if context.owner in _FIRST_STEP_DESCENDANTS or context.owner in _SHORT_INIT_DESCENDANTS:
            raise ValueError("Exclusive actual natural terminal descendant required")
        return _check_terminal_init_ancestor(context, storage, electrical, terminal.child)
    leaf = _FIRST_STEP_DESCENDANTS.get(getattr(context, "owner", None))
    if leaf is not None:
        return _check_first_step_ancestor(context, storage, electrical, leaf.child)
    short = _SHORT_INIT_DESCENDANTS.get(getattr(context, "owner", None))
    if short is not None:
        return _check_short_init_ancestor(context, storage, electrical, short.child)
    lease = _electrical_route(context, storage, electrical)
    _storage_metadata(context)
    if _electrical_values(context).identity != lease.values.identity:
        raise ValueError("Electrical work changed an unowned original Completion value")
    graph = _electrical_graph(context)
    _same_refs(graph[0], lease.graph[0])
    if graph[1] != lease.graph[1]:
        raise ValueError("Electrical work changed an unowned Completion reference/alias edge")
    return context


def _first_step_route(context, storage, electrical, transition):
    """Actual live first-step route, never a record or old numeric validator."""
    original = _electrical_route(context, storage, electrical)
    binding = original.module._electrical_api()
    producer = binding.module
    child, module = producer._first_step_route(electrical)
    lease = _FIRST_STEP_DESCENDANTS.get(context.owner)
    if (
        child is not transition
        or lease is None
        or getattr(context, "first_step_descendant", None) is not lease
        or (lease.parent is not context)
        or (lease.storage is not storage)
        or (lease.electrical is not electrical)
        or (lease.child is not transition)
        or (lease.original is not original)
        or (lease.producer is not producer)
        or (lease.module is not module)
        or (lease.status not in ("reserved", "sealed"))
        or (transition.parent is not context)
        or (transition.storage_parent is not storage)
        or (transition.initial is not context.init_parent)
        or (transition.phase is not context.phase)
        or (transition.sim is not context.sim)
        or (transition.p is not context.p)
        or (transition.cells is not context.cells)
        or (transition.handler is not context.handler)
        or (transition.cache is not context.phase.cache)
        or (vars(previous.previous).get("_claim_first_step_ancestor") is not lease.ancestor)
        or (vars(previous.previous).get("_check_first_step_ancestor") is not lease.ancestor_check)
    ) or (
        getattr(context, "terminal_init_descendant", None) is not None
        or context.owner in _TERMINAL_INIT_DESCENDANTS
    ):
        raise ValueError("Original Completion/storage/electrical/first-step ancestry changed")
    return lease


def _advance_lease(context):
    terminal = getattr(context, "terminal_init_descendant", None)
    if terminal is not None:
        if (
            getattr(context, "first_step_descendant", None) is not None
            or getattr(context, "short_init_descendant", None) is not None
            or _TERMINAL_INIT_DESCENDANTS.get(context.owner) is not terminal
        ):
            raise ValueError("Mutually exclusive actual natural terminal ancestry required")
        return terminal
    short = getattr(context, "short_init_descendant", None)
    if short is not None:
        if (
            getattr(context, "first_step_descendant", None) is not None
            or _SHORT_INIT_DESCENDANTS.get(context.owner) is not short
        ):
            raise ValueError("Mutually exclusive actual short-history ancestry required")
        return short
    return context.first_step_descendant


def _first_step_values(context, *, stable):
    lease = _advance_lease(context)
    fields = lease.fields if stable else lease.full_fields
    for (_, actual), holder, names, target in zip(
        lease.objects, lease.holders, lease.names, fields, strict=True
    ):
        if vars(actual) is not holder:
            raise ValueError("Original first-step ancestor holder changed")
        ignored = (
            next((allowed for owner, allowed in lease.permissions if owner is actual), frozenset())
            if stable
            else frozenset()
        )
        if stable and actual is context.sim:
            ignored = ignored | lease.original.allowed | lease.original.storage_allowed
        if tuple(name for name in holder if name not in ignored) != tuple(
            name for name in names if name not in ignored
        ):
            raise ValueError("First-step changed an unowned ancestor field roster")
        target.clear()
        target.update((name, holder[name]) for name in names if name not in ignored)
    projector = previous.previous._projector(context.init_parent)
    projector.objects = [*projector.objects, *lease.objects]
    project = previous.previous.core._LITERAL._project
    values = tuple(fields)
    if getattr(context, "molecule_session", None) is not None:
        values = context.molecule.project_state(context.molecule_session, values)
    return _scope(context).snapshot(project(projector, values))


def _first_step_graph(context, *, stable):
    _first_step_values(context, stable=stable)
    lease = _advance_lease(context)
    view = lease.view if stable else lease.full_view
    return _scope(context).graph(view, view, lease.tape)


def _first_step_runtime_permissions(lease):
    """Authenticate extensions from the retained actual molecular claimant.

    The consumer's complete source contract is checked separately below. A
    supplied or equal-copied permission tuple cannot become runtime authority.
    This reads the current runtime epoch, never a stale pre-step value snapshot.
    """
    parent, step = lease.parent, lease.child
    enabled = getattr(getattr(parent, "request", None), "native_molecules", False)
    session = getattr(parent, "molecule_session", None)
    if enabled is not True:
        rows = getattr(step, "molecule_permissions", ())
        if (
            session is not None
            or getattr(step, "molecule_claim", None) is not None
            or type(rows) is not tuple
            or rows
        ):
            raise ValueError("Molecular permissions require the actual enabled parent")
        return ()
    source = _molecule_api()
    claim = getattr(lease, "molecule_claim", None)
    if (
        session is None
        or parent.molecule is not source
        or step.molecule is not source
        or claim is None
        or step.molecule_claim is not claim
    ):
        raise ValueError("Original molecular session/child/runtime claim association changed")
    runtime = getattr(lease, "runtime_api", None)
    if runtime is None:
        runtime = source
        if getattr(step, "short_runtime", None) is not None:
            raise ValueError("A first-step runtime cannot adopt a continuous claimant")
    else:
        terminal = _TERMINAL_INIT_DESCENDANTS.get(getattr(parent, "owner", None))
        if terminal is lease and getattr(parent, "terminal_init_descendant", None) is lease:
            canonical, retained = _molecule_terminal_api(), step.terminal_runtime
        else:
            canonical, retained = _molecule_short_api(), step.short_runtime
        if runtime is not canonical or retained is not runtime:
            raise ValueError("Actual canonical current-runtime provider required")
        if (
            runtime.session_of(claim, child=step) is not session
            or runtime.session_provider(claim, child=step) is not source
        ):
            raise ValueError("Original continuous-runtime session/provider association changed")
    record = step.molecule_record
    if record is None:
        if runtime.validate_runtime_active(claim, child=step) is not claim:
            raise ValueError("Actual active molecular runtime claim changed")
    elif runtime.validate_runtime(claim, child=step) is not record:
        raise ValueError("Actual closed molecular runtime record changed")
    rows = runtime.runtime_permissions(claim)
    if type(rows) is not tuple or rows is not step.molecule_permissions:
        raise ValueError("Original molecular runtime permission tuple association changed")
    return rows


def _first_step_permissions(lease):
    step, module = lease.child, lease.module
    extensions = _first_step_runtime_permissions(lease)
    actual, expected = step.permissions, module._mutation_contract(step)
    if type(actual) is not tuple or type(expected) is not tuple or len(actual) != len(expected):
        raise ValueError("Complete source-derived first-step permission tuple required")
    seen = []
    for (owner, fields), (original, allowed) in zip(actual, expected, strict=True):
        if (
            owner is not original
            or any(owner is prior for prior in seen)
            or not any(owner is obj for _, obj in lease.objects)
            or type(fields) is not frozenset
            or type(allowed) is not frozenset
            or fields != allowed
            or any(type(name) is not str for name in fields)
        ):
            raise ValueError("Actual first-step holder/field source correspondence changed")
        seen.append(owner)
    extension_owners = []
    for owner, fields in extensions:
        selected = [allowed for original, allowed in actual if owner is original]
        if (
            any(owner is original for original in extension_owners)
            or type(fields) is not frozenset
            or any(type(name) is not str for name in fields)
            or len(selected) != 1
            or not fields <= selected[0]
        ):
            raise ValueError("Complete canonical runtime extension is missing from source contract")
        extension_owners.append(owner)
    if not any(owner is lease.parent.sim for owner, _ in actual):
        raise ValueError("Actual first-step Simulator permission is missing")
    return actual


def _claim_first_step_ancestor(context, storage, electrical, transition):
    """Reserve once; immutable whole-state proof precedes permission sealing."""
    module = _storage_api()
    frame = sys._getframe(1)
    with _LOCK:
        if (
            frame.f_code is not module._claim_first_step_ancestor.__code__
            or frame.f_globals is not vars(module)
            or frame.f_locals.get("context") is not storage
            or (frame.f_locals.get("electrical") is not electrical)
            or (frame.f_locals.get("transition") is not transition)
        ):
            raise CompletionRejected(
                "Actual first-step ancestor issuer required", stage="first_step_entry"
            )
        if (
            context.owner in _FIRST_STEP_DESCENDANTS
            or hasattr(context, "first_step_descendant")
            or context.owner in _SHORT_INIT_DESCENDANTS
            or hasattr(context, "short_init_descendant")
        ) or (
            context.owner in _TERMINAL_INIT_DESCENDANTS
            or hasattr(context, "terminal_init_descendant")
        ):
            context.invalid = storage.invalid = electrical.invalid = transition.invalid = True
            raise CompletionRejected(
                "First-step ancestor already attempted", stage="first_step_consumed"
            )
        original = _electrical_route(context, storage, electrical)
        producer = module._electrical_api().module
        child, consumer = producer._first_step_route(electrical)
        if (
            child is not transition
            or not transition.active
            or transition.invalid
            or transition.claimed
            or (transition.setup_frame is not None)
            or (transition.loop_frame is not None)
            or (transition.thread != get_ident())
            or (storage.first_step_transition is not transition)
        ):
            raise ValueError("Actual still-unrun first-step reservation required")
        lease = SimpleNamespace(
            parent=context,
            storage=storage,
            electrical=electrical,
            child=transition,
            original=original,
            producer=producer,
            module=consumer,
            status="reserving",
            primary=None,
            permissions=(),
        )
        _FIRST_STEP_DESCENDANTS[context.owner] = context.first_step_descendant = lease
        try:
            objects = list(original.objects)
            for role, obj in (("callback", context.phase.callbacks), ("gap", context.parent.gap)):
                if obj is not None and (not any((value is obj for _, value in objects))):
                    objects.append((role, obj))
            lease.objects = tuple(objects)
            lease.holders = tuple((vars(value) for _, value in lease.objects))
            lease.names = tuple((tuple(holder) for holder in lease.holders))
            lease.fields, lease.full_fields = ([{} for _ in objects] for _ in range(2))
            lease.view = SimpleNamespace(objects=lease.objects, fields=lease.fields)
            lease.full_view = SimpleNamespace(objects=lease.objects, fields=lease.full_fields)
            lease.tape = SimpleNamespace(rng=context.np_rng, events=(), draws=(), locals={})
            lease.before = _first_step_values(context, stable=False)
            lease.before_graph = _first_step_graph(context, stable=False)
            lease.ancestor = vars(previous.previous).get("_claim_first_step_ancestor")
            lease.ancestor_check = vars(previous.previous).get("_check_first_step_ancestor")
            if any(
                (
                    type(fn) is not FunctionType or fn.__globals__ is not vars(previous.previous)
                    for fn in (lease.ancestor, lease.ancestor_check)
                )
            ):
                raise ValueError("Actual retained first-step ancestor hooks unavailable")
            if (
                lease.ancestor(context.init_parent, context, storage, electrical, transition)
                is not context.init_parent
            ):
                raise ValueError("Different retained first-step ancestor")
            lease.status = "reserved"
            if context.request.native_molecules:
                lease.molecule_claim = context.molecule.bind_first_step(
                    context.molecule_session,
                    completion=context,
                    storage=storage,
                    electrical=electrical,
                    step=transition,
                )
            return context
        except BaseException as error:
            lease.status, lease.primary = ("failed", error)
            context.invalid = storage.invalid = electrical.invalid = transition.invalid = True
            raise


def _check_first_step_ancestor(context, storage, electrical, transition):
    """Seal only before setup, then audit the actual factored fourth epoch."""
    lease = _first_step_route(context, storage, electrical, transition)
    return _check_advance_ancestor(context, storage, electrical, transition, lease)


def _check_advance_ancestor(context, storage, electrical, transition, lease):
    if lease.module._check_ancestor_metadata(transition) is not electrical:
        raise ValueError("Different actual first-step metadata owner")
    permissions = _first_step_permissions(lease)
    if lease.status == "reserved":
        if (
            transition.setup_frame is not None
            or transition.loop_frame is not None
            or transition.work
        ):
            raise ValueError("First-step ancestor permissions were not sealed before source entry")
        if _first_step_values(context, stable=False).identity != lease.before.identity:
            raise ValueError("Original state changed before first-step permission publication")
        graph = _first_step_graph(context, stable=False)
        _same_refs(graph[0], lease.before_graph[0])
        if graph[1] != lease.before_graph[1]:
            raise ValueError("Original aliases changed before first-step permission publication")
        lease.permissions = permissions
        lease.values, lease.graph = (
            _first_step_values(context, stable=True),
            _first_step_graph(context, stable=True),
        )
        lease.status = "sealed"
    elif len(permissions) != len(lease.permissions) or any(
        owner is not actual or fields != allowed
        for (owner, fields), (actual, allowed) in zip(permissions, lease.permissions, strict=True)
    ):
        raise ValueError("Sealed first-step permission ownership changed")
    _storage_metadata(context)
    if (
        lease.ancestor_check(context.init_parent, context, storage, electrical, transition)
        is not context.init_parent
    ):
        raise ValueError("Different retained checked first-step ancestor")
    if _first_step_values(context, stable=True).identity != lease.values.identity:
        raise ValueError("First-step changed an unowned Completion value")
    graph = _first_step_graph(context, stable=True)
    _same_refs(graph[0], lease.graph[0])
    if graph[1] != lease.graph[1]:
        raise ValueError("First-step changed an unowned Completion alias/layout")
    return context


def _molecule_short_api():
    if not _pin(SHORT_RUNTIME_SHA256) or not _pin(SHORT_RUNTIME_REVIEW_SHA256):
        raise CompletionRejected(
            "Reviewed short-history runtime remains held", stage="short_init_held"
        )
    module = sys.modules.get(SHORT_RUNTIME_MODULE)
    path = Path(__file__).with_name("betse_native_init_molecule_short_runtime.py")
    if (
        type(module) is not ModuleType
        or path.is_symlink()
        or Path(module.__file__).resolve() != path.resolve()
        or hashlib.sha256(path.read_bytes()).hexdigest() != SHORT_RUNTIME_SHA256
    ):
        raise CompletionRejected(
            "Exact actual short-history runtime required", stage="short_init_producer"
        )
    names = (
        "bind_short_history",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "observe_runtime",
        "begin_iteration",
        "finish_iteration",
        "finish_runtime",
        "validate_iteration",
        "validate_runtime_active",
        "validate_runtime",
        "session_of",
        "session_provider",
        "runtime_failed_context",
    )
    previous.previous.previous._ready()._source_interface(module, path.read_bytes(), path, names)
    for name in names:
        fn = vars(module).get(name)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(module):
            raise ValueError("Actual short-history definition export required: " + name)
    return module


def _short_init_route(context, storage, electrical, transition):
    original = _electrical_route(context, storage, electrical)
    producer = original.module._electrical_api().module
    route = vars(producer).get("_short_init_route")
    path = Path(producer.__file__)
    previous.previous.previous._ready()._source_interface(
        producer, path.read_bytes(), path, ("_short_init_route",)
    )
    child, module = route(electrical)
    lease = _SHORT_INIT_DESCENDANTS.get(context.owner)
    if (
        lease is None
        or child is not transition
        or getattr(context, "short_init_descendant", None) is not lease
        or (getattr(context, "first_step_descendant", None) is not None)
        or (lease.parent is not context)
        or (lease.storage is not storage)
        or (lease.electrical is not electrical)
        or (lease.child is not transition)
        or (lease.original is not original)
        or (lease.producer is not producer)
        or (lease.module is not module)
        or (lease.status not in ("reserved", "sealed"))
        or (transition.parent is not context)
        or (transition.storage_parent is not storage)
        or (transition.electrical_parent is not electrical)
        or (transition.initial is not context.init_parent)
        or (transition.phase is not context.phase)
        or (transition.sim is not context.sim)
        or (transition.p is not context.p)
        or (transition.cells is not context.cells)
        or (transition.handler is not context.handler)
        or (transition.cache is not context.phase.cache)
        or (type(transition.request.iterations) is not int)
        or (transition.request.iterations != lease.iterations)
        or (vars(previous.previous).get("_claim_short_init_ancestor") is not lease.ancestor)
        or (vars(previous.previous).get("_check_short_init_ancestor") is not lease.ancestor_check)
    ) or (
        getattr(context, "terminal_init_descendant", None) is not None
        or context.owner in _TERMINAL_INIT_DESCENDANTS
    ):
        raise ValueError("Actual original continuous INIT ancestry changed")
    return lease


def _claim_short_init_ancestor(context, storage, electrical, transition):
    """Fresh N-bound ownership before source; never recycle a first-step lease."""
    runtime = _molecule_short_api()
    module, frame = (_storage_api(), sys._getframe(1))
    path = Path(module.__file__)
    previous.previous.previous._ready()._source_interface(
        module,
        path.read_bytes(),
        path,
        ("_claim_short_init_ancestor", "_check_short_init_ancestor"),
    )
    function = vars(module).get("_claim_short_init_ancestor")
    with _LOCK:
        if (
            type(function) is not FunctionType
            or frame.f_code is not function.__code__
            or frame.f_globals is not vars(module)
            or (frame.f_locals.get("context") is not storage)
            or (frame.f_locals.get("electrical") is not electrical)
            or (frame.f_locals.get("transition") is not transition)
        ):
            raise CompletionRejected(
                "Actual short-history ancestor issuer required", stage="short_init_entry"
            )
        if (
            context.owner in _FIRST_STEP_DESCENDANTS
            or context.owner in _SHORT_INIT_DESCENDANTS
            or hasattr(context, "first_step_descendant")
            or hasattr(context, "short_init_descendant")
        ) or (
            context.owner in _TERMINAL_INIT_DESCENDANTS
            or hasattr(context, "terminal_init_descendant")
        ):
            context.invalid = storage.invalid = electrical.invalid = transition.invalid = True
            raise CompletionRejected("INIT advance already attempted", stage="short_init_consumed")
        original = _electrical_route(context, storage, electrical)
        producer = module._electrical_api().module
        child, consumer = producer._short_init_route(electrical)
        count = transition.request.iterations
        if (
            child is not transition
            or not transition.active
            or transition.invalid
            or transition.claimed
            or (transition.setup_frame is not None)
            or (transition.loop_frame is not None)
            or (transition.thread != get_ident())
            or (type(count) is not int)
            or (not 1 <= count <= runtime.MAX_ITERATIONS)
        ):
            raise ValueError("Actual still-unrun bounded continuous INIT child required")
        lease = SimpleNamespace(
            parent=context,
            storage=storage,
            electrical=electrical,
            child=transition,
            original=original,
            producer=producer,
            module=consumer,
            iterations=count,
            runtime_api=runtime,
            status="reserving",
            primary=None,
            permissions=(),
        )
        _SHORT_INIT_DESCENDANTS[context.owner] = context.short_init_descendant = lease
        try:
            objects = list(original.objects)
            for role, obj in (("callback", context.phase.callbacks), ("gap", context.parent.gap)):
                if obj is not None and (not any((value is obj for _, value in objects))):
                    objects.append((role, obj))
            lease.objects = tuple(objects)
            lease.holders = tuple((vars(value) for _, value in lease.objects))
            lease.names = tuple((tuple(holder) for holder in lease.holders))
            lease.fields, lease.full_fields = ([{} for _ in objects] for _ in range(2))
            lease.view = SimpleNamespace(objects=lease.objects, fields=lease.fields)
            lease.full_view = SimpleNamespace(objects=lease.objects, fields=lease.full_fields)
            lease.tape = SimpleNamespace(rng=context.np_rng, events=(), draws=(), locals={})
            lease.before = _first_step_values(context, stable=False)
            lease.before_graph = _first_step_graph(context, stable=False)
            lease.ancestor = vars(previous.previous).get("_claim_short_init_ancestor")
            lease.ancestor_check = vars(previous.previous).get("_check_short_init_ancestor")
            if any(
                (
                    type(fn) is not FunctionType or fn.__globals__ is not vars(previous.previous)
                    for fn in (lease.ancestor, lease.ancestor_check)
                )
            ):
                raise ValueError("Actual retained short-history ancestor hooks unavailable")
            if (
                lease.ancestor(context.init_parent, context, storage, electrical, transition)
                is not context.init_parent
            ):
                raise ValueError("Different actual retained short-history ancestor")
            lease.status = "reserved"
            if context.request.native_molecules is not True:
                raise ValueError(
                    "This short-history molecular route requires its actual enabled session"
                )
            lease.molecule_claim = runtime.bind_short_history(
                context.molecule_session,
                completion=context,
                storage=storage,
                electrical=electrical,
                child=transition,
                iterations=count,
            )
            return context
        except BaseException as error:
            lease.status, lease.primary = ("failed", error)
            context.invalid = storage.invalid = electrical.invalid = transition.invalid = True
            raise


def _check_short_init_ancestor(context, storage, electrical, transition):
    lease = _short_init_route(context, storage, electrical, transition)
    return _check_advance_ancestor(context, storage, electrical, transition, lease)


# Separate held natural-terminal ancestry; no selected-history reuse.


def _molecule_terminal_api():
    if not _pin(TERMINAL_RUNTIME_SHA256) or not _pin(TERMINAL_RUNTIME_REVIEW_SHA256):
        raise CompletionRejected(
            "Reviewed natural-terminal runtime remains held", stage="terminal_init_held"
        )
    module = sys.modules.get(TERMINAL_RUNTIME_MODULE)
    path = Path(__file__).with_name("betse_native_init_terminal_molecules.py")
    if (
        type(module) is not ModuleType
        or path.is_symlink()
        or Path(module.__file__).resolve() != path.resolve()
        or (hashlib.sha256(path.read_bytes()).hexdigest() != TERMINAL_RUNTIME_SHA256)
    ):
        raise CompletionRejected(
            "Exact actual natural-terminal runtime required", stage="terminal_init_producer"
        )
    names = (
        "bind_terminal",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "observe_runtime",
        "begin_iteration",
        "finish_iteration",
        "finish_runtime",
        "validate_iteration",
        "validate_runtime_active",
        "validate_runtime",
        "session_of",
        "session_provider",
        "runtime_failed_context",
    )
    previous.previous.previous._ready()._source_interface(module, path.read_bytes(), path, names)
    for name in names:
        fn = vars(module).get(name)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(module):
            raise ValueError("Actual natural-terminal definition export required: " + name)
    return module


def _terminal_init_route(context, storage, electrical, transition):
    original = _electrical_route(context, storage, electrical)
    producer = original.module._electrical_api().module
    route = vars(producer).get("_terminal_init_route")
    path = Path(producer.__file__)
    previous.previous.previous._ready()._source_interface(
        producer, path.read_bytes(), path, ("_terminal_init_route",)
    )
    child, module = route(electrical)
    lease = _TERMINAL_INIT_DESCENDANTS.get(context.owner)
    if (
        lease is None
        or child is not transition
        or getattr(context, "terminal_init_descendant", None) is not lease
        or (getattr(context, "first_step_descendant", None) is not None)
        or (lease.parent is not context)
        or (lease.storage is not storage)
        or (lease.electrical is not electrical)
        or (lease.child is not transition)
        or (lease.original is not original)
        or (lease.producer is not producer)
        or (lease.module is not module)
        or (lease.status not in ("reserved", "sealed"))
        or (transition.parent is not context)
        or (transition.storage_parent is not storage)
        or (transition.electrical_parent is not electrical)
        or (transition.initial is not context.init_parent)
        or (transition.phase is not context.phase)
        or (transition.sim is not context.sim)
        or (transition.p is not context.p)
        or (transition.cells is not context.cells)
        or (transition.handler is not context.handler)
        or (transition.cache is not context.phase.cache)
        or (type(transition.request.iterations) is not int)
        or (transition.request.iterations != lease.iterations)
        or (vars(previous.previous).get("_claim_terminal_init_ancestor") is not lease.ancestor)
        or (
            vars(previous.previous).get("_check_terminal_init_ancestor") is not lease.ancestor_check
        )
    ) or (
        getattr(context, "short_init_descendant", None) is not None
        or context.owner in _SHORT_INIT_DESCENDANTS
        or context.owner in _FIRST_STEP_DESCENDANTS
        or (type(transition.request.maximum) is not int)
        or (transition.request.maximum != lease.maximum)
        or (
            transition.request.iterations
            != module._configured_count(context.p.init_tsteps, lease.maximum)
        )
    ):
        raise ValueError("Actual original continuous INIT ancestry changed")
    return lease


def _claim_terminal_init_ancestor(context, storage, electrical, transition):
    """Fresh N-bound ownership before source; never recycle a first-step lease."""
    runtime = _molecule_terminal_api()
    module, frame = (_storage_api(), sys._getframe(1))
    path = Path(module.__file__)
    previous.previous.previous._ready()._source_interface(
        module,
        path.read_bytes(),
        path,
        ("_claim_terminal_init_ancestor", "_check_terminal_init_ancestor"),
    )
    function = vars(module).get("_claim_terminal_init_ancestor")
    with _LOCK:
        if (
            type(function) is not FunctionType
            or frame.f_code is not function.__code__
            or frame.f_globals is not vars(module)
            or (frame.f_locals.get("context") is not storage)
            or (frame.f_locals.get("electrical") is not electrical)
            or (frame.f_locals.get("transition") is not transition)
        ):
            raise CompletionRejected(
                "Actual natural-terminal ancestor issuer required", stage="terminal_init_entry"
            )
        if (
            context.owner in _FIRST_STEP_DESCENDANTS
            or context.owner in _TERMINAL_INIT_DESCENDANTS
            or hasattr(context, "first_step_descendant")
            or hasattr(context, "terminal_init_descendant")
        ) or (
            context.owner in _SHORT_INIT_DESCENDANTS or hasattr(context, "short_init_descendant")
        ):
            context.invalid = storage.invalid = electrical.invalid = transition.invalid = True
            raise CompletionRejected(
                "INIT advance already attempted", stage="terminal_init_consumed"
            )
        original = _electrical_route(context, storage, electrical)
        producer = module._electrical_api().module
        child, consumer = producer._terminal_init_route(electrical)
        count = consumer._configured_count(context.p.init_tsteps, transition.request.maximum)
        if (
            child is not transition
            or not transition.active
            or transition.invalid
            or transition.claimed
            or (transition.setup_frame is not None)
            or (transition.loop_frame is not None)
            or (transition.thread != get_ident())
            or (type(count) is not int)
            or (not 1 <= count <= runtime.MAX_ITERATIONS)
        ) or transition.request.iterations != count:
            raise ValueError("Actual still-unrun bounded continuous INIT child required")
        lease = SimpleNamespace(
            parent=context,
            storage=storage,
            electrical=electrical,
            child=transition,
            original=original,
            producer=producer,
            module=consumer,
            iterations=count,
            runtime_api=runtime,
            status="reserving",
            primary=None,
            permissions=(),
            maximum=transition.request.maximum,
        )
        _TERMINAL_INIT_DESCENDANTS[context.owner] = context.terminal_init_descendant = lease
        try:
            objects = list(original.objects)
            for role, obj in (("callback", context.phase.callbacks), ("gap", context.parent.gap)):
                if obj is not None and (not any((value is obj for _, value in objects))):
                    objects.append((role, obj))
            lease.objects = tuple(objects)
            lease.holders = tuple((vars(value) for _, value in lease.objects))
            lease.names = tuple((tuple(holder) for holder in lease.holders))
            lease.fields, lease.full_fields = ([{} for _ in objects] for _ in range(2))
            lease.view = SimpleNamespace(objects=lease.objects, fields=lease.fields)
            lease.full_view = SimpleNamespace(objects=lease.objects, fields=lease.full_fields)
            lease.tape = SimpleNamespace(rng=context.np_rng, events=(), draws=(), locals={})
            lease.before = _first_step_values(context, stable=False)
            lease.before_graph = _first_step_graph(context, stable=False)
            lease.ancestor = vars(previous.previous).get("_claim_terminal_init_ancestor")
            lease.ancestor_check = vars(previous.previous).get("_check_terminal_init_ancestor")
            if any(
                (
                    type(fn) is not FunctionType or fn.__globals__ is not vars(previous.previous)
                    for fn in (lease.ancestor, lease.ancestor_check)
                )
            ):
                raise ValueError("Actual retained natural-terminal ancestor hooks unavailable")
            if (
                lease.ancestor(context.init_parent, context, storage, electrical, transition)
                is not context.init_parent
            ):
                raise ValueError("Different actual retained natural-terminal ancestor")
            lease.status = "reserved"
            if context.request.native_molecules is not True:
                raise ValueError(
                    "This natural-terminal molecular route requires its actual enabled session"
                )
            lease.molecule_claim = runtime.bind_terminal(
                context.molecule_session,
                completion=context,
                storage=storage,
                electrical=electrical,
                child=transition,
                maximum=transition.request.maximum,
            )
            return context
        except BaseException as error:
            lease.status, lease.primary = ("failed", error)
            context.invalid = storage.invalid = electrical.invalid = transition.invalid = True
            raise


def _check_terminal_init_ancestor(context, storage, electrical, transition):
    lease = _terminal_init_route(context, storage, electrical, transition)
    return _check_advance_ancestor(context, storage, electrical, transition, lease)
