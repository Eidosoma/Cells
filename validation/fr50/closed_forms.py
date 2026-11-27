"""FR-50's phase-1 closed forms, written by the builder from the references' spec (LAWS.md), for the
engine's tests and the judge's dry run. They are not the code-blind references, which alone judge
the registered comparison (validation/fr50/judge.py against references/results/).

Each is a judge.Reference built from a spec case (cases.json's entry), so the tests call the tagged
judge's own check functions and cannot drift from the judged run's criteria. Arithmetic is Decimal
at 60 digits with the 2019 SI constants: F = N_A e, R = N_A k.
- K1 (LAWS.md §2, §5): a = 1e15 P A o (pL/s), forward (inward) a c_node and backward a c_cell, each
  record its flux times t;
- K2 (§5): k = a (1/V_cell + 1/V_node), c_bar = n_tot / (V_cell + V_node), and
  F(t) = a [c_bar t - (V_cell/V_node)(c_cell(0) - c_bar)(1 - e^(-k t))/k],
  B(t) = a [c_bar t + (c_cell(0) - c_bar)(1 - e^(-k t))/k];
- K3 (§2): x = z F V/(R T), forward (inward) g c_out B(x), backward g c_in B(-x), B(x) =
  x/(e^x - 1), and inward/outward = (c_out/c_in) e^(-x);
- K4 and K4h (§3): dG/RT = dmu0/RT + ln(c_ADP c_Pi/(c_ATP c0)) + n ln(c_out/c_in),
  S = [1 + (K/c_in)^n]^-1 [1 + K_ATP/c_ATP]^-1, J+ = k a S and J- = J+ e^(dG/RT); K4's records
  J+- t.

Phase 2's (LAWS.md §2, §4, §5), with E_K = (R T/(z F)) ln(c_out/c_in) at 60 digits:
- E1, @3's membrane route at V = E_K: g = 1e15 P A v, forward (outward) g c_in B(-x), backward
  g c_out B(x), each record its flux times t;
- E2, a junction route at equal concentrations and potentials (x = 0): g = 1e15 P A gate v, each
  direction g c, sender to receiver;
- E3, an uncharged face: g = 1e15 D A / L, each direction g c;
- E4, the blocked population at V = E_K: g = 1e15 P r a o v u A with u = K1/(c_B + K1), K1 =
  K1(0) exp(s z_B delta F V_ref/(R T)), V_ref = V - E_K = 0 here;
- E6, the same population at the declared voltages and availabilities: u at V_ref = V - E_K, each
  direction (outward g c_in B(-x), inward g c_out B(x)), their ratio and their difference.
"""

import re
from decimal import Decimal, localcontext

from validation.fr50 import judge

N_A, E, K_B = Decimal("6.02214076e23"), Decimal("1.602176634e-19"), Decimal("1.380649e-23")
PRECISION = 60
RULE = re.compile(r"t_i = (\S+) i, i = 0 \.\.\. (\d+)")


def _d(text):
    return Decimal(text)


def record_times(case):
    """The case's record times, as strings, from its rule "t_i = h i, i = 0 ... N"."""
    step, count = RULE.fullmatch(case["record_times_s"]["rule"]).groups()
    return tuple(str(Decimal(step) * i) for i in range(int(count) + 1))


def _bernoulli(x):
    return Decimal(1) if x == 0 else x / (x.exp() - 1)


def _reference(case_id, kind, case, direction, *, scalars=(), times=(), series=None, rows=()):
    return judge.Reference(
        case_id=case_id,
        case_kind=kind,
        declared=case,
        direction=direction,
        scalars=dict(scalars),
        times_raw=tuple(times),
        times=tuple(Decimal(t) for t in times),
        series={k: tuple(v) for k, v in (series or {}).items()},
        rows_raw=tuple(
            {k: str(v) if not isinstance(v, str) else v for k, v in r.items()} for r in rows
        ),
        rows=tuple({k: Decimal(v) for k, v in r.items()} for r in rows),
        trusted=True,
        untrusted_because=(),
        invented=False,
        revision="the builder's closed forms (validation/fr50/closed_forms.py)",
        sha256="",
    )


def k1(case_id, case, times=None):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        a = Decimal("1e15") * _d(case["P_m_per_s"]) * _d(case["A_m2"]) * _d(case["opening"])
        forward, backward = a * _d(case["c_node_mM"]), a * _d(case["c_cell_mM"])
        times = times or record_times(case)
        series = dict(
            F_fmol=[forward * Decimal(t) for t in times],
            B_fmol=[backward * Decimal(t) for t in times],
        )
        scalars = dict(
            prefactor_pL_per_s=a,
            forward_fmol_per_s=forward,
            backward_fmol_per_s=backward,
            net_fmol_per_s=forward - backward,
        )
        return _reference(
            case_id, "K1", case, "inward", scalars=scalars, times=times, series=series
        )


