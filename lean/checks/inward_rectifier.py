"""Check the inward-rectifier stage bound, equivalent reference settings, and Kir4.1 data."""

import argparse
import json
import math
from itertools import product
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.laws.routes import inward_rectifier_linear_driving_force as law
from tests.unit import test_inward_rectifier_route as fixture
from validation.core_seams.references import design, exact


def reference(args):
    with exact.context():
        ci, co, v, t, area, g, ref, half, slope, opening = map(exact.dec, args)
        u = v - (co.ln() - ci.ln()) / exact.F_over_RT(t)
        scale = opening * area * g * co.sqrt() / ref.sqrt()
        # Differentiate the signed current by forward-mode dual arithmetic.
        drive = exact.Dual(u, 1)
        gate = 1 / (1 + ((drive - half) / slope).exp())
        current = scale * gate * drive
        return np.array(
            [
                float(current.a),
                float(-current.a * 10**15 / exact.F_C_per_mol()),
                float(10**12 * current.a * u),
                float(current.b),
            ]
        )


@jax.jit
def stage(*args):
    return jnp.stack(
        [
            law.current_A(*args),
            law.flux_fmol_s(*args),
            law.heat_pJ_s(*args),
            law.slope_conductance_S(*args),
            law.slope_bound_S(*args[:2], *args[3:]),
        ]
    )


def voltage_panel():
    cases = []
    for co, half, slope, opening in product(
        (2.0, 5.0, 35.0, 153.0), (-0.04, 0.0, 0.05), (0.006, 0.035), (0.0, 0.6, 1.0)
    ):
        e = math.log(co / 140.0) / float(exact.F_over_RT(298.15))
        for drive in (-0.12, -0.015, 0.0, 0.015, 0.12):
            cases.append((140.0, co, e + drive, 298.15, 1e-10, 1.0, 5.0, half, slope, opening))
    measured = np.array(stage(*np.array(cases).T)).T
    expected = np.array([reference(args) for args in cases])
    negative_slopes = int(np.sum(expected[:, 3] < 0))
    expected[:, 3] = np.abs(expected[:, 3])
    # Floors use the unrectified gain and full driving-voltage scale near reversal.
    gain = np.array([a[4] * a[5] * math.sqrt(a[1] / a[6]) for a in cases])
    volts = 0.4  # Covers the sum of |V| and |E| on this panel.
    units = np.array([volts, volts * 1e15 / float(exact.F_C_per_mol()), 1e12 * volts**2, 1])
    error = np.abs(measured[:, :4] - expected) / (gain[:, None] * units)
    assert np.all(error <= design.BAND_EPS * exact.EPS)
    assert np.all(measured[:, 2] >= 0) and np.all(measured[:, 3] <= measured[:, 4])
    assert negative_slopes > 0
    return dict(
        states=len(cases),
        negative_reference_slopes=negative_slopes,
        max_scaled_error=float(np.max(error)),
    )


def reference_world(exponent):
    # Squaring the multiplier on g gives the multiplier on its reference concentration.
    g, ref = math.ldexp(1.0, exponent), math.ldexp(4.0, 2 * exponent)
    raw = fixture.closed_pair(fixture.route(g_ref_S_per_m2=g, k_ref_mM=ref), end=0.001)
    area = next(p["area_m2"] for p in raw["model"]["membranes"] if p["id"] == "contact_0")
    args = (140.0, 5.0, 0.0, raw["model"]["temperature_K"], area, g, ref, 0.1, 0.05, 1.0)
    with np.errstate(over="ignore", invalid="ignore"):
        current = float(law.current_A(*map(np.float64, args), xp=np))
    ref_current = float(reference(args)[0])
    result = dict(
        g_ref_S_per_m2=g,
        k_ref_mM=ref,
        reference_A=ref_current,
        float64_A=current if math.isfinite(current) else None,
    )
    try:
        spec = parse_spec(raw)
    except ConfigError as err:
        return dict(**result, admitted=False, reason=str(err), passed=False)
    final = run(spec).final
    k = list(spec.model.species_ids).index("K")
    moved = float(final.state.passive_transferred[k, 0])
    heat = float(final.state.passive_dissipated_energy_pJ[0])
    passed = math.isclose(current, ref_current, rel_tol=design.BAND_EPS * exact.EPS)
    return dict(
        **result,
        admitted=True,
        transferred_fmol=moved,
        heat_pJ=heat,
        steps=int(final.step_index),
        passed=passed and moved < 0 < heat,
    )


def kir_measurements():
    data = json.loads(Path(__file__).with_name("data").joinpath("tada1998_kir41.json").read_text())
    outside = np.array(data["outside_K_mM"])
    e = law.reversal_V(outside[-1], outside, data["temperature_K"], xp=np)
    u = data["common_drive_mV"] / 1000
    # At fixed drive the unknown logistic, area and density cancel in the current ratio.
    currents = law.current_A(
        outside[-1], outside, e + u, data["temperature_K"], 1, 1, outside[-1], 0, 0.02, 1, xp=np
    )
    anchor = data["current_at_common_drive_pA"][-1]
    predicted = currents / currents[-1] * anchor
    np.testing.assert_allclose(predicted, anchor * np.sqrt(outside / outside[-1]), rtol=2e-14)
    return dict(
        predicted_pA=predicted.tolist(),
        measured_pA=data["current_at_common_drive_pA"],
        nernst_shift_mV=float(1000 * (e[0] - e[-1])),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls-only", action="store_true")
    opts = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    ordinary = voltage_panel()
    powers = [0, -8] if opts.controls_only else [0, -8, -512]
    worlds = [reference_world(e) for e in powers]
    for entry in worlds:
        assert entry["reference_A"] == worlds[0]["reference_A"]
        if entry["admitted"]:
            for key in ("transferred_fmol", "heat_pJ"):
                entry["passed"] &= math.isclose(
                    entry[key], worlds[0][key], rel_tol=design.BAND_EPS * exact.EPS
                )
    print(
        json.dumps(
            dict(voltage_panel=ordinary, reference_worlds=worlds, kir41=kir_measurements()),
            indent=2,
            allow_nan=False,
        )
    )
    return 0 if all(entry["passed"] for entry in worlds) else 1


if __name__ == "__main__":
    raise SystemExit(main())
