"""Unfrozen trajectory caller/horizon planning from accepted geometry metadata.

This module imports no scientific package and evaluates no model or fixture.
Local source-value time scales are planning estimates, not stability proofs.
"""

import ast
import hashlib
import json
import math
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from validation.geometry import stable_seed_partition_physiology_bridge_declarations as original

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "validation/geometry/stable_seed_partition_trajectory_"
GEOMETRY_ACCEPTANCE = Path(
    "/mnt/workspaces/Cells/stable-seed-explicit-ecm-partition-completion-review-20261031-01/ROOT_ACCEPTANCE.json"
)
GEOMETRY_ACCEPTANCE_SHA256 = "f2f1eab5db26bdc5e4b6dc9a8a9e3c54f5b894b2fbcdee344f5307900603a8c9"
ORIGINAL_CALLERS = "validation/geometry/stable_seed_partition_physiology_bridge_callers.json"
ORIGINAL_CALLERS_SHA256 = "4be058c5f6211a9a489c709ee95f371d3dd7bf0ba03c8834e789c0be3554c09f"
CLOCKS = (("base", 1e-6, 1), ("dt-half", 5e-7, 2), ("dt-quarter", 2.5e-7, 4))
POSITIVE_CAPS = {
    "uniform-two-species": 1048576,
    "unequal-clefts-readback-defects": 1048576,
    "two-cell-four-species": 4194304,
    "four-cell-reordered-gradient": 8388608,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def document_path():
    return ROOT / (PREFIX + "callers.json")


def document():
    return read(document_path())


def geometry_declaration(case):
    return original.geometry_declaration(case)


def _fraction(value):
    return Fraction(float(value))


def _constant(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _constant(node.left) * _constant(node.right)
    raise ValueError("Only the source's literal physical constant products are admitted")


def source_constants():
    tree = ast.parse((ROOT / "src/cells/processes/electrochemistry.py").read_bytes())
    result = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            if node.targets[0].id in {"F", "R"}:
                result[node.targets[0].id] = float(_constant(node.value))
    if set(result) != {"F", "R"}:
        raise ValueError("Retain the existing Cells Faraday/gas constant source")
    return result


def _record_scale(kind, owner, species, value, **inputs):
    if value <= 0:
        raise ValueError("Only positive source-value planning time scales are meaningful")
    return dict(
        kind=kind,
        owner=owner,
        species=species,
        tau_s=float(value),
        tau_s_exact=dict(numerator=str(value.numerator), denominator=str(value.denominator)),
        source_inputs=inputs,
    )


def time_scale_rows(case, shared, geometry):
    """Analytic metadata estimates on actual accepted V/A/L and literal D/P/C."""
    volumes = {row["id"]: _fraction(row["volume_m3"]) for row in geometry["regions"]}
    rows = []
    for species in case["species"]:
        name = species["id"]
        face = {owner: Fraction(0) for owner in geometry["bath_ids"]}
        for route in geometry["faces"]:
            conductance = (
                _fraction(case["face_diffusivity_m2_per_s"][name])
                * _fraction(route["area_m2"])
                / _fraction(route["length_m"])
            )
            face[route["sender"]] += conductance
            face[route["receiver"]] += conductance
        for owner, conductance in face.items():
            if conductance:
                rows.append(
                    _record_scale(
                        "finite_bath_diffusive_inventory",
                        owner,
                        name,
                        volumes[owner] / conductance,
                        volume_m3=float(volumes[owner]),
                        summed_DA_over_L_m3_s=float(conductance),
                    )
                )
        membrane = {owner: Fraction(0) for owner in geometry["owner_axis"]}
        for route in geometry["membranes"]:
            conductance = _fraction(case["membrane_permeability_m_per_s"][name]) * _fraction(
                route["area_m2"]
            )
            membrane[route["cell_id"]] += conductance
            membrane[route["bath_id"]] += conductance
        for owner, conductance in membrane.items():
            if conductance:
                rows.append(
                    _record_scale(
                        "membrane_inventory_exchange",
                        owner,
                        name,
                        volumes[owner] / conductance,
                        volume_m3=float(volumes[owner]),
                        summed_PA_m3_s=float(conductance),
                    )
                )
    constants = source_constants()
    faraday, gas = map(_fraction, (constants["F"], constants["R"]))
    for route in geometry["membranes"]:
        y_slot = int(route["bath_id"].rsplit("-", 1)[1])
        slope = Fraction(0)
        for species in case["species"]:
            name, z = species["id"], species["valence"]
            mean = (
                _fraction(case["cell_concentration_mM"][name])
                + _fraction(case["bath_concentration_by_slot_y_mM"][y_slot][name])
            ) / 2
            slope += z * z * _fraction(case["membrane_permeability_m_per_s"][name]) * mean
        tau = (
            _fraction(shared["specific_capacitance_F_per_m2"])
            * gas
            * _fraction(case["temperature_K"])
            / (faraday * faraday * slope)
        )
        rows.append(
            _record_scale(
                "zero_voltage_local_capacitive_slope",
                route["id"],
                None,
                tau,
                specific_capacitance_F_per_m2=shared["specific_capacitance_F_per_m2"],
                temperature_K=case["temperature_K"],
                F_C_mol=constants["F"],
                R_J_mol_K=constants["R"],
                summed_z2_P_meanC=slope.numerator / slope.denominator,
            )
        )
    return rows


def trace_bytes(case, steps, observations):
    x, s = case["capacities"], len(case["species"])
    columns = (48 * s + 96) * (
        x["capacity"] + x["extracellular_capacity"] + x["membrane_capacity"] + x["face_capacity"]
    ) + 96 * (x["capacity"] + x["extracellular_capacity"]) ** 2
    return 8 * (columns * (steps + 1 + observations) + 4 * (steps + 1))


def planning_document():
    """Read retained metadata only; do not construct new geometry or physiology."""
    if sha(GEOMETRY_ACCEPTANCE) != GEOMETRY_ACCEPTANCE_SHA256:
        raise ValueError("Changed exact Root geometry acceptance")
    if sha(ROOT / ORIGINAL_CALLERS) != ORIGINAL_CALLERS_SHA256:
        raise ValueError("Changed original four physical callers")
    accepted = read(GEOMETRY_ACCEPTANCE)
    original_callers = read(ROOT / ORIGINAL_CALLERS)
    geometry_rows = {row["case"]: row for row in accepted["accepted_geometry_reports"]}
    cases = []
    for case in original_callers["cases"]:
        accepted_row = geometry_rows[case["geometry_case"]]
        for record in (accepted_row["candidate"], accepted_row["report"]):
            if sha(record["path"]) != record["sha256"]:
                raise ValueError("Changed accepted saved geometry metadata")
        candidate = read(accepted_row["candidate"]["path"])
        geometry = json.loads(candidate["partition_binding"]["geometry_json"])
        scales = time_scale_rows(case, original_callers["shared"], geometry)
        fastest = min(
            scales,
            key=lambda row: Fraction(
                int(row["tau_s_exact"]["numerator"]), int(row["tau_s_exact"]["denominator"])
            ),
        )
        tau = Fraction(
            int(fastest["tau_s_exact"]["numerator"]), int(fastest["tau_s_exact"]["denominator"])
        )
        coarse_steps = max(8, math.ceil(tau / _fraction(1e-6)))
        end = coarse_steps * 1e-6
        peak_window_bytes = 2 * trace_bytes(case, 1, 2) + 2 * trace_bytes(case, 0, 0)
        positive_cap = POSITIVE_CAPS[case["id"]]
        arms = []
        for clock, dt, divisor in CLOCKS:
            count = coarse_steps * divisor
            maximum = max(count, math.ceil(end / dt))
            arms.append(
                dict(
                    id=clock,
                    dt_s=dt,
                    end_time_s=end,
                    end_time_hex=end.hex(),
                    actual_steps=count,
                    max_steps=maximum,
                    max_trace_bytes=positive_cap,
                    window_steps=1,
                    window_recording="full",
                    source_predicted_window_bytes=peak_window_bytes,
                    source_predicted_window_admission=peak_window_bytes <= positive_cap,
                )
            )
        if case["id"] == "four-cell-reordered-gradient":
            for cap, label in ((1048576, "1MiB"), (4194304, "4MiB")):
                for base in tuple(arms[:3]):
                    arms.append(
                        dict(
                            base,
                            id=base["id"] + "-refusal-" + label,
                            max_trace_bytes=cap,
                            source_predicted_window_admission=False,
                            expected_refusal=(
                                "Estimated window working storage exceeds max_trace_bytes"
                            ),
                        )
                    )
        cases.append(
            dict(
                case_id=case["id"],
                geometry_case=case["geometry_case"],
                geometry_acceptance_row=accepted_row,
                geometry_binding_identity=candidate["partition_binding"]["identity"],
                source_time_scale_rows=scales,
                fastest_planning_scale=fastest,
                horizon_rule=(
                    "ceil(one fastest positive local source-value time scale / coarse dt), "
                    "minimum eight coarse steps"
                ),
                end_time_s=end,
                coarse_steps=coarse_steps,
                dt_over_fastest_scale=1e-6 / float(tau),
                window_estimate_uses_initial_observation_at_zero=True,
                arms=arms,
                positive_arm_ids=["base", "dt-half", "dt-quarter"],
                fresh_initial_qualification_required_for_every_arm=True,
                uninterrupted_and_restart_share_identical_full_definition=True,
            )
        )
    return dict(
        kind="cells.unfrozen_partition_trajectory_horizon_callers@1",
        frozen=False,
        geometry_acceptance_sha256=GEOMETRY_ACCEPTANCE_SHA256,
        original_callers_document_sha256=ORIGINAL_CALLERS_SHA256,
        original_physical_callers_unchanged=True,
        source_value_time_scale_planning_only=True,
        time_scale_estimates_are_not_global_eigenvalues_or_stability_certificates=True,
        qualification_inherited=False,
        new_physical_cases=0,
        physical_cases=4,
        fresh_initial_case_arm_bindings=18,
        positive_trajectory_arms=12,
        window_refusal_arms=6,
        original_1MiB_and_4MiB_evidence_preserved=True,
        case4_8MiB_control_separately_authorized=True,
        guards=dict(worker_GiB=1, aggregate_GiB=2, host_reserve_GiB=8),
        numerical_launch_authorized=False,
        fixtures_materialized=0,
        models_evaluated=0,
        cases=cases,
    )


def selected(case_id, control_id):
    case = next(row for row in document()["cases"] if row["case_id"] == case_id)
    return next(row for row in case["arms"] if row["id"] == control_id)


def case(case_id):
    return next(row for row in document()["cases"] if row["case_id"] == case_id)


def comparison_ids(case_id):
    return tuple(case(case_id)["positive_arm_ids"])


def clock_labels(case_id, control_id):
    """Literal declared labels, without importing or evaluating a numerical model."""
    arm = selected(case_id, control_id)
    count, dt, end = arm["actual_steps"], arm["dt_s"], arm["end_time_s"]
    labels = [i * dt for i in range(count)] + [end]
    if (
        not labels
        or labels[0] != 0.0
        or any(b <= a for a, b in zip(labels, labels[1:], strict=False))
    ):
        raise ValueError("Full-horizon labels must strictly increase from the true initial epoch")
    return labels


def same_physical_definition(case_id, definitions):
    normalized = []
    caps = []
    for control_id in comparison_ids(case_id):
        raw = deepcopy(definitions[control_id])
        arm = selected(case_id, control_id)
        if raw["experiment"]["end_time"] != arm["end_time_s"]:
            raise ValueError("Each full-horizon caller declares its end time from initialization")
        for key, expected in (
            ("dt", arm["dt_s"]),
            ("max_steps", arm["max_steps"]),
            ("max_trace_bytes", arm["max_trace_bytes"]),
        ):
            if raw["execution"][key] != expected:
                raise ValueError("Changed explicit trajectory clock/storage contract: " + key)
        caps.append(raw["execution"]["max_trace_bytes"])
        raw["execution"].pop("dt")
        raw["execution"].pop("max_steps")
        normalized.append(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False))
    if len(set(caps)) != 1 or len(set(normalized)) != 1:
        raise ValueError(
            "Refinement retains identical physics, controls and storage within each case"
        )


def declaration(case_id, geometry, *, document_sha256, numerical_control_id):
    if document_sha256 != ORIGINAL_CALLERS_SHA256:
        raise ValueError("Bind the unchanged original physical caller document")
    arm = selected(case_id, numerical_control_id)
    value = deepcopy(original.declaration(case_id, geometry, document_sha256=document_sha256))
    value["experiment"]["end_time"] = arm["end_time_s"]
    value["execution"].update(
        dt=arm["dt_s"], max_steps=arm["max_steps"], max_trace_bytes=arm["max_trace_bytes"]
    )
    value["provenance"].update(
        kind="explicit_new_full_horizon_trajectory_initial_caller@1",
        trajectory_document_sha256=sha(document_path()),
        numerical_control_id=numerical_control_id,
        original_caller_document_sha256=ORIGINAL_CALLERS_SHA256,
        initial_qualification_inherited=False,
        full_horizon_contract_from_initialization=True,
    )
    return value
