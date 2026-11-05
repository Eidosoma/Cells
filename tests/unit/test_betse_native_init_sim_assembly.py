"""Source/typed-reservation controls; no successful native parent is fabricated."""

import ast
import contextlib
from threading import RLock, get_ident
from types import CodeType, FunctionType, SimpleNamespace

import pytest

from cells.processes import betse_native_init_sim_assembly as stage
from tests.unit import test_betse_native_init_retained_world as guards
from validation.betse import betse_native_init_sim_assembly_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    function = FunctionType(
        guards.blocked.__wrapped__.__code__, dict(vars(guards), software=software, _RAW_GUARDS=[])
    )
    with contextlib.contextmanager(function)(request, tmp_path, monkeypatch):
        yield


class Foreign:
    def __getattribute__(self, name):
        raise AssertionError("No foreign owner/native attribute read")


@pytest.mark.parametrize(
    "role", ("phase", "phase_kludge", "phase_time", "report", "run_core", "handler", "cache")
)
def test_assembly_compiles_complete_original_context_without_source_evaluation(role):
    code = stage.source.code(role)
    path, owner, method = stage.source.METHODS[role]
    assert type(code) is CodeType and code.co_qualname == owner + "." + method
    assert code.co_filename == str(stage.source.NATIVE / path)
    unit = compile(
        (stage.source.NATIVE / path).read_bytes(),
        str(stage.source.NATIVE / path),
        "exec",
        dont_inherit=True,
    )
    cls = next(c for c in unit.co_consts if type(c) is CodeType and c.co_name == owner)
    actual = next(c for c in cls.co_consts if type(c) is CodeType and c.co_name == method)
    assert stage.preparation.observation._code(actual) == stage.preparation.observation._code(code)


def test_assembly_source_boundary_keeps_original_order_and_no_SIM_completion_claim():
    plan = stage.source_plan()
    assert plan["original"]["order"] == (
        "runner compatibility",
        "SimPhase(SIM,cells,current_p,sim,callbacks)",
        "sim.sim_info_report(phase)",
        "sim.run_sim_core(phase)",
    )
    assert not plan["SIM_iterations_or_checkpoint_continuity"]
    assert plan["endpoint"] == "after_SIM_constructor_before_sim_info_report_and_run_sim_core"
    constructor = stage.source.original.nodes()["phase_kludge"]
    stores = [
        n
        for n in ast.walk(constructor)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "dyna" for t in n.targets)
    ]
    assert len(stores) == 1


def test_assembly_import_roster_and_compile_metadata_do_not_decorate_or_invoke():
    sites = stage.source.import_sites()
    assert sites[("SimPhase", "__init__")] == "betse/science/phase/phasecls.py"
    assert sites[("TissueHandler", "__init__")] == "betse/science/tissue/tishandler.py"
    assert stage.source.import_code("SimPhase", "__init__") is stage.source.code("phase")
    assert not stage._IMPORTS and not stage._ISSUED


@pytest.mark.parametrize("law", (None, "", "other", 1))
def test_assembly_wrong_law_refuses_before_any_owner_or_native_use(law):
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.from_preparation(Foreign(), law_id=law)
    assert caught.value.stage == "law"


def test_assembly_missing_reviews_refuse_instead_of_receipt_or_cache_hydration():
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.from_preparation(Foreign(), law_id=stage.LAW_ID)
    assert caught.value.stage == "producer_review_held"


@pytest.mark.parametrize("enabled,flag", ((False, None), (True, None), (1, "1"), (True, "1")))
def test_assembly_prepare_and_original_import_are_both_explicitly_held(monkeypatch, enabled, flag):
    if flag is not None:
        monkeypatch.setenv(stage.RELEASE, flag)
    else:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    expected = "producer_review_held" if enabled is True and flag == "1" else "release"
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.prepare(Foreign(), enabled=enabled)
    assert caught.value.stage == expected
    with pytest.raises(stage.AssemblyRejected) as imported:
        with stage.observing_phase_import(enabled=enabled):
            pytest.fail("No native import/factory may run")
    assert imported.value.stage == expected


def test_assembly_owner_cannot_be_created_from_phase_dict_or_saved_metadata():
    with pytest.raises(TypeError):
        stage.SimAssemblyOwner()
    with pytest.raises(stage.AssemblyRejected) as caught:
        stage.run_core_boundary(dict(completed=True, phase="SIM"))
    assert caught.value.stage == "owner"
    with pytest.raises(TypeError):
        stage.terminal.SimReservation()
    with pytest.raises(stage.terminal.InitTerminalRejected):
        stage.terminal._sim_reservation(object.__new__(stage.terminal.SimReservation))


