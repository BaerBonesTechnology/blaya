"""UV finishing tools and reversible checker material preview."""
import math
import bpy
import bmesh
from bpy.props import IntProperty, FloatProperty, BoolProperty, PointerProperty, CollectionProperty, EnumProperty
from mathutils import Vector


def selected_face(context, face):
    return not face.hide and (face.select if context.scene.tool_settings.use_uv_select_sync else face.select and all(l.uv_select_vert for l in face.loops))


def uv_islands(bm, layer):
    """Connected faces whose shared-edge UV endpoints coincide."""
    pending = set(bm.faces)  # Hidden neighbors keep the island connected; partial selection is skipped.
    while pending:
        seed = pending.pop(); island = {seed}; stack = [seed]
        while stack:
            face = stack.pop()
            for loop in face.loops:
                for other in loop.edge.link_loops:
                    adjacent = other.face
                    if adjacent not in pending:
                        continue
                    a = {l.vert: l[layer].uv for l in (loop, loop.link_loop_next)}
                    b = {l.vert: l[layer].uv for l in (other, other.link_loop_next)}
                    if a.keys() == b.keys() and all((a[v]-b[v]).length_squared < 1e-14 for v in a):
                        pending.remove(adjacent); island.add(adjacent); stack.append(adjacent)
        yield island


def island_areas(bm, island, layer, matrix):
    uv_area = world_area = 0.0
    for loops in bm.calc_loop_triangles():
        if loops[0].face not in island:
            continue
        a,b,c = [l[layer].uv for l in loops]
        uv_area += abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5
        a,b,c = [matrix @ l.vert.co for l in loops]
        world_area += (b-a).cross(c-a).length*.5
    return uv_area, world_area


class BLAYA_UVSettings(bpy.types.PropertyGroup):
    resolution: IntProperty(name='Texture', default=2048, min=64, max=32768, description='Square texture resolution in pixels')
    padding: IntProperty(name='Padding', default=8, min=0, max=256, description='Pack margin in pixels at the chosen texture resolution')
    density: FloatProperty(name='px / meter', default=512, min=.01, max=100000, description='Target texel density in pixels per meter; respects object scale and scene unit scale')
    pack_scale: BoolProperty(name='Fit Tile', default=False, description='Allow packing to rescale islands to fit. Disable to preserve texel density')


