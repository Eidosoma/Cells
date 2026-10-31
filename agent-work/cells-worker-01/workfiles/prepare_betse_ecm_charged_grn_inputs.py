# ruff: noqa: E501
"""Emit declared fixture recipes and independent cold equations without running them."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = ROOT / "validation/betse"
NEW = "betse_ecm_charged_grn"


def emit(name, text):
    with (BASE / (NEW + name)).open("x") as stream:
        stream.write(text)


emit(
    "_fixtures.py",
    '''"""Charged cold ECM recipes; every counterion has a real owned species row."""

from validation.betse.betse_ecm_grn_fixtures import fixture as previous

CASES = (
    "positive", "negative", "zero_charge_control", "compensation_off",
    "runtime_publish_off", "publication_carry", "negative_threshold_gap",
    "source_defaults", "scaled_charge", "rectangular", "fast_duplicate",
    "tight_junction", "temperature_split", "time_dilation", "smoothed",
    "scheduled_boundary", "no_modulators", "no_molecular_transport",
)
COMPONENT_CONTROLS = ("zero_charge_control", "compensation_off", "no_modulators", "no_molecular_transport")
RAW_CASES = ("cell_positive_excess", "cell_negative_excess", "env_positive_excess", "env_negative_excess")
DEPENDENCIES = (
    "wrong_owner", "missing_M", "wrong_M_valence", "moving_M", "mitochondria",
    "fluid", "missing_cache", "missing_ionic_cache", "missing_balance_events",
    "wrong_environment_shape", "missing_default", "missing_coefficients", "prepared_mapping",
)


def fixture(case="positive"):
    if case not in CASES:
        raise ValueError("Choose a declared ECM charged GRN case")
    inherited = {"positive": "charged", "zero_charge_control": "neutral_cold_control"}.get(case, case)
    data = previous(inherited if inherited in (
        "charged", "negative", "neutral_cold_control", "publication_carry", "rectangular",
        "fast_duplicate", "tight_junction", "temperature_split", "time_dilation", "smoothed",
        "no_modulators", "no_molecular_transport") else "charged")
    definition = data["definition"]
    geometry = definition["environment_geometry_definition"]
    ion = geometry["current_definition"]["ions"]
    original_ids = list(ion["ids"])
    ion["ids"] = original_ids + ["M"]
    ion["valence"] = list(ion["valence"]) + [-1.0]
    m = len(data["initial"]["voltage_V"])
    e = len(data["initial"]["environment_mol_m3"][0])
    n = len(data["initial"]["cell_mol_m3"][0])
    p_index = original_ids.index("P")
    gap = case == "negative_threshold_gap"
    for key, count, value in (
        ("cell_mol_m3", n, 0.5e-6 if gap else 1e-4),
        ("membrane_mol_m3", m, 2e-6 if gap else 1e-4),
        ("environment_mol_m3", e, 1e-4),
        ("membrane_flux_mol_m2_s", m, 0.0),
        ("junction_flux_mol_m2_s", m, 0.0),
        ("environment_flux_x_mol_m2_s", e, 0.0),
        ("environment_flux_y_mol_m2_s", e, 0.0),
    ):
        rows = data["initial"][key]
        rows.append([value] * count)
        if key in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
            rows[p_index] = [v - value for v in rows[p_index]]
    for key, width, value in (
        ("membrane_diffusion_m2_s", m, 0.0), ("gap_diffusion_m2_s", m, 0.0),
        ("environment_diffusion_m2_s", e, 0.0), ("tight_junction_modulator", e, 1.0),
    ):
        definition["ions"][key].append([value] * width)
    geometry["cache_initial_state"] = dict(
        cell_mol_m3=[row[:] for row in data["initial"]["cell_mol_m3"]],
        environment_mol_m3=[row[:] for row in data["initial"]["environment_mol_m3"]],
        free_diffusion_m2_s=list(geometry["cache_initial_state"]["free_diffusion_m2_s"]) + [0.0],
    )
    net = data["network"]
    z = -1.0 if case in ("negative", "negative_threshold_gap") else 0.0 if case == "zero_charge_control" else 1.0
    for row in net["configuration"]["biomolecules"]:
        row.update({"z": z, "scale factor": 2e-6 if case == "scaled_charge" else 1e-6})
        if case == "source_defaults":
            del row["Dgj"]
    net["cold_publish"] = case != "compensation_off"
    net["initial_ion_boundary"] = [row[0] for row in data["initial"]["environment_mol_m3"]]
    for index, call in enumerate(data["steps"]):
        packet = call["material"]
        packet["supplied_pump_membrane_flux_mol_m2_s"].append([0.0] * m)
        packet["supplied_late_membrane_flux_mol_m2_s"].append([0.0] * m)
        packet["boundary_mol_m3"][p_index] -= 1e-4
        packet["boundary_mol_m3"].append(1e-4)
        call["boundary_override"] = case == "scheduled_boundary" and index == 1
        if case == "runtime_publish_off":
            call["publication"] = False
    data["case_id"] = case
    data["case_role"] = "component_control" if case in COMPONENT_CONTROLS else "new_ecm_charged_grn_case"
    data["counterion_input_recipe"] = dict(actual_M_row=True, stationary_M=True,
        P_decrement_equals_supplied_M=True, membrane_cache_independent_from_bulk=gap,
        biological_calibration=False)
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared ECM cold capacity refusal")
    # Environment failures use E=12, M=9 to expose region/shape ownership.
    data = fixture("rectangular" if case.startswith("env_") else "positive")
    n = len(data["initial"]["cell_mol_m3"][0])
    m = len(data["initial"]["voltage_V"])
    e = len(data["initial"]["environment_mol_m3"][0])
    for row in data["network"]["configuration"]["biomolecules"]:
        row.update({"z": -1.0 if "negative" in case else 1.0,
                    "scale factor": 1.0 if case == "cell_positive_excess" else 1e-6,
                    "cell conc": 200.0 if case.startswith("cell_") else row["cell conc"],
                    "env conc": (2e8 if "positive" in case else 200.0) if case.startswith("env_") else row["env conc"]})
    data["network"]["raw_initialization_fault"] = case
    data["case_id"], data["case_role"] = case, "raw_partial_capacity_failure"
    return data
''',
)

old = (BASE / "betse_ecm_grn_reference.py").read_text()
reference = old.replace(
    "def cold(inputs, *, refinement=1):", "def configuration(inputs, *, refinement=1):", 1
)
charged_text = (BASE / "betse_normal_charged_grn_join_reference.py").read_text()
compensation = next(
    ast.get_source_segment(charged_text, n)
    for n in ast.parse(charged_text).body
    if isinstance(n, ast.FunctionDef) and n.name == "compensation"
)
compensation = compensation.replace(
    "90 if refinement == 1 else 140", "100 if refinement == 1 else 160"
)
compensation = compensation.replace('net["grn_configuration"]', 'net["configuration"]')
compensation = compensation.replace('net["ion_boundary_mM"]', 'net["initial_ion_boundary"]')
compensation = compensation.replace('net["grn_initialization_publish"]', 'net["cold_publish"]')
compensation = compensation.replace(
    '        bath_volume = d(inputs["bath_volume_m3"])',
    """        e = inputs["environment_sites"]
        grid = derive_geometry(inputs["material_declaration"]["environment_geometry_definition"], precision=ctx.prec)
        site_volume = d(inputs["material_declaration"]["environment_geometry_definition"]["parameters"]["cell_height_m"]) * d(grid["delta_m"]) ** 2
        true_volume = [d(v) for v in grid["true_environment_volume_m3"]]""",
)
compensation = compensation.replace(
    "simulator = dict(extra_rho_cells=[Decimal(0)] * n, extra_J_mem=[Decimal(0)] * m)",
    """simulator = {key: [Decimal(0)] * size for key, size in (
            ("extra_rho_cells", n), ("extra_rho_env", e), ("extra_J_mem", m),
            ("extra_Jenv_x", e), ("extra_Jenv_y", e))}""",
)
compensation = compensation.replace('n if tag == "cell" else m', 'n if tag == "cell" else e')
start = compensation.index("            def env_amount(state, i=i):")
end = compensation.index("        cell_charge = [", start)
compensation = (
    compensation[:start]
    + """            def env_amount(state, i=i):
                return sum(state["cc_env"][i], Decimal(0)) * site_volume

            def native_diagnostic(state, i=i):
                return sum((v * vol for v, vol in zip(state["cc_env"][i], true_volume, strict=True)), Decimal(0))

            count_before[species] = dict(cell=amount(before), source_effective_environment=env_amount(before), native_true_volume_diagnostic=native_diagnostic(before))
            count_after[species] = dict(cell=amount(after), source_effective_environment=env_amount(after), native_true_volume_diagnostic=native_diagnostic(after))
            count_gross[species] = {k: abs(v) + abs(count_after[species][k]) for k,v in count_before[species].items()}
        gene_count = {}
        for row in net["configuration"]["biomolecules"]:
            gene_count[row["name"]] = dict(
                cell=d(row["cell conc"]) * sum(volume, Decimal(0)),
                source_effective_environment=d(row["env conc"]) * e * site_volume,
                native_true_volume_diagnostic=d(row["env conc"]) * sum(true_volume, Decimal(0)),
            )
