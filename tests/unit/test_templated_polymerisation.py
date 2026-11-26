"""cells.operator.templated_polymerisation@1's kernel (gene regulation's option A, G4), on its own half-steps in
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
import json
from decimal import Decimal

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import templated_polymerisation as polymerisation
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.gene_regulation import cohort, engine_run, kernel, release_check, worlds

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


def _negative_mu():
    """pol T=5 at a potential set with E_pd = +4 RT, so that the RNA's standard potential, mu°_R =
    -L E_pd, is negative: the operator admits any finite mu° (a negative one is physical)."""
    return worlds.polymerase_limited(5, symbols=dict(worlds.test_instance(), E_pd=Decimal(4)))


# One route live: (world, or a builder of it; its edit, the route, seconds).
ONE_ROUTE = [
    ("pol T=5", None, "tx", 20.0),
    ("pol T=5", ("R", 1e-4), "deg_R", 10.0),
    ("pol T=5", None, "recharge", 10.0),
    ("rib n_R=10", None, "tl", 20.0),
    ("rib n_R=10", ("P", 1e-4), "deg_P", 10.0),
    pytest.param(_negative_mu, ("R", 1e-4), "deg_R", 10.0, id="pol T=5 mu_R below 0-deg_R"),
]


@pytest.mark.parametrize(("world", "edit", "route", "seconds"), ONE_ROUTE)
def test_one_live_route_books_the_whole_heat_and_it_is_minus_dG(world, edit, route, seconds):
    raw = kernel.truncated(world() if callable(world) else worlds.world(world), seconds)
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


def _beside_a_compartment(*, export=True, degradation=True):
    """R1 with its export node `space_0` declared as cell_0's compartment (FR-49, D327): with or
    without the export into it, and with or without the outside degradation there."""
    from validation.tissue import compartment_fixtures as cfx

    raw = worlds.with_export(worlds.r1(0.75))
    block = kernel.block(raw)
    dropped = set()
    if not degradation:
        block.pop("outside_degradations")
        dropped.add(f"deg_R_{worlds.SPACE}")
    if not export:
        block.pop("exports")
        dropped.add("export_R")
    controls = raw["experiment"]["polymerisation_controls"]
    raw["experiment"]["polymerisation_controls"] = [
        c for c in controls if c["route_id"] not in dropped
    ]
    patch = f"{worlds.EXPORT_PATCH}_{worlds.CELL}_{worlds.SPACE}"
    return cfx.with_compartments(
        raw, [cfx.compartment(cid="lumen_0", node=worlds.SPACE, patch=patch, owner=worlds.CELL)]
    )


# FR-49 (validation/fr49/REGISTRATION.md, Part H): (world, words of the refusal, or None where
# the world is admitted). Each refusal names the compartment; routes in the owner only compose.
BESIDE_A_COMPARTMENT = {
    "routes in the owner only": (
        lambda: _beside_a_compartment(export=False, degradation=False),
        None,
    ),
    "an export into the compartment": (
        lambda: _beside_a_compartment(degradation=False),
        f"export export_R opens onto '{worlds.SPACE}', compartment 'lumen_0'",
    ),
    "an outside degradation at the compartment": (
        _beside_a_compartment,
        f"outside degradation deg_R_{worlds.SPACE} is at '{worlds.SPACE}', compartment 'lumen_0'",
    ),
}


@pytest.mark.parametrize("name", sorted(BESIDE_A_COMPARTMENT))
def test_beside_a_compartment(name):
    """FR-49's expression entry: the compartments' list names cells.operator.templated_polymerisation@1, and the
    operator's own check refuses an export into a compartment's node and an outside degradation
    there, each with its reason. Host only: a parse, no compile."""
    build, words = BESIDE_A_COMPARTMENT[name]
    if words is None:
        spec = parse_spec(build())
        assert worlds.POLYMERISATION in [d.law for d in spec.model.operators]
        return
    with pytest.raises(ConfigError, match=words):
        parse_spec(build())


def test_beside_a_compartment_the_operators_check_is_the_only_wall(monkeypatch):
    """The plant (Part H): without check_compartments, the export into the compartment parses, so
    the refusal is the operator's own and nothing else stands behind it."""
    monkeypatch.setattr(polymerisation, "check_compartments", lambda spec, declaration: None)
    parse_spec(_beside_a_compartment(degradation=False))


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


def _replaced(raw, templates=True):
    """R1 beside cells.operator.scheduled_cell_replacement@1, which replaces its one cell at 120 s by a newcomer
    from template T (amendment S, §9.16), in place; with templates, T's values are the founder's
    time-0 values, as the occupant rule (item 6) requires."""
    from validation.tissue import secreted_species_fixtures as sfx

    template = sfx.template(raw, worlds.CELL, "T")
    raw.update(sfx.with_replacement(raw, [template], [(120.0, worlds.CELL, "T", "cell_0_g1")]))
    if templates:
        rates = {c["route_id"]: c["schedule"][0]["value"]
                 for c in raw["experiment"]["polymerisation_controls"]}  # fmt: skip
        kernel.block(raw)["templates"] = [dict(template_id="T", rates=rates)]
    return raw


