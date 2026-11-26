"""The probe driver: the engine on GARD's registered probe inputs, with their bundles (G2's roles).

GARD's G2 references (validation/gard/references/) are independent of the engine; their
`make-probes` command writes the registered probe inputs, and their harness reads the engine's
saved outputs by role. This driver runs the engine (cells.model.assembly_lineages@1) on those inputs and
on the lineages the roles name, and saves the outputs in the engine's own format: run bundles
(records.py) for lineages, and probe files for the probes. It reads only the inputs' files, never
the references' code.

    python -m validation.assembly_lineages.probes freeze OUT
        freezes the checkout's source (validation/source_snapshot.py) into OUT/source;
    cd OUT/source && PYTHONPATH=src:. python -m validation.assembly_lineages.probes run INPUTS OUT
        runs from that snapshot (so every record names the revision) on the make-probes
        directory INPUTS, writing OUT/roles.json and one directory per role.

**The roles** (the settings not in the registered inputs were approved by the lead on 17 November
2026, and each is recorded in its output):
- `lineage`, `lineage_single_event`, `lineage_diagnostic`: the T2-02-like world (worlds.py; matrix
  seed 20261117, founder seed 1117), stream seed 1, 100 fissions; the pair-consistent form, the
  single-event form, and the pair-consistent form with every draw's uniforms;
- `replay`: `lineage` run again; `batched`: `lineage` as lane 0 of four (lineage words 0-3);
- `restart`: `lineage_diagnostic` stopped mid-growth (halfway through growth 2) and at the join
  that makes fission 3 due (its fission pending), each continued from its checkpoint;
- `branches`: `lineage_diagnostic`'s post-fission landmark at fission 20, then 8 branch words
  (1-8), 12 fissions each, with uniforms (diagnostic);
- `beta0_ensemble`: G2's registered design (ENSEMBLE_DESIGN): the exchange law alone on four
  types, 500 lineages (lineage words 0-499), each observed past t = 2;
- `rescale_beta0`, `rescale_betac`: the pair-consistent form on the T2-02-like world with beta = 0
  and with beta = 3 everywhere (so 1 + c = 4, a power of two: the same events, every time scaled
  by exactly 1/4), one set of streams, 5 fissions, with uniforms;
- `kernel_probe`: both forms' rates at each registered state n, and each type's leave at
  n + e_i (the reverse of its join), from the kernel's own rate function, the catalysis state
  computed exactly at each state (as the kernel holds it at a founder or a daughter);
- `closed_world`: both forms' rates and factors at each registered state of each closed world. The
  engine's exchange law has a held reservoir only: joins are at the held activity `rho` as
  registered, and the inputs' finite pool (M) and theta are not used. A finite shared pool is an
  engine gap (the origin-of-life note's R5);
- `partition_probe`: the engine's fission pass on the registered parent, 400 times per rule, each
  split keyed by its own lineage word (0-399);
- `observer_probe`: the kernel's H (its cosine) of each registered parent-daughter pair;
- `f12_table`: the F12 event over all 4,096 twelve-boundary sequences (inheritance.py).
Every probe output echoes its registered inputs unmodified (`input_*` arrays), with the inputs
file's SHA-256.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROBE_FORMAT = "cells.assembly_lineages.probe@1"
MATRIX_SEED, FOUNDER_SEED, STREAM_SEED = 20261117, 1117, 1
FISSIONS = 100
BRANCH_LANDMARK, BRANCH_WORDS, BRANCH_FISSIONS = 20, tuple(range(1, 9)), 12
# G2's registered design of the beta = 0 ensemble: four types, k_join = 1, k_leave = 0.5, held
# activities (0.1, 0.2, 0.3, 0.4), the founder (5, 5, 5, 5), no catalysis, 500 lineages observed
# to t = 2. The values are read from the registered design file that make-probes writes beside
# inputs.json (inputs.json names it), and each must equal these constants, or the role refuses.
# The engine has no time horizon, so each lineage
# runs to its first fission at a size it cannot reach by t = 2 (2,048; its expected size there is
# about 54), under an event guard it cannot reach first (4,096), as the lead ruled: every event to
# t = 2 is in its trace, and the ensemble's record says, for each lineage, that it did not stop
# before t = 2 (its run.json's end.time is past it).
ENSEMBLE_DESIGN = {
    "types": 4,
    "k_join": 1.0,
    "k_leave": 0.5,
    "rho": (0.1, 0.2, 0.3, 0.4),
    "founder": (5, 5, 5, 5),
    "runs": 500,
    "t_end": 2.0,
}
ENSEMBLE_FISSION_SIZE, ENSEMBLE_GUARD = 2048, 4096
RESCALE_C, RESCALE_FISSIONS = 3.0, 5
PROBE_FISSION_SIZE = 128  # Probe worlds never run a lineage; above every registered state.


def snapshot_files():
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        + ["--", "src/cells", "validation/assembly_lineages", "validation/source_snapshot.py"],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    names = sorted({os.fsdecode(n) for n in listed.split(b"\0") if n})
    names = [n for n in names if (ROOT / n).is_file() and "__pycache__" not in n]
    return {name: name for name in names} | {"pyproject.toml": "pyproject.toml"}


def freeze(out):
    from validation import source_snapshot

    out = Path(out)
    record = source_snapshot.freeze(ROOT, out / "source", snapshot_files())
    print(json.dumps({"source": str(out / "source"), "git_revision": record["git_revision"]}))


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True) + "\n")


def _source():
    from cells.records.run_view import _engine_source

    return _engine_source() or {"unstated": "the engine ran from a checkout, not a snapshot"}


def write_probe(directory, role, arrays, descriptor, inputs=None):
    """A probe's output: probe.npz (its arrays and the echoed inputs) and probe.json."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    saved = dict(arrays)
    echoed = {}
    if inputs is not None:
        path, values = inputs
        for name, value in values.items():
            saved[f"input_{name}"] = value
        echoed = {"file": Path(path).name, "sha256": _sha256(path), "arrays": sorted(values)}
    np.savez(directory / "probe.npz", **saved)
    _json(
        directory / "probe.json",
        {
            "format": PROBE_FORMAT,
            "role": role,
            "source": _source(),
            "inputs": echoed,
            "arrays_sha256": _sha256(directory / "probe.npz"),
            **descriptor,
        },
    )
    return directory


