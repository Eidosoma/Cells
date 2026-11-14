"""The NumPy dG test per law of record (§3.4, guard 4): local_species_reactions@1's half-step
against the independent references (validation/reactions, used only through REFERENCES_USAGE.md).

Tier 1, host side. Two worlds between them run every law, order and factor kind at a cell and at a
finite outside node, with unequal, non-unit volumes (0.7 and 1.9 pL) and c0 = 0.4 mM:
* the enzyme world: passive E + S <-> C at both nodes, first-order C -> E + P, Michaelis-Menten
  S -> P with its catalyst E and without one, a zeroth-order source under Hill activation and a
  first-order sink under Hill inhibition;
* the Schnakenberg-type world: zeroth- and first-order mass action, the third-order 2U + V -> 3U
  (a coefficient of 2), a second-order U + V -> 2V and a passive U <-> V.
On seeded random amounts, multipliers (zero patterns forcing every node class) and half-steps
(h L from 0.02 to 0.75, refusals included), the engine's half-step is compared with
nr.half_step at the usage note's tolerances: the refusal flags (wherever |hL_max - 1/2| > 1e-12
x 1/2), h L, the end amounts (1e-12 relative), the extents (1e-12 x gross_extents), dG = W - H
against the 50-digit value at the engine's own dn (1e-12 x terms), the standard term against the
route form (1e-12 x terms), the node classes, single-class H and W, mixed H (1e-12 x heat_terms)
and W (1e-12 x (heat_terms + delta_G_terms)), the branch wherever sign_margin > 1e-10, and idle
nodes bitwise. The references' inputs are built from the raw declarations (amounts, volumes,
parameters, the engine's R and T), never from the engine's bound layout.
Two readings differ in form only: the engine books the standard term in species form,
sum_s mu°'_s dn_s, the reference in route form, sum_r dG°'_r dxi_r (equal to rounding).
"""

import copy
import json
import math
import os
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.specs import parse_spec
from cells.models.operators import species_reactions as sr
from cells.models.registry import get_model
from cells.processes.electrochemistry import R
from validation.reactions import network_reference as nr
from validation.tissue import species_reactions_fixtures as rfx

THETA = 0.5
VOLUMES = (("cell_0", 0.7),), (("ecs_0", 1.9),)  # pL: unequal, not 1.
C0 = 0.4  # mM.
BOTH = {"cells": ["cell_0"], "outside": ["ecs_0"]}
CELL, NODE = {"cells": ["cell_0"]}, {"outside": ["ecs_0"]}


def enzyme_world(scale=1.0):
    species = [
        rfx.species("S", moieties={"X": 1}, mu=0.2),
        rfx.species("E", moieties={"Y": 1}, mu=-0.1),
        rfx.species("C", moieties={"X": 1, "Y": 1}, mu=-3.0),
        rfx.species("P", moieties={"X": 1}, mu=-0.7),
    ]
    reactions = [
        rfx.passive("bind", BOTH, {"E": 1, "S": 1}, {"C": 1}, 20.0 * scale),
        rfx.mass_action("cat", CELL, {"C": 1}, {"E": 1, "P": 1}, 2.0 * scale),
        rfx.michaelis_menten("mm_cat", NODE, "S", {"P": 1}, 3.0 * scale, 2e-4, catalyst="E"),
        rfx.michaelis_menten("mm_plain", CELL, "S", {"P": 1}, 5e-4 * scale, 3e-4 * scale),
        rfx.mass_action(
            "feed", CELL, {}, {"S": 1}, 1e-4, factors=[rfx.hill("hill_activation", "C", 2e-5, 1.5)]
        ),
        rfx.mass_action(
            "drain", NODE, {"P": 1}, {}, 0.8, factors=[rfx.hill("hill_inhibition", "S", 4e-4, 2.2)]
        ),
    ]
    profile = dict(
        S=dict(cell_0=1e-3, ecs_0=5e-4),
        E=dict(cell_0=1e-4, ecs_0=2e-4),
        C=dict(cell_0=2e-5, ecs_0=1e-5),
        P=dict(cell_0=3e-5, ecs_0=1e-5),
    )
    return world(("E", "C", "P"), species, reactions, profile)


