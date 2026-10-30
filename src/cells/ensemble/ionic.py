"""Independent ionic worlds using ordinary guarded batch windows and snapshots.

World IDs are stable scheduling identities. These deterministic replicas do not
add stochastic samples; no random perturbation or biological variation is implied.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from time import monotonic

import numpy as np

from cells.assembly.io import digest, write_json
from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.batch_windows import plan_batch_windows, run_batch_windowed
from cells.core.grid import refinement_times
from cells.core.resources import trace_bytes
from cells.core.specs import digest as definition_digest
from cells.core.specs import parse_spec as parse_ionic
from cells.core.windows import WindowPolicy
from cells.models.registry import get_model

MODEL_ID = "ionic_worlds@1"


@dataclass(frozen=True)
class IonicSpec:
    simulation: object
    worlds: int
    world_id_start: int
    seed: int
    window_steps: int
    max_working_bytes: int
    max_output_bytes: int
    max_wall_seconds: float
    model: str = MODEL_ID
    recording: str = "summary"

    @property
    def end_time_s(self):
        return self.simulation.experiment.end_time

    def to_dict(self):
        return vars(self) | {"simulation": self.simulation.to_dict()}

    @property
    def fingerprint(self):
        return definition_digest(self.to_dict())

    @property
    def output_bound(self):
        # Scalar snapshot manifests retain their source inventory and complete
        # definition. Reserve that overhead as well as full numerical arrays.
        per_world = (
            256 * 1024
            + 4 * len(json.dumps(self.simulation.to_dict()))
            + 4 * trace_bytes(self.simulation, 0, 0)
        )
        return 16 * 1024**2 + self.worlds * per_world

    def batch(self):
        # The public scalar cohort uses positive IDs; the external scheduler's
        # zero-based IDs map bijectively to ID+1, independent of batch boundaries.
        worlds = tuple(
            WorldSpec(i + 1, self.simulation)
            for i in range(self.world_id_start, self.world_id_start + self.worlds)
        )
        bound = self.worlds * (
            math.ceil(self.end_time_s / self.simulation.execution.dt)
            + len(self.simulation.experiment.changes)
            + len(refinement_times(self.simulation))
            + 1
        )
        return BatchSpec(worlds, self.worlds, bound, self.max_working_bytes)


def validate_population(worlds, world_id_start, seed):
    """Check scheduler-owned identity without revalidating physical equations."""
    for key, value, low, high in (
        ("worlds", worlds, 1, 4096),
        ("world_id_start", world_id_start, 0, 2**31 - 2),
        ("seed", seed, 0, 2**32 - 1),
    ):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be an integer in [{low}, {high}]")
    if world_id_start + worlds >= 2**31:
        raise ValueError("Ionic positive world-ID namespace exhausted")


def parse_spec(data):
    defaults = dict(
        worlds=16,
        world_id_start=0,
        seed=0,
        window_steps=256,
        max_working_bytes=2 * 1024**3,
        max_output_bytes=512 * 1024**2,
        max_wall_seconds=600.0,
        recording="summary",
    )
    if (
        not isinstance(data, dict)
        or set(data) - (set(defaults) | {"model", "simulation"})
        or data.get("model") != MODEL_ID
        or "simulation" not in data
    ):
        raise ValueError("Require an explicit ionic_worlds@1 simulation definition")
    values = defaults | data
    validate_population(values["worlds"], values["world_id_start"], values["seed"])
    bounds = {
        "window_steps": (1, 4096),
        "max_working_bytes": (1024**2, 2 * 1024**3),
        "max_output_bytes": (1024**2, 8 * 1024**3),
    }
    for key, (low, high) in bounds.items():
        if type(values[key]) is not int or not low <= values[key] <= high:
            raise ValueError(f"{key} must be an integer in [{low}, {high}]")
    wall = values["max_wall_seconds"]
    if type(wall) not in (int, float) or not math.isfinite(wall) or not 0 < wall <= 43200:
        raise ValueError("Invalid ionic task wall limit")
    simulation = parse_ionic(values["simulation"])
    if simulation.to_dict()["model"]["id"] not in (
        "finite_extracellular@2",
        "finite_extracellular@3",
        "spatial_extracellular@2",
        "spatial_extracellular@3",
        "spatial_calcium@5",
        "resolved_membrane_profile_epoch@1",
        "resolved_membrane_profiles@1",
        "resolved_extracellular_barriers@1",
        "resolved_passive_bath_events@1",
        "resolved_active_bath_events@1",
        "resolved_passive_bath_epoch@1",
        "resolved_active_bath_epoch@1",
        "resolved_active_profile_barriers@1",
        "resolved_active_profile_barrier_epoch@1",
        "resolved_calcium_profile_barriers@1",
        "resolved_calcium_energy_profile_barriers@1",
        "resolved_calcium_energy_water_profile_barriers@1",
        "resolved_calcium_energy_water_repair_profile_barriers@1",
        "resolved_calcium_energy_water_profile_barrier_epoch@1",
        "resolved_calcium_energy_water_repair_profile_barrier_epoch@1",
        "resolved_calcium_profile_barrier_epoch@1",
        "resolved_calcium_energy_profile_barrier_epoch@1",
        "resolved_calcium_energy_water_extracellular_barrier_epoch@1",
        "resolved_calcium_energy_water_repair_extracellular_barrier_epoch@1",
        "resolved_calcium_energy_water_extracellular_barriers@1",
        "resolved_calcium_energy_water_repair_extracellular_barriers@1",
        "resolved_active_extracellular_barrier_epoch@1",
        "resolved_calcium_extracellular_barrier_epoch@1",
        "resolved_calcium_energy_extracellular_barrier_epoch@1",
        "resolved_active_extracellular_barriers@1",
        "resolved_calcium_extracellular_barriers@1",
        "resolved_calcium_energy_extracellular_barriers@1",
        "resolved_tissue@1",
        "resolved_tissue_excision@1",
        "resolved_tissue_active_excision@1",
        "resolved_calcium_excision@1",
        "resolved_calcium_energy_excision@1",
        "resolved_calcium_energy_water_excision@1",
        "resolved_calcium_energy_transport_excision@1",
        "resolved_calcium_energy_irreversible_transport_excision@1",
        "resolved_calcium_energy_atp_transport_excision@1",
        "resolved_calcium_energy_mitochondria_excision@1",
        "resolved_water@1",
        "resolved_water@2",
        "resolved_water@3",
        "resolved_energy@1",
        "resolved_energy@2",
        "resolved_energy_water@1",
        "resolved_energy_water@2",
        "resolved_cotransport@1",
        "resolved_cotransport_water@1",
        "resolved_tissue@2",
        "resolved_tissue@3",
        "resolved_tissue@4",
        "resolved_tissue@5",
        "resolved_tissue@6",
        "resolved_tissue@7",
        "resolved_tissue@8",
        "resolved_tissue@9",
        "resolved_tissue@10",
        "resolved_tissue@11",
        "resolved_active_membrane_profiles@1",
        "resolved_active_membrane_profile_epoch@1",
        "resolved_calcium_membrane_profiles@1",
        "resolved_calcium_energy_membrane_profiles@1",
        "resolved_calcium_membrane_profile_epoch@1",
        "resolved_calcium_energy_membrane_profile_epoch@1",
        "resolved_tissue@12",
        "resolved_calcium@1",
        "resolved_calcium@2",
        "resolved_calcium@3",
        "resolved_calcium@4",
        "resolved_calcium@5",
        "resolved_calcium@6",
        "resolved_calcium@7",
        "resolved_calcium@8",
        "resolved_calcium@9",
        "resolved_calcium@10",
        "resolved_calcium@11",
        "resolved_open_calcium@1",
        "resolved_open_calcium_energy@1",
        "resolved_open_calcium_bath_events@1",
        "resolved_open_calcium_energy_bath_events@1",
        "resolved_open_calcium_bath_epoch@1",
        "resolved_open_calcium_energy_bath_epoch@1",
        "resolved_calcium_water@1",
        "resolved_calcium_energy_water_repair@1",
        "resolved_calcium_energy_water_repair@2",
        "resolved_calcium_energy_water_repair_membrane_profiles@1",
        "resolved_calcium_energy_water_repair_membrane_profile_epoch@1",
        "resolved_calcium_energy_water@1",
        "resolved_calcium_energy_water@2",
        "resolved_calcium_energy_water_membrane_profiles@1",
        "resolved_calcium_energy_water_membrane_profile_epoch@1",
        "resolved_calcium_energy@1",
        "resolved_calcium_energy@2",
        "resolved_calcium_energy@3",
        "resolved_calcium_energy@4",
        "resolved_calcium_energy@5",
        "resolved_calcium_energy_regulated@1",
        "resolved_calcium_energy_regulated@2",
        "resolved_calcium_energy_regulated_excision@1",
        "resolved_calcium_energy_transport@1",
        "resolved_calcium_energy_irreversible_transport@1",
        "resolved_calcium_energy_atp_transport@1",
        "resolved_calcium_energy_mitochondria@1",
        "resolved_repair@1",
        "resolved_repair@2",
        "resolved_repair@3",
        "resolved_repair@4",
        "resolved_redistribution@1",
        "resolved_redistribution@2",
        "resolved_redistribution@3",
    ):
        raise ValueError(
            "Ionic ensembles require a registered finite, spatial or tissue calcium family"
        )
    if values["recording"] != "summary" or not simulation.execution.jit:
        raise ValueError("Ionic ensembles require summary recording and JIT")
    spec = IonicSpec(**(values | {"simulation": simulation}))
    if spec.output_bound > spec.max_output_bytes:
        raise ValueError("Ionic complete-checkpoint output allowance exceeded")
    plan_batch_windows(spec.batch(), WindowPolicy(spec.window_steps, "checkpoints"))
    return spec


def run(spec, *, backend="gpu", state=None, callback=None):
    if backend != spec.simulation.execution.backend:
        raise ValueError("Ionic task backend differs from its definition")
    began = monotonic()

    def record(window):
        if callback:
            callback(window.index + 1, window.checkpoints, None)
        if monotonic() - began > spec.max_wall_seconds:
            raise ValueError("Ionic task wall budget exceeded")

    result = run_batch_windowed(
        spec.batch(), WindowPolicy(spec.window_steps, "checkpoints"), checkpoints=state, sink=record
    )
    model = get_model(spec.simulation.model)
    checkpoints = result.checkpoints
    values = list(result.worlds.values())
    diagnostics = {k: max(w.diagnostics[k] for w in values) for k in values[0].diagnostics}
    if hasattr(model, "ensemble_voltage"):
        voltage = [
            model.ensemble_voltage(cp.state, cp.layout, spec.simulation, cp.time).tolist()
            for cp in checkpoints.values()
        ]
    else:
        voltage = [
            np.asarray(model.cell_voltage(cp.state.amount_increment, cp.layout, xp=np))[
                : len(spec.simulation.model.cells)
            ].tolist()
            for cp in checkpoints.values()
        ]
    return checkpoints, {
        "model": MODEL_ID,
        "physical_model": spec.simulation.to_dict()["model"]["id"],
        "worlds": spec.worlds,
        "world_id_start": spec.world_id_start,
        "deterministic_replicas": True,
        "through_time_s": min(cp.time for cp in checkpoints.values()),
        "integrated_world_steps": sum(cp.step_index for cp in checkpoints.values()),
        "final_voltage_V": voltage,
        **({"final_voltage_axis": "membrane_patch"} if hasattr(model, "ensemble_voltage") else {}),
        "ionic_accounting": diagnostics,
        "compile_seconds": result.timings.get("compile_seconds", 0.0),
        "execute_seconds": result.timings.get("execute_seconds", 0.0),
        "phase_timings": result.timings,
        "resources": result.resources,
        "elapsed_seconds": monotonic() - began,
        "backend": backend,
        "precision": "float64",
    }


def write_checkpoint(path, spec, state, *, execution, provenance=None):
    if execution["backend"] != spec.simulation.execution.backend:
        raise ValueError("Ionic checkpoint backend mismatch")
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    write_batch_snapshot(path / "cohort", spec.batch(), state)
    write_json(
        path / "manifest.json",
        {
            "format": "cells_ionic_ensemble_checkpoint@1",
            "definition": spec.to_dict(),
            "definition_sha256": spec.fingerprint,
            "cohort_manifest_sha256": digest(path / "cohort/manifest.json"),
            "execution": execution,
            "provenance": provenance,
        },
    )
    return digest(path / "manifest.json")


def load_checkpoint(path, *, backend="gpu"):
    from cells.assembly.engine import device_for

    path = Path(path)
    record = json.loads((path / "manifest.json").read_text())
    if record.get("format") != "cells_ionic_ensemble_checkpoint@1":
        raise ValueError("Unsupported ionic ensemble checkpoint")
    spec = parse_spec(record["definition"])
    if record["definition_sha256"] != spec.fingerprint or record[
        "cohort_manifest_sha256"
    ] != digest(path / "cohort/manifest.json"):
        raise ValueError("Ionic ensemble checkpoint identity changed")
    if (
        record["execution"]["backend"] != backend
        or record["execution"]["device_kind"] != device_for(backend, 0).device_kind
        or spec.simulation.execution.backend != backend
    ):
        raise ValueError("Ionic ensemble checkpoint device kind changed")
    saved = load_batch_snapshot(path / "cohort")
    if saved.spec != spec.batch():
        raise ValueError("Ionic checkpoint world definitions differ")
    return spec, saved.checkpoints, digest(path / "manifest.json")
