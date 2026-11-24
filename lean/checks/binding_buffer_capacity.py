"""Compare finite calcium increments in two experiments and test a manufactured binding case."""

import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.laws.reactions import rapid_binding


def measured_increments(study):
    free = np.asarray(study["free_Ca_mM"])
    total = np.asarray(study["total_Ca_mM"])
    free_steps, total_steps = np.diff(free), np.diff(total)
    assert np.all(free_steps > 0) and np.all(total_steps >= free_steps)
    return {
        "free_increments_mM": free_steps.tolist(),
        "total_increments_mM": total_steps.tolist(),
        "endpoint_total_over_free_increment": float((total[-1] - total[0]) / (free[-1] - free[0])),
    }


def compiled_control():
    # Single site with Kd = 1 mM. A zero binder total attains the lower bound.
    forms = (("empty", (), 0.0), ("bound", (("Ca", 1),), 0.0))
    net = rapid_binding.network(("Ca",), (("buffer", forms, 1.0, (("Ca", 1.0),)),))
    free = np.array([0.25, 0.5, 1.0, 2.0, 4.0])
    log_free = jnp.log(free[None, :])

    @jax.jit
    def total_at(binder):
        total, _ = rapid_binding.residual(
            log_free,
            jnp.zeros_like(log_free),
            jnp.full_like(log_free, binder),
            net["log_beta"],
            net["counts"],
            net["present"],
            jnp.ones_like(log_free, dtype=bool),
            xp=jnp,
        )
        return total[0]

    results = {}
    for binder in (0.0, 2.0):
        total = np.asarray(total_at(binder))
        slopes = np.diff(total) / np.diff(free)
        expected = 1 + binder / ((1 + free[:-1]) * (1 + free[1:]))
        np.testing.assert_allclose(slopes, expected, rtol=2e-15, atol=0)
        results[f"binder_{binder:g}_mM"] = slopes.tolist()
    return results


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    source = Path(__file__).with_name("data") / "paired_calibration_measurements.json"
    data = json.loads(source.read_text())
    measured = {
        key: measured_increments(data[key])
        for key in ("besarab1981_bsa_calcium@1", "gunther1998_bsa_calcium@1")
    }
    with jax.default_device(jax.devices("cpu")[0]):
        compiled = compiled_control()
    print(
        json.dumps(
            {"measured": measured, "synthetic_secant_slopes": compiled}, indent=2, allow_nan=False
        )
    )
