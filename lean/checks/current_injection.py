"""Opposite pulses on one clamped capacitor with a high-precision free-energy reference."""

import json

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from tests.unit.test_current_injection_runs import DT, definition
from validation.core_seams.references import exact


def pulses(carriers):
    current, duration = 1e-12, 2 * DT
    raw = definition([(0, current), (2, -current)], carriers)
    m = raw["model"]
    patch, cell, bath = m["membranes"][0], m["cells"][0], m["extracellular"][0]
    bath["boundary_potential_V"] = 0.025
    for kind in ("membrane_controls", "channel_controls", "pump_controls"):
        for control in raw["experiment"][kind]:
            control["schedule"][0]["availability"] = 0.0
    raw["experiment"]["observation_times"] = [0, duration, 2 * duration]
    spec = parse_spec(raw)
    hist = run(spec).history
    ids = list(spec.model.species_ids)
    with exact.context():
        d = exact.dec
        q = d(current) * d(duration)
        z = {row["id"]: row["valence"] for row in m["species"]}
        faraday = exact.F_C_per_mol() * d("1e-15")
        change = [d(carriers.get(s, 0)) * q / (z[s] * faraday) for s in ids]
        actual_q = sum(n * z[s] * faraday for s, n in zip(ids, change, strict=True))
        volume = d(cell["volume_pL"])

        def free(a):
            return a * ((a / volume).ln() - 1)

        chemical = d(0)
        for s, dn in zip(ids, change, strict=True):
            n = d(cell["initial_amount_fmol"][s])
            chemical += free(n + dn) - free(n)
        chemical *= exact.RT_J_per_mol(m["temperature_K"]) * d("0.001")
        cap, q0 = d(patch["capacitance_F"]), d(cell["initial_charge_C"])
        capacitor = ((q0 + actual_q) ** 2 - q0**2) / (2 * cap) * d("1e12")
        clamp = -actual_q * d(bath["boundary_potential_V"]) * d("1e12")
        work = chemical + capacitor - clamp
    delta = np.array(list(map(float, change)))
    first = [float(actual_q), -float(actual_q), float(clamp), float(work)]
    assert not np.any(hist.extracellular_amount_increment) and not np.any(hist.reservoir_supplied)
    # History contains every accepted step. Read the end of each polarity.
    mid, end = 2, 4
    for index, fraction in ((mid, 1), (end, 0)):
        np.testing.assert_allclose(
            hist.amount_increment[index, :, 0],
            fraction * delta,
            rtol=1e-13,
            atol=64 * np.finfo(float).eps * np.max(np.abs(delta)),
        )
        for field, target in zip(
            (
                "injection_charge_C",
                "electrode_charge_transferred_C",
                "electrode_work_pJ",
                "injection_work_pJ",
            ),
            first,
            strict=True,
        ):
            measured = float(getattr(hist, field)[index, 0])
            assert abs(measured - fraction * target) <= 3e-12 * abs(target), (
                field,
                measured,
                target,
            )
        scale = 1 if index == mid else 2
        np.testing.assert_allclose(
            hist.injection_image_charge_C[index, 0], scale * abs(first[0]), rtol=3e-12, atol=0
        )
        supply = np.maximum(delta, 0) if index == mid else np.abs(delta)
        removal = np.maximum(-delta, 0) if index == mid else np.abs(delta)
        for field, target in (
            ("injection_supplied_fmol", supply),
            ("injection_removed_fmol", removal),
        ):
            np.testing.assert_allclose(
                getattr(hist, field)[index, :, 0], target, rtol=1e-13, atol=0
            )
    actual = float(hist.injection_charge_C[mid, 0])
    assert abs(actual / float(q) - sum(carriers.values())) < 4e-15
    return dict(
        carriers=carriers,
        prescribed_C=float(q),
        positive_charge_C=actual,
        relative_charge_difference=actual / float(q) - 1,
        positive_supply_work_pJ=float(hist.injection_work_pJ[mid, 0]),
        reverse_supply_work_pJ=float(
            hist.injection_work_pJ[end, 0] - hist.injection_work_pJ[mid, 0]
        ),
        clamp_work_pJ=float(hist.electrode_work_pJ[mid, 0]),
        reference_supply_work_pJ=float(work),
    )


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    print(
        json.dumps(
            [
                pulses({"K": k, "M": m})
                for k, m in ((0.5, 0.5), (0.4912, 0.5088), (0.4912, 0.5088000005))
            ],
            indent=2,
            allow_nan=False,
        )
    )
