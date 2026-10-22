"""Shared HCN gates: native laws, owned multi-ion transport and complete execution."""

import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble import ionic
from cells.models import surface_hcn as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes import hcn_channels as channels
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests.unit import test_surface_channels as shared
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import hcn_reference
from validation.tissue import surface_hcn_fixtures as fixtures
from validation.tissue import surface_kinetic_reference as reference
from validation.tissue import surface_sodium_fixtures as sodium

BACKEND, EVIDENCE = shared.BACKEND, shared.EVIDENCE
PREFIX = "resolved-hcn"
STEPS = (2.5e-6, 1.25e-6, 0.625e-6)
REFERENCE_SETTINGS = dict(rtol=1e-13, state_atol=1e-16, charge_atol=5e-32)
REFERENCE_CHECK_SETTINGS = {k: v / 4 for k, v in REFERENCE_SETTINGS.items()}
SOURCE_HASHES = {
    "vg_funny.py": "254f2176e0b86906ae445fdd297750ad0b68cc9bd22da11d05437e6f9824cde7",
    "channelsabc.py": "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4",
}


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(shared, "fixtures", fixtures)
        patch.setattr(shared, "PREFIX", PREFIX)
        patch.setattr(shared, "MODEL_ID", model.MODEL_ID)
        patch.setattr(shared, "REFINEMENT_STEPS", STEPS)
        patch.setattr(shared, "BATCH_STEP_BUDGET", 2048)
        yield


def evidence(name, value):
    shared.evidence(name, value)


def check_reference_settings(result, settings):
    assert result["rtol"] == settings["rtol"]
    assert result["amount_energy_gate_atol"] == settings["state_atol"]
    assert result["electrode_charge_atol_C"] == settings["charge_atol"]


@pytest.fixture(scope="module")
def references():
    results = {}
    for arm in fixtures.ARMS:
        raw = parse_spec(fixtures.definition(arm)).to_dict()
        if BACKEND == "gpu" and EVIDENCE:
            path = Path(EVIDENCE) / "cpu" / f"{PREFIX}-trajectory-{arm}.json"
            saved = json.loads(path.read_text())
            assert saved["status"] == "passed" and saved["inputs"] == raw
            result = saved["independent_reference"]
        else:
            result = reference.integrate(raw, **REFERENCE_SETTINGS)
        check_reference_settings(result, REFERENCE_SETTINGS)
        results[arm] = result
    return results


