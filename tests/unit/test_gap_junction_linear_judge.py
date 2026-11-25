"""GJ-L1's reader and judge at their tag (D308): validation/gap_junction_tissue/linear_judge.py.

Every input here is synthetic: an engine run built from exact steady states with second-order step
errors added, and a reference interface built from the registrant's own closed forms
(validation/gap_junction_tissue/paper.py). Neither is the code-blind references' output, which do
not exist at the tag; the test shows that the reader reads the registered interface, refuses a
mismatch, and that every planted failure is caught.
- The committed linear_rule.json is what `rule` writes.
- A synthetic run that matches its references passes, and both engine plants (P-N1, P-W1) fail.
- The reader's plants: P-R1 (a reference off by 1e-9 fails its arm), P-R2 (the printed recursion
  as Figure 8's reference fails at n >= 3 and passes at n = 1 and 2), P-R3 and P-R4 (a changed or
  missing declaration is refused).
- The judge's plants: P-O1 (a step-independent bias fails), P-O2 (first order is inconclusive),
  and the retry replaces an inconclusive arm.

No world is compiled or run: about 2 s, most of it the import of the driver's worlds module.
"""

import copy
import json
import math

import numpy as np
import pytest

from validation import id_table
from validation.gap_junction_tissue import linear_judge as lj
from validation.gap_junction_tissue import paper, worlds

ERROR_AT_DT = 1e-5  # The synthetic as-written error at the step rule's dt (relative).


def exact(network, junction_scale=1.0):
    """The steady state and probe fluxes of a network by the registrant's dense solve."""
    conductance = [size * worlds.G_EQ1_M3_S for _, _, size in network.cells]
    unloaded = [u for _, u, _ in network.cells]
    edges = [(i, j, junction_scale * g * worlds.G_EQ1_M3_S) for _, i, j, g in network.edges]
    probes = [(i, g * worlds.G_EQ1_M3_S, held) for _, i, held, g in network.probes]
    c, flux = paper.linear_steady_state(conductance, unloaded, edges, probes)
    return np.asarray(c), flux


def engine_result(arm, network, *, error=0.0, junction_scale=1.0, bias=0.0, order=2):
    """One synthetic engine arm in run.py's results.json form: the exact steady state times
    (1 + bias + error (fraction)^order) at each step, its ledgers consistent with it."""
    c_exact, _ = exact(network, junction_scale)

    def run(fraction):
        c = c_exact * (1.0 + bias + error * fraction**order)
        out = dict(status="done", dt_s=arm["dt_s"] * fraction, concentration_mM=c.tolist(),
                   steady_rel_change=0.0)  # fmt: skip
        if network.probes:
            _, i, held, g = network.probes[-1]
            flux = g * worlds.G_EQ1_M3_S * (c[i] - held)
            out.update(port_mM=float(c[i]), exit_flux_mol_s=flux, exit_flux_formula_mol_s=flux,
                       ledger_rel_error=1e-14)  # fmt: skip
        return out

    result = dict(run(1.0), arm_id=arm["arm"])
    if arm["form"] == lj.AS_WRITTEN:
        result["dt_study"] = [dict(run(f), fraction=f) for f in (0.5, 0.25)]
    return result


