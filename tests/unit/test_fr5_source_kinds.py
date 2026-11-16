"""FR-5's source kinds (the FR-4/FR-5 note's §16): cells.patch_damage@1 and cells.ph_condition@1.

Their declarations and refusals through the real parse (FR-4's development world with the kinds
declared), and their hooks on the host: the damage's exact step from the applied hazards
(composition, the equilibrium, [0, 1] at any step, no schedule leaves d unchanged), the
derivatives the tableau carries, and both kinds' factors for the routing door (the core's seam).
The engine's run of both kinds is test_fr5_source_kinds_engine.py.
"""

import copy
import math
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models.inner_kinds import patch_damage as damage
from cells.models.inner_kinds import ph_condition as condition
from cells.processes import ph_condition as phc
from cells.processes import rapid_proton_buffer as closure
from validation.compartment_ph_engine import definitions as defs

DAMAGE = dict(id="damage_0", patch=defs.BOUNDING, law="bounding_patch_damage@1",
              initial_damage=0.25, injury_rate_per_s=1.0, resealing_rate_per_s=0.05)
CONDITION = dict(id="acid_0", node=defs.LUMEN, law="ph_conditioned_factor@1", ph50=5.5,
                 slope=4.0)


def world(damages=(DAMAGE,), conditions=(CONDITION,)):
    """FR-4's development world with the source kinds declared (no route reads them yet)."""
    d = defs.development_world(defs.fr4_world())
    if damages is not None:
        d["model"]["patch_damage"] = [copy.deepcopy(x) for x in damages]
    if conditions is not None:
        d["model"]["ph_conditions"] = [copy.deepcopy(x) for x in conditions]
    return d


def refused(match, **changes):
    damages = changes.pop("damages", (DAMAGE,))
    conditions = changes.pop("conditions", (CONDITION,))
    with pytest.raises(ConfigError, match=match):
        parse_spec(world(damages, conditions))


# ------------------------------------------------------------------------ declarations


def test_both_kinds_parse_round_trip_and_append_their_fields():
    spec = parse_spec(world())
    kinds = dict(spec.model.kinds)
    (d,) = kinds[damage.KIND_ID]
    (c,) = kinds[condition.KIND_ID]
    assert d == damage.Damage("damage_0", defs.BOUNDING, 0.25, 1.0, 0.05)
    assert c == condition.Condition("acid_0", defs.LUMEN, 5.5, 4.0, "H")
    assert damage.parse(damage.to_dict(kinds[damage.KIND_ID]), spec) == kinds[damage.KIND_ID]
    assert condition.parse(condition.to_dict(kinds[condition.KIND_ID]), spec) == kinds[
        condition.KIND_ID]
    assert damage.factor_sources(kinds[damage.KIND_ID]) == ("damage_0",)
    assert condition.factor_sources(kinds[condition.KIND_ID]) == ("acid_0",)
    from cells.models.registry import get_model

    model = get_model(spec.model)
    fields = model.STATE_TYPE._fields
    assert {"patch_damage", "patch_damage_injury_hazard", "patch_damage_resealing_hazard"} <= set(
        fields)
    state, p = model.initial_values(spec)
    bounding = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
    assert float(state.patch_damage[bounding]) == 0.25
    assert np.count_nonzero(state.patch_damage) == 1
    assert list(p.patch_damage_source_slot) == [bounding]
    nodes = [c.id for c in spec.model.cells] + [o.id for o in spec.model.extracellular]
    assert list(p.ph_condition_node) == [nodes.index(defs.LUMEN)]


@pytest.mark.parametrize("change, match", [
    (dict(patch="nowhere"), "unknown membrane patch"),
    (dict(law="prescribed_patch_injury_resealing@1"), "law is cells.bounding_patch_damage@1"),
    (dict(initial_damage=1.5), r"lies in \[0, 1\]"),
    (dict(initial_damage=-0.1), "initial_damage must be finite and nonnegative"),
    (dict(resealing_rate_per_s=-1.0), "resealing_rate_per_s must be finite and nonnegative"),
    (dict(injury_rate_per_s=float("nan")), "injury_rate_per_s must be finite"),
    (dict(id=defs.LUMEN), "unique among the model's IDs"),
])
def test_a_damage_entity_outside_its_contract_is_refused(change, match):
    refused(match, damages=(dict(DAMAGE, **change),))


