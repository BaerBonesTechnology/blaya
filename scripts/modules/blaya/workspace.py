"""A user-owned modeling/UV workspace, built without altering scene data."""
import bpy

PENDING = None


def split_area(window, area, factor, direction='VERTICAL'):
    before = {a.as_pointer() for a in window.screen.areas}
    with bpy.context.temp_override(window=window, area=area):
        bpy.ops.screen.area_split(direction=direction, factor=factor)
    editors = [a for a in window.screen.areas if a.as_pointer() not in before or a == area]
    if len(editors) != 2:
        raise RuntimeError('Could not split the editor')
    return editors


def configure(window):
    primary = max((a for a in window.screen.areas if a.type == 'VIEW_3D'),
                  key=lambda a: a.width * a.height,
                  default=max(window.screen.areas, key=lambda a: a.width * a.height))
    return split_area(window, primary, .24)


def finish_layout(window, editors):
    model, uv = sorted(editors, key=lambda a: a.x)
    model.type = 'VIEW_3D'
    model.spaces.active.show_region_ui = False
    model.spaces.active.show_region_toolbar = False
    uv.type = 'IMAGE_EDITOR'
    uv.ui_type = 'UV'
    uv.spaces.active.show_region_ui = False
    uv.spaces.active.show_region_toolbar = False
    window.workspace['blaya_workspace_version'] = 2
    for area in window.screen.areas:
        area.tag_redraw()


def finish_dock(window, editors):
    tools, model = sorted(editors, key=lambda a: a.x)
    tools.type = 'PROPERTIES'
    tools.ui_type = 'BLAYA_TOOLS'
    model.type = 'VIEW_3D'
    model.spaces.active.show_region_ui = False
    model.spaces.active.show_region_toolbar = False
    return model


def build_pending():
    global PENDING
    job = PENDING
    if job is None:
        return None
    try:
        window = job['window']
        if window not in bpy.context.window_manager.windows[:]:
            PENDING = None
            return None
        job['tries'] += 1
        # Workspace assignment is queued by Blender and takes effect next tick.
        if window.workspace != job['expected']:
            if job['tries'] > 30:
                raise RuntimeError('Workspace switch did not complete; try again')
            return .1
        if job['phase'] == 'duplicate':
            before = {w.as_pointer() for w in bpy.data.workspaces}
            with bpy.context.temp_override(window=window):
                result = bpy.ops.workspace.duplicate()
            created = [w for w in bpy.data.workspaces if w.as_pointer() not in before]
            if result != {'FINISHED'} or len(created) != 1:
                raise RuntimeError('Could not duplicate the source workspace')
            target = created[0]
            target.name = 'Kitchen 3D Animation' if job.get('kind') == 'ANIMATION' else 'Kitchen 3D'
            job.update(expected=target, phase='configure', tries=0)
            window.workspace = target
            return .1
        if job['phase'] == 'configure':
            job['editors'] = configure(window)
            job['phase'] = 'finish'
            return .1
        if job['phase'] == 'dock_existing':
            job['editors'] = configure(window)
            job['phase'] = 'finish_upgrade'
            return .1
        if job['phase'] == 'finish_upgrade':
            finish_dock(window, job['editors'])
            window.workspace['blaya_workspace_version'] = 2
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.show_region_ui = False
            PENDING = None
            return None
        if job['phase'] == 'finish':
            model = finish_dock(window, job['editors'])
            if job.get('kind') == 'ANIMATION':
                tools = next(a for a in window.screen.areas if a.ui_type == 'BLAYA_TOOLS')
                tools.spaces.active.blaya_workflow = 'ANIMATION'
                job['editors'] = split_area(window, model, .38, 'HORIZONTAL')
                job['phase'] = 'animation_rows'
                return .1
            job['editors'] = split_area(window, model, .67)
            job['phase'] = 'finish_views'
            return .1
        if job['phase'] == 'animation_rows':
            lower, viewport = sorted(job['editors'], key=lambda a: a.y)
            viewport.type = 'VIEW_3D'
            viewport.spaces.active.show_region_ui = False
            viewport.spaces.active.show_region_toolbar = False
            job['editors'] = split_area(window, lower, .5)
            job['phase'] = 'animation_finish'
            return .1
        if job['phase'] == 'animation_finish':
            dope, graph = sorted(job['editors'], key=lambda a: a.x)
            dope.type = 'DOPESHEET_EDITOR'
            dope.ui_type = 'DOPESHEET'
            dope.spaces.active.mode = 'DOPESHEET'
            dope.spaces.active.dopesheet.show_only_selected = True
            dope.spaces.active.show_region_ui = False
            graph.type = 'GRAPH_EDITOR'
            graph.spaces.active.mode = 'FCURVES'
            graph.spaces.active.dopesheet.show_only_selected = True
            graph.spaces.active.show_region_ui = False
            window.workspace['blaya_workspace_version'] = 2
            window.workspace['blaya_animation_workspace_version'] = 1
            for area in window.screen.areas:
                area.tag_redraw()
        else:
            finish_layout(window, job['editors'])
        bpy.context.window_manager.blaya_workspace_error = ''
        PENDING = None
        return None
    except Exception as error:
        bpy.context.window_manager.blaya_workspace_error = str(error)
        print('Workspace setup failed:', error)
        PENDING = None
        return None


