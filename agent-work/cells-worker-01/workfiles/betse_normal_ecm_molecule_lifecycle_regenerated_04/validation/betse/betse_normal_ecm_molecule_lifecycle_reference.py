# ruff: noqa: E501
"""Held fresh phase-aware Decimal conditionals; no production/science imports."""
import copy
from decimal import localcontext
from validation.betse import betse_normal_ecm_init_phase_reference as ordinary
from validation.betse import betse_normal_ecm_molecule_transport_reference as transport
from validation.betse import betse_normal_ecm_molecule_lifecycle_reference_models as models
from validation.betse.betse_normal_ecm_catalog_join_reference import serial

def evaluate(inputs, *, refinement, retain):
    if refinement not in (1, 2):
        raise ValueError('Require the predeclared independent Decimal100/160 forms')
    precision = 100 if refinement == 1 else 160
    mode = inputs.get('mode')
    kind = inputs.get('source_phase', 'INIT')
    if kind not in ('INIT', 'SIM'):
        raise ValueError('Reference requires the actual explicit source phase')
    with localcontext() as context:
        context.prec = precision
        if mode == 'setup':
            answer = ordinary.setup_equations(inputs)
            ordinary.retain_raw(retain, 'INIT-setup', answer, precision)
            result = serial(answer)
        elif mode == 'clock':
            profile = copy.deepcopy(inputs['time_profile'])
            if kind == 'SIM':
                for label in ('total_s', 'dt_s', 'sampling_s'):
                    profile['init_' + label] = profile['sim_' + label]
            clock, indices = ordinary.phase_clock(profile)
            answer = dict(clock=clock, sample_indices=indices)
            ordinary.retain_raw(retain, 'phase-clock', answer, precision)
            result = serial(answer)
        elif mode == 'phase_rules':
            answer = models.phase_rules(inputs)
            ordinary.retain_raw(retain, 'SIM-phase-rules', answer, precision)
            result = serial(answer)
        elif mode == 'nak':
            answer = ordinary.nak_equations(inputs, refinement)
            ordinary.retain_raw(retain, mode, answer, precision)
            result = serial(answer)
        elif mode == 'channels' and kind == 'INIT':
            result = ordinary.evaluate(inputs, refinement=refinement, retain=retain)
        elif mode == 'material':
            adapted = copy.deepcopy(inputs)
            nak = ordinary.nak_equations(inputs['nak_before'], refinement)
            ordinary.retain_raw(retain, 'fresh-NaK-before-primary-prefix', nak, precision)
            adapted['steps'][0]['supplied_pump_membrane_flux_mol_m2_s'] = nak['applied_flux']
            result = transport.evaluate(adapted, refinement=refinement, retain=retain)
        elif mode == 'commit':
            adapted = copy.deepcopy(inputs)
            primary = adapted['material_inputs']
            nak = ordinary.nak_equations(primary['nak_before'], refinement)
            ordinary.retain_raw(retain, 'fresh-NaK-before-deferred-commit', nak, precision)
            primary['steps'][0]['supplied_pump_membrane_flux_mol_m2_s'] = nak['applied_flux']
            result = transport.evaluate(adapted, refinement=refinement, retain=retain)
        elif mode == 'mechanics':
            result = ordinary.mechanics.evaluate({k: inputs[k] for k in ('definition', 'initial', 'steps')}, refinement=refinement, retain=retain)
        else:
            result = transport.evaluate(inputs, refinement=refinement, retain=retain)
            if mode == 'cold_initialization':
                profile = copy.deepcopy(inputs['time_profile'])
                if kind == 'SIM':
                    for label in ('total_s', 'dt_s', 'sampling_s'):
                        profile['init_' + label] = profile['sim_' + label]
                result['clock'], result['sample_indices'] = ordinary.phase_clock(profile)
    result.update(mode=mode, source_phase=kind, legacy_run_sim=kind == 'SIM', decimal_precision=precision, fresh_conditional_reference=True, carried_reference_forms=0, independently_carried_trajectory=False, physical_global_conservation_credit=False, inherited_channel_oracle_domains_unchanged=True, explicit_INIT04_dependency=True, historical_transition02_rebased=False)
    return result

def main():
    import argparse
    import builtins
    import hashlib
    import importlib.abc
    import json
    import sys
    from pathlib import Path
    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_ecm_init_phase_capture import record_failure
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--refinement', type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {'cells', 'betse', 'numpy', 'scipy', 'jax', 'jaxlib'}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split('.')[0] in blocked:
            raise ImportError('Independent event/mechanics reference import denied: ' + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):

        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in blocked:
                raise ImportError('Independent event/mechanics reference import denied: ' + fullname)
    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    retained = args.output.parent / ('raw-reference-' + str(args.refinement))
    completed_retained = []

    def retain(name, value):
        retained.mkdir(parents=True, exist_ok=True)
        with (retained / (name + '.json')).open('x') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
        completed_retained.append(name)

    def file_record(path):
        if not path.exists():
            return dict(path=str(path), present=False)
        if path.is_symlink() or not path.is_file():
            raise ValueError('Failure evidence must be a regular file: ' + str(path))
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return dict(path=str(path), present=True, bytes=path.stat().st_size, sha256=digest)

    def raw_records():
        return dict(completed_names=list(completed_retained), files=[file_record(path) for path in sorted(retained.iterdir())] if retained.exists() else [], incomplete_files_are_not_completed_forms=True)

    def retain_failure(payload):
        payload.update(worker_kind='independent_INIT_reference', scientific_credit=0)
        failure_path = args.output.with_name(args.output.name + '.failure.json')
        with failure_path.open('x') as stream:
            json.dump(payload, stream, indent=2, allow_nan=False)
            stream.write('\n')
    stage = 'input'
    try:
        incoming = json.loads(args.inputs.read_text())
        stage = 'evaluate'
        result = evaluate(incoming, refinement=args.refinement, retain=retain)
        stage = 'runtime'
        loaded = [n for n in sys.modules if n.split('.')[0] in blocked]
        assert not loaded
        result.update(production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory())
        stage = 'result_write'
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except Exception as error:
        record_failure(error, stage=stage, readers=dict(inputs=lambda: file_record(args.inputs), output=lambda: file_record(args.output), refinement=lambda: args.refinement, raw_reference_records=raw_records, runtime=inventory, loaded_production_modules=lambda: sorted((n for n in sys.modules if n.split('.')[0] in blocked))), retain=retain_failure)
        raise
if __name__ == '__main__':
    main()
