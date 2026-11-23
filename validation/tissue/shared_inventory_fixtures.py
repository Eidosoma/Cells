"""FR-43 part 2's worlds: one pool written by two processes (docs/FR43_SHARED_INVENTORIES_DESIGN.md
§2; D315). Synthetic values throughout.

The pair (C2.1): the gene unit's polymerase-limited world (validation/gene_regulation/worlds
.polymerase_limited: transcription spends the nucleotide N, recharging makes N from the finite M
and ATP reserves) beside local_species_reactions@1 on N, its second writer:
- "sink": the second-order route N + X -> W (driven mass action, k in 1/(mM s)), a second spender
  of N whose rate k V c_N c_X = k n_N n_X / V reads the cell's volume;
- "source": X -> N (driven mass action, k in 1/s), a second producer of N spending a finite X.
X and W are neutral, impermeant inventory rows (secreted_species_fixtures' trace, diffusivity and
floor). The network's moieties balance its route (N {n: 1}, X {x: 1}, W {n: 1, x: 1}; the source's
X {n: 1}), and in the species registry W carries N's moieties (phosphorus 3, nucleoside 1), the
source's X likewise, so every route conserves the world's moieties too. N's standard potential is
the registry's (the shared row's one authority, species_registry.check_shared_rows), converted to
the network's c0 of 1 mM; X's is 0, W's N's.

For C2.4, each writer can be idle (network_multiplier 0, or gene_rates 0: every one of the gene
unit's scheduled rates zero), and each can be taken away (gene_alone, network_alone), the rows kept.
"""

import copy
import math

from cells.registry.inventory_species import add_inventory_species
from validation.gene_regulation import worlds as gw
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx

C0_mM = 1.0  # The network's standard concentration (mM).
COPIES = 10  # The gene's template copies (A1-M's sweep value).
X_mM = 5.0  # X's initial concentration in the cell (mM).
W_mM = 1e-6  # W's (mM): a product starting at a trace.
K_SINK = 1e-4  # 1/(mM s): N + X -> W.
K_SOURCE = 1e-4  # 1/s: X -> N.
KINDS = ("sink", "source")


def _rows(raw, kind):
    """X (and the sink's W) as inventory rows, with the registry's moieties for the network's
    products."""
    rows = {"X": X_mM} if kind == "source" else {"X": X_mM, "W": W_mM}
    for name, mM in rows.items():
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=fx.TRACE_mM,
            diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM={gw.CELL: mM},
        )
    carrier = "X" if kind == "source" else "W"  # The row that carries N's moieties.
    for moiety in raw["model"]["moieties"]:
        weight = moiety["weights"].get("N")
        if weight:
            moiety["weights"][carrier] = weight
    return raw


def _network(raw, kind, *, k, multiplier):
    m = raw["model"]
    entry = next(s for s in m["species"] if s["id"] == "N")
    mu_N = entry["standard_mu_RT"] + math.log(C0_mM / m["standard_concentration_mM"])
    if kind == "sink":
        species = [
            rfx.species("N", moieties={"n": 1}, mu=mu_N),
            rfx.species("X", moieties={"x": 1}, mu=0.0),
            rfx.species("W", moieties={"n": 1, "x": 1}, mu=mu_N),
        ]
        rate = K_SINK if k is None else k
        reactions = [
            rfx.mass_action("spend_N", {"cells": [gw.CELL]}, {"N": 1, "X": 1}, {"W": 1}, rate)
        ]
    else:
        species = [
            rfx.species("N", moieties={"n": 1}, mu=mu_N),
            rfx.species("X", moieties={"n": 1}, mu=mu_N),
        ]
        rate = K_SOURCE if k is None else k
        reactions = [rfx.mass_action("supply_N", {"cells": [gw.CELL]}, {"X": 1}, {"N": 1}, rate)]
    controls = rfx.always([r["id"] for r in reactions], multiplier)
    return rfx.with_reactions(raw, species, reactions, controls, c0=C0_mM)


def _horizon(raw, end, every):
    if end is None:
        return raw
    out = copy.deepcopy(raw)
    dt = out["execution"]["dt"]
    every = end if every is None else every
    out["experiment"]["end_time"] = float(end)
    out["experiment"]["observation_times"] = fx.grid_times(end, dt, every)
    out["execution"]["max_steps"] = int(math.ceil(end / dt)) + 8
    return out


def _idle_gene(raw):
    out = copy.deepcopy(raw)
    for control in out["experiment"]["polymerisation_controls"]:
        for change in control["schedule"]:
            change["value"] = 0.0
    return out


def pair(kind="sink", *, copies=COPIES, k=None, dt=0.5, end=None, every=None,
         network_multiplier=1.0, gene_rates=1.0):  # fmt: skip
    """The gene unit beside the D152 network on N (C2.1). end: a shorter horizon than A1-M's
    (observed every `every` s, default the end); gene_rates 0 sets every gene rate to zero."""
    if kind not in KINDS:
        raise ValueError(f"kind is one of {KINDS}")
    raw = _rows(gw.polymerase_limited(copies, dt=dt), kind)
    raw = _network(raw, kind, k=k, multiplier=network_multiplier)
    if gene_rates == 0.0:
        raw = _idle_gene(raw)
    elif gene_rates != 1.0:
        raise ValueError("gene_rates is 1 or 0")
    return _horizon(raw, end, every)


def gene_alone(kind="sink", *, copies=COPIES, dt=0.5, end=None, every=None):
    """The gene unit alone on the pair's rows (no network)."""
    return _horizon(_rows(gw.polymerase_limited(copies, dt=dt), kind), end, every)


def network_alone(kind="sink", *, copies=COPIES, k=None, dt=0.5, end=None, every=None):
    """The network alone on the pair's rows (the gene unit's operator and controls removed)."""
    raw = pair(kind, copies=copies, k=k, dt=dt)
    raw["model"]["operators"] = [
        o for o in raw["model"]["operators"] if o["law"] != gw.POLYMERISATION
    ]
    raw["experiment"].pop("polymerisation_controls", None)
    return _horizon(raw, end, every)
