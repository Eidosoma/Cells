"""MG0b driver: the independent reduced model and the resolved_pump_tissue@3 chain.

The reduced model reproduces the heredity pre-screen's slow states and, at
several off-steady voltages, the engine's own instantaneous membrane rate
(gates at steady state, same composition): it transcribes the same laws. The
chain definition parses as resolved_pump_tissue@3 with open-gated junctions.
"""

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
