"""Full56 manufactured static open reservoirs; no slow trajectory/calibration claim."""

from copy import deepcopy

from validation.tissue import hcn_extra_catalog_fixtures as catalog

FAMILIES = ("calcium", "energy")
CASES = ("all", "mixed", "empty", "blocked", "permuted")
MODEL_IDS = dict(calcium="resolved_open_calcium@1", energy="resolved_open_calcium_energy@1")
PARENT_IDS = dict(calcium="resolved_calcium@11", energy="resolved_calcium_energy@5")
DT = 62.5e-9
END = 8e-6


def original_definition(raw):
    value = deepcopy(raw)
    family = next(k for k, v in MODEL_IDS.items() if v == value["model"]["id"])
    value["model"]["id"] = PARENT_IDS[family]
    for key in ("exterior_policy", "ionic_moiety_domain_policy", "ionic_moiety_ceiling_fmol"):
        value["model"].pop(key)
    return value


def ionic_totals(model):
    ion = model["ionic"]
    result = {
        row["id"]: sum(owner["initial_amount_fmol"][row["id"]] for owner in ion["extracellular"])
        for row in ion["species"]
    }
    for row in model["stores"]:
        store = row["model"]
        for species in store["species"]:
            amount = sum(
                owner["initial_amount_fmol"][species["id"]] for owner in store["compartments"]
            )
            for name in result:
                result[name] += species["moieties"][name] * amount
    return result


def _blocked(value):
    if isinstance(value, dict):
        return {key: item if key == "time" else _blocked(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_blocked(item) for item in value]
    return 0.0


def definition(family="energy", case="all", *, padded=True, depleted=False):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    raw = catalog.definition(family, "open", padded=False)
    m, e, x = (raw[key] for key in ("model", "experiment", "execution"))
    ion = m["ionic"]
    if case != "empty":
        for i, row in enumerate(ion["extracellular"]):
            row["reservoir"] = case != "mixed" or i in (0, 4)
            row["boundary_potential_V"] = 0.001 * (1 if i % 2 else -1) if row["reservoir"] else 0.0
        ion["closure"]["gauge_reference"] = None
    m.update(
        id=MODEL_IDS[family],
        exterior_policy="static_declared_ideal_chemical_and_voltage_reservoirs@1",
        ionic_moiety_domain_policy="hard_global_ionic_moiety_ceilings_fmol_every_stage@1",
        ionic_moiety_ceiling_fmol=None
        if case == "empty"
        else {name: 1.5 * value for name, value in ionic_totals(m).items()},
    )
    if depleted:
        if family != "energy":
            raise ValueError("Finite fuel only")
        pool = m["energy_pools"][0]["initial_amount_fmol"]
        used = pool["ATP"] / 2
        pool.update(ATP=pool["ATP"] - used, ADP=pool["ADP"] + used, Pi=pool["Pi"] + used)
    capacities = dict(
        capacity=len(ion["cells"]),
        extracellular_capacity=len(ion["extracellular"]),
        membrane_capacity=len(ion["membranes"]),
        edge_capacity=len(ion["junctions"]),
        face_capacity=len(ion["faces"]),
        channel_capacity=len(ion["channels"]),
        chemical_capacity=max(len(row["model"]["compartments"]) for row in m["stores"]),
        reaction_capacity=max(len(row["model"]["reactions"]) for row in m["stores"]),
    )
    if family == "energy":
        capacities["regeneration_capacity"] = len(m["regeneration_ports"])
    x.update({key: value + int(padded) for key, value in capacities.items()})
    x.update(dt=DT, jit=False, max_steps=512, max_trace_bytes=2**29)
    e.update(end_time=END)
    clocks = {0.0, END}
    for number, (_key, groups) in enumerate(
        (pair for pair in e.items() if pair[0].endswith("_controls"))
    ):
        change_time = (number + 1) * 0.5e-6
        for i, group in enumerate(groups):
            field = "controls" if "controls" in group else "schedule"
            first = deepcopy(group[field][0])
            first["time"] = 0.0
            group[field] = [_blocked(first) if case == "blocked" else first]
            if i == 0:
                second = deepcopy(group[field][0])
                second["time"] = change_time
                if "availability" in second:
                    second["availability"] *= 0.5
                group[field].append(second)
                clocks.add(change_time)
    # Explicit unchanged carrier controls place observations on accepted steps.
    carrier = e["membrane_controls"][0]
    previous = deepcopy(carrier["schedule"])
    carrier["schedule"] = [
        dict(
            time=time,
            availability=next(
                row["availability"] for row in reversed(previous) if row["time"] <= time
            ),
        )
        for time in sorted(clocks)
    ]
    e["observation_times"] = sorted(clocks)
    if case == "permuted":
        for key in (
            "cells",
            "extracellular",
            "species",
            "membranes",
            "junctions",
            "faces",
            "channels",
        ):
            ion[key].reverse()
        for key in ("stores", "calcium_channels", "ip3_release"):
            m[key].reverse()
        m["plasma_transport"]["membranes"].reverse()
        for key, groups in e.items():
            if key.endswith("_controls"):
                groups.reverse()
    return raw
