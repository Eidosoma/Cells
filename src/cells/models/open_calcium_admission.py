"""Open-system chemical/plasma loss bounds on an explicit admitted domain.

Ionic ceilings are hard domain limits, not conserved inventories. Nonionic
chemical moieties and the finite neutral fuel's adenylate/phosphorus remain
conserved. Strict positivity, voltage, affinity and every inherited kinetic
guard continue to apply at each stage. This is not unconditional RK positivity.
"""

import numpy as np

from cells.core import owned_calcium_profile_binding as background
from cells.core.specs import ConfigError
from cells.models import er_calcium as er
from cells.models import surface_calcium as calcium
from cells.models import surface_kinetic as kinetic
from cells.processes.electrochemistry import F, R


def ionic_moieties(state, p, *, xp):
    """Actual free+bound chemical ions and all exterior control-volume ions."""
    total = xp.sum(p.extracellular_amount_reference + state.extracellular_amount_increment, axis=-1)
    for i in range(p.er_initial_amount.shape[0]):
        s, c = calcium.store_state(state, i), calcium.store_layout(p, i)
        total += p.ion_content @ xp.sum((c.initial_amount + s.amount_increment) * c.active, axis=-1)
    return total


def chemical_bound(spec, p, ceilings):
    """Majorize reaction losses using declared ionic-domain ceilings.

    er.loss_bound's legacy ``conserved_totals`` argument is mathematically an
    upper-moiety vector. Here ionic entries are explicit domain limits, and
    only nonionic entries retain their truly conserved initial totals.
    """
    losses = []
    for i, model in enumerate(spec.model.stores):
        store = calcium.store_layout(p, i)
        upper = store.moieties @ np.sum(store.initial_amount * store.active, axis=-1)
        for ion, ceiling in zip(spec.model.species_ids, ceilings, strict=True):
            upper[model.moieties.index(ion)] = ceiling
        losses.append(er.loss_bound(calcium.store_spec(spec, i), conserved_totals=upper))
    return max(losses)


def plasma_bound(p):
    """Retain the complete parent's PMCA/NCX/Ca-channel coefficient majorants."""
    inside = np.zeros_like(p.amount_reference)
    outside = np.zeros_like(p.extracellular_amount_reference)
    temperature = p.temperature
    drive = calcium.process.chemical_drive(calcium.plasma.pump_parameters(p), temperature, xp=np)
    for i in np.flatnonzero(p.membrane_active):
        owner, other = p.membrane_cell[i], p.membrane_outside[i]
        pmca = (
            p.pmca_capacity[i]
            * p.pmca_atp[i]
            / (p.pmca_km_atp[i] + p.pmca_atp[i])
            / p.pmca_km_ca[i]
        )
        inside[p.plasma_ca, owner] += pmca / p.volume[owner]
        outside[p.plasma_ca, other] += (
            pmca
            * np.exp((drive[i] + 2 * F * calcium.process.MAX_VOLTAGE) / (R * temperature))
            / p.extracellular_volume[other]
        )
        ncx = p.ncx_capacity[i] * np.exp(F * calcium.process.MAX_VOLTAGE / (2 * R * temperature))
        cav = (
            p.membrane_area[i]
            * p.cav_permeability[i]
            * p.cav_abundance[i]
            / 1e-15
            * (1 + 2 * F * max(map(abs, calcium.gates.VOLTAGE_DOMAIN_V)) / (R * temperature))
        )
        for amounts, node, volume in (
            (inside, owner, p.volume[owner]),
            (outside, other, p.extracellular_volume[other]),
        ):
            amounts[p.plasma_ca, node] += (ncx / p.ncx_km_ca[i] + cav) / volume
            amounts[p.plasma_na, node] += 3 * ncx / p.ncx_km_na[i] / volume
    return max(float(np.max(inside, initial=0)), float(np.max(outside, initial=0)))


def loss_bound(spec, ceilings, *, fuel_runtime=None):
    # The existing finite-fuel A/P majorant is a coefficient view only. It
    # never substitutes initial/maintained fuel into a physical stage RHS.
    bound_spec = fuel_runtime.bounded_prior_spec(spec) if fuel_runtime is not None else spec
    _, p = calcium.initial_values(bound_spec)
    chemistry = chemical_bound(bound_spec, p, ceilings)
    plasma = plasma_bound(p)
    passive = background.background_loss_bound(p, max(map(abs, calcium.gates.VOLTAGE_DOMAIN_V)))
    result = chemistry + plasma + passive
    if not np.isfinite(result) or result < 0:
        raise ConfigError("Open chemical/plasma/background loss bound is not finite")
    return result


def check_steps(spec, steps, controls, bound):
    kinetic.check_steps(spec, steps, controls)
    h = np.max(steps, initial=0)
    # Exact full-catalog owners inherit all three calcium ceilings; the CaV
    # limit is the strongest, while the separate gates/ER limits remain.
    if h > 1.25e-6 + 1e-16:
        raise ConfigError("Open full-catalog calcium requires the inherited <=1.25 us CaV step")
    if (
        h > er.MAX_STEP + 16 * np.finfo(float).eps
        or h * bound > 0.25
        or h / calcium.gates.MIN_TAU_S > 0.25
    ):
        raise ConfigError(
            "Open calcium step * admitted chemical/plasma/background loss exceeds0.25"
        )
