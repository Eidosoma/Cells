"""cells.operator.integer_unit_population@1's statistical and coupled checks (FR-43 part 3; D315), registered in
validation/fr43_part3/REGISTRATION.md §3 and §4 before any reference value was seen:

* C3.3: feedback off, constant rates, 16,384 independent sites: the fraction with no active unit
  against the exact two-state P0(t) at ten times, z = 3.89 (Bonferroni, overall alpha 0.001); the
  same world with the assembly rate 10% high must fail; the first 16 sites' traces equal the exact
  kernel's for the same uniforms;
* C3.5: an equal-probability split (f = 1/2 exactly) of one active unit per site, 64 seeds x 128
  sites through the batch runner: exactly one recipient on every draw, the inventories exact, the
  first daughter's frequency in the 99.9% binomial band; the plant at f = 0.55 outside it and in its
  own; and one site with its transfer, whose pools divide by the partition's rule;
* the two-way case: turnover writes the pool the clock reads (the first event at the closed form
  with the supply, far from the one without it), and the integer state switches the flux the node
  pool sees (pure first-order clearance while no unit is active, filling while one is).

Four compiled programs (the many-site world, the dividing batch, the dividing world with its
transfer, the two-way world), each run once or twice: about 3-4 min on one core, nearly all
compiles. They need runs: the statistics need the engine's draws through its own event rule.
"""

import math

import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.numerics import counter_streams as streams
from cells.registry.models import get_model
from validation.fr43_part3 import statistics as st
from validation.fr43_part3 import worlds

W1 = "W1_two_subunits_feedback"
W3 = "W3_two_way_turnover"


def _final_rows(spec, every_step=False):
    end = spec.experiment.end_time
    steps = int(round(end / spec.execution.dt))
    policy = WindowPolicy(steps, "full" if every_step else "observations")
    rows = {}
    for window in iter_windows(spec, policy, None):
        for i, t in enumerate(np.asarray(window.times)):
            rows[round(float(t), 9)] = type(window.history)(
                *(np.asarray(v)[i] for v in window.history)
            )
    return rows


# ------------------------------------------------------------------ C3.3 and C3.5 (§4, §3)


@pytest.fixture(scope="module")
def two_state():
    return {ka: st.two_state_rows(ka) for ka in (st.KA, 1.1 * st.KA)}


def test_feedback_off_matches_the_two_state_solution(two_state):
    checks = st.two_state(two_state[st.KA])
    assert not any(c["miss"] for c in checks), checks


def test_an_assembly_rate_ten_percent_high_fails(two_state):
    assert any(c["miss"] for c in st.two_state(two_state[1.1 * st.KA]))


def test_the_trace_is_the_exact_kernels(two_state):
    """Feedback off and constant rates: t_k = t_{k-1} + E_k / a0, the channel by u2 against the
    partial sums, for the same uniforms (pathwise, to rounding)."""
    worst, mismatches, compared = st.pathwise(two_state[st.KA])
    assert compared > st.PATHWISE_SITES and mismatches == 0
    assert worst <= st.PATHWISE_BOUND_S, worst


@pytest.fixture(scope="module")
def splits():
    return {f: st.splits(f) for f in (0.5, 0.55)}


def test_an_equal_split_gives_one_recipient_per_draw_at_one_half(splits):
    half = splits[0.5]
    assert half["draws"] == st.SEEDS * st.PER_WORLD
    assert half["exactly_one_recipient"] and half["records_exact"]
    assert abs(half["frequency"] - 0.5) <= half["band_at_half"], half


def test_the_plant_at_055_leaves_the_half_band_and_keeps_its_own(splits):
    plant = splits[0.55]
    assert abs(plant["frequency"] - 0.5) > plant["band_at_half"], plant
    assert abs(plant["frequency"] - 0.55) <= plant["band_at_own"], plant


