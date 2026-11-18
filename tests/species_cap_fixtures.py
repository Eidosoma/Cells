"""A world above the old species cap of 7 that exercises the host's sum order (FR-9 / D165).

The W4 probe's cell_charged_9 (/mnt/workspaces/Cells/inventory-coupling-20261114-01/w4-cap-probe/
species_cap_probe.py, cell(1, charged=4)), rebuilt here from the validation fixtures:
- one heredity cell, H kicked by 4 mV so its ions move, on its held bath: a single column on both
  node axes, NumPy's pairwise case;
- four mobile charged species Q1 to Q4 (valences 1, -1, 2, -2) at cell-to-bath gradients,
  permeant through the membrane at 1e-10 m/s and immobile on faces and junctions, each node's
  fixed background absorbing their charge so every charge anchor is unchanged;
- D150's neutral species S, produced and cleared in the cell by scheduled_species_turnover@1.

That is 9 species (Na, K, M, P, Q1 to Q4, S), seven of them moving charged rows below slot 8. At 8
or more terms NumPy's host sums over the species axis take the pairwise order, so the host
charge_increment can differ from the explicit species-order sum that every ledger uses.
"""

import copy

import numpy as np

from cells.definitions import pump_composite_spec as cs
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import surface_pump_v3_fixtures as v3fx

Q_SPECIES = ((1, 2.0, 4.0), (-1, 3.0, 1.5), (2, 1.0, 2.0), (-2, 1.5, 0.5))  # z, cell mM, bath mM.
Q_PERMEABILITY = 1e-10  # m/s.


def add_charged(raw, name, valence, cell_mM, bath_mM, permeability):
    """A charged species at cell_mM in every cell and bath_mM in every outside node, permeant
    through every membrane, immobile on faces and junctions; each node's fixed background absorbs
    its charge."""
    out = copy.deepcopy(raw)
    m, x = out["model"], out["execution"]
    m["species"].append(dict(id=name, valence=valence))
    for nodes, mM in ((m["cells"], cell_mM), (m["extracellular"], bath_mM)):
        for node in nodes:
            amount = mM * node["volume_pL"]
            node["initial_amount_fmol"][name] = amount
            node["fixed_charge_equivalent_fmol"] -= valence * amount
    for patch in m["membranes"]:
        patch["permeability_m_per_s"][name] = permeability
    for junction in m.get("junctions", []):
        junction["permeability_m_per_s"][name] = 0.0
    for face in m.get("faces", []):
        face["diffusivity_m2_per_s"][name] = 0.0
    x["material_balance_atol_fmol"][name] = 1e-10
    return out


def charged_nine(*, dt=1e-3, steps=50):
    """The 9-species world, observed at every step."""
    end = steps * dt
    state = v3fx.kicked(v3fx.HEREDITY_STATES["H"], 4.0)
    raw = v3fx.heredity_cells(
        [state],
        dt=dt,
        end_time=end,
        observation_times=[k * dt for k in range(steps)] + [end],
        gate_voltages=[v3fx.HEREDITY_STATES["H"][0]],
    )
    for j, (z, cell_mM, bath_mM) in enumerate(Q_SPECIES):
        raw = add_charged(raw, f"Q{j + 1}", z, cell_mM, bath_mM, Q_PERMEABILITY)
    raw = add_inventory_species(
        raw,
        fx.SPECIES,
        trace_mM=1e-5,
        diffusivity_m2_per_s=1e-10,
        floor_fmol=1e-20,
        concentrations_mM={"cell_0": 1e-4},
    )
    raw = cs.frozen_definition(raw)
    routes = [("produce_S", "cell_0", "production"), ("clear_S", "cell_0", "clearance")]
    controls = [("produce_S", "cell_0", [(0.0, 1e-5)]), ("clear_S", "cell_0", [(0.0, 0.2)])]
    return fx.with_turnover(raw, routes, controls)


def species_order(spec, result):
    """On every observed state: NumPy's charge_increment (the host's sum over the species axis)
    against the explicit species-order sum (capacitor_change, which the ledgers use), and the
    explicit host sum against the compiled one. Returns (rows, rows where NumPy differs in the
    cells, explicit host equal to compiled on every row)."""
    import jax
    import jax.numpy as jnp

    from cells.models import pump_composite as pc
    from cells.models import surface_tissue as tissue

    model = pc.model_for(spec.model)
    _, parameters = model.initial_values(spec)
    layout = model.inner.inner_layout(parameters)
    cells = layout.active.size
    compiled = jax.jit(lambda s: tissue.capacitor_change(s, layout, xp=jnp)[0])
    differs, same_compiled = 0, True
    for i in range(len(result.times)):
        state = model.STATE_TYPE(*(np.asarray(v[i]) for v in result.history))
        inner = model.inner_state(state)
        numpy_sum = np.asarray(tissue.charge_increment(inner, layout, xp=np))
        explicit = np.asarray(tissue.capacitor_change(inner, layout, xp=np)[0])
        differs += int(not np.array_equal(numpy_sum[:cells], explicit[:cells]))
        same_compiled &= bool(np.array_equal(explicit, np.asarray(compiled(inner))))
    return len(result.times), differs, same_compiled
