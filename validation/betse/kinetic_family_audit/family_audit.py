"""Independent saved-number review of the bounded SPEC-010 family acceptance.

Stdlib-only decoder and Decimal physics. No Cells/BETSE/NumPy/JAX/SciPy imports,
no ODE solves, no mutation of the original capture or production sources.
"""

import argparse
import contextlib
import hashlib
import importlib.abc
import math
import signal
import sys
import time
import traceback
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from pathlib import Path
from xml.etree import ElementTree as ET

from artifacts import decode_npz, digest, flatten, near, read, require, sha, write

ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "runs/spec-010-family-2026-09-16/acceptance-01"
COMPLETION_SHA = "0901fb6ce8facddf4701bd32534d361fef60832c8dbf8427b0aaeab2aa26eb1f"
REGISTRATION_SHA = "112c7158956bbfdffe57a44a122097dddf8babbcac1461b66e4722c52b7aa01d"
REFERENCE = ROOT / "runs/num-011-kinetic-pump-2026-09-16/candidate-01"
REFERENCE_SHA = "57df709995d155139e20f026dbdd40bd37b417e9cbc8c182586ae8ecf681cbcb"
F, R = 96485.33212331001, 8.31446261815324
FIELDS = (
    "amount_increment",
    "leak_transferred",
    "pump_cycles",
    "dissipated_energy_pJ",
    "gate",
    "channel_transferred",
    "junction_gate",
    "junction_transferred",
    "junction_dissipated_energy_pJ",
    "extracellular_amount_increment",
)
FORBIDDEN = (
    "cells",
    "betse",
    "numpy",
    "scipy",
    "jax",
    "jaxlib",
    "coupled_reference",
    "coupled_candidate",
    "coupled_compare",
    "coupled_audit",
    "kinetic_finite_fixtures",
)


@contextlib.contextmanager
def fence():
    def forbidden(name):
        return any(name == p or name.startswith(p + ".") for p in FORBIDDEN)

    require(not any(forbidden(n) for n in sys.modules), "Model already imported")

    class Fence(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path, target=None):
            if forbidden(fullname):
                raise ImportError("Forbidden in independent review: " + fullname)
            return None

    finder = Fence()
    sys.meta_path.insert(0, finder)
    try:
        yield
        require(not any(forbidden(n) for n in sys.modules), "Review imported model")
    finally:
        sys.meta_path.remove(finder)


def authenticated():
    require(sha(CAPTURE / "completion.json") == COMPLETION_SHA, "Family completion changed")
    require(sha(CAPTURE / "registration.json") == REGISTRATION_SHA, "Family registration changed")
    done, r = read(CAPTURE / "completion.json"), read(CAPTURE / "registration.json")
    require(
        done["status"] == "family_checks_pass_pending_review"
        and not (CAPTURE / "failure.json").exists(),
        "Family attempt did not pass",
    )
    require(
        len(r["sources_sha256"]) == 601 and len(done["files_sha256"]) == 292, "Capture coverage"
    )
    require(
        all(sha(CAPTURE / n) == h for n, h in done["files_sha256"].items()),
        "Changed family payload",
    )
    # New audit/preflight files are outside this old manifest; its 601 captured
    # bytes and complete production inventory must remain identical.
    require(
        all(sha(ROOT / n) == h for n, h in r["sources_sha256"].items()), "Captured source changed"
    )
    production = {
        n.removeprefix("src/cells/"): h
        for n, h in r["sources_sha256"].items()
        if n.startswith("src/cells/")
    }
    require(
        set(production)
        == {str(p.relative_to(ROOT / "src/cells")) for p in (ROOT / "src/cells").rglob("*.py")}
        and len(production) == 55,
        "Production inventory changed",
    )
    with zipfile.ZipFile(CAPTURE / "sources.zip") as archive:
        require(
            len(archive.namelist()) == 601
            and set(archive.namelist()) == r["sources_sha256"].keys(),
            "Source capsule members",
        )
        require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes",
        )
    for name, count in (("family", 74), ("regression", 348)):
        suites = ET.parse(CAPTURE / f"{name}.xml").getroot().findall("testsuite")
        rows = [c for s in suites for c in s.findall("testcase")]
        require(len(rows) == sum(int(s.attrib["tests"]) for s in suites) == count, "JUnit coverage")
        require(
            all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped"))
            and all(c.find(k) is None for c in rows for k in ("failure", "error", "skipped")),
            "Nonpassing JUnit",
        )
    require(
        sha(REFERENCE / "completion.json") == REFERENCE_SHA, "Independent reference capture changed"
    )
    prior = read(REFERENCE / "completion.json")
    require(
        all(sha(REFERENCE / n) == h for n, h in prior["files_sha256"].items()),
        "Reference payload changed",
    )
    require(
        read(REFERENCE / "registration.json")["protocol"]["constants"] == {"F": F, "R": R},
        "Constants changed",
    )
    return r, production


