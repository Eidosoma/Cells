"""Self-check of the FR-51 code-blind reference. No engine import; it compiles no world.

    python -m pytest -q -p no:cacheprovider validation/fr51/references/test_fr51_reference.py

About 5 s on one core: route A on eight cases, route B at nine points, and the committed
outputs. It checks route B's own exp and ln, the two routes' agreement at sample points, the
fraction's exact ends, the identities of LAWS.md 2, 3 and 6, the block's senses, and that the
committed results/ and format-sample/ files are what the writer produces.
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

import fr51_reference as writer  # noqa: E402
import fr51_route_a as route_a  # noqa: E402
import fr51_route_b as route_b  # noqa: E402
import fr51_spec  # noqa: E402

SPEC = fr51_spec.load()
SAMPLE_SPEC = fr51_spec.load(writer.SAMPLE_SPEC)
CASES = {case.id: case for case in SPEC.cases}
I_E = SPEC.grid_count  # the index of V = E_ion; E_ion - 0.0005 and E_ion + 0.0005 follow
RESULT_FILES = sorted((HERE / "results").glob("*.json"))
SAMPLE_FILES = sorted((HERE / "format-sample").glob("INVENTED_*.json"))
EXACT_ARRAYS = ("voltages_V", "V_ref_V")  # exact decimal strings; every other value has 30 digits
_cache: dict = {}


def full_a(case_id: str, spec: fr51_spec.Spec = SPEC):
    """Route A at every voltage of one case, cached."""
    key = (spec.path, case_id)
    if key not in _cache:
        case = {c.id: c for c in spec.cases}[case_id]
        A = route_a.CaseA(spec, case)
        _cache[key] = (A, A.evaluate())
    return _cache[key]


@pytest.mark.parametrize("x", ["0", "1e-49", "-1e-49", "0.037", "-57", "60", "-0.5", "3.3"])
def test_route_b_exp_and_ln_match_decimal(x):
    ctx = decimal.Context(prec=250)
    assert writer.rel(Fraction(ctx.exp(Decimal(x))), route_b.exp_q(Fraction(x))) < 1e-190
    if Fraction(x) > 0 and Fraction(x) != 1:
        assert writer.rel(Fraction(ctx.ln(Decimal(x))), route_b.ln_q(Fraction(x))) < 1e-190


SAMPLE_POINTS = [("P1_K_equal", 240), ("P4_Cl_unequal", I_E), ("B1_two_modes_E1", 0),
                 ("B1_two_modes_E1", I_E), ("B4_anion_effective", 80),
                 ("S2_strong_two_modes", 300), ("G3_steep_Na_outside_voltage", 20),
                 ("G4_steep_Na_inside_reversal", I_E + 2), ("Z1_zero_blocker", 100)]


@pytest.mark.parametrize(("case_id", "j"), SAMPLE_POINTS)
def test_routes_agree_at_sample_points(case_id, j):
    A = route_a.CaseA(SPEC, CASES[case_id])
    B = route_b.CaseB(SPEC, CASES[case_id])
    assert Fraction(A.voltages[j]) == B.voltages[j]
    a, b = A.point(A.voltages[j]), B.point(B.voltages[j])
    assert a.keys() == b.keys()
    for key in a:
        pairs = zip(a[key], b[key], strict=True) if key in writer.PER_MODE else [(a[key], b[key])]
        for va, vb in pairs:
            if key == "V_ref":
                assert Fraction(va) == vb
            else:
                bound = 1e-60 if key in writer.U_AND_CURRENTS else 1e-80
                assert writer.rel(Fraction(va), vb) < bound, key


def test_zero_blocker_gives_exactly_the_free_population():
    _, out = full_a("Z1_zero_blocker")
    assert all(u == 1 for u in out["u"])
    assert all(theta == 0 for mode in out["theta"] for theta in mode)
    assert out["J_blocked"] == out["J_free"]
    assert out["dI_blocked_dV"] == out["dI_free_dV"]
    assert writer.fmt(out["u"][0]) == "1.00000000000000000000000000000e+0"


def test_strong_block_is_relatively_accurate():
    # delta = 0, so K = K(0) and u = K(0)/(c_B + K(0)), about 1e-18
    _, out = full_a("S1_strong_one_mode")
    k0 = Fraction("1e-15")
    expected = k0 / (Fraction(1000) + k0)
    assert all(writer.rel(Fraction(u), expected) < 1e-115 for u in out["u"])


def test_equal_concentrations_give_a_line_through_zero():
    A, out = full_a("P1_K_equal")
    G = (Fraction(A.pref) * A.case.z ** 2 * Fraction(A.F) * Fraction(A.q) * Fraction(A.c_i)
         / 10**15)
    for V, current in zip(A.voltages, out["I_free"], strict=True):
        if V == 0:
            assert current == 0
        else:
            assert writer.rel(Fraction(current), G * Fraction(V)) < 1e-110


@pytest.mark.parametrize("case_id", ["P2_K_unequal", "P3_Na_unequal", "P4_Cl_unequal"])
def test_current_reverses_at_the_nernst_potential(case_id):
    A = route_a.CaseA(SPEC, CASES[case_id])
    B = route_b.CaseB(SPEC, CASES[case_id])
    assert Fraction(A.E_ion) == B.E_ion
    at, below, above = (A.free(A.voltages[I_E + n]) for n in (0, 1, 2))
    assert below["I_free"] < 0 < above["I_free"]
    assert abs(at["J_free"]) < Decimal("1e-45") * abs(above["J_free"])


REVERSAL_CASES = [c.id for c in SPEC.cases if c.block is not None and c.block.reversal_ion]


@pytest.mark.parametrize("case_id", REVERSAL_CASES)
def test_u_at_reversal_is_the_zero_voltage_fraction(case_id):
    case = CASES[case_id]
    A = route_a.CaseA(SPEC, case)
    point = A.point(A.voltages[I_E])
    assert point["V_ref"] == 0
    c_B = Fraction(case.block.c_B_mM)
    modes = case.block.modes
    expected = (sum(Fraction(m.weight) * Fraction(m.k0_mM) / (c_B + Fraction(m.k0_mM))
                    for m in modes) / sum(Fraction(m.weight) for m in modes))
    assert writer.rel(Fraction(point["u"]), expected) < 1e-115


def test_block_senses():
    # An anion from the outside (B4): u is about 0.989 at -80 mV, the registration's probe
    # figure; it would be about 0.011 without sgn(z_B).
    A = route_a.CaseA(SPEC, CASES["B4_anion_effective"])
    assert abs(A.point(Decimal("-0.0800"))["u"] - Decimal("0.989")) < Decimal("5e-4")
    # A cation from the outside is relieved by depolarisation; one from the inside binds more
    # tightly as V rises (LAWS.md 3).
    for case_id, rising in (("B3_divalent_outside_E1", True), ("B2_woodhull_inside", False)):
        A = route_a.CaseA(SPEC, CASES[case_id])
        low, high = (A.point(Decimal(v))["u"] for v in ("-0.0800", "0.0200"))
        assert (high > low) == rising


def test_counts_scale_the_flux_and_leave_u():
    _, b1 = full_a("B1_two_modes_E1")
    _, c1 = full_a("C1_abundance_doubled")
    _, c2 = full_a("C2_units_declared")
    _, c2_doubled = full_a("C2_units_doubled")
    assert c2 == b1  # a = N/(A rho_ref) = 1
    assert c2_doubled == c1  # a = 2
    assert c1["u"] == b1["u"] and c1["theta"] == b1["theta"]
    for key in ("J_free", "I_free", "dI_free_dV", "J_blocked", "I_blocked", "dI_blocked_dV",
                "dJ_blocked_dc_o", "dJ_blocked_dc_i"):
        for doubled, single in zip(c1[key], b1[key], strict=True):
            assert writer.rel(Fraction(doubled), 2 * Fraction(single)) < 1e-115


def _check_strings(doc: dict) -> None:
    n = doc["voltage_count"]
    for name in writer.NAMES.values():
        if name not in doc:
            continue
        arrays = doc[name] if name in ("theta_k", "one_minus_theta_k") else [doc[name]]
        for values in arrays:
            assert len(values) == n, name
            for text in values:
                Decimal(text)
                if name not in EXACT_ARRAYS and text != "0":
                    mantissa = text.lstrip("-").split("e")[0].replace(".", "")
                    assert len(mantissa) == writer.OUT_DIGITS, (name, text)


@pytest.mark.skipif(not RESULT_FILES, reason="results/ is not generated yet")
def test_committed_results_are_what_the_writer_produces():
    assert {path.stem for path in RESULT_FILES} == set(CASES)
    for path in RESULT_FILES:
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["case_id"] == path.stem and doc["inputs"]["invented"] is False
        assert doc["voltage_count"] == len(doc["voltages_V"]) == SPEC.grid_count + 3
        assert doc["method"]["within_declared_accuracy"] is True
        assert doc["provenance"]["dirty_paths"] == []
        assert ("u" in doc) and (("theta_k" in doc) == (CASES[path.stem].block is not None))
        _check_strings(doc)
    for case_id in ("B1_two_modes_E1", "Z1_zero_blocker"):
        A, out = full_a(case_id)
        doc = json.loads((HERE / "results" / f"{case_id}.json").read_text(encoding="utf-8"))
        for name, values in writer.value_arrays(A, out).items():
            assert doc[name] == values, name
        assert doc["voltages_V"] == [str(v) for v in A.voltages]
        assert doc["E_ion_V"] == str(A.E_ion)
        assert doc["u_at_reversal"] == writer.fmt(out["u"][I_E])


def _skeleton(value):
    """The layout of a JSON value: keys, value types, and list lengths."""
    if isinstance(value, dict):
        return {key: _skeleton(item) for key, item in value.items()}
    if isinstance(value, list):
        return ["list", len(value), _skeleton(value[0]) if value else None]
    return type(value).__name__


@pytest.mark.skipif(not (RESULT_FILES and SAMPLE_FILES), reason="outputs not generated yet")
def test_format_sample_has_the_results_layout_and_is_marked_invented():
    def load(folder: str, name: str) -> dict:
        return json.loads((HERE / folder / f"{name}.json").read_text(encoding="utf-8"))

    assert {path.stem for path in SAMPLE_FILES} == {case.id for case in SAMPLE_SPEC.cases}
    pairs = (("INVENTED_free", "P2_K_unequal"),
             ("INVENTED_free_equal", "P1_K_equal"),  # E_ion = 0, exact zeros, the line
             ("INVENTED_zero_blocker_three_modes", "Z1_zero_blocker"),  # three modes, theta 0
             ("INVENTED_two_modes_reversal", "B1_two_modes_E1"),
             ("INVENTED_units_one_mode", "B2_woodhull_inside"))
    for sample_name, real_name in pairs:
        sample, real = load("format-sample", sample_name), load("results", real_name)
        assert sample["inputs"]["invented"] is True and "INVENTED" in sample["inputs"]["statement"]
        sample_shape, real_shape = _skeleton(sample), _skeleton(real)
        if sample["declared"]["units"] is not None:
            units_shape = _skeleton(load("results", "C2_units_declared")["declared"]["units"])
            assert sample_shape["declared"].pop("units") == units_shape
            real_shape["declared"].pop("units")
        assert sample_shape == real_shape, sample_name
        _check_strings(sample)
    A, out = full_a("INVENTED_two_modes_reversal", SAMPLE_SPEC)
    sample = load("format-sample", "INVENTED_two_modes_reversal")
    for name, values in writer.value_arrays(A, out).items():
        assert sample[name] == values, name


def test_no_engine_module_is_imported():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
