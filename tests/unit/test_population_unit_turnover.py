"""cells.operator.population_unit_turnover@1, FR-7's unit producer (F1): host rows, and one compiled world.

Host (NumPy, no compile), on the bound pump-free cell (unit_turnover_fixtures.leak_cell):
* the half-step against an independent 50-digit matrix exponential of the chain with its sinks
  (Decimal Taylor series, written here; never the engine's uniformization), at O(1) fractions:
  0, 1 and 3 pools, distinct and confluent rates, declared and written units, two routes sharing
  one precursor;
* the account: the precursor's move, the units written and every booking, exactly as booked;
* the booked work against the exact free-energy change written out independently (Decimal);
* zero rates select the start state bitwise, and untouched rows stay bitwise;
* plants, each caught by the row that must catch it: ν off by one, the 1e-15 dropped, a pool
  skipped, removal of the written units only, and a moved amount booked twice;
* the definition's refusals, one row each, and turnover's supply admitted (two writers of one row,
  the lead's ruling of 19 November 2026) with @3's bound reading the supply.
Compiled: one window program of 30 steps at 1 ms, a two-pool route on kir_0, with turnover's supply
off until 15 ms and on after it, serves every run:
* every row passes the runner's host checks;
* before the supply, the chain matches the exact solution at every step (the half-steps compose
  exactly across @3's steps, which move neither the precursor nor the units);
* the account holds on every row;
* runs resumed before and after the supply's change are bitwise the uninterrupted run's.
"""

from decimal import Decimal, getcontext
from types import SimpleNamespace
from typing import NamedTuple

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.models import pump_composite
from cells.operators import membrane_state
from cells.operators import population_unit_turnover as put
from cells.operators import species_regulated_availability as sra
from cells.operators.contract import Operator
from cells.registry import species_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from validation.fr7 import unit_turnover_fixtures as fx

getcontext().prec = 50
R_SI = Decimal("6.02214076e23") * Decimal("1.380649e-23")  # N_A k_B, exact (SI 2019).
H = 0.5  # s: a long half-step, so the fractions moved are O(1) (every Λ h <= 0.5 here).


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


# ------------------------------------------------------------------ the independent reference


def expm_apply(matrix, vector, h):
    """exp(matrix h) vector in Decimal, by its Taylor series (every |matrix h| entry <= 1 here)."""
    size = len(vector)
    term = list(vector)
    total = list(term)
    for k in range(1, 400):
        term = [sum(matrix[i][j] * term[j] for j in range(size)) * h / k for i in range(size)]
        total = [a + b for a, b in zip(total, term, strict=True)]
        if max(abs(t) for t in term) <= Decimal("1e-60") * max(abs(t) for t in total):
            return total
    raise AssertionError("the series did not converge")


def reference(n0, routes, h):
    """The chain with its sinks, exactly: n0 the precursor (fmol); routes, each (a, c_u, kappa,
    pools0 [units], N0 [units], r). Returns (n, [(consumed fmol, pools, N, removed), ...])."""
    d = Decimal
    total_a = sum(d(a) for a, *_ in routes)
    names = ["n"]
    for i, (_, _, _, pools0, _, _) in enumerate(routes):
        names += [f"C{i}", *(f"M{i}_{j}" for j in range(len(pools0))), f"N{i}", f"R{i}"]
    index = {k: j for j, k in enumerate(names)}
    size = len(names)
    m = [[d(0)] * size for _ in range(size)]
    x = [d(0)] * size
    x[index["n"]] = d(n0)
    m[index["n"]][index["n"]] = -total_a
    for i, (a, c, kappa, pools0, big_n0, r) in enumerate(routes):
        a, c, kappa, r = d(a), d(c), d(kappa), d(r)
        m[index[f"C{i}"]][index["n"]] += a
        chain = [*(f"M{i}_{j}" for j in range(len(pools0))), f"N{i}"]
        m[index[chain[0]]][index["n"]] += c * a
        for j in range(len(pools0)):
            here, there = index[chain[j]], index[chain[j + 1]]
            m[here][here] -= kappa
            m[there][here] += kappa
            x[here] = d(pools0[j])
        n_index = index[f"N{i}"]
        m[n_index][n_index] -= r
        m[index[f"R{i}"]][n_index] += r
        x[n_index] = d(big_n0)
    y = expm_apply(m, x, d(h))
    out = []
    for i, (_, _, _, pools0, _, _) in enumerate(routes):
        out.append(
            (
                y[index[f"C{i}"]],
                [y[index[f"M{i}_{j}"]] for j in range(len(pools0))],
                y[index[f"N{i}"]],
                y[index[f"R{i}"]],
            )
        )
    return y[index["n"]], out


# ------------------------------------------------------------------ host worlds


