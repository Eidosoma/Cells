#!/usr/bin/env python3
"""Extract plain arrays from a betse_reference_run.py run with BETSE's own loaders.

``extract`` imports BETSE, so run it with the BETSE environment's Python. It
loads the seed, INIT and SIM pickles with ``betse.science.filehandling``
(``loadWorld``/``loadSim``) and writes, without recomputing physics:

    geometry.npz         cell/membrane/ECM geometry and index maps (last pickle)
    init_history.npz     INIT time series (every non-empty Simulator ``*_time``)
    sim_history.npz      SIM time series
    init_final.npz       numeric Simulator arrays at the end of INIT (= SIM start)
    sim_final.npz        numeric Simulator arrays at the end of SIM
    manifest.json        names, shapes, dtypes, units, per-array and per-file
                         SHA-256, ions, clocks, parameters, gaps, source run
    home/                isolated HOME used while BETSE was imported

``verify`` checks a manifest against its NPZ files and ``compare`` pairs two
extractions (geometry identity; histories at common BETSE step indices; final
states), both with NumPy only::

    VENV_BETSE/bin/python -I validation/betse/betse_reference_extract.py extract \\
        --run RUN_DIR [--out DIR]          (default DIR: RUN_DIR/../extract)
    python -I validation/betse/betse_reference_extract.py verify EXTRACT_DIR
    python -I validation/betse/betse_reference_extract.py compare DIR_A DIR_B [--out F]

Units are SI as stored by BETSE (concentrations mol/m^3 = mmol/L) unless a
manifest entry says otherwise. Ragged BETSE arrays are stored as
``<name>_flat`` plus ``<name>_offsets`` (item i is ``flat[offsets[i]:offsets[i+1]]``).
"""

import argparse
import enum
import hashlib
import importlib.util
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if __name__ == "__main__" and sys.path and Path(sys.path[0] or ".").resolve() == HERE:
    sys.path.pop(0)  # validation/betse modules must never shadow BETSE's dependencies

import numpy as np  # noqa: E402

KIND = "cells.betse_reference_extract@1"
PHASE_KINDS = ("seed", "init", "sim")
MAX_STATE_ELEMENTS = 2_000_000
FILES = {
    "geometry": "geometry.npz",
    "init_history": "init_history.npz",
    "sim_history": "sim_history.npz",
    "init_final": "init_final.npz",
    "sim_final": "sim_final.npz",
}
M, N, K, IONS = ("membranes",), ("cells",), ("ECM grid points",), ("ions",)
G = ("ECM grid rows", "ECM grid cols")
XY = ("xy",)

# name: (units, axes, description). Curated from betse/science/cells.py.
GEOMETRY = {
    "cell_centres": ("m", N + XY, "cell centre coordinates"),
    "cell_vol": ("m^3", N, "cell volume"),
    "cell_sa": ("m^2", N, "whole-cell membrane area (sum of mem_sa)"),
    "R": ("m", N, "effective cell radius from volume"),
    "diviterm": ("m", N, "cell_vol / cell_sa"),
    "num_mems": ("1", N, "membranes per cell"),
    "num_nn": ("1", N, "gap-junction neighbours per cell"),
    "bflags_cells": ("index", ("boundary cells",), "indices of cluster-boundary cells"),
    "cell_verts": (
        "m",
        ("ragged per cell",) + XY,
        "cell polygon vertices (CCW): ecm_verts scaled by p.scale_cell about the centre",
    ),
    "ecm_verts": ("m", ("ragged per cell",) + XY, "clipped Voronoi polygon of each cell"),
    "cell_to_mems": ("index", ("ragged per cell",), "membrane indices of each cell"),
    "cell_nn": ("index", ("ragged per cell",), "neighbouring cell indices of each cell"),
    "mem_mids_flat": ("m", M + XY, "membrane midpoints"),
    "mem_vects_flat": (
        "m | 1",
        M + ("x y nx ny tx ty",),
        "midpoint (m), unit normal and unit tangent (dimensionless)",
    ),
    "mem_sa": ("m^2", M, "membrane area = membrane length * p.cell_height"),
    "mem_vol": ("m^3", M, "membrane sector volume (R_rads * mem_sa / 2)"),
    "mem_to_cells": ("index", M, "cell owning each membrane"),
    "mem_edges_flat": ("m", M + ("end",) + XY, "membrane segment end points"),
    "mem_verts": ("m", ("membrane vertices",) + XY, "membrane vertices"),
    "index_to_mem_verts": ("index", M + ("end",), "mem_verts indices of each membrane"),
    "R_rads": ("m", M, "distance from cell centre to membrane midpoint"),
    "nn_i": ("index", M, "gap-junction partner membrane of each membrane"),
    "mem_nn": ("index", M + ("pair",), "membrane pairs (self, partner)"),
    "cell_nn_i": ("index", M + ("pair",), "cell pair at each membrane (owner, neighbour)"),
    "nn_len": ("m", M, "distance between neighbouring cell centres across each membrane"),
    "gj_default_weights": ("1", M, "default gap-junction weight of each membrane"),
    "bflags_mems": ("index", ("boundary membranes",), "indices of cluster-boundary membranes"),
    "X": ("m", G, "ECM grid-space centre x"),
    "Y": ("m", G, "ECM grid-space centre y"),
    "xypts": ("m", K + XY, "ECM grid-space centres, flattened"),
    "map_ij2k": ("index", K + ("ij",), "grid (i, j) of each flattened point"),
    "map_cell2ecm": ("index", N, "nearest ECM grid point of each cell centre"),
    "map_mem2ecm": ("index", M, "nearest ECM grid point of each membrane midpoint"),
    "maskECM": ("1", G, "1 inside the cluster, 0 in the environment (ECM grid)"),
    "maskM": ("1", ("plot rows", "plot cols"), "cluster mask on BETSE's plotting grid"),
    "cluster_mask": ("1", ("image rows", "image cols"), "clipping-image mask of the cluster"),
    "inds_env": ("index", ("environment points",), "ECM points with maskECM == 0"),
    "inds_clust": ("index", ("cluster points",), "ECM points with maskECM == 1"),
    "envInds_inClust": ("index", ("points",), "ECM points inside the cluster with membranes"),
    "bflags_ecm": ("index", ("points",), "BETSE bflags_ecm"),
    "bTop_k": ("index", ("points",), "top boundary ECM points"),
    "bBot_k": ("index", ("points",), "bottom boundary ECM points"),
    "bL_k": ("index", ("points",), "left boundary ECM points"),
    "bR_k": ("index", ("points",), "right boundary ECM points"),
    "true_ecm_vol": ("m^3", K, "extracellular volume of each grid space"),
    "memSa_per_envSquare": ("m^2", K, "membrane area per grid space"),
    "mems_per_envSquare": ("1", K, "membranes per grid space"),
    "cell2env_corrF": ("1", N, "cell-to-environment correction factor"),
    "voronoi_mask": ("1", K, "BETSE voronoi_mask"),
    "bbox": ("m", ("corner",) + XY, "cluster bounding box"),
    "centre": ("m", XY, "cluster centre"),
    "delta": ("m", (), "ECM grid spacing"),
    "ecm_vol": ("m^3", (), "nominal grid-space volume (cell_height * delta^2)"),
    "ecm_sa": ("m^2", (), "grid-space face area used for cell-ECM flux"),
    "gj_len": ("m", (), "gap-junction length (p.cell_space)"),
    "mem_distance": ("m", (), "cell_space + 2 tm"),
    "xmin": ("m", (), "world x minimum"),
    "xmax": ("m", (), "world x maximum"),
    "ymin": ("m", (), "world y minimum"),
    "ymax": ("m", (), "world y maximum"),
    "cell_number": ("1", (), "number of cells"),
    "ratio_cell2ecm": ("1", (), "ecm_vol / mean cell volume"),
}

