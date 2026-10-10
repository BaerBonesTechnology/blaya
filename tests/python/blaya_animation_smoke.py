"""Run a disposable Kitchen 3D GUI with --factory-startup --python this_file."""
import json
import traceback
import bpy
from bpy_extras.anim_utils import animdata_get_channelbag_for_assigned_slot
from blaya import native_editor, workspace, animation

phase = 0
tries = 0
seen = set()
errors = []
for panel in native_editor.PANELS:
    if '_animation_' not in panel.__name__:
        continue
    original = panel.draw
    def wrap(original, name):
        def draw(self, context):
            try:
                original(self, context)
                seen.add(name)
            except Exception:
                errors.append(traceback.format_exc())
                traceback.print_exc()
        return draw
    panel.draw = wrap(original, panel.__name__)


def curves(obj):
    return animdata_get_channelbag_for_assigned_slot(obj.animation_data).fcurves


def run(tool, arguments):
    area = next(a for a in bpy.context.screen.areas if a.ui_type == 'BLAYA_TOOLS')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(area=area, region=region):
        result = bpy.ops.blaya.editor_action(operator_id=tool, arguments=json.dumps(arguments), workflow='ANIMATION')
    assert result == {'FINISHED'}, (tool, arguments, result)


def tick():
    global phase, tries
    try:
        if workspace.PENDING:
            tries += 1
            assert tries < 80
            return .2
        if phase == 0:
            bpy.ops.blaya.animation_workspace()
            phase = 1
            return .3
        assert bpy.context.workspace.name == 'Kitchen 3D Animation'
        if phase == 1:
            assert animation.editor(bpy.context, 'DOPESHEET_EDITOR')
            assert animation.editor(bpy.context, 'GRAPH_EDITOR')
            assert any(a.ui_type == 'TIMELINE' for a in bpy.context.screen.areas)
            assert any(a.ui_type == 'PROPERTIES' for a in bpy.context.screen.areas)
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            phase = 2
            return .4
        if phase == 2:
            assert len(seen) == 5 and not errors, (seen, errors)
            scene = bpy.context.scene
            cube = bpy.data.objects['Cube']
            bpy.context.view_layer.objects.active = cube
            for obj in scene.objects:
                obj.select_set(obj == cube)
            scene.blaya_animation.channels = 'LOCATION'
            for frame, value in ((1, 0), (10, 3), (20, 6)):
                scene.frame_set(frame)
                cube.location = (value, value, value)
                run('blaya.animation_key', {'operation': 'INSERT'})
            assert len(curves(cube)) == 3
            assert all(len(fc.keyframe_points) == 3 for fc in curves(cube))
            scene.frame_set(10)
            run('blaya.animation_key', {'operation': 'DELETE'})
            assert all([round(p.co.x) for p in fc.keyframe_points] == [1, 20] for fc in curves(cube))
            run('blaya.animation_key', {'operation': 'INSERT'})
            for fc in curves(cube):
                fc.lock = fc.array_index == 2
                for key in fc.keyframe_points:
                    selected = abs(key.co.x - 10) < .01
                    key.select_control_point = key.select_left_handle = key.select_right_handle = selected
            scene.blaya_animation.offset = 3
            run('blaya.animation_timing', {'operation': 'RIGHT'})
            for fc in curves(cube):
                expected = [1, 10, 20] if fc.lock else [1, 13, 20]
                assert [round(p.co.x) for p in fc.keyframe_points] == expected, [(fc.array_index, [p.co.x for p in fc.keyframe_points])]
            scene.frame_set(1)
            scene.blaya_animation.time_scale = 2
            run('blaya.animation_timing', {'operation': 'SCALE'})
            for fc in curves(cube):
                expected = [1, 10, 20] if fc.lock else [1, 20, 25]
                assert [round(p.co.x) for p in fc.keyframe_points] == expected, [p.co.x for p in fc.keyframe_points]
            run('blaya.animation_curve', {'operation': 'CONSTANT'})
            for fc in curves(cube):
                assert all(p.interpolation == ('CONSTANT' if p.select_control_point and not fc.lock else 'BEZIER') for p in fc.keyframe_points)
            run('blaya.animation_curve', {'operation': 'BEZIER'})
            run('blaya.animation_curve', {'operation': 'AUTO_CLAMPED'})
            assert all(p.handle_left_type == 'AUTO_CLAMPED' for fc in curves(cube) if not fc.lock for p in fc.keyframe_points if p.select_control_point)
            assert not scene.tool_settings.use_keyframe_insert_auto
            # Locked transform channels must not get keyed.
            cube.lock_scale = (True, False, False)
            scene.blaya_animation.channels = 'SCALE'
            run('blaya.animation_key', {'operation': 'INSERT'})
            assert not any(fc.data_path == 'scale' and fc.array_index == 0 for fc in curves(cube))
            # The existing workspace must reopen without changing its areas.
            before = [(a.as_pointer(), a.ui_type) for a in bpy.context.screen.areas]
            bpy.ops.blaya.animation_workspace()
            assert [(a.as_pointer(), a.ui_type) for a in bpy.context.screen.areas] == before
            for kind in ('DOPESHEET_EDITOR', 'GRAPH_EDITOR'):
                area = animation.editor(bpy.context, kind)
                with bpy.context.temp_override(area=area, region=next(r for r in area.regions if r.type=='WINDOW')):
                    (bpy.ops.action.view_all if kind == 'DOPESHEET_EDITOR' else bpy.ops.graph.view_all)()
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            bpy.ops.screen.screenshot(filepath='/tmp/blaya-animation-preview.png')
            print('PASS: animation panels, workspace reuse, key/delete, channel locks, selected-key retiming and curve controls', flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: animation smoke', flush=True)
    bpy.ops.wm.quit_blender()
    return None

bpy.app.timers.register(tick, first_interval=2)
