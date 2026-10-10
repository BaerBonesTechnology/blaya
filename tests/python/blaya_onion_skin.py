"""Disposable GUI regression: --factory-startup --python this_file."""
import bpy
import json
import traceback
from mathutils import Quaternion
from blaya import onion_skin as onion, workspace, native_editor

phase = 0
errors = []
for panel in native_editor.PANELS:
    if '_animation_onion' in panel.__name__:
        original = panel.draw
        def checked(self, context):
            try:
                original(self, context)
            except Exception:
                errors.append(traceback.format_exc())
                traceback.print_exc()
        panel.draw = checked

def action(name):
    area = next(a for a in bpy.context.screen.areas if a.ui_type == 'BLAYA_TOOLS')
    with bpy.context.temp_override(area=area, region=next(r for r in area.regions if r.type == 'WINDOW')):
        assert bpy.ops.blaya.editor_action(operator_id=name, arguments=json.dumps({}), workflow='ANIMATION') == {'FINISHED'}

def tick():
    global phase
    try:
        if workspace.PENDING:
            return .3
        if phase == 0:
            bpy.ops.blaya.animation_workspace()
            phase = 1
            return .5
        if phase == 1:
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete(use_global=False)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16)
            obj = bpy.context.object
            obj.name = 'Onion Skin Test'
            for frame, x, z in ((1, -6, 0), (10, 0, 2), (19, 6, 0)):
                obj.location = (x, 0, z)
                obj.keyframe_insert(data_path='location', frame=frame)
            bevel = obj.modifiers.new('Evaluated subdivision', 'SUBSURF')
            bevel.levels = 1
            scene = bpy.context.scene
            scene.frame_start = 1
            scene.frame_end = 19
            scene.frame_set(10, subframe=.25)
            scene.blaya_onion.step = 3
            before = (len(bpy.data.objects), len(bpy.data.meshes), obj.location.copy(), scene.frame_current_final)
            action('blaya.onion_skin')
            assert onion.active(scene)
            assert [s['frame'] for s in onion.STATE['samples']] == [7, 4, 13, 16]
            assert all(len(s['vertices']) > len(obj.data.vertices) for s in onion.STATE['samples'])
            assert (len(bpy.data.objects), len(bpy.data.meshes)) == before[:2]
            assert (obj.location-before[2]).length < 1e-6 and scene.frame_current_final == before[3]
            assert min(v[0] for v in onion.STATE['samples'][0]['vertices']) < -1
            assert min(v[0] for v in onion.STATE['samples'][2]['vertices']) > 0
            # Sampling failure must restore the exact frame and leave no mesh datablocks.
            old = onion.MAX_TRIANGLES
            onion.MAX_TRIANGLES = 1
            try:
                try:
                    onion.sample(bpy.context, [obj])
                    raise AssertionError('Expected complexity limit')
                except RuntimeError:
                    pass
            finally:
                onion.MAX_TRIANGLES = old
            assert scene.frame_current_final == before[3]
            assert len(bpy.data.meshes) == before[1]
            scene.frame_set(11)
            phase = 2
            return 1.2
        if phase == 2:
            scene = bpy.context.scene
            assert onion.STATE['signature'] == onion.signature(scene), onion.STATE['signature']
            assert onion.STATE['samples'][0]['frame'] == 8
            action('blaya.onion_refresh')
            action('blaya.onion_skin')
            assert not onion.STATE
            # A selected rig should capture its mesh and evaluated bone deformation.
            bpy.ops.object.armature_add()
            rig = bpy.context.object
            mesh = bpy.data.objects['Onion Skin Test']
            modifier = mesh.modifiers.new('Ghost rig test', 'ARMATURE')
            modifier.object = rig
            group = mesh.vertex_groups.new(name='Bone')
            group.add(list(range(len(mesh.data.vertices))), 1.0, 'REPLACE')
            bone = rig.pose.bones['Bone']
            for frame, z in ((1, 0), (19, 3)):
                bone.location.y = z
                bone.keyframe_insert(data_path='location', frame=frame)
            scene.frame_set(10)
            assert onion.selected_meshes(bpy.context) == [mesh]
            action('blaya.onion_skin')
            assert len(onion.STATE['samples']) == 4
            # Compare against sampling without the armature to verify deformation.
            z_with = max(v[2] for v in onion.STATE['samples'][-1]['vertices'])
            modifier.show_viewport = False
            baseline = onion.sample(bpy.context, [mesh])
            assert z_with > max(v[2] for v in baseline[-1]['vertices']) + 1
            modifier.show_viewport = True
            # Clear registered lifecycle handler prevents stale references after undo/load.
            assert onion.clear in bpy.app.handlers.undo_pre and onion.clear in bpy.app.handlers.load_pre
            onion.clear()
            assert not onion.STATE
            action('blaya.onion_skin')
            view = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
            view.spaces.active.region_3d.view_distance = 21
            view.spaces.active.region_3d.view_location = (0, 0, 3)
            view.spaces.active.region_3d.view_rotation = Quaternion((1, 0, 0), 1.35)
            view.spaces.active.overlay.show_floor = False
            phase = 3
            return .7
        if phase == 3:
            assert not errors, errors
            assert onion.STATE and all(s['batches'] is not None for s in onion.STATE['samples']), 'GPU draw failed'
            bpy.ops.screen.screenshot(filepath='/tmp/blaya-onion-preview.png')
            print('PASS: onion GPU draw, panels, evaluated geometry/rig, frame restoration, no scene objects, complexity guard, scrub refresh, toggle and lifecycle cleanup', flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: onion skin smoke', flush=True)
    bpy.ops.wm.quit_blender()
    return None

bpy.app.timers.register(tick, first_interval=2)