def values(arrays, name):
    return arrays[name]["values"]


def state_at(arrays, index, prefix=""):
    return {name: values(arrays, prefix + name)[index] for name in FIELDS}


def canonical(state, n):
    return (
        [state["amount_increment"][s][i] for i in range(n) for s in range(3)]
        + [state["extracellular_amount_increment"][s][0] for s in range(3)]
        + [state["leak_transferred"][s][i] for i in range(n) for s in range(3)]
        + state["pump_cycles"][:n]
        + state["dissipated_energy_pJ"][:n]
    )


def definition_matches(definition, case, step, times):
    m, e, x = (definition[k] for k in ("model", "experiment", "execution"))
    n = len(case["volume_pL"])
    require(
        definition["schema_version"] == 1 and m["id"] == "finite_extracellular@2", "Wrong family"
    )
    require(
        [(s["id"], s["valence"]) for s in m["species"]]
        == list(zip(case["species"], case["valence"], strict=True)),
        "Species mapping",
    )
    require(
        m["temperature_K"] == case["temperature_K"]
        and len(m["cells"]) == n
        and m["junctions"] == [],
        "Geometry scope",
    )
    require(
        e["end_time"] == 0.01
        and e["observation_times"] == times
        and e["channel_controls"] == e["junction_controls"] == [],
        "Observation/control scope",
    )
    require(
        x
        == dict(
            dt=step,
            jit=True,
            capacity=3,
            membrane_capacity=4,
            channel_capacity=2,
            edge_capacity=2,
            extracellular_capacity=2,
            backend="cpu",
            precision="float64",
            solver="rk4",
            max_steps=10000,
            max_trace_bytes=2**28,
            material_balance_atol_fmol=dict.fromkeys(case["species"], 2e-11),
        ),
        "Execution changed",
    )

    def amounts(concentrations, volume):
        return dict(zip(case["species"], [v * volume for v in concentrations], strict=True))

    require(
        m["extracellular"]
        == dict(
            id="outside",
            volume_pL=case["outside_volume_pL"],
            initial_amount_fmol=amounts(case["initial_outside_mM"], case["outside_volume_pL"]),
            fixed_charge_equivalent_fmol=case["fixed_outside_charge_fmol"],
        ),
        "Outside preparation",
    )
    for i, entry in enumerate(m["cells"]):
        require(
            entry["cell"]
            == dict(
                id=f"cell_{i}",
                volume_pL=case["volume_pL"][i],
                initial_amount_fmol=amounts(case["initial_inside_mM"][i], case["volume_pL"][i]),
                initial_voltage_V=case["initial_voltage_V"][i],
                fixed_charge_equivalent_fmol=case["fixed_inside_charge_fmol"][i],
            ),
            "Cell preparation",
        )
        p = dict(
            id=f"pump_{i}",
            law="nak_atp_mass_action_positive@1",
            roles={"sodium": "Na", "potassium": "K"},
            stoichiometry={"Na": -3, "K": 2},
            capacity_fmol_per_s=case["area_m2"][i] * case["alpha_mol_m2_s"][i] * 1e15,
            **{k: case[k][i] for k in ("km_na_mM", "km_k_mM", "km_atp_mM")},
            metabolism=dict(
                kind="maintained_chemical_reservoirs@1",
                **{k: case[k][i] for k in ("atp_mM", "adp_mM", "pi_mM")},
                delta_g0_J_per_mol=case["delta_g0_J_mol"][i],
            ),
        )
        expected = dict(
            id=f"membrane_{i}",
            inside=f"cell_{i}",
            outside="outside",
            area_m2=case["area_m2"][i],
            specific_capacitance_F_per_m2=case["specific_capacitance_F_m2"][i],
            passive={
                "law": "constant_field@1",
                "permeability_m_per_s": dict(
                    zip(case["species"], case["permeability_m_s"][i], strict=True)
                ),
            },
            pump=p,
        )
        require(
            entry["membrane"] == expected and entry["channel"] is None, "Membrane/pump preparation"
        )
        require(
            e["membrane_controls"][i]
            == dict(
                membrane_id=f"membrane_{i}",
                leak=[
                    dict(time=r["time_s"], multipliers=dict.fromkeys(case["species"], r["leak"]))
                    for r in case["controls"]
                ],
                pump=[dict(time=r["time_s"], multiplier=r["pump"]) for r in case["controls"]],
            ),
            "Control changed",
        )


