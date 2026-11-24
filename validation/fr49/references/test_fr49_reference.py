"""Self-check of the FR-49 code-blind reference. No engine import; it compiles no world.

    python -m pytest -q -p no:cacheprovider validation/fr49/references/test_fr49_reference.py

About 4 s on one core, most of it World L's Radau solve. It checks the routes against each other
(World L's two matrix-exponential forms, World B's closed form against the Taylor integrator, C2's
two root formulations), the laws' identities and exact ends, and that the committed results/ and
format-sample/ files are what the writer produces.
"""

from __future__ import annotations

import decimal
import json
import sys
from decimal import Decimal
from itertools import pairwise
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fr49_exact as exact  # noqa: E402
import fr49_ode as ode  # noqa: E402
import fr49_reference as writer  # noqa: E402
import fr49_spec  # noqa: E402

SPEC = fr49_spec.load()
SAMPLE_SPEC = fr49_spec.load(writer.SAMPLE_SPEC)
RESULTS = {w: HERE / "results" / f"{w}.json" for w in fr49_spec.WORLDS}
SAMPLES = {w: HERE / "format-sample" / f"INVENTED_{w}.json" for w in fr49_spec.WORLDS}
HAVE_RESULTS = all(p.exists() for p in RESULTS.values())
HAVE_SAMPLES = all(p.exists() for p in SAMPLES.values())
rel = writer.rel


@pytest.fixture(autouse=True)
def _high_precision():
    """The tests' own decimal arithmetic runs at 100 digits, not the default 28."""
    with decimal.localcontext(exact.context(100)):
        yield


def _L(spec=SPEC):
    return exact.world_L_expm(spec.L)


def test_world_L_matrix_exponential_forms_agree():
    primary, eigen = _L(), exact.world_L_sylvester(SPEC.L)
    for name in writer.L_QUANTITIES:
        assert all(rel(a, b) < 1e-60 for a, b in zip(primary[name], eigen[name], strict=True))
    times = exact.sample_times(SPEC.L.samples)
    t1 = Decimal(SPEC.L.t1)
    for i, t in enumerate(times):
        assert (primary["x_O"][i] == 0 and primary["x_C"][i] == 0) == (t <= t1)
        assert rel(primary["base_O"][i] + primary["x_O"][i], primary["n_O"][i]) < 1e-65
        assert 0 <= primary["share_x_C"][i] < 1


def test_world_L_radau_agrees():
    primary = _L()
    radau = ode.world_L_radau(SPEC.L)
    for k, name in enumerate(("n_O", "n_C", "x_O", "x_C")):
        assert all(rel(a, b) < 1e-13 for a, b in zip(primary[name], radau[k], strict=True))


def test_world_B_closed_forms():
    out = exact.world_B_exact(SPEC)
    once = out["once"]
    assert out["branch"] == "b < 0"  # the registration's evidence: the second branch
    assert rel(once["B*"], once["B1"]) < 1e-55
    # the equilibrium: binding equals unbinding at B*
    c, R = once["c*"], once["S"] - once["B*"]
    k_on, k_off = Decimal(SPEC.B.k_on), Decimal(SPEC.B.k_off)
    assert rel(k_on * c * R, k_off * once["B*"]) < 1e-55
    assert out["B"][0] == 0
    assert all(b2 > b1 for b1, b2 in pairwise(out["B"]))
    for B, n_L in zip(out["B"], out["n_L"], strict=True):
        assert rel(B + n_L, once["L_T"]) < 1e-58
    assert abs(1 / float(once["lambda"]) - 15.8) < 0.05  # the registration's tau


def test_world_B_once_values_by_the_second_route():
    once = exact.world_B_exact(SPEC)["once"]
    check = exact.world_B_once_check(SPEC)
    assert all(rel(once[k], check[k]) < 1e-55 for k in writer.B_ONCE)
    assert rel(check["B2"] - check["B1"], check["d"]) < 1e-55  # B2 - B1 = d
    assert rel(ode.capacity(SPEC.B.sites, SPEC.sites_per_fmol), check["S"]) < 1e-15


def test_taylor_integrator_matches_world_B():
    out = exact.world_B_exact(SPEC)
    once = out["once"]
    times = exact.sample_times(SPEC.B.samples)[:7]  # to 30 s
    states = exact.binding_taylor(SPEC.B.V_C, once["S"], [(SPEC.B.k_on, SPEC.B.k_off,
                                                           str(once["L_T"]))],
                                  [SPEC.B.B0], times, writer.TAYLOR_STEP["B"])
    assert all(rel(s[0], b) < 1e-45 for s, b in zip(states, out["B"], strict=False))


def test_c2_root_two_ways():
    root = exact.c2_root(SPEC)
    newton = exact.c2_root_newton2(SPEC, [2e-5, 1e-4])
    S, V_C = root["S"], Decimal(SPEC.C2.V_C)
    D = 1 + sum(root["c"][j] / root["K"][j] for j in range(2))
    for j, ligand in enumerate(SPEC.C2.ligands):
        lhs = V_C * root["c"][j] + S * (root["c"][j] / root["K"][j]) / D
        assert rel(lhs, Decimal(ligand.total)) < 1e-60
        assert rel(root["c"][j], newton["c"][j]) < 1e-60
        assert rel(root["B"][j], newton["B"][j]) < 1e-60
    assert rel(root["R"], S - root["B"][0] - root["B"][1]) < 1e-60


