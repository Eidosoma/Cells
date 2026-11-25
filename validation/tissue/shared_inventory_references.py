"""FR-43 part 2 (D315): the shared inventories judged against their code-blind references.

The references are validation/fr43_part2/references (the references agent's, written from the
equations and the declared worlds only). The criteria were fixed before any reference existed:
the specification's CRITERIA.md (23 November 2026, kept with the run inputs). This module applies
them as written, and records every number against its floor and its band.

C2.3, one pool with two writers at fixed volume, for each kind (sink: N + X -> W; source: X -> N):
- the engine runs the kind's world at its declared dt and at dt/2 (the -dt0p5 and -dt0p25 files);
- at the sample times t_i, e_q(h) = max_i |q_engine,h(t_i) - q_ref(t_i)| / max_i |q_ref(t_i)|;
- for q in {n_N, the gene unit's net books of N (produced minus consumed), the network's net books
  of N, the network's route rate}: pass if 3.6 <= e_q(dt) / e_q(dt/2) <= 4.4. Where
  e_q(dt) < 1e-8 the ratio is not judged, and q passes if e_q(dt/2) < 1e-8;
- the plant (must fail): against the planted reference (the network's k x 1.01), the ratio for
  n_N and for the network's books falls below 3.6.

C2.6 and C2.7, a passive reaction in a swelling cell (the C2.6 worlds at dt = 0.01 s and 0.005 s,
sampled at t = 0, 0.5, ..., 40 s):
- C2.6, for q in {n_A, n_B, n_C, V}: the ratio criterion above;
- C2.7, the engine's own books: F(N_t, V_t) + U(V_t) - F(N_0, V_0) - U(V_0) equals the booked work
  (the network's and the bath's water work) less the booked heat (the network's and water's). F is
  computed from the engine's amounts and volume (READOUTS.md's rule as amended); U = 0 (no
  modulus). The residual over the energy scale (the largest |dF| + |heat| + |work|), at every
  saved row, shrinks at second order: its ratio between dt and dt/2 lies in [3.6, 4.4];
- C2.7 against the reference, for q in {F, water's heat, the bath's water work, the network's
  heat}: the ratio criterion above;
- the plant (must fail): the network reads the declared volume V_0 for both its rates and its
  bookings. The engine's energy ledger refuses that run, or else its residual is at least 100 times
  the correct run's.

C2.8, both writers in a swelling cell (the C2.8 worlds at dt = 0.01 s and 0.005 s, sampled at
t = 0, 1, ..., 40 s):
- for q in {n_N, n_X, n_W, V, each writer's net books of N, each writer's net rate of N, F}: the
  ratio criterion above. The network's rate is its route's (an observation) times N's coefficient;
  the gene unit's is its own flux law at the engine's saved state, controls and current volume;
- the plants (must fail), one writer at a time: that writer reads the declared volume V_0 in place
  of the current one. For n_N or that writer's books, its e_q(dt/2) is at least 10 times the
  correct run's e_q(dt/2), and its ratio is below 3.6: the miss shows in amounts.

Usage (from a frozen snapshot's root): python -m validation.tissue.shared_inventory_references
{c23,c26,c28} OUT_DIR. It writes OUT_DIR/<case>.json and exits 0 when every criterion holds, else 1.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from validation import id_table

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "fr43_part2" / "references"
FLOOR = 1e-8  # Below it, e_q(dt) is too close to the reference's own accuracy for a ratio.
BAND = (3.6, 4.4)  # Strang over order-3 half-steps: e(dt) / e(dt/2) = 4 to leading order.
C23_KINDS = ("sink", "source")
C23_QUANTITIES = ("n_N", "gene_books_N", "network_books_N", "route_rate")
C23_PLANTED = ("n_N", "network_books_N")  # The planted reference must fail these by the ratio.
C26_WORLDS = ("C2.6-swelling-cell-dt0p01.json", "C2.6-swelling-cell-dt0p005.json")
C26_QUANTITIES = ("n_A", "n_B", "n_C", "V")
C27_QUANTITIES = ("F", "water_heat", "bath_water_work", "network_heat")
PLANT_RESIDUE_FACTOR = 100.0  # C2.7's plant, if the ledger admits it: residual >= 100 x correct.
C28_WORLDS = ("C2.8-swelling-pair-sink-dt0p01.json", "C2.8-swelling-pair-sink-dt0p005.json")
C28_QUANTITIES = (
    "n_N",
    "n_X",
    "n_W",
    "V",
    "gene_books_N",
    "network_books_N",
    "gene_rate_N",
    "network_rate_N",
    "F",
)
C28_PLANT_FACTOR = 10.0  # A plant's e(dt/2) against the correct run's.
C28_PLANTS = {  # writer: (module, class, its books)
    "gene_unit": (
        "cells.operators.templated_polymerisation",
        "TemplatedPolymerisation",
        "gene_books_N",
    ),
    "network": ("cells.operators.species_reactions", "LocalSpeciesReactions", "network_books_N"),
}
NETWORK = "local_species_reactions@1"


def reference(case):
    """(times [T] s, {quantity: [T]}) from out/<case>.json, in the engine's terms."""
    data = json.loads((REFERENCES / "out" / f"{case}.json").read_text())

    def get(name):
        return np.asarray(data[name], dtype=float)

    return get("times_s"), dict(
        n_N=get("amount_fmol.N"),
        gene_books_N=get("gene_produced_N_fmol") - get("gene_consumed_N_fmol"),
        network_books_N=get("network_produced_N_fmol") - get("network_consumed_N_fmol"),
        route_rate=get("network_route_rate_fmol_per_s"),
    )