@pytest.mark.parametrize("failing", (False, True))
def test_assembly_metadata_invocations_retain_actual_attempt_and_primary_cause(failing):
    context, returned = SimpleNamespace(metadata_work=[]), object()
    primary, cause = ValueError("source metadata refusal"), OSError("source cause")

    def run():
        if failing:
            raise primary from cause
        return returned

    if failing:
        with pytest.raises(ValueError) as caught:
            stage._metadata(context, "metadata only", run)
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert stage._metadata(context, "metadata only", run) is returned
    assert context.metadata_work == [
        dict(sequence=0, call="metadata only", status="failed" if failing else "returned")
    ]


def test_assembly_retained_view_is_only_metadata_and_never_relabels_an_INIT_phase():
    old = SimpleNamespace(
        phase=object(), p=object(), sim=object(), cells=object(), objects=(("sim", object()),)
    )
    view = stage._retained_view(old)
    assert view is not old and view.phase is old.phase and view.p is old.p
    assert view.sim is old.sim and view.cells is old.cells and view.objects is old.objects
    assert view.permissions == ((old.sim, frozenset(("dyna",))),)
    assert view.graph_fields is not getattr(old, "graph_fields", None)
    assert not stage._ISSUED


def _reservation_model():
    # Private registry-shaped metadata model; never insert an owner into the
    # real terminal/assembly registries or execute any native phase source.
    class MetadataOwner:
        pass

    owner, trial = MetadataOwner(), object()
    parent = SimpleNamespace(trial=trial, active=False, invalid=False)
    issued = {owner: (parent, trial)}
    reservations, retired, checks = {}, {}, []

    def authority(actual):
        assert actual is owner
        checks.append(actual)
        return parent

    namespace = dict(
        vars(stage.terminal),
        InitTerminalOwner=MetadataOwner,
        _ISSUED=issued,
        _SIM_RESERVATIONS=reservations,
        _SIM_RETIRED=retired,
        _LOCK=RLock(),
        _ACTIVE=[],
        _authority=authority,
    )
    reserve = FunctionType(stage.terminal.reserve_for_sim.__code__, namespace)
    validate = FunctionType(stage.terminal._sim_reservation.__code__, namespace)
    return SimpleNamespace(
        owner=owner,
        trial=trial,
        parent=parent,
        issued=issued,
        retired=retired,
        reservations=reservations,
        reserve=reserve,
        validate=validate,
        checks=checks,
    )


def test_assembly_private_retirement_model_is_irreversible_without_state_mutation(monkeypatch):
    model = _reservation_model()
    monkeypatch.setenv(stage.terminal.SIM_RESERVATION_RELEASE, "1")
    token = model.reserve(
        model.owner,
        expected_trial=model.trial,
        law_id=stage.terminal.SIM_RESERVATION_LAW,
        enabled=True,
    )
    assert model.validate(token) == (model.parent, model.trial)
    with pytest.raises(stage.terminal.InitTerminalRejected) as caught:
        model.reserve(
            model.owner,
            expected_trial=model.trial,
            law_id=stage.terminal.SIM_RESERVATION_LAW,
            enabled=True,
        )
    assert caught.value.stage == "consumed" and model.checks == [model.owner]
    assert not model.parent.active and not model.parent.invalid
    assert not stage.terminal._SIM_RESERVATIONS and not stage._ISSUED


@pytest.mark.parametrize("drift", ("retired", "issued", "trial", "active", "invalid", "thread"))
def test_assembly_private_retirement_metadata_drift_cannot_validate_closed_parent(
    monkeypatch, drift
):
    model = _reservation_model()
    monkeypatch.setenv(stage.terminal.SIM_RESERVATION_RELEASE, "1")
    token = model.reserve(
        model.owner,
        expected_trial=model.trial,
        law_id=stage.terminal.SIM_RESERVATION_LAW,
        enabled=True,
    )
    if drift == "retired":
        model.retired.clear()
    elif drift == "issued":
        model.issued[model.owner] = (model.parent, model.trial)
    elif drift == "trial":
        model.parent.trial = object()
    elif drift == "active":
        model.parent.active = True
    elif drift == "invalid":
        model.parent.invalid = True
    else:
        row = model.reservations[token]
        model.reservations[token] = (row[0], row[1], get_ident() + 1)
    with pytest.raises(stage.terminal.InitTerminalRejected) as caught:
        model.validate(token)
    assert caught.value.stage == "reservation"


def test_assembly_default_retirement_gate_precedes_foreign_owner_or_source_read(monkeypatch):
    monkeypatch.delenv(stage.terminal.SIM_RESERVATION_RELEASE, raising=False)
    with pytest.raises(stage.terminal.InitTerminalRejected) as caught:
        stage.terminal.reserve_for_sim(
            Foreign(),
            expected_trial=Foreign(),
            law_id=stage.terminal.SIM_RESERVATION_LAW,
            enabled=True,
        )
    assert caught.value.stage == "release"
