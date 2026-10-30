"""Uncommitted array RK4 trial with the same held protein charge at every stage.

No checkpoint admission/publication, energy-history rebasing, component update
or random draw occurs here. Source and trajectory acceptance belong to a future
joint owner. The returned valid flag covers local stage/domain/turnover checks.
"""

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import physiology_tissue_step as tissue
from cells.models import physiology_permeability_view as permeability
from cells.models import physiology_protein_charge_rhs as charged


def _stage(state, control, layout, delta, h, implementation, *, xp):
    step_ok = xp.isfinite(h) & (h > 0)
    domain = implementation.domain_valid(state, layout, layout.active, xp=xp) & step_ok

    def evaluate():
        rates = charged.array_readouts(
            state, control, layout, delta, implementation=implementation, xp=xp
        )
        passive, fuel, transport_ok = tissue._gross_fractions(
            state, control, layout, rates.field, rates.readouts, h, implementation, xp=xp
        )
        finite = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in rates.derivative]))
        fractions_ok = (
            xp.isfinite(passive)
            & xp.isfinite(fuel)
            & (passive <= permeability.MAX_PASSIVE_FRACTION_PER_STEP)
            & (fuel <= permeability.MAX_FUEL_FRACTION_PER_STEP)
        )
        field_ok = rates.valid & transport_ok
        valid = domain & field_ok & finite & fractions_ok
        reason = xp.where(~field_ok, 2, xp.where(~finite, 3, xp.where(~fractions_ok, 4, 0)))
        return rates.derivative, tissue.StageStatus(
            valid,
            domain,
            field_ok,
            finite,
            passive,
            fuel,
            rates.field.energy_balance_pJ_s,
            reason,
        )

    if xp is np:
        if not bool(domain):
            return tissue._invalid_stage(state, 1 if bool(step_ok) else 6, xp=np)
        try:
            return evaluate()
        except np.linalg.LinAlgError:
            derivative, status = tissue._invalid_stage(state, 5, xp=np)
            return derivative, status._replace(domain_valid=np.asarray(True))
    return jax.lax.cond(
        domain,
        lambda: evaluate(),
        lambda: tissue._invalid_stage(state, xp.where(step_ok, 1, 6), xp=xp),
    )


def array_rk4_step(
    state, control, layout, protein_charge_increment_C, step_s, *, implementation, xp=jnp
):
    """Return a local trial; valid is not a coupled-trajectory acceptance flag.

    Layout/permeability, controls and protein charge are held over the entire
    explicit interval. Ionic/gating/ER/fuel state evolves at all four stages.
    Original numerical domains and gross-turnover ceilings remain mandatory.
    """
    if implementation not in permeability.IMPLEMENTATIONS.values():
        raise ValueError("Require an exact ordinary implementation")
    h = xp.asarray(step_s)
    delta = xp.asarray(protein_charge_increment_C)
    if h.ndim != 0:
        raise ValueError("RK4 trial step requires a scalar interval")
    if delta.shape != (layout.active.size + layout.outside_active.size,):
        raise ValueError("Protein charge requires the exact padded owner axis")

    def stage(value):
        return _stage(value, control, layout, delta, h, implementation, xp=xp)

    def shifted(rate, factor):
        return jax.tree.map(lambda value, derivative: value + factor * h * derivative, state, rate)

    k1, a = stage(state)
    y2 = shifted(k1, 0.5)
    k2, b = stage(y2)
    y3 = shifted(k2, 0.5)
    k3, c = stage(y3)
    y4 = shifted(k3, 1.0)
    k4, d = stage(y4)
    proposed = jax.tree.map(
        lambda value, aa, bb, cc, dd: value + (h / 6) * (aa + 2 * bb + 2 * cc + dd),
        state,
        k1,
        k2,
        k3,
        k4,
    )
    endpoint, e = stage(proposed)
    statuses = (a, b, c, d, e)
    valid = xp.stack([s.valid for s in statuses])
    first_bad = xp.min(xp.where(valid, 5, xp.arange(5)))
    return tissue.RK4Trial(
        proposed,
        (state, y2, y3, y4, proposed),
        (k1, k2, k3, k4, endpoint),
        statuses,
        xp.all(valid),
        first_bad,
    )
