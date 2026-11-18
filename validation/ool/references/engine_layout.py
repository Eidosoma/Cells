"""Reading OL1's engine records (``cells.assembly_lineages@2``) as their FORMAT.md states them, into
the references' canonical layout (``records.py``), so the registered harness runs on them unchanged.

It reads files only, all of them under the probe set's directory; nothing here imports or runs
the engine. Every check below refuses the set (``MissingRecord`` or ``RecordFormatError``: harness
status 2), naming what failed:
- **file integrity:** every file listed in ``roles.json`` has its listed SHA-256; every probe's
  ``probe.npz`` has its ``arrays_sha256``; every bundle file has its ``manifest.json`` SHA-256;
- **the registered inputs:** each world, probe-state and design file the engine names has the
  SHA-256 of the references' committed file, and the inputs' pin is recorded;
- **the worlds:** a bundle's ``world.json`` states the registered world (units, tokens, role,
  phases, species, potentials, steps, rate constants, chi, catalysts and founder), compared
  field by field with the registered file;
- **the declarations:** every token from the closed menu; probe places and steps in the registered
  order; the SSA tokens; the channel table; a known end status.

The mapping (FORMAT.md's names on the left):
- probes: ``a_plus``, ``a_minus`` and ``input_states`` pass as they are (the engine writes them in
  the registered place and step order);
- bundles: ``place_count`` (in run.json's place order, held places included) becomes ``counts``
  over the registered finite places; ``event_heat_kT`` and ``reservoir_work_kT`` become ``heat_kT``
  and ``work_kT``; the signed ``event_channel`` codes and the channel rows (``direction``
  forward/reverse) become the canonical channel table; the stream identity is (seed, environment,
  lineage, branch); ``end.status = event_limit`` is the registered end, ``max_events``;
- the row base: FORMAT.md's rows are the start (kind 0), every 100 events (kind 1) and the end
  (kind 2). When the end falls on a periodic row's event count, the two rows must be equal, and one
  is kept; the result is the registered rows, every 100 events and the last;
- the ladder: ``observed`` [run, time, place] in the probe's place order becomes
  ``observation_counts_m{M}`` over the registered finite places; every run must end ``complete``
  (held to the horizon) and carry its own lineage word;
- refusals: ``results`` become one record per registered refusal file, with the tokens it was
  parsed under; ``all_refused`` must be true.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np

from .common import MissingRecord, RecordFormatError
from .design import (
    BOUNDARY_PROBE_FILE,
    CLOSED_WORLD_FILE,
    DESIGN_FILE,
    KERNEL_PROBE_FILE,
    PROBED_CONVENTIONS,
)
from .mass_action import OBSERVATION_TIMES
from .records import write_manifest
from .registered import DESIGN_DIR, WB_RUNGS, registered_world
from .world import Conventions

PAIR_TAGS = {("multinomial", "kept"): "multinomial__kept",
             ("multinomial_less_one", "extinct"): "multinomial_less_one__extinct"}
END_STATUS = {"event_limit": "max_events"}
KNOWN_END = ("event_limit", "complete", "stalled", "extinct", "inert", "capacity")
ENGINE_SSA = {"tau": "neg_log_u1_over_a0", "select": "first_prefix_gt_u2_a0"}


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise MissingRecord(f"{p} is missing")
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise RecordFormatError(f"{p} is not valid JSON: {exc}") from exc


def load_npz(path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise MissingRecord(f"{p} is missing")
    with np.load(p, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def registered_file(name: str) -> Path:
    p = DESIGN_DIR / name
    if not p.is_file():
        p = DESIGN_DIR / "refusals" / name
    if not p.is_file():
        raise RecordFormatError(f"the engine names a registered file {name!r} the references do not have")
    return p


def require_registered_sha(name: str, recorded: str, where: str) -> None:
    actual = sha256(registered_file(name))
    if recorded != actual:
        raise RecordFormatError(f"{where}: the engine read {name} with SHA-256 {recorded}; the registered file is "
                                f"{actual}")


def pair_tag(conventions: dict) -> str:
    c = Conventions.from_declared(conventions)
    key = (c.condensed_measure, c.last_molecule)
    if key not in PAIR_TAGS:
        raise RecordFormatError(f"the convention pair {key} is not a probed pair")
    return PAIR_TAGS[key]


# ---------------------------------------------------------------- the set's index

def check_index(root: Path) -> dict:
    """roles.json: every listed file present with its SHA-256; the pins; the probed pairs."""
    roles = load_json(root / "roles.json")
    for key in ("files", "inputs", "pairs", "source"):
        if key not in roles:
            raise MissingRecord(f"roles.json lacks {key!r}")
    bad = [f for f, h in roles["files"].items() if not (root / f).is_file() or sha256(root / f) != h]
    if bad:
        raise RecordFormatError(f"roles.json lists files whose SHA-256 differs or which are absent: {bad[:5]}")
    for name, h in roles["inputs"].get("files", {}).items():
        require_registered_sha(name, h, "roles.json inputs")
    pairs = sorted(pair_tag(p) for p in roles["pairs"])
    if pairs != sorted(PAIR_TAGS.values()):
        raise RecordFormatError(f"roles.json probes the pairs {pairs}; the registered design probes {sorted(PAIR_TAGS.values())}")
    inputs_dir = str(roles["inputs"].get("directory", ""))
    return dict(engine_revision=roles["source"].get("revision"), engine_dirty=roles["source"].get("dirty"),
                inputs_directory=inputs_dir, inputs_pin=inputs_dir.rsplit("-", 1)[-1] if "-" in inputs_dir else None,
                inputs_hashes_match=True, files_checked=len(roles["files"]), settings=roles.get("settings"),
                standing=roles.get("standing"))


# ---------------------------------------------------------------- probes

def convert_probe(src: Path, dst: Path, world_id: str, states_file: str) -> str:
    meta = load_json(src / "probe.json")
    if (src / "refused.json").is_file():
        raise MissingRecord(f"{src}: the engine refused the world ({load_json(src / 'refused.json').get('message')})")
    arrays_path = src / "probe.npz"
    if meta.get("arrays_sha256") != sha256(arrays_path):
        raise RecordFormatError(f"{src}/probe.npz does not have its declared arrays_sha256")
    world = meta.get("world", {})
    if world.get("registered") != f"{world_id}.world.json":
        raise RecordFormatError(f"{src}: world {world.get('registered')!r}, {world_id}.world.json expected")
    require_registered_sha(world["registered"], world.get("sha256"), str(src))
    inputs = meta.get("inputs", {})
    if inputs.get("file") != states_file:
        raise RecordFormatError(f"{src}: inputs from {inputs.get('file')!r}, {states_file} expected")
    require_registered_sha(states_file, inputs.get("sha256"), str(src))
    w = registered_world(world_id)
    if list(meta.get("places", [])) != [p.name for p in w.finite] or list(meta.get("steps", [])) != [s.name for s in w.steps]:
        raise RecordFormatError(f"{src}: places or steps out of the registered order")
    tag = pair_tag(meta.get("conventions"))
    arrays = load_npz(arrays_path)
    for name in ("input_states", "a_plus", "a_minus"):
        if name not in arrays:
            raise MissingRecord(f"{src}/probe.npz lacks {name!r}")
    dst.mkdir(parents=True, exist_ok=False)
    (dst / "probe.json").write_text(json.dumps(dict(world=world_id, conventions=meta["conventions"],
                                                    steps=meta["steps"], places=meta["places"],
                                                    engine=dict(source=meta.get("source"), path=str(src)))))
    np.savez(dst / "probe.npz", input_states=np.asarray(arrays["input_states"], dtype=np.int64),
             a_plus=np.asarray(arrays["a_plus"], float), a_minus=np.asarray(arrays["a_minus"], float))
    write_manifest(dst, ["probe.json", "probe.npz"])
    return tag


# ---------------------------------------------------------------- worlds

def _f(x) -> float:
    """A float from a number or an exact 'p/q' string (the registered files write chi exactly)."""
    if isinstance(x, str):
        from fractions import Fraction

        return float(Fraction(x))
    return float(x)


def world_differences(engine_world: dict, world_id: str) -> list:
    """Field-by-field differences between a bundle's world.json ``world`` and the registered world."""
    reg = json.loads((DESIGN_DIR / f"{world_id}.world.json").read_text())
    diff = []

    def same(a, b, what):
        if a != b:
            diff.append(f"{what}: engine {a!r}, registered {b!r}")

    units = engine_world.get("units", {})
    same(_f(units.get("standard_concentration_mM", math.nan)), _f(reg["standard_concentration_mM"]["float"]), "c0")
    same(_f(units.get("temperature_K", math.nan)), _f(reg["temperature_K"]), "temperature")
    same(engine_world.get("world_role"), reg.get("world_role"), "world_role")
    same(engine_world.get("founder"), reg["initial_state"], "founder")
    pool = engine_world.get("phases", {}).get("pool", {})
    same(_f(pool.get("volume_L", math.nan)), _f(reg["phases"]["pool"]["volume_L"]["float"]), "pool volume_L")
    held = {(p["species"]): _f(p["held_mM"]["float"]) for p in reg["places"] if "held_mM" in p}
    eng_held = {s["id"]: _f(s["held_mM"]) for s in pool.get("species", []) if s.get("kind") == "held"}
    same(eng_held, held, "held pool species")
    same(sorted(engine_world.get("phases", {}).get("membrane", {}).get("species", [])),
         sorted(p["species"] for p in reg["places"] if p["phase"] == "membrane"), "membrane species")
    eng_sp = {s["id"]: s for s in engine_world.get("species", [])}
    for s in reg["species"]:
        e = eng_sp.get(s["id"])
        if e is None:
            diff.append(f"species {s['id']} missing")
            continue
        same(e.get("moieties"), s["moieties"], f"{s['id']} moieties")
        for kind, mu in s["standard_mu_RT"].items():
            same(_f(e.get("standard_mu_RT", {}).get(kind, math.nan)), _f(mu["float"]), f"{s['id']} mu0 {kind}")
    eng_steps = {s["id"]: s for s in engine_world.get("steps", [])}
    same(sorted(eng_steps), sorted(s["id"] for s in reg["steps"]), "step ids")
    for s in reg["steps"]:
        e = eng_steps.get(s["id"], {})
        for key in ("reactants", "products", "locus"):
            same(e.get(key), s[key], f"{s['id']} {key}")
        same(_f(e.get("forward_rate_per_s", math.nan)), _f(s["forward_rate_per_s"]["float"]), f"{s['id']} rate")
    chi = {}
    for fe in engine_world.get("free_energy", []):
        for entry in fe.get("chi_kT", []):
            chi[frozenset(entry["pair"])] = _f(entry["chi"])
    same(chi, {frozenset(e["pair"]): _f(e["chi"]) for e in reg.get("regular_mixing_chi", [])}, "chi")
    rf = engine_world.get("rate_factor") or {}
    eng_cat = sorted((e["step"], e["catalyst"], _f(e["ddG_kT"])) for e in rf.get("entries", []))
    reg_cat = sorted((s["id"], c["catalyst"].split("@")[0], _f(c["ddG_kT"])) for s in reg["steps"]
                     for c in s.get("transition_state_factor", []))
    same(eng_cat, reg_cat, "catalysts")
    if reg_cat:
        same(rf.get("catalysing_phase"), "membrane", "catalysing phase")
    return diff


