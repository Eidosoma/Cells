"""B3, a compiled run of cells.operator.scheduled_bath_composition@1 (FR-10; docs/BATH_SCHEDULE_DESIGN.md §4).

The ledgers across an event. The species-only dose leg (validation/tissue/bath_schedule_fixtures)
under RK4 at 0.1 ms, whose energy bound is the absolute 2e-8 pJ, from a resolved profile, with the
bath's S stepped from 1e-3 to 1.5e-3 mM at step 20 (a step between resolved levels). Every host
check passes on every row through the runner, so the energy ledger stays within its bound before,
at and after the event, and the reservoir-work ledger closes with the operator's term. **The control
drops the term:** @3's own reservoir-work ledger, which reads the declared potential, then fails its
bound from the first row after the event. One RK4 compile: not tier 1 (idleness, B5, is
test_bath_schedule_idle.py).
"""

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.models.surface_pump import ENERGY_RTOL
from cells.registry.models import get_model
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx

DT_RK4, STEPS, EVENT_STEP = 1e-4, 60, 20


def b3_world():
    end = STEPS * DT_RK4
    raw = bfx.dosed_world(
        dt=DT_RK4, end=end, solver="rk4", observation_times=fx.grid_times(end, DT_RK4, DT_RK4)
    )
    timeline = [(EVENT_STEP * DT_RK4, ["bath"], {"cargo": 5e-4})]
    return bfx.with_bath_schedule(raw, ["bath"], bfx.CARGO, timeline)


def rows_of(result):
    model = get_model(result.spec.model)
    history = result.history
    return model, [
        model.STATE_TYPE(*(np.asarray(v)[i] for v in history)) for i in range(len(result.times))
    ]


def test_b3_the_ledgers_close_across_an_event_and_fail_without_the_term():
    result = run(parse_spec(b3_world()))  # Every host check, on every accepted row.
    model, rows = rows_of(result)
    _, p = model.initial_values(result.spec)
    spec = result.spec
    j = [c.id for c in spec.model.extracellular].index("bath")
    steps = np.rint(np.asarray(result.times) / DT_RK4).astype(int)
    tol = np.asarray(spec.execution.material_balance_atol_fmol)
    names = list(model.inner.LEDGERS)
    energy_ratio, failing_without = [], []
    for row, k in zip(rows, steps, strict=True):
        magnitudes = model.magnitudes(row, p)
        _, bounds = model.ledger_limits(
            row, p, tol, ENERGY_RTOL["rk4"], steps=k, magnitudes=magnitudes
        )
        energy = model.balances(row, p)["energy"]
        energy_ratio.append(abs(float(energy)) / float(bounds[names.index("energy")]))
        own = model.inner.balances(model.inner.inner_state(row), model.inner.inner_layout(p))
        limit = np.asarray(bounds[names.index("reservoir_work")])[j]
        failing_without.append(abs(float(own["reservoir_work"][j])) > float(limit))
    assert max(energy_ratio) < 1.0  # Within the absolute 2e-8 pJ across the event.
    before = [f for f, k in zip(failing_without, steps, strict=True) if k <= EVENT_STEP]
    after = [f for f, k in zip(failing_without, steps, strict=True) if k > EVENT_STEP]
    assert not any(before)  # Before the event the declared potential is the one in force.
    assert all(after)  # Without the operator's term the ledger fails from the first row after.
    final = rows[-1]
    held = np.asarray(final.bath_held_amount_fmol)[:, j]
    s = list(spec.model.species_ids).index(fx.SPECIES)
    assert held[s] == np.asarray(p.extracellular_amount_reference)[s, j] + 5e-4 * 1.0
