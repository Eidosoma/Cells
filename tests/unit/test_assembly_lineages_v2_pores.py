"""FR-31's Phase A in cells.model.assembly_lineages@2: cells.assembly_hazard.pore_nucleation@1, a vesicle hazard per
membrane area, and cells.operator.tension_hold@1, a held tension (docs/VESICLE_PORES_LAWS.md, tagged
pores-laws-sheet-registered-2026-11-22; D287; the lead's rulings of 22 November 2026).

New file for a new feature. Each claim with a planted error it must catch (D187):
- the law's closed form at a point, its temperature slope against a finite difference, and the
  six-point fit recovering known parameters from rows made by the law (§2, §4, §8);
- the declarations: a world's `hazard` and an experiment's `tension_holds` parse, round trip with
  their fingerprint, and name their pieces in the run's components, in both modes (planted: a hold
  without its pore law, refused);
- every refusal Phase A owns, each by its own message: the area's geometry, a step that changes a
  membrane place's count (an isomerisation keeping the membrane's total included), a species with
  no pool to return to, the parameters' forms, the hold's form and count, the cross-checks (no
  hold, no pore law, an osmotic lumen, sigma beyond sigma_beta/4);
- the clock in a single lineage, with chemistry running and idle: the rupture at t* = E/k_v from
  the sheet alone (E from domain 7), its pore row and released state, the hold's work, the
  opening's heat from the sheet's closed forms, the event's heat as its two parts, the books
  closed, the crossing draw discarded at the pore; eta_298 moving only how the heat divides
  (planted: a release booked from the closed state, which the ledger refuses); a vesicle alive at
  the horizon ending complete; the bundle's pores, tension_hold and check blocks read back;
- the clock in a population: each founder's own t* and freed slot, idle and running chemistry's
  end statuses (Q3), each moiety conserved, the relations' lysis events by the pore law paid by
  the hold; a transfer taking a removed vesicle's clock with it; a tie with a schedule stop, or
  between two vesicles (planted: one threshold for every key), refused;
- the clock's endpoints decided exactly (the Lean lane's case, 22 November 2026): a founder whose
  t* rounds onto the hold's end, or the horizon, from an exact crossing beyond it survives in both
  modes, and one binary64 step either side the exact and rounded decisions agree (planted at that
  cut: the rounded comparison t* <= cut, main's before the fix, which ruptures it);
- the pair's identity on its probe and at the world's states (planted: eta_m without its T
  factor, refused);
- FR-22's rung P: cuts before and between the ruptures resumed bitwise, the clocks in the host's
  document; a cut at a pending rupture's time, and a restart whose clocks differ (planted: a
  changed threshold draw), refused.

World-compiling cost: one single-lineage program and one population program (K = 3), about 20
runs, most of them a second or two once compiled; 81.7 s for the whole file on a shared light
CPU, most of it the first run's geometry probe verdict, world report and compile (the timed lane's
row is in tests/test_tiers.json). The endpoint rows add 16 runs on those programs, without the
diagnostic, 0.10-0.22 s per row on a shared light CPU. Reason: the claims are the runs' own
clocks, books and records.
"""

import copy
import functools
import math
from fractions import Fraction

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    IDEAL_MIXING,
    MASS_ACTION,
    MEMBRANE_PERMEATION,
    OSMOTIC_LUMEN,
    PHASE_EXCHANGE,
    PORE_NUCLEATION,
    SHARED_POOL,
    TENSION_HOLD,
    model,
    runner,
)
from cells.models.assembly_lineages_v2 import pore_nucleation as law
from cells.models.assembly_lineages_v2.spec import world_id
from tests.assembly_lineage_v2_fixtures import definition, species
from tests.assembly_lineage_v2_fixtures import world as ol1_world
from validation.vesicle_pores import fit_rows

E_A = 27e3


def test_the_rate_is_the_sheets_closed_form():
    sigma, t, log_nu, gamma = 7.5e-3, 300.0, 21.0, 11e-12
    expected = (log_nu + 0.5 * math.log(sigma) - 1.5 * math.log(t) - E_A / (law.R * t)
                - math.pi * gamma**2 / (sigma * law.K_B * t))  # fmt: skip
    assert law.log_rate_per_area(sigma, t, log_nu, gamma, E_A) == pytest.approx(
        expected, abs=0, rel=1e-15
    )
    assert law.log_rate(2e-9, sigma, t, log_nu, gamma, E_A) == pytest.approx(
        expected + math.log(2e-9), abs=0, rel=1e-15
    )


