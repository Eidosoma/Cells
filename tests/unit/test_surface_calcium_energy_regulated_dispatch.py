"""Public regulation contracts coexist with older physical model families.

These are dispatch/checkpoint checks; transient qualification is separate.
"""

import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


def family(version):
    suffix = "" if version == 1 else "_v2"
    fixtures = importlib.import_module(
        "validation.regulation.integrated_network_regulation" + suffix + "_fixtures"
    )
    schema = importlib.import_module(
        "cells.core.surface_calcium_energy_regulated" + suffix + "_spec"
    )
    model = importlib.import_module("cells.models.surface_calcium_energy_regulated" + suffix)
    return fixtures, schema, model


@pytest.mark.parametrize("version", [1, 2])
def test_registered_regulation_preserves_rules_controls_and_complete_checkpoint(version, tmp_path):
    fixtures, schema, model = family(version)
    raw = fixtures.definition("ordered", padded=True)
    expected = schema.parse(raw)
    spec = parse_spec(raw)
    assert spec == expected == parse_spec(spec.to_dict())
    assert get_model(spec.model) is model
    assert spec.to_dict()["model"]["network_regulation"] == raw["model"]["network_regulation"]
    times = sorted({0.0, spec.experiment.end_time, *(c.time for c in spec.experiment.changes)})
    controls = control_values(spec, times)
    direct = schema.control_values(expected, times)
    assert controls._fields == direct._fields
    for actual, target in zip(controls, direct, strict=True):
        np.testing.assert_array_equal(actual, target)
    checkpoint = initialise(spec)
    assert len(checkpoint.state._fields) == 38
    write_snapshot(tmp_path / "checkpoint", spec, checkpoint)
    restored = load_snapshot(tmp_path / "checkpoint")
    assert restored.spec == spec
    exact(restored.checkpoint.state, checkpoint.state)
    exact(restored.checkpoint.layout, checkpoint.layout)
    assert restored.checkpoint.time == checkpoint.time
    assert restored.checkpoint.event_index == checkpoint.event_index
    cohort = BatchSpec((WorldSpec(23, spec), WorldSpec(71, spec)), 2, 10000, 2**32)
    assert parse_batch(cohort.to_dict()) == cohort
    ensemble = parse_ensemble(
        dict(
            model="ionic_worlds@1",
            simulation=spec.to_dict(),
            worlds=1,
            world_id_start=23,
            window_steps=1,
        )
    )
    assert ensemble.simulation == spec and ensemble.world_id_start == 23
    evidence(
        "registered-regulation-" + str(version),
        dict(
            model=raw["model"]["id"],
            definition=spec.to_dict(),
            state_fields=list(checkpoint.state._fields),
            control_fields=list(controls._fields),
            control_times=times,
            snapshot_restored_exactly=True,
            scope="Public dispatch and complete initial checkpoint; no trajectory execution",
        ),
    )


def test_distinct_regulation_versions_cannot_share_one_compiled_cohort():
    specs = [parse_spec(family(v)[0].definition()) for v in (1, 2)]
    cohort = BatchSpec(
        tuple(WorldSpec(i + 1, spec) for i, spec in enumerate(specs)), 2, 10000, 2**32
    )
    with pytest.raises(ConfigError, match="one model family"):
        parse_batch(cohort.to_dict())


@pytest.mark.parametrize(
    "filename,module",
    [
        ("resolved_hcn_extra_energy.json", "surface_calcium_energy_hcn_extra"),
        ("resolved_calcium_energy_network_transport.json", "surface_calcium_energy_transport"),
        ("resolved_calcium_energy_mitochondria.json", "surface_calcium_energy_mitochondria"),
        ("resolved_calcium_energy_water.json", "surface_calcium_energy_water"),
    ],
)
def test_regulation_registration_keeps_existing_physical_dispatch(filename, module):
    path = Path(__file__).resolve().parents[2] / "configs" / filename
    raw = json.loads(path.read_text())
    spec = parse_spec(raw)
    assert get_model(spec.model) is importlib.import_module("cells.models." + module)
    assert parse_spec(spec.to_dict()) == spec
    assert spec.to_dict()["model"]["id"] == raw["model"]["id"]
    controls = control_values(spec, [0.0, spec.experiment.end_time])
    assert all(len(values) == 2 for values in controls)
    assert "network_regulation" not in spec.to_dict()["model"]
