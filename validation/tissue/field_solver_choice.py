"""The field solver a new definition declares (D147, docs/DECISIONS.md).

D147: a new definition of the resolved pump family (resolved_pump_tissue@1 to @3,
resolved_pump_water@1 and @2, resolved_pump_replacement@1) with at least one free field
offset declares capacitive_reduction_gauged_damped_newton@3; a definition with none keeps
the solver it declares. The count needs only the definition: the field_offset_free leaf of
initialise(spec).layout, set by finite extracellular space with floating components
(docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md).

Drivers offer CHOICES: "auto" follows D147; "2" and "3" declare that version explicitly,
and "2" reproduces the definitions made before D147.
"""

import copy

import numpy as np

from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID

CHOICES = ("auto", "2", "3")
SOLVERS = {"2": FACTORED_SOLVER_ID, "3": FLOOR_SOLVER_ID}
FAMILY = ("resolved_pump_tissue@", "resolved_pump_water@", "resolved_pump_replacement@")


def free_field_offsets(raw):
    """The free field offsets of a raw definition's layout (0 if it has no such leaf).

    The layout is built on the CPU: the count does not depend on the declared backend.
    """
    from cells.core.specs import parse_spec
    from cells.core.state import initialise

    probe = copy.deepcopy(raw)
    probe["execution"]["backend"] = "cpu"
    free = getattr(initialise(parse_spec(probe)).layout, "field_offset_free", None)
    return 0 if free is None else int(np.sum(np.asarray(free)))


def solver_for(raw, choice="auto"):
    """The field solver raw should declare under a choice (auto: D147)."""
    if choice not in CHOICES:
        raise ValueError(f"Unknown field solver choice {choice!r} (one of {CHOICES})")
    if choice != "auto":
        return SOLVERS[choice]
    declared = raw["execution"].get("field_solver")
    if not raw["model"]["id"].startswith(FAMILY):
        return declared
    return FLOOR_SOLVER_ID if free_field_offsets(raw) > 0 else declared


def declare(raw, choice="auto"):
    """A copy of raw that declares solver_for(raw, choice); unchanged when that is its own."""
    solver = solver_for(raw, choice)
    out = copy.deepcopy(raw)
    if solver is not None:
        out["execution"]["field_solver"] = solver
    return out