def engine(world):
    """(times [T] s, {quantity: [T]}, seconds) of the engine's run of worlds/<world>, every host
    check on every accepted row, at the world's observation times: N's amount in the cell, each
    writer's net books of N (the history's rows at those times), and the network's one route's rate
    (its observations, one row per observation time)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run
    from cells.registry.models import get_model

    raw = id_table.load(REFERENCES / "worlds" / world)
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    seconds = time.perf_counter() - started
    _, p = get_model(spec.model).initial_values(spec)
    row = list(spec.model.species_ids).index("N")
    h = result.history
    samples = np.asarray(spec.experiment.observation_times, dtype=float)
    times = np.asarray(result.times, dtype=float)
    rows = [int(np.argmin(np.abs(times - t))) for t in samples]
    assert np.allclose(times[rows], samples, rtol=0, atol=1e-9), (world, times[rows].tolist())

    def net(produced, consumed):
        return (
            np.asarray(getattr(h, produced))[rows, row, 0]
            - np.asarray(getattr(h, consumed))[rows, row, 0]
        )

    rate = np.asarray(result.observations.reaction_rate_fmol_per_s, dtype=float)
    assert rate.shape == (len(samples), 1), ("one route, one row per observation time", rate.shape)
    increment = np.asarray(h.amount_increment)[rows, row, 0]
    return (
        samples,
        dict(
            n_N=np.asarray(p.amount_reference)[row, 0] + increment,
            gene_books_N=net("poly_produced_fmol", "poly_consumed_fmol"),
            network_books_N=net("reaction_produced_fmol", "reaction_consumed_fmol"),
            route_rate=rate[:, 0],
        ),
        seconds,
    )


def free_energy(raw, ids, n, v):
    """READOUTS.md's F (as amended on 23 November 2026), pJ per row: the sum over the cell's species
    rows of RT n_s (ln(n_s / V) - 1) + RT lambda_s n_s, with lambda_s = mu°_s/RT - ln c0 from the
    species registry where it declares the row, else from the network at its own c0, else 0."""
    from cells.laws.electrochemistry import R

    model = raw["model"]
    rt = 1e-3 * R * model["temperature_K"]  # pJ/fmol.
    registry = {s["id"]: s.get("standard_mu_RT") for s in model["species"]}
    network = next(o for o in model["operators"] if o["law"] == NETWORK)
    own = {s["id"]: s["standard_mu_RT"] for s in network["species"]}
    lam = np.zeros(len(ids))
    for i, s in enumerate(ids):
        if registry.get(s) is not None:
            lam[i] = registry[s] - math.log(model["standard_concentration_mM"])
        elif s in own:
            lam[i] = own[s] - math.log(network["standard_concentration_mM"])
    return np.sum(rt * n * (np.log(n / v[:, None]) - 1.0) + rt * lam[None, :] * n, axis=1)


def engine_c26(world):
    """(samples [T] s, {quantity: [T]}, the identity's residual over its scale at every saved row,
    seconds) of the engine's run of worlds/<world>, every host check on every accepted row."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run
    from cells.registry.models import get_model

    raw = id_table.load(REFERENCES / "worlds" / world)
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    seconds = time.perf_counter() - started
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    h = result.history
    n = np.asarray(p.amount_reference)[:, 0][None, :] + np.asarray(h.amount_increment)[:, :, 0]
    v = np.asarray(p.volume)[0] + np.asarray(h.volume_increment_pL)[:, 0]
    f = free_energy(raw, ids, n, v)
    water_heat = np.asarray(h.water_dissipated_energy_pJ).sum(axis=1)
    bath_work = np.asarray(h.bath_water_work_pJ).sum(axis=1)
    network_heat = np.asarray(h.reaction_dissipated_energy_pJ)[:, 0]
    network_work = np.asarray(h.reaction_work_pJ)[:, 0]
    work, heat = network_work + bath_work, network_heat + water_heat
    residual = (f - f[0]) - (work - heat)  # U = 0: no modulus is declared.
    scale = float(np.max(np.abs(f - f[0])) + np.max(np.abs(heat)) + np.max(np.abs(work)))
    identity = dict(
        residual_over_scale=float(np.max(np.abs(residual))) / scale,
        endpoint_residual_over_scale=float(abs(residual[-1])) / scale,
        scale_pJ=scale,
    )
    samples = np.asarray(spec.experiment.observation_times, dtype=float)
    times = np.asarray(result.times, dtype=float)
    rows = [int(np.argmin(np.abs(times - t))) for t in samples]
    assert np.allclose(times[rows], samples, rtol=0, atol=1e-9), (world, times[rows].tolist())

    def at(name):
        return n[rows, ids.index(name)]

    values = dict(
        n_A=at("A"),
        n_B=at("B"),
        n_C=at("C"),
        V=v[rows],
        F=f[rows],
        water_heat=water_heat[rows],
        bath_water_work=bath_work[rows],
        network_heat=network_heat[rows],
        network_work=network_work[rows],
    )
    return samples, values, identity, seconds


