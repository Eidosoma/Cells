"""HCN1/2/4 gates and fixed Na/K/Ca permeability ratios from pinned BETSE 1.5.0.

One population has one m/h state and one availability, shared by its ion routes.
The unused h gate follows the source's relaxation but does not affect opening.
These continuous laws do not implement cAMP modulation or a native update clock.
"""

import jax.numpy as jnp

from cells.processes import sodium_channels

HCN_LAWS = {f"betse_hcn{i}_m@1": i for i in (1, 2, 4)}
LAW_CODES = {
    **sodium_channels.LAW_CODES,
    **{law: index for index, law in enumerate(HCN_LAWS, 3)},
}
LAW_PERMEABILITIES = {
    law: ((species, 1.0),) for law, species in sodium_channels.LAW_SPECIES.items()
} | {law: (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)) for law in HCN_LAWS}
SPECIES_VALENCE = {"Na": 1, "K": 1, "Ca": 2}


def kinetics(voltage, law_codes, *, xp=jnp):
    target, tau = sodium_channels.kinetics(voltage, law_codes, xp=xp)
    # HCN2/4 use the source's -10 mV shift. HCN1 does not.
    midpoint = xp.where(law_codes == 3, -0.094, xp.where(law_codes == 4, -0.089, -0.090))
    slope = xp.where(law_codes == 3, 0.0081, xp.where(law_codes == 4, 0.0062, 0.0096))
    activation = 1 / (1 + xp.exp((voltage - midpoint) / slope))
    hcn_target = xp.stack((activation, xp.ones_like(voltage)), axis=-2)
    seconds = xp.where(law_codes == 3, 0.030, xp.where(law_codes == 4, 0.184, 0.461))
    hcn_tau = xp.stack((seconds + xp.zeros_like(voltage), xp.full_like(voltage, 0.001)), axis=-2)
    selected = xp.expand_dims(law_codes >= 3, -2)
    return xp.where(selected, hcn_target, target), xp.where(selected, hcn_tau, tau)


def opening(gates, law_codes, *, xp=jnp):
    return xp.where(
        law_codes >= 3, gates[..., 0, :], sodium_channels.opening(gates, law_codes, xp=xp)
    )


def valid_codes(law_codes, *, xp=jnp):
    return xp.all((law_codes >= 0) & (law_codes <= 5) & (law_codes == xp.floor(law_codes)))
