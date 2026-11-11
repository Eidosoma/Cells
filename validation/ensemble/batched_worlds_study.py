"""Throughput of vectorized resolved-pump worlds (core/vector_windows.py) on one GPU.

Engine models: resolved_pump_tissue@1, @2 and @3, IMEX ARS(2,2,2) at dt = 1 ms
on the synthetic 825-node world of validation/tissue/resolved_scale_world.py
(225 cells, 600 outside nodes). The @2 world adds Cl and Ca with BETSE's mammal
concentrations (M rebalances charge) and a ca_atp_mass_action_positive@1 pump
on every patch, with BETSE's default Ca-ATPase coefficients. The @3 world is the
heredity tissue of validation/tissue/surface_pump_v3_study.tissue_definition:
NaV1.2 and Kir2.1 populations on every patch (2580 populations, the heredity
parameter set, Na leak x0.2). Worlds are replicas unless --heterogeneous (pump
capacity, and for @3 the channel permeabilities, spread by 0-20%); each world
still holds and processes its own parameter arrays.

Parts (one process each, so compile time and peak memory are per configuration):
  vector      compile one window for --worlds B, then time chained windows on the
              device (block_until_ready per window) with optional DCGM counters
  endtoend    run_vector_windowed over whole windows: host preparation, transfers,
              observation checks and device time, as the ensemble runner sees them
  sequential  the existing guarded lax.map path (core/batch_windows.py) with its
              per-step host checks, for comparison
  components  the window's parts timed alone: vmapped IMEX steps, device checks,
              batched dense Cholesky factorization and solve
  equivalence heterogeneous worlds (--heterogeneous implied): the vectorized batch
              against each world's own windowed run (core/windows.py) on the same
              backend; state and membrane-voltage differences
  checks      one world's accepted rows (core/runner.run): the model's device checks
              against its host check_values row for row (verdicts and diagnostics
              relative to their bounds), at the rows' own step counts and at
              hour-scale counts, and seeded faults (a channel transfer, a channel
              gate, a metabolic booking) caught at the same row by both
Usage:
  python -m validation.ensemble.batched_worlds_study PART --model 1 --worlds 64 \
      --output DIR [--window 32] [--seconds 30] [--dcgm-root DIR] [--backend gpu]
"""

import argparse
import copy
import json
import resource
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.batch import BatchSpec, WorldSpec  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.windows import WindowPolicy  # noqa: E402
from cells.numerics import surface_imex as imex  # noqa: E402
from validation.tissue import resolved_scale_world as world  # noqa: E402

# BETSE v1.5.0 defaults (parameters.py, mammal ion profile, sim_config.yaml).
CALCIUM = dict(
    cell_mM=dict(Cl=4.0, Ca=5.0e-5),
    env_mM=dict(Cl=115.0, Ca=2.0),
    free_D=dict(Cl=2.03e-9, Ca=0.79e-9),
    membrane_D=dict(Cl=1.0e-18, Ca=1.0e-18),
    alpha_ca_mol_m2_s=5.0e-8,
    km_ca_mM=1.0e-3,
    km_atp_mM=0.5,
)


def calcium_world(raw):
    """resolved_pump_tissue@2 on the same geometry: Na K P M plus Cl and Ca."""
    raw = copy.deepcopy(raw)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_pump_tissue@2"
    m["species"] += [dict(id="Cl", valence=-1), dict(id="Ca", valence=2)]
    for key, mM in (("cells", CALCIUM["cell_mM"]), ("extracellular", CALCIUM["env_mM"])):
        for owner in m[key]:
            volume = owner["volume_pL"]
            amounts = owner["initial_amount_fmol"]
            concentration = {k: v / volume for k, v in amounts.items()}
            concentration |= mM
            # Electroneutral start: M (valence -1) balances the added ions.
            concentration["M"] = (
                concentration["Na"]
                + concentration["K"]
                - concentration["P"]
                - concentration["Cl"]
                + 2 * concentration["Ca"]
            )
            owner["initial_amount_fmol"] = {k: c * volume for k, c in concentration.items()}
    for i, membrane in enumerate(m["membranes"]):
        for ion, d in CALCIUM["membrane_D"].items():
            membrane["permeability_m_per_s"][ion] = d / world.MEMBRANE_THICKNESS_m
        membrane["calcium_pump"] = dict(
            id=f"calcium_pump_{i}",
            law="ca_atp_mass_action_positive@1",
            roles=dict(calcium="Ca"),
            stoichiometry=dict(Ca=-1),
            capacity_fmol_per_s=CALCIUM["alpha_ca_mol_m2_s"] * membrane["area_m2"] * 1e15,
            km_ca_mM=CALCIUM["km_ca_mM"],
            km_atp_mM=CALCIUM["km_atp_mM"],
            metabolism=dict(membrane["pump"]["metabolism"]),
        )
    for junction in m["junctions"]:
        for ion, d in CALCIUM["free_D"].items():
            junction["permeability_m_per_s"][ion] = (
                d * world.GJ_SURFACE_FRACTION / world.GJ_LENGTH_m
            )
    for face in m["faces"]:
        face["diffusivity_m2_per_s"] |= CALCIUM["free_D"]
    e["calcium_pump_controls"] = [
        dict(pump_id=p["calcium_pump"]["id"], schedule=[dict(time=0.0, availability=1.0)])
        for p in m["membranes"]
    ]
    x["material_balance_atol_fmol"] |= dict(Cl=1e-10, Ca=1e-10)
    return raw


