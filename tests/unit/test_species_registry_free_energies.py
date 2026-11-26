"""Seam E's check of reaction-level standard free energies (docs/CORE_SEAMS_DESIGN.md §7.1; the
lead's ruling (d) of 19 November 2026; registry/species_registry.check_free_energies), with the
named potential sets and the moieties it rests on (§7.3; D234's B1 and B2).

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
- an entry with a species the registry gives no potential is not compared, and one naming a species
  that is not a row of the model (water, which entries omit) is refused;
- a named potential set (B1, the lead's rulings of 20 November 2026): cells.potential_set.beard2005@1 keeps its own
  contract, and applied whole (with a matrix buffer) it parses and writes back as declared. Every
  reaction's sum of nu mu°/RT equals the cited value written out here independently, at the
  world's temperature and at 310.15 K (the lane's appendix's column), and a form's ln K_d carries
  no temperature. Planted: a set row edited after the set was applied, and the world's temperature
  changed, are each refused at the definition; the helper refuses a row whose potential comes from
  elsewhere, and a second set. The set's moieties over the rows present are required, and its
  proton buffer is checked as the set's rows are (planted, each refused: a set moiety dropped, one
  edited, and the buffer's protonated form moved);
- the set's second version (D236): cells.potential_set.beard2005@2 is @1, bit for bit on every shared row, with AMP2-,
  fixed by adenylate kinase's constant in base forms, which carries no temperature. The set
  derives it from K_AK 0.4331 on totals at the free Mg2+ of the source's state-3 buffer, and
  applied at 298.15 K every potential is the lane's appendix's to its nine decimals, the match
  written out independently (3.808553529 mM, K_base 0.388964538). Planted: the buffer's Mg2+ read
  as free, and the constant left on totals, each move AMP off the appendix; the contract refuses
  a buffer with a second ligand and a matched constant at a pH basis. AMP joins adenine and
  phosphorus at 1, required as the set's moieties are (planted, AMP at 2 in phosphorus is
  refused); the kinase's entry beside the set is admitted in base forms and refused on totals;
- an entry in kJ/mol (F's kJ form, D234's option (b)) is converted at the world's declared
  temperature: the honest pump entry given in kJ/mol is admitted, and the same entry in a world
  3 K warmer is refused, its dG°/RT moved by 1 %. Table 2's four reactions as source-derived
  entries (the cited pH 7 value with its temperature-free offset, the lead's ruling (A)) are
  admitted beside the applied set at 310.15 K and at 298.15 K; planted, the same entries on the 1 M
  basis (converted at 310.15 K and held) are refused at 298.15 K;
- the moieties (B2): a moiety naming no row is refused; the ATP-driven law's fuel mode conserves
  phosphorus and adenine, and §7.3's planted error, the same mode with Pi +2, is refused naming the
  moiety, as is an entry with Pi +2;
- an operator's reported moves (the contract's species_moieties; GENE_REGULATION_DESIGN §7.6): the
  enzyme network's two moves conserve its enzyme and substrate moieties and are admitted; planted,
  a move with P +2 is refused naming the operator, the move and the moiety, a move naming water is
  refused as naming no row, and a non-integer count is refused at the hook's reading.
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
from cells.definitions.surface_pump_v3_spec import to_dict
from cells.kinds import transporter
from cells.laws.cycles import forms
from cells.operators.species_reactions import LocalSpeciesReactions
from cells.registry import laws as law_registry
from cells.registry import species_registry
from cells.registry.kind_registry import TEMPERATURE_INDEPENDENT, FreeEnergyEntry
from tests.unit import test_cycle_forms as tf
from tests.unit import test_cycle_kind as ck
from tests.unit import test_kinds_lifecycle_declarations as kl
from tests.unit import test_transporter_kind as tk
from validation.tissue import pump_water_fixtures as water
from validation.tissue import species_reactions_fixtures as rfx

# ------------------------------------------------------------------ a kind's: the diagram pump

PUMP = kl.PUMP
HYDROLYSIS = (("ATP", -1), ("ADP", 1), ("Pi", 1))  # Its one mode's net change: H only moves.
VALENCE = dict(tf.PUMP_ROLES)
POTENTIAL = {role: tf.PUMP_MU[(role, "N")] for role in VALENCE}  # The world's, at its 1000 mM.
PUMP_ID = re.escape(PUMP.law_id)
TRANSPORTER_ID = re.escape(transporter.KIND_ID)
KIND = rf"Kind {TRANSPORTER_ID}'s standard_free_energies, entry 0"


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
    return dataclasses.replace(PUMP, law_id="seamtest.cycle.edge_pump@1", cycle=cycle)


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
    return pump_world(), kind_scope((entry()._replace(law_id="seamtest.cycle.nowhere@1"),))


def modeless(monkeypatch):
    return pump_world(), kind_scope((entry()._replace(mode="unpumped"),))


# ------------------------------------------------------------------ an operator's: the reactions

MU = dict(S=0.0, E=0.0, C=-2.0, P=-1.0)  # The enzyme network's own, at its c0 of 1 mM.
REGISTRY_C0 = 1000.0
BINDING = (("E", -1), ("S", -1), ("C", 1))  # E + S -> C, sum nu = -1.
DG = MU["C"] - MU["E"] - MU["S"]  # At the operator's c0.
OPERATOR = r"Operator cells.operator.local_species_reactions@1's standard_free_energies, entry 0"


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


# ------------------------------------------------------------------ a named set and the moieties

BEARD = species_registry.BEARD_2005.name
GAS = 6.02214076e23 * 1.380649e-23  # J/(mol K), as the source's declared constants.
TABLE_2 = {  # The source's cited values, kJ/mol at pH 7, and their turnovers (stoichiometry).
    "C4": (-122.94 * 2, (("O2", -1), ("cytc_red", -4), ("H", -4), ("cytc_ox", 4))),
    "C3": (-32.53, (("QH2", -1), ("cytc_ox", -2), ("Q", 1), ("cytc_red", 2), ("H", 2))),
    "C1": (-69.37, (("NADH", -1), ("Q", -1), ("H", -1), ("NAD", 1), ("QH2", 1))),
    "F": (36.03, (("ADP", -1), ("Pi", -1), ("H", -1), ("ATP", 1))),
}
IN_RT_310_15 = dict(C4=-159.8216, C3=19.6215, C1=-43.0189, F=-2.5923)  # The lane's appendix, §7.


def expected_RT(name, temperature_K):
    """A cited reaction's dG°/RT on the 1 M basis, written out here, independently of the
    registry: the value at the world's temperature, plus nu_H ln 1e7 for its scalar protons and,
    for synthesis, -ln(1 + 1e-7 M / k_dH) for its total phosphate."""
    value, stoichiometry = TABLE_2[name]
    x = value * 1e3 / (GAS * temperature_K) + dict(stoichiometry)["H"] * math.log(1e7)
    return x - (math.log1p(1e-7 / 1.7783e-7) if name == "F" else 0.0)


def set_world(temperature_K=None, potential_set=species_registry.BEARD_2005):
    """Heredity cell D (its Na, K, M and P) with every other row of the set and a declared matrix
    buffer, Buf (valence -1), impermeant, at 1 mM (H at 1e-4 mM), no potentials of their own."""
    raw = water.heredity_cell("D", end_time=0.002)
    if temperature_K is not None:
        raw["model"]["temperature_K"] = temperature_K
    declared = {e["id"] for e in raw["model"]["species"]}
    for row, z in (*potential_set.rows, ("Buf", -1)):
        if row not in declared:
            mM = 1e-4 if row == "H" else 1.0
            ck.add_species(raw, row, z, 0.0, {"cell_0": mM, "bath_0": mM})
            del next(e for e in raw["model"]["species"] if e["id"] == row)["standard_mu_RT"]
    return raw


def a_named_set(monkeypatch):
    """cells.potential_set.beard2005@1 applied whole, with a matrix buffer at pK 7.4. Its preconditions: the set keeps
    its own contract; every reaction's sum of nu mu°/RT is the cited value at the world's
    temperature (written out independently, expected_RT), and at 310.15 K the lane's appendix's
    column; each form's ln K_d carries no temperature; the definition writes back as declared."""
    assert species_registry.potential_set_errors(species_registry.BEARD_2005) == []
    raw = species_registry.with_potential_set(set_world(), BEARD, proton_buffers={"Buf": 7.4})
    for temperature, column in ((raw["model"]["temperature_K"], None), (310.15, IN_RT_310_15)):
        mu = species_registry.potential_set_values(
            BEARD, temperature_K=temperature, standard_concentration_mM=1000.0
        )
        for name, (_, stoichiometry) in TABLE_2.items():
            got = sum(n * mu[row] for row, n in stoichiometry)
            assert abs(got - expected_RT(name, temperature)) <= 1e-12, (name, temperature)
            if column is not None:
                assert round(got, 4) == column[name], name
        assert mu["MgATP"] - mu["ATP"] - mu["Mg"] == pytest.approx(math.log(24.0e-6), abs=1e-14)
    spec = parse_spec(raw)
    again = parse_spec(to_dict(spec))
    assert species_registry.declared(again) == species_registry.declared(spec)
    assert species_registry.declared(spec).potential_set == BEARD
    return raw, contextlib.nullcontext()


