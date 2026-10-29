"""Static native tissue profiles bound to actual resolved physical owners.

The frozen profile kernels own selection, ordered overwrites and overlapping
insular barriers. This host bridge requires explicit SI geometry and preserves
the source definition except for selected membrane and junction permeability.
It does not translate dynamic interventions, pressure, ECM diffusion or cuts.
"""

import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from numbers import Real
from pathlib import Path

import numpy as np

from cells.core.specs import ConfigError, digest, parse_spec
from cells.models.registry import get_model
from cells.processes import betse_tissue_profiles as native

BRIDGE_ID = "resolved_tissue_static_profiles@1"
KIND = "cells.resolved_tissue_profile_preparation@1"
SUPPORTED_MODELS = ("resolved_tissue@1", "resolved_tissue@12")
SUPPORTED_IONS = {"Na": 1, "K": 1, "Cl": -1, "Ca": 2}
CONVERSION = "static_D_over_explicit_thickness_unit_rho@1"
UNITS = dict(
    diffusivity="m2/s",
    thickness="m",
    permeability="m/s",
    area="m2",
    concentration="fmol/pL = mol/m3",
    native_flux="mol/(m2*s), inward",
    cells_flux="fmol/s, cell-to-outside",
    rho_channel=1.0,
    coefficient_equation="P = D / thickness",
    amount_flux_equation="Cells_outward_fmol_s = -native_inward_flux * area / 1e-15",
    constants_scope="Unit-law correspondence at common F/R/T; Cells physical constants unchanged",
)
SOURCE_CORRESPONDENCE = dict(
    native_version="1.5.0",
    native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
    profile_kernel_sha256="840482d6612a4f0502eac9214acc1d90559345cb757d847f72f4dc8843502be1",
    native_electroflux_ast_sha256="fdea0e87111b95676927b226fdd3dd56db1ca20849dcd55da581c350d2eb4183",
    native_flux="betse/science/sim_toolbox.py:electroflux and update_Co",
    native_geometry="betse/science/sim.py passes p.tm and initial rho_channel=1",
    cells_flux="cells.coupling.selective.selective_flux, via cells.numerics.surface_transport",
)


@dataclass(frozen=True)
class Geometry:
    layout: native.Layout
    thickness_m: dict
    partner_membrane_ids: dict
    junction_membrane_ids: dict
    cell_neighbor_ids: dict
    provenance: dict
    length_unit: str = "m"
    rho_channel: float = 1.0


@dataclass(frozen=True)
class Preparation:
    definition: dict
    provenance: dict


def _json(value):
    def convert(v):
        if isinstance(v, np.ndarray):
            return v.tolist()
        if isinstance(v, np.generic):
            return v.item()
        raise TypeError("Require JSON-compatible explicit preparation inputs")

    try:
        return json.loads(json.dumps(value, allow_nan=False, default=convert))
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigError("Preparation provenance must be finite JSON data") from error


def _positive(value, label):
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not np.isfinite(value)
        or value <= 0
    ):
        raise ConfigError("Require finite positive " + label)
    result = float(value)
    if not np.isfinite(result) or result <= 0:
        raise ConfigError("Require representable positive " + label)
    return result


def _keys(mapping, ids, label):
    if type(mapping) is not dict or set(mapping) != set(ids):
        raise ConfigError("Require complete exact stable-ID " + label)


