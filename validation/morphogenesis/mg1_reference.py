"""MG1 independent reference: the Farhadifar vertex energy in numpy/scipy.

No Cells code is imported; only the definition JSON of apical_vertex_mechanics@1 is
shared. The reference has its own parsing of that JSON, its own geometry, a
closed-form gradient (not automatic differentiation), a Hessian from central
differences of that gradient, scipy minimizers and a box stress from finite
affine strains. It is the comparison target for the engine's energies, forces,
relaxed states, moduli, barriers and recoil responses.

Energy (Farhadifar et al. 2007, Curr Biol 17:2095, Box 1):
    E = sum_c K_c/2 (A_c - A0_c)^2 + sum_j Lambda_j l_j + sum_c Gamma_c/2 L_c^2.
Closed-form derivatives for a counterclockwise polygon with unwrapped corners
u_k = x[v_k] + B n_k:
    dl_k/du_k = -e_k, dl_k/du_{k+1} = +e_k   (e_k the unit edge vector u_k -> u_{k+1})
    dA/du_k = 1/2 (y_{k+1} - y_{k-1}, x_{k-1} - x_{k+1})
Periodic images are constant shifts, so derivatives with respect to u_k are those
with respect to x[v_k].
"""

from dataclasses import dataclass, replace

import numpy as np
from scipy import optimize


@dataclass(frozen=True)
class Tissue:
    box: np.ndarray  # [2, 2], columns are periodic vectors
    position: np.ndarray  # [V, 2]
    friction: np.ndarray  # [V]
    junction_tail: np.ndarray
    junction_head: np.ndarray
    junction_image: np.ndarray  # [J, 2]
    cell_vertices: tuple  # per cell: int array of corner vertices
    cell_images: tuple  # per cell: [n, 2] corner images
    line_tension: np.ndarray  # [J]
    contractility: np.ndarray  # [C]
    area_elasticity: np.ndarray  # [C]
    preferred_area: np.ndarray  # [C]
    vertex_ids: tuple
    junction_ids: tuple
    cell_ids: tuple
    cell_edge_junctions: tuple  # per cell: junction index of the edge from corner k to k+1

    @property
    def cells(self):
        return len(self.cell_vertices)


def from_definition(definition, control=None):
    """Arrays from a definition dict; control overrides one parameter_controls entry."""
    m = definition["model"]
    vid = [v["id"] for v in m["vertices"]]
    slot = {v: i for i, v in enumerate(vid)}
    junctions, cells = m["junctions"], m["cells"]
    tissue = Tissue(
        box=np.array(m["periods"], dtype=float).T,
        position=np.array([v["position"] for v in m["vertices"]], dtype=float),
        friction=np.array([v["friction"] for v in m["vertices"]], dtype=float),
        junction_tail=np.array([slot[j["vertices"][0]] for j in junctions]),
        junction_head=np.array([slot[j["vertices"][1]] for j in junctions]),
        junction_image=np.array([j["image"] for j in junctions], dtype=float),
        cell_vertices=tuple(np.array([slot[k["vertex"]] for k in c["corners"]]) for c in cells),
        cell_images=tuple(np.array([k["image"] for k in c["corners"]], dtype=float) for c in cells),
        line_tension=np.array([j["line_tension"] for j in junctions], dtype=float),
        contractility=np.array([c["contractility"] for c in cells], dtype=float),
        area_elasticity=np.array([c["area_elasticity"] for c in cells], dtype=float),
        preferred_area=np.array([c["preferred_area"] for c in cells], dtype=float),
        vertex_ids=tuple(vid),
        junction_ids=tuple(j["id"] for j in junctions),
        cell_ids=tuple(c["id"] for c in cells),
        cell_edge_junctions=_edge_junctions(m, slot),
    )
    if control is None:
        control = definition["experiment"]["parameter_controls"][0]
    return with_control(tissue, control)


def _edge_junctions(model, slot):
    declared = {}
    for i, j in enumerate(model["junctions"]):
        a, b, n = slot[j["vertices"][0]], slot[j["vertices"][1]], tuple(j["image"])
        declared[(a, b, *n)] = i
        declared[(b, a, -n[0], -n[1])] = i
    rows = []
    for c in model["cells"]:
        k = c["corners"]
        rows.append(
            np.array(
                [
                    declared[
                        (
                            slot[k[n]["vertex"]],
                            slot[k[(n + 1) % len(k)]["vertex"]],
                            k[(n + 1) % len(k)]["image"][0] - k[n]["image"][0],
                            k[(n + 1) % len(k)]["image"][1] - k[n]["image"][1],
                        )
                    ]
                    for n in range(len(k))
                ]
            )
        )
    return tuple(rows)


