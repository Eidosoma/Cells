"""MT-1's code-blind component references for the mitochondrial laws (the appendix at tag
mito-laws-appendix-2026-11-20b): the fast check.

The interface files parse and agree with their generator at a few rows; the physics checks pass
at a few exact states; the recorded verdicts hold; and nothing imports ``cells``. The full
regeneration (about 40 s on one core) is ``python -m
validation.mitochondria.references.components.design --check`` and stays out of this file.
"""
from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.mitochondria.references.components import (  # noqa: E402
    checks, design, hp, laws, plants, states)
from validation.mitochondria.references.components.hp import DEC, precision  # noqa: E402

IFACE = ROOT / "validation" / "mitochondria" / "references" / "components" / "interface"


def _load(name):
    return json.loads((IFACE / name).read_text())


def test_interface_parses_and_rows_match_states():
    inputs, rows = _load("inputs.json"), _load("rows.json")
    assert inputs["status"] == rows["status"] == "proposed, not registered"
    assert set(inputs["states"]) == set(rows["laws"]) == set(design.FORMS)
    for key, forms in rows["laws"].items():
        ids = [st["id"] for st in inputs["states"][key]]
        assert len(ids) == len(set(ids))
        assert tuple(forms) == design.registered_forms(key)
        for form, rs in forms.items():
            assert [r["id"] for r in rs] == ids
            for r in rs:
                for v in r["ref"].values():
                    for s in (v.values() if isinstance(v, dict) else (v,)):
                        Decimal(s)
                for v in r["band"].values():
                    for b in (v.values() if isinstance(v, dict) else (v,)):
                        assert b >= 0


def test_rows_regenerate_at_a_few_states():
    inputs, rows = _load("inputs.json"), _load("rows.json")
    for key, forms in rows["laws"].items():
        law = laws.LAWS_BY_KEY[key]
        P = hp.parameters(law.column)
        by_id = {st["id"]: st for st in inputs["states"][key]}
        for form, rs in forms.items():
            for r in (rs[0], rs[1], rs[-1]):
                s = {k: Decimal(v) for k, v in by_id[r["id"]]["inputs"].items()}
                with precision():
                    C = hp.constants(DEC)
                    ref = design.reference(law, P, C, s, form)
                    band = design.bands_for(law, P, C, s, form, ref)
                assert {k: design._ser(v) for k, v in ref.items()} == r["ref"], (key, form, r["id"])
                got = {k: ({kk: design._up(vv) for kk, vv in v.items()} if isinstance(v, dict)
                           else design._up(v)) for k, v in band.items()}
                assert got == r["band"], (key, form, r["id"])


def test_physics_at_a_few_exact_states():
    with precision():
        C = hp.constants(DEC)
        for law in laws.CYCLE_LAWS:
            P = hp.parameters(law.column)
            legs = law.legs_(P)
            assert sum(nu * z for _k, _s, nu, z in legs) == 0 and law.q_N(P) == -law.q(P)
            s0 = states.full_state(P, {})
            assert abs(law.x(DEC, P, C, s0) - law.dG_appendix(DEC, P, C, s0) / C["RT"]) < checks.TOL_EXACT
            if not law.has_flux:
                continue
            x0 = law.x(DEC, P, C, s0)
            for form in design.FORMS[law.key]:  # every form, registered or not
                A_l, B_l = law.literal_terms(form, DEC, P, C, s0)
                d = law.kappa_inv * (B_l / A_l).ln() - x0
                if law.form_kind(form) == "two_term":
                    # A failing form: its mismatch is the appendix's closed form, and not small.
                    assert abs(d - law.form_d_closed(form, DEC, P, C, s0)) < checks.TOL_EXACT
                    assert abs(d) > Decimal("0.1")
                    continue
                # A balanced form: d = 0, J = 0 at x = 0 and reverses past it, slopes check out.
                assert abs(d) < checks.TOL_EXACT
                r0 = laws.evaluate(law, DEC, P, C, s0, form)
                assert abs(r0["A_term"] / A_l - 1) < checks.TOL_EXACT
                at0 = laws.evaluate(law, DEC, P, C, checks.place_at_x(law, P, C, s0, 0), form)
                assert abs(at0["J"] / at0["S"]) < checks.TOL_EXACT
                for t in ("-1e-3", "2"):
                    r = laws.evaluate(law, DEC, P, C, checks.place_at_x(law, P, C, s0, Decimal(t)), form)
                    assert (r["J"] > 0) == (r["x"] < 0) and r["dissipation_W_per_L"] > 0
                num = checks.numeric_slopes(law, P, C, s0, "S", form)
                assert max(abs(num[v] - r0["slopes_lnS"][v]) for v in num) < checks.TOL_FD
            form0 = design.FORMS[law.key][0]
            assert abs(law.S_closed(DEC, P, C, s0) / laws.evaluate(law, DEC, P, C, s0, form0)["S"] - 1) < checks.TOL_EXACT
        # Section 8: the outer membrane's class sums equal Eq. 13; equal sides carry nothing.
        om = laws.OUTER
        P = hp.parameters(om.column)
        s0 = states.full_state(P, {})
        r = om.evaluate(DEC, P, C, s0)
        for c in om.CLASS_TOTALS:
            assert abs(r["class_J"][c] - r["eq13_J"][c]) <= checks.TOL_EXACT * abs(r["eq13_J"][c])
        assert all(v > 0 for v in r["dissipation_W_per_L"].values())
        same = dict(s0, **{k[:-2] + "_P": v for k, v in s0.items() if k.endswith("_E")})
        assert all(v == 0 for v in om.evaluate(DEC, P, C, same)["J"].values())
        # Section 10's two planted controls fail the equilibrium check.
        for pid in ("C1_q_reversed", "ANT_shares_0.35_0.60"):
            pl = plants.PLANTS_BY_ID[pid]
            law = laws.LAWS_BY_KEY[pl.law_key]
            P = hp.parameters(law.column)
            s = checks.place_at_x(law, P, C, states.full_state(P, {}), 0)
            v = pl.values(s, "declared")
            assert abs(v["J"] / v["S"]) > Decimal("1e-3")


def test_recorded_verdicts():
    chk, pl = _load("checks.json"), _load("plants.json")
    assert all(r["passes"] for r in chk["laws"].values())
    assert all(e["passes"] for r in chk["laws"].values() for e in r.get("equilibrium", {}).values())
    assert all(v["refused"] for v in chk["planted_controls"].values())
    assert chk["float64_calibration"]["passes"]
    assert chk["lumped_identity"]["passes"] and chk["binding_chain"]["passes"]
    assert chk["supply"]["passes"] and chk["kinase"]["passes"] and chk["outer_membrane"]["passes"]
    assert chk["appendix_numbers"]["all_agree"]
    assert all(v["passes"] for v in chk["form_identities"].values())
    assert all(e["caught"] for e in pl["plants"].values())
    assert set(pl["plants"]) <= {p.pid for p in plants.PLANTS}
    if design.REGISTERED_FORMS is None:
        assert set(pl["plants"]) == {p.pid for p in plants.PLANTS}


def test_nothing_imports_cells():
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import validation.mitochondria.references.components.design, "
        "validation.mitochondria.references.components.checks; "
        "bad = [m for m in sys.modules if m == 'cells' or m.startswith('cells.')]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    res = subprocess.run([sys.executable, "-c", code, str(ROOT)], capture_output=True, text=True,
                         timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
