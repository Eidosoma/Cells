"""Independent dynamic junction clock, implicit recurrence and scalar flux checks.

No Cells/BETSE numerical imports. Decimal rates and fluxes are reused from
the earlier isolated-junction oracle; complete active spatial accounting is
shared with the prior qualification.
"""

import numpy as np

from validation.betse.junction_gate.reference import rates as decimal_rates
from validation.betse.junction_transport.check import decimal_flux
from validation.betse.spatial_active import reference


def inputs(row, protocol):
    case, record = row["case"], row["fixture"]["junction_inputs"]
    dynamic = row["fixture"]["dynamic_junction"]
    assert record["events"] == case["junction_changes"]
    assert record["clock"] == "completed_updates_times_dt" and not record["native_methods_replaced"]
    assert dynamic["clock"] == "one_outer_dt_per_moving_ion"
    assert dynamic["blocking"] == "multiply_stored_opening_after_each_implicit_update"
    assert dynamic["calls_per_step"] == len(case["moving_order"])
    assert dynamic["threshold_voltage_V"] == protocol["junction"]["threshold_voltage_V"]
    assert dynamic["minimum_open_fraction"] == protocol["junction"]["minimum_open_fraction"]
    assert dynamic["native_source_sha256"] == protocol["junction"]["native_source_sha256"]
    assert len(record["steps"]) == row["steps"]
    blocks = []
    for step, captured in enumerate(record["steps"]):
        index = max(
            i
            for i, e in enumerate(case["junction_changes"])
            if round(e["time_s"] / row["dt_s"]) <= step
        )
        expected = np.asarray(dynamic["base_block"]) * case["junction_changes"][index]["fraction"]
        assert captured["index"] == step and captured["event_index"] == index
        assert captured["before_elapsed_s"] == step * row["dt_s"]
        np.testing.assert_array_equal(captured["block"], expected)
        blocks.append(expected)
    return np.stack(blocks)


def native_check(row, trace, protocol):
    blocks = inputs(row, protocol)
    ordered = protocol | {"species": row["case"]["moving_order"]}
    report = reference.native_check(row, trace, ordered)
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


def compare(row, trace, tol, tissue, active, rates, observed, opening, calls):
    report = reference.compare(row, trace, tol, tissue, active, rates, observed)
    final = np.flatnonzero((trace["method"] == 3) & trace["after"])
    ids = [row["species"][name] for name in row["case"]["moving_order"]]
    per_ion = np.stack(
        [
            trace["gjopen"][(trace["method"] == 0) & trace["after"] & (trace["ion"] == ion)]
            for ion in ids
        ],
        axis=1,
    )
    count, errors = 0, {}
    for name, actual, expected in (
        ("junction_open", opening, trace["gjopen"][final]),
        ("junction_after_ion", calls, per_ion),
    ):
        assert actual.shape == expected.shape and np.isfinite(actual).all()
        budget = tol["gate_atol"] + tol["gate_rtol"] * abs(expected)
        relative = abs(actual - expected) / budget
        np.testing.assert_allclose(relative, 0, atol=1, rtol=0, err_msg=name)
        errors[name] = float(np.max(abs(actual - expected)))
        report["max_error_over_budget"] = max(
            report["max_error_over_budget"], float(np.max(relative))
        )
        count += actual.size
    report.update(junction_compared_scalars=count, junction_max_errors=errors)
    report["compared_scalars"] += count
    return report