# Simulator *_time lists (betse/science/sim.py write2storage and class docstring).
HISTORY = {
    "time": ("s", (), "sample labels t = k * n_steps * dt / (n_steps - 1) for step index k"),
    "vm_time": ("V", M, "transmembrane voltage per membrane"),
    "vm_ave_time": ("V", N, "transmembrane voltage averaged to cell centres"),
    "vm_GHK_time": ("V", N, "Goldman estimate (only with 'use Goldman calculator')"),
    "cc_time": ("mol/m^3", IONS + N, "intracellular concentration per ion"),
    "cc_env_time": (
        "mol/m^3",
        IONS + ("environment",),
        "environment concentration per ion: per ECM grid point with extracellular "
        "spaces, else per membrane",
    ),
    "dd_time": (
        "m^2/s",
        IONS + M,
        "membrane diffusion constant Dm_cells per ion (permeability = Dm / p.tm)",
    ),
    "gjopen_time": ("1", M, "gap-junction open fraction"),
    "venv_time": ("V", K, "environmental voltage on the ECM grid"),
    "I_mem_time": ("A", M, "-Jn * mem_sa, transmembrane current per membrane"),
    "I_cell_x_time": ("A/m^2", N, "intracellular current density x at cell centres"),
    "I_cell_y_time": ("A/m^2", N, "intracellular current density y at cell centres"),
    "I_tot_x_time": ("A/m^2", G, "extracellular current density J_env_x"),
    "I_tot_y_time": ("A/m^2", G, "extracellular current density J_env_y"),
    "efield_gj_x_time": ("V/m", M, "intracellular field across gap junctions, x"),
    "efield_gj_y_time": ("V/m", M, "intracellular field across gap junctions, y"),
    "efield_ecm_x_time": ("V/m", G, "extracellular electric field x"),
    "efield_ecm_y_time": ("V/m", G, "extracellular electric field y"),
    "rho_cells_time": ("C/m^3", N, "net intracellular charge density"),
    "rate_NaKATP_time": ("mol/(m^2 s)", M, "Na/K-ATPase Na+ efflux rate (-f_Na)"),
    "P_cells_time": ("Pa", N, "total cell pressure"),
    "osmo_P_delta_time": ("Pa", N, "osmotic pressure difference"),
    "u_cells_x_time": ("m/s", N, "intracellular fluid velocity x"),
    "u_cells_y_time": ("m/s", N, "intracellular fluid velocity y"),
    "u_env_x_time": ("m/s", G, "extracellular fluid velocity x"),
    "u_env_y_time": ("m/s", G, "extracellular fluid velocity y"),
    "dx_cell_time": ("m", N, "cell displacement x"),
    "dy_cell_time": ("m", N, "cell displacement y"),
}

