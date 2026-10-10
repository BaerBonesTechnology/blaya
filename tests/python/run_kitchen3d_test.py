"""Isolated, timeout-bounded runner for background and GUI Kitchen 3D tests."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

parser=argparse.ArgumentParser()
parser.add_argument('--blender',required=True)
parser.add_argument('--script',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--ui',action='store_true')
args=parser.parse_args()
output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='kitchen3d-test-') as profile:
    env=os.environ.copy()
    env['BLENDER_USER_CONFIG']=profile
    env['KITCHEN3D_TEST_OUTPUT']=str(output)
    command=[args.blender,'--factory-startup','--python-exit-code','1']
    if not args.ui:command.append('--background')
    else:command+=['--window-geometry','0','0','1440','1000']
    command+=['--python',args.script]
    try:
        result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=180)
    except subprocess.TimeoutExpired as error:
        (output/'timeout.txt').write_text(str(error))
        raise SystemExit('Kitchen 3D test timed out')
    log=result.stdout+result.stderr
    (output/'test.log').write_text(log)
    print(log)
    failed=result.returncode or any(word in log for word in ('FAIL:', 'FAILED (', 'Traceback (most recent call last):'))
    if failed:raise SystemExit(result.returncode or 1)
    if not any(word in log for word in ('PASS:', '\nOK\n')):
        raise SystemExit('Test exited without a success marker')
