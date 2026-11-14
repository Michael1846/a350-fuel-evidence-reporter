# SPDX-License-Identifier: AGPL-3.0-only
"""Conservative, local aircraft identity and add-on manifest inspection.

The SimConnect aircraft title/model identifies the *selected aircraft*.
Package manifests identify an installed package candidate; they do not prove
that the simulator loaded the same revision when content is streamed or layered.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


def as_text(v):
    if isinstance(v, bytes):
        return v.decode('utf-8',errors='replace').split('\0')[0].strip()
    if v is None:return ''
    return str(v).strip().split('\0')[0]


def detect_variant(title='',model='',atc_type=''):
    data=' '.join(as_text(v) for v in (title,model,atc_type)).upper()
    compact=re.sub(r'[^A-Z0-9]', '', data)
    # Do not make the ULR designation from only 'A350'.
    is_1000=bool(re.search(r'A350\W*1000|A35K',data)) or 'A3501000' in compact
    is_900=bool(re.search(r'A350\W*900|A359',data)) or 'A350900' in compact
    is_a350=bool(re.search(r'A350|A35[K9]',data))
    if not is_a350:return {'family':'','variant':'','cabin':''}
    if is_1000 and is_900:variant=''
    elif is_1000:variant='A350-1000'
    elif is_900:variant='A350-900 ULR' if 'ULR' in data else 'A350-900'
    else:variant=''
    normalized=re.sub(r'[^a-z0-9]', '', as_text(title).lower())
    cabin=('No Cabin' if 'nocabin' in normalized else
           'Cabin' if ('cabin' in normalized and 'nocabin' not in normalized) else '')
    return {'family':'A350','variant':variant,'cabin':cabin}


def simulator_process():
    """Best-effort process name. An unavailable check is not an FS2024 claim."""
    if os.name!='nt':return ''
    try:
        res=subprocess.run(['tasklist','/fo','csv','/nh'],capture_output=True,text=True,timeout=3)
        procs=res.stdout.lower()
        if 'flightsimulator2024.exe' in procs:return 'MSFS 2024'
        if 'flightsimulator.exe' in procs:return 'MSFS 2020 or 2024 (not distinguished)'
    except (OSError,subprocess.TimeoutExpired):pass
    return ''


def discover_package_roots():
    """Use configured installed packages path, plus both standard Community roots."""
    roots=[]
    explicit=os.environ.get('A350_PACKAGES_ROOT','')
    if explicit:roots.extend(Path(x.strip()) for x in explicit.split(os.pathsep) if x.strip())
    appdata=Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming')))
    local=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))
    configs=[appdata/'Microsoft Flight Simulator 2024'/'UserCfg.opt',
             appdata/'Microsoft Flight Simulator'/'UserCfg.opt',
             local/'Packages'/'Microsoft.Limitless_8wekyb3d8bbwe'/'LocalCache'/'UserCfg.opt',
             local/'Packages'/'Microsoft.FlightSimulator_8wekyb3d8bbwe'/'LocalCache'/'UserCfg.opt']
    for cfg in configs:
        try:
            text=cfg.read_text(encoding='utf-8-sig',errors='replace')
            match=re.search(r'InstalledPackagesPath\s+"([^"]+)"',text,re.I)
            if match:roots.append(Path(match.group(1)))
        except OSError:pass
    roots.extend([appdata/'Microsoft Flight Simulator 2024'/'Packages',
                  local/'Packages'/'Microsoft.Limitless_8wekyb3d8bbwe'/'LocalCache'/'Packages'])
    unique=[];seen=set()
    for root in roots:
        for loc in (root,root/'Community',root/'Community2024',root/'Official',root/'Official'/'OneStore',root/'Official'/'Steam'):
            key=str(loc).lower()
            if key not in seen and loc.is_dir():seen.add(key);unique.append(loc)
    return unique


def manifest_versions(roots=None):
    """List installed A350 *package candidates* only. No recursive disk walk."""
    found=[]
    for root in (roots if roots is not None else discover_package_roots()):
        if not root.is_dir():continue
        # Some roots themselves refer directly to an aircraft package.
        candidates=[root] if (root/'manifest.json').exists() else []
        try:candidates.extend(x for x in root.iterdir() if x.is_dir() and re.search(r'inibuilds.*a350|aircraft.*a350',x.name,re.I))
        except OSError:pass
        for entry in candidates:
            path=entry/'manifest.json'
            if not path.is_file():continue
            try:obj=json.loads(path.read_text(encoding='utf-8-sig'))
            except (OSError,UnicodeError,ValueError):continue
            name=' '.join([entry.name,str(obj.get('title','')),str(obj.get('package_name',''))])
            if not re.search(r'a350',name,re.I):continue
            # Never use a version from a repaint/livery package as aircraft build.
            if re.search(r'liver(y|ies)|repaint|texture|scenery|soundpack',name,re.I):continue
            vers=as_text(obj.get('package_version') or obj.get('version'))
            if not re.fullmatch(r'\d+(?:\.\d+){1,4}',vers):continue
            found.append({'version':vers,'folder':entry.name,'path':str(path)})
    return found


def package_version(aircraft_family,roots=None):
    if aircraft_family!='A350':return {'version':'','status':'not_applicable','candidates':[]}
    candidates=manifest_versions(roots)
    distinct={p['version'] for p in candidates}
    if len(distinct)==1 and candidates:
        return {'version':next(iter(distinct)),'status':'manifest_candidate','candidates':candidates}
    if len(distinct)>1:
        return {'version':'','status':'ambiguous','candidates':candidates}
    return {'version':'','status':'not_found','candidates':[]}
