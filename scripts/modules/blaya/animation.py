"""Native animation workflow: selected transforms, editor-scoped keys and curves."""
import bpy
from . import onion_skin
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty


class BLAYA_AnimationSettings(bpy.types.PropertyGroup):
    channels: EnumProperty(name='Channels', items=[
        ('LRS', 'Translate / Rotate / Scale', 'Key unlocked transform channels'),
        ('LOCATION', 'Translate', 'Key unlocked location channels'),
        ('ROTATION', 'Rotate', 'Key unlocked rotation channels in the current rotation mode'),
        ('SCALE', 'Scale', 'Key unlocked scale channels'),
    ], default='LRS')
    offset: IntProperty(name='Frames', default=1, min=1, max=10000,
                        description='Move selected Dope Sheet keys by this many frames')
    time_scale: FloatProperty(name='Time Scale', default=2.0, min=.01, max=100,
                              description='Scale selected Dope Sheet keys around the current frame; 2 doubles spacing, 0.5 halves it')


def targets(context):
    if context.mode == 'POSE':
        return [bone for bone in (context.selected_pose_bones or []) if bone.id_data.is_editable]
    if context.mode == 'OBJECT':
        return [obj for obj in context.selected_objects if obj.is_editable]
    return []


def channels(target, preset):
    if preset in {'LRS', 'LOCATION'}:
        yield 'location', [i for i, locked in enumerate(target.lock_location) if not locked]
    if preset in {'LRS', 'ROTATION'}:
        mode = target.rotation_mode
        path = 'rotation_quaternion' if mode == 'QUATERNION' else 'rotation_axis_angle' if mode == 'AXIS_ANGLE' else 'rotation_euler'
        locks = list(target.lock_rotation)
        if mode in {'QUATERNION', 'AXIS_ANGLE'}:
            locks.insert(0, target.lock_rotations_4d and target.lock_rotation_w)
        yield path, [i for i, locked in enumerate(locks) if not locked]
    if preset in {'LRS', 'SCALE'}:
        yield 'scale', [i for i, locked in enumerate(target.lock_scale) if not locked]


class BLAYA_OT_animation_key(bpy.types.Operator):
    bl_idname = 'blaya.animation_key'
    bl_label = 'Set Key'
    bl_description = 'Key the chosen unlocked transform channels on selected objects or pose bones at the current frame'
    bl_options = {'REGISTER', 'UNDO'}
    operation: EnumProperty(items=[('INSERT', 'Set Key', ''), ('DELETE', 'Delete Key', '')])

    @classmethod
    def poll(cls, context):
        return bool(targets(context))

    @classmethod
    def description(cls, context, properties):
        if properties.operation == 'DELETE':
            return 'Remove keys at the current frame from the chosen unlocked transform channels of selected objects or pose bones'
        return cls.bl_description

    def execute(self, context):
        frame = context.scene.frame_current_final
        preset = context.scene.blaya_animation.channels
        count = 0
        for target in targets(context):
            for path, indices in channels(target, preset):
                for index in indices:
                    try:
                        if self.operation == 'DELETE':
                            changed = target.keyframe_delete(data_path=path, index=index, frame=frame)
                        else:
                            changed = target.keyframe_insert(data_path=path, index=index, frame=frame,
                                                             group=target.name)
                        count += bool(changed)
                    except RuntimeError:
                        # A missing channel/key is normal when deleting a partial pose.
                        if self.operation != 'DELETE':
                            raise
        self.report({'INFO'}, f'{count} transform channels ' + ('keyed' if self.operation == 'INSERT' else 'cleared'))
        return {'FINISHED'} if count else {'CANCELLED'}


def editor(context, kind):
    areas = [area for area in context.screen.areas if area.type == kind]
    if kind == 'DOPESHEET_EDITOR':
        areas = [area for area in areas if area.ui_type != 'TIMELINE' and area.spaces.active.mode in {'DOPESHEET', 'ACTION'}]
    if kind == 'GRAPH_EDITOR':
        areas = [area for area in areas if area.spaces.active.mode == 'FCURVES']
    return max(areas, key=lambda area: area.width * area.height, default=None)


def run_in_editor(context, kind, operator, **kwargs):
    area = editor(context, kind)
    if area is None:
        raise RuntimeError('Open the Kitchen 3D Animation workspace first')
    region = next(region for region in area.regions if region.type == 'WINDOW')
    with context.temp_override(area=area, region=region):
        if not operator.poll():
            raise RuntimeError('Select editable keyframes in the animation editor first')
        return operator('EXEC_DEFAULT', **kwargs)