@pytest.mark.parametrize("arm", ("clamped", "release"))
def test_reference_accuracy(arm, references):
    raw = parse_spec(fixtures.definition(arm)).to_dict()
    name = "reference-accuracy-" + arm
    if BACKEND == "gpu" and EVIDENCE:
        path = Path(EVIDENCE) / "cpu" / f"{PREFIX}-{name}.json"
        saved = json.loads(path.read_text())
        assert saved["status"] == "passed" and saved["inputs"] == raw
        assert saved["reference_settings"] == REFERENCE_SETTINGS
        assert saved["check_settings"] == REFERENCE_CHECK_SETTINGS
        assert saved["reference_state"] == references[arm]["state"]
        evidence(name, saved | dict(reused_cpu_reference_check=True))
        return
    c = reference.bind(raw)
    stronger = reference.integrate(raw, **REFERENCE_CHECK_SETTINGS)
    check_reference_settings(stronger, REFERENCE_CHECK_SETTINGS)
    diff = reference.unpack(c, np.asarray(references[arm]["state"]) - np.asarray(stronger["state"]))
    errors = {k: float(np.max(np.abs(v))) for k, v in diff.items()}
    bounds = {k: 3e-28 if k.endswith("_C") else 3e-14 for k in errors}
    passed = all(errors[k] <= bounds[k] for k in errors)
    evidence(
        name,
        dict(
            status="passed" if passed else "failed",
            inputs=raw,
            reference_settings=REFERENCE_SETTINGS,
            check_settings=REFERENCE_CHECK_SETTINGS,
            errors_by_field=errors,
            absolute_bounds=bounds,
            reference_state=references[arm]["state"],
            stronger_reference=stronger,
            scope="Independent-reference accuracy control, not a biological case",
            reused_cpu_reference_check=False,
        ),
    )
    assert passed, errors


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def test_design_and_rejections():
    for backend in ("cpu", "gpu"):
        raw = fixtures.definition(backend=backend)
        spec, state, p, _ = initial(raw)
        assert spec == parse_spec(spec.to_dict())
        assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
        assert spec.to_dict()["model"]["id"] == "resolved_tissue@5"
        assert (
            ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation
            == spec
        )
        assert state.channel_gate.shape == (2, 11)
        assert (
            state.channel_transferred.shape == state.channel_dissipated_energy_pJ.shape == (4, 11)
        )
        assert model.STATE_AXES["channel_transferred"] == ["species", "channel_slot"]
        np.testing.assert_array_equal(p.channel_laws, [0, 1, 0, 1, 1, 2, 2, 3, 4, 5, 0])
        np.testing.assert_array_equal(p.channel_relative_permeability[:, 7], [0.2, 1, 0, 0.05])
    faults = (
        "law",
        "old_model",
        "missing_ion",
        "duplicate_ion",
        "ratio",
        "negative_ratio",
        "nan_ratio",
        "valence",
        "unknown_species",
        "species_order",
        "membrane",
        "gate",
        "capacity",
        "duplicate_id",
        "missing_control",
        "temperature",
        "step",
        "old_schema",
    )
    for fault in faults:
        raw = fixtures.definition()
        channel = raw["model"]["channels"][7]
        if fault == "law":
            channel["kinetic_law"] = "betse_hcn2_cAMP@1"
        elif fault == "old_model":
            raw["model"]["id"] = "resolved_tissue@4"
        elif fault == "missing_ion":
            channel["permeant_ions"].pop()
        elif fault == "duplicate_ion":
            channel["permeant_ions"].append(deepcopy(channel["permeant_ions"][0]))
        elif fault in ("ratio", "negative_ratio", "nan_ratio"):
            channel["permeant_ions"][0]["relative_permeability"] = {
                "ratio": 0.3,
                "negative_ratio": -0.2,
                "nan_ratio": float("nan"),
            }[fault]
        elif fault == "valence":
            raw["model"]["species"][3]["valence"] = 1
        elif fault == "unknown_species":
            channel["permeant_ions"][0]["species_id"] = "Cl"
        elif fault == "species_order":
            channel["permeant_ions"].reverse()
        elif fault == "membrane":
            channel["membrane_id"] = "unknown"
        elif fault == "gate":
            channel["initial_gate"][0] = 1.01
        elif fault == "capacity":
            raw["execution"]["channel_capacity"] = 9
        elif fault == "duplicate_id":
            channel["id"] = raw["model"]["channels"][0]["id"]
        elif fault == "missing_control":
            raw["experiment"]["channel_controls"].pop()
        elif fault == "temperature":
            raw["model"]["temperature_K"] = 310.15
        elif fault == "step":
            raw["execution"]["dt"] = 5e-6
        else:
            channel["species_id"] = "K"
        with pytest.raises(ConfigError):
            timeline(parse_spec(raw))
    evidence(
        "design",
        dict(
            status="passed",
            rejections=list(faults),
            gate_shape=[2, 11],
            transfer_axes=model.STATE_AXES["channel_transferred"],
        ),
    )


