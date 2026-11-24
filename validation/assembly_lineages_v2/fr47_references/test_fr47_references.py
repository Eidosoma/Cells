"""FR-47 references' self-check: no engine import, a few seconds.

    python test_fr47_references.py        (or: python -m pytest test_fr47_references.py)

1. **Tiny worlds, the full joint master equation.** Each is built straight from SPEC.md section
   1's per-event propensities and propagated by matrix exponentials:
   - a shell world with a nonzero lumen founder, a lumen potential and all three stop kinds;
   - a gated world with unequal G and H.

   Method 1 (closed forms) and method 2 (the moment hierarchy) must match its moments. This tests
   the reading of the spec, not only the algebra.
2. **The writer on invented inputs.** It writes both world types' files. The test checks their
   structure, classes, units and float round-trip, their bytes against a second write, and their
   floats against a higher precision. Where the package is a clean commit, the committed invented
   files must equal what it writes.
"""

from __future__ import annotations

import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402

import numpy as np  # noqa: E402
import scipy.linalg  # noqa: E402
import scipy.stats  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fr47_exact  # noqa: E402
import fr47_numeric  # noqa: E402
import fr47_writer  # noqa: E402

TINY_SHELL = {
    "name": "tiny_shell",
    "type": "shell_washes",
    "spec": "self-check",
    "V_out_L": "1e-18",
    "V_in_L": "2e-19",
    "A_sh_m2": "2e-15",
    "P_s_m_per_s": "1e-7",
    "tracer_potentials_kBT": {"solution": "0.2", "lumen": "0.2 + ln(3)"},
    "founder_molecules": {"S@pool": 3, "S@lumen": 2, "B@wall": 5},
    "stops": [
        {"time_s": "0.7", "kind": "withdrawal", "f": "3/8"},
        {"time_s": "1.3", "kind": "replacement"},
        {"time_s": "2.2", "kind": "withdrawal", "f": "1/2"},
    ],
    "observation_times_s": ["0.4", "1.0", "1.9", "2.9"],
    "horizon_s": "3.0",
    "plants": [],
}

TINY_GATE = {
    "name": "tiny_gate",
    "type": "gated_shell",
    "spec": "self-check",
    "V_out_L": "1e-18",
    "V_in_L": "2e-19",
    "A_sh_m2": "2e-15",
    "P_s_m_per_s": "1e-7",
    "tracer_potentials_kBT": {"solution": "0.1", "lumen": "-0.2"},
    "gate": {
        "open_form": "G",
        "closed_form": "H",
        "a_open_kBT": "1.2",
        "b_closed_kBT": "-0.7",
        "mu0_G_kBT": "-0.4",
        "mu0_H_kBT": "-1.1",
        "k_GH_per_s": "1.7",
    },
    "founder_molecules": {"S@pool": 3, "S@lumen": 1, "B@wall": 7, "G@wall": 2, "H@wall": 1},
    "observation_times_s": ["0.3", "1.1", "2.5"],
    "horizon_s": "2.5",
    "plants": [],
}


def _f(x):
    return float(fr47_numeric.num(x))


def _moments(pmf):
    k = np.arange(pmf.size, dtype=float)
    mean = float(np.dot(k, pmf))
    dev = k - mean
    return mean, float(np.dot(dev**2, pmf)), float(np.dot(dev**4, pmf))


