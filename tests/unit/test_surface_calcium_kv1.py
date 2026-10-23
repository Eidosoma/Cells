"""Kv1 source correspondence and composition through the existing owned tissue."""

import hashlib
import json
import subprocess
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly_cluster.spec import channel_owners
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_calcium_spec import ionic_spec
from cells.models import surface_calcium_hcn as prior
from cells.models import surface_calcium_kv1 as model
from cells.models import surface_kv1 as ionic_model
from cells.models.registry import get_model
from cells.processes import hcn_channels
from cells.processes import kv1_channels as channels
from tests.unit import test_surface_calcium as shared
from tests.unit import test_surface_calcium_hcn as hcn
from tests.unit import test_surface_calcium_sodium as sodium
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import kv1_reference
from validation.tissue import surface_calcium_hcn_fixtures as prior_fixtures
from validation.tissue import surface_calcium_kv1_fixtures as fixtures
from validation.tissue import surface_calcium_reference as reference
from validation.tissue import surface_kinetic_reference as ionic_reference

BACKEND, EVIDENCE = shared.BACKEND, shared.EVIDENCE
PREFIX = "resolved-calcium-kv1"
SOURCE_HASHES = {
    "vg_k.py": "89412aff6163dfe4ccf61afb82418a788ff8e10fbe2ec8cda24c498316b4842f",
    "channelsabc.py": "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4",
}


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    with pytest.MonkeyPatch.context() as patch:
        for module in (shared, hcn, sodium):
            patch.setattr(module, "model", model)
            patch.setattr(module, "fixtures", fixtures)
            patch.setattr(module, "PREFIX", PREFIX)
        yield


initial = shared.initial
assert_multi_ion_report = hcn.assert_multi_ion_report
test_independent_stage_rates_and_accounting = shared.test_independent_stage_rates_and_accounting
test_free_ion_ownership_and_shared_population_block = (
    hcn.test_free_ion_ownership_and_shared_population_block
)
test_species_route_dissipation_cannot_decrease = hcn.test_species_route_dissipation_cannot_decrease
test_initial_assembly_report_and_planning = hcn.test_initial_assembly_report_and_planning
test_compiled_smoke_reference_and_checkpoint = sodium.test_compiled_smoke_reference_and_checkpoint


def evidence(name, value):
    shared.evidence(PREFIX + "-" + name, value)


def test_identity_catalogs_and_rejections():
    for backend in ("cpu", "gpu"):
        spec, state, p, _ = initial(fixtures.definition(backend=backend))
        assert spec == parse_spec(spec.to_dict())
        assert get_model(spec.model) is model and type(p) is model.LAYOUT_TYPE
        assert spec.to_dict()["model"]["id"] == "resolved_calcium@5"
        assert spec.to_dict()["model"]["ionic"]["id"] == "resolved_tissue@6"
        assert state.channel_gate.shape == (2, 16)
        assert (
            state.channel_transferred.shape == state.channel_dissipated_energy_pJ.shape == (4, 16)
        )
        np.testing.assert_array_equal(
            p.channel_laws, [0, 1, 0, 1, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0]
        )
        np.testing.assert_array_equal(
            p.channel_relative_permeability[:, 10:15], np.tile([[0], [1], [0], [0]], (1, 5))
        )
        for index, code in ((10, 11), (15, 6)):
            invalid = p.channel_laws.copy()
            invalid[index] = code
            assert not model.domain_valid(state, p._replace(channel_laws=invalid), p.active, xp=np)
    rejected = []
    for fault in ("outer", "inner", "old_catalog", "species", "ratio", "capacity", "step"):
        raw = fixtures.definition()
        m, x = raw["model"], raw["execution"]
        if fault in ("outer", "old_catalog"):
            m["id"] = "resolved_calcium@4"
        if fault in ("inner", "old_catalog"):
            m["ionic"]["id"] = "resolved_tissue@5"
        if fault == "species":
            m["ionic"]["channels"][10]["permeant_ions"][0]["species_id"] = "Na"
        elif fault == "ratio":
            m["ionic"]["channels"][10]["permeant_ions"][0]["relative_permeability"] = 0.5
        elif fault == "capacity":
            x["channel_capacity"] = 14
        elif fault == "step":
            x["dt"] = 5e-6
        with pytest.raises(ConfigError):
            shared.timeline(parse_spec(raw))
        rejected.append(fault)
    evidence("design", dict(status="passed", rejected=rejected, inputs=spec.to_dict()))


def test_previous_hcn_reduction():
    old, state, p, control = initial(prior_fixtures.definition())
    raw = old.to_dict()
    raw["model"]["id"], raw["model"]["ionic"]["id"] = "resolved_calcium@5", "resolved_tissue@6"
    new, newer, q, held = initial(raw)
    assert get_model(old.model) is prior and type(p) is prior.LAYOUT_TYPE
    first, second = prior.readouts(state, control, p, xp=np), model.readouts(newer, held, q, xp=np)
    exact(state, newer)
    exact(first.derivative, second.derivative)
    exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    assert parse_spec(new.to_dict()) == new
    for process in (np,):
        voltage = np.linspace(-0.12, 0.06, 61)
        for code in range(6):
            codes = np.full(voltage.shape, code, np.int64)
            exact(
                channels.kinetics(voltage, codes, xp=process),
                hcn_channels.kinetics(voltage, codes, xp=process),
            )
    evidence(
        "legacy",
        dict(status="passed", old_state_rates_fields="bitwise", old_catalog_preserved=True),
    )


