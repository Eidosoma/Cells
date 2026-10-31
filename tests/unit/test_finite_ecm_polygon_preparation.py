"""Explicit finite-ECM geometry, physical admission and complete initial fields."""

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

from cells.core import finite_ecm_polygon_preparation as physical
from cells.core import surface_tissue_spec as schema
from cells.core.schedule import control_values
from cells.models import surface_tissue as model
from cells.processes import finite_ecm_polygon_geometry as geometry
from validation.geometry import conservative_polygon_geometry_reference as polygon_reference
from validation.geometry import finite_ecm_polygon_fixtures as fixtures
from validation.geometry import finite_ecm_polygon_reference as reference


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
    folder = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "finite-ecm-polygon"
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


def bound(name, case):
    raw = fixtures.fixture(case)
    save(name + "-input", raw)
    try:
        request = geometry.from_partition(raw, law_id=geometry.LAW_ID)
        save(name + "-request", geometry.request_record(request))
        binding = geometry.prepare(request)
    except Exception as error:
        failure(name + "-geometry", error)
        raise
    save(name + "-geometry", dict(identity=binding.identity, geometry=binding.geometry))
    return raw, request, binding


def geometry_targets(name, raw):
    reports = []
    for refinement in (1, 2):
        value = reference.evaluate(raw, refinement=refinement)
        save(name + "-geometry-targets-" + str(refinement), value)
        reports.append(value)
    return reports


def prepared(name, case):
    declaration, request, binding = bound(name, case)
    try:
        raw = fixtures.physical(case, declaration, binding)
    except Exception as error:
        failure(name + "-physical-fixture", error)
        raise
    save(name + "-physical-input", raw)
    try:
        value = physical.prepare(request, binding, raw)
    except Exception as error:
        failure(name + "-physical", error)
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
    try:
        spec = schema.parse(packet["definition"])
        state, p = model.initial_values(spec)
        packet = packet | dict(state=state._asdict(), layout=p._asdict(), initial_control_probes=[])
        save(name + "-initial-state", packet)
        for index, time in enumerate((0.0, 5e-7)):
            table = control_values(spec, [time])
            control = type(table)(*(value[0] for value in table))
            fields = model.field_values(state, control, p, xp=np)
            save(
                name + "-initial-field-return-" + str(index),
                dict(time_s=time, control=control, field=fields),
            )
            derivative = model.derivative_from_field(fields, p, xp=np)
            phi = np.r_[
                fields.potential_V[: p.active.size][p.active],
                fields.potential_V[p.active.size :][p.outside_active],
            ]
            trial = dict(
                time_s=time,
                control=control,
                field=fields,
                derivative=derivative,
                potential_V=phi,
                valid=bool(fields.converged),
                energy_balance_pJ_s=float(fields.energy_balance_pJ_s),
            )
            save(name + "-initial-actual-" + str(index), trial)
            packet["initial_control_probes"].append(plain(trial))
    except Exception as error:
        failure(name + "-field", error)
        raise
    save(name + "-packet", packet)
    return plain(packet)


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_explicit_partition_geometry_and_distances(case):
    name = "geometry-" + case
    raw, _, binding = bound(name, case)
    try:
        targets = geometry_targets(name, raw)
        comparison = reference.compare_geometry(raw, binding.geometry, *targets)
    except Exception as error:
        failure(name + "-independent", error)
        raise
    save(name + "-comparison", comparison)
    assert comparison["exact_partition_volume_and_orthogonal_distance_targets"]
    assert not binding.geometry["qualification_inherited"]