def test_c2_transient_start_matches_radau():
    root = exact.c2_root(SPEC)
    times = exact.sample_times(SPEC.C2.samples)[:3]  # to 40 s
    ligands = [(g.k_on, g.k_off, g.total) for g in SPEC.C2.ligands]
    states = exact.binding_taylor(SPEC.C2.V_C, root["S"], ligands, list(SPEC.C2.B0), times,
                                  writer.TAYLOR_STEP["C2"])
    radau = ode.c2_integrate(SPEC, "Radau")
    for i, state in enumerate(states):
        for j in range(2):
            assert rel(state[j], radau[j][i]) < 1e-11


def test_c1_wash_arithmetic():
    well = exact.c1_wash(SPEC.C1)
    f = Decimal(SPEC.C1.wash_fraction)
    assert well["x_W_after"] == (1 - f) * Decimal(SPEC.C1.x_W0)  # the buffer carries no x
    assert well["b_W_after"] == ((1 - f) * Decimal(SPEC.C1.b_W0)
                                 + f * Decimal(SPEC.C1.V_W) * Decimal(SPEC.C1.buffer_mM))
    exact_check = exact.c1_wash_rational(SPEC.C1)
    assert all(rel(well[k], exact_check[k]) < 1e-55 for k in writer.WELL)
    assert exact_check["share_x_W_after"] + exact_check["share_b_W_after"] == 1


def _strings(doc: dict, names) -> None:
    for name in names:
        for text in doc[name]:
            Decimal(text)
            if text != "0":
                mantissa = text.lstrip("-").split("e")[0].replace(".", "")
                assert len(mantissa) == writer.OUT_DIGITS, (name, text)


@pytest.mark.skipif(not HAVE_RESULTS, reason="results/ is not generated yet")
def test_committed_results_are_what_the_writer_produces():
    docs = {w: json.loads(p.read_text(encoding="utf-8")) for w, p in RESULTS.items()}
    for world, doc in docs.items():
        assert doc["world"] == world and doc["inputs"]["invented"] is False
        assert doc["method"]["within_declared_accuracy"] is True
        assert doc["provenance"]["dirty_paths"] == []
    _strings(docs["L"], writer.L_QUANTITIES)
    _strings(docs["B"], writer.B_QUANTITIES)
    _strings(docs["C1"], writer.L_QUANTITIES)
    _strings(docs["C2"], writer.C2_QUANTITIES)
    primary = _L()
    for name in writer.L_QUANTITIES:
        assert docs["L"][name] == [writer.fmt(v) for v in primary[name]] == docs["C1"][name]
    B = exact.world_B_exact(SPEC)
    for name in writer.B_QUANTITIES:
        assert docs["B"][name] == [writer.fmt(v) for v in B[name]]
    assert docs["B"]["once"] == {k: writer.fmt(B["once"][k]) for k in writer.B_ONCE}
    well = exact.c1_wash(SPEC.C1)
    assert docs["C1"]["well"] == {k: writer.fmt(well[k]) for k in writer.WELL}
    root = exact.c2_root(SPEC)
    times = exact.sample_times(SPEC.C2.samples)[:3]
    ligands = [(g.k_on, g.k_off, g.total) for g in SPEC.C2.ligands]
    states = exact.binding_taylor(SPEC.C2.V_C, root["S"], ligands, list(SPEC.C2.B0), times,
                                  writer.TAYLOR_STEP["C2"])
    for i, state in enumerate(states):
        assert docs["C2"]["B1"][i] == writer.fmt(state[0])
        assert docs["C2"]["B2"][i] == writer.fmt(state[1])
    assert docs["C2"]["once"]["B1*"] == writer.fmt(root["B"][0])


def _skeleton(value):
    """The layout of a JSON value: keys, value types, and list lengths."""
    if isinstance(value, dict):
        return {key: _skeleton(item) for key, item in value.items()}
    if isinstance(value, list):
        return ["list", len(value), _skeleton(value[0]) if value else None]
    return type(value).__name__


@pytest.mark.skipif(not (HAVE_RESULTS and HAVE_SAMPLES), reason="outputs not generated yet")
def test_format_sample_has_the_results_layout_and_is_marked_invented():
    for world in fr49_spec.WORLDS:
        real = json.loads(RESULTS[world].read_text(encoding="utf-8"))
        sample = json.loads(SAMPLES[world].read_text(encoding="utf-8"))
        assert sample["inputs"]["invented"] is True
        assert "INVENTED" in sample["inputs"]["statement"]
        assert _skeleton(sample) == _skeleton(real), world
    sample_L = json.loads(SAMPLES["L"].read_text(encoding="utf-8"))
    primary = _L(SAMPLE_SPEC)
    assert sample_L["x_C"] == [writer.fmt(v) for v in primary["x_C"]]


def test_no_engine_module_is_imported():
    assert not any(name == "cells" or name.startswith("cells.") for name in sys.modules)
