"""Emulator: BETSE 1.5 general-network ion channels on the BETSE-order default world.

Validation tooling (D131), not an engine model. It adds BETSE's network channels
(chemistry/networks.py run_loop_channels) to the junction/pump emulator step
(emulator/junction.py) in BETSE's order:

* sim.py runs the network after the electrodiffusion loop and the Ca handler and
  before update_all_concs, so each channel sees the step-start bulk cell
  concentration, the exterior concentration after this step's ECM update, and the
  step-start Vm;
* each channel first advances its gates (channelsabc.py update_mh: semi-implicit
  Euler with step-start coefficients), then moves its ion with the constant-field
  flux at permeability P * maxDm / tm (networks.py: DChan, stb.electroflux), applied
  at once to cells, membranes and ECM (stb.update_Co); channels act in config order,
  each on the concentrations the previous one left;
* the membrane and junction transfers of the step are computed from the step start
  and added afterwards (they do not depend on the channels), and the membrane copy
  the next step's leak and pump read includes the channel transfer.

Laws (BETSE channel type -> kind, opening m^a h^b):

* Kv1p5 (vg_k.py)   -> kv1p5,  m h,    cells.processes.voltage_gates.kinetics
* Kir2p1 (vg_k.py)  -> kir2p1, m h^2,  cells.processes.potassium_channels.kir2p1_kinetics
* Nav1p2 (vg_na.py) -> nav1p2, m^3 h,  cells.processes.sodium_channels.nav1p2_kinetics
* KLeak (vg_k.py), NaLeak (vg_na.py) -> kleak, naleak: always open (gates fixed at 1)

The gated laws are the Cells process laws, whose targets, time constants and gate clock
equal BETSE's (tests/unit/test_surface_channels.py and test_surface_sodium.py replay the
unmodified BETSE classes to 5e-14). The Nav1p2 rates there take their analytic limits at
BETSE's removable singularities (-25, -40 and -65.000123 mV), where BETSE's own
expressions are 0/0. Channels inactive in INIT are skipped there (``init active``).
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.processes import potassium_channels, sodium_channels, voltage_gates
from validation.betse.emulator import junction, laws
from validation.betse.emulator import spatial as passive

# kind -> (gate kinetics or None for an always-open leak, (m power, h power), ion)
LAWS = {
    "kv1p5": (voltage_gates.kinetics, (1, 1), "K"),
    "kleak": (None, (0, 0), "K"),
    "kir2p1": (potassium_channels.kir2p1_kinetics, (1, 2), "K"),
    "nav1p2": (sodium_channels.nav1p2_kinetics, (3, 1), "Na"),
    "naleak": (None, (0, 0), "Na"),
}
KINDS = tuple(LAWS)


class Layout(NamedTuple):
    junction: junction.Layout
    kinds: tuple  # static: one of KINDS per channel, in BETSE config order
    ion: tuple  # static: species index per channel
    permeability: object  # [channel, membrane] maxDm / tm on targeted membranes, else 0 (m/s)
    active: object  # [channel] 1.0 when the channel runs in this phase, else 0.0


class State(NamedTuple):
    junction: junction.State
    gates: object  # [channel, 2 (m, h), membrane]; always-open channels keep ones


def kinetics(kind, vm, *, xp=jnp):
    """(targets, time constants) [2, membrane] of a gated kind at Vm (V, s)."""
    return LAWS[kind][0](vm, xp=xp)


def opening(kind, gate):
    """BETSE's P = m**a * h**b (vg_*.py _implement_state); 1 for the leaks."""
    a, b = LAWS[kind][1]
    if not (a or b):
        return 1.0
    m, h = gate[0], gate[1]
    return (m**a if a != 1 else m) * (h**b if b != 1 else h)


def steady_gates(kinds, vm, *, xp=np):
    """BETSE's channel init: gates at their steady state for the given Vm (networks.py:6624)."""
    vm = xp.asarray(vm)
    ones = xp.ones((2, vm.size))
    return xp.stack(
        [ones if LAWS[kind][0] is None else kinetics(kind, vm, xp=xp)[0] for kind in kinds]
    )


