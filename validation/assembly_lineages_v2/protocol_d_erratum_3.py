"""OL6 Protocol D, erratum 3's arithmetic for M (docs/OL6_PROTOCOL_D_ERRATUM_3.md; D304).

The erratum is the authority; this module is its registered arithmetic, tagged with it. It adds no
number and no tolerance. It judges with limit_qualification's own registered functions, mean_error
and criterion_m, and changes only which pairs M's z is taken over.

**Exact agreement.** A pair (observable, time) is exact at a rung when (d)'s value there is finite
and every exact replica's value has its bits. The float64 words are compared as integers, so 0.0
and -0.0 differ, and a NaN (a replica or a (d) run ended before that time) is never exact. An
exact pair's error is exactly 0, and it is reported as "exact".

**M** (§5.2) at the top rung K against K - 1:
- a pair exact at K is excluded from M's z: e_K is 0, so the registered inequality holds whatever
  K - 1's terms are;
- every other pair, a pair exact at K - 1 only among them, keeps lq.mean_error's values at both
  rungs, so its excess is bitwise the registered one;
- the verdict is the registered criterion_m over those pairs.

Run with `PYTHONPATH=src:. JAX_ENABLE_X64=1`; `python -m validation.assembly_lineages_v2.
protocol_d_erratum_3 check` runs the erratum's synthetic checks and prints `information`
(made-up columns only).
"""

import json
import math
import sys

import numpy as np

from validation.assembly_lineages_v2 import limit_qualification as lq


def exact_pairs(exact, d):
    """{name: bool[T]}: True where (d)'s value (`d`, {name: [T]}) is finite and every replica of
    `exact` ({name: [M, T]}) has its bits."""
    out = {}
    for k in d:
        y_d = np.asarray(d[k], dtype=np.float64)
        y_a = np.asarray(exact[k], dtype=np.float64)
        same = np.all(y_a.view(np.uint64) == y_d.view(np.uint64)[None, :], axis=0)
        out[k] = same & np.isfinite(y_d)
    return out


def mean_error(exact, d):
    """(errors, exact_at): the errors as the erratum reports them, lq.mean_error's (e, SE) per
    observable with (0.0, 0.0) at the exact pairs, every other pair bitwise the registered value;
    and the exact pairs (exact_pairs). M does not read these errors (criterion_m)."""
    errors, exact_at = lq.mean_error(exact, d), exact_pairs(exact, d)
    out = {}
    for k, (e, se) in errors.items():
        e, se = np.array(e, dtype=np.float64), np.array(se, dtype=np.float64)
        e[exact_at[k]], se[exact_at[k]] = 0.0, 0.0
        out[k] = (e, se)
    return out, exact_at


def criterion_m(exact_top, d_top, exact_below, d_below):
    """M under the erratum, at the top rung K (exact_top, d_top) against K - 1 (exact_below,
    d_below), each as limit_qualification.observables gives them ({name: [M, T]} and {name: [T]}).

    The registered criterion_m over the pairs not exact at K, from lq.mean_error at both rungs.
    Returns its keys (largest_z, passes, fails) with `exact`, the excluded pairs as {name: [time
    index]}, and the counts of pairs judged and excluded. With no pair left, every top-rung error
    is 0: the registered function's largest_z is then -inf, and M passes."""
    top, below = lq.mean_error(exact_top, d_top), lq.mean_error(exact_below, d_below)
    exact_at = exact_pairs(exact_top, d_top)
    kept_top, kept_below, excluded = {}, {}, {}
    for k, (e_k, se_k) in top.items():
        keep = ~exact_at[k]
        if not keep.all():
            excluded[k] = [int(i) for i in np.flatnonzero(~keep)]
        if keep.any():  # np.nanmax refuses an empty column set
            e_b, se_b = below[k]
            kept_top[k] = (e_k[keep], se_k[keep])
            kept_below[k] = (e_b[keep], se_b[keep])
    verdict = lq.criterion_m(kept_top, kept_below)
    return {**verdict, "exact": excluded,
            "pairs_judged": sum(int(e.size) for e, _ in kept_top.values()),
            "pairs_exact": sum(len(v) for v in excluded.values())}  # fmt: skip


