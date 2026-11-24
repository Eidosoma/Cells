"""The writer of FR-45's reference files (SPEC.md §5) and of its invented format sample.

One JSON file per world: reference_W1.json, reference_W1eq.json, reference_W1p.json,
reference_W2.json, reference_W3.json, reference_W4.json, reference_W5.json and
reference_W6.json. Floats are written with repr (round trip exact) and times are the
inputs' floats. Each file's keys, in order:

  schema, invented, world, units, equilibrium, trajectory, balances, [wash], heats, pairs,
  spread, spread_note, distance_at_horizon, [closed_form], [stage], plants, provenance

- world: the inputs echoed (constants, nodes, patches, ligands, free amounts, sets with
  their capacity S, populations, the declared start a_x, dt, times, horizon, wash).
- equilibrium: {totals, sets {id: R}, populations {id: B}, pools {"L@node": n}, residual,
  residual_definition, wang {set: {gap}}}; wang is {} where no set has two ligands alone.
- trajectory: [{observable, time_s, value, tolerance_gap}], observables n:<ligand>@<node>,
  R:<set>, B:<population>; at every observation time. value is the high-precision Taylor
  solution rounded once; tolerance_gap is |DOP853(rtol 1e-12) - DOP853(rtol 1e-13)|.
- balances: {ligands: [{ligand, node, time_s, total}], sets: [{set, time_s, sites}]}.
- wash (W2): {ligand: {removed, supplied}}.
- heats: {intervals: [{node, start_s, end_s, heat, bound, tolerance_gap}],
  G: [{node, time_s, G}], wash_free_energy_change (W2): [{node, time_s,
  free_energy_change, sets_part}]}.
- pairs: [{criterion, observable, time_s, [start_s, end_s], [dt_s], class, value,
  tolerance, against, [scale], [minimum]}]; class is constant, derived or band; a constant
  holds its value ("unchanged", "refused", "completes") and a null tolerance; a derived or
  band pair holds its tolerance; value null means the judge compares the engine against its
  own state (named in `against`). start_s and end_s are on heat pairs (C3a, C3b, C3c);
  dt_s is on every pair whose tolerance counts steps (C2b, C3b, C4a, C5, C8, C10), in every
  world; scale is on C8's pairs, whose tolerance is null except at the finest dt, and C8's
  two ratio pairs carry minimum (time_s, value and tolerance null).
- spread: "none" (nothing is drawn).
- distance_at_horizon: {observable: |x(T) - x_eq|}.
- closed_form (W4): [{observable, time_s, value, gap_from_ode}].
- stage (W5): {h_s, loads_times_h {L_n, L_R_summed, L_R_per_population, L_B},
  max_hL_summed, max_hL_per_population, threshold, verdict_summed, verdict_per_population}.
- plants: [{plant, criterion, compared, honest, planted, distance_in_bounds, [world],
  [bound_used], [assumption], [verdict_honest, verdict_planted]}]; compared is
  {observable, time_s} or, for a heat, {observable, start_s, end_s}.
- A refusal world (W5) has no trajectory: equilibrium and distance_at_horizon are null and
  trajectory, balances' and heats' lists are empty; it carries stage, C7 and P4.
- provenance: {references_revision, tree_clean, writer_version, regeneration_hash_seeds,
  spec, profile}.
"""

from __future__ import annotations

import json
from decimal import Decimal

import fr45ref_build as BLD
import fr45ref_hp as HP
import fr45ref_worlds as WL
from fr45ref_hp import ZERO, D, dmax, f64

SCHEMA = "fr45-reference/1"
WRITER_VERSION = "fr45-references-writer 1"
REGENERATION_HASH_SEEDS = (0, 1, 2)
FILE_ORDER = ("W1", "W1eq", "W1p", "W2", "W3", "W4", "W5", "W6")

CRITERIA = {
    "W1": ["C1", "C2a", "C3a", "C3b", "C3c", "C5", "C9", "C10"],
    "W1eq": ["C2b", "C3a", "C3b", "C3c", "C5", "C10"],
    "W1p": ["C1", "C3a", "C3b", "C3c", "C5", "C9", "C10"],
    "W2": ["C1", "C2a", "C3a", "C3b", "C3c", "C4a", "C4b", "C4c", "C5", "C6", "C10"],
    "W3": ["C1", "C2a", "C3a", "C3b", "C3c", "C5", "C9", "C10"],
    "W4": ["C3a", "C3b", "C3c", "C5", "C8", "C10"],
    "W5": ["C7"],
    "W6": ["C1", "C2a", "C3a", "C3b", "C3c", "C5", "C9", "C10"],
}
W2_WASH_ALONE_TIME = 5.0

