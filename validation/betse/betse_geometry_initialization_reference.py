"""Independent seed replay and geometry metrics, reusing verified stdlib tools."""

import math
from copy import deepcopy
from decimal import localcontext

from validation.betse.betse_environment_field_reference import d, serial
from validation.geometry.betse_geometry_reference import cell_geometry
from validation.perturbations.time_modulation_reference import pi, sine
from validation.tissue.physiology_protein_packet_provider_reference import _mt_uniforms


def evaluate_seed(recipe, before, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two declared independent precision settings")
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        data = recipe["native_input"]
        if recipe["classification"] == "manufactured_seed_cloud":
            return dict(
                points_m=deepcopy(data["seed_points_m"]),
                x_uniforms=[],
                y_uniforms=[],
                rng_before=deepcopy(before),
                rng_after=deepcopy(before),
                precision=context.prec,
            )
        mesh = data["mesh"]
        sides, radius, noise = (
            mesh["single_cell_sides"],
            d(mesh["cell_radius"]),
            d(mesh["single_cell_noise"]),
        )
        ux, intermediate = _mt_uniforms(before, sides + 1)
        uy, after = _mt_uniforms(intermediate, sides + 1)
        points = []
        for n in range(sides + 1):
            if n == sides:
                x = y = d(0)
            else:
                # The source stores each binary64 phase before the ufunc.
                phase = d((2 * n * math.pi) / sides)
                x, y = 2 * radius * sine(phase + pi() / 2), 2 * radius * sine(phase)
            points.append([x + d(ux[n]) * radius * noise, y + d(uy[n]) * radius * noise])
        return serial(
            dict(
                points_m=points,
                x_uniforms=ux,
                y_uniforms=uy,
                rng_before=before,
                rng_after=after,
                precision=context.prec,
            )
        )


def geometry_metrics(source):
    """Independent polygon/edge/owner equations conditional on B09 topology."""
    return cell_geometry(source["generation"]["native_capture_record"])
