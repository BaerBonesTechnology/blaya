"""Check GPU-first selection, CPU fallback and a real benchmark-scene render."""
import bpy
from blaya.render_benchmark_worker import choose, make_scene, select_device, candidates

cpu = dict(backend='CPU', id='CPU', name='CPU', threads=1, seconds=.1)
cuda = dict(backend='CUDA', id='test', name='GPU', threads=0, seconds=.3)
optix = dict(backend='OPTIX', id='test', name='GPU', threads=0, seconds=.2)
assert choose([cpu, cuda, optix]) == optix
assert choose([cpu, dict(optix, error='failed', seconds=-1)]) == cpu
assert choose([dict(backend='OPTIX', error='driver failure')]) is None
assert choose([]) is None
assert any(c['backend'] == 'CPU' for c in candidates())
scene = make_scene()
scene.render.resolution_x = scene.render.resolution_y = 32
scene.cycles.samples = 1
select_device(scene, cpu)
assert scene.cycles.device == 'CPU' and scene.render.threads == 1
assert scene.cycles.samples == 1 and scene.render.resolution_x == 32
assert bpy.ops.render.render() == {'FINISHED'}
import json
import os
import subprocess
import tempfile
from pathlib import Path
from blaya import render_benchmark_worker
before = (scene.as_pointer(), len(bpy.data.objects), scene.cycles.samples)
with tempfile.TemporaryDirectory() as directory:
    result = Path(directory) / 'result.json'
    child = subprocess.run([
        bpy.app.binary_path, '--background', '--factory-startup', '--disable-autoexec',
        '--python-exit-code', '1', '--python', render_benchmark_worker.__file__,
        '--', '--output', str(result),
    ], env=dict(os.environ, BLENDER_USER_CONFIG=str(Path(directory) / 'profile')),
        capture_output=True, text=True, timeout=120)
    assert child.returncode == 0, child.stdout + child.stderr
    report = json.loads(result.read_text(encoding='utf-8'))
    assert report['best'] and report['best']['seconds'] > 0, report
assert before == (scene.as_pointer(), len(bpy.data.objects), scene.cycles.samples)
print('PASS: GPU-first ranking, CPU fallback, quality preservation and benchmark scene render')
