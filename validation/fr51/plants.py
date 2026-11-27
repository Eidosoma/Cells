"""FR-51's registered plants (fr51-channel-block-v1 §3): each is the engine with one planted change,
in this process only.

**How a plant runs.** Each is a context manager. While it is entered, the engine runs planted, and
so does the judge's adapter (validation/fr51/engine.py), whose caches it clears on entry and exit.
Nothing is written to disk.

**How each is judged.** The plants judged against the references are in JUDGED: the plant, its
criterion and its registered cases. `python -m validation.fr51.plants --references DIR --out OUT`
judges each by the tagged judge's own check functions against the tagged references, and each must
fail. The engine-only plants fail their tests:
- ZERO_PLANT fails criterion Z;
- count_scaled fails C1;
- term_dropped fails RUN's item 4.
"""

import argparse
import contextlib
import json
from pathlib import Path

import numpy as np

from cells.definitions import surface_pump_v3_spec as spec_v3
from cells.laws import electrochemistry
from cells.laws.channels import open_channel_block as block_law
from cells.models import surface_pump_v3 as v3
from validation.fr51 import engine, judge


def _clear():
    engine.world.cache_clear()
    engine.program.cache_clear()
    engine._values.cache_clear()


@contextlib.contextmanager
def _patched(owner, name, value):
    original = getattr(owner, name)
    setattr(owner, name, value)
    _clear()
    try:
        yield
    finally:
        setattr(owner, name, original)
        _clear()


def swapped_concentrations():
    """P's plant: c_i and c_o exchanged in the flux."""
    original = v3.selective_flux

    def planted(c_from, c_to, *args, **kwargs):
        return original(c_to, c_from, *args, **kwargs)

    return _patched(v3, "selective_flux", planted)


def flipped_side():
    """B's plant (i): the side's sign flipped, s -> -s, in every exponent."""
    original = block_law.exponent_per_volt
    return _patched(block_law, "exponent_per_volt", lambda steep, t: -original(steep, t))


def reversal_valence_flipped():
    """B's plant (ii): E with the wrong sign of its valence. E is electrochemistry's since FR-64
    moved it there, unchanged; the engine calls it through that module, so the patch is seen."""
    original = electrochemistry.reversal_potential

    def planted(inside, outside, valence, temperature, *, xp=np):
        return original(inside, outside, -valence, temperature, xp=xp)

    return _patched(electrochemistry, "reversal_potential", planted)


def _layout_plant(change):
    """A plant on the blocked populations' layout fields: change(fields, spec) -> fields."""
    original = v3.block_initial_values

    def planted(spec, structure):
        return change(original(spec, structure), spec)

    return _patched(v3, "block_initial_values", planted)


def weights_swapped():
    """B's plant (iii): the modes' weights in reverse order (B1's two modes swapped). A population
    without a block keeps u = 1: its slots share K(0) = 1 and steepness 0."""
    return _layout_plant(
        lambda f, spec: f | {"channel_block_weight": f["channel_block_weight"][::-1]}
    )


def effective_without_sign():
    """B's plant (iv), V7's plant row: the effective-valence exponent without sgn(z_B); the
    electrical-distance form keeps s z_B delta."""

    def planted(self):
        s = block_law.SIDES[self.side]
        return tuple(
            s
            * (
                self.valence * m.electrical_distance
                if m.effective_valence is None
                else m.effective_valence
            )
            for m in self.modes
        )

    return _patched(spec_v3.ChannelBlock, "steepness", planted)


def reversal_read_as_voltage():
    """R's plant: a reversal reference read as the membrane voltage."""
    return _layout_plant(
        lambda f, spec: f | {"channel_block_reversal": np.zeros_like(f["channel_block_reversal"])}
    )


def literal_fraction():
    """S's plant: the literal u = 1 - sum_k w_k theta_k."""

    def planted(weight, free):
        total = weight[0] * (1 - free[0])
        for k in range(1, weight.shape[0]):
            total = total + weight[k] * (1 - free[k])
        return 1 - total

    return _patched(block_law, "unblocked_fraction", planted)


def zero_plant():
    """Z's plant: u = sum_k w_k/(1 + c_B/K_k), unnormalized: 0.9999999999999999 at c_B = 0 for
    (0.7, 0.2, 0.1)."""

    def planted(weight, free):
        total = weight[0] * free[0]
        for k in range(1, weight.shape[0]):
            total = total + weight[k] * free[k]
        return total

    return _patched(block_law, "unblocked_fraction", planted)