def _unused_template(raw):
    """_replaced's R1 with a second replacement template U, which no event uses, given values."""
    _replaced(raw)
    replacement = raw["model"]["operators"][0]
    replacement["templates"].append(dict(replacement["templates"][0], id="U"))
    replacement["template_capacity"] = 2
    block = kernel.block(raw)
    block["templates"].append(dict(block["templates"][0], template_id="U"))


def _another_version(raw):
    """_replaced's R1 over water, with replacement@2 in place of replacement@1 (§9.16, item 1)."""
    from validation.tissue import shared_inventory_fixtures as inventories

    raw.update(inventories.with_water_first(_replaced(raw)))
    (block,) = [
        o
        for o in raw["model"]["operators"]
        if o["law"] == "cells.operator.scheduled_cell_replacement@1"
    ]
    block.update(law="cells.operator.scheduled_cell_replacement@2", impermeant_species=[])


# R1's refusals (§9.1-§9.6, and §9.16's beside a replacement): (edit of R1's raw definition at
# p = 0.75, words of the refusal).
RELEASE_REFUSALS = [
    (lambda raw: _release(raw).update(machine="kept"), "machine is one of"),
    (lambda raw: _release(raw).update(durable_fraction=1.5), "durable_fraction"),
    (lambda raw: _release(raw).update(fates=[dict(durable="R", short_lived="R")]), "distinct"),
    (lambda raw: _release(raw)["fates"][0].update(short_lived="N"), "none of its draws"),
    (lambda raw: _release(raw)["fates"][0].update(short_lived="M"), "another standard_mu_RT"),
    (lambda raw: _release(raw).update(label=dict(at="later")), "label is at one of"),
    (
        lambda raw: _release(raw).update(fates=[dict(durable="R", short_lived="R_s")] * 2),
        "one {durable, short_lived} pair",
    ),
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
    (lambda raw: _replaced(raw, templates=False), "declare T in templates with a value for tx"),
    (
        lambda raw: kernel.block(_replaced(raw))["templates"][0].update(template_id="Z"),
        "declares values for Z, not a replacement template",
    ),
    (_unused_template, "template U's value for deg_R applies to no schedule"),
    (
        _another_version,
        "composes with cells.operator.scheduled_cell_replacement@1 only, not "
        "cells.operator.scheduled_cell_replacement@2",
    ),
    (
        lambda raw: _control(_replaced(raw), "deg_R")["schedule"].append(
            dict(time=180.0, value=1e-4)
        ),
        "at or after its founder's death",
    ),
    # Amendment T's export (§9.17.6), on R1 with worlds.with_export's export of R into its node.
    (lambda raw: _export(raw, patch=worlds.PATCH), "opens onto a held bath"),
    (lambda raw: _export(raw, coupling={}), "passive form is refused"),
    (lambda raw: _export(raw, row="N"), "is no fate row or product of a chain"),
    (lambda raw: _export(raw, saturation_mM={}), "gives K"),
    (lambda raw: _export(raw, k_E=1.0), "export_R has dt k"),
    (
        lambda raw: kernel.block(_export(raw))["outside_degradations"][0].update(polymer="R_s"),
        "is carried into",
    ),
]


def _export(raw, k_E=None, **changes):
    """raw, in place, with worlds.with_export's export of R into its finite node, the export's
    declaration then edited by `changes` and its k_E set."""
    raw.update(worlds.with_export(raw, **({} if k_E is None else dict(k_E=k_E))))
    kernel.block(raw)["exports"][0].update(changes)
    return raw


@pytest.mark.parametrize(("edit", "words"), RELEASE_REFUSALS)
def test_the_release_refuses(edit, words, monkeypatch):
    raw = worlds.r1(0.75)
    edit(raw)
    if edit is _another_version:  # Refused first as a second volume changer; that planted away:
        with pytest.raises(
            ConfigError, match="cells.operator.scheduled_cell_replacement@2 changes the volumes"
        ):
            parse_spec(raw)
        monkeypatch.setattr(polymerisation.species_reactions, "check_volume_changers", lambda *_: 0)
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)


