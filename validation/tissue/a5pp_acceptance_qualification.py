"""fr6-a5pp-v1's generator: the protocol's parts, as records (FR-6 A5'', D216).

The protocol is validation/tissue/a5pp_acceptance_protocol.json; its world is the references'
registered world a5pp_prior, built by validation/tissue/a5pp_acceptance_fixtures (the
engine-layout adapter). The generator writes records and computes no verdict; the judge
(validation/tissue/a5pp_acceptance_judge.py) reads them. Each part is its own unit
(OUT_DIR/results.json), and the judge merges the units (MG0c's form, as FR-1's and FR-3's).

Parts (the protocol's judged_parts):
* a5pp_rung_1ms ... a5pp_rung_0p125ms: the registered world on the references' ladder;
* K_prior_swapped, K_prior_shared_a, K_prior_shared_b, K_prior_shared_mean, K_prior_ignored,
  K_state_bypassed, K_k_on, K_k_off, K_basal_rule, K_basal_reference: each control world on all
  four rungs (one run per rung). The two basal controls (the lead's ruling 6): K_basal_rule at the
  protocol's registered delta (the coupling protocol's rule) in a judged run, or at DEV_DELTA in a
  development run, from which the judge derives the rule's delta (the departure is linear in
  delta); K_basal_reference at the references' registered delta, REFERENCE_DELTA;
* references: the FR references agent's, through its usage note only (validation/fr6/references/
  REFERENCES_USAGE.md: a5pp.reference and a5pp.floor), on the registered inputs.

Each engine run records, at every observation time (record_ms: integer milliseconds): each cell's
potential (V_CELL, V), its Na, K and Cl amounts (amount_CELL_SPECIES, fmol), its regulatory state
and exposure (s_CELL, U_CELL), its population's effective availability (a_eff_CELL) and its
coupling's factor (F_CELL); beside them the run's steps, dt, the printed IDs and the bound start.

Modes:
  python -m validation.tissue.a5pp_acceptance_qualification dev OUT_DIR PART [PART ...]
  python -m validation.tissue.a5pp_acceptance_qualification judged PROTOCOL_JSON OUT_DIR PART [...]
A judged run is refused, before anything is computed or written, unless the protocol is
registered (its status and its registration record), the source is a clean execution snapshot,
the protocol registers delta, and OUT_DIR is new (D150's and MG0c's guard).
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from validation.tissue import a5pp_acceptance_fixtures as af

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation" / "tissue" / "a5pp_acceptance_protocol.json"
PROTOCOL_ID = "fr6-a5pp-v1"
DEV_DELTA = 1e-4  # K_basal_rule's development delta; the judge derives the rule's from it.
REFERENCE_DELTA = 1e-3  # The references' registered basal control (K_basal_reference).
SPECIES = ("Na", "K", "Cl")


def dt_key(dt):
    """1e-3 -> '1ms', 1.25e-4 -> '0p125ms'."""
    return f"{dt * 1e3:g}".replace(".", "p") + "ms"


RUNGS = {f"a5pp_rung_{dt_key(dt)}": dt for dt in af.LADDER_S}
CONTROLS = {
    "K_prior_swapped": lambda delta: af.prior("swapped"),
    "K_prior_shared_a": lambda delta: af.prior("shared_a"),
    "K_prior_shared_b": lambda delta: af.prior("shared_b"),
    "K_prior_shared_mean": lambda delta: af.prior("shared_mean"),
    "K_prior_ignored": lambda delta: af.prior("ignored"),
    "K_state_bypassed": lambda delta: af.state_bypassed(),
    "K_k_on": lambda delta: af.rate("k_on"),
    "K_k_off": lambda delta: af.rate("k_off"),
    "K_basal_rule": lambda delta: af.basal(delta),
    "K_basal_reference": lambda delta: af.basal(REFERENCE_DELTA),
}
PARTS = (*RUNGS, *CONTROLS, "references")


# ------------------------------------------------------------------ provenance and guards


def snapshot_identity(root=None):
    root = ROOT if root is None else root
    manifest = Path(root) / "SNAPSHOT.json"
    if manifest.exists():
        snapshot = json.loads(manifest.read_text())
        return dict(kind="snapshot", git_revision=snapshot.get("git_revision"),
                    patch_sha256=snapshot.get("patch_sha256"), status=snapshot.get("status"))

    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(root, "a5pp_acceptance_qualification's source record")  # D259

    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              check=False).stdout.strip()

    return dict(kind="checkout", git_revision=git("rev-parse", "HEAD"),
                dirty=git("status", "--porcelain"))


def registered_delta(protocol):
    value = (protocol.get("registered_delta") or {}).get("basal")
    return float(value) if isinstance(value, (int, float)) and value > 0 else None


def judged_run_refusal(protocol, root=None):
    """Why a judged run may not start (None: it may). root: the source tree, ROOT (read when
    called) by default."""
    root = ROOT if root is None else root
    status = protocol.get("status")
    if not (isinstance(status, str) and status.lower().startswith("registered")):
        return "the protocol is not registered (its status does not begin 'registered')"
    record = protocol.get("registration")
    if not (isinstance(record, dict) and record.get("status") == status):
        return "the protocol's registration record is missing or does not match its status"
    if protocol.get("id") != PROTOCOL_ID:
        return f"not {PROTOCOL_ID}"
    if registered_delta(protocol) is None:
        return "the protocol registers no delta for the basal control"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot, not a checkout"
    snapshot = json.loads(manifest.read_text())
    if (snapshot.get("status") != "complete"
            or snapshot.get("patch_sha256") != hashlib.sha256(b"").hexdigest()):
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def refusal_before_writing(requested, out_dir):
    unknown = sorted(set(requested) - set(PARTS))
    if unknown or not requested:
        return f"unknown or no parts {unknown} (the parts: {list(PARTS)})"
    if Path(out_dir).exists():
        return "the output directory exists (each attempt writes its own)"
    return None


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        return value.item()
    return value


def git_blob(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


# ------------------------------------------------------------------ engine runs


def admit(raw):
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.runner import timeline

    try:
        spec = parse_spec(raw)
        timeline(spec)
    except ConfigError as error:
        return None, str(error)
    return spec, None


def ids_of(spec):
    from cells.operators import OPERATORS

    d = spec.to_dict()
    m, x = d["model"], d["execution"]
    found = {m.get("id"), m.get("inner_model"), (m.get("closure") or {}).get("law"),
             x.get("solver"), x.get("field_solver")}
    found |= {p.get("law") for p in m.get("membranes", [])}
    found |= {c.get("kinetic_law") for c in m.get("channels", [])}
    for op in m.get("operators", []):
        found.add(op["law"])
        step = getattr(OPERATORS.get(op["law"]), "STEP_ID", None)
        if step:
            found.add(step)
        found |= {s.get("law") for s in op.get("states", []) or []}
    return sorted(i for i in found if isinstance(i, str))


def records_of(result):
    """Every observation time's series (module docstring) from a runner result."""
    spec = result.spec
    m = spec.model
    cells = [c.id for c in m.cells]
    species = list(m.species_ids)
    anchor = np.asarray([[c.initial_amount_fmol[i] for c in m.cells]
                         for i in range(len(species))])
    channels = [c.id for c in m.channels]
    times = np.asarray(result.times)
    obs = vars(result.observations)
    obs_times = np.asarray(obs["times"])
    series = {}

    def add(name, value):
        series.setdefault(name, []).append(float(value))

    h = result.history
    for j, t in enumerate(obs_times):
        i = int(np.argmin(np.abs(times - t)))
        if abs(times[i] - t) > 1e-9 * max(1.0, abs(t)):
            raise ValueError(f"observation time {t} is not an accepted step")
        amounts = anchor + np.asarray(h.amount_increment)[i]
        state = np.asarray(h.regulatory_state)[i]
        exposure = np.asarray(h.regulatory_input_integral)[i]
        for k, c in enumerate(cells):
            add(f"V_{c}", np.asarray(obs["cell_potential_V"])[j][k])
            for s in SPECIES:
                add(f"amount_{c}_{s}", amounts[species.index(s), k])
            add(f"s_{c}", state[k] if state.size == len(cells) else np.nan)
            add(f"U_{c}", exposure[k] if exposure.size == len(cells) else np.nan)
            q = channels.index(af.population_name(c))
            add(f"a_eff_{c}", np.asarray(obs["channel_availability"])[j][q])
            factor = obs.get("coupling_factor")
            add(f"F_{c}", np.asarray(factor)[j][k] if factor is not None else np.nan)
    series = {k: [None if v != v else v for v in values] for k, values in series.items()}
    return dict(record_s=[float(t) for t in obs_times],
                record_ms=[af.ms(t) for t in obs_times], series=series, cells=cells,
                ids=ids_of(spec), dt_s=float(spec.execution.dt),
                steps=int(round(spec.experiment.end_time / spec.execution.dt)),
                diagnostics=plain({k: v for k, v in result.diagnostics.items()
                                   if isinstance(v, (int, float))}))