# Units of end-of-phase Simulator arrays; other numeric arrays are exported as "unknown".
STATE_UNITS = {
    **dict.fromkeys(("cc_cells", "cc_env", "cc_at_mem", "cc_er"), "mol/m^3"),
    **dict.fromkeys(("vm", "vm_ave", "v_cell", "v_env", "Phi_b", "vgj"), "V"),
    **dict.fromkeys(("Dm_cells", "Dm_base", "Dm_scheduled", "D_free", "D_gj", "D_env"), "m^2/s"),
    **dict.fromkeys(("J_cell_x", "J_cell_y", "J_env_x", "J_env_y", "Jn", "Jmem"), "A/m^2"),
    **dict.fromkeys(("Jgj", "Jc", "Jtx", "Jty"), "A/m^2"),
    **dict.fromkeys(("E_cell_x", "E_cell_y", "E_env_x", "E_env_y", "E_gj_x", "E_gj_y"), "V/m"),
    **dict.fromkeys(("fluxes_mem", "fluxes_gj", "fluxes_intra", "rate_NaKATP"), "mol/(m^2 s)"),
    **dict.fromkeys(("zs", "z_array", "gjopen", "channel_noise_factor"), "1"),
    **dict.fromkeys(("rho_cells", "rho_env"), "C/m^3"),
    **dict.fromkeys(("sigma_cell", "sigma_env"), "S/m"),
    "molar_mass": "kg/mol",
    "gjl": "m",
    "I_mem": "A",
    "P_cells": "Pa",
    "envV": "m^3",
}
for _ion in ("Na", "K", "Cl", "Ca", "H", "P", "M"):
    STATE_UNITS |= {
        f"c{_ion}cells": "mol/m^3",
        f"c{_ion}_env": "mol/m^3",
        f"Dm{_ion}": "m^2/s",
        f"Dgj{_ion}": "m^2/s",
        f"D{_ion}": "m^2/s",
        f"z{_ion}": "1",
        f"z2{_ion}": "1",
    }

# Key Parameters attributes (betse/science/parameters.py); every simple one is also dumped.
KEY_PARAMETERS = {
    "T": ("K", "temperature"),
    "cm": ("F/m^2", "specific membrane capacitance"),
    "tm": ("m", "membrane thickness (permeability = Dm / tm)"),
    "F": ("C/mol", "Faraday constant as used by BETSE"),
    "R": ("J/(mol K)", "gas constant as used by BETSE"),
    "kb": ("J/K", "Boltzmann constant"),
    "q": ("C", "elementary charge"),
    "NAv": ("1/mol", "Avogadro number"),
    "eo": ("F/m", "vacuum permittivity"),
    "er": ("1", "relative permittivity of electrolyte"),
    "dt": ("s", "time step of this phase"),
    "resample": ("s", "sampling interval of this phase"),
    "t_resample": ("steps", "resample / dt (float; BETSE truncates when indexing)"),
    "total_time": ("s", "configured duration of this phase"),
    "init_tsteps": ("steps", "int(INIT total / INIT dt)"),
    "sim_tsteps": ("steps", "int(SIM total / SIM dt)"),
    "init_time_step": ("s", "INIT dt"),
    "init_time_total": ("s", "INIT duration"),
    "init_time_sampling": ("s", "INIT sampling interval"),
    "sim_time_step": ("s", "SIM dt"),
    "sim_time_total": ("s", "SIM duration"),
    "sim_time_sampling": ("s", "SIM sampling interval"),
    "world_len": ("m", "configured world size"),
    "wsx": ("m", "actual world x size (BETSE adds 5 * lattice disorder * d_cell)"),
    "wsy": ("m", "actual world y size"),
    "cell_radius": ("m", "cell radius"),
    "d_cell": ("m", "cell diameter"),
    "cell_height": ("m", "cell height (z extent)"),
    "cell_space": ("m", "cell-cell spacing"),
    "cell_lattice_disorder": ("1", "lattice disorder (applied with unseeded RNG)"),
    "grid_size": ("1", "ECM grid points per side"),
    "is_ecm": ("bool", "extracellular spaces simulated"),
    "vol_env": ("m^3", "environment volume per membrane without extracellular spaces"),
    "scale_cell": ("1", "cell polygon scale about centres"),
    "true_cell_size": ("m", "true cell size"),
    "cell_polarizability": ("1", "cell polarizability"),
    "alpha_NaK": ("mol/(m^2 s)", "max Na/K-ATPase rate as used by pumpNaKATP (YAML: m/mol*s)"),
    "KmNK_Na": ("mol/m^3", "Na/K-ATPase Na half saturation"),
    "KmNK_K": ("mol/m^3", "Na/K-ATPase K half saturation"),
    "KmNK_ATP": ("mol/m^3", "Na/K-ATPase ATP half saturation"),
    "alpha_Ca": ("mol/(m^2 s)", "Ca-ATPase rate as used by pumpCaATP (YAML: m/mol*s)"),
    "KmCa_Ca": ("mol/m^3", "Ca-ATPase Ca half saturation"),
    "KmCa_ATP": ("mol/m^3", "Ca-ATPase ATP half saturation"),
    "cATP": ("mol/m^3", "fixed ATP"),
    "cADP": ("mol/m^3", "fixed ADP"),
    "cPi": ("mol/m^3", "fixed Pi"),
    "deltaGATP": ("J/mol", "ATP hydrolysis free energy"),
    "gj_surface": ("1", "gap-junction area as a fraction of cell area"),
    "gj_vthresh": ("mV", "gap-junction half-closing voltage (compared with vgj*1e3)"),
    "gj_vgrad": ("mV", "gap-junction gating window"),
    "gj_min": ("1", "minimum gap-junction open fraction"),
    "gj_radius": ("m", "gap-junction radius"),
    "gjl": ("m", "gap-junction length 2 tm + cell_space"),
    "v_sensitive_gj": ("bool", "voltage-sensitive gap junctions"),
    "D_tj": ("1", "tight-junction scaling"),
    "D_adh": ("1", "adherens-junction scaling"),
    "Dtj_rel": ("1", "relative tight-junction diffusion per ion"),
    "ions_dict": ("1", "enabled ions"),
    "cell_concs": ("mol/m^3", "configured initial intracellular concentrations"),
    "env_concs": ("mol/m^3", "configured initial environment concentrations"),
    "mem_perms": ("m^2/s", "configured default membrane diffusion constants Dm"),
    "free_diff": ("m^2/s", "free diffusion constants"),
    "ion_charge": ("1", "valences"),
    "molar_mass": ("kg/mol", "molar masses"),
    "ion_long_name": ("", "ion names"),
    "GHK_calc": ("bool", "Goldman calculator"),
    "dynamic_noise": ("bool", "dynamic noise"),
    "dynamic_noise_level": ("1", "dynamic noise level"),
    "channel_noise_level": ("1", "static K+ channel noise level"),
    "Ca_dyn": ("bool", "calcium dynamics"),
    "molecules_enabled": ("bool", "general network"),
    "grn_enabled": ("bool", "gene regulatory network"),
    "fluid_flow": ("bool", "fluid flow"),
    "deformation": ("bool", "deformation"),
    "deform_osmo": ("bool", "osmotic deformation"),
}

