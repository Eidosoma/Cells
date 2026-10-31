# ruff: noqa: E501, F841, B007, B905
"""Fresh pinned ECM channel/molecule/transporter native namespace; never production."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from validation.betse import betse_normal_ecm_catalog_join_native_network as qualified

class Clean(ast.NodeTransformer):

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)

def literal_nodes(root):
    nodes = qualified.literal_nodes(root)
    parsed = ast.parse((root / 'science/chemistry/networks.py').read_text())
    original = next((node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'MasterOfNetworks'))
    network = next((node for node in nodes if getattr(node, 'name', None) == 'MasterOfNetworks'))
    methods = [Clean().visit(copy.deepcopy(node)) for node in original.body if isinstance(node, ast.FunctionDef) and node.name in ('read_transporters', 'write_transporters', 'run_loop_transporters')]

    class Observe(ast.NodeTransformer):

        def visit_For(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.target) == 'name':
                node.body.insert(0, statement("self._observe_transporter('before',name,None,None,sim)"))
                node.body.append(statement("self._observe_transporter('after',name,None,None,sim)"))
            if ast.unparse(node.target) == '(i, (delc, coeff))':
                product = 'delta_prod_eval_strings' in ast.unparse(node.iter)
                stage, value = ('product_commit', 'delta_prod') if product else ('reactant_commit', 'delta_react')
                node.body.append(statement(f"self._observe_transporter('{stage}',name,i,{value},sim)"))
            return node

        def visit_Assign(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.targets[0]) == 'self.transporters[name].flux':
                return [node, statement("self._observe_transporter('flux',name,None,None,sim)")]
            return node

        def visit_AugAssign(self, node):
            node = self.generic_visit(node)
            if ast.unparse(node.target) == 'self.extra_J_mem':
                return [node, statement("self._observe_transporter('current',name,None,None,sim)")]
            return node
    network.body.extend((Observe().visit(node) if node.name == 'run_loop_transporters' else node for node in methods))
    transporter = Clean().visit(copy.deepcopy(next((node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'Transporter'))))
    transporter.body = [node for node in transporter.body if isinstance(node, ast.FunctionDef) and node.name in ('__init__', 'init_reaction')]
    network.body.append(Clean().visit(copy.deepcopy(next((n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == 'clear_cache')))))
    return nodes + [transporter]
_SCIENCE = None

def statement(text):
    return ast.parse(text).body[0]

def science():
    global _SCIENCE
    if _SCIENCE is None:
        pins = json.loads(qualified.PROTOCOL.read_text())['native_source']
        root = Path(pins['checkout']) / 'betse'
        for name in ('betse/science/chemistry/networks.py', 'betse/science/sim_toolbox.py'):
            file = Path(pins['checkout']) / name
            if hashlib.sha256(file.read_bytes()).hexdigest() != pins['source_sha256'][name]:
                raise ValueError('Changed authenticated transporter source ' + name)
            if file.read_bytes() != (Path(pins['installed_package']).parent / name).read_bytes():
                raise ValueError('Installed/native transporter source mismatch ' + name)
        ns = dict(qualified.science())
        ns['tex_val'] = str
        exec(compile(ast.fix_missing_locations(ast.Module(body=literal_nodes(root), type_ignores=[])), '<authenticated ECM general-owner configured transport>', 'exec'), ns)
        ns['fd'] = SimpleNamespace(**{key: ns[key] for key in ('gradient', 'divergence', 'integrator')})
        ns['stb'] = SimpleNamespace(molecule_mover=ns['molecule_mover'], no_negs=ns['no_negs'], electroflux=ns['electroflux'], update_Co=ns['update_Co'], div_env=ns['div_env'])
        _SCIENCE = ns
    return _SCIENCE