INVENTED_BANNER = (
    "INVENTED INPUTS. This file is the writer's format sample for the judge, written on "
    "invented volumes, constants, counts and times. It is not a reference for any "
    "registered world and none of its numbers belongs to FR-45. It carries every section "
    "and every criterion's pairs, so some (C2b against this world's own root, C7, C8 on "
    "every set) are there for their format only. A refusal world (W5) differs: its "
    "equilibrium and distance_at_horizon are null and its trajectory, balances' and heats' "
    "lists are empty."
)


def dumps(payload: dict) -> str:
    return json.dumps(payload, indent=1, ensure_ascii=True, allow_nan=False) + "\n"


def make_provenance(revision: str, tree_clean: bool, spec: dict, profile: str) -> dict:
    return {
        "references_revision": revision,
        "tree_clean": tree_clean,
        "writer_version": WRITER_VERSION,
        "regeneration_hash_seeds": list(REGENERATION_HASH_SEEDS),
        "spec": spec,
        "profile": profile,
    }


def _payload(
    run: BLD.WorldRun,
    provenance: dict,
    *,
    invented: bool,
    equilibrium_note: str | None,
    start_note: str | None = None,
    extra_pairs: dict | None = None,
    plants=None,
    closed=None,
    stage=None,
) -> dict:
    d: dict = {}
    if invented:
        d["INVENTED"] = INVENTED_BANNER
    d["schema"] = SCHEMA
    d["invented"] = invented
    d["world"] = run.world_echo(start_note)
    d["units"] = BLD.UNITS
    if run.has_traj:
        d["equilibrium"] = run.equilibrium_section(equilibrium_note)
        d["trajectory"] = run.trajectory_section()
        d["balances"] = run.balances_section()
        if run.world["wash"] is not None:
            rec = run.ode["B"]["records"]
            wash = run.world["wash"]
            d["wash"] = {}
            for p, pool in enumerate(run.sys.pools):
                if pool["node"] == wash["node"]:
                    rem, _ = rec[pool["ligand"]]
                    d["wash"][pool["ligand"]] = {
                        "removed": f64(rem),
                        "supplied": HP.fq(BLD.supplied_exact(run.sys, wash, p)),
                    }
        d["heats"] = run.heats_section()
    else:
        d["equilibrium"] = None
        d["trajectory"] = []
        d["balances"] = {"ligands": [], "sets": []}
        d["heats"] = {"intervals": [], "G": []}
    d["pairs"] = run.build_pairs(extra_pairs or {})
    d["spread"] = "none"
    d["spread_note"] = BLD.CLASS_NOTE
    d["distance_at_horizon"] = run.distance_at_horizon() if run.has_traj else None
    if closed is not None:
        d["closed_form"] = closed
    if stage is not None:
        d["stage"] = {k: v for k, v in stage.items() if not k.startswith("_")}
    d["plants"] = plants or []
    d["provenance"] = provenance
    return d


def _closed_form_rows(run: BLD.WorldRun, s: int) -> tuple[list, Decimal]:
    sysm = run.sys
    y0 = sysm.start()
    rows = []
    worst = ZERO
    bs = sysm.pops_of_set[s]
    for k, t in enumerate(run.times, start=1):
        cf = BLD.closed_form(sysm, y0, D(t), s)
        vals = [
            (f"B:{sysm.pops[bs[0]]['id']}", cf["B"][0], sysm.i_pop(bs[0])),
            (f"B:{sysm.pops[bs[1]]['id']}", cf["B"][1], sysm.i_pop(bs[1])),
            (f"R:{sysm.sets[s]['id']}", cf["R"], sysm.i_set(s)),
        ]
        for name, v, i in vals:
            gap = abs(v - run.yB[k][i])
            worst = max(worst, gap / sysm.Sd[s])
            rows.append(
                {"observable": name, "time_s": t, "value": f64(v), "gap_from_ode": f64(gap)}
            )
    return rows, worst


def _numeric(builder):
    world, _ = builder()
    return WL.numeric(world)