SCALAR_UNITS = {
    "T": "K",
    "ko_env": "1/m (Debye screening wavenumber, fixed per phase at its start)",
    "ko_cell": "1/m",
    "c_env_bound": "mol/m^3 (per ion, global boundary concentration)",
    "bound_V": "V (global boundary voltages T/B/L/R)",
    "cdl": "cells",
    "mdl": "membranes",
    "edl": "environment points (ECM grid points, else membranes)",
}

STATIC_NOT_SAVED = [
    "INIT state at t = 0 (before the first update) is not saved, so Vmem/concentrations at "
    "t = 0 are unavailable; only configured initial values (cell_concs/env_concs) are.",
    "Unsampled steps are not saved. A phase's final state is in *_final.npz; it is a history "
    "sample only if the last step index is sampled (see time.<phase>).",
    "Per-ion membrane / gap-junction flux histories are not saved; fluxes_mem/fluxes_gj "
    "hold only the last update (*_final.npz).",
    "Membrane lengths are not stored (mem_sa = length * p.cell_height).",
    "No gap-junction conductance is stored; BETSE stores D_gj, gjopen, gj_surface, gj_len.",
    "No channel gating variables are stored in time series; channel effects appear only "
    "through Dm_cells (dd_time).",
    "The RNG state is not saved; BETSE never seeds NumPy's global RNG, so lattice disorder "
    "and single-cell noise differ between independent `betse seed` runs.",
]


# ............................................................ NumPy-only helpers


class NotPlain(TypeError):
    """Value is not a simple scalar/collection."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def array_sha256(array):
    """SHA-256 of the C-contiguous array bytes (shape and dtype are recorded apart)."""
    array = np.asarray(array)
    if array.dtype.hasobject:
        raise TypeError("object arrays are not plain data")
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def flatten_ragged(items):
    """Ragged sequence -> (flat, offsets); item i is flat[offsets[i]:offsets[i + 1]]."""
    parts = [np.asarray(item) for item in items]
    filled = [part for part in parts if part.size]
    dtype = np.result_type(*filled) if filled else np.dtype(np.float64)
    trailing = filled[0].shape[1:] if filled else ()
    parts = [
        part.astype(dtype, copy=False) if part.size else np.zeros((0, *trailing), dtype)
        for part in parts
    ]
    offsets = np.zeros(len(parts) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([len(part) for part in parts])
    flat = np.concatenate(parts, axis=0) if parts else np.zeros((0,), dtype)
    return flat, offsets


def sample_schedule(n_steps, dt, labels):
    """Match BETSE sample labels to its step grid (betse/science/sim.py, _plot_loop).

    BETSE labels steps ``np.linspace(0, n_steps * dt, n_steps)`` and records a
    sample after the update of step k, so sample k holds the state after
    ``k + 1`` updates of ``dt``. Unmatched labels get index -1 and NaN elapsed.
    """
    grid = np.linspace(0, n_steps * dt, n_steps)
    labels = np.asarray(labels, dtype=np.float64)
    index = np.full(labels.shape, -1, dtype=np.int64)
    for i, label in enumerate(labels):
        hits = np.flatnonzero(grid == label)
        if hits.size:
            index[i] = hits[0]
    elapsed = np.where(index >= 0, (index + 1) * dt, np.nan)
    spacing = float(grid[1] - grid[0]) if n_steps > 1 else None
    return {"step_index": index, "elapsed_after_update_s": elapsed, "label_spacing_s": spacing}


def to_plain(value, depth=0):
    """JSON-safe copy of a simple value, else raise NotPlain."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        value = float(value)
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if depth < 3 and isinstance(value, dict) and len(value) <= 64:
        return {str(k): to_plain(v, depth + 1) for k, v in value.items()}
    if depth < 3 and isinstance(value, (list, tuple)) and len(value) <= 64:
        return [to_plain(v, depth + 1) for v in value]
    if isinstance(value, np.ndarray) and value.size <= 64 and value.dtype.kind in "biuf":
        return to_plain(value.tolist(), depth + 1)
    raise NotPlain(type(value).__name__)


