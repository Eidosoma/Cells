"""Worlds of scheduled_cell_replacement@2 over water (docs/PUMP_COMPOSITE_V2_DESIGN.md §2).

The heredity sheet of the replacement fixtures (seven cells, each facing its own held bath,
the centre cell_3 in D and the ring in H, voltage-gated junctions, no fixed background) under
ideal_osmosis_linear_compliance_water@1 as pump_water_fixtures.with_water declares it, then
scheduled_cell_replacement@2 with the replacement fixtures' templates and events. Every cell
carries the same impermeant P, which no route moves.
"""

from validation.tissue import cell_replacement_fixtures as rfx

WATER = "ideal_osmosis_linear_compliance_water@1"
LAW = "scheduled_cell_replacement@2"
V1 = "scheduled_cell_replacement@1"
DT = 1e-3
PF_M_S = 5e-4  # Fast water (aquaporin range), so volumes move within a short run.


def sheet(*, end=0.05, observed=None, solver=None, dt=DT):
    """The raw @3 heredity sheet."""
    raw = rfx.heredity_sheet(1, 0, dt=dt, end_time=end, solver=solver)
    raw["experiment"]["observation_times"] = list(observed or [0.0, end])
    return raw


def templates(raw, volumes=None):
    """Templates "h" (cell_1's declared state) and "d" (cell_3's), with arrival volumes."""
    out = [rfx.template_from_cell(raw, "cell_1", "h"), rfx.template_from_cell(raw, "cell_3", "d")]
    for t in out:
        if volumes and t["id"] in volumes:
            t["volume_pL"] = volumes[t["id"]]
    return out


def ring_neighbours(raw):
    """(slot, donor): two H cells of the ring that share a junction."""
    for j in raw["model"]["junctions"]:
        if "cell_3" not in (j["sender"], j["receiver"]):
            return j["sender"], j["receiver"]
    raise ValueError("no ring junction")


def over_water(raw, templates=(), events=(), **kw):
    """[water, replacement@2] (validation/tissue/cell_replacement_fixtures.over_water), with
    fast water by default."""
    return rfx.over_water(raw, templates, events, **{"pf_m_s": PF_M_S, **kw})


def replacement_v1(raw, templates=(), events=(), *, formation=None):
    """The same replacement as the frozen resolved_pump_replacement@1 definition."""
    return rfx.with_replacement(raw, templates, events, formation=formation)