def engine_run(world, dt, *, label):
    from cells.execution.errors import NumericalError
    from cells.execution.runner import run

    started = time.perf_counter()
    raw = af.build(world, dt=dt)
    spec, refusal = admit(raw)
    out = dict(kind="engine", label=label, dt_s=dt, end_s=float(world["end_s"]),
               steps=int(round(float(world["end_s"]) / dt)))
    if spec is None:
        return dict(out, admitted=False, completed=False, refusal=refusal,
                    wall_s=time.perf_counter() - started)
    try:
        result = run(spec)
    except NumericalError as error:
        return dict(out, admitted=True, completed=False, refusal=str(error),
                    wall_s=time.perf_counter() - started)
    return dict(out, admitted=True, completed=True, refusal=None, **records_of(result),
                wall_s=time.perf_counter() - started)


def _rung(dt):
    def part(name, context):
        return engine_run(af.registered(), dt, label=name)
    return part


def _control(make):
    def part(name, context):
        started = time.perf_counter()
        delta = context["delta"]
        world = make(delta)
        runs = {dt_key(dt): engine_run(world, dt, label=f"{name} at {dt:g} s")
                for dt in af.LADDER_S}
        ok = all(r["admitted"] and r["completed"] for r in runs.values())
        used = dict(K_basal_rule=delta, K_basal_reference=REFERENCE_DELTA).get(name)
        return dict(kind="engine_set", admitted=True, completed=ok, runs=runs, delta=used,
                    wall_s=time.perf_counter() - started)
    return part


