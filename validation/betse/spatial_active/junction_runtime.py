"""Initial/static export and evidence binding for ordinary dynamic junctions."""

import json
from pathlib import Path

import numpy as np

from cells.core.betse_junction_spec import MODEL_ID, SOLVER_ID
from cells.core.betse_spatial_spec import INITIAL_FIELDS
from cells.numerics import betse_active as active
from validation.betse.spatial_active import junctions, refinement

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = Path(__file__).with_name("junction_runtime_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    binding = rule["prior_binding"]
    root = Path(binding["root"])
    assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
    report = refinement.completed_prior(binding, current_root=root / "source")
    registration = json.loads((root / "registration.json").read_text())
    changed = []
    for name, sha in registration["sources_sha256"].items():
        if refinement.digest(ROOT / name) != sha:
            assert name in rule["allowed_prior_source_changes"], name
            changed.append(name)
    assert set(changed) == set(rule["allowed_prior_source_changes"])
    production = {str(p.relative_to(ROOT)) for p in (ROOT / "src").rglob("*.py")}
    old = {n for n in registration["sources_sha256"] if n.startswith("src/")}
    assert production - old == set(rule["new_production_files"])
    assert old <= production
    assert rule["tolerances"] == registration["component_protocol"]["tolerances"]
    return report | dict(
        changed_dispatch_files=changed,
        unchanged_prior_files=len(registration["sources_sha256"]) - len(changed),
        unchanged_production_files=len(old) - len(changed),
        new_production_files=rule["new_production_files"],
        production_comparison_scope="Frozen predecessor; only declared dispatch additions",
    )


def definition(case="block_release", index=0, *, backend="cpu", steps=None):
    rule = protocol()
    if case not in rule["cases"] or index not in rule["step_indices"]:
        raise ValueError("Unknown qualified junction case")
    root = Path(rule["prior_binding"]["root"])
    old = json.loads((root / "component-protocol.json").read_text())
    folder = root / f"evidence/cpu/junction-native/{case}/step-{index}/observed"
    row = json.loads((folder / "result.json").read_text())
    with np.load(folder / "trace.npz", allow_pickle=False) as trace:
        state, p = junctions.prepare(row, trace, old)
    a = p.active
    count = row["steps"] if steps is None else steps
    if not 0 < count <= row["steps"]:
        raise ValueError("Runtime export must stay within the qualified history")
    dt = row["dt_s"]
    values = state.active.tissue._asdict() | state.active._asdict()
    patches = a.tissue.membrane_area.size
    changes = [
        dict(
            time=round(c["time_s"] / dt) * dt,
            pump=[1.0] * patches,
            channel=[1.0] * patches,
            junction=[c["fraction"]] * patches,
        )
        for c in row["case"]["junction_changes"]
        if round(c["time_s"] / dt) <= count
    ]
    species = rule["native_species_inventory"]
    assert all(species[i] == name for name, i in row["species"].items())
    return dict(
        schema_version=1,
        model=dict(
            id=MODEL_ID,
            species=species,
            tissue={k: v.tolist() for k, v in a.tissue._asdict().items()},
            pump={k: v.tolist() for k, v in a.pump._asdict().items()},
            **{k: getattr(a, k).tolist() for k in active.Layout._fields[2:]},
            junction={k: v.tolist() for k, v in p.junction._asdict().items()},
            junction_block=p.junction_block.tolist(),
            moving_order=p.moving_order.tolist(),
            initial={k: values[k].tolist() for k in INITIAL_FIELDS}
            | dict(junction_open=state.junction_open.tolist()),
        ),
        experiment=dict(
            end_time=count * dt,
            observation_times=[i * dt for i in range(count + 1)],
            changes=changes,
        ),
        execution=dict(
            dt=dt,
            capacity=a.tissue.cell_volume.size,
            membrane_capacity=patches,
            edge_capacity=patches,
            extracellular_capacity=a.tissue.boundary_values.size,
            jit=True,
            backend=backend,
            precision="float64",
            solver=SOLVER_ID,
            max_steps=4096,
            max_trace_bytes=1024**3,
            material_balance_atol_fmol={k: 2e-11 for k in species},
        ),
    )
