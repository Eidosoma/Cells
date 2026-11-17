"""The kernel's local detailed-balance check (GARD_DESIGN §2.4, 1): passive laws only.

For stochastic laws the engine's heat check becomes a static property of the kernel. For every
transfer pair n <-> n + e_i, a passive law's rates must satisfy

    ln a_join_i(n) - ln a_leave_i(n + e_i) = A_i(n) = ln theta_i + ln N - ln(n_i + 1)

to rounding, where A_i is the exchange law's declared affinity (exchange.py): then the event heat
is a state-function difference and the ledger closes (ledger.py). The rates checked are the
kernel's own (kernel.rates, the same code on the host), never a transcription.

The verdict is a property of the law, not of a world: it is taken on the check's own generic
probe (PROBE_*: a few types with random transfer constants, supplies and leave constants, the
law's own probe data, and STATES random states), since special data can satisfy the identity by
accident (with a uniform or zero catalysis matrix, the preprint's single-event form of GARD's
catalysis passes). A law declared passive that fails is refused; a law declared driven is
admitted, and its deviation on a world's own data (`world_report`) is reported as its unsourced
cycle affinity, never closed.

The check's draws come from its own NumPy generator (PROBE_SEED), never from a simulation stream.
"""

import functools
import math

import numpy as np

from cells.core.specs import ConfigError
from cells.models.assembly_lineages import factors
from cells.models.assembly_lineages.kernel import Layout, rates

PROBE_SEED = 20261117
PROBE_TYPES = 4
STATES = 200
MAX_SIZE = 60
ATOL = 1e-9  # ln units: rounding of a few logarithms and one factor, far below any real bias.


def _probe_layout(law, rng, count):
    constants = rng.uniform(0.5, 4.0, count)
    supply = rng.uniform(0.05, 1.0, count)
    leave = rng.uniform(0.5, 2.0, count)
    data = None
    if law is not None:
        data = law.layout(law.parse_data(law.probe(rng, count), count), count)
    return _layout(constants, supply, leave, data)


def _layout(constants, supply, leave, factor):
    return Layout(
        kf_rho=constants * leave * supply,
        kb=np.asarray(leave, dtype=np.float64),
        log_theta=np.log(constants * supply),
        log_factorial=None,
        split_size=None,
        split_value=None,
        fission_limit=None,
        growth_limit=None,
        base_key=None,
        factor=() if factor is None else factor,
    )


def _state(law, counts, layout):
    if law is None:
        return ()
    return law.state(counts.astype(np.float64), layout.factor, np)


def deviations(law, layout, rng, states=STATES, max_size=MAX_SIZE):
    """ln a_join_i(n) - ln a_leave_i(n + e_i) - A_i(n), for every type of `states` random states."""
    count = layout.kb.shape[0]
    out = []
    for _ in range(states):
        size = int(rng.integers(1, max_size + 1))
        counts = rng.multinomial(size, rng.dirichlet(np.ones(count))).astype(np.int64)
        forward = rates(counts, np.int64(size), layout, _state(law, counts, layout), law, np)
        for i in range(count):
            after = counts.copy()
            after[i] += 1
            backward = rates(after, np.int64(size + 1), layout, _state(law, after, layout), law, np)
            declared = layout.log_theta[i] + math.log(size) - math.log(counts[i] + 1.0)
            out.append(math.log(forward[i]) - math.log(backward[count + i]) - declared)
    return np.asarray(out)


@functools.cache
def verdict(law_id):
    """The check's verdict on a rate-factor law (None: the exchange law alone), as a dict.

    Refuses (ConfigError) a law declared passive whose rates fail the identity."""
    law = None if law_id is None else factors.resolve(law_id)
    rng = np.random.default_rng(PROBE_SEED)
    layout = _probe_layout(law, rng, PROBE_TYPES)
    found = np.abs(deviations(law, layout, rng))
    role = "passive" if law is None else law.energy_role
    holds = bool(np.max(found) <= ATOL)
    if role == "passive" and not holds:
        raise ConfigError(
            f"{law_id} is declared passive, but its rates fail local detailed balance at the "
            f"kernel: |ln a+(n) - ln a-(n+e_i) - A_i(n)| reaches {np.max(found):.3g} > {ATOL:g} "
            "on the check's probe. Refused as passive; a law of this kind may be declared driven"
        )
    return {
        "law": law_id,
        "energy_role": role,
        "local_detailed_balance": "holds" if holds else "fails",
        "admitted_as": role,
        "probe": {
            "types": PROBE_TYPES,
            "states": STATES,
            "max_size": MAX_SIZE,
            "seed": PROBE_SEED,
            "tolerance_ln": ATOL,
            "max_abs_deviation_ln": float(np.max(found)),
        },
    }


def world_report(spec, *, states=STATES):
    """A driven law's deviation on the world's own data: its reported unsourced cycle affinity."""
    m = spec.model
    law = None if m.rate_factor is None else factors.resolve(m.rate_factor)
    world = m.world
    layout = _layout(
        np.asarray(world.types.transfer_constant),
        np.asarray(world.supply),
        np.asarray(world.leave_rate),
        None if law is None else law.layout(world.data, world.types.count),
    )
    rng = np.random.default_rng(PROBE_SEED)
    found = deviations(law, layout, rng, states=states, max_size=world.fission.size - 1)
    magnitude = np.abs(found)
    return {
        "states": states,
        "seed": PROBE_SEED,
        "sizes": [1, world.fission.size - 1],
        "max_abs_deviation_ln": float(np.max(magnitude)),
        "median_abs_deviation_ln": float(np.median(magnitude)),
        "p99_abs_deviation_ln": float(np.quantile(magnitude, 0.99)),
    }
