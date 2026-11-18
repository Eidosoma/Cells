"""FR-3's references on the registered worlds: the functions the protocol calls.

``reference(world)`` gives R-ode on any world, plus the closed forms, the equilibrium and the
quasi-steady comparison wherever the world admits them:
- the closed node's Riccati form and the depletion quadratic (one population, binding only);
- R-eq and the relaxation heat (binding only, every population on one closed node);
- the fixed-c forms on the reference side (association, dissociation, internalisation), with the
  depletion term stated;
- R-qss and epsilon (one population with internalisation, occupancy at its quasi-steady value).

``accessibility(worlds)`` gives Q4's occupancy ratios and relaxation rates. See
``REFERENCES_USAGE.md`` for the layouts.
"""

from __future__ import annotations

import numpy as np

from . import closed as C
from . import equilibrium as E
from . import kinetics, worlds


def _one(world):
    return len(world["populations"]) == 1


def reference(world: dict) -> dict:
    net = worlds.network(world)
    t = np.asarray(world["record_times_s"], dtype=np.float64)
    r = kinetics.integrate(net, t)
    out = {"times_s": t, "nodes": r["nodes"],
           "populations": [p["id"] for p in world["populations"]],
           "sites_fmol": [p.S for p in net.populations],
           "K_d_mM": [p.K_d for p in net.populations]}
    for key in ("n_fmol", "B_fmol", "R_fmol", "internalised_fmol", "heat_pJ", "work_pJ"):
        out[key] = r[key]
        out[f"{key}_floor"] = r[f"{key}_floor"]
    out["ledger_residual_pJ"] = r["ledger_residual_pJ"]
    out["occupancy"] = r["B_fmol"] / np.array([p.S for p in net.populations])
    binding_only = all(p.k_int == 0 for p in net.populations)
    faced = {p.node for p in net.populations}
    single_node = len(faced) == 1
    controls_flat = all(all(v == (1.0, 1.0) for v in (e[1] or {}).values()) for e in net.epochs)
    node = next(iter(faced))
    V = float(net.volumes[node])
    n0 = float(net.n0[node])
    p0 = net.populations[0]
    last_mb = [v[0] for v in (net.epochs[-1][1] or {0: (1.0, 1.0)}).values()]
    if binding_only and single_node and all(m > 0 for m in last_mb):
        # m_b scales k_on and k_off together, so the equilibrium is the multiplier's free limit
        N = n0 + sum(p.B0 for p in net.populations)
        eq = E.shared_node(N, V, [p.S for p in net.populations], [p.K_d for p in net.populations])
        rh = E.relaxation_heat(n0, [p.B0 for p in net.populations], V,
                               [p.S for p in net.populations], [p.K_d for p in net.populations],
                               net.RT)
        out["equilibrium"] = {"c_mM": eq["c_mM"], "B_fmol": eq["B_fmol"],
                              "heat_to_equilibrium_pJ": rh["heat_pJ"]}
        if _one(world) and controls_flat:
            d = C.depletion(p0.B0, n0, p0.S, p0.k_on, p0.k_off, V, t)
            out["riccati"] = {"B_fmol": d["B_fmol"], "n_fmol": d["n_fmol"],
                              "B_eq_fmol": d["B_eq_fmol"]}
    if _one(world) and controls_flat:
        c = n0 / V
        out["depletion_term"] = p0.S / (V * (p0.K_d + c))
        if binding_only:
            out["fixed_c"] = {"association_B_fmol": C.association(p0.B0, p0.S, p0.k_on,
                                                                  p0.k_off, c, t),
                              "dissociation_B_fmol": C.dissociation(p0.B0, p0.k_off, t)}
        else:
            fi = C.internalisation(p0.B0, p0.S, p0.k_on, p0.k_off, p0.k_int, c, t)
            out["fixed_c"] = {"internalisation_B_fmol": fi["B_fmol"],
                              "internalised_fmol": fi["internalised_fmol"]}
            KM = (p0.k_off + p0.k_int) / p0.k_on
            if abs(p0.B0 - p0.S * c / (KM + c)) <= 1e-12 * p0.S:
                q = C.qss(n0, p0.S, p0.k_on, p0.k_off, p0.k_int, V, t)
                i = r["nodes"].index(node)
                uptake = n0 - r["n_fmol"][-1, i]
                out["qss"] = {"n_fmol": q["n_fmol"], "epsilon": q["epsilon"],
                              "K_M_mM": q["K_M_mM"], "a_fmol_per_s": q["a_fmol_per_s"],
                              "b_fmol": q["b_fmol"],
                              "relative_error_over_uptake":
                                  float(np.max(np.abs(r["n_fmol"][:, i] - q["n_fmol"])) / uptake)}
    return out


def accessibility(world_by_alpha: dict) -> dict:
    """Q4: equilibrium occupancy ratios theta(alpha)/theta(1) at the true V (R-eq), the
    occupancy over the declared sites at alpha = 1's, and each relaxation's rate."""
    eq, rate = {}, {}
    for alpha, world in world_by_alpha.items():
        net = worlds.network(world)
        p = net.populations[0]
        node = p.node
        V, n0 = float(net.volumes[node]), float(net.n0[node])
        r = E.shared_node(n0 + p.B0, V, [p.S], [p.K_d])
        eq[alpha] = r["B_fmol"][0]
        rate[alpha] = p.k_on * r["c_mM"] + p.k_off
    S1 = eq[1.0]
    return {"theta_ratio": {a: eq[a] / S1 for a in eq},
            "relaxation_rate_per_s": rate}
