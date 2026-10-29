"""Independent complete calcium/fuel INIT carry and explicit SIM bath operation."""

import ast
import hashlib
from copy import deepcopy
from itertools import product
from pathlib import Path

import numpy as np

from validation.tissue import open_calcium_bath_reference as scheduled
from validation.topology import surface_bath_phase_handoff_reference as legacy

REQUEST_KIND = "cells.open_calcium_bath_phase_handoff_request@1"
OWNERS = {
    "resolved_open_calcium_bath_epoch@1": "resolved_open_calcium_bath_events@1",
    "resolved_open_calcium_energy_bath_epoch@1": "resolved_open_calcium_energy_bath_events@1",
}
POLICIES = dict(
    operation="explicit_init_checkpoint_to_new_sim_epoch@1",
    state_policy="carry_all_owned_calcium_fuel_bath_nonclock_arrays_original_anchors@1",
    clock_policy="new_sim_clock_zero_archive_both_init_clocks@1",
    controller_policy="explicit_new_sim_initial_dose_electrode_charge_and_work@1",
    control_policy="new_zero_based_sim_controls_archive_complete_init_history@1",
    carried_pool_policy="actual_carried_pools_all_sim_controls_and_pulse_box_corners@1",
    ionic_domain_policy="actual_carried_ions_plus_sim_dose_hard_moiety_limits@1",
)
CAPACITIES = (
    "capacity",
    "extracellular_capacity",
    "membrane_capacity",
    "edge_capacity",
    "face_capacity",
    "channel_capacity",
    "chemical_capacity",
    "reaction_capacity",
    "field_solver",
    "max_steps",
    "max_trace_bytes",
)
digest, _typed = legacy.digest, legacy._typed
flatten, unpack = scheduled.flatten, scheduled.unpack
F_CHARGE = scheduled.F * 1e-15


def canonical_physical(raw):
    model = deepcopy(scheduled.static_definition(raw)["model"])
    cells = [row["id"] for row in model["ionic"]["cells"]]
    stores = {row["cell_id"]: row for row in model["stores"]}
    model["stores"] = [stores[name] for name in cells]
    if "energy_pools" in model:
        model["energy_pools"].sort(key=lambda row: cells.index(row["cell_id"]))
    for row in model["stores"]:
        store = row["model"]
        store["moieties"].sort()
        for key in ("species", "compartments", "reactions"):
            store[key].sort(key=lambda item: item["id"])
    return model


def target_definition(epoch):
    value = deepcopy(epoch)
    model = value["model"]
    if model["id"] not in OWNERS or model["scheduled"]["id"] != OWNERS[model["id"]]:
        raise ValueError("Require the exact full calcium/fuel bath epoch")
    value["model"] = model["scheduled"]
    return value


