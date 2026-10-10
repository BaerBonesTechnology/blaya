"""Native soft-selection, transform constraints, and explicit edge shading."""
import bpy,bmesh

class BLAYA_OT_edge_shading(bpy.types.Operator):
    bl_idname='blaya.edge_shading';bl_label='Edge Shading';bl_options={'REGISTER','UNDO'}
    hard:bpy.props.BoolProperty(default=True)
    @classmethod
    def description(cls,context,p):
        return 'Mark selected edges sharp and smooth their adjacent faces' if p.hard else 'Clear sharpness on selected edges and smooth their adjacent faces'
    @classmethod
    def poll(cls,context):return context.mode=='EDIT_MESH'
    def execute(self,context):
        count=0
        for obj in context.objects_in_mode_unique_data:
            bm=bmesh.from_edit_mesh(obj.data)
            for edge in bm.edges:
                if edge.select and not edge.hide:
                    edge.smooth=not self.hard;count+=1
                    for face in edge.link_faces:
                        if not face.hide:face.smooth=True
            bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
        self.report({'INFO'},f'Updated {count} edges');return {'FINISHED'}


def draw_transform(layout,context):
    from . import hint
    s=context.scene.tool_settings
    box=layout.box();row=box.row(align=True)
    row.prop(s,'use_proportional_edit',text='Soft Selection',toggle=True)
    hint(row,'Proportional Editing is Blender’s soft selection. During a transform, scroll to change the influence radius. Connected limits influence to connected geometry; Projected ignores depth. Object Mode has a separate toggle below.')
    row=box.row(align=True);row.prop(s,'use_proportional_connected',text='Connected');row.prop(s,'use_proportional_projected',text='Projected')
    box.prop(s,'proportional_edit_falloff',text='Falloff');box.prop(s,'proportional_size',text='Radius')
    box.prop(s,'use_proportional_edit_objects',text='Soft Object Selection')
    row=box.row(align=True);row.label(text='Transform Constraints')
    hint(row,'While transforming: X/Y/Z constrains to an axis; Shift-X/Y/Z excludes that axis. Press the axis twice for local alignment. These are Blender’s modal transform keys; the Axis selector above sets the transform orientation.')
    box.prop(context.scene,'blaya_constraint_tool',text='')
    row=box.row(align=True);row.operator_context='INVOKE_REGION_WIN'
    for index,axis in enumerate('XYZ'):
        row.operator(context.scene.blaya_constraint_tool,text=axis).constraint_axis=tuple(i==index for i in range(3))
    box.prop(s,'snap_target',text='Snap With')
    row=box.row(align=True)
    for prop,label in (('use_snap_translate','Move'),('use_snap_rotate','Rotate'),('use_snap_scale','Scale')):row.prop(s,prop,text=label,toggle=True)
    box.prop(s,'use_mesh_automerge',text='Auto Merge')
    if s.use_mesh_automerge:box.prop(s,'double_threshold',text='Merge Distance')


def draw_shading(layout,context):
    row=layout.row(align=True)
    row.operator('blaya.edge_shading',text='Hard',icon='EDGE_SHARP').hard=True
    row.operator('blaya.edge_shading',text='Soft',icon='MOD_SMOOTH').hard=False


def register():
    bpy.utils.register_class(BLAYA_OT_edge_shading)
    bpy.types.Scene.blaya_constraint_tool=bpy.props.EnumProperty(name='Transform',items=[('transform.translate','Move','Constrain movement to the chosen axis'),('transform.rotate','Rotate','Constrain rotation to the chosen axis'),('transform.resize','Scale','Constrain scale to the chosen axis')])
def unregister():
    del bpy.types.Scene.blaya_constraint_tool
    bpy.utils.unregister_class(BLAYA_OT_edge_shading)
