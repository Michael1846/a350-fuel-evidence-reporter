# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise the packaged EXE locally, with synthetic data and no browser/SimConnect."""
import argparse
import hashlib
import io
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path)
    args=parser.parse_args()
    folder=args.folder.resolve()
    audit=ROOT/'audit'; audit.mkdir(exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='a350-smoke-',dir=audit) as temporary:
        data=Path(temporary)/'data'
        env=dict(os.environ,A350_REPORTER_PORT=str(port),A350_REPORTER_DATA_DIR=str(data),
                 A350_REPORTER_NO_BROWSER='1',PATH=os.environ['SystemRoot']+'\\System32')
        env.pop('PYTHONPATH',None); env.pop('PYTHONHOME',None)
        exe=folder/'A350FuelReporter.exe'
        with (audit/'exe-smoke.log').open('wb') as log:
            process=subprocess.Popen([str(exe)],cwd=temporary,env=env,stdout=log,stderr=log,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            url=f'http://127.0.0.1:{port}'
            def get(path):
                with opener.open(url+path,timeout=10) as response: return response.read()
            try:
                deadline=time.monotonic()+25
                while True:
                    if process.poll() is not None: raise RuntimeError('EXE exited before startup')
                    try:
                        info=json.loads(get('/api/version')); break
                    except (OSError,urllib.error.URLError):
                        if time.monotonic()>deadline: raise
                        time.sleep(.15)
                assert info['version']=='0.7.11-rc2', info
                assert b'Application source' in get('/')
                assert b'GNU AFFERO GENERAL PUBLIC LICENSE' in get('/legal/license')
                assert b'SimConnect.dll' in get('/legal/notices')
                assert b'CORRESPONDING_SOURCE.zip' in get('/legal/source-info')
                own_source=get('/legal/source.zip')
                assert hashlib.sha256(own_source).digest()==hashlib.sha256((folder/'APPLICATION_SOURCE.zip').read_bytes()).digest()
                request=urllib.request.Request(url+'/api/meta',data=b'{"flight":"SYNTHETIC-QA","dep":"EDDS","arr":"EDDV"}',
                    headers={'Content-Type':'application/json','Origin':url})
                with opener.open(request,timeout=5) as response: assert response.status==200
                pdf=get('/api/export.pdf'); assert pdf.startswith(b'%PDF')
                with zipfile.ZipFile(io.BytesIO(get('/api/export.zip'))) as archive:
                    assert 'A350_Fuel_Evidence_Report.pdf' in archive.namelist()
                    assert archive.read('A350_Fuel_Evidence_Report.pdf').startswith(b'%PDF')
                assert b'timestamp_utc' in get('/api/export-telemetry.csv')
                assert get('/api/export-waypoints.csv')
                assert (data/'case.json').is_file()
                assert json.loads((data/'case.json').read_text())['meta']['flight']=='SYNTHETIC-QA'
                assert not (folder/'data').exists()
                duplicate=subprocess.run([str(exe)],cwd=temporary,env=env,capture_output=True,timeout=12,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                assert b'already in use' in duplicate.stdout, duplicate.stdout
                assert json.loads(get('/api/version'))==info
                result={'version':info['version'],'result':'passed','data':'synthetic only',
                        'checks':['EXE with system-only PATH and no PYTHONPATH','HTTP UI/version',
                                  'license/notices/application-source download','local metadata save',
                                  'PDF/evidence ZIP/CSV export','external data directory','duplicate-instance protection'],
                        'not_tested':['clean Windows VM','live simulator','global hotkey','screenshots','SmartScreen'],
                        'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
                (audit/'exe-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                print(json.dumps(result,indent=2))
            finally:
                if process.poll() is None: process.terminate()
                process.wait(timeout=10)


if __name__=='__main__': main()