class BLAYA_OT_animation_timing(bpy.types.Operator):
    bl_idname = 'blaya.animation_timing'
    bl_label = 'Retime Selected Keys'
    bl_description = 'Edit selected keys in the Dope Sheet; hidden and locked channels follow Blender selection rules'
    bl_options = {'REGISTER', 'UNDO'}
    operation: EnumProperty(items=[
        ('LEFT', 'Earlier', 'Move selected Dope Sheet keys earlier by the frame offset'),
        ('RIGHT', 'Later', 'Move selected Dope Sheet keys later by the frame offset'),
        ('SCALE', 'Scale Time', 'Scale selected Dope Sheet keys around the current frame'),
    ])

    @classmethod
    def poll(cls, context):
        return context.screen is not None and editor(context, 'DOPESHEET_EDITOR') is not None

    @classmethod
    def description(cls, context, properties):
        return cls.bl_rna.properties['operation'].enum_items[properties.operation].description

    def execute(self, context):
        settings = context.scene.blaya_animation
        if self.operation == 'SCALE':
            kwargs = dict(mode='TIME_SCALE', value=(settings.time_scale, 0, 0, 0),
                          center_override=(context.scene.frame_current_final, 0, 0))
        else:
            offset = settings.offset * (-1 if self.operation == 'LEFT' else 1)
            kwargs = dict(mode='TIME_TRANSLATE', value=(offset, 0, 0, 0))
        try:
            return run_in_editor(context, 'DOPESHEET_EDITOR', bpy.ops.transform.transform, **kwargs)
        except RuntimeError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}


CURVES = (
    ('CONSTANT', 'Stepped', 'Use constant interpolation after selected Graph Editor keys', 'IPO_CONSTANT'),
    ('LINEAR', 'Linear', 'Use linear interpolation after selected Graph Editor keys', 'IPO_LINEAR'),
    ('BEZIER', 'Bézier', 'Use Bézier interpolation after selected Graph Editor keys', 'IPO_BEZIER'),
    ('AUTO_CLAMPED', 'Auto Clamped', 'Automatically smooth selected handles while limiting overshoot', 'HANDLE_AUTOCLAMPED'),
    ('AUTO', 'Auto', 'Automatically smooth selected keyframe handles', 'HANDLE_AUTO'),
    ('VECTOR', 'Vector', 'Point selected handles toward neighboring keys', 'HANDLE_VECTOR'),
    ('ALIGNED', 'Aligned', 'Keep selected handles aligned', 'HANDLE_ALIGNED'),
    ('FREE', 'Free', 'Allow independent editing of selected handles', 'HANDLE_FREE'),
)


class BLAYA_OT_animation_curve(bpy.types.Operator):
    bl_idname = 'blaya.animation_curve'
    bl_label = 'Edit Animation Curves'
    bl_options = {'REGISTER', 'UNDO'}
    operation: EnumProperty(items=[(key, label, description) for key, label, description, icon in CURVES])

    @classmethod
    def poll(cls, context):
        return context.screen is not None and editor(context, 'GRAPH_EDITOR') is not None

    @classmethod
    def description(cls, context, properties):
        return cls.bl_rna.properties['operation'].enum_items[properties.operation].description

    def execute(self, context):
        op = bpy.ops.graph.interpolation_type if self.operation in {'CONSTANT', 'LINEAR', 'BEZIER'} else bpy.ops.graph.handle_type
        try:
            return run_in_editor(context, 'GRAPH_EDITOR', op, type=self.operation)
        except RuntimeError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}


class BLAYA_OT_animation_frame(bpy.types.Operator):
    bl_idname = 'blaya.animation_frame'
    bl_label = 'Step Frame'
    bl_description = 'Step the playhead without changing keys'
    delta: IntProperty(default=1)

    def execute(self, context):
        context.scene.frame_set(context.scene.frame_current + self.delta)
        return {'FINISHED'}


class BLAYA_OT_animation_workspace(bpy.types.Operator):
    bl_idname = 'blaya.animation_workspace'
    bl_label = 'Open Animation Workspace'
    bl_description = 'Open a Kitchen 3D workspace with viewport, Dope Sheet, Graph Editor and timeline; reuse an existing layout unchanged'

    @classmethod
    def poll(cls, context):
        return context.window is not None and not bpy.app.background

    def execute(self, context):
        return bpy.ops.blaya.workspace(kind='ANIMATION')


