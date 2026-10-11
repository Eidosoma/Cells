"""Actual saved native seed and negative-evidence checks; no simulation replay."""

import shutil

import alignment as a
import contact as c
import preparation as p
import pytest

SESSION = c.ROOT / "runs/ref-003b1-2026-09-12/alignment-05"


def test_actual_native_preparation_is_rejected_not_qualified():
    result = p.audit(SESSION)
    assert result["status"] == "mismatch_confirmed"
    assert result["alignment_qualified"] is False
    assert result["requested_cells"] == 1 and result["actual_cells"] == 7
    assert result["network_disabled"] is True
    assert result["trajectory_calls"] == 0


@pytest.mark.parametrize(
    "path,value",
    [
        (("cell_count",), 1),
        (("requested_single_cell",), False),
        (("molecules_enabled",), True),
        (("membrane_owners", 0), 99),
        (("constants", "F"), 96485.33212331001),
        (("native_initial_inside_mM", 0, 0), 11.0),
        (("cell_volumes_m3", 0), 0),
        (("installed_python_sha256", "betse/science/sim.py"), "0" * 64),
        (("native_config_sha256",), "0" * 64),
        (("time_integration_run",), True),
        (("environment", "packages", "betse"), "1.4.1"),
    ],
)
def test_changed_native_preparation_cannot_support_diagnostic(tmp_path, path, value):
    output = tmp_path / "copy"
    shutil.copytree(SESSION, output)
    native = c.read(output / "native_preparation.json")
    target = native
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    # Test-generated corruption only; never modify captured evidence.
    (output / "native_preparation.json").unlink()
    c.write(output / "native_preparation.json", native)
    with pytest.raises(ValueError):
        p.audit(output)


def test_old_passive_contact_still_authenticates():
    assert c.audit(a.PRIOR)["case_count"] == 54
