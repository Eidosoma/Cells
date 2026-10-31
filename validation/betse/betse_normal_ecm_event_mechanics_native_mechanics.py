"""Original mechanics bodies on actual event/noise state at the reached native seam.

The extra DEC/neighbor view is an explicit conditional supplied declaration on
identical owners/measures/maps. It never overwrites the material/field geometry.
"""

import copy
import sys
import traceback
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_mechanics_join_native as mechanics

capture = mechanics.capture


class SourceMechanicsRejected(RuntimeError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = partial


def _prepared_mechanics_view(inputs):
    try:
        namespace, pins, sites = capture()
        raw = inputs["definition"]
        geometry, policy, parameters = (raw[key] for key in ("geometry", "policy", "parameters"))
        if policy["fluid_flow"] or policy["td_deform"] or policy["solver"] != "FULL":
            raise ValueError("No forced enabled flow/dynamic branch in ordinary capture")
        mesh = geometry["layout"]
        p = SimpleNamespace(
            deform_osmo=policy["deform_osmo"],
            fluid_flow=False,
            td_deform=False,
            deformation=policy["deformation"],
            is_ecm=policy["is_ecm"],
            molecules_enabled=policy["molecules_enabled"],
            grn_enabled=policy["grn_enabled"],
            fixed_cluster_bound=parameters["fixed_boundary"],
            lame_mu=parameters["young_modulus_Pa"] / (2 * (1 + 0.49)),
            galvanotropism=parameters["galvanotropism_m2_V"],
            dt=parameters["dt_s"],
            R=parameters["gas_constant_J_mol_K"],
            aquaporins=parameters["aquaporin_fraction"],
            mu_water=0.01,
            tm=parameters["membrane_thickness_m"],
            rho=parameters["density_kg_m3"],
            cell_height=mesh["cell_height_m"],
        )
        cells = namespace["CapturedCells"]()
        cells.cell_nn_i = np.asarray(mesh["neighbors"], int)
        cells.nn_len = np.asarray(mesh["lengths_m"])
        cells.nn_tx, cells.nn_ty = np.asarray(mesh["force_directions"]).T
        cells.cell_nn_tx, cells.cell_nn_ty = np.asarray(mesh["curl_directions"]).T
        cells.M_sum_mems = np.asarray(mesh["sum_membranes"], dtype=float)
        cells.num_mems = cells.M_sum_mems.sum(axis=1)
        cells.mem_vects_flat = np.column_stack(
            (np.zeros((len(cells.nn_len), 2)), np.asarray(mesh["force_directions"]))
        )
        cells.mem_sa, cells.mem_vol = (
            np.asarray(mesh[key]) for key in ("membrane_area_m2", "membrane_volume_m3")
        )
        cells.cell_sa, cells.cell_vol = (
            np.asarray(mesh[key]) for key in ("cell_area_m2", "cell_volume_m3")
        )
        cells.mesh = SimpleNamespace(
            vor_edge_len=np.asarray(mesh["dual_edge_m"]),
            tri_edge_len=np.asarray(mesh["primal_edge_m"]),
            delta_tri_0=np.asarray(mesh["incidence"], dtype=float),
            delta_tri_0_inv=np.asarray(mesh["incidence_inverse"], dtype=float),
            vor_sa=np.asarray(mesh["dual_area_m2"]),
        )
        cells.graphLaplacian(p)
        cells.map_cell2ecm = np.asarray(geometry["cell_to_environment"], int)
        cells.cell_centres, cells.mem_verts = (
            np.asarray(mesh[key]) for key in ("centers_m", "vertices_m")
        )
        cells.cell_to_mems = [np.flatnonzero(row).tolist() for row in cells.M_sum_mems]
        cells.mem_to_cells = np.argmax(cells.M_sum_mems, axis=0)
        cells.cell_verts = np.asarray(
            [cells.mem_verts[indices] for indices in cells.cell_to_mems], dtype=object
        )
        sim = SimpleNamespace(
            **{
                key: np.array(value, dtype=float)
                for key, value in inputs["initial"].items()
                if not key.startswith("display_")
            },
            cdl=len(geometry["cell_ids"]),
            mdl=len(cells.nn_len),
            edl=len(geometry["environment_ids"]),
            cellso=copy.deepcopy(cells),
            cell_centres_time=[],
            cell_verts_time=[],
        )
        sim.cellso.cell_centres = np.asarray(inputs["initial"]["display_centres_m"])
        imported_vertices = np.asarray(inputs["initial"]["display_vertices_m"], dtype=float)
        sim.cellso.cell_verts = np.asarray(
            [imported_vertices[indices].copy() for indices in cells.cell_to_mems], dtype=object
        )
        return dict(namespace=namespace, cells=cells, parameters=p, sim=sim, pins=pins, sites=sites)
    except Exception as error:
        retained = {
            key: data(value) for key, value in locals().items() if key not in {"namespace", "error"}
        }
        raise SourceMechanicsRejected(error, retained) from error


CACHE_KEYS = (
    "osmo_P_cell",
    "osmo_P_env",
    "osmo_P_delta",
    "u_osmo",
    "div_u_osmo",
    "PP",
    "gPxc",
    "gPyc",
    "d_cells_x",
    "d_cells_y",
    "u_cells_x",
    "u_cells_y",
    "u_env_x",
    "u_env_y",
)


def data(value):
    if isinstance(value, np.ndarray):
        if value.dtype.kind == "O":
            return dict(kind="object_array", shape=list(value.shape), items=data(value.tolist()))
        return value.copy()
    if isinstance(value, dict):
        return {key: data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [data(item) for item in value]
    if isinstance(value, SimpleNamespace) or hasattr(value, "__dict__"):
        return {key: data(item) for key, item in vars(value).items() if not callable(item)}
    if value is None or isinstance(value, (str, int, float, bool, np.generic)):
        return value
    raise ValueError("Unsupported available mechanical source buffer: " + type(value).__name__)


class Owner:
    def __init__(self, declared, sim, cells, parameters):
        try:
            self.inputs = declared
            definition = declared["mechanics_definition"]
            policy = definition["policy"]
            if (
                policy["display_regime"] != "none"
                or policy["fluid_flow"]
                or policy["td_deform"]
                or (policy["solver"] != "FULL")
            ):
                raise ValueError("Inherited ordinary mechanics/display domain is unchanged")
            if not 1 <= sim.cdl <= 16:
                raise ValueError("Inherited native event field domain<=16")
            self.prepared = _prepared_mechanics_view(
                dict(definition=definition, initial=declared["mechanics_initial"], steps=[])
            )
            self.namespace = self.prepared["namespace"]
            self.cells = self.prepared["cells"]
            self.sim = sim
            self.parameters = parameters
            for key in (
                "cell_vol",
                "cell_sa",
                "mem_sa",
                "cell_centres",
                "mem_to_cells",
                "map_cell2ecm",
            ):
                np.testing.assert_array_equal(
                    getattr(cells, key), getattr(self.cells, key), err_msg=key
                )
            for key in ("R", "dt", "tm", "cell_height"):
                assert getattr(parameters, key) == getattr(self.prepared["parameters"], key), key
            for key, value in vars(self.prepared["parameters"]).items():
                setattr(parameters, key, value)
            self.entry_store_presence = {key: hasattr(sim, key) for key in CACHE_KEYS}
            for key in CACHE_KEYS:
                initial = np.array(declared["mechanics_initial"][key], dtype=float)
                if key in ("u_env_x", "u_env_y"):
                    assert not np.any(initial)
                    if hasattr(sim, key):
                        assert np.array_equal(initial, getattr(sim, key))
                    else:
                        setattr(sim, key, initial)
                else:
                    setattr(sim, key, initial)
            self.history = []
            self.raw_calls = []
            self.sample_states = []
        except Exception as error:
            retained = dict(
                inputs=data(declared),
                supplied_entry_store_presence=getattr(self, "entry_store_presence", {}),
                available_mechanical_stores={
                    key: data(getattr(sim, key)) for key in CACHE_KEYS if hasattr(sim, key)
                },
                source_parameters=data(parameters),
                prior_partial=getattr(error, "partial", None),
            )
            if hasattr(self, "prepared"):
                retained["mechanics_view"] = data(self.prepared["cells"])
            raise SourceMechanicsRejected(error, retained) from error

    def cache(self):
        return {key: np.array(getattr(self.sim, key), copy=True) for key in CACHE_KEYS} | {
            key: np.asarray(self.inputs["mechanics_initial"][key]).copy()
            for key in ("display_centres_m", "display_vertices_m")
        }

    def incoming(self, ctx, index, clock_s, sigma):
        names = list(self.sim.grn.core.molecules)
        geometry = self.inputs["mechanics_definition"]["geometry"]
        return dict(
            receipt=dict(
                stage="normal_full_after_handlers_before_deferred_material_voltage",
                geometry_epoch=self.inputs["mechanics_definition"]["provenance"]["geometry_epoch"],
                cell_ids=geometry["cell_ids"],
                environment_ids=geometry["environment_ids"],
                source_step=index,
                deferred_material_voltage_commit_done=False,
            ),
            clock_s=float(clock_s),
            dt_s=self.parameters.dt,
            temperature_K=float(self.sim.T),
            pressure_Pa=self.sim.P_cells.copy(),
            electric_field_V_m=np.stack((self.sim.E_cell_x, self.sim.E_cell_y)),
            current_density_A_m2=np.stack((self.sim.J_cell_x, self.sim.J_cell_y)),
            charge_density_C_m3=self.sim.rho_cells.copy(),
            conductivity_S_m=np.array(sigma, copy=True),
            primary_ids=list(ctx.ion_ids),
            primary_cell_mM=self.sim.cc_cells.copy(),
            primary_env_mM=self.sim.cc_env.copy(),
            molecule_ids=[],
            molecule_cell_mM=[],
            molecule_env_mM=[],
            grn_ids=names,
            grn_cell_mM=[self.sim.grn.core.molecules[name].c_cells.copy() for name in names],
            grn_env_mM=[self.sim.grn.core.molecules[name].c_env.copy() for name in names],
            sample=False,
        )

    def advance(self, ctx, index, clock_s, sigma):
        before = self.incoming(ctx, index, clock_s, sigma)
        frames, auxiliary, latest, hh = ([], {"flow": None}, {}, [])
        stage = "initial"
        completed = False
        failure = None
        previous = sys.gettrace()
        codes = {self.namespace[name].__code__: name for name in ("osmotic_P", "getDeformation")}
        codes[self.namespace["CapturedCells"].HH_cells.__code__] = "HH_cells"

        def trace(frame, event, arg):
            if previous is not None:
                previous(frame, event, arg)
            if frame.f_code in codes and event in ("return", "exception"):
                observed = {
                    key: data(value)
                    for key, value in frame.f_locals.items()
                    if isinstance(value, (np.ndarray, float, int, bool, np.generic))
                }
                record = dict(function=codes[frame.f_code], event=event, locals=observed)
                if event == "return":
                    record["returned"] = data(arg)
                    latest[codes[frame.f_code]] = observed
                    if codes[frame.f_code] == "HH_cells":
                        hh.append(data(arg))
                else:
                    record["exception"] = dict(type=arg[0].__name__, message=str(arg[1]))
                self.raw_calls.append(record)
            return trace

        def observe(label):
            frames.append(dict(stage=label, cache=self.cache()))

        sim, cells, p = (self.sim, self.cells, self.parameters)
        try:
            observe("initial")
            sys.settrace(trace)
            stage = "osmotic_pressure"
            self.namespace["block_0"](sim, cells, clock_s, p)
            if p.deform_osmo:
                auxiliary["osmotic"] = dict(
                    zip(
                        (
                            "cell_osmotic_pressure_Pa",
                            "environment_osmotic_pressure_Pa",
                            "delta_pressure_Pa",
                            "water_velocity_m_s",
                            "divergence_per_s",
                            "PP_native",
                        ),
                        (
                            getattr(sim, key).copy()
                            for key in (
                                "osmo_P_cell",
                                "osmo_P_env",
                                "osmo_P_delta",
                                "u_osmo",
                                "div_u_osmo",
                                "PP",
                            )
                        ),
                        strict=True,
                    )
                )
                observe("osmotic_pressure")
            stage = "disabled_flow_gate"
            self.namespace["block_1"](sim, cells, clock_s, p)
            observe("disabled_flow_gate")
            stage = "steady_deformation"
            self.namespace["block_2"](sim, cells, clock_s, p)
            if p.deformation:
                local = latest["getDeformation"]
                potential, rotated_x, rotated_y, *_ = hh[-1]
                _, _, divergence = cells.curl(-sim.d_cells_y, sim.d_cells_x, 0)
                auxiliary["steady"] = dict(
                    displacement_m=np.stack((sim.d_cells_x, sim.d_cells_y)),
                    pressure_gradient_Pa_m=np.stack((sim.gPxc, sim.gPyc)),
                    unprojected_elastic_m=np.stack((local["dxo"], local["dyo"])),
                    rotational_m=np.stack((rotated_x, rotated_y)),
                    rotation_potential=potential,
                    osmotic_addition_native=np.stack((local["dxco"], local["dyco"]))
                    if p.deform_osmo
                    else np.zeros((2, sim.cdl)),
                    electric_addition_m=np.stack((sim.E_cell_x, sim.E_cell_y)) * p.galvanotropism,
                    divergence_numeric=divergence,
                )
                observe("steady_deformation")
            completed = True
        except Exception as error:
            failure = dict(
                stage=stage,
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            sys.settrace(previous)
            self.history.append(
                dict(
                    before=data(before),
                    frames=frames,
                    auxiliaries=auxiliary,
                    candidate=self.cache(),
                    sample=None,
                    carried_cache=self.cache(),
                    source_completed=completed,
                    failure=failure,
                    available_source_cells=data(cells),
                    available_source_parameters=data(p),
                    raw_calls=data(self.raw_calls),
                    complete_available_buffers=True,
                    supplied_entry_store_presence=self.entry_store_presence,
                )
            )

    def sample_state(self, index, clock_s, labels):
        eligible = float(clock_s) in labels
        row = dict(
            source_call=index,
            source_time_s=float(clock_s),
            native_calendar_eligible=eligible,
            display_attempted=False,
            display_completed=False,
            display_status="held_separate_display_domain_required" if eligible else "not_eligible",
            maximum_field_cells=16,
            minimum_quartic_display_cells=25,
        )
        self.sample_states.append(row)
        return row
