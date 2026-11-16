"""Per-law dispatch steps bit for bit like today's catalogue, the gated sheet with its junction
law (tests/inner_dispatch_worlds.py)."""

from tests.inner_dispatch_worlds import check_world


def test_declared_dispatch_steps_like_todays_catalogue_gated_sheet():
    check_world("gated_sheet")
