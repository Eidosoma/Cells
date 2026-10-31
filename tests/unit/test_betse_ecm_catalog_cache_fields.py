"""Cache readiness contracts only; no channel or physiological evolution."""

import ast
import copy
import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_channel_catalog_source as catalog
from cells.processes import betse_normal_ecm_catalog_join_source as source

FUNNY_CLASSES = ("HCN1", "HCN2", "HCN2_cAMP", "HCN4", "HCN4_cAMP", "HCNLeak")


def cache_metadata(cls, calls):
    """Small schema example; values are not a physiological initialization."""
    core = dict(
        targets=np.arange(3, dtype=np.int64),
        data_length=3,
        mdl=3,
        ions=[ion for ion, _ in source.ROUTES[cls]],
        rel_perm=[value for _, value in source.ROUTES[cls]],
        time_unit=1000.0,
        m=np.ones(3),
        h=np.ones(3),
        v_corr=0.0,
        modulator=1.0,
        chan_flux=np.zeros(3),
        DChan=None,
    )
    origin = dict(fields=dict(name="test", channel_type=cls), core_class=cls, core_fields=core)
    current = copy.deepcopy(origin)
    if calls:
        hot = {"P": np.ones(3), "_mInf": np.ones(3), "_mTau": np.ones(3)}
        if cls != "HCN2_ML":
            hot.update(_hInf=np.ones(3), _hTau=np.ones(3))
        if cls in FUNNY_CLASSES:
            hot["vrev"] = -45
        current["core_fields"].update(hot)
    cache = dict(
        wire=dict(channel_fields={"test": current}, owner_fields=dict(channels=True)),
        initial_channel_fields={"test": origin},
        channel_calls={"test": calls},
    )
    ctx = SimpleNamespace(
        catalog=dict(
            populations=[{"name": "test", "channel type": cls, "apply to": "all"}],
            tissue_profiles={},
        ),
        cells=SimpleNamespace(mem_i=np.arange(3)),
    )
    return ctx, cache


@pytest.mark.parametrize("cls", FUNNY_CLASSES)
@pytest.mark.parametrize("calls", [0, 1, 3])
def test_funny_constructor_and_hot_cache_are_distinct(cls, calls):
    ctx, cache = cache_metadata(cls, calls)
    before = copy.deepcopy(cache)
    source.validate_cached_channels(ctx, cache)
    assert source.equal_tree(cache, before)
    assert "vrev" not in cache["initial_channel_fields"]["test"]["core_fields"]
    assert ("vrev" in cache["wire"]["channel_fields"]["test"]["core_fields"]) is bool(calls)


@pytest.mark.parametrize(
    "mutation",
    ["cold_vrev", "missing_vrev", "extra_field", "target", "owner", "nonfinite_vrev"],
)
def test_funny_cache_still_rejects_missing_extra_or_corrupted_owners(mutation):
    ctx, cache = cache_metadata("HCN1", 0 if mutation == "cold_vrev" else 1)
    core = cache["wire"]["channel_fields"]["test"]["core_fields"]
    if mutation == "cold_vrev":
        core["vrev"] = -45
    elif mutation == "missing_vrev":
        del core["vrev"]
    elif mutation == "extra_field":
        core["unknown_gate"] = 0.0
    elif mutation == "target":
        core["targets"] = np.array([2, 1, 0])
    elif mutation == "owner":
        cache["wire"]["owner_fields"]["channels"] = False
    else:
        core["vrev"] = float("nan")
    with pytest.raises(ValueError):
        source.validate_cached_channels(ctx, cache)


@pytest.mark.parametrize("cls", ["HCN2_ML", "Nav1p2"])
def test_other_families_keep_their_existing_hot_schema(cls):
    ctx, cache = cache_metadata(cls, 1)
    source.validate_cached_channels(ctx, cache)
    cache["wire"]["channel_fields"]["test"]["core_fields"]["vrev"] = -45
    with pytest.raises(ValueError, match="source-private"):
        source.validate_cached_channels(ctx, cache)


def test_calculated_field_inventory_matches_literal_method_writes():
    """The guard table must follow class bodies, not a family-level guess."""
    tree = ast.parse(inspect.getsource(catalog))
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    assert set(catalog.CALCULATED_FIELDS) == set(source.FAMILIES)
    for cls in source.FAMILIES:
        method = next(
            node
            for node in classes[catalog.CLASSES[cls].__name__].body
            if isinstance(node, ast.FunctionDef) and node.name == "_calculate_state"
        )
        written = {
            node.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        }
        assert written == set(catalog.CALCULATED_FIELDS[cls]), cls
