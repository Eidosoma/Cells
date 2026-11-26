"""SPEC section 8's invented set: worlds of the references' own, in the registered layouts.

The text-only blocks of the registered inputs (units, judged entries, plants, echo and the like) are taken
as they stand.  Every number of a kind (a volume, a rate, an amount, a conductance, a seed, a horizon, a
rung, a sample time, a count) is this module's own, and `equal_numbers` compares the two sets by kind.
"""

from __future__ import annotations

import copy

from . import draws
from .declared import copy_fmol

COPIES = 4
GUARD_STEPS = 5
PAIRS_PER_COPY = 144
SEEDS = {
    "W5": [554101, 554102, 554103, 554104],
    "W5-exact": [553101, 553102, 553103, 553104],
    "W6": [662105, 662106, 662107, 662108],
}
REACTION_STEPS, REACTION_SAMPLE = 64, 1.5625  # steps of the coarsest rung in one sample interval, s
GENE_STEPS, GENE_SAMPLE = 100, 46.875


def _population(species, assemble, dissolve, conductance, reads):
    read = {"species": species, "at": "cell"} if reads else None
    return {
        "unit_states": [{"id": "free", "subunits": 1}, {"id": "active", "subunits": 2}],
        "initial_counts": {"free": 2, "active": 0},
        "channels": [
            {"id": "assemble", "reactants": {"free": 2}, "products": {"active": 1}, "rate_constant": assemble,
             "read": read},
            {"id": "dissolve", "reactants": {"active": 1}, "products": {"free": 2}, "rate_constant": dissolve,
             "read": None},
        ],
        "transfer": {"species": species, "conductance_pL_per_s": {"free": 0.0, "active": conductance}},
    }


def _reactions_world(name, assemble, dissolve, reads, rungs, retry):
    return {
        "kind": "reactions",
        "cell_pL": 1.6,
        "node_pL": 0.9,
        "end_s": 25.0,
        "rows_fmol": {"S_cell": 1.1, "S_node": 0.13, "X": 8.2, "Y": 5.3, "W": 7e-06},
        "reactions": [
            {"id": "make", "reactants": {"X": 1}, "products": {"S": 1}, "rate_constant": 0.039, "rate_unit": "1/s"},
            {"id": "spend", "reactants": {"S": 1, "Y": 1}, "products": {"W": 1}, "rate_constant": 0.052,
             "rate_unit": "1/(mM s)"},
        ],
        "population": _population("S", assemble, dissolve, 0.31, reads),
        "rungs_s": rungs,
        "retry_rung_s": retry,
        "samples_s": [REACTION_SAMPLE * i for i in range(17)],
        "seeds": SEEDS[name],
        "copies": COPIES,
    }


def _gene_world(rungs, retry):
    return {
        "kind": "gene",
        "cell_pL": 1.7,
        "node_pL": 0.83,
        "end_s": 562.5,
        "rows_fmol": {"N": 0.0032, "M": 0.00031, "Pi": 0.0011, "R_cell": 2e-12, "R_node": 2e-12},
        "gene": {
            "template_copies": 13,
            "machines_copies": 40,
            "product": "R",
            "residues": 280,
            "stages": 2,
            "speed_per_s": 56.0,
            "draws": {"N": 1},
            "releases": {"Pi": 2},
            "saturation_mM": {"N": 0.0006},
            "initiation_per_mM_s": 91000000.0,
            "degradation": {"polymer": "R", "monomers": {"M": 280}, "rate_per_s": 0.0013},
            "mu_RT": {"N": -20.9, "M": 0.8, "Pi": 0.35, "R": -3234.0},
            "c0_mM": 1000.0,
        },
        "population": _population("R", 20000.0, 0.15, 0.026, True),
        "rungs_s": rungs,
        "retry_rung_s": retry,
        "samples_s": [GENE_SAMPLE * i for i in range(13)],
        "seeds": SEEDS["W6"],
        "copies": COPIES,
    }


def _halvings(first, count):
    return [first / 2**i for i in range(count)]


def _worlds():
    fine, gene = REACTION_SAMPLE / REACTION_STEPS, GENE_SAMPLE / GENE_STEPS
    return {
        "W5": _reactions_world("W5", 1.45, 1.2, True, _halvings(fine, 6), fine / 64),
        "W5-exact": _reactions_world("W5-exact", 1.7, 1.15, False, [fine, fine / 4], None),
        "W6": _gene_world(_halvings(gene, 6), gene / 64),
    }


def _run(arm, world, first, step, index, role, variant=None, suffix="", change=None):
    entry = {
        "name": f"{world} {first}-first h={step!r} c{index}{suffix}",
        "arm": arm,
        "world": world,
        "first": first,
        "copy": index,
        "step_s": step,
        "role": role,
        "variant": variant,
    }
    if change is not None:
        entry["change"] = change
    return entry


