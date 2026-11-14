# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

datas = [('static', 'static'), ('LICENSE', '.'), ('NOTICE', '.'),
         ('THIRD_PARTY_NOTICES.md', '.'), ('SOURCE_ACCESS.md', '.'), ('licenses', 'licenses')]
binaries = []
hiddenimports = ['SimConnect']
tmp_ret = collect_all('SimConnect')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Windows 10/11 supply UCRT/API sets. Avoid collecting unrelated app-local copies
# from the build machine's PATH, and use only our audited official CRT inputs.
runtime = Path(SPECPATH) / 'build-inputs' / 'msvc-runtime'
crt_names = {'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'}
for name in crt_names:
    if not (runtime/name).is_file():
        raise RuntimeError('Run scripts/prepare_windows_runtime.py before building')
a.binaries = [item for item in a.binaries
              if not Path(item[0]).name.lower().startswith('api-ms-win-')
              and Path(item[0]).name.lower() != 'ucrtbase.dll'
              and Path(item[0]).name.lower() not in crt_names]
a.binaries += [(name, str(runtime/name), 'BINARY') for name in sorted(crt_names)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='A350FuelReporter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='A350FuelReporter',
)