@pytest.mark.parametrize("sigma", [3.3e-3, 7.0e-3, 8.0e-3])
def test_the_temperature_slope_matches_a_finite_difference(sigma):
    t, h, gamma = 300.0, 1e-3, 11e-12
    numeric = (law.log_rate_per_area(sigma, t + h, 0.0, gamma, E_A)
               - law.log_rate_per_area(sigma, t - h, 0.0, gamma, E_A)) / (2 * h)  # fmt: skip
    assert law.dlog_rate_dt(sigma, t, gamma, E_A) == pytest.approx(numeric, rel=1e-7)


def test_the_fit_recovers_the_laws_parameters():
    ln_c, gamma = 20.5, 11.3e-12
    ses = [0.03, 0.044, 0.028, 0.038, 0.025, 0.0365]
    conditions = [(t, s) for t in (1e6 / 3356, 1e6 / 3279) for s in (7.0e-3, 7.5e-3, 8.0e-3)]
    points = [
        (t, s, law.log_rate_per_area(s, t, ln_c, gamma, E_A), se)
        for (t, s), se in zip(conditions, ses, strict=True)
    ]
    out = fit_rows.fit(points, E_A)
    assert out["estimates"]["ln_C"] == pytest.approx(ln_c, rel=1e-10)
    assert out["estimates"]["gamma_N"] == pytest.approx(gamma, rel=1e-10)
    assert out["chi2"] < 1e-12 and out["dof"] == 4


# ------------------------------------------------------------------ a pore world (Phase A)

Q = 1e-19  # m², the quantum
K_L = 60  # quanta of one L molecule per leaflet
N_L = 10  # the founder's L molecules: W = 600 quanta, A = q W / 2 = 3e-17 m²
T_K = 300.0
GAMMA = 11e-12  # N: sigma_beta = pi Gamma^2/(k_B T) = 0.0918 N/m at T_K
SIGMA = 7.5e-3  # N/m: sigma_beta/sigma = 12.2
ETA_298 = 3e-10
U = "unsourced; test"


def hazard_block(log_c=34.0, area=Q * K_L * N_L / 2.0):
    """The pore law's world block, ln(A nu_A) = log_c at the founder's area (k_v near 1/s at
    SIGMA and T_K)."""
    values = {"nu_A": math.exp(log_c) / area, "gamma_N": GAMMA, "E_A_J_per_mol": E_A,
              "eta_298_Pa_s_m": ETA_298}  # fmt: skip
    return {"law": PORE_NUCLEATION, **{k: {"value": v, "provenance": U} for k, v in values.items()}}


def pore_world(*, population=False, lumen=True):
    """A bilayer vesicle of L, with a declared lumen of S, in a pool where A and B interconvert and
    S enters the lumen; the pore law. No step changes a membrane place's count."""
    pool = [{"id": n, "kind": "finite"} for n in ("L", "S", "A", "B")]
    steps = [{"id": "flip", "phase": "pool", "reactants": {"A": 1}, "products": {"B": 1},
              "law": MASS_ACTION, "forward_rate_per_s": 2.0}]  # fmt: skip
    phases = {"pool": {"volume_L": 1e-21, "species": pool}, "membrane": {"species": ["L"]}}
    vesicle = {"L@membrane": N_L}
    if lumen:
        phases["lumen"] = {"volume_L": 1e-22, "species": ["S"]}
        steps.append({"id": "entry", "locus": "membrane", "reactants": {"S@pool": 1},
                      "products": {"S@lumen": 1}, "law": MEMBRANE_PERMEATION,
                      "permeability_m_per_s": {"value": 3e-9, "provenance": U}})  # fmt: skip
        vesicle["S@lumen"] = 2
    out = {
        "units": {"time": "s", "temperature_K": T_K, "standard_concentration_mM": 1000.0},
        "conventions": {"free_energy_form": "discrete", "condensed_measure": "multinomial",
                        "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
                        "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept",
                        "exchange_encounter": "insertion_area"},
        "species": [species("L", {"l": 1}, solution=0.0, bilayer=-2.0),
                    species("S", {"s": 1}, solution=0.0), species("A", {"a": 1}, solution=0.0),
                    species("B", {"a": 1}, solution=0.5)],
        "phases": phases,
        "steps": steps,
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"L@pool": 3, "S@pool": 5, "A@pool": 4, "B@pool": 1, **vesicle},
        "geometry": {"law": BILAYER_GEOMETRY, "area_quantum_m2": Q,
                     "area_per_leaflet": {"L": {"quanta": K_L, "provenance": U}},
                     "vesicle_floor": {"quanta": K_L, "provenance": U},
                     "closure_cost_kT": {"value": 12.5, "provenance": U}},
        "hazard": hazard_block(),
    }  # fmt: skip
    if population:
        out["population"] = {
            "structure": SHARED_POOL,
            "slots": 3,
            "founders": [vesicle, dict(vesicle, **{"L@membrane": N_L + 2})],
        }
        out["founder"] |= {k: 0 for k in vesicle}
    return out


