"""Revilla, Castro and Barrio (1999)'s spent FR-30 extraction in §13.7's layout, for the rehearsal
of Tag A's chain (docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.7 part 10; D334).

The extraction (D311) wrote fit.json as an object of named lists and held_out.json as one flat list
(§13.6). Here both become one flat list in the fr30-junction-observations@1 layout, and
protocol.json becomes fr30-junction-protocol@1. Every entry keeps its id, signed voltage, polarity,
the paper's observable name, mapping, value, dispersion, source and digitizing error.

What the layout adds:
- Units read "G/G_0", and the normalization is the 10-mV prepulse.
- The dispersion carries n = 6 with what n counts, "oocyte pairs": "each point in Fig. 3B and 3C is
  the mean +- SEM of six pairs".
- The convention block is protocol.json's polarity convention: V_j = V1 - V2, steps applied to
  oocyte 1, both oocytes at one holding level.
- The split is recomputed by §13.7's S0 to S5 from the entries, and refused unless it is the
  extraction's own: decays at 60, 80 and 100 mV, 80 mV held out at both polarities, and G_ss alone
  at 20 and 40 mV with none held out.

Standard library only. Usage:
    python -m validation.junction_gate_benchmark.revilla1999_layout EXTRACTION_DIR OUT_DIR
"""

import argparse
import json
import sys
from pathlib import Path

from validation.junction_gate_benchmark import score as scorer

UNITS = {"s": "s", "ms": "ms", "G/G(10-mV prepulse)": scorer.STEADY_UNITS}
N_PAIRS = 6
N_COUNTS = "oocyte pairs"
EXPECTED_SPLIT = {"decay_list": [60.0, 80.0, 100.0], "steady_list": [20.0, 40.0],
                  "decay_mV": [80.0], "steady_mV": []}  # fmt: skip
CONVENTION = {
    "paper_vj_definition": "Vj = V1 - V2; steps applied to oocyte 1; positive Vj is a greater "
    "relative positivity in oocyte 1 (Methods)",
    "protocol_type": "one_sided",
    "stepped_cell": "cell_1",
    "holding_mV": {"cell_1": -40, "cell_2": -40},  # printed as "Vh, e.g., -40 mV", in both oocytes
    "sign_map": "as_printed",
}


def entries_of(doc):
    """The old entries, in order: an object of named lists (fit.json) or one flat list."""
    listed = doc["observables"]
    if isinstance(listed, dict):
        return [e for name in sorted(listed) for e in listed[name]]
    return list(listed)


def convert_entry(old):
    """One old entry in §13.7's layout."""
    mapped = old.get("maps_to_registered_observable")
    units = UNITS.get(old["units"], old["units"])
    dispersion = old.get("dispersion")
    if dispersion is not None:
        kind = "SEM" if str(dispersion["type"]).startswith("SEM") else dispersion["type"]
        dispersion = {"type": kind, "value": dispersion["value"], "units": units, "n": N_PAIRS,
                      "n_counts": N_COUNTS}  # fmt: skip
    method = "digitized" if str(old.get("method", "")).startswith("digitized") else "printed"
    return {
        "id": old["id"],
        "vj_mV": old["vj_mV"],
        "polarity": old["polarity"],
        "observable": old["observable"],
        "maps_to": mapped,
        "value": old["value"],
        "units": units,
        "normalization": "prepulse" if mapped == scorer.STEADY else None,
        "amplitude_definition": None,
        "dispersion": dispersion if mapped is not None else None,
        "n": N_PAIRS,
        "source": old.get("source", old.get("printed", "Revilla et al. 1999")),
        "method": method,
        "digitizing_error": old.get("digitizing_error"),
    }


def field(value=None, status="not_stated", quote=None, place=None, how=None):
    return {"value": value, "status": status, "quote": quote, "place": place, "how": how}