def definition(routes, controls, **kwargs):
    return fx.with_producer(fx.cell(**kwargs), routes, controls)


def bound(routes, controls, **kwargs):
    spec = parse_spec(definition(routes, controls, **kwargs))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == put.LAW_ID)
    return spec, model, op, state, p


def step(op, state, p, assembly, removal, h=H):
    control = SimpleNamespace(
        unit_assembly_rate=np.asarray(assembly, dtype=float),
        unit_removal_rate=np.asarray(removal, dtype=float),
    )
    return op.half_step(state, h, control, p, xp=np)


CASES = {
    # name: (routes [(population, pools, κ)], k_a, k_r, initial pools, written units)
    "direct": ([("kir_0", 0, None)], [0.7], [0.3], [[]], [0.0]),
    "one_pool": ([("kir_0", 1, 0.9)], [0.6], [0.2], [[40.0]], [500.0]),
    "three_pools": ([("kir_0", 3, 0.9)], [0.5], [0.4], [[50.0, 20.0, 10.0]], [-300.0]),
    "confluent": ([("kir_0", 2, 0.8)], [0.8], [0.8], [[30.0, 15.0]], [0.0]),
    "shared": (
        [("kir_0", 1, 0.5), (fx.SECOND, 0, None)],
        [0.4, 0.6],
        [0.3, 0.1],
        [[25.0], []],
        [0, 0],
    ),
}


def case_world(name):
    """The case's world: its initial pools declared (initial_pool_units, bound into the state),
    and its written units planted on membrane state's increment."""
    entries, assembly, removal, pools0, written = CASES[name]
    routes = [
        fx.route(f"r{i}", pop, pools=m, tau=None if m == 0 else m / kappa, initial=pools0[i])
        for i, (pop, m, kappa) in enumerate(entries)
    ]
    controls = {f"r{i}": [(0.0, assembly[i], removal[i])] for i in range(len(entries))}
    spec, model, op, state, p = bound(routes, controls)
    for i, values in enumerate(pools0):
        assert list(np.asarray(state.unit_pool_units)[i, : len(values)]) == values  # Bound.
    increment = np.array(state.population_abundance_increment, dtype=float)
    channels = [c.id for c in spec.model.channels]
    for i, (pop, _, _) in enumerate(entries):
        increment[channels.index(pop)] = written[i]
    state = state._replace(population_abundance_increment=increment)
    return spec, model, op, state, p


def engine_vs_reference(spec, op, state, p, assembly, removal, *, engine_p=None, units=None):
    """The largest relative difference of the half-step's outputs from the reference. The
    reference reads the declared structure (p, the declaration's ν); the engine runs on engine_p
    (a planted layout) when given, and units is the honest units function where it is planted."""
    new, ok = step(op, state, p if engine_p is None else engine_p, assembly, removal)
    assert bool(ok)
    species = list(spec.model.species_ids)
    row, cell = species.index(fx.PRECURSOR), 0
    n0 = float(np.asarray(p.amount_reference)[row, cell] + state.amount_increment[row, cell])
    units_of = units or membrane_state.units
    big_n0 = np.asarray(units_of(state, p, xp=np))
    big_n1 = np.asarray(membrane_state.units(new, p, xp=np))
    channel = np.asarray(p.unit_route_channel)
    present = np.asarray(p.unit_pool_present)
    routes = []
    for i in range(len(assembly)):
        pools0 = [
            float(v) for v, on in zip(state.unit_pool_units[i], present[i], strict=True) if on
        ]
        routes.append(
            (
                float(assembly[i]),
                put.conversion(spec_route(spec, i)),
                float(p.unit_route_maturation_rate[i]),
                pools0,
                float(big_n0[channel[i]]),
                float(removal[i]),
            )
        )
    n_ref, out = reference(n0, routes, H)
    worst = abs(
        Decimal(float(n0 - (new.unit_consumed_fmol - state.unit_consumed_fmol).sum())) - n_ref
    )
    worst /= n_ref
    for i, (consumed, pools, big_n, removed) in enumerate(out):
        got = [
            new.unit_consumed_fmol[i] - state.unit_consumed_fmol[i],
            *[v for v, on in zip(new.unit_pool_units[i], present[i], strict=True) if on],
            big_n1[channel[i]],
            new.unit_removed_units[channel[i]] - state.unit_removed_units[channel[i]],
        ]
        want = [consumed, *pools, big_n, removed]
        for g, w in zip(got, want, strict=True):
            worst = max(worst, abs(Decimal(float(g)) - w) / max(abs(w), Decimal("1e-300")))
    return float(worst), new


