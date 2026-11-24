"""FR-43 part 2 (D315): the shared inventories judged against their code-blind references.

The references are validation/fr43_part2/references (the references agent's, written from the
equations and the declared worlds only). The criteria were fixed before any reference existed:
the specification's CRITERIA.md (23 November 2026, kept with the run inputs). This module applies
them as written, and records every number against its floor and its band.

C2.3, one pool with two writers at fixed volume, for each kind (sink: N + X -> W; source: X -> N):
- the engine runs the kind's world at its declared dt and at dt/2 (the -dt0p5 and -dt0p25 files);
- at the sample times t_i, e_q(h) = max_i |q_engine,h(t_i) - q_ref(t_i)| / max_i |q_ref(t_i)|;
- for q in {n_N, the gene unit's net books of N (produced minus consumed), the network's net books
  of N, the network's route rate}: pass if 3.6 <= e_q(dt) / e_q(dt/2) <= 4.4. Where
  e_q(dt) < 1e-8 the ratio is not judged, and q passes if e_q(dt/2) < 1e-8;
- the plant (must fail): against the planted reference (the network's k x 1.01), the ratio for
  n_N and for the network's books falls below 3.6.

Usage (from a frozen snapshot's root): python -m validation.tissue.shared_inventory_references c23
OUT_DIR. It writes OUT_DIR/c23.json and exits 0 when every criterion holds, else 1.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "fr43_part2" / "references"
FLOOR = 1e-8  # Below it, e_q(dt) is too close to the reference's own accuracy for a ratio.
BAND = (3.6, 4.4)  # Strang over order-3 half-steps: e(dt) / e(dt/2) = 4 to leading order.
C23_KINDS = ("sink", "source")
C23_QUANTITIES = ("n_N", "gene_books_N", "network_books_N", "route_rate")
C23_PLANTED = ("n_N", "network_books_N")  # The planted reference must fail these by the ratio.


def reference(case):
    """(times [T] s, {quantity: [T]}) from out/<case>.json, in the engine's terms."""
    data = json.loads((REFERENCES / "out" / f"{case}.json").read_text())

    def get(name):
        return np.asarray(data[name], dtype=float)

    return get("times_s"), dict(
        n_N=get("amount_fmol.N"),
        gene_books_N=get("gene_produced_N_fmol") - get("gene_consumed_N_fmol"),
        network_books_N=get("network_produced_N_fmol") - get("network_consumed_N_fmol"),
        route_rate=get("network_route_rate_fmol_per_s"),
    )


def engine(world):
    """(times [T] s, {quantity: [T]}, seconds) of the engine's run of worlds/<world>, every host
    check on every accepted row, at the world's observation times: N's amount in the cell, each
    writer's net books of N (the history's rows at those times), and the network's one route's rate
    (its observations, one row per observation time)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run
    from cells.registry.models import get_model

    raw = json.loads((REFERENCES / "worlds" / world).read_text())
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    seconds = time.perf_counter() - started
    _, p = get_model(spec.model).initial_values(spec)
    row = list(spec.model.species_ids).index("N")
    h = result.history
    samples = np.asarray(spec.experiment.observation_times, dtype=float)
    times = np.asarray(result.times, dtype=float)
    rows = [int(np.argmin(np.abs(times - t))) for t in samples]
    assert np.allclose(times[rows], samples, rtol=0, atol=1e-9), (world, times[rows].tolist())

    def net(produced, consumed):
        return (
            np.asarray(getattr(h, produced))[rows, row, 0]
            - np.asarray(getattr(h, consumed))[rows, row, 0]
        )

    rate = np.asarray(result.observations.reaction_rate_fmol_per_s, dtype=float)
    assert rate.shape == (len(samples), 1), ("one route, one row per observation time", rate.shape)
    increment = np.asarray(h.amount_increment)[rows, row, 0]
    return (
        samples,
        dict(
            n_N=np.asarray(p.amount_reference)[row, 0] + increment,
            gene_books_N=net("poly_produced_fmol", "poly_consumed_fmol"),
            network_books_N=net("reaction_produced_fmol", "reaction_consumed_fmol"),
            route_rate=rate[:, 0],
        ),
        seconds,
    )


def error(values, ref):
    """e_q(h): the largest departure at the sample times over the reference's largest size."""
    return float(np.max(np.abs(values - ref)) / np.max(np.abs(ref)))


def ratio_verdict(e_dt, e_half):
    """CRITERIA.md's rule for one quantity: its ratio in the band, or both errors below 1e-8."""
    ratio = e_dt / e_half if e_half > 0 else float("inf")
    judged = e_dt >= FLOOR
    passed = (BAND[0] <= ratio <= BAND[1]) if judged else e_half < FLOOR
    return dict(e_dt=e_dt, e_half_dt=e_half, ratio=ratio, ratio_judged=judged, passed=passed)


def judge_c23(kinds=C23_KINDS):
    """C2.3's verdict, every number recorded: per kind, each quantity's errors and ratio against the
    reference, and the planted reference's ratios."""
    out = dict(case="C2.3", floor=FLOOR, band=list(BAND), kinds={})
    for kind in kinds:
        t_ref, ref = reference(f"C2.3-{kind}")
        t_plant, planted = reference(f"C2.3-{kind}-planted")
        assert np.array_equal(t_ref, t_plant)
        runs = {}
        for label, world in (
            ("dt", f"C2.3-{kind}-dt0p5.json"),
            ("half_dt", f"C2.3-{kind}-dt0p25.json"),
        ):
            times, values, seconds = engine(world)
            assert times.shape == t_ref.shape and np.allclose(times, t_ref, rtol=0, atol=1e-9), (
                world,
                times.tolist(),
            )
            runs[label] = dict(world=world, values=values, seconds=seconds)
        dt, half = runs["dt"]["values"], runs["half_dt"]["values"]
        quantities = {
            q: ratio_verdict(error(dt[q], ref[q]), error(half[q], ref[q])) for q in C23_QUANTITIES
        }
        plant = {}
        for q in C23_PLANTED:
            e_dt, e_half = error(dt[q], planted[q]), error(half[q], planted[q])
            r = e_dt / e_half if e_half > 0 else float("inf")
            plant[q] = dict(e_dt=e_dt, e_half_dt=e_half, ratio=r, fails_as_required=r < BAND[0])
        out["kinds"][kind] = dict(
            runs={
                k: dict(world=v["world"], seconds=round(v["seconds"], 2)) for k, v in runs.items()
            },
            quantities=quantities,
            plant=plant,
            passed=all(v["passed"] for v in quantities.values())
            and all(v["fails_as_required"] for v in plant.values()),
        )
    out["passed"] = all(k["passed"] for k in out["kinds"].values())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("case", choices=("c23",))
    parser.add_argument("out")
    parser.add_argument("--kinds", nargs="+", default=list(C23_KINDS), choices=C23_KINDS)
    args = parser.parse_args(argv)
    import jax

    jax.config.update("jax_enable_x64", True)
    verdict = judge_c23(tuple(args.kinds))
    verdict["references"] = str(REFERENCES.relative_to(ROOT))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.case}.json").write_text(json.dumps(verdict, indent=1) + "\n")
    print(
        json.dumps(
            {k: v["passed"] for k, v in verdict["kinds"].items()} | dict(passed=verdict["passed"])
        )
    )
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
