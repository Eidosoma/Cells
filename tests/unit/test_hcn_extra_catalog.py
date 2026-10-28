"""56-law integration: source gates, physical owners, versioning and replay."""

from copy import deepcopy
from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.controls import modulate
from cells.assembly_cluster.spec import channel_owners
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.runner import run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.ensemble import ionic
from cells.ensemble.cluster import aggregate
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_calcium_hcn_extra, surface_kinetic
from cells.models.registry import get_model
from cells.processes import hcn_extra_catalog as catalog
from cells.processes import hcn_extra_channels as channel
from cells.processes import morris_lecar_catalog as old_catalog
from tests.unit.test_morris_lecar_catalog import compare, perturb_free_calcium
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.channels import hcn_extra_reference as scalar
from validation.tissue import hcn_extra_catalog_fixtures as fixtures
from validation.tissue import morris_lecar_catalog_fixtures as previous
from validation.tissue import surface_calcium_energy_reference as energy_reference


def initial(family, raw=None):
    spec = parse_spec(fixtures.definition(family) if raw is None else raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    table = control_values(spec, [0.0])
    return spec, model, state, p, type(table)(*(v[0] for v in table))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_version_projection_roundtrip_and_batch_registration(family, backend):
    raw = fixtures.definition(family, backend=backend)
    spec, model, state, p, _ = initial(family, raw)
    assert model.MODEL_ID == fixtures.MODEL_IDS[family] and type(p) is model.LAYOUT_TYPE
    assert parse_spec(spec.to_dict()) == spec
    assert len(state) == dict(ionic=19, calcium=34, energy=38)[family]
    assert len(spec.model.channels) == 63
    assert set(p.channel_laws[p.channel_active]) == set(range(56))
    view = (
        p
        if family == "ionic"
        else surface_calcium_hcn_extra.ionic_layout(
            state if family == "calcium" else model.prior_state(state),
            p if family == "calcium" else model.prior_layout(p),
            xp=np,
        )
    )
    assert surface_kinetic.channel_process(view) is catalog
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    timeline(spec)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_stage_matches_independent_reference(family, arm, padded):
    raw = fixtures.definition(family, arm, padded=padded)
    spec, model, state, p, u = initial(family, raw)
    value = model.readouts(state, u, p, xp=np)
    checked = compare(family, spec, state, value.derivative)
    assert value.valid and model.control_domain_valid(state, u, p, p.active, xp=np)
    assert abs(value.field.energy_balance_pJ_s) < 1e-10
    absent = ~(catalog.gate_active(p.channel_laws, xp=np) & p.channel_active)
    assert np.all(value.derivative.channel_gate[absent] == 0)
    model.check_values(state, spec)
    if arm in ("blocked", "empty"):
        assert not np.any(value.derivative.channel_transferred)
    evidence(
        f"hcn-extra-stage-{family}-{arm}-{padded}", dict(status="passed", inputs=raw, **checked)
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_previous_53_laws_keep_bitwise_states_fields_and_rates(family):
    raw = previous.definition(family)
    old_spec, old_model, old_state, p, u = initial(family, raw)
    raw["model"]["id"] = fixtures.MODEL_IDS[family]
    if family != "ionic":
        raw["model"]["ionic"]["id"] = fixtures.MODEL_IDS["ionic"]
    spec, model, state, q, v = initial(family, raw)
    exact(old_state, state)
    for changed in (False, True):
        a = perturb_free_calcium(family, old_spec, old_state, p) if changed else old_state
        b = perturb_free_calcium(family, spec, state, q) if changed else state
        first, second = old_model.readouts(a, u, p, xp=np), model.readouts(b, v, q, xp=np)
        exact(first.derivative, second.derivative)
        exact(jax.tree.leaves(first.field), jax.tree.leaves(second.field))
    assert not old_catalog.valid_codes(np.arange(56), xp=np)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault",
    [
        "outer_version",
        "inner_version",
        "law",
        "ratio",
        "route",
        "leak_gate",
        "missing_gate",
        "step",
    ],
)
def test_invalid_declarations_cannot_enter_new_model(family, fault):
    raw = fixtures.definition(family)
    m = raw["model"] if family == "ionic" else raw["model"]["ionic"]
    if fault == "outer_version":
        raw["model"]["id"] = previous.MODEL_IDS[family]
    elif fault == "inner_version":
        m["id"] = previous.MODEL_IDS["ionic"]
    elif fault == "law":
        m["channels"][-1]["kinetic_law"] = "invented_hcn@1"
    elif fault == "ratio":
        m["channels"][-3]["permeant_ions"][0]["relative_permeability"] = 0.2
    elif fault == "route":
        m["channels"][-1]["permeant_ions"].pop()
    elif fault == "leak_gate":
        m["channels"][-3]["initial_gate"] = [1.0, 1.0]
    elif fault == "missing_gate":
        m["channels"][-1]["initial_gate"] = [0.2]
    else:
        raw["execution"]["dt"] = 2.5e-6
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("family", ["calcium", "energy"])
@pytest.mark.parametrize("code", [53, 54, 55])
def test_three_ions_reach_actual_calcium_owner_without_direct_fuel_cost(family, code):
    spec, model, state, p, u = initial(family)
    slot = int(np.flatnonzero(p.channel_laws == code)[0])
    patch = int(p.channel_membranes[slot])
    owner, outside = int(p.membrane_cell[patch]), int(p.membrane_outside[patch])
    held = u._replace(channel=u.channel.copy())
    held.channel[slot] = 0.0
    before, after = (model.readouts(state, c, p, xp=np).derivative for c in (u, held))
    flux = before.channel_transferred[:, slot]
    assert {s for s, f in zip(spec.model.species_ids, flux, strict=True) if f != 0} == {
        "Na",
        "K",
        "Ca",
    }
    expected = np.zeros_like(state.chemical_amount_increment)
    expected[owner, p.ionic_species, int(p.er_cytosol[owner])] = -flux
    np.testing.assert_allclose(
        before.chemical_amount_increment - after.chemical_amount_increment,
        expected,
        atol=3e-14,
        rtol=3e-10,
    )
    for name, index, sign in (
        ("amount_increment", owner, -1),
        ("extracellular_amount_increment", outside, 1),
    ):
        expected = np.zeros_like(getattr(state, name))
        expected[:, index] = sign * flux
        np.testing.assert_allclose(
            getattr(before, name) - getattr(after, name), expected, atol=3e-14, rtol=3e-10
        )
    if family == "energy":
        exact((before.energy_amount_increment_fmol,), (after.energy_amount_increment_fmol,))


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_blocking_transport_keeps_source_gate_clocks(family):
    _, model, state, p, u = initial(family)
    selected = p.channel_laws >= 53
    held = u._replace(channel=u.channel.copy())
    held.channel[selected] = 0.0
    a, b = (model.readouts(state, c, p, xp=np) for c in (u, held))
    assert a.valid and b.valid
    np.testing.assert_array_equal(a.derivative.channel_gate, b.derivative.channel_gate)
    assert np.all(b.derivative.channel_transferred[:, selected] == 0)
    assert np.all(b.derivative.channel_gate[0, p.channel_laws >= 54] != 0)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "fault", ["leak_gate", "nan_gate", "pad_law", "pad_control", "unknown_law", "hidden_chloride"]
)
def test_invalid_state_cannot_hide_in_blocked_channels(family, fault):
    spec, model, state, p, u = initial(family, fixtures.definition(family, "blocked"))
    slot = int(np.flatnonzero(p.channel_laws == 53)[0])
    if fault == "leak_gate":
        state.channel_gate[0, slot] = 1e-12
    elif fault == "nan_gate":
        state.channel_gate[0, slot] = np.nan
    elif fault == "pad_law":
        p.channel_laws[-1] = 55
    elif fault == "pad_control":
        u.channel[-1] = 0.1
    elif fault == "unknown_law":
        p.channel_laws[slot] = 56
    else:
        state.channel_transferred[spec.model.species_ids.index("Cl"), slot] = 1e-5
    assert not model.control_domain_valid(state, u, p, p.active, xp=np)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_snapshot_rejects_old_layout_even_with_identical_shapes(family, tmp_path):
    spec, model, state, p, _ = initial(family, fixtures.compact_probe(family))
    point = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    write_snapshot(tmp_path / "initial", spec, point)
    saved = load_snapshot(tmp_path / "initial")
    assert saved.spec == spec and type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    exact(saved.checkpoint.state, state)
    exact(saved.checkpoint.layout, p)
    old_type = get_model(parse_spec(previous.definition(family)).model).LAYOUT_TYPE
    with pytest.raises(ConfigError, match="state/layout"):
        validate_checkpoint(
            spec, replace(point, layout=old_type(*(getattr(p, k) for k in old_type._fields)))
        )


