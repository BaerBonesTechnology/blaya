"""UV winding inspection. No mesh normals or UV coordinates are modified."""
import bpy
import bmesh
from bpy.props import BoolProperty

HANDLE = None
EPSILON = 1e-12  # UV-coordinate area, independent of island location.
COLORS = {'NORMAL': (0.08, 0.32, 1.0, 0.40),
          'MIRRORED': (1.0, 0.08, 0.07, 0.50),
          'COLLAPSED': (1.0, 0.8, 0.02, 0.9)}


def winding(coords):
    # Translate to the first corner to avoid cancellation for distant UDIM tiles.
    x0, y0 = coords[0]
    area = sum((a[0]-x0)*(b[1]-y0)-(b[0]-x0)*(a[1]-y0)
               for a, b in zip(coords, coords[1:] + coords[:1])) * 0.5
    return 'COLLAPSED' if abs(area) <= EPSILON else 'NORMAL' if area > 0 else 'MIRRORED'


def visible_faces(context, bm):
    sync = context.scene.tool_settings.use_uv_select_sync
    return [face for face in bm.faces if not face.hide and (sync or face.select)]


def redraw(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.tag_redraw()


def draw_overlay():
    context = bpy.context
    if (not getattr(context.window_manager, 'blaya_uv_orientation', False)
            or context.area.type != 'IMAGE_EDITOR' or context.area.ui_type != 'UV'
            or context.mode != 'EDIT_MESH' or not context.space_data.overlay.show_overlays):
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    triangles = {key: [] for key in COLORS}
    lines = []
    points = []
    for obj in context.objects_in_mode_unique_data:
        bm = bmesh.from_edit_mesh(obj.data)
        uv = bm.loops.layers.uv.active
        if uv is None:
            continue
        for face in visible_faces(context, bm):
            coords = [tuple(loop[uv].uv) for loop in face.loops]
            kind = winding(coords)
            screen = [context.region.view2d.view_to_region(*co, clip=False) for co in coords]
            if kind == 'COLLAPSED':
                for a, b in zip(screen, screen[1:] + screen[:1]):
                    lines.extend((a, b))
                # A collapsed-to-point face still gets a visible marker.
                x, y = screen[0]
                points.extend(((x-4,y-4),(x+4,y+4),(x-4,y+4),(x+4,y-4)))
            else:
                for tri in tessellate_polygon([[Vector((x,y,0)) for x,y in screen]]):
                    triangles[kind].extend(screen[index] for index in tri)
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    previous_blend = gpu.state.blend_get()
    try:
        gpu.state.blend_set('ALPHA')
        shader.bind()
        for kind, vertices in triangles.items():
            if vertices:
                shader.uniform_float('color', COLORS[kind])
                batch_for_shader(shader, 'TRIS', {'pos': vertices}).draw(shader)
        if lines or points:
            shader.uniform_float('color', COLORS['COLLAPSED'])
            batch_for_shader(shader, 'LINES', {'pos': lines + points}).draw(shader)
    finally:
        gpu.state.blend_set(previous_blend)


class BLAYA_OT_uv_select_mirrored(bpy.types.Operator):
    bl_idname = 'blaya.uv_select_mirrored'
    bl_label = 'Select Mirrored'
    bl_description = 'Replace selection with mirrored faces among currently visible UVs; does not flip UVs'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.area.type == 'IMAGE_EDITOR' and context.area.ui_type == 'UV'

    def execute(self, context):
        sync = context.scene.tool_settings.use_uv_select_sync
        total = 0
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            uv = bm.loops.layers.uv.active
            if uv is None:
                continue
            faces = visible_faces(context, bm)
            hits = {face for face in faces if winding([tuple(loop[uv].uv) for loop in face.loops]) == 'MIRRORED'}
            if sync:
                for seq in (bm.faces, bm.edges, bm.verts):
                    for elem in seq:
                        elem.select_set(False)
                bm.select_history.clear()
                for face in hits:
                    face.select_set(True)
                bm.select_flush_mode()
            else:
                for face in faces:
                    selected = face in hits
                    face.uv_select_set(selected)
                bm.uv_select_flush_mode()
            total += len(hits)
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        redraw(context)
        self.report({'INFO'}, f'Selected {total} mirrored UV faces; UV coordinates unchanged')
        return {'FINISHED'}


class BLAYA_OT_uv_checker(bpy.types.Operator):
    bl_idname = 'blaya.uv_checker'
    bl_label = 'Checker'
    bl_description = 'Display a generated labeled color grid in this UV Editor; does not assign materials'

    @classmethod
    def poll(cls, context):
        return context.area.type == 'IMAGE_EDITOR' and context.area.ui_type == 'UV'

    def execute(self, context):
        image = next((im for im in bpy.data.images if im.get('blaya_checker') is True), None)
        if image is None:
            image = bpy.data.images.new('Lettered UV Checker', width=1024, height=1024)
            image.generated_type = 'COLOR_GRID'
            image['blaya_checker'] = True
        context.space_data.image = image
        return {'FINISHED'}


class BLAYA_PT_uv_orientation(bpy.types.Panel):
    bl_idname = 'BLAYA_PT_uv_orientation'
    bl_label = 'UV Orientation'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'UV'

    @classmethod
    def poll(cls, context):
        return context.area.ui_type == 'UV'

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(context.window_manager, 'blaya_uv_orientation', text='Orientation', toggle=True)
        row.operator('blaya.hint', text='', icon='INFO', emboss=False).message = (
            'Blue: normal winding. Red: mirrored winding. Yellow: collapsed UV faces. '
            'These colors inspect UV faces, not mesh normals. Mirroring may be intentional; rotation is OK.')
        if context.mode != 'EDIT_MESH':
            layout.label(text='Edit Mode required')
        elif not any(bmesh.from_edit_mesh(o.data).loops.layers.uv.active for o in context.objects_in_mode_unique_data):
            layout.label(text='No UV map')
        if not context.space_data.overlay.show_overlays:
            layout.label(text='Overlays off')
        if context.space_data.uv_editor.show_stretch:
            layout.prop(context.space_data.uv_editor, 'show_stretch', text='UV Stretch')
        layout.operator('blaya.uv_select_mirrored')
        layout.operator('blaya.uv_checker')


CLASSES = (BLAYA_OT_uv_select_mirrored, BLAYA_OT_uv_checker, BLAYA_PT_uv_orientation)


def register():
    global HANDLE
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.blaya_uv_orientation = BoolProperty(default=False, description='Blue: normal UV winding; red: mirrored; yellow: collapsed. Disable UV Stretch to avoid mixed colors. UV Editor overlays must be enabled.', options={'SKIP_SAVE'},
        update=lambda self, context: redraw(context))
    if not bpy.app.background:
        HANDLE = bpy.types.SpaceImageEditor.draw_handler_add(draw_overlay, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global HANDLE
    if HANDLE is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(HANDLE, 'WINDOW')
        HANDLE = None
    del bpy.types.WindowManager.blaya_uv_orientation
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