@pytest.mark.parametrize("case", fixtures.DOMAIN_CASES)
def test_unsupported_partition_or_boundary_refuses_independently(case):
    name = "domain-" + case
    raw = fixtures.domain(case)
    save(name + "-input", raw)
    with pytest.raises(geometry.PartitionRejected) as caught:
        request = geometry.from_partition(raw, law_id=geometry.LAW_ID)
        save(name + "-request", geometry.request_record(request))
        geometry.prepare(request)
    save(
        name + "-refusal",
        dict(
            type=type(caught.value).__name__,
            reason=str(caught.value),
            stage=caught.value.stage,
            trial=caught.value.trial,
        ),
    )
    with pytest.raises(
        (reference.ReferenceRejected, polygon_reference.ReferenceRejected)
    ) as independent:
        reference.evaluate(raw)
    save(
        name + "-independent-refusal",
        dict(type=type(independent.value).__name__, reason=str(independent.value)),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_passive_admission_polarized_initial_field_and_ECM_flux(case):
    name = "physical-" + case
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
        conversion = reference.compare_conversion(packet, *targets)
        save(name + "-conversion-comparison", conversion)
        report = reference.compare_initial_field(
            packet, retain=lambda label, record: save(name + "-" + label, record)
        )
        save(name + "-field-comparison", report)
        reference.assert_initial_field(report)
    except Exception as error:
        failure(name + "-independent", error)
        raise
    assert value.provenance["physical_model_prepared"]
    for key in (
        "inventories_rescaled",
        "physics_defaults_inserted",
        "native_equivalence",
        "qualification_inherited",
        "trajectory_executed",
    ):
        assert value.provenance[key] is False
    first, second = packet["initial_control_probes"]
    assert not np.array_equal(
        first["derivative"]["membrane_transferred"], second["derivative"]["membrane_transferred"]
    )
    assert all(not row["reservoir"] for row in packet["definition"]["model"]["extracellular"])
    # At least one bath is represented only by bath faces, exercising a floating
    # bulk component rather than merely multiple patches of one exterior pool.
    assert set(packet["geometry"]["bath_ids"]) - {
        row["bath_id"] for row in packet["geometry"]["membranes"]
    }
    assert all(stage["capacitive_components"] > 1 for stage in report["stages"])


@pytest.mark.parametrize("case", fixtures.PHYSICAL_DOMAIN_CASES)
def test_complete_physics_owner_units_and_boundary_refusals(case):
    name = "physical-domain-" + case
    declaration, request, binding = bound(name, "one-cell-grid")
    try:
        raw = fixtures.physical_domain(case, declaration, binding)
    except Exception as error:
        failure(name + "-fixture", error)
        raise
    save(name + "-physical-input", raw)
    with pytest.raises(physical.PhysicalRejected) as caught:
        physical.prepare(request, binding, raw)
    save(name + "-physical-refusal", caught.value.trial)
    assert not caught.value.trial["physical_model_prepared"]
    if case in (
        "missing-control",
        "duplicate-control-clock",
        "bad-charge-anchor",
        "unowned-gauge",
        "nongauge-boundary-potential",
    ):
        assert caught.value.trial["stage"] == "existing_complete_physical_admission"
        assert caught.value.trial["failure_type"] == "ConfigError"


def corrupt(case, g):
    g = deepcopy(g)
    if case == "bath-volume":
        next(row for row in g["regions"] if row["kind"] == "bath")["volume_m3"] *= 2
    elif case == "membrane-area":
        g["membranes"][0]["area_m2"] *= 2
    elif case == "face-distance":
        g["faces"][0]["length_m"] *= 2
    elif case == "face-normal":
        g["faces"][0]["normal_xy"][0] += 0.25
    elif case == "face-owner":
        row = g["faces"][0]
        row["sender"], row["receiver"] = row["receiver"], row["sender"]
    elif case == "boundary-owner":
        g["boundary"][0]["region_id"] = g["cell_ids"][0]
    elif case == "face-incidence":
        matrix = g["face_incidence"]
        for row in matrix:
            row[0] = 0
        matrix[0][0] = -1
        matrix[1][0] = 1
    elif case == "geometry-certificate":
        cert = g["regions"][0]["certificates"]["volume"]["exact"]
        cert["numerator"] = str(int(cert["numerator"]) + 1)
    else:
        raise ValueError(case)
    return g


@pytest.mark.parametrize("case", fixtures.CORRUPTION_CASES)
def test_independent_reference_detects_balanced_owner_and_metric_corruption(case):
    name = "corruption-" + case
    raw, request, binding = bound(name, "one-cell-grid")
    g = corrupt(case, binding.geometry)
    save(
        name + "-packet",
        dict(
            geometry_declaration=raw, geometry_request=geometry.request_record(request), geometry=g
        ),
    )
    targets = geometry_targets(name, raw)
    with pytest.raises(AssertionError):
        reference.compare_geometry(raw, g, *targets)
    save(name + "-comparison", dict(expected_corruption_refused=True))


@pytest.mark.parametrize("case", fixtures.OWNERSHIP_CASES)
def test_complete_geometry_and_preparation_authority(case):
    name = "ownership-" + case
    if case == "wrong-opt-in":
        raw = fixtures.fixture("one-cell-grid")
        save(name + "-input", raw)
        with pytest.raises(geometry.PartitionRejected):
            geometry.from_partition(raw, law_id="other")
        save(name + "-comparison", dict(wrong_opt_in_refused=True))
        return
    if case in ("request-identity", "binding-resealed-normal"):
        _, request, binding = bound(name, "one-cell-grid")
        if case == "request-identity":
            forged = replace(request, identity="0" * 64)
            save(name + "-forgery", geometry.request_record(forged))
            with pytest.raises(geometry.PartitionRejected):
                geometry.prepare(forged)
        else:
            g = binding.geometry
            g["faces"][0]["normal_xy"][0] += 0.25
            forged = replace(
                binding, geometry_json=geometry.exact._json(g), identity=geometry.exact._digest(g)
            )
            save(name + "-forgery", dict(identity=forged.identity, geometry=g))
            with pytest.raises(ValueError):
                geometry.validate_binding(request, forged)
        save(name + "-comparison", dict(incomplete_or_resealed_authority_refused=True))
        return
    request, binding, raw, value, _ = prepared(name, "one-cell-grid")
    definition, provenance = value.definition, value.provenance
    if case == "prepared-volume":
        definition["model"]["extracellular"][0]["volume_pL"] *= 2
    elif case == "prepared-inventory":
        definition["model"]["cells"][0]["initial_amount_fmol"]["Na"] *= 2
    elif case == "returned-copy-alias":
        definition["model"]["cells"][0]["id"] = "changed"
        geometry_copy = binding.geometry
        geometry_copy["faces"][0]["length_m"] *= 2
        assert value.definition["model"]["cells"][0]["id"] != "changed"
        assert binding.geometry["faces"][0]["length_m"] != geometry_copy["faces"][0]["length_m"]
        physical.validate(request, binding, raw, value)
        save(name + "-comparison", dict(returned_copies_independently_owned=True))
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
        physical.validate(request, binding, raw, forged)
    save(name + "-comparison", dict(resealed_physical_change_refused=True))
