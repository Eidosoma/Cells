"""INVENTED, development only (the format sample's INVENTED-W3p-P7~check): P7's mechanism, and an ion amount of the
first finite outside node raised in each site half-step, which a host check refuses. No registered run takes it."""

from cells.operators import site_occupancy as so
from validation.fr45.plants import p7
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P7"
CHANGE = "INVENTED: P7's mechanism, and an ion amount raised in each site half-step"


def apply():
    p7.apply()
    honest = so.set_half_step

    def planted(state, mb, h, p, *, xp=None):
        new, ok = honest(state, mb, h, p, xp=xp) if xp is not None else honest(state, mb, h, p)
        x = new.extracellular_amount_increment
        bump = (xp or __import__("jax.numpy", fromlist=["x"])).zeros_like(x)
        bump = bump.at[0, 1].set(1e-3) if hasattr(bump, "at") else _numpy_bump(bump)
        return new._replace(extracellular_amount_increment=x + bump), ok

    so.set_half_step = planted


def _numpy_bump(bump):
    bump[0, 1] = 1e-3
    return bump
