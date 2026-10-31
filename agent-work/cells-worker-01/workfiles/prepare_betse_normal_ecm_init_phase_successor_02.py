"""Prepare the two reviewed INIT02 evidence corrections; no science execution."""
# ruff: noqa: E501 -- embedded source templates preserve the initial proposal.

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-01")
REVIEW = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-preflight-20261031-01/REVIEW.json")
OUT = WORK / "betse_normal_ecm_init_phase_successor_02_proposal"
NATIVE = "validation/betse/betse_normal_ecm_init_phase_native.py"
TEST = "tests/unit/test_betse_normal_ecm_init_phase.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


CAPTURE = '''"""Small stdlib failure/sampling contracts; no scientific imports or evaluation."""

import struct
import traceback


def record_failure(error,*,stage,readers,retain):
    payload=dict(status="unexpected_source_failure",failure=dict(type=type(error).__name__,message=str(error),stage=stage,traceback="".join(traceback.format_exception(error))),available={},capture_errors=[])
    for name,reader in readers.items():
        try:
            payload["available"][name]=reader()
        except Exception as capture_error:
            payload["capture_errors"].append(dict(section=name,type=type(capture_error).__name__,message=str(capture_error)))
    if retain is not None:
        try:
            retain(payload)
        except Exception as archive_error:
            error.add_note("Failure evidence writer also failed: "+type(archive_error).__name__+": "+str(archive_error))
    return payload


def sampling_contract(*,source_labels,native_flags,reference_indices,native_rows,owned_rows,observation_indices,completed_calls):
    def require(condition,reason):
        if not condition:raise ValueError(reason)
    def bits(value):
        return struct.pack("<d",float(value))
    require(type(completed_calls) is int and 0<=completed_calls<=len(source_labels),"Completed prefix outside original calendar")
    require(len(native_flags)==len(source_labels) and all(type(v) is bool for v in native_flags),"Full native sample flag axis differs from source calendar")
    expected=[i for i,flag in enumerate(native_flags) if flag]
    require(len(reference_indices)==2,"Require both independent sampling forms")
    for indices in reference_indices:
        require(all(type(i) is int for i in indices) and indices==expected,"Independent sample indices differ from native source recurrence")
    require(len(native_rows)==len(owned_rows)==completed_calls,"Complete native/owned per-call sampling records required")
    selected=[]
    for i,(native,owned) in enumerate(zip(native_rows,owned_rows,strict=True)):
        eligible=i in expected
        require(native["source_call"]==owned["call_index"]==i,"Sample record source call differs")
        require(bits(native["source_time_s"])==bits(owned["source_label_s"])==bits(source_labels[i]),"Sample record original source label differs")
        require(type(native["native_calendar_eligible"]) is bool and native["native_calendar_eligible"] is eligible,"Native per-call eligibility differs from independent indices")
        require(type(owned["sample_eligible"]) is bool and owned["sample_eligible"] is eligible,"Owned per-call eligibility differs from native/independent indices")
        require(native["display_attempted"] is False and native["display_completed"] is False,"Headless INIT cannot acquire display credit")
        if eligible:selected.append(i)
    require(observation_indices==selected,"Emitted selected observations differ from native/independent prefix")
    return dict(original_sample_indices=expected,selected_prefix_indices=selected,completed_calls=completed_calls)
'''


