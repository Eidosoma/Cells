"""The worlds of an inputs file, read exactly.

A world is held as plain dictionaries of Decimals. Nothing here computes a result.
"""

import hashlib
import json
from decimal import Decimal

from .arith import ONE, ZERO, exact, thermal_energy


class World:
    """One world of `inputs.json`, every declared number read as the exact value of its double."""

    def __init__(self, name, block):
        self.name = name
        self.block = block
        self.cache = {}              # this world's own propagated states (never shared between worlds)
        self.temperature = exact(block["temperature_K"])
        self.rt = thermal_energy(self.temperature)
        self.volumes = {node: exact(v) for node, v in sorted(block["volumes_pL"].items())}
        self.nodes = sorted(self.volumes)
        self.collectors = sorted(block["collectors"])
        self.species = sorted(block["start_fmol"])
        self.start = {x: {node: exact(n) for node, n in sorted(amounts.items())}
                      for x, amounts in block["start_fmol"].items()}
        self.inlets = {inlet: {x: [(exact(t), exact(c)) for t, c in schedule]
                               for x, schedule in sorted(table.items())}
                       for inlet, table in sorted(block["inlets_mM"].items())}
        self.links = [(source, target, [(exact(t), exact(q)) for t, q in schedule])
                      for source, target, schedule in block["links_pL_per_s"]]
        self.faces = [(a, b, {x: exact(p) for x, p in sorted(table.items())})
                      for a, b, table in block["faces_pL_per_s"]]
        self.events = sorted(block["events"], key=lambda e: e["time_s"])
        self.labels = block["labels"]
        self.sites = block["sites"]
        self.end = block["end_s"]
        touched = set()
        for source, target, _ in self.links:
            touched.update((source, target))
        self.flow_nodes = [node for node in self.nodes if node in touched]
        # H: the world's inlets, the nodes any link touches and its collector (CRITERIA section 1).
        self.holder_count = len(self.inlets) + len(self.flow_nodes) + len(self.collectors)
        self.species_count = len(self.species)

    # ---- outputs ------------------------------------------------------------------------------------
    def output_floats(self):
        """The listed output times as JSON floats, t = 0 first."""
        if isinstance(self.block["outputs_s"], list):
            times = self.block["outputs_s"]
        else:
            times = self.block.get("compare_s", [])
        return [0.0] + list(times)

    # ---- schedules ----------------------------------------------------------------------------------
    def switch_times(self):
        """Every time after 0 at which a link's rate or an inlet's concentration changes."""
        times = set()
        for _, _, schedule in self.links:
            times.update(t for t, _ in schedule if t > 0)
        for table in self.inlets.values():
            for schedule in table.values():
                times.update(t for t, _ in schedule if t > 0)
        return sorted(times)

    @staticmethod
    def _in_force(schedule, time):
        value = None
        for start, entry in schedule:
            if start <= time:
                value = entry
        if value is None:
            raise ValueError("a schedule does not start at 0")
        return value

    def link_rates(self, time):
        """[(source, target, Q)] in the segment that starts at `time`."""
        return [(source, target, self._in_force(schedule, time)) for source, target, schedule in self.links]

    def inlet_level(self, inlet, species, time):
        return self._in_force(self.inlets[inlet][species], time)

    # ---- scales (READOUTS section 2, LAWS section 9) -------------------------------------------------
    def start_total(self, species):
        return sum(self.start[species].values(), ZERO)

    def declared_concentrations(self):
        """Every concentration the world declares: start levels, inlets, buffers."""
        values = []
        for x in self.species:
            for node, n in sorted(self.start[x].items()):
                values.append(n / self.volumes[node])
        for inlet in sorted(self.inlets):
            for x in sorted(self.inlets[inlet]):
                values.extend(level for _, level in self.inlets[inlet][x])
        for event in self.events:
            if event["kind"] == "exchange":
                values.extend(exact(level) for _, level in sorted(event["buffer_mM"].items()))
        return values

    def largest_log(self):
        """Lambda: the largest |ln(c / 1 mM)| over the declared concentrations."""
        return max((abs(c.ln()) for c in self.declared_concentrations()), default=ZERO)

    def throughput(self, step):
        """SPEC section 1: the largest outflow x (h/2) / volume over the nodes, over every segment; 0 if none."""
        best = ZERO
        where = None
        for time in [ZERO] + self.switch_times():
            for node in self.flow_nodes:
                outflow = sum((q for source, _, q in self.link_rates(time) if source == node), ZERO)
                rho = outflow * (step / 2) / self.volumes[node]
                if rho > best:
                    best, where = rho, node
        return best, where


class Inputs:
    """An inputs file: its worlds and its runs, with the sha256 of its bytes."""

    def __init__(self, path):
        with open(path, "rb") as handle:
            data = handle.read()
        self.sha256 = hashlib.sha256(data).hexdigest()
        self.table = json.loads(data.decode("utf-8"))
        self.worlds = {name: World(name, block) for name, block in sorted(self.table["worlds"].items())}
        self.runs = self.table["runs"]

    def runs_of(self, arm=None, world=None, role=None, heat=None):
        """The runs that match, in file order."""
        chosen = []
        for run in self.runs:
            if arm is not None and run["arm"] != arm:
                continue
            if world is not None and run["world"] != world:
                continue
            if role is not None and run["role"] != role:
                continue
            if heat is not None and run["heat"] != heat:
                continue
            chosen.append(run)
        return chosen

    def worlds_of(self, arm):
        """The worlds whose own arm this is: the arm of the first run that names them in file order."""
        own = {}
        for run in self.runs:
            own.setdefault(run["world"], run["arm"])
        return sorted(name for name, first in own.items() if first == arm)

    @staticmethod
    def step(run):
        return exact(run["step"]["s"])


__all__ = ["Inputs", "World", "Decimal", "ONE", "ZERO"]
