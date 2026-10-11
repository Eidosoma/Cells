"""Small real reference-worker check using the regenerated seven-cell preparation."""

import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).parent
PARENT = Path("/mnt/workspaces/Cells/ref-005e-fresh-20260919-01")


def test_reference_row_preserves_equations_and_reports_all_species(tmp_path):
    module_spec = importlib.util.spec_from_file_location("long_relaxation_job", HERE / "run.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    preparation = module.read(PARENT / "prepare/preparation.json")
    plan = copy.deepcopy(module.read(PARENT / "registration.json")["protocol"])
    plan["duration_s"] = 0.001
    plan["reference"]["sample_dt_s"] = 0.001 / 1000
    setting = plan["reference"]["solves"][0]
    definition = {
        "rows": [{"case": "pump_leak", "duration_s": 0.001, "plan": plan, "setting": setting}],
        "preparation": preparation,
        "runtime": module.runtime(),
        "sources_sha256": module.source_files(),
    }
    module.write(tmp_path / "registration.json", definition)
    (tmp_path / "rows/0").mkdir(parents=True)
    result = module.row(tmp_path, 0)
    assert result["steady_state_qualified"] is False
    assert result["min_concentration_mM"] > 0
    assert result["max_energy_residual_pJ"] <= plan["accounting"]["cells_energy_pJ"]
    residual = result["last_tenth_window"]
    assert len(residual["max_abs_inside_concentration_rate_mM_s"]) == 7
    assert all(len(v) == 3 for v in residual["max_abs_inside_concentration_rate_mM_s"])
    assert len(residual["max_abs_outside_concentration_rate_mM_s"]) == 3
    saved = json.loads((tmp_path / "rows/0/result.json").read_text())
    assert saved["trajectory_sha256"] == module.sha(tmp_path / "rows/0/trajectory.json")