def definition(model, *, steps, backend, scale=1.0, observe_every=None, junction_heat=None):
    end = steps * 1e-3
    every = steps if observe_every is None else observe_every
    times = [k * every * 1e-3 for k in range(steps // every)] + [end]
    if model == 3:
        from validation.tissue import surface_pump_v3_study as heredity

        raw = heredity.tissue_definition(
            dt=1e-3, end_time=end, backend=backend, observation_times=times
        )
        for channel in raw["model"]["channels"]:
            channel["max_permeability_m_per_s"] *= scale
        if junction_heat is not None:  # @3's opt-in junction-heat booking.
            raw["model"]["junction_heat_booking"] = junction_heat
    else:
        raw = world.definition(
            dt=1e-3,
            end_time=end,
            observation_times=times,
            solver=imex.ARS222_ID,
            backend=backend,
        )
    for membrane in raw["model"]["membranes"]:
        membrane["pump"]["capacity_fmol_per_s"] *= scale
    return calcium_world(raw) if model == 2 else raw


def batch(args, steps):
    options = dict(
        steps=steps,
        backend=args.backend,
        observe_every=args.observe_every,
        junction_heat=args.junction_heat,
    )
    if args.heterogeneous:
        # A 0-20% spread of pump capacity; each world is parsed separately.
        sims = [
            parse_spec(definition(args.model, scale=1 + 0.2 * i / args.worlds, **options))
            for i in range(args.worlds)
        ]
    else:
        sims = [parse_spec(definition(args.model, **options))] * args.worlds
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(sims))
    return BatchSpec(worlds, len(worlds), 2**53 - 1, 2**53 - 1)


def write(args, name, value):
    path = Path(args.output) / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=1, allow_nan=False) + "\n")
    tmp.replace(path)


def device_memory():
    stats = jax.devices()[0].memory_stats() or {}
    return {k: stats.get(k) for k in ("peak_bytes_in_use", "bytes_in_use", "bytes_limit")}


def counters_start(args, directory):
    if not args.dcgm_root:
        return None
    from cells.ensemble.telemetry import devices
    from validation.ensemble.qualification_metrics import GpuQualificationMetrics, registration

    gpu = devices("0", 1)[0]
    metrics = GpuQualificationMetrics(
        directory, registration(Path(args.dcgm_root), gpu["uuid"], 3600)
    )
    metrics.start()
    return metrics