def _geometry(geometry, model):
    if (
        type(geometry) is not Geometry
        or geometry.length_unit != "m"
        or type(geometry.provenance) is not dict
        or not geometry.provenance
    ):
        raise ConfigError("Require explicit SI geometry and nonempty geometry provenance")
    if (
        not isinstance(geometry.rho_channel, Real)
        or isinstance(geometry.rho_channel, (bool, np.bool_))
        or geometry.rho_channel != 1.0
    ):
        raise ConfigError("Only the static native unit-rho baseline is supported")
    try:
        layout = native.validate_layout(geometry.layout)
    except (TypeError, ValueError) as error:
        raise ConfigError(str(error)) from error
    for domain, rows in (
        ("cell", model.cells),
        ("membrane", model.membranes),
        ("environment", model.extracellular),
    ):
        if set(getattr(layout, domain + "_ids")) != {row.id for row in rows}:
            raise ConfigError(
                "Geometry " + domain + " IDs disagree with the actual resolved owners"
            )
    membranes = {row.id: row for row in model.membranes}
    cells = {row.id: i for i, row in enumerate(model.cells)}
    for i, mid in enumerate(layout.membrane_ids):
        patch = membranes[mid]
        if (layout.membrane_cell_ids[i], layout.membrane_environment_ids[i]) != (
            patch.inside,
            patch.outside,
        ):
            raise ConfigError("Geometry membrane cell/exterior ownership disagrees")
    _keys(geometry.thickness_m, layout.membrane_ids, "membrane thicknesses")
    thickness = {
        mid: _positive(geometry.thickness_m[mid], "membrane thickness in m")
        for mid in layout.membrane_ids
    }
    _keys(geometry.partner_membrane_ids, layout.membrane_ids, "reciprocal membrane partners")
    partners = geometry.partner_membrane_ids
    for mid, other in partners.items():
        if type(other) is not str or other not in membranes or partners[other] != mid:
            raise ConfigError("Membrane partners must be known and exactly reciprocal")
        if other != mid and membranes[mid].inside == membranes[other].inside:
            raise ConfigError("A non-boundary membrane pair must join distinct actual cells")
    junctions = {row.id: row for row in model.junctions}
    _keys(geometry.junction_membrane_ids, junctions, "junction contact pairs")
    used = set()
    for jid, row in junctions.items():
        pair = geometry.junction_membrane_ids[jid]
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or any(type(v) is not str or v not in membranes for v in pair)
        ):
            raise ConfigError("Require two actual membrane IDs per physical junction")
        a, b = pair
        if (
            a == b
            or partners[a] != b
            or (membranes[a].inside, membranes[b].inside) != (row.sender, row.receiver)
        ):
            raise ConfigError(
                "Junction contact pair must be reciprocal with its actual sender/receiver"
            )
        if a in used or b in used:
            raise ConfigError(
                "A reciprocal contact pair cannot ambiguously supply multiple junctions"
            )
        used.update(pair)
    paired = {mid for mid, other in partners.items() if mid != other}
    if paired != used:
        raise ConfigError("Every non-boundary pair needs exactly one identified resolved junction")
    _keys(geometry.cell_neighbor_ids, cells, "original cell neighbors")
    expected = {cell: set() for cell in cells}
    for edge in junctions.values():
        expected[edge.sender].add(edge.receiver)
        expected[edge.receiver].add(edge.sender)
    neighbors = np.zeros((len(cells), len(cells)), bool)
    for cell, values in geometry.cell_neighbor_ids.items():
        if (
            not isinstance(values, (list, tuple))
            or any(type(v) is not str or v not in cells for v in values)
            or len(set(values)) != len(values)
            or set(values) != expected[cell]
        ):
            raise ConfigError(
                "Original neighbor IDs must exactly match the declared physical junction graph"
            )
        for other in values:
            neighbors[layout.cell_ids.index(cell), layout.cell_ids.index(other)] = True
    record = _json(
        dict(
            layout=asdict(layout),
            thickness_m=thickness,
            partner_membrane_ids=partners,
            junction_membrane_ids=geometry.junction_membrane_ids,
            cell_neighbor_ids=geometry.cell_neighbor_ids,
            provenance=geometry.provenance,
            length_unit="m",
            rho_channel=1.0,
        )
    )
    return (
        layout,
        thickness,
        np.asarray(
            [layout.membrane_ids.index(partners[mid]) for mid in layout.membrane_ids],
            dtype=np.int64,
        ),
        neighbors,
        record,
    )


def _profile(row):
    if type(row) is not native.Profile or type(row.selector) is not native.Selector:
        raise ConfigError("Require frozen native Profile and Selector declarations")
    return _json(asdict(row))


def _decode_profile(row):
    selector = deepcopy(row["selector"])
    if selector["kind"] == "image":
        selector["value"] = native.Bitmap(np.asarray(selector["value"]["grayscale_F"]))
    if selector["permutation_cell_ids"] is not None:
        selector["permutation_cell_ids"] = tuple(selector["permutation_cell_ids"])
    return native.Profile(
        row["name"],
        native.Selector(**selector),
        tuple(row["diffusivity_m2_s"]),
        row["is_gj_insular"],
    )


