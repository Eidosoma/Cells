"""FR-5's start part (the FR-4/FR-5 note's §16.6): FR-4's world run with a checkpoint gives the
engine's snapshot of its final state and FR-5's start extract from its last record.

A few steps of the development world on the host path (compile-dominated): the snapshot restores
the run's final state; the extract's amounts are the last record's and its charges the engine's own
node charges; check_start admits it; FR-5's world built from it takes those amounts and charges and
holds parse_spec's keys only (its identity is the part's record's). The full start (1800 s) is the
generator's `start` part (validation/tissue/compartment_ph_qualification.fr5_start).
"""

import math
from dataclasses import replace

import numpy as np

from cells.io import load_snapshot
from tests.unit.test_fr4_world_engine import short
from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import engine_records
from validation.compartment_ph_engine.parameters import ARM_R, CHARGE_PER_FMOL

STEPS = 5


def test_a_checkpointed_run_gives_the_snapshot_and_fr5s_start(tmp_path):
    definition = short(defs.fr4_world(), STEPS)
    record = engine_records.run(definition, checkpoint_dir=tmp_path / "snapshot")
    assert record["completed"] and record["steps"] == STEPS
    end = record["record_s"][-1]
    nodes, readouts = record["start_nodes"], record["start_readouts"]
    assert set(nodes) == {defs.CELL, defs.BATH, defs.LUMEN}
    for node, taken in nodes.items():  # The last record's amounts, every FR-4 row.
        assert taken["amounts_fmol"] == {s: record["amounts_fmol"][node][s][-1]
                                         for s, _ in defs.SPECIES}
    assert readouts == dict(pH_c=record["series"]["pH_c"][-1], pH_L=record["series"]["pH_L"][-1],
                            V_b_V=record["series"]["V_b"][-1])
    # The snapshot is the run's final state: its amounts are the extract's.
    snap = load_snapshot(tmp_path / "snapshot")
    assert snap.checkpoint.time == end and snap.checkpoint.step_index == STEPS
    state, layout = snap.checkpoint.state, snap.checkpoint.layout
    lumen = [o["id"] for o in definition["model"]["extracellular"]].index(defs.LUMEN)
    h = [s for s, _ in defs.SPECIES].index("H")
    assert float(layout.extracellular_amount_reference[h, lumen]
                 + state.extracellular_amount_increment[h, lumen]) == nodes[defs.LUMEN][
        "amounts_fmol"]["H"]
    # The pump charged the patch: the lumen and the cytosol carry opposite net charges.
    assert nodes[defs.LUMEN]["charge_C"] > 0 > nodes[defs.CELL]["charge_C"]
    extract = defs.start_extract(producer="engine", nodes=nodes, readouts=readouts, time_s=end,
                                 dt_s=definition["execution"]["dt"], source=dict(kind="test"),
                                 engine_snapshot=str(tmp_path / "snapshot"))
    defs.check_start(extract)
    # FR-5's world from it, its checkpoint time moved to the short run's end.
    built = defs.fr5_world(replace(ARM_R, start_checkpoint_s=end), start=extract)
    assert set(built) == {"schema_version", "model", "experiment", "execution"}
    z = dict(defs.SPECIES)
    for node in built["model"]["cells"] + built["model"]["extracellular"]:
        taken = nodes[node["id"]]
        assert all(node["initial_amount_fmol"][s] == v for s, v in taken["amounts_fmol"].items())
        assert node["initial_charge_C"] == taken["charge_C"]
        net = node["fixed_charge_equivalent_fmol"] + math.fsum(
            z.get(s, 0) * n for s, n in node["initial_amount_fmol"].items())
        assert np.isclose(net * CHARGE_PER_FMOL, taken["charge_C"], rtol=1e-9, atol=1e-24)
