"""Q5 development study: the observed order of S5a's compact worlds after their partitions.

docs/CELL_DIVISION_S5_DESIGN.md §8.3 Q5. Each world runs at dt = 0.5, 0.25 and 0.125 ms
(every event lies on all three grids). The order is reported by inspection, with S3's stop
condition: every step term decreases. Engine only; no reference is needed. This is a
development study, not a judged run.

Engine models: resolved_pump_composite@1 over resolved_pump_tissue@3, with
membrane_entity_state@1, scheduled_membrane_insertion@2, restricted_cleft_lumen@2,
isopotential_partition@1, cytoplasmic_bridge_closure@1 and electrode_current_injection@1.

Worlds (tests/partition_fixtures; nominal, built from neither J1 input):
* furrow 1->2: the asymmetric furrow world (f 0.75, a 0.6, mismatch carriers). Its bridge
  closes over 1 ms, and 1 pA flows into d1 from its birth. End 20 ms.
* furrow 1->2->4: the second-onset world (cleft_quartered) with 1 pA into d1 until its own
  division. End 20 ms.

Compared at records strictly after the last division (10, 15 and 20 ms):
* each live patch's voltage;
* each live cell's amounts;
* each lumen's volume and composition;
* the bridge's exchange.
For each component, the step terms are e1 = |q(h) - q(h/2)| and e2 = |q(h/2) - q(h/4)|.
A component is measurable when both lie above Q3's floor, 64 eps x the quantity's scale (its
largest |value| over every component, record and step), defined before the judged run (the
lead, 14 November); its observed order is log2(e1 / e2). The others are rounding and are
counted apart (the lumen volumes, which follow the inserted area, among them).

Q5 is reported, not banded (the lead, 14 November, as S3's registered protocol): the judged run
judges its stop rules only. Every measurable component's step term decreases, and a quantity
that does not converge stops the run for a report. A band of [1.8, 2.3] was proposed after the
development orders (1.99 to 2.06) had been seen, and was dropped.

Usage: python -m validation.division.q5_order OUTPUT_DIR (through scripts/run_detached.sh).
"""

import json
import math
import sys
import time
from pathlib import Path

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from tests import partition_fixtures as fx

STATUS = "Development study for Q5 (S5a); not judged"
STEPS = (5e-4, 2.5e-4, 1.25e-4)
END = 0.02
RECORDS = (0.01, 0.015, 0.02)


def world(name, dt):
    if name == "furrow 1->2":
        raw = fx.cleft_divided(
            f=0.75,
            area_fraction=0.6,
            carriers={"Na": 0.5, "K": 0.5},
            bridge=("linear", 0.001),
            injection=1e-12,
            end=END,
        )
    else:
        raw = fx.cleft_quartered(injection=1e-12, end=END)
    raw["execution"]["dt"] = dt
    raw["execution"]["max_steps"] = int(math.ceil(END / dt)) + 8
    raw["experiment"]["observation_times"] = [0.0, *RECORDS]
    return raw


def quantities(result, spec):
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h, times = result.history, np.asarray(result.times)
    nodes = [c.id for c in spec.model.extracellular]
    lumens = [k for k, c in enumerate(nodes) if c.startswith("cleft")]
    e = [j.id for j in spec.model.junctions].index("bridge_1")
    out = {k: [] for k in ("patch_voltage_V", "cell_amount_fmol", "lumen_volume_pL",
                           "lumen_concentration_mM", "bridge_exchange_fmol")}  # fmt: skip
    for t in RECORDS:
        i = int(np.flatnonzero(np.isclose(times, t, rtol=0, atol=1e-12))[0])
        state = model.STATE_TYPE(*(np.asarray(v[i]) for v in h))
        q = model.view(p, state, xp=np)
        v = adapter.patch_voltages(adapter.node_potentials(state, q, xp=np), q, xp=np)
        out["patch_voltage_V"].append(np.asarray(v)[np.asarray(q.membrane_active)])
        amounts = np.asarray(p.amount_reference) + np.asarray(state.amount_increment)
        out["cell_amount_fmol"].append(amounts[:, np.asarray(q.active)])
        k = list(np.asarray(result.observations.times)).index(t)
        out["lumen_volume_pL"].append(np.asarray(result.observations.lumen_volume_pL)[k, lumens])
        out["lumen_concentration_mM"].append(
            np.asarray(result.observations.lumen_concentration_mM)[k][:, lumens]
        )
        out["bridge_exchange_fmol"].append(
            np.asarray(state.junction_transferred)[:, e]
            + np.asarray(state.partition_retired_junction_transferred_fmol)[:, e]
        )
    return {k: np.asarray(v) for k, v in out.items()}


