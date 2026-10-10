"""UI panel snapshots, cross-editor routing, and modeling and UV undo/redo regressions."""
import os
import json
import tempfile
import traceback
from pathlib import Path
import bpy
import bmesh
import numpy as np
from blaya import native_editor, workspace

output=Path(os.environ.get('KITCHEN3D_TEST_OUTPUT',str(Path(tempfile.gettempdir())/'kitchen3d-ui')))
output.mkdir(parents=True,exist_ok=True)
reference=os.environ.get('KITCHEN3D_SNAPSHOT_BASELINE')
seen=set();errors=[];phase=0;attempts=0;uv_open_requested=False
for panel in native_editor.PANELS:
    bpy.utils.unregister_class(panel);panel.bl_options=set()
    original=panel.draw
    def checked(original,name):
        def draw(self,context):
            try:original(self,context);seen.add(name)
            except Exception:errors.append(traceback.format_exc())
        return draw
    panel.draw=checked(original,panel.__name__)
    bpy.utils.register_class(panel)


def snapshot(tools,name):
    path=output/(name+'.png')
    tools.tag_redraw()
    bpy.ops.screen.screenshot(filepath=str(path))
    image=bpy.data.images.load(str(path),check_existing=False)
    try:
        width,height=image.size
        pixels=np.empty(width*height*4,np.float32);image.pixels.foreach_get(pixels)
        pixels=pixels.reshape(height,width,4)
        # Compare only the tools area, excluding cursor, viewport and OS window chrome.
        sx=width/max(a.x+a.width for a in bpy.context.screen.areas)
        sy=height/max(a.y+a.height for a in bpy.context.screen.areas)
        crop=pixels[round(tools.y*sy):round((tools.y+tools.height)*sy),round(tools.x*sx):round((tools.x+tools.width)*sx),:3]
        assert crop.size and np.ptp(crop)>.1, 'Panel capture is blank'
        np.savez_compressed(output/(name+'.npz'),pixels=crop)
        if reference:
            baseline=np.load(Path(reference)/(name+'.npz'))['pixels']
            assert baseline.shape==crop.shape, 'Panel dimensions changed'
            difference=np.mean(np.abs(baseline-crop)>.08)
            assert difference<.02,(name,'visual difference fraction',difference)
    finally:bpy.data.images.remove(image)


def current_coords(name):
    obj=bpy.data.objects[name]
    if obj.mode=='EDIT':return np.array([tuple(v.co) for v in bmesh.from_edit_mesh(obj.data).verts])
    return np.array([tuple(v.co) for v in obj.data.vertices])


def undo_tools(context):
    if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    cases=[('circularize',True,{'radius':3}),('space',False,{}),('relax',False,{'iterations':2}),('straighten',False,{})]
    for command,closed,kwargs in cases:
        if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        points=[(2,0,0),(0,1,0),(-2,0,0),(0,-1,0)] if closed else [(0,0,0),(.2,1,0),(2,-1,0),(3,0,0)]
        edges=[(0,1),(1,2),(2,3)]+([(3,0)] if closed else [])
        mesh=bpy.data.meshes.new('Undo mesh');mesh.from_pydata(points,edges,[])
        obj=bpy.data.objects.new('Undo '+command,mesh);bpy.context.collection.objects.link(obj)
        obj.select_set(True);bpy.context.view_layer.objects.active=obj
        name=obj.name;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.ed.undo_push(message='Before '+command)
        before=current_coords(name)
        assert getattr(bpy.ops.blaya,command)(**kwargs)=={'FINISHED'}
        after=current_coords(name);assert not np.allclose(before,after)
        # Scripts need an explicit undo boundary, as Blender does not push one
        # automatically for a nested operator invoked from a Python callback.
        bpy.ops.ed.undo_push(message='After '+command)
        assert bpy.ops.ed.undo()=={'FINISHED'}
        assert np.allclose(current_coords(name),before),command+' undo'
        assert bpy.ops.ed.redo()=={'FINISHED'}
        assert np.allclose(current_coords(name),after),command+' redo'
    bpy.ops.object.mode_set(mode='OBJECT')


def undo_uv(context):
    if context.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.mesh.primitive_plane_add()
    name=context.object.name
    bpy.ops.object.mode_set(mode='EDIT')
    context.scene.tool_settings.use_uv_select_sync=True
    bm=bmesh.from_edit_mesh(context.object.data);uv=bm.loops.layers.uv.active
    for face in bm.faces:
        for loop in face.loops:loop[uv].uv*=.5
    def uv_coords():
        mesh=bmesh.from_edit_mesh(bpy.data.objects[name].data);layer=mesh.loops.layers.uv.active
        return np.array([tuple(l[layer].uv) for f in mesh.faces for l in f.loops])
    context.scene.blaya_uv_settings.start_tile=1003
    bpy.ops.ed.undo_push(message='Before UDIM')
    before=uv_coords()
    with native_editor.override(context,'UV'):
        assert bpy.ops.blaya.uv_action(action='UDIM')=={'FINISHED'}
    after=uv_coords();assert not np.allclose(before,after)
    bpy.ops.ed.undo_push(message='After UDIM')
    assert bpy.ops.ed.undo()=={'FINISHED'};assert np.allclose(uv_coords(),before)
    assert bpy.ops.ed.redo()=={'FINISHED'};assert np.allclose(uv_coords(),after)
    bpy.ops.object.mode_set(mode='OBJECT')
    original=context.scene.blaya_uv_settings.density
    bpy.ops.ed.undo_push(message='Before preset')
    assert bpy.ops.blaya.uv_density_preset(density=20.48)=={'FINISHED'}
    bpy.ops.ed.undo_push(message='After preset')
    assert bpy.ops.ed.undo()=={'FINISHED'}
    assert abs(context.scene.blaya_uv_settings.density-original)<.01
    assert bpy.ops.ed.redo()=={'FINISHED'}
    assert abs(context.scene.blaya_uv_settings.density-2048)<.01


def tick():
    global phase,attempts,uv_open_requested
    try:
        tools=next((a for a in bpy.context.screen.areas if a.ui_type=='BLAYA_TOOLS'),None)
        if workspace.PENDING or tools is None:
            attempts+=1;assert attempts<150,'Workspace did not become ready';return .2
        if phase == 0 and not uv_open_requested:
            assert not any(a.ui_type=='UV' for a in bpy.context.screen.areas)
            tools.tag_redraw()
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=3)
            bpy.ops.screen.screenshot(filepath=str(output/'STARTUP.png'))
            assert bpy.ops.blaya.open_uv_editor()=={'FINISHED'}
            uv_open_requested=True
            return .2
        if phase < len(native_editor.WORKFLOWS)*3:
            index=phase//3;name=native_editor.WORKFLOWS[index][0]
            if phase%3==0:
                tools.spaces.active.blaya_workflow=name;tools.tag_redraw()
            elif phase%3==1:
                tools.tag_redraw()
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=3)
            else:
                snapshot(tools,name)
            phase+=1;return .4
        assert not errors,errors
        assert len(seen)==len(native_editor.PANELS),(seen,len(native_editor.PANELS))
        (output/'panels.json').write_text(json.dumps(sorted(seen),indent=2))
        with native_editor.override(bpy.context,'MODEL'):
            undo_tools(bpy.context)
            undo_uv(bpy.context)
        print('PASS: all workflow panel snapshots and modeling and UV undo/redo',flush=True)
    except Exception:
        traceback.print_exc();print('FAIL: Kitchen 3D UI regression',flush=True)
    bpy.ops.wm.quit_blender();return None

bpy.app.timers.register(tick,first_interval=2)
