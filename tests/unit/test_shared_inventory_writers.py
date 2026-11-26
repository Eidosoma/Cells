"""FR-43 part 2A (D315): one pool, two writers at fixed volume.

The gene unit beside a D152 network on its listed row N (validation/tissue/shared_inventory_fixtures
.pair): the 19 November 2026 two-writer rule, extended to the gene unit beside a D152 network, with
one registry potential for the shared row and separate material and energy accounts for each
writer (docs/FR43_SHARED_INVENTORIES_DESIGN.md §2.2).
- The definition: the pair is admitted, with a sink (N + X -> W) or a source (X -> N) beside the
  gene unit. It is refused when the registry gives no potential for N (the shared-row rule,
  species_registry.check_shared_rows), when the network's potential of N is off the registry's
  (check_potentials), on a row FR-42's label owner labels and on an exported row (both keep one
  writer); turnover on a listed row stays refused.
The runs (C2.2, C2.4) are test_shared_inventory_writers_runs.py's. Parses only (no compile).

FR-43 part 3's co-writers (docs/FR43_PART3_COWRITERS_DESIGN.md §3.4, §3.5; the species registry's
check_row_writers): a transfer may share a row with any declared writer, unless a writer claims it
alone (validation/fr43_part3/worlds' co-writer worlds).
- Admitted, in either declared order: cells.operator.integer_unit_population@1 beside a D152 source
  of its row in the cell and a sink at its node, beside the gene unit on N and on R, and D150's
  exchange beside the gene unit on N; the gene unit, a D152 network and the population on one row in
  all six orders; the population beside the gene unit under RK4.
- Refused by name: the population on a row the gene unit exports or whose monomers it returns at a
  node, and exchange of a labelled row (the claims); the population on the unit producer's
  precursor (R5: a transfer's rate has no static bound); site occupancy on a listed row (a second
  conversion, the lead's L1); an undeclared split row writer beside the population or the gene unit
  (fails closed).
"""

import itertools
import math

import jax
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.operators import integer_unit_population as iup
from cells.operators import templated_polymerisation as tp
from cells.operators.contract import Operator
from cells.registry import species_registry
from cells.registry.inventory_species import add_inventory_species
from validation.fr43_part3 import worlds as w3
from validation.gene_regulation import worlds as gw
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import shared_inventory_fixtures as sif
from validation.tissue import species_reactions_fixtures as rfx


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


# ------------------------------------------------------------------ the definition


@pytest.mark.parametrize("kind", sif.KINDS)
def test_the_pair_is_admitted(kind):
    spec = parse_spec(sif.pair(kind))
    laws = [d.law for d in spec.model.operators]
    assert laws == [gw.POLYMERISATION, rfx.REACTIONS]


def test_a_shared_row_needs_its_registry_potential():
    raw = sif.pair("sink")
    next(s for s in raw["model"]["species"] if s["id"] == "N").pop("standard_mu_RT")
    with pytest.raises(ConfigError, match="needs its standard potential in the species registry"):
        parse_spec(raw)


def test_the_network_must_agree_with_the_registry_potential():
    raw = sif.pair("sink")
    network = next(o for o in raw["model"]["operators"] if o["law"] == rfx.REACTIONS)
    next(s for s in network["species"] if s["id"] == "N")["standard_mu_RT"] += 0.1
    with pytest.raises(ConfigError, match="one authority for each standard potential"):
        parse_spec(raw)


def test_a_labelled_row_keeps_one_writer():
    raw = gw.with_share_labels(sif.pair("sink"), rows=("N",))
    with pytest.raises(ConfigError, match="a labelled or exported row"):
        parse_spec(raw)


def test_an_exported_row_keeps_one_writer():
    """A source X -> R of the exported row R (amendment T's export, gw.with_export)."""
    raw = gw.with_export(gw.polymerase_limited(sif.COPIES))
    raw = add_inventory_species(
        raw,
        "X",
        trace_mM=fx.TRACE_mM,
        diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM={gw.CELL: sif.X_mM},
    )
    m = raw["model"]
    for moiety in m["moieties"]:  # X carries R's moieties, so X -> R conserves them.
        if moiety["weights"].get("R"):
            moiety["weights"]["X"] = moiety["weights"]["R"]
    entry = next(s for s in m["species"] if s["id"] == "R")
    mu_R = entry["standard_mu_RT"] + math.log(sif.C0_mM / m["standard_concentration_mM"])
    species = [rfx.species(r, moieties={"r": 1}, mu=mu_R) for r in ("R", "X")]
    reactions = [rfx.mass_action("make_R", {"cells": [gw.CELL]}, {"X": 1}, {"R": 1}, 1e-6)]
    raw = rfx.with_reactions(raw, species, reactions, rfx.always(["make_R"]), c0=sif.C0_mM)
    with pytest.raises(ConfigError, match="a labelled or exported row"):
        parse_spec(raw)