def a_set_row_edited(monkeypatch):
    """ATP's potential edited after the set was applied. The helper's own refusals stand beside
    it: a set row whose potential comes from elsewhere, and a second set."""
    raw = species_registry.with_potential_set(set_world(), BEARD)
    mixed = set_world()
    next(e for e in mixed["model"]["species"] if e["id"] == "ATP")["standard_mu_RT"] = -2.5
    with pytest.raises(ValueError, match="take their potentials from it alone"):
        species_registry.with_potential_set(mixed, BEARD)
    with pytest.raises(ValueError, match="already names the potential set"):
        species_registry.with_potential_set(raw, BEARD)
    next(e for e in raw["model"]["species"] if e["id"] == "ATP")["standard_mu_RT"] = -2.5
    return raw, contextlib.nullcontext()


def a_set_re_tempered(monkeypatch):
    raw = species_registry.with_potential_set(set_world(), BEARD)
    raw["model"]["temperature_K"] += 1.0
    return raw, contextlib.nullcontext()


def a_set_moiety_dropped(monkeypatch):
    raw = species_registry.with_potential_set(set_world(), BEARD)
    raw["model"]["moieties"] = [m for m in raw["model"]["moieties"] if m["id"] != "phosphorus"]
    return raw, contextlib.nullcontext()