class BLAYA_OT_uv_action(bpy.types.Operator):
    bl_idname='blaya.uv_action'
    bl_label='UV Tool'
    bl_options={'REGISTER','UNDO'}
    action: EnumProperty(items=[(k,n,d) for k,n,d in (
        ('CUT','Cut','Rip selected UV boundaries and move; confirm the offset to separate the UVs'),
        ('SEW','Sew','Stitch selected matching UV edges using Blender stitch options'),
        ('RELAX','Relax','Minimize stretching of selected UVs'),
        ('PIN','Pin','Pin selected UVs for subsequent unwrapping'),
        ('UNPIN','Unpin','Unpin selected UVs'),
        ('HORIZONTAL','Horizontal','Align selected UVs to a horizontal line; use on an edge row, not an entire island'),
        ('VERTICAL','Vertical','Align selected UVs to a vertical line; use on an edge column, not an entire island'),
        ('OVERLAP','Overlap','Select overlapping UV faces using Blender overlap selection'),
        ('OUTSIDE','Outside Tile','Select faces with any UV corner outside the 0–1 tile. UDIM tiles may be intentional'),
        ('DENSITY','Set Density','Scale fully selected UV islands to the specified pixels per meter; partial islands are skipped'),
        ('PACK','Pack','Pack selected UV islands using pixel padding. Fit Tile changes density when enabled'),
    )])

    @classmethod
    def poll(cls,context):
        return context.mode=='EDIT_MESH' and context.area and context.area.type=='IMAGE_EDITOR' and context.area.ui_type=='UV'

    @classmethod
    def description(cls,context,properties):
        return cls.bl_rna.properties['action'].enum_items[properties.action].description

    def execute(self,context):
        s=context.scene.blaya_uv_settings
        try:
            if self.action in {'CUT','SEW'}:
                result = bpy.ops.uv.rip_move('INVOKE_DEFAULT') if self.action=='CUT' else bpy.ops.uv.stitch('INVOKE_DEFAULT',snap_islands=True,clear_seams=True)
                return {'FINISHED'} if 'RUNNING_MODAL' in result else result
            if self.action=='RELAX': return bpy.ops.uv.minimize_stretch('EXEC_DEFAULT',iterations=30)
            if self.action in {'PIN','UNPIN'}: return bpy.ops.uv.pin(clear=self.action=='UNPIN')
            if self.action in {'HORIZONTAL','VERTICAL'}:
                return bpy.ops.uv.align(axis='ALIGN_Y' if self.action=='HORIZONTAL' else 'ALIGN_X')
            if self.action=='OVERLAP': return bpy.ops.uv.select_overlap(extend=False)
            if self.action=='PACK':
                return bpy.ops.uv.pack_islands('EXEC_DEFAULT',margin_method='FRACTION',margin=s.padding/s.resolution,
                    scale=s.pack_scale,rotate=True,udim_source='ACTIVE_UDIM')
            if self.action=='OUTSIDE':
                hits_count=0
                for obj in context.objects_in_mode_unique_data:
                    bm=bmesh.from_edit_mesh(obj.data);uv=bm.loops.layers.uv.active
                    if not uv: continue
                    from .uv_orientation import visible_faces
                    faces=visible_faces(context,bm)
                    hits={f for f in faces if any(any(v < -1e-6 or v > 1+1e-6 for v in l[uv].uv) for l in f.loops)}
                    if context.scene.tool_settings.use_uv_select_sync:
                        for seq in (bm.faces,bm.edges,bm.verts):
                            for elem in seq: elem.select_set(False)
                        for f in hits:f.select_set(True)
                        bm.select_flush_mode()
                    else:
                        for f in faces:f.uv_select_set(f in hits)
                        bm.uv_select_flush_mode()
                    hits_count+=len(hits);bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
                self.report({'INFO'},f'Selected {hits_count} faces outside 0–1')
            elif self.action=='DENSITY':
                changed=skipped=0
                for obj in context.objects_in_mode_unique_data:
                    bm=bmesh.from_edit_mesh(obj.data);uv=bm.loops.layers.uv.active
                    if not uv:continue
                    for island in uv_islands(bm,uv):
                        chosen=[f for f in island if selected_face(context,f)]
                        if not chosen:continue
                        if len(chosen)!=len(island): skipped+=1;continue
                        uv_area,world_area=island_areas(bm,island,uv,obj.matrix_world)
                        world_area*=context.scene.unit_settings.scale_length**2
                        if min(uv_area,world_area)<=1e-15:skipped+=1;continue
                        current=s.resolution*math.sqrt(uv_area/world_area)
                        factor=s.density/current
                        loops=[l for f in island for l in f.loops]
                        center=sum((l[uv].uv for l in loops),Vector((0,0)))/len(loops)
                        for l in loops:l[uv].uv=center+(l[uv].uv-center)*factor
                        changed+=1
                    bmesh.update_edit_mesh(obj.data,loop_triangles=False,destructive=False)
                self.report({'INFO'},f'Scaled {changed} islands; skipped {skipped} partial or collapsed islands')
            return {'FINISHED'}
        except RuntimeError as error:
            self.report({'WARNING'},str(error));return {'CANCELLED'}


class BLAYA_MaterialBackup(bpy.types.PropertyGroup):
    material: PointerProperty(type=bpy.types.Material)


def restore_checkers():
    restored=0
    for mesh in bpy.data.meshes:
        if not mesh.blaya_checker_active:continue
        saved=[slot.material for slot in mesh.blaya_checker_backup]
        # No clear/rebuild for existing slots: preserve polygon material indices.
        for i,mat in enumerate(saved):
            if i<len(mesh.materials):mesh.materials[i]=mat
            else:mesh.materials.append(mat)
        while len(mesh.materials)>len(saved):mesh.materials.pop(index=len(mesh.materials)-1)
        mesh.blaya_checker_backup.clear();mesh.blaya_checker_active=False;restored+=1
    return restored


