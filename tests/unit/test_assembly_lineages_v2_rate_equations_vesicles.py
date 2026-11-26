"""cells.assembly_representation.rate_equations@1's vesicles (OL6 slice S2; the OL6 design note's §1.4, §3).

Closed forms and identities only, never a comparison with exact events (D304: Protocol D is
registered before any such reading). A deflating vesicle crosses the lumen's kink (a restart) and
lyses at the located σ = σ_max, its release booked; a floppy vesicle's mean split costs exactly
(k − 1) C_close (a floppy vesicle's F_v is linear in its contents), the floor refusing a split
below it; the limit's check reads the osmotic term on both sides of its kink; and the slice's
parse refusals. New files for the slice (D224): the S1 file is at about 60 s of tier 2's 90, so the
single-lineage vesicles are here (two worlds compiled, about 50 s) and the population in
test_assembly_lineages_v2_rate_equations_population.py.
"""

import copy
import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    IDEAL_MIXING,
    OSMOTIC_LUMEN,
    PHASE_EXCHANGE,
    SHARED_POOL,
    SHEAR_FISSION,
    rate_equations,
    runner,
    streams,
)
from tests.assembly_lineage_v2_fixtures import definition

jax.config.update("jax_enable_x64", True)

Q, K_L, NA, C_EXT_MM, CLOSE = 1e-19, 60, 6.02214076e23, 1000.0, 25.0
U = "unsourced; test"
ENVELOPE = {"min_count": 100.0, "provenance": "a test envelope"}
INTEGRATOR = {"id": "cells.solver.rosenbrock_rodas4_dense@1", "rtol": 1e-9, "atol_count": 1e-6,
              "step_limit": 100000}  # fmt: skip


def lumen_count(n_mem, x0):
    """The impermeant lumen count at which V_osm / V_sph = x0 for a membrane of n_mem lipids."""
    area = Q * K_L * n_mem / 2.0
    v_sph = area**1.5 / (6.0 * math.sqrt(math.pi)) * 1e3  # L
    return int(round(x0 * v_sph * NA * C_EXT_MM * 1e-3))


def species(name, moieties, **mu):
    return {"id": name, "moieties": moieties, "standard_mu_RT": mu, "catalogue": None,
            "evidence": None}  # fmt: skip


def vesicle_world(*, n_mem=12000, x0=0.97, pool_L=1000, sigma_max=2e-3, floor=1000 * K_L):
    """L joins a one-species membrane from a large pool (pool volume 1e-15 L, so its equilibrium
    count is about 4.8e4); the lumen holds an impermeant I at V_osm / V_sph = x0."""
    return {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": "multinomial",
                        "membrane_kinetics": "count_on_m", "lumen_volume": "osmotic",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept",
                        "exchange_encounter": "insertion_area"},
        "species": [species("L", {"l": 1}, solution=0.0, bilayer=-9.43),
                    species("I", {"i": 1}, solution=0.0)],
        "phases": {"pool": {"volume_L": 1e-15, "species": [{"id": "L", "kind": "finite"},
                                                           {"id": "I", "kind": "finite"}]},
                   "membrane": {"species": ["L"]}, "lumen": {"species": ["I"]}},
        "steps": [{"id": "join", "locus": "membrane", "reactants": {"L@pool": 1},
                   "products": {"L@membrane": 1}, "law": PHASE_EXCHANGE,
                   "insertion_velocity_m_per_s": {"value": 2e-7, "provenance": U}}],
        "free_energy": [{"law": IDEAL_MIXING},
                        {"law": OSMOTIC_LUMEN,
                         "outside_osmolarity_mM": {"value": C_EXT_MM, "provenance": U}}],
        "founder": {"L@pool": pool_L, "I@pool": 0, "L@membrane": n_mem,
                    "I@lumen": lumen_count(n_mem, x0)},
        "geometry": {"law": BILAYER_GEOMETRY, "area_quantum_m2": Q,
                     "area_per_leaflet": {"L": {"quanta": K_L, "provenance": U}},
                     "vesicle_floor": {"quanta": floor, "provenance": U},
                     "closure_cost_kT": {"value": CLOSE, "provenance": U},
                     "sigma_max_N_per_m": {"value": sigma_max, "provenance": U}},
    }  # fmt: skip


def as_representation(raw):
    out = copy.deepcopy(raw)
    x = out["execution"]
    for key in ("molecule_capacity", "chunk_events"):
        x.pop(key, None)
    x["representation"] = {"id": "cells.assembly_representation.rate_equations@1", "envelope": dict(ENVELOPE),
                           "integrator": dict(INTEGRATOR)}  # fmt: skip
    out["experiment"]["trace"] = False
    return out


def population_world(sizes, x0, *, slots):
    """`slots` slots on one pool; founders of `sizes` lipids, each at V_osm / V_sph = x0."""
    w = vesicle_world(n_mem=sizes[0], x0=x0, pool_L=48356)
    for place in ("L@membrane", "I@lumen"):
        w["founder"][place] = 0  # a population's founder is the pool's
    w["population"] = {"structure": SHARED_POOL, "slots": slots, "founders": [
        {"L@membrane": n, "I@lumen": lumen_count(n, x0)} for n in sizes]}  # fmt: skip
    return w


def population_definition(w, *, horizon, schedules):
    d = as_representation(definition(w, horizon=horizon))
    d["execution"]["mode"] = "population"
    if schedules:
        d["experiment"]["schedules"] = schedules
    return d


