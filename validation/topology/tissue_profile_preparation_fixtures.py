"""Explicit SI geometry and static profiles on real three-cell definitions."""

from copy import deepcopy

from validation.tissue import active_excision_fixtures, surface_excision_fixtures

IONS = ("Na", "K", "Cl", "Ca", "M", "P")
ARMS = (
    "overlap",
    "percent-alias",
    "color",
    "indices-duplicates",
    "image",
    "disabled",
    "no-later-profiles",
    "all-disabled",
)


def profile(name, kind, value, scale, *, insular=False, permutation=None, identity=None):
    return dict(
        name=name,
        selector=dict(
            kind=kind,
            value=value,
            expected_layout_identity=identity,
            permutation_cell_ids=permutation,
        ),
        diffusivity_m2_s=[scale * (i + 1) for i in range(6)],
        is_gj_insular=insular,
    )


def inputs(kind="passive", arm="overlap", *, permuted=False):
    if kind not in ("passive", "active") or arm not in ARMS:
        raise ValueError((kind, arm))
    definition = (
        surface_excision_fixtures.definition("open", padded=True)
        if kind == "passive"
        else active_excision_fixtures.definition("open", catalog="compact", padded=True)
    )
    m = definition["model"]
    cells, mems, env = (
        [r["id"] for r in m[key]] for key in ("cells", "membranes", "extracellular")
    )
    if permuted:
        cells.reverse()
        mems.reverse()
        env.reverse()
    by_mid = {r["id"]: r for r in m["membranes"]}
    centres = {"cell_0": [0.0, 0.0], "cell_1": [1e-5, 0.5e-5], "cell_2": [2e-5, 1e-5]}
    partners = {mid: mid for mid in mems}
    contacts = {
        "junction_0_1": ["membrane_0_shared", "membrane_1_shared"],
        "junction_1_2": ["membrane_1_bath", "membrane_2_shared"],
    }
    if kind == "active":
        contacts["junction_0_2"] = ["membrane_0_bath", "membrane_2_bath"]
    neighbors = {cid: [] for cid in cells}
    for edge in m["junctions"]:
        a, b = contacts[edge["id"]]
        partners[a] = b
        partners[b] = a
        neighbors[edge["sender"]].append(edge["receiver"])
        neighbors[edge["receiver"]].append(edge["sender"])
    layout = dict(
        cell_ids=cells,
        membrane_ids=mems,
        environment_ids=env,
        membrane_cell_ids=[by_mid[mid]["inside"] for mid in mems],
        membrane_environment_ids=[by_mid[mid]["outside"] for mid in mems],
        cell_membrane_ids=[
            [mid for mid in reversed(mems) if by_mid[mid]["inside"] == cid] for cid in cells
        ],
        cell_centres_m=[centres[cid] for cid in cells],
        bounds_m=[-1e-5, 3e-5, -1e-5, 2e-5],
        seed_fills=["blue" if cid == "cell_1" else "red" for cid in cells],
    )
    geometry = dict(
        layout=layout,
        thickness_m={r["id"]: (6.0 + 0.5 * i) * 1e-9 for i, r in enumerate(m["membranes"])},
        partner_membrane_ids=partners,
        junction_membrane_ids=contacts,
        cell_neighbor_ids=neighbors,
        provenance=dict(
            source="manufactured explicit surface/contact geometry",
            coordinate_unit="m",
            thickness_unit="m",
        ),
        length_unit="m",
        rho_channel=1.0,
    )
    default = profile("Default", "ids", ["cell_2"], 1e-18)
    rows = [
        profile("Region", "ids", ["cell_1", "cell_0", "cell_1"], 2e-18, insular=True),
        profile("Overlap", "ids", ["cell_0", "cell_2"], 4e-18, insular=True),
    ]
    if arm == "percent-alias":
        rows = [
            profile("Zero", "percent", 0.0, 2e-18, permutation=["cell_2", "cell_0", "cell_1"]),
            profile("AllLater", "all", None, 3e-18),
            profile("Selected", "percent", 66.7, 4e-18, permutation=["cell_1", "cell_2", "cell_0"]),
        ]
    if arm == "color":
        rows = [profile("Color", "color", "red", 3e-18, insular=True)]
    if arm == "indices-duplicates":
        rows = [profile("Repeated", "indices", [2, 0, 2], 3e-18)]
    if arm == "image":
        bitmap = [[255, 255, 255, 255], [0, 0, 255, 255], [0, 0, 255, 254], [255, 255, 255, 255]]
        rows = [profile("Image", "image", dict(grayscale_F=bitmap), 3e-18, insular=True)]
    if arm == "no-later-profiles":
        rows = []
    flags = [True, True, True, kind == "active", False, False]
    if arm == "all-disabled":
        flags = [False] * 6
    return deepcopy(
        dict(
            definition=definition,
            geometry=geometry,
            default=default,
            profiles=rows,
            ion_enabled=flags,
            enabled=arm != "disabled",
            is_ecm=False,
        )
    )
