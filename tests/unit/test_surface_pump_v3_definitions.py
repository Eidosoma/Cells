"""cells.model.resolved_pump_tissue@3: the explicit-stage guard and the definition errors (a shard of the
former test_surface_pump_v3.py).
"""

import os

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.models import surface_pump_v3
from cells.numerics import surface_imex as imex
from cells.registry.models import get_model
from validation.tissue import surface_pump_v3_fixtures as fixtures

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
CHANNEL_FIELDS = ("channel_gate", "channel_transferred", "channel_dissipated_energy_pJ")
# execution.energy_check's refusals at parse (definitions/energy_check_spec.py): (edit, message).
ENERGY_CHECK_FAULTS = {
    "energy_check_unknown": (
        lambda x: x["energy_check"].update(check="step_doubled_energy@2"),
        "requires check cells.execution.step_doubled_energy@1",
    ),
    "energy_check_no_cap": (
        lambda x: x["energy_check"].pop("integration_error_cap"),
        r"missing=\['integration_error_cap'\]",
    ),
    "energy_check_zero_cap": (
        lambda x: x["energy_check"].update(integration_error_cap=0.0),
        "integration_error_cap must be finite and positive",
    ),
    "energy_check_infinite_cap": (
        lambda x: x["energy_check"].update(integration_error_cap=float("inf")),
        "integration_error_cap must be finite and positive",
    ),
    "energy_check_euler": (
        lambda x: x.update(solver=imex.EULER_ID),
        r"runs only with \S*imex_ars222",
    ),
}
# A number out of its range, and a control that is no schedule, each refused by its own words: (edit
# of the model and the experiment, message). Channel 2 is NaV1.2.
VALUE_FAULTS = {
    "negative_permeability": (
        lambda m, e: m["channels"][2].update(max_permeability_m_per_s=-1e-9),
        "^channel permeability must be finite and nonnegative",
    ),
    "negative_abundance": (
        lambda m, e: m["channels"][2].update(abundance=-1.0),
        "^channel abundance must be finite and nonnegative",
    ),
    "nan_gate": (
        lambda m, e: m["channels"][2].update(initial_gate=[float("nan"), 0.5]),
        "^initial channel gate must be finite and nonnegative",
    ),
    "gate_above_one": (
        lambda m, e: m["channels"][2].update(initial_gate=[1.5, 0.5]),
        r"^initial channel gate must lie in \[0, 1\]",
    ),
    "bool_gate": (
        lambda m, e: m["channels"][2].update(initial_gate=[True, 0.5]),
        "^initial channel gate must be a finite number",
    ),
    "late_start": (
        lambda m, e: e["channel_controls"][2]["schedule"][0].update(time=1e-4),
        "^Controls must start at zero and increase within the horizon",
    ),
    "repeated_time": (
        lambda m, e: e["channel_controls"][2]["schedule"].append(dict(time=0.0, availability=0.5)),
        "^Controls must start at zero and increase within the horizon",
    ),
    "change_beyond_the_end": (
        lambda m, e: e["channel_controls"][2]["schedule"].append(
            dict(time=2 * e["end_time"], availability=0.5)
        ),
        "^Controls must start at zero and increase within the horizon",
    ),
    "availability_above_one": (
        lambda m, e: e["channel_controls"][2]["schedule"][0].update(availability=1.5),
        r"^availability must lie in \[0, 1\]",
    ),
    "duplicate_control": (
        lambda m, e: e["channel_controls"].append(dict(e["channel_controls"][2])),
        "^Each route needs one nonempty control schedule",
    ),
    "zero_area": (
        lambda m, e: m["membranes"][2].update(area_m2=0.0),
        "^route area must be finite and positive",
    ),
    "zero_capacitance": (
        lambda m, e: m["membranes"][2].update(capacitance_F=0.0),
        "^capacitance must be finite and positive",
    ),
    "negative_membrane_permeability": (
        lambda m, e: m["membranes"][2]["permeability_m_per_s"].update(Na=-1e-9),
        "^permeability must be finite and nonnegative",
    ),
}
CHANNEL_OBSERVATIONS = (
    *CHANNEL_FIELDS,
    "channel_flux_fmol_s",
    "channel_targets",
    "channel_tau_s",
    "channel_availability",
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def scaled_difference(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = max(np.max(np.abs(a), initial=0), np.max(np.abs(b), initial=0))
    return 0.0 if scale == 0 else float(np.max(np.abs(a - b)) / scale)


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.fixture(autouse=True)
def clear_compiled_programs():
    """Release the compiled programs after every test: these tests compile many programs
    and one process otherwise keeps them all (the unsplit file hit a 4 GB cap in tier 3)."""
    yield
    jax.clear_caches()


def test_explicit_stage_guard_refuses_open_sodium_channels():
    """A fully open NaV1.2 population is stiff: refused at 1 ms, admitted at 0.2 ms."""
    raw = fixtures.heredity_cells([fixtures.HEREDITY_STATES["D"][:4]], end_time=0.01)
    raw["model"]["channels"][1]["initial_gate"] = [1.0, 1.0]
    spec, state, p, control = initial(raw)
    rate = float(surface_pump_v3.membrane_rate(state, control, p, xp=np))
    assert 2500 < rate < 3000  # F^2/RT P c / (C/A) for 2.5e-7 m/s, 0.05 F/m^2.
    step = jax.jit(surface_pump_v3.checked_step)
    kept, valid = step(state, 1e-3, control, p, p.active)
    assert not valid
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)
    _, valid = step(state, 2e-4, control, p, p.active)
    assert valid
    with pytest.raises(NumericalError):
        run(spec)
    # The pre-screen states are far from it (open Kir2.1 dominates at H, about
    # 28 /s): window currents admit millisecond steps.
    for name in ("H", "D"):
        _, state, p, control = initial(
            fixtures.heredity_cells([fixtures.HEREDITY_STATES[name][:4]], end_time=0.01)
        )
        assert 1e-3 * float(surface_pump_v3.membrane_rate(state, control, p, xp=np)) < 0.05


OLD_IDS = {  # An old spelling in each kind of slot (D345): the slot that names it, and its edit.
    "old_law": (
        r"model\.channels\[2\]\.kinetic_law",
        lambda m, x: m["channels"][2].update(
            kinetic_law="nav1p2_m3h_regularized@1"  # id-moves: keep
        ),
    ),
    "old_operator": (
        r"model\.operators\[0\]\.law",
        lambda m, x: m.update(
            operators=[dict(law="scheduled_species_turnover@1")]  # id-moves: keep
        ),
    ),
    "old_kind": (
        r"model\.channels\[2\]\.availability_factors\[0\]\.kind",
        lambda m, x: m["channels"][2].update(
            availability_factors=[dict(kind="cells.transporter@1")]  # id-moves: keep
        ),
    ),
    "old_solver": (
        r"execution\.solver",
        lambda m, x: x.update(solver="imex_ars222_face_electromigration@1"),  # id-moves: keep
    ),
    "old_heat_choice": (
        r"model\.junction_heat_booking",
        lambda m, x: m.update(junction_heat_booking="trapezoid_nonnegative@1"),  # id-moves: keep
    ),
    "old_execution_choice": (
        r"execution\.energy_check\.check",
        lambda m, x: x.update(energy_check=dict(check="step_doubled_energy@1")),  # id-moves: keep
    ),
}


@pytest.mark.parametrize(
    "fault",
    [
        "retired_law_id",
        "unknown_law",
        "ion",
        "ion_ratio",
        "leak_gates",
        "gate_count",
        "patch",
        "missing_controls",
        "unknown_control",
        "duplicate_id",
        "capacity",
        "missing_channels",
        "hot",
        "sparse_field_rk4",
        "sparse_field_n2",
        *ENERGY_CHECK_FAULTS,
        *VALUE_FAULTS,
        *OLD_IDS,
    ],
)
def test_definition_errors_reject(fault):
    raw = fixtures.definition("clamped", solver=imex.ARS222_ID)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    channel = m["channels"][2]  # NaV1.2 on patch 2.
    if fault in ENERGY_CHECK_FAULTS:  # FR-18's X2 (D224): its block, then its own edit.
        x["energy_check"] = dict(check="cells.execution.step_doubled_energy@1", integration_error_cap=1e-2)
        ENERGY_CHECK_FAULTS[fault][0](x)
    elif fault in VALUE_FAULTS:
        VALUE_FAULTS[fault][0](m, e)
    elif fault == "retired_law_id":  # Renamed to cells.channel.nav1p2_m3h_regularized@1 (stage B).
        channel["kinetic_law"] = "betse_nav1p2_m3h_regularized@1"
    elif fault == "unknown_law":
        channel["kinetic_law"] = "cells.channel.nav1p3_m3h_regularized@1"
    elif fault == "ion":
        channel["permeant_ions"] = [dict(species_id="K", relative_permeability=1.0)]
    elif fault == "ion_ratio":
        channel["permeant_ions"][0]["relative_permeability"] = 0.5
    elif fault == "leak_gates":
        m["channels"][6]["initial_gate"] = [0.5, 0.5]
    elif fault == "gate_count":
        channel["initial_gate"] = [0.5]
    elif fault == "patch":
        channel["membrane_id"] = "membrane_9"
    elif fault == "missing_controls":
        e["channel_controls"].pop()
    elif fault == "unknown_control":
        e["channel_controls"][0]["channel_id"] = "channel_99"
    elif fault == "duplicate_id":
        channel["id"] = "calcium_pump_0"
    elif fault == "capacity":
        x["channel_capacity"] = len(m["channels"]) - 1
    elif fault == "missing_channels":
        del m["channels"]
    elif fault in OLD_IDS:
        OLD_IDS[fault][1](m, x)
    elif fault.startswith("sparse_field_"):  # FR-17 stage 1: the plain IMEX tableaux alone.
        x["field_solver"] = "cells.solver.sparse_capacitive_reduction_gauged_damped_newton@1"
        x["solver"] = "rk4" if fault.endswith("rk4") else imex.IMPLICIT_CONDUCTANCES_ID
    else:
        m["temperature_K"] = 400.5
    message = (ENERGY_CHECK_FAULTS | VALUE_FAULTS).get(fault, (None, None))[1]
    if fault in OLD_IDS:
        message = rf"^{OLD_IDS[fault][0]}: \S+@1 was renamed cells\.\w+\.\w+@1 \(D345\)$"
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)
