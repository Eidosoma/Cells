"""Blocked source/observer controls; no supplied token is a real phase owner."""

import ast
import builtins
import os
import sys
import time
from contextlib import contextmanager, nullcontext
from enum import Enum
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_init_dynamics_prelude as dynamics
from cells.processes import betse_native_init_retained_world as stage
from cells.processes import betse_native_parameter_seed_init_transition as key_source
from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import betse_native_init_retained_world_software as software

_RAW_GUARDS = []


def clone(fn, **values):
    value = FunctionType(
        fn.__code__, dict(fn.__globals__, **values), fn.__name__, fn.__defaults__, fn.__closure__
    )
    value.__kwdefaults__ = fn.__kwdefaults__
    return value


def test_completion_default_without_owned_successor_keeps_original_epoch_checks():
    assert stage._completion_initial_lease(NS()) is None


def test_completion_ancestor_claim_refuses_unbound_real_provider_before_foreign_read():
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("No foreign owner inspection before provider adoption")

    with pytest.raises(stage.InitRejected) as caught:
        stage._claim_completion_ancestor(Foreign(), Foreign(), Foreign())
    assert caught.value.stage == "dynamics_held"


@pytest.mark.parametrize("mutation", ("equal_copy", "shape", "writeable"))
def test_completion_cell_layout_metadata_retains_actual_array_and_base(mutation):
    # Array-layout helper only, not an issued completion or a permitted draw.
    array = np.asarray([1, 1, 1], dtype=np.int64)
    parent = NS(cells=NS(cell_i=array))
    lease = NS(
        cell_i=array,
        cell_type=type(array),
        cell_base=array.base,
        cell_layout=(
            array.dtype.str,
            tuple(array.shape),
            tuple(array.strides),
            array.ctypes.data,
            bool(array.flags.writeable),
            bool(array.flags.c_contiguous),
            bool(array.flags.f_contiguous),
        ),
    )
    stage._completion_cell_layout(parent, lease)
    if mutation == "equal_copy":
        parent.cells.cell_i = array.copy()
        assert np.array_equal(parent.cells.cell_i, array)
    elif mutation == "shape":
        array.shape = (1, 3)
    else:
        array.flags.writeable = False
    with pytest.raises(ValueError, match="identity/base/layout"):
        stage._completion_cell_layout(parent, lease)


def test_completion_ancestor_metadata_does_not_rearm_or_replace_retained_instances():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    names = (
        "_claim_completion_ancestor",
        "_completion_projection",
        "_completion_runtime",
        "_completion_wrapper_guard",
        "_completion_dispatch_guard",
    )
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(nodes) == len(names)
    for method in nodes:
        for node in ast.walk(method):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("exec", "eval", "setattr")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    assert not (isinstance(target, ast.Attribute) and target.attr == "__class__")


def test_completion_historical_alias_projection_keeps_true_views_not_equal_copies(monkeypatch):
    root = np.asarray([0, 1, 2, 3], dtype=np.int64)
    view, equal = root[:2], root.copy()
    parent = NS(cells=NS(cell_i=root))
    fields = [
        {
            "cell_i": root,
            "old_All_target": root,
            "old_partial_target": view,
            "unrelated_equal": equal,
        }
    ]
    monkeypatch.setattr(stage, "_seed_projection", lambda actual: NS(fields=fields))
    monkeypatch.setattr(stage, "_dynamics_projection", lambda actual: NS(fields=[]))
    aliases = stage._completion_cell_aliases(parent)
    assert any(value is root for value in aliases)
    assert any(value is view for value in aliases)
    assert all(value is not equal for value in aliases)


def test_completion_live_route_is_source_authenticated_before_invocation():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_completion_runtime"
    )
    text = ast.unparse(node)
    assert text.index("_dynamics_binding(raw)") < text.index("_source_interface(")
    assert text.index("_source_interface(") < text.index("route(prelude)")
    assert "('_completion_route',)" in text


def test_completion_caught_duplicate_reservation_stays_poisoned_before_source():
    parent = NS(entry_error=None, invalid=False, stage="metadata", request=None, trial=None)
    successor = NS(invalid=False)
    with pytest.raises(stage.InitRejected) as caught:
        stage._reject_completion_reservation(parent, successor)
    assert parent.invalid and successor.invalid
    assert caught.value is parent.entry_error
    with pytest.raises(stage.InitRejected) as sticky:
        stage._guard(parent)
    assert sticky.value is caught.value


def test_storage_default_without_successor_preserves_original_completion_epoch():
    assert stage._storage_initial_lease(NS()) is None


def test_storage_ancestor_refuses_unbound_provider_before_foreign_owner_read():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No supplied ancestor inspection before producer adoption")

    with pytest.raises(stage.InitRejected) as caught:
        stage._claim_storage_ancestor(Foreign(), Foreign(), Foreign())
    assert caught.value.stage == "dynamics_held"


@pytest.mark.parametrize("mutation", ("allowed_storage", "foreign_sim", "foreign_handler", "cells"))
def test_storage_factored_values_keep_original_nonstorage_bits_and_aliases(mutation, monkeypatch):
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    # Codec-only objects, not owners or entries in any issuance registry.
    array = np.asarray([0, 1], dtype=np.int64)
    sim = NS(fluxes_mem=np.asarray([-0.0, 2.0]), vm_time=[1], retained=-0.0)
    handler, cells = NS(retained=3), NS(cell_i=array, retained=4)
    objects = (("Simulator", sim), ("TissueHandler", handler), ("Cells", cells))
    parent = NS(phase=NS(sim=sim, dyna=handler), cells=cells, parent=NS(world=object()))
    lease = NS(
        objects=objects,
        holders=tuple(vars(actual) for _, actual in objects),
        names=tuple(tuple(vars(actual)) for _, actual in objects),
        fields=[{} for _ in objects],
        sim_fields=frozenset(("fluxes_mem", "vm_time")),
        handler_fields=frozenset(),
        cell_aliases=(array,),
    )
    lease.view = NS(objects=objects, fields=lease.fields)
    tape, scope = NS(rng=object(), events=(), draws=(), locals={}), observation.Scope()
    monkeypatch.setattr(stage, "_projector", lambda actual: NS(objects=list(objects)))
    monkeypatch.setattr(stage.core.previous, "_scope", lambda ignored: scope)
    before = stage._storage_initial_values(parent, lease)
    graph = scope.graph(lease.view, lease.view, tape)
    old_flux, old_history = sim.fluxes_mem, sim.vm_time
    sim.fluxes_mem, sim.vm_time = np.asarray([0.0, 0.0]), []
    if mutation == "foreign_sim":
        sim.retained = 0.0  # Equal arithmetic value; different typed bits.
    elif mutation == "foreign_handler":
        handler.retained = 4
    elif mutation == "cells":
        cells.retained = 5
    after = stage._storage_initial_values(parent, lease)
    current = scope.graph(lease.view, lease.view, tape)
    assert old_flux is not sim.fluxes_mem and old_history is not sim.vm_time
    assert cells.cell_i is array
    if mutation == "allowed_storage":
        assert before.identity == after.identity
        assert len(graph[0]) == len(current[0])
        assert all(a is b for a, b in zip(graph[0], current[0], strict=True))
        assert graph[1] == current[1]
    else:
        assert before.identity != after.identity


def test_storage_observation_does_not_weaken_other_object_field_rosters():
    sim, foreign = NS(time=[]), NS(time=[])
    parent = NS(phase=NS(sim=sim, dyna=NS()))
    lease = NS(
        objects=(("Simulator", sim), ("Other", foreign)),
        holders=(vars(sim), vars(foreign)),
        names=(("time",), ("time",)),
        fields=[{}, {}],
        sim_fields=frozenset(("time", "new_history")),
        handler_fields=frozenset(),
        view=object(),
    )
    sim.new_history = []
    assert stage._completion_projection(parent, lease) is lease.view
    foreign.new_history = []
    with pytest.raises(ValueError, match="unowned original field roster"):
        stage._completion_projection(parent, lease)


def test_storage_dispatch_uses_original_invoke_frame_without_replacing_methods():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("_storage_wrapper_guard", "_storage_dispatch_guard", "_claim_storage_ancestor"):
        source = ast.unparse(functions[name])
        assert "__class__ =" not in source
        assert "setattr(parent.phase.sim" not in source
    invoke = ast.unparse(functions["_invoke"])
    assert invoke.index("_storage_runtime(context)") < invoke.index("_completion_runtime(context)")
    assert "frame.f_code is not _invoke.__code__" in ast.unparse(
        functions["_storage_dispatch_guard"]
    )


@pytest.mark.parametrize("entry", ("guard", "invoke"))
@pytest.mark.parametrize("origin", ("completion", "storage", "storage_claim"))
def test_storage_retained_entry_preserves_first_rejection_before_any_later_delegate(entry, origin):
    primary, cause = ValueError("original entry rejection"), OSError("original cause")
    primary.__cause__ = cause
    storage = NS(entry_error=primary if origin == "storage" else None)
    completion = NS(
        entry_error=primary if origin == "completion" else None,
        storage_error=primary if origin == "storage_claim" else None,
        storage_transition=storage,
    )
    parent = NS(
        entry_error=None,
        dynamics_transition=NS(entry_error=None, completion_transition=completion),
        dynamics_error=RuntimeError("secondary stale/capture error"),
    )
    calls = []

    def delegate(*args, **kwargs):
        calls.append((args, kwargs))

    with pytest.raises(ValueError) as caught:
        if entry == "guard":
            stage._guard(parent)
        else:
            stage._invoke(parent, "Simulator.clear_storage", delegate, object())
    assert caught.value is primary and caught.value.__cause__ is cause
    assert calls == []


def test_electrical_default_keeps_original_unforwarded_ancestry():
    assert stage._electrical_initial_lease(NS()) is None


def test_electrical_ancestor_refuses_unavailable_authority_before_foreign_parent_read():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No supplied electrical/phase/parent data can grant a claim")

    with pytest.raises(stage.InitRejected) as caught:
        stage._claim_electrical_ancestor(Foreign(), Foreign(), Foreign(), Foreign())
    assert caught.value.stage == "dynamics_held"


@pytest.mark.parametrize("entry", ("guard", "invoke"))
def test_electrical_retained_rejection_precedes_later_registry_or_capture_error(entry):
    primary, cause = ValueError("electrical entry rejected"), RuntimeError("original cause")
    primary.__cause__ = cause
    electrical = NS(entry_error=primary)
    storage = NS(entry_error=None, electrical_transition=electrical, electrical_error=None)
    completion = NS(entry_error=None, storage_transition=storage, storage_error=None)
    parent = NS(
        entry_error=None,
        dynamics_transition=NS(entry_error=None, completion_transition=completion),
        dynamics_error=OSError("later observation failure"),
    )
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))

    with pytest.raises(ValueError) as caught:
        if entry == "guard":
            stage._guard(parent)
        else:
            stage._invoke(parent, "Simulator.update_V", forbidden, object())
    assert caught.value is primary and caught.value.__cause__ is cause
    assert calls == []


