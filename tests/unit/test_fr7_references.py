"""FR-7's registered references (R-chain, R-clear) stay as registered, and have power.

- the interface files parse, and inputs.json equals its generator;
- every band recomputes from the stored values, bounds and declared rules;
- every plant margin recomputes from the stored plant values; the zero-power list is exactly the
  compared rows a plant moves by under the declared margin, and V's compared rows follow V's rule;
- every applicable plant has power in every world, and R-clear's plants on their cases;
- a small deterministic subset regenerates: the template's closed forms, an m = 0 world's chain by
  quadrature, R-clear on every case, and the cell model against R-cell at a held N;
- nothing here imports the engine.

About 5 s. The full regeneration is test_fr7_references_regeneration.py (minutes; tier 3).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from validation.fr7.references import chain, clearance, design, worlds

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def reg():
    inputs = json.loads(worlds.INPUTS.read_text())
    return dict(inputs=inputs,
                rows=json.loads(design.ROWS_FILE.read_text()),
                plants=json.loads(design.PLANTS_FILE.read_text()),
                zero=json.loads(design.ZERO_FILE.read_text()),
                clear=json.loads(design.CLEAR_FILE.read_text()))


def test_the_inputs_equal_their_generator(reg):
    assert worlds.INPUTS.read_text() == worlds.text()
    assert set(reg["rows"]["worlds"]) == set(reg["inputs"]["worlds"])
    for doc in ("rows", "plants", "zero", "clear"):
        assert reg[doc]["registered"] == reg["inputs"]["registered"]


def test_bands_recompute_from_the_stored_references(reg):
    for name, w in reg["rows"]["worlds"].items():
        for k, q in w["quantities"].items():
            if "band" not in q:
                assert q["cls"] == "information", (name, k)
                continue
            rule = design.rule_of(reg["inputs"], k)
            fresh = design.band(rule, q["value"], q["bound"])
            assert np.array_equal(fresh, np.array(q["band"])), (name, k)
            assert np.all(np.array(q["bound"]) < 0.01 * np.array(q["band"])), (name, k)


def test_margins_zero_power_and_the_voltage_rule(reg):
    m_min = reg["inputs"]["power"]["margin"]
    for name, w in reg["rows"]["worlds"].items():
        qs, plants, zero = w["quantities"], reg["plants"]["worlds"][name]["plants"], \
            reg["zero"]["worlds"][name]
        v_ok = None
        for pname, p in plants.items():
            if not p["applicable"]:
                assert pname in zero["inapplicable"]
                continue
            listed, quiet = zero["rows_without_power"][pname], zero["unaffected"][pname]
            for k, pv in p["values"].items():
                ref, b = np.array(qs[k]["value"]), np.array(qs[k]["band"])
                m = np.abs(np.array(pv) - ref) / b
                assert np.allclose(m, p["margin"][k], rtol=1e-12, atol=0), (name, pname, k)
            status = {k: qs[k]["status"] for k in p["margin"]}
            kinds = design.zero_power_kinds(pname, p["margin"], status, list(p["margin"]), m_min)
            assert set(quiet) == {k for k, v in kinds.items() if v == "unaffected"}, (name, pname)
            assert set(listed) == {k for k, v in kinds.items() if v == "rows"}, (name, pname)
            for k, rows_listed in listed.items():
                expect = [[t, float(mm)] for t, mm, st in zip(
                    w["rows_s"], p["margin"][k], qs[k]["status"], strict=True)
                    if st == "compared" and mm < m_min]
                assert rows_listed == expect, (name, pname, k)
            if pname in design.MATERIAL_PLANTS and pname not in design.NO_CELL:
                ok = np.array(p["margin"]["V_V"]) >= m_min
                v_ok = ok if v_ok is None else v_ok & ok
        n = len(w["rows_s"])
        status = ["compared" if (r > 0 and v_ok[r]) else "information" for r in range(n)]
        assert qs["V_V"]["status"] == status, name
        # every other compared row has at least one plant with power on it: the non-core rows
        # are compared only there, and the core (units, conductance, material) is covered
        margins = {p: v["margin"] for p, v in plants.items() if v["applicable"]}
        union = design.power_union(margins, [k for k in qs if "band" in qs[k]], n, m_min)
        for k in design.NON_CORE:
            if "band" in qs[k]:
                expect = ["compared" if (r > 0 and union[k][r]) else "information"
                          for r in range(n)]
                assert qs[k]["status"] == expect, (name, k)
        for k, q in qs.items():
            if "band" in q and k not in design.NON_CORE:
                assert all(union[k][r] for r in range(n) if q["status"][r] == "compared"), \
                    (name, k)
        assert zero["core_rows_without_any_plant"] == {}, name


def test_every_applicable_plant_has_power(reg):
    m_min = reg["inputs"]["power"]["margin"]
    for name, w in reg["rows"]["worlds"].items():
        plants = reg["plants"]["worlds"][name]["plants"]
        templated = name != "W6_no_template_m3_t60"
        for pname, p in plants.items():
            if not p["applicable"]:
                continue
            hits = {k: sum(1 for mm, st in zip(m, w["quantities"][k]["status"], strict=True)
                           if st == "compared" and mm >= m_min) for k, m in p["margin"].items()}
            assert max(hits.values()) > 0, (name, pname)
            n_rows = len(w["rows_s"]) - 1
            if pname in ("nu_off_by_one", "cu_without_1e-15", "route_on_precursor_clearance",
                         "removal_on_increment_only"):
                assert hits["N_units"] >= 0.8 * n_rows, (name, pname, hits["N_units"])
            if pname == "factor_held_from_step_start":
                assert templated and hits["n_P_fmol"] + hits["N_units"] >= 0.5 * n_rows, \
                    (name, hits)
            if pname == "cu_without_1e-15" or pname == "nu_off_by_one":
                assert hits["total_fmol"] >= 0.8 * n_rows, (name, pname)
        if templated:
            assert sum(st == "compared" for st in w["quantities"]["V_V"]["status"]) \
                >= 0.8 * (len(w["rows_s"]) - 1), name
    power = reg["clear"]["synthetic_power"]
    assert "RC2_releasing_compartment" in power["compartment_left_out"]
    assert "RC5_compartment_stops_releasing" in power["sealed_compartment_counted"]
    assert "RC3_recrossing" in power["first_crossing_no_fall_back"]
    assert "RC4_not_cleared" in power["end_time_if_not_cleared"]
    assert "RC7_threshold_equality" in power["strict_inequality"]
    assert len(power["threshold_on_the_factor"]) >= 4


def test_closed_forms_and_one_quadrature_regenerate(reg):
    inputs = reg["inputs"]
    for name, w in reg["rows"]["worlds"].items():
        world = chain.World(inputs, name)
        t = np.array(w["rows_s"])
        q = w["quantities"]
        for k, fresh in (("n_T_fmol", world.template.amount(t)), ("D", world.drive(t)),
                         ("F_T", world.factor(t))):
            stored = np.array(q[k]["value"])
            assert np.all(np.abs(fresh - stored) <= np.array(q[k]["bound"]) + 1e-300), (name, k)
    name = "W1_dose_m0_t30"
    world = chain.World(inputs, name)
    fresh = chain.reference_chain(world, world.rows, panel_s=chain.PANEL_S / 2.0)
    q = reg["rows"]["worlds"][name]["quantities"]
    for k, key in (("n_P_fmol", "n_P"), ("N_units", "N"), ("W_fmol", "W"), ("R_units", "R"),
                   ("total_fmol", "total")):
        stored = np.array(q[k]["value"])
        assert np.all(np.abs(fresh[key] - stored) <= 1e-12 * np.abs(stored).max()), k


def test_clearance_regenerates(reg):
    inputs, clear = reg["inputs"], reg["clear"]
    cl = inputs["clearance"]
    eps = clearance.epsilon_computation(worlds.BASAL, cl["resolution_relative"])
    assert eps["epsilon"] == cl["epsilon"] == clear["epsilon"]["epsilon"]
    assert eps["held_precursor_move"] < cl["resolution_relative"]
    assert clear["epsilon"]["supplied_move"] < eps["held_precursor_move"]
    assert clear["operating_range"]["includes_trace_level"]
    assert clear["trace_level"]["molecules"] > 1e2
    for name, w in reg["rows"]["worlds"].items():
        D = w["quantities"]["D"]["value"]
        tc = clearance.t_clear(w["rows_s"], D, cl["epsilon"])
        assert tc == w["clearance"]["t_clear_s"] == clear["worlds"][name]["t_clear_s"]
        world = inputs["worlds"][name]
        if tc is not None:
            assert (world["horizon_s"] - tc) >= 5 * world["units"]["half_life_s"], name
            b = w["clearance"]["bracket"]
            assert b["at"] <= 1.0 and (b["before"] is None or b["before"] > 1.0)
    common = dict(inputs["clearance_cases"], epsilon=cl["epsilon"])
    for cname, case in inputs["clearance_cases"]["cases"].items():
        reg_case = clear["synthetic_cases"][cname]
        tc, _, _ = clearance.evaluate_case(case, common, common["rows_s"])
        assert tc == reg_case["t_clear_s"], cname
        for plant, entry in reg_case["plants"].items():
            tp, _, _ = clearance.evaluate_case(case, common, common["rows_s"], plant)
            assert tp == entry["t_clear_s"], (cname, plant)
    c7 = inputs["clearance_cases"]["definitional"]["RC7_threshold_equality"]
    assert clearance.t_clear(c7["rows_s"], c7["D"], cl["epsilon"]) == 20.0
    assert clearance.t_clear(c7["rows_s"], c7["D"], cl["epsilon"], strict=True) == 30.0


def test_the_cell_is_r_cells_form_at_a_held_population(reg):
    """With assembly and removal off, N stays N0 and the cell must be R-cell's pump-free cell."""
    from validation.coupling import cells_reference as rc

    inputs = json.loads(json.dumps(reg["inputs"]))
    w = inputs["worlds"]["W6_no_template_m3_t60"]
    w["units"]["assembly_per_s"], w["units"]["removal_per_s"] = 0.0, 0.0
    w["horizon_s"] = 10.0
    world = chain.World(inputs, "W6_no_template_m3_t60")
    mine, _ = chain.simulate(world, (1.0, 5.0, 10.0), rtol=1e-11)
    c, cell = inputs["constants"], inputs["cell"]
    a = world.N0 / (cell["patch_area_m2"] * cell["population"]["reference_density_per_m2"])
    ref = rc.simulate(rc.World(
        rc.Constants(c["faraday_C_per_mol"], c["gas_J_per_mol_K"], c["temperature_K"]),
        tuple(cell["species"]), tuple(cell["valence"]), tuple(cell["bath_mM"]),
        cells={"c": rc.Cell(cell["volume_pL"], tuple(cell["initial_mM"]),
                            initial_V=w["cell_start"]["initial_V"])},
        patches={"m": rc.Patch("c", cell["patch_area_m2"], cell["capacitance_F"],
                               tuple(cell["leak_permeability_m_s"]))},
        populations={"k": rc.Population("m", cell["population"]["permeability_m_s"],
                                        tuple(cell["population"]["relative_permeability"]),
                                        abundance=a)}), 10.0, record=(1.0, 5.0, 10.0),
        rtol=1e-11)
    for rec in mine:
        r = ref.at[rec["t"]]
        assert abs(rec["V"] - r["V"]["c"]) < 1e-11
        assert np.allclose(rec["amounts"], r["amounts_fmol"]["c"], rtol=1e-11, atol=1e-10)


def test_nothing_imports_the_engine():
    src = ROOT / "validation" / "fr7" / "references"
    for path in src.glob("*.py"):
        text = path.read_text()
        assert "import cells" not in text and "from cells" not in text, path.name
    code = ("import sys\n"
            "import validation.fr7.references.design, validation.fr7.references.chain\n"
            "import validation.fr7.references.clearance, validation.fr7.references.worlds\n"
            "bad = [m for m in sys.modules if m == 'cells' or m.startswith('cells.')]\n"
            "lane = [m for m in sys.modules if m.startswith('validation.fr7')\n"
            "        and m != 'validation.fr7' and not m.startswith('validation.fr7.references')]\n"
            "print(bad, lane)\n"
            "sys.exit(1 if bad or lane else 0)\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
