"""Selection, pivots, scene organization and a context pie menu."""
import bpy,bmesh,json,hashlib
from bpy.props import StringProperty,EnumProperty,PointerProperty
from mathutils import Vector
from . import isolation


def topology_signature(bm):
    for seq in (bm.verts,bm.edges,bm.faces):seq.index_update()
    payload=(len(bm.verts),sorted(tuple(sorted(v.index for v in e.verts)) for e in bm.edges),
             sorted(tuple(v.index for v in f.verts) for f in bm.faces))
    return hashlib.sha256(repr(payload).encode()).hexdigest()


class BLAYA_WorkflowSettings(bpy.types.PropertyGroup):
    selection_name:StringProperty(name='Set',default='Selection')
    group_name:StringProperty(name='Group',default='Group')
    rename_base:StringProperty(name='Base',default='Part')
    pivot_backup:StringProperty(options={'HIDDEN'})


ACTIONS=[
 ('LOOP','Loop','Select edge loops from selected edges','UV_EDGESEL'),
 ('RING','Ring','Select edge rings from selected edges','UV_FACESEL'),
 ('GROW','Grow','Grow component selection','ADD'),
 ('SHRINK','Shrink','Shrink component selection','REMOVE'),
 ('TRIS','Triangles','Select triangular faces','MOD_TRIANGULATE'),
 ('QUADS','Quads','Select quadrilateral faces','MESH_PLANE'),
 ('SAVE_SET','Save','Save the current component selection by name on each edited mesh','FILE_TICK'),
 ('LOAD_SET','Recall','Recall a saved selection; refuses changed topology','LOOP_BACK'),
 ('TEMP_PIVOT','Set Pivot','Place a temporary transform pivot at the selection; restores previous cursor and pivot with Restore','PIVOT_CURSOR'),
 ('RESTORE_PIVOT','Restore','Restore the cursor and transform pivot saved by Set Pivot','LOOP_BACK'),
 ('GROUP','Group','Parent selected root objects to a new Empty while preserving world transforms','OUTLINER_OB_EMPTY'),
 ('PARENT','Parent','Parent selected objects to the active object while preserving world transforms','CON_CHILDOF'),
 ('UNPARENT','Unparent','Clear parents while preserving world transforms','UNLINKED'),
 ('ISOLATE','Isolate','Toggle isolation of selected objects or mesh components; Ctrl-I restores previous visibility','HIDE_OFF'),
 ('COLLECTION','Collection','Move selected objects to a collection','OUTLINER_COLLECTION'),
]


