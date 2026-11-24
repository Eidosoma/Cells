"""Infer the shared Cl concentration ratio required by the two Freedman Fig. 6 means."""

import json
from itertools import product
from pathlib import Path

import numpy as np

from cells.laws.routes import constant_field_permeation as law


def comparison():
    data = json.loads((Path(__file__).with_name("data") / "freedman1997_chloride.json").read_text())
    fit, target = data["fit"], data["evaluation"]
    v1, v2 = (row["voltage_mV"] for row in (fit, target))
    i1, i2 = (row["current_mA_per_g_Hb"] for row in (fit, target))
    outside = data["outside_Cl_mM"]

    def unit_flux(v, ratio):
        return float(
            law.flux_fmol_s(
                outside * ratio, outside, v / 1000, -1, data["temperature_K"], 1.0, 1.0, 1.0, xp=np
            )
        )

    def predicted(a, b, current, ratio):
        return current * unit_flux(b, ratio) / unit_flux(a, ratio)

    def required(a, b, first, second):
        # At fixed voltages each flux is affine in the concentration ratio.
        # Eliminate the common permeability using the two signed currents.
        def residual(ratio):
            return first * unit_flux(b, ratio) - second * unit_flux(a, ratio)

        low, high = residual(0.5), residual(1.0)
        ratio = 0.5 - 0.5 * low / (high - low)
        assert ratio > 0
        np.testing.assert_allclose(predicted(a, b, first, ratio), second, atol=1e-12, rtol=0)
        return ratio

    ratio = required(v1, v2, i1, i2)
    # Table I's ±0.02 is donor SD of the initial mean ratio. Treat its endpoints
    # as sensitivity examples only. The figure precision below is a separate check.
    table_ratios = [0.65, 0.67, 0.69]
    precision = data["figure_reading_precision"]
    dv, di = precision["voltage_mV"], precision["current_mA_per_g_Hb"]
    corners = [
        required(v1 + x * dv, v2 + y * dv, i1 + z * di, i2 + w * di)
        for x, y, z, w in product((-1, 1), repeat=4)
    ]
    return dict(
        required_inside_over_outside=ratio,
        required_inside_mM=outside * ratio,
        table_ratio_sensitivity=table_ratios,
        predicted_mA_per_g_Hb=[predicted(v1, v2, i1, r) for r in table_ratios],
        figure_corner_range_ratio=[min(corners), max(corners)],
    )


if __name__ == "__main__":
    print(json.dumps(comparison(), indent=2, allow_nan=False))
