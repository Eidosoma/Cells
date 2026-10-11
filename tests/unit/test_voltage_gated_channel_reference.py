"""SPEC-006 reference checks; no new production model or biological acceptance."""

import ast
import copy
import json
import math
import subprocess
import sys
from dataclasses import FrozenInstanceError, asdict, replace
from decimal import localcontext

import pytest

from scripts import check_voltage_gated_channel as check
from tests import reference_multispecies as ionic
from tests import reference_voltage_gated_channel as ref


@pytest.fixture
def panel():
    return ionic.load_json(check.PROTOCOL)


@pytest.fixture
def definition(panel):
    return copy.deepcopy(panel["cases"][1]["definition"])


@pytest.fixture
def protocol(panel):
    return copy.deepcopy(
        next(p["protocol"] for p in panel["protocols"] if p["id"] == "block_release")
    )


def test_frozen_panel_and_separate_claims():
    result = check.verify()
    assert result["status"] == "pass", result["failures"]
    assert result["checks_failed"] == 0
    assert result["groups"]["source_unit_rates"]["checks"] == 13 * 4
    assert result["groups"]["decimal_channel_flux"]["checks"] == 2 * 2 * 7 * 3
    assert result["groups"]["species_permutation"]["checks"] == 30
    assert len(result["gate_protocols"]) == 7
    assert sum(len(v) for v in result["gate_protocols"].values()) == 62
    assert len(result["production_source_sha256"]) == 41
    assert len(result["source_sha256"]) == 10
    assert result["coupled_trajectory_qualification"] == "not_performed"
    assert result["method_selection"] == result["gpu_qualification"] == "not_performed"
    assert result["biological_acceptance"] == "not_assessable"
    assert result["production_change"] is result["native_betse_execution"] is False


@pytest.mark.parametrize("v", [-0.12, -0.065, -0.0253, -0.006, 0, 0.04, 0.06])
def test_native_ms_mv_units_and_gate_boundaries(v):
    k = ref.kinetics(v)
    with localcontext() as context:
        context.prec = 70
        oracle = tuple(float(x) for x in check.decimal_kinetics(v))
    assert tuple(asdict(k).values()) == pytest.approx(oracle, rel=2e-12, abs=1e-14)
    assert all(q >= 0 for q in ref.gate_rate(v, ref.Gate(0, 0)))
    assert all(q <= 0 for q in ref.gate_rate(v, ref.Gate(1, 1)))
    assert ref.gate_rate(v, ref.equilibrium_gate(v)) == (0.0, 0.0)
    settled = ref.relax_gate(v, ref.Gate(0.2, 0.8), 100 * max(k.tau_m_s, k.tau_h_s))
    assert (settled.m, settled.h) == pytest.approx(oracle[:2], abs=1e-15)


def test_fast_and_slow_timescales_do_not_inherit_10ms():
    low, high = ref.kinetics(-0.12), ref.kinetics(0.06)
    assert (high.tau_m_s, low.tau_m_s) == pytest.approx((0.001352, 0.022286))
    assert (high.tau_h_s, low.tau_h_s) == pytest.approx((0.690, 3.480))
    ratio = 0.01 / high.tau_m_s
    amplification = 1 - ratio + ratio**2 / 2 - ratio**3 / 6 + ratio**4 / 24
    assert amplification > 1  # Algebraic held-gate counterexample, no candidate ODE run.
    assert high.m_inf * (1 - amplification) < 0


@pytest.mark.parametrize("v", [-0.120001, 0.060001, 1, math.nan, math.inf, True, "0"])
def test_kinetics_refuses_invalid_or_unqualified_voltages(v):
    with pytest.raises(ValueError):
        ref.kinetics(v)


@pytest.mark.parametrize(
    "state", [(-1e-15, 1), (1.000001, 0), (0, math.nan), (0, math.inf), (True, 0), (0, "1")]
)
def test_gate_state_is_not_clipped_or_coerced(state):
    with pytest.raises(ValueError):
        ref.Gate(*state)


@pytest.mark.parametrize("elapsed", [-1, math.inf, math.nan, True, "1", 1e308])
def test_bad_elapsed_and_nonfinite_derived_arithmetic_are_refused(elapsed):
    with pytest.raises(ValueError):
        ref.relax_gate(0.06, ref.Gate(0, 1), elapsed)


