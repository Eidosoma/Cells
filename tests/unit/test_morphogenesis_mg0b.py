"""MG0b driver: the independent reduced model and the resolved_pump_tissue@3 chain.

The reduced model reproduces the heredity pre-screen's slow states and, at
several off-steady voltages, the engine's own instantaneous membrane rate
(gates at steady state, same composition): it transcribes the same laws. The
chain definition parses as resolved_pump_tissue@3 with open-gated junctions.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np

from cells.core.specs import parse_spec
from cells.core.surface_pump_v3_spec import control_values
from cells.models import surface_pump_v3
from cells.models.registry import get_model
from validation.morphogenesis import mg0b_domain_wall as dw
from validation.morphogenesis import mg0b_theory as theory
from validation.tissue import surface_pump_v3_fixtures as fixtures

jax.config.update("jax_enable_x64", True)


def heredity_parameters():
    return theory.CellParameters(
        **{**vars(dw.cell_parameters()), "nav_availability": 1.0, "control_m_s": 0.0}
    )


def test_reduced_model_reproduces_prescreen_slow_states():
    states = theory.slow_states(heredity_parameters(), 0.0)
    assert len(states) == 3
    for (v, c), key in zip(states, ("H", "U", "D"), strict=True):
        vm, na, k, m, _ = fixtures.HEREDITY_STATES[key]
        assert abs(v - vm) < 1e-7, key
        np.testing.assert_allclose([c["Na"], c["K"], c["M"]], [na, k, m], rtol=1e-6)


def test_reduced_current_matches_engine_membrane_rate():
    """dV/dt = -I(V)/C at t = 0 for cells kicked off H with steady gates at the kick."""
    p = dw.cell_parameters()
    vm, na, k, m, _ = fixtures.HEREDITY_STATES["H"]
    voltages = [-0.075, -0.05, -0.035, -0.025]
    raw = dw.chain_definition(
        len(voltages),
        state=(vm, na, k, m),
        end_time=0.002,
        observation_times=[0.0, 0.002],
        control=((0.0, 0.5),),
        junction_m_s=0.0,
    )
    cells = raw["model"]["cells"]
    for i, v in enumerate(voltages):
        charge = fixtures.HEREDITY_CAPACITANCE_F * v
        cells[i]["fixed_charge_equivalent_fmol"] += (charge - cells[i]["initial_charge_C"]) / (
            fixtures.CHARGE_PER_FMOL
        )
        cells[i]["initial_charge_C"] = charge
        kir, nav = fixtures.steady_gates(v)
        for c in raw["model"]["channels"]:
            if c["id"] == f"kir_{i}":
                c["initial_gate"] = kir
            elif c["id"] == f"nav_{i}":
                c["initial_gate"] = nav
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(x[0] for x in controls))
    law = surface_pump_v3.readouts(state, control, layout, xp=np)
    rate = np.asarray(law.field.membrane_voltage_rate_V_s)[: len(voltages)]
    composition = dict(Na=na, K=k, M=m)
    expected = [
        -float(theory.current_A(p, composition, v, 0.5)) / p.capacitance_F for v in voltages
    ]
    np.testing.assert_allclose(rate, expected, rtol=2e-6)


def test_chain_definition_parses_with_open_gated_junctions():
    vm, na, k, m, _ = fixtures.HEREDITY_STATES["H"]
    raw = dw.chain_definition(
        5,
        state=(vm, na, k, m),
        end_time=0.4,
        observation_times=[0.0, 0.4],
        control=((0.0, 0.2), (0.2, 0.4)),
        junction_m_s=1e-8,
        written=(3, 4),
        no_control=(0,),
        anchored_d=(4,),
        junction_schedule=[(0.0, [1, 1, 1, 1]), (0.2, [1, 0, 1, 1])],
    )
    spec = parse_spec(raw)
    model = spec.model
    assert len(model.junctions) == 4
    assert all(j.minimum_open_fraction == 1.0 and j.initial_gate == 1.0 for j in model.junctions)
    laws = [c.kinetic_law for c in model.channels]
    assert laws.count(dw.NALEAK_LAW_ID) == 4 + 2 + 1
    assert spec.execution.channel_capacity == len(model.channels)
    p = dw.cell_parameters()
    g = theory.junction_conductance_S(
        p, dict(Na=na, K=k, M=m), dw.JUNCTION_AREA_M2, dict(Na=1e-8, K=1e-8, M=1e-8)
    )
    ratio = 3.0
    pj = dw.junction_permeability_for(ratio, g / 3.0, dict(Na=na, K=k, M=m), p)
    assert abs(pj / 1e-8 - 1) < 1e-12


# ---------------------------------------------------------------- judging

PROTOCOL = (
    Path(__file__).resolve().parents[2]
    / "validation/morphogenesis/protocols/mg0b_domain_wall_v1.json"
)
# Theory values of the registered protocol (dev-03-mg0b/theory.json).
THEORY = dict(
    u_maxwell=0.5640141230484589,
    composition_mM=dict(Na=8.600146455184671, K=141.50868488470016, M=15.122218545605358),
    fast_states_V=dict(H=-0.05945080753309749, U=-0.0401945648246295, D=-0.02425698436831133),
    slope_conductance_S=dict(H=4.1293884414327247e-11, D=7.553997372409677e-11),
    bistable_control_range=[0.3770832679975349, 0.6794743366336637],
    continuum_width_cells={
        "0.25": 1.49228452729611,
        "0.5": 2.110409017421682,
        "1.0": 2.98456905459222,
        "2.0": 4.220818034843364,
        "4.0": 5.96913810918444,
        "8.0": 8.441636069686728,
    },
)


def relay_run(protocol, t, *, window_s=2.0):
    """Stand-in for run_both: each cell a relay (D at u >= 0.7, H at u <= 0.35)."""
    v_h, v_d = t["fast_states_V"]["H"], t["fast_states_V"]["D"]
    state = np.zeros(protocol.n, dtype=bool)
    rows = []
    for s in protocol.observation_times():
        u = dw._step_value(protocol.control, s)
        for i in range(protocol.n):
            if i in protocol.anchored_d or (i in protocol.written and s >= protocol.write[-1][0]):
                state[i] = True
            elif i not in protocol.no_control and (u >= 0.7 or u <= 0.35):
                state[i] = u >= 0.7
        rows.append(np.where(state, v_d, v_h))
    vm = np.array(rows)
    info = dict(
        diagnostics_max=dict(max_energy_balance_relative=1e-5, max_global_charge_bound_ratio=0.1),
        max_cell_composition_drift_rel=0.0,
    )
    return vm, vm.copy(), info


def stub_parts(monkeypatch, tmp_path, *, failing=None):
    monkeypatch.setattr(dw, "run_both", relay_run)
    monkeypatch.setattr(dw, "critical_ratio", lambda t: 0.2977)
    if failing is not None:

        def fail(args):
            raise RuntimeError("refused")

        monkeypatch.setitem(dw.PARTS, failing, fail)
    args = SimpleNamespace(output=tmp_path, quick=True, _theory=copy.deepcopy(THEORY))
    results, failures = dw.run_parts(args, [p for p in dw.PARTS if p != "theory"])
    results["theory"] = copy.deepcopy(THEORY)
    return results, failures


def test_every_registered_criterion_resolves_in_driver_results(monkeypatch, tmp_path):
    """Each criterion's metrics exist, as numbers, in the results the parts produce."""
    protocol = json.loads(PROTOCOL.read_text())
    results, failures = stub_parts(monkeypatch, tmp_path)
    assert not failures
    report = dw.build_report(results, failures, protocol)
    criteria = report["verdict"]["criteria"]
    assert [c["id"] for c in criteria] == [c["id"] for c in protocol["criteria"]]
    for c in criteria:
        assert c["values"], c["id"]
        assert all(isinstance(v, (int, float)) for v in c["values"]), c["id"]
    # The relay stand-in closes the uncoupled loop at the relay's thresholds.
    arm = report["parts"]["hysteresis"]["arms"]["uncoupled"]
    assert (arm["u_up"], arm["u_down"]) == (0.7, 0.35)
    rows = report["verdict"]["registered_predictions_check"]
    assert len(rows) == 36 and all(r["run"] is not None for r in rows)
    theory_rows = [r for r in rows if not r["name"].startswith(("reduced", "critical"))]
    for r in theory_rows:  # Registered values are the theory's, rounded.
        assert abs(r["difference"]) <= 5e-4 * abs(r["registered"]), r


