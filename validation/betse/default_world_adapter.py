#!/usr/bin/env python3
"""BETSE's default world in Cells backends, written in the comparison layout.

``betse_world`` maps one plain-BETSE extraction (``betse_reference_extract.py``) to
named physical quantities with units, independent of any backend; ``WORLD_UNITS``
says which BETSE array feeds which quantity. Backends:

* ``emulator``: validation/betse/emulator, BETSE's own update order. With BETSE's
  constants it should reproduce BETSE to roundoff; it attributes differences.
* ``resolved``: ``resolved_definition`` builds resolved_pump_tissue@1 inputs
  (cells, outside nodes, patches, junctions, faces, ring reservoirs at 0 V), or
  resolved_pump_tissue@2 when the ion profile enables Ca and BETSE's Ca-ATPase
  runs (alpha_Ca > 0): every patch then also carries a ca_atp_mass_action_positive@1
  pump.

Each run is INIT then SIM. SIM starts from BETSE's init_final.npz (``--sim-start
betse``, the default, so SIM errors exclude INIT errors) or from the backend's own
INIT end state (``chained``). Results are written with cells_betse_compare's
``write_layout``: one sample per completed update (sample k = state after k + 1
updates), the phase end state, BETSE's element and ion order, and the protocol and
geometry sha256 fixed before the run.

    python3 validation/betse/default_world_adapter.py snapshot --out RUN/source
    PYTHONPATH=RUN/source/src:RUN/source python3 -B \\
        RUN/source/validation/betse/default_world_adapter.py run \\
        --case CASE --protocol P.json --constants betse --device cpu --out RUN/layout
    python3 validation/betse/default_world_adapter.py compare-layouts \\
        --a LAYOUT_A --b LAYOUT_B --protocol P.json --out DIR
    python3 validation/betse/default_world_adapter.py resolved-definition \\
        --case CASE --phase init --dt 1e-3 --out FILE.json
    ... run --dt-factor F --sim-start chained ...      (emulator at BETSE's dt / F)
    ... run --model-difference NAME ...   (one Cells-model difference on, e.g. ecm_drift_off)
    ... difference-budget --case CASE --pair NAME BASE OTHER ... --out FILE.json
    ... betse-step-term --dense CASE --fine CASE --out FILE.json  (plain BETSE vs BETSE)
    ... snapshot --engine --out RUN/source; ... run-resolved --case CASE --device gpu --out DIR
    ... layout-differences --a LAYOUT_A --b LAYOUT_B --out FILE.json   (e.g. CPU vs L4)

Relative ``--out`` paths resolve against $CELLS_OUTPUT_ROOT.
"""

import argparse
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import betse_reference_run as reference_run  # noqa: E402
from validation.betse import cells_betse_compare as compare  # noqa: E402

PHASES = ("init", "sim")
# Sources a run executes, frozen by ``snapshot`` (checkout path -> same snapshot path).
EXECUTED = (
    "src/cells/__init__.py",
    "src/cells/processes/__init__.py",
    "src/cells/processes/electrochemistry.py",
    "src/cells/processes/junction_gate.py",
    "src/cells/processes/kinetic_pump.py",
    "src/cells/processes/er_calcium.py",
    "src/cells/processes/plasma_calcium.py",
    "src/cells/processes/voltage_gates.py",
    "validation/source_snapshot.py",
    "validation/betse/default_world_adapter.py",
    "validation/betse/cells_betse_compare.py",
    "validation/betse/betse_reference_run.py",
    "validation/betse/betse_reference_extract.py",
    "validation/betse/emulator/laws.py",
    "validation/betse/emulator/spatial.py",
    "validation/betse/emulator/active.py",
    "validation/betse/emulator/junction.py",
    "validation/betse/protocols/emulator_default_world.json",
    "validation/betse/protocols/emulator_default_world_dense.json",
    "validation/betse/protocols/default_world_dense_example.json",
    "validation/betse/protocols/emulator_default_world_mammal_dense.json",
)

# Backend-neutral quantity -> (units, BETSE source). Per-phase entries hold one value
# per phase; "params" are BETSE Parameters attributes from the extract manifest.
WORLD_UNITS = {
    "species": ("-", "manifest ions.order (BETSE ion index order)"),
    "valence": ("1", "manifest ions.valence"),
    "cell_volume_m3": ("m^3", "geometry cell_vol"),
    "membrane_area_m2": ("m^2", "geometry mem_sa (membrane length * cell_height)"),
    "membrane_cell": ("index", "geometry mem_to_cells"),
    "membrane_site": ("index", "geometry map_mem2ecm (row-major ECM grid point)"),
    "membrane_partner": ("index", "geometry nn_i (self = cluster boundary, no junction)"),
    "junction_weight": ("1", "geometry gj_default_weights"),
    "grid_shape": ("sites", "geometry X.shape (rows, cols)"),
    "grid_spacing_m": ("m", "geometry delta"),
    "cell_height_m": ("m", "params cell_height"),
    "site_volume_m3": ("m^3", "cell_height * delta^2 (BETSE ECM square)"),
    "ring_sites": ("index", "grid edge rows/cols, reset to c_env_bound each step"),
    "temperature_K": ("K", "params T"),
    "capacitance_F_m2": ("F/m^2", "params cm"),
    "membrane_permeability_m_s": ("m/s", "{phase}_final Dm_cells / params tm (constant)"),
    "junction_permeability_m_s": ("m/s", "D_gj * params gj_surface / geometry gj_len"),
    "env_diffusivity_m2_s": ("m^2/s", "{phase}_final D_env (species, grid points)"),
    "boundary_concentration_mM": ("mol/m^3 = mM", "final_state scalars c_env_bound"),
    "pump_capacity_fmol_s": ("fmol cycles/s", "params alpha_NaK * mem_sa * 1e15"),
    "pump_atp_mM": ("mM", "params cATP"),
    "pump_adp_mM": ("mM", "params cADP"),
    "pump_pi_mM": ("mM", "params cPi"),
    "pump_km_na_mM": ("mM", "params KmNK_Na"),
    "pump_km_k_mM": ("mM", "params KmNK_K"),
    "pump_km_atp_mM": ("mM", "params KmNK_ATP"),
    "pump_delta_g0_J_mol": ("J/mol", "params deltaGATP"),
    "calcium_pump": (
        "-",
        "None, or (ions_dict Ca and alpha_Ca > 0) the Ca-ATPase of sim.py ca_handler: "
        "capacity_fmol_s = alpha_Ca * mem_sa * 1e15; km_ca_mM, km_atp_mM = KmCa_Ca, KmCa_ATP; "
        "delta_g_mM_quotient_J_mol = deltaGATP, which pumpCaATP uses with a numeric-mM ATP "
        "quotient (the Na/K pump's quotient is molar); pools cATP, cADP, cPi",
    ),
    "gate_threshold_V": ("V", "params gj_vthresh (mV) * 1e-3"),
    "gate_minimum_open": ("1", "params gj_min"),
    "permittivity_F_m": ("F/m", "params er * eo"),
    "cell_size_ratio": ("1", "params cell_radius / true_cell_size"),
    "q_over_kb_C_K_J": ("C K/J", "params q / kb"),
    "debye_prefactor": ("1/(m^2 mM)", "params NAv q^2 z^2 / (er eo kb T), per species"),
    "betse_faraday_C_mol": ("C/mol", "params F"),
    "betse_gas_J_mol_K": ("J/(mol K)", "params R"),
    "initial_cell_mM": ("mM", "params cell_concs (INIT start; t = 0 is not saved)"),
    "initial_env_mM": ("mM", "params env_concs (INIT start)"),
    "dt_s": ("s", "params dt of the phase"),
    "steps": ("updates", "manifest time.<phase>.n_steps"),
}
# BETSE switches the mapping does not represent; the extraction must show these values.
REQUIRED_PARAMS = {
    "is_ecm": True,
    "sharpness": 1.0,
    "fast_update_ecm": False,
    "cluster_open": True,
    "cell_polarizability": 0.0,
    "fluid_flow": False,
    "deformation": False,
    "Ca_dyn": False,
    "molecules_enabled": False,
    "grn_enabled": False,
    "dynamic_noise": False,
    "v_sensitive_gj": True,
    "gj_flux_sensitive": False,
}
REQUIRED_SCALARS = {"NaKATP_block": 1, "gj_block": 1}


class AdapterError(ValueError):
    """The BETSE case is outside what this adapter maps; nothing is run."""


def _npz(path, keys=None):
    with np.load(path, allow_pickle=False) as data:
        return {k: data[k] for k in (data.files if keys is None else keys)}


def load_case(path):
    """(extract dir, manifest) of a verified BETSE extraction (case or extract dir)."""
    return compare.load_betse(path)


def betse_parameters(manifest, phase):
    """BETSE Parameters of a phase: the extract's simple attributes and its keyed table."""
    simple = manifest["parameters"]["all_simple_attributes"][phase]
    keyed = {k: v["value"] for k, v in manifest["parameters"]["key"][phase].items()}
    for name in set(simple) & set(keyed):
        if simple[name] != keyed[name]:
            raise AdapterError(f"{phase}: parameter {name} differs between extract tables")
    return simple | keyed


def _blind_case(path):
    """Manifest and the two input files a blind run reads, checked against the manifest."""
    directory = compare.betse_extract_dir(path)
    manifest = json.loads((directory / "manifest.json").read_text())
    for name in ("geometry.npz", "init_final.npz"):
        if reference_run.sha256_file(directory / name) != manifest["files"][name]["sha256"]:
            raise AdapterError(f"{name}: file sha256 differs from the extract manifest")
    return directory, manifest


