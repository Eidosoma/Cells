"""FR-4's world through the engine (validation/compartment_ph_engine/definitions.py; the note's
§13.1).

The development world (the declared world without FR-1's compartment operator, the lead's ruling) at
the declared 1 ms, for a few steps from its pH 7.2 start, with the built-in kinds on BUILTIN: B4's
closure, the proton pump and the proton leak, beside the K+ route.
- every accepted row passes all ten ledgers (energy with B4's stored term, the pump's heat and the
  maintenance's work, the leak's and the K+ route's heat);
- the pump moves 2 H_eq per cycle from the cytosol into the lumen and the leak returns some, so the
  lumen's H_eq changes by exactly their difference, and the lumen acidifies;
- the held fuel never changes.
K2's 5-step run (the self-consistent reversed pump, about a minute) is in
test_fr4_world_engine_k2.py, split from here for the tiers (the lead's ruling, 15 November 2026);
the helpers stay here.
"""

import copy

import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.models import get_model
from validation.compartment_ph_engine import definitions as defs

STEPS = 5


def short(definition, steps=STEPS):
    """The definition over its first `steps` steps, recorded at its start and end."""
    d = copy.deepcopy(definition)
    dt = d["execution"]["dt"]
    d["experiment"]["end_time"] = steps * dt
    d["experiment"]["observation_times"] = [0.0, steps * dt]
    d["execution"]["max_steps"] = steps + 8
    return d


def test_the_development_world_runs_with_every_ledger_closing():
    spec = parse_spec(defs.development_world(short(defs.fr4_world())))
    model = get_model(spec.model)
    assert [k for k, _ in model.structure.kinds] == [
        "cells.kind.passive_routes@1",
        "cells.kind.rapid_proton_buffer@1",
        "cells.kind.transporter@1",
    ]
    result = run(spec)  # Host checks on every accepted row: all ten ledgers.
    final, obs, ids = result.final.state, result.observations, list(spec.model.species_ids)
    h = ids.index("H")
    lumen = [n.id for n in spec.model.extracellular].index(defs.LUMEN)
    bounding = [p.id for p in spec.model.membranes].index(defs.BOUNDING)
    cycles = float(final.transporter_cycles[bounding])
    leak_in = float(final.passive_transferred[h, 0])  # Lumen to cytosol (inward-positive).
    assert cycles > 0 and leak_in > 0
    gained = float(final.extracellular_amount_increment[h, lumen])
    assert gained == pytest.approx(2 * cycles - leak_in, rel=1e-12)
    assert float(final.amount_increment[h, 0]) == pytest.approx(leak_in - 2 * cycles, rel=1e-12)
    for row in defs.FUEL_ROWS:
        assert float(final.amount_increment[ids.index(row), 0]) == 0.0
    ph_lumen = obs.pH[:, len(spec.model.cells) + lumen]  # B4's readout: cells, then outside.
    assert ph_lumen[0] == pytest.approx(7.2, abs=1e-9) and ph_lumen[-1] < ph_lumen[0]
    assert result.diagnostics["max_energy_balance_relative"] < 2e-3


def test_the_engine_records_give_the_judges_readouts_on_the_development_world():
    """validation/compartment_ph_engine/engine_records.run, the generator's engine path: every
    ENGINE_READOUTS series of FR-4 at each record, the energy identity from the engine's ledger,
    every row at every node, B4's running extrema and the charge ledger within its tolerance."""
    from validation.compartment_ph_engine import engine_records

    record = engine_records.run(short(defs.fr4_world()))
    assert record["admitted"] and record["completed"] and record["refusal"] is None
    assert record["steps"] == STEPS and record["record_s"] == pytest.approx([0.0, STEPS * 1e-3])
    s = record["series"]
    for name in ("pH_L", "pH_c", "V_b", "Heq_L", "Heq_c", "K_L", "K_c", "cycles", "work_pJ",
                 "heat_pJ", "stored_change_pJ", "energy_residual_pJ", "energy_flows_pJ",
                 "moved_H_pump", "moved_H_leak", "heat_pump_pJ", "heat_proton_leak_0_pJ",
                 "heat_bounding_0_K_pJ"):
        assert len(s[name]) == 2, name
    assert s["pH_L"][0] == pytest.approx(7.2, abs=1e-9) and s["pH_L"][1] < s["pH_L"][0]
    assert s["moved_H_pump"][1] == pytest.approx(2 * s["cycles"][1], rel=1e-15)
    gained = s["Heq_L"][1] - s["Heq_L"][0]  # Both transfers are counted cytosol to lumen.
    assert s["moved_H_leak"][1] < 0  # The leak returns protons to the cytosol.
    assert gained == pytest.approx(s["moved_H_pump"][1] + s["moved_H_leak"][1], rel=1e-9)
    for k in range(2):  # The identity, as the ledger books it.
        assert s["energy_residual_pJ"][k] == pytest.approx(
            s["stored_change_pJ"][k] + s["heat_pJ"][k] - s["work_pJ"][k], abs=1e-15)
    assert abs(s["energy_residual_pJ"][1]) <= 2e-3 * s["energy_flows_pJ"][1]
    assert set(record["amounts_fmol"]) == {defs.CELL, defs.BATH, defs.LUMEN}
    assert all(len(v) == 2 for node in record["amounts_fmol"].values() for v in node.values())
    stage = record["stage"]
    assert 0 <= stage["envelope_max_lag_ph"] <= 1e-3 and stage["envelope_stages_beyond"] == 0
    assert stage["cytosol_pH_min"] <= 7.2 + 1e-9 and stage["cytosol_pH_max"] >= 7.2 - 1e-9
    assert record["ledgers"]["charge_residual_C"] <= record["ledgers"]["charge_tolerance_C"]