def w1eq_world(w1_run: BLD.WorldRun) -> tuple[dict, dict]:
    """W1eq's start from W1's root: occupancy B_b/S and n_l = N_l - sum B_b, rounded once."""
    world = WL.numeric(WL.world_W1eq_inputs()[0])
    sysm = w1_run.sys
    root = w1_run.eq["root"]
    occ = {}
    for b, q in enumerate(sysm.pops):
        occ[q["id"]] = f64(root[sysm.i_pop(b)] / sysm.Sd[q["set_index"]])
    free = {}
    for p, pool in enumerate(sysm.pools):
        bound = sum((root[sysm.i_pop(b)] for b in sysm.pops_of_pool[p]), ZERO)
        free[(pool["ligand"], pool["node"])] = f64(pool["n0"] - bound)
    world["populations"] = [dict(p, occupancy=occ[p["id"]]) for p in world["populations"]]
    world["free"] = [dict(f, n=free[(f["ligand"], f["node"])]) for f in world["free"]]
    return world, {"occupancy": occ, "free": {f"{k[0]}@{k[1]}": v for k, v in free.items()}}


def build_all(provenance: dict, profile: str = "reference", only=None, log=print):
    """Every registered world's payload and the accuracy record."""
    HP.use_working_context(BLD.PROFILES[profile]["digits"])
    files: dict[str, dict] = {}
    acc: dict = {
        "normalisation": (
            "amounts by the node's scale s_node, heats by E, C8 by S, plants by their "
            "criterion's bound (CRITERIA.md)"
        ),
        "worlds": {},
    }
    want = set(only) if only else set(FILE_ORDER)

    def note(wid, run, extra=None):
        a = dict(run.acc)
        if extra:
            a.update(extra)
        acc["worlds"][wid] = a

    # W1 first: W1eq's start comes from its root.
    w1 = BLD.WorldRun(_numeric(WL.world_W1), profile, CRITERIA["W1"])
    w1.compute_equilibrium()
    log("W1 integrated")
    if "W1" in want:
        files["W1"] = _payload(
            w1, provenance, invented=False, equilibrium_note="the start's totals"
        )
        note("W1", w1)

    if "W1eq" in want:
        weq, written = w1eq_world(w1)
        r = BLD.WorldRun(weq, profile, CRITERIA["W1eq"])
        r.compute_equilibrium()
        same = all(f64(r.eq["root"][i]) == f64(w1.eq["root"][i]) for i in range(r.sys.n))
        gap = dmax(
            abs(r.eq["root"][i] - w1.eq["root"][i]) / w1.snode[r.sys.node_of_component(i)]
            for i in range(r.sys.n)
        )
        files["W1eq"] = _payload(
            r,
            provenance,
            invented=False,
            equilibrium_note="the start's totals (the written start below)",
            start_note=(
                "written from W1's R-eq root: initial occupancy B_b/S_s and free amount "
                "N_l - sum B_b, each the binary64 nearest to the exact value"
            ),
            extra_pairs={"C2b_root": w1.eq["root"]},
        )
        note(
            "W1eq",
            r,
            {
                "own_root_equals_W1_root_in_binary64": same,
                "own_root_vs_W1_root_over_s_node": f64(gap),
            },
        )
        log("W1eq integrated")

    if "W1p" in want:
        r = BLD.WorldRun(_numeric(WL.world_W1p), profile, CRITERIA["W1p"])
        r.compute_equilibrium()
        rows_same = all(r.yB[k] == w1.yB[k] for k in range(len(r.yB)))
        a_same = all(
            (r.ode["A"][rt]["states"][k] == w1.ode["A"][rt]["states"][k]).all()
            for rt in r.profile["rtols"]
            for k in range(len(r.yB))
        )
        if not (rows_same and a_same):
            raise RuntimeError("W1p's rows differ from W1's")
        payload = _payload(
            r, provenance, invented=False, equilibrium_note="the start's totals (W1's)"
        )
        plants, pacc = BLD.plants_W1p(r, BLD.PROFILES[profile])
        payload["plants"] = plants
        files["W1p"] = payload
        note("W1p", r, {"rows_bitwise_equal_W1": True, "plants": pacc})
        log("W1p integrated, plants sized")

    if "W2" in want:
        r = BLD.WorldRun(_numeric(WL.world_W2), profile, CRITERIA["W2"])
        r.compute_equilibrium()
        payload = _payload(
            r,
            provenance,
            invented=False,
            equilibrium_note="the post-wash totals: R-ode's state at 4.0 s through SPEC §1.4's map",
            extra_pairs={"wash_alone_time": W2_WASH_ALONE_TIME},
        )
        plants, pacc = BLD.plants_W2(r, BLD.PROFILES[profile], W2_WASH_ALONE_TIME)
        payload["plants"] = plants
        files["W2"] = payload
        note("W2", r, {"plants": pacc})
        log("W2 integrated, plants sized")

    if "W3" in want:
        r = BLD.WorldRun(_numeric(WL.world_W3), profile, CRITERIA["W3"])
        r.compute_equilibrium()
        payload = _payload(r, provenance, invented=False, equilibrium_note="the start's totals")
        w3p_world = _numeric(WL.world_W3p)
        hp = BLD.WorldRun(w3p_world, profile, [])
        same = all(hp.yB[k] == r.yB[k] for k in range(len(hp.yB)))
        if not same:
            raise RuntimeError("W3p's rows differ from W3's")
        plants, pacc = BLD.plants_W3p(hp, w3p_world, BLD.PROFILES[profile])
        payload["plants"] = plants
        files["W3"] = payload
        snode_same = all(hp.snode[k] == r.snode[k] for k in r.snode)
        note(
            "W3",
            r,
            {"W3p_rows_bitwise_equal_W3": True, "W3p_s_node_equals_W3": snode_same, "plants": pacc},
        )
        log("W3 integrated, W3p plants sized")

    if "W4" in want:
        r = BLD.WorldRun(_numeric(WL.world_W4), profile, CRITERIA["W4"])
        r.compute_equilibrium()
        closed, worst = _closed_form_rows(r, 0)
        files["W4"] = _payload(
            r,
            provenance,
            invented=False,
            equilibrium_note="the start's totals",
            extra_pairs={"C8_finest": r.world["dt_texts"][-1]},
            closed=closed,
        )
        note("W4", r, {"closed_form_gap_over_S_max": f64(worst)})
        log("W4 integrated")

    if "W5" in want:
        r = BLD.WorldRun(_numeric(WL.world_W5), profile, CRITERIA["W5"])
        st = BLD.stage_section(r.sys, r.world["dt"][0])
        files["W5"] = _payload(
            r,
            provenance,
            invented=False,
            equilibrium_note=None,
            stage=st,
            plants=[BLD.plant_P4(st)],
        )
        note("W5", r)
        log("W5 loads")

    if "W6" in want:
        r = BLD.WorldRun(_numeric(WL.world_W6), profile, CRITERIA["W6"])
        r.compute_equilibrium()
        files["W6"] = _payload(r, provenance, invented=False, equilibrium_note="the start's totals")
        note("W6", r)
        log("W6 integrated")

    return {f"reference_{wid}.json": files[wid] for wid in FILE_ORDER if wid in files}, acc


