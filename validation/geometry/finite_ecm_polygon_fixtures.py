"""Deferred explicit finite-ECM partition and polarized passive caller inputs."""

import math
from collections import defaultdict
from copy import deepcopy

from validation.geometry import finite_ecm_polygon_reference as independent

CASES = (
    "one-cell-grid",
    "unequal-width-grid",
    "two-cell-grid",
    "diamond-grid",
    "translated-grid",
    "reordered-owners",
)
DOMAIN_CASES = (
    "wrong-units",
    "native-source-claim",
    "duplicate-coordinate",
    "duplicate-vertex-id",
    "clockwise-region",
    "overlapping-region",
    "t-junction",
    "hole-in-domain",
    "direct-cell-cell",
    "cell-at-outer-boundary",
    "concave-bath",
    "nonorthogonal-dual",
    "missing-boundary",
    "wrong-boundary-owner",
    "reversed-boundary-side",
    "unsegmented-domain-edge",
    "outer-reservoir-boundary",
    "axial-flux-boundary",
    "centroid-midpoint-policy",
    "finite-membrane-volume-policy",
    "zero-height",
    "zero-membrane-path",
    "volume-underflow",
    "unused-vertex",
    "missing-bath-polygon",
    "invented-bath-volume",
)
PHYSICAL_DOMAIN_CASES = (
    "wrong-law",
    "wrong-geometry",
    "active-family",
    "missing-provenance",
    "missing-cell",
    "missing-bath",
    "numeric-bath-volume",
    "wrong-volume-owner",
    "wrong-membrane-bath",
    "numeric-membrane-area",
    "zero-capacitance",
    "negative-membrane-diffusivity",
    "missing-face",
    "reversed-face",
    "numeric-face-length",
    "wrong-face-area-owner",
    "negative-face-diffusivity",
    "held-reservoir",
    "direct-junction",
    "reference-in-amount",
    "reference-in-control",
    "missing-control",
    "duplicate-control-clock",
    "bad-charge-anchor",
    "unowned-gauge",
    "nongauge-boundary-potential",
)
CORRUPTION_CASES = (
    "bath-volume",
    "membrane-area",
    "face-distance",
    "face-normal",
    "face-owner",
    "boundary-owner",
    "face-incidence",
    "geometry-certificate",
)
OWNERSHIP_CASES = (
    "wrong-opt-in",
    "request-identity",
    "binding-resealed-normal",
    "prepared-volume",
    "prepared-inventory",
    "returned-copy-alias",
)


def _boundary(raw):
    incidence = defaultdict(list)
    for region in raw["regions"]:
        ring = region["vertex_ids"]
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
            incidence[tuple(sorted((a, b)))].append((region["id"], a, b))
    raw["boundary"] = [
        dict(region_id=owner, vertex_ids=[a, b], condition="sealed_no_transport@1")
        for owners in incidence.values()
        if len(owners) == 1
        for owner, a, b in owners
    ]
    return raw


def fixture(case):
    if case not in CASES:
        raise ValueError(case)
    nx = 5 if case == "two-cell-grid" else 3
    unit = 2.0**-17
    widths = [1, 2, 3] if case == "unequal-width-grid" else [1] * nx
    heights = [2, 1, 3] if case == "unequal-width-grid" else [1, 1, 1]
    xs = [0]
    for width in widths:
        xs.append(xs[-1] + width)
    ys = [0]
    for height in heights:
        ys.append(ys[-1] + height)

    def vertex(x, y):
        return "v-" + str(x) + "-" + str(y)

    vertices = [
        dict(id=vertex(x, y), xy_m=[unit * xs[x], unit * ys[y]])
        for y in range(4)
        for x in range(nx + 1)
    ]
    if case == "diamond-grid":
        for row in vertices:
            x, y = row["xy_m"]
            row["xy_m"] = [x - y, x + y]
    if case == "translated-grid":
        for row in vertices:
            row["xy_m"] = [row["xy_m"][0] + 2**-10, row["xy_m"][1] - 2**-9]
    regions = []
    for y in range(3):
        for x in range(nx):
            cell = (x, y) in ((1, 1), (3, 1))
            regions.append(
                dict(
                    id=("cell-" if cell else "bath-") + str(x) + "-" + str(y),
                    kind="cell" if cell else "bath",
                    vertex_ids=[
                        vertex(x, y),
                        vertex(x + 1, y),
                        vertex(x + 1, y + 1),
                        vertex(x, y + 1),
                    ],
                )
            )
    domain = (
        [vertex(x, 0) for x in range(nx)]
        + [vertex(nx, y) for y in range(3)]
        + [vertex(x, 3) for x in range(nx, 0, -1)]
        + [vertex(0, y) for y in range(3, 0, -1)]
    )
    if case == "reordered-owners":
        regions.reverse()
    return _boundary(
        dict(
            source=dict(
                kind="explicit_cell_bath_partition@1",
                generator=case,
                provenance=dict(
                    recipe=(
                        "Explicit dyadic rectilinear partition; "
                        "exact diamond transform/translation where named"
                    ),
                    coverage=(
                        "Declared polygons only; no Voronoi/Delaunay or BETSE native equivalence"
                    ),
                ),
            ),
            vertices=vertices,
            domain_vertex_ids=domain,
            regions=regions,
            boundary=[],
            height_m=2**-20,
            membrane_thickness_m=5e-9,
            membrane_geometry_policy="zero_volume_interface_explicit_path@1",
            face_distance_policy="orthogonal_volume_centroids_shared_face@1",
            axial_caps="sealed_no_transport@1",
            units=dict(coordinates="m", height="m", membrane_path="m", area="m2", volume="m3"),
        )
    )


