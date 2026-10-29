"""Independent scheduled baths, complete calcium/fuel equations and budgets.

The ordered Decimal bath setter and full open-owned reference are reused.
Only rate-input views receive prescribed reservoir inventories; conservation
always uses the unchanged original five/four-ion model and its actual ledgers.
No Cells/JAX imports, background mutation, finite-amount floors or pool rebasing.
"""

import ast
import hashlib
import math
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from validation.tissue import open_calcium_reference as owner
from validation.transport import surface_bath_events_reference as bath

F, R = owner.F, owner.R
MODEL_IDS = {
    "resolved_open_calcium_bath_events@1": "resolved_open_calcium@1",
    "resolved_open_calcium_energy_bath_events@1": "resolved_open_calcium_energy@1",
}
EXTERIOR_POLICY = "scheduled_declared_ideal_chemical_and_fixed_voltage_reservoirs@1"
flatten, unpack = owner.flatten, owner.unpack


def static_definition(raw):
    value = deepcopy(raw)
    value["model"]["id"] = MODEL_IDS[value["model"]["id"]]
    value["model"]["exterior_policy"] = "static_declared_ideal_chemical_and_voltage_reservoirs@1"
    for key in bath.EXTRA:
        value["model"].pop(key)
    return value


def bind(raw):
    m = raw["model"]
    if m.get("id") not in MODEL_IDS or m.get("exterior_policy") != EXTERIOR_POLICY:
        raise ValueError("Require the explicit scheduled owned-calcium bath identity/policy")
    static = static_definition(raw)
    parent = owner.bind(static)
    ionic = deepcopy(m["ionic"])
    ionic.update(
        id="resolved_active_bath_events@1", **{key: deepcopy(m[key]) for key in bath.EXTRA}
    )
    controller = bath.bind(dict(raw, model=ionic))
    context = dict(
        raw=deepcopy(raw),
        static_definition=static,
        parent=parent,
        controller=controller,
        shapes=parent["shapes"]
        | dict(reservoir_chemical_work_pJ=(len(ionic["extracellular"]),), phase_clock_s=(1,)),
    )
    # Derive the final-writer initial pulse box independently of production.
    coefficients = {
        row["id"]: {species["id"]: 0.0 for species in ionic["species"]}
        for row in ionic["extracellular"]
    }
    if m["phase"] == "SIM":
        for event in m["bath_events"]:
            if event["kind"] == "Cl_env" and not m["enabled_Cl"]:
                continue
            ion = event["kind"].split("_")[0]
            other = "Na" if ion == "Cl" else "M"
            for row in ionic["extracellular"]:
                if row["id"] in m["bath_site_ids"]:
                    amount = event["amplitude"] * row["initial_amount_fmol"][ion]
                    coefficients[row["id"]][ion] = coefficients[row["id"]][other] = amount
    limit = parent["ionic_moiety_ceiling_fmol"]
    if limit is not None:
        upper = owner.ionic_moieties(parent, owner.initial(parent))
        for i, species in enumerate(ionic["species"]):
            upper[i] += sum(max(0, row[species["id"]]) for row in coefficients.values())
        if np.any(upper > limit):
            raise ValueError("Bath pulse envelope exceeds declared hard ionic-moiety ceilings")
    return context


def initial(context):
    return np.r_[
        owner.initial(context["parent"]),
        np.zeros(context["shapes"]["reservoir_chemical_work_pJ"]),
        0.0,
    ]


def program(context, time):
    return bath.program(context["controller"], time)


def current_context(context, time, held_time):
    raw = deepcopy(context["static_definition"])
    signal = program(context, time)
    ionic = raw["model"]["ionic"]
    for j, row in enumerate(ionic["extracellular"]):
        for i, species in enumerate(ionic["species"]):
            row["initial_amount_fmol"][species["id"]] += signal["dose_fmol"][i, j]
    # This is an independent rate-argument view. Its fixed background and all
    # intracellular/store/pool anchors are bit-identical to the original model.
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                held = deepcopy(
                    next(row for row in reversed(group[key]) if row["time"] <= held_time)
                )
                held["time"] = 0.0
                group[key] = [held]
    return owner.bind(raw), signal


def evaluate(context, state, *, held_time=None):
    fields = unpack(context, state)
    time = float(fields["phase_clock_s"][0])
    raw = context["raw"]
    allowance = (
        64 * np.finfo(float).eps * max(raw["experiment"]["end_time"], raw["execution"]["dt"])
    )
    if not np.isfinite(state).all() or not 0 <= time <= raw["experiment"]["end_time"] + allowance:
        raise ValueError("Invalid full owned-calcium bath state/clock")
    held_time = time if held_time is None else held_time
    current, signal = current_context(context, time, held_time)
    vector = flatten(current, fields)
    slope, phi, proof = owner.evaluate(current, vector, held_time)
    derivative = unpack(current, slope)
    physical = current["calcium"] if current["finite_fuel"] else current
    chemical = (
        1e-3
        * R
        * physical["layout"]["temperature"]
        * np.sum(np.log(physical["ao"] / physical["vo"]) * derivative["reservoir_supplied"], axis=0)
    )
    values = dict(derivative, reservoir_chemical_work_pJ=chemical, phase_clock_s=np.ones(1))
    return (
        flatten(context, values),
        phi,
        proof
        | dict(
            program=signal,
            physical_reservoir_supply_fmol_s=np.asarray(proof["reservoir_supply_fmol_s"])
            + signal["dose_rate_fmol_s"],
            physical_electrode_current_A=np.asarray(proof["electrode_current_A"])
            - signal["charge_rate_A"],
            physical_chemical_power_pJ_s=proof["chemical_power_pJ_s"]
            + signal["chemical_power_pJ_s"].sum(),
            physical_reservoir_power_pJ_s=proof["reservoir_power_pJ_s"]
            + signal["electrochemical_power_pJ_s"].sum(),
            physical_electrode_power_pJ_s=proof["electrode_power_pJ_s"]
            + signal["electrode_power_pJ_s"].sum(),
        ),
    )


