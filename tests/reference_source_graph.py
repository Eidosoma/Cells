"""Independent fixed-graph source-coordinate composition (NUM-005a).

Reuses independently written local/constitutive equations, never Cells or BITSEY.
One local evaluation per cell; contacts accumulate through an explicit edge loop,
not production scatter or sums of complete pair RHSs. This is a reference model,
not an integrator, a new production family, or a qualified long-time assay.
"""

import copy
from dataclasses import dataclass

import numpy as np

from tests import reference_source_pair as eq
from tests.reference_emt import reference_rhs

CASE_KEYS = {
    "id",
    "origin",
    "cell_ids",
    "edge_ids",
    "edges",
    "primary",
    "context",
    "membrane_diffusion",
    "ionic_diffusion",
    "mirna_diffusion",
    "gates",
    "swap_hemichannels",
    "controls",
}
CONTROL_KEYS = {"leak", "pump", "ion_contact", "mirna_contact"}


def ids(values, name, *, nonempty=False):
    if (
        not isinstance(values, list)
        or any(type(x) is not int or x < 0 for x in values)
        or len(set(values)) != len(values)
        or (nonempty and not values)
    ):
        raise ValueError(f"Expected unique nonnegative integer {name}")
    return tuple(values)


def array(value, shape, name, *, upper=None):
    a = eq.checked_array(value, shape, name, upper=upper).copy()
    a.setflags(write=False)
    return a


@dataclass(frozen=True)
class Coordinates:
    """Typed slices in a reference interchange vector, compatible with pair N=2."""

    cells: int
    edges: int

    def __post_init__(self):
        if (
            type(self.cells) is not int
            or self.cells < 1
            or type(self.edges) is not int
            or self.edges < 0
        ):
            raise ValueError("Invalid coordinate dimensions")

    @property
    def primary(self):
        return slice(0, 6 * self.cells)

    @property
    def leak(self):
        return slice(6 * self.cells, 9 * self.cells)

    @property
    def pump(self):
        return slice(9 * self.cells, 10 * self.cells)

    @property
    def ionic(self):
        return slice(10 * self.cells, 10 * self.cells + 3 * self.edges)

    @property
    def local(self):
        return slice(10 * self.cells + 3 * self.edges, 13 * self.cells + 3 * self.edges)

    @property
    def mirna(self):
        return slice(13 * self.cells + 3 * self.edges, self.size)

    @property
    def size(self):
        return 13 * self.cells + 4 * self.edges


