"""Generated held scalar expressions; no equation evaluation during preparation."""


def build_equations(xp, movement, Vector, F, R, ordered_scatter):

    def domain(vector, p, anchor):
        present = anchor > 0
        amount = anchor + vector.amount_increment_fmol
        support = (
            p.edge_active
            & (p.edge_diffusivity_um2_s > 0)
            & present[:, p.edge_sender]
            & present[:, p.edge_receiver]
        )
        valid = xp.isfinite(amount).all() & xp.all(xp.where(present, amount > 0, amount == 0))
        for value, mask in (
            (vector.amount_increment_fmol, present),
            *((value, support) for value in vector[1:]),
        ):
            valid = valid & xp.isfinite(value).all() & xp.all(xp.where(mask, True, value == 0))
        return valid

    def energetic_values(vector, result, p, anchor, reference, potential):
        amount = anchor + vector.amount_increment_fmol
        present = anchor > 0
        density = xp.where(present, result.density_fmol_um2 / reference[:, None], 1.0)
        chemical_mu = R * p.temperature_K * xp.log(density)
        source, destination = (p.edge_sender, p.edge_receiver)
        electrical_drop = (
            p.effective_charge_e[:, None] * F * (potential[source] - potential[destination])
        )
        affinity = chemical_mu[:, source] - chemical_mu[:, destination] + electrical_drop
        heat = 0.001 * result.flux_fmol_s * affinity
        work = 0.001 * result.flux_fmol_s * electrical_drop
        chemical_power = 0.001 * chemical_mu * result.amount_rate_fmol_s
        residue = chemical_power.sum(axis=1) + heat.sum(axis=1) - work.sum(axis=1)
        electrochemical_mu = chemical_mu + p.effective_charge_e[:, None] * F * potential
        cargo_charge = 1e-15 * F * p.effective_charge_e[:, None] * amount
        cargo_charge_rate = 1e-15 * F * p.effective_charge_e[:, None] * result.amount_rate_fmol_s
        cell_charge_rate = (
            1e-15 * F * p.effective_charge_e[:, None] * result.cell_rate_residual_fmol_s
        )
        derivative = Vector(result.amount_rate_fmol_s, result.flux_fmol_s, heat, work)
        values = dict(
            kernel=result,
            amount_fmol=amount,
            chemical_mu_J_mol=chemical_mu,
            electrochemical_mu_J_mol=electrochemical_mu,
            electrochemical_drop_J_mol=affinity,
            chemical_power_patch_pJ_s=chemical_power,
            dissipation_edge_pJ_s=heat,
            field_power_edge_pJ_s=work,
            cargo_charge_C=cargo_charge,
            cargo_charge_rate_C_s=cargo_charge_rate,
            cell_cargo_charge_rate_C_s=cell_charge_rate,
            energy_rate_residual_pJ_s=residue,
            derivative=derivative,
        )
        return values

    def balances(vector, p, anchor, reference, potential):
        delta, h, heat, work = vector
        local = (
            delta
            + ordered_scatter(h, xp.zeros_like(delta), (p.edge_sender,), xp=xp)
            - ordered_scatter(h, xp.zeros_like(delta), (p.edge_receiver,), xp=xp)
        )
        cell = ordered_scatter(
            delta, xp.zeros((delta.shape[0], p.cell_active.size)), (p.patch_cell,), xp=xp
        )
        present = anchor > 0
        safe = xp.where(present, anchor, 1.0)
        area = xp.where(p.patch_active, p.patch_area_um2, 1.0)
        change = (
            0.001
            * R
            * p.temperature_K
            * xp.sum(
                delta * (xp.log(safe / area / reference[:, None]) - 1)
                + (safe + delta) * xp.log1p(delta / safe),
                axis=1,
            )
        )
        work_link = (
            work
            + 0.001
            * p.effective_charge_e[:, None]
            * F
            * (potential[p.edge_receiver] - potential[p.edge_sender])
            * h
        )
        return dict(
            local_material_fmol=local,
            cell_material_fmol=cell,
            cell_cargo_charge_C=1e-15 * F * p.effective_charge_e[:, None] * cell,
            chemical_energy_change_pJ=change,
            energy_balance_pJ=change + heat.sum(axis=1) - work.sum(axis=1),
            exact_prescribed_field_transfer_work_link_pJ=work_link,
        )

    return (domain, energetic_values, balances)