class BLAYA_OT_workflow(bpy.types.Operator):
    bl_idname='blaya.workflow';bl_label='Workflow Tool';bl_options={'REGISTER','UNDO'}
    action:EnumProperty(items=[(k,n,d) for k,n,d,_ in ACTIONS])
    @classmethod
    def description(cls,context,properties):return next(d for k,n,d,i in ACTIONS if k==properties.action)
    @classmethod
    def poll(cls,context):return context.area is not None and context.area.type=='VIEW_3D'
    def execute(self,context):
        s=context.scene.blaya_workflow
        mesh_actions={'LOOP','RING','GROW','SHRINK','TRIS','QUADS','SAVE_SET','LOAD_SET'}
        if self.action in mesh_actions and context.mode!='EDIT_MESH':
            self.report({'WARNING'},'Mesh Edit Mode required');return {'CANCELLED'}
        try:
            if self.action=='LOOP':return bpy.ops.mesh.select_edge_loop_multi()
            if self.action=='RING':return bpy.ops.mesh.select_edge_ring_multi()
            if self.action=='GROW':return bpy.ops.mesh.select_more()
            if self.action=='SHRINK':return bpy.ops.mesh.select_less()
            if self.action in {'TRIS','QUADS'}:
                bpy.ops.mesh.select_mode(type='FACE')
                return bpy.ops.mesh.select_face_by_sides(number=3 if self.action=='TRIS' else 4,type='EQUAL',extend=False)
            if self.action in {'SAVE_SET','LOAD_SET'}:
                name=s.selection_name.strip()
                if not name:self.report({'WARNING'},'Enter a selection-set name');return {'CANCELLED'}
                records=[]
                for obj in context.objects_in_mode_unique_data:
                    bm=bmesh.from_edit_mesh(obj.data)
                    saved=json.loads(obj.data.blaya_selection_sets or '{}')
                    signature=topology_signature(bm)
                    if self.action=='SAVE_SET':
                        saved[name]={'signature':signature,'mode':list(context.tool_settings.mesh_select_mode),
                            'selection':[[e.index for e in seq if e.select and not e.hide] for seq in (bm.verts,bm.edges,bm.faces)]}
                        obj.data.blaya_selection_sets=json.dumps(saved)
                    else:
                        record=saved.get(name)
                        if not record or record['signature']!=signature:
                            self.report({'WARNING'},f'{obj.name}: missing set or topology changed; selection unchanged');return {'CANCELLED'}
                        records.append((obj,bm,record))
                for obj,bm,record in records:
                    context.tool_settings.mesh_select_mode=record['mode']
                    # Deselect first: deselecting a face/edge also clears its vertices.
                    # Restore positive flags afterward so vertex-only sets survive.
                    for seq in (bm.faces,bm.edges,bm.verts):
                        for e in seq:e.select_set(False)
                    for seq,indices in zip((bm.verts,bm.edges,bm.faces),record['selection']):
                        chosen=set(indices)
                        for e in seq:
                            if e.index in chosen and not e.hide:e.select_set(True)
                    bm.select_history.clear();bm.select_flush_mode();bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
                return {'FINISHED'}
            if self.action=='TEMP_PIVOT':
                if not context.selected_objects:return {'CANCELLED'}
                if not s.pivot_backup:
                    s.pivot_backup=json.dumps({'location':list(context.scene.cursor.location),'rotation':list(context.scene.cursor.rotation_euler),
                        'mode':context.scene.cursor.rotation_mode,'pivot':context.scene.tool_settings.transform_pivot_point})
                bpy.ops.view3d.snap_cursor_to_selected();context.scene.tool_settings.transform_pivot_point='CURSOR'
                return {'FINISHED'}
            if self.action=='RESTORE_PIVOT':
                if s.pivot_backup:
                    saved=json.loads(s.pivot_backup);context.scene.cursor.location=saved['location'];context.scene.cursor.rotation_mode=saved['mode'];context.scene.cursor.rotation_euler=saved['rotation']
                    context.scene.tool_settings.transform_pivot_point=saved['pivot'];s.pivot_backup=''
                return {'FINISHED'}
            if self.action=='ISOLATE':return bpy.ops.blaya.isolate_selection()
            if context.mode!='OBJECT':self.report({'WARNING'},'Object Mode required');return {'CANCELLED'}
            if self.action=='PARENT':return bpy.ops.object.parent_set(type='OBJECT',keep_transform=True)
            if self.action=='UNPARENT':return bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            if self.action=='COLLECTION':
                result=bpy.ops.object.move_to_collection('INVOKE_DEFAULT')
                return {'FINISHED'} if 'RUNNING_MODAL' in result else result
            if self.action=='GROUP':
                selected=set(context.selected_objects)
                def has_selected_parent(obj):
                    parent=obj.parent
                    while parent:
                        if parent in selected:return True
                        parent=parent.parent
                    return False
                roots=[o for o in selected if not has_selected_parent(o)]
                if not roots:return {'CANCELLED'}
                group=bpy.data.objects.new(s.group_name.strip() or 'Group',None);context.collection.objects.link(group)
                group.location=sum((o.matrix_world.translation for o in roots),Vector())/len(roots)
                context.view_layer.update()
                for obj in roots:
                    world=obj.matrix_world.copy();obj.parent=group;obj.matrix_world=world
                for obj in selected:obj.select_set(False)
                group.select_set(True);context.view_layer.objects.active=group
                return {'FINISHED'}
        except RuntimeError as error:self.report({'WARNING'},str(error));return {'CANCELLED'}
        return {'CANCELLED'}


class BLAYA_OT_snap(bpy.types.Operator):
    bl_idname='blaya.snap';bl_label='Snap Target';bl_description='Enable snapping to this target. Toggle the magnet to turn snapping off'
    target:EnumProperty(items=[(k,k.title(),'') for k in ('VERTEX','EDGE','FACE','GRID')])
    def execute(self,context):
        context.scene.tool_settings.snap_elements={self.target};context.scene.tool_settings.use_snap=True
        return {'FINISHED'}


class BLAYA_OT_rename(bpy.types.Operator):
    bl_idname='blaya.rename';bl_label='Batch Rename';bl_description='Preview and rename selected objects to Base_001, Base_002, etc., ordered by current name';bl_options={'REGISTER','UNDO'}
    base:StringProperty(name='Base',default='Part')
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and bool(context.selected_objects)
    def invoke(self,context,event):
        self.base=context.scene.blaya_workflow.rename_base
        return context.window_manager.invoke_props_dialog(self,width=360)
    def draw(self,context):
        self.layout.prop(self,'base')
        for i,o in enumerate(sorted(context.selected_objects,key=lambda o:o.name)[:8],1):self.layout.label(text=f'{o.name} → {self.base}_{i:03d}')
    def execute(self,context):
        if not self.base.strip():return {'CANCELLED'}
        context.scene.blaya_workflow.rename_base=self.base.strip()
        for i,o in enumerate(sorted(context.selected_objects,key=lambda o:o.name),1):o.name=f'{self.base.strip()}_{i:03d}'
        return {'FINISHED'}


