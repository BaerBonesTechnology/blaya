"""Native tool editor panels with explicit routing to a modeling or UV view."""
import json
from types import SimpleNamespace

import bpy
from bpy.props import StringProperty, BoolProperty

PANELS = []
SIDEBAR_PANELS = []
WORKFLOWS = (
    ('MODEL', 'Model', 'MESH_CUBE'),
    ('UV', 'UV', 'UV'),
    ('SCULPT', 'Sculpt', 'SCULPTMODE_HLT'),
    ('ANIMATION', 'Animation', 'ANIM'),
    ('SCENE', 'Scene', 'OUTLINER'),
    ('SETUP', 'Setup', 'PREFERENCES'),
)


def target_area(context, workflow):
    if context.screen is None:
        return None
    if workflow == 'UV':
        areas = [a for a in context.screen.areas if a.type == 'IMAGE_EDITOR' and a.ui_type == 'UV']
    else:
        areas = [a for a in context.screen.areas if a.type == 'VIEW_3D']
    return max(areas, key=lambda a: a.width * a.height, default=None)


def override(context, workflow):
    area = target_area(context, workflow)
    if area is None:
        raise RuntimeError('Open a UV Editor' if workflow == 'UV' else 'Open a 3D View')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return context.temp_override(window=context.window, area=area, region=region)


def operator_for(identifier):
    module, name = identifier.split('.')
    return getattr(getattr(bpy.ops, module), name)


