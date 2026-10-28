"""Short host validation for one shared salt/water/finite-energy state."""

import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_cotransport_water_spec as schema
from cells.core.errors import NumericalError
from cells.core.runner import timeline
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.ensemble import ionic
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_cotransport as transport
from cells.models import surface_cotransport_water as model
from cells.models import surface_energy_water as water
from cells.models.registry import get_model
from validation.tissue import surface_cotransport_water_fixtures as fixtures
from validation.tissue import surface_cotransport_water_reference as reference

EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, value, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / "cpu"
        root.mkdir(parents=True, exist_ok=True)
        path = root / ("cotransport-water-" + name)
        path.with_suffix(".json").write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(path.with_suffix(".npz"), **arrays)


def initial(arm="coupled", *, padded=False, time=0.0):
    spec = parse_spec(fixtures.definition(arm, padded=padded))
    state, p = model.initial_values(spec)
    controls = control_values(spec, [time])
    return spec, state, p, type(controls)(*(v[0] for v in controls))


def compact(c, state):
    return reference.flatten(
        c,
        {
            k: np.asarray(getattr(state, k))[tuple(slice(0, n) for n in shape)]
            for k, shape in c["shapes"].items()
        },
    )


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_complete_registration_projection_and_roundtrip(backend, padded):
    raw = fixtures.definition("release", backend=backend, padded=padded)
    original = deepcopy(raw)
    spec = parse_spec(raw)
    assert spec.to_dict() == raw == original and parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model and len(model.initial_values(spec)[0]) == 31
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )
    w = schema.water_spec(spec)
    c = schema.cotransport_spec(spec)
    assert water.energy_spec(w) == transport.energy_spec(c)
    assert not hasattr(w.model, "cotransporters") and not hasattr(c.model, "water_compartments")


def test_seven_independent_clocks_and_padding():
    spec, _, _, _ = initial("release", padded=True)
    raw = spec.to_dict()
    events = sorted(
        {
            row["time"]
            for groups in raw["experiment"].values()
            if isinstance(groups, list)
            for group in groups
            if isinstance(group, dict) and "schedule" in group
            for row in group["schedule"]
        }
    )
    times = timeline(spec)
    assert all(t in times for t in events)
    probes = sorted(set(events) | {np.nextafter(t, 0) for t in events if t > 0})
    controls = control_values(spec, probes)
    assert controls._fields == (
        "membrane",
        "junction",
        "channel",
        "pump",
        "regeneration",
        "water",
        "cotransport",
    )
    for family, field, idkey, owners in (
        ("water_controls", "water", "membrane_id", spec.model.membranes),
        ("cotransport_controls", "cotransport", "cotransport_id", spec.model.cotransporters),
    ):
        schedules = {v[idkey]: v["schedule"] for v in raw["experiment"][family]}
        expected = np.zeros_like(getattr(controls, field))
        for j, owner in enumerate(owners):
            for i, t in enumerate(probes):
                expected[i, j] = next(
                    v["availability"] for v in reversed(schedules[owner.id]) if v["time"] <= t
                )
        np.testing.assert_array_equal(getattr(controls, field), expected)
    evidence("clocks", dict(status="passed", events=events, controls=list(controls._fields)))


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_complete_shared_stage_against_independent_reference(arm, padded):
    time = 32e-6 if arm == "release" else 0.0
    spec, state, p, control = initial(arm, padded=padded, time=time)
    if arm != "sealed_water":
        state.volume_increment_pL[0] = 0.01
        state.extracellular_volume_increment_pL[0] = -0.01
        state.water_transferred_pL[0] = -0.01
    delta = 0.1 * p.energy_initial_amount_fmol[0, 0]
    state.energy_amount_increment_fmol[:, 0] = [-delta, delta, delta]
    before = [v.copy() for v in state]
    value = model.readouts(state, control, p, xp=np)
    c = reference.bind(spec.to_dict())
    target, phi, proof = reference.evaluate(c, compact(c, state), time)
    actual = compact(c, value.derivative)
    absolute = reference.flatten(
        c,
        {
            k: np.full(shape, 3e-23 if k.endswith("_C") else 3e-12)
            for k, shape in c["shapes"].items()
        },
    )
    score = float(np.max(np.abs(actual - target) / (absolute + 3e-10 * np.abs(target)), initial=0))
    name = f"stage-{arm}-{int(padded)}"
    evidence(
        name,
        dict(status="captured", inputs=spec.to_dict(), proof=proof),
        dict(actual=actual, expected=target),
    )
    assert value.valid and np.isfinite(actual).all() and score <= 1
    potentials = np.r_[
        value.field.potential_V[: p.active.size][p.active],
        value.field.potential_V[p.active.size :][p.outside_active],
    ]
    np.testing.assert_allclose(potentials, phi, atol=3e-11, rtol=3e-10)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 2e-8
    assert abs(value.field.energy_balance_pJ_s) < 2e-8
    for a, b in zip(state, before, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        name, dict(status="passed", inputs=spec.to_dict(), max_error_over_budget=score, proof=proof)
    )


