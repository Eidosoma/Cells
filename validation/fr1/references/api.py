"""FR-1's references on the FR lane's registered worlds: the functions the protocol calls.

Each takes one block of ``reference_inputs.json`` as a plain ``json.load`` gives it. See
``REFERENCES_USAGE.md`` for the returned layouts.

- ``closed(world)``: R_closed's worlds (C3, C4, C5) and the C11 worlds of R_energy. The node
  amounts follow their law's closed form (A.2, A.3, A.5).
- ``step_map(world)``: one rung of R_step_map (A.4).
- ``linear(world)``: R_linear's worlds (A.6, A.7, A.8), by the matrix exponential.
- ``capacitor(network, q_i, q_j)``: A.9's V_b and V_pm from the charges.
- ``free_energy(amounts, volumes, temperature_K)``: A.10's G.
- ``energy(world)``: the free-energy change of the nodes each law touches, along the reference
  trajectory (A.10).

**Declared values are used as declared.** Where a schedule gives a derived rate beside its
parameters, the declared rate is used and checked against them to a relative 1e-14:
- kappa_per_s against 1e15 k_u A / V of the import's source;
- a_fmol_per_s against A V_max;
- b_fmol against K_M V of the source.
A mismatch is refused.
"""

from __future__ import annotations

from decimal import localcontext
from fractions import Fraction

import numpy as np

from . import capacitor as cap
from . import energy as en
from . import forms, stepmap
from .exact import DIGITS, check_constants, dec, exact

DERIVED_RTOL = 1e-14
SPECIES = "S"


def _rate(route: dict) -> dict:
    sched = route["schedule"]
    if len(sched) != 1 or float(sched[0]["time_s"]) != 0.0:
        raise ValueError(f"route {route['id']}: one schedule entry from t = 0 is supported")
    return sched[0]


def _close(declared, derived, what: str) -> None:
    d, x = float(declared), float(derived)
    if abs(d - x) > DERIVED_RTOL * max(abs(d), abs(x)):
        raise ValueError(f"{what}: declared {d!r} differs from its parameters' {x!r}")


def _routes(world: dict) -> list:
    """Each route as (law, direction, source, target, parameters), declared values checked."""
    out = []
    for r in world["routes"]:
        s = _rate(r)
        src_V = exact(world["nodes"][r["source"]]["volume_pL"])
        law, direction = r["law"], r["direction"]
        if law == "flux":
            par = {"J": exact(s["J_fmol_per_s"])}
        elif law == "first_order" and direction == "export":
            par = {"k": exact(s["k_e_per_s"])}
        elif law == "first_order" and direction == "import":
            par = {"k": exact(s["kappa_per_s"])}
            if "k_u_m_per_s" in s:
                _close(s["kappa_per_s"], forms.kappa(s["k_u_m_per_s"], r["patch_area_m2"], src_V),
                       f"route {r['id']} kappa")
        elif law == "saturable":
            par = {"a": exact(s["a_fmol_per_s"]), "b": exact(s["b_fmol"])}
            if "V_max_fmol_per_s_m2" in s:
                _close(s["a_fmol_per_s"], exact(r["patch_area_m2"]) *
                       exact(s["V_max_fmol_per_s_m2"]), f"route {r['id']} a")
            if "K_M_mM" in s:
                _close(s["b_fmol"], exact(s["K_M_mM"]) * src_V, f"route {r['id']} b")
        else:
            raise ValueError(f"route {r['id']}: law {law!r} as {direction!r} is not a form here")
        out.append((law, direction, r["source"], r["target"], par))
    return out


def _amount0(world: dict, node: str, species: str = SPECIES):
    return exact(world["nodes"][node]["initial_fmol"].get(species, 0))


def _times(world: dict) -> np.ndarray:
    t = np.asarray(world["record_times_s"], dtype=np.float64)
    if t[0] != 0.0 or np.any(np.diff(t) <= 0):
        raise ValueError("record times must start at 0 and increase")
    return t