def test_zero_time_keeps_identity_and_initial_state_is_not_implicitly_prepared(definition):
    p = ref.resolve(definition)
    g = p.channel.initial_gate
    assert (g.m, g.h) == (0, 1)
    assert ref.relax_gate(-0.065, g, 0) is g
    assert ref.equilibrium_gate(-0.065) != g
    with pytest.raises(FrozenInstanceError):
        g.m = 1
    with pytest.raises(ValueError):
        ref.gate_rate(-0.065, [0, 1])
    with pytest.raises(ValueError):
        ref.relax_gate(-0.065, {"m": 0, "h": 1}, 1)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), "cells.voltage_gated_membrane_reference@2"),
        (("unknown",), 1),
        (("assembly", "schema"), "multispecies_membrane@1"),
        (("channel",), None),
        (("channel", "id"), "bad id"),
        (("channel", "id"), "cell_0"),
        (("channel", "membrane_id"), "missing"),
        (("channel", "species_id"), "missing"),
        (("channel", "species_id"), "Ca"),
        (("channel", "species_id"), "Cl"),
        (("channel", "species_id"), True),
        (("channel", "kinetic_law"), "generic_expression@1"),
        (("channel", "voltage_shift_V"), 0),
        (("channel", "q10"), 2),
        (("channel", "max_permeability_m_per_s"), -1),
        (("channel", "max_permeability_m_per_s"), True),
        (("channel", "max_permeability_m_per_s"), math.inf),
        (("channel", "max_permeability_m_per_s"), 1e308),
        (("channel", "abundance"), -1),
        (("channel", "abundance"), "1"),
        (("channel", "abundance"), False),
        (("channel", "abundance"), math.nan),
        (("channel", "initial_gate"), [0, 1]),
        (("channel", "initial_gate", "open_probability"), 0),
        (("channel", "initial_gate", "m"), -1e-10),
        (("channel", "initial_gate", "m"), 1.01),
        (("channel", "initial_gate", "h"), math.inf),
        (("channel", "initial_gate", "h"), True),
        (("assembly", "bath", "temperature_K"), 310),
        (("assembly", "cell", "initial_amount_fmol", "Ca"), 0),
        (("assembly", "cell", "initial_voltage_V"), 0),
    ],
)
def test_invalid_definition_refused(definition, path, value):
    target = definition
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        ref.resolve(definition)


@pytest.mark.parametrize("field", ["m", "h"])
def test_complete_initial_gates_are_required(definition, field):
    del definition["channel"]["initial_gate"][field]
    with pytest.raises(ValueError):
        ref.resolve(definition)


def test_nonliteral_species_names_and_explicit_binding(definition):
    original = ref.resolve(definition)
    expected = ref.evaluate(original, gate=ref.Gate(0.2, 0.8))
    assembly = definition["assembly"]
    names = {s["id"]: f"ion_{i}" for i, s in enumerate(assembly["species"])}
    for item in assembly["species"]:
        item["id"] = names[item["id"]]
    for owner, field in (
        (assembly["cell"], "initial_amount_fmol"),
        (assembly["bath"], "concentration_mM"),
        (assembly["membrane"]["passive"], "permeability_m_per_s"),
        (assembly["membrane"]["pump"], "stoichiometry"),
    ):
        owner[field] = {names[s]: v for s, v in owner[field].items()}
    pump = assembly["membrane"]["pump"]
    pump["roles"] = {role: names[s] for role, s in pump["roles"].items()}
    definition["channel"]["species_id"] = names[definition["channel"]["species_id"]]
    renamed = ref.resolve(definition)
    assert renamed.species_index == original.species_index
    assert ref.evaluate(renamed, gate=ref.Gate(0.2, 0.8)) == expected


@pytest.mark.parametrize("field", ["abundance", "max_permeability_m_per_s"])
def test_real_disabled_mechanism_keeps_gate_state_and_domain(definition, field):
    p = ref.resolve(definition)
    disabled = replace(p, channel=replace(p.channel, **{field: 0}))
    g = ref.Gate(0.4, 0.6)
    a, b = ref.evaluate(p, gate=g), ref.evaluate(disabled, gate=g)
    assert a.channel_flux_fmol_per_s != 0
    assert b.channel_flux_fmol_per_s == 0
    assert b.gate_rate_per_s == a.gate_rate_per_s != (0, 0)
    amounts = list(p.assembly.initial_amount_fmol)
    amounts[0] += (
        (0.08 - p.assembly.initial_voltage_V) * p.assembly.capacitance_F / ionic.CHARGE_PER_FMOL
    )
    with pytest.raises(ValueError, match="Gate voltage"):
        ref.evaluate(disabled, amounts, g, availability=0)