def test_electrical_route_replaced_during_proof_never_invokes_unproved_capture(tmp_path):
    module = ModuleType("metadata_route_not_an_owner")
    module.__file__ = str(tmp_path / "route-source.py")
    stage.Path(module.__file__).write_text("# metadata source; no executable owner\n")
    calls = []

    def template(value):
        value.calls.append("unproved route called")

    captured = FunctionType(template.__code__, vars(module), "_electrical_route")
    proved = FunctionType(template.__code__, vars(module), "_electrical_route")
    module._electrical_route = captured
    storage = NS(electrical_transition=object(), calls=calls)

    def proof(actual, raw, path, names):
        assert actual is module and names == ("_electrical_route",)
        assert raw.startswith(b"# metadata")
        module._electrical_route = proved

    function = clone(
        stage._electrical_runtime,
        _storage_runtime=lambda parent: (storage, module, object(), object()),
        previous=NS(_ready=lambda: NS(_source_interface=proof)),
    )
    with pytest.raises(ValueError, match="changed before invocation"):
        function(object())
    assert calls == [] and module._electrical_route is proved


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit blocked-software release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    scope = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    control = FunctionType(guards._blockade.__wrapped__.__code__, scope)
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("numerical_or_RNG")
        raise AssertionError("Actual numerical/RNG source entry held")

    try:
        with contextmanager(control)(request, tmp_path), monkeypatch.context() as patch:
            for name in ("pinv", "inv", "svd", "solve", "lstsq"):
                patch.setattr(np.linalg, name, forbidden)
            for name in (
                "RandomState",
                "default_rng",
                "seed",
                "set_state",
                "rand",
                "randn",
                "normal",
                "uniform",
                "shuffle",
            ):
                patch.setattr(np.random, name, forbidden)
            try:
                yield
            finally:
                software.snapshot.write_json(
                    tmp_path / "operator-RNG-blocked.json", dict(attempted=attempts)
                )
            assert attempts == []
    finally:
        if scope["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(scope["_BLOCKADE_FAILURES"])


def test_full_source_boundary_retains_original_cells_option_and_new_simulator_order(tmp_path):
    plan = stage.source_plan()
    literal = plan["literal"]
    assert len(software.OWNED) == 4
    assert literal["original_constructor_arguments"] == ("kind", "cells", "p", "callbacks")
    assert literal["original_constructor_keeps_non_None_cells"] is True
    assert literal["original_constructor_omits_sim_and_creates_fresh_simulator"] is True
    assert plan["parameter_stores"] == ("_run_sim", "dt", "resample", "total_time", "t_resample")
    assert plan["source_stages"] == ("phase_constructor", "init_core")
    assert plan["key_source"] is plan["key_review"] is plan["parent_source"] is None
    assert plan["native_execution_released"] is False
    software.snapshot.write_json(tmp_path / "source-boundary.json", plan)


@pytest.mark.parametrize("entry", ["request", "prepare"])
def test_unavailable_real_key_and_parent_hook_refuse_before_any_foreign_owner_read(entry):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("No foreign owner read before actual producer adoption")

    with pytest.raises(stage.InitRejected) as caught:
        if entry == "request":
            stage.from_seed(Foreign(), law_id=stage.LAW_ID)
        else:
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "unbound_contract"


@pytest.mark.parametrize("key", tuple(stage.source.SITES))
def test_original_method_code_extraction_evaluates_no_native_module_class_or_body(key, tmp_path):
    selected = stage.source.code(key)
    assert type(selected) is CodeType
    path, owner, name = stage.source.SITES[key]
    assert selected.co_filename == str(stage.source.NATIVE / path) and selected.co_name == name
    if key == "cache_vector":
        assert selected.co_freevars == ("__class__",)
    software.snapshot.write_json(
        tmp_path / "unexecuted-CodeType.json",
        dict(
            name=key,
            owner=owner,
            filename=selected.co_filename,
            names=selected.co_names,
            freevars=selected.co_freevars,
            executed=False,
        ),
    )


def _ordering():
    """Abstract controller tokens, never from_seed/prepare or an issued claim/phase."""
    log, state = [], NS(active=False, closed=False)
    p, cells, callback, original_claim, original_owner = (object() for _ in range(5))
    faults = NS(where=None, error=ValueError("source or seal"), cause=KeyError("cause"))

    class MetadataClaim:
        parameters = p

    claim = MetadataClaim()

    @contextmanager
    def transition(seed_claim, *, original_owner, law_id, enabled):
        assert seed_claim is original_claim and original_owner is context.seed_owner
        assert law_id == "metadata law" and enabled is True
        log.append("claim_enter")
        state.active = True
        try:
            yield claim
        finally:
            state.active, state.closed = False, True
            log.append("claim_exit")

    def init_core(phase):
        assert state.active and phase is context.phase
        log.append("init_core")
        if faults.where == "core":
            raise faults.error from faults.cause

    context = NS(
        key=NS(seed_to_init=transition, SeedInitClaim=MetadataClaim, SEED_INIT_LAW="metadata law"),
        seed_claim=original_claim,
        seed_owner=original_owner,
        p=p,
        cells=cells,
        callback=callback,
        kind=object(),
        phase=None,
        stage_caches=[],
        stage=None,
        claim=None,
    )

    def make(actual, role, **kwargs):
        assert state.active and actual is context and role == "SimPhase"
        assert tuple(kwargs) == ("kind", "p", "cells", "callbacks") and "sim" not in kwargs
        assert kwargs["cells"] is cells and kwargs["p"] is p and kwargs["callbacks"] is callback
        log.append("constructor")
        if faults.where == "constructor":
            raise faults.error from faults.cause
        actual.phase = NS(sim=NS(init_core=init_core))

    def seal(actual):
        assert state.active and actual is context
        log.append("fallible_seal")
        if faults.where == "seal":
            raise faults.error from faults.cause

    def closed(actual):
        assert state.closed and not state.active and actual is context
        log.append("exact_closed_validation")
        if faults.where == "closed":
            raise faults.error from faults.cause

    coordinate = clone(
        stage._coordinate,
        _make=make,
        _seal=seal,
        _closed=closed,
        _snapshot=lambda actual: "metadata observation",
        _account=lambda actual: nullcontext(),
    )
    return NS(
        context=context, coordinate=coordinate, log=log, state=state, faults=faults, claim=claim
    )


@pytest.mark.parametrize("failure", [None, "constructor", "core", "seal", "closed"])
def test_one_claim_covers_ordered_constructor_core_and_fallible_seal_before_closed_validation(
    failure,
):
    h = _ordering()
    h.faults.where = failure
    issued_before = tuple(stage._ISSUED.items())
    if failure is None:
        h.coordinate(h.context)
        assert h.log == [
            "claim_enter",
            "constructor",
            "init_core",
            "fallible_seal",
            "claim_exit",
            "exact_closed_validation",
        ]
    else:
        with pytest.raises(ValueError) as caught:
            h.coordinate(h.context)
        assert caught.value is h.faults.error and caught.value.__cause__ is h.faults.cause
        assert h.log[0] == "claim_enter" and "claim_exit" in h.log
        if failure != "closed":
            assert "exact_closed_validation" not in h.log
    assert h.context.claim is h.claim and tuple(stage._ISSUED.items()) == issued_before


def _observer_context():
    return NS(
        thread=stage.get_ident(),
        active=True,
        invalid=False,
        inherited=False,
        observing=False,
        primary=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        cleanup_errors=(),
        request=None,
        trial=None,
        stage="isolated_metadata",
        work=[],
        frames={},
        pending={},
        locals={},
        raw_returns=[],
        proxies=[],
        invocations=[],
        allowed_codes=frozenset(),
        methods={},
        required_hooks=(sys.getprofile(), sys.gettrace()),
        restore_setters=(sys.setprofile, sys.settrace),
        restore_getters=(sys.getprofile, sys.gettrace),
        call_tracing=sys.call_tracing,
    )


@pytest.mark.parametrize("layer", ["profile", "trace"])
def test_direct_unclaimed_selected_body_retains_attempt_and_zero_delegate_before_inherited_hooks(
    layer, tmp_path
):
    context = _observer_context()
    counts = []

    def probe():
        counts.append("BODY_MUST_NOT_RUN")

    context.allowed_codes = frozenset((probe.__code__,))
    original = (sys.getprofile(), sys.gettrace())

    def profile(frame, event, arg):
        if layer == "profile" and frame.f_code is probe.__code__ and event == "call":
            stage._admit(context, frame)
        if original[0] is not None:
            original[0](frame, event, arg)

    def trace(frame, event, arg):
        if layer == "trace" and frame.f_code is probe.__code__ and event == "call":
            stage._admit(context, frame)
        return trace

    stage._ACTIVE.append(context)
    try:
        sys.setprofile(profile)
        sys.settrace(trace if layer == "trace" else original[1])
        with pytest.raises(stage.InitRejected) as caught:
            probe()
        assert caught.value is context.entry_error and counts == []
        assert len(context.work) == 1 and context.work[0]["body_started"] is False
    finally:
        sys.setprofile(original[0])
        sys.settrace(original[1])
        assert stage._ACTIVE.pop() is context
        software.snapshot.write_json(
            tmp_path / "raw-metadata-probe.json",
            dict(
                delegate_calls=len(counts),
                attempted_rows=len(context.work),
                native_body=False,
                both_original_hooks_restored=sys.getprofile() is original[0]
                and sys.gettrace() is original[1],
            ),
        )


@pytest.mark.parametrize("primary", [False, True])
def test_raw_source_unwind_capture_failure_does_not_replace_original_error(primary):
    context = _observer_context()
    source_error, cause, capture = (
        ValueError("original"),
        KeyError("cause"),
        OSError("locals archive"),
    )
    source_error.__cause__ = cause
    frame = sys._getframe()
    context.frames[id(frame)] = dict(
        frame=frame, code=frame.f_code, globals=frame.f_globals, returned=False, work={}
    )
    context.pending[id(frame)] = source_error if primary else None

    class BadLocals(dict):
        def __setitem__(self, key, value):
            raise capture

    context.locals = BadLocals()
    observe = clone(stage._observe, _normal_return=lambda actual: False)
    returned = np.asarray([0.0, -0.0])
    observe(context, frame, "return", returned)
    assert context.last_raw_return[1] is returned and context.capture_error is capture
    assert context.primary is (source_error if primary else None)
    assert source_error.__cause__ is cause


@pytest.mark.parametrize("hook", [0, 1])
@pytest.mark.parametrize("after", [False, True])
@pytest.mark.parametrize("primary", [False, True])
def test_partial_observer_setup_attempts_both_restores_and_preserves_source_primary(
    hook, after, primary
):
    context = _observer_context()
    actual = context.required_hooks
    real_setters = context.restore_setters
    capture, source_error = OSError("install failure"), ValueError("source primary")
    context.primary = source_error if primary else None
    calls = []

    def setter(index, value):
        restoring = value is actual[index]
        calls.append((index, restoring))
        if index == hook and not restoring:
            if after:
                real_setters[index](value)
            raise capture
        real_setters[index](value)

    context.restore_setters = (lambda value: setter(0, value), lambda value: setter(1, value))
    account = contextmanager(
        clone(
            stage._account.__wrapped__,
            _inherited=lambda context, prior, frame, event, arg: (
                prior(frame, event, arg) if prior is not None else None
            ),
        )
    )
    try:
        with pytest.raises((ValueError, OSError)) as caught, account(context):
            raise AssertionError("Failed observer setup must not enter source block")
        assert caught.value is (source_error if primary else capture)
        assert (0, True) in calls and (1, True) in calls
    finally:
        real_setters[0](actual[0])
        real_setters[1](actual[1])
    assert sys.getprofile() is actual[0] and sys.gettrace() is actual[1]


@pytest.mark.parametrize("mode", ["retained", "new_request", "checkpoint"])
def test_no_supplied_phase_or_plain_cache_or_serialized_owner_supplies_INIT_authority(mode):
    if mode == "retained":
        with pytest.raises(TypeError):
            stage.InitOwner()
    elif mode == "new_request":
        with pytest.raises(stage.InitRejected) as caught:
            stage._authority(NS())
        assert caught.value.stage == "owner"
    else:
        with pytest.raises(TypeError):
            object.__new__(stage.InitOwner).__reduce_ex__(4)


def test_public_prepare_has_single_irreversible_retirement_and_no_issued_child_before_sealing():
    path = software.ROOT / software.SOURCE
    methods = {
        node.name: node
        for node in ast.parse(path.read_bytes()).body
        if isinstance(node, ast.FunctionDef)
    }
    body = ast.unparse(methods["prepare"])
    assert body.index("_CONSUMED[request] = _RETIRED[") < body.index("context.parent_claim(")
    assert body.index("context.parent_claim(") < body.index("_coordinate(context)")
    assert body.index("_coordinate(context)") < body.index("object.__new__(InitOwner)")
    assert "sim=" not in ast.unparse(methods["_coordinate"])


@pytest.mark.parametrize("mutation", [None, "different_record", "different_claim"])
def test_closed_parameter_validation_never_reopens_the_active_only_parameter_accessor(mutation):
    source_record, seed_claim, seed_owner = object(), object(), object()

    class ClosedMetadataClaim:
        @property
        def parameters(self):
            raise AssertionError("An active-only accessor cannot validate a closed claim")

        @property
        def record(self):
            return source_record

    claim = ClosedMetadataClaim()
    calls = []

    def validate(current, *, seed_claim, original_owner):
        calls.append((current, seed_claim, original_owner))
        return object() if mutation == "different_record" else source_record

    context = NS(
        key=NS(SeedInitClaim=ClosedMetadataClaim, validate_closed_init=validate),
        claim=claim if mutation != "different_claim" else object(),
        seed_claim=seed_claim,
        seed_owner=seed_owner,
        parameter_record=None,
    )
    if mutation is None:
        assert stage._closed(context) is source_record and context.parameter_record is source_record
    else:
        with pytest.raises(ValueError):
            stage._closed(context)
        assert context.parameter_record is None
    assert len(calls) == (0 if mutation == "different_claim" else 1)


@pytest.mark.parametrize("primary", [False, True])
def test_recording_failure_retains_raw_result_and_original_primary_separately(primary):
    context = _observer_context()
    original, cause, capture = ValueError("source"), KeyError("cause"), OSError("event append")
    original.__cause__ = cause
    context.primary = original if primary else None

    class RejectAppend(list):
        def append(self, value):
            raise capture

    context.events = RejectAppend()
    returned = np.asarray([0.0, -0.0])
    with pytest.raises(stage.InitRejected) as caught:
        stage._event(context, "completed_return", returned)
    assert context.last_raw == ("completed_return", returned)
    assert context.capture_error is capture and caught.value.__cause__ is capture
    assert context.primary is (original if primary else None)
    assert original.__cause__ is cause and returned.tobytes() == np.asarray([0.0, -0.0]).tobytes()


@pytest.mark.parametrize("mutation", ["phase_kind", "phase_parameter", "raw_constructor"])
def test_constructor_entry_refuses_relabelled_or_unclaimed_optional_arguments_before_body(mutation):
    context = NS(phase=None, kind=object(), p=object(), cells=object(), callback=object())
    actual = object()
    kwargs = dict(kind=context.kind, p=context.p, cells=context.cells, callbacks=context.callback)
    parent = NS(f_code=stage.factories._make.__code__)
    if mutation == "phase_kind":
        kwargs["kind"] = object()
    elif mutation == "phase_parameter":
        kwargs["p"] = object()
    else:
        parent = sys._getframe()
    assert (
        stage._entry_allowed(context, "SimPhase", "__init__", actual, (actual,), kwargs, parent)
        is False
    )


def test_owned_runtime_namespace_keeps_native_class_and_delegate_without_allocating_any_object():
    calls = []

    class MetadataNative:
        def __init__(self):
            calls.append("UNEXECUTED_CONSTRUCTOR")

        def dormant(self):
            calls.append("UNEXECUTED_DORMANT")

    context = _observer_context()
    context.factories = {"Simulator": MetadataNative}
    context.runtime_types, context.runtime_bindings = {}, {}
    context.import_roster, context.factory_names = {}, ("Simulator",)
    context.selected, context.native_functions = (
        (("Simulator", "__init__"),),
        (MetadataNative.__init__,),
    )
    context.source_files = []
    stage._ACTIVE.append(context)
    try:
        stage._namespace(context)
        cls = context.runtime_types["Simulator"]
        assert cls.__bases__ == (MetadataNative,)
        assert context.delegates[("Simulator", "__init__")] is MetadataNative.__init__
        assert (
            context.methods[("Simulator", "__init__")].__code__ is MetadataNative.__init__.__code__
        )
        wrapper = vars(cls)["__init__"]
        cells = dict(
            zip(
                wrapper.__code__.co_freevars,
                (c.cell_contents for c in wrapper.__closure__ or ()),
                strict=True,
            )
        )
        assert cells["context"] is context and cells["delegate"] is MetadataNative.__init__
        assert vars(cls)["dormant"].__code__ is wrapper.__code__
        assert calls == [] and not stage._OBJECTS
    finally:
        assert stage._ACTIVE.pop() is context


@pytest.mark.parametrize("field", ["body", "event", "MT"])
@pytest.mark.parametrize("primary", [False, True])
def test_inherited_callback_epoch_failure_preserves_exact_primary_and_separate_capture(
    field, primary
):
    context = _observer_context()
    source_error, cause = ValueError("original source"), KeyError("cause")
    source_error.__cause__ = cause
    context.primary = source_error if primary else None
    capture = OSError("changed " + field)

    def after(current, old):
        assert current is context and old == "before"
        raise capture

    callback = clone(stage._inherited, _epoch=lambda current: "before", _same_epoch=after)
    if primary:
        assert (
            callback(context, lambda *args: "actual return", object(), "return", None)
            == "actual return"
        )
        assert context.primary is source_error and source_error.__cause__ is cause
    else:
        with pytest.raises(OSError) as caught:
            callback(context, lambda *args: "actual return", object(), "return", None)
        assert caught.value is capture
    assert context.capture_error is capture and context.inherited is False


@pytest.mark.parametrize("stage_name", ["constructor", "core", "seal"])
def test_failed_context_root_is_retained_before_secondary_archive_or_attachment(stage_name):
    context = NS(invalid=False, stage=stage_name)

    class RejectAppend:
        def append(self, value):
            raise OSError("archive refused")

    class NoAttributes(Exception):
        def __setattr__(self, name, value):
            raise OSError("exception attachment refused")

    original = NoAttributes("original source")
    scope = dict(vars(stage), _FAILED=RejectAppend(), _LAST_FAILED=None)
    fn = FunctionType(stage._retain.__code__, scope)
    fn(context, original)
    assert scope["_LAST_FAILED"] is context and context.failure_error is original
    assert context.invalid is True
    assert context.failure_append_error[1] is context
    assert context.failure_attachment_error[1] is context


@pytest.mark.parametrize("hook", [0, 1])
@pytest.mark.parametrize("after", [False, True])
def test_unwind_restore_failure_never_replaces_the_unclassified_original_exception(hook, after):
    context = _observer_context()
    original_hooks, real_setters = context.required_hooks, context.restore_setters
    primary, cause, capture = (
        ValueError("unclassified original"),
        KeyError("source cause"),
        OSError("restore refused"),
    )
    primary.__cause__ = cause
    attempted, refused = [], []

    def setter(index, value):
        restore = value is original_hooks[index]
        attempted.append((index, restore))
        if index == hook and restore and not refused:
            refused.append(True)
            if after:
                real_setters[index](value)
            raise capture
        real_setters[index](value)

    context.restore_setters = (lambda value: setter(0, value), lambda value: setter(1, value))
    account = contextmanager(
        clone(
            stage._account.__wrapped__,
            _inherited=lambda context, prior, frame, event, arg: (
                prior(frame, event, arg) if prior is not None else None
            ),
        )
    )
    try:
        with pytest.raises(ValueError) as caught, account(context):
            raise primary
        assert caught.value is primary and caught.value.__cause__ is cause
        assert any(error is capture for _, error, _ in context.cleanup_errors)
        assert (0, True) in attempted and (1, True) in attempted
    finally:
        real_setters[0](original_hooks[0])
        real_setters[1](original_hooks[1])
    assert sys.getprofile() is original_hooks[0] and sys.gettrace() is original_hooks[1]


@pytest.mark.parametrize("missing", ["CONSUMER_INTERFACE_SHA256", "CONSUMER_REVIEW_SHA256"])
def test_unavailable_native_namespace_contract_is_an_independent_pre_read_gate(missing):
    calls = []
    key = NS(
        CONSUMER_MODULE=stage.__name__,
        CONSUMER_INTERFACE_SHA256="a" * 64,
        CONSUMER_REVIEW_SHA256="b" * 64,
        CONSUMER_KEY_REVIEW_SHA256="c" * 64,
        consumer_interface=lambda raw: calls.append(raw),
    )
    setattr(key, missing, None)
    ready = clone(stage._key_private_contract, KEY_REVIEW_SHA256="c" * 64)
    with pytest.raises(stage.InitRejected) as caught:
        ready(key)
    assert caught.value.stage == "namespace_contract" and calls == []


@pytest.mark.parametrize("ecm", [False, True])
@pytest.mark.parametrize(
    "mutation", [None, "missing_core", "repeat_core", "conditional", "pending", "return_value"]
)
def test_complete_call_ledger_requires_every_real_stage_and_original_conditional_helper(
    ecm, mutation
):
    required = [
        ("SimPhase", "__init__"),
        ("SimPhase", "_init_kludge"),
        ("SimPhase", "_init_kludge_time"),
        ("Simulator", "__init__"),
        ("Simulator", "init_core"),
        ("SimPhaseCaches", "__init__"),
        *(
            ("TissueHandler", name)
            for name in (
                "__init__",
                "_init_tissues",
                "_init_cuts",
                "_init_events",
                "_init_events_global",
            )
        ),
    ]
    if ecm:
        required.append(("Simulator", "initDenv"))
    rows = [(role, method, object(), None) for role, method in required]
    ctx = NS(p=NS(is_ecm=ecm), method_returns=rows, frames={})
    if mutation == "missing_core":
        rows[:] = [row for row in rows if row[:2] != ("Simulator", "init_core")]
    elif mutation == "repeat_core":
        rows.extend(row for row in tuple(rows) if row[:2] == ("Simulator", "init_core"))
    elif mutation == "conditional":
        if ecm:
            rows[:] = [row for row in rows if row[:2] != ("Simulator", "initDenv")]
        else:
            rows.append(("Simulator", "initDenv", object(), None))
    elif mutation == "pending":
        ctx.frames[1] = dict(returned=False)
    elif mutation == "return_value":
        rows[0] = (*rows[0][:3], object())
    if mutation is None:
        assert stage._completion(ctx) is None
    else:
        with pytest.raises(ValueError):
            stage._completion(ctx)


@pytest.mark.parametrize("hook", [0, 1])
def test_inherited_callback_hook_retarget_is_a_capture_refusal_before_later_work(hook):
    context = _observer_context()
    original = context.required_hooks
    context.observer_hooks, context.observing = original, True

    def retarget(*args):
        (sys.setprofile, sys.settrace)[hook](lambda *args: None)
        return "completed callback"

    run = clone(stage._inherited, _epoch=lambda current: (), _same_epoch=lambda current, old: None)
    try:
        with pytest.raises(ValueError) as caught:
            run(context, retarget, object(), "return", None)
        assert context.capture_error is caught.value and context.inherited is False
    finally:
        sys.setprofile(original[0])
        sys.settrace(original[1])
    assert sys.getprofile() is original[0] and sys.gettrace() is original[1]


@pytest.mark.parametrize("broken", [False, True])
def test_failed_parameter_claim_retention_never_replaces_the_original_primary(broken):
    retained = object()

    class Primary(ValueError):
        def __getattribute__(self, name):
            if name == "seed_init_claim":
                if broken:
                    raise OSError("failed-claim metadata capture")
                return retained
            return super().__getattribute__(name)

    primary = Primary("original source")
    context = NS(invalid=False)
    scope = dict(vars(stage), _FAILED=[], _LAST_FAILED=None)
    keep = FunctionType(stage._retain.__code__, scope)
    keep(context, primary)
    assert scope["_LAST_FAILED"] is context and context.failure_error is primary
    if broken:
        assert context.failed_claim_capture[1] is primary
    else:
        assert context.failed_parameter_claim is retained


@pytest.mark.parametrize(
    "mutation", [None, "factory_body", "factory_default", "validator_body", "wrapper"]
)
def test_actual_key_public_contextmanager_and_body_contract_is_checked_without_entering_claim(
    mutation, monkeypatch
):
    path = stage.Path(key_source.__file__)
    raw = path.read_bytes()
    factory = key_source.seed_to_init
    if mutation == "factory_body":
        body = factory.__wrapped__
        monkeypatch.setattr(
            body, "__code__", body.__code__.replace(co_consts=(*body.__code__.co_consts, "drift"))
        )
    elif mutation == "factory_default":
        monkeypatch.setattr(factory.__wrapped__, "__kwdefaults__", {"enabled": 0})
    elif mutation == "validator_body":
        body = key_source.validate_closed_init
        monkeypatch.setattr(
            body, "__code__", body.__code__.replace(co_consts=(*body.__code__.co_consts, "drift"))
        )
    elif mutation == "wrapper":
        replacement = clone(factory)
        replacement.__wrapped__ = factory.__wrapped__
        monkeypatch.setattr(key_source, "seed_to_init", replacement)
    if mutation is None:
        assert stage._key_interface(key_source, raw, path) is None
    else:
        with pytest.raises(stage.InitRejected) as caught:
            stage._key_interface(key_source, raw, path)
        assert caught.value.stage == "key_interface"


def _private_namespace_metadata():
    """Real Key binding sampler, original unexecuted CodeTypes; no claim or owner."""
    native_builtins = dict(vars(builtins))
    native_namespace = dict(__builtins__=native_builtins, SimPhase=object())
    context = NS(methods={}, runtime_types={}, factory_names=("SimPhase",))
    cell = (lambda context: lambda: context)(context).__closure__[0]
    children = stage._code_tree(stage._namespace.__code__)
    import_code = next(
        code for code in children if code.co_name == "<lambda>" and "_imports" in code.co_names
    )
    factory_code = next(
        code for code in children if code.co_name == "<lambda>" and "_make" in code.co_names
    )
    import_wrapper = FunctionType(import_code, vars(stage), closure=(cell,))
    factory_wrapper = FunctionType(factory_code, vars(stage), closure=(cell,))
    factory_wrapper.__kwdefaults__ = {"_role": "SimPhase"}
    originals = {}
    for name, catalog in (
        ("__init__", "phase"),
        ("_init_kludge", "phase_kludge"),
        ("_init_kludge_time", "phase_time"),
    ):
        code = stage.source.code(catalog)
        original = FunctionType(code, native_namespace, name)
        originals[name] = original
        namespace = dict(native_namespace)
        namespace["__builtins__"] = dict(native_builtins, __import__=import_wrapper)
        namespace["SimPhase"] = factory_wrapper
        context.methods[("SimPhase", name)] = FunctionType(code, namespace, name)
    proof = NS(original_native=NS(methods=originals))
    return NS(consumer=context, proof=proof, factory=factory_wrapper, importer=import_wrapper)


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "factory_code",
        "body_code",
        "builtin",
        "order",
        "native_global",
        "foreign_wrapper_globals",
    ],
)
def test_real_key_private_namespace_sampler_rejects_drift_without_any_native_body_or_issued_owner(
    mutation,
):
    h = _private_namespace_metadata()
    body = h.consumer.methods[("SimPhase", "__init__")]
    if mutation == "factory_code":
        h.factory.__code__ = h.factory.__code__.replace(
            co_consts=(*h.factory.__code__.co_consts, "drift")
        )
    elif mutation == "body_code":
        body.__code__ = body.__code__.replace(co_consts=(*body.__code__.co_consts, "drift"))
    elif mutation == "builtin":
        body.__globals__["__builtins__"]["len"] = lambda value: 0
    elif mutation == "order":
        value = body.__globals__.pop("__builtins__")
        body.__globals__["__builtins__"] = value
    elif mutation == "native_global":
        body.__globals__["extra"] = object()
    elif mutation == "foreign_wrapper_globals":
        body.__globals__["SimPhase"] = clone(h.factory)
    if mutation is None:
        actual = key_source._private_bindings(h.proof, h.consumer, stage)
        assert actual and any(value is body for value in actual)
    else:
        with pytest.raises(ValueError):
            key_source._private_bindings(h.proof, h.consumer, stage)


