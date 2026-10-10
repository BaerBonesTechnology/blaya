"""Exercise the installed Python runtime, file I/O and Cycles CPU renderer."""
# SPDX-License-Identifier: GPL-2.0-or-later
import os
import sys
from pathlib import Path
import bpy
import numpy

output = Path(os.environ['KITCHEN3D_TEST_OUTPUT'])
expected_executable = {
    'win32': 'kitchen3d.exe',
    'linux': 'kitchen3d',
    'darwin': 'Kitchen 3D',
}[sys.platform]
assert Path(bpy.app.binary_path).name == expected_executable, bpy.app.binary_path
assert numpy.isfinite(numpy.eye(4)).all()
assert bpy.ops.blaya.isolate_selection.get_rna_type().identifier
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 1
scene.render.resolution_x = scene.render.resolution_y = 32
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(output / 'render.png')
bpy.ops.render.render(write_still=True)
assert (output / 'render.png').stat().st_size > 0
path = str(output / 'roundtrip.blend')
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
assert bpy.context.scene.render.engine == 'CYCLES'
print('PASS: installed runtime, Cycles CPU render and save/reopen')
