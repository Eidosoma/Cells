"""Compare the registered sodium–anion carrier with independent rates and SMCT1 measurements."""

import json
from pathlib import Path

import jax
import numpy as np
from scipy.optimize import brentq

from cells.execution.runner import run
from cells.kinds import transporter
from tests.unit import test_na_anion_symport_factored as fixture
from validation.core_seams.references import design, exact


def reference(n, ratios, voltage, temperature, forward_capacity, parameters):
    with exact.context():
        ni, no, bi, bo = map(exact.dec, ratios)  # At N and P, in row order.
        x = (
            n * (ni / no).ln()
            + (bi / bo).ln()
            + (n - 1) * exact.F_over_RT(temperature) * exact.dec(voltage)
        )
        s_na = 1 / (1 + (exact.dec(parameters["K_Na_mM"]) / no) ** parameters["hill_Na"])
        s_b = 1 / (1 + (exact.dec(parameters["K_B_mM"]) / bo) ** parameters["hill_B"])
        plus = exact.dec(forward_capacity) * s_na * s_b
        minus = plus * x.exp()
        net = plus - minus
        heat = -exact.RT_J_per_mol(temperature) * net * x / 1000
        return np.array(list(map(float, [x, s_na * s_b, plus, minus, net, heat])))


def voltage_panel():
    cases = 0
    stalls = 0
    max_floors = 0.0
    for n in range(1, 5):
        for end in ("a", "b"):
            raw = fixture.world(n_Na=n, hill_Na=3, hill_B=2)
            pop = raw["model"][transporter.MODEL_KEY][0]
            pop["orientation"] = {"N": end}
            spec, _, state, p, control = fixture.bound(raw)
            endpoints = fixture.concentrations(spec)
            sign = 1 if end == "a" else -1
            ratios = [v for s in ("Na", fixture.ANION) for v in endpoints[s][::sign]]
            ni, no, bi, bo = ratios
            t = spec.model.temperature_K
            center = 0.0
            if n > 1:
                center = -(n * np.log(ni / no) + np.log(bi / bo)) / (
                    (n - 1) * float(exact.F_over_RT(t))
                )
            for offset in (-0.075, -0.005, 0.0, 0.005, 0.075):
                v = center + offset
                for opening in (0.0, 0.25, 1.0):
                    ct = control._replace(
                        cycle_availability=opening * np.ones_like(control.cycle_availability)
                    )
                    probe = fixture.probed(p, state, ct, sign * v)
                    m = probe.modes
                    observed = np.asarray(
                        [float(z[0, 0]) for z in (m.x, m.s, m.j_plus, m.j_minus, m.j)]
                        + [float(probe.populations.heat_pJ_s[0])]
                    )
                    expected = reference(
                        n, ratios, v, t, pop["capacity_fmol_s"] * opening, pop["parameters"]
                    )
                    x, _, plus, minus, j, _ = expected
                    dx = design.rel_floor(float(m.x_terms[0, 0]))
                    rate_floor = (plus + minus) * dx
                    heat_floor = (
                        float(exact.RT_J_per_mol(t))
                        / 1000
                        * (rate_floor * (abs(x) + dx) + abs(j) * dx)
                    )
                    floors = np.array([dx, dx, rate_floor, rate_floor, rate_floor, heat_floor])
                    error = np.abs(expected - observed)
                    assert np.all(error <= design.BAND_EPS * floors), (
                        n,
                        end,
                        offset,
                        opening,
                        error,
                        floors,
                    )
                    max_floors = max(
                        max_floors, float(np.max(error[floors > 0] / floors[floors > 0]))
                    )
                    actual_j = observed[4]
                    assert probe.populations.valid[0] and observed[5] >= 0
                    for i, coefficient in enumerate((n, -n, 1, -1)):
                        assert probe.rows.rate[i, 0] == coefficient * actual_j
                    assert probe.populations.charge_a_to_b_fmol_s[0] == -sign * (n - 1) * actual_j
                    if n > 1 and opening > 0:
                        if offset:
                            assert np.sign(actual_j) == -np.sign(offset)
                        else:
                            assert abs(actual_j) <= design.BAND_EPS * rate_floor
                            stalls += 1
                    cases += 1
    return dict(states=cases, active_stalls=stalls, max_roundoff_floors=max_floors)


