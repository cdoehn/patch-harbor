"""Check built distributions and stable release assets without publishing them."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from scripts.build_release import _audit_release_artifacts, _wheel_contract, canonical_pyz_from_wheel


def require(value, message):
    if not value:
        raise ValueError(message)


def distribution_names(version):
    """Name local stable or development builds without granting release eligibility."""
    require(isinstance(version, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:\.dev[0-9]+)?', version),
            'distribution verification requires a stable or development package version')
    return (f'patchharbor-{version}.pyz', f'patchharbor-{version}-py3-none-any.whl',
            f'patchharbor-{version}.tar.gz')


def names(version):
    require(isinstance(version, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version),
            'release requires an explicit stable package version')
    return (*distribution_names(version), 'runtime-manifest.json', 'SHA256SUMS')


def run(command, cwd, env=None):
    done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
    require(done.returncode == 0, 'release verification process failed: '+done.stdout+done.stderr)
    return done.stdout


PROBE = r'''
from dataclasses import asdict
from hashlib import sha256
from io import StringIO
import json, os, platform, sys
from pathlib import Path
selected, expected_sha, output, version, route = sys.argv[1:]
if route == 'pyz':
    assert sha256(Path(selected).read_bytes()).hexdigest() == expected_sha
if selected:
    sys.path.insert(0, selected)
# Capture the verifier's own host facts before guarding runtime operations.
# Windows platform.uname() performs a local socket.gethostname() lookup.
host = {'system': platform.system(), 'machine': platform.machine(),
        'python': platform.python_version(), 'implementation': platform.python_implementation()}
def audit(event, args):
    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn')) or event == 'os.system':
        raise AssertionError('export attempted external work: '+event)
sys.addaudithook(audit)
from patchharbor import api, cli
import patchharbor
assert patchharbor.__version__ == version
if selected:
    assert api.__file__.startswith(selected + os.sep), api.__file__
else:
    assert Path(api.__file__).is_relative_to(Path(sys.prefix)), api.__file__
out = Path(output)
first, second = out/'api', out/'cli'
first.mkdir(); second.mkdir()
result = api.export_runtime(first)
assert result.sha256 == expected_sha and result.path.read_bytes()
stdout = StringIO()
assert cli.main(['runtime','export','--output-dir',str(second),'--json'], stdout=stdout) == 0
document = json.loads(stdout.getvalue())
assert document['success'] and document['result']['sha256'] == expected_sha
assert Path(document['result']['path']).read_bytes() == result.path.read_bytes()
assert document['result']['distribution_version'] == result.distribution_version == version
assert result.requires_python == '>=3.10' and result.profile == 'patchharbor-core-no-watcher-v1'
assert 'patchharbor_watcher' not in sys.modules
facts = asdict(result); facts['path'] = str(result.path)
print(json.dumps({'runtime': facts, 'capabilities': asdict(api.integration_capabilities()),
                 'host': host}))
'''


def verify_distributions(directory: Path, version: str, workspace: Path) -> dict:
    """Install actual wheel and sdist offline; exercise the public API and CLI."""
    pyz_name, wheel_name, sdist_name = distribution_names(version)
    directory = directory.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    pyz, wheel, sdist = (directory/n for n in (pyz_name, wheel_name, sdist_name))
    _audit_release_artifacts(wheel, sdist)
    require(_wheel_contract(wheel).version == version, 'requested/distribution version mismatch')
    expected = sha256(pyz.read_bytes()).hexdigest()
    environment = {k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME') and not k.startswith('GIT_')}
    environment.update(PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_CONFIG_FILE=os.devnull)
    # The wheel uses a real fresh venv; the sdist uses pip's standard target install
    # with already available build dependencies, never a network build environment.
    venv = workspace/'venv'
    run([sys.executable,'-m','venv','--without-pip',str(venv)],workspace,environment)
    python = venv/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    run([sys.executable,'-m','pip','--python',str(python),'install','--no-index','--no-deps',
         '--no-cache-dir','--no-compile',str(wheel)],workspace,environment)
    target = workspace/'sdist-install'
    run([sys.executable,'-m','pip','install','--target',str(target),'--no-index','--no-deps',
         '--no-cache-dir','--no-compile','--no-build-isolation',str(sdist)],workspace,environment)
    offline = dict(environment, PATH='')
    for key in ('HOME','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','APPDATA','LOCALAPPDATA'):
        offline[key] = str(workspace/'absent-user-state')
    proofs = {}
    for route, interpreter, selected in (('wheel',python,''),('sdist',sys.executable,str(target)),
                                        ('pyz',sys.executable,str(pyz))):
        output=workspace/route;output.mkdir()
        command=[str(interpreter),'-I','-B']
        if route != 'wheel': command.append('-S')
        proof=json.loads(run([*command,'-c',PROBE,selected,expected,str(output),version,route],workspace,offline))
        require(proof['runtime']['sha256'] == expected, 'export/build PYZ mismatch')
        for name in ('api','cli'):
            require((output/name/pyz_name).read_bytes()==pyz.read_bytes(), 'export bytes differ')
        proofs[route]=proof
    # Exercise the actual console launcher and the PYZ's __main__ as well.
    for route, command in (('console',[str(venv/('Scripts/patchharbor.exe' if os.name=='nt' else 'bin/patchharbor'))]),
                           ('pyz-main',[sys.executable,'-I','-S','-B',str(pyz)])):
        output=workspace/route;output.mkdir()
        doc=json.loads(run([*command,'runtime','export','--output-dir',str(output),'--json'],workspace,offline))
        require(doc['success'] and doc['result']['sha256']==expected, 'launcher export failed')
        require((output/pyz_name).read_bytes()==pyz.read_bytes(),'launcher bytes differ')
    require(not (workspace/'absent-user-state').exists(), 'export created user state')
    return proofs


def write_manifest(directory: Path, version: str, commit: str, proof: dict) -> dict:
    require(re.fullmatch(r'[0-9a-f]{40}',commit), 'full source commit required')
    required=names(version)
    runtime=proof['runtime']
    require(runtime['distribution_version']==version, 'runtime version mismatch')
    raw=(directory/required[0]).read_bytes()
    require(runtime['sha256']==sha256(raw).hexdigest() and runtime['size']==len(raw), 'runtime proof mismatch')
    document={'marker':'patchharbor-runtime-release','format_version':1,'version':version,
              'source_commit':commit,'tag':'v'+version,
              'runtime':dict(filename=required[0], **{k:runtime[k] for k in
                  ('size','sha256','profile','requires_python','content_id')}),
              'integration_capabilities':proof['capabilities'],'capability_host':proof['host']}
    with (directory/'runtime-manifest.json').open('x',encoding='utf-8') as f:
        json.dump(document,f,sort_keys=True,indent=2);f.write('\n')
    checksums=''.join(sha256((directory/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in sorted(required[:-1]))
    with (directory/'SHA256SUMS').open('x',encoding='ascii') as f:f.write(checksums)
    verify_assets(directory,version,commit)
    return document


def verify_assets(directory: Path, version: str, commit: str) -> dict:
    required=names(version)
    require(re.fullmatch(r'[0-9a-f]{40}',commit), 'full source commit required')
    require({p.name for p in directory.iterdir()}==set(required), 'release asset set incomplete or unexpected')
    require(all((directory/n).is_file() and not (directory/n).is_symlink() for n in required),'nonregular asset')
    document=json.loads((directory/'runtime-manifest.json').read_bytes())
    require(set(document)=={'marker','format_version','version','source_commit','tag','runtime',
                           'integration_capabilities','capability_host'},'manifest fields differ')
    require(document['marker']=='patchharbor-runtime-release' and type(document['format_version']) is int
            and document['format_version']==1 and document['version']==version
            and document['source_commit']==commit and document['tag']=='v'+version,'release binding mismatch')
    runtime=document['runtime'];raw=(directory/required[0]).read_bytes()
    require(set(runtime)=={'filename','size','sha256','profile','requires_python','content_id'},'runtime fields differ')
    require(runtime['filename']==required[0] and type(runtime['size']) is int and runtime['size']==len(raw)
            and runtime['sha256']==sha256(raw).hexdigest(),'runtime bytes mismatch')
    require(runtime['profile']=='patchharbor-core-no-watcher-v1' and runtime['requires_python']=='>=3.10'
            and re.fullmatch(r'[0-9a-f]{64}',runtime['content_id']), 'invalid runtime contract')
    caps=document['integration_capabilities'];host=document['capability_host']
    require(set(caps)=={'contract_version','snapshot_contract_version','guarded_apply_contract_version',
                       'safe_reference_contract_version'},'incomplete capability facts')
    require(all(type(caps[k]) is int and caps[k]==v for k,v in
                {'contract_version':2,'snapshot_contract_version':2,'guarded_apply_contract_version':1}.items()), 'unsupported integration contract')
    require(caps['safe_reference_contract_version'] is None or
            (type(caps['safe_reference_contract_version']) is int and caps['safe_reference_contract_version']==1),
            'invalid safe-reference capability')
    require(set(host)=={'system','machine','python','implementation'} and all(type(v) is str and v for v in host.values()),
            'missing capability host')
    expected=''.join(sha256((directory/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in sorted(required[:-1]))
    require((directory/'SHA256SUMS').read_text(encoding='ascii')==expected,'checksum inventory or bytes mismatch')
    _audit_release_artifacts(directory/required[1],directory/required[2])
    require(_wheel_contract(directory/required[1]).version==version,'wheel version differs')
    recipe, canonical = canonical_pyz_from_wheel(directory/required[1])
    require(raw == canonical and recipe.version == version and recipe.content_id == runtime['content_id']
            and recipe.requires_python == runtime['requires_python'], 'canonical wheel/PYZ/manifest mismatch')
    return document