# ---------------------------------------------------------------- run bundles

def stream_identity(stream: dict) -> str:
    try:
        return f"seed={stream['seed']}/environment={stream['environment']}/lineage={stream['lineage']}/branch={stream['branch']}"
    except KeyError as exc:
        raise MissingRecord(f"run.json stream lacks {exc}") from exc


def convert_run(src: Path, dst: Path, world_id: str) -> str:
    if (src / "refused.json").is_file():
        raise MissingRecord(f"{src}: the engine refused the run ({load_json(src / 'refused.json').get('message')})")
    manifest = load_json(src / "manifest.json")
    for name, h in (manifest.get("files_sha256") or {}).items():
        if not (src / name).is_file() or sha256(src / name) != h:
            raise RecordFormatError(f"{src}/{name} does not have its manifest SHA-256")
    if not manifest.get("files_sha256"):
        raise MissingRecord(f"{src}/manifest.json lists no file hashes")
    run = load_json(src / "run.json")
    world = load_json(src / "world.json")
    tag = pair_tag(run.get("conventions"))
    if world.get("world", {}).get("conventions") != run.get("conventions"):
        raise RecordFormatError(f"{src}: the world's conventions differ from the run's")
    diff = world_differences(world.get("world", {}), world_id)
    if diff:
        raise RecordFormatError(f"{src}: the engine's world is not the registered {world_id}: {diff[:4]}")
    tokens = run.get("ssa", {}).get("tokens", {})
    if any(tokens.get(k) != v for k, v in ENGINE_SSA.items()):
        raise RecordFormatError(f"{src}: SSA tokens {tokens}; {ENGINE_SSA} expected")
    w = registered_world(world_id)
    names = [st.name for st in w.steps]
    rows = []
    for row in run.get("channels", {}).get("rows", []):
        d = {"forward": 1, "reverse": -1}.get(row.get("direction"))
        if d is None or row.get("step") not in names:
            raise RecordFormatError(f"{src}: channel row {row}")
        rows.append(dict(step=row["step"], direction=d, code=int(row["event_channel"])))
    status = run.get("end", {}).get("status")
    if status not in KNOWN_END:
        raise RecordFormatError(f"{src}: end status {status!r} is not one FORMAT.md names")
    rec = load_npz(src / "records.npz")
    need = ("row_event", "row_kind", "place_count", "event_heat_kT", "reservoir_work_kT", "event_time", "event_channel")
    absent = [k for k in need if k not in rec]
    if absent:
        raise MissingRecord(f"{src}/records.npz lacks {absent}")
    place_names = [p["name"] for p in sorted(run["places"], key=lambda p: p["index"])]
    try:
        cols = [place_names.index(p.name) for p in w.finite]
    except ValueError as exc:
        raise RecordFormatError(f"{src}: a registered place is not among the run's places") from exc
    kind = np.asarray(rec["row_kind"])
    keep = [k for k in range(len(kind)) if kind[k] in (0, 1)]
    ends = [k for k in range(len(kind)) if kind[k] == 2]
    if len(ends) != 1:
        raise RecordFormatError(f"{src}: {len(ends)} end rows; FORMAT.md's row base has one")
    end = ends[0]
    events = np.asarray(rec["row_event"])
    same_as = [k for k in keep if events[k] == events[end]]
    if same_as:
        k = same_as[0]
        for name in ("place_count", "event_heat_kT", "reservoir_work_kT"):
            if np.asarray(rec[name][k]).tobytes() != np.asarray(rec[name][end]).tobytes():
                raise RecordFormatError(f"{src}: the end row and the periodic row at event {int(events[end])} "
                                        f"differ in {name}")
    else:
        keep.append(end)
    keep = sorted(keep, key=lambda k: (events[k], k))
    dst.mkdir(parents=True, exist_ok=False)
    canonical = dict(world=world_id, conventions=run["conventions"], ssa=dict(ENGINE_SSA), channels=rows,
                     stream=stream_identity(run.get("stream", {})), initial_state=world["world"]["founder"],
                     end_reason=END_STATUS.get(status, status),
                     engine=dict(path=str(src), source=run.get("source"), end=run.get("end")))
    (dst / "run.json").write_text(json.dumps(canonical))
    arrays = dict(event_time=np.asarray(rec["event_time"], float),
                  event_channel=np.asarray(rec["event_channel"], dtype=np.int64),
                  row_event=np.asarray(events[keep], dtype=np.int64),
                  counts=np.asarray(rec["place_count"], dtype=np.int64)[keep][:, cols],
                  heat_kT=np.asarray(rec["event_heat_kT"], float)[keep],
                  work_kT=np.asarray(rec["reservoir_work_kT"], float)[keep])
    if "event_uniforms" in rec:
        arrays["event_uniforms"] = np.asarray(rec["event_uniforms"], float)
    np.savez(dst / "records.npz", **arrays)
    write_manifest(dst, ["run.json", "records.npz"])
    return tag


