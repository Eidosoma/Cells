"""Scale smoke test: one Xenopus-egg-sized cell at rest (cell-division plan stage 2; development).

Engine model: resolved_pump_tissue@3, unmodified, with no pump, no channel populations and
no junctions: one cell facing a held bath, IMEX ARS(2,2,2) at the qualified 1 ms step.
Every run goes through core/runner.run (host row checks on every accepted row); the model's
device row checks (surface_pump_v3.device_checks) then run on every accepted row, and each
ledger's residual is divided by its checked bound (surface_pump.ledger_limits with
surface_pump_v3.channel_magnitudes, the bounds both checks use). The optional water arm is
resolved_pump_water@1 on the same cell (its own host checks through run()).

The egg (rows of /mnt/workspaces/Cells/cell-division-20261111-01/verification/
xenopus_parameters.csv, each with its source there):
* water volume 0.782 uL per egg (de Laat, Buwalda & Habets 1974, Table 2, onset of first
  cleavage): concentrations are per litre cell water;
* cytosol: the measured activities Na 19.4, K 51.4, Cl 53.1 mM (de Laat 1974, Table 4) used
  as the ideal-solution concentrations, so the constant-field law sees activities; bound Na
  (about 60%) and K (about 30%) are not represented;
* medium: Steinberg's NaCl 58.2 and KCl 0.67 mM on the same activity basis, coefficient
  a_K / c_K = 0.545 / 0.67 (de Laat 1974 p11); Ca(NO3)2, MgSO4 and Tris are omitted, so the
  bath is NaCl + KCl only (declared simplification);
* old membrane approximately nonselective: P_Na = P_K, P_Cl = 0 (de Laat 1974: P_Na/P_K
  about 1; Cl replacement has no effect), P chosen so the input resistance at the
  zero-current potential is 852 kOhm (de Laat & Bluemink 1974, Table I, onset of first
  cleavage, normal eggs), on the folded area 8.69 mm2 (1.7 x the geometric 5.11 mm2,
  Bluemink & de Laat 1973);
* capacitance 0.62 uF/cm2 (DiCaprio, French & Sanders 1974, Table I, smooth-area basis) on
  the geometric 5.11 mm2;
* no electrogenic pump (de Laat 1974 p13: ouabain and ethacrynic acid to 1e-3 M without
  effect; Kline et al. 1983: pump current < 0.01 uA/cm2);
* 295.15 K (de Laat & Bluemink 1974: 20-24 C).

The cell is at its zero-current potential: Na enters and K leaves at equal charge rates,
so composition drifts slowly (no pump) while Vm stays near rest.

Parts (each writes <part>.json in --output; refusals are kept as results):
  anchor  the definition built as the heredity fixtures build theirs (charge anchor C Vm,
          fixed background anchor/F - sum z n): parsed, accepted or refused at the definition
  run     the definition with the anchor taken from the rounded background (F (background
          + sum z n), exact sum) for --end s: run(), device checks, per-ledger ratios
  water   the same consistent cell as resolved_pump_water@1 (water on: Pf from the egg's
          water permeability, no cortex modulus or pressure offset) for --end s

Usage: python -m validation.tissue.egg_scale_smoke PART[,PART...] --output DIR [--end S]
"""

import argparse
import copy
import json
import math
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.processes.electrochemistry import CHARGE_PER_FMOL  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# Exact SI products (N_A e, N_A k_B) for the reference arithmetic. The definition's charge
# anchor uses the engine's CHARGE_PER_FMOL, as the heredity fixtures do: CODATA's rounded
# 96485.33212 differs from N_A e by 3.4e-11 relative, which alone moves the egg's anchor by
# about 1e-20 C, the definition check's absolute bound.
F = 6.02214076e23 * 1.602176634e-19  # C/mol
R = 6.02214076e23 * 1.380649e-23  # J/(mol K)

TEMPERATURE_K = 295.15
WATER_VOLUME_PL = 0.782e6  # 0.782 uL
FOLDED_AREA_M2 = 8.69e-6  # 8.69 mm2
GEOMETRIC_AREA_M2 = 5.11e-6  # 5.11 mm2
SPECIFIC_CAPACITANCE_F_M2 = 0.62e-2  # 0.62 uF/cm2
CAPACITANCE_F = SPECIFIC_CAPACITANCE_F_M2 * GEOMETRIC_AREA_M2
INPUT_RESISTANCE_OHM = 852e3
SPECIES = (("Na", 1), ("K", 1), ("Cl", -1))
CYTOSOL_mM = dict(Na=19.4, K=51.4, Cl=53.1)
ACTIVITY_COEFFICIENT = 0.545 / 0.67
BATH_mM = {s: ACTIVITY_COEFFICIENT * c for s, c in dict(Na=58.2, K=0.67, Cl=58.2 + 0.67).items()}
RELATIVE_PERMEABILITY = dict(Na=1.0, K=1.0, Cl=0.0)
WATER_PF_M_S = 1.87e-7  # 1.87e-5 cm/s (de Laat 1974 p7, 3H2O exchange at 15 C)
HEREDITY_VOLUME_PL = 0.7505222518670602  # validation/tissue/surface_pump_v3_fixtures.py
HEREDITY_CAPACITANCE_F = 0.05 * 3.261272165616906e-10


