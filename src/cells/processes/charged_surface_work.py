"""HELD supplied-patch charged-cargo owner with explicit prescribed-field work.

The existing finite-volume flux kernel and RK4 arithmetic are reused unchanged.
This is an isothermal ideal-mixture component with a time-constant imposed
potential, not an endogenous field solver, biological calibration or native
BETSE radial-redistribution trajectory. Importing this module loads no science.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import NamedTuple

LAW_ID = "held_charged_surface_prescribed_field_work@1"
HELD_SOURCE_PROTOTYPE = True
NUMERICAL_LAUNCH_AUTHORIZED = False
MATERIAL_ATOL_FMOL = 2e-12
ENERGY_ATOL_PJ = 2e-10
DISSIPATION_ATOL_PJ = 1e-12
ENERGY_RATE_ATOL_PJ_S = 3e-12
CHARGE_ATOL_C = 3e-25
CHARGE_RATE_ATOL_A = 3e-23
MAX_LOSS_PER_STEP = 0.05
MAX_CELLS, MAX_PATCHES, MAX_POPULATIONS, MAX_EDGES, MAX_STEPS = 16, 64, 8, 128, 4096
STATE_FIELDS = (
    "amount_increment_fmol",
    "transferred_fmol",
    "dissipated_energy_pJ",
    "field_work_pJ",
)
SOURCE_PINS = {
    "src/cells/__init__.py": "c52dd018d1eabbb38929a8c5d5fedb125b01c37da01012933af1588f4f6cfa5e",
    "src/cells/numerics/__init__.py": (
        "78f29ade80db277f67facd2022a2405a218cc12ecb03015bf42ba9f43e253696"
    ),
    "src/cells/processes/__init__.py": (
        "26ca2cc8045c256192fee77ec49fc76520af2a95d9835d09fc23882661883142"
    ),
    "src/cells/numerics/membrane_redistribution.py": (
        "6e12f8e10d62a90741818685882954ec43d01f828ea6dbf3c87fa300fa2140ab"
    ),
    "src/cells/numerics/fixed_step.py": (
        "a9821afc713c07b18c4d586ba7e991379eb011be54494a177aab13b8a39dd3b6"
    ),
    "src/cells/numerics/extracellular_field.py": (
        "bb0702893a0605616fa84e7864d1e8b4409dbf3404a0b8c8195a538c2488fbbf"
    ),
    "src/cells/processes/electrochemistry.py": (
        "e52dc29e3514268d538b7ceff293d32fd24d36ed3e9ef6242dc2906592c112f2"
    ),
}


class SurfaceRejected(ValueError):
    def __init__(self, code, *, stage, partial=None):
        super().__init__(code)
        self.code, self.stage, self.partial = code, stage, partial


def require(value, code, *, stage="owner_binding", partial=None):
    if not value:
        raise SurfaceRejected(code, stage=stage, partial=partial)


def canonical(value):
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    if type(value) is dict:
        return {key: canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(
            canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def parse(text, *, max_bytes=2**20):
    require(type(text) is str and len(text.encode()) <= max_bytes, "bounded_complete_owner_JSON")

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate_owner_JSON_key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite owner JSON: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


@dataclass(frozen=True)
class Buffer:
    dtype: str
    shape: tuple
    data_hex: str


@dataclass(frozen=True)
class Binding:
    declaration_json: str
    source_pins_json: str
    identity: str


@dataclass(frozen=True)
class Checkpoint:
    binding_identity: str
    state: tuple
    time_s: float
    step_index: int
    identity: str


@dataclass(frozen=True)
class Proposal:
    binding_identity: str
    parent_identity: str
    candidate: Checkpoint
    evidence_json: str
    identity: str


class Vector(NamedTuple):
    amount_increment_fmol: object
    transferred_fmol: object
    dissipated_energy_pJ: object
    field_work_pJ: object


def _pins():
    require(bool(SOURCE_PINS), "unchanged_kernel_pins_required")
    root = Path(__file__).resolve().parents[3]
    for rel, expected in SOURCE_PINS.items():
        path = root / rel
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        require(actual == expected, "unchanged_dependency:" + rel, stage="source_identity")


def _modules():
    _pins()
    import numpy as np

    from cells.numerics import fixed_step, membrane_redistribution
    from cells.processes.electrochemistry import F, R

    return np, membrane_redistribution, fixed_step, F, R


def _record(value, np):
    if hasattr(value, "_asdict"):
        return {key: _record(item, np) for key, item in value._asdict().items()}
    if type(value) is dict:
        return {key: _record(item, np) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_record(item, np) for item in value]
    if hasattr(value, "dtype"):
        array = np.asarray(value)
        require(array.dtype.kind in "bifu", "explicit_numeric_evidence_dtype")
        return dict(
            dtype=array.dtype.str, shape=list(array.shape), data_hex=array.tobytes(order="C").hex()
        )
    return value


def _buffer(value, np):
    array = np.asarray(value)
    require(array.dtype.str == "<f8", "owned_state_requires_binary64")
    return Buffer(array.dtype.str, tuple(array.shape), array.tobytes(order="C").hex())


def _decode(value, shape, np):
    require(
        type(value) is Buffer and value.dtype == "<f8" and value.shape == shape,
        "complete_state_dtype_and_axes",
    )
    require(
        type(value.data_hex) is str and len(value.data_hex) == 16 * math.prod(shape),
        "complete_state_byte_count",
    )
    data = bytes.fromhex(value.data_hex)
    require(data.hex() == value.data_hex, "canonical_complete_state_hex")
    return np.frombuffer(data, dtype="<f8").reshape(shape)


def checkpoint_record(value):
    return dict(
        binding_identity=value.binding_identity,
        state={
            key: dict(dtype=buf.dtype, shape=list(buf.shape), data_hex=buf.data_hex)
            for key, buf in zip(STATE_FIELDS, value.state, strict=True)
        },
        time_s=value.time_s,
        step_index=value.step_index,
    )


def _seal_checkpoint(binding, values, time, index, np):
    value = Checkpoint(
        binding.identity, tuple(_buffer(v, np) for v in values), float(time), index, ""
    )
    return replace(value, identity=digest(checkpoint_record(value)))


def declaration(binding):
    require(type(binding) is Binding, "owned_binding_type")
    raw = parse(binding.declaration_json)
    pins = parse(binding.source_pins_json)
    require(
        pins == SOURCE_PINS and binding.identity == digest([LAW_ID, raw, pins]),
        "unchanged_complete_binding_seal",
    )
    return raw


def bind(raw):
    """Explicit caller-supplied geometry/fields only; no inferred tissue owners."""
    require(
        type(raw) is dict
        and set(raw)
        == {
            "kind",
            "law",
            "scope",
            "policies",
            "owners",
            "layout",
            "initial_amount_fmol",
            "reference_density_fmol_um2",
            "prescribed_potential_V",
            "time_labels_s",
            "provenance",
        },
        "complete_explicit_owner_declaration",
    )
    require(
        raw["kind"] == "charged_surface_work_declaration@1"
        and raw["law"] == LAW_ID
        and raw["scope"] == "supplied_fixed_surface_prescribed_field_component@1",
        "separate_opt_in_component_scope",
    )
    require(
        raw["policies"]
        == dict(
            chemical="ideal_dilute_surface_mixture@1",
            field="prescribed_time_constant_potential@1",
            thermal="maintained_isothermal_temperature@1",
            charge="constant_effective_cargo_no_ionic_field_feedback@1",
        ),
        "explicit_open_field_and_constitutive_assumptions",
    )
    owners = raw["owners"]
    require(
        set(owners) == {"cells", "patches", "populations", "edges"}, "complete_named_owner_axes"
    )
    limits = dict(
        cells=MAX_CELLS, patches=MAX_PATCHES, populations=MAX_POPULATIONS, edges=MAX_EDGES
    )
    for key, names in owners.items():
        require(
            type(names) is list and (0 if key == "edges" else 1) <= len(names) <= limits[key],
            "bounded_owner_axis:" + key,
        )
        require(
            all(type(name) is str and 0 < len(name.encode()) <= 64 for name in names)
            and len(set(names)) == len(names),
            "unique_ordered_owner_ids:" + key,
        )
    require(
        type(raw["provenance"]) is dict
        and type(raw["provenance"].get("caller")) is str
        and 0 < len(raw["provenance"]["caller"].encode()) <= 1024
        and raw["provenance"].get("units")
        == dict(
            amount="fmol",
            area="um2",
            length="um",
            diffusivity="um2/s",
            potential="V",
            temperature="K",
            energy="pJ",
            time="s",
        ),
        "explicit_caller_and_units",
    )
    labels = raw["time_labels_s"]
    require(
        type(labels) is list
        and 2 <= len(labels) <= MAX_STEPS + 1
        and labels[0] == 0.0
        and all(type(t) in (int, float) and math.isfinite(t) for t in labels)
        and all(b > a for a, b in zip(labels, labels[1:], strict=False)),
        "bounded_original_declared_clock",
    )
    np, movement, _, _, _ = _modules()
    require(set(raw["layout"]) == set(movement.Layout._fields), "all_existing_kernel_layout_fields")
    arrays = {}
    masks = {"cell_active", "patch_active", "edge_active"}
    indices = {"patch_cell", "edge_sender", "edge_receiver"}
    for key, value in raw["layout"].items():
        array = np.asarray(value)
        if key in masks:
            require(
                array.dtype.kind == "b" or (key == "edge_active" and array.size == 0),
                "boolean_mask:" + key,
            )
            array = array.astype(np.bool_)
        elif key in indices:
            # Empty edge axes carry explicit int64 when NumPy's empty-list
            # default would otherwise be float; no nonempty value is coerced.
            require((array.size == 0) or array.dtype.kind in "iu", "integer_owner_indices:" + key)
            array = array.astype(np.int64)
        else:
            require(array.dtype.kind in "fiu", "real_physical_value:" + key)
            array = array.astype(np.float64)
        arrays[key] = array
    p = movement.validate_layout(movement.Layout(**arrays))
    n, m, k, e = map(lambda key: len(owners[key]), ("cells", "patches", "populations", "edges"))
    require(
        (p.cell_active.size, p.patch_active.size, p.effective_charge_e.size, p.edge_active.size)
        == (n, m, k, e),
        "exact_owner_to_kernel_axes",
    )
    values = []
    for key in ("initial_amount_fmol", "reference_density_fmol_um2", "prescribed_potential_V"):
        value = np.asarray(raw[key])
        require(value.dtype.kind in "fiu", "real_explicit_initial_or_imposed_field:" + key)
        values.append(value.astype(np.float64))
    initial, density, potential = values
    require(
        initial.shape == (k, m) and density.shape == (k,) and potential.shape == (m,),
        "complete_owned_initial_and_imposed_fields",
    )
    require(
        np.isfinite(initial).all()
        and np.all(initial >= 0)
        and np.all(initial[:, ~p.patch_active] == 0),
        "nonnegative_initial_and_zero_padding",
    )
    require(
        np.isfinite(density).all() and np.all(density > 0),
        "positive_declared_standard_surface_density",
    )
    require(
        np.isfinite(potential).all() and np.all(potential[~p.patch_active] == 0),
        "finite_prescribed_field_and_zero_padding",
    )
    for cell in np.flatnonzero(p.cell_active):
        selected = initial[:, p.patch_active & (p.patch_cell == cell)]
        require(
            np.all(np.all(selected > 0, axis=1) | np.all(selected == 0, axis=1)),
            "finite_log_domain_requires_filled_or_absent_cell_population",
        )
    text = json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)
    pins = json.dumps(SOURCE_PINS, sort_keys=True, separators=(",", ":"))
    value = Binding(text, pins, "")
    return replace(value, identity=digest([LAW_ID, parse(text), SOURCE_PINS]))


def _parameters(binding):
    raw = declaration(binding)
    require(bind(raw) == binding, "complete_revalidated_canonical_owner_binding")
    np, movement, fixed, F, R = _modules()
    mask = {"cell_active", "patch_active", "edge_active"}
    index = {"patch_cell", "edge_sender", "edge_receiver"}
    p = movement.Layout(
        **{
            key: np.asarray(
                value, dtype=np.bool_ if key in mask else np.int64 if key in index else np.float64
            )
            for key, value in raw["layout"].items()
        }
    )
    movement.validate_layout(p)
    return (
        raw,
        np,
        movement,
        fixed,
        F,
        R,
        p,
        np.asarray(raw["initial_amount_fmol"], dtype=np.float64),
        np.asarray(raw["reference_density_fmol_um2"], dtype=np.float64),
        np.asarray(raw["prescribed_potential_V"], dtype=np.float64),
    )


def initial(binding):
    raw, np, _, _, _, _, p, anchor, _, _ = _parameters(binding)
    k, m = anchor.shape
    e = p.edge_active.size
    zeros = Vector(np.zeros((k, m)), *(np.zeros((k, e)) for _ in range(3)))
    return _seal_checkpoint(binding, zeros, raw["time_labels_s"][0], 0, np)


def _state_domain(vector, p, anchor, np):
    present = anchor > 0
    amount = anchor + vector.amount_increment_fmol
    support = (
        p.edge_active
        & (p.edge_diffusivity_um2_s > 0)
        & present[:, p.edge_sender]
        & present[:, p.edge_receiver]
    )
    valid = np.isfinite(amount).all() and np.all(np.where(present, amount > 0, amount == 0))
    for value, mask in (
        (vector.amount_increment_fmol, present),
        *((value, support) for value in vector[1:]),
    ):
        valid = valid and np.isfinite(value).all() and np.all(np.where(mask, True, value == 0))
    return bool(valid)


def _checkpoint(binding, checkpoint, params):
    raw, np, _, _, _, _, p, anchor, _, _ = params
    require(
        type(checkpoint) is Checkpoint
        and checkpoint.binding_identity == binding.identity
        and checkpoint.identity == digest(checkpoint_record(checkpoint)),
        "complete_bound_checkpoint_seal",
        stage="checkpoint",
    )
    i = checkpoint.step_index
    labels = raw["time_labels_s"]
    require(
        type(i) is int and 0 <= i < len(labels) and checkpoint.time_s == labels[i],
        "exact_global_checkpoint_clock",
        stage="checkpoint",
    )
    k, m = anchor.shape
    e = p.edge_active.size
    require(len(checkpoint.state) == 4, "all_four_surface_ledgers", stage="checkpoint")
    vector = Vector(
        *(
            _decode(value, shape, np)
            for value, shape in zip(checkpoint.state, ((k, m), (k, e), (k, e), (k, e)), strict=True)
        )
    )
    require(
        _state_domain(vector, p, anchor, np),
        "complete_positive_state_and_padding_domain",
        stage="checkpoint",
        partial=checkpoint_record(checkpoint),
    )
    if i == 0:
        require(
            all(np.all(value == 0) for value in vector),
            "original_initial_anchor",
            stage="checkpoint",
        )
    return vector


def _stage(vector, params, retain):
    raw, np, movement, _, F, R, p, anchor, reference, potential = params
    retain("unmasked_state", _record(vector, np))
    require(
        _state_domain(vector, p, anchor, np),
        "positive_unmasked_trial_before_logs",
        stage="trial_domain",
    )
    amount = anchor + vector.amount_increment_fmol
    result = movement.rates(amount, potential, p, xp=np)
    retain("unchanged_flux_kernel_return", _record(result, np))
    require(bool(result.valid), "unchanged_flux_kernel_domain", stage="flux_domain")
    present = anchor > 0
    density = np.where(present, result.density_fmol_um2 / reference[:, None], 1.0)
    chemical_mu = R * p.temperature_K * np.log(density)
    source, destination = p.edge_sender, p.edge_receiver
    electrical_drop = (
        p.effective_charge_e[:, None] * F * (potential[source] - potential[destination])
    )
    affinity = chemical_mu[:, source] - chemical_mu[:, destination] + electrical_drop
    heat = 1e-3 * result.flux_fmol_s * affinity
    work = 1e-3 * result.flux_fmol_s * electrical_drop
    chemical_power = 1e-3 * chemical_mu * result.amount_rate_fmol_s
    residue = chemical_power.sum(axis=1) + heat.sum(axis=1) - work.sum(axis=1)
    electrochemical_mu = chemical_mu + p.effective_charge_e[:, None] * F * potential
    cargo_charge = 1e-15 * F * p.effective_charge_e[:, None] * amount
    cargo_charge_rate = 1e-15 * F * p.effective_charge_e[:, None] * result.amount_rate_fmol_s
    cell_charge_rate = 1e-15 * F * p.effective_charge_e[:, None] * result.cell_rate_residual_fmol_s
    derivative = Vector(result.amount_rate_fmol_s, result.flux_fmol_s, heat, work)
    values = dict(
        kernel=result,
        amount_fmol=amount,
        chemical_mu_J_mol=chemical_mu,
        electrochemical_mu_J_mol=electrochemical_mu,
        electrochemical_drop_J_mol=affinity,
        chemical_power_patch_pJ_s=chemical_power,
        dissipation_edge_pJ_s=heat,
        field_power_edge_pJ_s=work,
        cargo_charge_C=cargo_charge,
        cargo_charge_rate_C_s=cargo_charge_rate,
        cell_cargo_charge_rate_C_s=cell_charge_rate,
        energy_rate_residual_pJ_s=residue,
        derivative=derivative,
    )
    retain("complete_energetic_return", _record(values, np))
    require(
        all(
            np.isfinite(value).all()
            for value in (
                *derivative,
                chemical_mu,
                affinity,
                chemical_power,
                residue,
                electrochemical_mu,
                cargo_charge,
                cargo_charge_rate,
                cell_charge_rate,
            )
        ),
        "finite_complete_energy_rates",
        stage="energy_rate",
    )
    require(
        np.max(np.abs(cell_charge_rate), initial=0) <= CHARGE_RATE_ATOL_A,
        "per_cell_cargo_charge_rate",
        stage="accounting",
    )
    require(
        np.max(np.abs(residue), initial=0) <= ENERGY_RATE_ATOL_PJ_S,
        "open_prescribed_field_energy_rate",
        stage="accounting",
    )
    require(
        np.min(heat, initial=0) >= -ENERGY_RATE_ATOL_PJ_S,
        "ideal_mixture_dissipation_rate",
        stage="accounting",
    )
    return values


def _balances(vector, params):
    _, np, _, _, F, R, p, anchor, reference, potential = params
    from cells.numerics.extracellular_field import ordered_scatter

    delta, h, heat, work = vector
    local = (
        delta
        + ordered_scatter(h, np.zeros_like(delta), (p.edge_sender,), xp=np)
        - ordered_scatter(h, np.zeros_like(delta), (p.edge_receiver,), xp=np)
    )
    cell = ordered_scatter(
        delta, np.zeros((delta.shape[0], p.cell_active.size)), (p.patch_cell,), xp=np
    )
    present = anchor > 0
    safe = np.where(present, anchor, 1.0)
    area = np.where(p.patch_active, p.patch_area_um2, 1.0)
    change = (
        1e-3
        * R
        * p.temperature_K
        * np.sum(
            delta * (np.log(safe / area / reference[:, None]) - 1)
            + (safe + delta) * np.log1p(delta / safe),
            axis=1,
        )
    )
    work_link = (
        work
        + 1e-3
        * p.effective_charge_e[:, None]
        * F
        * (potential[p.edge_receiver] - potential[p.edge_sender])
        * h
    )
    return dict(
        local_material_fmol=local,
        cell_material_fmol=cell,
        cell_cargo_charge_C=1e-15 * F * p.effective_charge_e[:, None] * cell,
        chemical_energy_change_pJ=change,
        energy_balance_pJ=change + heat.sum(axis=1) - work.sum(axis=1),
        exact_prescribed_field_transfer_work_link_pJ=work_link,
    )


def _check_balances(vector, params, previous=None):
    _, np, _, _, _, _, _, _, _, _ = params
    values = _balances(vector, params)
    for key in ("local_material_fmol", "cell_material_fmol"):
        require(
            np.max(np.abs(values[key]), initial=0) <= MATERIAL_ATOL_FMOL,
            "surface_material_ledger:" + key,
            stage="accounting",
            partial=_record(values, np),
        )
    for key in ("energy_balance_pJ", "exact_prescribed_field_transfer_work_link_pJ"):
        require(
            np.isfinite(values[key]).all()
            and np.max(np.abs(values[key]), initial=0) <= ENERGY_ATOL_PJ,
            "open_prescribed_field_energy_ledger:" + key,
            stage="accounting",
            partial=_record(values, np),
        )
    require(
        np.isfinite(values["cell_cargo_charge_C"]).all()
        and np.max(np.abs(values["cell_cargo_charge_C"]), initial=0) <= CHARGE_ATOL_C,
        "per_cell_cargo_charge_ledger",
        stage="accounting",
        partial=_record(values, np),
    )
    require(
        np.min(vector.dissipated_energy_pJ, initial=0) >= -DISSIPATION_ATOL_PJ,
        "nonnegative_cumulative_heat",
        stage="accounting",
    )
    if previous is not None:
        require(
            np.min(vector.dissipated_energy_pJ - previous.dissipated_energy_pJ, initial=0)
            >= -DISSIPATION_ATOL_PJ,
            "adjacent_heat_history",
            stage="accounting",
        )
    return values


def readout(binding, checkpoint, *, observer=None):
    params = _parameters(binding)
    np = params[1]
    raw = {}

    def retain(name, value):
        raw[name] = value
        if observer is not None:
            observer(name, value)

    try:
        vector = _checkpoint(binding, checkpoint, params)
        values = _stage(vector, params, retain)
        balances = _check_balances(vector, params)
        return dict(
            stage=_record(values, np),
            balances=_record(balances, np),
            raw=raw,
            scope="open_prescribed_field_component",
            closed_system_or_biological_claim=False,
        )
    except Exception as error:
        raise SurfaceRejected(
            getattr(error, "code", "surface_readout_failed"),
            stage=getattr(error, "stage", "readout"),
            partial=dict(
                input=checkpoint_record(checkpoint)
                if type(checkpoint) is Checkpoint
                else repr(checkpoint),
                raw=raw,
                cause=getattr(error, "partial", None),
            ),
        ) from error


def advance(binding, checkpoint, *, observer=None):
    """One original declared interval, four guarded RHS calls and an unmasked endpoint."""
    params = _parameters(binding)
    raw, np, _, fixed, _, _, p, _, _, _ = params
    evidence = dict(
        parent=checkpoint_record(checkpoint)
        if type(checkpoint) is Checkpoint
        else repr(checkpoint),
        initial_raw={},
        trials=[],
        endpoint=None,
        endpoint_raw={},
        candidate_accepted=False,
    )

    def retain(name, value):
        if observer is not None:
            observer(name, value)

    try:
        vector = _checkpoint(binding, checkpoint, params)
        _check_balances(vector, params)
        index = checkpoint.step_index
        require(
            index + 1 < len(raw["time_labels_s"]),
            "checkpoint_already_at_declared_horizon",
            stage="clock",
        )
        left, right = raw["time_labels_s"][index : index + 2]
        dt = right - left

        def capture_initial(name, value):
            evidence["initial_raw"][name] = value
            retain("initial/" + name, value)

        initial_rates = _stage(vector, params, capture_initial)
        loss = dt * initial_rates["kernel"].outgoing_rate_s_inv
        evidence["declared_loss_bound"] = _record(loss, np)
        retain("declared_loss_bound", _record(loss, np))
        require(
            np.max(loss, initial=0) <= MAX_LOSS_PER_STEP,
            "existing_integrated_surface_loss_bound",
            stage="step_admission",
            partial=_record(loss, np),
        )

        def rhs(trial):
            role = ("k1", "k2", "k3", "k4")[len(evidence["trials"])]
            entry = dict(role=role, state=_record(trial, np), raw={})
            evidence["trials"].append(entry)
            retain(role + "/input", entry["state"])

            def capture(name, value):
                entry["raw"][name] = value
                retain(role + "/" + name, value)

            result = _stage(trial, params, capture)
            return result["derivative"]

        # rk4_step is imported byte-for-byte from the established solver. Its
        # PyTree traversal does not turn these NumPy leaves into device arrays.
        proposed = fixed.rk4_step(rhs, vector, dt)
        evidence["endpoint"] = _record(proposed, np)
        retain("unmasked_endpoint", evidence["endpoint"])
        require(
            _state_domain(proposed, p, params[7], np), "unmasked_endpoint_domain", stage="endpoint"
        )

        def capture_endpoint(name, value):
            evidence["endpoint_raw"][name] = value
            retain("endpoint/" + name, value)

        values = _stage(proposed, params, capture_endpoint)
        balances = _balances(proposed, params)
        evidence["raw_balances"] = _record(balances, np)
        retain("raw_balances", evidence["raw_balances"])
        _check_balances(proposed, params, previous=vector)
        candidate = _seal_checkpoint(binding, proposed, right, index + 1, np)
        evidence["candidate_checkpoint"] = dict(
            **checkpoint_record(candidate), identity=candidate.identity
        )
        evidence["candidate_accepted"] = True
        evidence["endpoint_readout"] = _record(values, np)
        evidence.update(
            left_s=left, right_s=right, actual_step_s=dt, field_and_thermal_owners_unchanged=True
        )
        value = Proposal(
            binding.identity,
            checkpoint.identity,
            candidate,
            json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False),
            "",
        )
        return replace(
            value,
            identity=digest(
                [
                    LAW_ID,
                    value.binding_identity,
                    value.parent_identity,
                    checkpoint_record(candidate),
                    parse(value.evidence_json, max_bytes=16 * 2**20),
                ]
            ),
        )
    except Exception as error:
        evidence["candidate_accepted"] = False
        raise SurfaceRejected(
            getattr(error, "code", "surface_interval_failed"),
            stage=getattr(error, "stage", "interval"),
            partial=dict(
                evidence=evidence,
                cause=getattr(error, "partial", None),
                original_type=type(error).__name__,
                original_reason=str(error),
            ),
        ) from error


def dump_checkpoint(checkpoint):
    return json.dumps(
        dict(
            kind="charged_surface_complete_checkpoint@1",
            **checkpoint_record(checkpoint),
            identity=checkpoint.identity,
        ),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def load_checkpoint(binding, text):
    value = parse(text)
    require(
        set(value) == {"kind", "binding_identity", "state", "time_s", "step_index", "identity"}
        and value["kind"] == "charged_surface_complete_checkpoint@1"
        and set(value["state"]) == set(STATE_FIELDS),
        "complete_checkpoint_JSON",
        stage="checkpoint",
    )
    buffers = []
    for key in STATE_FIELDS:
        row = value["state"][key]
        require(
            set(row) == {"dtype", "shape", "data_hex"}, "complete_buffer_JSON", stage="checkpoint"
        )
        buffers.append(Buffer(row["dtype"], tuple(row["shape"]), row["data_hex"]))
    checkpoint = Checkpoint(
        value["binding_identity"],
        tuple(buffers),
        value["time_s"],
        value["step_index"],
        value["identity"],
    )
    params = _parameters(binding)
    vector = _checkpoint(binding, checkpoint, params)
    _check_balances(vector, params)
    return checkpoint