@pytest.mark.parametrize("slot", [None, "KEY_SOURCE_SHA256", "KEY_REVIEW_SHA256", "body"])
def test_actual_key_consumer_interface_normalizes_only_two_declared_literal_backrefs(slot):
    raw = (software.ROOT / software.SOURCE).read_bytes()
    identity, refs = key_source.consumer_interface(raw)
    assert refs == (("KEY_SOURCE_SHA256", None), ("KEY_REVIEW_SHA256", None))
    changed = raw
    if slot == "body":
        changed += b"\n# another exact consumer byte\n"
    elif slot is not None:
        old = (slot + " = None").encode()
        assert raw.count(old) == 1
        changed = raw.replace(old, (slot + " = '" + "a" * 64 + "'").encode(), 1)
    actual, _ = key_source.consumer_interface(changed)
    assert (actual == identity) is (slot != "body")


@pytest.mark.parametrize("mutation", [None, "equal_array", "descriptor"])
def test_post_claim_seal_compares_reference_and_descriptor_graphs_even_with_equal_cache_bytes(
    mutation,
):
    first, second = np.array([1.0, -0.0]), np.array([1.0, -0.0])
    assert first is not second and first.tobytes() == second.tobytes()
    phase, cache = object(), NS(identity="unchanged_cache")
    old = ((phase, first), {"alias": ("array", 0)})
    current = (
        (phase, second if mutation == "equal_array" else first),
        {"alias": ("array", 1 if mutation == "descriptor" else 0)},
    )
    ctx = NS(phase=phase, private_seal=(phase, cache, old))
    check = clone(
        stage._check_post_claim_seal,
        _snapshot=lambda current: cache,
        _graph=lambda current: current_graph,
    )
    current_graph = current
    if mutation is None:
        assert check(ctx) is None
    else:
        with pytest.raises(ValueError):
            check(ctx)