def spec_route(spec, i):
    block = next(d for d in spec.model.operators if d.law == put.LAW_ID)
    return block.routes[i]


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_half_step_is_the_exact_chain(name):
    spec, _, op, state, p = case_world(name)
    _, assembly, removal, _, _ = CASES[name]
    worst, _ = engine_vs_reference(spec, op, state, p, assembly, removal)
    assert worst < 1e-13, worst


PLANTS = {
    "nu_off_by_one": lambda p: p._replace(
        unit_route_conversion=np.asarray(p.unit_route_conversion) * 4 / 5
    ),
    "femto_dropped": lambda p: p._replace(
        unit_route_conversion=np.asarray(p.unit_route_conversion) * 1e15
    ),
    "pool_skipped": lambda p: p._replace(
        unit_pool_present=np.array([[True, True, False]]),
        unit_pool_last=np.array([[False, True, False]]),
    ),
}


@pytest.mark.parametrize("plant", sorted(PLANTS))
def test_each_plant_fails_the_exact_chain_row(plant):
    spec, _, op, state, p = case_world("three_pools")
    _, assembly, removal, _, _ = CASES["three_pools"]
    honest, _ = engine_vs_reference(spec, op, state, p, assembly, removal)
    planted, _ = engine_vs_reference(
        spec, op, state, p, assembly, removal, engine_p=PLANTS[plant](p)
    )
    assert honest < 1e-13 and planted > 1e-6, (honest, planted)


def test_removal_of_the_written_units_only_fails_the_exact_chain_row(monkeypatch):
    """Every unit is removed, the declared ones included: a law that removed only the written
    increment is caught (the reference removes from the whole N)."""
    spec, _, op, state, p = case_world("one_pool")
    _, assembly, removal, _, _ = CASES["one_pool"]
    honest, _ = engine_vs_reference(spec, op, state, p, assembly, removal)
    whole = membrane_state.units

    def written_only(s, q, *, xp):
        return xp.where(q.channel_active, s.population_abundance_increment, 0.0)

    monkeypatch.setattr(membrane_state, "units", written_only)
    planted, _ = engine_vs_reference(spec, op, state, p, assembly, removal, units=whole)
    assert honest < 1e-13 and planted > 1e-3, (honest, planted)


def test_the_account_and_the_untouched_rows():
    """The account from the bound start, its declared initial pools included (D232's W5
    ruling)."""
    spec, model, op, state, p = case_world("shared")
    _, assembly, removal, _, _ = CASES["shared"]
    assert float(np.asarray(p.unit_route_initial_units)[0]) == 25.0  # Route r0's one pool.
    new, ok = step(op, state, p, assembly, removal)
    assert bool(ok)
    species = list(spec.model.species_ids)
    row = species.index(fx.PRECURSOR)
    consumed = new.unit_consumed_fmol - state.unit_consumed_fmol
    # The precursor's move is the routes' consumption, applied to its stored increment.
    moved = new.amount_increment[row, 0] - state.amount_increment[row, 0]
    assert moved == pytest.approx(-consumed.sum(), rel=1e-15)
    others = [k for k in range(len(species)) if k != row]
    assert new.amount_increment[others].tobytes() == state.amount_increment[others].tobytes()
    # Membrane state's units change by inserted less removed, booked in the producer's fields.
    net = (new.unit_inserted_units - state.unit_inserted_units) - (
        new.unit_removed_units - state.unit_removed_units
    )
    change = new.population_abundance_increment - state.population_abundance_increment
    np.testing.assert_allclose(change, net, rtol=1e-15, atol=0)
    # The two ledgers of the account, and membrane state's and @3's, close at rounding.
    ledgers = model.balances(new, p)
    bounds = op.own_bounds(op.own_magnitudes(new, p, xp=np), 1)
    for name, bound_ in zip(put.LEDGERS, bounds, strict=True):
        assert np.all(np.abs(ledgers[name]) <= bound_), name
    assert np.all(np.abs(ledgers["population_abundance_entity"]) <= 1e-9)
    assert np.all(np.abs(ledgers["local"][row]) <= 1e-20)


def test_an_initial_pool_missing_from_the_account_fails_the_chain_ledger():
    """The plant leaves the declared initial units in transit out of the account (D232's W5
    ruling): the chain ledger is off by them."""
    spec, model, op, state, p = case_world("shared")
    _, assembly, removal, _, _ = CASES["shared"]
    p = p._replace(unit_route_initial_units=np.zeros_like(p.unit_route_initial_units))
    new, _ = step(op, state, p, assembly, removal)
    ledgers = model.balances(new, p)
    bound_ = op.own_bounds(op.own_magnitudes(new, p, xp=np), 1)[0]
    assert np.max(np.abs(ledgers["unit_chain"])) > 1e6 * np.max(bound_)


