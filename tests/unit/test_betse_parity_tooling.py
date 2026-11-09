"""Parity tooling: the emulator's harmonic face-rule option and the tolerance recipe.

compact_ecm_faces_harmonic (emulator/spatial.compact_faces) gives each ECM face Cells' face
coefficient (default_world_adapter.resolved_definition); protocol_tolerances.py derives
tolerances by the pinned method and must reproduce the registered rung-1 v2 numbers.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from validation.betse import protocol_tolerances as pt
from validation.betse.emulator import laws
from validation.betse.emulator import spatial as passive

ROOT = Path(__file__).resolve().parents[2]
RUNG1 = Path("/mnt/workspaces/Cells/parity-rung1-20261108-01")
H = 1e-5


def grid(diffusivity, valence=(1.0, -1.0)):
    """A minimal compact_faces layout: 2 species on a rows x cols grid."""
    d = np.asarray(diffusivity, dtype=np.float64)
    shape = (len(valence), *d.shape)
    layout = SimpleNamespace(
        spacing=H,
        screening_wavenumber=1e6,
        cell_size_ratio=0.5,
        moving=np.ones(len(valence), dtype=bool),
        diffusivity=np.broadcast_to(d, shape).copy(),
        valence=np.asarray(valence),
        native_q_over_kb=1.602e-19 / 1.3806e-23,
        temperature=310.0,
        boundary_values=np.zeros(d.shape),
    )
    mobility = layout.diffusivity * layout.valence[:, None, None] * layout.native_q_over_kb / 310.0
    rows, cols = d.shape
    c = np.broadcast_to(10.0 + np.arange(cols, dtype=np.float64), shape).copy()
    phi = 1e-3 * np.sin(np.arange(rows * cols, dtype=np.float64))
    return c, SimpleNamespace(outside_potential_V=phi.reshape(d.shape)), layout, mobility


def test_harmonic_face_rule_option_is_cells_series_conductance():
    assert laws.MODEL_DIFFERENCES["compact_ecm_faces_harmonic"] == (
        "compact_ecm_faces",
        "harmonic_ecm_faces",
    )
    variant = laws.default_world("betse", ("compact_ecm_faces_harmonic",))
    assert variant.compact_ecm_faces and variant.harmonic_ecm_faces
    assert not laws.default_world("betse", ("compact_ecm_faces",)).harmonic_ecm_faces

    # Uniform diffusivity: the two rules agree (to roundoff in the mobility product).
    c, f, layout, mobility = grid(np.full((4, 5), 2e-9))
    arithmetic = passive.compact_faces(c, f, layout, 1e-4, mobility, 1.0, xp=np)
    harmonic = passive.compact_faces(c, f, layout, 1e-4, mobility, 1.0, xp=np, harmonic=True)
    for a, b in zip(arithmetic, harmonic, strict=True):
        np.testing.assert_allclose(a, b, rtol=1e-14, atol=1e-30)

    # A barrier square: the face coefficient is 2 Da Db / (Da + Db), for anions too.
    d = np.full((4, 5), 2e-9)
    d[1, 2] = 0.05 * 2e-9
    c, f, layout, mobility = grid(d)
    fx, _, _ = passive.compact_faces(c, f, layout, 1e-4, mobility, 0.0, xp=np, harmonic=True)
    face = 2 * 2e-9 * 1e-10 / (2e-9 + 1e-10)
    np.testing.assert_allclose(fx[:, 1, 1], -face * (c[:, 1, 2] - c[:, 1, 1]) / H, rtol=1e-14)
    fx_a, _, _ = passive.compact_faces(c, f, layout, 1e-4, mobility, 0.0, xp=np)
    np.testing.assert_allclose(fx_a[:, 1, 1], -0.5 * (2e-9 + 1e-10) / H, rtol=1e-14)
    drift_only = passive.compact_faces(c, f, layout, 1e-4, mobility, 1.0, xp=np, harmonic=True)[0]
    drift_only = drift_only - fx  # the electromigration part of each face flux
    phi = 2 / (1e6 * H) * 0.5 * f.outside_potential_V
    per_d = layout.valence * layout.native_q_over_kb / 310.0
    expected = -face * per_d * (phi[1, 2] - phi[1, 1]) / H * 0.5 * (c[:, 1, 2] + c[:, 1, 1])
    np.testing.assert_allclose(drift_only[:, 1, 1], expected, rtol=1e-12)
    assert expected[0] * expected[1] < 0  # cation and anion drift oppositely

    # The boundary ring is held (reservoirs), as in Cells.
    _, _, delta = passive.compact_faces(c, f, layout, 1e-4, mobility, 1.0, xp=np, harmonic=True)
    ring = passive.boundary_mask(d.shape, xp=np)
    assert np.all(delta[:, ring] == 0)


def write(path, value):
    path.write_text(json.dumps(value))
    return path


def rows(volt, cell, ecm):
    by_ion = lambda v: {i: {"max": v, "final_max": v / 2} for i in ("Na", "K")}  # noqa: E731
    return {
        "vm_time": {"max": volt, "final": {"max": volt / 2}},
        "vm_ave_time": {"max": volt / 4, "final": {"max": volt / 4}},
        "cc_time": {"by_ion": by_ion(cell)},
        "cc_env_time_interior": {"by_ion": by_ion(ecm)},
    }


def test_recipe_sums_terms_with_margin_and_rounding(tmp_path, monkeypatch):
    budget = {
        "pairs": {
            name: {"phases": {p: {"observables": rows(v, 2 * v, 3 * v)} for p in pt.PHASES}}
            for name, v in (("a", 1e-6), ("b", 4e-6), ("c", 2e-6))
        }
    }
    write(tmp_path / "budget.json", budget)
    write(tmp_path / "step.json", {"phases": budget["pairs"]["c"]["phases"]})
    context = SimpleNamespace(ions=["Na", "K"], base=tmp_path, done={})
    context.path = lambda name: tmp_path / name
    monkeypatch.setattr(pt, "Context", lambda case, base: context)
    recipe = {
        "case": "unused",
        "terms": {
            "max_ab": {"budget": "budget.json", "pairs": ["a", "b"]},
            "step_scaled": {"step": ["step.json"], "scale": 0.5},
            "max_of": {
                "max_of": [{"budget": "budget.json", "pairs": ["a"]}, {"step": ["step.json"]}]
            },
        },
    }
    out = pt.derive(recipe, tmp_path)
    # max_ab 4e-6, step_scaled 1e-6, max_of 2e-6: sum 7e-6, x3 = 2.1e-5 -> 3e-5.
    assert out["sums_before_margin"]["voltage"]["init"] == pytest.approx(7e-6)
    assert out["tolerance"]["voltage"]["sim"] == 3e-5
    assert out["tolerance"]["ecm_concentration"]["init"]["by_ion"]["K"] == 7e-5  # 3 x 2.1e-5
    assert out["largest_term"]["voltage"]["init"] == "max_ab"
    assert pt.up1(2.00001e-5) == 3e-5 and pt.up1(2e-5) == 2e-5 and pt.up1(0) == 0


@pytest.mark.skipif(not RUNG1.is_dir(), reason="rung-1 evidence not on this machine")
def test_recipe_reproduces_the_registered_rung1_v2_tolerances():
    e, b, a = RUNG1 / "emulator-01", RUNG1 / "blind-01", RUNG1 / "attribution-01"
    budget = str(e / "difference_budget.json")
    recipe = {
        "case": str(RUNG1 / "betse-reference/default-world-mammal-dense"),
        "terms": {
            "betse_init_step": {
                "max_of": [
                    {"budget": budget, "pairs": ["betse_dt_vs_dt_over_100"]},
                    {"step": [str(e / "betse_step_term.json")]},
                ]
            },
            "constants_codata_vs_betse": {"budget": budget, "pairs": ["betse_vs_codata_constants"]},
            "exterior_field_law_bound_ecm_drift_off": {
                "budget": budget,
                "pairs": ["ecm_drift_off"],
            },
            "conservative_compact_ecm_faces_at_dt_over_100": {
                "budget": budget,
                "pairs": ["compact_ecm_faces_at_dt_over_100"],
            },
            "physical_time_gate_and_no_concentration_lag": {
                "budget": budget,
                "pairs": ["gate_once_no_lag", "gate_once_no_lag_at_dt_over_100"],
            },
            "cells_numerics_ars222": {
                "layouts": [str(b / "D-gpu/layout"), str(b / "D-half-gpu/layout")],
                "scale": 4 / 3,
            },
            "X_ext_within_cell_patch_voltage_spread": {
                "x_ext_runs": [
                    str(b / f"{n}/run.json") for n in ("D-gpu", "D-cpu", "F-gpu", "D-half-gpu")
                ],
                "per_volt": "constants_codata_vs_betse",
            },
            "calcium_pump_law_cells_vs_betse": {
                "budget": str(a / "emulator/pump_law_budget.json"),
                "pairs": ["pump_law_betse_constants", "pump_law_codata_constants"],
            },
            "cells_exterior_field_boltzmann_response": {
                "field_layouts": [str(b / "D-gpu/layout"), str(b / "F-gpu/layout")]
            },
        },
    }
    derived = pt.derive(recipe, RUNG1)
    protocol = json.loads(
        (
            ROOT / "validation/betse/protocols/physical_default_world_mammal_dense_v2.json"
        ).read_text()
    )
    assert derived["tolerance"] == protocol["tolerance_classes"][protocol["verdict_class"]]


def test_comparator_judges_against_a_declared_reference_layout(tmp_path):
    """A protocol ``reference`` replaces the BETSE arrays by a pinned comparison layout."""
    import hashlib

    from tests.unit.test_cells_betse_compare import EXAMPLE, make_betse
    from validation.betse import cells_betse_compare as cmp

    protocol = json.loads(EXAMPLE.read_text())
    betse = make_betse(tmp_path / "betse")
    geometry = betse["files"]["geometry.npz"]["sha256"]
    change = {"phase": "sim", "observable": "cc_env_time", "index": [2, 1, 4]}
    shifted = {**change, "new_value": 103.0 * (1 + 1e-6)}  # far outside both classes
    reference = tmp_path / "reference"
    cmp.write_layout(
        reference,
        cmp.layout_from_betse(tmp_path / "betse", betse, protocol, shifted),
        protocol_sha256="0" * 64,  # the reference's own run protocol; not this one
        betse_geometry_sha256=geometry,
        provenance={"producer": "reference"},
    )
    digest = hashlib.sha256((reference / cmp.LAYOUT_MANIFEST).read_bytes()).hexdigest()

    def judged(name, spec, perturbation):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(protocol | {"reference": spec}))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        phases = cmp.layout_from_betse(tmp_path / "betse", betse, protocol, perturbation)
        cmp.write_layout(
            tmp_path / name,
            phases,
            protocol_sha256=sha,
            betse_geometry_sha256=geometry,
            provenance={"producer": "test"},
        )
        return cmp.run_comparison(tmp_path / "betse", tmp_path / name, path)

    spec = {"kind": "comparison_layout", "path": str(reference), "manifest_sha256": digest}
    same = judged("same", spec, shifted)
    assert same["verdict"] == "pass" and same["reference"]["manifest_sha256"] == digest
    plain = judged("plain", spec, None)  # equal to BETSE, so it differs from the reference
    assert plain["verdict"] == "fail"
    worst = plain["phases"]["sim"]["observables"]["cc_env_time"]["history"]["max_rel"]
    assert worst["element"] == [1, 4]
    refused = judged("refused", spec | {"manifest_sha256": "f" * 64}, shifted)
    assert refused["verdict"] == "refused" and "manifest_sha256" in refused["refusals"][0]
    (reference / "sim_final.npz").write_bytes(b"tampered")
    tampered = judged("tampered", spec, shifted)
    assert tampered["verdict"] == "refused" and "sim_final.npz" in tampered["refusals"][0]


def test_field_solver_is_declared_and_must_match_the_protocol(tmp_path):
    from cells.core.specs import parse_spec
    from tests.unit.test_default_world_adapter import DT, MAMMAL, judged_protocol_file, write_case
    from validation.betse import default_world_adapter as adapter

    case = write_case(tmp_path / "betse", ions=MAMMAL)
    world = adapter.betse_world(case, blind=True)
    start = adapter.phase_start(world, "init")
    floor = adapter.RESOLVED_FLOOR_FIELD_SOLVER
    assert adapter.RESOLVED_FIELD_SOLVER == "capacitive_reduction_gauged_damped_newton@2"
    assert floor == "capacitive_reduction_gauged_damped_newton@3"
    default = adapter.resolved_definition(world, "init", start, dt=1e-3)
    declared = adapter.resolved_definition(world, "init", start, dt=1e-3, field_solver=floor)
    assert default["execution"]["field_solver"] == adapter.RESOLVED_FIELD_SOLVER
    assert declared["execution"]["field_solver"] == floor
    assert {k: v for k, v in declared["execution"].items() if k != "field_solver"} == {
        k: v for k, v in default["execution"].items() if k != "field_solver"
    }
    assert parse_spec(declared).execution.field_solver == floor
    with pytest.raises(adapter.AdapterError, match="field solver"):
        adapter.resolved_definition(world, "init", start, dt=1e-3, field_solver="newton@9")
    run = dict(
        device_kind="cpu", dt_init=DT["init"], dt_sim=DT["sim"], solver=adapter.RESOLVED_SOLVER
    )
    world = world | {"case": "synthetic"}
    model = adapter.RESOLVED_CALCIUM_MODEL_ID
    plain = judged_protocol_file(tmp_path, model=model)  # names no field solver: for @2
    adapter.judged_protocol(plain, world, **run)
    with pytest.raises(adapter.AdapterError, match="field_solver"):
        adapter.judged_protocol(plain, world, **run, field_solver=floor)
    (tmp_path / "floor").mkdir()
    declares = judged_protocol_file(tmp_path / "floor", model=model, field_solver=floor)
    adapter.judged_protocol(declares, world, **run, field_solver=floor)
    with pytest.raises(adapter.AdapterError, match="field_solver"):
        adapter.judged_protocol(declares, world, **run)
