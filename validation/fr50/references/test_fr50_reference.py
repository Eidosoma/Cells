"""Self-check of the FR-50 code-blind reference. No engine import; it compiles no world.

    python -m pytest -q -p no:cacheprovider validation/fr50/references/test_fr50_reference.py

About 3 s on one core. It checks route B's own exp and ln, the zero-net states' exact
identities, u = 1/2 at E4's reversal, Ussing's ratio at the host voltages, K2's conservation, and
that the committed results/ and format-sample/ files are what the writer produces.
"""

from __future__ import annotations

import decimal
import json
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fr50_ode as ode  # noqa: E402
import fr50_reference as writer  # noqa: E402
import fr50_route_a as route_a  # noqa: E402
import fr50_route_b as route_b  # noqa: E402
import fr50_spec  # noqa: E402

SPEC = fr50_spec.load()
SAMPLE_SPEC = fr50_spec.load(writer.SAMPLE_SPEC)
CASES = {case.kind: case for case in SPEC.cases}
RESULT_FILES = sorted((HERE / "results").glob("*.json"))
SAMPLE_FILES = sorted((HERE / "format-sample").glob("INVENTED_*.json"))
rel = writer.rel


@pytest.fixture(autouse=True)
def _high_precision():
    """The tests' own decimal arithmetic runs at 140 digits, not the default 28."""
    with decimal.localcontext(route_a.context(140)):
        yield


@pytest.mark.parametrize("x", ["0", "1e-49", "-3.25", "2.5", "-57", "0.5"])
def test_route_b_exp_and_ln_match_decimal(x):
    ctx = decimal.Context(prec=250)
    assert rel(ctx.exp(Decimal(x)), route_b.exp_q(Fraction(x))) < 1e-190
    if Fraction(x) > 0:
        assert rel(ctx.ln(Decimal(x)), route_b.ln_q(Fraction(x))) < 1e-190


def test_zero_net_states_are_exact():
    for kind in ("K1", "E2", "E3"):
        A, B = route_a.CaseA(SPEC, CASES[kind]), route_b.CaseB(SPEC, CASES[kind])
        assert A.values["net"] == 0 and B.values["net"] == 0 and B.values["rho"] == 1
        assert A.values["forward"] == A.values["backward"]
        assert B.values["route"] == "direct_exact"
    A, B = route_a.CaseA(SPEC, CASES["K4"]), route_b.CaseB(SPEC, CASES["K4"])
    assert A.values["dG_cyc_over_RT"] == 0 and B.values["dG_cyc_over_RT"] == 0
    assert A.values["J_plus"] == A.values["J_minus"]
    # S = 1/(1 + 0.25/0.25) / (1 + 0.1/1) = 5/11, so J+ = 1e-3 x 5/11
    assert Fraction(B.values["J_plus"]) == Fraction(5, 11 * 1000)
    assert rel(A.values["J_plus"], Fraction(5, 11000)) < 1e-115


def test_reversal_cases():
    for kind in ("E1", "E4"):
        A, B = route_a.CaseA(SPEC, CASES[kind]), route_b.CaseB(SPEC, CASES[kind])
        assert Fraction(A.E_K) == B.E_K
        assert B.values["route"] == "ussing_and_net"
        assert rel(A.values["forward"], A.values["backward"]) < 1e-48
        assert 0 < abs(B.values["rho"] - 1) < 1e-48  # E_K carries 50 digits
        for key in ("forward", "backward"):
            assert rel(A.values[key], B.values[key]) < 1e-100
    A = route_a.CaseA(SPEC, CASES["E4"])
    assert A.values["u"] == Decimal("0.5")
    assert route_b.CaseB(SPEC, CASES["E4"]).values["u"] == Fraction(1, 2)


@pytest.mark.parametrize("kind", ["K3", "E6"])
def test_host_evaluations_follow_ussing(kind):
    case = CASES[kind]
    A, B = route_a.CaseA(SPEC, case), route_b.CaseB(SPEC, case)
    q = A.q
    c_in, c_out = Decimal(case["c_in_mM"]), Decimal(case["c_out_mM"])
    for ea, eb in zip(A.evaluations, B.evaluations, strict=True):
        x = case["valence"] * q * ea["V"]
        assert rel(ea["ratio_inward_over_outward"], c_out / c_in * (-x).exp()) < 1e-110
        for key in ("forward", "backward"):
            assert rel(ea[key], eb[key]) < 1e-100
    if kind == "E6":
        n = len(case["voltages_V"])
        full, half = A.evaluations[:n], A.evaluations[n:]
        for one, other in zip(full, half, strict=True):
            assert rel(one["forward"], 2 * other["forward"]) < 1e-110  # availability 0.5
            assert one["u"] == other["u"]
            assert rel(one["difference"], one["forward"] - one["backward"]) < 1e-110