def state_geometry(raw, context):
    x = raw["execution"]
    routes = {
        "amount_increment": "capacity",
        "extracellular_amount_increment": "extracellular_capacity",
        "membrane_transferred": "membrane_capacity",
        "junction_transferred": "edge_capacity",
        "face_transferred": "face_capacity",
        "reservoir_supplied": "extracellular_capacity",
        "membrane_dissipated_energy_pJ": "membrane_capacity",
        "junction_dissipated_energy_pJ": "edge_capacity",
        "face_dissipated_energy_pJ": "face_capacity",
        "electrode_charge_transferred_C": "extracellular_capacity",
        "reservoir_work_pJ": "extracellular_capacity",
        "electrode_work_pJ": "extracellular_capacity",
        "channel_gate": "channel_capacity",
        "channel_transferred": "channel_capacity",
        "channel_dissipated_energy_pJ": "channel_capacity",
        "junction_gate": "edge_capacity",
        "pump_cycles": "membrane_capacity",
        "pump_dissipated_energy_pJ": "membrane_capacity",
        "metabolic_work_pJ": "membrane_capacity",
        "plasma_pump_cycles": "membrane_capacity",
        "plasma_exchange_cycles": "membrane_capacity",
        "plasma_dissipated_energy_pJ": "membrane_capacity",
        "calcium_gate": "membrane_capacity",
        "calcium_channel_transferred": "membrane_capacity",
        "calcium_channel_dissipated_energy_pJ": "membrane_capacity",
        "plasma_metabolic_work_pJ": "membrane_capacity",
        "energy_amount_increment_fmol": "capacity",
        "regeneration_cycles_fmol": "regeneration_capacity",
        "regeneration_dissipated_energy_pJ": "regeneration_capacity",
        "regeneration_supplied_work_pJ": "regeneration_capacity",
        "reservoir_chemical_work_pJ": "extracellular_capacity",
    }
    shapes, masks = {}, {}
    for name, compact in context["shapes"].items():
        shape = tuple(compact)
        if name == "chemical_amount_increment":
            shape = (*compact[:-1], x["chemical_capacity"])
        elif name in ("reaction_extent", "reaction_dissipated_energy_pJ"):
            shape = (*compact[:-1], x["reaction_capacity"])
        elif name in routes:
            shape = (*compact[:-1], x[routes[name]])
        if any(a < b for a, b in zip(shape, compact, strict=True)):
            raise ValueError("Insufficient full calcium/fuel state capacity")
        shapes[name] = shape
        masks[name] = np.zeros(shape, dtype=bool)
        masks[name][tuple(slice(0, size) for size in compact)] = True
    ion = raw["model"]["ionic"]
    reservoir = np.zeros(x["extracellular_capacity"], dtype=bool)
    reservoir[: len(ion["extracellular"])] = [row["reservoir"] for row in ion["extracellular"]]
    for name in (
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
        "reservoir_chemical_work_pJ",
    ):
        masks[name] &= reservoir
    masks["extracellular_amount_increment"] &= ~reservoir
    for j, row in enumerate(ion["channels"]):
        masks["channel_gate"][len(row["initial_gate"]) :, j] = False
    return shapes, masks


def validate_original_layout(record, raw, context):
    ion, x = raw["model"]["ionic"], raw["execution"]
    legacy.validate_original_layout(
        record, dict(raw, model=ion), dict(parent=context["controller"]["parent"])
    )
    original = context["parent"]
    base = original["calcium"] if original["finite_fuel"] else original
    n, capacity = len(base["stores"]), x["chemical_capacity"]
    amount = np.ones((n, base["stores"][0].n0.shape[0], capacity))
    volume = np.ones((n, capacity))
    active = np.zeros((n, capacity), dtype=bool)
    for i, store in enumerate(base["stores"]):
        width = store.n0.shape[1]
        amount[i, :, :width] = store.n0
        volume[i, :width] = store.volume
        active[i, :width] = True
    fixed = np.zeros((n, capacity))
    chemical_fixed = np.zeros_like(fixed)
    for i, store in enumerate(base["stores"]):
        incidence = np.zeros(capacity)
        incidence[store.cy], incidence[store.er] = -1.0, 1.0
        fixed[i] = store.cap * store.membrane["initial_voltage_V"] * incidence
        fixed[i] -= F_CHARGE * (store.z @ (amount[i] * active[i]))
        chemical_fixed[i] = fixed[i]
        chemical_fixed[i, store.cy] += base["qi"][i]
    expected = dict(
        er_initial_amount=amount,
        er_volume=volume,
        er_active=active,
        er_fixed_charge_C=fixed,
        chemical_fixed_charge_C=chemical_fixed,
        er_valence=np.asarray([store.z for store in base["stores"]], dtype=np.float64),
        er_standard_mu_RT=np.asarray([store.mu0 for store in base["stores"]], dtype=np.float64),
        er_initial_voltage=np.asarray(
            [store.membrane["initial_voltage_V"] for store in base["stores"]]
        ),
        er_capacitance=np.asarray([store.cap for store in base["stores"]]),
        open_reservoir_world=np.asarray(any(row["reservoir"] for row in ion["extracellular"])),
        open_ionic_moiety_ceiling_fmol=np.zeros(len(ion["species"]))
        if original["ionic_moiety_ceiling_fmol"] is None
        else np.asarray(original["ionic_moiety_ceiling_fmol"]),
    )
    if original["finite_fuel"]:
        pool = np.zeros((3, x["capacity"]))
        pool[:, : len(ion["cells"])] = original["energy_initial"]
        dg = np.zeros(x["capacity"])
        dg[: len(ion["cells"])] = original["energy_delta_g0"]
        expected.update(energy_initial_amount_fmol=pool, energy_delta_g0_J_mol=dg)
    for key, value in expected.items():
        try:
            actual = _typed(record[key], value.shape, value.dtype) if key in record else None
        except ValueError as error:
            saved = record.get(key)
            saved_shape = saved.get("shape") if isinstance(saved, dict) else None
            saved_dtype = saved.get("dtype") if isinstance(saved, dict) else None
            raise ValueError(
                f"Original full layout {key}: expected shape {list(value.shape)} "
                f"dtype {value.dtype.str}; saved shape {saved_shape} dtype {saved_dtype}: {error}"
            ) from error
        equal = actual is not None and (
            np.allclose(actual, value, rtol=0, atol=3e-25)
            if key in ("er_fixed_charge_C", "chemical_fixed_charge_C")
            else np.array_equal(actual, value)
        )
        if not equal:
            raise ValueError("Original full chemical/fuel anchor or domain changed: " + key)


