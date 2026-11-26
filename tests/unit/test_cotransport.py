"""The two electroneutral symports on the cycle kind against the 80-digit reference of their
manufactured rate: cells.cycle.na_k_2anion_symport_reversible_tanh@1 and, bound to potassium and one monovalent
anion, cells.cycle.electroneutral_symport_reversible_tanh@1.

The reference (validation/transport/cotransport_reference.py) is scalar 80-digit decimals with no
Cells import, and the protocol (cotransport_protocol.json) holds its tolerances and the named
stoichiometries: both were the older kernel's, whose equation the two laws keep. Each case is the
kind's own evaluation, in NumPy, on the bare closed world of test_cycle_kind.py; nothing compiles.
The rate equation's 60-digit rows, with their planted laws, are in that file.
"""

import copy
import functools
import json
import math
from pathlib import Path

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.kinds import transporter
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from tests.unit import test_cycle_kind as core
from tests.unit import test_transporter_kind as tk
from validation.transport import cotransport_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/transport/cotransport_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]
SPECIES = ("Na", "K", "M")  # The world's monovalent anion M stands for the protocol's Cl.
NU = {  # The protocol's stoichiometries, in SPECIES's order.
    name: tuple(counts.get("Cl" if s == "M" else s, 0) for s in SPECIES)
    for name, counts in PROTOCOL["named_laws"].items()
}


def symport(name, capacity=2.0, population="symport_0", n_end="a"):
    """The population of a named stoichiometry: the configured symport without sodium, the symport
    of Na, K and two anions with it."""
    if NU[name][0] == 0:
        salts = ("K", "M", *NU[name][1:])
        return core.salt_case(salts, capacity, population, n_end=n_end).entry
    return core.nkcc_case(capacity, population, n_end=n_end).entry


class World:
    """The bare closed world with populations, as an evaluation at given concentrations. Its
    layout's reference amounts are zero, so a state holds a concentration of any size."""

    def __init__(self, *entries, temperature=298.15, turned=False):
        raw = core.core_world(*entries)
        raw["model"]["temperature_K"] = temperature
        if turned:
            raw["model"]["species"].reverse()
        with tk.scoped():
            self.spec, self.impl, state, p, self.control = core.na_ca_start(raw)
        fields = ("amount_reference", "extracellular_amount_reference")
        self.p = p._replace(**{f: np.zeros_like(getattr(p, f)) for f in fields})
        self.ids = list(self.spec.model.species_ids)
        self.start = state._replace(
            amount_increment=p.amount_reference + state.amount_increment,
            extracellular_amount_increment=p.extracellular_amount_reference
            + state.extracellular_amount_increment,
        )

    def at(self, ci, co):
        """The state with SPECIES at ci in the cell and co in the bath (mM)."""
        inside = self.start.amount_increment.copy()
        outside = self.start.extracellular_amount_increment.copy()
        for s, a, b in zip(SPECIES, ci, co, strict=True):
            inside[self.ids.index(s), 0] = a * self.p.volume[0]
            outside[self.ids.index(s), 0] = b * self.p.extracellular_volume[0]
        return self.start._replace(amount_increment=inside, extracellular_amount_increment=outside)

    def opened(self, *availability):
        return self.control._replace(cycle_availability=np.array(availability))

    def evaluate(self, state, control=None):
        potentials = np.array([-0.03, 0.0])  # A symport reads no voltage.
        control = self.control if control is None else control
        with np.errstate(all="ignore"):
            return (
                transporter._evaluate(state, potentials, control, self.p, xp=np),
                transporter.rates(state, potentials, control, self.p, xp=np),
            )


@functools.cache
def lone(name, capacity=2.0, temperature=298.15):
    """The world of one named symport."""
    return World(symport(name, capacity), temperature=temperature)


def close(actual, expected, key):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


