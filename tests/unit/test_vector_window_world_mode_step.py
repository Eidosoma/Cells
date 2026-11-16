"""refusals="world" on the vector path: a refused step (docs/WINDOW_DEVICE_CHECKS_DESIGN.md §5.5).

The refused-step kind of test_vector_window_world_mode.py's check, in its own file to keep each
file under the tier cap: the world whose step is refused is refused alone, with batch mode's
record, and the other worlds run bitwise as in a cohort where nothing is refused.
"""

import jax
import pytest

from tests.unit.test_vector_window_world_mode import (
    refuses_one_world_and_the_others_run_as_unrefused,
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_a_refused_step_refuses_one_world_and_the_others_run_as_unrefused(monkeypatch):
    refuses_one_world_and_the_others_run_as_unrefused("refuse", monkeypatch)