READERS = '''
def _failure_readers(scope,error):
    """Read all reached numeric buffers without allowing capture errors to mask cause."""
    def safe(value):
        if isinstance(value,(np.ndarray,np.generic)):
            array=np.asarray(value)
            if array.dtype.kind in "biuf":return array.copy()
            return dict(unsupported_dtype=array.dtype.str,shape=list(array.shape),raw_bytes=np.frombuffer(array.tobytes(),np.uint8).copy())
        if isinstance(value,dict):return {str(key):safe(v) for key,v in value.items()}
        if isinstance(value,(list,tuple)):return [safe(v) for v in value]
        if value is None or type(value) in (str,int,float,bool):return value
        return dict(available_object_type=type(value).__name__)
    def fields(obj):
        return {key:safe(value) for key,value in vars(obj).items() if not callable(value)}
    def frames():
        rows=[]
        cursor=error.__traceback__
        while cursor is not None:
            frame=cursor.tb_frame
            local=frame.f_locals
            rows.append(dict(function=frame.f_code.co_name,path=frame.f_code.co_filename,line=cursor.tb_lineno,
                             arrays={key:safe(value) for key,value in local.items() if isinstance(value,(np.ndarray,np.generic))},
                             objects={key:fields(value) for key,value in local.items() if key in ("self","sim","cells","p","ctx") and hasattr(value,"__dict__")}))
            cursor=cursor.tb_next
        return rows
    readers=dict(source_inputs=lambda:safe(scope.get("declared")),traceback_frames=frames,
                 reached_local_arrays=lambda:{key:safe(value) for key,value in scope.items() if isinstance(value,(np.ndarray,np.generic))},
                 reached_records=lambda:{key:safe(scope.get(key)) for key in ("history","frames","environment_records","calcium_rows","field_rows","cold_cache","cold_material","cold_trace","cold_policy","setup_pre","finalized","source_calendar","source_times","material_candidate","post_material_cache","reset_return","before_reset","failure")},
                 global_numpy_rng=lambda:safe(np.random.get_state()),global_python_rng=lambda:safe(setup_native.random.getstate()))
    for name in ("sim","cells","parameters","ctx"):
        obj=scope.get(name)
        if obj is not None and hasattr(obj,"__dict__"):
            readers[name+"_fields"]=lambda obj=obj:fields(obj)
    ctx=scope.get("ctx")
    if ctx is not None:
        readers["network_cache"]=lambda:safe(network.cache(ctx))
        readers["network_trace"]=lambda:safe(ctx.trace)
    values=scope.get("values")
    if callable(values):readers["material_values"]=lambda:safe(values())
    for name in ("setup_owner","mechanical_owner"):
        obj=scope.get(name)
        if obj is not None:
            readers[name+"_fields"]=lambda obj=obj:fields(obj)
    owner=scope.get("setup_owner")
    if owner is not None:
        if hasattr(owner,"rng"):readers["setup_numpy_rng"]=lambda:safe(owner.rng.get_state())
        if hasattr(owner,"python"):readers["setup_python_rng"]=lambda:safe(owner.python.getstate())
    return readers
'''


SAMPLING = '''
def compare_sampling(binding,parent,captured,cold_forms,accepted_states):
    """Compare eligibility independently and compare every complete selected payload."""
    labels=captured["source_times_s"].tolist()
    native_flags=[bool(v) for v in captured["source_calendar"]["sampled"]]
    references=[row["sample_indices"] for row in cold_forms]
    result=capture_evidence.sampling_contract(source_labels=labels,native_flags=native_flags,reference_indices=references,
        native_rows=fixtures.events.plain(captured["sample_states"][:parent.cursor]),
        owned_rows=fixtures.events.plain(ions.data(parent.history)),observation_indices=[row["call_index"] for row in parent.observations],completed_calls=parent.cursor)
    for form in cold_forms:
        np.testing.assert_array_equal(form["clock"]["source_times_s"],captured["source_times_s"])
    for observation in parent.observations:
        index=observation["call_index"]
        accepted=accepted_states[index]
        source=captured["history"][index]
        np.testing.assert_array_equal(observation["source_label_s"],labels[index])
        exact(observation["network"],accepted.network)
        exact(observation["field"],accepted.field)
        exact(observation["mechanics"],accepted.mechanics)
        exact(observation["network"].material.values._asdict(),source["candidate"])
        exact(observation["network"].network_cache,source["post_material_cache"])
        exact(observation["mechanics"].cache,captured["mechanics_history"][index]["candidate"])
        for section,value in base.field_output(observation["field"]).items():exact(value,source["field"][section])
        assert observation["native_storage_called"] is False and observation["display_completed"] is False
    return result
'''