def test_leak_pump_and_channel_controls_are_independent(definition):
    p, g = ref.resolve(definition), ref.Gate(0.4, 0.6)
    on = ref.evaluate(p, gate=g)
    channel_only = ref.evaluate(p, gate=g, leak_control=[0] * 4, pump_control=0)
    baseline_only = ref.evaluate(p, gate=g, availability=0)
    assert channel_only.channel_flux_fmol_per_s == on.channel_flux_fmol_per_s
    assert channel_only.amount_rate_fmol_per_s == on.channel_species_rate_fmol_per_s
    assert baseline_only.amount_rate_fmol_per_s == on.baseline.amount_rate_fmol_per_s
    assert channel_only.gate_rate_per_s == baseline_only.gate_rate_per_s == on.gate_rate_per_s
    for u in (-1, 1.01, True, math.inf, "0"):
        with pytest.raises(ValueError):
            ref.evaluate(p, gate=g, availability=u)


def test_equal_present_open_fraction_does_not_determine_future(definition):
    p = ref.resolve(definition)
    a, b = ref.Gate(0.2, 0.8), ref.Gate(0.8, 0.2)
    aa, bb = ref.evaluate(p, gate=a), ref.evaluate(p, gate=b)
    assert aa.open_probability == bb.open_probability
    assert aa.amount_rate_fmol_per_s == bb.amount_rate_fmol_per_s
    assert aa.baseline.voltage_V == bb.baseline.voltage_V
    assert aa.gate_rate_per_s != bb.gate_rate_per_s
    assert (
        ref.relax_gate(0, a, 0.001).open_probability != ref.relax_gate(0, b, 0.001).open_probability
    )


def test_channel_history_has_its_own_material_and_charge_contribution(definition):
    p = ref.resolve(definition)
    base, index = p.assembly, p.species_index
    passive = (2e-6, -3e-6, 4e-6, -1e-7)
    cycles, history = 1e-6, -2e-6
    amounts = tuple(
        n + leak + nu * cycles + (history if i == index else 0)
        for i, (n, leak, nu) in enumerate(
            zip(base.initial_amount_fmol, passive, base.stoichiometry, strict=True)
        )
    )
    result = ref.evaluate(p, amounts, ref.Gate(0.3, 0.7), availability=0)
    delta_charge = math.fsum(
        z * (leak + nu * cycles + (history if i == index else 0))
        for i, (z, leak, nu) in enumerate(
            zip(base.valence, passive, base.stoichiometry, strict=True)
        )
    )
    assert result.baseline.voltage_V == pytest.approx(
        base.initial_voltage_V + ionic.CHARGE_PER_FMOL / base.capacitance_F * delta_charge,
        abs=3e-13,
    )
    wrong = delta_charge - base.valence[index] * history
    assert (
        abs(
            result.baseline.voltage_V
            - (base.initial_voltage_V + ionic.CHARGE_PER_FMOL / base.capacitance_F * wrong)
        )
        > 1e-6
    )
    assert base.initial_amount_fmol == p.assembly.initial_amount_fmol


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), "invalid"),
        (("unknown",), 0),
        (("initial_gate",), {"open_probability": 0.1}),
        (("end_time_s",), 0),
        (("end_time_s",), math.inf),
        (("end_time_s",), True),
        (("voltage_steps",), []),
        (("voltage_steps",), {}),
        (("voltage_steps", 0, "time_s"), 0.001),
        (("voltage_steps", 1, "time_s"), 0),
        (("voltage_steps", 1, "time_s"), 1),
        (("voltage_steps", 0, "voltage_V"), 0.061),
        (("voltage_steps", 0, "voltage_V"), True),
        (("voltage_steps", 0, "extra"), 1),
        (("availability_steps",), []),
        (("availability_steps", 0, "time_s"), 0.01),
        (("availability_steps", 1, "multiplier"), 1.01),
        (("availability_steps", 0, "multiplier"), True),
        (("availability_steps", 0, "multiplier"), math.nan),
        (("sample_times_s",), []),
        (("sample_times_s",), {}),
        (("sample_times_s",), [0, 0]),
        (("sample_times_s",), [0.1, 0]),
        (("sample_times_s",), [-1]),
        (("sample_times_s",), [1]),
        (("sample_times_s",), [math.inf]),
        (("sample_times_s",), [False]),
    ],
)
def test_invalid_program_is_refused(protocol, path, value):
    target = protocol
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        ref.resolve_program(protocol)