def check_layout(a, definition):
    """Check all retained active/padded numeric fields against declared geometry."""
    m, x = definition["model"], definition["execution"]
    entries, species = m["cells"], [s["id"] for s in m["species"]]
    n, nc, nm, no, nk, ne = (
        len(entries),
        x["capacity"],
        x["membrane_capacity"],
        x["extracellular_capacity"],
        x["channel_capacity"],
        x["edge_capacity"],
    )
    expected = {}
    for mask, ids, count, capacity in (
        ("active", "ids", n, nc),
        ("membrane_active", "membrane_ids", n, nm),
        ("extracellular_active", "extracellular_ids", 1, no),
        ("channel_active", "channel_ids", 0, nk),
        ("junction_active", "junction_ids", 0, ne),
    ):
        expected[mask] = [i < count for i in range(capacity)]
        expected[ids] = [i + 1 if i < count else -1 for i in range(capacity)]
    for name, capacity in (("owners", nm), ("cell_membranes", nc)):
        expected[name] = list(range(n)) + [0] * (capacity - n)
    for name, capacity in (
        ("outside_owners", nm),
        ("channel_membranes", nk),
        ("channel_species", nk),
        ("senders", ne),
        ("receivers", ne),
    ):
        expected[name] = [0] * capacity
    expected.update(
        species_codes=[1, 2, 3],
        valence=[[s["valence"]] for s in m["species"]],
        temperature=[m["temperature_K"]] * no,
        channel_laws=[-1] * nk,
        pump_present=[i < n for i in range(nm)],
        pump_sodium_species=[0] * nm,
        pump_potassium_species=[1] * n + [0] * (nm - n),
    )
    for name, capacity, default in (
        ("volume", nc, 1.0),
        ("voltage_reference", nc, 0.0),
        ("fixed_charge_equivalent", nc, 0.0),
        ("area", nm, 1.0),
        ("specific_capacitance", nm, 1.0),
        ("capacitance", nm, 1.0),
        ("pump_capacity", nm, 0.0),
        ("pump_drive", nm, 0.0),
        ("channel_permeability", nk, 0.0),
        ("channel_abundance", nk, 0.0),
        ("junction_area", ne, 1.0),
        ("junction_sensitivity", ne, 1.0),
        ("junction_half_voltage", ne, 0.0),
        ("junction_tau", ne, 1.0),
        ("extracellular_volume", no, 1.0),
        ("extracellular_fixed_charge_equivalent", no, 0.0),
    ):
        expected[name] = [default] * capacity
    for name, capacity in (
        ("amount_reference", nc),
        ("extracellular_amount_reference", no),
        ("permeability", nm),
        ("junction_permeability", ne),
        ("junction_residual", ne),
        ("stoichiometry", nm),
    ):
        expected[name] = [[0] * capacity for _ in species]
    for name in ("atp_mM", "adp_mM", "pi_mM", "km_na_mM", "km_k_mM", "km_atp_mM", "delta_g0_J_mol"):
        expected["pump_" + name] = [
            0.0 if name == "delta_g0_J_mol" else 1000.0 if name == "pi_mM" else 1.0
        ] * nm
    for i, entry in enumerate(entries):
        c, p = entry["cell"], entry["membrane"]
        pump, pools = p["pump"], p["pump"]["metabolism"]
        for name, v in (
            ("volume", c["volume_pL"]),
            ("voltage_reference", c["initial_voltage_V"]),
            ("fixed_charge_equivalent", c["fixed_charge_equivalent_fmol"]),
            ("area", p["area_m2"]),
            ("specific_capacitance", p["specific_capacitance_F_per_m2"]),
            ("capacitance", p["area_m2"] * p["specific_capacitance_F_per_m2"]),
            ("pump_capacity", pump["capacity_fmol_per_s"]),
        ):
            expected[name][i] = v
        for name in ("atp_mM", "adp_mM", "pi_mM", "km_na_mM", "km_k_mM", "km_atp_mM"):
            expected["pump_" + name][i] = (pools if name in pools else pump)[name]
        expected["pump_delta_g0_J_mol"][i] = pools["delta_g0_J_per_mol"]
        expected["pump_drive"][i] = pools["delta_g0_J_per_mol"] + R * m["temperature_K"] * math.log(
            pools["adp_mM"] * pools["pi_mM"] / (1000 * pools["atp_mM"])
        )
        for s, name in enumerate(species):
            expected["amount_reference"][s][i] = c["initial_amount_fmol"][name]
            expected["permeability"][s][i] = p["passive"]["permeability_m_per_s"][name]
            expected["stoichiometry"][s][i] = pump["stoichiometry"].get(name, 0)
    outside = m["extracellular"]
    expected["extracellular_volume"][0] = outside["volume_pL"]
    expected["extracellular_fixed_charge_equivalent"][0] = outside["fixed_charge_equivalent_fmol"]
    for s, name in enumerate(species):
        expected["extracellular_amount_reference"][s][0] = outside["initial_amount_fmol"][name]
    expected["initial_countercharge_C"] = math.fsum(
        [
            F
            * 1e-15
            * math.fsum(
                [
                    outside["fixed_charge_equivalent_fmol"],
                    *(s["valence"] * outside["initial_amount_fmol"][s["id"]] for s in m["species"]),
                ]
            ),
            *(
                e["membrane"]["area_m2"]
                * e["membrane"]["specific_capacitance_F_per_m2"]
                * e["cell"]["initial_voltage_V"]
                for e in entries
            ),
        ]
    )
    for name, value in expected.items():
        found = values(a, "cell_ids" if name == "ids" and "cell_ids" in a else name)
        if name == "pump_drive":
            near(found, value)
        else:
            require(found == value, "Saved layout differs: " + name)
    return expected