def _load(path):
    with np.load(path, allow_pickle=False) as saved:
        return {k: saved[k] for k in saved.files}


# ------------------------------------------------------------------ worlds


def t2_world(*, matrix=True):
    from validation.assembly_lineages import worlds

    world = worlds.t2_02_like(MATRIX_SEED, FOUNDER_SEED)
    if not matrix:
        world.pop("law_data")
    return world


def lineage_definition(law, *, fissions=FISSIONS, uniforms=False, lineage=0, branch=0):
    from validation.assembly_lineages import worlds

    data = worlds.definition(
        t2_world(matrix=law is not None), law, fissions=fissions, seed=STREAM_SEED, lineage=lineage
    )
    data["experiment"]["uniforms"] = uniforms
    data["execution"]["stream"]["branch"] = branch
    return data


def probe_world(count, k_join, k_leave, rho, beta):
    """A world for the kernel's rates at registered states: its constants as registered."""
    from cells.models.assembly_lineages import CONTINUATION, EXCHANGE_LAW, FISSION

    k_join, k_leave = np.asarray(k_join, float), np.asarray(k_leave, float)
    founder = [1] + [0] * (count - 1)
    return {
        "types": {"prefix": "t", "count": count, "transfer_constant": (k_join / k_leave).tolist()},
        "supply": np.asarray(rho, float).tolist(),
        "exchange": {"law": EXCHANGE_LAW, "leave_rate": k_leave.tolist()},
        "law_data": {"catalysis_matrix": np.asarray(beta, float).tolist()},
        "founder": founder,
        "fission": {
            "operator": FISSION,
            "size": PROBE_FISSION_SIZE,
            "partition": {"rule": "exact_fraction", "fraction": 0.5},
        },
        "continuation": {
            "operator": CONTINUATION,
            "daughter": "first",
            "empty": "extinct",
            "sink": "discard",
        },
        "units": {"time": "nominal", "temperature_K": None},
    }


def probe_definition(world, law):
    from validation.assembly_lineages import worlds

    return worlds.definition(world, law, fissions=1, seed=STREAM_SEED)


# ------------------------------------------------------------------ the kernel's rates


