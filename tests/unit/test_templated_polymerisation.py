"""templated_polymerisation@1's kernel (gene regulation's option A, G4), on its own half-steps in
NumPy (validation/gene_regulation/kernel.py): no world is compiled. Each row advances a world of
validation/gene_regulation/worlds.py for a few seconds of model time.

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

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import templated_polymerisation as polymerisation
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.gene_regulation import engine_run, kernel, worlds

EPS = np.finfo(float).eps


def _ends(raw, *, only=None, record=False):
    spec, p, states, increments = kernel.run(raw, only=only, record=record)
    return states[0], states[max(states)], p, spec, increments


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
    for i, (c, _) in enumerate(polymerisation.releases_of(block)):  # The hold: L mu°_res each.
        transit[c.id] += c.residues * float(np.sum(state.poly_hold_fmol[i]))
    g = engine_run.free_energy(amounts, transit, mu, residue, 1.0, block.c0_mM)
    rt = 1e-3 * 8.314462618 * spec.model.temperature_K
    size = sum(abs(n) * rt * (abs(mu[k]) + abs(np.log(n / block.c0_mM)) + 1) for k, n in
               amounts.items())  # fmt: skip
    return g, size


def _with_amount(raw, row, mM):
    out = copy.deepcopy(raw)
    out["model"]["cells"][0]["initial_amount_fmol"][row] = mM  # V = 1 pL.
    return out


# One route live: (world, its edit, the route, seconds).
ONE_ROUTE = [
    ("pol T=5", None, "tx", 20.0),
    ("pol T=5", ("R", 1e-4), "deg_R", 10.0),
    ("pol T=5", None, "recharge", 10.0),
    ("rib n_R=10", None, "tl", 20.0),
    ("rib n_R=10", ("P", 1e-4), "deg_P", 10.0),
]


@pytest.mark.parametrize(("world", "edit", "route", "seconds"), ONE_ROUTE)
def test_one_live_route_books_the_whole_heat_and_it_is_minus_dG(world, edit, route, seconds):
    raw = kernel.truncated(worlds.world(world), seconds)
    if edit is not None:
        raw = _with_amount(raw, *edit)
    start, end, p, spec, _ = _ends(raw, only=route)
    heats = np.concatenate([end.poly_chain_heat_pJ, end.poly_degradation_heat_pJ,
                            end.poly_transfer_heat_pJ])  # fmt: skip
    total = float(np.sum(end.poly_dissipated_energy_pJ))
    assert total > 0
    others = [h for h in heats if h != 0.0]
    assert len(others) == 1  # Only the live route books.
    assert others[0] == pytest.approx(total, rel=1e-13, abs=1e-15)
    (g1, size), (g0, _) = _G(end, p, spec), _G(start, p, spec)
    bookings = float(np.sum(end.poly_energy_magnitude_pJ))
    assert abs(total + float(g1 - g0)) <= 64 * EPS * (size + bookings)


@pytest.mark.parametrize("world", ["A1", "two-gene"])
def test_every_route_live_sums_to_the_heat_and_one_sided_routes_never_cool(world):
    raw = worlds.a1(end=30.0) if world == "A1" else kernel.truncated(worlds.world(world), 30.0)
    _, end, _, _, increments = _ends(raw, record=True)
    routes = sum(float(np.sum(getattr(end, k))) for k in (
        "poly_chain_heat_pJ", "poly_degradation_heat_pJ", "poly_transfer_heat_pJ"))  # fmt: skip
    total = float(np.sum(end.poly_dissipated_energy_pJ))
    magnitude = float(np.sum(end.poly_energy_magnitude_pJ))
    assert abs(routes - total) <= 64 * EPS * magnitude
    assert min(float(np.min(x)) for x in increments) >= 0.0


def test_zero_rates_leave_the_state_bit_for_bit():
    start, end, _, _, _ = _ends(kernel.truncated(worlds.world("pol T=5"), 1.5), only="no route")
    for a, b in zip(start, end, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b))


def test_a_product_above_one_molar_at_a_chain_in_use_is_refused():
    raw = _with_amount(worlds.world("pol T=5"), "R", 1500.0)
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    _, ok = kernel.OP.half_step(state, 0.25, kernel.controls(raw, block), p, xp=np)
    assert not bool(ok)


def _release_in_a1(short_lived):
    """An edit of A1's block: transcription releasing into R and `short_lived` (FR-38)."""

    def edit(b):
        b["chains"][0]["release"] = worlds._release(0.75, "returned", [80], [("R", short_lived)])

    return edit