# ------------------------------------------------------------------ the synthetic checks (§4)

REPLICAS, TIMES = 128, 8


def _registered_z(exact_top, d_top, exact_below, d_below, columns=None):
    """The registered criterion_m's largest z, over every pair or over `columns` only."""
    top, below = lq.mean_error(exact_top, d_top), lq.mean_error(exact_below, d_below)
    if columns is not None:
        top = {k: (e[columns], s[columns]) for k, (e, s) in top.items()}
        below = {k: (e[columns], s[columns]) for k, (e, s) in below.items()}
    return lq.criterion_m(top, below)["largest_z"]


def _same(a, b):
    """Bitwise equality of two floats (two -inf are the same)."""
    return np.float64(a).view(np.uint64) == np.float64(b).view(np.uint64)


def _rung(rng, value, spread, columns_exact=()):
    """One synthetic rung of one observable: (d)'s values, and REPLICAS replicas around them with a
    relative spread, bitwise (d)'s at columns_exact."""
    d = value * (1.0 + 0.1 * np.arange(TIMES))
    replicas = d[None, :] * (1.0 + spread * rng.standard_normal((REPLICAS, TIMES)))
    replicas[:, list(columns_exact)] = d[list(columns_exact)]
    return replicas, d


def one(a, d):
    """One observable's (replicas, (d)) pair of dicts, named V."""
    return {"V": a}, {"V": d}


