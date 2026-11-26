"""The composite runs the species registry's checks on its own definition (D176; the core's find).

@3's parser hook runs species_registry.check_definition on the inner definition only, where no
operator is seen. So the composite's check_definition runs it on the composite definition first:
an operator's in-step mover of a two-form row is refused, naming the operator.

The world: water and the K-anion symport on the replacement fixtures' heredity sheet (the symport's
in-step process moves its own rows), with a neutral row B at a trace that the registry declares
with two forms. Nothing moves B, so the world is admitted; with the symport's moves_in_step planted
to move B's cell rows (monkeypatch, test-only), the definition is refused, naming the symport.
"""

import copy
import math

import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import k_anion_symport
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import pump_water_fixtures as wfx

TRACE = dict(trace_mM=1e-6, floor_fmol=1e-20)
TWO_FORMS = dict(standard_mu_RT=0.0, protonated_standard_mu_RT=-7.2 * math.log(10.0))


def world():
    """[water, symport] with B declared in the registry with two forms, at a trace everywhere."""
    raw = rfx.heredity_sheet(radius=1, disc=0, dt=1e-3, end_time=0.02)
    raw = add_inventory_species(raw, "B", diffusivity_m2_per_s=1e-10, **TRACE)
    raw = copy.deepcopy(cs.frozen_definition(wfx.with_symport(wfx.with_water(raw))))
    raw["model"]["standard_concentration_mM"] = 1000.0
    for entry in raw["model"]["species"]:
        if entry["id"] == "B":
            entry.update(TWO_FORMS, background=dict(TRACE))
    return raw


def test_an_operator_moving_a_two_form_row_is_refused_by_the_composite(monkeypatch):
    spec = parse_spec(world())  # Nothing moves B: admitted.
    assert spec.model.species_registry is not None
    original = k_anion_symport.KAnionSymport.moves_in_step

    def planted(self, spec, declaration):
        return (*original(self, spec, declaration), ("B", "cell"))

    monkeypatch.setattr(k_anion_symport.KAnionSymport, "moves_in_step", planted)
    with pytest.raises(
        ConfigError, match=r"species B has two forms .*cells.operator.k_anion_symport_mass_action@1"
    ):
        parse_spec(world())
