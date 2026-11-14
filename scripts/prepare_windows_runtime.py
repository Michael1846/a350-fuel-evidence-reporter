# SPDX-License-Identifier: AGPL-3.0-only
"""Select unmodified x64 CRT files from an installed stable VS Redist directory."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES=('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll')


def main():
    program_files=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))
    locator=program_files/'Microsoft Visual Studio/Installer/vswhere.exe'
    installations=json.loads(subprocess.check_output([str(locator),'-products','*','-format','json','-utf8'],encoding='utf-8-sig'))
    candidates=[]
    for installation in installations:
        if installation.get('isPrerelease'): continue
        base=Path(installation['installationPath'])
        for path in (base/'VC/Redist/MSVC').glob('*/x64/Microsoft.VC*.CRT'):
            if all((path/name).is_file() for name in FILES):
                version=tuple(int(p) for p in path.parents[1].name.split('.'))
                candidates.append((version,path,base))
    if not candidates: raise RuntimeError('Install stable Visual Studio C++ Build Tools with x64 Redist files')
    _,origin,base=max(candidates,key=lambda item:item[0])
    target=ROOT/'build-inputs/msvc-runtime'; target.mkdir(parents=True,exist_ok=True)
    evidence=[]
    for name in FILES:
        source=origin/name
        shutil.copyfile(source,target/name)
        evidence.append({'name':name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                         'origin':'Visual Studio Build Tools/'+origin.relative_to(base).as_posix()+'/'+name})
    notices=ROOT/'licenses/Microsoft-runtime'; notices.mkdir(parents=True,exist_ok=True)
    (notices/'runtime.json').write_text(json.dumps({'component':'Microsoft Visual C++ x64 Runtime',
        'source':'Installed stable Visual Studio Build Tools VC/Redist tree',
        'redist_reference':'https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution',
        'license_reference':'https://visualstudio.microsoft.com/license-terms/',
        'files':evidence},indent=2),encoding='utf-8')
    print('Prepared official x64 CRT files:',', '.join(FILES))


if __name__=='__main__': main()
