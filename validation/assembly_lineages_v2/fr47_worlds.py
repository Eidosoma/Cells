"""FR-47's worlds in the engine's form (the FR-47 protocol; fr47_spec/SPEC.md §2; D323).

W1, W1Δ and W2's four rungs, as `cells.assembly_lineages@2` definitions:
- for exact events, in population mode with one slot (the washes need a population);
- for the deterministic representation, `cells.rate_equations@1`. It runs them once FR-47's build
  admits the shell, the washes and E2; until then it refuses them by name.

**Every input is SPEC.md's**, and every count is molecules in one place.
- The wall's subunit B is one inert species: no step moves it, so its potential is a constant that
  cancels in every compared quantity. Here it is bilayer −3.0.
- The run settings are the protocol's §5.

`python -m validation.assembly_lineages_v2.fr47_worlds check` parses every definition and reports
each one's verdict. It runs nothing.
"""

import json
import math
import sys

from cells.models.assembly_lineages_v2 import (
    GATE_FACTOR,
    IDEAL_MIXING,
    MASS_ACTION,
    MODEL_ID,
    PRESCRIBED_SHELL,
    RATE_EQUATIONS,
    SHARED_POOL,
    SHELL_PERMEATION,
)

PROVENANCE = "FR-47's qualification, fr47_spec/SPEC.md §2"
UNITS = {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0}
CONVENTIONS = {"free_energy_form": "discrete", "condensed_measure": "multinomial",
               "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
               "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept"}  # fmt: skip
SHELL = {"V_out_L": 2e-18, "V_in_L": 2.5e-19, "A_m2": 1.2e-15, "P_m_per_s": 1.5e-7}
W1 = {"tracer": 30000, "wall": 120,
      "withdrawals": ((0, 0.5, (2.5, 9.0)), (1, 0.25, (5.0,))), "replacement": (2, (7.0,)),
      "times": (1.25, 2.0, 3.5, 4.5, 6.0, 6.5, 8.0, 10.5), "horizon": 11.0}  # fmt: skip
W1D_MU = {"solution": 0.7, "lumen": 0.7 + math.log(2.0)}
W2 = {"tracer": 20000, "wall": 100, "a": 1.0, "b": -1.0, "mu_G": -1.0, "mu_H": -1.5,
      "k_GH": 4.0, "rungs": (64, 256, 1024, 4096),
      "times": (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0), "horizon": 6.0}  # fmt: skip
EXACT = {"chunk_events": 4096, "event_limit": 2**31 - 1}
D = {"integrator": {"id": "rosenbrock_rodas4_dense@1", "rtol": 1e-10, "atol_count": 1e-6,
                    "step_limit": 1000000},
     "envelope": {"min_count": 10.0, "provenance": "FR-47's qualification runs"}}  # fmt: skip
SEEDS = {"W1": (470001, 970001), "W1D": (470201, 970201), "W2_64": (470401, 970401),
         "W2_256": (470601, 970601), "W2_1024": (470801, 970801), "W2_4096": (471001, 971001),
         "P7": (471201, None), "P8": (471401, None)}  # fmt: skip


def _species(name, moieties, **mu):
    return {"id": name, "moieties": moieties, "standard_mu_RT": mu, "catalogue": None,
            "evidence": None}  # fmt: skip


