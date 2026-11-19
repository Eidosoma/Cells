"""A composite's values for the readers of a model's values (FR-8's engine gap,
validation/long_duration/RESULTS_20261118.md §7).

surface_pump_projective.settling reads the channel gates' targets as values.channel_targets. A
composite's values nest the inner model's under `ionic`, so the lookup found nothing and the readout
silently dropped the channel gates: at FR-8's W0's initial row it reported the junction gates'
largest distance (1.8e-4) where the channel gates' is 0.022, 124 times larger. The composite's
values now forward the inner's targets as a property, with no field added, so settling on the
composite equals settling on the inner model at the composite's view and effective control, as
FR-8's M4 evaluates it. Planted: the values without the property, as the composite's were, report
the junction gates' distance only, which the test tells apart.
"""

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.schedule import control_values
from cells.models import surface_pump_projective as projective
from cells.registry.models import get_model
from validation.long_duration import worlds


def w0():
    """FR-8's W0 (validation/long_duration/worlds.w0), bound, with its control at t = 0."""
    spec = parse_spec(worlds.w0(end=0.01))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(np.asarray(v)[0] for v in controls))
    return model, state, control, p


def at_the_view(model, state, control, p):
    """settling on the inner model at the composite's view and effective control (FR-8's M4)."""
    return projective.settling(
        model.inner,
        model.inner_state(state),
        model.control_view(control, state, p, xp=np),
        model.view(p, state, xp=np),
    )


def test_settling_on_a_composite_reads_its_channel_gates():
    model, state, control, p = w0()
    values = model.readouts(state, control, p, xp=np)
    assert values.channel_targets is values.ionic.channel_targets
    # A property, not a field: the values' fields, and so every record and traced program, are
    # unchanged; a rebuilt or traced copy keeps it.
    assert "channel_targets" not in type(values)._fields
    assert type(values._replace(valid=values.valid)) is type(values)
    assert type(jax.tree_util.tree_map(lambda x: x, values)) is type(values)
    direct = projective.settling(model, state, control, p)
    assert direct[0] and direct == at_the_view(model, state, control, p)

    # Planted: the values without the property, as the composite's were before the fix.
    plain = type(values).__bases__[0]

    class Before:
        def readouts(self, *args, **kwargs):
            return plain(*model.readouts(*args, **kwargs))

    before = projective.settling(Before(), state, control, p)
    assert before[0] and before[1] == direct[1]
    assert direct[2] > 100 * before[2] > 0  # The channel gates were dropped (FR-8: 124 times).
