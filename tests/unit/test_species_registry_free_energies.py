"""Seam E's check of reaction-level standard free energies (docs/CORE_SEAMS_DESIGN.md §7.1; the
lead's ruling (d) of 19 November 2026; registry/species_registry.check_free_energies).

Each claim with its plant (D187), in one table whose every row parses a definition:
- a kind's entries are read at the definition, through F's checks, and an entry that names its
  cycle law and mode takes that law's form's band for the mode, Wegscheider's B_W plus one ulp of
  the mode's implied dG°/RT: an honest diagram pump whose constants put it near the edge of that
  band is admitted, its residual asserted to lie inside the band and well outside the rounding
  bound; planted, the same entry naming no law is refused by the rounding bound, and a dG°/RT
  just outside the form's band is refused, naming the law and mode; an entry naming a hosted law
  whose form has no constants of its own (a factored form) takes the rounding bound, and one off
  by twice it is refused;
- F's checks are the definition's: an entry naming a law the kind does not host, and a mode the
  form lacks, are refused as definition errors, naming the kind and the entry;
- an operator's entries take check_potentials' rounding at the reaction level, converted by
  (sum nu) ln(c0_registry / c0): E + S -> C has sum nu = -1, and the registry's c0 is 1000 times
  the operator's, so a missing conversion or one of the wrong sign is refused. The honest entry is
  admitted, so is one off by half the rounding bound, and one off by twice it is refused; an entry
  naming a law is refused (an operator hosts none);
- an entry with a species the registry gives no potential is not compared.
The pump's rows use the kinds owner's diagram pump world (tests/unit/test_kinds_lifecycle_
declarations.py); the operator's, the reactions fixture's enzyme network at a registry c0 of
1000 mM (as tests/unit/test_species_potentials.py).
"""

import contextlib
import dataclasses
import math
import re
from decimal import Decimal, localcontext

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import transporter
from cells.laws.cycles import forms
from cells.operators.species_reactions import LocalSpeciesReactions
from cells.registry import laws as law_registry
from cells.registry import species_registry
from cells.registry.kind_registry import FreeEnergyEntry
from tests.unit import test_cycle_forms as tf
from tests.unit import test_cycle_kind as ck
from tests.unit import test_kinds_lifecycle_declarations as kl
from tests.unit import test_transporter_kind as tk
from validation.tissue import species_reactions_fixtures as rfx

# ------------------------------------------------------------------ a kind's: the diagram pump

PUMP = kl.PUMP
HYDROLYSIS = (("ATP", -1), ("ADP", 1), ("Pi", 1))  # Its one mode's net change: H only moves.
VALENCE = dict(tf.PUMP_ROLES)
POTENTIAL = {role: tf.PUMP_MU[(role, "N")] for role in VALENCE}  # The world's, at its 1000 mM.
KIND = r"Kind cells\.transporter@1's standard_free_energies, entry 0"


def residual(value):
    """dG°/RT less the world's sum of nu mu°/RT, both at the world's c0 (the diagram's standard
    state, so no conversion), exactly."""
    with localcontext() as ctx:
        ctx.prec = species_registry.FREE_ENERGY_DIGITS
        return Decimal(value) - sum(n * Decimal(POTENTIAL[s]) for s, n in HYDROLYSIS)


def bands(law):
    """(the ruling's band, the rounding bound, Wegscheider's record) of the law's one mode at the
    world's potentials. The ruling's band is computed here from forms.wegscheider, not from the
    form's own method: B_W plus one ulp of the mode's implied dG°/RT, the entry's one rounding."""
    w = forms.wegscheider(law.cycle, 0, VALENCE, POTENTIAL, 1000.0)
    _, value, _ = forms.implied_free_energy(law.cycle, 0)
    magnitude = sum(abs(n * POTENTIAL[s]) for s, n in HYDROLYSIS) + abs(value)
    rounding = species_registry.POTENTIAL_ULPS * species_registry.EPS * magnitude
    return w.band + Decimal(math.ulp(value)), Decimal(rounding), w


