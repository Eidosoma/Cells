"""NaV1.2 source correspondence and mixed-ion resolved execution."""

import hashlib
import json
import subprocess
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.runner import run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble import ionic
from cells.models import surface_sodium as model
from cells.models.registry import get_model
from cells.processes import sodium_channels as channels
from tests.unit import test_surface_channels as shared
from tests.unit.test_surface_kinetic import exact
from validation.tissue import sodium_reference
from validation.tissue import surface_channel_fixtures as potassium_fixtures
from validation.tissue import surface_sodium_fixtures as fixtures

BACKEND, EVIDENCE = shared.BACKEND, shared.EVIDENCE
PREFIX = "resolved-sodium"
STEPS = (2.5e-6, 1.25e-6, 0.625e-6)
SOURCE_HASHES = {
    "vg_na.py": "6faa67bdc4bfd0ee35dc1cc0fd8dcd73a703ff58120d1b1968da94dac1fe8831",
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


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


def test_trajectory_batch_budget():
    shared.test_trajectory_batch_budget()


def test_design_and_rejections():
    for backend in ("cpu", "gpu"):
        raw = fixtures.definition(backend=backend)
        spec, state, p, _ = initial(raw)
        assert spec == parse_spec(spec.to_dict())
        assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
        assert spec.to_dict()["model"]["id"] == "resolved_tissue@4"
        assert (
            ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation
            == spec
        )
        np.testing.assert_array_equal(p.channel_laws, [0, 1, 0, 1, 1, 2, 2, 0])
        for index, code in ((5, 3), (7, 2)):
            corrupt = p.channel_laws.copy()
            corrupt[index] = code
            assert not model.domain_valid(state, p._replace(channel_laws=corrupt), p.active, xp=np)
    faults = (
        "unknown_law",
        "v2_identity",
        "v3_identity",
        "sodium_as_K",
        "potassium_as_Na",
        "missing_species",
        "bad_gate",
        "nan_gate",
        "temperature",
        "step",
        "duplicate",
        "capacity",
        "control",
    )
    for fault in faults:
        raw = fixtures.definition()
        m, e, x = raw["model"], raw["experiment"], raw["execution"]
        ch = m["channels"][5]
        if fault == "unknown_law":
            ch["kinetic_law"] = "unregistered"
        elif fault == "v2_identity":
            m["id"] = "resolved_tissue@2"
        elif fault == "v3_identity":
            m["id"] = "resolved_tissue@3"
        elif fault == "sodium_as_K":
            ch["species_id"] = "K"
        elif fault == "potassium_as_Na":
            m["channels"][1]["species_id"] = "Na"
        elif fault == "missing_species":
            ch["species_id"] = "absent"
        elif fault == "bad_gate":
            ch["initial_gate"][1] = 1.1
        elif fault == "nan_gate":
            ch["initial_gate"][0] = float("nan")
        elif fault == "temperature":
            m["temperature_K"] = 310.0
        elif fault == "step":
            x["dt"] = 5e-6
        elif fault == "duplicate":
            ch["id"] = m["channels"][0]["id"]
        elif fault == "capacity":
            x["channel_capacity"] = 6
        else:
            e["channel_controls"][5]["schedule"][0]["availability"] = -0.1
        with pytest.raises(ConfigError):
            timeline(parse_spec(raw))
    evidence("design", dict(status="passed", inputs=spec.to_dict(), rejected=list(faults)))


def test_native_law_and_discrete_clock(tmp_path):
    output = tmp_path / "native.json"
    worker = Path(__file__).resolve().parents[2] / "validation/betse/sodium_native.py"
    process = subprocess.run(
        ["/mnt/workspaces/Cells/venv-betse/bin/python", "-B", str(worker), str(output)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    (tmp_path / "native.stdout.log").write_text(process.stdout)
    (tmp_path / "native.stderr.log").write_text(process.stderr)
    process.check_returncode()
    native = json.loads(output.read_text())
    assert native["version"] == "1.5.0" and native["source_sha256"] == SOURCE_HASHES
    assert native["powers"] == [3, 1]
    v = np.asarray(native["voltage_V"])
    codes = np.full(v.shape, 2, dtype=np.int64)
    target, tau = jax.jit(channels.kinetics)(*jax.device_put((v, codes), jax.devices(BACKEND)[0]))
    assert target.device.platform == BACKEND
    stable_tau = np.asarray(tau)
    source_target, source_tau = sodium_reference.source_float_parameters(v)
    decimal_target, decimal_tau = (
        np.asarray(
            [[float(x) for x in sodium_reference.kinetics(float(value))[i]] for value in v]
        ).T
        for i in (0, 1)
    )
    # Retain every source sample. Near a removable zero, direct 1-exp
    # subtraction loses precision: check the stable implementation against
    # Decimal, and explain the native value with its own float arithmetic.
    distances = np.abs(
        (v[:, None] - np.asarray([-0.025, -0.040, -0.065000123]))
        / np.asarray([0.009, 0.005, 0.005])
    )
    regular = np.all(distances >= 1e-4, axis=1)
    assert np.count_nonzero(~regular) == 1
    for actual, wanted in ((target, decimal_target), (tau, decimal_tau)):
        np.testing.assert_allclose(actual, wanted, rtol=3e-14, atol=3e-15)
    count, maximum = 0, 0.0
    for actual, source_value, expected in (
        (target, source_target, native["target"]),
        (target, source_target, native["initial"]),
        (tau, source_tau, native["tau_s"]),
    ):
        expected = np.asarray(expected)
        np.testing.assert_allclose(source_value, expected, rtol=5e-14, atol=5e-15)
        np.testing.assert_allclose(
            np.asarray(actual)[:, regular], expected[:, regular], rtol=5e-14, atol=5e-15
        )
        count += actual[:, regular].size
    for trace in native["traces"]:
        gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), (2, v.size)).copy()
        for voltage, expected, opened in zip(
            trace["voltages_V"], trace["gates"], trace["opening"], strict=True
        ):
            target, tau = channels.kinetics(np.asarray(voltage), codes, xp=np)
            dt = trace["dt_s"]
            gates = (gates * tau + dt * target) / (tau + dt)
            np.testing.assert_allclose(gates, expected, rtol=5e-14, atol=5e-15)
            np.testing.assert_allclose(
                channels.opening(gates, codes, xp=np), opened, rtol=5e-14, atol=5e-15
            )
            maximum = max(maximum, float(np.max(np.abs(gates - expected))))
            count += gates.size + v.size
    finite = np.asarray(native["singular_probes"]["finite"])
    assert not finite[0, 0] and not finite[2, 0]
    assert not finite[3, 1] and not finite[3, 2]
    evidence(
        "native",
        dict(
            status="passed",
            native=native,
            compared_scalars=count,
            max_gate_error=maximum,
            capture_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
            finite_native_precision=dict(
                dimensionless_distance_threshold=1e-4,
                direct_comparison_voltage_V=v[regular].tolist(),
                cancellation_voltage_V=v[~regular].tolist(),
                native_tau_s=np.asarray(native["tau_s"])[:, ~regular].tolist(),
                stable_tau_s=stable_tau[:, ~regular].tolist(),
                decimal_tau_s=decimal_tau[:, ~regular].tolist(),
                source_arithmetic_replayed_all_finite_samples=True,
                production_compared_to_decimal_at_all_finite_samples=True,
            ),
            scope=(
                "Isolated finite native equations and native gate clock; "
                "singular probes retained separately"
            ),
        ),
    )


def test_continuous_limits_clamps_and_gate_power():
    centers = np.asarray([-0.025, -0.040, -0.065000123])
    voltage = np.unique(
        np.r_[np.linspace(-0.120, 0.060, 37), centers, centers - 1e-12, centers + 1e-12]
    )
    target, tau = channels.nav1p2_kinetics(voltage, xp=np)
    for i, v in enumerate(voltage):
        expected = sodium_reference.kinetics(float(v))
        np.testing.assert_allclose(
            target[:, i], [float(x) for x in expected[0]], rtol=3e-14, atol=3e-15
        )
        np.testing.assert_allclose(
            tau[:, i], [float(x) for x in expected[1]], rtol=3e-14, atol=3e-15
        )
    assert np.all(tau > 0) and np.all((target >= 0) & (target <= 1))
    device = jax.devices(BACKEND)[0]
    centers_device = jax.device_put(centers, device)
    limits = jax.jit(channels.nav1p2_kinetics)(centers_device)
    derivatives = jax.jit(jax.jacfwd(channels.nav1p2_kinetics))(centers_device)
    assert all(np.all(np.isfinite(v)) for v in (*limits, *derivatives))
    for got, wanted in zip(limits, channels.nav1p2_kinetics(centers, xp=np), strict=True):
        np.testing.assert_allclose(got, wanted, rtol=3e-14, atol=3e-15)
    gates = np.asarray([[0.2, 0.2, 0.2], [0.7, 0.7, 0.7]])
    np.testing.assert_allclose(
        channels.opening(gates, np.asarray([0, 1, 2]), xp=np), [0.14, 0.098, 0.0056], rtol=1e-15
    )
    initial_gates = np.broadcast_to(np.asarray([[0.2], [0.7]]), target.shape)
    expected = target + (initial_gates - target) * np.exp(-0.002 / tau)
    errors = []
    for dt in STEPS:

        def solve(g, v, step_size=dt):
            t, decay = channels.nav1p2_kinetics(v)

            def step(old, unused):
                k1 = (t - old) / decay
                k2 = (t - old - step_size * k1 / 2) / decay
                k3 = (t - old - step_size * k2 / 2) / decay
                k4 = (t - old - step_size * k3) / decay
                return old + step_size * (k1 + 2 * k2 + 2 * k3 + k4) / 6, None

            return jax.lax.scan(step, g, None, length=round(0.002 / step_size))[0]

        actual = jax.jit(solve)(*jax.device_put((initial_gates, voltage), device))
        errors.append(float(np.max(np.abs(actual - expected))))
    assert errors[0] < 1e-8
    assert errors[-1] <= max(errors[0] * 0.02, 2e-14)
    evidence(
        "clamps",
        dict(
            status="passed",
            voltage_V=voltage.tolist(),
            dt_s=list(STEPS),
            max_gate_errors=errors,
            singular_voltage_V=centers.tolist(),
            finite_autodiff=True,
            opening="m**3*h",
            reference="80-digit Decimal rate limits and analytic exponential clamp",
        ),
    )


def test_sodium_species_ownership_and_selective_block():
    spec, state, p, control = initial()
    blocked = control._replace(channel=control.channel.copy())
    blocked.channel[5] = 0.0
    a, b = (model.readouts(state, c, p, xp=np) for c in (control, blocked))
    exact((a.derivative.channel_gate,), (b.derivative.channel_gate,))
    exact((a.derivative.channel_transferred[:5],), (b.derivative.channel_transferred[:5],))
    assert b.derivative.channel_transferred[5] == 0
    assert a.derivative.channel_transferred[5] != 0
    expected_cell = np.zeros_like(a.derivative.amount_increment)
    expected_cell[spec.model.species_ids.index("Na"), 0] = -a.derivative.channel_transferred[5]
    np.testing.assert_allclose(
        a.derivative.amount_increment - b.derivative.amount_increment,
        expected_cell,
        rtol=1e-10,
        atol=3e-14,
    )
    expected_outside = np.zeros_like(a.derivative.extracellular_amount_increment)
    owner = p.membrane_outside[p.channel_membranes[5]]
    expected_outside[spec.model.species_ids.index("Na"), owner] = a.derivative.channel_transferred[
        5
    ]
    np.testing.assert_allclose(
        (a.derivative.extracellular_amount_increment - b.derivative.extracellular_amount_increment)
        - (a.derivative.reservoir_supplied - b.derivative.reservoir_supplied),
        expected_outside,
        rtol=1e-10,
        atol=3e-14,
    )
    assert a.valid and b.valid
    assert abs(a.field.energy_balance_pJ_s) < 1e-10
    assert abs(b.field.energy_balance_pJ_s) < 1e-10
    evidence(
        "ownership",
        dict(
            status="passed",
            sodium_only_transfer=True,
            gates_keep_evolving=True,
            potassium_populations_unchanged=True,
        ),
    )


def test_prior_catalogs_and_compositions():
    raw = potassium_fixtures.definition()
    old, state, p, c = initial(raw)
    raw["model"]["id"] = "resolved_tissue@4"
    raw["execution"]["dt"] = STEPS[0]
    new, newer, q, d = initial(raw)
    assert type(p) is not type(q)
    exact(newer, state)
    a, b = model.readouts(state, c, p, xp=np), model.readouts(newer, d, q, xp=np)
    exact(a.derivative, b.derivative)
    exact(jax.tree.leaves(a.field), jax.tree.leaves(b.field))
    assert old == parse_spec(old.to_dict()) and new == parse_spec(new.to_dict())
    # The older layout must still reject the new NaV numeric law code.
    bad = p.channel_laws.copy()
    bad[0] = 2
    assert not model.domain_valid(state, p._replace(channel_laws=bad), p.active, xp=np)
    shared.test_legacy_v2_and_kv_only_reduction()
    shared.test_prior_resolved_compositions()
    evidence(
        "legacy-catalog",
        dict(status="passed", potassium_only_comparison="bitwise", older_layout_rejects_nav=True),
    )


def test_world_specific_species_and_laws():
    raw = fixtures.definition("clamped", backend=BACKEND)
    raw["experiment"].update(end_time=50e-6, observation_times=[0.0, 25e-6, 50e-6])
    first = parse_spec(raw)
    raw["model"]["channels"][5].update(species_id="K", kinetic_law="betse_kv1p5_mh@1")
    second = parse_spec(raw)
    expected = [run(s) for s in (first, second)]
    assert np.any(
        expected[0].final.state.amount_increment != expected[1].final.state.amount_increment
    )
    batch = run_batch(BatchSpec((WorldSpec(11, first), WorldSpec(27, second)), 2, 1024, 2**29))
    for identity, value in zip((11, 27), expected, strict=True):
        exact(batch.worlds[identity].history, value.history)
    evidence(
        "world-laws",
        dict(
            status="passed",
            world_ids=[11, 27],
            different_species_and_laws=True,
            comparison="bitwise",
        ),
    )


# Reuse complete trajectories, accounting, replay, worlds and CPU/L4 comparison.
# Only fixtures, evidence names, model identity and finer timesteps differ.
trajectories = shared.trajectories
references = shared.references
test_independent_stage_rates = shared.test_independent_stage_rates
test_blocked_gates_additive_populations_and_guard = (
    shared.test_blocked_gates_additive_populations_and_guard
)
test_compiled_smoke = shared.test_compiled_smoke
test_independent_trajectories = shared.test_independent_trajectories
test_refinement = shared.test_refinement


def test_release_refinement(trajectories, references):
    shared.refinement_case(trajectories, references, "release")


test_restart_branch_windows_and_identity = shared.test_restart_branch_windows_and_identity
test_worlds_ensemble_and_independent_restart = shared.test_worlds_ensemble_and_independent_restart
test_cpu_gpu = shared.test_cpu_gpu
