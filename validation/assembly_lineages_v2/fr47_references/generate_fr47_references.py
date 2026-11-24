"""Generate FR-47's reference files, their accuracy check and C8's resolution table.

    taskset -c 6 python generate_fr47_references.py [--out DIR] [--allow-dirty]

Writes, into ``references/`` (or ``--out``):
- ``reference_<world>.json`` for the registered worlds (W1, W1D, W2_Ng64/256/1024/4096) and the
  invented worlds (``invented_shell``, ``invented_gate``) that the judge reads first;
- ``accuracy.json``:
  - method 1 (the written values) against method 2 (independent float64 numerics), in CRITERIA's
    normalisation;
  - method 1 re-evaluated at a higher precision, which must give the same floats;
  - the identities' closure on the written floats, in ulps;
- ``c8_resolution.json``: per rung, C8's largest pair over the tracer observables (CRITERIA C8 as
  amended, AMENDMENT-2026-11-24 section 1), its resolution at M = 128 and the replicas a
  resolution of 4.5 would take, with the slope's linearised standard error. C8 is reported, not
  claimed; the checker fits the slope from the gap lists, since the references fit nothing.

BLAS is pinned to one thread before numpy loads. Every output is deterministic: no timestamps,
host names, paths or process seeds are written.
"""

from __future__ import annotations

import os

for _var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[_var] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fr47_exact  # noqa: E402
import fr47_writer  # noqa: E402


def _world_names():
    """Every input world, in sorted order: the registered ones, then the invented ones (whose
    names start with ``invented_``). A resized W2 is a data edit in ``inputs/``."""
    names = sorted(f[:-5] for f in os.listdir(os.path.join(HERE, "inputs")) if f.endswith(".json"))
    return (
        [n for n in names if not n.startswith("invented_")],
        [n for n in names if n.startswith("invented_")],
    )


REGISTERED, INVENTED = _world_names()
CHECK_PREC = 100
M = fr47_exact.M_REPLICAS
RESOLUTION_FLOOR = 4.5


