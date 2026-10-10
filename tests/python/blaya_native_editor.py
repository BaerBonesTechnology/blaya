"""GUI smoke test for all workflow panels and cross-editor tool routing."""
import json
import os
import tempfile
import traceback
from pathlib import Path
import bpy
import bmesh
from blaya import native_editor, workspace

seen = set()
errors = []
step = 0
tries = 0
# Expand the test panels before their first draw; production defaults remain collapsed.
for panel in native_editor.PANELS:
    bpy.utils.unregister_class(panel)
    panel.bl_options = set()
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
    bpy.utils.register_class(panel)


def tick():
    global step, tries
    try:
        tools = next((a for a in bpy.context.screen.areas if a.ui_type == 'BLAYA_TOOLS'), None)
        if workspace.PENDING or tools is None:
            tries += 1
            assert tries < 50, 'Workspace did not finish'
            return .25
        if step == 0 and not any(a.ui_type == 'UV' for a in bpy.context.screen.areas):
            assert bpy.ops.blaya.open_uv_editor() == {'FINISHED'}
            return .25
        if step < len(native_editor.WORKFLOWS):
            tools.spaces.active.blaya_workflow = native_editor.WORKFLOWS[step][0]
            tools.tag_redraw()
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            step += 1
            return .5
        assert not errors, errors
        assert len(seen) == len(native_editor.PANELS), (seen, len(native_editor.PANELS))
        region = next(r for r in tools.regions if r.type == 'WINDOW')
        cube = bpy.data.objects['Cube']
        bpy.context.view_layer.objects.active = cube
        cube.select_set(True)
        with native_editor.override(bpy.context, 'MODEL'):
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        cube.scale = (2, 3, 4)
        with bpy.context.temp_override(area=tools, region=region):
            result = bpy.ops.blaya.editor_action(operator_id='blaya.command',
                    arguments=json.dumps({'command': 'freeze'}), workflow='MODEL')
        assert result == {'FINISHED'} and tuple(cube.scale) == (1, 1, 1)
        with native_editor.override(bpy.context, 'MODEL'):
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
        with bpy.context.temp_override(area=tools, region=region):
            result = bpy.ops.blaya.editor_action(operator_id='uv.smart_project',
                    arguments='{}', workflow='UV')
        assert result == {'FINISHED'}
        with native_editor.override(bpy.context, 'UV'):
            bpy.ops.uv.select_all(action='SELECT')
        with bpy.context.temp_override(area=tools, region=region):
            result = bpy.ops.blaya.editor_action(operator_id='blaya.uv_action',
                    arguments=json.dumps({'action': 'PIN'}), workflow='UV')
        bm = bmesh.from_edit_mesh(cube.data)
        layer = bm.loops.layers.uv.active
        assert result == {'FINISHED'} and all(loop[layer].pin_uv for f in bm.faces for loop in f.loops)
        # Capture the populated Model editor for visual inspection.
        tools.spaces.active.blaya_workflow = 'MODEL'
        tools.tag_redraw()
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        output=Path(os.environ.get('KITCHEN3D_TEST_OUTPUT',tempfile.gettempdir()))
        output.mkdir(parents=True,exist_ok=True)
        bpy.ops.screen.screenshot(filepath=str(output/'kitchen3d-native-editor.png'))
        print('PASS: all workflow panels, Model freeze and UV unwrap/pin routed from Tools editor', flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: native tools editor', flush=True)
    bpy.ops.wm.quit_blender()
    return None

bpy.app.timers.register(tick, first_interval=2.0)