@pytest.mark.parametrize("entry", ["prepare", "authority"])
@pytest.mark.parametrize("observer", ["delegate", "profile", "trace"])
def test_caller_retains_exact_primary_and_raw_context_when_retention_helper_entry_is_rejected(
    entry, observer, monkeypatch
):
    primary, cause, secondary = (
        ValueError("original failure"),
        KeyError("cause"),
        OSError("retention entry"),
    )
    primary.__cause__ = cause
    ctx = NS(active=False, invalid=False, validating=False, entry_error=None, primary=None)

    def fail(*args, **kwargs):
        raise primary

    def rejected(*args):
        raise secondary

    if entry == "authority":

        class MetadataOwner:
            pass

        token = MetadataOwner()
        scope = dict(
            vars(stage),
            InitOwner=MetadataOwner,
            _ISSUED={token: ctx},
            _check=fail,
            _retain=rejected,
            _LAST_FAILED=None,
        )
        fn = FunctionType(stage._authority.__code__, scope)
        args = (token,)
        kwargs = {}
    else:

        class MetadataRequest:
            seed_owner = object()

        token = MetadataRequest()
        trial, observation = object(), NS(identity="unchanged")
        parent = NS(trial=trial, api=NS(_independent_atoms=lambda value: (value,)))
        refs = (parent, trial, observation, ((), {}))
        previous = NS(
            _authority=lambda owner: parent,
            _snapshot=lambda value: observation,
            _graph=lambda value: ((), {}),
            **{stage.PARENT_CLAIM: fail, stage.PARENT_CHECK: fail},
        )
        ctx.active = True
        scope = dict(
            vars(stage),
            Request=MetadataRequest,
            _REQUESTS={token: refs},
            _CONSUMED={},
            _RETIRED={},
            _ACTIVE=[],
            previous=previous,
            _ready=lambda: NS(),
            _raw_context=lambda *args: ctx,
            source_plan=lambda: {},
            _retain=rejected,
            _LAST_FAILED=None,
        )
        fn = FunctionType(stage.prepare.__code__, scope)
        monkeypatch.setenv(stage.RELEASE, "1")
        args, kwargs = (token,), dict(enabled=True)
    original = (sys.getprofile(), sys.gettrace())
    if observer != "delegate":
        scope["_retain"] = FunctionType(stage._retain.__code__, scope)
    inherited_locals = {}

    def profile(frame, event, arg):
        if original[0] is not None:
            original[0](frame, event, arg)
        if (
            observer == "profile"
            and event == "call"
            and frame.f_code is stage._retain.__code__
            and frame.f_globals is scope
        ):
            raise secondary

    def trace(frame, event, arg):
        prior = original[1] if event == "call" else inherited_locals.get(id(frame))
        if prior is not None:
            inherited_locals[id(frame)] = prior(frame, event, arg)
        if (
            observer == "trace"
            and event == "call"
            and frame.f_code is stage._retain.__code__
            and frame.f_globals is scope
        ):
            raise secondary
        if event == "return":
            inherited_locals.pop(id(frame), None)
        return trace

    try:
        sys.setprofile(profile if observer == "profile" else original[0])
        sys.settrace(trace if observer == "trace" else original[1])
        with pytest.raises(ValueError) as caught:
            fn(*args, **kwargs)
    finally:
        sys.setprofile(original[0])
        sys.settrace(original[1])
    assert caught.value is primary and caught.value.__cause__ is cause
    assert scope["_LAST_FAILED"] is ctx and ctx.failure_error is primary
    assert ctx.retention_entry_error == (secondary, primary, ctx)
    assert ctx.active is False and ctx.validating is False and ctx.invalid is True
    assert sys.getprofile() is original[0] and sys.gettrace() is original[1]


