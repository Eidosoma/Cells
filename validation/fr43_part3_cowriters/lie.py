"""The Lie plant's host patch (CRITERIA.md §6.1, P3; SPEC.md §2): the composite's step runs the
second halves of its split parts in declared order, in place of the reverse.

The composite's split step (cells/models/pump_composite.py, Composition.split_step) runs each split
part's first half in declared order, the inner step, then the second halves over
`reversed(splits)`: Strang's symmetric splitting. The patch binds the module's name `reversed` to
an iterator in the given order, in this process only, so that one loop runs in declared order and
nothing else changes: Lie's splitting, first order in the step. It refuses unless that loop is the
module's one use of the name (check_site, a structural check of the source), so it cannot change
anything else. Compiled programs are cleared before and after.

A plant run's definition, inputs and operators are its honest run's (TABLE.md §4); its record
names the patch (`host_patch`: ID and CHANGE).
"""

import ast
import contextlib
import inspect

ID = "second_halves_declared_order"
CHANGE = (
    "cells.models.pump_composite: Composition.split_step runs the split parts' second halves in "
    "declared order instead of reversed (the module's name `reversed` bound to an iterator in the "
    "given order, in the plant's process only): Lie splitting in place of Strang's"
)


def _declared_order(sequence):
    return iter(sequence)


def check_site(module):
    """Refuse unless the module's one use of `reversed` is split_step's loop `for op in
    reversed(splits)` in class Composition, and the module defines no name `reversed`."""
    if "reversed" in vars(module):
        raise RuntimeError(f"{module.__name__} already binds the name `reversed`")
    tree = ast.parse(inspect.getsource(module))
    uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "reversed"]
    if len(uses) != 1:
        raise RuntimeError(f"{module.__name__} uses `reversed` {len(uses)} times, not once")
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Composition"]
    steps = [
        n
        for c in classes
        for n in c.body
        if isinstance(n, ast.FunctionDef) and n.name == "split_step"
    ]
    loops = [
        n
        for step in steps
        for n in ast.walk(step)
        if isinstance(n, ast.For)
        and isinstance(n.iter, ast.Call)
        and isinstance(n.iter.func, ast.Name)
        and n.iter.func.id == "reversed"
        and [ast.unparse(a) for a in n.iter.args] == ["splits"]
    ]
    if len(loops) != 1:
        raise RuntimeError("Composition.split_step has no loop `for ... in reversed(splits)`")


@contextlib.contextmanager
def second_halves_in_declared_order():
    """The patch (module docstring), for the duration of the context."""
    import jax

    from cells.models import pump_composite as module

    check_site(module)
    jax.clear_caches()
    module.reversed = _declared_order
    try:
        yield
    finally:
        del module.reversed
        jax.clear_caches()
