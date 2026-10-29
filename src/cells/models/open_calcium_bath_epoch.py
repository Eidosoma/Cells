"""Exact bath INIT carry with admission of actual carried chemistry/fuel.

Only the phase clock resets. All35/39 other arrays, including the chemical-work
integral, remain against the original physical anchors and fixed background.
"""

from itertools import product

import numpy as np

from cells.core.specs import ConfigError
from cells.models import open_calcium_admission as ionic_domain
from cells.models import surface_bath_epoch as ordinary_epoch
from cells.models import surface_calcium_energy as fuel
from cells.processes.electrochemistry import CHARGE_PER_FMOL


def validate_carried_envelope(scheduled, state, layout):
    value = scheduled.parent_state(state)
    upper = ionic_domain.ionic_moieties(value, layout, xp=np)
    upper += np.sum(np.maximum(layout.bath_amount_coefficient_fmol, 0.0), axis=(0, 2))
    if layout.open_reservoir_world and np.any(upper > layout.open_ionic_moiety_ceiling_fmol):
        raise ConfigError("Actual carried ions plus SIM bath exceed hard ionic-moiety ceilings")
    return upper


def carried_pool_turnover_bound(scheduled, spec, state, layout):
    """Full rates at actual carried amounts, every SIM control and pulse corner."""
    from cells.core.schedule import control_values

    if not hasattr(state, "energy_amount_increment_fmol"):
        return dict(maximum_fraction_rate_s_inv=0.0, finite_fuel=False)
    raw = scheduled.parent_state(state)
    current_amount = fuel.energy_amounts(raw, layout)
    if not np.isfinite(current_amount).all() or np.any(current_amount[:, layout.active] <= 0):
        raise ConfigError("Actual carried ATP/ADP/Pi must remain finite and strictly positive")
    amount = np.where(layout.active, current_amount, 1.0)
    table = control_values(
        scheduled.schema.owner_spec(spec), [row.time for row in spec.experiment.changes]
    )
    enabled = np.flatnonzero(np.any(layout.bath_amount_coefficient_fmol != 0, axis=(1, 2)))
    worst = dict(
        maximum_fraction_rate_s_inv=0.0, worst_pulse_corner=[0.0] * 3, worst_held_control_time_s=0.0
    )
    for bits in product((0.0, 1.0), repeat=len(enabled)):
        pulse = np.zeros(3)
        pulse[enabled] = bits
        dose = np.sum(layout.bath_amount_coefficient_fmol * pulse[:, None, None], axis=0)
        charge = CHARGE_PER_FMOL * np.sum(layout.valence * dose, axis=0)
        current = scheduled.parent_layout(layout)._replace(
            extracellular_amount_reference=layout.extracellular_amount_reference + dose,
            initial_outside_charge_C=layout.initial_outside_charge_C + charge,
        )
        for i in range(len(spec.experiment.changes)):
            control = type(table)(*(row[i] for row in table))
            value = scheduled.base.readouts(raw, control, current, xp=np)
            if not value.valid:
                raise ConfigError(
                    "Actual carried Ca/fuel does not admit a SIM pulse/control corner"
                )
            exchange = value.parent.exchange
            gross = exchange.gross_hydrolysis_fmol_s + exchange.gross_synthesis_fmol_s
            fraction = float(
                np.max(np.where(layout.active, gross / np.min(amount, axis=0), 0.0), initial=0)
            )
            if not np.isfinite(fraction):
                raise ConfigError("Nonfinite actual-carried-pool gross turnover")
            if fraction > worst["maximum_fraction_rate_s_inv"]:
                worst.update(
                    maximum_fraction_rate_s_inv=fraction,
                    worst_pulse_corner=pulse.tolist(),
                    worst_held_control_time_s=spec.experiment.changes[i].time,
                )
    return worst | dict(
        finite_fuel=True,
        corners=2 ** len(enabled),
        held_control_states=len(spec.experiment.changes),
        carried_amount_fmol=current_amount[:, layout.active].tolist(),
        original_amount_fmol=layout.energy_initial_amount_fmol[:, layout.active].tolist(),
        carried_increment_fmol=raw.energy_amount_increment_fmol[:, layout.active].tolist(),
        scope=(
            "actual complete carried Ca/fuel state; every SIM control and independent pulse corner"
        ),
    )


def check_carried_pool_turnover(scheduled, spec, state, layout, step):
    if not np.isfinite(step) or step < 0:
        raise ConfigError("Carried-pool step must be finite and nonnegative")
    witness = carried_pool_turnover_bound(scheduled, spec, state, layout)
    if step * witness["maximum_fraction_rate_s_inv"] > fuel.MAX_INITIAL_POOL_CHANGE_PER_STEP:
        raise ConfigError("SIM step exceeds0.05 gross turnover of the actual carried ATP/ADP/Pi")
    return witness


class Adapter(ordinary_epoch.Adapter):
    def check_definition(self, spec):
        from cells.core.open_calcium_bath_phase_handoff import validate_carried_stages

        target = self.schema.scheduled_spec(spec)
        state, layout = self.initial_values(spec)
        self.scheduled.check_values(state, target)
        validate_carried_stages(target, state, layout)
        check_carried_pool_turnover(
            self.scheduled, target, state, layout, min(spec.execution.dt, spec.experiment.end_time)
        )

    def carried_pool_turnover_bound(self, spec):
        state, layout = self.initial_values(spec)
        return carried_pool_turnover_bound(
            self.scheduled, self.schema.scheduled_spec(spec), state, layout
        )

    def check_carried_pool_turnover(self, spec, step):
        state, layout = self.initial_values(spec)
        return check_carried_pool_turnover(
            self.scheduled, self.schema.scheduled_spec(spec), state, layout, step
        )

    def check_steps(self, spec, steps, controls):
        self.scheduled.check_steps(self.schema.scheduled_spec(spec), steps, controls)
        self.check_carried_pool_turnover(spec, float(np.max(steps, initial=0)))
