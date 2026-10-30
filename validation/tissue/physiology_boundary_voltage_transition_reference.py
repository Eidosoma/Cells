"""Independent raw-owner Decimal capacitor constraints and path work histories.

No Cells/JAX imports or production matrices, slot maps, seals or ramp algebra.
The existing independent full-node ordinary oracle admits held endpoints.
"""

import hashlib
import json
from decimal import Decimal, localcontext

from validation.tissue import physiology_boundary_voltage_reference as held

LAW = "ideal_fixed_inventory_linear_capacitive_ramp@1"
DECLARATION = "cells.physiology_boundary_voltage_ramp_declaration@1"


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def d(value):
    return Decimal.from_float(float(value))


def _solve(matrix, rhs):
    """100-digit pivoted elimination; no production solve or floating matrix."""
    n = len(rhs)
    augmented = [list(row) + [value] for row, value in zip(matrix, rhs, strict=True)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda j: abs(augmented[j][i]))
        if not augmented[pivot][i]:
            raise ValueError("Independent ideal capacitor constraints are singular")
        augmented[i], augmented[pivot] = augmented[pivot], augmented[i]
        scale = augmented[i][i]
        augmented[i] = [value / scale for value in augmented[i]]
        for j in range(n):
            if j == i:
                continue
            scale = augmented[j][i]
            augmented[j] = [a - scale * b for a, b in zip(augmented[j], augmented[i], strict=True)]
    return [row[-1] for row in augmented]


def _increment(model, delta_b):
    cells = [row["id"] for row in model["cells"]]
    outside = [row["id"] for row in model["extracellular"]]
    n = len(cells)
    count = n + len(outside)
    matrix = [[Decimal(0) for _ in range(count)] for _ in range(count)]
    adjacency = [set() for _ in range(count)]
    for patch in model["membranes"]:
        i, j = cells.index(patch["inside"]), n + outside.index(patch["outside"])
        capacitance = d(patch["capacitance_F"])
        matrix[i][i] += capacitance
        matrix[j][j] += capacitance
        matrix[i][j] -= capacitance
        matrix[j][i] -= capacitance
        adjacency[i].add(j)
        adjacency[j].add(i)
    fixed = {n + i: delta_b[i] for i, row in enumerate(model["extracellular"]) if row["reservoir"]}
    unseen = set(range(count))
    while unseen:
        group, todo = set(), [min(unseen)]
        while todo:
            item = todo.pop()
            if item in group:
                continue
            group.add(item)
            todo.extend(adjacency[item] - group)
        unseen -= group
        if not group.intersection(fixed):
            # A different representative from production's outside pin is valid.
            fixed[min(group)] = Decimal(0)
    free = [i for i in range(count) if i not in fixed]
    rhs = [-sum((matrix[i][j] * value for j, value in fixed.items()), Decimal(0)) for i in free]
    answer = _solve([[matrix[i][j] for j in free] for i in free], rhs)
    potential = [Decimal(0) for _ in range(count)]
    for i, value in fixed.items():
        potential[i] = value
    for i, value in zip(free, answer, strict=True):
        potential[i] = value
    node = [sum((a * b for a, b in zip(row, potential, strict=True)), Decimal(0)) for row in matrix]
    return potential, node


def _boundary(model, binding, memory):
    original = {row["id"]: d(row["boundary_potential_V"]) for row in model["extracellular"]}
    written = {}
    for side, owners in binding["boundary_reservoir_ids"]:
        value = d(memory[held.SIDES.index(side)])
        for name in owners:
            if name in written and written[name] != value:
                raise ValueError("Independent ramp corner conflict")
            written[name] = value
    return [written.get(row["id"], original[row["id"]]) for row in model["extracellular"]]


