"""Independent scalar polynomial/constant-field ODE and pinned native functions.

No Cells or JAX imports. Reference integrates increments to avoid loss of small
charge changes on the large potassium pool; rates and scatter are scalar loops.
"""

import ast
import hashlib
import math
import os
from bisect import bisect_right
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

R = 6.02214076e23 * 1.380649e-23
F = 6.02214076e23 * 1.602176634e-19
NATIVE_HASHES = {
    "sim_toolbox.py": "d94b50e8c0fdcee28b6b301c493ffa5aaf42b18e87ea4750483e164a3bdcacec",
    "endo_retic.py": "14a989709bd22558f557b7177bd7728c8bf02b5711e0306a3673833812a848f8",
}


def native_functions():
    root = Path(
        os.environ.get("CELLS_ER_NATIVE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0/betse/science")
    )
    result = {}
    for name, expected in NATIVE_HASHES.items():
        path = root / name
        if not path.exists() and name == "endo_retic.py":
            path = root / "organelles" / name
        source = path.read_bytes()
        if hashlib.sha256(source).hexdigest() != expected:
            raise ValueError("Pinned BETSE source changed: " + str(path))
        tree = ast.parse(source)
        if name == "sim_toolbox.py":
            function = next(
                n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "pumpCaER"
            )
        else:
            owner = next(
                n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "EndoRetic"
            )
            function = next(
                n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "channels"
            )
        namespace = {"np": np}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        result[function.name] = namespace[function.name]
    return result