class BLAYA_OT_workspace(bpy.types.Operator):
    bl_idname = 'blaya.workspace'
    bl_label = 'Create / Open Kitchen 3D Workspace'
    kind: bpy.props.EnumProperty(items=[('MODEL', 'Modeling', ''), ('ANIMATION', 'Animation', '')], default='MODEL')
    bl_description = 'Open the Kitchen 3D workspace, or create one from Layout with a dedicated left tools editor, modeling viewport and UV editor. Existing workspaces and scene data are preserved. Save your blend file to retain the workspace'

    @classmethod
    def poll(cls, context):
        return context.window is not None and not bpy.app.background

    def execute(self, context):
        global PENDING
        if PENDING is not None:
            self.report({'INFO'}, 'Workspace setup is already running')
            return {'FINISHED'}
        name = 'Kitchen 3D Animation' if self.kind == 'ANIMATION' else 'Kitchen 3D'
        legacy_name = 'BLAYA Animation' if self.kind == 'ANIMATION' else 'BLAYA'
        existing = bpy.data.workspaces.get(name) or bpy.data.workspaces.get(legacy_name)
        if existing:
            existing.name = name
            context.window.workspace = existing
            if existing.get('blaya_workspace_version', 0) < 2:
                PENDING = {'window': context.window, 'expected': existing,
                           'phase': 'dock_existing', 'tries': 0}
                bpy.app.timers.register(build_pending, first_interval=.1)
            return {'FINISHED'}
        source = bpy.data.workspaces.get('Layout') or context.window.workspace
        context.window_manager.blaya_workspace_error = ''
        PENDING = {'window': context.window, 'expected': source, 'phase': 'duplicate', 'tries': 0, 'kind': self.kind}
        context.window.workspace = source
        bpy.app.timers.register(build_pending, first_interval=.1)
        self.report({'INFO'}, 'Creating animation workspace' if self.kind == 'ANIMATION' else 'Creating tools, modeling and UV workspace')
        return {'FINISHED'}


def draw(layout, context):
    layout.operator('blaya.workspace', icon='WORKSPACE')
    if context.window_manager.blaya_workspace_error:
        from . import hint
        row = layout.row()
        row.label(text='Workspace setup failed', icon='ERROR')
        hint(row, context.window_manager.blaya_workspace_error)


def register():
    bpy.utils.register_class(BLAYA_OT_workspace)
    bpy.types.WindowManager.blaya_workspace_error = bpy.props.StringProperty(options={'SKIP_SAVE'})


def unregister():
    global PENDING
    if bpy.app.timers.is_registered(build_pending):
        bpy.app.timers.unregister(build_pending)
    PENDING = None
    del bpy.types.WindowManager.blaya_workspace_error
    bpy.utils.unregister_class(BLAYA_OT_workspace)
