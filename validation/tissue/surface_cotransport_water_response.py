"""Finite-salt/water/fuel response panel with separately controlled mechanisms.

Rates and initial inventories are inherited unchanged from the manufactured
component fixture. This is a closed, channel-free physical response test, not
a fitted biological preparation or a native BETSE trajectory comparison.
"""

import math

from validation.tissue import surface_cotransport_water_fixtures as base

END_TIME = 0.5
INTERVENTION_TIME = 0.25
DT = 12.5e-6
SUPPLY_AVAILABILITY = 0.1
ARMS = (
    "supply_on",
    "supply_off",
    "supply_recovery",
    "cotransport_blocked",
    "cotransport_release",
    "water_blocked",
)
CONTROL_KINDS = ("membrane", "junction", "channel", "pump", "regeneration", "water", "cotransport")


def definition(arm="supply_on", *, dt=DT, padded=False):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = base.definition("coupled", backend="cpu", padded=padded, dt=dt)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    # Remove populations rather than merely blocking them: blocked gates still
    # have their intrinsic time constants and require the ordinary gate grid.
    m["channels"], e["channel_controls"] = [], []
    x["channel_capacity"] = int(padded)
    for kind in CONTROL_KINDS:
        for group in e[kind + "_controls"]:
            level = SUPPLY_AVAILABILITY if kind == "regeneration" else 1.0
            group["schedule"] = [dict(time=0.0, availability=level)]
    if arm in ("supply_off", "supply_recovery"):
        for group in e["regeneration_controls"]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
            if arm == "supply_recovery":
                group["schedule"].append(
                    dict(time=INTERVENTION_TIME, availability=SUPPLY_AVAILABILITY)
                )
    if arm in ("cotransport_blocked", "cotransport_release"):
        for group in e["cotransport_controls"]:
            group["schedule"] = [dict(time=0.0, availability=0.0)]
            if arm == "cotransport_release":
                group["schedule"].append(dict(time=INTERVENTION_TIME, availability=1.0))
    if arm == "water_blocked":
        e["water_controls"][0]["schedule"] = [dict(time=0.0, availability=0.0)]
    # These are exact integer multiples of every declared refinement grid.
    indices = (
        0,
        40,
        80,
        160,
        400,
        800,
        1600,
        4000,
        8000,
        16000,
        20000,
        20040,
        20080,
        20160,
        20400,
        20800,
        21600,
        24000,
        28000,
        32000,
        40000,
    )
    e.update(end_time=END_TIME, observation_times=[i * DT for i in indices])
    x.update(max_steps=200000, max_trace_bytes=2**30)
    return raw


def refined_recovery_definition(local_times, *, factor=1, stop_time_s=None):
    """Preserve a declared recovery microgrid while refining the whole trajectory.

    By default the supplied boundaries cover the first original step after
    restoration. An explicitly declared, nominal-grid-aligned stop can extend
    that interval into the recovery tail without changing the physical horizon.
    They are numerical inputs, not states or biological events. Each dyadic
    refinement splits both this grid and the nominal timestep; no automatic
    state-dependent grid choice or checkpoint migration occurs here.
    """
    if type(factor) is not int or factor not in (1, 2, 4):
        raise ValueError("The response convergence factors are 1, 2 and 4")
    points = list(local_times)
    original_stop = (round(INTERVENTION_TIME / DT) + 1) * DT
    stop = original_stop if stop_time_s is None else stop_time_s
    if (
        type(stop) not in (int, float)
        or not math.isfinite(stop)
        or not original_stop <= stop <= END_TIME
        or stop != round(stop / DT) * DT
    ):
        raise ValueError("Recovery stop must be a nominal boundary inside the physical horizon")
    if (
        len(points) < 3
        or any(type(t) not in (int, float) or not math.isfinite(t) for t in points)
        or points[0] != INTERVENTION_TIME
        or points[-1] != stop
        or any(a >= b for a, b in zip(points, points[1:], strict=False))
    ):
        raise ValueError("Require exact increasing boundaries of the declared recovery interval")
    for _ in range(factor.bit_length() - 1):
        finer = []
        for left, right in zip(points, points[1:], strict=False):
            middle = (left + right) / 2
            if not left < middle < right:
                raise ValueError("Recovery refinement is below the float clock resolution")
            finer.extend((left, middle))
        points = [*finer, points[-1]]
    raw = definition("supply_recovery", dt=DT / factor)
    raw["execution"]["refinement_times"] = points[1:-1]
    return raw


def duration_inputs(raw):
    """Analytical initial water scale and inventory scales; no Cells imports."""
    m = raw["model"]
    gas = 8.31446261815324
    owners = [*m["cells"], *m["extracellular"]]
    pool = m["energy_pools"][0]["initial_amount_fmol"]
    slopes = []
    for owner, water in zip(owners, m["water_compartments"], strict=True):
        particles = sum(owner["initial_amount_fmol"].values()) + water["impermeant_amount_fmol"]
        if owner["id"] == m["cells"][0]["id"]:
            particles += sum(pool.values())
        slopes.append(
            water["bulk_modulus_Pa"] / water["reference_volume_pL"]
            + gas * m["temperature_K"] * particles / owner["volume_pL"] ** 2
        )
    conductance = (
        m["membranes"][0]["area_m2"]
        * m["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"]
        / 1e-15
    )
    tau = 1 / (conductance * sum(slopes))
    return dict(
        horizon_s=raw["experiment"]["end_time"],
        intervention_s=INTERVENTION_TIME,
        scale_scope="Enabled baseline scales; blocked-arm actual rates may be zero",
        initial_water_linear_tau_s=tau,
        pre_intervention_water_time_constants=INTERVENTION_TIME / tau,
        post_intervention_water_time_constants=(END_TIME - INTERVENTION_TIME) / tau,
        atp_inventory_fmol=pool["ATP"],
        regeneration_upper_rate_fmol_s=(
            m["regeneration_ports"][0]["capacity_fmol_per_s"] * SUPPLY_AVAILABILITY
        ),
        qualification=(
            "Initial time-scale estimates; actual trajectories and late slopes decide settling"
        ),
    )
