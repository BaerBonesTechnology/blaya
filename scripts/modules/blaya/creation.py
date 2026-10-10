"""Mesh shortcuts plus Blender's complete, extensible native object Add menu."""
import bpy

PRIMITIVES = (
    ('add_plane', 'Plane', 'primitive_plane_add', 'MESH_PLANE'),
    ('add_cube', 'Cube', 'primitive_cube_add', 'MESH_CUBE'),
    ('add_circle', 'Circle', 'primitive_circle_add', 'MESH_CIRCLE'),
    ('add_uv_sphere', 'UV Sphere', 'primitive_uv_sphere_add', 'MESH_UVSPHERE'),
    ('add_ico_sphere', 'Ico Sphere', 'primitive_ico_sphere_add', 'MESH_ICOSPHERE'),
    ('add_torus', 'Torus', 'primitive_torus_add', 'MESH_TORUS'),
    ('add_grid', 'Grid', 'primitive_grid_add', 'MESH_GRID'),
    ('add_monkey', 'Monkey', 'primitive_monkey_add', 'MESH_MONKEY'),
)
OPERATORS = {key: operator for key, _, operator, _ in PRIMITIVES}


class BLAYA_PT_create(bpy.types.Panel):
    bl_order = 3
    bl_idname = 'BLAYA_PT_create'
    bl_label = 'Create'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Model'

    def draw(self, context):
        from . import draw_tool_grid, hint
        layout = self.layout
        mesh = layout.column()
        mesh.enabled = context.mode in {'OBJECT', 'EDIT_MESH'}
        draw_tool_grid(mesh, ('add_plane', 'add_cube', 'add_circle', 'add_uv_sphere',
                             'add_ico_sphere', 'cylinder', 'cone', 'add_torus', 'add_grid', 'add_monkey'))
        row = layout.row(align=True)
        row.enabled = context.mode == 'OBJECT'
        row.menu('VIEW3D_MT_add', text='All Objects', icon='ADD')
        hint(row, 'Complete native Blender Add menu: meshes, curves, surfaces, metaballs, text, point clouds, volumes, Grease Pencil, armatures, lattices, empties, images, lights, probes, cameras, speakers, force fields and collection instances. Includes installed add-on entries. Object Mode required. Native entries retain their own defaults; Cylinder/cone shortcuts use triangulated caps.')


CLASSES = (BLAYA_PT_create,)
def register():
    for cls in CLASSES: bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(CLASSES): bpy.utils.unregister_class(cls)
