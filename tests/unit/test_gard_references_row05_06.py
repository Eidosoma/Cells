"""GARD references, rows 5 and 6: the SSA oracle and the fission partition.

Planted controls: a biased channel choice (under common variates and in the ensemble),
and a split at 0.55 (both partition rules).
"""

from __future__ import annotations

import numpy as np
import pytest

from validation.gard.references import exchange_law as ex
from validation.gard.references import fission_partition as fp
from validation.gard.references import ssa_oracle as so
from validation.gard.references.harness import counts_at_times
from validation.gard.references.kernels import PAIR_CONSISTENT, SINGLE_EVENT
from validation.gard.references.lineage_oracle import DOMAIN_PARTITION, _split, simulate_lineage, stream_uniforms
from validation.gard.references.standin import ensemble_arrays, preprint_law

D = ex.REGISTERED_DESIGN


@pytest.mark.parametrize("form", [PAIR_CONSISTENT, SINGLE_EVENT])
def test_crn_replay_agrees_and_a_biased_choice_is_caught(form):
    law, founder = preprint_law(8, form)
    _, run, a = simulate_lineage(law, founder, n_fissions=8, seed=31)
    so.SSAConvention.from_declared(run["ssa_convention"])
    table = so.ChannelTable.from_declared(run["channels"], law.n_types)
    res = so.check_crn_replay(law, founder, a["event_uniforms"], a["event_channel"], a["event_time"], 80,
                              a["fission_split"], a["fission_followed"], a["events_per_growth"], table, 40000)
    assert res.passed, res.detail
    assert res.detail["events_compared"] > 300
    _, _, bad = simulate_lineage(law, founder, n_fissions=8, seed=31, leave_weight=so.PLANTED_LEAVE_WEIGHT)
    res_bad = so.check_crn_replay(law, founder, bad["event_uniforms"], bad["event_channel"], bad["event_time"], 80,
                                  bad["fission_split"], bad["fission_followed"], bad["events_per_growth"], table,
                                  40000)
    assert not res_bad.passed and res_bad.detail["first_real_difference"] is not None


def _interleaved(G):
    """Join and leave of each type adjacent, with codes 2i+1 (join) and 2i+2 (leave)."""
    t = np.repeat(np.arange(G), 2)
    sg = np.tile([1, -1], G)
    return so.ChannelTable(sg, t, np.where(sg > 0, 2 * t + 1, 2 * t + 2), G)


def test_the_declared_channel_table_is_read_not_assumed():
    law, founder = preprint_law(9, PAIR_CONSISTENT, n_types=40)
    G = law.n_types
    inter = _interleaved(G)
    _, run, a = simulate_lineage(law, founder, n_fissions=3, seed=33, table=inter)
    declared = so.ChannelTable.from_declared(run["channels"], G)
    assert np.array_equal(declared.code, inter.code) and np.array_equal(declared.sign, inter.sign)
    args = (law, founder, a["event_uniforms"], a["event_channel"], a["event_time"], 80,
            a["fission_split"], a["fission_followed"], a["events_per_growth"])
    assert so.check_crn_replay(*args, declared, 40000).passed
    # the same events read with the default order are refused or fail: the order matters
    with pytest.raises(so.ConventionMissing):
        so.check_crn_replay(*args, so.ChannelTable.default(G), 40000)
    relabelled = so.ChannelTable(inter.sign, inter.type_index, inter.code, G)
    wrong_order = so.ChannelTable(np.concatenate([relabelled.sign[::2], relabelled.sign[1::2]]),
                                  np.concatenate([relabelled.type_index[::2], relabelled.type_index[1::2]]),
                                  np.concatenate([relabelled.code[::2], relabelled.code[1::2]]), G)
    assert not so.check_crn_replay(*args, wrong_order, 40000).passed


def test_a_malformed_channel_table_is_refused():
    G = 3
    good = so.ChannelTable.default(G).to_declared([f"t{i}" for i in range(G)])
    so.ChannelTable.from_declared(good, G)
    for mutate in ("drop", "repeat", "stoich", "none"):
        bad = {"rows": [dict(r) for r in good["rows"]]}
        if mutate == "drop":
            bad["rows"] = bad["rows"][:-1]
        elif mutate == "repeat":
            bad["rows"][1] = dict(bad["rows"][0], row=1)
        elif mutate == "stoich":
            bad["rows"][0] = dict(bad["rows"][0], stoichiometry={"assembly": {"t0": -1}})
        else:
            bad = None
        with pytest.raises(so.ConventionMissing):
            so.ChannelTable.from_declared(bad, G)


def test_oracle_refuses_a_run_without_a_declared_convention():
    with pytest.raises(so.ConventionMissing):
        so.SSAConvention.from_declared(None)
    with pytest.raises(so.ConventionMissing):
        so.SSAConvention.from_declared(dict(so.DECLARED_BY_ENGINE, tau="neg_log_one_minus_u1_over_a0"))
    with pytest.raises(so.ConventionMissing):
        so.SSAConvention.from_declared({k: v for k, v in so.DECLARED_BY_ENGINE.items() if k != "uniform"})