def physics(definition, state):
    """60-digit extensive entropy/chemical and capacitor energy accounting."""
    with localcontext() as ctx:
        ctx.prec = 60
        d = Decimal
        m = definition["model"]
        n = len(m["cells"])
        z = [d(s["valence"]) for s in m["species"]]
        species = [s["id"] for s in m["species"]]
        rt, qf = d(R) * d(m["temperature_K"]), d(F) * d("1e-15")
        q, o, leak = (
            state[k]
            for k in ("amount_increment", "extracellular_amount_increment", "leak_transferred")
        )
        ledgers = [
            [d(leak[s][i]) + (-3, 2, 0)[s] * d(state["pump_cycles"][i]) for s in range(3)]
            for i in range(n)
        ]
        local = [abs(d(q[s][i]) - ledgers[i][s]) for i in range(n) for s in range(3)]
        external = [abs(d(o[s][0]) + sum(row[s] for row in ledgers)) for s in range(3)]
        global_error = [abs(d(o[s][0]) + sum(d(q[s][i]) for i in range(n))) for s in range(3)]
        energy, work, voltage, ci = d(0), d(0), [], []
        for i, compartment in enumerate([e["cell"] for e in m["cells"]] + [m["extracellular"]]):
            volume = d(compartment["volume_pL"])
            concentrations = []
            for s, name in enumerate(species):
                n0 = d(compartment["initial_amount_fmol"][name])
                dn = d(q[s][i] if i < n else o[s][0])
                amount = n0 + dn
                require(amount > 0, "Saved inventory depleted")
                concentrations.append(amount / volume)
                energy += (
                    d(".001")
                    * rt
                    * (amount * (amount / volume).ln() - n0 * (n0 / volume).ln() - dn)
                )
            ci.append(concentrations)
            if i < n:
                membrane = m["cells"][i]["membrane"]
                cap = d(membrane["area_m2"]) * d(membrane["specific_capacitance_F_per_m2"])
                q0 = cap * d(compartment["initial_voltage_V"])
                dq = qf * sum(z[s] * d(q[s][i]) for s in range(3))
                v = (q0 + dq) / cap
                voltage.append(v)
                require(all(abs(zs * d(F) * v / rt) <= 50 for zs in z), "Saved voltage domain")
                energy += ((q0 + dq) ** 2 - q0**2) / (2 * cap) * d("1e12")
                pools = membrane["pump"]["metabolism"]
                drive = (
                    d(pools["delta_g0_J_per_mol"])
                    + rt
                    * (d(pools["adp_mM"]) * d(pools["pi_mM"]) / (1000 * d(pools["atp_mM"]))).ln()
                )
                work -= d(".001") * drive * d(state["pump_cycles"][i])
        affinities = []
        for i, entry in enumerate(m["cells"]):
            pools = entry["membrane"]["pump"]["metabolism"]
            a = (
                d(pools["delta_g0_J_per_mol"]) / rt
                + (
                    d(pools["adp_mM"])
                    * d(pools["pi_mM"])
                    / (1000 * d(pools["atp_mM"]))
                    * (ci[-1][0] / ci[i][0]) ** 3
                    * (ci[i][1] / ci[-1][1]) ** 2
                ).ln()
                - d(F) * voltage[i] / rt
            )
            require(abs(a) <= 80, "Saved pump affinity domain")
            affinities.append(float(a))
        qinitial = (
            d(m["extracellular"]["fixed_charge_equivalent_fmol"])
            + sum(
                z[s] * d(m["extracellular"]["initial_amount_fmol"][name])
                for s, name in enumerate(species)
            )
        ) * qf
        qinitial += sum(
            d(e["membrane"]["area_m2"])
            * d(e["membrane"]["specific_capacitance_F_per_m2"])
            * d(e["cell"]["initial_voltage_V"])
            for e in m["cells"]
        )
        charge = qinitial + qf * sum(
            z[s] * (d(o[s][0]) + sum(d(q[s][i]) for i in range(n))) for s in range(3)
        )
        residual = energy + sum(d(v) for v in state["dissipated_energy_pJ"]) - work
        return dict(
            local_material_fmol=float(max(local)),
            outside_material_fmol=float(max(external)),
            global_material_fmol=float(max(global_error)),
            countercharge_C=float(abs(charge)),
            energy_pJ=float(abs(residual)),
            voltage_V=list(map(float, voltage)),
            affinity_over_RT=affinities,
            work_pJ=float(work),
            min_concentration_mM=float(min(flatten(ci))),
        )


