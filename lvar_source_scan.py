# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only inspection of textual aircraft files for candidate FF LVar names.

Does NOT decrypt archives, synthesize LVar names, write aircraft files, or
automatically select candidates. Candidate matches must be tested in the sim.
"""
import re
from pathlib import Path

EXTENSIONS={'.xml','.js','.html','.htm','.json','.cfg','.txt','.ini','.css','.ts','.jsx','.tsx'}
PATTERN=re.compile(rb'(?<![A-Za-z0-9_:])(?:L:1:|L:|Z:)[A-Za-z_][A-Za-z0-9_.:/-]{2,140}',re.I)
RELATED=re.compile(r'(?:FUEL.?FLOW|FLOW.?FUEL|(?:^|[_:])FF(?:[_:]|$)|ENG\d?.?FUEL)',re.I)

def scan(folder,max_files=3000,max_size=2_000_000,max_candidates=120):
    root=Path(folder).expanduser()
    if not root.is_dir():raise ValueError('Select a readable aircraft package directory')
    found={};files=0;truncated=False
    for item in root.rglob('*'):
        if files>=max_files or len(found)>=max_candidates:truncated=True;break
        if not item.is_file() or item.suffix.lower() not in EXTENSIONS or item.is_symlink():continue
        try:
            if item.stat().st_size>max_size:continue
            contents=item.read_bytes();files+=1
            for m in PATTERN.finditer(contents):
                name=m.group(0).decode('ascii',errors='ignore').rstrip(':')
                if RELATED.search(name):
                    found.setdefault(name,{'name':name,'file':str(item.relative_to(root))})
        except (PermissionError, OSError, ValueError):continue
    return {'candidates':list(found.values()),'scanned_text_files':files,'truncated':truncated,
            'warning':'Candidates are only text matches. They are not verified iniBuilds A350 fuel-flow outputs.'}
