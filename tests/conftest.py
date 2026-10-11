import json
from pathlib import Path

import pytest

from cells.core.specs import parse_spec

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_data():
    return json.loads((ROOT / "configs/single_cell_pulse.json").read_text())


@pytest.fixture
def spec(config_data):
    return parse_spec(config_data)
