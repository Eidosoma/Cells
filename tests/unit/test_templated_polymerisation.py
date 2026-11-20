"""templated_polymerisation@1's kernel (gene regulation's option A, G4), on its own half-steps in
NumPy: no world is compiled. Each row integrates a world of validation/gene_regulation/worlds.py
for a few seconds of model time, two half-steps of dt/2 per step as the composite's split step
takes them, with the inner model inert for these rows (impermeant, no channel).

- One route live: its heat is the whole booked heat and equals -dG, G from the state alone at 60
  digits (engine_run.free_energy), never from extents or bookings.
- Every route live: the routes' heats sum to the booked heat, within rounding on their gross
  moves (the bookings' magnitude); each chain's and degradation's increment is non-negative at
  every half-step (the module docstring's claim inside the one-sided domain).
- Zero rates leave the state bit for bit; a chain whose product stands above 1 M is refused.
- The declaration: its refusals, and the cited entries it returns to the species registry, which
  refuses a perturbed one.
"""

import copy
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import OPERATORS
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.gene_regulation import engine_run, worlds

OP = OPERATORS[worlds.POLYMERISATION]


def _block(raw):
    (block,) = [o for o in raw["model"]["operators"] if o["law"] == worlds.POLYMERISATION]
    return block


def _controls(raw, block, only=None):
    """The world's rates at time 0 by route, every route but `only`'s at zero when it is given."""
    rate = {c["route_id"]: c["schedule"][0]["value"] for c in raw["experiment"][
        "polymerisation_controls"]}  # fmt: skip

    def values(routes):
        return np.array([rate[r.id] if only in (None, r.id) else 0.0 for r in routes])

    return SimpleNamespace(
        polymerisation_initiation_rate=values(block.chains),
        polymerisation_degradation_rate=values(block.degradations),
        polymerisation_transfer_capacity=values(block.transfers),
    )


def _integrate(raw, *, steps, dt=0.5, only=None, record=False):
    """(start, end, p, spec, per-half-step route-heat increments) of `steps` steps."""
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    control = _controls(raw, block, only)
    start, increments = state, []
    for _ in range(2 * steps):
        new, ok = OP.half_step(state, dt / 2, control, p, xp=np)
        assert bool(ok)
        if record:
            increments.append(
                np.concatenate([
                    new.poly_chain_heat_pJ - state.poly_chain_heat_pJ,
                    new.poly_degradation_heat_pJ - state.poly_degradation_heat_pJ,
                ])
            )  # fmt: skip
        state = new
    return start, state, p, spec, increments


def _G(state, p, spec):
    """(G of a state (§3.4) from its rows and complexes alone, pJ, as a Decimal; the magnitude
    of its terms, sum |n mu| in pJ, which bounds the rounding its float inputs carry)."""
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    species = list(spec.model.species_ids)
    amounts = {
        s.id: float(p.amount_reference[species.index(s.id), 0]
                    + state.amount_increment[species.index(s.id), 0])
        for s in block.species
    }  # fmt: skip
    mu = dict(zip([s.id for s in block.species], block.mu_RT, strict=True))
    transit, residue = {}, {}
    for i, c in enumerate(block.chains):
        r = c.residues // c.stages
        transit[c.id] = float(r * sum(j * state.poly_complexes_fmol[i, j] for j in range(c.stages)))
        residue[c.id] = mu[c.product] / c.residues  # c0 = 1000 mM: mu°_res at 1 M.
    g = engine_run.free_energy(amounts, transit, mu, residue, 1.0, block.c0_mM)
    rt = 1e-3 * 8.314462618 * spec.model.temperature_K
    size = sum(abs(n) * rt * (abs(mu[k]) + abs(np.log(n / block.c0_mM)) + 1) for k, n in
               amounts.items())  # fmt: skip
    return g, size


def _with_amount(raw, row, mM):
    out = copy.deepcopy(raw)
    out["model"]["cells"][0]["initial_amount_fmol"][row] = mM  # V = 1 pL.
    return out


# One route live: (world, its edit, the route, steps).
ONE_ROUTE = [
    ("pol T=5", None, "tx", 40),
    ("pol T=5", ("R", 1e-4), "deg_R", 20),
    ("pol T=5", None, "recharge", 20),
    ("rib n_R=10", None, "tl", 40),
    ("rib n_R=10", ("P", 1e-4), "deg_P", 20),
]