def domain(case):
    raw = fixture(
        "two-cell-grid" if case in ("hole-in-domain", "direct-cell-cell") else "one-cell-grid"
    )
    if case == "wrong-units":
        raw["units"]["coordinates"] = "um"
    elif case == "native-source-claim":
        raw["source"]["kind"] = "native_betse_mesh@1"
    elif case == "duplicate-coordinate":
        raw["vertices"][1]["xy_m"] = raw["vertices"][0]["xy_m"][:]
    elif case == "duplicate-vertex-id":
        raw["vertices"][1]["id"] = raw["vertices"][0]["id"]
    elif case == "clockwise-region":
        raw["regions"][0]["vertex_ids"].reverse()
    elif case == "overlapping-region":
        raw["regions"].append(deepcopy(raw["regions"][0]) | dict(id="overlap"))
    elif case == "t-junction":
        a = next(row for row in raw["vertices"] if row["id"] == "v-1-0")["xy_m"]
        b = next(row for row in raw["vertices"] if row["id"] == "v-1-1")["xy_m"]
        raw["vertices"].append(
            dict(id="hanging", xy_m=[(x + y) / 2 for x, y in zip(a, b, strict=True)])
        )
        raw["regions"][0]["vertex_ids"].insert(2, "hanging")
    elif case == "hole-in-domain":
        raw["regions"] = [row for row in raw["regions"] if row["id"] != "bath-2-1"]
    elif case == "direct-cell-cell":
        next(row for row in raw["regions"] if row["id"] == "bath-2-1")["kind"] = "cell"
    elif case == "cell-at-outer-boundary":
        raw["regions"][0]["kind"] = "cell"
    elif case == "concave-bath":
        raw["regions"] = [
            row for row in raw["regions"] if row["id"] not in ("bath-0-0", "bath-1-0", "bath-0-1")
        ]
        raw["regions"].insert(
            0,
            dict(
                id="concave-bath",
                kind="bath",
                vertex_ids=["v-0-0", "v-1-0", "v-2-0", "v-2-1", "v-1-1", "v-1-2", "v-0-2", "v-0-1"],
            ),
        )
        _boundary(raw)
    elif case == "nonorthogonal-dual":
        for row in raw["vertices"]:
            row["xy_m"][0] += row["xy_m"][1] / 4
    elif case == "missing-boundary":
        raw["boundary"].pop()
    elif case == "wrong-boundary-owner":
        raw["boundary"][0]["region_id"] = "cell-1-1"
    elif case == "reversed-boundary-side":
        raw["boundary"][0]["vertex_ids"].reverse()
    elif case == "unsegmented-domain-edge":
        raw["domain_vertex_ids"].remove("v-1-0")
    elif case == "outer-reservoir-boundary":
        raw["boundary"][0]["condition"] = "ideal_reservoir@1"
    elif case == "axial-flux-boundary":
        raw["axial_caps"] = "open_transport@1"
    elif case == "centroid-midpoint-policy":
        raw["face_distance_policy"] = "distance_to_edge_midpoints@1"
    elif case == "finite-membrane-volume-policy":
        raw["membrane_geometry_policy"] = "subtract_guessed_membrane_volume@1"
    elif case == "zero-height":
        raw["height_m"] = 0.0
    elif case == "zero-membrane-path":
        raw["membrane_thickness_m"] = 0.0
    elif case == "volume-underflow":
        raw["height_m"] = float.fromhex("0x0.0000000000001p-1022")
    elif case == "unused-vertex":
        raw["vertices"].append(dict(id="unused", xy_m=[1.0, 2.0]))
    elif case == "missing-bath-polygon":
        raw["regions"].pop(0)
    elif case == "invented-bath-volume":
        raw["regions"][0]["volume_m3"] = 1e-15
    else:
        raise ValueError(case)
    return raw


