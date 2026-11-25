"""FR-38's second registered comparison: the builder's tools in the tiers (protocol §5, D334).

- **The registered worlds parse** (validation/gene_regulation/fr38_v2/worlds.check): AF, AN, B, C
  and D at the three rungs, with their support runs and the plants' world data, each parsed with
  its initial values built. Nothing is compiled or run (about 7 s), as the protocol asks of the
  builder before the registration's tag.
- **release_check's net agreement is scoped to e^(y_f) << 1** (release_check.net_scope), on
  synthetic counters (no world compiled). Re-synthesis makes the net reading depart from route 2's
  gross one:
  - out of scope at AN's synthetic potentials (e^(y_f) about 0.13), so the check stands on route 2;
  - in scope at AF's (about 1e-8), where it passes on consistent counters and fails on counters
    whose booked loss is not the declared k.
- **The table builds from records alone** (campaign.table_check): every planned job's record made
  up on its own registered definition (no engine run), then each family's table built and hashed,
  with every run at every rung, route 2, survival, the excess, the plants and the restart (about
  5 s).
- **The C and D exports** (engine_run.readouts): one made-up world (no registered input) with the
  store and water together runs 30 s of model time. It exports n_Mx, H_store, V, H_water and
  W_bath, and they enter G's identity with their signs: what is left is far below them, water's
  second-order residual (FR-43's C2.7; fr38_v2/smoke.py shows C's identity at rounding and D's
  residual at second order). Reason: the exports are new code. Cost: about 40 s, one compile.
"""

import math

import numpy as np
import pytest

from cells.operators.templated_polymerisation import COPY_FMOL
from validation.gene_regulation import release_check
from validation.gene_regulation.fr38_v2 import campaign, worlds


def test_every_registered_world_and_plant_parses():
    verdicts = worlds.check()
    assert len(verdicts) == 3 * sum(len(worlds.runs(f)) for f in worlds.LABELLED) + len(
        worlds.PLANTS
    )
    assert set(verdicts.values()) == {"parses"}


ROWS = {"R": ("durable", "k_d"), "R_s": ("short_lived", "k_s")}


def _net_record(family, row, departure, every=60.0):
    """Synthetic counters of a fate row in a hold world: a constant release into it from t = 0 and
    a booked net loss k (1 - departure) n, so the net reading departs from the gross one by
    re-synthesis at `departure` per molecule; n_M at the world's start."""
    f = worlds.HOLDS[family]
    fate, rate = ROWS[row]
    t = [float(x) for x in np.arange(0.0, f.samples[1] + every / 2, every)]
    start = (f.r0_copies if row == "R" else f.rs0_copies) * COPY_FMOL
    q, kn = 1e-12, getattr(f, rate) * (1.0 - departure)
    n = [q / kn + (start - q / kn) * math.exp(-kn * s) for s in t]
    readouts = {f"n_{row}": n, f"int_Q_tx_release_{fate}": [q * s for s in t],
                f"int_D_{row}": [start + q * s - x for s, x in zip(t, n, strict=True)],
                "n_M": [f.m0_mM] * len(t)}  # fmt: skip
    return dict(definition=worlds.hold(family, "p_sched returned", dt=2.0), cell="cell_0", t=t,
                readouts=readouts)  # fmt: skip


SCOPE = [
    # family, row, the counters' departure, the row passes, the net agreement (None: out of scope)
    ("AN", "R_s", 0.13, True, None),  # e^(y_f) about 0.13: out of scope by design
    ("AF", "R", 0.0, True, True),  # reach k_d (ts - t1) e^(y_f) = 7.5e-9: in scope, agrees
    ("AF", "R", 0.13, False, False),  # in scope: a booked loss that is not k_d fails
    ("AF", "R_s", 0.0, True, None),  # reach 5.0e-8 at 9000 s, over the 3e-8 allowance
]