def test_a_replacement_takes_the_occupants_chains_and_hold_and_restarts_its_counters(monkeypatch):
    """FR-38's step 4 (amendment S, §9.16), about 1 s, no world compiled: R1 with A1's k_I beside
    replacement@1 at 120 s, T's k_I half the founder's, after 60 s of the operator's own
    half-steps. Nothing due: the state bit for bit. Due: complexes and hold 0, every machine free,
    each removal counter the amount that left, mu°_res (W + L H) the free energy leaving, every
    birth value the counter's, the residue and machine ledgers at rounding, and the founder's
    per-producer identity (item 4). With labels (FR-42's pool reporter, erratum E) the same state
    and the emptied holds reported, zeros when nothing is due. A stale count is refused. The
    controls: the due count steps at 120 s and T's values hold from then. A donor copy into the
    slot is refused (check_occupants)."""
    from dataclasses import replace
    from types import SimpleNamespace

    raw = _replaced(kernel.truncated(worlds.r1(0.75, initiation=K_I), 240.0))
    kernel.block(raw)["templates"][0]["rates"]["tx"] = 0.5 * K_I
    spec = parse_spec(raw)
    model = get_model(spec.model)
    op = next(o for o in model.operators if o.LAW_ID == polymerisation.LAW_ID)
    state, p = model.initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    control = kernel.controls(raw, block)
    for _ in range(60):
        state, ok = op.half_step(state, 1.0, control, p, xp=np)
        assert bool(ok)

    def due(count):
        return SimpleNamespace(**{polymerisation.REPLACEMENTS_DUE: np.array([count])})

    same, ok = op.event(state, due(0.0), p, xp=np)
    assert bool(ok) and all(np.array_equal(a, b) for a, b in zip(same, state, strict=True))
    assert not bool(op.event(state, due(2.0), p, xp=np)[1])  # Stale.
    after, ok = op.event(state, due(1.0), p, xp=np)
    assert bool(ok) and int(after.poly_rep_applied[0]) == 1
    C, H = state.poly_complexes_fmol[0], float(np.sum(state.poly_hold_fmol))
    # FR-42's pool reporter (erratum E): with labels it reports the holds it empties, in order.
    rows = np.array([0])
    assert op.event(state, due(0.0), p, xp=np, labels=rows)[2].tolist() == [0.0]
    labelled, ok_l, removed = op.event(state, due(1.0), p, xp=np, labels=rows)
    assert removed.tolist() == [H] and all(
        np.array_equal(a, b) for a, b in zip(labelled, after, strict=True)
    )
    assert C.sum() > 0 and H > 0
    assert not np.any(after.poly_complexes_fmol) and not np.any(after.poly_hold_fmol)
    assert np.array_equal(after.poly_free_machines_fmol, p.poly_pool_total_fmol)
    W = float(np.sum(p.poly_chain_held[0] * C))
    assert after.poly_rep_chains_removed_fmol[0] == pytest.approx(C.sum(), rel=4 * EPS)
    assert after.poly_rep_residues_removed_fmol[0] == pytest.approx(W, rel=4 * EPS)
    assert after.poly_rep_hold_removed_fmol[0, 0] == H
    rt = 1e-3 * 8.314462618 * spec.model.temperature_K
    leaving = rt * p.poly_chain_residue_mu_RT[0] * (W + p.poly_chain_length[0] * H)
    assert after.poly_rep_removed_energy_pJ[0] == pytest.approx(leaving, rel=16 * EPS)
    counters = [float(getattr(state, n)[0]) for n in polymerisation.CHAIN_COUNTERS]
    assert after.poly_rep_chain_birth_fmol[0].tolist() == counters
    assert after.poly_rep_chain_departed_fmol[0].tolist() == counters  # The founder's from 0.
    assert np.array_equal(after.poly_rep_release_birth_fmol[0], state.poly_hold_released_fmol[0])
    assert np.array_equal(after.poly_rep_degradation_birth_fmol, state.poly_degraded_fmol)
    ledgers, magnitudes = op.own_ledgers(after, p, xp=np), op.own_magnitudes(after, p, xp=np)
    for value, size in zip(ledgers.values(), magnitudes, strict=True):
        assert np.all(np.abs(value) <= 64 * EPS * size + 1e-30)
    species = list(spec.model.species_ids)

    def n(s, row):
        i = species.index(row)
        return float(p.amount_reference[i, 0] + s.amount_increment[i, 0])

    initial = float(np.sum(p.poly_rel_hold0_fmol))
    start = model.initial_values(spec)[0]
    kept = sum(n(state, r) - n(start, r) + float(state.poly_degraded_fmol[f])
               for f, r in enumerate(("R", "R_s")))  # fmt: skip
    arrivals = float(state.poly_released_fmol[0])
    assert abs(initial + arrivals - H - kept) <= _identity_bound(initial, arrivals, H, kept)
    values = cs.control_values(spec, [118.0, 120.0, 122.0])
    assert values.polymerisation_replacements_due[:, 0].tolist() == [0.0, 1.0, 1.0]
    assert values.polymerisation_initiation_rate[:, 0].tolist() == [K_I, 0.5 * K_I, 0.5 * K_I]
    replacement, events = polymerisation.common.replacement_of(spec)
    donor = replace(events[0], newcomer="donor_copy", template=None, donor="cell_0")
    monkeypatch.setattr(polymerisation.common, "replacement_of", lambda s: (replacement, (donor,)))
    schedule = next(x for o, _, x in cs.entries(spec) if o.LAW_ID == polymerisation.LAW_ID)
    with pytest.raises(ConfigError, match="a donor copy into or from cell_0"):
        polymerisation.check_occupants(spec, block, schedule)


def _identity_bound(*terms):
    return 64 * EPS * max(abs(t) for t in terms) + 1e-30


# R1 on the kernel for 60 s at dt 2 s: (p, machine, transcription's k_I, p's source).
RELEASES = [
    (0.75, "returned", 0.0, "constant"),
    (1.0, "held", 0.0, "constant"),
    (0.0, "held", K_I, "constant"),
    (0.25, "returned", K_I, "scheduled"),
]