def with_control(tissue, control):
    """Apply one parameter_controls entry (overrides of the model's base values)."""
    jslot = {j: i for i, j in enumerate(tissue.junction_ids)}
    cslot = {c: i for i, c in enumerate(tissue.cell_ids)}
    values = {
        "line_tension": tissue.line_tension.copy(),
        "contractility": tissue.contractility.copy(),
        "area_elasticity": tissue.area_elasticity.copy(),
        "preferred_area": tissue.preferred_area.copy(),
    }
    for kind, mapping in values.items():
        slots = jslot if kind == "line_tension" else cslot
        for key, value in control.get(kind, {}).items():
            mapping[slots[key]] = value
    return replace(tissue, **values)


def corners(tissue, x, box=None):
    box = tissue.box if box is None else box
    return [x[v] + n @ box.T for v, n in zip(tissue.cell_vertices, tissue.cell_images, strict=True)]


def junction_vectors(tissue, x, box=None):
    box = tissue.box if box is None else box
    return x[tissue.junction_head] + tissue.junction_image @ box.T - x[tissue.junction_tail]


def shoelace(u):
    w = np.roll(u, -1, axis=0)
    return 0.5 * np.sum(u[:, 0] * w[:, 1] - w[:, 0] * u[:, 1])


def geometry(tissue, x, box=None):
    polys = corners(tissue, x, box)
    area = np.array([shoelace(u - u[0]) for u in polys])
    perimeter = np.array(
        [np.sum(np.linalg.norm(np.roll(u, -1, axis=0) - u, axis=1)) for u in polys]
    )
    length = np.linalg.norm(junction_vectors(tissue, x, box), axis=1)
    return area, perimeter, length


def energy(tissue, x, box=None):
    area, perimeter, length = geometry(tissue, x, box)
    t = tissue
    return float(
        np.sum(0.5 * t.area_elasticity * (area - t.preferred_area) ** 2)
        + np.sum(0.5 * t.contractility * perimeter**2)
        + np.sum(t.line_tension * length)
    )


def _units(vectors, keep):
    norms = np.linalg.norm(vectors, axis=1)
    safe = np.where(keep, norms, 1.0)
    return np.where(keep[:, None], vectors / safe[:, None], 0.0)


def gradient(tissue, x, fixed=None):
    """Closed-form dE/dx, [V, 2].

    fixed: a junction whose length is held constant (prescribed): its line term and
    its edges' perimeter derivatives are omitted (they vanish), so a junction
    contracted to exactly zero length has a finite gradient.
    """
    t = tissue
    g = np.zeros_like(x)
    keep = np.ones(len(t.line_tension), dtype=bool)
    if fixed is not None:
        keep[fixed] = False
    unit = _units(junction_vectors(t, x), keep)
    np.add.at(g, t.junction_head, t.line_tension[:, None] * unit)
    np.add.at(g, t.junction_tail, -t.line_tension[:, None] * unit)
    area, perimeter, _ = geometry(t, x)
    for c, (vertices, u) in enumerate(zip(t.cell_vertices, corners(t, x), strict=True)):
        following, previous = np.roll(u, -1, axis=0), np.roll(u, 1, axis=0)
        e = _units(following - u, t.cell_edge_junctions[c] != (-1 if fixed is None else fixed))
        d_perimeter = np.roll(e, 1, axis=0) - e  # incoming unit minus outgoing unit
        d_area = 0.5 * np.stack(
            [following[:, 1] - previous[:, 1], previous[:, 0] - following[:, 0]], axis=1
        )
        pressure = t.area_elasticity[c] * (area[c] - t.preferred_area[c])
        np.add.at(g, vertices, t.contractility[c] * perimeter[c] * d_perimeter + pressure * d_area)
    return g


def forces(tissue, x):
    return -gradient(tissue, x)


