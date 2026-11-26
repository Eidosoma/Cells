"""One standard potential per species: an operator's own potentials must agree with the registry's.

D152's reactions operator declares mu°/RT per reacting species at its own c0, and a kind (the
transporter's finite fuel) reads the species registry's. In a world where both write the same rows,
two declarations of one potential would book them at two values (the FR-4/FR-5 note's §17.3 item 2,
ruling D3's option (a)). The registry's check_definition, which the composite runs on its own
definition, converts each operator's declared potential to the registry's c0 and refuses one that
differs at more than rounding (core/species_registry.check_potentials), naming the operator.

The world: the reactions fixture's enzyme network (S, E, C and P at c0 = 1 mM), with the registry
declaring the same potentials at its own c0. Agreeing declarations are admitted at either c0; a
difference of twice the rounding bound on P is refused and half of it admitted; a species the
registry gives no potential is not compared.
"""

import math

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.registry import species_registry
from validation.tissue import species_reactions_fixtures as rfx

MU_RT = dict(S=0.0, E=0.0, C=-2.0, P=-1.0)  # The enzyme network's own, at its c0.


def world(registry_c0, *, planted=0.0, declared=tuple(MU_RT)):
    """The enzyme network with the registry's potentials for `declared`, converted to registry_c0;
    `planted` is added to P's."""
    raw = rfx.enzyme_network()
    (block,) = [o for o in raw["model"]["operators"] if o["law"] == rfx.REACTIONS]
    shift = math.log(registry_c0 / block["standard_concentration_mM"])
    raw["model"]["standard_concentration_mM"] = registry_c0
    for entry in raw["model"]["species"]:
        if entry["id"] in declared:
            entry["standard_mu_RT"] = (
                MU_RT[entry["id"]] + shift + (planted if entry["id"] == "P" else 0.0)
            )
    return raw, shift


@pytest.mark.parametrize("registry_c0", [1.0, 1000.0])
def test_potentials_agreeing_with_the_registry_are_admitted(registry_c0):
    spec = parse_spec(world(registry_c0)[0])
    assert species_registry.standard_potential(spec, "P")[1] == registry_c0


@pytest.mark.parametrize("side", [2.0, 0.5])
def test_a_potential_unlike_the_registry_s_is_refused_at_its_rounding_bound(side):
    _, shift = world(1000.0)
    registry = MU_RT["P"] + shift
    bound = species_registry.POTENTIAL_ULPS * species_registry.EPS
    bound *= abs(registry) + abs(MU_RT["P"]) + abs(shift)
    raw, _ = world(1000.0, planted=side * bound)
    if side < 1:
        parse_spec(raw)
    else:
        with pytest.raises(ConfigError, match=r"cells.operator.local_species_reactions@1 declares species 'P'"):
            parse_spec(raw)


def test_a_species_the_registry_gives_no_potential_is_not_compared():
    raw, _ = world(1000.0, planted=1.0, declared=("S", "E", "C"))
    spec = parse_spec(raw)
    assert species_registry.standard_potential(spec, "P") is None