def json_floats(values):
    return [None if not math.isfinite(v) else float(v) for v in np.asarray(values, float)]


def write_npz(path, arrays):
    """Write {name: (array, meta)} uncompressed and exclusively; return the manifest entry."""
    entries, data = {}, {}
    for name, (array, meta) in arrays.items():
        array = np.asarray(array)
        if array.dtype.hasobject:
            raise TypeError(f"{name}: object arrays are not plain data")
        data[name] = array
        entries[name] = {
            "shape": list(array.shape),
            "dtype": array.dtype.str,
            "sha256": array_sha256(array),
            **meta,
        }
    with Path(path).open("xb") as stream:
        np.savez(stream, **data)
    return {"sha256": sha256_file(path), "size_bytes": Path(path).stat().st_size, "arrays": entries}


def verify_files(directory, files):
    """Problems comparing NPZ files in ``directory`` with manifest ``files`` entries."""
    directory, problems = Path(directory), []
    if not isinstance(files, dict) or not files:
        return ["manifest lists no files"]
    for name, entry in files.items():
        path = directory / name
        if Path(name).name != name or not path.is_file():
            problems.append(f"{name}: missing or not a plain file name")
            continue
        if sha256_file(path) != entry.get("sha256"):
            problems.append(f"{name}: file sha256 differs")
        if path.stat().st_size != entry.get("size_bytes"):
            problems.append(f"{name}: file size differs")
        try:
            with np.load(path, allow_pickle=False) as npz:
                stored = {key: npz[key] for key in npz.files}
        except (OSError, ValueError) as error:
            problems.append(f"{name}: unreadable without pickle: {error!r}")
            continue
        declared = entry.get("arrays", {})
        for key in sorted(set(declared) ^ set(stored)):
            where = "manifest" if key in declared else "file"
            problems.append(f"{name}: array {key!r} only in the {where}")
        for key in sorted(set(declared) & set(stored)):
            array, row = stored[key], declared[key]
            if list(array.shape) != row.get("shape"):
                problems.append(f"{name}:{key}: shape {list(array.shape)} != {row.get('shape')}")
            if array.dtype.str != row.get("dtype"):
                problems.append(f"{name}:{key}: dtype {array.dtype.str} != {row.get('dtype')}")
            if array_sha256(array) != row.get("sha256"):
                problems.append(f"{name}:{key}: array sha256 differs")
            if not isinstance(row.get("units"), str):
                problems.append(f"{name}:{key}: no units declared")
    return problems


def verify_extract(directory):
    """Problems found in an extraction directory (empty list: consistent)."""
    try:
        manifest = json.loads((Path(directory) / "manifest.json").read_text())
    except (OSError, ValueError) as error:
        return [f"manifest unreadable: {error!r}"]
    problems = []
    if manifest.get("kind") != KIND:
        problems.append(f"unexpected kind {manifest.get('kind')!r}")
    if manifest.get("status") != "complete":
        problems.append(f"status is {manifest.get('status')!r}")
    return problems + verify_files(directory, manifest.get("files"))


def _load_npz(path):
    with np.load(path, allow_pickle=False) as npz:
        return {key: npz[key] for key in npz.files}


def _difference(x, y):
    if x.shape != y.shape or x.dtype.kind != y.dtype.kind:
        return {"equal": False, "shape_a": list(x.shape), "shape_b": list(y.shape)}
    equal = bool(np.array_equal(x, y, equal_nan=x.dtype.kind == "f"))
    row = {"equal": equal, "shape": list(x.shape)}
    if not equal and x.size and x.dtype.kind in "biuf":
        delta = np.abs(x.astype(np.float64) - y.astype(np.float64))
        row["max_abs_diff"] = float(np.nanmax(delta))
        row["max_abs_a"] = float(np.nanmax(np.abs(x.astype(np.float64))))
    return row


def _compare_sets(a, b):
    rows = {name: _difference(a[name], b[name]) for name in sorted(set(a) & set(b))}
    only = sorted(set(a) ^ set(b))
    return rows, only, not only and all(row["equal"] for row in rows.values())


def compare_extracts(dir_a, dir_b):
    """Geometry identity and step-aligned history/final differences of two extractions.

    History samples are paired by BETSE step index (manifest time.<phase>.step_index),
    so runs with different sampling intervals compare at their common steps.
    """
    dir_a, dir_b = Path(dir_a), Path(dir_b)
    manifests = [json.loads((d / "manifest.json").read_text()) for d in (dir_a, dir_b)]
    geometry, only, same = _compare_sets(
        _load_npz(dir_a / FILES["geometry"]), _load_npz(dir_b / FILES["geometry"])
    )
    result = {
        "a": str(dir_a),
        "b": str(dir_b),
        "geometry_identical": same,
        "geometry_arrays_only_in_one": only,
        "geometry": geometry,
        "phases": {},
    }
    for phase in ("init", "sim"):
        times = [m.get("time", {}).get(phase) for m in manifests]
        if not all(times):
            continue
        index = [np.asarray(t["step_index"]) for t in times]
        common = np.intersect1d(index[0][index[0] >= 0], index[1][index[1] >= 0])
        rows = [np.searchsorted(i, common) if np.all(np.diff(i) > 0) else None for i in index]
        if rows[0] is None or rows[1] is None:
            raise ValueError(f"{phase}: step indices are not strictly increasing")
        histories = [_load_npz(d / FILES[f"{phase}_history"]) for d in (dir_a, dir_b)]
        history, only_h, same_h = _compare_sets(
            {k: v[rows[0]] for k, v in histories[0].items() if k != "time"},
            {k: v[rows[1]] for k, v in histories[1].items() if k != "time"},
        )
        final, only_f, same_f = _compare_sets(
            _load_npz(dir_a / FILES[f"{phase}_final"]), _load_npz(dir_b / FILES[f"{phase}_final"])
        )
        result["phases"][phase] = {
            "common_step_indices": common.tolist(),
            "history_identical_at_common_steps": same_h,
            "history_arrays_only_in_one": only_h,
            "history": history,
            "final_identical": same_f,
            "final_arrays_only_in_one": only_f,
            "final": final,
        }
    return result


