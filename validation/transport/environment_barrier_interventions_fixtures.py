"""Pure-data initial/transient cases for the single native ECM-opening pulse.

The caller seals the static request through its preparation bridge. These
manufactured cases change no underlying rates or physical inventories to make
an integration finish sooner. No production or accelerator imports occur.
"""

from validation.transport.environment_barrier_preparation_fixtures import request

MODEL_ID = "resolved_extracellular_barriers@1"
TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"
CASES = (
    "partial",
    "duplicate",
    "blocked",
    "open",
    "reseal",
    "init",
    "none",
    "zero_species",
    "asymmetric_modulators",
    "unit_factors",
)


def inputs(case="partial", *, permuted=False, padded=False):
    """Return the static recipe and explicit dynamic declarations.

    Root's factory supplies the exact replayable preparation artifact. Physical
    duration is 10 us, covering the opening and return of the logistic pulse;
    this is a coupling transient and does not establish tissue equilibration.
    """
    case = "init" if case == "INIT" else case
    if case not in CASES:
        raise ValueError(f"Unknown ECM intervention case {case!r}")
    static_case = (
        case if case in ("zero_species", "asymmetric_modulators", "unit_factors") else "overlap"
    )
    raw = request(static_case, permuted=permuted, padded=padded)
    definition = raw["definition"]
    dt, end = 62.5e-9, 10e-6
    definition["execution"].update(dt=dt, max_steps=4096)
    experiment = definition["experiment"]
    experiment["end_time"] = end
    by_owner = {row["membrane_id"]: row for row in experiment["membrane_controls"]}
    by_owner["membrane_0_sw"]["schedule"].append({"time": 3.3e-6, "availability": 0.7})
    by_owner["membrane_1_ne"]["schedule"].append({"time": 7.7e-6, "availability": 0.4})
    intervention = {
        "name": "ecm_opening",
        "site_ids": ["se", "nw"],
        "on_s": 2e-6,
        "off_s": 7e-6,
        "change_s": 1e-6,
        "amplitude": 0.65,
    }
    if case == "duplicate":
        intervention["site_ids"] = ["se", "nw", "se", "nw"]
    elif case == "blocked":
        intervention["amplitude"] = 0.0
    elif case in ("open", "reseal"):
        intervention["site_ids"] = list(raw["grid"]["site_ids"])
        intervention["amplitude"] = 1.0 if case == "open" else 0.9
        if case == "reseal":
            intervention["off_s"] = 5e-6
    elif case == "none":
        intervention = None
    times = {0.0, end, 1e-6, 2e-6, 3e-6, 3.3e-6, 5e-6, 6e-6, 7e-6, 7.7e-6, 8e-6, 9e-6}
    if intervention is not None:
        times.update((intervention["on_s"], intervention["off_s"]))
    # Ordinary observations use nominal integer ticks; controls retain their
    # distinct absolute times. No rounded near-duplicate boundaries are added.
    controls = {3.3e-6, 7.7e-6}
    experiment["observation_times"] = sorted(
        time if time in controls else round(time / dt) * dt for time in times
    )
    # Use exactly the same values in event metadata and the nominal grid.
    experiment["end_time"] = 160 * dt
    if intervention is not None:
        for key in ("on_s", "off_s"):
            intervention[key] = round(intervention[key] / dt) * dt
    # Preserve every requested boundary in the ordinary absolute-time event
    # grid. These carrier rows leave the physical availability unchanged.
    by_owner["membrane_0_sw"]["schedule"] = [
        {"time": time, "availability": 0.7 if time >= 3.3e-6 else 1.0}
        for time in experiment["observation_times"]
    ]
    return {
        "request": raw,
        "intervention": intervention,
        "phase": "INIT" if case == "init" else "SIM",
        "timing_policy": TIMING_POLICY,
        "barrier_target_capacity": (0 if intervention is None else len(intervention["site_ids"]))
        + int(padded),
    }
