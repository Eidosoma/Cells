"""FR-43 part 2A (D315): one pool, two writers at fixed volume, the runs.

The gene unit beside a D152 network on its listed row N (validation/tissue/shared_inventory_fixtures
.pair), through the runner with every host check on every accepted row, 20 steps of 0.5 s:
- C2.2: N's amount at every saved row is its start plus each writer's own books (produced minus
  consumed), to the rounding of that many accumulations; both writers move N; a copy of the records
  with one writer's consumption 1e-3 high fails the check;
- C2.4: either writer at zero rate gives the other alone, bitwise, on every field both runs hold.
The definition's refusals are test_shared_inventory_writers.py's. Its reason and cost: five
compiled worlds of the gene unit, the composition FR-43 admits (seconds as the tier tool measures).
"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.models import get_model
from validation.tissue import shared_inventory_fixtures as sif

END = 10.0  # 20 steps of the gene world's 0.5 s.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def amounts(spec, result, name):
    """[T] fmol of `name` in the cell: its anchor plus its increments."""
    _, p = get_model(spec.model).initial_values(spec)
    row = list(spec.model.species_ids).index(name)
    return (
        np.asarray(p.amount_reference)[row, 0]
        + np.asarray(result.history.amount_increment)[:, row, 0]
    )


def books(history, row):
    """Each writer's own net books of species `row` in the cell, [T] fmol: (gene unit, network)."""
    gene = (
        np.asarray(history.poly_produced_fmol)[:, row, 0]
        - np.asarray(history.poly_consumed_fmol)[:, row, 0]
    )
    network = (
        np.asarray(history.reaction_produced_fmol)[:, row, 0]
        - np.asarray(history.reaction_consumed_fmol)[:, row, 0]
    )
    return gene, network


def books_error(spec, history, n):
    row = list(spec.model.species_ids).index("N")
    gene, network = books(history, row)
    return float(np.max(np.abs((n - n[0]) - (gene + network))))


def test_each_writer_books_its_own_moves_of_the_shared_row():
    """C2.2: n_N(t) = n_N(0) + each writer's produced minus consumed at every saved row, to the
    rounding of that many accumulations at the books' scale (64 eps per row); both writers move N
    (the runner's material ledger closes their sum on every row); a 1e-3 error in one writer's
    books fails the check."""
    spec = parse_spec(sif.pair("sink", end=END))
    result = run(spec)  # Every host check on every accepted row.
    n = amounts(spec, result, "N")
    row = list(spec.model.species_ids).index("N")
    gene, network = books(result.history, row)
    assert float(np.max(np.abs(gene))) > 0 and float(np.max(np.abs(network))) > 0
    scale = float(np.max(np.abs(n)) + np.max(np.abs(gene)) + np.max(np.abs(network)))
    tolerance = 64 * np.finfo(float).eps * len(n) * scale
    assert books_error(spec, result.history, n) <= tolerance
    planted = result.history._replace(
        reaction_consumed_fmol=np.asarray(result.history.reaction_consumed_fmol) * (1 + 1e-3)
    )
    assert books_error(spec, planted, n) > tolerance


IDLE = [
    ("network idle", lambda: sif.pair("sink", end=END, network_multiplier=0.0),
     lambda: sif.gene_alone("sink", end=END)),
    ("gene idle", lambda: sif.pair("sink", end=END, gene_rates=0.0),
     lambda: sif.network_alone("sink", end=END)),
]  # fmt: skip


@pytest.mark.parametrize(("case", "idle", "alone"), IDLE, ids=[c for c, _, _ in IDLE])
def test_either_writer_idle_gives_the_other_alone_bitwise(case, idle, alone):
    """C2.4: D152's claim 2 and the gene unit's zero rates both select the start state, so the
    pair with one writer idle is the other writer alone, bit for bit, on every shared field."""
    a, b = run(parse_spec(idle())), run(parse_spec(alone()))
    assert np.asarray(a.times).tobytes() == np.asarray(b.times).tobytes()
    shared = sorted(set(a.history._fields) & set(b.history._fields))
    assert shared
    differ = [
        k
        for k in shared
        if np.asarray(getattr(a.history, k)).tobytes()
        != np.asarray(getattr(b.history, k)).tobytes()
    ]
    assert not differ, (case, differ)