def test_K4h_ratio_is_exp_dG():
    A = route_a.CaseA(SPEC, CASES["K4h"])
    v = A.values
    assert rel(v["J_minus_over_J_plus"], v["dG_cyc_over_RT"].exp()) < 1e-110


def test_K2_conservation_and_radau():
    case = CASES["K2"]
    A = route_a.CaseA(SPEC, case)
    v = A.values
    V_O, V_N = Decimal(case["V_cell_pL"]), Decimal(case["V_node_pL"])
    total = V_O * v["c_cell"][0] + V_N * v["c_node"][0]
    for i in range(len(v["F"])):
        assert rel(V_O * v["c_cell"][i] + V_N * v["c_node"][i], total) < 1e-110
        # the net inward record is the cell's gain
        gain = V_O * (v["c_cell"][i] - v["c_cell"][0])
        assert abs(v["F"][i] - v["B"][i] - gain) <= Decimal("1e-110") * total
    radau = ode.relaxation_radau(case)
    for key in ("c_cell", "c_node", "F", "B"):
        assert all(rel(a, b) < 1e-11 for a, b in zip(v[key], radau[key], strict=True))


def _strings(doc: dict) -> None:
    def walk(value, name=""):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(item, key)
        elif isinstance(value, list):
            for item in value:
                walk(item, name)
        elif isinstance(value, str) and name.endswith(("_s", "_mM", "_fmol", "_cycles",
                                                       "_over_RT", "_over_J_plus", "_per_s")):
            if name in ("record_times_s",) or name.endswith("_V") or value == "0":
                return
            Decimal(value)
            mantissa = value.lstrip("-").split("e")[0].replace(".", "")
            assert len(mantissa) == writer.OUT_DIGITS, (name, value)

    walk({k: v for k, v in doc.items() if k not in ("declared", "method", "provenance")})


@pytest.mark.skipif(not RESULT_FILES, reason="results/ is not generated yet")
def test_committed_results_are_what_the_writer_produces():
    assert {path.stem for path in RESULT_FILES} == {case.id for case in SPEC.cases}
    for path in RESULT_FILES:
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["inputs"]["invented"] is False
        assert doc["method"]["within_declared_accuracy"] is True
        assert doc["provenance"]["dirty_paths"] == []
        _strings(doc)
    for kind in ("E4", "K2", "E6"):
        case = CASES[kind]
        doc = json.loads((HERE / "results" / f"{case.id}.json").read_text(encoding="utf-8"))
        A = route_a.CaseA(SPEC, case)
        if kind == "E4":
            assert doc["u"] == writer.fmt(A.values["u"])
            assert doc["F_fmol"] == [writer.fmt(x) for x in A.values["F"]]
            assert doc["E_K_V"] == str(A.E_K)
        elif kind == "K2":
            assert doc["B_fmol"] == [writer.fmt(x) for x in A.values["B"]]
        else:
            assert [e["u"] for e in doc["evaluations"]] == [writer.fmt(e["u"])
                                                             for e in A.evaluations]


def _skeleton(value):
    """The layout of a JSON value: keys, value types, and list lengths."""
    if isinstance(value, dict):
        return {key: _skeleton(item) for key, item in value.items()}
    if isinstance(value, list):
        return ["list", len(value), _skeleton(value[0]) if value else None]
    return type(value).__name__


@pytest.mark.skipif(not (RESULT_FILES and SAMPLE_FILES), reason="outputs not generated yet")
def test_format_sample_has_the_results_layout_and_is_marked_invented():
    real = {fr50_spec.kind_of(p.stem): json.loads(p.read_text(encoding="utf-8"))
            for p in RESULT_FILES}
    sample = {fr50_spec.kind_of(p.stem): json.loads(p.read_text(encoding="utf-8"))
              for p in SAMPLE_FILES}
    assert sample.keys() == real.keys()
    for kind, doc in sample.items():
        assert doc["inputs"]["invented"] is True and "INVENTED" in doc["inputs"]["statement"]
        shape, real_shape = _skeleton(doc), _skeleton(real[kind])
        # the declared echo carries each case's own descriptive strings, the same keys
        assert shape.pop("declared").keys() == real_shape.pop("declared").keys()
        assert shape == real_shape, kind


def test_no_engine_module_is_imported():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
