"""Batched numeric junction/NaK block mapping after host owner admission.

Compile the complete physical owner binding on the host, then vmap apply over
independent worlds. The result is a control proposal, not an accepted physical
step. Clock, graph provenance, field/energy admission and publication stay with
the caller. Invalid worlds retain their raw setter output and a false validity.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.schedule import control_values
from cells.models import physiology_block_control_view as host
from cells.models import physiology_permeability_view as view
from cells.processes import betse_global_controls as source


class Kernel(NamedTuple):
    setters: source.Kernel
    control_template: object
    membrane_cell: object
    junction_sender_membrane: object
    junction_receiver_membrane: object
    junction_sender_cell: object
    junction_receiver_cell: object
    junction_active: object
    cell_count: object
    has_nak_owners: object
    original_temperature_K: object


class Values(NamedTuple):
    valid: object
    block_state: host.BlockState
    effective_control: object
    source_values: source.Values
    junction_factors: object
    checks: object


def compile_kernel(spec, tissue_binding, binding):
    """Validate actual source/owner association before producing immutable arrays."""
    if type(binding) is not host.Binding or binding.identity != host.record(binding)["identity"]:
        raise ValueError("Require the original complete block-control binding")
    host.restore(host.record(binding), spec, tissue_binding)
    table = control_values(spec, [0.0])
    template = type(table)(*(np.zeros_like(value[0]) for value in table))
    membranes = {row.id: row for row in spec.model.membranes}
    cells = {row.id: i for i, row in enumerate(spec.model.cells)}
    indices = {name: i for i, name in enumerate(binding.program.membrane_ids)}
    if not indices:
        raise ValueError("Require a nonempty actual membrane axis")
    capacity = template.junction.size
    sender, receiver, source_cell, target_cell = (
        np.zeros(capacity, dtype=np.int64) for _ in range(4)
    )
    for i, (name, a, b) in enumerate(binding.junction_membranes):
        edge = spec.model.junctions[i]
        if edge.sender == edge.receiver:
            raise ValueError("A physical junction cannot join a cell to itself")
        if name != edge.id:
            raise ValueError("Block contact order differs from actual junction order")
        sender[i], receiver[i] = indices[a], indices[b]
        source_cell[i], target_cell[i] = cells[edge.sender], cells[edge.receiver]
    result = Kernel(
        source.compile_program(binding.program),
        template,
        np.asarray(
            [cells[membranes[name].inside] for name in binding.program.membrane_ids], dtype=np.int64
        ),
        sender,
        receiver,
        source_cell,
        target_cell,
        np.arange(capacity) < len(spec.model.junctions),
        np.asarray(len(cells), dtype=np.int64),
        np.asarray(host._has_pump_owners(spec), dtype=bool),
        np.asarray(spec.model.temperature_K, dtype=np.float64),
    )
    return view._immutable_tree(result)


def _shapes(state, base, kernel, time, enabled, *, xp):
    if type(state) is not host.BlockState or type(kernel) is not Kernel:
        raise ValueError("Require the complete typed block state and compiled physical kernel")
    if type(base) is not type(kernel.control_template):
        raise ValueError("Require the complete original ordinary control type")
    nm, nj = kernel.membrane_cell.size, kernel.junction_active.size
    if nm == 0:
        raise ValueError("Require a nonempty membrane owner axis")
    for value, shape, dtype in (
        (state.junction_available, (nm,), xp.float64),
        (state.pump_available, (), xp.float64),
        (kernel.membrane_cell, (nm,), xp.int64),
        (kernel.junction_sender_membrane, (nj,), xp.int64),
        (kernel.junction_receiver_membrane, (nj,), xp.int64),
        (kernel.junction_sender_cell, (nj,), xp.int64),
        (kernel.junction_receiver_cell, (nj,), xp.int64),
        (kernel.junction_active, (nj,), xp.bool_),
        (kernel.cell_count, (), xp.int64),
        (kernel.has_nak_owners, (), xp.bool_),
        (kernel.original_temperature_K, (), xp.float64),
        (time, (), xp.float64),
        (enabled, (), xp.bool_),
    ):
        if value.shape != shape or value.dtype != dtype:
            raise ValueError("Require complete single-world shapes and explicit numeric precision")
    for value, template in zip(base, kernel.control_template, strict=True):
        if value.shape != template.shape or value.dtype != xp.float64:
            raise ValueError("Require every original float64 control field and padded axis")
    if base.junction.shape != (nj,):
        raise ValueError("Physical contact axis differs from the complete control frame")
    return nm


def _fractions(value, *, xp):
    return xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))


def apply(state, base_control, kernel, time_s, events_enabled, *, xp=jnp):
    """Propose physical controls; each world keeps its own validity and raw trial.

    Supply the unchanged original held baseline on every call. Numeric owner
    checks catch malformed mappings but cannot authenticate a deliberately
    rewritten graph: compile_kernel and saved host provenance remain required.
    No field solve, RNG use, phase selection or accepted time step occurs here.
    """
    # A compiled host map can be shared as a closed-over JIT constant. Convert
    # every numeric leaf before indexing, including that shared map's owners.
    state, base_control, kernel = jax.tree.map(xp.asarray, (state, base_control, kernel))
    time, enabled = xp.asarray(time_s), xp.asarray(events_enabled)
    nm = _shapes(state, base_control, kernel, time, enabled, xp=xp)
    active = kernel.junction_active
    sender, receiver = kernel.junction_sender_membrane, kernel.junction_receiver_membrane
    index_ok = (sender >= 0) & (sender < nm) & (receiver >= 0) & (receiver < nm)
    # Safe gathers retain the raw indices and fail admission; they do not repair
    # a bad physical owner map or permit it to affect another batched world.
    si, ri = xp.clip(sender, 0, nm - 1), xp.clip(receiver, 0, nm - 1)
    ids, weights = xp.concatenate((si, ri)), xp.concatenate((active, active)).astype(xp.int64)
    hits = (
        np.bincount(ids, weights=weights, minlength=nm)
        if xp is np
        else xp.bincount(ids, weights=weights, length=nm)
    )
    values = source.apply(
        source.State(
            kernel.original_temperature_K,
            state.junction_available,
            state.pump_available,
            xp.zeros(4, dtype=xp.float64),
        ),
        kernel.setters,
        time,
        kernel.original_temperature_K,
        enabled,
        xp=xp,
    )
    after = host.BlockState(values.state.junction_available, values.state.pump_available)
    left, right = after.junction_available[si], after.junction_available[ri]
    factors = xp.where(active, left, 1.0)
    effective = base_control._replace(junction=base_control.junction * factors)
    if hasattr(effective, "pump"):
        effective = effective._replace(pump=base_control.pump * after.pump_available)
    checks = dict(
        original_temperature=xp.isfinite(kernel.original_temperature_K)
        & (kernel.original_temperature_K > 0),
        finite_event_label=xp.isfinite(time),
        block_only_program=~kernel.setters.enabled[0] & ~kernel.setters.enabled[3],
        initial_block_domain=_fractions(state.junction_available, xp=xp)
        & _fractions(state.pump_available, xp=xp),
        original_control_domain=xp.all(xp.stack([_fractions(v, xp=xp) for v in base_control])),
        membrane_owners=(kernel.cell_count > 0)
        & xp.all((kernel.membrane_cell >= 0) & (kernel.membrane_cell < kernel.cell_count)),
        junction_indices=xp.all(~active | index_ok),
        junction_owners=xp.all(
            ~active
            | (
                (sender != receiver)
                & (kernel.junction_sender_cell >= 0)
                & (kernel.junction_sender_cell < kernel.cell_count)
                & (kernel.junction_receiver_cell >= 0)
                & (kernel.junction_receiver_cell < kernel.cell_count)
                & (kernel.junction_sender_cell != kernel.junction_receiver_cell)
                & (kernel.membrane_cell[si] == kernel.junction_sender_cell)
                & (kernel.membrane_cell[ri] == kernel.junction_receiver_cell)
            )
        ),
        exclusive_contact_membranes=xp.all(hits <= 1),
        symmetric_contact_factors=xp.all(~active | (left == right)),
        actual_nak_owners=kernel.has_nak_owners | (after.pump_available == 1),
        source_control_domain=values.physical_domain,
        compatible_pump_frame=~kernel.has_nak_owners | xp.asarray(hasattr(base_control, "pump")),
        effective_control_domain=xp.all(xp.stack([_fractions(v, xp=xp) for v in effective])),
    )
    checks = {key: xp.asarray(checks[key]) for key in sorted(checks)}
    return Values(
        xp.all(xp.stack(tuple(checks.values()))), after, effective, values, factors, checks
    )
