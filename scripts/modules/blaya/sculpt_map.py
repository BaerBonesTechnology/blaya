"""ZBrush terminology mapped to Blender workflows, without claiming parity."""
import bpy
from bpy.props import StringProperty, EnumProperty
from .search_map import entry, search

ENTRIES = [
    entry('standard', 'Standard Brush', 'Draw', 'standard draw sculpt raise lower',
          'Sculpt Mode → Brush Asset Shelf → Draw',
          'A starting point for adding or removing volume. Brush falloff and stroke response differ; adjust strength and radius.'),
    entry('move', 'Move Brush', 'Grab', 'move grab pull silhouette',
          'Sculpt Mode → Brush Asset Shelf → Grab',
          'Pulls existing vertices to reshape the silhouette. It does not add topology; use enough geometry for the intended change.'),
    entry('clay', 'ClayBuildup', 'Clay Strips / Clay', 'clay buildup claybuildup build volume',
          'Sculpt Mode → Brush Asset Shelf → Clay Strips or Clay',
          'Related volume-building brushes, not exact ZBrush brush replicas. Tune strength, tip shape and stroke spacing.'),
    entry('damstandard', 'DamStandard', 'Draw Sharp / Crease', 'dam standard damstandard sharp crease carve',
          'Sculpt Mode → Brush Asset Shelf → Draw Sharp or Crease',
          'Useful starting points for sharp grooves and creases. Their profiles differ from DamStandard.'),
    entry('smooth', 'Smooth / Shift', 'Smooth', 'shift smooth smoothing',
          'Sculpt Mode → Brush Asset Shelf → Smooth; inspect Sculpt keymap for temporary smoothing',
          'Blender supports smoothing brushes. This learning map does not remap Shift or install ZBrush interaction controls.'),
    entry('mask', 'Mask / Ctrl', 'Mask', 'ctrl mask paint protect inverse clear',
          'Sculpt Mode → Mask tools and Mask menu',
          'Masks protect parts of a sculpt. Invert, clear, grow, shrink and smooth operations are available. Ctrl gestures depend on the active keymap.'),
    entry('polygroups', 'PolyGroups', 'Face Sets', 'polygroup polygroups groups face set hide isolate',
          'Sculpt Mode → Face Sets menu',
          'Face Sets organize sculpt regions for visibility and brush behavior. They are not mesh objects, material slots or a complete PolyGroups replacement.'),
    entry('dynamesh', 'DynaMesh', 'Voxel Remesh', 'dynamesh dyna mesh remesh rebuild fuse resolution',
          'Sculpt Mode → Remesh → Voxel Size / Remesh',
          'Related topology-rebuilding workflow, with different algorithms. Smaller voxels create more geometry. Remeshing changes topology and can remove fine detail; duplicate the mesh first when needed.'),
    entry('sculptris', 'Sculptris Pro', 'Dynamic Topology (Dyntopo)', 'sculptris pro dynamic topology dyntopo detail',
          'Sculpt Mode → Dyntopo',
          'Changes topology locally during strokes. It is not subdivision-level sculpting and requires a different workflow from Multires.'),
    entry('subdivision', 'Subdivision Levels', 'Multiresolution Modifier', 'subdivision subdivide levels multires multiresolution',
          'Properties → Modifiers → Multiresolution',
          'Sculpt across subdivision levels on a stable base mesh. Topology-changing operations can conflict with this workflow; Voxel Remesh is not a way to add a Multires level.'),
    entry('zremesher', 'ZRemesher', 'QuadriFlow Remesh / Manual Retopology', 'zremesher quad remesh retopology retopo',
          'Object Mode → Object Data Properties → Remesh → QuadriFlow; or retopology in Edit Mode',
          'QuadriFlow is an automatic quad-remeshing option, not the same solver as ZRemesher. Inspect edge flow and preserve the source sculpt for projection.'),
    entry('subtools', 'SubTools', 'Objects / Collections', 'subtool subtools separate objects collection',
          'Outliner → Objects / Collections',
          'Use objects for separate sculpt pieces and collections to organize them. Switching the active sculpt object is a distinct operation from hiding or isolating it.'),
    entry('symmetry', 'Activate Symmetry', 'Sculpt Symmetry', 'symmetry mirror x y z radial',
          'Sculpt Mode → Symmetry controls',
          'Mirror strokes across the chosen object-local axes. Stroke symmetry differs from a Mirror modifier or a one-time Symmetrize operation.'),
    entry('lazymouse', 'LazyMouse', 'Stabilize Stroke', 'lazy mouse lazymouse stabilize smooth stroke',
          'Active Brush Settings → Stroke → Stabilize Stroke, when supported',
          'Stabilizes the stroke path with radius and factor controls. Availability depends on the brush/stroke type; behavior differs from LazyMouse.'),
    entry('navigation', 'ZBrush Navigation', 'Viewport Navigation / Keymap', 'orbit pan zoom navigation pen tablet right click',
          'Preferences → Keymap; Kitchen 3D Tools → Setup',
          'Kitchen 3D currently uses Industry Compatible controls. This map explains equivalents only; a dedicated ZBrush navigation preset is not yet installed.'),
]
BY_ID = {item['id']: item for item in ENTRIES}
ITEMS = [(i['id'], i['maya']+' → '+i['blender'], i['note']) for i in ENTRIES]


class BLAYA_OT_sculpt_map_details(bpy.types.Operator):
    bl_idname = 'blaya.sculpt_map_details'
    bl_label = 'ZBrush → Blender Learning Map'
    entry_id: StringProperty()

    @classmethod
    def description(cls, context, properties):
        item = BY_ID.get(properties.entry_id)
        return item['blender']+'\n'+item['where']+'\n\n'+item['note'] if item else 'Find the Blender sculpt workflow'

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)

    def draw(self, context):
        from . import hint
        item = BY_ID.get(self.entry_id)
        if item:
            self.layout.label(text=item['maya']+' → '+item['blender'])
            hint(self.layout, item['where']+'\n\n'+item['note'])

    def execute(self, context):
        return {'FINISHED'}


class BLAYA_OT_sculpt_map_search(bpy.types.Operator):
    bl_idname = 'blaya.sculpt_map_search'
    bl_label = 'Search ZBrush → Blender Learning Map'
    bl_property = 'entry_id'
    entry_id: EnumProperty(items=ITEMS)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context):
        return bpy.ops.blaya.sculpt_map_details('INVOKE_DEFAULT', entry_id=self.entry_id)


class BLAYA_PT_sculpt_learning(bpy.types.Panel):
    bl_label = 'ZBrush → Blender Learning Map'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sculpt'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(context.window_manager, 'blaya_sculpt_query', text='', icon='VIEWZOOM')
        matches = search(context.window_manager.blaya_sculpt_query, ENTRIES)
        if not matches:
            layout.label(text='No matches')
        for item in matches:
            layout.operator('blaya.sculpt_map_details', text=item['maya']).entry_id = item['id']


CLASSES = (BLAYA_OT_sculpt_map_details, BLAYA_OT_sculpt_map_search, BLAYA_PT_sculpt_learning)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.blaya_sculpt_query = StringProperty(
        name='ZBrush or Blender tool', description='Search sculpting tools and related Blender workflows',
        options={'SKIP_SAVE', 'TEXTEDIT_UPDATE'})


def unregister():
    del bpy.types.WindowManager.blaya_sculpt_query
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