# The declaration's refusals: (edit of A1's block, words of the refusal).
REFUSALS = [
    (lambda b: b["chains"][0].update(stages=7), "divide"),
    (_release_in_a1("P"), "writes 'P', a fate row"),  # One producer per fate row.
    (lambda b: b["degradations"][0].update(standard_free_energy={"dG": 1.0}), "dG_RT"),
    (lambda b: b["degradations"][0]["standard_free_energy"].update(basis="other"), "basis"),
    (lambda b: b["transfers"][0].update(standard_free_energy={"dG_RT": float("nan")}), "finite"),
    (lambda b: b["transfers"][0].update(standard_free_energy=1.0), "null or an object"),
    (lambda b: b["degradations"][0].pop("standard_free_energy"), "standard_free_energy"),
]


@pytest.mark.parametrize(("edit", "words"), REFUSALS)
def test_the_declaration_refuses(edit, words):
    raw = worlds.a1(end=60.0)
    edit(kernel.block(raw))
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)


def test_the_cited_entries_reach_the_registry_which_refuses_a_perturbed_one():
    raw = worlds.a1(end=60.0)
    (block,) = [d for d in parse_spec(raw).model.operators if d.law == worlds.POLYMERISATION]
    entries = kernel.OP.standard_free_energies(block)
    assert [e.stoichiometry for e in entries] == [
        (("R", -1), ("M", 1200)),
        (("P", -1), ("A", 400)),
        (("M", -1), ("ATP", -2), ("N", 1), ("ADP", 2)),
    ]
    assert entries[0].dG_basis == kind_registry.TEMPERATURE_INDEPENDENT
    assert entries[2].dG_RT is not None and entries[2].dG_kJ_mol is None
    bad = copy.deepcopy(raw)
    kernel.block(bad)["degradations"][0]["standard_free_energy"]["dG_kJ_mol"] *= 1 + 1e-9
    with pytest.raises(ConfigError, match="one authority for each standard free energy"):
        parse_spec(bad)


# ------------------------------------------------------------------ the release (§9, FR-38)

K_I = float(worlds.sheet.A1["k_I_tx"])


def _release(raw):
    return kernel.block(raw)["chains"][0]["release"]


def _control(raw, route):
    return next(c for c in raw["experiment"]["polymerisation_controls"] if c["route_id"] == route)


# R1's refusals (§9.1-§9.6): (edit of R1's raw definition at p = 0.75, words of the refusal).
RELEASE_REFUSALS = [
    (lambda raw: _release(raw).update(machine="kept"), "machine is one of"),
    (lambda raw: _release(raw).update(durable_fraction=1.5), "durable_fraction"),
    (lambda raw: _release(raw).update(fates=[dict(durable="R", short_lived="R")]), "distinct"),
    (lambda raw: _release(raw)["fates"][0].update(short_lived="N"), "none of its draws"),
    (lambda raw: _release(raw)["fates"][0].update(short_lived="M"), "another standard_mu_RT"),
    (lambda raw: _release(raw).update(label=dict(id="l", at="release")), "label is null"),
    (lambda raw: _release(raw).update(machine="held", initial_copies=[2e4]), "cannot hold"),
    (lambda raw: _release(raw).update(dwell_s=1.0), "dt/tau"),
    (
        lambda raw: (
            _release(raw).update(durable_fraction="scheduled"),
            raw["experiment"]["polymerisation_controls"].append(
                dict(route_id=worlds.RELEASE, schedule=[dict(time=0.0, value=1.2)])
            ),
        ),
        "durable fraction is in",
    ),
]


@pytest.mark.parametrize(("edit", "words"), RELEASE_REFUSALS)
def test_the_release_refuses(edit, words):
    raw = worlds.r1(0.75)
    edit(raw)
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)


def _identity_bound(*terms):
    return 64 * EPS * max(abs(t) for t in terms) + 1e-30


# R1 on the kernel for 60 s at dt 2 s: (p, machine, transcription's k_I).
RELEASES = [
    (0.75, "returned", 0.0),
    (1.0, "held", 0.0),
    (0.0, "held", K_I),
    (0.25, "returned", K_I),
]


