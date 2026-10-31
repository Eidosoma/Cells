# ruff: noqa: E501
"""Write deferred checks; never import/collect pytest or evaluate fixtures."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
file = ROOT / "tests/unit/test_betse_normal_ecm_calcium_join.py"
text = file.read_text().replace("betse_normal_ecm_calcium_join", "betse_normal_ecm_catalog_join")
text = text.replace("normal-ecm-calcium-join", "normal-ecm-catalog-join").replace(
    "CELLS_ECM_CALCIUM_CPU", "CELLS_ECM_CATALOG_CPU"
)
tree = ast.parse(text)
start = (
    next(n for n in tree.body if getattr(n, "name", None) == "test_ecm_calcium_raw_partial")
    .decorator_list[0]
    .lineno
    - 1
)
end = (
    next(n for n in tree.body if getattr(n, "name", None) == "runtime_receipt")
    .decorator_list[0]
    .lineno
    - 1
)
lines = text.splitlines(True)
head = "".join(lines[:start])
tail = "".join(lines[end:])
head = head.replace("def test_ecm_calcium_field_history(", "def test_ecm_catalog_history(")
head = head.replace(
    'calcium_configuration=inputs["calcium"], bootstrap_dt_s=',
    'catalog=inputs["catalog"], calcium_configuration=inputs["calcium"], bootstrap_dt_s=',
)
head = head.replace(
    'len(captured["history"]) == 3', 'len(captured["history"]) == inputs["stop_after_calls"]'
)
head = head.replace(
    '    exact(cold_parents[0]["policy"], captured["cold_policy"])',
    '    exact(cold_parents[0]["policy"], captured["cold_policy"])\n    exact(cold_parents[0]["channel_trace"],captured["cold_trace"])',
)
head = head.replace(
    '("material", "calcium", "network", "field")',
    '("material", "calcium", "channels", "network", "field")',
)
head = head.replace(
    "                observed[name] = ions.data(incoming)",
    '                archive(tmp_path,case+"-actual-"+name+"-input-before-reference-"+str(index), incoming)\n                observed[name] = ions.data(incoming)',
)
head = head.replace(
    '                before_network=before("network"),',
    '                before_network=before("network"),\n                before_channels=before("channels"),',
)
head = head.replace(
    '        exact(observed["network"], native_call["network"]["before"])',
    '        exact(observed["network"], native_call["network"]["before"])\n        exact(observed["channels"],native_call["network"]["before_channels"])',
)
head = head.replace(
    '            ("network", base.legacy.compare_local(feedback, *answers["network"])),',
    '            ("channels",compare_channels(binding,feedback,*answers["channels"])),\n            ("network", base.legacy.compare_local(feedback, *answers["network"])),',
)
head = head.replace("complete_calls=3,", 'complete_calls=inputs["stop_after_calls"],')
head = head.replace(
    "conditional_material_reference_forms=6,",
    'conditional_material_reference_forms=2*inputs["stop_after_calls"],\n                conditional_channel_reference_forms=2*inputs["stop_after_calls"],',
)
for key in ("calcium", "network", "field"):
    head = head.replace(
        "conditional_" + key + "_reference_forms=6,",
        "conditional_" + key + '_reference_forms=2*inputs["stop_after_calls"],',
    )
head = head.replace(
    "complete_native_ECM_CaATP=True,",
    'complete_native_ECM_CaATP=True,\n                complete_native_ECM_modern_catalog=True,\n                modern_class_count=len(inputs["catalog"]["populations"] or []),\n                actual_channel_owner_flag=inputs["catalog"]["populations"] is not None,',
)
comparison = """
def compare_channels(binding,feedback,lower,target):
    rows,add=base.legacy.comparisons()
    protocol=json.loads((Path(__file__).resolve().parents[2]/"validation/betse/betse_normal_ecm_catalog_join_protocol.json").read_text())
    g=binding.material_binding.geometry_binding
    cb=g.current_binding
    s,m,n,e=len(cb.ion_ids),len(cb.membrane_ids),len(cb.cell_ids),len(g.geometry.grid_points_m)
    flux_factor=128*np.finfo(float).eps*(s+m+4+32)
    current_factor=128*np.finfo(float).eps*(s+2+n+m+e+64)
    gate_rows=[row for row in feedback["channel_events"] if row["stage"]=="gate_after"]
    flux_rows=[row for row in feedback["channel_events"] if row["stage"]=="flux_after"]
    route_rows=[row for row in feedback["channel_events"] if row["stage"]=="route_after"]
    slot=0
    for index,(actual,wanted,less) in enumerate(zip(gate_rows,target["events"],lower["events"],strict=True)):
        assert actual["name"]==wanted["name"]
        cache=actual["population"]["core_fields"]
        tolerance=protocol["catalog_budgets"][wanted["class_name"]]
        for key in ("m","h","P"):
            if key not in wanted: continue
            values=np.broadcast_to(cache[key],np.asarray(wanted[key]).shape)
            add(str(index)+"/gate/"+key,values,wanted[key],less[key],
                tolerance["absolute"]+tolerance["relative"]*abs(np.asarray(wanted[key])),"unchanged class gate budget")
        add(str(index)+"/modulator",cache["modulator"],wanted["modulator"],less["modulator"],
            3e-14+6e-12*abs(np.asarray(wanted["modulator"])),"native Hill expression")
        for q,(route,lo) in enumerate(zip(wanted["routes"],less["routes"],strict=True)):
            before,after=flux_rows[slot],route_rows[slot]
            assert before["name"]==after["name"]==wanted["name"]
            assert before["fields"]["ion"]==route["ion_id"]
            prefix=str(index)+"/route/"+str(q)+"/"
            add(prefix+"flux",before["fields"]["f_ED"],route["chan_flux"],lo["chan_flux"],
                1e-18+flux_factor*np.asarray(route["flux_gross"]),"unchanged B24 local flux budget")
            add(prefix+"diffusion",before["fields"]["DChan"],route["DChan"],lo["DChan"],
                3e-20+6e-12*abs(np.asarray(route["DChan"])),"unchanged ECM diffusion budget")
            for field,key in (("cmem","sampled_bulk_at_membrane"),):
                add(prefix+key,before["fields"][field],route[key],lo[key],
                    3e-13+6e-12*abs(np.asarray(route[key])),"source bulk gather")
            i=list(cb.ion_ids).index(route["ion_id"])
            for key,source_key in (("cell_after","cell_mol_m3"),("membrane_after","membrane_mol_m3"),("environment_after","environment_mol_m3")):
                add(prefix+key,after["values"][source_key][i],route[key],lo[key],
                    3e-13+6e-12*abs(np.asarray(route[key])),"unchanged ECM concentration budget")
            flux=np.asarray(before["fields"]["f_ED"])
            area=np.asarray(cb.kernel.membrane_area_m2)
            volume=np.asarray(g.definition["geometry"]["cell_volume_m3"])
            site_volume=g.definition["parameters"]["cell_height_m"]*g.geometry.delta_m**2
            dt=feedback["before_channels"]["dt_s"]
            dc=np.asarray(after["values"]["cell_mol_m3"])[i]-np.asarray(before["values"]["cell_mol_m3"])[i]
            de=np.asarray(after["values"]["environment_mol_m3"])[i]-np.asarray(before["values"]["environment_mol_m3"])[i]
            transfer=dt*np.sum(flux*area)
            cell_amount=np.sum(dc*volume)
            effective=np.sum(de)*site_volume
            actual_book=dict(membrane_transfer_mol=transfer,cell_change_mol=cell_amount,
                source_effective_environment_change_mol=effective,source_effective_balance_mol=cell_amount+effective,
                conservative_environment_change_mol=-transfer,conservative_balance_mol=cell_amount-transfer,
                true_grid_environment_change_mol=np.sum(de*g.geometry.true_environment_volume_m3),
                source_minus_conservative_environment_mol=effective+transfer)
            for key,value in actual_book.items():
                add(prefix+key,value,route["book"][key],lo["book"][key],
                    3e-14+6e-12*abs(route["book"][key]),"unchanged ECM amount budget; source-effective and true-grid books distinct")
            np.testing.assert_array_equal(after["population"]["core_fields"]["chan_flux"],before["fields"]["f_ED"])
            np.testing.assert_array_equal(after["population"]["core_fields"]["DChan"],before["fields"]["DChan"])
            slot+=1
    assert slot==len(flux_rows)==len(route_rows)==target["voltage_nonce_count"]
    post=feedback["before"]
    add("channel_current",post["incoming_channel_current_A_m2"],target["extra_current"],lower["extra_current"],
        1e-30+current_factor*np.asarray(target["extra_current_gross"]),"unchanged GRN current gross budget")
    for key in ("cell_mol_m3","membrane_mol_m3","environment_mol_m3"):
        wanted=np.asarray(target["values_after"][key])
        add("after/"+key,post["values_before"][key],wanted,lower["values_after"][key],
            3e-13+6e-12*abs(wanted),"unchanged ECM material budget")
    # Channels never add to ordinary membrane storage, including zero-weight routes.
    np.testing.assert_array_equal(post["values_before"]["membrane_flux_mol_m2_s"],
        feedback["before_channels"]["values_before"]["membrane_flux_mol_m2_s"])
    return rows