@pytest.mark.parametrize(("p", "machine", "k_I", "source"), RELEASES)
def test_the_release_keeps_its_identities_and_sits_on_its_limit(p, machine, k_I, source):
    """FR-38, about 0.3 s a row, no world compiled: R1's world (worlds.r1) on the kernel, whose
    rows with k_I > 0 bring arrivals into the hold. The hold's, each fate row's and the machines'
    identities (§9.7); at k_I = 0 the hold and releases on their closed forms (§9.10, no affinity
    factor); at p = 0 or 1 the zero-rate route's counter and heat exactly 0.0; G's identity with
    the hold's term (§9.5), the routes' heats summing to the booked heat, and no heat increment
    below zero. A chain without a release keeps today's form, and this one round-trips. A
    scheduled p reaches the controls at its changes (cs.control_values)."""
    raw = kernel.truncated(worlds.r1(p, machine=machine, initiation=k_I), 60.0)
    if source == "scheduled":
        _release(raw)["durable_fraction"] = "scheduled"
        schedule = [dict(time=0.0, value=p), dict(time=30.0, value=1.0)]
        raw["experiment"]["polymerisation_controls"].append(
            dict(route_id=worlds.RELEASE, schedule=schedule)
        )
        values = cs.control_values(parse_spec(raw), [0.0, 28.0, 30.0, 58.0])
        assert list(values.polymerisation_release_fraction[:, 0]) == [p, p, 1.0, 1.0]
        assert list(values.polymerisation_release_class[:, 0]) == [1.0] * 4
        schedule.pop()  # The kernel holds the time-0 values.
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


PRODUCER = "cell_0-g0-tx"  # A producer's label: cell, occupant generation and chain (D296).


EDGE = 0.25  # e^(y_f) at the edge row's start: re-synthesis a quarter of the gross loss.


def _r1(k_I, edge=False):
    """R1's world at p = 0.75 to 40 s, outputs every step. With edge, near its fate rows'
    degradation's domain edge (y_f <= X_DOM = -1), at e^(y_f) = EDGE at the start: E_pd = 0, so
    that mu°_R = L mu°_res = 0 (a listed row's potential is >= 0, so E_pd cannot reach the edge
    alone), and M's amount set so that y_f = E_pd/RT + ln(c_M/c0) - ln(c_R/c0)/L_R (§4.4, with
    mu°_M = 0) is ln(EDGE), about 243 mM."""
    if not edge:
        raw = worlds.r1(0.75, initiation=k_I)
    else:
        a = worlds.sheet.A1
        c0, length = worlds.C0_MM, int(a["L_R"])
        symbols = dict(worlds.test_instance(), E_pd=Decimal(0))
        c_M = c0 * EDGE * (float(a["c_R"]) / c0) ** (1.0 / length)
        raw = _with_amount(worlds.r1(0.75, initiation=k_I, symbols=symbols), "M", c_M)
    raw = kernel.truncated(raw, 40.0)
    raw["experiment"]["observation_times"] = [float(t) for t in range(0, 41, 2)]
    return raw


def _labelled(at, k_I, *, edge=False, chain="tx"):
    """_r1's world labelled by shares (FR-42, D289, D296; errata C and F): FR-42's labels on R and
    R_s, the window [0, 20 s) on transcription's own label schedule marking its releases, or at
    completion its completions, which the hold then carries into the fate rows. With chain None
    the window marks the species' own arrivals instead, re-synthesis among them. The producer row
    marks at completion too, transcription's completions joining its producer label by its own
    schedule (a source's, D296) from t = 0, beside the species' window."""
    raw = _r1(k_I, edge)
    if at in ("completion", "producer"):
        _release(raw)["label"] = dict(at="completion")
    if at == "producer":
        labels = (*worlds.R1_LABELS, PRODUCER)
        sources = (("tx", "R", ((0.0, PRODUCER),)),)
        return worlds.with_share_labels(raw, window=(0.0, 20.0), labels=labels, sources=sources)
    return worlds.with_share_labels(raw, window=(0.0, 20.0), chain=chain)


def _cohort_copies(spec, layout, state, row="R"):
    """A row's amount carrying the window's label (label 1), in copies, at the one cell."""
    i = list(spec.model.species_ids).index(row)
    n = layout.amount_reference[i, 0] + state.amount_increment[i, 0]
    share = state.label_share[worlds.R1_LABELLED.index(row), 1, 0]
    return float(n * share) / polymerisation.COPY_FMOL


