"""Native mesh editing tools and explicit, non-applied symmetry setup."""
import bpy
from . import circular, loop_tools
from bpy.props import EnumProperty, FloatProperty

TOOLS = (
    ('relax', 'Relax', 'MOD_SMOOTH', 'Smooth selected edge chains or loops with live preview; open endpoints stay fixed. Closed loops can shrink.', 'blaya.relax'),
    ('space', 'Space', 'ALIGN_JUSTIFY', 'Evenly space vertices along the selected polyline with live preview; open endpoints stay fixed.', 'blaya.space'),
    ('straighten', 'Straighten', 'IPO_LINEAR', 'Straighten open chains between fixed endpoints with live preview.', 'blaya.straighten'),
    ('circularize', 'Circularize', 'MESH_CIRCLE', 'Round closed edge loops, holes or unconnected vertices. Adjust radius, spacing, center and plane without changing topology.', 'blaya.circularize'),
    ('knife', 'Knife', 'MOD_BUILD', 'Multi-Cut equivalent: draw cuts on the mesh. Enter confirms; Esc cancels. Uses Blender’s native Knife interaction.', 'mesh.knife_tool'),
    ('loop_cut', 'Loop Cut', 'EDGESEL', 'Insert Edge Loop equivalent: hover an edge, scroll for cut count, click to place and slide. Works best on quad strips.', 'mesh.loopcut_slide'),
    ('bisect', 'Bisect', 'MOD_BOOLEAN', 'Slice selected geometry with a drawn plane. Blender’s tool options control filling and which side to clear; fill can produce n-gons.', 'mesh.bisect'),
    ('connect', 'Connect', 'AUTOMERGE_ON', 'Connect selected vertices across faces with Connect Vertex Path. Select vertices on a connected face path first.', 'mesh.vert_connect_path'),
    ('bridge', 'Bridge', 'MOD_SOLIDIFY', 'Bridge selected open edge loops. Equal vertex counts produce the most predictable quad strips; adjust twist and cuts in Adjust Last Operation.', 'mesh.bridge_edge_loops'),
    ('grid_fill', 'Grid Fill', 'MESH_GRID', 'Fill selected boundary edges with a quad grid. Use a suitable closed boundary with an even vertex count; adjust span and offset in Adjust Last Operation.', 'mesh.fill_grid'),
    ('edge_slide', 'Slide', 'ARROW_LEFTRIGHT', 'Slide selected edges along neighboring edges without a free transform. Move the mouse, then click to confirm or Esc to cancel.', 'transform.edge_slide'),
    ('dissolve', 'Dissolve', 'X', 'Dissolve selected components while retaining surrounding surfaces. Can create n-gons; inspect topology afterward.', 'mesh.dissolve_mode'),
    ('crease', 'Crease', 'EDGE_CREASE', 'Adjust subdivision crease on selected edges. Enter a value or move the mouse; requires subdivision to see the smoothing effect.', 'transform.edge_crease'),
    ('flip_normals', 'Flip', 'NORMALS_FACE', 'Reverse normals on selected faces. Use Face Orientation to inspect the result.', 'mesh.flip_normals'),
    ('face_orientation', 'Orientation', 'FACESEL', 'Toggle this viewport’s Face Orientation overlay: blue front faces and red back faces. This checks mesh normals, not UV winding.', None),
    ('mirror', 'Mirror', 'MOD_MIRROR', 'Add an X-axis Mirror modifier with merge and clipping, or show the first existing Mirror. Uses the local origin by default; start with a half mesh to avoid overlapping copies. Does not delete geometry or apply the modifier.', None),
    ('symmetrize', 'Symmetrize', 'MOD_MIRROR', 'Copy selected mesh geometry from one local-axis side to the other. Choose the source side before confirming; this changes topology and is separate from a live Mirror modifier.', None),
)
BY_KEY = {row[0]: row for row in TOOLS}


def active_mirror(context):
    obj = context.active_object
    return next((m for m in obj.modifiers if m.type == 'MIRROR'), None) if obj and obj.type == 'MESH' else None


class BLAYA_OT_mirror_setup(bpy.types.Operator):
    bl_idname = 'blaya.mirror_setup'
    bl_label = 'Set Up Mirror'
    bl_description = BY_KEY['mirror'][3]
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.is_editable and context.mode in {'OBJECT', 'EDIT_MESH'}

    def execute(self, context):
        mod = active_mirror(context)
        if mod is None:
            mod = context.active_object.modifiers.new('Mirror', 'MIRROR')
            mod.use_axis = (True, False, False)
            mod.use_clip = True
            mod.use_mirror_merge = True
            self.report({'INFO'}, 'Mirror added about the local X origin; use a half mesh to avoid overlap')
        else:
            self.report({'INFO'}, 'Using existing Mirror; settings preserved')
        return {'FINISHED'}