def a_set_moiety_edited(monkeypatch):
    raw = species_registry.with_potential_set(set_world(), BEARD)
    (adenine,) = [m for m in raw["model"]["moieties"] if m["id"] == "adenine"]
    adenine["weights"]["ATP"] = 2
    return raw, contextlib.nullcontext()


def a_buffer_edited(monkeypatch):
    """The matrix buffer's protonated form moved after the set was applied: recorded under
    proton_buffers, so checked like the set's rows."""
    raw = species_registry.with_potential_set(set_world(), BEARD, proton_buffers={"Buf": 7.4})
    assert raw["model"]["proton_buffers"] == {"Buf": 7.4}
    (form,) = next(e for e in raw["model"]["species"] if e["id"] == "Buf")["forms"]
    form["standard_mu_RT"] += 0.1
    return raw, contextlib.nullcontext()


SECOND = species_registry.BEARD_2005_V2
KINASE = (("ADP", -2), ("ATP", 1), ("AMP", 1))  # 2 ADP3- -> ATP4- + AMP2-, in base forms.
# The lane's appendix, its potentials at 298.15 K (mu°/RT at 1 M; D236's ruled forms):
# docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20b, section 9.
APPENDIX_298 = {
    "H": 0.0, "K": 0.0, "Mg": 0.0, "O2": 0.0, "NAD": 0.0, "Q": 0.0, "cytc_ox": 0.0, "ADP": 0.0,
    "Pi": 0.0, "S_ox": 0.0, "cytc_red": 40.914814298, "QH2": 62.715891459,
    "NADH": 106.817529855, "ATP": -2.029938769, "S_red": 90.699434204, "AMP": 2.974205870,
    "MgATP": -12.667395497, "MgADP": -7.966185778, "H2PO4": -15.542437799,
}  # fmt: skip


def state_3_match():
    """(free Mg2+ in M, K_base) written out here, independently of the registry's bisection: the
    positive root of m^2 + (K_MgADP + ADP - Mg) m - Mg K_MgADP = 0 for the state-3 buffer (5.0 mM
    Mg2+, 1.3 mM ADP), then K_AK (1 + m/K_MgADP)^2 / (1 + m/K_MgATP)."""
    k_adp, k_atp, mg, adp = 347.0e-6, 24.0e-6, 5.0e-3, 1.3e-3
    b = k_adp + adp - mg
    m = (-b + math.sqrt(b * b + 4 * mg * k_adp)) / 2
    return m, 0.4331 * (1 + m / k_adp) ** 2 / (1 + m / k_atp)


