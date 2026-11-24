"""Free-offset composites and the solver-change refusal for D147's composite tests (D156).

tests/unit/test_field_solver_composite.py (no stepping) and test_field_solver_composite_runs.py
(the runs). Two resolved_pump_composite@1 definitions with one free field offset each, built with
field solver version 2:
- minimal: D150's quiescent one-cell world (validation/tissue/secreted_species_fixtures.world)
  with the cell's wall patch on its finite node, so the capacitor component {cell_0, ecs_0}
  holds no bath, and ion diffusivity on the node's face, the outside return path a floating
  component needs (numerics/surface_field.py). Its compositions are the bath's, so it stays
  quiescent; it has no channels, so its programs compile in about 20 s;
- release: surface_pump_v3_fixtures' padded release world made a composite with no operators
  (pump_composite_spec.frozen_definition), the world composite_crossrev's replacement_padded
  starts from (two cells, five outside nodes, NaV1.2 channels, IMEX only);
- replacement: composite_crossrev's replacement_padded made a composite, the operator-bearing
  case: that world under scheduled_cell_replacement@1 with two own-template events. Stepped under
  versions 2 and 3 through both events it ran bitwise alike with equal diagnostics, about 80 s a
  program on a shared CPU, too long for a test (the advisor's check of 14 November:
  /mnt/workspaces/Cells/architecture-block-20261114-01/check-round.json).
"""

import copy

import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import branch_checkpoint, validate_checkpoint
from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID, SPARSE_SOLVER_ID
from cells.records.io import load_snapshot, write_snapshot
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import surface_pump_v3_fixtures as v3fx

IMEX = "imex_ars222_face_electromigration@1"
FLIP = {
    FACTORED_SOLVER_ID: FLOOR_SOLVER_ID,
    FLOOR_SOLVER_ID: FACTORED_SOLVER_ID,
    SPARSE_SOLVER_ID: FACTORED_SOLVER_ID,
}


def minimal(end=None):
    """The minimal free-offset composite, to 4 ms at 1 ms (max_steps 12); with `end`, the same
    definition to a later end, its execution block unchanged."""
    raw = fx.world(dt=1e-3, end=0.004)
    for membrane in raw["model"]["membranes"]:
        if membrane["id"] == "wall_cell_0":
            membrane["outside"] = "ecs_0"
    face = raw["model"]["faces"][0]
    for s, z in fx.ION_SPECIES:
        if z != 0:
            face["diffusivity_m2_per_s"][s] = 1e-9
    if end is not None:
        raw["experiment"]["end_time"] = end
        raw["experiment"]["observation_times"] = [0.0, end]
    return raw


def release():
    return cs.frozen_definition(v3fx.definition("release", solver=IMEX))


def replacement():
    """composite_crossrev's replacement_padded, built as it builds it, made a composite."""
    from cells.definitions.cell_replacement_spec import exact_event_times
    from validation.tissue import cell_replacement_fixtures as rfx

    padded = v3fx.definition("release", solver=IMEX)
    padded["experiment"]["end_time"] = 0.0012
    padded["experiment"]["observation_times"] = [0.0, 0.0012]
    p1, p2 = exact_event_times((4, 9), padded["execution"]["dt"])
    own = [
        rfx.template_from_cell(padded, "cell_0", "own_0"),
        rfx.template_from_cell(padded, "cell_1", "own_1"),
    ]
    events = ((p1, "cell_0", "own_0", "n1"), (p2, "cell_0", "own_0", "n2"))
    return cs.frozen_definition(rfx.with_replacement(padded, own, events))


def with_solver(raw, solver):
    out = copy.deepcopy(raw)
    out["execution"]["field_solver"] = solver
    return out


def refused_across_the_change(raw, checkpoint, directory):
    """A checkpoint of raw (a minimal() definition) does not resume under the other field solver,
    directly or through a snapshot saved in directory: validate_checkpoint refuses its layout and
    branch_checkpoint the execution change, while the same branch without it is admitted."""
    solver = raw["execution"]["field_solver"]
    later = copy.deepcopy(raw)
    later["experiment"].update(end_time=0.006, observation_times=[0.0, 0.006])
    saved = load_snapshot(write_snapshot(directory, parse_spec(raw), checkpoint))
    for spec, point in ((parse_spec(raw), checkpoint), (saved.spec, saved.checkpoint)):
        with pytest.raises(ConfigError, match="layout"):
            validate_checkpoint(parse_spec(with_solver(raw, FLIP[solver])), point)
        with pytest.raises(ConfigError, match="model or execution settings"):
            branch_checkpoint(spec, point, parse_spec(with_solver(later, FLIP[solver])))
        assert branch_checkpoint(spec, point, parse_spec(later)).step_index == point.step_index
