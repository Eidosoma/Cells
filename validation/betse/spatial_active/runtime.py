"""Export only initial/static native inputs and authenticate the qualified baseline."""

import json
from pathlib import Path

import numpy as np

from cells.core.betse_spatial_spec import INITIAL_FIELDS, SOLVER_ID
from cells.numerics import betse_active as active
from validation.betse.spatial_active import fixtures, refinement

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_PATH = Path(__file__).with_name("runtime_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline():
    rule = protocol()
    binding = rule["prior_binding"]
    root = Path(binding["root"])
    assert refinement.digest(root / "completion.json") == binding["completion_sha256"]
    # Verify the predecessor against its OWN frozen production sources: the
    # ordinary runner is deliberately changing, the qualified kernel is not.
    report = refinement.completed_prior(binding, current_root=root / "source")
    registration = json.loads((root / "registration.json").read_text())
    allowed = set(rule["allowed_prior_source_changes"])
    differences, unchanged = [], []
    for name, digest in registration["sources_sha256"].items():
        if not name.startswith("src/"):
            continue
        if refinement.digest(ROOT / name) != digest:
            assert name in allowed, "Unregistered production change: " + name
            differences.append(name)
        else:
            unchanged.append(name)
    report["production_comparison_scope"] = (
        "Predecessor frozen source, then explicit runtime-change allowlist"
    )
    report["unchanged_production_files"] = len(unchanged)
    report["changed_prior_runtime_files"] = differences
    report["new_runtime_files"] = rule["new_runtime_files"]
    assert "src/cells/numerics/betse_active.py" in unchanged
    assert "src/cells/numerics/betse_spatial.py" in unchanged
    return report


def definition(case="coupled", index=2, *, backend="cpu", steps=None):
    root = Path(protocol()["prior_binding"]["root"])
    old_protocol = json.loads((root / "component-protocol.json").read_text())
    if case not in {v["id"] for v in old_protocol["cases"]} or index not in (0, 1, 2):
        raise ValueError("Unknown qualified native case")
    folder = root / f"evidence/cpu/long-active-native/{case}/step-{index}/observed"
    row = json.loads((folder / "result.json").read_text())
    with np.load(folder / "trace.npz", allow_pickle=False) as trace:
        state, p = fixtures.prepare(row, trace, old_protocol)
    species = protocol()["native_species_inventory"]
    assert p.tissue.valence.tolist() == [1, 1, -1, 2, -1, -1]
    assert p.tissue.moving.tolist() == [True, True, True, False, False, False]
    assert all(species[index] == name for name, index in row["species"].items())
    count = row["steps"] if steps is None else steps
    if not 0 < count <= row["steps"]:
        raise ValueError("Export duration must fit qualified history")
    dt = row["dt_s"]
    values = dict(state.tissue._asdict()) | state._asdict()
    return dict(
        schema_version=1,
        model=dict(
            id=active.MODEL_ID,
            species=species,
            tissue={k: v.tolist() for k, v in p.tissue._asdict().items()},
            pump={k: v.tolist() for k, v in p.pump._asdict().items()},
            **{k: getattr(p, k).tolist() for k in active.Layout._fields[2:]},
            initial={k: values[k].tolist() for k in INITIAL_FIELDS},
        ),
        experiment=dict(
            end_time=count * dt,
            observation_times=[i * dt for i in sorted({0, count // 2, count})],
        ),
        execution=dict(
            dt=dt,
            capacity=p.tissue.cell_volume.size,
            membrane_capacity=p.tissue.membrane_area.size,
            edge_capacity=p.tissue.membrane_area.size,
            extracellular_capacity=p.tissue.boundary_values.size,
            jit=True,
            backend=backend,
            precision="float64",
            solver=SOLVER_ID,
            max_steps=4096,
            max_trace_bytes=1024**3,
            material_balance_atol_fmol={k: 2e-11 for k in species},
        ),
    )