class Model:
    """Full-state anchor, fixed graph and one explicitly held control setting."""

    def __init__(self, case, panel=None):
        if not isinstance(case, dict) or set(case) != CASE_KEYS:
            raise ValueError("Incomplete or unknown graph-reference fields")
        self.case = copy.deepcopy(case)
        self.panel = copy.deepcopy(eq.load_panel() if panel is None else panel)
        if not all(isinstance(case[name], str) and case[name] for name in ("id", "origin")):
            raise ValueError("Graph reference requires explicit identity/origin")
        self.cell_ids = ids(case["cell_ids"], "cell IDs", nonempty=True)
        self.edge_ids = ids(case["edge_ids"], "edge IDs")
        self.n, self.e = len(self.cell_ids), len(self.edge_ids)
        self.coordinates = Coordinates(self.n, self.e)
        endpoints = case["edges"]
        if not isinstance(endpoints, list) or len(endpoints) != self.e:
            raise ValueError("Edge endpoint count differs")
        indices, seen = [], set()
        for endpoints_for_edge in endpoints:
            if (
                not isinstance(endpoints_for_edge, list)
                or len(endpoints_for_edge) != 2
                or any(type(x) is not int or x not in self.cell_ids for x in endpoints_for_edge)
                or endpoints_for_edge[0] == endpoints_for_edge[1]
            ):
                raise ValueError("Invalid edge endpoints")
            unordered = tuple(sorted(endpoints_for_edge))
            if unordered in seen:
                raise ValueError("Duplicate undirected edge")
            seen.add(unordered)
            indices.append(tuple(self.cell_ids.index(x) for x in endpoints_for_edge))
        self.edges = tuple(indices)
        self.context = array(case["context"], (3, self.n), "context")
        if np.any(self.context[1] > 1000):
            raise ValueError("Outside Snail domain")
        self.anchor = array(case["primary"], (6, self.n), "primary", upper=1000)
        self.membrane_diffusion = array(
            case["membrane_diffusion"], (3, self.n), "membrane diffusion"
        )
        self.ionic_diffusion = array(case["ionic_diffusion"], (3, self.e), "ionic diffusion")
        self.mirna_diffusion = array(case["mirna_diffusion"], (self.e,), "miRNA diffusion")
        if (
            not isinstance(case["gates"], list)
            or len(case["gates"]) != self.e
            or any(g is not None and g not in self.panel["gate_parameters"] for g in case["gates"])
        ):
            raise ValueError("Unknown or misaligned gate profiles")
        if (
            not isinstance(case["swap_hemichannels"], list)
            or len(case["swap_hemichannels"]) != self.e
            or any(type(x) is not bool for x in case["swap_hemichannels"])
        ):
            raise ValueError("Expected one boolean hemichannel swap per edge")
        self.gates = tuple(case["gates"])
        self.swaps = tuple(case["swap_hemichannels"])
        self.controls = self.checked_controls(case["controls"])
        self.area, self.volume = eq.geometry(self.panel)
        self.validate_primary(self.anchor)

    def checked_controls(self, controls):
        if not isinstance(controls, dict) or set(controls) != CONTROL_KEYS:
            raise ValueError("Incomplete or unknown graph controls")
        shapes = {
            "leak": (3, self.n),
            "pump": (self.n,),
            "ion_contact": (self.e,),
            "mirna_contact": (self.e,),
        }
        return {k: array(controls[k], shape, k, upper=1) for k, shape in shapes.items()}

    def validate_primary(self, primary):
        primary = eq.checked_array(primary, (6, self.n), "primary", upper=1000)
        if np.any(primary[:3] < 1e-6):
            raise ValueError("Outside bounded ionic domain")
        vm = eq.voltage(primary, self.context, self.panel)
        delta = np.asarray([vm[a] - vm[b] for a, b in self.edges])
        if max(np.max(abs(vm)), np.max(abs(delta), initial=0)) > 0.2:
            raise ValueError("Outside source voltage domain")
        p = self.panel["parameters"]
        if (
            max(
                np.max(abs(vm)) * p["F"] / (p["R"] * p["T"]),
                np.max(abs(delta), initial=0) * p["q"] / (p["kb"] * p["T"]),
            )
            > 50
        ):
            raise ValueError("Outside electrical exponent domain")
        return primary, vm, delta

    def evaluate(self, primary, time=0, *, controls=None):
        if not np.isfinite(time) or time < 0:
            raise ValueError("Invalid nominal time")
        primary, vm, delta = self.validate_primary(primary)
        held = self.controls if controls is None else self.checked_controls(controls)
        leak, pump, cycle = eq.membrane_flux(primary, vm, self.membrane_diffusion, held, self.panel)
        local = np.zeros((6, self.n))
        local[3:] = reference_rhs(time, primary[3:], self.context[1])
        scales, flux = np.ones((4, self.e)), np.zeros((4, self.e))
        contact = np.zeros((6, self.n))
        factor = self.area / self.volume
        for i, (a, b) in enumerate(self.edges):
            scales[:, i] = eq.gate_scales(
                delta[i], self.panel, {"gate": self.gates[i], "swap_hemichannels": self.swaps[i]}
            )
            flux[:3, i] = (
                eq.upwind_flux(
                    primary[:3], eq.Z, self.ionic_diffusion[:, i], delta[i], (a, b), self.panel
                )
                * held["ion_contact"][i]
            )
            flux[3, i] = (
                eq.upwind_flux(
                    primary[3:4], [-1.0], [self.mirna_diffusion[i]], delta[i], (a, b), self.panel
                )[0]
                * held["mirna_contact"][i]
            )
            flux[:, i] *= scales[:, i]
            contribution = flux[:, i] * factor
            contact[:4, a] -= contribution
            contact[:4, b] += contribution
        membrane = np.zeros((6, self.n))
        membrane[:3] = (leak + pump) * factor
        packet = np.zeros((len(eq.PACKET), self.n))
        packet[eq.PRIMARY_INDEX], packet[eq.CONTEXT_INDEX] = primary, self.context
        packet[8] = primary[3]
        ratio = primary[3] / 40
        packet[9:16] = primary[4] * ratio[None, :] ** np.arange(7)[:, None] / (1 + ratio) ** 6
        result = {
            "voltage": vm,
            "delta_v": delta,
            "gate_scales": scales,
            "leak_flux": leak,
            "pump_flux": pump,
            "pump_cycle_flux": cycle,
            "local_rate": local,
            "junction_flux": flux,
            "contact_rate": contact,
            "membrane_rate": membrane,
            "primary_rate": membrane + local + contact,
            "packet": packet,
        }
        if any(not np.isfinite(v).all() for v in result.values()):
            raise ValueError("Nonfinite graph readout/rate")
        return result

    def initial(self):
        return np.r_[self.anchor.ravel(), np.zeros(self.coordinates.size - 6 * self.n)]

    def derivative(self, values, *, increments=False, controls=None):
        values = np.asarray(values)
        if values.shape != (self.coordinates.size,) or not np.isfinite(values).all():
            raise ValueError("Invalid complete graph primary/history vector")
        primary = values[self.coordinates.primary].reshape(6, self.n)
        if increments:
            primary = primary + self.anchor
        r = self.evaluate(primary, controls=controls)
        factor = self.area / self.volume
        return np.r_[
            r["primary_rate"].ravel(),
            r["leak_flux"].ravel() * factor,
            r["pump_cycle_flux"] * factor,
            r["junction_flux"][:3].ravel() * factor,
            r["local_rate"][3:].ravel(),
            r["junction_flux"][3] * factor,
        ]

    def accounting(self, values):
        values = np.asarray(values)
        s = self.coordinates
        if (
            values.ndim != 2
            or values.shape[1] != s.size
            or not len(values)
            or not np.isfinite(values).all()
        ):
            raise ValueError("Invalid complete graph history array")
        predicted = np.broadcast_to(self.anchor, (len(values), 6, self.n)).copy()
        predicted[:, :3] += values[:, s.leak].reshape(-1, 3, self.n)
        predicted[:, :3] += np.array([-3.0, 2.0, 0.0])[None, :, None] * values[
            :, s.pump, None
        ].transpose(0, 2, 1)
        predicted[:, 3:] += values[:, s.local].reshape(-1, 3, self.n)
        ionic = values[:, s.ionic].reshape(len(values), 3, self.e)
        mirna = values[:, s.mirna]
        for i, (a, b) in enumerate(self.edges):
            predicted[:, :3, a] -= ionic[:, :, i]
            predicted[:, :3, b] += ionic[:, :, i]
            predicted[:, 3, a] -= mirna[:, i]
            predicted[:, 3, b] += mirna[:, i]
        error = predicted - values[:, s.primary].reshape(-1, 6, self.n)
        return {
            "ionic": float(np.max(abs(error[:, :3]))),
            "regulatory": float(np.max(abs(error[:, 3:]))),
        }


def from_pair(panel, case, time=0):
    """Freeze one existing pair control setting, without integrating or repinning."""
    primary, context = eq.initial_state(panel, case)
    held = eq.controls_at(panel, case, time)
    edge = case.get("edge", [0, 1])
    return Model(
        {
            "id": f"{case['id']}@{time:g}",
            "origin": "frozen_SPEC003_initial_state_at_control_setting",
            "cell_ids": [100, 200],
            "edge_ids": [10],
            "edges": [[100 + 100 * x for x in edge]],
            "primary": primary.tolist(),
            "context": context.tolist(),
            "membrane_diffusion": case.get("membrane_diffusion", panel["membrane_diffusion"]),
            "ionic_diffusion": [[x] for x in panel["junction_ion_diffusion"]],
            "mirna_diffusion": [panel["junction_mirna_diffusion"]],
            "gates": [case["gate"]],
            "swap_hemichannels": [case.get("swap_hemichannels", False)],
            "controls": {
                "leak": held["leak"].tolist(),
                "pump": held["pump"].tolist(),
                "ion_contact": [float(held["ion_contact"])],
                "mirna_contact": [float(held["mirna_contact"])],
            },
        },
        panel,
    )
