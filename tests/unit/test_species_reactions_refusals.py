"""Tier-1 tests of local_species_reactions@1's definition refusals (D152 version 1, milestone 1).

docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §1.1, §1.3, §1.4, §2.1, §2.2, §2.5, §3.1, §4.6, §5 and
§7.2. Host side, no compile. Each refusal names its reason:
* the species (charged, permeant, undeclared, moieties, standard potentials, identity), the laws
  (molecularity, coefficients, closure, sources and sinks, Michaelis-Menten's one substrate and its
  read-only catalyst, factors on driven laws only, every parameter's domain), the sites (a held
  bath, undeclared nodes) and the schedule (the dt grid, the horizon, time 0, coverage);
* the composition: RK4; more than 7 species; an identity that differs from a D150 operator's, in
  either order; a turnover route on a row the network writes (a catalyst's row is admitted); a cell
  route on a slot that replacement@1 replaces (outside routes compose); and every provider or closer
  of the declared volumes, masks and outside anchors, with the operators version 1 composes with
  admitted (the contract's structure check, and one refusal through the parser).
"""

import copy
import re

import pytest

from cells.core import pump_composite_spec as cs
from cells.core.inventory_species import add_inventory_species
from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import OPERATORS
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

LAW = "local_species_reactions@1"


def block(raw):
    return next(b for b in raw["model"]["operators"] if b["law"] == LAW)


def reaction(raw, name):
    return next(r for r in block(raw)["reactions"] if r["id"] == name)


def controls(raw, name):
    return next(c for c in raw["experiment"]["reaction_controls"] if c["reaction_id"] == name)


def species_entry(raw, name):
    return next(s for s in block(raw)["species"] if s["id"] == name)


def uncatalysed(raw, rate):
    """The conversion without its catalyst, so declared with a maximum rate (V_max, mM/s)."""
    conversion = reaction(raw, "conversion")
    conversion.update(catalyst=None, max_rate_mM_per_s=rate)
    del conversion["catalytic_rate_per_s"]


