"""Explicit routing is auditable and cannot silently turn failures into passes."""

import pytest

from scripts import test_finite_extracellular_build as driver


@pytest.mark.parametrize("key", ["PYTEST_ADDOPTS", "PYTEST_PLUGINS"])
def test_driver_rejects_inherited_hidden_routing(tmp_path, monkeypatch, key):
    monkeypatch.setenv(key, "unregistered")
    with pytest.raises(ValueError, match="inherited pytest overrides"):
        driver.run_tests(tmp_path / "matrix")
