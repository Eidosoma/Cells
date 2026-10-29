"""Manufactured explicit ideal baths; no calibrated tissue or equilibration claim."""

from copy import deepcopy

from validation.tissue import active_excision_fixtures as active
from validation.tissue import surface_excision_fixtures as passive

FAMILIES = ("passive", "active")
CASES = ("overlap", "single", "negative", "empty", "disabled", "init", "permuted")
DT = 62.5e-9
END = 8e-6
MODEL_IDS = dict(passive="resolved_passive_bath_events@1", active="resolved_active_bath_events@1")


def definition(family="active", case="overlap", *, padded=True):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    raw = (
        active.definition("clamped", catalog="full", padded=padded)
        if family == "active"
        else passive.definition("clamped", padded=padded)
    )
    m, e, x = (raw[k] for k in ("model", "experiment", "execution"))
    # The counterion is a real mobile inventory/charge owner. Its fixed
    # background is declared compatibly in this manufactured initial input.
    m["species"].append(dict(id="M", valence=-1))
    for row in (*m["cells"], *m["extracellular"]):
        amount = 20.0 * row["volume_pL"]
        row["initial_amount_fmol"]["M"] = amount
        row["fixed_charge_equivalent_fmol"] += amount
    for kind, key in (
        ("membranes", "permeability_m_per_s"),
        ("junctions", "permeability_m_per_s"),
        ("faces", "diffusivity_m2_per_s"),
    ):
        for row in m[kind]:
            row[key]["M"] = 1e-10
    x["material_balance_atol_fmol"]["M"] = 2e-11
    x.update(dt=DT, jit=False, max_steps=512, max_trace_bytes=2**28)
    events = [
        dict(kind="K_env", on_s=0.25e-6, off_s=4e-6, change_s=1e-6, amplitude=0.25),
        dict(kind="Cl_env", on_s=1e-6, off_s=5e-6, change_s=1.5e-6, amplitude=0.02),
        dict(kind="Na_env", on_s=2e-6, off_s=6e-6, change_s=1e-6, amplitude=0.01),
    ]
    if case == "single":
        events = events[:1]
    elif case == "negative":
        events = events[:1]
        events[0]["amplitude"] = -0.2
    elif case == "empty":
        events = []
    elif case == "disabled":
        events = events[1:2]
    m.update(
        id=MODEL_IDS[family],
        bath_events=events,
        bath_site_ids=["bath", "shared"],
        enabled_Cl=case != "disabled",
        phase="INIT" if case == "init" else "SIM",
        timing_policy="phase_clock_rk_stage_native_logistic@1",
        controller_policy="explicit_ideal_reservoir_dose_voltage_compensation_work@1",
        baseline_policy="each_declared_reservoir_reference_concentration@1",
    )
    clocks = {i * DT for i in (0, 4, 8, 16, 20, 32, 40, 48, 60, 64, 72, 80, 96, 112, 128)}
    e.update(end_time=END)
    for kind, switch in (
        ("membrane", 1.25e-6),
        ("junction", 2.5e-6),
        ("channel", 3.75e-6),
        ("pump", 4.5e-6),
    ):
        for i, group in enumerate(e.get(kind + "_controls", [])):
            group["schedule"] = [dict(time=0.0, availability=0.8)]
            if i == 0:
                group["schedule"].append(dict(time=switch, availability=0.4))
                clocks.add(switch)
    # Accepted observation boundaries are declared as unchanged-value held
    # controls, avoiding any hidden observation-induced integration splits.
    carrier = e["membrane_controls"][0]
    previous = deepcopy(carrier["schedule"])
    carrier["schedule"] = [
        dict(
            time=t,
            availability=next(v["availability"] for v in reversed(previous) if v["time"] <= t),
        )
        for t in sorted(clocks)
    ]
    e["observation_times"] = sorted(clocks)
    if case == "permuted":
        for key in (
            "species",
            "cells",
            "extracellular",
            "membranes",
            "junctions",
            "faces",
            "channels",
        ):
            if key in m:
                m[key].reverse()
        m["bath_site_ids"].reverse()
        for key, groups in e.items():
            if key.endswith("_controls"):
                groups.reverse()
    return raw