# ............................................................ BETSE-side extraction


def _load_sibling(name):
    spec = importlib.util.spec_from_file_location(f"_cells_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _isolate_home(home):
    """BETSE resolves its dot directory from HOME; keep it inside the extract output."""
    (home / ".config/matplotlib").mkdir(parents=True, exist_ok=True)
    os.environ.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_CACHE_HOME=str(home / ".cache"),
        MPLCONFIGDIR=str(home / ".config/matplotlib"),
        MPLBACKEND="Agg",
    )


def _is_ragged(value):
    if isinstance(value, np.ndarray):
        return value.dtype.hasobject
    try:
        lengths = {len(item) for item in value}
    except TypeError:
        return False
    return len(lengths) > 1


def extract_geometry(cells):
    arrays, missing, other = {}, {}, {}
    for name, (units, axes, description) in GEOMETRY.items():
        value = getattr(cells, name, None)
        if value is None:
            missing[name] = "absent or None in the saved Cells object"
            continue
        meta = {"units": units, "axes": list(axes), "description": description}
        meta["source"] = f"cells.{name}"
        if _is_ragged(value):
            flat, offsets = flatten_ragged(value)
            arrays[f"{name}_flat"] = (flat, meta)
            arrays[f"{name}_offsets"] = (
                offsets,
                {
                    "units": "index",
                    "axes": ["items + 1"],
                    "description": f"offsets into {name}_flat",
                    "source": f"cells.{name}",
                },
            )
            continue
        array = np.asarray(value)
        if array.dtype.hasobject or array.dtype.kind not in "biuf":
            missing[name] = f"not plain numeric data ({type(value).__name__})"
            continue
        if units == "index" and array.size == 0:
            array = array.astype(np.int64)  # an empty BETSE list would load as float64
        arrays[name] = (array, meta)
    for name, value in sorted(vars(cells).items()):
        if name not in GEOMETRY:
            shape = getattr(value, "shape", None)
            other[name] = type(value).__name__ + (f" {list(shape)}" if shape is not None else "")
    return arrays, missing, other


def extract_history(sim, phase):
    arrays, empty, unexported = {}, [], {}
    for name in sorted(n for n in vars(sim) if n == "time" or n.endswith("_time")):
        value = getattr(sim, name)
        if not isinstance(value, (list, tuple, np.ndarray)) or len(value) == 0:
            empty.append(name)
            continue
        items = list(value)
        try:
            array = np.stack([np.asarray(item) for item in items])
        except ValueError:
            shapes = sorted({tuple(np.shape(item)) for item in items})
            unexported[name] = f"ragged samples {shapes[:4]}"
            continue
        if array.dtype.hasobject:
            unexported[name] = "object samples"
            continue
        units, axes, description = HISTORY.get(name, ("unknown", None, "BETSE Simulator list"))
        if axes is None or len(axes) != array.ndim - 1:
            axes = tuple(f"dim{i}" for i in range(1, array.ndim))
        meta = {
            "units": units,
            "axes": ["samples", *axes],
            "description": description,
            "source": f"{phase} sim.{name}",
        }
        arrayish = [item for item in items if isinstance(item, np.ndarray)]
        if len({id(item) for item in arrayish}) < len(arrayish):
            meta["aliased_samples"] = True
            meta["description"] += (
                " [BETSE appended the same array object more than once: aliased entries "
                "hold its end-of-phase values, not history]"
            )
        arrays[name] = (array, meta)
    return arrays, empty, unexported


def extract_final(sim, phase):
    arrays, scalars, skipped = {}, {}, {}
    for name, value in sorted(vars(sim).items()):
        if name == "time" or name.endswith("_time"):
            continue
        array = None
        if isinstance(value, np.ndarray) and value.dtype.kind in "biuf":
            array = value
        elif (
            isinstance(value, list)
            and value
            and all(isinstance(v, np.ndarray) and v.dtype.kind in "biuf" for v in value)
        ):
            try:
                array = np.stack(value)
            except ValueError:
                skipped[name] = "ragged list of arrays"
                continue
        if array is not None:
            if array.size > MAX_STATE_ELEMENTS:
                skipped[name] = f"{list(array.shape)} exceeds {MAX_STATE_ELEMENTS} elements"
                continue
            arrays[name] = (
                array,
                {
                    "units": STATE_UNITS.get(name, "unknown"),
                    "axes": [f"dim{i}" for i in range(array.ndim)],
                    "description": f"Simulator.{name} at the end of {phase}",
                    "source": f"{phase} sim.{name}",
                },
            )
            continue
        try:
            scalars[name] = to_plain(value)
        except NotPlain:
            skipped[name] = type(value).__name__
    return arrays, scalars, skipped


