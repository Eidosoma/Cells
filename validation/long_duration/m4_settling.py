"""M4: settling after interventions on W0 (REGISTRATION_20261118.md §6, amendment 2).

run ARM OUT_DIR: W0 at 1 ms to 180 s with the arm's intervention at t0 = 60 s (A0 none, A1 the
channel step, A2 the dose step, A3 the regulatory write), through the windowed runner (host row
checks). At every accepted row in [t0 - 1 s, t0 + 120 s] the sink evaluates
models/surface_pump_projective.settling on the composite's inner model at the composite's own
effective control and view (amendment 2: settling on the composite itself omits the channel
gates), and keeps that row's membrane voltages. The direct composite call is kept beside it
at every DIRECT_EVERY-th kept row (it only shows the gap, and doubles the cost per row).

judge OUTPUT.json M2_JSON ARM_DIR...: the settling time per registered threshold, the background
check against A0, the budget rule's threshold from S7b's M2 spectrum, and each arm's peak |dVm|
from A0. Stage 0 makes no qualification claim (amendment 1, Q1).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

ARMS = ("A0", "A1", "A2", "A3")
DIRECT_EVERY = 100


def timing(development=None):
    """(t0, end) as registered, or a development (t0, end) for smoke runs only."""
    from validation.long_duration import worlds

    reg = worlds.registration()["m4"]
    return (reg["t0_s"], reg["end_s"]) if development is None else tuple(development)


def world(arm, development=None):
    from validation.long_duration import worlds

    reg = worlds.registration()["m4"]
    t0, end = timing(development)
    kwargs = dict(A0={}, A1=dict(channel_step=t0), A2=dict(dose=t0), A3=dict(write=t0))[arm]
    return worlds.w0(end=end, dt=reg["dt_s"], observation_times=[0.0, t0, end], **kwargs)


class SettlingSink:
    """The settling readouts and membrane voltages at every accepted row in a time window."""

    def __init__(self, spec, model, window):
        from cells.execution.schedule import control_values

        self.spec, self.model, self.window = spec, model, window
        _, self.p = model.initial_values(spec)
        self.control_values = control_values
        self.rows = {}

    def __call__(self, result):
        from cells.models import surface_pump_projective as projective

        times = np.asarray(result.times, dtype=float)
        keep = np.flatnonzero((times >= self.window[0]) & (times <= self.window[1]))
        if not len(keep):
            return
        model, p = self.model, self.p
        controls = self.control_values(self.spec, [float(times[i]) for i in keep])
        for j, i in enumerate(keep):
            t = float(times[i])
            if t in self.rows:
                continue
            row = model.STATE_TYPE(*(np.asarray(v)[i] for v in result.history))
            control = type(controls)(*(np.asarray(v)[j] for v in controls))
            inner_state = model.inner_state(row)
            inner_control = model.control_view(control, row, p, xp=np)
            view = model.view(p, row, xp=np)
            ok, rate, gate = projective.settling(model.inner, inner_state, inner_control, view)
            direct = (False, np.nan, np.nan)
            if len(self.rows) % DIRECT_EVERY == 0:  # Only to show the gap (amendment 2).
                try:
                    direct = projective.settling(model, row, control, p)
                except Exception:
                    pass
            vm = projective.membrane_voltage(inner_state, view)
            self.rows[t] = (bool(ok), rate, gate, bool(direct[0]), direct[1], direct[2], vm)

    def arrays(self):
        times = np.asarray(sorted(self.rows))
        cols = list(zip(*(self.rows[t] for t in times), strict=True))
        names = ("valid", "voltage_rate", "gate_distance", "direct_valid", "direct_voltage_rate",
                 "direct_gate_distance", "vm")  # fmt: skip
        return dict(times=times, **{k: np.asarray(v) for k, v in zip(names, cols, strict=True)})


def run_arm(arm, out_dir, development=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, run_windowed
    from cells.registry.models import get_model
    from validation.long_duration import harness, worlds

    reg = worlds.registration()["m4"]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    t0, end = timing(development)
    spec = parse_spec(world(arm, development))
    model = get_model(spec.model)
    if (
        getattr(model, "process_operator", None) is not None
    ):  # Amendment 2 rests on there being none.
        raise RuntimeError("W0 declares a membrane-process operator, which M4 does not foresee")
    sink = SettlingSink(
        spec, model, (t0 + reg["readout_window_s"][0], t0 + reg["readout_window_s"][1])
    )
    record = dict(
        measurement="M4",
        arm=arm,
        t0_s=t0,
        end_s=end,
        run_of_record=development is None,
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        snapshot_revision=harness.snapshot_revision(),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    started = time.perf_counter()
    try:
        result = run_windowed(spec, WindowPolicy(window_steps=2048), sink=sink)
        record.update(status="complete", steps=int(result.resources["executed_steps"]),
                      diagnostics={k: float(v) for k, v in result.diagnostics.items()})  # fmt: skip
    except Exception as error:  # A refusal is the arm's result (§0).
        record.update(status="refused", error_type=type(error).__name__, error=str(error))
    record["seconds"] = time.perf_counter() - started
    if sink.rows:
        np.savez_compressed(out / "settling.npz", **sink.arrays())
    (out / "run.json").write_text(json.dumps(record, indent=1) + "\n")
    return 0 if record["status"] == "complete" else 1


def settling_time(times, rate, gate, theta_v, theta_g, start, hold, last):
    """The first row t >= start from which rate <= theta_v and gate <= theta_g at every row
    through t + hold, with t <= last; None if no such row."""
    t = np.asarray(times, dtype=float)
    inside = (np.asarray(rate) <= theta_v) & (np.asarray(gate) <= theta_g)
    # The next outside row's time at or after each row (inf if none): a row qualifies when that
    # lies beyond its hold.
    outside = np.where(inside, np.inf, t)
    next_outside = np.minimum.accumulate(outside[::-1])[::-1]
    qualifies = (t >= start) & (t <= last) & (next_outside > t + hold)
    first = np.flatnonzero(qualifies)
    return float(t[first[0]]) if len(first) else None


def exceeds(times, rate, gate, theta_v, theta_g, start, stop):
    t = np.asarray(times, dtype=float)
    mask = (t >= start) & (t <= stop)
    return bool(np.any((np.asarray(rate)[mask] > theta_v) | (np.asarray(gate)[mask] > theta_g)))


def judge(output, m2_path, directories):
    from validation.long_duration import worlds

    reg = worlds.registration()["m4"]
    hold = reg["hold_s"]
    arms = {}
    for d in directories:
        record = json.loads((Path(d) / "run.json").read_text())
        data = (
            dict(np.load(Path(d) / "settling.npz"))
            if (Path(d) / "settling.npz").is_file()
            else None
        )
        arms[record["arm"]] = (record, data)
    if len({(r["t0_s"], r["run_of_record"]) for r, _ in arms.values()}) != 1:
        raise ValueError("M4's arms differ in t0 or in being runs of record")
    t0 = next(iter(arms.values()))[0]["t0_s"]
    last = t0 + reg["not_settled_after_s"]
    stop = t0 + reg["readout_window_s"][1]
    m2 = json.loads(Path(m2_path).read_text())["worlds"]["S7b"]["split"]
    fast = np.asarray([complex(r, i) for r, i in m2["fast_part"]])
    tau_f = 1.0 / float(np.min(np.abs(fast)))
    allowed = [v for v, _ in reg["thresholds"] if v * tau_f <= reg["residual_transient_V"]]
    rule_threshold = max(allowed) if allowed else None
    control = arms["A0"][1]
    out = dict(
        measurement="M4",
        run_of_record=next(iter(arms.values()))[0]["run_of_record"],
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        tau_f_s=tau_f,
        budget_rule_threshold_V_per_s=rule_threshold,
        arms={},
    )
    for arm, (record, data) in arms.items():
        entry = dict(status=record["status"], error=record.get("error"))
        if data is None or record["status"] != "complete":
            out["arms"][arm] = entry
            continue
        settle = {}
        for theta_v, theta_g in reg["thresholds"]:
            key = f"{theta_v:g}"
            ts = settling_time(data["times"], data["voltage_rate"], data["gate_distance"], theta_v,
                               theta_g, t0, hold, last)  # fmt: skip
            background = exceeds(control["times"], control["voltage_rate"],
                                 control["gate_distance"], theta_v, theta_g, t0, stop)  # fmt: skip
            settle[key] = dict(
                settling_time_s=ts,
                after_intervention_s=None if ts is None else ts - t0,
                not_settled=ts is None,
                attributable=not background,
            )
        entry["settling"] = settle
        if arm != "A0" and np.array_equal(data["times"], control["times"]):
            entry["peak_dVm_from_A0_V"] = float(np.max(np.abs(data["vm"] - control["vm"])))
        sampled = np.isfinite(data["direct_gate_distance"])
        entry["gap"] = dict(  # Amendment 2: the direct composite call on the sampled rows.
            sampled_rows=int(sampled.sum()),
            direct_gate_distance_max=float(
                np.max(data["direct_gate_distance"][sampled], initial=0)
            ),
            inner_gate_distance_max=float(np.max(data["gate_distance"][sampled], initial=0)),
            direct_voltage_rate_max=float(np.max(data["direct_voltage_rate"][sampled], initial=0)),
            inner_voltage_rate_max=float(np.max(data["voltage_rate"][sampled], initial=0)),
        )
        entry["window_length_at_rule_threshold_s"] = (
            settle[f"{rule_threshold:g}"]["after_intervention_s"] if rule_threshold else None
        )
        out["arms"][arm] = entry
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "run":  # run ARM OUT_DIR [T0 END]: a development (t0, end), never of record.
        development = tuple(float(v) for v in sys.argv[4:6]) if len(sys.argv) > 4 else None
        sys.exit(run_arm(sys.argv[2], sys.argv[3], development))
    sys.exit(judge(sys.argv[2], sys.argv[3], sys.argv[4:]))
