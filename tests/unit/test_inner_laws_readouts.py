"""Per-law dispatch's compiled readouts against today's catalogue (D172/D176; the note's §7.4 (b)).

Split from test_inner_laws.py for the tiers (its two compiled-readouts tests took most of its time;
the helpers stay there). On the host every output is bitwise, padding included (the declared
fill); compiled, every output is bitwise but the two padding columns at a Kv1.5-free world's
inactive slots, and an undeclared pump's rates up to the sign of a zero.
"""

import jax
import numpy as np

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import parse_spec
from cells.models import surface_pump_v3
from cells.registry.models import get_model
from tests.unit.test_inner_laws import (
    ARS,
    compiled_matches,
    flat_readouts,
    initial,
    padded,
    same_bits,
    without_pumps,
)
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import surface_pump_v3_fixtures as fixtures


def test_dispatch_readouts_are_todays_with_the_host_padding_fill():
    """Readouts at the initial state, the object's against the module's: on the host every output
    is bitwise, padding included (the declared fill, §7.4 (b)); compiled, every output is bitwise
    but the two padding columns at a Kv1.5-free world's inactive slots, which read 0 and 1."""
    worlds = (
        padded(parse_spec(water_fixtures.heredity_cell("D", end_time=0.01))),
        parse_spec(fixtures.definition("release", solver=ARS)),
    )
    for spec in worlds:
        impl = get_model(spec.model)
        state, control, p = initial(spec, impl)
        host = flat_readouts(impl.readouts(state, control, p, xp=np))
        today = flat_readouts(surface_pump_v3.readouts(state, control, p, xp=np))
        assert all(same_bits(host[k], today[k]) for k in today)
        compiled = flat_readouts(jax.jit(impl.readouts)(state, control, p))
        reference = flat_readouts(jax.jit(surface_pump_v3.readouts)(state, control, p))
        inactive = ~np.asarray(p.channel_active)
        kv = spec3.KV1P5_LAW_ID in impl.declared_channel_laws
        padding = ("channel_targets", "channel_tau_s")
        for key in padding:
            if not kv and inactive.any():
                assert same_bits(compiled[key][..., ~inactive], reference[key][..., ~inactive])
                fill = 0.0 if key == "channel_targets" else 1.0
                assert np.all(compiled[key][..., inactive] == fill)
            else:
                assert same_bits(compiled[key], reference[key]), key
        compiled_matches(
            {k: v for k, v in compiled.items() if k not in padding},
            {k: v for k, v in reference.items() if k not in padding},
        )


def test_pump_and_junction_dispatch_readouts_are_todays():
    """Undeclared pumps and junction laws give today's bits through today's expressions, on the
    host and compiled, in worlds without a calcium pump, without any pump and with junctions."""
    heredity = water_fixtures.heredity_cell("D", end_time=0.01)
    for raw in (heredity, without_pumps(heredity), water_fixtures.gated_sheet(end_time=0.01)):
        spec = parse_spec(raw)
        impl = get_model(spec.model)
        state, control, p = initial(spec, impl)
        host = flat_readouts(impl.readouts(state, control, p, xp=np))
        today = flat_readouts(surface_pump_v3.readouts(state, control, p, xp=np))
        assert all(same_bits(host[k], today[k]) for k in today)
        compiled = flat_readouts(jax.jit(impl.readouts)(state, control, p))
        reference = flat_readouts(jax.jit(surface_pump_v3.readouts)(state, control, p))
        compiled_matches(compiled, reference)
