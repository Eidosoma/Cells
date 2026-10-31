"""Generate a private two-owner phase coordinator, without executing science."""
# ruff: noqa: E501 -- Literal source adapters and explicit scope diagnostics.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells")
INIT = BASE / "betse-normal-ecm-init-phase-prepared-20261031-04/source"
PREFIX = "betse_normal_ecm_molecule_lifecycle"


def fn(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def write(name, tree):
    path = ROOT / "src/cells/processes" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# ruff: noqa: E501\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    compile(text, str(path), "exec")
    with path.open("x") as stream:
        stream.write(text)
    print(str(path))


HELPERS = """
def phase_failure_snapshot(ctx,supplied):
    return dict(owner_buffers=owners.available(ctx),supplied_owner_cache=supplied)

def expected_flags(raw):
    kind=raw['time_profile']['phase']
    if kind not in ('INIT','SIM'):
        raise ValueError('Require explicit native INIT/SIM phase selection')
    owner=raw['owners']['configuration']
    return dict(FIXED_FLAGS,phase=kind,_run_sim=kind=='SIM',
        molecules_enabled=owner['general network']['implement network'],
        grn_enabled=owner['gene regulatory network settings']['gene regulatory network simulated'])

def validate_owner_scope(raw):
    transport.bind(raw['owners'])
    for actual,wanted in ((raw['owners']['field'],raw['field']),
                          (raw['owners']['calcium'],raw['calcium']),
                          (raw['owners']['handlers']['grn']['catalog'],raw['catalog'])):
        if not common.equal_tree(actual,wanted):
            raise ValueError('Phase physical/carrier/catalog declarations differ from actual owner inputs')
    if raw['setup']['channel_noise_level']!=0 or raw['setup']['dynamic_noise']!=dict(enabled=False,level=0.0):
        raise ValueError('First supplied owner lifecycle closes static/dynamic noise while preserving complete stream/reset receipts')
    if any(value!=0 for key in ('global_options','scheduled_options') for value in raw['setup'][key].values()):
        raise ValueError('This phase composition requires the supplied no-intervention material seam')
    policy=raw['mechanics_definition']['policy']
    if any(policy[key] for key in ('deformation','deform_osmo','fluid_flow')):
        raise ValueError('Enabled mechanics/osmotic/flow requires a separate complete two-owner coupling')
    for key in ('molecules_enabled','grn_enabled'):
        if policy[key] is not expected_flags(raw)[key]:
            raise ValueError('Supplied mechanics projection must declare the actual independent owner flags')
    if raw['time_profile']['phase']=='SIM' and lifecycle.profile(raw['time_profile'])['sim']['step_count']!=3:
        raise ValueError('SIM retains the explicit existing three-call source domain')

def owner_context(binding,values,forcing=None):
    return owners.make_context(binding,ions.data(binding.inputs_raw['owners']),values,forcing,
                               phase_kind=binding.calendar.phase)

def install_stores(ctx,stores):
    kind=ctx.phase.kind
    setup.install(ctx,stores)
    owners.phase(ctx,kind)

def restore_owners(ctx,saved,index):
    owners.validate_phase_cache(ctx,saved,index)
    return owners.restore(ctx,ions.data(saved))

def dispatch_owners(ctx,definition,publication,label,observer=None):
    result=owners.dispatch(ctx,definition,publication,label,observer)
    ctx.trace=dict(source_completed=True,source_phase=ctx.phase.kind,legacy_run_sim=ctx.p._run_sim,
        controls_after={key:source.clone(getattr(ctx.sim,key)) for key in ('gj_block','NaKATP_block')},
        handlers=result['handlers'],source_order=result['order'],
        shared_after=result['shared_after'],publication_owner=result['publication_owner'])
    return ctx.trace
"""


def main():
    mechanics = ast.parse(
        (INIT / "src/cells/processes/betse_normal_ecm_init_phase_mechanics.py").read_text()
    )
    bind = fn(mechanics, "bind")
    for node in bind.body:
        if isinstance(node, ast.If) and "policy['molecules_enabled']" in ast.unparse(node.test):
            node.test = ast.parse(
                "not policy['is_ecm'] or any(policy[k] is not raw['flags'][k] for k in ('molecules_enabled','grn_enabled'))",
                mode="eval",
            ).body
            node.body = ast.parse(
                "raise ValueError('Mechanics projection must retain the actual two-owner phase flags')"
            ).body
    inputs = fn(mechanics, "mechanics_input")
    inputs.body = [
        n
        for n in inputs.body
        if not (isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in ("molecules", "names"))
    ]
    inputs.body[2:2] = ast.parse("""
products={role:({} if not ctx.enabled[role] else getattr(ctx.sim,role).core.molecules)
          for role in ('molecules','grn')}
""").body
    returned = next(n for n in inputs.body if isinstance(n, ast.Return))
    replacements = {
        "molecule_ids": "list(products['molecules'])",
        "molecule_cell_mM": "[np.array(obj.c_cells,copy=True) for obj in products['molecules'].values()]",
        "molecule_env_mM": "[np.array(obj.c_env,copy=True) for obj in products['molecules'].values()]",
        "grn_ids": "list(products['grn'])",
        "grn_cell_mM": "[np.array(obj.c_cells,copy=True) for obj in products['grn'].values()]",
        "grn_env_mM": "[np.array(obj.c_env,copy=True) for obj in products['grn'].values()]",
    }
    for keyword in returned.value.keywords:
        if keyword.arg in replacements:
            keyword.value = ast.parse(replacements[keyword.arg], mode="eval").body
    write(PREFIX + "_mechanics.py", mechanics)

    phase = ast.parse(
        (INIT / "src/cells/processes/betse_normal_ecm_init_phase.py")
        .read_text()
        .replace("betse_normal_ecm_init_phase_mechanics", PREFIX + "_mechanics")
        .replace("betse_normal_ecm_init_phase_source", PREFIX + "_source")
    )
    phase.body[1:1] = ast.parse("""
from cells.processes import betse_normal_ecm_molecule_lifecycle_owners as owners
from cells.processes import betse_normal_ecm_molecule_transport as transport
""").body
    for node in phase.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "LAW_ID":
                node.value = ast.Constant("betse_supplied_ECM_phase_general_transport_GRN_v1_5_0@1")
            if node.targets[0].id == "INPUT_KIND":
                node.value = ast.Constant("cells.normal_ecm_molecule_owner_phase_inputs@1")
    bind = fn(phase, "bind")
    bind.body.insert(2, ast.parse("validate_owner_scope(raw)").body[0])
    for node in ast.walk(bind):
        if isinstance(node, ast.Set) and {
            n.value for n in node.elts if isinstance(n, ast.Constant)
        } >= {"kind", "case_id", "field", "stop_after_calls"}:
            node.elts.append(ast.Constant("owners"))
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "FIXED_FLAGS.items()":
            node.iter = ast.parse("expected_flags(raw).items()", mode="eval").body
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "init"
            and "lifecycle.profile" in ast.unparse(node.value)
        ):
            node.slice = ast.parse("raw['time_profile']['phase'].lower()", mode="eval").body
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "calendars.bind":
            for kw in node.keywords:
                if kw.arg == "phase":
                    kw.value = ast.parse("raw['time_profile']['phase']", mode="eval").body
                if kw.arg == "requested_duration_s":
                    kw.value = ast.parse(
                        "raw['time_profile'][raw['time_profile']['phase'].lower()+'_total_s']",
                        mode="eval",
                    ).body
    for node in bind.body:
        if (
            isinstance(node, ast.If)
            and ast.unparse(node.test) == "raw['time_profile']['phase'] != 'INIT'"
        ):
            node.test = ast.parse(
                "raw['time_profile']['phase'] not in ('INIT','SIM')", mode="eval"
            ).body
    init = fn(phase, "initialize")
    init.args.kwonlyargs.append(ast.arg(arg="handler_observer"))
    init.args.kw_defaults.append(ast.Constant(None))
    init.body.insert(
        1,
        ast.parse(
            "if declaration.calendar.phase!='INIT':\n    raise ValueError('Fresh entry is INIT only; SIM requires the actual completed INIT handoff')"
        ).body[0],
    )
    advance = fn(phase, "advance")
    keep = [
        (a, d)
        for a, d in zip(advance.args.kwonlyargs, advance.args.kw_defaults, strict=True)
        if a.arg not in ("before_channels", "before_network")
    ]
    advance.args.kwonlyargs = [a for a, d in keep] + [ast.arg(arg="handler_observer")]
    advance.args.kw_defaults = [d for a, d in keep] + [ast.Constant(None)]

    class Owners(ast.NodeTransformer):
        def visit_Expr(self, node):
            if (
                isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func) == "common.configure"
            ):
                return None
            return self.generic_visit(node)

        def visit_Call(self, node):
            called = ast.unparse(node.func)
            if called == "network.make_context":
                args = [copy.deepcopy(node.args[0]), copy.deepcopy(node.args[1])]
                if len(node.args) > 3:
                    args.append(copy.deepcopy(node.args[3]))
                return ast.Call(
                    func=ast.Name(id="owner_context", ctx=ast.Load()), args=args, keywords=[]
                )
            if called == "common.cache":
                node.func = ast.parse("owners.cache", mode="eval").body
            elif called == "source.validate_init_cache":
                node.func = ast.parse("owners.validate_phase_cache", mode="eval").body
            elif called == "source.restore":
                node.func = ast.Name(id="restore_owners", ctx=ast.Load())
            elif called == "source.cold":
                return ast.parse("owners.initialize(ctx,handler_observer)", mode="eval").body
            elif called == "setup.install":
                node.func = ast.Name(id="install_stores", ctx=ast.Load())
            elif called == "source.run_dispatch":
                node.func = ast.Name(id="dispatch_owners", ctx=ast.Load())
                node.args = node.args[:4] + [ast.Name(id="handler_observer", ctx=ast.Load())]
            elif called == "catalog.failure_snapshot":
                node.func = ast.Name(id="phase_failure_snapshot", ctx=ast.Load())
            return self.generic_visit(node)

        def visit_keyword(self, node):
            if (
                node.arg == "source_phase"
                and isinstance(node.value, ast.Constant)
                and node.value.value == "INIT"
            ):
                node.value = ast.parse("binding.calendar.phase", mode="eval").body
            if (
                node.arg == "legacy_run_sim"
                and isinstance(node.value, ast.Constant)
                and node.value.value is False
            ):
                node.value = ast.parse("binding.calendar.phase=='SIM'", mode="eval").body
            return self.generic_visit(node)

    phase = Owners().visit(phase)
    init = fn(phase, "initialize")
    for node in ast.walk(init):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "owners.validate_phase_cache":
            node.keywords.append(ast.keyword(arg="pre_late", value=ast.Constant(True)))
    try_body = next(n for n in init.body if isinstance(n, ast.Try)).body
    position = next(
        i
        for i, n in enumerate(try_body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "net"
    )
    try_body[position:position] = ast.parse("owners.reset_storage(ctx)").body
    verifier = fn(phase, "verify")
    for node in ast.walk(verifier):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "check_rate":
            value = ast.unparse(node.args[0])
            if value == "parent.rate_cache":
                node.args[2] = ast.parse(
                    "binding.setup_receipt.get('entry_CaATP_present',False) or (index>0 and binding.calcium['alpha_Ca']>0)",
                    mode="eval",
                ).body
            elif value == "parent.nak_rate":
                node.args[2] = ast.parse(
                    "binding.setup_receipt.get('entry_NaK_present',False) or index>0", mode="eval"
                ).body
    binding_verifier = fn(phase, "verify_binding")
    old_test = next(
        n
        for n in binding_verifier.body
        if isinstance(n, ast.If) and "receipt['source_phase']" in ast.unparse(n.test)
    )
    old_test.test = ast.parse(
        """
receipt['source_phase'] != binding.calendar.phase
or receipt['legacy_run_sim'] is not (binding.calendar.phase=='SIM')
or receipt['event_finalization']['legacy_run_sim'] is not (binding.calendar.phase=='SIM')
or receipt['event_finalization']['event_fire_calls'] != 0
or receipt['event_finalization']['dynamic_noise_calls'] != 0
""".strip().replace("\n", " "),
        mode="eval",
    ).body
    advance = fn(phase, "advance")
    advance.args.kwonlyargs.append(ast.arg(arg="before_commit"))
    advance.args.kw_defaults.append(ast.Constant(None))
    post = next(
        n
        for n in ast.walk(advance)
        if isinstance(n, ast.FunctionDef) and n.name == "on_post_network"
    )
    post.body += ast.parse("""
holder['before_commit']=ions.freeze(dict(
    mode='commit',definition=ions.data(binding.inputs['definition']),
    values_before=source.material_values(ctx.sim),
    initial=ions.data(parent.network.material.values._asdict()),
    steps=[source.clone(packet)],material_inputs=incoming,
    source_phase=binding.calendar.phase,legacy_run_sim=binding.calendar.phase=='SIM'))
if before_commit is not None:
    before_commit(holder['before_commit'])
""").body
    phase.body += ast.parse(HELPERS).body
    phase.body = [
        n
        for n in phase.body
        if not (
            isinstance(n, ast.ImportFrom)
            and n.module == "cells.processes"
            and any(a.asname == "catalog" for a in n.names)
        )
    ]
    write(PREFIX + "_phase.py", phase)


if __name__ == "__main__":
    main()
