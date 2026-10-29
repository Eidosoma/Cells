"""Complete calcium/fuel epoch carry and stage checks, not full trajectories."""

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from tests import owned_calcium_profile_barrier_phase_fixtures as fixtures
from validation.topology import owned_calcium_profile_barrier_phase_handoff_reference as reference

FAMILIES = ("calcium", "energy")
CASES = ("changed", "empty")


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "owned-calcium-profile-barrier-phase-reference"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


@lru_cache
def setup(family, case):
    request = fixtures.request(family, case)
    context, independent = reference.initial(request)
    prepared = fixtures.prepared(family, case)
    schema, model, size = fixtures.OWNERS[family]
    spec = parse_spec(prepared.definition)
    state, layout = model.initial_values(spec)
    return request, context, independent, prepared, spec, state, layout, schema, model, size


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(v[0] for v in table))


def assert_conservation(proof):
    for name in (
        "local_material_fmol",
        "outside_material_fmol",
        "chemical_material_residual_fmol",
        "chemical_ionic_owner_residual_fmol",
        "global_material_residual_fmol",
        "adenylate_fmol",
        "phosphorus_fmol",
        "pool_cycle_residual_fmol",
    ):
        if name in proof:
            np.testing.assert_allclose(proof[name], 0.0, rtol=0, atol=3e-14, err_msg=name)
    assert abs(proof["global_charge_residual_C"]) <= 3e-25
    assert abs(proof["energy_pJ"]) <= 1e-10
    if "pool_internal_transfer_residual_pJ" in proof:
        np.testing.assert_allclose(
            proof["pool_internal_transfer_residual_pJ"], 0.0, rtol=0, atol=1e-10
        )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", CASES)