def validate_state(state, n):
    for name, shape in (
        ("amount_increment", [3, 3]),
        ("leak_transferred", [3, 4]),
        ("pump_cycles", [4]),
        ("dissipated_energy_pJ", [4]),
        ("gate", [2, 2]),
        ("channel_transferred", [2]),
        ("junction_gate", [2]),
        ("junction_transferred", [3, 2]),
        ("junction_dissipated_energy_pJ", [2]),
        ("extracellular_amount_increment", [3, 2]),
    ):
        value = state[name]

        def extent(v, dimensions, name=name):
            require(type(v) is list and len(v) == dimensions[0], "State axes: " + name)
            if len(dimensions) > 1:
                for row in v:
                    extent(row, dimensions[1:])

        extent(value, shape)
        require(
            all(type(v) is float and math.isfinite(v) for v in flatten(value)), "State dtype/finite"
        )
        if name in (
            "gate",
            "channel_transferred",
            "junction_gate",
            "junction_transferred",
            "junction_dissipated_energy_pJ",
        ):
            require(all(v == 0 for v in flatten(value)), "Absent mechanism owns state")
        else:
            count = 1 if name == "extracellular_amount_increment" else n
            rows = value if len(shape) > 1 else [value]
            require(all(v == 0 for row in rows for v in row[count:]), "Nonzero padding state")


