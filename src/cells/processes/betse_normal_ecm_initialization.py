"""Explicit pre-bootstrap owner admission; no seed, init or pickle execution.

The native SIM runner loads a hot simulator, reinitializes dynamics, clears
storage, then calls update_V once. Capture is passive at the declared boundary
before that call. A complete compatible owner snapshot can enter the existing
field bootstrap without source.cold(). Missing stores stay missing. Capturing
native objects establishes their contents, not the seed/init/load history.
"""

import hashlib
import inspect
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_grn_source as source
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_mechanics_join as mechanics
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_field_join as field
from cells.processes import betse_normal_ecm_mechanics_join as mechanical_field
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_normal_ecm_prebootstrap_owner_admission_v1_5_0@1"
SOURCE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
STAGE = "normal_SIM_after_init_dynamics_clear_storage_before_bootstrap_update_V"
DECLARATION_KIND = "cells.normal_ecm_initialization_boundary_declaration@1"
NATIVE_TYPES = {
    "sim": (
        "betse.science.sim.Simulator",
        "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    ),
    "cells": (
        "betse.science.cells.Cells",
        "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
    ),
    "parameters": (
        "betse.science.parameters.Parameters",
        "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e",
    ),
}
NATIVE_DESCRIPTOR_SOURCES = {
    "betse/lib/yaml/yamlalias.py": (
        "cc87d9403c088a936a00187e33417b05a"
        "e2d26f64ee02b37d7857504cf3f0e37"
    ),
    "betse/util/type/descriptor/expralias.py": (
        "96f5095f544894dd880a63cbdcb6333db"
        "d178e0d64ed173b6afec384878a1986"
    ),
}
NATIVE_PARAMETER_ALIASES = ("solver_type", "cell_radius", "is_ecm", "cell_polarizability")
SIM_FIELDS = (
    "cc_cells",
    "cc_at_mem",
    "cc_env",
    "vm",
    "fluxes_mem",
    "fluxes_gj",
    "fluxes_env_x",
    "fluxes_env_y",
    "vgj",
    "Egj",
    "E_gj_x",
    "E_gj_y",
    "gjopen",
    "D_free",
    "Dm_cells",
    "D_gj",
    "D_env",
    "TJ_modulator",
    "D_env_weight",
    "D_env_weight_base",
    "TJ_targets",
    "zs",
    "movingIons",
    "ionlabel",
    "T",
    "cdl",
    "mdl",
    "edl",
    "sigma",
    "ko_env",
    "ko_cell",
    "sigma_cell",
    "sigma_env",
    "gj_block",
    "NaKATP_block",
    "c_env_bound",
    "bound_V",
    "smooth_weight_mem",
    "smooth_weight_o",
    "rho_channel",
    "rho_pump",
    "CaATP_block",
    "met_concs",
    "endo_retic",
    "rate_CaATP",
    "P_cells",
    "P_base",
    "P_mod",
    "Dm_base",
    "Dm_scheduled",
    "channel_noise_factor",
    "extra_rho_cells",
    "extra_rho_env",
    "extra_J_mem",
    "extra_Jenv_x",
    "extra_Jenv_y",
    "rho_cells",
    "J_cell_x",
    "J_cell_y",
    "E_cell_x",
    "E_cell_y",
    "E_env_x",
    "E_env_y",
    "osmo_P_cell",
    "osmo_P_env",
    "osmo_P_delta",
    "u_osmo",
    "div_u_osmo",
    "PP",
    "gPxc",
    "gPyc",
    "d_cells_x",
    "d_cells_y",
    "u_cells_x",
    "u_cells_y",
    "u_env_x",
    "u_env_y",
)
CELL_FIELDS = (
    "cell_i",
    "mem_i",
    "mem_to_cells",
    "nn_i",
    "bflags_mems",
    "gj_len",
    "gj_default_weights",
    "mem_sa",
    "cell_sa",
    "cell_vol",
    "cell_centres",
    "mem_mids_flat",
    "mem_vects_flat",
    "M_sum_mems",
    "num_mems",
    "R_rads",
    "diviterm",
    "X",
    "Y",
    "xypts",
    "delta",
    "map_ij2k",
    "map_cell2ecm",
    "map_mem2ecm",
    "memSa_per_envSquare",
    "mems_per_envSquare",
    "true_ecm_vol",
    "M_divmap_mem2ecm",
    "cell2env_corrF",
    "lapENVinv",
    "lapENV_P_inv",
    "xmin",
    "xmax",
    "ymin",
    "ymax",
    "lapGJ",
    "lapGJinv",
    "cell_nn_i",
    "nn_len",
    "nn_tx",
    "nn_ty",
    "cell_nn_tx",
    "cell_nn_ty",
    "mem_verts",
    "cell_verts",
    "all_bound_mem_inds",
    "interior_bound_mem_inds",
    "ecm_inds_bound_cell",
    "mem_vol",
)
PARAMETER_FIELDS = (
    "is_ecm",
    "solver_type",
    "fluid_flow",
    "td_deform",
    "v_sensitive_gj",
    "Ca_dyn",
    "molecules_enabled",
    "grn_enabled",
    "ions_dict",
    "F",
    "R",
    "T",
    "q",
    "kb",
    "NAv",
    "er",
    "eo",
    "mu",
    "cell_height",
    "cell_space",
    "cell_radius",
    "true_cell_size",
    "tm",
    "gj_surface",
    "cluster_open",
    "fast_update_ecm",
    "sharpness",
    "smooth_cells",
    "cm",
    "cell_polarizability",
    "dt",
    "sim_tsteps",
    "alpha_Ca",
    "cATP",
    "cADP",
    "cPi",
    "KmCa_Ca",
    "KmCa_ATP",
    "deltaGATP",
    "deformation",
    "deform_osmo",
    "fixed_cluster_bound",
    "galvanotropism",
    "lame_mu",
    "aquaporins",
    "mu_water",
    "rho",
    "channel_noise_level",
)
MESH_FIELDS = ("vor_edge_len", "tri_edge_len", "delta_tri_0", "delta_tri_0_inv", "vor_sa")
DISPLAY_FIELDS = ("cell_centres", "cell_verts", "mem_verts")
GROUPS = {
    "sim": SIM_FIELDS,
    "cells": CELL_FIELDS,
    "parameters": PARAMETER_FIELDS,
    "mesh": MESH_FIELDS,
    "display": DISPLAY_FIELDS,
}
EXCLUDED = ("channels", "transporters", "mitochondria", "standalone_molecules")
MAX_ELEMENTS = 1_000_000


@dataclass(frozen=True)
class Boundary:
    declaration: object
    observation_kind: str
    owners: object
    network_cache: object
    excluded_owner_state: object
    source_objects: object
    identity: str


@dataclass(frozen=True)
class Handoff:
    boundary_identity: str
    binding_identity: str
    parent: object
    provenance: object
    identity: str


class InitializationRejected(ValueError):
    def __init__(self, reason, *, stage, boundary=None, partial=None):
        super().__init__("ECM owner handoff refused at " + stage + ": " + str(reason))
        self.stage = stage
        self.boundary = boundary
        self.partial = partial


def _copy(value, depth=0):
    """Copy numeric contents without executing owner methods or filling stores."""
    if depth > 24:
        raise ValueError("Owner snapshot exceeds bounded nesting")
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in "bifu" or value.size > MAX_ELEMENTS:
            raise ValueError("Require bounded real/bool owner arrays")
        return ions.freeze(value)
    if isinstance(value, np.generic):
        # The existing cache/digest contract distinguishes native float64
        # scalars from Python floats. They are immutable; preserve their bits
        # and type rather than changing the supplied owner's representation.
        if type(value) is not np.float64:
            raise ValueError(
                "Require NumPy float64 owner scalars; other scalar dtypes are unsupported"
            )
        return value
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, Mapping):
        if len(value) > MAX_ELEMENTS or any(type(k) not in (str, int) for k in value):
            raise ValueError("Require bounded named or indexed owner fields")
        return ions.freeze({k: _copy(v, depth + 1) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_ELEMENTS:
            raise ValueError("Owner sequence exceeds capture bound")
        return tuple(_copy(v, depth + 1) for v in value)
    raise ValueError("Uncaptured owner type: " + type(value).__qualname__)


def _attributes(owner):
    return owner if isinstance(owner, Mapping) else vars(owner)


def _entry(owner, key):
    values = {} if owner is None else _attributes(owner)
    if key not in values:
        return dict(present=False)
    try:
        value = values[key]
        # SolverType is recorded by its actual enum name; no enum is invented.
        if key == "solver_type" and hasattr(value, "name"):
            value = value.name
        if key == "cell_verts" and isinstance(value, np.ndarray) and value.dtype.kind == "O":
            # Native ragged display vertices are an object array. Retain every
            # coordinate as nested numeric data; never infer polygon closure.
            value = value.tolist()
        return dict(present=True, captured=True, value=_copy(value))
    except Exception as error:
        return dict(present=True, captured=False, error=str(error), type=type(values[key]).__name__)


def _declaration(raw):
    if (
        not isinstance(raw, Mapping)
        or set(raw) != {"kind", "stage", "geometry_classification", "upstream_evidence"}
        or raw["kind"] != DECLARATION_KIND
        or raw["stage"] != STAGE
        or raw["geometry_classification"] not in ("supplied_layout", "unqualified_native_layout")
    ):
        raise ValueError(
            "Declare the exact pre-bootstrap supplied-owner boundary without a native-chain claim"
        )
    evidence = raw["upstream_evidence"]
    if not isinstance(evidence, (tuple, list)) or not evidence:
        raise ValueError(
            "Link original owner evidence; links do not establish native initialization"
        )
    for row in evidence:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"path", "sha256"}
            or type(row["path"]) is not str
            or not row["path"]
            or type(row["sha256"]) is not str
            or len(row["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in row["sha256"])
        ):
            raise ValueError("Require evidence paths and SHA256 content identifiers")
    return _copy(raw)


def boundary_record(value):
    return (
        LAW_ID,
        SOURCE_REVISION,
        value.declaration,
        value.observation_kind,
        value.owners,
        value.network_cache,
        value.excluded_owner_state,
        value.source_objects,
    )


def capture_supplied(owners, network_cache, excluded_owner_state, declaration):
    """Retain an explicitly supplied owner boundary, including absence/errors."""
    if set(owners) != set(GROUPS) or set(excluded_owner_state) != set(EXCLUDED):
        raise ValueError("Declare every owner group and excluded-owner observation")
    # False means actually observed empty/disabled, never an inferred default.
    if any(type(v) is not bool for v in excluded_owner_state.values()):
        raise ValueError("Require explicit excluded-owner presence booleans")
    groups = {
        group: {key: _entry(owners[group], key) for key in keys} for group, keys in GROUPS.items()
    }
    cache_entry = _entry({"owner": network_cache}, "owner")
    result = Boundary(
        _declaration(declaration),
        "supplied_owner_boundary",
        _copy(groups),
        _copy(cache_entry),
        _copy(excluded_owner_state),
        _copy({}),
        "",
    )
    return replace(result, identity=ions.digest(boundary_record(result)))


def capture_native(phase, declaration):
    """Read pinned native objects at a caller-declared seam, without advancing."""
    owners = dict(sim=phase.sim, cells=phase.cells, parameters=phase.p)
    pins = {}
    for name, owner in owners.items():
        cls = type(owner)
        qualified = cls.__module__ + "." + cls.__qualname__
        expected_type, expected_sha = NATIVE_TYPES[name]
        if qualified != expected_type:
            raise ValueError("Require the pinned native owner class: " + name)
        path = Path(inspect.getfile(cls))
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError("Require the pinned native owner class/source: " + name)
        pins[name] = dict(type=qualified, source=str(path), sha256=actual_sha)
    kind = getattr(phase.kind, "name", None)
    if kind != "SIM":
        raise ValueError("This boundary is the ordinary SIM phase, after dynamics reinitialization")
    n, m, e = (vars(phase.sim)[key] for key in ("cdl", "mdl", "edl"))
    if not 1 <= n <= 16 or not 1 <= m <= 128 or not 1 <= e <= 49:
        raise ValueError("Do not widen the frozen native owner capture domain")
    native_root = Path(pins["parameters"]["source"]).parents[2]
    for relative, expected_sha in NATIVE_DESCRIPTOR_SOURCES.items():
        actual_sha = hashlib.sha256((native_root / relative).read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError("Changed native YAML descriptor source: " + relative)
        pins[relative] = dict(source=str(native_root / relative), sha256=actual_sha)
    owner = vars(phase.sim).get("grn")
    core = None if owner is None else vars(owner).get("core")
    if core is None:
        raise ValueError("No complete existing GRN owner to capture")
    core_fields = vars(core)
    # Preserve unsupported owners in the refusal evidence instead of using the
    # bounded X/Y serializer to erase them.
    excluded = dict(
        channels=bool(core_fields["channels"]),
        transporters=bool(core_fields["transporters"]),
        mitochondria=core_fields["mit"] is not None,
        standalone_molecules=vars(phase.sim)["molecules"] is not None,
    )
    groups = owners | dict(
        mesh=vars(phase.cells).get("mesh"), display=vars(phase.sim).get("cellso")
    )
    try:
        cached = source.cache(SimpleNamespace(sim=phase.sim))
    except Exception as error:
        # Diagnostic capture remains incomplete; it cannot enter handoff.
        result = capture_supplied(groups, None, excluded, declaration)
        cache_entry = _copy(
            dict(present=True, captured=False, error=str(error), type=type(error).__name__)
        )
        result = replace(result, network_cache=cache_entry)
    else:
        result = capture_supplied(groups, cached, excluded, declaration)
    # These four Parameters fields are YAML descriptors, not instance vars.
    # Their pinned getters read/validate the original configuration and do not
    # write it. No arbitrary native property or initializer is invoked.
    parameters = dict(result.owners["parameters"])
    for key in NATIVE_PARAMETER_ALIASES:
        try:
            parameters[key] = _entry({key: getattr(phase.p, key)}, key)
        except Exception as error:
            parameters[key] = dict(
                present=True, captured=False, error=str(error), type="native_yaml_alias"
            )
    updated = dict(result.owners, parameters=_copy(parameters))
    result = replace(result, owners=_copy(updated))
    pins["phase_kind"] = kind
    pins["excluded_owners"] = "presence_only; private state is unsupported and cannot enter handoff"
    result = replace(
        result,
        observation_kind="pinned_native_objects_at_declared_boundary",
        source_objects=_copy(pins),
    )
    return replace(result, identity=ions.digest(boundary_record(result)))


def validate_boundary(value):
    if type(value) is not Boundary or value.identity != ions.digest(boundary_record(value)):
        raise InitializationRejected(
            "Changed or unsealed boundary", stage="authentication", boundary=value
        )
    _declaration(value.declaration)
    if value.observation_kind not in (
        "supplied_owner_boundary",
        "pinned_native_objects_at_declared_boundary",
    ):
        raise InitializationRejected(
            "Unknown boundary observation", stage="authentication", boundary=value
        )
    if set(value.owners) != set(GROUPS) or any(
        set(value.owners[g]) != set(keys) for g, keys in GROUPS.items()
    ):
        raise InitializationRejected(
            "Incomplete presence inventory", stage="authentication", boundary=value
        )
    if set(value.excluded_owner_state) != set(EXCLUDED) or any(
        type(v) is not bool for v in value.excluded_owner_state.values()
    ):
        raise InitializationRejected(
            "Incomplete excluded-owner inventory", stage="authentication", boundary=value
        )


def _required(boundary, group, name):
    entry = boundary.owners[group][name]
    if not entry["present"] or not entry.get("captured", False):
        raise ValueError("Missing/unreadable native owner: " + group + "." + name)
    return entry["value"]


def _same(actual, expected, name):
    """Exact axis, domain and binary64 equality; no numerical allowance."""
    a, b = np.asarray(actual), np.asarray(expected)
    if a.shape != b.shape or a.dtype.kind not in "bifu" or b.dtype.kind not in "bifu":
        raise ValueError("Changed owner shape/type: " + name)
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Nonfinite source owner: " + name)
    if a.dtype.kind == "b" or b.dtype.kind == "b":
        if a.dtype.kind != b.dtype.kind or not np.array_equal(a, b):
            raise ValueError("Changed boolean mask owner: " + name)
        return
    if a.dtype.kind == "f" or b.dtype.kind == "f":
        # Parameters.F and several native counters/constant factors are Python
        # integers. Admit an exact scalar integer representation of a declared
        # float; arrays must still have their original binary64 dtype.
        if a.ndim == 0 and a.dtype.kind in "iu" and b.dtype.kind == "f":
            integer = int(a)
            if (
                not math.isfinite(float(integer))
                or int(float(integer)) != integer
                or float(integer) != float(b)
            ):
                raise ValueError("Changed exact scalar constant: " + name)
            return
        if a.dtype.kind != "f" or a.dtype.itemsize != 8:
            raise ValueError("Require original binary64 native owner: " + name)
        if a.astype("<f8", copy=False).tobytes() != b.astype("<f8", copy=False).tobytes():
            raise ValueError("Changed source owner bits: " + name)
    elif not np.array_equal(a, b):
        raise ValueError("Changed source owner: " + name)


def _binding(binding):
    if type(binding) not in (field.Binding, calcium.Binding):
        raise ValueError("Require an existing field or calcium/field binding")
    base = field.bind(ions.data(binding.inputs))
    if ions.digest(base.material_binding) != ions.digest(binding.material_binding) or ions.digest(
        base.voltage_binding
    ) != ions.digest(binding.voltage_binding):
        raise ValueError("Changed original operators/cache or material binding")
    if type(binding) is field.Binding:
        if ions.digest(base) != ions.digest(binding):
            raise ValueError("Changed field binding")
    else:
        calcium.validate_composition(binding)
    return base


def _check_owners(binding, boundary):
    _binding(binding)
    validate_boundary(boundary)
    if any(boundary.excluded_owner_state.values()):
        raise ValueError(
            "Channel/private gate, transporter, mitochondrial "
            "or separate molecule owners are unsupported"
        )

    def p(key):
        return _required(boundary, "parameters", key)

    def c(key):
        return _required(boundary, "cells", key)

    def s(key):
        return _required(boundary, "sim", key)

    if p("solver_type") != "FULL" or any(
        p(key) is not False
        for key in ("fluid_flow", "td_deform", "v_sensitive_gj", "molecules_enabled", "Ca_dyn")
    ):
        raise ValueError(
            "Require ordinary FULL, disabled flow/dynamic/voltage-gates/ER/separate molecules"
        )
    if p("is_ecm") is not True or p("grn_enabled") is not True:
        raise ValueError("Require the actual ECM GRN branch")
    mb = binding.material_binding
    gb, k = mb.geometry_binding, mb.kernel
    cb, g = gb.current_binding, gb.geometry
    n, m, e = len(cb.cell_ids), len(cb.membrane_ids), math.prod(g.shape)
    if not 1 <= n <= 16 or not 1 <= m <= 128 or not 1 <= len(cb.ion_ids) <= 32 or e > 49:
        raise ValueError("Do not widen the frozen source capture domain")
    active = tuple(name for name, enabled in p("ions_dict").items() if enabled == 1)
    if active != cb.ion_ids:
        raise ValueError("Actual native ion roles/order differ from the bound rows")
    geometry = gb.definition["geometry"]
    cell_pairs = dict(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=cb.kernel.owner,
        nn_i=k.partner,
        bflags_mems=k.boundary,
        gj_len=k.gap_length_m,
        gj_default_weights=k.gap_weights,
        mem_sa=cb.kernel.membrane_area_m2,
        cell_sa=cb.kernel.cell_area_m2,
        cell_vol=geometry["cell_volume_m3"],
        cell_centres=geometry["cell_centres_m"],
        mem_mids_flat=geometry["membrane_midpoints_m"],
        M_sum_mems=cb.kernel.owner_sum,
        num_mems=np.bincount(cb.kernel.owner, minlength=n),
        R_rads=binding.voltage_binding.kernel.radius_m,
        diviterm=binding.voltage_binding.kernel.diviterm_m,
        X=g.X_m,
        Y=g.Y_m,
        xypts=g.grid_points_m,
        delta=float(g.delta_m),
        map_ij2k=g.index_ij,
        map_cell2ecm=g.cell_to_grid,
        map_mem2ecm=g.membrane_to_grid,
        memSa_per_envSquare=g.membrane_area_per_site_m2,
        mems_per_envSquare=g.membranes_per_site,
        true_ecm_vol=g.true_environment_volume_m3,
        M_divmap_mem2ecm=g.membrane_divergence_map_m2,
        cell2env_corrF=g.cell_to_environment_correction,
        lapENVinv=g.dirichlet_inverse_m2,
        lapENV_P_inv=g.neumann_inverse_m2,
    )
    for key, expected in cell_pairs.items():
        _same(c(key), expected, "cells." + key)
    vectors = np.asarray(c("mem_vects_flat"))
    if vectors.shape != (m, 4):
        raise ValueError("Require original four-column native membrane vectors")
    _same(vectors[:, 2:], cb.kernel.normal_xy, "cells.mem_vects_flat normal columns")
    for key, expected in dict(
        cdl=n,
        mdl=m,
        edl=e,
        zs=cb.kernel.valence,
        movingIons=k.moving,
        Dm_cells=k.membrane_diffusion_m2_s,
        D_gj=k.gap_diffusion_m2_s,
        D_env=k.environment_diffusion_m2_s,
        TJ_modulator=k.tight_junction_modulator,
        smooth_weight_mem=cb.kernel.membrane_weight,
        smooth_weight_o=cb.kernel.other_weight,
        sigma=gb.cache.sigma_S_m,
        ko_env=gb.cache.ko_environment_per_m,
    ).items():
        _same(s(key), expected, "sim." + key)
    cache = gb.definition["cache_initial_state"]
    for key, expected in dict(
        D_free=cache["free_diffusion_m2_s"],
        cc_cells=cache["cell_mol_m3"],
        cc_env=cache["environment_mol_m3"],
    ).items():
        _same(s(key), expected, "cache source sim." + key)
    ep = gb.definition["parameters"]
    expected_p = dict(
        F=cb.kernel.F_C_mol,
        R=k.R_J_mol_K,
        T=ep["configured_temperature_K"],
        q=ep["q_C"],
        kb=ep["kb_J_K"],
        NAv=ep["NAv_per_mol"],
        er=ep["relative_permittivity"],
        eo=ep["vacuum_permittivity_F_m"],
        mu=ep["magnetic_permeability_H_m"],
        cell_height=ep["cell_height_m"],
        cell_space=ep["cell_space_m"],
        cell_radius=ep["cell_radius_m"],
        true_cell_size=ep["true_cell_size_m"],
        tm=k.membrane_thickness_m,
        gj_surface=k.gap_surface_fraction,
        sharpness=k.sharpness,
        smooth_cells=cb.kernel.source_smooth_cells,
        cm=binding.inputs["field_parameters"]["capacitance_F_m2"],
        cell_polarizability=binding.inputs["field_parameters"]["polarizability"],
        dt=binding.inputs["bootstrap"]["dt_s"],
    )
    for key, expected in expected_p.items():
        _same(p(key), expected, "parameters." + key)
    for key, expected in dict(
        cluster_open=k.cluster_open, fast_update_ecm=k.fast_update_ecm
    ).items():
        if p(key) is not expected:
            raise ValueError("Changed source branch: " + key)
    for key in ("xmin", "xmax", "ymin", "ymax"):
        _same(c(key), float(gb.definition["world"][key + "_m"]), "cells." + key)
    initial = {key: s(attr) for key, attr in source.MATERIAL_PAIRS}
    initial["junction_field_xy_source"] = np.column_stack((s("E_gj_x"), s("E_gj_y")))
    for key, expected in binding.inputs["initial"].items():
        _same(initial[key], expected, "initial." + key)
    state = material.state(mb, initial)
    controls = {key: s(key) for key in ("gj_block", "NaKATP_block")}
    definition = binding.inputs["network"]
    for key, expected in definition["initial_controls"].items():
        _same(controls[key], expected, "controls." + key)
    _same(s("c_env_bound"), definition["initial_ion_boundary"], "sim.c_env_bound")
    if set(s("bound_V")) != set(binding.inputs["bootstrap"]["boundary_V"]):
        raise ValueError("Use actual boundary voltage values at bootstrap")
    for key, expected in binding.inputs["bootstrap"]["boundary_V"].items():
        _same(s("bound_V")[key], expected, "bootstrap boundary " + key)
    entry = boundary.network_cache
    if not entry["present"] or not entry.get("captured", False) or entry["value"] is None:
        raise ValueError("Missing/unreadable hot GRN owner cache")
    cached = entry["value"]
    if set(cached["wire"]["molecule_fields"]) != {"X", "Y"}:
        raise ValueError("Require the complete bounded X/Y owner cache")
    for name, values in cached["wire"]["molecule_fields"].items():
        for key, size in (("c_cells", n), ("cc_at_mem", m), ("c_env", e)):
            a = np.asarray(values[key])
            if (
                a.dtype != np.float64
                or a.shape != (size,)
                or not np.isfinite(a).all()
                or np.any(a < 0)
            ):
                raise ValueError("Invalid hot molecular owner axis/domain: " + name + "." + key)
    _same(cached["wire"]["ion_boundary_state"], s("c_env_bound"), "owner ionic boundary epoch")
    for key, expected in cached["wire"]["simulator_fields"].items():
        _same(s(key), expected, "publication sim." + key)
    if set(cached["wire"]["simulator_fields"]) != {
        "extra_rho_cells",
        "extra_rho_env",
        "extra_J_mem",
        "extra_Jenv_x",
        "extra_Jenv_y",
    }:
        raise ValueError("Require every source publication store")
    for key, expected in cached["coefficient_fields"].items():
        _same(s(key), expected, "molecular coefficients sim." + key)
    # Actual post-profile coefficients are compared, never silently rebuilt.
    for key, expected in definition["grid_index_groups"].items():
        _same(c(key), expected, "cells." + key)
    return state, controls, cached


def handoff(binding, boundary, *, before_field=None):
    """Execute only the existing bootstrap on complete supplied hot owners."""
    stage, ctx, parent = "owner_admission", None, None
    try:
        initial, controls, cached = _check_owners(binding, boundary)
        if type(binding) is calcium.Binding:
            stage = "calcium_admission"
            rate_entry = boundary.owners["sim"]["rate_CaATP"]
            if rate_entry["present"]:
                raise ValueError(
                    "Existing calcium call-zero contract cannot admit a persisted INIT rate_CaATP; "
                    "keep it present"
                )
            for key, expected in calcium.parameters(binding).items():
                _same(_required(boundary, "parameters", key), expected, "calcium parameter " + key)
            for key, expected in dict(
                CaATP_block=np.ones(len(initial.values.voltage_V)), rho_pump=1
            ).items():
                _same(_required(boundary, "sim", key), expected, "calcium policy " + key)
            if (
                _required(boundary, "sim", "met_concs") is not None
                or _required(boundary, "sim", "endo_retic") is not None
            ):
                raise ValueError("Calcium maintained-pool/disabled-ER policy does not match")
            dt = binding.inputs["bootstrap"]["dt_s"]
            _same(_required(boundary, "parameters", "sim_tsteps"), 3, "source clock count")
        stage = "hot_owner_hydration"
        working = material.Values(*(np.array(v, copy=True) for v in initial.values))
        ctx = network.make_context(binding, working, ions.data(binding.inputs["network"]))
        source.restore(ctx, cached)
        if ions.digest(source.cache(ctx)) != ions.digest(cached):
            raise ValueError("Hot owner serializer cannot round-trip the supplied complete cache")
        if ions.digest(source.material_values(ctx.sim)) != ions.digest(initial.values._asdict()):
            raise ValueError("Hot owner hydration changed primary material")
        parent = network._state(binding, initial, cached, controls)
        stage = "bootstrap"
        boot = binding.inputs["bootstrap"]
        prepared, fields = field.reconstruct(
            binding, parent, boot["dt_s"], boot["boundary_V"], "bootstrap", before_field
        )
        if type(binding) is calcium.Binding:
            clock = calcium.Clock(ions.freeze(np.linspace(0, 3 * dt, 3)), 0, 0.0)
            candidate = calcium.joined_state(
                binding, prepared, fields, calcium.RateCache(False, None), clock
            )
        else:
            candidate = field.state(binding, prepared, fields)
        provenance = ions.freeze(
            dict(
                law=LAW_ID,
                source_revision=SOURCE_REVISION,
                boundary_stage=STAGE,
                observation_kind=boundary.observation_kind,
                geometry_classification=boundary.declaration["geometry_classification"],
                upstream_evidence=boundary.declaration["upstream_evidence"],
                admission="complete_supplied_owner_boundary",
                bootstrap_calls=1,
                bootstrap_implementation="existing_component_field_reconstruct",
                native_bootstrap_executed=False,
                cold_owner_calls=0,
                native_init_dynamics_calls=0,
                native_seed_init_load_chain_established=False,
                full_SimRunner_executed=False,
                mechanics_admitted=False,
            )
        )
        result = Handoff(boundary.identity, binding.identity, candidate, provenance, "")
        return replace(
            result,
            identity=ions.digest(
                (
                    result.boundary_identity,
                    result.binding_identity,
                    result.parent,
                    result.provenance,
                )
            ),
        )
    except Exception as error:
        raise InitializationRejected(
            error,
            stage=stage,
            boundary=boundary,
            partial=dict(
                parent=parent,
                source=getattr(error, "partial", None),
                hydrated_owner=None
                if ctx is None
                else network._failure_snapshot(ctx, boundary.network_cache),
            ),
        ) from error


def missing_stores(boundary):
    """Inventory only; an empty inventory is not native-initialization proof."""
    validate_boundary(boundary)
    return ions.freeze(
        {
            group: [
                key
                for key, entry in values.items()
                if not entry["present"] or not entry.get("captured", False)
            ]
            for group, values in boundary.owners.items()
        }
    )


def handoff_mechanics(binding, boundary, field_handoff):
    """Attach complete matching held mechanics stores, without running them.

    This takes the explicit field-only bootstrap receipt. It cannot compose
    the separate calcium and mechanics loops, repair a missing native store,
    or reinterpret a scalar disabled-flow store as a grid array.
    """
    stage = "mechanics_admission"
    try:
        validate_boundary(boundary)
        if type(binding) is not mechanical_field.Binding:
            raise ValueError("Require the existing ordinary field/mechanics composition")
        checked = mechanical_field.bind(ions.data(binding.inputs))
        if ions.digest(checked) != ions.digest(binding):
            raise ValueError("Changed composed mechanics binding/operators")
        if (
            type(field_handoff) is not Handoff
            or field_handoff.boundary_identity != boundary.identity
            or field_handoff.binding_identity != binding.field.identity
            or type(field_handoff.parent) is not field.State
            or field_handoff.identity
            != ions.digest(
                (
                    field_handoff.boundary_identity,
                    field_handoff.binding_identity,
                    field_handoff.parent,
                    field_handoff.provenance,
                )
            )
            or field_handoff.provenance["bootstrap_calls"] != 1
            or field_handoff.provenance["mechanics_admitted"] is not False
        ):
            raise ValueError("Require the unchanged single-bootstrap receipt on these owners")
        definition = binding.mechanics.definition
        layout = definition["geometry"]["layout"]

        def c(key):
            return _required(boundary, "cells", key)

        def p(key):
            return _required(boundary, "parameters", key)

        pairs = dict(
            cell_nn_i="neighbors",
            nn_len="lengths_m",
            mem_vol="membrane_volume_m3",
            mem_verts="vertices_m",
        )
        for native, declared in pairs.items():
            _same(c(native), layout[declared], "mechanics cells." + native)
        _same(
            np.column_stack((c("nn_tx"), c("nn_ty"))),
            layout["force_directions"],
            "mechanics force directions",
        )
        _same(
            np.column_stack((c("cell_nn_tx"), c("cell_nn_ty"))),
            layout["curl_directions"],
            "mechanics curl directions",
        )
        for native, declared in dict(
            vor_edge_len="dual_edge_m",
            tri_edge_len="primal_edge_m",
            delta_tri_0="incidence",
            delta_tri_0_inv="incidence_inverse",
            vor_sa="dual_area_m2",
        ).items():
            _same(_required(boundary, "mesh", native), layout[declared], "DEC mesh." + native)
        _same(c("lapGJ"), binding.mechanics.operators.laplacian, "cells.lapGJ")
        _same(c("lapGJinv"), binding.mechanics.operators.laplacian_inverse, "cells.lapGJinv")
        for key in ("deformation", "deform_osmo"):
            if p(key) is not definition["policy"][key]:
                raise ValueError("Changed mechanical branch: " + key)
        mp = definition["parameters"]
        expected_p = dict(
            lame_mu=mp["young_modulus_Pa"] / (2 * (1 + 0.49)),
            galvanotropism=mp["galvanotropism_m2_V"],
            aquaporins=mp["aquaporin_fraction"],
            mu_water=mp["water_viscosity_Pa_s"],
            rho=mp["density_kg_m3"],
        )
        for key, expected in expected_p.items():
            _same(p(key), expected, "mechanics parameter " + key)
        if p("fixed_cluster_bound") is not mp["fixed_boundary"]:
            raise ValueError("Changed source fixed-boundary declaration")
        cache = {
            key: _required(boundary, "sim", key)
            for key in mechanics.CACHE_KEYS
            if not key.startswith("display_")
        }
        cache["display_centres_m"] = _required(boundary, "display", "cell_centres")
        owner = np.asarray(c("mem_to_cells"))
        rows = _required(boundary, "display", "cell_verts")
        if len(rows) != len(binding.mechanics.definition["geometry"]["cell_ids"]):
            raise ValueError("Missing original ragged display owner axis")
        vertices = np.empty((len(owner), 2), dtype=np.float64)
        for index, row in enumerate(rows):
            ids = np.flatnonzero(owner == index)
            values = np.asarray(row, dtype=np.float64)
            if values.shape != (len(ids), 2):
                raise ValueError("Display rows do not match original membrane owners")
            vertices[ids] = values
        cache["display_vertices_m"] = vertices
        held = mechanics.state(binding.mechanics, cache)
        for key, expected in binding.inputs["mechanics_initial"].items():
            _same(cache[key], expected, "held mechanics." + key)
        for key in ("P_cells", "P_base", "P_mod"):
            values = np.asarray(_required(boundary, "sim", key))
            if values.shape != (len(rows),) or not np.isfinite(values).all():
                raise ValueError("Incomplete initial pressure owner: " + key)
            if binding.inputs[
                "pressure_policy"
            ] == "native_zero_baseline_no_pressure_events" and np.any(values != 0):
                raise ValueError(
                    "Declared zero-pressure source baseline differs from captured pressure"
                )
        candidate = mechanical_field.state(binding, field_handoff.parent, held)
        provenance = ions.freeze(
            dict(
                field_handoff.provenance,
                mechanics_admitted=True,
                mechanical_calls=0,
                source_pressure_events_executed=False,
            )
        )
        result = Handoff(boundary.identity, binding.identity, candidate, provenance, "")
        return replace(
            result,
            identity=ions.digest(
                (
                    result.boundary_identity,
                    result.binding_identity,
                    result.parent,
                    result.provenance,
                )
            ),
        )
    except Exception as error:
        raise InitializationRejected(
            error, stage=stage, boundary=boundary, partial=dict(field_handoff=field_handoff)
        ) from error
