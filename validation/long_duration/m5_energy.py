"""M5: where the energy check binds, on W0 (REGISTRATION_20261118.md §7).

run BOOKING DT OUT_DIR: W0 to 60 s with the dose step at 20 s and the write at 40 s, observed
every 1 s, at dt with the junction booking, through the windowed runner (device row checks,
which hand any window near a bound to the host's check_values, so a refusal keeps the host's own
message; 256-step windows, so a run-time refusal is bracketed to 256 steps; the host checks would
evaluate every row's ledgers a second time beside the sink's). At every accepted row the
sink evaluates rho = |R| / B with the check's own functions: R the energy entry of the
composite's inner_balances (the ledgers the row checks judge) and B its bound from the inner
ledger_limits at the row's global step count (ENERGY_ATOL_PJ + rtol F plus the step rounding
allowance). A refusal at definition time or at run time is the arm's result.

judge OUTPUT.json ARM_DIR...: rho_max per arm, the order from the two largest unrefused dt per
booking, the binding step dt* (or its labelled extrapolation), the trapezoid's effect, and each
arm's observation rows against the same booking's 1 ms arm with the caps (reported).
Stage 0 makes no qualification claim (amendment 1, Q1).
"""

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

WINDOW_STEPS = 256


def timing(development=None):
    """(end, dose, write) as registered, or a development triple for smoke runs only."""
    from validation.long_duration import worlds

    reg = worlds.registration()["m5"]
    if development is None:
        return reg["end_s"], reg["dose_s"], reg["write_s"]
    return tuple(development)


def world(booking, dt, development=None):
    from validation.long_duration import worlds

    reg = worlds.registration()["m5"]
    end, dose, write = timing(development)
    times = worlds.grid(0.0, end, reg["observe_every_s"])
    return worlds.w0(end=end, dt=dt, observation_times=times, booking=booking, dose=dose,
                     write=write)  # fmt: skip


def ratio(residual, bound):
    """rho: the energy residual's magnitude over the check's bound (above 1 the check refuses)."""
    return abs(residual) / bound


class EnergySink:
    """rho at every accepted row, the rows' global step counts, and the observation rows."""

    def __init__(self, spec, model, observed):
        self.spec, self.model = spec, model
        _, self.p = model.initial_values(spec)
        self.tol = np.asarray(spec.execution.material_balance_atol_fmol)
        self.rtol = model.inner.ENERGY_RTOL[spec.execution.solver]
        self.observed = set(float(t) for t in observed)
        self.step = 0
        self.first = True
        self.times, self.rho, self.residual, self.bound, self.flows = [], [], [], [], []
        self.rows = {}
        self.last_time = 0.0

    def __call__(self, result):
        model, p = self.model, self.p
        times = np.asarray(result.times, dtype=float)
        # Row i of a window is global step base + i, base the previous window's last step (0 at
        # first); a later window's row 0 repeats that step, so it is skipped.
        start, base = (0 if self.first else 1), self.step
        with np.errstate(all="ignore"):
            for i in range(start, len(times)):
                count = base + i
                row = model.STATE_TYPE(*(np.asarray(v)[i] for v in result.history))
                ledgers = model.inner_balances(row, p)
                flows, limits = model.inner.ledger_limits(
                    row, p, self.tol, self.rtol, steps=count,
                    magnitudes=model.inner_magnitudes(row, p, xp=np),
                )  # fmt: skip
                index = list(ledgers).index("energy")
                residual, bound = float(ledgers["energy"]), float(np.asarray(limits[index]))
                self.times.append(float(times[i]))
                self.residual.append(residual)
                self.bound.append(bound)
                self.flows.append(float(flows))
                self.rho.append(ratio(residual, bound))
                t = float(times[i])
                if t in self.observed and t not in self.rows:
                    self.rows[t] = tuple(
                        np.array(np.asarray(v)[i], copy=True) for v in result.history
                    )
        self.step = base + len(times) - 1
        self.first = False
        self.last_time = float(times[-1])


