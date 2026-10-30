"""Independent prescribed-packet component + continuous held-P loop oracle.

Uses Decimal owner arithmetic and original full independent tissue equations.
No production/Cells/JAX import or independent RNG-engine claim. Tissue dt and
event intervals never replace the declared physiological component duration.
"""

from decimal import Decimal, localcontext

import numpy as np

from validation.perturbations import betse_perturbations_reference as protein_reference
from validation.tissue import physiology_tissue_step_reference as tissue_reference


def component_transition(binding, component, prescribed_uniforms):
    controls = component["controls"]
    inputs, geometry = binding["inputs"], binding["geometry"]
    raw = dict(
        phase=controls["phase"],
        solver=controls["solver"],
        dynamic_enabled=controls["dynamic_enabled"],
        protein_enabled=controls["protein_enabled"],
        dt_s=controls["dt_s"],
        dynamic_level=controls["dynamic_level_mol_m2_s"],
        membrane_area_m2=geometry["membrane_area_m2"],
        cell_volume_m3=geometry["cell_volume_m3"],
        owner=[inputs["cell_ids"].index(name) for name in geometry["membrane_cell_ids"]],
        environment_owner=[
            inputs["environment_ids"].index(name) for name in geometry["membrane_environment_ids"]
        ],
        environment_volume_m3=geometry["environment_volume_m3"][0],
        is_ecm=True,
        fast_update_ecm=False,
    )
    active = protein_reference.active(raw)
    if active != (prescribed_uniforms is not None):
        raise ValueError("Prescribed packet must obey the original component draw guard")
    if active:
        uniforms = np.asarray(prescribed_uniforms)
        if (
            uniforms.shape != (len(inputs["membrane_ids"]),)
            or not np.isfinite(uniforms).all()
            or np.any((uniforms < 0) | (uniforms >= 1))
        ):
            raise ValueError("Require one original uniform packet per active physiological call")
    protein = component["protein"]
    result = protein_reference.protein(
        raw,
        dict(
            cell=protein["cell_mol_m3"],
            membrane=protein["membrane_mol_m3"],
            environment=protein["environment_mol_m3"],
        ),
        prescribed_uniforms,
    )
    diffusion = {key: np.asarray(value) for key, value in component["diffusion"].items()}
    if controls["phase"] == "SIM":
        base, scheduled = diffusion["base_m2_s"], diffusion["scheduled_m2_s"]
        if base.shape != scheduled.shape:
            raise ValueError("Require complete matching declared diffusion buffers")
        with localcontext() as context:
            context.prec = 80
            current = np.empty_like(base, dtype=float)
            for index in np.ndindex(base.shape):
                current[index] = float(
                    Decimal.from_float(float(base[index]))
                    + Decimal.from_float(float(scheduled[index]))
                )
        diffusion = diffusion | dict(current_m2_s=current)
    return dict(
        protein={
            name: np.asarray(result["state"][key])
            for name, key in (
                ("cell_mol_m3", "cell"),
                ("membrane_mol_m3", "membrane"),
                ("environment_mol_m3", "environment"),
            )
        },
        diffusion=diffusion,
        controls=dict(controls),
        time_s=float(component["time_s"]) + float(controls["dt_s"]),
        loop_calls=component["loop_calls"] + 1,
        stream_next_tick=component["stream_next_tick"] + int(active),
        active=active,
        prescribed_uniforms=prescribed_uniforms,
        flux_mol_m2_s=result["flux"],
    )


def advance(raw, fields, binding, component, prescribed_uniforms, *, loop_index, refinement=1):
    """Own continuous reference state across every original subinterval.

    Callers must carry returned fields into the next reference loop; reseeding
    from a production RK endpoint is not trajectory qualification.
    """
    if type(loop_index) is not int or loop_index < 0:
        raise ValueError("Require an explicit nonnegative nominal loop index")
    dt = float(component["controls"]["dt_s"])
    start, end = loop_index * dt, (loop_index + 1) * dt
    points = tissue_reference.grid(raw)
    if not np.isfinite([dt, start, end]).all() or dt <= 0 or end <= start:
        raise ValueError("Require a full finite physiological interval")
    if start not in points or end not in points or end > raw["experiment"]["end_time"]:
        raise ValueError("Nominal boundaries must be exact original tissue grid points")
    proposed = component_transition(binding, component, prescribed_uniforms)
    oracle = tissue_reference.view.ORACLES[raw["model"]["id"]]
    intervals = []
    for before, after in zip(points, points[1:], strict=False):
        if before < start or after > end:
            continue
        result = tissue_reference.integrate(
            raw,
            fields,
            binding,
            proposed["diffusion"]["current_m2_s"],
            start_time_s=before,
            end_time_s=after,
            refinement=refinement,
        )
        fields = oracle.unpack(result["context"], result["state"])
        intervals.append(result)
    if not intervals or intervals[-1]["end_time_s"] != end:
        raise ValueError("Independent subintervals did not cover the full nominal interval")
    return dict(
        component=proposed,
        fields=fields,
        state=intervals[-1]["state"],
        endpoint_potential_V=intervals[-1]["endpoint_potential_V"],
        context=intervals[-1]["context"],
        intervals=intervals,
        start_time_s=start,
        end_time_s=end,
        physiological_dt_s=dt,
        tissue_nominal_dt_s=raw["execution"]["dt"],
        next_loop_index=loop_index + 1,
        refinement=refinement,
    )
