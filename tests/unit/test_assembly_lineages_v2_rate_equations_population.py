"""cells.rate_equations@1's shared pool (OL6 slice S2; the OL6 design note's §3, §6.9).

Closed forms and identities only, never a comparison with exact events (D304). A population of
two vesicles on one pool transfers by the exact operator's domain-6 draws, divides into its free
slot (every daughter lives, daughter 0 in its parent's slot) and stops `slots_full` when a split
finds no free slot; two identical vesicles lysing at one instant are refused (FR-20's rule). A new
file for the slice's population (D224): two population worlds compiled, about 45 s.
"""

import jax.numpy as jnp
import numpy as np
import pytest
from scipy.linalg import expm

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    GATE_FACTOR,
    IDEAL_MIXING,
    MASS_ACTION,
    PRESCRIBED_SHELL,
    SHARED_POOL,
    SHEAR_FISSION,
    SHELL_PERMEATION,
    rate_equations,
    runner,
    streams,
    transfer,
)
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_rate_equations_vesicles import (
    population_definition,
    population_world,
)


def test_a_population_transfers_divides_into_a_free_slot_and_stops_when_full():
    w = population_world([12000, 10000], 0.3, slots=2)
    w["division"] = {"law": SHEAR_FISSION}
    fresh = [48356, 0]
    schedules = [
        {"index": 0, "kind": "transfer", "times_s": [1.0], "K_keep": 1, "fresh_pool": fresh},
        {"index": 1, "kind": "shear", "k": 2, "times_s": [2.0]},
        {"index": 2, "kind": "shear", "k": 2, "times_s": [3.0]},
    ]
    spec = parse_spec(population_definition(w, horizon=4.0, schedules=schedules))
    run = runner.run(spec)
    assert run.status == "slots_full"
    moved, split, full = run.events
    base = streams.base_key_data(1, 0, 0, 0)
    kept = transfer.sample(base, spec.experiment.schedules[0], 0, [0, 1], 1)[0]
    assert moved["kind"] == "transfer" and moved["kept"] == kept  # domain 6, as exact
    (alive,) = kept
    assert split["outcome"] == "split" and split["slot"] == alive
    assert sorted(split["homes"]) == [0, 1]  # daughter 0 in its slot, daughter 1 in the free one
    sub = alive  # founder i holds key i:0, its sub-lineage i
    assert split["keys"] == [(sub << 32) + 1, (sub << 32) + 2]
    first, second = (np.asarray(d) for d in split["daughters"])
    assert np.allclose(first, second, rtol=1e-15, atol=0.0)
    assert full["outcome"] == "slots_full"
    assert run.rows["alive"][-1].tolist() == [True, True] and run.moieties["closes"]


def test_two_identical_vesicles_lysing_at_one_instant_are_refused():
    w = population_world([12000, 12000], 0.97, slots=2)
    w["founder"]["L@pool"] = 2000
    spec = parse_spec(population_definition(w, horizon=50.0, schedules=None))
    with pytest.raises(ConfigError, match="two lyses at one instant"):
        runner.run(spec)


# ------------------------------------------------------------------ FR-47: a shell's washes (D323)

SHELL = {"V_out_L": 1e-18, "V_in_L": 2e-19, "A_m2": 1e-15, "P_m_per_s": 2e-7}  # made up
U = "unsourced; test"
NA = 6.02214076e23


def _species(name, moieties, **mu):
    return {"id": name, "moieties": moieties, "standard_mu_RT": mu, "catalogue": None,
            "evidence": None}  # fmt: skip


