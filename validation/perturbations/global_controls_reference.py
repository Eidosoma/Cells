"""Independent high-precision setter expressions; no production or array imports."""

from decimal import Decimal, localcontext

SIDES = ("top", "bottom", "left", "right")


def d(value):
    return Decimal.from_float(float(value))


def evaluate(program, state, time_s, original_temperature_K, *, events_enabled=True):
    with localcontext() as context:
        context.prec = 125
        temperature, pump = d(state["temperature_K"]), d(state["pump_available"])
        junctions = [d(x) for x in state["junction_available"]]
        voltage = [d(x) for x in state["boundary_voltage_V"]]
        for row in program["events"] if events_enabled else ():
            gain = 10 / d(row["change_s"])
            first = 1 / (1 + (-gain * (d(time_s) - d(row["on_s"]))).exp())
            last = 1 / (1 + (-gain * (d(time_s) - d(row["off_s"]))).exp())
            pulse = first - last
            kind = row["kind"]
            if kind == "temperature":
                temperature = d(original_temperature_K) * (1 + d(row["amplitude"]) * pulse)
            elif kind == "junction_block":
                for name in row["target_ids"]:
                    junctions[program["membrane_ids"].index(name)] = 1 - pulse
            elif kind == "pump_block":
                pump = 1 - pulse
            else:
                voltage[SIDES.index(row["positive_boundary"])] = d(row["amplitude"]) * pulse
                voltage[SIDES.index(row["negative_boundary"])] = -d(row["amplitude"]) * pulse
        return dict(
            temperature_K=float(temperature),
            pump_available=float(pump),
            junction_available=[float(v) for v in junctions],
            boundary_voltage_V=[float(v) for v in voltage],
        )
