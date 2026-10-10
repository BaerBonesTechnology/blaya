"""Reversible dialog previews always recompute from the original coordinates."""
import bmesh


class MeshPreview:
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def restore(self):
        for obj, vertices in getattr(self, '_snapshot', ()):
            if obj.mode != 'EDIT':
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            for index, co in vertices:
                bm.verts[index].co = co
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=False)

    def apply_geometry(self, context):
        changes = self.calculate_changes(context)
        if not changes:
            raise ValueError('Select at least three vertices')
        for obj, bm, vertices, points in changes:
            for vertex, point in zip(vertices, points):
                vertex.co = point
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=False)

    def invoke(self, context, event):
        self._snapshot = []
        for obj in context.objects_in_mode_unique_data:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.index_update()
            self._snapshot.append((obj, [(v.index, v.co.copy()) for v in bm.verts
                                         if v.select and not v.hide]))
        self.check(context)
        return context.window_manager.invoke_props_dialog(self, width=340, confirm_text='Apply')

    def check(self, context):
        if not getattr(self, '_snapshot', None):
            return False
        self.restore()
        self._preview_error = ''
        try:
            self.apply_geometry(context)
        except ValueError as error:
            self._preview_error = str(error)
        return True

    def cancel(self, context):
        self.restore()
        self._snapshot = []

    def execute(self, context):
        self.restore()
        self._snapshot = []
        try:
            self.apply_geometry(context)
        except ValueError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}

    def draw_error(self):
        if getattr(self, '_preview_error', ''):
            box = self.layout.box()
            box.alert = True
            # Short wrapped messages remain readable in the compact dialog.
            import textwrap
            for line in textwrap.wrap(self._preview_error, 44):
                box.label(text=line)
