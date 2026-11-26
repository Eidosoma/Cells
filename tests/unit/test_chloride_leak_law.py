"""The always-open chloride leak on @3, cells.channel.clleak_always_open@1 (D228 item 3, the H1 seam's Cl⁻ part;
seam F), each claim with a planted error it must catch (D187):

- it is declared on the template: gate-free, its permeant ion Cl⁻ at valence -1, code 10, with
  Cells' own leak form as its cited source and this file's test; it is registered from @3's row of
  the model table, the registry's own declaration from its module, and a definition may name it,
  while today's five keep their rows (planted: another law at its code, refused);
- a population of it parses on a patch, its ion Cl⁻ at the valence its law gives, -1 (planted, each
  refused by name: a population naming an impermeant anion, or K, neither of them the law's; a model
  whose Cl is +1; and a ratio that is not the law's);
- at availability 1 and abundance 1 it moves what a Cl-only constant-field permeability of the
  same value on its patch moves: one IMEX step of each world, with half the bath's Cl⁻ swapped
  for its impermeant anion so that Cl⁻ moves, gives the same cell and outside amounts, and the
  population's transfer and heat are the patch's (planted: half the permeability, which moves
  less).
"""

import copy
import dataclasses
from pathlib import Path

import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws.channels import clleak_always_open as clleak
from cells.registry import laws as law_registry
from cells.registry.model_table import MODELS
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures

ROOT = Path(__file__).resolve().parents[2]
CL = 2  # The chloride row: the heredity cell's species Na, K, Cl (its permeant anion), P.


def chloride_world(*, patch=None, population=None, swap=0.0):
    """The heredity cell with its permeant anion as Cl: on its patch at `patch` m/s (the cell's
    own anion permeability by default), and, given `population`, a population of the chloride
    leak at that permeability, abundance 1 and availability 1. `swap` moves that fraction of the
    bath's Cl into its impermeant anion P, which keeps the bath's charge and takes Cl⁻ off its
    equilibrium, so it moves."""
    raw = copy.deepcopy(water_fixtures.heredity_cell("D", end_time=0.004))
    m, x = raw["model"], raw["execution"]
    for species in m["species"]:
        if species["id"] == "M":
            species["id"] = "Cl"
    for holder in (*m["cells"], *m["extracellular"]):
        holder["initial_amount_fmol"]["Cl"] = holder["initial_amount_fmol"].pop("M")
    for membrane in m["membranes"]:
        anion = membrane["permeability_m_per_s"].pop("M")
        membrane["permeability_m_per_s"]["Cl"] = anion if patch is None else patch
    x["material_balance_atol_fmol"]["Cl"] = x["material_balance_atol_fmol"].pop("M")
    bath = m["extracellular"][0]["initial_amount_fmol"]
    moved, bath["Cl"] = swap * bath["Cl"], (1 - swap) * bath["Cl"]
    bath["P"] += moved
    if population is not None:
        m["channels"].append(
            dict(
                id="cl_0",
                membrane_id=m["membranes"][0]["id"],
                kinetic_law=clleak.LAW_ID,
                max_permeability_m_per_s=population,
                abundance=1.0,
                initial_gate=[],
                permeant_ions=[dict(species_id="Cl", relative_permeability=1.0)],
            )
        )
        raw["experiment"]["channel_controls"].append(
            dict(channel_id="cl_0", schedule=[dict(time=0.0, availability=1.0)])
        )
        x["channel_capacity"] = len(m["channels"])
    return raw


def anion_permeability():
    (membrane,) = water_fixtures.heredity_cell("D", end_time=0.004)["model"]["membranes"]
    return membrane["permeability_m_per_s"]["M"]


def one_step(raw):
    """(spec, the state after one IMEX step) of a world."""
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    end, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert valid
    return spec, end


