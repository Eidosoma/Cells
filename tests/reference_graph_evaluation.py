"""D041 immutable fixed-control scalar evaluation; no production or solver changes."""

import json
from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType

import numpy as np

from tests import reference_comparison_evidence as recording
from tests import reference_source_graph as graph

eq = graph.eq
REVISION = "prepared_scalar_graph@1"
POLICIES = ("scalar_frozen", "scalar_cached")


def immutable(value):
    if isinstance(value, dict):
        return MappingProxyType({key: immutable(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(immutable(item) for item in value)
    if isinstance(value, np.ndarray):
        # Bytes-backed buffers cannot be made writable through setflags.
        return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
    return value


def estimate_array_bytes(cells, edges):
    """Conservative additional model/cache/scratch estimate, not a hard RSS bound."""
    return 8 * (512 * cells + 256 * edges + 128)


@dataclass
class _Timing:
    calls: int = 0
    seconds: float = 0.0


@dataclass(frozen=True, init=False, eq=False)
class PreparedModel:
    """Read-only numerical snapshot; changed controls require a new model/identity."""

    def __init__(self, model, *, policy, array_budget_bytes=268435456):
        begun = perf_counter()
        if policy not in POLICIES:
            raise ValueError("Unknown integration evaluation policy")
        if not isinstance(model, graph.Model):
            raise ValueError("Expected a validated fixed graph model")
        estimate = estimate_array_bytes(len(model.case["cell_ids"]), len(model.case["edges"]))
        if type(array_budget_bytes) is not int or array_budget_bytes <= 0:
            raise ValueError("Invalid integration evaluation array budget")
        if estimate > array_budget_bytes:
            raise recording.ref.BudgetExceeded("Integration evaluation arrays exceed budget")
        snapshot = graph.Model(model.case, model.panel)
        for name, value in vars(snapshot).items():
            if name != "case":
                object.__setattr__(self, name, immutable(value))
        object.__setattr__(self, "_case_json", json.dumps(snapshot.case, sort_keys=True))
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "estimated_array_bytes", estimate)
        object.__setattr__(
            self,
            "cache_identity",
            recording.runner.digest({"case": snapshot.case, "panel": snapshot.panel}),
        )
        p = self.panel["parameters"]
        snail = (self.context[1] / 72) ** 2
        constants = (
            {
                "_factor": self.area / self.volume,
                "_bath": np.asarray(self.panel["bath_ions"], dtype=np.float64),
                "_diffusion_over_tm": self.membrane_diffusion / p["tm"],
                "_pump_enabled": np.any(self.membrane_diffusion > 0, axis=0),
                "_ionic_over_len": self.ionic_diffusion / p["GJ_len"],
                "_mirna_over_len": self.mirna_diffusion / p["GJ_len"],
                "_snail_mir": 6 * (1 + 0.4 * snail) / (1 + snail),
                "_snail_mrna": (5 / 12) * (1 + 10 * snail) / (1 + snail),
            }
            if policy == "scalar_cached"
            else {}
        )
        for name, value in constants.items():
            object.__setattr__(self, name, immutable(value))
        object.__setattr__(self, "_timing", _Timing())
        object.__setattr__(self, "preparation_seconds", perf_counter() - begun)

    @property
    def case(self):
        return json.loads(self._case_json)

    @property
    def identity(self):
        return {"revision": REVISION, "policy": self.policy, "model_sha256": self.cache_identity}

    validate_primary = graph.Model.validate_primary
    checked_controls = graph.Model.checked_controls
    initial = graph.Model.initial
    accounting = graph.Model.accounting

    def receipt(self):
        return {
            **self.identity,
            "rhs_calls": self._timing.calls,
            "rhs_seconds": self._timing.seconds,
            "preparation_seconds": self.preparation_seconds,
            "estimated_array_bytes": self.estimated_array_bytes,
            "stage_and_curve_checks_changed": False,
            "state_dependent_values_cached": False,
        }

    def evaluate(self, primary, time=0, *, controls=None):
        if controls is not None:
            raise ValueError("Changed controls require a new prepared model")
        if self.policy == "scalar_frozen":
            return graph.Model.evaluate(self, primary, time)
        return self._evaluate_cached(primary, time)

    def derivative(self, values, *, increments=False, controls=None):
        begun = perf_counter()
        if (
            not isinstance(values, np.ndarray)
            or values.dtype != np.float64
            or values.shape != (self.coordinates.size,)
            or not np.isfinite(values).all()
            or type(increments) is not bool
        ):
            raise ValueError("Expected finite float64 complete vector and explicit coordinate mode")
        if controls is not None:
            raise ValueError("Changed controls require a new prepared model")
        if self.policy == "scalar_frozen":
            result = graph.Model.derivative(self, values, increments=increments)
        else:
            primary = values[self.coordinates.primary].reshape(6, self.n)
            if increments:
                primary = primary + self.anchor
            r = self.evaluate(primary)
            factor = self._factor
            # All six coordinate blocks, with the frozen multiplication ordering.
            result = np.concatenate(
                (
                    r["primary_rate"].ravel(),
                    r["leak_flux"].ravel() * factor,
                    r["pump_cycle_flux"] * factor,
                    r["junction_flux"][:3].ravel() * factor,
                    r["local_rate"][3:].ravel(),
                    r["junction_flux"][3] * factor,
                )
            )
        if result.shape != values.shape or not np.isfinite(result).all():
            raise ValueError("Nonfinite or incomplete prepared RHS")
        self._timing.calls += 1
        self._timing.seconds += perf_counter() - begun
        return result

    def _membrane_flux(self, primary, vm):
        p, bath, controls = self.panel["parameters"], self._bath, self.controls
        x = eq.Z[:, None] * vm * (p["F"] / (p["R"] * p["T"])) + 1e-25
        bernoulli_negative = x / -np.expm1(-x)
        leak = (
            self._diffusion_over_tm
            * bernoulli_negative
            * (bath[:, None] * np.exp(-x) - primary[:3])
            * controls["leak"]
        )
        nai, ki = primary[:2]
        nao, ko = bath[:2]
        omega = (p["cADP"] * p["cPi"] / p["cATP"]) * 1e-3 * (nao / nai) ** 3 * (ki / ko) ** 2
        reverse_ratio = omega * np.exp((p["deltaGATP"] - p["F"] * vm) / (p["R"] * p["T"]))
        sat_na = (nai / p["KmNK_Na"]) ** 3
        sat_k = (ko / p["KmNK_K"]) ** 2
        sat_atp = p["cATP"] / p["KmNK_ATP"]
        cycle = (
            p["alpha_NaK"]
            * (sat_na / (1 + sat_na))
            * (sat_k / (1 + sat_k))
            * (sat_atp / (1 + sat_atp))
            * (1 - reverse_ratio)
            * controls["pump"]
            * self._pump_enabled
        )
        pump = np.array([-3.0, 2.0, 0.0])[:, None] * cycle
        return leak, pump, cycle

    def _local_rhs(self, state):
        mir, mrna, protein = state
        z3 = (protein * 9 / 100) ** 3
        z2 = (protein * 9 / 25) ** 2
        r = mir / 40
        translation_polynomial = (
            1 + 3 * r + 3 * r**2 + 0.4 * r**3 + 0.3 * r**4 + 0.12 * r**5 + 0.02 * r**6
        )
        return np.array(
            [
                self._snail_mir * (1 + 0.1 * z3) / (1 + z3) - 0.05 * mir,
                self._snail_mrna * (1 + 15 * z2) / (1 + z2) - 0.5 * mrna,
                (mrna / 6) * translation_polynomial / (1 + r) ** 6 - 0.1 * protein,
            ]
        )

    def _upwind(self, values, valence, diffusion_over_len, delta, edge):
        p = self.panel["parameters"]
        left, right = edge
        x = np.asarray(valence) * p["q"] * delta / (p["kb"] * p["T"])
        donor = np.where(x >= 0, values[:, left], values[:, right])
        return diffusion_over_len * (values[:, left] - values[:, right] + x * donor)

    def _evaluate_cached(self, primary, time):
        if not np.isfinite(time) or time < 0:
            raise ValueError("Invalid nominal time")
        primary, vm, delta = self.validate_primary(primary)
        held = self.controls
        leak, pump, cycle = self._membrane_flux(primary, vm)
        local = np.zeros((6, self.n))
        local[3:] = self._local_rhs(primary[3:])
        scales, flux = np.ones((4, self.e)), np.zeros((4, self.e))
        contact = np.zeros((6, self.n))
        factor = self._factor
        for i, (a, b) in enumerate(self.edges):
            scales[:, i] = eq.gate_scales(
                delta[i], self.panel, {"gate": self.gates[i], "swap_hemichannels": self.swaps[i]}
            )
            flux[:3, i] = (
                self._upwind(primary[:3], eq.Z, self._ionic_over_len[:, i], delta[i], (a, b))
                * held["ion_contact"][i]
            )
            flux[3, i] = (
                self._upwind(primary[3:4], [-1.0], self._mirna_over_len[i], delta[i], (a, b))[0]
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


def integrate(model, output, *, comparison, **kwargs):
    """Qualify evaluator identity and aggregate allocation before frozen execution."""
    if not isinstance(model, PreparedModel):
        raise ValueError("An explicit prepared evaluator is required")
    if kwargs["identity"].get("integration_evaluation") != model.identity:
        raise ValueError("Integration evaluation identity differs")
    resources = kwargs["resources"]
    width = resources["window_steps"]
    if type(width) is not int or not 1 <= width <= 256:
        raise ValueError("Invalid evaluation window width")
    estimate = (
        recording.estimate_array_bytes(width, model.coordinates.size, model.n)
        + model.estimated_array_bytes
    )
    if estimate > resources["estimated_array_budget_bytes"]:
        raise recording.ref.BudgetExceeded(
            "Aggregate evaluation and recording arrays exceed budget"
        )
    return recording.integrate(model, output, comparison=comparison, **kwargs)