def provenance():
    git = ["git", "-C", str(ROOT)]

    def out(*args):
        return subprocess.run([*git, *args], capture_output=True, text=True).stdout

    return dict(
        argv=sys.argv,
        host=platform.node(),
        revision=out("rev-parse", "HEAD").strip(),
        dirty=out("status", "--porcelain", "--untracked-files=no"),
        diff=out("diff", "HEAD"),
        jax=jax.__version__,
    )


# ---------------------------------------------------------------- reference arithmetic


def ghk_flux_mol_s(voltage, permeability_m_s):
    """Outward constant-field flux (mol/s) of each species at a membrane voltage (V).

    Written here from the Goldman-Hodgkin-Katz flux equation, independently of the engine's
    selective_flux, to place the cell at its zero-current potential and set P from Rin.
    """
    u = F * voltage / (R * TEMPERATURE_K)
    flux = {}
    for s, z in SPECIES:
        ci, co, x = CYTOSOL_mM[s], BATH_mM[s], z * u
        factor = x / -math.expm1(-x) if abs(x) > 1e-12 else 1.0 + x / 2
        flux[s] = permeability_m_s[s] * FOLDED_AREA_M2 * factor * (ci - co * math.exp(-x))
    return flux


def current_A(voltage, permeability_m_s):
    flux = ghk_flux_mol_s(voltage, permeability_m_s)
    return F * math.fsum(z * flux[s] for s, z in SPECIES)


def rest_and_permeability():
    """(zero-current Vm in V, P in m/s) with P_Na = P_K = P giving Rin = 852 kOhm at rest."""
    from scipy.optimize import brentq

    unit = {s: 1e-9 * r for s, r in RELATIVE_PERMEABILITY.items()}
    vm = brentq(lambda v: current_A(v, unit), -0.1, 0.05, xtol=1e-16, rtol=4 * np.finfo(float).eps)
    h = 1e-6
    slope = (current_A(vm + h, unit) - current_A(vm - h, unit)) / (2 * h)
    scale = 1.0 / (INPUT_RESISTANCE_OHM * slope)
    return vm, {s: 1e-9 * r * scale for s, r in RELATIVE_PERMEABILITY.items()}


# ---------------------------------------------------------------- definitions


