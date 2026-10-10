import bpy, bmesh, traceback, json
from blaya import loop_tools, workspace, native_editor
phase=0
live=[]
errors=[]
original_draw=loop_tools.BLAYA_OT_relax.draw
def draw(self,context):
    live[:] = [self]
    try: original_draw(self,context)
    except Exception: errors.append(traceback.format_exc())
loop_tools.BLAYA_OT_relax.draw=draw
for cls in native_editor.PANELS:
    if cls.__name__.endswith('_model_tools'):
        original=cls.draw
        def panel_draw(self,context):
            try: original(self,context)
            except Exception: errors.append(traceback.format_exc())
        cls.draw=panel_draw
base=[]
def tick():
    global phase
    try:
        if workspace.PENDING:return .3
        if phase==0:
            bpy.ops.object.select_all(action='DESELECT')
            mesh=bpy.data.meshes.new('Preview test')
            mesh.from_pydata([(0,0,0),(1,2,0),(2,-1,0),(3,0,0)],[(0,1),(1,2),(2,3)],[])
            obj=bpy.data.objects.new('Preview test',mesh)
            bpy.context.collection.objects.link(obj)
            obj.select_set(True)
            bpy.context.view_layer.objects.active=obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            base.extend(v.co.copy() for v in bmesh.from_edit_mesh(mesh).verts)
            area=next(a for a in bpy.context.screen.areas if a.ui_type=='BLAYA_TOOLS')
            with bpy.context.temp_override(area=area,region=next(r for r in area.regions if r.type=='WINDOW')):
                assert bpy.ops.blaya.editor_action(operator_id='blaya.command',arguments=json.dumps({'command':'relax'}),workflow='MODEL')=={'FINISHED'}
            phase=1
            return .7
        assert live and not errors,errors
        op=live[0]
        bm=bmesh.from_edit_mesh(bpy.context.edit_object.data)
        assert any((v.co-co).length>.01 for v,co in zip(bm.verts,base)), 'No initial live preview'
        op.influence=0
        op.check(bpy.context)
        assert all((v.co-co).length<1e-6 for v,co in zip(bm.verts,base))
        op.influence=.75
        op.check(bpy.context)
        assert any((v.co-co).length>.01 for v,co in zip(bm.verts,base))
        op.cancel(bpy.context)
        assert all((v.co-co).length<1e-6 for v,co in zip(bm.verts,base))
        print('PASS: native tool routing, dialog draw, initial preview, property recompute and Cancel restoration',flush=True)
    except Exception:
        traceback.print_exc()
        print('FAIL: loop UI',flush=True)
    bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(tick,first_interval=2)
