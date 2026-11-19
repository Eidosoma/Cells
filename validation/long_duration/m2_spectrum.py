"""M2: the slow spectrum from E's dense eigenvalues (REGISTRATION_20261118.md §4).

For each world (D1, S7b, S7a; @1 and @3 alone, since E refuses the composite):
* slow mode, formulation "rhs", globalization "auto", from the declared initial state: E's
  solve_and_check, with the full dense spectrum of the reduced Jacobian (count 0);
* fast mode at the converged composition (the slow solution's state as the base world), Newton
  from it, and its dense spectrum;
* the declared split: n_f, the fast problem's reduced dimension; the full spectrum's n_f
  eigenvalues of largest modulus its fast part, the rest its slow spectrum; separated if the
  sorted moduli of the fast part and of the fast spectrum agree pairwise within relative 0.1
  and eps = max |slow| / min |fast part| <= 0.1;
* H_R1 = 1 / max |lambda_slow|, and H_R1 / dt_N2 with M1's dt_N2 for the sheets.
Stage 0 makes no qualification claim (amendment 1, Q1).

Usage: python -m validation.long_duration.m2_spectrum OUTPUT.json [M1_JSON]
"""

import json
import sys
import time

import numpy as np


def split(full, fast, match, separation):
    """The declared split of a full spectrum (complex rates) by the fast spectrum's size."""
    full, fast = np.asarray(full, dtype=complex), np.asarray(fast, dtype=complex)
    n_f = len(fast)
    order = np.argsort(-np.abs(full), kind="stable")
    fast_part, slow = full[order[:n_f]], full[order[n_f:]]
    a, b = np.sort(np.abs(fast_part)), np.sort(np.abs(fast))
    relative = np.abs(a - b) / np.maximum(b, np.finfo(float).tiny) if n_f else np.zeros(0)
    eps = (
        float(np.max(np.abs(slow)) / np.min(np.abs(fast_part)))
        if len(slow) and n_f and np.min(np.abs(fast_part)) > 0
        else None
    )
    matched = bool(np.all(relative <= match)) if n_f else False
    return dict(
        n_full=len(full),
        n_fast=n_f,
        fast_part=[[float(v.real), float(v.imag)] for v in fast_part],
        slow=[[float(v.real), float(v.imag)] for v in slow],
        fast_match_relative=[float(v) for v in relative],
        fast_matched=matched,
        epsilon=eps,
        separated=bool(matched and eps is not None and eps <= separation),
        h_r1_s=float(1.0 / np.max(np.abs(slow)))
        if len(slow) and np.max(np.abs(slow)) > 0
        else None,
    )


def rates(stability):
    return np.asarray([complex(r, i) for r, i in stability["eigenvalues_per_s"]])


def analyse(raw, reg):
    """Slow and fast problems of one world, and the declared split."""
    from cells.analysis import stationary as sa
    from cells.definitions.specs import parse_spec

    started = time.perf_counter()
    spec = parse_spec(raw)
    slow_pb = sa.problem(spec, mode="slow", formulation=reg["formulation"])
    options = dict(newton_options=dict(globalization=reg["globalization"]),
                   stability_options=dict(method="dense", count=0))  # fmt: skip
    slow, solution = sa.solve_and_check(slow_pb, slow_pb.anchor, label="slow", **options)
    out = dict(slow=slow)
    if not slow["converged"]:
        out.update(outcome="not converged", seconds=time.perf_counter() - started)
        return out
    state, _, _ = slow_pb.embed(solution.u, solution.theta)
    _, layout = slow_pb.model.initial_values(spec)
    fast_pb = sa.problem(spec, state=state, layout=layout, mode="fast")
    fast, _ = sa.solve_and_check(fast_pb, fast_pb.anchor, label="fast", **options)
    out["fast"] = fast
    if not fast["converged"]:
        out.update(outcome="fast mode not converged", seconds=time.perf_counter() - started)
        return out
    out["split"] = split(
        rates(slow["stability"]),
        rates(fast["stability"]),
        reg["fast_match_relative"],
        reg["separation_max"],
    )
    out["outcome"] = "separated" if out["split"]["separated"] else "not separated"
    out["slow_classification"] = slow["stability"]["classification"]
    out["consistency"] = slow.get("consistency")
    out["seconds"] = time.perf_counter() - started
    return out


def run(output, m1_path=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.long_duration import harness, worlds

    reg = worlds.registration()["m2"]
    m1 = json.loads(open(m1_path).read())["worlds"] if m1_path else {}
    out = dict(
        measurement="M2",
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        snapshot_revision=harness.snapshot_revision(),
        m1=m1_path,
        worlds={},
    )
    for name in reg["worlds"]:
        world = analyse(getattr(worlds, name.lower())(), reg)
        if name.lower() in m1 and world.get("split", {}).get("h_r1_s"):
            dt_n2 = m1[name.lower()]["n2"]["primary"]["dt_N2_s"]
            world["h_r1_over_dt_n2"] = world["split"]["h_r1_s"] / dt_n2
            world["reaches_reading_factor"] = world["h_r1_over_dt_n2"] >= reg["reading_factor"]
        out["worlds"][name] = world
        print(name, world.get("outcome"), json.dumps(world.get("split", {}).get("epsilon")))
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1, default=str)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
