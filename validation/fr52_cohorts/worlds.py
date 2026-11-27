"""FR-52's worlds (docs/PASSIVE_COHORT_DESIGN.md §3; the lead's P3 and growth after D376).

**The qualification world**, G1's and crossrev's world for cells.operator.integer_unit_population@1
with its cohorts declared: two populations on one cell's contact patch, each with one site, so one
compile runs both kinds of pairing table.
* The homo population (site_0, row G's): free subunits (1), dimers (2), closed and open tetramers
  (4 each), at 16 subunits from row G's start (2, 1, 3, 0). Its channels are 2F ⇄ D, 2D ⇄ T_c,
  T_c ⇄ T_o and open2 (2T_c -> 2T_o, two pairs by rule), and its transfer conducts S through the
  open tetramer only. Its cohort's class is {dimer, closed, open}, with no carries: every channel
  resolves by rule.
* The hetero population (site_1, row F's): free (1), dimers a and b (2) and tetramers (4), at 8
  subunits from row F's start (2, 2, 1, 0), with 2F ⇄ D_a, 2F ⇄ D_b, join (D_a + D_b -> T) and cut
  (T -> D_a + D_b). It has no transfer, so it moves nothing. Its cohort's class is {dimer_a,
  dimer_b, tetramer}, with row F's two declared pairings: join [dimer_a, tetramer], cut
  [tetramer, dimer_a].
* The rates are constant and read nothing, so every event time is exact and the two sites never
  meet (one stage). Both windows are [1, 2) s, inside the run of 4 s at 10 ms, with a complete
  trace and a row every step.
* SEED was chosen with replay (a host replica of the event rule at constant rates, the exact
  kernel's channel rule and the sites' counter streams) so that the run holds, in the homo, a
  merge, a split, an opening, a closing, an open2, an assembly inside the window and a loss of a
  dimer after it; in the hetero, a join, a cut and a loss of a dimer b after its window; and an
  event on each site on both sides of the restart's cut (RESTART_S, inside both windows, between
  events). required(events) states the ten and the cut; the compiled test asserts them.
* unobserved(): the same world with no cohort (its twin).

**dividing_beside_cohort()**: cells.operator.isopotential_partition@1 divides cell_0, whose site is
mapped onto its daughters, while a second cell's site carries a cohort (the lead's ruling on §9.5:
the partition's finiteness check reads the record at the division).
"""

import copy
import math

import numpy as np

from validation.fr43_part3 import worlds as part3
from validation.tissue import secreted_species_fixtures as ssf

LAW = part3.LAW
PATCH, CELL, NODE = part3.PATCH, part3.CELL, part3.NODE
DT, END, EVERY = 0.01, 4.0, 0.01
WINDOW_S = (1.0, 2.0)
RESTART_S = 1.5  # The restart's cut (case E): inside both windows, between events.
TRACE = 256
SEED = 1
CELL_pL, NODE_pL = 1.0, 0.5
CELL_mM, NODE_mM = 1.0, 0.05
OPEN_CONDUCTANCE_pL_PER_S = 0.05

HOMO = dict(
    id="homo",
    states=(("free", 1), ("dimer", 2), ("closed", 4), ("open", 4)),
    channels=(
        ("assemble", {"free": 2}, {"dimer": 1}, 0.1),
        ("dissolve", {"dimer": 1}, {"free": 2}, 0.5),
        ("merge", {"dimer": 2}, {"closed": 1}, 0.5),
        ("split", {"closed": 1}, {"dimer": 2}, 0.5),
        ("opening", {"closed": 1}, {"open": 1}, 0.5),
        ("closing", {"open": 1}, {"closed": 1}, 0.5),
        ("open2", {"closed": 2}, {"open": 2}, 1.0),
    ),
    start={"free": 2, "dimer": 1, "closed": 3, "open": 0},
    site="site_0",
)
HETERO = dict(
    id="hetero",
    states=(("free", 1), ("dimer_a", 2), ("dimer_b", 2), ("tetramer", 4)),
    channels=(
        ("assemble_a", {"free": 2}, {"dimer_a": 1}, 0.2),
        ("dissolve_a", {"dimer_a": 1}, {"free": 2}, 0.5),
        ("assemble_b", {"free": 2}, {"dimer_b": 1}, 0.2),
        ("dissolve_b", {"dimer_b": 1}, {"free": 2}, 0.5),
        ("join", {"dimer_a": 1, "dimer_b": 1}, {"tetramer": 1}, 1.0),
        ("cut", {"tetramer": 1}, {"dimer_a": 1, "dimer_b": 1}, 0.5),
    ),
    start={"free": 2, "dimer_a": 2, "dimer_b": 1, "tetramer": 0},
    site="site_1",
)
COHORTS = (
    dict(
        id="homo_units", site="site_0", states=["dimer", "closed", "open"], window_s=list(WINDOW_S)
    ),
    dict(
        id="hetero_units",
        site="site_1",
        states=["dimer_a", "dimer_b", "tetramer"],
        window_s=list(WINDOW_S),
        carries=[
            dict(channel="join", pairs=[["dimer_a", "tetramer"]]),
            dict(channel="cut", pairs=[["tetramer", "dimer_a"]]),
        ],
    ),
)


