"""OL5 references, the engine adapter: OL1's FORMAT.md layout read into the canonical records.

A writer here turns the stand-in's canonical records into FORMAT.md's layout (the engine's
names, signed channel codes, held places in run.json's place order, the row base with its end
row, hashed files), so the adapter is tested without engine output. On the round trip every
registered row passes; each planted defect in the layout is refused (status 2) by the check that
owns it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from validation.ool.references import engine_layout as EL
from validation.ool.references import harness as H
from validation.ool.references import standin as S
from validation.ool.references.common import MissingRecord, RecordFormatError
from validation.ool.references.design import (
    BOUNDARY_PROBE_FILE,
    CLOSED_WORLD_FILE,
    DESIGN_FILE,
    KERNEL_PROBE_FILE,
    LEDGER_RUN,
    PROBED_CONVENTIONS,
    RESCALE_RUN,
)
from validation.ool.references.registered import DESIGN_DIR, WB_RUNGS, registered_world
from validation.ool.references.world import Conventions

TAGS = {0: "multinomial__kept", 1: "multinomial_less_one__extinct"}


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def engine_world(world_id: str, conventions: dict) -> dict:
    reg = json.loads((DESIGN_DIR / f"{world_id}.world.json").read_text())
    pool = reg["phases"]["pool"]
    pool_species = []
    for p in reg["places"]:
        if p["phase"] == "pool":
            entry = {"id": p["species"], "kind": "held" if "held_mM" in p else "finite"}
            if "held_mM" in p:
                entry["held_mM"] = p["held_mM"]["float"]
            pool_species.append(entry)
    w = {"units": {"standard_concentration_mM": reg["standard_concentration_mM"]["float"],
                   "temperature_K": reg["temperature_K"], "time": "s"},
         "conventions": conventions, "founder": reg["initial_state"],
         "phases": {"membrane": {"species": [p["species"] for p in reg["places"] if p["phase"] == "membrane"]},
                    "pool": {"species": pool_species, "volume_L": pool["volume_L"]["float"]}},
         "species": [{"id": s["id"], "moieties": s["moieties"],
                      "standard_mu_RT": {k: v["float"] for k, v in s["standard_mu_RT"].items()}} for s in reg["species"]],
         "steps": [{"id": s["id"], "reactants": s["reactants"], "products": s["products"], "locus": s["locus"],
                    "forward_rate_per_s": s["forward_rate_per_s"]["float"]} for s in reg["steps"]],
         "free_energy": [{"law": "cells.free_energy.ideal_mixing@1"},
                         {"law": "cells.free_energy.regular_mixing@1",
                          "chi_kT": [{"pair": e["pair"], "chi": float(Fraction(e["chi"]))} for e in reg["regular_mixing_chi"]]}],
         "rate_factor": {"catalysing_phase": "membrane",
                         "entries": [{"step": s["id"], "catalyst": c["catalyst"].split("@")[0], "ddG_kT": c["ddG_kT"]}
                                     for s in reg["steps"] for c in s["transition_state_factor"]]}}
    if "world_role" in reg:
        w["world_role"] = reg["world_role"]
    return w


def write_probe(src: Path, dst: Path, role: str, world_id: str, states_file: str) -> None:
    meta = json.loads((src / "probe.json").read_text())
    dst.mkdir(parents=True)
    shutil.copyfile(src / "probe.npz", dst / "probe.npz")
    (dst / "probe.json").write_text(json.dumps(dict(
        format="cells.assembly_lineages.probe@2", role=role, source={"revision": "test"},
        inputs={"file": states_file, "sha256": sha(DESIGN_DIR / states_file)}, arrays_sha256=sha(dst / "probe.npz"),
        world={"registered": f"{world_id}.world.json", "sha256": sha(DESIGN_DIR / f"{world_id}.world.json")},
        conventions=meta["conventions"], places=meta["places"], steps=meta["steps"])))


def write_run(src: Path, dst: Path, world_id: str, mutate=None) -> None:
    meta = json.loads((src / "run.json").read_text())
    with np.load(src / "records.npz") as z:
        rec = {k: z[k] for k in z.files}
    w = registered_world(world_id)
    finite = [p.name for p in w.finite]
    held = [p for p in w.places.values() if p.held]
    order = [p.name for p in held] + [n for n in finite if not n.endswith("@membrane")] + \
        [n for n in finite if n.endswith("@membrane")]
    names = [st.name for st in w.steps]
    code_of = {}
    rows = []
    for k, row in enumerate(meta["channels"]):
        r = names.index(row["step"])
        code = (r + 1) * row["direction"]
        code_of[row["code"]] = code
        rows.append(dict(direction="forward" if row["direction"] > 0 else "reverse", event_channel=code,
                         step=row["step"], row=k))
    counts = np.zeros((len(rec["row_event"]), len(order)), dtype=np.int64)
    for j, name in enumerate(order):
        if name in finite:
            counts[:, j] = rec["counts"][:, finite.index(name)]
    E = len(rec["event_channel"])
    row_kind = np.ones(len(rec["row_event"]), dtype=np.int8)
    row_kind[0] = 0
    # FORMAT.md's row base: the end row repeats the last periodic row when they share the event count
    re_ = np.concatenate([rec["row_event"], rec["row_event"][-1:]])
    rk = np.concatenate([row_kind, np.array([2], dtype=np.int8)])
    out = dict(row_event=re_, row_kind=rk, place_count=np.concatenate([counts, counts[-1:]]),
               event_heat_kT=np.concatenate([rec["heat_kT"], rec["heat_kT"][-1:]]),
               reservoir_work_kT=np.concatenate([rec["work_kT"], rec["work_kT"][-1:]]),
               event_time=rec["event_time"],
               event_channel=np.array([code_of[int(c)] for c in rec["event_channel"]], dtype=np.int32),
               event_uniforms=rec["event_uniforms"])
    lineage = int(meta["stream"].rsplit("-", 1)[-1]) if meta["stream"][-1].isdigit() else 0
    run = dict(format="cells.assembly_lineages.run@2", conventions=meta["conventions"],
               ssa={"tokens": {"tau": "neg_log_u1_over_a0", "select": "first_prefix_gt_u2_a0"}},
               channels={"rows": rows},
               stream={"seed": 1, "environment": 0, "lineage": lineage if "other" not in meta["stream"] else 99,
                       "branch": 0},
               end={"status": "event_limit" if meta["end_reason"] == "max_events" else meta["end_reason"],
                    "events": E}, source={"revision": "test"},
               places=[{"index": i, "name": n} for i, n in enumerate(order)])
    world = dict(format="cells.assembly_lineages.world@2", id="test", world=engine_world(world_id, meta["conventions"]))
    if mutate:
        mutate(run, world, out)
    dst.mkdir(parents=True)
    (dst / "run.json").write_text(json.dumps(run))
    (dst / "world.json").write_text(json.dumps(world))
    np.savez(dst / "records.npz", **out)
    (dst / "manifest.json").write_text(json.dumps(dict(files_sha256={f: sha(dst / f) for f in
                                                                      ("run.json", "world.json", "records.npz")})))


def write_engine_set(roles: dict, root: Path, mutate_run=None) -> Path:
    root.mkdir(parents=True)
    for i, (kp, bp, cw, cu, lr, rp, os_) in enumerate(zip(roles["kernel_probe"], roles["boundary_probe"],
                                                           roles["closed_world"], roles["closed_world_uncatalysed"],
                                                           roles["ledger_run"], roles["replay"], roles["other_stream"])):
        t = TAGS[i]
        write_probe(Path(kp), root / "kernel_probe" / t, "kernel_probe", "ol1_wa", KERNEL_PROBE_FILE)
        write_probe(Path(bp), root / "boundary_probe" / t, "boundary_probe", "ol1_boundary", BOUNDARY_PROBE_FILE)
        write_probe(Path(cw), root / "closed_world" / "ol1_wa_closed" / t, "closed_world", "ol1_wa_closed",
                    CLOSED_WORLD_FILE)
        write_probe(Path(cu), root / "closed_world" / "ol1_wa_closed_uncatalysed" / t, "closed_world",
                    "ol1_wa_closed_uncatalysed", CLOSED_WORLD_FILE)
        write_run(Path(lr), root / "ledger_run" / t, "ol1_wa", mutate_run)
        write_run(Path(rp), root / "replay" / t, "ol1_wa")
        write_run(Path(os_), root / "other_stream" / t, "ol1_wa")
        for wid, key in (("ol1_wa_closed", "base"), ("ol1_wa_closed_x2", "scaled")):
            write_run(Path(roles["rescale"][i][key]), root / "rescale_pair" / t / wid, wid)
        meta = json.loads((Path(roles["wb_ensemble"]) / "ensemble.json").read_text())
        with np.load(Path(roles["wb_ensemble"]) / "ensemble.npz") as z:
            ens = {k: z[k] for k in z.files}
        for q, M in enumerate(WB_RUNGS):
            d = root / "wb_ensemble" / f"ol1_wb_m{M}" / t
            d.mkdir(parents=True)
            obs = ens[f"observation_counts_m{M}"]
            # the registered design: every run its own stream, none shared (across rungs as well)
            np.savez(d / "probe.npz", observed=obs[:, :, [1, 2, 0]], status=np.array(["complete"] * len(obs)),
                     lineage=10000 * q + np.arange(len(obs)), events=np.ones(len(obs), dtype=np.int64),
                     input_observation_times_s=np.array([0.25, 0.5, 1.0, 2.0]))
            (d / "probe.json").write_text(json.dumps(dict(
                arrays_sha256=sha(d / "probe.npz"), conventions=Conventions(**PROBED_CONVENTIONS[i]).as_dict(),
                world={"registered": f"ol1_wb_m{M}.world.json", "sha256": sha(DESIGN_DIR / f"ol1_wb_m{M}.world.json")},
                inputs={"file": DESIGN_FILE, "sha256": sha(DESIGN_DIR / DESIGN_FILE)},
                places=["S@pool", "T@pool", "L@membrane"], streams="one per run")))
        del meta
    ref = json.loads((Path(roles["refusals"]) / "refusals.json").read_text())
    (root / "refusals").mkdir()
    (root / "refusals" / "refusals.json").write_text(json.dumps(dict(all_refused=True, results=[
        dict(registered=f"{rid}.world.json", sha256=sha(DESIGN_DIR / "refusals" / f"{rid}.world.json"),
             refused=v["refused"], message=v["message"], conventions=v["parsed_under"]) for rid, v in ref.items()])))
    files = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}
    (root / "FORMAT.md").write_text("test layout\n")
    files["FORMAT.md"] = sha(root / "FORMAT.md")
    (root / "roles.json").write_text(json.dumps(dict(
        files=files, inputs={"directory": "/x/inputs-test", "files": {n: sha(DESIGN_DIR / n) for n in
                                                                     (KERNEL_PROBE_FILE, DESIGN_FILE)}},
        pairs=[Conventions(**p).as_dict() for p in PROBED_CONVENTIONS], source={"revision": "test", "dirty": False})))
    return root


@pytest.fixture(scope="module")
def standin(tmp_path_factory):
    base = tmp_path_factory.mktemp("ool-engine-layout")
    roles = S.build_standin(base / "canonical")
    conv = Conventions(**PROBED_CONVENTIONS[1])
    second = {key: str(S.write_run(base / f"rescale-{key}", wid, conv, 301, max_events=RESCALE_RUN["events"],
                                   row_every=RESCALE_RUN["events"], t_end=1e9, stream="standin-rescale"))
              for wid, key in (("ol1_wa_closed", "base"), ("ol1_wa_closed_x2", "scaled"))}
    roles["rescale"] = [roles["rescale_pair"], second]
    return base, roles


def test_the_round_trip_passes_every_registered_row(standin):
    base, roles = standin
    root = write_engine_set(roles, base / "engine")
    canon, prov = EL.convert(root, base / "converted")
    assert prov["inputs_pin"] == "test" and prov["files_checked"] > 50
    for tag, r in canon.items():
        status, report = H.run_rows(r, None if tag == "multinomial__kept" else ["OL1-3", "OL1-4"])
        assert status == 0, {k: v for k, v in report.items() if not v["passed"]}
    # the row base comes back as registered: every 100 events and the last, once each
    with np.load(Path(canon["multinomial__kept"]["ledger_run"][0]) / "records.npz") as z:
        assert z["row_event"].tolist() == list(range(0, LEDGER_RUN["max_events"] + 1, LEDGER_RUN["row_every_events"]))


def _refused(roles, base, name, mutate_run=None, edit=None):
    root = write_engine_set(roles, base / name, mutate_run)
    if edit:
        edit(root)
    with pytest.raises((MissingRecord, RecordFormatError)) as exc:
        EL.convert(root, base / f"{name}-out")
    return str(exc.value)


def test_planted_defects_in_the_layout_are_refused(standin):
    base, roles = standin

    def rate(run, world, rec):
        world["world"]["steps"][3]["forward_rate_per_s"] *= 1.5

    assert "is not the registered" in _refused(roles, base, "rate", rate)

    def end_row(run, world, rec):
        rec["event_heat_kT"][-1] += 1.0

    assert "end row" in _refused(roles, base, "endrow", end_row)

    def status(run, world, rec):
        run["end"]["status"] = "finished"

    assert "end status" in _refused(roles, base, "status", status)

    def ssa(run, world, rec):
        run["ssa"]["tokens"]["select"] = "first_prefix_ge_u2_a0"

    assert "SSA tokens" in _refused(roles, base, "ssa", ssa)

    def wrong_input(root):
        p = root / "kernel_probe" / TAGS[0] / "probe.json"
        meta = json.loads(p.read_text())
        meta["world"]["sha256"] = "0" * 64
        p.write_text(json.dumps(meta))
        idx = json.loads((root / "roles.json").read_text())
        idx["files"][f"kernel_probe/{TAGS[0]}/probe.json"] = sha(p)
        (root / "roles.json").write_text(json.dumps(idx))

    assert "registered file is" in _refused(roles, base, "input", edit=wrong_input)

    def tampered(root):
        p = root / "replay" / TAGS[0] / "records.npz"
        p.write_bytes(p.read_bytes() + b"x")

    assert "SHA-256" in _refused(roles, base, "tamper", edit=tampered)

    def incomplete(root):
        d = root / "wb_ensemble" / "ol1_wb_m20" / TAGS[1]
        with np.load(d / "probe.npz") as z:
            arr = {k: z[k] for k in z.files}
        arr["status"][3] = "stalled"
        np.savez(d / "probe.npz", **arr)
        meta = json.loads((d / "probe.json").read_text())
        meta["arrays_sha256"] = sha(d / "probe.npz")
        (d / "probe.json").write_text(json.dumps(meta))
        idx = json.loads((root / "roles.json").read_text())
        for f in ("probe.npz", "probe.json"):
            idx["files"][f"wb_ensemble/ol1_wb_m20/{TAGS[1]}/{f}"] = sha(d / f)
        (root / "roles.json").write_text(json.dumps(idx))

    assert "did not end complete" in _refused(roles, base, "incomplete", edit=incomplete)
