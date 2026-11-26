"""FR-4's and FR-5's qualification generator: the protocols' parts, as records.

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §13-§14; the protocols fr4_acidification_v1.json and
fr5_transfer_v1.json (validation/compartment_ph/protocols/). The generator writes records and
computes no verdict; the judge (validation/tissue/compartment_ph_judge.py) reads them. Each part
is its own unit (OUT_DIR/results.json), so the ladder's rungs run in parallel and the judge merges
the units (MG0c's form).

Parts of fr4-acidification-v1 (`judge.units` in the protocol):
* rung_2ms, rung_1ms, rung_0p5ms, rung_0p25ms: definitions.fr4_world(World()) at each dt of
  dt_study.LADDER_S, 900 s, records every 1 s;
* control_k1 (P_K = 0), control_k2 (the self-consistent reversed pump, the lead's ruling (b):
  validation/compartment_ph_engine/planted.py's planted law, registered only inside its block) and
  control_k3 (the lumen buffer's k_on at 1e-3 /mM/s on the closure's declaration, refused at the
  definition through the envelope), each at the declared 1 ms;
* reference: R-closure on the declared world, its floor, P_K = 0 and R-kinetic with the lumen's
  k_on at 1e-3 (validation/tissue/compartment_ph_reference_stage.fr4_reference).
Parts of fr5-transfer-v1:
* start: FR-4's declared world at 1 ms to 1800 s. It writes the engine's snapshot there and the
  start extract OUT_DIR/start.json (definitions.start_extract) that every other FR-5 part reads
  (--start): one start for the engine and the references (tr.Start);
* T_rung_1ms ... T_rung_0p125ms and R_rung_...: each arm (parameters.ARM_T, ARM_R) at each dt
  of dt_study.FR5_LADDER_S, 400 s from the extract;
* T_control (f = 1) and R_control (d = 0), at the declared 0.5 ms;
* reference: R-transfer from the extract, both arms, their controls and floors
  (compartment_ph_reference_stage.fr5_reference).

**The engine path is one function, `engine_run`:**
validation/compartment_ph_engine/engine_records.run on the declared world (fr4_world with FR-1's
compartment operator, the composite: judged runs, a dated pre-run correction of 16 November 2026,
bitwise the development world's over 900 s) or on the development world without the operator
(development's default), as the one world of a vector window checking every accepted row on the
device (judged runs: the protocols' execution path) or on the windowed runner checking them on the
host (development's default); ENGINE_READOUTS is what it returns per record. What is not wired yet
is a stand-in (STAND_INS), each blocking only its own parts (STAND_IN_PARTS): every entry refuses
those parts before anything is written, and a judged run of a protocol is refused while a stand-in
blocks any of that protocol's parts (`blocking_stand_ins`), so FR-4's judged run does not wait for
FR-5's parts; each run records the stand-ins that block its protocol, which the judge refuses.

Modes:
  python -m validation.tissue.compartment_ph_qualification dev fr4|fr5 OUT_DIR PART [PART ...]
      [--start START_JSON] [--quick] [--path host|vector] [--world development|declared]
  python -m validation.tissue.compartment_ph_qualification judged PROTOCOL_JSON OUT_DIR PART
      [PART ...] [--start START_JSON]   (the vector path, the declared world)
A judged run is refused, before anything is computed or written, unless the protocol is registered
(its status and its registration record), the source is a clean execution snapshot, no stand-in
blocks any of the protocol's parts, FR-5's start extract was written by the engine from this same
snapshot, and OUT_DIR is new (D150's and MG0c's guard). `--quick` (development only) runs every
part to QUICK_END_S, so a check reaches the code under test in minutes (AGENTS.md's 30-minute
rule); the judge refuses quick results. A judged run takes the protocols' execution path,
`vector` (the lead's ruling, a dated pre-run correction of 15 November 2026): every accepted row
checked on the device in a vector window (engine_records.run), and refuses any other; a
development run takes `host` (every accepted row checked on the host) unless `--path` names one.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import dt_study
from validation.compartment_ph_engine.parameters import World
from validation.tissue import compartment_ph_reference_stage as stage

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS = {
    "fr4": ROOT / "validation" / "compartment_ph" / "protocols" / "fr4_acidification_v1.json",
    "fr5": ROOT / "validation" / "compartment_ph" / "protocols" / "fr5_transfer_v1.json",
}
IDS = {"fr4": "fr4-acidification-v1", "fr5": "fr5-transfer-v1"}
QUICK_END_S = 20.0
K3_LUMEN_K_ON = 1e-3  # /mM/s: the protocol's K3 (1 /M/s)
HOST_PATH = "host"  # Every accepted row checked on the host (the windowed runner): development.
VECTOR_PATH = "vector"  # Every accepted row checked on the device (a vector window).
PATHS = (HOST_PATH, VECTOR_PATH)  # engine_records.PATHS.
DEVELOPMENT_WORLD = "development"  # engine_records.WORLDS: without FR-1's compartment operator
DECLARED_WORLD = "declared"  # the composite with it (definitions.declared_world)
WORLDS = (DEVELOPMENT_WORLD, DECLARED_WORLD)
JUDGED_WORLD = DECLARED_WORLD  # The protocols' world (the lead's ruling, a dated pre-run correction
# of 16 November 2026: bitwise the development world's over 900 s); development keeps both.
JUDGED_PATH = VECTOR_PATH  # The protocols' execution path (the lead's ruling, a dated pre-run
# correction of 15 November 2026); development runs default to the host path.


def default_world(*, judged):
    """The world a run takes unless --world names one: the protocols' for a judged run."""
    return JUDGED_WORLD if judged else DEVELOPMENT_WORLD