@pytest.mark.parametrize("at", ["release", "completion", "producer", "edge"])
def test_the_label_marks_each_molecule(at):
    """FR-38, no world compiled, about 1.5 s a row (the edge row 3 s): labels on shares (FR-42,
    D289; errata C and F), with the label owner's own update (species_labels.advance) as the
    composite applies it. Every physical field is the unlabelled run's bit for bit (a label at
    completion changes no physics), each row's and the hold's shares sum to 1, and the cohort
    starts at exactly zero.
    - At release (k_I = 0): route 1, R's row times its cohort share, on the window's closed form
      within the survivors' bound plus the update's split, k_f h^2/(12 tau).
    - At the degradation's domain edge (k_I = 0, e^(y_f) = 1/4; erratum F): route 1 on
      transcription's own schedule equals route 2, cohort.known_rate on the run's own releases at
      the gross k_d, within route 2's grid error (the same on every second output) plus the
      split's error term and the shares' rounding. The window on the species' own arrivals counts
      the re-synthesised molecules too, so it lies above that bound: it is not the cohort.
    - At completion (A1's k_I, D296): the hold's cohort, the window's completions still held, on
      route 2's known-rate calculation at the hold's exact exit rate 1/tau, from the run's own
      completions, within its grid error (the same on every second output) plus the survivors'
      bound; and the hold carries the cohort into both fate rows.
    - A producer (step 3): transcription's own schedule puts all its completions at its producer
      label, so the hold's producer amount is every completion still held, the window's cohort
      takes none of them, and the hold carries the producer's label into both fate rows."""
    k_I, edge = (0.0 if at in ("release", "edge") else K_I), at == "edge"
    spec, layout, states, _ = kernel.run(_labelled(at, k_I, edge=edge))
    plain = kernel.run(_r1(k_I, edge))[2][20]
    start, end = states[0], states[20]
    for name in type(plain)._fields:
        assert np.array_equal(getattr(end, name), getattr(plain, name)), name
    shares, hold = end.label_share[:, :, 0], end.label_pool_share[0, :, 0]  # [R, R_s][base, cohort]
    assert np.all(np.abs(shares.sum(axis=1) - 1.0) <= 128 * EPS)
    assert abs(hold.sum() - 1.0) <= 128 * EPS
    assert start.label_share[0, 1, 0] == start.label_pool_share[0, 1, 0] == 0.0
    route1 = _cohort_copies(spec, layout, end)
    if at == "release":
        exact = release_check.window_cohort(0.75, "durable", 0.0, 20.0, 40.0)
        bound = release_check.SURVIVORS + release_check.split_bound("durable", spec.execution.dt)
        assert abs(route1 - exact) <= bound * exact and hold[1] == 0.0
        return
    t = sorted(float(k) * spec.execution.dt for k in states)
    if at == "edge":
        released = [float(states[k].poly_hold_released_fmol[0, 0, 0]) / polymerisation.COPY_FMOL
                    for k in sorted(states)]  # fmt: skip
        k_d = float(worlds.sheet.RELEASE["k_durable"])
        fine = cohort.known_rate(t, released, k_d, 0.0, 20.0, 40.0)
        coarse = cohort.known_rate(t[::2], released[::2], k_d, 0.0, 20.0, 40.0)
        split = release_check.split_bound("durable", spec.execution.dt)
        bound = abs(fine - coarse) + (split + release_check.SHARES) * fine
        assert abs(route1 - fine) <= bound
        species = kernel.run(_labelled(at, k_I, edge=True, chain=None))
        assert _cohort_copies(species[0], species[1], species[2][20]) - fine > bound
        return
    made = [float(states[k].poly_released_fmol[0]) for k in sorted(states)]
    rate = 1.0 / float(worlds.sheet.RELEASE["tau"])
    marked, until = (2, 40.0) if at == "producer" else (1, 20.0)
    fine = cohort.known_rate(t, made, rate, 0.0, until, 40.0)
    coarse = cohort.known_rate(t[::2], made[::2], rate, 0.0, until, 40.0)
    held = float(end.poly_hold_fmol[0, 0] * hold[marked])
    assert held > 0 and abs(held - fine) <= abs(fine - coarse) + release_check.SURVIVORS * fine
    assert shares[0, marked] > 0 and shares[1, marked] > 0  # Carried into both fate rows.
    assert at != "producer" or hold[1] == 0.0  # The window's cohort took no completion.


def _node_G(state, p, spec):
    """(G at the export's node from its rows alone, pJ, as a Decimal; its terms' magnitude)."""
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    species, slot = list(spec.model.species_ids), [c.id for c in spec.model.extracellular]
    k = slot.index(worlds.SPACE)
    volume = spec.model.extracellular[k].volume_pL
    amounts = {
        s.id: float(p.extracellular_amount_reference[species.index(s.id), k]
                    + state.extracellular_amount_increment[species.index(s.id), k])
        for s in block.species
    }  # fmt: skip
    mu = dict(zip([s.id for s in block.species], block.mu_RT, strict=True))
    residue = {c.id: mu[c.product] / c.residues for c in block.chains}
    g = engine_run.free_energy(amounts, dict.fromkeys(residue, 0.0), mu, residue, volume,
                               block.c0_mM)  # fmt: skip
    rt = 1e-3 * 8.314462618 * spec.model.temperature_K
    size = sum(abs(n) * rt * (abs(mu[r]) + abs(np.log(n / volume / block.c0_mM)) + 1)
               for r, n in amounts.items())  # fmt: skip
    return g, size