@pytest.mark.parametrize("arm", ["sealed", "absent", "sealed_water"])
def test_disabled_component_recovers_complete_existing_model(arm):
    spec, state, p, control = initial(arm, padded=True)
    actual = model.rhs(state, control, p, p.active, xp=np)
    old = transport if arm == "sealed_water" else water
    projected = schema.cotransport_spec(spec) if arm == "sealed_water" else schema.water_spec(spec)
    y, q = old.initial_values(projected)
    controls = control_values(projected, [0.0])
    expected = old.rhs(y, type(controls)(*(v[0] for v in controls)), q, q.active, xp=np)
    for name in old.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(actual, name), getattr(expected, name))
    extras = water.EXTRA_AXES if arm == "sealed_water" else transport.EXTRA_AXES
    assert all(not np.any(getattr(actual, k)) for k in extras)


@pytest.mark.parametrize(
    "fault",
    ["unknown_coupling", "missing_water", "missing_transport", "unknown_role", "unknown_owner"],
)
def test_ambiguous_or_invalid_composition_is_rejected(fault):
    raw = fixtures.definition()
    if fault == "unknown_coupling":
        raw["model"]["energy_osmotic_coupling"] = "implicit"
    elif fault == "missing_water":
        raw["experiment"].pop("water_controls")
    elif fault == "missing_transport":
        raw["experiment"].pop("cotransport_controls")
    elif fault == "unknown_role":
        raw["model"]["cotransporters"][0]["roles"]["potassium"] = "absent"
    else:
        raw["model"]["water_compartments"][0]["compartment_id"] = "absent"
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_cotransport_has_no_instantaneous_water_energy_or_charge_shortcut():
    _, state, p, control = initial()
    on = model.readouts(state, control, p, xp=np)
    off = model.readouts(
        state, control._replace(cotransport=np.zeros_like(control.cotransport)), p, xp=np
    )
    assert np.any(on.derivative.amount_increment != off.derivative.amount_increment)
    for key in (
        *water.EXTRA_AXES,
        "energy_amount_increment_fmol",
        "pump_cycles",
        "electrode_charge_transferred_C",
    ):
        np.testing.assert_array_equal(getattr(on.derivative, key), getattr(off.derivative, key))
    np.testing.assert_array_equal(
        on.field.rates.membrane_current_A, off.field.rates.membrane_current_A
    )
    assert not np.any(on.cotransport.direct_charge_C_s)


@pytest.mark.parametrize("field", [*transport.EXTRA_AXES, *water.EXTRA_AXES])
def test_corrupt_local_ledgers_are_rejected(field):
    spec, state, _, _ = initial("two_patches", padded=True)
    getattr(state, field).flat[0] += 0.001
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


