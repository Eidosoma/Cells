"""Offline adapter tests. Fabricated records test the checker, never stand in for BETSE."""

import copy
import json

import pytest

from validation.betse import contact as c


@pytest.fixture
def protocol():
    return c.read(c.HERE / "protocol.json")


@pytest.fixture
def records(protocol):
    cases = c.build_cases(protocol)
    registration = {"protocol": protocol, "cases": cases}
    ids = [case["id"] for case in cases]
    upstream = {"case_ids": ids, "results": {}}
    cells = {
        "case_ids": ids,
        "input_arrays_unchanged": True,
        "device": "cpu",
        "x64_enabled": True,
        "jit_disabled": False,
        "results": {},
    }
    for profile in c.PROFILES:
        constants = protocol["profiles"][profile]
        rates = [c.oracle(case, constants) for case in cases]
        before = c.reference_inputs(cases)
        after = {
            k: ([x + 1e-25 for x in v] if k in ("zc", "vBA") else v) for k, v in before.items()
        }
        upstream["results"][profile] = {
            "dtype": "float64",
            "shape": [len(cases)],
            "constants": constants,
            "inputs_before": before,
            "inputs_after": after,
            "raw_density_mol_per_m2_s": [
                rate * 1e-15 / case["area_m2"] for rate, case in zip(rates, cases, strict=True)
            ],
            "flux_fmol_per_s": rates,
            "derived_inward_current_A": [
                rate * case["valence"] * constants["F"] * 1e-15
                for rate, case in zip(rates, cases, strict=True)
            ],
            "warnings": [],
        }
    for backend in c.CELLS_BACKENDS:
        reference = upstream["results"]["matched_constants"]
        cells["results"][backend] = copy.deepcopy(
            {
                key: reference[key]
                for key in ("dtype", "shape", "flux_fmol_per_s", "derived_inward_current_A")
            }
        )
    return registration, upstream, cells


def test_frozen_panel(protocol):
    cases = c.build_cases(protocol)
    assert len(cases) == len({case["id"] for case in cases}) == 54
    assert {case["species"] for case in cases} == {"Na", "K", "Cl"}


def test_synthetic_checker_records_pass(records):
    result = c.evaluate(*records)
    assert result["status"] == "pass"
    assert result["comparison_count"] == 1047
    assert result["exact_blocking_checks"] == 15
    assert len(result["voltage_input_mutations_per_upstream_profile"]) == 18


@pytest.mark.parametrize("profile", c.PROFILES)
def test_analytic_limits(protocol, profile):
    cases = c.build_cases(protocol)
    constants = protocol["profiles"][profile]
    for case in cases:
        value = c.oracle(case, constants)
        if case["id"].endswith("blocked"):
            assert value == 0.0
        if case["id"].endswith(f"reversal_{profile}"):
            assert abs(value) < 1e-12
        if case["voltage_V"] == 0:
            diffusion = (
                case["area_m2"]
                * case["permeability_m_per_s"]
                / 1e-15
                * (case["outside_mM"] - case["inside_mM"])
            )
            assert value == pytest.approx(diffusion, abs=1e-15)


@pytest.mark.parametrize("profile", c.PROFILES)
@pytest.mark.parametrize("species", ("Na", "K", "Cl"))
def test_dimensional_relations(protocol, profile, species):
    cases = {case["id"]: case for case in c.build_cases(protocol)}
    constants = protocol["profiles"][profile]
    base = c.oracle(cases[f"{species}/voltage_1"], constants)
    for label, factor in (("reversed", -1), ("double_area", 2), ("double_thickness", 1)):
        assert c.oracle(cases[f"{species}/{label}"], constants) == pytest.approx(
            factor * base, abs=1e-14
        )


