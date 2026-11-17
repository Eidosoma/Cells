"""NUM-009 v2 general-engineering preflights, not extra full-panel attempts."""

import subprocess

import numpy as np
import pytest

from tests import finite_extracellular_numerical_data as data
from tests import finite_extracellular_numerical_data_v2 as binding
from tests import finite_extracellular_tangent as tangent
from tests import reference_finite_extracellular_dynamics as v1
from tests import reference_finite_extracellular_dynamics_v2 as ref
from tests.unit.test_finite_extracellular_dynamics import small as small


@pytest.fixture(scope="module")
def panel():
    return binding.load_panel()


def observations(case, arrays, method, samples):
    return arrays | {
        "sample_times_s": samples,
        "sample_state": ref.sample_record(case, arrays, method, samples),
    }


@pytest.fixture(scope="module")
def small_records(panel, small):
    records, stats = {}, {}
    samples = ref.comparison_grid(small, panel[0]["candidate"])
    for setting in panel[0]["references"]:
        arrays, stats[setting["id"]] = ref.integrate_reference(small, setting)
        records[setting["id"]] = observations(small, arrays, setting["method"], samples)
    for dt in panel[0]["candidate"]["steps_s"]:
        name = f"rk4_{dt:g}"
        arrays, stats[name] = ref.integrate_candidate(small, dt, budget=tangent.Budget())
        assert stats[name]["status"] == "complete"
        records[name] = observations(small, arrays, "RK4", samples)
    return records, stats


def total_matrix(case):
    result = np.zeros((case.layout.s, case.size))
    for s, indices in enumerate(tangent.amount_indices(case).T):
        result[s, indices] = 1
    return result


def test_unavailable_differentiation_interval_is_refused():
    with pytest.raises(v1.DomainViolation):
        tangent.difference_rule(1e-6, 0.0, 0.0)


def test_read_only_v2_auditor_imports_no_rhs_or_ode():
    result = subprocess.run(
        [
            str(data.ROOT / ".venv/bin/python"),
            "-c",
            "import sys; from scripts import audit_finite_extracellular_reference_v2; "
            "assert 'scipy.integrate' not in sys.modules; assert 'cells' not in sys.modules; "
            "assert 'tests.finite_extracellular_tangent' not in sys.modules",
        ],
        cwd=data.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
