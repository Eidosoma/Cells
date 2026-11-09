"""MG0a: a decaying morphogen from a source on fixed tissue (reaction_transport@1).

Engine model run: reaction_transport@1 (src/cells/models/reaction_transport.py),
unmodified. Species A is the morphogen: it moves on cell contacts and decays
irreversibly to an immobile product B (forward rate k, reverse rate 0, B
permeability 0). The source is one large-volume reservoir cell holding A, with
no decay, coupled to the tissue by ordinary contacts. reaction_transport@1 has
no source term, so the reservoir drains slowly; its drain rate mu is part of
the exact discrete solution below rather than an error.

Geometry (two-point flux finite volumes, cells of height HEIGHT_UM):
  strip    n cells of width a in a row; V = a^2 h, g = D a h / a = D h, so
           g/V = D/a^2 and the continuum length is lambda = sqrt(D/k). The
           reservoir is the strip's cell 0 (centre x = 0, same contact g).
  polygon  Voronoi cells of a jittered hexagonal lattice (seeded); g = D h l/d
           for a shared edge of length l between generators d apart.

References, all computed here with numpy/scipy, never with Cells code:
  quasi-steady  the slowest eigenmode of the discrete linear system (finite
                reservoir included): its rate mu solves a scalar secular
                equation; its tissue shape phi (phi = 1 at the reservoir) is a
                sparse direct solve. RK4 maps share L's eigenvectors, so the
                engine's late profile c/c_reservoir must equal phi to round-off
                once the other modes (rates >= k) have decayed.
  Dirichlet     the same solve at mu = 0 (a held source), reported only.
  transient     exact piecewise solution x(t) = V^1/2 Q exp(Lambda t) Q^T V^-1/2
                x0 by symmetric eigendecomposition, including the decay and
                contact ledgers, for the time-step study and cut-and-restore.
  continuum     lambda = sqrt(D/k); the strip's exact discrete exponent is
                theta = arccosh(1 + (k - mu) a^2 / (2 D)), lambda_d = a/theta,
                lambda_d / lambda - 1 ~ (a/lambda)^2 / 24.

Literature values (Kicheva et al. 2007, Science 315:521, wing-disc Dpp; record
C1c in morphogenesis-plan-20261109-01/research-verified.json): lambda =
20.2 +/- 5.7 um (7.7 cells), D = 0.10 um^2/s, k = 2.52e-4 1/s. The model inputs
are D and k; sqrt(D/k) = 19.92 um. The measured 20.2 um is context, not a
criterion.

Cut and restore: reaction_transport@1 has no excision or replacement event
contract (core/excision.py dispatches surface_* families only). A cut is
therefore modelled as closing every contact across a cut line
(prescribed_contact_open_fractions), and restore as reopening them. This is
isolation, not removal; the linear steady state is unique, so the arm checks
machinery only (docs/MORPHOGENESIS_PLAN.md).

Usage:
  python -m validation.morphogenesis.mg0a_gradient PART [PART ...] --output DIR
      [--protocol FILE]
  PART: strip scaling refinement timestep polygon cut   (or: all)
"""

import argparse
import json
import math
import resource
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import linalg, optimize, sparse
from scipy.sparse import linalg as sparse_linalg
from scipy.spatial import Voronoi

MODEL_ID = "reaction_transport@1"
KICHEVA_2007 = dict(
    citation="Kicheva et al. 2007, Science 315:521-525, doi:10.1126/science.1135774",
    lambda_um=20.2,
    lambda_um_sd=5.7,
    lambda_cells=7.7,
    D_um2_s=0.10,
    k_per_s=2.52e-4,
)
CELL_WIDTH_UM = KICHEVA_2007["lambda_um"] / KICHEVA_2007["lambda_cells"]
HEIGHT_UM = 10.0  # Cancels from every profile; fixes amounts only.
UM3_PER_PL = 1.0e3
SOURCE_VOLUME_PL = 1.0e6
SOURCE_CONCENTRATION = 1.0  # fmol/pL (1 mM); the system is linear.
RELAXATION_RATES = 40.0  # Horizon in units of 1/k: other modes decay by e^-40.
STABILITY_FRACTION = 0.5  # reaction_transport@1 admits h * alpha <= 0.5.
SEGMENT_STEPS = 8192  # Accepted-trace window per runner call (memory bound).


@dataclass(frozen=True)
class Graph:
    """Cell 0 is the reservoir. Volumes pL, conductances pL/s, rates 1/s, um."""

    volume: np.ndarray
    edges: np.ndarray  # (m, 2) from, to
    conductance: np.ndarray
    rate: np.ndarray
    position: np.ndarray  # (n, 2) um; the reservoir sits at x = 0
    kind: str
    meta: dict

    @property
    def n(self):
        return len(self.volume)