def population(kind, *, conducting=None):
    """The operator's population of one kind (HOMO or HETERO), its one site on the contact patch;
    conducting: the state whose units conduct S (None: no transfer)."""
    states = [s for s, _ in kind["states"]]
    transfers = []
    if conducting is not None:
        g = {s: (OPEN_CONDUCTANCE_pL_PER_S if s == conducting else 0.0) for s in states}
        transfers.append(dict(id="flow", species=part3.SPECIES, conductance_pL_per_s=g))
    return dict(
        id=kind["id"],
        unit_states=[dict(id=s, subunits=w) for s, w in kind["states"]],
        channels=[
            dict(id=c, reactants=dict(r), products=dict(p), rate_per_s=k, read=None)
            for c, r, p, k in kind["channels"]
        ],
        transfers=transfers,
        division=None,
        sites=[part3.site(kind["site"], kind["start"])],
    )


def qualification(*, seed=SEED, dt=DT, end=END, every=EVERY, trace=TRACE, cohorts=True):
    """The qualification world as a raw composite definition (module docstring); cohorts False
    gives its unobserved twin."""
    raw = ssf.world(
        cells=((CELL, CELL_pL),),
        nodes=((NODE, NODE_pL),),
        faces=(),
        dt=dt,
        end=end,
        observation_times=ssf.grid_times(end, dt, every),
        concentrations_mM={CELL: CELL_mM, NODE: NODE_mM},
    )
    block = part3.block(
        [population(HOMO, conducting="open"), population(HETERO)], seed=seed, trace=trace
    )
    if cohorts:
        block["cohorts"] = copy.deepcopy(list(COHORTS))
    raw["model"]["operators"].append(block)
    return raw


def unobserved(**keywords):
    return qualification(cohorts=False, **keywords)


# ------------------------------------------------------------------ the seed (host replica)


def replay(seed=SEED, *, end=END):
    """{site id: [(time, channel id), ...]}: each site's events over [0, end] by the operator's
    event rule at constant rates (module docstring of integer_unit_population: thresholds -ln u1
    of the site's counter-based stream, the channel the first whose partial sum exceeds
    min(u2 a0, nextafter(a0, 0))). A replica for choosing the seed, never a reference: the
    compiled test reads the engine's own trace."""
    import jax.numpy as jnp

    from cells.numerics import counter_streams as streams

    kinds = (HOMO, HETERO)
    keys = streams.sites_key_data(seed, len(kinds), "events")
    out = {}
    for index, kind in enumerate(kinds):
        draws = np.asarray(
            streams.site_uniforms(
                jnp.asarray(np.repeat(keys[index : index + 1], 512, axis=0)),
                jnp.arange(512, dtype=jnp.int64),
                2,
            )
        )
        counts = dict(kind["start"])
        t, k, events = 0.0, 0, []
        while k < len(draws):
            rates = []
            for _, r, _, rate in kind["channels"]:
                ff = 1.0
                for state, order in r.items():
                    ff *= math.perm(counts[state], order) if counts[state] >= order else 0.0
                rates.append(rate * ff)
            total = 0.0
            partial = []
            for a in rates:
                total += a
                partial.append(total)
            if total == 0.0:
                break
            t += -math.log(draws[k, 0]) / total
            if t > end:
                break
            target = min(draws[k, 1] * total, math.nextafter(total, 0.0))
            j = next(y for y, c in enumerate(partial) if c > target)
            name, r, p, _ = kind["channels"][j]
            for state, order in r.items():
                counts[state] -= order
            for state, order in p.items():
                counts[state] += order
            events.append((t, name))
            k += 1
        out[kind["site"]] = events
    return out


