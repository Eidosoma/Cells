"""Conservative material coordinates for one sealed salt/water/fuel pair.

This independent reference codec drops only the two redundant bulk-ion fields.
Every other coordinate, including finite fuel, water and heat/work histories,
is integrated unchanged. Reconstruction is a declared change of coordinates;
it never repairs, clips or projects an independently integrated bulk state.

Positive passive membrane transfer is outward. A positive Na/K pump cycle
moves three Na outward and two K inward. Neutral KCC/NKCC cycles are inward.
Their large neutral transfers are excluded algebraically from field charge.
No production, JAX, field solver or numerical integrator is imported here.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

F = 6.02214076e23 * 1.602176634e-19
CHARGE_PER_FMOL = F * 1e-15
MODEL_ID = "resolved_cotransport_water@1"
BULK_FIELDS = ("amount_increment", "extracellular_amount_increment")
FIELD_NAMES = (
    *BULK_FIELDS,
    "membrane_transferred",
    "junction_transferred",
    "face_transferred",
    "reservoir_supplied",
    "membrane_dissipated_energy_pJ",
    "junction_dissipated_energy_pJ",
    "face_dissipated_energy_pJ",
    "electrode_charge_transferred_C",
    "reservoir_work_pJ",
    "electrode_work_pJ",
    "channel_gate",
    "channel_transferred",
    "channel_dissipated_energy_pJ",
    "junction_gate",
    "pump_cycles",
    "pump_dissipated_energy_pJ",
    "metabolic_work_pJ",
    "energy_amount_increment_fmol",
    "regeneration_cycles_fmol",
    "regeneration_dissipated_energy_pJ",
    "regeneration_supplied_work_pJ",
    "volume_increment_pL",
    "extracellular_volume_increment_pL",
    "water_transferred_pL",
    "water_dissipated_energy_pJ",
    "pool_volume_work_pJ",
    "cotransport_cycles_fmol",
    "cotransport_transferred_fmol",
    "cotransport_dissipated_energy_pJ",
)


def _vector(value, size, label):
    array = np.asarray(value)
    if array.shape != (size,) or array.dtype.kind != "f" or not np.isfinite(array).all():
        raise ValueError(f"{label} requires one finite floating vector of length {size}")
    return np.asarray(array, dtype=np.float64)


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _immutable(array, dtype):
    result = np.asarray(array, dtype=dtype).copy()
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class MaterialCoordinates:
    """Flat-state codec bound to explicit species, route and original field axes."""

    shapes: object
    slices: object
    integrated_indices: object
    species_ids: tuple
    valence: object
    pump_stoichiometry: object
    cotransport_nu: object
    pump_present: bool
    full_size: int

    @property
    def size(self):
        return self.integrated_indices.size

    def _fields(self, full):
        return {name: full[self.slices[name]].reshape(shape) for name, shape in self.shapes.items()}

    def _mapped_bulk(self, full):
        fields = self._fields(full)
        passive = fields["membrane_transferred"][:, 0]
        cycles = float(fields["pump_cycles"][0])
        if not self.pump_present and cycles != 0:
            raise ValueError("An absent Na/K pump cannot carry a cycle history or rate")
        routes = fields["cotransport_cycles_fmol"]
        terms = [
            [
                -float(passive[i]),
                float(self.pump_stoichiometry[i]) * cycles,
                *(int(n) * float(x) for n, x in zip(self.cotransport_nu[i], routes, strict=True)),
            ]
            for i in range(len(self.species_ids))
        ]
        try:
            inside = np.asarray([math.fsum(row) for row in terms])
            magnitudes = np.asarray([math.fsum(abs(v) for v in row) for row in terms])
        except (OverflowError, ValueError) as error:
            raise ValueError("Material-coordinate reconstruction is not representable") from error
        if not np.isfinite(inside).all() or not np.isfinite(magnitudes).all():
            raise ValueError("Material-coordinate reconstruction is not finite")
        return inside[:, None], -inside[:, None], magnitudes[:, None]

    def unpack(self, reduced):
        """Decode the complete 31-field flat state without changing kept values."""
        reduced = _vector(reduced, self.size, "Reduced material state")
        full = np.zeros(self.full_size)
        full[self.integrated_indices] = reduced
        inside, outside, _ = self._mapped_bulk(full)
        full[self.slices[BULK_FIELDS[0]]] = inside.ravel()
        full[self.slices[BULK_FIELDS[1]]] = outside.ravel()
        return full

    def pack(self, full):
        """Encode an on-manifold state; inconsistent discarded fields are refused.

        Exact comparison is intentional: this path starts at the original zero
        state or at its own decoded reference endpoint. It must not silently
        import and repair a production or legacy independently integrated state.
        """
        full = _vector(full, self.full_size, "Complete material state")
        inside, outside, _ = self._mapped_bulk(full)
        for name, expected in zip(BULK_FIELDS, (inside, outside), strict=True):
            if not np.array_equal(full[self.slices[name]], expected.ravel()):
                raise ValueError(
                    "Bulk material state is inconsistent with its declared ledger coordinates"
                )
        return full[self.integrated_indices].copy()

    def derivative_consistency(self, full_slope):
        """Compare the original bulk RHS with the derivative of the linear map.

        The bound concerns only summation/conversion roundoff in the equivalent
        rate reduction. It is not an ODE tolerance, trajectory budget, physical
        acceptance bound, or permission to modify any derivative.
        """
        slope = _vector(full_slope, self.full_size, "Complete material derivative")
        inside, outside, scale = self._mapped_bulk(slope)
        residual = np.stack(
            [
                slope[self.slices[name]].reshape(expected.shape) - expected
                for name, expected in zip(BULK_FIELDS, (inside, outside), strict=True)
            ]
        )
        # The old path has scalar Decimal-to-float conversions, passive/pump
        # updates and a separately summed neutral-route update. Count a generous
        # finite number of elementary operations, without a free absolute floor.
        operations = 16 + 4 * self.cotransport_nu.shape[1]
        eps = np.finfo(np.float64).eps
        gamma = operations * eps / (1 - operations * eps)
        bound = gamma * scale
        return dict(
            mapped_inside_fmol_s=inside,
            mapped_outside_fmol_s=outside,
            residual_fmol_s=residual,
            roundoff_bound_fmol_s=bound,
            within_roundoff=bool(np.all(np.abs(residual) <= bound)),
        )

    def pack_derivative(self, full_slope):
        """Keep the original non-bulk rates after checking the coordinate identity."""
        slope = _vector(full_slope, self.full_size, "Complete material derivative")
        if not self.derivative_consistency(slope)["within_roundoff"]:
            raise ValueError(
                "Bulk RHS disagrees with the conservative material-coordinate derivative"
            )
        return slope[self.integrated_indices].copy()

    def charge_increment_fmol(self, reduced):
        """Return [inside, outside] charge-equivalent increments in fmol.

        Never recover this charge by summing the reconstructed bulk amounts:
        that would reintroduce cancellation of large neutral cotransport terms.
        The paired exterior uses the exact opposite of the same computed charge.
        """
        reduced = _vector(reduced, self.size, "Reduced material state")
        full = np.zeros(self.full_size)
        full[self.integrated_indices] = reduced
        fields = self._fields(full)
        cycles = float(fields["pump_cycles"][0])
        if not self.pump_present and cycles != 0:
            raise ValueError("An absent Na/K pump cannot carry a cycle history or rate")
        membrane = fields["membrane_transferred"][:, 0]
        try:
            # Single compensated reduction also avoids a separate final
            # subtraction when passive current nearly balances pump current.
            equivalent = -math.fsum(
                [*(int(z) * float(v) for z, v in zip(self.valence, membrane, strict=True)), cycles]
            )
        except (OverflowError, ValueError) as error:
            raise ValueError("Ledger charge is not representable") from error
        if not math.isfinite(equivalent):
            raise ValueError("Ledger charge is not finite")
        return np.asarray([equivalent, -equivalent])

    def charge_increment_C(self, reduced):
        """Convenience scaling; original qi/qo anchors are never changed here."""
        charge = self.charge_increment_fmol(reduced) * CHARGE_PER_FMOL
        if not np.isfinite(charge).all():
            raise ValueError("Ledger charge in coulombs is not finite")
        return charge


def bind(c):
    """Admit only the closed, single-pair, channel/junction/face-free subset."""
    m = c["raw"]["model"]
    if (
        m["id"] != MODEL_ID
        or m["temperature_K"] != 298.15
        or len(m["cells"]) != 1
        or len(m["extracellular"]) != 1
        or len(m["membranes"]) != 1
        or m["channels"]
        or m["junctions"]
        or m["faces"]
    ):
        raise ValueError("Material coordinates require the declared sealed single-pair subset")
    inside, outside, patch = m["cells"][0], m["extracellular"][0], m["membranes"][0]
    if (
        outside["reservoir"] is not False
        or patch["inside"] != inside["id"]
        or patch["outside"] != outside["id"]
        or m["closure"]
        != dict(
            law="resolved_capacitor_components_current_continuity@1",
            gauge_reference=outside["id"],
        )
        or not all(_finite_number(row["initial_charge_C"]) for row in (inside, outside))
        or math.fsum((inside["initial_charge_C"], outside["initial_charge_C"])) != 0
    ):
        raise ValueError("Require finite paired charge owners and the actual exterior gauge")
    ids = tuple(row["id"] for row in m["species"])
    z = tuple(row["valence"] for row in m["species"])
    if not ids or len(set(ids)) != len(ids) or any(type(v) is not int for v in z):
        raise ValueError("Require distinct species with explicit integer valences")
    if (
        not np.array_equal(c["qi"], [inside["initial_charge_C"]])
        or not np.array_equal(c["qo"], [outside["initial_charge_C"]])
        or not np.array_equal(c["layout"]["valence"], [[v] for v in z])
        or not np.array_equal(c["layout"]["membrane_cell"], [0])
        or not np.array_equal(c["layout"]["membrane_outside"], [0])
    ):
        raise ValueError("Bound charge, valence and patch axes must retain their original owners")
    pools = m["energy_pools"]
    if len(pools) != 1 or pools[0]["cell_id"] != inside["id"]:
        raise ValueError("Require the unchanged inside-owned finite pool")
    pool_id = pools[0]["id"]
    if any(row["pool_id"] != pool_id for row in m["regeneration_ports"]):
        raise ValueError("Regeneration must retain the inside-owned finite pool")
    pump, stoichiometry = patch["pump"], [0] * len(ids)
    if pump is not None:
        roles = pump["roles"]
        if (
            pump["law"] != "nak_atp_mass_action_positive@1"
            or set(roles) != {"sodium", "potassium"}
            or roles["sodium"] == roles["potassium"]
            or not set(roles.values()) <= set(ids)
            or pump["stoichiometry"] != {roles["sodium"]: -3, roles["potassium"]: 2}
            or pump["metabolism"] != dict(kind="finite_energy_pool@1", pool_id=pool_id)
        ):
            raise ValueError("Require the declared inside-owned 3Na/2K finite-pool pump")
        for role, coefficient in (("sodium", -3), ("potassium", 2)):
            index = ids.index(roles[role])
            if z[index] != 1:
                raise ValueError("Na/K pump roles require monovalent cations")
            stoichiometry[index] = coefficient
    routes = m["cotransporters"]
    nu = np.zeros((len(ids), len(routes)), dtype=np.int64)
    names = set()
    for j, route in enumerate(routes):
        if route["id"] in names or route["membrane_id"] != patch["id"]:
            raise ValueError("Neutral cotransport must retain distinct actual patch owners")
        names.add(route["id"])
        roles = route["roles"]
        if route["law"] == "kcc_reversible_tanh@1":
            expected = {"potassium": (1, 1), "chloride": (-1, 1)}
        elif route["law"] == "nkcc_reversible_tanh@1":
            expected = {"sodium": (1, 1), "potassium": (1, 1), "chloride": (-1, 2)}
        else:
            raise ValueError("Only the declared neutral KCC/NKCC laws are supported")
        if (
            set(roles) != set(expected)
            or len(set(roles.values())) != len(roles)
            or not set(roles.values()) <= set(ids)
        ):
            raise ValueError("Require explicit distinct neutral-cotransport species roles")
        for role, (valence, coefficient) in expected.items():
            index = ids.index(roles[role])
            if z[index] != valence:
                raise ValueError("Neutral cotransport role valence mismatch")
            nu[index, j] = coefficient
        if sum(int(z[i]) * int(nu[i, j]) for i in range(len(ids))) != 0:
            raise ValueError("Cotransport must have exactly zero stoichiometric charge")
    if (
        not np.array_equal(nu, c["cotransport_nu"])
        or not np.array_equal(c["cotransport_inside"], [0] * len(routes))
        or not np.array_equal(c["cotransport_outside"], [1] * len(routes))
    ):
        raise ValueError("Bound cotransport coefficients differ from their declared owners")
    shapes = dict(c["shapes"])
    s, r, g = len(ids), len(routes), len(m["regeneration_ports"])
    expected_shapes = dict(
        amount_increment=(s, 1),
        extracellular_amount_increment=(s, 1),
        membrane_transferred=(s, 1),
        junction_transferred=(s, 0),
        face_transferred=(s, 0),
        reservoir_supplied=(s, 1),
        membrane_dissipated_energy_pJ=(1,),
        junction_dissipated_energy_pJ=(0,),
        face_dissipated_energy_pJ=(0,),
        electrode_charge_transferred_C=(1,),
        reservoir_work_pJ=(1,),
        electrode_work_pJ=(1,),
        channel_gate=(2, 0),
        channel_transferred=(s, 0),
        channel_dissipated_energy_pJ=(s, 0),
        junction_gate=(0,),
        pump_cycles=(1,),
        pump_dissipated_energy_pJ=(1,),
        metabolic_work_pJ=(1,),
        energy_amount_increment_fmol=(3, 1),
        regeneration_cycles_fmol=(g,),
        regeneration_dissipated_energy_pJ=(g,),
        regeneration_supplied_work_pJ=(g,),
        volume_increment_pL=(1,),
        extracellular_volume_increment_pL=(1,),
        water_transferred_pL=(1,),
        water_dissipated_energy_pJ=(1,),
        pool_volume_work_pJ=(1,),
        cotransport_cycles_fmol=(r,),
        cotransport_transferred_fmol=(s, r),
        cotransport_dissipated_energy_pJ=(r,),
    )
    if tuple(shapes) != FIELD_NAMES or shapes != expected_shapes:
        raise ValueError("Require all 31 original, unpadded reference field shapes and order")
    slices, indices, offset = {}, [], 0
    for name, shape in shapes.items():
        end = offset + math.prod(shape)
        slices[name] = slice(offset, end)
        if name not in BULK_FIELDS:
            indices.extend(range(offset, end))
        offset = end
    return MaterialCoordinates(
        shapes=MappingProxyType(shapes),
        slices=MappingProxyType(slices),
        integrated_indices=_immutable(indices, np.int64),
        species_ids=ids,
        valence=_immutable(z, np.int64),
        pump_stoichiometry=_immutable(stoichiometry, np.int64),
        cotransport_nu=_immutable(nu, np.int64),
        pump_present=pump is not None,
        full_size=offset,
    )
