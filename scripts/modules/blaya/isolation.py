"""Toggle object and component isolation without revealing previously hidden geometry."""
import bpy
import bmesh
from bpy.app.handlers import persistent

STARTED_LOCAL = set()

LAYERS = ('.kitchen3d_isolate_vertices', '.kitchen3d_isolate_edges', '.kitchen3d_isolate_faces')


def isolated(mesh):
    if mesh.is_editmode:
        bm = bmesh.from_edit_mesh(mesh)
        return any(seq.layers.int.get(name) is not None
                   for seq, name in zip((bm.verts, bm.edges, bm.faces), LAYERS))
    return any(mesh.attributes.get(name) is not None for name in LAYERS)


def restore(mesh):
    if mesh.is_editmode:
        bm = bmesh.from_edit_mesh(mesh)
        for seq, name in zip((bm.verts, bm.edges, bm.faces), LAYERS):
            layer = seq.layers.int.get(name)
            if layer is None:
                continue
            for element in seq:
                saved = element[layer]
                if saved:
                    element.hide = saved == 2
                    if element.hide:
                        element.select_set(False)
            seq.layers.int.remove(layer)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    else:
        for seq, name in zip((mesh.vertices, mesh.edges, mesh.polygons), LAYERS):
            attribute = mesh.attributes.get(name)
            if attribute is None:
                continue
            for element, saved in zip(seq, attribute.data):
                if saved.value:
                    element.hide = saved.value == 2
                    if element.hide:
                        element.select = False
            mesh.attributes.remove(attribute)
        mesh.update()


class BLAYA_OT_isolate_selection(bpy.types.Operator):
    bl_idname = 'blaya.isolate_selection'
    bl_label = 'Isolate Selection'
    bl_description = 'Toggle isolation of selected objects or mesh components; restore previous visibility on the next press'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode in {'OBJECT', 'EDIT_MESH'}

    def execute(self, context):
        space = context.space_data
        saved = {obj.data for obj in context.scene.objects
                 if obj.type == 'MESH' and obj.data.is_editable and isolated(obj.data)}
        if saved:
            for mesh in saved:
                restore(mesh)
            if space.as_pointer() in STARTED_LOCAL and space.local_view:
                bpy.ops.view3d.localview(frame_selected=False)
            STARTED_LOCAL.discard(space.as_pointer())
            return {'FINISHED'}
        if context.mode == 'OBJECT':
            STARTED_LOCAL.discard(space.as_pointer())
            if not space.local_view and not context.selected_objects:
                self.report({'WARNING'}, 'Select objects to isolate')
                return {'CANCELLED'}
            return bpy.ops.view3d.localview(frame_selected=False)
        objects = list(context.objects_in_mode_unique_data)
        if not any(v.select and not v.hide for obj in objects for v in bmesh.from_edit_mesh(obj.data).verts):
            self.report({'WARNING'}, 'Select mesh components to isolate')
            return {'CANCELLED'}
        # BMesh custom-data follows topology edits and survives leaving Edit Mode.
        # 0 denotes newly created geometry; 1/2 record visible/hidden elements.
        for obj in objects:
            bm = bmesh.from_edit_mesh(obj.data)
            for seq, name in zip((bm.verts, bm.edges, bm.faces), LAYERS):
                layer = seq.layers.int.new(name)
                for element in seq:
                    element[layer] = 2 if element.hide else 1
        started_local = not bool(space.local_view)
        restore_local = started_local or space.as_pointer() in STARTED_LOCAL
        try:
            if started_local and bpy.ops.view3d.localview(frame_selected=False) != {'FINISHED'}:
                raise RuntimeError('Could not enter local view')
            if bpy.ops.mesh.hide(unselected=True) != {'FINISHED'}:
                raise RuntimeError('Could not isolate mesh components')
        except RuntimeError as error:
            for obj in objects:
                restore(obj.data)
            if started_local and space.local_view:
                bpy.ops.view3d.localview(frame_selected=False)
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        if restore_local:
            STARTED_LOCAL.add(space.as_pointer())
        return {'FINISHED'}


@persistent
def clear_started(*args):
    STARTED_LOCAL.clear()


def register():
    bpy.app.handlers.load_pre.append(clear_started)
    bpy.utils.register_class(BLAYA_OT_isolate_selection)


def unregister():
    for mesh in getattr(bpy.data, 'meshes', ()):
        if mesh.is_editable and isolated(mesh):
            restore(mesh)
    wm = getattr(bpy.context, 'window_manager', None)
    for window in wm.windows if wm else ():
        for area in window.screen.areas:
            if area.type == 'VIEW_3D' and area.spaces.active.as_pointer() in STARTED_LOCAL:
                with bpy.context.temp_override(window=window, area=area):
                    if area.spaces.active.local_view:
                        bpy.ops.view3d.localview(frame_selected=False)
    STARTED_LOCAL.clear()
    if clear_started in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(clear_started)
    bpy.utils.unregister_class(BLAYA_OT_isolate_selection)
