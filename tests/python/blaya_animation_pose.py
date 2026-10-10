"""Run with Kitchen 3D --background --factory-startup --python-exit-code 1 --python this_file."""
import bpy
from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot

bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.armature_add()
rig = bpy.context.object
bpy.ops.object.mode_set(mode='EDIT')
other = rig.data.edit_bones.new('Untouched')
other.head = (2, 0, 0)
other.tail = (2, 0, 1)
bpy.ops.object.mode_set(mode='POSE')
for bone in rig.pose.bones:
    bone.select = bone.name == 'Bone'
rig.data.bones.active = rig.data.bones['Bone']
bone = rig.pose.bones['Bone']
bone.rotation_mode = 'QUATERNION'
bone.lock_location = (True, False, False)
bone.lock_scale = (True, False, False)
bone.lock_rotations_4d = True
bone.lock_rotation_w = True
bpy.context.scene.blaya_animation.channels = 'LRS'
for frame in (5, 10):
    bpy.context.scene.frame_set(frame)
    assert bpy.ops.blaya.animation_key(operation='INSERT') == {'FINISHED'}
curves = animdata_get_channelbag_for_assigned_slot(rig.animation_data).fcurves
expected = {(bone.path_from_id(path), i) for path, indices in
            [('location', (1, 2)), ('rotation_quaternion', (1, 2, 3)), ('scale', (1, 2))] for i in indices}
assert {(fc.data_path, fc.array_index) for fc in curves} == expected
assert all([p.co.x for p in fc.keyframe_points] == [5, 10] for fc in curves)
assert bpy.ops.blaya.animation_key(operation='DELETE') == {'FINISHED'}
assert all([p.co.x for p in fc.keyframe_points] == [5] for fc in curves)
print('PASS: selected pose-bone keying, quaternion channels, transform locks and current-frame deletion', flush=True)