class System:
    def __init__(self, raw):
        m = raw["model"]
        self.species = sorted(m["species"], key=lambda s: s["id"])
        self.compartments = sorted(m["compartments"], key=lambda c: c["id"])
        self.reactions = sorted(m["reactions"], key=lambda r: r["id"])
        self.ids = [s["id"] for s in self.species]
        self.owners = [c["id"] for c in self.compartments]
        self.n0 = np.array(
            [[c["initial_amount_fmol"][s] for c in self.compartments] for s in self.ids]
        )
        self.volume = np.array([c["volume_pL"] for c in self.compartments])
        self.mu0 = np.array([s["standard_mu_RT"] for s in self.species])
        self.z = np.array([s["valence"] for s in self.species])
        self.c0 = m["standard_concentration_mM"]
        self.rt = R * m["temperature_K"]
        self.membrane = m["membrane"]
        self.cy = self.owners.index(self.membrane["cytosol"])
        self.er = self.owners.index(self.membrane["er"])
        self.ca = self.ids.index(self.membrane["calcium_species"])
        self.cap = self.membrane["area_m2"] * self.membrane["specific_capacitance_F_per_m2"]
        self.nr = len(self.reactions)
        self.size = self.n0.size + 2 * self.nr + len(self.ids) + 5

    def unpack(self, y):
        ns, nr = len(self.ids), self.nr
        i = self.n0.size
        return (
            y[:i].reshape(self.n0.shape),
            y[i : i + nr],
            y[i + nr : i + 2 * nr],
            y[i + 2 * nr : i + 2 * nr + ns],
            y[i + 2 * nr + ns : i + 2 * nr + ns + 1],
            y[i + 2 * nr + ns + 1 : i + 2 * nr + ns + 2],
            y[-3:],
        )

    def rhs(self, y, controls):
        delta = self.unpack(y)[0]
        amount = self.n0 + delta
        if np.any(amount <= 0):
            raise ValueError("Independent ER reference left positive domain")
        c = amount / self.volume
        voltage = self.membrane["initial_voltage_V"] + F * 1e-15 / self.cap * math.fsum(
            self.z * delta[:, self.er]
        )
        derivative = np.zeros_like(amount)
        extents, energies = [], []
        for r in self.reactions:
            owner = self.owners.index(r["compartment"])
            dmu = math.fsum(
                (r["products"].get(s, 0) - r["reactants"].get(s, 0)) * self.mu0[i]
                for i, s in enumerate(self.ids)
            )
            factor = (
                self.volume[owner]
                * self.c0
                * r["forward_rate_per_s"]
                * controls["reactions"][r["id"]]
            )
            forward = factor * math.prod(
                (c[self.ids.index(s), owner] / self.c0) ** n for s, n in r["reactants"].items()
            )
            reverse = (
                factor
                * math.exp(dmu)
                * math.prod(
                    (c[self.ids.index(s), owner] / self.c0) ** n for s, n in r["products"].items()
                )
            )
            rate = forward - reverse
            affinity = -dmu
            for i, s in enumerate(self.ids):
                nu = r["products"].get(s, 0) - r["reactants"].get(s, 0)
                derivative[i, owner] += nu * rate
                affinity -= nu * math.log(c[i, owner] / self.c0)
            extents.append(rate)
            energies.append(1e-3 * self.rt * rate * affinity)
        mu = self.rt * np.log(c[:, self.er] / c[:, self.cy]) + self.z * F * voltage

        def flux(i, permeability):
            x = self.z[i] * F * voltage / self.rt
            # Independent Taylor expansion through sixth order at zero voltage.
            if abs(x) < 1e-3:
                b = 1 - x / 2 + x * x / 12 - x**4 / 720 + x**6 / 30240
            else:
                b = x / math.expm1(x)
            return (
                self.membrane["area_m2"]
                * permeability
                / 1e-15
                * (c[i, self.cy] * b - c[i, self.er] * (b + x))
            )

        leak = [
            flux(i, self.membrane["permeability_m_per_s"][s] * controls["passive"][s])
            for i, s in enumerate(self.ids)
        ]
        pump, energy = 0.0, 0.0
        p = self.membrane["pump"]
        if p is not None:
            drive = p["delta_g0_J_per_mol"] + self.rt * math.log(
                p["adp_mM"] * p["pi_mM"] / p["atp_mM"]
            )
            energy = drive + mu[self.ca]
            pump = (
                p["capacity_fmol_per_s"]
                * controls["pump"]
                * c[self.ca, self.cy]
                / (p["km_ca_mM"] + c[self.ca, self.cy])
                * p["atp_mM"]
                / (p["km_atp_mM"] + p["atp_mM"])
                * (1 - math.exp(energy / self.rt))
            )
        release = 0.0
        g = self.membrane["release"]
        if g is not None:
            a = (c[self.ca, self.cy] / g["activation_mM"]) ** g["activation_n"]
            h = (c[self.ca, self.cy] / g["inhibition_mM"]) ** g["inhibition_n"]
            release = flux(
                self.ca, g["permeability_m_per_s"] * controls["release"] * a / (1 + a) / (1 + h)
            )
        for i in range(len(self.ids)):
            rate = leak[i] + (pump + release if i == self.ca else 0.0)
            derivative[i, self.cy] -= rate
            derivative[i, self.er] += rate
        dissipation = [
            -1e-3 * math.fsum(np.asarray(leak) * mu),
            -1e-3 * pump * energy,
            -1e-3 * release * mu[self.ca],
        ]
        return np.concatenate(
            (derivative.ravel(), extents, energies, leak, [pump, release], dissipation)
        )


def reference(raw, requested, *, method="DOP853"):
    system = System(raw)
    controls = raw["experiment"]["controls"]
    switches = [p["time"] for p in controls]
    nodes = sorted({0.0, raw["experiment"]["end_time"], *switches})
    state = np.zeros(system.size)
    values = np.zeros((len(requested), system.size))
    calls = 0
    for start, end in zip(nodes, nodes[1:], strict=False):
        control = controls[bisect_right(switches, start) - 1]

        def rhs(t, y, control=control):
            return system.rhs(y, control)

        solution = solve_ivp(
            rhs,
            (start, end),
            state,
            method=method,
            rtol=2e-13,
            atol=2e-17,
            max_step=0.00005,
            dense_output=True,
        )
        if not solution.success:
            raise ValueError(solution.message)
        calls += solution.nfev
        mask = (np.asarray(requested) >= start) & (np.asarray(requested) <= end)
        values[mask] = solution.sol(np.asarray(requested)[mask]).T
        state = solution.y[:, -1]
    rows = [system.unpack(y) for y in values]
    return {
        name: np.stack([row[i] for row in rows])
        for i, name in enumerate(
            (
                "amount_increment",
                "reaction_extent",
                "dissipated_energy_pJ",
                "passive_transferred",
                "pump_transferred",
                "release_transferred",
                "transport_dissipated_energy_pJ",
            )
        )
    } | {"rhs_calls": calls}
