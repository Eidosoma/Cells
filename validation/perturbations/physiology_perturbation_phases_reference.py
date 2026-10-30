"""Independent prescribed-packet reference for component phase separation.

No Cells/JAX imports or RNG-engine claim. Raw owner geometry and the existing
independent Decimal protein law define the post-ion proposal. Preparation has
no clock/tick/protein update; finish uses the original full component duration.
"""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.perturbations import betse_perturbations_reference as protein_reference


def _controls(raw, state):
    controls = state["controls"]
    return raw | dict(
        phase=controls["phase"],
        solver=controls["solver"],
        dynamic_enabled=controls["dynamic_enabled"],
        protein_enabled=controls["protein_enabled"],
        dt_s=controls["dt_s"],
        dynamic_level=controls["dynamic_level_mol_m2_s"],
    )


def prepare(raw, state):
    controls = _controls(raw, state)
    result = deepcopy(state)
    if state["loop_calls"] >= 2**64 - 1:
        raise ValueError("Component count cannot advance")
    end = float(state["time_s"]) + float(controls["dt_s"])
    if not np.isfinite(end) or end <= state["time_s"]:
        raise ValueError("Component duration cannot advance finitely")
    if controls["phase"] == "SIM":
        base = np.asarray(state["diffusion"]["base_m2_s"])
        scheduled = np.asarray(state["diffusion"]["scheduled_m2_s"])
        current = np.empty_like(base, dtype=float)
        with localcontext() as context:
            context.prec = 80
            for index in np.ndindex(base.shape):
                current[index] = float(
                    Decimal.from_float(float(base[index]))
                    + Decimal.from_float(float(scheduled[index]))
                )
        if not np.isfinite(current).all() or np.any(current < 0):
            raise ValueError("Prepared physical permeability leaves its domain")
        result["diffusion"]["current_m2_s"] = current
    return dict(
        source=deepcopy(state), held=result, dynamic_active=protein_reference.active(controls)
    )


def finish(raw, state, prepared, prescribed_uniforms):
    """Compute one full-dt protein proposal, after an external ionic interval."""
    controls = _controls(raw, state)
    expected = prepare(raw, state)
    for domain in ("protein", "diffusion"):
        for name, value in expected["source"][domain].items():
            if not np.array_equal(value, prepared["source"][domain][name]):
                raise ValueError("Changed source in independent phase reference")
    for name in ("time_s", "loop_calls", "stream_next_tick", "controls"):
        if expected["source"][name] != prepared["source"][name]:
            raise ValueError("Changed clock/controls in independent phase reference")
    active = expected["dynamic_active"]
    if active != (prescribed_uniforms is not None):
        raise ValueError("Prescribed packet violates the original dynamic guard")
    if active and state["stream_next_tick"] >= 2**64 - 1:
        raise ValueError("Active draw counter cannot advance")
    protein = state["protein"]
    proposal = protein_reference.protein(
        controls,
        dict(
            cell=protein["cell_mol_m3"],
            membrane=protein["membrane_mol_m3"],
            environment=protein["environment_mol_m3"],
        ),
        prescribed_uniforms,
    )
    result = deepcopy(expected["held"])
    result["protein"] = {
        name: np.asarray(proposal["state"][key])
        for name, key in (
            ("cell_mol_m3", "cell"),
            ("membrane_mol_m3", "membrane"),
            ("environment_mol_m3", "environment"),
        )
    }
    result.update(
        time_s=float(state["time_s"]) + float(controls["dt_s"]),
        loop_calls=state["loop_calls"] + 1,
        stream_next_tick=state["stream_next_tick"] + int(active),
    )
    return result