def physical_fields(context, state):
    values = {key: np.array(value, copy=True) for key, value in unpack(context, state).items()}
    signal = program(context, float(values["phase_clock_s"][0]))
    values["extracellular_amount_increment"] += signal["dose_fmol"]
    values["reservoir_supplied"] += signal["dose_fmol"]
    values["electrode_charge_transferred_C"] -= signal["charge_C"]
    values["reservoir_work_pJ"] += signal["electrochemical_work_pJ"]
    values["electrode_work_pJ"] += signal["electrode_work_pJ"]
    values["reservoir_chemical_work_pJ"] += signal["chemical_work_pJ"]
    return values


def conservation(context, state):
    values = unpack(context, state)
    parent = context["parent"]
    transport = flatten(parent, values)
    proof = owner.conservation(parent, transport)
    signal = program(context, float(values["phase_clock_s"][0]))
    ionic = context["raw"]["model"]["ionic"]
    with localcontext() as ctx:
        ctx.prec = 80
        scale = bath.decimal(F) * Decimal("1e-15")
        work, compensation, program_energy = [], [], []
        for j, row in enumerate(ionic["extracellular"]):
            supplied_charge = scale * sum(
                (
                    bath.decimal(species["valence"])
                    * bath.decimal(values["reservoir_supplied"][i, j])
                    for i, species in enumerate(ionic["species"])
                ),
                Decimal(0),
            )
            programmed_charge = scale * sum(
                (
                    bath.decimal(species["valence"]) * bath.decimal(signal["dose_fmol"][i, j])
                    for i, species in enumerate(ionic["species"])
                ),
                Decimal(0),
            )
            compensation.append(float(programmed_charge - bath.decimal(signal["charge_C"][j])))
            work.append(
                float(
                    bath.decimal(values["reservoir_work_pJ"][j])
                    - bath.decimal(values["reservoir_chemical_work_pJ"][j])
                    - Decimal("1e12") * bath.decimal(row["boundary_potential_V"]) * supplied_charge
                )
            )
            program_energy.append(
                float(
                    bath.decimal(signal["chemical_work_pJ"][j])
                    - bath.decimal(signal["electrochemical_work_pJ"][j])
                    - bath.decimal(signal["electrode_work_pJ"][j])
                )
            )
    # Material dose enters outside inventory and supplied material equally.
    # Keeping those two original additive terms separate preserves small
    # transport residuals instead of rounding them away beside a large dose.
    return proof | dict(
        reservoir_work_pJ=np.asarray(work),
        electrode_charge_C=proof["electrode_charge_C"] + np.asarray(compensation),
        global_charge_C=proof["global_charge_C"] + math.fsum(compensation),
        energy_residual_pJ=proof["energy_residual_pJ"] + math.fsum(program_energy),
        chemical_change_pJ=proof["chemical_change_pJ"] + signal["chemical_work_pJ"].sum(),
        external_work_pJ=proof["external_work_pJ"]
        + (signal["electrochemical_work_pJ"] + signal["electrode_work_pJ"]).sum(),
        program_energy_pJ=np.asarray(program_energy),
        actual_ionic_moiety_fmol=owner.ionic_moieties(parent, transport)
        + signal["dose_fmol"].sum(axis=-1),
        original_anchor_policy=(
            "original complete physical definition; additive bath work/material/charge"
        ),
    )


def dependency_manifest(root):
    """Audit the actual module closure, own bodies, legacy helpers and package."""
    root = Path(root).resolve()
    pending, seen = [Path(__file__).resolve()], {}
    while pending:
        path = pending.pop()
        relative = str(path.relative_to(root))
        if relative in seen:
            continue
        source = path.read_bytes()
        tree = ast.parse(source)
        legacy = path.parent == root / "tests" and path.name.startswith("reference_")
        package = path == root / "tests/__init__.py"
        if package and any(
            not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            for node in tree.body
        ):
            raise ValueError("Reference package initializer must contain documentation only")
        if not path.is_relative_to(root / "validation") and not legacy and not package:
            raise ValueError("Non-reference dependency: " + relative)
        seen[relative] = hashlib.sha256(source).hexdigest()
        parents = {
            child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            parent, nested = parents.get(node), False
            while parent is not None:
                nested |= isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                parent = parents.get(parent)
            if nested and path != Path(__file__).resolve() and not legacy:
                continue
            if isinstance(node, ast.Import):
                names = [value.name for value in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    parts = list(path.relative_to(root).with_suffix("").parts[:-1])
                    module = ".".join(parts[: len(parts) - node.level + 1]) + (
                        "." + module if module else ""
                    )
                names = [module, *(module + "." + value.name for value in node.names)]
            else:
                continue
            for name in names:
                if name.split(".")[0] in {"cells", "jax", "jaxlib"}:
                    raise ValueError(
                        "Production/JAX import in independent bath reference: " + relative
                    )
                candidate = root.joinpath(*name.split("."))
                for local in (candidate.with_suffix(".py"), candidate / "__init__.py"):
                    if local.is_file():
                        pending.append(local.resolve())
    return dict(sorted(seen.items()))
