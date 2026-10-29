"""Full56 manufactured owners with one native extracellular opening pulse.

The static recipe retains the complete physical model. The caller seals that
recipe through the qualified complete-owner bridge. These synthetic coupling
inputs establish neither tissue equilibration nor a biological calibration.
"""

from copy import deepcopy

from validation.transport import environment_barrier_composition_fixtures as static

FAMILIES = ("ionic", "calcium", "energy")
MODEL_IDS = dict(
    ionic="resolved_active_extracellular_barriers@1",
    calcium="resolved_calcium_extracellular_barriers@1",
    energy="resolved_calcium_energy_extracellular_barriers@1",
)
PARENT_IDS = dict(
    ionic="resolved_tissue@12", calcium="resolved_calcium@11", energy="resolved_calcium_energy@5"
)
TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"
CASES = ("partial", "duplicate", "init", "none", "blocked", "asymmetric", "reseal")


def inputs(family="energy", case="partial", *, permuted=False, padded=False):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    recipe = static.request(
        family,
        "zero_endpoint"
        if case == "reseal"
        else "asymmetric_modulators"
        if case == "asymmetric"
        else "overlap",
        permuted=permuted,
        padded=padded,
    )
    if case == "reseal":
        # Sodium closes at TJ sites while other charged species retain the
        # field's required return paths. The event can reopen those Na routes;
        # fixed zero modulators remain closed throughout.
        recipe["relative_TJ"]["Na"] = 0.0
    raw = recipe["definition"]
    dt, end = 62.5e-9, 160 * 62.5e-9
    raw["execution"].update(dt=dt, max_steps=4096)
    experiment = raw["experiment"]
    experiment["end_time"] = end
    for name, groups in experiment.items():
        if name.endswith("_controls"):
            for row in groups:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [v for v in row[key] if v["time"] <= end]
    # Explicit held-control changes exercise each full owner's own controls.
    # Source physical parameters, stores, pumps and pool inventories stay as
    # declared by the complete fixture; no rates are weakened for runtime.
    for name, time in (
        ("channel_controls", 3.3e-6),
        ("pump_controls", 7.7e-6),
        ("regeneration_controls", 5.1e-6),
    ):
        if name in experiment and experiment[name]:
            row = experiment[name][0]
            change = deepcopy(row["schedule"][0])
            change.update(time=time, availability=0.37)
            row["schedule"] = sorted(
                [v for v in row["schedule"] if v["time"] != time] + [change],
                key=lambda v: v["time"],
            )
    event = dict(
        name="complete_ecm_opening",
        site_ids=["outside_1", "outside_2"],
        on_s=32 * dt,
        off_s=112 * dt,
        change_s=1e-6,
        amplitude=0.65,
    )
    if case == "duplicate":
        event["site_ids"] *= 2
    if case == "blocked":
        event["amplitude"] = 0.0
    if case == "none":
        event = None
    if case == "reseal":
        event.update(site_ids=list(recipe["grid"]["site_ids"]), off_s=64 * dt, amplitude=1.0)
    times = {i * dt for i in (0, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160)}
    for name, groups in experiment.items():
        if name.endswith("_controls"):
            for row in groups:
                times.update(v["time"] for v in row.get("controls", row.get("schedule", [])))
    experiment["observation_times"] = sorted(times)
    # Unchanged-value carrier rows preserve each observation as an accepted
    # event boundary, including off-tick held-control changes.
    carrier = experiment["membrane_controls"][0]
    previous = deepcopy(carrier["schedule"])
    carrier["schedule"] = [
        dict(
            time=t,
            availability=next(v["availability"] for v in reversed(previous) if v["time"] <= t),
        )
        for t in sorted(times | {v["time"] for v in previous})
    ]
    return dict(
        request=recipe,
        intervention=event,
        phase="INIT" if case == "init" else "SIM",
        timing_policy=TIMING_POLICY,
        barrier_target_capacity=(0 if event is None else len(event["site_ids"])) + int(padded),
    )


def assemble(values, prepared):
    """Combine a bridge result with plain event declarations, without rebinding physics."""
    raw = deepcopy(prepared.definition)
    family = next(k for k, v in PARENT_IDS.items() if v == raw["model"]["id"])
    raw["model"].update(
        id=MODEL_IDS[family],
        barrier_preparation=dict(
            definition=deepcopy(prepared.definition), provenance=deepcopy(prepared.provenance)
        ),
        intervention=deepcopy(values["intervention"]),
        phase=values["phase"],
        timing_policy=values["timing_policy"],
    )
    raw["execution"]["barrier_target_capacity"] = values["barrier_target_capacity"]
    return raw