def buttons(layout,context,keys):
    from . import prefs
    display=prefs(context).tool_display
    grid=layout.grid_flow(row_major=True,columns=4 if display=='ICONS' else 1,even_columns=True,align=True)
    for key in keys:
        k,name,desc,icon=next(a for a in ACTIONS if a[0]==key)
        grid.operator('blaya.workflow',text='' if display=='ICONS' else name,icon=icon if display!='TEXT' else 'NONE').action=k


class BLAYA_PT_selection(bpy.types.Panel):
    bl_order = 1
    bl_idname='BLAYA_PT_selection';bl_label = 'Selection';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Model'
    def draw(self,context):
        l=self.layout;buttons(l,context,['LOOP','RING','GROW','SHRINK','TRIS','QUADS'])
        l.prop(context.scene.blaya_workflow,'selection_name');buttons(l,context,['SAVE_SET','LOAD_SET'])


class BLAYA_PT_pivot(bpy.types.Panel):
    bl_order = 2
    bl_idname='BLAYA_PT_pivot';bl_label = 'Pivot';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Model';bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        l=self.layout;s=context.scene.tool_settings
        buttons(l,context,['TEMP_PIVOT','RESTORE_PIVOT'])
        l.prop(s,'transform_pivot_point',text='Pivot');l.prop(context.scene.transform_orientation_slots[0],'type',text='Axis')
        row=l.row(align=True);row.prop(s,'use_snap',text='',icon='SNAP_ON');row.prop(s,'snap_elements',text='Target')
        from .finishing import draw_transform
        draw_transform(l,context)
        if context.scene.blaya_workflow.pivot_backup:l.label(text='Temporary pivot active',icon='PIVOT_CURSOR')


class BLAYA_PT_scene(bpy.types.Panel):
    bl_idname='BLAYA_PT_scene';bl_label='Scene Tools';bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Scene'
    def draw(self,context):
        l=self.layout;l.prop(context.scene.blaya_workflow,'group_name')
        buttons(l,context,['GROUP','PARENT','UNPARENT','ISOLATE','COLLECTION'])
        l.operator('blaya.rename',text='Rename',icon='SORTALPHA')


class BLAYA_MT_context_pie(bpy.types.Menu):
    bl_idname='BLAYA_MT_context_pie';bl_label='Kitchen 3D'
    def draw(self,context):
        pie=self.layout.menu_pie()
        if context.area.type=='IMAGE_EDITOR':
            for action,label,icon in [('CUT','Cut','SCULPTMODE_HLT'),('SEW','Sew','AUTOMERGE_ON'),('RELAX','Relax','MOD_SMOOTH'),('PACK','Pack','UV_ISLANDSEL'),('PIN','Pin','PINNED'),('UNPIN','Unpin','UNPINNED'),('DENSITY','Density','UV_SYNC_SELECT')]:
                pie.operator('blaya.uv_action',text=label,icon=icon).action=action
        elif context.mode=='EDIT_MESH':
            for key,label,icon in [('extrude','Extrude','ORIENTATION_NORMAL'),('bevel','Bevel','EDGE_BEVEL'),('merge','Merge','AUTOMERGE_ON')]:pie.operator('blaya.command',text=label,icon=icon).command=key
            for action in ('LOOP','RING','GROW','SHRINK'):pie.operator('blaya.workflow',text=action.title()).action=action
        else:
            for key,label,icon in [('freeze','Freeze','FREEZE'),('origin_center','Center Pivot','OBJECT_ORIGIN'),('origin_edit','Edit Pivot','TRANSFORM_ORIGINS')]:pie.operator('blaya.command',text=label,icon=icon).command=key
            for action in ('GROUP','PARENT','UNPARENT','ISOLATE'):pie.operator('blaya.workflow',text=action.title()).action=action
        pie.operator('blaya.map_search',text='Search',icon='VIEWZOOM')


CLASSES=(BLAYA_WorkflowSettings,BLAYA_OT_workflow,BLAYA_OT_snap,BLAYA_OT_rename,BLAYA_PT_selection,BLAYA_PT_pivot,BLAYA_PT_scene,BLAYA_MT_context_pie)
def register():
    isolation.register()
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.blaya_workflow=PointerProperty(type=BLAYA_WorkflowSettings)
    bpy.types.Mesh.blaya_selection_sets=StringProperty(default='{}')
def unregister():
    isolation.unregister()
    del bpy.types.Mesh.blaya_selection_sets;del bpy.types.Scene.blaya_workflow
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