# ---------------------------------------------------------------- the ladder

def convert_ensemble(src_root: Path, dst: Path, tag: str) -> None:
    design_name = DESIGN_FILE
    arrays, meta = {}, {"rungs": {}}
    for M in WB_RUNGS:
        src = src_root / f"ol1_wb_m{M}" / tag
        pmeta = load_json(src / "probe.json")
        if pmeta.get("arrays_sha256") != sha256(src / "probe.npz"):
            raise RecordFormatError(f"{src}/probe.npz does not have its declared arrays_sha256")
        wrec = pmeta.get("world", {})
        if wrec.get("registered") != f"ol1_wb_m{M}.world.json":
            raise RecordFormatError(f"{src}: world {wrec.get('registered')!r}")
        require_registered_sha(wrec["registered"], wrec.get("sha256"), str(src))
        inputs = pmeta.get("inputs", {})
        if inputs.get("file") != design_name:
            raise RecordFormatError(f"{src}: inputs from {inputs.get('file')!r}, {design_name} expected")
        require_registered_sha(design_name, inputs.get("sha256"), str(src))
        if pair_tag(pmeta.get("conventions")) != tag:
            raise RecordFormatError(f"{src}: the probe's conventions are not the pair {tag}")
        z = load_npz(src / "probe.npz")
        for name in ("observed", "status", "lineage", "input_observation_times_s"):
            if name not in z:
                raise MissingRecord(f"{src}/probe.npz lacks {name!r}")
        if [float(t) for t in z["input_observation_times_s"]] != list(OBSERVATION_TIMES):
            raise RecordFormatError(f"{src}: observation times {z['input_observation_times_s']}")
        not_complete = int(np.sum(np.asarray(z["status"]) != "complete"))
        if not_complete:
            raise RecordFormatError(f"{src}: {not_complete} runs did not end complete (held to the horizon)")
        w = registered_world(f"ol1_wb_m{M}")
        try:
            cols = [list(pmeta["places"]).index(p.name) for p in w.finite]
        except ValueError as exc:
            raise RecordFormatError(f"{src}: a registered place is not among the probe's places") from exc
        arrays[f"observation_counts_m{M}"] = np.asarray(z["observed"], dtype=np.int64)[:, :, cols]
        meta["rungs"][str(M)] = {"streams": [f"seed=1/environment=0/lineage={int(x)}/branch=0" for x in z["lineage"]],
                                 "stream_rule": pmeta.get("streams")}
    dst.mkdir(parents=True, exist_ok=False)
    (dst / "ensemble.json").write_text(json.dumps(meta))
    np.savez(dst / "ensemble.npz", **arrays)
    write_manifest(dst, ["ensemble.json", "ensemble.npz"])