def egg_definition(*, end_time=60.0, dt=1e-3, anchor="consistent", observe_every=1.0):
    """The egg on resolved_pump_tissue@3 (raw definition).

    anchor "fixture": charge anchor C Vm and background anchor/F - sum z n, as the heredity
    fixtures build theirs; "consistent": the same background, with the anchor recomputed as
    F (background + sum z n) by an exact sum, so the declared inventory and anchor agree.
    """
    ids = [s for s, _ in SPECIES]
    z = dict(SPECIES)
    vm, permeability = rest_and_permeability()
    inside = {s: CYTOSOL_mM[s] * WATER_VOLUME_PL for s in ids}
    charge = CAPACITANCE_F * vm
    background = charge / CHARGE_PER_FMOL - math.fsum(z[s] * inside[s] for s in ids)
    if anchor == "fixture":
        anchor_C = charge
    elif anchor == "consistent":
        anchor_C = CHARGE_PER_FMOL * math.fsum((background, *(z[s] * inside[s] for s in ids)))
    else:
        raise ValueError(anchor)
    count = int(end_time / observe_every + 1e-9)
    steps = sorted(
        {*(round(k * observe_every / dt) for k in range(count + 1)), round(end_time / dt)}
    )
    times = [k * dt for k in steps]
    always = [dict(time=0.0, availability=1.0)]
    raw = dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=TEMPERATURE_K,
            species=[dict(id=s, valence=v) for s, v in SPECIES],
            cells=[
                dict(
                    id="egg",
                    volume_pL=WATER_VOLUME_PL,
                    initial_amount_fmol=inside,
                    fixed_charge_equivalent_fmol=background,
                    initial_charge_C=anchor_C,
                )
            ],
            extracellular=[
                dict(
                    id="steinberg",
                    volume_pL=1.0,
                    initial_amount_fmol=dict(BATH_mM),
                    fixed_charge_equivalent_fmol=-math.fsum(z[s] * BATH_mM[s] for s in ids),
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                )
            ],
            membranes=[
                dict(
                    id="old_membrane",
                    inside="egg",
                    outside="steinberg",
                    area_m2=FOLDED_AREA_M2,
                    capacitance_F=CAPACITANCE_F,
                    permeability_m_per_s=permeability,
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                )
            ],
            junctions=[],
            faces=[],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end_time,
            observation_times=times,
            membrane_controls=[dict(membrane_id="old_membrane", schedule=copy.deepcopy(always))],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=1,
            membrane_capacity=1,
            edge_capacity=0,
            face_capacity=0,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver="imex_ars222_face_electromigration@1",
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=int(math.ceil(end_time / dt)) + 8,
            max_trace_bytes=2**31,
            material_balance_atol_fmol={s: 1e-10 for s in ids},
        ),
    )
    inputs = dict(
        rest_V=vm,
        permeability_m_per_s=permeability,
        capacitance_F=CAPACITANCE_F,
        charge_C_vm=charge,
        anchor_C=anchor_C,
        background_fmol=background,
        inventory_charge_C=CHARGE_PER_FMOL
        * math.fsum((background, *(z[s] * inside[s] for s in ids))),
        bath_mM=dict(BATH_mM),
        scale=dict(
            volume_over_heredity=WATER_VOLUME_PL / HEREDITY_VOLUME_PL,
            capacitance_over_heredity=CAPACITANCE_F / HEREDITY_CAPACITANCE_F,
            largest_amount_fmol=max(inside.values()),
            time_constant_s=INPUT_RESISTANCE_OHM * CAPACITANCE_F,
        ),
    )
    return raw, inputs


# ---------------------------------------------------------------- checks


def model_checks(model_id):
    """(module, ledger names, limits, magnitudes): the bounds the model's row checks use."""
    from cells.models import surface_pump as first
    from cells.models import surface_pump_v3 as v3
    from cells.models import surface_pump_water as water

    if model_id == "resolved_pump_tissue@3":
        return v3, first.LEDGERS, first.ledger_limits, v3.channel_magnitudes
    if model_id == "resolved_pump_water@1":
        return water, water.LEDGERS, water.ledger_limits, water.magnitudes
    raise ValueError(model_id)


def device_rows(model_id, spec, result, chunk=4096):
    """Device row checks and per-ledger |residual| / bound on every accepted row."""
    model, ledgers, limits, magnitudes = model_checks(model_id)
    p = model.initial_values(spec)[1]
    constants = model.device_check_constants(spec)

    def one(previous, row, steps):
        failed, values = model.device_checks(previous, row, p, constants, steps)
        b = model.device_balances(row, p)
        _, bounds = limits(
            row,
            p,
            constants.material_atol,
            constants.energy_rtol,
            steps=steps,
            magnitudes=magnitudes(row, p, xp=jnp),
            xp=jnp,
        )
        ratios = jnp.stack(
            [
                jnp.max(jnp.abs(v) / jnp.broadcast_to(bound, jnp.shape(v)), initial=0.0)
                for v, bound in zip(b.values(), bounds, strict=True)
            ]
        )
        return failed, values, ratios

    check = jax.jit(jax.vmap(one, in_axes=(0, 0, 0)))
    h, n = result.history, len(result.times)
    failing, names = [], set()
    worst = np.zeros(len(ledgers))
    worst_row = np.zeros(len(ledgers), dtype=int)
    largest = np.zeros(len(model.DEVICE_DIAGNOSTICS))
    for start in range(1, n, chunk):
        stop = min(n, start + chunk)
        prev = jax.tree.map(lambda v, a=start, b=stop: jnp.asarray(np.asarray(v)[a - 1 : b - 1]), h)
        rows = jax.tree.map(lambda v, a=start, b=stop: jnp.asarray(np.asarray(v)[a:b]), h)
        steps = jnp.arange(start, stop) + result.start_step
        failed, values, ratios = (np.asarray(x) for x in check(prev, rows, steps))
        for k in np.flatnonzero(failed.any(axis=1)):
            failing.append(int(start + k))
            names |= {c for c, f in zip(model.DEVICE_CHECKS, failed[k], strict=True) if f}
        largest = np.maximum(largest, values.max(axis=0))
        k = ratios.argmax(axis=0)
        better = ratios[k, np.arange(ratios.shape[1])] > worst
        worst = np.where(better, ratios[k, np.arange(ratios.shape[1])], worst)
        worst_row = np.where(better, start + k, worst_row)
    times = np.asarray(result.times)
    return dict(
        device_failing_rows=failing[:20],
        device_failing_row_count=len(failing),
        device_failed_checks=sorted(names),
        device_diagnostics=dict(zip(model.DEVICE_DIAGNOSTICS, largest.tolist(), strict=True)),
        ledger_ratio_to_bound={
            name: dict(max_ratio=float(r), row=int(i), time_s=float(times[i]))
            for name, r, i in zip(ledgers, worst, worst_row, strict=True)
        },
    )


