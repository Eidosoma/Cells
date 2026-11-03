"""Native-blocked same-instance integration controls; no scientific admission."""

import ast
import os
from contextlib import contextmanager
from types import FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_phase_assembly as assembly
from cells.processes import betse_native_seed_init_core as core
from cells.processes import betse_native_seed_world_geometry as geometry
from cells.processes import betse_native_seed_world_poisson as poisson
from cells.processes import betse_native_world_phase_construction as world
from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_core_integration_software as software

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit native-blocked integration software release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    namespace = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    fn = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("operator_or_RNG")
        raise AssertionError("No actual operator/RNG execution")

    try:
        with contextmanager(fn)(request, tmp_path), monkeypatch.context() as patch:
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
            ):
                patch.setattr(np.random, name, forbidden)
            try:
                yield
            finally:
                software.snapshot.write_json(
                    tmp_path / "solver-RNG-blocked.json", dict(attempted=attempts)
                )
            assert attempts == []
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


def clone(fn, **values):
    result = FunctionType(
        fn.__code__, dict(fn.__globals__, **values), fn.__name__, fn.__defaults__, fn.__closure__
    )
    result.__kwdefaults__ = fn.__kwdefaults__
    return result


def test_contract_source_modes_and_every_new_provider_gate_remain_closed():
    assert poisson.FLUX_OPERATORS == ("original", "disabled")
    assert poisson.PARENT_SOURCE_SHA256 is poisson.PARENT_REVIEW_SHA256 is None
    assert core.COORDINATOR_SOURCE_SHA256 is core.COORDINATOR_REVIEW_SHA256 is None
    assert world.SEED_POISSON_SOURCE_SHA256 is world.SEED_INIT_CORE_INTERFACE_SHA256 is None
    assert len(software.OWNED) == len(set(software.OWNED)) == 9
    assert set(core.METHODS) == {"init_core", "initDenv"}
    assert len(poisson.TAIL_FIELDS) == 6


@pytest.mark.parametrize(
    "entry", ["geometry_request", "world_request", "geometry_prepare", "core_prepare"]
)
def test_unadopted_routes_refuse_before_foreign_owner_or_native_body(entry):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("No foreign owner access")

    with pytest.raises(ValueError):
        if entry == "geometry_request":
            poisson.from_geometry(Foreign(), law_id=poisson.LAW_ID, flux_operator="original")
        elif entry == "world_request":
            core.from_world(Foreign(), law_id=core.LAW_ID)
        elif entry == "geometry_prepare":
            poisson.prepare(Foreign(), enabled=True)
        else:
            core.prepare(Foreign(), enabled=True)


@pytest.mark.parametrize("field", [None, "source", "review", "body"])
def test_core_two_slot_binding_has_no_source_hash_cycle_and_rejects_other_byte_changes(field):
    raw = (software.ROOT / "src/cells/processes/betse_native_seed_init_core.py").read_bytes()
    identity, refs = world._seed_core_binding(raw)
    assert refs == (("COORDINATOR_SOURCE_SHA256", None), ("COORDINATOR_REVIEW_SHA256", None))
    changed = raw
    if field == "source":
        changed = raw.replace(
            b"COORDINATOR_SOURCE_SHA256 = None",
            b"COORDINATOR_SOURCE_SHA256 = '" + b"a" * 64 + b"'",
            1,
        )
    elif field == "review":
        changed = raw.replace(
            b"COORDINATOR_REVIEW_SHA256 = None",
            b"COORDINATOR_REVIEW_SHA256 = '" + b"b" * 64 + b"'",
            1,
        )
    elif field == "body":
        changed = raw + b"\n# distinct non-slot source witness\n"
    current, _ = world._seed_core_binding(changed)
    assert (current == identity) is (field != "body")


@pytest.mark.parametrize("which", ["geometry", "world"])
def test_public_consumed_owner_refuses_before_any_stale_numeric_check(which):
    module, name, marker = (
        (geometry, "GeometryOwner", "poisson")
        if which == "geometry"
        else (poisson, "PoissonOwner", "core")
    )
    owner = object.__new__(getattr(module, name))  # Negative unissued/retired witness only.
    context = NS(trial=object())
    setattr(context, marker, object())
    fn = clone(
        module._authority,
        _ISSUED={owner: context},
        _FORWARDED={owner: getattr(context, marker)},
        _check=lambda value: (_ for _ in ()).throw(AssertionError("Stale validator")),
    )
    with pytest.raises(ValueError) as caught:
        fn(owner)
    assert caught.value.stage == "forwarded" and caught.value.trial is context.trial