def references_part(name, context):
    """The references through their usage note's API only (a5pp.reference and a5pp.floor), on
    the registered inputs, whose git blob must be the one the references' design records."""
    from validation.fr6.references import a5pp

    del name, context
    started = time.perf_counter()
    data = af.INPUTS.read_bytes()
    design = json.loads(af.DESIGN.read_text())
    blob = git_blob(data)
    if blob != design["inputs"]["git_blob"]:
        raise SystemExit("Refused: the references' inputs are not the registered file")
    inputs = json.loads(data)
    world, constants = inputs["worlds"][af.WORLD_ID], inputs["constants"]
    r = a5pp.reference(world, constants)
    floor = a5pp.floor(world, constants)
    cells = [str(c) for c in r["cells"]]
    times = np.asarray(r["times_s"], dtype=float)
    series = {}
    V = np.asarray(r["V_V"], dtype=float)
    amounts = np.asarray(r["amounts_fmol"], dtype=float)
    s = np.asarray(r["s"], dtype=float)
    a_eff = np.asarray(r["a_eff"], dtype=float)
    for k, c in enumerate(cells):
        series[f"V_{c}"] = V[:, k].tolist()
        for i, sp in enumerate(SPECIES):
            series[f"amount_{c}_{sp}"] = amounts[:, k, i].tolist()
        series[f"s_{c}"] = s[:, k].tolist()
        series[f"a_eff_{c}"] = a_eff[:, k].tolist()
    return dict(kind="reference", admitted=True, completed=True, cells=cells,
                record_s=times.tolist(), record_ms=[af.ms(t) for t in times], series=series,
                floor={str(k): float(v) for k, v in floor.items()},
                start=dict(V0_V={str(k): float(v) for k, v in r["V0_V"].items()},
                           background_fmol={str(k): float(v)
                                            for k, v in r["background_fmol"].items()}),
                inputs_git_blob=blob, wall_s=time.perf_counter() - started)


FUNCTIONS = {**{n: _rung(dt) for n, dt in RUNGS.items()},
             **{n: _control(make) for n, make in CONTROLS.items()},
             "references": references_part}


def run_parts(requested, out_dir, *, status, delta):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True)
    record = dict(protocol_id=PROTOCOL_ID, status=status, source=snapshot_identity(),
                  requested_parts=list(requested), delta=delta, parts={}, complete=False)
    path = out_dir / "results.json"
    context = dict(out_dir=str(out_dir), delta=delta)
    for name in requested:
        started = time.perf_counter()
        value = FUNCTIONS[name](name, context)
        value["seconds"] = time.perf_counter() - started
        record["parts"][name] = plain(value)
        path.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n")
    record["complete"] = True
    path.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n")
    return record


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("mode", choices=("dev", "judged"))
    parser.add_argument("args", nargs="+")
    args = parser.parse_args(argv)
    if args.mode == "judged":
        if len(args.args) < 3:
            raise SystemExit("judged PROTOCOL_JSON OUT_DIR PART [PART ...]")
        protocol = json.loads(Path(args.args[0]).read_text())
        out_dir, parts = args.args[1], args.args[2:]
        why = judged_run_refusal(protocol)
        delta = registered_delta(protocol)
        status = "Judged run of " + PROTOCOL_ID
    else:
        out_dir, parts = args.args[0], args.args[1:]
        why, delta = None, DEV_DELTA
        status = "Development run of " + PROTOCOL_ID + " (not a judged run)"
    why = why or refusal_before_writing(parts, out_dir)
    if why:
        raise SystemExit("Refused: " + why)
    run_parts(parts, out_dir, status=status, delta=delta)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
