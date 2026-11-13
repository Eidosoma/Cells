"""Worlds for resolved_pump_replacement@1 tests and studies (definitions only).

Heredity sheets: validation/stationary/worlds.e07_sheet_definition (E07-v1 cells,
own held baths, voltage-gated junctions), with every fixed background zero
(worlds.ionic_background), so one template fits every slot. Templates are taken
from a declared cell of the definition (its declared amounts and gates); a
template from the declared H state is the isolated H steady state of the
pre-screens.
"""

import copy

from validation.stationary import worlds
from validation.tissue import surface_pump_v3_fixtures as fx

FORMATION = dict(
    law="delayed_first_order_junction_formation@1",
    initial_abundance=0.0,
    lag_s=600.0,
    time_constant_s=1800.0,
    gate_at_arrival="law_open",
)
NO_ROUTES = dict(
    channel_permeability_m_per_s={},
    channel_abundance={},
    membrane_permeability_m_per_s={},
    pump_capacity_fmol_per_s_m2=None,
    calcium_pump_capacity_fmol_per_s_m2=None,
)


def heredity_sheet(radius=1, disc=None, *, scale=0.6, dt=1e-3, end_time=0.1, solver=None):
    """A hexagonal heredity sheet (D inside ring `disc`, H elsewhere) as a raw @3 definition."""
    cells, edges = worlds.hexagon(radius)
    states = {k: v[:4] for k, v in fx.HEREDITY_STATES.items()}
    written = [
        states["D"] if disc is not None and worlds.ring(c) <= disc else states["H"] for c in cells
    ]
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition(
            written, edges, scale=scale, gated=True, dt=dt, end_time=end_time
        )
    )
    if solver is not None:
        raw["execution"]["solver"] = solver
    return raw


def template_from_cell(raw, cell_id, template_id, *, routes=None):
    """A template with the declared amounts and channel gates of one cell."""
    m = raw["model"]
    cell = next(c for c in m["cells"] if c["id"] == cell_id)
    membranes = {p["id"] for p in m["membranes"] if p["inside"] == cell_id}
    gates = {
        c["kinetic_law"]: list(c["initial_gate"])
        for c in m["channels"]
        if c["membrane_id"] in membranes and c["initial_gate"]
    }
    return dict(
        id=template_id,
        volume_pL=cell["volume_pL"],
        fixed_charge_equivalent_fmol=cell["fixed_charge_equivalent_fmol"],
        amounts_fmol=dict(cell["initial_amount_fmol"]),
        channel_gates=gates,
        route_values=copy.deepcopy(NO_ROUTES if routes is None else routes),
    )


def with_replacement(raw, templates=(), events=(), *, formation=None, capacity=None):
    """The raw definition as resolved_pump_replacement@1.

    events: (time, slot, template, carrier) for isolated templates, or (time, slot,
    template or None, carrier, donor) for donor copies.
    """
    raw = copy.deepcopy(raw)
    raw["model"]["id"] = "resolved_pump_replacement@1"
    raw["model"]["replacement"] = dict(
        law="scheduled_cell_replacement@1",
        inner_model="resolved_pump_tissue@3",
        junction_formation=dict(FORMATION if formation is None else formation),
        templates=[copy.deepcopy(t) for t in templates],
        template_capacity=max(1, len(templates)) if capacity is None else capacity,
    )
    raw["experiment"]["replacement_events"] = [event(*e) for e in events]
    return raw


def event(time, slot, template, carrier, donor=None):
    """An isolated_template event, or a donor_copy (inheritance route) when donor is given."""
    return dict(
        time=time,
        slot=slot,
        newcomer="isolated_template" if donor is None else "donor_copy",
        template=template,
        donor=donor,
        carrier_id=carrier,
    )


def route_template(template_id, routes=None):
    """A route-only template (route values for donor copies; no state)."""
    return dict(
        id=template_id,
        volume_pL=None,
        fixed_charge_equivalent_fmol=None,
        amounts_fmol=None,
        channel_gates=None,
        route_values=copy.deepcopy(NO_ROUTES if routes is None else routes),
    )


def over_water(
    raw,
    templates=(),
    events=(),
    *,
    impermeant=("P",),
    pf_m_s=5e-4,
    availability=1.0,
    impermeant_fmol=0.0,
    formation=None,
):
    """[water, scheduled_cell_replacement@2] on a raw @3 definition (v2 design §2): water as
    pump_water_fixtures.with_water declares it, then the replacement block of with_replacement
    under law @2, with its impermeant species. Templates' volume_pL are arrival volumes."""
    from cells.core import pump_composite_spec as cs
    from validation.tissue import pump_water_fixtures as wfx

    water = cs.frozen_definition(
        wfx.with_water(
            raw, pf_m_s=pf_m_s, availability=availability, impermeant_fmol=impermeant_fmol
        )
    )
    v1 = cs.frozen_definition(with_replacement(raw, templates, events, formation=formation))
    block = dict(copy.deepcopy(v1["model"]["operators"][0]), law="scheduled_cell_replacement@2")
    block["impermeant_species"] = list(impermeant)
    water["model"]["operators"].append(block)
    water["experiment"]["replacement_events"] = v1["experiment"]["replacement_events"]
    return water