def default_path(*, judged):
    """The path a run takes unless --path names one: the protocols' for a judged run."""
    return JUDGED_PATH if judged else HOST_PATH


def dt_key(dt):
    """2e-3 -> '2ms', 5e-4 -> '0p5ms', 1.25e-4 -> '0p125ms'."""
    return f"{dt * 1e3:g}".replace(".", "p") + "ms"


FR4_RUNGS = {f"rung_{dt_key(dt)}": dt for dt in dt_study.LADDER_S}
FR4_CONTROLS = ("control_k1", "control_k2", "control_k3")
FR4_DECLARED_DT = 1e-3
FR5_RUNGS = {f"{arm}_rung_{dt_key(dt)}": (arm, dt)
             for arm in ("T", "R") for dt in dt_study.FR5_LADDER_S}
FR5_CONTROL_PARTS = {"T_control": "T", "R_control": "R"}
PARTS = {
    "fr4": (*FR4_RUNGS, *FR4_CONTROLS, "reference"),
    "fr5": ("start", *[n for n in FR5_RUNGS if n.startswith("T")], "T_control",
            *[n for n in FR5_RUNGS if n.startswith("R")], "R_control", "reference"),
}
ENGINE_PARTS = {*FR4_RUNGS, *FR4_CONTROLS, "start", *FR5_RUNGS, *FR5_CONTROL_PARTS}

# What remains a stand-in on this branch, and why, and the parts each one blocks. Empty: every
# part is wired. The last, fr5_kinds (FR-5's rungs and controls), went on 16 November 2026 with the
# core's raw-sum bound (cells.kind.passive_routes@1, §7.5 amended, 0649f00e), after which arm R runs
# its release burst without refusal (fr5_quick_check, nothing relaxed).
STAND_INS = {}
STAND_IN_PARTS = {}


def blocking_stand_ins(which):
    """The stand-ins that block any of protocol `which`'s parts ("fr4" or "fr5"), sorted: a judged
    run of that protocol is refused while this is not empty, and every run records it."""
    return sorted(name for name in STAND_INS if STAND_IN_PARTS[name] & set(PARTS[which]))