@pytest.mark.parametrize("changed", [False, True])
def test_actual_simulator_projection_retains_original_values_and_never_substitutes_saved_cache(
    changed,
):
    original = np.array([1.0, -0.0])
    sim = NS(dyna=object(), retained=original)
    phase = NS(sim=sim)
    parent = NS(phase=phase)
    authority = NS(sim=sim, original_sim_fields=("dyna", "retained"))
    projected = clone(world._world_sim_fields, _world_core_context=lambda value: authority)
    before = projected(parent, sim)
    sim.created_by_body = np.ones(2)
    if changed:
        sim.retained = np.array([1.0, -0.0])
    result = projected(parent, sim)
    assert tuple(result) == ("dyna", "retained") and result["dyna"] is sim.dyna
    assert result["retained"] is sim.retained
    assert (result["retained"] is before["retained"]) is not changed
    assert tuple(vars(sim)) == ("dyna", "retained", "created_by_body")


def test_actual_assembly_native_call_reaches_only_same_core_route_and_keeps_dispatch_frame():
    context, actual, delegate, phase = (
        NS(active=False, world_mode=assembly.WORLD_MODE),
        object(),
        object(),
        object(),
    )
    calls = []

    def dispatch(current, label, body, *args, **kwargs):
        calls.append((current, label, body, args, kwargs))
        return "metadata_return"

    api = NS(
        _world_has_seed_core_route=lambda value: value is context,
        _world_dispatch_seed_core=dispatch,
    )
    call = clone(assembly._native_call, _guard=lambda value: None, _world_api=lambda: api)
    assert call(context, "Simulator.init_core", delegate, actual, phase) == "metadata_return"
    assert calls == [(context, "Simulator.init_core", delegate, (actual, phase), {})]


def test_original_literal_sources_are_readonly_and_original_and_disabled_callers_remain_distinct():
    assert core.source_plan()["stop_before"].startswith("phase.dyna.init_profiles")
    for mode in poisson.FLUX_OPERATORS:
        plan = poisson.source_plan(flux_operator=mode)
        assert plan["known_original_flux_issue_not_repaired"] is True
    definitions = {
        node.name: node
        for node in ast.parse(software.ROOT.joinpath(software.SOURCE).read_bytes()).body
        if isinstance(node, ast.FunctionDef)
    }
    assert "context.parent_claim(" in ast.unparse(definitions["prepare"])
    assert core.PROPOSED_CLAIM == "_claim_for_seed_init_core"
    assert "_check_fields" in ast.unparse(definitions["_check"])


def _registry_metadata(which):
    """Private relation witnesses, never an issued phase/owner or a positive pilot."""
    owner, trial = object(), object()
    p, cells, mesh, mask, rng, grid, sim = (NS() for _ in range(7))
    phase = NS(p=p, cells=cells, sim=sim)
    shared = dict(phase=phase, p=p, cells=cells, mesh=mesh, mask=mask, rng=rng, grid=grid)
    parent = NS(
        **shared, owner=owner, trial=trial, active=False, invalid=False, thread=core.get_ident()
    )
    child = NS(**shared, parent=parent, invalid=False, thread=parent.thread)
    if which == "geometry":
        request = poisson.Request(owner, "parent", "source", "original", "request")
        child.entries = {"Grid.makeLaplacian": poisson._grid_call}
        module = NS(Request=poisson.Request, _grid_call=poisson._grid_call)
        parent.poisson = child
        router, key = geometry._poisson_route, "_world_seed_poisson_api"
    else:
        request = core.Request(owner, "parent", "source", "original", "request")
        child.sim = sim
        child.entries = dict(wrapper_guard=core._wrapper_guard, dispatch=core._dispatch)
        module = NS(
            Request=core.Request, _wrapper_guard=core._wrapper_guard, _dispatch=core._dispatch
        )
        parent.core = child
        router, key = poisson._seed_core_route, "_seed_init_core_api"
    child.request, child.refs = request, (parent, trial, object())
    module._REQUESTS, module._CONSUMED, module._RETIRED = (
        {request: child.refs},
        {request: child},
        {owner: child},
    )
    issued, forwarded = {owner: parent}, {owner: child}
    api = NS(**{key: lambda: module})
    calls = []

    def forbidden(*args):
        calls.append(args)
        raise AssertionError("No stale cache validator or native delegate")

    fn = clone(
        router,
        _ready=lambda: api,
        _ISSUED=issued,
        _FORWARDED=forwarded,
        _check=forbidden,
        _snapshot=forbidden,
    )
    return NS(
        parent=parent,
        child=child,
        owner=owner,
        request=request,
        module=module,
        issued=issued,
        forwarded=forwarded,
        route=fn,
        calls=calls,
    )


