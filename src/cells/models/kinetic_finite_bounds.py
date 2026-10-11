"""Conservative host-only enclosures of a kinetic finite-bath cubic interval.

Bernstein control hulls avoid uncertain extrema-root rounding. Basic arithmetic
is rounded outwards with nextafter; logs include 64 epsilon of absolute/relative
allowance (an explicit libm assumption, not a correctly-rounded-log theorem).
Refusal means unable to certify, not necessarily an actually unsafe trajectory.
"""

import numpy as np

from cells.core.errors import NumericalError
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.processes.kinetic_pump import MAX_ABS_AFFINITY_OVER_RT, MAX_ABS_ION_POTENTIAL_OVER_RT


def outward(lo, hi):
    with np.errstate(under="ignore", over="ignore", invalid="ignore"):
        return np.nextafter(lo, -np.inf), np.nextafter(hi, np.inf)


def point(value):
    return np.asarray(value), np.asarray(value)


def add(a, b):
    return outward(a[0] + b[0], a[1] + b[1])


def scale(a, value):
    x, y = a[0] * value, a[1] * value
    return outward(np.minimum(x, y), np.maximum(x, y))


def subtract(a, b):
    return add(a, (-b[1], -b[0]))


def divide_positive(a, value):
    return outward(a[0] / value, a[1] / value)


def log_interval(a):
    if np.any(a[0] <= 0) or not np.isfinite(a).all():
        raise NumericalError(
            "Unable to certify kinetic cubic: concentration enclosure is not positive finite"
        )
    lo, hi = np.log(a[0]), np.log(a[1])
    allowance = 64 * np.finfo(float).eps * np.maximum(1.0, np.maximum(np.abs(lo), np.abs(hi)))
    return outward(lo - allowance, hi + allowance)


def cubic_hull(times, values, left, right):
    """Enclose the exact Hermite polynomial for the represented binary inputs.

    dt subtraction, products and division by three are separately widened. The
    hull is deliberately looser than the existing floating extrema estimate.
    """
    shape = (-1,) + (1,) * (values.ndim - 1)
    h = subtract(point(np.asarray(times)[1:]), point(np.asarray(times)[:-1]))
    h = tuple(v.reshape(shape) for v in h)
    a = divide_positive(scale(h, left), 3.0)
    b = divide_positive(scale(h, right), 3.0)
    points = (
        point(values[:-1]),
        add(point(values[:-1]), a),
        subtract(point(values[1:]), b),
        point(values[1:]),
    )
    return np.minimum.reduce([v[0] for v in points]), np.maximum.reduce([v[1] for v in points])


def sum_species(a):
    # Sequential outward additions rather than an unbounded reduction error.
    result = point(np.zeros(a[0].shape[:-2] + a[0].shape[-1:]))
    for i in range(a[0].shape[-2]):
        result = add(result, (a[0][..., i, :], a[1][..., i, :]))
    return result


def pump_enclosures(times, history, f0, f1, layout, *, inside=None):
    increments = cubic_hull(
        times, history.amount_increment, f0.amount_increment, f1.amount_increment
    )
    outside = cubic_hull(
        times,
        history.extracellular_amount_increment,
        f0.extracellular_amount_increment,
        f1.extracellular_amount_increment,
    )
    if inside is None:
        inside = add(increments, point(layout.amount_reference))
    outside = add(outside, point(layout.extracellular_amount_reference))
    present = np.flatnonzero(layout.pump_present)
    owners, out = layout.owners[present], layout.outside_owners[present]
    na, k = layout.pump_sodium_species[present], layout.pump_potassium_species[present]

    def concentration_log(bounds, species, indices, volume):
        selected = tuple(v[..., species, indices] for v in bounds)
        return log_interval(divide_positive(selected, volume[indices]))

    ni = concentration_log(inside, na, owners, layout.volume)
    no = concentration_log(outside, na, out, layout.extracellular_volume)
    ki = concentration_log(inside, k, owners, layout.volume)
    ko = concentration_log(outside, k, out, layout.extracellular_volume)
    charge = sum_species(scale(increments, layout.valence))
    dv = divide_positive(scale(charge, CHARGE_PER_FMOL), layout.capacitance[layout.cell_membranes])
    voltage = add(point(layout.voltage_reference), dv)
    voltage = tuple(v[..., owners] for v in voltage)
    rt = R * layout.temperature[out]
    electrical = divide_positive(scale(voltage, F), rt)
    mu_na, mu_k = add(subtract(ni, no), electrical), add(subtract(ki, ko), electrical)
    # Derive the drive again from the declared pools, rather than treating a
    # rounded precomputed drive as an exact thermodynamic authority.
    drive = divide_positive(point(layout.pump_delta_g0_J_mol[present]), rt)
    for name, sign in (("adp_mM", 1), ("pi_mM", 1), ("atp_mM", -1)):
        drive = add(
            drive, scale(log_interval(point(getattr(layout, "pump_" + name)[present])), sign)
        )
    drive = subtract(drive, log_interval(point(1000.0)))
    # Combine the voltage coefficient only once: -3 mu_Na + 2 mu_K.
    chemical = add(scale(subtract(ni, no), -3), scale(subtract(ki, ko), 2))
    affinity = subtract(add(drive, chemical), electrical)

    # Cover RT/coefficient rounding and the alternate evaluation order in the
    # process implementation; no widening of the declared physical domain.
    def guarded(a):
        margin = (
            128
            * np.finfo(float).eps
            * (
                1
                + np.maximum(np.abs(a[0]), np.abs(a[1]))
                + np.maximum(np.abs(drive[0]), np.abs(drive[1]))
                + 3 * np.maximum(np.abs(mu_na[0]), np.abs(mu_na[1]))
                + 2 * np.maximum(np.abs(mu_k[0]), np.abs(mu_k[1]))
            )
        )
        return outward(a[0] - margin, a[1] + margin)

    return guarded(mu_na), guarded(mu_k), guarded(affinity)


def check_pump_interpolants(times, history, f0, f1, layout, *, inside=None):
    if len(times) < 2 or not np.any(layout.pump_present):
        return
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        bounds = pump_enclosures(times, history, f0, f1, layout, inside=inside)
    for interval, limit in zip(
        bounds,
        (MAX_ABS_ION_POTENTIAL_OVER_RT, MAX_ABS_ION_POTENTIAL_OVER_RT, MAX_ABS_AFFINITY_OVER_RT),
        strict=True,
    ):
        if (
            not np.isfinite(interval).all()
            or np.any(interval[0] < -limit)
            or np.any(interval[1] > limit)
        ):
            raise NumericalError(
                "Unable to certify kinetic cubic interior within the pump domain; no clipping"
            )