def test_standalone_shared_catalog():
    spec = ionic_spec(parse_spec(fixtures.definition()))
    assert parse_spec(spec.to_dict()) == spec and get_model(spec.model) is ionic_model
    state, p = ionic_model.initial_values(spec)
    controls = shared.control_values(spec, [0.0])
    held = type(controls)(*(v[0] for v in controls))
    actual = ionic_model.readouts(state, held, p, xp=np)
    c = ionic_reference.bind(spec.to_dict())
    expected, _, proof = ionic_reference.evaluate(c, ionic_reference.initial(c), 0.0)
    ratio = assert_states(
        c,
        ionic_reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert actual.valid and type(p) is ionic_model.LAYOUT_TYPE
    evidence(
        "standalone-stage",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            independent_root=proof,
        ),
    )


def test_assembly_controls_all_kv1_owners():
    spec = shared.parse_assembly(fixtures.assembly_definition())
    _, state, p, control = initial(spec.ionic.to_dict())
    owners = channel_owners(spec)
    assert set(owners[10:15]) == {0, 1}
    rows = []
    for stopped_owner in (0, 1):
        levels = np.ones(2)
        levels[stopped_owner] = 0.0
        held = control._replace(channel=control.channel * levels[owners])
        before, after = (model.readouts(state, v, p, xp=np) for v in (control, held))
        assert np.count_nonzero(before.derivative.channel_transferred[1, 10:15]) == 5
        assert not np.any(after.derivative.channel_transferred[:, owners == stopped_owner])
        exact(
            after.derivative.channel_transferred[:, owners != stopped_owner],
            before.derivative.channel_transferred[:, owners != stopped_owner],
        )
        exact(after.derivative.channel_gate, before.derivative.channel_gate)
        c = reference.bind(spec.ionic.to_dict())
        expected, _, proof = reference.evaluate(c, reference.initial(c), 0.0, channel_levels=levels)
        ratio = assert_states(
            c,
            reference.flatten(c, after.derivative._asdict()),
            expected,
            atol=3e-12,
            charge_atol=3e-23,
            rtol=3e-10,
        )
        rows.append(
            dict(stopped_owner=stopped_owner, max_error_over_budget=ratio, independent_root=proof)
        )
    evidence(
        "assembly-owner-control",
        dict(status="passed", cases=rows, channel_owner_indices=owners.tolist()),
    )


def test_native_laws_and_discrete_clock(tmp_path):
    output = tmp_path / "native.json"
    script = Path(__file__).resolve().parents[2] / "validation/betse/kv1_native.py"
    child = subprocess.run(
        ["/mnt/workspaces/Cells/venv-betse/bin/python", "-B", str(script), str(output)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    (tmp_path / "native.stdout.log").write_text(child.stdout)
    (tmp_path / "native.stderr.log").write_text(child.stderr)
    child.check_returncode()
    native = json.loads(output.read_text())
    assert native["version"] == "1.5.0" and native["source_sha256"] == SOURCE_HASHES
    voltage = np.asarray(native["voltage_V"])
    device = jax.devices(BACKEND)[0]
    maximum, count = 0.0, 0
    for family in range(1, 7):
        law = next(law for law, f in kv1_reference.LAWS.items() if f == family)
        codes = np.full(voltage.shape, channels.LAW_CODES[law], np.int64)
        row = native["families"][str(family)]
        assert row["powers"] == [1, 2 if family == 1 else 1] and row["time_unit"] == 1000
        assert row["ions"] == ["K"] and row["relative_permeability"] == [1.0]
        target, tau = jax.jit(channels.kinetics)(*jax.device_put((voltage, codes), device))
        assert target.device.platform == BACKEND and np.all(np.asarray(tau) > 0)
        expected = [
            np.asarray(
                [[float(x) for x in kv1_reference.kinetics(v, family)[i]] for v in voltage]
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
                "Six isolated source laws and native semi-implicit clocks; "
                "continuous coupled RK4 is checked separately"
            ),
        ),
    )


def test_continuous_clamps_gate_powers_and_gradients():
    voltage = np.tile(np.linspace(-0.12, 0.06, 31), 5)
    codes = np.repeat(np.arange(6, 11), 31)
    target, tau = channels.kinetics(voltage, codes, xp=np)
    gates = np.broadcast_to(np.array([[0.2], [0.7]]), target.shape)
    duration, steps = 0.003, (50e-6, 25e-6, 12.5e-6)
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
    assert errors[0] < 3e-7 and errors[-1] <= max(errors[0] * 0.02, 2e-14)
    _, gradient = jax.jvp(
        lambda v: channels.kinetics(v, codes)[0],
        (jax.device_put(voltage, device),),
        (jax.device_put(np.ones_like(voltage), device),),
    )
    assert (
        np.isfinite(gradient).all()
        and np.all(np.asarray(gradient)[0] > 0)
        and np.all(np.asarray(gradient)[1] < 0)
    )
    for h in (0.0, 0.3, 1.0):
        g = np.stack((gates[0], np.full_like(voltage, h)))
        opened = jax.jit(channels.opening)(*jax.device_put((g, codes), device))
        wanted = np.array(
            [
                float(kv1_reference.opening(pair, family))
                for pair, family in zip(g.T, np.repeat((1, 2, 3, 4, 6), 31), strict=True)
            ]
        )
        np.testing.assert_allclose(opened, wanted, rtol=3e-15, atol=3e-16)
    evidence(
        "clamps",
        dict(
            status="passed",
            duration_s=duration,
            dt_s=list(steps),
            max_gate_errors=errors,
            all_gate_powers_checked=True,
            finite_gradients=True,
            scope="Analytic clamp/refinement controls, not biological cases",
        ),
    )
