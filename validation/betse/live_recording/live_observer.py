"""Read-only INIT profiling adapter; one pending update, no growing trace lists."""

import dis
import hashlib
import math
import sys
from pathlib import Path

import live_context as ctx

sys.path.insert(0, str(ctx.HERE.parent / "native_recording"))
import native_row as layout  # noqa: E402

need = ctx.need
HISTORY_SOURCE = dict(
    time=None,
    cc_time="cc_cells",
    cc_env_time="cc_env",
    vm_time="vm",
    I_mem_time="I_mem",
    rho_cells_time="rho_cells",
    rate_NaKATP_time="rate_NaKATP",
    gjopen_time="gjopen",
    dd_time="Dm_cells",
)
CALLS = (
    "run_sim_core",
    "init_dynamics",
    "clear_storage",
    "initial_update_V",
    "loop",
    "loop_return",
    "run_return",
)


def successful_return(frame):
    return dis.opname[frame.f_code.co_code[frame.f_lasti]] in ("RETURN_VALUE", "RETURN_CONST")


def numeric(value):
    import numpy as np

    array = np.asarray(value, dtype=np.float64)
    need(np.isfinite(array).all(), "Nonfinite observation")
    return array.tolist()


def json_tree(value):
    """Legacy JSON scalar/container semantics without a decimal round-trip.

    BETSE parameters include float subclasses. Normalize the validation-side
    copy, never native objects or the strict codec. Global recursion has no
    closure cycle. Unsupported objects still fail instead of being coerced.
    """
    if value is None or type(value) is bool:
        return value
    if isinstance(value, float):
        need(math.isfinite(value), "Nonfinite JSON scalar")
        return float(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [json_tree(v) for v in value]
    if isinstance(value, dict):
        need(all(isinstance(k, str) for k in value), "Nonstring native key")
        return {str(k): json_tree(v) for k, v in value.items()}
    raise ValueError("Unsupported native JSON type: " + type(value).__name__)


def history_specs(sim, steps):
    import numpy as np

    return {
        name: dict(
            dtype="<f8",
            shape=[steps - 1]
            + (
                []
                if source is None
                else [int(sim.mdl)]
                if source == "rate_NaKATP"
                else list(np.asarray(getattr(sim, source)).shape)
            ),
        )
        for name, source in HISTORY_SOURCE.items()
    }


class StreamObserver:
    """The storage-only mode emits no physical trace, but still observes history writes.

    Native histories and the native time array/set are deliberately NOT changed.
    Full trace has one raw-call group and one physical-step group in flight.
    """

    def __init__(self, phase, science, snapshot, header, sink, observed):
        self.phase, self.snapshot, self.header_factory = phase, snapshot, header
        self.sink, self.observed = sink, observed
        self.science = Path(science).resolve()
        self.sim_file = str(self.science / "sim.py")
        self.toolbox = str(self.science / "sim_toolbox.py")
        self.calls = dict.fromkeys(CALLS, 0)
        self.loop_frame = None
        self.pending = self.raw = self.inflight = None
        self.updates = self.samples = 0
        self.validator = layout.Validator()
        self.started = self.finished = False
        self.peak_pending_updates = 0

    def emit(self, value):
        value = json_tree(value)
        self.validator.accept(value)
        self.sink.append(value)

    def enter_loop(self, frame):
        need(not self.started and self.loop_frame is None, "Repeated loop entry")
        need(
            self.calls
            == dict(
                run_sim_core=1,
                init_dynamics=1,
                clear_storage=1,
                initial_update_V=1,
                loop=0,
                loop_return=0,
                run_return=0,
            ),
            "Incomplete native lifecycle",
        )
        need(
            self.phase.sim.molecules is None and not self.phase.p.grn_enabled,
            "Only network-free pump INIT supported",
        )
        times, sampled = frame.f_locals["time_steps"], frame.f_locals["time_steps_sampled"]
        need(
            len(times) == self.phase.p.init_tsteps and len(sampled) == len(times) - 1,
            "Native clock extent",
        )
        need(
            all((time in sampled) == (i > 0) for i, time in enumerate(times)),
            "Native storage schedule",
        )
        self.loop_frame = frame
        self.calls["loop"] = 1
        initial = self.snapshot(self.phase.sim) if self.observed else None
        self.emit(self.header_factory(initial))
        self.started = True

    def raw_call(self, frame, event, argument):
        name = frame.f_code.co_name
        if event == "call":
            need(self.inflight is None and self.pending is None, "Overlapping raw call/update")
            if self.raw is None:
                self.raw = dict(index=self.updates, before=self.snapshot(self.phase.sim), calls=[])
            keys = (
                ("cNai", "cNao", "cKi", "cKo", "Vm", "T", "block")
                if name == "pumpNaKATP"
                else ("cA", "cB", "Dc", "d", "zc", "vBA", "T", "rho")
            )
            record = dict(function=name, inputs={key: numeric(frame.f_locals[key]) for key in keys})
            if name == "electroflux":
                record["species_index"] = int(self.loop_frame.f_locals["i"])
            self.raw["calls"].append(record)
            need(len(self.raw["calls"]) <= len(self.phase.sim.movingIons) + 1, "Extra raw calls")
            self.inflight = (id(frame), record)
        else:
            need(self.inflight is not None and self.inflight[0] == id(frame), "Unpaired raw return")
            self.inflight[1]["returned"] = numeric(argument)
            self.inflight = None

    def begin(self):
        need(self.pending is None and self.inflight is None, "Overlapping step")
        need(
            self.updates < self.phase.p.init_tsteps and self.samples == max(0, self.updates - 1),
            "Missing storage before next step",
        )
        label = float(self.loop_frame.f_locals["t"])
        need(
            label == float(self.loop_frame.f_locals["time_steps"][self.updates]),
            "Native chronology",
        )
        self.pending = dict(index=self.updates, raw_label_s=label)
        if self.observed:
            need(self.raw is not None and self.raw["index"] == self.updates, "Missing raw group")
            self.pending.update(
                before_elapsed_s=self.updates * self.phase.p.dt,
                after_elapsed_s=(self.updates + 1) * self.phase.p.dt,
                before=self.snapshot(self.phase.sim),
                order=[],
            )
        self.peak_pending_updates = max(self.peak_pending_updates, 1)

    def boundary(self, name):
        need(self.pending is not None and name not in self.pending, "Missing/duplicate boundary")
        if self.observed:
            self.pending[name] = self.snapshot(self.phase.sim)
            self.pending["order"].append(name)
        else:
            self.pending[name] = True

    def flush_step(self, storage):
        need(self.pending is not None and "after_voltage" in self.pending, "Incomplete update")
        if self.observed:
            self.emit(
                dict(
                    kind="native_step",
                    index=self.pending["index"],
                    step=self.pending,
                    raw_step=self.raw,
                    label_s=self.pending["raw_label_s"],
                    storage=storage,
                )
            )
        self.pending = self.raw = None

    def stored(self, label):
        need(
            self.pending is not None and self.updates > 1 and self.inflight is None,
            "Storage before complete sampled update",
        )
        index = self.updates - 1
        need(
            self.pending["index"] == index and label == self.pending["raw_label_s"], "Storage clock"
        )
        self.flush_step(dict(index=index, raw_label_s=label))
        values = {}
        for name in HISTORY_SOURCE:
            history = getattr(self.phase.sim, name)
            need(len(history) == self.samples + 1, "History growth differs: " + name)
            values[name] = numeric(history[-1])
        self.emit(dict(kind="native_history", index=self.samples, values=values))
        self.samples += 1

    def observe(self, frame, event, argument):
        if event not in ("call", "return") or (event == "return" and not successful_return(frame)):
            return
        name, source = frame.f_code.co_name, frame.f_code.co_filename
        own = source == self.sim_file and frame.f_locals.get("self") is self.phase.sim
        if own and event == "call" and name in ("run_sim_core", "init_dynamics", "clear_storage"):
            need(not self.started and self.calls[name] == 0, "Repeated/late native setup")
            self.calls[name] += 1
        if own and name == "update_V" and event == "call" and not self.started:
            self.calls["initial_update_V"] += 1
        if own and name == "_run_sim_core_loop":
            if event == "call":
                self.enter_loop(frame)
            else:
                need(
                    self.loop_frame is frame
                    and self.pending is None
                    and self.raw is None
                    and self.inflight is None,
                    "Incomplete loop return",
                )
                self.calls["loop_return"] += 1
                self.loop_frame = None
            return
        if own and name == "run_sim_core" and event == "return":
            self.calls["run_return"] += 1
        if self.loop_frame is None:
            return
        direct = frame.f_back is self.loop_frame
        if (
            self.observed
            and direct
            and source == self.toolbox
            and name in ("pumpNaKATP", "electroflux")
        ):
            self.raw_call(frame, event, argument)
        # Some Simulator methods are called through pinned beartype wrappers.
        # Match their actual source and instance, as the closed observer does;
        # the direct-parent restriction applies only to raw toolbox calls.
        if own:
            if name == "update_all_concs":
                if event == "call":
                    self.begin()
                    self.boundary("before_ordinary")
                else:
                    self.boundary("after_ordinary")
            elif name == "update_V" and event == "return":
                need(self.pending is not None and "after_ordinary" in self.pending, "Voltage order")
                self.boundary("after_voltage")
                self.updates += 1
                if self.updates == 1:
                    self.flush_step(None)
            elif name == "write2storage" and event == "return":
                self.stored(float(frame.f_locals["t"]))

    def validate_complete(self):
        need(
            self.started
            and all(value == 1 for value in self.calls.values())
            and self.updates == self.phase.p.init_tsteps
            and self.samples == self.updates - 1
            and self.pending is None
            and self.raw is None
            and self.inflight is None
            and self.loop_frame is None,
            "Incomplete live observation",
        )

    def finish(self, row):
        self.validate_complete()
        need(not self.finished and sys.getprofile() is None, "Hook active/reused footer")
        # Re-read the unmodified native histories sample-by-sample, without
        # materializing a full JSON history. This also catches later mutation.
        digests = {}
        for name, spec in self.validator.header["histories"].items():
            history = getattr(self.phase.sim, name)
            need(len(history) == self.samples, "Terminal history extent")
            digest = hashlib.sha256()
            for value in history:
                layout.hash_array(numeric(value), spec["shape"][1:], digest)
            digests[name] = digest.hexdigest()
        trace = (
            dict(
                calls=dict(self.calls),
                gate_initializations=0,
                hook_restored=True,
                inflight_calls=0,
                pending=None,
                status="complete_observation_not_qualification",
            )
            if self.observed
            else None
        )
        self.emit(dict(kind="native_footer", row=row, trace=trace, histories_sha256=digests))
        self.validator.finish()
        result = self.sink.finish()
        self.finished = True
        return result

    def partial(self):
        return dict(
            status="partial_not_qualified",
            calls=dict(self.calls),
            updates=self.updates,
            history_samples=self.samples,
            pending=self.pending,
            raw=self.raw,
            inflight_calls=int(self.inflight is not None),
            hook_restored=sys.getprofile() is None,
        )
