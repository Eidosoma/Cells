"""Check pump reversals and combined current in cells.model.resolved_pump_tissue@3."""

import json
import math
from pathlib import Path

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.execution.schedule import control_values
from cells.registry.models import get_model
from validation.betse.pump_contact import pump_reference as nak
from validation.chemistry import finite_calcium_pump_reference as calcium
from validation.tissue import surface_pump_v2_fixtures as v2
from validation.tissue import surface_pump_v3_fixtures as v3

CONSTANTS = nak.CONSTANTS["matched_constants"]
F, R = CONSTANTS["F"], CONSTANTS["R"]
T = 298.15
NA_IN, K_IN = 12.0, 140.0
NA_OUT, K_OUT = (v3.HEREDITY_BATH_mM[s] for s in ("Na", "K"))
CA_IN, CA_OUT = v2.CELL_CA_mM, v2.OUTSIDE_CA_mM
FUEL = dict(atp_mM=1.5, adp_mM=1.0, pi_mM=5.0, delta_g0_J_per_mol=-30500.0)
NAK_CAPACITY = 0.1  # fmol/s per patch
END_S = 0.001
PROTOCOL = Path(calcium.__file__).with_name("finite_calcium_pump_protocol.json")
TOL = json.loads(PROTOCOL.read_text())["tolerances"]


def reversal_voltages():
    rt = R * T
    drive = FUEL["delta_g0_J_per_mol"] + rt * math.log(
        FUEL["adp_mM"] * FUEL["pi_mM"] / (1000 * FUEL["atp_mM"])
    )
    nak_stall = (drive - 3 * rt * math.log(NA_IN / NA_OUT) + 2 * rt * math.log(K_IN / K_OUT)) / F
    ca_stall = (drive - rt * math.log(CA_IN / CA_OUT)) / (2 * F)
    return nak_stall, ca_stall


def reference(voltage, ca_capacity):
    case = dict(
        nak.BASE,
        id="tissue-patch",
        na_in_mM=NA_IN,
        na_out_mM=NA_OUT,
        k_in_mM=K_IN,
        k_out_mM=K_OUT,
        atp_mM=FUEL["atp_mM"],
        adp_mM=FUEL["adp_mM"],
        pi_mM=FUEL["pi_mM"],
        delta_g0_J_mol=FUEL["delta_g0_J_per_mol"],
        temperature_K=T,
        voltage_V=voltage,
        area_m2=v3.HEREDITY_AREA_M2,
        alpha_mol_m2_s=NAK_CAPACITY * 1e-15 / v3.HEREDITY_AREA_M2,
    )
    sodium = nak.oracle(case, CONSTANTS)
    # A 1 pL reference volume makes each fuel amount in fmol numerically equal to its mM.
    pump = v2.calcium_pump(0)
    ca = calcium.rates(
        CA_IN,
        CA_OUT,
        voltage,
        [FUEL[k] for k in ("atp_mM", "adp_mM", "pi_mM")],
        1.0,
        T,
        FUEL["delta_g0_J_per_mol"],
        ca_capacity,
        pump["km_ca_mM"],
        pump["km_atp_mM"],
        1.0,
        kind="pmca",
    )
    return (
        sodium["third_out_na_fmol_s"] / 3,
        ca["cycles_fmol_s"],
        sodium["cycle_free_energy_J_mol"],
        ca["reaction_free_energy_J_mol"],
    )


def definition(voltages, ca_capacity):
    raw = v3.heredity_cells(
        [(v, NA_IN, K_IN, 12.0) for v in voltages],
        dt=END_S / 20,
        end_time=END_S,
        solver="rk4",
        temperature_K=T,
    )
    model, experiment, execution = raw["model"], raw["experiment"], raw["execution"]
    model["channels"] = []
    experiment["channel_controls"] = []
    execution["channel_capacity"] = 0
    model["species"].append(dict(id="Ca", valence=2))
    execution["material_balance_atol_fmol"]["Ca"] = 2e-11
    for key, concentration in (("cells", CA_IN), ("extracellular", CA_OUT)):
        for node in model[key]:
            amount = concentration * node["volume_pL"]
            node["initial_amount_fmol"]["Ca"] = amount
            node["fixed_charge_equivalent_fmol"] -= 2 * amount
    for i, patch in enumerate(model["membranes"]):
        patch["permeability_m_per_s"] = {s["id"]: 0.0 for s in model["species"]}
        patch["pump"]["capacity_fmol_per_s"] = NAK_CAPACITY
        patch["pump"]["metabolism"].update(FUEL)
        pump = v2.calcium_pump(i)
        pump["capacity_fmol_per_s"] = ca_capacity
        pump["metabolism"].update(FUEL)
        patch["calcium_pump"] = pump
        experiment["calcium_pump_controls"].append(
            dict(pump_id=pump["id"], schedule=[dict(time=0.0, availability=1.0)])
        )
    return raw


