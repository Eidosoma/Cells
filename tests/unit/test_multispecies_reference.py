"""SPEC-005 independent engineering checks, not a production or biological acceptance."""

import copy
import itertools
import json
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, asdict, replace
from decimal import Decimal, localcontext

import pytest

from scripts import check_multispecies_contract as check
from tests import reference_multispecies as ref


@pytest.fixture
def panel():
    return ref.load_json(check.PROTOCOL)


@pytest.fixture
def definition(panel):
    return copy.deepcopy(panel["cases"][1]["assembly"])


def test_frozen_instantaneous_panel_passes_with_separate_claims():
    result = check.verify()
    assert result["status"] == "pass", result["failures"]
    assert result["checks_failed"] == 0
    assert result["groups"]["decimal_flux"]["checks"] == 210
    assert result["groups"]["species_permutation"]["checks"] == 30
    assert result["trajectory_qualification"] == "not_performed"
    assert result["gpu_qualification"] == "not_performed"
    assert result["biological_acceptance"] == "not_assessable"
    assert result["production_change"] is False
    assert result["protocol_sha256"] == check.FROZEN_PROTOCOL_SHA256
    assert len(result["source_sha256"]) == 9


@pytest.mark.parametrize("x", [-50, -1, -1e-4, -1e-8, 0, 1e-8, 1e-4, 1, 50])
def test_bernoulli_domain_endpoints_and_removable_singularity(x, panel):
    with localcontext() as context:
        context.prec = panel["passive_probe"]["decimal_precision"]
        value = Decimal(str(x))
        oracle = float(value / (value.exp() - 1)) if value else 1.0
    assert ref.bernoulli(x) == pytest.approx(oracle, rel=panel["tolerances"]["rtol"], abs=1e-16)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), "cells.multispecies_membrane_reference@2"),
        (("unknown",), 1),
        (("species",), []),
        (("species",), {}),
        (("species", 0, "valence"), True),
        (("species", 0, "valence"), 1.0),
        (("species", 0, "valence"), 0),
        (("species", 0, "valence"), 4),
        (("species", 0, "id"), "Ca"),
        (("species", 0, "id"), "bad id"),
        (("species", 0, "id"), ""),
        (("species", 0, "units"), "mM"),
        (("cell", "volume_pL"), 0),
        (("cell", "volume_pL"), -1),
        (("cell", "volume_pL"), "1"),
        (("cell", "volume_pL"), True),
        (("cell", "volume_pL"), math.inf),
        (("cell", "initial_amount_fmol", "Na"), 0),
        (("cell", "initial_amount_fmol", "Ca"), -1),
        (("cell", "initial_amount_fmol", "Ca"), math.nan),
        (("cell", "initial_amount_fmol", "missing"), 1),
        (("cell", "fixed_charge_equivalent_fmol"), -142.00673677527658),
        (("cell", "fixed_charge_equivalent_fmol"), math.inf),
        (("cell", "initial_voltage_V"), 0),
        (("cell", "initial_voltage_V"), math.nan),
        (("bath", "concentration_mM", "Cl"), 150),
        (("bath", "concentration_mM", "Ca"), 0),
        (("bath", "concentration_mM", "Ca"), math.inf),
        (("bath", "background_charge_mM"), 0),
        (("bath", "background_charge_mM"), math.nan),
        (("bath", "temperature_K"), 0),
        (("bath", "temperature_K"), 1e308),
        (("bath", "volume_pL"), 1),
        (("bath", "amount_fmol"), {"Ca": 2}),
        (("membrane", "inside"), "missing"),
        (("membrane", "outside"), "cell_0"),
        (("membrane", "id"), "bath_0"),
        (("membrane", "area_m2"), 0),
        (("membrane", "area_m2"), 1e-320),
        (("membrane", "specific_capacitance_F_per_m2"), -1),
        (("membrane", "specific_capacitance_F_per_m2"), math.inf),
        (("membrane", "passive", "law"), "calcium_channel@1"),
        (("membrane", "passive", "permeability_m_per_s", "Ca"), -1),
        (("membrane", "passive", "permeability_m_per_s", "Ca"), True),
        (("membrane", "pump", "law"), "arbitrary_expression@1"),
        (("membrane", "pump", "expression"), "eval(...)"),
        (("membrane", "pump", "roles", "sodium"), "missing"),
        (("membrane", "pump", "roles", "sodium"), "K"),
        (("membrane", "pump", "stoichiometry", "Na"), -2),
        (("membrane", "pump", "stoichiometry", "Na"), -3.0),
        (("membrane", "pump", "stoichiometry", "Ca"), 1),
        (("membrane", "pump", "capacity_fmol_per_s"), -1),
        (("membrane", "pump", "drive_J_per_mol"), math.nan),
        (("membrane", "pump", "id"), "cell_0"),
    ],
)
def test_invalid_or_unimplemented_definitions_are_rejected(definition, path, value):
    target = definition
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        ref.resolve(definition)