@pytest.mark.parametrize("name", NU)
@pytest.mark.parametrize("turned", [False, True], ids=("as given", "turned"))
def test_named_roles_bind_their_species_and_move_the_protocols_counts_and_no_charge(name, turned):
    """Whatever the order of the species rows: the counts are the protocol's, in at the cell and out
    at the bath, every other species moves by none, the cycles are the same, and charge is neither
    created nor moved."""
    world = World(symport(name), turned=True) if turned else lone(name)
    with tk.scoped():
        (check,) = transporter.cycle_checks(world.spec)
    assert (check.charge_sum, check.charge_moved, check.admitted) == (0, 0, True)
    ends = ([12.0, 140.0, 10.0], [145.0, 4.0, 120.0])
    e, rates = world.evaluate(world.at(*ends))
    as_given, _ = lone(name).evaluate(lone(name).at(*ends))
    close(e.j, as_given.j, "rate_atol_fmol_s")
    j, expected = float(e.j[0, 0]), dict(zip(SPECIES, NU[name], strict=True))
    for k, s in enumerate(world.ids):
        count = expected.get(s, 0)
        assert float(rates.cell[k, 0]) == pytest.approx(count * j, rel=1e-15, abs=0)
        assert float(rates.outside[k, 0]) == pytest.approx(-count * j, rel=1e-15, abs=0)


@pytest.mark.parametrize(
    "name,over,reason",
    [
        ("nkcc", dict(law="tests.cycle.unknown@1"), "law is one of"),
        ("nkcc", dict(roles=dict(Na="K", K="K", anion="M")), "a distinct species row"),
        ("nkcc", dict(roles=dict(Na="Na", K="K")), "roles binds each of Na, K, anion"),
        ("nkcc", dict(roles=dict(Na="Na", K="Cs", anion="M")), "a distinct species row"),
        ("nkcc", dict(roles=dict(Na="Ca", K="K", anion="M")), r"role Na has valence \+1"),
        ("nkcc", dict(roles=dict(Na="Na", K="K", anion="S")), "role anion has valence -1"),
        ("kcc", dict(roles=dict(cation="K", anion="K")), "a distinct species row"),
        ("kcc", dict(roles=dict(cation="K")), "roles binds each of cation, anion"),
        ("kcc", dict(roles=dict(cation="K", anion="Na")), "is electroneutral; 1 K and 1 Na move"),
        ("kcc", dict(roles=dict(cation="Ca", anion="M")), "is electroneutral; 1 Ca and 1 M move"),
    ],
)
def test_wrong_roles_species_and_valences_are_refused(name, over, reason):
    (full,) = (n for n in NU if n.startswith(name))
    with tk.scoped(), pytest.raises(ConfigError, match=reason):
        parse_spec(core.core_world(symport(full) | over))


CASES = {
    "physiological gradient": ([12.0, 140.0, 10.0], [145.0, 4.0, 120.0], 298.15, 2.0, 0.8),
    "reverse gradient": ([145.0, 4.0, 120.0], [12.0, 140.0, 10.0], 310.0, 2.0, 0.8),
    "stall": ([4.0, 8.0, 16.0], [4.0, 8.0, 16.0], 298.15, 2.0, 1.0),
    "near stall": ([4.0, 8.0, 16.0], [4.0, 8.0000000008, 16.0], 298.15, 2.0, 1.0),
    "lower temperature": ([2.0, 4.0, 8.0], [8.0, 16.0, 32.0], 200.0, 2.0, 1.0),
    "upper temperature": ([2.0, 4.0, 8.0], [8.0, 16.0, 32.0], 400.0, 2.0, 1.0),
    "blocked": ([12.0, 140.0, 10.0], [145.0, 4.0, 120.0], 298.15, 2.0, 0.0),
    "zero capacity": ([12.0, 140.0, 10.0], [145.0, 4.0, 120.0], 298.15, 0.0, 1.0),
    "extreme": ([1e-300] * 3, [1e300] * 3, 298.15, 2.0, 1.0),
}