def test_k3_is_refused_at_the_definition_through_the_envelope():
    """The lead's ruling on K3: the lumen buffer's k_on at 1e-3 /mM/s is refused at the definition,
    and the refusal is attributed to the envelope (the same world is admitted with B4's stage check
    removed); a refusal for another reason is not."""
    from dataclasses import replace

    from validation.compartment_ph_engine import engine_records
    from validation.compartment_ph_engine.parameters import World

    w = World()
    k3 = replace(w, lumen_buffer=replace(w.lumen_buffer, k_on_per_mM_s=1e-3))
    record = engine_records.run(short(defs.fr4_world(k3)))
    assert not record["admitted"] and record["refusal_reason"] == "envelope"
    assert "domain invalid" in record["refusal"]
    other = defs.fr4_world()
    other["model"]["transporters"][0]["capacity_fmol_s"] = -1.0
    record = engine_records.run(short(other))
    assert not record["admitted"] and record["refusal_reason"] is None


def test_k2s_planted_slope_follows_the_patch_voltage_in_its_exchanged_frame():
    """Item 7 (core-d172 5b1b931e): K2's planted law reads the stage's potentials in its own frame
    (the two sides exchanged, the patch voltage negated), so its slope is e^a times its value at
    its static head, a = n F (V - V_head) / RT with V_head the head in the patch's frame (about
    +0.266 V at the start, where h_c = h_L): past it the reversed pump counts its e^a. Called bare
    it is the head's. No run: the hook at the development world's start."""
    import math

    import numpy as np

    from cells.definitions.surface_pump_v3_spec import control_values
    from cells.kinds import proton_buffer, transporter
    from cells.laws.electrochemistry import F, R
    from cells.models import surface_pump_v3
    from cells.registry import kind_registry
    from validation.compartment_ph_engine import planted

    kind = planted.reversed_pump()
    with kind_registry.scope(planted.registry(kind)):
        spec = parse_spec(defs.development_world(defs.fr4_world()))
        structure = surface_pump_v3.structure(spec.model)
        state, p = surface_pump_v3.initial_values(spec, structure=structure)
        controls = control_values(spec, [0.0])
        control = type(controls)(*(v[0] for v in controls))
        read, ok = proton_buffer.stage_read(state, p, xp=np)
    assert bool(ok)
    b = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
    n = p.active.size  # stage_term is per node: cells, then outside nodes.
    cell, lumen = int(p.membrane_cell[b]), n + int(p.membrane_outside[b])
    c_in, c_out, fuel = transporter.gather(read, p, xp=np)
    i, q = transporter.proton_law(c_out, c_in, np.zeros_like(c_in), fuel, p, xp=np)
    head = -float(transporter.static_head_V(i, q, xp=np)[b])  # The patch's frame.
    bare_nodes = kind.stage_term(read, None, control, p, xp=np)
    bare = float(bare_nodes[:n][cell])
    assert float(bare_nodes[lumen]) == bare  # The patch's both ends.

    def potentials(voltage):  # The bounding patch's cell at V; the lumen and the bath at 0.
        out = np.zeros(p.active.size + p.outside_active.size)
        out[cell] = voltage
        return out

    a_unit = 2 * F / (R * spec.model.temperature_K)
    for shift in (-0.05, 0.0, 0.02, 0.05):
        term = float(kind.stage_term(read, potentials(head + shift), control, p, xp=np)[:n][cell])
        assert term == pytest.approx(bare * math.exp(a_unit * shift), rel=1e-9), shift
    assert 0.25 < head < 0.3  # FR-4's drive near -51 kJ/mol, n = 2, h_c = h_L at the start.