def synthetic_results(rule, *, overrides=None):
    """A results.json in run.py's form for every registered arm (overrides: {arm: kwargs})."""
    nets, overrides = lj.networks(), overrides or {}
    arms = {}
    for arm in rule["arms"]:
        kwargs = dict(error=ERROR_AT_DT if arm["form"] == lj.AS_WRITTEN else 1e-15)
        if arm["planted"]:
            kwargs["junction_scale"] = lj.PLANTED_SCALE
        kwargs.update(overrides.get(arm["arm"], {}))
        arms[arm["arm"]] = engine_result(arm, nets[arm["network"]], **kwargs)

    def chains(prefix):
        return [
            dict(n=n, loads=[arms[f"{prefix}figure8-chain{n}-held{h:g}"] for h in lj.FIGURE8_LOADS])
            for n in lj.FIGURE8_N
        ]

    def figures(prefix):
        return dict(
            figure3=[v for k, v in arms.items() if k.startswith(f"{prefix}figure3-")],
            figure5_lumped=[v for k, v in arms.items() if k.startswith(f"{prefix}figure5-lumped")],
            figure5_network=[v for k, v in arms.items() if k.startswith(f"{prefix}figure5-net")],
        )

    norton = figures("")
    parts = dict(
        figure3=dict(status="done", result=dict(figure3=norton["figure3"])),
        figure5=dict(status="done", result=dict(figure5_lumped=norton["figure5_lumped"],
                                                figure5_network=norton["figure5_network"])),
        figure8=dict(status="done", result=dict(chains=chains(""))),
        control=dict(status="done", result=arms["control-planted"]),
        aswritten=dict(status="done", result=dict(**figures("aw-"), chains=chains("aw-"),
                                                  control_planted=arms["aw-control-planted"])),
    )  # fmt: skip
    return dict(record=dict(synthetic=True), parts=parts)


def synthetic_interface(rule):
    """A reference interface in the registered schema, from the registrant's closed forms."""
    nets = lj.networks()
    networks = {}
    for net_id, declared in rule["networks"].items():
        c, _ = exact(nets[net_id])
        cells = [cell["id"] for cell in declared["cells"]]
        networks[net_id] = dict(
            declaration=copy.deepcopy(declared),
            concentrations=dict(zip(cells, c.tolist(), strict=True)),
            accuracy_rel=1e-15,
            method="synthetic: paper.linear_steady_state (the registrant's, not the references')",
        )
    physical = paper.chain_physical(1.0, 1.0, 10)
    return dict(
        format=lj.REFERENCE_FORMAT,
        registration="synthetic",
        networks=networks,
        chains={
            str(n): dict(
                g_eq_ratio=physical[n - 1], intercept=1.0, accuracy_rel=1e-15, method="synthetic"
            )
            for n in lj.FIGURE8_N
        },  # fmt: skip
        limits=dict(figure3=7.5, figure5b=50.0 / 7.0, chain=paper.chain_limit(1.0, 1.0)),
        printed_recursion=dict(
            literal=paper.chain_literal(1.0, 1.0, 10),
            resistance_form=paper.chain_paper(1.0, 1.0, 10),
        ),
    )


def write(tmp_path, interface):
    directory = tmp_path / "interface"
    directory.mkdir(exist_ok=True)
    (directory / lj.INTERFACE_FILE).write_text(json.dumps(interface))
    return directory


@pytest.fixture(scope="module")
def rule():
    return lj.rule()


@pytest.fixture(scope="module")
def table(rule):
    return lj.table(synthetic_results(rule), rule)


def test_the_references_spec_is_what_spec_writes_and_holds_no_seen_value():
    text = lj.SPEC_FILE.read_text()
    assert json.loads(text) == json.loads(json.dumps(lj.spec()))
    for seen in ("7.17", "7.18", "1.88", "1.89", "2.7e-14", "5.8e-13"):  # Thresholds, dev errors.
        assert seen not in text


def test_the_committed_rule_is_what_rule_writes(rule):
    # rule() takes its solvers from the live worlds module, and its other IDs as it was frozen.
    written = id_table.translate(json.loads(json.dumps(rule)))
    assert id_table.load(lj.RULE_FILE) == written


def test_a_matching_run_passes_and_both_engine_plants_are_caught(tmp_path, rule, table):
    interface = lj.read_interface(write(tmp_path, synthetic_interface(rule)), rule)
    verdict = lj.judge(table, interface)
    assert verdict["verdict"] == "passed"
    assert verdict["plants_caught"] == ["aw-control-planted", "control-planted"]
    planted = verdict["arms"]["control-planted"]
    assert planted["margin"] > 1e8  # 8.3e-4 against a floor below 1e-12.
    orders = [v["order"] for k, v in table["arms"].items() if k.startswith("aw-")]
    assert all(abs(q - 2.0) < 1e-6 for q in orders)
    reported = verdict["reported"]["printed_values"]
    assert [r["agrees"] for r in reported] == [True, True, True, False]  # 7.15 against 50/7.