def test_one_damage_per_patch_unique_ids_and_a_nonempty_list():
    refused("already carries a damage", damages=(DAMAGE, dict(DAMAGE, id="damage_1")))
    refused("unique", damages=(DAMAGE, dict(DAMAGE, patch=defs.PLASMA)))
    refused("non-empty list", damages=())
    refused("missing", damages=({k: v for k, v in DAMAGE.items() if k != "initial_damage"},))


@pytest.mark.parametrize("change, match", [
    (dict(node="nowhere"), "unknown node"),
    (dict(law="ph_condition@1"), "law is cells.ph_conditioned_factor@1"),
    (dict(slope=0.0), "slope"),
    (dict(slope=-4.0), "slope"),
    (dict(ph50=float("inf")), "ph50"),
    (dict(proton="Q"), "unknown proton row"),
    (dict(proton="Cl"), "valence"),
    (dict(proton="K"), "closure's proton row"),
    (dict(id=defs.BOUNDING), "unique among the model's IDs"),
])
def test_a_condition_outside_its_contract_is_refused(change, match):
    refused(match, conditions=(dict(CONDITION, **change),))


def test_an_undeclared_source_kind_is_absent():
    spec = parse_spec(world(damages=None, conditions=None))
    assert not {damage.KIND_ID, condition.KIND_ID} & set(dict(spec.model.kinds))
    from cells.models.registry import get_model

    fields = get_model(spec.model).STATE_TYPE._fields
    assert not any(f.startswith("patch_damage") for f in fields)


# ------------------------------------------------------------------------ the damage's step


def layout(k=3, present=(False, True, False), injury=1.0, resealing=0.05):
    present = np.asarray(present)
    return SimpleNamespace(
        patch_damage_present=present,
        patch_damage_injury_rate_per_s=np.where(present, injury, 0.0),
        patch_damage_resealing_rate_per_s=np.where(present, resealing, 0.0),
        patch_damage_source_slot=np.flatnonzero(present),
    )


def closed_form(d0, a, b, t):
    s = a + b
    if s == 0:
        return d0
    eq = a / s
    return eq + (d0 - eq) * math.exp(-s * t)


@pytest.mark.parametrize("d0, a, b", [(0.0, 1.0, 0.0), (0.25, 1.0, 0.05), (0.99995, 0.0, 0.05),
                                       (0.5, 0.0, 0.0), (1.0, 1.0, 0.0), (0.3, 2e3, 7e2)])
def test_the_exact_step_composes_and_matches_the_closed_form(d0, a, b):
    """n steps of the exact step from the applied hazards equal the closed form to rounding, and
    two half steps equal one step: d is exact at every step's end."""
    h, n = 5e-4, 2000
    d = np.asarray(d0)
    for _ in range(n):
        d = damage.exact_damage(d, a * h, b * h, xp=np)
    assert abs(float(d) - closed_form(d0, a, b, n * h)) <= 8 * n * np.finfo(float).eps
    one = damage.exact_damage(np.asarray(d0), a * h, b * h, xp=np)
    half = damage.exact_damage(damage.exact_damage(np.asarray(d0), a * h / 2, b * h / 2, xp=np),
                               a * h / 2, b * h / 2, xp=np)
    assert abs(float(one) - float(half)) <= 4 * np.finfo(float).eps
    assert 0.0 <= float(d) <= 1.0


def test_d_stays_in_unit_interval_at_any_step_and_no_hazard_leaves_it_unchanged():
    for d0 in (0.0, 0.1, 0.5, 0.9, 1.0):
        for a_h, b_h in ((1e4, 0.0), (0.0, 1e4), (3e3, 5e3), (1e-20, 1e-20)):
            d = float(damage.exact_damage(np.asarray(d0), a_h, b_h, xp=np))
            assert 0.0 <= d <= 1.0
        assert float(damage.exact_damage(np.asarray(d0), 0.0, 0.0, xp=np)) == d0