def required(events, *, window=WINDOW_S, cut=RESTART_S):
    """{requirement: bool} of the module docstring over {site id: [(time, channel id), ...]}."""
    homo, hetero = events[HOMO["site"]], events[HETERO["site"]]
    start, end = window

    def has(seq, name, low=-math.inf, high=math.inf):
        return any(c == name and low <= t < high for t, c in seq)

    return {
        "homo: a merge": has(homo, "merge"),
        "homo: a split": has(homo, "split"),
        "homo: an opening": has(homo, "opening"),
        "homo: a closing": has(homo, "closing"),
        "homo: an open2": has(homo, "open2"),
        "homo: an assembly inside the window": has(homo, "assemble", start, end),
        "homo: a dimer lost after the window": has(homo, "dissolve", end),
        "hetero: a join": has(hetero, "join"),
        "hetero: a cut": has(hetero, "cut"),
        "hetero: a dimer b lost after the window": has(hetero, "dissolve_b", end),
        "the cut lies between events, with events on both sides at each site": all(
            not any(abs(t - cut) < 1e-6 for t, _ in seq)
            and any(t < cut for t, _ in seq)
            and any(t > cut for t, _ in seq)
            for seq in (homo, hetero)
        ),
    }


def find_seed(first=0, last=10_000):
    """The first seed in [first, last) whose replay meets every requirement."""
    for seed in range(first, last):
        if all(required(replay(seed)).values()):
            return seed
    return None


# ------------------------------------------------------------------ a division beside a cohort

OTHER_CELL, OTHER_PATCH = "cell_1", "contact_1"


def dividing_beside_cohort(*, at=0.02, dt=0.01, end=0.05, seed=11):
    """cell_0 divided by cells.operator.isopotential_partition@1 at `at` (part 3's C3.5 form): its
    site holds two free subunits and is mapped onto one site at each daughter's contact patch.
    cell_1, which never divides, holds a site with one active unit on its own contact patch and
    a cohort of that state ({active}, window [0, 1) s)."""
    from cells.definitions import partition_spec as ps

    raw = ssf.world(
        cells=((CELL, CELL_pL), (OTHER_CELL, CELL_pL)),
        nodes=((NODE, NODE_pL),),
        contacts=((PATCH, CELL, NODE), (OTHER_PATCH, OTHER_CELL, NODE)),
        faces=(),
        dt=dt,
        end=end,
        observation_times=ssf.grid_times(end, dt, dt),
        concentrations_mM={CELL: CELL_mM, OTHER_CELL: CELL_mM, NODE: NODE_mM},
    )
    division = ps.add_division(
        raw, division_id="first", parent=CELL, daughters=part3.DAUGHTERS, volume_fraction=0.5
    )
    zero = {"free": 0, "active": 0}
    sites = [
        part3.site("site_0", {"free": 2, "active": 0}),
        *(part3.site(f"site_0_{d}", zero, patch=f"{PATCH}_{d}") for d in part3.DAUGHTERS),
        part3.site("site_1", {"free": 0, "active": 1}, patch=OTHER_PATCH),
    ]
    units = dict(
        id="units",
        unit_states=[dict(id="free", subunits=1), dict(id="active", subunits=2)],
        channels=[
            dict(id="assemble", reactants={"free": 2}, products={"active": 1}, rate_per_s=0.6,
                 read=None),
            dict(id="dissolve", reactants={"active": 1}, products={"free": 2}, rate_per_s=1.0,
                 read=None),
        ],
        transfers=[
            dict(id="flow", species=part3.SPECIES,
                 conductance_pL_per_s={"free": 0.0, "active": OPEN_CONDUCTANCE_pL_PER_S})
        ],
        division="independent_segregation",
        sites=sites,
    )  # fmt: skip
    maps = [("site_0", tuple(f"site_0_{d}" for d in part3.DAUGHTERS))]
    block = part3.block([units], seed=seed, trace=8, divisions=maps)
    block["cohorts"] = [dict(id="beside", site="site_1", states=["active"], window_s=[0.0, 1.0])]
    raw["model"]["operators"] = [
        dict(law=part3.STATE, populations=[]),
        dict(law=part3.PARTITION, divisions=[division]),
        block,
    ]
    raw["experiment"]["partition_events"] = [dict(division="first", time=at, carriers=["c1", "c2"])]
    return raw