def test_a_pump_past_its_head_is_refused_at_the_face_free_lumens_row():
    """Item 7 per node (core-d172 2c780f9f): the pump's slope goes to both of its patch's ends, so
    B7's per-stage refusal holds FR-4's face-free lumen, whose node carries the bounding patch's
    capacitance alone, as well as the cell, which carries the plasma patch's too. Driven past its
    static head until dt G / C_b = 1.5 at the declared 1 ms, the stage is refused at the lumen's
    row, where the same slope counted at the cell only passes: it relaxes the lumen patch's voltage
    and not the cell's (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §8.3), so no row holds it there,
    and what is left is the lumen patch's row of the K+ route and the leak. No run: membrane_rate
    at the development world's start, at potentials past the head."""
    import dataclasses
    import math

    import numpy as np

    from cells.definitions.surface_pump_v3_spec import control_values
    from cells.kinds import proton_buffer, transporter
    from cells.laws.electrochemistry import F, R
    from cells.models import surface_pump_v3
    from cells.registry import kind_registry
    from validation.compartment_ph_engine import planted

    spec = parse_spec(defs.development_world(defs.fr4_world()))
    structure = surface_pump_v3.structure(spec.model)
    state, p = surface_pump_v3.initial_values(spec, structure=structure)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    read, ok = proton_buffer.stage_read(state, p, xp=np)
    assert bool(ok)
    dt, bound = spec.execution.dt, surface_pump_v3.EXPLICIT_STEP_BOUND
    patches = [m.id for m in spec.model.membranes]
    b = patches.index(defs.BOUNDING)
    n, j = p.active.size, int(p.membrane_outside[b])
    cell, lumen = int(p.membrane_cell[b]), n + j
    assert bool(surface_pump_v3.free_outside_nodes(p, xp=np)[j])  # The lumen is face-free.
    c_b = spec.model.membranes[b].capacitance_F
    c_cell = sum(m.capacitance_F for m in spec.model.membranes if m.inside == defs.CELL)
    assert c_cell > 2 * c_b  # The plasma patch's capacitance is the cell's too.

    c_in, c_out, fuel = transporter.gather(read, p, xp=np)
    i, q = transporter.proton_law(c_in, c_out, np.zeros_like(c_in), fuel, p, xp=np)
    head = float(transporter.static_head_V(i, q, xp=np)[b])
    bare = float(transporter.stage_term(read, None, control, p, xp=np)[:n][cell])
    target = 1.5 * bound * c_b / dt  # The pump's slope that the lumen's row cannot hold.
    voltage = head - math.log(target / bare) * R * spec.model.temperature_K / (2 * F)
    potentials = np.zeros(n + p.outside_active.size)
    potentials[cell] = voltage  # The bounding patch at V, past the head; the lumen at 0.
    nodes = transporter.stage_term(read, potentials, control, p, xp=np)
    assert float(nodes[:n][cell]) == pytest.approx(target, rel=1e-9)
    assert float(nodes[lumen]) == float(nodes[:n][cell])

    def rate():
        return float(
            surface_pump_v3.membrane_rate(
                state, control, p, xp=np, structure=structure, potentials=potentials
            )
        )

    per_node = rate()
    assert dt * per_node > bound  # Refused, at the lumen's row:
    assert dt * per_node == pytest.approx(1.5, abs=0.05)  # target / C_b, with the K+ route's.

    def cells_only(read, potentials, control, p, *, xp):  # The same slope at the cell alone.
        nodes = transporter.stage_term(read, potentials, control, p, xp=xp)
        return xp.where(xp.arange(nodes.shape[0]) < p.active.size, nodes, 0.0)

    with kind_registry.scope(
        planted.registry(dataclasses.replace(transporter.TRANSPORTER, stage_term=cells_only))
    ):
        cell_row = rate()
    assert dt * cell_row <= bound  # The slope at the cell alone would pass.
    # F^2/RT P A max(c) of the K+ route and of the leak (at the read's free h), over C_b.
    membrane, k = spec.model.membranes[b], spec.model.species_ids.index("K")
    largest_k = max(
        p.amount_reference[k, cell] / p.volume[cell],
        p.extracellular_amount_reference[k, j] / p.extracellular_volume[j],
    )
    (leak,) = dict(spec.model.kinds)["cells.kind.passive_routes@1"]
    permeance = membrane.permeability_m_per_s[k] * largest_k
    permeance += leak.permeability * max(float(c_in[b]), float(c_out[b]))
    slope = F * F / (R * spec.model.temperature_K) * membrane.area_m2 * permeance
    assert cell_row == pytest.approx(slope / c_b, rel=1e-9, abs=0)