def schnakenberg_world(scale=1.0):
    species = [rfx.species("U", moieties={"M": 1}), rfx.species("V", moieties={"M": 1}, mu=-0.5)]
    reactions = [
        rfx.mass_action("make_u", BOTH, {}, {"U": 1}, 1e-4 * scale),
        rfx.mass_action("decay_u", BOTH, {"U": 1}, {}, 0.1 * scale),
        rfx.mass_action("make_v", BOTH, {}, {"V": 1}, 9e-5 * scale),
        rfx.mass_action("auto", BOTH, {"U": 2, "V": 1}, {"U": 3}, 1e5 * scale),
        rfx.mass_action("swap", NODE, {"U": 1, "V": 1}, {"V": 2}, 50.0 * scale),
        rfx.passive("relax", CELL, {"U": 1}, {"V": 1}, 0.5 * scale),
    ]
    profile = dict(U=dict(cell_0=1e-3, ecs_0=8e-4), V=dict(cell_0=9e-4, ecs_0=1.1e-3))
    return world(("U", "V"), species, reactions, profile)


def world(extra, species, reactions, profile):
    cells, nodes = VOLUMES
    raw = rfx.species_world(extra, profile=profile, faces=False, cells=cells, nodes=nodes)
    names = [r["id"] for r in reactions]
    return rfx.with_reactions(raw, species, reactions, rfx.always(names), c0=C0)


def near_equilibrium(net, raw, sites, amounts, volumes, increment, outside, species_ids, rng):
    """Set each passive route's first product at its equilibrium with the other species (relative
    offset ~1e-7, either sign), in both the reference's amounts and the engine's increments."""
    c0 = net.c0_mM
    mu = {s.name: s.mu0_RT for s in net.species}
    names = [s.name for s in net.species]
    nodes = rfx.reference_nodes(raw)
    n_cells = len(raw["model"]["cells"])
    for r, reaction in enumerate(net.reactions):
        if reaction.law != "passive":
            continue
        product = next(iter(reaction.products))
        others = {
            **{s: -c for s, c in reaction.reactants.items()},
            **{s: c for s, c in reaction.products.items() if s != product},
        }
        dmu = sum(mu[s] * c for s, c in reaction.products.items()) - sum(
            mu[s] * c for s, c in reaction.reactants.items()
        )
        for j in np.flatnonzero(sites[r]):
            # prod a^nu = exp(-dmu): a_product^beta = exp(-dmu) / prod_{others} a^nu.
            log_a = -dmu - sum(
                c * math.log(amounts[names.index(s), j] / volumes[j] / c0)
                for s, c in others.items()
            )
            beta = reaction.products[product]
            target = c0 * math.exp(log_a / beta) * volumes[j] * (1 + 1e-7 * rng.uniform(-1, 1))
            k, s = names.index(product), species_ids.index(product)
            declared = nodes[j]["initial_amount_fmol"][product]
            if j < n_cells:
                increment[s, j] = target - declared
                amounts[k, j] = declared + increment[s, j]
            else:
                outside[s, j - n_cells] = target - declared
                amounts[k, j] = declared + outside[s, j - n_cells]


# ------------------------------------------------------------------ the comparison