def test_uniform_construction_is_open_unit_interval():
    words = np.array([0, (1 << 52) - 1, 1234 << 52], dtype=np.uint64)
    words = np.append(words, np.bitwise_not(np.zeros(1, dtype=np.uint64)))  # the all-ones word
    u = so.uniforms_from_words(words)
    assert u[0] == 0.5 * 2.0 ** -52 and u[1] == 1.0 - 0.5 * 2.0 ** -52
    assert np.all((u > 0) & (u < 1))


def test_birth_death_pmf_matches_its_moments():
    p = so.birth_death_pmf(2.0, 20, 1.0, 0.5)
    n = np.arange(p.size)
    m, v = ex.size_moments_beta0(2.0, 20, 1.0, 0.5, 1.0)
    assert abs((p * n).sum() - m[0]) < 1e-9 * m[0]
    assert abs((p * n * n).sum() - (p * n).sum() ** 2 - v[0]) < 1e-7 * v[0]


def _sizes(ensemble):
    times = np.asarray(D["times"])
    return times, np.stack([counts_at_times(D["founder"], a["event_time"], a["event_channel"], times).sum(axis=1)
                            for _, _, a in ensemble])


def test_birth_death_ensemble_and_a_biased_choice():
    lam = D["k_join"] * float(np.sum(D["rho"]))
    N0 = int(np.sum(D["founder"]))
    times, sizes = _sizes(ensemble_arrays(D["runs"], seed=303))
    res = so.check_birth_death_ensemble(times, sizes, N0, lam, D["k_leave"])
    assert res.passed, res.detail
    times, sizes = _sizes(ensemble_arrays(D["runs"], seed=404, leave_weight=so.PLANTED_LEAVE_WEIGHT))
    res_bad = so.check_birth_death_ensemble(times, sizes, N0, lam, D["k_leave"])
    assert not res_bad.passed


@pytest.mark.parametrize("P,rule", [([3, 2, 1], "binomial"), ([4, 1, 2], "binomial"),
                                    ([3, 2, 2, 1], "exact_fraction"), ([5, 3, 1], "exact_fraction")])
def test_partition_pmfs_match_enumeration(P, rule):
    assert fp.check_enumeration(P, rule).passed


def test_registered_design_has_power():
    parents = np.tile(fp.REGISTERED_PARENT, (fp.REGISTERED_FISSIONS, 1))
    for rule in ("exact_fraction", "binomial"):
        assert fp.planted_power(parents, rule)["combined"] >= fp.MIN_POWER


def _splits(rule, fraction_or_p, n, seed):
    P = fp.REGISTERED_PARENT
    out = []
    for f in range(n):
        u = stream_uniforms(seed, DOMAIN_PARTITION, 0, f, int(P.sum()))
        out.append(_split(P, rule, fraction_or_p, fraction_or_p, u))
    return np.tile(P, (n, 1)), np.asarray(out)


@pytest.mark.parametrize("rule", ["exact_fraction", "binomial"])
def test_chi_square_passes_the_declared_rule_and_catches_a_split_at_055(rule):
    parents, splits = _splits(rule, 0.5, fp.REGISTERED_FISSIONS, 77)
    res = fp.check_partition_records(parents, splits, rule)
    assert res.passed, res.detail
    parents, bad = _splits(rule, fp.PLANTED_FRACTION, fp.REGISTERED_FISSIONS, 78)
    res_bad = fp.check_partition_records(parents, bad, rule)
    assert not res_bad.passed


def test_binomial_splits_presented_as_exact_are_caught():
    parents, splits = _splits("binomial", 0.5, 50, 79)
    assert not fp.check_partition_records(parents, splits, "exact_fraction").passed


def test_too_few_splits_fail_as_underpowered():
    parents, splits = _splits("binomial", 0.5, 30, 80)
    res = fp.check_partition_records(parents, splits, "binomial")
    assert res.detail["underpowered"] and not res.passed


@pytest.mark.parametrize("rule", ["stop", "fission"])
def test_the_event_guard_rule_is_followed(rule):
    law, founder = preprint_law(10, PAIR_CONSISTENT, n_types=40)
    _, run, a = simulate_lineage(law, founder, n_fissions=3, seed=35, event_guard=25, guard_rule=rule)
    table = so.ChannelTable.from_declared(run["channels"], law.n_types)
    args = (law, founder, a["event_uniforms"], a["event_channel"], a["event_time"], 80, a["fission_split"],
            a["fission_followed"], a["events_per_growth"], table, 25)
    if rule == "stop":
        assert run["end_status"] == "event_guard" and a["fission_split"].shape[0] == 0
    else:
        assert a["fission_split"].shape[0] == 3
    assert so.check_crn_replay(*args, guard_rule=rule).passed
    other = "fission" if rule == "stop" else "stop"
    assert not so.check_crn_replay(*args, guard_rule=other).passed or rule == "stop"
