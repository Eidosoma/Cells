"""Self-check of FR-43 part 2's reference model (numpy/scipy only; it compiles no engine world).

About 3 s on one core:
- the right-hand side conserves the machines and every declared moiety (residues in transit
  counted), and its N books add up, at the declared state and at perturbed states;
- its heat and work rates close the free-energy balance d(F + U + G_transit)/dt = works - heats,
  with the gradient of the free energy taken by the chain rule from F's own formula;
- the source route alone (gene unit idle) follows its closed form n_X = n_X0 exp(-k t);
- water alone (reaction off) follows the closed-form relation between V and t, and the held
  bath's work is 1e-3 psi_out (V - V0);
- recharging's sign split adds up to its signed integral.
"""

import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fr43p2_reference import World, integrate  # noqa: E402

WORLDS = os.path.join(HERE, "worlds")
STRUCTURES = ["C2.8-swelling-pair-sink-dt0p01.json", "C2.3-source-dt0p5.json",
              "C2.6-swelling-cell-dt0p01.json"]


def _world(name, **kw):
    return World(os.path.join(WORLDS, name), **kw)


def _states(world, count=3, seed=7):
    """The declared state and perturbed positive states (complexes spread over the stages)."""
    rng = np.random.default_rng(seed)
    out = [world.y0()]
    for _ in range(count):
        y = world.y0()
        ns = len(world.species)
        y[:ns] *= rng.uniform(0.3, 3.0, ns)
        if world.gene:
            share = rng.dirichlet(np.ones(world.chain.stages + 1))
            y[world._iF] = world.machines_total * share[0]
            y[world._iC:world._iC + world.chain.stages] = world.machines_total * share[1:]
        if world.water:
            y[world.pos["V"]] = rng.uniform(0.8, 2.5)
        out.append(y)
    return out


def _free_energy_rate(world, y, dy):
    """d(F + U + G_transit)/dt along dy, by the chain rule on F's, U's and G_transit's formulas."""
    RT = world.RT_pJ
    V = y[world.pos["V"]] if world.water else world.V0
    lin = world.f_linear_terms()
    rate = sum(RT * (math.log(y[i] / V) + lin[s]) * dy[i] for i, s in enumerate(world.species))
    if world.water:
        w = world.water
        dF_dV = -RT * sum(y[:len(world.species)]) / V
        dU_dV = 1e-3 * (w.bulk_modulus * (V / w.v_ref - 1.0) + w.p0)
        rate += (dF_dV + dU_dV) * dy[world.pos["V"]]
    if world.gene:
        ch = world.chain
        mu_res = world.gene_mu[ch.product] / ch.residues
        rate += sum(RT * mu_res * ch.per_stage * j * dy[world._iC + j] for j in range(ch.stages))
    return rate


def test_rhs_conserves_and_closes_its_books():
    for name in STRUCTURES:
        world = _world(name)
        for y in _states(world):
            dy = world.rhs(0.0, y)
            f = world.fluxes(y)
            dn = {s: dy[i] for i, s in enumerate(world.species)}
            if world.gene:
                ch = world.chain
                dC = dy[world._iC:world._iC + ch.stages]
                assert abs(dy[world._iF] + sum(dC)) <= 1e-12 * world.machines_total
                dW = ch.per_stage * sum(j * dC[j] for j in range(ch.stages))
                for mid, w in world.moieties.items():
                    w_res = w.get(ch.product, 0.0) / ch.residues
                    terms = [w.get(s, 0.0) * dn[s] for s in world.species] + [w_res * dW]
                    assert abs(sum(terms)) <= 1e-12 * sum(abs(t) for t in terms), (name, mid)
                assert abs(dn["N"] - f["gene_rate_N"] - f["network_rate_N"]) \
                    <= 1e-12 * (abs(f["gene_rate_N"]) + abs(f["network_rate_N"]))
            for rx in world.reactions:  # the network's own moieties
                for mid in {k for s in rx.nu for k in world.net_moieties.get(s, {})}:
                    assert sum(rx.nu[s] * world.net_moieties[s].get(mid, 0.0) for s in rx.nu) == 0
            acc = f["acc"]
            booked = (acc.get("W.bath", 0.0) - acc.get("H.water", 0.0) - acc.get("H.tx", 0.0)
                      - acc.get("H.deg", 0.0) - acc.get("H.rc", 0.0)
                      + sum(v for k, v in acc.items() if k.startswith("dG.net.")))
            scale = sum(abs(v) for k, v in acc.items() if k.startswith(("W.", "H.", "dG.")))
            assert abs(_free_energy_rate(world, y, dy) - booked) <= 1e-11 * scale, name


def test_source_route_alone_follows_its_closed_form():
    world = _world("C2.3-source-dt0p5.json")
    world.chain.k_init = 0.0  # the gene unit idle: no initiation, recharging or degradation
    world.transfer.capacity = 0.0
    world.degradation.rate = 0.0
    times = [0.0, 150.0, 300.0, 600.0]
    Y, _ = integrate(world, times, rtol=1e-11)
    (rx,) = world.reactions
    x0, n0 = world.n0[world.idx["X"]], world.n0[world.idx["N"]]
    for t, y in zip(times, Y):
        x = x0 * math.exp(-rx.k * t)
        assert abs(y[world.idx["X"]] - x) <= 1e-10 * x0
        assert abs(y[world.idx["N"]] - (n0 + x0 - x)) <= 1e-10 * x0
        assert abs(y[world.pos[f"ext.net.{rx.rid}"]] - (x0 - x)) <= 1e-10 * x0


def test_water_alone_follows_its_closed_form():
    world = _world("C2.6-swelling-cell-dt0p01.json")
    world.reactions[0].k = 0.0  # the reaction off: the osmolytes are fixed
    w = world.water
    assert w.bulk_modulus == 0.0 and w.p0 == 0.0
    times = [0.0, 10.0, 40.0]
    Y, _ = integrate(world, times, rtol=1e-11)
    v_e = sum(world.n0) / sum(world.bath_conc.values())
    kappa_cb = 1e15 * w.area * w.lp * w.availability * world.RT_J * sum(world.bath_conc.values())
    for t, y in zip(times, Y):
        v = y[world.pos["V"]]
        # dV/dt = kappa (n/V - c_b)  =>  -(V - V0) - V_e ln((V_e - V)/(V_e - V0)) = kappa c_b t
        lhs = -(v - world.V0) - v_e * math.log((v_e - v) / (v_e - world.V0))
        assert abs(lhs - kappa_cb * t) <= 1e-10 * max(1.0, kappa_cb * t)
        assert abs(y[world.pos["W.bath"]] - 1e-3 * w.psi_out * (v - world.V0)) \
            <= 1e-12 * abs(1e-3 * w.psi_out)


def test_recharging_split_adds_up():
    world = _world("C2.3-sink-dt0p5.json")
    times = [0.0, 30.0, 45.0]  # recharging runs backward until about 36 s, then forward
    Y, info = integrate(world, times, rtol=1e-6, atol=np.full(len(world.names), 1e-20))
    assert len(info["recharge_sign_changes_s"]) == 1
    prod, cons = info["rc_produced"], info["rc_consumed"]
    for k, y in enumerate(Y):
        assert abs(prod[k] - cons[k] - y[world.pos["ext.rc"]]) <= 1e-15
    assert prod[-1] > 0 and cons[-1] > 0
    assert all(b >= a for a, b in zip(prod, prod[1:])) and all(b >= a for a, b in zip(cons, cons[1:]))
