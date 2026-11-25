"""The mechanical check of SPEC section 8: none of the spec folder's numbers is in the rehearsal's
inputs.

    exclusions.py           the numbers of inputs_rehearsal.json and of the legacy definitions'
    steps,
                            against those of spec/inputs.json and spec/inputs_part2.json (and the
                            captured
                            steps of both legacy files), by category

A category holds every declared number of its kind: volumes, amounts, permeabilities (and
diffusivities), rates (every rate, capacity, constant of a law, metabolite, abundance, gate and
threshold value, temperature), geometry (areas, lengths, capacitances, charges, voltages), seeds,
times (schedules, compared times, horizons, restarts) and steps. A number matches another at 1e-12
relative. The exemptions are listed and each has its reason. `exclusions.py` exits 1 on any other
match.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules  # noqa: E402

# Structural numbers: a law's or a graph's, or a schedule's level.
TRIVIAL = {0.0, 1.0, -1.0}
EXEMPT = {
    (
        "temperature",
        298.15,
    ): "the channel law admits this temperature only, so every world with a channel has it",
    (
        "steps",
        2.5e-05,
    ): "the channel law's stated bound (the one exception of SPEC section 8), inv_bound only",
    ("steps", 1.25e-05): "the second step of the family at that bound",
    ("steps", 6.25e-06): "the third step of the family at that bound",
    ("stoichiometry", -3.0): "the pump's ions are the law's",
    ("stoichiometry", 2.0): "the pump's ions are the law's",
    ("valence", 1.0): "the ions' charges",
}


def close(a, b):
    return a == b or abs(a - b) <= 1e-12 * max(abs(a), abs(b))


def add(out, category, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return
    out.setdefault(category, set()).add(float(value))


CATEGORY = {
    "volume_pL": "volumes",
    "pool_volume_L": "volumes",
    "initial_amount_fmol": "amounts",
    "fixed_charge_equivalent_fmol": "amounts",
    "initial_free_trimers": "amounts",
    "permeability_m_per_s": "permeabilities",
    "max_permeability_m_per_s": "permeabilities",
    "diffusivity_m2_per_s": "permeabilities",
    "capacity_fmol_per_s": "rates",
    "km_na_mM": "rates",
    "km_k_mM": "rates",
    "km_atp_mM": "rates",
    "atp_mM": "rates",
    "adp_mM": "rates",
    "pi_mM": "rates",
    "delta_g0_J_per_mol": "rates",
    "k_on_M_inv_s": "rates",
    "k_close_s_inv": "rates",
    "k_off_s_inv": "rates",
    "k_fragment_dissolve_s_inv": "rates",
    "abundance": "rates",
    "initial_gate": "rates",
    "m": "rates",
    "h": "rates",
    "threshold_voltage_V": "rates",
    "minimum_open_fraction": "rates",
    "temperature_K": "temperature",
    "area_m2": "geometry",
    "length_m": "geometry",
    "capacitance_F": "geometry",
    "initial_charge_C": "geometry",
    "initial_voltage_V": "geometry",
    "stoichiometry": "stoichiometry",
    "end_s": "times",
    "end_time_s": "times",
    "final_s": "times",
    "potential_times_s": "times",
    "summary_times_s": "times",
    "spacing_s": "times",
    "last_s": "times",
    "step_s": "steps",
    "seeds": "seeds",
    "material_tolerance_fmol": "rates",
}


def walk(value, key, out):
    if key == "controls":
        for family in value.values():
            if isinstance(family, dict):
                for s in family.values():
                    for point in s:
                        add(out, "times", point[0])
        return
    if isinstance(value, dict):
        for k, v in value.items():
            walk(v, key if k in ("Na", "K", "Cl") and key in CATEGORY else k, out)
    elif isinstance(value, list):
        for v in value:
            walk(v, key, out)
    elif key in CATEGORY:
        add(out, CATEGORY[key], value)


def numbers(inputs):
    out = {}
    for world in inputs["worlds"].values():
        walk(
            {
                k: v
                for k, v in world.items()
                if k not in ("scales", "amount_refs", "closure_terms_V", "p")
            },
            "",
            out,
        )
    for r in inputs["runs"]:
        add(out, "steps", r["step_s"])
        for t in re.findall(r"restart at ([0-9.eE+-]+)", r.get("variant") or ""):
            add(out, "times", float(t))
    return out


def captured_steps(*files):
    out = set()
    for f in files:
        d = json.loads((rules.SPEC / f).read_text())
        for w in d["worlds"].values():
            out.update(w.get("captured_steps_s") or [])
    return out


def main():
    folder = {}
    for f in ("inputs.json", "inputs_part2.json"):
        for category, values in numbers(json.loads((rules.SPEC / f).read_text())).items():
            folder.setdefault(category, set()).update(values)
    folder["steps"] |= captured_steps("legacy_part1.json", "legacy_part2.json") | {
        3.125e-06,
        1.5625e-06,
    }
    folder["times"] |= {
        7.3e-05,
        3.713e-03,
    }  # The captured off-grid observations (SPEC section 2.3).
    mine = numbers(json.loads((rules.HERE / "inputs_rehearsal.json").read_text()))
    from make_inputs import WORLDS  # The legacy steps, which inputs_rehearsal.json does not hold.

    for w in WORLDS.values():
        for k in (1, 2, 4):
            add(mine, "steps", w["legacy"] / k)
    bad, exempt, counts = [], [], {}
    for category, values in sorted(mine.items()):
        counts[category] = len(values)
        for v in sorted(values):
            if v in TRIVIAL:
                continue
            for u in folder.get(category, ()):
                if close(v, u):
                    key = (category, u)
                    if key in EXEMPT or (category == "stoichiometry"):
                        exempt.append(
                            (category, v, EXEMPT.get(key, "the pump's ions are the law's"))
                        )
                    else:
                        bad.append((category, v, u))
                    break
    print("numbers checked by category:", counts)
    for e in sorted(set(exempt)):
        print("  exempt", *e)
    for b in bad:
        print("  MATCH", *b)
    print("no other match" if not bad else f"{len(bad)} matches")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
