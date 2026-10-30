# ruff: noqa: E501 -- emitted source templates; final files are formatted separately.
"""Emit charged fixtures and independent cold equations without evaluating either."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = ROOT / "validation/betse"

fixture = (BASE / "betse_normal_grn_join_fixtures.py").read_text()
fixture = fixture[: fixture.index("\ndef raw_fixture(")]
fixture = fixture.replace("CASES = (", "TEMPLATE_CASES = (", 1)
fixture = fixture.replace("COMPONENT_CONTROLS = (", "TEMPLATE_CONTROLS = (", 1)
start, end = fixture.index("RAW_CASES = ("), fixture.index("\n\ndef fixture(")
fixture = fixture[:start] + fixture[end:]
fixture = fixture.replace('def fixture(case="regulated"):', 'def _template(case="regulated"):')
fixture = fixture.replace("case not in CASES", "case not in TEMPLATE_CASES")
fixture = fixture.replace("case in COMPONENT_CONTROLS", "case in TEMPLATE_CONTROLS")
fixture += """

CASES = (
    "positive", "negative", "zero_charge_control", "compensation_off",
    "runtime_publish_off", "negative_threshold_gap", "source_defaults",
    "growth_off", "no_modulators", "temperature_split", "time_dilation",
    "scaled_charge",
)
COMPONENT_CONTROLS = ("zero_charge_control", "compensation_off", "growth_off")
RAW_CASES = (
    "cell_positive_excess", "cell_negative_excess",
    "env_positive_excess", "env_negative_excess",
)
DEPENDENCIES = (
    "missing_M", "wrong_M_valence", "missing_ionic_cache",
    "missing_balance_events", "missing_source_default", "wrong_owner",
)


def fixture(case="positive"):
    if case not in CASES:
        raise ValueError("Choose a declared charged GRN case")
    data = _template({"runtime_publish_off": "publish_off", "growth_off": "no_growth"}.get(
        case, case if case in TEMPLATE_CASES else "regulated"))
    # A real sixth, stationary M(-1) ion is supplied by this caller. Subtracting
    # the same amount from the pre-existing P(-1) inputs retains their combined
    # nominal charge. This is a manufactured input recipe, not a source repair.
    ion = data["ion_definition"]["ions"]
    original_ids = list(ion["ids"])
    for definition in (data["ion_definition"], data["current_definition"]):
        definition["ions"]["ids"] = original_ids + ["M"]
        definition["ions"]["valence"] = list(definition["ions"]["valence"]) + [-1.0]
    for key in ("membrane_diffusion_m2_s", "gap_diffusion_m2_s"):
        ion[key] = list(ion[key]) + [[0.0] * 9]
    voltage = data["voltage_definition"]["ions"]
    voltage["free_diffusion_m2_s"] = list(voltage["free_diffusion_m2_s"]) + [0.0]
    gap = case == "negative_threshold_gap"
    for key, value in (("cell_mol_m3", 0.5e-6 if gap else 1e-4),
                       ("membrane_mol_m3", 2e-6 if gap else 1e-4),
                       ("bath_mol_m3", 1e-4),
                       ("membrane_flux_mol_m2_s", 0.0),
                       ("junction_flux_mol_m2_s", 0.0)):
        width = 3 if key == "cell_mol_m3" else 9
        data["initial"][key] = list(data["initial"][key]) + [[value] * width]
        if key in ("cell_mol_m3", "membrane_mol_m3", "bath_mol_m3"):
            p = original_ids.index("P")
            data["initial"][key][p] = [v - value for v in data["initial"][key][p]]
    definition = data["channel_definition"]
    definition["kind"] = "cells.betse_normal_charged_grn_join_inputs@1"
    net = definition["network"]
    z = -1.0 if case in ("negative", "negative_threshold_gap") else 0.0 if case == "zero_charge_control" else 1.0
    scale = 2e-6 if case == "scaled_charge" else 1e-6
    for config, row in zip(net["grn_configuration"]["biomolecules"], net["molecules"], strict=True):
        config.update({"z": z, "scale factor": scale})
        row["parameters"].update(z=z, scale_factor=scale)
        row["provenance"] = "Manufactured charged product; formal charge scale, no physiological calibration"
    net["ion_boundary_mM"] = [row[0] for row in data["initial"]["bath_mol_m3"]]
    net["grn_initialization_publish"] = case != "compensation_off"
    net["provenance"] = "Actual charged MasterOfGenes/Core lifecycle and normal dispatch; real M(-1) compensation row"
    data["charged_grn_case_id"] = data.pop("grn_case_id")
    data["charged_grn_case_id"] = case
    data["case_role"] = "component_control" if case in COMPONENT_CONTROLS else "new_charged_grn_case"
    data["counterion_input_recipe"] = dict(
        actual_M_row=True, stationary_M=True,
        P_decrement_equals_supplied_M=True,
        membrane_cache_independent_from_bulk=gap,
        biological_calibration=False,
    )
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared cold charge capacity refusal")
    data = fixture("negative" if "negative" in case else "positive")
    net = data["channel_definition"]["network"]
    for config, row in zip(net["grn_configuration"]["biomolecules"], net["molecules"], strict=True):
        scale = 1.0 if case == "cell_positive_excess" else 1e-6
        cell = 200.0 if case.startswith("cell_") else config["cell conc"]
        env = (2e8 if "positive" in case else 200.0) if case.startswith("env_") else config["env conc"]
        config.update({"cell conc": cell, "env conc": env, "scale factor": scale})
        row["parameters"].update(c_bound=env, scale_factor=scale)
        row["initial"].update(c_cells=[cell] * 3, cc_at_mem=[cell] * 9, c_env=[env] * 9)
    net["raw_initialization_fault"] = case
    data["drives"] = data["drives"][:1]
    data["charged_grn_case_id"], data["case_role"] = case, "raw_partial_failure"
    return data
