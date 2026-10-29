"""Independent complete carry and six stages; no trajectory qualification."""

import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.models import surface_active_profile_barrier_epoch as model
from tests import active_profile_barrier_phase_fixtures as fixtures
from validation.topology import active_profile_barrier_phase_handoff_reference as reference


def evidence(name, report, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "active-profile-barrier-phase-reference"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(
            json.dumps(
                report,
                indent=2,
                allow_nan=False,
                default=lambda v: np.asarray(v).tolist(),
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@lru_cache
def setup(case):
    request = fixtures.request(case)
    context, independent = reference.initial(request)
    prepared = fixtures.prepared(case)
    spec = parse_spec(prepared.definition)
    state, layout = model.initial_values(spec)
    return request, context, independent, prepared, spec, state, layout


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def assert_conservation(proof):
    for key in ("local_material_fmol", "outside_material_fmol", "global_material_residual_fmol"):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0.0, atol=3e-14, err_msg=key)
    for key in (
        "capacitor_charge_residual_C",
        "electrode_charge_residual_C",
        "global_charge_residual_C",
    ):
        np.testing.assert_allclose(proof[key], 0.0, rtol=0.0, atol=3e-25, err_msg=key)
    assert abs(proof["energy_pJ"]) <= 1e-10


@pytest.mark.parametrize("case", ["changed", "empty"])
def test_original_complete_checkpoint_carries_every_physical_array(case):
    request, c, independent, prepared, _, state, _ = setup(case)
    before = deepcopy(request)
    source, checkpoint = fixtures.source_checkpoint()
    assert len(c["shapes"]) == len(c["padded_shapes"]) == len(state) == 20
    assert len({p["kinetic_law"] for p in request["simulation"]["model"]["channels"]}) == 56
    assert reference.target_definition(prepared.definition) == request["simulation"]
    carried = c["carried_arrays"]
    for name in state._fields:
        expected = np.zeros((1,)) if name == "phase_clock_s" else getattr(checkpoint.state, name)
        np.testing.assert_array_equal(carried[name], expected, err_msg=name)
        np.testing.assert_array_equal(getattr(state, name), expected, err_msg=name)
        assert carried[name].dtype == np.dtype("float64")
        assert carried[name].shape == c["padded_shapes"][name]
    assert float(checkpoint.state.phase_clock_s[0]) == fixtures.DT
    assert np.any(checkpoint.state.face_transferred != 0.0)
    assert np.any(checkpoint.state.channel_transferred != 0.0)
    assert np.any(checkpoint.state.metabolic_work_pJ != 0.0)
    np.testing.assert_array_equal(reference.flatten(c, state._asdict()), independent)
    detached = independent.copy()
    detached[0] += 1.0
    assert request == before
    evidence(
        "carry-" + case,
        dict(
            request=request,
            source_time_s=checkpoint.time,
            retained_physical_fields=list(state._fields[:-1]),
            padded_shapes=c["padded_shapes"],
            source_accounting_origin=source.to_dict()["model"],
            scope="Exact complete state carry from one 1-ns INIT step; no full trajectory claim",
        ),
        {"carried-" + k: v for k, v in carried.items()}
        | {"source-" + k: np.asarray(v) for k, v in checkpoint.state._asdict().items()},
    )


@pytest.mark.parametrize("case", ["changed", "empty"])
def test_complete_three_phase_local_stages_against_independent_equations(case):
    _, c, independent, _, spec, state, layout = setup(case)
    reports, arrays = [], {}
    for i, time in enumerate((0.0, fixtures.DT, 2 * fixtures.DT)):
        stage = state._replace(phase_clock_s=np.asarray([time]))
        vector = independent.copy()
        vector[-1] = time
        target, phi, proof = reference.evaluate(c, vector, time)
        actual = model.rhs(stage, control(spec, time), layout, layout.active, xp=np)
        flat = reference.flatten(c, actual._asdict())
        budget = reference.flatten(
            c,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in c["shapes"].items()
            },
        ) + 3e-10 * np.abs(target)
        ratio = float(np.max(np.abs(flat - target) / budget, initial=0.0))
        field = model.field_values(stage, control(spec, time), layout, xp=np)
        observed = np.r_[
            field.potential_V[: layout.active.size][layout.active],
            field.potential_V[layout.active.size :][layout.outside_active],
        ]
        reports.append(dict(time_s=time, error_over_budget=ratio, proof=proof))
        arrays.update(
            {
                str(i) + "-" + key: value
                for key, value in dict(
                    state=vector,
                    derivative=flat,
                    independent_derivative=target,
                    budget=budget,
                    potential_V=observed,
                    independent_potential_V=phi,
                ).items()
            }
        )
        evidence("stages-" + case, dict(stages=reports, complete_fields=20), arrays)
        assert ratio <= 1.0
        np.testing.assert_allclose(observed, phi, rtol=3e-10, atol=3e-13)
        assert field.converged
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
        assert abs(field.energy_balance_pJ_s) <= 1e-10
        assert proof["max_charge_residual_C"] <= 3e-25
        assert proof["max_component_current_residual_A"] <= 1e-23
        np.testing.assert_array_equal(actual.phase_clock_s, [1.0])
        for name, shape in c["shapes"].items():
            np.testing.assert_array_equal(getattr(actual, name)[..., shape[-1] :], 0.0)


@pytest.mark.parametrize("case", ["changed", "empty"])
def test_history_conservation_stays_anchored_to_original_INIT(case):
    _, c, independent, _, _, _, _ = setup(case)
    source = c["source_context"]
    original = reference.flatten(source, c["source_arrays"])
    before = reference.conservation(source, original)
    after = reference.conservation(c, independent)
    assert_conservation(before)
    assert_conservation(after)
    for name in (
        "original_cell_amount_fmol",
        "original_outside_amount_fmol",
        "original_cell_charge_C",
        "original_outside_charge_C",
        "cell_amount_fmol",
        "outside_amount_fmol",
        "cell_charge_C",
        "outside_charge_C",
        "global_material_residual_fmol",
        "capacitor_charge_residual_C",
        "electrode_charge_residual_C",
    ):
        np.testing.assert_array_equal(after[name], before[name], err_msg=name)
    np.testing.assert_allclose(after["energy_pJ"], before["energy_pJ"], rtol=0, atol=3e-13)
    changed = {k: v.copy() for k, v in reference.unpack(c, independent).items()}
    changed["membrane_transferred"][0, 0] += 1e-5
    broken = reference.conservation(c, reference.flatten(c, changed))
    assert broken["local_material_fmol"] >= 0.99e-5
    changed = {k: v.copy() for k, v in reference.unpack(c, independent).items()}
    changed["metabolic_work_pJ"][0] += 1e-5
    broken_energy = reference.conservation(c, reference.flatten(c, changed))
    np.testing.assert_allclose(broken_energy["energy_pJ"] - after["energy_pJ"], -1e-5, atol=1e-15)
    evidence("conservation-" + case, dict(before=before, after=after, corrupted=broken))


MALFORMED = (
    "missing-field",
    "extra-field",
    "missing-property",
    "wrong-dtype",
    "float-shape",
    "wrong-shape",
    "wrong-values-rank",
    "string-value",
    "bool-value",
    "nonfinite-physical",
    "nonfinite-padding",
    "nonzero-padding",
    "ragged-values",
)


@pytest.mark.parametrize("fault", MALFORMED)
def test_malformed_complete_checkpoint_is_rejected_before_compaction(fault):
    request = fixtures.request()
    state = request["source"]["checkpoint"]["state"]
    row = state["amount_increment"]
    if fault in ("nonfinite-padding", "nonzero-padding"):
        row = state["extracellular_amount_increment"]
        absent = len(request["source"]["definition"]["model"]["extracellular"])
        assert absent < row["shape"][-1]
    if fault == "missing-field":
        del state["face_transferred"]
    elif fault == "extra-field":
        state["unowned_history"] = deepcopy(row)
    elif fault == "missing-property":
        del row["dtype"]
    elif fault == "wrong-dtype":
        row["dtype"] = "<f4"
    elif fault == "float-shape":
        row["shape"][0] = float(row["shape"][0])
    elif fault == "wrong-shape":
        row["shape"][-1] += 1
    elif fault == "wrong-values-rank":
        row["values"] = np.asarray(row["values"]).ravel().tolist()
    elif fault == "string-value":
        row["values"][0][0] = "0.0"
    elif fault == "bool-value":
        row["values"][0][0] = False
    elif fault == "nonfinite-physical":
        row["values"][0][0] = float("nan")
    elif fault == "nonfinite-padding":
        row["values"][0][absent] = float("inf")
    elif fault == "nonzero-padding":
        row["values"][0][absent] = 1e-25
    elif fault == "ragged-values":
        row["values"][0].pop()
    with pytest.raises(ValueError):
        reference.initial(request)
    evidence("refusal-" + fault, dict(fault=fault, rejected=True))


@pytest.mark.parametrize("fault", ["clock", "capacity", "physical-anchor", "source-phase"])
def test_original_clock_owner_and_accounting_origin_cannot_be_rewritten(fault):
    request = fixtures.request()
    if fault == "clock":
        request["source"]["checkpoint"]["state"]["phase_clock_s"]["values"] = [0.0]
    elif fault == "capacity":
        request["simulation"]["execution"]["capacity"] += 1
    elif fault == "physical-anchor":
        request["simulation"]["model"]["cells"][0]["initial_charge_C"] += 1e-20
    elif fault == "source-phase":
        request["source"]["definition"]["model"]["phase"] = "SIM"
    with pytest.raises(ValueError):
        reference.initial(request)
    evidence("refusal-" + fault, dict(fault=fault, rejected=True))


def test_oracle_dependency_closure_contains_only_independent_reference_code():
    root = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
    manifest = reference.dependency_manifest(root)
    assert "validation/betse/contact.py" in manifest
    assert "validation/tissue/surface_kinetic_reference.py" in manifest
    assert "validation/transport/environment_barrier_preparation_reference.py" in manifest
    assert {
        "tests/reference_er_calcium.py",
        "tests/reference_gated_calcium.py",
        "tests/reference_ip3_calcium.py",
        "tests/reference_plasma_calcium.py",
        "tests/reference_spatial_calcium.py",
    } <= set(manifest)
    assert all(
        name.startswith("validation/")
        or (Path(name).parent == Path("tests") and Path(name).name.startswith("reference_"))
        for name in manifest
    )
    evidence("dependency-closure", dict(sources=manifest, production_imports=False))
