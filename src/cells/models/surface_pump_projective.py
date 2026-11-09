"""Projective-integration readouts of the resolved pump family (resolved_pump_tissue@1-@3).

cells.core.projective calls these on accepted host rows (NumPy). They read the
model's own state, laws and ledgers and add none:

coordinates  the error coordinates the jump controller normalizes by the
             declared tolerances: free concentration (mM) of every species in
             every active cell and finite outside node; each active patch's
             membrane voltage (V, the capacitor-charge map, linear in the
             state); every active junction gate and gated channel gate.
settling     at a state and its controls: the largest membrane-voltage rate
             (V/s, the model's readouts) and the largest gate distance from its
             steady state at the actual voltage, |g_inf(V) - g|.
energy       the energy-ledger residual of balances() and the integrated
             energy flows that scale its bound in check_values.
linear_ledgers  every other ledger of balances(): material (local, outside,
             total), charge (capacitor, electrode, global), reservoir,
             electrode and metabolic work. Each is affine in the state.
"""

import numpy as np

from cells.models import surface_tissue as tissue
from cells.processes import junction_gate

COORDINATES = ("concentration_mM", "membrane_voltage_V", "gate")


def host_layout(layout):
    return type(layout)(*(np.asarray(v) for v in layout))


def _gate_mask(row, p):
    mask = getattr(p, "channel_gate_active", None)
    if mask is None:
        mask = np.broadcast_to(np.asarray(p.channel_active, dtype=bool), row.channel_gate.shape)
    return np.asarray(mask, dtype=bool)


def membrane_voltage(row, p):
    """Patch voltages of the active patches (V): initial voltage plus the charge map."""
    _, _, dv = tissue.capacitor_change(row, p, xp=np)
    return (p.initial_membrane_voltage_V + dv)[np.asarray(p.membrane_active, dtype=bool)]


def coordinates(model, row, p):
    ci, co = model.physical_amounts(row, p)
    cells = np.asarray(p.active, dtype=bool)
    outside = np.asarray(p.outside_active, dtype=bool) & ~np.asarray(p.reservoir, dtype=bool)
    concentration = np.concatenate(
        (
            (ci[:, cells] / p.volume[cells]).ravel(),
            (co[:, outside] / p.extracellular_volume[outside]).ravel(),
        )
    )
    gates = np.concatenate(
        (
            row.junction_gate[np.asarray(p.junction_active, dtype=bool)],
            row.channel_gate[_gate_mask(row, p)],
        )
    )
    return dict(
        concentration_mM=concentration,
        membrane_voltage_V=membrane_voltage(row, p),
        gate=gates,
    )


def settling(model, row, control, p):
    """(valid, max |dVm/dt| V/s, max |g_inf - g|) from the model's readouts."""
    with np.errstate(all="ignore"):
        values = model.readouts(row, control, p, xp=np)
    if not bool(values.valid):
        return False, np.inf, np.inf
    field = values.field
    rate = np.abs(field.membrane_voltage_rate_V_s[np.asarray(p.membrane_active, dtype=bool)])
    junctions = np.asarray(p.junction_active, dtype=bool)
    target = junction_gate.kinetics(
        field.rates.junction_voltage_V,
        junction_gate.Parameters(p.junction_threshold_voltage, p.junction_minimum),
        xp=np,
    ).target
    distance = [np.abs(target - row.junction_gate)[junctions]]
    targets = getattr(values, "channel_targets", None)
    if targets is not None and np.size(row.channel_gate):
        distance.append(np.abs(targets - row.channel_gate)[_gate_mask(row, p)])
    distance = np.concatenate(distance)
    return (
        True,
        float(np.max(rate, initial=0.0)),
        float(np.max(distance, initial=0.0)),
    )


def energy(model, row, p):
    """(energy-ledger residual pJ, integrated flows pJ) as check_values evaluates them."""
    with np.errstate(all="ignore"):
        residual = float(model.balances(row, p)["energy"])
    flows = sum(
        float(np.sum(np.abs(getattr(row, k))))
        for k in type(row)._fields
        if k.endswith(("_dissipated_energy_pJ", "_work_pJ"))
    )
    return residual, flows


def linear_ledgers(model, row, p):
    with np.errstate(all="ignore"):
        values = model.balances(row, p)
    return {k: np.asarray(v, dtype=np.float64) for k, v in values.items() if k != "energy"}
