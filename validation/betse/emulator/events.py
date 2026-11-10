"""Emulator: BETSE 1.5 scheduled interventions on the BETSE-order default world.

Validation tooling (D131), not an engine model. BETSE fires its events in SIM only, at
the start of every update (sim.py run_sim_core: ``phase.dyna.fire_events(t)`` before the
pumps), with t the update's label t_k = k N dt / (N - 1) (``np.linspace(0, N dt, N)``,
sim.py:2455), and holds the values for that update:

* block NaKATP pump: ``NaKATP_block = 1 - pulse(t_k)`` multiplies every Na/K pump's flux
  (sim_toolbox.pumpNaKATP ``block``); here the pump control;
* block gap junctions: ``gj_block[targets] = 1 - pulse(t_k)`` multiplies the stored gate
  after each per-ion advance (channels/gap_junction.py); here junction.step's
  ``control.junction``, which applies blocking to the stored value as BETSE does;
* change X mem: ``Dm_cells = Dm_base + Dm_scheduled``, with
  ``Dm_scheduled[X][targets] = mult * pulse(t_k) * Dm_default`` (tishandler
  _fire_events_tissue, makeAllChanges); here the layout's membrane permeability for the
  update, (Dm_base + mult * pulse * Dm_default) / tm.

``pulse`` is BETSE's toolbox.pulse (logistic difference, g = 10 / change rate), in
BETSE's operation order. A per-update ``Drive`` carries the pump and junction factors,
the membrane permeability and optional field inputs (spatial.MembraneInputs, for term
propagation); ``step`` is junction.step with them. validation/betse/event_world_adapter.py
maps a plain-BETSE case's events to drives.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from validation.betse.emulator import junction, laws


class Drive(NamedTuple):
    pump: object  # [..., membrane] Na/K pump availability (1 - pulse under a pump block)
    junction: object  # [..., membrane] junction block factor on the stored gate
    permeability: object  # [..., species, membrane] membrane permeability (m/s)
    membrane_inputs: object = None  # spatial.MembraneInputs (term propagation) or None


def pulse(t, t_on, t_off, t_change):
    """BETSE toolbox.pulse, same operations; exp overflow gives BETSE's exact 0 or 1."""
    g = (1 / t_change) * 10
    with np.errstate(over="ignore"):
        y1 = 1 / (1 + (np.exp(-g * (np.asarray(t, dtype=np.float64) - t_on))))
        y2 = 1 / (1 + (np.exp(-g * (np.asarray(t, dtype=np.float64) - t_off))))
    return y1 - y2


def labels(steps, dt):
    """BETSE's update labels of a phase (sim.py _plot_loop)."""
    return np.linspace(0, steps * dt, steps)


def step(state, p, dt, drive, *, xp=jnp, variant=laws.QUALIFIED):
    """junction.step with this update's pump and junction factors and membrane permeability."""
    tissue = p.active.tissue._replace(membrane_permeability=drive.permeability)
    layout = p._replace(active=p.active._replace(tissue=tissue))
    control = junction.Control(drive.pump, xp.ones_like(drive.pump), drive.junction)
    return junction.step(
        state, layout, dt, control, xp=xp, variant=variant, membrane_inputs=drive.membrane_inputs
    )
