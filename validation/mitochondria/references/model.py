"""Beard 2005 (corrected 2006) from its data file: compiler, conservation laws and solvers.

The model lives in ``beard2005_model.json``. This module turns it into right-hand sides
for two arithmetics:

- float, for the stiff time integration (SciPy's Radau, with LSODA as a cross-check);
- ``decimal`` at 50 digits, for the exact steady-state Newton solve.

Expressions in the data file are checked against a small grammar (numbers, names, the
four operations, powers, ``exp``, ``ln``, ``ratio0`` and ``bern``) before they are
compiled, so the data file can only ever describe arithmetic.

Eq. 22 conserves two inventories (``conservation_laws`` finds them in exact rationals),
so its Jacobian is singular and its steady states depend on initial inventories that
Beard 2005 never reports (Q25). The Newton solve replaces two rows of Eq. 22 by those
invariants, with their values given explicitly.
"""

from __future__ import annotations

import ast
import json
import math
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import numpy as np

DATA = Path(__file__).with_name("beard2005_model.json")
FUNCS = ("exp", "ln", "ratio0", "bern")
DEC_PREC = 50


def load(path: Path | None = None) -> dict:
    return json.loads(Path(path or DATA).read_text())


def parse_printed(text: str | None) -> float | None:
    """'2.9802 x 10^-6' -> 2.9802e-06; '4.2530' -> 4.253; None -> None."""
    if text is None:
        return None
    t = text.replace(" ", "")
    if "x10^" in t:
        mant, exp = t.split("x10^")
        return float(mant) * 10.0 ** int(exp)
    return float(t)


def parse_printed_fraction(text: str) -> Fraction:
    t = text.replace(" ", "")
    if "x10^" in t:
        mant, exp = t.split("x10^")
        return Fraction(mant) * Fraction(10) ** int(exp)
    return Fraction(t)


# --------------------------------------------------------------------------- expressions

_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Constant, ast.Load,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)


