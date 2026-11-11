"""Parity post-processing tools (no BETSE, no Cells run; synthetic inputs).

network_cases (case preparation by exact replacements), step_order (observed order and the
step-term rule), parity_recipes (the pinned-method recipe), parity_protocols (protocol
assembly and discrimination) and parity_margins (judged margins). Their reproduction of the
P4b evidence (parity-p4b-channels-20261110-01 derive-01/02, judged-01) was checked when they
were landed.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from validation.betse import (
    network_cases,
    parity_margins,
    parity_protocols,
    parity_recipes,
    step_order,
)

ROOT = Path(__file__).resolve().parents[2]
IONS = ["Na", "K", "Cl", "Ca", "P", "M"]
BASE_YAML = """general network:

  implement network: False  # Turn the entire network on (True) or off (False)

  biomolecules:  # specify the properties of any number of auxiliary chemicals

    - name: 'X'
      Dm: 0.0

  #-------------------------------------
  reactions:

  channels:

    - name: Nav
      channel class: Na
      init active: False

    # available channel types for each channel class:
tissue:
        Dm_Na: 2.0e-18     # Na+ membrane diffusion constant [m2/s]
"""
KIR = {"name": "Kir", "class": "K", "type": "Kir2p1", "max_dm": 7.5e-17, "init_active": True}
NAV = {"name": "Nav", "class": "Na", "type": "Nav1p2", "max_dm": 1.875e-15, "init_active": False}
LOW = [["        Dm_Na: 2.0e-18     #", "        Dm_Na: 4.0e-19     #"]]


def test_cases_are_exact_replacements_of_the_base_config(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "sim_config.yaml").write_text(BASE_YAML)
    (base / "INITS").mkdir()
    seed = tmp_path / "world_1.betse.gz"
    seed.write_bytes(b"seed")
    spec = {
        "channels": {"KIR": KIR, "NAV": NAV},
        "worlds": {"low": LOW},
        "cases": {
            "c-dense": {
                "channels": ["KIR", "NAV"],
                "world": "low",
                "leave_one_out": {"kir2p1": ["NAV"], "all": []},
            }
        },
    }
    written = network_cases.prepare_all(
        spec, tmp_path / "ref", base=base, seed=seed, python=sys.executable
    )
    assert written == {"c-dense": ["c-dense", "c-no-kir2p1-dense", "c-no-all-dense"]}
    ref = tmp_path / "ref"
    assert (ref / "c-dense.cases").read_text().split() == written["c-dense"]
    case = (ref / "c-dense/inputs/config/sim_config.yaml").read_text()
    assert "  implement network: True   #" in case
    assert network_cases.NO_BIOMOLECULES in case and "name: 'X'" not in case
    assert network_cases.block([KIR, NAV]) in case and "init active: False\n\n    #" in case
    assert "Dm_Na: 4.0e-19" in case and "#----" in case and "  reactions:" in case
    off = (ref / "c-no-all-dense/inputs/config/sim_config.yaml").read_text()
    assert off == BASE_YAML.replace("2.0e-18     #", "4.0e-19     #")  # network stays off
    assert (ref / "c-no-all-dense/inputs/config/INITS/world_1.betse.gz").read_bytes() == b"seed"
    record = json.loads((ref / "c-dense/inputs/config.prepare.json").read_text())
    assert record["status"] == "complete"
    with pytest.raises(ValueError, match="exactly once"):
        network_cases.section(BASE_YAML + BASE_YAML, network_cases.CHANNELS)


def rows(volt, cell, ecm):
    """protocol_tolerances.rows_terms-shaped values for both phases."""
    return {
        p: {
            "voltage": volt,
            "cell_concentration": {i: cell.get(i, 1e-6 * volt) for i in IONS},
            "ecm_concentration": {i: ecm for i in IONS},
        }
        for p in ("init", "sim")
    }


def test_order_and_the_step_term_rule():
    assert step_order.order(10.0, 1.0) == pytest.approx(1.0, abs=1e-12)
    assert step_order.order(99.0, 0.99) == pytest.approx(2.0, abs=1e-9)
    assert step_order.order(0.0, 1.0) is None
    first = step_order.evaluate(rows(10.0, {}, 1.0), rows(1.0, {}, 1.0), rows(11.0, {}, 1.0))
    assert first["rule_outcome"] == step_order.CLEAN and not first["outside_band_or_undetermined"]
    assert "every P4b case" not in first["rule_outcome"]
    entry = first["phases"]["sim"]["voltage"]
    assert entry["step_term_10_over_9_dt1_dt10"] == pytest.approx(100 / 9)
    # Immobile P and the ECM do not decide; a second-order cell ion does.
    p_only = step_order.evaluate(
        rows(10.0, {"P": 0.0}, 99.0), rows(1.0, {"P": 0.0}, 0.99), rows(11.0, {}, 1.0)
    )
    assert p_only["rule_outcome"] == step_order.CLEAN
    second = step_order.evaluate(
        rows(10.0, {"K": 99e-6}, 1.0), rows(1.0, {"K": 0.99e-6}, 1.0), rows(11.0, {}, 1.0)
    )
    assert second["rule_outcome"] == step_order.FALLBACK
    assert second["outside_band_or_undetermined"] == [
        "init/cell_concentration/K",
        "sim/cell_concentration/K",
    ]


@pytest.mark.parametrize("outcome", [step_order.CLEAN, step_order.FALLBACK])
def test_recipe_follows_the_order_rule(tmp_path, outcome):
    check = tmp_path / "order.json"
    check.write_text(json.dumps({"rule_outcome": outcome}))
    r = parity_recipes.recipe(tmp_path, "c-dense", check)
    terms = r["terms"]
    at = "dt_over_10" if outcome == step_order.CLEAN else "dt_over_100"
    if outcome == step_order.CLEAN:
        assert terms["betse_init_step"]["pairs"] == ["betse_dt_vs_dt_over_10"]
        assert terms["betse_init_step"]["scale"] == pytest.approx(10 / 9)
    else:
        assert terms["betse_init_step"] == {
            "budget": str(tmp_path / "emulator/c-dense_difference_budget.json"),
            "pairs": ["betse_dt_vs_dt_over_100"],
        }
    assert terms[f"conservative_compact_ecm_faces_at_{at}"]["pairs"] == [
        f"compact_ecm_faces_at_{at}"
    ]
    assert terms["physical_time_gate_and_no_concentration_lag"]["pairs"][1] == (
        f"gate_once_no_lag_at_{at}"
    )
    assert len(terms["cells_exterior_field_propagated"]["pairs"]) == 6
    assert "field_both_D_half" in terms["cells_exterior_field_propagated"]["pairs"]
    assert terms["cells_numerics_ars222"]["scale"] == pytest.approx(4 / 3)
    assert r["step_order_rule"]["outcome"] == outcome
    assert not any("x_ext" in k.lower() for k in terms)


def observables(volt, cell):
    """betse_pair_terms / difference-budget observable rows."""
    ion_rows = {i: {"max": cell[i], "final_max": cell[i]} for i in IONS}
    return {
        "vm_time": {"max": volt, "final": {"max": volt}},
        "vm_ave_time": {"max": volt, "final": {"max": volt}},
        "cc_time": {"by_ion": ion_rows},
        "cc_env_time_interior": {"by_ion": {i: {"max": 1e-6, "final_max": 1e-6} for i in IONS}},
    }


def test_protocol_assembly_and_discrimination(tmp_path):
    tol = {
        "voltage": {"init": 1e-3, "sim": 1e-5},
        "cell_concentration": {
            p: {"by_ion": {i: (1e-12 if i == "P" else 1e-5) for i in IONS}} for p in ("init", "sim")
        },
        "ecm_concentration": {
            p: {"by_ion": {i: (1e-12 if i == "P" else 1e-4) for i in IONS}} for p in ("init", "sim")
        },
    }
    derived = {
        "tolerance": tol,
        "method": "3 x sum",
        "recipe_path": "recipe.json",
        "terms": {"b": {}, "a": {}},
        "largest_term": {},
        "sums_before_margin": {},
        "provisional_terms": [],
        "recipe": {"step_order_rule": {"outcome": step_order.CLEAN}},
    }
    (tmp_path / "derived.json").write_text(json.dumps(derived))
    cell = {i: (0.0 if i == "P" else 2e-5) for i in IONS} | {"Ca": 5e-6}
    effect = {"phases": {"init": {"observables": observables(5e-3, cell)},
                         "sim": {"observables": observables(5e-6, cell)}}}  # fmt: skip
    (tmp_path / "option.json").write_text(json.dumps(effect))
    run = {"phases": {"init": {"channels": [
        {"name": "Kir", "active": True, "m_range": [0, 1], "gate_lag_max_abs": [0.1, 0.2],
         "open_fraction_lag_max_rel": 0.05},
        {"name": "Nav", "active": False, "gate_lag_max_abs": [0.6, 0.0]},
        {"name": "K_Leak", "active": True}]}}}  # fmt: skip
    (tmp_path / "run.json").write_text(json.dumps(run))
    extract = tmp_path / "case/extract"
    extract.mkdir(parents=True)
    for phase, (lo, hi) in (("init", (-0.09, -0.004)), ("sim", (-0.0912, -0.0905))):
        np.savez(extract / f"{phase}_history.npz", vm_time=np.array([[lo, hi]]))
        np.savez(extract / f"{phase}_final.npz", vm=np.array([lo]))
    case = {
        "id": "physical-c-dense",
        "betse_case": "c-dense",
        "template": str(ROOT / "validation/betse/protocols/physical_p4_kv1p5_kleak_dense.json"),
        "derived": str(tmp_path / "derived.json"),
        "purpose": "test",
        "primary": "kir2p1_given_rest (BETSE)",
        "options": {"kir2p1_given_rest (BETSE)": {"file": str(tmp_path / "option.json")}},
        "laws": {"kir2p1": "kir2p1_mh2@1"},
        "gate_lag_run": str(tmp_path / "run.json"),
        "coverage_case": str(tmp_path / "case"),
        "cells_run": {"note": "n"},
        "derivation": {"field_terms": "propagated"},
        "world_change": {"factor": 0.2},
        "limits": ["Covered: Kir2.1 {coverage}."],
        "notes": ["x"],
        "status": "PROPOSED",
    }
    proto = parity_protocols.build(case)
    ratio = proto["discrimination_by_channel"]["kir2p1"]["effect_over_tolerance"]
    assert ratio["init"]["voltage"] == pytest.approx(5.0)
    assert ratio["sim"]["voltage"] == pytest.approx(0.5)
    assert ratio["init"]["cell_concentration"]["Na"] == pytest.approx(2.0)
    assert "P" not in ratio["init"]["cell_concentration"]
    nd = proto["discrimination_by_channel"]["kir2p1"]["non_discriminating"]
    assert "sim/voltage" in nd and "init/cell_concentration/Ca" in nd
    assert "init/voltage" not in nd and proto["non_discriminating"] == nd
    assert proto["discrimination_ratio"]["effect"] == "kir2p1_given_rest (BETSE)"
    assert proto["tolerance_classes"] == {proto["verdict_class"]: tol}
    assert proto["tolerance_derivation"]["terms"] == ["a", "b"]
    assert proto["tolerance_derivation"]["field_terms"] == "propagated"
    assert proto["tolerance_derivation"]["step_order_rule"]["outcome"] == step_order.CLEAN
    assert set(proto["gate_lag"]["phases"]["init"]) == {"Kir"}  # inactive and leaks dropped
    assert proto["voltage_coverage_mV"]["init"] == pytest.approx([-90.0, 0.0])
    assert proto["limits"] == [
        "Covered: Kir2.1 INIT -90.0 to 0.0 mV (from 0 V), SIM -91.2 to -90.5 mV."
    ]
    assert proto["world_change"] == {"factor": 0.2} and proto["cells_run"]["note"] == "n"
    assert proto["cells_run"]["model"] == "resolved_pump_tissue@3"  # template kept
    derived["provisional_terms"] = ["t"]
    (tmp_path / "derived.json").write_text(json.dumps(derived))
    with pytest.raises(ValueError, match="provisional"):
        parity_protocols.build(case)


def test_margins_per_option():
    protocol = {
        "verdict_class": "v",
        "discrimination_by_channel": {
            "kir2p1": {
                "effect_over_tolerance": {
                    "init": {"voltage": 20.0, "cell_concentration": {"K": 0.5}},
                    "sim": {"voltage": 300.0, "cell_concentration": {"K": 6.0}},
                },
                "non_discriminating": ["init/cell_concentration/K"],
            }
        },
    }

    def obs(volt, k):
        return {
            "vm_time": {"classes": {"v": {"tolerance": 1e-3}},
                        "worst_error_in_tolerance_kind": volt},
            "cc_time": {"classes": {"v": {"by_ion": {
                "K": {"worst": k, "tolerance": 1e-5}, "P": {"worst": 0.0, "tolerance": 1e-12}}}}},
            "venv_time": {"judged": False, "classes": {"v": {"tolerance": 1e-3}}},
        }  # fmt: skip

    result = {"verdict": "pass", "refusals": [],
              "phases": {"init": {"observables": obs(2e-4, 1e-6)},
                         "sim": {"observables": obs(1e-4, 4e-6)}}}  # fmt: skip
    m = parity_margins.margins(result, protocol)
    assert m["worst"]["item"] == "sim/cell_concentration/K"
    assert m["worst"]["error_over_tolerance"] == pytest.approx(0.4)
    assert set(m["error_over_tolerance"]) == {
        "init/voltage", "sim/voltage", "init/cell_concentration/K", "sim/cell_concentration/K"
    }  # fmt: skip
    kir = m["discriminating_margins"]["kir2p1"]
    assert set(kir) == {"init/voltage", "sim/voltage", "sim/cell_concentration/K"}
    assert kir["init/voltage"]["effect_over_error"] == pytest.approx(20 * 1e-3 / 2e-4)
    assert kir["sim/cell_concentration/K"]["margin_tolerance_over_error"] == pytest.approx(2.5)


def test_backend_variant_adds_terms_and_never_tightens(tmp_path, monkeypatch):
    from validation.betse import backend_variant as bv
    from validation.betse import protocol_tolerances as pt

    base = json.loads(
        (ROOT / "validation/betse/protocols/physical_p4b_nav_kleak_dense.json").read_text()
    )
    path = tmp_path / "base.json"
    path.write_text(json.dumps(base))
    label = base["verdict_class"]
    old = base["tolerance_classes"][label]
    sums = base["tolerance_derivation"]["sums_before_margin"]

    def zero():
        return {
            p: {
                "voltage": 0.0,
                "cell_concentration": {i: 0.0 for i in IONS},
                "ecm_concentration": {i: 0.0 for i in IONS},
            }
            for p in ("init", "sim")
        }

    big = zero()
    big["sim"]["voltage"] = 10 * sums["voltage"]["sim"]  # widens SIM Vm
    big["init"]["cell_concentration"]["Na"] = 1e-30  # far below rounding: no change
    terms = {"cpu_vs_l4": big, "l4_run_to_run": zero()}
    monkeypatch.setattr(pt, "Context", lambda case, base: None)
    monkeypatch.setattr(pt, "term", lambda ctx, spec: terms[spec["layouts"][0]])
    spec = {
        "case": "unused",
        "backend": "gpu (L4)",
        "terms": {n: {"layouts": [n, "b"], "role": n} for n in terms},
        "notes": ["extra"],
    }
    out = bv.variant(spec, path)
    tol = out["tolerance_classes"][label]
    assert out["id"] == base["id"] + "-l4" and out["cells_run"]["backends"] == ["gpu (L4)"]
    assert "optional_repeat" not in out["cells_run"]
    assert tol["voltage"]["sim"] == pt.up1(3 * 11 * sums["voltage"]["sim"])
    assert tol["voltage"]["init"] == old["voltage"]["init"]
    assert tol["cell_concentration"]["init"] == old["cell_concentration"]["init"]
    bt = out["tolerance_derivation"]["backend_terms"]
    assert bt["changed"] == ["sim/voltage"] and bt["registered_tolerance_reproduced_from_sums"]
    assert set(out["tolerance_derivation"]["terms"]) >= set(terms)
    factor = old["voltage"]["sim"] / tol["voltage"]["sim"]
    channel = out["discrimination_by_channel"]["nav1p2"]["effect_over_tolerance"]
    registered = base["discrimination_by_channel"]["nav1p2"]["effect_over_tolerance"]
    assert channel["sim"]["voltage"] == pytest.approx(registered["sim"]["voltage"] * factor)
    assert out["discrimination_ratio"]["sim"]["voltage"] == pytest.approx(channel["sim"]["voltage"])
    assert out["base_protocol"]["id"] == base["id"] and out["notes"][-1] == "extra"
    assert base["tolerance_classes"][label] == old  # input untouched