@pytest.mark.parametrize("name", NU)
@pytest.mark.parametrize("case", CASES)
def test_the_80_digit_rates_at_stall_forward_backward_and_the_far_domain(name, case):
    """The cycles, the affinity (-RT x), each species' transport and the heat are the reference's to
    the protocol's tolerances; the heat is never negative, no charge moves and nothing works. The
    domain admits each case, the far one-sided one among them. Planted: the cycles of a gradient of
    potassium larger by 0.1% are told apart at the two gradients."""
    ci, co, temperature, capacity, opening = CASES[case]
    world = lone(name, capacity, temperature)
    state, control = world.at(ci, co), world.opened(opening)
    e, rates = world.evaluate(state, control)
    expected = reference.cycle(ci, co, NU[name], capacity, opening, temperature)
    assert bool(e.valid[0])
    affinity = -R * temperature * float(e.x[0, 0])
    close(e.j[0, 0], expected["cycle_fmol_s"], "rate_atol_fmol_s")
    close(affinity, expected["affinity_J_mol"], "affinity_atol_J_mol")
    rows = [world.ids.index(s) for s in SPECIES]
    close(rates.cell[rows, 0], expected["transported_fmol_s"], "rate_atol_fmol_s")
    close(rates.heat_pJ_s[0], expected["dissipated_power_pJ_s"], "power_atol_pJ_s")
    assert float(rates.heat_pJ_s[0]) >= 0 and float(rates.work_pJ_s[0]) == 0
    assert np.all(e.d_j_d_psi == 0)  # No voltage term, so no charge slope.
    if case == "physiological gradient":
        assert np.sign(e.j[0, 0]) == (1 if NU[name][0] else -1)  # NKCC takes salt in, KCC out.
    if case == "stall":
        assert e.j[0, 0] == 0 == affinity
    if case in ("physiological gradient", "reverse gradient"):
        steeper = world.at(ci, [co[0], co[1] * 1.001, co[2]])
        off = float(world.evaluate(steeper, control)[0].j[0, 0])
        assert abs(off - expected["cycle_fmol_s"]) > 1e-5 * abs(expected["cycle_fmol_s"])


@pytest.mark.parametrize("name", NU)
def test_unequal_concentrations_with_equal_products_stall(name):
    ci = [4.0, 8.0, 4.0]
    co = [8.0, 4.0, 4.0] if NU[name][0] else [4.0, 4.0, 8.0]  # KCC reads no sodium.
    world = lone(name)
    e, _ = world.evaluate(world.at(ci, co))
    close(-R * 298.15 * e.x[0, 0], 0, "affinity_atol_J_mol")
    close(e.j[0, 0], 0, "rate_atol_fmol_s")


def test_shared_owners_take_every_route_once_each_way_and_alone():
    """Three routes on one patch, one with its N at the bath: the two owners' rates are the signed
    owner loops' of the reference at the routes' cycles, the species' totals and the charge are
    unchanged, and closing one route leaves the others' cycles bit for bit and no state moved."""
    kcc, nkcc = sorted(NU, key=lambda n: NU[n][0])
    entries = (
        symport(kcc, 2.0, "r0"), symport(nkcc, 3.0, "r1"), symport(kcc, 0.5, "r2", n_end="b")
    )  # fmt: skip
    world = World(*entries)
    state = world.at([12.0, 145.0, 30.0], [140.0, 4.0, 20.0])
    before = copy.deepcopy(state)
    e, rates = world.evaluate(state, world.opened(0.8, 0.6, 0.9))
    counts = list(zip(*(NU[n] for n in (kcc, nkcc, kcc)), strict=True))
    expected = np.array(
        reference.exchange([float(v) for v in e.j[0]], [0, 0, 1], [1, 1, 0], counts, 2)
    )
    rows = [world.ids.index(s) for s in SPECIES]
    amounts = np.stack((rates.cell[:, 0], rates.outside[:, 0]), axis=-1)
    close(amounts[rows], expected, "rate_atol_fmol_s")
    close(amounts.sum(axis=-1), 0, "rate_atol_fmol_s")
    close(np.array(world.spec.model.valence) @ amounts, 0, "rate_atol_fmol_s")
    closed, _ = world.evaluate(state, world.opened(0.8, 0.0, 0.9))
    assert closed.j[0, 1] == 0 and e.j[0, 1] != 0
    assert np.array_equal(closed.j[0, [0, 2]], e.j[0, [0, 2]])
    assert all(np.array_equal(a, b) for a, b in zip(before, state, strict=True))


@pytest.mark.parametrize("name", NU)
def test_the_finite_chemical_free_energy_derivative_is_minus_the_heat(name):
    """Over 1e-4 of the fastest amount's time the 80-digit ideal free energy changes by minus the
    heat, within the difference's own third-order bound, and no charge moves."""
    ci, co = [12.0, 140.0, 10.0], [145.0, 4.0, 120.0]
    world = lone(name)
    state = world.at(ci, co)
    _, rates = world.evaluate(state, world.opened(0.8))
    rows = [world.ids.index(s) for s in SPECIES]
    derivative = np.stack((rates.cell[rows, 0], rates.outside[rows, 0]), axis=-1)
    volumes = np.array([float(world.p.volume[0]), float(world.p.extracellular_volume[0])])
    n = np.stack((ci, co), axis=-1) * volumes
    h = 1e-4 / np.max(np.abs(derivative) / n)
    minus, plus = n - h * derivative, n + h * derivative
    difference = reference.chemical_free_energy_change(
        minus.tolist(), plus.tolist(), volumes.tolist(), 298.15
    ) / (2 * h)
    third = 1e-3 * R * 298.15 * np.sum(np.abs(derivative) ** 3 / (n - h * np.abs(derivative)) ** 2)
    scale = 1e-3 * R * 298.15 * np.sum(n * (np.abs(np.log(n / volumes / 1000)) + 1))
    bound = h**2 * third / 6 + 32 * np.finfo(float).eps * scale / h
    heat = float(rates.heat_pJ_s[0])
    assert abs(difference + heat) <= bound < 1e-3 * heat
    close(CHARGE_PER_FMOL * np.array([1, 1, -1]) @ derivative, 0, "charge_atol_C")


