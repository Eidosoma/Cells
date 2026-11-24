"""The field solver a new definition declares (D147, docs/DECISIONS.md; D156 for composites).

D147: a new definition of the resolved pump family (resolved_pump_tissue@1 to @3,
resolved_pump_water@1 and @2, resolved_pump_replacement@1) with at least one free field
offset declares capacitive_reduction_gauged_damped_newton@3; a definition with none keeps
the solver it declares. The count needs only the definition: the field_offset_free leaf of
initialise(spec).layout, set by finite extracellular space with floating components
(docs/FIELD_FLOOR_ACCEPTANCE_DESIGN.md).

D156: a resolved_pump_composite@1 definition follows its inner model, whose field solve it
runs. The composite admits resolved_pump_tissue@3 alone as its inner model, so a new composite
with a free offset declares version 3 too, and one with none keeps its own. No
resolved_pump_composite@1 world of the repository's builders had a free offset when this was
added (D150's fixtures; the crossrev injection, volume, division and species sets; D152's
reaction worlds; S5's egg), so none of their definitions changes. The free-offset worlds of the
crossrev base and qualification sets carry the water and replacement IDs, already in the family,
and those guards run them as declared; frozen definitions are never redeclared.

Drivers offer CHOICES: "auto" follows D147; "2" and "3" declare that version explicitly,
and "2" reproduces the definitions made before D147.

FR-17 stage 1 (the lead's ruling, 23 November 2026): sparse_capacitive_reduction_gauged_damped_
newton@1 is version 2's method on sparse patterns, with no floor. "auto" refuses it for a
free-offset world, which D147 sends to version 3's floor, until a floor variant of the sparse ID
is qualified; a world with no free offset keeps it.
"""

import copy

import numpy as np

from cells.numerics.surface_field import FACTORED_SOLVER_ID, FLOOR_SOLVER_ID, SPARSE_SOLVER_ID

CHOICES = ("auto", "2", "3")
SOLVERS = {"2": FACTORED_SOLVER_ID, "3": FLOOR_SOLVER_ID}
FAMILY = ("resolved_pump_tissue@", "resolved_pump_water@", "resolved_pump_replacement@")
COMPOSITE = "resolved_pump_composite@"  # D156: decided by its inner model.


def in_family(raw):
    """Whether D147's trigger applies to raw: a model of the resolved pump family, or a composite
    whose inner model is one (D156)."""
    model = raw["model"]
    if model["id"].startswith(COMPOSITE):
        return str(model.get("inner_model")).startswith(FAMILY)
    return model["id"].startswith(FAMILY)


def free_field_offsets(raw):
    """The free field offsets of a raw definition's layout (0 if it has no such leaf).

    The layout is built on the CPU: the count does not depend on the declared backend.
    """
    from cells.definitions.specs import parse_spec
    from cells.execution.state import initialise

    probe = copy.deepcopy(raw)
    probe["execution"]["backend"] = "cpu"
    free = getattr(initialise(parse_spec(probe)).layout, "field_offset_free", None)
    return 0 if free is None else int(np.sum(np.asarray(free)))


def solver_for(raw, choice="auto"):
    """The field solver raw should declare under a choice (auto: D147, with D156's composites)."""
    if choice not in CHOICES:
        raise ValueError(f"Unknown field solver choice {choice!r} (one of {CHOICES})")
    if choice != "auto":
        return SOLVERS[choice]
    declared = raw["execution"].get("field_solver")
    if not in_family(raw):
        return declared
    if free_field_offsets(raw) > 0:
        if declared == SPARSE_SOLVER_ID:
            raise ValueError(
                f"{SPARSE_SOLVER_ID} has no floor variant yet: a world with free field offsets "
                f"declares {FLOOR_SOLVER_ID} (D147)"
            )
        return FLOOR_SOLVER_ID
    return declared


def declare(raw, choice="auto"):
    """A copy of raw that declares solver_for(raw, choice); unchanged when that is its own."""
    solver = solver_for(raw, choice)
    out = copy.deepcopy(raw)
    if solver is not None:
        out["execution"]["field_solver"] = solver
    return out
