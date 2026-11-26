"""cells.assembly_representation.rate_equations@1's pore clock (OL6 slice S3; the OL6 design note's §3.5, §3.6, §4).

Closed forms and identities only, never a comparison with exact events (D304: Protocol D is
registered before any such reading):
- the regression identity: a held vesicle whose area no step changes ruptures at
  t* = start_s + E/k_v, pore_clock.rupture_time's time with the same domain-7 E, to the crossing
  tolerance; the opening books Phase A's w = σ_β/σ (paid by the hold) and q_open; the bundle's
  pores and tension_hold blocks;
- pores against no pores: a vesicle whose tension comes from F (an osmotic lumen, an
  area-changing join) takes exactly its pore-free twin's steps, so their rows are identical bit for
  bit until the first opening, which falls below σ_max (the twin lyses at σ_max later); the
  opening's booking is opening_from_f's, w = 0;
- each daughter draws its own threshold at birth (domain 7, its key, counter 0), in a single
  lineage and in a population;
- the slice's refusals: an area-changing step under a hold (T2), σ_max beyond σ_β/4 with σ from F,
  a pore law with no tension, a hold with an osmotic lumen (tension_hold's own words) (exact events
  admit the σ-from-F world since OL6 S4: test_assembly_lineages_v2_pores_device.py);
- the clock's bound (D309): |U^H| <= 1e-10 + 2e-3 |ΔH| per accepted step, planted at the bound
  (accepted) and just beyond it (refused) in both its parts, and Protocol D's D7 at 50 nm, which
  the absolute 1e-10 refused (its §7.2), running to its opening in (d) alone.
A new file for the slice (D224): the S2 files are at 39 and 47 s of tier 2's 90; four worlds
compiled here (a held vesicle, a σ-from-F vesicle and its twin, the daughters' two), about 60 s
on a shared light CPU, most of it the limit's generic verdict and the twin pair at rtol 1e-12.
D7's row adds a fifth world, about 20 s (D309's follow-up: the one world the bound was changed for).
"""

import copy
import json
import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    IDEAL_MIXING,
    MASS_ACTION,
    PHASE_EXCHANGE,
    PORE_NUCLEATION,
    SHEAR_FISSION,
    pore_clock,
    rate_equations,
    records,
    runner,
)
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_rate_equations_vesicles import (
    K_L,
    Q,
    U,
    as_representation,
    population_definition,
    population_world,
    species,
    vesicle_world,
)
from validation.assembly_lineages_v2 import limit_qualification

jax.config.update("jax_enable_x64", True)

T_K = 296.15
N_MEM = 20000  # the held vesicle's lipids: A = q K_L N / 2 = 6e-14 m²
SIGMA = 7.5e-3  # N/m, the hold's; with Γ = 11 pN, σ_β/σ = 12.4 and k_v is about 0.7/s
HOLD = {"index": 0, "sigma_N_per_m": SIGMA, "start_s": 0.5, "end_s": 8.0}
TIGHT = {"rtol": 1e-12, "atol_count": 1e-9}  # §3.5's clock bound in a σ-from-F world (S3's note)


def hazard(gamma, log_c, area):
    """The pore law's world block, ln(A ν_A) = log_c at `area`."""
    values = {"nu_A": math.exp(log_c) / area, "gamma_N": gamma, "E_A_J_per_mol": 27e3,
              "eta_298_Pa_s_m": 3e-10}  # fmt: skip
    return {"law": PORE_NUCLEATION, **{k: {"value": v, "provenance": U} for k, v in values.items()}}


