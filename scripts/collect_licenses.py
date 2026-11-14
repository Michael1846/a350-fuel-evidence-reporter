# SPDX-License-Identifier: AGPL-3.0-only
"""Copy installed distribution notices verbatim; record evidence, not approval."""
import hashlib
import importlib.metadata as metadata
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'licenses'


def main():
    DEST.mkdir(exist_ok=True)
    inventory = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        name = dist.metadata['Name']
        notices = []
        for member in dist.files or []:
            path = str(member).replace('\\', '/')
            if '..' in Path(path).parts or not re.search(r'(licen[cs]e|copying|notice|copyright|authors)', Path(path).name, re.I):
                continue
            if Path(path).suffix.lower() in ('.py', '.pyc', '.pyd', '.dll'): continue
            src = Path(dist.locate_file(member))
            if not src.is_file(): continue
            target = DEST / name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            notices.append({'path':target.relative_to(ROOT).as_posix(),
                            'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
        inventory.append({'name':name, 'version':dist.version,
                          'license_expression':dist.metadata.get('License-Expression'),
                          'license_metadata':dist.metadata.get('License'), 'notices':notices})
    pylicense = Path(sys.base_prefix) / 'LICENSE.txt'
    if not pylicense.is_file(): raise RuntimeError('CPython LICENSE.txt not found')
    (DEST / 'CPython').mkdir(exist_ok=True)
    shutil.copyfile(pylicense, DEST / 'CPython' / 'LICENSE.txt')
    (DEST / 'inventory.json').write_text(json.dumps({'python':sys.version, 'packages':inventory}, indent=2), encoding='utf-8')
    # Use the exact full AGPL text supplied with the inspected SimConnect wheel.
    sim = metadata.distribution('SimConnect')
    shutil.copyfile(sim.locate_file('SimConnect-0.4.26.dist-info/LICENSE'), ROOT / 'LICENSE')
    print(f'Collected notices for {len(inventory)} installed distributions and CPython.')


if __name__ == '__main__': main()
