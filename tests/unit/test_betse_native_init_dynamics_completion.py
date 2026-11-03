"""Source/closed-input controls; all actual INIT/draw/factory work is forbidden."""

import ast
import sys
from enum import Enum
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_dynamics_completion as stage
from tests.unit import test_betse_native_init_dynamics_prelude as inherited
from validation.betse import betse_native_init_dynamics_completion_software as runner


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    function = inherited._blocked_generator
    generator = FunctionType(
        function.__code__, dict(function.__globals__, stage=stage, runner=runner)
    )(request, tmp_path, monkeypatch)
    before, started, primary = (sys.getprofile(), sys.gettrace()), False, None
    failed = len(stage._FAILED)
    try:
        next(generator)
        started = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        drain = FunctionType(
            inherited.cleanup._drain_guard.__code__,
            dict(
                inherited.cleanup._drain_guard.__globals__,
                _write_failure_diagnostics=inherited._diagnostics,
            ),
        )
        drain(
            generator,
            started,
            tuple(stage._FAILED[failed:]),
            tmp_path,
            required_hooks=before,
            primary=primary,
        )


def test_original_whole_tail_order_and_rng_are_compiled_without_execution(tmp_path):
    plan = stage.source_plan()
    assert plan["extent"] == (809, 1012) and plan["original_tail_statements"] == 35
    assert plan["original_alias_reads"] == (778, 779) and not plan["prefix_replayed"]
    assert plan["full_module_compile_context"] and plan["mandatory_channel_rng_even_if_level_zero"]
    assert not plan["time_vector_solver_storage_updateV_pickle_or_completed_INIT_admission"]
    node = stage._node()
    text = ast.unparse(node)
    assert text.index("phase.dyna.init_profiles(phase)") < text.index("np.random.random(self.mdl)")
    assert text.index("np.random.random(self.mdl)") < text.index("p.channel_noise_level")
    assert text.index("self.cellso = cells") < text.index("phase.dyna.init_events(phase)")
    assert (
        text.index("phase.dyna.init_events(phase)")
        < text.index("self.ko_env")
        < text.index("self.cgj")
    )
    assert text.index("self.cgj") < text.index("self.fast_sim_init")
    assert "RandomState(" not in text and ".seed(" not in text
    assert "smooth_weight_mem" not in text and "self.initDenv" not in text
    code = stage._code()
    assert type(code) is CodeType and code.co_qualname == "Simulator.init_dynamics"
    assert code.co_filename == str(stage.NATIVE / stage.SIM_FILE)
    runner.snapshot.write_json(
        tmp_path / "source-only.json",
        dict(plan=plan, compiled_qualname=code.co_qualname, actual_original_helper_or_rng_calls=0),
    )


@pytest.mark.parametrize("mode", ["default", "integer", "environment"])
def test_source_and_rng_release_refuses_before_source_or_owner_access(monkeypatch, mode):
    monkeypatch.setenv(stage.RELEASE, "0" if mode == "environment" else "1")
    monkeypatch.setattr(
        stage, "_ready", lambda: pytest.fail("No runtime/owner access before release")
    )
    with pytest.raises(stage.CompletionRejected) as caught:
        stage.prepare(None, enabled=1 if mode == "integer" else mode != "default")
    assert caught.value.stage == "release"


def test_parent_and_tissue_adoption_remain_real_missing_prerequisites(monkeypatch):
    monkeypatch.setattr(
        stage.previous, "_authority", lambda value: pytest.fail("No arbitrary parent access")
    )
    with pytest.raises(stage.CompletionRejected) as caught:
        stage.from_prelude(None, law_id=stage.LAW_ID)
    assert caught.value.stage == "unbound"
    with pytest.raises(stage.CompletionRejected) as caught:
        stage.from_prelude(None, law_id="foreign")
    assert caught.value.stage == "law"


@pytest.mark.parametrize("value", [None, {}, NS(), object.__new__(stage.CompletionClaim)])
def test_record_namespace_and_unissued_claim_do_not_authorize_participation(value):
    with pytest.raises(stage.CompletionRejected):
        stage.validate_active(value, original_owner=None)
    with pytest.raises(stage.CompletionRejected):
        stage.failed_context(value)


class Solver(Enum):
    FULL = 1
    FAST = 2


@pytest.fixture
def declaration():
    """Only a domain-check declaration, never an issued phase/PreludeOwner."""
    p = NS(
        _run_sim=False,
        is_ecm=True,
        ions_dict={"Ca": 0},
        Ca_dyn=False,
        molecules_enabled=False,
        grn_enabled=False,
        deform_osmo=False,
        fluid_flow=False,
        deformation=False,
        solver_type=Solver.FULL,
        channel_noise_level=0.0,
    )
    return NS(p=p, phase=NS(kind=NS(name="INIT")), original_globals={"SolverType": Solver})


def test_ordinary_scope_accepts_declaration_without_executing_a_body_or_rng(declaration):
    stage._domain(declaration)
    assert declaration.p.channel_noise_level == 0.0


@pytest.mark.parametrize(
    "field",
    [
        "Ca",
        "molecules_enabled",
        "grn_enabled",
        "deform_osmo",
        "fluid_flow",
        "deformation",
        "FAST",
        "unknown_solver",
    ],
)
def test_actual_requested_unowned_branch_is_not_silently_disabled(declaration, field):
    p = declaration.p
    if field == "Ca":
        p.ions_dict["Ca"], p.Ca_dyn = 1, True
    elif field == "FAST":
        p.solver_type = Solver.FAST
    elif field == "unknown_solver":
        p.solver_type = object()
    else:
        setattr(p, field, True)
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._domain(declaration)
    assert caught.value.stage == "unavailable_branch"
    if field not in ("Ca", "FAST", "unknown_solver"):
        assert getattr(p, field) is True


@pytest.mark.parametrize("field,value", [("_run_sim", True), ("is_ecm", False), ("kind", "SEED")])
def test_actual_phase_and_ecm_boundary_are_not_relabelled(declaration, field, value):
    if field == "kind":
        declaration.phase.kind.name = value
    else:
        setattr(declaration.p, field, value)
    with pytest.raises(stage.CompletionRejected) as caught:
        stage._domain(declaration)
    assert caught.value.stage == "domain"


def test_participation_registry_check_is_distinct_from_recursive_full_audit():
    tree = ast.parse(open(stage.__file__).read())
    funcs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "_check(" not in ast.unparse(funcs["_active"])
    assert "_registry(context)" in ast.unparse(funcs["_active"])
    assert "context.tissue.validate_active" in ast.unparse(funcs["_check"])
    assert "record" not in ast.unparse(funcs["_active"])
    assert "observe" in stage.TISSUE_API and "validate_rng_call" in stage.TISSUE_API


def test_shared_observer_recipe_keeps_existing_guard_code_and_current_registry():
    context = NS()
    stage._observer_recipe(context)
    namespace = context.observer_namespace
    assert namespace["_ACTIVE"] is stage._ACTIVE
    assert namespace["_guard"].__code__ is stage.previous._guard.__code__
    assert namespace["_recover_hooks"].__code__ is stage.previous._recover_hooks.__code__
    assert namespace["_observe"] is stage._observe and namespace["_epoch"] is stage._epoch
    assert namespace["DynamicsRejected"] is stage.CompletionRejected
    assert namespace is not vars(stage.previous)
