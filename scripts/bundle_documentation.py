# SPDX-License-Identifier: AGPL-3.0-only
"""Add reviewed documentation to an existing Windows ZIP without rebuilding code."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / 'release/0.7.11-rc2'
ORIGINAL = RELEASE / 'A350FuelReporter-0.7.11-rc2-windows-x64-LOCAL-RC.zip'
OUTPUT = RELEASE / 'A350FuelReporter-0.7.11-rc2-windows-x64-LOCAL-RC-WITH-GUIDES.zip'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    docs = RELEASE / 'Documentation'
    additions = {f'A350FuelReporter/Documentation/{p.name}': p.read_bytes()
                 for p in sorted(docs.iterdir()) if p.is_file()}
    assert sum(name.endswith('.pdf') for name in additions) == 2
    additions['A350FuelReporter/START-HERE.txt'] = (
        'A350 Fuel Evidence Reporter 0.7.11-rc2\r\n'
        'Extract the whole ZIP, then run A350FuelReporter.exe.\r\n'
        'Keep _internal next to the EXE. Read README-WINDOWS.txt.\r\n\r\n'
        'English illustrated User Guide (16 pages):\r\n'
        'Documentation\\A350_Fuel_Evidence_Reporter_User_Guide_EN.pdf\r\n\r\n'
        'Technical reference for iniBuilds reviewers (13 pages):\r\n'
        'Documentation\\A350_Fuel_Evidence_Reporter_iniBuilds_Data_Reference_EN.pdf\r\n\r\n'
        'This adds documentation only. The application has not been rebuilt.\r\n'
        'Known rc2 issue: true_track_deg contains radians in the reviewed path;\r\n'
        'the technical reference explains how to derive degrees.\r\n'
        '\r\nExport creates a local download only, not a support submission.\r\n'
        'No recordings or reports are automatically sent to iniBuilds, Discord,\r\n'
        'a forum or a cloud service. Choose and attach files manually yourself.\r\n'
        'The optional SimBrief OFP fetch does not upload recorded telemetry.\r\n\r\n'
        'This remains a local validation candidate. See the release checklist.\r\n'
    ).encode('utf-8')
    with zipfile.ZipFile(ORIGINAL) as old, zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as new:
        assert not set(old.namelist()) & set(additions)
        for entry in old.infolist():
            new.writestr(entry, old.read(entry.filename))
        for name, data in additions.items():
            new.writestr(name, data)
    with zipfile.ZipFile(ORIGINAL) as old, zipfile.ZipFile(OUTPUT) as new:
        assert new.testzip() is None
        assert len(new.namelist()) == len(set(new.namelist()))
        assert len(new.namelist()) == len(old.namelist()) + len(additions)
        assert all(digest(old.read(n)) == digest(new.read(n)) for n in old.namelist())
        assert all(new.read(n) == data for n, data in additions.items())
        assert not any(Path(n).name.lower() in {'case.json', 'config.json', 'engine_sources.json',
                                              'continuous_5s_telemetry.csv'} for n in new.namelist())
        exe_hash = digest(new.read('A350FuelReporter/A350FuelReporter.exe'))
    manifest = json.loads((RELEASE/'release-manifest.json').read_text())
    manifest.update(documentation_bundle=True,
                    base_windows_zip=ORIGINAL.name,
                    base_windows_zip_sha256=digest(ORIGINAL.read_bytes()),
                    windows_zip=OUTPUT.name,
                    windows_zip_sha256=digest(OUTPUT.read_bytes()),
                    executable_unchanged=True,
                    executable_sha256=exe_hash)
    manifest['files'] += [{'path': name.removeprefix('A350FuelReporter/'),
                          'sha256': digest(data), 'bytes': len(data)}
                         for name, data in additions.items()]
    manifest_path = RELEASE/'release-manifest-with-guides.json'
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    hashes = ''.join(f'{digest(p.read_bytes())}  {p.name}\n' for p in (OUTPUT, manifest_path))
    (RELEASE/'SHA256SUMS-WITH-GUIDES.txt').write_text(hashes, encoding='ascii')
    print(json.dumps({'zip': str(OUTPUT.resolve()), 'bytes': OUTPUT.stat().st_size,
                      'original_members_verified': len(old.infolist()), 'added_files': len(additions),
                      'exe_sha256': exe_hash, 'verification': 'passed'}, indent=2))

if __name__ == '__main__':
    main()