def shell_world(*, tracer=4000, wall=50, delta=0.0, gate=None):
    """FR-47's shape on made-up inputs, never the protocol's: one shell slot in a finite pool; a
    tracer S enters the lumen by the shell's permeation, κ_in = P A / V_out = 0.2 per s, and
    leaves at κ_out = P A e^Δ / V_in = e^Δ per s, with Δ the tracer's lumen potential less its
    solution one (FR-48); the wall is a subunit B, which no step moves. With `gate` = N_g, the
    wall also holds the forms G and H, switching by a wall step, with the gate factor on the
    entry."""
    mu = {"solution": 0.3, "lumen": 0.3 + delta} if delta else {"solution": 0.0}
    w = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": "multinomial",
                        "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept"},
        "species": [_species("S", {"s": 1}, **mu), _species("B", {"b": 1}, bilayer=-3.0)],
        "phases": {"pool": {"volume_L": SHELL["V_out_L"],
                            "species": [{"id": "S", "kind": "finite"}]},
                   "membrane": {"species": ["B"]},
                   "lumen": {"volume_L": SHELL["V_in_L"], "species": ["S"]}},
        "steps": [{"id": "entry", "locus": "membrane", "reactants": {"S@pool": 1},
                   "products": {"S@lumen": 1}, "law": SHELL_PERMEATION,
                   "permeability_m_per_s": {"value": SHELL["P_m_per_s"], "provenance": U}}],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"S@pool": tracer, "S@lumen": 0, "B@membrane": 0},
        "population": {"structure": SHARED_POOL, "slots": 1,
                       "founders": [{"S@lumen": 0, "B@membrane": wall}]},
        "geometry": {"law": PRESCRIBED_SHELL,
                     "area_m2": {"value": SHELL["A_m2"], "provenance": U}},
    }  # fmt: skip
    if gate is not None:
        w["species"] += [_species("G", {"g": 1}, bilayer=-0.5),
                         _species("H", {"g": 1}, bilayer=-1.2)]  # fmt: skip
        w["phases"]["membrane"]["species"] += ["G", "H"]
        w["population"]["founders"][0] |= {"G@membrane": gate // 2, "H@membrane": gate - gate // 2}
        w["founder"] |= {"G@membrane": 0, "H@membrane": 0}
        w["steps"].append({"id": "switch", "phase": "membrane", "reactants": {"G": 1},
                           "products": {"H": 1}, "law": MASS_ACTION, "forward_rate_per_s": 3.0})
        w["rate_factor"] = {"law": GATE_FACTOR, "forms": ["G", "H"],
                            "entries": [{"form": "G", "step": "entry", "ddG_kT": 0.8},
                                        {"form": "H", "step": "entry", "ddG_kT": -0.6}]}
    return w


def shell_definition(w, *, stops=(), times=(), horizon=1.0, representation=True, rtol=1e-9,
                     seed=1, buffer=0, fresh=0):  # fmt: skip
    """One run of `w` in population mode: (d) at `rtol`, or exact events; `stops` are (kind,
    time, fraction), each wash's buffer or fresh pool holding `buffer` or `fresh` tracers."""
    schedules = [{"index": i, "kind": "withdrawal", "times_s": [t], "fraction": f,
                  "buffer": [buffer]}
                 if kind == "withdrawal" else
                 {"index": i, "kind": "replacement", "times_s": [t], "pool": [fresh]}
                 for i, (kind, t, f) in enumerate(stops)]  # fmt: skip
    d = definition(w, horizon=horizon, observations=times, event_limit=2**31 - 1,
                   row_every=2**31 - 1, trace=False, seed=seed, molecules=1 << 14,
                   chunk=256)  # fmt: skip
    d["execution"]["mode"] = "population"
    if schedules:
        d["experiment"]["schedules"] = schedules
    if representation:
        for key in ("molecule_capacity", "chunk_events"):
            d["execution"].pop(key)
        d["execution"]["representation"] = {
            "id": "cells.rate_equations@1",
            "envelope": {"min_count": 10.0, "provenance": "a test envelope"},
            "integrator": {"id": "rosenbrock_rodas4_dense@1", "rtol": rtol, "atol_count": 1e-6,
                           "step_limit": 100000}}  # fmt: skip
    return d


STOPS = (("withdrawal", 1.0, 0.5), ("replacement", 2.0, None), ("withdrawal", 3.0, 0.25))
TIMES = (0.5, 1.5, 2.5, 3.5)


def closed_form(n0, delta, stops, times, horizon):
    """The mean's closed form (the rate equations are linear): the two-place matrix exponential
    between stops, each stop's mean map; ({time: (pool, lumen)}, [(kind, removed, heat)],
    [(start, end) states per interval])."""
    k_in = SHELL["P_m_per_s"] * SHELL["A_m2"] / (SHELL["V_out_L"] * 1e-3)
    k_out = SHELL["P_m_per_s"] * SHELL["A_m2"] * np.exp(delta) / (SHELL["V_in_L"] * 1e-3)
    rates = np.array([[-k_in, k_out], [k_in, -k_out]])
    x, t, observed, washes, intervals, start = np.array([float(n0), 0.0]), 0.0, {}, [], [], None
    start = x.copy()
    for kind, at, f in sorted([("obs", s, None) for s in times] + [(k, s, f) for k, s, f in stops],
                              key=lambda e: e[1]):  # fmt: skip
        x, t = expm(rates * (at - t)) @ x, at
        if kind == "obs":
            observed[at] = x.copy()
            continue
        intervals.append((start, x.copy()))
        if kind == "withdrawal":
            washes.append((kind, f * x[0], -(1 - f) * x[0] * np.log1p(-f)))
            x = np.array([(1 - f) * x[0], x[1]])
        else:
            washes.append((kind, x[0], None))
            x = np.array([0.0, x[1]])
        start = x.copy()
    intervals.append((start, expm(rates * (horizon - t)) @ x))
    return observed, washes, intervals


def f_cont(x, delta):
    """Stirling's F of (pool, lumen) counts, each term 0 at 0 (SPEC.md §3.2's form)."""
    mu = (0.3, 0.3 + delta) if delta else (0.0, 0.0)
    out = 0.0
    for n, m, v in zip(x, mu, (SHELL["V_out_L"], SHELL["V_in_L"]), strict=True):
        if n > 0:
            out += n * (m - np.log(NA * v)) + n * np.log(n) - n
    return out


def test_a_shell_s_washes_follow_the_mean_s_closed_form_with_their_books_and_records(tmp_path):
    """FR-47 (D323) in (d), on a made-up W1Δ shape (Δ = ln 2): a withdrawal at f = 1/2, a
    tracer-free full wash, then a withdrawal at f = 1/4 that only E2's refilled pool can feed. The
    counts at every observation, each wash's removed amount and mixing heat −(1 − f) n ln(1 − f),
    and each interval's continuous heat −ΔF_cont (each term 0 at 0, the two zero starts booked by
    closure) equal the linear mean's closed form, each read by FR-47's judge from (d)'s rows and
    stop events; the tracer moiety balances with the removed amounts; the books close; the records
    name the shell, the washes and E2, and their status, development-only until FR-47's verdict.
    One population program compiled and one run: about 25 s."""
    import json

    from cells.models.assembly_lineages_v2 import records
    from validation.assembly_lineages_v2 import fr47_judge

    delta, n0 = float(np.log(2.0)), 4000
    spec = parse_spec(shell_definition(shell_world(delta=delta), stops=STOPS, times=TIMES,
                                       horizon=4.0))  # fmt: skip
    run = runner.run(spec)
    assert run.status == "complete" and run.moieties["closes"] and run.dissipation["holds"]
    e2 = run.statistics["e2"]
    assert e2["places"] == ["S@pool", "S@lumen"] and e2["zero_starts"] == 2  # founder, the wash
    observed, washes, intervals = closed_form(n0, delta, STOPS, TIMES, 4.0)
    # read as FR-47's judge reads (d)'s rows and stop events
    world, times = spec.model.world, [t for _, t, _ in STOPS]
    counts = fr47_judge.d_observables(run, world, ["S@pool", "S@lumen"], TIMES)
    for t in TIMES:
        got = (counts[("S@pool", t)], counts[("S@lumen", t)])
        assert np.allclose(got, observed[t], rtol=0.0, atol=1e-6 * n0), t
    stops = fr47_judge.d_stops(run)
    assert [(t, kind) for t, kind, _, _ in stops] == [(t, k) for k, t, _ in STOPS]
    for (_, kind, removed, heat), (_, want, want_heat) in zip(stops, washes, strict=True):
        assert abs(removed - want) <= 1e-6 * n0
        assert (heat is None) == (kind == "replacement")
        if heat is not None:
            assert abs(heat - want_heat) <= 1e-6 * n0
    assert washes[2][1] > 20.0  # the pool refilled after the full wash: E2's flux (P4 gives 0)
    for (a, b, heat), (x0, x1) in zip(fr47_judge.d_intervals(run, times, 4.0), intervals,
                                      strict=True):  # fmt: skip
        assert abs(heat - (f_cont(x0, delta) - f_cont(x1, delta))) <= 1e-6 * n0, (a, b)
    names = [p.name for p in world.places]
    rows = run.rows
    present = (rows["pool_counts"][-1][names.index("S@pool")]
               + rows["slot_counts"][-1][0][names.index("S@lumen")])  # fmt: skip
    assert abs(present + sum(r for _, _, r, _ in stops) - n0) <= 1e-9 * n0
    records.write_run(tmp_path / "bundle", run)
    record = json.loads((tmp_path / "bundle" / "run.json").read_text())
    assert {"shell", "washes", "e2"} <= set(record["representation"]["formulas"])
    assert record["representation"]["qualification"] == {
        "status": "admitted, development-only until fr47-shell-exchange's verdict",
        "protocol": "fr47-shell-exchange-registered-2026-11-24",
        "paths": ["shell", "washes", "e2"]}  # fmt: skip
    assert record["check"]["world"]["parity"]["identical"]
    kinds = np.load(tmp_path / "bundle" / "rows.npz")["row_kind"].tolist()
    assert kinds.count("withdrawal") == 2 and kinds.count("replacement") == 1


def test_a_switching_gate_in_a_shell_has_its_limit_s_rates_and_its_own_check(monkeypatch):
    """FR-47's W2 shape on made-up inputs, at the host (no run): (d)'s wall step G -> H runs at
    k (N_w + 1)/N_w per G copy and k e^(μ°_H − μ°_G) (N_w + 1)/N_w per H copy, SPEC.md §3.3's
    limit factor, here in a shell's world; the gate factor g = (n_G e^a + n_H e^b)/(n_G + n_H)
    multiplies both directions of the entry; the world's own check (the identity, E2's linear
    form) and its parity with the exact kernel pass, and a planted (d) view whose shell extent is
    off by e^0.5 fails parity (the identity check cannot see it: the extent cancels between the
    two directions). Three small compiles: about 10 s."""
    spec = parse_spec(shell_definition(shell_world(gate=40, wall=30), horizon=1.0))
    problem = rate_equations.Problem(spec)
    names = [p.name for p in spec.model.world.places]
    assert [n for n, on in zip(names, problem.e2, strict=False) if on] == ["S@lumen"]
    n = np.zeros(problem.P)
    for name, value in {"S@pool": 3000.0, "S@lumen": 500.0, "B@membrane": 30.0,
                        "G@membrane": 17.0, "H@membrane": 23.0}.items():  # fmt: skip
        n[names.index(name)] = value
    forward = np.exp(np.asarray(problem.log_direction(jnp.asarray(n), True)))
    reverse = np.exp(np.asarray(problem.log_reverse(jnp.asarray(n))))
    kf = np.asarray(problem.layout.kf)
    entry, switch = 0, 1
    factor = (30 + 40 + 1) / (30 + 40)
    assert kf[switch] * forward[switch] / 17.0 == pytest.approx(3.0 * factor, rel=1e-14)
    assert kf[switch] * reverse[switch] / 23.0 == pytest.approx(
        3.0 * np.exp(-1.2 + 0.5) * factor, rel=1e-14)  # fmt: skip
    g = (17.0 * np.exp(0.8) + 23.0 * np.exp(-0.6)) / 40.0
    k_in = SHELL["P_m_per_s"] * SHELL["A_m2"] / (SHELL["V_out_L"] * 1e-3)
    k_out = SHELL["P_m_per_s"] * SHELL["A_m2"] / (SHELL["V_in_L"] * 1e-3)
    assert kf[entry] * forward[entry] == pytest.approx(g * k_in * 3000.0, rel=1e-14)
    assert kf[entry] * reverse[entry] == pytest.approx(g * k_out * 500.0, rel=1e-14)
    worst = rate_equations.limit_check(problem, np.random.default_rng(1), states=4)
    assert worst["e2_linearity"] <= 1e-12 and worst["identity"] <= 1e-12
    tends = rate_equations.shell_parity(spec, np.random.default_rng(1))
    assert not tends["identical"] and tends["order"] >= 0.9  # the switch's (N + 1)/N, as 1/λ
    original = rate_equations.Problem.view

    def off_extent(self, n, forward):  # planted: (d)'s shell extent off by e^0.5
        v = original(self, n, forward)
        return v._replace(log_encounter=v.log_encounter + 0.5)

    monkeypatch.setattr(rate_equations.Problem, "view", off_extent)
    with pytest.raises(ConfigError, match="does not tend to its exact form"):
        rate_equations.shell_parity(spec, np.random.default_rng(1))


@pytest.mark.parametrize("value, retried", [(-1e-4, True), (-1e-6, False)])
def test_e2_s_rule_below_zero_retries_a_quarter_step(value, retried):
    """CRITERIA's rule for E2 places below zero: a step result with an E2 place below
    −10·atol_count (−1e-5 here) is rejected and retried at exactly h/4 (planted: the first
    step's lumen set to −1e-4); one at −1e-6, within the bound, is accepted, and the next step,
    which starts below zero, books its heat by closure. The washes row's program, reused: about
    2 s after it."""
    spec = parse_spec(shell_definition(shell_world(delta=float(np.log(2.0))), stops=STOPS,
                                       times=TIMES, horizon=4.0))  # fmt: skip
    state = rate_equations._Run(spec)
    shape = state.shape
    lumen = [p.name for p in spec.model.world.places].index("S@lumen")
    at = shape.problem.P + shape.places.tolist().index(lumen)  # slot 0's lumen in y
    honest, sizes = state.prog["step"], []

    def planted(y, h, alive):
        result = honest(y, h, alive)
        sizes.append(float(h))
        return result._replace(y=result.y.at[at].set(value)) if len(sizes) == 1 else result

    state.prog = {**state.prog, "step": planted}
    state.integrate(0.5)
    assert state.status is None and state.t == 0.5 and state.below_rejected == int(retried)
    if retried:
        assert sizes[1] == sizes[0] / 4.0 and state.zero_starts >= 1
    else:
        assert sizes[1] != sizes[0] / 4.0 and state.zero_starts >= 2  # the founder's, then -1e-6


def test_a_wash_that_supplies_tracer_closes_its_books_and_its_moieties():
    """FR-47's washes with supply, at the host on the washes row's program (no integration): from
    a pool of 3000 and a lumen of 500, a withdrawal at f = 1/4 whose buffer carries 300 tracers in
    fV, then a pulse replacement whose fresh pool holds 2500. The ledger closes at every row, each
    wash moving F_cont by its work less its sink and heat; the mixing heat is Stirling's
    F(kept; (1 − f)V) + F(b; fV) − F(kept + b; V) ≥ 0, computed apart; the pulse's work and sink
    are F_cont of the fresh and the old pool; the tracer balances with what was removed and
    supplied. About 1 s after the washes row."""
    delta = float(np.log(2.0))
    stops = (("withdrawal", 1.0, 0.25), ("replacement", 2.0, None))
    spec = parse_spec(shell_definition(shell_world(delta=delta), stops=stops, times=TIMES,
                                       horizon=4.0, buffer=300, fresh=2500))  # fmt: skip
    state = rate_equations._Run(spec)
    names = [p.name for p in spec.model.world.places]
    shape = state.shape
    y = np.asarray(state.y).copy()
    y[names.index("S@pool")] = 3000.0
    y[shape.problem.P + shape.places.tolist().index(names.index("S@lumen"))] = 500.0
    state.y = jnp.asarray(y)
    state.row("start")
    withdrawal_, pulse = spec.experiment.schedules
    state.withdrawal(withdrawal_)
    state.replacement(pulse)
    ledger, moieties = rate_equations._books(state)
    assert ledger["closes"] and moieties["closes"]
    w, r = state.events

    def F(c, volume_L):  # the pool's Stirling F of c tracers in a volume
        return c * (0.3 - np.log(NA * volume_L)) + c * np.log(c) - c

    v = SHELL["V_out_L"]
    heat = F(2250.0, 0.75 * v) + F(300.0, 0.25 * v) - F(2550.0, v)
    assert (w["removed"]["S@pool"], w["remaining"]["S@pool"]) == (750.0, 2250.0)
    assert w["supplied"]["S@pool"] == 300.0 and heat > 0.0
    assert w["mixing_heat_kT"] == pytest.approx(heat, rel=1e-12)
    assert w["buffer_F_kT"] == pytest.approx(F(300.0, 0.25 * v), rel=1e-12)
    assert (r["removed"]["S@pool"], r["supplied"]["S@pool"]) == (2550.0, 2500.0)
    assert r["work_kT"] == pytest.approx(F(2500.0, v), rel=1e-12)
    assert r["sink_kT"] == pytest.approx(F(2550.0, v), rel=1e-12)
    moved = sum(e["removed"]["S@pool"] - e["supplied"]["S@pool"] for e in state.events)
    pool, slots = shape.split(np.asarray(state.y))[:2]
    present = pool[names.index("S@pool")] + slots[0, shape.places.tolist().index(
        names.index("S@lumen"))]  # fmt: skip
    assert present + moved == 3500.0
