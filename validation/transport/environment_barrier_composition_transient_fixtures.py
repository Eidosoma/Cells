"""Full declared barrier/control transients; six manufactured conditions, no biology.

The existing geometry, rates, inventories and complete 50-us control history are
unchanged. Added observation carriers hold their previous value. The common
numerical step follows the qualified full-water/repair parent comparison.
"""

from copy import deepcopy

FAMILIES = ("water", "repair")
CASES = ("overlap", "asymmetric_modulators", "zero_endpoint")
DATASETS = tuple(f"{family}-{case}" for family in FAMILIES for case in CASES)
BASE_DT_S = 0.625e-6


def parts(dataset):
    if dataset not in DATASETS:
        raise ValueError(dataset)
    return dataset.split("-", 1)


def event_times(raw):
    e = raw["experiment"]
    times = {0.0, e["end_time"]}
    for name, groups in e.items():
        if name.endswith("_controls"):
            times.update(
                row["time"]
                for group in groups
                for row in group.get("schedule", group.get("controls", []))
            )
    return sorted(times)


def observed(raw):
    """Add held-value carriers so every original observation is an exact boundary."""
    result = deepcopy(raw)
    e = result["experiment"]
    times = sorted({*event_times(raw), *e["observation_times"]})
    e["observation_times"] = times
    carrier = e["membrane_controls"][0]["schedule"]
    for time in times:
        if time == e["end_time"] or any(row["time"] == time for row in carrier):
            continue
        held = deepcopy(next(row for row in reversed(carrier) if row["time"] <= time))
        held["time"] = time
        carrier.append(held)
        carrier.sort(key=lambda row: row["time"])
    return result


def inputs(dataset):
    # Fixture loading is deliberately separate from the serialized oracle worker.
    from validation.transport import environment_barrier_composition_fixtures as original

    family, case = parts(dataset)
    source = original.request(family, case, permuted=False, padded=False)
    request = deepcopy(source)
    request["definition"] = observed(source["definition"])
    request["definition"]["execution"]["dt"] = BASE_DT_S
    assert source["definition"]["experiment"]["end_time"] == 50e-6
    return dict(source_request=source, request=request)


def assert_same_physics_and_control_history(source, target):
    """Check the history as a function, including both sides of every boundary."""
    assert source["model"] == target["model"]
    assert source["experiment"]["end_time"] == target["experiment"]["end_time"] == 50e-6
    assert {k: v for k, v in source["execution"].items() if k != "dt"} == {
        k: v for k, v in target["execution"].items() if k != "dt"
    }
    old, new = source["experiment"], target["experiment"]
    assert set(old) == set(new)
    assert set(event_times(source)) <= set(target["experiment"]["observation_times"])
    assert set(old["observation_times"]) <= set(new["observation_times"])
    for name, groups in old.items():
        if not name.endswith("_controls"):
            continue
        for before, after in zip(groups, new[name], strict=True):
            key = "controls" if "controls" in before else "schedule"
            assert {k: v for k, v in before.items() if k != key} == {
                k: v for k, v in after.items() if k != key
            }
            assert all(row in after[key] for row in before[key])
            clocks = sorted({row["time"] for row in before[key] + after[key]})
            samples = clocks + [(a + b) / 2 for a, b in zip(clocks[:-1], clocks[1:], strict=True)]
            for time in samples:
                a = next(v for v in reversed(before[key]) if v["time"] <= time)
                b = next(v for v in reversed(after[key]) if v["time"] <= time)
                assert {k: v for k, v in a.items() if k != "time"} == {
                    k: v for k, v in b.items() if k != "time"
                }
