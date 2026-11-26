"""Compare the split-step region theorem with one compiled step of the closed A/B chain."""

import json
import math

import jax
import numpy as np

from validation.morphogenesis import mg0c_turing as mg
from validation.reactions.chain_reference import mode_basis


def closed_chain():
    """The passive pair and two-mode initial profile from the engine's composition test."""
    pair = mg.passive_pair()
    modes = mode_basis(12)
    profile = {s: c * (1 + 0.05 * modes[2] + 0.02 * modes[5]) for s, c in pair["base_mM"].items()}
    dt = 0.05
    raw = mg.chain_world(
        profile,
        network=pair["network"],
        diffusivities=pair["diffusivities"],
        dt=dt,
        end=dt,
        observation_times=[0.0, dt],
    )
    model = raw["model"]
    if (
        model["id"] != "cells.model.resolved_pump_composite@1"
        or model["inner_model"] != "cells.model.resolved_pump_tissue@3"
    ):
        raise AssertionError("Expected the composite on the resolved tissue host")
    if any(f["law"] != "cells.route.logmean_electrodiffusion@1" for f in model["faces"]):
        raise AssertionError("Expected the declared electrodiffusion faces")
    if any(p["permeability_m_per_s"][s] != 0 for p in model["membranes"] for s in profile):
        raise AssertionError("A and B must be impermeant on all membrane patches")
    run = mg.run_chain(raw, pair["base_mM"], window_steps=1)
    if run["steps"] != 1 or not np.array_equal(run["times"], [0.0, dt]):
        raise AssertionError("Expected both endpoints of one accepted split step")
    return run


def region_balance(region, transferred, nodes, faces, amounts, extents, weights, column):
    """Compare independently stored amounts, signed face transfers and booked reaction extents."""
    inside = np.array([n in region for n in nodes])
    signs = np.array([int(f.receiver in region) - int(f.sender in region) for f in faces])
    selected = amounts[:, :, inside]
    changes = np.array([math.fsum(row) for row in selected[1] - selected[0]])
    cut_by_species = np.array([math.fsum(row * signs) for row in transferred])
    extent = math.fsum(extents[n] for n in region)

    # The composition ledger uses 64 eps times the observed inventory scale.
    totals = selected.sum(axis=2)
    rounding = 64 * np.finfo(float).eps
    species_tolerance = rounding * totals.max(axis=0)
    species_residual = changes - (cut_by_species + column * extent)

    face_inventory = weights @ transferred
    crossings = {
        f.id: float(sign * value)
        for f, sign, value in zip(faces, signs, face_inventory, strict=True)
        if sign
    }
    change = math.fsum(weights * changes)
    boundary = math.fsum(crossings.values())
    tolerance = float(rounding * max(totals @ weights))
    internal = [
        abs(value)
        for f, value in zip(faces, face_inventory, strict=True)
        if f.sender in region and f.receiver in region
    ]
    return {
        "inventory_change_fmol": change,
        "boundary_inflow_fmol": boundary,
        "residual_fmol": change - boundary,
        "tolerance_fmol": tolerance,
        "crossing_faces_fmol": crossings,
        "max_internal_face_transfer_fmol": float(max(internal, default=0.0)),
        "reaction_extent_fmol": extent,
        "max_species_residual_fmol": float(max(np.abs(species_residual))),
        "species_within_tolerance": bool(np.all(np.abs(species_residual) <= species_tolerance)),
    }


def require_balance(result):
    if not (
        result["species_within_tolerance"]
        and abs(result["residual_fmol"]) <= result["tolerance_fmol"]
    ):
        raise AssertionError(f"Species or weighted regional balance failed: {result}")


def check(run):
    model = run["spec"].model
    (declaration,) = model.operators
    (reaction,) = declaration.reactions
    if declaration.law != "cells.operator.local_species_reactions@1" or reaction.kind != "closed":
        raise AssertionError("Expected the closed reaction operator")
    names = run["names"]
    weights_by_name = {s.identity.id: dict(s.moieties) for s in declaration.species}
    if weights_by_name != {"A": {"M": 1}, "B": {"M": 1}}:
        raise AssertionError(f"Unexpected declared inventory: {weights_by_name}")
    weights = np.array([weights_by_name[s]["M"] for s in names])
    reactants, products = dict(reaction.reactants), dict(reaction.products)
    column = np.array([products.get(s, 0) - reactants.get(s, 0) for s in names])
    if reactants != {"A": 1} or products != {"B": 1} or weights @ column != 0:
        raise AssertionError("The fixture must implement the balanced A to B conversion")

    nodes = [n.id for n in model.extracellular if not n.reservoir]
    if nodes != [n.id for n in model.extracellular if n.id.startswith("node_")] or len(nodes) != 12:
        raise AssertionError("Expected the twelve finite nodes on the fixture's amount axis")
    if not all(f.sender in nodes and f.receiver in nodes for f in model.faces):
        raise AssertionError("Every face must join two finite nodes on this closed chain")
    state = run["final"].state
    rows = [model.species_ids.index(s) for s in names]
    transferred = np.asarray(state.face_transferred)[rows, : len(model.faces)]
    extents = {
        r.node: float(x)
        for r, x in zip(declaration.routes, state.reaction_extent_fmol, strict=True)
    }
    if set(extents) != set(nodes) or len(declaration.routes) != len(nodes):
        raise AssertionError("Expected one reaction route per finite node")
    region = {f"node_{i}" for i in range(2, 6)}
    data = (nodes, model.faces, run["amount"], extents, weights, column)
    part = region_balance(region, transferred, *data)
    whole = region_balance(set(nodes), transferred, *data)
    require_balance(part)
    require_balance(whole)

    cut = part["crossing_faces_fmol"]
    tolerance = part["tolerance_fmol"]
    if (
        len(cut) != 2
        or min(cut.values()) >= -tolerance
        or max(cut.values()) <= tolerance
        or min(
            abs(part["boundary_inflow_fmol"]),
            part["max_internal_face_transfer_fmol"],
            abs(part["reaction_extent_fmol"]),
        )
        <= tolerance
    ):
        raise AssertionError("Expected resolved inflow, outflow, internal transport and conversion")
    # Reverse one booked boundary face in the comparison data. It is internal to the whole chain.
    flipped = max(cut, key=lambda name: abs(cut[name]))
    wrong_transfers = transferred.copy()
    wrong_transfers[:, [f.id for f in model.faces].index(flipped)] *= -1
    wrong_part = region_balance(region, wrong_transfers, *data)
    wrong_whole = region_balance(set(nodes), wrong_transfers, *data)
    require_balance(wrong_whole)
    if wrong_part["species_within_tolerance"] or not abs(wrong_part["residual_fmol"]) > tolerance:
        raise AssertionError("The regional balance accepted the reversed boundary face")
    return {
        "model": "cells.model.resolved_pump_composite@1",
        "inner_model": model.inner_model,
        "operator": declaration.law,
        "face_law": "cells.route.logmean_electrodiffusion@1",
        "backend": run["spec"].execution.backend,
        "dtype": transferred.dtype.name,
        "step_s": run["spec"].execution.dt,
        "region": sorted(region),
        "region_balance": part,
        "whole_chain": whole,
        "reversed_face": {
            "id": flipped,
            "region_residual_fmol": wrong_part["residual_fmol"],
            "whole_chain_residual_fmol": wrong_whole["residual_fmol"],
        },
    }


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        print(json.dumps(check(closed_chain()), indent=2, allow_nan=False))