@pytest.mark.parametrize("family", ["calcium", "energy"])
def test_assembly_owner_controls_report_and_checkpoint(family, tmp_path):
    spec = parse_assembly(fixtures.assembly_definition(family))
    _, model, state, p, u = initial(family, spec.ionic.to_dict())
    levels = np.array([0.0, 1.0])
    held = modulate(u, levels, channel_owners(spec))
    actual = model.readouts(state, held, p, xp=np)
    assert actual.valid
    compare(family, spec.ionic, state, actual.derivative, levels=levels)
    combined_state = assembly.initial_state(spec)
    report = assembly.summary(spec, combined_state) | dict(
        arm=family, wall_start=0.0, wall_end=1.0, execute_seconds=0.0
    )
    assert report["physical_model"] == fixtures.MODEL_IDS[family]
    assert aggregate([report, report])[family]["worlds"] == 2 * spec.pool.worlds
    for key in ("ip3", "calcium", "channel_transfer_axes", "channel_species_ids") + (
        ("finite_energy",) if family == "energy" else ()
    ):
        wrong = deepcopy(report)
        wrong.pop(key)
        with pytest.raises(ValueError):
            aggregate([report, wrong])
    write_checkpoint(tmp_path / "assembly", spec, combined_state, backend="cpu")
    restored, newer, _ = load_checkpoint(tmp_path / "assembly", backend="cpu")
    assert restored == spec
    exact(flatten(newer).values(), flatten(combined_state).values())


