"""profile_rehearsal_part2.json: what the judge needs of Part 2's rehearsal, in a proposed shape.

    make_profile2.py write     the file, formed from make_inputs2.py and checked against it
    make_profile2.py check     that every run, world and plant it names exists

The judge has not yet given its shape for Part 2. This is Part 1's (its README, section 5) with four
additions, each named here:
- `paths`: the key of a cluster's pools in the reference paths (the registered clusters': `base`);
- an engine plant's `distance` of EP4's kind, whose planted run is a cluster's: it names the plant
  under `cluster_gated_calcium` of the margins, its seed index and its world ID;
- `retry_step_s`: each world's, half its last step (the registered: 1.5625 us);
- `names_of`: the invented name of each registered world and run that PART2.md section 14 names.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs2 as m  # noqa: E402

TARGET = m.HERE / "profile_rehearsal_part2.json"
SC14 = "SC14 availability on the other cell's channel"


def captures():
    out = {}
    for name in m.WORLDS:
        out[name] = dict(set="captures", kind="windows", folder=f"runs/{name}-{{step}}")
    for name in m.CLUSTERS:
        out[name] = dict(set="captures", kind="assembly", folder=f"runs/{name}-{{step}}-s{{seed}}",
                         summaries="ticks")  # fmt: skip
    return out


def engine_plants():
    release = dict(
        named=["store_release"], planted_run="P-release inv_ip3",
        distance=dict(world="inv_ip3", entry="store_release", power_plant="release"),
    )  # fmt: skip
    swapped = dict(
        named=["channel_K", "channel_K_summary"], planted_run=SC14,
        distance=dict(world="inv_cluster_gated", cluster_structural=SC14, seed_index=1, world_id=0),
    )  # fmt: skip
    more = [
        {"path": ["stores", "*", "membrane", "release", "permeability_m_per_s"], "multiply": 1.01}
    ]
    return {
        "inv_EP3": dict(change=[], **release),
        "EP3": dict(change=more, **release),
        "inv_EP4": dict(change=[], **swapped),
        "EP4": dict(change=[{"exchange_channels": ["cell_0", "cell_1"]}], **swapped),
    }


def profile():
    names = {f"{k}_calcium": f"inv_{k}" for k in m.KINDS}
    names |= {f"cluster_{k}_calcium": f"inv_cluster_{k}" for k in m.KINDS}
    h1 = m.WORLDS["inv_ip3"]["candidate"][0]
    names |= {
        "ip3_calcium h=1.25e-05 restart": f"inv_ip3 h={h1!r} restart",
        "ip3_calcium plant release": "inv_ip3 plant release",
        "cluster_gated_calcium plant swapped": "inv_cluster_gated plant swapped",
        "cluster_ip3_calcium s1 pool": "inv_cluster_ip3 s1 pool",
        "cluster_spatial_calcium s0 w0": "inv_cluster_spatial s0 w0",
    }
    sets = {
        v["consumer"]: [f"{k} s0 w{i}" for i in range(m.IDS)] for k, v in m.CLUSTERS.items()
    }  # fmt: skip
    return dict(
        names=dict(
            inputs="inputs_rehearsal_part2.json", legacy="legacy_rehearsal_part2.json",
            paths="reference_paths_rehearsal_part2.json", margins="margins_rehearsal_part2.json",
            manifest="plants_manifest_rehearsal_part2.json",
        ),
        captures=captures(),
        paths={k: m.PATHS_UNDER for k in m.CLUSTERS},
        engine_plants=engine_plants(),
        not_blind=sets,
        not_blind_pool_runs=[f"{k} s0 pool" for k in m.CLUSTERS],
        notes={},
        counts={},
        runs=0,
        off_grid_runs=[],
        retry_step_s={
            **{k: m.retry_step(k) for k in m.WORLDS},
            **{k: m.retry_step(v["child"]) for k, v in m.CLUSTERS.items()},
        },
        names_of=names,
        plant_targets=dict(
            ionic="inv_spatial", junctions="inv_spatial", restart=f"inv_ip3 h={h1!r} restart",
            engine_plant="inv_ip3 plant release",
            engine_plant_swapped="inv_cluster_gated plant swapped", pool="inv_cluster_ip3 s1 pool",
            pool_path=["inv_cluster_spatial s0 pool", "cell_0", "0"],
            not_blind="inv_cluster_spatial s0 w0", assembly="inv_cluster_spatial s1 w0",
        ),
    )  # fmt: skip


def check(value):
    inputs = json.loads((m.HERE / "inputs_rehearsal_part2.json").read_text())
    runs = {r["name"]: r for r in inputs["runs"]}
    families = {r["family"] for r in inputs["runs"] if r["family"]}
    bad = []

    def need(where, name, pool):
        if name not in pool:
            bad.append((where, name))

    if set(value["captures"]) != set(inputs["worlds"]):
        bad.append(("captures", set(inputs["worlds"]) ^ set(value["captures"])))
    variants = {r["variant"] for r in inputs["runs"] if r["role"] == "plant"}
    if set(value["engine_plants"]) != variants:
        bad.append(("engine_plants", variants ^ set(value["engine_plants"])))
    for consumer, names in value["not_blind"].items():
        for name in names:
            need("not_blind", name, families)
            if not any(r["family"] == name and r["consumer"] == consumer for r in inputs["runs"]):
                bad.append(("not_blind", consumer, name))
    for name in value["not_blind_pool_runs"]:
        need("run", name, runs)
    for name in value["paths"]:
        need("paths", name, inputs["worlds"])
    for name in value["names_of"].values():
        need("names_of", name, set(inputs["worlds"]) | set(runs) | families)
    t = value["plant_targets"]
    for k in ("ionic", "junctions", "not_blind", "assembly"):
        need(k, t[k], families)
    for k in ("restart", "engine_plant", "engine_plant_swapped", "pool"):
        need(k, t[k], runs)
    need("pool_path", t["pool_path"][0], runs)
    for world, step in value["retry_step_s"].items():
        child = inputs["worlds"][world].get("same_as", world)
        steps = {r["step_s"] for r in inputs["runs"] if r["world"] == child and r["step_s"]}
        if step != min(steps) / 2:
            bad.append(("retry_step_s", world, step))
    for b in bad:
        print("  BAD", *b)
    return not bad


if __name__ == "__main__":
    value = profile()
    if sys.argv[1:] == ["write"]:
        TARGET.write_text(json.dumps(value, indent=1) + "\n")
    if not check(value):
        raise SystemExit(1)
    print("profile", "written" if sys.argv[1:] == ["write"] else "checked")
