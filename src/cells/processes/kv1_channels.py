"""Complete pinned BETSE Kv1 family in the shared multi-ion channel catalog.

Kv1.1/2/3/4/6 extend the previously qualified Kv1.5, Kir2.1, NaV1.2 and HCN
laws. Voltage is in volts and time constants in seconds. These continuous
equations preserve source gate powers; they do not adopt BETSE's update clock.
"""

import jax.numpy as jnp

from cells.processes import hcn_channels

FAMILIES = (1, 2, 3, 4, 6)
KV1_LAWS = {f"betse_kv1p{i}_mh{'2' if i == 1 else ''}@1": i for i in FAMILIES}
LAW_CODES = {**hcn_channels.LAW_CODES, **{law: i for i, law in enumerate(KV1_LAWS, 6)}}
LAW_PERMEABILITIES = hcn_channels.LAW_PERMEABILITIES | {law: (("K", 1.0),) for law in KV1_LAWS}
SPECIES_VALENCE = hcn_channels.SPECIES_VALENCE


def kinetics(voltage, law_codes, *, xp=jnp):
    target, tau = hcn_channels.kinetics(voltage, law_codes, xp=xp)
    index = xp.clip(law_codes - 6, 0, 4)

    def parameters(values):
        return xp.asarray(values)[index]

    def logistic(midpoint, slope):
        return 1 / (1 + xp.exp((voltage - parameters(midpoint)) / parameters(slope)))

    activation = logistic(
        [-0.0305, -0.021, -0.0141, -0.0217, -0.0208],
        [-0.0113943, -0.0113943, -0.0103, -0.0169, -0.0081],
    )
    inactivation = logistic(
        [-0.030, -0.022, -0.033, -0.0736, -0.022],
        [0.0273943, 0.0113943, 0.0037, 0.0128, 0.01139],
    )
    activation_tau = parameters([0.030, 0.150, 0, 0, 0.030]) * logistic(
        [-0.07656, -0.06756, 0, 0, -0.04656], [0.0261479, 0.0341479, 1, 1, 0.04414]
    )
    inactivation_tau = parameters([15, 15, 0, 0, 5]) * logistic(
        [-0.16056, -0.04656, 0, 0, -0.04656], [-0.100, -0.0441479, 1, 1, -0.04414]
    )
    activation_tau = xp.where(index == 2, 0.01916 - 0.284 * voltage, activation_tau)
    inactivation_tau = xp.where(index == 2, 1.1624 - 13.760 * voltage, inactivation_tau)
    activation_tau = xp.where(index == 3, 0.003, activation_tau)
    inactivation_tau = xp.where(index == 3, 0.119, inactivation_tau)
    selected = xp.expand_dims(law_codes >= 6, -2)
    return (
        xp.where(selected, xp.stack((activation, inactivation), axis=-2), target),
        xp.where(selected, xp.stack((activation_tau, inactivation_tau), axis=-2), tau),
    )


def opening(gates, law_codes, *, xp=jnp):
    m, h = gates[..., 0, :], gates[..., 1, :]
    return xp.where(
        law_codes >= 6,
        m * h * xp.where(law_codes == 6, h, 1.0),
        hcn_channels.opening(gates, law_codes, xp=xp),
    )


def valid_codes(law_codes, *, xp=jnp):
    return xp.all((law_codes >= 0) & (law_codes <= 10) & (law_codes == xp.floor(law_codes)))