def orders(coarse, middle, fine):
    """{quantity: summary} of the observed orders (module docstring)."""
    out = {}
    eps = np.finfo(float).eps
    for name in coarse:
        a, b, c = (np.ravel(x[name]) for x in (coarse, middle, fine))
        e1, e2 = np.abs(a - b), np.abs(b - c)
        scale = float(np.max(np.abs(np.concatenate((a, b, c))))) if a.size else 0.0
        floor = 64 * eps * scale  # Q3's floor, on the quantity's scale.
        measurable = (e1 > floor) & (e2 > floor)
        p = np.log2(e1[measurable] / e2[measurable]) if measurable.any() else np.array([])
        out[name] = dict(
            components=int(a.size),
            scale=scale,
            floor=floor,
            measurable=int(measurable.sum()),
            rounding_only=int((~measurable).sum()),
            every_step_term_decreases=bool(np.all(e2[measurable] < e1[measurable])),
            order_min=float(p.min()) if p.size else None,
            order_median=float(np.median(p)) if p.size else None,
            order_max=float(p.max()) if p.size else None,
            largest_relative_step_term=float(np.max(e1 / np.maximum(np.abs(c), 1e-300)))
            if a.size
            else None,
        )
    return out


def verdict(report):
    """Q5's verdict, its stop rules only (orders are reported): every measurable component's
    step term decreases, and every quantity with a measurable component converges."""
    stops = {
        f"{world} {name}": summary["every_step_term_decreases"]
        for world, quantities in report["worlds"].items()
        for name, summary in quantities.items()
        if summary["measurable"]
    }
    return dict(every_step_term_decreases=stops, verdict="pass" if all(stops.values()) else "stop")


def judge(output, protocol_path=None, root=None):
    """The judged run: refused first unless the S5 protocol is registered and the source a
    clean snapshot (s5_protocol.registered); then the study, with the stop rules' verdict."""
    from validation.division import s5_protocol

    s5_protocol.registered("Q5", protocol_path or s5_protocol.PROTOCOL, root or s5_protocol.ROOT)
    main(output)  # The run first (it writes q5_order.json), then its verdict on what was written.
    report = json.loads((Path(output) / "q5_order.json").read_text())
    report["verdict"] = verdict(report)
    (Path(output) / "q5_judged.json").write_text(json.dumps(report, indent=1) + "\n")
    return report


def main(output):
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status=STATUS, steps_s=list(STEPS), end_s=END, records_s=list(RECORDS), worlds={})
    for name in ("furrow 1->2", "furrow 1->2->4"):
        values = []
        for dt in STEPS:
            spec = parse_spec(world(name, dt))
            start = time.perf_counter()
            result = run(spec)
            values.append(quantities(result, spec))
            print(f"{name} dt={dt}: {time.perf_counter() - start:.1f} s", flush=True)
        report["worlds"][name] = orders(*values)
        (output / "q5_order.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1), flush=True)
    return report


if __name__ == "__main__":
    if sys.argv[1:2] == ["judge"]:
        judge(sys.argv[2])
    else:
        main(sys.argv[1])