# ------------------------------------------------------------------------------------------
# The format sample: invented inputs exercising every section and every pair class.


def invented_world() -> dict:
    """INVENTED. Two nodes, a shared ligand, a set inside a cell, a wash and two dt values."""
    world = {
        "id": "INVENTED-X",
        "title": "INVENTED format-sample world (not FR-45's)",
        "nodes": [
            {"id": "vessel", "kind": "node", "V": "2.5"},
            {"id": "pod", "kind": "cell", "V": "0.4"},
        ],
        "patches": [{"id": "pod_face", "inside": "pod", "outside": "vessel"}],
        "ligands": ["Q1", "Q2", "Q3", "Q4", "Q5"],
        "free": [
            {"ligand": "Q1", "node": "vessel", "n": "3.0e-3"},
            {"ligand": "Q2", "node": "vessel", "n": "2.0e-3"},
            {"ligand": "Q3", "node": "vessel", "n": "0.5e-3"},
            {"ligand": "Q4", "node": "pod", "n": "0.6e-3"},
            {"ligand": "Q5", "node": "pod", "n": "0.3e-3"},
        ],
        "sets": [
            {
                "id": "lattice",
                "owner": "node vessel",
                "faces": "vessel",
                "copies": "3000000.0",
                "sites_per_copy": "2",
                "accessible_fraction": "0.5",
            },
            {
                "id": "sheet",
                "owner": "node vessel",
                "faces": "vessel",
                "copies": "800000.0",
                "sites_per_copy": "1",
                "accessible_fraction": "0.9",
            },
            {
                "id": "liner",
                "owner": "patch pod_face, inside face",
                "faces": "pod",
                "copies": "500000.0",
                "sites_per_copy": "3",
                "accessible_fraction": "0.4",
            },
        ],
        "populations": [
            {
                "id": "lattice_Q1",
                "set": "lattice",
                "ligand": "Q1",
                "k_on": "900.0",
                "k_off": "0.45",
                "occupancy": "0.15",
            },
            {
                "id": "lattice_Q2",
                "set": "lattice",
                "ligand": "Q2",
                "k_on": "2.5e3",
                "k_off": "0.2",
                "occupancy": "0.0",
            },
            {
                "id": "lattice_Q3",
                "set": "lattice",
                "ligand": "Q3",
                "k_on": "1.2e3",
                "k_off": "0.6",
                "occupancy": "0.05",
            },
            {
                "id": "sheet_Q2",
                "set": "sheet",
                "ligand": "Q2",
                "k_on": "1.1e3",
                "k_off": "0.35",
                "occupancy": "0.1",
            },
            {
                "id": "liner_Q4",
                "set": "liner",
                "ligand": "Q4",
                "k_on": "1.8e3",
                "k_off": "0.6",
                "occupancy": "0.0",
            },
            {
                "id": "liner_Q5",
                "set": "liner",
                "ligand": "Q5",
                "k_on": "700.0",
                "k_off": "0.25",
                "occupancy": "0.2",
            },
        ],
        "dt": ["0.01", "0.005"],
        "times": ["0.1", "0.25", "0.26", "0.5"],
        "horizon": "0.5",
        "wash": {
            "t": "0.25",
            "node": "vessel",
            "f": "0.25",
            "buffer": [
                {"ligand": "Q1", "c": "1e-12"},
                {"ligand": "Q2", "c": "4.0e-4"},
                {"ligand": "Q3", "c": "1e-12"},
            ],
        },
    }
    return WL.numeric(world)


