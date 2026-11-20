"""Check stall, reversal and instantaneous heat at the seven mitochondrial kind readouts."""

import json
import math
from decimal import Decimal as D
from functools import partial
from pathlib import Path
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.kinds import transporter
from cells.laws.cycles import forms
from cells.laws.electrochemistry import R
from cells.modules import node_concentrations
from lean.checks.mitochondrial_cycles import CYCLES, P_CHARGE
from tests.unit import test_mito_cycle_laws as fx
from validation.mitochondria import component_comparison as cc

KEYS = (
    "complex_I",
    "complex_III_eq24",
    "complex_IV",
    "atp_synthase",
    "nucleotide_exchange",
    "phosphate_carrier",
    "k_h_exchange",
)
SHARES = (1, 2, 4, 1, 1, 1, 1)
DRIVES = (-1, -(2**-24), -(2**-40), 0, 2**-40, 2**-24, 1)


class Readout(NamedTuple):
    valid: np.ndarray
    stage_valid: np.ndarray
    x: np.ndarray
    forward: np.ndarray
    flux: np.ndarray
    stage_flux: np.ndarray
    heat: np.ndarray
    stage_heat: np.ndarray
    heat_derivative: np.ndarray


def read_rates(read, volts, control, p, *, xp):
    probe = transporter.probe(read, volts, control, p, xp=xp)
    rates = transporter.rates(read, volts, control, p, xp=xp)
    return Readout(
        probe.populations.valid,
        rates.valid,
        probe.modes.x[0],
        probe.modes.j_plus[0],
        probe.modes.j[0],
        rates.derivatives["cycle_count"][0],
        probe.populations.heat_pJ_s,
        rates.heat_pJ_s,
        rates.derivatives["cycle_dissipated_energy_pJ"],
    )


def free_activities(read, p, species, lumen):
    conc = node_concentrations(read, p, xp=np)
    return {
        f"{cc.SET_INPUT.get(s, s)}_{side}": D.from_float(float(conc[i, node])) / 1000
        for i, s in enumerate(species)
        for side, node in (("N", 0), ("P", len(p.active) + lumen))
    }


def reference_state(read, volts, p, species, lumen, ref):
    coords = free_activities(read, p, species, lumen)
    delta_v = float(volts[len(p.active) + lumen] - volts[0])
    coords["u"] = D.from_float(delta_v) * 1000 * ref.k.F_OVER_RT_PER_MV
    return ref.x_and_s(coords)


def at_drive(target, name, q, x0, read, volts, p, species, lumen, ref):
    """Set the N−P voltage or the P-side free substrate at a fixed stage read."""
    v = volts.copy()
    if q:
        v[0] = v[len(p.active) + lumen] + float(
            (x0 - target) / (int(q) * ref.k.F_OVER_RT_PER_MV * 1000)
        )
        return read, v, float(1000 * (v[0] - v[len(p.active) + lumen]))
    row = species.index({"pic": "Pi", "khe": "K"}[name])
    conc = node_concentrations(read, p, xp=np)[row, len(p.active) + lumen]
    new_conc = float(D.from_float(float(conc)) * (x0 - target).exp())
    outside = np.array(read.extracellular_amount_increment)
    outside[row, lumen] = (
        new_conc * p.extracellular_volume[lumen] - p.extracellular_amount_reference[row, lumen]
    )
    return read._replace(extracellular_amount_increment=outside), v, new_conc


def check_readout(sample, slot, x_ref, plus_ref, target, rt, *, enabled=True):
    assert bool(sample.valid[slot]) and bool(sample.stage_valid)
    x, plus, j, heat = (
        float(v[slot]) for v in (sample.x, sample.forward, sample.flux, sample.heat)
    )
    assert (
        sample.stage_flux[slot] == j
        and sample.stage_heat[slot] == heat
        and sample.heat_derivative[slot] == heat
    )
    assert abs(float(x_ref) - target) < 1e-13
    assert abs(x - float(x_ref)) < 1e-13
    if not enabled:
        assert plus == j == heat == 0
        return
    j_ref = plus_ref * (1 - x_ref.exp())
    # Near a cancellation, scale the absolute flux error by a one-way rate.
    error = float(abs(D.from_float(j) - j_ref) / plus_ref)
    assert error < 2e-13 and math.isclose(plus, float(plus_ref), rel_tol=2e-13)
    heat_scale = rt * plus_ref / 1000
    heat_ref = -rt * x_ref * j_ref / 1000
    heat_error = float(abs(D.from_float(heat) - heat_ref) / heat_scale)
    assert heat_error < 4e-13
    j_at_x = D.from_float(plus) * (1 - D.from_float(x).exp())
    assert math.isclose(j, float(j_at_x), rel_tol=5e-14)
    assert math.isclose(heat, float(-rt * D.from_float(x) * D.from_float(j) / 1000), rel_tol=5e-14)
    if target:
        assert j * target < 0 and heat > 0
    assert (heat == 0) == (x == 0) and heat >= 0
    return error, heat_error


