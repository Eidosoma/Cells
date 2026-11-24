"""Self-check of FR-38's second comparison's code-blind references (about 10 s, no engine import).

Run with BLAS pinned to one thread:

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
        python -B -m pytest -q validation/gene_regulation/fr38_v2/references/test_fr38v2_references.py

or as a script (python -B test_fr38v2_references.py). It checks the integrators' coefficients,
exact structural zeros of the equations of motion, and the writer on the invented family: the
file's layout and classes (SPEC.md sections 4 and 7, amendments 1 and 2), the accuracy
requirement, and that reference_invented.json regenerates bitwise, provenance aside.
"""

import json
import os
import sys
import tempfile
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402

import fr38v2_integrate as In  # noqa: E402
import fr38v2_model as Mo  # noqa: E402
import fr38v2_worlds as Wd  # noqa: E402
import fr38v2_writer as Wr  # noqa: E402

LD = np.longdouble
COMMITTED = os.path.join(HERE, "out", "reference_invented.json")


def test_no_engine_import():
    assert not any(m == "cells" or m.startswith("cells.") for m in sys.modules)


def test_coefficients():
    n, w = In.gbs_weights(8)
    assert n == [2, 4, 6, 8, 10, 12, 14, 16]
    assert abs(sum(w) - 1) < LD("1e-17")
    c, A, b, E = In.gauss_legendre(5)        # asserts B(10) and C(5) in 50-digit arithmetic
    assert abs(c[2] - LD("0.5")) < LD("1e-19")
    for q in range(1, 11):
        assert abs(np.sum(b * c ** (q - 1)) - LD(1) / q) < LD("1e-18")
    assert np.allclose(np.sum(E, axis=1).astype(float), 1.0)


def test_structural_zeros():
    w = Mo.World(Wd.family("AF"))
    sv = w.segment_values(0.0)
    f = w.rhs(np.zeros((w.NS, w.R), dtype=LD), w.batch(1, sv))
    I = w.ix
    blank = w.row_index["blank"]
    for s in ("C1", "H", "iJI", "iQ", "iQd", "iQs", "HrelD", "HrelS", "Htx"):
        assert f[I[s], blank] == 0
    for run, idle in (("p=0 returned", "D"), ("p=1 held", "S")):
        r = w.row_index[run]
        assert f[I["iQ" + idle.lower()], r] == 0 and f[I["Hrel" + idle], r] == 0
        assert not np.signbit(f[I["iQ" + idle.lower()], r])
    # the machines, the hold and the moieties are linear invariants of the right-hand side
    r = w.row_index["p_sched held"]
    mach = f[I["F"], r] + sum(f[I[f"C{j}"], r] for j in range(1, 9)) + f[I["H"], r]
    assert abs(mach) <= LD("1e-27")     # a few ulps of fluxes near 1e-10 fmol/s
    assert Fraction(Wd.COPY_FMOL) == Fraction(1.6605390671738468e-09)


def _validate(doc):
    times = doc["times_s"]
    assert len(times) <= 61
    assert doc["kind"] == "cells.fr38_v2.reference@1"
    assert doc["units"] == {"amount": "fmol", "energy": "pJ", "time": "s", "volume": "pL",
                            "copy_fmol": Wd.COPY_FMOL}
    assert doc["provenance"]["sha256_of_this_file_excluded"] is True
    assert doc["method"]["run_time_s"] == "out/run_times.json"
    assert doc["method"]["safety_factor"] >= 2
    runs = doc["runs"]
    assert "blank" in runs and set(runs["blank"]) == {"series", "checks"}
    t1, t2 = doc["inputs"]["window_s"]
    world = Mo.World(Wd.family(doc["family"]))
    seen_constant = False
    for name, run in runs.items():
        row = world.rows[world.row_index[name]]
        for qn, s in run["series"].items():
            assert len(s["class"]) == len(s["value"]) == len(s["accuracy"]) == len(times)
            assert s["class"] == Wr.classes_for(qn, row, times, t1, t2)
            for c, v, a in zip(s["class"], s["value"], s["accuracy"]):
                assert c in ("constant", "stepped")
                if c == "constant":
                    seen_constant = True
                    assert v == 0.0 and not np.signbit(v) and a is None
                else:
                    assert np.isfinite(v) and a is not None and a >= 0
                    if Wr.judged(world, qn):
                        assert a <= 1e-11 * s["scale"]
        if name == "blank":
            continue
        assert {"series", "checks", "survival", "route2", "not_compared",
                "excess_over_blank"} <= set(run)
        for e in run["survival"]:
            if e["ratio"] is None:
                assert e["alive_t2"] == 0.0 and e["alive_ts"] == 0.0
                assert e["accuracy"] == [None, None, None]
        for e in run["route2"]:
            if e["class"] == "constant":
                assert e["value"] == 0.0 and e["accuracy"] is None
            else:
                assert e["accuracy"] <= 1e-11 * e["scale"]
        for fate in ("durable", "short_lived"):
            s = run["excess_over_blank"][fate]
            assert set(s["class"]) == {"stepped"}
            assert len(run["not_compared"][f"cohort_net_{fate}"]) == len(times)
        assert run["checks"]["membership_sum_largest_relative"] < 1e-15
        assert run["checks"]["G_identity_largest_pJ"] < 1e-15
    assert seen_constant
    kinds = {p["plant"] for p in doc["plants"]}
    # mapping (P1, P1''), host-side (P1'), world data (P2-P5, P7), record (P6)
    assert {"P1", "P1′", "P1″", "P2", "P3a", "P3b", "P4", "P5", "P6", "P7"} <= kinds
    for p in doc["plants"]:
        assert {"plant", "run", "quantity", "time_s", "honest", "planted",
                "relative_distance", "scale"} <= set(p)
        if p["plant"] == "P1′":
            assert {"route2_bound", "distance_in_route2_bounds"} <= set(p)


def _without_provenance(doc):
    d = dict(doc)
    d.pop("provenance")
    return Wr.dumps(d)


def test_invented_file_regenerates_and_validates():
    with tempfile.TemporaryDirectory(dir=os.environ.get("FR38V2_TMP")) as tmp:
        path, _ = Wr.write_family(Wd.family("invented"), tmp)
        with open(path, encoding="ascii") as fh:
            text = fh.read()
    doc = json.loads(text)
    assert Wr.dumps(doc) == text                      # canonical bytes: sorted keys, repr floats
    _validate(doc)
    if os.path.exists(COMMITTED):
        with open(COMMITTED, encoding="ascii") as fh:
            committed = json.load(fh)
        assert _without_provenance(doc) == _without_provenance(committed)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
