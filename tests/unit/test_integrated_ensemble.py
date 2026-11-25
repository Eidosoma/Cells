"""Integrated scheduling preserves worlds and model semantics, on a live pump tissue."""

import copy

import pytest

from cells.ensemble.cli import aggregate
from cells.ensemble.families import parse_definition, population
from cells.ensemble.plan import balance, plan
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_fixtures


def experiment(*, backend="cpu", worlds=2, width=1, end=0.0004):
    """One arm: the pump tissue at rest, each control held at its first value."""
    simulation = surface_pump_fixtures.definition("closed", backend=backend, solver=imex.ARS222_ID)
    simulation["experiment"].update(end_time=end, observation_times=[0.0, end])
    for name, controls in simulation["experiment"].items():
        if name.endswith("_controls"):
            for control in controls:
                control["schedule"] = control["schedule"][:1]
    raw = {"model": "ionic_worlds@1", "simulation": simulation, "window_steps": 2}
    return {
        "kind": "ionic_ensemble@1",
        "seed": 123,
        "arms": [
            {
                "id": "active",
                "definition": raw,
                "worlds": worlds,
                "batch_worlds": width,
                "seconds_per_world": None,
            }
        ],
        "execution": {
            "max_wall_seconds": 600,
            "max_output_bytes": 512 * 1024**2,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 1,
        },
    }


def test_counts_ids_kind_and_balancing():
    data = experiment(worlds=16, width=8)
    original = copy.deepcopy(data)
    result = plan(data, 1)
    tuned = plan(balance(data, {"active": 1.0}, 4.0), 1)

    def ids(p):
        populations = [population(parse_definition(t["definition"])) for t in p["tasks"]]
        return [
            i for p in populations for i in range(p.world_id_start, p.world_id_start + p.worlds)
        ]

    assert ids(result) == ids(tuned) == list(range(16))
    assert data == original
    data["kind"] = "finite_bond_ensemble@1"
    with pytest.raises(ValueError, match="kind"):
        plan(data, 1)


def test_reject_owned_counts_and_over_budget():
    data = experiment()
    raw = data["arms"][0]["definition"]
    raw["seed"] = 17
    with pytest.raises(ValueError, match="owns"):
        plan(data, 1)
    raw.pop("seed")
    data["execution"]["max_output_bytes"] = 1024**2
    with pytest.raises(ValueError, match="bound"):
        plan(data, 1)


def test_ionic_aggregation_does_not_invent_assembly_statistics():
    row = {
        "arm": "a",
        "model": "ionic_worlds@1",
        "physical_model": "finite_extracellular@3",
        "worlds": 2,
        "wall_start": 0.0,
        "wall_end": 1.0,
        "execute_seconds": 0.1,
        "integrated_world_steps": 10,
        "final_voltage_V": [[-0.08, -0.07], [-0.06, -0.05]],
        "ionic_accounting": {"balance": 2e-15},
    }
    value = aggregate([row, row])["a"]
    assert value["worlds"] == 4 and value["integrated_world_steps"] == 20
    assert value["final_voltage_mean_V"] == pytest.approx([-0.07, -0.06])
    assert "completed_shells" not in value and "completion_probability" not in value
    assert "committed_events" not in value