def shell_master_equation(raw):
    """Moments of S@pool, S@lumen, each stop's removed count and kept count, from the joint law of
    (n_pool, n_lumen), with SPEC.md section 1's propensities: kappa_in per pool molecule, kappa_out
    per lumen molecule; a withdrawal removes each pool molecule with probability f."""
    pa = _f(raw["P_s_m_per_s"]) * _f(raw["A_sh_m2"])
    k_in = pa / (_f(raw["V_out_L"]) * 1e-3)
    pots = raw["tracer_potentials_kBT"]
    delta = _f(pots["lumen"]) - _f(pots["solution"])
    k_out = pa * math.exp(delta) / (_f(raw["V_in_L"]) * 1e-3)
    n_tot = raw["founder_molecules"]["S@pool"] + raw["founder_molecules"]["S@lumen"]
    states = [(a, b) for a in range(n_tot + 1) for b in range(n_tot + 1 - a)]
    index = {s: i for i, s in enumerate(states)}
    gen = np.zeros((len(states), len(states)))
    for (a, b), i in index.items():
        if a > 0:  # a pool molecule enters the lumen
            gen[i, index[(a - 1, b + 1)]] += k_in * a
            gen[i, i] -= k_in * a
        if b > 0:  # a lumen molecule leaves
            gen[i, index[(a + 1, b - 1)]] += k_out * b
            gen[i, i] -= k_out * b
    prob = np.zeros(len(states))
    prob[index[(raw["founder_molecules"]["S@pool"], raw["founder_molecules"]["S@lumen"])]] = 1.0
    events = [(_f(t), "obs", None) for t in raw["observation_times_s"]]
    events += [(_f(s["time_s"]), s["kind"], _f(s.get("f", "1/1"))) for s in raw["stops"]]
    events.sort(key=lambda e: e[0])
    t_prev, out = 0.0, {"pairs": {}, "stops": {}}
    for t, kind, f in events:
        prob = prob @ scipy.linalg.expm(gen * (t - t_prev))
        t_prev = t
        if kind == "obs":
            pool = np.zeros(n_tot + 1)
            lumen = np.zeros(n_tot + 1)
            for (a, b), i in index.items():
                pool[a] += prob[i]
                lumen[b] += prob[i]
            out["pairs"][("S@pool", t)] = _moments(pool)
            out["pairs"][("S@lumen", t)] = _moments(lumen)
            continue
        new = np.zeros(len(states))
        removed = np.zeros(n_tot + 1)
        kept = np.zeros(n_tot + 1)
        for (a, b), i in index.items():
            if prob[i] == 0.0:
                continue
            for r in range(a + 1):  # r of the a pool molecules removed
                w = scipy.stats.binom.pmf(r, a, f) if kind == "withdrawal" else float(r == a)
                if w == 0.0:
                    continue
                new[index[(a - r, b)]] += prob[i] * w
                removed[r] += prob[i] * w
                kept[a - r] += prob[i] * w
        prob = new
        out["stops"][t] = (_moments(removed), _moments(kept), f)
    return out


def gate_master_equation(raw):
    """Moments of S@pool, S@lumen, G@wall and H@wall from the joint law of (K, n_lumen), with
    SPEC.md section 1's propensities: each G copy to H at k_GH, each H copy to G at
    k_GH e^(mu_H - mu_G); a pool molecule enters at g(K) kappa_in, a lumen molecule leaves at
    g(K) kappa_out, g(K) = (K e^a + (N_g - K) e^b)/N_g."""
    pa = _f(raw["P_s_m_per_s"]) * _f(raw["A_sh_m2"])
    k_in = pa / (_f(raw["V_out_L"]) * 1e-3)
    pots = raw["tracer_potentials_kBT"]
    k_out = pa * math.exp(_f(pots["lumen"]) - _f(pots["solution"])) / (_f(raw["V_in_L"]) * 1e-3)
    gate = raw["gate"]
    a, b = _f(gate["a_open_kBT"]), _f(gate["b_closed_kBT"])
    k_gh = _f(gate["k_GH_per_s"])
    k_hg = k_gh * math.exp(_f(gate["mu0_H_kBT"]) - _f(gate["mu0_G_kBT"]))
    fo = raw["founder_molecules"]
    n_g = fo["G@wall"] + fo["H@wall"]
    n_tot = fo["S@pool"] + fo["S@lumen"]
    states = [(k, n) for k in range(n_g + 1) for n in range(n_tot + 1)]
    index = {s: i for i, s in enumerate(states)}
    gen = np.zeros((len(states), len(states)))
    for (k, n), i in index.items():
        g = (k * math.exp(a) + (n_g - k) * math.exp(b)) / n_g
        moves = [
            ((k - 1, n), k_gh * k),
            ((k + 1, n), k_hg * (n_g - k)),
            ((k, n + 1), g * k_in * (n_tot - n)),
            ((k, n - 1), g * k_out * n),
        ]
        for target, rate in moves:
            if rate > 0:
                gen[i, index[target]] += rate
                gen[i, i] -= rate
    prob = np.zeros(len(states))
    prob[index[(fo["G@wall"], fo["S@lumen"])]] = 1.0
    t_prev, out = 0.0, {}
    for t in (_f(x) for x in raw["observation_times_s"]):
        prob = prob @ scipy.linalg.expm(gen * (t - t_prev))
        t_prev = t
        open_ = np.zeros(n_g + 1)
        lumen = np.zeros(n_tot + 1)
        for (k, n), i in index.items():
            open_[k] += prob[i]
            lumen[n] += prob[i]
        out[("S@lumen", t)] = _moments(lumen)
        out[("S@pool", t)] = _moments(lumen[::-1].copy())
        out[("G@wall", t)] = _moments(open_)
        out[("H@wall", t)] = _moments(open_[::-1].copy())
    return out


def _close(a, b, rel=1e-10, absolute=1e-12):
    return abs(a - b) <= max(rel * max(abs(a), abs(b)), absolute)


