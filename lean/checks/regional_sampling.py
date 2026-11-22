"""FR-37. Check compiled collection, refill and remainder against the two-region draw formula."""

import json

import jax
import numpy as np

from cells.operators.wash_schedule import WashProgram


def compare(spec, result, tracer, start, drawn, expected_sample, expected_left):
    regions = ("A", "B")
    species = list(spec.model.species_ids).index(tracer)
    outside = [node.id for node in spec.model.extracellular]
    nodes = [outside.index(r) for r in regions]
    volume = np.asarray([spec.model.extracellular[n].volume_pL for n in nodes])
    np.testing.assert_array_equal(volume, [100.0, 100.0])
    (program,) = (op.data for op in spec.experiment.operators if isinstance(op.data, WashProgram))
    background = 1e-12  # mM, both starting regions and refill
    fractions = dict.fromkeys(regions, 0.0)
    for event in program.events:
        assert event.time == 0.001 and dict(event.buffer_mM)[tracer] == background
        fractions[event.node] = event.fraction
    np.testing.assert_array_equal(drawn, volume * [fractions[r] for r in regions])
    np.testing.assert_allclose(result.times, [0.0, 0.001, 0.002], rtol=0, atol=1e-15)

    def history(field):
        return np.asarray(getattr(result.history, field))[:, species, :][:, nodes]

    ref = np.asarray(result.final.layout.extracellular_amount_reference)[species, nodes]
    amount = history("extracellular_amount_increment") + ref
    collected = history("wash_collected_fmol")
    supplied = history("wash_supplied_fmol")
    tolerance = 16 * np.finfo(float).eps * sum(start)
    # Bookings are made on the step leaving the event time.
    np.testing.assert_array_equal(collected[:2], 0)
    np.testing.assert_array_equal(supplied[:2], 0)
    np.testing.assert_allclose(
        amount[:2] - background * volume, [start, start], rtol=0, atol=tolerance
    )
    np.testing.assert_allclose(supplied[-1], background * drawn, rtol=4e-15, atol=0)
    collected_excess = collected[-1] - background * drawn
    left_excess = amount[-1] - background * volume
    np.testing.assert_allclose(collected_excess, drawn * start / volume, rtol=0, atol=tolerance)
    np.testing.assert_allclose(left_excess, expected_left, rtol=0, atol=tolerance)
    sample = float(collected_excess.sum())
    np.testing.assert_allclose(sample, expected_sample, rtol=0, atol=tolerance)
    residual = amount + collected - supplied - amount[0]
    np.testing.assert_allclose(residual, 0, rtol=0, atol=tolerance)
    u, v = drawn
    a, b = volume
    cA, cB = start / volume
    sample_mean = sample / (u + v)
    chamber_mean = sum(start) / (a + b)
    bias = (u * b - v * a) * (cA - cB) / ((u + v) * (a + b))
    np.testing.assert_allclose(
        sample_mean - chamber_mean, bias, rtol=0, atol=tolerance / sum(drawn)
    )
    return {
        "drawn_pL_A_B": drawn.tolist(),
        "collected_excess_fmol": sample,
        "remainder_excess_fmol_A_B": left_excess.tolist(),
        "refill_fmol_A_B": supplied[-1].tolist(),
        "sample_excess_mM": sample_mean,
        "chamber_excess_mM": chamber_mean,
        "bias_mM": sample_mean - chamber_mean,
        "max_local_inventory_residual_fmol": float(np.abs(residual).max()),
    }


if __name__ == "__main__":
    from validation.sampling import uneven_draw

    jax.config.update("jax_enable_x64", True)
    cases = (
        ("unmixed", [8, 2], [100, 0], 8, [0, 2]),
        ("mixed", [5, 5], [50, 50], 5, [2.5, 2.5]),
        ("port", [8, 2], [75, 25], 6.5, [2, 1.5]),
    )
    results = {}
    for name, start, draw, sample, left in cases:
        spec, result = uneven_draw.run(name)
        results[name] = compare(
            spec, result, uneven_draw.S, np.array(start), np.array(draw), sample, left
        )
    print(json.dumps(results, indent=2))