def test_compiled_two_world_full_38_field_stage_and_failure_isolation():
    spec, model, state, p, u = initial("energy")
    changed = perturb_free_calcium("energy", spec, state, p)
    changed.channel_gate[:, p.channel_laws == 55] = [[0.51], [0.8]]
    states = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, changed, strict=True)))
    controls = type(u)(*(np.stack((v, v)) for v in u))
    evaluate = jax.jit(
        jax.vmap(
            lambda y, c, q: (
                model.rhs(y, c, q, q.active),
                model.control_domain_valid(y, c, q, q.active),
            ),
            in_axes=(0, 0, None),
        )
    )
    got, valid = evaluate(states, controls, p)
    assert np.all(valid)
    checks = [
        compare(
            "energy",
            spec,
            model.STATE_TYPE(*(v[i] for v in states)),
            model.STATE_TYPE(*(v[i] for v in got)),
        )
        for i in (0, 1)
    ]
    bad = states._replace(channel_gate=states.channel_gate.copy())
    bad.channel_gate[1, 0, np.flatnonzero(p.channel_laws == 53)[0]] = 0.25
    failed, valid = evaluate(bad, controls, p)
    assert np.array_equal(np.asarray(valid), [True, False])
    assert all(np.isnan(v[1]).all() for v in failed)
    exact((v[0] for v in failed), (v[0] for v in got))
    evidence(
        "hcn-extra-compiled-stage",
        dict(
            status="passed", inputs=spec.to_dict(), world_checks=checks, invalid_world_isolated=True
        ),
    )


def test_compiled_50us_coupled_trajectory_and_final_snapshot(tmp_path):
    raw = fixtures.compact_probe("energy")
    result = run(parse_spec(raw))
    c = energy_reference.bind(raw)
    expected = energy_reference.integrate(raw)
    actual = energy_reference.flatten(c, vars(result.observations))
    target = np.asarray(expected["state"])
    report = dict(
        status="captured",
        inputs=raw,
        diagnostics=result.diagnostics,
        independent_reference={
            k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in expected.items()
        },
        scope="50 us live coupling; slow HCN relaxation is separate component evidence",
    )
    evidence(
        "hcn-extra-trajectory",
        report,
        dict(observed=actual, reference=target, signed_error=actual - target),
    )
    ratio = assert_states(c, actual, target)
    absent = ~(
        catalog.gate_active(result.final.layout.channel_laws, xp=np)
        & result.final.layout.channel_active
    )
    assert np.all(result.observations.channel_gate[:, absent] == 0)
    write_run(tmp_path / "run", result)
    saved = load_snapshot(tmp_path / "run/checkpoint_final")
    assert (
        saved.spec == result.spec
        and type(saved.checkpoint.layout) is get_model(result.spec.model).LAYOUT_TYPE
    )
    exact(saved.checkpoint.state, result.final.state)
    exact(saved.checkpoint.layout, result.final.layout)
    evidence(
        "hcn-extra-trajectory",
        report | dict(status="passed", max_error_over_budget=ratio, complete_final_snapshot=True),
    )