def with_match(**changed):
    """cells.potential_set.beard2005@2 with its kinase's match changed (a plant)."""
    r = SECOND.reactions[-1]
    planted = r._replace(**changed.pop("reaction", {}), match=r.match._replace(**changed))
    return SECOND._replace(reactions=(*SECOND.reactions[:-1], planted))


def a_second_version(monkeypatch):
    """cells.potential_set.beard2005@2 applied whole, with AMP. Its preconditions: the set keeps its own contract;
    every row it shares with @1 has @1's double, bit for bit, at the world's temperature and at
    310.15 K; adenylate kinase's sum of nu mu°/RT is -ln K_base at both, its constant carrying no
    temperature; AMP's moieties are adenine and phosphorus at 1 each."""
    assert species_registry.potential_set_errors(SECOND) == []
    _, k_base = state_3_match()
    for temperature in (298.15, 310.15):
        first, second = (
            species_registry.potential_set_values(
                name, temperature_K=temperature, standard_concentration_mM=1000.0
            )
            for name in (BEARD, SECOND.name)
        )
        assert set(second) - set(first) == {"AMP"}
        assert all(float.hex(first[k]) == float.hex(second[k]) for k in first), temperature
        kinase = sum(n * second[row] for row, n in KINASE)
        assert abs(kinase + math.log(k_base)) <= 1e-12, temperature
    raw = species_registry.with_potential_set(set_world(potential_set=SECOND), SECOND.name)
    moieties = {m["id"]: m["weights"] for m in raw["model"]["moieties"]}
    assert moieties["phosphorus"]["AMP"] == 1 and moieties["adenine"]["AMP"] == 1
    spec = parse_spec(raw)
    assert species_registry.declared(parse_spec(to_dict(spec))) == species_registry.declared(spec)
    return raw, contextlib.nullcontext()


def the_second_version_as_the_appendix_prints_it(monkeypatch):
    """cells.potential_set.beard2005@2 applied in a world at 298.15 K: every set row's and form's mu°/RT, as the world
    declares it, is the lane's appendix's to its nine decimals, AMP's included, and the match is
    the appendix's (free Mg2+ 3.808553529 mM, K_base 0.388964538, written out independently; its
    section 7 declares no rounded constant). Planted, each
    moving AMP off the appendix: the buffer's total Mg2+ read as free (no ADP in the buffer:
    K_base 0.491) and the constant on totals left unconverted (a buffer of negligible Mg2+). The
    contract refuses a buffer with a second ligand and a matched constant at a pH basis."""
    m, k_base = state_3_match()
    assert (f"{m * 1e3:.9f}", f"{k_base:.9f}") == ("3.808553529", "0.388964538")
    raw = species_registry.with_potential_set(set_world(298.15, SECOND), SECOND.name)
    assert raw["model"]["standard_concentration_mM"] == 1000.0  # The appendix's 1 M basis.
    declared = {e["id"]: e for e in raw["model"]["species"]}
    rows = [row for row, _ in SECOND.rows]
    printed = {row: declared[row]["standard_mu_RT"] for row in rows}
    forms = [f for row in rows for f in declared[row].get("forms", ())]
    printed |= {f["id"]: f["standard_mu_RT"] for f in forms}
    nine = {k: f"{v:.9f}" for k, v in APPENDIX_298.items()}
    assert {k: f"{v:.9f}" for k, v in printed.items()} == nine
    for plant in (with_match(buffer_M=(("Mg", 5.0e-3),)), with_match(buffer_M=(("Mg", 1e-12),))):
        with monkeypatch.context() as patch:
            patch.setattr(species_registry, "POTENTIAL_SETS", {SECOND.name: plant})
            mu = species_registry.potential_set_values(
                SECOND.name, temperature_K=298.15, standard_concentration_mM=1000.0
            )
        assert f"{mu['AMP']:.9f}" != nine["AMP"], plant.reactions[-1].match
    for plant, refusal in (
        (with_match(buffer_M=(("Mg", 5.0e-3), ("ADP", 1.3e-3), ("H", 1e-7))), "holds one ligand"),
        (with_match(reaction=dict(proton_reference_M=1e-7)), "in base forms at 1 M"),
    ):
        (error,) = species_registry.potential_set_errors(plant)
        assert error.startswith("reaction for AMP: ") and refusal in error, error
    return raw, contextlib.nullcontext()