@pytest.mark.parametrize("which", ["geometry", "world"])
@pytest.mark.parametrize(
    "mutation", [None, "issued", "forwarded", "consumed", "request", "caller", "entry", "trial"]
)
def test_registry_routes_keep_exact_retirement_and_reference_edges_without_old_cache_validation(
    which, mutation
):
    h = _registry_metadata(which)
    if mutation == "issued":
        h.issued.pop(h.owner)
    elif mutation == "forwarded":
        h.forwarded[h.owner] = NS()
    elif mutation == "consumed":
        h.module._CONSUMED[h.request] = NS()
    elif mutation == "request":
        h.module._REQUESTS[h.request] = tuple([*h.child.refs])
    elif mutation == "caller":
        h.child.cells = NS(**vars(h.parent.cells))
    elif mutation == "entry":
        h.child.entries[next(iter(h.child.entries))] = lambda *args: None
    elif mutation == "trial":
        h.parent.trial = object()
    if mutation is None:
        child, module = h.route(h.parent)
        assert child is h.child and module is h.module
    else:
        with pytest.raises(ValueError):
            h.route(h.parent)
    assert h.calls == []


@pytest.mark.parametrize(
    "mutation", [None, "before_entry", "remove_old", "reorder_old", "entry_roster", "trial"]
)
def test_core_registry_projection_permission_never_authorizes_premature_or_reordered_fields(
    mutation,
):
    h = _registry_metadata("world")
    ctx = h.child
    ctx.sim.dyna, ctx.sim.retained = object(), np.array([1.0, -0.0])
    ctx.original_sim_fields = tuple(vars(ctx.sim))
    ctx.entered = []
    if mutation == "before_entry":
        ctx.sim.new_field = object()
    elif mutation == "remove_old":
        del ctx.sim.retained
    elif mutation == "reorder_old":
        value = ctx.sim.dyna
        del ctx.sim.dyna
        ctx.sim.dyna = value
    elif mutation == "entry_roster":
        ctx.entered[:] = ["initDenv"]
    elif mutation == "trial":
        ctx.parent.trial = object()
    fn = clone(
        core._check_fields,
        _bootstrap=lambda value: None,
        _REQUESTS=h.module._REQUESTS,
        _CONSUMED=h.module._CONSUMED,
        _RETIRED=h.module._RETIRED,
    )
    if mutation is None:
        assert fn(ctx) == ctx.original_sim_fields
        ctx.entered.append("init_core")
        ctx.sim.new_field = object()
        assert fn(ctx) == (*ctx.original_sim_fields, "new_field")
    else:
        with pytest.raises(ValueError):
            fn(ctx)


@pytest.mark.parametrize("mutation", [None, "method", "actual"])
def test_grid_forwarding_checks_actual_method_and_grid_before_any_dispatch(mutation):
    context, child, delegate, wrapper = (
        NS(grid=object(), poisson=object()),
        NS(),
        object(),
        object(),
    )
    calls = []

    def reject(*args):
        raise ValueError("Unowned grid call")

    def dispatch(*args):
        calls.append(args)
        return "metadata_return"

    child.entries = {"Grid.makeLaplacian": dispatch}
    fn = clone(
        geometry._grid_call,
        _poisson_route=lambda value: (child, NS(_reject=reject)),
        _guard=lambda value: (_ for _ in ()).throw(AssertionError("Stale geometry guard")),
    )
    actual = object() if mutation == "actual" else context.grid
    name = "cell_grid" if mutation == "method" else "makeLaplacian"
    args, kwargs = (), {"bound": dict.fromkeys(("N", "S", "E", "W"), "value")}
    if mutation is None:
        assert fn(context, name, delegate, actual, args, kwargs, wrapper) == "metadata_return"
        assert calls == [(child, delegate, actual, args, kwargs, wrapper)]
    else:
        with pytest.raises(ValueError):
            fn(context, name, delegate, actual, args, kwargs, wrapper)
        assert calls == []