def closed(world: dict) -> dict:
    """The two-node closed forms: A.2 (flux or first-order export), A.3 (a pair, or an import
    alone with a = 0) and A.5 (saturable import)."""
    routes = _routes(world)
    t = _times(world)
    laws = sorted((law, d) for law, d, *_ in routes)
    out = {"times_s": t, "species": SPECIES}
    if laws == [("flux", "export")]:
        _, _, c, o, p = routes[0]
        r = forms.loading_flux(_amount0(world, c), _amount0(world, o), p["J"], t)
        if not np.all(r["valid"]):
            raise ValueError("the flux law would empty the source within the record times")
        out.update(form="A.2 flux", amount_fmol={c: r["n_c_fmol"], o: r["n_o_fmol"]},
                   floor_fmol={c: r["floor_fmol"], o: r["floor_fmol"]})
    elif laws == [("first_order", "export")]:
        _, _, c, o, p = routes[0]
        r = forms.loading_first_order(_amount0(world, c), _amount0(world, o), p["k"], t)
        out.update(form="A.2 first-order", amount_fmol={c: r["n_c_fmol"], o: r["n_o_fmol"]},
                   floor_fmol={c: r["floor_fmol"], o: r["floor_fmol"]})
    elif laws in ([("first_order", "export"), ("first_order", "import")],
                  [("first_order", "import")]):
        exp = [x for x in routes if x[1] == "export"]
        imp = [x for x in routes if x[1] == "import"][0]
        o, c = imp[2], imp[3]
        a = exp[0][4]["k"] if exp else Fraction(0)
        if exp and (exp[0][2], exp[0][3]) != (c, o):
            raise ValueError("the pair must join the same two nodes")
        r = forms.two_way(_amount0(world, c), _amount0(world, o), a, imp[4]["k"], t)
        out.update(form="A.3" if exp else "A.3 with a = 0",
                   amount_fmol={c: r["n_c_fmol"], o: r["n_o_fmol"]},
                   floor_fmol={c: r["floor_fmol"], o: r["floor_fmol"]}, x_eq=r["x_eq"],
                   a_per_s=float(a), b_per_s=float(imp[4]["k"]))
    elif laws == [("saturable", "import")]:
        _, _, o, c, p = routes[0]
        r = forms.saturable_release(_amount0(world, o), _amount0(world, c), p["a"], p["b"], t)
        out.update(form="A.5", amount_fmol={c: r["n_c_fmol"], o: r["n_o_fmol"]},
                   floor_fmol={c: r["floor_fmol"], o: r["floor_fmol"]})
    else:
        raise ValueError(f"no closed form for routes {laws}")
    return out


def step_map(world: dict) -> dict:
    """One rung of A.4: the palindrome's map iterated at the world's dt, sampled at the records."""
    routes = _routes(world)
    exp = [x for x in routes if x[1] == "export" and x[0] == "first_order"]
    imp = [x for x in routes if x[1] == "import" and x[0] == "first_order"]
    if len(exp) != 1 or len(imp) != 1 or len(routes) != 2:
        raise ValueError("A.4 needs exactly one first-order export and one first-order import")
    c, o = exp[0][2], exp[0][3]
    a, b = exp[0][4]["k"], imp[0][4]["k"]
    dt = exact(world["dt_s"])
    t = _times(world)
    steps = []
    for x in t:
        k = exact(x) / dt
        n = round(k)
        if abs(k - n) > Fraction(1, 10 ** 9):
            raise ValueError(f"record time {x} is not on the dt grid")
        steps.append(n)
    if any(b2 % steps[1] for b2 in steps[1:]) or steps[0] != 0:
        raise ValueError("record times must be equally spaced multiples of the first record")
    every = steps[1]
    it = stepmap.iterate(_amount0(world, c), _amount0(world, o), a, b, dt, steps[-1],
                         plan="single", every=every)
    if list(it["steps"]) != steps:
        raise ValueError("record times must be equally spaced from 0")
    fp = stepmap.fixed_point(a, b, dt)
    N = float(_amount0(world, c) + _amount0(world, o))
    with localcontext() as ctx:
        ctx.prec = DIGITS
        Nd = dec(_amount0(world, c)) + dec(_amount0(world, o))
        x = np.array([float(dec(v) / Nd) for v in it["n_c_fmol"]])
    floor_c = np.abs(it["n_c_fmol"] - it["n_c_float64_fmol"]) + 0.5 * np.spacing(N)
    floor_o = np.abs(it["n_o_fmol"] - it["n_o_float64_fmol"]) + 0.5 * np.spacing(N)
    return {
        "times_s": t, "steps": it["steps"], "dt_s": float(dt), "species": SPECIES,
        "x": x, "amount_fmol": {c: it["n_c_fmol"], o: it["n_o_fmol"]},
        "amount_float64_fmol": {c: it["n_c_float64_fmol"], o: it["n_o_float64_fmol"]},
        "floor_fmol": {c: floor_c, o: floor_o},
        "rounding_allowance_fmol": stepmap.rounding_allowance(N, steps[-1]),
        "x_star": fp["x_star"], "x_eq": fp["x_eq"],
        "splitting": {"relative_displacement": fp["bias"],
                      "absolute_displacement": fp["x_star"] - fp["x_eq"],
                      "leading_term": fp["leading_term"],
                      "relative_over_leading": fp["ratio"]},
        "a_per_s": float(a), "b_per_s": float(b),
    }