def outward(nak_cycles, ca_cycles):
    """Signed Na, K and Ca transferred from cell to bath."""
    return np.stack((3 * nak_cycles, -2 * nak_cycles, ca_cycles))


def initial_rates(spec):
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    control = jax.tree.map(lambda values: values[0], control_values(spec, [0.0]))
    return jax.device_get(jax.jit(model.readouts)(state, control, layout))


def check():
    nak_stall, ca_stall = reversal_voltages()
    midpoint = (nak_stall + ca_stall) / 2
    j_nak, j_ca, _, _ = reference(midpoint, 1.0)
    ca_capacity = -j_nak / (2 * j_ca)
    assert ca_capacity > 0
    voltages = [
        min(nak_stall, ca_stall) - 0.01,
        ca_stall,
        midpoint,
        nak_stall,
        max(nak_stall, ca_stall) + 0.01,
    ]
    expected_nak, expected_ca, energy_nak, energy_ca = np.array(
        [reference(v, ca_capacity) for v in voltages]
    ).T
    raw = definition(voltages, ca_capacity)
    result = run(parse_spec(raw))
    stage = initial_rates(result.spec)
    assert stage.valid
    field = stage.field
    indices = [result.spec.model.species_ids.index(s) for s in ("Na", "K", "Ca")]
    np.testing.assert_allclose(field.rates.membrane_voltage_V, voltages, rtol=0, atol=1e-14)
    actual_nak, actual_ca = stage.derivative.pump_cycles, stage.derivative.calcium_pump_cycles
    for actual, expected, stall in (
        (actual_nak, expected_nak, nak_stall),
        (actual_ca, expected_ca, ca_stall),
    ):
        np.testing.assert_allclose(
            actual, expected, rtol=nak.RELATIVE, atol=TOL["rate_atol_fmol_s"]
        )
        for rate, voltage in zip(actual, voltages, strict=True):
            if voltage == stall:
                assert abs(rate) <= TOL["rate_atol_fmol_s"]
            else:
                assert np.sign(rate) == np.sign(voltage - stall)
    for actual, expected in (
        (stage.pump_affinity_J_mol, energy_nak),
        (stage.calcium_pump_affinity_J_mol, energy_ca),
    ):
        np.testing.assert_allclose(
            actual, expected, rtol=TOL["relative"], atol=TOL["potential_atol_J_mol"]
        )
    flux = outward(expected_nak, expected_ca)
    np.testing.assert_allclose(
        field.rates.membrane_flux_fmol_s[indices],
        flux,
        rtol=nak.RELATIVE,
        atol=TOL["rate_atol_fmol_s"],
    )
    expected_current = F * 1e-15 * (expected_nak + 2 * expected_ca)
    for current in (field.electrode_current_A, result.observations.electrode_current_A[0]):
        np.testing.assert_allclose(
            current, expected_current, rtol=nak.RELATIVE, atol=nak.ABSOLUTE["inward_current_A"]
        )
    # Both pumps turn at the middle patch while their outward charge fluxes cancel initially.
    assert actual_nak[2] < 0 < actual_ca[2]
    assert abs(field.electrode_current_A[2]) < nak.ABSOLUTE["inward_current_A"]
    state = result.final.state
    transferred = outward(state.pump_cycles, state.calcium_pump_cycles)
    for balance in (state.amount_increment, state.reservoir_supplied):
        np.testing.assert_allclose(np.asarray(balance)[indices], -transferred, rtol=0, atol=1e-15)
    heat = np.array([state.pump_dissipated_energy_pJ, state.calcium_pump_dissipated_energy_pJ])
    assert (heat >= 0).all() and (heat[:, 2] > 0).all()
    return dict(
        model=raw["model"]["id"],
        duration_s=END_S,
        initial_voltages_V=voltages,
        nak_stall_V=nak_stall,
        calcium_stall_V=ca_stall,
        calcium_capacity_fmol_s=ca_capacity,
        max_cycle_error_fmol_s=float(
            max(np.max(abs(actual_nak - expected_nak)), np.max(abs(actual_ca - expected_ca)))
        ),
        max_current_error_A=float(np.max(abs(field.electrode_current_A - expected_current))),
        midpoint_cycles_fmol_s=[float(actual_nak[2]), float(actual_ca[2])],
        midpoint_electrode_current_A=float(field.electrode_current_A[2]),
        midpoint_heat_pJ=heat[:, 2].tolist(),
    )


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, allow_nan=False))