def checkpoint(directory, definition, layout, state, time_s, step, sources, runtime):
    m = read(directory / "manifest.json")
    require(
        m["manifest_sha256"] == digest({k: v for k, v in m.items() if k != "manifest_sha256"}),
        "Checkpoint manifest checksum",
    )
    starts = {
        row["time"]
        for c in definition["experiment"]["membrane_controls"]
        for key in ("leak", "pump")
        for row in c[key]
    }
    event = sum(t <= time_s for t in starts) - 1
    require(m["clock"] == dict(time=time_s, step_index=step, event_index=event), "Checkpoint clock")
    require(
        m["kind"] == "cells_complete_numerical_checkpoint"
        and m["schema_version"] == 1
        and m["random_state"] is None,
        "Checkpoint contract",
    )
    require(
        m["source_hashes"] == sources
        and m["runtime"] == runtime
        and m["spec"] == definition
        and m["spec_sha256"] == digest(definition),
        "Checkpoint identity",
    )
    require(m["state_sha256"] == sha(directory / "state.npz"), "Checkpoint state checksum")
    a = decode_npz(directory / "state.npz")
    require(set(a) == set(layout) | set(FIELDS), "Checkpoint membership")
    for name, expected in state.items():
        require(values(a, name) == expected, "Checkpoint state mismatch")
    check_layout(a, definition)
    return a