def observed(result):
    obs = result.observations
    vm = np.asarray(obs.membrane_voltage_V)[:, 0]
    amount = np.asarray(obs.amount)[:, :, 0]
    return dict(
        times_s=np.asarray(obs.times).tolist(),
        membrane_voltage_V=vm.tolist(),
        vm_change_V=float(vm[-1] - vm[0]),
        amount_change_fmol=(amount[-1] - amount[0]).tolist(),
        field_charge_residual_C_max=float(np.max(np.abs(np.asarray(obs.charge_residual_C)))),
        electrode_current_A=np.asarray(obs.electrode_current_A)[[0, -1]].tolist(),
    )


# ---------------------------------------------------------------- parts


def part_anchor(args):
    from cells.core.specs import parse_spec

    raw, inputs = egg_definition(end_time=args.end, anchor="fixture")
    out = dict(
        part="anchor",
        inputs=inputs,
        anchor_minus_inventory_C=inputs["anchor_C"] - inputs["inventory_charge_C"],
        definition_bound_C=1e-20,  # surface_tissue.check_definition
        # One float64 step of the declared background, as charge: the finest anchor the
        # declared inventory can represent at this magnitude.
        background_resolution_C=float(np.spacing(inputs["background_fmol"])) * CHARGE_PER_FMOL,
    )
    try:
        parse_spec(raw)
        out["verdict"] = "accepted"
    except Exception as error:  # Kept: the refusal is the result.
        out["verdict"] = "refused"
        out["refusal"] = repr(error)
    return out


def _run(raw, inputs, part):
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    out = dict(part=part, inputs=inputs, model=raw["model"]["id"])
    started = time.perf_counter()
    try:
        spec = parse_spec(raw)
        result = run(spec)
    except Exception as error:  # Kept: a refusal is the result.
        out.update(verdict="refused", refusal=repr(error), tb=traceback.format_exc())
        out["wall_s"] = time.perf_counter() - started
        return out
    out["host_checks"] = "passed (core/runner.run, every accepted row)"
    out["accepted_rows"] = len(result.times)
    out["host_diagnostics"] = {k: float(v) for k, v in result.diagnostics.items() if np.isscalar(v)}
    out["timings"] = dict(result.timings)
    out["observed"] = observed(result)
    out["device"] = device_rows(raw["model"]["id"], spec, result)
    accepted = not out["device"]["device_failing_rows"]
    out["verdict"] = "accepted" if accepted else "device check failed"
    out["wall_s"] = time.perf_counter() - started
    return out


def part_run(args):
    raw, inputs = egg_definition(end_time=args.end, anchor="consistent")
    return _run(raw, inputs, "run")


def part_water(args):
    from validation.tissue import pump_water_fixtures as water

    raw, inputs = egg_definition(end_time=args.end, anchor="consistent")
    raw = water.with_water(raw, pf_m_s=WATER_PF_M_S, bulk_modulus_Pa=0.0, pressure_offset_Pa=0.0)
    inputs = dict(inputs, water_pf_m_s=WATER_PF_M_S, bulk_modulus_Pa=0.0, pressure_offset_Pa=0.0)
    return _run(raw, inputs, "water")


PARTS = dict(anchor=part_anchor, run=part_run, water=part_water)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts")
    parser.add_argument("--output", required=True)
    parser.add_argument("--end", type=float, default=60.0)
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name in args.parts.split(","):
        started = time.perf_counter()
        try:
            result = PARTS[name](args)
        except Exception as error:  # Kept as the part's result.
            result = dict(part=name, verdict="error", error=repr(error), tb=traceback.format_exc())
        result["provenance"] = provenance()
        result["part_wall_s"] = time.perf_counter() - started
        (output / f"{name}.json").write_text(json.dumps(result, indent=1, default=float) + "\n")
        print(name, result.get("verdict"), f"{result['part_wall_s']:.1f} s", flush=True)


if __name__ == "__main__":
    main()
