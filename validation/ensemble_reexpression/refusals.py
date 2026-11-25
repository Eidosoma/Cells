"""What the engine raised, as a kind of refusal (spec/TABLE.md §4), and the rows a refused run
keeps.

The mapping, which README.md lists for the checker:
- `check`: a NumericalError of the engine's own ledgers or of its dissipation, at a completed row,
  or a pool whose finite material does not balance;
- `domain`: any other NumericalError, and a ConfigError or AssemblyError whose message names a
  domain, a bound or a range that a declared value left (OUT_OF_RANGE);
- `definition`: every other refusal at parse or before a step;
- `harness`: anything the engine did not raise as one of these.
"""

import dataclasses
import re

import numpy as np

from cells.assembly.spec import AssemblyError
from cells.definitions.specs import ConfigError
from cells.execution.energy_check import MESSAGE as ENERGY_MESSAGE
from cells.execution.errors import NumericalError
from cells.execution.grid import EventGrid, applied_definition
from cells.execution.windows import WindowPolicy, iter_windows
from cells.models.surface_pump import DISSIPATION_MESSAGE, LEDGER_MESSAGE
from cells.registry.models import get_model

DEFINITION, DOMAIN, CHECK, HARNESS = "definition", "domain", "check", "harness"
SECOND_PASS = "second_pass_completed"  # A check's refusal that its second pass does not meet.
PARTIAL, WINDOW_STEPS = "partial.npz", 1  # The second pass's rows, and its windows' length.
POLICY = WindowPolicy(WINDOW_STEPS, "full")  # The second pass's windows, every row recorded.
CHECKS = (LEDGER_MESSAGE, DISSIPATION_MESSAGE, ENERGY_MESSAGE)
POOL_CHECKS = ("Finite material conservation failed", "Material transfer counters disagree")
# A declared value that left a range the message states. The engine's words: "domain" (the laws' and
# the field's), "RK4 steps" and "step exceeds" (the laws' and the solvers' step bounds), "must lie
# in", "cannot exceed", "must be finite and positive" and "nonnegative", "exceeds"; and of Part 2's
# pieces "must be >" a number, "finite positive number", "is finite and >= 0", a parameter that "is
# positive", "at least" or "at most", "is a normal float".
OUT_OF_RANGE = re.compile(
    r"\bdomain\b|RK4 steps|\bstep exceeds\b|must lie in|must be in \[|cannot exceed|"
    r"must be finite and (?:positive|nonnegative)|exceeds positive finite|reached its event cap|"
    r"must be >=? |must be a finite positive number|is finite and >= 0|"
    r"parameter \S+ is (?:positive|at least|at most)|is a normal float"
)
# One refusal of the engine's names a law and a range together. Its law is today's in every block
# that reaches it with the label's string, so what left its place is the range.
GATE = re.compile(r"Junction gate requires \S+, a threshold in")


def kind_of(error, *, stage, gates=()):
    """The kind of an exception. stage: "parse" or "run"; gates: the laws that the declaration's
    junction gates name, for the one message that names a law and a range together."""
    message = str(error)
    if isinstance(error, NumericalError):
        return CHECK if message.startswith(CHECKS) else DOMAIN
    if isinstance(error, (ConfigError, AssemblyError)):
        if any(text in message for text in POOL_CHECKS):
            return CHECK
        if OUT_OF_RANGE.search(message):
            return DOMAIN
        if GATE.search(message) and gates and all(law in message for law in gates):
            return DOMAIN
        return DEFINITION
    if stage == "parse" and isinstance(error, (KeyError, TypeError, AttributeError, IndexError)):
        return DEFINITION  # The engine's parser could not read the declaration.
    return HARNESS


def qualified(kind):
    """A class's full name: its module and its name in it (a record's `raised`)."""
    return f"{kind.__module__}.{kind.__qualname__}"


def policy():
    """Every field of the second pass's window policy, its defaults written out."""
    return dataclasses.asdict(POLICY)


def refusal(error, *, stage, gates=(), time=None):
    """A table entry's `refusal`."""
    return {
        "kind": kind_of(error, stage=stage, gates=gates),
        "message": str(error),
        "time_s": time,
    }


def rows_before(spec, checkpoint=None):
    """(the accepted rows of a run that the engine refuses, as trajectory.npz's arrays; the time of
    the row that failed, or None where the pass completes; the class of what the pass raised there).

    The scalar runner keeps no row of a run it refuses. This runs the same definition again in
    windows of one step, through the engine's own windowed path, and keeps each one it accepts."""
    applied = applied_definition(spec)[0]
    grid = EventGrid(applied)
    start = 0 if checkpoint is None else checkpoint.step_index
    windows, failed, raised = [], None, None
    try:
        for window in iter_windows(spec, POLICY, checkpoint):
            windows.append(window)
    except NumericalError as error:
        failed = float(grid[min(start + len(windows) + 1, len(grid) - 1)])
        raised = qualified(type(error))
    return joined(windows, get_model(spec.model)), failed, raised


def joined(windows, model):
    """Adjacent windows' rows as one trajectory's arrays; adjacent windows share one row."""
    if not windows:
        return None
    arrays = {
        name: np.concatenate(
            [np.asarray(getattr(w.history, name))[min(k, 1) :] for k, w in enumerate(windows)]
        )
        for name in model.STATE_TYPE._fields
    }
    arrays["accepted_times"] = np.concatenate(
        [np.asarray(w.times)[min(k, 1) :] for k, w in enumerate(windows)]
    )
    for name in vars(windows[0].observations):
        key = "observation_times" if name == "times" else f"observed_{name}"
        arrays[key] = np.concatenate([np.asarray(getattr(w.observations, name)) for w in windows])
    return arrays