def strip(cells, *, width_um=CELL_WIDTH_UM, D=KICHEVA_2007["D_um2_s"],
          k=KICHEVA_2007["k_per_s"], height_um=HEIGHT_UM):  # fmt: skip
    """A one-cell-wide strip: reservoir (0) then cells 1..n at x = i a."""
    volume = np.full(cells + 1, width_um**2 * height_um / UM3_PER_PL)
    volume[0] = SOURCE_VOLUME_PL
    edges = np.array([(i, i + 1) for i in range(cells)], dtype=np.int64).reshape(-1, 2)
    g = np.full(cells, D * height_um / UM3_PER_PL)
    rate = np.full(cells + 1, k)
    rate[0] = 0.0
    position = np.stack([width_um * np.arange(cells + 1), np.zeros(cells + 1)], axis=1)
    meta = dict(cells=cells, width_um=width_um, D_um2_s=D, k_per_s=k, height_um=height_um)
    return Graph(volume, edges, g, rate, position, "strip", meta)


def _polygon_area(points):
    x, y = points[:, 0], points[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def polygon(*, rows=12, cols=40, seed=0, jitter=0.2, spacing_um=CELL_WIDTH_UM,
            D=KICHEVA_2007["D_um2_s"], k=KICHEVA_2007["k_per_s"], height_um=HEIGHT_UM):  # fmt: skip
    """Voronoi tissue of a jittered hexagonal lattice; source along the left edge.

    Generators are laid out with one extra frame row/column on every side; the
    tissue is the rows x cols interior cells, whose regions are all bounded.
    Leftmost-column cells couple to the reservoir with g = D h s_row / s.
    """
    rng = np.random.default_rng(seed)
    row_pitch = spacing_um * math.sqrt(3) / 2
    pts, interior, first_column = [], [], []
    for j in range(-2, rows + 2):
        for i in range(-2, cols + 2):
            pts.append(((i + 0.5 * (j % 2)) * spacing_um, j * row_pitch))
            interior.append(0 <= i < cols and 0 <= j < rows)
            first_column.append(i == 0 and 0 <= j < rows)
    pts = np.asarray(pts) + rng.uniform(-jitter, jitter, size=(len(pts), 2)) * spacing_um
    interior = np.asarray(interior)
    vor = Voronoi(pts)
    tissue = np.flatnonzero(interior)
    slot = {int(p): s + 1 for s, p in enumerate(tissue)}
    volume = [SOURCE_VOLUME_PL]
    for p in tissue:
        region = vor.regions[vor.point_region[p]]
        if -1 in region or not region:
            raise ValueError("Interior Voronoi region is unbounded; enlarge the frame")
        volume.append(_polygon_area(vor.vertices[region]) * height_um / UM3_PER_PL)
    edges, g = [], []
    for (p, q), verts in zip(vor.ridge_points, vor.ridge_vertices, strict=True):
        if int(p) in slot and int(q) in slot:
            if -1 in verts:
                raise ValueError("Interior ridge is unbounded")
            length = float(np.hypot(*(vor.vertices[verts[0]] - vor.vertices[verts[1]])))
            distance = float(np.hypot(*(pts[p] - pts[q])))
            a, b = sorted((slot[int(p)], slot[int(q)]))
            edges.append((a, b))
            g.append(D * height_um * length / distance / UM3_PER_PL)
    x_min = pts[tissue, 0].min()
    left = [slot[int(p)] for p in np.flatnonzero(first_column)]
    for s in left:
        edges.append((0, s))
        g.append(D * height_um * row_pitch / spacing_um / UM3_PER_PL)
    order = np.lexsort((np.asarray(edges)[:, 1], np.asarray(edges)[:, 0]))
    edges = np.asarray(edges, dtype=np.int64)[order]
    g = np.asarray(g)[order]
    rate = np.full(len(volume), k)
    rate[0] = 0.0
    position = np.vstack([[x_min - spacing_um, 0.0], pts[tissue]])
    meta = dict(rows=rows, cols=cols, seed=seed, jitter=jitter, spacing_um=spacing_um,
                D_um2_s=D, k_per_s=k, height_um=height_um, source_cells=len(left))  # fmt: skip
    return Graph(np.asarray(volume), edges, g, rate, position, "polygon", meta)


def max_exit_rate(graph, opening=None):
    o = np.ones(len(graph.edges)) if opening is None else np.asarray(opening)
    loss = graph.rate.copy()
    w = graph.conductance * o
    np.add.at(loss, graph.edges[:, 0], w / graph.volume[graph.edges[:, 0]])
    np.add.at(loss, graph.edges[:, 1], w / graph.volume[graph.edges[:, 1]])
    return float(loss.max())


def stable_dt(graph, *, fraction=0.4):
    """Largest power-of-two step (s) with h * alpha <= fraction (admitted at 0.5)."""
    return 2.0 ** math.floor(math.log2(fraction / max_exit_rate(graph)))


def definition(graph, *, end_time, dt, observation_times, schedule=None):
    """A complete reaction_transport@1 definition (JSON-ready dict).

    schedule: [(time, open_fractions)] with the first entry at time 0; default
    all contacts open throughout.
    """
    n, m = graph.n, len(graph.edges)
    ids = [1000 + i for i in range(n)]
    amount_a = np.zeros(n)
    amount_a[0] = SOURCE_CONCENTRATION * graph.volume[0]
    schedule = [(0.0, np.ones(m))] if schedule is None else schedule
    steps = int(math.ceil(end_time / dt)) + len(schedule) + 8
    return dict(
        schema_version=1,
        model=dict(
            id=MODEL_ID,
            units=dict(amount="fmol", volume="pL", time="s"),
            species=["A", "B"],
            population=dict(count=n, cell_ids=ids),
            initial_state=dict(amount=[amount_a.tolist(), [0.0] * n], volume=graph.volume.tolist()),
            parameters=dict(
                reaction=dict(
                    from_species="A",
                    to_species="B",
                    forward_rate=graph.rate.tolist(),
                    reverse_rate=[0.0] * n,
                ),
                contacts=[
                    dict(
                        contact_id=1 + e,
                        from_cell_id=ids[int(a)],
                        to_cell_id=ids[int(b)],
                        permeability=[float(g), 0.0],
                    )
                    for e, ((a, b), g) in enumerate(
                        zip(graph.edges, graph.conductance, strict=True)
                    )
                ],
            ),
        ),
        experiment=dict(
            end_time=float(end_time),
            source=dict(kind="none"),
            contact=dict(
                kind="prescribed_contact_open_fractions",
                contact_ids=[1 + e for e in range(m)],
                schedule=[
                    dict(time=float(t), open_fractions=[float(v) for v in o]) for t, o in schedule
                ],
            ),
            observation_times=[float(t) for t in observation_times],
        ),
        execution=dict(
            backend="cpu",
            precision="float64",
            solver="rk4",
            dt=float(dt),
            capacity=n,
            edge_capacity=m,
            jit=True,
            max_steps=steps,
            max_trace_bytes=2**40,  # Admission only; segments bound real storage.
        ),
    )


def run_segmented(raw, *, segment_steps=SEGMENT_STEPS):
    """Run a definition in horizon windows, keeping observations and diagnostics.

    Each window is a runner branch of the same definition with a later end time
    (core/runner.branch_checkpoint): model, execution, past controls unchanged.
    Window ends are multiples of dt, so they lie on the shared grid.
    """
    from cells.core.runner import branch_checkpoint, run
    from cells.core.specs import parse_spec

    end, dt = raw["experiment"]["end_time"], raw["execution"]["dt"]
    observe = sorted(raw["experiment"]["observation_times"])
    ends, step = [], segment_steps
    while step * dt < end:
        ends.append(step * dt)
        step += segment_steps
    ends.append(end)
    previous, checkpoint = None, None
    out = dict(times=[], A=[], B=[], transferred=[], converted=[])
    diagnostics, timings = [], dict(execute_seconds=0.0, total_run_seconds=0.0)
    start = 0.0
    for stop in ends:
        window = json.loads(json.dumps(raw))
        window["experiment"]["end_time"] = stop
        window["experiment"]["observation_times"] = [t for t in observe if t <= stop] or [stop]
        contact = window["experiment"]["contact"]
        contact["schedule"] = [c for c in contact["schedule"] if c["time"] <= stop]
        spec = parse_spec(window)
        if checkpoint is not None:
            checkpoint = branch_checkpoint(previous, checkpoint, spec)
        value = run(spec, checkpoint)
        obs = value.observations
        for i, t in enumerate(obs.times):
            if (t > start or (start == 0.0 and t == 0.0)) and t in observe:
                out["times"].append(float(t))
                out["A"].append(np.asarray(obs.amount[i, 0]))
                out["B"].append(np.asarray(obs.amount[i, 1]))
                out["transferred"].append(np.asarray(obs.transferred[i, 0]))
                out["converted"].append(np.asarray(obs.converted[i]))
        diagnostics.append(dict(value.diagnostics))
        for key in timings:
            timings[key] += float(value.timings.get(key, 0.0))
        previous, checkpoint, start = spec, value.final, stop
    out = {k: (v if k == "times" else np.asarray(v)) for k, v in out.items()}
    worst = {
        k: max(d[k] for d in diagnostics)
        for k in ("max_balance_error_fmol", "max_process_accounting_error_fmol")
    }
    return out, dict(runtime_checks=worst, windows=len(ends), **timings)


# ---------------------------------------------------------------- references


def _matrix(graph, opening=None):
    """Concentration generator M (V dc/dt = M c), sparse CSR."""
    o = np.ones(len(graph.edges)) if opening is None else np.asarray(opening)
    w = graph.conductance * o
    a, b = graph.edges[:, 0], graph.edges[:, 1]
    n = graph.n
    off = sparse.coo_matrix(
        (np.concatenate([w, w]), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(n, n)
    )
    degree = np.zeros(n)
    np.add.at(degree, a, w)
    np.add.at(degree, b, w)
    return (off - sparse.diags(degree + graph.rate * graph.volume)).tocsr()


def quasi_steady(graph, opening=None):
    """Slowest mode: rate mu and shape phi (phi[0] = 1) of the discrete system.

    (M + mu V) phi = 0 with phi_0 = 1: the tissue rows are a sparse solve; the
    reservoir row is the secular equation F(mu) = mu V_0 + (M phi)_0 = 0.
    """
    M = _matrix(graph, opening)
    V = graph.volume
    tt = M[1:, 1:].tocsc()
    tr = np.asarray(M[1:, 0].todense()).ravel()
    row = M[0, :]

    def shape(mu):
        lhs = (tt + sparse.diags(mu * V[1:])).tocsc()
        return np.concatenate([[1.0], sparse_linalg.spsolve(lhs, -tr)])

    def secular(mu):
        return mu * V[0] + float((row @ shape(mu))[0])

    k_min = float(graph.rate[1:].min())
    if secular(0.0) >= 0:
        mu = 0.0
    else:
        mu = optimize.brentq(
            secular, 0.0, 0.5 * k_min, xtol=1e-300, rtol=4 * np.finfo(float).eps, maxiter=500
        )
    return mu, shape(mu), shape(0.0)


class Transient:
    """Exact solution of the linear system under piecewise-constant openings."""

    def __init__(self, graph, schedule=None):
        self.graph = graph
        m = len(graph.edges)
        self.schedule = [(0.0, np.ones(m))] if schedule is None else list(schedule)
        self._eig = {}

    def _modes(self, opening):
        key = tuple(np.asarray(opening, float))
        if key not in self._eig:
            s = 1.0 / np.sqrt(self.graph.volume)
            M = _matrix(self.graph, opening).toarray()
            lam, q = linalg.eigh(s[:, None] * M * s[None, :])
            self._eig[key] = (lam, q)
        return self._eig[key]

    def solve(self, times):
        """Amounts A, B and A contact ledgers at sorted times, from the reservoir start."""
        g = self.graph
        s = np.sqrt(g.volume)
        y = np.zeros(g.n)
        y[0] = SOURCE_CONCENTRATION * g.volume[0] / s[0]
        b = np.zeros(g.n)
        ledger = np.zeros(len(g.edges))
        t_now, out = 0.0, dict(A=[], B=[], transferred=[])
        bounds = [t for t, _ in self.schedule[1:]]
        for t_target in times:
            while True:
                idx = int(np.searchsorted(bounds, t_now, side="right"))
                opening = self.schedule[idx][1]
                t_next = bounds[idx] if idx < len(bounds) else math.inf
                step_to = min(t_target, t_next)
                tau = step_to - t_now
                if tau > 0:
                    lam, q = self._modes(opening)
                    z = q.T @ y
                    lt = lam * tau
                    phi1 = np.where(
                        np.abs(lt) < 1e-12,
                        tau * (1 + lt / 2),
                        np.expm1(lt) / np.where(lam == 0, 1, lam),
                    )
                    integral_y = q @ (phi1 * z)
                    y = q @ (np.exp(lt) * z)
                    integral_c = integral_y / s
                    b += g.rate * g.volume * integral_c
                    w = g.conductance * np.asarray(opening)
                    ledger += w * (integral_c[g.edges[:, 0]] - integral_c[g.edges[:, 1]])
                    t_now = step_to
                if t_now >= t_target:
                    break
            out["A"].append(y * s)
            out["B"].append(b.copy())
            out["transferred"].append(ledger.copy())
        return {k: np.asarray(v) for k, v in out.items()}


# ---------------------------------------------------------------- analysis


def strip_exponent(graph, mu=0.0):
    """Exact discrete decay length a/theta of the strip (um)."""
    meta = graph.meta
    eps = (meta["k_per_s"] - mu) * meta["width_um"] ** 2 / meta["D_um2_s"]
    return meta["width_um"] / math.acosh(1 + eps / 2)


def three_point_lambda(c, width):
    """a/arccosh((c[i-1] + c[i+1]) / (2 c[i])) over interior strip cells."""
    ratio = (c[:-2] + c[2:]) / (2 * c[1:-1])
    return width / np.arccosh(ratio)


def cosh_fit(c, width):
    """Least-squares fit of C0 cosh((L - x)/lambda)/cosh(L/lambda), L = (n + 1/2) a.

    c excludes the reservoir; x = i a for i = 1..n. Relative residuals.
    """
    n = len(c)
    x = width * np.arange(1, n + 1)
    big = (n + 0.5) * width

    def model(p):
        c0, lam = p
        return (
            c0
            * np.exp(-x / lam)
            * (1 + np.exp(-2 * (big - x) / lam))
            / (1 + np.exp(-2 * big / lam))
        )

    guess = (c[0] * math.exp(width / 7.0), -width / math.log(c[1] / c[0]))
    fit = optimize.least_squares(
        lambda p: model(p) / c - 1, guess, xtol=1e-15, ftol=1e-15, gtol=1e-15, method="lm"
    )
    return dict(
        C0=float(fit.x[0]),
        lambda_um=float(fit.x[1]),
        max_rel_residual=float(np.max(np.abs(fit.fun))),
    )


def ledger_checks(graph, result):
    """Driver-side mass and ledger identities on the engine's observations."""
    A, B, T, X = result["A"], result["B"], result["transferred"], result["converted"]
    received = np.zeros_like(A)
    np.add.at(received, (slice(None), graph.edges[:, 0]), -T)
    np.add.at(received, (slice(None), graph.edges[:, 1]), T)
    initial = np.zeros(graph.n)
    initial[0] = SOURCE_CONCENTRATION * graph.volume[0]
    # Per cell: A change = receipts - conversion; B change = conversion (B is immobile).
    cell_a = A - initial - received + X
    cell_b = B - X
    scale = np.maximum(np.abs(received) + np.abs(X), np.finfo(float).tiny)
    tissue = slice(1, None)
    source_edges = (graph.edges[:, 0] == 0) | (graph.edges[:, 1] == 0)
    inflow = np.where(graph.edges[source_edges, 0] == 0, 1.0, -1.0) @ T[:, source_edges].T
    tissue_mass = A[:, tissue].sum(axis=1) + B[:, tissue].sum(axis=1)
    late = np.asarray(result["times"]) > 0
    rel_tissue = np.abs(tissue_mass - inflow)[late] / np.abs(inflow)[late]
    total = A.sum(axis=1) + B.sum(axis=1)
    return dict(
        tissue_mass_balance_rel_max=float(rel_tissue.max()),
        cell_ledger_rel_max=float(np.max(np.abs(cell_a[:, tissue]) / scale[:, tissue])),
        cell_product_ledger_rel_max=float(np.max(np.abs(cell_b[:, tissue]) / scale[:, tissue])),
        closed_world_total_rel_max=float(np.max(np.abs(total - initial.sum())) / initial.sum()),
        min_amount_fmol=float(min(A.min(), B.min())),
    )


def profile_checks(graph, result, opening=None, *, component=None):
    """Late engine profile against the exact quasi-steady and Dirichlet shapes."""
    mu, phi, dirichlet = quasi_steady(graph, opening)
    A = result["A"][-1]
    c = A / graph.volume
    shape = c / c[0]
    cells = np.arange(1, graph.n) if component is None else np.asarray(component)
    rel = np.abs(shape[cells] / phi[cells] - 1)
    norm = np.max(np.abs(shape[cells] - phi[cells])) / np.max(np.abs(phi[cells]))
    return (
        dict(
            drain_rate_mu_per_s=mu,
            mu_over_k=mu / float(graph.rate[1:].min()),
            profile_vs_exact_rel_max=float(rel.max()),
            profile_vs_exact_rel_argmax_cell=int(cells[int(np.argmax(rel))]),
            profile_vs_exact_normwise=float(norm),
            exact_shape_min=float(phi[cells].min()),
            dirichlet_vs_quasi_steady_rel_max=float(
                np.max(np.abs(dirichlet[cells] / phi[cells] - 1))
            ),
        ),
        shape,
        phi,
    )


def _strip_horizon(graph, dt):
    k = graph.meta["k_per_s"]
    steps = int(math.ceil(RELAXATION_RATES / k / dt))
    return steps * dt


def strip_case(graph, *, label):
    dt = stable_dt(graph)
    end = _strip_horizon(graph, dt)
    raw = definition(graph, end_time=end, dt=dt, observation_times=[0.0, end / 2, end])
    t0 = time.perf_counter()
    result, info = run_segmented(raw)
    checks, shape, phi = profile_checks(graph, result)
    width = graph.meta["width_um"]
    c = shape[1:]
    lam_cont = math.sqrt(graph.meta["D_um2_s"] / graph.meta["k_per_s"])
    three = three_point_lambda(shape, width)[1:]  # Interior cells 2..n-1.
    fit = cosh_fit(c, width)
    lam_d = strip_exponent(graph, checks["drain_rate_mu_per_s"])
    entry = dict(
        label=label,
        geometry=graph.meta,
        dt_s=dt,
        end_time_s=end,
        h_alpha=dt * max_exit_rate(graph),
        lambda_continuum_um=lam_cont,
        lambda_continuum_cells=lam_cont / width,
        lambda_discrete_exact_um=lam_d,
        lambda_three_point_um=dict(
            median=float(np.median(three)), min=float(three.min()), max=float(three.max())
        ),
        lambda_cosh_fit=fit,
        lambda_fit_vs_continuum_rel=fit["lambda_um"] / lam_cont - 1,
        lambda_fit_vs_discrete_rel=fit["lambda_um"] / lam_d - 1,
        predicted_discretisation_rel=(width / lam_cont) ** 2 / 24,
        lambda_vs_kicheva_measured_um=dict(
            model=fit["lambda_um"],
            measured=KICHEVA_2007["lambda_um"],
            sd=KICHEVA_2007["lambda_um_sd"],
        ),
        **checks,
        **ledger_checks(graph, result),
        run=info,
        wall_seconds=time.perf_counter() - t0,
    )
    return entry


# ---------------------------------------------------------------- parts

STRIP_CELLS = 64  # 8.4 continuum lengths at the Kicheva values.
SCALING_FACTORS = (0.25, 1.0, 4.0)  # D/k relative to Kicheva (lambda x0.5, x1, x2).
# Cell width 2a, a, a/2 on one physical strip (32, 64, 128 cells). A finer a/4
# level needs 3.2e5 RK4 steps over 40/k, where reaction_transport@1's
# step-count-independent balance guard (512 eps x total) refused the run on
# accumulated reservoir rounding (dev-01, morphogenesis-mg0-20261109-01).
REFINEMENT_LEVELS = (0.5, 1, 2)
TIMESTEP_LEVELS = (16.0, 8.0, 4.0, 2.0, 1.0)
# Early times: by 3600 s the transient errors reach the round-off floor (dev-02).
TIMESTEP_TIMES = (300.0, 600.0, 900.0)


def part_strip(args):
    return strip_case(strip(STRIP_CELLS), label="kicheva_strip")


def part_scaling(args):
    cases = []
    for factor in SCALING_FACTORS:
        D = KICHEVA_2007["D_um2_s"] * factor
        cells = int(round(STRIP_CELLS * math.sqrt(factor) * 1.25)) if factor > 1 else STRIP_CELLS
        cases.append(strip_case(strip(cells, D=D), label=f"D_over_k_x{factor:g}"))
    x = np.log([c["geometry"]["D_um2_s"] / c["geometry"]["k_per_s"] for c in cases])
    y = np.log([c["lambda_cosh_fit"]["lambda_um"] for c in cases])
    slope = float(np.polyfit(x, y, 1)[0])
    discrete = np.log([c["lambda_discrete_exact_um"] for c in cases])
    return dict(
        cases=cases,
        log_slope_lambda_vs_D_over_k=slope,
        log_slope_discrete_prediction=float(np.polyfit(x, discrete, 1)[0]),
        continuum_slope=0.5,
    )


def part_refinement(args):
    cases = []
    for level in REFINEMENT_LEVELS:
        cases.append(
            strip_case(
                strip(int(STRIP_CELLS * level), width_um=CELL_WIDTH_UM / level),
                label=f"a_over_{level:g}",
            )
        )
    errors = [abs(c["lambda_fit_vs_continuum_rel"]) for c in cases]
    orders = [
        math.log(errors[i] / errors[i + 1])
        / math.log(REFINEMENT_LEVELS[i + 1] / REFINEMENT_LEVELS[i])
        for i in range(len(errors) - 1)
    ]
    return dict(cases=cases, lambda_errors=errors, observed_orders=orders, expected_order=2.0)


def part_timestep(args):
    graph = strip(STRIP_CELLS)
    exact = Transient(graph).solve(list(TIMESTEP_TIMES))
    levels = []
    for dt in TIMESTEP_LEVELS:
        end = TIMESTEP_TIMES[-1]
        raw = definition(graph, end_time=end, dt=dt, observation_times=list(TIMESTEP_TIMES))
        result, info = run_segmented(raw)
        tissue = slice(1, None)
        errs = []
        for i in range(len(TIMESTEP_TIMES)):
            ref = exact["A"][i][tissue]
            errs.append(float(np.max(np.abs(result["A"][i][tissue] - ref)) / np.max(np.abs(ref))))
        levels.append(
            dict(dt_s=dt, h_alpha=dt * max_exit_rate(graph), normwise_rel_error=errs, run=info)
        )
    orders = []
    for i in range(len(levels) - 1):
        row = []
        for j in range(len(TIMESTEP_TIMES)):
            a, b = levels[i]["normwise_rel_error"][j], levels[i + 1]["normwise_rel_error"][j]
            row.append(math.log2(a / b) if a > 0 and b > 0 else None)
        orders.append(row)
    finest = [e for lv in levels[-3:] for e in lv["normwise_rel_error"]]
    return dict(
        times_s=list(TIMESTEP_TIMES),
        levels=levels,
        observed_orders=orders,
        expected_order=4.0,
        finest_pairs_min_error=float(min(finest)),
    )


def part_polygon(args):
    graph = polygon()
    dt = stable_dt(graph)
    end = int(math.ceil(RELAXATION_RATES / graph.meta["k_per_s"] / dt)) * dt
    raw = definition(graph, end_time=end, dt=dt, observation_times=[0.0, end / 2, end])
    t0 = time.perf_counter()
    result, info = run_segmented(raw)
    checks, shape, phi = profile_checks(graph, result)
    # Diagnostic only: effective decay length from ln(c) against x in the interior.
    x = graph.position[1:, 0] - graph.position[1:, 0].min()
    lam = math.sqrt(graph.meta["D_um2_s"] / graph.meta["k_per_s"])
    window = (x > lam) & (x < 3 * lam)
    slope = np.polyfit(x[window], np.log(shape[1:][window]), 1)[0]
    return dict(
        geometry=graph.meta,
        cells=graph.n - 1,
        contacts=len(graph.edges),
        dt_s=dt,
        end_time_s=end,
        h_alpha=dt * max_exit_rate(graph),
        **checks,
        **ledger_checks(graph, result),
        diagnostic_effective_lambda_um=float(-1 / slope),
        lambda_continuum_um=lam,
        run=info,
        wall_seconds=time.perf_counter() - t0,
    )


CUT_AT_CELL = 12  # Close the contact between strip cells 12 and 13.


def part_cut(args):
    """Machinery check on the Kicheva strip: no cut, cut without restore, cut and restore."""
    graph = strip(STRIP_CELLS)
    dt = stable_dt(graph)
    k = graph.meta["k_per_s"]
    t_cut = int(math.ceil(RELAXATION_RATES / k / dt)) * dt
    t_restore = t_cut + int(math.ceil(5 / k / dt)) * dt
    end = t_restore + int(math.ceil(RELAXATION_RATES / k / dt)) * dt
    m = len(graph.edges)
    open_ = np.ones(m)
    cut = open_.copy()
    cut_edge = int(
        np.flatnonzero((graph.edges[:, 0] == CUT_AT_CELL) & (graph.edges[:, 1] == CUT_AT_CELL + 1))[
            0
        ]
    )
    cut[cut_edge] = 0.0
    arms = dict(
        no_cut=[(0.0, open_), (t_cut, open_)],
        cut_without_restore=[(0.0, open_), (t_cut, cut)],
        cut_and_restore=[(0.0, open_), (t_cut, cut), (t_restore, open_)],
    )
    observe = [0.0, t_cut, t_cut + 1 / k, t_restore, t_restore + 1 / k, end]
    observe = [round(t / dt) * dt for t in observe]
    report = dict(
        t_cut_s=t_cut,
        t_restore_s=t_restore,
        end_time_s=end,
        dt_s=dt,
        cut_edge=[CUT_AT_CELL, CUT_AT_CELL + 1],
        arms={},
    )
    proximal = np.arange(1, CUT_AT_CELL + 1)
    distal = np.arange(CUT_AT_CELL + 1, graph.n)
    for name, schedule in arms.items():
        raw = definition(graph, end_time=end, dt=dt, observation_times=observe, schedule=schedule)
        result, info = run_segmented(raw)
        exact = Transient(graph, schedule).solve(result["times"])
        tissue = slice(1, None)
        transient_err = []
        for i, t in enumerate(result["times"]):
            if t == 0.0:
                continue  # Both are exactly zero in the empty tissue at t = 0.
            ref = exact["A"][i][tissue]
            diff = np.max(np.abs(result["A"][i][tissue] - ref))
            transient_err.append(float(diff / np.max(np.abs(ref))))
        final_opening = schedule[-1][1]
        component = proximal if name == "cut_without_restore" else None
        checks, shape, phi = profile_checks(graph, result, final_opening, component=component)
        entry = dict(
            observation_times_s=result["times"],
            transient_normwise_rel_error=transient_err,
            **checks,
            **ledger_checks(graph, result),
            run=info,
        )
        if name == "cut_without_restore":
            c = result["A"][-1] / graph.volume
            entry["distal_max_over_source"] = float(np.max(c[distal]) / c[0])
            entry["distal_exact_max_over_source"] = float(
                np.max(exact["A"][-1][distal] / graph.volume[distal]) / c[0]
            )
        entry["_final_shape"] = shape
        report["arms"][name] = entry
    shapes = {k: v.pop("_final_shape") for k, v in report["arms"].items()}
    report["restored_vs_uncut_final_rel_max"] = float(
        np.max(np.abs(shapes["cut_and_restore"][1:] / shapes["no_cut"][1:] - 1))
    )
    return report


PARTS = dict(
    strip=part_strip,
    scaling=part_scaling,
    refinement=part_refinement,
    timestep=part_timestep,
    polygon=part_polygon,
    cut=part_cut,
)


# ---------------------------------------------------------------- judging


def _lookup(results, path):
    value = results
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def evaluate(protocol, results):
    """Apply a protocol's criteria (metric path, comparison, threshold) to results."""
    verdicts = []
    for c in protocol["criteria"]:
        values = []
        for path in c["metrics"]:
            try:
                values.append(_lookup(results, path))
            except (KeyError, IndexError, TypeError):
                values.append(None)
        flat = []
        for v in values:
            flat.extend(v if isinstance(v, list) else [v])
        if any(v is None for v in flat):
            ok = False
        elif c["comparison"] == "abs_le":
            ok = all(abs(v) <= c["threshold"] for v in flat)
        elif c["comparison"] == "le":
            ok = all(v <= c["threshold"] for v in flat)
        elif c["comparison"] == "ge":
            ok = all(v >= c["threshold"] for v in flat)
        elif c["comparison"] == "within":
            lo, hi = c["threshold"]
            ok = all(lo <= v <= hi for v in flat)
        else:
            raise ValueError(f"Unknown comparison {c['comparison']}")
        verdicts.append(
            dict(id=c["id"], judged=c.get("judged", True), passed=bool(ok), values=flat)
        )
    judged = [v for v in verdicts if v["judged"]]
    return dict(passed=all(v["passed"] for v in judged), criteria=verdicts)


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def main(argv=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="+", choices=[*PARTS, "all"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    parts = list(PARTS) if "all" in args.parts else args.parts
    results, failures = {}, {}
    for part in parts:
        t0 = time.perf_counter()
        try:
            results[part] = PARTS[part](args)
            results[part]["part_wall_seconds"] = time.perf_counter() - t0
        except Exception as error:  # Preserve the failure as evidence.
            failures[part] = dict(error=repr(error), traceback=traceback.format_exc())
        print(
            f"{part}: {'ok' if part in results else 'FAILED'} in {time.perf_counter() - t0:.1f} s",
            flush=True,
        )
    report = dict(
        kind="cells.morphogenesis_mg0a_results@1",
        engine_model=MODEL_ID,
        parts=_jsonable(results),
        failures=failures,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    if args.protocol is not None:
        protocol = json.loads(args.protocol.read_text())
        report["protocol_id"] = protocol["id"]
        report["verdict"] = (
            evaluate(protocol, report["parts"])
            if not failures
            else dict(passed=False, reason="part failures")
        )
    path = args.output / "results.json"
    with path.open("x") as stream:
        json.dump(report, stream, indent=1)
    if failures:
        (args.output / "failure.json").write_text(json.dumps(failures, indent=1))
    print(path)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