def pore_definition(w=None, *, sigma=SIGMA, start=0.0, end=50.0, horizon=5.0, **kw):
    w = pore_world() if w is None else w
    d = definition(w, horizon=horizon, molecules=64, **kw)
    if "population" in w:
        d["execution"]["mode"] = "population"
    d["experiment"]["tension_holds"] = [
        {"index": 0, "sigma_N_per_m": sigma, "start_s": start, "end_s": end}
    ]
    return d


@pytest.mark.parametrize("population", [False, True])
def test_a_pore_world_parses_round_trips_and_names_its_pieces(population):
    d = pore_definition(pore_world(population=population))
    spec = parse_spec(d)
    world = spec.model.world
    assert world.hazard[0] == PORE_NUCLEATION and spec.experiment.tension_holds[0].sigma == SIGMA
    again = parse_spec(spec.to_dict())
    assert again.fingerprint == spec.fingerprint and world_id(again.model.world) == world_id(world)
    assert spec.to_dict()["model"]["world"]["hazard"] == d["model"]["world"]["hazard"]
    assert spec.to_dict()["experiment"]["tension_holds"] == d["experiment"]["tension_holds"]
    parts = model.components(spec)
    assert PORE_NUCLEATION in parts["laws"] and parts["operators"] == [TENSION_HOLD]
    log_nu, gamma, e_a, eta = law.parameters(world)
    assert (gamma, e_a, eta) == (GAMMA, E_A, ETA_298)
    assert log_nu == pytest.approx(34.0 - math.log(Q * K_L * N_L / 2.0), rel=1e-15)
    planted = copy.deepcopy(d)  # a hold without its pore law
    del planted["model"]["world"]["hazard"]
    with pytest.raises(ConfigError, match="only reader in Phase A is the pore law"):
        parse_spec(planted)


def _drop_hazard_value(d):
    del d["model"]["world"]["hazard"]["eta_298_Pa_s_m"]


def _membrane_join(d):
    d["model"]["world"]["steps"].append(
        {"id": "join", "locus": "membrane", "reactants": {"L@pool": 1},
         "products": {"L@membrane": 1}, "law": PHASE_EXCHANGE,
         "insertion_velocity_m_per_s": {"value": 1e-8, "provenance": U}})  # fmt: skip


def _isomerisation(d):
    """L -> P in the membrane at equal quanta: the membrane's total is kept, its places' counts
    are not."""
    w = d["model"]["world"]
    w["species"].append(species("P", {"l": 1}, solution=0.0, bilayer=-2.5))
    w["phases"]["pool"]["species"].append({"id": "P", "kind": "finite"})
    w["phases"]["membrane"]["species"].append("P")
    w["geometry"]["area_per_leaflet"]["P"] = {"quanta": K_L, "provenance": U}
    w["founder"] |= {"P@pool": 0, "P@membrane": 0}
    w["steps"].append(
        {
            "id": "iso",
            "phase": "membrane",
            "reactants": {"L": 1},
            "products": {"P": 1},
            "law": MASS_ACTION,
            "forward_rate_per_s": 1.0,
        }
    )


def _homeless(d):
    w = d["model"]["world"]
    w["species"].append(species("M", {"m": 1}, bilayer=-3.0))
    w["phases"]["membrane"]["species"].append("M")
    w["geometry"]["area_per_leaflet"]["M"] = {"quanta": K_L, "provenance": U}
    w["founder"]["M@membrane"] = 1


def _no_geometry(d):
    d["model"]["world"] = ol1_world(held=False, regular=False, catalysis=False) | {
        "hazard": hazard_block()
    }


def _shell(d):
    from tests.unit.test_assembly_lineages_v2_geometry import shell_world

    d["model"]["world"] = shell_world() | {"hazard": hazard_block()}


def _osmotic(d):
    w = d["model"]["world"]
    w["conventions"]["lumen_volume"] = "osmotic"
    del w["phases"]["lumen"]["volume_L"]
    w["free_energy"].append(
        {"law": OSMOTIC_LUMEN, "outside_osmolarity_mM": {"value": 1e4, "provenance": U}}
    )
    w["geometry"]["sigma_max_N_per_m"] = {"value": 0.01, "provenance": U}


def _set_hold(**fields):
    def apply(d):
        d["experiment"]["tension_holds"][0].update(fields)

    return apply


def _second_hold(d):
    holds = d["experiment"]["tension_holds"]
    holds.append(dict(holds[0], index=1, start_s=60.0, end_s=70.0))


def _no_hold(d):
    del d["experiment"]["tension_holds"]


