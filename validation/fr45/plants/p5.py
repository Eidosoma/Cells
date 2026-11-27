"""P5 (C6, C4a): the wash scales every bound amount facing the washed node by (1 - f) and leaves R_s unchanged, so
the removed f B is booked nowhere (CRITERIA:125; the lead's ruling 7). It changes the wash wherever the engine
implements it: the NumPy and compiled maps and the run's own event (TABLE §8.1). Seam: wash_schedule.apply_events."""

from cells.operators import wash_schedule as wash
from validation.fr45.plants import same as declare  # noqa: F401

ID = "P5"
CHANGE = "apply_events: every B facing the washed node scaled by (1 - f), R unchanged"


def apply():
    import jax.numpy as jnp

    from cells.operators import site_occupancy as so

    honest = wash.apply_events

    def planted(state, control, p, *, xp=jnp, labels=None):
        out = honest(state, control, p, xp=xp, labels=labels)
        new = out[0]
        due = p.wash_node & (control.wash_count == state.wash_applied + 1)
        node = p.site_facing_node
        hit = (p.site_facing_kind == so.OUTSIDE) & due[node]
        bound = p.site_bound_anchor_fmol + state.site_bound_increment_fmol
        scaled = (1.0 - control.wash_fraction[node]) * bound - p.site_bound_anchor_fmol
        # Only where the wash acts: every other entry keeps the honest map's bits.
        new = new._replace(site_bound_increment_fmol=xp.where(hit, scaled, new.site_bound_increment_fmol))
        return (new, *out[1:])

    wash.apply_events = planted
