"""Independent mixed-input oracle using the established Decimal laws.

The junction-only loop is retained from junction_reference without changing
that frozen source. Pump/channel checks consume independently reconstructed
per-step inputs; no evolving Cells state enters the native oracle.
"""

import numpy as np

from validation.betse.junction_gate.reference import rates as decimal_rates
from validation.betse.junction_transport.check import decimal_flux
from validation.betse.spatial_active import intervention_reference, junction_reference, reference


def inputs(row, protocol):
    assert row["case"]["junction_changes"] == [
        dict(time_s=e["time_s"], fraction=e["junction_fraction"])
        for e in row["case"]["interventions"]
    ]
    return intervention_reference.step_rows(row), junction_reference.inputs(row, protocol)


def native_check(row, trace, protocol):
    rows, blocks = inputs(row, protocol)
    ordered = protocol | {"species": row["case"]["moving_order"]}
    report = reference.native_check(row, trace, ordered, step_rows=rows)
    g, p, a = row["geometry"], row["parameters"], row["arrays"]
    partners, area = np.asarray(g["nn_i"], dtype=int), np.asarray(g["mem_sa"])
    ids = [row["species"][name] for name in row["case"]["moving_order"]]
    indices = np.flatnonzero((trace["method"] == 0) & ~trace["after"])
    assert len(indices) == row["steps"] * len(ids)
    maximum_gate = maximum_flux = 0.0
    calls = 0
    for count, index in enumerate(indices):
        step, slot = divmod(count, len(ids))
        ion = ids[slot]
        assert trace["step"][index] == step and trace["ion"][index] == ion
        assert trace["method"][index + 1] == 0 and trace["after"][index + 1]
        voltage = trace["vm"][index, partners] - trace["vm"][index]
        alpha, beta = decimal_rates(voltage, protocol["junction"]["threshold_voltage_V"])
        opening = (
            trace["gjopen"][index]
            + row["dt_s"] * (alpha + beta * protocol["junction"]["minimum_open_fraction"])
        ) / (1 + row["dt_s"] * (alpha + beta))
        opening *= blocks[step]
        np.testing.assert_allclose(
            trace["gjopen"][index + 1],
            opening,
            atol=protocol["tolerances"]["gate_atol"],
            rtol=protocol["tolerances"]["gate_rtol"],
        )
        maximum_gate = max(maximum_gate, float(np.max(abs(trace["gjopen"][index + 1] - opening))))
        ci = trace["cc_at_mem"][index, ion]
        coefficient = np.asarray(a["D_gj"])[ion] * protocol["gj_surface_fraction"] / g["gj_len"]
        flux = np.array(
            [
                decimal_flux(left, right, -dv, a["zs"][ion], p["T"], sa, per, 1.0, op, p)
                for left, right, dv, sa, per, op in zip(
                    ci, ci[partners], voltage, area, coefficient, opening, strict=True
                )
            ]
        )
        flux[np.asarray(g["bflags_mems"], dtype=int)] = 0
        actual = (trace["fluxes_gj"][index + 1, ion] - trace["fluxes_gj"][index, ion]) * area * 1e15
        np.testing.assert_allclose(
            actual,
            flux,
            atol=protocol["native_update_tolerances"]["flux_atol_fmol_s"],
            rtol=protocol["native_update_tolerances"]["flux_rtol"],
        )
        maximum_flux = max(maximum_flux, float(np.max(abs(actual - flux))))
        calls += len(area)
    return report | dict(
        junction_gate_compared_scalars=calls,
        junction_flux_compared_scalars=calls,
        max_junction_gate_error=maximum_gate,
        max_junction_flux_error_fmol_s=maximum_flux,
    )
