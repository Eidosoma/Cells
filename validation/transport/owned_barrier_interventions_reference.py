"""Independent full-owner dynamics with independently recomputed ECM coefficients.

Only the 80-digit native coefficient oracle is reused from passive scheduling.
Every field, channel, store, calcium pump and finite-fuel rate comes from the
complete independent parent. No Cells/JAX, production binder or passive RHS is
called. Cryptographic artifact replay is a separate software contract.
"""

import math
from copy import deepcopy

import numpy as np

from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_kinetic_reference as ionic
from validation.transport import environment_barrier_interventions_reference as native
from validation.transport import environment_barrier_preparation_reference as static

OWNERS = {
    "resolved_active_extracellular_barriers@1": ("resolved_tissue@12", ionic),
    "resolved_calcium_extracellular_barriers@1": ("resolved_calcium@11", calcium),
    "resolved_calcium_energy_extracellular_barriers@1": ("resolved_calcium_energy@5", energy),
}
EXTRA = ("barrier_preparation", "intervention", "phase", "timing_policy")
flatten, unpack = ionic.flatten, ionic.unpack


def leaf(raw):
    outer = raw["model"]
    return outer if outer["id"] == "resolved_tissue@12" else outer["ionic"]


def bind(raw):
    model = raw["model"]
    parent_id, equation = OWNERS[model["id"]]
    if model["phase"] not in ("INIT", "SIM") or model["timing_policy"] != native.TIMING_POLICY:
        raise ValueError("Declare the independent native ECM phase-clock policy")
    parent = deepcopy(raw)
    for key in EXTRA:
        parent["model"].pop(key)
    parent["model"]["id"] = parent_id
    capacity = parent["execution"].pop("barrier_target_capacity")
    artifact = model["barrier_preparation"]
    if parent["model"] != artifact["definition"]["model"]:
        raise ValueError("The entire physical parent must match the prepared owner")
    request = deepcopy(artifact["provenance"]["request"])
    request["definition"]["model"] = deepcopy(leaf(request["definition"]))
    request["definition"]["model"]["id"] = "resolved_tissue@1"
    request["kind"] = static.REQUEST_KIND
    prepared = static.prepare(request)
    maps = prepared["coefficients"]["face_m2_s"]
    for face in leaf(parent)["faces"]:
        for species, value in face["diffusivity_m2_per_s"].items():
            if not math.isclose(
                value, maps[species][face["id"]], rel_tol=64 * np.finfo(float).eps, abs_tol=0
            ):
                raise ValueError("Static face coefficient disagrees with independent arithmetic")
    event = deepcopy(model["intervention"])
    if type(capacity) is not int or not 0 <= capacity <= 65536:
        raise ValueError("Require explicit bounded target capacity")
    if event is not None:
        targets = event["site_ids"]
        if (
            len(targets) > capacity
            or not targets
            or any(site not in request["grid"]["site_ids"] for site in targets)
        ):
            raise ValueError("Target occurrences need known sites and sufficient capacity")
        values = [event[k] for k in ("on_s", "off_s", "change_s", "amplitude")]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError("Require finite pulse numbers")
        on, off, change, amplitude = values
        if not 0 <= on < off <= raw["experiment"]["end_time"] or change <= 0:
            raise ValueError("Invalid phase-local pulse interval")
        if not 0 <= amplitude <= 1:
            raise ValueError("Invalid ECM amplitude")
    bound = equation.bind(parent)
    tolerance = (
        64 * np.finfo(float).eps * max(raw["experiment"]["end_time"], raw["execution"]["dt"])
    )
    coefficients = dict(
        request=request,
        static=prepared,
        event=event,
        phase=model["phase"],
        end_time=raw["experiment"]["end_time"],
        phase_clock_atol_s=tolerance,
    )
    return dict(
        equation=equation,
        parent=bound,
        parent_definition=parent,
        definition=deepcopy(raw),
        coefficients=coefficients,
        shapes=bound["shapes"] | {"phase_clock_s": (1,)},
        phase_clock_atol_s=tolerance,
    )


def initial(context):
    return np.r_[context["equation"].initial(context["parent"]), 0.0]


def coefficient_values(context, clock):
    return native.coefficients(context["coefficients"], float(clock))


def current_parent(context, clock, *, held_time=None):
    signal = coefficient_values(context, clock)
    raw = deepcopy(context["parent_definition"])
    for face in leaf(raw)["faces"]:
        face["diffusivity_m2_per_s"] = {
            s: signal["face_m2_s"][s][face["id"]] for s in face["diffusivity_m2_per_s"]
        }
    if held_time is not None:
        for name, groups in raw["experiment"].items():
            if name.endswith("_controls"):
                for group in groups:
                    key = "controls" if "controls" in group else "schedule"
                    row = deepcopy(next(v for v in reversed(group[key]) if v["time"] <= held_time))
                    row["time"] = 0.0
                    group[key] = [row]
    return context["equation"].bind(raw), signal


def _ionic_energy_rate(bound, state, derivative, potential):
    """Differentiate chemical/capacitive energy with the independent full RHS."""
    d, rate = ionic.unpack(bound, state), ionic.unpack(bound, derivative)
    inside = (bound["ai"] + d["amount_increment"]) / bound["vi"]
    outside = (bound["ao"] + d["extracellular_amount_increment"]) / bound["vo"]
    ni, no = rate["amount_increment"], rate["extracellular_amount_increment"]
    chemical = (
        1e-3
        * ionic.R
        * bound["layout"]["temperature"]
        * (np.sum(np.log(inside) * ni) + np.sum(np.log(outside) * no))
    )
    n = len(bound["vi"])
    valence = np.asarray(bound["layout"]["valence"])
    electrical = 1e-3 * ionic.F * (
        np.sum(valence * ni * potential[:n]) + np.sum(valence * no * potential[n:])
    ) + 1e12 * np.sum(potential[n:] * rate["electrode_charge_transferred_C"])
    heat = sum(float(np.sum(v)) for k, v in rate.items() if k.endswith("_dissipated_energy_pJ"))
    work = sum(
        float(np.sum(rate[k]))
        for k in ("metabolic_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
    )
    return float(chemical + electrical + heat - work)


def evaluate(context, state, time, *, held_time=None):
    value = np.asarray(state)
    expected_size = sum(math.prod(s) for s in context["shapes"].values())
    if value.shape != (expected_size,) or not np.isfinite(value).all():
        raise ValueError("Require the finite complete-owner state and its phase clock")
    clock = float(value[-1])
    if abs(clock - float(time)) > context["phase_clock_atol_s"]:
        raise ValueError("Independent stage time differs from the state-owned phase clock")
    parent, signal = current_parent(context, clock, held_time=held_time)
    derivative, potential, proof = context["equation"].evaluate(parent, value[:-1], clock)
    if context["equation"] is ionic:
        proof = proof | dict(
            physical_energy_balance_pJ_s=_ionic_energy_rate(
                parent, value[:-1], derivative, potential
            )
        )
    return np.r_[derivative, 1.0], potential, proof | dict(ecm_coefficients=signal)
