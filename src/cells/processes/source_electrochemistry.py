"""Independent constitutive laws for the explicitly nominal BITSEY profile.

Not the physical-model pump/GHK contract. Constants, rounding and regularization
are part of this source identity; no upstream implementation is imported.
"""

import jax.numpy as jnp

F, R, Q, KB, T = 96485.0, 8.314, 1.602e-19, 1.3806e-23, 310.0
RADIUS, CM, THICKNESS, CONTACT_LENGTH = 5e-6, 0.05, 7.5e-9, 1e-7
GATES = {
    "45/45": (-110.0, -0.0102, -110.0, -0.0102, 0.06, 1.56),
    "40/37": (407.0, 0.0263, 245.0, 0.0195, 0.28, 1.02),
}


def membrane_flux(ions, voltage, bath, diffusion, leak_control, pump_control, *, xp=jnp):
    valence = xp.asarray([1.0, 1.0, -1.0])[:, None]
    x = valence * voltage[..., None, :] * F / (R * T) + 1e-25
    leak = leak_control * (diffusion / THICKNESS) * x * (bath * xp.exp(-x) - ions) / (-xp.expm1(-x))
    sodium, potassium = ions[..., 0, :], ions[..., 1, :]
    outside_na, outside_k = bath[0], bath[1]
    omega = (
        (0.15e-3)
        * (0.15e-3)
        * (outside_na * 1e-3) ** 3
        * (potassium * 1e-3) ** 2
        / ((1.5e-3) * (sodium * 1e-3) ** 3 * (outside_k * 1e-3) ** 2)
    )
    a, b, d = (sodium / 12.0) ** 3, (outside_k / 0.2) ** 2, 1.5 / 0.5
    saturation = (a / (1 + a)) * (b / (1 + b)) * (d / (1 + d))
    cycle = (
        xp.any(diffusion > 0, axis=-2)
        * pump_control
        * 1e-7
        * saturation
        * (1 - omega / xp.exp((37000.0 + F * voltage) / (R * T)))
    )
    return leak, cycle


def junction_flux(
    concentration, delta_v, diffusion, gate_parameters, gate_enabled, controls, *, xp=jnp
):
    sender, receiver = concentration
    a1, v1, a2, v2, minimum, maximum = gate_parameters
    opening = 1 / (1 + xp.exp(a1 * (-delta_v - v1)) + xp.exp(a2 * (delta_v - v2)))
    ionic_scale = xp.where(gate_enabled, minimum + (maximum - minimum) * opening, 1.0)
    mirna_scale = xp.where(gate_enabled, maximum * opening, 1.0)
    scales = xp.stack((ionic_scale, ionic_scale, ionic_scale, mirna_scale), axis=-2)
    valence = xp.asarray([1.0, 1.0, -1.0, -1.0])[:, None]
    x = valence * delta_v[..., None, :] * Q / (KB * T)
    donor = xp.where(x >= 0, sender, receiver)
    flux = diffusion / CONTACT_LENGTH * (sender - receiver + x * donor) * scales
    multipliers = xp.stack((controls[..., 0, :],) * 3 + (controls[..., 1, :],), axis=-2)
    return flux * multipliers, scales
