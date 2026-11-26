"""FR-52's twins in fresh processes, scalar and through run_batch (docs/PASSIVE_COHORT_DESIGN.md
§2.2, §5.3): the landing's evidence that the record is passive where it is declared.

Each run is its own process (the caller starts one per run), and writes every field at every row:
  python -B -m validation.fr52_cohorts.twins run OUT {observed,unobserved} {scalar,batch}
  python -B -m validation.fr52_cohorts.twins compare OUT
* scalar: the qualification world through iter_windows, one window, full recording;
* batch: the same world as world 1 of a two-world run_batch, world 2 the same world at another
  seed (so the batch is a batch), a trace with T > 0 through run_batch (§5.3's item to verify).
`compare` holds, in each path, every field of the unobserved run bit for bit in the observed one
but the record, and the diagnostics equal; it reports, for information, whether the scalar and
batch paths agree too. Exit 0 when the twins agree in both paths.
"""

import json
import sys
from pathlib import Path

import numpy as np

RECORD = "integer_cohort_units"
OTHER_SEED = 2


def _definition(kind, seed=None):
    from validation.fr52_cohorts import worlds

    keywords = {} if seed is None else dict(seed=seed)
    return worlds.qualification(**keywords) if kind == "observed" else worlds.unobserved(**keywords)


def run(out, kind, path):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    spec = parse_spec(_definition(kind))
    steps = int(round(spec.experiment.end_time / spec.execution.dt))
    if path == "scalar":
        (window,) = iter_windows(spec, WindowPolicy(steps, "full"), None)
        history, diagnostics = window.history, dict(window.diagnostics)
    else:
        from cells.execution.batch import BatchSpec, WorldSpec, run_batch

        other = parse_spec(_definition(kind, seed=OTHER_SEED))
        result = run_batch(BatchSpec((WorldSpec(1, spec), WorldSpec(2, other)), 2, 4096, 2**31))
        history, diagnostics = result.worlds[1].history, dict(result.worlds[1].diagnostics)
    arrays = {name: np.asarray(value) for name, value in history._asdict().items()}
    np.savez(out / f"{kind}-{path}.npz", **arrays)
    (out / f"{kind}-{path}.json").write_text(
        json.dumps(dict(fields=list(arrays), diagnostics=diagnostics), indent=1, sort_keys=True)
    )
    print(kind, path, len(arrays), "fields,", arrays["integer_events"].shape[0], "rows", flush=True)


def _same(a, b):
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def compare(out):
    out = Path(out)
    report, ok = {}, True
    for path in ("scalar", "batch"):
        seen, plain = (np.load(out / f"{kind}-{path}.npz") for kind in ("observed", "unobserved"))
        info = [json.loads((out / f"{kind}-{path}.json").read_text()) for kind in
                ("observed", "unobserved")]  # fmt: skip
        differ = sorted(f for f in plain.files if f != RECORD and not _same(seen[f], plain[f]))
        fields = sorted(set(seen.files) ^ set(plain.files))
        holds = not differ and not fields and info[0]["diagnostics"] == info[1]["diagnostics"]
        holds &= plain[RECORD].shape[1] == 0 and seen[RECORD].shape[1] > 0
        report[path] = dict(fields_compared=len(plain.files) - 1, differ=differ,
                            fields_in_one_only=fields,
                            diagnostics_equal=info[0]["diagnostics"] == info[1]["diagnostics"],
                            twins_hold=bool(holds))  # fmt: skip
        ok &= bool(holds)
    scalar, batch = np.load(out / "observed-scalar.npz"), np.load(out / "observed-batch.npz")
    report["scalar_against_batch, observed (information)"] = sorted(
        f for f in scalar.files if not _same(scalar[f], batch[f])
    )
    report["verdict"] = "the twins hold in both paths" if ok else "FAIL"
    (out / "compare.json").write_text(json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    command, out, *rest = sys.argv[1:]
    if command == "run":
        run(out, *rest)
    else:
        sys.exit(compare(out))