def planted_c26(world):
    """C2.7's plant: the network reads the declared volume V_0 (no view), for its rates and its
    bookings alike. (refused by the energy ledger, message, its identity or None)."""
    import jax

    from cells.execution.errors import NumericalError
    from cells.operators import species_reactions as sr

    original = sr.LocalSpeciesReactions.half_step

    def planted(self, *args, view=None, **kwargs):
        return original(self, *args, **kwargs)

    jax.clear_caches()  # The runner's compiled rollout is cached per model: retrace the plant.
    sr.LocalSpeciesReactions.half_step = planted
    try:
        try:
            _, _, identity, _ = engine_c26(world)
        except NumericalError as refusal:
            return "energy" in str(refusal), str(refusal)[:400], None
        return False, None, identity
    finally:
        sr.LocalSpeciesReactions.half_step = original
        jax.clear_caches()


def reference_c26():
    data = json.loads((REFERENCES / "out" / "C2.6-swelling-cell.json").read_text())

    def get(name):
        return np.asarray(data[name], dtype=float)

    return get("times_s"), dict(
        n_A=get("amount_fmol.A"),
        n_B=get("amount_fmol.B"),
        n_C=get("amount_fmol.C"),
        V=get("volume_pL"),
        F=get("free_energy_pJ"),
        water_heat=get("water_heat_pJ"),
        bath_water_work=get("bath_water_work_pJ"),
        network_heat=get("network_heat_pJ"),
        network_work=get("network_work_pJ"),
        U=get("elastic_energy_pJ"),
    )


