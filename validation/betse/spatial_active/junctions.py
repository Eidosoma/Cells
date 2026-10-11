"""Static/initial mapping and source binding for dynamic spatial junctions."""

import json
from pathlib import Path

import numpy as np

from cells.numerics import betse_junction as model
from cells.processes import junction_gate
from validation.betse.spatial_active import fixtures, refinement

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = Path(__file__).with_name("junction_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    binding, root = rule["prior_binding"], Path(rule["prior_binding"]["root"])
    assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
    report = refinement.completed_prior(binding, current_root=ROOT)
    reg = json.loads((root / "registration.json").read_text())
    for name, digest in reg["sources_sha256"].items():
        assert refinement.digest(ROOT / name) == digest, name
    old = {n for n in reg["sources_sha256"] if n.startswith("src/")}
    current = {str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")}
    assert current - old == set(rule["new_production_files"])
    return report | dict(
        all_prior_sources_unchanged=len(reg["sources_sha256"]),
        new_production_files=rule["new_production_files"],
    )


def prepare(row, trace, rule):
    state, active = fixtures.prepare(row, trace, rule)
    record = row["fixture"]["dynamic_junction"]
    assert record["enabled"] and record["native_class"] == "Gap_Junction"
    assert record["native_source_sha256"] == rule["junction"]["native_source_sha256"]
    assert record["clock"] == "one_outer_dt_per_moving_ion"
    assert record["blocking"] == "multiply_stored_opening_after_each_implicit_update"
    assert record["calls_per_step"] == len(row["case"]["moving_order"])
    shape = active.tissue.membrane_area.shape
    mask = np.ones(shape)
    mask[row["geometry"]["bflags_mems"]] = 0
    active = active._replace(tissue=active.tissue._replace(junction_open=mask))
    layout = model.validate_layout(
        model.Layout(
            active,
            junction_gate.Parameters(
                *(
                    np.full(shape, record[name])
                    for name in ("threshold_voltage_V", "minimum_open_fraction")
                )
            ),
            np.asarray(record["base_block"]),
            np.asarray([row["species"][name] for name in row["case"]["moving_order"]]),
        )
    )
    np.testing.assert_array_equal(trace["initial_gjopen"], record["initial_open"])
    return model.initial_state(state, layout, trace["initial_gjopen"]), layout


def controls(case, dt, steps, patches):
    events = case["junction_changes"]
    indices = [round(e["time_s"] / dt) for e in events]
    values = np.array([e["fraction"] for e in events])
    event = np.searchsorted(indices, np.arange(steps), side="right") - 1
    assert indices[0] == 0 and all(a < b for a, b in zip(indices, indices[1:], strict=False))
    assert all(
        abs(e["time_s"] - i * dt) <= 8 * np.finfo(float).eps * max(dt, e["time_s"])
        for e, i in zip(events, indices, strict=True)
    )
    assert np.isfinite(values).all() and np.all((values >= 0) & (values <= 1))
    return model.Control(
        np.ones((steps, patches)),
        np.ones((steps, patches)),
        np.broadcast_to(values[event, None], (steps, patches)).copy(),
    )


def arrays(states, rates, observed):
    return fixtures.arrays(states.active, rates.active, observed) | {
        "junction__open": states.junction_open,
        "junction__after_ion": rates.junction_after_ion,
    }
