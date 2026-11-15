"""Per-law dispatch steps bit for bit like today's catalogue, the five-law release world (both
pumps, ARS(2,2,2)) and the RK4 single patch (tests/inner_dispatch_worlds.py)."""

import pytest

from tests.inner_dispatch_worlds import check_world


@pytest.mark.parametrize("name", ["release", "rk4_single_patch"])
def test_declared_dispatch_steps_like_todays_catalogue(name):
    check_world(name)