@pytest.mark.parametrize("case",fixtures.RAW_CASES)
def test_ecm_catalog_raw_partial(tmp_path,case):
    inputs=fixtures.raw_fixture(case)
    archive(tmp_path,case+"-raw-inputs",inputs)
    folder,captured=isolated(tmp_path,inputs)
    cold_returns=[]
    parent=None
    def after_cold(value):
        archive(tmp_path,case+"-raw-cold-return",value)
        cold_returns.append(value)
    try:
        binding=joined.bind(inputs)
        parent=joined.initialize(binding,after_cold=after_cold)
        archive(tmp_path,case+"-raw-bootstrap-return",parent)
        returned=joined.advance(binding,parent,
            before_channels=lambda value:archive(tmp_path,case+"-raw-before-channels",value),
            before_network=lambda value:archive(tmp_path,case+"-raw-channel-return-before-GRN",value),
            after_calcium=lambda rate,phase:archive(tmp_path,case+"-raw-CaATP-return",dict(rate=rate,phase=phase)),
            after_material=lambda candidate,trial,network,calcium:archive(tmp_path,case+"-raw-material-return",dict(candidate=candidate,trial=trial,network=network,calcium=calcium)))
        archive(tmp_path,case+"-raw-unexpected-complete",returned)
    except joined.CatalogJoinRejected as error:
        partial=error.partial
        archive(tmp_path,case+"-raw-available-partial",dict(parent=parent,partial=partial,
            error=str(error),traceback=traceback.format_exc()))
        if "literal_pole" in case:
            assert partial["stage"]=="cold_cache_guard" and len(cold_returns)==1
            exact(cold_returns[0]["network"].network_cache,captured["cold_cache"])
            cores=partial["catalog_cache"]["wire"]["channel_fields"]
            failed=list(cores.values())[-1]["core_fields"]
            assert not joined.source.finite_tree(failed)
            if case.startswith("second_"):
                assert joined.source.finite_tree(list(cores.values())[0]["core_fields"])
        elif case=="empty_profile_indices":
            assert partial["stage"]=="cold" and not cold_returns
            assert captured["status"]=="source_refused" and captured["failure"]["stage"]=="cold"
            exact(partial["catalog_cache"],captured["cold_failure"])
            exact(partial["catalog_trace"],captured["cold_trace"])
        else:
            assert partial["stage"]=="material_calcium_network"
            actual=partial["network"]
            native_feedback=captured["history"][0]["network"]
            exact(actual,native_feedback)
            assert partial["material"]["frames"]
            if "channel_overflow" in case:
                fluxes=[v for v in actual["channel_events"] if v["stage"]=="flux_after"]
                assert fluxes and not np.isfinite(fluxes[-1]["fields"]["f_ED"]).all()
                if case.startswith("second_"):
                    assert np.isfinite(fluxes[0]["fields"]["f_ED"]).all()
            else:
                assert "run_loop_channels" in actual["dispatch_stages"]
                assert captured["status"]=="source_refused" and not actual["source_completed"]
    except Exception as error:
        archive(tmp_path,case+"-raw-unexpected-refusal",dict(parent=parent,error=str(error),
            traceback=traceback.format_exc(),partial=getattr(error,"partial",None)))
        raise
    else:
        raise AssertionError("Declared native raw limit was not reached")
    (folder/"raw-retention.json").write_text(json.dumps(dict(positive_credit=False,
        completed_calls=0,native_status=captured["status"],
        strict_finite_guard_distinct_from_native_exception="literal_pole" in case or "overflow" in case,
        complete_native_raw_buffers_retained=True,complete_available_port_partial_retained=True,
        source_ER_disabled=True,physical_global_conservation_credit=False),indent=2)+"\\n")