@pytest.mark.parametrize("field", ["fixed_charge_equivalent_fmol", "initial_voltage_V"])
def test_charge_inputs_cannot_be_implicitly_filled(definition, field):
    del definition["cell"][field]
    with pytest.raises(ValueError, match="exactly these fields"):
        ref.resolve(definition)


def test_dropping_an_inactive_species_is_not_charge_neutral(definition):
    definition["membrane"]["passive"]["permeability_m_per_s"]["Ca"] = 0
    ref.resolve(definition)
    definition["species"].pop()
    for mapping in (
        definition["cell"]["initial_amount_fmol"],
        definition["bath"]["concentration_mM"],
        definition["membrane"]["passive"]["permeability_m_per_s"],
    ):
        del mapping["Ca"]
    with pytest.raises(ValueError, match="bath charge"):
        ref.resolve(definition)
    # Even after explicitly repairing the bath, the old fixed charge cannot disappear.
    definition["bath"]["background_charge_mM"] = 6
    with pytest.raises(ValueError, match="anchor are inconsistent"):
        ref.resolve(definition)


def test_pump_role_valence_is_checked_after_explicit_binding(definition):
    pump = definition["membrane"]["pump"]
    pump["roles"]["potassium"] = "Ca"
    pump["stoichiometry"] = {"Na": -3, "Ca": 2}
    with pytest.raises(ValueError, match="monovalent positive"):
        ref.resolve(definition)


def test_pump_roles_do_not_depend_on_literal_species_names(definition):
    original = ref.evaluate(ref.resolve(definition))
    replacements = {"Na": "species_a", "K": "species_b", "Cl": "species_c", "Ca": "species_d"}
    for item in definition["species"]:
        item["id"] = replacements[item["id"]]
    for owner, field in (
        (definition["cell"], "initial_amount_fmol"),
        (definition["bath"], "concentration_mM"),
        (definition["membrane"]["passive"], "permeability_m_per_s"),
        (definition["membrane"]["pump"], "stoichiometry"),
    ):
        owner[field] = {replacements[k]: v for k, v in owner[field].items()}
    pump = definition["membrane"]["pump"]
    pump["roles"] = {role: replacements[species] for role, species in pump["roles"].items()}
    assert ref.evaluate(ref.resolve(definition)) == original