def check():
    """The erratum's synthetic checks on made-up columns (none of the protocol's runs): a dict of
    named results, each with `ok`."""
    rng = np.random.default_rng(3)
    out = {}
    first = (0, 1, 2)
    a_top, d_top = _rung(rng, 0.7316, 1e-3, first)
    a_below, d_below = _rung(rng, 0.6113, 2e-3, first)

    # (i) bitwise-equal columns at both rungs: excluded, the rest judged as registered
    m = criterion_m(*one(a_top, d_top), *one(a_below, d_below))
    registered_all = _registered_z(*one(a_top, d_top), *one(a_below, d_below))
    registered_kept = _registered_z(*one(a_top, d_top), *one(a_below, d_below),
                                    columns=slice(3, None))
    out["(i) a bitwise-equal column is excluded"] = {
        "exact": m["exact"], "z": m["largest_z"], "z_registered_over_every_pair": registered_all,
        "ok": m["exact"] == {"V": list(first)} and _same(m["largest_z"], registered_kept)
        and m["largest_z"] <= registered_all}  # fmt: skip

    # (ii) one replica 1 ulp from (d) at the top rung: not exact, computed as registered
    a = np.tile(d_top, (REPLICAS, 1))
    a[0, 0] = np.nextafter(d_top[0], np.inf)
    b = np.tile(d_below, (REPLICAS, 1))
    m = criterion_m({"V": a[:, :1]}, {"V": d_top[:1]}, {"V": b[:, :1]}, {"V": d_below[:1]})
    z = _registered_z({"V": a[:, :1]}, {"V": d_top[:1]}, {"V": b[:, :1]}, {"V": d_below[:1]})
    out["(ii) one replica 1 ulp off is computed as registered"] = {
        "exact": m["exact"], "z": m["largest_z"], "z_registered": z, "passes": m["passes"],
        "ok": m["exact"] == {} and _same(m["largest_z"], z)}  # fmt: skip

    # (iii) genuinely different columns: unchanged
    g_top, gd_top = _rung(rng, 0.7316, 1e-3)
    g_below, gd_below = _rung(rng, 0.6113, 2e-3)
    m = criterion_m(*one(g_top, gd_top), *one(g_below, gd_below))
    z = _registered_z(*one(g_top, gd_top), *one(g_below, gd_below))
    out["(iii) a genuinely different column is unchanged"] = {
        "exact": m["exact"], "z": m["largest_z"], "z_registered": z,
        "ok": m["exact"] == {} and _same(m["largest_z"], z)}  # fmt: skip

    # (iv) exact at K - 1 only: computed as registered (the lower rung's residue kept)
    m = criterion_m(*one(g_top, gd_top), *one(a_below, d_below))
    z = _registered_z(*one(g_top, gd_top), *one(a_below, d_below))
    out["(iv) a pair exact at K - 1 only is computed as registered"] = {
        "exact": m["exact"], "z": m["largest_z"], "z_registered": z,
        "ok": m["exact"] == {} and _same(m["largest_z"], z)}  # fmt: skip

    # (v) a NaN replica, and a NaN (d) value: never exact
    a = np.tile(d_top, (REPLICAS, 1))
    a[5, 1] = np.nan
    d_nan = d_top.copy()
    d_nan[2] = np.nan
    nan_d = np.tile(d_nan, (REPLICAS, 1))
    got = exact_pairs({"V": a, "W": nan_d}, {"V": d_top, "W": d_nan})
    out["(v) a NaN never makes a pair exact"] = {
        "exact_V": np.flatnonzero(got["V"]).tolist(), "exact_W": np.flatnonzero(got["W"]).tolist(),
        "ok": not got["V"][1] and not got["W"][2] and got["V"][0] and got["W"][0]}  # fmt: skip

    # (vi) every replica the same, (d) alone 1 ulp off either way: not exact, computed as
    # registered (upward, the offset cancels the mean's rounding residue here: e = 0, SE > 0)
    a = np.tile(d_top, (REPLICAS, 1))
    result = {}
    for name, step in (("up", np.inf), ("down", -np.inf)):
        d_off = d_top.copy()
        d_off[0] = np.nextafter(d_top[0], step)
        m = criterion_m({"V": a[:, :1]}, {"V": d_off[:1]}, {"V": b[:, :1]}, {"V": d_below[:1]})
        z = _registered_z({"V": a[:, :1]}, {"V": d_off[:1]}, {"V": b[:, :1]}, {"V": d_below[:1]})
        result[name] = {"exact": m["exact"], "z": m["largest_z"], "z_registered": z,
                        "passes": m["passes"],
                        "ok": m["exact"] == {} and _same(m["largest_z"], z)}  # fmt: skip
    out["(vi) (d) alone 1 ulp off is computed as registered"] = {
        **result, "ok": all(r["ok"] for r in result.values())}

    # (vii) +0.0 against -0.0: not exact (bits)
    got = exact_pairs({"S": np.zeros((REPLICAS, 1))}, {"S": np.array([-0.0])})
    out["(vii) 0.0 against -0.0 is not exact"] = {"ok": not got["S"][0]}

    # (viii) every pair exact at K: nothing judged, largest z -inf, M passes
    m = criterion_m({"V": np.tile(d_top, (REPLICAS, 1))}, {"V": d_top}, *one(g_below, gd_below))
    out["(viii) every pair exact at K"] = {
        "pairs_judged": m["pairs_judged"], "pairs_exact": m["pairs_exact"],
        "z": m["largest_z"], "passes": m["passes"],
        "ok": m["pairs_judged"] == 0 and m["pairs_exact"] == TIMES and m["largest_z"] == -math.inf
        and m["passes"]}  # fmt: skip

    # (ix) the reported errors: (0, 0) at the exact pairs, bitwise registered elsewhere; and an
    # exact count (integers), where the registered mean_error is already exactly (0, 0), so B is
    # untouched
    errors, at = mean_error(*one(a_top, d_top))
    (e_reg, se_reg) = lq.mean_error(*one(a_top, d_top))["V"]
    counts = np.tile(np.array([97.0, 1200.0, 64000.0, 3.0]), (REPLICAS, 1))
    (e_c, se_c) = lq.mean_error({"N@pool": counts}, {"N@pool": counts[0]})["N@pool"]
    e, se = errors["V"]
    out["(ix) the reported errors, and an exact count"] = {
        "registered_residue_at_exact": [float(x) for x in e_reg[list(first)]],
        "ok": bool(np.all(e[list(first)] == 0.0) and np.all(se[list(first)] == 0.0)
                   and np.array_equal(e[3:].view(np.uint64), e_reg[3:].view(np.uint64))
                   and np.array_equal(se[3:].view(np.uint64), se_reg[3:].view(np.uint64))
                   and np.all(e_c == 0.0) and np.all(se_c == 0.0)
                   and at["V"].tolist() == [True] * 3 + [False] * 5)}  # fmt: skip
    return out


