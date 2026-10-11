"""D038 bounded graph readouts; no production imports or integration changes.

Batch the observation axis only. Preserve edge accumulation order and the
scalar equation expressions; static cache construction never consumes state.
"""

import hashlib
import json
from time import perf_counter
from types import MappingProxyType

import numpy as np

from tests import reference_candidate_comparison as original
from tests import reference_source_graph as graph

ref, prep, paths = original.ref, original.prep, original.paths
REVISION = "bounded_graph_readouts@1"
POLICIES = ("scalar_frozen", "batched_cached")


def fingerprint(readouts):
    result = hashlib.sha256()
    for key in sorted(readouts):
        value = readouts[key]
        result.update(json.dumps([key, value.dtype.str, value.shape]).encode())
        result.update(value.tobytes())
    return result.hexdigest()


def estimate_array_bytes(samples, cells, edges):
    """Conservative scratch/output estimate; not a hard process RSS limit."""
    return 8 * ((samples + 1) * (160 * cells + 64 * edges) + 64 * cells + 32 * edges)


class BatchedReadouts:
    def __init__(self, model, *, max_samples=256, array_budget_bytes=268435456):
        if type(max_samples) is not int or not 1 <= max_samples <= 256:
            raise ValueError("Invalid readout batch capacity")
        if type(array_budget_bytes) is not int or array_budget_bytes <= 0:
            raise ValueError("Invalid readout array budget")
        if not isinstance(model, graph.Model):
            raise ValueError("Expected a validated fixed graph model")
        self.estimated_array_bytes = estimate_array_bytes(
            max_samples, len(model.case["cell_ids"]), len(model.case["edges"])
        )
        if self.estimated_array_bytes > array_budget_bytes:
            raise ref.BudgetExceeded("Readout working array estimate exceeds budget")
        # Snapshot and validate independently of later edits to the caller's
        # dictionaries. The numerical cache contains only immutable arrays and
        # scalars; it must not silently track a changed graph/control setting.
        snapshot = graph.Model(model.case, model.panel)
        self.n, self.e, self.size = snapshot.n, snapshot.e, snapshot.coordinates.size
        self.max_samples, self.array_budget_bytes = max_samples, array_budget_bytes
        self.p = MappingProxyType(dict(snapshot.panel["parameters"]))
        self.anchor, self.context = snapshot.anchor, snapshot.context
        self.edges = snapshot.edges
        self.diffusion, self.ionic_diffusion = snapshot.membrane_diffusion, snapshot.ionic_diffusion
        self.mirna_diffusion = snapshot.mirna_diffusion
        self.controls = MappingProxyType(snapshot.controls)
        self.area, self.volume = snapshot.area, snapshot.volume
        self.factor = self.area / self.volume
        self.bath = np.asarray(snapshot.panel["bath_ions"], dtype=np.float64)
        self.bath.setflags(write=False)
        self.gates = tuple(
            None if name is None else tuple(snapshot.panel["gate_parameters"][name])
            for name in snapshot.gates
        )
        self.swaps = snapshot.swaps
        self.cache_identity = original.candidate.digest(
            {"case": snapshot.case, "panel": snapshot.panel}
        )
        self.diffusion_over_tm = self.diffusion / self.p["tm"]
        self.pump_enabled = np.any(self.diffusion > 0, axis=0)
        self.diffusion_over_tm.setflags(write=False)
        self.pump_enabled.setflags(write=False)

    def _batch(self, values, tail, name):
        if (
            not isinstance(values, np.ndarray)
            or values.dtype != np.float64
            or values.ndim != 1 + len(tail)
            or values.shape[1:] != tail
        ):
            raise ValueError(f"Expected float64 {name} with explicit batch and semantic axes")
        if not 1 <= len(values) <= self.max_samples:
            raise ValueError("Readout batch exceeds registered capacity or is empty")
        if not np.isfinite(values).all():
            raise ValueError(f"Nonfinite {name}")
        return values

    def evaluate(self, primary):
        primary = self._batch(primary, (6, self.n), "primary")
        if np.any(primary < 0) or np.any(primary > 1000) or np.any(primary[:, :3] < 1e-6):
            raise ValueError("Outside bounded primary domain")
        p, batch = self.p, len(primary)
        vm = (
            (np.matmul(graph.eq.Z, primary[:, :3]) - self.context[0])
            * p["F"]
            * self.volume
            / (self.area * p["cm"])
        )
        delta = np.empty((batch, self.e))
        for i, (left, right) in enumerate(self.edges):
            delta[:, i] = vm[:, left] - vm[:, right]
        if max(np.max(abs(vm)), np.max(abs(delta), initial=0)) > 0.2:
            raise ValueError("Outside source voltage domain")
        if (
            max(
                np.max(abs(vm)) * p["F"] / (p["R"] * p["T"]),
                np.max(abs(delta), initial=0) * p["q"] / (p["kb"] * p["T"]),
            )
            > 50
        ):
            raise ValueError("Outside electrical exponent domain")

        x = graph.eq.Z[None, :, None] * vm[:, None] * (p["F"] / (p["R"] * p["T"])) + 1e-25
        bernoulli_negative = x / -np.expm1(-x)
        leak = (
            self.diffusion_over_tm
            * bernoulli_negative
            * (self.bath[None, :, None] * np.exp(-x) - primary[:, :3])
            * self.controls["leak"]
        )
        nai, ki = primary[:, 0], primary[:, 1]
        nao, ko = self.bath[:2]
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
            * self.controls["pump"]
            * self.pump_enabled
        )
        pump = np.array([-3.0, 2.0, 0.0])[None, :, None] * cycle[:, None]
        local = np.zeros((batch, 6, self.n))
        local[:, 3:] = graph.reference_rhs(
            0, primary[:, 3:].transpose(1, 0, 2), self.context[1]
        ).transpose(1, 0, 2)
        scales, flux = np.ones((batch, 4, self.e)), np.zeros((batch, 4, self.e))
        contact = np.zeros((batch, 6, self.n))
        for i, (left, right) in enumerate(self.edges):
            if self.gates[i] is not None:
                a1, v1, a2, v2, residual, maximum = self.gates[i]
                if self.swaps[i]:
                    a1, v1, a2, v2 = a2, v2, a1, v1
                opening = 1 / (
                    1 + np.exp(a1 * (-delta[:, i] - v1)) + np.exp(a2 * (delta[:, i] - v2))
                )
                scales[:, :3, i] = (residual + (maximum - residual) * opening)[:, None]
                scales[:, 3, i] = maximum * opening
            ion_x = graph.eq.Z * p["q"] * delta[:, i, None] / (p["kb"] * p["T"])
            ion_donor = np.where(ion_x >= 0, primary[:, :3, left], primary[:, :3, right])
            flux[:, :3, i] = (
                self.ionic_diffusion[:, i]
                / p["GJ_len"]
                * (primary[:, :3, left] - primary[:, :3, right] + ion_x * ion_donor)
                * self.controls["ion_contact"][i]
            )
            mir_x = -1.0 * p["q"] * delta[:, i] / (p["kb"] * p["T"])
            mir_donor = np.where(mir_x >= 0, primary[:, 3, left], primary[:, 3, right])
            flux[:, 3, i] = (
                self.mirna_diffusion[i]
                / p["GJ_len"]
                * (primary[:, 3, left] - primary[:, 3, right] + mir_x * mir_donor)
                * self.controls["mirna_contact"][i]
            )
            flux[:, :, i] *= scales[:, :, i]
            contribution = flux[:, :, i] * self.factor
            contact[:, :4, left] -= contribution
            contact[:, :4, right] += contribution
        membrane = np.zeros_like(local)
        membrane[:, :3] = (leak + pump) * self.factor
        packet = np.zeros((batch, len(graph.eq.PACKET), self.n))
        packet[:, graph.eq.PRIMARY_INDEX], packet[:, graph.eq.CONTEXT_INDEX] = primary, self.context
        packet[:, 8] = primary[:, 3]
        ratio = primary[:, 3] / 40
        packet[:, 9:16] = (
            primary[:, 4, None]
            * ratio[:, None] ** np.arange(7)[None, :, None]
            / (1 + ratio[:, None]) ** 6
        )
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
        if any(not np.isfinite(value).all() for value in result.values()):
            raise ValueError("Nonfinite graph readout/rate")
        return result

    def observed(self, increments):
        increments = self._batch(increments, (self.size,), "complete increments")
        primary = increments[:, : 6 * self.n].reshape(-1, 6, self.n) + self.anchor
        r = self.evaluate(primary)
        return {
            "voltage": r["voltage"],
            "gate_scale": r["gate_scales"],
            "membrane_and_junction_flux": np.concatenate(
                [
                    r[k].reshape(len(increments), -1)
                    for k in ("leak_flux", "pump_flux", "junction_flux")
                ],
                axis=1,
            ),
            "binding_cache": r["packet"][:, graph.eq.DERIVED_INDEX],
            "packet": r["packet"],
            "primary_rhs": r["primary_rate"],
        }