# ---------------------------------------------------------------- refusals

def convert_refusals(src: Path, dst: Path) -> None:
    rec = load_json(src / "refusals.json")
    if rec.get("all_refused") is not True:
        raise RecordFormatError(f"{src}/refusals.json: all_refused is {rec.get('all_refused')!r}")
    out = {}
    for r in rec.get("results", []):
        name = r.get("registered", "")
        require_registered_sha(name, r.get("sha256"), f"{src}/refusals.json")
        out[name[: -len(".world.json")]] = dict(refused=bool(r.get("refused")), message=r.get("message"),
                                                parsed_under=r.get("conventions"))
    dst.mkdir(parents=True, exist_ok=False)
    (dst / "refusals.json").write_text(json.dumps(out, indent=1))
    write_manifest(dst, ["refusals.json"])


# ---------------------------------------------------------------- the whole set

def convert(probes_dir, out_dir) -> tuple[dict, dict]:
    """Convert the set into canonical records under out_dir. Returns (roles per pair, provenance):
    roles[tag] maps every role; the per-pair roles hold both pairs, and ``wb_ensemble`` and
    ``rescale_pair`` hold the given pair's records."""
    root, out = Path(probes_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    prov = check_index(root)
    tags = [PAIR_TAGS[(p["condensed_measure"], p["last_molecule"])] for p in PROBED_CONVENTIONS]
    common = {k: [] for k in ("kernel_probe", "boundary_probe", "closed_world", "closed_world_uncatalysed",
                              "ledger_run", "replay", "other_stream")}
    for tag in tags:
        common["kernel_probe"].append(str(out / "kernel_probe" / tag))
        convert_probe(root / "kernel_probe" / tag, out / "kernel_probe" / tag, "ol1_wa", KERNEL_PROBE_FILE)
        common["boundary_probe"].append(str(out / "boundary_probe" / tag))
        convert_probe(root / "boundary_probe" / tag, out / "boundary_probe" / tag, "ol1_boundary", BOUNDARY_PROBE_FILE)
        for wid, role in (("ol1_wa_closed", "closed_world"), ("ol1_wa_closed_uncatalysed", "closed_world_uncatalysed")):
            common[role].append(str(out / role / tag))
            convert_probe(root / "closed_world" / wid / tag, out / role / tag, wid, CLOSED_WORLD_FILE)
        for role in ("ledger_run", "replay", "other_stream"):
            common[role].append(str(out / role / tag))
            convert_run(root / role / tag, out / role / tag, "ol1_wa")
    convert_refusals(root / "refusals", out / "refusals")
    roles = {}
    for tag in tags:
        convert_ensemble(root / "wb_ensemble", out / "wb_ensemble" / tag, tag)
        pair = {}
        for wid, key in (("ol1_wa_closed", "base"), ("ol1_wa_closed_x2", "scaled")):
            convert_run(root / "rescale_pair" / tag / wid, out / "rescale_pair" / tag / wid, wid)
            pair[key] = str(out / "rescale_pair" / tag / wid)
        roles[tag] = dict(common, refusals=str(out / "refusals"), wb_ensemble=str(out / "wb_ensemble" / tag),
                          rescale_pair=pair)
    (out / "roles.json").write_text(json.dumps(roles, indent=1))
    return roles, prov


def copy_format(probes_dir, out_dir) -> None:
    """Keep a copy of the set's FORMAT.md beside the verdict, for the record."""
    shutil.copyfile(Path(probes_dir) / "FORMAT.md", Path(out_dir) / "FORMAT.md")