def test_native_laws_and_discrete_clock(tmp_path):
    output = tmp_path / "native.json"
    script = Path(__file__).resolve().parents[2] / "validation/betse/hcn_native.py"
    native_process = subprocess.run(
        ["/mnt/workspaces/Cells/venv-betse/bin/python", "-B", str(script), str(output)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    (tmp_path / "native.stdout.log").write_text(native_process.stdout)
    (tmp_path / "native.stderr.log").write_text(native_process.stderr)
    native_process.check_returncode()
    native = json.loads(output.read_text())
    assert native["version"] == "1.5.0" and native["source_sha256"] == SOURCE_HASHES
    voltage = np.asarray(native["voltage_V"])
    device = jax.devices(BACKEND)[0]
    maximum, count = 0.0, 0
    for family, code in ((1, 3), (2, 4), (4, 5)):
        row = native["families"][str(family)]
        assert row["powers"] == [1, 0] and row["time_unit"] == 1000
        assert row["ions"] == ["Na", "K", "Ca"]
        assert row["relative_permeability"] == [0.2, 1.0, 0.05]
        codes = np.full(voltage.shape, code, np.int64)
        target, tau = jax.jit(channels.kinetics)(*jax.device_put((voltage, codes), device))
        assert target.device.platform == BACKEND
        expected = [
            np.asarray(
                [[float(x) for x in hcn_reference.kinetics(v, family)[i]] for v in voltage]
            ).T
            for i in (0, 1)
        ]
        for actual, wanted in (
            (target, row["initial"]),
            (target, row["target"]),
            (tau, row["tau_s"]),
            (target, expected[0]),
            (tau, expected[1]),
        ):
            np.testing.assert_allclose(actual, wanted, rtol=5e-14, atol=5e-15)
            count += np.asarray(actual).size
        for trace in row["traces"]:
            gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), (2, voltage.size)).copy()
            for v, wanted, opened in zip(
                trace["voltage_V"], trace["gates"], trace["opening"], strict=True
            ):
                target, tau = channels.kinetics(np.asarray(v), codes, xp=np)
                dt = trace["dt_s"]
                gates = (tau * gates + dt * target) / (tau + dt)
                np.testing.assert_allclose(gates, wanted, rtol=5e-14, atol=5e-15)
                np.testing.assert_allclose(
                    channels.opening(gates, codes, xp=np), opened, rtol=5e-14, atol=5e-15
                )
                maximum = max(maximum, float(np.max(np.abs(gates - wanted))))
                count += gates.size + voltage.size
    evidence(
        "native",
        dict(
            status="passed",
            native=native,
            compared_scalars=count,
            max_gate_error=maximum,
            capture_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
            scope=(
                "Isolated pinned gate laws, ratios and native semi-implicit clock; "
                "coupled RK4 has a separate reference"
            ),
        ),
    )


def test_continuous_clamps_and_shared_gate_power():
    voltage = np.tile(np.linspace(-0.12, 0.06, 31), 3)
    codes = np.repeat(np.array([3, 4, 5]), 31)
    target, tau = channels.kinetics(voltage, codes, xp=np)
    gates = np.broadcast_to(np.array([[0.2], [0.7]]), target.shape)
    duration, steps = 0.2, (0.001, 0.0005, 0.00025)
    expected = target + (gates - target) * np.exp(-duration / tau)
    errors = []
    device = jax.devices(BACKEND)[0]
    for dt in steps:

        def solve(g, v, laws, step_size=dt):
            wanted, decay = channels.kinetics(v, laws)

            def step(old, _):
                k1 = (wanted - old) / decay
                k2 = (wanted - old - step_size * k1 / 2) / decay
                k3 = (wanted - old - step_size * k2 / 2) / decay
                k4 = (wanted - old - step_size * k3) / decay
                return old + step_size * (k1 + 2 * k2 + 2 * k3 + k4) / 6, None

            return jax.lax.scan(step, g, None, length=round(duration / step_size))[0]

        actual = jax.jit(solve)(*jax.device_put((gates, voltage, codes), device))
        assert actual.device.platform == BACKEND
        errors.append(float(np.max(np.abs(actual - expected))))
    assert errors[0] < 1e-8 and errors[-1] <= max(errors[0] * 0.02, 2e-14)
    _, derivative = jax.jvp(
        lambda v: channels.kinetics(v, codes)[0],
        (jax.device_put(voltage, device),),
        (jax.device_put(np.ones_like(voltage), device),),
    )
    assert np.isfinite(derivative).all() and np.all(np.asarray(derivative)[0] < 0)
    for h in (0.0, 0.3, 1.0):
        np.testing.assert_array_equal(
            channels.opening(np.stack((gates[0], np.full_like(voltage, h))), codes, xp=np), gates[0]
        )
    evidence(
        "clamps",
        dict(
            status="passed",
            duration_s=duration,
            dt_s=list(steps),
            max_gate_errors=errors,
            h_does_not_affect_opening=True,
            hyperpolarization_increases_target=True,
            finite_autodiff=True,
        ),
    )