class BLAYA_OT_editor_action(bpy.types.Operator):
    bl_idname = 'blaya.editor_action'
    bl_label = 'Workflow Tool'
    bl_options = {'INTERNAL'}
    operator_id: StringProperty()
    arguments: StringProperty(default='{}')
    workflow: StringProperty(default='MODEL')
    tooltip: StringProperty()
    invoke_tool: BoolProperty(default=True)

    @classmethod
    def description(cls, context, properties):
        return properties.tooltip or 'Run this tool in the adjacent modeling or UV view'

    def run(self, context, invoke):
        try:
            with override(context, self.workflow):
                op = operator_for(self.operator_id)
                if not op.poll():
                    self.report({'WARNING'}, 'This tool is unavailable for the current selection or mode')
                    return {'CANCELLED'}
                result = op('INVOKE_DEFAULT' if invoke and self.invoke_tool else 'EXEC_DEFAULT',
                            **json.loads(self.arguments))
            # Modal tools install their own handler in the target editor.
            return {'CANCELLED'} if 'CANCELLED' in result else {'FINISHED'}
        except (RuntimeError, TypeError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def invoke(self, context, event):
        return self.run(context, True)

    def execute(self, context):
        return self.run(context, False)


class OperatorArguments:
    def __init__(self, properties, identifier):
        object.__setattr__(self, '_properties', properties)
        object.__setattr__(self, '_identifier', identifier)
        object.__setattr__(self, '_values', {})

    def __setattr__(self, name, value):
        self._values[name] = list(value) if isinstance(value, (tuple, set)) else value
        self._properties.arguments = json.dumps(self._values)
        # Keep the original tool's contextual tooltip, including learning-map hints.
        rna = operator_for(self._identifier).get_rna_type()
        cls = bpy.types.Operator.bl_rna_get_subclass_py(rna.identifier)
        description = getattr(cls, 'description', None)
        if description:
            try:
                self._properties.tooltip = description(bpy.context, SimpleNamespace(**self._values))
            except (AttributeError, KeyError, TypeError):
                pass


class ToolLayout:
    """Reuse existing panel layouts while routing operator buttons to their editor."""
    def __init__(self, layout, workflow, width=240):
        object.__setattr__(self, '_layout', layout)
        object.__setattr__(self, '_workflow', workflow)
        object.__setattr__(self, '_width', width)

    def __setattr__(self, name, value):
        setattr(self._layout, name, value)

    def __getattr__(self, name):
        value = getattr(self._layout, name)
        if name == 'grid_flow':
            from . import prefs
            if prefs().tool_display == 'ICONS':
                return lambda *args, **kwargs: IconGrid(self._layout, self._workflow, self._width)
        if name in {'row', 'column', 'column_flow', 'grid_flow', 'box', 'split'}:
            return lambda *args, **kwargs: ToolLayout(value(*args, **kwargs), self._workflow, self._width - (16 if name == 'box' else 0))
        return value

    def operator(self, identifier, **kwargs):
        op = operator_for(identifier)
        rna = op.get_rna_type()
        kwargs.setdefault('text', rna.name)
        # Source panels are drawn under a real target-area context, so poll remains accurate.
        row = self._layout.column(align=True)
        row.enabled = op.poll()
        properties = row.operator('blaya.editor_action', **kwargs)
        # All routed buttons share one operator. Explicitly set even empty
        # arguments so invoking a no-argument tool cannot reuse the last tool's
        # properties (for example a modeling command on Onion Skin).
        properties.arguments = '{}'
        properties.operator_id = identifier
        properties.workflow = self._workflow
        properties.tooltip = rna.description or rna.name
        properties.invoke_tool = self._layout.operator_context.startswith('INVOKE')
        return OperatorArguments(properties, identifier)

    def menu(self, identifier, **kwargs):
        arguments = self.operator('wm.call_menu', **kwargs)
        arguments.name = identifier
        return arguments


class IconGrid:
    """Fixed-size square buttons wrap to the actual panel width."""
    def __init__(self, layout, workflow, width):
        self.layout = layout.column(align=False)
        self.workflow = workflow
        self.columns = max(1, int(max(32, width - 32) // 40))
        self.count = 0
        self.row = None
        self.scale_y = 1.5

    def operator(self, identifier, **kwargs):
        if self.count % self.columns == 0:
            self.row = self.layout.row(align=False)
            self.row.alignment = 'LEFT'
            self.row.scale_x = 1.5
            self.row.scale_y = 1.5
        self.count += 1
        return ToolLayout(self.row, self.workflow).operator(identifier, **kwargs)


def draw_navigation(layout, space):
    layout.prop_tabs_enum(space, 'blaya_workflow', icon_only=True)


def make_panel(source, workflow, order):
    source_poll = source.__dict__.get('poll')

    def poll(cls, context):
        return (context.space_data.blaya_workflow == workflow
                and (workflow != 'UV' or order == 0 or target_area(context, workflow) is not None))

    def draw(self, context):
        target = target_area(context, workflow)
        if target is None:
            if workflow == 'UV':
                self.layout.operator('blaya.open_uv_editor', icon='UV')
            else:
                self.layout.label(text='Open a 3D View', icon='INFO')
            return
        region = context.region
        left = region.view2d.region_to_view(0, 0)[0]
        right = region.view2d.region_to_view(region.width, 0)[0]
        width = abs(right - left) / context.preferences.system.ui_scale
        with override(context, workflow):
            if source_poll and not source_poll.__func__(source, bpy.context):
                self.layout.label(text='Select a mesh and enter Edit Mode', icon='INFO')
                return
            source.draw(SimpleNamespace(layout=ToolLayout(self.layout, workflow, width)), bpy.context)

    return type('BLAYA_NATIVE_PT_' + source.__name__.removeprefix('BLAYA_PT_'), (bpy.types.Panel,), {
        '__module__': __name__,
        'bl_label': source.bl_label,
        'bl_space_type': 'PROPERTIES',
        'bl_region_type': 'WINDOW',
        'bl_context': 'blaya',
        'bl_order': order,
        'bl_options': set(getattr(source, 'bl_options', set())),
        'poll': classmethod(poll),
        'draw': draw,
    })


def register():
    import blaya as core
    from . import creation, model_workflow, uv_orientation, uv_workflow, shelf_workflow, animation, sculpt_map
    groups = {
        'MODEL': (core.BLAYA_PT_shelf, model_workflow.BLAYA_PT_selection,
                  model_workflow.BLAYA_PT_pivot, creation.BLAYA_PT_create,
                  core.BLAYA_PT_model_tools, core.BLAYA_PT_cleanup, core.BLAYA_PT_learning),
        'UV': (core.BLAYA_PT_uv_shelf, uv_orientation.BLAYA_PT_uv_orientation,
               uv_workflow.BLAYA_PT_uv_finish, core.BLAYA_PT_uv_learning),
        'SCULPT': (sculpt_map.BLAYA_PT_sculpt_learning,),
        'ANIMATION': (animation.BLAYA_PT_animation_workspace, animation.BLAYA_PT_animation_keying,
                      animation.BLAYA_PT_animation_timing, animation.BLAYA_PT_animation_curves,
                      animation.BLAYA_PT_animation_onion),
        'SCENE': (model_workflow.BLAYA_PT_scene,),
        'SETUP': (core.BLAYA_PT_setup, shelf_workflow.BLAYA_PT_shortcuts),
    }
    bpy.utils.register_class(BLAYA_OT_editor_action)
    for workflow, sources in groups.items():
        for index, source in enumerate(sources):
            panel = make_panel(source, workflow, index)
            bpy.utils.register_class(panel)
            PANELS.append(panel)
    for module in (core, creation, model_workflow, uv_orientation, uv_workflow, shelf_workflow, animation, sculpt_map):
        for cls in module.CLASSES:
            if issubclass(cls, bpy.types.Panel):
                SIDEBAR_PANELS.append(cls)
                bpy.utils.unregister_class(cls)


def unregister():
    for panel in reversed(PANELS):
        bpy.utils.unregister_class(panel)
    PANELS.clear()
    for panel in SIDEBAR_PANELS:
        bpy.utils.register_class(panel)
    SIDEBAR_PANELS.clear()
    bpy.utils.unregister_class(BLAYA_OT_editor_action)
