"""Scheduled ECM stage inputs on the complete water/repair owners.

The inherited 50-us controls and physical parameters are unchanged. Pulse,
padding and order variants are manufactured numerical cases, not independent
biological observations or qualified evolved trajectories.
"""

from copy import deepcopy

from validation.transport import environment_barrier_composition_fixtures as static

FAMILIES = ("water", "repair")
CASES = (
    "partial",
    "duplicate",
    "INIT",
    "none",
    "zeroamp",
    "asymmetric_modulators",
    "zero_endpoint",
    "close-reopen",
)
TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"
MODEL_IDS = {
    "water": "resolved_calcium_energy_water_extracellular_barriers@1",
    "repair": "resolved_calcium_energy_water_repair_extracellular_barriers@1",
}
DT_S = 0.25e-6


def inputs(family="water", case="partial", *, permuted=False, padded=True):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    static_case = case if case in ("asymmetric_modulators", "zero_endpoint") else "overlap"
    request = static.request(family, static_case, permuted=permuted, padded=padded)
    if case == "close-reopen":
        # Initial tight boundary Na diffusivity is zero, while other charged
        # species retain return paths. The pulse opens and subsequently closes
        # those Na routes without a floor or an artificial conductance.
        request["relative_TJ"]["Na"] = 0.0
    raw = request["definition"]
    raw["execution"]["dt"] = DT_S
    event = {
        "name": "owned_ecm_pulse",
        "site_ids": ["outside_1", "outside_2"],
        "on_s": 10e-6,
        "off_s": 30e-6,
        "change_s": 4e-6,
        "amplitude": 0.75,
    }
    if case == "duplicate":
        event["site_ids"] = ["outside_1", "outside_2", "outside_1", "outside_2"]
    if case == "zeroamp":
        event["amplitude"] = 0.0
    if case == "close-reopen":
        event["amplitude"] = 1.0
    if permuted:
        event["site_ids"].reverse()
    if case == "none":
        event = None
    e = raw["experiment"]
    times = {0.0, e["end_time"], *e["observation_times"], 10e-6, 20e-6, 30e-6}
    for key, groups in e.items():
        if key.endswith("_controls"):
            times.update(
                row["time"]
                for group in groups
                for row in group.get("controls", group.get("schedule", []))
            )
    e["observation_times"] = sorted(times)
    carrier = e["membrane_controls"][0]["schedule"]
    for time in e["observation_times"]:
        if time == e["end_time"] or any(row["time"] == time for row in carrier):
            continue
        value = deepcopy(next(row for row in reversed(carrier) if row["time"] <= time))
        value["time"] = time
        carrier.append(value)
        carrier.sort(key=lambda row: row["time"])
    return dict(
        request=request,
        intervention=event,
        phase="INIT" if case == "INIT" else "SIM",
        timing_policy=TIMING_POLICY,
        barrier_target_capacity=(0 if event is None else len(event["site_ids"])) + int(padded),
    )
