"""Self-check of FR-45's code-blind references. A few seconds; never imports the engine.

  python -m pytest validation/fr45/references/test_references.py -q
  (or: python validation/fr45/references/test_references.py)

It checks the arithmetic (the decimal trig, the rounding), R-eq's routes against each other
on invented inputs (including two nearly equal K, and two equal K, where the pooled closed form
applies, with the user's theta formula), the Taylor integrator against DOP853
and against the fixed-concentration closed form, conservation, the heat's sign and the
affinity check's sensitivity, and that the writer regenerates the committed invented format
sample byte for byte. When the spec copy is present, it also checks the transcribed worlds
against SPEC.md's rows.
"""

from __future__ import annotations

import decimal
import json
import math
import os
import pathlib
import random
import sys
from decimal import Decimal
from fractions import Fraction

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fr45ref_build as BLD  # noqa: E402
import fr45ref_equilibrium as EQ  # noqa: E402
import fr45ref_hp as HP  # noqa: E402
import fr45ref_worlds as WL  # noqa: E402
import fr45ref_writer as WR  # noqa: E402
from fr45ref_model import System  # noqa: E402

SAMPLE = HERE / "format_sample_INVENTED.json"
SPEC_ROOT = pathlib.Path(
    os.environ.get("FR45_SPEC_ROOT", "/mnt/workspaces/Cells/fr45-references-v2-20261124/spec")
)


def _two_ligand_world(
    V, n1, n2, copies, k1, km1, k2, km2, occ1="0.0", occ2="0.0", times=("0.5", "1.0")
):
    """INVENTED inputs: one node, one set, two ligands."""
    w = {
        "id": "T",
        "title": "INVENTED test world",
        "nodes": [{"id": "cup", "kind": "node", "V": V}],
        "ligands": ["X", "Y"],
        "free": [{"ligand": "X", "node": "cup", "n": n1}, {"ligand": "Y", "node": "cup", "n": n2}],
        "sets": [
            {
                "id": "s",
                "owner": "node cup",
                "faces": "cup",
                "copies": copies,
                "sites_per_copy": "1",
                "accessible_fraction": "1.0",
            }
        ],
        "populations": [
            {"id": "s_X", "set": "s", "ligand": "X", "k_on": k1, "k_off": km1, "occupancy": occ1},
            {"id": "s_Y", "set": "s", "ligand": "Y", "k_on": k2, "k_off": km2, "occupancy": occ2},
        ],
        "dt": ["0.01"],
        "times": list(times),
        "horizon": times[-1],
        "wash": None,
    }
    return WL.numeric(w)


def test_decimal_trig_and_rounding():
    for x in (-0.99, -0.5, 0.0, 0.3, 0.999999):
        assert abs(float(HP.acos(HP.D(x))) - math.acos(x)) <= 4e-16 * max(1.0, math.acos(x))
    for y in (0.0, 0.1, 1.0, 2.5, 3.1):
        assert abs(float(HP.cos(HP.D(y))) - math.cos(y)) <= 4e-16
    x = Decimal("0.123456789")
    assert abs(HP.cos(HP.acos(x)) - x) < Decimal("1e-45")
    assert str(HP.pi()).startswith("3.14159265358979323846264338327950288")
    rng = random.Random(7)
    for _ in range(2000):
        d = HP.D(rng.random()) * HP.D(10) ** rng.randint(-30, 30) / 3
        assert HP.f64(d) == float(Fraction(d))
    assert HP.EPS == Decimal(2) ** -52