"""
with (BASE / "betse_normal_charged_grn_join_fixtures.py").open("x") as stream:
    stream.write(fixture)

reference = (BASE / "betse_normal_grn_join_reference.py").read_text()
reference = reference.replace(
    "def cold(inputs, *, refinement=1):", "def configuration(inputs, *, refinement=1):"
)
reference = reference.replace(
    "scale_factor=d(1),", 'scale_factor=d(row.get("scale factor", 1)),', 1
)
point = reference.index("\ndef warm(")
reference = (
    reference[:point]
    + '''

def compensation(inputs, *, refinement=1):
    """Independent charge/count accounting from immutable pre-constructor inputs.

    Decimal computes the physical quantities. An explicitly stored primitive
    binary64 sum independently describes the source's scalar charge/branch
    semantics; no native/model output is used and no trajectory is carried.
    """
    if refinement not in (1, 2) or inputs["mode"] != "cold_initialization":
        raise ValueError("Require charged inputs before owner construction")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        net, ids = inputs["network"], inputs["ion_ids"]
        before = {k: [[d(v) for v in row] for row in rows] for k, rows in inputs["ionic_state"].items()}
        after = copy.deepcopy(before)
        bound = list(map(d, net["ion_boundary_mM"]))
        F = d(inputs["F"])
        n, m = inputs["cells"], inputs["membranes"]
        volume = list(map(d, inputs["cell_volume_m3"]))
        bath_volume = d(inputs["bath_volume_m3"])
        valence = list(map(d, inputs["valence"]))
        formal, source_q, charge_gross = {}, {}, {}
        for region, key in (("cell", "cell conc"), ("env", "env conc")):
            total, rounded, gross = Decimal(0), 0.0, Decimal(0)
            for row in net["grn_configuration"]["biomolecules"]:
                term = d(row[key]) * d(row["z"]) * d(row.get("scale factor", 1.0))
                total += term
                gross += abs(term)
                first = float(float(row[key]) * float(row["z"]))
                term64 = float(first * float(row.get("scale factor", 1.0)))
                rounded = float(rounded + term64)
            formal[region], source_q[region], charge_gross[region] = total, d(rounded), gross
        simulator = dict(extra_rho_cells=[Decimal(0)] * n, extra_J_mem=[Decimal(0)] * m)
        stages, actions, failure = [], {}, None
        published = net["grn_initialization_publish"]
        if published:
            for tag, array in (("cell", "cc_cells"), ("env", "cc_env")):
                q = source_q[tag]
                stages.append(dict(stage="before", tag=tag, Q=q))
                species = "M" if q < 0 else "K" if tag == "cell" else "Na"
                index = ids.index(species)
                capacity = sum(before[array][index], Decimal(0)) / len(before[array][index])
                refusal_capacity = (sum(before["cc_at_mem"][index], Decimal(0)) / m
                                    if tag == "cell" and q < 0 else capacity)
                if q != 0 and abs(q) <= capacity:
                    after[array][index] = [v - abs(q) for v in before[array][index]]
                    if tag == "env":
                        bound[index] -= abs(q)
                    actions[tag] = dict(action="remove", species=species, source_Q=q,
                                        admission_capacity=capacity, refusal_capacity=refusal_capacity)
                elif q != 0 and abs(q) > refusal_capacity:
                    failure = tag + ("_negative_excess" if q < 0 else "_positive_excess")
                    actions[tag] = dict(action="refuse", species=species, source_Q=q,
                                        admission_capacity=capacity, refusal_capacity=refusal_capacity)
                    break
                else:
                    actions[tag] = dict(action="zero" if q == 0 else "negative_threshold_gap",
                                        species=None, source_Q=q,
                                        admission_capacity=capacity, refusal_capacity=refusal_capacity)
                simulator["extra_rho_cells" if tag == "cell" else "extra_rho_env"] = [F * q] * (n if tag == "cell" else m)
                stages.append(dict(stage="after", tag=tag, Q=q))
        else:
            actions = {tag: dict(action="disabled", species=None, source_Q=source_q[tag]) for tag in ("cell", "env")}
        count_before, count_after, count_gross = {}, {}, {}
        for i, species in enumerate(ids):
            def amount(state):
                return sum((v * volume[j] for j, v in enumerate(state["cc_cells"][i])), Decimal(0))
            def env_amount(state):
                return sum(state["cc_env"][i], Decimal(0)) / m * bath_volume
            count_before[species] = dict(cell=amount(before), declared_single_bath=env_amount(before), source_effective_bath=m * env_amount(before))
            count_after[species] = dict(cell=amount(after), declared_single_bath=env_amount(after), source_effective_bath=m * env_amount(after))
            count_gross[species] = {k: abs(v) + abs(count_after[species][k]) for k, v in count_before[species].items()}
        cell_charge = [F * sum((valence[i] * (after["cc_cells"][i][j] - before["cc_cells"][i][j]) for i in range(len(ids))), Decimal(0)) for j in range(n)]
        env_charge = [F * sum((valence[i] * (after["cc_env"][i][j] - before["cc_env"][i][j]) for i in range(len(ids))), Decimal(0)) for j in range(m)]
        charge_ledger = dict(
            cell_ionic_charge_change_C_m3=cell_charge,
            env_ionic_charge_change_C_m3=env_charge,
            formal_gene_cell_charge_C_m3=[F * formal["cell"]] * n,
            formal_gene_env_charge_C_m3=[F * formal["env"]] * m,
            cell_ionic_plus_formal_change_C_m3=[v + F * formal["cell"] for v in cell_charge],
            env_ionic_plus_formal_change_C_m3=[v + F * formal["env"] for v in env_charge],
        )
        return plain(dict(
            ionic_state=after, ion_boundary_state=bound, simulator_fields=simulator,
            formal_gene_charge_mM=formal, source_Q_mM=source_q,
            source_Q_gross_mM=charge_gross, actions=actions, balance_stages=stages,
            failure_case=failure, source_exception=None if failure is None else "BetseSimConfException",
            charge_has_been_balanced=published and failure is None,
            ionic_count_before_mol=count_before, ionic_count_after_mol=count_after,
            ionic_count_change_mol={s: {k: count_after[s][k] - v for k, v in row.items()} for s, row in count_before.items()},
            ionic_count_gross_mol=count_gross, charge_ledger=charge_ledger,
            ionic_membrane_cache_refreshed=False,
            counterion_removal_is_material_sink=True,
            boundary_value_is_not_reservoir_inventory=True,
            physical_conservation_credit=False, energetic_conservation_credit=False,
            source_compensation_only=True, cold_initialization=True,
            decimal_precision=ctx.prec, carried_reference_forms=0,
            fresh_conditional_reference=True,
        ))


def cold(inputs, *, refinement=1):
    result = compensation(inputs, refinement=refinement)
    if result["failure_case"] is None:
        fields = configuration(inputs, refinement=refinement)
        for key in ("molecule_fields", "reaction_matrix", "owner_fields"):
            result[key] = fields[key]
    return result
'''
    + reference[point:]
)
with (BASE / "betse_normal_charged_grn_join_reference.py").open("x") as stream:
    stream.write(reference)
print({"emitted_without_evaluating": 2})
