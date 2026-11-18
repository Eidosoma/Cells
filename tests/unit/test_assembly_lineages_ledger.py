"""The stochastic thermodynamic ledger (GARD_DESIGN §2.4): it closes against k_BT ln pi at every
saved row for a passive law, and reports the unsourced cycle work for the driven one.

Planted errors it must catch:
- a heat sign error: the same run with its heat booking negated fails the closure;
- a work booking with the wrong sign: likewise;
and the runner refuses a passive law's run whose ledger does not close.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import GARD_PAIR_CONSISTENT, GARD_SINGLE_EVENT, ledger, runner
from tests.assembly_lineage_fixtures import definition, world


def _closes(rows, phi=None):
    phi = rows["log_weight"][:, 0] if phi is None else phi
    heat = rows["exchange_heat_kT"][:, 0]
    work = rows["fission_work_kT"][:, 0]
    sink = rows["discarded_free_energy_kT"][:, 0]
    residual = ledger.residual(heat, phi, phi[0], work, sink)
    scale = np.cumsum(np.abs(np.diff(heat, prepend=0.0))) + np.abs(phi) + abs(phi[0])
    scale += np.cumsum(np.abs(np.diff(work, prepend=0.0))) + np.cumsum(
        np.abs(np.diff(sink, prepend=0.0))
    )
    return bool(np.all(np.abs(residual) <= ledger.RTOL * np.maximum(scale, 1.0)))


@pytest.fixture(scope="module")
def runs():
    the_world = world(seed=8)
    return {
        law: runner.run(parse_spec(definition(the_world, law, fissions=8)))
        for law in (GARD_PAIR_CONSISTENT, GARD_SINGLE_EVENT)
    }


def _event_heats(run):
    """Each event's heat from the trace, by the exchange law's affinity (a passive law's heat):
    a join of i at n books ln theta_i + ln N - ln(n_i + 1); a leave books minus that of its
    reverse join."""
    world = run.spec.model.world
    theta = np.log(np.asarray(world.types.transfer_constant) * np.asarray(world.supply))
    daughters = iter(run.rows["assembly_count"][run.rows["row_kind"] == 2, :, 0])
    counts = np.asarray(world.founder, dtype=np.int64).copy()
    channels = iter(run.trace["event_channel"])
    heats = []
    for growth in run.trace["events_per_growth"]:
        for _ in range(growth):
            c = int(next(channels))
            i, size = abs(c) - 1, int(counts.sum())
            if c > 0:
                heats.append(theta[i] + np.log(size) - np.log(counts[i] + 1.0))
                counts[i] += 1
            else:
                counts[i] -= 1
                rest = size - 1
                heats.append(
                    -theta[i] if rest == 0 else -(theta[i] + np.log(rest) - np.log(counts[i] + 1.0))
                )
        counts = next(daughters, counts).copy()
    return np.asarray(heats)


def test_the_passive_ledger_closes_at_every_row(runs):
    run = runs[GARD_PAIR_CONSISTENT].check()
    assert run.closure["checked"] and run.closure["holds"] and _closes(run.rows)
    heats = _event_heats(run)
    assert np.any(heats < 0)  # Non-monotone, as declared: single events go uphill.
    parents = run.rows["row_kind"] == 1
    booked = np.cumsum(heats)[np.cumsum(run.trace["events_per_growth"])[: parents.sum()] - 1]
    assert np.allclose(booked, run.rows["exchange_heat_kT"][parents, 0], rtol=1e-12, atol=1e-12)
    planted = dict(run.rows, exchange_heat_kT=-run.rows["exchange_heat_kT"])
    assert not _closes(planted)
    planted = dict(run.rows, fission_work_kT=-run.rows["fission_work_kT"])
    assert not _closes(planted)


def test_the_driven_form_reports_its_cycle_work(runs):
    run = runs[GARD_SINGLE_EVENT].check()  # Driven: reported, never refused.
    assert not run.closure["checked"] and not run.closure["holds"]
    assert run.closure["max_abs_residual_kT"] > 1e-3 and run.status == "complete"


def test_the_extinct_end_closes_with_the_empty_convention():
    """A lineage that loses its last molecule: its last heat is -ln theta_i (Phi(empty) = 0)."""
    data = definition(
        world(seed=2, founder_size=1, transfer_constant=0.05), GARD_PAIR_CONSISTENT, fissions=3
    )
    run = runner.run(parse_spec(data)).check()
    assert run.status == "extinct" and run.rows["row_kind"][-1] == 3
    assert run.rows["assembly_count"][-1].sum() == 0 and run.closure["holds"]


def test_a_passive_run_that_does_not_close_is_refused(monkeypatch, runs):
    run = runs[GARD_PAIR_CONSISTENT]
    monkeypatch.setattr(ledger, "RTOL", -1.0)  # No residual can meet a negative bound.
    refused = runner._assemble(
        run.spec,
        run.structure,
        run.verdict,
        None,
        "complete",
        [dict(r) for r in _rows_of(run)],
        [],
        [],
        [],
        (np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)),
        run.qualifier,
        "fresh",
        {},
        {},
    )
    assert refused.status == "refused"
    with pytest.raises(runner.LedgerRefused):
        refused.check()


def _rows_of(run):
    """The runner's row dicts back from a run's arrays (enough for _assemble)."""
    rows = run.rows
    count = run.spec.model.world.types.count
    out = []
    for r in range(len(rows["row_time"])):
        out.append(
            {
                "time": rows["row_time"][r],
                "events": rows["row_event"][r],
                "age": 0,
                "counts": rows["assembly_count"][r, :count, 0],
                "size": rows["assembly_count"][r, :count, 0].sum(),
                "joined": rows["joined_total"][r, :count, 0],
                "left": rows["left_total"][r, :count, 0],
                "discarded": rows["discarded_total"][r, :count, 0],
                "heat": rows["exchange_heat_kT"][r, 0],
                "heat_magnitude": 0.0,
                "work": rows["fission_work_kT"][r, 0],
                "work_magnitude": 0.0,
                "sink": rows["discarded_free_energy_kT"][r, 0],
                "sink_magnitude": 0.0,
                "occupant": rows["occupant"][r, 0],
                "generation": rows["generation"][r, 0],
                "fissions": 0,
                "status": 0,
                "kind": int(rows["row_kind"][r]),
                "fission": int(rows["row_fission"][r]),
            }
        )
    return out