def a_second_version_amp_at_two_phosphorus(monkeypatch):
    raw = species_registry.with_potential_set(set_world(potential_set=SECOND), SECOND.name)
    (phosphorus,) = [m for m in raw["model"]["moieties"] if m["id"] == "phosphorus"]
    phosphorus["weights"]["AMP"] = 2
    return raw, contextlib.nullcontext()


def the_kinase_beside_the_second_version(k):
    """cells.potential_set.beard2005@2 applied, with adenylate kinase's entry declared beside it at the constant k (a
    planted declarer, as Table 2's): in base forms at K_base, or the constant on totals."""

    def setup(monkeypatch):
        raw = species_registry.with_potential_set(set_world(potential_set=SECOND), SECOND.name)
        planted = ((KINASE_LAW, (FreeEnergyEntry(KINASE, -math.log(k), 1000.0),)),)
        monkeypatch.setattr(species_registry, "declared_free_energies", lambda spec: planted)
        return raw, contextlib.nullcontext()

    return setup


KINASE_LAW = "The adenylate kinase law's standard_free_energies"


def with_moieties(raw, *weights):
    raw["model"]["moieties"] = [dict(id=name, weights=dict(w)) for name, w in weights]
    return raw


PHOSPHORUS = ("phosphorus", (("Pi", 1), ("ADP", 2), ("ATP", 3)))
ADENINE = ("adenine", (("ATP", 1), ("ADP", 1)))


def an_unknown_moiety_row(monkeypatch):
    return with_moieties(pump_world(), ("glucose", (("Glc", 1),))), kind_scope()


def fuel_world(law_id):
    """Held world D with one finite-fuel population of the ATP-driven law's general form (its
    fuel moves: ATP -1, ADP +1, Pi +1 per cycle) under `law_id`, phosphorus and adenine declared."""
    population = dict(ck.FINITE_POP, law=law_id)
    return with_moieties(tk.held_world(population), PHOSPHORUS, ADENINE)


def off_by_one():
    """§7.3's planted error: the ATP-driven law's form with Pi +2 per cycle."""
    law = law_registry.BUILTIN.lookup("cells.cycle.atp_driven_transporter_mass_action_positive@1")
    (mode, counts), = law.cycle.modes
    cycle = law.cycle._replace(modes=((mode, (*counts[:4], 2)),))
    return dataclasses.replace(law, law_id="seamtest.cycle.atp_pi_off_by_one@1", cycle=cycle)


def a_balanced_fuel_mode(monkeypatch):
    return fuel_world("cells.cycle.atp_driven_transporter_mass_action_positive@1"), kind_scope()


def a_fuel_mode_off_by_one(monkeypatch):
    laws = law_registry.BUILTIN.extended(off_by_one())
    return fuel_world("seamtest.cycle.atp_pi_off_by_one@1"), law_registry.scope(laws)


ENZYME = ("enzyme", (("E", 1), ("C", 1)))
SUBSTRATE = ("substrate", (("S", 1), ("C", 1), ("P", 1)))
MOVES = r"Operator cells.operator.local_species_reactions@1's"


def operator_moves(moves):
    """The enzyme network with its two moieties, its operator reporting `moves`."""

    def setup(monkeypatch):
        monkeypatch.setattr(
            LocalSpeciesReactions, "species_moieties", lambda self, declaration: moves
        )
        return with_moieties(enzyme_world(), ENZYME, SUBSTRATE), contextlib.nullcontext()

    return setup


def an_entry_off_by_one(monkeypatch):
    planted = entry()._replace(stoichiometry=(("ATP", -1), ("ADP", 1), ("Pi", 2)))
    return with_moieties(pump_world(), PHOSPHORUS), kind_scope((planted,))


def in_kJ(temperature_K):
    """The honest pump entry given in kJ/mol at the world's declared temperature (F's kJ form,
    TEMPERATURE_INDEPENDENT): dG°/RT x R T / 1000, R laws/electrochemistry's."""
    honest = entry()
    value = honest.dG_RT * GAS * temperature_K / 1000.0
    return honest._replace(dG_RT=None, dG_kJ_mol=value, dG_basis=TEMPERATURE_INDEPENDENT)


