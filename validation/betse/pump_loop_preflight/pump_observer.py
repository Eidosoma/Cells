"""Read-only native pump/passive boundaries on the existing full-loop observer."""

import importlib
import sys

import pump_context as ctx

sys.path.insert(0, str(ctx.HERE.parent / "channel_loop_preparation"))
old = importlib.import_module("loop_observer")
c = ctx.c


def numeric(value):
    import numpy as np

    a = np.asarray(value, dtype=np.float64)
    c.require(np.isfinite(a).all(), "Nonfinite native observation")
    return a.tolist()


class PumpLoopObserver(old.ChannelLoopObserver):
    """Only direct loop calls count; junction electroflux is not membrane leak."""

    def __init__(self, *args):
        super().__init__(*args)
        self.toolbox = str(self.science / "sim_toolbox.py")
        self.raw_steps, self.inflight = [], {}

    def observe(self, frame, event, argument):
        name = frame.f_code.co_name
        if (
            event in ("call", "return")
            and self.loop_frame is not None
            and frame.f_back is self.loop_frame
            and frame.f_code.co_filename == self.toolbox
            and name in ("pumpNaKATP", "electroflux")
        ):
            if event == "call":
                index = len(self.steps)
                if index == len(self.raw_steps):
                    self.raw_steps.append(
                        dict(index=index, before=self.snapshot(self.phase.sim), calls=[])
                    )
                c.require(len(self.raw_steps) == index + 1 and not self.inflight, "Raw step order")
                keys = (
                    ("cNai", "cNao", "cKi", "cKo", "Vm", "T", "block")
                    if name == "pumpNaKATP"
                    else ("cA", "cB", "Dc", "d", "zc", "vBA", "T", "rho")
                )
                record = dict(function=name, inputs={k: numeric(frame.f_locals[k]) for k in keys})
                if name == "electroflux":
                    record["species_index"] = int(self.loop_frame.f_locals["i"])
                self.raw_steps[index]["calls"].append(record)
                self.inflight[id(frame)] = record
            elif old.successful_return(frame):
                c.require(id(frame) in self.inflight, "Unpaired native function return")
                self.inflight.pop(id(frame))["returned"] = numeric(argument)
        super().observe(frame, event, argument)

    def validate_complete(self):
        super().validate_complete()
        c.require(
            len(self.raw_steps) == len(self.steps) and not self.inflight, "Raw loop incomplete"
        )
        moving = list(map(int, self.phase.sim.movingIons))
        for index, step in enumerate(self.raw_steps):
            calls = step["calls"]
            c.require(
                step["index"] == index and all("returned" in v for v in calls), "Raw coverage"
            )
            c.require(
                sum(v["function"] == "pumpNaKATP" for v in calls)
                == int(self.phase.p.alpha_NaK > 0),
                "Pump call count",
            )
            c.require(
                [v["species_index"] for v in calls if v["function"] == "electroflux"] == moving,
                "Passive species call order",
            )
            if self.phase.p.alpha_NaK > 0:
                c.require(calls[0]["function"] == "pumpNaKATP", "Pump/passive order")

    def partial(self):
        return super().partial() | {
            "raw_steps": self.raw_steps,
            "inflight_calls": len(self.inflight),
        }
