"""profile_rehearsal.json: what the judge needs of the rehearsal, in its own shape.

    make_profile.py write     the file, formed from make_inputs.py and checked against it
    make_profile.py check     that every run, world and plant it names exists

The shape is the judge's (its README, section 5): `captures` gives every world's legacy folder and
where its summaries are, `engine_plants` the four plant runs (a plant run's `variant` is its key),
`not_blind` the two families of inv_base that are marked as a prototype's, `plant_targets` the runs
and families that the judge's own plants alter.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs  # noqa: E402
import rules  # noqa: E402

CROSS = ("inv_cross",)  # Captured in a set of its own (README).
TARGET = rules.HERE / "profile_rehearsal.json"


def captures():
    out = {}
    for name, world in make_inputs.WORLDS.items():
        kind = "assembly" if world["consumer"] in ("cell", "base") else "windows"
        entry = dict(
            set="captures_cross" if name in CROSS else "captures",
            kind=kind,
            folder=f"runs/{name}-{{step}}" + ("-s{seed}" if kind == "assembly" else ""),
        )
        if kind == "assembly":
            entry["summaries"] = "result" if world["consumer"] == "cell" else "ticks"
        out[name] = entry
    return out


def engine_plants():
    st6 = "ST6 availability on the other cell's channel"
    return {
        "inv_EP1": dict(
            change=[],
            named=["channel_K"],
            planted_run="PW-channel inv_cluster",
            distance=dict(world="inv_cluster", entry="channel_K", power_plant="channel"),
        ),
        "EP1": dict(
            change=[{"path": ["channels", "*", "max_permeability_m_per_s"], "multiply": 1.01}],
            named=["channel_K"],
            planted_run="PW-channel inv_release",
            distance=dict(world="inv_release", entry="channel_K", power_plant="channel"),
        ),
        "inv_EP2": dict(
            change=[],
            named=["channel_K"],
            planted_run=st6,
            distance=dict(world="inv_base", entry="channel_K", structural=st6),
        ),
        "EP2": dict(
            change=[{"exchange_channels": ["cell_0", "cell_1"]}],
            named=["channel_K"],
            planted_run=st6,
            distance=dict(world="inv_base", entry="channel_K", structural=st6),
        ),
    }


def profile():
    cluster = make_inputs.WORLDS["inv_cluster"]["candidate"][0]
    return dict(
        names=dict(
            inputs="inputs_rehearsal.json",
            legacy="legacy_rehearsal.json",
            paths="reference_paths_rehearsal.json",
            margins="margins_rehearsal.json",
            manifest="plants_manifest_rehearsal.json",
        ),
        captures=captures(),
        engine_plants=engine_plants(),
        not_blind={"base": ["inv_base s0 w0", "inv_base s0 w1"]},
        not_blind_pool_runs=["inv_base s0 pool"],
        notes={},
        counts={},
        runs=0,
        off_grid_runs=[f"inv_offgrid h={make_inputs.WORLDS['inv_offgrid']['candidate'][0]!r}"],
        plant_targets=dict(
            ionic="inv_cluster",
            other_schedule="inv_release",
            junctions="inv_junctions",
            restart=f"inv_cluster h={cluster!r} restart",
            engine_plant="inv_cluster plant channel",
            pool="inv_base s1 pool",
            pool_path=["inv_base s0 pool", "cell_0", "2"],
            not_blind="inv_base s0 w0",
            assembly="inv_base s1 w0",
        ),
    )


def check(value):
    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    runs = {r["name"]: r for r in inputs["runs"]}
    families = {r["family"] for r in inputs["runs"] if r["family"]}
    bad = []

    def need(where, name, pool):
        if name not in pool:
            bad.append((where, name))

    for name in value["captures"]:
        need("captures", name, inputs["worlds"])
    if set(value["captures"]) != set(inputs["worlds"]):
        bad.append(("captures", set(inputs["worlds"]) - set(value["captures"])))
    variants = {r["variant"] for r in inputs["runs"] if r["role"] == "plant"}
    if set(value["engine_plants"]) != variants:
        bad.append(("engine_plants", variants ^ set(value["engine_plants"])))
    for name in value["not_blind"]["base"]:
        need("not_blind", name, families)
    for name in value["not_blind_pool_runs"] + value["off_grid_runs"]:
        need("run", name, runs)
    t = value["plant_targets"]
    for k in ("ionic", "other_schedule", "junctions", "not_blind", "assembly"):
        need(k, t[k], families)
    for k in ("restart", "engine_plant", "pool"):
        need(k, t[k], runs)
    need("pool_path", t["pool_path"][0], runs)
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
