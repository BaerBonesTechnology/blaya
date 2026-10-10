"""Atomic edit-mesh previews with dialog and viewport interaction."""
import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy.props import BoolProperty, EnumProperty, PointerProperty
from .geometry_math import coordinates, transform_points


class BLAYA_MeshSettings(bpy.types.PropertyGroup):
    interaction: EnumProperty(name='Interaction', items=[
        ('MODAL', 'Drag', 'Drag in the viewport; Enter applies and Esc cancels'),
        ('DIALOG', 'Dialog', 'Adjust exact values in a live preview dialog')], default='DIALOG')
    allow_shape_keys: BoolProperty(name='Edit Active Shape Key', default=False,
        description='Explicitly allow coordinate edits on the active shape key; vertex order is preserved')
    surface: EnumProperty(name='Surface', items=[
        ('NONE', 'Free', 'Do not project edited vertices'),
        ('SUBSURF', 'Evaluated Subdivision', 'Project onto the original evaluated subdivision mesh; an approximation to the limit surface'),
        ('TARGET', 'Target Mesh', 'Project onto the evaluated surface of another mesh')], default='NONE')
    target: PointerProperty(name='Target', type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH')


def settings(context):
    return getattr(context.scene, 'blaya_mesh_settings', None)


class MeshPreview:
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def validate(self, context):
        config = settings(context)
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            if not any(v.select and not v.hide for v in bm.verts):
                continue
            if not obj.data.is_editable:
                raise ValueError(f'{obj.name}: mesh is read-only')
            if obj.data.shape_keys and not getattr(config, 'allow_shape_keys', False):
                raise ValueError(f'{obj.name}: shape keys are present. Enable Edit Active Shape Key to modify the active key')

    def capture(self, context):
        self.validate(context)
        self._snapshot = []
        self._mesh_state = []
        self._surfaces = {}
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.index_update()
            selected = [(v, v.co.copy()) for v in bm.verts if v.select and not v.hide]
            self._snapshot.append((obj, selected))
            self._mesh_state.append((obj, obj.data, obj.active_shape_key_index, len(bm.verts), bm))
        self.prepare_surfaces(context)

    def validate_snapshot(self):
        for obj, data, key, count, bm in getattr(self, '_mesh_state', ()):
            if obj.mode != 'EDIT' or obj.data != data or obj.active_shape_key_index != key:
                raise ValueError('The edit mesh or active shape key changed; restart the tool')
            if len(bmesh.from_edit_mesh(data).verts) != count:
                raise ValueError('Mesh topology changed during preview; restart the tool')
        for obj, vertices in getattr(self, '_snapshot', ()):
            if any(not isinstance(v, int) and not v.is_valid for v, co in vertices):
                raise ValueError('Mesh topology changed during preview; restart the tool')

    def restore(self):
        self.validate_snapshot()
        for obj, vertices in getattr(self, '_snapshot', ()):
            if obj.mode != 'EDIT':
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            for vertex, co in vertices:
                # Integer snapshots remain supported for existing test/extension callers.
                (bm.verts[vertex] if isinstance(vertex, int) else vertex).co = co
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

    def prepare_surfaces(self, context):
        config = settings(context)
        mode = getattr(config, 'surface', 'NONE')
        if mode == 'NONE':
            return
        depsgraph = context.evaluated_depsgraph_get()
        for obj, vertices in self._snapshot:
            if not vertices:
                continue
            target = config.target if mode == 'TARGET' else obj
            if target is None or target.type != 'MESH':
                raise ValueError('Choose a mesh surface target')
            if mode == 'TARGET' and target in context.objects_in_mode_unique_data:
                raise ValueError('Surface target must be outside the current edit selection')
            if mode == 'SUBSURF' and not any(m.type == 'SUBSURF' and m.show_viewport for m in obj.modifiers):
                raise ValueError(f'{obj.name}: add an enabled Subdivision Surface modifier first')
            obj.update_from_editmode()
            evaluated = target.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                if mesh is None or not mesh.polygons:
                    raise ValueError('Surface target has no faces')
                mesh.calc_loop_triangles()
                if len(mesh.loop_triangles) > 1_000_000:
                    raise ValueError('Surface target exceeds 1 million triangles')
                points = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
                mesh.vertices.foreach_get('co', points)
                world = transform_points(evaluated.matrix_world, points.reshape(-1, 3))
                triangles = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
                mesh.loop_triangles.foreach_get('vertices', triangles)
                self._surfaces[obj.as_pointer()] = BVHTree.FromPolygons(world.tolist(), triangles.reshape(-1, 3).tolist(), all_triangles=True)
            finally:
                evaluated.to_mesh_clear()

    def apply_geometry(self, context):
        self.validate(context)
        changes = self.calculate_changes(context)
        if not changes:
            raise ValueError('Select at least three vertices')
        prepared = []
        for obj, bm, vertices, points in changes:
            points = coordinates(points)
            if len(points) != len(vertices) or any(not v.is_valid for v in vertices):
                raise ValueError('Geometry changed while preparing the tool')
            surface = getattr(self, '_surfaces', {}).get(obj.as_pointer())
            if surface:
                world = transform_points(obj.matrix_world, points)
                hits = [surface.find_nearest(Vector(p))[0] for p in world]
                if any(p is None for p in hits):
                    raise ValueError('Could not find the target surface')
                points = transform_points(obj.matrix_world.inverted(), hits)
            prepared.append((obj, bm, vertices, points))
        # BMesh has no foreach_set: retain safe edit-mode writes, update once per mesh.
        touched = {}
        rollback = [(v, v.co.copy()) for obj, bm, vertices, points in prepared for v in vertices]
        try:
            for obj, bm, vertices, points in prepared:
                touched[obj.as_pointer()] = (obj, bm)
                for vertex, point in zip(vertices, points):
                    vertex.co = point
        except Exception:
            for vertex, co in rollback:
                if vertex.is_valid:
                    vertex.co = co
            raise
        finally:
            for obj, bm in touched.values():
                bm.normal_update()
                bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=False)

    def invoke(self, context, event):
        try:
            self.capture(context)
        except (ValueError, RuntimeError, ReferenceError) as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        self.check(context)
        if getattr(settings(context), 'interaction', 'DIALOG') == 'MODAL' and context.area.type == 'VIEW_3D':
            self._area = context.area
            self._mouse_x = event.mouse_x
            self._drag_property = 'radius' if hasattr(self, 'radius') else 'influence'
            if self._drag_property == 'radius' and self.radius == 0 and not self._preview_error:
                # Separate objects/loops can be far apart: seed from their fitted
                # radii, never from the bounds of the combined selection.
                radii = []
                for obj, bm, vertices, points in self.calculate_changes(context):
                    world = transform_points(obj.matrix_world, points)
                    radii.append(np.linalg.norm(world - world.mean(axis=0), axis=1).mean())
                self.radius = max(float(np.median(radii)), .001)
                self.check(context)
            self._initial_value = getattr(self, self._drag_property)
            self._drag_scale = max(self._initial_value, .001) / 200 if self._drag_property == 'radius' else .005
            context.window_manager.modal_handler_add(self)
            self.update_header()
            return {'RUNNING_MODAL'}
        return context.window_manager.invoke_props_dialog(self, width=360, confirm_text='Apply')

    def update_header(self):
        error = getattr(self, '_preview_error', '')
        self._area.header_text_set(error or f'{self.bl_label}: drag {self._drag_property} | Wheel: iterations/strength | X/Y/Z/B: plane | Enter: apply | Esc: cancel')

    def modal(self, context, event):
        try:
            self.validate_snapshot()
            if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
                self.cancel(context)
                return {'CANCELLED'}
            if event.type in {'RET', 'NUMPAD_ENTER', 'LEFTMOUSE'} and event.value == 'PRESS':
                if self._preview_error:
                    self.report({'WARNING'}, self._preview_error)
                    return {'RUNNING_MODAL'}
                self._area.header_text_set(None)
                return self.execute(context)
            changed = False
            if event.type == 'MOUSEMOVE':
                value = self._initial_value + (event.mouse_x - self._mouse_x) * self._drag_scale
                setattr(self, self._drag_property, max(0, min(1, value)) if self._drag_property == 'influence' else max(.000001, value))
                changed = True
            elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                sign = 1 if event.type == 'WHEELUPMOUSE' else -1
                if hasattr(self, 'iterations'):
                    self.iterations = max(1, min(100, self.iterations + sign))
                else:
                    self.influence = max(0, min(1, self.influence + sign * .05))
                    if self._drag_property == 'influence':
                        self._initial_value, self._mouse_x = self.influence, event.mouse_x
                changed = True
            elif event.type in {'X', 'Y', 'Z', 'B'} and event.value == 'PRESS' and hasattr(self, 'plane'):
                self.plane = 'BEST' if event.type == 'B' else event.type
                changed = True
            if changed:
                self.check(context)
                self.update_header()
            return {'RUNNING_MODAL'}
        except (ValueError, ReferenceError, RuntimeError) as error:
            self.report({'WARNING'}, str(error))
            try:
                self.cancel(context)
            except (ValueError, ReferenceError, RuntimeError):
                self._area.header_text_set(None)
            return {'CANCELLED'}

    def check(self, context):
        if not getattr(self, '_snapshot', None):
            return False
        self._preview_error = ''
        try:
            self.restore()
            self.apply_geometry(context)
        except (ValueError, RuntimeError, ReferenceError) as error:
            self._preview_error = str(error)
        return True

    def cancel(self, context):
        try:
            self.restore()
        finally:
            self._snapshot = []
            self._mesh_state = []
            self._surfaces = {}
            if getattr(self, '_area', None):
                self._area.header_text_set(None)

    def execute(self, context):
        try:
            if not getattr(self, '_snapshot', None):
                self.capture(context)
            self.restore()
            self.apply_geometry(context)
        except (ValueError, RuntimeError, ReferenceError) as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        finally:
            self._snapshot = []
            self._mesh_state = []
            self._surfaces = {}
        return {'FINISHED'}

    def draw_error(self):
        if getattr(self, '_preview_error', ''):
            box = self.layout.box()
            box.alert = True
            import textwrap
            for line in textwrap.wrap(self._preview_error, 44):
                box.label(text=line)


def register():
    bpy.utils.register_class(BLAYA_MeshSettings)
    bpy.types.Scene.blaya_mesh_settings = PointerProperty(type=BLAYA_MeshSettings)


def unregister():
    del bpy.types.Scene.blaya_mesh_settings
    bpy.utils.unregister_class(BLAYA_MeshSettings)