def judge_c26():
    """C2.6 and C2.7's verdict, every number recorded."""
    t_ref, ref = reference_c26()
    runs, identities = {}, {}
    for label, world in zip(("dt", "half_dt"), C26_WORLDS, strict=True):
        samples, values, identity, seconds = engine_c26(world)
        assert samples.shape == t_ref.shape and np.allclose(samples, t_ref, rtol=0, atol=1e-9)
        runs[label] = dict(world=world, values=values, seconds=seconds)
        identities[label] = identity
    dt, half = runs["dt"]["values"], runs["half_dt"]["values"]
    c26 = {q: ratio_verdict(error(dt[q], ref[q]), error(half[q], ref[q])) for q in C26_QUANTITIES}
    c27_reference = {
        q: ratio_verdict(error(dt[q], ref[q]), error(half[q], ref[q])) for q in C27_QUANTITIES
    }
    coarse = identities["dt"]["residual_over_scale"]
    fine = identities["half_dt"]["residual_over_scale"]
    ratio = coarse / fine if fine > 0 else float("inf")
    c27_identity = dict(
        identities,
        ratio=ratio,
        passed=BAND[0] <= ratio <= BAND[1],
        network_work_max_pJ=float(
            max(np.max(np.abs(dt["network_work"])), np.max(np.abs(half["network_work"])))
        ),
        reference_U_max_pJ=float(np.max(np.abs(ref["U"]))),
    )
    refused, message, planted_identity = planted_c26(C26_WORLDS[0])
    if refused:
        plant = dict(refused_by_the_energy_ledger=True, message=message, fails_as_required=True)
    else:
        over = (planted_identity or {}).get("residual_over_scale", 0.0) / coarse if coarse else 0.0
        plant = dict(
            refused_by_the_energy_ledger=False,
            message=message,
            identity=planted_identity,
            residual_over_correct=over,
            fails_as_required=over >= PLANT_RESIDUE_FACTOR,
        )
    passed = (
        all(v["passed"] for v in c26.values())
        and all(v["passed"] for v in c27_reference.values())
        and c27_identity["passed"]
        and plant["fails_as_required"]
    )
    return dict(
        case="C2.6 and C2.7",
        floor=FLOOR,
        band=list(BAND),
        runs={k: dict(world=v["world"], seconds=round(v["seconds"], 2)) for k, v in runs.items()},
        c26=c26,
        c27_identity=c27_identity,
        c27_reference=c27_reference,
        plant=plant,
        passed=passed,
    )


def gene_rate_N(raw, spec, p, n, free, complexes, volume, times):
    """The gene unit's net rate of N (fmol/s) at each saved state: its own flux law (fluxes and
    changes) at the engine's amounts, machines and complexes, its scheduled controls at each time,
    and the cell's current volume."""
    from cells.operators import templated_polymerisation as tp

    ids = list(spec.model.species_ids)
    rows = [int(r) for r in np.asarray(p.poly_rows)]
    at_n = rows.index(ids.index("N"))
    op = next(o for o in raw["model"]["operators"] if o["law"] == tp.LAW_ID)
    schedules = {c["route_id"]: c["schedule"] for c in raw["experiment"]["polymerisation_controls"]}

    def value(route, t):
        return [e for e in schedules[route] if e["time"] <= t][-1]["value"]

    out = []
    for i, t in enumerate(times):
        controls = tuple(
            np.array([value(item["id"], t) for item in op[key]])
            for key in ("chains", "degradations", "transfers")
        )
        routes, _ = tp.fluxes(
            n[i][rows][:, None], free[i], complexes[i], controls, p, np.asarray([volume[i]]), xp=np
        )
        out.append(float(tp.changes(*routes[:4], p, xp=np)[0][at_n, 0]))
    return np.asarray(out)


