"""FR-1's acceptance worlds: cells.operator.cell_owned_compartments@1 with exchange@1 (and turnover@1 or
cells.operator.local_species_reactions@1 beside it), the worlds of the protocol's references
(docs/CLOSED_COMPARTMENT_DESIGN.md §6.3 and Appendix A). All values are synthetic.

Built on compartment_fixtures (the declaration) and secreted_species_fixtures (D150's quiescent
species-only worlds: passive cells, zero ion permeability on every patch, every node at the bath's
ion composition with a zero charge anchor). Every world has the owner cell_0 (1 pL) with its wall
patch on the held bath, and the compartment lys_0 stored at node ecs_0 (V_O = 0.1 pL) behind its
bounding patch contact_0 (1e-11 m^2); no face names ecs_0. S is the neutral species; records every
10 ms on the step grid.

* flux_loading, first_order_loading: C3 (A.2), export only (loading with retention);
* two_way: C4 (A.3, A.4), a first-order export and a first-order import on the bounding patch;
* saturable_release: C5 (A.5), a saturable import from the compartment into the cytosol;
* load_and_degrade: C6 (A.6), a first-order export with turnover's first-order clearance at the
  compartment's node;
* load_and_react: C7 (A.7), a first-order export with D152's first-order S -> P at the node;
* uptake_path: C8 (A.8), a first-order import on the plasma patch contact_e from the finite node
  ecs_e (2 pL, face-free) into the cytosol, and a first-order export on the bounding patch;
* from_trace: C11 (A.2, A.5, A.10), each loading and release law from a 1e-15 mM trace on the
  receiving side, under ARS at 1 ms or RK4 at 0.1 ms.

Rates in the experiment's units: a flux J in fmol/s, a first-order export k_e in 1/s, a first-order
import's uptake velocity k_u in m/s (kappa = 1e15 k_u A / V in 1/s), and a saturable import's V_max
in fmol s^-1 m^-2 with K_M in mM.
"""

from validation.tissue import compartment_fixtures as cf
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rx

ARS, RK4 = fx.IMEX, "rk4"
DECLARED_DT, RK4_DT, RECORD_EVERY_S = 1e-3, 1e-4, 0.01
LADDER_S = (1e-3, 5e-4, 2.5e-4, 1.25e-4)
OWNER, NODE, PATCH = cf.OWNER, cf.NODE, cf.PATCH
UPTAKE_NODE, UPTAKE_PATCH = "ecs_e", "contact_e"
V_O, V_C, V_E = 0.1, 1.0, 2.0  # pL: the compartment, the cytosol, C8's extracellular node
# (2 pL, unequal to the cytosol's 1 pL, so a kappa on the wrong volume shows: the references'
# power finding, ruled 17 November 2026).
AREA_M2 = fx.CONTACT_AREA_M2  # Every contact patch's area, the bounding patch's included.
PL_PER_M3 = 1e15
POOL_mM, LUMEN_mM, TRACE_mM = 1e-3, 1e-6, 1e-15

# C3: loading with retention.
C3_END_S = 5.0
C3_FLUX = 1e-4  # fmol/s: moves 5e-4 fmol in 5 s, half the 1e-3 fmol pool.
C3_EXPORT = 0.5  # 1/s
# C4: two-way first-order exchange, a = k_e and b = kappa = 1e15 k_u A / V_O.
C4_END_S = 1.0
C4_A, C4_B = 10.0, 20.0  # 1/s
# C5: saturable release, a = A V_max (fmol/s) and b = K_M V_O (fmol).
C5_END_S = 5.0
C5_LUMEN_mM = 1e-2  # 1e-3 fmol at V_O
C5_A, C5_KM = 2e-4, 5e-3
# C6: loading with first-order clearance at the node.
C6_END_S = 3.0
C6_EXPORT, C6_CLEAR = 1.0, 2.0
# C7: loading with D152's first-order S -> P at the node.
C7_END_S = 3.0
C7_EXPORT, C7_REACT = 1.0, 2.0
# C8: the uptake path, kappa_u = 1e15 k_u A / V_E.
C8_END_S = 5.0
C8_KAPPA, C8_EXPORT = 2.0, 1.0
# C11: from a trace (the horizons under RK4 are short: every row is checked).
C11_END_S = {ARS: 1.0, RK4: 0.2}
C11_LAWS = ("flux_export", "first_order_export", "saturable_import", "first_order_import")
C11_RELEASE_KAPPA = 2.0  # 1/s, the first-order release's kappa