@pytest.mark.parametrize("case_slot", [0, 1])
def test_permutation_invariance_at_nonuniform_control_and_noninitial_state(panel, case_slot):
    definition = panel["cases"][case_slot]["assembly"]
    p = ref.resolve(definition)
    amount = {
        s: n + 0.00001 * i
        for i, (s, n) in enumerate(zip(p.species_ids, p.initial_amount_fmol, strict=True))
    }
    controls = {s: i / len(p.species_ids) for i, s in enumerate(p.species_ids)}

    def mapped_evaluation(resolved):
        result = asdict(
            ref.evaluate(
                resolved,
                [amount[s] for s in resolved.species_ids],
                leak_control=[controls[s] for s in resolved.species_ids],
                pump_control=0.37,
            )
        )
        return {
            key: dict(zip(resolved.species_ids, value, strict=True))
            if isinstance(value, tuple)
            else value
            for key, value in result.items()
        }

    expected = mapped_evaluation(p)
    for ordering in itertools.permutations(definition["species"]):
        permuted = copy.deepcopy(definition)
        permuted["species"] = list(ordering)
        assert mapped_evaluation(ref.resolve(permuted)) == expected


def test_resolution_copies_input_and_produces_immutable_owned_values(definition):
    before = copy.deepcopy(definition)
    p = ref.resolve(definition)
    ref.evaluate(p)
    assert definition == before
    definition["cell"]["initial_amount_fmol"]["Ca"] = 100
    assert p.initial_amount_fmol[-1] == 0.001
    with pytest.raises(FrozenInstanceError):
        p.volume_pL = 2
    with pytest.raises(ValueError, match="immutable tuple"):
        replace(p, bath_mM=list(p.bath_mM))


def test_amounts_are_primary_and_volume_only_derives_concentrations(definition):
    p = ref.resolve(definition)
    larger = replace(p, volume_pL=2 * p.volume_pL)
    result = ref.evaluate(larger)
    assert result.concentration_mM == tuple(n / 2 for n in p.initial_amount_fmol)
    assert result.voltage_V == p.initial_voltage_V
    assert larger.fixed_charge_equivalent_fmol == p.fixed_charge_equivalent_fmol


@pytest.mark.parametrize(
    "amount",
    [
        (12, 140, 10),
        (12, 140, 10, 0),
        (12, 140, 10, -1),
        (12, 140, 10, math.nan),
        (12, 140, 10, math.inf),
        (12, 140, 10, True),
        (12, 140, 10, 10),
    ],
)
def test_invalid_state_rejected_even_when_all_routes_are_off(definition, amount):
    p = ref.resolve(definition)
    with pytest.raises(ValueError):
        ref.evaluate(p, amount, leak_control=[0] * 4, pump_control=0)


@pytest.mark.parametrize(
    "controls", [(-1, 0, 0, 0), (1, 2, 1, 1), (1, 1), (math.nan, 1, 1, 1), (True, 1, 1, 1)]
)
def test_invalid_leak_controls_rejected(definition, controls):
    with pytest.raises(ValueError):
        ref.evaluate(ref.resolve(definition), leak_control=controls)


@pytest.mark.parametrize("control", [-1, 2, math.inf, math.nan, True, "0"])
def test_invalid_pump_controls_rejected(definition, control):
    p = ref.resolve(definition)
    with pytest.raises(ValueError):
        ref.evaluate(p, pump_control=control)
    with pytest.raises(ValueError):
        ref.pump_cycle(p, [0] * 4, control)


@pytest.mark.parametrize("x", [-50.01, 50.01, math.nan, math.inf, True])
def test_invalid_bernoulli_argument_rejected(x):
    with pytest.raises(ValueError):
        ref.bernoulli(x)


def test_divalent_voltage_domain_is_not_the_old_monovalent_domain():
    assert ref.dimensionless_voltage(1, 0.7, 298.15) < 50
    with pytest.raises(ValueError, match="Voltage exceeds"):
        ref.dimensionless_voltage(2, 0.7, 298.15)


@pytest.mark.parametrize("field", ["permeability_m_per_s", "capacity_fmol_per_s"])
def test_nonfinite_derived_rates_are_rejected(definition, field):
    p = ref.resolve(definition)
    varied = replace(p, **{field: (1e308,) * 4 if field == "permeability_m_per_s" else 1e308})
    with pytest.raises(ValueError, match="finite"):
        ref.evaluate(varied)


