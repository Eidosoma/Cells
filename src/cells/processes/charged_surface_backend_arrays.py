"""Typed array trees and allocation schemas; no science imported at module load."""

import math
from dataclasses import dataclass
from typing import NamedTuple


class State(NamedTuple):
    amount_increment_fmol: object
    transferred_fmol: object
    dissipated_energy_pJ: object
    field_work_pJ: object


class KernelValues(NamedTuple):
    density_fmol_um2: object
    flux_fmol_s: object
    amount_rate_fmol_s: object
    forward_rate_s_inv: object
    reverse_rate_s_inv: object
    outgoing_rate_s_inv: object
    cell_rate_residual_fmol_s: object
    valid: object


class Layout(NamedTuple):
    temperature_K: object
    effective_charge_e: object
    cell_active: object
    patch_active: object
    patch_cell: object
    patch_area_um2: object
    edge_active: object
    edge_sender: object
    edge_receiver: object
    edge_diffusivity_um2_s: object
    edge_width_um: object
    edge_distance_um: object


class Parameters(NamedTuple):
    layout: object
    anchor: object
    reference: object
    potential: object


class Inputs(NamedTuple):
    state: object
    parameters: object
    dt_s: object
    ready: object


class StageTrace(NamedTuple):
    unmasked_state: object
    attempted: object
    domain_valid: object
    kernel_called: object
    kernel: object
    energetic_called: object
    values: object
    ok: object
    code: object


class BalanceTrace(NamedTuple):
    called: object
    values: object
    ok: object


class Attempt(NamedTuple):
    initial_balance: object
    initial: object
    trials: object
    endpoint: object
    endpoint_balance: object
    loss_called: object
    loss_dt_outgoing: object
    actual_dt_s: object
    ready: object
    endpoint_formed: object
    ok: object
    code: object
    candidate: object


@dataclass(frozen=True)
class Leaf:
    dtype: str
    shape: tuple


def map_tree(function, value):
    if isinstance(value, dict):
        return {key: map_tree(function, value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        items = (map_tree(function, item) for item in value)
        return type(value)(*items) if hasattr(value, "_fields") else tuple(items)
    return function(value)


def schemas(c, m, k, e):
    """Exact dtypes/axes before array allocation; geometry values are irrelevant."""

    def real(*shape):
        return Leaf("<f8", tuple(shape))

    def boolean(*shape):
        return Leaf("|b1", tuple(shape))

    def integer(*shape):
        return Leaf("<i8", tuple(shape))

    state = State(real(k, m), real(k, e), real(k, e), real(k, e))
    kernel = KernelValues(
        real(k, m),
        real(k, e),
        real(k, m),
        real(k, e),
        real(k, e),
        real(k, m),
        real(k, c),
        boolean(),
    )
    layout = Layout(
        real(),
        real(k),
        boolean(c),
        boolean(m),
        integer(m),
        real(m),
        boolean(e),
        integer(e),
        integer(e),
        real(k, e),
        real(e),
        real(e),
    )
    energy = dict(
        kernel=kernel,
        amount_fmol=real(k, m),
        chemical_mu_J_mol=real(k, m),
        electrochemical_mu_J_mol=real(k, m),
        electrochemical_drop_J_mol=real(k, e),
        chemical_power_patch_pJ_s=real(k, m),
        dissipation_edge_pJ_s=real(k, e),
        field_power_edge_pJ_s=real(k, e),
        cargo_charge_C=real(k, m),
        cargo_charge_rate_C_s=real(k, m),
        cell_cargo_charge_rate_C_s=real(k, c),
        energy_rate_residual_pJ_s=real(k),
        derivative=state,
    )
    balances = dict(
        local_material_fmol=real(k, m),
        cell_material_fmol=real(k, c),
        cell_cargo_charge_C=real(k, c),
        chemical_energy_change_pJ=real(k),
        energy_balance_pJ=real(k),
        exact_prescribed_field_transfer_work_link_pJ=real(k, e),
    )
    stage = StageTrace(
        state,
        boolean(),
        boolean(),
        boolean(),
        kernel,
        boolean(),
        energy,
        boolean(),
        Leaf("<i4", ()),
    )
    balance = BalanceTrace(boolean(), balances, boolean())
    inputs = Inputs(state, Parameters(layout, real(k, m), real(k), real(m)), real(), boolean())
    attempt = Attempt(
        balance,
        stage,
        (stage, stage, stage, stage),
        stage,
        balance,
        boolean(),
        real(k, m),
        real(),
        boolean(),
        boolean(),
        boolean(),
        Leaf("<i4", ()),
        state,
    )
    return dict(
        state=state,
        kernel=kernel,
        energy=energy,
        balances=balances,
        stage=stage,
        balance=balance,
        inputs=inputs,
        attempt=attempt,
    )


def zero_tree(schema, xp):
    return map_tree(lambda leaf: xp.zeros(leaf.shape, dtype=leaf.dtype), schema)


def leaf_list(tree):
    result = []
    map_tree(lambda leaf: result.append(leaf), tree)
    return result


def schema_bytes(schema, *, worlds=1):
    widths = {"<f8": 8, "<i8": 8, "<i4": 4, "|b1": 1}
    return worlds * sum(widths[leaf.dtype] * math.prod(leaf.shape) for leaf in leaf_list(schema))


def actual_bytes(tree):
    return sum(int(value.nbytes) for value in leaf_list(tree))


def check_axes(tree, schema, np, *, worlds=None):
    def structure(value):
        if isinstance(value, dict):
            return ("dict", tuple((key, structure(value[key])) for key in sorted(value)))
        if isinstance(value, tuple):
            return (
                "tuple",
                getattr(value, "_fields", None),
                tuple(structure(item) for item in value),
            )
        return "leaf"

    if structure(tree) != structure(schema):
        raise ValueError("Complete named array tree structure differs")
    values, expected = leaf_list(tree), leaf_list(schema)
    if len(values) != len(expected):
        raise ValueError("Complete array leaf inventory differs")
    for value, leaf in zip(values, expected, strict=True):
        prefix = () if worlds is None else (worlds,)
        if np.asarray(value).dtype.str != leaf.dtype or value.shape != prefix + leaf.shape:
            raise ValueError("Exact array dtype/axes differ from declared group schema")
