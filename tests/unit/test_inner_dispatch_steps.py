"""Per-law dispatch steps bit for bit like today's catalogue, the heredity cell with and without
pumps (tests/inner_dispatch_worlds.py; the other worlds are test_inner_dispatch_steps_*.py)."""

import pytest

from tests.inner_dispatch_worlds import check_world


@pytest.mark.parametrize("name", ["heredity_D", "heredity_D_no_pumps"])
def test_declared_dispatch_steps_like_todays_catalogue(name):
    check_world(name)
