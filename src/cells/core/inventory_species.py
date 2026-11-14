"""A definition helper: one more inventory species on @3's species axis (secreted species, D150).

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §1.1 and §1.3. A secreted species is one more row of
resolved_pump_tissue@3's species axis: valence 0, zero membrane and junction permeability and its
own diffusivity on every face. @3 owns its amounts as it owns the ions'. Its face diffusivity is the
effective kind (a FRAP-measured D: free diffusion reduced by tortuosity and hindrance), never a free
(FCS) diffusivity on its own (§6, the lead's ruling).

@3 requires every species to be positive at every active node, so a species that is "absent"
somewhere is declared at a trace background c_bg > 0 in every cell, node, bath and replacement
template (§1.3). Its material ledgers are checked at its own scale with a species-scale floor
(`material_balance_atol_fmol`), far below the ions' 1e-10 fmol.

add_inventory_species works on a raw (dictionary) definition of resolved_pump_tissue@3, or of
resolved_pump_composite@1 over it, and returns a new one: no physics, no new law. Composite
replacement templates (scheduled_cell_replacement@1 or @2) gain the trace in their amounts, scaled
by the template volume, unless an amount is given. Route-only templates are left as they are.
"""

import copy
import math

REPLACEMENT_LAWS = ("scheduled_cell_replacement@1", "scheduled_cell_replacement@2")


def _positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def add_inventory_species(
    raw,
    species_id,
    *,
    trace_mM,
    diffusivity_m2_per_s,
    floor_fmol,
    concentrations_mM=None,
    template_amounts_fmol=None,
):
    """A copy of `raw` with the neutral, membrane-impermeant species `species_id` declared.

    trace_mM: the trace background c_bg (mM) of every cell, outside node (baths included) and full
    replacement template; concentrations_mM {node id: mM} replaces it at named cells or outside
    nodes (a pre-formed profile, a loaded pool or a bath held at c0). diffusivity_m2_per_s: the
    species' effective diffusivity on every face, or {face id: value} naming every face.
    floor_fmol: its material-ledger floor. template_amounts_fmol {template id: fmol} replaces a
    template's trace amount (a granule-loaded newcomer).
    """
    out = copy.deepcopy(raw)
    m, x = out["model"], out["execution"]
    if any(s["id"] == species_id for s in m["species"]):
        raise ValueError(f"Species {species_id!r} is already declared")
    trace = _positive(trace_mM, "trace_mM")
    floor = _positive(floor_fmol, "floor_fmol")
    given = dict(concentrations_mM or {})
    m["species"].append(dict(id=species_id, valence=0))
    nodes = [*m["cells"], *m["extracellular"]]
    unknown = set(given) - {c["id"] for c in nodes}
    if unknown:
        raise ValueError(f"Unknown nodes in concentrations_mM: {sorted(unknown)}")
    for node in nodes:
        c = _positive(given.get(node["id"], trace), f"concentration at {node['id']}")
        node["initial_amount_fmol"][species_id] = c * node["volume_pL"]
    for patch in m["membranes"]:
        patch["permeability_m_per_s"][species_id] = 0.0
    for junction in m.get("junctions", []):
        junction["permeability_m_per_s"][species_id] = 0.0
    faces = m.get("faces", [])
    if isinstance(diffusivity_m2_per_s, dict):
        if set(diffusivity_m2_per_s) != {f["id"] for f in faces}:
            raise ValueError("A diffusivity map names every face exactly once")
        values = {k: _positive(v, f"diffusivity on {k}") for k, v in diffusivity_m2_per_s.items()}
    else:
        d = _positive(diffusivity_m2_per_s, "diffusivity_m2_per_s")
        values = {f["id"]: d for f in faces}
    for face in faces:
        face["diffusivity_m2_per_s"][species_id] = values[face["id"]]
    x["material_balance_atol_fmol"][species_id] = floor
    loaded = dict(template_amounts_fmol or {})
    seen = set()
    for block in m.get("operators", []):
        if block.get("law") not in REPLACEMENT_LAWS:
            continue
        for template in block["templates"]:
            seen.add(template["id"])
            if template["amounts_fmol"] is None:  # Route-only: carries route values only.
                continue
            amount = loaded.get(template["id"], trace * template["volume_pL"])
            template["amounts_fmol"][species_id] = _positive(
                amount, f"template {template['id']} amount"
            )
    if set(loaded) - seen:
        raise ValueError(
            f"Unknown templates in template_amounts_fmol: {sorted(set(loaded) - seen)}"
        )
    return out