def accepted_index(raw, time):
    # The existing exact union algorithm is reused on a read-only schedule-key
    # view; owned store controls use `controls` instead of `schedule`.
    value = deepcopy(raw)
    for name, groups in value["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                if "controls" in group:
                    group["schedule"] = group.pop("controls")
    return legacy.accepted_index(value, time)


def check_proof(proof):
    groups = (
        (
            3e-14,
            (
                "local_material_fmol",
                "outside_material_fmol",
                "chemical_ledger_fmol",
                "ionic_ownership_fmol",
                "nonionic_moiety_fmol",
                "ionic_global_fmol",
            ),
        ),
        (3e-25, ("capacitor_charge_C", "electrode_charge_C", "global_charge_C")),
        (
            1e-10,
            (
                "energy_residual_pJ",
                "reservoir_work_pJ",
                "electrode_work_pJ",
                "pool_energy_pJ",
                "program_energy_pJ",
            ),
        ),
        (2e-12, ("pool_material_fmol", "adenylate_fmol", "phosphorus_fmol")),
    )
    for limit, keys in groups:
        for key in keys:
            value = np.asarray(proof[key])
            if not np.isfinite(value).all() or np.max(np.abs(value), initial=0) > limit:
                raise ValueError("Inconsistent complete source history: " + key)


def admission(context, state, step):
    """Independent actual-carried state at every held control and pulse corner."""
    if not np.isfinite(step) or step < 0:
        raise ValueError("Carried-pool step must be finite and nonnegative")
    raw, parent = context["raw"], context["parent"]
    fields = unpack(context, state)
    initial = scheduled.owner.ionic_moieties(parent, flatten(parent, fields))
    coefficients = {}
    for event in raw["model"]["bath_events"]:
        if event["kind"] == "Cl_env" and not raw["model"]["enabled_Cl"]:
            continue
        ion = event["kind"].split("_")[0]
        for name in (ion, "Na" if ion == "Cl" else "M"):
            coefficients[name] = (event["kind"], event["amplitude"], ion)
    ionic = raw["model"]["ionic"]
    upper = initial.copy()
    for i, species in enumerate(ionic["species"]):
        if species["id"] in coefficients:
            _, amplitude, source = coefficients[species["id"]]
            upper[i] += sum(
                max(0, amplitude * row["initial_amount_fmol"][source])
                for row in ionic["extracellular"]
                if row["id"] in raw["model"]["bath_site_ids"]
            )
    limits = parent["ionic_moiety_ceiling_fmol"]
    if limits is not None and np.any(upper > limits):
        raise ValueError("Actual carried ions plus SIM dose exceed hard ionic-moiety ceilings")
    if not parent["finite_fuel"]:
        return dict(
            ionic_moiety_upper_fmol=upper, maximum_fraction_rate_s_inv=0.0, finite_fuel=False
        )
    amount = parent["energy_initial"] + fields["energy_amount_increment_fmol"]
    if not np.isfinite(amount).all() or np.any(amount <= 0):
        raise ValueError("Nonpositive actual carried ATP/ADP/Pi")
    events = [
        row
        for row in raw["model"]["bath_events"]
        if row["kind"] != "Cl_env" or raw["model"]["enabled_Cl"]
    ]
    clocks = sorted(
        {
            row["time"]
            for name, groups in raw["experiment"].items()
            if name.endswith("_controls")
            for group in groups
            for row in group.get("controls", group.get("schedule", []))
        }
    )
    maximum, worst = 0.0, None
    for bits in product((0.0, 1.0), repeat=len(events)):
        selected = {event["kind"]: bit for event, bit in zip(events, bits, strict=True)}
        current = deepcopy(context["static_definition"])
        for row in current["model"]["ionic"]["extracellular"]:
            if row["id"] not in raw["model"]["bath_site_ids"]:
                continue
            baseline = dict(row["initial_amount_fmol"])
            for species, (kind, amplitude, source) in coefficients.items():
                row["initial_amount_fmol"][species] += selected[kind] * amplitude * baseline[source]
        # Evaluate on an independent stage context carrying the real deltas.
        stage = scheduled.owner.bind(current)
        for time in clocks:
            vector = flatten(stage, fields)
            slope, _, _ = scheduled.owner.evaluate(stage, vector, time)
            rates = unpack(stage, slope)
            cells = [row["id"] for row in ionic["cells"]]
            gross = np.zeros(len(cells))
            for j, membrane in enumerate(ionic["membranes"]):
                i = cells.index(membrane["inside"])
                gross[i] += abs(rates["pump_cycles"][j]) + abs(rates["plasma_pump_cycles"][j])
            gross += np.abs(rates["er_pump_transferred"][:, 0])
            pools = {row["id"]: row for row in raw["model"]["energy_pools"]}
            for j, port in enumerate(raw["model"]["regeneration_ports"]):
                i = cells.index(pools[port["pool_id"]]["cell_id"])
                gross[i] += abs(rates["regeneration_cycles_fmol"][j])
            fraction = float(np.max(gross / np.min(amount, axis=0), initial=0))
            if fraction > maximum:
                maximum, worst = fraction, dict(pulses=selected, held_control_time_s=time)
    if not np.isfinite(maximum) or step * maximum > 0.05:
        raise ValueError("SIM step exceeds0.05 gross turnover of actual carried pools")
    return dict(
        ionic_moiety_upper_fmol=upper,
        finite_fuel=True,
        maximum_fraction_rate_s_inv=maximum,
        carried_amount_fmol=amount,
        worst=worst,
        corners=2 ** len(events),
        held_control_states=len(clocks),
    )


def bind(request):
    if (
        type(request) is not dict
        or set(request) != {"kind", "policies", "source", "simulation"}
        or request["kind"] != REQUEST_KIND
        or request["policies"] != POLICIES
    ):
        raise ValueError("Require explicit full calcium/fuel INIT/SIM policies")
    source = request["source"]
    if (
        type(source) is not dict
        or set(source) != {"definition", "checkpoint", "identity"}
        or digest({key: value for key, value in source.items() if key != "identity"})
        != source["identity"]
    ):
        raise ValueError("Complete typed source identity disagrees")
    raw, target = source["definition"], request["simulation"]
    if (
        raw["model"]["id"] != target["model"]["id"]
        or raw["model"]["phase"] != "INIT"
        or target["model"]["phase"] != "SIM"
    ):
        raise ValueError("Require exact ordinary full calcium/fuel INIT to SIM owners")
    if canonical_physical(raw) != canonical_physical(target):
        raise ValueError("Physical owners, original chemical/fuel anchors or hard ceilings changed")
    capacities = (
        (*CAPACITIES, "regeneration_capacity") if "energy_pools" in raw["model"] else CAPACITIES
    )
    if any(raw["execution"][key] != target["execution"][key] for key in capacities):
        raise ValueError("Physical capacities or resource quotas cannot change at handoff")
    original, current = scheduled.bind(raw), scheduled.bind(target)
    point = source["checkpoint"]
    if set(point) != {"time", "step_index", "event_index", "state", "layout"}:
        raise ValueError("Incomplete full calcium/fuel checkpoint")
    shapes, masks = state_geometry(raw, original)
    arrays = legacy.decode_state(point["state"], shapes, masks)
    scheduled.owner.validate_padded_state(
        original["parent"], {key: arrays[key] for key in original["parent"]["shapes"]}
    )
    for key in ("channel_gate", "junction_gate", "calcium_gate"):
        if np.any((arrays[key] < 0) | (arrays[key] > 1)):
            raise ValueError("Carried physical gate is outside its domain")
    validate_original_layout(point["layout"], raw, original)
    step, event = accepted_index(raw, point["time"])
    if (
        type(point["step_index"]) is not int
        or point["step_index"] != step
        or type(point["event_index"]) is not int
        or point["event_index"] != event
    ):
        raise ValueError("Source accepted clock/control position disagrees")
    allowance = (
        64 * np.finfo(float).eps * max(raw["execution"]["dt"], raw["experiment"]["end_time"])
    )
    if abs(arrays["phase_clock_s"][0] - point["time"]) > allowance:
        raise ValueError("Source phase clock differs from accepted checkpoint time")
    vector = flatten(original, arrays)
    if step == 0 and not np.array_equal(vector, scheduled.initial(original)):
        raise ValueError("Initial source rewrites declared histories or gates")
    scheduled.evaluate(original, vector, held_time=point["time"])
    proof = scheduled.conservation(original, vector)
    check_proof(proof)
    carried = {key: value.copy() for key, value in arrays.items()}
    carried["phase_clock_s"] = np.zeros(1)
    current.update(
        source_context=original,
        source_arrays=arrays,
        carried_arrays=carried,
        source_time_s=point["time"],
        source_phase_clock_s=float(arrays["phase_clock_s"][0]),
        padded_shapes=shapes,
        active_masks=masks,
        source_proof=proof,
        simulation=deepcopy(target),
    )
    current["carried_admission"] = admission(
        current,
        flatten(current, carried),
        min(target["execution"]["dt"], target["experiment"]["end_time"]),
    )
    return current


def initial(request):
    context = bind(request)
    return context, flatten(context, context["carried_arrays"])


def evaluate(context, state, *, held_time=None):
    return scheduled.evaluate(context, state, held_time=held_time)


def conservation(context, state):
    return scheduled.conservation(context, state)


def operation(context):
    return scheduled.program(context, 0.0)


def verify_epoch(epoch):
    target = target_definition(epoch)
    record = epoch["model"]["handoff"]
    if set(record) != {*POLICIES, "source", "clocks", "controller_operation", "carried_admission"}:
        raise ValueError("Incomplete complete-calcium/fuel bath epoch")
    context, state = initial(
        dict(
            kind=REQUEST_KIND,
            policies={key: record[key] for key in POLICIES},
            source=record["source"],
            simulation=target,
        )
    )
    expected_clocks = dict(
        init_checkpoint_time_s=context["source_time_s"],
        init_phase_clock_s=context["source_phase_clock_s"],
        sim_epoch_time_s=0.0,
        sim_phase_clock_s=0.0,
    )
    if record["clocks"] != expected_clocks:
        raise ValueError("Archived full INIT/SIM clocks disagree")
    op = record["controller_operation"]
    keys = {
        "kind",
        "time_s",
        "original_parent_definition_digest",
        "native_bath_binding_identities",
        "bath_site_ids",
        "dose_fmol",
        "charge_C",
        "chemical_work_pJ",
        "electrochemical_work_pJ",
        "electrode_charge_C",
        "electrode_work_pJ",
        "accounting",
        "identity",
    }
    if set(op) != keys:
        raise ValueError("Incomplete explicit SIM controller operation")
    if (
        op["kind"] != "cells.surface_bath_initial_controller_operation@1"
        or op["time_s"] != 0.0
        or digest({key: value for key, value in op.items() if key != "identity"}) != op["identity"]
        or op["original_parent_definition_digest"] != digest(scheduled.static_definition(target))
    ):
        raise ValueError("Initial SIM operation or original anchor digest disagrees")
    model, ionic = target["model"], target["model"]["ionic"]
    if (
        op["bath_site_ids"] != model["bath_site_ids"]
        or op["accounting"]
        != "additive initial controller operation against unchanged original anchors"
    ):
        raise ValueError("Initial controller owners or accounting policy changed")
    expected_bindings = []
    for name in model["bath_site_ids"]:
        j = next(i for i, row in enumerate(ionic["extracellular"]) if row["id"] == name)
        parent = context["controller"]["parent"]
        expected_bindings.append(
            digest(
                dict(
                    grid=digest(dict(species=[row["id"] for row in ionic["species"]], site=name)),
                    events=model["bath_events"],
                    baseline=(parent["ao"][:, j] / parent["vo"][j]).tolist(),
                    is_ecm=True,
                    enabled_Cl=model["enabled_Cl"],
                )
            )
        )
    if op["native_bath_binding_identities"] != expected_bindings:
        raise ValueError("Initial operation native bath bindings changed")
    expected = operation(context)
    for key in (
        "dose_fmol",
        "charge_C",
        "chemical_work_pJ",
        "electrochemical_work_pJ",
        "electrode_work_pJ",
    ):
        actual = np.asarray(op[key])
        value = expected[key]
        padded = np.pad(value, [(0, a - b) for a, b in zip(actual.shape, value.shape, strict=True)])
        if not np.allclose(actual, padded, rtol=5e-13, atol=3e-25 if key.endswith("_C") else 3e-12):
            raise ValueError("Explicit SIM dose/charge/work disagrees: " + key)
    if not np.allclose(op["electrode_charge_C"], -np.asarray(op["charge_C"]), rtol=0, atol=3e-25):
        raise ValueError("SIM electrode compensation disagrees")
    if not np.allclose(
        record["carried_admission"]["ionic_moiety_upper_fmol"],
        context["carried_admission"]["ionic_moiety_upper_fmol"],
        rtol=3e-13,
        atol=3e-12,
    ):
        raise ValueError("Actual carried ionic envelope witness disagrees")
    actual = record["carried_admission"]["pool_turnover"]
    expected_pool = context["carried_admission"]
    if (
        record["carried_admission"]["step_s"]
        != min(target["execution"]["dt"], target["experiment"]["end_time"])
        or actual["finite_fuel"] != expected_pool["finite_fuel"]
    ):
        raise ValueError("Actual carried admission step or fuel identity changed")
    if expected_pool["finite_fuel"]:
        if not np.allclose(
            actual["carried_amount_fmol"], expected_pool["carried_amount_fmol"], rtol=0, atol=2e-12
        ) or not np.isclose(
            actual["maximum_fraction_rate_s_inv"],
            expected_pool["maximum_fraction_rate_s_inv"],
            rtol=3e-10,
            atol=3e-12,
        ):
            raise ValueError("Actual carried pool witness was replaced by original initial fuel")
    return context, state


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