def _state_identity(state):
    return digest(
        {
            key: dict(
                shape=list(np.asarray(value).shape),
                dtype=str(np.asarray(value).dtype),
                values=np.asarray(value).tolist(),
            )
            for key, value in state._asdict().items()
        }
    )


def prepare(definition, geometry, default, profiles, *, ion_enabled, enabled=True, is_ecm=False):
    """Return a validated definition and a complete deterministic replay recipe."""
    if (
        type(definition) is not dict
        or type(definition.get("model")) is not dict
        or definition["model"].get("id") not in SUPPORTED_MODELS
    ):
        raise ConfigError(
            "Static preparation supports direct resolved_tissue@1 or resolved_tissue@12 only"
        )
    if not isinstance(profiles, (tuple, list)):
        raise ConfigError("Require an explicit ordered static profile sequence")
    flags = np.asarray(ion_enabled)
    if flags.shape != (6,) or flags.dtype.kind != "b":
        raise ConfigError("Require the explicit six native ion-enable booleans")
    source_spec = parse_spec(deepcopy(definition))
    source = source_spec.to_dict()
    m = source_spec.model
    for ion, active in zip(native.IONS, flags, strict=True):
        if active and (
            ion not in SUPPORTED_IONS
            or ion not in m.species_ids
            or m.valence[m.species_ids.index(ion)] != SUPPORTED_IONS[ion]
        ):
            raise ConfigError(
                "Enabled profile ion is unsupported, absent or has the wrong physical valence: "
                + ion
            )
    layout, thickness, partner, neighbors, geometry_record = _geometry(geometry, m)
    declarations = dict(
        default=_profile(default),
        profiles=[_profile(row) for row in profiles],
        ion_enabled=flags.tolist(),
        enabled=enabled,
        is_ecm=is_ecm,
    )
    try:
        binding = native.compile_profiles(
            layout, default, profiles, ion_enabled=flags, is_ecm=is_ecm, enabled=enabled
        )
        initial = np.zeros((6, len(layout.membrane_ids)))
        by_membrane = {row.id: row for row in m.membranes}
        for i, ion in enumerate(native.IONS):
            if ion in m.species_ids:
                si = m.species_ids.index(ion)
                for j, mid in enumerate(layout.membrane_ids):
                    initial[i, j] = by_membrane[mid].permeability_m_per_s[si] * thickness[mid]
        diffusion = native.apply_profile_diffusion(initial, binding.kernel, xp=np)
        weights = native.insular_membrane_weights(binding, partner, neighbors, xp=np)
    except (TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid static profile binding: " + str(error)) from error
    if (
        not np.isfinite(diffusion).all()
        or np.any(diffusion < 0)
        or not np.isin(weights, [0.0, 1.0]).all()
    ):
        raise ConfigError("Require finite nonnegative static diffusion and binary insularity")
    result = deepcopy(source)
    selected = (
        np.any(binding.kernel.membranes, axis=0)
        if binding.names
        else np.zeros(len(layout.membrane_ids), bool)
    )
    changes = []
    for row in result["model"]["membranes"]:
        j = layout.membrane_ids.index(row["id"])
        for i, ion in enumerate(native.IONS):
            if flags[i] and selected[j]:
                value = float(diffusion[i, j] / thickness[row["id"]])
                if not np.isfinite(value) or value < 0:
                    raise ConfigError("Invalid converted membrane permeability")
                old = row["permeability_m_per_s"][ion]
                row["permeability_m_per_s"][ion] = value
                if old != value:
                    changes.append(
                        dict(
                            domain="membrane", id=row["id"], species_id=ion, before=old, after=value
                        )
                    )
    edge_weights = {}
    for row in result["model"]["junctions"]:
        a, b = geometry_record["junction_membrane_ids"][row["id"]]
        wa, wb = weights[layout.membrane_ids.index(a)], weights[layout.membrane_ids.index(b)]
        if wa != wb:
            raise ConfigError("Reciprocal contact weights disagree")
        edge_weights[row["id"]] = float(wa)
        if wa == 0:
            for ion, old in row["permeability_m_per_s"].items():
                row["permeability_m_per_s"][ion] = 0.0
                if old != 0.0:
                    changes.append(
                        dict(domain="junction", id=row["id"], species_id=ion, before=old, after=0.0)
                    )
    prepared_spec = parse_spec(result)
    result = prepared_spec.to_dict()
    restored = deepcopy(result)
    for change in changes:
        row = next(
            row for row in restored["model"][change["domain"] + "s"] if row["id"] == change["id"]
        )
        if row["permeability_m_per_s"][change["species_id"]] != change["after"]:
            raise ConfigError("Validation changed a selected physical coefficient")
        row["permeability_m_per_s"][change["species_id"]] = change["before"]
    if restored != source:
        raise ConfigError(
            "Preparation changed inventories, IDs or unselected definition parameters"
        )
    implementation = get_model(source_spec.model)
    before, _ = implementation.initial_values(source_spec)
    after, _ = get_model(prepared_spec.model).initial_values(prepared_spec)
    if type(after) is not type(before) or any(
        np.asarray(a).dtype != np.asarray(b).dtype or not np.array_equal(a, b)
        for a, b in zip(after, before, strict=True)
    ):
        raise ConfigError(
            "Preparation would change an inferred initial state; declare its gate states explicitly"
        )
    provenance = _json(
        dict(
            kind=KIND,
            bridge_id=BRIDGE_ID,
            law_id=native.LAW_ID,
            source_definition=source,
            source_definition_sha256=digest(source),
            prepared_definition_sha256=digest(result),
            geometry=geometry_record,
            profile_declarations=declarations,
            binding=native.binding_manifest(binding),
            conversion=CONVERSION,
            units=UNITS,
            source_correspondence=SOURCE_CORRESPONDENCE,
            diffusivity_m2_s=diffusion.tolist(),
            diffusion_axes=dict(species=list(native.IONS), membrane_ids=list(layout.membrane_ids)),
            insular_membrane_weights={
                mid: float(weights[i]) for i, mid in enumerate(layout.membrane_ids)
            },
            insular_junction_weights=edge_weights,
            changes=changes,
            state_fields=list(before._fields),
            initial_state_sha256=_state_identity(before),
            dynamic_scope=(
                "Static membrane profiles and insular targets; "
                "interventions/pressure/ECM transport separate"
            ),
            junction_scope=(
                "One explicit reciprocal contact per edge; "
                "IDs, intrinsic gates and schedules preserved"
            ),
            native_scope=(
                "Frozen selector/ordered-overlap/insular kernels; "
                "no full native geometry/solver equivalence"
            ),
        )
    )
    provenance["identity"] = digest(provenance)
    return Preparation(result, provenance)


def replay(provenance):
    """Rebuild the prepared definition from declared source/profile/geometry IDs."""
    try:
        p = deepcopy(provenance)
        identity = p.pop("identity")
        if p["kind"] != KIND or identity != digest(p):
            raise ConfigError("Stale preparation identity")
        g = deepcopy(p["geometry"])
        layout = g.pop("layout")
        layout["cell_centres_m"] = np.asarray(layout["cell_centres_m"], dtype=float)
        geometry = Geometry(native.Layout(**layout), **g)
        rows = p["profile_declarations"]
        result = prepare(
            p["source_definition"],
            geometry,
            _decode_profile(rows["default"]),
            [_decode_profile(r) for r in rows["profiles"]],
            ion_enabled=rows["ion_enabled"],
            enabled=rows["enabled"],
            is_ecm=rows["is_ecm"],
        )
        if result.provenance != provenance:
            raise ConfigError("Preparation recipe, owners or numerical provenance changed")
        return result
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid complete static preparation recipe: " + str(error)) from error


def write_preparation(directory, prepared):
    expected = replay(prepared.provenance)
    if prepared.definition != expected.definition:
        raise ConfigError("Prepared definition disagrees with replayed physical recipe")
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    for name, value in (
        ("definition.json", expected.definition),
        ("provenance.json", expected.provenance),
    ):
        (path / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return path


def read_preparation(directory):
    path = Path(directory)
    provenance = json.loads((path / "provenance.json").read_text())
    expected = replay(provenance)
    if json.loads((path / "definition.json").read_text()) != expected.definition:
        raise ConfigError("Prepared definition changed relative to the complete physical recipe")
    return expected
