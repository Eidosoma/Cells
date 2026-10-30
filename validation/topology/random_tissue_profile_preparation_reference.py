"""Native random selection followed by independent physical-owner preparation.

The RNGs execute the pinned native picker sites; they are not independently
implemented. Owner expansion, SI conversion and complete physical RHS use the
existing independent references. No Cells or JAX import is needed.
"""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.perturbations import target_selection_native as native
from validation.perturbations import target_selection_reference as selection
from validation.tissue.physiology_permeability_view_reference import ORACLES
from validation.topology import tissue_profile_composition_reference as physical


def native_parameters(request):
    geometry = request["geometry"]
    layout = geometry["layout"]
    cells, membranes, environments = (
        layout[k] for k in ("cell_ids", "membrane_ids", "environment_ids")
    )
    model = request["definition"]["model"]
    leaf = model.get("ionic", model)
    patches = {row["id"]: row for row in leaf["membranes"]}

    def profile(row):
        selector = row["selector"]
        kind, value = selector["kind"], selector["value"]
        indices = (
            [cells.index(v) for v in value] if kind == "ids" else value if kind == "indices" else []
        )
        return dict(
            name=row["name"],
            picker="indices" if kind == "ids" else kind,
            indices=indices,
            percent=value if kind == "percent" else None,
            color=None,
            bitmap=None,
            diffusivity_m2_s=row["diffusivity_m2_s"],
            insular=row["is_gj_insular"],
        )

    with localcontext() as context:
        context.prec = 80
        initial = [
            [
                float(
                    Decimal(str(patches[mid]["permeability_m_per_s"].get(ion, 0)))
                    * Decimal(str(geometry["thickness_m"][mid]))
                )
                for mid in membranes
            ]
            for ion in ("Na", "K", "Cl", "Ca", "M", "P")
        ]
    return dict(
        layout=dict(
            cell_ids=cells,
            membrane_ids=membranes,
            environment_ids=environments,
            membrane_cell=[cells.index(v) for v in layout["membrane_cell_ids"]],
            membrane_environment=[
                environments.index(v) for v in layout["membrane_environment_ids"]
            ],
            cell_membranes=[
                [membranes.index(v) for v in row] for row in layout["cell_membrane_ids"]
            ],
            cell_centres_m=layout["cell_centres_m"],
            bounds_m=layout["bounds_m"],
            seed_fills=layout["seed_fills"],
        ),
        default=profile(request["default"]),
        profiles=[profile(row) for row in request["profiles"]],
        enabled=request["enabled"],
        is_ecm=request["is_ecm"],
        ion_enabled=request["ion_enabled"],
        initial_membrane_m2_s=initial,
        global_gj_percent=request["global_gj_percent"],
    )


def prepare(request):
    raw = native_parameters(request)
    captured = native.evaluate(raw, request["selection_stream"])
    permutations = {
        row["name"]: row["permutation"]
        for row in captured["operations"]
        if row["kind"] == "percent"
    }
    owners = selection.evaluate(raw, request["selection_stream"]["cell_order"], permutations)
    resolved = deepcopy(request)
    for row in resolved["profiles"]:
        if row["selector"]["kind"] == "percent":
            # The static reference decodes declarations before applying the
            # enable flag. A placeholder in a disabled row consumes no RNG and
            # never affects the physical result or target-selection evidence.
            row["selector"]["permutation_cell_ids"] = permutations.get(
                row["name"], raw["layout"]["cell_ids"]
            )
    expected = physical.prepare(resolved)
    return dict(native=captured, selection=owners, physical=expected)


def rates(definition):
    oracle = ORACLES[definition["model"]["id"]]
    context = oracle.bind(definition)
    initial = oracle.initial(context)
    rate, potential, proof = oracle.evaluate(context, initial, 0.0)
    return dict(
        state_fields=list(context["shapes"]),
        initial=initial,
        rate=rate,
        rate_atol=oracle.flatten(
            context,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in context["shapes"].items()
            },
        ),
        potential_V=potential,
        proof=proof,
    )