@pytest.mark.parametrize("fault", ["pool", "volume", "ion", "padding"])
def test_exhaustion_and_padding_reject_even_with_all_routes_off(fault):
    _, state, p, control = initial(padded=True)
    if fault == "pool":
        state.energy_amount_increment_fmol[0, 0] = -p.energy_initial_amount_fmol[0, 0]
    elif fault == "volume":
        state.volume_increment_pL[0] = p.water_minimum_volume_pL[0] - p.volume[0]
    elif fault == "ion":
        state.amount_increment[0, 0] = -p.amount_reference[0, 0]
    else:
        state.cotransport_cycles_fmol[-1] = 1e-9
    disabled = type(control)(*(np.zeros_like(v) for v in control))
    assert not model.control_domain_valid(state, disabled, p, p.active, xp=np)


def host_steps(state, p, control, steps=8):
    dt = fixtures.DT

    def add(y, k, h):
        return model.STATE_TYPE(*(a + h * b for a, b in zip(y, k, strict=True)))

    for _ in range(steps):
        k1 = model.rhs(state, control, p, p.active, xp=np)
        k2 = model.rhs(add(state, k1, dt / 2), control, p, p.active, xp=np)
        k3 = model.rhs(add(state, k2, dt / 2), control, p, p.active, xp=np)
        k4 = model.rhs(add(state, k3, dt), control, p, p.active, xp=np)
        state = model.STATE_TYPE(
            *(
                a + dt * (b + 2 * c + 2 * d + e) / 6
                for a, b, c, d, e in zip(state, k1, k2, k3, k4, strict=True)
            )
        )
    return state


def test_short_integrated_salt_water_feedback_and_complete_checkpoint(tmp_path):
    spec, state, p, control = initial()
    on = host_steps(state, p, control)
    off = host_steps(state, p, control._replace(cotransport=np.zeros_like(control.cotransport)))
    diagnostic = model.check_values(on, spec)
    model.check_values(off, spec)
    assert abs(on.volume_increment_pL[0] - off.volume_increment_pL[0]) > 1e-10
    assert np.any(on.energy_amount_increment_fmol != off.energy_amount_increment_fmol)
    time = np.array([8 * fixtures.DT])
    observed = model.observe_history(time, model.STATE_TYPE(*(v[None] for v in on)), p, time, spec)
    current = model.readouts(on, control, p, xp=np)
    np.testing.assert_array_equal(
        observed.membrane_flux_fmol_s[0], current.field.rates.membrane_flux_fmol_s
    )
    np.testing.assert_array_equal(
        observed.cotransport_transferred_fmol[0], on.cotransport_transferred_fmol
    )
    assert all(hasattr(observed, k) for k in model.STATE_TYPE._fields)
    # Initial snapshot is a schema/state completeness check; long replay is separate.
    checkpoint = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    write_snapshot(tmp_path / "complete", spec, checkpoint)
    saved = load_snapshot(tmp_path / "complete")
    for a, b in zip(saved.checkpoint.state, state, strict=True):
        np.testing.assert_array_equal(a, b)
    path = tmp_path / "complete/state.npz"
    with np.load(path, allow_pickle=False) as archive:
        values = {k: archive[k] for k in archive.files if k != "pool_volume_work_pJ"}
    np.savez(path, **values)
    import hashlib

    manifest_path = tmp_path / "complete/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["state_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    del manifest["manifest_sha256"]
    manifest["manifest_sha256"] = digest(manifest)
    manifest_path.write_text(json.dumps(manifest) + "\n")
    with pytest.raises(ConfigError, match="Invalid checkpoint state fields"):
        load_snapshot(tmp_path / "complete")
    evidence(
        "short-feedback",
        dict(
            status="passed",
            steps=8,
            inputs=spec.to_dict(),
            diagnostics=diagnostic,
            on_cell_volume_increment_pL=float(on.volume_increment_pL[0]),
            blocked_cell_volume_increment_pL=float(off.volume_increment_pL[0]),
            complete_state_fields=31,
            checkpoint_missing_field_rejected=True,
        ),
    )
