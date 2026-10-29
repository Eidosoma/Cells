"""Six full 10-us scheduled-barrier conditions, with explicit bounded work units."""

from copy import deepcopy

FAMILIES = ("ionic", "calcium", "energy")
CASES = ("asymmetric", "reseal")
DATASETS = tuple(f"{family}-{case}" for family in FAMILIES for case in CASES)
END_S = 160 * 62.5e-9
DT_S = 62.5e-9
CHUNK_ENDS_S = tuple(i * END_S / 4 for i in range(5))


def definition(captured):
    """Use accepted stage input data; retain all physical owners and controls."""
    raw = deepcopy(captured)
    assert raw["experiment"]["end_time"] == END_S
    assert raw["execution"]["dt"] == DT_S
    model = raw["model"]
    assert model["phase"] == "SIM" and model["intervention"] is not None
    event = model["intervention"]
    assert 0 <= event["on_s"] < event["off_s"] <= END_S
    # Compact only execution capacities. Physical definitions, laws, stores,
    # pools, observation clocks and every held-control history stay exact.
    ion = model if model["id"] == "resolved_active_extracellular_barriers@1" else model["ionic"]
    raw["execution"].update(
        capacity=len(ion["cells"]),
        extracellular_capacity=len(ion["extracellular"]),
        membrane_capacity=len(ion["membranes"]),
        edge_capacity=len(ion["junctions"]),
        face_capacity=len(ion["faces"]),
        channel_capacity=len(ion["channels"]),
        barrier_target_capacity=len(event["site_ids"]),
    )
    if "regeneration_ports" in model:
        raw["execution"]["regeneration_capacity"] = len(model["regeneration_ports"])
    # The exact static artifact still owns its original preparation execution;
    # only scheduled execution capacity changes. No owner property changes.
    return raw


def samples(raw):
    times = {0.0, END_S, *raw["experiment"]["observation_times"]}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                times.update(v["time"] for v in row.get("controls", row.get("schedule", [])))
    return sorted(times)


def window(raw, chunk, *, pilot=False):
    if type(chunk) is not int or not 0 <= chunk < 4:
        raise ValueError(chunk)
    left, right = CHUNK_ENDS_S[chunk : chunk + 2]
    if pilot:
        if chunk != 0:
            raise ValueError("Pilot must start at original time zero")
        # The pilot is a distinct subinterval and has no full-trajectory credit.
        right = 8 * DT_S
    return left, right, sorted({left, right, *(t for t in samples(raw) if left <= t <= right)})