def test_shared_gate_ownership_charge_and_energy():
    spec, state, p, control = initial()
    stopped = control._replace(channel=control.channel.copy())
    stopped.channel[7] = 0
    a, b = (model.readouts(state, c, p, xp=np) for c in (control, stopped))
    exact((a.derivative.channel_gate,), (b.derivative.channel_gate,))
    flux = a.derivative.channel_transferred[:, 7]
    assert np.count_nonzero(flux) == 3 and flux[2] == 0
    assert not np.any(b.derivative.channel_transferred[:, 7])
    np.testing.assert_array_equal(
        a.derivative.channel_transferred[:, :7], b.derivative.channel_transferred[:, :7]
    )
    expected = np.zeros_like(state.amount_increment)
    expected[:, 0] = -flux
    np.testing.assert_allclose(
        a.derivative.amount_increment - b.derivative.amount_increment,
        expected,
        rtol=1e-10,
        atol=3e-14,
    )
    exterior = np.zeros_like(state.extracellular_amount_increment)
    exterior[:, p.membrane_outside[p.channel_membranes[7]]] = flux
    np.testing.assert_allclose(
        (a.derivative.extracellular_amount_increment - b.derivative.extracellular_amount_increment)
        - (a.derivative.reservoir_supplied - b.derivative.reservoir_supplied),
        exterior,
        rtol=1e-10,
        atol=3e-14,
    )
    current = CHARGE_PER_FMOL * np.dot(np.asarray(spec.model.valence), flux)
    expected_current = np.zeros_like(p.membrane_area)
    expected_current[p.channel_membranes[7]] = current
    np.testing.assert_allclose(
        a.field.rates.membrane_current_A - b.field.rates.membrane_current_A,
        expected_current,
        rtol=1e-10,
        atol=3e-23,
    )
    assert (
        a.valid
        and b.valid
        and abs(a.field.energy_balance_pJ_s) < 1e-10
        and abs(b.field.energy_balance_pJ_s) < 1e-10
    )
    assert np.min(a.derivative.channel_dissipated_energy_pJ) >= -1e-12
    for field in ("channel_transferred", "channel_dissipated_energy_pJ"):
        wrong = getattr(state, field).copy()
        wrong[2, 7] = 1e-8
        changed = state._replace(**{field: wrong})
        assert not model.domain_valid(changed, p, p.active, xp=np)
        with pytest.raises(NumericalError):
            model.check_values(changed, spec)
    # Equal-valence transfers can cancel in charge while breaking species ledgers.
    wrong = state.channel_transferred.copy()
    wrong[0, 7], wrong[1, 7] = 1e-8, -1e-8
    changed = state._replace(channel_transferred=wrong)
    assert model.domain_valid(changed, p, p.active, xp=np)
    with pytest.raises(NumericalError, match="accounting"):
        model.check_values(changed, spec)
    # A constant total heat cannot hide a decrease in one species route.
    left, right = (state.channel_dissipated_energy_pJ.copy() for _ in range(2))
    left[0, 7], left[1, 7] = 2e-10, 2e-10
    right[0, 7], right[1, 7] = 3e-10, 1e-10
    rows = [state._replace(channel_dissipated_energy_pJ=v) for v in (left, right)]
    for row in rows:
        model.check_values(row, spec)
    history = model.STATE_TYPE(*(np.stack(v) for v in zip(*rows, strict=True)))
    with pytest.raises(NumericalError, match="dissipation"):
        model.check_values(history, spec)
    for index, code in ((7, 6), (10, 3)):
        bad = p.channel_laws.copy()
        bad[index] = code
        assert not model.domain_valid(state, p._replace(channel_laws=bad), p.active, xp=np)
    evidence(
        "ownership",
        dict(
            status="passed",
            shared_gate_and_block=True,
            three_species_separate_ledgers=True,
            calcium_valence=2,
            missing_routes_reject=True,
            charge_neutral_ledger_corruption_rejected=True,
            species_route_heat_decrease_rejected=True,
            energy_balance_pJ_s=float(a.field.energy_balance_pJ_s),
        ),
    )


def test_legacy_catalog_reduction():
    raw = sodium.definition()
    old, state, p, control = initial(raw)
    spec, new, q, held = initial(fixtures.convert(raw))
    a, b = (
        model.readouts(y, c, layout, xp=np)
        for y, c, layout in ((state, control, p), (new, held, q))
    )
    for field in model.STATE_TYPE._fields:
        if field in ("channel_transferred", "channel_dissipated_energy_pJ"):
            expected = np.zeros_like(getattr(b.derivative, field))
            expected[p.channel_species, np.arange(p.channel_active.size)] = getattr(
                a.derivative, field
            )
            np.testing.assert_array_equal(getattr(b.derivative, field), expected)
        else:
            np.testing.assert_array_equal(
                getattr(a.derivative, field), getattr(b.derivative, field)
            )
    exact(jax.tree.leaves(a.field), jax.tree.leaves(b.field))
    assert (
        type(p) is not type(q)
        and old == parse_spec(old.to_dict())
        and spec == parse_spec(spec.to_dict())
    )
    evidence(
        "legacy",
        dict(status="passed", original_sodium_fields="bitwise", new_layout_separates_species=True),
    )


