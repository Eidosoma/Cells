"""The layouts agree through the compiled runner (the kinds owner's design statement 1, condition
2; the lead's answer of 19 November: one compiled-path agreement world, in tier 3).

The charged world (tests/unit/test_transporter_kind.py's: the proton law on held fuel beside the
cell's proton buffer) runs through the runner, compiled, with every accepted row checked on the
host, in version 1's form and in the general form. Its cycles, amounts, supply, heat and work agree
within the bounds that tests/unit/test_cycle_kind.py derives for the host-stepped agreement
(statement 1, amendment 2), with their X and one-way scale read from the probe at both ends of the
run (planted: one side's capacity 1e-9 larger, refused by the cycles' bound and by the heat's).
FR-4's development world over 20 s is the same comparison at scale, kept as the kinds owner's
evidence: its amounts, voltages and cycles were identical.
"""

import copy

import numpy as np

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.laws.electrochemistry import R
from cells.registry.models import get_model
from tests.unit import test_cycle_kind as ck
from tests.unit import test_transporter_kind as tk

U = np.finfo(float).eps / 2


def compiled(raw, kinds):
    """(spec, the runner's result) for the world, compiled, every accepted row checked."""
    with ck.scoped(*kinds):
        spec = parse_spec(copy.deepcopy(raw))
        assert spec.execution.jit
        return spec, run(spec)


def test_the_layouts_agree_through_the_compiled_runner():
    raw, kinds = tk.charged_world(), tk.CHARGED_KINDS
    twin = copy.deepcopy(raw)
    twin["model"]["transporters"] = [ck.general(raw["model"]["transporters"][0])]
    _, a = compiled(raw, kinds)
    spec, b = compiled(twin, kinds)
    with ck.scoped(*kinds):
        impl = get_model(spec.model)
        first, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    for state in (first, b.final.state):  # The bounds' premises, read rather than assumed.
        modes = ck.probed(spec, state, p, control, kinds).modes
        assert float(np.max(modes.x_terms[:, 0])) <= ck.X_MAX
        assert float(np.max((modes.j_plus + modes.j_minus)[:, 0] / np.abs(modes.j[:, 0]))) <= ck.RHO_MAX
    steps = b.final.step_index
    assert steps == a.final.step_index > 0
    x, y = a.final.state, b.final.state
    cycles_a, cycles_b = float(x.transporter_cycles[0]), float(y.cycle_count[0, 0])
    # test_cycle_kind.py's bounds over the run's steps (their derivation is there).
    bound = steps * 2 * U * ((ck.ROWS + 10) * ck.X_MAX + 14) * ck.RHO_MAX * abs(cycles_a)
    assert cycles_a != 0 and abs(cycles_a - cycles_b) <= bound, (cycles_a, cycles_b, bound)
    n = float(np.max(np.abs(p.cycle_nu)))
    for name in ("amount_increment", "extracellular_amount_increment", "reservoir_supplied"):
        assert float(np.max(np.abs(getattr(x, name) - getattr(y, name)))) <= n * bound, name
    rt = 1e-3 * R * spec.model.temperature_K
    energy = (
        steps * 2 * U * ck.X_MAX
        * (((ck.ROWS + 10) * ck.X_MAX + 14) * ck.RHO_MAX + ck.ROWS + 3) * rt * abs(cycles_a)
    )  # fmt: skip
    for v1, axis in (
        ("transporter_dissipated_energy_pJ", "cycle_dissipated_energy_pJ"),
        ("transporter_metabolic_work_pJ", "cycle_metabolic_work_pJ"),
    ):
        h1, h2 = float(getattr(x, v1)[0]), float(getattr(y, axis)[0])
        assert h1 != 0 and abs(h1 - h2) <= energy, (v1, h1, h2, energy)
    for result in (a, b):
        assert result.diagnostics["max_energy_balance_relative"] < 1e-6
    # Planted: a capacity 1e-9 larger on one side, through the same compiled path.
    planted = copy.deepcopy(twin)
    planted["model"]["transporters"][0]["capacity_fmol_s"] *= 1 + 1e-9
    _, c = compiled(planted, kinds)
    z = c.final.state
    assert abs(cycles_a - float(z.cycle_count[0, 0])) > 100 * bound
    heat_a, heat_c = float(x.transporter_dissipated_energy_pJ[0]), float(z.cycle_dissipated_energy_pJ[0])
    assert abs(heat_a - heat_c) > energy