def a_kJ_entry(monkeypatch):
    raw = pump_world()
    return raw, kind_scope((in_kJ(raw["model"]["temperature_K"]),))


def a_kJ_entry_at_another_temperature(monkeypatch):
    """The same kJ entry, the world 3 K warmer: converted at the world's temperature, its dG°/RT
    moves by 1 %, far beyond the form's band, so the conversion is shown to read it."""
    raw = pump_world()
    planted = in_kJ(raw["model"]["temperature_K"])
    raw["model"]["temperature_K"] += 3.0
    return raw, kind_scope((planted,))


def table_2_entries(one_molar_at=None):
    """Table 2's four reactions as source-derived entries (F's kJ form, TEMPERATURE_INDEPENDENT),
    as a law citing Table 2 writes them (the lead's ruling (A)): the cited pH 7 value in kJ/mol
    with the temperature-free offset nu_H ln 1e7, and -ln(1 + 1e-7 M / k_dH) for synthesis's total
    phosphate. one_molar_at: the plant, the 1 M basis instead, the value converted to 1 M at that
    temperature and held constant, with no offset."""
    out = []
    for name, (value, stoichiometry) in TABLE_2.items():
        offset = dict(stoichiometry)["H"] * math.log(1e7)
        offset -= math.log1p(1e-7 / 1.7783e-7) if name == "F" else 0.0
        if one_molar_at is not None:
            value, offset = value + offset * GAS * one_molar_at / 1000.0, 0.0
        out.append(
            FreeEnergyEntry(
                stoichiometry, c0=1000.0, dG_kJ_mol=value, dG_basis=TEMPERATURE_INDEPENDENT,
                dG_RT_offset=offset,
            )
        )  # fmt: skip
    return tuple(out)


def entries_beside_the_set(temperature_K, *, one_molar_at=None):
    """The set applied in a world at temperature_K, with Table 2's entries declared beside it (a
    planted declarer: no shipped law is charge-balanced on the set's rows yet)."""

    def setup(monkeypatch):
        raw = species_registry.with_potential_set(set_world(temperature_K), BEARD)
        planted = ((TABLE_2_LAWS, table_2_entries(one_molar_at)),)
        monkeypatch.setattr(species_registry, "declared_free_energies", lambda spec: planted)
        return raw, contextlib.nullcontext()

    return setup


TABLE_2_LAWS = "Table 2's laws' standard_free_energies"


def an_entry_naming_water(monkeypatch):
    planted = entry()._replace(stoichiometry=(*HYDROLYSIS, ("H2O", -1)))
    return pump_world(), kind_scope((planted,))