def check_backend(evaluate, exact_flux, spec, p, control, read, volts, refs):
    species = list(spec.model.species_ids)
    lumen = [o.id for o in spec.model.extracellular].index("lumen_0")
    zero_v = np.zeros_like(volts)
    rt = D.from_float(R) * D.from_float(float(p.temperature))
    off = control._replace(cycle_availability=np.zeros_like(control.cycle_availability))
    records = {}
    for slot, (name, q, ref, key) in enumerate(zip(CYCLES, P_CHARGE, refs, KEYS, strict=True)):
        x0, _ = reference_state(read, zero_v, p, species, lumen, ref)
        scale = D.from_float(
            float(p.cycle_capacity_fmol_s[slot] * control.cycle_availability[slot])
        )
        scale /= ref.k.P[cc.ENGINE[key].capacity]
        rate_errors = []
        heat_errors = []
        for target in DRIVES:
            stage, v, setting = at_drive(
                D(target), name, q, x0, read, zero_v, p, species, lumen, ref
            )
            x_ref, s_ref = reference_state(stage, v, p, species, lumen, ref)
            args = slot, x_ref, scale * s_ref, target, rt
            sample = evaluate(stage, v, control, p)
            rate_error, heat_error = check_readout(sample, *args)
            rate_errors.append(rate_error)
            heat_errors.append(heat_error)
            if target == 0:
                records[name] = {
                    "stall_mV_N_minus_P" if q else "stall_free_P_mM": setting,
                    "x_at_stall": float(sample.x[slot]),
                }
                log_plus = math.log(float(sample.forward[slot]))
            if target == 1:
                check_readout(evaluate(stage, v, off, p), *args, enabled=False)
                if not q:
                    v[0] += 0.1
                    shifted = evaluate(stage, v, control, p)
                    check_readout(shifted, *args)
                    for field in ("x", "flux", "heat"):
                        assert getattr(shifted, field)[slot] == getattr(sample, field)[slot]
        # The physical stall can fall between two float64 settings. Exercise the
        # production rate kernel at exactly supplied drives with this population's scale.
        tiny = 2.0**-60
        drives = np.array([-tiny, 0.0, tiny])
        flux = np.asarray(exact_flux(log_plus, drives))
        expected = [
            float(D.from_float(log_plus).exp() * (1 - D.from_float(x).exp())) for x in drives
        ]
        np.testing.assert_allclose(flux, expected, rtol=5e-14, atol=0)
        assert flux[0] > 0 and flux[1] == 0 and flux[2] < 0
        records[name]["max_rate_error_over_reference_forward_rate"] = max(rate_errors)
        records[name]["max_heat_error_over_RT_forward_rate"] = max(heat_errors)
    return records


def yeast_synthase(protons_per_atp):
    path = Path(__file__).parent / "data" / "mitochondrial_stall.json"
    data = json.loads(path.read_text())["petersen2012_yeast_stall@1"]
    anchor = data["single_load"]
    corrected = data["corrected_stalls"]
    records = []
    for q, measured, error in corrected:
        if q == anchor["Q"]:
            assert (measured, error) == (
                anchor["corrected_stall_dpH"],
                anchor["interpolation_error_dpH"],
            )
            continue
        predicted = anchor["corrected_stall_dpH"] + math.log10(q / anchor["Q"]) / protons_per_atp
        # Adding the reported limits needs no independence or distribution assumption.
        limits = error + anchor["interpolation_error_dpH"]
        records.append(
            dict(
                Q=q,
                observed=measured,
                predicted=predicted,
                within_added_limits=abs(predicted - measured) <= limits,
            )
        )
    low, high = corrected[0], corrected[-1]
    return dict(
        model_protons_per_ATP=protons_per_atp,
        observed_endpoint_shift_dpH=high[1] - low[1],
        predicted_endpoint_shift_dpH=math.log10(high[0] / low[0]) / protons_per_atp,
        within_added_limits=sum(row["within_added_limits"] for row in records),
        other_corrected_rows=records,
    )


def run():
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    raw = fx.host_p_world()
    spec, impl, state, p, control = fx.start(raw)
    read, volts, _ = fx.evaluation(impl, state, p, control)
    assert tuple(r["id"] for r in raw["model"][transporter.MODEL_KEY]) == CYCLES
    np.testing.assert_array_equal(p.cycle_charge_moved[0], P_CHARGE)
    np.testing.assert_array_equal(p.cycle_mono_share[0], SHARES)
    synthase = CYCLES.index("f1")
    outer_h = (
        p.cycle_row_present[:, synthase]
        & ~p.cycle_row_at_n[:, synthase]
        & (p.cycle_row_species[:, synthase] == list(spec.model.species_ids).index("H"))
    )
    protons_per_atp = float(-p.cycle_nu[0, outer_h, synthase].sum())
    assert protons_per_atp == 3
    inputs = cc.interface("inputs")
    refs = [cc.DryRunAdapter(key, inputs) for key in KEYS]
    args = spec, p, control, read, volts, refs
    return dict(
        numpy=check_backend(
            partial(read_rates, xp=np), partial(forms.sign_exact_flux, xp=np), *args
        ),
        jax_jit=check_backend(
            jax.jit(partial(read_rates, xp=jnp)),
            jax.jit(partial(forms.sign_exact_flux, xp=jnp)),
            *args,
        ),
        yeast_synthase=yeast_synthase(protons_per_atp),
    )


if __name__ == "__main__":
    with fx.mito_scoped():
        print(json.dumps(run(), indent=2, allow_nan=False))