def ion_table(sim, p):
    enabled = [name for name, on in p.ions_dict.items() if on]
    index = {name: int(getattr(sim, f"i{name}")) for name in enabled}
    order = sorted(enabled, key=index.get)
    return {
        "order": order,
        "index": index,
        "long_names": [sim.ionlabel[index[name]] for name in order],
        "valence": [int(z) for z in np.asarray(sim.zs)],
        "molar_mass_kg_per_mol": [float(m) for m in np.asarray(sim.molar_mass)],
        "free_diffusion_m2_per_s": [float(d) for d in np.asarray(sim.D_free)],
        "configured_membrane_D_m2_per_s": {n: to_plain(p.mem_perms[n]) for n in order},
        "configured_initial_cell_mol_per_m3": {n: to_plain(p.cell_concs[n]) for n in order},
        "configured_initial_env_mol_per_m3": {n: to_plain(p.env_concs[n]) for n in order},
        "moving_ions": [int(i) for i in sim.movingIons],
        "consistent_index": all(sim.ionlabel[index[n]] == p.ion_long_name[n] for n in order),
    }


def parameters(p):
    key, every = {}, {}
    for name, (units, description) in KEY_PARAMETERS.items():
        row = {"units": units, "description": description}
        try:
            row["value"] = to_plain(getattr(p, name))
        except AttributeError:
            row.update(value=None, absent=True)
        except NotPlain as error:
            row.update(value=None, not_plain=str(error))
        key[name] = row
    for name, value in sorted(vars(p).items()):
        if not name.startswith("_"):
            try:
                every[name] = to_plain(value)
            except NotPlain:
                pass
    return key, every


def geometry_consistency(reference, others):
    names = (
        "cell_centres",
        "mem_mids_flat",
        "mem_sa",
        "cell_vol",
        "mem_to_cells",
        "xypts",
        "nn_i",
        "cell_nn_i",
    )
    return {
        label: {
            name: bool(
                np.array_equal(
                    np.asarray(getattr(reference, name)), np.asarray(getattr(cells, name))
                )
            )
            for name in names
            if hasattr(reference, name) and hasattr(cells, name)
        }
        for label, cells in others.items()
    }


def _phase_pickles(result, run_dir):
    pickles = {}
    for phase in PHASE_KINDS:
        row = result.get("phases", {}).get(phase)
        if not row:
            continue
        names = row.get("pickles", [])
        if len(names) != 1:
            raise RuntimeError(f"{phase}: expected one pickle, run recorded {names}")
        recorded = (row["outputs"]["created"] | row["outputs"]["modified"])[names[0]]
        pickles[phase] = {"path": str(run_dir / "config" / names[0]), "recorded": recorded}
    if not {"init", "sim"} & set(pickles):
        raise RuntimeError("run has neither an INIT nor a SIM pickle")
    return pickles


def _phase_time(sim, p, phase):
    n_steps = int(p.init_tsteps if phase == "init" else p.sim_tsteps)
    schedule = sample_schedule(n_steps, p.dt, sim.time)
    index = schedule["step_index"]
    return {
        "dt_s": float(p.dt),
        "n_steps": n_steps,
        "sampling_interval_s": float(p.resample),
        "t_resample_steps": float(p.t_resample),
        "n_samples": len(sim.time),
        "label_spacing_s": schedule["label_spacing_s"],
        "step_index": index.tolist(),
        "elapsed_after_update_s": json_floats(schedule["elapsed_after_update_s"]),
        "labels_match_betse_step_grid_exactly": bool(index.size and np.all(index >= 0)),
        "final_state_elapsed_s": n_steps * float(p.dt),
        "last_sample_is_final_state": bool(index.size and index[-1] == n_steps - 1),
        "derivation": "labels are BETSE's (history 'time'); step_index/elapsed match them to "
        "np.linspace(0, n_steps*dt, n_steps) with k+1 updates (sim.py _plot_loop)",
    }


