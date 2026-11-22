"""FR-31's Phase A in cells.assembly_lineages@2: cells.pore_nucleation@1, a vesicle hazard per
membrane area, and cells.tension_hold@1, a held tension (docs/VESICLE_PORES_LAWS.md, tagged
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
  hold, no pore law, an osmotic lumen, sigma beyond sigma_beta/4).
These parse only: none compiles a world, and the file runs in a few seconds.
"""

import copy
import math

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
    with pytest.raises(ConfigError, match="clock is not built yet"):  # slice 1: no behaviour yet
        runner.run(spec)
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
    "no geometry": (_no_geometry, "declares cells.bilayer_geometry@1"),
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