def test_resolved_program_disallows_mutable_groups(protocol):
    p = ref.resolve_program(protocol)
    for field in ("voltage_steps", "availability_steps", "sample_times_s"):
        with pytest.raises(ValueError):
            replace(p, **{field: list(getattr(p, field))})
    with pytest.raises(ValueError):
        replace(p, voltage_steps=([0, -0.08],))


def test_step_state_continuity_and_readout_sidedness(protocol):
    p = ref.resolve_program(protocol)
    rows = {x.time_s: x for x in ref.sample_program(p)}
    expected = ref.relax_gate(-0.08, p.initial_gate, 0.023)
    assert (rows[0.023].m, rows[0.023].h) == (expected.m, expected.h)
    assert rows[0.023].voltage_V == 0.02
    assert rows[0.017].availability == 0 and rows[0.041].availability == 1
    assert rows[0.4].availability == 0 and rows[0.4].available_open_fraction == 0
    no_final = ref.sample_program(replace(p, voltage_steps=p.voltage_steps[:-1]))[-1]
    assert (no_final.m, no_final.h) == (rows[0.4].m, rows[0.4].h)
    assert (no_final.dm_per_s, no_final.dh_per_s) != (rows[0.4].dm_per_s, rows[0.4].dh_per_s)


def test_availability_and_observations_do_not_advance_gates(protocol):
    p = ref.resolve_program(protocol)
    rows = ref.sample_program(p)
    altered = replace(p, availability_steps=((0, 0), (0.000123, 1), (0.017001, 0), (0.4, 1)))
    alternate = ref.sample_program(altered)
    assert [(r.m, r.h, r.dm_per_s, r.dh_per_s) for r in rows] == [
        (r.m, r.h, r.dm_per_s, r.dh_per_s) for r in alternate
    ]
    assert ref.sample_program(replace(p, sample_times_s=p.sample_times_s[::2])) == rows[::2]


def test_short_voltage_pulse_is_not_lost_to_observation_spacing(panel):
    p = ref.resolve_program(
        next(p["protocol"] for p in panel["protocols"] if p["id"] == "substep_pulse")
    )
    pulse = ref.sample_program(replace(p, sample_times_s=(0.025,)))[0]
    passive = ref.sample_program(replace(p, voltage_steps=((0, -0.08),), sample_times_s=(0.025,)))[
        0
    ]
    assert abs(pulse.m - passive.m) > 1e-3


@pytest.mark.parametrize("payload", ['{"m":0,"m":1,"h":1}', '{"m":NaN,"h":1}', '{"m":1e999,"h":1}'])
def test_strict_json_loader_rejects_duplicate_and_nonfinite_keys(tmp_path, payload):
    p = tmp_path / "bad.json"
    p.write_text(payload)
    with pytest.raises(ValueError):
        ionic.load_json(p)


def test_unregistered_panel_change_is_refused(tmp_path, monkeypatch, panel):
    p = tmp_path / "changed.json"
    panel["tolerances"]["gate"] = 1
    p.write_text(json.dumps(panel))
    monkeypatch.setattr(check, "PROTOCOL", p)
    with pytest.raises(ValueError, match="Frozen SPEC-006"):
        check.verify()


def test_reference_has_no_production_or_solver_imports():
    tree = ast.parse((check.ROOT / "tests/reference_voltage_gated_channel.py").read_text())
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(a.name.split(".")[0] for a in node.names)
        if isinstance(node, ast.ImportFrom):
            modules.append(node.module.split(".")[0])
    assert set(modules) <= {"bisect", "math", "dataclasses", "tests"}


def test_cli_new_receipt_is_inspectable_and_never_overwritten(tmp_path):
    output = tmp_path / "receipt.json"
    command = [
        sys.executable,
        str(check.ROOT / "scripts/check_voltage_gated_channel.py"),
        "--output",
        str(output),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=True)
    result = json.loads(output.read_text())
    assert json.loads(first.stdout) == result and result["status"] == "pass"
    original = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode != 0 and "FileExistsError" in second.stderr
    assert output.read_bytes() == original