def k2(case_id, case, times=None):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        a = Decimal("1e15") * _d(case["P_m_per_s"]) * _d(case["A_m2"]) * _d(case["opening"])
        v_o, v_n = _d(case["V_cell_pL"]), _d(case["V_node_pL"])
        c_o0, c_n0 = _d(case["c_cell_mM_at_0"]), _d(case["c_node_mM_at_0"])
        k = a * (1 / v_o + 1 / v_n)
        c_bar = (v_o * c_o0 + v_n * c_n0) / (v_o + v_n)
        times = times or record_times(case)
        F, B, c_cell, c_node = [], [], [], []
        for text in times:
            t = Decimal(text)
            decay = (-k * t).exp()
            integral = (1 - decay) / k
            F.append(a * (c_bar * t - (v_o / v_n) * (c_o0 - c_bar) * integral))
            B.append(a * (c_bar * t + (c_o0 - c_bar) * integral))
            c_cell.append(c_bar + (c_o0 - c_bar) * decay)
            c_node.append(c_bar - (v_o / v_n) * (c_o0 - c_bar) * decay)
        series = dict(c_cell_mM=c_cell, c_node_mM=c_node, F_fmol=F, B_fmol=B)
        scalars = dict(a_pL_per_s=a, k_per_s=k, c_bar_mM=c_bar)
        return _reference(
            case_id, "K2", case, "inward", scalars=scalars, times=times, series=series
        )


def k3(case_id, case):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        F, R = N_A * E, N_A * K_B
        g = Decimal("1e15") * _d(case["P_m_per_s"]) * _d(case["A_m2"]) * _d(case["opening"])
        c_in, c_out, z = _d(case["c_in_mM"]), _d(case["c_out_mM"]), Decimal(case["valence"])
        rows = []
        for v in case["voltages_V"]:
            x = z * F * Decimal(v) / (R * _d(case["T_K"]))
            forward, backward = g * c_out * _bernoulli(x), g * c_in * _bernoulli(-x)
            rows.append(
                dict(
                    V_V=v,
                    forward_fmol_per_s=forward,
                    backward_fmol_per_s=backward,
                    ratio_inward_over_outward=forward / backward,
                    ratio_backward_over_forward=backward / forward,
                )
            )
        return _reference(case_id, "K3", case, "inward", rows=rows)


def _transporter(case):
    n, c0 = Decimal(case["stoichiometry"]), _d(case["c0_mM"])
    c_in, c_out = _d(case["c_in_mM"]), _d(case["c_out_mM"])
    mu, fuel = ({k: _d(v) for k, v in case[key].items()} for key in ("mu0_over_RT", "fuel_mM"))
    dg = mu["ADP"] + mu["Pi"] - mu["ATP"]
    dg += (fuel["ADP"] * fuel["Pi"] / (fuel["ATP"] * c0)).ln() + n * (c_out / c_in).ln()
    s = 1 / (1 + (_d(case["K_mM"]) / c_in) ** int(n)) / (1 + _d(case["K_ATP_mM"]) / fuel["ATP"])
    plus = _d(case["capacity_fmol_cycles_per_s"]) * _d(case["availability"]) * s
    return dg, s, plus, plus * dg.exp()


def k4(case_id, case, times=None):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        dg, s, plus, minus = _transporter(case)
        times = times or record_times(case)
        series = dict(
            F_fmol_cycles=[plus * Decimal(t) for t in times],
            B_fmol_cycles=[minus * Decimal(t) for t in times],
        )
        scalars = dict(
            dG_cyc_over_RT=dg,
            S=s,
            J_plus_fmol_cycles_per_s=plus,
            J_minus_fmol_cycles_per_s=minus,
            net_fmol_cycles_per_s=plus - minus,
        )
        return _reference(
            case_id, "K4", case, "forward", scalars=scalars, times=times, series=series
        )


def k4h(case_id, case):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        dg, s, plus, minus = _transporter(case)
        scalars = dict(
            dG_cyc_over_RT=dg,
            S=s,
            J_plus_fmol_cycles_per_s=plus,
            J_minus_fmol_cycles_per_s=minus,
            J_minus_over_J_plus=minus / plus,
        )
        return _reference(case_id, "K4h", case, "forward", scalars=scalars)


def _constants():
    return N_A * E, N_A * K_B


def _e_k(case):
    """E_K (V) of the case's ion, (R T/(z F)) ln(c_out/c_in), at the context's precision."""
    F, R = _constants()
    z = Decimal(case["valence"])
    return R * _d(case["T_K"]) / (z * F) * (_d(case["c_out_mM"]) / _d(case["c_in_mM"])).ln()


def _unblocked(case, v_ref):
    """LAWS.md §4's u at V_ref for the case's one-mode block, summed over its modes by weight."""
    F, R = _constants()
    block = case["block"]
    blocker = block["blocker"]
    side = 1 if blocker["side"] == "outside" else -1
    z_b, c_b = Decimal(blocker["valence"]), _d(blocker["concentration_mM"])
    u = Decimal(0)
    for mode in block["modes"]:
        k = (
            _d(mode["k0_mM"])
            * (
                side * z_b * _d(mode["electrical_distance"]) * F * v_ref / (R * _d(case["T_K"]))
            ).exp()
        )
        u += _d(mode["weight"]) * k / (c_b + k)
    return u


