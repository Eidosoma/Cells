"""Synthetic resolved pump worlds: the kinetic fixtures without channel populations.

Parameters are synthetic, not biological measurements. reduction() returns the
same world as resolved_tissue@2 with an empty channel list, for equivalence.
"""

from validation.tissue import surface_kinetic_fixtures as kinetic

ARMS = kinetic.ARMS
FACTORED_SOLVER = "capacitive_reduction_gauged_damped_newton@2"


def reduction(arm="open", *, backend="cpu", padded=True):
    """resolved_tissue@2 with no channels (dense field), the reference identity."""
    raw = kinetic.definition(arm, backend=backend, padded=padded)
    raw["model"]["channels"] = []
    raw["experiment"]["channel_controls"] = []
    raw["execution"]["channel_capacity"] = 0
    return raw


def definition(arm="open", *, backend="cpu", padded=True, solver="rk4", temperature_K=298.15):
    raw = reduction(arm, backend=backend, padded=padded)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"], m["temperature_K"] = "resolved_pump_tissue@1", temperature_K
    del m["channels"], e["channel_controls"], x["channel_capacity"]
    for p in m["junctions"]:
        p["gate"]["law"] = "junction_voltage_relaxation@1"
    x["field_solver"], x["solver"] = FACTORED_SOLVER, solver
    return raw