def rate_tables(spec, states):
    """The kernel's rates and factors at each state (rows of counts of the declared types), with
    the catalysis state computed exactly there: join [S, C], leave [S, C], g_join, g_leave."""
    import jax
    import jax.numpy as jnp

    from cells.models.assembly_lineages import exchange, factors, kernel, model

    structure = model.structure(spec)
    layout = jax.tree_util.tree_map(jnp.asarray, model.layout(spec))
    law = None if structure.factor is None else factors.resolve(structure.factor)
    count = spec.model.world.types.count
    capacity = structure.capacity
    padded = np.zeros((len(states), capacity), dtype=np.int64)
    padded[:, :count] = states

    def at(counts):
        size = jnp.sum(counts)
        state = kernel.factor_state(counts, layout, law, structure.unroll)
        rates = kernel.rates(counts, size, layout, state, law)
        n = counts.astype(jnp.float64)
        base_join, base_leave = exchange.base_rates(
            n, size.astype(jnp.float64), layout.kf_rho, layout.kb
        )
        if law is None:
            g_join, g_leave = jnp.ones_like(n), jnp.ones_like(n)
        else:
            g_join, g_leave = law.factors(n, size.astype(jnp.float64), state, layout.factor, jnp)
        return rates, base_join, base_leave, g_join, g_leave

    out = jax.jit(jax.vmap(at))(jnp.asarray(padded))
    rates, bj, bl, gj, gl = (np.asarray(a) for a in out)
    return {
        "join_rate": rates[:, :count],
        "leave_rate": rates[:, capacity : capacity + count],
        "base_join_rate": bj[:, :count],
        "base_leave_rate": bl[:, :count],
        "g_join": gj[:, :count],
        "g_leave": gl[:, :count],
    }


def forms():
    """{form word: law ID}: GARD's two forms."""
    from cells.models.assembly_lineages import GARD_PAIR_CONSISTENT, GARD_SINGLE_EVENT

    return {"pair_consistent": GARD_PAIR_CONSISTENT, "single_event": GARD_SINGLE_EVENT}


def kernel_probe(inputs, out):
    from cells.definitions.specs import parse_spec

    path = Path(inputs) / "kernel_probe_inputs.npz"
    data = _load(path)
    states = data["states"].astype(np.int64)
    count = states.shape[1]
    arrays, definitions = {}, {}
    after = np.repeat(states, count, axis=0) + np.tile(
        np.eye(count, dtype=np.int64), (len(states), 1)
    )
    for form, law in forms().items():
        world = probe_world(count, data["k_join"], data["k_leave"], data["rho"], data["beta"])
        spec = parse_spec(probe_definition(world, law))
        definitions[form] = spec.to_dict()
        here = rate_tables(spec, states)
        there = rate_tables(spec, after)
        for name, values in here.items():
            arrays[f"{form}.{name}"] = values
        index = np.arange(count)
        arrays[f"{form}.leave_rate_after_join"] = there["leave_rate"].reshape(
            len(states), count, count
        )[:, index, index]
        arrays[f"{form}.g_leave_after_join"] = there["g_leave"].reshape(len(states), count, count)[
            :, index, index
        ]
    descriptor = {
        "definitions": definitions,
        "says": {
            "<form>.join_rate [state, type]": "the kernel's join rate of each type at state n",
            "<form>.leave_rate [state, type]": "the kernel's leave rate at n (0 where n_i = 0)",
            "<form>.leave_rate_after_join [state, type]": "type i's leave rate at n + e_i: the "
            "reverse of its join at n",
            "<form>.base_join_rate, base_leave_rate": "the exchange law's rates without factors",
            "<form>.g_join, g_leave [state, type]": "the rate factors at n",
            "<form>.g_leave_after_join [state, type]": "type i's leave factor at n + e_i",
            "forms": forms(),
            "catalysis_state": "x = beta n computed exactly at each state (a serial fold over the "
            "types), as the kernel holds it at a founder or a daughter",
            "constants": "transfer constant K_i = k_join_i / k_leave_i, leave constant "
            "k_leave_i, held activity rho_i, as registered; the join constant is K_i k_leave_i",
        },
    }
    return write_probe(out, "kernel_probe", arrays, descriptor, (path, data))