def audit():
    r, sources = authenticated()
    plan = read(REFERENCE / "registration.json")["protocol"]
    reference = read(REFERENCE / "reference.json")["results"]
    records = read(CAPTURE / "trajectory-comparisons.json")
    directories = [
        p.parent
        for p in (CAPTURE / "family-artifacts").glob("*/comparison.json")
        if not p.parent.is_symlink()
    ]
    require(len(directories) == len(records) == 12, "Trajectory coverage")
    require(
        sorted(
            (read(p / "comparison.json") for p in directories), key=lambda v: (v["case"], v["dt_s"])
        )
        == sorted(records, key=lambda v: (v["case"], v["dt_s"])),
        "Comparison aggregation",
    )
    expected = {(c["id"], step) for c in plan["cases"] for step in (0.0001, 0.00005)}
    require({(v["case"], v["dt_s"]) for v in records} == expected, "Case/step coverage")
    maxima = dict.fromkeys(
        (
            "local_material_fmol",
            "outside_material_fmol",
            "global_material_fmol",
            "countercharge_C",
            "energy_pJ",
        ),
        0.0,
    )
    summary, physical_count, comparisons, restarts, checkpoints = [], 0, 0, 0, 0
    for directory in sorted(directories):
        saved = read(directory / "comparison.json")
        case = next(c for c in plan["cases"] if c["id"] == saved["case"])
        n, step = len(case["volume_pL"]), saved["dt_s"]
        run = directory / "run"
        definition = read(run / "resolved_config.json")
        times = reference[case["id"]]["DOP853"]["times_s"]
        definition_matches(definition, case, step, times)
        manifests = {}
        for name in ("run", "resume"):
            manifest = read(directory / name / "manifest.json")
            require(
                manifest["definition_sha256"] == digest(definition)
                and manifest["source_hashes"] == sources,
                "Run identity",
            )
            require(
                manifest["runtime"]["cells_version"] == "0.16.0.dev0"
                and manifest["cpu_affinity"] == [0, 1, 2, 3],
                "Runtime/device context",
            )
            require(
                manifest["runtime"]["packages"]
                == {k: v for k, v in r["runtime"]["packages"].items() if k != "pytest"},
                "Run package context",
            )
            require(
                all(sha(directory / name / k) == h for k, h in manifest["files_sha256"].items()),
                "Run manifest payload",
            )
            require(
                read(directory / name / "resolved_config.json") == definition,
                "Resume definition changed",
            )
            manifests[name] = manifest
        a, b = decode_npz(run / "trajectory.npz"), decode_npz(directory / "resume/trajectory.npz")
        layout = check_layout(a, definition)
        require(check_layout(b, definition) == layout, "Resumed layout differs")
        native_times = values(a, "accepted_times")
        require(
            native_times == [i * step for i in range(round(0.01 / step))] + [0.01],
            "Native accepted mesh",
        )
        start = native_times.index(0.006)
        require(values(b, "accepted_times") == native_times[start:], "Restart clock suffix")
        for field in FIELDS:
            require(
                values(a, field)[start:] == values(b, field), "Restart full-state suffix mismatch"
            )
        restarts += 1
        require(values(a, "observation_times") == times, "Saved observation grid")
        require(
            values(b, "observation_times") == [t for t in times if t >= 0.006],
            "Restart observations",
        )
        require(
            all(v == 0 for field in FIELDS for v in flatten(values(a, field)[0])),
            "Initial state mismatch",
        )
        previous = [0.0] * 4
        cache = {}
        for prefix, sample_times in (("", native_times), ("observed_", times)):
            for i, t in enumerate(sample_times):
                state = state_at(a, i, prefix)
                validate_state(state, n)
                key = tuple(v for field in FIELDS for v in flatten(state[field]))
                if key not in cache:
                    cache[key] = physics(definition, state)
                physical_count += 1
                found = cache[key]
                for field in maxima:
                    limit = (
                        1e-20
                        if field == "countercharge_C"
                        else 2e-8
                        if field == "energy_pJ"
                        else 2e-11
                    )
                    require(found[field] <= limit, "Independent balance: " + field)
                    maxima[field] = max(maxima[field], found[field])
                if not prefix:
                    require(
                        all(
                            v >= -1e-10 and v + 1e-10 >= p
                            for v, p in zip(state["dissipated_energy_pJ"], previous, strict=True)
                        ),
                        "Dissipation decreased",
                    )
                    previous = state["dissipated_energy_pJ"]
                else:
                    near(values(a, "observed_voltage_V")[i][:n], found["voltage_V"], atol=1e-12)
                    near(sum(values(a, "observed_pump_work_J")[i]) * 1e12, found["work_pJ"])
                    nearest = min(range(len(native_times)), key=lambda j: abs(native_times[j] - t))
                    require(
                        abs(native_times[nearest] - t) <= 1e-15, "Panel observation not on mesh"
                    )
                    for field in FIELDS:
                        near(state[field], values(a, field)[nearest])
        for location, index in (
            (run / "checkpoint_final", len(native_times) - 1),
            (run / f"snapshots/step-{start:06d}", start),
            (directory / "resume/checkpoint_final", len(native_times) - 1),
        ):
            checkpoint(
                location,
                definition,
                layout,
                state_at(a, index),
                native_times[index],
                index,
                sources,
                manifests["run"]["runtime"],
            )
            checkpoints += 1
        scores = {}
        for method in ("DOP853", "Radau"):
            oracle = reference[case["id"]][method]["state"]
            actual = [canonical(state_at(a, i, "observed_"), n) for i in range(len(times))]
            ratios = [
                abs(x - y) / (1e-8 + 2e-7 * abs(y))
                for row, target in zip(actual, oracle, strict=True)
                for x, y in zip(row, target, strict=True)
            ]
            require(max(ratios) <= 1, "Independent trajectory reference mismatch")
            near(saved["methods"][method]["max_error_over_budget"], max(ratios), atol=1e-15)
            require(saved["methods"][method]["comparisons"] == len(ratios), "Comparison count")
            reference_voltages = [
                [
                    case["initial_voltage_V"][i]
                    + F
                    * 1e-15
                    * math.fsum(case["valence"][s] * row[3 * i + s] for s in range(3))
                    / (case["area_m2"][i] * case["specific_capacitance_F_m2"][i])
                    for i in range(n)
                ]
                for row in oracle
            ]
            voltage_error = max(
                abs(v - target)
                for row, expected_row in zip(
                    values(a, "observed_voltage_V"), reference_voltages, strict=True
                )
                for v, target in zip(row[:n], expected_row, strict=True)
            )
            require(voltage_error <= 1e-7, "Independent reference voltage mismatch")
            near(saved["methods"][method]["max_voltage_error_V"], voltage_error, atol=1e-15)
            comparisons += len(ratios)
            scores[method] = max(ratios)
        summary.append(
            dict(
                case=case["id"],
                dt_s=step,
                accepted_states=len(native_times),
                sampled_states=len(times),
                max_error_over_budget=scores,
            )
        )
    return dict(
        status="bounded_family_saved_data_review_pass",
        scope="12 pump/leak trajectories; other lifecycle features retain software-test evidence",
        comparisons=comparisons,
        physical_records=physical_count,
        restart_suffixes=restarts,
        complete_checkpoints=checkpoints,
        maxima=maxima,
        trajectories=summary,
        new_tests=74,
        regression_tests=348,
        source_inputs=601,
        production_modules=55,
        biology_validated=False,
        gpu_tested=False,
        native_betse_trajectory=False,
        full_release_matrix_run=False,
        stable_release_promoted=False,
    )