def test_turnover_on_a_listed_row_stays_refused():
    """Other conversions keep the gene unit's one-writer rule: D150's turnover producing N (FR-43
    part 3: refused as a conversion of a listed row)."""
    raw = fx.with_turnover(
        gw.polymerase_limited(sif.COPIES),
        [("make_N", gw.CELL, "production")],
        [("make_N", gw.CELL, [(0.0, 1e-6)])],
        species=[dict(id="N", catalogue=None, evidence=None)],
    )
    raw["model"]["operators"][-1]["routes"][0]["species"] = "N"  # The fixture's routes name S.
    with pytest.raises(ConfigError, match="converts 'N', a listed row"):
        parse_spec(raw)


# ------------------------------------------------------------------ FR-43 part 3: the co-writers


def _exchange_beside_the_gene_unit(first):
    raw, patch = w3.gene_world()
    return w3.with_exchange_of(raw, "N", patch, gw.CELL, first=first)


ADMITTED = {
    "a D152 source of S in the cell": lambda first: w3.beside_reactions("source", first=first),
    "a D152 sink of S at the node": lambda first: w3.beside_reactions(
        "sink", at="outside", first=first
    ),
    "the gene unit's nucleotide N": lambda first: w3.beside_gene_unit("N", first=first),
    "the gene unit's mRNA R": lambda first: w3.beside_gene_unit("R", first=first),
    "exchange beside the gene unit on N": _exchange_beside_the_gene_unit,
}


@pytest.mark.parametrize("first", (False, True), ids=("operator last", "operator first"))
@pytest.mark.parametrize("name", sorted(ADMITTED))
def test_a_transfer_shares_a_row_with_a_writer_in_either_order(name, first):
    """Newly admitted (design §3.5): the transfer (the integer population, or exchange) declared
    last or first beside the row's other writer."""
    spec = parse_spec(ADMITTED[name](first))
    laws = [d.law for d in spec.model.operators]
    transfer = iup.LAW_ID if iup.LAW_ID in laws else w3.EXCHANGE
    assert (laws[0] == transfer) is first and len(laws) == 2


@pytest.mark.parametrize("order", list(itertools.permutations(("gene", "reactions", "units"))))
def test_the_gene_unit_a_network_and_the_population_on_one_row(order):
    """The triple (design §3.5) parses in every declared order; its run is the statistics file's."""
    laws = [d.law for d in parse_spec(w3.triple(order)).model.operators]
    assert laws == [{"gene": tp.LAW_ID, "reactions": rfx.REACTIONS, "units": iup.LAW_ID}[k]
                    for k in order]  # fmt: skip


def test_the_population_beside_the_gene_unit_under_rk4():
    """Admitted under RK4 (D152's reactions refuse it): both keep exact half-steps around @3's RK4
    step (RK4 = "split")."""
    spec = parse_spec(w3.beside_gene_unit("N", solver="rk4"))
    assert spec.execution.solver == "rk4"


REFUSED = {
    "the population on an exported row": (
        lambda: w3.on_exported_row("R"),
        f"{iup.LAW_ID} writes 'R' at cell_0, a labelled or exported row",
    ),
    "the population on an outside degradation's monomer": (
        lambda: w3.on_exported_row("M"),
        f"{iup.LAW_ID} writes 'M' at cell_0, a labelled or exported row",
    ),
    "exchange of a labelled row": (
        w3.exchange_of_labelled_row,
        f"{w3.EXCHANGE} writes 'N' at cell_0, a labelled or exported row",
    ),
    "the population on the unit producer's precursor": (
        w3.on_precursor,
        f"made at a rate with no static bound by {iup.LAW_ID}",
    ),
    "site occupancy on a listed row": (
        w3.sites_on_listed_row,
        f"{w3.SITES} converts 'N', a listed row",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_each_co_writer_refusal(name):
    """Design §3.4's refusals by name, each the first check that a world reaches."""
    build, message = REFUSED[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


class _Undeclared(Operator):
    """A split row writer that declares no ROW_MOVES (an outside operator, say)."""

    LAW_ID = "tests.operator.undeclared_writer@1"
    SPLIT = True
    RK4 = "split"
    STATE_AXES = {"moved_fmol": ["route"]}
    ENTITY_WRITES = {"amount_increment": ("moved_fmol",)}


GUARDS = {
    "the population": (lambda: w3.beside_reactions("source"), iup.LAW_ID),
    "the gene unit": (lambda: w3.beside_gene_unit("N"), tp.LAW_ID),
}


@pytest.mark.parametrize("guard", sorted(GUARDS))
def test_an_undeclared_split_row_writer_fails_closed_beside_a_guard(guard, monkeypatch):
    """Its rows are unknown, so whether it may share one cannot be checked (the unit producer's
    row is test_population_unit_turnover.py's)."""
    build, law = GUARDS[guard]
    spec = parse_spec(build())
    declaration = next(d for d in spec.model.operators if d.law == law)
    entries = species_registry._entries(spec) + ((_Undeclared(), None),)
    monkeypatch.setattr(species_registry, "_entries", lambda _: entries)
    check = (lambda: iup.check_writers(spec, declaration, None)) if law == iup.LAW_ID else (
        lambda: tp.check_writers(spec, declaration)
    )  # fmt: skip
    with pytest.raises(ConfigError, match=f"{_Undeclared.LAW_ID} writes species rows in its"):
        check()
