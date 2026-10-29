"""Independent initial physical definition from explicit polygons and owners.

Stdlib only. No production binder, inferred topology, RNG or state migration.
Complete passive field/rate comparisons reuse the separately frozen reference.
"""

from copy import deepcopy
from math import fsum, hypot

from validation.geometry.betse_geometry_reference import polygon


def measures(source):
    mesh, geom = source["mesh"], source["geometry"]
    points = dict(zip(mesh["dual_vertex_ids"], mesh["dual_points_m"], strict=True))
    cells, patches = {}, {}
    for cid, face, group in zip(
        mesh["cell_ids"], mesh["dual_cells"], geom["cell_membrane_ids"], strict=True
    ):
        raw = [points[name] for name in face]
        _, centre = polygon(raw)
        shrunk = [
            [centre[k] + geom["shrink_factor"] * (point[k] - centre[k]) for k in (0, 1)]
            for point in raw
        ]
        radial = []
        for mid, a, b in zip(group, shrunk[-1:] + shrunk[:-1], shrunk, strict=True):
            area = hypot(b[0] - a[0], b[1] - a[1]) * geom["height_m"]
            midpoint = [(a[k] + b[k]) / 2 for k in (0, 1)]
            pie = hypot(midpoint[0] - centre[0], midpoint[1] - centre[1]) * area / 2
            patches[mid] = dict(owner=cid, area_m2=area)
            radial.append(pie)
        cells[cid] = dict(native_radial=fsum(radial), polygon=polygon(shrunk)[0] * geom["height_m"])
    return dict(cells=cells, membranes=patches)


def definition(request):
    p = deepcopy(request["physics"])
    source = request["geometry_source"]
    metric = measures(source)
    model = dict(id="resolved_tissue@1", species=p["species"], temperature_K=p["temperature_K"])
    by_id = {row["id"]: row for row in p["cells"]}
    model["cells"] = [
        dict(by_id[name], volume_pL=metric["cells"][name][p["volume_policy"]] * 1e15)
        for name in source["mesh"]["cell_ids"]
    ]
    by_id = {row["id"]: row for row in p["extracellular"]}
    model["extracellular"] = []
    for name in source["grid"]["environment_ids"]:
        row = deepcopy(by_id[name])
        row["volume_pL"] = row.pop("volume_m3") * 1e15
        model["extracellular"].append(row)
    by_id = {row["id"]: row for row in p["membranes"]}
    model["membranes"] = []
    for name in source["geometry"]["membrane_ids"]:
        row = by_id[name]
        area = metric["membranes"][name]["area_m2"]
        model["membranes"].append(
            dict(
                id=name,
                inside=row["inside"],
                outside=row["outside"],
                area_m2=area,
                capacitance_F=area * row["specific_capacitance_F_per_m2"],
                permeability_m_per_s={
                    s["id"]: row["diffusivity_m2_per_s"][s["id"]] / row["thickness_m"]
                    for s in p["species"]
                },
                law="constant_field@1",
            )
        )
    model["junctions"] = []
    for row in p["junctions"]:
        model["junctions"].append(
            dict(
                id=row["id"],
                sender=row["sender"],
                receiver=row["receiver"],
                area_m2=metric["membranes"][row["membrane_ids"][0]]["area_m2"],
                permeability_m_per_s=row["permeability_m_per_s"],
                law="constant_field@1",
            )
        )
    model.update(faces=p["faces"], closure=p["closure"])
    return dict(
        schema_version=1,
        model=model,
        experiment=deepcopy(request["experiment"]),
        execution=deepcopy(request["execution"]),
    )