def _largest_propensity(world):
    channels = {channel["id"]: channel for channel in world["population"]["channels"]}
    assemble, dissolve = channels["assemble"], channels["dissolve"]
    rows = world["rows_fmol"]
    if assemble["read"] is None:
        concentration = 1.0
        basis = "constant rates"
    elif world["kind"] == "reactions":
        concentration = (rows["S_cell"] + rows["S_node"]) / world["cell_pL"]
        basis = (
            "the declared material of S only; S is also made from X without a static bound, so the definition "
            "leaves the site unchecked after the build"
        )
    else:
        gene = world["gene"]
        rate = gene["speed_per_s"] / (gene["residues"] / gene["stages"])
        produced = world["end_s"] * rate * gene["machines_copies"] * float(copy_fmol())
        concentration = (rows["R_cell"] + rows["R_node"] + produced) / world["cell_pL"]
        basis = "the declared R plus the horizon times the gene unit's largest production rate, kappa x machines"
    return 2 * assemble["rate_constant"] * concentration + dissolve["rate_constant"], basis


def build_inputs(registered):
    """inputs_invented.json, from the registered inputs' text blocks and this module's numbers."""
    worlds = _worlds()
    arms = {world: int(arm) for arm, world in registered["arms"].items()}
    firsts = registered["firsts"]
    families, runs = [], []
    for name, world in worlds.items():
        for first in firsts[name]:
            families.append(
                {
                    "id": f"{name} {first}-first",
                    "world": name,
                    "first": first,
                    "rungs_s": world["rungs_s"],
                    "retry_rung_s": world["retry_rung_s"],
                    "arm": arms[name],
                }
            )
            for step in world["rungs_s"]:
                runs += [_run(arms[name], name, first, step, c, "judged") for c in range(COPIES)]
    w5, w6 = worlds["W5"], worlds["W6"]
    restart = {
        "W5": {"run": f"W5 reactions-first h={w5['rungs_s'][2]!r} c0", "time_s": w5["samples_s"][8]},
        "W6": {"run": f"W6 gene-first h={w6['rungs_s'][2]!r} c0", "time_s": w6["samples_s"][6]},
    }
    runs.append(_run(1, "W5", "reactions", w5["rungs_s"][2], 0, "support", "restart", " restart"))
    runs.append(_run(3, "W6", "gene", w6["rungs_s"][2], 0, "support", "restart", " restart"))
    lie = "second halves in declared order"
    for step in w5["rungs_s"][-3:]:
        runs += [_run(1, "W5", "reactions", step, c, "plant", lie, " lie") for c in range(COPIES)]
    # The refused run breaks SPEC 2's placement (the largest propensity times the step is above 1).
    refused = REACTION_SAMPLE / 2
    runs.append(
        _run(2, "W5-exact", "reactions", refused, 0, "support", "refused", " refused", {"step_s": refused})
    )
    # The stopped run starts with more Pi, so that x of LAWS 3 crosses -1 inside the run.
    runs.append(
        _run(3, "W6", "gene", w6["rungs_s"][0], 0, "support", "stopped", " stopped", {"rows_fmol.Pi": 0.0084})
    )
    retry = dict(registered["retry"])
    retry["runs"] = [
        _run(1, "W5", "reactions", w5["retry_rung_s"], c, "judged", None, " retry") for c in range(COPIES)
    ]
    residues, stages = w6["gene"]["residues"], w6["gene"]["stages"]
    identities = copy.deepcopy(registered["identities"])
    swaps = {80.0: residues / stages, 160.0: 2.0 * residues / stages, 240.0: float(residues)}
    for terms in identities["W6"].values():
        for term in terms:
            sign = -1.0 if term[1] < 0 else 1.0
            term[1] = sign * swaps.get(abs(term[1]), abs(term[1]))
    start = {}
    for name in ("W5", "W5-exact"):
        rows = worlds[name]["rows_fmol"]
        start[name] = {
            "n_S_c": rows["S_cell"], "n_S_o": rows["S_node"], "n_X": rows["X"], "n_Y": rows["Y"], "n_W": rows["W"],
            "xi_1": 0.0, "xi_2": 0.0, "moved": 0.0,
        }
    rows = w6["rows_fmol"]
    machines = "machines_copies * copy_fmol"
    start["W6"] = {
        "n_N": rows["N"], "n_M": rows["M"], "n_Pi": rows["Pi"], "n_R_c": rows["R_cell"], "n_R_o": rows["R_node"],
        "free": machines, "engaged": 0.0, "transit": 0.0, "inits": 0.0, "exits": 0.0, "made": 0.0, "lost": 0.0,
        "moved": 0.0,
    }
    placement = []
    for name, world in worlds.items():
        largest, basis = _largest_propensity(world)
        placement.append(
            {
                "world": name,
                "largest_propensity_per_s": largest,
                "dt_a0_max_at_the_coarsest_step": largest * world["rungs_s"][0],
                "basis": basis,
            }
        )
    draw_rule = dict(registered["draws"])
    draw_rule["file"] = "draws_invented.json"
    draw_rule["pairs_per_copy"] = PAIRS_PER_COPY
    return {
        "schema": registered["schema"],
        "units": registered["units"],
        "constants": registered["constants"],
        "arms": registered["arms"],
        "firsts": firsts,
        "copies": COPIES,
        "worlds": worlds,
        "families": families,
        "runs": runs,
        "retry": retry,
        "judged": copy.deepcopy(registered["judged"]),
        "identities": identities,
        "start": start,
        "machines_start": {
            "W6": {"free_fmol": machines, "stage_complexes_fmol": [0.0] * stages}
        },
        "minimum_events": {
            "W5": {"per_copy": 20, "total": 100},
            "W5-exact": {"per_copy": 25, "total": 110},
            "W6": {"per_copy": 15, "total": 75},
        },
        "guard_steps": GUARD_STEPS,
        "restart": restart,
        "draws": draw_rule,
        "placement": placement,
        "plants": copy.deepcopy(registered["plants"]),
        "reference_accuracy": registered["reference_accuracy"],
        "echo": registered["echo"],
    }


