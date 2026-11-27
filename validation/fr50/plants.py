"""FR-50's registered plants (fr50-one-way-records-v1 §2 and §3): each is the engine with one
planted change, in this process only: phase 1's to a kind's one-way record hook, phase 2's to @3's
channel split (surface_pump_v3.channel_one_way_split).

**How a plant runs.** `planted(name)` is a context manager. While it is entered, the active kind
registry holds the kind with its `one_way_fluxes` hook replaced, and nothing else. A run's
implementation is cached per registry (surface_pump_v3._implementation), so a planted run compiles
its own program and never reuses the honest one. Nothing is written to disk.

**The plants**, each judged by the tagged judge (validation/fr50/judge.py's PLANTS), which says what
each must fail:
- K1 (a), `K1a_backward_halved`: the passive route's backward (outward) one-way flux halved. The
  step rule restores the record from the booked net, so the records stay right and the gap shows
  it, r = 1/3;
- K1 (b), `K1b_both_halved`: both directions halved. The gap stays 0 and the records are half;
- K3, `K3_bernoulli_exchanged`: B(x) and B(-x) exchanged in the constant-field split, by reading
  the end's potentials negated (x -> -x), which inverts Ussing's factor at every nonzero voltage;
- K4 (a), `K4a_no_saturation`: the transporter's J+ without its saturation S (and J- = J+ e^x with
  it), version 1's layout;
- K4 (b), `K4b_ratio_inverted`: J- = J+ e^(-x) in place of J+ e^x, x = dG_cyc/RT, as J+^2 / J-.

**Phase 2's plants** replace @3's channel split, surface_pump_v3.channel_one_way_split, which
channel_rates calls by its module name wherever the split is asked: the host's clamped path and the
compiled step's records. While one is entered, @3's implementation objects are rebuilt (their caches
cleared on entry and on exit), so a compiled run traces the planted split in its own program; the
engine adapter keys its runs by plant. channel_rates' flux is untouched:
- `E4_block_omitted` and `E6b_block_omitted`: FR-51's block left out of both directions (u taken as
  absent), D327's planted fault;
- `E6a_availability_omitted`: the split's own opening, with the routed availability left out;
- `E6c_bernoulli_exchanged`: B(x) and B(-x) exchanged, by the split reading the voltage negated.
"""

import contextlib
import dataclasses

from cells.kinds import passive_routes, transporter
from cells.models import surface_pump_v3
from cells.registry import kind_registry


def _only(fluxes):
    ((net, (forward, backward)),) = fluxes.items()
    return net, forward, backward


def backward_halved(view, p, *, xp):
    net, forward, backward = _only(passive_routes.record_fluxes(view, p, xp=xp))
    return {net: (forward, 0.5 * backward)}


def both_halved(view, p, *, xp):
    net, forward, backward = _only(passive_routes.record_fluxes(view, p, xp=xp))
    return {net: (0.5 * forward, 0.5 * backward)}


def bernoulli_exchanged(view, p, *, xp):
    return passive_routes.record_fluxes(view._replace(potentials=-view.potentials), p, xp=xp)


def no_saturation(view, p, *, xp):
    net, plus, minus = _only(transporter.record_fluxes(view, p, xp=xp))
    c_in, _, fuel = transporter.gather(view.read, p, xp=xp)
    s = xp.exp(transporter._version_1_log_s(c_in, fuel, p, xp=xp))
    safe = xp.where(s > 0, s, 1.0)
    return {net: (xp.where(s > 0, plus / safe, 0.0), xp.where(s > 0, minus / safe, 0.0))}


def ratio_inverted(view, p, *, xp):
    net, plus, minus = _only(transporter.record_fluxes(view, p, xp=xp))
    safe = xp.where(minus > 0, minus, 1.0)
    return {net: (plus, xp.where(minus > 0, plus * plus / safe, 0.0))}


PLANTED = {
    "K1a_backward_halved": (passive_routes.PASSIVE_ROUTES, backward_halved),
    "K1b_both_halved": (passive_routes.PASSIVE_ROUTES, both_halved),
    "K3_bernoulli_exchanged": (passive_routes.PASSIVE_ROUTES, bernoulli_exchanged),
    "K4a_no_saturation": (transporter.TRANSPORTER, no_saturation),
    "K4b_ratio_inverted": (transporter.TRANSPORTER, ratio_inverted),
}


_SPLIT = surface_pump_v3.channel_one_way_split  # The honest split, which each plant wraps.


def block_omitted(c_in, c_out, voltage, opening, availability, u, p, *, xp):
    return _SPLIT(c_in, c_out, voltage, opening, availability, None, p, xp=xp)


def availability_omitted(c_in, c_out, voltage, opening, availability, u, p, *, xp):
    return _SPLIT(c_in, c_out, voltage, opening, xp.ones_like(availability), u, p, xp=xp)


def split_bernoulli_exchanged(c_in, c_out, voltage, opening, availability, u, p, *, xp):
    return _SPLIT(c_in, c_out, -voltage, opening, availability, u, p, xp=xp)


PLANTED_SPLIT = {
    "E4_block_omitted": block_omitted,
    "E6a_availability_omitted": availability_omitted,
    "E6b_block_omitted": block_omitted,
    "E6c_bernoulli_exchanged": split_bernoulli_exchanged,
}


def _rebuild():
    """Clear @3's implementation objects, so the next run binds and traces the split in place (the
    engine adapter keys its runs by plant, so an honest run is never a planted one's)."""
    surface_pump_v3._implementation.cache_clear()
    surface_pump_v3._bound_checks.cache_clear()


@contextlib.contextmanager
def planted(name):
    """The engine with plant `name` (PLANTED or PLANTED_SPLIT), or as it is for None."""
    if name is None:
        yield
        return
    if name in PLANTED_SPLIT:
        surface_pump_v3.channel_one_way_split = PLANTED_SPLIT[name]
        _rebuild()
        try:
            yield
        finally:
            surface_pump_v3.channel_one_way_split = _SPLIT
            _rebuild()
        return
    kind, hook = PLANTED[name]
    registry = kind_registry.KindRegistry()
    registry.register(dataclasses.replace(kind, one_way_fluxes=hook))
    with kind_registry.scope(registry):
        yield
