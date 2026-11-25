"""Checks of the rehearsal's inputs that need no engine: `checks.py` runs them all.

- grid: every time of every world and every run's step against SPEC section 4's rule (2 eps t), the
horizons and the schedules that are exact, the one change one unit in the last place off, and the
one off-grid change;
- ratios: `inv_amounts` against the thresholds of SPEC section 8, and the fixed charges' residuals;
- offsets: the geometry factors of SPEC section 6 in every world with free field offsets;
- rules: the registered worlds' scales, amount_refs and closure terms (rules.py check);
- definitions: the block of every world against its legacy definition (the model's leaves).
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs  # noqa: E402
import rules  # noqa: E402

THRESHOLDS = {"n_cell": 4.3e4, "n_out": 6.3e4, "voltage": 2.5e4, "energy_identity": 4.7e4}


def ulps(t, h):
    """The distance of t from the nearest k h in units in the last place of t."""
    k = round(t / h)
    return round(abs(k * h - t) / math.ulp(t), 3)


def times_of(world):
    """{what: [times]} of a world: its horizon, schedules, compared times and restarts."""
    ionic = world["ionic"]
    out = {"end": [ionic["end_s"]]}
    for family in ("leak", "pump", "channel", "junction"):
        entry = ionic["controls"][family]
        if isinstance(entry, dict):
            for s in entry.values():
                out.setdefault(f"{family} schedule", []).extend(t for t, _ in s if t)
    out["potential"] = world.get("potential_times_s", [])
    out["summary"] = world.get("summary_times_s", [])
    if "history_times" in world:
        h = world["history_times"]
        n = round((h["last_s"] - h["first_s"]) / h["spacing_s"])
        out["spacing"] = [h["spacing_s"]]
        out["rows"] = [i * h["spacing_s"] for i in range(n + 1)]
    return out


def grid():
    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    steps = {}
    for r in inputs["runs"]:
        if r["step_s"] is not None:
            steps.setdefault(r["world"], set()).add(r["step_s"])
    bad = []
    off = {"inv_offgrid": [0.0041234]}
    for name, world in inputs["worlds"].items():
        legacy = make_inputs.WORLDS[name]["legacy"]
        grids = sorted(steps[name]) + [legacy / k for k in (1, 2, 4)]
        ones, exact = set(), 0
        for what, times in times_of(world).items():
            for t in times:
                for h in grids:
                    if what == "spacing":
                        ok = rules.on_grid(t, h)
                    else:
                        ok = rules.on_grid(t, h)
                    known = what.endswith("schedule") and t in off.get(name, [])
                    if known:
                        if ok:
                            bad.append((name, what, t, h, "on grid, but is the off-grid change"))
                        continue
                    if not ok:
                        bad.append((name, what, t, h, "off grid"))
                    if what != "rows" and t:
                        u = ulps(t, h)
                        if u:
                            ones.add((what, t, u))
                        else:
                            exact += 1
        counts = {h: rules.grid_steps(world["ionic"]["end_s"], h) for h in grids}
        print(
            f"{name}: steps {counts}; times one unit in the last place off k h: "
            f"{sorted(ones) or 'none'}"
        )
    for b in bad:
        print("  BAD", *b)
    return not bad


def ratios():
    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    w = inputs["worlds"]["inv_amounts"]
    ok = True
    for entry, limit in THRESHOLDS.items():
        names = (
            [entry] if entry in w["amount_refs"] else [f"{entry}_{x}" for x in ("Na", "K", "Cl")]
        )
        for k in names:
            r = w["amount_refs"][k] / w["scales"][k]
            ok &= r >= limit
            print(
                f"inv_amounts {k}: amount_refs/scales {r:.3g} (at least {limit:.3g}) "
                f"{'ok' if r >= limit else 'SHORT'}"
            )
    for group in ("cells", "outside"):
        for name, c in w["ionic"][group].items():
            res = rules.charge_residual_C(
                w["ionic"]["species"],
                c["initial_amount_fmol"],
                c["fixed_charge_equivalent_fmol"],
                c["initial_charge_C"],
            )
            ok &= 0 < abs(res) <= 5.1e-24
            print(
                f"inv_amounts {name}: rule less declared {res:.2e} C "
                f"(fixed {c['fixed_charge_equivalent_fmol']!r})"
            )
    return ok


def offsets():
    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    ok = True
    for name, w in inputs["worlds"].items():
        f = rules.field_factors(w["ionic"])
        if f is None:
            continue
        row, conductance, free = f
        fine = row <= 2.01 and conductance <= 0.53
        ok &= fine
        print(
            f"{name}: row factor {row:.4f} (at most 2.01), conductance ratio {conductance:.4f} "
            f"(at most 0.53), free {free}"
        )
    return ok


def definitions():
    """The block of every world against its legacy definition, leaf by leaf (parsed by nothing: both
    come from one source, so this checks the writing of the two forms)."""
    ok, leaves = True, 0

    def same(what, a, b):
        nonlocal ok, leaves
        leaves += 1
        if a != b:
            ok = False
            print("  DIFFER", what, a, b)

    inputs = json.loads((rules.HERE / "inputs_rehearsal.json").read_text())
    for name, world in make_inputs.WORLDS.items():
        b = inputs["worlds"][name]["ionic"]
        d = make_inputs.legacy(world, world["legacy"], observations=(0.0,))["model"]
        same((name, "temperature"), d["temperature_K"], b["temperature_K"])
        same((name, "species"), {s["id"]: s["valence"] for s in d["species"]}, b["species"])
        outside = {o["id"]: o for o in [d["extracellular"], *d.get("surroundings", [])]}
        same((name, "regions"), set(outside), set(b["outside"]))
        for o, v in outside.items():
            for k in ("volume_pL", "initial_amount_fmol", "fixed_charge_equivalent_fmol"):
                same((name, o, k), v[k], b["outside"][o][k])
        cells = {c["cell"]["id"]: c for c in d["cells"]}
        for c, v in cells.items():
            for k in (
                "volume_pL",
                "initial_amount_fmol",
                "fixed_charge_equivalent_fmol",
                "initial_voltage_V",
            ):
                same((name, c, k), v["cell"][k], b["cells"][c][k])
            m, mb = v["membrane"], b["membranes"][v["membrane"]["id"]]
            same((name, c, "area"), m["area_m2"], mb["area_m2"])
            same(
                (name, c, "capacitance"),
                m["area_m2"] * m["specific_capacitance_F_per_m2"],
                mb["capacitance_F"],
            )
            same(
                (name, c, "charge"),
                mb["capacitance_F"] * v["cell"]["initial_voltage_V"],
                b["cells"][c]["initial_charge_C"],
            )
            same(
                (name, c, "inside/outside"),
                (m["inside"], m["outside"]),
                (mb["inside"], mb["outside"]),
            )
            same(
                (name, c, "leak"),
                m["passive"]["permeability_m_per_s"],
                mb["passive"]["permeability_m_per_s"],
            )
            p, pb = m["pump"], mb["pump"]
            same((name, c, "pump present"), p is None, pb is None)
            if p is not None:
                for k in (
                    "capacity_fmol_per_s",
                    "km_na_mM",
                    "km_k_mM",
                    "km_atp_mM",
                    "roles",
                    "stoichiometry",
                ):
                    same((name, c, k), p[k], pb[k])
                for k in ("atp_mM", "adp_mM", "pi_mM", "delta_g0_J_per_mol"):
                    same((name, c, k), p["metabolism"][k], pb["metabolism"][k])
            if v["channel"] is not None:
                cb = b["channels"][v["channel"]["id"]]
                for k in (
                    "max_permeability_m_per_s",
                    "abundance",
                    "initial_gate",
                    "species_id",
                    "membrane_id",
                ):
                    same((name, c, k), v["channel"][k], cb[k])
        for j in d["junctions"]:
            jb = b["junctions"][j["id"]]
            for k in ("from_cell", "to_cell", "area_m2", "permeability_m_per_s"):
                same((name, j["id"], k), j[k], jb[k])
            for k in ("threshold_voltage_V", "minimum_open_fraction", "initial_gate"):
                same((name, j["id"], k), j["gate"][k], jb["gate"][k])
        for f in d.get("faces", []):
            fb = b["faces"][f["id"]]
            for k in ("sender", "receiver", "area_m2", "length_m", "diffusivity_m2_per_s"):
                same((name, f["id"], k), f[k], fb[k])
    print(f"definitions: {leaves} leaves of {len(make_inputs.WORLDS)} worlds compared")
    return ok


def main():
    results = dict(grid=grid(), ratios=ratios(), offsets=offsets(), definitions=definitions())
    print(results)
    rules.check()
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