def test_execution_plan():
    rows = []
    for arm in fixtures.ARMS:
        for dt in STEPS:
            raw = fixtures.definition(arm)
            raw["execution"]["dt"] = dt
            spec = parse_spec(raw)
            grid = timeline(spec)
            rows.append(
                dict(
                    arm=arm,
                    dt_s=dt,
                    steps=len(grid) - 1,
                    trace_bytes=trace_bytes(spec, len(grid) - 1),
                )
            )
    specs = [parse_spec(fixtures.definition(arm)) for arm in ("clamped", "release")]
    planned = plan_batch(
        BatchSpec(tuple(WorldSpec(i + 10, s) for i, s in enumerate(specs)), 2, 2048, 2**29)
    )
    evidence(
        "plan",
        dict(
            status="passed",
            grids=rows,
            two_world_padded_steps=planned.padded_step_bound,
            two_world_working_bytes=planned.estimated_working_bytes,
            scope="Host planning only",
        ),
    )


def test_compiled_invalid_trials_keep_complete_state():
    _, state, p, control = initial()
    state, p, control = jax.device_put((state, p, control), jax.devices(BACKEND)[0])
    check = jax.jit(
        lambda y, c, dt: rk4_checked_step(model.rhs, model.domain_valid, y, dt, c, p, p.active)
    )
    bad = control._replace(channel=control.channel * 0 + 1.1)
    for c, dt in ((bad, STEPS[0]), (control, 1e6)):
        kept, valid = check(state, c, dt)
        assert not valid
        exact(kept, state)
    evidence(
        "guard", dict(status="passed", invalid_controls_and_trials_keep_all_species_ledgers=True)
    )


def test_heterogeneous_world_laws_and_species(trajectories):
    baseline = trajectories["clamped"]
    for change in ("hcn_law", "sodium_route"):
        different = baseline.spec.to_dict()
        if change == "hcn_law":
            different["model"]["channels"][7]["kinetic_law"] = "betse_hcn4_m@1"
        else:
            different["model"]["channels"][0].update(
                kinetic_law="betse_nav1p2_m3h_regularized@1",
                permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
            )
        with pytest.raises((ConfigError, ValueError)):
            branch_checkpoint(baseline.spec, baseline.checkpoint_at(0.001), parse_spec(different))
    raw = baseline.spec.to_dict()
    raw["model"]["channels"][7]["kinetic_law"] = "betse_hcn4_m@1"
    raw["model"]["channels"][0].update(
        kinetic_law="betse_nav1p2_m3h_regularized@1",
        permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
    )
    spec = parse_spec(raw)
    value = run(spec)
    batch = run_batch(
        BatchSpec((WorldSpec(10, baseline.spec), WorldSpec(11, spec)), 2, 2048, 2**29)
    )
    exact(batch.worlds[10].history, baseline.history)
    exact(batch.worlds[11].history, value.history)
    c = reference.bind(spec.to_dict())
    expected = reference.integrate(spec.to_dict(), **REFERENCE_SETTINGS)
    ratio = assert_states(
        c, reference.flatten(c, vars(value.observations)), np.asarray(expected["state"])
    )
    with pytest.raises((ConfigError, ValueError)):
        branch_checkpoint(baseline.spec, baseline.checkpoint_at(0.001), spec)
    evidence(
        "world-laws",
        dict(
            status="passed",
            independently_owned_laws_and_ion_routes=True,
            max_error_over_budget=ratio,
            changed_population_branch_rejected=True,
            separately_rejected_population_changes=["hcn_law", "sodium_route"],
            comparison="bitwise to standalone worlds",
        ),
    )


trajectories = shared.trajectories
test_independent_stage_rates = shared.test_independent_stage_rates
test_compiled_smoke = shared.test_compiled_smoke
test_independent_trajectories = shared.test_independent_trajectories
test_refinement = shared.test_refinement
test_restart_branch_windows_and_identity = shared.test_restart_branch_windows_and_identity
test_worlds_ensemble_and_independent_restart = shared.test_worlds_ensemble_and_independent_restart
test_cpu_gpu = shared.test_cpu_gpu


def test_release_refinement(trajectories, references):
    shared.refinement_case(trajectories, references, "release")
