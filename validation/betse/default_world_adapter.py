#!/usr/bin/env python3
"""BETSE's default world in Cells backends, written in the comparison layout.

``betse_world`` maps one plain-BETSE extraction (``betse_reference_extract.py``) to
named physical quantities with units, independent of any backend; ``WORLD_UNITS``
says which BETSE array feeds which quantity. Backends:

* ``emulator``: validation/betse/emulator, BETSE's own update order. With BETSE's
  constants it should reproduce BETSE to roundoff; it attributes differences.
* ``resolved``: ``resolved_definition`` builds resolved_pump_tissue@1 inputs
  (cells, outside nodes, patches, junctions, faces, ring reservoirs at 0 V).

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


def betse_world(path):
    """Backend-neutral physical inputs of one BETSE default-world case (see WORLD_UNITS)."""
    directory, manifest = load_case(path)
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
        "init_final": {
            "cell_mM": finals["init"]["cc_cells"],
            "membrane_mM": finals["init"]["cc_at_mem"],
            "env_mM": finals["init"]["cc_env"],
            "gate_open": finals["init"]["gjopen"],
        },
    }
    _check_world(world)
    return world


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
    if sim_start == "betse":
        return {k: np.array(v, dtype=np.float64) for k, v in world["init_final"].items()}
    if sim_start == "chained" and chained is not None:
        return {k: np.array(v, dtype=np.float64) for k, v in chained.items()}
    raise AdapterError("SIM start must be 'betse' or 'chained' with an INIT end state")


# ............................................................ comparison layout


def layout_phase(world, elapsed, vm, cell_mM, env_mM, v_env):
    """Comparison-layout phase from samples at ``elapsed`` (s after the phase start).

    vm (S, membranes) V; cell_mM (S, ions, cells); env_mM (S, ions, sites); v_env
    (S, sites) V. The last sample is the phase end state.
    """
    vm, cell_mM, env_mM, v_env = (
        np.asarray(a, dtype=np.float64) for a in (vm, cell_mM, env_mM, v_env)
    )
    if not len(elapsed) == len(vm) == len(cell_mM) == len(env_mM) == len(v_env):
        raise AdapterError("observables and elapsed times have different sample counts")
    owner, n = world["membrane_cell"], world["cell_volume_m3"].size
    counts = np.bincount(owner, minlength=n)
    vm_ave = np.stack([np.bincount(owner, row, minlength=n) / counts for row in vm])
    history = {
        "vm_time": vm,
        "vm_ave_time": vm_ave,
        "cc_time": cell_mM,
        "cc_env_time": env_mM,
        "venv_time": v_env,
    }
    return {
        "elapsed_after_update_s": [float(t) for t in elapsed],
        "final_elapsed_s": float(elapsed[-1]),
        "history": history,
        "final": {compare.SUPPORTED[k]: v[-1] for k, v in history.items()},
    }


def resolved_layout_phase(world, definition, observations):
    """Comparison-layout phase from resolved_pump_tissue@1 observations of one phase.

    Slots follow the definition's order (BETSE cells, row-major grid points, BETSE
    membranes); ``amount``/``extracellular_amount`` are (S, species, slots) fmol,
    divided by each compartment's volume (pL) to give mM. The t = 0 row is dropped.
    """
    model = definition["model"]
    n, o, m = (len(model[k]) for k in ("cells", "extracellular", "membranes"))
    species = len(model["species"])
    times = np.asarray(observations.times, dtype=np.float64)
    keep = times > 0
    amount = np.asarray(observations.amount)[keep]
    outside = np.asarray(observations.extracellular_amount)[keep]
    if amount.shape[1] != species or outside.shape[1] != species:
        raise AdapterError("resolved amounts are not (samples, species, slots)")
    cell_pL = np.array([c["volume_pL"] for c in model["cells"]])
    site_pL = np.array([c["volume_pL"] for c in model["extracellular"]])
    return layout_phase(
        world,
        times[keep],
        np.asarray(observations.membrane_voltage_V)[keep][:, :m],
        amount[:, :, :n] / cell_pL,
        outside[:, :, :o] / site_pL,
        np.asarray(observations.extracellular_potential_V)[keep][:, :o],
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
    layout = junction.validate_layout(
        junction.Layout(
            active.Layout(tissue, pump, np.asarray(na), np.asarray(k), np.ones(m), np.zeros(m)),
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


def emulator_phase(state, layout, dt, steps, variant, device):
    """Run one phase on ``device``; per-update observables and the end state."""
    import jax
    import jax.numpy as jnp

    from validation.betse.emulator import junction, spatial

    m = layout.junction_block.size
    control = junction.Control(*(np.ones(m) for _ in junction.Control._fields))

    def run(state, layout, dt, control):
        def one(carry, _):
            old, ok = carry
            new, _, valid = junction.step(old, layout, dt, control, variant=variant)
            ok = ok & valid
            new = jax.tree.map(lambda a, b: jnp.where(ok, a, b), new, old)
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
        "accepted_updates": int(accepted.sum()),
        "first_rejected_update": None if accepted.all() else int(np.argmin(accepted)) + 1,
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


def run_emulator(case, protocol_path, out, *, constants, device_kind, sim_start):
    import jax

    jax.config.update("jax_enable_x64", True)
    from validation.betse.emulator import laws

    protocol, protocol_sha = compare.load_protocol(protocol_path)
    world = betse_world(case)
    variant = laws.default_world(constants)
    device = jax.devices(device_kind)[0]
    phases, records, chained = {}, {}, None
    for phase in PHASES:
        start = phase_start(world, phase, sim_start, chained)
        state, layout, ko = emulator_inputs(world, phase, start, variant)
        dt, steps = world["dt_s"][phase], world["steps"][phase]
        result = emulator_phase(state, layout, dt, steps, variant, device)
        chained = result["end"]
        records[phase] = {
            "dt_s": dt,
            "updates": steps,
            "valid": result["valid"],
            "accepted_updates": result["accepted_updates"],
            "first_rejected_update": result["first_rejected_update"],
            "wall_s_including_compile": result["wall_s_including_compile"],
            "start": "configured cell/env concentrations, gates 1"
            if phase == "init"
            else sim_start,
            "ko_env_per_m": ko,
            "betse_ko_env_per_m": world["betse_ko_env"][phase],
            "ko_env_relative_difference": ko / world["betse_ko_env"][phase] - 1,
            "gate_open_range": [float(result["gate_open"].min()), float(result["gate_open"].max())],
        }
        elapsed = [(k + 1) * dt for k in range(steps)]  # sample k: after k + 1 updates
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
RESOLVED_SOLVER = "imex_ars222_face_electromigration@1"
RESOLVED_FIELD_SOLVER = "capacitive_reduction_gauged_damped_newton@2"
RESOLVED_CLOSURE = "resolved_capacitor_components_current_continuity@1"
CONTRACT_CHARGE_PER_FMOL_C = 96485.33212e-15  # the identity's initial_charge_C convention
NEUTRAL_ROUNDOFF = 1e-14  # |sum z*amount| / sum |z*amount| treated as a neutral composition


def resolved_definition(world, phase, start, *, dt, observation_elapsed=None, backend="cpu"):
    """resolved_pump_tissue@1 definition of one BETSE phase (contract of 8 November).

    Cells keep BETSE's order; outside nodes are the row-major ECM grid points, the
    edge ring being reservoirs held at c_env_bound and 0 V. One junction per
    reciprocal membrane pair (BETSE's per-membrane gap junction; boundary membranes
    are self-partnered and carry none). One face per adjacent grid pair, except
    between two reservoirs; area cell_height * delta and length delta, so the face
    factor D * area / length = D * cell_height (BETSE's own stencil is 2*delta wide).
    Immobile P stays a species with zero permeability and diffusivity.
    """
    species = world["species"]
    valence = world["valence"]
    n, m = world["cell_volume_m3"].size, world["membrane_area_m2"].size
    rows, cols = world["grid_shape"]
    ring = set(world["ring_sites"].tolist())

    def compartment(prefix, index, volume_m3, mM, amounts=None):
        volume_pL = float(volume_m3) * 1e15
        values = mM if amounts is None else amounts
        amount = {sp: float(values[i]) * volume_pL for i, sp in enumerate(species)}
        terms = [float(valence[i]) * amount[sp] for i, sp in enumerate(species)]
        charge = math.fsum(terms)
        # A neutral composition gives a roundoff charge (<= 1e-14 fmol here) once
        # amount = c * V is rounded; floating capacitor components need exactly zero,
        # so that residual is the fixed background. Charged states are left as given.
        neutral = abs(charge) <= NEUTRAL_ROUNDOFF * math.fsum(abs(t) for t in terms)
        fixed = -charge if neutral else 0.0
        return {
            "id": f"{prefix}{index}",
            "volume_pL": volume_pL,
            "initial_amount_fmol": amount,
            "fixed_charge_equivalent_fmol": fixed,
            "initial_charge_C": CONTRACT_CHARGE_PER_FMOL_C * math.fsum([fixed, *terms]),
        }

    cells = [
        compartment("cell-", i, world["cell_volume_m3"][i], start["cell_mM"][:, i])
        for i in range(n)
    ]
    outside = []
    for k in range(rows * cols):
        held = world["boundary_concentration_mM"] if k in ring else None
        node = compartment("ecm-", k, world["site_volume_m3"], start["env_mM"][:, k], held)
        node.update(reservoir=k in ring, boundary_potential_V=0.0)
        outside.append(node)
    area = world["membrane_area_m2"]
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
                    "initial_gate": float(start["gate_open"][j]),
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
    return {
        "schema_version": 1,
        "model": {
            "id": RESOLVED_MODEL_ID,
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
        "experiment": {
            "end_time": steps * dt,
            "observation_times": observed,
            # Every route is listed, fully available from t = 0 (no BETSE events).
            "membrane_controls": _controls("membrane", membranes),
            "junction_controls": _controls("junction", junctions),
            "pump_controls": _controls("pump", [row["pump"] for row in membranes]),
        },
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
            "solver": RESOLVED_SOLVER,
            "field_solver": RESOLVED_FIELD_SOLVER,
            "max_steps": steps,
            "max_trace_bytes": 8 * 2**30,
            "material_balance_atol_fmol": {sp: 1e-10 for sp in species},
        },
    }


def _controls(kind, routes):
    full = [{"time": 0.0, "availability": 1.0}]
    return [{f"{kind}_id": route["id"], "schedule": full} for route in routes]


def junction_gate_dt_bound(world):
    """Largest dt of the resolved gate update: dt * (1.3 exp(77 Vth) + 20) <= 0.125."""
    return 0.125 / (1.3 * math.exp(77 * world["gate_threshold_V"]) + 20)


# ............................................................ command line


def cmd_snapshot(args):
    from validation import source_snapshot

    out = reference_run.resolve_out(args.out)
    value = source_snapshot.freeze(ROOT, out, {name: name for name in EXECUTED})
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
    )
    summary = {k: record[k] for k in ("valid", "device", "constants", "sim_start", "max_rss_mib")}
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
    snapshot.set_defaults(func=cmd_snapshot)
    run = sub.add_parser("run", help="emulator INIT then SIM, written in the comparison layout")
    run.add_argument("--case", required=True, help="BETSE case or extraction directory")
    run.add_argument("--protocol", required=True, help="comparison protocol fixed before the run")
    run.add_argument("--constants", choices=("betse", "codata"), default="betse")
    run.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    run.add_argument("--sim-start", choices=("betse", "chained"), default="betse")
    run.add_argument("--out", required=True, help="fresh layout directory")
    run.set_defaults(func=cmd_run)
    pair = sub.add_parser("compare-layouts", help="two layouts of one case (e.g. CPU vs L4)")
    pair.add_argument("--a", required=True)
    pair.add_argument("--b", required=True)
    pair.add_argument("--protocol", required=True)
    pair.add_argument("--out", required=True)
    pair.set_defaults(func=cmd_compare_layouts)
    resolved = sub.add_parser("resolved-definition", help="resolved_pump_tissue@1 inputs")
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
