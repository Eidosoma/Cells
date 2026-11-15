"""FR-4's world through the engine (validation/compartment_ph/definitions.py; the note's §13.1).

The development world (the declared world without FR-1's compartment operator, the lead's ruling) at
the declared 1 ms, for a few steps from its pH 7.2 start, with the built-in kinds on BUILTIN: B4's
closure, the proton pump and the proton leak, beside the K+ route.
- every accepted row passes all ten ledgers (energy with B4's stored term, the pump's heat and the
  maintenance's work, the leak's and the K+ route's heat);
- the pump moves 2 H_eq per cycle from the cytosol into the lumen and the leak returns some, so the
  lumen's H_eq changes by exactly their difference, and the lumen acidifies;
- the held fuel never changes.
"""

import copy

import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.registry import get_model
from validation.compartment_ph import definitions as defs

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
        "cells.passive_routes@1",
        "cells.rapid_proton_buffer@1",
        "cells.transporter@1",
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
    """validation/compartment_ph/engine_records.run, the generator's engine path: every
    ENGINE_READOUTS series of FR-4 at each record, the energy identity from the engine's ledger,
    every row at every node, B4's running extrema and the charge ledger within its tolerance."""
    from validation.compartment_ph import engine_records

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

    from validation.compartment_ph import engine_records
    from validation.compartment_ph.parameters import World

    w = World()
    k3 = replace(w, lumen_buffer=replace(w.lumen_buffer, k_on_per_mM_s=1e-3))
    record = engine_records.run(short(defs.fr4_world(k3)))
    assert not record["admitted"] and record["refusal_reason"] == "envelope"
    assert "domain invalid" in record["refusal"]
    other = defs.fr4_world()
    other["model"]["transporters"][0]["capacity_fmol_s"] = -1.0
    record = engine_records.run(short(other))
    assert not record["admitted"] and record["refusal_reason"] is None