@pytest.mark.parametrize("which", ["geometry", "world"])
def test_retirement_source_order_and_factored_check_preserve_sticky_epoch_before_fallible_sealing(
    which,
):
    module, claim, check, marker = (
        (geometry, "_claim_for_world_poisson", "_check_world_poisson_authority", "poisson")
        if which == "geometry"
        else (poisson, "_claim_for_seed_init_core", "_check_seed_init_core_authority", "core")
    )
    text = (software.ROOT / "src" / (module.__name__.replace(".", "/") + ".py")).read_bytes()
    nodes = {n.name: n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    body = ast.unparse(nodes[claim])
    assert body.index("parent." + marker + " = transition") < body.index("_FORWARDED[owner]")
    assert body.index("_FORWARDED[owner]") < body.index("_check(parent)")
    assert "parent.invalid = transition.invalid = True" in body
    assert not any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id == "_authority"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "_authority"
        )
        for node in ast.walk(nodes[check])
    )


def test_coordinator_plan_declares_exact_closed_poisson_and_core_routes():
    plan = world.source_plan()
    assert plan["seed_poisson"]["flux_modes"] == ("original", "disabled")
    assert plan["seed_poisson"]["source"] is plan["seed_poisson"]["review"] is None
    current = plan["seed_init_core"]
    assert current["interface"] is current["review"] is current["coordinator_review"] is None
    assert current["back_reference_slots"] == (
        "COORDINATOR_SOURCE_SHA256",
        "COORDINATOR_REVIEW_SHA256",
    )
    assert current["released"] is plan["seed_poisson"]["released"] is False


@pytest.mark.parametrize(
    "name", ["_world_voronoi_lifecycle_api", "_world_seed_geometry_api", "_world_geometry_context"]
)
def test_reached_ancestor_router_code_is_retained_even_when_function_identity_stays_equal(name):
    """Binding reducer only: no native owner, stage issuer or checker is mocked into admission."""
    calls = []

    def unused(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Binding capture must never enter a stage/helper body")

    class ClaimShape:
        parameters = property(unused)
        record = property(unused)
        check = unused

    hooks = {
        key: unused
        for key in (world.CONSTRUCT_HOOK, world.CHECK_HOOK, world.SEAL_HOOK, world.CHECK_SEAL_HOOK)
    }
    api = NS(
        key=NS(
            construction=unused,
            validate_closed_seed=unused,
            WorldConstructionClaim=ClaimShape,
            ClosedSeedRecord=object,
        ),
        parameters=NS(validate_completed_history=unused, WorldReadyParametersOwner=object),
        callbacks=NS(_validate=unused),
        helpers=NS(_atoms=world._independent_atoms, literal=NS(_surface=lambda cls: ())),
        stages=(NS(**hooks, WORLD_MODE="metadata_only", _WORLD={}),),
    )
    context = NS(api=api, helper_authority=())
    original = getattr(world, name)
    helper = clone(original)
    reducer = clone(world._bindings, _check_helpers=lambda value: None, **{name: helper})
    before = reducer(context)

    def replacement():
        return None

    helper.__code__ = replacement.__code__
    after = reducer(context)
    assert any(value is helper for value in before) and any(value is helper for value in after)
    assert len(before) != len(after) or any(a is not b for a, b in zip(before, after, strict=True))
    assert (
        calls == []
        and getattr(world, name) is original
        and original.__code__ is not helper.__code__
    )


@pytest.mark.parametrize("released", [False, True])
def test_runner_authenticates_expected_image_before_importing_any_adapter_definition(
    tmp_path, released
):
    calls, primary = [], ValueError("Changed immutable manifest")
    software.snapshot.write_json(
        tmp_path / "inputs.json",
        dict(
            software_release_requested=released,
            snapshot_sha256="f" * 64,
            owned_files={},
        ),
    )

    def verify(root, *, manifest_sha256):
        calls.append((root, manifest_sha256))
        assert manifest_sha256 == "f" * 64
        raise primary

    def forbidden(name):
        calls.append(("import", name))
        raise AssertionError("No definition import before exact manifest/release authentication")

    child = clone(
        software.child,
        snapshot=NS(verify=verify),
        importlib=NS(import_module=forbidden),
    )
    with pytest.raises(ValueError) as caught:
        child(tmp_path, "unexecuted")
    if released:
        assert caught.value is primary and calls == [(software.ROOT, "f" * 64)]
    else:
        assert calls == [] and "release" in str(caught.value)