def linear(world: dict) -> dict:
    """A.6 to A.8: first-order routes, clearance and first-order reactions, as one linear system
    over (node, species), with the cleared amount as an extra state."""
    routes = _routes(world)
    t = _times(world)
    nodes = list(world["nodes"])
    species = sorted({s for n in nodes for s in world["nodes"][n]["initial_fmol"]})
    states = [(n, s) for n in nodes for s in species]
    idx = {x: i for i, x in enumerate(states)}
    cleared = len(states)
    M = len(states) + 1
    G = [[Fraction(0)] * M for _ in range(M)]

    def move(src, dst, k):
        G[src][src] -= k
        G[dst][src] += k
    for law, _direction, s, d, p in routes:
        if law != "first_order":
            raise ValueError("R_linear's worlds hold first-order routes only")
        move(idx[(s, SPECIES)], idx[(d, SPECIES)], p["k"])
    if "clearance_per_s" in world:
        node = world["clearance_node"]
        for k in world["clearance_per_s"].values():
            move(idx[(node, SPECIES)], cleared, exact(k))
    for rx in world.get("reactions", {}).values():
        if len(rx["reactants"]) != 1 or len(rx["products"]) != 1 or \
                any(v != 1 for v in list(rx["reactants"].values()) + list(rx["products"].values())):
            raise ValueError("first-order A -> B reactions only")
        a_s, b_s = next(iter(rx["reactants"])), next(iter(rx["products"]))
        for node in rx["sites"].get("outside", []) + rx["sites"].get("cells", []):
            move(idx[(node, a_s)], idx[(node, b_s)], exact(rx["rate_constant_per_s"]))
    y0 = [_amount0(world, n, s) for n, s in states] + [Fraction(0)]
    # States that neither change nor feed another stay constant: solve the rest.
    live = [i for i in range(M) if any(G[i][j] != 0 for j in range(M)) or
            any(G[j][i] != 0 for j in range(M))]
    r_live = forms.linear([[G[i][j] for j in live] for i in live], [0] * len(live),
                          [y0[i] for i in live], t)
    y = np.empty((t.size, M))
    fl = np.empty((t.size, M))
    for i in range(M):
        if i in live:
            y[:, i] = r_live["y"][:, live.index(i)]
            fl[:, i] = r_live["floor"][:, live.index(i)]
        else:
            y[:, i] = float(y0[i])
            fl[:, i] = 0.5 * np.spacing(abs(float(y0[i])))
    r = {"y": y, "floor": fl}
    amounts = {n: {s: r["y"][:, idx[(n, s)]] for s in species} for n in nodes}
    floors = {n: {s: r["floor"][:, idx[(n, s)]] for s in species} for n in nodes}
    out = {"times_s": t, "nodes": nodes, "species": species, "amount_fmol": amounts,
           "floor_fmol": floors}
    if "clearance_per_s" in world:
        out["cleared_fmol"] = r["y"][:, cleared]
        out["cleared_floor_fmol"] = r["floor"][:, cleared]
    if world.get("reactions"):
        tot = sum(r["y"][:, idx[(n, s)]] for n in nodes for s in species
                  if not (s != SPECIES and n not in _reaction_nodes(world)))
        out["moiety_fmol"] = tot
    return out