def test_shell_tiny_master_equation():
    ref = fr47_exact.reference(TINY_SHELL)
    me = shell_master_equation(TINY_SHELL)
    num = fr47_numeric.shell_numeric(TINY_SHELL)
    checked = 0
    for obs, t, m in ref["pairs"]:
        if obs == "B@wall":
            assert m == {"constant": True, "value": 5}
            continue
        want = me["pairs"][(obs, float(t))]
        got = (float(m["mean"]), float(m["var"]), float(m["mu4"]))
        alt = num["pairs"][(obs, float(t))]
        for x, y, z in zip(got, want, alt, strict=True):
            assert _close(x, y), (obs, t, got, want)
            assert _close(z, y), (obs, t, alt, want)
            checked += 1
    for t, kind, _f, removed, heat in ref["stops"]:
        rem_me, kept_me, f_me = me["stops"][float(t)]
        got = (float(removed["mean"]), float(removed["var"]), float(removed["mu4"]))
        for x, y in zip(got, rem_me, strict=True):
            assert _close(x, y), (t, got, rem_me)
            checked += 1
        if kind == "withdrawal":
            c = -math.log1p(-f_me)
            want = (c * kept_me[0], c * c * kept_me[1], c**4 * kept_me[2])
            got = (float(heat["mean"]), float(heat["var"]), float(heat["mu4"]))
            for x, y in zip(got, want, strict=True):
                assert _close(x, y), (t, got, want)
                checked += 1
        else:
            assert heat is None
    # (d)'s mean trajectory is the exact mean in a linear world, and its heat closes
    for (obs, t), value in ref["d"]["pairs"].items():
        if obs != "B@wall":
            assert _close(float(value), me["pairs"][(obs, float(t))][0])
    assert checked == 4 * 2 * 3 + 3 * 3 + 2 * 3


def test_gate_tiny_master_equation():
    ref = fr47_exact.reference(TINY_GATE)
    me = gate_master_equation(TINY_GATE)
    num = fr47_numeric.gate_numeric(TINY_GATE)
    checked = 0
    for obs, t, m in ref["pairs"]:
        if obs == "B@wall":
            assert m == {"constant": True, "value": 7}
            continue
        want = me[(obs, float(t))]
        got = (float(m["mean"]), float(m["var"]), float(m["mu4"]))
        alt = num["pairs"][(obs, float(t))]
        for x, y, z in zip(got, want, alt, strict=True):
            assert _close(x, y), (obs, t, got, want)
            assert _close(z, y, rel=1e-9), (obs, t, alt, want)
            checked += 1
    assert checked == 4 * 3 * 3
    # the mean field, by an independent integrator
    for (obs, t), value in ref["d"].items():
        if obs != "B@wall":
            assert _close(float(value), num["d_pairs"][(obs, float(t))], rel=1e-11)


def _invented():
    out = {}
    for name in ("invented_shell", "invented_gate"):
        with open(os.path.join(HERE, "inputs", f"{name}.json"), encoding="utf-8") as fh:
            out[name] = json.load(fh)
    return out


def _check_document(doc, raw):
    assert list(doc) == (
        ["world", "units", "pairs", "stops", "d"]
        + (["gap"] if raw["type"] == "gated_shell" else [])
        + ["plants", "provenance"]
    )
    assert doc["world"]["name"] == raw["name"]
    times = [float(t) for t in raw["observation_times_s"]]
    observables = (
        fr47_exact.SHELL_OBSERVABLES
        if raw["type"] == "shell_washes"
        else fr47_exact.GATE_OBSERVABLES
    )
    assert [(e["observable"], e["time_s"]) for e in doc["pairs"]] == [
        (o, t) for o in observables for t in times
    ]
    for e in doc["pairs"]:
        if e["observable"] == "B@wall":
            assert e["class"] == "constant" and e["value"] == raw["founder_molecules"]["B@wall"]
            assert isinstance(e["value"], int)
        else:
            assert e["class"] == "spread" and e["var"] > 0 and e["mu4"] > 0
    for s, stop in zip(doc["stops"], raw.get("stops", []), strict=True):
        assert s["time_s"] == float(stop["time_s"]) and s["kind"] == stop["kind"]
        assert s["removed"]["class"] in ("constant", "spread")
        if stop["kind"] == "replacement":
            assert s["f"] == 1.0 and s["mixing_heat"] is None
        else:
            assert s["mixing_heat"]["class"] in ("constant", "spread")
    assert len(doc["d"]["pairs"]) == len(doc["pairs"])
    if raw["type"] == "shell_washes":
        assert len(doc["d"]["intervals"]) == len(raw["stops"]) + 1
    else:
        assert [(g["observable"], g["time_s"]) for g in doc["gap"]] == [
            (o, t) for o in fr47_exact.GAP_OBSERVABLES for t in times
        ]
        assert all(g["resolution"] >= 0 for g in doc["gap"])
    assert doc["plants"] and all(p["distance_in_bounds"] > 0 for p in doc["plants"])
    for key in ("counts", "pairs", "stops.mixing_heat", "d.intervals.heat", "gap.resolution"):
        assert key in doc["units"]