def _hold_key(d):
    d["experiment"]["tension_holds"][0]["rate_N_per_m_per_s"] = 1.0


def _set_hazard(name, value):
    def apply(d):
        d["model"]["world"]["hazard"][name] = value

    return apply


REFUSALS = {
    "no geometry": (_no_geometry, "declares cells.assembly_geometry.bilayer_geometry@1"),
    "a prescribed shell": (_shell, "a prescribed shell has no tension"),
    "a membrane join": (_membrane_join, "step join changes L@membrane's count"),
    "an isomerisation keeping the total": (_isomerisation, "step iso changes"),
    "a membrane species with no pool": (_homeless, "M has none"),
    "a missing parameter": (_drop_hazard_value, r"missing=\['eta_298_Pa_s_m'\]"),
    "a parameter without provenance": (
        _set_hazard("gamma_N", {"value": GAMMA}), r"gamma_N is \{value, provenance\}"),
    "a zero line tension": (
        _set_hazard("gamma_N", {"value": 0.0, "provenance": U}), "finite and positive"),
    "no hold": (_no_hold, "the experiment declares one in tension_holds"),
    "a second hold": (_second_hold, "a second hold, or an overlapping one, is refused"),
    "a hold's unknown key": (_hold_key, "a tension hold's keys are"),
    "a zero tension": (_set_hold(sigma_N_per_m=0.0), "finite and positive"),
    "an end before the start": (_set_hold(start_s=3.0, end_s=3.0), "must come after its start_s"),
    "a negative start": (_set_hold(start_s=-1.0), "finite and nonnegative"),
    "an osmotic lumen": (_osmotic, "refuses lumen_volume osmotic"),
    "beyond sigma_beta/4": (_set_hold(sigma_N_per_m=0.023), "beyond sigma_beta/4"),
}  # fmt: skip


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_every_refusal_of_phase_a(case):
    change, message = REFUSALS[case]
    d = pore_definition()
    change(d)
    with pytest.raises(ConfigError, match=message):
        parse_spec(d)
    assert parse_spec(pore_definition()).model.world.hazard is not None  # the control parses


# ------------------------------------------------------------------ the clock and the rupture

K_B, N_AV = 1.380649e-23, 6.02214076e23
AREA = Q * K_L * N_L / 2.0  # m², the founder's


def sheet_time(spec, key=0, area=AREA, start=0.0):
    """(t*, E, ln k_v) from the sheet alone (§2, §4, §5): E = -ln u from domain 7 (the key,
    counter 0), k_v = A nu_A sigma^(1/2) T^(-3/2) exp(-E_A/(R T)) exp(-pi Gamma^2/(sigma k_B T))."""
    from cells.models.assembly_lineages_v2 import streams

    stream = streams.stream_key_data(model.layout(spec).base_key, key, "pore")
    energy = -math.log(float(streams.uniforms(stream, 0, 1)[0]))
    hazard = spec.model.world.hazard[1]
    sigma = spec.experiment.tension_holds[0].sigma
    log_k = (math.log(area) + math.log(hazard["nu_A"][0]) + 0.5 * math.log(sigma)
             - 1.5 * math.log(T_K) - E_A / (K_B * N_AV * T_K)
             - math.pi * GAMMA**2 / (sigma * K_B * T_K))  # fmt: skip
    return start + energy / math.exp(log_k), energy, log_k


def sheet_opening(spec, area=AREA, eta=ETA_298):
    """(w, q_open) in k_BT from the sheet's §3 and §7: w = sigma pi r_c^2 / k_BT, and
    q_open = ln(A n_s) - sigma_beta/sigma with n_s's closed form at 298.15 K."""
    nu = spec.model.world.hazard[1]["nu_A"][0]
    sigma = spec.experiment.tension_holds[0].sigma
    r_c = GAMMA / sigma
    w = sigma * math.pi * r_c**2 / (K_B * T_K)
    n_s = (4 * math.pi * eta * nu * math.exp(-E_A / (K_B * N_AV * 298.15))
           / (math.sqrt(math.pi) * GAMMA * K_B**-0.5 * 298.15))  # fmt: skip
    delta_f = 2 * math.pi * r_c * GAMMA / (K_B * T_K) - math.log(area * n_s)
    return w, -delta_f + w


@functools.cache
def single_run(idle=False, eta=ETA_298, horizon=5.0, plant=None):
    """One held vesicle (running chemistry, or idle with every rate zero), in the diagnostic
    mode; `plant` names a planted error."""
    w = pore_world()
    w["hazard"]["eta_298_Pa_s_m"]["value"] = eta
    if idle:
        w["founder"].update({"A@pool": 0, "B@pool": 0, "S@pool": 0, "S@lumen": 0})
    d = pore_definition(w, horizon=horizon, uniforms=True)
    d["experiment"]["diagnostic"] = True
    spec = parse_spec(d)
    if plant == "release_from_the_closed_state":  # the release ignores the open pore's dF
        from cells.models.assembly_lineages_v2 import pore_clock

        real = pore_clock.opening
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(pore_clock, "opening", lambda *a: real(*a)[:2] + (0.0,))
            return spec, runner.run(spec)
    return spec, runner.run(spec)