def test_part_failure_fails_the_protocol_but_every_criterion_is_judged(monkeypatch, tmp_path):
    protocol = json.loads(PROTOCOL.read_text())
    results, failures = stub_parts(monkeypatch, tmp_path, failing="cut")
    assert list(failures) == ["cut"]
    report = dw.build_report(results, failures, protocol)
    verdict = report["verdict"]
    assert verdict["passed"] is False and verdict["failed_parts"] == ["cut"]
    by = {c["id"]: c for c in verdict["criteria"]}
    assert by["B6_cut_restore_returns"]["passed"] is False
    assert by["B6_cut_restore_returns"]["values"] == [None]
    assert by["B0_single_cell"]["passed"] is True
    # Re-judging the saved results reproduces the saved verdict.
    path = tmp_path / "results.json"
    path.write_text(json.dumps(report))
    judgement = dw.rejudge(path, protocol, tmp_path / "judgement.json")
    assert judgement["matches_saved_verdict"] is True
    assert json.loads((tmp_path / "judgement.json").read_text())["verdict"]["passed"] is False


def test_numerics_summary_reports_a_missing_diagnostic_as_unknown():
    full = dict(max_energy_balance_relative=1e-5, max_global_charge_bound_ratio=0.2)
    runs = dict(a=dict(run=dict(diagnostics_max=full)), b=[dict(diagnostics_max=dict(full))])
    assert dw.numerics_summary(runs)["max_global_charge_bound_ratio"] == 0.2
    runs["b"][0]["diagnostics_max"].pop("max_global_charge_bound_ratio")
    worst = dw.numerics_summary(runs)
    assert worst["max_global_charge_bound_ratio"] is None
    assert worst["max_energy_balance_relative"] == 1e-5 and worst["engine_runs"] == 2
    assert dw.numerics_summary({})["max_energy_balance_relative"] is None