def engine_c28(world, edit=None):
    """(samples [T] s, {quantity: [T]}, seconds) of the engine's run of worlds/<world>, every host
    check on every accepted row, at the observation times. edit: None, or a function that changes
    the raw world in place before it is parsed (a test's shorter horizon)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.runner import run
    from cells.registry.models import get_model

    raw = id_table.load(REFERENCES / "worlds" / world)
    if edit is not None:
        edit(raw)
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = run(spec)
    seconds = time.perf_counter() - started
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    h = result.history
    samples = np.asarray(spec.experiment.observation_times, dtype=float)
    times = np.asarray(result.times, dtype=float)
    rows = [int(np.argmin(np.abs(times - t))) for t in samples]
    assert np.allclose(times[rows], samples, rtol=0, atol=1e-9), (world, times[rows].tolist())
    n = np.asarray(p.amount_reference)[:, 0][None, :] + np.asarray(h.amount_increment)[rows, :, 0]
    v = np.asarray(p.volume)[0] + np.asarray(h.volume_increment_pL)[rows, 0]
    i_n = ids.index("N")

    def net(produced, consumed):
        return (
            np.asarray(getattr(h, produced))[rows, i_n, 0]
            - np.asarray(getattr(h, consumed))[rows, i_n, 0]
        )

    network = next(o for o in raw["model"]["operators"] if o["law"] == NETWORK)
    (route,) = network["reactions"]
    nu_n = route["products"].get("N", 0) - route["reactants"].get("N", 0)
    rate = np.asarray(result.observations.reaction_rate_fmol_per_s, dtype=float)
    assert rate.shape == (len(samples), 1), ("one route, one row per observation time", rate.shape)
    free = np.asarray(h.poly_free_machines_fmol)[rows]
    complexes = np.asarray(h.poly_complexes_fmol)[rows]
    values = dict(
        n_N=n[:, i_n],
        n_X=n[:, ids.index("X")],
        n_W=n[:, ids.index("W")],
        V=v,
        gene_books_N=net("poly_produced_fmol", "poly_consumed_fmol"),
        network_books_N=net("reaction_produced_fmol", "reaction_consumed_fmol"),
        gene_rate_N=gene_rate_N(raw, spec, p, n, free, complexes, v, samples),
        network_rate_N=nu_n * rate[:, 0],
        F=free_energy(raw, ids, n, v),
    )
    return samples, values, seconds


def planted_c28(writer, world, edit=None):
    """(values or None, refusal message or None): the run with `writer` on the declared volume V_0
    (its half-step drops the view the composite passes); edit as engine_c28's."""
    import importlib

    import jax

    from cells.execution.errors import NumericalError

    module, name, _ = C28_PLANTS[writer]
    cls = getattr(importlib.import_module(module), name)
    original = cls.half_step

    def planted(self, *args, view=None, **kwargs):
        return original(self, *args, **kwargs)

    jax.clear_caches()  # The runner's compiled rollout is cached per model: retrace the plant.
    cls.half_step = planted
    try:
        try:
            return engine_c28(world, edit)[1], None
        except NumericalError as refusal:
            return None, str(refusal)[:400]
    finally:
        cls.half_step = original
        jax.clear_caches()


def reference_c28():
    data = json.loads((REFERENCES / "out" / "C2.8-swelling-pair-sink.json").read_text())

    def get(name):
        return np.asarray(data[name], dtype=float)

    return get("times_s"), dict(
        n_N=get("amount_fmol.N"),
        n_X=get("amount_fmol.X"),
        n_W=get("amount_fmol.W"),
        V=get("volume_pL"),
        gene_books_N=get("gene_produced_N_fmol") - get("gene_consumed_N_fmol"),
        network_books_N=get("network_produced_N_fmol") - get("network_consumed_N_fmol"),
        gene_rate_N=get("gene_rate_N_fmol_per_s"),
        network_rate_N=get("network_rate_N_fmol_per_s"),
        F=get("free_energy_pJ"),
    )


def judge_c28():
    """C2.8's verdict, every number recorded: the quantities by the ratio criterion, and each
    writer's plant at dt and dt/2."""
    t_ref, ref = reference_c28()
    runs = {}
    for label, world in zip(("dt", "half_dt"), C28_WORLDS, strict=True):
        samples, values, seconds = engine_c28(world)
        assert samples.shape == t_ref.shape and np.allclose(samples, t_ref, rtol=0, atol=1e-9)
        runs[label] = dict(world=world, values=values, seconds=seconds)
    dt, half = runs["dt"]["values"], runs["half_dt"]["values"]
    quantities = {
        q: ratio_verdict(error(dt[q], ref[q]), error(half[q], ref[q])) for q in C28_QUANTITIES
    }
    plants = {}
    for writer, (_, _, books) in C28_PLANTS.items():
        wrong = {
            label: planted_c28(writer, world)
            for label, world in zip(("dt", "half_dt"), C28_WORLDS, strict=True)
        }
        refusals = {label: msg for label, (_, msg) in wrong.items() if msg is not None}
        entry = dict(refused=refusals or None, quantities={})
        if not refusals:
            for q in ("n_N", books):
                e_dt = error(wrong["dt"][0][q], ref[q])
                e_half = error(wrong["half_dt"][0][q], ref[q])
                ratio = e_dt / e_half if e_half > 0 else float("inf")
                over = e_half / quantities[q]["e_half_dt"] if quantities[q]["e_half_dt"] else 0.0
                entry["quantities"][q] = dict(
                    e_dt=e_dt,
                    e_half_dt=e_half,
                    ratio=ratio,
                    over_correct_half_dt=over,
                    shows=over >= C28_PLANT_FACTOR and ratio < BAND[0],
                )
        entry["fails_as_required"] = any(v["shows"] for v in entry["quantities"].values())
        plants[writer] = entry
    passed = all(v["passed"] for v in quantities.values()) and all(
        v["fails_as_required"] for v in plants.values()
    )
    return dict(
        case="C2.8",
        floor=FLOOR,
        band=list(BAND),
        plant_factor=C28_PLANT_FACTOR,
        runs={k: dict(world=v["world"], seconds=round(v["seconds"], 2)) for k, v in runs.items()},
        quantities=quantities,
        plants=plants,
        passed=passed,
    )