def ref(quantity, **owner):
    return {"$geometry": quantity, **owner}


def physical(case, declaration, binding):
    g = binding.geometry
    target = independent.evaluate(declaration)
    edges = {row["id"]: row for row in target["edges"]}
    ordered_cells = sorted(g["cell_ids"])
    ordered_baths = sorted(g["bath_ids"])
    species = [dict(id=name, valence=z) for name, z in (("Na", 1), ("K", 1), ("Cl", -1))]
    charges = dict.fromkeys(g["owner_axis"], 0.0)
    desired_cell = {name: -0.035 - 0.02 * i for i, name in enumerate(ordered_cells)}
    model = dict(
        id="resolved_tissue@1",
        temperature_K=298.15,
        species=species,
        cells=[],
        extracellular=[],
        membranes=[],
        junctions=[],
        faces=[],
        closure=dict(
            law="resolved_capacitor_components_current_continuity@1",
            gauge_reference=g["membranes"][0]["bath_id"],
        ),
    )
    experiment = dict(
        end_time=1e-6,
        observation_times=[0.0, 5e-7, 1e-6],
        membrane_controls=[],
        junction_controls=[],
    )
    for index, patch in enumerate(g["membranes"]):
        specific = 0.01 * (1 + 0.04 * index)
        cap_squared = independent.multiply(
            edges[patch["edge_id"]]["area_squared"],
            independent.multiply(independent.ratio(specific), independent.ratio(specific)),
        )
        q = independent.number(cap_squared, root=True) * desired_cell[patch["cell_id"]]
        charges[patch["cell_id"]] += q
        charges[patch["bath_id"]] -= q
        name = patch["id"]
        model["membranes"].append(
            dict(
                id=name,
                inside=patch["cell_id"],
                outside=patch["bath_id"],
                law="constant_field@1",
                area_m2=ref("membrane_area_m2", membrane_id=name),
                capacitance_F=ref(
                    "membrane_capacitance_F",
                    membrane_id=name,
                    specific_capacitance_F_per_m2=specific,
                ),
                permeability_m_per_s={
                    species_name: ref(
                        "membrane_permeability_m_per_s",
                        membrane_id=name,
                        diffusivity_m2_per_s=declaration["membrane_thickness_m"] * p,
                    )
                    for species_name, p in (("Na", 1e-9), ("K", 2e-9), ("Cl", 8e-10))
                },
            )
        )
        experiment["membrane_controls"].append(
            dict(
                membrane_id=name,
                schedule=[dict(time=0.0, availability=0.8), dict(time=5e-7, availability=0.45)],
            )
        )
    for index, face in enumerate(g["faces"]):
        name = face["id"]
        model["faces"].append(
            dict(
                id=name,
                sender=face["sender"],
                receiver=face["receiver"],
                law="logmean_electrodiffusion@1",
                area_m2=ref("face_area_m2", face_id=name),
                length_m=ref("face_length_m", face_id=name),
                diffusivity_m2_per_s={
                    s: diffusion * (1 + 0.03 * index)
                    for s, diffusion in (("Na", 1.2e-9), ("K", 1.7e-9), ("Cl", 2e-9))
                },
            )
        )
    charge_unit = 6.02214076e23 * 1.602176634e-19 * 1e-15
    for kind, names in (("cells", g["cell_ids"]), ("extracellular", g["bath_ids"])):
        for name in names:
            volume = independent.number(
                independent.multiply(target["regions"][name]["volume"], independent.ratio(1e15))
            )
            if kind == "cells":
                concentrations = (12.0 + ordered_cells.index(name), 140.0, 10.0)
            else:
                factor = 1 + 0.025 * ordered_baths.index(name)
                concentrations = (145.0 * factor, 4.0 * factor, 149.0 * factor)
            amounts = {s["id"]: volume * c for s, c in zip(species, concentrations, strict=True)}
            owner = dict(
                id=name,
                volume_pL=ref("region_volume_pL", region_id=name),
                initial_amount_fmol=amounts,
                initial_charge_C=charges[name],
                fixed_charge_equivalent_fmol=charges[name] / charge_unit
                - math.fsum(s["valence"] * amounts[s["id"]] for s in species),
            )
            if kind == "extracellular":
                owner.update(reservoir=False, boundary_potential_V=0.0)
            model[kind].append(owner)
    execution = dict(
        dt=6.25e-8,
        capacity=len(g["cell_ids"]) + 1,
        extracellular_capacity=len(g["bath_ids"]) + 1,
        membrane_capacity=len(g["membranes"]) + 1,
        edge_capacity=1,
        face_capacity=len(g["faces"]) + 1,
        backend="cpu",
        jit=False,
        precision="float64",
        solver="rk4",
        field_solver="capacitive_reduction_gauged_damped_newton@1",
        max_steps=256,
        max_trace_bytes=2**26,
        material_balance_atol_fmol={s["id"]: 2e-11 for s in species},
    )
    if case == "reordered-owners":
        for key in ("cells", "extracellular", "membranes", "faces"):
            model[key].reverse()
        experiment["membrane_controls"].reverse()
    return dict(
        kind="cells.finite_ecm_polygon_passive_request@1",
        opted_in_law="cells_finite_ecm_polygon_passive_preparation@1",
        geometry_identity=binding.identity,
        target_model_id="resolved_tissue@1",
        definition_template=dict(
            schema_version=1, model=model, experiment=experiment, execution=execution
        ),
        provenance=dict(
            case=case,
            source="Complete synthetic passive caller, not measured physiology",
            bath_volumes="Exact declared bath polygon extrusion, no inferred cleft or source grid",
            charge_recipe=(
                "Sum exact-area patch C * declared cell potential; gauge bath and all "
                "capacitor-attached baths start at zero; bulk baths follow current continuity"
            ),
            declared_cell_potential_V=desired_cell,
            bulk_bath_potential_policy=(
                "Independent full-node current-continuity solution for floating bulk baths"
            ),
            coefficients=(
                "Explicit per-face species diffusivity and per-patch capacitance and membrane paths"
            ),
            boundary=(
                "Every outer side and both axial caps explicitly sealed; finite bath flags retained"
            ),
        ),
    )


