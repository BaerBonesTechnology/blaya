"""Run twice with one isolated BLENDER_USER_CONFIG, after creating a legacy fixture.

First invocation: --python this_file -- migrate
Second invocation: --python this_file -- reload
"""
import sys
import bpy
import addon_utils
import blaya

mode = sys.argv[sys.argv.index('--') + 1]
assert 'blaya' not in bpy.context.preferences.addons
assert 'blaya' not in {module.__name__ for module in addon_utils.modules()}
assert not getattr(blaya, '__addon_enabled__', False)
settings = blaya.prefs()
assert settings.tool_display == 'BOTH'
assert settings.shelf_name == 'Migration QA'
assert any(item.label == 'Saved Bevel' and item.command == 'bevel'
           for item in settings.shelf)
if mode == 'migrate':
    settings.space_menu = 'LIST'
    assert bpy.context.preferences.is_dirty
    bpy.ops.wm.save_userpref()
else:
    assert settings.space_menu == 'LIST'
    bpy.ops.wm.read_factory_userpref()
    blaya.initialize_preferences()
    assert blaya.prefs().tool_display == 'ICONS'
    assert blaya.prefs().shelf_initialized
    assert 'blaya' not in bpy.context.preferences.addons
print('PASS: native preferences', mode, flush=True)
