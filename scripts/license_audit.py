# SPDX-License-Identifier: AGPL-3.0-only
"""Collect version-specific license/source evidence without executing downloads.

Fetched archives are retained; each hash is recorded for component provenance.
"""
import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import os
import re
import ssl
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'audit/license-audit'
SOURCES=ROOT/'release/dependency-sources'
RUNTIME=('Pillow','PyMuPDF','SimConnect','reportlab','charset-normalizer')


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def get_json(url):
    request=urllib.request.Request(url,headers={'User-Agent':'A350FuelReporter-license-audit','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=40) as response: return json.load(response)


def fetch(url,path,expected=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.is_file():
        request=urllib.request.Request(url,headers={'User-Agent':'A350FuelReporter-license-audit'})
        with urllib.request.urlopen(request,timeout=45) as response, path.with_suffix(path.suffix+'.part').open('wb') as output:
            while chunk:=response.read(1024*1024): output.write(chunk)
        path.with_suffix(path.suffix+'.part').replace(path)
    sha=digest(path)
    if expected and sha!=expected: raise RuntimeError(f'Upstream digest mismatch: {path.name}')
    return {'url':url,'filename':path.name,'sha256':sha,'bytes':path.stat().st_size,
            'verification':'upstream SHA-256 matched' if expected else 'TLS download; locally recorded SHA-256'}


def repo_source(repo,ref,label):
    info=get_json(f'https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref,safe="")}')
    commit=info['sha']
    record=fetch(f'https://codeload.github.com/{repo}/tar.gz/{commit}',SOURCES/f'{label}-{commit[:12]}.tar.gz')
    record.update(repository=repo,ref=ref,commit=commit)
    return record


def fetch_evidence():
    AUDIT.mkdir(parents=True,exist_ok=True)
    records={'wheels':[],'additional_sources':[],'errors':[]}
    order={tag:n for n,tag in enumerate(sys_tags())}
    for name in RUNTIME:
        version=metadata.version(name)
        info=get_json(f'https://pypi.org/pypi/{name}/{version}/json')
        options=[]
        for item in info['urls']:
            if item['packagetype']!='bdist_wheel': continue
            tags=parse_wheel_filename(item['filename'])[3]
            ranks=[order[tag] for tag in tags if tag in order]
            if ranks: options.append((min(ranks),item))
        item=min(options,key=lambda pair:pair[0])[1]
        record=fetch(item['url'],AUDIT/item['filename'],item['digests']['sha256'])
        record.update(name=name,version=version)
        records['wheels'].append(record)
        print(f'Wheel evidence: {name} {version}',flush=True)
    embed=fetch('https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip',AUDIT/'python-3.11.9-embed-amd64.zip')
    records['cpython_embed']=embed
    jobs=[('python/cpython-source-deps',tag,'CPython-'+tag) for tag in
          ('bzip2-1.0.8','xz-5.2.5','zlib-1.3.1','libffi-3.4.4','openssl-3.0.13')]
    jobs.append(('python-pillow/Pillow','12.3.0','Pillow-full-build-source'))
    for repo,ref,label in jobs:
        try:
            record=repo_source(repo,ref,label)
            records['additional_sources'].append(record)
            print(f'Native/build source: {label}',flush=True)
        except Exception as error:
            records['errors'].append({'component':label,'error':str(error)})
            print(f'Unresolved download: {label}: {error}',flush=True)
    (AUDIT/'fetch.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    return records


def archive_hashes(path):
    result={}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith('/'): continue
            sha=hashlib.sha256(archive.read(name)).hexdigest()
            result.setdefault(sha,[]).append(name)
    return result


def installed_indexes():
    indexes={}
    for name in RUNTIME:
        dist=metadata.distribution(name)
        by_hash={}
        for member in dist.files or []:
            if str(member).endswith('.pyc'): continue
            path=Path(dist.locate_file(member))
            if path.is_file(): by_hash.setdefault(digest(path),[]).append(str(member).replace('\\','/'))
        indexes[name]=by_hash
    return indexes


def fetch_pillow_sources():
    records=json.loads((AUDIT/'fetch.json').read_text())
    full=next(x for x in records['additional_sources'] if x.get('repository')=='python-pillow/Pillow')
    with tarfile.open(SOURCES/full['filename']) as archive:
        member=next(x for x in archive if x.name.endswith('/.github/dependencies.json'))
        versions=json.load(archive.extractfile(member))
    cache=get_json('https://api.github.com/repos/python-pillow/pillow-depends/commits/main')['sha']
    names={'brotli':'brotli-{v}.tar.gz','freetype':'freetype-{v}.tar.gz',
           'jpegturbo':'libjpeg-turbo-{v}.tar.gz','lcms2':'lcms2-{v}.tar.gz',
           'libavif':'libavif-{v}.tar.gz','libpng':'libpng-{v}.tar.gz',
           'libwebp':'libwebp-{v}.tar.gz','openjpeg':'openjpeg-{v}.tar.gz',
           'tiff':'tiff-{v}.tar.gz','xz':'xz-{v}.tar.gz','zlib-ng':'zlib-ng-{v}.tar.gz'}
    extra=[]
    for component,template in names.items():
        filename=template.format(v=versions[component])
        try:
            url=f'https://raw.githubusercontent.com/python-pillow/pillow-depends/{cache}/{filename}'
            record=fetch(url,SOURCES/filename)
            record.update(component=component,version=versions[component],
                          upstream_cache_commit=cache,build_recipe_commit=full['commit'])
            extra.append(record)
            print(f'Pillow native source: {filename}',flush=True)
        except Exception as error:
            extra.append({'component':component,'filename':filename,'error':str(error)})
            print(f'Unresolved Pillow source: {filename}: {error}',flush=True)
    records['pillow_native_sources']=extra
    (AUDIT/'fetch.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


def fetch_remaining_sources():
    records=json.loads((AUDIT/'fetch.json').read_text())
    extra=[]
    for repo,ref,label in (('zlib-ng/zlib-ng','2.3.3','zlib-ng-2.3.3'),
                           ('videolan/dav1d','1.5.3','dav1d-1.5.3')):
        try:
            record=repo_source(repo,ref,label)
            if label.startswith('dav1d') and not record['commit'].startswith('b546257'):
                raise RuntimeError('dav1d source tag does not match reported binary commit')
            extra.append(record)
            print(f'Additional source: {label}',flush=True)
        except Exception as error: extra.append({'component':label,'error':str(error)})
    try:
        record=fetch('https://aomedia.googlesource.com/aom/+archive/refs/tags/v3.14.1.tar.gz',SOURCES/'aom-3.14.1.tar.gz')
        record.update(component='aom',version='3.14.1')
        extra.append(record)
        print('Additional source: aom-3.14.1',flush=True)
    except Exception as error: extra.append({'component':'aom-3.14.1','error':str(error)})
    records['remaining_sources']=extra
    (AUDIT/'fetch.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


def map_binaries():
    records=json.loads((AUDIT/'fetch.json').read_text())
    wheels={item['name']:archive_hashes(AUDIT/item['filename']) for item in records['wheels']}
    installed=installed_indexes()
    cpython=archive_hashes(AUDIT/records['cpython_embed']['filename'])
    crt=json.loads((ROOT/'licenses/Microsoft-runtime/runtime.json').read_text())
    crt_hashes={item['sha256']:item for item in crt['files']}
    binary=ROOT/'dist/A350FuelReporter'
    mappings=[]
    for path in sorted(binary.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in ('.dll','.pyd'): continue
        sha=digest(path)
        evidence=[]
        for name,hashes in wheels.items():
            if sha in hashes:
                evidence.append({'upstream':name,'wheel_members':hashes[sha],
                                 'installed_match':sha in installed[name]})
        if sha in cpython: evidence.append({'upstream':'CPython-3.11.9-official-embed','members':cpython[sha]})
        if sha in crt_hashes: evidence.append({'upstream':'Microsoft-Visual-Studio-stable-Redist',
                                              'origin':crt_hashes[sha]['origin']})
        if evidence: status='exact-artifact-match'
        elif path.name.lower().startswith(('api-ms-win-','vcruntime','msvcp')) or path.name.lower()=='ucrtbase.dll':
            status='Microsoft-runtime-license-review'
        else: status='unmapped'
        mappings.append({'path':path.relative_to(binary).as_posix(),'sha256':sha,'bytes':path.stat().st_size,
                         'status':status,'evidence':evidence})
    result={'binary_count':len(mappings),'mapped':sum(bool(x['evidence']) for x in mappings),
            'unmapped':[x['path'] for x in mappings if x['status']=='unmapped'],
            'mappings':mappings}
    (ROOT/'docs/BINARY_SOURCE_MAP.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='mappings'},indent=2))
    return result


def source_notices():
    dest=ROOT/'licenses/Native-source'; dest.mkdir(parents=True,exist_ok=True)
    copied=[]
    for path in sorted(SOURCES.glob('*.tar.*')):
        with tarfile.open(path) as archive:
            for member in archive:
                name=Path(member.name).name
                if not member.isfile() or member.size>2_000_000: continue
                if not re.search(r'^(COPYING|LICEN[CS]E|NOTICE|AUTHORS|PATENTS|FTL\.TXT|GPLv2\.TXT)',name,re.I): continue
                if Path(name).suffix.lower() in ('.py','.c','.h','.js','.html','.patch','.in'): continue
                content=archive.extractfile(member).read()
                filename=hashlib.sha256((path.name+'/'+member.name).encode()).hexdigest()[:16]+'-'+name
                (dest/filename).write_bytes(content)
                copied.append({'archive':path.name,'member':member.name,'file':filename,
                               'sha256':hashlib.sha256(content).hexdigest()})
    (dest/'inventory.json').write_text(json.dumps(copied,indent=2),encoding='utf-8')
    print(f'Copied {len(copied)} source notices.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--map',action='store_true')
    parser.add_argument('--pillow-sources',action='store_true')
    parser.add_argument('--remaining-sources',action='store_true')
    parser.add_argument('--notices',action='store_true')
    args=parser.parse_args()
    if args.fetch: fetch_evidence()
    if args.pillow_sources: fetch_pillow_sources()
    if args.remaining_sources: fetch_remaining_sources()
    if args.map: map_binaries()
    if args.notices: source_notices()


if __name__=='__main__': main()
