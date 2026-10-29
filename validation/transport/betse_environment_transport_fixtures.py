"""Small explicit extracellular grids, coefficient regions and bath schedules."""

from math import cos, sin

UNIT = 2.0**-17


def base(shape=(4, 5)):
    ny, nx = shape
    count = ny * nx
    ions = ["Na", "K", "Cl", "M"]
    baseline = [14.0, 3.0, 10.0, 7.0]
    return dict(
        name="ionic-base",
        kind="ion",
        shape=list(shape),
        delta_m=UNIT,
        height_m=UNIT / 2,
        site_ids=[f"grid-r{i}-c{j}" for i in range(ny) for j in range(nx)],
        species_ids=ions,
        valence=[1.0, 1.0, -1.0, -1.0],
        q_C=1.602e-19,
        kb_J_K=1.3806e-23,
        faraday_C_mol=96485.0,
        temperature_K=300.0,
        dt_s=1e-5,
        sharpness=1.0,
        fluid_flow=False,
        is_ecm=True,
        D_free_m2_s=[1e-9, 1.2e-9, 0.7e-9, 0.4e-9],
        relative_TJ=[1.0, 0.8, 0.6, 0.4],
        adherens_factor=0.35,
        tight_factor=0.08,
        er=80.0,
        regions=dict(
            cluster=list(range(count // 2)),
            boundary_membrane=[0, nx, nx, count - 1],
            neighbor_membrane=[min(count - 1, nx + 1), min(count - 1, nx + 2)],
            boundary_cell=[0, min(count - 1, nx + 1)],
        ),
        tj_modulator=[[1.0] * count for _ in ions],
        concentration_mol_m3=[
            [
                baseline[s] + 0.12 * cos(0.7 * i + 0.4 * j + s) + 0.04 * sin(i + 0.6 * j)
                for i in range(ny)
                for j in range(nx)
            ]
            for s in range(4)
        ],
        base_bath_mol_m3=baseline,
        initial_boundary_mol_m3=baseline,
        electric_V_m=[
            [4 + sin(i + 0.3 * j) for i in range(ny) for j in range(nx)],
            [-3 + cos(0.3 * i + j) for i in range(ny) for j in range(nx)],
        ],
        velocity_m_s=[
            [2e-6 * sin(i + j) for i in range(ny) for j in range(nx)],
            [1e-6 * cos(i - 0.4 * j) for i in range(ny) for j in range(nx)],
        ],
        times_s=[0.0, 0.25, 0.5],
        events=[],
        enabled_Cl=True,
        legacy_bath_fields=True,
        molecule=dict(
            initial_mol_m3=[1 + 0.1 * cos(i + 0.4 * j) for i in range(ny) for j in range(nx)],
            diffusion_m2_s=1.3e-9,
            valence=1.0,
            bath_mol_m3=1.0,
            relative_TJ=0.3,
            ignore_TJ=False,
            extra_mobility_m2_V_s=0.0,
            time_dilation=1.0,
        ),
        wound=None,
    )


def cases():
    result = [base()]

    def add(name, shape=(4, 5)):
        value = base(shape)
        value["name"] = name
        result.append(value)
        return value

    value = add("uniform-stationary")
    value["concentration_mol_m3"] = [[v] * 20 for v in value["base_bath_mol_m3"]]
    value["electric_V_m"] = [[0.0] * 20 for _ in range(2)]
    value = add("prescribed-TJ-modulators")
    value["tj_modulator"][1] = [0.2 + 0.03 * i for i in range(20)]
    value = add("zero-diffusion-species")
    value["D_free_m2_s"][-1] = 0.0
    value = add("neutral-species")
    value["valence"] = [0.0] * 4
    value = add("advective-grid")
    value["fluid_flow"] = True
    value = add("source-smoothing")
    value["sharpness"] = 0.5
    add("two-by-two-grid", (2, 2))
    add("rectangular-grid", (5, 3))
    value = add("zero-tight-barrier")
    value["tight_factor"] = 0.0
    value = add("amplified-adherens-normalization")
    value["adherens_factor"] = 2.5
    value = add("non-ECM-weight-map")
    value["is_ecm"] = False
    value["kind"] = "coefficients"
    for label in ("barrier", "ignore-barrier", "extra-mobility", "accelerated"):
        value = add("molecule-" + label)
        value["kind"] = "molecule"
        if label == "ignore-barrier":
            value["molecule"]["ignore_TJ"] = True
        if label == "extra-mobility":
            value["molecule"].update(diffusion_m2_s=0.0, extra_mobility_m2_V_s=2e-8)
        if label == "accelerated":
            value["molecule"]["time_dilation"] = 3.0
    for ion in ("K", "Cl", "Na"):
        value = add("bath-" + ion)
        value["events"] = [
            dict(kind=ion + "_env", on_s=0.1, off_s=0.8, change_s=0.05, amplitude=0.4)
        ]
    value = add("bath-disabled-Cl")
    value["enabled_Cl"] = False
    value["events"] = [dict(kind="Cl_env", on_s=0.1, off_s=0.8, change_s=0.05, amplitude=0.4)]
    value = add("legacy-non-ECM-bath")
    value["is_ecm"] = False
    value["kind"] = "coefficients"
    value["events"] = [dict(kind="K_env", on_s=0.1, off_s=0.8, change_s=0.05, amplitude=0.4)]
    for factor in (0.0, 0.7):
        value = add("wound-coefficient-" + str(factor))
        value["wound"] = dict(targets=[1, 1, 6], factor=factor)
    return result


def limitations():
    result = []

    def add(name):
        value = base()
        value["name"] = name
        result.append(value)
        return value

    value = add("missing-sodium-normalizer")
    value["missing_sodium"] = True
    value = add("zero-sodium-normalizer")
    value["D_free_m2_s"][0] = 0.0
    value = add("all-zero-sodium-map")
    value["adherens_factor"] = 0.0
    value["tight_factor"] = 0.0
    value["regions"]["cluster"] = list(range(20))
    value = add("negative-barrier")
    value["tight_factor"] = -0.1
    value = add("negative-TJ-modulator")
    value["tj_modulator"][0] = [-1.0] * 20
    value = add("unstable-ionic-Euler")
    value["dt_s"] = 10.0
    value["clip_probe"] = True
    value = add("unstable-molecule-raises")
    value["kind"] = "molecule"
    value["dt_s"] = 10.0
    value = add("zero-temperature")
    value["temperature_K"] = 0.0
    value = add("flat-electric-field-shape")
    value["flat_electric"] = True
    value = add("missing-TJ-modulator")
    value["tj_modulator"] = None
    value = add("one-row-grid")
    value.update(base((1, 5)))
    value["name"] = "one-row-grid"
    value = add("legacy-non-ECM-missing-fields")
    value["is_ecm"] = False
    value["kind"] = "coefficients"
    value["legacy_bath_fields"] = False
    value["events"] = [dict(kind="K_env", on_s=0.1, off_s=0.8, change_s=0.05, amplitude=0.4)]
    value = add("overlapping-salt-counterion-overwrite")
    value["events"] = [
        dict(kind=k + "_env", on_s=0.1, off_s=0.8, change_s=0.05, amplitude=0.4)
        for k in ("Na", "K", "Cl")
    ]
    value = add("zero-bath-transition")
    value["events"] = [dict(kind="K_env", on_s=0.1, off_s=0.8, change_s=0.0, amplitude=0.4)]
    value = add("missing-counterion")
    value["missing_counterion"] = True
    value["events"] = [dict(kind="K_env", on_s=0.1, off_s=0.8, change_s=0.05, amplitude=0.4)]
    value = add("molecule-skips-small-bath")
    value["kind"] = "molecule"
    value["molecule"].update(initial_mol_m3=[0.0] * 20, bath_mol_m3=1e-16)
    value = add("source-sharpness-outside-domain")
    value["sharpness"] = -0.5
    value = add("collocated-mass-defect")
    value["adherens_factor"] = value["tight_factor"] = 1.0
    value["relative_TJ"] = [1.0] * 4
    value["D_free_m2_s"] = [1e-9] * 4
    value["base_bath_mol_m3"] = [0.0] * 4
    value["initial_boundary_mol_m3"] = [0.0] * 4
    value["electric_V_m"] = [[0.0] * 20 for _ in range(2)]
    value["concentration_mol_m3"] = [[float(i == 6) for i in range(20)] for _ in range(4)]
    value = add("checkerboard-null-stencil")
    value.update(base((8, 8)))
    value["name"] = "checkerboard-null-stencil"
    value["adherens_factor"] = value["tight_factor"] = 1.0
    value["relative_TJ"] = [1.0] * 4
    value["D_free_m2_s"] = [1e-9] * 4
    value["electric_V_m"] = [[0.0] * 64 for _ in range(2)]
    value["concentration_mol_m3"] = [
        [v + 0.2 * (-1) ** (i + j) for i in range(8) for j in range(8)]
        for v in value["base_bath_mol_m3"]
    ]
    return result


def refinement():
    result = []
    for n in (8, 16, 32):
        value = base((n, n))
        value["name"] = f"interior-source-refinement-{n}"
        value["delta_m"] = UNIT / n
        value["height_m"] = UNIT / 2
        value["adherens_factor"] = value["tight_factor"] = 1.0
        value["D_free_m2_s"] = [1e-9] * 4
        value["relative_TJ"] = [1.0] * 4
        value["regions"] = {key: [] for key in value["regions"]}
        value["electric_V_m"] = [[0.0] * (n * n) for _ in range(2)]
        value["concentration_mol_m3"] = [
            [
                v
                + 0.1
                * cos(2 * 3.141592653589793 * (i + 0.5) / n)
                * cos(2 * 3.141592653589793 * (j + 0.5) / n)
                for i in range(n)
                for j in range(n)
            ]
            for v in value["base_bath_mol_m3"]
        ]
        value["dt_s"] = 1e-8
        value["times_s"] = [0.0]
        result.append(value)
    return result
