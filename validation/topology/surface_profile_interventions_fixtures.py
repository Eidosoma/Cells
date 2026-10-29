"""Explicit four-ion passive manufactured inputs and membrane-only phase events."""

from copy import deepcopy

from validation.topology.tissue_profile_preparation_fixtures import inputs as static_inputs

CASES = ("SIM", "INIT", "guards", "negative-safe", "transient-zero", "empty")


def inputs(case="SIM", *, permuted=True):
    raw = static_inputs("passive", "no-later-profiles", permuted=permuted)
    m = raw["definition"]["model"]
    e = raw["definition"]["experiment"]
    x = raw["definition"]["execution"]
    m["species"].append(dict(id="Ca", valence=2))
    for kind in ("cells", "extracellular"):
        for i, row in enumerate(m[kind]):
            amount = (0.002 + 0.0003 * i if kind == "cells" else 1.8 + 0.1 * i) * row["volume_pL"]
            row["initial_amount_fmol"]["Ca"] = amount
            row["fixed_charge_equivalent_fmol"] -= 2 * amount
    for row in m["membranes"]:
        row["permeability_m_per_s"]["Ca"] = 1e-10
    for row in m["junctions"]:
        row["permeability_m_per_s"]["Ca"] = 1e-8
    for row in m["faces"]:
        row["diffusivity_m2_per_s"]["Ca"] = 1e-12
    x.update(dt=0.125e-6, jit=False, max_steps=128, max_trace_bytes=2**26)
    x["material_balance_atol_fmol"]["Ca"] = 1e-11
    e.update(end_time=10e-6, observation_times=[0.0, 5e-6, 10e-6])
    for kind in ("membrane", "junction"):
        for row in e[kind + "_controls"]:
            initial = row["schedule"][0]["availability"]
            row["schedule"] = [
                dict(time=0.0, availability=initial),
                dict(time=5e-6, availability=0.6 * initial),
            ]
    cells = raw["geometry"]["layout"]["cell_ids"]

    def profile(name, ids, scale):
        return dict(
            name=name,
            selector=dict(
                kind="ids", value=ids, expected_layout_identity=None, permutation_cell_ids=None
            ),
            diffusivity_m2_s=[scale * (i + 1) * 1e-18 for i in range(6)],
            is_gj_insular=False,
        )

    raw["profiles"] = [
        profile("Region", [cells[0], cells[1], cells[0]], 4),
        profile("Selected", [cells[-1]], 2),
    ]
    raw["ion_enabled"] = [True, True, True, True, False, False]
    if case == "guards":
        raw["ion_enabled"] = [False] * 6
    if case == "transient-zero":
        raw["ion_enabled"][0] = False
        for row in m["membranes"]:
            row["permeability_m_per_s"]["Na"] = 0.0
    mids = raw["geometry"]["layout"]["membrane_ids"]
    count = sum(
        len(raw["geometry"]["layout"]["cell_membrane_ids"][cells.index(cid)])
        for cid in raw["profiles"][0]["selector"]["value"]
    )
    events = []
    for i, kind in enumerate(("Ca_mem", "Na_mem", "Cl_mem", "K_mem")):
        names = (
            ["Region", "Selected"]
            if kind == "Na_mem"
            else ["Region", "Region"]
            if kind == "Cl_mem"
            else ["Default"]
            if kind == "K_mem"
            else ["Selected"]
        )
        occurrence = sum(
            len(raw["geometry"]["layout"]["cell_membrane_ids"][cells.index(cid)])
            for name in names
            for cid in (
                cells
                if name == "Default"
                else next(p for p in raw["profiles"] if p["name"] == name)["selector"]["value"]
            )
        )
        spatial = (
            dict(values=[0.25 + 0.1 * j for j in range(occurrence)], axis="occurrence")
            if kind == "Na_mem"
            else dict(values=[0.5 + 0.05 * j for j in range(len(mids))], axis="membrane")
            if kind == "Cl_mem"
            else None
        )
        events.append(
            dict(
                name="event-" + kind,
                kind=kind,
                profiles=names,
                on_s=2e-6,
                off_s=6e-6,
                change_s=1e-6,
                amplitude=-0.2 if case == "negative-safe" else 0.7 + 0.1 * i,
                spatial=spatial,
                source_function="explicit_samples" if spatial is not None else "None",
                dynamic_factor=0.8 if kind == "Na_mem" else 1.0,
            )
        )
    if case == "transient-zero":
        events = [next(row for row in events if row["kind"] == "Na_mem")]
        events[0].update(on_s=1e-6, off_s=2e-6, change_s=0.1e-6)
        x["dt"] = 0.01e-6
        x["max_steps"] = 1100
    if case == "empty":
        events = []
    raw.update(
        interventions=events,
        phase="INIT" if case == "INIT" else "SIM",
        intervention_capacity=4,
        intervention_target_capacity=max(2, 2 * count + 8),
    )
    return deepcopy(raw)
