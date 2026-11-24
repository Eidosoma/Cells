"""Compare native flux reversals with pH-clamp and squid-axon measurements."""

import json
import math
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import brentq

from cells.laws.electrochemistry import F, R
from cells.laws.routes import constant_field_permeation
from cells.laws.transport import proton_leak

DATA = Path(__file__).with_name("data")
CHARGE = np.array([1, 1, -1])


@jax.jit
def net_charge_flux(voltage, inside, outside, temperature, weights):
    inward = constant_field_permeation.flux_fmol_s(
        inside,
        outside,
        voltage,
        CHARGE,
        temperature,
        1e-10,
        1e-8 * weights,
        1.0,
    )
    return jnp.dot(CHARGE, inward)


def root_mV(flux, *args):
    return 1000 * brentq(lambda v: float(flux(v, *args)), -0.25, 0.25, xtol=1e-15)


def squid_substitutions(study, hk):
    assert hk["ion_order"] == ["Na", "K", "Cl"]
    weights = np.array(hk["relative_permeability"])
    inside = np.array([0.0, study["internal_K_mM"], 0.0])
    thermal = 1000 * R * (study["temperature_C"] + 273.15) / F
    external_sum = study["external_K_plus_Na_mM"]
    k = np.array(study["external_K_mM"])
    measured = np.array(study["mean_voltage_inside_minus_outside_mV"])
    observed = measured - measured[0]
    roots = [
        root_mV(
            net_charge_flux,
            inside,
            np.array([external_sum - ko, ko, study["approx_external_Cl_mM"]]),
            study["temperature_C"] + 273.15,
            weights,
        )
        for ko in k
    ]
    # With a fixed interior and external chloride, the GHK denominator cancels in voltage shifts.
    numerator = weights[0] * (external_sum - k) + weights[1] * k + weights[2] * inside[2]
    predicted = np.array(roots) - roots[0]
    np.testing.assert_allclose(
        predicted, thermal * np.log(numerator / numerator[0]), atol=1e-10, rtol=0
    )
    # At fixed internal composition, exp(V / thermal) is affine in external K for Na substitution.
    # Anchor at the end points where both cations are present. Evaluate only interior solutions.
    low, high = 0, len(k) - 2
    assert k[low] == 10 and k[high] == 350 and k[-1] == external_sum
    interior = slice(low + 1, high)
    weight = (k[interior] - k[low]) / (k[high] - k[low])
    interpolated = thermal * np.log(
        (1 - weight) * np.exp(measured[low] / thermal) + weight * np.exp(measured[high] / thermal)
    )
    return {
        "external_K_mM": k.tolist(),
        "measured_change_mV": observed.tolist(),
        "transferred_permeability_native_change_mV": predicted.tolist(),
        "two_anchor_evaluation_K_mM": k[interior].tolist(),
        "two_anchor_prediction_mV": interpolated.tolist(),
        "two_anchor_prediction_minus_measured_mV": (interpolated - measured[interior]).tolist(),
    }


@jax.jit
def proton_flux(voltage, inside, outside, temperature):
    return proton_leak.flux_fmol_s(inside, outside, voltage, temperature, 1e-10, 1e-8, 1.0)


def proton_reversals(study, measured_key, temperature_C):
    rows = []
    temperature = temperature_C + 273.15
    for pi, po, observed in zip(
        study["pipette_pH"], study["bath_pH"], study[measured_key], strict=True
    ):
        root = root_mV(proton_flux, 10 ** (3 - pi), 10 ** (3 - po), temperature)
        nominal = 1000 * R * temperature / F * math.log(10) * (pi - po)
        assert abs(root - nominal) < 1e-10
        rows.append(
            {"pipette_pH": pi, "bath_pH": po, "observed_mV": observed, "nominal_root_mV": root}
        )
    return rows


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    studies = json.loads((DATA / "membrane_physiology_pairs.json").read_text())
    hk = json.loads((DATA / "hodgkin_katz1949_rest.json").read_text())
    macrophage = studies["kapus1993_macrophage_proton@1"]
    microglia = studies["morihata2000_microglia_proton@1"]
    with jax.default_device(jax.devices("cpu")[0]):
        results = {
            "squid": squid_substitutions(studies["ohki1979_squid_perfusion@1"], hk),
            "macrophages": proton_reversals(macrophage, "reversal_mV", macrophage["temperature_C"]),
            "microglia": proton_reversals(
                microglia, "approx_reversal_mV", np.mean(microglia["temperature_range_C"])
            ),
        }
    print(json.dumps(results, indent=2, allow_nan=False))
