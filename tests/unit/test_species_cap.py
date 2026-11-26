"""The species cap at 1,024 (FR-43 / D315; FR-9 / D165 raised it from 7 to 16), and the sum order a
world above the old cap of 7 exercises.

On tests/species_cap_fixtures.py's 9-species world (the W4 probe's cell_charged_9 rebuilt: one
heredity cell, four mobile charged species and D150's S; a single cell column, seven moving
charged rows below slot 8):
1. the cap, now 1,024, admits it (above the old caps of 7 and 16);
2. on its own layout the host's species-axis sum (surface_tissue.charge_increment, NumPy's
   pairwise order for a single column of 8 or more species) differs from the explicit
   species-order sum that every ledger uses (capacitor_change) for seeded increments in the
   charged rows, while the explicit host sum equals the compiled one bitwise. The order the old
   cap guarded against is real, and the ledgers do not depend on it.
The world run through the runner with every host check on every accepted row is
test_species_cap_runs.py, in tier 2: the run takes about 15 s whatever its length (14.7 to 17.3 s
for 5, 10, 20 and 40 steps, nearly all of it compilation), and that file 21 s, above tier 1's 20 s.
The cap's refusal and its reason are tested here on the cap's own check (a 1,025-species world's
parse is test_species_cap_large.py's, tier 3, beside the 1,024-row run); each operator's call to it
is tested in test_secreted_species.py and test_species_reactions_refusals.py, with the cap set to 16
for the test, so their worlds stay small.
"""

from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution import batch, batch_windows, resources, windows
from cells.execution.runner import _trace_budget
from cells.execution.state import initialise
from cells.models import pump_composite as pc
from cells.models import surface_tissue as tissue
from cells.operators import species_common
from tests.species_cap_fixtures import chain_world, charged_nine


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def world():
    return parse_spec(charged_nine(steps=20))


def test_the_cap_is_1024_and_admits_the_nine_species_world(world):
    assert species_common.MAX_SPECIES == 1024
    assert list(world.model.species_ids)[4:8] == ["Q1", "Q2", "Q3", "Q4"]
    assert len(world.model.species_ids) == 9


def test_the_cap_refuses_1025_species_with_the_reason_and_admits_1024():
    """The cap's check reads only the world's species count (every species, ions included)."""

    def spec(count):
        return SimpleNamespace(
            model=SimpleNamespace(species_ids=tuple(f"X{i}" for i in range(count)))
        )

    species_common.check_species_cap(spec(1024), "a_law@1")  # 1,024 are admitted.
    with pytest.raises(ConfigError, match="a_law@1 admits at most 1024 species per world") as error:
        species_common.check_species_cap(spec(1025), "a_law@1")
    reason = str(error.value)
    assert "this world declares 1025" in reason and "ions included" in reason
    assert "explicit species order (D148)" in reason
    assert "another probe (FR-43 / D315)" in reason


def test_the_trace_estimate_counts_the_network_layout_once():
    """FR-43 / D315: the reactions' bound layout (the dense [species rows, route] arrays) is counted
    once per resident copy, and the saved rows per time point. The 256-species chain at 400 steps of
    5 ms is admitted under the fixtures' 2 GiB budget (its measured peak: 1.1 GiB); the layout
    counted on every saved row, as before, would alone exceed it (that estimate was 9.5 GiB)."""
    spec = parse_spec(chain_world(256, dt=0.005, end=2.0))
    steps = 400
    fixed = resources.fixed_bytes(spec)
    assert resources.trace_bytes(spec, steps) == fixed + resources.row_bytes(spec, steps)
    assert resources.trace_bytes(spec, 0) - resources.row_bytes(spec, 0) == fixed  # Once a copy.
    _trace_budget(spec, steps)  # The runner's admission: no refusal.
    assert fixed * (steps + 1) > spec.execution.max_trace_bytes


def test_the_windowed_and_batch_estimates_count_a_layout_once_per_world(monkeypatch):
    """FR-43 / D315: where a path holds several copies of a world's rows (two adjacent results,
    two checkpoints), each copy's rows are counted and its layout once: the estimate grows by
    exactly one fixed_bytes per world, whatever it is."""
    raw = chain_world(32, dt=0.005, end=2.0, every=0.25)
    spec = parse_spec(raw)
    two = batch.parse_batch(
        dict(
            schema_version=1,
            kind="independent_worlds",
            worlds=[dict(world_id=i, simulation=raw) for i in (1, 2)],
            execution=dict(
                mapping="lax_map", max_worlds=4, max_padded_steps=10**6, max_working_bytes=2**31
            ),
        )
    )
    policy = windows.WindowPolicy(256)

    def estimates(value):
        for module in (windows, batch, batch_windows):
            monkeypatch.setattr(module, "fixed_bytes", lambda spec, value=value: value)
        return (
            windows.plan_windows(spec, policy).estimated_working_bytes,
            batch.plan_batch(two).estimated_working_bytes,
            batch_windows.plan_batch_windows(two, policy).estimated_working_bytes,
        )

    none, some = estimates(0), estimates(1000)
    assert [b - a for a, b in zip(none, some, strict=True)] == [1000, 2000, 2000]


def test_the_host_sum_order_differs_while_the_ledgers_explicit_sum_is_the_compiled_one(world):
    model = pc.model_for(world.model)
    _, parameters = model.initial_values(world)
    layout = model.inner.inner_layout(parameters)
    inner = model.inner_state(initialise(world).state)
    charged = (np.asarray(layout.valence).reshape(-1) != 0)[:, None]
    cells = layout.active.size
    assert cells == 1  # A single column: NumPy's pairwise case.
    compiled = jax.jit(lambda s: tissue.capacitor_change(s, layout, xp=jnp)[0])
    rng = np.random.default_rng(20261114)
    differs = 0
    for _ in range(20):
        shape_cells = np.shape(inner.amount_increment)
        shape_outside = np.shape(inner.extracellular_amount_increment)
        state = inner._replace(
            amount_increment=np.where(charged, rng.normal(scale=1e-4, size=shape_cells), 0.0),
            extracellular_amount_increment=np.where(
                charged, rng.normal(scale=1e-4, size=shape_outside), 0.0
            ),
        )
        host = np.asarray(tissue.charge_increment(state, layout, xp=np))
        explicit = np.asarray(tissue.capacitor_change(state, layout, xp=np)[0])
        differs += int(not np.array_equal(host[:cells], explicit[:cells]))
        np.testing.assert_array_equal(explicit, np.asarray(compiled(state)))
    assert differs > 0, "the host's order never differed: the guard did not reach the cap's reason"