def test_a_moved_amount_booked_twice_fails_the_conversion_ledger():
    spec, model, op, state, p = case_world("one_pool")
    _, assembly, removal, _, _ = CASES["one_pool"]
    new, _ = step(op, state, p, assembly, removal)
    twice = new._replace(unit_consumed_fmol=2 * new.unit_consumed_fmol)
    for row, fails in ((new, False), (twice, True)):
        residual = op.own_ledgers(row, p, xp=np)["unit_conversion"]
        bound_ = op.own_bounds(op.own_magnitudes(row, p, xp=np), 1)[1]
        assert bool(np.any(np.abs(residual) > bound_)) is fails


def test_the_booked_work_is_the_exact_free_energy_change():
    spec, _, op, state, p = case_world("shared")
    _, assembly, removal, _, _ = CASES["shared"]
    new, _ = step(op, state, p, assembly, removal)
    row = list(spec.model.species_ids).index(fx.PRECURSOR)
    n = Decimal(float(np.asarray(p.amount_reference)[row, 0] + state.amount_increment[row, 0]))
    delta = Decimal(float(new.amount_increment[row, 0] - state.amount_increment[row, 0]))
    v, t = Decimal(float(np.asarray(p.volume)[0])), Decimal(float(np.asarray(p.temperature)))

    def g(x):
        return x * ((x / v).ln() - 1)

    exact = Decimal("1e-3") * R_SI * t * (g(n + delta) - g(n))
    booked = Decimal(float(new.unit_turnover_work_pJ[0] - state.unit_turnover_work_pJ[0]))
    assert abs(booked - exact) <= Decimal("1e-12") * abs(exact)
    # In the 1 mM reference convention, taking material out below 1 mM raises G: signed work.
    assert delta < 0 and exact > 0


