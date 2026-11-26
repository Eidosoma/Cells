"""One computation: a family's frozen definition and its composite rewrite run as one computation.

The check of test_pump_composite_contract.py's test_a_frozen_definition_and_its_rewrite_are_one_
computation (the test review's parity, which the lead made the condition of its removals on 25
November 2026), as a function of the definition, with the runner's other inputs added: the family's
own format and its rewrite through cells.definitions.pump_composite_spec.frozen_definition give an
equal composite spec, the same implementation object, equal execution blocks, and bit-identical
initial state, layout, parameters, controls at every point of the world's event grid and
integration steps. These are what core/runner.run takes from a definition: the family's step,
right-hand side and checks are the composition's own objects (pump_composite.FamilyModel), and its
other calls pass the composition its composite spec. Host only: nothing is compiled or run.

What a run adds is the host's reading of it through the family's own names (its summarize, say),
which this cannot see. The frozen = composite guards (test_pump_composite_water.py,
test_pump_composite_replacement.py) check their worlds here, keep one compiled run of both formats
per family, and read the replacement's other worlds' runs through both summaries (D390's slimming).
"""

import numpy as np


def same_bits(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def assert_one_computation(raw):
    """Assert that RAW and its frozen_definition rewrite are one computation; (frozen, rewrite)."""
    import jax

    from cells.definitions import pump_composite_spec as cs
    from cells.definitions.specs import parse_spec
    from cells.execution.grid import EventGrid
    from cells.execution.runner import integration_steps  # The step sequence: the last input.
    from cells.execution.schedule import control_values as scheduled_controls
    from cells.registry.models import get_model

    frozen, rewrite = parse_spec(raw), parse_spec(cs.frozen_definition(raw))
    family, model = get_model(frozen.model), get_model(rewrite.model)
    assert family.module.composite(frozen) == rewrite
    assert family.composition is model
    assert frozen.execution == rewrite.execution
    state, layout = model.initial_values(rewrite)
    frozen_state, frozen_layout = family.initial_values(frozen)
    assert type(state) is type(frozen_state) and type(layout) is type(frozen_layout)
    for name in type(state)._fields:
        assert same_bits(getattr(state, name), getattr(frozen_state, name)), name
    for name in type(layout)._fields:
        a, b = getattr(layout, name), getattr(frozen_layout, name)
        assert same_bits(a, b) if hasattr(a, "shape") else a == b, name
    leaves, treedef = jax.tree_util.tree_flatten(model.parameters(rewrite, layout))
    frozen_leaves, frozen_treedef = jax.tree_util.tree_flatten(
        family.parameters(frozen, frozen_layout)
    )
    assert treedef == frozen_treedef
    for k, (a, b) in enumerate(zip(leaves, frozen_leaves, strict=True)):
        assert same_bits(a, b) if hasattr(a, "shape") else a == b, f"parameters leaf {k}"
    grid = EventGrid(frozen)
    times = [grid[i] for i in range(len(grid))]
    controls, frozen_controls = cs.control_values(rewrite, times), scheduled_controls(frozen, times)
    assert controls._fields == frozen_controls._fields
    for name, a, b in zip(controls._fields, controls, frozen_controls, strict=True):
        assert same_bits(a, b), name
    rewrite_grid = EventGrid(rewrite)
    assert [rewrite_grid[i] for i in range(len(rewrite_grid))] == times
    steps = [integration_steps(spec, np.asarray(times)) for spec in (frozen, rewrite)]
    assert same_bits(*steps)
    return frozen, rewrite
