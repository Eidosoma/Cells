"""FR-49's World B, its development check (fr49-compartment-compositions-v1, Part B;
validation/fr49/REGISTRATION.md §4). B1 to B6 against the code-blind references are the registered
judgement (validation/fr49/judge_bc.py), run once from a clean snapshot; this file is a regression
of the compiled path through sites at a compartment beside a wash elsewhere.

World B (validation/fr49/worlds_bc.world_b) is shortened here: the wash moved from 300 s to 30 s and
the horizon from 600 s to 60 s, at dt = 0.1 s, observed every 5 s. Its twin declares the wash with
no event. Two compiles. The checks:
- both runs complete, so the runner's host checks pass on every accepted row (every ledger);
- B2: n_L + B = L_T at lys to 1e-10 L_T on every row;
- B5: lys's species rows and the population's R and B are bit for bit the twin's on every row,
  before and after the wash, while the well's wash applies once in the run and never in the twin;
- the transient meets the exact Riccati solution (the design note's §1.2, from cases.json's values)
  within 1e-3 of B* on every row, a development bound: SSPRK(3,3)'s local error at the start, where
  dt L is about 0.2, is about 6e-5 of the transient's scale (the judgement's B3 and B4 are 7.2 to
  8.8 and 1e-10).

Seconds and reason (D224): 55 s on one core at the build (two compiles and 1,200 steps; measured
again at landing). It is the only compiled path through cells.operator.site_occupancy@1 beside
cells.operator.cell_owned_compartments@1 and a wash of another node.
"""

import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.models import get_model
from validation.fr49 import worlds
from validation.fr49 import worlds_bc as wb

jax.config.update("jax_enable_x64", True)

T_WASH, END, DT, EVERY = 30.0, 60.0, 0.1, 5.0
SITES_PER_FMOL = 602_214_076.0


def shortened(event):
    raw = wb.world_b(dt=DT, end=END, every=EVERY, event=event)
    for e in raw["experiment"]["compartment_wash_events"]:
        e["time"] = T_WASH
    return raw


@pytest.fixture(scope="module")
def runs():
    out = {}
    for name, event in (("washed", True), ("twin", False)):
        spec = parse_spec(shortened(event))
        out[name] = (spec, run(spec))  # Its host checks run on every accepted row.
    return out


def amounts(spec, result):
    """(n_L at lys, B) on every saved row, fmol."""
    _, p = get_model(spec.model).initial_values(spec)
    h = result.history
    row = list(spec.model.species_ids).index(wb.LIGAND)
    lys = [c.id for c in spec.model.extracellular].index(wb.LYS)
    n_l = (np.asarray(p.extracellular_amount_reference)[row, lys]
           + np.asarray(h.extracellular_amount_increment)[:, row, lys])  # fmt: skip
    bound = np.asarray(p.site_bound_anchor_fmol)[0] + np.asarray(h.site_bound_increment_fmol)[:, 0]
    return n_l, bound


def exact(times):
    """B(t) from B(0) = 0: the Riccati solution with depletion (LAWS.md §3; design note §1.2)."""
    v = worlds.declared("B")
    volume, total = float(v["V_C_pL"]), float(v["initial_fmol"]["n_L"])
    sites = v["sites"]
    capacity = (float(sites["accessible_fraction"]) * int(sites["sites_per_copy"])
                * float(sites["copies"]) / SITES_PER_FMOL)  # fmt: skip
    k_on, k_off = float(v["k_on_per_mM_per_s"]), float(v["k_off_per_s"])
    k_d = k_off / k_on
    q = total + capacity + volume * k_d
    # The discriminant q^2 - 4 L_T S, written without cancellation.
    square = (total - capacity) ** 2 + 2 * volume * k_d * (total + capacity) + (volume * k_d) ** 2
    upper = (q + math.sqrt(square)) / 2
    lower = total * capacity / upper  # B1 = B*, the smaller root.
    rate = k_on * (upper - lower) / volume
    r = (lower / upper) * np.exp(-rate * np.asarray(times))
    return (lower - upper * r) / (1 - r), lower, total


def test_b2_the_ligand_is_conserved_at_lys_on_every_row(runs):
    spec, result = runs["washed"]
    n_l, bound = amounts(spec, result)
    total = float(worlds.declared("B")["initial_fmol"]["n_L"])
    assert np.all(np.abs(n_l + bound - total) <= 1e-10 * total)


def test_b5_lys_and_the_sites_are_the_twins_bit_for_bit_across_a_wash_elsewhere(runs):
    spec, washed = runs["washed"]
    _, twin = runs["twin"]
    lys = [c.id for c in spec.model.extracellular].index(wb.LYS)
    well = [c.id for c in spec.model.extracellular].index(wb.WELL)
    a, b = washed.history, twin.history
    for name in ("site_free_increment_fmol", "site_bound_increment_fmol"):
        assert np.asarray(getattr(a, name)).tobytes() == np.asarray(getattr(b, name)).tobytes()
    at_lys = [np.asarray(h.extracellular_amount_increment)[:, :, lys] for h in (a, b)]
    assert at_lys[0].tobytes() == at_lys[1].tobytes()
    assert np.asarray(a.wash_applied)[-1, well] == 1 and np.asarray(b.wash_applied)[-1, well] == 0
    assert np.all(np.asarray(a.wash_applied)[:, lys] == 0)


def test_the_transient_meets_the_exact_riccati_solution(runs):
    spec, result = runs["washed"]
    _, bound = amounts(spec, result)
    expected, b_star, _ = exact(result.times)
    assert np.all(np.abs(bound - expected) <= 1e-3 * b_star), np.max(np.abs(bound - expected))
    assert bound[0] == 0.0 and np.all(np.diff(bound) > 0)