@pytest.mark.parametrize("mutation", [None, "timing", "other_parameter", "old_simulator", "holder"])
def test_endpoint_observation_projection_permits_only_successor_timing_fields(mutation):
    class MetadataStore:
        pass

    p, old_sim = MetadataStore(), MetadataStore()
    p._run_sim, p.original = False, object()
    old_sim.retained = np.array([1.0, -0.0])
    objects = (("p", p), ("old_sim", old_sim))
    fields = [{}, {}]
    lease = NS(
        objects=objects,
        holders=(vars(p), vars(old_sim)),
        names=(tuple(vars(p)), tuple(vars(old_sim))),
        fields=fields,
        view=NS(objects=objects, fields=fields),
    )
    ctx = NS(seed_lease=lease, p=p)
    initial = stage._seed_projection(ctx)
    before = tuple(tuple(part) for part in initial.fields)
    if mutation == "timing":
        p.dt, p.resample, p.total_time, p.t_resample = 0.01, 0.1, 1.0, 10.0
    elif mutation == "other_parameter":
        p.unowned = object()
    elif mutation == "old_simulator":
        old_sim.new_field = object()
    elif mutation == "holder":
        old_sim.__dict__ = dict(vars(old_sim))
    if mutation in (None, "timing"):
        current = stage._seed_projection(ctx)
        assert tuple(tuple(part) for part in current.fields) == before
        assert "_run_sim" not in current.fields[0]
    else:
        with pytest.raises(ValueError):
            stage._seed_projection(ctx)


@pytest.mark.parametrize("entry", ["ready", "unissued_claim"])
def test_new_endpoint_handoff_has_an_independent_unadopted_gate_before_foreign_owner_read(entry):
    ready = clone(stage.previous._init_consumer_api, _ready=lambda: NS())
    claim = clone(stage.previous._claim_for_init_phase, _init_consumer_api=ready)
    with pytest.raises(stage.previous.JunctionsRejected) as caught:
        if entry == "ready":
            ready()
        else:
            claim(object(), expected=object(), transition=object())
    assert caught.value.stage == "INIT_held"


