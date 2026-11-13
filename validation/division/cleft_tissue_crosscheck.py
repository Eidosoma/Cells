"""R-tissue's static entry point against R-full on S3's one-cell cleft egg (S5 design §7.2).

The egg is R-full's own: cleft_egg_reference.build(the J1 declared inputs, the default values,
the record's P_old and A/L), as S3's engine definition builds it (cleft_egg_engine.rfull).
R-tissue runs it through R-full's runner hook (cleft_tissue_reference.runner, which calls
simulate_static) with R-full's registered integrator (Radau, rtol 1e-10). It is compared with
* the record: Em at J1 (the front edge of pulse 180), -12.79494 mV, and Rm at J1, 488 kOhm;
* R-full itself, run in the same job: V at every pulse's front edge and sample to the horizon,
  and the state at J1.
The target is 1e-10 V on every pulse edge (design §7.2). This module reads the J1 inputs and the
record and holds no division (the J2 bright line, design §10.1); each part's result records the
partition modules loaded in its process, which must be none (an error otherwise).

Parts (python -m validation.division.cleft_tissue_crosscheck PART[,PART] --output DIR):
  record   R-tissue's J1 readout (to J1 plus one sample) against the record
  pulses   R-tissue and R-full to the horizon: every pulse edge and the state at J1
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.division import cleft_egg_reference as ref  # noqa: E402
from validation.division import cleft_tissue_reference as rt  # noqa: E402

RECORD = Path(__file__).with_name("j1_prediction_of_record.json")
TARGET_V = 1e-10  # Design §7.2.


def record_egg():
    """(declared inputs, R-full's egg at the record's calibration, the record)."""
    d = ref.load_declared()
    record = json.loads(RECORD.read_text())
    egg = ref.build(
        d,
        ref.scalar_values(d),
        p_old=float(record["p_old_m_s"]),
        a_over_l=float(record["a_over_l_m"]),
    )
    return d, egg, record


def part_record(_args=None):
    """R-tissue's Em and Rm at J1 (j1_readout through the runner hook) against the record."""
    d, egg, record = record_egg()
    j1, run = ref.j1_readout(d, egg, method="Radau", rtol=1e-10, runner=rt.runner)
    d_em = j1["em_V"] - float(record["prediction_of_record_V"])
    return dict(
        em_V=j1["em_V"],
        record_em_V=float(record["prediction_of_record_V"]),
        d_em_V=d_em,
        rm_ohm=j1["rm_ohm"],
        record_rm_ohm=float(record["rm_at_j1_ohm"]),
        d_rm_relative=j1["rm_ohm"] / float(record["rm_at_j1_ohm"]) - 1.0,
        at_j1=j1["at_j1"],
        target_V=TARGET_V,
        passes=bool(abs(d_em) <= TARGET_V),
        steps=run.steps,
        wall_s=run.wall_s,
    )


def part_pulses(_args=None):
    """R-tissue and R-full to the horizon from one definition: every pulse edge, J1's state."""
    d, egg, record = record_egg()
    horizon = float(d["time"]["horizon_s"])
    j1 = float(d["time"]["j1_s"])
    full = ref.simulate(egg, horizon, record=(j1,))
    tissue = rt.runner(egg, horizon, record=(j1,))
    if set(full.onset_V) != set(tissue.onset_V) or set(full.sample_V) != set(tissue.sample_V):
        raise AssertionError("the two runs sampled different pulses")
    front = {k: tissue.onset_V[k] - full.onset_V[k] for k in sorted(full.onset_V)}
    sample = {k: tissue.sample_V[k] - full.sample_V[k] for k in sorted(full.sample_V)}
    worst_front = max(front, key=lambda k: abs(front[k]))
    worst_sample = max(sample, key=lambda k: abs(sample[k]))
    a, b = full.at[j1], tissue.at[j1]
    em_pulse = int(d["rm_definition"]["j1_em_pulse"])
    return dict(
        horizon_s=horizon,
        pulses=len(front),
        front_edge_dV=front,
        sample_dV=sample,
        worst_front_edge=dict(pulse=worst_front, dV=front[worst_front]),
        worst_sample=dict(pulse=worst_sample, dV=sample[worst_sample]),
        em_at_j1=dict(
            rfull_V=full.onset_V[em_pulse],
            rtissue_V=tissue.onset_V[em_pulse],
            record_V=float(record["prediction_of_record_V"]),
        ),
        at_j1=dict(
            V=(a["V"], b["V"]),
            lumen_mM=(a["lumen_mM"], b["lumen_mM"]),
            cytosol_mM=(a["cytosol_mM"], b["cytosol_mM"]),
            heat_pJ=(a["heat_pJ"], b["heat_pJ"]),
            area_m2=(a["area"], b["area"]),
            lumen_max_relative=max(
                abs(y / x - 1.0) for x, y in zip(a["lumen_mM"], b["lumen_mM"], strict=True)
            ),
        ),
        v0=(full.v0, tissue.v0),
        target_V=TARGET_V,
        passes=bool(max(abs(x) for x in [*front.values(), *sample.values()]) <= TARGET_V),
        steps=dict(rfull=full.steps, rtissue=tissue.steps),
        wall_s=dict(rfull=full.wall_s, rtissue=tissue.wall_s),
    )


PARTS = dict(record=part_record, pulses=part_pulses)


def partition_modules_loaded():
    """The loaded modules under validation.division whose names mention a partition (R-tissue
    loads R-ops on its division path only)."""
    return sorted(
        m for m in sys.modules if m.startswith("validation.division.") and "partition" in m
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name in args.parts.split(","):
        started = time.perf_counter()
        try:
            result = PARTS[name](args)
            result["verdict"] = "pass" if result["passes"] else "fail"
        except Exception as error:  # Kept as the part's result.
            result = dict(verdict="error", error=repr(error), tb=traceback.format_exc())
        result["part"] = name
        # The bright line at run time: this process must never have loaded a partition module.
        result["partition_modules_loaded"] = partition_modules_loaded()
        if result["partition_modules_loaded"]:
            result["verdict"] = "error"
        result["provenance"] = ref.provenance()
        result["part_wall_s"] = time.perf_counter() - started
        text = json.dumps(result, indent=1, default=float) + "\n"
        (output / f"{name}.json").write_text(text)
        print(name, result["verdict"], f"{result['part_wall_s']:.1f} s", flush=True)


if __name__ == "__main__":
    main()
