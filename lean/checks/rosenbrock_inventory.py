"""Check closed material inventories in native Rodas4 stages, dense output and saved rows."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import jax
import jax.numpy as jnp
import numpy as np
from rate_equation_flux import AVOGADRO, pair_world

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import rate_equations, records, runner
from cells.numerics import rosenbrock_dense
from tests.assembly_lineage_v2_fixtures import definition, step
from tests.unit.test_assembly_lineages_v2_rate_equations import as_representation, linear_world

DATA = Path(__file__).with_name("data")
EPS = np.finfo(np.float64).eps


def recorded_run(world, times, directory):
    spec = parse_spec(as_representation(definition(world, horizon=times[-1], observations=times)))
    run = runner.run(spec)
    run.check_books()
    records.write_run(directory, run)
    record = json.loads((directory / "run.json").read_text())
    assert record["status"] == "complete" and record["events"] == []
    assert (
        record["engine_models"]["representation"]
        == "cells.assembly_representation.rate_equations@1"
    )
    assert record["ledger"]["closes"] and record["moieties"]["closes"]
    assert record["rows"]["places"][:3] == ["A@pool", "B@pool", "C@pool"]
    with np.load(directory / "rows.npz") as rows:
        observed = rows["row_kind"] == "observed"
        np.testing.assert_array_equal(rows["row_time_s"][observed], times)
        counts = rows["counts"][observed, :3]
    return spec, record, counts


def association(directory):
    world = linear_world()
    for species, moieties in zip(
        world["species"][:3], ({"a": 1}, {"b": 1}, {"a": 1, "b": 1}), strict=True
    ):
        species["moieties"] = moieties
    world["steps"] = [step("association", {"A": 1, "B": 1}, {"C": 1}, 2.0, phase="pool")]
    times = (0.0001, 0.25, 0.5, 1.0)
    spec, record, counts = recorded_run(world, times, directory)
    program = rate_equations._program(spec)
    shape = program["shape"]
    y, alive = shape.initial()
    h = rosenbrock_dense.initial_step(
        lambda z: shape.rhs(z, alive),
        y,
        spec.execution.rtol,
        spec.execution.atol_count,
        shape.weight(),
        times[0],
    )
    assert h == times[0]
    result = program["step"](y, h, alive)
    assert bool(result.finite) and float(program["norm"](result.error, y, result.y)) <= 1
    np.testing.assert_array_equal(result.y[:3], counts[0])

    # Each C carries one of each material. Simply counting molecules is a negative control.
    weights = np.array([[1, 0, 1], [0, 1, 1]])
    start = weights @ y[:3]
    stages = np.asarray(result.stages)[:, :3]
    assert len(stages) == 6
    stage_residual = np.abs(stages @ weights.T)
    stage_scale = np.maximum(1.0, np.abs(stages) @ weights.T)
    assert np.all(stage_residual <= 64 * EPS * stage_scale)
    theta = jnp.linspace(0.0, 1.0, 5)
    dense = np.asarray(program["dense"](y, result, theta))[:, :3]
    dense_drift = np.abs(dense @ weights.T - start)
    assert np.all(dense_drift <= 64 * EPS * start)
    saved_drift = np.abs(counts @ weights.T - start) / start
    assert saved_drift.max() <= record["moieties"]["tolerance"]
    unweighted_change = float(counts[-1].sum() - y[:3].sum())
    assert abs(unweighted_change) > 1
    return dict(
        inventories=["A+C", "B+C"],
        initial_molecules=start.tolist(),
        accepted_steps=record["representation"]["statistics"]["accepted"],
        first_step_s=h,
        stages=len(stages),
        max_stage_residual_molecules=float(stage_residual.max()),
        dense_fractions=theta.tolist(),
        max_dense_drift_molecules=float(dense_drift.max()),
        saved_times_s=list(times),
        max_saved_relative_drift=float(saved_drift.max()),
        saved_relative_tolerance=record["moieties"]["tolerance"],
        unweighted_molecule_change=unweighted_change,
    )


def sugar_recovery(directory):
    source = json.loads((DATA / "kahana1960_pgi_recovery.json").read_text())
    direction = json.loads((DATA / "pgi_flux_direction.json").read_text())
    measurements = np.asarray(source["measurements"])
    measured = measurements[:, 1:].sum(axis=1)
    # Start at the first positive pair: zero F6P lies outside the representation's count domain.
    t0, g, f = measurements[1]
    scale = 1000.0  # molecules per mM; the inventory is independent of volume and rates
    world = pair_world(
        direction["dyson1968_pgi_equilibrium"]["kinetic_F6P_over_G6P"],
        273.15 + source["temperature_C"],
    )
    world["phases"]["pool"]["volume_L"] = scale / (AVOGADRO * 1e-3)
    world["founder"].update({"A@pool": round(g * scale), "B@pool": round(f * scale)})
    np.testing.assert_array_equal(
        [world["founder"]["A@pool"], world["founder"]["B@pool"]], np.array([g, f]) * scale
    )
    elapsed = (measurements[2, 0] - t0) * 60
    _, record, counts = recorded_run(world, (elapsed,), directory)
    predicted = float(counts[-1, :2].sum() / scale)
    np.testing.assert_allclose(predicted, measured[1], rtol=record["moieties"]["tolerance"], atol=0)

    extract = []
    for course in direction["eicher2012_pgi_direction"]["courses"]:
        first = sum(course["first"][1:])
        last = sum(course["last"][1:])
        extract.append(
            dict(
                dataset=course["dataset"],
                initial_mM=first,
                final_mM=last,
                change_percent=100 * (last / first - 1),
            )
        )
    return dict(
        kahana=dict(
            times_min=measurements[:, 0].tolist(),
            measured_pair_mM=measured.tolist(),
            recovery_percent=(100 * measured / measured[0]).tolist(),
            model_start_min=t0,
            model_end_min=float(measurements[2, 0]),
            model_final_pair_mM=predicted,
            observed_minus_model_mM=measured[-1] - predicted,
        ),
        eicher_extract=extract,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundles", type=Path, help="keep both native run.json and rows.npz pairs")
    args = parser.parse_args()
    with TemporaryDirectory() as tmp:
        directory = args.bundles or Path(tmp)
        results = dict(
            association=association(directory / "association"),
            sugar_recovery=sugar_recovery(directory / "pgi"),
        )
        print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    main()