def build_draws(registered_draws):
    """draws_invented.json: LAWS section 6's rule on this module's seeds, by the references' own Threefry."""
    worlds = {}
    for name, seeds in SEEDS.items():
        copies = []
        for index, seed in enumerate(seeds):
            u1, u2 = draws.copy_table(seed, 0, PAIRS_PER_COPY)
            copies.append(
                {
                    "copy": index, "seed": seed, "site_index": 0, "domain": "events",
                    "u1": [u.hex() for u in u1], "u2": [u.hex() for u in u2],
                }
            )
        worlds[name] = {"copies": copies}
    return {
        "kind": registered_draws["kind"],
        "rule": "LAWS.md section 6 (the references' own Threefry-2x32 implements it)",
        "jax_version": "none (no JAX was used)",
        "jax_threefry_partitionable": True,
        "worlds": worlds,
    }


def numbers_by_kind(inputs):
    """The numbers of one set of inputs, by kind; zeros are of no kind (SPEC section 8)."""
    kinds = {
        kind: set()
        for kind in (
            "volume", "horizon", "amount", "rate", "conductance", "concentration", "potential", "count", "chain",
            "rung", "time", "seed", "pairs", "guard", "minimum",
        )
    }
    for world in inputs["worlds"].values():
        kinds["volume"].update((world["cell_pL"], world["node_pL"]))
        kinds["horizon"].add(world["end_s"])
        kinds["amount"].update(world["rows_fmol"].values())
        kinds["rate"].update(r["rate_constant"] for r in world.get("reactions", ()))
        kinds["rate"].update(c["rate_constant"] for c in world["population"]["channels"])
        kinds["conductance"].update(world["population"]["transfer"]["conductance_pL_per_s"].values())
        kinds["rung"].update(world["rungs_s"])
        kinds["rung"].update(() if world["retry_rung_s"] is None else (world["retry_rung_s"],))
        kinds["time"].update(world["samples_s"])
        kinds["seed"].update(world["seeds"])
        gene = world.get("gene")
        if gene:
            kinds["count"].update((gene["template_copies"], gene["machines_copies"]))
            kinds["chain"].update((gene["residues"], gene["stages"], gene["residues"] // gene["stages"]))
            kinds["rate"].update(
                (gene["speed_per_s"], gene["initiation_per_mM_s"], gene["degradation"]["rate_per_s"])
            )
            kinds["concentration"].update(gene["saturation_mM"].values())
            kinds["potential"].update(gene["mu_RT"].values())
    kinds["time"].update(entry["time_s"] for entry in inputs["restart"].values())
    kinds["rung"].update(run["step_s"] for run in inputs["runs"])
    kinds["pairs"].add(inputs["draws"]["pairs_per_copy"])
    kinds["guard"].add(inputs["guard_steps"])
    for counts in inputs["minimum_events"].values():
        kinds["minimum"].update(counts.values())
    return {kind: {float(v) for v in values} - {0.0} for kind, values in kinds.items()}


def equal_numbers(invented, registered):
    """The numbers of a kind that the two sets share: none is allowed."""
    left, right = numbers_by_kind(invented), numbers_by_kind(registered)
    return {kind: sorted(left[kind] & right[kind]) for kind in left if left[kind] & right[kind]}