def _reaction_nodes(world: dict) -> set:
    return {n for rx in world.get("reactions", {}).values()
            for n in rx["sites"].get("outside", []) + rx["sites"].get("cells", [])}


def capacitor(network: dict, q_i_C, q_j_C) -> dict:
    """A.9: V_b = phi_i - phi_j and V_pm = phi_i - phi_b for each pair of charges (C)."""
    qi = np.atleast_1d(np.asarray(q_i_C, dtype=np.float64))
    qj = np.atleast_1d(np.asarray(q_j_C, dtype=np.float64))
    if qi.shape != qj.shape:
        raise ValueError("q_i and q_j must have one shape")
    Vb, Vpm, fl = [], [], []
    for a, b in zip(qi, qj, strict=True):
        r = cap.cell_compartment(network["C_pm_F"], network["C_b_F"], a, b,
                                 network.get("phi_b_V", 0.0))
        Vb.append(r["V_b_V"])
        Vpm.append(r["V_pm_V"])
        f = r["solve"]["phi_floor_V"]
        fl.append(max(f["cell"], f["comp"]))
    return {"V_b_V": np.array(Vb), "V_pm_V": np.array(Vpm), "floor_V": np.array(fl)}


def free_energy(amounts_fmol: dict, volumes_pL: dict, temperature_K) -> float:
    """A.10's G = RT sum_nodes n (ln(n/V) - 1) (pJ), RT = 1e-3 R T pJ/fmol, exact SI R."""
    return sum(en.node_free_energy(n, volumes_pL[k], temperature_K)
               for k, n in amounts_fmol.items())


def energy(world: dict, constants=None) -> dict:
    """A.10 along the reference trajectory of a two-node world: R_closed's, a C11 world, or C6
    (A.6, loading with clearance, whose trajectory is ``linear``'s). The nodes' free-energy
    change dG(t) = sum_nodes [G(n(t)) - G(n(0))] (pJ), per node and in total, is evaluated per
    node as a stable increment in decimals, with a float64 second evaluation as its floor; the
    trajectory itself is returned with its floor. In C6 the cleared amount leaves both nodes,
    and dG is the loading's and the clearance's work together."""
    check_constants(constants)
    if world.get("reactions"):
        raise ValueError("a reaction's energy needs its standard potentials, which no world "
                         "declares")
    if "clearance_per_s" in world:
        lin = linear(world)
        traj = {"times_s": lin["times_s"], "form": "A.6",
                "amount_fmol": {n: lin["amount_fmol"][n][SPECIES] for n in lin["nodes"]},
                "floor_fmol": {n: lin["floor_fmol"][n][SPECIES] for n in lin["nodes"]}}
    else:
        traj = closed(world)
    T = world["temperature_K"]
    per_node, floors = {}, {}
    for node, n in traj["amount_fmol"].items():
        V = world["nodes"][node]["volume_pL"]
        n0 = _amount0(world, node)
        vals, fl = [], []
        for x in n:
            d = exact(x) - n0
            g = float(en.node_change(n0, d, V, T))
            rt = float(en.RT(T)) * 1e-3
            gf = rt * (float(d) * (np.log(float(n0) / float(V)) - 1.0) +
                       float(x) * np.log1p(float(d) / float(n0)))
            vals.append(g)
            fl.append(abs(g - gf) + 0.5 * float(np.spacing(abs(g))))
        per_node[node] = np.array(vals)
        floors[node] = np.array(fl)
    total = sum(per_node.values())
    return {"times_s": traj["times_s"], "form": traj["form"], "dG_pJ": total,
            "dG_floor_pJ": sum(floors.values()), "dG_by_node_pJ": per_node,
            "amount_fmol": traj["amount_fmol"], "floor_fmol": traj["floor_fmol"]}