@pytest.mark.parametrize("labelled", [False, True])
def test_the_export_books_both_sides_and_carries_its_labels(labelled, tmp_path):
    """FR-38's amendment T (§9.17; erratum H, §9.21), NumPy, no world compiled, about 2 s unlabelled
    and 7 s labelled (its unlabelled twin and the series readout; the timed lane, 23 November
    2026): R1 at p = 0.75 with the export of R into a finite node (k_E = 1e-3 /s, driven by NTP)
    and R's loss there, 600 s.
    - The node's heat is booked at the node: its outside degradation's, every increment >= 0. The
      export's whole heat is the cell's. Each side's routes sum to its booked heat.
    - G's identity over the cell and the node within rounding (64 eps (size + bookings)): the
      energy ledger, which books both sides' standard terms and heat against @3's chemical terms,
      closes. engine_run's export closes it too, its G over the cell and the node's written rows
      and its heat over both. Planted, the cell's G and heat alone miss it by about 1e7 bounds.
    - The producer's identity with its net export, and the node's balance: n_o - n_o(0) = forward
      - backward - its loss, within rounding; engine_run reads the node's row and counters by ID.
      cohort.read refuses the exported row: one pool's reading omits its export.
    - With labels: every physical field is the unlabelled run's bit for bit, and the cohort marked
      on transcription's own schedule rides into the node, whose shares sum to 1. There route 1,
      the node's row times the cohort's share, meets route 2, two pools in series on the run's own
      counters (cohort.series; §9.17.5's second readout as erratum H reads it), within route 2's
      grid error plus the share update's split."""
    raw = worlds.with_export(kernel.truncated(worlds.r1(0.75), 600.0), k_E=1e-3)
    if labelled:
        raw = worlds.with_share_labels(raw, window=(0.0, 300.0), chain="tx")
    spec, layout, states, increments = kernel.run(raw, record=True)
    start, end = states[0], states[max(states)]
    node_heat = float(end.poly_outside_dissipated_energy_pJ[0])
    assert node_heat > 0 and node_heat == pytest.approx(
        float(end.poly_outside_degradation_heat_pJ[0]), rel=1e-12
    )
    cell_heat = float(np.sum(end.poly_dissipated_energy_pJ))
    routes = sum(float(np.sum(getattr(end, k))) for k in (
        "poly_chain_heat_pJ", "poly_degradation_heat_pJ", "poly_release_heat_pJ",
        "poly_export_heat_pJ"))  # fmt: skip
    bookings = float(np.sum(end.poly_energy_magnitude_pJ)) + float(
        np.sum(end.poly_outside_energy_magnitude_pJ)
    )
    assert abs(routes - cell_heat) <= 64 * EPS * bookings and float(end.poly_export_heat_pJ[0]) > 0
    (g1, size1), (g0, size0) = _G(end, layout, spec), _G(start, layout, spec)
    (o1, nsize1), (o0, nsize0) = _node_G(end, layout, spec), _node_G(start, layout, spec)
    total = float((g1 - g0) + (o1 - o0)) + cell_heat + node_heat
    bound = 64 * EPS * (size0 + size1 + nsize0 + nsize1 + bookings)
    assert abs(total) <= bound
    assert min(float(np.min(x)) for x in increments) >= 0.0
    times, values, checks = engine_run.readouts(spec, states)  # Amendment T's export.
    assert checks["exported_nodes"] == [worlds.SPACE] and checks["G_identity_largest_pJ"] <= bound
    assert checks["routes_minus_total_largest_pJ"] <= 64 * EPS * bookings
    assert min(checks["smallest_class_increment"][k] for k in ("H_exp", "H_odeg")) > 0
    assert abs(float(g1 - g0) + cell_heat) > 1e3 * bound  # Planted: the node's terms omitted.
    species, k = list(spec.model.species_ids), [c.id for c in spec.model.extracellular]
    i, o = species.index("R"), k.index(worlds.SPACE)

    def cell(s, row):
        return float(layout.amount_reference[species.index(row), 0]
                     + s.amount_increment[species.index(row), 0])  # fmt: skip

    reference = float(layout.extracellular_amount_reference[i, o])
    node = [reference + float(s.extracellular_amount_increment[i, o]) for s in (start, end)]
    net = float(end.poly_export_forward_fmol[0] - end.poly_export_backward_fmol[0])
    lost = float(end.poly_outside_degraded_fmol[0])
    assert net > 0 and abs(node[1] - node[0] - net + lost) <= _identity_bound(*node, net, lost)
    at = worlds.SPACE
    assert values[f"n_R_{at}"][-1] == node[1] and values[f"int_D_route_deg_R_{at}"][-1] == lost
    assert values["int_E_export_R_forward"][-1] - values["int_E_export_R_backward"][-1] == net
    path = tmp_path / "run.json"
    record = dict(t=times, readouts=values, cell=checks["exported_cell"], definition=raw)
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="leaves by export export_R"):
        cohort.read(path, "R")
    H0, H = float(start.poly_hold_fmol[0, 0]), float(end.poly_hold_fmol[0, 0])
    A = float(end.poly_released_fmol[0])
    kept = sum(cell(end, r) - cell(start, r) + float(end.poly_degraded_fmol[f])
               for f, r in enumerate(("R", "R_s")))  # fmt: skip
    assert abs(H0 + A - H - kept - net) <= _identity_bound(H0, A, H, kept, net)
    if not labelled:
        return
    plain = kernel.run(worlds.with_export(kernel.truncated(worlds.r1(0.75), 600.0), k_E=1e-3))
    plain = plain[2][max(plain[2])]
    for name in type(plain)._fields:
        assert np.array_equal(getattr(end, name), getattr(plain, name)), name
    shares = end.label_outside_share[0, :, o]  # R's labels at the node: [base, cohort].
    assert shares[1] > 0 and abs(float(np.sum(shares)) - 1.0) <= 128 * EPS
    assert values[f"label_R_cohort_{at}"][-1] == node[1] * float(shares[1])  # engine_run's.
    # §9.17.5's second readout (erratum H, item 2): the cohort at the node by route 1, the node's
    # row times its share, and route 2, two pools in series from the run's own counters.
    steps = sorted(states)
    t = [float(k) * spec.execution.dt for k in steps]

    def series_of(name, index=(0,)):
        return [float(getattr(states[k], name)[index]) for k in steps]

    rows = dict(
        Q=series_of("poly_hold_released_fmol", (0, 0, 0)),
        forward=series_of("poly_export_forward_fmol"),
        backward=series_of("poly_export_backward_fmol"),
        n_c=[cell(states[k], "R") for k in steps],
        n_o=[reference + float(states[k].extracellular_amount_increment[i, o]) for k in steps],
    )
    k_d = float(worlds.sheet.RELEASE["k_durable"])
    args = (t, rows["Q"], k_d, rows["forward"], rows["n_c"], rows["backward"], rows["n_o"])
    route2 = cohort.series(*args, worlds.OUTSIDE_RATE, 0.0, 300.0, t[-1])[1]
    error = cohort.series_error(*args, worlds.OUTSIDE_RATE, 0.0, 300.0, t[-1])
    route1 = node[1] * float(shares[1])
    split = release_check.split_bound("durable", spec.execution.dt)
    assert error is not None and abs(route1 - route2) <= error + (split + 128 * EPS) * route2


