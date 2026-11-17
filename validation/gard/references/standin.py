"""A complete stand-in record set built by the host oracle, for dry-running the harness.

``build_standin`` writes every role the harness reads. The engine's roles come from
``lineage_oracle``, and the probe outputs come from the references' own functions. This
lets the harness, the record layout and every planted control be exercised end to end
before the engine exists. It is never a substitute for the engine's records: a pass
here shows only that the harness reads what it should and fails when it should.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import closed_world, detailed_balance, exchange_law, fission_partition, observers
from .harness import CLOSED_WORLD_CONFIGS, probe_input_arrays
from .kernels import (EXTINCTION_UNCATALYSED, PAIR_CONSISTENT, SINGLE_EVENT, ExchangeLaw, HeldReservoir, PREPRINT,
                      gard_beta, gard_founder)
from .lineage_oracle import DOMAIN_PARTITION, _split, simulate_lineage, stream_uniforms
from .records import write_bundle


def preprint_law(seed: int, form: str, n_types: int = PREPRINT["n_types"],
                 founder_mass: int | None = None) -> tuple[ExchangeLaw, np.ndarray]:
    """The preprint's world (p. 10, Appendix F); smaller ``n_types`` keep the same constants."""
    rng = np.random.default_rng(seed)
    beta = gard_beta(n_types, rng)
    mass = min(PREPRINT["founder_mass"], n_types) if founder_mass is None else founder_mass
    founder = gard_founder(n_types, mass, rng)
    law = ExchangeLaw(beta, PREPRINT["k_join"], PREPRINT["k_leave"], HeldReservoir(np.full(n_types, PREPRINT["rho"])),
                      form, EXTINCTION_UNCATALYSED)
    return law, founder


def write_probe(path: Path, meta: dict, arrays: dict) -> Path:
    path.mkdir(parents=True, exist_ok=False)
    (path / "probe.json").write_text(json.dumps(meta, sort_keys=True, indent=1))
    np.savez(path / "probe.npz", **arrays)
    (path / "manifest.json").write_text(json.dumps({"complete": True}))
    return path


def ensemble_arrays(runs: int, *, kb_factor: float = 1.0, leave_weight: float = 1.0,
                    seed: int = 11) -> list[tuple[dict, dict, dict]]:
    """The registered beta = 0 ensemble in memory: (world, run, arrays) per run.

    ``kb_factor`` != 1 plants a wrong k_b: the dynamics use it while the world record
    declares the registered k_b. ``leave_weight`` != 1 plants a biased channel choice.
    """
    d = exchange_law.REGISTERED_DESIGN
    G = len(d["rho"])
    law = ExchangeLaw(np.zeros((G, G)), d["k_join"], d["k_leave"] * kb_factor, HeldReservoir(np.asarray(d["rho"])),
                      PAIR_CONSISTENT, EXTINCTION_UNCATALYSED)
    founder = np.asarray(d["founder"], dtype=np.int64)
    out = []
    world = None
    for r in range(runs):
        world, run, arrays = simulate_lineage(law, founder, fission_mass=10 ** 9, n_fissions=1, seed=seed, branch=r,
                                              t_max=float(d["times"][-1]), event_guard=None, diagnostics=False,
                                              leave_weight=leave_weight, world=world)
        if kb_factor != 1.0 and r == 0:
            world = json.loads(json.dumps(world))
            world["constants"]["k_leave"] = [float(d["k_leave"])] * G
        out.append((world, run, arrays))
    return out


def ensemble_runs(out: Path, runs: int, **kw) -> list[str]:
    """The registered ensemble written as one bundle per run."""
    return [str(write_bundle(out / f"run{r:04d}", w, rr, a)) for r, (w, rr, a) in enumerate(ensemble_arrays(runs, **kw))]