def test_writer_invented_inputs():
    prov = {
        "references_revision": "self-check",
        "references_clean": False,
        "writer_version": fr47_writer.WRITER_VERSION,
        "regeneration_hash_seeds": fr47_writer.REGENERATION_HASH_SEEDS,
    }
    with tempfile.TemporaryDirectory() as tmp:
        for name, raw in _invented().items():
            path = os.path.join(tmp, f"reference_{name}.json")
            doc = fr47_writer.write(os.path.join(HERE, "inputs", f"{name}.json"), path, prov=prov)
            with open(path, "rb") as fh:
                data = fh.read()
            assert data == fr47_writer.dumps(doc)
            again = fr47_writer.dumps(fr47_writer.build_document(raw, prov))
            assert again == data, "two writes differ"
            higher = fr47_writer.dumps(fr47_writer.build_document(raw, prov, prec=90))
            assert higher == data, "the floats change at 90 digits"
            reread = json.loads(data)
            assert reread == doc and fr47_writer.dumps(reread) == data  # repr round trip
            _check_document(reread, raw)


def test_committed_invented_files_match():
    """Where the package is a clean commit, the committed invented files are what it writes."""
    rev, clean = fr47_writer.package_revision()
    if not (rev and clean):
        return
    prov = fr47_writer.provenance()
    for name, raw in _invented().items():
        path = os.path.join(HERE, "references", f"reference_{name}.json")
        if not os.path.exists(path):
            return
        with open(path, "rb") as fh:
            assert fh.read() == fr47_writer.dumps(fr47_writer.build_document(raw, prov)), name


def test_naming_rules():
    """AMENDMENT-2026-11-24: a plant entry's tie goes to the earliest time or stop, then the first
    observable in the spec's order (section 2); C8 takes the tracer pair alone (section 1)."""
    dec = fr47_exact.Decimal
    cands = [
        {"observable": "S@pool", "time_s": dec(5), "distance": dec(2)},
        {"observable": "mixing_heat", "time_s": dec(2), "distance": dec(2)},
        {"observable": "removed", "time_s": dec(2), "distance": dec(2) * (1 - dec("1e-50"))},
        {"observable": "S@lumen", "time_s": dec(1), "distance": dec(1)},
    ]
    best = fr47_exact._largest(cands)
    assert (best["observable"], best["time_s"]) == ("removed", 2)
    num = {
        ("S@pool", 5.0): (0.0, 2.0, 1.0),
        ("mixing_heat", 2.0): (0.0, 2.0, 1.0),
        ("removed", 2.0): (0.0, 2.0 * (1 - 1e-12), 1.0),
        ("S@lumen", 1.0): (0.0, 1.0, 1.0),
    }
    assert fr47_numeric.largest(num) == ("removed", 2.0)
    with open(os.path.join(HERE, "inputs", "W1.json"), encoding="utf-8") as fh:
        named = {
            (p, c): (b["observable"], b.get("time_s"))
            for p, c, b in fr47_exact.reference(json.load(fh))["plants"]
        }
    # P2's removed count and mixing heat at 2.5 s tie exactly; P6 ties 10.5 s with the horizon
    assert named[("P2", "C4")] == ("removed", 2.5) and named[("P6", "C5")] == (
        "tracer_moiety",
        10.5,
    )
    gaps = {
        ("S@pool", 1.0): (-3.0, 0.1),
        ("S@lumen", 1.0): (3.0, 0.1),
        ("S@pool", 2.0): (2.0, 0.1),
        ("S@lumen", 2.0): (-2.0, 0.1),
    }
    assert fr47_numeric.c8_largest(gaps, [2.0, 1.0]) == ("S@pool", 1.0)


def test_no_engine_import():
    """Code-blind: no engine module is loaded, whether run as a script or under pytest."""
    loaded = [m for m in sys.modules if m == "cells" or m.startswith("cells.")]
    assert not loaded, loaded


if __name__ == "__main__":
    import time

    t0 = time.time()
    for fn in (
        test_shell_tiny_master_equation,
        test_gate_tiny_master_equation,
        test_writer_invented_inputs,
        test_committed_invented_files_match,
        test_naming_rules,
        test_no_engine_import,
    ):
        t1 = time.time()
        fn()
        print(f"{fn.__name__}: ok ({time.time() - t1:.2f} s)")
    print(f"all passed in {time.time() - t0:.2f} s")
