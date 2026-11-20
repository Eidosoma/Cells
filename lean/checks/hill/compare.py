"""Compare the compiled Cells Hill factors to the two normalized forms of GRN.Dynamics.hill."""

import json
from decimal import Decimal, localcontext
from itertools import product

import jax
import jax.numpy as jnp
import numpy as np

from cells.laws.reactions import hill_factors
from tests.unit.test_hill_factors import K_VALUES, N_VALUES, X_VALUES


def compare():
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Use the Cells CPU environment with JAX_ENABLE_X64=1")
    cases = list(product(X_VALUES, K_VALUES, N_VALUES))
    x, k, n = np.asarray(cases).T
    tolerance = 4 * np.finfo(np.float64).eps
    errors = {}
    for name, basal, high in (("hill_activation", 0, 1), ("hill_inhibition", 1, 0)):
        with localcontext() as ctx:
            ctx.prec = 65
            expected = []
            for case in cases:
                concentration, half, exponent = map(Decimal.from_float, case)
                ratio = (concentration / half) ** exponent
                expected.append(float((basal + high * ratio) / (1 + ratio)))

        def evaluate(x, k, n, kind=hill_factors.KINDS[name]):
            return hill_factors.factor(jnp.log(x), k, n, kind, xp=jnp)

        actual = np.asarray(jax.jit(evaluate)(x, k, n))
        np.testing.assert_allclose(actual, expected, atol=tolerance, rtol=0)
        errors[name] = float(np.max(np.abs(actual - expected)))
    return {"cases": len(cases) * len(errors), "atol": tolerance, "max_abs_error": errors}


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