@pytest.mark.parametrize("idle", [False, True])
def test_a_held_vesicle_ruptures_at_its_threshold_and_its_books_close(idle):
    spec, run = single_run(idle)
    t_star, energy, log_k = sheet_time(spec)
    assert run.status == "lysed" and run.closure["holds"]
    (event,) = run.pores["events"]
    assert event["time_s"] == pytest.approx(t_star, rel=1e-13)
    assert event["threshold_E"] == pytest.approx(energy, rel=1e-14) and event["counter"] == 0
    assert math.log(event["rate_per_s"]) == pytest.approx(log_k, abs=1e-12)
    kinds, times = run.rows["row_kind"], run.rows["row_time"]
    assert kinds[-2:].tolist() == [9, 2] and times[-1] == times[-2] == event["time_s"]
    # The released state: the vesicle empty, its molecules at their pool places, totals kept.
    # The lane's own state (run.final) is the state at t*, before the release.
    names = [p.name for p in spec.model.world.places]
    before, after = run.final["counts"][: len(names)], run.rows["place_count"][-1]
    vesicle = {"L@membrane": "L@pool", "S@lumen": "S@pool"}
    for place, pool in vesicle.items():
        i, j = names.index(place), names.index(pool)
        assert after[i] == 0 and after[j] == before[j] + before[i]
        assert event["release"]["returned"].get(pool, 0) == before[i]
    # The hold's work, the opening's heat, and the row's heat as the event's two parts.
    w, q_open = sheet_opening(spec)
    hold = run.rows["tension_hold_work_kT"]
    assert hold[:-2].tolist() == [[0.0]] * (len(hold) - 2)
    assert hold[-2:, 0] == pytest.approx([w, w], rel=1e-13) and event["work_kT"] == hold[-1, 0]
    assert event["opening_heat_kT"] == pytest.approx(q_open, abs=1e-10)
    heat = run.rows["event_heat_kT"]  # the pore row's, over the device's sum at its last event
    assert heat[-2] - float(run.final["heat"]) == pytest.approx(
        event["opening_heat_kT"] + event["release"]["release_heat_kT"], abs=1e-12
    )
    # The diagnostic record: the crossing draw discarded at the pore, no step event lysed.
    body, arrays = run.diagnostic["body"], run.diagnostic["arrays"]
    assert body["fates"][-1] == "discarded_at_pore" and arrays["draw_fate"][-1] == 3
    assert not arrays["event_lysed"].any() and body["pore_events"] == run.pores["events"]
    assert arrays["pore_draw_threshold"].tolist() == [event["threshold_E"]]
    assert arrays["pore_draw_time"].tolist() == [event["time_s"]]


def test_eta_moves_the_opening_and_the_release_apart_and_a_closed_state_release_is_refused():
    """eta_298 sets the opening's dF and so its heat (the sheet's §7), and the release from the
    open state takes the difference back: the event's heat, its time and the books are unchanged
    (planted: a release booked from the closed state, which the ledger refuses)."""
    spec, base = single_run()
    _, scaled = single_run(eta=10 * ETA_298)
    (a,), (b,) = base.pores["events"], scaled.pores["events"]
    assert b["time_s"] == a["time_s"] and b["work_kT"] == a["work_kT"]
    assert b["opening_heat_kT"] - a["opening_heat_kT"] == pytest.approx(math.log(10), abs=1e-12)
    assert b["release"]["release_heat_kT"] - a["release"]["release_heat_kT"] == pytest.approx(
        -math.log(10), abs=1e-12
    )
    assert scaled.closure["holds"]
    assert scaled.rows["event_heat_kT"][-1] == pytest.approx(
        base.rows["event_heat_kT"][-1], abs=1e-12
    )
    _, planted = single_run(plant="release_from_the_closed_state")
    assert planted.status == "refused" and not planted.closure["holds"]