def main():
    if sha(REVIEW) != "ab6b07e33489748bdfa75d01a037aa82b0c22e8e8cfb33c0e0a36acca0137c3d":
        raise ValueError("Wrong final independent INIT review")
    OUT.mkdir(exist_ok=False)
    source = OUT / "source"
    (source / "validation/betse").mkdir(parents=True)
    (source / "tests/unit").mkdir(parents=True)
    capture = source / "validation/betse/betse_normal_ecm_init_phase_capture.py"
    capture.write_text(CAPTURE)
    original = (PARENT / "source" / NATIVE).read_text()
    tree = ast.parse(original)
    tree.body.insert(
        next(i for i, n in enumerate(tree.body) if isinstance(n, ast.FunctionDef)),
        ast.parse(
            "from validation.betse import betse_normal_ecm_init_phase_capture as capture_evidence"
        ).body[0],
    )
    helper = ast.parse(READERS).body[0]
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate")
    function.args.kwonlyargs.append(ast.arg(arg="retain_failure"))
    function.args.kw_defaults.append(ast.Constant(None))
    # Initialize before bootstrap and again before each attempted reset.
    index = next(i for i, n in enumerate(function.body) if isinstance(n, ast.With))
    function.body[index:index] = ast.parse("reset_return = None").body
    loop = next(
        n
        for n in ast.walk(function)
        if isinstance(n, ast.For) and ast.unparse(n.target) == "(index, call)"
    )
    reset = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.Expr)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "source['resets']"
    )
    loop.body[reset:reset] = ast.parse("reset_return = None").body
    inner = next(
        n
        for n in ast.walk(function)
        if isinstance(n, ast.Try)
        and any(
            isinstance(s, ast.Expr)
            and isinstance(s.value, ast.Call)
            and ast.unparse(s.value.func) == "field_call"
            for s in n.body
        )
    )
    inner.handlers[0].body.append(
        ast.parse('if field_phase in ("bootstrap", "reset"):\n    raise').body[0]
    )
    # Stage markers and outer capture cover constructors/finalizers before the
    # old loop try exists. All numerical function bodies remain unchanged.
    markers = {
        "setup_owner": "setup_owner",
        "cold_cache": "cold",
        "mechanical_owner": "mechanics_entry",
        "finalized": "event_finalization",
        "source_calendar": "clock",
    }

    class Mark(ast.NodeTransformer):
        def visit_Assign(self, node):
            name = ast.unparse(node.targets[0])
            return (
                [ast.parse("capture_stage = " + repr(markers[name])).body[0], node]
                if name in markers
                else node
            )

    body = []
    for statement in function.body:
        value = Mark().visit(statement)
        body.extend(value if isinstance(value, list) else [value])
    outer = ast.parse(
        'try:\n    pass\nexcept Exception as error:\n    capture_evidence.record_failure(error,stage=(field_phase if capture_stage == "source_loop" else capture_stage),readers=_failure_readers(locals(),error),retain=retain_failure)\n    raise\nfinally:\n    sys.settrace(capture_previous_trace)'
    ).body[0]
    for i, statement in enumerate(body):
        if isinstance(statement, ast.With):
            body[i:i] = ast.parse('capture_stage = "source_loop"').body
            break
    outer.body = body
    function.body = ast.parse(
        'capture_stage = "input_and_geometry"\ncapture_previous_trace = sys.gettrace()'
    ).body + [outer]
    tree.body.insert(tree.body.index(function), helper)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    assignment = next(
        n for n in main.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "result"
    )
    assignment.value.keywords.append(
        ast.keyword(arg="retain_failure", value=ast.Name(id="retain_failure", ctx=ast.Load()))
    )
    position = main.body.index(assignment)
    main.body[position:position] = ast.parse("""
def retain_failure(value):
    archives.write_archive(args.output.parent / (args.output.name + "-failure-before-reraise"),value)
""").body
    (source / NATIVE).write_text(
        "# ruff: noqa: F841\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    )
    code = (PARENT / "source" / TEST).read_text()
    code = code.replace(
        "from validation.betse import betse_normal_ecm_init_phase_native as native",
        "from validation.betse import betse_normal_ecm_init_phase_native as native\nfrom validation.betse import betse_normal_ecm_init_phase_capture as capture_evidence",
    )
    code = code.replace("\ndef setup_rows(", SAMPLING + "\n\ndef setup_rows(", 1)
    code = code.replace(
        "    initial_setup_identity = ions.digest(binding.setup_receipt)",
        '    accepted_states = {}\n    compare_sampling(binding,parent,captured,answers["cold"],accepted_states)\n    initial_setup_identity = ions.digest(binding.setup_receipt)',
        1,
    )
    code = code.replace(
        "        parent = candidate\n",
        '        accepted_states[index] = candidate\n        compare_sampling(binding,candidate,captured,answers["cold"],accepted_states)\n        parent = candidate\n',
        1,
    )
    (source / TEST).write_text(code)
    for path in (capture, source / NATIVE, source / TEST):
        compile(path.read_text(), str(path), "exec")
    record = dict(
        kind="cells.INIT02_reviewed_evidence_proposal@1",
        parent_manifest_sha256=sha(PARENT / "MANIFEST.json"),
        review=dict(path=str(REVIEW), sha256=sha(REVIEW)),
        repaired_findings=["INIT-CAPTURE-01", "INIT-SAMPLING-02"],
        source_equations_changed=False,
        fixtures_ids_cases_budgets_changed=False,
        proposed_sha256={
            str(p.relative_to(source)): sha(p) for p in (capture, source / NATIVE, source / TEST)
        },
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_reference_model_evaluations=0,
        pytest_collection=0,
        numerical_runs=0,
    )
    with (OUT / "proposal.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(record["proposed_sha256"]))


if __name__ == "__main__":
    main()