# The readouts the engine path returns per record (the judge reads these names), for the core:
ENGINE_READOUTS = dict(
    series=dict(
        pH_L="the lumen's pH from the closure's read (the stored H_eq row, never a state of pH)",
        pH_c="the cytosol's pH, the same read",
        V_b="the bounding patch's voltage, phi_c - phi_L (V)",
        Heq_L="the lumen's H row (proton equivalents, fmol)", Heq_c="the cytosol's H row",
        K_L="the lumen's K row (fmol)", K_c="the cytosol's K row",
        X_L="FR-5: the lumen's X row (fmol)", X_c="FR-5: the cytosol's X row",
        cycles="the pump's cumulative cycles (fmol; transporter_cycles)",
        work_pJ="the maintenance's cumulative supplied work (transporter_metabolic_work_pJ)",
        heat_pJ="the cumulative heat of every law", stored_change_pJ="the stored free energy's "
        "change since the start", energy_residual_pJ="stored change + heat - work",
        energy_flows_pJ="the integrated energy flows the engine's ledger allowance uses",
        d="FR-5: the damage state", f="FR-5: the condition's factor f(pH_L) on the transfer",
        moved_H_pump="the pump's cumulative proton transfer, c to L (fmol)",
        moved_H_leak="the proton leak's", moved_H_pore="FR-5: the proton pore's",
        moved_X_transfer="FR-5: the conditioned route's cumulative X transfer, c to L (fmol)",
        moved_X_pore="FR-5, arm R: the cargo pore's",
        **{f"heat_{r}_pJ": f"each route's cumulative heat ({r})" for r in (
            "pump", "proton_leak_0", "proton_pore_0", "bounding_0_K", "cargo_transfer_0",
            "cargo_pore_0")}),
    stage=dict(
        envelope_max_lag_ph="the running maximum of rapid_proton_buffer.lag_estimate_ph over every "
                            "stage of every buffered node (B4's proton_buffer_max_lag_pH, gap 7), "
                            "at the last record",
        envelope_stages_beyond="the envelope refusals: 0 for a part that ran to its end, since "
                               "B4's stage check refuses the step at the first stage beyond the "
                               "budget",
        cytosol_pH_min="the cytosol's smallest pH over every stage (proton_buffer_min_pH)",
        cytosol_pH_max="its largest (proton_buffer_max_pH)"),
    amounts_fmol="{node: {species: [amount at each record]}} for every node and row: the judge "
                 "computes the material check and its allowance from these (the lead's ruling, "
                 "15 November 2026), never from an engine tolerance",
    ledgers=dict(charge_residual_C="the largest charge residual", charge_tolerance_C="its "
                 "tolerance"),
    part=dict(admitted="parsed and admitted", completed="ran to its end without a refusal",
              refusal="the engine's refusal message (a refusal is a verdict, not an ending)",
              refusal_reason="'envelope' when the same world is admitted with B4's stage check "
                             "removed (K3's catch), else None",
              steps="the steps taken", definition_sha256="the definition's identity"),
)


def engine_run(definition, *, planted=None, checkpoint_dir=None, path=HOST_PATH,
               world=DEVELOPMENT_WORLD):
    """The engine part's record for one definition (ENGINE_READOUTS at every record, keyed by
    integer second, and the stage diagnostics and ledgers): engine_records.run, which parses the
    development world (a refusal there is `admitted` false) and runs it in windows on the CPU
    backend in float64, every accepted row checked on the host (`path` "host", development) or
    on the device in a vector window ("vector", the protocols' execution path). `planted`
    names a planted law registered only inside its block (K2). With `checkpoint_dir` (FR-5's
    start part) a completed run also writes the engine's snapshot there at the end
    (cells.records.io.write_snapshot) and returns FR-5's start under `start_nodes` and `start_readouts`,
    which fr5_start makes the start extract (definitions.start_extract, producer "engine")."""  # noqa: E501
    from validation.compartment_ph_engine import engine_records
    from validation.compartment_ph_engine import planted as plants

    if planted is not None:  # K2's reversed pump, registered only inside its block.
        registry = plants.registry(plants.PLANTED[planted]())
        return engine_records.run(definition, registry=registry, path=path, world=world,
                                  checkpoint_dir=checkpoint_dir)
    return engine_records.run(definition, path=path, world=world, checkpoint_dir=checkpoint_dir)


def engine_part(definition, context, *, planted=None, checkpoint_dir=None):
    started = time.perf_counter()
    record = engine_run(definition, planted=planted, checkpoint_dir=checkpoint_dir,
                        path=context["path"], world=context["world"])
    record.update(kind="engine", dt_s=definition["execution"]["dt"],
                  end_s=definition["experiment"]["end_time"],
                  definition_sha256=defs.canonical_sha256(definition),
                  wall_s=time.perf_counter() - started)
    return record


# ------------------------------------------------------------------------ the parts


def _world(quick):
    return replace(World(), end_s=QUICK_END_S) if quick else World()


def fr4_rung(name, context):
    return engine_part(defs.fr4_world(_world(context["quick"]), dt_s=FR4_RUNGS[name]), context)


def fr4_control(name, context):
    w = _world(context["quick"])
    if name == "control_k1":
        return engine_part(defs.fr4_world(w.control(), dt_s=FR4_DECLARED_DT), context)
    if name == "control_k2":
        return engine_part(defs.fr4_world(w, dt_s=FR4_DECLARED_DT), context, planted="sign")
    lumen = replace(w.lumen_buffer, k_on_per_mM_s=K3_LUMEN_K_ON)
    return engine_part(defs.fr4_world(replace(w, lumen_buffer=lumen), dt_s=FR4_DECLARED_DT),
                       context)


def fr4_reference(name, context):
    del name
    return stage.fr4_reference(end_s=QUICK_END_S if context["quick"] else None)


