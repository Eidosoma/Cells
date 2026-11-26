"""FR-51's fraction at c_B = 0 on compiled programs (fr51-channel-block-v1 criterion Z; S, the
strong end, is in test_fr51_blocked_run.py).

About 65 s, measured cold on the timed lane: three clamped programs and two one-step programs
(jax.jit of checked_step, RK4's). Reason: the unblocked fraction must be exact at c_B = 0 and
relatively accurate at strong block where XLA flushes subnormals and may fuse operations, so D327
asks for both ends on the compiled program.
The host rows, with the plants, are in test_surface_pump_v3_populations.py.
"""

from functools import partial

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.registry.models import get_model
from validation.fr51 import engine as fr51
from validation.fr51 import plants as fr51_plants

STEP = 1e-5  # One checked step (s).


def test_the_zero_blocker_end_on_the_compiled_program():
    """FR-51's Z compiled (about 60 s: three clamped programs and two one-step programs). At every
    grid voltage u is exactly 1, and the blocked population's flux, and a second unblocked
    population's on the same patch, are the block-free world's bit for bit; one checked step of
    Z1's world is its twin's bit for bit; Z's plant, an unnormalized sum, fails there."""
    grid = np.array([-0.120 + 0.0005 * j for j in range(361)])

    def stepped(case_id, blocked):
        """(flux [V, species, channel], u [V, channel] or None, the state after one checked step)
        of the case's world with a second, unblocked Na population on the same patch."""
        raw = fr51.raw_world(case_id, blocked=blocked)
        raw["model"]["channels"].append(
            dict(raw["model"]["channels"][0], id="second", kinetic_law="cells.channel.naleak_always_open@1",
                 permeant_ions=[dict(species_id="Na", relative_permeability=1.0)])
        )  # fmt: skip
        raw["model"]["channels"][1].pop("block", None)
        raw["experiment"]["channel_controls"].append(
            dict(channel_id="second", schedule=[dict(time=0.0, availability=1.0)])
        )
        raw["execution"]["channel_capacity"] = 2
        spec = parse_spec(raw)
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        clamp = jax.jit(jax.vmap(partial(model.clamped_channel_flux, xp=jnp, block=blocked),
                                 in_axes=(None, None, None, 0)))  # fmt: skip
        out = clamp(state, control, p, grid)
        step = jax.jit(model.checked_step)(state, STEP, control, p, p.active)
        assert bool(step[1])
        return np.asarray(out[0]), (np.asarray(out[2].block.u) if blocked else None), step[0]

    blocked, twin = stepped("Z1_zero_blocker", True), stepped("Z1_zero_blocker", False)
    assert np.all(blocked[1] == 1.0)  # u, both populations, at every grid voltage.
    assert np.array_equal(blocked[0], twin[0])  # Both populations' flux, at every grid voltage.
    assert all(np.array_equal(a, b) for a, b in zip(blocked[2], twin[2], strict=True))
    with fr51_plants.zero_plant():  # Z's plant, on the compiled program.
        _, state, control, p, _ = fr51.world("Z1_zero_blocker")
        planted = fr51.program("Z1_zero_blocker")(state, control, p, grid)[2].block.u
        assert not np.all(np.asarray(planted) == 1.0)