def test_equilibrium_three_routes():
    cases = [
        (
            "1.0",
            "1.6e-3",
            "0.9e-3",
            "1445314.0",
            "1.2e3",
            "0.9",
            "5.0e2",
            "0.15",
        ),  # W1-like, invented scale
        (
            "3.0",
            "2.0e-3",
            "4.0e-3",
            "2000000.0",
            "800.0",
            "0.4",
            "800.0",
            "0.40001",
        ),  # K1 close to K2
        ("1.0e5", "30.0", "70.0", "9000000000.0", "1.0e4", "0.2", "2.0e4", "0.1"),  # large volume
        ("1.0", "2.0e-3", "1.0e-3", "2000000.0", "1.0e3", "0.5", "2.0e3", "1.0"),  # equal K
    ]
    for args in cases:
        w = _two_ligand_world(*args)
        sysm = System(w)
        N = sysm.pool_totals(sysm.start())
        br = EQ.bracket(sysm, N)
        nw = EQ.newton(sysm, N)
        wg = EQ.wang(sysm, N, 0)
        S = sysm.Sd[0]
        assert 0 < wg["R"] < S and wg["is_largest"] and -1 <= wg["arg"] <= 1
        assert abs(wg["R"] - br["R"][0]) / S < Decimal("1e-40")
        assert max(abs(a - b) for a, b in zip(br["state"], nw["state"], strict=True)) / S < Decimal(
            "1e-40"
        )
        res = EQ.residuals(sysm, N, br["state"])
        assert max(res.values()) / S < Decimal("1e-40")
        # the pooled closed form, where both K are equal, and the user's theta both ways
        pooled = EQ.pooled(sysm, N)
        assert bool(pooled) == (sysm.K[0] == sysm.K[1])
        for pl in pooled.values():
            assert max(abs(v - br["state"][i]) for i, v in pl["amounts"].items()) / S < Decimal(
                "1e-40"
            )
        assert max(abs(a - b) for a, b in BLD.theta_both_ways(sysm, br["state"])) < Decimal("1e-40")
        # the affinity check vanishes at the root and is sensitive away from it
        assert max(abs(a) for a in EQ.affinities(sysm, br["state"])) / BLD.RT < Decimal("1e-25")
        far = list(br["state"])
        far[sysm.i_pop(0)] *= Decimal("1.001")
        far[sysm.i_set(0)] -= br["state"][sysm.i_pop(0)] * Decimal("0.001")
        far[0] -= br["state"][sysm.i_pop(0)] * Decimal("0.001")
        assert max(abs(a) for a in EQ.affinities(sysm, far)) / BLD.RT > Decimal("1e-4")


def test_taylor_against_dop853_and_conservation():
    w = _two_ligand_world(
        "1.0",
        "1.6e-3",
        "0.9e-3",
        "1445314.0",
        "1.2e3",
        "0.9",
        "5.0e2",
        "0.15",
        occ1="0.1",
        times=("0.25", "0.5", "1.0"),
    )
    sysm = System(w)
    out = BLD.integrate(sysm, w, BLD.PROFILES["sample"])
    y0 = out["y0"]
    N0 = sysm.pool_totals(y0)
    scale = max(abs(v) for v in y0)
    for k in range(1, 4):
        yB = out["B"]["states"][k]
        yA = out["A"][1e-13]["states"][k]
        assert max(abs(HP.D(float(a)) - b) for a, b in zip(yA, yB, strict=True)) / scale < Decimal(
            "1e-10"
        )
        assert max(
            abs(a - b) for a, b in zip(sysm.pool_totals(yB), N0, strict=True)
        ) / scale < Decimal("1e-40")
        assert abs(sysm.set_sums(yB)[0] - sysm.Sd[0]) / sysm.Sd[0] < Decimal("1e-40")
        # the coarse and fine Taylor runs agree far below binary64
        yC = out["Bc"]["states"][k]
        assert max(abs(a - b) for a, b in zip(yB, yC, strict=True)) / scale < Decimal("1e-17")
    # the heat over every interval is non-negative (G is a Lyapunov function of SPEC §1.2)
    G = [sysm.G(y, "cup") for y in out["B"]["states"]]
    assert all(G[k] >= G[k + 1] for k in range(len(G) - 1))


def test_taylor_against_closed_form():
    # INVENTED: a volume so large that the concentrations are fixed to ~1e-25
    w = _two_ligand_world(
        "1.0e25",
        "1.2e22",
        "0.8e22",
        "1445314.0",
        "1.2e3",
        "0.9",
        "5.0e2",
        "0.15",
        times=("0.4", "0.8"),
    )
    sysm = System(w)
    out = BLD.integrate(sysm, w, BLD.PROFILES["sample"])
    S = sysm.Sd[0]
    for k, t in enumerate(w["times"], start=1):
        cf = BLD.closed_form(sysm, out["y0"], HP.D(t), 0)
        yB = out["B"]["states"][k]
        assert abs(cf["B"][0] - yB[sysm.i_pop(0)]) / S < Decimal("1e-20")
        assert abs(cf["B"][1] - yB[sysm.i_pop(1)]) / S < Decimal("1e-20")
        assert abs(cf["R"] - yB[sysm.i_set(0)]) / S < Decimal("1e-20")


def test_steps_are_exact_integers():
    assert WL.steps("4.0125", "0.0125") == 321
    assert WL.steps("51.2", "0.008") == 6400
    try:
        WL.steps("0.3", "0.008")
    except ValueError:
        pass
    else:
        raise AssertionError("a non-integer step count must be refused")


def test_spec_rows_when_present():
    spec = SPEC_ROOT / "validation" / "fr45" / "spec" / "SPEC.md"
    if not spec.exists():
        return
    rows = WL.check_against_spec(spec.read_text(encoding="utf-8"))
    assert len(rows) > 60


