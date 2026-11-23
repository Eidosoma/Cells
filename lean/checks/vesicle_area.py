"""Synthetic FR-31 holds with scaled areas and initial vesicle counts."""

import argparse
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import pairwise
from pathlib import Path


def check(areas, counts, exposure, expected):
    """Compare the exponential formula to independently specified rational results."""
    weights = [Decimal(n) / sum(counts) for n in counts]
    mean = sum(w * a for w, a in zip(weights, areas, strict=True))
    low, high = min(areas), max(areas)

    def survival(a):
        return (-exposure * a).exp()

    lower = survival(mean)
    mixture = sum(w * survival(a) for w, a in zip(weights, areas, strict=True))
    upper = (
        lower
        if low == high
        else ((high - mean) * survival(low) + (mean - low) * survival(high)) / (high - low)
    )
    tolerance = Decimal("1e-48")
    for computed, exact in zip((lower, mixture, upper), expected, strict=True):
        oracle = Decimal(exact.numerator) / exact.denominator
        assert abs(computed - oracle) <= tolerance, (areas, computed, exact)
    assert lower <= mixture + tolerance and mixture <= upper + tolerance
    return dict(
        areas=areas,
        counts=counts,
        mean_area=str(mean.normalize()),
        lower=float(lower),
        population=float(mixture),
        upper=float(upper),
    )


def run():
    with localcontext() as ctx:
        ctx.prec = 60
        q = Decimal(2).ln()
        return {
            "endpoints": check(
                [1, 3], [1, 1], q, (Fraction(1, 4), Fraction(5, 16), Fraction(5, 16))
            ),
            "interior": check(
                [1, 2, 3], [1, 2, 1], q, (Fraction(1, 4), Fraction(9, 32), Fraction(5, 16))
            ),
            "one_area": check([2, 2], [1, 3], q, (Fraction(1, 4),) * 3),
            "zero_exposure": check([1, 3], [1, 3], Decimal(0), (Fraction(1),) * 3),
        }


def osmotic_measurements():
    """Check quantities that can be reconstructed without matching vesicles across cohorts."""
    data = Path(__file__).with_name("data")
    charged = json.loads((data / "saha2020_osmotic_rupture.json").read_text(), parse_float=Decimal)
    neutral = json.loads((data / "shibly2016_swelling.json").read_text(), parse_float=Decimal)
    rupture = charged["rupture"]
    rates, external = rupture["rate_per_s"], rupture["external_tension_mN_m"]
    assert len(rates) == len(external) == len(rupture["rate_sd_per_s"]) == 3
    assert all(a < b for a, b in pairwise(rates)) and all(a < b for a, b in pairwise(external))
    swelling = charged["swelling"]
    hold = neutral["rupture_traces"]
    dr = hold["plateau_fractional_radius_change"]
    # Eq. 6 uses the first-order area change 2 Δr/r₀. The spherical area ratio is exact.
    nominal = 2 * hold["area_modulus_mN_m"] * dr
    assert (
        hold["reported_osmotic_tension_mN_m"] + hold["external_tension_mN_m"]
        == hold["reported_total_tension_mN_m"]
    )
    return dict(
        charged_rate_ratio_high_to_low=float(rates[-1] / rates[0]),
        charged_rupture_osmolarity_mOsm_L=rupture["initial_osmolarity_difference_mOsm_L"],
        charged_swelling_osmolarities_mOsm_L=swelling["initial_osmolarity_difference_mOsm_L"],
        charged_swelling_tensions_mN_m=[
            float(x) for x in swelling["geometry_osmotic_tension_mN_m"]
        ],
        charged_rate_matched_tension_mN_m=float(rupture["rate_matched_osmotic_tension_mN_m"]),
        neutral_plateau_spherical_area_ratio=float((1 + dr) ** 2),
        neutral_nominal_osmotic_tension_mN_m=float(nominal),
        neutral_reported_osmotic_tension_mN_m=float(hold["reported_osmotic_tension_mN_m"]),
        neutral_reported_total_tension_mN_m=float(hold["reported_total_tension_mN_m"]),
        individual_absolute_areas_and_complete_event_times="unavailable",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--osmotic-evidence",
        action="store_true",
        help="Read the published swelling and rupture measurements",
    )
    result = osmotic_measurements() if parser.parse_args().osmotic_evidence else run()
    print(json.dumps(result, indent=2, allow_nan=False))