def check_expr(expr: str, known: set[str]) -> ast.Expression:
    """Parse ``expr`` and refuse anything but arithmetic on known names."""
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"{type(node).__name__} not allowed in {expr!r}")
        if isinstance(node, ast.Call):
            if not (isinstance(node.func, ast.Name) and node.func.id in FUNCS) or node.keywords:
                raise ValueError(f"call not allowed in {expr!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError(f"constant {node.value!r} not allowed in {expr!r}")
        if isinstance(node, ast.Name) and node.id not in known and node.id not in FUNCS:
            raise ValueError(f"unknown name {node.id!r} in {expr!r}")
    return tree


def names_in(expr: str) -> set[str]:
    return {n.id for n in ast.walk(ast.parse(expr, mode="eval")) if isinstance(n, ast.Name)} - set(FUNCS)


def eval_fraction(expr: str, env: dict[str, Fraction]) -> Fraction:
    """Exact value of a stoichiometric coefficient such as '-(4+1)' or 'n_A - 1'."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return Fraction(n.value)
        if isinstance(n, ast.Name):
            return env[n.id]
        if isinstance(n, ast.UnaryOp):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
        raise ValueError(ast.dump(n))
    return ev(check_expr(expr, set(env)))


# --------------------------------------------------------------------------- arms

@dataclass
class Arm:
    """One choice per switch in the data file; ``published()`` is the published arm."""
    column: str = "with"
    table: str = "e8"
    J_DH: str = "eq1"
    J_C3: str = "eq24_with_eq7_proton_term"   # Q02: what the published curves were computed with
    J_F1: str = "eq11"
    J_PiHt: str = "eq16_printed"
    DGo_ATP_sign: int = 1
    cytc_volume: str = "V_x"
    H_x_row: str = "pdf"
    T: float = 298.15
    overrides: dict = field(default_factory=dict)   # parameter name -> value (working units)

    @classmethod
    def published(cls, **kw):
        return cls(**kw)

    @classmethod
    def without_control(cls, **kw):
        kw.setdefault("column", "without")
        kw.setdefault("J_C3", "eq7")
        return cls(**kw)

    def label(self) -> str:
        ref = Arm.published() if self.column == "with" else Arm.without_control()
        diff = [f"{k}={getattr(self, k)}" for k in ("table", "J_DH", "J_C3", "J_F1", "J_PiHt", "DGo_ATP_sign",
                                                    "cytc_volume", "H_x_row", "T")
                if getattr(self, k) != getattr(ref, k)]
        diff += [f"{k}={v:g}" for k, v in sorted(self.overrides.items())]
        return f"{self.column}-control" + ("[" + ",".join(diff) + "]" if diff else "")


def parameters(model: dict, arm: Arm) -> dict[str, float]:
    """Working-unit parameter values for an arm (Table 1 column and version)."""
    out = {}
    for name, p in model["parameters"].items():
        printed = p[arm.table][arm.column]
        if printed is None:
            continue
        out[name] = parse_printed(printed) * p["scale"]
    for name, c in model["text_constants"].items():
        out[name] = c["value"]
    out["DGo_ATP"] = arm.DGo_ATP_sign * abs(model["text_constants"]["DGo_ATP"]["value"])
    out["R"] = model["constants"]["R"]["value"]
    out["F"] = model["constants"]["F"]["value"]
    out["T"] = arm.T
    out.update(arm.overrides)
    return out


STATES = ("H_x", "K_x", "Mg_x", "NADH_x", "QH2_x", "cytCred", "ATP_x", "mATP_x", "mADP_x", "Pi_x",
          "ATP_i", "ADP_i", "AMP_i", "mATP_i", "mADP_i", "Pi_i", "dPsi")
HELD = ("H_e", "K_e", "Mg_i", "ATP_e", "ADP_e", "AMP_e", "Pi_e", "O2")


def flux_exprs(model: dict, arm: Arm) -> dict[str, str]:
    out = {}
    for name, f in model["fluxes"].items():
        out[name] = f["variants"][getattr(arm, name)] if "variants" in f else f["expr"]
    return out


def ode_rows(model: dict, arm: Arm) -> dict[str, dict]:
    rows = {k: dict(v) for k, v in model["ode"]["rows"].items()}
    if arm.H_x_row == "stale_web_xml":
        rows["H_x"]["terms"] = dict(model["ode"]["stale_web_xml_H_x_row"])
    rows["cytCred"]["volume"] = arm.cytc_volume
    return rows


# --------------------------------------------------------------------------- compiler

class _ConstLift(ast.NodeTransformer):
    """Replace numeric literals by names so the same code runs in float or Decimal."""
    def __init__(self, table):
        self.table = table

    def visit_Constant(self, node):
        key = repr(node.value)
        name = self.table.setdefault(key, f"_k{len(self.table)}")
        return ast.copy_location(ast.Name(id=name, ctx=ast.Load()), node)


def _dec_exp(x):
    return x.exp()


def _dec_ln(x):
    return x.ln()


def _ratio0(a, b):
    return a / b if b != 0 else a * 0


def _bern_float(u):
    if abs(u) < 1e-8:
        return 1.0 - u / 2.0
    return u / math.expm1(u)


def _bern_dec(u):
    if abs(u) < Decimal("1e-20"):
        return 1 - u / 2
    return u / (u.exp() - 1)


@dataclass
class Compiled:
    model: dict
    arm: Arm
    params: dict
    source: str
    flux_names: tuple
    _fn_float: object = None
    _fn_dec: object = None

    def _namespace(self, kind):
        ns = {"__builtins__": {}}
        conv = float if kind == "float" else (lambda v: Decimal(repr(float(v))) if not isinstance(v, Fraction)
                                              else Decimal(v.numerator) / Decimal(v.denominator))
        if kind == "float":
            ns.update(exp=math.exp, ln=math.log, ratio0=_ratio0, bern=_bern_float)
        else:
            ns.update(exp=_dec_exp, ln=_dec_ln, ratio0=_ratio0, bern=_bern_dec)
        for k, v in self.params.items():
            ns[k] = conv(v)
        for lit, name in self._consts.items():
            ns[name] = conv(Fraction(lit)) if kind != "float" else float(lit)
        for name, c in self._coeffs.items():
            ns[name] = float(c) if kind == "float" else Decimal(c.numerator) / Decimal(c.denominator)
        return ns

    def fn(self, kind="float"):
        attr = "_fn_float" if kind == "float" else "_fn_dec"
        if getattr(self, attr) is None:
            ns = self._namespace(kind)
            exec(compile(self.source, "<beard2005>", "exec"), ns)
            setattr(self, attr, ns["_model"])
        return getattr(self, attr)

    def _args(self, y, held, kind):
        if kind == "float":
            return y, held
        return [_dec(v) for v in y], {k: _dec(v) for k, v in held.items()}

    def rhs(self, y, held, kind="float"):
        return self.fn(kind)(*self._args(y, held, kind))[0]

    def fluxes(self, y, held, kind="float"):
        return dict(zip(self.flux_names, self.fn(kind)(*self._args(y, held, kind))[1]))


def compile_model(model: dict | None = None, arm: Arm | None = None) -> Compiled:
    model = model or load()
    arm = arm or Arm.published()
    params = parameters(model, arm)
    fexprs = flux_exprs(model, arm)
    rows = ode_rows(model, arm)
    known = set(params) | set(STATES) | set(HELD)
    consts: dict[str, str] = {}
    lifter = _ConstLift(consts)

    def code(expr):
        tree = check_expr(expr, known)
        return ast.unparse(lifter.visit(tree).body)

    lines = ["def _model(y, h):",
             "    " + ", ".join(STATES) + ", = y",
             "    " + ", ".join(HELD) + ", = (h[k] for k in " + repr(HELD) + ")"]
    for a in model["algebraic"]:
        lines.append(f"    {a['name']} = {code(a['expr'])}")
        known.add(a["name"])
    for name, expr in fexprs.items():
        lines.append(f"    {name} = {code(expr)}")
        known.add(name)
    frac_env = {k: Fraction(repr(v)) if not isinstance(v, int) else Fraction(v) for k, v in params.items()}
    coeffs: dict[str, Fraction] = {}
    outs = []
    for s in STATES:
        row = rows[s]
        terms = []
        for j, c in row["terms"].items():
            val = eval_fraction(c, frac_env)
            cname = f"_c_{s}_{j}"
            coeffs[cname] = val
            terms.append(f"{cname}*{j}")
        rate = "(" + " + ".join(terms) + ")"
        if row.get("factor"):
            rate = f"{row['factor']}*{rate}"
        lines.append(f"    d_{s} = {rate}/{row['volume']}")
        outs.append(f"d_{s}")
    lines.append("    return (" + ", ".join(outs) + ",), (" + ", ".join(fexprs) + ",)")
    comp = Compiled(model, arm, params, "\n".join(lines), tuple(fexprs))
    comp._consts = {k: v for k, v in consts.items()}
    comp._coeffs = coeffs
    return comp


# --------------------------------------------------------------------------- conservation

def stoichiometry(model: dict, arm: Arm) -> tuple[list[str], list[str], list[list[Fraction]]]:
    """Exact amount-rate stoichiometry: d(amount_s)/dt = sum_j S[s][j] J_j (per l mito)."""
    params = parameters(model, arm)
    env = {k: Fraction(repr(v)) for k, v in params.items()}
    rows = ode_rows(model, arm)
    fl = list(model["fluxes"])
    S = [[eval_fraction(rows[s]["terms"][j], env) if j in rows[s]["terms"] else Fraction(0) for j in fl]
         for s in STATES]
    return list(STATES), fl, S


def left_null_space(S: list[list[Fraction]]) -> list[list[Fraction]]:
    """Basis of {y : y^T S = 0}, exact, in reduced form."""
    m, n = len(S), len(S[0])
    A = [[S[i][j] for i in range(m)] for j in range(n)]   # S^T, n x m
    pivots, r = [], 0
    for c in range(m):
        p = next((i for i in range(r, n) if A[i][c] != 0), None)
        if p is None:
            continue
        A[r], A[p] = A[p], A[r]
        pv = A[r][c]
        A[r] = [x / pv for x in A[r]]
        for i in range(n):
            if i != r and A[i][c] != 0:
                f = A[i][c]
                A[i] = [a - f * b for a, b in zip(A[i], A[r])]
        pivots.append(c)
        r += 1
    free = [c for c in range(m) if c not in pivots]
    basis = []
    for fcol in free:
        v = [Fraction(0)] * m
        v[fcol] = Fraction(1)
        for row, pc in enumerate(pivots):
            v[pc] = -A[row][fcol]
        basis.append(v)
    return basis


def conservation_laws(model: dict | None = None, arm: Arm | None = None) -> list[dict[str, Fraction]]:
    """The invariants of Eq. 22 as {state: weight} on the states' amounts.

    Amounts are V*c for concentrations, V_x*ln(H_x)/rbuff_coeff for the buffered H+ row,
    and C_IM*dPsi for the potential."""
    model = model or load()
    arm = arm or Arm.published()
    states, _, S = stoichiometry(model, arm)
    return [{s: w for s, w in zip(states, v) if w != 0} for v in left_null_space(S)]


def amount(state: str, value, params: dict, rows: dict, kind="float"):
    """The conserved amount (per l mito) carried by one state's value."""
    if kind == "float":
        P = {k: float(v) for k, v in params.items()}
        ln = math.log
    else:
        P = {k: Decimal(repr(float(v))) for k, v in params.items()}
        ln = _dec_ln
    if state == "H_x":
        return P["V_x"] * ln(value) / P["rbuff_coeff"]
    vol = rows[state]["volume"]
    return P[vol] * value


def invariants(comp: Compiled, y, kind="float"):
    laws = conservation_laws(comp.model, comp.arm)
    rows = ode_rows(comp.model, comp.arm)
    out = []
    for law in laws:
        tot = 0
        for s, w in law.items():
            wv = float(w) if kind == "float" else Decimal(w.numerator) / Decimal(w.denominator)
            tot = tot + wv * amount(s, y[STATES.index(s)], comp.params, rows, kind)
        out.append(tot)
    return laws, out


# --------------------------------------------------------------------------- conditions

def buffer_free_mg(Mg_total, ATP_e, ADP_e, K_MgATP, K_MgADP):
    """Free Mg2+ of a buffer with total Mg2+ and nucleotides at Table 1's constants (Q26)."""
    lo, hi = 0.0, Mg_total
    for _ in range(200):
        m = 0.5 * (lo + hi)
        bound = ATP_e * m / (m + K_MgATP) + ADP_e * m / (m + K_MgADP)
        if m + bound > Mg_total:
            hi = m
        else:
            lo = m
    return 0.5 * (lo + hi)


def held(model, comp: Compiled, *, ADP_e=0.0, ATP_e=0.0, AMP_e=0.0, Pi_e=0.0, O2=2.6e-5,
         pH_e=7.1, K_e=0.150, Mg_total_e=5.0e-3, mg_i_rule="buffer_free"):
    p = comp.params
    if mg_i_rule == "buffer_free":
        Mg_i = buffer_free_mg(Mg_total_e, ATP_e, ADP_e, p["K_MgATP"], p["K_MgADP"])
    elif mg_i_rule == "total":
        Mg_i = Mg_total_e
    else:
        raise ValueError(mg_i_rule)
    return {"H_e": 10.0 ** -pH_e, "K_e": K_e, "Mg_i": Mg_i, "ATP_e": ATP_e, "ADP_e": ADP_e,
            "AMP_e": AMP_e, "Pi_e": Pi_e, "O2": O2}


def _mg_split(total_mg, atp, adp, k_atp, k_adp):
    """Free Mg2+ and the bound forms for a Mg2+ total at binding equilibrium."""
    lo, hi = 0.0, total_mg
    for _ in range(200):
        m = 0.5 * (lo + hi)
        tot = m + atp * m / (m + k_atp) + adp * m / (m + k_adp)
        lo, hi = (m, hi) if tot < total_mg else (lo, m)
    m = 0.5 * (lo + hi)
    return m, atp * m / (m + k_atp), adp * m / (m + k_adp)


def _ak_equilibrium(atp, adp, amp, K):
    """IMS pools after 2 ADP = ATP + AMP reaches K = ATP*AMP/ADP^2 (totals conserved)."""
    lo, hi = -min(atp, amp), adp / 2.0
    g = lambda x: K * (adp - 2 * x) ** 2 - (amp + x) * (atp + x)
    if adp + atp + amp == 0:
        return 0.0, 0.0, 0.0
    for _ in range(200):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if g(m) > 0 else (lo, m)
    x = 0.5 * (lo + hi)
    return atp + x, adp - 2 * x, amp + x


def initial_state(comp: Compiled, h: dict, *, pH_x=7.1, K_x=0.150, Mg_x_total=1.0e-3, dPsi=170.0,
                  NADH_frac=0.6, QH2_frac=0.5, cytc_red_frac=0.1, Pi_x=None):
    """A declared, equilibrated starting state (NOT from Beard 2005; Q25).

    Matrix ATP/ADP starts at F1F0 equilibrium (Eq. 11's zero) and the IMS nucleotides at
    adenylate kinase equilibrium, both with Mg2+ bound at equilibrium. Starting far from
    those equilibria makes Eq. 22 drive free forms negative (F1F0 and the kinase act on
    totals, binding on free forms), which Eq. 14 cannot survive. Only two inventories of
    this state reach the steady state: the matrix Mg2+ total and the charge combination."""
    p = comp.params
    RT = p["R"] * p["T"]
    Pi = h["Pi_e"] if Pi_x is None else Pi_x
    H_x = 10.0 ** -pH_x
    DG_H = p["F"] * dPsi + RT * math.log(h["H_e"] / H_x)
    expo = -(p["DGo_ATP"] - p["n_A"] * DG_H) / RT
    if comp.arm.J_F1 == "eq11_with_proton_term":
        expo += math.log(H_x / 1e-7)
    Keq = math.exp(min(expo, 700.0)) / p["one_molar"]   # fATP/(fADP Pi)
    A = p["A_tot"]
    Mg, ATP_x = 1e-4, 0.0
    for _ in range(100):
        rho = Keq * Pi * (1 + Mg / p["K_MgATP"]) / (1 + Mg / p["K_MgADP"])
        ATP_x = A * rho / (1 + rho)
        Mg, mATP_x, mADP_x = _mg_split(Mg_x_total, ATP_x, A - ATP_x, p["K_MgATP"], p["K_MgADP"])
    ATP_i, ADP_i, AMP_i = _ak_equilibrium(h["ATP_e"], h["ADP_e"], h["AMP_e"], p["K_AK"])
    Mg_i = h["Mg_i"]
    y = {"H_x": H_x, "K_x": K_x, "Mg_x": Mg, "NADH_x": NADH_frac * p["NAD_tot"],
         "QH2_x": QH2_frac * p["Q_tot"], "cytCred": cytc_red_frac * p["cytC_tot"], "ATP_x": ATP_x,
         "mATP_x": mATP_x, "mADP_x": mADP_x, "Pi_x": Pi,
         "ATP_i": ATP_i, "ADP_i": ADP_i, "AMP_i": AMP_i,
         "mATP_i": ATP_i * Mg_i / (Mg_i + p["K_MgATP"]),
         "mADP_i": ADP_i * Mg_i / (Mg_i + p["K_MgADP"]), "Pi_i": h["Pi_e"], "dPsi": dPsi}
    return np.array([y[s] for s in STATES])


def with_invariants(comp: Compiled, y0, charge=None, mg_total=None):
    """Shift a start state so its invariants take given values: the charge inventory through
    K_x (weight 1 on V_x K_x), the Mg2+ inventory through the matrix Mg2+ total."""
    y = np.array(y0, float)
    p = comp.params
    if mg_total is not None:
        ATP_x = y[STATES.index("ATP_x")]
        Mg, mA, mD = _mg_split(mg_total, ATP_x, p["A_tot"] - ATP_x, p["K_MgATP"], p["K_MgADP"])
        y[STATES.index("Mg_x")], y[STATES.index("mATP_x")], y[STATES.index("mADP_x")] = Mg, mA, mD
    if charge is not None:
        laws, vals = invariants(comp, y)
        k = next(i for i, law in enumerate(laws) if "K_x" in law)
        y[STATES.index("K_x")] += (charge - vals[k]) / (float(laws[k]["K_x"]) * p["V_x"])
    return y


# --------------------------------------------------------------------------- integration

def integrate(comp: Compiled, h: dict, y0, t_end=4000.0, method="Radau", rtol=1e-10, atol_rel=1e-12,
              t_eval=None):
    """Stiff integration of Eq. 22 in float64."""
    from scipy.integrate import solve_ivp
    f = comp.fn("float")
    scale = np.maximum(np.abs(np.asarray(y0, float)), 1e-6)
    scale[STATES.index("H_x")] = 1e-8
    scale[STATES.index("dPsi")] = 100.0
    atol = atol_rel * scale
    sol = solve_ivp(lambda t, y: f(y, h)[0], (0.0, t_end), np.asarray(y0, float), method=method,
                    rtol=rtol, atol=atol, t_eval=t_eval)
    if not sol.success:
        raise RuntimeError(sol.message)
    return sol


# --------------------------------------------------------------------------- exact steady state

def _dec(v):
    return v if isinstance(v, Decimal) else Decimal(repr(float(v)))


def _solve_dec(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(M[i][c]))
        if M[p][c] == 0:
            raise ZeroDivisionError("singular Jacobian")
        M[c], M[p] = M[p], M[c]
        for i in range(c + 1, n):
            f = M[i][c] / M[c][c]
            if f != 0:
                M[i] = [a - f * bb for a, bb in zip(M[i], M[c])]
    x = [Decimal(0)] * n
    for i in reversed(range(n)):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


@dataclass
class SteadyState:
    y: list            # Decimal states, STATES order
    residual: Decimal  # max |f_i| scaled, over the free rows
    iterations: int
    invariant_values: list
    pinned: tuple

    def floats(self):
        return np.array([float(v) for v in self.y])


def steady_state(comp: Compiled, h: dict, y_guess, invariant_values=None, pinned=(), prec=DEC_PREC,
                 tol_exp=-38, max_iter=60):
    """Newton in Decimal on Eq. 22 with the invariants replacing two rows.

    ``invariant_values``: values of ``invariants(...)`` to impose (default: those of
    ``y_guess``). ``pinned``: states fixed at exactly zero (e.g. IMS nucleotides when the
    buffer has none, where Eq. 14's limit is taken analytically)."""
    laws = conservation_laws(comp.model, comp.arm)
    rows = ode_rows(comp.model, comp.arm)
    f = comp.fn("decimal")
    with localcontext() as ctx:
        ctx.prec = prec
        hd = {k: _dec(v) for k, v in h.items()}
        y = [_dec(v) for v in y_guess]
        for s in pinned:
            y[STATES.index(s)] = Decimal(0)
        if invariant_values is None:
            _, invariant_values = invariants(comp, y, kind="decimal")
        G = [_dec(v) for v in invariant_values]
        free = [i for i, s in enumerate(STATES) if s not in pinned]
        # rows replaced by invariants: pick distinct states with nonzero weight
        replaced = []
        for law in laws:
            for s in ("dPsi", "Mg_x", "K_x", "mATP_x", "mADP_x", "H_x"):
                if s in law and STATES.index(s) not in replaced and s not in pinned:
                    replaced.append(STATES.index(s))
                    break
        Pd = {k: _dec(v) for k, v in comp.params.items()}
        wlaws = [{STATES.index(s): Decimal(w.numerator) / Decimal(w.denominator) for s, w in law.items()}
                 for law in laws]
        scale = [max(abs(v), Decimal("1e-9")) for v in y]
        scale[STATES.index("H_x")] = Decimal("1e-8")
        scale[STATES.index("dPsi")] = Decimal(100)

        def amount_d(i, v):
            s = STATES[i]
            if s == "H_x":
                return Pd["V_x"] * v.ln() / Pd["rbuff_coeff"]
            return Pd[rows[s]["volume"]] * v

        def F(yv):
            d = f(yv, hd)[0]
            out = []
            for i in free:
                if i in replaced:
                    k = replaced.index(i)
                    out.append(sum(w * amount_d(j, yv[j]) for j, w in wlaws[k].items()) - G[k])
                else:
                    out.append(d[i])
            return out

        it = 0
        for it in range(1, max_iter + 1):
            Fy = F(y)
            # Jacobian by central differences (Decimal, relative step 1e-20)
            J = [[Decimal(0)] * len(free) for _ in free]
            for c, i in enumerate(free):
                hstep = scale[i] * Decimal("1e-20")
                yp = y[:]
                ym = y[:]
                yp[i] += hstep
                ym[i] -= hstep
                Fp, Fm = F(yp), F(ym)
                for r in range(len(free)):
                    J[r][c] = (Fp[r] - Fm[r]) / (2 * hstep)
            dx = _solve_dec(J, [-v for v in Fy])
            lam = Decimal(1)
            for _ in range(60):
                yn = y[:]
                for c, i in enumerate(free):
                    yn[i] = y[i] + lam * dx[c]
                if all(yn[STATES.index(s)] > 0 for s in ("H_x", "QH2_x", "NADH_x", "cytCred", "K_x")) and \
                        yn[STATES.index("QH2_x")] < Pd["Q_tot"] and yn[STATES.index("NADH_x")] < Pd["NAD_tot"] and \
                        yn[STATES.index("cytCred")] < Pd["cytC_tot"]:
                    try:
                        F(yn)
                        break
                    except ArithmeticError:
                        pass
                lam /= 2
            else:
                raise ArithmeticError("Newton: no admissible step")
            y = yn
            step = max(abs(lam * dx[c]) / scale[i] for c, i in enumerate(free))
            if step < Decimal(10) ** tol_exp:
                break
        else:
            raise ArithmeticError(f"Newton: no convergence in {max_iter} iterations")
        d = f(y, hd)[0]
        res = max(abs(d[i]) / (scale[i] if STATES[i] != "dPsi" else Decimal(1)) for i in free)
        _, inv_now = invariants(comp, y, kind="decimal")
        return SteadyState(y=y, residual=res, iterations=it, invariant_values=inv_now, pinned=tuple(pinned))