def test_zero_rates_select_the_start_state_bitwise():
    _, _, op, state, p = case_world("direct")
    new, ok = step(op, state, p, [0.0], [0.0])
    assert bool(ok)
    for a, b in zip(new, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


# ------------------------------------------------------------------ the definition


def base_routes():
    return [fx.route("kir_units", "kir_0", pools=2, tau=0.02)], {"kir_units": [(0.0, 50.0, 20.0)]}


def refused(routes, controls, *, mutate=None, **kwargs):
    raw = definition(routes, controls, **kwargs)
    if mutate is not None:
        mutate(raw)
    with pytest.raises(ConfigError) as error:
        parse_spec(raw)
    return str(error.value)


def _block(raw):
    return next(op for op in raw["model"]["operators"] if op["law"] == put.LAW_ID)


REFUSALS = {
    "unknown population": (
        lambda b: b["routes"][0].update(population="kv_9"),
        "not a channel population",
    ),
    "precursor not listed": (
        lambda b: b["routes"][0].update(precursor="M"),
        "is not a listed species",
    ),
    "nu zero": (lambda b: b["routes"][0].update(molecules_per_unit=0), "is >= 1"),
    "nu not an integer": (lambda b: b["routes"][0].update(molecules_per_unit=2.5), "an integer"),
    "too many pools": (lambda b: b["routes"][0].update(maturation_pools=9), "in [0, 8]"),
    "time without pools": (
        lambda b: b["routes"][0].update(maturation_pools=0),
        "maturation_time_s is null",
    ),
    "pools without time": (
        lambda b: b["routes"][0].update(maturation_time_s=None),
        "maturation_time_s",
    ),
    "population twice": (
        lambda b: b["routes"].append(fx.route("again", "kir_0")),
        "one route per population",
    ),
    "charged precursor": (
        lambda b: b["species"].append(dict(id="Na", catalogue=None, evidence=None)),
        "neutral species only",
    ),
    "unknown key": (lambda b: b["routes"][0].update(stray=1), "stray"),
    "initial pools not a list": (
        lambda b: b["routes"][0].update(initial_pool_units=0.0),
        "initial_pool_units is an explicit list of its 2 maturation pools",
    ),
    "initial pools of the wrong length": (
        lambda b: b["routes"][0].update(initial_pool_units=[1.0]),
        "initial_pool_units is an explicit list of its 2 maturation pools",
    ),
    "a negative initial pool": (
        lambda b: b["routes"][0].update(initial_pool_units=[1.0, -1.0]),
        "initial_pool_units entry must be finite and nonnegative",
    ),
    "initial pools left out": (
        lambda b: b["routes"][0].pop("initial_pool_units"),
        "initial_pool_units",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_each_declaration_refusal(name):
    change, message = REFUSALS[name]
    routes, controls = base_routes()
    text = refused(routes, controls, mutate=lambda raw: change(_block(raw)))
    assert message in text, text


def test_a_listed_species_no_route_consumes_is_refused():
    routes, controls = base_routes()
    raw = add_inventory_species(
        definition(routes, controls),
        "spare",
        trace_mM=fx.TRACE_mM,
        diffusivity_m2_per_s=fx.DIFFUSIVITY,
        floor_fmol=fx.FLOOR_FMOL,
    )
    _block(raw)["species"].append(dict(id="spare", catalogue=None, evidence=None))
    with pytest.raises(ConfigError, match="no route consumes it"):
        parse_spec(raw)


def _controls(raw):
    return raw["experiment"]["unit_turnover_controls"]


SCHEDULE_REFUSALS = {
    "not from zero": (lambda c: c[0]["schedule"][0].update(time=0.002), "starts at 0"),
    "off the grid": (
        lambda c: c[0]["schedule"].append(
            dict(time=0.0105, assembly_rate_per_s=1.0, removal_rate_per_s=1.0)
        ),
        "on the clock's grid",
    ),
    "past the end": (
        lambda c: c[0]["schedule"].append(
            dict(time=0.03, assembly_rate_per_s=1.0, removal_rate_per_s=1.0)
        ),
        "0 < t < end",
    ),
    "negative rate": (
        lambda c: c[0]["schedule"][0].update(removal_rate_per_s=-1.0),
        "finite rate >= 0",
    ),
    "missing": (lambda c: c.clear(), "needs its schedule"),
    "too fast": (
        lambda c: c[0]["schedule"][0].update(assembly_rate_per_s=2000.0),
        "dt Λ",
    ),
}


@pytest.mark.parametrize("name", sorted(SCHEDULE_REFUSALS))
def test_each_schedule_refusal(name):
    change, message = SCHEDULE_REFUSALS[name]
    routes, controls = base_routes()
    text = refused(routes, controls, mutate=lambda raw: change(_controls(raw)))
    assert message in text, text


def test_membrane_state_is_required():
    routes, controls = base_routes()

    def drop_state(raw):
        raw["model"]["operators"] = [
            op for op in raw["model"]["operators"] if op["law"] != fx.STATE
        ]

    text = refused(routes, controls, mutate=drop_state)
    assert fx.STATE in text, text


class _Stub:
    PROCESS = False  # No in-step process (the species registry's moved_in_step reads it).
    SPLIT = True  # A split part: with an amount write, a split row writer (contract.writes_rows).
    EVENT_REPLACES = {}
    SHARED_ROW_POTENTIAL = False

    def __init__(self, law, *, writes=(), role="user", species=(), moves=None, rows=(), bound=None):
        """moves: its ROW_MOVES (None: undeclared); rows: its written rows; bound: its
        production_bound's rate at each of them (None: no production_bound)."""
        self.LAW_ID, self.IDENTITY_ROLE, self.ROW_MOVES = law, role, moves
        self.ENTITY_WRITES = dict.fromkeys(writes, ("x",))
        self._species = tuple(SimpleNamespace(id=s) for s in species)
        self._rows = tuple(rows)
        if bound is not None:
            self.production_bound = lambda spec, declaration: dict.fromkeys(self._rows, bound)

    def species_identities(self, declaration):
        return self._species

    def written_rows(self, spec, declaration):
        return self._rows

    def sole_rows(self, spec, declaration):
        return ()


AMOUNTS = ("amount_increment", "extracellular_amount_increment")
PRECURSOR_ROWS = ((fx.PRECURSOR, fx.CELL), (fx.PRECURSOR, "ecs_0"))
WRITER_REFUSALS = {
    "trafficking": (
        _Stub(
            "cells.operator.scheduled_membrane_trafficking@1",
            writes=("population_abundance_increment",),
        ),
        "also writes population units",
    ),
    # FR-43 part 3: another conversion of the precursor is refused by name, a transfer by R5 (its
    # production has no static bound), and an undeclared split row writer fails closed.
    "another conversion": (
        _Stub(
            "cells.operator.planted_conversion@1",
            writes=AMOUNTS[:1],
            moves="conversion",
            rows=PRECURSOR_ROWS[:1],
        ),
        "converts the precursor",
    ),
    "a transfer": (
        _Stub(
            "cells.operator.planted_transfer@1",
            writes=AMOUNTS,
            moves="transfer",
            rows=PRECURSOR_ROWS,
            bound=float("inf"),
        ),
        "made at a rate with no static bound by cells.operator.planted_transfer@1",
    ),
    "an undeclared split row writer": (
        _Stub("cells.operator.planted_writer@1", writes=AMOUNTS[:1]),
        "declares no ROW_MOVES",
    ),
    "turnover admitted": (
        _Stub(
            put.TURNOVER_LAW,
            role="author",
            species=(fx.PRECURSOR,),
            writes=AMOUNTS,
            moves="conversion",
            rows=PRECURSOR_ROWS[:1],
        ),
        None,
    ),
}


@pytest.mark.parametrize("name", sorted(WRITER_REFUSALS))
def test_the_writers_of_units_and_precursor(name, monkeypatch):
    routes, controls = base_routes()
    spec = parse_spec(definition(routes, controls))
    declaration = next(d for d in spec.model.operators if d.law == put.LAW_ID)
    stub, message = WRITER_REFUSALS[name]
    entries = list(composite_spec.entries(spec)) + [(stub, None, None)]
    monkeypatch.setattr(composite_spec, "entries", lambda _: tuple(entries))
    if message is None:
        put.check_writers(spec, declaration)
    else:
        with pytest.raises(ConfigError, match=message):
            put.check_writers(spec, declaration)


def test_a_d152_reaction_on_the_precursor_and_an_in_step_mover_are_refused(monkeypatch):
    routes, controls = base_routes()
    spec = parse_spec(definition(routes, controls))
    declaration = next(d for d in spec.model.operators if d.law == put.LAW_ID)
    base_entries = list(composite_spec.entries(spec))
    d152 = _Stub(put.species_reactions.LAW_ID, role="author", species=(fx.PRECURSOR,))
    monkeypatch.setattr(composite_spec, "entries", lambda _: (*base_entries, (d152, "net", None)))
    monkeypatch.setattr(
        put.species_reactions, "written", lambda net: {(fx.PRECURSOR, fx.CELL): "use"}
    )
    with pytest.raises(ConfigError, match="one local-kinetics writer"):
        put.check_writers(spec, declaration)
    monkeypatch.setattr(put.species_reactions, "written", lambda net: {})
    put.check_writers(spec, declaration)  # The network writes another row: admitted.
    monkeypatch.setattr(composite_spec, "entries", lambda _: tuple(base_entries))
    moved = {fx.PRECURSOR: {"cell": ("a planted kind",)}}
    monkeypatch.setattr(species_registry, "moved_in_step", lambda _: moved)
    with pytest.raises(ConfigError, match="moved inside the inner step"):
        put.check_writers(spec, declaration)


def test_turnover_supplies_the_precursor_and_the_bound_reads_the_supply():
    routes, controls = base_routes()
    routes[0]["initial_pool_units"] = [300.0, 200.0]  # Counted in the bound (D232's W5 ruling).
    raw = fx.with_supply(definition(routes, controls), [(0.0, 0.0), (0.015, 1e-3)])
    spec = parse_spec(raw)  # Two writers of one row, admitted (Q3).
    assert parse_spec(composite_spec.to_dict(spec)).model.operators == spec.model.operators
    laws = [d.law for d in spec.model.operators]
    assert laws.index(fx.TURNOVER) < laws.index(put.LAW_ID)
    declaration = spec.model.operators[laws.index(put.LAW_ID)]
    checked = put.check_spec_for(spec, spec, declaration)
    kir = next(c for c in spec.model.channels if c.id == "kir_0")
    area = next(m for m in spec.model.membranes if m.id == kir.membrane_id).area_m2
    row = list(spec.model.species_ids).index(fx.PRECURSOR)
    pool = spec.model.cells[0].initial_amount_fmol[row] + 1e-3 * spec.experiment.end_time
    units = kir.abundance * area * fx.DENSITY + 500.0 + (6.02214076e23 * 1e-15 / 4) * pool
    got = next(c for c in checked.model.channels if c.id == "kir_0").abundance
    assert got == pytest.approx(units / (area * fx.DENSITY), rel=1e-15)


# ------------------------------------------------------------------ B1′: the routable assembly rate


class UnitControl(NamedTuple):
    unit_assembly_rate: np.ndarray
    unit_removal_rate: np.ndarray


class _Planted(Operator):
    """A planted rate-route source (B1′): a declared factor on the producer's assembly rate and
    its validity, or no route (factor None)."""

    LAW_ID = "tests.operator.planted_unit_route@1"
    SPLIT = True
    RK4 = "split"
    RATE_ROUTES = ((put.LAW_ID, "unit_assembly_rate"),)

    def __init__(self, factor, valid=True):
        self.factor, self.valid = factor, valid

    def half_step(self, state, h, control, p, *, xp):
        return state, None

    def rate_factors(self, state, p, target, field, *, xp):
        if self.factor is None:
            return None
        return np.asarray(self.factor), np.asarray(self.valid)


def _bitwise_but(a, b, skipped=None):
    for name in type(a)._fields:
        if name != skipped:
            assert np.asarray(getattr(a, name)).tobytes() == np.asarray(getattr(b, name)).tobytes()


def test_the_assembly_rate_is_routable_and_a_route_multiplies_it_in_the_half_step():
    """B1′'s target side (docs/INVENTORY_COUPLING_DESIGN.md §2.1): the producer declares its
    assembly rate routable, and its elements are its routes at their cells. Beside a route source
    declared before it, the composite's half-step is bitwise the half-step at the product rate.
    Planted: an invalid evaluation (a range breach) refuses the half-step, and a source with no
    route in the definition leaves the call unchanged."""
    spec, model, op, state, p = case_world("shared")
    _, assembly, removal, _, _ = CASES["shared"]
    declaration = next(d for d in spec.model.operators if d.law == put.LAW_ID)
    assert dict(op.ROUTABLE_CONTROLS) == {"unit_assembly_rate": "rate"}
    cells = op.routable_elements(declaration, "unit_assembly_rate")
    assert cells == (("r0", fx.CELL), ("r1", fx.CELL))
    state_op = model.operators[0]
    factor = np.array([0.5, 0.25])
    composite = pump_composite.Composition(model.inner, (state_op, _Planted(factor), op))
    assert composite.rate_routes == {op: ((composite.operators[1], "unit_assembly_rate"),)}
    control = UnitControl(np.asarray(assembly, dtype=float), np.asarray(removal, dtype=float))
    routed, ok = composite._half_step(op, state, H, control, p, xp=np)
    expected, ok_expected = step(op, state, p, np.asarray(assembly) * factor, removal)
    assert bool(ok) and bool(ok_expected)
    _bitwise_but(routed, expected)
    breach = pump_composite.Composition(model.inner, (state_op, _Planted(factor, False), op))
    _, ok = breach._half_step(op, state, H, control, p, xp=np)
    assert not bool(ok)
    idle = pump_composite.Composition(model.inner, (state_op, _Planted(None), op))
    unrouted, ok = idle._half_step(op, state, H, control, p, xp=np)
    plain, _ = step(op, state, p, assembly, removal)
    assert bool(ok)
    _bitwise_but(unrouted, plain)
    assert not np.array_equal(routed.unit_consumed_fmol, plain.unit_consumed_fmol)  # It acts.


def test_the_coupling_v2_routes_a_template_onto_the_assembly_rate():
    """F3's code (B1′ on cells.operator.species_regulated_availability@2; development, not judged): a Hill
    activation of a template species in the cell, F = b + (1 - b) c^n / (K^n + c^n), multiplies the
    producer's assembly rate in its half-steps. It parses, round trips and binds one route; the
    routed half-step is bitwise the half-step at the product rate, and records F; switched off
    (the cut control), F is exactly 1 and the half-step is the scheduled one. Planted, each
    refused: the producer declared before its route's source, and the template outside the
    declared operating range while the coupling is on (off, the same breach is admitted)."""
    routes, controls = base_routes()
    spec = parse_spec(fx.with_template_route(definition(routes, controls)))
    again = parse_spec(composite_spec.to_dict(spec))
    assert again.model.operators == spec.model.operators
    assert again.experiment.operators == spec.experiment.operators
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    coupling = next(o for o in model.operators if o.LAW_ID == fx.COUPLING_2)
    producer = next(o for o in model.operators if o.LAW_ID == put.LAW_ID)
    assert model.rate_routes == {producer: ((coupling, "unit_assembly_rate"),)}
    assert np.asarray(p.coupling_unit_assembly_rate_routes).tolist() == [[0]]
    row = list(spec.model.species_ids).index(fx.TEMPLATE)
    amount = np.asarray(p.amount_reference)[row, 0] + np.asarray(state.amount_increment)[row, 0]
    c = amount / np.asarray(p.volume)[0]
    expected = 0.1 + 0.9 * c**2 / (1e-3**2 + c**2)
    factor, ok = coupling.rate_factors(state, p, put.LAW_ID, "unit_assembly_rate", xp=np)
    assert bool(ok) and float(factor[0]) == pytest.approx(expected, rel=1e-14) and expected < 1
    values = composite_spec.control_values(spec, [0.0])
    control = model.CONTROL_TYPE(*(v[0] for v in values))
    h = 0.5 * spec.execution.dt
    record = sra.SpeciesRegulatedAvailabilityV2.FACTOR_RECORD
    routed, ok = model._half_step(producer, state, h, control, p, xp=np)
    product = control._replace(unit_assembly_rate=control.unit_assembly_rate * factor)
    by_hand, _ = producer.half_step(state, h, product, p, xp=np)
    assert bool(ok)
    _bitwise_but(routed, by_hand, record)
    assert np.asarray(getattr(routed, record)).tobytes() == np.asarray(factor).tobytes()
    off = state._replace(coupling_enabled=np.zeros_like(state.coupling_enabled))
    cut, ok = model._half_step(producer, off, h, control, p, xp=np)
    plain, _ = producer.half_step(off, h, control, p, xp=np)
    assert bool(ok)
    _bitwise_but(cut, plain, record)
    assert not np.array_equal(routed.unit_consumed_fmol, cut.unit_consumed_fmol)  # It acts.
    assert np.asarray(getattr(cut, record)).tolist() == [1.0]  # The factor applied: exactly 1.
    with pytest.raises(ConfigError, match="precedes it"):
        parse_spec(fx.with_template_route(definition(routes, controls), coupling_first=False))
    narrow = parse_spec(
        fx.with_template_route(definition(routes, controls), operating_range=(0.5, 1.0))
    )
    model2 = get_model(narrow.model)
    state2, p2 = model2.initial_values(narrow)
    producer2 = next(o for o in model2.operators if o.LAW_ID == put.LAW_ID)
    _, ok = model2._half_step(producer2, state2, h, control, p2, xp=np)
    assert not bool(ok)
    off2 = state2._replace(coupling_enabled=np.zeros_like(state2.coupling_enabled))
    _, ok = model2._half_step(producer2, off2, h, control, p2, xp=np)
    assert bool(ok)


# ------------------------------------------------------------------ one compiled world

STEPS, DT, SUPPLY_ON = 30, 1e-3, 0.015
POLICY = WindowPolicy(10, "full")
RATES = (50.0, 20.0)  # k_a, k_r (1/s), synthetic; κ = 2 / 0.02 s.


def compiled_definition():
    routes = [fx.route("kir_units", "kir_0", pools=2, tau=0.02)]
    raw = definition(routes, {"kir_units": [(0.0, *RATES)]}, end=STEPS * DT)
    return fx.with_supply(raw, [(0.0, 0.0), (SUPPLY_ON, 1e-3)])


def collect(spec, checkpoint=None):
    windows = list(iter_windows(spec, POLICY, checkpoint))
    rows = {}
    for window in windows:
        for i, _ in enumerate(np.asarray(window.times)):
            rows[window.start_step + i] = type(window.history)(
                *(np.asarray(v)[i] for v in window.history)
            )
    return windows, rows


@pytest.fixture(scope="module")
def run():
    spec = parse_spec(compiled_definition())
    windows, rows = collect(spec)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == put.LAW_ID)
    return spec, model, op, p, windows, rows


def test_every_row_is_checked_and_the_chain_is_exact_before_the_supply(run):
    spec, _, op, p, _, rows = run
    assert sorted(rows) == list(range(STEPS + 1))  # The runner checked every row (else raised).
    row0 = rows[0]
    species = list(spec.model.species_ids)
    n0 = float(np.asarray(p.amount_reference)[species.index(fx.PRECURSOR), 0])
    big_n0 = float(np.asarray(membrane_state.units(row0, p, xp=np))[0])
    c = put.conversion(spec_route_compiled(spec))
    for k in range(1, int(round(SUPPLY_ON / DT)) + 1):
        _, [(consumed, pools, big_n, removed)] = reference(
            n0, [(RATES[0], c, 100.0, [0.0, 0.0], big_n0, RATES[1])], k * DT
        )
        r = rows[k]
        got = [
            r.unit_consumed_fmol[0],
            *r.unit_pool_units[0],
            np.asarray(membrane_state.units(r, p, xp=np))[0],
            r.unit_removed_units[0],
        ]
        for g, w in zip(got, [consumed, *pools, big_n, removed], strict=True):
            assert abs(Decimal(float(g)) - w) <= Decimal("1e-12") * abs(w), (k, g, w)


def spec_route_compiled(spec):
    block = next(d for d in spec.model.operators if d.law == put.LAW_ID)
    return block.routes[0]


def test_the_account_holds_on_every_row(run):
    spec, model, op, p, _, rows = run
    for k, r in rows.items():
        ledgers = model.balances(r, p)
        bounds = op.own_bounds(op.own_magnitudes(r, p, xp=np), max(k, 1))
        for name, bound_ in zip(put.LEDGERS, bounds, strict=True):
            assert np.all(np.abs(ledgers[name]) <= bound_), (k, name)
        assert np.all(np.abs(ledgers["population_abundance_entity"]) <= 1e-9), k
    final = rows[STEPS]
    assert final.turnover_produced_fmol.max() > 0  # The supply ran after 15 ms.
    assert final.unit_inserted_units[0] > 0 and final.unit_removed_units[0] > 0


@pytest.mark.parametrize("time", (0.012, 0.018))
def test_a_resumed_run_is_bitwise_the_uninterrupted_one(run, time):
    spec, _, _, _, windows, rows = run
    checkpoint = next(
        w.checkpoint_at(float(t))
        for w in windows
        for t in np.asarray(w.times)
        if abs(t - time) < 1e-9
    )
    _, resumed = collect(spec, checkpoint)
    start = int(round(time / DT))
    for k in range(start, STEPS + 1):
        for a, b in zip(resumed[k], rows[k], strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), k