def setup(args, steps, report):
    """Planned cohort, validated starts and resident device inputs, timed."""
    from cells.core import vector_windows as vw
    from cells.core.devices import execution_device
    from cells.models.registry import get_model

    began = time.perf_counter()
    spec = batch(args, steps)
    report["definition_seconds"] = time.perf_counter() - began
    tick = time.perf_counter()
    plan = vw.plan_vector_windows(spec, WindowPolicy(args.window, "checkpoints"))
    report["plan_seconds"] = time.perf_counter() - tick
    tick = time.perf_counter()
    starts = vw._initial_checkpoints(plan, None)
    report["start_validation_seconds"] = time.perf_counter() - tick
    tick = time.perf_counter()
    model = get_model(spec.worlds[0].simulation.model)
    device = execution_device(args.backend)
    state, params, active, constants, _ = vw.resident_inputs(plan, starts, model, device)
    report["device_input_seconds"] = time.perf_counter() - tick
    report["memory_after_setup"] = device_memory()
    ids = [w.world_id for w in spec.worlds]
    grids = [
        plan.worlds[g[0]].grid.windows(plan.worlds[g[0]].start_step, args.window)
        for g in plan.groups
    ]
    current = vw._Round(plan, grids, starts, ids, [0] * len(ids), True)

    def arguments(round_, state):
        return (state, *jax.device_put(round_.arrays, device), params, active, constants)

    def following(round_):
        return vw._Round(plan, grids, starts, ids, round_.stops, False)

    return plan, model, state, current, arguments, following