def test_unrepresentable_integer_and_non_scalar_identifier_rejected(definition):
    with pytest.raises(ValueError, match="finite"):
        ref.number(10**500, "huge input")
    definition["membrane"]["id"] = []
    with pytest.raises(ValueError, match="IDs"):
        ref.resolve(definition)


def test_overflowing_json_exponent_rejected(tmp_path):
    path = tmp_path / "overflow.json"
    path.write_text('{"x": 1e999}')
    with pytest.raises(ValueError, match="finite"):
        ref.load_json(path)


def test_nonfinite_pump_thermal_scale_is_not_silently_saturated(definition):
    p = replace(ref.resolve(definition), temperature_K=2e307)
    with pytest.raises(ValueError, match="pump thermal scale"):
        ref.pump_cycle(p, [0.0] * 4)


def test_absent_pump_and_zero_capacity_have_explicit_accounting(definition):
    p = ref.resolve(definition)
    disabled = ref.evaluate(replace(p, capacity_fmol_per_s=0))
    assert disabled.pump_cycles_fmol_per_s == 0
    assert disabled.cycle_energy_J_per_mol is not None
    definition["membrane"]["pump"] = None
    absent = ref.resolve(definition)
    result = ref.evaluate(absent)
    assert result.cycle_energy_J_per_mol is None
    assert result.chemical_power_W == 0
    assert result.amount_rate_fmol_per_s == disabled.amount_rate_fmol_per_s
    with pytest.raises(ValueError, match="absent pump"):
        ref.ledger_residuals(absent, absent.initial_amount_fmol, [0] * 4, 0.1)


def test_wrong_ledgers_produce_residuals_without_repair(definition):
    p = ref.resolve(definition)
    result = ref.ledger_residuals(p, p.initial_amount_fmol, [0.01, 0, 0, 0], 0)
    assert result["material_residual_fmol"][0] == -0.01
    assert abs(result["charge_residual_V"]) > 0.09
    assert result["bath_exchange_fmol"][0] == -0.01
    assert p.initial_amount_fmol[0] == 12


@pytest.mark.parametrize(
    "payload",
    [
        '{"x": 1, "x": 2}',
        '{"x": {"y": 1, "y": 2}}',
        '{"x": NaN}',
        '{"x": Infinity}',
        '{"x": -Infinity}',
    ],
)
def test_json_duplicates_and_nonfinite_literals_rejected(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_text(payload)
    with pytest.raises(ValueError):
        ref.load_json(path)


def test_changed_panel_is_not_silently_accepted(tmp_path, monkeypatch):
    path = tmp_path / "changed.json"
    path.write_bytes(check.PROTOCOL.read_bytes() + b"\n")
    monkeypatch.setattr(check, "PROTOCOL", path)
    with pytest.raises(ValueError, match="Frozen panel changed"):
        check.verify()


def test_failed_numerical_checks_are_retained(monkeypatch):
    original = ref.passive_flux
    monkeypatch.setattr(ref, "passive_flux", lambda *a, **k: -original(*a, **k))
    result = check.verify()
    assert result["status"] == "fail"
    assert result["checks_failed"] == len(result["failures"]) > 0
    assert result["groups"]["decimal_flux"]["failed"] > 0
    assert result["groups"]["passive_dissipation"]["failed"] > 0


def test_cli_receipt_and_no_overwrite(tmp_path):
    output = tmp_path / "receipt.json"
    command = [
        sys.executable,
        str(check.ROOT / "scripts/check_multispecies_contract.py"),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout) == json.loads(output.read_text())
    before = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    assert second.returncode != 0
    assert "FileExistsError" in second.stderr
    assert output.read_bytes() == before


def test_independent_reference_imports_no_production_or_jax():
    import ast

    source = check.ROOT / "tests/reference_multispecies.py"
    tree = ast.parse(source.read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add(node.module.split(".")[0])
    assert roots <= {"json", "math", "dataclasses", "pathlib"}