TABLE = {  # name: (definition and scope, None (admitted) or the refusal's pattern)
    "an honest pump near the edge of its form band": (at_the_edge, None),
    "the same entry naming no law": (
        naming_no_law,
        rf"{KIND}: dG°/RT .* beyond the rounding bound",
    ),
    "an energy just outside the form band": (
        just_outside,
        rf"{KIND} \({PUMP_ID}'s cycle, mode pump\): .* beyond its law's form's band",
    ),
    "a law whose form gives no band": (
        bandless,
        rf"{KIND} \({re.escape(transporter.PROTON.law_id)}'s cycle, mode cycle\): .* beyond the "
        "rounding bound",
    ),
    "a law the kind does not host": (
        unhosted,
        rf"{KIND}: '{re.escape('seamtest.cycle.nowhere@1')}' is not a cycle law it hosts",
    ),
    "a mode the form lacks": (
        modeless,
        rf"{KIND}: {PUMP_ID}'s form has no mode 'unpumped'",
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
        rf"{OPERATOR}: '{PUMP_ID}' is not a cycle law it hosts",
    ),
    "a species with no registry potential": (
        reactions((FreeEnergyEntry(BINDING, DG + 1.0, 1.0),), declared=("S", "E", "P")),
        None,
    ),
    "an entry naming a species that is not a row": (
        an_entry_naming_water,
        rf"{KIND} \({PUMP_ID}'s cycle, mode pump\): it names 'H2O', which is not "
        "a species of the model",
    ),
    "a named set applied whole": (a_named_set, None),
    "a named set's row edited": (
        a_set_row_edited,
        r"species ATP \(potential set cells.potential_set.beard2005@1\): its potentials .* are not the set's",
    ),
    "a named set at another temperature": (
        a_set_re_tempered,
        r"species NADH \(potential set cells.potential_set.beard2005@1\): .* at 311\.0 K",
    ),
    "a named set's moiety dropped": (
        a_set_moiety_dropped,
        r"potential set cells.potential_set.beard2005@1: its moiety phosphorus over the rows present, .* is declared "
        "as None: a named set's moieties are required",
    ),
    "a named set's moiety edited": (
        a_set_moiety_edited,
        r"potential set cells.potential_set.beard2005@1: its moiety adenine over the rows present, .* is declared as "
        r"\{'ATP': 2, 'ADP': 1\}",
    ),
    "a named set's proton buffer edited": (
        a_buffer_edited,
        r"proton buffer Buf \(potential set cells.potential_set.beard2005@1, pK 7\.4\): its potentials .* are not",
    ),
    "the second version applied whole, with AMP": (a_second_version, None),
    "the second version as the lane's appendix prints it": (
        the_second_version_as_the_appendix_prints_it,
        None,
    ),
    "the second version's AMP at 2 in phosphorus": (
        a_second_version_amp_at_two_phosphorus,
        r"potential set cells.potential_set.beard2005@2: its moiety phosphorus over the rows present, .* is declared "
        r"as \{.*'AMP': 2\}",
    ),
    "adenylate kinase in base forms beside the second version": (
        the_kinase_beside_the_second_version(state_3_match()[1]),
        None,
    ),
    "adenylate kinase on totals beside the second version": (
        the_kinase_beside_the_second_version(0.4331),
        rf"{KINASE_LAW}, entry 0: dG°/RT .* beyond the rounding bound",
    ),
    "a moiety naming no row": (an_unknown_moiety_row, r"moiety glucose: 'Glc' is not a species"),
    "a fuel mode that conserves every moiety": (a_balanced_fuel_mode, None),
    "a fuel mode with Pi off by one": (
        a_fuel_mode_off_by_one,
        rf"Kind {TRANSPORTER_ID}'s move under {re.escape('seamtest.cycle.atp_pi_off_by_one@1')}, "
        r"mode cycle: it "
        r"changes moiety phosphorus by \+1 per turnover",
    ),
    "an entry in kJ/mol at the world's temperature": (a_kJ_entry, None),
    "an entry in kJ/mol at another temperature": (
        a_kJ_entry_at_another_temperature,
        rf"{KIND} \({PUMP_ID}'s cycle, mode pump\): dG° .* kJ/mol \(dG°/RT .* at "
        r"313\.0 K\) .* beyond its law's form's band",
    ),
    "Table 2's reactions beside the set at 310.15 K": (entries_beside_the_set(310.15), None),
    "Table 2's reactions beside the set at 298.15 K": (entries_beside_the_set(298.15), None),
    "Table 2's reactions on the 1 M basis at 298.15 K": (
        entries_beside_the_set(298.15, one_molar_at=310.15),
        rf"{TABLE_2_LAWS}, entry 0: dG° .* kJ/mol \(dG°/RT .* at 298\.15 K\) .* beyond the "
        "rounding bound",
    ),
    "an entry with Pi off by one": (
        an_entry_off_by_one,
        rf"{KIND}: it changes moiety phosphorus by \+1 per turnover",
    ),
    "an operator's moves that conserve every moiety": (
        operator_moves(
            (
                ("binding", (("E", -1), ("S", -1), ("C", 1))),
                ("catalysis", (("C", -1), ("E", 1), ("P", 1))),
            )
        ),
        None,
    ),
    "an operator's move with P off by one": (
        operator_moves((("catalysis", (("C", -1), ("E", 1), ("P", 2))),)),
        rf"{MOVES} move catalysis: it changes moiety substrate by \+1 per turnover",
    ),
    "an operator's move naming a species that is not a row": (
        operator_moves((("leak", (("S", -1), ("H2O", 1))),)),
        rf"{MOVES} move leak: it names 'H2O', which is not a species of the model",
    ),
    "an operator's move with a count that is not an integer": (
        operator_moves((("half", (("S", -1), ("P", 0.5))),)),
        rf"{MOVES} species_moieties: move 'half' is a non-empty",
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
