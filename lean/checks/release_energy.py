"""Reconstruct the heat of terminal release from independent, 65-digit endpoint energies."""

import json
from decimal import Decimal, localcontext

import jax
import numpy as np
from terminal_release import collect, observed

from cells.operators import templated_polymerisation as polymer
from cells.registry.models import get_model
from validation.gene_regulation import kernel, sheet_check, worlds


def dec(value):
    return Decimal.from_float(float(value))


def potential_energy(n, cap):
    return sheet_check.RT * n * ((n / cap).ln() - 1)


def isolated(p):
    raw = observed(worlds.r1(p), 10)
    for control in raw["experiment"]["polymerisation_controls"]:
        if control["route_id"].startswith("deg_"):
            control["schedule"][0]["value"] = 0.0
    spec, _, times, values, _ = collect(raw)
    cap = dec(spec.model.cells[0].volume_pL) * sheet_check.C_STD_MM
    errors, relative = [], []
    assert not any(values["int_Q_tx"])
    for row, fate, fraction in zip(("R", "R_s"), polymer.FATES, (p, 1 - p), strict=True):
        ns = values[f"n_{row}"]
        releases = values[f"int_Q_{worlds.RELEASE}_{fate}"]
        heats = values[f"H_rel_{worlds.RELEASE}_{fate}"]
        assert not any(values[f"int_D_{row}"])
        if fraction == 0:
            assert not any(releases) and not any(heats)
        else:
            assert releases[-1] > 0 and heats[-1] > 0
        for n, heat in zip(ns, heats, strict=True):
            expected = potential_energy(dec(ns[0]), cap) - potential_energy(dec(n), cap)
            error = abs(dec(heat) - expected)
            assert error <= Decimal("2e-12") * abs(expected)
            errors.append(error)
            if expected:
                relative.append(error / abs(expected))
    return dict(
        fraction=p,
        saved_rows=len(times),
        max_error_pJ=float(max(errors)),
        max_relative_error=float(max(relative)),
        heat_pJ=values["H_total"][-1],
    )


def change(a, b):
    return dec(b) - dec(a)


def unchanged_amount():
    """One component move with equal release and loss at a positive, unchanged fate amount."""
    from cells.definitions.specs import parse_spec

    spec = parse_spec(worlds.r1(0.5))
    state, layout = get_model(spec.model).initial_values(spec)
    block = next(d for d in spec.model.operators if d.law == worlds.POLYMERISATION)
    names = [s.id for s in block.species]
    (chain,) = block.chains
    q = 1e-13
    n = np.asarray(layout.amount_reference)[layout.poly_rows]
    dn = np.zeros_like(n)
    dn[names.index("M"), 0] = chain.residues * q
    lost = np.zeros_like(state.poly_degraded_fmol)
    lost[next(i for i, d in enumerate(block.degradations) if d.polymer == "R")] = q
    out = np.zeros_like(state.poly_hold_released_fmol)
    out[0, 0, 0] = q
    zero = np.zeros_like(state.poly_initiated_fmol)
    extents = (
        zero,
        np.zeros_like(state.poly_complexes_fmol),
        lost,
        np.zeros_like(state.poly_transferred_fmol),
        out,
    )
    heats = polymer.route_heats(
        n, dn, zero, extents, layout.volume, layout.active, layout, float(sheet_check.RT), xp=np
    )
    booked = dec(heats[3][0, 0, 0])
    cap = dec(layout.volume[0]) * sheet_check.C_STD_MM
    expected = -dec(q) * sheet_check.RT * (dec(n[names.index("R"), 0]) / cap).ln()
    assert booked > 0 and abs(booked - expected) < Decimal("2e-12") * expected
    return dict(
        released_and_lost_fmol=q,
        net_R_change_fmol=0,
        release_heat_pJ=float(booked),
        error_pJ=float(abs(expected - booked)),
    )


