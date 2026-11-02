"""Prepared blocked controls. Not executed by source-only development.

No genuine positive parent is synthesized. Source compilation, refusal paths
and observation/data-association helpers are checked independently; a future
positive continuity run requires Root's actual constants/handoff authority.
"""

import ast
import builtins
from types import FunctionType, ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_parameter_load_remainder as stage
from tests.unit import test_betse_native_parameter_initializer_constants as inherited
from validation.betse import betse_native_parameter_load_remainder_software as runner
from validation.betse.betse_native_single_cell_core_synthetic import SyntheticCaptureFailure

blocked = inherited.blocked
prevent_reference_execution = inherited.prevent_reference_execution


def test_exact_tail_profile_branches_and_helper_source_without_execution():
    plan = stage.source_plan()
    assert plan["statement_slice"] == (203, 218) and plan["source_lines"] == (1127, 1154)
    assert plan["load_cursor"] == 218 and plan["replaces"] == ("wsx", "wsy")
    assert len(plan["tail_stores"]) == 14 and len(plan["profile_union"]) == 24
    assert tuple(row[0] for row in plan["profiles"]) == stage.PROFILE_NAMES
    assert plan["profile_lines"] == (1265, 1496) and plan["balance_lines"] == (1569, 1605)
    assert (
        not plan["native_bodies_copied_or_rewritten"] and not plan["public_module_globals_patched"]
    )
    assert not plan["material_phase_world_science_admitted"]
    _, _, _, tail, _, _ = stage._source()
    assert [node.targets[0].attr for node in tail[:5]] == ["d_cell", "nx", "ny", "wsx", "wsy"]
    assert all("vol_env" not in ast.unparse(node) for node in tail)


def _compiled_shape():
    module = ModuleType("conditional-original-parameter-namespace")
    vars(module)["__builtins__"] = vars(builtins)

    def forbidden(self):
        raise AssertionError("Source compilation is not permission to run")

    original = FunctionType(forbidden.__code__, vars(module), "load")
    context = SimpleNamespace(
        parent=SimpleNamespace(function=original), api=SimpleNamespace(namespace=vars(module))
    )
    return module, context


def test_compile_transports_actual_iu_and_keeps_original_tail_ast():
    module, context = _compiled_shape()
    function = stage._compile(context)
    path, cls, _, selected, _, _ = stage._source()
    transport = ast.parse("iu = kwargs[" + repr(stage.LOCAL_KEY) + "]").body[0]
    stage.prefix.parameters.inherited._method(cls, "load").body = [transport, *selected]
    expected = stage.prefix.parameters._method_code(cls, "load", str(path))
    assert stage.prefix.parameters.inherited._code(
        function.__code__
    ) == stage.prefix.parameters.inherited._code(expected)
    assert function.__globals__ is vars(module)
    assert function.__builtins__ is context.parent.function.__builtins__
    assert (
        "_load_ion_profile" in function.__code__.co_names
        and stage.LOCAL_KEY in function.__code__.co_consts
    )


@pytest.mark.parametrize("mode", ["valid", "code", "namespace", "cached-builtins", "defaults"])
def test_original_helper_correspondence_rejects_static_drift_without_call(mode):
    module, _ = _compiled_shape()
    path, _, _, _, _, node = stage._source()
    code = stage.previous.previous.boundary._code(node, str(path), node.name)
    namespace = vars(module)
    function = FunctionType(code, namespace, node.name)
    if mode == "code":
        function.__code__ = (lambda a, b: None).__code__
    elif mode == "namespace":
        function = FunctionType(code, dict(namespace), node.name)
    elif mode == "cached-builtins":
        namespace["__builtins__"] = dict(vars(builtins))
        function = FunctionType(code, namespace, node.name)
        namespace["__builtins__"] = vars(builtins)
    elif mode == "defaults":
        function.__defaults__ = ()
    if mode == "valid":
        assert stage._canonical(function, code, namespace)
    else:
        with pytest.raises(ValueError):
            stage._canonical(function, code, namespace)


