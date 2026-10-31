"""Prepare fresh Decimal phase/owner conditionals from explicit frozen sources."""
# ruff: noqa: E501 -- Literal source wrappers; none are evaluated here.

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
BASE = Path("/mnt/workspaces/Cells")
INIT = BASE / "betse-normal-ecm-init-phase-prepared-20261031-04/source"
TRANSITION = BASE / "betse-normal-ecm-init-sim-transition-prepared-20261031-02/source"
PREFIX = "betse_normal_ecm_molecule_lifecycle"

EVALUATE = """
def evaluate(inputs,*,refinement,retain):
    if refinement not in (1,2):
        raise ValueError('Require the predeclared independent Decimal100/160 forms')
    precision=100 if refinement==1 else 160
    mode=inputs.get('mode')
    kind=inputs.get('source_phase','INIT')
    if kind not in ('INIT','SIM'):
        raise ValueError('Reference requires the actual explicit source phase')
    with localcontext() as context:
        context.prec=precision
        if mode=='setup':
            answer=ordinary.setup_equations(inputs)
            ordinary.retain_raw(retain,'INIT-setup',answer,precision)
            result=serial(answer)
        elif mode=='clock':
            profile=copy.deepcopy(inputs['time_profile'])
            if kind=='SIM':
                for label in ('total_s','dt_s','sampling_s'):
                    profile['init_'+label]=profile['sim_'+label]
            clock,indices=ordinary.phase_clock(profile)
            answer=dict(clock=clock,sample_indices=indices)
            ordinary.retain_raw(retain,'phase-clock',answer,precision)
            result=serial(answer)
        elif mode=='phase_rules':
            answer=models.phase_rules(inputs)
            ordinary.retain_raw(retain,'SIM-phase-rules',answer,precision)
            result=serial(answer)
        elif mode=='nak':
            answer=ordinary.nak_equations(inputs,refinement)
            ordinary.retain_raw(retain,mode,answer,precision)
            result=serial(answer)
        elif mode=='channels' and kind=='INIT':
            result=ordinary.evaluate(inputs,refinement=refinement,retain=retain)
        elif mode=='material':
            adapted=copy.deepcopy(inputs)
            nak=ordinary.nak_equations(inputs['nak_before'],refinement)
            ordinary.retain_raw(retain,'fresh-NaK-before-primary-prefix',nak,precision)
            adapted['steps'][0]['supplied_pump_membrane_flux_mol_m2_s']=nak['applied_flux']
            result=transport.evaluate(adapted,refinement=refinement,retain=retain)
        elif mode=='commit':
            adapted=copy.deepcopy(inputs)
            primary=adapted['material_inputs']
            nak=ordinary.nak_equations(primary['nak_before'],refinement)
            ordinary.retain_raw(retain,'fresh-NaK-before-deferred-commit',nak,precision)
            primary['steps'][0]['supplied_pump_membrane_flux_mol_m2_s']=nak['applied_flux']
            result=transport.evaluate(adapted,refinement=refinement,retain=retain)
        elif mode=='mechanics':
            result=ordinary.mechanics.evaluate({k:inputs[k] for k in ('definition','initial','steps')},
                refinement=refinement,retain=retain)
        else:
            result=transport.evaluate(inputs,refinement=refinement,retain=retain)
            if mode=='cold_initialization':
                profile=copy.deepcopy(inputs['time_profile'])
                if kind=='SIM':
                    for label in ('total_s','dt_s','sampling_s'):
                        profile['init_'+label]=profile['sim_'+label]
                result['clock'],result['sample_indices']=ordinary.phase_clock(profile)
    result.update(mode=mode,source_phase=kind,legacy_run_sim=kind=='SIM',decimal_precision=precision,
        fresh_conditional_reference=True,carried_reference_forms=0,independently_carried_trajectory=False,
        physical_global_conservation_credit=False,inherited_channel_oracle_domains_unchanged=True,
        explicit_INIT04_dependency=True,historical_transition02_rebased=False)
    return result
"""


def fn(tree, name):
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def write(name, tree):
    path = ROOT / "validation/betse" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# ruff: noqa: E501\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    compile(text, str(path), "exec")
    with path.open("x") as stream:
        stream.write(text)
    print(str(path))


def main():
    old = ast.parse(
        (
            TRANSITION / "validation/betse/betse_normal_ecm_init_sim_transition_reference.py"
        ).read_text()
    )
    rules = fn(old, "phase_rules")
    # Only metadata describing which owners exist is generalized; numeric rules remain exact.
    for n in ast.walk(rules):
        if not isinstance(n, ast.keyword):
            continue
        if n.arg in ("grn_owner_reused", "grn_core_reused"):
            n.value = ast.parse("inputs['enabled']['grn']", mode="eval").body
        if n.arg == "molecular_current_concentrations_retained":
            n.value = ast.parse("any(inputs['enabled'].values())", mode="eval").body
    models = ast.parse('''
"""Copied phase reset arithmetic; current owner existence is explicit metadata."""
import copy
from decimal import Decimal
from validation.betse import betse_normal_ecm_catalog_join_reference as catalog
from validation.betse import betse_normal_ecm_init_phase_reference as ordinary
d,numbers,serial=catalog.d,catalog.numbers,catalog.serial
''')
    models.body.append(rules)
    write(PREFIX + "_reference_models.py", models)
    root = ast.parse(
        (INIT / "validation/betse/betse_normal_ecm_init_phase_reference.py").read_text()
    )
    outer = ast.parse('''
"""Held fresh phase-aware Decimal conditionals; no production/science imports."""
import copy
from decimal import localcontext
from validation.betse import betse_normal_ecm_init_phase_reference as ordinary
from validation.betse import betse_normal_ecm_molecule_transport_reference as transport
from validation.betse import betse_normal_ecm_molecule_lifecycle_reference_models as models
from validation.betse.betse_normal_ecm_catalog_join_reference import serial
''')
    outer.body += ast.parse(EVALUATE).body
    outer.body.append(fn(root, "main"))
    outer.body += ast.parse("if __name__=='__main__':\n    main()").body
    write(PREFIX + "_reference.py", outer)


if __name__ == "__main__":
    main()
