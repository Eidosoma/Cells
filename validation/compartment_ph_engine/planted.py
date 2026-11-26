"""K2's planted law for FR-4's protocol: the self-consistent reversed pump (the lead's ruling (b)).

fr4-acidification-v1's controls.K2_planted_sign defines it physically: the declared world with its
pump's two sides exchanged in the law. Per forward cycle the population hydrolyses one ATP at the
cytosol (its held fuel, unchanged) and moves n H+ from the lumen to the cytosol:

    dG_cyc = d_rG'_ATP + n [RT ln(h_c/h_L) + F V_b],   V_b = phi_c - phi_L,
    J = k a S (1 - exp(dG_cyc/RT)),   S = [1 + (K_H/h_L)^n]^-1 [1 + K_ATP/c_ATP]^-1,

the lumen's H_eq -n and the cytosol's +n per cycle, heat -J dG_cyc and the maintenance's work
-J d_rG'_ATP. Every ledger closes, so only J4 against the independent reference catches it.

It is cells.kind.transporter@1 with its rates, stage term, ledger terms and readouts replaced: the
proton kernel (laws/pumps/proton_pump.py, unedited) evaluated with the inside and outside free
protons exchanged and the patch voltage negated, its moves and ledger terms reversed. The fuel
band stays the cytosol's (the kernel checks it at its inside proton, here the lumen's, so it is
switched off there and checked at h_c). A planted law of a control, registered only inside its
block: never a model of the engine. It composes from the transporter module's public stage helpers
(gather, proton_law, patch_voltage, static_head_V, role_rows, supply_record), never its private
names.
"""

import dataclasses


def _reversed(state, potentials, availability, p, *, xp):
    """(cycles, dG_cyc, drive, valid) per membrane slot of the reversed pump."""
    from cells.kinds import transporter as t
    from cells.laws.pumps import proton_pump as proton

    c_in, c_out, fuel = t.gather(state, p, xp=xp)
    voltage = t.patch_voltage(potentials, p, xp=xp)
    i, q = t.proton_law(c_out, c_in, -voltage, fuel, p, xp=xp)  # The two sides exchanged.
    r = proton.kinetics(i, q, availability, xp=xp)
    unbanded = q._replace(fuel_ph_band=xp.full_like(q.fuel_ph_band, 1e300))
    valid = proton.domain_valid(i, unbanded, availability, xp=xp)
    ph_cytosol = -xp.log10(c_in / proton.STANDARD_STATE_mM)
    valid = valid & (xp.abs(ph_cytosol - q.fuel_ph_ref) <= q.fuel_ph_band)
    # The reversed pump is the proton law's; a world declaring only the neutral law has none.
    mask = p.transporter_proton if p.transporter_proton.shape[-1] else xp.zeros_like(valid)
    zero = xp.zeros_like(c_in)
    return (
        xp.where(mask, r.cycles_fmol_s, zero),
        xp.where(mask, r.cycle_free_energy_J_mol, zero),
        xp.where(mask, r.chemical_drive_J_mol, zero),
        xp.where(mask, valid, True),
    )


def _rates(state, potentials, control, p, *, xp):
    from cells.kinds import transporter as t
    from cells.models.surface_pump_v3 import KindRates
    from cells.numerics.extracellular_field import scatter

    cycles, energy, drive, valid = _reversed(
        state, potentials, control.transporter_availability, p, xp=xp
    )
    moved = xp.where(valid, cycles, 0.0)
    species = state.amount_increment.shape[0]
    inward = xp.where(
        t.role_rows(p, species, xp=xp), (p.transporter_stoichiometry * moved)[None, :], 0.0
    )
    heat = -1e-3 * moved * energy
    work = xp.where(p.transporter_held, -1e-3 * moved * drive, 0.0)
    return KindRates(
        cell=scatter(inward, state.amount_increment, (p.membrane_cell,), xp=xp),
        outside=-scatter(
            inward, state.extracellular_amount_increment, (p.membrane_outside,), xp=xp
        ),
        derivatives=dict(
            transporter_cycles=moved,
            transporter_dissipated_energy_pJ=heat,
            transporter_metabolic_work_pJ=work,
            transporter_fuel_supplied_fmol=t.supply_record(moved, p, species, xp=xp),
        ),
        heat_pJ_s=heat,
        work_pJ_s=work,
        membrane_flux=-inward,
        valid=xp.all(valid),
    )


def _ledger_terms(state, p, *, xp):
    from cells.kinds import transporter as t

    terms = t.ledger_terms(state, p, xp=xp)
    return dict(terms, cell=-terms["cell"], outside=-terms["outside"])


def _stage_term(read, potentials, control, p, *, xp):
    """The kernel's slope at the stage, the transporter's own form with the two sides exchanged,
    at both of the patch's ends (cells, then outside nodes): at the stage's patch voltage, negated
    into the law's frame (the true slope, past its static head included), or at the reversed
    law's static head when membrane_rate passes no potentials."""
    from cells.kinds import transporter as t
    from cells.laws.pumps import proton_pump as proton
    from cells.models.surface_pump_v3 import patch_node_conductance

    if not p.transporter_proton.shape[-1]:
        return xp.zeros(p.active.size + p.outside_active.size)
    c_in, c_out, fuel = t.gather(read, p, xp=xp)
    i, q = t.proton_law(c_out, c_in, xp.zeros_like(c_in), fuel, p, xp=xp)
    if potentials is None:  # Structure, not a value: the caller passes no potentials.
        voltage = t.static_head_V(i, q, xp=xp)
    else:
        voltage = -t.patch_voltage(potentials, p, xp=xp)  # The law's frame: the sides exchanged.
    slope = proton.electrogenic_conductance_S(
        i._replace(voltage_V=voltage), q, control.transporter_availability, xp=xp
    )
    slope = xp.where(p.transporter_proton & p.membrane_active, slope, 0.0)
    return patch_node_conductance(slope, p, xp=xp)  # Both ends: cells, then outside nodes.


def _readouts(state, read, potentials, control, p, *, xp):
    del state
    values = _reversed(read, potentials, control.transporter_availability, p, xp=xp)[:3]
    return tuple(xp.where(p.transporter_present, value, 0.0) for value in values)


def reversed_pump():
    """K2(b)'s planted transporter kind (module docstring)."""
    from cells.kinds import transporter as t

    return dataclasses.replace(
        t.TRANSPORTER,
        rates=_rates,
        stage_term=_stage_term,
        ledger_terms=_ledger_terms,
        readouts=_readouts,
    )


def registry(kind):
    """The built-in kinds with `kind` in place of the transporter, for one control's block."""
    from cells.kinds import transporter as t
    from cells.registry import kind_registry

    out = kind_registry.KindRegistry()
    for known in kind_registry.active().model_keys().values():
        out.register(kind if known is t.TRANSPORTER else known)
    return out


PLANTED = {"sign": reversed_pump}  # The generator's planted names.
