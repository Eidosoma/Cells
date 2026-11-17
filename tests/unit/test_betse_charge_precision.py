"""Independent charge arithmetic and unchanged saved native BETSE targets."""

import itertools
import json
from decimal import Decimal, localcontext
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.processes.electrochemistry import F
from tests.unit import test_betse_junction_runtime as reference
from validation.assays import source_order_precision as repair
from validation.betse.emulator import junction_spec
from validation.betse.emulator import spatial as field
from validation.betse.spatial_active import junction_runtime as runtime
from validation.betse.spatial_active.refinement import digest

RULE = repair.protocol()
BACKEND = reference.BACKEND
ROOT = Path(RULE["native_reference_binding"]["root"])
CASES = [(case, level) for case in runtime.protocol()["cases"] for level in range(3)]


def decimal_charge(concentration, valence, extra):
    with localcontext() as context:
        context.prec = 80
        return np.asarray(
            [
                float(
                    sum(
                        Decimal.from_float(float(z)) * Decimal.from_float(float(c))
                        for z, c in zip(valence, values, strict=True)
                    )
                    * Decimal.from_float(F)
                    + Decimal.from_float(float(offset))
                )
                for values, offset in zip(concentration.T, extra, strict=True)
            ]
        )


def test_host_charge_precision_known_answers():
    # Positive concentrations and integer charges; all orderings retain a tiny
    # net charge despite terms that defeat ordinary float64 accumulation.
    concentration = np.array([[2.0**53, 2.0**53], [1.0, 2.0**-30], [2.0**53, 2.0**53]])
    valence = np.array([1.0, 1.0, -1.0])
    extra = np.array([0.0, 0.0])
    expected = decimal_charge(concentration, valence, extra)
    for order in itertools.permutations(range(3)):
        index = np.asarray(order)
        actual = field.charge_density(concentration[index], valence[index], extra, xp=np)
        np.testing.assert_array_equal(actual, expected)
    assert np.max(abs((valence * F) @ concentration - expected)) > 1e-6
    # Real archived initial states exercise all six species and the extracellular
    # shape, not only constructed cancellation examples.
    raw = json.loads((ROOT / "source/configs/betse_spatial_junction.json").read_text())
    state, parameters = reference.definition_arrays(junction_spec.parse(raw).model)
    p, tissue = parameters.active.tissue, state.active.tissue
    counts = 0
    for values, offset in (
        (tissue.cell_concentration, p.extra_cell_charge_density),
        (tissue.outside_concentration, p.extra_outside_charge_density),
    ):
        target = decimal_charge(values, p.valence, offset)
        actual = field.charge_density(values, p.valence, offset, xp=np)
        np.testing.assert_allclose(actual, target, rtol=8 * np.finfo(float).eps, atol=0)
        counts += actual.size
    reference.common.evidence(
        "charge-precision-known-answers",
        dict(
            status="passed",
            independent_decimal_digits=80,
            permutations=6,
            real_fixture_values=counts,
            old_scaled_dot_rejects_known_answer=True,
        ),
    )


def test_compiled_charge_precision():
    jax.config.update("jax_enable_x64", True)
    device = jax.devices(BACKEND)[0]
    values = np.array([[2.0**53, 2.0**53], [1.0, 2.0**-30], [2.0**53, 2.0**53]])
    valence, extra = np.array([1.0, 1.0, -1.0]), np.zeros(2)
    compiled = jax.jit(field.charge_density)
    for order in itertools.permutations(range(3)):
        index = np.asarray(order)
        args = jax.device_put((values[index], valence[index], extra), device)
        result = np.asarray(compiled(*args))
        np.testing.assert_array_equal(result, decimal_charge(values, valence, extra))


@pytest.fixture(scope="module")
def native():
    done = json.loads((ROOT / "completion.json").read_text())
    assert digest(ROOT / "completion.json") == RULE["native_reference_binding"]["completion_sha256"]
    folder = ROOT / "evidence/cpu/junction-runtime-native"
    rows = runtime.authenticate_capture(folder, runtime.native_protocol())
    for case, level in CASES:
        name = f"evidence/cpu/junction-runtime-qualified-{case}-{level}.json"
        assert digest(ROOT / name) == done["evidence_sha256"][name]
        report = json.loads((ROOT / name).read_text())
        assert report["status"] == "passed"
        assert (
            report["native_trace_sha256"] == rows[f"{case}/step-{level}/observed"]["trace_sha256"]
        )
    reference.common.evidence(
        "charge-precision-native-binding",
        dict(
            status="passed",
            root=str(folder),
            pairs=len(CASES),
            completion_sha256=digest(folder / "completion.json"),
            independent_native_update_checks=(
                "Reused authenticated completed checks; native inputs unchanged"
            ),
        ),
    )
    return folder, rows