def betse_world(path, *, blind=False):
    """Backend-neutral physical inputs of one BETSE default-world case (see WORLD_UNITS).

    ``blind`` reads no BETSE history or end-state observable: only the manifest,
    geometry.npz and the parameter arrays Dm_cells, D_env and D_gj of init_final.npz
    (their constancy over both phases is checked by non-blind reads). SIM must then
    continue from the backend's own INIT end.
    """
    directory, manifest = _blind_case(path) if blind else load_case(path)
    params = {phase: betse_parameters(manifest, phase) for phase in PHASES}
    scalars = {p: manifest["final_state"][p]["scalars"] for p in PHASES}
    for phase in PHASES:
        for name, value in REQUIRED_PARAMS.items():
            if params[phase].get(name) != value:
                raise AdapterError(f"{phase}: BETSE {name}={params[phase].get(name)!r}")
        for name, value in REQUIRED_SCALARS.items():
            if scalars[phase].get(name) != value:
                raise AdapterError(f"{phase}: BETSE {name}={scalars[phase].get(name)!r}")
        if any(v != 0 for v in scalars[phase]["bound_V"].values()):
            raise AdapterError("nonzero global boundary voltages are not mapped")
    p = params["init"]
    geometry = _npz(directory / "geometry.npz")
    if blind:
        inputs = _npz(directory / "init_final.npz", ("Dm_cells", "D_env", "D_gj"))
        finals = {phase: inputs for phase in PHASES}
    else:
        finals = {phase: _npz(directory / f"{phase}_final.npz") for phase in PHASES}
    ions = manifest["ions"]
    species = list(ions["order"])
    valence = np.asarray(ions["valence"], dtype=np.float64)
    if scalars["init"]["movingIons"] != list(range(len(species))):
        raise AdapterError("every BETSE ion must be a moving ion")
    for name in ("D_env", "D_gj"):
        if not np.array_equal(finals["init"][name], finals["sim"][name]):
            raise AdapterError(f"{name} changes between INIT and SIM")
    if scalars["init"]["c_env_bound"] != scalars["sim"]["c_env_bound"]:
        raise AdapterError("c_env_bound changes between INIT and SIM")
    membrane_permeability = {}
    for phase in PHASES:
        dm = finals[phase]["Dm_cells"]
        if not blind:
            history = _npz(directory / f"{phase}_history.npz", ["dd_time"])["dd_time"]
            if not np.all(history == dm[None]):
                raise AdapterError(f"{phase}: Dm_cells is not constant (channels or events)")
        membrane_permeability[phase] = dm / p["tm"]
    rows, cols = (int(v) for v in geometry["X"].shape)
    k = np.arange(rows * cols)
    ring = np.flatnonzero((k // cols == 0) | (k % cols == 0) | (k // cols == rows - 1))
    ring = np.union1d(ring, np.flatnonzero(k % cols == cols - 1))
    area = np.asarray(geometry["mem_sa"], dtype=np.float64)
    debye = p["NAv"] * p["q"] ** 2 * valence**2 / (p["er"] * p["eo"] * p["kb"] * p["T"])
    world = {
        "case": manifest.get("source_run", {}).get("case"),
        "extract": str(directory),
        "geometry_sha256": manifest["files"]["geometry.npz"]["sha256"],
        "species": species,
        "valence": valence,
        "cell_volume_m3": np.asarray(geometry["cell_vol"], dtype=np.float64),
        "membrane_area_m2": area,
        "membrane_cell": np.asarray(geometry["mem_to_cells"], dtype=np.int64),
        "membrane_site": np.asarray(geometry["map_mem2ecm"], dtype=np.int64),
        "membrane_partner": np.asarray(geometry["nn_i"], dtype=np.int64),
        "junction_weight": np.asarray(geometry["gj_default_weights"], dtype=np.float64),
        "grid_shape": (rows, cols),
        "grid_spacing_m": float(geometry["delta"]),
        "cell_height_m": float(p["cell_height"]),
        "site_volume_m3": float(p["cell_height"]) * float(geometry["delta"]) ** 2,
        "ring_sites": ring,
        "temperature_K": float(p["T"]),
        "capacitance_F_m2": float(p["cm"]),
        "membrane_permeability_m_s": membrane_permeability,
        "junction_permeability_m_s": finals["init"]["D_gj"]
        * p["gj_surface"]
        / float(geometry["gj_len"]),
        "env_diffusivity_m2_s": np.asarray(finals["init"]["D_env"], dtype=np.float64),
        "boundary_concentration_mM": np.asarray(scalars["init"]["c_env_bound"], dtype=float),
        "pump_capacity_fmol_s": p["alpha_NaK"] * area * 1e15,
        "pump_atp_mM": float(p["cATP"]),
        "pump_adp_mM": float(p["cADP"]),
        "pump_pi_mM": float(p["cPi"]),
        "pump_km_na_mM": float(p["KmNK_Na"]),
        "pump_km_k_mM": float(p["KmNK_K"]),
        "pump_km_atp_mM": float(p["KmNK_ATP"]),
        "pump_delta_g0_J_mol": float(p["deltaGATP"]),
        "calcium_pump": _calcium_pump(p, species, area),
        "gate_threshold_V": float(p["gj_vthresh"]) * 1e-3,
        "gate_minimum_open": float(p["gj_min"]),
        "permittivity_F_m": float(p["er"]) * float(p["eo"]),
        "cell_size_ratio": float(p["cell_radius"]) / float(p["true_cell_size"]),
        "q_over_kb_C_K_J": float(p["q"]) / float(p["kb"]),
        "debye_prefactor": debye,
        "betse_faraday_C_mol": float(p["F"]),
        "betse_gas_J_mol_K": float(p["R"]),
        "initial_cell_mM": np.asarray([p["cell_concs"][s] for s in species], dtype=float),
        "initial_env_mM": np.asarray([p["env_concs"][s] for s in species], dtype=float),
        "dt_s": {phase: float(params[phase]["dt"]) for phase in PHASES},
        "steps": {phase: int(manifest["time"][phase]["n_steps"]) for phase in PHASES},
        "betse_ko_env": {phase: float(scalars[phase]["ko_env"]) for phase in PHASES},
        "time": {phase: manifest["time"][phase] for phase in PHASES},
        "init_final": None
        if blind
        else {
            "cell_mM": finals["init"]["cc_cells"],
            "membrane_mM": finals["init"]["cc_at_mem"],
            "env_mM": finals["init"]["cc_env"],
            "gate_open": finals["init"]["gjopen"],
        },
    }
    _check_world(world)
    return world


def _calcium_pump(p, species, area):
    """BETSE's plasma-membrane Ca-ATPase on every membrane, or None.

    sim.py runs ca_handler when the ion profile enables Ca (the extraction then
    lists a Ca ion) and pumps when alpha_Ca > 0.
    """
    enabled = p.get("ions_dict", {}).get("Ca", int("Ca" in species))
    if bool(enabled) != ("Ca" in species):
        raise AdapterError("ions_dict and the extracted ion order disagree on Ca")
    if "Ca" not in species or not float(p["alpha_Ca"]) > 0:
        return None
    return {
        "capacity_fmol_s": float(p["alpha_Ca"]) * area * 1e15,
        "km_ca_mM": float(p["KmCa_Ca"]),
        "km_atp_mM": float(p["KmCa_ATP"]),
        "atp_mM": float(p["cATP"]),
        "adp_mM": float(p["cADP"]),
        "pi_mM": float(p["cPi"]),
        "delta_g_mM_quotient_J_mol": float(p["deltaGATP"]),
    }


def _check_world(w):
    n, m, s = w["cell_volume_m3"].size, w["membrane_area_m2"].size, len(w["species"])
    partner = w["membrane_partner"]
    if not np.array_equal(partner[partner], np.arange(m)):
        raise AdapterError("gap-junction partners are not reciprocal")
    if np.any(w["junction_weight"] != w["junction_weight"][partner]):
        raise AdapterError("gap-junction weights are not reciprocal")
    if set(np.unique(w["membrane_cell"])) != set(range(n)):
        raise AdapterError("a cell has no membrane")
    if w["junction_permeability_m_s"].shape != (s, m):
        raise AdapterError("D_gj is not (ions, membranes)")
    ring = set(w["ring_sites"].tolist())
    if any(int(k) in ring for k in w["membrane_site"]):
        raise AdapterError("a membrane faces the reset boundary ring")
    if (
        abs(float(w["valence"] @ w["initial_cell_mM"])) > 1e-9
        or abs(float(w["valence"] @ w["initial_env_mM"])) > 1e-9
    ):
        raise AdapterError("configured initial concentrations are not neutral")


def screening_wavenumber(world, env_mM):
    """BETSE's ko_env (sim.py init_dynamics): mean over sites of sqrt(sum prefactor*c)."""
    return float(np.sqrt(world["debye_prefactor"] @ np.asarray(env_mM)).mean())


def phase_start(world, phase, sim_start="betse", chained=None):
    """Starting concentrations (mM) and gate opening of a phase."""
    n, m = world["cell_volume_m3"].size, world["membrane_area_m2"].size
    o = math.prod(world["grid_shape"])
    if phase == "init":
        cell = np.repeat(world["initial_cell_mM"][:, None], n, axis=1)
        return {
            "cell_mM": cell,
            "membrane_mM": cell[:, world["membrane_cell"]],
            "env_mM": np.repeat(world["initial_env_mM"][:, None], o, axis=1),
            "gate_open": np.ones(m),
        }
    if sim_start == "betse" and world["init_final"] is not None:
        return {k: np.array(v, dtype=np.float64) for k, v in world["init_final"].items()}
    if sim_start == "chained" and chained is not None:
        return {k: np.array(v, dtype=np.float64) for k, v in chained.items()}
    raise AdapterError("SIM start must be 'betse' or 'chained' with an INIT end state")


# ............................................................ comparison layout


def layout_phase(world, elapsed, vm, cell_mM, env_mM, v_env=None, *, vm_ave=None, diagnostics=None):
    """Comparison-layout phase from samples at ``elapsed`` (s after the phase start).

    vm (S, membranes) V; cell_mM (S, ions, cells); env_mM (S, ions, sites); v_env
    (S, sites) V or None (no venv_time). vm_ave defaults to BETSE's plain mean of a
    cell's membrane voltages. ``diagnostics`` maps "diag_*_time" names to (S, ...)
    arrays that no protocol judges. The last sample is the phase end state.
    """
    history = {"vm_time": vm, "cc_time": cell_mM, "cc_env_time": env_mM}
    if v_env is not None:
        history["venv_time"] = v_env
    history = {k: np.asarray(v, dtype=np.float64) for k, v in history.items()}
    owner, n = world["membrane_cell"], world["cell_volume_m3"].size
    if vm_ave is None:
        counts = np.bincount(owner, minlength=n)
        vm_ave = np.stack([np.bincount(owner, row, minlength=n) / counts for row in vm])
    history["vm_ave_time"] = np.asarray(vm_ave, dtype=np.float64)
    extra = {k: np.asarray(v) for k, v in (diagnostics or {}).items()}
    if any(not k.startswith("diag_") or not k.endswith("_time") for k in extra):
        raise AdapterError("diagnostic arrays are named diag_*_time")
    if any(len(v) != len(elapsed) for v in (*history.values(), *extra.values())):
        raise AdapterError("observables and elapsed times have different sample counts")
    final = {compare.SUPPORTED[k]: v[-1] for k, v in history.items()}
    final |= {k.removesuffix("_time"): v[-1] for k, v in extra.items()}
    return {
        "elapsed_after_update_s": [float(t) for t in elapsed],
        "final_elapsed_s": float(elapsed[-1]),
        "history": history | extra,
        "final": final,
    }


RESOLVED_OBSERVED = (
    "times",
    "amount_increment",
    "amount",
    "extracellular_amount",
    "extracellular_amount_increment",
    "membrane_voltage_V",
    "cell_potential_V",
    "extracellular_potential_V",
    "junction_gate",
    "charge_residual_C",
    "component_current_residual_A",
)


def resolved_layout_phase(world, definition, observations):
    """Comparison-layout phase from resolved_pump_tissue@1/@2 observations of one phase.

    Judged arrays follow physical_route_observables.txt: vm_ave_time is each cell's
    charge voltage Q_cell / sum(C_patch), with Q_cell = initial_charge_C + F * sum
    z * amount_increment and C_patch = cm * mem_sa; vm_time broadcasts it to the
    cell's membranes; concentrations are amount / volume (mM, BETSE order). Per-patch
    voltages and node potentials are diag_* arrays; there is no venv_time. Slots
    follow the definition (BETSE cells, row-major grid points, BETSE membranes);
    ``observations`` maps RESOLVED_OBSERVED names to stacked arrays, amounts being
    (S, species, slots). The t = 0 row is dropped.
    """
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    model = definition["model"]
    n, o, m = (len(model[k]) for k in ("cells", "extracellular", "membranes"))
    valence = np.array([row["valence"] for row in model["species"]], dtype=np.float64)
    obs = {k: np.asarray(observations[k]) for k in RESOLVED_OBSERVED}
    keep = obs["times"] > 0
    obs = {k: v[keep] for k, v in obs.items()}
    if (
        obs["amount"].shape[1] != valence.size
        or obs["extracellular_amount"].shape[1] != valence.size
    ):
        raise AdapterError("resolved amounts are not (samples, species, slots)")
    owner = world["membrane_cell"]
    capacitance = np.bincount(
        owner, [row["capacitance_F"] for row in model["membranes"]], minlength=n
    )
    charge0 = np.array([row["initial_charge_C"] for row in model["cells"]])
    charge = charge0 + CHARGE_PER_FMOL * np.einsum(
        "s,tsn->tn", valence, obs["amount_increment"][:, :, :n]
    )
    vm_ave = charge / capacitance
    cell_pL = np.array([c["volume_pL"] for c in model["cells"]])
    site_pL = np.array([c["volume_pL"] for c in model["extracellular"]])
    diagnostics = {
        "diag_patch_voltage_time": obs["membrane_voltage_V"][:, :m],
        "diag_cell_potential_time": obs["cell_potential_V"][:, :n],
        "diag_extracellular_potential_time": obs["extracellular_potential_V"][:, :o],
        "diag_junction_gate_time": obs["junction_gate"][:, : len(model["junctions"])],
    }
    return layout_phase(
        world,
        obs["times"],
        vm_ave[:, owner],
        obs["amount"][:, :, :n] / cell_pL,
        obs["extracellular_amount"][:, :, :o] / site_pL,
        vm_ave=vm_ave,
        diagnostics=diagnostics,
    )


def provenance(extra):
    """Snapshot identity when executed from a frozen snapshot, else the checkout's Git state."""
    record = dict(extra)
    if (ROOT / "SNAPSHOT.json").is_file():
        from validation import source_snapshot

        value = source_snapshot.verify(ROOT)
        record["snapshot"] = {
            "root": str(ROOT),
            "manifest_sha256": reference_run.sha256_file(ROOT / "SNAPSHOT.json"),
            "git_revision": value["git_revision"],
            "patch_sha256": value["patch_sha256"],
            "repository": value["repository"],
            "files": len(value["files"]),
        }
        record["git_revision"] = value["git_revision"]
        record["dirty"] = bool(value["selected_status_porcelain_v1_z"])
    else:
        git = reference_run.git_provenance(
            [ROOT / name for name in EXECUTED if (ROOT / name).is_file()]
        )
        record["git"] = git
        record["git_revision"] = git.get("revision")
        record["dirty"] = git.get("dirty")
    return record


# ............................................................ emulator backend


def emulator_inputs(world, phase, start, variant):
    """Emulator layout and state for one phase (all ions moving, no Kv1p5 population)."""
    from cells.processes import junction_gate, kinetic_pump
    from validation.betse.emulator import active, junction, spatial

    n, m, s = world["cell_volume_m3"].size, world["membrane_area_m2"].size, len(world["species"])
    rows, cols = world["grid_shape"]
    o = rows * cols
    ko = screening_wavenumber(world, start["env_mM"])
    tissue = spatial.Layout(
        cell_volume=world["cell_volume_m3"],
        membrane_area=world["membrane_area_m2"],
        cell_owner=world["membrane_cell"],
        outside_owner=world["membrane_site"],
        partner=world["membrane_partner"],
        moving=np.ones(s, dtype=bool),
        valence=world["valence"],
        membrane_permeability=world["membrane_permeability_m_s"][phase],
        junction_permeability=world["junction_permeability_m_s"],
        membrane_open=np.ones(m),
        junction_open=world["junction_weight"],
        diffusivity=world["env_diffusivity_m2_s"].reshape(s, rows, cols),
        boundary_concentration=world["boundary_concentration_mM"],
        boundary_values=np.zeros((rows, cols)),
        extra_cell_charge_density=np.zeros(n),
        extra_outside_charge_density=np.zeros(o),
        spacing=np.asarray(world["grid_spacing_m"]),
        height=np.asarray(world["cell_height_m"]),
        temperature=np.asarray(world["temperature_K"]),
        capacitance_density=np.asarray(world["capacitance_F_m2"]),
        screening_wavenumber=np.asarray(ko),
        permittivity=np.asarray(world["permittivity_F_m"]),
        cell_size_ratio=np.asarray(world["cell_size_ratio"]),
        native_q_over_kb=np.asarray(world["q_over_kb_C_K_J"]),
    )
    pump = kinetic_pump.Parameters(
        world["pump_capacity_fmol_s"],
        *(
            np.full(m, world[k])
            for k in (
                "pump_atp_mM",
                "pump_adp_mM",
                "pump_pi_mM",
                "pump_km_na_mM",
                "pump_km_k_mM",
                "pump_km_atp_mM",
                "pump_delta_g0_J_mol",
            )
        ),
    )
    na, k = world["species"].index("Na"), world["species"].index("K")
    calcium = None
    if world["calcium_pump"] is not None:
        from cells.processes import er_calcium

        c = world["calcium_pump"]
        calcium = active.CalciumPump(
            np.asarray(world["species"].index("Ca")),
            er_calcium.PumpParameters(
                c["capacity_fmol_s"],
                *(
                    np.full(m, c[key])
                    for key in (
                        "km_ca_mM",
                        "km_atp_mM",
                        "atp_mM",
                        "adp_mM",
                        "pi_mM",
                        "delta_g_mM_quotient_J_mol",
                    )
                ),
            ),
            np.ones(m),
        )
    layout = junction.validate_layout(
        junction.Layout(
            active.Layout(
                tissue, pump, np.asarray(na), np.asarray(k), np.ones(m), np.zeros(m), calcium
            ),
            junction_gate.Parameters(
                np.full(m, world["gate_threshold_V"]), np.full(m, world["gate_minimum_open"])
            ),
            np.ones(m),
            np.arange(s),
        ),
        variant=variant,
    )
    tissue_state = spatial.initial_state(
        start["cell_mM"], start["membrane_mM"], start["env_mM"], layout.active.tissue
    )
    state = junction.initial_state(
        active.initial_state(tissue_state, layout.active, np.zeros(m), np.zeros(m)),
        layout,
        start["gate_open"],
    )
    return state, layout, ko


def emulator_phase(state, layout, dt, steps, variant, device, substeps=1):
    """Run one phase on ``device``; observables after every ``substeps`` updates of dt.

    With substeps = f > 1 the phase takes f * steps updates of dt (the caller passes
    BETSE's dt / f) and records the same sample times as BETSE.
    """
    import jax
    import jax.numpy as jnp

    from validation.betse.emulator import junction, spatial

    m = layout.junction_block.size
    control = junction.Control(*(np.ones(m) for _ in junction.Control._fields))

    def run(state, layout, dt, control):
        def update(carry):
            old, ok = carry
            new, _, valid = junction.step(old, layout, dt, control, variant=variant)
            ok = ok & valid
            return jax.tree.map(lambda a, b: jnp.where(ok, a, b), new, old), ok

        def one(carry, _):
            if substeps == 1:
                new, ok = update(carry)
            else:
                new, ok = jax.lax.fori_loop(0, substeps, lambda _, c: update(c), carry)
            f = spatial.field(new.active.tissue, layout.active.tissue, variant=variant)
            tissue = new.active.tissue
            record = (
                f.membrane_voltage_V,
                tissue.cell_concentration,
                tissue.outside_concentration,
                f.outside_potential_V.reshape(-1),
                new.junction_open,
                ok,
            )
            return (new, ok), record

        return jax.lax.scan(one, (state, jnp.asarray(True)), None, length=steps)

    compiled = jax.jit(run)
    args = jax.device_put((state, layout, jnp.asarray(dt), control), device)
    start = time.perf_counter()
    (final, ok), history = jax.block_until_ready(compiled(*args))
    wall = time.perf_counter() - start
    history = [np.asarray(v) for v in history]
    accepted = history[-1]
    return {
        "valid": bool(ok),
        "accepted_samples": int(accepted.sum()),
        "first_rejected_sample": None if accepted.all() else int(np.argmin(accepted)) + 1,
        "wall_s_including_compile": wall,
        "vm": history[0],
        "cell_mM": history[1],
        "env_mM": history[2],
        "v_env": history[3],
        "gate_open": history[4],
        "end": {
            "cell_mM": np.asarray(final.active.tissue.cell_concentration),
            "membrane_mM": np.asarray(final.active.tissue.membrane_concentration),
            "env_mM": np.asarray(final.active.tissue.outside_concentration),
            "gate_open": np.asarray(final.junction_open),
        },
    }


def run_emulator(
    case, protocol_path, out, *, constants, device_kind, sim_start, dt_factor=1, differences=()
):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.betse.emulator import laws

    protocol, protocol_sha = compare.load_protocol(protocol_path)
    world = betse_world(case)
    variant = laws.default_world(constants, differences)
    device = jax.devices(device_kind)[0]
    phases, records, chained = {}, {}, None
    for phase in PHASES:
        start = phase_start(world, phase, sim_start, chained)
        state, layout, ko = emulator_inputs(world, phase, start, variant)
        dt, steps = world["dt_s"][phase], world["steps"][phase]
        result = emulator_phase(state, layout, dt / dt_factor, steps, variant, device, dt_factor)
        chained = result["end"]
        records[phase] = {
            "dt_s": dt / dt_factor,
            "dt_factor": dt_factor,
            "updates": steps * dt_factor,
            "valid": result["valid"],
            "accepted_samples": result["accepted_samples"],
            "first_rejected_sample": result["first_rejected_sample"],
            "wall_s_including_compile": result["wall_s_including_compile"],
            "start": "configured cell/env concentrations, gates 1"
            if phase == "init"
            else sim_start,
            "ko_env_per_m": ko,
            "betse_ko_env_per_m": world["betse_ko_env"][phase],
            "ko_env_relative_difference": ko / world["betse_ko_env"][phase] - 1,
            "gate_open_range": [float(result["gate_open"].min()), float(result["gate_open"].max())],
        }
        elapsed = [(k + 1) * dt for k in range(steps)]  # BETSE sample k: after k + 1 of its dt
        phases[phase] = layout_phase(
            world, elapsed, result["vm"], result["cell_mM"], result["env_mM"], result["v_env"]
        )
        if not result["valid"]:
            break
    record = {
        "kind": "cells.default_world_adapter_run@1",
        "created_utc": reference_run.utc_now(),
        "backend": "emulator",
        "model": "validation/betse/emulator (BETSE-order kernel, not an engine model)",
        "variant": variant._asdict(),
        "constants": constants,
        "model_differences": list(differences),
        "dt_factor": dt_factor,
        "device": str(device),
        "jax": jax.__version__,
        "sim_start": sim_start,
        "case": world["case"],
        "betse_extract": world["extract"],
        "protocol": {
            "path": str(Path(protocol_path).resolve()),
            "sha256": protocol_sha,
            "id": protocol.get("id"),
        },
        "phases": records,
        "valid": all(r["valid"] for r in records.values()) and len(records) == len(PHASES),
        "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
    record = provenance(record)
    out = reference_run.resolve_out(out)
    if record["valid"]:
        compare.write_layout(
            out,
            phases,
            protocol_sha256=protocol_sha,
            betse_geometry_sha256=world["geometry_sha256"],
            provenance=record,
        )
    else:
        out.mkdir(parents=True, exist_ok=False)
    reference_run.write_json(out / "run.json", record)
    return record


# ............................................................ layout vs layout


def compare_layouts(a, b, protocol_path):
    """Two comparison layouts of the same case (e.g. CPU and L4), judged by the protocol."""
    protocol, protocol_sha = compare.load_protocol(protocol_path)
    label = protocol["verdict_class"]
    manifests = [json.loads((Path(d) / compare.LAYOUT_MANIFEST).read_text()) for d in (a, b)]
    if manifests[0]["betse_geometry_sha256"] != manifests[1]["betse_geometry_sha256"]:
        raise compare.Refusal("layouts were built on different BETSE geometries")
    result = {"kind": "cells.layout_pair_comparison@1", "created_utc": reference_run.utc_now()}
    result["layouts"] = [
        {"directory": str(Path(d).resolve()), "provenance_device": m["provenance"].get("device")}
        for d, m in zip((a, b), manifests, strict=True)
    ]
    result["protocol"] = {"path": str(Path(protocol_path).resolve()), "sha256": protocol_sha}
    result["verdict_class"] = label
    phases, verdict = {}, True
    for phase in protocol["phases"]:
        times = [m["phases"][phase]["elapsed_after_update_s"] for m in manifests]
        if times[0] != times[1]:
            raise compare.Refusal(f"{phase}: the layouts sample different times")
        rows = {}
        for part in ("history", "final"):
            arrays = [_npz(Path(d) / f"{phase}_{part}.npz") for d in (a, b)]
            for name in sorted(arrays[0]):
                quantity = _quantity(protocol, name)
                kind = protocol["tolerance_quantities"][quantity]["kind"]
                absolute, relative = compare.errors(arrays[0][name], arrays[1][name])
                worst = float({"abs": absolute, "rel": relative}[kind].max())
                tolerance = protocol["tolerance_classes"][label][quantity]
                series = arrays[0][name] if part == "history" else arrays[0][name][None]
                change = compare.dynamic_range(series, kind)
                rows[f"{part}/{name}"] = {
                    "max_abs": float(absolute.max()),
                    "max_rel": float(relative.max()),
                    "kind": kind,
                    "tolerance": tolerance,
                    "pass": worst <= tolerance,
                    "dynamic_range": change,
                }
                verdict &= worst <= tolerance
        phases[phase] = rows
    result["phases"] = phases
    result["verdict"] = "pass" if verdict else "fail"
    return result


def _quantity(protocol, name):
    for history, row in protocol["observables"].items():
        if name in (history, row.get("final")):
            return row["tolerance"]
    raise compare.Refusal(f"{name} is not an observable of this protocol")


# ............................................................ resolved backend inputs

RESOLVED_MODEL_ID = "resolved_pump_tissue@1"
RESOLVED_CALCIUM_MODEL_ID = "resolved_pump_tissue@2"  # with BETSE's Ca-ATPase
RESOLVED_CALCIUM_PUMP_LAW = "ca_atp_mass_action_positive@1"
RESOLVED_SOLVER = "imex_ars222_face_electromigration@1"
RESOLVED_FIELD_SOLVER = "capacitive_reduction_gauged_damped_newton@2"
RESOLVED_CLOSURE = "resolved_capacitor_components_current_continuity@1"
NEUTRAL_ROUNDOFF = 1e-14  # |sum z*amount| / sum |z*amount| treated as a neutral composition


def resolved_model_id(world):
    """resolved_pump_tissue@1, or @2 when the world has BETSE's Ca-ATPase."""
    return RESOLVED_MODEL_ID if world["calcium_pump"] is None else RESOLVED_CALCIUM_MODEL_ID


def calcium_standard_energy(world):
    """The Ca pump's 1 M standard energy: pumpCaATP's numeric-mM quotient plus R T ln(1000).

    BETSE's Ca-ATPase quotient cADP * cPi * cCao / (cATP * cCai) is in numeric mM
    (its Na/K quotient is molar), so its deltaGATP is a 1 mM-standard energy. Cells'
    ca_atp_mass_action_positive@1 declares a 1 M standard state, as the Na/K law does;
    with the same R both give the same chemical drive. Cells' (CODATA) R is used, so
    only the constants differ, as for every other law.
    """
    from cells.processes.electrochemistry import R

    c = world["calcium_pump"]
    return c["delta_g_mM_quotient_J_mol"] + R * world["temperature_K"] * math.log(1000.0)


def resolved_definition(
    world,
    phase,
    start,
    *,
    dt,
    observation_elapsed=None,
    backend="cpu",
    solver=RESOLVED_SOLVER,
):
    """resolved_pump_tissue@1 (or @2, see resolved_model_id) definition of one BETSE phase.

    Cells keep BETSE's order; outside nodes are the row-major ECM grid points, the
    edge ring being reservoirs held at c_env_bound and 0 V. One junction per
    reciprocal membrane pair (BETSE's per-membrane gap junction; boundary membranes
    are self-partnered and carry none). One face per adjacent grid pair, except
    between two reservoirs; area cell_height * delta and length delta, so the face
    factor D * area / length = D * cell_height (BETSE's own stencil is 2*delta wide).
    Immobile P stays a species with zero permeability and diffusivity.

    ``start`` holds concentrations (cell_mM, env_mM, per-membrane gate_open), or a
    handoff from ``resolved_handoff``: amounts (cell_fmol, env_fmol), each
    compartment's fixed charge and tracked charge and the per-junction gates, used
    unchanged (recomputing charge from absolute amounts would add roundoff that
    floating capacitor components cannot hold).
    """
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    species = world["species"]
    valence = world["valence"]
    n, m = world["cell_volume_m3"].size, world["membrane_area_m2"].size
    rows, cols = world["grid_shape"]
    ring = set(world["ring_sites"].tolist())

    handoff = "cell_fmol" in start

    def compartment(prefix, index, volume_m3, values, fixed=None, charge_C=None):
        volume_pL = float(volume_m3) * 1e15
        scale = 1.0 if handoff else volume_pL  # amounts as handed off, or c * V
        amount = {sp: float(values[i]) * scale for i, sp in enumerate(species)}
        terms = [float(valence[i]) * amount[sp] for i, sp in enumerate(species)]
        if fixed is None:
            # A neutral composition gives a roundoff charge (<= 1e-14 fmol here) once
            # amount = c * V is rounded; floating capacitor components need exactly
            # zero, so that residual is the fixed background. Charged states stay.
            charge = math.fsum(terms)
            neutral = abs(charge) <= NEUTRAL_ROUNDOFF * math.fsum(abs(t) for t in terms)
            fixed = -charge if neutral else 0.0
        return {
            "id": f"{prefix}{index}",
            "volume_pL": volume_pL,
            "initial_amount_fmol": amount,
            "fixed_charge_equivalent_fmol": float(fixed),
            "initial_charge_C": CHARGE_PER_FMOL * math.fsum([fixed, *terms])
            if charge_C is None
            else float(charge_C),
        }

    if handoff:
        cell_values, env_values = start["cell_fmol"], start["env_fmol"]
        fixed_cell, fixed_env = start["cell_fixed_fmol"], start["env_fixed_fmol"]
        charge_cell, charge_env = start["cell_charge_C"], start["env_charge_C"]
    else:
        cell_values, env_values = start["cell_mM"], start["env_mM"]
        fixed_cell, fixed_env = [None] * n, [None] * (rows * cols)
        charge_cell, charge_env = [None] * n, [None] * (rows * cols)
    cells = [
        compartment(
            "cell-", i, world["cell_volume_m3"][i], cell_values[:, i], fixed_cell[i], charge_cell[i]
        )
        for i in range(n)
    ]
    outside = []
    for k in range(rows * cols):
        values = env_values[:, k]
        if k in ring and not handoff:
            values = world["boundary_concentration_mM"]
        node = compartment("ecm-", k, world["site_volume_m3"], values, fixed_env[k], charge_env[k])
        node.update(reservoir=k in ring, boundary_potential_V=0.0)
        outside.append(node)
    area = world["membrane_area_m2"]
    calcium = world["calcium_pump"]
    membranes = []
    for j in range(m):
        perm = world["membrane_permeability_m_s"][phase][:, j]
        membranes.append(
            {
                "id": f"mem-{j}",
                "inside": f"cell-{world['membrane_cell'][j]}",
                "outside": f"ecm-{world['membrane_site'][j]}",
                "area_m2": float(area[j]),
                "capacitance_F": world["capacitance_F_m2"] * float(area[j]),
                "permeability_m_per_s": {sp: float(perm[i]) for i, sp in enumerate(species)},
                "law": "constant_field@1",
                "pump": {
                    "id": f"pump-{j}",
                    "law": "nak_atp_mass_action_positive@1",
                    "roles": {"sodium": "Na", "potassium": "K"},
                    "stoichiometry": {"Na": -3, "K": 2},
                    "capacity_fmol_per_s": float(world["pump_capacity_fmol_s"][j]),
                    "km_na_mM": world["pump_km_na_mM"],
                    "km_k_mM": world["pump_km_k_mM"],
                    "km_atp_mM": world["pump_km_atp_mM"],
                    "metabolism": {
                        "kind": "maintained_chemical_reservoirs@1",
                        "atp_mM": world["pump_atp_mM"],
                        "adp_mM": world["pump_adp_mM"],
                        "pi_mM": world["pump_pi_mM"],
                        "delta_g0_J_per_mol": world["pump_delta_g0_J_mol"],
                    },
                },
            }
        )
        if calcium is not None:
            membranes[-1]["calcium_pump"] = {
                "id": f"capump-{j}",
                "law": RESOLVED_CALCIUM_PUMP_LAW,
                "roles": {"calcium": "Ca"},
                "stoichiometry": {"Ca": -1},
                "capacity_fmol_per_s": float(calcium["capacity_fmol_s"][j]),
                "km_ca_mM": calcium["km_ca_mM"],
                "km_atp_mM": calcium["km_atp_mM"],
                "metabolism": {
                    "kind": "maintained_chemical_reservoirs@1",
                    "atp_mM": calcium["atp_mM"],
                    "adp_mM": calcium["adp_mM"],
                    "pi_mM": calcium["pi_mM"],
                    "delta_g0_J_per_mol": calcium_standard_energy(world),
                },
            }
    junctions, pairs = [], set()
    partner, owner = world["membrane_partner"], world["membrane_cell"]
    for j in range(m):
        k = int(partner[j])
        if k <= j:
            continue  # self-partnered boundary membrane, or the pair's second member
        pair = (int(owner[j]), int(owner[k]))
        if pair[0] == pair[1] or frozenset(pair) in pairs:
            raise AdapterError(f"junction pair {pair} is repeated or within one cell")
        pairs.add(frozenset(pair))
        perm = world["junction_permeability_m_s"][:, j] * world["junction_weight"][j]
        junctions.append(
            {
                "id": f"gj-{j}-{k}",
                "sender": f"cell-{pair[0]}",
                "receiver": f"cell-{pair[1]}",
                "area_m2": float(area[j]),
                "permeability_m_per_s": {sp: float(perm[i]) for i, sp in enumerate(species)},
                "law": "constant_field@1",
                "gate": {
                    "law": "junction_voltage_relaxation@1",
                    "threshold_voltage_V": world["gate_threshold_V"],
                    "minimum_open_fraction": world["gate_minimum_open"],
                    "initial_gate": float(
                        start["junction_gate"][len(junctions)] if handoff else start["gate_open"][j]
                    ),
                },
            }
        )
    diffusivity = world["env_diffusivity_m2_s"]
    faces = []
    for a in range(rows * cols):
        for b in (a + 1 if (a + 1) % cols else None, a + cols if a + cols < rows * cols else None):
            if b is None or (a in ring and b in ring):
                continue
            d = 2 * diffusivity[:, a] * diffusivity[:, b]
            d = np.divide(
                d, diffusivity[:, a] + diffusivity[:, b], out=np.zeros_like(d), where=d > 0
            )
            faces.append(
                {
                    "id": f"face-{a}-{b}",
                    "sender": f"ecm-{a}",
                    "receiver": f"ecm-{b}",
                    "area_m2": world["cell_height_m"] * world["grid_spacing_m"],
                    "length_m": world["grid_spacing_m"],
                    "diffusivity_m2_per_s": {sp: float(d[i]) for i, sp in enumerate(species)},
                    "law": "logmean_electrodiffusion@1",
                }
            )
    steps = round(world["steps"][phase] * world["dt_s"][phase] / dt)
    if not math.isclose(steps * dt, world["steps"][phase] * world["dt_s"][phase], rel_tol=1e-12):
        raise AdapterError("dt must divide the BETSE phase duration")
    elapsed = (
        world["time"][phase]["elapsed_after_update_s"]
        if observation_elapsed is None
        else observation_elapsed
    )
    observed = sorted(
        {0.0, steps * dt}
        | {round(t / dt) * dt for t in elapsed if abs(t / dt - round(t / dt)) < 1e-6}
    )
    experiment = {
        "end_time": steps * dt,
        "observation_times": observed,
        # Every route is listed, fully available from t = 0 (no BETSE events).
        "membrane_controls": _controls("membrane", membranes),
        "junction_controls": _controls("junction", junctions),
        "pump_controls": _controls("pump", [row["pump"] for row in membranes]),
    }
    if calcium is not None:
        experiment["calcium_pump_controls"] = _controls(
            "pump", [row["calcium_pump"] for row in membranes]
        )
    return {
        "schema_version": 1,
        "model": {
            "id": resolved_model_id(world),
            "temperature_K": world["temperature_K"],
            "species": [{"id": sp, "valence": int(valence[i])} for i, sp in enumerate(species)],
            "cells": cells,
            "extracellular": outside,
            "membranes": membranes,
            "junctions": junctions,
            "faces": faces,
            # Reservoirs exist, so no gauge node is chosen.
            "closure": {"law": RESOLVED_CLOSURE, "gauge_reference": None},
        },
        "experiment": experiment,
        "execution": {
            "dt": dt,
            "capacity": n,
            "extracellular_capacity": rows * cols,
            "membrane_capacity": m,
            "edge_capacity": len(junctions),
            "face_capacity": len(faces),
            "backend": backend,
            "jit": True,
            "precision": "float64",
            "solver": solver,
            "field_solver": RESOLVED_FIELD_SOLVER,
            "max_steps": steps,
            "max_trace_bytes": 8 * 2**30,
            "material_balance_atol_fmol": {sp: 1e-10 for sp in species},
        },
    }


def patch_exterior_check(world, phase):
    """X_ext of a resolved layout phase: |V_patch - Q_cell / sum(C_patch)| over all samples
    and patches (where, when, 95th percentile) and the largest |exterior potential| at a
    patch, i.e. at its outside node. BETSE's Vm has no exterior term (zero Phi_b)."""
    owner, site = world["membrane_cell"], world["membrane_site"]
    times = np.asarray(phase["elapsed_after_update_s"])
    history = phase["history"]
    patch = history["diag_patch_voltage_time"]
    deviation = np.abs(patch - history["vm_ave_time"][:, owner])
    t, j = np.unravel_index(int(np.argmax(deviation)), deviation.shape)
    exterior = np.abs(history["diag_extracellular_potential_time"][:, site])
    te, je = np.unravel_index(int(np.argmax(exterior)), exterior.shape)
    return {
        "x_ext_V": float(deviation[t, j]),
        "at": {
            "elapsed_s": float(times[t]),
            "membrane": int(j),
            "cell": int(owner[j]),
            "patch_voltage_V": float(patch[t, j]),
            "charge_voltage_V": float(history["vm_ave_time"][t, owner[j]]),
        },
        "p95_over_samples_and_patches_V": float(np.percentile(deviation, 95)),
        "max_abs_exterior_potential_at_patches_V": float(exterior[te, je]),
        "exterior_at": {"elapsed_s": float(times[te]), "membrane": int(je), "site": int(site[je])},
        "samples": int(times.size),
    }


def resolved_handoff(definition, checkpoint):
    """SIM start from a resolved INIT end state: amounts, fixed charges and gates as they are."""
    from cells.models import surface_pump as model

    model_def = definition["model"]
    n, o = len(model_def["cells"]), len(model_def["extracellular"])
    state = type(checkpoint.state)(*(np.asarray(v) for v in checkpoint.state))
    layout = type(checkpoint.layout)(*(np.asarray(v) for v in checkpoint.layout))
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    cell, outside = (np.asarray(v) for v in model.physical_amounts(state, layout))
    valence = np.array([row["valence"] for row in model_def["species"]], dtype=np.float64)

    def charge(rows, increment):
        start = np.array([row["initial_charge_C"] for row in rows])
        return start + CHARGE_PER_FMOL * (valence @ np.asarray(increment)[:, : len(rows)])

    return {
        "cell_fmol": cell[:, :n],
        "env_fmol": outside[:, :o],
        "cell_charge_C": charge(model_def["cells"], state.amount_increment),
        "env_charge_C": charge(model_def["extracellular"], state.extracellular_amount_increment),
        "cell_fixed_fmol": [row["fixed_charge_equivalent_fmol"] for row in model_def["cells"]],
        "env_fixed_fmol": [
            row["fixed_charge_equivalent_fmol"] for row in model_def["extracellular"]
        ],
        "junction_gate": np.asarray(state.junction_gate)[: len(model_def["junctions"])],
    }


def _isolated_sites(definition):
    """Non-reservoir outside nodes without a membrane (their own capacitor components)."""
    model = definition["model"]
    faced = {row["outside"] for row in model["membranes"]}
    return np.array(
        [
            k
            for k, node in enumerate(model["extracellular"])
            if not node["reservoir"] and node["id"] not in faced
        ],
        dtype=np.int64,
    )


def _resolved_checks(definition, obs, newton):
    """Field, charge and isolated-square behaviour of one resolved phase (no BETSE data)."""
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    model = definition["model"]
    valence = np.array([row["valence"] for row in model["species"]], dtype=np.float64)
    iso = _isolated_sites(definition)
    o = len(model["extracellular"])
    charge0 = np.array([row["initial_charge_C"] for row in model["extracellular"]])
    increment = obs["extracellular_amount_increment"][:, :, :o]
    charge = charge0 + CHARGE_PER_FMOL * np.einsum("s,tsk->tk", valence, increment)
    potential = obs["extracellular_potential_V"][:, :o]
    amount = obs["extracellular_amount"][:, :, :o]
    initial = np.array(
        [
            [row["initial_amount_fmol"][s["id"]] for s in model["species"]]
            for row in model["extracellular"]
        ]
    ).T
    isolated = {"count": int(iso.size)}
    if iso.size:
        moving = initial[:, iso] > 0
        change = np.abs(amount[:, :, iso] / np.where(moving, initial[:, iso], 1.0) - 1)
        t, k = np.unravel_index(np.argmax(np.abs(potential[:, iso])), potential[:, iso].shape)
        isolated |= {
            "max_abs_charge_C": float(np.max(np.abs(charge[:, iso]))),
            "max_abs_potential_V": float(np.abs(potential[:, iso]).max()),
            "at": {"elapsed_s": float(obs["times"][t]), "site": int(iso[k])},
            "potential_range_V": [float(potential[:, iso].min()), float(potential[:, iso].max())],
            "max_relative_amount_change": float(np.max(np.where(moving, change, 0.0))),
        }
    iterations = [row["iterations"] for row in newton]
    return {
        "newton_at_window_ends": newton,
        "newton_iterations": {
            "min": min(iterations),
            "max": max(iterations),
            "mean": float(np.mean(iterations)),
            "all_converged": all(row["converged"] for row in newton),
        },
        "max_abs_charge_residual_C": float(np.max(np.abs(obs["charge_residual_C"]))),
        "max_abs_component_current_residual_A": float(
            np.max(np.abs(obs["component_current_residual_A"]))
        ),
        "isolated_squares": isolated,
        "outside_node_potential_range_V": [float(potential.min()), float(potential.max())],
    }


def _window_sink(observed, newton, control, model):
    """Collect a window's needed observations, field solve and ledgers at its end state.

    ``model`` is the definition's model module (resolved_pump_tissue@1 or @2).
    """
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    def sink(window):
        for k in RESOLVED_OBSERVED:
            observed[k].append(np.asarray(getattr(window.observations, k)))
        state = type(window.final.state)(*(np.asarray(v) for v in window.final.state))
        layout = type(window.final.layout)(*(np.asarray(v) for v in window.final.layout))
        w = model.readouts(state, control, layout, xp=np)
        with np.errstate(all="ignore"):
            ledgers = model.balances(state, layout)
        newton.append(
            {
                "time_s": float(window.final.time),
                "iterations": int(w.field.iterations),
                "converged": bool(w.field.converged),
                "current_normalized": float(w.field.current_normalized),
                # Ledger residuals at the window end (P1's check_values bounds them).
                "ledgers_max_abs": {
                    k: float(np.max(np.abs(v), initial=0.0)) for k, v in ledgers.items()
                },
                "supplied_charge_C": float(
                    np.sum(np.abs(layout.valence * state.reservoir_supplied)) * CHARGE_PER_FMOL
                ),
            }
        )

    return sink


# Run backends as protocols' cells_run "backends" name them.
PROTOCOL_BACKENDS = {"cpu": "cpu", "gpu": "gpu (L4)"}


def judged_protocol(protocol_path, world, *, device_kind, dt_init, dt_sim, solver):
    """(protocol, sha256) of a pre-registered protocol whose case and cells_run match the run."""
    protocol, sha = compare.load_protocol(protocol_path)
    run = protocol.get("cells_run") or {}
    expected = {
        "betse_case": (protocol.get("betse_case"), world["case"]),
        "model": (run.get("model"), resolved_model_id(world)),
        "solver": (run.get("solver"), solver),
        "dt_init_s": (run.get("dt_init_s"), dt_init),
        "dt_sim_s": (run.get("dt_sim_s"), dt_sim),
        "sim_start": (run.get("sim_start"), "Cells' own INIT end state"),
    }
    for name, (declared, actual) in expected.items():
        if declared != actual:
            raise AdapterError(f"protocol {name} is {declared!r}; this run has {actual!r}")
    if PROTOCOL_BACKENDS[device_kind] not in run.get("backends", ()):
        raise AdapterError(f"protocol backends {run.get('backends')} exclude {device_kind}")
    return protocol, sha


def run_resolved(
    case,
    out,
    *,
    device_kind,
    dt_init=1e-3,
    dt_sim=1e-4,
    solver=RESOLVED_SOLVER,
    window_steps=250,
    protocol_path=None,
):
    """resolved_pump_tissue@1/@2 run: INIT then SIM from its own INIT end, windowed.

    Reads BETSE inputs only (``betse_world(blind=True)``) and computes no difference
    from BETSE. Without ``protocol_path`` the layout names no protocol, so the
    comparator refuses it; with one (judged run) the protocol must match the case and
    the run (``judged_protocol``) and its sha256 goes into the layout manifest.
    """
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, run_windowed
    from cells.models.registry import get_model

    world = betse_world(case, blind=True)
    protocol = sha = None
    if protocol_path is not None:
        protocol, sha = judged_protocol(
            protocol_path,
            world,
            device_kind=device_kind,
            dt_init=dt_init,
            dt_sim=dt_sim,
            solver=solver,
        )
    out = reference_run.resolve_out(out)
    out.mkdir(parents=True, exist_ok=False)
    device = jax.devices(device_kind)[0]
    start, phases, records = phase_start(world, "init"), {}, {}
    for phase, dt in (("init", dt_init), ("sim", dt_sim)):
        definition = resolved_definition(
            world, phase, start, dt=dt, backend=device_kind, solver=solver
        )
        reference_run.write_json(out / f"{phase}_definition.json", definition)
        record = {
            "dt_s": dt,
            "solver": solver,
            "start": "configured" if phase == "init" else "own INIT end",
        }
        records[phase] = record
        observed, newton = {k: [] for k in RESOLVED_OBSERVED}, []
        try:
            spec = parse_spec(definition)
            controls = control_values(spec, [0.0])
            control = type(controls)(*(np.asarray(v[0]) for v in controls))

            sink = _window_sink(observed, newton, control, get_model(spec.model))
            started = time.perf_counter()
            result = run_windowed(spec, WindowPolicy(window_steps), sink=sink)
            record["wall_s"] = time.perf_counter() - started
        except Exception as error:  # keep the evidence of a failed integration
            record["failure"] = {
                "type": type(error).__name__,
                "message": str(error)[:2000],
                "windows_completed": len(newton),
                "last_completed_time_s": newton[-1]["time_s"] if newton else 0.0,
                "window_ends": newton,
            }
            if newton:
                partial = {k: np.concatenate(v) for k, v in observed.items()}
                np.savez_compressed(out / f"{phase}_partial_observations.npz", **partial)
                record["failure"]["checks_before_failure"] = _resolved_checks(
                    definition, partial, newton
                )
            break
        obs = {k: np.concatenate(v) for k, v in observed.items()}
        record |= {
            "steps": int(result.final.step_index - result.start_step),
            "execute_ms_per_step": 1e3
            * result.timings.get("window_execute_seconds", float("nan"))
            / max(1, result.final.step_index - result.start_step),
            "timings": result.timings,
            "resources": result.resources,
            "diagnostics": result.diagnostics,
            **_resolved_checks(definition, obs, newton),
        }
        phases[phase] = resolved_layout_phase(world, definition, obs)
        record["patch_exterior"] = patch_exterior_check(world, phases[phase])
        start = resolved_handoff(definition, result.final)
    run = {
        "kind": "cells.default_world_adapter_run@1",
        "created_utc": reference_run.utc_now(),
        "backend": "resolved",
        "model": resolved_model_id(world),
        "blind": (
            "BETSE inputs only (manifest, geometry.npz, init_final parameter arrays); "
            "no BETSE history or end state read; no Cells-vs-BETSE difference computed"
        ),
        "device": str(device),
        "jax": jax.__version__,
        "sim_start": "chained",
        "case": world["case"],
        "betse_extract": world["extract"],
        "phases": records,
        "valid": len(phases) == len(PHASES),
        "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "protocol": None
        if protocol is None
        else {"path": str(Path(protocol_path).resolve()), "sha256": sha, "id": protocol.get("id")},
    }
    if device_kind == "gpu":
        run["gpu_peak_bytes"] = device.memory_stats().get("peak_bytes_in_use")
    run = provenance(run)
    if run["valid"]:
        compare.write_layout(
            out / "layout",
            phases,
            protocol_sha256=sha,  # None: blind integration run, not judgeable
            betse_geometry_sha256=world["geometry_sha256"],
            provenance=run,
        )
    reference_run.write_json(out / "run.json", compare.json_safe(run))
    return run


def layout_differences(a, b):
    """Every array of two layouts of one case (e.g. CPU vs L4): max abs and rel difference."""
    manifests = [json.loads((Path(d) / compare.LAYOUT_MANIFEST).read_text()) for d in (a, b)]
    if manifests[0]["betse_geometry_sha256"] != manifests[1]["betse_geometry_sha256"]:
        raise compare.Refusal("layouts were built on different BETSE geometries")
    rows = {}
    for phase in manifests[0]["phases"]:
        if [m["phases"][phase]["elapsed_after_update_s"] for m in manifests].count(
            manifests[0]["phases"][phase]["elapsed_after_update_s"]
        ) != 2:
            raise compare.Refusal(f"{phase}: the layouts sample different times")
        for part in ("history", "final"):
            arrays = [_npz(Path(d) / f"{phase}_{part}.npz") for d in (a, b)]
            for name in sorted(arrays[0]):
                absolute, relative = compare.errors(arrays[0][name], arrays[1][name])
                rows[f"{phase}/{part}/{name}"] = {
                    "max_abs": float(absolute.max()),
                    "max_rel": float(relative.max()),
                    "max_abs_value": float(np.abs(arrays[0][name]).max()),
                }
    return rows


# Difference budget: observable -> error kind (relative to the base value for "rel").
BUDGET = {
    "vm_ave_time": "abs",
    "vm_time": "abs",
    "cc_time": "rel",
    "cc_env_time": "rel",
    "venv_time": "abs",
}


def _labels(world, name, element):
    cols = world["grid_shape"][1]
    if name == "vm_time":
        return {"membrane": element[0], "cell": int(world["membrane_cell"][element[0]])}
    if name == "vm_ave_time":
        return {"cell": element[0]}
    ion = {"ion": world["species"][element[0]]} if name in ("cc_time", "cc_env_time") else {}
    k = element[-1]
    if name == "cc_time":
        return ion | {"cell": k}
    return ion | {"site": k, "row": k // cols, "col": k % cols}


def _difference_rows(world, times, history, final):
    """BUDGET rows of two runs of one case: max difference over samples and at the end.

    Concentration rows add per-ion maxima (``by_ion``), and ``cc_env_time_interior``
    repeats the ECM row without the boundary ring (as the judged protocols do).
    """
    rows = {}
    ring = np.zeros(math.prod(world["grid_shape"]), dtype=bool)
    ring[world["ring_sites"]] = True
    for name, kind in (*BUDGET.items(), ("cc_env_time_interior", "rel")):
        source = name.removesuffix("_interior")
        end = compare.SUPPORTED[source]
        pick = 0 if kind == "abs" else 1
        err = compare.errors(history[0][source], history[1][source])[pick]
        ferr = compare.errors(final[0][end], final[1][end])[pick]
        if name != source:  # interior: ring sites cannot be the maximum
            err, ferr = np.where(ring, -1.0, err), np.where(ring, -1.0, ferr)
        i = np.unravel_index(int(np.argmax(err)), err.shape)
        j = np.unravel_index(int(np.argmax(ferr)), ferr.shape)
        series = np.concatenate([history[0][source], final[0][end][None]])
        if name != source:
            series = series[..., ~ring]
        rows[name] = {
            "kind": "absolute (V)" if kind == "abs" else "relative to the base value",
            "max": float(err[i]),
            "elapsed_s": float(times[i[0]]),
            "element": [int(v) for v in i[1:]],
            "labels": _labels(world, source, [int(v) for v in i[1:]]),
            "base_value": float(history[0][source][i]),
            "other_value": float(history[1][source][i]),
            "final": {
                "max": float(ferr[j]),
                "element": [int(v) for v in j],
                "labels": _labels(world, source, [int(v) for v in j]),
                "base_value": float(final[0][end][j]),
                "other_value": float(final[1][end][j]),
            },
            "base_change_over_phase": compare.dynamic_range(series, kind),
        }
        if source in ("cc_time", "cc_env_time"):
            rows[name]["by_ion"] = {
                ion: {
                    "max": float(err[:, k].max()),
                    "final_max": float(ferr[k].max()),
                    "elapsed_s": float(times[int(np.argmax(err[:, k].max(axis=-1)))]),
                }
                for k, ion in enumerate(world["species"])
            }
    return rows


def layout_difference(world, base, other):
    """Per phase and BUDGET observable: max |difference| over every common sample (where and
    when) and at the phase end, with the base's own change over the phase."""
    manifests = [json.loads((Path(d) / compare.LAYOUT_MANIFEST).read_text()) for d in (base, other)]
    phases = {}
    for phase in PHASES:
        times = [m["phases"][phase]["elapsed_after_update_s"] for m in manifests]
        if len(times[0]) != len(times[1]) or not np.allclose(times[0], times[1], rtol=0, atol=1e-9):
            raise compare.Refusal(f"{phase}: the layouts sample different times")
        history = [_npz(Path(d) / f"{phase}_history.npz") for d in (base, other)]
        final = [_npz(Path(d) / f"{phase}_final.npz") for d in (base, other)]
        rows = _difference_rows(world, times[0], history, final)
        phases[phase] = {"samples": len(times[0]), "observables": rows}
    return {
        "base": str(Path(base).resolve()),
        "other": str(Path(other).resolve()),
        "runs": [
            json.loads((Path(d) / "run.json").read_text()).get("variant") for d in (base, other)
        ],
        "phases": phases,
    }


def betse_step_term(world, dense, fine):
    """Plain BETSE against plain BETSE with a smaller INIT step on the same seed.

    Measures BETSE's own INIT step error. A fine INIT sample lies one fine step after
    the dense sample it pairs with (BETSE sample k is the state after k + 1 updates);
    the INIT end and all SIM samples coincide exactly. Reads BETSE outputs only.
    """
    directories = [load_case(case)[0] for case in (dense, fine)]
    manifests = [json.loads((d / "manifest.json").read_text()) for d in directories]
    if len({m["files"]["geometry.npz"]["sha256"] for m in manifests}) != 1:
        raise AdapterError("the two BETSE cases have different geometries")
    phases = {}
    for phase in PHASES:
        times = [np.asarray(m["time"][phase]["elapsed_after_update_s"]) for m in manifests]
        steps = [m["time"][phase]["dt_s"] for m in manifests]
        offset = steps[1] if steps[1] < steps[0] else 0.0
        pairs = []
        for i, t in enumerate(times[0]):
            j = int(np.argmin(np.abs(times[1] - (t + offset))))
            if abs(times[1][j] - (t + offset)) <= 1e-9:
                pairs.append((i, j))
        if not pairs:
            raise AdapterError(f"{phase}: no paired samples")
        index = [np.array([p[k] for p in pairs]) for k in (0, 1)]
        history = [
            {k: v[index[n]] for k, v in _npz(d / f"{phase}_history.npz").items() if k in BUDGET}
            for n, d in enumerate(directories)
        ]
        final = [_npz(d / f"{phase}_final.npz") for d in directories]
        phases[phase] = {
            "samples": len(pairs),
            "pairing_offset_s": offset,
            "dt_s": steps,
            "observables": _difference_rows(world, times[0][index[0]], history, final),
        }
    return {
        "kind": "cells.betse_step_term@1",
        "created_utc": reference_run.utc_now(),
        "dense": str(directories[0]),
        "fine": str(directories[1]),
        "reads": "plain BETSE outputs of both cases only (no Cells model)",
        "phases": phases,
    }


def _controls(kind, routes):
    full = [{"time": 0.0, "availability": 1.0}]
    return [{f"{kind}_id": route["id"], "schedule": full} for route in routes]


def junction_gate_dt_bound(world):
    """Largest dt of the resolved gate update: dt * (1.3 exp(77 Vth) + 20) <= 0.125."""
    return 0.125 / (1.3 * math.exp(77 * world["gate_threshold_V"]) + 20)


# ............................................................ command line


def cmd_snapshot(args):
    import subprocess

    from validation import source_snapshot

    names = set(EXECUTED)
    if args.engine:  # the resolved backend imports most of the engine
        listed = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                "src/cells",
            ],
            check=True,
            capture_output=True,
        ).stdout
        names |= {p for p in listed.decode().split("\0") if p and (ROOT / p).is_file()}
    out = reference_run.resolve_out(args.out)
    value = source_snapshot.freeze(ROOT, out, {name: name for name in sorted(names)})
    print(json.dumps({"snapshot": str(out), "git_revision": value["git_revision"]}, indent=2))
    return 0


def cmd_run(args):
    record = run_emulator(
        args.case,
        args.protocol,
        args.out,
        constants=args.constants,
        device_kind=args.device,
        sim_start=args.sim_start,
        dt_factor=args.dt_factor,
        differences=tuple(args.model_difference),
    )
    summary = {
        k: record[k]
        for k in ("valid", "device", "constants", "dt_factor", "sim_start", "max_rss_mib")
    }
    summary["phases"] = {
        p: {k: r[k] for k in ("valid", "wall_s_including_compile", "ko_env_relative_difference")}
        for p, r in record["phases"].items()
    }
    print(json.dumps(summary, indent=2))
    return 0 if record["valid"] else 1


def cmd_compare_layouts(args):
    result = compare_layouts(args.a, args.b, args.protocol)
    out = reference_run.resolve_out(args.out)
    out.mkdir(parents=True, exist_ok=False)
    reference_run.write_json(out / "result.json", compare.json_safe(result))
    print(json.dumps({"verdict": result["verdict"], "out": str(out)}, indent=2))
    return 0 if result["verdict"] == "pass" else 1


def cmd_run_resolved(args):
    record = run_resolved(
        args.case,
        args.out,
        device_kind=args.device,
        dt_init=args.dt_init,
        dt_sim=args.dt_sim,
        solver=args.solver,
        window_steps=args.window_steps,
        protocol_path=args.protocol,
    )
    print(json.dumps({"valid": record["valid"], "device": record["device"]}, indent=2))
    return 0 if record["valid"] else 1


def cmd_layout_differences(args):
    out = reference_run.resolve_out(args.out)
    result = {
        "kind": "cells.layout_differences@1",
        "created_utc": reference_run.utc_now(),
        "a": str(Path(args.a).resolve()),
        "b": str(Path(args.b).resolve()),
        "arrays": layout_differences(args.a, args.b),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    reference_run.write_json(out, compare.json_safe(result))
    worst = max(result["arrays"].items(), key=lambda kv: kv[1]["max_rel"])
    print(json.dumps({"out": str(out), "largest_relative": worst}, indent=2))
    return 0


def cmd_difference_budget(args):
    world = betse_world(args.case, blind=True)
    out = reference_run.resolve_out(args.out)
    result = {
        "kind": "cells.emulator_difference_budget@1",
        "created_utc": reference_run.utc_now(),
        "case": world["case"],
        "observables": {k: v for k, v in BUDGET.items()},
        "pairs": {name: layout_difference(world, a, b) for name, a, b in args.pair},
    }
    result = provenance(result)
    out.parent.mkdir(parents=True, exist_ok=True)
    reference_run.write_json(out, compare.json_safe(result))
    print(json.dumps({"out": str(out), "pairs": list(result["pairs"])}, indent=2))
    return 0


def cmd_betse_step_term(args):
    world = betse_world(args.dense, blind=True)
    out = reference_run.resolve_out(args.out)
    result = provenance(betse_step_term(world, args.dense, args.fine))
    out.parent.mkdir(parents=True, exist_ok=True)
    reference_run.write_json(out, compare.json_safe(result))
    print(json.dumps({"out": str(out)}, indent=2))
    return 0


def cmd_resolved_definition(args):
    world = betse_world(args.case)
    start = phase_start(world, args.phase, "betse")
    definition = resolved_definition(world, args.phase, start, dt=args.dt, backend=args.device)
    out = reference_run.resolve_out(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    reference_run.write_json(out, definition)
    counts = {k: len(v) for k, v in definition["model"].items() if isinstance(v, list)}
    print(
        json.dumps(
            {"out": str(out), "counts": counts, "gate_dt_bound_s": junction_gate_dt_bound(world)}
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot", help="freeze the sources a run executes")
    snapshot.add_argument("--out", required=True)
    snapshot.add_argument("--engine", action="store_true", help="also freeze all of src/cells")
    snapshot.set_defaults(func=cmd_snapshot)
    run = sub.add_parser("run", help="emulator INIT then SIM, written in the comparison layout")
    run.add_argument("--case", required=True, help="BETSE case or extraction directory")
    run.add_argument("--protocol", required=True, help="comparison protocol fixed before the run")
    run.add_argument("--constants", choices=("betse", "codata"), default="betse")
    run.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    run.add_argument("--sim-start", choices=("betse", "chained"), default="betse")
    run.add_argument("--dt-factor", type=int, default=1, help="updates of dt/f per BETSE dt")
    run.add_argument(
        "--model-difference",
        action="append",
        default=[],
        choices=("ecm_drift_off", "compact_ecm_faces", "gate_once_no_lag"),
        help="switch on one deliberate Cells-model difference (emulator/laws.py), to size it",
    )
    run.add_argument("--out", required=True, help="fresh layout directory")
    run.set_defaults(func=cmd_run)
    blind = sub.add_parser("run-resolved", help="blind resolved_pump_tissue@1/@2 INIT then SIM")
    blind.add_argument("--case", required=True)
    blind.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    blind.add_argument("--dt-init", type=float, default=1e-3)
    blind.add_argument("--dt-sim", type=float, default=1e-4)
    blind.add_argument("--solver", default=RESOLVED_SOLVER)
    blind.add_argument("--window-steps", type=int, default=250)
    blind.add_argument(
        "--protocol", help="pre-registered protocol of a judged run (default: blind)"
    )
    blind.add_argument("--out", required=True, help="fresh run directory")
    blind.set_defaults(func=cmd_run_resolved)
    diff = sub.add_parser("layout-differences", help="every array of two layouts, unjudged")
    diff.add_argument("--a", required=True)
    diff.add_argument("--b", required=True)
    diff.add_argument("--out", required=True, help="fresh JSON file")
    diff.set_defaults(func=cmd_layout_differences)
    budget = sub.add_parser("difference-budget", help="emulator variant differences")
    budget.add_argument("--case", required=True, help="BETSE case (inputs only)")
    budget.add_argument(
        "--pair", nargs=3, action="append", required=True, metavar=("NAME", "BASE", "OTHER")
    )
    budget.add_argument("--out", required=True, help="fresh JSON file")
    budget.set_defaults(func=cmd_difference_budget)
    step = sub.add_parser("betse-step-term", help="plain BETSE dense vs fine INIT step")
    step.add_argument("--dense", required=True, help="BETSE case at BETSE's INIT dt")
    step.add_argument("--fine", required=True, help="same seed, smaller INIT dt")
    step.add_argument("--out", required=True, help="fresh JSON file")
    step.set_defaults(func=cmd_betse_step_term)
    pair = sub.add_parser("compare-layouts", help="two layouts of one case (e.g. CPU vs L4)")
    pair.add_argument("--a", required=True)
    pair.add_argument("--b", required=True)
    pair.add_argument("--protocol", required=True)
    pair.add_argument("--out", required=True)
    pair.set_defaults(func=cmd_compare_layouts)
    resolved = sub.add_parser("resolved-definition", help="resolved_pump_tissue@1/@2 inputs")
    resolved.add_argument("--case", required=True)
    resolved.add_argument("--phase", choices=PHASES, default="init")
    resolved.add_argument("--dt", type=float, required=True)
    resolved.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    resolved.add_argument("--out", required=True)
    resolved.set_defaults(func=cmd_resolved_definition)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (AdapterError, compare.Refusal) as error:
        print(json.dumps({"refused": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
