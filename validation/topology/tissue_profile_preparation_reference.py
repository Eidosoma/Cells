"""Independent stable-owner preparation using frozen owner loops and Decimal."""

from copy import deepcopy
from decimal import Decimal, localcontext

from validation.topology import betse_tissue_profiles_reference as frozen


def prepare(inputs):
    source = inputs["definition"]
    g = inputs["geometry"]
    layout = g["layout"]
    cells, mems, env = (layout[k] for k in ("cell_ids", "membrane_ids", "environment_ids"))
    model = source["model"]
    by_mid = {r["id"]: r for r in model["membranes"]}
    species = [r["id"] for r in model["species"]]
    initial = [
        [
            float(
                Decimal(str(by_mid[mid]["permeability_m_per_s"].get(ion, 0)))
                * Decimal(str(g["thickness_m"][mid]))
            )
            for mid in mems
        ]
        for ion in frozen.IONS
    ]
    permutations = {}

    def row(value):
        s = value["selector"]
        kind = s["kind"]
        if kind == "ids":
            kind = "indices"
            selected = [cells.index(v) for v in s["value"]]
        elif kind == "indices":
            selected = s["value"]
        else:
            selected = []
        if kind == "percent":
            permutations[value["name"]] = [cells.index(v) for v in s["permutation_cell_ids"]]
        return dict(
            name=value["name"],
            picker=kind,
            indices=selected,
            color=s["value"] if kind == "color" else None,
            percent=s["value"] if kind == "percent" else None,
            bitmap=s["value"]["grayscale_F"] if kind == "image" else None,
            diffusivity_m2_s=value["diffusivity_m2_s"],
            insular=value["is_gj_insular"],
        )

    raw = dict(
        layout=dict(
            cell_ids=cells,
            membrane_ids=mems,
            environment_ids=env,
            membrane_cell=[cells.index(v) for v in layout["membrane_cell_ids"]],
            membrane_environment=[env.index(v) for v in layout["membrane_environment_ids"]],
            cell_membranes=[
                [mems.index(v) for v in group] for group in layout["cell_membrane_ids"]
            ],
            cell_centres_m=layout["cell_centres_m"],
            bounds_m=layout["bounds_m"],
            seed_fills=layout["seed_fills"],
            partner_membrane=[mems.index(g["partner_membrane_ids"][mid]) for mid in mems],
            cell_neighbors=[[cells.index(v) for v in g["cell_neighbor_ids"][cid]] for cid in cells],
        ),
        default=row(inputs["default"]),
        profiles=[row(v) for v in inputs["profiles"]],
        enabled=inputs["enabled"],
        is_ecm=inputs["is_ecm"],
        ion_enabled=inputs["ion_enabled"],
        initial_membrane_m2_s=initial,
    )
    values = frozen.profiles(raw, permutations)
    result = deepcopy(source)
    with localcontext() as context:
        context.prec = 80
        selected = {m for target in values["targets"].values() for m in target["membranes"]}
        for patch in result["model"]["membranes"]:
            j = mems.index(patch["id"])
            for i, ion in enumerate(frozen.IONS):
                if inputs["ion_enabled"][i] and j in selected:
                    assert ion in species
                    patch["permeability_m_per_s"][ion] = float(
                        Decimal(str(values["diffusion_m2_s"][i][j]))
                        / Decimal(str(g["thickness_m"][patch["id"]]))
                    )
    edges = {}
    for edge in result["model"]["junctions"]:
        a, b = g["junction_membrane_ids"][edge["id"]]
        weights = [values["gj_weights"][mems.index(v)] for v in (a, b)]
        assert weights[0] == weights[1]
        edges[edge["id"]] = weights[0]
        if weights[0] == 0:
            edge["permeability_m_per_s"] = {ion: 0.0 for ion in edge["permeability_m_per_s"]}
    return dict(definition=result, profile_result=values, insular_junction_weights=edges)


def outward_flux(ci, co, voltage, z, temperature, area, diffusion, thickness, F, R):
    with localcontext() as context:
        context.prec = 80

        def dec(v):
            return Decimal(str(v))

        x = dec(z) * dec(F) * dec(voltage) / (dec(R) * dec(temperature))
        if x == 0:
            return float(
                dec(area) * dec(diffusion) / dec(thickness) * (dec(ci) - dec(co)) / dec(1e-15)
            )
        return float(
            dec(area)
            * dec(diffusion)
            / dec(thickness)
            / dec(1e-15)
            * x
            * (dec(ci) - dec(co) * (-x).exp())
            / (1 - (-x).exp())
        )