def closed_world(inputs, out):
    from cells.definitions.specs import parse_spec

    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    written = {}
    for path in sorted(Path(inputs).glob("closed_world_*_inputs.npz")):
        name = path.name[len("closed_world_") : -len("_inputs.npz")]
        data = _load(path)
        states = data["states"].astype(np.int64)
        count = states.shape[1]
        arrays, definitions = {}, {}
        for form, law in forms().items():
            world = probe_world(count, data["k_join"], data["k_leave"], data["rho"], data["beta"])
            spec = parse_spec(probe_definition(world, law))
            definitions[form] = spec.to_dict()
            for key, values in rate_tables(spec, states).items():
                arrays[f"{form}.{key}"] = values
        descriptor = {
            "world": name,
            "definitions": definitions,
            "says": {
                "<form>.join_rate, leave_rate [state, type]": "the kernel's rates at each "
                "registered state",
                "<form>.g_join, g_leave [state, type]": "the rate factors there",
                "<form>.base_join_rate, base_leave_rate": "the exchange law's rates without "
                "factors: join k_join rho N, leave k_leave n_i",
            },
            "declared": "the engine's exchange law holds its reservoir: every join is at the held "
            "activity rho as registered. The inputs' finite pool (M) and theta are not the "
            "engine's and are not used; a finite shared pool is an engine gap (the origin-of-life "
            "note's R5)",
        }
        written[name] = str(
            write_probe(out / name, "closed_world", arrays, descriptor, (path, data))
        )
    _json(
        out / "closed_world.json",
        {"format": PROBE_FORMAT, "role": "closed_world", "worlds": written},
    )
    return out


def partition_probe(inputs, out):
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import runner

    path = Path(inputs) / "partition_probe_inputs.json"
    registered = json.loads(path.read_text())
    parent = np.asarray(registered["parent"], dtype=np.int64)
    count, size, splits = len(parent), int(parent.sum()), int(registered["splits"])
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    rules = {}
    for rule in registered["rules"]:
        name = rule["partition"]
        value = rule.get("fraction", rule.get("p"))
        key = "fraction" if name == "exact_fraction" else "probability"
        world = probe_world(
            count, [1.0] * count, [1.0] * count, [1.0 / count] * count, np.zeros((count, count))
        )
        world.pop("law_data")
        world["fission"] = {
            "operator": world["fission"]["operator"],
            "size": size,
            "partition": {"rule": name, key: value},
        }
        data = probe_definition(world, None)
        data["experiment"]["uniforms"] = True
        spec = parse_spec(data)
        result = runner.fission_pass(spec, np.tile(parent, (splits, 1)), range(splits))
        arrays = {
            "first": result["first"],
            "second": parent[None, :] - result["first"],
            "partition_uniforms": result["partition_uniforms"],
            "parent": parent,
        }
        rules[name] = str(
            write_probe(
                out / name,
                "partition_probe",
                arrays,
                {
                    "rule": {"partition": name, key: value},
                    "definition": spec.to_dict(),
                    "lineage_words": [0, splits - 1],
                    "says": {
                        "first [split, type]": "the first daughter's counts of each split",
                        "second [split, type]": "the parent less the first",
                        "partition_uniforms [split, place]": "the partition stream's uniform "
                        "for each molecule place (places by type in declared order)",
                    },
                    "how": "the engine's compiled fission pass on lanes holding the registered "
                    "parent with its fission due, split k keyed as the founder 0:0 of lineage "
                    "word k (runner.fission_pass)",
                },
            )
        )
    shutil.copyfile(path, out / path.name)
    _json(
        out / "partition_probe.json",
        {
            "format": PROBE_FORMAT,
            "role": "partition_probe",
            "rules": rules,
            "inputs": {"file": path.name, "sha256": _sha256(path)},
        },
    )
    return out


