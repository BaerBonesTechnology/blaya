"""Open an old Kitchen 3D workspace file, then run this GUI script."""
import traceback
import bpy
from blaya import workspace
step = 0
tries = 0

def tick():
    global step, tries
    try:
        if step == 0:
            assert bpy.context.workspace.get('blaya_workspace_version') == 1
            assert not any(a.ui_type == 'BLAYA_TOOLS' for a in bpy.context.screen.areas)
            bpy.ops.blaya.workspace()
            step = 1
            return .5
        if workspace.PENDING:
            tries += 1
            assert tries < 40
            return .25
        assert bpy.context.workspace.get('blaya_workspace_version') == 2
        assert len([a for a in bpy.context.screen.areas if a.ui_type == 'BLAYA_TOOLS']) == 1
        assert any(a.ui_type == 'UV' for a in bpy.context.screen.areas)
        assert any(a.ui_type == 'PROPERTIES' for a in bpy.context.screen.areas)
        print('PASS: explicit upgrade of legacy workspace to native tools editor', flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: legacy workspace upgrade', flush=True)
    bpy.ops.wm.quit_blender()
    return None

bpy.app.timers.register(tick, first_interval=1)
