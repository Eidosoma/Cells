"""Complete active polygon admission and independently checked initial fields.

Every prelude and actual trial is durable before assertions. No step, trajectory,
native-equivalence or failed-mesh qualification is performed by this packet.
"""

import importlib
import json
import os
import traceback
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import active_polygon_physiology_preparation as active
from cells.core.schedule import control_values
from cells.processes import conservative_polygon_geometry as geometry
from validation.geometry import active_polygon_physiology_fixtures as fixtures
from validation.geometry import active_polygon_physiology_reference as reference
from validation.geometry import active_polygon_physiology_runtime as runtime
from validation.geometry import conservative_polygon_geometry_fixtures as polygons


def save(name, value):
    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "active-polygon-physiology"
    root.mkdir(parents=True, exist_ok=True)
    path = root / (name + ".json")
    runtime.write(path, value)
    return path


def failure(name, error):
    save(
        name + "-failure",
        dict(
            type=type(error).__name__,
            reason=str(error),
            trial=getattr(error, "trial", None),
            traceback=traceback.format_exc(),
        ),
    )


def geometry_input(name, case):
    declaration = polygons.fixture(fixtures.geometry_case(case))
    save(name + "-geometry-input", declaration)
    try:
        request = geometry.from_polygons(declaration, law_id=geometry.LAW_ID)
        save(name + "-geometry-request", geometry.request_record(request))
        binding = geometry.prepare(request)
    except Exception as error:
        failure(name + "-geometry", error)
        raise
    save(name + "-geometry-actual", dict(identity=binding.identity, geometry=binding.geometry))
    return declaration, request, binding


def prepared(name, case):
    declaration, g_request, binding = geometry_input(name, case)
    try:
        raw = fixtures.request(case, declaration, binding)
    except Exception as error:
        failure(name + "-fixture", error)
        raise
    save(name + "-active-input", raw)
    try:
        value = active.prepare(g_request, binding, raw)
    except Exception as error:
        failure(name + "-active", error)
        raise
    packet = dict(
        case=case,
        geometry_declaration=declaration,
        geometry_request=geometry.request_record(g_request),
        geometry=binding.geometry,
        geometry_identity=binding.identity,
        request=raw,
        definition=value.definition,
        provenance=value.provenance,
        identity=value.identity,
    )
    save(name + "-prepared", packet)
    return g_request, binding, raw, value, packet


def initial_packet(name, packet):
    raw = packet["definition"]
    target = raw["model"]["id"]
    parser = importlib.import_module("cells.core." + active.FAMILIES[target][0])
    model = importlib.import_module("cells.models." + active.FAMILIES[target][1])
    try:
        spec = parser.parse(raw)
        state, p = model.initial_values(spec)
        packet = packet | dict(state=state._asdict(), layout=p._asdict(), initial_control_probes=[])
        save(name + "-initial-state", packet)
        for i, time in enumerate((0.0, 5e-7)):
            table = control_values(spec, [time])
            control = type(table)(*(row[0] for row in table))
            # This readout is instantaneous on the SAME untouched initial state.
            result = model.readouts(state, control, p, xp=np)
            field = result.field
            phi = np.r_[
                field.potential_V[: p.active.size][p.active],
                field.potential_V[p.active.size :][p.outside_active],
            ]
            trial = dict(
                time_s=time,
                control=control._asdict(),
                derivative=result.derivative._asdict(),
                potential_V=phi,
                field=field._asdict(),
                valid=bool(result.valid),
            )
            save(name + f"-initial-actual-{i}", trial)
            packet["initial_control_probes"].append(trial)
    except Exception as error:
        failure(name + "-initial-field", error)
        raise
    # Store plain JSON values for fresh independent workers.
    packet = json.loads(
        json.dumps(packet, allow_nan=False, default=lambda item: np.asarray(item).tolist())
    )
    save(name + "-packet", packet)
    return packet


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_family_units_polarization_and_initial_flow(case):
    name = "positive-" + case
    _, _, _, value, packet = prepared(name, case)
    packet = initial_packet(name, packet)
    try:
        for refinement in (1, 2):
            save(
                name + f"-conversion-targets-{refinement}",
                reference.materialize(
                    packet["geometry_declaration"],
                    packet["geometry"],
                    packet["request"],
                    refinement=refinement,
                ),
            )
        conversion = reference.compare_conversion(packet)
        save(name + "-conversion-comparison", conversion)
        field = reference.compare_initial_field(
            packet, retain=lambda label, value, stem=name: save(stem + "-" + label, value)
        )
        save(name + "-field-comparison", field)
        reference.assert_initial_field(field)
    except Exception as error:
        failure(name + "-independent", error)
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
    first, second = packet["initial_control_probes"]
    assert np.any(np.asarray(first["derivative"]["pump_cycles"]) != 0)
    assert np.any(np.asarray(first["derivative"]["channel_transferred"]) != 0)
    assert not np.array_equal(
        first["derivative"]["pump_cycles"], second["derivative"]["pump_cycles"]
    )
    for key in ("chemical_amount_increment", "energy_amount_increment_fmol"):
        if key in first["derivative"]:
            assert np.any(np.asarray(first["derivative"][key]) != 0)
    ion = packet["definition"]["model"].get("ionic", packet["definition"]["model"])
    assert {row["id"]: row["reservoir"] for row in ion["extracellular"]} == value.provenance[
        "actual_reservoir_flags"
    ]