def test_the_chloride_leak_is_declared_and_registered_on_at3():
    law = clleak.LAW
    assert law.errors() == [] and law.law_id == clleak.LAW_ID == "cells.channel.clleak_always_open@1"
    assert (law.code, law.gates, law.permeant) == (10, (), (("Cl", -1, 1.0),))
    assert (law.rk4_step_s, law.kinetics, law.opening, law.reads) == (None, None, None, ())
    assert law.voltage_domain_V == (-0.120, 0.060) and not law.gated
    assert law.provenance == "cited" and law.source.works == ()  # Cells' own documents.
    assert "EXCITABLE_TISSUE_EQUATIONS.md" in law.source.place
    assert law.source.licence.startswith("no numbers taken")
    test_file, test_name = law.test.split("::")
    assert (ROOT / test_file).resolve() == Path(__file__).resolve()
    assert callable(globals()[test_name])
    registry = law_registry.active()
    assert registry.lookup(law.law_id) is law and registry.module(law.law_id) == clleak.__name__
    assert clleak.__name__ in MODELS["cells.model.resolved_pump_tissue@3"].law_homes
    assert spec3.law_codes()[law.law_id] == 10 and spec3.gate_counts()[law.law_id] == 0
    assert spec3.law_permeabilities()[law.law_id] == (("Cl", 1.0),)
    assert law.law_id not in spec3.LAW_CODES
    assert {species: valence for species, valence, _ in law.permeant} == {"Cl": -1}
    with pytest.raises(ValueError, match="channel codes are distinct"):  # Planted: its code taken.
        law_registry.BUILTIN.extended(dataclasses.replace(law, law_id="tests.channel.cl_twin@1"))


def test_a_chloride_population_parses_on_its_patch_at_valence_minus_one():
    spec = parse_spec(chloride_world(patch=0.0, population=anion_permeability()))
    (population,) = [c for c in spec.model.channels if c.id == "cl_0"]
    assert population.kinetic_law == clleak.LAW_ID and population.initial_gate == ()
    assert [(i.species_id, i.relative_permeability) for i in population.permeant_ions] == [
        ("Cl", 1.0)
    ]
    impermeant = chloride_world(patch=0.0, population=anion_permeability())
    impermeant["model"]["channels"][-1]["permeant_ions"] = [
        dict(species_id="P", relative_permeability=1.0)
    ]
    potassium = chloride_world(patch=0.0, population=anion_permeability())
    potassium["model"]["channels"][-1]["permeant_ions"] = [
        dict(species_id="K", relative_permeability=1.0)
    ]
    cation = chloride_world(patch=0.0, population=anion_permeability())
    (chloride,) = [s for s in cation["model"]["species"] if s["id"] == "Cl"]
    chloride["valence"] = 1
    for holder in (*cation["model"]["cells"], *cation["model"]["extracellular"]):
        holder["fixed_charge_equivalent_fmol"] -= 2 * holder["initial_amount_fmol"]["Cl"]
    half = chloride_world(patch=0.0, population=anion_permeability())
    half["model"]["channels"][-1]["permeant_ions"][0]["relative_permeability"] = 0.5
    mismatch = f"its law's species and valence: {clleak.LAW_ID} carries "
    for raw, words in (  # Planted, each refused.
        (impermeant, mismatch + "no P, and the model declares it at valence -1"),
        (potassium, mismatch + "no K, and the model declares it at valence 1"),
        (cation, mismatch + "Cl at valence -1, and the model declares it at valence 1"),
        (half, "exactly match the named law's permeability ratios"),
    ):
        with pytest.raises(ConfigError, match=words):
            parse_spec(raw)


def test_a_chloride_population_moves_what_a_chloride_patch_does():
    permeability, swap = anion_permeability(), 0.5  # Half the bath's Cl⁻ swapped: Cl⁻ moves.
    _, through_patch = one_step(chloride_world(swap=swap))
    spec, through_population = one_step(
        chloride_world(patch=0.0, population=permeability, swap=swap)
    )
    slot = [c.id for c in spec.model.channels].index("cl_0")
    close = dict(rtol=1e-12, atol=1e-21)
    for name in ("amount_increment", "extracellular_amount_increment", "reservoir_supplied"):
        np.testing.assert_allclose(
            getattr(through_population, name), getattr(through_patch, name), **close
        )
    moved = through_population.channel_transferred[CL, slot]
    assert abs(moved) > 1e-9 and through_population.membrane_transferred[CL, 0] == 0
    np.testing.assert_allclose(moved, through_patch.membrane_transferred[CL, 0], **close)
    heat = through_population.membrane_dissipated_energy_pJ[0] + np.sum(
        through_population.channel_dissipated_energy_pJ[:, slot]
    )
    np.testing.assert_allclose(heat, through_patch.membrane_dissipated_energy_pJ[0], **close)
    # Planted: half the permeability moves less, beyond the tolerance.
    _, halved = one_step(chloride_world(patch=0.0, population=permeability / 2, swap=swap))
    assert not np.allclose(halved.amount_increment, through_patch.amount_increment, **close)