def test_a_vesicle_alive_at_the_horizon_ends_complete_and_the_bundle_reads_back(tmp_path):
    """A horizon before t*: no rupture, no pore row, the hold's column zero, and idle chemistry
    ends complete, never inert (Q3). The ruptured run's bundle reads back with its pores and
    tension_hold blocks, the pore stream in its identity, and the pore row's legend."""
    from cells.models.assembly_lineages_v2 import records

    spec, ruptured = single_run(idle=True)
    t_star = ruptured.pores["events"][0]["time_s"]
    _, alive = single_run(idle=True, horizon=t_star / 2)
    assert alive.status == "complete" and alive.pores["events"] == []
    assert 9 not in alive.rows["row_kind"] and not alive.rows["tension_hold_work_kT"].any()
    assert alive.rows["row_time"][-1] == t_star / 2 and alive.closure["holds"]
    records.write_run(tmp_path / "bundle", ruptured)
    _, record, arrays = records.read(tmp_path / "bundle")
    assert record["pores"]["events"] == ruptured.pores["events"]
    assert record["pores"]["causes"] == {"pore": 1, "threshold": 0}
    assert record["tension_hold"] == [
        {
            "index": 0,
            "sigma_N_per_m": SIGMA,
            "start_s": 0.0,
            "end_s": 50.0,
            "payer": "source:tension_hold/0",
        }
    ]
    assert record["stream"]["domains"]["pore"] == 7 and "pore_clock" in record["ssa"]
    assert record["check"]["pores"]["probe"]["holds"]
    assert record["records"]["row_kind"]["legend"]["9"] == "pore"
    assert "lysed" in record["lifecycle"]["statuses"] and record["end"]["status"] == "lysed"
    assert arrays["tension_hold_work_kT"].shape == (len(arrays["row_time"]), 1)


FOUNDERS = ((0, AREA), (1 << 32, Q * K_L * (N_L + 2) / 2.0))  # (key, area) of slots 0 and 1


@functools.cache
def population_run(idle=False, horizon=5.0, transfer=None, start=0.0):
    """Two held vesicles on one pool (running chemistry, or idle), in the diagnostic mode, with a
    transfer keeping one of them when `transfer` gives its time, and the hold from `start`."""
    w = pore_world(population=True)
    if idle:
        w["founder"].update({"A@pool": 0, "B@pool": 0, "S@pool": 0})
        for founder in w["population"]["founders"]:
            founder["S@lumen"] = 0
    d = pore_definition(w, horizon=horizon, uniforms=True, start=start)
    d["experiment"]["diagnostic"] = True
    if transfer is not None:
        d["experiment"]["schedules"] = [{"index": 3, "kind": "transfer", "times_s": [transfer],
                                         "K_keep": 1, "fresh_pool": [3, 5, 4, 1]}]  # fmt: skip
    spec = parse_spec(d)
    return spec, runner.run(spec)


@pytest.mark.parametrize("idle", [False, True])
def test_each_vesicle_of_a_population_ruptures_at_its_own_threshold(idle, tmp_path):
    """Each founder's rupture time is its own E/k_v (domain 7 at its key, its area), its slot is
    freed on its pore row, the hold's column sums the openings and the books close. A population
    whose vesicles have all ruptured ends inert when its chemistry is idle, complete when its pool
    goes on (Q3). Each rupture is a lysis by the pore law, paid by the hold's source."""
    from cells.models.assembly_lineages_v2 import records
    from cells.records import relations as rel

    spec, run = population_run(idle)
    events = {e["key"]: e for e in run.pores["events"]}
    assert set(events) == {key for key, _ in FOUNDERS} and run.closure["holds"]
    for slot, (key, area) in enumerate(FOUNDERS):
        t_star, energy, _ = sheet_time(spec, key=key, area=area)
        e = events[key]
        assert e["slot"] == slot and e["time_s"] == pytest.approx(t_star, rel=1e-13)
        assert e["threshold_E"] == pytest.approx(energy, rel=1e-14)
        w, q_open = sheet_opening(spec, area=area)
        assert e["work_kT"] == pytest.approx(w, rel=1e-13)
        assert e["opening_heat_kT"] == pytest.approx(q_open, abs=1e-10)
        (r,) = np.flatnonzero((run.rows["row_kind"] == 9) & (run.rows["row_time"] == e["time_s"]))
        assert run.rows["slot_key"][r, slot] == -1 and not run.rows["slot_count"][r, slot].any()
        assert run.rows["slot_key"][r - 1, slot] == key
    works = sum(e["work_kT"] for e in events.values())
    assert run.rows["tension_hold_work_kT"][-1, 0] == pytest.approx(works, rel=1e-13)
    assert run.status == ("inert" if idle else "complete")
    totals = run.rows["pool_count"] + run.rows["slot_count"].sum(axis=1)
    moiety = {"L": "l", "S": "s", "A": "a", "B": "a"}  # A and B interconvert
    places = [moiety[p.species] for p in spec.model.world.places]
    for name in set(places):  # a closed world: each moiety's total is kept through the ruptures
        column = totals[:, [i for i, x in enumerate(places) if x == name]].sum(axis=1)
        assert (column == column[0]).all()
    assert (run.diagnostic["arrays"]["draw_fate"] == 3).sum() == 2
    records.write_run(tmp_path / "p", run)
    _, tables = rel.read(tmp_path / "p")
    lyses = [e for e in tables["events"] if e.kind == "lysis"]
    assert len(lyses) == 2 and {(e.by, e.source) for e in lyses} == {
        (PORE_NUCLEATION, "source:tension_hold/0")
    }
    (payer,) = [s for s in tables["sources"] if s.id == "source:tension_hold/0"]
    assert payer.payer_of == "tension_hold_work_kT" and payer.declared_by == TENSION_HOLD