def uptake_velocity(kappa, volume):
    """k_u (m/s) for a first-order import with kappa (1/s) out of a node of `volume` pL."""
    return kappa * volume / (PL_PER_M3 * AREA_M2)


def record_times(end, dt):
    return fx.grid_times(end, dt, RECORD_EVERY_S)


def _base(*, dt, solver, end, profile, nodes=((NODE, V_O),), contacts=((PATCH, OWNER, NODE),),
          extra=()):
    kwargs = dict(cells=((OWNER, V_C),), nodes=nodes, contacts=contacts, dt=dt, end=end,
                  solver=solver, observation_times=record_times(end, dt))
    if extra:
        return rx.species_world(extra, profile=profile, faces=False, **kwargs)
    return fx.world(faces=(), concentrations_mM=profile.get(fx.SPECIES), **kwargs)


def _declared(raw):
    return cf.with_compartments(raw, [cf.compartment()])


def flux_loading(*, dt=DECLARED_DT, solver=ARS, end=C3_END_S, lumen_mM=LUMEN_mM, flux=C3_FLUX):
    """C3, the flux law: a scheduled J from the cytosol's pool into the compartment."""
    raw = _base(dt=dt, solver=solver, end=end, profile={fx.SPECIES: {OWNER: POOL_mM,
                                                                     NODE: lumen_mM}})
    raw = fx.with_exchange(raw, [("load", PATCH, "export", "flux")],
                           [("load", OWNER, [(0.0, flux)])])
    return _declared(raw)


def first_order_loading(*, dt=DECLARED_DT, solver=ARS, end=C3_END_S, lumen_mM=LUMEN_mM,
                        export=C3_EXPORT):
    """C3, the first-order law: k_e n_c from the cytosol's pool into the compartment."""
    raw = _base(dt=dt, solver=solver, end=end, profile={fx.SPECIES: {OWNER: POOL_mM,
                                                                     NODE: lumen_mM}})
    raw = fx.with_exchange(raw, [("load", PATCH, "export", "first_order")],
                           [("load", OWNER, [(0.0, export)])])
    return _declared(raw)


def two_way(*, dt=DECLARED_DT, solver=ARS, end=C4_END_S, a=C4_A, b=C4_B, changes=(),
            volume=V_O):
    """C4: a first-order export (a = k_e) and a first-order import (b = kappa) on the bounding
    patch, from the pool in the cytosol; `changes`: later (time, a, b) changes (C12's restarts);
    `volume`: the compartment's (pL; C12's batch varies it)."""
    raw = _base(dt=dt, solver=solver, end=end, nodes=((NODE, volume),),
                profile={fx.SPECIES: {OWNER: POOL_mM, NODE: LUMEN_mM}})
    export = [(0.0, a), *((t, x) for t, x, _ in changes)]
    release = [(0.0, uptake_velocity(b, volume)),
               *((t, uptake_velocity(y, volume)) for t, _, y in changes)]
    raw = fx.with_exchange(raw, [("load", PATCH, "export", "first_order"),
                                 ("release", PATCH, "import", "first_order")],
                           [("load", OWNER, export), ("release", OWNER, release)])
    return _declared(raw)


def saturable_release(*, dt=DECLARED_DT, solver=ARS, end=C5_END_S, cytosol_mM=LUMEN_mM,
                      a=C5_A, km=C5_KM):
    """C5: a saturable import from the loaded compartment into the cytosol, a = A V_max."""
    raw = _base(dt=dt, solver=solver, end=end, profile={fx.SPECIES: {OWNER: cytosol_mM,
                                                                     NODE: C5_LUMEN_mM}})
    raw = fx.with_exchange(raw, [("release", PATCH, "import", "saturable")],
                           [("release", OWNER, [(0.0, a / AREA_M2, km)])])
    return _declared(raw)


