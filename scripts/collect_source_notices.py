# SPDX-License-Identifier: AGPL-3.0-only
"""Read native-source notices without extracting or executing archive members."""
import hashlib
import json
import re
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'release/dependency-sources/mupdf-1.28.2-source.tar.gz'
    dest=ROOT/'licenses/MuPDF-source'; dest.mkdir(parents=True,exist_ok=True)
    notices=[]
    with tarfile.open(source) as archive:
        for member in archive:
            name=Path(member.name).name
            if not member.isfile() or member.size>2_000_000: continue
            if not re.search(r'^(COPYING|LICEN[CS]E|NOTICE|FTL\.TXT|GPLv2\.TXT)',name,re.I): continue
            if Path(name).suffix.lower() in ('.py','.c','.h','.js','.html'): continue
            content=archive.extractfile(member).read()
            filename=hashlib.sha256(member.name.encode()).hexdigest()[:12]+'-'+name
            (dest/filename).write_bytes(content)
            notices.append({'source_member':member.name,'copied_file':filename,
                            'sha256':hashlib.sha256(content).hexdigest()})
    (dest/'inventory.json').write_text(json.dumps(notices,indent=2),encoding='utf-8')
    print(f'Copied {len(notices)} upstream MuPDF/native dependency notice files.')


if __name__=='__main__': main()