def test_a_population_s_clocks_end_with_their_vesicles_and_ties_are_refused(monkeypatch):
    """A transfer that removes a vesicle before its t* takes its rupture with it; a vesicle alive
    at the horizon with idle chemistry ends complete. A rupture time shared with a schedule stop,
    or with another vesicle's (planted: one threshold for every key), is refused at the start."""
    from cells.models.assembly_lineages_v2 import pore_clock

    spec, run = population_run(transfer=0.03)
    (event,) = run.pores["events"]
    (removed,) = [life for life in run.population["lives"] if life["end_reason"] == "removed"]
    assert event["key"] != removed["key"] and run.closure["holds"]
    t_star = sheet_time(spec, key=event["key"], area=dict(FOUNDERS)[event["key"]])[0]
    assert event["time_s"] == pytest.approx(t_star, rel=1e-13)
    _, alive = population_run(idle=True, horizon=0.05)
    assert alive.status == "complete" and alive.pores["events"] == []
    assert alive.rows["slot_key"][-1].tolist()[:2] == [key for key, _ in FOUNDERS]
    _, ruptured = population_run(idle=True)
    d = pore_definition(pore_world(population=True), uniforms=True)
    first = min(e["time_s"] for e in ruptured.pores["events"])
    d["experiment"]["schedules"] = [{"index": 1, "kind": "replacement", "times_s": [first],
                                     "pool": [3, 5, 4, 1]}]  # fmt: skip
    with pytest.raises(ConfigError, match="the time of a schedule stop"):
        runner.run(parse_spec(d))
    d = pore_definition(pore_world(population=True), uniforms=True)
    d["model"]["world"]["population"]["founders"][1]["L@membrane"] = N_L  # equal areas
    monkeypatch.setattr(pore_clock, "threshold", lambda *a: (0.5, math.log(2.0)))
    with pytest.raises(ConfigError, match="Two vesicles' pores open at the same time"):
        runner.run(parse_spec(d))


@pytest.mark.parametrize("cut", ["before", "at", "after"])
def test_the_clock_decides_its_endpoints_exactly(cut, monkeypatch):
    """The Lean lane's case (22 November 2026). Held from 1 s, the founder's t* = 1 + E/k_v rounds
    onto 1.4042194113471334 s, while its exact crossing, from the same binary E and k_v, lies
    2.4e-17 s beyond it. Both endpoints are decided exactly (FORMAT_PORES.md, "The clock"): with
    the hold's end, or the horizon, at that t* the founder survives, in both modes; one binary64
    step either side, the exact and the rounded decisions agree (planted at the middle cut: the
    rounded comparison t* <= cut, main's before the fix, which ruptures it in all four runs)."""
    from cells.models.assembly_lineages_v2 import pore_clock

    _, base = single_run()  # E and k_v as the engine draws and records them
    (e,) = base.pores["events"]
    energy, rate = e["threshold_E"], e["rate_per_s"]
    t_star = 1.0 + energy / rate  # the engine's t* from 1 s, as it rounds
    cuts = {"before": math.nextafter(t_star, -math.inf), "at": t_star,
            "after": math.nextafter(t_star, math.inf)}  # fmt: skip
    exact = Fraction(1.0) + Fraction(energy) / Fraction(rate)
    assert (exact <= Fraction(cuts[cut])) == (cut == "after")
    assert (t_star == cuts[cut] and exact > Fraction(cuts[cut])) == (cut == "at")  # on the edge

    def founder(population, at_end):
        """The founder's ruptures, (t, E, k_v), with the cut as the hold's end or the horizon."""
        end, horizon = (cuts[cut], 2.0) if at_end else (50.0, cuts[cut])
        d = pore_definition(pore_world(population=population), start=1.0, end=end,
                            horizon=horizon, uniforms=True)  # fmt: skip
        run = runner.run(parse_spec(d))
        assert run.closure["holds"]
        return [(x["time_s"], x["threshold_E"], x["rate_per_s"]) for x in run.pores["events"]
                if x["key"] == 0]  # fmt: skip

    modes = [(population, at_end) for population in (False, True) for at_end in (True, False)]
    ruptured = [[(t_star, energy, rate)]] * len(modes)
    assert [founder(*m) for m in modes] == (ruptured if cut == "after" else [[]] * len(modes))
    if cut == "at":  # planted: the rounded comparison
        monkeypatch.setattr(pore_clock, "reaches", lambda e, k, s, c: s + float(e) / k <= c)
        assert [founder(*m) for m in modes] == ruptured


