# SPDX-License-Identifier: AGPL-3.0-only
"""Assemble matched source/build evidence beside a prepared Windows candidate."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'release/dependency-sources'


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def inventory():
    original=json.loads((ROOT/'docs/DEPENDENCY_SOURCES.json').read_text())
    audit=json.loads((ROOT/'audit/license-audit/fetch.json').read_text())
    lookup={}
    for key in ('packages','additional_archives'):
        for item in original.get(key,[]): lookup[item['filename']]=item
    for key in ('additional_sources','pillow_native_sources','remaining_sources'):
        for item in audit.get(key,[]):
            if 'sha256' in item: lookup[item['filename']]=item
    files=[]
    for path in sorted(SOURCE.iterdir()):
        if not path.is_file() or path.name=='manifest.json': continue
        if path.name not in lookup: raise RuntimeError(f'Untracked source archive: {path.name}')
        record=lookup[path.name]
        digest=sha(path)
        if digest!=record['sha256']: raise RuntimeError(f'Source hash mismatch: {path.name}')
        files.append({'filename':path.name,'bytes':path.stat().st_size,'sha256':digest,
                      'url':record['url'],'upstream_commit':record.get('commit'),
                      'verification':record.get('verification','PyPI SHA-256 matched')})
    result={'version':'0.7.11-rc2','publisher':'Brazzor','archives':files,
            'technical_collection':'assembled; native rebuilds not independently reproduced',
            'system_library_binary_inputs':'Microsoft CRT retained under Microsoft terms; source not represented as available',
            'references':['BINARY_SOURCE_MAP.json','SOURCE_BUILD.md']}
    (ROOT/'docs/SOURCE_COMPONENTS.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result,audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory-only',action='store_true')
    parser.add_argument('--release',type=Path)
    args=parser.parse_args()
    data,audit=inventory()
    if args.inventory_only:
        print(f'Verified {len(data["archives"])} source archives.'); return
    if not args.release: parser.error('--release is required unless --inventory-only')
    release=args.release.resolve()
    application=release/'APPLICATION_SOURCE.zip'
    if not application.is_file(): raise RuntimeError('Package the application first')
    output=release/'CORRESPONDING_SOURCE.zip'
    if output.exists(): raise RuntimeError('Source package already exists')
    index=[]
    def add(archive,path,name):
        archive.write(path,name)
        index.append({'path':name,'sha256':sha(path),'bytes':path.stat().st_size})
    with zipfile.ZipFile(output,'w',zipfile.ZIP_STORED,allowZip64=True) as archive:
        add(archive,application,'APPLICATION_SOURCE.zip')
        add(archive,ROOT/'audit/license-audit/fetch.json','source-evidence/fetch.json')
        for record in data['archives']:
            add(archive,SOURCE/record['filename'],'upstream-sources/'+record['filename'])
        for record in audit['wheels']:
            add(archive,ROOT/'audit/license-audit'/record['filename'],'binary-build-inputs/wheels/'+record['filename'])
        for path in sorted((ROOT/'build-inputs/msvc-runtime').glob('*.dll')):
            add(archive,path,'binary-build-inputs/microsoft-crt/'+path.name)
        for name in ('LICENSE','NOTICE','SOURCE_ACCESS.md','THIRD_PARTY_NOTICES.md'):
            add(archive,ROOT/name,name)
        for name in ('SOURCE_BUILD.md','SOURCE_COMPONENTS.json','BINARY_SOURCE_MAP.json'):
            add(archive,ROOT/'docs'/name,'docs/'+name)
        archive.writestr('SOURCE_FILE_MANIFEST.json',json.dumps({'files':index,
            'application_source_sha256':sha(application)},indent=2))
    with zipfile.ZipFile(output) as archive:
        for record in index:
            with archive.open(record['path']) as stream:
                digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=record['sha256']: raise RuntimeError(f'Archive verification failed: {record["path"]}')
    manifest_path=release/'release-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest.update(corresponding_source_asset=output.name,corresponding_source_sha256=sha(output),
                    source_scope=data['technical_collection'])
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assets=[application,output,next(release.glob('*windows-x64-LOCAL-RC.zip')),manifest_path]
    (release/'SHA256SUMS.txt').write_text(''.join(f'{sha(path)}  {path.name}\n' for path in assets),encoding='utf-8')
    (ROOT/'audit/source-package-verification.json').write_text(json.dumps({'result':'passed',
        'source_archives':len(data['archives']),'manifest_entries':len(index),'asset_bytes':output.stat().st_size,
        'sha256':sha(output)},indent=2),encoding='utf-8')
    print(f'Verified source package: {output}\nSource archives: {len(data["archives"])}.')


if __name__=='__main__': main()
