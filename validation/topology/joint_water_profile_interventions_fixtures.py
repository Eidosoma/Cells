"""Explicit full56 water/repair owners and native regional pulse declarations."""

from copy import deepcopy

from validation.tissue import calcium_energy_water_hcn_extra_fixtures as water
from validation.tissue import calcium_energy_water_repair_hcn_extra_fixtures as repair
from validation.topology import owned_calcium_profile_interventions_fixtures as native

FAMILIES = ("water", "repair")
CASES = ("SIM", "INIT", "close-reopen", "ion-flags", "empty-events")


def inputs(family="water", case="SIM", *, padded=True):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    result = native.inputs("fuel5", case)
    raw = (
        water.definition("release", padded=padded)
        if family == "water"
        else repair.definition("preinjured", parent="release", padded=padded)
    )
    assert {p["id"] for p in raw["model"]["ionic"]["membranes"]} == set(
        result["geometry"]["layout"]["membrane_ids"]
    )
    experiment = raw["experiment"]
    experiment.update(
        end_time=4e-6,
        observation_times=[
            v * 1e-6 for v in (0, 0.75, 1, 1.125, 1.5, 2, 2.5, 2.875, 3, 3.125, 3.5, 4)
        ],
    )
    for i, (name, rows) in enumerate(
        (name, rows) for name, rows in experiment.items() if name.endswith("_controls")
    ):
        for j, row in enumerate(rows):
            key = "controls" if "controls" in row else "schedule"
            first = deepcopy(row[key][0])
            first["time"] = 0.0
            if name == "injury_controls" and j == 0:
                first["injury"] = 0.7
            row[key] = [first]
            if j == 0:
                off = 1.25e-6 + (i % 9) * 0.125e-6
                closed = native._scaled(first, 0.0)
                closed["time"] = off
                reopened = native._scaled(first, 0.7)
                reopened["time"] = off + 0.75e-6
                row[key] += [closed, reopened]
            if name == "channel_controls" and row["channel_id"] in ("hcn_extra_0", "hcn_extra_2"):
                row[key] += [
                    dict(time=1.125e-6, availability=0.0),
                    dict(time=2.625e-6, availability=0.6),
                ]
                row[key].sort(key=lambda v: v["time"])
    times = set(experiment["observation_times"])
    for name, groups in experiment.items():
        if name.endswith("_controls"):
            times.update(
                v["time"]
                for row in groups
                for v in row["controls" if "controls" in row else "schedule"]
            )
    experiment["observation_times"] = sorted(times)
    # Explicit unchanged-value knots make every requested transient sample an
    # accepted production boundary, without resampling any control.
    carrier = experiment["membrane_controls"][0]["schedule"]
    for time in sorted(times):
        if time == experiment["end_time"] or any(v["time"] == time for v in carrier):
            continue
        held = deepcopy(next(v for v in reversed(carrier) if v["time"] <= time))
        held["time"] = time
        carrier.append(held)
        carrier.sort(key=lambda v: v["time"])
    raw["execution"].update(dt=0.03125e-6, jit=False, max_steps=2048, max_trace_bytes=2**28)
    result["definition"] = raw
    # Declared manufactured coefficients resolve transient pulse error. These
    # are fixture inputs, with every physical equation and tolerance unchanged.
    for profile in (result["default"], *result["profiles"]):
        profile["diffusivity_m2_s"] = [10 * v for v in profile["diffusivity_m2_s"]]
    return result


def public_inputs(family="water"):
    result = inputs(family, padded=False)
    raw = result["definition"]
    raw["experiment"].update(end_time=2e-9, observation_times=[0.0, 1e-9, 2e-9])
    for name, rows in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in rows:
                key = "controls" if "controls" in row else "schedule"
                row[key] = row[key][:1]
    raw["execution"].update(dt=1e-9, max_steps=4)
    event = next(v for v in result["interventions"] if v["kind"] == "Na_mem")
    event.update(profiles=["Selected"], on_s=0.5e-9, off_s=1.5e-9, change_s=8e-9)
    result.update(interventions=[event], intervention_capacity=1)
    return result