def buttons(layout, context, operator, items):
    from . import prefs
    icons = prefs(context).tool_display == 'ICONS'
    target = layout.grid_flow(row_major=True, columns=4 if icons else 1, even_columns=True, align=True)
    for key, label, description, icon in items:
        target.operator(operator, text='' if icons else label,
                        icon=icon if prefs(context).tool_display != 'TEXT' else 'NONE').operation = key


class BLAYA_PT_animation_workspace(bpy.types.Panel):
    bl_label = 'Animation Workspace'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    def draw(self, context):
        self.layout.operator('blaya.animation_workspace', icon='WORKSPACE')


class BLAYA_PT_animation_keying(bpy.types.Panel):
    bl_label = 'Keying'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.blaya_animation, 'channels', text='')
        buttons(layout, context, 'blaya.animation_key', (
            ('INSERT', 'Set Key', '', 'KEY_HLT'), ('DELETE', 'Delete Key', '', 'KEY_DEHLT')))
        layout.prop(context.scene.tool_settings, 'use_keyframe_insert_auto', text='Auto Key', toggle=True)


class BLAYA_PT_animation_timing(bpy.types.Panel):
    bl_label = 'Timing'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene, 'frame_current', text='Frame')
        row = layout.row(align=True)
        row.operator('screen.frame_jump', text='', icon='REW').end = False
        row.operator('screen.keyframe_jump', text='', icon='PREV_KEYFRAME').next = False
        row.operator('blaya.animation_frame', text='', icon='TRIA_LEFT').delta = -1
        row.operator('screen.animation_play', text='', icon='PAUSE' if context.screen.is_animation_playing else 'PLAY')
        row.operator('blaya.animation_frame', text='', icon='TRIA_RIGHT').delta = 1
        row.operator('screen.keyframe_jump', text='', icon='NEXT_KEYFRAME').next = True
        row.operator('screen.frame_jump', text='', icon='FF').end = True
        row = layout.row(align=True)
        row.prop(scene, 'frame_start', text='Start')
        row.prop(scene, 'frame_end', text='End')
        layout.prop(scene, 'use_preview_range', text='Preview Range')
        if scene.use_preview_range:
            row = layout.row(align=True)
            row.prop(scene, 'frame_preview_start', text='Start')
            row.prop(scene, 'frame_preview_end', text='End')
        layout.separator()
        layout.prop(scene.blaya_animation, 'offset')
        buttons(layout, context, 'blaya.animation_timing', (
            ('LEFT', 'Earlier', '', 'TRIA_LEFT'), ('RIGHT', 'Later', '', 'TRIA_RIGHT')))
        layout.prop(scene.blaya_animation, 'time_scale')
        layout.operator('blaya.animation_timing', text='Scale Selected Keys', icon='TIME').operation = 'SCALE'


class BLAYA_PT_animation_curves(bpy.types.Panel):
    bl_label = 'Curves'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    def draw(self, context):
        layout = self.layout
        if editor(context, 'GRAPH_EDITOR') is None:
            layout.operator('blaya.animation_workspace', icon='GRAPH')
            return
        buttons(layout, context, 'blaya.animation_curve', CURVES[:3])
        layout.separator()
        buttons(layout, context, 'blaya.animation_curve', CURVES[3:])


class BLAYA_PT_animation_onion(bpy.types.Panel):
    bl_label = 'Onion Skin'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.blaya_onion
        layout.operator('blaya.onion_skin', text='Onion Skin', icon='GHOST_ENABLED',
                        depress=onion_skin.active(context.scene))
        row = layout.row(align=True)
        before = row.column(align=True)
        before.prop(settings, 'before')
        before.prop(settings, 'before_color', text='')
        after = row.column(align=True)
        after.prop(settings, 'after')
        after.prop(settings, 'after_color', text='')
        layout.prop(settings, 'step')
        layout.prop(settings, 'opacity', slider=True)
        layout.operator('blaya.onion_refresh', icon='FILE_REFRESH')


CLASSES = (BLAYA_AnimationSettings, BLAYA_OT_animation_key, BLAYA_OT_animation_timing,
           BLAYA_OT_animation_curve, BLAYA_OT_animation_frame, BLAYA_OT_animation_workspace,
           BLAYA_PT_animation_workspace, BLAYA_PT_animation_keying,
           BLAYA_PT_animation_timing, BLAYA_PT_animation_curves, BLAYA_PT_animation_onion)


def register():
    onion_skin.register()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blaya_animation = PointerProperty(type=BLAYA_AnimationSettings)


def unregister():
    onion_skin.unregister()
    del bpy.types.Scene.blaya_animation
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