def held_world():
    """A bilayer vesicle of L in a pool where A and B interconvert; no step reads or changes the
    membrane's count but its geometry, so its area is fixed (Phase A's world, at large counts)."""
    return {
        "units": {"time": "s", "temperature_K": T_K, "standard_concentration_mM": 1000.0},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": "multinomial",
                        "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept",
                        "exchange_encounter": "insertion_area"},
        "species": [species("L", {"l": 1}, solution=0.0, bilayer=-9.43),
                    species("A", {"a": 1}, solution=0.0), species("B", {"a": 1}, solution=-0.5)],
        "phases": {"pool": {"volume_L": 1e-17,
                            "species": [{"id": n, "kind": "finite"} for n in "LAB"]},
                   "membrane": {"species": ["L"]}},
        "steps": [{"id": "flip", "phase": "pool", "reactants": {"A": 1}, "products": {"B": 1},
                   "law": MASS_ACTION, "forward_rate_per_s": 2.0}],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"L@pool": 0, "A@pool": 5000, "B@pool": 3000, "L@membrane": N_MEM},
        "geometry": {"law": BILAYER_GEOMETRY, "area_quantum_m2": Q,
                     "area_per_leaflet": {"L": {"quanta": K_L, "provenance": U}},
                     "vesicle_floor": {"quanta": 1000 * K_L, "provenance": U},
                     "closure_cost_kT": {"value": 25.0, "provenance": U}},
        "hazard": hazard(11e-12, 34.0, Q * K_L * N_MEM / 2.0),
    }  # fmt: skip


def held_definition(world=None):
    d = as_representation(definition(held_world() if world is None else world, horizon=10.0,
                                     observations=(0.25, 1.0, 5.0)))  # fmt: skip
    d["experiment"]["tension_holds"] = [dict(HOLD)]
    return d


def tense_world(**kw):
    """S2's deflating vesicle (L leaves for a small pool, so its tension rises through the kink to
    σ_max = 2 mN/m), with the pore law at Γ = 4 pN (σ_β/4 = 3.07 mN/m) and σ from F."""
    w = vesicle_world(**kw)
    w["hazard"] = hazard(4e-12, 30.0, Q * K_L * 12000 / 2.0)
    return w


def tight(d):
    d["execution"]["representation"]["integrator"].update(TIGHT)
    return d


@pytest.fixture(scope="module")
def held_run():
    spec = parse_spec(held_definition())
    return spec, runner.run(spec)


def test_a_held_vesicle_ruptures_at_start_plus_e_over_its_rate(held_run, tmp_path):
    spec, run = held_run
    world = spec.model.world
    assert run.status == "lysed" and run.rows["row_kind"].tolist() == [
        "start", "observed", "observed", "lysis"]  # fmt: skip
    (event,) = run.events
    area = Q * K_L * N_MEM / 2.0
    base = rate_equations._Run(spec).base_key
    _, energy = pore_clock.threshold(base, 0, 0)
    t_star, hold, log_k = pore_clock.rupture_time(world, spec.experiment.tension_holds, area,
                                                  energy)  # fmt: skip
    rate = math.exp(log_k)
    tolerance = 10 * (rate_equations.H_ERROR + 1e-9 * max(1.0, energy))
    assert event["cause"] == "pore" and event["threshold_E"] == energy and hold.index == 0
    assert abs(event["time_s"] - t_star) <= tolerance / rate
    assert event["rate_per_s"] == pytest.approx(rate, rel=1e-12)
    # H grows at k_v only inside the hold: 0 at 0.25 s, k_v (1.0 − 0.5) at 1.0 s.
    h_rows = run.rows["pore_clock_H"][:, 0]
    assert h_rows[1] == 0.0 and h_rows[2] == pytest.approx(rate * 0.5, rel=1e-12)
    # Phase A's opening, paid by the hold: w = σ_β/σ, q_open = −ΔF_open + w.
    work, heat, delta_f = pore_clock.opening(world, area, SIGMA)
    recorded = (event["work_kT"], event["opening_heat_kT"], event["delta_F_kT"])
    assert recorded == (work, heat, delta_f)
    assert run.rows["tension_hold_work_kT"][-1, 0] == work and run.rows["work_kT"][-1] >= work
    assert run.ledger["closes"] and run.moieties["closes"]
    assert run.statistics["pores"]["largest_clock_error"] <= rate_equations.H_ERROR
    record = json.loads((records.write_run(tmp_path, run) / "run.json").read_text())
    assert record["pores"]["causes"] == {"pore": 1, "threshold": 0}
    assert record["tension_hold"][0]["payer"] == "source:tension_hold/0"
    assert {law["id"]: law["limit_formulas"] for law in record["laws"]}[PORE_NUCLEATION] == (
        rate_equations.PORE_LIMIT)