def protocol_fields():
    """protocol.json's fields, from the extraction's protocol.json (as read by its extractor)."""
    return {
        "step_duration_s": field(
            30.0,
            "read",
            how="the extractor's reading: the Fig. 3B inset "
            "shows the analysed decay on a 30-s axis",
        ),  # fmt: skip
        "step_durations_s": field(
            [0.5, 30.0],
            "stated",
            quote="Vj pulses of +-100 mV in 20-mV increments, printed as 500 ms and 30 s long",
            place="Fig. 2 legend, p. 1378",
        ),  # fmt: skip
        "gss_time_s": field(),
        "prepulse_mV": field(
            10.0,
            "stated",
            quote="normalized to the gj of brief 10-mV Vj prepulses",
            place="Methods",
        ),  # fmt: skip
        "prepulse_s": field(),
        "normalization": field(
            "prepulse",
            "stated",
            quote="steady-state gj ... normalized to the gj of brief 10-mV Vj prepulses",
            place="Methods",
        ),  # fmt: skip
        "reference_mV": field(),
        "fit_window_s": field(),
        "fit_form": field(
            "two exponentials",
            "stated",
            quote="wild-type decays biexponential (tau1 fast, tau2 slow)",
            place="Results, p. 1377",
        ),  # fmt: skip
        "fit_offset": field(),
        "amplitude_definition": field(),
        "sampling_Hz": field(),
        "filter_Hz": field(
            1000.0,
            "stated",
            quote="junctional currents low-pass filtered at 1 kHz",
            place="Methods",
        ),  # fmt: skip
        "temperature_C": field(),
        "cells": field(
            "Xenopus laevis oocyte pairs",
            "stated",
            quote="stage V and VI, paired",
            place="Methods, p. 1375",
        ),  # fmt: skip
        "construct": field(
            "wild-type rat Cx43 cRNA with an antisense against Xenopus Cx38",
            "stated",
            quote="cRNA of wild-type rat Cx43, co-injected with an "
            "antisense oligonucleotide against Xenopus Cx38 mRNA",
            place="Methods",
        ),  # fmt: skip
        "n": field(
            N_PAIRS,
            "stated",
            quote="each point is the mean +- SEM of six pairs",
            place="Fig. 3 legend",
        ),  # fmt: skip
    }


def convert(extraction_dir):
    """(fit, held_out, protocol) documents in §13.7's layout."""
    root = Path(extraction_dir)
    fit_old = json.loads((root / "fit.json").read_text())
    held_old = json.loads((root / "held_out.json").read_text())
    fit_entries = [convert_entry(e) for e in entries_of(fit_old)]
    held_entries = [convert_entry(e) for e in entries_of(held_old)]
    probe = [scorer.read_entry(e, f"entry[{i}]") for i, e in enumerate(fit_entries + held_entries)]
    classes = scorer.classify(probe)
    held_out = {"decay_mV": scorer.rank_rule(classes["decay_list"]),
                "steady_mV": scorer.rank_rule(classes["steady_list"])}  # fmt: skip
    found = {"decay_list": classes["decay_list"], "steady_list": classes["steady_list"], **held_out}
    if found != EXPECTED_SPLIT or classes["training_only"] or classes["training"]:
        raise scorer.Refusal("the recomputed split is not the extraction's own (D311)")
    split = {"rule": scorer.SPLIT_RULE, "classes_mV": classes, "seen_mV": [], "held_out": held_out}
    paper = {"citation": fit_old["paper"]["citation"], "doi": fit_old["paper"]["doi"],
             "pdf_sha256": fit_old["paper"]["pdf_sha256"]}  # fmt: skip
    common = {"registration": {"section": "13.7", "tag": "rehearsal on spent files"},
              "paper": paper, "arm": "homotypic wild-type rat Cx43 (RCx43-wt), oocyte pairs",
              "convention": CONVENTION, "split": split}  # fmt: skip
    fit = {
        "schema": scorer.OBSERVATIONS_SCHEMA,
        "role": "train",
        **common,
        "observables": fit_entries,
        "withheld": [],
        "not_used": fit_old.get("not_used", []),
    }
    withheld = [
        {
            "name": "Table 1's per-polarity Boltzmann fits",
            "why": "fitted across voltages that include the held-out 80 mV (E6)",
        }
    ]
    held = {
        "schema": scorer.OBSERVATIONS_SCHEMA,
        "role": "held_out",
        **common,
        "observables": held_entries,
        "withheld": withheld,
        "not_used": [],
    }
    protocol = {"schema": scorer.PROTOCOL_SCHEMA, "role": "protocol", "paper": paper,
                "convention": CONVENTION, "fields": protocol_fields()}  # fmt: skip
    return fit, held, protocol


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("extraction_dir")
    parser.add_argument("out_dir")
    args = parser.parse_args(argv)
    try:
        fit, held, protocol = convert(args.extraction_dir)
    except scorer.Refusal as err:
        print(f"REFUSED: {err}", file=sys.stderr)
        return 2
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, doc in (("fit.json", fit), ("held_out.json", held), ("protocol.json", protocol)):
        (out / name).write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote fit.json, held_out.json and protocol.json to {out}; no value printed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