def readout_scores(actual, expected, tolerances):
    mapping = {
        "voltage": "voltage",
        "gate_scale": "gate_scales",
        "membrane_and_junction_flux": "junction_flux",
        "binding_cache": "packet",
        "packet": "packet",
        "primary_rhs": "primary_rate",
    }
    if set(actual) != set(mapping) or set(expected) != set(mapping):
        raise ValueError("Readout field inventory differs")
    scores = {}
    for key, target in mapping.items():
        a, b = actual[key], expected[key]
        if (
            a.shape != b.shape
            or a.dtype != np.float64
            or b.dtype != np.float64
            or not np.isfinite(a).all()
            or not np.isfinite(b).all()
        ):
            raise ValueError("Readout shape/precision/values differ")
        tol = tolerances[target]
        scores[key] = float(np.max(abs(a - b) / (tol["atol"] + tol["rtol"] * abs(b)), initial=0))
    return scores


class Comparison(original.Comparison):
    """Explicit per-instance readout policy; never patch the frozen module globals."""

    def __init__(self, *args, policy, **kwargs):
        if policy not in POLICIES:
            raise ValueError("Unknown diagnostic policy")
        super().__init__(*args, **kwargs)
        self.policy = policy
        self.readout_seconds = self.fingerprint_seconds = self.cache_seconds = 0.0
        self.readout_batches = 0

    def open(self, start_tick, grid, guard):
        super().open(start_tick, grid, guard)
        begun = perf_counter()
        self.cached = (
            BatchedReadouts(
                self.model,
                max_samples=self.resources["window_steps"],
                array_budget_bytes=self.resources["estimated_array_budget_bytes"],
            )
            if self.policy == "batched_cached"
            else None
        )
        self.cache_seconds = perf_counter() - begun

    def consume(self, data):
        # Keep the frozen source's grid, scoring and recording operation order.
        # The only numerical substitution is this instance's readout evaluator.
        width = self.resources["window_steps"]
        while self.next_time is not None and self.next_time <= data["times"][-1]:
            self.guard()
            batch = []
            while (
                self.next_time is not None
                and self.next_time <= data["times"][-1]
                and len(batch) < width
            ):
                batch.append(self.next_time)
                self.next_time = next(self.times, None)
            times = np.asarray(batch, dtype=np.float64)
            states = {"candidate": original.candidate.sample_window(data, times)}
            states.update({key: reader.sample(times) for key, reader in self.readers.items()})
            begun = perf_counter()
            readouts = {
                key: self.cached.observed(value)
                if self.cached is not None
                else prep.observed(self.model, value)
                for key, value in states.items()
            }
            self.readout_seconds += perf_counter() - begun
            self.readout_batches += len(states)
            for value in states.values():
                self.residual = max(
                    self.residual, float(np.max(abs(ref.residual(self.model, value))))
                )
                if np.any(value[:, ref.blocked_coordinates(self.model)] != 0):
                    raise ValueError("Blocked comparison history changed")
            for key in self.readers:
                scores = prep.comparison_scores(
                    self.model,
                    states["candidate"],
                    states[key],
                    readouts["candidate"],
                    readouts[key],
                    self.selected["numerics"]["targets"],
                )
                for quantity, score in scores.items():
                    if not np.isfinite(score):
                        raise ValueError("Nonfinite candidate comparison score")
                    self.scores[key][quantity] = max(self.scores[key].get(quantity, 0), score)
            begun = perf_counter()
            readout_hashes = {key: fingerprint(value) for key, value in readouts.items()}
            self.fingerprint_seconds += perf_counter() - begun
            phase = perf_counter()
            flags = np.isin(times, self.observers)
            arrays = {"times": times, "observer": flags, **states}
            path = self.folder / f"chunk-{self.chunks:06d}.npz"
            paths.save_arrays(path, arrays, self.root, self.resources["artifact_budget_bytes"])
            with (self.folder / "chunks.jsonl").open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "path": path.name,
                            "sha256": ref.sha(path),
                            "samples": len(times),
                            "start": float(times[0]),
                            "end": float(times[-1]),
                            "readout_hashes": readout_hashes,
                        },
                        sort_keys=True,
                        allow_nan=False,
                    )
                    + "\n"
                )
            self.samples += len(times)
            self.chunks += 1
            self.observer_samples += int(flags.sum())
            self.raw_array_bytes += sum(value.nbytes for value in arrays.values())
            self.last = float(times[-1])
            self.recording_seconds += perf_counter() - phase

    def finish(self):
        result = super().finish()
        ref.write_json(
            self.folder / "diagnostics.json",
            {
                "revision": REVISION,
                "policy": self.policy,
                "readout_seconds": self.readout_seconds,
                "readout_batches": self.readout_batches,
                "readout_evaluations": result["derived_readout_evaluations"],
                "cache_seconds": self.cache_seconds,
                "fingerprint_seconds": self.fingerprint_seconds,
                "cache_identity": self.cached.cache_identity if self.cached is not None else None,
                "readout_array_estimate_bytes": 0
                if self.cached is None
                else self.cached.estimated_array_bytes,
                "evaluation_hashes_retained_per_batch": True,
                "integration_policy_changed": False,
            },
        )
        return result
