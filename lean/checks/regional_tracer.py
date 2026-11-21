"""Compare FR-33's two Lean claims with the maintained Cells examples on CPU float64."""

import json

import jax
import numpy as np

from cells.definitions.pump_composite_spec import identity
from validation.compartment_transfer import example as control
from validation.regions import example, readouts


def largest(values):
    return float(np.max(np.abs(values)))


def cohort_balance(trace, cohort, first, region, nodes, routes):
    """Compare the actual region, its complement and clearance since the selected row."""
    amount = trace["amount"][cohort]
    loss = trace["loss"][cohort]

    def total(series, selected):
        return sum(
            (np.asarray(series[n][first:]) for n in selected),
            start=np.zeros(len(trace["times"]) - first),
        )

    inside = total(amount, region)
    outside = total(amount, [n for n in nodes if n not in region])
    all_loss = total(loss, nodes)
    region_loss = total(loss, region)
    cut = np.zeros_like(inside)
    for route in routes:
        sign = int(route["destination"] in region) - int(route["source"] in region)
        moved = np.asarray(trace["transfer"][cohort][route["id"]][first:])
        cut += sign * (moved - moved[0])

    initial = inside[0] + outside[0]
    new_loss = all_loss - all_loss[0]
    whole_error = largest(inside + outside + new_loss - initial)
    region_error = largest(inside - inside[0] + (region_loss - region_loss[0]) - cut)
    # Each recorded endpoint includes the rounding of preceding solves and bookings.
    tolerance = readouts.CLOSURE_ULPS * np.finfo(float).eps * len(inside) * initial
    if not (
        0 < initial
        and whole_error <= tolerance
        and region_error <= tolerance
        and new_loss[-1] > tolerance
    ):
        raise AssertionError(f"{cohort} balance: {whole_error}, {region_error}, bound {tolerance}")
    return {
        "rows": len(inside),
        "start_s": trace["times"][first],
        "region": region,
        "initial_label_fmol": initial,
        "label_inside_final_fmol": inside[-1],
        "label_outside_final_fmol": outside[-1],
        "loss_at_start_fmol": all_loss[0],
        "loss_since_start_fmol": new_loss[-1],
        "net_label_into_region_fmol": cut[-1],
        "max_whole_residual_fmol": whole_error,
        "max_region_residual_fmol": region_error,
        "tolerance_fmol": tolerance,
    }


def pulse_chase():
    run = example.run()
    spec, _, _ = run
    out = example.exports(run)
    trace = out["trace"]
    nodes = out["ST"]["cell_nodes"]
    routes = readouts.world_map(spec, control.ST)["routes"]
    if set(nodes) != {control.CELL, control.NODE_T, control.NODE_D} or [
        (r["id"], r["source"], r["destination"]) for r in routes
    ] != [("release", control.NODE_T, control.CELL)]:
        raise AssertionError("Expected one closed cell with its two compartments and one release")

    donor = cohort_balance(trace, "from_ecs_0", 0, [control.NODE_T], nodes, routes)
    switch = readouts.step_index(trace["times"], example.T_PULSE, "the end of the pulse")
    pulse = cohort_balance(trace, "pulse", switch, [control.CELL], nodes, routes)
    if not (
        pulse["loss_at_start_fmol"] > pulse["tolerance_fmol"]
        and trace["amount"]["chase"][control.CELL][-1] > pulse["tolerance_fmol"]
    ):
        raise AssertionError(
            "The pulse needs prior clearance and ongoing production into the chase"
        )
    # Only the donor cohort enters this route. Check the tracer's book against the engine counter.
    sampled = [
        readouts.step_index(trace["times"], t, "the engine sample") for t in out["ST"]["times"]
    ]
    transfer = np.asarray(trace["transfer"]["from_ecs_0"]["release"])[sampled]
    engine_transfer_error = largest(transfer - out["ST"]["transfer_fmol"]["release"])
    if not (
        donor["net_label_into_region_fmol"] < -donor["tolerance_fmol"]
        and engine_transfer_error <= donor["tolerance_fmol"]
    ):
        raise AssertionError(
            "Expected resolved export of the old donor label at the recorded route"
        )
    return {
        **identity(spec.model),
        "step_s": spec.execution.dt,
        "end_s": trace["times"][-1],
        "donor_cohort": donor,
        "pulse_cohort": pulse,
        "max_route_error_against_engine_fmol": engine_transfer_error,
    }


def matched_donors():
    out = control.exports()
    times = np.asarray(out["times"])
    transfer, degradation = out["T"], out["D"]
    donor = np.asarray(transfer["donor_fmol"])
    initial = donor[0]
    withdrawn = initial - donor
    received = np.asarray(transfer["receiver_fmol"]) - transfer["receiver_fmol"][0]
    unmoved = np.asarray(degradation["receiver_fmol"]) - degradation["receiver_fmol"][0]
    expected = initial * np.exp(-control.KAPPA * times)
    residuals = {
        "donor_difference": largest(donor - degradation["donor_fmol"]),
        "donor_against_exponential": largest(donor - expected),
        "receiver_credit": largest(received - withdrawn),
        "exchange_book": largest(transfer["transfer_fmol"] - withdrawn),
        "transfer_arm_loss": largest(transfer["loss_fmol"]),
        "degradation_arm_receiver_gain": largest(unmoved),
        "degradation_book": largest(degradation["loss_fmol"] - withdrawn),
    }
    tolerance = 1e-12 * initial  # The maintained control's donor tolerance, in fmol here.
    if not (
        np.all(np.isfinite(list(residuals.values())))
        and max(residuals.values()) <= tolerance
        and len(times) > 1
        and times[0] == 0
        and np.all(withdrawn[times > 0] > tolerance)
    ):
        raise AssertionError(f"Matched donors: {residuals}, bound {tolerance}")
    return {
        "rows": len(times),
        "initial_donor_fmol": initial,
        "end_s": times[-1],
        "final_donor_fmol": donor[-1],
        "transfer_receiver_gain_fmol": received[-1],
        "degradation_receiver_gain_fmol": unmoved[-1],
        "transfer_loss_fmol": transfer["loss_fmol"][-1],
        "degradation_loss_fmol": degradation["loss_fmol"][-1],
        "max_residuals_fmol": residuals,
        "tolerance_fmol": tolerance,
    }


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        print(
            json.dumps(
                {"pulse_chase": pulse_chase(), "matched_donors": matched_donors()},
                indent=2,
                allow_nan=False,
            )
        )
