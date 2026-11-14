# SPDX-License-Identifier: AGPL-3.0-only
"""Build a local candidate, using an allowlist for application source exports.

No upload, publishing, personal flight import or release clearance is performed.
"""
import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('static','tests','scripts','docs','licenses','.github')
ROOT_SUFFIXES = {'.py','.md','.txt','.spec','.bat'}


def version():
    for node in ast.parse((ROOT/'app.py').read_text(encoding='utf-8')).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='APP_VERSION' for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError('APP_VERSION not found')


def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build_inputs():
    files=list(ROOT.glob('*.py'))
    files += [ROOT/name for name in ('A350FuelReporter.spec','LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','SOURCE_ACCESS.md')]
    for name in ('static','licenses'):
        files.extend(p for p in (ROOT/name).rglob('*') if p.is_file())
    files.extend((ROOT/'build-inputs/msvc-runtime').glob('*.dll'))
    return {p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(files)}


def source_files():
    files = [p for p in ROOT.iterdir() if p.is_file() and (p.suffix in ROOT_SUFFIXES or p.name in ('LICENSE','NOTICE','.gitignore','.gitattributes'))]
    for name in SOURCE_DIRS:
        if (ROOT/name).is_dir():
            files.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    for path in sorted(files):
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise RuntimeError(f'Unsafe source path: {path}')
        yield path


def verify_environment():
    if sys.version_info[:3] != (3,11,9) or sys.maxsize <= 2**32 or os.name!='nt':
        raise RuntimeError('Inspected candidate environment is CPython 3.11.9, Windows x64')
    for filename in ('requirements-lock.txt','requirements-build.txt'):
        for line in (ROOT/filename).read_text().splitlines():
            if not line or line.startswith(('#','-')): continue
            name, expected = line.split(';')[0].strip().split('==')
            if metadata.version(name) != expected:
                raise RuntimeError(f'Unexpected {name} version; expected {expected}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--commit',default=None)
    args=parser.parse_args()
    verify_environment()
    release = args.output or ROOT/'release'/version()
    if release.exists(): raise RuntimeError('Output exists; choose a new --output directory')
    audit=ROOT/'audit'; audit.mkdir(exist_ok=True)
    if args.build:
        env=dict(os.environ, PYINSTALLER_CONFIG_DIR=str(ROOT/'.build-cache'))
        with (audit/'pyinstaller.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-B','-m','PyInstaller','--clean','--noconfirm','A350FuelReporter.spec'],
                                  cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        if result.returncode: raise RuntimeError('Build failed; see audit/pyinstaller.log')
        (audit/'build-inputs.json').write_text(json.dumps(build_inputs(),indent=2),encoding='utf-8')
    fingerprint=audit/'build-inputs.json'
    if not fingerprint.is_file() or json.loads(fingerprint.read_text(encoding='utf-8'))!=build_inputs():
        raise RuntimeError('Build inputs changed or provenance missing; rebuild with --build')
    binary=ROOT/'dist'/'A350FuelReporter'
    if not (binary/'A350FuelReporter.exe').is_file(): raise RuntimeError('Build the candidate first')
    if any(p.name.lower() in ('data','case.json','config.json','engine_sources.json') for p in binary.rglob('*')):
        raise RuntimeError('Personal/runtime data detected in build folder')
    release.mkdir(parents=True)
    source=release/'APPLICATION_SOURCE.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(): archive.write(path,path.relative_to(ROOT).as_posix())
    staged=release/'A350FuelReporter'
    shutil.copytree(binary,staged)
    for name in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','SOURCE_ACCESS.md','README-WINDOWS.txt','CHANGELOG.md'):
        shutil.copyfile(ROOT/name,staged/name)
    shutil.copytree(ROOT/'docs',staged/'docs')
    shutil.copyfile(source,staged/'APPLICATION_SOURCE.zip')
    files=[{'path':p.relative_to(staged).as_posix(),'sha256':sha256(p),'bytes':p.stat().st_size}
           for p in sorted(staged.rglob('*')) if p.is_file()]
    manifest={'version':version(),'source_commit':args.commit,'public_release':'technical acceptance checklist applies',
              'application_source_sha256':sha256(source),'python':sys.version,
              'source_scope':'Application source; matched dependency source asset supplied separately',
              'files':files}
    (release/'release-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    windows=release/f'A350FuelReporter-{version()}-windows-x64-LOCAL-RC.zip'
    with zipfile.ZipFile(windows,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staged.rglob('*')):
            if path.is_file(): archive.write(path,path.relative_to(release).as_posix())
    checksums=''.join(f'{sha256(p)}  {p.name}\n' for p in (source,windows,release/'release-manifest.json'))
    (release/'SHA256SUMS.txt').write_text(checksums,encoding='utf-8')
    print(f'Local candidate prepared: {release}\nSee technical release checklist')


if __name__=='__main__': main()