@pytest.mark.parametrize(("world", "edit", "route", "steps"), ONE_ROUTE)
def test_one_live_route_books_the_whole_heat_and_it_is_minus_dG(world, edit, route, steps):
    raw = worlds.world(world)
    if edit is not None:
        raw = _with_amount(raw, *edit)
    start, end, p, spec, _ = _integrate(raw, steps=steps, only=route)
    heats = np.concatenate([end.poly_chain_heat_pJ, end.poly_degradation_heat_pJ,
                            end.poly_transfer_heat_pJ])  # fmt: skip
    total = float(np.sum(end.poly_dissipated_energy_pJ))
    assert total > 0
    others = [h for h in heats if h != 0.0]
    assert len(others) == 1  # Only the live route books.
    assert others[0] == pytest.approx(total, rel=1e-13, abs=1e-15)
    (g1, size), (g0, _) = _G(end, p, spec), _G(start, p, spec)
    bookings = float(np.sum(end.poly_energy_magnitude_pJ))
    assert abs(total + float(g1 - g0)) <= 64 * np.finfo(float).eps * (size + bookings)


@pytest.mark.parametrize("world", ["A1", "two-gene"])
def test_every_route_live_sums_to_the_heat_and_one_sided_routes_never_cool(world):
    _, end, _, _, increments = _integrate(worlds.world(world), steps=60, record=True)
    routes = sum(float(np.sum(getattr(end, k))) for k in (
        "poly_chain_heat_pJ", "poly_degradation_heat_pJ", "poly_transfer_heat_pJ"))  # fmt: skip
    total = float(np.sum(end.poly_dissipated_energy_pJ))
    magnitude = float(np.sum(end.poly_energy_magnitude_pJ))
    assert abs(routes - total) <= 64 * np.finfo(float).eps * magnitude
    assert min(float(np.min(x)) for x in increments) >= 0.0


def test_zero_rates_leave_the_state_bit_for_bit():
    raw = worlds.world("pol T=5")
    start, end, _, _, _ = _integrate(raw, steps=3, only="no route")
    for a, b in zip(start, end, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b))


def test_a_product_above_one_molar_at_a_chain_in_use_is_refused():
    raw = _with_amount(worlds.world("pol T=5"), "R", 1500.0)
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    _, ok = OP.half_step(state, 0.25, _controls(raw, block), p, xp=np)
    assert not bool(ok)


# The declaration's refusals: (edit of A1's block, words of the refusal).
REFUSALS = [
    (lambda b: b["chains"][0].update(stages=7), "divide"),
    (lambda b: b["degradations"][0].update(standard_free_energy={"dG": 1.0}), "dG_RT"),
    (lambda b: b["degradations"][0]["standard_free_energy"].update(basis="other"), "basis"),
    (lambda b: b["transfers"][0].update(standard_free_energy={"dG_RT": float("nan")}), "finite"),
    (lambda b: b["transfers"][0].update(standard_free_energy=1.0), "null or an object"),
    (lambda b: b["degradations"][0].pop("standard_free_energy"), "standard_free_energy"),
]


@pytest.mark.parametrize(("edit", "words"), REFUSALS)
def test_the_declaration_refuses(edit, words):
    raw = worlds.a1(end=60.0)
    edit(_block(raw))
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)


def test_the_cited_entries_reach_the_registry_which_refuses_a_perturbed_one():
    raw = worlds.a1(end=60.0)
    (block,) = [d for d in parse_spec(raw).model.operators if d.law == worlds.POLYMERISATION]
    entries = OP.standard_free_energies(block)
    assert [e.stoichiometry for e in entries] == [
        (("R", -1), ("M", 1200)),
        (("P", -1), ("A", 400)),
        (("M", -1), ("ATP", -2), ("N", 1), ("ADP", 2)),
    ]
    assert entries[0].dG_basis == kind_registry.TEMPERATURE_INDEPENDENT
    assert entries[2].dG_RT is not None and entries[2].dG_kJ_mol is None
    bad = copy.deepcopy(raw)
    _block(bad)["degradations"][0]["standard_free_energy"]["dG_kJ_mol"] *= 1 + 1e-9
    with pytest.raises(ConfigError, match="one authority for each standard free energy"):
        parse_spec(bad)
