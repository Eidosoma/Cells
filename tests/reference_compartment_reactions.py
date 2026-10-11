"""Independent scalar polynomial rates and SciPy references; no Cells/JAX imports."""

import math
from bisect import bisect_right

import numpy as np
from scipy.integrate import solve_ivp


def reference(raw, times, *, method="DOP853"):
    model = raw["model"]
    species = sorted(model["species"], key=lambda s: s["id"])
    compartments = sorted(model["compartments"], key=lambda c: c["id"])
    reactions = sorted(model["reactions"], key=lambda r: r["id"])
    ids = [s["id"] for s in species]
    owners = [c["id"] for c in compartments]
    n_species, n_compartments, n_reactions = len(ids), len(owners), len(reactions)
    n = np.array([[c["initial_amount_fmol"][s] for c in compartments] for s in ids])
    initial = np.concatenate((n.ravel(), np.zeros(2 * n_reactions)))
    volume = [c["volume_pL"] for c in compartments]
    standard = model["standard_concentration_mM"]
    mu = {s["id"]: s["standard_mu_RT"] for s in species}
    RT = 6.02214076e23 * 1.380649e-23 * model["temperature_K"] * 1e-3
    schedule = raw["experiment"]["reaction_controls"]
    switches = [p["time"] for p in schedule]
    nodes = sorted({0.0, raw["experiment"]["end_time"], *switches})
    result = np.empty((len(times), len(initial)))
    state, calls = initial.copy(), 0
    for start, end in zip(nodes, nodes[1:], strict=False):
        control = schedule[bisect_right(switches, start) - 1]["multipliers"]

        def rhs(_, values, control=control):
            nonlocal calls
            calls += 1
            amounts = values[: n.size].reshape(n.shape)
            if np.any(amounts <= 0):
                raise ValueError("Reference left the positive chemical domain")
            derivative, extent, dissipation = np.zeros_like(amounts), [], []
            for reaction in reactions:
                c = owners.index(reaction["compartment"])
                a = {s: amounts[i, c] / volume[c] / standard for i, s in enumerate(ids)}
                dmu = math.fsum(
                    coef * mu[s] for s, coef in reaction["products"].items()
                ) - math.fsum(coef * mu[s] for s, coef in reaction["reactants"].items())
                kf = reaction["forward_rate_per_s"] * control[reaction["id"]]
                forward = (
                    kf
                    * volume[c]
                    * standard
                    * math.prod(a[s] ** coef for s, coef in reaction["reactants"].items())
                )
                reverse = (
                    kf
                    * math.exp(dmu)
                    * volume[c]
                    * standard
                    * math.prod(a[s] ** coef for s, coef in reaction["products"].items())
                )
                net = forward - reverse
                affinity = (
                    -dmu
                    + math.fsum(coef * math.log(a[s]) for s, coef in reaction["reactants"].items())
                    - math.fsum(coef * math.log(a[s]) for s, coef in reaction["products"].items())
                )
                for i, s in enumerate(ids):
                    derivative[i, c] += (
                        reaction["products"].get(s, 0) - reaction["reactants"].get(s, 0)
                    ) * net
                extent.append(net)
                dissipation.append(RT * net * affinity)
            return np.concatenate((derivative.ravel(), extent, dissipation))

        solution = solve_ivp(
            rhs, (start, end), state, method=method, rtol=2e-12, atol=2e-15, dense_output=True
        )
        if not solution.success:
            raise ValueError(solution.message)
        selected = (np.asarray(times) >= start) & (np.asarray(times) <= end)
        result[selected] = solution.sol(np.asarray(times)[selected]).T
        state = solution.y[:, -1]
    return {
        "amount": result[:, : n.size].reshape(-1, n_species, n_compartments),
        "reaction_extent": result[:, n.size : n.size + n_reactions],
        "dissipated_energy_pJ": result[:, n.size + n_reactions :],
        "rhs_calls": calls,
    }


def binding_equilibrium(calcium_total, buffer_total, kd):
    # Stable smaller root of b^2 - (Ct + Bt + Kd)b + Ct*Bt = 0.
    total = calcium_total + buffer_total + kd
    bound = (
        2
        * calcium_total
        * buffer_total
        / (total + math.sqrt(total**2 - 4 * calcium_total * buffer_total))
    )
    return calcium_total - bound, buffer_total - bound, bound