def fr5_start(name, context):
    """FR-4's declared world to the checkpoint time, then the engine's snapshot and the start
    extract (OUT_DIR/start.json) every other FR-5 part reads. A run the engine refuses writes
    neither: its record carries the refusal, and FR-5's other parts have no start."""
    del name
    end = QUICK_END_S if context["quick"] else stage.START_TIME_S
    definition = defs.fr4_world(replace(World(), end_s=end), dt_s=FR4_DECLARED_DT)
    snapshot = context["out_dir"] / "engine_snapshot"
    record = engine_part(definition, context, checkpoint_dir=snapshot)
    nodes, readouts = record.pop("start_nodes", None), record.pop("start_readouts", None)
    if nodes is None:
        return record
    extract = defs.start_extract(
        producer="engine", nodes=nodes, readouts=readouts, time_s=record["record_s"][-1],
        dt_s=FR4_DECLARED_DT, source=snapshot_identity(), engine_snapshot=str(snapshot),
        world=f"fr4_world(replace(World(), end_s={end!r}))")
    path = context["out_dir"] / "start.json"
    path.write_text(json.dumps(plain(extract), indent=1, allow_nan=False) + "\n")
    record["extract_sha256"] = defs.start_sha256(plain(extract))
    return record


def _arm(arm, context):
    dw = dt_study.FR5_ARMS[arm]
    if context["quick"]:
        dw = replace(dw, horizon_s=QUICK_END_S, start_checkpoint_s=context["start"]["time_s"])
    return dw


def _with_start(record, context):
    extract = context["start"]
    record["start"] = dict(extract_sha256=defs.start_sha256(extract),
                           producer=extract["producer"], time_s=extract["time_s"])
    return record


def fr5_rung(name, context):
    arm, dt = FR5_RUNGS[name]
    d = defs.fr5_world(_arm(arm, context), dt_s=dt, start=context["start"])
    return _with_start(engine_part(d, context), context)


def fr5_control(name, context):
    arm = FR5_CONTROL_PARTS[name]
    d = defs.fr5_world(_arm(arm, context), dt_s=dt_study.FR5_DECLARED_DT_S,
                       start=context["start"], control=stage.CONTROLS[arm])
    return _with_start(engine_part(d, context), context)


def fr5_reference(name, context):
    del name
    return stage.fr5_reference(context["start"], end_s=QUICK_END_S if context["quick"] else None)


FUNCTIONS = {
    "fr4": {**dict.fromkeys(FR4_RUNGS, fr4_rung), **dict.fromkeys(FR4_CONTROLS, fr4_control),
            "reference": fr4_reference},
    "fr5": {"start": fr5_start, **dict.fromkeys(FR5_RUNGS, fr5_rung),
            **dict.fromkeys(FR5_CONTROL_PARTS, fr5_control), "reference": fr5_reference},
}


# ------------------------------------------------------------------------ provenance and guards


def snapshot_identity(root=ROOT):
    """The run's source: the execution snapshot's manifest, or the checkout's revision and
    status."""
    manifest = Path(root) / "SNAPSHOT.json"
    if manifest.exists():
        snapshot = json.loads(manifest.read_text())
        return dict(kind="snapshot", git_revision=snapshot.get("git_revision"),
                    patch_sha256=snapshot.get("patch_sha256"), status=snapshot.get("status"))

    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(root, "compartment_ph_qualification's source record")  # D259

    def git(*args):
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              check=False)
        return done.stdout.strip()

    return dict(kind="checkout", git_revision=git("rev-parse", "HEAD"),
                dirty=git("status", "--porcelain"))


def judged_run_refusal(protocol, root=ROOT):
    """Why a judged run may not start (None: it may): MG0c's and D150's guard, and the stand-ins
    that block this protocol's parts."""
    status = protocol.get("status")
    if not (isinstance(status, str) and status.lower().startswith("registered")):
        return "the protocol is not registered (its status does not begin 'registered')"
    record = protocol.get("registration")
    if not (isinstance(record, dict) and record.get("status") == status):
        return "the protocol's registration record is missing or does not match its status"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot, not a checkout"
    snapshot = json.loads(manifest.read_text())
    clean = snapshot.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if snapshot.get("status") != "complete" or not clean:
        return "the execution snapshot is incomplete or carries uncommitted changes"
    which = next((k for k, v in IDS.items() if v == protocol.get("id")), None)
    blocking = sorted(STAND_INS) if which is None else blocking_stand_ins(which)
    if blocking:
        return (f"stand-ins remain on this branch for this protocol's parts ({blocking}): the "
                "engine is not wired")
    return None


