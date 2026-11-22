"""Compare adenylate kinase on total nucleotides and the work of a held NADH supply."""

import json
import math
from pathlib import Path

import jax
import numpy as np

from cells.execution.runner import run
from cells.kinds import transporter
from cells.laws.electrochemistry import R
from cells.registry import species_registry
from tests.unit import test_mito_cycle_laws as fx
from validation.mitochondria import component_comparison as cc


def kinase(inputs, measurements):
    engine, reason = cc.engine_adapter("adenylate_kinase", inputs)
    assert engine is not None, reason
    a = cc.parameter(inputs, "K_MgATP")
    d = cc.parameter(inputs, "K_MgADP")
    # The declared match uses 5 mM total Mg and 1.3 mM total ADP as the only binder.
    b = d + 0.0013 - 0.005
    match = (math.sqrt(b * b + 4 * d * 0.005) - b) / 2
    base = 0.4331 * (1 + match / d) ** 2 / (1 + match / a)

    def apparent(mg):
        return base * (1 + mg / a) / (1 + mg / d) ** 2

    errors = []
    adp_total = atp_total = 0.001  # M
    for mg in (1e-9, 0.0001, d - 2 * a, 0.001, 0.00185, match, 0.0083):
        for load in (0.5, 1.0, 2.0):
            amp = load * apparent(mg) * adp_total**2 / atp_total
            free = dict(Mg_P=mg, ADP3_P=adp_total / (1 + mg / d),
                        ATP4_P=atp_total / (1 + mg / a), AMP_P=amp)
            values = dict(dpsi_mV=160.0)
            got = engine.evaluate(values, free)
            forward = engine.capacity * apparent(mg) * adp_total**2
            net = forward - engine.capacity * amp * atp_total
            assert math.isclose(got["S"], forward, rel_tol=2e-13)
            assert abs(got["x"] - math.log(load)) < 2e-13
            errors.append(abs(got["J"] - net) / forward)
            if load != 1:
                assert got["J"] * (1 - load) > 0
            if mg == match and load == 0.5:
                omitted = engine.evaluate(values, free, plant="dropped_factor")
                rate_ratio = got["J"] / omitted["J"]
                assert math.isclose(rate_ratio, 1 + match / a, rel_tol=2e-13)
    assert max(errors) < 2e-13
    lawson = measurements["lawson1979_myokinase"]
    maize = measurements["kleczkowski1991_maize"]
    return dict(cases=len(errors), max_flux_error_over_forward=max(errors),
                matched_free_Mg_mM=1000 * match, matched_apparent_K=apparent(match),
                rate_ratio_full_over_omitted_Mg_prefactor=rate_ratio, peak_free_Mg_mM=1000 * (d - 2 * a),
                peak_apparent_K=apparent(d - 2 * a),
                lawson_observed=lawson["total_ATP_AMP_over_ADP_squared"],
                lawson_predicted=[apparent(m / 1000) for m in lawson["free_Mg_mM"]],
                maize_observed=maize["total_ATP_AMP_over_ADP_squared"],
                maize_predicted_range=sorted(apparent(m / 1000) for m in maize["free_Mg_mM_interval"]))


def supply(inputs):
    engine, reason = cc.engine_adapter("nadh_supply", inputs)
    assert engine is not None, reason
    r = cc.parameter(inputs, "r")
    k1, k2 = (cc.parameter(inputs, name) for name in ("k_Pi1_mM", "k_Pi2_mM"))
    held = 10**-0.10 * r
    nad = 0.001
    stalls, errors = {}, []
    for ph in (6.8, 7.0, 7.1, 7.4):
        h = 10**-ph
        stall = held * 1e-7 / h
        stalls[str(ph)] = stall
        for pi_mM in (0.3, 5.0):
            forward = engine.capacity * (1 + pi_mM / k1) / (1 + pi_mM / k2) * r * nad
            for load in (0.5, 1.0, 2.0):
                values = dict(h_N=h, NAD_N=nad, NADH_N=nad * stall * load, Pi_N=pi_mM / 1000,
                              S_ox_N=0.001, S_red_N=0.001 * held, dpsi_mV=160.0)
                got = engine.evaluate(values, cc.free_coordinates(values, inputs))
                assert math.isclose(got["S"], forward, rel_tol=2e-13)
                assert abs(got["x"] - math.log(load)) < 2e-13
                errors.append(abs(got["J"] / forward - (1 - load)))
                if load != 1:
                    assert got["J"] * (1 - load) > 0
    assert max(errors) < 2e-13
    return dict(cases=len(errors), max_flux_error_over_forward=max(errors),
                held_reduced_over_oxidized=held, stall_free_NADH_over_NAD=stalls)


