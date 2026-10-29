"""Independent Decimal pulse/ordered writes plus complete passive field/RHS."""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.tissue import surface_dynamics_reference as passive
from validation.topology.betse_tissue_profiles_reference import IONS, pulse


def parent_definition(raw):
    value = deepcopy(raw)
    for key in ("profile_preparation", "interventions", "phase", "timing_policy", "reset_policy"):
        value["model"].pop(key)
    value["model"]["id"] = "resolved_tissue@1"
    for key in ("intervention_capacity", "intervention_target_capacity"):
        value["execution"].pop(key)
    return value


def permeability(raw, time):
    m = raw["model"]
    p = m["profile_preparation"]["provenance"]
    if p["kind"] == "cells.initial_geometry_profile_preparation@1":
        p = p["profile_preparation"]
    value = parent_definition(raw)
    mems = p["geometry"]["layout"]["membrane_ids"]
    by_mid = {r["id"]: r for r in value["model"]["membranes"]}
    scheduled = [[0.0] * len(mems) for _ in IONS]
    pulses = {}
    with localcontext() as context:
        context.prec = 80

        def d(v):
            return Decimal(str(v))

        for row in sorted(m["interventions"], key=lambda e: IONS.index(e["kind"].split("_")[0])):
            kind = row["kind"]
            ion = IONS.index(kind.split("_")[0])
            pulses[row["name"]] = (
                float(pulse(time, row["on_s"], row["off_s"], row["change_s"]))
                if m["phase"] == "SIM"
                else 0.0
            )
            if (
                m["phase"] != "SIM"
                or kind in ("Cl_mem", "Ca_mem")
                and not p["profile_declarations"]["ion_enabled"][ion]
            ):
                continue
            ids = [
                mid
                for name in row["profiles"]
                for mid in p["binding"]["targets"][name]["membranes"]
            ]
            spatial = row["spatial"]
            for occurrence, mid in enumerate(ids):
                sample = (
                    1
                    if spatial is None
                    else spatial["values"]
                    if isinstance(spatial["values"], (int, float))
                    else spatial["values"][
                        occurrence if spatial["axis"] == "occurrence" else mems.index(mid)
                    ]
                )
                scale = (
                    d(p["profile_declarations"]["default"]["diffusivity_m2_s"][ion])
                    * d(row["amplitude"])
                    * d(row["dynamic_factor"])
                    * d(sample)
                )
                increment = scale * pulse(time, row["on_s"], row["off_s"], row["change_s"])
                scheduled[ion][mems.index(mid)] = float(increment)
                if scale != 0:
                    by_mid[mid]["permeability_m_per_s"][IONS[ion]] = float(
                        (d(p["diffusivity_m2_s"][ion][mems.index(mid)]) + increment)
                        / d(p["geometry"]["thickness_m"][mid])
                    )
    return value, dict(pulse=pulses, scheduled_m2_s=scheduled)


def bind(raw):
    return dict(raw=deepcopy(raw), parent=passive.bind(parent_definition(raw)))


def initial(c):
    return np.r_[passive.initial(c["parent"]), 0.0]


def flatten(c, values):
    return np.r_[passive.flatten(c["parent"], values), np.asarray(values["phase_clock_s"]).ravel()]


def evaluate(c, state, time=None, *, held_time=None):
    clock = float(state[-1])
    raw, events = permeability(c["raw"], clock)
    if held_time is not None:
        for name in ("membrane_controls", "junction_controls"):
            for group in raw["experiment"][name]:
                a = next(
                    v["availability"] for v in reversed(group["schedule"]) if v["time"] <= held_time
                )
                group["schedule"] = [dict(time=0.0, availability=a)]
    context = passive.bind(raw)
    slope, phi, proof = passive.evaluate(context, state[:-1], clock)
    return np.r_[slope, 1.0], phi, proof | dict(events=events)