@pytest.mark.parametrize("mode", ["default", "integer", "local", "constants", "law"])
def test_gate_refuses_before_hook_or_parameter_work(monkeypatch, mode):
    for name in (
        stage.RELEASE,
        stage.previous.RELEASE,
        stage.previous.previous.RELEASE,
        stage.previous.previous.mod.RELEASE,
    ):
        monkeypatch.setenv(name, "1")
    if mode in ("local", "constants"):
        monkeypatch.setenv(stage.RELEASE if mode == "local" else stage.previous.RELEASE, "0")
    enabled = False if mode == "default" else 1 if mode == "integer" else True

    def forbidden():
        raise AssertionError("Hook must not be reached")

    monkeypatch.setattr(stage, "_hook", forbidden)
    with pytest.raises(stage.LoadRejected) as caught:
        stage.complete_load(
            None, law_id="wrong" if mode == "law" else stage.LAW_ID, enabled=enabled
        )
    assert caught.value.stage == ("law" if mode == "law" else "release")


def test_missing_predecessor_hook_is_executable_prework_refusal(monkeypatch):
    for name in (
        stage.RELEASE,
        stage.previous.RELEASE,
        stage.previous.previous.RELEASE,
        stage.previous.previous.mod.RELEASE,
    ):
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(stage, "HANDOFF_PRODUCER_SHA256", None)
    before = len(stage._CONSUMED)
    with pytest.raises(stage.LoadRejected) as caught:
        stage.complete_load(None, law_id=stage.LAW_ID, enabled=True)
    assert caught.value.stage == "predecessor_handoff" and len(stage._CONSUMED) == before


def test_raw_helper_return_survives_observer_copy_failure(monkeypatch):
    context = SimpleNamespace(raw_return=None, raw_returns=[], returns={"balance": []}, locals={})
    frame, value = object(), (object(), object())
    primary = SyntheticCaptureFailure("metadata copy refused")

    def bad(frame):
        raise primary

    monkeypatch.setattr(stage, "_copy_locals", bad)
    with pytest.raises(SyntheticCaptureFailure) as caught:
        stage._returned(context, "balance", frame, value)
    assert caught.value is primary and context.raw_return == ("balance", frame, value)
    assert context.raw_returns[0][2] is value and context.returns["balance"][0] is value


@pytest.mark.parametrize("mode", ["valid", "helper-edge", "roster", "volume", "selector"])
def test_output_association_helper_requires_complete_original_data_graph(mode):
    # A data-check fixture, never an issued parameter/WorldReady owner.
    plan = stage.source_plan()
    members = tuple((name, object()) for name in stage.PROFILE_NAMES)
    fields = {"vol_env": object(), "wsx": object(), "wsy": object()}
    before = tuple(fields)
    volume = fields["vol_env"]
    profile_fields = plan["profiles"][0][1]
    for name in (*plan["tail_stores"], *profile_fields):
        if name not in fields:
            fields[name] = object()
    a, b, c, d = object(), object(), object(), object()
    fields.update(conc_env_m=a, z_M_env=b, cM_cell=c, z_M_cell=d)
    p = SimpleNamespace(**fields)
    base, internal = object(), {}
    context = SimpleNamespace(
        p=p,
        api=SimpleNamespace(members=members, base=base),
        plan=plan,
        before_names=before,
        original_volume=volume,
        internal=internal,
        entries=dict(tail=1, ion=1, balance=2, ion_alias=1),
        returns=dict(tail=[None], ion=[None], balance=[(a, b), (c, d)], ion_alias=[members[0][1]]),
        locals=dict(ion=dict(base=base), tail=dict(iu=internal)),
    )
    if mode == "helper-edge":
        p.cM_cell = object()
    elif mode == "roster":
        p.foreign = 1
    elif mode == "volume":
        p.vol_env = object()
    elif mode == "selector":
        context.returns["ion_alias"] = [object()]
    if mode == "valid":
        assert stage._outputs(context) == "BASIC"
    else:
        with pytest.raises(ValueError):
            stage._outputs(context)


def test_software_launch_is_held_before_packet_access(monkeypatch, tmp_path):
    monkeypatch.delenv(runner.SOFTWARE_RELEASE, raising=False)
    with pytest.raises(ValueError, match="remains held"):
        runner.software(tmp_path / "missing", tmp_path / "output")
    assert not (tmp_path / "output").exists()