def part_vector(args):
    from cells.core import vector_windows as vw

    label = f"vector-model{args.model}-worlds{args.worlds}"
    label += "-heterogeneous" if args.heterogeneous else ""
    label += "-junction-trapezoid" if args.junction_heat else ""
    report = dict(
        part="vector",
        model=args.model,
        worlds=args.worlds,
        window=args.window,
        heterogeneous=args.heterogeneous,
    )
    began = time.perf_counter()
    steps = args.window * (args.max_windows + 2)
    plan, model, state, current, arguments, following = setup(args, steps, report)
    executable, compile_seconds, memory = vw.compile_window(
        model, arguments(current, state), plan.observation_rows
    )
    report.update(compile_seconds=compile_seconds, compiled_memory_analysis=memory)
    write(args, label + ".json", report)
    # A warm-up window (also the first state change), then timed windows.
    windows, failures, metrics, deadline = [], None, None, None
    for k in range(args.max_windows):
        tick = time.perf_counter()
        final, first, bits, maxima, _ = executable(*arguments(current, state))
        first = np.asarray(first)  # Waits for the window; summaries only.
        seconds = time.perf_counter() - tick
        if np.any(first >= 0):
            failures = dict(window=k, first=first.tolist(), bits=np.asarray(bits).tolist())
            break
        state = final
        if k == 0:
            report["warmup_window_seconds"] = seconds
            metrics = counters_start(args, Path(args.output) / (label + "-gpu"))
            warm_time = time.time()
            deadline = time.perf_counter() + args.seconds
        else:
            windows.append(seconds)
        current = following(current)
        if deadline is not None and time.perf_counter() > deadline and len(windows) >= 3:
            break
    if metrics is not None:
        report["gpu_counters"] = metrics.finish(warm_time=warm_time)
    report["memory_after_run"] = device_memory()
    report["host_peak_rss_MiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    report["timed_window_seconds"] = windows
    report["failures"] = failures
    if windows:
        median = float(np.median(windows))
        report["ms_per_batch_step"] = 1e3 * median / args.window
        report["world_steps_per_second"] = args.worlds * args.window / median
        report["ms_per_world_step"] = 1e3 * median / (args.window * args.worlds)
    report["max_diagnostics"] = dict(
        zip(model.DEVICE_DIAGNOSTICS, np.max(np.asarray(maxima), axis=0).tolist(), strict=True)
    )
    report["total_seconds"] = time.perf_counter() - began
    write(args, label + ".json", report)


def part_components(args):
    """The window's parts at --worlds B: vmapped IMEX steps alone, device checks
    alone, and the batched dense Cholesky factorization and solve they contain."""
    import jax.numpy as jnp
    from jax.scipy.linalg import cho_solve

    label = f"components-model{args.model}-worlds{args.worlds}"
    report = dict(part="components", model=args.model, worlds=args.worlds, window=args.window)
    plan, model, state, current, arguments, _ = setup(args, args.window * 3, report)
    # Window arguments: state, then the round's steps, counts, held controls,
    # their index, observation slots and first step index; then the residents.
    _, steps, counts, table, held, _, _, params, active, constants = arguments(current, state)
    control = jax.tree.map(lambda t: t[:, 0], table)
    dt = steps[:, 0]

    @jax.jit
    def stepping(state):
        def body(y, _):
            y, _ = jax.vmap(model.checked_step)(y, dt, control, params, active)
            return y, None

        return jax.lax.scan(body, state, None, length=args.window)[0]

    zero = jnp.zeros(dt.shape[0], dtype=jnp.int64)  # Accepted-step count of each row.

    @jax.jit
    def checking(state):
        def body(total, _):
            failed, values = jax.vmap(model.device_checks)(state, state, params, constants, zero)
            return total + values.sum() + failed.sum(), None

        return jax.lax.scan(body, 0.0, None, length=args.window)[0]

    matrix = params.field_capacitor_solve_matrix
    factor = jax.jit(jax.vmap(jnp.linalg.cholesky))
    solve = jax.jit(jax.vmap(lambda f, b: cho_solve((f, True), b)))
    rhs = jnp.ones(matrix.shape[:2])
    lower = factor(matrix)

    def timed(name, fn, *inputs, per):
        tick = time.perf_counter()
        jax.block_until_ready(fn(*inputs))
        report[name + "_compile_and_first_seconds"] = time.perf_counter() - tick
        samples = []
        for _ in range(5):
            tick = time.perf_counter()
            jax.block_until_ready(fn(*inputs))
            samples.append(time.perf_counter() - tick)
        report[name + "_ms"] = 1e3 * float(np.median(samples)) / per
        write(args, label + ".json", report)

    timed("imex_step_per_batch_step", stepping, state, per=args.window)
    timed("device_checks_per_batch_row", checking, state, per=args.window)
    timed("cholesky_batch", factor, matrix, per=1)
    timed("cholesky_solve_batch", solve, lower, rhs, per=1)
    report["nodes"] = int(matrix.shape[-1])


def part_endtoend(args):
    from cells.core.vector_windows import run_vector_windowed

    label = f"endtoend-model{args.model}-worlds{args.worlds}"
    steps = args.window * args.max_windows
    spec = batch(args, steps)
    began = time.perf_counter()
    result = run_vector_windowed(spec, WindowPolicy(args.window, "checkpoints"))
    wall = time.perf_counter() - began
    t = result.timings
    report = dict(
        part="endtoend",
        model=args.model,
        worlds=args.worlds,
        window=args.window,
        steps=steps,
        wall_seconds=wall,
        timings=t,
        resources=result.resources,
        steady_ms_per_batch_step=1e3
        * (t["total_run_seconds"] - t["compile_seconds"] - t["static_preparation_seconds"])
        / steps,
        diagnostics_max={
            k: max(w.diagnostics[k] for w in result.worlds.values())
            for k in next(iter(result.worlds.values())).diagnostics
        },
        memory=device_memory(),
    )
    write(args, label + ".json", report)


def part_sequential(args):
    from cells.core.batch_windows import iter_batch_windows

    label = f"sequential-model{args.model}-worlds{args.worlds}"
    steps = args.window * args.max_windows
    spec = batch(args, steps)
    began = time.perf_counter()
    windows = []
    for window in iter_batch_windows(spec, WindowPolicy(args.window, "checkpoints")):
        windows.append(window.timings)
    report = dict(
        part="sequential",
        model=args.model,
        worlds=args.worlds,
        window=args.window,
        steps=steps,
        wall_seconds=time.perf_counter() - began,
        windows=windows,
        execute_ms_per_batch_step=1e3
        * float(np.median([w["execute_seconds"] for w in windows[1:] or windows]))
        / args.window,
        host_check_ms_per_batch_step=1e3
        * float(np.median([w["analysis_seconds"] for w in windows[1:] or windows]))
        / args.window,
        memory=device_memory(),
    )
    write(args, label + ".json", report)


def part_equivalence(args):
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import run_windowed

    args.heterogeneous = True
    label = f"equivalence-{args.backend}-model{args.model}-worlds{args.worlds}"
    steps = args.window * args.max_windows
    spec = batch(args, steps)
    policy = WindowPolicy(args.window, "checkpoints")
    seen = {w.world_id: [] for w in spec.worlds}

    def collect(window):
        for identity, found in window.observations.items():
            seen[identity].append(found)

    began = time.perf_counter()
    vector = run_vector_windowed(spec, policy, sink=collect)
    report = dict(
        part="equivalence",
        backend=args.backend,
        model=args.model,
        worlds=args.worlds,
        window=args.window,
        steps=steps,
        vector_seconds=time.perf_counter() - began,
        worlds_compared={},
    )
    for member in spec.worlds:
        own_seen = []
        tick = time.perf_counter()
        own = run_windowed(member.simulation, policy, sink=own_seen.append)
        fields = {}
        for name, a, b in zip(
            own.final.state._fields,
            vector.worlds[member.world_id].final.state,
            own.final.state,
            strict=True,
        ):
            a, b = np.asarray(a), np.asarray(b)
            scale = float(np.max(np.abs(b), initial=0.0))
            difference = float(np.max(np.abs(a - b), initial=0.0))
            fields[name] = dict(
                max_abs=difference,
                scale=scale,
                relative=difference / scale if scale else 0.0,
                bitwise=bool(np.array_equal(a, b)),
            )
        mine = np.concatenate([o.membrane_voltage_V for o in seen[member.world_id]])
        theirs = np.concatenate([w.observations.membrane_voltage_V for w in own_seen])
        report["worlds_compared"][str(member.world_id)] = dict(
            single_world_seconds=time.perf_counter() - tick,
            fields=fields,
            membrane_voltage_max_abs_V=float(np.max(np.abs(mine - theirs))),
            observations=int(len(mine)),
            bitwise=all(f["bitwise"] for f in fields.values()),
            diagnostics_vector=vector.worlds[member.world_id].diagnostics,
            diagnostics_single=own.diagnostics,
        )
        write(args, label + ".json", report)
    compared = report["worlds_compared"].values()
    report["max_membrane_voltage_abs_V"] = max(c["membrane_voltage_max_abs_V"] for c in compared)
    report["max_field_relative"] = max(
        f["relative"] for c in compared for f in c["fields"].values()
    )
    report["all_bitwise"] = all(c["bitwise"] for c in compared)
    write(args, label + ".json", report)


# Accepted steps in one hour at dt = 1 ms: the checks part's hour-scale counts.
HOUR_STEPS = 3_600_000


def seeded_fault(history, p, kind, row):
    """A copy of a history with one fault from ``row`` on, and its expected check."""
    values = {k: np.array(v, copy=True) for k, v in history._asdict().items()}
    if kind == "channel_transfer":  # 1e-6 fmol of K through population 0, unbooked.
        values["channel_transferred"][row:, 1, 0] += 1e-6
        return type(history)(**values), "local"
    if kind == "channel_gate":  # Population 0's first gate above 1.
        values["channel_gate"][row:, 0, 0] = 1.0 + 1e-9
        return type(history)(**values), "domain"
    if kind == "metabolic":  # 1e-10 pJ of Na/K pump work on patch 0, no cycles.
        values["metabolic_work_pJ"][row:, 0] += 1e-10
        return type(history)(**values), "metabolic_work"
    raise ValueError(kind)


def part_checks(args):
    """Device checks against host check_values on one world's accepted rows."""
    from cells.core.errors import NumericalError
    from cells.core.runner import run
    from cells.models import surface_pump as family
    from cells.models.registry import get_model

    label = f"checks-{args.backend}-model{args.model}"
    steps = args.window * args.max_windows
    spec = parse_spec(definition(args.model, steps=steps, backend=args.backend))
    model = get_model(spec.model)
    report = dict(part="checks", backend=args.backend, model=args.model, steps=steps)
    tick = time.perf_counter()
    value = run(spec)
    report["run_seconds"] = time.perf_counter() - tick
    history = model.STATE_TYPE(*(np.asarray(v) for v in value.history))
    rows = len(history.amount_increment)
    _, p = model.initial_values(spec)
    constants = model.device_check_constants(spec)
    device = jax.devices(args.backend)[0]
    checks = jax.jit(jax.vmap(model.device_checks, in_axes=(0, 0, None, None, 0)))
    params = jax.device_put(p, device)

    def device_rows(history, offset):
        previous = type(history)(*(np.concatenate((v[:1], v[:-1])) for v in history))
        failed, values = checks(
            jax.device_put(previous, device),
            jax.device_put(history, device),
            params,
            jax.device_put(constants, device),
            jax.device_put(offset + np.arange(rows), device),
        )
        return np.asarray(failed), np.asarray(values)

    def host_row(history, j, offset):
        row = type(history)(*(v[j : j + 1] for v in history))
        try:
            return model.check_values(row, spec, steps=[offset + j]), None
        except NumericalError as error:
            return None, str(error)

    tol = min(spec.execution.material_balance_atol_fmol)
    scales = {  # Smallest bound of each rounding residual (host bounds).
        "max_balance_error_fmol": tol,
        "max_extracellular_balance_error_fmol": tol,
        "max_global_balance_error_fmol": tol,
        "max_capacitor_charge_error_C": 3e-25,
        "max_electrode_charge_error_C": 3e-25,
        "max_global_charge_error_C": family.GLOBAL_CHARGE_ATOL_C,
        "max_reservoir_work_error_pJ": 3e-12,
        "max_electrode_work_error_pJ": 3e-12,
        "max_metabolic_work_error_pJ": 3e-12,
        "max_global_charge_bound_ratio": 1.0,
    }
    for offset in (0, HOUR_STEPS):
        tick = time.perf_counter()
        failed, values = device_rows(history, offset)
        device_seconds = time.perf_counter() - tick
        tick = time.perf_counter()
        differences, host_failures = {}, []
        for j in range(rows):
            host, message = host_row(history, j, offset)
            if message is not None:
                host_failures.append([j, message])
                continue
            for k, (key, value) in enumerate(host.items()):
                difference = abs(float(values[j, k]) - value)
                # Rounding residuals relative to their smallest bound; the energy
                # residual (a truncation quantity) relative to itself.
                scale = scales.get(key, max(abs(value), 1e-300))
                differences[key] = max(differences.get(key, 0.0), difference / scale)
        report[f"passing_offset_{offset}"] = dict(
            rows=rows,
            device_failed_rows=int(failed.any(axis=1).sum()),
            host_failures=host_failures,
            max_difference_over_scale=differences,
            device_seconds=device_seconds,
            host_seconds=time.perf_counter() - tick,
            device_max=dict(
                zip(model.DEVICE_DIAGNOSTICS, values.max(axis=0).tolist(), strict=True)
            ),
        )
        write(args, label + ".json", report)
    faults, row = {}, rows // 2
    for kind in ("channel_transfer", "channel_gate", "metabolic"):
        if kind.startswith("channel") and args.model != 3:
            continue
        corrupted, expected = seeded_fault(history, p, kind, row)
        failed, _ = device_rows(corrupted, 0)
        device_first = np.flatnonzero(failed.any(axis=1))
        host_first = None
        for j in range(rows):
            _, message = host_row(corrupted, j, 0)
            if message is not None:
                host_first = [j, message]
                break
        first = int(device_first[0]) if len(device_first) else None
        faults[kind] = dict(
            seeded_row=row,
            expected_check=expected,
            host_first=host_first,
            device_first_row=first,
            device_checks=None
            if first is None
            else [c for c, f in zip(model.DEVICE_CHECKS, failed[first], strict=True) if f],
            agree=host_first is not None
            and first == host_first[0]
            and model.device_failure_message(model.DEVICE_CHECKS[int(np.argmax(failed[first]))])
            == host_first[1],
        )
        write(args, label + ".json", report | dict(faults=faults))
    report["faults"] = faults
    report["all_agree"] = (
        all(not report[f"passing_offset_{o}"]["host_failures"] for o in (0, HOUR_STEPS))
        and all(report[f"passing_offset_{o}"]["device_failed_rows"] == 0 for o in (0, HOUR_STEPS))
        and all(f["agree"] and f["host_first"][0] == row for f in faults.values())
    )
    write(args, label + ".json", report)


# Heredity tier 1 (docs/HEREDITY_FIRST_EXPERIMENT.md, design.json): world-steps
# at dt = 1 ms, and the design's x1.25 allowance for NaV/Kir gates (G1).
TIER_1_WORLD_STEPS = 6431040000
CHANNEL_ALLOWANCE = 1.25


def part_summary(args):
    """Table of all vector results in --output, with the tier-1 cost at each width."""
    rows = []
    for path in sorted(Path(args.output).glob("vector-model*-worlds*.json")):
        r = json.loads(path.read_text())
        counters = (r.get("gpu_counters") or {}).get("after_warmup") or {}
        hardware = (counters.get("hardware") or {}).get("fields") or {}
        busy = (counters.get("gpu_busy") or {}).get("mean_pct_over_covered_time")
        rows.append(
            dict(
                model=r["model"],
                worlds=r["worlds"],
                heterogeneous=r.get("heterogeneous", False),
                ms_per_batch_step=r.get("ms_per_batch_step"),
                world_steps_per_second=r.get("world_steps_per_second"),
                compile_seconds=r.get("compile_seconds"),
                peak_device_bytes=(r.get("memory_after_run") or {}).get("peak_bytes_in_use"),
                compiled_bytes=sum(
                    (r.get("compiled_memory_analysis") or {}).get(k, 0)
                    for k in (
                        "argument_size_in_bytes",
                        "output_size_in_bytes",
                        "temp_size_in_bytes",
                    )
                ),
                gpu_busy_pct=busy,
                **{
                    name + "_pct": (hardware.get(name) or {}).get("mean_pct_over_covered_time")
                    for name in ("sm_active", "sm_occupancy", "dram_active")
                },
                failures=r.get("failures"),
                # @3 carries the channels; @1/@2 take the design's allowance.
                l4_tier_1_gpu_hours=TIER_1_WORLD_STEPS
                * (1.0 if r["model"] == 3 else CHANNEL_ALLOWANCE)
                / r["world_steps_per_second"]
                / 3600
                if r.get("world_steps_per_second")
                else None,
            )
        )
    endtoend = []
    for path in sorted(Path(args.output).glob("endtoend-model*-worlds*.json")):
        r = json.loads(path.read_text())
        endtoend.append(
            dict(
                model=r["model"],
                worlds=r["worlds"],
                window=r["window"],
                steps=r["steps"],
                ms_per_batch_step=r["steady_ms_per_batch_step"],
                ms_per_world_step=r["steady_ms_per_batch_step"] / r["worlds"],
                # The host waits for a window only after finishing the previous
                # one (the device runs ahead), so this is the wait left over, not
                # the device time: the vector part measures that.
                device_wait_ms_per_world_step=1e3
                * r["timings"]["execute_seconds"]
                / (r["steps"] * r["worlds"]),
                analysis_seconds=r["timings"]["analysis_seconds"],
                peak_device_bytes=(r.get("memory") or {}).get("peak_bytes_in_use"),
            )
        )
    sequential = []
    for path in sorted(Path(args.output).glob("sequential-model*-worlds*.json")):
        r = json.loads(path.read_text())
        sequential.append(
            {k: r[k] for k in ("model", "worlds", "window", "steps")}
            | {
                "execute_ms_per_batch_step": r["execute_ms_per_batch_step"],
                "host_check_ms_per_batch_step": r["host_check_ms_per_batch_step"],
            }
        )
    failures = sorted(p.name for p in Path(args.output).glob("*.failure.json"))
    write(
        args,
        "summary.json",
        dict(
            kind="cells.batched_worlds_summary@1",
            rows=sorted(rows, key=lambda r: (r["model"], r["heterogeneous"], r["worlds"])),
            endtoend=sorted(endtoend, key=lambda r: (r["model"], r["worlds"])),
            sequential=sorted(sequential, key=lambda r: (r["model"], r["worlds"])),
            failures=failures,
            tier_1_world_steps=TIER_1_WORLD_STEPS,
            channel_allowance=CHANNEL_ALLOWANCE,
            l4_tier_1_gpu_hours_scope=(
                "measured L4 rate (x 1.25 channel allowance for models 1 and 2); not GH200"
            ),
        ),
    )


PARTS = dict(
    summary=part_summary,
    components=part_components,
    vector=part_vector,
    endtoend=part_endtoend,
    sequential=part_sequential,
    equivalence=part_equivalence,
    checks=part_checks,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--model", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--worlds", type=int, default=1)
    parser.add_argument("--output", required=True)
    parser.add_argument("--window", type=int, default=32)
    parser.add_argument("--max-windows", type=int, default=40)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--backend", default="gpu")
    parser.add_argument("--dcgm-root")
    parser.add_argument("--heterogeneous", action="store_true")
    parser.add_argument("--observe-every", type=int, help="observation spacing in steps")
    parser.add_argument(
        "--junction-heat", help="model 3: junction_heat_booking (e.g. trapezoid_nonnegative@1)"
    )
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    label = f"{args.part}-{args.backend}-model{args.model}-worlds{args.worlds}"
    try:
        PARTS[args.part](args)
    except BaseException as exc:
        write(
            args,
            label + ".failure.json",
            dict(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc()),
        )
        raise


if __name__ == "__main__":
    main()