def hessian(tissue, x, step=1e-6):
    """Central differences of the closed-form gradient, symmetrized, [2V, 2V]."""
    flat = x.ravel()
    columns = []
    for k in range(flat.size):
        plus, minus = flat.copy(), flat.copy()
        plus[k] += step
        minus[k] -= step
        columns.append(
            (
                gradient(tissue, plus.reshape(x.shape)) - gradient(tissue, minus.reshape(x.shape))
            ).ravel()
            / (2 * step)
        )
    h = np.array(columns).T
    return 0.5 * (h + h.T)


def relax(tissue, x0, *, gtol=1e-13, maxiter=200000, polish=False):
    """L-BFGS with the closed-form gradient (and optionally a Newton polish).

    Returns (positions, max |F|, scipy result).
    """
    shape = x0.shape

    def fun(flat):
        x = flat.reshape(shape)
        return energy(tissue, x), gradient(tissue, x).ravel()

    result = optimize.minimize(
        fun,
        x0.ravel(),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": maxiter, "maxcor": 50, "gtol": gtol, "ftol": 1e-18},
    )
    x = result.x.reshape(shape)
    if polish:
        x = newton_polish(tissue, x)
    return x, float(np.max(np.abs(gradient(tissue, x)))), result


def _newton(gradient_of, hessian_of, z, iterations):
    """Newton steps (pseudo-inverse over nonzero modes) accepted while max |g| decreases.

    The acceptance test uses the gradient, not the energy: energies carry a large
    constant (Farhadifar's -N Gamma p0^2 / 2 in Staddon units), so their rounding
    floor stops energy-based line searches at gradients near 1e-7.
    """
    g = gradient_of(z)
    for _ in range(iterations):
        values, vectors = np.linalg.eigh(hessian_of(z))
        keep = np.abs(values) > 1e-9 * np.max(np.abs(values))
        step = vectors[:, keep] @ ((vectors[:, keep].T @ g) / values[keep])
        t = 1.0
        while t > 1e-4:
            trial = z - t * step
            g_trial = gradient_of(trial)
            if np.max(np.abs(g_trial)) < np.max(np.abs(g)):
                z, g = trial, g_trial
                break
            t *= 0.5
        else:
            break
    return z


def _fd_hessian(gradient_of, z, step=1e-6):
    columns = []
    for k in range(z.size):
        plus, minus = z.copy(), z.copy()
        plus[k] += step
        minus[k] -= step
        columns.append((gradient_of(plus) - gradient_of(minus)) / (2 * step))
    h = np.array(columns).T
    return 0.5 * (h + h.T)


def newton_polish(tissue, x, iterations=6):
    """Newton polish of a near minimum with the finite-difference Hessian."""
    shape = np.asarray(x).shape

    def grad(z):
        return gradient(tissue, z.reshape(shape)).ravel()

    return _newton(
        grad, lambda z: _fd_hessian(grad, z), np.asarray(x, float).ravel(), iterations
    ).reshape(shape)


def box_stress(tissue, x, strain=1e-6):
    """(1/det B) dE(x F^T, F B)/dF at F = I by central differences, [2, 2]."""
    stress = np.zeros((2, 2))
    for a in range(2):
        for b in range(2):
            values = []
            for sign in (1, -1):
                deformation = np.eye(2)
                deformation[a, b] += sign * strain
                values.append(energy(tissue, x @ deformation.T, deformation @ tissue.box))
            stress[a, b] = (values[0] - values[1]) / (2 * strain)
    return stress / np.linalg.det(tissue.box)


def velocity_jump(before, after, x):
    """v(0+) - v(0-) = (grad E_before - grad E_after) / eta, at the same positions."""
    return (gradient(before, x) - gradient(after, x)) / before.friction[:, None]


def self_check(tissue, x, step=1e-6):
    """Largest |closed-form gradient - central difference of the energy|."""
    flat = x.ravel()
    numeric = np.zeros_like(flat)
    for k in range(flat.size):
        plus, minus = flat.copy(), flat.copy()
        plus[k] += step
        minus[k] -= step
        numeric[k] = (
            energy(tissue, plus.reshape(x.shape)) - energy(tissue, minus.reshape(x.shape))
        ) / (2 * step)
    return float(np.max(np.abs(numeric - gradient(tissue, x).ravel())))


def place(tissue, x, junction, length, theta):
    """Positions with the junction's head at x_tail - B n + length (cos theta, sin theta)."""
    y = np.array(x, dtype=float)
    tail, head = tissue.junction_tail[junction], tissue.junction_head[junction]
    shift = tissue.junction_image[junction] @ tissue.box.T
    y[head] = y[tail] - shift + length * np.array([np.cos(theta), np.sin(theta)])
    return y


