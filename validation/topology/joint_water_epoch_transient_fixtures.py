"""Full epoch inputs derived from the completed compact profile trajectories."""

from copy import deepcopy

FAMILIES = ("water", "repair")
CASES = ("changed-controls", "close-reopen")
DATASETS = (
    "INIT-water",
    "INIT-repair",
    "SIM-water-changed-controls",
    "SIM-water-close-reopen",
    "SIM-repair-changed-controls",
    "SIM-repair-close-reopen",
)
EXTRA = {"id", "profile_preparation", "interventions", "phase", "timing_policy", "reset_policy"}


def scaled(value, factor):
    if isinstance(value, dict):
        return {k: (v if k == "time" else scaled(v, factor)) for k, v in value.items()}
    if isinstance(value, list):
        return [scaled(v, factor) for v in value]
    return value * factor if type(value) in (int, float) else value


def observations(raw):
    experiment = raw["experiment"]
    times = {0.0, experiment["end_time"], *experiment["observation_times"]}
    for name, rows in experiment.items():
        if name.endswith("_controls"):
            times.update(
                c["time"]
                for row in rows
                for c in row["controls" if "controls" in row else "schedule"]
            )
    experiment["observation_times"] = sorted(times)
    carrier = experiment["membrane_controls"][0]["schedule"]
    for time in sorted(times):
        if time == experiment["end_time"] or any(c["time"] == time for c in carrier):
            continue
        held = deepcopy(next(c for c in reversed(carrier) if c["time"] <= time))
        held["time"] = time
        carrier.append(held)
        carrier.sort(key=lambda c: c["time"])
    return raw


def definitions(qualified_sim, qualified_closure):
    """Keep the exact qualified model, profiles, coefficients and physical capacities."""
    assert {k: v for k, v in qualified_sim["model"].items() if k not in EXTRA} == {
        k: v for k, v in qualified_closure["model"].items() if k not in EXTRA
    }
    assert (
        qualified_sim["model"]["profile_preparation"]
        == qualified_closure["model"]["profile_preparation"]
    )
    init = deepcopy(qualified_sim)
    init["model"]["phase"] = "INIT"
    assert init["experiment"]["end_time"] == 4e-6
    assert init["execution"]["dt"] == 0.03125e-6
    result = {"INIT": observations(init)}
    for case in CASES:
        target = deepcopy(init)
        target["model"]["phase"] = "SIM"
        for i, (name, rows) in enumerate(
            (n, r) for n, r in target["experiment"].items() if n.endswith("_controls")
        ):
            for j, row in enumerate(rows):
                key = "controls" if "controls" in row else "schedule"
                first = deepcopy(row[key][0])
                first = scaled(first, 0.45)
                first["time"] = 0.0
                row[key] = [first]
                if j == 0:
                    off, reopened = (
                        scaled(first, 0.0),
                        scaled(deepcopy(init["experiment"][name][j][key][0]), 0.8),
                    )
                    off["time"] = (1.375 + 0.125 * (i % 4)) * 1e-6
                    reopened["time"] = (2.375 + 0.125 * (i % 4)) * 1e-6
                    row[key] += [off, reopened]
        if case == "close-reopen":
            target["model"]["interventions"] = deepcopy(qualified_closure["model"]["interventions"])
            for name in ("intervention_capacity", "intervention_target_capacity"):
                target["execution"][name] = qualified_closure["execution"][name]
        result[case] = observations(target)
    return result
