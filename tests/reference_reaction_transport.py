"""Independent dense linear-system oracle, only for tiny verification worlds.

No Cells process, topology, schedule, or numerical function is imported here.
Species-major indexing and all signed ledger rows are assembled explicitly.
Changing generators are applied in time order, never averaged into one rate.
"""

import numpy as np
from scipy.linalg import expm


def generator(spec, opening):
    model = spec.model
    n, e = len(model.cell_ids), len(model.contacts)
    size = 3 * n + 2 * e
    matrix = np.zeros((size, size))
    cell_slots = {value: i for i, value in enumerate(model.cell_ids)}
    first, second = (model.species.index(s) for s in (model.from_species, model.to_species))
    for cell, (forward, reverse) in enumerate(
        zip(model.forward_rate, model.reverse_rate, strict=True)
    ):
        a, b, r = first * n + cell, second * n + cell, 2 * n + 2 * e + cell
        matrix[a, a] -= forward
        matrix[b, a] += forward
        matrix[a, b] += reverse
        matrix[b, b] -= reverse
        matrix[r, a] += forward
        matrix[r, b] -= reverse
    for edge, contact in enumerate(model.contacts):
        source, target = cell_slots[contact.from_cell_id], cell_slots[contact.to_cell_id]
        for species, permeability in enumerate(contact.permeability):
            i, j = species * n + source, species * n + target
            q = 2 * n + species * e + edge
            rate_i = permeability * opening[edge] / model.volumes[source]
            rate_j = permeability * opening[edge] / model.volumes[target]
            matrix[i, i] -= rate_i
            matrix[i, j] += rate_j
            matrix[j, i] += rate_i
            matrix[j, j] -= rate_j
            matrix[q, i] += rate_i
            matrix[q, j] -= rate_j
    return matrix


def reference(spec, times):
    n, e = len(spec.model.cell_ids), len(spec.model.contacts)
    controls = spec.experiment.contact
    anchor = np.zeros(3 * n + 2 * e)
    anchor[: 2 * n] = np.asarray(spec.model.initial_amounts).ravel()
    index, anchor_time = 0, 0.0
    matrix = generator(spec, controls[0].open_fractions)
    records = []
    for time in times:
        while index + 1 < len(controls) and controls[index + 1].time <= time:
            next_time = controls[index + 1].time
            anchor = expm((next_time - anchor_time) * matrix) @ anchor
            index, anchor_time = index + 1, next_time
            matrix = generator(spec, controls[index].open_fractions)
        records.append(expm((time - anchor_time) * matrix) @ anchor)
    values = np.asarray(records)
    return (
        values[:, : 2 * n].reshape((len(times), 2, n)),
        values[:, 2 * n : 2 * n + 2 * e].reshape((len(times), 2, e)),
        values[:, 2 * n + 2 * e :],
    )