def mixed():
    raw = observed(worlds.r1(0.5, machine="held", initiation=float(sheet_check.A1["k_I_tx"])), 60)
    kernel.block(raw)["chains"][0]["release"]["durable_fraction"] = "scheduled"
    schedule = [(0, 0.0), (16, 0.5), (36, 1.0)]
    raw["experiment"]["polymerisation_controls"].append(
        dict(route_id=worlds.RELEASE, schedule=[dict(time=t, value=p) for t, p in schedule])
    )
    spec, states, times, values, _ = collect(raw)
    _, layout = get_model(spec.model).initial_values(spec)
    block = next(d for d in spec.model.operators if d.law == worlds.POLYMERISATION)
    control = kernel.controls(raw, block)
    (chain,) = block.chains
    volume = dec(spec.model.cells[0].volume_pL)
    assert dec(block.c0_mM) == sheet_check.C_STD_MM
    cap = volume * sheet_check.C_STD_MM
    species = [s.id for s in block.species]
    indices = [list(spec.model.species_ids).index(row) for row in species]
    initial = [dec(layout.amount_reference[i, 0]) for i in indices]
    standard = {row: sheet_check.RT * dec(m) for row, m in zip(species, block.mu_RT, strict=True)}
    hold_mu = standard[chain.product]
    r = chain.residues // chain.stages
    maxima = dict.fromkeys(("synthesis", "degradation", "release", "state_function"), Decimal(0))
    counts = dict(active_release=0, loss_during_inactive_release=0, falling_fate_rows=0)
    release_total = Decimal(0)

    def compare(kind, expected, recorded, scale):
        error = abs(expected - recorded)
        assert error <= Decimal("2e-10") * scale, (kind, expected, recorded, scale)
        maxima[kind] = max(error, maxima[kind])

    for k, (before, after) in enumerate(zip(states[:-1], states[1:], strict=True)):
        fraction = next(p for t, p in reversed(schedule) if times[k] >= t)
        control.polymerisation_release_fraction[0] = fraction
        # Public trajectories save full steps. Recover the intermediate operator state to price
        # each half-step at its own endpoints, then compare with the compiled saved endpoint.
        mid, ok = kernel.OP.half_step(before, spec.execution.dt / 2, control, layout, xp=np)
        assert bool(ok)
        for a, b in ((before, mid), (mid, after)):
            slopes, dg = {}, []
            for row, ix, ref in zip(species, indices, initial, strict=True):
                u = ref + dec(a.amount_increment[ix, 0])
                v = ref + dec(b.amount_increment[ix, 0])
                move = potential_energy(v, cap) - potential_energy(u, cap)
                slopes[row] = standard[row] + (
                    sheet_check.RT * (u / cap).ln() if u == v else move / (v - u)
                )
                dg.append(standard[row] * (v - u) + move)
                if row in chain.release.rows() and v < u:
                    counts["falling_fate_rows"] += 1
            dh = change(a.poly_hold_fmol[0, 0], b.poly_hold_fmol[0, 0])
            dw = sum(
                j * r * change(u, v)
                for j, (u, v) in enumerate(
                    zip(a.poly_complexes_fmol[0], b.poly_complexes_fmol[0], strict=True)
                )
            )
            transit = dw * hold_mu / chain.residues
            dg.extend((transit, dh * hold_mu))
            heat = change(a.poly_dissipated_energy_pJ[0], b.poly_dissipated_energy_pJ[0])
            compare("state_function", -sum(dg), heat, sum(map(abs, dg)) + abs(heat))
            s = change(a.poly_stage_exits_fmol[0], b.poly_stage_exits_fmol[0])
            completed = change(a.poly_released_fmol[0], b.poly_released_fmol[0])
            terms = [s * r * count * slopes[row] for row, count in chain.releases]
            terms += [-s * r * count * slopes[row] for row, count in chain.draws]
            terms += [hold_mu * completed, transit]
            compare(
                "synthesis",
                -sum(terms),
                change(a.poly_chain_heat_pJ[0], b.poly_chain_heat_pJ[0]),
                sum(map(abs, terms)),
            )
            for j, d in enumerate(block.degradations):
                loss = change(a.poly_degraded_fmol[j], b.poly_degraded_fmol[j])
                terms = [loss * d.residues * count * slopes[row] for row, count in d.monomers]
                terms.append(-loss * slopes[d.polymer])
                compare(
                    "degradation",
                    -sum(terms),
                    change(a.poly_degradation_heat_pJ[j], b.poly_degradation_heat_pJ[j]),
                    sum(map(abs, terms)),
                )
            for f, row in enumerate(chain.release.fates[0]):
                q = change(a.poly_hold_released_fmol[0, 0, f], b.poly_hold_released_fmol[0, 0, f])
                measured = change(a.poly_release_heat_pJ[0, 0, f], b.poly_release_heat_pJ[0, 0, f])
                assert q >= 0 and measured >= 0
                if (fraction, f) in ((0, 0), (1, 1)):
                    assert q == measured == 0
                    if (
                        b.amount_increment[indices[species.index(row)], 0]
                        < a.amount_increment[indices[species.index(row)], 0]
                    ):
                        counts["loss_during_inactive_release"] += 1
                else:
                    assert q > 0
                    counts["active_release"] += 1
                expected = q * (hold_mu - slopes[row])
                compare("release", expected, measured, abs(expected))
                release_total += measured
    assert min(counts.values()) > 0 and values["int_Q_tx"][-1] > 0
    assert all(values[f"int_D_{row}"][-1] > 0 for row in chain.release.rows())
    # A second booking of detachment would leave this much unbalanced heat.
    assert release_total > 1000 * maxima["state_function"]
    return dict(
        saved_rows=len(times),
        half_steps=2 * (len(times) - 1),
        **counts,
        max_error_pJ={k: float(v) for k, v in maxima.items()},
        extra_heat_if_booked_twice_pJ=float(release_total),
    )


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    with localcontext() as ctx:
        ctx.prec = 65
        print(
            json.dumps(
                dict(
                    isolated=[isolated(p) for p in (0.0, 0.5, 1.0)],
                    mixed=mixed(),
                    unchanged_amount=unchanged_amount(),
                ),
                indent=2,
                allow_nan=False,
            )
        )