def _two_producers(seconds=600.0):
    """§9.17.5's two-producer row: R1 at p = 0.75 with A1's k_I in cell_0 and a copy of its gene
    unit in cell_1 (tx_1, its release and its own fate rows R and R_s, one producer per fate row at
    its cell), each exporting R into one finite node (worlds.with_export), where one outside
    degradation acts; FR-42's labels on R and R_s, each chain declared their producer (amendment G),
    so the owner derives cell_0-g0-tx and cell_1-g0-tx_1. Outputs every 20 s."""
    raw = kernel.truncated(worlds.r1(0.75, initiation=K_I), seconds)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["cells"].append(dict(copy.deepcopy(m["cells"][0]), id="cell_1"))
    m["membranes"].append(dict(copy.deepcopy(m["membranes"][0]), id="patch_1", inside="cell_1"))
    e["membrane_controls"].append(dict(e["membrane_controls"][0], membrane_id="patch_1"))
    x.update(capacity=2, membrane_capacity=2)
    block = kernel.block(raw)
    block["pools"].append(dict(block["pools"][0], id="pol_1", cell="cell_1"))
    chain = copy.deepcopy(block["chains"][0])
    chain.update(id="tx_1", pool="pol_1")
    chain["release"]["id"] = "tx_release_1"
    block["chains"].append(chain)
    block["degradations"] += [
        dict(d, id=f"{d['id']}_1", cell="cell_1") for d in block["degradations"]
    ]
    controls = e["polymerisation_controls"]
    controls += [dict(c, route_id=f"{c['route_id']}_1") for c in list(controls)]
    raw = worlds.with_export(worlds.with_export(raw), cell="cell_1", ident="R_1", outside=False)
    producers = [dict(source=c, windows=[]) for c in ("tx", "tx_1")]
    raw["model"]["operators"].append(
        dict(law=worlds.SHARE_LABELS, species=[
            dict(id=r, labels=["base"], initial=[], producers=producers) for r in ("R", "R_s")
        ])
    )  # fmt: skip
    raw["experiment"]["label_arrivals"] = [
        dict(species=r, schedule=[dict(time=0.0, label="base")]) for r in ("R", "R_s")
    ]  # The species' own; the producers' are derived.
    raw["experiment"]["observation_times"] = [float(t) for t in range(0, int(seconds) + 1, 20)]
    return raw


def test_two_producers_share_one_node_row_by_label():
    """§9.17.5's first readout with two producers into one node (the lead's review; amendment G's
    derived labels; erratum H), NumPy, no world compiled, about 6 s: each producer's RNA at the
    node by route 1, the node's R times the producer's share there, and by route 2, its net exports
    carried at the outside degradation's gross k_o (cohort.known_rate on the outputs every 20 s).
    Route 2 counts every exported molecule, the cell's starting trace at the base label among them,
    so it may exceed route 1 by at most that trace's exports, k_E n_R(0) T, besides route 2's grid
    error (every second output) and the node update's split, k_o h^2/(12 tau). The producers' and
    the base's amounts sum to the node's row. engine_run refuses to export either cell: the node
    takes the other's export too, so G over one cell and the node would not close."""
    raw = _two_producers()
    spec, layout, states, _ = kernel.run(raw)
    with pytest.raises(ValueError, match="also takes cell_1's export export_R_1"):
        engine_run.readouts(spec, states, "cell_0")
    end, steps = states[max(states)], sorted(states)
    t = [float(k) * spec.execution.dt for k in steps]
    species, slots = list(spec.model.species_ids), [c.id for c in spec.model.extracellular]
    i, o = species.index("R"), slots.index(worlds.SPACE)
    n_o = float(
        layout.extracellular_amount_reference[i, o] + end.extracellular_amount_increment[i, o]
    )
    shares = end.label_outside_share[0, :, o]  # [base, cell_0-g0-tx, cell_1-g0-tx_1]
    assert abs(float(np.sum(shares)) - 1.0) <= 128 * EPS
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    k_o = worlds.OUTSIDE_RATE
    trace = worlds.EXPORT_RATE * float(layout.amount_reference[i, 0]) * t[-1]
    split = k_o * (spec.execution.dt / 2) ** 2 / (12.0 * float(worlds.sheet.RELEASE["tau"]))
    for e, producer in enumerate(("cell_0-g0-tx", "cell_1-g0-tx_1")):
        assert block.exports[e].cell == f"cell_{e}"
        net = [float(states[k].poly_export_forward_fmol[e] - states[k].poly_export_backward_fmol[e])
               for k in steps]  # fmt: skip
        route1 = n_o * float(shares[1 + e])
        route2 = cohort.known_rate(t, net, k_o, 0.0, t[-1], t[-1])
        grid = abs(route2 - cohort.known_rate(t[::2], net[::2], k_o, 0.0, t[-1], t[-1]))
        slack = grid + (split + 128 * EPS) * route2
        assert route1 > 0 and -slack <= route2 - route1 <= trace + slack, (producer, route1, route2)