def _spread(zs):
    zs = np.asarray(zs)
    return {"z_min": float(zs.min()), "z_median": float(np.median(zs)), "z_max": float(zs.max()),
            "beyond_4.5": int(np.sum(zs > lq.Z_STAR)), "beyond_6": int(np.sum(zs > lq.Z_FAIL))}


def information():
    """What the registered arithmetic gives at pairs the erratum leaves as registered (made-up
    values; the erratum's §4, disclosed and not changed), each with the lower rung bitwise exact,
    over 200 values from 0.1 to 10: one replica 1 ulp from (d); (d) alone 1 ulp off, up and down.
    And replicas all equal at both rungs with (d) off, where the combined SE is 0; and how often a
    constant column of made-up non-integer values has SE exactly 0 by rounding alone."""
    values = np.linspace(0.1, 10.0, 200)

    def z_at(top_replicas, d_top, v):
        w = 0.83 * v
        return _registered_z({"V": top_replicas}, {"V": np.array([d_top])},
                             {"V": np.full((REPLICAS, 1), w)}, {"V": np.array([w])})

    one_off = []
    for v in values:
        a = np.full((REPLICAS, 1), v)
        a[0, 0] = np.nextafter(v, np.inf)
        one_off.append(z_at(a, v, v))
    out = {"one replica 1 ulp off": _spread(one_off)}
    for name, step in (("up", np.inf), ("down", -np.inf)):
        out[f"(d) alone 1 ulp {name}"] = _spread(
            [z_at(np.full((REPLICAS, 1), v), np.nextafter(v, step), v) for v in values])
    flat = {"V": np.full((REPLICAS, 1), 1.0)}
    out["replicas all 1.0 at both rungs, (d) 2.0"] = {
        "z": _registered_z(flat, {"V": np.array([2.0])}, flat, {"V": np.array([2.0])})}
    # how often a constant column's sum leaves no residue (SE exactly 0) by rounding alone, in the
    # observables' [M, 8] layout, on made-up values from 1e-25 to 1e2
    zero_se = {}
    for m in (128, 256):
        made_up = 10.0 ** np.random.default_rng(23).uniform(-25.0, 2.0, size=(500, TIMES))
        count = 0
        for row in made_up:
            _, se = lq.mean_error({"V": np.tile(row, (m, 1))}, {"V": row})["V"]
            count += int(np.sum(se == 0.0))
        zero_se[f"M = {m}"] = {"constant_columns": int(made_up.size), "se_exactly_0": count}
    out["constant columns, made-up values 1e-25 to 1e2, SE exactly 0"] = zero_se
    return out


def _printable(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _printable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_printable(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        raise SystemExit("usage: python -m validation.assembly_lineages_v2.protocol_d_erratum_3 "
                         "check")
    results = check()
    print(json.dumps(_printable({"checks": results, "information": information()}), indent=1))
    raise SystemExit(0 if all(r["ok"] for r in results.values()) else 1)
