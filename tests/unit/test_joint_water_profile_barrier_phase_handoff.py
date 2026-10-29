"""Complete water/fuel/repair history and explicit two-schedule phase boundaries."""

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import joint_water_profile_barrier_phase_handoff as bridge
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.tissue_phase import prepare_request, replay
from tests.joint_water_profile_barrier_phase_fixtures import (
    DT,
    OWNERS,
    prepared,
    request,
    source_checkpoint,
)
from tests.unit.test_joint_water_profile_barrier_phase_reference import evidence
from tests.unit.test_surface_kinetic import exact

FAMILIES = [pytest.param("water", id="water_owner"), pytest.param("repair", id="repair_owner")]


@pytest.mark.parametrize("case", ("changed", "empty"))
@pytest.mark.parametrize("family", FAMILIES)
def test_combined_epoch_preserves_all_original_arrays_and_both_static_recipes(case, family):
    schema, model, fields = OWNERS[family]
    scheduled = model.scheduled
    source, before = source_checkpoint(family)
    artifact = prepared(family, case)
    spec = parse_spec(artifact.definition)
    point = initialise(spec)
    exact(scheduled.parent_state(point.state), scheduled.parent_state(before.state))
    exact(scheduled.parent_layout(point.layout), scheduled.parent_layout(before.layout))
    assert point.time == point.step_index == point.event_index == 0
    assert before.time == DT and len(point.state) == fields
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    for name in ("channel_transferred", "pump_cycles", "face_transferred", "metabolic_work_pJ"):
        assert np.any(getattr(point.state, name) != 0), name
    assert np.any(point.state.chemical_amount_increment != 0)
    stores = point.layout.er_initial_amount + point.state.chemical_amount_increment
    np.testing.assert_array_equal(
        artifact.provenance["preservation"]["chemical_store_amount_fmol"], stores
    )
    from cells.models import surface_calcium_energy as fuel

    assert np.any(point.state.energy_amount_increment_fmol != 0)
    assert np.any(point.state.volume_increment_pL != 0)
    np.testing.assert_array_equal(
        artifact.provenance["preservation"]["energy_pool_amount_fmol"],
        fuel.energy_amounts(
            scheduled.parent_state(point.state), scheduled.parent_layout(point.layout)
        ),
    )
    np.testing.assert_array_equal(
        artifact.provenance["preservation"]["original_volume_reference_pL"],
        np.r_[point.layout.volume, point.layout.extracellular_volume],
    )
    actual_volume = np.r_[
        point.layout.volume + point.state.volume_increment_pL,
        point.layout.extracellular_volume + point.state.extracellular_volume_increment_pL,
    ]
    np.testing.assert_array_equal(
        artifact.provenance["preservation"]["actual_volume_pL"], actual_volume
    )
    np.testing.assert_array_equal(
        artifact.provenance["preservation"]["pool_volume_work_pJ"], point.state.pool_volume_work_pJ
    )
    if family == "repair":
        assert np.any(point.state.injury_transferred != 0)
        for name, value in artifact.provenance["preservation"]["prescribed_repair"].items():
            np.testing.assert_array_equal(value, getattr(point.state, name))
    assert spec.model.coupled_preparation == source.model.coupled_preparation
    assert schema.scheduled_spec(spec).model.phase == "SIM"
    assert artifact == replay(artifact.provenance)
    record = model.handoff_record(spec)
    reset = record["buffer_reset"]
    np.testing.assert_array_equal(reset["scheduled_buffer_m2_s"], 0)
    np.testing.assert_array_equal(
        reset["baseline_diffusion_m2_s"], point.layout.native_baseline_m2_s
    )
    exterior = record["coefficient_reset"]
    assert exterior["stateful_coefficient_buffer"] is False
    for key, field in (
        ("baseline_site_diffusion_m2_s", "barrier_base_m2_s"),
        ("fixed_modulators", "barrier_modulator"),
        ("free_diffusion_m2_s", "barrier_free_m2_s"),
        ("baseline_native_sodium_weight", "barrier_weight_base"),
    ):
        np.testing.assert_array_equal(exterior[key], getattr(point.layout, field))
    signal = model.signal_values(point.state, point.layout, xp=np)
    if case == "empty":
        assert not np.any(signal.membrane.scheduled)
        assert not np.any(signal.barrier.pulse)
    else:
        # Smooth pulse tails are evaluated on the new clock, not suppressed
        # by the archival zero-buffer record or the previous INIT phase.
        assert np.any(signal.membrane.pulse > 0)
        assert np.any(signal.barrier.pulse > 0)
    evidence(
        "owned-combined-epoch-preservation-" + family + "-" + case,
        dict(
            definition=spec.to_dict(),
            physical_fields=fields - 1,
            only_phase_clock_reset=True,
            original_accounting_layout_exact=True,
            membrane_and_ecm_recipes_exact=True,
            full_trajectory_credit=False,
        ),
        arrays={key: np.asarray(value) for key, value in point.state._asdict().items()},
    )


@pytest.mark.parametrize("fault", ("clock", "precision", "layout", "history", "index", "time"))
@pytest.mark.parametrize("family", FAMILIES)
def test_combined_epoch_refuses_corrupt_actual_source(fault, family):
    spec, point = source_checkpoint(family)
    if fault == "clock":
        point = replace(point, state=point.state._replace(phase_clock_s=np.zeros(1)))
    elif fault == "precision":
        point = replace(
            point,
            state=point.state._replace(channel_gate=point.state.channel_gate.astype(np.float32)),
        )
    elif fault == "layout":
        point = replace(point, layout=point.layout._replace(volume=point.layout.volume * 2))
    elif fault == "history":
        values = np.array(point.state.face_transferred)
        values.flat[0] += 1e-3
        point = replace(point, state=point.state._replace(face_transferred=values))
    elif fault == "index":
        point = replace(point, event_index=-1)
    else:
        point = replace(point, time=DT / 2)
    with pytest.raises((ConfigError, NumericalError, ValueError)):
        bridge.capture_source(spec, point)


@pytest.mark.parametrize("fault", ("phase", "capacity", "owner", "policy", "recipe"))
@pytest.mark.parametrize("family", FAMILIES)
def test_combined_epoch_refuses_implicit_physical_and_phase_changes(fault, family):
    raw = request(family)
    if fault == "phase":
        raw["simulation"]["model"]["phase"] = "INIT"
    elif fault == "capacity":
        raw["simulation"]["execution"]["capacity"] += 1
    elif fault == "owner":
        raw["simulation"]["model"]["id"] = (
            "resolved_calcium_energy_water_repair_profile_barriers@1"
            if family == "water"
            else "resolved_calcium_energy_water_profile_barriers@1"
        )
    elif fault == "policy":
        raw["policies"]["coefficient_policy"] = "clear_all_transfers"
    else:
        raw["simulation"]["model"]["coupled_preparation"]["provenance"]["identity"] = "changed"
    with pytest.raises((ConfigError, NumericalError)):
        prepare_request(raw)


@pytest.mark.parametrize("field", ("buffer_reset", "coefficient_reset", "preservation"))
@pytest.mark.parametrize("family", FAMILIES)
def test_combined_epoch_replay_recomputes_complete_handoff_records(field, family):
    artifact = prepared(family)
    damaged = deepcopy(artifact.provenance)
    damaged[field] = {}
    damaged.pop("identity")
    damaged["identity"] = digest(damaged)
    with pytest.raises(ConfigError):
        replay(damaged)
    if field != "preservation":
        raw = deepcopy(artifact.definition)
        raw["model"]["handoff"][field] = {}
        with pytest.raises(ConfigError):
            parse_spec(raw)