def world():
    raw = fx.host_p_world({**fx.SUPPLY, **fx.KINASE})
    dt = raw["execution"]["dt"]
    raw["experiment"].update(end_time=2 * dt, observation_times=[0, dt, 2 * dt])
    spec, impl, state, p, control = fx.start(raw)
    read, volts, _ = fx.evaluation(impl, state, p, control)
    species = list(spec.model.species_ids)
    lumen = [n.id for n in spec.model.extracellular].index("lumen_0")
    populations = [n["id"] for n in raw["model"][transporter.MODEL_KEY]]
    dh, ak = (populations.index(name) for name in ("dh", "ak"))
    np.testing.assert_array_equal(p.cycle_charge_moved[0], [0, 0])
    free = fx.free_molar(spec, p, read)
    mu0 = species_registry.potential_set_values(
        fx.SET, temperature_K=fx.T_K, standard_concentration_mM=species_registry.SET_C0_MM
    )
    held = free["S_red_N"] / free["S_ox_N"]
    stall = held * 1e-7 / free["h_N"]
    work_records = []
    for load in (0.5, 2.0):
        # Change only free NADH in the closure's prepared read. ATP, ADP, H and Mg retain
        # the values from the real initial stage. The trajectory below uses the original state.
        increment = np.array(read.amount_increment)
        row = species.index("NADH")
        increment[row, 0] = free["NAD_N"] * stall * load * 1000 * p.volume[0] - p.amount_reference[row, 0]
        stage = read._replace(amount_increment=increment)
        local = fx.free_molar(spec, p, stage)
        mu = {s: mu0[s] + math.log(local[f"{cc.SET_INPUT.get(s, s)}_N"])
              for s in ("S_red", "S_ox", "NAD", "NADH", "H")}
        rates = transporter.rates(stage, volts, control, p, xp=np)
        assert bool(rates.valid)
        flux = float(rates.derivatives["cycle_count"][0, dh])
        scale = flux * R * fx.T_K / 1000
        upkeep = -scale * (mu["S_ox"] - mu["S_red"])
        delivered = scale * (mu["NADH"] + mu["H"] - mu["NAD"])
        work, heat = float(rates.work_pJ_s[dh]), float(rates.heat_pJ_s[dh])
        assert flux * (1 - load) > 0 and heat > 0
        np.testing.assert_allclose([work, heat + delivered], upkeep, rtol=2e-12, atol=0)
        work_records.append(dict(load=load, flux_fmol_s=flux, heat_pJ_s=heat,
                                 work_pJ_s=work, delivered_pJ_s=delivered))

    result = run(spec)
    assert result.final.step_index == 2
    h = result.history
    ak_extent = h.cycle_count[1:, 0, ak]
    dh_extent = h.cycle_count[1:, 0, dh]
    assert np.all(ak_extent != 0) and np.all(dh_extent != 0)
    for s, coefficient in (("ADP", -2), ("ATP", 1), ("AMP", 1)):
        np.testing.assert_allclose(h.extracellular_amount_increment[1:, species.index(s), lumen],
                                   coefficient * ak_extent, rtol=3e-13, atol=0)
    for s, coefficient in (("NAD", -1), ("NADH", 1)):
        np.testing.assert_allclose(h.amount_increment[1:, species.index(s), 0],
                                   coefficient * dh_extent, rtol=3e-13, atol=0)
    for s, coefficient in (("S_red", 1), ("S_ox", -1)):
        row = species.index(s)
        np.testing.assert_array_equal(h.amount_increment[:, row, 0], 0)
        np.testing.assert_allclose(h.cycle_supplied_fmol[1:, row, dh],
                                   coefficient * dh_extent, rtol=3e-13, atol=0)
    return dict(steps=result.final.step_index, kinase_extent_fmol=float(ak_extent[-1]),
                supply_extent_fmol=float(dh_extent[-1]), supply_power=work_records)


if __name__ == "__main__":
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    with fx.mito_scoped():
        center = Path(fx.__file__).with_name("mito_component_center_rows.json")
        inputs = json.loads(center.read_text())["inputs"]
        data = Path(__file__).with_name("data") / "mitochondrial_reaction_measurements.json"
        print(json.dumps(dict(kinase=kinase(inputs, json.loads(data.read_text())), supply=supply(inputs), world=world()),
                         indent=2, allow_nan=False))