def edge_law(fraction=0.9):
    """The diagram pump with its fuel edge's forward constant moved so that Wegscheider's residual
    sits at `fraction` of its band: still an honest law, its entry being its constants' own."""
    form = PUMP.cycle
    w = forms.wegscheider(form, 0, VALENCE, POTENTIAL, 1000.0)
    factor = math.exp(fraction * float(w.band) - float(w.constant))  # Its cycle runs fuel forward.
    edges = tuple(
        e._replace(forward=e.forward._replace(k0_per_s=e.forward.k0_per_s * factor))
        if e.id == "fuel" else e
        for e in form.diagram.edges
    )  # fmt: skip
    cycle = form._replace(diagram=form.diagram._replace(edges=edges))
    return dataclasses.replace(PUMP, law_id="seamtest.edge_pump@1", cycle=cycle)


EDGE = edge_law()


def entry(law=PUMP):
    """The law's entry as the transporter's hook gives it: its constants' implied dG°/RT at the
    diagram's standard state, naming the law and its mode."""
    net, value, c0 = forms.implied_free_energy(law.cycle, 0)
    assert tuple(net.items()) == HYDROLYSIS
    return FreeEnergyEntry(HYDROLYSIS, value, c0, law.law_id, "pump")


def pump_world(law=PUMP):
    raw = kl.pump_world()
    (population,) = raw["model"][transporter.MODEL_KEY]
    population["law"] = law.law_id
    return raw


@contextlib.contextmanager
def kind_scope(declared=None):
    """The transporter, or one whose hook returns `declared`, beside the pumps' laws."""
    kind = transporter.TRANSPORTER
    if declared is not None:
        kind = dataclasses.replace(kind, standard_free_energies=lambda declaration: declared)
    laws = law_registry.BUILTIN.extended(*ck.TEST_LAWS, PUMP, EDGE)
    with tk.scoped(kind), law_registry.scope(laws):
        yield


def at_the_edge(monkeypatch):
    """The edge pump through the transporter's own hook. Its preconditions: Wegscheider admits it,
    and its residual lies inside the form's band, near its edge, and far outside the rounding
    bound, so the form's band is what admits it."""
    band, rounding, w = bands(EDGE)
    value = entry(EDGE).dG_RT
    assert w.admitted
    assert Decimal("0.8") * band <= abs(residual(value)) <= Decimal("0.95") * band
    assert abs(residual(value)) > 4 * rounding
    return pump_world(EDGE), kind_scope()


def naming_no_law(monkeypatch):
    return pump_world(EDGE), kind_scope((entry(EDGE)._replace(law_id=None, mode=None),))


def just_outside(monkeypatch):
    band, _, _ = bands(PUMP)
    honest = entry(PUMP)
    assert abs(residual(honest.dG_RT)) < band / 100  # The pump itself is consistent.
    return pump_world(), kind_scope((honest._replace(dG_RT=honest.dG_RT + 1.1 * float(band)),))


def bandless(monkeypatch):
    """An entry naming a hosted law whose form has no constants of its own (the proton law's
    factored form), off by twice the rounding bound: that bound, not a form's band, refuses it."""
    _, rounding, _ = bands(PUMP)
    honest = entry(PUMP)
    planted = honest._replace(
        dG_RT=honest.dG_RT + 2.0 * float(rounding), law_id=transporter.PROTON.law_id, mode="cycle"
    )
    return pump_world(), kind_scope((planted,))


def unhosted(monkeypatch):
    return pump_world(), kind_scope((entry()._replace(law_id="seamtest.nowhere@1"),))


def modeless(monkeypatch):
    return pump_world(), kind_scope((entry()._replace(mode="unpumped"),))


# ------------------------------------------------------------------ an operator's: the reactions