CASES = {
    # The species.
    "charged": (lambda raw: species_entry(raw, "S").update(id="Na"), "neutral species only"),
    "permeant": (
        lambda raw: raw["model"]["membranes"][1]["permeability_m_per_s"].update(S=1e-9),
        "zero membrane, junction and channel permeability only",
    ),
    "undeclared species": (
        lambda raw: species_entry(raw, "S").update(id="Q"),
        "does not declare",
    ),
    "species twice": (
        lambda raw: block(raw)["species"].append(copy.deepcopy(species_entry(raw, "S"))),
        "lists a species twice",
    ),
    "species keys": (lambda raw: species_entry(raw, "S").pop("standard_mu_RT"), "missing"),
    "moiety count": (
        lambda raw: species_entry(raw, "S").update(moieties={"X": 0}),
        "moiety counts are positive integers",
    ),
    "moiety fraction": (
        lambda raw: species_entry(raw, "S").update(moieties={"X": 1.5}),
        "moiety counts are positive integers",
    ),
    "no moiety": (
        lambda raw: species_entry(raw, "S").update(moieties={}),
        "integer counts",
    ),
    "standard potential": (
        lambda raw: species_entry(raw, "S").update(standard_mu_RT=float("inf")),
        "finite number",
    ),
    "evidence": (
        lambda raw: species_entry(raw, "S").update(catalogue=dict(catalogue="c", entry="e")),
        "kind of evidence",
    ),
    "standard concentration": (
        lambda raw: block(raw).update(standard_concentration_mM=0.0),
        "standard_concentration_mM must be > 0",
    ),
    # The reactions and their laws.
    "unknown law": (lambda raw: reaction(raw, "supply").update(law="hill"), "law is one of"),
    "law keys": (
        lambda raw: reaction(raw, "supply").update(saturation_mM=1.0),
        "unknown=['saturation_mM']",
    ),
    "unlisted species": (
        lambda raw: reaction(raw, "supply").update(products={"Q": 1}),
        "not a listed species",
    ),
    "fractional coefficient": (
        lambda raw: reaction(raw, "catalysis").update(reactants={"C": 1.5}),
        "positive integers",
    ),
    "boolean coefficient": (
        lambda raw: reaction(raw, "catalysis").update(reactants={"C": True}),
        "positive integers",
    ),
    "zero coefficient": (
        lambda raw: reaction(raw, "catalysis").update(reactants={"C": 0}),
        "positive integers",
    ),
    "unbalanced": (
        lambda raw: reaction(raw, "binding").update(products={"C": 2}),
        "neither a pure source",
    ),
    "no change": (
        lambda raw: reaction(raw, "catalysis").update(products={"C": 1}),
        "changes no species",
    ),
    "open passive": (
        lambda raw: reaction(raw, "binding").update(reactants={}, products={"S": 1}),
        "passive reaction binding must be closed",
    ),
    "passive factors": (
        lambda raw: reaction(raw, "binding").update(
            factors=[rfx.hill("hill_activation", "S", 1e-3, 1.0)]
        ),
        "takes no factors",
    ),
    "passive molecularity": (
        lambda raw: reaction(raw, "binding").update(reactants={"E": 2, "S": 2}, products={"C": 2}),
        "molecularity above 3",
    ),
    "driven molecularity": (
        lambda raw: reaction(raw, "catalysis").update(reactants={"S": 4}, products={"P": 4}),
        "molecularity above 3",
    ),
    "second substrate": (
        lambda raw: reaction(raw, "conversion").update(
            reactants={"S": 1, "C": 1}, products={"P": 1, "C": 1}
        ),
        "consumes one substrate",
    ),
    "substrate order": (
        lambda raw: reaction(raw, "conversion").update(reactants={"S": 2}, products={"P": 2}),
        "consumes one substrate",
    ),
    "unlisted catalyst": (
        lambda raw: reaction(raw, "conversion").update(catalyst="Q"),
        "is not a listed species",
    ),
    "written catalyst": (
        lambda raw: reaction(raw, "conversion").update(catalyst="P"),
        "read, never written",
    ),
    "saturation": (
        lambda raw: reaction(raw, "conversion").update(saturation_mM=0.0),
        "saturation_mM must be > 0",
    ),
    "negative rate": (
        lambda raw: reaction(raw, "catalysis").update(rate_constant=-1.0),
        "rate_constant must be >= 0",
    ),
    "negative catalytic rate": (
        lambda raw: reaction(raw, "conversion").update(catalytic_rate_per_s=-1.0),
        "catalytic_rate_per_s must be >= 0",
    ),
    "maximum rate with a catalyst": (
        lambda raw: reaction(raw, "conversion").update(max_rate_mM_per_s=1e-3),
        "declares a catalyst, so its rate is catalytic_rate_per_s",
    ),
    "catalytic rate without a catalyst": (
        lambda raw: reaction(raw, "conversion").update(catalyst=None),
        "declares no catalyst, so its rate is max_rate_mM_per_s",
    ),
    "negative maximum rate": (lambda raw: uncatalysed(raw, -1.0), "max_rate_mM_per_s must be >= 0"),
    "no catalyst key": (
        lambda raw: reaction(raw, "conversion").pop("catalyst"),
        "declares its catalyst",
    ),
    "forward rate": (
        lambda raw: reaction(raw, "binding").update(forward_rate_per_s=0.0),
        "forward_rate_per_s must be > 0",
    ),
    "factor law": (
        lambda raw: reaction(raw, "removal")["factors"][0].update(law="logistic"),
        "a factor's law is one of",
    ),
    "factor species": (
        lambda raw: reaction(raw, "removal")["factors"][0].update(species="Q"),
        "not a listed species",
    ),
    "factor constant": (
        lambda raw: reaction(raw, "removal")["factors"][0].update(half_saturation_mM=0.0),
        "half_saturation_mM must be > 0",
    ),
    "factor coefficient": (
        lambda raw: reaction(raw, "removal")["factors"][0].update(hill_coefficient=-1.0),
        "hill_coefficient must be > 0",
    ),
    "reaction twice": (
        lambda raw: block(raw)["reactions"].append(copy.deepcopy(reaction(raw, "supply"))),
        "reaction IDs are unique",
    ),
    # The sites.
    "held bath": (
        lambda raw: reaction(raw, "removal").update(sites={"outside": ["bath"]}),
        "held bath",
    ),
    "undeclared cell": (
        lambda raw: reaction(raw, "supply").update(sites={"cells": ["ghost"]}),
        "not a declared cell",
    ),
    "cell as outside": (
        lambda raw: reaction(raw, "supply").update(sites={"outside": ["cell_0"]}),
        "not a declared outside node",
    ),
    "site twice": (
        lambda raw: reaction(raw, "supply").update(sites={"cells": ["cell_0", "cell_0"]}),
        "lists a site twice",
    ),
    "empty sites": (
        lambda raw: reaction(raw, "supply").update(sites={"cells": []}),
        "non-empty list or 'all'",
    ),
    "site kind": (
        lambda raw: reaction(raw, "supply").update(sites={"nodes": ["cell_0"]}),
        "declares its sites as",
    ),
    # The schedule.
    "off the grid": (
        lambda raw: controls(raw, "supply")["schedule"].append(dict(time=0.0015, multiplier=1.0)),
        "exact multiple of dt",
    ),
    "beyond the horizon": (
        lambda raw: controls(raw, "supply")["schedule"].append(dict(time=1.0, multiplier=1.0)),
        "outside the horizon",
    ),
    "late start": (
        lambda raw: controls(raw, "supply")["schedule"][0].update(time=0.001),
        "starts at time 0",
    ),
    "unordered": (
        lambda raw: controls(raw, "supply")["schedule"].extend(
            [dict(time=0.002, multiplier=1.0), dict(time=0.001, multiplier=1.0)]
        ),
        "increase strictly",
    ),
    "negative multiplier": (
        lambda raw: controls(raw, "supply")["schedule"][0].update(multiplier=-1.0),
        "multiplier of the schedule of supply must be >= 0",
    ),
    "empty schedule": (
        lambda raw: controls(raw, "supply").update(schedule=[]),
        "lists its changes",
    ),
    "undeclared reaction": (
        lambda raw: controls(raw, "supply").update(reaction_id="ghost"),
        "undeclared reaction",
    ),
    "foreign site": (
        lambda raw: controls(raw, "supply").update(site="ecs_0"),
        "not a site of reaction supply",
    ),
    "schedule twice": (
        lambda raw: raw["experiment"]["reaction_controls"].append(
            copy.deepcopy(controls(raw, "supply"))
        ),
        "one schedule per reaction and site",
    ),
    "unscheduled route": (
        lambda raw: raw["experiment"]["reaction_controls"].remove(controls(raw, "supply")),
        "reaction supply needs a schedule at cell_0",
    ),
    "unused schedule": (
        lambda raw: raw["experiment"]["reaction_controls"].append(
            dict(reaction_id="supply", site="cell_0", schedule=[dict(time=0.0, multiplier=1.0)])
        ),
        "applies to no site",
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_definition_refusals(name):
    change, message = CASES[name]
    raw = rfx.enzyme_network()
    change(raw)
    with pytest.raises(ConfigError, match=re.escape(message)):
        parse_spec(raw)


def test_all_sites_resolve_to_the_cells_and_finite_outside_nodes():
    raw = rfx.enzyme_network()
    reaction(raw, "removal").update(sites={"cells": "all", "outside": "all"})
    spec = parse_spec(raw)
    routes = [(r.kind, r.node) for r in spec.model.operators[0].routes if r.reaction == "removal"]
    assert routes == [("cell", "cell_0"), ("outside", "ecs_0")]  # Never the held bath.


# ------------------------------------------------------------------ the composition


def test_rk4_is_refused_with_its_reasons():
    raw = rfx.enzyme_network(solver="rk4", dt=1e-4, end=4e-4)
    with pytest.raises(ConfigError, match="refuses RK4 in version 1") as error:
        parse_spec(raw)
    assert "no consumer needs it" in str(error.value)


def test_more_than_seven_species_are_refused_with_the_reason():
    raw = rfx.enzyme_network()  # 3 ions and S, E, C, P: 7.
    parse_spec(raw)
    raw = add_inventory_species(
        raw, "X", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    with pytest.raises(ConfigError, match="at most 7 species per world") as error:
        parse_spec(raw)
    assert "local_species_reactions@1 admits" in str(error.value)


def with_turnover(raw, routes, *, first=False, species=None):
    """routes: (id, species, node, kind); D150's turnover on the network's world."""
    out = copy.deepcopy(raw)
    names = sorted({s for _, s, _, _ in routes})
    turnover = dict(
        law=fx.TURNOVER,
        species=species or [dict(id=s, catalogue=None, evidence=None) for s in names],
        routes=[dict(id=r, species=s, node=n, kind=k) for r, s, n, k in routes],
        templates=[],
    )
    out["model"]["operators"].insert(0 if first else len(out["model"]["operators"]), turnover)
    out["experiment"]["turnover_controls"] = [
        dict(
            route_id=r,
            carrier_id=n if n.startswith("cell") else None,
            schedule=[dict(time=0.0, rate=0.1)],
        )
        for r, _, n, _ in routes
    ]
    return out


def test_turnover_on_a_row_the_network_writes_is_refused():
    raw = rfx.enzyme_network()
    for first in (False, True):
        with pytest.raises(ConfigError, match="which reaction conversion writes"):
            parse_spec(with_turnover(raw, [("clear_P", "P", "ecs_0", "clearance")], first=first))
        with pytest.raises(ConfigError, match="which reaction binding writes"):
            parse_spec(with_turnover(raw, [("make_S", "S", "cell_0", "production")], first=first))
    # The catalyst E is read at ecs_0, never written there: its clearance composes.
    parse_spec(with_turnover(raw, [("clear_E", "E", "ecs_0", "clearance")]))


def test_identities_must_agree_with_the_d150_operators_in_either_order():
    raw = rfx.enzyme_network()
    gzmk = dict(catalogue=dict(catalogue="cells-proteins@0", entry="GZMK"), evidence="label_only")
    species_entry(raw, "E").update(gzmk)
    other = [
        dict(
            id="E",
            catalogue=dict(catalogue="cells-proteins@0", entry="BMP2B"),
            evidence="label_only",
        )
    ]
    same = [dict(id="E", **gzmk)]
    routes = [("clear_E", "E", "ecs_0", "clearance")]
    for first in (False, True):
        with pytest.raises(ConfigError, match="another identity"):
            parse_spec(with_turnover(raw, routes, first=first, species=other))
        parse_spec(with_turnover(raw, routes, first=first, species=same))
    exchange = fx.with_exchange(
        raw,
        [("export_P", "contact_0", "export", "first_order")],
        [("export_P", "cell_0", [(0.0, 0.1)])],
        species=[dict(id="P", catalogue=dict(catalogue="c", entry="p"), evidence="model")],
    )
    exchange["model"]["operators"][-1]["routes"][0]["species"] = "P"
    with pytest.raises(ConfigError, match="another identity"):
        parse_spec(exchange)


def replaced(outside_only):
    raw = rfx.enzyme_network()
    if outside_only:  # The network's cell reactions dropped: only ecs_0's routes remain.
        keep = {"conversion", "removal"}
        block(raw)["reactions"] = [r for r in block(raw)["reactions"] if r["id"] in keep]
        raw["experiment"]["reaction_controls"] = [
            c for c in raw["experiment"]["reaction_controls"] if c["reaction_id"] in keep
        ]
    template = fx.template(raw, "cell_0", "T")
    return fx.with_replacement(raw, [template], [(0.002, "cell_0", "T", "c0_new")])


def test_cell_routes_on_replaced_slots_are_refused_and_outside_routes_compose():
    with pytest.raises(ConfigError, match="a slot scheduled_cell_replacement@1 replaces"):
        parse_spec(replaced(outside_only=False))
    parse_spec(replaced(outside_only=True))


REFUSED = {  # Operator lists with each provider or closer (requirements first) and the reason.
    "water": (("ideal_osmosis_linear_compliance_water@1",), "reads volume as declared"),
    "replacement@2": (
        ("ideal_osmosis_linear_compliance_water@1", "scheduled_cell_replacement@2"),
        "reads volume as declared",
    ),
    "lumen@1": (
        (
            "membrane_entity_state@1",
            "scheduled_membrane_insertion@1",
            "restricted_cleft_lumen@1",
        ),
        "reads extracellular_volume as declared",
    ),
    "lumen@2": (
        (
            "membrane_entity_state@1",
            "scheduled_membrane_insertion@2",
            "restricted_cleft_lumen@2",
        ),
        "reads extracellular_volume as declared",
    ),
    "insertion@1": (
        ("membrane_entity_state@1", "scheduled_membrane_insertion@1"),
        "reads outside_active as declared",
    ),
    "insertion@1 anchors": (
        ("membrane_entity_state@1", "scheduled_membrane_insertion@1"),
        "reads extracellular_amount_reference as declared",
    ),
    "insertion@2": (
        ("membrane_entity_state@1", "scheduled_membrane_insertion@2"),
        "reads outside_active as declared, but scheduled_membrane_insertion@2 closes it",
    ),
    "partition": (
        ("membrane_entity_state@1", "isopotential_partition@1"),
        "reads active as declared, but isopotential_partition@1 closes it",
    ),
    "bridge": (
        (
            "membrane_entity_state@1",
            "isopotential_partition@1",
            "cytoplasmic_bridge_closure@1",
        ),
        "reads active as declared, but isopotential_partition@1 closes it",
    ),
}
ADMITTED = (
    (),
    ("electrode_current_injection@1",),
    ("membrane_entity_state@1",),
    ("scheduled_cell_replacement@1",),
    ("scheduled_species_turnover@1",),
    ("scheduled_species_exchange@1",),
    ("scheduled_species_turnover@1", "scheduled_species_exchange@1"),
)


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_providers_and_closers_of_what_it_reads_as_declared_are_refused(name):
    laws, message = REFUSED[name]
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        mine = [e for e in errors if e.startswith(LAW)]
        assert any(message in e for e in mine), (order, errors)


@pytest.mark.parametrize("laws", ADMITTED, ids=lambda laws: "+".join(laws) or "alone")
def test_the_operators_version_1_composes_with_are_admitted(laws):
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert not [e for e in errors if LAW in e], (order, errors)


def test_a_volume_provider_is_refused_through_the_parser():
    from validation.tissue import pump_water_fixtures as wfx

    base = wfx.heredity_cell("H", dt=1e-3, end_time=0.004)
    base["experiment"]["observation_times"] = [0.0, 0.004]
    water = cs.frozen_definition(wfx.with_water(base, pf_m_s=5e-4))
    water = add_inventory_species(
        water, "S", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    cell = water["model"]["cells"][0]["id"]
    raw = rfx.with_reactions(
        water,
        [rfx.species("S")],
        [rfx.mass_action("supply", {"cells": [cell]}, {}, {"S": 1}, 1e-6)],
        [("supply", None, [(0.0, 1.0)])],
    )
    with pytest.raises(ConfigError, match="local_species_reactions@1 reads volume as declared"):
        parse_spec(raw)


# ------------------------------------------------------------------ the batch signature (Q11 (c))


def batch(*worlds):
    from cells.core.batch import parse_batch

    execution = dict(
        mapping="lax_map", max_worlds=4, max_padded_steps=10**6, max_working_bytes=2**31
    )
    return parse_batch(
        dict(
            schema_version=1,
            kind="independent_worlds",
            worlds=[dict(world_id=i + 1, simulation=w) for i, w in enumerate(worlds)],
            execution=execution,
        )
    )


def test_the_batch_signature_refuses_two_structures_in_one_batch():
    """The lead's ruling Q11 (c): one network per batch. Other parameters, potentials, c0 and
    multipliers are per-world bindings and admitted; another stoichiometry, law kind or factor
    species is refused."""
    base = rfx.enzyme_network()
    values = rfx.enzyme_network({"binding": 2.0, "supply": 0.0}, c0=0.5, mu=(0.1, 0.2, -1.0, -2.0))
    reaction(values, "catalysis")["rate_constant"] = 3.0
    reaction(values, "removal")["factors"][0]["half_saturation_mM"] = 2e-3
    batch(base, values)  # Admitted: the same network.
    stoichiometry = copy.deepcopy(base)
    reaction(stoichiometry, "catalysis")["products"] = {"E": 1, "S": 1}
    kind = copy.deepcopy(base)
    binding = reaction(kind, "binding")
    binding.update(law="mass_action", rate_constant=binding.pop("forward_rate_per_s"))
    factor = copy.deepcopy(base)
    reaction(factor, "removal")["factors"][0]["species"] = "E"
    for other in (stoichiometry, kind, factor):
        parse_spec(other)  # Each is a valid world on its own.
        with pytest.raises(ConfigError, match="matching model array axes"):
            batch(base, other)