def engine(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model.operators[0], state, p


def route_map(spec):
    """[route] -> (reaction index, combined node index)."""
    declaration = spec.model.operators[0]
    reactions = [r.id for r in declaration.reactions]
    nodes = [c.id for c in spec.model.cells] + [c.id for c in spec.model.extracellular]
    return [(reactions.index(r.reaction), nodes.index(r.node)) for r in declaration.routes]


def trial(raw, rng, counts):
    """One random half-step, engine against reference (module docstring)."""
    spec, op, state, p = engine(raw)
    net, sites = rfx.reference_network(raw), rfx.reference_sites(raw)
    names = [s.name for s in net.species]
    nodes = rfx.reference_nodes(raw)
    volumes = np.asarray([n["volume_pL"] for n in nodes], dtype=float)
    species_ids = list(spec.model.species_ids)
    # Random amounts at the route nodes, a decade either side of the declared ones, set through the
    # engine's increments; the reference adds the same increments to the raw declared amounts.
    increment = np.array(state.amount_increment, copy=True)
    outside = np.array(state.extracellular_amount_increment, copy=True)
    raw_amounts = np.zeros((len(names), len(nodes)))
    n_cells = len(raw["model"]["cells"])
    for j, node in enumerate(nodes):
        for k, name in enumerate(names):
            declared = node["initial_amount_fmol"][name]
            target = declared * 10 ** rng.uniform(-1, 1) if sites[:, j].any() else declared
            s = species_ids.index(name)
            if j < n_cells:
                increment[s, j] = target - declared
                raw_amounts[k, j] = declared + increment[s, j]
            else:
                outside[s, j - n_cells] = target - declared
                raw_amounts[k, j] = declared + outside[s, j - n_cells]
    if rng.uniform() < 0.4:  # Every passive route within ~1e-7 of its equilibrium: crossings.
        near_equilibrium(
            net, raw, sites, raw_amounts, volumes, increment, outside, species_ids, rng
        )
    state = state._replace(amount_increment=increment, extracellular_amount_increment=outside)
    reactions = len(net.reactions)
    m = np.where(rng.uniform(size=reactions) < 0.2, 0.0, 10 ** rng.uniform(-0.5, 0.5, reactions))
    pattern = rng.integers(4)
    passive = np.asarray([r.law == "passive" for r in net.reactions])
    if pattern == 1:
        m[~passive] = 0.0  # Passive only.
    elif pattern == 2:
        m[passive] = 0.0  # Driven only.
    routes = route_map(spec)
    multiplier = np.asarray([m[r] for r, _ in routes])
    rt = nr.rt_pJ_per_fmol(R, raw["model"]["temperature_K"])
    rates = nr.rates(net, raw_amounts, volumes, multipliers=m, sites=sites)
    load = np.max(rates.consumption_rate, initial=0.0)
    if load == 0:
        return
    target = rng.choice([rng.uniform(0.02, 0.45), rng.uniform(0.55, 0.75)], p=[0.8, 0.2])
    h = target / load
    with np.errstate(invalid="ignore", divide="ignore"):  # A refused candidate may log a negative.
        ref = nr.half_step(net, raw_amounts, volumes, h, rt, multipliers=m, sites=sites)
        terms = sr.half_step_terms(state, multiplier, h, p, xp=np)
        new, ok = op.half_step(state, h, SimpleNamespace(reaction_multiplier=multiplier), p, xp=np)
    if abs(ref.hL_max - THETA) > 1e-12 * THETA:  # Either side of the bound, never at it.
        assert bool(ok) == bool(terms.valid) == bool(ref.admitted), (ref.hL_max, ok, ref.admitted)
    if not ref.admitted:
        counts["refused"] += 1
        return
    counts["admitted"] += 1
    assert terms.max_hl == pytest.approx(ref.hL_max, rel=1e-12, abs=1e-300)
    # Map the engine's routes to [R, N].
    extent = np.zeros((reactions, len(nodes)))
    nonreversing = np.zeros((reactions, len(nodes)), dtype=bool)
    for (r, i), value, flag in zip(routes, terms.extent, terms.nonreversing, strict=True):
        extent[r, i], nonreversing[r, i] = value, flag
    rows = [species_ids.index(n) for n in names]
    dn = np.where(terms.written, terms.dn, 0.0)  # The engine's own delta, [k, N].
    end = sr.node_amounts(state, p, xp=np) + dn
    active = ref.node_class != "idle"
    for j in range(len(nodes)):
        if not active[j]:  # Idle: the start state, bitwise.
            if j < n_cells:
                assert (
                    new.amount_increment[rows, j].tobytes()
                    == state.amount_increment[rows, j].tobytes()
                )
            else:
                jj = j - n_cells
                assert (
                    new.extracellular_amount_increment[rows, jj].tobytes()
                    == state.extracellular_amount_increment[rows, jj].tobytes()
                )
            assert terms.heat[j] == 0.0 and terms.work[j] == 0.0
            continue
        assert np.all(np.abs(end[:, j] - ref.end[:, j]) <= 1e-12 * np.abs(ref.end[:, j])), j
    assert np.all(np.abs(extent - ref.extents) <= 1e-12 * ref.gross_extents + 1e-300)
    exact = nr.exact_energy_change(
        net, raw_amounts, volumes, rt, delta_fmol=dn, extents_fmol=extent
    )
    with localcontext() as ctx:
        ctx.prec = 60
        for j in np.flatnonzero(active):
            booked = Decimal(float(terms.work[j])) - Decimal(float(terms.heat[j]))
            scale = exact.terms[j] + Decimal("1e-300")
            assert abs(booked - exact.delta_G[j]) <= Decimal("1e-12") * scale, ("dG", j)
            standard = Decimal(float(terms.standard[j]))
            assert abs(standard - exact.standard_routes[j]) <= Decimal("1e-12") * scale, ("std", j)
    for j in np.flatnonzero(active):
        cls = ref.node_class[j]
        counts[cls] += 1
        engine_class = (
            "mixed" if terms.mixed[j] else "passive" if terms.passive_only[j] else "driven"
        )
        assert engine_class == cls, (j, engine_class, cls)
        if cls == "driven":
            assert terms.heat[j] == 0.0
        elif cls == "passive":
            assert terms.work[j] == 0.0
        else:
            assert abs(terms.heat[j] - ref.heat[j]) <= 1e-12 * ref.heat_terms[j], ("H", j)
            assert abs(terms.work[j] - ref.work[j]) <= 1e-12 * (
                ref.heat_terms[j] + ref.delta_G_terms[j]
            ), ("W", j)
            for r in np.flatnonzero(passive & sites[:, j]):
                if ref.sign_margin[r, j] > 1e-10 and ref.branch[r, j] in ("share", "quadrature"):
                    assert nonreversing[r, j] == (ref.branch[r, j] == "share"), (r, j)
                    counts[str(ref.branch[r, j])] += 1


@pytest.mark.parametrize(
    ("builder", "scale"),
    [
        (enzyme_world, 1.0),
        (enzyme_world, 2.5),
        (schnakenberg_world, 1.0),
        (schnakenberg_world, 0.4),
    ],
    ids=["enzyme", "enzyme_scaled", "schnakenberg", "schnakenberg_scaled"],
)
def test_the_half_step_matches_the_reference_per_law(builder, scale):
    raw = builder(scale)
    rng = np.random.default_rng(152 + int(10 * scale) + (0 if builder is enzyme_world else 7))
    counts = dict(admitted=0, refused=0, mixed=0, passive=0, driven=0, share=0, quadrature=0)
    for _ in range(60):
        trial(raw, rng, counts)
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:  # The counts of record, in the tier runner's output folder.
        path = Path(root) / "species_reactions_against_references.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(world=builder.__name__, scale=scale, **counts)) + "\n")
    assert counts["admitted"] >= 30 and counts["refused"] >= 3, counts
    for name in ("mixed", "passive", "driven"):
        assert counts[name] > 0, counts
    assert counts["share"] > 0 and counts["quadrature"] > 0, counts


def test_both_worlds_run_every_law_order_and_factor_kind():
    laws = set()
    for raw in (enzyme_world(), schnakenberg_world()):
        block = next(b for b in raw["model"]["operators"] if b["law"] == rfx.REACTIONS)
        for r in block["reactions"]:
            order = sum(r["reactants"].values())
            laws.add((r["law"], order if r["law"] == "mass_action" else None))
            if r["law"] == "michaelis_menten":
                laws.add(("catalysed", r["catalyst"] is not None))
            for f in r["factors"]:
                laws.add(("factor", f["law"]))
    assert {("mass_action", q) for q in range(4)} <= laws
    assert {(rfx.PASSIVE, None), ("catalysed", True), ("catalysed", False)} <= laws
    assert {("factor", "hill_activation"), ("factor", "hill_inhibition")} <= laws
    assert copy.deepcopy(VOLUMES) == VOLUMES and C0 != 1.0 and math.isfinite(C0)