class BLAYA_OT_checker_material(bpy.types.Operator):
    bl_idname='blaya.checker_material'
    bl_label='Checker Preview'
    bl_description='Preview a lettered checker on selected single-user meshes. Restore returns original material slots; use Material Preview shading to see it'
    bl_options={'REGISTER','UNDO'}
    restore: BoolProperty(default=False)

    def execute(self,context):
        if self.restore:
            self.report({'INFO'},f'Restored {restore_checkers()} mesh material sets');return {'FINISHED'}
        objects=[o for o in context.selected_objects if o.type=='MESH']
        if not objects or any(o.data.users>1 or o.data.library for o in objects):
            self.report({'WARNING'},'Select local single-user meshes for checker preview');return {'CANCELLED'}
        if any(not o.data.uv_layers.active for o in objects):
            self.report({'WARNING'},'Every selected mesh needs an active UV map');return {'CANCELLED'}
        image=next((im for im in bpy.data.images if im.get('blaya_checker') is True),None)
        if image is None:
            image=bpy.data.images.new('Lettered UV Checker',width=1024,height=1024);image.generated_type='COLOR_GRID';image['blaya_checker']=True
        mat=next((m for m in bpy.data.materials if m.get('blaya_preview') is True),None)
        if mat is None:
            mat=bpy.data.materials.new('Checker Preview');mat.use_nodes=True;mat['blaya_preview']=True
            tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
            mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        for o in objects:
            mesh=o.data
            if mesh.blaya_checker_active:continue
            if any(slot.link=='OBJECT' for slot in o.material_slots):
                self.report({'WARNING'},f'Skipped {o.name}: object-linked materials');continue
            for original in mesh.materials:mesh.blaya_checker_backup.add().material=original
            mesh.blaya_checker_active=True
            if not mesh.materials:mesh.materials.append(mat)
            else:
                for i in range(len(mesh.materials)):mesh.materials[i]=mat
        return {'FINISHED'}


def buttons(layout,context,items):
    from . import prefs
    display=prefs(context).tool_display
    grid=layout.grid_flow(row_major=True,columns=4 if display=='ICONS' else 1,even_columns=True,align=True)
    for action,label,icon in items:
        grid.operator('blaya.uv_action',text='' if display=='ICONS' else label,icon=icon if display!='TEXT' else 'NONE').action=action


class BLAYA_PT_uv_finish(bpy.types.Panel):
    bl_idname='BLAYA_PT_uv_finish';bl_label='UV Finish';bl_space_type='IMAGE_EDITOR';bl_region_type='UI';bl_category='UV'
    @classmethod
    def poll(cls,context):return context.area.ui_type=='UV'
    def draw(self,context):
        l=self.layout;s=context.scene.blaya_uv_settings
        from .diagnostics import draw_uv
        draw_uv(l,context)
        buttons(l,context,[('CUT','Cut','SCULPTMODE_HLT'),('SEW','Sew','AUTOMERGE_ON'),('RELAX','Relax','MOD_SMOOTH'),('PIN','Pin','PINNED'),('UNPIN','Unpin','UNPINNED'),('HORIZONTAL','Horizontal','TRIA_RIGHT'),('VERTICAL','Vertical','TRIA_UP'),('OVERLAP','Overlap','SELECT_INTERSECT'),('OUTSIDE','Outside','SELECT_DIFFERENCE')])
        l.prop(s,'resolution');l.prop(s,'density')
        buttons(l,context,[('DENSITY','Set Density','UV_SYNC_SELECT')])
        row=l.row(align=True);row.prop(s,'padding');row.prop(s,'pack_scale')
        buttons(l,context,[('PACK','Pack','UV_ISLANDSEL')])
        if any(m.blaya_checker_active for m in bpy.data.meshes):l.label(text='Checker preview active',icon='TEXTURE')
        row=l.row(align=True);row.operator('blaya.checker_material',text='Preview',icon='TEXTURE');row.operator('blaya.checker_material',text='Restore',icon='LOOP_BACK').restore=True


CLASSES=(BLAYA_UVSettings,BLAYA_MaterialBackup,BLAYA_OT_uv_action,BLAYA_OT_checker_material,BLAYA_PT_uv_finish)
def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.blaya_uv_settings=PointerProperty(type=BLAYA_UVSettings)
    bpy.types.Mesh.blaya_checker_backup=CollectionProperty(type=BLAYA_MaterialBackup)
    bpy.types.Mesh.blaya_checker_active=BoolProperty(default=False)
def unregister():
    # Native startup modules unregister under restricted data access at shutdown.
    if hasattr(bpy.data, "meshes"):
        restore_checkers()
    del bpy.types.Mesh.blaya_checker_active;del bpy.types.Mesh.blaya_checker_backup;del bpy.types.Scene.blaya_uv_settings
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
