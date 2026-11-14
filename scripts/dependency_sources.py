# SPDX-License-Identifier: AGPL-3.0-only
"""Fetch pinned upstream source archives without installing or executing them."""
import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    packages={}
    for file in ('requirements-lock.txt','requirements-build.txt'):
        for line in (ROOT/file).read_text().splitlines():
            if re.match(r'^[A-Za-z].*==',line):
                name,version=line.split(';')[0].strip().split('==')
                packages[name]=version
    records=[]
    target=ROOT/'release'/'dependency-sources'
    if args.download: target.mkdir(parents=True,exist_ok=True)
    for name,version in sorted(packages.items()):
        endpoint=f'https://pypi.org/pypi/{name}/{version}/json'
        with urllib.request.urlopen(endpoint,timeout=25) as response: meta=json.load(response)
        sources=[file for file in meta['urls'] if file['packagetype']=='sdist']
        if len(sources)!=1: raise RuntimeError(f'Expected exactly one sdist: {name}')
        item=sources[0]
        if urllib.parse.urlparse(item['url']).hostname!='files.pythonhosted.org':
            raise RuntimeError('Unexpected source host')
        if Path(item['filename']).name!=item['filename']: raise RuntimeError('Unsafe source filename')
        record={'name':name,'version':version,'filename':item['filename'],'url':item['url'],
                'sha256':item['digests']['sha256'],'bytes':item['size'],
                'metadata_url':endpoint,'download_verified':False}
        if args.download:
            dest=target/item['filename']
            if not dest.exists():
                with urllib.request.urlopen(item['url'],timeout=40) as response, dest.open('wb') as out:
                    while chunk:=response.read(1024*1024): out.write(chunk)
            with dest.open('rb') as source_file:
                digest=hashlib.file_digest(source_file,'sha256').hexdigest()
            if digest!=record['sha256'] or dest.stat().st_size!=record['bytes']:
                raise RuntimeError(f'Source digest/size mismatch: {name}')
            record['download_verified']=True
        records.append(record)
        print(f'{name} {version}: {item["size"]:,} bytes; downloaded={record["download_verified"]}',flush=True)
    document={'status':'Upstream sdists only; native source completeness/binary correspondence not certified',
              'packages':records,'additional_source_review':['MuPDF nested source/native dependencies',
              'CPython 3.11.9 and bundled dependencies','Microsoft SimConnect.dll/runtime terms',
              'ReportLab font preferred source forms']}
    if args.download:
        extra=[]
        for name,version,url in (
            ('CPython','3.11.9','https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tar.xz'),
            ('MuPDF','1.28.2','https://mupdf.com/downloads/archive/mupdf-1.28.2-source.tar.gz')):
            record={'name':name,'version':version,'url':url,'download_verified':False}
            try:
                dest=target/Path(urllib.parse.urlparse(url).path).name
                if not dest.exists():
                    with urllib.request.urlopen(url,timeout=40) as response, dest.open('wb') as out:
                        while chunk:=response.read(1024*1024): out.write(chunk)
                with dest.open('rb') as source_file:
                    digest=hashlib.file_digest(source_file,'sha256').hexdigest()
                record.update(filename=dest.name,bytes=dest.stat().st_size,sha256=digest,
                              downloaded=True,verification='TLS retrieval and recorded digest; upstream signature not checked')
                print(f'{name} {version}: downloaded {dest.stat().st_size:,} bytes',flush=True)
            except Exception as error:
                record['error']=str(error)
                print(f'{name}: {error}',flush=True)
            extra.append(record)
        document['additional_archives']=extra
    (ROOT/'docs'/'DEPENDENCY_SOURCES.json').write_text(json.dumps(document,indent=2),encoding='utf-8')
    if args.download: (target/'manifest.json').write_text(json.dumps(document,indent=2),encoding='utf-8')


if __name__=='__main__': main()