# ------------------------------------------------------------------ the pair check, checkpoints


def test_the_pore_pair_keeps_its_identity_and_a_wrong_damping_law_is_refused(monkeypatch):
    """The sheet's §7: ln k_v - ln P = -(dF - w)/k_BT on the check's probe (T from 260 to 380 K)
    and at the world's own states, both recorded in run.json's check (planted: eta_m without its
    T/298.15 factor, so P's temperature law no longer matches k_v's, which the probe refuses)."""
    from cells.models.assembly_lineages_v2 import balance

    verdict = balance.pore_verdict()
    assert verdict["holds"] and verdict["probe"]["max_abs_deviation_ln"] <= balance.ATOL
    _, run = single_run()
    assert run.pores["check"]["probe"] == verdict
    assert run.pores["check"]["world"]["max_abs_deviation_ln"] <= balance.ATOL
    real = law.eta_m
    monkeypatch.setattr(
        law, "eta_m", lambda t, e_a, eta=ETA_298: real(t, e_a, eta) * law.T_REF_K / t
    )
    with pytest.raises(ConfigError, match="the pore's pair fails"):
        balance._pore_verdict.__wrapped__()


@pytest.mark.parametrize("where", ["before_both", "between", "after_both"])
def test_a_resumed_pore_world_is_the_uninterrupted_world_after_the_cut(where, tmp_path,
                                                                       monkeypatch):  # fmt: skip
    """FR-22's rung P with the pore clock, the hold from 0.5 s: a cut before both ruptures, between
    them, or after both (no vesicle left), written, read back and resumed, is the uninterrupted
    world after the cut,
    bitwise (rows, the hold's column, the trace, the uniforms, the lives, the final lane); the
    host's document keeps each living vesicle's clock, and the two segments' ruptures are the
    uninterrupted run's. Refused: a cut at a pending rupture's time, and a restart whose clocks are
    not its definition's (planted: a threshold draw changed after the cut)."""
    from cells.models.assembly_lineages_v2 import checkpoints, pore_clock
    from tests.unit.test_assembly_lineages_v2_checkpoints import differences

    spec, a = population_run(start=0.5)
    for e in a.pores["events"]:  # the hold's start shifts each rupture time by 0.5 s
        key = e["key"]
        assert e["time_s"] == pytest.approx(
            sheet_time(spec, key=key, area=dict(FOUNDERS)[key], start=0.5)[0], rel=1e-13
        )
    times = a.trace["event_time"]
    first, second = sorted(e["time_s"] for e in a.pores["events"])
    ruptured = {"before_both": 0, "between": 1, "after_both": 2}[where]
    edge = (first, second, second)[ruptured]  # the cut: one event before it, or one after
    k = int(np.searchsorted(times, edge)) + (1 if ruptured == 2 else -1)
    assert 1 <= k < len(times) and (ruptured == 0 or times[k - 1] > first)
    b1 = runner.run(spec, stop=k)
    assert b1.status == "stopped" and len(b1.pores["events"]) == ruptured
    living = sorted(clock["key"] for clock in b1.resume["doc"]["pores"])
    assert living == sorted(life["key"] for life in b1.population["lives"]
                            if life["end_reason"] == "censored")  # fmt: skip
    checkpoints.write(tmp_path / "cut", b1.checkpoint())
    saved = checkpoints.read(tmp_path / "cut")
    b2 = runner.run(spec, start=saved)
    assert differences(a, b1, b2, k) == [] and b2.closure["holds"]
    assert b1.pores["events"] + b2.pores["events"] == a.pores["events"]
    if ruptured == 2:  # no clock is left to plant against
        assert b1.resume["doc"]["pores"] == [] and b2.pores["events"] == []
        return
    with monkeypatch.context() as patch:  # planted: the clocks rebuilt at the restart differ
        draw = pore_clock.threshold
        patch.setattr(pore_clock, "threshold", lambda *x: (0.5, draw(*x)[1] + 1.0))
        with pytest.raises(ConfigError, match="pore clocks are not its definition's"):
            runner.run(spec, start=saved)
    b1.resume["doc"]["pores"][0]["t_star"] = float(b1.final["time"])
    with pytest.raises(ConfigError, match="a vesicle's rupture time, is refused"):
        b1.checkpoint()