MU = dict(S=0.0, E=0.0, C=-2.0, P=-1.0)  # The enzyme network's own, at its c0 of 1 mM.
REGISTRY_C0 = 1000.0
BINDING = (("E", -1), ("S", -1), ("C", 1))  # E + S -> C, sum nu = -1.
DG = MU["C"] - MU["E"] - MU["S"]  # At the operator's c0.
OPERATOR = r"Operator local_species_reactions@1's standard_free_energies, entry 0"


def enzyme_world(declared=tuple(MU)):
    """The enzyme network with the registry's potentials for `declared`, converted to its c0."""
    raw = rfx.enzyme_network()
    (block,) = [o for o in raw["model"]["operators"] if o["law"] == rfx.REACTIONS]
    assert block["standard_concentration_mM"] == 1.0
    raw["model"]["standard_concentration_mM"] = REGISTRY_C0
    for item in raw["model"]["species"]:
        if item["id"] in declared:
            item["standard_mu_RT"] = MU[item["id"]] + math.log(REGISTRY_C0)
    return raw


def operator_rounding():
    """check_potentials' rounding of the binding entry, in floats: its plants sit at half and
    twice it, far from where the evaluation's own rounding could matter."""
    shift = math.log(REGISTRY_C0)
    magnitude = sum(abs(n * (MU[s] + shift)) for s, n in BINDING) + abs(DG) + abs(-1 * shift)
    return species_registry.POTENTIAL_ULPS * species_registry.EPS * magnitude


def reactions(entries, declared=tuple(MU)):
    def setup(monkeypatch):
        monkeypatch.setattr(
            LocalSpeciesReactions, "standard_free_energies", lambda self, declaration: entries
        )
        return enzyme_world(declared), contextlib.nullcontext()

    return setup


BOUND = operator_rounding()
TABLE = {  # name: (definition and scope, None (admitted) or the refusal's pattern)
    "an honest pump near the edge of its form band": (at_the_edge, None),
    "the same entry naming no law": (
        naming_no_law,
        rf"{KIND}: dG°/RT .* beyond the rounding bound",
    ),
    "an energy just outside the form band": (
        just_outside,
        rf"{KIND} \(seamtest\.diagram_pump@1's cycle, mode pump\): .* beyond its law's form's band",
    ),
    "a law whose form gives no band": (
        bandless,
        rf"{KIND} \({re.escape(transporter.PROTON.law_id)}'s cycle, mode cycle\): .* beyond the "
        "rounding bound",
    ),
    "a law the kind does not host": (
        unhosted,
        rf"{KIND}: 'seamtest\.nowhere@1' is not a cycle law it hosts",
    ),
    "a mode the form lacks": (
        modeless,
        rf"{KIND}: seamtest\.diagram_pump@1's form has no mode 'unpumped'",
    ),
    "an honest operator entry converted by sum nu": (
        reactions((FreeEnergyEntry(BINDING, DG, 1.0),)),
        None,
    ),
    "an operator entry off by half the rounding bound": (
        reactions((FreeEnergyEntry(BINDING, DG + 0.5 * BOUND, 1.0),)),
        None,
    ),
    "an operator entry off by twice the rounding bound": (
        reactions((FreeEnergyEntry(BINDING, DG + 2.0 * BOUND, 1.0),)),
        rf"{OPERATOR}: dG°/RT .* beyond the rounding bound",
    ),
    "an operator entry naming a law": (
        reactions((FreeEnergyEntry(BINDING, DG, 1.0, PUMP.law_id, "pump"),)),
        rf"{OPERATOR}: 'seamtest\.diagram_pump@1' is not a cycle law it hosts",
    ),
    "a species with no registry potential": (
        reactions((FreeEnergyEntry(BINDING, DG + 1.0, 1.0),), declared=("S", "E", "P")),
        None,
    ),
}


@pytest.mark.parametrize("name", list(TABLE))
def test_each_declared_free_energy_is_held_to_its_band(name, monkeypatch):
    setup, refusal = TABLE[name]
    raw, scope = setup(monkeypatch)
    with scope:
        if refusal is None:
            parse_spec(raw)
        else:
            with pytest.raises(ConfigError, match=refusal):
                parse_spec(raw)
