"""Complete ionic/calcium/fuel histories at standalone ECM phase boundaries."""

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import owned_barrier_phase_handoff as bridge
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.tissue_phase import prepare_request, replay
from tests.owned_barrier_phase_fixtures import (
    DT,
    OWNERS,
    prepared,
    request,
    source_checkpoint,
)
from tests.unit.test_owned_barrier_phase_reference import evidence
from tests.unit.test_surface_kinetic import exact

FAMILIES = [
    pytest.param("ionic", id="ionic_owner"),
    pytest.param("calcium", id="chemical_owner"),
    pytest.param("energy", id="fuel_owner"),
]


@pytest.mark.parametrize("case", ("changed", "empty"))
@pytest.mark.parametrize("family", FAMILIES)
def test_ecm_epoch_preserves_all_original_arrays_and_static_recipe(case, family):
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
    if family != "ionic":
        assert np.any(point.state.chemical_amount_increment != 0)
        stores = point.layout.er_initial_amount + point.state.chemical_amount_increment
        np.testing.assert_array_equal(
            artifact.provenance["preservation"]["chemical_store_amount_fmol"], stores
        )
    else:
        assert "chemical_store_amount_fmol" not in artifact.provenance["preservation"]
    if family == "energy":
        assert np.any(point.state.energy_amount_increment_fmol != 0)
        np.testing.assert_array_equal(
            artifact.provenance["preservation"]["energy_pool_amount_fmol"],
            scheduled.base.energy_amounts(
                scheduled.parent_state(point.state), scheduled.parent_layout(point.layout)
            ),
        )
    assert spec.model.barrier_preparation == source.model.barrier_preparation
    assert schema.scheduled_spec(spec).model.phase == "SIM"
    assert artifact == replay(artifact.provenance)
    record = model.handoff_record(spec)
    assert "buffer_reset" not in record
    assert "buffer_policy" not in record
    assert (
        not {"profile_preparation", "coupled_preparation", "membrane_interventions"}
        & spec.to_dict()["model"]["scheduled"].keys()
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
        assert not np.any(signal.pulse)
    else:
        # Smooth pulse tails are evaluated on the new clock, not suppressed
        # by the archival zero-buffer record or the previous INIT phase.
        assert np.any(signal.pulse > 0)
    evidence(
        "owned-ecm-epoch-preservation-" + family + "-" + case,
        dict(
            definition=spec.to_dict(),
            physical_fields=fields - 1,
            only_phase_clock_reset=True,
            original_accounting_layout_exact=True,
            only_ecm_recipe_exact=True,
            full_trajectory_credit=False,
        ),
        arrays={key: np.asarray(value) for key, value in point.state._asdict().items()},
    )


@pytest.mark.parametrize("fault", ("clock", "precision", "layout", "history", "index", "time"))
@pytest.mark.parametrize("family", FAMILIES)
def test_ecm_epoch_refuses_corrupt_actual_source(fault, family):
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
def test_ecm_epoch_refuses_implicit_physical_and_phase_changes(fault, family):
    raw = request(family)
    if fault == "phase":
        raw["simulation"]["model"]["phase"] = "INIT"
    elif fault == "capacity":
        raw["simulation"]["execution"]["capacity"] += 1
    elif fault == "owner":
        raw["simulation"]["model"]["id"] = {
            "ionic": "resolved_calcium_extracellular_barriers@1",
            "calcium": "resolved_calcium_energy_extracellular_barriers@1",
            "energy": "resolved_active_extracellular_barriers@1",
        }[family]
    elif fault == "policy":
        raw["policies"]["coefficient_policy"] = "clear_all_transfers"
    else:
        raw["simulation"]["model"]["barrier_preparation"]["provenance"]["identity"] = "changed"
    with pytest.raises((ConfigError, NumericalError)):
        prepare_request(raw)


@pytest.mark.parametrize("field", ("clocks", "coefficient_reset", "preservation"))
@pytest.mark.parametrize("family", FAMILIES)
def test_ecm_epoch_replay_recomputes_complete_handoff_records(field, family):
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


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("key", ("profile_preparation", "coupled_preparation"))
def test_standalone_ecm_does_not_admit_a_membrane_profile_recipe(family, key):
    from validation.topology import owned_barrier_phase_handoff_reference as independent

    raw = request(family)
    raw["simulation"]["model"][key] = {}
    with pytest.raises((ConfigError, NumericalError)):
        prepare_request(raw)
    with pytest.raises(ValueError, match="membrane-profile"):
        independent.initial(raw)
    evidence(
        "standalone-only-" + family + "-" + key,
        dict(rejected_field=key, no_membrane_profile_recipe=True),
    )