def _channel_prefactor(case, availability):
    keys = ("P_m_per_s", "relative_permeability", "abundance", "open_fraction", "A_m2")
    g = Decimal("1e15") * availability
    for key in keys:
        g *= _d(case[key])
    return g


def _steady(case_id, kind, case, direction, g, forward, backward, scalars=(), times=None):
    times = times or record_times(case)
    series = dict(
        F_fmol=[forward * Decimal(t) for t in times],
        B_fmol=[backward * Decimal(t) for t in times],
    )
    scalars = dict(
        scalars,
        prefactor_pL_per_s=g,
        forward_fmol_per_s=forward,
        backward_fmol_per_s=backward,
        net_fmol_per_s=forward - backward,
    )
    return _reference(case_id, kind, case, direction, scalars=scalars, times=times, series=series)


def e1(case_id, case, times=None):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        F, R = _constants()
        e_k = _e_k(case)
        x = Decimal(case["valence"]) * F * e_k / (R * _d(case["T_K"]))
        g = Decimal("1e15") * _d(case["P_m_per_s"]) * _d(case["A_m2"]) * _d(case["availability"])
        forward = g * _d(case["c_in_mM"]) * _bernoulli(-x)
        backward = g * _d(case["c_out_mM"]) * _bernoulli(x)
        return _steady(case_id, "E1", case, "outward", g, forward, backward,
                       scalars=dict(E_K_V=e_k, V_V=e_k), times=times)  # fmt: skip


def e2(case_id, case, times=None):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        g = Decimal("1e15") * _d(case["P_m_per_s"]) * _d(case["A_m2"]) * _d(case["gate"])
        g *= _d(case["availability"])
        forward, backward = g * _d(case["c_sender_mM"]), g * _d(case["c_receiver_mM"])
        return _steady(case_id, "E2", case, "sender", g, forward, backward, times=times)


def e3(case_id, case, times=None):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        g = Decimal("1e15") * _d(case["D_m2_per_s"]) * _d(case["A_m2"]) / _d(case["L_m"])
        forward, backward = g * _d(case["c_sender_mM"]), g * _d(case["c_receiver_mM"])
        return _steady(case_id, "E3", case, "sender", g, forward, backward, times=times)


def e4(case_id, case, times=None):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        F, R = _constants()
        e_k = _e_k(case)
        x = Decimal(case["valence"]) * F * e_k / (R * _d(case["T_K"]))
        u = _unblocked(case, Decimal(0))
        g = _channel_prefactor(case, _d(case["availability"])) * u
        forward = g * _d(case["c_in_mM"]) * _bernoulli(-x)
        backward = g * _d(case["c_out_mM"]) * _bernoulli(x)
        return _steady(case_id, "E4", case, "outward", g, forward, backward,
                       scalars=dict(E_K_V=e_k, V_V=e_k, u=u), times=times)  # fmt: skip


def e6(case_id, case):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        F, R = _constants()
        e_k = _e_k(case)
        rows = []
        for v in case["voltages_V"]:
            for a in case["availabilities"]:
                x = Decimal(case["valence"]) * F * Decimal(v) / (R * _d(case["T_K"]))
                u = _unblocked(case, Decimal(v) - e_k)
                g = _channel_prefactor(case, Decimal(a)) * u
                out = g * _d(case["c_in_mM"]) * _bernoulli(-x)
                back = g * _d(case["c_out_mM"]) * _bernoulli(x)
                rows.append(
                    dict(
                        V_V=v, availability=a, V_ref_V=Decimal(v) - e_k, u=u,
                        forward_fmol_per_s=out, backward_fmol_per_s=back,
                        ratio_inward_over_outward=back / out,
                        ratio_backward_over_forward=back / out,
                        difference_forward_minus_backward_fmol_per_s=out - back,
                    )
                )  # fmt: skip
        return _reference(case_id, "E6", case, "outward", scalars=dict(E_K_V=e_k), rows=rows)


BUILDERS = {"K1": k1, "K2": k2, "K3": k3, "K4": k4, "K4h": k4h}
PHASE_2_BUILDERS = {"E1": e1, "E2": e2, "E3": e3, "E4": e4, "E6": e6}


def phase_1(cases):
    """{case ID: Reference} for every phase-1 case of the spec's cases (cases.json's "cases")."""
    out = {}
    for case_id, case in cases.items():
        kind = case_id.split("_")[0]
        if kind in BUILDERS:
            out[case_id] = BUILDERS[kind](case_id, case)
    return out


def phase_2(cases):
    """{case ID: Reference} for every phase-2 case of the spec's cases (cases.json's "cases")."""
    out = {}
    for case_id, case in cases.items():
        kind = case_id.split("_")[0]
        if kind in PHASE_2_BUILDERS:
            out[case_id] = PHASE_2_BUILDERS[kind](case_id, case)
    return out