def path_energy_and_gradient(tissue, z, junction, length):
    """Energy and gradient in (positions, theta) with the junction's length prescribed."""
    x, theta = z[:-1].reshape(-1, 2), z[-1]
    y = place(tissue, x, junction, length, theta)
    g = gradient(tissue, y, fixed=junction)
    tail, head = tissue.junction_tail[junction], tissue.junction_head[junction]
    g[tail] += g[head]
    g_theta = g[head] @ (length * np.array([-np.sin(theta), np.cos(theta)]))
    g[head] = 0.0
    return energy(tissue, y), np.concatenate([g.ravel(), [g_theta]])


def contraction(tissue, x0, junction, fractions, *, gtol=1e-11, polish="none"):
    """Quasi-static contraction with scipy L-BFGS from a minimum x0.

    polish: "none", "end" (Newton polish of the last point; the barrier needs only
    E(last) - E(first), and the first point is x0 itself when fractions start at 1)
    or "all". Returns (energies, positions, initial length).
    """
    tail, head = tissue.junction_tail[junction], tissue.junction_head[junction]
    d = x0[head] + tissue.junction_image[junction] @ tissue.box.T - x0[tail]
    length0, theta = float(np.linalg.norm(d)), float(np.arctan2(d[1], d[0]))
    z = np.concatenate([np.asarray(x0, dtype=float).ravel(), [theta]])
    energies, positions = [], []
    for fraction in fractions:
        length = fraction * length0
        result = optimize.minimize(
            lambda w, length=length: path_energy_and_gradient(tissue, w, junction, length),
            z,
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": 200000, "maxcor": 50, "gtol": gtol, "ftol": 1e-20},
        )
        z = result.x
        if polish == "all" or (polish == "end" and fraction == fractions[-1]):

            def grad(w, length=length):
                return path_energy_and_gradient(tissue, w, junction, length)[1]

            z = _newton(grad, lambda w: _fd_hessian(grad, w), z, 6)
        energies.append(path_energy_and_gradient(tissue, z, junction, length)[0])
        positions.append(place(tissue, z[:-1].reshape(-1, 2), junction, length, z[-1]))
    return np.array(energies), positions, length0


def strained(tissue, x, deformation):
    """The tissue and positions after an affine deformation of vertices and box."""
    return replace(tissue, box=deformation @ tissue.box), np.asarray(x) @ deformation.T


def relaxed_curvature(tissue, x, generator, *, strain=1e-3, gtol=1e-12):
    """d2E/de2 of the relaxed energy by central differences of relaxed strained states."""
    values = []
    for e in (-strain, 0.0, strain):
        t, y = strained(tissue, x, np.eye(2) + e * np.asarray(generator))
        y, _, _ = relax(t, y, gtol=gtol)
        values.append(energy(t, y))
    return (values[0] - 2 * values[1] + values[2]) / strain**2


def linear_recoil(before, after, x, junction, times):
    """Linear response to a parameter change at equilibrium x (uniform friction).

    delta x(t) = sum_k (1 - exp(-lambda_k t / eta)) (v_k . f / lambda_k) v_k over the
    nonzero modes of the post-change Hessian, f the force jump. Returns the opening
    d(t) - d0 to first order, its initial rate and the effective time
    tau = Delta d_inf / d'(0).
    """
    eta = float(after.friction[0])
    if np.any(after.friction != eta):
        raise ValueError("linear_recoil assumes uniform friction")
    f = (gradient(before, x) - gradient(after, x)).ravel()
    values, vectors = np.linalg.eigh(hessian(after, x))
    keep = np.abs(values) > 1e-9 * np.max(np.abs(values))
    tail, head = after.junction_tail[junction], after.junction_head[junction]
    d = x[head] + after.junction_image[junction] @ after.box.T - x[tail]
    unit = d / np.linalg.norm(d)
    selector = np.zeros_like(x)
    selector[head], selector[tail] = unit, -unit
    weights = (vectors[:, keep].T @ selector.ravel()) * (vectors[:, keep].T @ f)
    lam = values[keep]
    opening = np.array([np.sum(weights * (1 - np.exp(-lam * t / eta)) / lam) for t in times])
    rate = float(selector.ravel() @ f / eta)
    final = float(np.sum(weights / lam))
    return opening, rate, final / rate