def _load(name):
    with open(os.path.join(HERE, "inputs", f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _blas_threads():
    try:
        from threadpoolctl import threadpool_info
    except ImportError:
        return None
    import numpy  # noqa: F401

    return sorted({info["num_threads"] for info in threadpool_info()})


# --------------------------------------------------------------------------------------------
# Accuracy: method 1 (the file) against method 2, in CRITERIA's normalisation
# --------------------------------------------------------------------------------------------


def _spread_v(var, mu4):
    return mu4 - var * var * (M - 3) / (M - 1)


class Worst:
    """The largest value of a figure and where it is."""

    def __init__(self):
        self.items = {}

    def add(self, figure, value, where):
        value = float(value)  # numpy scalars become plain floats for the JSON file
        cur = self.items.get(figure)
        if cur is None or value > cur[0]:
            self.items[figure] = (value, where)

    def merge(self, other, world):
        for figure, (value, where) in other.items.items():
            self.add(figure, value, f"{world}: {where}")

    def as_dict(self):
        return {k: {"value": v, "at": w} for k, (v, w) in self.items.items()}


def _moment_figures(worst, prefix, ref, num, where):
    mean, var, mu4 = ref["mean"], ref["var"], ref["mu4"]
    m2, v2, q2 = num
    vv = _spread_v(var, mu4)
    worst.add(f"{prefix}.mean_z", abs(m2 - mean) / math.sqrt(var / M), where)
    worst.add(f"{prefix}.var_spread_z", abs(v2 - var) / math.sqrt(vv / M), where)
    worst.add(f"{prefix}.mu4_spread_z_relative", abs(q2 - mu4) / (2 * vv), where)
    worst.add(f"{prefix}.mean_relative", abs(m2 - mean) / abs(mean), where)
    worst.add(f"{prefix}.var_relative", abs(v2 - var) / var, where)
    worst.add(f"{prefix}.mu4_relative", abs(q2 - mu4) / mu4, where)


def _scale_pairs(doc):
    """CRITERIA's s_y for a pair: its observable's largest |reference mean| over the founder and
    the times (the d values are the reference's mean trajectory)."""
    founder = doc["world"]["founder_molecules"]
    scale = {}
    for e in doc["d"]["pairs"]:
        obs = e["observable"]
        scale[obs] = max(scale.get(obs, abs(founder[obs])), abs(e["value"]))
    return scale


def accuracy_world(name, doc, raw):
    import fr47_numeric

    num = fr47_numeric.numeric(raw)
    worst = Worst()
    flags = {}
    for e in doc["pairs"]:
        key = (e["observable"], e["time_s"])
        where = f"{e['observable']} at {e['time_s']} s"
        if e["class"] == "constant":
            founder = raw["founder_molecules"][e["observable"]]
            flags["constants_equal_founder"] = bool(
                flags.get("constants_equal_founder", True) and e["value"] == founder
            )
            continue
        _moment_figures(worst, "pairs", e, num["pairs"][key], where)
    scale = _scale_pairs(doc)
    for e in doc["d"]["pairs"]:
        key = (e["observable"], e["time_s"])
        if key not in num["d_pairs"]:
            continue
        worst.add(
            "d.pairs.bounds",
            abs(num["d_pairs"][key] - e["value"]) / (1e-5 * scale[e["observable"]]),
            f"{e['observable']} at {e['time_s']} s",
        )
    if raw["type"] == "shell_washes":
        rem_scale = max(abs(s["removed"]) for s in doc["d"]["stops"])
        heat_scale = max(
            abs(s["mixing_heat"]) for s in doc["d"]["stops"] if s["mixing_heat"] is not None
        )
        for s, ds in zip(doc["stops"], doc["d"]["stops"], strict=True):
            t = s["time_s"]
            n_rem, n_heat = num["stops"][t]
            _moment_figures(worst, "stops.removed", s["removed"], n_rem, f"removed at {t} s")
            if s["mixing_heat"] is not None:
                _moment_figures(
                    worst, "stops.mixing_heat", s["mixing_heat"], n_heat, f"mixing heat at {t} s"
                )
            d_rem, d_heat = num["d_stops"][t]
            worst.add(
                "d.stops.removed_bounds",
                abs(d_rem - ds["removed"]) / (1e-5 * rem_scale),
                f"removed at {t} s",
            )
            if ds["mixing_heat"] is not None:
                worst.add(
                    "d.stops.mixing_heat_bounds",
                    abs(d_heat - ds["mixing_heat"]) / (1e-5 * heat_scale),
                    f"mixing heat at {t} s",
                )
        heat_scale = max(abs(i["heat"]) for i in doc["d"]["intervals"])
        for i, (_t0, _t1, q) in zip(doc["d"]["intervals"], num["intervals"], strict=True):
            worst.add(
                "d.intervals.bounds",
                abs(q - i["heat"]) / (1e-5 * heat_scale),
                f"interval {i['start_s']}-{i['end_s']} s",
            )
    else:
        sd = {
            (e["observable"], e["time_s"]): math.sqrt(e["var"])
            for e in doc["pairs"]
            if e["class"] == "spread"
        }
        for g in doc["gap"]:
            key = (g["observable"], g["time_s"])
            ng, nres = num["gap"][key]
            where = f"{g['observable']} at {g['time_s']} s"
            worst.add("gap.z", abs(ng - g["gap"]) / (sd[key] / math.sqrt(M)), where)
            worst.add("gap.resolution_absolute", abs(nres - g["resolution"]), where)
        worst.add(
            "hierarchy.mass_minus_one", max(abs(v - 1.0) for v in num["mass"].values()), "all times"
        )
        worst.add("hierarchy.cut_edge_mass", max(num["edge_mass"].values()), "all times")
        flags["hierarchy_window"] = {
            "k_lo": num["window"][0],
            "k_hi": num["window"][1],
            "N_g": num["Ng"],
        }
        mine = c8_pair(doc)
        flags["c8_same_largest_pair"] = num["c8"] == (mine["observable"], mine["time_s"])
    for p in doc["plants"]:
        cands = num["plants"][(p["plant"], p["criterion"])]
        if "time_s" in p:
            key = (p["observable"], p["time_s"])
        else:
            key = (p["observable"], p["start_s"], p["end_s"])
        honest, planted, unit = cands[key]
        dist = abs(planted - honest) / unit
        # method 2, by its own naming rule (AMENDMENT-2026-11-24 section 2), names the same quantity
        flags["plants_same_quantity"] = bool(
            flags.get("plants_same_quantity", True) and fr47_numeric.largest(cands) == key
        )
        tag = f"{p['plant']}/{p['criterion']} {key}"
        worst.add("plants.planted_in_bounds", abs(planted - p["planted"]) / unit, tag)
        worst.add("plants.honest_in_bounds", abs(honest - p["honest"]) / unit, tag)
        worst.add(
            "plants.distance_relative",
            abs(dist - p["distance_in_bounds"]) / p["distance_in_bounds"],
            tag,
        )
    return worst, flags


# --------------------------------------------------------------------------------------------
# Identities on the written floats, in ulps
# --------------------------------------------------------------------------------------------


def _ulps(x, target):
    return abs(x - target) / math.ulp(target) if target != 0 else abs(x) / math.ulp(1.0)


def identities_world(doc):
    out = {}
    raw = doc["world"]
    if raw["type"] == "shell_washes":
        total = raw["founder_molecules"]["S@pool"] + raw["founder_molecules"]["S@lumen"]
        mean = {
            (e["observable"], e["time_s"]): (e["value"] if e["class"] == "constant" else e["mean"])
            for e in doc["pairs"]
        }
        dval = {(e["observable"], e["time_s"]): e["value"] for e in doc["d"]["pairs"]}
        times = sorted({e["time_s"] for e in doc["pairs"]})
        worst_exact = worst_d = 0.0
        for t in times:
            removed = [
                s["removed"]["mean"] if s["removed"]["class"] == "spread" else s["removed"]["value"]
                for s in doc["stops"]
                if s["time_s"] < t
            ]
            d_removed = [s["removed"] for s in doc["d"]["stops"] if s["time_s"] < t]
            worst_exact = max(
                worst_exact,
                _ulps(math.fsum([mean[("S@pool", t)], mean[("S@lumen", t)]] + removed), total),
            )
            worst_d = max(
                worst_d,
                _ulps(math.fsum([dval[("S@pool", t)], dval[("S@lumen", t)]] + d_removed), total),
            )
        out["moiety_present_plus_removed_ulps_of_founder"] = worst_exact
        out["d_moiety_present_plus_removed_ulps_of_founder"] = worst_d
        out["d_pairs_equal_exact_means_bitwise"] = all(dval[k] == mean[k] for k in dval)
        out["d_stops_equal_exact_means_bitwise"] = all(
            ds["removed"] == s["removed"].get("mean", s["removed"].get("value"))
            and (ds["mixing_heat"] is None or ds["mixing_heat"] == s["mixing_heat"].get("mean"))
            for s, ds in zip(doc["stops"], doc["d"]["stops"], strict=True)
        )
    else:
        founder = raw["founder_molecules"]
        n_tr = founder["S@pool"] + founder["S@lumen"]
        n_g = founder["G@wall"] + founder["H@wall"]
        pairs = {(e["observable"], e["time_s"]): e for e in doc["pairs"]}
        dval = {(e["observable"], e["time_s"]): e["value"] for e in doc["d"]["pairs"]}
        gap = {(g["observable"], g["time_s"]): g for g in doc["gap"]}
        times = sorted({e["time_s"] for e in doc["pairs"]})
        acc = {
            k: 0.0
            for k in (
                "pool_plus_lumen_mean_ulps",
                "G_plus_H_mean_ulps",
                "var_pool_vs_lumen_ulps",
                "mu4_pool_vs_lumen_ulps",
                "var_G_vs_H_ulps",
                "mu4_G_vs_H_ulps",
                "d_pool_plus_lumen_ulps",
                "d_G_plus_H_ulps",
                "gap_pool_plus_lumen_ulps",
                "resolution_pool_vs_lumen_ulps",
            )
        }
        for t in times:
            p, lum = pairs[("S@pool", t)], pairs[("S@lumen", t)]
            g, h = pairs[("G@wall", t)], pairs[("H@wall", t)]
            acc["pool_plus_lumen_mean_ulps"] = max(
                acc["pool_plus_lumen_mean_ulps"], _ulps(math.fsum([p["mean"], lum["mean"]]), n_tr)
            )
            acc["G_plus_H_mean_ulps"] = max(
                acc["G_plus_H_mean_ulps"], _ulps(math.fsum([g["mean"], h["mean"]]), n_g)
            )
            acc["var_pool_vs_lumen_ulps"] = max(
                acc["var_pool_vs_lumen_ulps"], _ulps(p["var"], lum["var"])
            )
            acc["mu4_pool_vs_lumen_ulps"] = max(
                acc["mu4_pool_vs_lumen_ulps"], _ulps(p["mu4"], lum["mu4"])
            )
            acc["var_G_vs_H_ulps"] = max(acc["var_G_vs_H_ulps"], _ulps(g["var"], h["var"]))
            acc["mu4_G_vs_H_ulps"] = max(acc["mu4_G_vs_H_ulps"], _ulps(g["mu4"], h["mu4"]))
            acc["d_pool_plus_lumen_ulps"] = max(
                acc["d_pool_plus_lumen_ulps"],
                _ulps(math.fsum([dval[("S@pool", t)], dval[("S@lumen", t)]]), n_tr),
            )
            acc["d_G_plus_H_ulps"] = max(
                acc["d_G_plus_H_ulps"],
                _ulps(math.fsum([dval[("G@wall", t)], dval[("H@wall", t)]]), n_g),
            )
            gp, gl = gap[("S@pool", t)], gap[("S@lumen", t)]
            acc["gap_pool_plus_lumen_ulps"] = max(
                acc["gap_pool_plus_lumen_ulps"], _ulps(-gp["gap"], gl["gap"])
            )
            acc["resolution_pool_vs_lumen_ulps"] = max(
                acc["resolution_pool_vs_lumen_ulps"], _ulps(gp["resolution"], gl["resolution"])
            )
        out.update(acc)
    return out


# --------------------------------------------------------------------------------------------
# C8's resolution table
# --------------------------------------------------------------------------------------------


def c8_pair(doc):
    """C8's largest pair on the written floats: the largest |gap| over S@pool and S@lumen at the
    observation times, a tie going to S@pool, then to the earliest time (CRITERIA C8 as amended,
    AMENDMENT-2026-11-24 section 1)."""
    best = None
    for g in doc["gap"]:  # ordered S@pool, S@lumen, G@wall, H@wall, then by time
        if g["observable"] not in fr47_exact.C8_OBSERVABLES:
            continue
        if best is None or abs(g["gap"]) > abs(best["gap"]):
            best = g
    return best


def c8_table(docs):
    rows = []
    gated = [n for n in REGISTERED if docs[n]["world"]["type"] == "gated_shell"]
    gated.sort(
        key=lambda n: (
            docs[n]["world"]["founder_molecules"]["G@wall"]
            + docs[n]["world"]["founder_molecules"]["H@wall"]
        )
    )
    for name in gated:
        doc = docs[name]
        founder = doc["world"]["founder_molecules"]
        sd = {
            (e["observable"], e["time_s"]): math.sqrt(e["var"])
            for e in doc["pairs"]
            if e["class"] == "spread"
        }
        largest = c8_pair(doc)
        rows.append(
            {
                "world": name,
                "N_g": founder["G@wall"] + founder["H@wall"],
                "N_w": founder["B@wall"] + founder["G@wall"] + founder["H@wall"],
                "largest_pair": {
                    "observable": largest["observable"],
                    "time_s": largest["time_s"],
                    "gap": largest["gap"],
                    "sd": sd[(largest["observable"], largest["time_s"])],
                    "resolution": largest["resolution"],
                    # sizing only: the replicas at which this pair's resolution would be 4.5
                    "replicas_for_resolution_4.5": M
                    * (RESOLUTION_FLOOR / largest["resolution"]) ** 2,
                },
            }
        )
    xs = [math.log(r["N_g"]) for r in rows]
    se = None
    if len(rows) >= 2:
        xbar = sum(xs) / len(xs)
        sxx = sum((x - xbar) ** 2 for x in xs)
        se = (
            math.sqrt(
                sum(
                    (x - xbar) ** 2 / r["largest_pair"]["resolution"] ** 2
                    for x, r in zip(xs, rows, strict=True)
                )
            )
            / sxx
        )
    return {
        "rule": "CRITERIA C8 as amended (AMENDMENT-2026-11-24 section 1): reported from the "
        "reference alone, not claimed. Each rung's gap is taken at its largest pair, the largest "
        "|gap| over S@pool and S@lumen at the observation times (ties to S@pool, then the earliest "
        "time); resolution = |gap| / (SD / sqrt(128)). The slope on ln|gap| against ln N_g is "
        "fitted from the reference files' gap lists by the checker: the references fit nothing "
        "(SPEC.md section 4)",
        "M": M,
        "rungs": rows,
        "slope_se_linearised_all_rungs": se,
        "slope_se_note": "the standard error of a least-squares slope of ln|gap| on ln N_g over "
        "all rungs if each rung's ln|gap| were measured with SD 1/resolution "
        "(linearised; meaningless where a resolution is below about 3)",
    }


# --------------------------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(HERE, "references"))
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--skip-numeric", action="store_true", help="skip method 2 (development only)")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    prov = fr47_writer.provenance(allow_dirty=args.allow_dirty)
    threads = _blas_threads()
    if threads not in (None, [1]):
        raise SystemExit(f"BLAS is not pinned to one thread: {threads}")
    docs, raws = {}, {}
    precision = {"prec": fr47_exact.DEFAULT_PREC, "check_prec": CHECK_PREC, "files": {}}
    for name in REGISTERED + INVENTED:
        raw = _load(name)
        doc = fr47_writer.build_document(raw, prov)
        data = fr47_writer.dumps(doc)
        with open(os.path.join(args.out, f"reference_{name}.json"), "wb") as fh:
            fh.write(data)
        check = fr47_writer.dumps(fr47_writer.build_document(raw, prov, prec=CHECK_PREC))
        precision["files"][name] = check == data
        docs[name], raws[name] = doc, raw
        print(
            f"wrote reference_{name}.json ({len(data)} bytes); "
            f"{CHECK_PREC}-digit floats identical: {check == data}",
            flush=True,
        )
    precision["all_identical"] = all(precision["files"].values())
    accuracy = {
        "provenance": prov,
        "method_1": "closed forms in decimal arithmetic at 60 digits (fr47_exact.py): "
        "the written values",
        "method_2": "independent float64 numerics (fr47_numeric.py): expm and pmf enumeration, "
        "DOP853 for the rate equations, and Radau on the moment hierarchy over every gate state",
        "normalisation": {
            "mean_z": "|m2 - m1| / sqrt(var / 128): CRITERIA's mean z per unit difference",
            "var_spread_z": "|v2 - v1| / sqrt((mu4 - var^2 (M-3)/(M-1)) / 128): the spread z",
            "mu4_spread_z_relative": "|q2 - q1| / (2 (mu4 - var^2 (M-3)/(M-1))): the spread z's "
            "relative change, so |dz| = |z| times this",
            "bounds": "|y2 - y1| / (1e-5 s_y): C1's bound, with CRITERIA's scales",
            "gap.z": "|gap2 - gap1| / (SD / sqrt(128))",
            "plants": "planted and honest in the criterion's own bound; distance relative",
        },
        "precision_check": precision,
        "worlds": {},
        "identities": {},
    }
    overall = Worst()
    if not args.skip_numeric:
        import time

        for name in REGISTERED + INVENTED:
            started = time.monotonic()
            worst, flags = accuracy_world(name, docs[name], raws[name])
            accuracy["worlds"][name] = {"largest": worst.as_dict(), "flags": flags}
            overall.merge(worst, name)
            # console only: elapsed times are never written into a file
            print(f"method 2 on {name}: done in {time.monotonic() - started:.1f} s", flush=True)
    accuracy["largest_over_worlds"] = overall.as_dict()
    for name in REGISTERED + INVENTED:
        accuracy["identities"][name] = identities_world(docs[name])
    with open(os.path.join(args.out, "accuracy.json"), "wb") as fh:
        fh.write(fr47_writer.dumps(accuracy))
    table = c8_table(docs)
    table["provenance"] = prov
    with open(os.path.join(args.out, "c8_resolution.json"), "wb") as fh:
        fh.write(fr47_writer.dumps(table))
    print("wrote accuracy.json and c8_resolution.json", flush=True)


if __name__ == "__main__":
    main()