def test_format_sample_regenerates_bitwise():
    payload = WR.build_sample()
    text = WR.dumps(payload)
    assert text == SAMPLE.read_text(encoding="utf-8"), "the committed format sample is stale"
    d = json.loads(text)
    assert d["invented"] is True and d["INVENTED"].startswith("INVENTED INPUTS")
    for key in (
        "world",
        "units",
        "equilibrium",
        "trajectory",
        "balances",
        "wash",
        "heats",
        "pairs",
        "spread",
        "distance_at_horizon",
        "closed_form",
        "stage",
        "plants",
        "provenance",
    ):
        assert key in d, key
    assert d["spread"] == "none"
    classes = {p["class"] for p in d["pairs"]}
    assert classes == {"constant", "derived", "band"}
    assert {p["value"] for p in d["pairs"] if p["class"] == "constant"} == {
        "unchanged",
        "refused",
        "completes",
    }
    assert {p["criterion"] for p in d["pairs"]} == {
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
    }
    assert {p["plant"] for p in d["plants"]} == {f"P{i}" for i in range(1, 10)}
    for pair in d["pairs"]:
        counts_steps = pair["criterion"] in ("C2b", "C3b", "C4a", "C5", "C10") or (
            pair["criterion"] == "C8" and not pair["observable"].startswith("ratio:")
        )
        assert ("dt_s" in pair) == counts_steps, pair
    times = set(d["world"]["observation_times"])
    assert {r["time_s"] for r in d["trajectory"]} == times
    # the saved rows of C4a, C5 and C9 include the start (AMENDMENT answer 7)
    for crit in ("C4a", "C5", "C9"):
        assert {p["time_s"] for p in d["pairs"] if p["criterion"] == crit} == times | {0.0}, crit
    # C3c covers the wash's interval; C3a and C3b leave it out
    assert any(p.get("spans_wash") for p in d["pairs"] if p["criterion"] == "C3c")
    assert not any(p.get("spans_wash") for p in d["pairs"] if p["criterion"] in ("C3a", "C3b"))
    # C9's and C4b's state-dependent tolerances are written as terms (AMENDMENT answer 9)
    for pair in d["pairs"]:
        state_dependent = pair["criterion"] == "C9" or (
            pair["criterion"] == "C4b" and not pair["observable"].startswith("supplied:")
        )
        if state_dependent:
            assert pair["tolerance"] is None and "formula" in pair["tolerance_terms"], pair
    assert any(p.get("information") for p in d["plants"])
    # amendment 2: theta in the equilibrium, both ways, for every population
    assert set(d["equilibrium"]["theta"]) == {q["id"] for q in d["world"]["populations"]}
    for th in d["equilibrium"]["theta"].values():
        assert set(th) == {"formula", "root", "gap"}
    # the event map alone on the start and on the wash row (W7's shape), and P5 per state
    wash_t = d["world"]["wash"]["t"]
    for crit in ("C4b", "C6"):
        assert {p["time_s"] for p in d["pairs"] if p["criterion"] == crit} == {0.0, wash_t}
    p5 = [(e["criterion"], e["compared"]["time_s"]) for e in d["plants"] if e["plant"] == "P5"]
    assert [c for c, _ in p5] == ["C6", "C6", "C4a"] and [t for _, t in p5[:2]] == [0.0, wash_t]


def test_free_energy_function_is_the_references_own():
    import fr45ref_free_energy as FE

    for wid, builder in (("W3", WL.world_W3), ("W7", WL.world_W7)):
        world = WL.numeric(builder()[0])
        with decimal.localcontext(HP.make_context(FE.DIGITS)):
            sysm = System(world)
            y = list(sysm.start())
            y[0] = y[0] * Decimal("0.75")  # any state will do
        names = sysm.observables()
        for node in sysm.facing_nodes():
            amounts = {
                names[i]: float(y[i]) for i in range(sysm.n) if sysm.node_of_component(i) == node
            }
            exact = [HP.D(float(v)) for v in y]
            with decimal.localcontext(HP.make_context(FE.DIGITS)):
                want = +sysm.G(exact, node)
            assert FE.G(wid, node, amounts) == want
            bad = dict(amounts)
            bad.pop(sorted(bad)[0])
            try:
                FE.G(wid, node, bad)
            except KeyError:
                pass
            else:
                raise AssertionError("a missing amount must be refused")


def test_no_engine_import():
    assert not any(m == "cells" or m.startswith("cells.") for m in sys.modules)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
