"""FR-4's K2 through the engine: the self-consistent reversed pump (the lead's ruling (b)) over the
development world's first steps, with every ledger closing, and guard (a), the moves flipped alone,
refused by the material ledger.

Split from test_fr4_world_engine.py for the tiers (the lead's ruling, 15 November 2026): this run
takes about a minute, so the fast tests there join the gate without it; the tier record places
each file. The helpers stay there.
"""

import pytest

from tests.unit.test_fr4_world_engine import short
from validation.compartment_ph import definitions as defs


def test_k2_the_reversed_pump_closes_every_ledger_and_alkalinizes_the_lumen():
    """K2 = (b) (the lead's ruling): the self-consistent reversed pump runs with every ledger
    closing, so only J4 can catch it, and it moves the lumen's pH the wrong way; the pump's moves
    flipped alone (guard (a)) are refused by the engine's material ledger."""
    import dataclasses

    from cells.models.inner_kinds import transporter
    from validation.compartment_ph import engine_records, planted

    record = engine_records.run(
        short(defs.fr4_world()), registry=planted.registry(planted.reversed_pump())
    )
    assert record["completed"], record["refusal"]
    s = record["series"]
    assert s["cycles"][1] > 0 and s["moved_H_pump"][1] < 0  # n H+ from the lumen per cycle.
    assert s["pH_L"][1] > s["pH_L"][0] == pytest.approx(7.2, abs=1e-9)
    assert s["Heq_L"][1] - s["Heq_L"][0] == pytest.approx(
        s["moved_H_pump"][1] + s["moved_H_leak"][1], rel=1e-9
    )
    assert 0 < s["heat_pump_pJ"][1] < s["work_pJ"][1]
    assert abs(s["energy_residual_pJ"][1]) <= 2e-3 * s["energy_flows_pJ"][1]

    def flipped(state, potentials, control, p, *, xp):
        r = transporter.rates(state, potentials, control, p, xp=xp)
        return r._replace(cell=-r.cell, outside=-r.outside)

    guard = dataclasses.replace(transporter.TRANSPORTER, rates=flipped)
    record = engine_records.run(short(defs.fr4_world()), registry=planted.registry(guard))
    assert record["admitted"] and not record["completed"]
    assert "accounting failed: local" in record["refusal"]