def observer_probe(inputs, out):
    import jax
    import jax.numpy as jnp

    from cells.models.assembly_lineages import kernel
    from validation.assembly_lineages import inheritance

    path = Path(inputs) / "observer_probe_inputs.npz"
    data = _load(path)
    parents = jnp.asarray(data["probe_parent"].astype(np.int64))
    daughters = jnp.asarray(data["probe_daughter"].astype(np.int64))
    similarity = np.asarray(jax.jit(jax.vmap(kernel.cosine))(parents, daughters))
    marks = [
        inheritance.inherited(p, d)
        for p, d in zip(data["probe_parent"], data["probe_daughter"], strict=True)
    ]
    if any(m is None for m in marks):
        raise ValueError("An observer pair holds an empty vector: no boundary")
    return write_probe(
        out,
        "observer_probe",
        {"similarity": similarity, "inherited": np.asarray(marks, dtype=bool)},
        {
            "says": {
                "similarity [pair]": "the kernel's H: integer dot products, then a correctly "
                "rounded square root and division (kernel.cosine), as fission_similarity is "
                "computed; NaN for an empty vector. Diagnostic: inheritance is not decided from it",
                "inherited [pair]": "H > 0.9 strictly, decided in exact integer arithmetic, "
                "100 (P.D)^2 > 81 (P.P)(D.D), by validation/assembly_lineages/inheritance.py: "
                "H = 0.9 is a break",
            }
        },
        (path, data),
    )


# ------------------------------------------------------------------ lineages


def write_bundle(directory, run, provenance):
    from cells.models.assembly_lineages import records

    records.write_run(directory, run, provenance=provenance)
    return str(directory)


