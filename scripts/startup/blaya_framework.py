# SPDX-FileCopyrightText: 2026 Kitchen 3D contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native distribution entry point; workflow implementation stays modular."""
import bpy
from bpy.app.handlers import persistent
from bpy.utils import previews

_registered_tools = False
_brand_icons = None


def ensure_tools():
    global _registered_tools
    if not _registered_tools:
        import blaya
        blaya.register()
        from blaya import native_editor
        native_editor.register()
        _registered_tools = True
    return True


def bootstrap():
    if not ensure_tools():
        return None
    if bpy.app.background or bpy.context.window is None or bpy.data.filepath:
        return None
    import blaya
    blaya.initialize_preferences()
    settings = blaya.prefs()
    if settings is None:
        return None
    blaya.render_benchmark.configure_windows_default(bpy.context.scene)
    if not settings.native_initialized:
        # Kitchen 3D's own preferences directory makes this independent of Blender's.
        if bpy.context.window_manager.keyconfigs.active.name == 'Blender':
            bpy.ops.blaya.use_industry_keymap()
        settings.native_initialized = True
        bpy.context.preferences.is_dirty = True
    existing = bpy.data.workspaces.get('Kitchen 3D') or bpy.data.workspaces.get('BLAYA')
    if existing is not None:
        existing.name = 'Kitchen 3D'
    if existing is None or existing.get('blaya_workspace_version', 0) < 2:
        bpy.ops.blaya.workspace()
    return .2 if blaya.workspace.PENDING is not None else None


def show_startup_splash():
    # Recheck in case a file was opened or the preference changed while waiting.
    if bpy.app.background or bpy.data.filepath or not bpy.context.preferences.view.show_splash:
        return None
    import blaya
    if bpy.app.timers.is_registered(bootstrap) or blaya.workspace.PENDING is not None:
        return .2
    if bpy.context.window is not None:
        bpy.ops.wm.splash('INVOKE_DEFAULT')
    return None


def defer_startup_splash():
    if not bpy.app.timers.is_registered(show_startup_splash):
        bpy.app.timers.register(show_startup_splash, first_interval=.2)


@persistent
def after_load(_):
    ensure_tools()
    import blaya
    blaya.migrate_preferences()
    blaya.initialize_preferences()
    if not bpy.app.timers.is_registered(bootstrap):
        bpy.app.timers.register(bootstrap, first_interval=.2)


class BLAYA_NATIVE_OT_about(bpy.types.Operator):
    bl_idname = 'blaya_native.about'
    bl_label = 'About Kitchen 3D'

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=440)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.label(text='Kitchen 3D', icon_value=_brand_icons['mark'].icon_id if _brand_icons else 0)
        row.label(text='|')
        row.label(text='Blender Distro', icon='BLENDER')
        layout.label(text='Built on Blender ' + bpy.app.version_string)
        layout.label(text='Independent project by Baer Bones Technology.')
        layout.label(text='Not affiliated with or endorsed by the Blender Foundation.')
        layout.separator()
        layout.operator('wm.url_open', text='Support Blender Development', icon='FUND').url = 'https://fund.blender.org/'
        layout.operator('wm.splash_about', text='Blender Credits & License')

    def execute(self, context):
        return {'FINISHED'}


class BLAYA_NATIVE_MT_framework(bpy.types.Menu):
    bl_label = 'Kitchen 3D'

    def draw(self, context):
        layout = self.layout
        layout.operator('blaya.workspace', text='Open Kitchen 3D Workspace', icon='WORKSPACE')
        layout.operator('blaya.animation_workspace', icon='ANIM')
        layout.operator('blaya.use_industry_keymap', text='Use Industry Compatible Keymap')
        layout.separator()
        layout.operator('blaya_native.about', icon='INFO')
        layout.operator('wm.url_open', text='Blender Documentation', icon='HELP').url = 'https://docs.blender.org/manual/en/latest/'
        layout.operator('wm.url_open', text='Download Official Blender', icon='BLENDER').url = 'https://www.blender.org/download/'
        layout.operator('wm.url_open', text='Support Blender Development', icon='FUND').url = 'https://fund.blender.org/'


class BLAYA_NATIVE_PT_preferences(bpy.types.Panel):
    bl_label = 'Kitchen 3D Workflow'
    bl_space_type = 'PREFERENCES'
    bl_region_type = 'WINDOW'
    bl_context = 'interface'

    def draw(self, context):
        import blaya
        settings = blaya.prefs(context)
        self.layout.prop(settings, 'maya_keys')
        self.layout.prop(settings, 'tool_display')
        self.layout.prop(settings, 'space_menu')
        self.layout.prop(settings, 'area_threshold')


def draw_menu(self, context):
    row = self.layout.row()
    row.scale_x = 1.35
    row.menu('BLAYA_NATIVE_MT_framework', text='Kitchen 3D', icon_value=_brand_icons['mark'].icon_id if _brand_icons else 0)


def register():
    global _brand_icons
    ensure_tools()
    from pathlib import Path
    import blaya
    _brand_icons = previews.new()
    _brand_icons.load('mark', str(Path(blaya.__file__).parent / 'assets' / 'brand.png'), 'IMAGE')
    for cls in (BLAYA_NATIVE_OT_about, BLAYA_NATIVE_MT_framework, BLAYA_NATIVE_PT_preferences):
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.append(draw_menu)
    bpy.app.handlers.load_post.append(after_load)
    bpy.app.handlers.load_factory_startup_post.append(after_load)
    bpy.app.handlers.load_factory_preferences_post.append(after_load)
    if not bpy.app.timers.is_registered(bootstrap):
        bpy.app.timers.register(bootstrap, first_interval=.2, persistent=True)


def unregister():
    global _registered_tools, _brand_icons
    if _brand_icons is not None:
        previews.remove(_brand_icons)
        _brand_icons = None
    if bpy.app.timers.is_registered(bootstrap):
        bpy.app.timers.unregister(bootstrap)
    if bpy.app.timers.is_registered(show_startup_splash):
        bpy.app.timers.unregister(show_startup_splash)
    for handlers in (bpy.app.handlers.load_post, bpy.app.handlers.load_factory_startup_post,
                     bpy.app.handlers.load_factory_preferences_post):
        if after_load in handlers:
            handlers.remove(after_load)
    bpy.types.TOPBAR_MT_editor_menus.remove(draw_menu)
    for cls in (BLAYA_NATIVE_PT_preferences, BLAYA_NATIVE_MT_framework, BLAYA_NATIVE_OT_about):
        bpy.utils.unregister_class(cls)
    if _registered_tools:
        import blaya
        from blaya import native_editor
        native_editor.unregister()
        blaya.unregister()
        _registered_tools = False
