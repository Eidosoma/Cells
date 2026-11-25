"""Checks of Part 2's rehearsal inputs that need no engine run.

    checks2.py [SPEC]                       grid, ratios, offsets, fuel and the rules
    PYTHONPATH=SNAPSHOT/src:SNAPSHOT checks2.py definitions

- grid: every time of every world, against SPEC section 4's rule (2 eps t) at the four steps (the
  three and the retry's) and at the legacy steps; the horizon is the steps' product bit for bit;
- ratios: `inv_amounts` against PART2.md section 15's thresholds, the fixed charges' residuals;
- offsets: the geometry factors of section 8 in every world;
- fuel: A of `inv_fuel`, and what its potentials leave of the pumps' number (section 2.4);
- rules: the registered worlds' numbers by rules2.py (SPEC is the spec folder, or a copy of it at
  the criteria's commit);
- definitions: every block against the snapshot's own parse of the legacy definition, leaf by leaf.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rehearsal"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_arrays2 as la  # noqa: E402
import make_inputs2 as m  # noqa: E402
import rules  # noqa: E402
import rules2  # noqa: E402

THRESHOLDS = {"cytosol": 1.7e4, "store": 4.4, "n_out": 22, "voltage": 7.7e3, "store_voltage": 4.8}


def inputs():
    return json.loads((m.HERE / "inputs_rehearsal_part2.json").read_text())


def grid():
    data, bad = inputs(), []
    for name, w in m.WORLDS.items():
        block = data["worlds"][name]
        steps = [*w["candidate"], m.retry_step(name)]
        legacy = [w["legacy"] / k for k in (1, 2, 4)]
        times = {
            "end": [w["end"]], "rows": la.compared(w), "potential": list(w["potentials"]),
            "declared": [v for g in block["history_times"].values() for v in g.values()],
        }  # fmt: skip
        for cluster in (c for c, v in m.CLUSTERS.items() if v["child"] == name):
            times["summary"] = list(m.CLUSTERS[cluster]["summaries"])
        if name == m.RESTART[0]:
            times["restart"] = [m.RESTART[1]]
        worst = 0.0
        for what, values in times.items():
            for t in values:
                for h in (*steps, *legacy):
                    k = round(t / h)
                    if t:
                        worst = max(worst, abs(t - k * h) / (rules.EPS * t))
                    if not rules.on_grid(t, h):
                        bad.append((name, what, t, h))
        for h in (*steps, *legacy):
            if rules.grid_steps(w["end"], h) * h != w["end"]:
                bad.append((name, "the horizon is not the steps' product", h))
        counts = {h: rules.grid_steps(w["end"], h) for h in steps}
        print(f"{name}: steps {counts}, {len(times['rows'])} compared rows, the worst time "
              f"{worst:.2f} eps t off its grid point")  # fmt: skip
    for b in bad:
        print("  BAD", *b)
    return not bad


def ratios():
    data, ok = inputs()["worlds"], True
    w = data["inv_amounts"]
    r = {k: v / w["scales"][k] for k, v in w["amount_refs"].items()}
    groups = {
        "cytosol": [k for k in r if k.startswith("cyt_")],
        "store": [k for k in r if k.startswith("store_") and k != "store_voltage"],
        "n_out": [k for k in r if k.startswith("n_out_")],
        "voltage": ["voltage"], "store_voltage": ["store_voltage"],
    }  # fmt: skip
    for g, limit in THRESHOLDS.items():
        best = max(r[k] for k in groups[g])
        ok &= best >= limit
        short = {k: float(f"{r[k]:.3g}") for k in groups[g]}
        print(f"inv_amounts {g}: amount_refs/scales {short}"
              f", at least {limit:g} at one: {'ok' if best >= limit else 'SHORT'}")  # fmt: skip
    for name in ("inv_amounts", "inv_spatial"):
        for group in ("cells", "outside"):
            for c, v in data[name]["ionic"][group].items():
                res = rules.charge_residual_C(
                    m.SPECIES, v["initial_amount_fmol"], v["fixed_charge_equivalent_fmol"],
                    v["initial_charge_C"],
                )  # fmt: skip
                fine = 0 < abs(res) <= 5.1e-24 or name != "inv_amounts"
                ok &= fine and abs(res) <= 1e-20
                print(f"{name} {c}: rule less declared {res:.2e} C")
    return ok


def offsets():
    ok = True
    for name, w in m.WORLDS.items():
        factor, row, ratio = rules2.World(m.blocks(w)).conductances()
        fine = factor <= rules2.ROW_FACTOR and factor * ratio <= 2.01 * 0.53
        ok &= fine
        print(f"{name}: row factor {factor:.4f} (at most 2.01), conductance ratio {ratio:.4f}, "
              f"largest row sum {row:.3e}")  # fmt: skip
    return ok


def fuel():
    b = inputs()["worlds"]["inv_fuel"]
    p = b["fuel_standard_mu_RT"]
    pumps = [s["membrane"]["pump"] for s in b["stores"].values()]
    pumps += [v["pump"] for v in b["plasma_transport"].values()]
    rt = rules.R * b["ionic"]["temperature_K"]
    made = rt * (p["ADP"] + p["Pi"] - p["ATP"] + math.log(1000 / 1.0))
    a = abs(p["ATP"]) + abs(p["ADP"]) + abs(p["Pi"]) + math.log(1000 / 1.0)
    ok = 2500 <= a <= 3200
    for q in pumps:
        g = q["delta_g0_at_1M_J_per_mol"]
        allowed = 1e-12 * abs(g) + 16 * rules.EPS * rt * a
        ok &= abs(made - g) <= allowed
        print(f"inv_fuel: A {a:.1f}, formed less declared {made - g:.2e} J/mol, allowed "
              f"{allowed:.2e}, 1e-12 of itself {1e-12 * abs(g):.2e}")  # fmt: skip
    return ok


def definitions():
    """The blocks against the snapshot's own parse of the legacy definitions."""
    from cells.definitions.specs import parse_spec

    data, leaves, ok = inputs()["worlds"], 0, True

    def same(what, a, b, relative=0.0):
        nonlocal leaves, ok
        leaves += 1
        if a != b and not (relative and abs(a - b) <= relative * abs(b)):
            ok = False
            print("  DIFFER", what, a, b)

    for name in m.WORLDS:
        b = data[name]
        raw = parse_spec(m.definition(name, "h")).to_dict()
        model, ion = raw["model"], raw["model"]["ionic"]
        i = b["ionic"]
        same((name, "T"), ion["temperature_K"], i["temperature_K"])
        same((name, "species"), {s["id"]: s["valence"] for s in ion["species"]}, i["species"])
        regions = {o["id"]: o for o in [ion["extracellular"], *ion["surroundings"]]}
        same((name, "regions"), set(regions), set(i["outside"]))
        for o, v in regions.items():
            for k in ("volume_pL", "fixed_charge_equivalent_fmol", "initial_amount_fmol"):
                same((name, o, k), v[k], i["outside"][o][k])
        same((name, "gauge"), ion["closure"]["gauge_reference"], i["closure"]["gauge_reference"])
        for c in ion["cells"]:
            cid, mid = c["cell"]["id"], c["membrane"]["id"]
            cell, mem, want = c["cell"], c["membrane"], i["membranes"][mid]
            for k in ("volume_pL", "fixed_charge_equivalent_fmol", "initial_amount_fmol",
                      "initial_voltage_V"):  # fmt: skip
                same((name, cid, k), cell[k], i["cells"][cid][k])
            cap = mem["area_m2"] * mem["specific_capacitance_F_per_m2"]
            same((name, mid, "capacitance"), cap, want["capacitance_F"])
            same((name, cid, "charge"), cap * cell["initial_voltage_V"],
                 i["cells"][cid]["initial_charge_C"])  # fmt: skip
            for k in ("inside", "outside", "area_m2"):
                same((name, mid, k), mem[k], want[k])
            same((name, mid, "leak"), mem["passive"]["permeability_m_per_s"],
                 want["passive"]["permeability_m_per_s"])  # fmt: skip
            for k in ("capacity_fmol_per_s", "km_na_mM", "km_k_mM", "km_atp_mM", "roles",
                      "stoichiometry"):  # fmt: skip
                same((name, mid, k), mem["pump"][k], want["pump"][k])
            for k in ("atp_mM", "adp_mM", "pi_mM", "delta_g0_J_per_mol"):
                same((name, mid, k), mem["pump"]["metabolism"][k], want["pump"]["metabolism"][k])
            ch, cb = c["channel"], i["channels"][c["channel"]["id"]]
            for k in ("membrane_id", "species_id", "max_permeability_m_per_s", "abundance",
                      "initial_gate"):  # fmt: skip
                same((name, ch["id"], k), ch[k], cb[k])
        for j in ion["junctions"]:
            jb = i["junctions"][j["id"]]
            for k in ("from_cell", "to_cell", "area_m2", "permeability_m_per_s"):
                same((name, j["id"], k), j[k], jb[k])
            for k in ("initial_gate", "minimum_open_fraction", "threshold_voltage_V"):
                same((name, j["id"], k), j["gate"][k], jb["gate"][k])
        for f in ion["faces"]:
            for k in ("sender", "receiver", "area_m2", "length_m", "diffusivity_m2_per_s"):
                same((name, f["id"], k), f[k], i["faces"][f["id"]][k])
        rt = rules.R * ion["temperature_K"]

        def pump(what, got, want, rt=rt):
            for k in ("capacity_fmol_per_s", "km_ca_mM", "km_atp_mM", "atp_mM", "adp_mM", "pi_mM"):
                same((*what, k), got[k], want[k])
            same((*what, "dg0"), got["delta_g0_J_per_mol"] + rt * math.log(1000),
                 want["delta_g0_at_1M_J_per_mol"], 1e-15)  # fmt: skip

        for row in model["stores"]:
            c, s, want = row["cell_id"], row["model"], b["stores"][row["cell_id"]]
            for k in ("temperature_K", "standard_concentration_mM"):
                same((name, c, k), s[k], want[k])
            same((name, c, "rows"), {x["id"]: x["valence"] for x in s["species"]},
                 {x: v["valence"] for x, v in want["species"].items()})  # fmt: skip
            same((name, c, "mu"), {x["id"]: float(x["standard_mu_RT"]) for x in s["species"]},
                 {x: v["standard_mu_RT"] for x, v in want["species"].items()})  # fmt: skip
            for part in s["compartments"]:
                for k in ("volume_pL", "initial_amount_fmol"):
                    same((name, c, part["id"], k), part[k], want["compartments"][part["id"]][k])
            same((name, c, "reactions"), {r["id"] for r in s["reactions"]}, set(want["reactions"]))
            for r in s["reactions"]:
                rb = want["reactions"][r["id"]]
                for k in ("compartment", "forward_rate_per_s"):
                    same((name, c, r["id"], k), r[k], rb[k])
                for k in ("reactants", "products"):
                    got = {x: n for x, n in r[k].items() if n}
                    same((name, c, r["id"], k), got, rb[k])
            mem, mb = s["membrane"], want["membrane"]
            for k in ("cytosol", "er", "area_m2", "initial_voltage_V"):
                same((name, c, "membrane", k), mem[k], mb[k])
            same((name, c, "store capacitance"),
                 mem["area_m2"] * mem["specific_capacitance_F_per_m2"],
                 mb["capacitance_F"])  # fmt: skip
            same((name, c, "store permeability"), mem["permeability_m_per_s"],
                 mb["permeability_m_per_s"])  # fmt: skip
            pump((name, c, "store pump"), mem["pump"], mb["pump"])
            for k in ("permeability_m_per_s", "activation_mM", "activation_n", "inhibition_mM",
                      "inhibition_n"):  # fmt: skip
                same((name, c, "release", k), mem["release"][k], mb["release"][k])
        for v in model.get("plasma_transport", {}).get("membranes", []):
            want = b["plasma_transport"][v["membrane_id"]]
            pump((name, v["membrane_id"], "plasma pump"), v["pump"], want["pump"])
            for k in ("capacity_fmol_per_s", "km_na_mM", "km_ca_mM"):
                same((name, v["membrane_id"], "exchanger", k), v["exchanger"][k],
                     want["exchanger"][k])  # fmt: skip
        for v in model.get("calcium_channels", []):
            for k in ("membrane_id", "species_id", "max_permeability_m_per_s", "abundance",
                      "initial_gate"):  # fmt: skip
                same((name, v["id"], k), v[k], b["calcium_channels"][v["id"]][k])
        for v in model.get("ip3_release", []):
            for k in ("species_id", "activation_mM", "activation_n"):
                same((name, v["cell_id"], "ip3", k), v[k], b["ip3_release"][v["cell_id"]][k])
        for key in ("stores", "plasma_transport", "calcium_channels", "ip3_release"):
            same((name, "has", key), key in model, key in b)
        same((name, "end"), raw["experiment"]["end_time"], i["end_s"])
        same((name, "tolerance"), raw["execution"]["material_balance_atol_fmol"],
             i["material_tolerance_fmol"])  # fmt: skip
    print(f"definitions: {leaves} leaves of {len(m.WORLDS)} worlds against the parsed form: {ok}")
    return ok


def main(spec):
    results = dict(grid=grid(), ratios=ratios(), offsets=offsets(), fuel=fuel())
    print(results)
    rules2.check(spec / "inputs_part2.json")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["definitions"]:
        raise SystemExit(0 if definitions() else 1)
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else rules2.SPEC))
