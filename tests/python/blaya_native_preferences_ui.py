"""Run in an isolated GUI process; verify the native Preferences panel draws."""
import bpy
import traceback
import blaya_framework

seen = []
errors = []
step = 0
panel = blaya_framework.BLAYA_NATIVE_PT_preferences
original = panel.draw

def draw(self, context):
    try:
        original(self, context)
        seen.append(True)
    except Exception:
        errors.append(traceback.format_exc())

panel.draw = draw

def tick():
    global step
    try:
        if step == 0:
            bpy.context.preferences.active_section = 'INTERFACE'
            bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
            step = 1
            return 1.0
        assert seen and not errors, (seen, errors)
        print('PASS: native Workflow Preferences panel renders', flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: native Workflow Preferences panel', flush=True)
    bpy.ops.wm.quit_blender()
    return None

bpy.app.timers.register(tick, first_interval=2.0)