def test_a_dividing_site_with_its_transfer_keeps_every_inventory():
    raw = worlds.divided(
        sites=1, transfer=True, counts={"free": 0, "active": 1}, at=0.2, end=0.4, dt=0.01,
        every=0.01, seed=5,
    )  # fmt: skip
    spec = parse_spec(raw)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    rows = _final_rows(spec, every_step=True)
    s = list(spec.model.species_ids).index(worlds.SPECIES)
    world = worlds.spec_worlds()[W1]
    total = world["initial_amounts_fmol"]["cell"] + world["initial_amounts_fmol"]["node"]
    for t, row in rows.items():
        phase = np.asarray(row.division_applied)[0]
        amounts = np.asarray(p.amount_reference)[s] + row.amount_increment[s]
        cells = amounts[1:] if phase else amounts[:1]  # The parent, or the two daughters.
        node = float(np.asarray(p.extracellular_amount_reference)[s, 1])
        node += float(row.extracellular_amount_increment[s, 1])
        assert abs(cells.sum() + node - total) <= 1e-14 * total, t
        counts = row.integer_counts
        assert int(counts[:, 0].sum() + 2 * counts[:, 1].sum()) == 2, t  # Across the lineage.
        ledgers = model.balances(row, p)
        assert np.all(ledgers["integer_subunits"] == 0.0), t
    last = rows[max(rows)]
    assert last.integer_counts[0].tolist() == [0, 0]  # The parent is retired, its units moved.
    received = last.integer_divided_units[1:, 1]
    assert sorted(received.tolist()) == [0, 1]


# ------------------------------------------------------------------ the two-way case


@pytest.fixture(scope="module")
def two_way():
    spec = parse_spec(worlds.spec_world(W3, dt=0.01, end=6.0, every=0.01, trace=64))
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    return spec, model, p, _final_rows(spec, every_step=True)


def test_turnover_writes_the_pool_the_clock_reads(two_way):
    """Inactive at the start: no transfer, and turnover's supply P raises c, so H(t) = k ff (c0 t
    + P t^2 / (2 V)) and the first event solves H = E0; without the supply it would be E0 / a0."""
    spec, _, _, rows = two_way
    world = worlds.spec_worlds()[W3]  # The references' declared values.
    k = world["channels"][0]["rate_constant_per_s"] * 2  # ff(2, 2) = 2.
    v, n0 = world["volumes_pL"]["cell"], world["initial_amounts_fmol"]["cell"]
    supply = world["turnover"]["production_cell_fmol_per_s"]
    words = jnp.asarray([streams.key_data(world["stream"]["seed"], 0, "events")])
    e0 = -math.log(float(streams.site_uniforms(words, jnp.asarray([0]), 2)[0, 0]))
    a, b = k * supply / (2 * v), k * n0 / v  # H(t) = a t^2 + b t (c in mM = fmol/pL).
    with_supply = (-b + math.sqrt(b * b + 4 * a * e0)) / (2 * a)
    without = e0 / b
    first = rows[max(rows)].integer_trace_time_s[0, 0]
    assert abs(first - with_supply) <= 1e-4  # The splitting's O(dt^2) at 10 ms.
    assert abs(without - with_supply) > 100 * abs(first - with_supply)


def test_the_integer_state_switches_the_flux_the_node_sees(two_way):
    spec, model, p, rows = two_way
    s = list(spec.model.species_ids).index(worlds.SPECIES)
    clearance = worlds.spec_worlds()[W3]["turnover"]["clearance_node_per_s"]
    times = sorted(rows)
    filled = 0
    for a, b in zip(times, times[1:], strict=False):
        ra, rb = rows[a], rows[b]
        na = float(
            np.asarray(p.extracellular_amount_reference)[s, 1]
            + ra.extracellular_amount_increment[s, 1]
        )
        nb = float(
            np.asarray(p.extracellular_amount_reference)[s, 1]
            + rb.extracellular_amount_increment[s, 1]
        )
        inactive = int(ra.integer_counts[0, 1]) == 0 and int(rb.integer_counts[0, 1]) == 0
        if inactive and int(ra.integer_events[0]) == int(rb.integer_events[0]):
            assert abs(nb - na * math.exp(-clearance * (b - a))) <= 1e-13 * na, a  # Clearance only.
        elif int(ra.integer_counts[0, 1]) == 1 and int(rb.integer_counts[0, 1]) == 1:
            filled += nb > na * math.exp(-clearance * (b - a))  # The unit fills the node.
        for name in ("local", "outside", "total", "integer_subunits"):
            assert np.all(np.isfinite(model.balances(rb, p)[name])), (a, name)
    assert filled > 0