def evaluate(raw, fields, binding_record, held_control, numeric_time_s, declarations):
    model = raw["model"].get("ionic", raw["model"])
    original = {row["id"]: row["boundary_potential_V"] for row in model["extracellular"]}
    memory = []
    for _, owners in binding_record["boundary_reservoir_ids"]:
        values = [original[name] for name in owners]
        if values and any(value != values[0] for value in values):
            raise ValueError("Inconsistent independent initial side memory")
        memory.append(values[0] if values else 0.0)
    oracle = held.ORACLES[raw["model"]["id"]]

    def endpoint(side_memory):
        _, effective, _ = held.reconstruct(
            raw,
            binding_record,
            dict(boundary_voltage_V=side_memory),
            held_control,
            numeric_time_s,
            False,
        )
        context = oracle.bind(effective)
        if set(fields) != set(context["shapes"]):
            raise ValueError("Independent capacitor ramp requires the complete original state")
        rate, phi, proof = oracle.evaluate(context, oracle.flatten(context, fields), 0.0)
        return context, rate, phi, proof

    context, rate, phi, proof = endpoint(memory)
    cells = [row["id"] for row in model["cells"]]
    outside = [row["id"] for row in model["extracellular"]]
    segments = []
    with localcontext() as precision:
        precision.prec = 100
        charge_sum = [Decimal(0) for _ in outside]
        work_sum = [Decimal(0) for _ in outside]
        energy_sum = Decimal(0)
        for declaration in declarations:
            if (
                declaration["kind"] != DECLARATION
                or declaration["law"] != LAW
                or declaration["identity"]
                != _digest({k: v for k, v in declaration.items() if k != "identity"})
            ):
                raise ValueError("Independent ramp path identity mismatch")
            target = declaration["target_boundary_voltage_V"]
            start = _boundary(model, binding_record, memory)
            finish = _boundary(model, binding_record, target)
            delta_b = [b - a for a, b in zip(start, finish, strict=True)]
            response, node = _increment(model, delta_b)
            delta_vm = [
                response[cells.index(row["inside"])]
                - response[len(cells) + outside.index(row["outside"])]
                for row in model["membranes"]
            ]
            charge = [
                node[len(cells) + i] if row["reservoir"] else Decimal(0)
                for i, row in enumerate(model["extracellular"])
            ]
            work = [
                Decimal("1e12") * (v + change / 2) * q
                for v, change, q in zip(start, delta_b, charge, strict=True)
            ]
            energy = Decimal(0)
            for row, change in zip(model["membranes"], delta_vm, strict=True):
                vm = d(phi[cells.index(row["inside"])]) - d(
                    phi[len(cells) + outside.index(row["outside"])]
                )
                energy += Decimal("0.5e12") * d(row["capacitance_F"]) * change * (2 * vm + change)
            for i in range(len(outside)):
                charge_sum[i] += charge[i]
                work_sum[i] += work[i]
            energy_sum += energy
            segments.append(
                dict(
                    delta_boundary_V=[float(v) for v in delta_b],
                    delta_membrane_voltage_V=[float(v) for v in delta_vm],
                    node_charge_change_C=[float(v) for v in node],
                    electrode_charge_change_C=[float(v) for v in charge],
                    externally_supplied_work_pJ=[float(v) for v in work],
                    capacitor_energy_change_pJ=float(energy),
                    work_residual_pJ=float(energy - sum(work, Decimal(0))),
                )
            )
            context, rate, phi, proof = endpoint(target)
            memory = list(target)
        return dict(
            law=LAW,
            segments=segments,
            cumulative_electrode_charge_C=[float(v) for v in charge_sum],
            cumulative_external_work_pJ=[float(v) for v in work_sum],
            cumulative_capacitor_energy_pJ=float(energy_sum),
            final_rate=rate.tolist(),
            final_phi=phi.tolist(),
            rate_shapes={key: list(shape) for key, shape in context["shapes"].items()},
            final_boundary_voltage_V=memory,
            full_owner_field_proof=proof,
            ionic_time_s=numeric_time_s,
            ionic_evolution=False,
            native_transition_claim=False,
        )