def test_scalar_vector_broadcast_and_jit_kinetics_match_independent_source():
    voltage = np.linspace(-0.12, 0.06, 37)[:, None]
    codes = np.array([55, 53, 54])
    evaluate = jax.jit(lambda v, c: (channel.initial_gates(v, c), channel.kinetics(v, c)))
    native_initial, (target, tau) = evaluate(voltage, codes)
    for column, name in enumerate(("HCN4_cAMP", "HCNLeak", "HCN2_cAMP")):
        for row, v in enumerate(voltage[:, 0]):
            expected_init = scalar.initial_gates(float(v), name)
            expected_target, expected_tau = scalar.kinetics(float(v), name)
            for got, expected in (
                (native_initial[row, :, column], expected_init),
                (target[row, :, column], expected_target),
                (tau[row, :, column], expected_tau),
            ):
                np.testing.assert_allclose(
                    got,
                    np.zeros(2) if name == "HCNLeak" else np.asarray(expected, dtype=float),
                    rtol=3e-14,
                    atol=2e-15,
                )
    assert not np.array_equal(native_initial[:, 0, 0], target[:, 0, 0])
    np.testing.assert_allclose(
        channel.initial_gates(-0.080, 55, xp=np), [0.5, 1.0], rtol=0, atol=1e-15
    )
    np.testing.assert_allclose(
        channel.kinetics(-0.076, 55, xp=np)[0], [0.5, 1.0], rtol=0, atol=1e-15
    )
    assert channel.opening([0.0, 0.0], 53, xp=np) == 1.0
    for codes in (np.array([True]), np.array([54.0]), np.array([-1]), np.array([56]), np.array(54)):
        assert not catalog.valid_codes(codes, xp=np)


@pytest.mark.parametrize("name,code", [("HCN2_cAMP", 54), ("HCN4_cAMP", 55)])
def test_actual_rk4_channel_clamps_cover_activation_and_recovery(name, code):
    import jax.numpy as jnp

    # The unused h gate is deliberately displaced to check its retained clock.
    gates = channel.initial_gates(-0.080, code, xp=np)
    gates[1] = 0.3
    expected = gates.copy()
    phases = []
    for voltage in (-0.120, 0.060, -0.080):
        target, tau = channel.kinetics(voltage, code, xp=np)
        ref_target, ref_tau = (np.asarray(v, dtype=float) for v in scalar.kinetics(voltage, name))
        duration = 12 * float(ref_tau[0])
        steps = int(np.ceil(duration / (min(ref_tau) / 32)))
        dt = duration / steps

        @jax.jit
        def integrate(y, target=target, tau=tau, dt=dt, steps=steps):
            def step(g, _):
                def f(x):
                    return (jnp.asarray(target) - x) / jnp.asarray(tau)

                a = f(g)
                b = f(g + dt * a / 2)
                c = f(g + dt * b / 2)
                d = f(g + dt * c)
                newer = g + dt / 6 * (a + 2 * b + 2 * c + d)
                return newer, newer

            return jax.lax.scan(step, y, None, length=steps)

        gates, history = integrate(gates)
        indices = np.array(sorted({0, 1, 31, 63, steps // 12, steps // 2, steps - 1}))
        times = (indices + 1) * dt
        analytic = ref_target + (expected - ref_target) * np.exp(-times[:, None] / ref_tau)
        observed = np.asarray(history)[indices]
        np.testing.assert_allclose(observed, analytic, rtol=0, atol=2e-8)
        expected = ref_target + (expected - ref_target) * np.exp(-duration / ref_tau)
        np.testing.assert_allclose(gates, expected, rtol=0, atol=2e-8)
        phases.append(
            dict(
                voltage_V=voltage,
                duration_s=duration,
                steps=steps,
                dt_s=dt,
                max_absolute_gate_error=float(np.max(abs(observed - analytic))),
                final_gate=np.asarray(gates).tolist(),
                target=ref_target.tolist(),
            )
        )
    evidence(
        "hcn-extra-clamps-" + name,
        dict(
            status="passed",
            phases=phases,
            scope=(
                "Continuous channel-only RK4, 12 activation time constants per phase; "
                "native source update checked separately"
            ),
        ),
    )