@pytest.mark.parametrize(("p", "machine", "k_I"), RELEASES)
def test_the_release_keeps_its_identities_and_sits_on_its_limit(p, machine, k_I):
    """FR-38, about 0.3 s a row, no world compiled: R1's world (worlds.r1) on the kernel, whose
    rows with k_I > 0 bring arrivals into the hold. The hold's, each fate row's and the machines'
    identities (§9.7); at k_I = 0 the hold and releases on their closed forms (§9.10, no affinity
    factor); at p = 0 or 1 the zero-rate route's counter and heat exactly 0.0; G's identity with
    the hold's term (§9.5), the routes' heats summing to the booked heat, and no heat increment
    below zero. A chain without a release keeps today's form, and this one round-trips."""
    raw = kernel.truncated(worlds.r1(p, machine=machine, initiation=k_I), 60.0)
    start, end, layout, spec, increments = _ends(raw, record=True)
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    assert type(block.chains[0]) is polymerisation.ReleasingChain
    assert parse_spec(spec.to_dict()).model.operators == spec.model.operators
    (a1,) = [d for d in parse_spec(worlds.a1(end=60.0)).model.operators if d.law == block.law]
    assert type(a1.chains[0]) is polymerisation.Chain
    assert "release" not in polymerisation.declaration_to_dict(a1)["chains"][0]
    species = list(spec.model.species_ids)

    def n(state, row):
        i = species.index(row)
        return float(layout.amount_reference[i, 0] + state.amount_increment[i, 0])

    H0, H = float(start.poly_hold_fmol[0, 0]), float(end.poly_hold_fmol[0, 0])
    A = float(end.poly_released_fmol[0])
    Q = end.poly_hold_released_fmol[0, 0]  # [fate]
    assert (k_I > 0) == (A > 0)
    assert abs(H0 + A - H - Q[0] - Q[1]) <= _identity_bound(H0, A, H, *Q)
    for f, row in enumerate(("R", "R_s")):
        lost = float(end.poly_degraded_fmol[f])
        gained = n(end, row) - n(start, row)
        assert abs(gained - Q[f] + lost) <= _identity_bound(n(end, row), Q[f], lost)
    M = float(layout.poly_pool_total_fmol[0])
    engaged = float(np.sum(end.poly_complexes_fmol)) + (H if machine == "held" else 0.0)
    assert abs(float(end.poly_free_machines_fmol[0]) + engaged - M) <= _identity_bound(M)
    if k_I == 0.0:
        tau = float(worlds.sheet.RELEASE["tau"])
        assert H == pytest.approx(H0 * np.exp(-60.0 / tau), rel=1e-10)
        out = -np.expm1(-60.0 / tau) * H0
        assert Q[0] == pytest.approx(p * out, rel=1e-10)
        assert Q[1] == pytest.approx((1.0 - p) * out, rel=1e-10)
    if p in (0.0, 1.0):
        zero = 0 if p == 0.0 else 1
        assert Q[zero] == 0.0 and end.poly_release_heat_pJ[0, 0, zero] == 0.0
    total = float(np.sum(end.poly_dissipated_energy_pJ))
    routes = sum(float(np.sum(getattr(end, k))) for k in (
        "poly_chain_heat_pJ", "poly_degradation_heat_pJ", "poly_release_heat_pJ"))  # fmt: skip
    bookings = float(np.sum(end.poly_energy_magnitude_pJ))
    assert abs(routes - total) <= 64 * EPS * bookings
    (g1, size), (g0, _) = _G(end, layout, spec), _G(start, layout, spec)
    assert abs(total + float(g1 - g0)) <= 64 * EPS * (size + bookings)
    assert min(float(np.min(x)) for x in increments) >= 0.0


def _labelled(at, k_I):
    """R1's labelled world at p = 0.75 (§9.8's route 1), the label held at class 2 from t = 0;
    labelled at completion, the hold has both classes, class 1 holding R1's 80 copies."""
    raw = worlds.r1(0.75, labelled=True, initiation=k_I)
    _control(raw, worlds.LABEL)["schedule"] = [dict(time=0.0, value=2.0)]
    if at == "completion":
        _release(raw).update(label=dict(id=worlds.LABEL, at="completion"), initial_copies=[80, 0])
    return kernel.truncated(raw, 60.0)


@pytest.mark.parametrize("at", ["release", "completion"])
def test_the_label_puts_each_molecule_in_its_class(at):
    """FR-38, about 0.3 s a row, no world compiled: the class axis (§9.1). Labelled at release, the
    hold keeps one class and every release enters class 2's rows, bit for bit the unlabelled
    run's releases. Labelled at completion, with arrivals (A1's k_I), every arrival enters hold
    class 2, while class 1's starting copies leave into class 1's rows alone."""
    _, end, _, _, _ = _ends(_labelled(at, K_I if at == "completion" else 0.0))
    hold, released = end.poly_hold_fmol[0], end.poly_hold_released_fmol[0]  # [class], [class, fate]
    if at == "release":
        _, plain, _, _, _ = _ends(kernel.truncated(worlds.r1(0.75), 60.0))
        assert hold[1] == 0.0 and np.all(released[0] == 0.0)
        assert np.array_equal(released[1], plain.poly_hold_released_fmol[0, 0])
        assert hold[0] == plain.poly_hold_fmol[0, 0]
        return
    H0 = 80 * polymerisation.COPY_FMOL
    A = float(end.poly_released_fmol[0])
    tau = float(worlds.sheet.RELEASE["tau"])
    assert A > 0 and hold[0] == pytest.approx(H0 * np.exp(-60.0 / tau), rel=1e-10)
    assert abs(H0 - hold[0] - np.sum(released[0])) <= _identity_bound(H0)
    assert abs(A - hold[1] - np.sum(released[1])) <= _identity_bound(A, hold[1])
