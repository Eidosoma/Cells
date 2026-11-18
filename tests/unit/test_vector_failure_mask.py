"""The vector windows' failure mask (cells.core.vector_windows).

Each world's failures are one int32: bit 0 is the step refusal, and the model's device checks
follow from FAILURE_SHIFT (both _pack calls take it).
- The capacity follows from the dtype and the shift: MAX_DEVICE_CHECKS is 31.
- The last supported check takes bit 31, int32's sign bit. Every check's bit, that one included,
  round-trips through a real window: _pack, the scan's acceptance (flags, accept and _expand's
  state selection), the transfer to the host and the host's reader (_unpack).
- A model with 32 checks is refused at admission (require_device_checks, called before any device
  allocation), and one with 31 is admitted.
"""

from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import vector_windows as vw
from cells.core.specs import ConfigError

CHECKS = tuple(f"check_{k}" for k in range(vw.MAX_DEVICE_CHECKS))  # The last supported count.


def test_the_capacity_follows_from_the_mask_and_its_shift():
    assert vw.FAILURE_SHIFT == 1  # Bit 0 is the step refusal.
    assert vw.MAX_DEVICE_CHECKS == jnp.iinfo(vw.FAILURE_MASK_DTYPE).bits - vw.FAILURE_SHIFT == 31


def model_with(n):
    hooks = dict.fromkeys(vw.DEVICE_HOOKS)
    return SimpleNamespace(**hooks | {"DEVICE_CHECKS": tuple(f"check_{k}" for k in range(n))})


def test_admission_holds_31_checks_and_refuses_32():
    vw.require_device_checks(model_with(31))
    with pytest.raises(ConfigError, match="at most 31 device checks.*This model declares 32"):
        vw.require_device_checks(model_with(32))


def window(failing):
    """One window of three steps for two worlds, with len(CHECKS) device checks. World 0's check
    `failing` fails at row 2 (or its step is refused there, for "step"); world 1 never fails.
    Returns the window's outputs, moved to the host."""
    target = jnp.asarray([-2 if failing == "step" else failing, -1], dtype=jnp.int32)

    def step(state, dt, control, params, active):
        refused = (params == -2) & (state["row"] == 1)  # Its step into row 2.
        return {"x": state["x"] + dt, "row": state["row"] + 1}, ~refused

    def checks(previous, row, params, constants, steps):
        failed = (jnp.arange(len(CHECKS)) == params) & (steps == 2)
        return failed, jnp.zeros(1)

    zeros = jnp.zeros(2, dtype=jnp.int32)
    outputs = vw._vector_window(
        {"x": jnp.zeros(2), "row": zeros},
        jnp.full((2, 3), 0.25),
        jnp.asarray([3, 3], dtype=jnp.int32),
        jnp.zeros((2, 1)),
        jnp.zeros((2, 3), dtype=jnp.int32),
        jnp.zeros((2, 3), dtype=jnp.int32),
        zeros,
        target,
        jnp.ones(2, dtype=bool),
        zeros,
        step=step,
        checks=checks,
        rows=1,
    )
    return jax.device_get(outputs)


@pytest.mark.parametrize("failing", [*range(len(CHECKS)), "step"])
def test_every_bit_round_trips_through_a_window_and_the_host_reader(failing):
    final, first, bits, _, _ = window(failing)
    expected = ("step",) if failing == "step" else (CHECKS[failing],)
    assert int(first[0]) == 2 and vw._unpack(bits[0], CHECKS) == expected
    if failing == len(CHECKS) - 1:  # The sign bit: a negative mask, still a failure.
        assert int(bits[0]) == np.iinfo(np.int32).min
    # Acceptance: world 0 kept its row-1 state (row 2 refused); world 1 took all three steps.
    assert float(final["x"][0]) == 0.25 and int(final["row"][0]) == 1
    assert int(first[1]) == -1 and int(bits[1]) == 0 and float(final["x"][1]) == 0.75