@pytest.mark.parametrize("name", NU)
def test_the_stall_slope_is_half_the_capacity_times_each_count(name):
    """At equal concentrations dJ/d ln c is -k a nu/2 at the cell and +k a nu/2 at the bath."""
    world = lone(name)
    e, _ = world.evaluate(world.at([10.0] * 3, [10.0] * 3), world.opened(0.8))
    moved = [n for n in NU[name] if n]
    expected = [sign * 0.8 * n for n in moved for sign in (-1.0, 1.0)]  # k a/2 = 0.8.
    close(e.d_j_d_ln_c[0, : 2 * len(moved), 0], expected, "rate_atol_fmol_s")


@pytest.mark.parametrize("bad", [0.0, -1.0, math.nan, math.inf])
@pytest.mark.parametrize("blocking", ["control", "capacity"])
def test_a_bad_substrate_is_outside_the_domain_even_when_the_route_is_blocked(bad, blocking):
    for name in NU:
        world = lone(name, 0.0 if blocking == "capacity" else 2.0)
        control = world.opened(0.0 if blocking == "control" else 1.0)
        good, _ = world.evaluate(world.at([1.0] * 3, [1.0] * 3), control)
        outside, _ = world.evaluate(world.at([1.0] * 3, [1.0, bad, 1.0]), control)
        assert bool(good.valid[0]) and not bool(outside.valid[0])


@pytest.mark.parametrize("capacity", [-1.0, math.inf, math.nan, True])
def test_an_invalid_capacity_is_refused(capacity):
    for name in NU:
        with tk.scoped(), pytest.raises(ConfigError, match="capacity_fmol_s must be"):
            parse_spec(core.core_world(symport(name) | dict(capacity_fmol_s=capacity)))


@pytest.mark.parametrize("temperature", [199.9, 400.1])
def test_a_temperature_outside_the_protocols_domain_is_the_hosts_refusal(temperature):
    """The laws state no temperature domain of their own: their host's is the protocol's."""
    low, high = PROTOCOL["temperature_domain_K"]
    assert not low <= temperature <= high
    with pytest.raises(ConfigError, match="requires 200-400 K"):
        World(symport(next(iter(NU))), temperature=temperature)


def test_the_cycles_replay_every_species_and_a_neutral_corruption_is_refused():
    """Four host steps of both symports: every amount is the cycles times the counts, and a state
    that gained equal potassium and anion, which no charge shows, is refused by its ledger."""
    entries = [symport(name, 20.0, f"r{i}") for i, name in enumerate(NU)]
    raw = core.core_world(*entries)
    with tk.scoped():
        spec, impl, state, p, control = core.na_ca_start(raw)
        states = [state]
        for _ in range(4):
            state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
            assert bool(valid)
            states.append(state)

        def check(last):
            history = impl.STATE_TYPE(*(np.stack(v) for v in zip(*states[:-1], last, strict=True)))
            impl.check_values(history, spec, steps=np.arange(len(states)))

        check(state)
        corrupt = state.amount_increment.copy()
        corrupt[[list(spec.model.species_ids).index(s) for s in ("K", "M")], 0] += 0.03
        with pytest.raises(NumericalError, match="accounting failed"):
            check(state._replace(amount_increment=corrupt))
    cycles = np.asarray(state.cycle_count[0])
    assert np.all(cycles != 0)
    for k, s in enumerate(SPECIES):
        row = list(spec.model.species_ids).index(s)
        moved = math.fsum(NU[name][k] * c for name, c in zip(NU, cycles, strict=True))
        close(state.amount_increment[row, 0], moved, "material_atol_fmol")
        close(state.extracellular_amount_increment[row, 0], -moved, "material_atol_fmol")