def test_book_takes_the_applied_hazards_and_rates_carry_the_derivatives():
    p = layout()
    control = SimpleNamespace(patch_damage_injury=np.array([0.0, 1.0, 0.0]),
                              patch_damage_resealing=np.array([0.0, 1.0, 0.0]))
    a, b = damage.hazard_rates(control, p)
    assert list(a) == [0.0, 1.0, 0.0] and list(b) == [0.0, 0.05, 0.0]
    start = SimpleNamespace(patch_damage=np.array([0.0, 0.4, 0.0]))
    applied = {"patch_damage_injury_hazard": a, "patch_damage_resealing_hazard": b}.__getitem__
    booked, ok = damage.book(applied, start, None, p, 1e-3, xp=np)
    expected = closed_form(0.4, 1.0, 0.05, 1e-3)
    assert ok and abs(booked["patch_damage"][1] - expected) <= 4 * np.finfo(float).eps
    assert booked["patch_damage"][0] == booked["patch_damage"][2] == 0.0
    state = SimpleNamespace(patch_damage=np.array([0.0, 0.4, 0.0]),
                            amount_increment=np.zeros((9, 1)),
                            extracellular_amount_increment=np.zeros((9, 2)))
    rates = damage.rates(state, None, control, p, xp=np)
    assert rates.valid and not rates.cell.any() and not rates.outside.any()
    assert rates.derivatives["patch_damage"][1] == pytest.approx(1.0 * 0.6 - 0.05 * 0.4)
    assert list(rates.derivatives["patch_damage_injury_hazard"]) == list(a)
    assert float(rates.heat_pJ_s) == float(rates.work_pJ_s) == 0.0
    out_of_range = SimpleNamespace(**{**vars(state), "patch_damage": np.array([0.0, 1.2, 0.0])})
    assert not damage.rates(out_of_range, None, control, p, xp=np).valid


def test_the_damage_domain_and_its_factor():
    p = layout()
    good = SimpleNamespace(patch_damage=np.array([0.0, 0.7, 0.0]),
                           patch_damage_injury_hazard=np.array([0.0, 3.0, 0.0]),
                           patch_damage_resealing_hazard=np.array([0.0, 0.1, 0.0]))
    assert damage.domain(good, p, xp=np)
    for name, value in (("patch_damage", [0.0, 1.0 + 1e-12, 0.0]),
                        ("patch_damage", [0.1, 0.7, 0.0]),
                        ("patch_damage_injury_hazard", [0.0, -1e-30, 0.0])):
        assert not damage.domain(SimpleNamespace(**{**vars(good), name: np.array(value)}), p,
                                 xp=np)
    assert list(damage.factors(good, p, xp=np)) == [0.7]


# ------------------------------------------------------------------------ the condition's factor


def test_the_condition_reads_free_h_at_its_node_as_b4s_ph():
    spec = parse_spec(world())
    from cells.models.registry import get_model

    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    from cells.models.inner_kinds import proton_buffer

    read, ok = proton_buffer.PROTON_BUFFER.stage_read(state, p, xp=np)
    assert ok
    nodes = [c.id for c in spec.model.cells] + [o.id for o in spec.model.extracellular]
    lumen = nodes.index(defs.LUMEN)
    # The condition reads what every rate of the stage reads: the read's H row over the volume.
    h = condition.free_proton_mM(read, p, xp=np)
    volume = np.concatenate((p.volume, p.extracellular_volume))
    amounts = np.concatenate((p.amount_reference + read.amount_increment,
                              p.extracellular_amount_reference
                              + read.extracellular_amount_increment), axis=1)
    assert float(h[0]) == float(amounts[[s for s, _ in defs.SPECIES].index("H"), lumen]
                                / volume[lumen])
    ph_read = -np.log10(h[0] / closure.PH_REFERENCE_mM)
    f = condition.factors(read, p, xp=np)
    assert float(f[0]) == float(phc.factor(ph_read, 5.5, 4.0, xp=np))
    assert 0.0 < float(f[0]) < 1e-6  # pH 7.2 against pH50 5.5: closed.
    # B4's own readout recomputes h from the closure; the read holds h V as an increment on the
    # stored row's reference, so the two agree to about eps H_eq / (h V) relative in h.
    columns = proton_buffer.PROTON_BUFFER.readouts(state, read, None, None, p, xp=np)
    ph = dict(zip(proton_buffer.COLUMNS, columns, strict=True))["pH"]
    assert abs(float(ph_read) - float(ph[lumen])) <= 1e-11
    (column,) = condition.readouts(state, read, None, None, p, xp=np)
    assert list(column) == list(f)