def shell_world(tracer_mu, tracer, wall, gate=None):
    """One shell slot in a finite pool: the tracer S in the pool and the lumen, the wall's subunit
    B, the shell's entry, and with `gate` = N_g the forms G and H switching by a wall step."""
    species = [_species("S", {"s": 1}, **tracer_mu), _species("B", {"b": 1}, bilayer=-3.0)]
    membrane = ["B"]
    steps = [{"id": "entry", "locus": "membrane", "reactants": {"S@pool": 1},
              "products": {"S@lumen": 1}, "law": SHELL_PERMEATION,
              "permeability_m_per_s": {"value": SHELL["P_m_per_s"], "provenance": PROVENANCE}}]
    slot = {"S@lumen": 0, "B@membrane": wall}
    founder = {"S@pool": tracer, "S@lumen": 0, "B@membrane": 0}
    world = {
        "units": dict(UNITS), "conventions": dict(CONVENTIONS), "species": species,
        "phases": {"pool": {"volume_L": SHELL["V_out_L"],
                            "species": [{"id": "S", "kind": "finite"}]},
                   "membrane": {"species": membrane},
                   "lumen": {"volume_L": SHELL["V_in_L"], "species": ["S"]}},
        "steps": steps, "free_energy": [{"law": IDEAL_MIXING}], "founder": founder,
        "population": {"structure": SHARED_POOL, "slots": 1, "founders": [slot]},
        "geometry": {"law": PRESCRIBED_SHELL,
                     "area_m2": {"value": SHELL["A_m2"], "provenance": PROVENANCE}},
    }  # fmt: skip
    if gate is not None:
        species += [_species("G", {"g": 1}, bilayer=W2["mu_G"]),
                    _species("H", {"g": 1}, bilayer=W2["mu_H"])]  # fmt: skip
        membrane += ["G", "H"]
        slot.update({"G@membrane": gate // 2, "H@membrane": gate - gate // 2})
        founder.update({"G@membrane": 0, "H@membrane": 0})
        steps.append({"id": "switch", "phase": "membrane", "reactants": {"G": 1},
                      "products": {"H": 1}, "law": MASS_ACTION, "forward_rate_per_s": W2["k_GH"]})
        world["rate_factor"] = {"law": GATE_FACTOR, "forms": ["G", "H"],
                                "entries": [{"form": "G", "step": "entry", "ddG_kT": W2["a"]},
                                            {"form": "H", "step": "entry", "ddG_kT": W2["b"]}]}
    return world


def world(name, rung=None):
    if name == "W1":
        return shell_world({"solution": 0.0}, W1["tracer"], W1["wall"])
    if name == "W1D":
        return shell_world(dict(W1D_MU), W1["tracer"], W1["wall"])
    if name == "W2":
        if rung not in W2["rungs"]:
            raise ValueError(f"W2's rungs are {W2['rungs']}")
        return shell_world({"solution": 0.0}, W2["tracer"], W2["wall"], gate=rung)
    raise ValueError(f"FR-47's worlds are W1, W1D and W2, not {name!r}")


def _capacity(w):
    total = sum(w["founder"].values()) + sum(sum(f.values()) for f in w["population"]["founders"])
    return 1 << int(math.ceil(math.log2(max(4 * total, 256))))


def definition(name, rung=None, seed=1, representation=False):
    """One run's definition: exact events (representation False) or (d) (True)."""
    w = world(name, rung)
    spec = W1 if name in ("W1", "W1D") else W2
    experiment = {"time_horizon_s": spec["horizon"], "event_limit": EXACT["event_limit"],
                  "row_every_events": EXACT["event_limit"],
                  "observation_times_s": list(spec["times"]), "trace": False, "uniforms": False}
    if name in ("W1", "W1D"):
        experiment["schedules"] = [
            *({"index": i, "kind": "withdrawal", "times_s": list(t), "fraction": f, "buffer": [0]}
              for i, f, t in W1["withdrawals"]),
            {"index": W1["replacement"][0], "kind": "replacement",
             "times_s": list(W1["replacement"][1]), "pool": [0]}]  # fmt: skip
    execution = {"backend": "cpu", "precision": "float64", "mode": "population",
                 "stream": {"seed": int(seed), "environment": 0, "lineage": 0, "branch": 0}}
    if representation:
        execution["representation"] = {"id": RATE_EQUATIONS, "envelope": dict(D["envelope"]),
                                       "integrator": dict(D["integrator"])}  # fmt: skip
    else:
        execution |= {"molecule_capacity": _capacity(w), "chunk_events": EXACT["chunk_events"]}
    return {"schema_version": 1, "model": {"id": MODEL_ID, "world": w},
            "experiment": experiment, "execution": execution}  # fmt: skip


def check():
    """Every definition parsed (nothing run): the exact ones must parse; (d)'s verdict reported."""
    from cells.definitions.specs import ConfigError, parse_spec

    out = {}
    cases = [("W1", None), ("W1D", None)] + [("W2", r) for r in W2["rungs"]]
    for name, rung in cases:
        key = name if rung is None else f"{name}_{rung}"
        parse_spec(definition(name, rung, seed=SEEDS[key][0]))
        try:
            parse_spec(definition(name, rung, seed=SEEDS[key][0], representation=True))
            d_verdict = "admitted"
        except ConfigError as error:
            d_verdict = f"refused: {str(error)[:160]}"
        out[key] = {"exact": "parses", "d": d_verdict}
    return out


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        raise SystemExit("usage: python -m validation.assembly_lineages_v2.fr47_worlds check")
    print(json.dumps(check(), indent=1))