def first_order_release(*, dt=DECLARED_DT, solver=ARS, end=C5_END_S, cytosol_mM=LUMEN_mM,
                        kappa=C11_RELEASE_KAPPA):
    """C11's first-order release: a first-order import from the loaded compartment."""
    raw = _base(dt=dt, solver=solver, end=end, profile={fx.SPECIES: {OWNER: cytosol_mM,
                                                                     NODE: C5_LUMEN_mM}})
    raw = fx.with_exchange(raw, [("release", PATCH, "import", "first_order")],
                           [("release", OWNER, [(0.0, uptake_velocity(kappa, V_O))])])
    return _declared(raw)


def load_and_degrade(*, dt=DECLARED_DT, solver=ARS, end=C6_END_S, export=C6_EXPORT,
                     clear=C6_CLEAR):
    """C6: first-order loading with turnover's first-order clearance at the compartment's node."""
    raw = first_order_loading(dt=dt, solver=solver, end=end, export=export)
    return fx.with_turnover(raw, [("degrade", NODE, "clearance")],
                            [("degrade", None, [(0.0, clear)])])


def load_and_react(*, dt=DECLARED_DT, solver=ARS, end=C7_END_S, export=C7_EXPORT,
                   react=C7_REACT):
    """C7: first-order loading with D152's first-order S -> P at the compartment's node (P
    declared at the trace everywhere; S and P one moiety)."""
    raw = _base(dt=dt, solver=solver, end=end, extra=("P",),
                profile={fx.SPECIES: {OWNER: POOL_mM, NODE: LUMEN_mM}})
    raw = fx.with_exchange(raw, [("load", PATCH, "export", "first_order")],
                           [("load", OWNER, [(0.0, export)])])
    species = [rx.species("S", moieties={"X": 1}), rx.species("P", moieties={"X": 1})]
    reactions = [rx.mass_action("convert", {"outside": [NODE]}, {"S": 1}, {"P": 1}, react)]
    raw = rx.with_reactions(raw, species, reactions, rx.always(["convert"]))
    return _declared(raw)


def uptake_path(*, dt=DECLARED_DT, solver=ARS, end=C8_END_S, kappa=C8_KAPPA,
                export=C8_EXPORT):
    """C8: ecs_e -> cytosol (a first-order import on contact_e) -> compartment (a first-order
    export on the bounding patch), a closed three-node chain."""
    raw = _base(dt=dt, solver=solver, end=end,
                nodes=((UPTAKE_NODE, V_E), (NODE, V_O)),
                contacts=((UPTAKE_PATCH, OWNER, UPTAKE_NODE), (PATCH, OWNER, NODE)),
                profile={fx.SPECIES: {UPTAKE_NODE: POOL_mM, OWNER: LUMEN_mM,
                                      NODE: LUMEN_mM}})
    raw = fx.with_exchange(raw, [("uptake", UPTAKE_PATCH, "import", "first_order"),
                                 ("load", PATCH, "export", "first_order")],
                           [("uptake", OWNER, [(0.0, uptake_velocity(kappa, V_E))]),
                            ("load", OWNER, [(0.0, export)])])
    return _declared(raw)


def from_trace(law, solver):
    """C11: one loading or release law from a 1e-15 mM trace on the receiving side, under ARS at
    1 ms or RK4 at 0.1 ms, recorded at every step (C11 judges every row)."""
    dt = DECLARED_DT if solver == ARS else RK4_DT
    end = C11_END_S[solver]
    if law == "flux_export":
        raw = flux_loading(dt=dt, solver=solver, end=end, lumen_mM=TRACE_mM)
    elif law == "first_order_export":
        raw = first_order_loading(dt=dt, solver=solver, end=end, lumen_mM=TRACE_mM)
    elif law == "saturable_import":
        raw = saturable_release(dt=dt, solver=solver, end=end, cytosol_mM=TRACE_mM)
    elif law == "first_order_import":
        raw = first_order_release(dt=dt, solver=solver, end=end, cytosol_mM=TRACE_mM)
    else:
        raise ValueError(law)
    raw["experiment"]["observation_times"] = fx.grid_times(end, dt, dt)
    return raw