def test_a_vesicle_crosses_its_kink_and_lyses_at_sigma_max_with_its_release_booked():
    spec = parse_spec(as_representation(definition(vesicle_world(), horizon=50.0,
                                                   observations=(1.0,))))  # fmt: skip
    run = runner.run(spec)  # books checked inside: a run whose books do not close is refused
    assert run.status == "lysed" and run.rows["row_kind"].tolist() == ["start", "observed", "lysis"]
    assert run.statistics["restarts"] == 1 and run.statistics["crossings"] == 2  # kink, lysis
    (lysis,) = run.events
    assert lysis["cause"] == "threshold" and lysis["time_s"] == run.rows["row_time_s"][-1]
    sigma_max = 2e-3
    assert abs(lysis["sigma_N_per_m"] - sigma_max) <= 10 * INTEGRATOR["rtol"] * sigma_max
    # The release: every vesicle molecule in its pool place, the totals as the founder's.
    founder = np.asarray(spec.model.world.founder, dtype=np.float64)
    end = run.rows["counts"][-1]
    assert end[2] == 0.0 and end[3] == 0.0  # L@membrane, I@lumen
    assert abs(end[0] - (founder[0] + founder[2])) <= 1e-9 * founder[2] and end[1] == founder[3]
    assert run.moieties["closes"] and run.dissipation["holds"]
    again = runner.run(spec)  # deterministic: the same bits (the program is kept)
    for name, values in run.rows.items():
        assert np.array_equal(values, again.rows[name]), name


def test_a_shear_stop_splits_a_floppy_vesicle_by_its_mean_at_the_closure_cost():
    w = vesicle_world(x0=0.6, pool_L=48356)
    w["division"] = {"law": SHEAR_FISSION, "continuation": "uniform"}
    d = as_representation(definition(w, horizon=3.0))
    d["experiment"]["schedules"] = [
        {"index": 0, "kind": "shear", "k": 4, "times_s": [1.0]},
        {"index": 1, "kind": "shear", "k": 2, "times_s": [2.0]},
    ]
    spec = parse_spec(d)
    run = runner.run(spec)
    assert run.status == "complete"
    refused, split = run.events
    assert refused["outcome"] == "refused_volume"  # v = 0.6 > 4^(-1/2)
    assert split["outcome"] == "split" and split["keys"] == [1, 2]
    base = streams.base_key_data(1, 0, 0, 0)
    u = float(streams.uniforms(streams.stream_key_data(base, 0, "continuation"), 0, 1)[0])
    assert split["followed"] == int(np.floor(u * 2))  # domain 3, counter 0: the exact draw
    # A floppy vesicle's F_v is linear in its contents, so the split costs (k − 1) C_close.
    assert abs(split["shear_work_kT"] - CLOSE) <= 1e-9 * abs(split["sink_kT"])
    parent = np.asarray(split["parent_counts"])
    first, second = (np.asarray(d) for d in split["daughters"])
    vesicle = np.asarray([0.0, 0.0, 1.0, 1.0]) * parent  # L@membrane, I@lumen
    assert np.array_equal(first, vesicle / 2) and np.array_equal(second, vesicle - vesicle / 2)
    assert run.rows["keys"][-1].tolist() == [split["keys"][split["followed"]]]
    # The floor refuses a split whose daughters fall below it, the parent kept (no integration).
    high = vesicle_world(x0=0.6, pool_L=48356, floor=7000 * K_L)
    high["division"] = w["division"]
    d_high = copy.deepcopy(d)
    d_high["model"]["world"] = high
    state = rate_equations._Run(parse_spec(d_high))
    before = np.asarray(state.y).copy()
    state.shear((1.0, 1, 2, None))
    assert state.events[-1]["outcome"] == "refused_floor"
    assert np.array_equal(np.asarray(state.y), before)


def test_the_limit_check_reads_the_osmotic_term_on_both_sides_of_its_kink():
    spec = parse_spec(as_representation(definition(vesicle_world())))
    problem = rate_equations.Problem(spec)
    draw = rate_equations.vesicle_draw(problem)
    rng = np.random.default_rng(7)
    sides = {bool(problem.kink(draw(rng)) > 0) for _ in range(16)}
    assert sides == {True, False}
    worst = rate_equations.limit_check(problem, np.random.default_rng(7), draw=draw)
    assert worst["states"] == rate_equations.CHECK_STATES and worst["potential"] <= 1e-6


def _edit(path, value):
    def edit(raw):
        node = raw
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        return raw

    return edit


def _population(slots=2, founder_mem=12000, min_count=100.0):
    w = population_world([12000, founder_mem], 0.3, slots=slots)
    d = population_definition(w, horizon=1.0, schedules=None)
    d["execution"]["representation"]["envelope"]["min_count"] = min_count
    return d


@pytest.mark.parametrize(
    "raw, words",
    [
        (_population(slots=65), "at most 64"),
        (_population(founder_mem=10000, min_count=11000.0), "founder 1's L@membrane holds 10000"),
        (_edit(("experiment", "schedules"),
               [{"index": 0, "kind": "replacement", "times_s": [0.5], "pool": [100, 0]}])(
            _population()), "replacement schedule is refused"),
    ],
)  # fmt: skip
def test_the_slice_s_refusals(raw, words):
    with pytest.raises(ConfigError, match=words):
        parse_spec(raw)