def error(values, ref):
    """e_q(h): the largest departure at the sample times over the reference's largest size."""
    return float(np.max(np.abs(values - ref)) / np.max(np.abs(ref)))


def ratio_verdict(e_dt, e_half):
    """CRITERIA.md's rule for one quantity: its ratio in the band, or both errors below 1e-8."""
    ratio = e_dt / e_half if e_half > 0 else float("inf")
    judged = e_dt >= FLOOR
    passed = (BAND[0] <= ratio <= BAND[1]) if judged else e_half < FLOOR
    return dict(e_dt=e_dt, e_half_dt=e_half, ratio=ratio, ratio_judged=judged, passed=passed)


def judge_c23(kinds=C23_KINDS):
    """C2.3's verdict, every number recorded: per kind, each quantity's errors and ratio against the
    reference, and the planted reference's ratios."""
    out = dict(case="C2.3", floor=FLOOR, band=list(BAND), kinds={})
    for kind in kinds:
        t_ref, ref = reference(f"C2.3-{kind}")
        t_plant, planted = reference(f"C2.3-{kind}-planted")
        assert np.array_equal(t_ref, t_plant)
        runs = {}
        for label, world in (
            ("dt", f"C2.3-{kind}-dt0p5.json"),
            ("half_dt", f"C2.3-{kind}-dt0p25.json"),
        ):
            times, values, seconds = engine(world)
            assert times.shape == t_ref.shape and np.allclose(times, t_ref, rtol=0, atol=1e-9), (
                world,
                times.tolist(),
            )
            runs[label] = dict(world=world, values=values, seconds=seconds)
        dt, half = runs["dt"]["values"], runs["half_dt"]["values"]
        quantities = {
            q: ratio_verdict(error(dt[q], ref[q]), error(half[q], ref[q])) for q in C23_QUANTITIES
        }
        plant = {}
        for q in C23_PLANTED:
            e_dt, e_half = error(dt[q], planted[q]), error(half[q], planted[q])
            r = e_dt / e_half if e_half > 0 else float("inf")
            plant[q] = dict(e_dt=e_dt, e_half_dt=e_half, ratio=r, fails_as_required=r < BAND[0])
        out["kinds"][kind] = dict(
            runs={
                k: dict(world=v["world"], seconds=round(v["seconds"], 2)) for k, v in runs.items()
            },
            quantities=quantities,
            plant=plant,
            passed=all(v["passed"] for v in quantities.values())
            and all(v["fails_as_required"] for v in plant.values()),
        )
    out["passed"] = all(k["passed"] for k in out["kinds"].values())
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("case", choices=("c23", "c26", "c28"))
    parser.add_argument("out")
    parser.add_argument("--kinds", nargs="+", default=list(C23_KINDS), choices=C23_KINDS)
    args = parser.parse_args(argv)
    import jax

    jax.config.update("jax_enable_x64", True)
    judges = dict(c23=lambda: judge_c23(tuple(args.kinds)), c26=judge_c26, c28=judge_c28)
    verdict = judges[args.case]()
    verdict["references"] = str(REFERENCES.relative_to(ROOT))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.case}.json").write_text(json.dumps(verdict, indent=1) + "\n")
    parts = {k: v["passed"] for k, v in verdict.get("kinds", {}).items()}
    print(json.dumps(parts | dict(passed=verdict["passed"])))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
