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
"""

import math

import jax
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.registry.inventory_species import add_inventory_species
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