@pytest.mark.parametrize(("family", "row", "departure", "ok", "agrees"), SCOPE)
def test_the_net_agreement_is_scoped_to_small_exp_y(family, row, departure, ok, agrees, tmp_path):
    import json

    f = worlds.HOLDS[family]
    fate, rate = ROWS[row]
    path = tmp_path / "record.json"
    path.write_text(json.dumps(_net_record(family, row, departure)))
    checks = release_check.Checks()
    release_check.survival(checks, family, path, row, fate, window=f.window, ts=f.samples[1],
                           k_expected=getattr(f, rate))  # fmt: skip
    (result,) = checks.rows
    assert (result["ok"], result["net_agrees"]) == (ok, agrees), result
    assert result["net_scope"]["in_scope"] == (agrees is not None)


TINY = worlds.Hold(
    "made up", mu_fate=-12000.0, m0_mM=0.01, n0_mM=1.5, pi0_mM=4.0, mu_N=24.0, r0_copies=12.0,
    rs0_copies=9.0, speed=12.5, k_N_mM=0.03, pool_copies=3000.0, k_I=5.0e4, tau_s=10.0,
    h0_copies=30.0, k_d=0.0025, k_s=0.02, p_sched=((0.0, 0.8), (15.0, 0.35)),
    window=(10.0, 20.0), horizon=30.0, every=10.0, samples=(20.0, 30.0),
    store=worlds.Store(forward_per_s=1 / 20), water=worlds.Water(lp_m_per_Pa_s=1.0e-12),
)  # fmt: skip


def test_the_store_and_water_exports_enter_g():
    record = campaign.one(worlds.hold("made up", "p_sched returned", dt=0.5, f=TINY))
    assert not record["refused"], record.get("refusal")
    x = record["readouts"]
    for name in ("n_Mx", "H_store", "V", "H_water", "W_bath", "n_K", "n_Y"):
        assert len(x[name]) == len(record["t"]), name
    assert x["n_Mx"][-1] > 10 * x["n_Mx"][0] and x["V"][-1] > x["V"][0]
    assert min(x["H_water"]) >= 0.0 and x["H_store"][-1] > 0.0
    c = record["checks"]
    beside = max(abs(a + b - w) for a, b, w in zip(x["H_store"], x["H_water"], x["W_bath"],
                                                    strict=True))  # fmt: skip
    assert c["G_identity_largest_pJ"] <= 1e-3 * beside, (c, beside)


def test_a_twin_is_its_labelled_run_without_the_label_owner():
    """C1's twins: the same definition with neither the owner nor its schedule (no compile)."""
    import copy

    for family, run in (
        ("AN", "p_sched returned"),
        ("B", "p=0.55 held"),
        ("D", "p_sched returned"),
    ):
        labelled = copy.deepcopy(worlds.world(family, run, dt=2.0))
        labelled["model"]["operators"] = [
            o for o in labelled["model"]["operators"] if o["law"] != worlds.LABELS
        ]
        del labelled["experiment"]["label_arrivals"]
        assert labelled == worlds.world(family, run + worlds.UNLABELLED, dt=2.0), family


def test_the_table_builds_from_records_alone(tmp_path):
    """Amendment 4's §8 contract, on fabricated records: every run at every rung, route 2,
    survival and the excess; the restart in a run entry's form with its checkpoint; the
    world-data plants only (the judge forms P1, P1′, P1″ and P6), P9's naming its V0 patch."""
    summary = campaign.table_check(tmp_path)
    expect = {"AF": ["P2", "P5", "P7"], "AN": ["P3a", "P3b", "P4 AN"], "B": ["P4 B"],
              "C": ["P8", "P8 blank"], "D": ["P9"]}  # fmt: skip
    for family, plants in expect.items():
        s = summary[family]
        assert s["rungs"] == ["0.5", "1.0", "2.0"] and not s["missing"], (family, s)
        assert (s["route2"], s["survival"], s["plants"]) == (6, 4, plants), (family, s)
        assert s["excess"] == (family != "B") and s["restart"] == (family == "AN"), (family, s)
        patches = {name: "V0" if name == "P9" else None for name in plants}
        assert s["host_patches"] == patches, (family, s)
    assert summary["AN"]["restart_form"] == ["blank", "checkpoint", "excess_over_blank", "route2",
                                             "survival"]  # fmt: skip
    assert summary["AN"]["twin_has_survival"] is False