@pytest.mark.parametrize("factor", (-1.0, 1e-15, 1e9, 2.0))
def test_wrong_sign_units_or_scale_fail_even_when_readouts_are_consistent(records, factor):
    registration, upstream, cells = records
    values = upstream["results"]["matched_constants"]
    for key in ("raw_density_mol_per_m2_s", "flux_fmol_per_s", "derived_inward_current_A"):
        values[key] = [v * factor for v in values[key]]
    assert c.evaluate(registration, upstream, cells)["status"] == "failed"


@pytest.mark.parametrize("backend", c.CELLS_BACKENDS)
def test_changed_cells_output_fails(records, backend):
    registration, upstream, cells = records
    cells["results"][backend]["flux_fmol_per_s"][0] += 1e-5
    assert c.evaluate(registration, upstream, cells)["status"] == "failed"


@pytest.mark.parametrize("field", ("cA", "cB", "Dc", "d", "vBA", "zc", "T", "rho"))
def test_bad_reference_input_mapping_rejected(records, field):
    registration, upstream, cells = records
    upstream["results"]["source_constants"]["inputs_before"][field][0] += 1
    with pytest.raises(ValueError, match="mapping/mutation"):
        c.evaluate(registration, upstream, cells)


def test_hidden_input_mutation_rejected(records):
    registration, upstream, cells = records
    upstream["results"]["matched_constants"]["inputs_after"]["vBA"][3] = 0.0
    with pytest.raises(ValueError, match="mapping/mutation"):
        c.evaluate(registration, upstream, cells)


def test_missing_backend_rejected(records):
    registration, upstream, cells = records
    cells["results"].pop("jax_jit")
    with pytest.raises(ValueError, match="Missing Cells backend"):
        c.evaluate(registration, upstream, cells)


@pytest.mark.parametrize("bad", (float("nan"), float("inf"), True, "0"))
def test_nonnumeric_result_rejected(records, bad):
    registration, upstream, cells = records
    cells["results"]["jax_jit"]["flux_fmol_per_s"][0] = bad
    with pytest.raises(ValueError, match="Nonfinite or nonnumeric"):
        c.evaluate(registration, upstream, cells)


def test_changed_constants_rejected(records):
    registration, upstream, cells = records
    upstream["results"]["source_constants"]["constants"] = {"F": 1, "R": 1}
    with pytest.raises(ValueError, match="Reference constants differ"):
        c.evaluate(registration, upstream, cells)


def test_blocked_tiny_nonzero_rejected(records):
    registration, upstream, cells = records
    index = next(i for i, case in enumerate(registration["cases"]) if case["id"] == "Na/blocked")
    cells["results"]["numpy"]["flux_fmol_per_s"][index] = 1e-30
    with pytest.raises(ValueError, match="not exactly zero"):
        c.evaluate(registration, upstream, cells)


@pytest.mark.parametrize("bad", ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'))
def test_strict_json(tmp_path, bad):
    path = tmp_path / "bad.json"
    path.write_text(bad)
    with pytest.raises(ValueError):
        c.read(path)


def test_nonoverwriting_receipts(tmp_path):
    path = tmp_path / "receipt.json"
    c.write(path, {"original": True})
    with pytest.raises(FileExistsError):
        c.write(path, {"original": False})
    assert json.loads(path.read_text()) == {"original": True}


def test_nonoverwriting_capture_directory(tmp_path):
    with pytest.raises(FileExistsError):
        c.capture(tmp_path)
    assert not (tmp_path / "failure.json").exists()


@pytest.mark.parametrize(
    "field,value", (("area_m2", 0), ("temperature_K", 0), ("area_m2", float("inf")))
)
def test_invalid_positive_parameters_rejected(protocol, field, value):
    protocol[field] = value
    with pytest.raises((ValueError, ArithmeticError)):
        c.build_cases(protocol)


def test_out_of_domain_protocol_rejected(protocol):
    protocol["voltage_grid_V"][0] = 100.0
    with pytest.raises(ValueError, match="voltage domain"):
        c.build_cases(protocol)