def run_arm(booking, dt, out_dir, development=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, run_windowed
    from cells.registry.models import get_model
    from validation.long_duration import harness, worlds

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    record = dict(
        measurement="M5",
        booking=booking,
        dt_s=dt,
        timing_s=list(timing(development)),
        run_of_record=development is None,
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        snapshot_revision=harness.snapshot_revision(),
        window_steps=WINDOW_STEPS,
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    started = time.perf_counter()
    sink = None
    try:
        spec = parse_spec(world(booking, dt, development))
        model = get_model(spec.model)
        if getattr(model, "retiring", ()):
            raise RuntimeError("W0 declares a retiring operator, which M5 does not foresee")
        record["trapezoid_layout_size"] = int(
            np.asarray(model.initial_values(spec)[1].junction_heat_trapezoid).size
        )
        sink = EnergySink(spec, model, spec.experiment.observation_times)
        policy = WindowPolicy(window_steps=WINDOW_STEPS, row_checks="device")
        result = run_windowed(spec, policy, sink=sink)
        record.update(status="complete", steps=int(result.resources["executed_steps"]),
                      diagnostics={k: float(v) for k, v in result.diagnostics.items()})  # fmt: skip
    except Exception as error:  # A refusal is the arm's result (§7).
        stage = "definition" if sink is None or not sink.times else "run"
        record.update(status="refused", stage=stage, error_type=type(error).__name__,
                      error=str(error))  # fmt: skip
        if sink is not None and sink.times:
            record["refused_between_s"] = [sink.last_time, sink.last_time + WINDOW_STEPS * dt]
    record["seconds"] = time.perf_counter() - started
    if sink is not None and sink.times:
        rows = {}
        if sink.rows:
            fields = sink.model.STATE_TYPE._fields
            obs_times = np.asarray(sorted(sink.rows))
            columns = list(zip(*(sink.rows[t] for t in obs_times), strict=True))
            rows = {f"row_{k}": np.stack(v) for k, v in zip(fields, columns, strict=True)}
            rows["row_times"] = obs_times
        np.savez_compressed(
            out / "energy.npz",
            times=np.asarray(sink.times),
            rho=np.asarray(sink.rho),
            residual_pJ=np.asarray(sink.residual),
            bound_pJ=np.asarray(sink.bound),
            flows_pJ=np.asarray(sink.flows),
            **rows,
        )
        record["rho_max"] = float(np.max(sink.rho))
        record["rho_max_time_s"] = float(sink.times[int(np.argmax(sink.rho))])
        record["rows_checked"] = len(sink.times)
    (out / "run.json").write_text(json.dumps(record, indent=1) + "\n")
    return 0


def order(dt_a, rho_a, dt_b, rho_b):
    if not (rho_a > 0 and rho_b > 0 and dt_a != dt_b):
        return None
    return math.log(rho_a / rho_b) / math.log(dt_a / dt_b)


def energy_refusal(record):
    """A refusal by the energy ledger's row check (the host's message for that ledger)."""
    from cells.models.surface_pump import LEDGER_MESSAGE

    return record["status"] == "refused" and (LEDGER_MESSAGE + "energy") in record.get("error", "")


def observed_classes(directory, record):
    """(times, membrane voltages [rows, patches], concentrations [rows, species, cells]) of an
    arm's observation rows, from the engine's own readouts at the composite's view."""
    from cells.definitions.specs import parse_spec
    from cells.models import surface_pump_projective as projective
    from cells.registry.models import get_model

    with np.load(Path(directory) / "energy.npz") as archive:  # Each array once: an indexed
        data = {k: archive[k] for k in archive.files}  # npz decompresses per access.
    if "row_times" not in data:
        return None
    development = None if record["run_of_record"] else record["timing_s"]
    spec = parse_spec(world(record["booking"], record["dt_s"], development))
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    fields = model.STATE_TYPE._fields
    vm, conc = [], []
    for i in range(len(data["row_times"])):
        row = model.STATE_TYPE(*(data[f"row_{f}"][i] for f in fields))
        inner_state, view = model.inner_state(row), model.view(p, row, xp=np)
        vm.append(projective.membrane_voltage(inner_state, view))
        ci, _ = model.inner.physical_amounts(inner_state, view)
        cells = np.asarray(view.active, dtype=bool)
        conc.append(ci[:, cells] / view.volume[cells])
    return data["row_times"], np.asarray(vm), np.asarray(conc)


def by_products(directories, records):
    """Each complete arm's observation rows against its booking's 1 ms arm (reported, with the
    caps; not judged)."""
    from validation.long_duration import worlds

    caps = worlds.registration()["benchmarks"]["parity_caps"]
    arms = {(r["booking"], r["dt_s"]): (d, r) for d, r in zip(directories, records, strict=True)}
    out = []
    for (booking, dt), (d, r) in sorted(arms.items()):
        base = arms.get((booking, 1e-3))
        if (
            dt == 1e-3
            or r["status"] != "complete"
            or base is None
            or base[1]["status"] != "complete"
        ):
            continue
        test, ref = observed_classes(d, r), observed_classes(*base)
        if test is None or ref is None:
            continue
        times = np.intersect1d(test[0], ref[0])
        a = np.searchsorted(test[0], times)
        b = np.searchsorted(ref[0], times)
        dv = float(np.max(np.abs(test[1][a] - ref[1][b]), initial=0.0))
        dc = float(np.max(np.abs(test[2][a] - ref[2][b]) / np.abs(ref[2][b]), initial=0.0))
        out.append(dict(booking=booking, dt_s=dt, rows=len(times), max_dVm_V=dv,
                        max_relative_dc=dc, voltage_cap_ratio=dv / caps["voltage_V"],
                        concentration_cap_ratio=dc / caps["relative_concentration"]))  # fmt: skip
    return out


def judge(output, directories):
    from validation.long_duration import worlds

    records = [json.loads((Path(d) / "run.json").read_text()) for d in directories]
    if len({r["run_of_record"] for r in records}) != 1:
        raise ValueError("M5's arms mix development runs with runs of record")
    out = dict(
        measurement="M5",
        run_of_record=records[0]["run_of_record"],
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        arms=[
            {
                k: r.get(k)
                for k in (
                    "booking",
                    "dt_s",
                    "status",
                    "stage",
                    "error",
                    "rho_max",
                    "rho_max_time_s",
                    "refused_between_s",
                    "trapezoid_layout_size",
                )
            }
            for r in records
        ],  # fmt: skip
        bookings={},
    )
    for booking in worlds.registration()["m5"]["bookings"]:
        arms = sorted((r for r in records if r["booking"] == booking), key=lambda r: r["dt_s"])
        unrefused = [r for r in arms if r["status"] == "complete"]
        entry = dict(rho_max={str(r["dt_s"]): r["rho_max"] for r in unrefused})
        p = None
        if len(unrefused) >= 2:
            a, b = unrefused[-1], unrefused[-2]
            p = order(a["dt_s"], a["rho_max"], b["dt_s"], b["rho_max"])
        entry["order"] = p
        refused_energy = [r["dt_s"] for r in arms if energy_refusal(r)]
        if refused_energy:
            entry["binding_step_s"] = min(refused_energy)
            entry["binding_step_kind"] = "smallest dt refused by the energy check"
        elif unrefused and p is not None and p > 0:  # Only a residual growing with dt.
            largest = unrefused[-1]
            entry["binding_step_s"] = largest["dt_s"] * (1.0 / largest["rho_max"]) ** (1.0 / p)
            entry["binding_step_kind"] = "extrapolation from the largest unrefused dt"
        entry["other_refusals"] = [
            dict(dt_s=r["dt_s"], stage=r.get("stage"), error=r.get("error"))
            for r in arms
            if r["status"] == "refused" and not energy_refusal(r)
        ]
        out["bookings"][booking] = entry
    default, trapezoid = (out["bookings"].get(b, {}).get("rho_max", {}) for b in
                          worlds.registration()["m5"]["bookings"])  # fmt: skip
    out["trapezoid_effect"] = {
        dt: trapezoid[dt] / default[dt] for dt in default if dt in trapezoid and default[dt] > 0
    }
    out["by_products"] = by_products(directories, records)
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    if (
        sys.argv[1] == "run"
    ):  # run BOOKING DT OUT_DIR [END DOSE WRITE]: development, never of record.
        development = tuple(float(v) for v in sys.argv[5:8]) if len(sys.argv) > 5 else None
        sys.exit(run_arm(sys.argv[2], float(sys.argv[3]), sys.argv[4], development))
    sys.exit(judge(sys.argv[2], sys.argv[3:]))