def test_endpoint_sticky_retirement_precedes_original_validation_and_actual_lease_capture():
    path = stage.Path(stage.previous.__file__)
    nodes = {
        node.name: node
        for node in ast.parse(path.read_bytes()).body
        if isinstance(node, ast.FunctionDef)
    }
    body = ast.unparse(nodes["_claim_for_init_phase"])
    assert body.index("parent.init_transition = transition") < body.index("_FORWARDED[owner]")
    assert body.index("_FORWARDED[owner]") < body.index("_check(parent)")
    assert body.index("_check(parent)") < body.index("module._capture_seed_lease(")
    assert "parent.invalid = transition.invalid = True" in body
    authority = ast.unparse(nodes["_check_init_phase_authority"])
    calls = {
        node.func.id
        for node in ast.walk(nodes["_check_init_phase_authority"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_check" not in calls and "_authority" not in calls
    assert "module._check_seed_lease(transition)" in authority


@pytest.mark.parametrize("slot", [None, *stage.previous.INIT_BACK_REFERENCE_SLOTS, "body"])
def test_endpoint_template_normalizes_only_four_independently_checked_consumer_backrefs(slot):
    raw = (software.ROOT / software.SOURCE).read_bytes()
    binding = clone(stage.previous._init_consumer_binding, _ready=lambda: guards.stage)
    identity, refs = binding(raw)
    assert refs == tuple((name, None) for name in stage.previous.INIT_BACK_REFERENCE_SLOTS)
    changed = raw
    if slot == "body":
        changed += b"\n# exact endpoint consumer template changes\n"
    elif slot is not None:
        old = (slot + " = None").encode()
        assert raw.count(old) == 1
        changed = raw.replace(old, (slot + " = '" + "a" * 64 + "'").encode(), 1)
    actual, changed_refs = binding(changed)
    assert (actual == identity) is (slot != "body")
    if slot not in (None, "body"):
        assert dict(changed_refs)[slot] == "a" * 64
    # Key's independently declared template normalizes exactly its TWO refs.
    key_original = key_source.consumer_interface(raw)[0]
    key_changed = key_source.consumer_interface(changed)[0]
    assert (key_original == key_changed) is (
        slot in (None, "KEY_SOURCE_SHA256", "KEY_REVIEW_SHA256")
    )


@pytest.mark.parametrize("mutation", [None, "registry", "entry", "context", "role"])
def test_endpoint_factored_lease_retains_actual_tuple_entries_without_reopening_numeric_state(
    mutation,
):
    cache, raw, role = NS(), object(), "actual retained cache role"
    value = (cache, role)
    registry = {raw: value}
    module = NS(_OBJECTS=registry)
    edge = stage._seed_edge_records(module, cache)
    assert edge[3] == (("_OBJECTS", registry, ((raw, value, value),)),)
    lease = NS(edges=(edge,))
    if mutation == "registry":
        module._OBJECTS = dict(registry)
    elif mutation == "entry":
        registry[raw] = tuple([cache, role])
    elif mutation == "context":
        registry[raw] = (NS(), role)
    elif mutation == "role":
        registry[raw] = (cache, "different role")
    if mutation is None:
        stage.core._check_profile_ancestor_edges(lease)
    else:
        with pytest.raises(ValueError):
            stage.core._check_profile_ancestor_edges(lease)


@pytest.mark.parametrize(
    "module",
    [
        stage.core.previous,
        stage.core.previous.previous,
        stage.core.previous.previous.previous,
        stage.core._BASE,
        stage.core._BASE.image,
        stage.core._PREFIX,
        stage.core,
        stage.previous.previous,
        stage.previous,
        stage.caches.previous,
        stage.caches,
    ],
    ids=lambda module: module.__name__.rsplit(".", 1)[-1],
)
def test_real_source_module_registry_roster_preserves_module_aliases_without_mapping_calls(
    module, tmp_path
):
    # Inspect actual loaded source-module declarations. No context, owner,
    # claim, phase or registry entry is fabricated or admitted by this control.
    witness = NS()
    edge = stage._seed_edge_records(module, witness)
    actual = {name: (registry, entries) for name, registry, entries in edge[3]}
    for name, (registry, entries) in actual.items():
        assert vars(module)[name] is registry
        if type(registry) is ModuleType:
            assert name == "_WORLD" and entries == ()
        else:
            assert type(registry) in (dict, stage.WeakKeyDictionary)
    if module is stage.previous:
        assert actual["_WORLD"] == (module._WORLD, ())
        assert type(module._WORLD) is ModuleType
    stage.core._check_profile_ancestor_edges(NS(edges=(edge,)))
    software.snapshot.write_json(
        tmp_path / "actual-source-registry-roster.json",
        dict(
            module=module.__name__,
            retained=tuple((name, type(value).__qualname__) for name, (value, _) in actual.items()),
            actual_issued_owner=False,
            constructor_or_native_body=False,
        ),
    )


@pytest.mark.parametrize("mutation", [None, "alias", "registry", "entry", "not_registry"])
def test_module_alias_and_real_registry_edges_are_distinct_and_independently_guarded(mutation):
    witness, raw = NS(), object()
    original = ModuleType("retained_original_Poisson_source")
    value = (witness, "original role")
    registry = {raw: value}
    module = NS(_WORLD=original, _OBJECTS=registry)
    edge = stage._seed_edge_records(module, witness)
    if mutation == "alias":
        module._WORLD = ModuleType(original.__name__)
    elif mutation == "registry":
        module._OBJECTS = dict(registry)
    elif mutation == "entry":
        registry[raw] = tuple([witness, "original role"])
    elif mutation == "not_registry":

        class NotRegistry:
            def items(self):
                raise AssertionError("No foreign mapping delegate may execute")

        module._OBJECTS = NotRegistry()
        with pytest.raises(ValueError):
            stage._seed_edge_records(module, witness)
        return
    lease = NS(edges=(edge,))
    if mutation is None:
        stage.core._check_profile_ancestor_edges(lease)
    else:
        with pytest.raises(ValueError):
            stage.core._check_profile_ancestor_edges(lease)


@pytest.mark.parametrize("entry", ["api", "claim"])
def test_dynamics_handoff_unbound_gate_precedes_any_foreign_owner_or_callback(entry, monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("No foreign owner inspection before reviewed adoption")

    monkeypatch.setattr(stage.importlib, "import_module", lambda *a: pytest.fail("No import"))
    with pytest.raises(stage.InitRejected) as caught:
        if entry == "api":
            stage._dynamics_api()
        else:
            stage._claim_for_init_dynamics_prelude(
                Foreign(), expected=Foreign(), transition=Foreign(), entries=Foreign()
            )
    assert caught.value.stage == "dynamics_held"


@pytest.mark.parametrize("slot", [None, "PARENT_SOURCE_SHA256", "PARENT_REVIEW_SHA256", "body"])
def test_dynamics_handoff_exact_two_literal_backrefs_leave_all_other_source_bytes_bound(slot):
    raw = stage.Path(dynamics.__file__).read_bytes()
    binding = clone(stage._dynamics_binding, previous=NS(_ready=lambda: guards.stage))
    identity, refs = binding(raw)
    assert refs == (("PARENT_SOURCE_SHA256", None), ("PARENT_REVIEW_SHA256", None))
    changed = raw
    if slot == "body":
        changed += b"\n# distinct exact prelude byte\n"
    elif slot is not None:
        old = (slot + " = None").encode()
        assert raw.count(old) == 1
        changed = raw.replace(old, (slot + " = '" + "c" * 64 + "'").encode(), 1)
    actual, _ = binding(changed)
    assert (identity == actual) is (slot != "body")


def _dynamics_frame_model(method, mutation):
    """Original runtime factory/wrapper CodeTypes; no parent/owner is issued."""
    source_calls, dispatches, guards_seen = [], [], []

    class SyntheticOriginal:
        def initDenv(self, cells, p):
            source_calls.append("UNAUTHORIZED_BODY")

        def get_ion(self, name):
            source_calls.append("UNAUTHORIZED_BODY")

    context = NS(
        factories={"Simulator": SyntheticOriginal},
        runtime_types={},
        runtime_bindings={},
        objects=[],
        dynamics_frames={},
        dynamics_attempts=[],
        invalid=False,
        stage="synthetic_wrapper_metadata",
        request=object(),
        trial=None,
        entry_error=None,
        p=object(),
        cells=NS(original="cells"),
    )
    child = NS(active=True, invalid=False, body_frame=None, entries={})
    context.dynamics_transition = child
    objects = {}
    scope = dict(vars(stage), _OBJECTS=objects)

    def route(parent):
        assert parent is context
        if context.invalid or child.invalid:
            raise ValueError("Sticky failed metadata epoch")
        return child, api

    scope["_dynamics_route"] = route
    for name in (
        "_guard",
        "_invoke",
        "_dynamics_wrapper_guard",
        "_dynamics_dispatch_guard",
        "_reject",
    ):
        scope[name] = FunctionType(getattr(stage, name).__code__, scope)
    factory_scope = dict(
        vars(stage.factories),
        _guard=lambda value: None,
        _OBJECTS=objects,
        _lazy_factory=lambda value, role: value.factories[role],
        _native_call=scope["_invoke"],
    )
    runtime_type = FunctionType(stage.factories._runtime_type.__code__, factory_scope)
    factory_scope["_runtime_type"] = runtime_type
    cls = runtime_type(context, "Simulator")
    factory_scope["_guard"] = scope["_guard"]
    actual = object.__new__(cls)
    context.phase = NS(sim=actual)
    objects[actual] = context
    context.objects.append(("Simulator", actual))
    marker = object()

    def dispatched(child_arg, parent, label, delegate, receiver, args, kwargs, frame):
        assert child_arg is child and parent is context and receiver is actual
        assert frame is sys._getframe(1) and frame.f_code is stage._invoke.__code__
        dispatches.append((label, args, kwargs))
        return marker

    child.entries["dispatch"] = dispatched

    def checked(child_arg, parent, frame):
        assert child_arg is child and parent is context
        guards_seen.append(frame)
        if mutation == "argument":
            frame.f_locals["args"] = (
                (NS(original="cells"), context.p)
                if method == "initDenv"
                else (bytes("Na", "ascii").decode(),)
            )
        elif mutation == "caught_reentry":
            try:
                invoke_method()
            except (stage.InitRejected, ValueError):
                pass

    api = NS(_ACTIVE=[child], _wrapper_guard=checked)
    wrapper = vars(cls)[method]
    if mutation == "closure":
        cells = dict(zip(wrapper.__code__.co_freevars, wrapper.__closure__, strict=True))
        cells["delegate"].cell_contents = lambda *a, **k: source_calls.append("FOREIGN_BODY")
    receiver = actual
    if mutation == "receiver":
        receiver = object.__new__(cls)
        objects[receiver] = context

    def invoke_method():
        if child.body_frame is None:
            child.body_frame = sys._getframe()
        args = (context.cells, context.p) if method == "initDenv" else ("Na",)
        return getattr(receiver, method)(*args)

    return NS(
        call=invoke_method,
        context=context,
        child=child,
        cls=cls,
        source_calls=source_calls,
        dispatches=dispatches,
        guards_seen=guards_seen,
        marker=marker,
    )


@pytest.mark.parametrize("method", stage.DYNAMICS_HELPERS)
@pytest.mark.parametrize("mutation", [None, "closure", "receiver", "argument", "caught_reentry"])
def test_dynamics_handoff_actual_shared_wrapper_code_preserves_closures_and_zero_native_delegates(
    method, mutation, tmp_path
):
    model = _dynamics_frame_model(method, mutation)
    wrappers = [vars(model.cls)[name] for name in stage.DYNAMICS_HELPERS]
    assert wrappers[0].__code__ is wrappers[1].__code__
    assert wrappers[0].__closure__ is not wrappers[1].__closure__
    if mutation is None:
        assert model.call() is model.marker
        assert len(model.dispatches) == len(model.guards_seen) == 1
    else:
        with pytest.raises((stage.InitRejected, ValueError)):
            model.call()
        assert model.context.invalid and model.child.invalid
        assert model.dispatches == []
    assert model.source_calls == []
    software.snapshot.write_json(
        tmp_path / "shared-original-wrapper-metadata.json",
        dict(
            method=method,
            mutation=mutation,
            actual_factory_wrapper_CodeType=True,
            source_delegate_calls=model.source_calls,
            dispatches=len(model.dispatches),
            issued_InitOwner=False,
            synthetic_metadata_only=True,
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    [None, "owned_field", "owned_in_place", "parameter", "cell_alias", "holder", "extra"],
)
def test_dynamics_handoff_projection_keeps_full_immutable_state_and_aliases(mutation):
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    class Store:
        pass

    sim, p, cells = Store(), Store(), Store()
    sim.D_env, sim.retained = np.array([[1.0, 2.0]]), np.array([7.0, -0.0])
    p.dt, cells.original = 0.01, np.array([4.0, -0.0])
    original_array = cells.original
    objects = (("sim", sim), ("p", p), ("cells", cells))
    fields = [{} for _ in objects]
    context = NS(
        objects=objects,
        p=p,
        cells=cells,
        phase=NS(sim=sim),
        parent=NS(world=object()),
        dynamics_lease=NS(
            objects=objects,
            holders=tuple(vars(value) for _, value in objects),
            names=tuple(tuple(vars(value)) for _, value in objects),
            fields=fields,
            view=NS(objects=objects, fields=fields),
            tape=NS(rng=object(), events=(), draws=(), locals={}),
        ),
    )
    scope = observation.Scope()
    core = NS(previous=NS(_scope=lambda ignored: scope), _LITERAL=stage.core._LITERAL)
    values = clone(stage._dynamics_values, core=core, _projector=lambda value: NS(objects=objects))
    graph = clone(stage._dynamics_graph, core=core)
    original_values, original_graph = values(context), graph(context)
    if mutation == "owned_field":
        sim.smooth_weight_mem = np.array([1.0, 2.0])
    elif mutation == "owned_in_place":
        sim.D_env[0, 0] = 3.0
    elif mutation == "parameter":
        p.dt = 0.02
    elif mutation == "cell_alias":
        cells.original = original_array.copy()
        assert cells.original.tobytes() == original_array.tobytes()
    elif mutation == "holder":
        sim.__dict__ = dict(vars(sim))
    elif mutation == "extra":
        sim.not_owned = 17
    if mutation in (None, "owned_field", "owned_in_place"):
        assert values(context).identity == original_values.identity
        current = graph(context)
        stage.core.previous._same(current[0], original_graph[0])
        assert current[1] == original_graph[1]
    elif mutation == "parameter":
        assert values(context).identity != original_values.identity
    elif mutation == "cell_alias":
        assert values(context).identity == original_values.identity
        with pytest.raises(ValueError):
            stage.core.previous._same(graph(context)[0], original_graph[0])
    else:
        with pytest.raises(ValueError):
            values(context)


def test_dynamics_handoff_claim_is_irreversible_and_factored_check_has_no_stale_cache_equality():
    nodes = {
        node.name: node
        for node in ast.parse(stage.Path(stage.__file__).read_bytes()).body
        if isinstance(node, ast.FunctionDef)
    }
    claim = ast.unparse(nodes["_claim_for_init_dynamics_prelude"])
    assert claim.index("parent.dynamics_transition = transition") < claim.index("_FORWARDED[owner]")
    assert claim.index("_FORWARDED[owner]") < claim.index("_check(parent, closed=True)")
    assert claim.index("_check(parent, closed=True)") < claim.index(
        "_capture_dynamics_lease(parent)"
    )
    check = ast.unparse(nodes["_check_init_dynamics_prelude_authority"])
    assert "_check(parent, closed=True)" in check
    assert "_dynamics_values" in check and "_dynamics_graph" in check
    calls = {
        node.func.id
        for node in ast.walk(nodes["_check_init_dynamics_prelude_authority"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_authority" not in calls and "_snapshot" not in calls


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "issuance",
        "retirement",
        "request",
        "record",
        "phase",
        "lease",
        "lease_registry",
        "frames",
        "attempts",
    ],
)
def test_dynamics_handoff_private_registry_link_controls_cannot_substitute_equal_contexts(mutation):
    """Private metadata table only; no public owner or registry is manufactured."""
    owner, p, cells, callback = (object() for _ in range(4))
    phase = NS(sim=object())
    trial, record = object(), object()
    request = dynamics.Request(owner, "metadata-parent", "metadata-source", "metadata-request")
    entries = dict(dispatch=dynamics._dispatch, wrapper_guard=dynamics._wrapper_guard)
    parent = NS(
        owner=owner,
        active=False,
        invalid=False,
        thread=stage.get_ident(),
        trial=trial,
        parameter_record=record,
        phase=phase,
        p=p,
        cells=cells,
        callback=callback,
        dynamics_entries=entries,
        dynamics_frames={},
        dynamics_attempts=[],
    )
    child = NS(
        request=request,
        invalid=False,
        thread=parent.thread,
        parent=parent,
        parent_trial=trial,
        parent_record=record,
        phase=phase,
        p=p,
        cells=cells,
        sim=phase.sim,
        callback=callback,
        entries=entries,
    )
    child.refs = (parent, trial, object(), object())
    parent.dynamics_transition = child
    lease = NS(
        entries=entries,
        frames=parent.dynamics_frames,
        attempts=parent.dynamics_attempts,
        transition=child,
    )
    parent.dynamics_lease = lease
    api = NS(
        Request=dynamics.Request,
        _REQUESTS={request: child.refs},
        _CONSUMED={request: child},
        _RETIRED={owner: child},
        _dispatch=dynamics._dispatch,
        _wrapper_guard=dynamics._wrapper_guard,
    )
    issuance, forwarding, leases = {owner: parent}, {owner: child}, {owner: lease}
    check = clone(
        stage._dynamics_route,
        _dynamics_api=lambda: api,
        _ISSUED=issuance,
        _FORWARDED=forwarding,
        _DYNAMICS_LEASES=leases,
    )
    if mutation == "issuance":
        issuance[owner] = NS(**vars(parent))
    elif mutation == "retirement":
        forwarding[owner] = NS(**vars(child))
    elif mutation == "request":
        api._REQUESTS[request] = tuple(list(child.refs))
    elif mutation == "record":
        child.parent_record = object()
    elif mutation == "phase":
        child.phase = NS(**vars(phase))
    elif mutation == "lease":
        parent.dynamics_lease = NS(**vars(lease))
    elif mutation == "lease_registry":
        leases[owner] = NS(**vars(lease))
    elif mutation == "frames":
        parent.dynamics_frames = dict(parent.dynamics_frames)
    elif mutation == "attempts":
        parent.dynamics_attempts = list(parent.dynamics_attempts)
    if mutation is None:
        assert check(parent) == (child, api)
    else:
        with pytest.raises(ValueError):
            check(parent)


@pytest.mark.parametrize("value", [object, FunctionType, np.ndarray, 7, "surface-leaf"])
def test_dynamics_surface_leaf_results_are_exact_original_identity_atoms(value):
    old = stage.factories.aliases._atoms(value)
    new = stage._surface_atoms(value)
    assert len(new) == len(old)
    assert all(a is b for a, b in zip(new, old, strict=True))


@pytest.mark.parametrize("kind", ["object", "ndarray", "python"])
def test_dynamics_surface_binding_keeps_exact_original_class_roster_and_atoms(kind):
    class Example:
        def method(self, value=1):
            raise AssertionError("No source delegate may execute")

        @property
        def value(self):
            raise AssertionError("No property delegate may execute")

    cls = {"object": object, "ndarray": np.ndarray, "python": Example}[kind]
    before, after = stage.factories._surface(cls), stage._surface(cls)
    assert len(before) == len(after)
    assert all(a is b for a, b in zip(before, after, strict=True))


@pytest.mark.parametrize("mutation", ["method_code", "closure", "sampler_code", "surface_delegate"])
def test_dynamics_surface_still_detects_live_mutable_code_closure_and_sampler_drift(
    mutation, monkeypatch
):
    retained = object()

    def make(marker):
        def method(self):
            return marker

        return method

    class Example:
        pass

    Example.method = make(retained)
    before = stage._surface(Example)
    if mutation == "method_code":
        function = Example.method
        monkeypatch.setattr(
            function,
            "__code__",
            function.__code__.replace(co_consts=(*function.__code__.co_consts, "changed")),
        )
    elif mutation == "closure":
        Example.method.__closure__[0].cell_contents = object()
    elif mutation == "sampler_code":

        def hostile(value):
            raise AssertionError("Foreign sampler body must never execute")

        monkeypatch.setattr(stage.factories.aliases._atoms, "__code__", hostile.__code__)
    elif mutation == "surface_delegate":
        monkeypatch.setattr(
            stage.factories, "_surface", lambda value: pytest.fail("Foreign surface")
        )
    if mutation in ("sampler_code", "surface_delegate"):
        with pytest.raises(ValueError):
            stage._surface(Example)
    else:
        with pytest.raises(ValueError):
            stage.core.previous._same(stage._surface(Example), before)


@pytest.fixture
def synthetic_init_inputs(monkeypatch, tmp_path):
    """REAL public issuer, explicit synthetic upstream/provider/body contracts.

    No InitOwner is allocated, cast, hydrated or inserted by the fixture.
    Acquisition and upstream/parameter authority are test-only stand-ins, so
    this fixture supplies no actual native parent or scientific admission.
    Constructor dispatch, sealing, issuance, ongoing checks and the following
    consumer claim use the actual production APIs and runtime wrapper factory.
    """
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    h = NS()

    class Kind(Enum):
        INIT = 1

    h.p = NS(
        _run_sim=False,
        dt=0.01,
        resample=0.1,
        total_time=1.0,
        t_resample=10.0,
        is_ecm=True,
        init_export_dirname="metadata-no-path-created",
        v_sensitive_gj=False,
        ions_dict={"Na": 1, "K": 1},
        cbnd=None,
    )
    h.cells = NS(weights=np.array([0.25, 0.5]), environment=np.array([[3.0, 4.0], [5.0, 6.0]]))
    h.callback = NS(label="same synthetic callback")
    old_sim, old_handler = NS(historical="sim"), NS(historical="handler")
    old_phase = NS(
        p=h.p,
        cells=h.cells,
        sim=old_sim,
        dyna=old_handler,
        cache=NS(historical="cache"),
        callbacks=h.callback,
    )
    original_record, seed_claim, seed_owner = object(), object(), object()
    world = NS(
        active=False,
        invalid=False,
        p=h.p,
        parameter_record=original_record,
        claim=seed_claim,
        request=NS(world_parameters=seed_owner),
    )
    old_objects = [
        ("old_phase", old_phase),
        ("old_sim", old_sim),
        ("old_handler", old_handler),
        ("old_cache", old_phase.cache),
        ("parameters", h.p),
        ("cells", h.cells),
        ("callback", h.callback),
    ]
    seed = NS(
        trial=NS(source_completed=True, identity="synthetic-upstream-not-native"),
        phase=old_phase,
        sim=old_sim,
        dyna=old_handler,
        p=h.p,
        cells=h.cells,
        api=guards.stage,
        rng=object(),
        thread=stage.get_ident(),
        world=NS(world=world, parent=NS(projector=NS(objects=old_objects))),
    )

    class UpstreamMetadataOwner:
        pass

    upstream_owner = UpstreamMetadataOwner()
    scope = observation.Scope()
    tape = NS(rng=seed.rng, events=(), draws=(), locals={})

    def upstream(owner):
        assert owner is upstream_owner
        return seed

    def retire(owner, *, expected, transition):
        assert owner is upstream_owner and expected is seed.trial
        assert not hasattr(seed, "attempted")
        seed.attempted = transition
        assert transition.phase is None and transition.claim is None
        # This predecessor is explicitly synthetic. Capture its ACTUAL live
        # metadata before the real INIT constructor, instead of inventing a
        # missing lease after an owner is issued. Empty native source edges
        # grant no real upstream authority; every buffer/alias is observed by
        # the same original projection and graph functions used downstream.
        objects = tuple(old_objects)
        fields = [{} for _ in objects]
        lease = NS(
            edges=(),
            files=(),
            samplers=(),
            objects=objects,
            holders=tuple(vars(value) for _, value in objects),
            names=tuple(tuple(vars(value)) for _, value in objects),
            fields=fields,
            view=NS(objects=objects, fields=fields),
            tape=tape,
            projector=NS(objects=list(old_objects)),
            stream=stage._rng(transition),
        )
        transition.seed_lease = lease
        lease.values, lease.graph = stage._seed_values(transition), stage._seed_graph(transition)
        h.synthetic_seed_lease = lease

    def live(transition, *, parameter_claim, parameter_record):
        assert seed.attempted is transition
        assert transition.p is h.p and transition.cells is h.cells
        return seed

    predecessor = NS(
        JunctionsOwner=UpstreamMetadataOwner,
        previous=stage.previous.previous,
        _authority=upstream,
        _snapshot=lambda parent: scope.snapshot(dict(p=vars(h.p), cells=vars(h.cells))),
        _graph=lambda parent: scope.graph(h.cells, h.p, tape),
        **{stage.PARENT_CLAIM: retire, stage.PARENT_CHECK: live},
    )
    record = object()

    class SyntheticClaim:
        active = False

        @property
        def parameters(self):
            assert self.active
            return h.p

        @property
        def record(self):
            assert not self.active
            return record

        def check(self):
            assert self.active

    @contextmanager
    def transition(claim, *, original_owner, law_id, enabled):
        assert claim is seed_claim and original_owner is seed_owner and enabled is True
        value = SyntheticClaim()
        value.active = True
        try:
            yield value
        finally:
            value.active = False

    def closed(claim, *, seed_claim, original_owner):
        assert type(claim) is SyntheticClaim and original_owner is seed_owner
        return claim.record

    key = NS(
        seed_to_init=transition,
        validate_closed_init=closed,
        SeedInitClaim=SyntheticClaim,
        SEED_INIT_LAW="synthetic-provider-not-native",
    )

    class BoundarySink:
        def __init__(self):
            self.rows, self.started = [], time.monotonic()

        def __call__(self, name):
            row = (name, time.monotonic() - self.started)
            self.rows.append(row)
            try:
                software.snapshot.write_json(
                    tmp_path / ("synthetic-body-boundary-" + str(len(self.rows)) + ".json"),
                    dict(boundary=row, source_or_scientific_credit=False),
                )
            except BaseException as error:
                self.capture = (error, row)
                raise

    h.boundaries = BoundarySink()
    namespace = dict(__name__=__name__, __builtins__=vars(builtins), np=np, milestone=h.boundaries)
    synthetic = """
class Simulator:
    def __init__(self):
        milestone("Simulator.__init__")
    def init_core(self, phase):
        milestone("init_core_begin")
        self.D_env = np.array([[2.0, 4.0], [6.0, 8.0]])
        self.c_env_bound = np.array([10.0, 20.0])
        self.retained = np.array([0.125, -0.0])
        self.gj_funk = None
        self.initDenv(phase.cells, phase.p)
        milestone("init_core_end")
    def initDenv(self, cells, p):
        self.D_env_weight = cells.environment
    def get_ion(self, ion_name):
        return {"Na": 0, "K": 1}[ion_name]
    def init_dynamics(self, phase):
        milestone("dynamics_begin")
        self.smooth_weight_mem = phase.cells.weights
        self.smooth_weight_o = phase.cells.weights
        self.initDenv(phase.cells, phase.p)
        for key, val in phase.p.ions_dict.items():
            if val == 1:
                ion_i = self.get_ion(key)
                if phase.p.cbnd is not None:
                    self.c_env_bound[ion_i] = phase.p.cbnd[key]
        milestone("dynamics_end")
class SimPhaseCaches:
    def __init__(self, phase):
        milestone("cache_begin")
        self.phase = phase
class TissueHandler:
    def __init__(self, p):
        milestone("handler_begin")
        self._init_tissues(p)
        self._init_cuts(p)
        self._init_events(p)
    def _init_tissues(self, p):
        pass
    def _init_cuts(self, p):
        pass
    def _init_events(self, p):
        self._init_events_global(p)
    def _init_events_global(self, p):
        pass
class SimPhase:
    def __init__(self, *, kind, p, cells, callbacks):
        milestone("phase_begin")
        sim = Simulator()
        self.callbacks = callbacks
        self.cells = cells
        self.kind = kind
        self.p = p
        self.sim = sim
        self.cache = SimPhaseCaches(self)
        self.dyna = TissueHandler(p)
        self._init_kludge()
        self.export_dirname = p.init_export_dirname
        milestone("phase_end")
    def _init_kludge(self):
        self.sim.dyna = self.dyna
        self._init_kludge_time()
    def _init_kludge_time(self):
        pass
class Gap_Junction:
    pass
"""
    # Clearly test-labelled bodies, never a substituted original-source oracle.
    exec(compile(synthetic, __file__, "exec"), namespace)
    factories = {
        role: namespace[role]
        for role in ("SimPhase", "Simulator", "SimPhaseCaches", "TissueHandler")
    }

    def acquire_synthetic(context):
        context.factories = factories
        context.kind = Kind.INIT
        context.factory_names = tuple(factories)
        context.import_roster = {}
        context.selected = (
            ("SimPhase", "__init__"),
            ("SimPhase", "_init_kludge"),
            ("SimPhase", "_init_kludge_time"),
            ("Simulator", "__init__"),
            ("Simulator", "init_core"),
            ("Simulator", "initDenv"),
            ("SimPhaseCaches", "__init__"),
            *(
                ("TissueHandler", name)
                for name in (
                    "__init__",
                    "_init_tissues",
                    "_init_cuts",
                    "_init_events",
                    "_init_events_global",
                )
            ),
        )
        context.native_functions = tuple(
            getattr(factories[role], name) for role, name in context.selected
        )
        context.source_files = []

    monkeypatch.setattr(stage, "previous", predecessor)
    monkeypatch.setattr(stage, "_ready", lambda: key)
    monkeypatch.setattr(
        stage, "source_plan", lambda: dict(law=stage.LAW_ID, synthetic_not_native=True)
    )
    monkeypatch.setattr(stage, "_dynamics_api", lambda: dynamics)
    monkeypatch.setattr(stage, "_acquire", acquire_synthetic)
    monkeypatch.setattr(stage.core.previous, "_scope", lambda ignored: scope)
    monkeypatch.setattr(stage.core.previous, "_rng", lambda ignored: NS(identity="metadata-no-RNG"))
    monkeypatch.setenv(stage.RELEASE, "1")
    h.upstream_owner, h.old_phase, h.old_sim = upstream_owner, old_phase, old_sim
    h.upstream, h.predecessor = seed, predecessor
    h.scope, h.factories, h.namespace = scope, factories, namespace
    h.seams = (
        "synthetic upstream predecessor",
        "synthetic predecessor live metadata lease captured before actual phase allocation",
        "synthetic active/closed parameter provider",
        "synthetic constructor/core/helper bodies acquired before allocation",
        "ordinary observation scope and unchanged non-RNG stream metadata",
        "unbound provider gates remain closed outside this fixture",
    )
    return h


@pytest.fixture
def issued_synthetic_init(synthetic_init_inputs, tmp_path):
    h = synthetic_init_inputs
    started = time.monotonic()
    marks = []

    def mark(name):
        row = (name, time.monotonic() - started)
        marks.append(row)
        software.snapshot.write_json(
            tmp_path / ("public-issuer-boundary-" + str(len(marks)) + ".json"),
            dict(boundary=row, prior=tuple(marks), native_or_scientific_credit=False),
        )

    mark("before_from_seed")
    h.request = stage.from_seed(h.upstream_owner, law_id=stage.LAW_ID)
    mark("after_from_seed_before_prepare")
    h.owner = stage.prepare(h.request, enabled=True)
    mark("after_prepare_before_authority")
    h.context = stage._authority(h.owner)
    mark("after_authority")
    assert type(h.owner) is stage.InitOwner and stage._ISSUED[h.owner] is h.context
    assert h.context.phase is not h.old_phase and h.context.phase.sim is not h.old_sim
    assert h.context.p is h.p and h.context.cells is h.cells
    return h


def test_synthetic_predecessor_captures_actual_old_metadata_before_any_phase_or_claim(
    synthetic_init_inputs,
):
    h = synthetic_init_inputs
    request = stage.from_seed(h.upstream_owner, law_id=stage.LAW_ID)
    refs = stage._REQUESTS[request]
    context = stage._raw_context(request, refs, stage._ready())
    assert context.phase is None and context.claim is None
    h.predecessor._claim_for_init_phase(
        h.upstream_owner, expected=h.upstream.trial, transition=context
    )
    lease = context.seed_lease
    assert lease is h.synthetic_seed_lease
    assert context.phase is None and context.claim is None
    assert not context.objects and not hasattr(context, "owner")
    assert not lease.edges and not lease.files and not lease.samplers
    assert any(actual is h.p for _, actual in lease.objects)
    assert any(actual is h.cells for _, actual in lease.objects)
    assert stage._seed_values(context).identity == lease.values.identity
    current = stage._seed_graph(context)
    assert len(current[0]) == len(lease.graph[0])
    assert all(a is b for a, b in zip(current[0], lease.graph[0], strict=True))
    assert current[1] == lease.graph[1]
    h.cells.weights[0] = 99.0
    assert stage._seed_values(context).identity != lease.values.identity
    assert all(value is not context for value in stage._ISSUED.values())


@pytest.mark.parametrize("entry", ("guard", "invoke"))
@pytest.mark.parametrize("falsey", (False, True))
def test_first_step_retained_entry_keeps_leaf_primary_before_any_runtime_route(
    entry, falsey, monkeypatch
):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary = (Falsey if falsey else ValueError)("first-step original entry failure")
    primary.__cause__ = TypeError("original cause")
    leaf = NS(entry_error=primary)
    electrical = NS(first_step_transition=leaf)
    storage = NS(electrical_transition=electrical)
    completion = NS(storage_transition=storage)
    prelude = NS(completion_transition=completion)
    initial = NS(dynamics_transition=prelude)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("No route/validator/delegate may replace an existing primary")

    monkeypatch.setattr(stage, "_first_step_runtime", forbidden)
    with pytest.raises(ValueError) as caught:
        if entry == "guard":
            stage._guard(initial)
        else:
            stage._invoke(initial, "Simulator.update_V", forbidden)
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__
    assert calls == []


@pytest.mark.parametrize("entry", ("guard", "invoke"))
@pytest.mark.parametrize("falsey", (False, True))
def test_first_step_retained_source_precedes_secondary_entry_and_runtime_route(
    entry, falsey, monkeypatch
):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    original, cause = (Falsey if falsey else ValueError)("raw source"), OSError("source cause")
    original.__cause__ = cause
    leaf = NS(
        first_failure=("source", original),
        entry_error=RuntimeError("secondary entry failure"),
        failure_error=OSError("secondary capture"),
    )
    electrical = NS(first_step_transition=leaf)
    storage = NS(electrical_transition=electrical)
    completion = NS(storage_transition=storage)
    prelude = NS(completion_transition=completion)
    initial, calls = NS(dynamics_transition=prelude), []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("A retained first source failure must precede all live routes/delegates")

    monkeypatch.setattr(stage, "_first_step_runtime", forbidden)
    with pytest.raises(ValueError) as caught:
        if entry == "guard":
            stage._guard(initial)
        else:
            stage._invoke(initial, "Simulator.update_V", forbidden)
    assert caught.value is original and original.__cause__ is cause
    assert calls == []


def test_dynamics_setup_namespace_and_epoch_cost_without_issuing_or_allocating_source_objects(
    synthetic_init_inputs, tmp_path
):
    h = synthetic_init_inputs
    request = stage.from_seed(h.upstream_owner, law_id=stage.LAW_ID)
    refs = stage._REQUESTS[request]
    context = stage._raw_context(request, refs, stage._ready())
    context.atoms = refs[0].api._independent_atoms
    context.checker = (context.atoms, context.atoms.__code__, context.atoms.__globals__)
    context.metadata = tuple(
        (name, function, context.atoms(function))
        for name, function in vars(stage).items()
        if type(function) is FunctionType and function.__globals__ is vars(stage)
    )
    context.parent_claim = getattr(stage.previous, stage.PARENT_CLAIM)
    context.parent_check = getattr(stage.previous, stage.PARENT_CHECK)
    durations, events = {}, {}
    stage._ACTIVE.append(context)
    try:
        for name in ("_acquire", "_namespace", "_binding", "_snapshot", "_graph", "_epoch"):
            start = time.monotonic()
            value = getattr(stage, name)(context)
            durations[name] = time.monotonic() - start
            if name == "_binding":
                context.bindings = value
        prior = sys.getprofile()

        def counted(frame, event, arg):
            key = (event, frame.f_code.co_name)
            events[key] = events.get(key, 0) + 1
            if prior is not None:
                prior(frame, event, arg)

        try:
            sys.setprofile(counted)
            stage._binding(context)
        finally:
            sys.setprofile(prior)
        assert not context.objects and context.phase is None
        assert all(
            getattr(stage, name).__code__ not in context.allowed_codes
            for name in ("_guard", "_make", "_invoke")
        )
    finally:
        assert stage._ACTIVE.pop() is context
        context.active = False
    software.snapshot.write_json(
        tmp_path / "namespace-epoch-cost.json",
        dict(
            durations=durations,
            original_helpers=len(context.allowed_functions),
            source_objects_allocated=0,
            full_metadata_functions=len(context.metadata),
            binding_profile_events=sum(events.values()),
            binding_event_roster=tuple((*key, value) for key, value in events.items()),
        ),
    )


@pytest.mark.parametrize(
    "selection, seconds, allowed",
    [
        ("ordinary-blocked-control", 480, True),
        (software.INTEGRATION_SELECTIONS[0], 1800, True),
        (software.INTEGRATION_SELECTIONS[1], 1800, True),
        ("ordinary-blocked-control", 1800, False),
        (software.INTEGRATION_SELECTIONS[0], True, False),
        (software.INTEGRATION_SELECTIONS[0], 1801, False),
    ],
)
def test_dynamics_setup_long_envelope_cannot_widen_ordinary_or_unknown_work(
    selection, seconds, allowed
):
    if allowed:
        assert software._integration_policy(selection, seconds) == seconds
    else:
        with pytest.raises(ValueError):
            software._integration_policy(selection, seconds)


def test_dynamics_issued_public_INIT_pilot_has_no_hydrated_or_registry_injected_owner(
    issued_synthetic_init, tmp_path
):
    h = issued_synthetic_init
    assert h.owner.phase is h.context.phase
    assert h.owner.trial is h.context.trial and h.context.trial.source_completed is True
    assert h.context.claim.record is h.context.parameter_record
    assert stage._FORWARDED.get(h.owner) is None
    for name in ("_guard", "_make", "_invoke", "_dynamics_route", "_dynamics_wrapper_guard"):
        assert getattr(stage, name).__code__ not in h.context.allowed_codes
    assert all(fn in h.context.allowed_functions for fn in h.context.native_functions)
    software.snapshot.write_json(
        tmp_path / "issued-public-synthetic-INIT.json",
        dict(
            public_entry_points=("from_seed", "prepare", "_authority"),
            actual_production_InitOwner_type=True,
            constructor_runtime_factory_used=True,
            exact_same_p_cells_callback=True,
            seams=h.seams,
            native_parent_or_constructor_or_scientific_credit=False,
        ),
    )


@pytest.fixture
def issued_synthetic_dynamics(issued_synthetic_init, monkeypatch):
    """Public consumer + real parent claim/lease/wrapper routing, synthetic bodies."""
    h = issued_synthetic_init

    def namespace_synthetic(context):
        original = h.factories["Simulator"]
        functions = {name: getattr(original, name) for name in dynamics.METHODS}

        def no_gap(*args, **kwargs):
            raise AssertionError("No gap factory authorized in this synthetic input")

        context.original_globals = h.namespace
        context.private = dict(h.namespace, Gap_Junction=no_gap)
        context.gap_factory = h.namespace["Gap_Junction"]
        context.gap_constructor, context.numpy = no_gap, np
        context.methods = dict(
            functions,
            init_dynamics=FunctionType(
                functions["init_dynamics"].__code__, context.private, "init_dynamics"
            ),
        )
        context.native_functions, context.helper_functions = tuple(functions.values()), ()
        context.native_delegates = {name: functions[name] for name in stage.DYNAMICS_HELPERS}
        context.sim_wrappers = {
            name: vars(type(context.sim))[name] for name in stage.DYNAMICS_HELPERS
        }
        context.helpers, context.gap_bodies = {}, {}
        context.allowed_codes = frozenset(
            function.__code__ for function in context.methods.values()
        )
        context.expected_body = context.methods["init_dynamics"].__code__
        context.body_functions = {
            function.__code__: function for function in context.methods.values()
        }

        def held_full_body():
            raise AssertionError("The entire native dynamics body remains forbidden")

        context.full_body = held_full_body.__code__

    monkeypatch.setattr(dynamics, "_ready", lambda: None)
    monkeypatch.setattr(
        dynamics, "source_plan", lambda: dict(law=dynamics.LAW_ID, synthetic_not_native=True)
    )
    monkeypatch.setattr(dynamics, "_namespace", namespace_synthetic)
    monkeypatch.setenv(dynamics.RELEASE, "1")
    h.dynamics_request = dynamics.from_init(h.owner, law_id=dynamics.LAW_ID)
    h.prior_trial = h.context.trial
    return h


def test_dynamics_issued_joint_public_chain_preserves_original_phase_and_once_only_epoch(
    issued_synthetic_dynamics, tmp_path
):
    h = issued_synthetic_dynamics
    child_owner = dynamics.prepare(h.dynamics_request, enabled=True)
    child = dynamics._authority(child_owner)
    assert stage._FORWARDED[h.owner] is child and child.parent is h.context
    assert child.phase is h.context.phase and child.p is h.p and child.cells is h.cells
    assert child.callback is h.callback and child.sim is h.context.phase.sim
    assert child.parent_trial is h.prior_trial and h.context.trial is h.prior_trial
    assert len(child.helper_invocations) == len(child.helper_returns) == 3
    assert child.ion_order == ("Na", "K")
    assert stage._check_init_dynamics_prelude_authority(child) is h.context
    with pytest.raises(stage.InitRejected) as consumed:
        stage._authority(h.owner)
    assert consumed.value.stage == "forwarded"
    with pytest.raises(dynamics.DynamicsRejected):
        dynamics.prepare(h.dynamics_request, enabled=True)
    software.snapshot.write_json(
        tmp_path / "public-issued-synthetic-chain.json",
        dict(
            actual_production_entry_points=("from_seed", "prepare", "from_init", "prepare"),
            public_InitOwner_and_PreludeOwner_issuers_used=True,
            no_owner_constructor_cast_or_registry_injection=True,
            exact_p_phase_cells_simulator_callback=True,
            helper_order=tuple(row["name"] for row in child.helper_invocations),
            once_only_epoch=True,
            seams=(
                *h.seams,
                "synthetic dynamics namespace/bodies; production observers/dispatch/sealing",
            ),
            native_parent_body_operator_RNG_or_scientific_credit=False,
        ),
    )
