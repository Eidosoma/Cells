"""Manufactured full56 ionic geometry and both native coefficient schedules."""

from copy import deepcopy

from validation.transport import owned_barrier_interventions_fixtures as exterior

CASES = (
    "joint",
    "duplicates",
    "INIT",
    "disabled",
    "membrane-only",
    "barrier-only",
    "closed",
    "guarded",
    "negative-safe",
)
MODEL_ID = "resolved_active_profile_barriers@1"
TIMING_POLICY = "phase_clock_rk_stage_native_logistic@1"
RESET_POLICY = "fresh_phase_zero_scheduled_sim_only@1"


def inputs(case="joint", *, permuted=False, padded=True):
    if case not in CASES:
        raise ValueError(case)
    values = exterior.inputs(
        "ionic", "reseal" if case == "closed" else "asymmetric", permuted=permuted, padded=padded
    )
    recipe = values["request"]
    raw = recipe["definition"]
    model = raw["model"]
    cells, mems, sites = (
        [v["id"] for v in model[k]] for k in ("cells", "membranes", "extracellular")
    )
    by_mid = {v["id"]: v for v in model["membranes"]}
    partners = {mid: mid for mid in mems}
    contacts, neighbors = {}, {cid: [] for cid in cells}
    for edge in model["junctions"]:
        pair = [
            next(mid for mid in mems if by_mid[mid]["inside"] == cid and partners[mid] == mid)
            for cid in (edge["sender"], edge["receiver"])
        ]
        contacts[edge["id"]] = pair
        partners[pair[0]], partners[pair[1]] = pair[1], pair[0]
        neighbors[edge["sender"]].append(edge["receiver"])
        neighbors[edge["receiver"]].append(edge["sender"])
    layout = dict(
        cell_ids=cells,
        membrane_ids=mems,
        environment_ids=sites,
        membrane_cell_ids=[by_mid[mid]["inside"] for mid in mems],
        membrane_environment_ids=[by_mid[mid]["outside"] for mid in mems],
        cell_membrane_ids=[
            [mid for mid in reversed(mems) if by_mid[mid]["inside"] == cid] for cid in cells
        ],
        cell_centres_m=[[i * 1e-5, 0.0] for i in range(len(cells))],
        bounds_m=[-1e-5, (len(cells) + 1) * 1e-5, -1e-5, 1e-5],
        seed_fills=["red"] * len(cells),
    )
    geometry = dict(
        layout=layout,
        thickness_m={mid: (8 + 0.5 * i) * 1e-9 for i, mid in enumerate(mems)},
        partner_membrane_ids=partners,
        junction_membrane_ids=contacts,
        cell_neighbor_ids=neighbors,
        provenance=dict(
            source="manufactured complete ionic geometry", coordinate_unit="m", thickness_unit="m"
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

    default = profile("Default", cells, 1.0)
    profiles = [
        profile("Region", [cells[0], cells[1], cells[0]], 3.0),
        profile("Selected", [cells[-1]], 2.0),
    ]
    flags = [True, True, True, True, False, False]
    if case == "closed":
        flags[0] = False
        for row in model["membranes"]:
            row["permeability_m_per_s"]["Na"] = 0.0
    if case == "guarded":
        flags[2] = False
    targets = ["Region", "Selected"]
    if case == "duplicates":
        targets = ["Region", "Selected", "Region"]
        values["intervention"]["site_ids"] *= 2
    count = sum(
        len(layout["cell_membrane_ids"][cells.index(cid)])
        for name in targets
        for cid in next(p for p in profiles if p["name"] == name)["selector"]["value"]
    )
    events = [
        dict(
            name="membrane_Na",
            kind="Na_mem",
            profiles=targets,
            on_s=1e-6,
            off_s=6e-6,
            change_s=1e-6,
            amplitude=0.7,
            spatial=dict(values=[0.4 + 0.03 * i for i in range(count)], axis="occurrence"),
            source_function="explicit_samples",
            dynamic_factor=0.8,
        ),
        dict(
            name="membrane_Cl",
            kind="Cl_mem",
            profiles=["Default"],
            on_s=3e-6,
            off_s=8e-6,
            change_s=1e-6,
            amplitude=0.4,
            spatial=None,
            source_function="None",
            dynamic_factor=1.0,
        ),
    ]
    if case == "closed":
        events = events[:1]
        events[0].update(
            profiles=["Default"], spatial=None, source_function="None", on_s=2e-6, off_s=4e-6
        )
    if case == "negative-safe":
        for event in events:
            event["amplitude"] = -0.2
    if case == "disabled":
        for event in events:
            event["amplitude"] = 0.0
        values["intervention"]["amplitude"] = 0.0
    if case == "membrane-only":
        values["intervention"] = None
    if case == "barrier-only":
        events = []
    return dict(
        profile_request=dict(
            definition=deepcopy(raw),
            geometry=geometry,
            default=default,
            profiles=profiles,
            ion_enabled=flags,
            enabled=True,
            is_ecm=False,
        ),
        barrier_template=recipe,
        membrane_interventions=events,
        barrier_intervention=values["intervention"],
        phase="INIT" if case == "INIT" else "SIM",
        intervention_capacity=4 if padded else len(events),
        intervention_target_capacity=max(count, len(mems)) + int(padded),
        barrier_target_capacity=(
            0 if values["intervention"] is None else len(values["intervention"]["site_ids"])
        )
        + int(padded),
    )


def preparation_request(values, profile_preparation):
    barrier = deepcopy(values["barrier_template"])
    barrier["definition"] = deepcopy(profile_preparation["definition"])
    return dict(
        kind="cells.active_profile_barrier_preparation_request@1",
        order="static_membrane_profiles_then_extracellular_barriers@1",
        profile_preparation=deepcopy(profile_preparation),
        barrier_request=barrier,
    )


def definition(values, prepared):
    raw = deepcopy(prepared.definition)
    raw["model"].update(
        id=MODEL_ID,
        coupled_preparation=dict(
            definition=deepcopy(prepared.definition), provenance=deepcopy(prepared.provenance)
        ),
        membrane_interventions=values["membrane_interventions"],
        barrier_intervention=values["barrier_intervention"],
        phase=values["phase"],
        timing_policy=TIMING_POLICY,
        reset_policy=RESET_POLICY,
    )
    for key in ("intervention_capacity", "intervention_target_capacity", "barrier_target_capacity"):
        raw["execution"][key] = values[key]
    return raw
