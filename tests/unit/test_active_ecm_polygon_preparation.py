"""Complete actual active ECM admission, independent initial flows and fields."""

import importlib
import json
import math
import os
import struct
import traceback
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import active_ecm_polygon_preparation as active
from cells.core.schedule import control_values
from cells.processes import finite_ecm_polygon_geometry as geometry
from validation.geometry import active_ecm_polygon_fixtures as fixtures
from validation.geometry import active_ecm_polygon_reference as reference
from validation.geometry import active_ecm_polygon_runtime as runtime
from validation.geometry import finite_ecm_polygon_fixtures as ecm_fixtures


def plain(value):
    if hasattr(value, "_asdict"):
        return {key: plain(item) for key, item in value._asdict().items()}
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if isinstance(value, np.ndarray) or isinstance(value, np.generic):
        return plain(value.tolist())
    if type(value) is float and not math.isfinite(value):
        return dict(binary64_bits_hex=struct.pack(">d", value).hex(), nonfinite=value.hex())
    return value


def save(name, value):
    folder = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "active-ecm-polygon"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name + ".json")
    arrays = {}

    def collect(item, trail="root"):
        if isinstance(item, (np.ndarray, np.generic)):
            arrays[trail] = np.asarray(item)
        elif hasattr(item, "_asdict"):
            collect(item._asdict(), trail)
        elif isinstance(item, dict):
            for key, child in item.items():
                collect(child, trail + "/" + str(key))
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                collect(child, trail + "/" + str(index))

    collect(value)
    if arrays:
        with path.with_suffix(".npz").open("xb") as handle:
            np.savez_compressed(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
    with path.open("x") as handle:
        json.dump(plain(value), handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def failure(name, error):
    save(
        name + "-failure",
        dict(
            type=type(error).__name__,
            reason=str(error),
            stage=getattr(error, "stage", None),
            trial=getattr(error, "trial", None),
            traceback=traceback.format_exc(),
        ),
    )


def prepared(name, case):
    declaration = ecm_fixtures.fixture(fixtures.geometry_case(case))
    save(name + "-geometry-input", declaration)
    try:
        request = geometry.from_partition(declaration, law_id=geometry.LAW_ID)
        save(name + "-geometry-request", geometry.request_record(request))
        binding = geometry.prepare(request)
        save(name + "-geometry-actual", dict(identity=binding.identity, geometry=binding.geometry))
        raw = fixtures.request(case, declaration, binding)
        save(name + "-active-input", raw)
        value = active.prepare(request, binding, raw)
    except Exception as error:
        failure(name + "-prepare", error)
        raise
    packet = dict(
        case=case,
        geometry_declaration=declaration,
        geometry_request=geometry.request_record(request),
        geometry=binding.geometry,
        geometry_identity=binding.identity,
        request=raw,
        definition=value.definition,
        provenance=value.provenance,
        identity=value.identity,
    )
    save(name + "-prepared", packet)
    return request, binding, raw, value, packet


def field_packet(name, packet):
    target = packet["definition"]["model"]["id"]
    parser = importlib.import_module("cells.core." + active.FAMILIES[target][0])
    model = importlib.import_module("cells.models." + active.FAMILIES[target][1])
    try:
        spec = parser.parse(packet["definition"])
        state, p = model.initial_values(spec)
        packet = packet | dict(state=state._asdict(), layout=p._asdict(), initial_control_probes=[])
        save(name + "-initial-state", packet)
        for index, time in enumerate((0.0, 5e-7)):
            table = control_values(spec, [time])
            control = type(table)(*(v[0] for v in table))
            actual = model.readouts(state, control, p, xp=np)
            save(
                name + "-initial-readout-return-" + str(index),
                dict(control=control, readout=actual),
            )
            trial = dict(
                time_s=time,
                control=control,
                derivative=actual.derivative,
                field=actual.field,
                valid=bool(actual.valid),
            )
            save(name + "-initial-actual-" + str(index), trial)
            packet["initial_control_probes"].append(plain(trial))
    except Exception as error:
        failure(name + "-initial-field", error)
        raise
    save(name + "-packet", packet)
    return plain(packet)


@pytest.mark.parametrize("case", fixtures.CASES)
def test_actual_family_conversion_and_complete_initial_field(case):
    name = "positive-" + case
    _, _, _, value, packet = prepared(name, case)
    packet = field_packet(name, packet)
    try:
        targets = []
        for refinement in (1, 2):
            target = reference.materialize(
                packet["geometry_declaration"],
                packet["geometry"],
                packet["request"],
                refinement=refinement,
            )
            save(name + "-conversion-targets-" + str(refinement), target)
            targets.append(target)
        comparison = reference.compare_conversion(packet, *targets)
        save(name + "-conversion-comparison", comparison)
        report = reference.compare_initial_field(
            packet, retain=lambda label, record: save(name + "-" + label, record)
        )
        save(name + "-field-comparison", report)
        reference.assert_initial_field(report)
    except Exception as error:
        failure(name + "-reference", error)
        raise
    assert value.provenance["physical_model_prepared"]
    for key in (
        "inventories_rescaled",
        "physiology_defaults_inserted",
        "target_identity_relabelled",
        "solver_trajectory_executed",
        "native_equivalence",
        "geometry_or_family_qualification_inherited",
    ):
        assert value.provenance[key] is False
    first = packet["initial_control_probes"][0]["derivative"]
    if case.endswith("disabled"):
        for key in (
            "pump_cycles",
            "channel_transferred",
            "plasma_pump_cycles",
            "plasma_exchange_cycles",
            "calcium_channel_transferred",
            "er_pump_transferred",
            "regeneration_cycles_fmol",
        ):
            if key in first:
                assert not np.any(first[key])
    else:
        assert np.any(np.asarray(first["pump_cycles"]) != 0)
        assert np.any(np.asarray(first["channel_transferred"]) != 0)
    assert all(not flag for flag in value.provenance["actual_reservoir_flags"].values())


@pytest.mark.parametrize("case", fixtures.DOMAIN_CASES)
def test_unsupported_topology_family_and_complete_owner_refusals(case):
    name = "domain-" + case
    declaration = ecm_fixtures.fixture("two-cell-grid")
    save(name + "-geometry-input", declaration)
    try:
        request = geometry.from_partition(declaration, law_id=geometry.LAW_ID)
        binding = geometry.prepare(request)
        save(
            name + "-geometry-actual",
            dict(
                request=geometry.request_record(request),
                geometry=binding.geometry,
                identity=binding.identity,
            ),
        )
        raw = fixtures.invalid(case, declaration, binding)
        save(name + "-active-input", raw)
    except Exception as error:
        failure(name + "-prelude", error)
        raise
    with pytest.raises(active.ActivePreparationRejected) as caught:
        active.prepare(request, binding, raw)
    save(name + "-refusal", caught.value.trial)
    assert not caught.value.trial["physical_model_prepared"]
    if case in (
        "open-nonnull-ceiling",
        "wrong-free-ion-inventory",
        "missing-control",
        "duplicate-control-clock",
        "bad-charge-anchor",
    ):
        assert caught.value.trial["stage"] == "existing_complete_physical_admission"
        assert caught.value.trial["failure_type"] == "ConfigError"


@pytest.mark.parametrize("case", fixtures.CORRUPTION_CASES)
def test_independent_conversion_refuses_changed_geometry_or_physiology(case):
    name = "corruption-" + case
    _, _, _, _, packet = prepared(name, "fuel-calcium-two-cell")
    changed = deepcopy(packet)
    outer = changed["definition"]["model"]
    ion = outer["ionic"]
    if case == "bath-volume":
        ion["extracellular"][0]["volume_pL"] *= 2
    elif case == "face-length":
        ion["faces"][0]["length_m"] *= 2
    elif case == "face-owner":
        row = ion["faces"][0]
        row["sender"], row["receiver"] = row["receiver"], row["sender"]
    elif case == "channel-path":
        ion["channels"][0]["max_permeability_m_per_s"] *= 2
    elif case == "cytosol-ER-partition":
        outer["stores"][0]["model"]["compartments"][1]["volume_pL"] *= 2
    elif case == "fuel-owner":
        outer["energy_pools"][0]["cell_id"] = ion["cells"][1]["id"]
    elif case == "reservoir-flag":
        ion["extracellular"][0]["reservoir"] = True
    elif case == "control-clock":
        changed["definition"]["experiment"]["channel_controls"][0]["schedule"][1]["time"] *= 0.9
    else:
        raise ValueError(case)
    save(name + "-packet", changed)
    targets = []
    for refinement in (1, 2):
        value = reference.materialize(
            changed["geometry_declaration"],
            changed["geometry"],
            changed["request"],
            refinement=refinement,
        )
        save(name + "-conversion-targets-" + str(refinement), value)
        targets.append(value)
    with pytest.raises(AssertionError):
        reference.compare_conversion(changed, *targets)
    save(name + "-comparison", dict(expected_corruption_refused=True))


@pytest.mark.parametrize("case", fixtures.FIELD_CORRUPTION_CASES)
def test_independent_complete_field_refuses_corruption_with_unchanged_RHS(case):
    name = "field-corruption-" + case
    _, _, _, _, packet = prepared(name, "fuel-calcium-full")
    packet = field_packet(name, packet)
    changed = deepcopy(packet)
    field = changed["initial_control_probes"][0]["field"]
    if case == "face-flux":
        field["rates"]["face_flux_fmol_s"][0][0] += 0.001
    elif case == "aggregate-membrane-flux":
        field["rates"]["membrane_flux_fmol_s"][0][0] += 0.001
    elif case == "cell-source":
        field["rates"]["cell_rate_fmol_s"][0][0] += 0.001
    elif case == "membrane-heat":
        field["rates"]["membrane_dissipation_pJ_s"][0] += 0.001
    elif case == "capacitor-charge":
        field["membrane_charge_C"][0] += 1e-16
    elif case == "chemical-power":
        field["chemical_energy_rate_pJ_s"] += 0.001
    else:
        raise ValueError(case)
    save(name + "-changed-packet", changed)
    report = reference.compare_initial_field(
        changed, retain=lambda label, record: save(name + "-changed-" + label, record)
    )
    save(name + "-changed-comparison", report)
    with pytest.raises(AssertionError):
        reference.assert_initial_field(report)
    save(
        name + "-comparison",
        dict(expected_corruption_refused=True, derivative_and_initial_state_unchanged=True),
    )


@pytest.mark.parametrize("case", fixtures.OWNERSHIP_CASES)
def test_immutable_geometry_physiology_and_source_owners(case):
    name = "ownership-" + case
    request, binding, raw, value, _ = prepared(name, "fuel-calcium-full")
    definition, provenance = value.definition, value.provenance
    if case == "definition-bath-volume":
        definition["model"]["ionic"]["extracellular"][0]["volume_pL"] *= 2
    elif case == "definition-fuel":
        definition["model"]["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 2
    elif case == "definition-channel":
        definition["model"]["ionic"]["channels"][0]["abundance"] *= 2
    elif case == "provenance-face-owner":
        provenance["owner_projection"]["faces"].reverse()
    elif case == "returned-copy-alias":
        definition["model"]["ionic"]["cells"][0]["id"] = "changed"
        assert value.definition["model"]["ionic"]["cells"][0]["id"] != "changed"
        active.validate(request, binding, raw, value)
        save(name + "-comparison", dict(returned_copies_owned=True))
        return
    else:
        raise ValueError(case)
    forged = replace(
        value,
        definition_json=geometry.exact._json(definition),
        provenance_json=geometry.exact._json(provenance),
        identity=geometry.exact._digest(dict(definition=definition, provenance=provenance)),
    )
    save(
        name + "-forgery",
        dict(definition=definition, provenance=provenance, identity=forged.identity),
    )
    with pytest.raises(ValueError):
        active.validate(request, binding, raw, forged)
    save(name + "-comparison", dict(resealed_change_refused=True))


# Software contracts for the prospective repair; these add no physical cases.
ENERGY_CASES = [
    ("resolved_tissue@2", 1e-10, 1e-10),
    ("resolved_tissue@12", 1e-10, 1e-10),
    ("resolved_energy@1", 2e-8, 2e-8),
    ("resolved_energy@2", 2e-8, 2e-10),
    ("resolved_calcium@1", 1e-10, 1e-10),
    ("resolved_calcium@11", 1e-10, 1e-10),
    ("resolved_calcium_energy@1", 2e-10, 3e-10),
    ("resolved_calcium_energy@5", 1e-10, 3e-10),
    ("resolved_open_calcium@1", 1e-10, 1e-10),
    ("resolved_open_calcium_energy@1", 1e-10, 1e-10),
]


@pytest.mark.parametrize(
    "model_id,actual_limit,independent_limit", ENERGY_CASES, ids=[row[0] for row in ENERGY_CASES]
)
def test_family_energy_limits_reject_boundary_and_agreeing_defects(
    model_id, actual_limit, independent_limit
):
    assert reference.ENERGY_LIMITS[model_id] == (actual_limit, independent_limit)
    observed = []
    for sign in (-1, 1):
        for scale in (0.0, 0.5, 1.0):
            record = reference.energy_evidence(
                model_id, sign * scale * actual_limit, sign * scale * independent_limit
            )
            reference.assert_energy(model_id, record)
            observed.append(dict(record=record, admitted=True))
        for column, limit in (("actual", actual_limit), ("independent", independent_limit)):
            record = reference.energy_evidence(model_id, 0.0, 0.0)
            record[column + "_energy_balance_pJ_s"] = sign * math.nextafter(limit, math.inf)
            with pytest.raises(AssertionError):
                reference.assert_energy(model_id, record)
            observed.append(dict(record=record, admitted=False))
        equal = sign * math.nextafter(max(actual_limit, independent_limit), math.inf)
        record = reference.energy_evidence(model_id, equal, equal)
        assert record["actual_energy_balance_pJ_s"] == record["independent_energy_balance_pJ_s"]
        with pytest.raises(AssertionError):
            reference.assert_energy(model_id, record)
        observed.append(dict(record=record, admitted=False))
    save("energy-boundaries-" + model_id, dict(records=observed, software_contract_only=True))


@pytest.mark.parametrize("column", ["actual", "independent"])
@pytest.mark.parametrize(
    "invalid", [float("nan"), float("inf"), -float("inf")], ids=["nan", "inf", "negative-inf"]
)
def test_energy_gate_refuses_nonfinite_residuals(column, invalid):
    record = reference.energy_evidence("resolved_calcium@1", 0.0, 0.0)
    record[column + "_energy_balance_pJ_s"] = invalid
    save("nonfinite-energy-" + column + "-" + invalid.hex(), record)
    with pytest.raises(AssertionError):
        reference.assert_energy("resolved_calcium@1", record)


def test_energy_evidence_cannot_omit_or_widen_required_limits():
    model_id = "resolved_energy@2"
    record = reference.energy_evidence(model_id, 1e-9, 1e-10)
    reference.assert_energy(model_id, record)
    for key in ("actual_absolute_budget_pJ_s", "independent_absolute_budget_pJ_s"):
        changed = deepcopy(record)
        changed[key] *= 2
        with pytest.raises(AssertionError):
            reference.assert_energy(model_id, changed)
    for key in ("actual_energy_balance_pJ_s", "independent_energy_balance_pJ_s"):
        changed = deepcopy(record)
        del changed[key]
        with pytest.raises(KeyError):
            reference.assert_energy(model_id, changed)
    changed = deepcopy(record)
    changed["independent_identity_available"] = False
    with pytest.raises(AssertionError):
        reference.assert_energy(model_id, changed)
    save("required-energy-evidence", dict(software_contract_only=True, passed=True))


@pytest.mark.parametrize("column", ["actual", "independent"])
def test_full_field_acceptance_requires_both_absolute_energy_gates(column):
    model_id = "resolved_tissue@12"
    stage = dict(
        production_stage_valid=True,
        transport_valid=True,
        derivative_error_over_budget=0.0,
        intended_cell_potential_error_over_budget=0.0,
        physical_field_comparisons=[dict(error_over_budget=0.0)],
        accounting=dict(
            independent_energy_balance_pJ_s=0.0,
            source_owner_balance_error_over_budget=0.0,
            capacitive_components=2,
        ),
        independent_face_flux_fmol_s=[[1.0]],
        energy=reference.energy_evidence(model_id, 0.0, 0.0),
    )
    report = dict(model_id=model_id, stages=[stage])
    reference.assert_initial_field(report)
    stage["energy"][column + "_energy_balance_pJ_s"] = 2e-10
    if column == "independent":
        stage["accounting"]["independent_energy_balance_pJ_s"] = 2e-10
    save("full-energy-gate-" + column, report)
    with pytest.raises(AssertionError):
        reference.assert_initial_field(report)


def semantic_declaration():
    return dict(
        model=dict(
            ionic=dict(
                species=[dict(id="Na"), dict(id="Ca")],
                channels=[dict(id="gate", initial_gate=[0.2, 0.7], permeant_ids=["Na", "Ca"])],
            ),
            stores=[
                dict(
                    cell_id="owner",
                    model=dict(
                        moieties=["Ca", "B"],
                        species=[
                            dict(id="Ca", moieties=dict(Ca=1)),
                            dict(id="B", moieties=dict(B=1)),
                        ],
                        compartments=[
                            dict(id="er", initial_amount_fmol=dict(Ca=0.2)),
                            dict(id="cytosol", initial_amount_fmol=dict(Ca=0.1)),
                        ],
                        reactions=[dict(id="r2", rate=0.2), dict(id="r1", rate=0.1)],
                    ),
                )
            ],
        ),
        experiment=dict(
            membrane_controls=[dict(membrane_id="patch", schedule=[dict(time=0.0), dict(time=0.5)])]
        ),
        provenance=dict(moieties=["Ca", "B"]),
    )


@pytest.mark.parametrize("lane", ["admission", "independent"])
def test_named_chemical_tables_preserve_associations_and_original_input(lane):
    normalize = active._semantic if lane == "admission" else reference.semantic
    raw = semantic_declaration()
    changed = deepcopy(raw)
    for key in ("moieties", "species", "compartments", "reactions"):
        changed["model"]["stores"][0]["model"][key].reverse()
    saved = deepcopy(raw)
    assert normalize(raw) == normalize(changed)
    assert raw == saved
    save(
        "semantic-named-" + lane, dict(original=raw, reordered=changed, software_contract_only=True)
    )


@pytest.mark.parametrize("lane", ["admission", "independent"])
def test_semantic_normalization_preserves_ordered_axes_and_changed_chemistry(lane):
    normalize = active._semantic if lane == "admission" else reference.semantic
    raw = semantic_declaration()
    ordered = [
        ("model", "ionic", "species"),
        ("model", "ionic", "channels", 0, "initial_gate"),
        ("model", "ionic", "channels", 0, "permeant_ids"),
        ("experiment", "membrane_controls", 0, "schedule"),
        ("provenance", "moieties"),
    ]
    for path in ordered:
        changed = deepcopy(raw)
        value = changed
        for key in path:
            value = value[key]
        value.reverse()
        assert normalize(raw) != normalize(changed)
    for change in ("inventory", "stoichiometry", "rate", "owner"):
        changed = deepcopy(raw)
        chemical = changed["model"]["stores"][0]["model"]
        if change == "inventory":
            chemical["compartments"][0]["initial_amount_fmol"]["Ca"] += 0.01
        elif change == "stoichiometry":
            chemical["species"][0]["moieties"]["Ca"] = 2
        elif change == "rate":
            chemical["reactions"][0]["rate"] += 0.01
        else:
            chemical["compartments"][0]["id"] = "other"
        assert normalize(raw) != normalize(changed)
    save("semantic-distinct-" + lane, dict(software_contract_only=True, passed=True))


@pytest.mark.parametrize("lane", ["admission", "independent"])
def test_duplicate_chemical_names_are_refused(lane):
    normalize = active._semantic if lane == "admission" else reference.semantic
    for key in ("moieties", "species", "compartments", "reactions"):
        raw = semantic_declaration()
        rows = raw["model"]["stores"][0]["model"][key]
        rows.append(deepcopy(rows[0]))
        with pytest.raises((AssertionError, ValueError)):
            normalize(raw)
    save("semantic-duplicates-" + lane, dict(software_contract_only=True, passed=True))


def test_raw_first_writer_preserves_numeric_failure_and_successful_json():
    folder = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "active-ecm-polygon/raw-write-contract"
    folder.mkdir(parents=True, exist_ok=False)
    finite = dict(values=[0.0, 1.25], valid=True)
    path = folder / "finite.json"
    runtime.write(path, finite)
    assert json.loads(path.read_text()) == finite
    assert not path.with_suffix(".raw.json").exists()
    for name, invalid in (
        ("nan", float("nan")),
        ("inf", float("inf")),
        ("negative-inf", -float("inf")),
    ):
        path = folder / (name + ".json")
        array = np.asarray([1.0, invalid], dtype=np.float64)
        with pytest.raises(ValueError):
            runtime.write(path, dict(values=array, scalar=invalid))
        raw = json.loads(path.with_suffix(".raw.json").read_text())
        assert raw["typed_arrays"] == path.with_suffix(".npz").name
        assert raw["value"]["scalar"]["binary64_bits_hex"] == struct.pack(">d", invalid).hex()
        assert raw["value"]["values"]["dtype"] == array.dtype.str
        assert raw["value"]["values"]["shape"] == [2]
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as saved:
            np.testing.assert_array_equal(saved["root/values"], array)
    save("raw-first-writer", dict(capture_only=True, successful_json_schema_preserved=True))
