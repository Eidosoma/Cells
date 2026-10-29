"""Two explicit complete calcium owners with declared manufactured SI geometry."""

from copy import deepcopy

from validation.tissue import hcn_extra_catalog_fixtures as fuel
from validation.tissue import surface_calcium_cav_fixtures as calcium

FAMILIES = ("calcium6", "fuel5")
CASES = ("SIM", "INIT", "close-reopen", "ion-flags", "empty-events")


def _scaled(value, factor):
    if isinstance(value, dict):
        return {k: (_scaled(v, factor) if k != "time" else v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scaled(v, factor) for v in value]
    return value * factor if type(value) in (int, float) else value


def inputs(family="calcium6", case="SIM"):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    definition = (
        calcium.definition(padded=True)
        if family == "calcium6"
        else fuel.definition("energy", padded=True)
    )
    m = definition["model"]["ionic"]
    e = definition["experiment"]
    x = definition["execution"]
    e.update(end_time=4e-6, observation_times=[0.0, 1e-6, 1.5e-6, 2e-6, 2.5e-6, 3e-6, 4e-6])
    families = [name for name in e if name.endswith("_controls")]
    for i, name in enumerate(families):
        for j, row in enumerate(e[name]):
            key = "controls" if "controls" in row else "schedule"
            initial = deepcopy(row[key][0])
            initial["time"] = 0.0
            row[key] = [initial]
            if j == 0:
                off = 1.25e-6 + (i % 9) * 0.125e-6
                closed = _scaled(initial, 0.0)
                closed["time"] = off
                reopened = _scaled(initial, 0.7)
                reopened["time"] = off + 0.75e-6
                row[key] += [closed, reopened]
    # Declared neutral knots make the requested pulse stages accepted boundaries.
    carrier = e["membrane_controls"][0]["schedule"]
    for time in e["observation_times"]:
        if time == e["end_time"] or any(v["time"] == time for v in carrier):
            continue
        held = deepcopy(next(v for v in reversed(carrier) if v["time"] <= time))
        held["time"] = time
        carrier.append(held)
        carrier.sort(key=lambda v: v["time"])
    x.update(dt=0.03125e-6, jit=False, max_steps=1024, max_trace_bytes=2**28)
    cells = [p["id"] for p in m["cells"]]
    mems = [p["id"] for p in m["membranes"]]
    outside = [p["id"] for p in m["extracellular"]]
    patches = {p["id"]: p for p in m["membranes"]}
    available = {cid: [p["id"] for p in m["membranes"] if p["inside"] == cid] for cid in cells}
    partners = {mid: mid for mid in mems}
    contacts = {}
    neighbors = {cid: [] for cid in cells}
    for edge in m["junctions"]:
        a = available[edge["sender"]].pop(0)
        b = available[edge["receiver"]].pop(0)
        partners[a] = b
        partners[b] = a
        contacts[edge["id"]] = [a, b]
        neighbors[edge["sender"]].append(edge["receiver"])
        neighbors[edge["receiver"]].append(edge["sender"])
    centres = {cid: [i * 1e-5, i * 0.5e-5] for i, cid in enumerate(cells)}
    cells.reverse()
    mems.reverse()
    outside.reverse()
    layout = dict(
        cell_ids=cells,
        membrane_ids=mems,
        environment_ids=outside,
        membrane_cell_ids=[patches[mid]["inside"] for mid in mems],
        membrane_environment_ids=[patches[mid]["outside"] for mid in mems],
        cell_membrane_ids=[[mid for mid in mems if patches[mid]["inside"] == cid] for cid in cells],
        cell_centres_m=[centres[cid] for cid in cells],
        bounds_m=[-1e-5, 5e-5, -1e-5, 3e-5],
        seed_fills=None,
    )
    geometry = dict(
        layout=layout,
        thickness_m={mid: (6 + 0.5 * i) * 1e-9 for i, mid in enumerate(mems)},
        partner_membrane_ids=partners,
        junction_membrane_ids=contacts,
        cell_neighbor_ids=neighbors,
        provenance=dict(
            source="manufactured explicit coupled-owner geometry/contact declarations",
            length_unit="m",
        ),
        length_unit="m",
        rho_channel=1.0,
    )

    def profile(name, ids, scale):
        return dict(
            name=name,
            selector=dict(
                kind="ids", value=ids, expected_layout_identity=None, permutation_cell_ids=None
            ),
            diffusivity_m2_s=[scale * (i + 1) * 1e-18 for i in range(6)],
            is_gj_insular=False,
        )

    default = profile("Default", cells, 1)
    rows = [profile("Region", [cells[0], cells[0]], 4), profile("Selected", [cells[-1]], 2)]
    events = []
    for kind, targets in (
        ("Ca_mem", ["Selected"]),
        ("Na_mem", ["Region", "Selected"]),
        ("Cl_mem", ["Region", "Region"]),
        ("K_mem", ["Default"]),
    ):
        events.append(
            dict(
                name="event-" + kind,
                kind=kind,
                profiles=targets,
                on_s=1e-6,
                off_s=3e-6,
                change_s=0.25e-6,
                amplitude=0.8,
                spatial=None,
                source_function="None",
                dynamic_factor=1.0,
            )
        )
    if case == "close-reopen":
        event = next(v for v in events if v["kind"] == "Na_mem")
        event.update(profiles=["Selected"], amplitude=-2.0)
        events = [event]
    if case == "empty-events":
        events = []
    return deepcopy(
        dict(
            definition=definition,
            geometry=geometry,
            default=default,
            profiles=rows,
            ion_enabled=[False] * 6
            if case == "ion-flags"
            else [True, True, True, True, False, False],
            enabled=True,
            is_ecm=False,
            interventions=events,
            phase="INIT" if case == "INIT" else "SIM",
            intervention_capacity=len(events),
            intervention_target_capacity=4 * len(mems) if events else 0,
        )
    )


def public_inputs(family):
    """Two complete-owner steps for public serialization and exact replay."""
    raw = inputs(family)
    definition = raw["definition"]
    definition["experiment"].update(end_time=2e-9, observation_times=[0.0, 1e-9, 2e-9])
    for name, rows in definition["experiment"].items():
        if name.endswith("_controls"):
            for row in rows:
                key = "controls" if "controls" in row else "schedule"
                row[key] = row[key][:1]
    definition["execution"].update(dt=1e-9, max_steps=4)
    event = next(v for v in raw["interventions"] if v["kind"] == "Na_mem")
    event.update(profiles=["Selected"], on_s=0.5e-9, off_s=1.5e-9, change_s=8e-9)
    raw["interventions"] = [event]
    raw["intervention_capacity"] = 1
    return raw
