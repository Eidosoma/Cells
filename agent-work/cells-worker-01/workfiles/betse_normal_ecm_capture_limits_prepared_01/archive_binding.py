"""Strict normal-current typed archives; stdlib only, no physical evaluation."""
import hashlib
import json
import math
import re
import struct
import zipfile
from pathlib import Path

from qualification_typed_evidence import array_header

KIND='cells.betse_normal_current_raw_evidence@1'
MAX_BYTES=64*2**20
MAX_MEMBERS=310689

def require(condition,message):
    if not condition:raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def read(path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink(),'Regular unlinked JSON required')
    require(path.stat().st_size<=MAX_BYTES,'JSON size bound')
    def pairs(rows):
        out={}
        for key,value in rows:
            require(key not in out,'Duplicate JSON key');out[key]=value
        return out
    def bad(value):raise ValueError('Nonstandard JSON scalar: '+value)
    return json.loads(path.read_text(),object_pairs_hook=pairs,parse_constant=bad)

def bind(folder,*,decoded=False):
    folder=Path(folder)
    require(folder.is_dir() and not folder.is_symlink(),'Real archive directory required')
    manifest=folder/'manifest.json';row=read(manifest)
    require(set(row)=={'kind','complete','files'} and row['kind']==KIND and row['complete'] is True,
        'Exact complete normal-current archive schema required')
    require(type(row['files']) is dict and set(row['files'])=={'data.json','arrays.npz'},'Complete typed payload pair required')
    for name,digest in row['files'].items():
        path=folder/name
        require(path.is_file() and not path.is_symlink() and type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest) and sha(path)==digest,'Typed archive hash mismatch')
    tree=read(folder/'data.json');descriptors={};paths={};scalar_bits=0;nodes=0
    def visit(node,path='root',depth=0):
        nonlocal scalar_bits,nodes
        nodes+=1;require(nodes<=2000000 and depth<=128,'Typed tree bound')
        if type(node) is dict:
            if set(node)=={'array','dtype','shape'}:
                name=node['array'];require(type(name) is str and re.fullmatch(r'a(?:0|[1-9][0-9]*)',name),'Canonical numeric array owner')
                require(name not in descriptors,'Repeated typed array owner')
                require(type(node['dtype']) is str and type(node['shape']) is list and all(type(v) is int and v>=0 for v in node['shape']),'Typed descriptor fields')
                descriptors[name]=node;paths[name]=path;return
            if set(node)=={'mapping'}:
                require(type(node['mapping']) is list,'Mapping rows')
                keys=[]
                for pair in node['mapping']:
                    require(type(pair) is list and len(pair)==2,'Mapping pair')
                    key,value=pair
                    require(key is None or type(key) in (str,int,bool) or type(key) is float and math.isfinite(key),'Supported mapping key')
                    require(key not in keys,'Duplicate typed mapping key');keys.append(key)
                    visit(value,path+'/'+str(key),depth+1)
                return
            if set(node)=={'sequence'}:
                require(type(node['sequence']) is list,'Sequence rows')
                for i,value in enumerate(node['sequence']):visit(value,path+'/'+str(i),depth+1)
                return
            if set(node)=={'float64_bits'}:
                require(type(node['float64_bits']) is str and re.fullmatch('[0-9a-f]{16}',node['float64_bits']),'Exact binary64 scalar bits')
                scalar_bits+=1;return
            raise ValueError('Unknown typed node')
        require(node is None or type(node) in (str,int,bool),'Every floating scalar requires exact bits')
    visit(tree)
    require(set(descriptors)=={'a'+str(i) for i in range(len(descriptors))},'Noncontiguous writer array identities')
    archive=folder/'arrays.npz';require(archive.stat().st_size<=MAX_BYTES,'Archive compressed size bound')
    headers={};payloads={};numeric_scalars=0
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        require(len(entries)<=MAX_MEMBERS and sum(r.file_size for r in entries)<=MAX_BYTES,'Expanded archive bound')
        names=[r.filename for r in entries]
        require(len(names)==len(set(names)) and set(names)=={key+'.npy' for key in descriptors},'Exact unique typed NPZ owners')
        for info in entries:
            require(not info.is_dir() and not info.flag_bits&1,'Plain unencrypted NPY member required')
            key=info.filename[:-4];data=z.read(info);header=array_header(data);desc=descriptors[key]
            require(desc==dict(array=key,dtype=header['dtype'],shape=list(header['shape'])),'Typed descriptor/header mismatch')
            headers[key]=dict(dtype=header['dtype'],shape=list(header['shape']),fortran=header['fortran'],
                payload_sha256=hashlib.sha256(memoryview(data)[header['offset']:]).hexdigest(),owner_path=paths[key])
            numeric_scalars+=header['count']
            if decoded:payloads[key]=dict(__typed_array__=True,**headers[key])
    result=dict(kind=KIND,complete=True,manifest_sha256=sha(manifest),files=row['files'],arrays=len(descriptors),
        numeric_scalars=numeric_scalars,exact_float64_scalar_nodes=scalar_bits,typed_nodes=nodes,typed_headers=headers,
        nonfinite_bits_preserved=True,no_numeric_recomputation=True)
    if decoded:
        def decode(node):
            if type(node) is dict:
                if set(node)=={'mapping'}:return {key:decode(value) for key,value in node['mapping']}
                if set(node)=={'sequence'}:return [decode(value) for value in node['sequence']]
                if set(node)=={'float64_bits'}:return struct.unpack('<d',bytes.fromhex(node['float64_bits']))[0]
                return {k:v for k,v in payloads[node['array']].items() if k!='owner_path'}
            return node
        return result,decode(tree)
    return result