def test_the_clock_s_error_bound_refuses_a_run(held_run):
    """D309's bound planted on one accepted step of the held vesicle's run: an estimate at
    1e-10 + 2e-3 |ΔH| is accepted and H advances by ΔH; one just beyond it is refused and H stays.
    ΔH = 0 is the absolute part; at ΔH = 0.25 the absolute 1e-10 alone would refuse both."""
    spec, _ = held_run
    for increment in (0.0, 0.25):
        bound = rate_equations.H_ERROR + rate_equations.H_RELATIVE * increment
        for factor, refused in ((1.0, False), (1.0 + 1e-9, True)):
            state = rate_equations._Run(spec)
            carried = {name: np.full(state.H.shape, value) for name, value in (
                ("increment", increment), ("error", -factor * bound), ("k1", 0.0), ("k2", 0.0))}
            if refused:
                with pytest.raises(ConfigError, match="the pore clock's error estimate, .* passes "
                                   "its bound 1e-10 \\+ 0.002 \\|dH\\|"):  # fmt: skip
                    state.advance_clock(carried)
                assert np.all(state.H == 0.0)
            else:
                state.advance_clock(carried)
                assert np.all(state.H == increment) and state.clock_fraction == 1.0


def test_d7_s_50_nm_world_runs_under_the_relative_bound():
    """Protocol D's D7 at 50 nm, the registered definition at seed 1, in (d) alone (nothing is
    compared with exact events): its clock's estimate passes the absolute 1e-10 that refused it
    (Protocol D's §7.2) but stays within D309's bound, and it opens by its pore at H = E."""
    spec = parse_spec(limit_qualification.definition("D7", 50.0, 1, True))
    run = runner.run(spec)
    pores = run.statistics["pores"]
    assert run.status == "lysed" and [e["cause"] for e in run.events] == ["pore"]
    assert pores["largest_clock_error"] > rate_equations.H_ERROR
    assert 0.0 < pores["largest_clock_error_fraction"] <= 1.0
    assert (pores["clock_error_bound"], pores["clock_error_relative"]) == (1e-10, 2e-3)
    (opening,) = run.events
    energy = opening["threshold_E"]
    assert abs(opening["clock_H"] - energy) <= 10 * (rate_equations.H_ERROR + 1e-12 * energy)
    assert run.ledger["closes"] and run.moieties["closes"] and run.dissipation["holds"]


def test_pores_against_no_pores_rows_are_identical_until_the_first_opening():
    observations = (0.5, 1.0, 1.5, 2.0, 3.0)
    twin_d = tight(as_representation(definition(vesicle_world(), horizon=50.0,
                                                observations=observations)))  # fmt: skip
    pore_d = copy.deepcopy(twin_d)
    pore_d["model"]["world"] = tense_world()
    twin, pore = runner.run(parse_spec(twin_d)), runner.run(parse_spec(pore_d))
    assert pore.status == "lysed" and twin.status == "lysed"
    (opening,), (lysis,) = pore.events, twin.events
    assert opening["cause"] == "pore" and lysis["cause"] == "threshold"
    assert opening["time_s"] < lysis["time_s"] and opening["sigma_N_per_m"] < 2e-3
    n = len(pore.rows["row_kind"]) - 1  # every row before the opening's
    assert pore.rows["row_kind"].tolist()[:n] == ["start", "observed", "observed", "observed",
                                                  "observed"]  # fmt: skip
    for name, values in twin.rows.items():
        assert np.array_equal(values[:n], pore.rows[name][:n]), name
    # The opening: H = E (domain 7, key 0) to the crossing tolerance, and no work with σ from F.
    spec = parse_spec(pore_d)
    _, energy = pore_clock.threshold(rate_equations._Run(spec).base_key, 0, 0)
    assert opening["threshold_E"] == energy
    assert abs(opening["clock_H"] - energy) <= 10 * (rate_equations.H_ERROR + 1e-12 * energy)
    assert (opening["work_kT"], opening["opening_heat_kT"], opening["delta_F_kT"]) == (
        pore_clock.opening_from_f(spec.model.world, opening["area_m2"],
                                  opening["sigma_N_per_m"]))  # fmt: skip
    assert pore.ledger["closes"] and pore.moieties["closes"] and pore.dissipation["holds"]