def smct1_measurements():
    def cycle_rate(volts, layout, state, control):
        return float(fixture.probed(layout, state, control, volts).modes.j[0, 0])

    data = json.loads(Path(__file__).with_name("data").joinpath("coady2007_smct1.json").read_text())
    hi_na, lo_na = data["external_sodium_mM"]
    hi_b, lo_b = data["external_substrate_mM"]
    stall = []
    for sodium, substrate in ((hi_na, hi_b), (lo_na, hi_b), (hi_na, lo_b)):
        raw = fixture.world(n_Na=2)
        raw["model"]["temperature_K"] = data["temperature_K"]
        bath = raw["model"]["extracellular"][0]
        for species, c, z in (("Na", sodium, 1), (fixture.ANION, substrate, -1)):
            amount = c * bath["volume_pL"]
            bath["fixed_charge_equivalent_fmol"] -= z * (
                amount - bath["initial_amount_fmol"][species]
            )
            bath["initial_amount_fmol"][species] = amount
        _, _, state, p, control = fixture.bound(raw)
        stall.append(brentq(cycle_rate, -0.5, 0.5, args=(p, state, control), xtol=1e-15))
        if len(stall) == 1:
            probe = fixture.probed(p, state, control, -0.05)
            sodium_rate, lactate_rate = (float(probe.rows.rate[i, 0]) for i in (0, 2))
            charge = -float(probe.populations.charge_a_to_b_fmol_s[0])
            charge_per_lactate = charge / lactate_rate
            osmolytes_per_charge = (sodium_rate + lactate_rate) / charge
    na_shift, b_shift = 1000 * (np.array(stall[1:]) - stall[0])
    np.testing.assert_allclose(
        [charge_per_lactate, osmolytes_per_charge, na_shift / b_shift],
        [1, 3, 2],
        rtol=design.BAND_EPS * exact.EPS,
    )
    independent = json.loads(
        Path(__file__).with_name("data").joinpath("gopal2004_lactate.json").read_text()
    )
    predicted_charge = charge_per_lactate * np.array(independent["lactate_uptake_pmol"])
    return dict(
        charge_per_lactate=charge_per_lactate,
        osmolytes_per_charge=osmolytes_per_charge,
        isolated_stall_shifts_mV=[na_shift, b_shift],
        ratio_of_shifts=na_shift / b_shift,
        measured_charge_per_lactate=data["charge_per_lactate"]["mean"],
        measured_osmolytes_per_charge=data["osmolytes_per_charge"]["mean"],
        measured_shift_ratios=[
            data["ratio_of_zero_current_shifts"][s]["mean"] for s in ("lactate", "propionate")
        ],
        independent_predicted_charge_pmol=predicted_charge.tolist(),
        independent_observed_charge_pmol=independent["net_positive_charge_pmol"],
    )


def host_run():
    spec, _, _, _, _ = fixture.bound(fixture.world())
    result = run(spec)
    final = result.final.state
    cycles = float(np.sum(final.cycle_count))
    lactate = float(final.amount_increment[list(spec.model.species_ids).index(fixture.ANION), 0])
    assert cycles > 0 and np.isclose(cycles, lactate, rtol=8 * exact.EPS, atol=0)
    return dict(
        steps=int(result.final.step_index),
        cycles_fmol=cycles,
        lactate_gain_fmol=lactate,
        max_charge_error_C=float(result.diagnostics["max_global_charge_error_C"]),
    )


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    print(
        json.dumps(
            dict(voltage_panel=voltage_panel(), smct1=smct1_measurements(), host_run=host_run()),
            indent=2,
            allow_nan=False,
        )
    )