# FR-42's one-way moves (D289, D296): (world, its labelled rows, the hold's marking, seconds).
MOVES = [
    ("pol T=5", ("R", "N", "M", "ATP"), None, 30.0),
    ("R1 held", ("R", "R_s", "M"), "release", 60.0),
    ("R1 held", ("M", "R_s", "R"), "completion", 60.0),
]


@pytest.mark.parametrize(("world", "labelled", "at", "seconds"), MOVES)
def test_the_one_way_moves_close_each_labelled_row(world, labelled, at, seconds):
    """FR-42 (D289, D296), about 0.3 s a row, no world compiled: with labels the half-step's state
    is bit for bit the unlabelled call's, and its moves are non-negative, with no transfers, and
    close each labelled row and cell and each hold: n1 - n0 = sum into - out + carried in - carried
    out. Window material joins label 1 of 3; a chain's material its source label, here 2.
    - pol T=5 moves rows by draws, completions (at the source label), both degradation
      directions (R's re-synthesis among them) and both transfer directions.
    - R1 with A1's k_I: arrivals into the hold, at the base where the release marks its labels and
      at the source label at completion; fate releases into the rows at the source label, or
      carried from the hold where it marks them at completion, never also into the row."""
    if world == "pol T=5":
        raw = kernel.truncated(worlds.world(world), seconds)
    else:
        raw = kernel.truncated(worlds.r1(0.75, machine="held", initiation=K_I), seconds)
        if at == "completion":
            _release(raw)["label"] = dict(at="completion")
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    state = type(state)(*(np.asarray(v) for v in state))
    (block,) = [d for d in spec.model.operators if d.law == worlds.POLYMERISATION]
    control = kernel.controls(raw, block)
    rows = np.array([list(spec.model.species_ids).index(r) for r in labelled])
    m, nodes = len(rows), layout.active.shape[0] + layout.outside_active.shape[0]
    arrival = np.zeros((m, 3))
    arrival[:, 1] = 1.0  # The window names label 1 of 3.
    source = np.zeros((len(block.chains) + 1, 3))  # Padded past the chains, as the owner's.
    source[:, 2] = 1.0
    reference = np.asarray(layout.amount_reference)[rows]
    h = spec.execution.dt / 2
    regrown = carried = 0.0
    for _ in range(int(round(seconds / h))):
        plain, ok = kernel.OP.half_step(state, h, control, layout, xp=np)
        new, ok2, (out, into, transfers, pools) = kernel.OP.half_step(
            state, h, control, layout, xp=np, labels=(rows, arrival, source)
        )
        assert bool(ok) and bool(ok2) and transfers == ()
        assert all(np.array_equal(a, b) for a, b in zip(plain, new, strict=True))
        n0p, n1p, intop, outp, (amount, origin, destination) = pools
        assert np.all(out >= 0) and np.all(into >= 0) and np.all(into[:, 0] == 0)
        assert np.all(intop >= 0) and np.all(outp >= 0) and np.all(amount >= 0)
        sites = np.zeros(m * nodes + len(n0p))  # Carried in minus out, by site.
        np.add.at(sites, destination, amount)
        np.add.at(sites, origin, -amount)
        moved = sites[: m * nodes].reshape(m, nodes)[:, : into.shape[2]]
        n0 = reference + state.amount_increment[rows]
        n1 = reference + new.amount_increment[rows]
        gap = np.abs((n1 - n0) - (np.sum(into, axis=1) - out + moved))
        scale = np.maximum.reduce([np.abs(n1), out, np.sum(into, axis=1), np.abs(moved)])
        assert np.all(gap <= 64 * EPS * scale + 1e-30)
        if len(n0p):
            held = np.abs((n1p - n0p) - (np.sum(intop, axis=1) - outp + sites[m * nodes :]))
            assert np.all(held <= 64 * EPS * np.maximum(n0p, n1p) + 1e-30)
            assert np.all(np.sum(intop, axis=1) == intop[:, 2 if at == "completion" else 0])
            fates = into[[labelled.index("R"), labelled.index("R_s")], 2]  # At the source label.
            assert (at == "completion") == (np.all(fates == 0) and np.sum(amount) > 0)
        regrown += float(into[0, 2, 0]) if world == "pol T=5" else 0.0
        carried += float(np.sum(amount))
        state = new
    assert world != "pol T=5" or regrown > 0  # R's chain-sourced gains: its completions.
    assert (at == "completion") == (carried > 0)
