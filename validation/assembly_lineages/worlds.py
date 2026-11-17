"""World definitions for the assembly-lineage family: GARD's T2-02-like comparison world.

`t2_02_like` follows the numbers the Plastic Heredity preprint states for its contract T2-02
(v5.0, Appendix F, "Common state, kinetics and environment" and the T2-02 row; Zenodo
10.5281/zenodo.22143269, CC BY 4.0; numbers cited under D186):

- 100 molecular types; one catalytic matrix per environment, beta_ij = exp(-4 + 4 Z_ij) with
  independent standard-normal Z_ij and the diagonal kept;
- a constant, uniform held reservoir, rho_i = 0.01; k_f = 1e-2 and k_b = 1e-4, so the transfer
  constant K = k_f / k_b = 100 (family.py; the join constant derives from it exactly);
- an initial mass of 40, of 40 distinct types sampled uniformly without replacement;
- direct categorical single-molecule events, growing exactly to mass 80;
- an exact-size multivariate-hypergeometric split, floor(N / 2) molecules to the first daughter,
  and the first daughter continues; no retry on extinction.

It is "T2-02-like", a comparison world (D192), not the preprint's runs: the matrix and the
founder are drawn here from recorded seeds (NumPy's default generator), the engine's streams are
its own, and the preprint's 40,000-event guard (which would fission the current state, and was
never reached in its retained campaigns) is the engine's event guard, which stops the lineage.
"""

import numpy as np

from cells.models.assembly_lineages import (
    CONTINUATION,
    EXCHANGE_LAW,
    FISSION,
    GARD_PAIR_CONSISTENT,
    MODEL_ID,
)

TYPES = 100
MU, SIGMA = -4.0, 4.0
SUPPLY = 0.01
JOIN, LEAVE = 1e-2, 1e-4
FOUNDER_SIZE = 40
FISSION_SIZE = 80
GUARD = 40000


def catalysis_matrix(seed, count=TYPES):
    """beta = exp(MU + SIGMA Z), Z standard normal from NumPy's default generator at `seed`."""
    z = np.random.default_rng(seed).standard_normal((count, count))
    return np.exp(MU + SIGMA * z)


def founder(seed, count=TYPES, size=FOUNDER_SIZE):
    """`size` distinct types, sampled uniformly without replacement, one molecule each."""
    counts = np.zeros(count, dtype=np.int64)
    counts[np.random.default_rng(seed).choice(count, size, replace=False)] = 1
    return counts


def t2_02_like(matrix_seed, founder_seed):
    return {
        "types": {"prefix": "t", "count": TYPES, "transfer_constant": JOIN / LEAVE},
        "supply": SUPPLY,
        "exchange": {"law": EXCHANGE_LAW, "leave_rate": LEAVE},
        "law_data": {"catalysis_matrix": catalysis_matrix(matrix_seed).tolist()},
        "founder": founder(founder_seed).tolist(),
        "fission": {
            "operator": FISSION,
            "size": FISSION_SIZE,
            "partition": {"rule": "exact_fraction", "fraction": 0.5},
        },
        "continuation": {
            "operator": CONTINUATION,
            "daughter": "first",
            "empty": "extinct",
            "sink": "discard",
        },
        "units": {"time": "nominal", "temperature_K": None},
    }


def definition(world, law=GARD_PAIR_CONSISTENT, *, fissions, seed, environment=0, lineage=0):
    """A single-lineage definition of `world`; law None runs the exchange law alone (the world
    then holds no law_data)."""
    model = {"id": MODEL_ID, "world": world}
    if law is not None:
        model["rate_factor"] = {"law": law}
    return {
        "schema_version": 1,
        "model": model,
        "experiment": {
            "fissions": fissions,
            "growth_event_limit": GUARD,
            "trace": True,
            "uniforms": False,
        },
        "execution": {
            "backend": "cpu",
            "precision": "float64",
            "mode": "single_lineage",
            "stream": {"seed": seed, "environment": environment, "lineage": lineage, "branch": 0},
        },
    }