SAMPLE_CRITERIA = [
    "C1",
    "C2a",
    "C2b",
    "C3a",
    "C3b",
    "C3c",
    "C4a",
    "C4b",
    "C4c",
    "C5",
    "C6",
    "C7",
    "C8",
    "C9",
    "C10",
]
SAMPLE_PROVENANCE = {
    "references_revision": "INVENTED (a format sample has no generating revision)",
    "tree_clean": True,
    "writer_version": WRITER_VERSION,
    "regeneration_hash_seeds": list(REGENERATION_HASH_SEEDS),
    "spec": {"note": "invented inputs; SPEC.md §5's format"},
    "profile": "sample",
}


def build_sample() -> dict:
    HP.use_working_context(BLD.PROFILES["sample"]["digits"])
    world = invented_world()
    prof = BLD.PROFILES["sample"]
    r = BLD.WorldRun(world, "sample", SAMPLE_CRITERIA)
    r.compute_equilibrium()
    st = BLD.stage_section(r.sys, world["dt"][0])
    liner = r.sys.set_index["liner"]
    closed, _ = _closed_form_rows(r, liner)
    payload = _payload(
        r,
        dict(SAMPLE_PROVENANCE),
        invented=True,
        equilibrium_note="INVENTED: the post-wash totals",
        extra_pairs={
            "wash_alone_time": 0.5,
            "C8_finest": world["dt_texts"][-1],
            "C2b_root": r.eq["root"],
        },
        closed=closed,
        stage=st,
    )
    plants = []
    best, _, _ = BLD.plant_dynamics_C1(r, world, prof, "P1", skip_R=True, unshared=True)
    plants.append(BLD._plant_entry("P1", "C1", best, assumption=BLD.P1_ASSUMPTION))
    best, _, _ = BLD.plant_dynamics_C1(r, BLD.crossed_koff_world(world), prof, "P2")
    plants.append(BLD._plant_entry("P2", "C1", best))
    for plant in ("P3", "P6"):
        entry, _ = BLD.plant_energy(r, plant)
        plants.append(entry)
    plants.append(BLD.plant_P4(st))
    p5, _ = BLD.plants_W2(r, prof, 0.5)
    plants += p5
    p7, _ = BLD.plants_W3p(r, world, prof, label=world["id"])
    plants += p7
    plants.append(BLD.plant_P8(r))
    plants.append(BLD.plant_P9(r))
    payload["plants"] = plants
    return payload