def start_refusal(extract, *, judged, root=ROOT):
    """Why an FR-5 part may not use this start extract (None: it may)."""
    if extract is None:
        return "FR-5's parts need --start START_JSON (the start part's start.json)"
    if judged and (extract["producer"] != "engine"
                   or extract.get("source") != snapshot_identity(root)):
        return "a judged FR-5 part starts from the engine's extract written from this snapshot"
    return None


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        return value.item()
    return value


def refusal_before_writing(which, requested, out_dir, extract, *, judged, quick, root=ROOT,
                           path=HOST_PATH, world=DEVELOPMENT_WORLD):
    """Every refusal an entry makes before anything is computed or written."""
    unknown = sorted(set(requested) - set(PARTS[which]))
    if unknown or not requested:
        return f"unknown or no parts {unknown} (the parts: {list(PARTS[which])})"
    if judged and quick:
        return "a judged run has no quick horizon"
    if judged and path != JUDGED_PATH:
        return (f"a judged run takes the protocols' execution path ({JUDGED_PATH}, a dated pre-run "
                f"correction); the {path} path is for development")
    if judged and world != JUDGED_WORLD:
        return (f"a judged run takes the protocols' world ({JUDGED_WORLD}: FR-1's compartment "
                f"operator included, a dated pre-run correction); the {world} world is for "
                "development")
    blocked = {name: sorted(set(requested) & STAND_IN_PARTS[name]) for name in STAND_INS}
    blocked = {name: parts for name, parts in blocked.items() if parts}
    if blocked:
        return "; ".join(f"parts {parts} need what is still a stand-in here: {STAND_INS[name]}"
                         for name, parts in blocked.items())
    if which == "fr5" and set(requested) - {"start"}:
        why = start_refusal(extract, judged=judged, root=root)
        if why:
            return why
    if Path(out_dir).exists():
        return "the output directory exists (each attempt writes its own)"
    return None


def run(which, requested, out_dir, *, status, extract=None, quick=False, path=HOST_PATH,
        world=DEVELOPMENT_WORLD):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True)
    results = dict(status=status, protocol_id=IDS[which], source=snapshot_identity(),
                   requested_parts=list(requested), complete=False, quick=quick, path=path,
                   world=world, stand_ins=blocking_stand_ins(which), parts={})
    context = dict(quick=quick, start=extract, out_dir=out_dir, path=path, world=world)
    for name in [p for p in PARTS[which] if p in requested]:
        started = time.perf_counter()
        value = FUNCTIONS[which][name](name, context)
        value["seconds"] = time.perf_counter() - started
        results["parts"][name] = value
        (out_dir / "results.json").write_text(json.dumps(plain(results), indent=1) + "\n")
    results["complete"] = True
    (out_dir / "results.json").write_text(json.dumps(plain(results), indent=1) + "\n")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("dev", "judged"))
    parser.add_argument("target", help="dev: fr4 or fr5; judged: the protocol's JSON")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("parts", nargs="+")
    parser.add_argument("--start", type=Path)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--path", choices=PATHS, default=None,
                        help="where every accepted row is checked (engine_records.run): judged "
                             "runs the protocols' vector path, development runs host unless named")
    parser.add_argument("--world", choices=WORLDS, default=None,
                        help="declared (the composite with FR-1's compartment operator: judged "
                             "runs) or development (without it: development's default)")
    args = parser.parse_args(argv)
    if args.mode == "judged":
        protocol = json.loads(Path(args.target).read_text())
        which = next((k for k, v in IDS.items() if v == protocol.get("id")), None)
        why = "not an FR-4 or FR-5 protocol" if which is None else judged_run_refusal(protocol)
        status = "Judged run of " + str(protocol.get("id"))
    else:
        which, why, status = args.target, None, "Development run"
        if which not in IDS:
            raise SystemExit("Refused: dev takes fr4 or fr5")
    extract = None
    if why is None and args.start is not None:
        extract = defs.read_start(args.start)
    path = args.path or default_path(judged=args.mode == "judged")
    world = args.world or default_world(judged=args.mode == "judged")
    if why is None:
        why = refusal_before_writing(which, args.parts, args.out_dir, extract,
                                     judged=args.mode == "judged", quick=args.quick, path=path,
                                     world=world)
    if why:
        raise SystemExit("Refused: " + why)
    run(which, args.parts, args.out_dir, status=status, extract=extract, quick=args.quick,
        path=path, world=world)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