def _extract_with_betse(pickles, out):
    import betse
    from betse.science import filehandling as fh

    loaded = {}
    if "seed" in pickles:
        cells, p = fh.loadWorld(pickles["seed"]["path"])
        loaded["seed"] = (None, cells, p)
    for phase in ("init", "sim"):
        if phase in pickles:
            loaded[phase] = fh.loadSim(pickles[phase]["path"])
    last = "sim" if "sim" in loaded else "init"
    sim_last, cells, p_last = loaded[last]
    files, finals, times, gaps, notes = {}, {}, {}, {}, []

    arrays, missing, other = extract_geometry(cells)
    files[FILES["geometry"]] = write_npz(out / FILES["geometry"], arrays)
    geometry = {
        "source": f"{last} pickle Cells object",
        "missing": missing,
        "other_cells_attributes": other,
        "identical_in_other_pickles": geometry_consistency(
            cells, {k: v[1] for k, v in loaded.items() if k != last}
        ),
        "counts": {
            "cells": int(len(cells.cell_i)),
            "membranes": int(len(cells.mem_i)),
            "ecm_grid_points": int(len(cells.xypts)),
            "ecm_grid_shape": list(np.shape(cells.X)),
        },
    }
    for phase in ("init", "sim"):
        if phase not in loaded:
            continue
        sim, _, p = loaded[phase]
        arrays, empty, unexported = extract_history(sim, phase)
        files[FILES[f"{phase}_history"]] = write_npz(out / FILES[f"{phase}_history"], arrays)
        gaps[phase] = {"empty_time_series": empty, "unexported_time_series": unexported}
        aliased = sorted(n for n, (_, meta) in arrays.items() if meta.get("aliased_samples"))
        if aliased:
            notes.append(f"{phase}: aliased time series {aliased}")
        times[phase] = _phase_time(sim, p, phase)
        arrays, scalars, skipped = extract_final(sim, phase)
        files[FILES[f"{phase}_final"]] = write_npz(out / FILES[f"{phase}_final"], arrays)
        finals[phase] = {
            "scalars": scalars,
            "scalar_units": {k: v for k, v in SCALAR_UNITS.items() if k in scalars},
            "skipped": skipped,
        }
    key, every = {}, {}
    for phase in ("init", "sim"):
        if phase in loaded:
            key[phase], every[phase] = parameters(loaded[phase][2])
    return {
        "betse": {"version": betse.__version__, "package": str(Path(betse.__file__).parent)},
        "numpy": np.__version__,
        "files": files,
        "geometry": geometry,
        "final_state": finals,
        "ions": ion_table(sim_last, p_last),
        "time": times,
        "parameters": {"key": key, "all_simple_attributes": every},
        "not_saved": {"time_series": gaps, "static": STATIC_NOT_SAVED},
        "notes": notes,
    }


def cmd_extract(args):
    run_dir = Path(args.run).absolute()
    out = Path(args.out).absolute() if args.out else run_dir.parent / "extract"
    if out.exists():
        raise SystemExit(f"Refusing existing output directory: {out}")
    result_path = run_dir / "result.json"
    if not result_path.is_file():
        raise SystemExit(f"No result.json in {run_dir} (failed or incomplete run)")
    out.mkdir(parents=True)
    runner = _load_sibling("betse_reference_run")
    record = {
        "kind": KIND,
        "status": "running",
        "created_utc": utc_now(),
        "command": sys.argv,
        "python": sys.version,
    }
    try:
        record["provenance"] = runner.git_provenance(
            [Path(__file__), HERE / "betse_reference_run.py"], out / "git-dirty.diff"
        )
        result = json.loads(result_path.read_text())
        if result.get("status") != "complete":
            raise RuntimeError(f"run status is {result.get('status')!r}")
        pickles = _phase_pickles(result, run_dir)
        for phase, row in pickles.items():
            now = {
                "size_bytes": Path(row["path"]).stat().st_size,
                "sha256": sha256_file(row["path"]),
            }
            if now != row.pop("recorded"):
                raise RuntimeError(f"{phase} pickle changed since the run: {row['path']}")
            row.update(now)
        record["source_run"] = {
            "directory": str(run_dir),
            "result_json": {"path": str(result_path), "sha256": sha256_file(result_path)},
            "case": result.get("case"),
            "config_file": result["config"]["config_file"],
            "config_file_sha256": result["config"]["config_file_sha256"],
            "cells_revision": result.get("provenance", {}).get("revision"),
            "betse_versions": result.get("betse_environment", {}).get("versions"),
            "pickles": pickles,
        }
        _isolate_home(out / "home")
        record.update(_extract_with_betse(pickles, out))
        problems = verify_files(out, record["files"])
        if problems:
            raise RuntimeError(f"self-verification failed: {problems[:5]}")
        record["status"] = "complete"
        record["finished_utc"] = utc_now()
        runner.write_json(out / "manifest.json", record)
        print(json.dumps({"status": "complete", "manifest": str(out / "manifest.json")}))
        return 0
    except Exception as error:
        record["status"] = "failed"
        record["finished_utc"] = utc_now()
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["outputs_preserved"] = True
        runner.write_json(out / "failure.json", record)
        print(json.dumps({"status": "failed", "failure": str(out / "failure.json")}))
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract", help="extract NPZ + manifest (needs BETSE)")
    extract.add_argument("--run", required=True, help="betse_reference_run.py run directory")
    extract.add_argument("--out", help="fresh output directory (default RUN/../extract)")
    verify = sub.add_parser("verify", help="check manifest against NPZ files (NumPy only)")
    verify.add_argument("directory")
    compare = sub.add_parser("compare", help="compare two extractions (NumPy only)")
    compare.add_argument("a")
    compare.add_argument("b")
    compare.add_argument("--out", help="write the comparison JSON here (exclusive)")
    args = parser.parse_args(argv)
    if args.command == "extract":
        return cmd_extract(args)
    if args.command == "compare":
        result = compare_extracts(args.a, args.b)
        text = json.dumps(result, indent=2, sort_keys=True)
        if args.out:
            with Path(args.out).open("x") as stream:
                stream.write(text + "\n")
        summary = {"geometry_identical": result["geometry_identical"]}
        for phase, row in result["phases"].items():
            summary[phase] = {
                "common_steps": len(row["common_step_indices"]),
                "history_identical_at_common_steps": row["history_identical_at_common_steps"],
                "final_identical": row["final_identical"],
            }
        print(json.dumps(summary, indent=2))
        return 0
    problems = verify_extract(args.directory)
    print(json.dumps({"consistent": not problems, "problems": problems}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