def count_scaled():
    """C's plant: the blocker concentration scaled by the population's abundance (its count)."""

    def change(f, spec):
        scaled = f["channel_block_concentration_mM"].copy()
        for slot, channel in enumerate(spec.model.channels):
            scaled[slot] *= channel.abundance
        return f | {"channel_block_concentration_mM": scaled}

    return _layout_plant(change)


def _terms_plant(change):
    original = v3.channel_block_terms

    def planted(*args, **kwargs):
        return change(original(*args, **kwargs))

    return _patched(v3, "channel_block_terms", planted)


def term_dropped():
    """G's plant (i), and RUN's: the block's term dropped, T_V = u G_max."""
    return _terms_plant(lambda t: t._replace(voltage_term_S=t.block.u * t.g_max_S))


def todays_term():
    """G's plant (ii): today's unblocked G_max alone."""
    return _terms_plant(lambda t: t._replace(voltage_term_S=t.g_max_S))


def without_e():
    """E's plant (i): the concentration terms without their part through E."""
    return _terms_plant(
        lambda t: t._replace(
            outside_term=t.outside_term - t.outside_through_e,
            inside_term=t.inside_term - t.inside_through_e,
        )
    )


def e1_reversal_at_e2():
    """E's plant (ii): the terms evaluated with E1's reversal potential (B1 at E1's concentrations)
    at E2's state."""
    original = electrochemistry.reversal_potential
    case = next(c for c in engine.spec_of()["cases"] if c["id"] == "B1_two_modes_E1")
    c_i, c_o = float(case["c_i_mM"]), float(case["c_o_mM"])

    def planted(inside, outside, valence, temperature, *, xp=np):
        ones = xp.ones_like(inside)
        return original(c_i * ones, c_o * ones, valence, temperature, xp=xp)

    return _patched(electrochemistry, "reversal_potential", planted)


# The plants judged against the references: {name: (plant, criterion, its registered cases)}.
JUDGED = {
    "P: c_i and c_o exchanged": (swapped_concentrations, "P", ("P2_K_unequal",)),
    "B (i): the side's sign flipped": (flipped_side, "B-u", ("B1_two_modes_E1",)),
    "B (ii): E with the wrong sign of its valence": (
        reversal_valence_flipped,
        "B-u",
        ("B1_two_modes_E1",),
    ),
    "B (iii): the two modes' weights swapped": (weights_swapped, "B-u", ("B1_two_modes_E1",)),
    "B (iv), V7: the effective valence without sgn(z_B)": (
        effective_without_sign,
        "B-u",
        ("B4_anion_effective",),
    ),
    "R: a reversal reference read as the membrane voltage": (
        reversal_read_as_voltage,
        "R",
        ("B1_two_modes_E1",),
    ),
    "S: the literal 1 - sum w theta": (
        literal_fraction,
        "S",
        ("S1_strong_one_mode", "S2_strong_two_modes"),
    ),
    "G (i): the block's term dropped": (term_dropped, "G", ("B1_two_modes_E1",)),
    "G (ii): today's G_max alone": (todays_term, "G", ("G3_steep_Na_outside_voltage",)),
    "E (i): without the part through E": (without_e, "E", ("B1_two_modes_E1",)),
    "E (ii): E1's reversal at E2's state": (e1_reversal_at_e2, "E", ("B1_two_modes_E2",)),
}


def judge_plants(references):
    """{plant: {caught, cases: {case: {passed, worst}}}}. A plant is caught when its criterion fails
    on one of its cases."""
    out = {}
    for name, (plant, criterion, cases) in JUDGED.items():
        check = judge.CHECKS[criterion][0]
        found = {}
        with plant():
            for case_id in cases:
                ref = references[case_id]
                passed, worst = check(engine.engine(case_id, ref.voltages), ref)
                found[case_id] = dict(passed=passed, worst=worst)
        out[name] = dict(caught=not all(v["passed"] for v in found.values()), cases=found)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    verdict = judge_plants(judge.read_results(args.references))
    (args.out / "plants.json").write_text(json.dumps(verdict, indent=1))
    print(json.dumps({k: v["caught"] for k, v in verdict.items()}, indent=1))
    return 0 if all(v["caught"] for v in verdict.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
