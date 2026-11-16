"""Development evidence for the lead's item 4 (15 November 2026): two runs of one engine part, the
host-checked path and the vector-window path (every accepted row checked on the device), compared
field by field. Analysis only (it ran from fr45/pipeline/ until it moved here, its logic
unchanged):

    python -m validation.compartment_ph_engine.path_agreement HOST_RESULTS VECTOR_RESULTS PART
        OUT_JSON

Per series and per amount row: bitwise equal or not, the largest absolute difference and the
largest relative one (|a - b| / max(|a|, |b|)); the stage extrema, the ledgers, the steps and the
models' check diagnostics side by side; and the cost: each path's wall seconds, its compile and its
run phase (the wall less compile), with their ratios.
"""

import json
import math
import sys
from pathlib import Path


def compare_lists(a, b):
    if len(a) != len(b):
        return dict(lengths=[len(a), len(b)])
    bitwise = all(x == y and type(x) is type(y) for x, y in zip(a, b, strict=True))
    absolute = max((abs(x - y) for x, y in zip(a, b, strict=True)), default=0.0)
    relative = max((abs(x - y) / max(abs(x), abs(y)) for x, y in zip(a, b, strict=True)
                    if max(abs(x), abs(y)) > 0), default=0.0)
    return dict(bitwise=bitwise, max_abs=absolute, max_rel=relative)


def phases(part):
    t = part.get("timings") or {}
    compile_s = t.get("window_compile_or_cache_seconds", t.get("compile_seconds"))
    wall = part.get("wall_s")
    run = None if wall is None or compile_s is None else wall - compile_s
    return dict(wall_s=wall, compile_s=compile_s, run_s=run, timings=t)


def ratio(a, b):
    return None if a is None or b is None or b == 0 else a / b


def main(argv):
    host_path, vector_path, name, out_json = argv
    host = json.loads(Path(host_path).read_text())
    vector = json.loads(Path(vector_path).read_text())
    h, v = host["parts"][name], vector["parts"][name]
    series = {k: compare_lists(h["series"][k], v["series"][k])
              for k in sorted(set(h["series"]) | set(v["series"]))
              if k in h["series"] and k in v["series"]}
    amounts = {}
    for node in sorted(h["amounts_fmol"]):
        for species in sorted(h["amounts_fmol"][node]):
            amounts[f"{node}/{species}"] = compare_lists(h["amounts_fmol"][node][species],
                                                         v["amounts_fmol"][node][species])
    rows = list(series.values()) + list(amounts.values())
    cost = dict(host=phases(h), vector=phases(v))
    cost["wall_speedup"] = ratio(cost["host"]["wall_s"], cost["vector"]["wall_s"])
    cost["run_phase_speedup"] = ratio(cost["host"]["run_s"], cost["vector"]["run_s"])
    steps = h.get("steps")
    for label in ("host", "vector"):
        c = cost[label]
        c["run_ms_per_step"] = None if c["run_s"] is None or not steps else 1e3 * c["run_s"] / steps
    out = dict(
        host=str(host_path), vector=str(vector_path), part=name,
        sources=dict(host=host.get("source"), vector=vector.get("source")),
        paths=dict(host=host.get("path"), vector=vector.get("path")),
        admitted=dict(host=h.get("admitted"), vector=v.get("admitted")),
        completed=dict(host=h.get("completed"), vector=v.get("completed")),
        refusal=dict(host=h.get("refusal"), vector=v.get("refusal")),
        steps=dict(host=h.get("steps"), vector=v.get("steps")),
        record_s_equal=h.get("record_s") == v.get("record_s"),
        series=series, amounts=amounts,
        all_bitwise=all(r.get("bitwise", False) for r in rows),
        not_bitwise=sorted([k for k, r in series.items() if not r.get("bitwise")]
                           + [k for k, r in amounts.items() if not r.get("bitwise")]),
        max_rel_over_all=max((r.get("max_rel", math.inf) for r in rows), default=None),
        stage=dict(host=h.get("stage"), vector=v.get("stage"),
                   equal=h.get("stage") == v.get("stage")),
        ledgers=dict(host=h.get("ledgers"), vector=v.get("ledgers"),
                     equal=h.get("ledgers") == v.get("ledgers")),
        diagnostics=dict(host=h.get("diagnostics"), vector=v.get("diagnostics")),
        cost=cost,
    )
    Path(out_json).write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print("bitwise:", out["all_bitwise"], "not bitwise:", out["not_bitwise"])
    print("max rel:", out["max_rel_over_all"], "stage equal:", out["stage"]["equal"],
          "ledgers equal:", out["ledgers"]["equal"])
    print("cost:", json.dumps({k: cost[k] for k in ("wall_speedup", "run_phase_speedup")}),
          {k: {x: cost[k][x] for x in ("wall_s", "compile_s", "run_s", "run_ms_per_step")}
           for k in ("host", "vector")})


if __name__ == "__main__":
    main(sys.argv[1:])