def test_complete_padded_physical_arrays_and_original_definitions_carry(family, case):
    request, c, vector, prepared, _, state, _, _, _, size = setup(family, case)
    source, checkpoint = fixtures.source_checkpoint(family)
    assert len(state) == len(c["shapes"]) == len(c["padded_shapes"]) == size
    assert reference.target_definition(prepared.definition) == request["simulation"]
    for name in state._fields:
        expected = np.zeros((1,)) if name == "phase_clock_s" else getattr(checkpoint.state, name)
        np.testing.assert_array_equal(c["carried_arrays"][name], expected, err_msg=name)
        np.testing.assert_array_equal(getattr(state, name), expected, err_msg=name)
        assert expected.shape == c["padded_shapes"][name]
        assert expected.dtype == np.dtype("float64")
        np.testing.assert_array_equal(getattr(state, name)[~c["active_masks"][name]], 0.0)
    np.testing.assert_array_equal(reference.flatten(c, state._asdict()), vector)
    assert checkpoint.time == fixtures.DT
    assert float(checkpoint.state.phase_clock_s[0]) == fixtures.DT
    assert np.any(checkpoint.state.chemical_amount_increment != 0.0)
    assert np.any(checkpoint.state.er_passive_transferred != 0.0)
    assert np.any(checkpoint.state.channel_transferred != 0.0)
    if family == "energy":
        assert np.any(checkpoint.state.energy_amount_increment_fmol != 0.0)
    assert (
        len({row["kinetic_law"] for row in request["simulation"]["model"]["ionic"]["channels"]})
        == 56
    )
    evidence(
        "carry-" + family + "-" + case,
        dict(
            request=request,
            source_definition=source.to_dict(),
            complete_fields=size,
            carried_physical_fields=list(state._fields[:-1]),
            padded_shapes=c["padded_shapes"],
            phase_clock_only_reset=True,
            scope="One1ns INIT step carried to SIM; no full trajectory or biological qualification",
        ),
        {"source-" + key: np.asarray(v) for key, v in checkpoint.state._asdict().items()}
        | {"carried-" + key: v for key, v in c["carried_arrays"].items()},
    )


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", CASES)
def test_three_complete_stages_from_carried_state(family, case):
    _, c, vector, _, spec, state, layout, _, model, size = setup(family, case)
    records, arrays = [], {}
    for i, time in enumerate((0.0, fixtures.DT, 2 * fixtures.DT)):
        stage = state._replace(phase_clock_s=np.asarray([time]))
        trial = vector.copy()
        trial[-1] = time
        target, phi, proof = reference.evaluate(c, trial, time)
        u = control(spec, time)
        actual = model.rhs(stage, u, layout, layout.active, xp=np)
        flat = reference.flatten(c, actual._asdict())
        budget = reference.flatten(
            c,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in c["shapes"].items()
            },
        ) + 3e-10 * np.abs(target)
        ratio = float(np.max(np.abs(flat - target) / budget, initial=0.0))
        field = model.field_values(stage, u, layout, xp=np)
        observed_phi = np.r_[
            field.potential_V[: layout.active.size][layout.active],
            field.potential_V[layout.active.size :][layout.outside_active],
        ]
        records.append(dict(time_s=time, error_over_budget=ratio, proof=proof))
        arrays.update(
            {
                str(i) + "-" + key: value
                for key, value in dict(
                    state=trial,
                    actual=flat,
                    independent=target,
                    budget=budget,
                    potential_V=observed_phi,
                    independent_potential_V=phi,
                ).items()
            }
        )
        evidence(
            "stages-" + family + "-" + case, dict(stages=records, complete_fields=size), arrays
        )
        assert ratio <= 1.0
        assert field.converged
        np.testing.assert_allclose(observed_phi, phi, rtol=3e-10, atol=3e-13)
        assert abs(field.energy_balance_pJ_s) <= 1e-10
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
        assert proof["max_charge_residual_C"] <= 3e-25
        assert proof["max_component_current_residual_A"] <= 1e-23
        for name in state._fields:
            np.testing.assert_array_equal(getattr(actual, name)[~c["active_masks"][name]], 0.0)
        np.testing.assert_array_equal(actual.phase_clock_s, [1.0])


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("case", CASES)
def test_original_chemical_charge_fuel_and_work_accounting_survives_handoff(family, case):
    _, c, vector, _, _, _, _, _, _, _ = setup(family, case)
    source = c["source_context"]
    before = reference.conservation(source, reference.flatten(source, c["source_arrays"]))
    after = reference.conservation(c, vector)
    assert_conservation(before)
    assert_conservation(after)
    for key in (
        "original_cell_free_amount_fmol",
        "original_outside_amount_fmol",
        "original_cell_charge_C",
        "original_outside_charge_C",
        "original_chemical_amount_fmol",
        "chemical_fixed_background_C",
        "chemical_amount_fmol",
        "free_cytosol_amount_fmol",
        "er_voltage_V",
        "cell_charge_C",
        "outside_charge_C",
        "chemical_material_residual_fmol",
        "chemical_ionic_owner_residual_fmol",
        "global_material_residual_fmol",
        "original_fuel_amount_fmol",
        "original_fuel_delta_g0_J_mol",
        "fuel_amount_fmol",
        "pool_cycle_residual_fmol",
        "pool_internal_transfer_residual_pJ",
    ):
        if key in after:
            np.testing.assert_array_equal(after[key], before[key], err_msg=key)
    np.testing.assert_allclose(after["energy_pJ"], before["energy_pJ"], rtol=0, atol=3e-13)
    changed = {k: v.copy() for k, v in reference.unpack(c, vector).items()}
    changed["reaction_extent"][0, 0] += 1e-5
    broken = reference.conservation(c, reference.flatten(c, changed))
    assert np.max(np.abs(broken["chemical_material_residual_fmol"])) >= 0.99e-5
    changed = {k: v.copy() for k, v in reference.unpack(c, vector).items()}
    changed["metabolic_work_pJ"][0] += 1e-5
    work = reference.conservation(c, reference.flatten(c, changed))
    if family == "energy":
        # Existing pump-work ledgers are internal transfers in the finite pool.
        assert work["energy_pJ"] == after["energy_pJ"]
        np.testing.assert_allclose(
            np.sum(
                work["pool_internal_transfer_residual_pJ"]
                - after["pool_internal_transfer_residual_pJ"]
            ),
            1e-5,
            rtol=0,
            atol=1e-15,
        )
    else:
        np.testing.assert_allclose(
            work["energy_pJ"] - after["energy_pJ"], -1e-5, rtol=0, atol=1e-15
        )
    evidence(
        "conservation-" + family + "-" + case,
        dict(before=before, after=after, corrupted_chemical_history=broken),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_every_real_absent_owner_mask_rejects_hidden_history(family):
    request, c, _, _, _, _, _, _, _, _ = setup(family, "changed")
    checked = {}
    for name, mask in c["active_masks"].items():
        absent = np.argwhere(~mask)
        if not absent.size:
            continue
        index = tuple(int(i) for i in absent[0])
        assert not mask[index]
        corrupted = fixtures.request(family)
        row = corrupted["source"]["checkpoint"]["state"][name]
        array = np.asarray(row["values"], dtype=float)
        array[index] = 1e-25
        row["values"] = array.tolist()
        with pytest.raises(ValueError, match="absent physical owner"):
            reference.decode_state(
                corrupted["source"]["checkpoint"]["state"], c["padded_shapes"], c["active_masks"]
            )
        checked[name] = list(index)
    assert "extracellular_amount_increment" in checked and "channel_gate" in checked
    assert (
        request["source"]["checkpoint"]["state"]
        == fixtures.request(family)["source"]["checkpoint"]["state"]
    )
    evidence("absent-owners-" + family, dict(checked_absent_indices=checked))


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("fault", ["missing", "nonfinite", "dtype", "shape", "bool", "clock"])
def test_incomplete_or_malformed_chemical_fuel_history_is_rejected(family, fault):
    request = fixtures.request(family)
    state = request["source"]["checkpoint"]["state"]
    key = "chemical_amount_increment" if family == "calcium" else "energy_amount_increment_fmol"
    row = state[key]
    if fault == "missing":
        del state[key]
    elif fault == "nonfinite":
        value = np.asarray(row["values"], dtype=float)
        value.flat[0] = float("nan")
        row["values"] = value.tolist()
    elif fault == "dtype":
        row["dtype"] = "<f4"
    elif fault == "shape":
        row["shape"][-1] += 1
    elif fault == "bool":
        values = row["values"]
        while isinstance(values[0], list):
            values = values[0]
        values[0] = False
    elif fault == "clock":
        state["phase_clock_s"]["values"] = [0.0]
    with pytest.raises(ValueError):
        reference.initial(request)
    evidence("refusal-" + family + "-" + fault, dict(fault=fault, rejected=True))


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("fault", ["store-anchor", "charge-anchor", "capacity"])
def test_original_store_charge_and_owner_anchors_cannot_change(family, fault):
    request = fixtures.request(family)
    target = request["simulation"]
    if fault == "store-anchor":
        target["model"]["stores"][0]["model"]["membrane"]["initial_voltage_V"] += 1e-6
    elif fault == "charge-anchor":
        target["model"]["ionic"]["cells"][0]["initial_charge_C"] += 1e-20
    elif fault == "capacity":
        target["execution"]["chemical_capacity"] += 1
    with pytest.raises(ValueError):
        reference.initial(request)
    evidence("refusal-" + family + "-" + fault, dict(fault=fault, rejected=True))


def test_complete_independent_dependency_closure_includes_legacy_equation_helpers():
    root = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
    manifest = reference.dependency_manifest(root)
    assert {
        "validation/transport/owned_calcium_profile_barrier_reference.py",
        "validation/tissue/surface_calcium_reference.py",
        "validation/tissue/surface_calcium_energy_reference.py",
        "validation/chemistry/finite_energy_reference.py",
        "validation/betse/contact.py",
        "tests/reference_er_calcium.py",
        "tests/reference_gated_calcium.py",
        "tests/reference_ip3_calcium.py",
        "tests/reference_plasma_calcium.py",
        "tests/reference_spatial_calcium.py",
    } <= set(manifest)
    assert all(
        path.startswith("validation/")
        or (Path(path).parent == Path("tests") and Path(path).name.startswith("reference_"))
        for path in manifest
    )
    evidence("dependency-closure", dict(sources=manifest, production_imports=False))