@pytest.mark.parametrize("dependency",fixtures.DEPENDENCIES)
def test_ecm_catalog_dependencies(tmp_path,dependency):
    inputs=fixtures.fixture("mixed_forward")
    archive(tmp_path,dependency+"-baseline-inputs-before-constructor",inputs)
    binding=joined.bind(inputs)
    parent=joined.initialize(binding,after_cold=lambda value:archive(tmp_path,dependency+"-baseline-cold-return",value))
    archive(tmp_path,dependency+"-valid-admission",dict(binding=binding,parent=parent))
    cache_deps={"missing_channel_cache","missing_private_gate","changed_target_cache","changed_owner_flag","missing_constructor_metadata"}
    messages=dict(
        ER_requested="Native ordinary ER is disabled; no forced Ca_dyn or missing kinetics",
        expression_profile="Expression profiles require separately owned expression/tissue state",
        legacy_cagPotassium="Require a reachable modern catalog factory class",
        INIT_requested="Require separately declared normal SIM channel configuration",
        missing_profile_map="Require explicit prepared tissue membrane index maps",
        missing_route_ion="Require every original channel route ion role",
        unsupported_modifier="Channel expression labels require separately qualified regulation",
        missing_channel_cache="Require every ECM owner/cache field",
        missing_private_gate="Require all source-private initialized and hot gate fields",
        changed_target_cache="Changed native channel routing or constructor metadata",
        changed_owner_flag="Require the actual cold-configured channel owner flag",
        wrong_clock="Require original normal time vector and accumulated material dt",
        invented_rate_presence="Require actual rate-cache absence or complete immutable source-written rate",
        supplied_old_field="Old electric fields must come from the actual preceding field stage",
        missing_constructor_metadata="Require every configured channel and complete constructor/cache metadata",
        varying_dt="Require one configured dt for the actual normal source clock")
    if dependency in cache_deps|{"wrong_clock","invented_rate_presence"}:
        rate,clock,net=parent.rate_cache,parent.clock,parent.network
        if dependency in cache_deps:
            cached=ions.data(net.network_cache)
            name=next(iter(cached["wire"]["channel_fields"]))
            if dependency=="missing_channel_cache": cached["wire"].pop("channel_fields")
            elif dependency=="missing_private_gate": cached["wire"]["channel_fields"][name]["core_fields"].pop("_mpower")
            elif dependency=="changed_target_cache": cached["wire"]["channel_fields"][name]["core_fields"]["targets"]=np.array([0])
            elif dependency=="changed_owner_flag": cached["wire"]["owner_fields"]["channels"]=False
            else: cached["initial_channel_fields"].pop(name)
            net=joined.network._state(binding,net.material,cached,net.controls)
        elif dependency=="wrong_clock": clock=joined.Clock(clock.source_times_s,1,0.0)
        else: rate=joined.RateCache(True,ions.freeze(np.zeros(9)))
        changed=joined.joined_state(binding,net,parent.field,rate,clock)
        archive(tmp_path,dependency+"-malformed-parent-before-call",changed)
        with pytest.raises((ValueError,joined.CatalogJoinRejected)) as caught:
            joined.advance(binding,changed)
    else:
        changed=copy.deepcopy(inputs)
        row=changed["catalog"]["populations"][0]
        if dependency=="ER_requested": changed["calcium"]["Ca_dyn"]=True
        elif dependency=="expression_profile": row["apply to"]="express"
        elif dependency=="legacy_cagPotassium": row["channel type"]="cagPotassium"
        elif dependency=="INIT_requested": changed["catalog"]["phase"]="INIT"
        elif dependency=="missing_profile_map": row["apply to"]=["absent"]
        elif dependency=="missing_route_ion":
            changed["catalog"]["populations"][0]=fixtures.population("CaLeak")
            changed["catalog"]["populations"][0]["channel class"]="Ca"
            # Validation of route prerequisites uses declared roles directly; a no-Ca caller
            # is a separate channel prerequisite refusal, before attempting calcium composition.
            with pytest.raises(ValueError) as route_error:
                joined.source.validate_catalog(changed["catalog"],["Na","K","Cl","P"],9)
            archive(tmp_path,dependency+"-malformed-inputs-before-call",changed)
            leaf=route_error.value
            assert str(leaf)==messages[dependency]
            (root(tmp_path)/("dependency-"+dependency+".json")).write_text(json.dumps(dict(
                baseline_admitted=True,intended_failure_reached=True,actual_leaf_type=type(leaf).__name__,
                actual_message=str(leaf),expected_message=messages[dependency],source_failure_credit=False),indent=2)+"\\n")
            return
        elif dependency=="unsupported_modifier": row.update({"channel activators":["Ca*"],"activator Km":[1e-4],"activator n":[2.0]})
        elif dependency=="supplied_old_field": changed["field"]["steps"][0]["material"]["electric_x_source"]=[[0.0]]
        else: changed["field"]["steps"][1]["material"]["dt_s"]*=2
        archive(tmp_path,dependency+"-malformed-inputs-before-call",changed)
        with pytest.raises(ValueError) as caught:
            joined.bind(changed)
    archive(tmp_path,dependency+"-partial",dict(partial=getattr(caught.value,"partial",None)))
    leaf=caught.value
    while leaf.__cause__ is not None: leaf=leaf.__cause__
    archive(tmp_path,dependency+"-refusal",dict(type=type(leaf).__name__,message=str(leaf)))
    assert type(leaf) is ValueError and str(leaf)==messages[dependency]
    (root(tmp_path)/("dependency-"+dependency+".json")).write_text(json.dumps(dict(
        baseline_admitted=True,intended_failure_reached=True,actual_leaf_type=type(leaf).__name__,
        actual_message=str(leaf),expected_message=messages[dependency],source_failure_credit=False),indent=2)+"\\n")
"""
# Place compare before test decorators, so no decorator accidentally binds to the comparison.
pos = head.index('@pytest.mark.parametrize("case", fixtures.CASES)')
raw_pos = comparison.index('@pytest.mark.parametrize("case",fixtures.RAW_CASES)')
comparison_fn = comparison[:raw_pos]
raw_dep = comparison[raw_pos:]
text = head[:pos] + comparison_fn + "\n" + head[pos:] + raw_dep + "\n" + tail
text = text.replace(
    "Prepared native ECM CaATP/full-field checks",
    "Prepared native ECM modern catalog/CaATP/full-field checks",
)
(ROOT / "tests/unit/test_betse_normal_ecm_catalog_join.py").write_text(text)
print("Wrote94 deferred IDs,78 native captures,1314 fresh reference forms; tests not collected")