def _shear_world(population):
    if population:
        w = population_world([12000, 10000], 0.3, slots=4)
        w["hazard"] = hazard(4e-12, 30.0, Q * K_L * 12000 / 2.0)
        w["division"] = {"law": SHEAR_FISSION}
        return population_definition(w, horizon=3.0, schedules=None)
    w = tense_world(x0=0.6, pool_L=48356)
    w["division"] = {"law": SHEAR_FISSION, "continuation": "uniform"}
    return as_representation(definition(w, horizon=3.0))


@pytest.mark.parametrize("population", [False, True])
def test_each_daughter_draws_its_own_threshold_at_birth(population):
    spec = parse_spec(_shear_world(population))
    state = rate_equations._Run(spec)
    founders = [d[0] for d in state.draws]
    assert founders == ([0, 1 << 32] if population else [0])
    state.t = 1.0
    state.shear((1.0, 0, 2, None))
    splits = [e for e in state.events if e.get("outcome") == "split"]
    assert splits and all(e["kind"] == "fission" for e in splits)
    born = [d for d in state.draws if d[4] == 1.0]
    for key, counter, u, energy, _ in born:
        assert counter == 0 and (u, energy) == pore_clock.threshold(state.base_key, key, 0)
    for slot in np.flatnonzero(state.alive):
        assert state.H[slot] == 0.0 and state.E[slot] == pore_clock.threshold(
            state.base_key, int(state.keys[slot]), 0)[1]  # fmt: skip
    expected = sum(len(e["keys"]) for e in splits) if population else 1  # the followed one
    assert len(born) == expected


def _join(d):
    d["model"]["world"]["steps"].append(
        {"id": "join", "locus": "membrane", "reactants": {"L@pool": 1},
         "products": {"L@membrane": 1}, "law": PHASE_EXCHANGE,
         "insertion_velocity_m_per_s": {"value": 1e-8, "provenance": U}})  # fmt: skip
    d["model"]["world"]["founder"]["L@pool"] = 1000
    return d


def _no_hold(d):
    del d["experiment"]["tension_holds"]
    return d


def _hold_on_tense(d):
    d["experiment"]["tension_holds"] = [dict(HOLD, sigma_N_per_m=1e-3)]
    return d


def _wide(d):
    d["model"]["world"]["hazard"] = hazard(2e-12, 30.0, Q * K_L * 12000 / 2.0)
    return d


@pytest.mark.parametrize(
    "build, words",
    [
        (lambda: _join(held_definition()), "changes L@membrane's count under a held tension"),
        (lambda: _wide(tight(as_representation(definition(tense_world())))), "beyond sigma_beta/4"),
        (lambda: _no_hold(held_definition()), "reads a tension: a held one"),
        (lambda: _hold_on_tense(as_representation(definition(tense_world()))),
         "refuses lumen_volume osmotic"),
    ],
    ids=["T2", "sigma_max", "no tension", "hold and osmotic"],
)  # fmt: skip
def test_the_clock_s_refusals(build, words):
    with pytest.raises(ConfigError, match=words):
        parse_spec(build())