def execute(output, tests):
    require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs" and not output.exists(),
        "Use fresh audit output",
    )
    require(
        tests.is_relative_to(ROOT / "reports") and tests.is_file(), "Missing audit software receipt"
    )
    suites = ET.parse(tests).getroot().findall("testsuite")
    require(
        all(int(s.get(k, "0")) == 0 for s in suites for k in ("failures", "errors", "skipped")),
        "Audit tests failed",
    )
    require(sum(int(s.attrib["tests"]) for s in suites) >= 12, "Insufficient audit tests")
    output.mkdir(parents=True)
    start = time.monotonic()

    def deadline(_sig, _frame):
        raise TimeoutError("Bounded saved-data audit exceeded 45 seconds")

    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 45)
    try:
        inputs = {str(p.relative_to(ROOT)): sha(p) for p in Path(__file__).parent.glob("*.py")}
        write(
            output / "registration.json",
            dict(
                schema="cells.kinetic_family_saved_audit@1",
                capture=str(CAPTURE.relative_to(ROOT)),
                capture_completion_sha256=COMPLETION_SHA,
                source_sha256=inputs,
                tests=dict(path=str(tests.relative_to(ROOT)), sha256=sha(tests)),
                registered_utc=datetime.now(UTC).isoformat(),
                model_imports_forbidden=list(FORBIDDEN),
                precision_digits=60,
                timeout_seconds=45,
            ),
        )
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in inputs:
                archive.write(ROOT / name, arcname=name)
        with fence():
            result = audit()
            authenticated()
        require(all(sha(ROOT / n) == h for n, h in inputs.items()), "Audit source changed")
        write(output / "review.json", result)
        write(
            output / "completion.json",
            dict(
                status="bounded_family_independently_closed",
                elapsed_seconds=time.monotonic() - start,
                finished_utc=datetime.now(UTC).isoformat(),
                files_sha256={p.name: sha(p) for p in output.iterdir() if p.is_file()},
                **{
                    k: result[k]
                    for k in (
                        "comparisons",
                        "physical_records",
                        "restart_suffixes",
                        "complete_checkpoints",
                        "new_tests",
                        "regression_tests",
                    )
                },
                full_release_matrix_run=False,
                stable_release_promoted=False,
                biology_validated=False,
                gpu_tested=False,
            ),
        )
        print(
            {
                "status": "bounded_family_independently_closed",
                "elapsed_seconds": time.monotonic() - start,
                "completion_sha256": sha(output / "completion.json"),
            }
        )
    except BaseException:
        write(
            output / "failure.json",
            dict(status="audit_failed_not_closed", traceback=traceback.format_exc()),
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tests", type=Path, required=True)
    args = parser.parse_args()
    execute(args.output.resolve(), args.tests.resolve())
