"""Atomic per-world component selection after complete transition admission.

No RNG is sampled here. Rejected worlds select every original source bit and
retain the complete trial/admission. Ionic state and work ledgers are inputs;
this operation publishes only component state, never a charged-loop checkpoint.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp

from cells.numerics import physiology_protein_transition_arrays as transition


class CommitSelection(NamedTuple):
    valid: object
    state: object
    trial: object
    checks: object


class TransitionCommit(NamedTuple):
    selection: CommitSelection
    admission: object


def _select(source, packet, geometry, admission, *, xp):
    if type(admission) is not transition.ProteinTransitionAdmission:
        raise ValueError("Require a complete internal transition admission")
    proposal = admission.component
    checks = dict(
        complete_transition_admission=admission.valid,
        source_association=transition._equal(source, proposal.source_state, xp=xp),
        packet_association=transition._equal(packet, proposal.source_packet, xp=xp),
        geometry_association=transition._equal(geometry, proposal.source_geometry, xp=xp),
    )
    checks = {key: checks[key] for key in sorted(checks)}
    valid = xp.all(xp.stack(tuple(checks.values())))
    state = jax.tree.map(
        lambda trial, parent: xp.where(valid, trial, parent), proposal.trial, source
    )
    return TransitionCommit(CommitSelection(valid, state, proposal.trial, checks), admission)


def evaluate(
    source,
    packet,
    geometry,
    charge_reference,
    before_endpoint,
    after_endpoint,
    *,
    xp=jnp,
    **parameters,
):
    """Recompute the full supplied-packet/field/work gate, then select atomically.

    Native packets must already come from their owned host provider; the stable
    provider may be staged separately. No supplied validity flag admits state.
    The original energy/material/domain/clock/held-P checks remain mandatory.
    """
    admission = transition.evaluate(
        source,
        packet,
        geometry,
        charge_reference,
        before_endpoint,
        after_endpoint,
        xp=xp,
        **parameters,
    )
    return _select(source, packet, geometry, admission, xp=xp)


def _finish(
    source,
    packet,
    geometry,
    proposal,
    charge_reference,
    before_endpoint,
    after_endpoint,
    *,
    xp,
    **parameters,
):
    """Trusted internal boundary consuming actual retained provider output.

    Recompute complete associated admission, including frozen source/packet/
    geometry snapshots. This is staging for bounded compilation; host decoding
    independently recomputes the full public gate before publishing any state.
    """
    admission = transition._finish(
        source,
        packet,
        geometry,
        proposal,
        charge_reference,
        before_endpoint,
        after_endpoint,
        xp=xp,
        **parameters,
    )
    return _select(source, packet, geometry, admission, xp=xp)