"""
    + compensation[end:]
)
# Only environment-site loops change; membrane threshold capacity stays M-sized.
point = compensation.index("        env_charge = [")
compensation = compensation[:point] + compensation[point:].replace("range(m)", "range(e)", 1)
compensation = compensation.replace('[F * formal["env"]] * m', '[F * formal["env"]] * e')
helper = """

def cold_inputs(inputs):
    initial = inputs["initial"]
    external = inputs["definition"]["environment_geometry_definition"]
    current = external["current_definition"]
    return dict(mode="cold_initialization", network=inputs["network"],
        material_declaration=inputs["definition"], ion_ids=current["ions"]["ids"],
        valence=current["ions"]["valence"], cells=len(initial["cell_mol_m3"][0]),
        membranes=len(initial["voltage_V"]), environment_sites=len(initial["environment_mol_m3"][0]),
        ionic_state={key: initial[source] for key,source in (
            ("cc_cells","cell_mol_m3"),("cc_at_mem","membrane_mol_m3"),("cc_env","environment_mol_m3"))},
        F=current["parameters"]["F_C_mol"], cell_volume_m3=external["geometry"]["cell_volume_m3"])


def cold(inputs, *, refinement=1):
    result = compensation(inputs, refinement=refinement)
    if result["failure_case"] is None:
        fields = configuration(inputs, refinement=refinement)
        for key in ("molecule_fields", "reaction_matrix", "owner_fields", "independent_geometry"):
            result[key] = fields[key]
    return result

"""
point = reference.index("\ndef flatten_flux(")
reference = reference[:point] + "\n\n" + compensation + "\n" + helper + reference[point:]
emit("_reference.py", reference)
print("Emitted fixture recipe and independent ECM compensation reference; neither evaluated")
