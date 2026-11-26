"""Replay XC0 definition-time charge admission and audit each rounding step with exact rationals."""

import json
import math
from copy import deepcopy
from fractions import Fraction

from cells.definitions.specs import ConfigError, parse_spec
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from validation import id_table
from validation.xenopus_bioelectric import xc0_worlds as xc0

ANCHOR_REFUSAL = "Initial inventory, fixed background and explicit charge anchor disagree"


def replay(name, original, *, offset_steps=0):
    raw = deepcopy(original)
    cell = raw["model"]["cells"][0]
    anchor = cell["initial_charge_C"]
    intended_fixed = cell["fixed_charge_equivalent_fmol"]
    fixed = intended_fixed + offset_steps * math.ulp(intended_fixed)
    cell["fixed_charge_equivalent_fmol"] = fixed
    defect = Fraction(fixed) - Fraction(intended_fixed)

    terms = [s["valence"] * cell["initial_amount_fmol"][s["id"]] for s in raw["model"]["species"]]
    ions = sum(map(Fraction, terms))
    k = CHARGE_PER_FMOL
    quotient = anchor / k
    ionic_sum = math.fsum(terms)
    assert intended_fixed == quotient - ionic_sum
    net = math.fsum([fixed, *terms])
    charge = k * net
    residual = charge - anchor

    # Fraction(float) reads its exact stored value. Each reference uses the actual
    # operands of that operation, so error from an earlier stage is counted once.
    k_exact = Fraction(k)
    stages = (
        ("division", quotient, Fraction(anchor) / k_exact, k_exact),
        ("ionic_sum", ionic_sum, ions, k_exact),
        ("background", fixed, Fraction(quotient) - Fraction(ionic_sum) + defect, k_exact),
        ("net_sum", net, Fraction(fixed) + ions, k_exact),
        ("conversion", charge, k_exact * Fraction(net), 1),
        ("comparison", residual, Fraction(charge) - Fraction(anchor), 1),
    )
    budget = Fraction(0)
    errors_in_ulps = {}
    for stage, value, exact, to_coulombs in stages:
        spacing = Fraction(math.ulp(value))
        error = abs(Fraction(value) - exact)
        assert 2 * error <= spacing, (name, stage, error, spacing)
        errors_in_ulps[stage] = float(error / spacing)
        budget += to_coulombs * spacing / 2

    mismatch = k_exact * defect
    floor = Fraction(1e-20)  # The original parser's binary64 literal in C.
    tolerance = max(floor, budget)
    assert abs(Fraction(residual) - mismatch) <= budget
    if offset_steps:
        assert abs(mismatch) > tolerance + budget, name
    expected = offset_steps == 0
    assert (abs(Fraction(residual)) <= tolerance) == expected, name
    try:
        parse_spec(id_table.translate(raw))
        admitted = True
    except ConfigError as exc:
        if ANCHOR_REFUSAL not in str(exc):
            raise
        admitted = False

    return dict(
        case=name,
        offset_steps=offset_steps,
        defect_fmol=float(defect),
        planted_charge_C=float(mismatch),
        background_fmol=fixed,
        anchor_C=anchor,
        residual_C=residual,
        budget_C=float(budget),
        tolerance_C=float(tolerance),
        errors_in_ulps=errors_in_ulps,
        expected_admission=expected,
        absolute_floor_admits=abs(Fraction(residual)) <= floor,
        scale_bound_admits=abs(Fraction(residual)) <= tolerance,
        native_admits=admitted,
    )


def main():
    data = xc0.inputs()
    volume = xc0.volume_pl(data)
    rows = [replay("baseline", xc0.world(d=data))]
    for sodium in (21, 38):
        for power in range(18, 23):
            b_amount = 1.5 * 2**power
            raw = xc0.world(d=data, cell_mm={"cell_1": {"Na": sodium, "B": b_amount / volume}})
            name = f"Na{sodium}-B-binade{power}"
            rows.append(replay(name, raw))
            if sodium == 38 and power == 20:
                for steps in (-4, 4):
                    rows.append(replay(f"{name}-offset{steps:+d}", raw, offset_steps=steps))

    # These monovalent amounts have exact ionic sum S, strictly within one binade.
    # At ±half spacing either nearest background leaves the same absolute residual.
    for power, sign in ((19, 1), (20, 1), (20, -1), (26, 0)):
        total = 1.5 * 2**power
        anchor = CHARGE_PER_FMOL * (sign * math.ulp(total) / 2)
        raw = xc0.world(d=data)
        raw["model"]["cells"][0] = xc0.node_entry(
            "cell_1", dict(Na=total, K=3, Cl=1, A=1, B=1), 1.0, anchor, data, ()
        )
        name = f"binade{power}-half-spacings{sign:+d}"
        row = replay(name, raw)
        assert abs(row["residual_C"]) == abs(anchor)
        rows.append(row)
    return dict(
        model=id_table.translate(xc0.MODEL),
        charge_per_fmol_C=CHARGE_PER_FMOL,
        original_floor_C=1e-20,
        rows=rows,
        all_native_expected=all(r["native_admits"] == r["expected_admission"] for r in rows),
        all_scale_expected=all(r["scale_bound_admits"] == r["expected_admission"] for r in rows),
        balanced_refusals=[
            r["case"] for r in rows if r["expected_admission"] and not r["native_admits"]
        ],
        erroneous_admissions=[
            r["case"] for r in rows if not r["expected_admission"] and r["native_admits"]
        ],
    )


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result["all_native_expected"] else 1)
