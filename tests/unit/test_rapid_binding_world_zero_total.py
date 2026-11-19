"""A held total driven through zero (the lead's ruling 3, 19 November 2026).

The world is the general closure on B4's buffered cell, plus a neutral ligand L on its own binder C
at the cell, so that draining L moves no charge. An H+ drain this fast would move enough charge in
one step to fail the field's domain first. The planted reading carrier takes L out of the cell at
a constant rate that takes L's stored total through zero at 60% of the run, inside the third step.
- The envelope refuses first. As the free L runs out, the network's lag behind the drain passes
  its 1e-3 pX budget while the read is still valid: here between 40% and 30% of L's total left,
  shown at the host level at the drain's transport. In a run it refuses the first stage it sees
  past that point, a step before the crossing at the world's step.
- With the envelope lifted (a planted copy of the kind without its stage_check), the run reaches
  the crossing, and the engine refuses that step: at its end state the read is invalid and
  domain_valid fails, so no invalid step is accepted. The message names the crossing step, so the
  two before it were accepted.
- The exact-zero case, at the host level: with L's stored total exactly 0, the read is invalid,
  domain_valid is False and the closure's term is NaN, so the ledger would refuse too.
No shipped law moves a closure row (§5.2's proxy admits none), so no admitted world reaches these
cases today; this is the engine's answer when one does.

Split from test_rapid_binding_world.py for the tiers, beside the other run files; the carrier,
its test-namespace law and the world's helpers stay there.
"""

from dataclasses import replace

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import proton_buffer
from cells.registry import kind_registry, laws
from tests import kind_fixtures
from tests.unit.test_proton_buffer_kind import buffered_world, host
from tests.unit.test_rapid_binding_world import amounts, general, reading_carrier, reads_law


def neutral_world():
    """B4's buffered cell under the general closure, plus a neutral ligand L on its own binder C
    at the cell (the closure holds H on B and L on C); L at 1 mM in the bath, C a trace there."""
    raw = general(buffered_world(quiet=True))
    m = raw["model"]
    m["species"] += [
        dict(id="L", valence=0, standard_mu_RT=0.0),
        dict(id="C", valence=0, standard_mu_RT=0.0,
             forms=[dict(id="LC", counts={"L": 1}, standard_mu_RT=-10.0)]),
    ]  # fmt: skip
    cell, bath = m["cells"][0], m["extracellular"][0]
    for node, l_mM, c_mM in ((cell, 1.0, 1.0), (bath, 1.0, 1e-9)):
        volume = node["volume_pL"]
        node["initial_amount_fmol"] |= dict(L=l_mM * volume, C=c_mM * volume)
    for patch in m["membranes"]:
        patch["permeability_m_per_s"] |= dict(L=0.0, C=0.0)
    raw["execution"]["material_balance_atol_fmol"] |= dict(L=1e-10, C=1e-10)
    read = m[proton_buffer.MODEL_KEY][0]
    read["ligand_rows"] = ["H", "L"]
    read["binders"][cell["id"]] = ["B", "C"]
    read["k_on_per_mM_s"]["C"] = {"L": 1e7}
    return raw


def test_a_held_total_driven_through_zero_is_refused_at_its_crossing_step():
    raw = neutral_world()
    registry = laws.active().extended(reads_law())
    kinds = kind_fixtures.registry(reading_carrier(), proton_buffer.PROTON_BUFFER)
    with kind_registry.scope(kinds), laws.scope(registry):
        start = parse_spec(kind_fixtures.declare_carrier(raw, species="L", rate=0.0))
        impl, state, p, _ = host(start)
    l = list(start.model.species_ids).index("L")
    stored = float(amounts(state, p)[l, 0])
    end, dt = start.experiment.end_time, start.execution.dt
    rate = stored / (0.6 * end)
    assert 2 * dt < 0.6 * end < 3 * dt  # The crossing lies inside the third step.

    def left(fraction):
        """The start state with L's stored total at the cell at `fraction` of its start."""
        increment = np.array(state.amount_increment)
        increment[l, 0] = fraction * stored - float(p.amount_reference[l, 0])
        return state._replace(amount_increment=increment)

    # The envelope at the drain's transport (L out of the cell into the bath), read still valid.
    cell = np.zeros_like(np.asarray(state.amount_increment))
    outside = np.zeros_like(np.asarray(state.extracellular_amount_increment))
    cell[l, 0], outside[l, 0] = -rate, rate
    for fraction, within in ((0.4, True), (0.3, False)):
        read, ok = proton_buffer.stage_read(left(fraction), p, xp=np)
        assert bool(ok)
        assert bool(proton_buffer.stage_check(read, cell, outside, p, xp=np)) is within
    # With the envelope lifted, the run reaches the crossing, and the engine refuses that step.
    lifted = replace(proton_buffer.PROTON_BUFFER, stage_check=None)
    with kind_registry.scope(kind_fixtures.registry(reading_carrier(), lifted)), laws.scope(registry):
        drained = parse_spec(kind_fixtures.declare_carrier(raw, species="L", rate=rate))
        step = r"domain failure on \[0\.002\d*, 0\.003\d*\]; no invalid step accepted"
        with pytest.raises(NumericalError, match=step):
            run(drained)
    # The exact-zero case, at the host level: numpy's warnings from the failed solve are silenced,
    # and its outputs asserted.
    zero = left(0.0)
    with kind_registry.scope(kinds), np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        _, ok = proton_buffer.stage_read(zero, p, xp=np)
        valid = impl.domain_valid(zero, p, p.active, xp=np)
        term = proton_buffer.ledger_terms(zero, p, xp=np)["stored_pJ"]
    assert float(amounts(zero, p)[l, 0]) == 0.0
    assert not bool(ok) and not bool(valid)
    assert np.isnan(term[0]) and term[1] == 0.0  # The closure's cell; the bath has no closure.
