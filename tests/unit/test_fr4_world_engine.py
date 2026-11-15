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
