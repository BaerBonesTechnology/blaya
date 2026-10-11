"""Export linked meshes with material and object animation through the source glTF add-on."""
# SPDX-License-Identifier: GPL-2.0-or-later
import json
import os
from pathlib import Path
import sys

import bpy

# Use this checkout's exporter even when testing with an older release executable.
source = Path(__file__).resolve().parents[2] / 'scripts/addons_core'
if 'io_scene_gltf2' in sys.modules:
    sys.modules['io_scene_gltf2'].unregister()
    for name in list(sys.modules):
        if name == 'io_scene_gltf2' or name.startswith('io_scene_gltf2.'):
            del sys.modules[name]
sys.path.insert(0, str(source))
import io_scene_gltf2
assert Path(io_scene_gltf2.__file__).resolve().is_relative_to(source)
io_scene_gltf2.register()

output = Path(os.environ['KITCHEN3D_TEST_OUTPUT'])
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.frame_end = 10
parent = bpy.data.objects.new('Instances', None)
scene.collection.objects.link(parent)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.object
cube.parent = parent
second = cube.copy()
second.data = cube.data
scene.collection.objects.link(second)
second.location.x = 3

material = bpy.data.materials.new('AnimatedMaterial')
material.use_nodes = True
cube.data.materials.append(material)
roughness = material.node_tree.nodes.get('Principled BSDF').inputs['Roughness']
for frame, value in ((1, .1), (10, .9)):
    roughness.default_value = value
    roughness.keyframe_insert('default_value', frame=frame)

# A surviving node must still have its animation index remapped after instancing.
mover = bpy.data.objects.new('AnimatedSurvivor', None)
scene.collection.objects.link(mover)
for frame, x in ((1, 0), (10, 5)):
    mover.location.x = x
    mover.keyframe_insert('location', frame=frame)

for gpu_instances in (False, True):
    path = output / f'instancing-{gpu_instances}.gltf'
    result = bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLTF_SEPARATE',
        export_gpu_instances=gpu_instances, export_pointer_animation=True,
        export_animation_mode='SCENE')
    assert result == {'FINISHED'}, result
    data = json.loads(path.read_text(encoding='utf-8'))
    nodes = data['nodes']
    channels = [channel for animation in data.get('animations', []) for channel in animation['channels']]
    pointers = [channel['target'].get('extensions', {}).get('KHR_animation_pointer', {}).get('pointer')
                for channel in channels]
    expected = '/materials/0/pbrMetallicRoughness/roughnessFactor'
    assert expected in pointers, (gpu_instances, 'Lost material animation', pointers)
    survivor = next(index for index, node in enumerate(nodes) if node.get('name') == 'AnimatedSurvivor')
    assert any(channel['target'].get('node') == survivor
               and channel['target']['path'] == 'translation' for channel in channels), channels
    assert all(0 <= channel['target']['node'] < len(nodes)
               for channel in channels if 'node' in channel['target'])
    if gpu_instances:
        assert any('EXT_mesh_gpu_instancing' in node.get('extensions', {}) for node in nodes)
        assert len(nodes) == 2, nodes
    else:
        assert len(nodes) == 4, nodes

print('PASS: GPU instancing preserves material animation and remaps surviving object animation')