def build_standin(out_dir: str | Path, *, seed: int = 5, n_fissions: int = 12, ensemble: int | None = None) -> dict:
    """Write every role; return the roles mapping the harness reads."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    roles: dict = {}
    pc, founder = preprint_law(seed, PAIR_CONSISTENT)
    se = pc.with_form(SINGLE_EVENT)
    w, r, a = simulate_lineage(pc, founder, n_fissions=n_fissions, seed=seed, diagnostics=False)
    roles["lineage"] = str(write_bundle(out / "lineage", w, r, a))
    w2, r2, a2 = simulate_lineage(se, founder, n_fissions=n_fissions, seed=seed, diagnostics=False, world=w)
    roles["lineage_single_event"] = str(write_bundle(out / "lineage_single_event", w2, r2, a2))
    w3, r3, a3 = simulate_lineage(pc, founder, n_fissions=n_fissions, seed=seed, diagnostics=True, world=w)
    roles["lineage_diagnostic"] = str(write_bundle(out / "lineage_diagnostic", w3, r3, a3))
    roles["replay"] = str(write_bundle(out / "replay", w, r, a))
    roles["batched"] = str(write_bundle(out / "batched", w, r, a))
    restart_run = dict(r, restart={"row": 5, "event": int(a["row_event"][5]), "fission": 2})
    tail = {k: v for k, v in a.items()}
    roles["restart"] = [str(write_bundle(out / "restart_mid", w, restart_run, tail))]
    roles["branches"] = []
    for k in range(3):
        wb, rb, ab = simulate_lineage(pc, founder, n_fissions=3, seed=seed, branch=100 + k, diagnostics=True, world=w)
        roles["branches"].append(str(write_bundle(out / f"branch{k}", wb, rb, ab)))
    # rescaling pair: beta = 0 and uniform beta = 1 (scale 2, exact in binary)
    G = pc.n_types
    l0 = pc.with_beta(np.zeros((G, G)))
    l1 = pc.with_beta(np.ones((G, G)))
    for name, law in (("rescale_beta0", l0), ("rescale_betac", l1)):
        wr, rr, ar = simulate_lineage(law, founder, n_fissions=4, seed=seed + 1, diagnostics=False)
        roles[name] = str(write_bundle(out / name, wr, rr, ar))
    # beta = 0 ensemble
    n_ens = exchange_law.REGISTERED_DESIGN["runs"] if ensemble is None else ensemble
    roles["beta0_ensemble"] = ensemble_runs(out / "beta0_ensemble", n_ens, seed=seed + 2)
    # probe outputs
    inputs = probe_input_arrays()
    kin = inputs["kernel_probe_inputs"]
    kp = dict(kin)
    verdicts = {}
    for form in (PAIR_CONSISTENT, SINGLE_EVENT):
        law = ExchangeLaw(kin["beta"], kin["k_join"], kin["k_leave"], HeldReservoir(kin["rho"]), form,
                          EXTINCTION_UNCATALYSED)
        t = detailed_balance.kernel_table(law, kin["states"])
        tag = form.replace("-", "_")
        kp.update({f"join_{tag}": t["join"], f"leave_{tag}": t["leave"], f"leave_up_{tag}": t["leave_up"]})
        r_max = float(np.nanmax(np.abs(detailed_balance.ldb_residuals_from_table(t["join"], t["leave_up"],
                                                                               t["affinity"]))))
        verdicts[form] = detailed_balance.classify(r_max)
    roles["kernel_probe"] = str(write_probe(out / "kernel_probe", {"check_verdict": verdicts,
                                                                   "boundary": EXTINCTION_UNCATALYSED}, kp))
    cw: dict = {}
    for cfg in CLOSED_WORLD_CONFIGS:
        cin = inputs[f"closed_world_{cfg['name']}_inputs"]
        for form in (PAIR_CONSISTENT, SINGLE_EVENT):
            law = ExchangeLaw(cin["beta"], cin["k_join"], cin["k_leave"], HeldReservoir(cin["rho"]), form,
                              EXTINCTION_UNCATALYSED)
            tag = f"{cfg['name']}_{form.replace('-', '_')}"
            j = np.zeros(cin["states"].shape)
            lv = np.zeros(cin["states"].shape)
            for k, x in enumerate(cin["states"]):
                from .kernels import propensities
                j[k], lv[k] = propensities(law, x)
            cw.update({f"states_{tag}": cin["states"], f"join_{tag}": j, f"leave_{tag}": lv})
    roles["closed_world"] = str(write_probe(out / "closed_world", {}, cw))
    part: dict = {}
    P = fission_partition.REGISTERED_PARENT
    for rule in ("exact_fraction", "binomial"):
        splits = []
        for f in range(fission_partition.REGISTERED_FISSIONS):
            u = stream_uniforms(seed, DOMAIN_PARTITION, 7, f + (0 if rule == "binomial" else 10 ** 6), int(P.sum()))
            splits.append(_split(P, rule, 0.5, 0.5, u))
        part[f"parents_{rule}"] = np.tile(P, (len(splits), 1))
        part[f"splits_{rule}"] = np.asarray(splits)
    roles["partition_probe"] = str(write_probe(out / "partition_probe", {}, part))
    oin = inputs["observer_probe_inputs"]
    H = np.array([observers.similarity(p, d) for p, d in zip(oin["probe_parent"], oin["probe_daughter"])])
    I = np.array([observers.inherited_exact(p, d) for p, d in zip(oin["probe_parent"], oin["probe_daughter"])])
    roles["observer_probe"] = str(write_probe(out / "observer_probe", {}, dict(oin, H=H, inherited=I)))
    roles["f12_table"] = str(write_probe(out / "f12_table", {"bit_order": "lsb_first"},
                                         {"verdicts": observers.f12_reference_table()}))
    (out / "roles.json").write_text(json.dumps(roles, indent=1))
    return roles
