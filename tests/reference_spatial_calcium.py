"""Independent composition of scalar spatial and ER reference equations.

No Cells/JAX imports. The spatial reference owns transport and the Kirchhoff
solve; scalar chemical references own each cytosol/ER inventory. Their common
derivative is integrated together, including across prescribed interventions.
"""

import math
from bisect import bisect_right

import numpy as np
from scipy.integrate import solve_ivp

from tests.reference_er_calcium import System as ERSystem
from validation.betse.spatial_cluster import reference as spatial

ER_FIELDS = (
    "chemical_amount_increment",
    "reaction_extent",
    "reaction_dissipated_energy_pJ",
    "er_passive_transferred",
    "er_pump_transferred",
    "er_release_transferred",
    "er_transport_dissipated_energy_pJ",
)


class System:
    def __init__(self, raw):
        self.raw = raw
        self.ionic = {"model": raw["model"]["ionic"], "experiment": raw["experiment"]}
        self.context = spatial.bind(self.ionic)
        stores = {s["cell_id"]: s["model"] for s in raw["model"]["stores"]}
        self.cells = [c["cell"]["id"] for c in self.ionic["model"]["cells"]]
        self.stores = [ERSystem({"model": stores[c]}) for c in self.cells]
        self.controls = {c["cell_id"]: c["controls"] for c in raw["experiment"]["store_controls"]}
        self.offsets = np.cumsum([int(self.context["offsets"][-1]), *(s.size for s in self.stores)])
        self.size = int(self.offsets[-1])
        self.shapes = dict(zip(spatial.FIELDS, self.context["shapes"], strict=True))
        er = self.stores[0].unpack(np.zeros(self.stores[0].size))
        self.shapes.update(
            {name: (len(self.cells), *a.shape) for name, a in zip(ER_FIELDS, er, strict=True)}
        )

    def initial(self):
        return np.r_[spatial.initial(self.context), np.zeros(self.size - self.offsets[0])]

    def unpack(self, y):
        result = spatial.unpack(self.context, y[..., : self.offsets[0]])
        # Scalar states only; caller stacks requested observations.
        stores = [
            s.unpack(y[a:b])
            for s, a, b in zip(self.stores, self.offsets[:-1], self.offsets[1:], strict=True)
        ]
        result.update({name: np.stack([s[j] for s in stores]) for j, name in enumerate(ER_FIELDS)})
        return result

    def rhs(self, y, time, *, channel_levels=None):
        arrays = [y[a:b] for a, b in zip(self.offsets[:-1], self.offsets[1:], strict=True)]
        inside = np.empty_like(self.context["initial"])
        derivatives = []
        for i, (s, value) in enumerate(zip(self.stores, arrays, strict=True)):
            amount = s.n0 + s.unpack(value)[0]
            for j, ion in enumerate(self.context["ids"]):
                inside[j, i] = amount[s.ids.index(ion), s.cy]
            controls = self.controls[self.cells[i]]
            held = controls[bisect_right([c["time"] for c in controls], time) - 1]
            derivatives.append(s.rhs(value, held))
        controls = spatial.control_at(self.ionic, time)
        if channel_levels is not None:
            controls = dict(controls)
            for owner, channel in self.context["channels"]:
                key = (channel["id"], "schedule")
                controls[key] = dict(controls[key])
                controls[key]["availability"] *= channel_levels[owner]
        external = spatial.rhs(
            self.context,
            controls,
            y[: self.offsets[0]],
            inside_amount=inside,
            coupled_field=getattr(self, "coupled_field", None),
        )
        influx = spatial.unpack(self.context, external)["amount_increment"]
        for i, (s, rates) in enumerate(zip(self.stores, derivatives, strict=True)):
            chemistry = s.unpack(rates)[0]
            for j, ion in enumerate(self.context["ids"]):
                chemistry[s.ids.index(ion), s.cy] += influx[j, i]
        return np.concatenate((external, *derivatives))

    def flatten_actual(self, values):
        """Field views for comparing active coordinates without padded slots."""
        return {
            k: np.asarray(values[k])[(..., *(slice(0, size) for size in shape))]
            for k, shape in self.shapes.items()
        }


def reference(raw, requested, *, method="DOP853", channel_segments=None, system_class=System):
    system = system_class(raw)
    nodes = {0.0, raw["experiment"]["end_time"]}
    for kind in ("membrane", "channel", "junction"):
        for group in raw["experiment"][kind + "_controls"]:
            for name in ("leak", "pump") if kind == "membrane" else ("schedule",):
                nodes.update(p["time"] for p in group[name])
    for controls in system.controls.values():
        nodes.update(c["time"] for c in controls)
    nodes.update(getattr(system, "extra_times", ()))
    if channel_segments is not None:
        nodes.update(t for t, _ in channel_segments if 0 <= t <= raw["experiment"]["end_time"])
    times = np.asarray(requested)
    value = system.initial()
    output = np.empty((len(times), system.size))
    nodes = sorted(nodes)
    calls = 0
    for start, end in zip(nodes[:-1], nodes[1:], strict=True):
        levels = (
            None
            if channel_segments is None
            else channel_segments[bisect_right([s[0] for s in channel_segments], start) - 1][1]
        )

        def evaluate(t, y, start=start, levels=levels):
            nonlocal calls
            calls += 1
            if calls > 300000:
                raise ValueError("Spatial calcium reference RHS budget exceeded")
            return system.rhs(y, start, channel_levels=levels)

        solution = solve_ivp(
            evaluate,
            (start, end),
            value,
            method=method,
            rtol=2e-13,
            atol=2e-17,
            max_step=0.00005,
            dense_output=True,
        )
        if not solution.success or not np.isfinite(solution.y).all():
            raise ValueError("Independent spatial calcium integration failed")
        selected = (times >= start) & (times <= end)
        if np.any(selected):
            output[selected] = solution.sol(times[selected]).T
        value = solution.y[:, -1]
    rows = [system.unpack(v) for v in output]
    return {k: np.stack([r[k] for r in rows]) for k in system.shapes} | {"rhs_calls": calls}


def physical_energy_derivative(system, y, dy):
    """Direct potentials times rates, separately from production integral ledgers."""
    state, rates = system.unpack(y), system.unpack(dy)
    c = system.context
    value = 0.0
    for i, s in enumerate(system.stores):
        amount = s.n0 + state["chemical_amount_increment"][i]
        potential = s.mu0[:, None] + np.log(amount / (s.volume * s.c0))
        value += 1e-3 * s.rt * np.sum(potential * rates["chemical_amount_increment"][i])
        voltage = s.membrane["initial_voltage_V"] + spatial.F * 1e-15 / s.cap * math.fsum(
            s.z * state["chemical_amount_increment"][i, :, s.er]
        )
        value += (
            1e12
            * voltage
            * spatial.F
            * 1e-15
            * math.fsum(s.z * rates["chemical_amount_increment"][i, :, s.er])
        )
    co = (c["outside_initial"] + state["extracellular_amount_increment"]) / c["outside_volume"]
    value += 1e-3 * c["rt"] * np.sum(np.log(co) * rates["extracellular_amount_increment"])
    voltage = spatial.voltage(c, state["amount_increment"])
    value += (
        1e12
        * spatial.F
        * 1e-15
        * np.sum(voltage * np.sum(c["z"][:, None] * rates["amount_increment"], axis=0))
    )
    return float(value)