class BLAYA_OT_symmetrize(bpy.types.Operator):
    bl_idname = 'blaya.symmetrize'
    bl_label = 'Symmetrize Selection'
    bl_description = BY_KEY['symmetrize'][3]
    bl_options = {'REGISTER', 'UNDO'}
    direction: EnumProperty(name='Copy', items=[
        ('NEGATIVE_X', '-X → +X', 'Use the negative local X side as source'),
        ('POSITIVE_X', '+X → -X', 'Use the positive local X side as source'),
        ('NEGATIVE_Y', '-Y → +Y', 'Use the negative local Y side as source'),
        ('POSITIVE_Y', '+Y → -Y', 'Use the positive local Y side as source'),
        ('NEGATIVE_Z', '-Z → +Z', 'Use the negative local Z side as source'),
        ('POSITIVE_Z', '+Z → -Z', 'Use the positive local Z side as source'),
    ], default='NEGATIVE_X')
    threshold: FloatProperty(name='Merge Distance', default=.0001, min=0, precision=5)

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.prop(self, 'direction')
        self.layout.prop(self, 'threshold')

    def execute(self, context):
        return bpy.ops.mesh.symmetrize(direction=self.direction, threshold=self.threshold)


def run(operator, context, key):
    if context.area is None or context.area.type != 'VIEW_3D':
        operator.report({'WARNING'}, 'Use a 3D Viewport')
        return {'CANCELLED'}
    if key == 'face_orientation':
        context.space_data.overlay.show_face_orientation = not context.space_data.overlay.show_face_orientation
        return {'FINISHED'}
    if key == 'mirror':
        if not BLAYA_OT_mirror_setup.poll(context):
            operator.report({'WARNING'}, 'Select an editable mesh in Object or mesh Edit Mode')
            return {'CANCELLED'}
        return bpy.ops.blaya.mirror_setup()
    if context.mode != 'EDIT_MESH':
        operator.report({'WARNING'}, 'Select mesh components in Edit Mode first')
        return {'CANCELLED'}
    try:
        if key == 'symmetrize':
            result = bpy.ops.blaya.symmetrize('INVOKE_DEFAULT')
        else:
            module, name = BY_KEY[key][4].split('.')
            result = getattr(getattr(bpy.ops, module), name)('INVOKE_DEFAULT')
        # The native operator owns its modal handler; this dispatcher is finished.
        return {'FINISHED'} if 'RUNNING_MODAL' in result else result
    except RuntimeError as error:
        operator.report({'WARNING'}, str(error))
        return {'CANCELLED'}


def draw(layout, context):
    from . import draw_tool_grid, hint
    for title, keys in (
        ('Cut / Connect', ('knife', 'loop_cut', 'bisect', 'connect', 'bridge', 'grid_fill')),
        ('Shape / Spacing', ('circularize', 'relax', 'space', 'straighten')),
        ('Edges', ('edge_slide', 'dissolve', 'crease')),
        ('Normals', ('normals', 'flip_normals', 'face_orientation')),
        ('Symmetry', ('mirror', 'symmetrize')),
    ):
        box = layout.box()
        box.label(text=title)
        draw_tool_grid(box, keys)
        if title == 'Shape / Spacing':
            settings = context.scene.blaya_mesh_settings
            box.prop(settings, 'interaction', expand=True)
            box.prop(settings, 'surface')
            if any(m.show_viewport and m.type in {'MIRROR', 'BOOLEAN', 'ARRAY', 'REMESH', 'NODES'}
                   for obj in context.objects_in_mode_unique_data for m in obj.modifiers):
                box.label(text='Edits affect the base mesh; modifiers stay live', icon='INFO')
            if settings.surface == 'TARGET':
                box.prop(settings, 'target')
            box.prop(settings, 'allow_shape_keys')
            hint(box, 'Drag mode: move the mouse to change radius or influence; wheel changes iterations or strength; X/Y/Z/B chooses the circularize plane. Enter applies, Esc restores. Surface projection uses the original evaluated surface. Modifiers stay unapplied; shape-key editing requires explicit opt-in.')
        if title == 'Normals':
            from .finishing import draw_shading
            draw_shading(box,context)
        if title == 'Symmetry':
            mod = active_mirror(context)
            if mod:
                box.label(text=mod.name, icon='MOD_MIRROR')
                box.prop(mod, 'use_axis', text='Axis', toggle=True)
                row = box.row(align=True)
                row.prop(mod, 'use_clip', text='Clip')
                row.prop(mod, 'use_mirror_merge', text='Merge')
                box.prop(mod, 'merge_threshold', text='Distance')
                box.prop(mod, 'mirror_object', text='Center')
                hint(box, 'Controls the first Mirror modifier on the active object. Other Mirror modifiers remain available in Properties > Modifiers. Axes are local to the object, or the chosen Center object. Clipping constrains center vertices during edits; it does not remove overlapping halves.')


CLASSES = (BLAYA_OT_mirror_setup, BLAYA_OT_symmetrize)
def register():
    from . import mesh_preview
    mesh_preview.register()
    circular.register()
    loop_tools.register()
    for cls in CLASSES: bpy.utils.register_class(cls)
def unregister():
    loop_tools.unregister()
    circular.unregister()
    from . import mesh_preview
    mesh_preview.unregister()
    for cls in reversed(CLASSES): bpy.utils.unregister_class(cls)