def validate_layout(p, *, variant):
    if len(p.kinds) != len(p.ion) or any(k not in KINDS for k in p.kinds):
        raise ValueError("Network channels need a known kind and an ion each")
    t = p.junction.active.tissue
    m = t.membrane_area.size
    if np.asarray(p.permeability).shape != (len(p.kinds), m):
        raise ValueError("Network channel permeability is [channel, membrane]")
    if np.any(np.asarray(p.permeability) < 0) or not np.isfinite(p.permeability).all():
        raise ValueError("Network channel permeability must be finite and nonnegative")
    for index in p.ion:
        if not 0 <= index < t.valence.size or not t.moving[index]:
            raise ValueError("Network channel ion must be a moving species")
        if t.valence[index] != 1:
            raise ValueError("Network channel ions here are monovalent (Na, K)")
    return p


def step(state, p, dt, control, *, xp=jnp, variant=laws.QUALIFIED, membrane_inputs=None):
    """One BETSE update with network channels; unchanged state on an invalid trial.

    ``membrane_inputs`` (spatial.MembraneInputs or None) changes only what the membrane
    processes see: junction.step's, and here the channels and their gates.
    """
    t = p.junction.active.tissue
    old = state.junction.active.tissue
    base, rates, valid = junction.step(
        state.junction,
        p.junction,
        dt,
        control,
        xp=xp,
        variant=variant,
        membrane_inputs=membrane_inputs,
    )
    field = passive.field(old, t, xp=xp, variant=variant)
    vm = field.membrane_voltage_V
    if membrane_inputs is not None:
        vm = vm + membrane_inputs.voltage_shift
    _, reset, delta, _ = passive.transport(old, t, dt, xp=xp, variant=variant)
    after_ecm = (reset + delta).reshape(old.outside_concentration.shape)
    cells, outside = passive.ownership(t, xp=xp)
    voxel_fmol = t.height * t.spacing**2 * 1e15
    cell, env = old.cell_concentration, after_ecm
    gates, transferred = [], xp.zeros_like(old.membrane_inward_fmol)
    species = xp.arange(t.valence.size)[:, None]
    for c, (kind, ion) in enumerate(zip(p.kinds, p.ion, strict=True)):
        if LAWS[kind][0] is not None:
            targets, tau = kinetics(kind, vm, xp=xp)
            gate = (tau * state.gates[c] + dt * targets) / (tau + dt)
        else:
            gate = state.gates[c]
        gate = xp.where(p.active[c] > 0, gate, state.gates[c])
        gates.append(gate)
        flux = (
            laws.ghk_leak(
                cell[ion, t.cell_owner],
                passive.membrane_view(env[ion, t.outside_owner], vm, membrane_inputs, ion)[0],
                vm,
                t.valence[ion],
                t.temperature,
                t.membrane_area,
                p.permeability[c],
                opening(kind, gate),
                variant,
                xp=xp,
            )
            * p.active[c]
        )
        flux = (species == ion) * flux
        cell = cell + dt * (flux @ cells.T) / (t.cell_volume * 1e15)
        env = env - dt * (flux @ outside.T) / voxel_fmol
        transferred = transferred + dt * flux
    gain_cell = cell - old.cell_concentration
    gain_env = env - after_ecm
    tissue = base.active.tissue
    tissue = tissue._replace(
        cell_concentration=tissue.cell_concentration + gain_cell,
        membrane_concentration=xp.where(
            t.moving[:, None],
            tissue.membrane_concentration + gain_cell[:, t.cell_owner],
            tissue.membrane_concentration,
        ),
        outside_concentration=tissue.outside_concentration + gain_env,
        membrane_inward_fmol=tissue.membrane_inward_fmol + transferred,
    )
    candidate = State(
        base._replace(active=base.active._replace(tissue=tissue)),
        xp.stack(gates) if gates else state.gates,
    )
    valid &= passive.domain_valid(tissue, xp=xp)
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in jax.tree.leaves(candidate)]))
    lo, hi = voltage_gates.VOLTAGE_DOMAIN_V
    valid &= xp.all((vm >= lo) & (vm <= hi))
    return (
        jax.tree.map(lambda new, prior: xp.where(valid, new, prior), candidate, state),
        rates,
        valid,
    )
