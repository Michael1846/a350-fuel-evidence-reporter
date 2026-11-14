# SPDX-License-Identifier: AGPL-3.0-only
"""Run the regression suite with isolated synthetic data and a bounded timeout."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    audit=ROOT/'audit'; audit.mkdir(exist_ok=True)
    temp=ROOT/'.test-temp'; temp.mkdir(exist_ok=True)
    data=ROOT/'.test-data'; data.mkdir(exist_ok=True)
    env=dict(os.environ, A350_REPORTER_DATA_DIR=str(data),
             PYTHONDONTWRITEBYTECODE='1', TEMP=str(temp), TMP=str(temp))
    with (audit/'tests.log').open('w',encoding='utf-8') as log:
        run=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-v'],
                           cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    (audit/'test-result.json').write_text(json.dumps({'exit_code':run.returncode,'python':sys.version,
        'data':'isolated synthetic data','log':'tests.log'},indent=2),encoding='utf-8')
    print((audit/'tests.log').read_text(encoding='utf-8')[-2200:])
    raise SystemExit(run.returncode)


if __name__=='__main__': main()