def lineages(out):
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import (
        GARD_PAIR_CONSISTENT,
        GARD_SINGLE_EVENT,
        checkpoints,
        runner,
    )

    out = Path(out)
    roles = {}
    lineage = parse_spec(lineage_definition(GARD_PAIR_CONSISTENT))
    single = parse_spec(lineage_definition(GARD_SINGLE_EVENT))
    diagnostic = parse_spec(lineage_definition(GARD_PAIR_CONSISTENT, uniforms=True))
    first = runner.run(lineage).check()
    roles["lineage"] = write_bundle(
        out / "lineage", first, {"operation": "probe", "role": "lineage"}
    )
    roles["lineage_single_event"] = write_bundle(
        out / "lineage_single_event", runner.run(single), {"operation": "probe"}
    )
    diag = runner.run(diagnostic).check()
    roles["lineage_diagnostic"] = write_bundle(
        out / "lineage_diagnostic", diag, {"operation": "probe"}
    )
    roles["replay"] = write_bundle(out / "replay", runner.run(lineage), {"operation": "probe"})
    others = [parse_spec(lineage_definition(GARD_PAIR_CONSISTENT, lineage=w)) for w in (1, 2, 3)]
    batch = runner.run_lanes([lineage, *others])
    batched = out / "batched"
    batched.mkdir()
    members = {}
    for i, run in enumerate(batch):
        members[f"lane{i}"] = write_bundle(
            batched / f"lane{i}", run, {"operation": "probe", "lane": i}
        )
    _json(
        batched / "batched.json",
        {
            "format": PROBE_FORMAT,
            "role": "batched",
            "lanes": members,
            "lineage": "lane0: the lineage role's definition, as lane 0 of 4",
        },
    )
    roles["batched"] = str(batched)
    # Restart: mid-growth (halfway through growth 2) and across a pending fission (fission 3).
    rows = diag.rows
    parents = rows["row_event"][rows["row_kind"] == 1]
    stops = {
        "mid_growth": int((parents[0] + parents[1]) // 2),
        "across_fission": int(parents[2]),
    }
    restart = out / "restart"
    restart.mkdir()
    cases = {}
    for name, stop in stops.items():
        stopped = runner.run(diagnostic, stop=stop)
        state = stopped.checkpoint()
        case = restart / name
        case.mkdir()
        checkpoints.write(case / "checkpoint", state)
        continued = runner.run(diagnostic, start=state)
        cases[name] = {
            "stop_event": stop,
            "checkpoint_status": int(state.lane["status"]),
            "stopped": write_bundle(case / "stopped", stopped, {"operation": "probe"}),
            "checkpoint": str(case / "checkpoint"),
            "continued": write_bundle(case / "continued", continued, {"operation": "probe"}),
        }
    _json(
        restart / "restart.json",
        {
            "format": PROBE_FORMAT,
            "role": "restart",
            "of": "lineage_diagnostic",
            "cases": cases,
            "uninterrupted": roles["lineage_diagnostic"],
        },
    )
    roles["restart"] = str(restart)
    # Branches: the post-fission landmark at fission 20, then 8 branch words.
    branches = out / "branches"
    branches.mkdir()
    landmark_spec = parse_spec(
        lineage_definition(GARD_PAIR_CONSISTENT, fissions=BRANCH_LANDMARK, uniforms=True)
    )
    landmark = runner.run(landmark_spec).check()
    state = landmark.checkpoint()
    checkpoints.write(branches / "checkpoint", state)
    futures = {}
    for word in BRANCH_WORDS:
        spec = parse_spec(
            lineage_definition(
                GARD_PAIR_CONSISTENT,
                fissions=BRANCH_LANDMARK + BRANCH_FISSIONS,
                uniforms=True,
                branch=word,
            )
        )
        futures[str(word)] = write_bundle(
            branches / f"branch{word}", runner.run(spec, start=state), {"operation": "probe"}
        )
    _json(
        branches / "branches.json",
        {
            "format": PROBE_FORMAT,
            "role": "branches",
            "landmark": write_bundle(branches / "landmark", landmark, {"operation": "probe"}),
            "checkpoint": str(branches / "checkpoint"),
            "branch_words": list(BRANCH_WORDS),
            "branches": futures,
            "fissions_each": BRANCH_FISSIONS,
            "mode": "diagnostic: every draw's uniforms saved",
        },
    )
    roles["branches"] = str(branches)
    return roles


def ensemble_world():
    """The registered beta = 0 ensemble's world (ENSEMBLE_DESIGN), exchange alone."""
    from cells.models.assembly_lineages import CONTINUATION, EXCHANGE_LAW, FISSION

    d = ENSEMBLE_DESIGN
    return {
        "types": {
            "prefix": "t",
            "count": d["types"],
            "transfer_constant": d["k_join"] / d["k_leave"],
        },
        "supply": list(d["rho"]),
        "exchange": {"law": EXCHANGE_LAW, "leave_rate": d["k_leave"]},
        "founder": list(d["founder"]),
        "fission": {
            "operator": FISSION,
            "size": ENSEMBLE_FISSION_SIZE,
            "partition": {"rule": "exact_fraction", "fraction": 0.5},
        },
        "continuation": {
            "operator": CONTINUATION,
            "daughter": "first",
            "empty": "extinct",
            "sink": "discard",
        },
        "units": {"time": "nominal", "temperature_K": None},
    }


def registered_design(inputs):
    """The registered beta = 0 ensemble design, read from the inputs' design file and checked
    value by value against ENSEMBLE_DESIGN: (path, the file's values)."""
    names = json.loads((Path(inputs) / "inputs.json").read_text())
    path = Path(inputs) / names["beta0_ensemble"]
    design = json.loads(path.read_text())
    d = ENSEMBLE_DESIGN
    types = d["types"]
    expected = {
        "types": types,
        "k_join": [d["k_join"]] * types,
        "k_leave": [d["k_leave"]] * types,
        "transfer_constant": [d["k_join"] / d["k_leave"]] * types,
        "rho": list(d["rho"]),
        "founder": list(d["founder"]),
        "observation_time": d["t_end"],
        "runs": d["runs"],
    }
    differs = {k: (design.get(k), v) for k, v in expected.items() if design.get(k) != v}
    if differs:
        raise ValueError(f"The registered design differs from the driver's constants: {differs}")
    return path, design


def beta0_ensemble(inputs, out):
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import runner
    from validation.assembly_lineages import worlds

    out = Path(out)
    out.mkdir()
    design_path, design = registered_design(inputs)
    shutil.copyfile(design_path, out / design_path.name)
    runs, t_end = design["runs"], design["observation_time"]
    specs = []
    for w in range(runs):
        data = worlds.definition(ensemble_world(), None, fissions=1, seed=STREAM_SEED, lineage=w)
        data["experiment"]["growth_event_limit"] = ENSEMBLE_GUARD
        specs.append(parse_spec(data))
    members, stopped = {}, {}
    for start in range(0, runs, 50):
        batch = specs[start : start + 50]
        for i, run in zip(range(start, start + len(batch)), runner.run_lanes(batch), strict=True):
            members[str(i)] = write_bundle(out / f"w{i:03d}", run, {"operation": "probe"})
            stopped[str(i)] = bool(run.rows["row_time"][-1] <= t_end)
    if any(stopped.values()):
        raise RuntimeError("A lineage of the ensemble stopped before t_end")
    _json(
        out / "beta0_ensemble.json",
        {
            "format": PROBE_FORMAT,
            "role": "beta0_ensemble",
            "members": members,
            "lineage_words": [0, runs - 1],
            "design": {
                "file": design_path.name,
                "sha256": _sha256(design_path),
                "equals_the_driver_constants": True,
                "observation_times": design["observation_times"],
                "runs": runs,
                "observation_time": t_end,
            },
            "law": "the exchange law alone (no rate factor: beta = 0); transfer constant "
            "K = k_join / k_leave, leave constant k_leave",
            "horizon": f"each lineage to its first fission at size {ENSEMBLE_FISSION_SIZE} "
            f"(world.json fission.size), under an event guard of {ENSEMBLE_GUARD} "
            "(resolved_config.json experiment.growth_event_limit): every trace extends past "
            f"t_end = {t_end}, and each run.json's end.time is later than it",
            "stopped_before_t_end": stopped,
            "ends": "by design every run ends at the event guard (status event_limit, its life "
            "censored by event_limit, near t = 8), before it could reach the fission size: an "
            "honest record of why it ended, not a failure; the design reads only t <= t_end",
        },
    )
    return str(out)


def rescale(out):
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import GARD_PAIR_CONSISTENT, runner

    out = Path(out)
    roles = {}
    for role, value in (("rescale_beta0", 0.0), ("rescale_betac", RESCALE_C)):
        data = lineage_definition(GARD_PAIR_CONSISTENT, fissions=RESCALE_FISSIONS, uniforms=True)
        world = data["model"]["world"]
        world["law_data"] = {"catalysis_matrix": np.full((100, 100), value).tolist()}
        run = runner.run(parse_spec(data)).check()
        roles[role] = write_bundle(out / role, run, {"operation": "probe", "uniform_beta": value})
    return roles


FORMAT_STATEMENT = """# The engine's output format for G2's roles (cells.model.assembly_lineages@1)

Frozen with the relationship keys (D202). Every file is described by the files themselves; this
page says where to look. Nothing here needs the engine's code.

## A run bundle (lineage roles)
A directory with world.json, run.json, records.npz, relations.npz, relations.json,
resolved_config.json, summary.json and manifest.json (every file's SHA-256, written last).
- relations.npz and relations.json (cells.relations@1): the run's relationship tables, read with
  that format's reader: the lives, the fission and extinction events, the slot, the reservoir and
  the unmodelled agent as sources, and the material edges (supplies and leaves weighed by the
  bundle's own cumulative records; each unfollowed daughter's discards with its own counts on
  the edge).
- world.json (cells.assembly_lineages.world@1): {format, id, world, derived}. `world` is the world
  as its definitions state it: types {prefix, count, transfer_constant}, supply (rho), exchange
  {law, leave_rate}, law_data {catalysis_matrix} (absent without catalysis), founder (a count per
  type), fission {operator, size, partition {rule, fraction | probability}}, continuation
  {operator, daughter, empty, sink}, units {time, temperature_K}. `derived` holds the type ids,
  standard_transfer_mu_RT, join_rate (k_join = K k_leave), leave_rate and founder_size. `id` is the
  SHA-256 of the world's canonical JSON; run.json's `world` names it.
- run.json (cells.assembly_lineages.run@1): format, world (the world record's id), founder, model,
  engine_models, definition_sha256, run {qualifier, start}, keys (the key rule), lives (the lives'
  vocabulary), law (id, form, energy_role, formulas, provenance, interface, check, world_report,
  exchange {id, energy_role, formulas, provenance, interface}), mode, stream (generator, seed,
  environment, lineage, branch, fold_order, domains, reserved_domains, uniform), ssa (the direct
  method's convention), ledger (conventions and closure), operators {fission, continuation},
  lifecycle, source (the engine's revision), end, time {unit, temperature_K, rates, bases},
  channels (the declared channel table: rows in the kernel's order and event_channel's meaning),
  layers, records (every array: file, array, base, axes, unit, kind, layer, owner, and what it
  says), diagnostics; and bound in every-descendant mode.
- records.npz: the arrays run.json's `records` declares, by name; loads with allow_pickle=False.
  Bases: row, fission, event, growth, life (run.json time.bases says what each row is).

## A probe (kernel_probe, closed_world/<world>, partition_probe/<rule>, observer_probe)
probe.json (cells.assembly_lineages.probe@1): format, role, source, inputs {file, sha256, arrays},
arrays_sha256 (the SHA-256 of the bytes of probe.npz beside it, as written), the engine
definitions used, and
`says`: what each array of probe.npz is. probe.npz holds the outputs and the registered inputs
unmodified, prefixed input_. Arrays of both forms are named <form>.<array>, form pair_consistent
or single_event. observer_probe's `inherited` holds each pair's mark, H > 0.9 strictly, decided in
exact integers (H = 0.9 is a break); its `similarity` is the kernel's floating-point H, diagnostic.

## Where a reader finds what the probes do not repeat
- A form's detailed-balance verdict is its lineage run's `law.check.admitted_as` in run.json
  (`passive` for the pair-consistent form in `lineage`; `driven` for the single-event form in
  `lineage_single_event`), with the check's probe in `law.check.probe`.
- A run without a rate-factor law has `law.id` and `law.form` null in run.json (form "none").
- The event guard of a run is resolved_config.json's `experiment.growth_event_limit`.
- A form's factor formulas, the last molecule's leave included, are run.json's `law.formulas`.

## The beta0_ensemble role
Its values are read from the registered design file named in the inputs' inputs.json
(beta0_ensemble_design.json, copied into the role's folder; beta0_ensemble.json gives its SHA-256)
and checked against the driver's own: 500 runs, one stream each (lineage words 0..499). Every run
ends at the event guard by design (status event_limit, its life censored by event_limit, near
t = 8), before it could reach the fission size: not a failure. The design reads only t <= 2, and
beta0_ensemble.json's stopped_before_t_end shows that no run stopped earlier. Each run's fission
size is world.json's world.fission.size (2048) and its event guard resolved_config.json's
experiment.growth_event_limit (4096).

## Groups
batched/batched.json, restart/restart.json, branches/branches.json, beta0_ensemble/
beta0_ensemble.json, closed_world/closed_world.json and partition_probe/partition_probe.json list
their members' paths. A checkpoint directory holds checkpoint.json
(cells.assembly_lineages.checkpoint@1) and lane.npz.

## f12_table
f12_table.npz (sequences [4096, 12] int8, f12 [4096] bool, certified_at [4096] int64) and
f12_table.json (cells.assembly_lineages.f12_table@1): the encoding and the declared parameters.
"""


def run(inputs, out):
    import cells
    from validation.assembly_lineages import inheritance

    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "FORMAT.md").write_text(FORMAT_STATEMENT)
    roles = {}
    roles |= lineages(out)
    roles["beta0_ensemble"] = beta0_ensemble(inputs, out / "beta0_ensemble")
    roles |= rescale(out)
    roles["kernel_probe"] = str(kernel_probe(inputs, out / "kernel_probe"))
    roles["closed_world"] = str(closed_world(inputs, out / "closed_world"))
    roles["partition_probe"] = str(partition_probe(inputs, out / "partition_probe"))
    roles["observer_probe"] = str(observer_probe(inputs, out / "observer_probe"))
    inheritance.write_table(out / "f12_table")
    roles["f12_table"] = str(out / "f12_table")
    _json(
        out / "roles.json",
        {
            "format": "cells.assembly_lineages.probe_roles@1",
            "roles": roles,
            "inputs": {
                "directory": str(Path(inputs).resolve()),
                "files": {
                    p.name: _sha256(p) for p in sorted(Path(inputs).iterdir()) if p.is_file()
                },
            },
            "source": _source(),
            "cells": cells.__file__,
            "settings": {
                "matrix_seed": MATRIX_SEED,
                "founder_seed": FOUNDER_SEED,
                "stream_seed": STREAM_SEED,
                "fissions": FISSIONS,
                "branch_landmark": BRANCH_LANDMARK,
                "branch_words": list(BRANCH_WORDS),
                "branch_fissions": BRANCH_FISSIONS,
                "beta0_ensemble": {
                    k: list(v) if isinstance(v, tuple) else v for k, v in ENSEMBLE_DESIGN.items()
                },
                "rescale_c": RESCALE_C,
                "rescale_fissions": RESCALE_FISSIONS,
                "approved": "the lead, 17 November 2026",
            },
        },
    )
    print(json.dumps({"roles": len(roles), "out": str(out)}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze")
    frozen.add_argument("out", type=Path)
    running = commands.add_parser("run")
    running.add_argument("inputs", type=Path)
    running.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        freeze(args.out)
    else:
        run(args.inputs, args.out)


if __name__ == "__main__":
    main()
