"""Closed-form passive-pair solution, independent of RK4 and coupling kernels."""

import numpy as np


def exact_pair(spec, times):
    times = np.asarray(times, dtype=np.float64)
    open_time = np.zeros_like(times)
    schedule = spec.experiment.contact
    for index, change in enumerate(schedule):
        stop = schedule[index + 1].time if index + 1 < len(schedule) else spec.experiment.end_time
        open_time += change.open_fraction * np.maximum(0.0, np.minimum(times, stop) - change.time)
    sender = spec.model.cell_ids.index(spec.model.from_cell_id)
    receiver = 1 - sender
    va, vb = spec.model.volumes[sender], spec.model.volumes[receiver]
    na, nb = spec.model.initial_amounts[sender], spec.model.initial_amounts[receiver]
    rate = spec.model.permeability * (1 / va + 1 / vb)
    equilibrium_a = (na + nb) * (va / (va + vb))
    transfer = (na - equilibrium_a) * (-np.expm1(-rate * open_time))
    amounts = np.zeros((len(times), spec.execution.capacity))
    amounts[:, sender] = na - transfer
    amounts[:, receiver] = nb + transfer
    transfers = np.zeros((len(times), spec.execution.edge_capacity))
    transfers[:, 0] = transfer
    return amounts, transfers
