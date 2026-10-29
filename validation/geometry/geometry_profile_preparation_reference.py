"""Independent geometry/profile owner view and frozen Decimal profile equations."""

from copy import deepcopy

from validation.geometry.betse_geometry_reference import polygon
from validation.topology import tissue_profile_preparation_reference as profiles


def derive_geometry(request):
    artifact = request["geometry_preparation"]
    physical = artifact["provenance"]["request"]["physics"]
    source = artifact["provenance"]["request"]["geometry_source"]
    mesh, g = source["mesh"], source["geometry"]
    cells = mesh["cell_ids"]
    mems = g["membrane_ids"]
    vertices = dict(zip(mesh["dual_vertex_ids"], mesh["dual_points_m"], strict=True))
    centres = [polygon([vertices[name] for name in row])[1] for row in mesh["dual_cells"]]
    owner = {
        mid: cid for cid, group in zip(cells, g["cell_membrane_ids"], strict=True) for mid in group
    }
    patches = {row["id"]: row for row in physical["membranes"]}
    neighbors = {name: [] for name in cells}
    for edge in artifact["definition"]["model"]["junctions"]:
        a, b = edge["sender"], edge["receiver"]
        if b not in neighbors[a]:
            neighbors[a].append(b)
        if a not in neighbors[b]:
            neighbors[b].append(a)
    return dict(
        layout=dict(
            cell_ids=cells,
            membrane_ids=mems,
            environment_ids=source["grid"]["environment_ids"],
            membrane_cell_ids=[owner[mid] for mid in mems],
            membrane_environment_ids=g["membrane_environment_ids"],
            cell_membrane_ids=g["cell_membrane_ids"],
            cell_centres_m=centres,
            bounds_m=source["grid"]["bounds_m"],
            seed_fills=None
            if request["seed_fills"] is None
            else [request["seed_fills"][cid] for cid in cells],
        ),
        thickness_m={mid: patches[mid]["thickness_m"] for mid in mems},
        partner_membrane_ids=dict(zip(mems, g["partner_membrane_ids"], strict=True)),
        junction_membrane_ids={row["id"]: row["membrane_ids"] for row in physical["junctions"]},
        cell_neighbor_ids=neighbors,
    )


def prepare(request):
    raw = {
        key: deepcopy(request[key])
        for key in ("default", "profiles", "ion_enabled", "enabled", "is_ecm")
    }
    raw["definition"] = deepcopy(request["geometry_preparation"]["definition"])
    raw["geometry"] = derive_geometry(request)
    return profiles.prepare(raw)