def test_reader_plants(tmp_path, rule, table):
    good = synthetic_interface(rule)
    off = copy.deepcopy(good)  # P-R1
    off["networks"]["figure3-g1"]["concentrations"]["A"] *= 1.0 + 1e-9
    verdict = lj.judge(table, lj.read_interface(write(tmp_path, off), rule))
    assert verdict["verdict"] == "failed"
    assert verdict["arms"]["figure3-g1"]["status"] == "failed"
    assert verdict["arms"]["aw-figure3-g1"]["status"] == "passed"  # 1e-9 is inside its 3 est.
    printed = copy.deepcopy(good)  # P-R2
    resistance = paper.chain_paper(1.0, 1.0, 10)
    for n in lj.FIGURE8_N:
        printed["chains"][str(n)]["g_eq_ratio"] = resistance[n - 1]
    verdict = lj.judge(table, lj.read_interface(write(tmp_path, printed), rule))
    status = {n: verdict["arms"][f"figure8-chain{n}"]["status"] for n in lj.FIGURE8_N}
    assert status == {1: "passed", 2: "passed", 3: "failed", 4: "failed", 5: "failed",
                      10: "failed"}  # fmt: skip
    swapped = copy.deepcopy(good)  # P-R3
    cells = swapped["networks"]["figure3-g2"]["declaration"]["cells"]
    cells[0]["unloaded"], cells[1]["unloaded"] = cells[1]["unloaded"], cells[0]["unloaded"]
    with pytest.raises(lj.ComparisonError, match="figure3-g2"):
        lj.read_interface(write(tmp_path, swapped), rule)
    missing = copy.deepcopy(good)  # P-R4
    del missing["networks"]["figure5-network-g10"]
    with pytest.raises(lj.ComparisonError, match="lacks registered networks"):
        lj.read_interface(write(tmp_path, missing), rule)


def test_order_plants_and_the_retry(tmp_path, rule, table):
    interface = lj.read_interface(write(tmp_path, synthetic_interface(rule)), rule)
    biased = lj.table(synthetic_results(rule, overrides={"aw-figure3-g2": dict(bias=1e-5)}), rule)
    verdict = lj.judge(biased, interface)  # P-O1
    assert biased["arms"]["aw-figure3-g2"]["order"] == pytest.approx(2.0, abs=1e-6)
    assert verdict["arms"]["aw-figure3-g2"]["status"] == "failed"
    assert verdict["verdict"] == "failed"
    first = lj.table(synthetic_results(rule, overrides={"aw-figure3-g5": dict(order=1)}), rule)
    verdict = lj.judge(first, interface)  # P-O2
    assert first["arms"]["aw-figure3-g5"]["order"] == pytest.approx(1.0, abs=1e-6)
    assert verdict["arms"]["aw-figure3-g5"]["status"] == "inconclusive"
    assert verdict["verdict"] == "inconclusive"
    verdict = lj.judge(first, interface, retry=table)  # The finer triple replaces it.
    assert verdict["arms"]["aw-figure3-g5"]["status"] == "passed"
    assert verdict["verdict"] == "passed"


def test_a_plant_that_did_not_run_is_not_caught(tmp_path, rule, table):
    interface = lj.read_interface(write(tmp_path, synthetic_interface(rule)), rule)
    for arm in ("control-planted", "aw-control-planted"):
        rows = dict(table["arms"])
        rows[arm] = dict(rows[arm], status="refused", refusals=["the planted run was refused"])
        verdict = lj.judge(dict(table, arms=rows), interface)
        assert verdict["verdict"] == "instrument not validated"
        assert verdict["plants_uncaught"] == [arm]


def test_the_derived_floors_cover_their_terms(rule):
    nets = lj.networks()
    for arm in rule["arms"]:
        net, dt = nets[arm["network"]], arm["dt_s"]
        assert lj.transient(net) < 1e-12 and math.isfinite(lj.rounding(net, dt))
        assert lj.floor(net, dt) == pytest.approx(
            lj.F_N * (lj.transient(net) + lj.rounding(net, dt))
        )
