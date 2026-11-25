import functools
import json
from pathlib import Path

import pytest

from cells.definitions.specs import parse_spec

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_data():
    """The shared small world: two cells that convert two species and exchange them through one
    contact, open from 0, closed from 2.03 and three quarters open from 5.07, to 12 s."""
    return json.loads((ROOT / "configs/reaction_transport_pair.json").read_text())


@pytest.fixture
def spec(config_data):
    return parse_spec(config_data)


@pytest.fixture
def short_world(request, monkeypatch):
    """A row of batch_fixtures.ROUTES: a shared world's builder, short_spec by its name, with the
    row's step route planted for the test. Parametrize with indirect=True."""
    from tests.batch_fixtures import short_spec, step_route

    name, route = request.param
    step_route(monkeypatch, route)
    return functools.partial(short_spec, name)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "needs_checkout: reads files outside an execution snapshot's scope (for example configs/)",
    )