def physical_domain(case, declaration, binding):
    raw = physical("one-cell-grid", declaration, binding)
    model = raw["definition_template"]["model"]
    experiment = raw["definition_template"]["experiment"]
    if case == "wrong-law":
        raw["opted_in_law"] = "other"
    elif case == "wrong-geometry":
        raw["geometry_identity"] = "0" * 64
    elif case == "active-family":
        raw["target_model_id"] = "resolved_tissue@2"
        model["id"] = "resolved_tissue@2"
    elif case == "missing-provenance":
        raw["provenance"] = {}
    elif case == "missing-cell":
        model["cells"].pop()
    elif case == "missing-bath":
        model["extracellular"].pop()
    elif case == "numeric-bath-volume":
        model["extracellular"][0]["volume_pL"] = 1.0
    elif case == "wrong-volume-owner":
        model["extracellular"][0]["volume_pL"]["region_id"] = model["cells"][0]["id"]
    elif case == "wrong-membrane-bath":
        model["membranes"][0]["outside"] = "unowned"
    elif case == "numeric-membrane-area":
        model["membranes"][0]["area_m2"] = 1e-10
    elif case == "zero-capacitance":
        model["membranes"][0]["capacitance_F"]["specific_capacitance_F_per_m2"] = 0.0
    elif case == "negative-membrane-diffusivity":
        model["membranes"][0]["permeability_m_per_s"]["Na"]["diffusivity_m2_per_s"] = -1e-18
    elif case == "missing-face":
        model["faces"].pop()
    elif case == "reversed-face":
        face = model["faces"][0]
        face["sender"], face["receiver"] = face["receiver"], face["sender"]
    elif case == "numeric-face-length":
        model["faces"][0]["length_m"] = 1e-5
    elif case == "wrong-face-area-owner":
        model["faces"][0]["area_m2"]["face_id"] = model["faces"][1]["id"]
    elif case == "negative-face-diffusivity":
        model["faces"][0]["diffusivity_m2_per_s"]["Na"] = -1e-9
    elif case == "held-reservoir":
        model["extracellular"][0]["reservoir"] = True
    elif case == "direct-junction":
        model["junctions"] = [dict(id="unsupported")]
    elif case == "reference-in-amount":
        model["cells"][0]["initial_amount_fmol"]["Na"] = deepcopy(model["cells"][0]["volume_pL"])
    elif case == "reference-in-control":
        experiment["membrane_controls"][0]["schedule"][0]["availability"] = deepcopy(
            model["cells"][0]["volume_pL"]
        )
    elif case == "missing-control":
        experiment["membrane_controls"].pop()
    elif case == "duplicate-control-clock":
        experiment["membrane_controls"][0]["schedule"][1]["time"] = 0.0
    elif case == "bad-charge-anchor":
        model["cells"][0]["initial_charge_C"] += 1e-12
    elif case == "unowned-gauge":
        model["closure"]["gauge_reference"] = "absent"
    elif case == "nongauge-boundary-potential":
        next(
            row
            for row in model["extracellular"]
            if row["id"] != model["closure"]["gauge_reference"]
        )["boundary_potential_V"] = 0.001
    else:
        raise ValueError(case)
    return raw