@pytest.mark.parametrize("case", fixtures.DOMAIN_CASES)
def test_unsupported_domain_and_incomplete_active_ownership_refuse(case):
    name = "domain-" + case
    declaration, g_request, binding = geometry_input(
        name,
        "open-fuel-mixed"
        if case
        in ("missing-open-policy", "open-ceiling-below-true-moiety", "empty-open-nonnull-ceiling")
        else "fuel-calcium-full",
    )
    try:
        raw = fixtures.invalid(case, declaration, binding)
    except Exception as error:
        failure(name + "-fixture", error)
        raise
    save(name + "-active-input", raw)
    with pytest.raises(active.ActivePreparationRejected) as caught:
        active.prepare(g_request, binding, raw)
    save(name + "-active-refusal", caught.value.trial)
    assert caught.value.trial["physical_model_prepared"] is False
    if case in (
        "wrong-free-ion-amount",
        "closed-calcium-held-bath",
        "closed-fuel-held-bath",
        "missing-open-policy",
        "open-ceiling-below-true-moiety",
        "empty-open-nonnull-ceiling",
        "missing-control",
        "unordered-control-clock",
        "existing-charge-closure-refusal",
    ):
        assert caught.value.trial["stage"] == "existing_complete_physical_admission"
        assert caught.value.trial["failure_type"] == "ConfigError"


@pytest.mark.parametrize("case", fixtures.MUTATION_CASES)
def test_immutable_active_inventory_fuel_and_provenance(case):
    name = "mutation-" + case
    g_request, binding, raw, value, _ = prepared(name, "fuel-calcium-full")
    definition, provenance = value.definition, value.provenance
    if case == "definition-area":
        definition["model"]["ionic"]["membranes"][0]["area_m2"] *= 2
    elif case == "definition-inventory":
        definition["model"]["ionic"]["cells"][0]["initial_amount_fmol"]["Na"] *= 2
    elif case == "definition-fuel":
        definition["model"]["energy_pools"][0]["initial_amount_fmol"]["ATP"] *= 2
    elif case == "provenance-owner":
        provenance["owner_projection"]["cells"].reverse()
    elif case == "returned-copy-alias":
        definition["model"]["ionic"]["cells"][0]["id"] = "forged"
        assert value.definition["model"]["ionic"]["cells"][0]["id"] != "forged"
        active.validate(g_request, binding, raw, value)
        save(name + "-comparison", dict(returned_copies_do_not_mutate_preparation=True))
        return
    else:
        raise ValueError(case)
    forged = replace(
        value,
        definition_json=geometry._json(definition),
        provenance_json=geometry._json(provenance),
        identity=geometry._digest(dict(definition=definition, provenance=provenance)),
    )
    save(
        name + "-forgery",
        dict(definition=definition, provenance=provenance, identity=forged.identity),
    )
    with pytest.raises(ValueError):
        active.validate(g_request, binding, raw, forged)
    save(name + "-comparison", dict(resealed_mutation_refused=True))


@pytest.mark.parametrize("case", fixtures.CORRUPTION_CASES)
def test_independent_conversion_detects_geometry_or_physiology_changes(case):
    name = "corruption-" + case
    _, _, _, _, packet = prepared(name, "open-fuel-mixed")
    changed = deepcopy(packet)
    model = changed["definition"]["model"]
    ion = model["ionic"]
    if case == "volume":
        ion["cells"][0]["volume_pL"] *= 1.1
    elif case == "capacitance":
        ion["membranes"][0]["capacitance_F"] *= 1.1
    elif case == "channel-path":
        ion["channels"][0]["max_permeability_m_per_s"] *= 2
    elif case == "fuel-owner":
        model["energy_pools"][0]["cell_id"] = ion["cells"][1]["id"]
    elif case == "reservoir-flag":
        ion["extracellular"][0]["reservoir"] = False
    elif case == "control-clock":
        changed["definition"]["experiment"]["channel_controls"][0]["schedule"][1]["time"] *= 0.9
    else:
        raise ValueError(case)
    save(name + "-packet", changed)
    with pytest.raises(AssertionError):
        reference.compare_conversion(changed)
    save(name + "-comparison", dict(independent_reference_rejected_corruption=True))


def test_finite_fuel_initial_composition_changes_owned_pumping_without_time_advance():
    packets = []
    for case in ("fuel-calcium-full", "fuel-calcium-depleted"):
        name = "fuel-sensitivity-" + case
        _, _, _, _, packet = prepared(name, case)
        packet = initial_packet(name, packet)
        report = reference.compare_initial_field(
            packet, retain=lambda label, value, stem=name: save(stem + "-" + label, value)
        )
        save(name + "-field-comparison", report)
        reference.assert_initial_field(report)
        packets.append(packet)
    first, second = (p["initial_control_probes"][0]["derivative"] for p in packets)
    save("fuel-sensitivity-comparison", dict(first=first, second=second, time_advanced=False))
    assert not np.array_equal(first["pump_cycles"], second["pump_cycles"])
    assert not np.array_equal(first["plasma_pump_cycles"], second["plasma_pump_cycles"])
    assert not np.array_equal(first["er_pump_transferred"], second["er_pump_transferred"])
